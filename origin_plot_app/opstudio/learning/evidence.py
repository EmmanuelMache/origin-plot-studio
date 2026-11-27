"""evidence.py - a sanitised evidence bundle for the fortnightly improvement cycle, built from LOCAL records.

build(service) groups what this installation recorded into items a maintainer (or a scheduled coding job) can act on,
and export(service, path) writes them as one JSON file. Writing the file is a local action: THIS MODULE UPLOADS
NOTHING and needs no developer token, no AI credentials and no account.

Consent: records enter a bundle only while the diagnostics preference is on (it is off by default). With the
preference off the bundle has no items.

What an item is made of - and only of this: the sanitised structure signature ('p2:', see signatures), the data
family, a template id of the installed catalogue, the app version, a category, the class of an error (a word, never a
message), a count of DISTINCT operations (a retry or a repeated signal of one operation counts once), first / last
date, and the before / after interpretation as structural role words. Never rows, values, header text, file names,
paths, sample names, titles or notes. An item whose columns cannot be named by a recognised role is withheld.

Three kinds are kept apart, because they call for different work:
    defect       the software failed or keeps needing the same correction (parser failure, a template that was
                 recommended and could not be drawn, the same format corrected in two or more separate operations)
    preference   the user chose something (a template, a style, a saved workflow, an accepted suggestion):
                 DATA, not a bug - no code change and no version bump follows from it
    request      a single correction or a rejected suggestion: unverified; it may or may not be a defect

Schema 'opstudio.evidence/1':
    {"schema", "generated_at", "app_version", "installation", "items": [
        {"id", "category", "kind", "data_family", "signature", "signature_version", "template_id", "app_version",
         "count", "first_seen", "last_seen", "before", "after", "validation", "error_class"}]}
    category: classification_error | parser_failure | incompatible_recommendation | repeated_correction |
              confirmed_workflow | preference | feedback
    installation: a random id created once on this computer (not derived from the machine or the user).
"""
import json, os

from . import models as M, privacy, signatures as sg
from .models import Outcome, ActionResult
from .store import StorageUnavailable

CATEGORIES = ("classification_error", "parser_failure", "incompatible_recommendation", "repeated_correction", "confirmed_workflow", "preference", "feedback")
ITEM_KINDS = ("defect", "preference", "request")
_EVENT_CATEGORY = {"classification_corrected": "classification_error", "column_mapping_corrected": "repeated_correction", "unit_mapping_confirmed": "repeated_correction",
                   "workflow_saved": "confirmed_workflow", "template_preference_saved": "preference", "graph_style_saved": "preference",
                   "suggestion_accepted": "feedback", "suggestion_rejected": "feedback", "import_failed": "parser_failure", "analysis_failed": "incompatible_recommendation"}
ITEM_KEYS = ("id", "category", "kind", "data_family", "signature", "signature_version", "template_id", "app_version", "count", "first_seen", "last_seen",
             "before", "after", "validation", "error_class")


def _kind(category, count, outcome=""):
    if category in ("parser_failure", "incompatible_recommendation"): return "defect"
    if category in ("preference", "confirmed_workflow"): return "preference"
    if category == "feedback": return "preference" if outcome == "accepted" else "request"
    return "defect" if count >= 2 else "request"          # a correction: one is a request, the same one again is a defect


def _collect(service):
    """Raw groups: key -> {'ops': set, 'first', 'last', fields...}. Raises StorageUnavailable."""
    st = service.store; groups = {}; withheld = 0
    def add(category, sig, fam, tid, appv, err, before, after, validation, op, when, outcome=""):
        key = M.digest([category, sig, fam, tid, appv, err, before, after, outcome], 32)
        g = groups.setdefault(key, {"category": category, "signature": sig, "data_family": fam, "template_id": tid, "app_version": appv, "error_class": err,
                                    "before": before, "after": after, "validation": validation, "ops": set(), "first": when, "last": when, "outcome": outcome})
        g["ops"].add(op); g["first"] = min(g["first"], when); g["last"] = max(g["last"], when)
        if when >= g["last"]: g["validation"] = validation
    def flags(v):
        v = v or {}
        return {k: (bool(v[k]) if v.get(k) is not None else None) for k in ("structural_checks_passed", "preview_rendered", "user_confirmed")}
    mems = {m["id"]: m for m in st.memories(limit=100000)}
    for e in st.events(limit=100000):
        cat = _EVENT_CATEGORY.get(e["event_type"])
        if not cat or e["origin"] not in ("user", "memory"): continue
        if cat == "feedback":
            mem = mems.get(e["memory_id"] or "")
            if mem is None: continue
            out = e["event_type"].replace("suggestion_", "")
            add(cat, mem.get("share_signature") or "", mem.get("data_family") or "unknown", mem.get("template_id") or "", e["app_version"], "", {}, {"memory_kind": mem["kind"], "outcome": out},
                flags(None), e["operation_id"], e["created_at"], out)
            continue
        if e["origin"] != "user": continue
        ctx = e["context"] or {}
        b, r1 = privacy.shareable_snapshot(e["before"], ctx); a, r2 = privacy.shareable_snapshot(e["after"], ctx)
        if r1 or r2: withheld += 1; continue
        sig = (ctx.get("share_signature") or "") if int(ctx.get("column_count") or 0) else ""
        fam = a.get("data_family") or ctx.get("data_family") or "unknown"
        add(cat, sig, fam, a.get("template_id") or ctx.get("template_id") or "", e["app_version"], "", b, a, flags(e["validation"]), e["operation_id"], e["created_at"])
    for d in st.diagnostics():
        cat = _EVENT_CATEGORY.get(d["event_type"])
        if not cat: continue
        det = d.get("detail") or {}
        if det.get("needs_review"): withheld += 1; continue
        err = "" if d["error_class"] == "not_remembered" else d["error_class"]
        add(cat, d["signature"], d["data_family"], d["template_id"], d["app_version"], err, det.get("before") or {}, det.get("after") or {}, flags(None), d["operation_id"], d["created_at"])
    return groups, withheld


def build_with_stats(service):
    """(bundle, stats) - stats = {'consent': bool, 'withheld': n, 'storage': bool}. See the module text."""
    bundle = {"schema": M.EVIDENCE_SCHEMA, "generated_at": M.now_iso(service.clock), "app_version": service.app_version, "installation": service.installation_id(), "items": []}
    stats = {"consent": bool(service.get_settings()["diagnostics"]), "withheld": 0, "storage": True}
    if not stats["consent"]: return bundle, stats
    try: groups, stats["withheld"] = _collect(service)
    except StorageUnavailable:
        stats["storage"] = False; return bundle, stats
    for key in sorted(groups):
        g = groups[key]; n = len(g["ops"])
        item = {"id": "ev_" + key[:20], "category": g["category"], "kind": _kind(g["category"], n, g["outcome"]), "data_family": g["data_family"],
                "signature": g["signature"] if sg.is_shareable_signature(g["signature"]) else "", "signature_version": sg.SIGNATURE_VERSION,
                "template_id": g["template_id"], "app_version": g["app_version"], "count": n, "first_seen": g["first"], "last_seen": g["last"],
                "before": g["before"], "after": g["after"], "validation": g["validation"], "error_class": g["error_class"]}
        if privacy.scan_private(item) or problems_of_item(item): stats["withheld"] += 1; continue
        bundle["items"].append(item)
    bundle["items"].sort(key=lambda i: ({"defect": 0, "request": 1, "preference": 2}[i["kind"]], -i["count"], i["id"]))
    return bundle, stats


def build(service):
    """The evidence bundle (a plain dict of schema 'opstudio.evidence/1'). No items unless the diagnostics preference is on."""
    return build_with_stats(service)[0]


def _write(bundle, path):
    """Write one bundle to `path` through a temporary file of the same folder. OSError when that is not possible."""
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(bundle, f, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


def export(service, path):
    """Write the bundle to `path` (local file; nothing is uploaded). Returns an ActionResult; detail has 'items',
    'withheld', 'consent' and the counts per kind."""
    bundle, stats = build_with_stats(service)
    if not stats["storage"]: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The learning database is not available")
    if not stats["consent"]: return ActionResult(Outcome.DISABLED, "Diagnostics are switched off; there is nothing to export", detail={"items": 0, "consent": False})
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        _write(bundle, path)
    except OSError as e: return ActionResult(Outcome.STORAGE_UNAVAILABLE, f"The file could not be written ({type(e).__name__})")
    kinds = {k: sum(1 for i in bundle["items"] if i["kind"] == k) for k in ITEM_KINDS}
    return ActionResult(Outcome.SAVED, "Evidence exported", detail={"items": len(bundle["items"]), "withheld": stats["withheld"], "consent": True, **kinds})


# ------------------------------------------------------------------------------------------------ the automatic file
# The user may choose a folder ONCE; from then on the same bundle is written there by the app itself, as one file per
# installation. This is still a local write: the module opens no connection. The folder is meant to be one that another
# program of the user copies elsewhere (a Google Drive / OneDrive folder), so the texts of the app say plainly that the
# file leaves the computer that way and that whoever can see the folder can read it. Off by default.
AUTO_FOLDER = "Origin Plot Studio evidence"
AUTO_PREFIX = "ops_evidence_"
_AUTO_KEY = "auto_evidence:folder"


def auto_folder(service):
    """The folder the evidence file is written into by itself; '' while that is off or the database is unavailable."""
    try: return str(service.store.setting(_AUTO_KEY, "") or "")
    except StorageUnavailable: return ""


def auto_file(service):
    """The full name of this installation's automatic file ('' while off): <folder>/ops_evidence_<installation>.json."""
    folder = auto_folder(service); inst = service.installation_id() if folder else ""
    return os.path.join(folder, AUTO_PREFIX + inst + ".json") if folder and inst else ""


def auto_set(service, folder):
    """Switch the automatic evidence file on or off.

    folder: an existing folder the user chose - the file goes into its sub-folder AUTO_FOLDER (the folder itself when it
    already has that name). Switching it on also turns the diagnostics preference on: without it there are no records
    and nothing could be written. An empty folder switches it off and removes this installation's own file (nothing
    else in that folder is touched). Returns an ActionResult; detail['folder'] is the folder in use ('' when off)."""
    try:
        if not folder:
            old = auto_file(service); service.store.set_setting(_AUTO_KEY, "")
            removed = False
            if old and os.path.isfile(old):
                try: os.remove(old); removed = True
                except OSError: pass
            return ActionResult(Outcome.SAVED, "The automatic evidence file is off", detail={"folder": "", "removed": removed})
        folder = os.path.abspath(str(folder))
        if not os.path.isdir(folder): return ActionResult(Outcome.NOT_FOUND, "That folder does not exist")
        target = folder if os.path.basename(folder.rstrip("\\/")) == AUTO_FOLDER else os.path.join(folder, AUTO_FOLDER)
        try: os.makedirs(target, exist_ok=True)
        except OSError as e: return ActionResult(Outcome.STORAGE_UNAVAILABLE, f"The folder could not be created ({type(e).__name__})")
        service.store.set_setting(_AUTO_KEY, target); service.set_setting("diagnostics", True)
        return ActionResult(Outcome.SAVED, "The automatic evidence file is on", detail={"folder": target})
    except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The setting could not be saved")


def auto_write(service, *, blocked=False):
    """Write or refresh the automatic file, when that is switched on. Called by the app when it starts and closes.

    blocked: True in local-only mode - the purpose of this file is to leave the computer through a synced folder, so
    it is not written then. Returns an ActionResult: SAVED (written), ALREADY_SAVED (the file already says the same),
    DISABLED (off, paused, or the diagnostics preference is off), NOT_FOUND (the folder is not there right now, for
    example a drive that is not connected - it is NOT created again), STORAGE_UNAVAILABLE."""
    path = auto_file(service)
    if not path: return ActionResult(Outcome.DISABLED, "The automatic evidence file is off", detail={"on": False})
    if blocked: return ActionResult(Outcome.DISABLED, "Local-only mode: the automatic evidence file is paused", detail={"on": True, "paused": True})
    if not os.path.isdir(os.path.dirname(path)): return ActionResult(Outcome.NOT_FOUND, "The folder of the automatic evidence file is not there right now", detail={"on": True})
    bundle, stats = build_with_stats(service)
    if not stats["storage"]: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The learning database is not available")
    if not stats["consent"]: return ActionResult(Outcome.DISABLED, "Problem records are switched off; nothing is written", detail={"on": True, "consent": False})
    try:
        with open(path, encoding="utf-8") as f: old = json.load(f)
        if isinstance(old, dict) and old.get("items") == bundle["items"] and old.get("app_version") == bundle["app_version"] and old.get("installation") == bundle["installation"]:
            return ActionResult(Outcome.ALREADY_SAVED, "The evidence file is up to date", detail={"on": True, "items": len(bundle["items"]), "path": path})
    except (OSError, ValueError): pass
    try: _write(bundle, path)
    except OSError as e: return ActionResult(Outcome.STORAGE_UNAVAILABLE, f"The file could not be written ({type(e).__name__})")
    return ActionResult(Outcome.SAVED, "Evidence file written", detail={"on": True, "items": len(bundle["items"]), "withheld": stats["withheld"], "path": path})


def problems_of_item(item):
    out = []
    if not isinstance(item, dict) or set(item) != set(ITEM_KEYS): return ["keys"]
    if item["category"] not in CATEGORIES: out.append("category")
    if item["kind"] not in ITEM_KINDS: out.append("kind")
    if item["data_family"] not in M.FAMILIES: out.append("data_family")
    if item["signature"] and not sg.is_shareable_signature(item["signature"]): out.append("signature")
    if not isinstance(item["count"], int) or item["count"] < 1: out.append("count")
    try: M.assert_inert({"before": item["before"], "after": item["after"], "error_class": item["error_class"], "template_id": item["template_id"]})
    except M.RecipeError as e: out.append(e.code)
    return out


def validate_bundle(bundle):
    """Problems of a bundle against the schema ([] = valid): for the consumer of the file and for tests."""
    if not isinstance(bundle, dict): return ["not_an_object"]
    out = []
    if set(bundle) != {"schema", "generated_at", "app_version", "installation", "items"}: out.append("keys")
    if bundle.get("schema") != M.EVIDENCE_SCHEMA: out.append("schema")
    if bundle.get("installation") and not M.is_uuid(bundle.get("installation")): out.append("installation")
    for n, item in enumerate(bundle.get("items") if isinstance(bundle.get("items"), list) else []):
        out += [f"items[{n}].{p}" for p in problems_of_item(item)]
    if privacy.scan_private(bundle): out.append("private_content")
    return out

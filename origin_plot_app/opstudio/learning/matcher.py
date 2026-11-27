"""matcher.py - which saved memories fit the file / graph in front of the user, and why.

Lookup order (the same for every data family):

  1. candidates of a permitted scope (and, for preferences, of the same data family)
  2. mandatory constraints: the columns the recipe uses exist, units do not conflict, the data family has no hard
     incompatibility with those columns, the template the memory names is INSTALLED (opstudio.REGISTRY or one of the
     user's own templates) - a memory whose template is gone is not offered and is flagged 'needs revalidation'
  3. exact validated structural matches first; weaker ones only as visible suggestions (weak=True), never applied
     without the user
  4. the user's own explicit choices before shared ones that say something else
  5. equally valid candidates that disagree are ALL returned with conflict=True - nothing is picked by popularity
  6. every suggestion says in plain words why it matches

THE MATCH GRADE IS NOT A PROBABILITY. 'exact' / 'compatible' / 'weak' name which structural test passed:
    exact        the same structural signature (container, separators, header words, units, column order)
    compatible   every column the recipe uses is present under the same header word with no conflicting unit
                 (other columns, their order or the separators may differ) - or, for a shared record, the same
                 sanitised structure
    weak         the columns were found only by their structural meaning (role), under different header words
No number between 0 and 1 is produced anywhere in this module, and no embedding is used.

Standard library only; the installed templates are read lazily from the parent package.
"""
from dataclasses import dataclass, field

from . import models as M
from . import signatures as sg

GRADE_ORDER = {"exact": 0, "compatible": 1, "weak": 2}
_NOT_A_ROLE = ("unknown", "other", "index", "error")


# ------------------------------------------------------------------------------------------------ installed templates
def contract_version(template):
    """The compatibility version of an installed template: a digest of what a saved preference depends on - its id, the
    kind of data it takes and the names of its data roles. It changes when an update changes that contract."""
    return M.digest([getattr(template, "id", ""), getattr(template, "data_kind", ""), sorted((getattr(template, "roles", None) or {}).keys())], 12)


def installed_templates():
    """{template id: compatibility version} of the Analysis catalogue as installed now (built-in and the user's own).
    This is the only list a template preference can refer to: there is no second catalogue in the learning system."""
    out = {}
    try:
        from ..core import REGISTRY
        for tid, t in REGISTRY.items(): out[tid] = contract_version(t)
    except Exception: return out
    try:
        from .. import api
        for tid, u in api.user_templates().items(): out[tid] = "u." + out.get(u.get("base"), "")[:10]
    except Exception: pass
    return out


def template_version(template_id, templates=None):
    t = installed_templates() if templates is None else templates
    return t.get(template_id, "")


# ------------------------------------------------------------------------------------------------ mapping checks
def effective_units(context, units=None):
    """Per column: the declared unit of the mapping where given, else the unit the header declares."""
    base = list(context.units); units = list(units or [])
    return [(units[i] if i < len(units) and units[i] else (base[i] if i < len(base) else "")) for i in range(context.column_count)]


def check_family(family, context, roles, units=None):
    """('passed' | 'unverified' | 'failed', problems) - the hard prerequisites of a data family for the chosen X and Y
    columns (models.FAMILY_RULES). 'unverified' means the headers and units say nothing either way: the classification
    then rests on the user's confirmation alone. This is a technical exclusion test, not a scientific proof."""
    rule = M.FAMILY_RULES.get(family)
    if not rule: return "unverified", []
    eff = effective_units(context, units); problems = []; evidence = 0
    def col(i, axis):
        nonlocal evidence
        ok_roles, ok_dims = rule[axis]
        role = sg.classify_header(context.headers[i]) if i < len(context.headers) else "unknown"
        dim = sg.unit_dimension(eff[i]) if i < len(eff) else ""
        if role not in _NOT_A_ROLE:
            if role in ok_roles: evidence += 1
            else: problems.append(f"{axis}_role_incompatible")
        if dim:
            if dim in ok_dims: evidence += 1
            else: problems.append(f"{axis}_unit_incompatible")
    x = roles.get("x"); ys = roles.get("y") or []
    if isinstance(x, int) and x < context.column_count: col(x, "x")
    for y in ys:
        if isinstance(y, int) and y < context.column_count: col(y, "y")
    problems = sorted(set(problems))
    return ("failed" if problems else ("passed" if evidence else "unverified")), problems


def check_mapping(context, roles, units=None, family="unknown", numeric_ok=None):
    """The technical checks of a mapping against a context. roles are positions ({'x': 0, 'y': [1]}).
    Returns (checks, problems): checks = {'columns_exist', 'roles_distinct', 'numeric_values', 'units_consistent',
    'family_prerequisites'} ; problems = stable words. numeric_ok: per-column list, or a callable(position) -> bool;
    default: context.numeric_ok. A column whose numeric content was not checked FAILS the check - a mapping is not
    remembered on the assumption that numbers are there."""
    checks = {}; problems = []; n = context.column_count
    x = roles.get("x"); ys = list(roles.get("y") or [])
    used = ([x] if isinstance(x, int) else []) + [y for y in ys if isinstance(y, int)]
    others = [v for k, v in roles.items() if k not in ("x", "y")]
    flat = used + [i for v in others for i in (v if isinstance(v, list) else [v]) if isinstance(i, int)]
    if not isinstance(x, int): problems.append("x_column_missing")
    if not ys: problems.append("y_column_missing")
    exist = all(0 <= i < n for i in flat) and isinstance(x, int) and bool(ys)
    if any(not 0 <= i < n for i in flat): problems.append("column_out_of_range")
    checks["columns_exist"] = exist
    distinct = len(set(used)) == len(used)
    for a, b in (("obs", "calc"), ("obs", "diff"), ("calc", "diff")):
        if isinstance(roles.get(a), int) and roles.get(a) == roles.get(b): distinct = False
    if not distinct: problems.append("roles_not_distinct")
    checks["roles_distinct"] = distinct
    def num(i):
        if callable(numeric_ok):
            try: return bool(numeric_ok(i))
            except Exception: return None
        src = numeric_ok if isinstance(numeric_ok, (list, tuple)) else context.numeric_ok
        return src[i] if i < len(src) else None
    got = [num(i) for i in used if 0 <= i < n]
    if any(v is False for v in got): problems.append("no_numeric_values")
    elif any(v is None for v in got): problems.append("numeric_not_checked")
    checks["numeric_values"] = bool(got) and all(v is True for v in got)
    conflict = False
    declared = list(units or [])
    for i in flat:
        if 0 <= i < n and i < len(declared) and i < len(context.units) and sg.units_conflict(declared[i], context.units[i]): conflict = True
    if conflict: problems.append("units_conflict")
    checks["units_consistent"] = not conflict
    fam, fp = check_family(family, context, {"x": x, "y": ys}, units) if exist else ("unverified", [])
    checks["family_prerequisites"] = fam; problems += fp
    return checks, problems


def resolve_refs(recipe_roles, context, *, exact=False):
    """Recipe column references -> positions in THIS context. Returns (resolved, method, problems); method is the
    weakest way a column was found: 'position' (only for an exactly matching layout), 'header' or 'role'."""
    rank = {"position": 0, "header": 1, "role": 2}; method = "position"; problems = []; resolved = {}; heads = list(context.headers)
    def one(ref):
        nonlocal method
        if not isinstance(ref, dict): return None
        i = ref.get("i"); h = ref.get("h"); role = ref.get("role")
        if exact and isinstance(i, int) and 0 <= i < context.column_count: return i
        if h:
            hits = [k for k, x in enumerate(heads) if x == h]
            if len(hits) == 1:
                if rank["header"] > rank[method]: method = "header"
                return hits[0]
            role = role or sg.classify_header(h)
        if role and role not in _NOT_A_ROLE:
            hits = [k for k, x in enumerate(heads) if sg.classify_header(x) == role]
            if len(hits) > 1 and isinstance(i, int) and i in hits: hits = [i]
            if len(hits) == 1:
                method = "role"; return hits[0]
        return None
    for name, v in (recipe_roles or {}).items():
        if isinstance(v, list):
            got = [one(r) for r in v]
            if any(g is None for g in got) or not got: problems.append(f"{name}_column_missing")
            else: resolved[name] = got
        else:
            g = one(v)
            if g is None: problems.append(f"{name}_column_missing")
            else: resolved[name] = g
    return resolved, method, problems


# ------------------------------------------------------------------------------------------------ one memory against a context
@dataclass
class Match:
    grade: str = ""                                   # '' = not offered
    reasons: list = field(default_factory=list)       # stable words (why it matched, or why it did not)
    notes: list = field(default_factory=list)         # plain words for the user
    resolved: dict = field(default_factory=dict)
    needs_revalidation: bool = False
    explanation: str = ""


def scope_key(scope, context, target=None):
    """The key a scoped memory is bound to: the project for 'personal_project', the graph / panel for a style."""
    if target == "graph": return M.digest(["graph", context.graph_id], 24) if context.graph_id else ""
    if target == "panel": return M.digest(["panel", context.graph_id, context.panel_id or str(context.panel_index)], 24) if (context.graph_id or context.panel_id) else ""
    if scope == "personal_project": return M.digest(["project", context.project_id], 24) if context.project_id else ""
    return ""


def _mem_units(mem, ref):
    i = ref.get("i") if isinstance(ref, dict) else None
    units = (mem.get("recipe") or {}).get("units")
    if isinstance(units, list) and isinstance(i, int) and i < len(units) and isinstance(units[i], str) and units[i]: return units[i] if units[i] != "other" else ""
    cu = (mem.get("context") or {}).get("units") or []
    return cu[i] if isinstance(i, int) and i < len(cu) else ""


def _words(headers, idx):
    names = []
    for i in idx:
        if isinstance(i, int) and i < len(headers) and headers[i]: names.append(headers[i])
    return ", ".join(names[:4])


def evaluate(mem, context, templates=None):
    """Match one memory (store dict) against a context. Never raises; a memory that cannot be offered has grade ''."""
    m = Match(); kind = mem.get("kind"); recipe = mem.get("recipe") or {}; shared = mem.get("visibility", "personal") != "personal"
    templates = installed_templates() if templates is None else templates
    if not mem.get("enabled", True): m.reasons.append("disabled"); return m
    if shared and mem.get("status") != "approved": m.reasons.append("not_approved"); return m
    if kind == "legacy_lesson": m.reasons.append("not_a_suggestion"); return m
    # --- the template a memory names must be installed
    tids = [t for t in {mem.get("template_id") or "", recipe.get("template_id") or ""} if t]
    if kind == "workflow": tids += [s["params"]["template_id"] for s in recipe.get("steps", []) if s.get("op") == "draw_template" and s.get("params", {}).get("template_id")]
    for tid in tids:
        if tid not in templates:
            m.needs_revalidation = True; m.reasons.append("template_not_installed"); return m
    saved_v = mem.get("template_version") or recipe.get("template_version") or ""
    changed = bool(tids and saved_v and templates.get(mem.get("template_id") or recipe.get("template_id") or tids[0]) != saved_v)
    # --- scope
    scope = mem.get("scope") or "personal_format"
    if scope == "personal_project" and (not mem.get("scope_key") or mem.get("scope_key") != scope_key(scope, context)): m.reasons.append("other_project"); return m
    if scope == "personal_instrument" and (not mem.get("instrument") or mem.get("instrument") != context.instrument): m.reasons.append("other_instrument"); return m
    same_sig = bool(mem.get("signature")) and mem.get("signature") == context.signature
    same_share = bool(mem.get("share_signature")) and mem.get("share_signature") == context.share_signature
    fam = mem.get("data_family") or "unknown"

    if kind in ("import_mapping", "unit_mapping"):
        refs = recipe.get("roles") if kind == "import_mapping" else {"y": [e.get("col") for e in recipe.get("units", [])]}
        resolved, method, problems = resolve_refs(refs, context, exact=same_sig)
        if problems: m.reasons += problems; return m
        flat = []
        for name, v in refs.items():
            for ref, idx in zip(v if isinstance(v, list) else [v], resolved[name] if isinstance(resolved[name], list) else [resolved[name]]): flat.append((ref, idx))
        undeclared = False
        for n, (ref, idx) in enumerate(flat):
            mu = recipe["units"][n].get("unit", "") if kind == "unit_mapping" else _mem_units(mem, ref)
            cu = context.units[idx] if idx < len(context.units) else ""
            if mu == "other": mu = ""
            if sg.units_conflict(mu, cu): m.reasons.append("units_conflict"); return m
            if bool(mu) != bool(cu): undeclared = True
        if kind == "import_mapping":
            state, fp = check_family(fam, context, {"x": resolved.get("x"), "y": resolved.get("y") or []})
            if state == "failed": m.reasons += fp; return m
            m.resolved = {"data_family": fam, "roles": resolved}
        else:
            m.resolved = {"units": [{"column": idx, "unit": e.get("unit", "")} for e, (_r, idx) in zip(recipe["units"], flat)]}
        cols = _words(context.headers, [i for _r, i in flat])
        if same_sig and not shared:
            m.grade = "exact"; m.explanation = "Same column names, units, separators and column order as your saved export format."
        elif method in ("position", "header") and not shared:
            m.grade = "compatible"; m.explanation = f"The columns this uses ({cols or 'the same columns'}) are present under the same names with no conflicting unit; other parts of the file differ."
        elif shared and same_share:
            m.grade = "compatible"; m.explanation = "Same column meanings, units and separators as an approved shared format."
        else:
            m.grade = "weak"; m.explanation = f"Columns with the same meaning were found under other names ({cols or 'see the columns'}); check them before applying."
        if undeclared and m.grade != "exact": m.notes.append("A unit is declared on one side only; it was not compared.")
    elif kind == "classification":
        mh = [h for h in (mem.get("context") or {}).get("headers", []) if h]
        if same_sig and not shared:
            m.grade = "exact"; m.explanation = "Same column names, units, separators and column order as the file whose type you confirmed."
        elif mh and not shared and set(mh) <= set(context.headers) and not _unit_clash(mem, context):
            m.grade = "compatible"; m.explanation = "All columns of the file whose type you confirmed are present here under the same names."
        elif same_share:
            m.grade = "compatible" if shared else "weak"
            m.explanation = "Same column meanings and units as " + ("an approved shared format." if shared else "the file whose type you confirmed, under other column names.")
        else: m.reasons.append("structure_differs"); return m
        m.resolved = {"data_family": fam}
    elif kind == "template_preference":
        if fam == "unknown" and not same_sig: m.reasons.append("no_family"); return m
        if scope == "personal_format" and not shared:
            if not same_sig: m.reasons.append("other_format"); return m
            m.grade = "exact"; m.explanation = "You chose this template for files of exactly this format."
        elif fam == context.data_family and fam != "unknown":
            m.grade = "compatible"; m.explanation = "Chosen for this data family" + (" by an approved shared preference." if shared else " by you.")
        else: m.reasons.append("other_family"); return m
        m.resolved = {"template_id": recipe.get("template_id", "")}
    elif kind == "graph_style":
        tscope = (recipe.get("target") or {}).get("scope")
        if tscope in ("graph", "panel"):
            if shared or not mem.get("scope_key") or mem.get("scope_key") != scope_key(scope, context, tscope): m.reasons.append("other_" + tscope); return m
            m.grade = "exact"; m.explanation = f"The style you saved for this {tscope}."
        else:
            if fam == "unknown" or fam != context.data_family: m.reasons.append("other_family"); return m
            if mem.get("template_id") and context.template_id and mem["template_id"] != context.template_id: m.reasons.append("other_template"); return m
            m.grade = "compatible"; m.explanation = "A style saved for this data family" + (" (approved shared preference)." if shared else " by you.")
        m.resolved = {"style": recipe.get("style", {}), "target": recipe.get("target", {})}
    elif kind == "workflow":
        need = (recipe.get("requires") or {}).get("roles") or []
        have = {sg.classify_header(h) for h in context.headers}
        if any(r not in have for r in need): m.reasons.append("required_columns_missing"); return m
        if same_sig and not shared: m.grade = "exact"; m.explanation = "A workflow you saved for files of exactly this format."
        elif fam != "unknown" and fam == context.data_family: m.grade = "compatible"; m.explanation = "A workflow saved for this data family; the columns it needs are present."
        else: m.reasons.append("other_family"); return m
        m.resolved = {"steps": recipe.get("steps", [])}
    elif kind == "legacy_format":
        if not context.legacy_signature or context.legacy_signature != mem.get("signature"): m.reasons.append("other_layout"); return m
        m.grade = "compatible"; m.explanation = "The same file layout as a reading recipe learned by an earlier version of the app."
        m.notes.append("Imported from the earlier learned formats; it was not validated or confirmed in this version.")
        m.resolved = {"legacy_recipe": recipe.get("recipe", {})}
    else:
        m.reasons.append("unknown_kind"); return m
    if changed:
        m.needs_revalidation = True; m.notes.append("The template changed with an update since this was saved; check the result.")
        if m.grade == "exact": m.grade = "compatible"
    if mem.get("needs_revalidation"): m.needs_revalidation = True
    m.reasons.append({"exact": "same_signature", "compatible": "same_columns", "weak": "same_roles"}[m.grade])
    return m


def _unit_clash(mem, context):
    mc = mem.get("context") or {}
    for h, u in zip(mc.get("headers", []), mc.get("units", [])):
        if h in context.headers and sg.units_conflict(u, context.units[context.headers.index(h)]): return True
    return False


# ------------------------------------------------------------------------------------------------ all memories against a context
_SLOT = {"import_mapping": "mapping", "classification": "mapping", "legacy_format": "legacy", "unit_mapping": "units", "graph_style": "style"}


def _claim(kind, resolved):
    if kind == "import_mapping": return ("family", resolved.get("data_family")), ("roles", M.canonical_json(resolved.get("roles")))
    if kind == "classification": return (("family", resolved.get("data_family")),)
    return (("value", M.canonical_json(resolved)),)


def _disagree(a, b):
    da, db = dict(a), dict(b)
    return any(k in db and db[k] != v for k, v in da.items())


def find(memories, context, *, templates=None, auto_apply=False, kinds=None):
    """(suggestions, flagged): every memory that may be offered for this context as a plain dict (see
    models.Suggestion for the fields), best grade first, the user's own before shared ones; and the ids of memories
    that could not be offered because a template they name is not installed (to be flagged 'needs revalidation')."""
    templates = installed_templates() if templates is None else templates
    out = []; flagged = []
    for mem in memories:
        if kinds and mem.get("kind") not in kinds: continue
        mt = evaluate(mem, context, templates)
        if not mt.grade:
            if mt.needs_revalidation: flagged.append(mem["id"])
            continue
        val = mem.get("validation") or {}
        personal = mem.get("visibility", "personal") == "personal"
        out.append({"id": "sg_" + M.digest([mem["id"], mem.get("revision"), context.fingerprint()], 20), "memory_id": mem["id"], "revision": int(mem.get("revision") or 1),
                    "kind": mem["kind"], "grade": mt.grade, "explanation": mt.explanation, "weak": mt.grade == "weak", "conflict": False, "conflicts_with": (),
                    "auto_apply_ok": False, "data_family": mem.get("data_family") or "unknown", "scope": mem.get("scope") or "", "visibility": mem.get("visibility", "personal"),
                    "origin": mem.get("origin") or "", "template_id": mem.get("template_id") or (mem.get("recipe") or {}).get("template_id", ""),
                    "needs_revalidation": mt.needs_revalidation, "user_confirmed": bool(val.get("user_confirmed")) and personal and mem.get("origin") == "user",
                    "recipe": mem.get("recipe") or {}, "resolved": mt.resolved, "notes": tuple(mt.notes),
                    "_claim": _claim(mem["kind"], mt.resolved), "_slot": _SLOT.get(mem["kind"], ""), "_updated": mem.get("updated_at") or "",
                    "_validated": bool(val.get("structural_checks_passed"))})
    # order: grade, then the user's own explicit choices, then other origins; newest first. No popularity anywhere.
    out.sort(key=lambda s: s["_updated"], reverse=True)
    out.sort(key=lambda s: (GRADE_ORDER[s["grade"]], 0 if s["user_confirmed"] else (1 if s["visibility"] == "personal" else 2)))
    for slot in {s["_slot"] for s in out if s["_slot"] and s["_slot"] != "legacy"}:
        group = [s for s in out if s["_slot"] == slot]
        best = min(GRADE_ORDER[s["grade"]] for s in group)
        top = [s for s in group if GRADE_ORDER[s["grade"]] == best]
        leaders = [s for s in top if s["user_confirmed"]] or top
        for a in group:                 # compared with the leaders only: the user's own choice is not put in doubt by a weaker or a shared one
            against = [b for b in leaders if b is not a and _disagree(a["_claim"], b["_claim"])]
            if against:
                a["conflict"] = True; a["conflicts_with"] = tuple(b["id"] for b in against)
    for s in out:
        s["auto_apply_ok"] = bool(auto_apply and s["grade"] == "exact" and not s["conflict"] and not s["weak"] and s["user_confirmed"] and s["_validated"]
                                  and not s["needs_revalidation"] and s["kind"] in ("import_mapping", "classification", "unit_mapping"))
    for s in out:
        for k in ("_claim", "_slot", "_updated", "_validated"): s.pop(k)
    return out, flagged


def rank_templates(compatible_template_ids, memories, context, templates=None):
    """The given template ids in preference order - and ONLY the given ids: this function can move an id, it can never
    add one, and an id no memory knows keeps its place. The caller has already filtered the Analysis catalogue for what
    the data can fill (opstudio.api.recommend / detection.compatibility); a preference only ranks inside that list.
    Order: the user's choice for exactly this format, then the user's choice for the data family, then approved shared
    preferences; within a level the most recently confirmed first; everything else in the order it came in.
    Returns (ordered ids, {id: reason})."""
    ids = list(compatible_template_ids or [])
    templates = installed_templates() if templates is None else templates
    level = {}; why = {}
    prefs = sorted((m for m in memories if m.get("kind") == "template_preference"), key=lambda m: m.get("updated_at") or "", reverse=True)
    for n, mem in enumerate(prefs):
        tid = (mem.get("recipe") or {}).get("template_id")
        if tid not in ids: continue
        mt = evaluate(mem, context, templates)
        if not mt.grade: continue
        personal = mem.get("visibility", "personal") == "personal"
        lv = (0 if mt.grade == "exact" else 1) if personal else 2
        if tid not in level or (lv, n) < level[tid]:
            level[tid] = (lv, n); why[tid] = mt.explanation
    order = sorted(range(len(ids)), key=lambda i: (level.get(ids[i], (9, 0)), i))
    return [ids[i] for i in order], why

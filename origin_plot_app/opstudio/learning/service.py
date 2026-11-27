"""service.py - LearningService: the ONE place the app records what the user confirmed and asks what it remembers.

The pages of the app (Start here, Workbook, graph editors, Assistant) call this service; none of them writes a memory
file of its own. The service never touches the user's data, graphs or projects: it is told what happened (as allowlisted
descriptions), keeps what may be kept, and answers with explicit outcomes.

Lifecycle of a correction:

    stage_change(context, before, after, origin=..., operation_id=...)   in process memory only
        -> validate(candidate, current_context, rendered=True)           technical checks against what is displayed NOW
        -> confirm(candidate.id, remember=..., scope=..., confirmation_token=...)
        -> one event + one memory revision, committed together            (or nothing at all)

Rules the code below enforces:
  * only origin='user' can become a confirmed correction; 'system', 'memory' and 'migration' candidates are refused
  * opening, refreshing or restoring records nothing (nothing is recorded unless confirm() is called for a user candidate)
  * applying a memory (apply_suggestion) records at most one 'accepted' feedback row per operation id - never a
    confirmation: 'times applied' and 'user confirmations' are separate counters
  * a confirmation token is bound to the file / sheet / source revision / graph / panel and to the staged values; if any
    of them changed the outcome is 'stale_candidate'
  * a database that cannot be written never stops the user's work: the outcome is 'storage_unavailable' with
    applied=True ("Mapping applied; could not remember it"), and 'saved' is reported only after the commit succeeded
  * failures (record_failure) go to a separate diagnostics table, only while the diagnostics preference is on, and are
    never turned into a memory

Importable without Qt, pandas or Origin.
"""
import copy, json, os, re, threading, time
from collections import OrderedDict

from . import matcher, models as M, privacy, signatures as sg
from .models import Outcome, Context, Candidate, ValidationResult, RecordResult, ActionResult, Suggestion, ApplyResult
from .store import Store, StorageUnavailable

SETTING_DEFAULTS = {"personal_learning": True,      # remember what the user confirms, and offer it again (this computer only)
                    "diagnostics": False,           # keep sanitised failure records for the evidence export
                    "sharing": False,               # allow contributions to be queued and synchronised at all
                    "sharing_scope": "lab",         # default scope offered when sharing: 'lab' | 'community'
                    "auto_apply": False,            # apply an exact, validated, own mapping without the Apply click
                    "lab_id": ""}
_RELEVANT = {"classification_corrected": ("data_family", "confirmed"),
             "column_mapping_corrected": ("data_family", "roles", "units", "read"),
             "unit_mapping_confirmed": ("units",),
             "template_preference_saved": ("template_id", "template_version", "data_family"),
             "graph_style_saved": ("style", "target", "include_limits"),
             "workflow_saved": ("workflow", "roles")}
MESSAGES = {
    ("mapping", Outcome.SAVED): "Mapping remembered", ("template", Outcome.SAVED): "Template preference saved",
    ("style", Outcome.SAVED): "Style saved", ("workflow", Outcome.SAVED): "Workflow saved",
    ("mapping", Outcome.STORAGE_UNAVAILABLE): "Mapping applied; could not remember it",
    ("template", Outcome.STORAGE_UNAVAILABLE): "Template used; could not remember the preference",
    ("style", Outcome.STORAGE_UNAVAILABLE): "Style applied; could not save it", ("workflow", Outcome.STORAGE_UNAVAILABLE): "Workflow finished; could not save it",
}
_GENERIC = {Outcome.ALREADY_SAVED: "Already remembered", Outcome.VALIDATION_FAILED: "Not remembered: the checks did not pass",
            Outcome.STALE: "The preview changed; confirm the result that is shown now", Outcome.NOT_REMEMBERED: "Applied without remembering",
            Outcome.DISABLED: "Applied; learning is switched off", Outcome.NOT_FOUND: "Not found", Outcome.NOT_PERMITTED: "Only a change you made yourself can be remembered",
            Outcome.STORAGE_UNAVAILABLE: "Applied; could not remember it", Outcome.SAVED: "Saved"}
_PROBLEM_TEXT = {
    "x_column_missing": "no X column is chosen", "y_column_missing": "no Y column is chosen", "column_out_of_range": "a chosen column does not exist in this file",
    "roles_not_distinct": "the same column is used for two roles", "no_numeric_values": "a chosen column has no usable numbers",
    "numeric_not_checked": "the numbers of a chosen column were not checked", "units_conflict": "a declared unit contradicts the unit in the column header",
    "x_role_incompatible": "the X column is named as a different quantity than this measurement type needs",
    "y_role_incompatible": "a Y column is named as a different quantity than this measurement type needs",
    "x_unit_incompatible": "the unit of the X column does not fit this measurement type", "y_unit_incompatible": "the unit of a Y column does not fit this measurement type",
    "preview_not_rendered": "the preview of this change has not finished", "no_family": "no measurement type is chosen",
    "template_not_installed": "this template is not installed", "empty_style": "there is no style setting to save",
    "target_scope_missing": "say whether the style is for this graph, this panel or the data family", "target_not_identified": "the graph or panel is not identified",
    "no_units": "no unit is declared", "unsupported_operation": "the workflow contains a step that cannot be saved", "no_change": "nothing changed",
    "origin_not_user": "the change was not made by you", "nothing_allowed": "nothing of this change can be remembered", "stale_candidate": "the displayed file or mapping changed",
    "unknown_scope": "unknown scope", "no_workflow": "there is no workflow to save",
}


def _app_version():
    v = os.environ.get("OPS_APP_VERSION")
    if v: return v
    try:
        here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(here, "smart_plots.py"), encoding="utf-8", errors="replace") as f:
            m = re.search(r'^VERSION\s*=\s*"([0-9][0-9A-Za-z.\-+]{0,20})"', f.read(200000), re.M)
        return m.group(1) if m else ""
    except Exception: return ""


class _Staged:
    __slots__ = ("candidate", "context", "state", "token", "validation", "problems", "include_limits", "group")

    def __init__(self, candidate, context, include_limits, group):
        self.candidate = candidate; self.context = context; self.state = "staged"; self.token = ""; self.validation = {}; self.problems = ()
        self.include_limits = include_limits; self.group = group


def dedup_key(kind, scope, key, signature, family, instrument, recipe):
    """The identity of a reusable memory: a second confirmation of the same thing revises / confirms the memory instead of
    adding another row. Derived from stored fields only, so an export imported again finds its own memory."""
    if kind in ("import_mapping", "classification", "unit_mapping"): parts = [kind, scope, key, signature, instrument if scope == "personal_instrument" else ""]
    elif kind == "template_preference": parts = [kind, scope, key, signature if scope == "personal_format" else family, instrument if scope == "personal_instrument" else "", recipe.get("template_id", "")]
    elif kind == "graph_style":
        ts = (recipe.get("target") or {}).get("scope", "")
        parts = [kind, ts, key if ts in ("graph", "panel") else family, recipe.get("template_id", "") if ts == "family" else ""]
    elif kind == "workflow": parts = [kind, scope, key, signature if scope == "personal_format" else family, M.digest(recipe.get("steps", []), 16)]
    elif kind == "legacy_format": parts = [kind, signature]
    elif kind == "legacy_lesson": parts = [kind, re.sub(r"\s+", " ", str(recipe.get("text", ""))).strip().lower()]
    else: parts = [kind, signature, M.digest(recipe, 16)]
    return M.digest(parts, 40)


class LearningService:
    """See the module text. One instance per application; safe to call from several threads (each thread gets its own
    database connection; the in-memory staging area is guarded by a lock)."""

    def __init__(self, db_path=None, *, app_version=None, clock=None, templates=None):
        """db_path: the database file; default <private folder>/learning/learning.sqlite3 (or $OPS_LEARNING_DIR/...).
        clock: callable returning seconds since 1970 (tests). templates: {id: version} or a callable returning that -
        default: the installed Analysis catalogue (matcher.installed_templates)."""
        self.clock = clock or time.time
        self.app_version = str(app_version) if app_version else _app_version()
        self.store = Store(db_path, app_version=self.app_version, clock=self.clock)
        self._templates = templates
        self._lock = threading.RLock()
        self._candidates = OrderedDict(); self._by_target = {}; self._confirmed = OrderedDict(); self._suggestions = OrderedDict()
        self._secret = os.urandom(16).hex()

    # -------------------------------------------------------------------------------------------- small things
    @property
    def db_path(self): return self.store.path

    def new_operation_id(self):
        """A fresh operation id. Create ONE at the start of a deliberate user action and keep it through preview,
        validation and confirmation: a repeated signal with the same id cannot be recorded twice."""
        return M.new_id()

    def templates(self):
        t = self._templates
        if t is None: return matcher.installed_templates()
        return dict(t() if callable(t) else t)

    def available(self):
        """True when the database can be opened right now."""
        return self.store.available()

    def close(self): self.store.close_all()

    def get_settings(self):
        """The preferences as a dict (see SETTING_DEFAULTS). The defaults when the database cannot be read."""
        out = dict(SETTING_DEFAULTS)
        try:
            for k in out: out[k] = self.store.setting("pref:" + k, out[k])
        except StorageUnavailable: pass
        return out

    def set_setting(self, name, value):
        """Change one preference. 'personal_learning', 'diagnostics', 'sharing', 'auto_apply': bool; 'sharing_scope':
        'lab' | 'community'; 'lab_id': a uuid or ''. Turning sharing off stops new uploads; the result's detail says
        how many contributions are still queued (cancel_queued_contributions() removes them)."""
        if name not in SETTING_DEFAULTS: return ActionResult(Outcome.NOT_FOUND, "unknown preference")
        if name in ("personal_learning", "diagnostics", "sharing", "auto_apply"):
            if not isinstance(value, bool): return ActionResult(Outcome.VALIDATION_FAILED, "on or off")
        elif name == "sharing_scope":
            if value not in M.SHARE_SCOPES: return ActionResult(Outcome.VALIDATION_FAILED, "lab or community")
        elif name == "lab_id":
            if value and not M.is_uuid(value): return ActionResult(Outcome.VALIDATION_FAILED, "not a lab id")
            value = str(value or "")
        try:
            if self.store.setting("pref:" + name, SETTING_DEFAULTS[name]) == value: return ActionResult(Outcome.ALREADY_SAVED)
            self.store.set_setting("pref:" + name, value)
            detail = {"queued_contributions": len(self.store.outbox(states=("queued", "failed")))} if name == "sharing" and value is False else {}
            return ActionResult(Outcome.SAVED, detail=detail)
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The preference could not be saved")

    def installation_id(self):
        """A random id of this installation, created once and kept locally. It is not derived from the computer, the
        account or anything else about the user. '' when the database is unavailable."""
        try:
            v = self.store.setting("installation", "")
            if not M.is_uuid(v):
                v = M.new_id(); self.store.set_setting("installation", v)
            return v
        except StorageUnavailable: return ""

    # -------------------------------------------------------------------------------------------- stage
    @staticmethod
    def _infer(changes):
        keys = set(changes)
        if any(k.startswith(("roles.", "read.")) for k in keys): return "column_mapping_corrected"
        if keys & {"data_family", "confirmed"}: return "classification_corrected"
        if "units" in keys: return "unit_mapping_confirmed"
        if "template_id" in keys: return "template_preference_saved"
        if keys & {"style", "target", "include_limits"}: return "graph_style_saved"
        if "workflow" in keys: return "workflow_saved"
        return ""

    @staticmethod
    def _relevant(snapshot, event_type):
        return {k: copy.deepcopy(v) for k, v in (snapshot or {}).items() if k in _RELEVANT.get(event_type, ())}

    def stage_change(self, context, before, after, *, origin, operation_id, event_type=None, include_limits=False):
        """Stage what the user changed. Nothing is written. Returns a Candidate.

        context   Context or raw dict (models.Context.build): what is displayed - structure plus the stable ids of
                  project / file / sheet / dataset / graph / panel and the source revision
        before, after   raw descriptions (privacy.local_snapshot lists the keys that are read; everything else, such
                  as cell values, titles, names and paths, is ignored)
        origin    'user' for a deliberate action of the user; 'system' (refresh, restore, programmatic selection),
                  'memory' (a learned recipe was applied) and 'migration' give a candidate that can never be learned from
        operation_id   the id of the user's operation (new_operation_id())
        event_type     optional: say which event this is when a change touches several things - e.g.
                  'classification_corrected' for "Confirm type", which then records the type ONLY and asserts nothing
                  about the columns. Default: derived from what changed.
        include_limits True only when the user explicitly chose to keep numerical axis limits in a saved style

        A new candidate for the same target (dataset, or graph/panel) and the same kind of change supersedes the
        earlier one; a superseded, discarded or unknown candidate confirms as 'stale_candidate'."""
        ctx = Context.build(context)
        origin = origin if origin in M.ORIGINS else "system"
        b = privacy.local_snapshot(before, ctx, include_limits=include_limits); a = privacy.local_snapshot(after, ctx, include_limits=include_limits)
        changes = privacy.diff(b, a)
        et = event_type if event_type in M.EVENT_KIND else self._infer(changes)
        if et:
            keep = _RELEVANT[et]
            relevant = {k: v for k, v in changes.items() if k.split(".", 1)[0] in keep}
        else: relevant = {}
        group = M.EVENT_GROUP.get(et, "mapping")
        learnable, reason = True, ""
        if origin != "user": learnable, reason = False, "origin_not_user"
        elif not relevant: learnable, reason = False, ("no_change" if (b or a) or not (before or after) else "nothing_allowed")
        cand = Candidate(id=M.new_id(), operation_id=str(operation_id or M.new_id())[:80], origin=origin, event_type=et or "", kind=M.EVENT_KIND.get(et, ""),
                         target_id=ctx.target_id(group), learnable=learnable, reason=reason, changes=copy.deepcopy(relevant),
                         before=self._relevant(b, et) if et else b, after=self._relevant(a, et) if et else a, fingerprint=ctx.fingerprint())
        st = _Staged(cand, ctx, bool(include_limits), group)
        with self._lock:
            if origin == "user":                                   # a system refresh never throws the user's staged change away
                old = self._by_target.get((cand.target_id, group))
                if old: self._candidates.pop(old, None)
                self._by_target[(cand.target_id, group)] = cand.id
            self._candidates[cand.id] = st
            while len(self._candidates) > 256: self._candidates.popitem(last=False)
        return cand

    def discard(self, candidate_id):
        """Cancel a staged candidate (the page was closed, the dialog cancelled). Nothing was stored, nothing is."""
        cid = getattr(candidate_id, "id", candidate_id)
        with self._lock:
            st = self._candidates.pop(cid, None)
            if st and self._by_target.get((st.candidate.target_id, st.group)) == cid: self._by_target.pop((st.candidate.target_id, st.group), None)
        return st is not None

    def pending(self, target_id=None):
        """The staged candidates (optionally of one target) - for a page that wants to show 'unsaved correction'."""
        with self._lock: return [s.candidate for s in self._candidates.values() if target_id in (None, s.candidate.target_id)]

    # -------------------------------------------------------------------------------------------- validate
    def validate(self, candidate, current_context, *, rendered=None, current=None, numeric_ok=None):
        """Check a candidate against what is displayed NOW. Call it when the preview of the change has finished.

        current_context  the context as it is at this moment. A different file, sheet, source revision, graph or panel
                         than at staging time makes the candidate stale (it is discarded).
        rendered         True when the preview / graph / workflow of exactly this change finished successfully
        current          optional: the snapshot that is displayed now; if it differs from the staged one the candidate
                         is stale (the mapping changed while the preview was rendering)
        numeric_ok       optional per-column list or callable(position) -> bool saying that usable numbers exist;
                         default: current_context.numeric_ok. The numbers themselves are never passed in.

        Returns a ValidationResult; its token is what confirm() needs. A passed validation is a TECHNICAL statement
        (columns exist, roles distinct, numbers present, no unit contradiction, no hard incompatibility with the data
        family). It does not say the interpretation is scientifically right - that is the user's confirmation."""
        cid = getattr(candidate, "id", candidate)
        with self._lock: st = self._candidates.get(cid)
        if st is None: return ValidationResult(False, stale=True, problems=("stale_candidate",), messages=(_PROBLEM_TEXT["stale_candidate"],))
        ctx = Context.build(current_context); cand = st.candidate
        stale = ctx.fingerprint() != cand.fingerprint
        if not stale and current is not None:
            cur = self._relevant(privacy.local_snapshot(current, ctx, include_limits=st.include_limits), cand.event_type)
            stale = cur != cand.after
        if stale:
            self.discard(cid)
            return ValidationResult(False, stale=True, problems=("stale_candidate",), messages=(_PROBLEM_TEXT["stale_candidate"],))
        if not cand.learnable:
            return ValidationResult(False, problems=(cand.reason,), messages=(_PROBLEM_TEXT.get(cand.reason, cand.reason),))
        checks, problems = self._checks(cand, ctx, numeric_ok)
        need_render = cand.event_type in ("column_mapping_corrected", "template_preference_saved", "graph_style_saved", "workflow_saved")
        checks["preview_rendered"] = rendered is True
        checks["structural_checks_passed"] = not problems
        checks["user_confirmed"] = False
        pending = need_render and rendered is not True
        all_problems = tuple(problems) + (("preview_not_rendered",) if pending else ())
        ok = not all_problems
        with self._lock:
            st.validation = dict(checks); st.problems = all_problems
            st.state = "validated" if ok else ("invalid" if problems else "staged")
            st.token = M.digest([self._secret, cid, ctx.fingerprint(), cand.after, cand.event_type]) if ok else ""
            token = st.token
        return ValidationResult(ok, token=token, checks=checks, problems=all_problems, messages=tuple(_PROBLEM_TEXT.get(p, p) for p in all_problems))

    def _checks(self, cand, ctx, numeric_ok):
        et = cand.event_type; a = cand.after; checks = {}; problems = []
        fam = a.get("data_family") or ctx.data_family
        if et == "column_mapping_corrected":
            checks, problems = matcher.check_mapping(ctx, a.get("roles") or {}, a.get("units"), fam, numeric_ok)
        elif et == "classification_corrected":
            checks["family_known"] = fam != "unknown"
            if fam == "unknown": problems.append("no_family")
            checks["family_prerequisites"] = "unverified"            # the columns are NOT part of a type confirmation
        elif et == "unit_mapping_confirmed":
            units = list(a.get("units") or []); before = list(cand.before.get("units") or [])
            changed = [i for i, u in enumerate(units) if u and (i >= len(before) or before[i] != u)]
            checks["units_declared"] = bool(changed)
            if not changed: problems.append("no_units")
            clash = any(i < len(ctx.units) and sg.units_conflict(units[i], ctx.units[i]) for i in changed)
            checks["units_consistent"] = not clash
            if clash: problems.append("units_conflict")
            if any(i >= ctx.column_count for i in changed): problems.append("column_out_of_range")
        elif et == "template_preference_saved":
            tid = a.get("template_id") or ""
            checks["template_installed"] = tid in self.templates()
            if not checks["template_installed"]: problems.append("template_not_installed")
        elif et == "graph_style_saved":
            target = a.get("target") or {}; ts = target.get("scope")
            checks["style_present"] = bool(a.get("style")); checks["target_scope_declared"] = ts in M.TARGET_SCOPES
            if not a.get("style"): problems.append("empty_style")
            if ts not in M.TARGET_SCOPES: problems.append("target_scope_missing")
            elif ts in ("graph", "panel") and not matcher.scope_key("", ctx, ts): problems.append("target_not_identified")
            elif ts == "family" and fam == "unknown": problems.append("no_family")
        elif et == "workflow_saved":
            steps = (a.get("workflow") or {}).get("steps") or []
            checks["operations_supported"] = bool(steps)
            if not steps: problems.append("no_workflow")
            installed = self.templates()
            missing = [s["params"].get("template_id") for s in steps if s["op"] == "draw_template" and s["params"].get("template_id") not in installed]
            checks["templates_installed"] = not missing
            if missing: problems.append("template_not_installed")
        return checks, problems

    # -------------------------------------------------------------------------------------------- confirm
    def _result(self, st, outcome, **kw):
        group = st.group if st else "mapping"
        msg = kw.pop("message", None) or MESSAGES.get((group, outcome)) or _GENERIC.get(outcome, "")
        return RecordResult(outcome, message=msg, candidate_id=st.candidate.id if st else kw.pop("candidate_id", ""), **kw)

    def confirm(self, candidate_id, *, remember, scope=None, confirmation_token, current_context=None):
        """The user confirmed the displayed result.

        remember            False: the change is applied, nothing reusable is stored ('applied_without_remembering')
        scope               where the memory applies: 'personal_format' (this export format - default),
                            'personal_instrument', 'personal_family', 'personal_project'
        confirmation_token  the token of the last successful validate() of this candidate
        current_context     optional last check: the context displayed at the moment of the click

        Outcomes: 'saved' (one event and one memory revision were committed together), 'already_saved' (this operation
        was recorded before - a double click adds nothing), 'applied_without_remembering', 'disabled' (personal
        learning is off), 'storage_unavailable' (applied=True: the mapping stands, the memory was not written),
        'validation_failed', 'stale_candidate', 'not_permitted' (the candidate did not come from the user)."""
        cid = getattr(candidate_id, "id", candidate_id)
        with self._lock:
            prev = self._confirmed.get(cid); st = self._candidates.get(cid)
        if prev is not None:
            if prev.outcome == Outcome.SAVED: return RecordResult(Outcome.ALREADY_SAVED, applied=True, message=_GENERIC[Outcome.ALREADY_SAVED], memory_id=prev.memory_id,
                                                                  revision=prev.revision, event_id=prev.event_id, candidate_id=cid, effect=prev.effect)
            return prev
        if st is None: return RecordResult(Outcome.STALE, message=_GENERIC[Outcome.STALE], candidate_id=cid)
        cand = st.candidate
        if cand.origin != "user": return self._result(st, Outcome.NOT_PERMITTED, problems=("origin_not_user",))
        if not cand.learnable:
            if cand.reason == "no_change":
                res = self._result(st, Outcome.NOT_REMEMBERED, applied=True, message="Nothing changed, so there is nothing to remember", problems=("no_change",))
                self._finish(cid, res); return res
            return self._result(st, Outcome.VALIDATION_FAILED, problems=(cand.reason,))
        if st.state != "validated": return self._result(st, Outcome.VALIDATION_FAILED, problems=st.problems or ("not_validated",))
        if not confirmation_token or confirmation_token != st.token: return self._result(st, Outcome.STALE)
        if current_context is not None and Context.build(current_context).fingerprint() != cand.fingerprint:
            self.discard(cid); return self._result(st, Outcome.STALE)
        # from here on the user's change is confirmed and stays applied, whatever happens to the memory
        if not remember:
            res = self._result(st, Outcome.NOT_REMEMBERED, applied=True)
            self._note_unremembered(st)
            self._finish(cid, res); return res
        if not self.get_settings()["personal_learning"]:
            res = self._result(st, Outcome.DISABLED, applied=True); self._finish(cid, res); return res
        sc = M.normalise_scope(scope)
        if sc is None: return self._result(st, Outcome.VALIDATION_FAILED, applied=True, problems=("unknown_scope",))
        try: ev, mem = self._build(st, sc)
        except M.RecipeError as e: return self._result(st, Outcome.VALIDATION_FAILED, applied=True, problems=(e.code,))
        try: r = self.store.record_confirmation(ev, mem)
        except StorageUnavailable:
            return self._result(st, Outcome.STORAGE_UNAVAILABLE, applied=True)            # the candidate stays: the user may try again
        res = self._result(st, r["outcome"], applied=True, memory_id=r["memory_id"], revision=r["revision"], event_id=r["event_id"], effect=r["effect"])
        self._finish(cid, res)
        return res

    def _finish(self, cid, result):
        with self._lock:
            st = self._candidates.pop(cid, None)
            if st and self._by_target.get((st.candidate.target_id, st.group)) == cid: self._by_target.pop((st.candidate.target_id, st.group), None)
            self._confirmed[cid] = result
            while len(self._confirmed) > 256: self._confirmed.popitem(last=False)

    def _note_unremembered(self, st):
        """A correction the user confirmed WITHOUT remembering: nothing reusable is kept. Only while the separate
        diagnostics preference is on, one sanitised row notes that this format needed a correction."""
        try:
            if not self.get_settings()["diagnostics"]: return
            c = st.candidate; ctx = st.context
            b, _ = privacy.shareable_snapshot(c.before, ctx.stored()); a, review = privacy.shareable_snapshot(c.after, ctx.stored())
            self.store.add_diagnostic({"operation_id": c.operation_id, "event_type": c.event_type, "target_id": c.target_id, "error_class": "not_remembered",
                                       "data_family": c.after.get("data_family") or ctx.data_family, "signature": ctx.share_signature, "template_id": c.after.get("template_id") or ctx.template_id,
                                       "detail": {"before": b, "after": a, "needs_review": review}})
        except StorageUnavailable: pass

    def _ref(self, ctx, i):
        h = ctx.headers[i] if i < len(ctx.headers) else ""
        return {"h": h, "i": i} if h else {"i": i}

    def _build(self, st, scope):
        """(event, memory) for a validated user candidate. Raises RecipeError when the recipe does not pass the schema."""
        c = st.candidate; ctx = st.context; a = c.after; et = c.event_type; kind = c.kind
        fam = a.get("data_family") or ctx.data_family
        key = matcher.scope_key(scope, ctx)
        if scope == "personal_project" and not key: raise M.RecipeError("project_not_identified", "scope")
        if scope == "personal_instrument" and not ctx.instrument: raise M.RecipeError("instrument_not_identified", "scope")
        tid, tver = "", ""
        if kind == "import_mapping":
            roles = {k: ([self._ref(ctx, i) for i in v] if isinstance(v, list) else self._ref(ctx, v)) for k, v in (a.get("roles") or {}).items()}
            read = {"delimiter": ctx.delimiter, "decimal": ctx.decimal, "header_row": ctx.header_row, "container": ctx.container}
            if ctx.encoding: read["encoding"] = ctx.encoding
            read.update(a.get("read") or {})
            recipe = {"data_family": fam, "roles": roles, "units": matcher.effective_units(ctx, a.get("units")), "read": read}
        elif kind == "classification":
            recipe = {"data_family": fam}
            if ctx.instrument: recipe["instrument"] = ctx.instrument
        elif kind == "unit_mapping":
            units = list(a.get("units") or []); before = list(c.before.get("units") or [])
            recipe = {"units": [{"col": self._ref(ctx, i), "unit": u} for i, u in enumerate(units) if u and (i >= len(before) or before[i] != u)]}
            if fam != "unknown": recipe["data_family"] = fam
        elif kind == "template_preference":
            tid = a.get("template_id") or ""; tver = self.templates().get(tid, "")
            if fam == "unknown" and scope != "personal_format": raise M.RecipeError("no_family", "data_family")
            recipe = {"template_id": tid, "template_version": tver, "data_family": fam}
        elif kind == "graph_style":
            ts = (a.get("target") or {}).get("scope")
            recipe = {"style": a.get("style") or {}, "target": {"scope": ts, "panel_index": ctx.panel_index if ts == "panel" else -1}}
            if fam != "unknown": recipe["data_family"] = fam
            if ctx.template_id and ctx.template_id in self.templates():
                tid = ctx.template_id; tver = self.templates().get(tid, ""); recipe["template_id"] = tid
            if a.get("include_limits"): recipe["include_limits"] = True
            key = matcher.scope_key(scope, ctx, ts) if ts in ("graph", "panel") else key
        elif kind == "workflow":
            used = privacy._role_axes(a.get("roles") or {})
            need = sorted({sg.classify_header(ctx.headers[i]) for i in used if i < len(ctx.headers)} - {"unknown", "other"})
            recipe = {"steps": (a.get("workflow") or {}).get("steps") or [], "requires": {"data_family": fam, "roles": need}}
            if fam != "unknown": recipe["data_family"] = fam
        else: raise M.RecipeError("unknown_kind", "kind")
        recipe = M.validate_recipe(kind, recipe)
        validation = dict(st.validation); validation["structural_checks_passed"] = True; validation["user_confirmed"] = True
        mem = {"kind": kind, "signature": ctx.signature, "signature_version": ctx.signature_version, "share_signature": ctx.share_signature, "data_family": fam,
               "instrument": ctx.instrument, "scope": scope, "scope_key": key, "origin": "user", "recipe": recipe, "context": ctx.stored(),
               "constraints": {"column_count": ctx.column_count, "template_id": tid, "template_version": tver, "signature_version": ctx.signature_version},
               "validation": validation, "provenance": {"origin": "user", "event_type": et, "app_version": self.app_version},
               "template_id": tid, "template_version": tver, "app_version": self.app_version,
               "dedup_key": dedup_key(kind, scope, key, ctx.signature, fam, ctx.instrument, recipe)}
        ev = {"operation_id": c.operation_id, "event_type": et, "target_id": c.target_id, "origin": "user", "context": ctx.stored(), "before": c.before, "after": c.after,
              "validation": validation, "remember": True, "scope": scope}
        return ev, mem

    def undo_saving(self, record_result):
        """Take back what a confirm() stored - the MEMORY, not the user's mapping, graph or workbook (those have their own
        undo). A memory the confirmation created is removed; a revision it made is rolled back; a repeated confirmation
        is un-counted. Accepts the RecordResult or its event id."""
        eid = getattr(record_result, "event_id", record_result)
        if not eid: return ActionResult(Outcome.NOT_FOUND, "nothing was saved by this action")
        try: outcome, mid = self.store.undo_saving(eid)
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "Saving could not be undone")
        if outcome == Outcome.SAVED:
            with self._lock:
                for cid, r in list(self._confirmed.items()):
                    if r.event_id == eid: self._confirmed.pop(cid, None)
        text = {Outcome.SAVED: "Saving undone", Outcome.NOT_PERMITTED: "This memory was changed again since; edit or forget it in Learning history"}.get(outcome, _GENERIC.get(outcome, ""))
        return ActionResult(outcome, text, memory_id=mid)

    # -------------------------------------------------------------------------------------------- suggestions
    def find_suggestions(self, current_context, *, kinds=None):
        """The saved memories that fit the current context, best match first (see matcher). [] when personal learning
        is off or the database is unavailable. Nothing is applied and nothing is recorded by asking."""
        ctx = Context.build(current_context)
        try:
            s = self.get_settings()
            if not s["personal_learning"]: return []
            templates = self.templates()
            found, flagged = matcher.find(self.store.memories(enabled=True), ctx, templates=templates, auto_apply=s["auto_apply"], kinds=kinds)
            for mid in flagged:
                try: self.store.flag_revalidation(mid, True)
                except StorageUnavailable: pass
        except StorageUnavailable: return []
        out = []
        with self._lock:
            for d in found:
                self._suggestions[d["id"]] = (d["memory_id"], d["revision"], ctx.fingerprint())
                out.append(Suggestion(**copy.deepcopy(d)))
            while len(self._suggestions) > 2048: self._suggestions.popitem(last=False)
        return out

    def apply_suggestion(self, suggestion_id, current_context, *, operation_id, numeric_ok=None):
        """The user chose Apply (or auto-apply is on): REVALIDATE the memory against the current file, and only then
        hand its recipe back. The service changes nothing in the user's data; the caller applies `resolved`.

        Records at most one 'accepted' feedback row for this operation id (a replay adds nothing). It is never a
        confirmation of the memory's correctness and never a vote: user_confirmations stays as it was.

        Outcomes: 'saved' / 'already_saved' (applied=True), 'storage_unavailable' (applied=True, the use was not
        counted), 'validation_failed' (this file does not fit after all - nothing applied, the memory is untouched),
        'stale_candidate' (the suggestion belongs to another file/sheet/revision or is unknown: ask again),
        'not_found', 'disabled'."""
        sid = getattr(suggestion_id, "id", suggestion_id)
        with self._lock: ref = self._suggestions.get(sid)
        if ref is None: return ApplyResult(Outcome.STALE, message="Ask for suggestions again for the file that is open now")
        mid, rev, fp = ref
        ctx = Context.build(current_context)
        if ctx.fingerprint() != fp: return ApplyResult(Outcome.STALE, memory_id=mid, message="The file or sheet changed; ask for suggestions again")
        try: mem = self.store.memory(mid)
        except StorageUnavailable: return ApplyResult(Outcome.STORAGE_UNAVAILABLE, memory_id=mid, message="The saved memory could not be read")
        if mem is None: return ApplyResult(Outcome.NOT_FOUND, memory_id=mid, message="This memory no longer exists")
        if not mem["enabled"]: return ApplyResult(Outcome.DISABLED, memory_id=mid, message="This memory is disabled")
        if int(mem["revision"]) != int(rev): return ApplyResult(Outcome.STALE, memory_id=mid, message="This memory was edited; ask for suggestions again")
        templates = self.templates()
        mt = matcher.evaluate(mem, ctx, templates)
        if not mt.grade:
            return ApplyResult(Outcome.VALIDATION_FAILED, memory_id=mid, revision=rev, kind=mem["kind"], problems=tuple(mt.reasons),
                               message="This file does not fit the saved memory: " + "; ".join(_PROBLEM_TEXT.get(p, p.replace("_", " ")) for p in mt.reasons))
        resolved = copy.deepcopy(mt.resolved); checks = {"grade": mt.grade}
        if mem["kind"] == "import_mapping":
            units = list(ctx.units)
            refs = mem["recipe"].get("roles", {})
            for name, v in refs.items():
                for r, i in zip(v if isinstance(v, list) else [v], resolved["roles"][name] if isinstance(resolved["roles"][name], list) else [resolved["roles"][name]]):
                    u = matcher._mem_units(mem, r)
                    if u and i < len(units) and not units[i]: units[i] = u
            ck, problems = matcher.check_mapping(ctx, resolved["roles"], units, mem.get("data_family") or "unknown", numeric_ok)
            checks.update(ck)
            if problems:
                return ApplyResult(Outcome.VALIDATION_FAILED, memory_id=mid, revision=rev, kind=mem["kind"], validation=checks, problems=tuple(problems),
                                   message="The saved mapping does not pass the checks for this file: " + "; ".join(_PROBLEM_TEXT.get(p, p) for p in problems))
            resolved["units"] = units; resolved["read"] = copy.deepcopy(mem["recipe"].get("read", {}))
        try:
            outcome = self.store.add_feedback(mid, rev, str(operation_id or M.new_id())[:80], "accepted", "", "memory")
            if mem.get("needs_revalidation") and not mt.needs_revalidation: self.store.flag_revalidation(mid, False)
        except StorageUnavailable: outcome = Outcome.STORAGE_UNAVAILABLE
        return ApplyResult(outcome, applied=True, memory_id=mid, revision=rev, kind=mem["kind"], recipe=copy.deepcopy(mem["recipe"]), resolved=resolved,
                           validation=checks, message="Saved mapping applied" if mem["kind"] == "import_mapping" else "Applied")

    def rank_templates(self, compatible_template_ids, context, *, explain=False):
        """Reorder the template ids the caller found compatible (opstudio.api.recommend / detection.compatibility) by
        the saved preferences. It returns exactly the ids it was given - it cannot add a template, and an id no memory
        mentions keeps its place. With explain=True: (ids, {id: reason})."""
        ids = list(compatible_template_ids or [])
        try:
            if not self.get_settings()["personal_learning"]: return (ids, {}) if explain else ids
            ranked, why = matcher.rank_templates(ids, self.store.memories(kinds=("template_preference",), enabled=True), Context.build(context), self.templates())
        except StorageUnavailable: ranked, why = ids, {}
        return (ranked, why) if explain else ranked

    # -------------------------------------------------------------------------------------------- feedback and management
    def record_feedback(self, memory_id, revision, outcome, *, operation_id, reason=None):
        """An EXPLICIT answer of the user to a proposal: outcome 'accepted' or 'rejected' (also 'suggestion_accepted' /
        'suggestion_rejected'). Scrolling past, closing a window or not using a suggestion is not a rejection - do not
        call this for those. reason: one of models.FEEDBACK_REASONS (free text is stored as 'other').
        One row per (memory, operation); a repeat returns 'already_saved'."""
        out = str(outcome or "").replace("suggestion_", "")
        if out not in M.FEEDBACK_OUTCOMES: return ActionResult(Outcome.VALIDATION_FAILED, "accepted or rejected")
        r = str(reason or "")
        r = r if r in M.FEEDBACK_REASONS else "other"
        if not self.get_settings()["personal_learning"]: return ActionResult(Outcome.DISABLED, _GENERIC[Outcome.DISABLED], memory_id=memory_id)
        try: res = self.store.add_feedback(memory_id, int(revision or 0), str(operation_id or M.new_id())[:80], out, r, "user")
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The answer could not be saved", memory_id=memory_id)
        return ActionResult(res, _GENERIC.get(res, ""), memory_id=memory_id, revision=int(revision or 0))

    def _toggle(self, memory_id, flag):
        try: res = self.store.set_enabled(memory_id, flag, M.new_id())
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The change could not be saved", memory_id=memory_id)
        return ActionResult(res, {Outcome.SAVED: "Memory enabled" if flag else "Memory disabled"}.get(res, _GENERIC.get(res, "")), memory_id=memory_id)

    def disable_memory(self, memory_id):
        """Keep the memory and its history, but stop offering it. 'saved', 'already_saved', 'not_found', 'storage_unavailable'."""
        return self._toggle(memory_id, False)

    def enable_memory(self, memory_id): return self._toggle(memory_id, True)

    def edit_memory(self, memory_id, recipe, *, reason):
        """Replace the recipe of a memory. The recipe is validated like any untrusted recipe (models.validate_recipe);
        the edit creates a NEW REVISION and keeps the prior recipe. An edited memory is marked as not technically
        validated until it is applied to a file again. A record received from others cannot be edited ('not_permitted').
        reason: a short word such as 'user_edit'."""
        try: mem = self.store.memory(memory_id)
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The memory could not be read", memory_id=memory_id)
        if mem is None: return ActionResult(Outcome.NOT_FOUND, _GENERIC[Outcome.NOT_FOUND], memory_id=memory_id)
        if mem["visibility"] != "personal": return ActionResult(Outcome.NOT_PERMITTED, "A shared record cannot be edited here; disable or forget it instead", memory_id=memory_id)
        try: clean = M.validate_recipe(mem["kind"], copy.deepcopy(recipe))
        except M.RecipeError as e: return ActionResult(Outcome.VALIDATION_FAILED, f"The recipe is not acceptable ({e.code})", memory_id=memory_id, detail={"code": e.code, "path": e.path})
        extra = {"validation": {"structural_checks_passed": None, "preview_rendered": False, "user_confirmed": True, "edited": True}}
        if mem["kind"] in ("import_mapping", "classification", "template_preference") and clean.get("data_family"): extra["data_family"] = clean["data_family"]
        if mem["kind"] == "template_preference":
            installed = self.templates()
            if clean["template_id"] not in installed: return ActionResult(Outcome.VALIDATION_FAILED, _PROBLEM_TEXT["template_not_installed"], memory_id=memory_id, detail={"code": "template_not_installed"})
            clean["template_version"] = installed[clean["template_id"]]; extra["template_id"] = clean["template_id"]; extra["template_version"] = clean["template_version"]
        why = reason if isinstance(reason, str) and re.match(r"^[a-z_]{1,40}$", reason) else "user_edit"
        try: res, rev = self.store.edit_memory(memory_id, clean, why, M.new_id(), extra)
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The edit could not be saved", memory_id=memory_id)
        return ActionResult(res, {Outcome.SAVED: "Memory updated"}.get(res, _GENERIC.get(res, "")), memory_id=memory_id, revision=rev)

    def forget_memory(self, memory_id, *, shared_action=None):
        """Remove a memory for good: the recipe, its revisions, its feedback and the events that led to it. What stays is
        a tombstone (two ids and a time) so that neither a queued upload nor a later download can bring it back.

        shared_action   None / 'keep_shared': a contribution that was already sent stays where it is
                        'withdraw': additionally queue the withdrawal of the sent contribution
        A contribution that is queued but not yet sent is always cancelled. detail['remote_copy'] says whether a copy
        left this computer before - a copy someone already downloaded cannot be recalled immediately."""
        if shared_action not in (None, "withdraw", "keep_shared"): return ActionResult(Outcome.VALIDATION_FAILED, "unknown shared_action", memory_id=memory_id)
        try: res, detail = self.store.forget_memory(memory_id, shared_action)
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The memory could not be removed", memory_id=memory_id)
        with self._lock:
            for sid, ref in list(self._suggestions.items()):
                if ref[0] == memory_id: self._suggestions.pop(sid, None)
        return ActionResult(res, {Outcome.SAVED: "Memory forgotten", Outcome.ALREADY_SAVED: "Already forgotten"}.get(res, _GENERIC.get(res, "")), memory_id=memory_id, detail=detail)

    def cancel_queued_contributions(self, memory_id=None):
        """Remove contributions that are queued but not sent yet (all, or those of one memory)."""
        try: n = self.store.cancel_queued(memory_id)
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The queue could not be changed")
        return ActionResult(Outcome.SAVED if n else Outcome.ALREADY_SAVED, detail={"cancelled": n})

    # -------------------------------------------------------------------------------------------- history
    @staticmethod
    def _state(mem):
        if mem is None: return "forgotten"
        if not mem["enabled"]: return "disabled"
        return "needs_revalidation" if mem["needs_revalidation"] else "active"

    def _contribution(self, mem, rows):
        rows = [r for r in rows if r["memory_id"] == mem["id"] and r["action"] == "submit"]
        if mem["visibility"] != "personal": return {"exists": True, "received": True, "state": mem["status"], "scope": mem["visibility"], "contribution_id": mem["remote_id"]}
        if not rows and not mem["remote_id"]: return {"exists": False, "received": False, "state": "", "scope": "", "contribution_id": ""}
        last = rows[-1] if rows else None
        return {"exists": True, "received": False, "state": mem["status"] if mem["remote_id"] else (last["state"] if last else ""), "scope": last["scope"] if last else "",
                "contribution_id": mem["remote_id"] or (last["contribution_id"] if last else "")}

    def history(self, filters=None):
        """What was recorded, newest first: one dict per event with
            event_id, date, event_type, origin, scope, data_family, kind, memory_id, revision, state
            ('active' | 'disabled' | 'needs_revalidation' | 'forgotten' | ''), shared (a contribution exists),
            contribution_state, changes (the safe before/after difference).
        filters (all optional): event_type (word or list), kind, data_family, state, memory_id, origin, since (ISO time),
        limit (default 500). [] when the database is unavailable."""
        f = dict(filters or {})
        et = f.get("event_type"); et = [et] if isinstance(et, str) else (list(et) if et else None)
        try:
            events = self.store.events(memory_id=f.get("memory_id"), event_types=et, origin=f.get("origin"), since=f.get("since"), limit=int(f.get("limit") or 500))
            mems = {m["id"]: m for m in self.store.memories()}; outbox = self.store.outbox()
        except StorageUnavailable: return []
        out = []
        for e in events:
            mem = mems.get(e["memory_id"]) if e["memory_id"] else None
            state = self._state(mem) if e["memory_id"] else ("forgotten" if e["event_type"] == "memory_forgotten" else "")
            contrib = self._contribution(mem, outbox) if mem else {"exists": False, "state": ""}
            row = {"event_id": e["id"], "date": e["created_at"], "event_type": e["event_type"], "origin": e["origin"], "scope": e["scope"] or (mem["scope"] if mem else ""),
                   "data_family": (e["after"].get("data_family") or (mem["data_family"] if mem else "") or e["context"].get("data_family") or ""),
                   "kind": mem["kind"] if mem else M.EVENT_KIND.get(e["event_type"], ""), "memory_id": e["memory_id"] or "", "revision": int(e["memory_revision"] or 0),
                   "state": state, "shared": bool(contrib["exists"]), "contribution_state": contrib["state"], "changes": privacy.diff(e["before"], e["after"])}
            if f.get("kind") and row["kind"] != f["kind"]: continue
            if f.get("data_family") and row["data_family"] != M.family_token(f["data_family"]): continue
            if f.get("state") and row["state"] != f["state"]: continue
            out.append(row)
        return out

    def memories(self, filters=None):
        """The reusable memories as summaries (newest first): id, kind, scope, visibility, status, data_family, origin,
        state, revision, template_id, user_confirmations, times_applied, times_rejected, created_at, updated_at,
        signature_version, shared, contribution_state. filters: kind, data_family, state, visibility."""
        f = dict(filters or {})
        try: mems = self.store.memories(kinds=(f["kind"],) if f.get("kind") else None, family=M.family_token(f["data_family"]) if f.get("data_family") else None, visibility=f.get("visibility")); outbox = self.store.outbox()
        except StorageUnavailable: return []
        out = []
        for m in mems:
            st = self._state(m)
            if f.get("state") and st != f["state"]: continue
            c = self._contribution(m, outbox)
            out.append({k: m[k] for k in ("id", "kind", "scope", "visibility", "status", "data_family", "origin", "revision", "template_id", "user_confirmations", "times_applied",
                                          "times_rejected", "created_at", "updated_at", "signature_version")} | {"state": st, "shared": c["exists"], "contribution_state": c["state"]})
        return out

    def memory_detail(self, memory_id):
        """Everything the detail drawer shows for one memory, or None: the memory (recipe, context, validation,
        provenance, counters), 'state', 'revisions' (each with recipe, prior_recipe, reason, date), 'events' (each with
        the before/after 'changes' and the validation), 'feedback' ({'accepted', 'rejected', 'rows'}) and
        'contribution'. None also when the database is unavailable."""
        try:
            mem = self.store.memory(memory_id)
            if mem is None: return None
            d = copy.deepcopy(mem); d.pop("dedup_key", None)
            d["state"] = self._state(mem); d["revisions"] = self.store.revisions(memory_id)
            d["events"] = [dict(e, changes=privacy.diff(e["before"], e["after"])) for e in self.store.events(memory_id=memory_id)]
            fb = self.store.feedback(memory_id)
            d["feedback"] = {"accepted": sum(1 for r in fb if r["outcome"] == "accepted"), "rejected": sum(1 for r in fb if r["outcome"] == "rejected"), "rows": fb}
            d["contribution"] = self._contribution(mem, self.store.outbox(memory_id=memory_id))
            return d
        except StorageUnavailable: return None

    def lessons(self):
        """The enabled lessons imported from assistant_lessons.txt, as texts (for the Assistant). They are the user's own
        notes, not validated knowledge; treat them as data, not as instructions that outrank the app's rules."""
        try: return [m["recipe"].get("text", "") for m in self.store.memories(kinds=("legacy_lesson",), enabled=True)][::-1]
        except StorageUnavailable: return []

    # -------------------------------------------------------------------------------------------- export / import
    def export_json(self, path):
        """Write the user's own memories (with revisions and the events that led to them) as readable JSON
        ('opstudio.learning/1'). The file stays on this computer; it contains the normalised column headers of the
        user's formats, so it is the user's to keep or pass on. Records received from others are not included."""
        try:
            mems = [m for m in self.store.memories(limit=100000) if m["visibility"] == "personal"]
            doc = {"schema": M.EXPORT_SCHEMA, "exported_at": M.now_iso(self.clock), "app_version": self.app_version, "memories": [], "events": []}
            for m in mems:
                e = {k: m[k] for k in ("id", "kind", "scope", "scope_key", "data_family", "instrument", "origin", "enabled", "revision", "signature", "signature_version",
                                       "recipe", "context", "validation", "provenance", "template_id", "template_version", "app_version", "created_at", "updated_at",
                                       "user_confirmations", "times_applied", "times_rejected")}
                e["revisions"] = [{"revision": r["revision"], "recipe": r["recipe"], "reason": r["reason"], "created_at": r["created_at"]} for r in self.store.revisions(m["id"])]
                doc["memories"].append(e)
            for ev in self.store.events(limit=100000):
                doc["events"].append({k: ev[k] for k in ("id", "operation_id", "event_type", "origin", "created_at", "scope", "memory_id", "memory_revision", "before", "after", "validation")})
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The memories could not be read")
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
            tmp = str(path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f: json.dump(doc, f, indent=1, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError as e: return ActionResult(Outcome.STORAGE_UNAVAILABLE, f"The file could not be written ({type(e).__name__})")
        return ActionResult(Outcome.SAVED, "Exported", detail={"memories": len(doc["memories"]), "events": len(doc["events"])})

    def import_json(self, path):
        """Read memories from an export file. EVERYTHING in the file is treated as untrusted: the size and schema are
        checked, every recipe goes through models.validate_recipe, every context is rebuilt from the allowlist (its
        signature is recomputed, never taken from the file), ids are checked, and nothing forgotten here is restored.

        An imported memory is the user's to use but arrives UNCONFIRMED: origin 'migration', validation unknown - it
        is offered as a suggestion, never auto-applied and not shareable until it is confirmed again on a real file.
        A memory naming a template that is not installed is kept but flagged 'needs revalidation' and not offered.
        detail: {'imported', 'updated', 'unchanged', 'rejected': [{'index', 'reason'}]}."""
        try:
            if os.path.getsize(path) > 8 * 1024 * 1024: return ActionResult(Outcome.VALIDATION_FAILED, "The file is too large to be a learning export")
            with open(path, encoding="utf-8") as f: doc = json.load(f)
        except (OSError, ValueError) as e: return ActionResult(Outcome.VALIDATION_FAILED, f"The file could not be read ({type(e).__name__})")
        if not isinstance(doc, dict) or doc.get("schema") != M.EXPORT_SCHEMA or not isinstance(doc.get("memories"), list):
            return ActionResult(Outcome.VALIDATION_FAILED, "This is not a learning export of this app")
        if len(doc["memories"]) > 5000: return ActionResult(Outcome.VALIDATION_FAILED, "The file holds too many entries")
        installed = self.templates(); counts = {"imported": 0, "updated": 0, "unchanged": 0, "rejected": []}
        for n, raw in enumerate(doc["memories"]):
            try: mem = self._untrusted_memory(raw, installed)
            except M.RecipeError as e: counts["rejected"].append({"index": n, "reason": e.code}); continue
            try: effect, _mid, _rev = self.store.put_memory(mem, reason="import_json")
            except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The import could not be saved", detail=counts)
            if effect == "tombstoned": counts["rejected"].append({"index": n, "reason": "forgotten_here"})
            else: counts[{"created": "imported", "revised": "updated", "unchanged": "unchanged"}[effect]] += 1
        return ActionResult(Outcome.SAVED if (counts["imported"] or counts["updated"]) else Outcome.ALREADY_SAVED, "Imported", detail=counts)

    def _untrusted_memory(self, raw, installed):
        """A memory dict for the store from an untrusted description (an import file). Raises RecipeError."""
        if not isinstance(raw, dict): raise M.RecipeError("not_an_object", "memory")
        kind = raw.get("kind")
        if kind not in M.KINDS: raise M.RecipeError("unknown_kind", "kind")
        recipe = M.validate_recipe(kind, raw.get("recipe"), untrusted=True)
        rc = raw.get("context") if isinstance(raw.get("context"), dict) else {}
        ctx = Context.build({k: rc.get(k) for k in ("container", "delimiter", "decimal", "encoding", "header_row", "column_count", "headers", "units", "data_family", "instrument")})
        M.assert_inert(ctx.stored())
        scope = M.normalise_scope(raw.get("scope")) or "personal_format"
        key = raw.get("scope_key") if isinstance(raw.get("scope_key"), str) and re.match(r"^[0-9a-f]{0,40}$", raw.get("scope_key")) else ""
        fam = M.family_token(recipe.get("data_family") or raw.get("data_family"))
        if kind == "legacy_format": sig, sver = recipe["legacy_signature"], sg.LEGACY_SIGNATURE_VERSION
        elif kind == "legacy_lesson": sig, sver = "", sg.LEGACY_SIGNATURE_VERSION
        else: sig, sver = ctx.signature, sg.SIGNATURE_VERSION
        tid = recipe.get("template_id") or ""
        steps_t = [s["params"]["template_id"] for s in recipe.get("steps", []) if s.get("op") == "draw_template" and s["params"].get("template_id")] if kind == "workflow" else []
        missing = any(t not in installed for t in ([tid] if tid else []) + steps_t)
        orig = raw.get("origin") if raw.get("origin") in M.ORIGINS else "unknown"
        mid = raw.get("id") if M.is_uuid(raw.get("id")) else None
        return {"id": mid, "kind": kind, "signature": sig, "signature_version": sver, "share_signature": ctx.share_signature if sver == 2 else "", "data_family": fam,
                "instrument": ctx.instrument, "scope": scope, "scope_key": key, "origin": "migration", "enabled": bool(raw.get("enabled", True)), "needs_revalidation": missing,
                "recipe": recipe, "context": ctx.stored() if sver == 2 else {},
                "constraints": {"column_count": ctx.column_count, "template_id": tid, "template_version": installed.get(tid, ""), "signature_version": sver},
                "validation": {"structural_checks_passed": None, "preview_rendered": None, "user_confirmed": None, "imported": True},
                "provenance": {"origin": "migration", "source": "import_json", "original_origin": orig, "app_version": self.app_version},
                "template_id": tid, "template_version": installed.get(tid, ""), "app_version": self.app_version,
                "dedup_key": dedup_key(kind, scope, key, sig, fam, ctx.instrument, recipe)}

    # -------------------------------------------------------------------------------------------- failures (diagnostics)
    def record_failure(self, context, event_type, error_class, *, operation_id):
        """A genuine failure of an import ('import_failed') or of an analysis / graph ('analysis_failed').
        Recorded ONLY while the diagnostics preference is on ('disabled' otherwise), in the diagnostics table - apart
        from memories; a failure can never become a recipe. What is kept: the sanitised structure signature, the data
        family, the template id, the app version and a CLASS of error (privacy.safe_error_class: a word, or the bare
        name of the exception class - never the message, which may contain a path or a sample name).
        error_class may be an exception object or a text. Retries with the same operation id are not counted twice."""
        if event_type not in M.FAILURE_EVENTS: return ActionResult(Outcome.VALIDATION_FAILED, "import_failed or analysis_failed")
        if not self.get_settings()["diagnostics"]: return ActionResult(Outcome.DISABLED, "Diagnostics are switched off; nothing was recorded")
        ctx = Context.build(context)
        try:
            res = self.store.add_diagnostic({"operation_id": str(operation_id or M.new_id())[:80], "event_type": event_type,
                                             "target_id": ctx.target_id("mapping" if event_type == "import_failed" else "analysis"),
                                             "error_class": privacy.safe_error_class(error_class), "data_family": ctx.data_family, "signature": ctx.share_signature,
                                             "template_id": ctx.template_id, "detail": {}})
        except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The failure could not be recorded")
        return ActionResult(res, "Recorded for diagnostics" if res == Outcome.SAVED else _GENERIC.get(res, ""))

    # -------------------------------------------------------------------------------------------- explicit Save actions
    def _save(self, context, before, after, event_type, *, operation_id, scope, rendered, origin, include_limits=False):
        cand = self.stage_change(context, before, after, origin=origin, operation_id=operation_id, event_type=event_type, include_limits=include_limits)
        if cand.origin != "user":
            self.discard(cand.id); return RecordResult(Outcome.NOT_PERMITTED, message=_GENERIC[Outcome.NOT_PERMITTED], candidate_id=cand.id, problems=("origin_not_user",))
        if not cand.learnable:
            self.discard(cand.id); return RecordResult(Outcome.VALIDATION_FAILED, message="There is nothing here that can be saved", candidate_id=cand.id, problems=("nothing_to_save",))
        v = self.validate(cand, context, rendered=rendered)
        if not v.ok:
            self.discard(cand.id)
            return RecordResult(Outcome.STALE if v.stale else Outcome.VALIDATION_FAILED, message="Not saved: " + "; ".join(v.messages), candidate_id=cand.id, problems=v.problems)
        res = self.confirm(cand.id, remember=True, scope=scope, confirmation_token=v.token)
        if res.outcome in (Outcome.STORAGE_UNAVAILABLE, Outcome.VALIDATION_FAILED): self.discard(cand.id)
        return res

    def save_template_preference(self, context, template_id, *, operation_id, scope="personal_family", generated=True, origin="user"):
        """'Prefer this template': the user chose to remember a compatible template. The template must be installed and
        the graph must really have been generated with it (generated=True, as reported by the drawing code).
        scope 'personal_family' (default: for this data family) or 'personal_format' (for exactly this export format).
        Event 'template_preference_saved'. Returns a RecordResult."""
        return self._save(context, {}, {"template_id": str(template_id or "")}, "template_preference_saved", operation_id=operation_id, scope=scope, rendered=generated is True, origin=origin)

    def save_style(self, context, style, *, target, operation_id, scope="personal_family", rendered=True, include_limits=False, origin="user"):
        """'Save style': remember display settings (models.STYLE: line, marker, colours, axis presentation, legend,
        panel arrangement and the per-component switches zoom / inset / markers / observed / fitted / difference /
        background / Bragg ticks) for a DECLARED target:
            target='graph'   this graph only        (context.graph_id)
            target='panel'   this panel only        (context.graph_id + panel_id / panel_index)
            target='family'  graphs of this data family (and of this template, when the context names one)
        Nothing but presentation is kept: no measured values, titles, sample names or fitted results, and no numerical
        axis limits unless include_limits=True. Applying a saved style to several graphs is the caller's explicit batch
        action - a 'panel' style is never offered for another panel. Event 'graph_style_saved'."""
        tgt = dict(target) if isinstance(target, dict) else {"scope": target}
        return self._save(context, {}, {"style": style, "target": tgt}, "graph_style_saved", operation_id=operation_id, scope=scope, rendered=rendered is True, origin=origin, include_limits=include_limits)

    def save_workflow(self, context, steps, *, operation_id, scope="personal_family", succeeded=True, roles=None, origin="user"):
        """'Save workflow': remember a COMPLETED sequence of supported operations (models.STEP_OPS). A step outside that
        closed vocabulary, or a parameter outside its closed set, refuses the whole workflow ('validation_failed',
        problem 'unsupported_operation'). succeeded must be True (the workflow really finished). roles: the mapping in
        use ({'x': col, 'y': [cols]}), recorded only as the structural column meanings the workflow needs.
        A cell edit is not an operation and cannot be saved. Event 'workflow_saved'."""
        try: M.Arr(M._step, 1, 32)(list(steps or []), True, "steps")
        except M.RecipeError as e: return RecordResult(Outcome.VALIDATION_FAILED, message="Not saved: " + _PROBLEM_TEXT["unsupported_operation"], problems=("unsupported_operation", e.code))
        after = {"workflow": {"steps": list(steps or [])}}
        if roles: after["roles"] = roles
        return self._save(Context.build(context), {}, after, "workflow_saved", operation_id=operation_id, scope=scope, rendered=succeeded is True, origin=origin)

    # -------------------------------------------------------------------------------------------- sharing (see sync.py)
    def preview_contribution(self, memory_id, *, scope=None, role_overrides=None):
        """The exact sanitised record that would be shared, for the user to read before consenting (sync.preview_contribution)."""
        from . import sync
        return sync.preview_contribution(self, memory_id, scope=scope, role_overrides=role_overrides)

    def submit_contribution(self, memory_id, *, scope, consent, preview_digest, role_overrides=None):
        """Queue a previewed contribution after explicit consent (sync.submit). Nothing is sent by this call."""
        from . import sync
        return sync.submit(self, memory_id, scope=scope, consent=consent, preview_digest=preview_digest, role_overrides=role_overrides)

    def withdraw_contribution(self, memory_id):
        """Cancel a queued contribution, or queue the withdrawal of one that was sent (sync.withdraw). The memory stays."""
        from . import sync
        return sync.withdraw(self, memory_id)

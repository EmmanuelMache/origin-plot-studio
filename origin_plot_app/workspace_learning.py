"""workspace_learning.py - the Qt side of personal learning.

    LearningController   one per window (ws.learning): turns what the screens show into the allowlisted contexts and
                         snapshots of opstudio.learning, stages a change the USER made, validates it against what is
                         displayed, and persists it only when the user confirms. Screens call this; they never write
                         memory files themselves.
    MappingBar           the compact area under the type / X / Y controls: 'Saved XRD mapping available' (Apply /
                         Dismiss) and 'Use XRD · X: ... · Y: ...' with 'Remember this mapping', a scope and Confirm.
    HistoryDialog        Settings > Learning: what was remembered, with view, edit, disable, export and forget.

Rules kept here (see opstudio/learning/service.py for the storage side):
  * opening, refreshing or restoring a file records nothing (origin 'system');
  * applying a remembered mapping is origin 'memory' and never counts as a new confirmation;
  * a staged change that is not confirmed is thrown away when the file or sheet changes;
  * a failure to remember never undoes the user's work: the mapping stays applied and the message says so;
  * column positions refer to the file's own column order (the raw sheet), never to the order the app shows.
"""
import os, uuid, json, copy
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QComboBox, QDialog, QTableWidget, QTableWidgetItem,
                               QPlainTextEdit, QFileDialog, QMessageBox, QHeaderView, QAbstractItemView, QSplitter, QWidget)

SCOPES = [("personal_format", "This export format"), ("personal_instrument", "This instrument's files"), ("personal_family", "This kind of data"), ("personal_project", "This project")]
EVENT_WORDS = {"classification_corrected": "Data type confirmed", "column_mapping_corrected": "Column mapping", "unit_mapping_confirmed": "Units", "template_preference_saved": "Preferred graph",
               "graph_style_saved": "Graph style", "workflow_saved": "Workflow", "suggestion_accepted": "Suggestion used", "suggestion_rejected": "Suggestion dismissed",
               "memory_disabled": "Switched off", "memory_forgotten": "Forgotten", "import_failed": "Import problem", "analysis_failed": "Analysis problem"}
KIND_WORDS = {"import_mapping": "Column mapping", "classification": "Data type", "unit_mapping": "Units", "template_preference": "Preferred graph", "graph_style": "Graph style",
              "workflow": "Workflow", "legacy_lesson": "Assistant lesson (earlier version)", "legacy_format": "Learned file layout (earlier version)"}
# the graph editor's switches -> the component words of a saved style (presentation only; no ranges, titles or values)
EDITOR_COMPONENTS = {"markers": "markers", "observed_markers": "observed", "fitted_markers": "fitted", "inset": "inset", "show_difference": "difference",
                     "show_bragg": "bragg_ticks", "show_background": "background"}


def _lib():
    from opstudio import learning
    return learning


def _ctx_dict(ctx):
    """The allowlisted fields of a Context as a plain dict (to build a variant of it, e.g. with a template id)."""
    return {k: getattr(ctx, k) for k in _lib().Context.ALLOWED if hasattr(ctx, k)}


GUIDE = """How learning works - you do not have to manage anything.

WHAT THE APP REMEMBERS (only when you say so)
  - Columns and type: correct a file's type or its X / Y columns (Start here or Workbook), tick 'Remember this mapping'
    and press Confirm.
  - Your own graph: Workbook > 'Draw my own graph...' - choose X, Y and any graph that fits, leave 'Remember this for
    such data' ticked. Or on Start here, tick 'Prefer this graph for such data' before 'Create graph'.
  - A look: graph editor > 'Save style...' (this graph, this panel, or graphs of this kind of data).
  - A merge: Workbook > Table > 'Remember the last merge as a workflow...'.

WHAT HAPPENS NEXT TIME
  - A file of the same layout shows 'Saved ... mapping available' with Apply and Dismiss. Apply uses it; Dismiss hides it
    for that file. It is checked against the new file first and never changes your numbers.
  - Your preferred graph is listed first, marked 'Your saved preference'. The other graphs that fit are still there.

WHEN SOMETHING REMEMBERED IS WRONG
  - Open Help > Learning, select the line and press Disable (keep it, stop offering it) or Forget (remove it).
  - Edit changes the settings of one line and keeps the earlier version as a revision.

THE FOUR SWITCHES AT THE TOP
  - Remember what I confirm: the main switch. Off = nothing new is remembered and nothing saved is offered.
  - Apply my own exact mappings without asking: off by default. On = a mapping you confirmed yourself is applied to a
    file of exactly the same layout without the Apply click (it says so, and changing the columns undoes it).
  - Keep problem records / Allow shared contributions: off by default; leave them off unless you set those up.

HELPING TO IMPROVE THE APP (optional, off by default)
  - 'Save the evidence file by itself...' asks once for a folder - choose your Google Drive folder (or another folder
    that is synced). The app then keeps one small file there up to date: kinds of corrections and failures, never
    names, folders or measurements. The app itself sends nothing; your Drive program copies the file, and whoever can
    see that folder can read it. The developer's review reads these files every 14 days.
  - Untick it to stop: the file of this computer is removed from the folder. Local-only mode pauses it.

WHERE IT IS KEPT
  On this computer, in your own data folder - not in the program, not in a project, and nothing is uploaded.
  Only settings are kept (structure, columns, units, switches): never measurements, file names, folders or sample names.
  Export... writes it to a file (a backup, or to move it to another computer with Import...).
"""


class LearningController(QObject):
    changed = Signal()

    def __init__(self, ws):
        super().__init__(ws); self.ws = ws; self._svc = None; self._failed = ""; self._base = {}; self._pending = {}; self._dismissed = set(); self._last_saved = {}
        self._ns = None; self.migration = None

    # ---------------------------------------------------------------- service
    @property
    def svc(self):
        if self._svc is None and not self._failed:
            try: self._svc = _lib().service()
            except Exception as e: self._failed = str(e)[:200]
        return self._svc

    def enabled(self):
        s = self.svc
        try: return bool(s and s.get_settings().get("personal_learning"))
        except Exception: return False

    def migrate_once(self):
        """Take the lessons and learned file layouts of earlier versions into the structured memory (idempotent; the
        original files stay where they are)."""
        s = self.svc
        if s is None or self.migration is not None: return self.migration
        try:
            import private_store
            self.migration = _lib().migrate_legacy(s, os.path.dirname(os.path.abspath(__file__)), private_store.private_dir())
        except Exception as e: self.migration = {"error": str(e)[:200]}
        return self.migration

    def auto_evidence(self):
        """Refresh the automatic evidence file (when the user switched that on). A local write; paused in local-only
        mode. Never raises; returns the ActionResult or None."""
        s = self.svc
        if s is None: return None
        try:
            from opstudio.learning import evidence as EV
            try:
                import outbound_policy; blocked = bool(outbound_policy.local_only())
            except Exception: blocked = False
            return EV.auto_write(s, blocked=blocked)
        except Exception: return None

    def _opaque(self, text):
        """An id for a file / project that is stable on this computer and says nothing about its path or name."""
        if self._ns is None:
            try: self._ns = uuid.UUID(self.svc.installation_id())
            except Exception: self._ns = uuid.uuid4()
        return uuid.uuid5(self._ns, os.path.normcase(os.path.abspath(str(text)))).hex

    # ---------------------------------------------------------------- what is on show
    def describe(self, path):
        """The file and sheet on show as the learning core needs it, or None: the context (structure only), the mapping
        as positions in the file's own column order, and the names needed to apply a mapping again."""
        ctrl = getattr(self.ws, "workbench", None); s = self.svc
        if ctrl is None or s is None or not path: return None
        try:
            import related
            from opstudio import data as OD
            from opstudio.detection import detect
            slug = ctrl.project_for(path); table, sheet, sheets, _cols, prefs = ctrl._table(path, slug)
            raw = ctrl.raw_sheets(path, slug)[sheet]
            derived = set((ctrl.settings_for(path, slug).get("sheet_settings", {}).get(sheet, {}) or {}).get("derived") or []) | set(related.WORKED_NAMES)
            cols = [str(c) for c in raw.columns if str(c) not in derived]
            typed = getattr(table, "measurement_type", None); det = detect(table, typed)
            family = typed or det.kind
            st = os.stat(path) if os.path.isfile(path) else None
            lay = ""
            try:
                import smart_plots as sp
                lay = sp.layout_signature(path) or ""
            except Exception: lay = ""
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "other"
            ctx = _lib().context_from_table(OD.Table("data", raw[cols]), container=ext, data_family=family, project_id=self._opaque("project:" + slug) if slug else "",
                                            file_id=self._opaque(path), sheet_id=f"sheet-{sheets.index(sheet)}", dataset_id=self._opaque(path) + f"-{sheets.index(sheet)}",
                                            source_revision=f"{st.st_mtime_ns}-{st.st_size}" if st else "", legacy_signature=lay)
            x = cols.index(table.x) if table.x in cols else -1; ys = [cols.index(y) for y in (table.ys[:1] if table.ys else []) if y in cols]
            return {"path": path, "ctx": ctx, "cols": cols, "sheet": sheet, "sheet_index": sheets.index(sheet), "family": family, "typed": bool(typed), "detected": det.kind,
                    "needs_confirmation": bool(det.needs_confirmation), "x": x, "ys": ys, "snapshot": {"data_family": family, "x_index": x, "y_indices": ys}, "key": (path, sheets.index(sheet))}
        except Exception:
            return None

    # ---------------------------------------------------------------- baseline, staging, confirmation
    def baseline(self, path):
        """The file was opened or refreshed (not a user correction): remember what it looked like, so a later change by
        the user can be compared with it. A staged change of ANOTHER file or sheet is discarded here."""
        d = self.describe(path)
        if d is None: return None
        for key in [k for k in self._pending if k != d["key"]]: self.cancel(key=key)
        if d["key"] not in self._base and d["key"] not in self._pending: self._base[d["key"]] = {"snapshot": copy.deepcopy(d["snapshot"]), "typed": d["typed"]}
        return d

    def user_changed(self, path, *, type_only=False):
        """The USER changed the type or the X / Y roles and the preview of that change is on show: stage it and check it.
        Returns the pending state ({"text", "valid", "messages"}) or None when there is nothing to learn."""
        s = self.svc; d = self.describe(path)
        if s is None or d is None or not self.enabled(): return None
        base = self._base.get(d["key"]) or {"snapshot": {"data_family": "Unknown", "x_index": -1, "y_indices": []}, "typed": False}
        before = copy.deepcopy(base["snapshot"]); after = copy.deepcopy(d["snapshot"])
        if type_only:
            before = {"data_family": before["data_family"] if base["typed"] else "Unknown"}; after = {"data_family": after["data_family"], "confirmed": True}
        old = self._pending.pop(d["key"], None)
        if old:
            try: s.discard(old["candidate"].id)
            except Exception: pass
        try:
            cand = s.stage_change(d["ctx"], before, after, origin="user", operation_id=s.new_operation_id(), event_type="classification_corrected" if type_only else None)
            if not cand.learnable: self.changed.emit(); return None
            check = s.validate(cand, d["ctx"], rendered=True, current=after)
        except Exception:
            self.changed.emit(); return None
        cols = d["cols"]; xn = cols[d["x"]] if 0 <= d["x"] < len(cols) else "?"; yn = ", ".join(cols[i] for i in d["ys"]) or "?"
        text = f"Use {d['family']}" + ("" if type_only else f" · X: {xn} · Y: {yn}")
        self._pending[d["key"]] = {"candidate": cand, "check": check, "text": text, "type_only": type_only, "valid": bool(check.ok), "messages": list(check.messages), "path": path}
        self.changed.emit(); return self._pending[d["key"]]

    def pending(self, path):
        d = self.describe(path)
        return self._pending.get(d["key"]) if d else None

    def cancel(self, path=None, *, key=None):
        """Throw the staged change away (the page was left, another file or sheet was chosen, or Cancel was pressed)."""
        if key is None:
            d = self.describe(path); key = d["key"] if d else None
        p = self._pending.pop(key, None) if key else None
        if p and self.svc is not None:
            try: self.svc.discard(p["candidate"].id)
            except Exception: pass
        if p: self.changed.emit()
        return bool(p)

    def confirm(self, path, *, remember=True, scope="personal_format"):
        """The user pressed Confirm. Returns (result or None, message). The mapping on show stays applied in every case."""
        s = self.svc; d = self.describe(path)
        if s is None or d is None: return None, ""
        p = self._pending.get(d["key"])
        if p is None: return None, ""
        try: r = s.confirm(p["candidate"].id, remember=bool(remember), scope=scope, confirmation_token=p["check"].token, current_context=d["ctx"])
        except Exception as e:
            self._pending.pop(d["key"], None); self.changed.emit(); return None, "Mapping applied; could not remember it."
        O = _lib().Outcome
        if r.outcome == O.STALE:
            self._pending.pop(d["key"], None); self.changed.emit()
            return r, "The file or sheet changed after this was prepared, so nothing was remembered. Change the mapping again to confirm it."
        if r.outcome == O.VALIDATION_FAILED:
            return r, "Not remembered: " + ("; ".join(p["messages"]) or r.message or "the mapping did not pass the checks")
        self._pending.pop(d["key"], None)
        self._base[d["key"]] = {"snapshot": copy.deepcopy(d["snapshot"]), "typed": d["typed"]}
        what = "Type" if p["type_only"] else "Mapping"
        if r.outcome in (O.SAVED, O.ALREADY_SAVED):
            self._last_saved[d["key"]] = r; msg = f"{what} remembered."
        elif r.outcome == O.STORAGE_UNAVAILABLE: msg = f"{what} applied; could not remember it."
        elif r.outcome == O.DISABLED: msg = f"{what} applied. Personal learning is switched off, so it was not remembered."
        else: msg = f"{what} applied (not remembered)."
        self.changed.emit(); return r, msg

    def last_saved(self, path):
        d = self.describe(path)
        return self._last_saved.get(d["key"]) if d else None

    def undo_saving(self, path):
        """Undo SAVING the memory (not the mapping on show, which stays as it is)."""
        s = self.svc; d = self.describe(path); r = self._last_saved.pop(d["key"], None) if d else None
        if s is None or r is None: return False
        try: out = s.undo_saving(r)
        except Exception: return False
        self.changed.emit(); return bool(getattr(out, "ok", False))

    # ---------------------------------------------------------------- suggestions
    def suggestions(self, path):
        """Saved mappings / types that fit the file on show and are not what is in effect already."""
        s = self.svc; d = self.describe(path)
        if s is None or d is None or not self.enabled() or d["key"] in self._pending: return []
        try: found = s.find_suggestions(d["ctx"], kinds=("import_mapping", "classification"))
        except Exception: return []
        out = []
        for g in found:
            if (d["key"], g.memory_id, g.revision) in self._dismissed: continue
            x, ys, fam = self._resolved(g, d)
            same_map = g.kind != "import_mapping" or (x == d["x"] and ys == d["ys"])
            same_type = not fam or str(fam).lower() == str(d["family"]).lower()
            if same_map and same_type and d["typed"]: continue                      # already what is on show
            out.append(g)
        return out

    def _resolved(self, sug, d):
        r = sug.resolved or {}; roles = r.get("roles") or r
        x = roles.get("x"); x = x.get("i") if isinstance(x, dict) else x
        ys = roles.get("y") or []; ys = [(y.get("i") if isinstance(y, dict) else y) for y in ys]
        fam = (sug.recipe or {}).get("data_family") or sug.data_family
        try: fam = _lib().family_kind(fam) or fam
        except Exception: pass
        return (x if isinstance(x, int) else -1), [y for y in ys if isinstance(y, int)], fam

    def apply(self, path, sug):
        """Use a saved mapping for the file on show. It is checked against this file first. Returns (applied, message)."""
        s = self.svc; d = self.describe(path); ctrl = getattr(self.ws, "workbench", None)
        if s is None or d is None or ctrl is None: return False, ""
        try: r = s.apply_suggestion(sug.id, d["ctx"], operation_id=s.new_operation_id())
        except Exception as e: return False, "The saved mapping could not be used for this file."
        if not r.applied: return False, "The saved mapping does not fit this file" + (": " + r.message if r.message else "") + ". Nothing was changed."
        fake = type("S", (), {"resolved": r.resolved, "recipe": r.recipe, "data_family": sug.data_family, "kind": sug.kind})
        x, ys, fam = self._resolved(fake, d); cols = d["cols"]
        xn = cols[x] if 0 <= x < len(cols) else (cols[d["x"]] if 0 <= d["x"] < len(cols) else ""); yn = cols[ys[0]] if ys and 0 <= ys[0] < len(cols) else (cols[d["ys"][0]] if d["ys"] else "")
        if sug.kind == "classification": xn, yn = "", ""                            # a remembered type says nothing about the columns
        kinds = self.type_names()
        measurement = next((k for k in kinds if str(k).lower() == str(fam).lower()), d["family"] if d["typed"] else "Automatic")
        try: ctrl.set_mapping(path, xn, yn, d["sheet_index"], measurement)
        except Exception as e: return False, f"The saved mapping could not be applied ({str(e)[:120]})."
        d2 = self.describe(path)
        if d2: self._base[d2["key"]] = {"snapshot": copy.deepcopy(d2["snapshot"]), "typed": d2["typed"]}      # applied by memory: the new baseline, not a user correction
        self.changed.emit()
        return True, "Saved mapping applied" + (f": {fam}" if fam else "") + (f" · X: {xn} · Y: {yn}" if xn and yn else "") + ". Change the type or columns to undo it."

    def dismiss(self, path, sug):
        s = self.svc; d = self.describe(path)
        if s is None or d is None: return
        self._dismissed.add((d["key"], sug.memory_id, sug.revision))
        try: s.record_feedback(sug.memory_id, sug.revision, "rejected", operation_id=s.new_operation_id(), reason="not_wanted")
        except Exception: pass
        self.changed.emit()

    def type_names(self):
        sh = getattr(self.ws, "pages", None)
        try:
            page = self.ws.pages.widget(6); return [page.type_combo.itemText(i) for i in range(page.type_combo.count())]
        except Exception: return []

    # ---------------------------------------------------------------- graphs offered, preferred graph
    def rank(self, rows, path):
        """Rows of Workbench.recommendations() with the compatible ones reordered by the saved preferences. Only the
        order among templates that already FIT changes; nothing is added and an unfit template is never moved up."""
        s = self.svc; d = self.describe(path) if path else None
        if s is None or d is None or not rows or not self.enabled(): return rows
        good = [r for r in rows if r.get("compatible")]; rest = [r for r in rows if not r.get("compatible")]
        try: ids, why = s.rank_templates([r["id"] for r in good], d["ctx"], explain=True)
        except Exception: return rows
        if not why: return rows
        by = {r["id"]: r for r in good}; out = []
        for i in ids:
            r = by.get(i)
            if r is None: continue
            if i in why: r = dict(r, preferred=True, reason=(str(why[i]) + ". " + str(r.get("reason") or "")).strip())
            out.append(r)
        for r in out + rest: r.pop("recommended", None)
        if out: out[0]["recommended"] = True
        return out + rest

    def save_template_preference(self, path, template_id, *, scope="personal_family"):
        """'Prefer this graph for such data' - only after the graph was really generated with that template."""
        s = self.svc; d = self.describe(path)
        if s is None or d is None: return None, ""
        try:
            ctx = _lib().Context.build(dict(_ctx_dict(d["ctx"]), template_id=str(template_id)))
            r = s.save_template_preference(ctx, str(template_id), operation_id=s.new_operation_id(), scope=scope, generated=True)
        except Exception as e: return None, "The graph was made; the preference could not be remembered."
        return r, ("Preferred graph remembered for this kind of data." if r.saved else "The graph was made; the preference was not remembered" + (f" ({r.message})." if r.message else "."))

    # ---------------------------------------------------------------- graph style
    def graph_context(self, graph, panel=None):
        s = self.svc
        if s is None: return None
        try:
            combo = graph.combo; path = (combo.get("files") or [""])[0]; d = self.describe(path) if path else None
            fam = d["family"] if d else ""; base = _ctx_dict(d["ctx"]) if d is not None else {}
            gid = self._opaque("graph:" + "|".join(map(str, combo.get("files") or [])) + "|" + str(combo.get("template")))
            return _lib().Context.build(dict(base, data_family=fam or base.get("data_family") or "Unknown", template_id=str(combo.get("template") or ""), graph_id=gid,
                                             panel_id=f"panel-{panel}" if panel is not None else "", panel_index=int(panel) if panel is not None else -1))
        except Exception: return None

    @staticmethod
    def style_of(combo, panel=None):
        """The presentation settings of a graph (or of one of its panels) as a declarative style: the publication style and
        the component switches. No titles, labels, zoom ranges or data."""
        sw = combo.get("switches") or {}; opts = dict(sw)
        if panel is not None: opts.update((sw.get("panel_options") or {}).get(str(panel), {}))
        comp = {word: bool(opts[k]) for k, word in EDITOR_COMPONENTS.items() if k in opts}
        style = {"components": comp} if comp else {}
        if combo.get("style") and panel is None: style["style_id"] = str(combo["style"])
        return style

    def save_style(self, graph, *, target="graph", panel=None, scope="personal_family"):
        s = self.svc; ctx = self.graph_context(graph, panel if target == "panel" else None)
        if s is None or ctx is None: return None, "The style could not be remembered."
        style = self.style_of(graph.combo, panel if target == "panel" else None)
        if not style: return None, "There is nothing to remember yet: change a component or the publication style first."
        try: r = s.save_style(ctx, style, target=target, operation_id=s.new_operation_id(), scope=scope, rendered=True)
        except Exception: return None, "The style could not be remembered."
        where = {"graph": "this graph", "panel": f"panel {int(panel) + 1}" if panel is not None else "this panel", "family": "graphs of this kind of data"}[target]
        return r, (f"Style remembered for {where}." if r.saved else "The style is applied; it was not remembered" + (f" ({r.message})." if r.message else "."))

    def style_suggestions(self, graph, panel=None):
        s = self.svc; ctx = self.graph_context(graph, panel)
        if s is None or ctx is None or not self.enabled(): return []
        try: return [g for g in s.find_suggestions(ctx, kinds=("graph_style",))]
        except Exception: return []

    def apply_style(self, graph, sug, *, panel=None):
        """Put a saved style on ONE graph (or one of its panels). Other graphs are not touched. Returns (changed, message)."""
        s = self.svc; ctx = self.graph_context(graph, panel)
        if s is None or ctx is None: return False, ""
        try: r = s.apply_suggestion(sug.id, ctx, operation_id=s.new_operation_id())
        except Exception: return False, "The saved style could not be used."
        if not r.applied: return False, "The saved style does not fit this graph. Nothing was changed."
        st = (r.recipe or {}).get("style") or r.recipe or {}; comp = st.get("components") or {}
        new = copy.deepcopy(graph.combo); sw = new.setdefault("switches", {})
        opts = sw if panel is None else sw.setdefault("panel_options", {}).setdefault(str(panel), {})
        for k, word in EDITOR_COMPONENTS.items():
            if word in comp: opts[k] = bool(comp[word])
        if st.get("style_id") and panel is None: new["style"] = st["style_id"]
        if new == graph.combo: return False, "This graph already has the saved style."
        graph.combo = new
        return True, "Saved style applied to " + ("this graph." if panel is None else f"panel {int(panel) + 1}.")

    # ---------------------------------------------------------------- workflows and failures
    def save_workflow(self, path, steps, *, scope="personal_family"):
        """An operation the user completed and chose to save (closed vocabulary of steps; no cell values)."""
        s = self.svc; d = self.describe(path)
        if s is None or d is None: return None, "The workflow could not be remembered."
        try: r = s.save_workflow(d["ctx"], steps, operation_id=s.new_operation_id(), scope=scope, succeeded=True)
        except Exception: return None, "The workflow could not be remembered."
        return r, ("Workflow remembered." if r.saved else "Not remembered" + (f" ({r.message})." if r.message else "."))

    def record_failure(self, path, event_type, error):
        """A real failure, kept only when diagnostics are switched on, as an error class - never the text of the error."""
        s = self.svc; d = self.describe(path) if path else None
        if s is None or d is None: return
        try: s.record_failure(d["ctx"], event_type, str(type(error).__name__ if isinstance(error, BaseException) else error), operation_id=s.new_operation_id())
        except Exception: pass


def controller(ws):
    """The one LearningController of a window (made on first use)."""
    c = getattr(ws, "learning", None)
    if c is None:
        c = LearningController(ws); ws.learning = c
    return c


# ============================================================================================ the bar under type / X / Y
class MappingBar(QFrame):
    """Shows, for the file on show: a saved mapping that fits (Apply / Dismiss), and - after the user changed the type
    or the columns - what would be confirmed, with 'Remember this mapping', its scope and Confirm."""
    def __init__(self, ws, path_of, refresh=None, parent=None):
        super().__init__(parent); self.ws = ws; self.path_of = path_of; self.refresh_page = refresh; self.ctl = controller(ws); self._sug = None; self._busy = False
        self.setObjectName("learningBar"); lay = QVBoxLayout(self); lay.setContentsMargins(0, 4, 0, 4); lay.setSpacing(4)
        self.sug_row = QWidget(); r1 = QHBoxLayout(self.sug_row); r1.setContentsMargins(0, 0, 0, 0)
        self.sug_text = QLabel(""); self.sug_text.setWordWrap(True); r1.addWidget(self.sug_text, 1)
        self.b_apply = QPushButton("Apply"); self.b_apply.clicked.connect(self.apply); r1.addWidget(self.b_apply)
        self.b_dismiss = QPushButton("Dismiss"); self.b_dismiss.clicked.connect(self.dismiss); r1.addWidget(self.b_dismiss); lay.addWidget(self.sug_row)
        self.conf_row = QWidget(); r2 = QHBoxLayout(self.conf_row); r2.setContentsMargins(0, 0, 0, 0)
        self.conf_text = QLabel(""); self.conf_text.setWordWrap(True); r2.addWidget(self.conf_text, 1)
        self.remember = QCheckBox("Remember this mapping"); self.remember.setChecked(True); r2.addWidget(self.remember)
        self.scope = QComboBox()
        for key, text in SCOPES: self.scope.addItem(text, key)
        self.scope.setToolTip("Where the remembered mapping is offered again"); r2.addWidget(self.scope)
        self.b_confirm = QPushButton("Confirm mapping"); self.b_confirm.setObjectName("primary"); self.b_confirm.clicked.connect(self.confirm); r2.addWidget(self.b_confirm); lay.addWidget(self.conf_row)
        self.done_row = QWidget(); r3 = QHBoxLayout(self.done_row); r3.setContentsMargins(0, 0, 0, 0)
        self.done_text = QLabel(""); r3.addWidget(self.done_text, 1)
        self.b_view = QPushButton("View"); self.b_view.clicked.connect(lambda: open_history(self.ws)); r3.addWidget(self.b_view)
        self.b_undo = QPushButton("Undo saving"); self.b_undo.setToolTip("Forget what was just remembered. The mapping on show stays as it is."); self.b_undo.clicked.connect(self.undo_saving); r3.addWidget(self.b_undo)
        lay.addWidget(self.done_row); self._done = ""
        self.ctl.changed.connect(self.update_bar); self.update_bar()

    def update_bar(self):
        path = self.path_of(); p = self.ctl.pending(path) if path else None
        self.conf_row.setVisible(bool(p))
        if p:
            self.conf_text.setText(p["text"] + ("" if p["valid"] else "  -  cannot be confirmed: " + "; ".join(p["messages"])))
            self.b_confirm.setEnabled(bool(p["valid"])); self.b_confirm.setText("Confirm type" if p["type_only"] else "Confirm mapping")
            self.remember.setText("Remember this type" if p["type_only"] else "Remember this mapping"); self._done = ""
        sugs = self.ctl.suggestions(path) if path and not p else []
        self._sug = sugs[0] if sugs else None; self.sug_row.setVisible(bool(self._sug))
        if self._sug:
            g = self._sug; fam = g.data_family or ""
            try: fam = _lib().family_kind(fam) or fam
            except Exception: pass
            note = " There are two saved mappings that disagree: check before you apply one." if g.conflict else (" A weaker match: check it before you use it." if g.weak else "")
            self.sug_text.setText(f"Saved {fam} {'type' if g.kind == 'classification' else 'mapping'} available - {str(g.explanation).rstrip(".")}.{note}")
        self.done_row.setVisible(bool(self._done) and not p)
        self.done_text.setText(self._done); saved = bool(path and self.ctl.last_saved(path)); self.b_view.setVisible(saved); self.b_undo.setVisible(saved)
        self.setVisible(bool(p) or bool(self._sug) or (bool(self._done) and not p))

    def _status(self, text):
        if text and hasattr(self.ws, "set_status"): self.ws.set_status(text)

    def confirm(self):
        if self._busy: return                                    # a double click is one confirmation
        self._busy = True
        try:
            path = self.path_of(); r, msg = self.ctl.confirm(path, remember=self.remember.isChecked(), scope=self.scope.currentData())
            if r is None and not msg: return                     # nothing was waiting (a second click): what was said stays
            self._done = msg; self._status(msg); self.update_bar()
        finally: self._busy = False

    def apply(self):
        if self._sug is None: return
        ok, msg = self.ctl.apply(self.path_of(), self._sug); self._done = msg if ok else ""; self._status(msg)
        if ok and self.refresh_page: self.refresh_page()
        self.update_bar()

    def dismiss(self):
        if self._sug is None: return
        self.ctl.dismiss(self.path_of(), self._sug); self._status("The saved mapping is not offered for this file again in this session."); self.update_bar()

    def undo_saving(self):
        ok = self.ctl.undo_saving(self.path_of()); self._done = "Saving undone: it is not remembered. The mapping on show is unchanged." if ok else self._done
        self._status(self._done); self.update_bar()


# ============================================================================================ Settings > Learning
class HistoryDialog(QDialog):
    COLS = ["Date", "What", "Kind of data", "Where it applies", "State", "Shared"]

    def __init__(self, ws=None, parent=None):
        super().__init__(parent or ws); self.ws = ws; self.ctl = controller(ws) if ws is not None else None; self.svc = self.ctl.svc if self.ctl else _lib().service()
        self.setWindowTitle("Learning"); self.resize(980, 620); lay = QVBoxLayout(self)
        head = QLabel("<b>What the app remembers</b> - only what you confirmed, kept on this computer. A remembered mapping or style is a setting, never your measurements. "
                      "Nothing here is shared unless you submit it yourself."); head.setWordWrap(True); lay.addWidget(head)
        row = QHBoxLayout(); self.boxes = {}
        for key, text, tip in [("personal_learning", "Remember what I confirm", "Off: nothing new is remembered and nothing saved is offered"),
                               ("auto_apply", "Apply my own exact mappings without asking", "Only a mapping you confirmed yourself, for exactly the same file layout; it is checked against the file first and can be undone"),
                               ("diagnostics", "Keep problem records for a diagnostic export", "Kinds of failures only (no file names, no data). Used when you create an evidence file for the developer"),
                               ("sharing", "Allow shared contributions", "Off by default. Needs a configured lab or community service; each contribution is previewed and submitted by you")]:
            b = QCheckBox(text); b.setToolTip(tip); b.toggled.connect(lambda on, k=key: self.set_pref(k, on)); self.boxes[key] = b; row.addWidget(b)
        row.addStretch(1); lay.addLayout(row)
        arow = QHBoxLayout(); self.auto_box = QCheckBox("Save the evidence file by itself into a folder (to help improve the app)")
        self.auto_box.setToolTip("Asks once for a folder - choose your Google Drive folder or another synced folder. One small file is kept up to date there: kinds of corrections "
                                 "and failures only, no names, folders or measurements. The app sends nothing itself; whoever can see that folder can read the file. Untick to stop.")
        self.auto_box.toggled.connect(self._auto_toggled); arow.addWidget(self.auto_box); self.auto_label = QLabel(""); self.auto_label.setWordWrap(True); arow.addWidget(self.auto_label, 1); lay.addLayout(arow)
        split = QSplitter(Qt.Horizontal); lay.addWidget(split, 1)
        self.table = QTableWidget(0, len(self.COLS)); self.table.setHorizontalHeaderLabels(self.COLS); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.show_detail); split.addWidget(self.table)
        side = QWidget(); sl = QVBoxLayout(side); sl.setContentsMargins(0, 0, 0, 0)
        self.detail = QPlainTextEdit(); self.detail.setReadOnly(True); sl.addWidget(self.detail, 1)
        btn = QHBoxLayout(); self.buttons = {}
        for key, text, fn in [("edit", "Edit…", self.edit), ("toggle", "Disable", self.toggle), ("forget", "Forget…", self.forget), ("share", "Preview contribution…", self.preview_share), ("withdraw", "Withdraw contribution", self.withdraw)]:
            b = QPushButton(text); b.clicked.connect(fn); self.buttons[key] = b; btn.addWidget(b)
        sl.addLayout(btn); split.addWidget(side); split.setStretchFactor(0, 3); split.setStretchFactor(1, 2)
        foot = QHBoxLayout(); self.note = QLabel(""); self.note.setWordWrap(True); foot.addWidget(self.note, 1)
        for text, fn in [("How it works", self.guide), ("Export…", self.export), ("Import…", self.import_), ("Evidence file for the developer…", self.evidence), ("Close", self.accept)]:
            b = QPushButton(text); b.clicked.connect(fn); foot.addWidget(b)
        lay.addLayout(foot); self.rows = []; self.reload()

    # -- data
    def reload(self):
        s = self.svc; self._loading = True
        prefs = s.get_settings() if s else {}
        for k, b in self.boxes.items(): b.setChecked(bool(prefs.get(k)))
        folder = self.auto_folder(); self.auto_box.setChecked(bool(folder)); self.auto_label.setText(folder)
        self._loading = False
        mems = s.memories() if s else []; self.rows = mems; self.table.setRowCount(len(mems))
        for i, m in enumerate(mems):
            fam = m.get("data_family") or ""
            try: fam = _lib().family_kind(fam) or fam
            except Exception: pass
            scope = dict(SCOPES).get(m.get("scope"), m.get("scope") or "")
            state = {"active": "In use", "disabled": "Switched off", "needs_revalidation": "Needs checking (the graph it names is not installed)", "forgotten": "Forgotten"}.get(m.get("state"), m.get("state") or "")
            if m.get("origin") == "migration": state += " · from an earlier version"
            for c, v in enumerate([str(m.get("updated_at") or m.get("created_at") or "")[:16].replace("T", " "), KIND_WORDS.get(m.get("kind"), m.get("kind") or ""), fam, scope, state,
                                   (m.get("contribution_state") or "yes") if m.get("shared") else "no"]):
                self.table.setItem(i, c, QTableWidgetItem(str(v)))
        if not s: self.note.setText("The learning database could not be opened, so nothing can be remembered in this session. Your work is not affected.")
        elif not mems: self.note.setText("Nothing is remembered yet. Correct a file's type or columns on Start here and confirm with 'Remember this mapping'.")
        self.show_detail()

    def current(self):
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def show_detail(self):
        m = self.current(); on = m is not None
        for b in self.buttons.values(): b.setEnabled(on)
        if not on: self.detail.setPlainText(""); return
        d = self.svc.memory_detail(m["id"]) or {}
        self.buttons["toggle"].setText("Enable" if d.get("state") == "disabled" else "Disable")
        self.buttons["withdraw"].setEnabled(bool(m.get("shared")))
        lines = [KIND_WORDS.get(m.get("kind"), m.get("kind") or ""), f"Revision {d.get('revision', m.get('revision'))} · confirmed by you {m.get('user_confirmations', 0)} time(s) · used {m.get('times_applied', 0)} time(s) · dismissed {m.get('times_rejected', 0)} time(s)", ""]
        lines += ["What is remembered:", json.dumps(d.get("recipe") or {}, indent=1, ensure_ascii=False), ""]
        for e in (d.get("events") or [])[:6]:
            lines.append(f"{str(e.get('date') or e.get('created_at') or '')[:16].replace('T', ' ')}  {EVENT_WORDS.get(e.get('event_type'), e.get('event_type'))}")
            for k, ch in (e.get("changes") or {}).items(): lines.append(f"    {k}: {ch.get('before')!r}  ->  {ch.get('after')!r}")
            v = e.get("validation") or {}
            if v: lines.append("    checks: " + ", ".join(f"{k}={'yes' if x is True else 'no' if x is False else x}" for k, x in v.items() if not isinstance(x, (dict, list))))
        prov = d.get("provenance") or {}
        if prov: lines += ["", "Where it came from: " + ", ".join(f"{k}={v}" for k, v in prov.items() if not isinstance(v, (dict, list)))]
        self.detail.setPlainText("\n".join(lines))

    # -- actions
    def set_pref(self, key, on):
        if getattr(self, "_loading", False) or not self.svc: return
        r = self.svc.set_setting(key, bool(on))
        if key == "sharing" and on: self.note.setText("Sharing is allowed, but no lab or community service is configured in this build yet: nothing is sent. Each contribution would be previewed first.")
        elif key == "sharing" and not on:
            queued = (getattr(r, "detail", {}) or {}).get("queued", 0)
            self.note.setText("Sharing is off: nothing new is uploaded." + (f" {queued} queued contribution(s) remain - 'Withdraw contribution' cancels them." if queued else "") + " A copy that was already exported or downloaded by others cannot be recalled.")
        if self.ctl: self.ctl.changed.emit()

    def toggle(self):
        m = self.current()
        if not m: return
        d = self.svc.memory_detail(m["id"]) or {}
        (self.svc.enable_memory if d.get("state") == "disabled" else self.svc.disable_memory)(m["id"]); self.after("Switched on again." if d.get("state") == "disabled" else "Switched off: it is kept in this list but no longer offered.")

    def forget(self, ask=True):
        m = self.current()
        if not m: return
        if ask and QMessageBox.question(self, "Forget", "Forget this? It is removed from this computer and no longer offered." + (" Its shared contribution is withdrawn too; copies others already downloaded cannot be recalled at once." if m.get("shared") else "")) != QMessageBox.Yes: return
        self.svc.forget_memory(m["id"], shared_action="withdraw" if m.get("shared") else None); self.after("Forgotten.")

    def edit(self, text=None):
        m = self.current()
        if not m: return
        d = self.svc.memory_detail(m["id"]) or {}
        if text is None:
            dlg = QDialog(self); dlg.setWindowTitle("Edit what is remembered"); v = QVBoxLayout(dlg); v.addWidget(QLabel("Settings only (the app checks them). A change is kept as a new revision."))
            ed = QPlainTextEdit(json.dumps(d.get("recipe") or {}, indent=1, ensure_ascii=False)); v.addWidget(ed); h = QHBoxLayout(); ok = QPushButton("Save"); ca = QPushButton("Cancel"); h.addStretch(1); h.addWidget(ok); h.addWidget(ca); v.addLayout(h)
            ok.clicked.connect(dlg.accept); ca.clicked.connect(dlg.reject); dlg.resize(520, 420)
            if dlg.exec() != QDialog.Accepted: return
            text = ed.toPlainText()
        try: recipe = json.loads(text)
        except Exception as e: self.note.setText(f"Not saved: the text is not valid ({e})."); return
        r = self.svc.edit_memory(m["id"], recipe, reason="edited in Learning history")
        self.after("Saved as a new revision." if getattr(r, "ok", False) else "Not saved: " + (getattr(r, "message", "") or "the settings did not pass the checks") + ".")

    def preview_share(self):
        m = self.current()
        if not m: return
        try: p = self.svc.preview_contribution(m["id"])
        except Exception as e: self.note.setText(f"No preview: {str(e)[:160]}"); return
        payload = getattr(p, "payload", None) or (p.get("payload") if isinstance(p, dict) else p)
        QMessageBox.information(self, "Exactly what would be shared", "This is the whole contribution - structure and settings, no names, paths or measurements:\n\n" + json.dumps(payload, indent=1, ensure_ascii=False, default=str)[:3500] +
                                "\n\nNothing is sent from here: no lab or community service is configured in this build yet.")

    def withdraw(self):
        m = self.current()
        if not m: return
        self.svc.withdraw_contribution(m["id"]); self.after("Contribution withdrawn (a queued one is cancelled; a sent one is marked for removal at the next sync).")

    def guide(self, show=True):
        """The short guide: what is remembered, what happens next time, how to undo it. Returns the text."""
        if show:
            d = QDialog(self); d.setWindowTitle("How learning works"); v = QVBoxLayout(d); t = QPlainTextEdit(GUIDE); t.setReadOnly(True); v.addWidget(t)
            b = QPushButton("Close"); b.clicked.connect(d.accept); v.addWidget(b); d.resize(760, 560); d.exec()
        return GUIDE

    def export(self, path=None):
        if not path: path, _ = QFileDialog.getSaveFileName(self, "Export what is remembered", "origin_plot_studio_learning.json", "JSON (*.json)")
        if not path: return None
        r = self.svc.export_json(path); self.note.setText(f"Exported to {path}." if getattr(r, "ok", False) else "Export failed: " + getattr(r, "message", "")); return path

    def import_(self, path=None):
        if not path: path, _ = QFileDialog.getOpenFileName(self, "Import remembered settings", "", "JSON (*.json)")
        if not path: return
        r = self.svc.import_json(path); self.after(getattr(r, "message", "") or ("Imported." if getattr(r, "ok", False) else "Nothing was imported."))

    def evidence(self, path=None):
        """A sanitized evidence file for the developer's fortnightly review. It is written locally; nothing is sent."""
        if not path: path, _ = QFileDialog.getSaveFileName(self, "Save an evidence file", "origin_plot_studio_evidence.json", "JSON (*.json)")
        if not path: return None
        try:
            from opstudio.learning import evidence as EV
            out = EV.export(self.svc, path)
            if not getattr(out, "ok", False):
                self.note.setText("No evidence file was written: " + (getattr(out, "message", "") or "nothing to export") + ". Tick 'Keep problem records for a diagnostic export' first."); return None
            self.note.setText(f"Evidence file written: {path}. It holds kinds of corrections and problems only - no names, paths or measurements. Read it, then send it yourself if you wish."); return path
        except Exception as e:
            self.note.setText(f"The evidence file could not be written ({str(e)[:160]})."); return None

    # -- the automatic evidence file
    def auto_folder(self):
        try:
            from opstudio.learning import evidence as EV
            return EV.auto_folder(self.svc) if self.svc else ""
        except Exception: return ""

    def _auto_toggled(self, on):
        if getattr(self, "_loading", False): return
        if not on: self.set_auto_evidence(""); return
        folder = QFileDialog.getExistingDirectory(self, "Choose your Google Drive folder (or another synced folder)", os.path.expanduser("~"))
        if folder: self.set_auto_evidence(folder)
        else: self.reload()

    def set_auto_evidence(self, folder):
        """Switch the automatic evidence file on (folder) or off (''). Returns the folder in use ('' when off)."""
        if not self.svc: return ""
        from opstudio.learning import evidence as EV
        r = EV.auto_set(self.svc, folder); used = (getattr(r, "detail", None) or {}).get("folder", "") if getattr(r, "ok", False) else ""
        if not getattr(r, "ok", False): self.after("The automatic evidence file was not switched on: " + (getattr(r, "message", "") or "the setting could not be saved") + "."); return ""
        if not used: self.after("The automatic evidence file is off. The file of this computer was removed from the folder."); return ""
        w = self.ctl.auto_evidence() if self.ctl else EV.auto_write(self.svc)
        paused = bool((getattr(w, "detail", None) or {}).get("paused"))
        self.after(f"The evidence file is now kept up to date in {used}" + (" - paused while local-only mode is on." if paused else ". Problem records were switched on for it. "
                   "It holds kinds of corrections and failures only; whoever can see that folder can read it."))
        return used

    def after(self, text):
        self.reload(); self.note.setText(text)
        if self.ctl: self.ctl.changed.emit()


def open_history(ws, parent=None):
    d = HistoryDialog(ws, parent); d.exec(); return d

"""Session basics and the command area, added on top of the window:

  File far left, then Save / Undo / Redo (one Undo / Redo pair for the whole app), then the sections; a command search
  (Ctrl+Q) that finds and runs any command by name.
  Clear graph, Clear all graphs, Remove ticked graphs, Start afresh (keep settings and layout, or not): each asks with a
  one-line summary, and each can be undone (Ctrl+Z) until the app is closed.
  Save (to the session file in use), Save as, Recent sessions, an autosave every few minutes, and 'Recover last session'
  after the app was closed without saving (a crash, a power cut)."""
import json, os, time
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QStringListModel
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QCompleter, QLineEdit, QMenu, QMessageBox, QPushButton, QToolButton, QAbstractButton, QFileDialog

import smart_plots as sp


def _quiet(): return bool(os.environ.get("OPS_NO_OPEN"))
def _flag():
    import workspace_qt as WQ
    return Path(WQ.cfg_path()).with_name("running.flag")


# ------------------------------------------------------------------------------------------------ undo of removals
def _snapshot(w, what):
    w._session_undo.append({"what": what, "t": time.time(), "singles": list(w.singles), "combined": list(w.combined), "boards": list(w.boards), "groups": list(getattr(w, "user_groups", []))})
    del w._session_undo[:-30]; w._session_redo.clear()


def _restore(w, snap):
    w.singles, w.combined, w.boards, w.user_groups = list(snap["singles"]), list(snap["combined"]), list(snap["boards"]), list(snap["groups"])
    w.refresh_list()
    if w.items: w.list.setCurrentRow(0)
    else: w.show_empty()


def undo_any(w):
    """One Undo for the whole app: the last thing done is undone - a removal / clearing, or a change of a graph's look."""
    last_fmt = getattr(w.ribbon, "last_change", 0) if getattr(w, "ribbon", None) is not None else 0
    if w._session_undo and w._session_undo[-1]["t"] >= last_fmt:
        snap = w._session_undo.pop()
        w._session_redo.append({"what": snap["what"], "t": time.time(), "singles": list(w.singles), "combined": list(w.combined), "boards": list(w.boards), "groups": list(getattr(w, "user_groups", []))})
        _restore(w, snap); w.set_status(f"Undone: {snap['what']}. Redo: Ctrl+Y."); return "session"
    if getattr(w, "ribbon", None) is not None: w.ribbon.undo(); return "format"
    w.set_status("Nothing to undo."); return None


def redo_any(w):
    if w._session_redo:
        snap = w._session_redo.pop(); what = snap["what"]
        w._session_undo.append({"what": what, "t": time.time(), "singles": list(w.singles), "combined": list(w.combined), "boards": list(w.boards), "groups": list(getattr(w, "user_groups", []))})
        _restore(w, snap); w.set_status(f"Done again: {what}."); return "session"
    if getattr(w, "ribbon", None) is not None: w.ribbon.redo(); return "format"
    return None


def _ask(w, title, text):
    return _quiet() or QMessageBox.question(w, title, text + "\nYour files on the disk are not touched. Undo: Ctrl+Z.") == QMessageBox.Yes


def _files(items): return len({getattr(i, "path", None) for i in items if getattr(i, "path", None)})


def clear_graph(w):
    it = w.current()
    if it is None: w.set_status("There is no graph on show."); return None
    _snapshot(w, "clear graph"); r = w._remove_current_plain(it)
    if r != "removed": w._session_undo.pop()
    else: w.set_status(f"Removed from the list: {it.title.strip()[:60]}. Undo: Ctrl+Z.")
    return r


def clear_all_graphs(w):
    n = len(w.singles) + len(w.boards)
    if not n: w.set_status("The list is empty already."); return None
    if not _ask(w, "Clear all graphs", f"Remove {n} graph(s) from {_files(w.singles)} file(s) from the list?"): return "kept"
    _snapshot(w, f"clear all graphs ({n})"); w.singles, w.combined, w.boards, w.user_groups = [], [], [], []
    w.refresh_list(); w.show_empty(); w.datamodel.set(None); w.resmodel.set(None); w.set_status(f"{n} graph(s) removed from the list. Undo: Ctrl+Z."); return "cleared"


def remove_ticked(w):
    its = [i for i in w.ticked() if isinstance(i, (sp.Item, sp.Board))]
    if not its: w.set_status("Tick the graphs to remove first."); return None
    if not _ask(w, "Remove ticked graphs", f"Remove {len(its)} ticked graph(s) from {_files(its)} file(s) from the list?"): return "kept"
    _snapshot(w, f"remove {len(its)} graph(s)"); ids = {id(i) for i in its}
    w.singles = [s for s in w.singles if id(s) not in ids]; w.boards = [b for b in w.boards if id(b) not in ids]; w.regroup(); w.refresh_list()
    (w.list.setCurrentRow(0) if w.items else w.show_empty()); w.set_status(f"{len(its)} graph(s) removed from the list. Undo: Ctrl+Z."); return "removed"


def start_afresh(w, keep=None):
    """An empty session. keep=True: settings and layout stay; False: the layout goes back to the default as well."""
    n = len(w.singles) + len(w.boards)
    if keep is None and not _quiet():
        box = QMessageBox(w); box.setWindowTitle("Start afresh"); box.setText(f"Start with an empty session? {n} graph(s) from {_files(w.singles)} file(s) leave the list.\nYour files on the disk are not touched. Undo: Ctrl+Z.")
        b1 = box.addButton("Keep settings and layout", QMessageBox.AcceptRole); b2 = box.addButton("Reset the layout too", QMessageBox.DestructiveRole); box.addButton(QMessageBox.Cancel); box.exec()
        if box.clickedButton() not in (b1, b2): return "kept"
        keep = box.clickedButton() is b1
    w.autosave(); _snapshot(w, "start afresh"); w.singles, w.combined, w.boards, w.user_groups = [], [], [], []
    w.refresh_list(); w.show_empty(); w.datamodel.set(None); w.resmodel.set(None); w.session_path = None
    if keep is False and hasattr(w, "reset_layout"): w.reset_layout()
    w.set_status("Empty session. Add your data files (Ctrl+O, or drop them on the window). Undo: Ctrl+Z."); return "new"


# ------------------------------------------------------------------------------------------------ save, save as, recent, autosave, recovery
def _recent(w):
    import workspace_qt as WQ
    return [p for p in (WQ.load_cfg().get("recent_sessions") or []) if isinstance(p, str)]


def _remember(w, path):
    import workspace_qt as WQ
    if not path or os.path.basename(path) in ("last_session.json", "autosave_session.json"): return
    r = [path] + [p for p in _recent(w) if p != path]; WQ.save_cfg({"recent_sessions": r[:10]}); w.session_path = path; _fill_recent(w)


def _fill_recent(w):
    m = getattr(w, "recent_menu", None)
    if m is None: return
    m.clear(); rs = _recent(w)
    for p in rs:
        a = m.addAction(os.path.basename(p) + "   —   " + os.path.dirname(p), lambda p=p: w.open_session(p)); a.setToolTip(p); a.setEnabled(os.path.isfile(p))
    if not rs: m.addAction("(no saved session yet)").setEnabled(False)


def save(w):
    """Save to the session file in use; the first time it asks where (Save as)."""
    p = getattr(w, "session_path", None)
    return w.save_session(p) if p else w.save_session()


def autosave_now(w):
    """Every few minutes while there is something in the list: the same file 'Resume last session' reads."""
    try:
        if w.singles and w.job_thread is None: w.autosave()
    except Exception: pass


def needs_recovery(w):
    """True when the app was not closed properly last time and an autosaved session exists."""
    try:
        import workspace_menu as WM
        return _flag().exists() and WM.LASTSES.exists()
    except Exception: return False


def recover_last(w):
    r = w.resume_last()
    if r: w.set_status("The last session is back (it was saved by itself).")
    return r


# ------------------------------------------------------------------------------------------------ command search
def commands(w):
    """Every command of the app by name: menu entries (with their menu path) and the buttons that are on show."""
    out = {}
    def walk(menu, path):
        for a in menu.actions():
            t = a.text().split("\t")[0].replace("&", "").strip()
            if a.menu() is not None: walk(a.menu(), path + [t])
            elif t and not a.isSeparator(): out.setdefault(" › ".join(path + [t]), a.trigger)
    for name, b in (("File", getattr(w, "file_btn", None)), ("View", getattr(w, "panels_btn", None)), ("Tools", getattr(w, "tools_btn", None)), ("Help", getattr(w, "help_btn", None))):
        if b is not None and b.menu() is not None: walk(b.menu(), [name])
    for a in w.actions():
        t = a.text().replace("&", "").strip()
        if t and t not in out and not any(k.endswith(" › " + t) for k in out): out[t + (f"   ({a.shortcut().toString()})" if not a.shortcut().isEmpty() else "")] = a.trigger
    for i, (_k, name, _t) in enumerate(__import__("workspace_qt").SECTIONS): out[f"Go to {name}"] = (lambda i=i: w.go(i))
    for b in w.findChildren(QAbstractButton):
        t = b.text().replace("&", "").replace("▾", "").strip()
        if len(t) > 2 and b.isEnabled() and b.menu() is None if isinstance(b, (QPushButton, QToolButton)) else False:
            if not any(k == t or k.endswith(" › " + t) for k in out): out.setdefault(t, b.click)
    return out


def run_command(w, text):
    cmds = commands(w); q = text.strip().lower()
    if not q: return None
    hit = next((k for k in cmds if k.lower() == q), None) or next((k for k in cmds if k.lower().split(" › ")[-1].startswith(q)), None) or next((k for k in cmds if q in k.lower()), None)
    if hit is None: w.set_status(f"No command is called '{text}'. Type a part of its name, e.g. 'export', 'origin', 'reset layout'."); return None
    w.set_status(f"Command: {hit}"); cmds[hit](); return hit


# ------------------------------------------------------------------------------------------------ installing
def install(w):
    import types, workspace_qt as WQ
    w._session_undo, w._session_redo = [], []; w.session_path = None
    w._remove_current_plain = w.remove_current
    def remove_current(it=None):
        it = it or w.current()
        if it is None: return "none"
        _snapshot(w, "remove graph"); r = w._remove_current_plain(it)
        if r != "removed": w._session_undo.pop()
        return r
    w.remove_current = remove_current
    for name, fn in (("undo_any", undo_any), ("redo_any", redo_any), ("clear_graph", clear_graph), ("clear_all_graphs", clear_all_graphs), ("remove_ticked", remove_ticked), ("start_afresh", start_afresh),
                     ("save", save), ("recover_last", recover_last), ("needs_recovery", needs_recovery), ("run_command", run_command), ("commands", commands)):
        setattr(w, name, types.MethodType(fn, w))
    # sessions: remember the file in use and the recent ones
    _save, _open = w.save_session, w.open_session
    def save_session(path=None):
        p = _save(path)
        if p: _remember(w, p)
        return p
    def open_session(path=None):
        if getattr(w, "templates_page", None) is not None and w.pages.currentWidget() is w.templates_page and path is None and hasattr(w.templates_page, "draw_all_in_origin"):
            return w.templates_page.draw_all_in_origin()                # Ctrl+Shift+O on the Templates page: Draw all in Origin like this
        if path is None and w.singles: _snapshot(w, "open session")
        p = _open(path)
        if p and isinstance(p, str): _remember(w, p)
        elif path: _remember(w, path) if os.path.isfile(str(path)) and w.singles else None
        return p
    w.save_session, w.open_session = save_session, open_session
    for name, method in (("save_view", "export_all"), ):
        old = getattr(w, name, None)
        if old is not None:
            setattr(w, name, (lambda old=old, method=method: getattr(w.templates_page, method)() if (getattr(w, "templates_page", None) is not None and w.pages.currentWidget() is w.templates_page and hasattr(w.templates_page, method)) else old()))
    oldg = getattr(w, "group_ticked", None)
    if oldg is not None:
        w.group_ticked = lambda how="stack": w.templates_page.combine() if (how == "overlay" and getattr(w, "templates_page", None) is not None and w.pages.currentWidget() is w.templates_page and hasattr(w.templates_page, "combine")) else oldg(how)
    # one Undo / Redo for the app
    for a in w.findChildren(QAction):
        if a.shortcut().toString() in ("Ctrl+Z", "Ctrl+Y"): a.setShortcut(QKeySequence())
    from PySide6.QtGui import QShortcut
    for sc in w.findChildren(QShortcut):
        if sc.key().toString() in ("Ctrl+Z", "Ctrl+Y"): sc.setEnabled(False)
    au = QAction("Undo", w); au.setShortcut(QKeySequence("Ctrl+Z")); au.triggered.connect(lambda: w.undo_any()); w.addAction(au)
    ar = QAction("Redo", w); ar.setShortcut(QKeySequence("Ctrl+Y")); ar.triggered.connect(lambda: w.redo_any()); w.addAction(ar)
    _header(w)
    try:                                                    # the TGA / DTG module: Tools menu, command search
        import workspace_tga
        w.tga_analysis = lambda path=None: workspace_tga.open_dialog(w, path)
        tm = w.tools_btn.menu(); a = QAction("TGA / DTG analysis: zones, mass loss, CH / CaCO₃, Excel…", w); a.triggered.connect(lambda: w.tga_analysis())
        a.setToolTip("TG + DTG in one graph, zones you can drag, stepwise and tangent mass loss side by side, Ca(OH)₂ / CaCO₃ from zones you confirmed, export to Excel"); a.setStatusTip(a.toolTip())
        tm.insertAction(tm.actions()[0] if tm.actions() else None, a); tm.setToolTipsVisible(True); w.tga_action = a
    except Exception: pass
    # autosave every few minutes; a flag that says the app is running (a crash leaves it behind)
    mins = float(WQ.load_cfg().get("autosave_min") or 5)
    w._autosave_timer = QTimer(w); w._autosave_timer.setInterval(int(max(1.0, mins) * 60000)); w._autosave_timer.timeout.connect(lambda: autosave_now(w)); w._autosave_timer.start()
    w.crashed_last_time = needs_recovery(w)
    if not _quiet():
        try: _flag().write_text(str(time.time()), encoding="utf-8")
        except Exception: pass
        if w.crashed_last_time:
            QTimer.singleShot(800, lambda: (recover_last(w) if QMessageBox.question(w, "Recover last session", "The app was not closed properly last time. Bring back the session that was saved by itself?") == QMessageBox.Yes else None))
    return w


def closed_properly(w=None):
    try: _flag().unlink()
    except Exception: pass


def _header(w):
    """File at the far left, Save / Undo / Redo beside it, the command search at the right; the File menu gets its session entries."""
    tb = getattr(w, "topbar_layout", None); fb = getattr(w, "file_btn", None)
    if tb is None or fb is None: return
    first_nav = next((b for b in w.header_nav.buttons()), None); idx = tb.indexOf(first_nav) if first_nav is not None else 0
    tb.removeWidget(fb); tb.insertWidget(idx, fb); fb.setToolTip("File: new, open, recent, save, import, export, convert, clear / start afresh, exit"); k = idx + 1
    w.quick = []
    for glyph, name, tip, fn in (("💾", "Save", "Save (Ctrl+S) – Save the session to its file: files, graph types, names, edits, layout. The first time it asks where. Disabled: nothing is loaded yet", lambda: w.save()),
                                 ("↶", "Undo", "Undo (Ctrl+Z) – Undo the last thing done: a removal, a clearing, or a change of a graph's look", lambda: w.undo_any()),
                                 ("↷", "Redo", "Redo (Ctrl+Y) – Do again what Undo took back", lambda: w.redo_any())):
        b = QPushButton(glyph, objectName="menu"); b.setFixedWidth(36); b.setToolTip(tip); b.setStatusTip(tip); b.setAccessibleName(name); b.clicked.connect(fn); tb.insertWidget(k, b); k += 1; w.quick.append(b)
    tb.insertSpacing(k, 10)
    w.cmd = QLineEdit(placeholderText="Search commands…  (Ctrl+Q)"); w.cmd.setObjectName("cmdsearch"); w.cmd.setMinimumWidth(170); w.cmd.setMaximumWidth(240); w.cmd.setClearButtonEnabled(True)
    w.cmd.setToolTip("Command search (Ctrl+Q) – Type a part of a command's name and press Enter to run it: 'export', 'origin', 'reset layout', 'clear all graphs' …")
    w.cmd.setStyleSheet("QLineEdit#cmdsearch { background: #24486B; color: white; border: 1px solid #3A6088; border-radius: 6px; padding: 5px 8px; }")
    w._cmd_model = QStringListModel(w); comp = QCompleter(w._cmd_model, w); comp.setCaseSensitivity(Qt.CaseInsensitive); comp.setFilterMode(Qt.MatchContains); comp.setMaxVisibleItems(14); w.cmd.setCompleter(comp)
    def refresh(): w._cmd_model.setStringList(sorted(commands(w)))
    def go():
        t = w.cmd.text(); w.cmd.clear(); run_command(w, t)
    w.cmd.returnPressed.connect(go); w.cmd.refresh = refresh
    si = tb.indexOf(w.search); tb.insertWidget(si if si >= 0 else tb.count(), w.cmd)
    for a in w.findChildren(QAction):                       # Ctrl+Q is the command search now (Exit: Alt+F4, or File > Exit)
        if a.shortcut().toString() == "Ctrl+Q": a.setShortcut(QKeySequence())
    aq = QAction("Search commands", w); aq.setShortcut(QKeySequence("Ctrl+Q")); aq.triggered.connect(lambda: (refresh(), w.cmd.setFocus(), w.cmd.selectAll())); w.addAction(aq)
    # the File menu: session entries where people look for them
    fm = fb.menu(); first = fm.actions()[0] if fm.actions() else None
    def add(text, fn, tip, key=None, before=first):
        a = QAction(text + (f"\t{key}" if key else ""), w); a.triggered.connect(fn); a.setToolTip(tip); a.setStatusTip(tip); fm.insertAction(before, a); return a
    fm.setToolTipsVisible(True)
    add("Save", lambda: w.save(), "Save the session to the file in use (asks where the first time)", "Ctrl+S")
    for a in fm.actions():
        if a.text().startswith("Save session"): a.setText("Save session as…\tCtrl+Shift+S"); a.setToolTip("Save the session under a new name")
    w.recent_menu = QMenu("Recent sessions", w); fm.insertMenu(first, w.recent_menu); _fill_recent(w)
    cm = QMenu("Clear / Start afresh", w); cm.setToolTipsVisible(True); fm.insertMenu(first, cm)
    for text, fn, tip in (("Clear graph", lambda: w.clear_graph(), "Remove the graph on show from the list (the file stays). Undo: Ctrl+Z"),
                          ("Clear all graphs", lambda: w.clear_all_graphs(), "Remove every graph from the list; settings and layout stay. Undo: Ctrl+Z"),
                          ("Remove ticked graphs", lambda: w.remove_ticked(), "Remove the ticked graphs from the list (their files stay on the disk). Undo: Ctrl+Z"),
                          ("Start afresh…", lambda: w.start_afresh(), "An empty session: keep settings and layout, or reset the layout too. Undo: Ctrl+Z"),
                          ("Reset layout", lambda: w.reset_layout(), "Put every panel back where it was at the first start"),
                          ("Recover last session", lambda: w.recover_last(), "Bring back the session that the app saved by itself (every few minutes and when it closes)")):
        a = cm.addAction(text, fn); a.setToolTip(tip); a.setStatusTip(tip)
    fm.insertSeparator(first)
    asv = QAction("Save session as", w); asv.setShortcut(QKeySequence("Ctrl+Shift+S")); asv.triggered.connect(lambda: w.save_session()); w.addAction(asv)
    w.session_menu = cm

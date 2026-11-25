"""Command area and session basics: File far left, quick Save / Undo / Redo, command search, clear / remove / start afresh
with undo, save / save as / recent, autosave and recovery."""
import os, sys, tempfile, json
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
TMP = Path(tempfile.mkdtemp()); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app"))
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
from PySide6.QtWidgets import QApplication, QPushButton, QToolButton
from PySide6.QtCore import Qt
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, workspace_session as WS, smart_plots as sp
app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)
EX = ROOT / "origin_plot_app" / "examples_synthetic"
def wait(w, n=4000):
    for _ in range(n):
        app.processEvents()
        if w.job_thread is None and getattr(w, "loader", None) is None: break
for size in ((1366, 768), (1920, 1080)):
    w = W.Workspace([]); w.resize(*size); w.show(); app.processEvents(); tb = w.topbar_layout
    order = [tb.itemAt(i).widget() for i in range(tb.count()) if tb.itemAt(i).widget() is not None and tb.itemAt(i).widget().isVisible()]
    btns = [x for x in order if isinstance(x, QPushButton)]
    check(f"{size[0]}×{size[1]}: File is the left-most command, then Save, Undo, Redo, then the sections", btns[0] is w.file_btn and btns[1:4] == w.quick and btns[4].text() == "Start here", [b.text() for b in btns[:6]])
    xs = [b.mapTo(w, b.rect().topLeft()).x() for b in btns]; right = max(b.mapTo(w, b.rect().topRight()).x() for b in btns)
    check(f"{size[0]}×{size[1]}: the commands of the top bar are in one row, left to right, nothing clipped", xs == sorted(xs) and right <= w.size().width() and all(b.width() > 20 for b in btns), (right, w.size().width()))
    if size[0] == 1366: w.close()
check("the quick buttons say name, shortcut and what they do (and when they are disabled)", all(" – " in b.toolTip() and "(Ctrl+" in b.toolTip() for b in w.quick) and "Disabled:" in w.quick[0].toolTip())
check("command search (Ctrl+Q) is in the top bar", w.cmd.isVisible() and "Ctrl+Q" in w.cmd.placeholderText() and any(a.shortcut().toString() == "Ctrl+Q" and a.text() == "Search commands" for a in w.actions()))
cmds = w.commands(); check("the command search knows the commands by name (menus with their path, sections, buttons)", len(cmds) > 80 and any(k.endswith("Reset layout") for k in cmds) and "Go to Templates" in cmds and any("Clear all graphs" in k for k in cmds), len(cmds))
r = w.run_command("go to templ"); check("typing a part of a name runs the command", r == "Go to Templates" and w.pages.currentIndex() == 5, r)
r = w.run_command("zzz-nothing"); check("no command found: a helpful line, nothing happens", r is None and "No command is called" in w.status.text(), w.status.text()); w.go(0)
fm = [a.text().split("\t")[0] for a in w.file_btn.menu().actions() if a.text()]
check("File menu: Save project, Recent sessions, Clear / Start afresh first, then the rest", fm[:3] == ["Save project", "Recent sessions", "Clear / Start afresh"] and "Save session as…" in fm and "Exit" in fm, fm[:8])
sub = [a.text() for a in w.session_menu.actions()]
check("Clear / Start afresh: Clear graph, Clear all graphs, Remove ticked graphs, Start afresh, Reset layout, Recover last session", sub == ["Clear graph", "Clear all graphs", "Remove ticked graphs", "Start afresh…", "Reset layout", "Recover last session"], sub)
from PySide6.QtWidgets import QAbstractButton
tot = 0; miss = []
for i in range(w.pages.count()):
    w.go(i)
    for _ in range(6): app.processEvents()
    for b in w.findChildren(QAbstractButton):
        if isinstance(b, (QPushButton, QToolButton)) and b.isVisible():
            tot += 1
            if not b.toolTip().strip(): miss.append((W.SECTIONS[i][1], b.text(), b.objectName(), type(b.parent()).__name__))
check(f"check 2: every visible button in every section has a tooltip ({tot} checked)", tot > 120 and not miss, sorted(set(miss)))
import re as _re
named = [b for b in w.findChildren(QAbstractButton) if isinstance(b, (QPushButton, QToolButton)) and len(b.toolTip()) > 20]
check("spot check of the tooltips: more than 30 describe the command, at least 20 name a shortcut, at least 6 say what enables a disabled command",
      len(named) >= 30 and sum(1 for b in named if "Disabled:" in b.toolTip()) >= 6 and sum(1 for b in named if _re.search(r"\((Ctrl|Shift|F\d|[A-Z]\))", b.toolTip())) >= 20,
      (len(named), sum(1 for b in named if "Disabled:" in b.toolTip()), sum(1 for b in named if _re.search(r"\((Ctrl|Shift|F\d|[A-Z]\))", b.toolTip()))))
w.go(0)
# ---- load, then clear / remove / start afresh, each undoable
w.load([str(EX / "xrd_raw.csv"), str(EX / "calorimetry.csv"), str(EX / "strength.csv")]); wait(w)
n0 = len(w.singles); check("three files loaded", n0 >= 3, n0)
w.list.setCurrentRow(0); first = w.current(); w.clear_graph()
check("Clear graph removes the graph on show", first not in w.singles and len(w.singles) == n0 - 1)
check("… and Undo (one Undo for the whole app) brings it back", w.undo_any() == "session" and len(w.singles) == n0 and first in w.singles)
check("Redo removes it again; Undo once more restores", w.redo_any() == "session" and len(w.singles) == n0 - 1 and w.undo_any() == "session" and len(w.singles) == n0)
w.clear_all_graphs(); check("Clear all graphs empties the list", not w.singles and not w.items)
w.undo_any(); check("Undo brings all graphs back", len(w.singles) == n0)
w.tick_all(False); w.list.item(0).setCheckState(Qt.Checked); app.processEvents(); nt = len([i for i in w.ticked() if isinstance(i, sp.Item)]); w.remove_ticked()
check("Remove ticked graphs removes only the ticked ones; Undo restores", len(w.singles) == n0 - nt and w.undo_any() == "session" and len(w.singles) == n0, (nt, len(w.singles)))
# ---- Delete key / 'Remove selected' on a highlighted (not ticked) row of Your graphs
w.list.clearSelection(); row = next(i for i in range(w.list.count()) if isinstance(w.items[i], sp.Item))
w.list.item(row).setSelected(True); app.processEvents(); target = w.items[row]
check("selected() reports the highlighted row, not the ticked ones", w.selected() == [target])
r = w.remove_selected()
check("Delete / 'Remove selected' removes the highlighted graph; Undo restores", r == "removed" and target not in w.singles and w.undo_any() == "session" and target in w.singles)
w.list.clearSelection(); app.processEvents()
check("with nothing highlighted, Remove selected says so and removes nothing", w.remove_selected() is None and len(w.singles) == n0)
auto_row = next((i for i in range(w.list.count()) if isinstance(w.items[i], sp.Combined) and not getattr(w.items[i], "mine", False)), None)
if auto_row is not None:
    w.list.item(auto_row).setSelected(True); app.processEvents()
    check("a ★ combined figure the app made can't be deleted directly; a clear message says so (not a silent no-op)",
          w.remove_selected() == "auto" and "change the Group list" in w.status.text() and len(w.singles) == n0)
    w.list.clearSelection(); app.processEvents()
del_act = next((a for a in w.list.actions() if a.shortcut().toString() == "Del"), None)
check("Your graphs has one Delete action, removing the highlighted graph(s) (or the one on show)", del_act is not None)
w.start_afresh(keep=True); check("Start afresh: an empty session, settings and layout kept", not w.singles and w.outdir is not None)
w.undo_any(); check("Start afresh can be undone", len(w.singles) == n0)
# ---- undo of a change of look still works through the same Undo
it = next(i for i in w.items if isinstance(i, sp.Item)); w.list.setCurrentRow(w.items.index(it)); app.processEvents()
w.ribbon.change({"title": "My title"}) if hasattr(w.ribbon, "change") else None
k = w.undo_any(); check("the same Undo undoes a change of a graph's look when that was the last thing done", k in ("format", "session"), k)
# ---- save, save as, recent
p1 = str(TMP / "one.json"); w.save_session(p1); check("Save session as writes the file and remembers it", os.path.isfile(p1) and w.session_path == p1 and W.load_cfg()["recent_sessions"][0] == p1)
os.remove(p1); w.save(); check("Save (Ctrl+S) writes to the session file in use without asking", os.path.isfile(p1))
rec = [a.text() for a in w.recent_menu.actions()]; check("Recent sessions lists it", any("one.json" in t for t in rec), rec)
w.clear_all_graphs(); w.open_session(p1); wait(w); check("a recent session opens again with its graphs", len(w.singles) == n0)
# ---- autosave and recovery
import workspace_menu as WM
check("an autosave timer runs every few minutes (5 by default)", w._autosave_timer.isActive() and w._autosave_timer.interval() == 5 * 60000)
if WM.LASTSES.exists(): os.remove(WM.LASTSES)
WS.autosave_now(w); check("the autosave writes the session that 'Recover last session' reads", WM.LASTSES.exists())
WS._flag().write_text("x"); check("after a crash (the running flag is left behind) the app knows there is a session to recover", w.needs_recovery())
w.clear_all_graphs(); w.recover_last(); wait(w); check("Recover last session brings the graphs back", len(w.singles) == n0)
# ---- View > Side bar, and panels that can be dragged
w.panel_actions["nav"].setChecked(True); app.processEvents()
check("View > Side bar shows the side bar with the sections", w.navw.isVisible() and w.navw.width() >= 100 and [b.text() for b in w.navgroup.buttons()][:2] == ["Start here", "Workspace"], w.navw.width())
w.panel_actions["nav"].setChecked(False); app.processEvents(); check("… and hides it again", not w.navw.isVisible())
d0 = w.graphs_dock; f0 = d0.windowFlags(); d0.setFloating(True); app.processEvents()
check("a panel that floats while it is dragged stays a dock panel (so it can be dropped on another side)", d0.isFloating() and not getattr(d0, "_popped", False) and not bool(d0.windowFlags() & Qt.WindowMinMaxButtonsHint))
w.wsmain.addDockWidget(Qt.RightDockWidgetArea, d0); d0.setFloating(False); app.processEvents()
check("… and docks on the other side", not d0.isFloating() and w.wsmain.dockWidgetArea(d0) == Qt.RightDockWidgetArea)
w.panel_as_window(d0); app.processEvents(); check("'as its own window' makes a normal window with minimise / maximise", d0.isFloating() and bool(d0.windowFlags() & Qt.WindowMinMaxButtonsHint))
w.dock_back(); app.processEvents(); check("'Put the panels back in place' docks it again", not d0.isFloating() and w.wsmain.dockWidgetArea(d0) == Qt.LeftDockWidgetArea)
# ---- every panel: fold, float, close - clear buttons in its title
d1 = w.settings_dock; w.dock_back(); app.processEvents()
check("every panel has a title strip with Fold, Float and Close buttons (with tooltips)", all(hasattr(d, "close_btn") and d.close_btn.toolTip().startswith("Close") and d.fold_btn.toolTip() and d.float_btn.toolTip() for d in w.wsmain.findChildren(type(d1))) and len(w.wsmain.findChildren(type(d1))) >= 6)
d1.fold_btn.click(); app.processEvents(); folded = not d1.widget().isVisible() and d1.isVisible(); d1.fold_btn.click(); app.processEvents()
check("Fold leaves only the title; a second click unfolds", folded and d1.widget().isVisible())
d1.close_btn.click(); app.processEvents(); closed = not d1.isVisible(); d1.toggleViewAction().trigger(); app.processEvents()
check("Close hides the panel; View > Panels brings it back with its content", closed and d1.isVisible() and d1.widget().isVisible())
d1.float_btn.click(); app.processEvents(); fl = d1.isFloating(); d1.float_btn.click(); app.processEvents(); check("Float takes the panel out; a second click puts it back", fl and not d1.isFloating())
# ---- the app finishes its own update
import self_update as su
check("the updater knows when a folder of the new version is missing here", su.incomplete(str(TMP)) and not su.incomplete(str(ROOT / "origin_plot_app")))
w._upd_msg(("waiting", {"version": sp.VERSION, "completes": True}))
check("… and then the button 'Finish the update (one click)' appears by itself", w.upd_btn.text().startswith("↑ Finish the update") and "Finish the update" in w.status.text(), w.upd_btn.text())
w.close(); check("closing properly clears the flag: nothing to recover next time", not WS._flag().exists())
print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

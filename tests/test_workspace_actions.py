"""Modern window: right-click menus, mouse actions, the Save menu and keyboard shortcuts (real key presses), without a screen."""
import json, os, sys, tempfile, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TMP = Path(tempfile.mkdtemp(prefix="ws_actions_"))
os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_NO_OPEN"] = "1"; os.environ["ORIGIN_PLOT_APP_HOME"] = str(TMP / "store")
ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "origin_plot_app"; sys.path.insert(0, str(A))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import workspace_qt as W, workspace_actions as WA, smart_plots as sp
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
app = QApplication.instance() or QApplication(sys.argv); app.setStyleSheet(W.STYLE)
def wait(c, t=120):
    t0 = time.time()
    while not c() and time.time() - t0 < t: app.processEvents(); time.sleep(0.02)
    app.processEvents(); return c()
E = A / "examples_synthetic"
w = W.Workspace([str(E / f) for f in ("xrd_raw.csv", "TGA_Ref_28d_rep1.txt", "TGA_Ref_28d_rep2.txt", "ftir.xlsx")]); w.resize(1500, 920); w.show()
wait(lambda: w.thread is None and w.list.count() > 0); w.outdir.setText(str(TMP / "results")); w.activateWindow(); app.processEvents()
saved = {}
WA.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (saved["path"], ""))
WA.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (saved["path"], ""))
def key(k, mod=Qt.NoModifier, target=None):
    QTest.keyClick(target or w, k, mod); app.processEvents()

# ---------------------------------------------------------------- keyboard
key(Qt.Key_F1)
check("F1 shows the card of mouse actions and shortcuts", hasattr(w, "shortcut_box") and "Ctrl+S" in w.shortcut_box.text() and "Right click" in w.shortcut_box.text())
dup = [k for k in WA.SHORTCUTS if k[2] is not None]; seqs = [a.shortcut().toString() for a in w.actions() if a.shortcut().toString()]          # the window-wide keys (list / graph keys are local to them)
check("no shortcut is given twice (a doubled key would do nothing)", len(seqs) == len(set(seqs)), sorted(s for s in seqs if seqs.count(s) > 1))
key(Qt.Key_2, Qt.ControlModifier | Qt.ShiftModifier)
check("Ctrl+Shift+2 opens Analysis", w.pages.currentIndex() == 1)
key(Qt.Key_1, Qt.ControlModifier | Qt.ShiftModifier)
i_x = next(i for i, it in enumerate(w.items) if "xrd_raw" in str(getattr(it, "path", "")))
w.list.setFocus(); w.list.setCurrentRow(i_x); app.processEvents()
key(Qt.Key_Space, target=w.list)
check("Space ticks the graph on show (in Your graphs)", w.list.item(i_x).checkState() == Qt.Checked)
key(Qt.Key_Space, target=w.list)
check("... and unticks it", w.list.item(i_x).checkState() == Qt.Unchecked)
key(Qt.Key_A, Qt.ControlModifier, target=w.list)
check("Ctrl+A ticks all", all(w.list.item(i).checkState() == Qt.Checked for i in range(w.list.count())))
key(Qt.Key_A, Qt.ControlModifier | Qt.ShiftModifier, target=w.list)
check("Ctrl+Shift+A unticks all", not w.ticked())
key(Qt.Key_F, Qt.ControlModifier)
check("Ctrl+F goes to the search box", w.search.hasFocus())
w.list.setFocus(); w.list.setCurrentRow(i_x); app.processEvents()
saved["path"] = str(TMP / "s1.json"); w.list.item(i_x).setCheckState(Qt.Checked)
key(Qt.Key_S, Qt.ControlModifier)
d = json.load(open(TMP / "s1.json", encoding="utf-8")) if (TMP / "s1.json").exists() else {}
check("Ctrl+S saves the session (the current window's format, plus ticks and your groups)", "files" in d and "graphs" in d and len(d["modern_ticked"]) == 1, list(d)[:8])
key(Qt.Key_E, Qt.ControlModifier); wait(lambda: w.job_thread is None, 200)
pub = sorted(p.suffix for p in (TMP / "results" / "publication").glob("*")) if (TMP / "results" / "publication").exists() else []
check("Ctrl+E saves this graph (PNG, PDF, SVG ...)", {".png", ".pdf", ".svg"} <= set(pub), pub)
ax = w.fig.axes[0]; x0 = ax.get_xlim()
w.canvas.setFocus(); key(Qt.Key_Z, target=w.canvas)
check("Z on the graph: zoom mode", "zoom" in str(w.navtb.mode).lower())
key(Qt.Key_S, target=w.canvas)
check("S on the graph: select-range mode (a letter, so only on the graph)", w.span is not None)
key(Qt.Key_Escape)
# ---------------------------------------------------------------- mouse
class Ev:  # a wheel event as matplotlib gives it
    def __init__(s, up): s.inaxes, s.button, s.xdata, s.ydata = ax, "up" if up else "down", 30.0, 1000.0
w.wheel_zoom(Ev(True)); x1 = ax.get_xlim()
check("mouse wheel up zooms in around the pointer", (x1[1] - x1[0]) < (x0[1] - x0[0]) and x1[0] < 30 < x1[1], (x0, x1))
w.reset_axes(); check("double click / Ctrl+R resets the axes", abs(ax.get_xlim()[0] - x0[0]) < 1e-6)
li = w.list.item(i_x); w.list.itemDoubleClicked.emit(li)
check("double click a graph in the list: tick / untick", li.checkState() == Qt.Unchecked)
# drag to change the order
first_single = next(i for i, it in enumerate(w.items) if it in w.singles); last = w.list.count() - 1
before = [s.title for s in w.singles]
it_ = w.list.takeItem(last); w.list.insertItem(first_single, it_); w.reorder_from_list()
check("dragging a graph in Your graphs changes the order of the graphs", [s.title for s in w.singles] == [before[-1]] + before[:-1], [s.title[:12] for s in w.singles])
# ---------------------------------------------------------------- right click
i_x = next(i for i, it in enumerate(w.items) if "xrd_raw" in str(getattr(it, "path", "")))
rect = w.list.visualItemRect(w.list.item(i_x)); m = w.menu_graphs(rect.center())
texts = [a.text() for a in m.actions()]
check("right click on a graph: tick, sample name, graph type, analyse, peak labels, group, draw, save, folder, remove",
      all(any(t.startswith(x) for t in texts) for x in ("Tick", "Sample name", "Graph type", "Analyse", "Peak labels", "Group the ticked", "Draw in Origin", "Save:", "Open the file", "Remove")), texts)
next(a for a in m.actions() if a.text() == "Tick only this one").trigger(); app.processEvents()
check("'Tick only this one' from the menu", [w.items.index(i) for i in w.ticked()] == [i_x])
r = w.quick_tool(w.items[i_x], "Find peaks"); job_done = wait(lambda: w.job_thread is None, 120)
check("right click > Analyse > Find peaks runs the tool on that graph", w.pages.widget(1).resmodel.rowCount() >= 3, w.pages.widget(1).msg.text()[:80])
w.go(0); w.list.setCurrentRow(i_x); app.processEvents()
mc = w.menu_canvas(w.canvas.rect().center())
check("right click on the graph: reset, zoom, pan, range, labels, copy, save view, save, draw", len([a for a in mc.actions() if a.text()]) >= 9, [a.text() for a in mc.actions() if a.text()])
w.copy_view(); check("copy the picture to the clipboard", not QApplication.clipboard().pixmap().isNull())
p = w.save_view(str(TMP / "view.svg")); check("save the view (with your zoom) as SVG / PNG / PDF", Path(p).exists() and Path(p).stat().st_size > 1000)
from PySide6.QtCore import QItemSelectionModel as _SM
w.dataview.selectionModel().select(w.datamodel.index(0, 0), _SM.SelectionFlag.Select); w.dataview.selectionModel().select(w.datamodel.index(1, 1), _SM.SelectionFlag.Select)
t = w.copy_table(w.dataview)
check("right click on the Data table: copy the selected cells (tab-separated, for Excel or Origin)", t.count("\n") == 2 and "\t" in t, t[:80])
mt = w.menu_table(w.dataview.rect().center(), w.dataview, "data"); check("table menu: copy, copy all, save", len([a for a in mt.actions() if a.text()]) == 3)
check("save the data table as CSV and as Excel", Path(w.save_table("data", str(TMP / "d.csv"))).exists() and Path(w.save_table("data", str(TMP / "d.xlsx"))).exists())
w.assistant.say("ai", "Hello **there**")
mch = w.menu_chat(w.assistant.view.rect().center()); check("right click in the chat: copy, copy all, save, new chat", any(a.text() == "Save the chat…" for a in mch.actions()))
check("save the chat as text", "Hello there" in open(w.save_chat(str(TMP / "chat.txt")), encoding="utf-8").read())
# remove, then open the session again in a new window
n = len(w.singles); w.list.setCurrentRow(i_x); w.list.setFocus(); key(Qt.Key_Delete, target=w.list)
check("Delete removes the graph from the list (not the file)", len(w.singles) == n - 1 and (E / "xrd_raw.csv").exists())
w2 = W.Workspace([]); w2.show(); saved["path"] = str(TMP / "s1.json"); r = w2.open_session()
check("Open a session (Ctrl+Shift+O): graphs, graph types and ticks come back", r == len(d["graphs"]) and len(w2.ticked()) == 1, r)
names = [a.text() for a in w.save_btn.menu().actions() if a.text()]
check("Save ▾ menu: graph, view, copy, data, results, session, open session, chat, results folder", len(names) == 9 and any("Ctrl+S" in x for x in names), names)
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

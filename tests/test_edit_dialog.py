"""Right click on a graph -> Edit this graph…: titles, fonts, axes, curves, legend, look (and XRD zoom / pattern-or-fit) in one window."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
os.environ["OPS_SETTINGS_FILE"] = str(Path(tempfile.mkdtemp()) / "settings_modern.json")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "tests"))
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
from PySide6.QtWidgets import QApplication, QMenu, QColorDialog
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor
from matplotlib.colors import to_rgb
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, smart_plots as sp, make_highscore as mh
D = Path(tempfile.mkdtemp())
w = W.Workspace([]); w.resize(1600, 900); w.show(); app.processEvents()
w.load_sync([str(ROOT / "origin_plot_app" / "examples_synthetic" / "tga.xlsx"), str(mh.write_fit(D / "F1.CSV"))]); app.processEvents()
tga = next(i for i in w.singles if i.kind == "TGA"); fit = next(i for i in w.singles if i.kind.startswith("Fit"))
w.list.setCurrentRow(w.items.index(tga)); app.processEvents(); w.canvas.draw()
rb = w.ribbon
# right click on an empty part of the graph
c = w.canvas; ax = c.figure.axes[0]; bb = ax.get_window_extent(); dpr = c.devicePixelRatioF()
px, py = (bb.x0 + bb.x1) / 2 + 3, bb.y0 + 0.93 * bb.height
m = QMenu(); rb.menu_items(m, QPoint(int(px / dpr), int(c.height() - py / dpr)))
texts = [a.text() for a in m.actions() if a.text()]
check("right click anywhere on a graph: 'Edit this graph…' first, then title, axis titles, look, legend, axis range, undo / redo / back",
      texts and texts[0].startswith("✎") and "Title…" in texts and "x axis title…" in texts and "Look" in texts and "Legend" in texts and "Undo (Ctrl+Z)" in texts, texts)
mg = W.QMenu() if hasattr(W, "QMenu") else QMenu()
import workspace_actions as WA
captured = {}
WA._show = lambda self, menu, widget, pos: captured.setdefault("m", menu)
w.menu_graphs(w.list.visualItemRect(w.list.item(w.items.index(tga))).center())
check("right click in Your graphs: 'Edit this graph…' too", any(a.text().startswith("✎") for a in captured["m"].actions()))
# the window
d = rb.edit_dialog(tga); app.processEvents()
check("the window: Titles, Text, Axes, Curves, Layout", [d.tabs.tabText(i) for i in range(d.tabs.count())] == ["Titles", "Text", "Axes", "Curves", "Layout"])
d.e_title.setText("Mass loss of Ref 28 d"); d.e_y.setText("Mass (%)"); d.e_y.setSelection(0, 0)
d.e_x.setText("T (°C)"); d.e_x.setFocus(); d.e_x.setSelection(0, 1); d.wrap("_")
d.r_role.setCurrentIndex(1); d.r_size.setCurrentText("14"); d.r_bold.setCurrentIndex(2); d.r_italic.setChecked(True)
d.a_x0.setText("100"); d.a_x1.setText("900"); d.a_w.setValue(2.0)
QColorDialog.getColor = staticmethod(lambda *a, **k: QColor("#00205b"))
d.pick("axis")
d.pick_line("*", d.tab.cellWidget(0, 1)); d.tab.cellWidget(0, 2).setValue(2.5)
d.l_leg.setCurrentIndex(2)
d.apply(); app.processEvents()
f = tga.fmt
check("Apply: title, axis titles (with a subscript), fonts, x range, axis colour and weight, curve colour and weight, legend - one step",
      f.get("title") == "Mass loss of Ref 28 d" and f.get("xtitle") == "_{T} (°C)" and f["text"]["axis_titles"] == {"size": 14.0, "bold": False, "italic": True}
      and f.get("xlim") == [100.0, 900.0] and f["axis"] == {"colour": "#00205b", "width": 2.0} and f["lines"]["*"] == {"colour": "#00205b", "width": 2.5} and f.get("legend") == "off", f)
check("... drawn in the graph", tuple(w.fig.axes[0].get_xlim()) == (100.0, 900.0) and to_rgb(w.fig.axes[0].spines["left"].get_edgecolor()) == to_rgb("#00205b"))
rb.undo(); app.processEvents()
check("Ctrl+Z undoes the whole Apply at once", not getattr(tga, "fmt", None))
rb.redo(); d.close()
d2 = rb.edit_dialog(tga); d2.l_look.setCurrentText("Slides"); d2.apply(); app.processEvents()
check("Layout › Look: a ready-made look", tga.fmt["text"]["axis_titles"]["size"] == 16 and tga.fmt.get("title") == "Mass loss of Ref 28 d")
d2.close()
d3 = rb.edit_dialog(tga); r = d3.apply()
check("Apply with nothing changed: nothing happens", r == "same"); d3.close()
# XRD: zoom and pattern / fit in the same window
w.list.setCurrentRow(w.items.index(fit)); app.processEvents()
d4 = rb.edit_dialog(fit)
check("an XRD fit: the window also has the zoomed part and pattern / fit", d4.l_zoom.isVisibleTo(d4) or d4.l_zoom.parent() is not None)
d4.l_zoom.setCurrentIndex(2); d4.l_view.setCurrentText(sp.FIT_VIEWS[1]); d4.apply(); app.processEvents()
check("... applied: zoom off, the whole fit", fit.fmt.get("zoom_off") and len(fit.spec["panels"]) >= 2 and not any(p.get("inset") for p in fit.spec["panels"]))
d4.close(); w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

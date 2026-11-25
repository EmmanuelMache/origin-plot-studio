"""Editing on the graph itself: click (the ribbon opens on it, with a frame round it), double click (type a title again), right click
(bigger, bold, colour, thicker …), drag the zoomed part. XRD only, beside Zoom / Pan: the zoomed part on or off, and the middle part of
a fit (tick rows, peaks with labels from the peak list, both, nothing)."""
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
import numpy as np
import smart_plots as sp, make_highscore as mh
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMenu
from PySide6.QtCore import QPoint, Qt
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W
D = Path(tempfile.mkdtemp())
files = [mh.write_fit(D / "S1FIT.CSV"), mh.write_peaklist(D / "S1.CSV"), ROOT / "origin_plot_app" / "examples_synthetic" / "strength.csv"]
w = W.Workspace([]); w.resize(1500, 950); w.show(); app.processEvents()
w.load_sync([str(f) for f in files]); app.processEvents()
fit = next(i for i in w.singles if i.kind.startswith("Fit")); xy = next(i for i in w.singles if not i.kind.startswith(("Fit", "XRD")))
rb = w.ribbon
# ---------------------------------------------------------------- the middle part of a fit
names = lambda: [p["yname"] or ("tick rows" if p.get("rows") else "?") for p in fit.spec["panels"]]
w.list.setCurrentRow(w.items.index(fit)); app.processEvents()
check("XRD fit: it opens as the measured pattern with its labels (the basic graph): no calculated curve, no difference",
      [c["label"] for c in fit.spec["panels"][0]["curves"]] in (["Observed"], ["Yobs"]) and len(fit.spec["panels"]) == 1 and fit.spec["panels"][0].get("labels")
      and w.xrd_view.isVisibleTo(w) and w.xrd_view.currentText() == sp.FIT_VIEWS[0] and not w.xrd_mid.isVisibleTo(w))
w.xrd_view.setCurrentText(sp.FIT_VIEWS[1]); w.xrd_view.activated.emit(1); app.processEvents()
check("... 'Fit' beside Zoom / Pan: observed, calculated and difference (and the middle-part choice appears)", len(fit.spec["panels"]) >= 2 and w.xrd_mid.isVisibleTo(w))
for mid, want in ((sp.FIT_MIDDLE[2], ["Peaks", "Difference"]), (sp.FIT_MIDDLE[3], ["Peaks", "tick rows", "Difference"]), (sp.FIT_MIDDLE[1], ["tick rows", "Difference"]), (sp.FIT_MIDDLE[4], ["Difference"])):
    w.xrd_mid.setCurrentText(mid); w.xrd_mid.activated.emit(w.xrd_mid.currentIndex()); app.processEvents()
    check(f"fit, middle part '{mid}': fit, then {', '.join(want)}", names()[1:] == want, names())
w.xrd_mid.setCurrentText(sp.FIT_MIDDLE[2]); w.xrd_mid.activated.emit(w.xrd_mid.currentIndex()); app.processEvents()
pk = fit.spec["panels"][1]
check("peaks with labels: one line per listed peak at its calculated height, coloured per phase, the strong ones labelled with the phase letter",
      len(pk["curves"]) >= 4 and pk.get("placed") and all(t_.replace("+", "").isalpha() for _, _, t_, _, _ in pk["placed"]), [q[2] for q in pk.get("placed", [])][:8])
check("... a phase with zero calculated height has no line (alite)", "A" not in {c["label"] for c in pk["curves"]})
check("the Origin path draws the same panels (curves with gaps, labels placed)", all(np.isnan(c["y"]).any() for c in pk["curves"]))
# ---------------------------------------------------------------- the XRD bar
check("XRD graph: 'Zoomed part', its range and 'middle part' beside Zoom / Pan", w.xrd_zoom.isVisibleTo(w) and w.xrd_zoom_rng.isVisibleTo(w) and w.xrd_mid.isVisibleTo(w))
w.list.setCurrentRow(w.items.index(xy)); app.processEvents()
check("other graphs: not shown (the zoom switch is for XRD only)", not w.xrd_zoom.isVisibleTo(w) and not w.xrd_mid.isVisibleTo(w))
w.list.setCurrentRow(w.items.index(fit)); app.processEvents()
# ---------------------------------------------------------------- editing on the graph
w.canvas.draw(); rr = w.canvas.get_renderer()
class Ev:
    def __init__(s, x, y, dbl=False, button=1): s.x, s.y, s.button, s.dblclick, s.inaxes = x, y, button, dbl, None
def centre(artist):
    b = artist.get_window_extent(rr); return (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2
ax0 = w.fig.axes[0]
obs = next(l for l in ax0.get_lines() if l.get_label() == "Observed")
xd, yd = obs.get_xdata(), obs.get_ydata(); k = int(np.argmax(yd)); px, py = ax0.transData.transform((xd[k], yd[k]))
r = rb.on_click(Ev(px, py))
check("click on a curve: Lines opens with that curve chosen, a frame round it", r == "curve" and rb.tabText(rb.currentIndex()) == "Lines" and rb.curve.currentText() == "Observed"
      and any(p_.get_gid() == "chosen" for p_ in list(w.fig.patches) + list(w.fig.artists)), (r, rb.curve.currentText()))
yl = next(a.yaxis.label for a in w.fig.axes if a.yaxis.label.get_text())
QInputDialog.getText = staticmethod(lambda *a, **k: ("Intensity (counts s^{-1})", True))
done = rb.on_double(Ev(*centre(yl), dbl=True))
check("double click on the y axis title: type it again, it is changed in the graph", done and fit.fmt.get("ytitle") == "Intensity (counts s^{-1})" and "s$^{−1}$" in next(a.yaxis.label for a in w.fig.axes if a.yaxis.label.get_text()).get_text())
w.canvas.draw(); rr = w.canvas.get_renderer()
yl = next(a.yaxis.label for a in w.fig.axes if a.yaxis.label.get_text())
cx, cy = centre(yl); dpr = w.canvas.devicePixelRatioF()
m = QMenu(); rb.menu_items(m, QPoint(int(cx / dpr), int(w.canvas.height() - cy / dpr)))
texts = [a.text() for a in m.actions() if a.text()]
check("right click on that title: edit, bigger, smaller, bold, italic, colour, back to the app's look; zoom on/off (XRD)",
      "Edit the text… (double click)" in texts and "Bigger letters" in texts and "Bold on / off" in texts and "Colour…" in texts and any(t.startswith("Zoomed part:") for t in texts), texts)
next(a for a in m.actions() if a.text() == "Bigger letters").trigger(); app.processEvents()
check("'Bigger letters' works", (fit.fmt.get("text") or {}).get("axis_titles", {}).get("size", 0) > 0)
# drag the zoomed part
w.canvas.draw()
iax = next(c for a in w.fig.axes for c in getattr(a, "child_axes", []))
ib = iax.get_window_extent(); parent = next(a for a in w.fig.axes if iax in getattr(a, "child_axes", [])).get_window_extent()
sx, sy = (ib.x0 + ib.x1) / 2, (ib.y0 + ib.y1) / 2
rb.on_click(Ev(sx, sy)); rb.on_motion(Ev(sx - 0.4 * parent.width, sy - 0.05 * parent.height)); rb.on_release(Ev(sx - 0.4 * parent.width, sy - 0.05 * parent.height)); app.processEvents()
ir = fit.fmt.get("inset_rect")
check("drag the zoomed part to the left: it stays where you put it", ir is not None and ir[0] < 0.3, ir)
rb.undo(); check("... undo puts it back", fit.fmt.get("inset_rect") is None)
w.modes.button(0).setChecked(True)
check("with Zoom (or Pan, Select range) on, a click is for zooming, not for editing", rb.on_click(Ev(px, py)) is None)
w.modes.button(0).setChecked(False)
# ---------------------------------------------------------------- the ribbon as in Word, in the top bar
check("the formatting ribbon belongs to Workspace: its tabs above its buttons, under the one top bar (File is the top bar's File menu)",
      rb.head.parentWidget() is rb and [rb.tabText(i) for i in range(rb.count())] == ["Home", "Insert", "Draw", "Design", "Layout", "Axes", "Lines"] and rb.isVisible())
w.go(1); app.processEvents(); check("... and is not shown in Analysis", not rb.isVisible()); w.go(0); app.processEvents()
check("no version on the screen above the graph (Help › About has it)", not any(("Version " + sp.VERSION) in (l.text() if hasattr(l, "text") else "") for l in w.findChildren(type(w.status)) if l.isVisible()))
rb.set_display(1); check("⌃: tabs only (the buttons fold away)", not rb.stack.isVisible() and rb.bar.isVisible())
rb.set_display(2); check("Ctrl+F1: hidden", not rb.isVisible())
rb.set_display(0); check("and back", rb.isVisible() and rb.stack.isVisible() and W.load_cfg().get("ribbon_mode") == 0)
hid = rb.customise(keep=set(rb.groups) - {"Home / Clipboard"})
check("Customise the ribbon: a group can be hidden (and it stays hidden at the next start)", hid == ["Home / Clipboard"] and not rb.groups["Home / Clipboard"].isVisibleTo(rb) and W.load_cfg().get("ribbon_hidden") == ["Home / Clipboard"])
rb.customise(keep=set(rb.groups))
w.list.setCurrentRow(w.items.index(fit)); app.processEvents()
look = dict((n, f) for n, _, f in __import__("workspace_ribbon").LOOKS)
rb.apply_look(look["Slides"], "Slides")
check("Design > Looks (as Word's Styles): 'Slides' gives large letters and heavy lines", fit.fmt["text"]["axis_titles"]["size"] == 16 and fit.fmt["lines"]["*"]["width"] == 2.5)
rb.apply_look(None, "App look"); check("'App look' takes the look back to the app's", not fit.fmt.get("text") and not fit.fmt.get("lines"))
from PySide6.QtGui import QFont
QFontDialog = __import__("PySide6.QtWidgets", fromlist=["QFontDialog"]).QFontDialog
f0 = QFont("Arial"); f0.setPointSizeF(13); f0.setBold(True)
QFontDialog.getFont = staticmethod(lambda *a, **k: (True, f0))
rb.role.setCurrentIndex(0); rb.font_dialog()
check("↘ of the Font group: the whole font dialog", fit.fmt["text"]["title"] == {"family": "Arial", "size": 13.0, "bold": True, "italic": False}, fit.fmt["text"].get("title"))
rb.role.setCurrentIndex(1); rb.step_size(+1); s1 = fit.fmt["text"]["axis_titles"]["size"]; rb.step_size(-1)
check("A↑ / A↓", fit.fmt["text"]["axis_titles"]["size"] == s1 - 1)
# ---------------------------------------------------------------- stack the graphs selected in the list (not ticked): the preview at once
f2 = mh.write_fit(D / "S2FIT.CSV", seed=5); w.load_sync([str(f2)]); app.processEvents()
fits = [i for i in w.singles if i.kind.startswith("Fit")]
w._tick_only([]); w.list.clearSelection()
for it_ in fits:
    w.list.item(w.items.index(it_)).setSelected(True)
r = w.group_ticked("stack"); app.processEvents()
cur = w.current()
check("XRD fits selected in the list (Ctrl / Shift + click), Stack: one stacked figure, shown at once in Workspace", r == "grouped" and getattr(cur, "mine", False) and cur.how == "stack" and len(cur.members) == 2 and w.pages.currentIndex() == 0)
# ---------------------------------------------------------------- a figure of several panels (Fig_C, Fig_D ...): the Panel bar
import pandas as pd
xr = np.linspace(10, 40, 500); profC = pd.DataFrame({"2theta_deg": xr, "Yobs": 100 + np.sin(xr) * 5, "Ycalc": 100 + np.sin(xr) * 5, "Ydiff": np.zeros_like(xr)})
frC = {"name": "G", "width_mm": 180, "height_mm": 90, "layout": {"rows": [1], "cols": [1, 1]}, "panels": [
    {"cell": [0, 0], "type": "rietveld", "letter": "(a)", "profile": "P", "x": "2theta_deg", "obs": "Yobs", "calc": "Ycalc", "diff": "Ydiff", "zoom": "P", "zoom_x": "2theta_deg", "zoom_xlim": [14, 16], "xlim": [10, 40]},
    {"cell": [0, 1], "type": "rietveld", "letter": "(b)", "profile": "P", "x": "2theta_deg", "obs": "Yobs", "calc": "Ycalc", "diff": "Ydiff", "zoom": "P", "zoom_x": "2theta_deg", "zoom_xlim": [14, 16], "xlim": [10, 40]}]}
recC = {"figures": [frC], "phases": []}
import paper_figures as pf
real_recipe_for, real_load_sheets = pf.recipe_for, pf.load_sheets
pf.recipe_for = lambda p: None; pf.load_sheets = lambda p: {"P": profC}
pathC = str(D / "composed.xlsx")
dC = dict(kind=sp.COMPOSED_KIND, name="G", nums=profC[["2theta_deg"]].rename(columns={"2theta_deg": "x"}), n={"x": "x"}, x="x", ys=[], units={}, t=lambda c: str(c), series=None, cat_only=False, _composed=(pathC, recC, frC))
cit = sp.Item(pathC, dC, []); cit.auto = "G"; cit.nfile = 1; cit.paper_name = "G"; cit.build(w.opt)
w.singles = w.singles + [cit]; w.regroup(); w.refresh_list(); w.list.setCurrentRow(w.items.index(cit)); app.processEvents()
check("a figure of several panels shows the Panel bar, one entry per panel", w.panel_combo.isVisibleTo(w) and [w.panel_combo.itemText(i) for i in range(w.panel_combo.count())] == ["(a)", "(b)"])
w.list.setCurrentRow(w.items.index(fit)); app.processEvents()
check("... hidden again for a graph that is not a figure of several panels", not w.panel_combo.isVisibleTo(w))
w.list.setCurrentRow(w.items.index(cit)); app.processEvents()
w.panel_combo.setCurrentText("(b)"); app.processEvents()
check("Panel bar reflects the selected panel's own settings (defaults: zoomed part, dots, difference row all on)", w.panel_zoom_cb.isChecked() and w.panel_dots.isChecked() and w.panel_diff.isChecked())
w.panel_dots.setChecked(False); app.processEvents()
check("switching one panel's observed curve to a line changes only that panel", cit.fmt == {"panels": {"(b)": {"obs_style": "line"}}}, cit.fmt)
w.panel_combo.setCurrentText("(a)"); app.processEvents()
check("... the other panel (selected again) still shows its own, unaffected default", w.panel_dots.isChecked())
r2 = rb.undo(); app.processEvents()
check("Undo (Ctrl+Z) takes the panel change off again", "Changed" in r2 and not cit.fmt, (r2, cit.fmt))
# ---------------------------------------------------------------- arrange a workbook of several figures
check("one graph from a file: nothing to arrange", w.arrange_workbook(it=fit) is None and "only one graph" in w.status.text())
frC2 = dict(frC, name="H"); dC2 = dict(dC, name="H", _composed=(pathC, recC, frC2))
cit2 = sp.Item(pathC, dC2, []); cit2.auto = "H"; cit2.nfile = 1; cit2.paper_name = "H"; cit2.build(w.opt)
w.singles = w.singles + [cit2]; w.regroup(); w.refresh_list()
check("the same file now gives two graphs: menu offers to arrange them", any("Arrange this workbook" in a.text() for a in w.menu_graphs(w.list.visualItemRect(w.list.item(w.items.index(cit))).center()).actions()))
from workspace_workbook import WorkbookDialog
real_exec = QDialog.exec
def fake_exec(self):                                        # move the second figure (H) to the top
    h = next(self.list.item(i) for i in range(self.list.count()) if self.list.item(i).data(Qt.UserRole).name == "H")
    r_ = self.list.row(h); self.list.takeItem(r_); self.list.insertItem(0, h)
    return QDialog.Accepted
QDialog.exec = fake_exec
r3 = w.arrange_workbook(it=cit)
QDialog.exec = real_exec
check("'Arrange this workbook's figures…' reorders them in Your graphs", r3 == "arranged" and [s.name for s in w.singles if s.path == pathC] == ["H", "G"], [s.name for s in w.singles if s.path == pathC])
check("... and 'Draw in Origin' / the paper set follow it (they draw from w.singles in this order)", w.singles.index(cit2) < w.singles.index(cit))
pf.recipe_for, pf.load_sheets = real_recipe_for, real_load_sheets
w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

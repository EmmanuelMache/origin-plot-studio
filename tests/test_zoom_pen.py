"""XRD: the zoomed part (inset) on or off - for every graph (Settings > XRD) or for one graph (ribbon, Analysis > XRD) - and drawing the
sketch freely with a pen, a finger on a touch screen or the mouse."""
import os, sys, tempfile, math
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
import smart_plots as sp, make_highscore as mh, sketch_pad as SK
D = Path(tempfile.mkdtemp())
XRD = str(ROOT / "origin_plot_app" / "examples_synthetic" / "xrd_raw.csv")
has = lambda it: any(p.get("inset") for p in it.spec["panels"])
fit = sp.load_file(str(mh.write_fit(D / "F1.CSV")))[0][0]
pat = sp.load_file(XRD)[0][0]
# ---------------------------------------------------------------- for every graph: Settings > XRD > Zoomed part
check("the choices: automatic, on every XRD pattern and fit, no inset (or a typed range)", sp.INSETS == ["Automatic on sample pages", "On every XRD pattern and fit", "No inset"])
fit.build({}, fit.kind); pat.build({}, pat.kind)
check("Automatic: the fit has its zoom, a single pattern has none (as before)", has(fit) and not has(pat))
o = {"inset": "On every XRD pattern and fit"}; fit.build(o, fit.kind); pat.build(o, pat.kind)
check("On every XRD pattern and fit: the pattern gets a zoom too, chosen by the app", has(pat) and has(fit) and any("chosen by the app" in r for r in pat.det.get("_rec", [])), (pat.spec["panels"][0].get("inset") or {}).get("xlim"))
o = {"inset": "No inset"}; fit.build(o, fit.kind); pat.build(o, pat.kind)
check("No inset: no zoom on the fit nor on the pattern", not has(fit) and not has(pat))
# ---------------------------------------------------------------- for one graph: its format
fit.fmt = {"zoom_off": True}; fit.build({}, fit.kind)
check("one graph, zoom off: no zoom although the setting is automatic", not has(fit))
pat.fmt = {"zoom_on": True}; pat.build({}, pat.kind)
check("one pattern, zoom on: it gets the app's region", has(pat))
pat.fmt = {"zoom": [25, 35]}; pat.build({}, pat.kind)
check("one pattern, your range 25-35", tuple(pat.spec["panels"][0]["inset"]["xlim"]) == (25.0, 35.0))
fit.fmt = {}; pat.fmt = {}
# ---------------------------------------------------------------- free-hand strokes
def loop(x, y, w, h, n=80, jit=3, seed=0):
    r = np.random.default_rng(seed); t = np.linspace(0, 1, n); pts = []
    for u in t:                                          # a hand-drawn rectangle: round the four sides, ending near the start
        s_ = u * 4
        if s_ < 1: q = (x + w * s_, y)
        elif s_ < 2: q = (x + w, y + h * (s_ - 1))
        elif s_ < 3: q = (x + w * (3 - s_), y + h)
        else: q = (x, y + h * (4 - s_))
        pts.append((q[0] + r.normal(0, jit), q[1] + r.normal(0, jit)))
    return pts
wave = [(x, 420 + 60 * math.sin(x / 50)) for x in np.linspace(130, 950, 60)]
items = SK.classify_strokes([loop(100, 100, 850, 500), loop(620, 120, 300, 200, seed=1), loop(120, 115, 60, 35, seed=2), wave])
kinds = sorted(i["type"] for i in items)
check("free-hand: a big closed shape = graph box, closed inside = zoom, a small one in a corner = legend, a line = curve", kinds == ["box", "curve", "legend", "zoom"], kinds)
d = SK.read_sketch(items)
g = d["graphs"][0]
check("... read as one graph with the zoom top right and the legend top left", d["layout"] == "single" and g["inset_rect"][0] > 0.5 and g["legend_loc"] == "upper left", (g["inset_rect"], g["legend_loc"]))
two = SK.read_sketch(SK.classify_strokes([loop(60, 100, 480, 400), loop(580, 100, 480, 400, seed=3)]))
check("two frames drawn side by side: a figure of 2 columns", two["layout"] == "figure" and two["cols"] == 2)
tiny = SK.classify_strokes([loop(10, 10, 40, 30)])
check("a tiny closed scribble outside every frame is not taken for a graph", not tiny)
# ---------------------------------------------------------------- in the window
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, workspace_tools as WT
w = W.Workspace([]); w.show(); app.processEvents()
xrd_rows = [r for g_, rows in WT.analysis_tree() if g_ == "XRD" for r in rows]
check("Analysis > XRD: 'Zoomed part (inset): on or off'", any(r[0].startswith("Zoomed part") and r[3] == {"do": "zoom"} for r in xrd_rows))
check("Settings > XRD has 'Zoomed part (inset)' (a typed range works too)", "inset" in w.set_fields and w.set_fields["inset"].isEditable())
w.load_sync([str(D / "F1.CSV"), XRD]); app.processEvents()
f_ = next(i for i in w.singles if i.kind.startswith("Fit")); p_ = next(i for i in w.singles if i.kind == "XRD")
w.list.setCurrentRow(w.items.index(f_)); app.processEvents()
rb = w.ribbon
check("for an XRD graph, beside Zoom / Pan: 'Zoomed part' (on), its range, and pattern / fit", w.xrd_zoom.isVisibleTo(w) and w.xrd_zoom.isChecked() and w.xrd_view.isVisibleTo(w))
check("... and not in the ribbon at the top", not any("Zoom" in rb.tabText(i) for i in range(rb.count())) and not hasattr(rb, "zoom"))
w.xrd_zoom.setChecked(False); app.processEvents()
check("untick 'Zoomed part': the fit on show has no zoom (Ctrl+Z brings it back)", not has(f_) and f_.fmt.get("zoom_off"))
rb.undo(); check("... undo", has(f_))
w.list.setCurrentRow(w.items.index(p_)); app.processEvents()
w.xrd_zoom_rng.setText("26-36"); w.xrd_zoom_rng.returnPressed.emit(); app.processEvents()
check("the pattern: zoom on with a typed range (Enter)", has(p_) and tuple(p_.spec["panels"][0]["inset"]["xlim"]) == (26.0, 36.0))
w._tick_only([f_, p_])
m = w.tools.zoom_ticked(1)
check("Analysis > XRD > Zoomed part: off for the ticked graphs", not has(f_) and not has(p_), m)
m = w.tools.zoom_ticked(0)
check("... on for the ticked graphs (the app's region)", has(f_) and has(p_), m)
w.set_fields["inset"].setCurrentText("No inset"); w.apply_settings()
check("Settings > XRD > Zoomed part 'No inset': graphs that follow the setting lose it; your own 'on' stays", has(f_) and f_.fmt.get("zoom_on"))
# the pen in the pad: a real mouse drag (a pen or a finger arrives the same way)
dlg = rb.sketch(); dlg.resize(1200, 760); app.processEvents()
vp = dlg.pad.viewport()
def drag(pts):
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, pts[0]); [QTest.mouseMove(vp, q) for q in pts[1:]]; QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, pts[-1]); app.processEvents()
sc_ = lambda x, y: dlg.pad.mapFromScene(x, y)
drag([sc_(x, y) for x, y in loop(100, 100, 850, 500, jit=0)])
drag([sc_(x, y) for x, y in [(x, 420 + 60 * math.sin(x / 50)) for x in np.linspace(130, 950, 40)]])
dz = dlg.update_reading()
check("drawing with the mouse (pen / finger): a frame and a curve are read as one graph with one curve", dz["layout"] == "single" and len(dz["graphs"][0]["curves"]) == 1, dlg.read.toPlainText())
n0 = len([i for i in dlg.pad.sc.items() if i.data(0)])
QTest.keyClick(dlg.pad, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
check("Ctrl+Z takes back the last stroke", len([i for i in dlg.pad.sc.items() if i.data(0)]) == n0 - 1)
dlg.pad.tool = "erase"; QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, sc_(100, 300)); app.processEvents()
check("⌫ Erase: a touch on the frame removes it", not [i for i in dlg.pad.sc.items() if i.data(0)])
dlg.close(); w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

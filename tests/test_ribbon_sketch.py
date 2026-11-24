"""The ribbon at the top (File, Home, Graph, Axes, Lines, Insert: text, font, size, bold, italic, colours, superscript / subscript,
axis colour and weight, line colour and weight, ranges, undo / redo) and the sketch pad (a drawn design lays the graphs out)."""
import os, sys, tempfile, copy
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
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import to_rgb
import smart_plots as sp, origin_plot_app as opa, make_highscore as mh
import sketch_pad as SK
D = Path(tempfile.mkdtemp())

# ---------------------------------------------------------------- superscript / subscript
check("typed ^{..} and _{..} become real superscript and subscript (preview)", sp._mt("S_{BET} (m^{2} g^{-1})") == "S$_{BET}$ (m$^{2}$ g$^{−1}$)", sp._mt("S_{BET} (m^{2} g^{-1})"))
check("... and in Origin's notation", opa.otext("S_{BET} m^{2}") == "S\\-(BET) m\\+(2)")
check("Unicode sub/superscripts still work as before", sp._mt("cm⁻¹ CaCO₃") == "cm$^{−1}$ CaCO$_{3}$")

# ---------------------------------------------------------------- the format of one graph
it = sp.load_file(str(mh.write_fit(D / "S1FIT.CSV")))[0][0]
it.build({}, it.kind)
before = copy.deepcopy({k: it.spec[k] for k in ("title", "xname")})
x_before = np.array(it.spec["panels"][0]["curves"][0]["y"]).copy()
it.fmt = {"fit_view": sp.FIT_VIEWS[1], "title": "Sample S_{1}", "xtitle": "2θ (°)", "ytitle": "I (counts s^{-1})", "xlim": [20, 45], "legend": "off",
          "text": {"axis_titles": {"size": 14, "italic": True, "bold": False, "colour": "#8b0000", "family": "Arial"}, "numbers": {"size": 11, "colour": "Blue"}},
          "axis": {"colour": "#00008b", "width": 2.5}, "lines": {"Observed": {"colour": "#008000", "width": 3}, "*": {"width": 2}}}
it.build({}, it.kind)
check("titles, x range and legend from the format are in the graph", it.spec["title"] == "Sample S_{1}" and it.spec["xname"] == "2θ (°)" and it.spec["panels"][0]["yname"] == "I (counts s^{-1})"
      and tuple(it.spec["xlim"]) == (20, 45) and not it.spec["panels"][0]["legend"])
check("the data are not changed by any format", np.array_equal(np.array(it.spec["panels"][0]["curves"][0]["y"]), x_before))
fig = Figure(); FigureCanvasAgg(fig); sp.preview_figure(it.spec, fig=fig); fig.canvas.draw(); ax = fig.axes[0]
yl = ax.yaxis.label
check("axis titles: size 14, italic, not bold, dark red", yl.get_fontsize() == 14 and yl.get_fontstyle() == "italic" and yl.get_fontweight() in ("normal", 400) and to_rgb(yl.get_color())[0] > 0.5)
tl = [t for t in ax.get_yticklabels() if t.get_text()]
check("axis numbers: size 11, blue", tl and tl[0].get_fontsize() == 11 and to_rgb(tl[0].get_color())[2] > 0.8)
check("axis colour and weight", to_rgb(ax.spines["left"].get_edgecolor()) == (0, 0, 139 / 255) and ax.spines["left"].get_linewidth() == 2.5)
L = {l.get_label(): l for l in ax.get_lines() if len(l.get_xdata()) > 3}
check("line colour and weight per curve ('Observed' green 3 pt), the others 'all curves' 2 pt", to_rgb(L["Observed"].get_color()) == (0, 128 / 255, 0) and L["Observed"].get_linewidth() == 3 and L["Calculated"].get_linewidth() == 2)
pub = sp.publication_figure(it)
check("the publication files get the same look", any(to_rgb(l.get_color()) == (0, 128 / 255, 0) for a in pub.axes for l in a.get_lines()))
# Origin
cls = next(c for c in vars(opa).values() if isinstance(c, type) and hasattr(c, "titles") and hasattr(c, "plot"))
class Fake:
    nlabel = 0; fs = 1.0; jk = 1.0; st = opa.Style()
    def __init__(s): s.cmds = []; s.fmt = it.spec["fmt"]
    def ex(s, c): s.cmds.append(c)
    soft = ex
for n_ in ("_role", "_styled"): setattr(Fake, n_, getattr(cls, n_))
fk = Fake(); cls.titles(fk, "2θ (°)", "I (counts s^{-1})")
o = " ".join(fk.cmds)
check("Origin: axis titles with superscript, italic, size and colour", "\\i(I (counts s\\+(-1)))" in o and "yl.fsize=31" in o and "yl.color=color(139,0,0)" in o, o[:220])
check("Origin: the curve colour and weight", sp.fmt_curve(it.spec["fmt"], "Observed", (0, 0, 0), 1.5) == ((0, 128, 0), 3.0) and sp.fmt_curve(it.spec["fmt"], "Calculated", (224, 0, 0), 1.5) == ((224, 0, 0), 2.0))
it.fmt = {}; it.build({}, it.kind)
check("an empty format: the app's own look again", it.spec["title"] == before["title"] and it.spec["xname"] == before["xname"])
it.fmt = {"title": "kept"}
try:
    import json
    js = sp.session_dump([it], [], {})
    check("the format is saved with the session", '"fmt": {"title": "kept"}' in json.dumps(js, default=str))
except Exception as e:
    check("the format is saved with the session", False, e)
it.fmt = {}

# ---------------------------------------------------------------- reading a sketch
one = SK.read_sketch([{"type": "box", "rect": (100, 100, 800, 500)}, {"type": "zoom", "rect": (600, 120, 280, 200)}, {"type": "legend", "rect": (120, 120, 100, 60)},
                      {"type": "text", "pos": (500, 70), "text": "My title"}, {"type": "text", "pos": (500, 640), "text": "2θ (°)"},
                      {"type": "text", "pos": (50, 350), "text": "Counts"}, {"type": "text", "pos": (300, 400), "text": "note"}])
g = one["graphs"][0]
check("a sketch with one box: one graph, titles from where the text is (above, below, left), a note inside", one["layout"] == "single" and g["title"] == "My title"
      and g["xtitle"] == "2θ (°)" and g["ytitle"] == "Counts" and g["notes"] and g["notes"][0][2] == "note", one["lines"])
check("... the zoom box top right of the graph (axes fractions) and the legend top left", g["inset_rect"][0] > 0.6 and g["inset_rect"][1] > 0.5 and g["legend_loc"] == "upper left", (g["inset_rect"], g["legend_loc"]))
xs = np.linspace(150, 850, 30)
stk = SK.read_sketch([{"type": "box", "rect": (100, 100, 800, 500)}] + [{"type": "curve", "pts": [(x, 200 + 120 * k + 20 * np.sin(x / 40)) for x in xs]} for k in range(3)])
ovl = SK.read_sketch([{"type": "box", "rect": (100, 100, 800, 500)}] + [{"type": "curve", "pts": [(x, 350 + 150 * np.sin(x / 60 + k)) for x in xs]} for k in range(3)])
check("curves one above the other: stacked; crossing curves: overlaid", stk["graphs"][0]["how"] == "stack" and ovl["graphs"][0]["how"] == "overlay")
col = SK.read_sketch([{"type": "box", "rect": (100, 50 + 200 * k, 800, 200)} for k in range(3)])
grid = SK.read_sketch([{"type": "box", "rect": (60 + 520 * (k % 2), 60 + 320 * (k // 2), 480, 280)} for k in range(4)])
check("boxes touching one above the other: panels; a grid: a figure (a), (b) … of rows x columns", col["layout"] == "panels" and grid["layout"] == "figure" and (grid["rows"], grid["cols"]) == (2, 2))
check("a portrait pad: portrait page", SK.read_sketch([{"type": "box", "rect": (50, 50, 500, 400)}], (700, 1000))["orientation"] == "Portrait")
check("no box: it says what to draw", SK.read_sketch([])["layout"] == "none")
check("the zoom range for any graph: the busiest part of the data", (lambda z: z is not None and z[0] < 33 < z[1] and abs((z[0] + z[1]) / 2 - 33) < 1)(sp.auto_zoom(np.linspace(5, 70, 500), np.exp(-0.5 * ((np.linspace(5, 70, 500) - 33) / 1.5) ** 2) * 100 + 5)))

# ---------------------------------------------------------------- in the window: ribbon and sketch pad
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W
w = W.Workspace([]); w.show(); app.processEvents()
rb = w.ribbon
check("the ribbon, as in Word: Home, Insert, Draw, Design, Layout, Axes, Lines", [rb.tabText(i) for i in range(rb.count())] == ["Home", "Insert", "Draw", "Design", "Layout", "Axes", "Lines"])
files = [mh.write_fit(D / "A1.CSV", seed=1), mh.write_fit(D / "A2.CSV", seed=2), mh.write_fit(D / "A3.CSV", seed=3)]
w.load_sync([str(f) for f in files]); app.processEvents()
single = [i for i in w.singles]
w.list.setCurrentRow(w.items.index(single[0])); app.processEvents()
rb.role.setCurrentIndex(1); rb.which.setCurrentIndex(1); rb.edit.setText("Intensity (counts s^{-1})"); rb.apply_text()
check("Home: type the y axis title (Enter)", single[0].fmt.get("ytitle") == "Intensity (counts s^{-1})" and "s$^{−1}$" in w.fig.axes[0].yaxis.label.get_text())
rb.role.setCurrentIndex(0); rb.edit.setText("Calcium silicate"); rb.edit.setSelection(8, 8); rb.wrap("_")
check("X₂ on selected letters: subscript", single[0].fmt.get("title") == "Calcium_{ silicate}" or "_{" in str(single[0].fmt.get("title")), single[0].fmt.get("title"))
rb.role.setCurrentIndex(1); rb.size.setCurrentText("16"); rb._size(); rb.bold.setChecked(False); rb.style_text(bold=False); rb.pick_colour("text", "#8b0000")
st = single[0].fmt["text"]["axis_titles"]
check("Home: size, bold off and colour of the axis titles", st == {"size": 16.0, "bold": False, "colour": "#8b0000"}, st)
rb.pick_colour("axis", "#00008b"); rb.axw.setValue(2.0); rb.set_axis(width=2.0)
rb.curve.setCurrentText("Observed"); rb.pick_colour("line", "#008000"); rb.lw.setValue(3.0); rb.set_line(width=3.0)
check("Axes and Lines: axis colour and weight, colour and weight of one curve", single[0].fmt["axis"] == {"colour": "#00008b", "width": 2.0} and single[0].fmt["lines"] == {"Observed": {"colour": "#008000", "width": 3.0}})
rb.x0.setText("25"); rb.x1.setText("40"); rb.apply_ranges()
check("Axes: the x range", single[0].fmt.get("xlim") == [25.0, 40.0] and tuple(w.fig.axes[0].get_xlim()) == (25.0, 40.0), w.fig.axes[0].get_xlim())
rb.undo(); u1 = single[0].fmt.get("xlim"); rb.redo(); r1 = single[0].fmt.get("xlim")
check("Undo and redo (Ctrl+Z / Ctrl+Y)", u1 is None and r1 == [25.0, 40.0])
rb.legend.setCurrentIndex(2); rb.set_fmt(legend="off")
check("Graph: legend off", single[0].fmt.get("legend") == "off")
class Ev:
    def __init__(s, x, y): s.x, s.y, s.button, s.dblclick, s.inaxes = x, y, 1, False, None
w.canvas.draw(); lab = next(a.xaxis.label for a in w.fig.axes if a.xaxis.label.get_text()); bb = lab.get_window_extent(w.canvas.get_renderer())
r = rb.on_click(Ev((bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2))
check("click on the x axis title in the graph: it is chosen in the ribbon, ready to type", r == "axis_titles" and rb.which.currentIndex() == 0 and rb.edit.text() == str(single[0].spec["xname"]))
rb.reset(); check("Reset look: the app's own look again", not single[0].fmt)
# the sketch pad
d = rb.sketch(); app.processEvents()
check("Insert > Sketch a design… opens the pad with Graph, Zoom, Curve, Text, Legend and a photo to trace", d.isVisible() and [t[0] for t in SK.TOOLS] == ["pen", "select", "erase", "box", "zoom", "curve", "text", "legend"] and d.pad.tool == "pen")
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPen, QImage, QColor
for rect, kind in (((80, 80, 900, 520), "box"), ((640, 100, 320, 200), "zoom")):
    it_ = d.pad.sc.addRect(QRectF(*rect), QPen()); it_.setData(0, kind)
t_ = d.pad.sc.addText("Sample A"); t_.setPos(480, 30); t_.setData(0, "text")
dz = d.update_reading()
check("the pad reads what was drawn and says it before anything is changed", dz["layout"] == "single" and dz["graphs"][0]["title"] == "Sample A" and dz["graphs"][0]["inset_rect"] and "zoomed part" in d.read.toPlainText(), d.read.toPlainText())
img = QImage(200, 120, QImage.Format_RGB32); img.fill(QColor("white")); img.save(str(D / "sketch.png"))
check("a photo of a paper sketch can be put behind to trace", d.set_photo(str(D / "sketch.png")) and d.pad.photo is not None)
w._tick_only([single[1]]); w.list.setCurrentRow(w.items.index(single[1]))
m = d.apply(); app.processEvents()
ins = (single[1].spec["panels"][0].get("inset") or {})
check("'Lay out the ticked graphs like this': title and the zoom where it was drawn", single[1].fmt.get("title") == "Sample A" and ins.get("curves") and ins.get("rect", (0,))[0] > 0.6, (m, ins.get("rect")))
# several boxes in a grid -> a panel figure
d.clear()
for k in range(2):
    b_ = d.pad.sc.addRect(QRectF(60 + 520 * k, 100, 480, 400), QPen()); b_.setData(0, "box")
w._tick_only(single[:2]); nb = len(w.boards)
m2 = d.apply(); app.processEvents()
check("two boxes side by side, two graphs ticked: a panel figure (a), (b) with 2 columns", len(w.boards) == nb + 1 and w.boards[-1].cols == 2 and len(w.boards[-1].members) == 2, m2)
# curves stacked in one box with three graphs ticked -> one stacked figure
d.clear(); b_ = d.pad.sc.addRect(QRectF(80, 80, 900, 520), QPen()); b_.setData(0, "box")
from PySide6.QtGui import QPainterPath
for k in range(3):
    pth = QPainterPath(); pts = [(x, 160 + 140 * k + 15 * np.sin(x / 30)) for x in np.linspace(120, 940, 40)]
    pth.moveTo(*pts[0]); [pth.lineTo(*q) for q in pts[1:]]
    c_ = d.pad.sc.addPath(pth, QPen()); c_.setData(0, "curve"); c_.setData(1, pts)
w._tick_only(single)
m3 = d.apply(); app.processEvents()
check("three curves one above the other, three graphs ticked: one stacked figure", any(getattr(c, "mine", False) and c.how == "stack" and len(c.members) == 3 for c in w.combined), m3)
d.close(); w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

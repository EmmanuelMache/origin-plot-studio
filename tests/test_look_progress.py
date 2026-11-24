"""Graph settings > Size and look (orientation, letter size, font weight, text colour, line colour, curve and axis weights) and the
moving bar while the app reads, draws and saves."""
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
from PySide6.QtWidgets import QApplication
from matplotlib.text import Text
from matplotlib.colors import to_rgb
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, smart_plots as sp, make_highscore as mh
import origin_plot_app as opa
d = Path(tempfile.mkdtemp())
f = mh.write_fit(d / "S1FIT.CSV")
w = W.Workspace([]); w.show(); app.processEvents()
check("Size and look has orientation, letters, font weight, text colour and line colour (with curve and axis weights)",
      all(hasattr(w, a) for a in ("orient", "fscale", "fweight", "tcolour", "ccolour", "curvew", "axisw")))
w.load_sync([str(f)]); app.processEvents()
for i_ in w.singles:
    if i_.kind.startswith("Fit"): i_.fmt = {"fit_view": sp.FIT_VIEWS[1]}; i_.build(w.opt, i_.kind)      # the whole fit (calculated curve in red)
w.list.setCurrentRow(w.items.index(next(i for i in w.items if getattr(i, "kind", "").startswith("Fit") and i in w.singles))); app.processEvents()
bold0 = sum(t.get_fontweight() in ("bold", 700) for t in w.fig.findobj(Text) if t.get_text())
w.fweight.setCurrentText("Normal"); w.ccolour.setCurrentText("Dark blue"); w.tcolour.setCurrentText("#8b0000"); w.fscale.setCurrentText("120 %")
w.orient.setCurrentText("Portrait")
look = w.look_changed(); app.processEvents()
ts = [t for t in w.fig.findobj(Text) if t.get_text()]
check("font weight Normal: no bold letters left in the graph", bold0 > 0 and not any(t.get_fontweight() in ("bold", 700) for t in ts), bold0)
w.canvas.draw(); vis = [t for t in w.fig.findobj(Text) if t.get_text() and t.get_visible()]
check("text colour (typed #8b0000): no black text left, the axis numbers included", vis and not any(to_rgb(t.get_color()) == (0, 0, 0) for t in vis)
      and any(abs(to_rgb(t.get_color())[0] - 0x8b / 255) < 0.01 for t in vis))
from matplotlib.figure import Figure
f2 = Figure(); ax2 = f2.add_subplot(); ax2.text(0, 0, "phase", color=(0, 0, 0.5)); sp.apply_look(f2)
check("... coloured labels keep their colours", to_rgb(ax2.texts[0].get_color()) == (0, 0, 0.5))
lines = [l for ax in w.fig.axes for l in ax.get_lines() if len(l.get_xdata()) > 3]
check("line colour Dark blue: the observed curve (black before) is dark blue, the red calculated curve stays red",
      any(to_rgb(l.get_color()) == (0, 0, 139 / 255) for l in lines) and any(to_rgb(l.get_color())[0] > 0.8 for l in lines))
check("orientation is saved and used for the pages", w.opt.get("orientation") == "Portrait" and W.load_cfg().get("orientation") == "Portrait")
check("the look is saved for the next start", W.load_cfg().get("font_weight") == "Normal" and W.load_cfg().get("curve_colour") == "Dark blue")
w.curvew.setText("3"); w.look_changed(); app.processEvents()
lw = max(l.get_linewidth() for ax in w.fig.axes for l in ax.get_lines() if len(l.get_xdata()) > 3)
check("Curve (pt) is used in the preview too", lw >= 3.0, lw)
# Origin: the same choices
o = opa.Origin.__new__(opa.Origin) if hasattr(opa, "Origin") else None
mo = opa.MockOrigin()
class Fake:
    def __init__(s): s.cmds = []; s.nlabel = 0; s.fs = 1.0; s.jk = 1.0
    def ex(s, c): s.cmds.append(c)
    soft = ex
cls = next(c for c in vars(opa).values() if isinstance(c, type) and hasattr(c, "text") and hasattr(c, "style") and hasattr(c, "plot"))
Fake._role = cls._role; Fake.fmt = {}
fk = Fake(); cls.text(fk, "abc", 1, 1, 15, (0, 0, 0), bold=True); cls.style(fk, "d", (0, 0, 0), 1.5)
txt = " ".join(fk.cmds)
check("Origin gets the same look: no bold, the text colour, the line colour for black curves", "\\b(" not in txt and "color(139,0,0)" in txt and "-c color(0,0,139)" in txt, txt[:200])
sp.LOOK.update(font_weight=sp.FONT_WEIGHTS[0], text_colour="Automatic", curve_colour="Automatic", font_scale=1.0)
# the moving bar
check("the bar is hidden when nothing runs", not w.pbar.isVisible())
w.busy_on("Drawing"); app.processEvents()
check("it runs while the app works (no number yet: it moves)", w.pbar.isVisible() and w.pbar.maximum() == 0)
w.set_status("Drawing graph 3 of 10 in Origin: X")
check("'graph 3 of 10': it fills up", w.pbar.maximum() == 10 and w.pbar.value() == 3)
w.busy_off()
check("and goes away when done", not w.pbar.isVisible())
seen = []
w.busy_on = (lambda f0: (lambda what="": (seen.append(what), f0(what))[1]))(w.busy_on)
w.load_sync([str(mh.write_fit(d / "S2FIT.CSV", seed=3))]) if False else None
w.load([str(mh.write_fit(d / "S3FIT.CSV", seed=4))])
import time; t0 = time.time()
while w.thread is not None and time.time() - t0 < 60: app.processEvents(); time.sleep(0.02)
app.processEvents()
check("reading files shows it too, and it stops after", any("Reading" in s for s in seen) and not w.pbar.isVisible(), seen)
w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

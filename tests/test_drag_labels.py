"""Drag a peak label (or a curve's name in a stacked figure) to where you want it: it stays there, also in Origin; undo; put back."""
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
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtCore import QPoint
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, smart_plots as sp, make_highscore as mh
D = Path(tempfile.mkdtemp())
w = W.Workspace([]); w.resize(1600, 900); w.show(); app.processEvents()
w.load_sync([str(mh.write_fit(D / "S1FIT.CSV")), str(mh.write_peaklist(D / "S1.CSV")), str(mh.write_fit(D / "S2FIT.CSV", seed=3))]); app.processEvents()
fit = next(i for i in w.singles if i.kind.startswith("Fit") and i.spec["panels"][0].get("placed"))
w.list.setCurrentRow(w.items.index(fit)); app.processEvents(); w.canvas.draw()
rb = w.ribbon
class Ev:
    def __init__(s, x, y, button=1): s.x, s.y, s.button, s.dblclick, s.inaxes = x, y, button, False, None
def art_of(q):
    ax = w.fig.axes[0]
    return next(t for t in ax.texts if t.get_text() == sp._lb(q[2]) and abs(t.get_position()[0] - q[3]) < 1e-9 and abs(t.get_position()[1] - q[4]) < 1e-9)
q0 = fit.spec["panels"][0]["placed"][0]; n0 = len(fit.spec["panels"][0]["placed"])
a = art_of(q0); bb = a.get_window_extent(w.canvas.get_renderer()); x, y = (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2
check("press on a peak label: it can be dragged", rb.on_click(Ev(x, y)) == "label")
rb.on_motion(Ev(x + 60, y + 40)); rb.on_release(Ev(x + 60, y + 40)); app.processEvents()
q1 = fit.spec["panels"][0]["placed"][0]
check("dropped: the label stays where you put it (its peak, its text and the other labels are unchanged)",
      (q1[0], q1[1], str(q1[2])) == (q0[0], q0[1], str(q0[2])) and q1[3] > q0[3] and q1[4] > q0[4] and len(fit.spec["panels"][0]["placed"]) == n0
      and fit.spec["panels"][0]["placed"][1:] == [tuple(q) for q in fit.spec["panels"][0]["placed"][1:]], (q0[3:], q1[3:]))
check("it is kept with the graph (and so in a saved session and in Origin, which read the same positions)", len(fit.fmt["moved"]) == 1)
fit.build(w.opt, fit.kind)
check("it survives the graph being drawn again", fit.spec["panels"][0]["placed"][0][3:] == q1[3:])
w.draw(); w.canvas.draw(); a = art_of(q1); bb = a.get_window_extent(w.canvas.get_renderer())
m = QMenu(); dpr = w.canvas.devicePixelRatioF(); rb.menu_items(m, QPoint(int((bb.x0 + bb.x1) / 2 / dpr), int(w.canvas.height() - (bb.y0 + bb.y1) / 2 / dpr)))
texts = [x_.text() for x_ in m.actions() if x_.text()]
check("right click on it: 'Put this label back' and 'Put all moved labels back'", "Put this label back" in texts and "Put all moved labels back" in texts, texts)
rb.undo(); app.processEvents()
check("Ctrl+Z puts it back", fit.spec["panels"][0]["placed"][0][3:] == q0[3:] and not fit.fmt.get("moved"))
rb.set_fmt(moved=None)
w.canvas.draw(); a = art_of(fit.spec["panels"][0]["placed"][0]); bb = a.get_window_extent(w.canvas.get_renderer()); x, y = (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2
rb.on_click(Ev(x, y)); r = rb.on_release(Ev(x, y))
check("a click without a drag still chooses the label (font, size, colour in Home)", r == "labels" and not fit.fmt.get("moved"))
# the name of a curve in a stacked figure
stk = next((c for c in w.combined if c.how == "stack"), None)
if stk is None:
    w._tick_only([i for i in w.singles if i.kind.startswith("Fit")]); w.group_ticked("stack"); stk = next(c for c in w.combined if c.how == "stack")
w.list.setCurrentRow(w.items.index(stk)); app.processEvents(); w.canvas.draw()
t0 = stk.spec["panels"][0]["texts"][0]
a = next(t for t in w.fig.axes[0].texts if t.get_text() == str(t0[2])); bb = a.get_window_extent(w.canvas.get_renderer()); x, y = (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2
rb.on_click(Ev(x, y)); rb.on_motion(Ev(x - 120, y + 10)); rb.on_release(Ev(x - 120, y + 10)); app.processEvents()
stk2 = w.current(); t1 = stk2.spec["panels"][0]["texts"][0]
check("stacked figure: the name of a curve can be dragged too", t1[0] < t0[0] and t1[2] == t0[2], (t0[:2], t1[:2]))
w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

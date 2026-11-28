"""Peak labels on or off - every graph that has labels on its peaks can be drawn with them or without:
an XRD pattern, a thermal graph, a figure made of several graphs, a figure of a workbook (per panel and for all panels),
and the graphs of Analysis. Hidden labels are not lost: the peaks stay in Results, other graphs keep theirs, and the
drawing sent to Origin follows the switch. All data here is synthetic (made by this test)."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
os.environ["OPS_SETTINGS_FILE"] = str(Path(tempfile.mkdtemp()) / "settings_modern.json"); os.environ["OPS_PRIVATE_DIR"] = tempfile.mkdtemp()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "tests"))
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
import numpy as np, pandas as pd
import smart_plots as sp, make_highscore as mh, paper_figures as pf
from opstudio import origin as OG, side_tables as SD
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W
D = Path(tempfile.mkdtemp())
src = pd.read_csv(ROOT / "origin_plot_app" / "examples_synthetic" / "xrd_raw.csv")            # a synthetic pattern of the examples, written twice under generated names
scan_a, scan_b = D / "generated_scan_one.csv", D / "generated_scan_two.csv"; src.to_csv(scan_a, index=False)
src2 = src.copy(); src2.iloc[:, 1] = src2.iloc[:, 1] * 0.7 + 5; src2.to_csv(scan_b, index=False)
files = [scan_a, scan_b, ROOT / "origin_plot_app" / "examples_synthetic" / "strength.csv", ROOT / "origin_plot_app" / "examples_synthetic" / "tga.xlsx"]
w = W.Workspace([]); w.resize(1500, 950); w.show(); app.processEvents()
w.opt["xrd_labels"] = sp.XRD_LABELS[1]                       # labels suggested from the phase library: names on the peaks of both patterns
w.load_sync([str(f) for f in files]); app.processEvents()
rb = w.ribbon
fits = [i for i in w.singles if i.kind == "XRD"]; fit = fits[0]
plain = next(i for i in w.singles if not i.kind.startswith(("Fit", "XRD", "TGA")) and not sp.has_peak_labels(i))
def fmt(it): return getattr(it, "fmt", None) or {}
def placed(it):
    out = []
    for p in sp.all_panels(it.spec):
        out += list(p.get("placed") or []) + list(p.get("placed_below") or []) + list((p.get("y2") or {}).get("placed") or []) + list((p.get("inset") or {}).get("placed") or [])
    return out
def shown(it):
    w.list.setCurrentRow(w.items.index(it)); app.processEvents()
def drawn_texts():
    return [t.get_text() for a in w.fig.axes for a_ in [a] + list(a.child_axes) for t in a_.texts if t.get_text().strip()]

# ---------------------------------------------------------------- one XRD graph
shown(fit)
texts0 = {q[2] for q in placed(fit)}; top0 = fit.spec["panels"][0]["ylim"][1]; n0 = len(placed(fit))
check("an XRD graph with labels on its peaks: a 'Peak labels' box beside Zoom / Pan, ticked", n0 > 0 and sp.has_peak_labels(fit) and w.peak_labels_cb.isVisibleTo(w) and w.peak_labels_cb.isChecked(), n0)
check("... its labels are in the picture", texts0 and texts0 <= set(drawn_texts()), sorted(texts0)[:5])
w.peak_labels_cb.setChecked(False); app.processEvents()
check("untick it: this graph is drawn WITHOUT its peak labels - none on the peaks, none in the zoomed part", fmt(fit) == {"peak_labels": False} and placed(fit) == [] and not (texts0 & set(drawn_texts())), (fmt(fit), len(placed(fit))))
check("... no empty room is kept above the curve for them (the page is laid out again)", fit.spec["panels"][0]["ylim"][1] < top0, (fit.spec["panels"][0]["ylim"][1], top0))
check("... the curve itself is unchanged, and the labels are kept aside (the peaks are not lost)", len(fit.spec["panels"][0]["curves"]) >= 1 and len(sp.labels_of(fit.spec["panels"][0])) > 0 and sp.has_peak_labels(fit))
check("... the box stays there (unticked), so they can be put back", w.peak_labels_cb.isVisibleTo(w) and not w.peak_labels_cb.isChecked())
other = fits[1]
check("another graph keeps its labels: the switch is each graph's own", len(placed(other)) > 0 and not getattr(other, "fmt", None))
w.peak_labels_cb.setChecked(True); app.processEvents()
check("tick it again: the labels are back as they were", not fmt(fit) and {q[2] for q in placed(fit)} == texts0 and abs(fit.spec["panels"][0]["ylim"][1] - top0) < 1e-9)
rb.set_peak_labels(False); app.processEvents(); r_u = rb.undo(); app.processEvents()
check("Undo (Ctrl+Z) takes the change off", "Changed" in str(r_u) and not fmt(fit) and len(placed(fit)) == n0, (r_u, fmt(fit)))
shown(plain)
check("a graph that has no peak labels: no box (nothing to switch)", not w.peak_labels_cb.isVisibleTo(w) and not sp.has_peak_labels(plain))

# ---------------------------------------------------------------- a thermal graph: labels on the DTG steps, results kept
tga = next((i for i in w.singles if i.kind.startswith("TGA") and sp.has_peak_labels(i)), None)
check("the synthetic TGA / DTG graph has labels on its steps", tga is not None)
if tga is not None:
    shown(tga); res0 = None if tga.results is None else tga.results.to_csv(); nt = len(placed(tga))
    rb.set_peak_labels(False); app.processEvents()
    check("TGA / DTG without labels: none drawn (also none on the second axis), the result table is the same", nt > 0 and placed(tga) == [] and (None if tga.results is None else tga.results.to_csv()) == res0, (nt, len(placed(tga))))
    rb.set_peak_labels(True); app.processEvents()
    check("... and with them again", len(placed(tga)) == nt)

# ---------------------------------------------------------------- a figure made of several graphs follows its own switch
st = next(x for x in w.items if isinstance(x, sp.Combined) and x.how == "stack" and x.kind == "XRD"); r = "grouped"; shown(st)
ns = len(placed(st))
check("two XRD graphs stacked: the figure carries the labels of both", r == "grouped" and st.how == "stack" and ns > 0 and w.peak_labels_cb.isVisibleTo(w) and w.peak_labels_cb.isChecked(), ns)
rb.set_peak_labels(False, fit); app.processEvents(); st = next(x for x in w.items if isinstance(x, sp.Combined) and x.how == "stack" and x.kind == "XRD"); st.build(); app.processEvents()
check("one of its graphs has its labels switched off: the stacked figure still shows the labels of both (its own switch decides)", len(placed(st)) == ns and placed(fit) == [], (len(placed(st)), ns))
shown(st); w.peak_labels_cb.setChecked(False); app.processEvents(); st = w.current()
check("the stacked figure without labels: none drawn, the traces closer together (no room kept for labels)", placed(st) == [] and fmt(st).get("peak_labels") is False, len(placed(st)))
check("... the graph that had its labels on still has them, the one switched off is still off", len(placed(other)) > 0 and placed(fit) == [])
rb.set_peak_labels(True, st); rb.set_peak_labels(True, fit); app.processEvents()

# ---------------------------------------------------------------- a figure of a workbook: per panel, and all panels
xr = np.linspace(10, 40, 600)
def prof(k):
    y = 100 + sum(h * np.exp(-(xr - p_) ** 2 / 0.02) for p_, h in ((15.0 + k, 900), (22.0, 500 + 100 * k), (31.0 - k, 700)))
    return pd.DataFrame({"2theta_deg": xr, "Yobs": y, "Ycalc": y * 0.99, "Ydiff": y * 0.01})
labs = pd.DataFrame({"Sample": ["Alpha"] * 2 + ["Beta"] * 3, "Label": ["KA1", "KA2", "QB1", "QB2", "QB3"], "2θ (°)": [15.0, 22.0, 16.0, 22.0, 30.0],
                     "Peak top (counts)": [1000, 600, 1000, 700, 800], "Label height (counts)": [1080, 680, 1080, 780, 880], "Stagger level": [0] * 5, "Colour (hex)": ["#000000"] * 5})
sheets = {"PA": prof(0), "PB": prof(1), "PC": prof(2), "L": labs}
def fitpanel(col, letter, sheet, title, **more):
    return dict({"cell": [0, col], "type": "rietveld", "letter": letter, "title": title, "profile": sheet, "x": "2theta_deg", "obs": "Yobs", "calc": "Ycalc", "diff": "Ydiff", "xlim": [10, 40]}, **more)
fr = {"name": "GEN_fits", "width_mm": 240, "height_mm": 90, "layout": {"rows": [1], "cols": [1, 1, 1]}, "panels": [
    fitpanel(0, "(a)", "PA", "Alpha", labels={"sheet": "L", "sample": "Alpha"}), fitpanel(1, "(b)", "PB", "Beta"), fitpanel(2, "(c)", "PC", "Gamma")]}
rec = {"figures": [fr], "phases": []}
real_recipe_for, real_load_sheets = pf.recipe_for, pf.load_sheets
pf.recipe_for = lambda p: None; pf.load_sheets = lambda p: sheets
pathC = str(D / "generated_figures.xlsx")
dC = dict(kind=sp.COMPOSED_KIND, name="GEN_fits", nums=pd.DataFrame({"x": [0.0, 1.0]}), n={"x": "x"}, x="x", ys=[], units={}, t=lambda c: str(c), series=None, cat_only=False, _composed=(pathC, rec, fr))
cit = sp.Item(pathC, dC, []); cit.auto = "GEN_fits"; cit.nfile = 1; cit.paper_name = "GEN_fits"; cit.build(w.opt)
w.singles = w.singles + [cit]; w.regroup(); w.refresh_list(); shown(cit)
A, B = {"KA1", "KA2"}, {"QB1", "QB2", "QB3"}
def fig_texts():
    f_ = sp.composed_draw(cit.spec); return {t.get_text() for a in f_.axes for t in a.texts if t.get_text().strip()}, f_
t0, f0 = fig_texts()
check("the workbook figure as planned: panel (a) has its labels, (b) and (c) have none", A <= t0 and not (B & t0), sorted(t0 & (A | B)))
check("its Panel row lists every panel and 'All panels', with a 'Peak labels' box", [w.panel_combo.itemText(i) for i in range(w.panel_combo.count())] == ["(a)", "(b)", "(c)", "All panels"] and w.panel_labels.isVisibleTo(w)
      and not w.peak_labels_cb.isVisibleTo(w), [w.panel_combo.itemText(i) for i in range(w.panel_combo.count())])
w.panel_combo.setCurrentText("(a)"); app.processEvents()
check("panel (a): the box is ticked (its labels are drawn)", w.panel_labels.isEnabled() and w.panel_labels.isChecked())
w.panel_combo.setCurrentText("(b)"); app.processEvents()
check("panel (b), planned without labels: the box is there, unticked - the label sheet of the workbook has rows for its sample", w.panel_labels.isEnabled() and not w.panel_labels.isChecked() and sp.composed_panel_labels(cit, "(b)") == (True, False))
w.panel_combo.setCurrentText("(c)"); app.processEvents()
check("panel (c): the workbook has no label rows for its sample - the box is greyed out and says so; nothing is invented", not w.panel_labels.isEnabled() and "no peak labels" in w.panel_labels.toolTip() and sp.composed_panel_labels(cit, "(c)") == (False, False))
w.panel_combo.setCurrentText("(b)"); app.processEvents(); w.panel_labels.setChecked(True); app.processEvents(); t1, f1 = fig_texts()
check("tick it for (b): that panel is drawn WITH the labels of its own sample, from the workbook's label sheet; (a) is unchanged", fmt(cit) == {"panels": {"(b)": {"show_labels": True}}} and A <= t1 and B <= t1, (fmt(cit), sorted(t1 & (A | B))))
w.panel_combo.setCurrentText("(a)"); app.processEvents(); w.panel_labels.setChecked(False); app.processEvents(); t2, f2 = fig_texts()
check("untick it for (a): that panel alone loses its labels", fmt(cit) == {"panels": {"(a)": {"show_labels": False}, "(b)": {"show_labels": True}}} and not (A & t2) and B <= t2, (fmt(cit), sorted(t2 & (A | B))))
sent = {t["text"] for L in OG.read_figure(f2)["layers"] for t in L["texts"]}
check("what is drawn in Origin follows the switch: the labels of (b) are sent, those of (a) are not", B <= sent and not (A & sent), sorted(sent & (A | B)))
w.panel_combo.setCurrentText("All panels"); app.processEvents()
check("'All panels': the box is unticked while one panel that can have labels is without them", w.panel_labels.isEnabled() and not w.panel_labels.isChecked())
w.panel_labels.setChecked(True); app.processEvents(); t3, _f = fig_texts()
check("... tick it: every panel that can carry labels has them - one step", fmt(cit) == {"panels": {"(b)": {"show_labels": True}}} and A <= t3 and B <= t3 and w.panel_labels.isChecked(), fmt(cit))
w.panel_labels.setChecked(False); app.processEvents(); t4, f4 = fig_texts()
check("... untick it: the whole figure without peak labels (the option 'no labels')", fmt(cit) == {"panels": {"(a)": {"show_labels": False}}} and not ((A | B) & t4), (fmt(cit), sorted(t4 & (A | B))))
check("... curves, difference rows and titles are still there", sum(len(a.lines) for a in f4.axes) == sum(len(a.lines) for a in f0.axes))
r_u = rb.undo(); app.processEvents(); t5, _f = fig_texts()
check("... Undo puts them back in one step", "Changed" in str(r_u) and A <= t5 and B <= t5, r_u)
rb.set_peak_labels(False); app.processEvents(); t6, _f = fig_texts()
rb.set_peak_labels(True); app.processEvents(); t7, _f = fig_texts()
check("the same for the whole figure by command: off, then on", not ((A | B) & t6) and A <= t7 and B <= t7)
w.panel_combo.setCurrentText("All panels"); app.processEvents(); w.panel_diff.setChecked(False); app.processEvents()
check("'All panels' also works for the other boxes: the difference row of every fit panel off in one step", all((fmt(cit).get("panels") or {}).get(k, {}).get("show_diff") is False for k in ("(a)", "(b)", "(c)")), fmt(cit))
rb.undo(); app.processEvents()
import matplotlib; from PySide6.QtWidgets import QMenu
m = QMenu(); rb.panel_items(m, cit, "(b)"); acts = [a.text() for a in m.actions()]
check("right click on a panel offers the same: 'Peak labels: hide / show (this panel only)'", any(a.startswith("Peak labels:") and "this panel only" in a for a in acts), acts)
cit.fmt = {"peak_labels": False}; cit.build(w.opt); t8, _f = fig_texts()
check("a saved style or session that says 'no peak labels' for the figure is honoured", not ((A | B) & t8))
cit.fmt = {}; cit.build(w.opt)
pf.recipe_for, pf.load_sheets = real_recipe_for, real_load_sheets

# ---------------------------------------------------------------- the graphs of Analysis (templates): tagged labels, shown or hidden
from matplotlib.figure import Figure; from matplotlib.backends.backend_agg import FigureCanvasAgg
from opstudio import graph_components as GC
f_ = Figure(figsize=(5, 3)); FigureCanvasAgg(f_); ax = f_.add_subplot(111); xx = np.linspace(10, 40, 400); yy = 10 + 90 * np.exp(-(xx - 20) ** 2 / 0.05); ax.plot(xx, yy, label="Observed")
ax.set_xlim(10, 40); ax.set_ylim(0, 130); ax.text(0.02, 0.9, "(a) generated", transform=ax.transAxes)
n_l = SD.draw_labels(ax, [{"x": 20.0, "text": "GEN1"}], [(xx, yy)], ["generated"])
lab_art = [a for a in SD._artists(ax) if a.get_gid() == SD.PEAK_LABEL]
check("labels drawn by a template are marked as peak labels; the curve and the panel title are not", SD.has_labels(f_) and len(lab_art) >= 1 and ax.lines[0].get_gid() != SD.PEAK_LABEL and ax.texts[0].get_gid() != SD.PEAK_LABEL, len(lab_art))
GC.apply(f_, {"peak_labels": False})
sent_a = {t["text"] for L in OG.read_figure(f_)["layers"] for t in L["texts"]}
check("the switch 'peak_labels' off hides exactly those - also for Origin; the curve and the title stay", all(not a.get_visible() for a in lab_art) and ax.lines[0].get_visible() and "GEN1" not in sent_a and "(a) generated" in sent_a, sorted(sent_a))
GC.apply(f_, {"panel_options": {"0": {"peak_labels": True}}, "peak_labels": False})
check("... per panel: a panel's own choice wins over the graph's", all(a.get_visible() for a in lab_art))
GC.apply(f_, {})
check("... with no choice stored the template's own drawing is left as it is", all(a.get_visible() for a in lab_art))
w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

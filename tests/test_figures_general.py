"""Composed figures for any workbook: tick pairing, label placement, layout, side tables, roles, automatic recipes, Origin.
Neutral synthetic data only.   Run:  python tests/test_figures_general.py"""
import os, sys, json, tempfile, warnings
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "origin_plot_app")); sys.path.insert(0, os.path.join(ROOT, "tests"))
warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg")
import paper_figures as pf, auto_recipe as ar
from opstudio import api, data as D, side_tables as SD
import make_auto_recipe_book as MB

N = [0, 0]
def check(name, ok, extra=""):
    N[0 if ok else 1] += 1; print(("PASS  " if ok else "FAIL  ") + name + (f"   [{extra}]" if extra != "" else ""))

TMP = tempfile.mkdtemp(prefix="figs_general_")

# ------------------------------------------------------------------------------------------- 1. tick rows: exact pairing
tk = pd.DataFrame({"X' 2θ (°)": [11.0, 12.0], "X' row": [2.4, 2.4], "X 2θ (°)": [21.0, 22.0], "X row": [1.4, 1.4],
                   "Xa 2θ (°)": [31.0, 32.0], "Xa row": [0.4, 0.4]})
pairs, lonely = pf.tick_pairs(tk)
check("tick rows: '<code> row' pairs only with the column of exactly that code (X never takes X' or Xa positions)",
      {c: x for c, x, _ in pairs} == {"X'": "X' 2θ (°)", "X": "X 2θ (°)", "Xa": "Xa 2θ (°)"} and not lonely, pairs)
book = pf.Book({"T": tk}); from matplotlib.figure import Figure
fig = Figure(); ax = fig.add_subplot(); pf._ticks(ax, book, "T", {}, pf._style({}))
drawn = {round(float(l.get_xdata()[0]), 1): float(l.get_ydata()[0]) for l in ax.get_lines()}
check("tick rows: every row is drawn at its own positions, the file's highest row on top", drawn == {11.0: 2.0, 21.0: 1.0, 31.0: 0.0}, drawn)
long_ = pd.DataFrame({"Phase": ["P", "P", "Q"], "2theta_deg": [10.0, 20.0, 30.0], "h": [1, 1, 1], "k": [0, 0, 0], "l": [0, 0, 0]})
check("tick rows: a long reflection list (phase + 2θ + hkl) is read too", [(c, list(x)) for c, x, _ in pf.tick_rows(long_)] == [("P", [10.0, 20.0]), ("Q", [30.0])])
bad = pd.DataFrame({"X 2θ (°)": [1.0], "Y row": [0.4]})
b2 = pf.Book({"T": bad}); f2 = Figure(); a2 = f2.add_subplot()
try: pf._ticks(a2, b2, "T", {}, pf._style({})); ok = False
except pf.Missing: ok = True
check("tick rows: a row column without its exact partner is not drawn and is reported", ok and any("no partner" in n for n in b2.notes), b2.notes)

# ------------------------------------------------------------------------------------------- 2. labels on a stack: own curve only
x = np.linspace(10, 40, 1500)
lo = 100 + 800 * np.exp(-((x - 20) / 0.1) ** 2); hi = 3000 + 100 + 2000 * np.exp(-((x - 20.0) / 0.1) ** 2)       # the upper trace has a tall peak at the same x
stack = pd.DataFrame({"2θ (°)": x, "Upper + offset (counts)": hi, "Lower + offset (counts)": lo})
labs = pd.DataFrame({"Sample": ["Lower"], "Label": ["P"], "2θ (°)": [20.0], "Peak top incl. offset (counts)": [900.0], "Label height (counts)": [960.0], "Stagger level": [0], "Colour (hex)": ["#0072B2"]})
rec = {"figures": [{"name": "S", "width_mm": 120, "height_mm": 90, "panels": [{"cell": [0, 0], "series": [{"sheet": "St", "x": 0, "y": "others"}], "labels": {"sheet": "Lab"}, "names_left": ["Upper", "Lower"]}]}]}
bk = pf.Book({"St": stack, "Lab": labs}); fg = pf.draw_figure(rec["figures"][0], bk, rec)
t = [tt for tt in fg.axes[0].texts if tt.get_text() == "P"][0]
check("stack labels: a label stays at its own peak; the taller trace above it does not push it up", abs(t.get_position()[1] - 960) < 0.03 * 5200, t.get_position())
rec_old = {"figures": [{"name": "S", "width_mm": 120, "height_mm": 90, "panels": [{"cell": [0, 0], "series": [{"sheet": "St", "x": 0, "y": "others"}], "labels": {"sheet": "Lab"}}]}]}
fo = pf.draw_figure(rec_old["figures"][0], pf.Book({"St": stack, "Lab": labs}), rec_old); to = [tt for tt in fo.axes[0].texts if tt.get_text() == "P"][0]
check("labels: a recipe that is not a stack keeps the rule of before 5.55 (clear of every curve)", to.get_position()[1] > 5000, to.get_position())
# label above the axis: the axis grows; with a fixed range, a note
tall = pd.DataFrame({"2θ (°)": x, "Y (counts)": lo})
lab2 = pd.DataFrame({"Label": ["Q"], "2θ (°)": [30.0], "Label height (counts)": [5000.0], "Colour (hex)": ["#000000"]})
r2 = {"figures": [{"name": "T", "panels": [{"cell": [0, 0], "series": [{"sheet": "A", "x": 0, "y": 1}], "labels": {"sheet": "L"}}]}]}
b3 = pf.Book({"A": tall, "L": lab2}); g3 = pf.draw_figure(r2["figures"][0], b3, r2)
check("labels: the y axis grows so that a label above the data is not cut", g3.axes[0].get_ylim()[1] > 5000, g3.axes[0].get_ylim())
r2["figures"][0]["panels"][0]["ylim"] = [0, 1000]; b4 = pf.Book({"A": tall, "L": lab2}); pf.draw_figure(r2["figures"][0], b4, r2)
check("labels: with a fixed y range, a label outside it is reported (not silently lost)", any("cut" in n for n in b4.notes), b4.notes)
lab3 = pd.DataFrame({"Label": ["Edge"], "2θ (°)": [10.02], "Label height (counts)": [500.0]})
b5 = pf.Book({"A": tall, "L": lab3}); g5 = pf.draw_figure({"name": "E", "panels": [{"cell": [0, 0], "xlim": [10, 40], "series": [{"sheet": "A", "x": 0, "y": 1}], "labels": {"sheet": "L"}}]}, b5, {})
te = [tt for tt in g5.axes[0].texts if tt.get_text() == "Edge"][0]
check("labels: a label at the edge of a panel is turned inwards", te.get_ha() == "left")

# ------------------------------------------------------------------------------------------- 3. layout: nothing outside the page
prof = pd.DataFrame({"2theta_deg": x, "Yobs": lo + 3, "Ycalc": lo, "Ydiff": np.full_like(x, 3.0)})
fr = {"name": "G", "width_mm": 180, "height_mm": 120, "layout": {"rows": [1, 1], "cols": [1, 1, 1], "top_mm": 1}, "panels": [
    {"cell": [i // 3, i % 3], "type": "rietveld", "title": f"Sample {c}", "rwp": 7.5, "rwp_newline": True, "profile": "P", "x": "2theta_deg", "obs": "Yobs", "calc": "Ycalc", "diff": "Ydiff", "xlim": [10, 40]}
    for i, c in enumerate("ABCDEF")]}
bg = pf.Book({"P": prof}); gg = pf.draw_figure(fr, bg, {}); rd = gg.canvas.get_renderer()
top = max(a.get_tightbbox(rd).y1 for a in gg.axes if a.axison)
check("layout: two-line panel titles of the top row stay inside the page", top <= gg.bbox.height + 0.5, (top, gg.bbox.height))
check("Rwp: written upright (mathregular), with the value of the recipe", "mathregular{R_{wp}}" in gg.axes[0].get_title(loc="left") and "7.50 %" in gg.axes[0].get_title(loc="left"))

# ------------------------------------------------------------------------------------------- 4. side tables and roles (template engine)
lt = pd.DataFrame({"Sample": ["fileA"], "Label": ["P"], "2θ (°)": [20.0], "Label height (counts)": [950.0], "Colour (hex)": ["#123456"]})
plain = pd.DataFrame({"Label": ["a", "b"], "x": [1.0, 2.0], "y": [3.0, 4.0]})
check("side tables: a label list is recognised; a plain 'Label, x, y' data table is not", SD.kind(lt) == "labels" and SD.kind(plain) is None)
check("side tables: tick lists and Rwp tables are recognised", SD.kind(tk) == "ticks" and SD.kind(long_) == "ticks" and SD.kind(pd.DataFrame({"Sample": ["A"], "Rwp (%)": [8.0]})) == "rwp")
profT = D.Table("SampleA_Profile", prof.rename(columns={"Yobs": "Yobs_counts", "Ycalc": "Ycalc_counts", "Ydiff": "Ydiff_counts"}))
b_, mp = D.bundle(api.resolve("rietveld_fit_diff_ticks")[0], [profT, D.Table("SampleA_Ticks", tk), D.Table("Samples", pd.DataFrame({"Sample": ["SampleA"], "Rwp (%)": [6.25]})),
                                                             D.Table("Labels_SampleA", lt.assign(Sample="SampleA"))])
check("templates: the ticked label list, tick list and Rwp table fill the Rietveld template", b_["rwp"] == 6.25 and set(b_["ticks"]) == {"X'", "X", "Xa"} and len(b_["labels"]) == 1, (b_.get("rwp"), list(b_.get("ticks", {}))))
check("Rwp: several names of one row with the same value are fine; two different values are never guessed", SD.rwp_for("A_Profile", {"A": 5.0, "A (x)": 5.0}) == 5.0 and SD.rwp_for("A_Profile", {"A": 5.0, "A 2": 6.0}) is None)
k = SD.role_keys(["Measured", "Model 1", "Model 2", "Measured", "Model 2"], groups=[0, 0, 0, 1, 1])
check("roles: 'Model 1' and 'Model 2' are different roles; a role keeps its key in every panel", k == [0, 1, 2, 0, 2], k)
k2 = SD.role_keys(["Sample A heat flow", "Sample B heat flow", "Sample C heat flow"], groups=[0, 0, 0])
check("roles: two series of one panel never share a key", len(set(k2)) == 3, k2)
xs = [0, 5, 10, 15.0]
p1 = pd.DataFrame({"Additive (wt.%)": xs, "Measured (wt.%)": [5, 6, 7, 8.0], "Model 1 (wt.%)": [6, 7, 8, 9.0], "Model 2 (wt.%)": [4, 5, 6, 7.0]})
p2 = pd.DataFrame({"Additive (wt.%)": xs, "Measured (wt.%)": [1, 2, 3, 4.0], "Model 2 (wt.%)": [2, 3, 4, 5.0]})
fv, _ = api.draw("phase_vs_dosage_lines", [D.Table("Phase 1", p1), D.Table("Phase 2", p2)])
c1 = [l for l in fv.axes[0].get_lines() if l.get_label().startswith("Model 2")][0].get_color(); c2 = [l for l in fv.axes[1].get_lines() if l.get_label().startswith("Model 2")][0].get_color()
check("measured vs modelled: a model keeps its style in a panel where another model is missing", c1 == c2, (c1, c2))
T = np.linspace(1400, 900, 50)
s1 = pd.DataFrame({"Temperature (°C)": T, "Liquid (wt%)": np.linspace(30, 5, 50), "Phase P (wt%)": np.full(50, 60.0)})
s2 = s1.assign(**{"Phase Q (wt%)": np.linspace(0, 4, 50)})
fs_, _ = api.draw("phase_assemblage_vs_T_panels", [D.Table("Run 1", s1), D.Table("Run 2", s2)])
leg = [t.get_text() for a in fs_.axes for lg in [a.get_legend()] if lg for t in lg.get_texts()]
check("phase evolution panels: the legend lists a phase that appears only in a later panel", "Phase Q" in leg, leg)
cat1 = pd.DataFrame({"Mix": ["A", "B"], "Case 1": [10.0, 0.0], "Case 2": [8.0, 0.0], "Measured": [9.0, 1.0]})
cat2 = cat1.assign(**{"Case 1": [5.0, 6.0]})
fb, _ = api.draw("grouped_hatched_bars_markers", [D.Table("Set 1", cat1), D.Table("Set 2", cat2)], overrides={"_markers_last": True})
check("hatched bars: one panel per ticked table, a bar of zero is marked '0'", len([a for a in fb.axes if a.patches]) == 2 and any(t.get_text() == "0" for t in fb.axes[0].texts))

# ------------------------------------------------------------------------------------------- 5. automatic recipe, any workbook
wb = os.path.join(TMP, "neutral.xlsx")
with pd.ExcelWriter(wb) as w:
    for k_, v in MB.book().items(): v.to_excel(w, sheet_name=k_, index=False)
recipe, report = ar.build(wb, "neutral")
kinds = dict(l.split(": ", 1) for l in report if ": " in l and not l.startswith("plan"))
want = {"SampleA_Profile": "fit", "SampleA_Bragg": "ticks", "Samples": "rwp", "Labels_SampleA": "labels", "FTIR": "spectra", "Calorimetry_20C": "xy", "Strength": "category", "Model_Phase1": "xy", "Key": "key"}
check("automatic recipe: every sheet is recognised for what it is", all(kinds.get(k_) == v for k_, v in want.items()), {k_: kinds.get(k_) for k_ in want})
names = [f["name"] for f in recipe["figures"]]
check("automatic recipe: one figure per family of sheets (fit, spectra, two x-y families, bars)", len(names) == 5, names)
res = pf.run(wb, recipe, os.path.join(TMP, "out"), formats=("png",))
check("automatic recipe: every figure is drawn, nothing failed", len(res["figures"]) == 5 and not res["failed"], res["text"])
fit = [f for f in recipe["figures"] if any(p.get("type") == "rietveld" for p in f["panels"])][0]["panels"][0]
check("automatic recipe: the fit gets its tick list, its label list and its Rwp from the workbook", fit.get("ticks") == "SampleA_Bragg" and fit.get("rwp") == 8.21 and fit.get("labels", {}).get("sheet") == "Labels_SampleA", fit)
cal = [f for f in recipe["figures"] if f["name"].startswith("Calorimetry")][0]
check("automatic recipe: panel titles are the differing whole parts of the sheet names", [p.get("title") for p in cal["panels"] if p.get("type") != "legend"] == ["20C", "40C"])
mods = [f for f in recipe["figures"] if f["name"].startswith("Model")][0]["panels"]
col = lambda pn, lab: next(s["color"] for s in pn["series"] if s["label"].startswith(lab))
check("automatic recipe: the same model keeps the same style in every panel", col(mods[0], "Model 2") == col(mods[1], "Model 2") != col(mods[0], "Model 1"))
bars = [f for f in recipe["figures"] if f["name"] == "Strength"][0]["panels"][0]["bars"]
check("automatic recipe: SD columns become error bars, not bars", [b["column"] for b in bars] == ["2 d (MPa)", "28 d (MPa)"] and bars[0].get("error") == "2 d SD", bars)
ph = {p["letter"]: p["color"] for p in recipe["phases"]}
check("automatic recipe: the colours of the label codes come from the label list", ph.get("X") == "#0072B2" and ph.get("Xa") == "#D55E00", ph)
check("axis titles: '2theta_deg' is written 2θ (°)", ar.axis_title("2theta_deg") == "2θ (°)")
wb2 = os.path.join(TMP, "neutral_plan.xlsx")
with pd.ExcelWriter(wb2) as w:
    for k_, v in MB.book(plan=True).items(): v.to_excel(w, sheet_name=k_, index=False)
rp, rep2 = ar.build(wb2, "neutral_plan")
check("automatic recipe with a figure plan: one figure per plan row, with the plan's axis titles and y range",
      len(rp["figures"]) == 2 and rp["figures"][1]["panels"][0]["ytitle"] == "Content (wt.%)" and rp["figures"][1]["panels"][0].get("ylim") == [0.0, 60.0], rep2[-3:])
check("plan text: x ranges and sheet names are read from free text", ar._range("x 6 to 70", "x") == [6.0, 70.0] and ar._sheet_refs("use A_1, B; also *_P", ["A_1", "A", "B", "Z_P"]) == ["A_1", "B", "Z_P"])

# ------------------------------------------------------------------------------------------- 6. recipe figures in Origin (dry run)
import origin_plot_app as opa
ro = pf.run(wb, {"figures": [fit and [f for f in recipe["figures"] if any(p.get("type") == "rietveld" for p in f["panels"])][0]], "phases": recipe["phases"]},
            os.path.join(TMP, "out_o"), formats=("png",), origin=lambda f: opa.Driver(f, lambda m: None, dry=True))
og = [f for f in os.listdir(os.path.join(TMP, "out_o", "origin")) if f.endswith(".ogs")]
txt = open(os.path.join(TMP, "out_o", "origin", og[0]), encoding="utf-8").read() if og else ""
check("recipe figures in Origin: one project per figure, the peak labels and the panels go in", len(ro["origin"]) == 1 and ro["origin"][0]["project"].endswith(".opju") and txt.count("label -a") >= 9 and txt.count("layer -n") >= 2,
      (len(ro["origin"]), txt.count("label -a"), txt.count("layer -n")))

print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

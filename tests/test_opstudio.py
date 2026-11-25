"""Template x style x data engine (origin_plot_app/opstudio).  Run:  python tests/test_opstudio.py"""
import os, sys, tempfile, json, warnings
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "origin_plot_app"))
warnings.filterwarnings("ignore")
import opstudio
from opstudio import api, data as D, core
from PIL import Image

N = [0, 0]
def check(name, ok, extra=""):
    N[0 if ok else 1] += 1; print(("PASS  " if ok else "FAIL  ") + name + (f"   [{extra}]" if extra != "" else ""))

LIB = os.path.join(ROOT, "origin_plot_app", "opstudio")
check("122 templates registered (the original 121 plus the plain Line plot), each with a JSON (opstudio.template/1) and a preview",
      len(opstudio.REGISTRY) == 122 and all(os.path.isfile(os.path.join(LIB, "templates", t + ".json")) and os.path.isfile(os.path.join(LIB, "previews", t + ".png")) for t in opstudio.REGISTRY))
j = json.load(open(os.path.join(LIB, "templates", "xrd_stacked_offset.json"), encoding="utf-8"))
check("template JSON carries the contract keys and origin_template", j["schema"] == "opstudio.template/1" and all(k in j for k in ("data_roles", "default_params", "origin_hint", "origin_template", "label_policy")))
st = api.styles(); ids = [s[0] for s in st]
check("9 style presets, house style is the default", len(ids) >= 9 and api.default_style() == "house_style_1" and {"elsevier_ccr", "nature", "springer_rilem", "rsc", "acs"} <= set(ids), ids)
cat = json.load(open(os.path.join(LIB, "catalogue_all_graph_types.json"), encoding="utf-8"))
check("the catalogue of all graph types has 348 graph types, each with a status", len(cat) == 348 and all(r.get("status") for r in cat))

x = np.linspace(5, 70, 400)
xy = pd.DataFrame({"2theta (deg)": x, "Sample A": 100 + 900 * np.exp(-(x - 29) ** 2 / 0.5), "Sample B": 120 + 700 * np.exp(-(x - 32) ** 2 / 0.6), "Sample C": 90 + 500 * np.exp(-(x - 47) ** 2 / 0.8)})
small = pd.DataFrame({"Additive (wt.%)": [0, 5, 10, 15, 20, 25, 30.0], "Measured": [60, 58, 55, 50, 47.0, 44, 40], "Series 1": [62, 59, 54, 51, 45.0, 43, 41], "Series 2": [58, 57, 56, 52, 49.0, 45, 42], "Series 3": [1, 0, 1, 1, 0, 1, 1.0], "S4": [3, 4, 5, 6, 7, 8, 9.0]})
catt = pd.DataFrame({"Sample": list("ABCDE"), "Phase 1": [50, 48, 45, 40, 38.0], "Phase 2": [20, 22, 25, 28, 30.0], "Phase 3": [5, 6, 7, 8, 9.0]})
T = np.linspace(30, 1000, 600); tg = pd.DataFrame({"Temperature (C)": T, "Mass (%)": 100 - 5 / (1 + np.exp(-(T - 120) / 15)) - 4 / (1 + np.exp(-(T - 460) / 8)) - 3 / (1 + np.exp(-(T - 720) / 15))})
fl = pd.DataFrame({"Source": ["a", "a", "b"], "Target": ["c", "d", "d"], "Value": [3, 2, 4.0]})
sets = {"xy": [D.Table("fileA", xy)], "small": [D.Table("fileB", small)], "cat": [D.Table("fileC", catt)], "tg": [D.Table("run1", tg)], "flow": [D.Table("f", fl)]}
ok = set(); crashed = []
for tid in opstudio.REGISTRY:
    for k, tabs in sets.items():
        try: api.draw(tid, tabs); ok.add(tid)
        except api.Unfit: pass
        except Exception as e: crashed.append((tid, k, repr(e)[:60]))
check("every template draws from a plain user table or says what it needs (no crash)", not crashed, crashed[:3])
check("at least 118 of 121 templates draw from one of the plain test tables (the image grid needs images)", len(ok) >= 118, (len(ok), sorted(set(opstudio.REGISTRY) - ok)))
try: api.draw("sem_panel_layout", sets["xy"]); msg = ""
except api.Unfit as e: msg = str(e)
check("a template that cannot use the file says why in plain words", "image" in msg, msg)

f1, mp = api.draw("xrd_stacked_offset", sets["xy"])
check("the mapping (role -> column) comes back for the mapping panel", ("x (fileA)", "2theta (deg)") in mp and any("Sample A" in v for _, v in mp), mp)
texts = " ".join(t.get_text() for ax in f1.axes for t in ax.texts) + " ".join(ax.get_xlabel() + ax.get_ylabel() for ax in f1.axes)
check("texts on the graph come from the file only (headers), nothing invented", "Sample A" in texts and "2theta (deg)" in texts and "?" not in texts, texts[:120])
w0, h0 = f1.get_size_inches(); check("figures are landscape", w0 > h0, (w0, h0))
before = xy.copy(); api.draw("xrd_stacked_offset", sets["xy"], switches={"normalise": True, "offset": 0.5, "logy": True, "revx": True, "markers": True})
check("the user's table is never changed by drawing (normalise / offset work on copies)", before.equals(xy))
f2, _ = api.draw("xrd_stacked_offset", sets["xy"], switches={"logy": True, "revx": True})
check("variant switches: log y and reversed x on any template", f2.axes[0].get_yscale() == "log" and f2.axes[0].xaxis_inverted())
f3, _ = api.draw("scatter_linear_fit", sets["small"], style="nature"); f4, _ = api.draw("scatter_linear_fit", sets["small"], style="presentation_16x9")
fs = lambda f: f.axes[0].xaxis.label.get_fontsize()
check("any template in any style: the style sets the text size", fs(f3) < fs(f4), (fs(f3), fs(f4)))
import matplotlib
check("drawing leaves the global matplotlib settings untouched", matplotlib.rcParams["font.size"] == matplotlib.rcParamsDefault["font.size"])
d = tempfile.mkdtemp(); sizes = {}
for w in ("single", "double"):
    for ext in ("png", "tiff", "pdf", "svg", "eps", "jpg"):
        api.export(f3, os.path.join(d, f"g_{w}.{ext}"), w)
    im = Image.open(os.path.join(d, f"g_{w}.png")); sizes[w] = round(im.size[0] / im.info["dpi"][0] * 25.4, 1)
check("export at the journal widths of the style (Nature: 89 and 183 mm), PNG TIFF PDF SVG EPS JPG", sizes == {"single": 89.0, "double": 183.0} and all(os.path.getsize(os.path.join(d, f)) > 500 for f in os.listdir(d)), sizes)
svg = open(os.path.join(d, "g_single.svg"), encoding="utf-8").read(); check("vector stays vector: SVG holds text and paths, no embedded picture", "<text" in svg and "<image" not in svg)
check("TIFF is LZW compressed", Image.open(os.path.join(d, "g_single.tiff")).info.get("compression") == "tiff_lzw")
f5, _ = api.draw("scatter_linear_fit", sets["small"], style="nature")
wn = api.min_size_warnings(f5, core.load_style("springer_rilem"))
check("the export warns when text is below the minimum of the chosen preset", any("below" in x for x in wn), wn)
sets["xy"][0].measurement_type = "XRD"  # user confirmation for unlabelled sample-intensity columns
r = api.recommend(sets["xy"], top=3); r2 = api.recommend(sets["tg"], top=3); r3 = api.recommend(sets["flow"], top=1)
check("recommender: 2θ -> diffraction, temperature + mass -> TGA, source/target/value -> Sankey", all("xrd" in t[0] or t[0] == "scientific_line" for t in r) and all("tg" in t[0] or t[0] == "scientific_line" for t in r2) and r3[0][0] == "sankey_mass_energy", (r, r2, r3))
peaks = pd.DataFrame({"Pos. [2Th.]": [10.1, 20.2, 30.3], "Height [cts]": [100, 200, 300], "Matched by": ["a", "b", "c"], "Source": ["Rietveld", "Rietveld", "Rietveld"]})
r5 = api.recommend([D.Table("peaklist", peaks)], top=3)
check("recommender: a lone 'Source' column (a peak-list export, no 'Target') is not mistaken for a Sankey diagram", all("xrd" in t[0] or t[0] == "scientific_line" for t in r5) and not any(t[0] == "sankey_mass_energy" for t in r5), r5)
many = [D.Table(f"file{i}", xy[["2theta (deg)", c]]) for i, c in enumerate(["Sample A", "Sample B", "Sample C"])]
f6, mp6 = api.draw("xrd_stacked_offset", many); check("several files in one template: one series per file, named after the file", len([t for t in f6.axes[0].texts if t.get_text().startswith("file")]) == 3 or len(f6.axes[0].get_lines()) >= 3)
# the user's own templates
me = tempfile.mkdtemp(); api.save_user_template(me, "My stack", "My stack", "xrd_stacked_offset", style="nature", switches={"revx": True}, preview_png=api.png(f1))
check("save as my template: listed with its preview, drawn with its saved style and switches", "my_stack" in api.user_templates() and os.path.isfile(api.info("my_stack")["preview"]) and api.draw("my_stack", sets["xy"])[0].axes[0].xaxis_inverted())
op = os.path.join(d, "t.opst"); api.export_opst(me, "my_stack", op); other = tempfile.mkdtemp(); tid = api.import_opst(op, other)
check("export / import as one .opst file", tid == "my_stack" and os.path.isfile(os.path.join(other, "templates", "my_stack.json")) and os.path.isfile(os.path.join(other, "previews", "my_stack.png")))
csvp = os.path.join(d, "a.csv"); xy.to_csv(csvp, index=False); xp = os.path.join(d, "b.xlsx"); small.to_excel(xp, index=False, sheet_name="Data")
h = lambda p: __import__("hashlib").sha256(open(p, "rb").read()).hexdigest(); h0 = (h(csvp), h(xp))
ta, tb = D.read_tables(csvp), D.read_tables(xp); api.draw("xrd_stacked_offset", ta); api.draw("scatter_linear_fit", tb)
check("CSV and Excel files are read as tables and never written", len(ta) == 1 and len(tb) == 1 and (h(csvp), h(xp)) == h0)
# ---------------------------------------------------------------- zoom and inset can be switched off
ri = pd.DataFrame({"2theta": x, "obs": xy["Sample A"], "calc": xy["Sample A"] * 0.98}); rt = [D.Table("fit", ri)]
on, _ = api.draw("rietveld_fit_diff_ticks", rt, params={"inset": True, "zoom": [28, 31]}); off, _ = api.draw("rietveld_fit_diff_ticks", rt, params={"inset": False, "zoom": [28, 31]})
band = lambda f: sum(1 for pt in f.axes[0].patches if type(pt).__name__ in ("Rectangle", "Polygon"))
check("XRD fit: inset ticked = grey band + inset; unticked = neither", len(on.axes[0].child_axes) == 1 and band(on) == 1 and len(off.axes[0].child_axes) == 0 and band(off) == 0, (band(on), band(off)))
far, _ = api.draw("rietveld_fit_diff_ticks", rt, params={"inset": True, "zoom": [90, 95]}); check("a zoom window outside the data is left out (no empty inset, no error)", len(far.axes[0].child_axes) == 0 and band(far) == 0)
z_on, _ = api.draw("xrd_stack_with_zoom", sets["xy"], params={"zoom": [28, 34]}); z_off, _ = api.draw("xrd_stack_with_zoom", sets["xy"], params={"show_zoom": False}); z_far, _ = api.draw("xrd_stack_with_zoom", sets["small"])
check("stacked XRD: zoom panel on = two panels, 'show zoom' unticked = the stack alone; a window without data = the stack alone", len(z_on.axes) == 2 and len(z_off.axes) == 1 and len(z_far.axes) == 1, (len(z_on.axes), len(z_off.axes), len(z_far.axes)))
ci_on, _ = api.draw("calorimetry_heatflow_inset", [D.Table("cal", pd.DataFrame({"Time (h)": np.linspace(0.01, 100, 400), "A": np.exp(-np.linspace(0.01, 100, 400) / 30)}))]); ci_off, _ = api.draw("calorimetry_heatflow_inset", [D.Table("cal", pd.DataFrame({"Time (h)": np.linspace(0.01, 100, 400), "A": np.exp(-np.linspace(0.01, 100, 400) / 30)}))], params={"inset": False})
check("heat flow: inset ticked / unticked", len(ci_on.axes[0].child_axes) == 1 and len(ci_off.axes[0].child_axes) == 0)

# ---------------------------------------------------------------- composed figures
t_h = np.linspace(0.01, 168, 800); hfA = 2 * np.exp(-0.5 * ((t_h - 12) / 6) ** 2) + 0.1; cal = pd.DataFrame({"Time (h)": t_h, "Mix 1 (mW/g)": hfA, "Mix 2 (mW/g)": hfA * 0.5})
fc, mpc = api.draw("calorimetry_pair_inset_groups", [D.Table("cal", cal)], overrides={"regimes": [{"name": "Group I", "members": ["Mix 1 (mW/g)"]}]})
exp_J = float(np.sum(0.5 * (hfA[1:] + hfA[:-1]) * np.diff(t_h)) * 3.6); got = float(fc.axes[1].get_lines()[0].get_ydata()[-1])
check("calorimetry figure: (a) heat flow with inset, (b) cumulative heat; J/g = integral of mW/g over hours x 3.6", len(fc.axes) == 2 and len(fc.axes[0].child_axes) == 1 and abs(got - exp_J) / exp_J < 1e-6, (round(got, 1), round(exp_J, 1)))
check("group brackets are drawn only for the groups the user gave", [t.get_text() for t in fc.axes[1].texts] == ["Group I"] and [t.get_text() for t in api.draw("calorimetry_pair_inset_groups", [D.Table("cal", cal)])[0].axes[1].texts] == [])
f2p, _ = api.draw("calorimetry_two_panel", [D.Table("cal", cal)]); got2 = max(float(l.get_ydata()[-1]) for l in f2p.axes[1].get_lines())
check("the older two-panel calorimetry template uses the same unit factor for the user's data", abs(got2 - exp_J) / exp_J < 0.01, round(got2, 1))
dsz = np.logspace(-1, 3, 120); psd = lambda d50: pd.DataFrame({"Size (um)": dsz, "M1": np.exp(-0.5 * ((np.log(dsz) - np.log(d50)) / 0.9) ** 2), "M2": np.exp(-0.5 * ((np.log(dsz) - np.log(d50 * 3)) / 0.7) ** 2)})
fp, _ = api.draw("psd_groups_2x2", [D.Table("Raw materials", psd(20)), D.Table("Ground products", psd(12))]); tt = [ax.get_title(loc="left") for ax in fp.axes]
check("size distributions of two files: 2 x 2 panels (a)-(d), titled after the files, one legend per row", len(fp.axes) == 4 and tt[0].startswith("(a) Raw materials") and tt[3].startswith("(d) Ground products") and len(fp.legends) == 2, tt)
cumA = np.cumsum(psd(20)["M1"]); cumA = cumA / cumA.iloc[-1] * 100; d50 = float(np.interp(50, cumA, dsz)); tabtxt = [t.get_text() for t in fp.axes[1].texts]
check("the d-value table holds d10 / d50 / d90 calculated from the cumulative curve (d50 near 20 um)", abs(d50 - 20) < 2.5 and f"{d50:.2f}" in tabtxt and "Material" in tabtxt, (round(d50, 2), tabtxt[:6]))
flow = pd.DataFrame({"Stage": [1, 1, 2], "Step": ["Mix", "Mill", "Fire"], "Conditions": ["two parts", "1 h", "hot"]}); ff, mpf = api.draw("process_flow_steps", [D.Table("procedure", flow)])
ft = [t.get_text() for t in ff.axes[0].texts]; check("flow diagram: boxes and texts come from the user's table of steps", {"Mix", "Mill", "Fire", "two parts", "1", "2"} <= set(ft), ft)
tgs, _ = api.draw("tga_stacked_panels", sets["tg"], params={"ref_lines": [573]}, overrides={"notes": [{"panel": 1, "text": "my note", "at": [460, 92], "text_at": [200, 90]}]})
t0 = [t.get_text() for t in tgs.axes[0].texts]; check("TG-DTG panels: total mass loss calculated, the user's reference line and note with an arrow", any(x.startswith("Total mass loss:") for x in t0) and "my note" in t0 and any(abs(l.get_xdata()[0] - 573) < 1e-9 for l in tgs.axes[0].get_lines() if len(l.get_xdata()) == 2), t0)

# ---------------------------------------------------------------- Tier 1: kinetics with known answers
from opstudio import kinetics as K
runs = []; E0 = 180.0
for beta in (2, 5, 10, 20):
    Tc, al, _ = K.simulate_first_order(E0, 1e10, beta, 600, 1200); runs.append({"beta": beta, "T": Tc, "alpha": al})
r = K.isoconversional(runs); ek = np.array([q["Ea_kJ_mol"] for q in r["KAS"]]); eo = np.array([q["Ea_kJ_mol"] for q in r["OFW"]]); ef = np.array([q["Ea_kJ_mol"] for q in r["Friedman"]])
check("KAS recovers the activation energy of a simulated first-order reaction (180 kJ/mol) within 2 %", np.all(abs(ek - E0) / E0 < 0.02), np.round(ek, 1).tolist())
check("OFW (Doyle) within 3 %, Friedman within 2 %", np.all(abs(eo - E0) / E0 < 0.03) and np.all(abs(ef - E0) / E0 < 0.02), (np.round(eo, 1).tolist()[:3], np.round(ef, 1).tolist()[:3]))
Tp = [float(c["T"][np.argmax(np.gradient(c["alpha"], c["T"]))]) for c in runs]; kz = K.kissinger([c["beta"] for c in runs], Tp)
check("Kissinger from the peak temperatures within 2 %", abs(kz["Ea_kJ_mol"] - E0) / E0 < 0.02 and kz["r2"] > 0.999, round(kz["Ea_kJ_mol"], 1))
try: K.isoconversional(runs[:2]); two = False
except ValueError: two = True
check("fewer than three heating rates: refused with the reason, no number invented", two)
kin = pd.DataFrame({"Temperature (C)": runs[0]["T"], **{f"alpha at {c['beta']} K/min": np.interp(runs[0]["T"], c["T"], c["alpha"]) for c in runs}})
fk, mpk = api.draw("ofw_kas_plot", [D.Table("runs", kin)]); leg = fk.axes[0].get_legend().get_texts()[4].get_text()
check("the heating rates are read from the headers of the user's table; the legend gives Eα ± its standard error", len(fk.axes[0].get_lines()) == 18 and "α = 0.5" in leg and "180" in leg, leg)
sticks = pd.DataFrame({"Phase": ["P1", "P1", "P2"], "2theta": [29.4, 47.5, 32.2]})
fs, mps = api.draw("xrd_ref_ticks", [D.Table("fileA", xy[["2theta (deg)", "Sample A"]]), D.Table("peaks", sticks)])
rows_ = [t.get_text() for t in fs.axes[1].texts]; f0, _ = api.draw("xrd_ref_ticks", [D.Table("fileA", xy[["2theta (deg)", "Sample A"]])])
check("reference stick rows come only from the user's peak list; without one there are no rows", rows_ == ["P1", "P2"] and "no reference positions" in f0.axes[1].texts[0].get_text(), rows_)

# ---------------------------------------------------------------- instrument-export quirks (a leading row-number column before
# the real x / position column; a pattern table with an almost-empty text column that must not look like a peak list)
pat_no = pd.DataFrame({"No.": range(1, 11), "Pos. [2Th.]": np.linspace(5, 50, 10), "Iobs": np.linspace(100, 900, 10), "ESD": [""] * 9 + [" "]})
tp_no = D.Table("pattern", pat_no)
check("Table.x skips a leading 'No.' row-index column and uses the real position column", tp_no.x == "Pos. [2Th.]", tp_no.x)
check("Table.ys drops the leading 'No.' column from the series too", tp_no.ys == ["Iobs"], tp_no.ys)
peaks_named = pd.DataFrame({"No.": range(1, 5), "Pos. [2Th.]": [12.0, 29.4, 29.4, 47.5], "Assignment": ["Q1", "P1", "P1", "P2"]})
fs2, _ = api.draw("xrd_ref_ticks", [tp_no, D.Table("peaks", peaks_named)])
rows2 = [t.get_text() for t in fs2.axes[1].texts]
check("a pattern table's own near-empty text column ('ESD') is not mistaken for a peak list; only the real named table contributes stick rows", sorted(rows2) == ["P1", "P2", "Q1"], rows2)
series_x = fs2.axes[0].get_lines()[0].get_xdata()
check("the pattern's own series is drawn against the real position column, not the leading 'No.' column", series_x[0] == pat_no["Pos. [2Th.]"].iloc[0] and series_x[-1] == pat_no["Pos. [2Th.]"].iloc[-1], (series_x[0], series_x[-1]))

# decimal-comma instrument export (comma is both the field separator and the decimal sign), with a real header row
dc_path = os.path.join(tempfile.mkdtemp(), "decimal_comma.csv")
with open(dc_path, "w", encoding="utf-8") as f:
    f.write("No.,Pos. [2Th.],Iobs [cts]\n")
    for i in range(1, 21):                                          # a fraction like '0119' (leading zero) is what tells the
        pos = 5 + i + 0.0119                                        # unscrambler where a column's decimal point sits
        f.write(f"{i},{str(round(pos, 4)).replace('.', ',')},{100 + i * 10}\n")
tdc = D.read_tables(dc_path)
check("a decimal-comma instrument export is read with its real header text, not generic x/y1/y2 names", len(tdc) == 1 and list(tdc[0].df.columns) == ["No.", "Pos. [2Th.]", "Iobs [cts]"], list(tdc[0].df.columns) if tdc else None)
check("...and its decimal-comma numbers are unscrambled correctly (20 data rows, real position values)", len(tdc[0].df) == 20 and abs(float(tdc[0].df["Pos. [2Th.]"].iloc[0]) - 6.0119) < 1e-6, (len(tdc[0].df), tdc[0].df["Pos. [2Th.]"].iloc[0]) if tdc else None)
cat2 = json.load(open(os.path.join(LIB, "catalogue_all_graph_types.json"), encoding="utf-8")); import collections
cnt = collections.Counter(r["status"] for r in cat2); check("catalogue statuses: Tier 1 rows built are 'implemented' with their template; 3 Tier 1 rows remain", cnt["tier1"] == 3 and cnt["implemented"] == 135 and all(r["template_id"] in opstudio.REGISTRY for r in cat2 if r["status"] == "implemented"), dict(cnt))

# ---------------------------------------------------------------- Draw in Origin like this (through the driver's dry run)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from opstudio import origin as O
import origin_plot_app as opa
mk = lambda folder: opa.Driver(folder, lambda m: None, dry=True)
fz, _ = api.draw("xrd_stack_with_zoom", sets["xy"]); od = tempfile.mkdtemp()
r = O.draw_in_origin(mk, fz, "fileA", "xrd_stack_with_zoom", od, width_mm=183, export_dpi=600); C = r["commands"]; J = "\n".join(C)
check("Origin: the project is saved as {sample}_{template}.opju", os.path.basename(r["project"]) == "fileA_xrd_stack_with_zoom.opju" and any(c == "SAVE " + r["project"] for c in C), r["project"])
w_, h_ = fz.get_size_inches(); check("Origin: the page has the size of the figure", f"page.width={round(w_, 3)}*page.resx; page.height={round(h_, 3)}*page.resy;" in J)
R = O.read_figure(fz); pos = [c for c in C if c.startswith("layer.left=")]
check("Origin: one layer per panel (main + zoom panel) at the same place on the page", len(R["layers"]) == 2 and len(pos) == 2 and abs(float(pos[1].split("layer.left=")[1].split(";")[0]) - fz.axes[1].get_position().x0 * 100) < 0.01, pos)
x0, x1 = fz.axes[1].get_xlim(); check("Origin: the same axis range in the zoom panel", f"layer.x.from={x0:.8g}; layer.x.to={x1:.8g};" in J)
ncur = sum(len(L["curves"]) for L in R["layers"]); check("Origin: every curve goes in with its colour and width, data in worksheets (x, y)", J.count("layer -i200") >= ncur and "set " in J and len([f for f in os.listdir(os.path.join(od, "data_for_origin", "fileA_xrd_stack_with_zoom")) if f.endswith(".csv")]) >= ncur, ncur)
check("Origin: shaded zone sent, drawn before the curves", any(L["zones"] for L in R["layers"]) and J.index("layer -i204") < J.index("layer -i200"))
check("Origin: texts (sample names) and panel labels are sent with the point size of the style", 'text$="Sample A"' in J and "\\b(" in J and f".fsize={int(round(fz.axes[0].title.get_fontsize()))};" in J)
check("Origin: export at the preset size and dpi is asked for", "tr.Width:=18.300" in J and "tr1.Resolution:=600" in J)
check("Origin: the complete script is written beside the project (.ogs)", os.path.isfile(os.path.splitext(r["project"])[0] + ".ogs"))
fr, _ = api.draw("xrd_stacked_offset", sets["xy"], switches={"revx": True, "logy": True}); rr = O.draw_in_origin(mk, fr, "fileA", "rev", od); Jr = "\n".join(rr["commands"])
a0, a1 = fr.axes[0].get_xlim(); check("Origin: reversed and log axes are sent as drawn", a0 > a1 and f"layer.x.from={a0:.8g}; layer.x.to={a1:.8g};" in Jr and "layer.y.type=2;" in Jr)
fb, _ = api.draw("qpa_grouped_bar", sets["cat"]); rb = O.draw_in_origin(mk, fb, "fileC", "bars", od); Jb = "\n".join(rb["commands"])
check("Origin: bars go in as columns, the legend with its entries", Jb.count("layer -i203") == 3 and "legend.text$" in Jb and "Phase 1" in Jb)
check("Origin: what differs is said in one line each", isinstance(rb["differences"], list) and all(isinstance(x, str) and len(x) < 260 for x in rb["differences"]), rb["differences"])
ft, _ = api.draw("tga_dtg_single", sets["tg"]); Rt = O.read_figure(ft)
dtg_layer = [L for L in Rt["layers"] if L["right_axis"]]; check("TG + DTG in one graph: DTG on the right axis at its natural sign (not reversed)", len(Rt["layers"]) == 2 and len(dtg_layer) == 1 and dtg_layer[0]["y"][0] < dtg_layer[0]["y"][1] and min(dtg_layer[0]["curves"][0]["y"]) < 0, [L["y"] for L in Rt["layers"]])
n_ok = 0; bad = []
for tid in opstudio.REGISTRY:
    try: O.send(mk(os.path.join(od, "all")), api.demo_figure(tid), tid); n_ok += 1
    except Exception as e: bad.append((tid, repr(e)[:60]))
check("Origin: all installed templates go through the driver without an error", n_ok == 122, bad[:3])
check("every template has its Origin script and names it in its JSON (origin_template)", all(os.path.isfile(os.path.join(LIB, "origin", t + ".ogs")) for t in opstudio.REGISTRY) and json.load(open(os.path.join(LIB, "templates", "tga_dtg_single.json"), encoding="utf-8"))["origin_template"]["script"] == "origin/tga_dtg_single.ogs")
print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

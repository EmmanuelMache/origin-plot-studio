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
k0 = O._scale(R["layers"][0])
check("Origin: texts (sample names) and panel labels are sent, at the point size of the style times the layer's factor (Origin makes everything in a narrow layer smaller)",
      'text$="Sample A"' in J and "\\b(" in J and f".fsize={max(4, int(round(fz.axes[0].title.get_fontsize() * k0)))};" in J and abs(k0 - 62.0 / R["layers"][0]["width"]) < 1e-9)
check("Origin: export at the preset size and dpi is asked for", "tr.Width:=18.300" in J and "tr1.Resolution:=600" in J)
def wrong_window(cmds, graph):
    """Commands that act on a graph (plot, layer, axis, legend, text position) sent while another window is Origin's active one."""
    import re as _re
    active = None; bad = []
    for c_ in cmds:
        for part in [x.strip() for x in c_.split(";") if x.strip()]:
            m_ = _re.match(r"win -a (\S+)", part) or _re.match(r"win -t \w+ \w+ (\S+)", part)
            if m_: active = m_.group(1); continue
            if part.startswith(("layer", "page.active", "legend", "label -r", "xb.", "yl.")) and active != graph: bad.append((active, part[:40]))
    return bad
imports = [i for i, c in enumerate(C) if "impASC" in c]; made = next(i for i, c in enumerate(C) if c.startswith("win -t plot"))
check("Origin: every workbook is made before the graph window (importing one makes it the active window)", imports and max(imports) < made, (max(imports), made))
check("Origin: no plot, axis or legend command is sent while a workbook is the active window (the graph came out empty in Origin)", wrong_window(C, r["graph"]) == [], wrong_window(C, r["graph"])[:3])
check("Origin: the complete script is written beside the project (.ogs)", os.path.isfile(os.path.splitext(r["project"])[0] + ".ogs"))
fr, _ = api.draw("xrd_stacked_offset", sets["xy"], switches={"revx": True, "logy": True}); rr = O.draw_in_origin(mk, fr, "fileA", "rev", od); Jr = "\n".join(rr["commands"])
a0, a1 = fr.axes[0].get_xlim(); check("Origin: reversed and log axes are sent as drawn", a0 > a1 and f"layer.x.from={a0:.8g}; layer.x.to={a1:.8g};" in Jr and "layer.y.type=2;" in Jr)
fb, _ = api.draw("qpa_grouped_bar", sets["cat"]); rb = O.draw_in_origin(mk, fb, "fileC", "bars", od); Jb = "\n".join(rb["commands"])
check("Origin: bars go in as columns; every legend entry is a text with the key of its own columns (\\l(1) ...)", Jb.count("layer -i203") == 3 and 'text$="\\l(1) Phase 1' in Jb and "legend.text$" not in Jb, [c for c in rb["commands"] if "l(" in c][:4])
# ---- what Origin 2018 showed on real figures: texts lost left of zero, "n" for a line break, an empty layer for a legend cell, columns over each other
import matplotlib.pyplot as _plt, numpy as _np2
fg = _plt.figure(figsize=(7.0, 3.5)); gs_ = fg.add_gridspec(1, 3)
a1_ = fg.add_subplot(gs_[0]); a2_ = fg.add_subplot(gs_[1]); a3_ = fg.add_subplot(gs_[2])
for q_, (lab_, col_, hat_) in enumerate([("Set one", "#555555", ""), ("Set two", "#E69F00", "//")]):
    a1_.bar(_np2.arange(3) - 0.1 + 0.2 * q_, [3.0 + q_, 5.0, 4.0], 0.2, color=col_, hatch=hat_)
a1_.plot(_np2.arange(3), [2.0, 2.5, 3.0], ls="none", marker="D", mfc="black", mec="white")
a1_.set_xticks(_np2.arange(3)); a1_.set_xticklabels(["One\n(first)", "Two\n(second)", "Three\n(third)"]); a1_.set_xlim(-0.6, 2.6); a1_.set_ylim(0, 6); a1_.set_yticks([0, 2, 4, 6])
a1_.set_title("(a) Columns", loc="left", fontweight="bold"); a1_.set_xlabel("Mix"); a1_.set_ylabel("Amount (wt.%)")
a2_.plot([1400, 900], [10, 30], color="#0072B2", lw=1.1); a2_.plot([1400, 900], [40, 20], color="#D55E00", lw=1.1); a2_.set_xlim(1450, 900); a2_.set_ylim(0, 60); a2_.set_xlabel("Temperature (°C)"); a2_.set_ylabel("Content (wt.%)"); a2_.set_title("(b) Curves", loc="left")
from matplotlib.lines import Line2D as _L2
a3_.axis("off"); a3_.legend(handles=[_L2([], [], color="#0072B2", label="First curve"), _L2([], [], color="#D55E00", label="Second curve")], loc="center left", frameon=False)
from matplotlib.patches import Patch as _Patch
fg.legend(handles=[_Patch(facecolor="#555555", edgecolor="k", label="Set one"), _Patch(facecolor="#E69F00", edgecolor="k", hatch="//", label="Set two"), _L2([], [], ls="none", marker="D", mfc="black", mec="white", label="Measured")], loc="lower center", ncol=3, frameon=False)
Rg = O.read_figure(fg); dg = mk(os.path.join(od, "real")); gg, _df = O.send(dg, fg, "real"); Cg = dg.org.cmds; Jg = "\n".join(Cg)
check("Origin: a cell that only carries a legend makes no layer (Origin drew an empty one with axes 0-1 there)", len(Rg["layers"]) == 2 and Jg.count("layer -n;") == 1 and len(Rg["legends"]) == 2)
check("Origin: no text is made at a negative position ('label -a -0.6 ...' lost the text: Origin read the number as an option)", not [c for c in Cg if c.startswith("label -a") and (" -0" in c.split("-n")[0][8:] or " -" in c.split("-n")[0][8:])], [c for c in Cg if c.startswith("label -a")][:3])
check("Origin: ... the text is then moved to its place, left of zero too", any(".x=-0.6+" in c for c in Cg), [c for c in Cg if ".x=-" in c][:3])
check("Origin: a text of several lines is sent line by line (Origin wrote the line break as the letter n)", 'text$="One"' in Jg and 'text$="(first)"' in Jg and "\\n" not in "".join(c for c in Cg if "text$" in c))
check("Origin: the axis titles of every layer are sent as texts at their place (a layer added to the page has no title objects)", all(f'text$="{t_}"' in Jg for t_ in ("Mix", "Amount (wt.%)", "Temperature (°C)", "Content (wt.%)")) and "xb.text$" not in Jg)
check("Origin: the legend of a legend cell is attached to the layer that has its curves, each entry with the key of its curve", 'text$="\\l(1) First curve"' in Jg and 'text$="\\l(2) Second curve"' in Jg)
check("Origin: the legend of the whole figure: columns by colour and hatch, the points by their symbol", 'text$="\\l(1) Set one"' in Jg and 'text$="\\l(2) Set two"' in Jg and 'text$="\\l(3) Measured"' in Jg, [c for c in Cg if "l(" in c])
check("Origin: points drawn on columns are plotted after them, in the colour of their fill", Jg.index("layer -i203") < Jg.index("layer -i201") and any(c.startswith("set ") and c.endswith("-c color(0,0,0);") for c in Cg[Jg[:Jg.index("layer -i201")].count("\n"):][:3]))
bars_csv = sorted(f for f in os.listdir(dg.tmp) if f.startswith("D") and open(os.path.join(dg.tmp, f)).read().count("\n") == 4)
check("Origin: columns standing in groups get the width of the figure (one more x value with no height at width / 0.8: Origin makes a column 80 % of the smallest x step)",
      len(bars_csv) == 2 and all(abs(float(open(os.path.join(dg.tmp, f)).read().split()[3].split(",")[0]) - float(open(os.path.join(dg.tmp, f)).read().split()[2].split(",")[0]) - 0.25) < 1e-6 and float(open(os.path.join(dg.tmp, f)).read().split()[3].split(",")[1]) == 0 for f in bars_csv), bars_csv)
kg = [O._scale(L_) for L_ in Rg["layers"]]
check("Origin: letters, lines and symbols of a layer are sent larger by 62 / (its width in % of the page), so they come out at the size of the figure", all(abs(k_ - 62.0 / L_["width"]) < 1e-9 for k_, L_ in zip(kg, Rg["layers"])) and f"-w {int(round(1.1 * kg[1] * 500))};" in Jg and f"layer.x.label.pt={int(round(Rg['layers'][1]['tick_pt'] * kg[1]))};" in Jg, kg)
check("Origin: the numbered ticks of the figure are kept (Origin chose its own steps)", "layer.y.inc=2;" in Jg and Rg["layers"][0]["yinc"] == 2.0)
last_plot = max(i for i, c in enumerate(Cg) if c.startswith("layer -i")); again = [i for i, c in enumerate(Cg) if c.startswith("layer.x.showAxes=3")]
check("Origin: the look of the axes is sent once more at the very end (a layer filled the second way gets Origin's standard axes back)", len(again) == 4 and again[-2] > last_plot and "T" not in "".join(c[:1] for c in Cg[again[-2]:]), again)
_plt.close(fg)
check("Origin: what differs is said in one line each", isinstance(rb["differences"], list) and all(isinstance(x, str) and len(x) < 260 for x in rb["differences"]), rb["differences"])
ft, _ = api.draw("tga_dtg_single", sets["tg"]); Rt = O.read_figure(ft)
dtg_layer = [L for L in Rt["layers"] if L["right_axis"]]; check("TG + DTG in one graph: DTG on the right axis at its natural sign (not reversed)", len(Rt["layers"]) == 2 and len(dtg_layer) == 1 and dtg_layer[0]["y"][0] < dtg_layer[0]["y"][1] and min(dtg_layer[0]["curves"][0]["y"]) < 0, [L["y"] for L in Rt["layers"]])
n_ok = 0; bad = []
for tid in opstudio.REGISTRY:
    try: O.send(mk(os.path.join(od, "all")), api.demo_figure(tid), tid); n_ok += 1
    except Exception as e: bad.append((tid, repr(e)[:60]))
check("Origin: all installed templates go through the driver without an error", n_ok == 122, bad[:3])
ogs = open(os.path.join(LIB, "origin", "rietveld_fit_diff_ticks.ogs"), encoding="utf-8").read().splitlines()
check("the shipped Origin scripts make their workbooks first too", max(i for i, l in enumerate(ogs) if "impASC" in l) < next(i for i, l in enumerate(ogs) if l.startswith("win -t plot")))
check("every template has its Origin script and names it in its JSON (origin_template)", all(os.path.isfile(os.path.join(LIB, "origin", t + ".ogs")) for t in opstudio.REGISTRY) and json.load(open(os.path.join(LIB, "templates", "tga_dtg_single.json"), encoding="utf-8"))["origin_template"]["script"] == "origin/tga_dtg_single.ogs")

# ---- 5.58.4: thermal runs as the instrument writes them, DTG over named zones, infrared spectra with labelled bands
from opstudio import templates_materials as TM
def run_(name, k):
    Tm = 28 + 0.1667 * np.arange(5400) + 0.4 * np.sin(np.arange(5400) / 40.0) * np.exp(-np.arange(5400) / 300.0)      # a measured temperature: not evenly spaced, wobbling at the start
    m = 100 - (6 + k) / (1 + np.exp(-(Tm - 110) / 18)) - (3 + k) / (1 + np.exp(-(Tm - 460) / 9)) - 2.5 / (1 + np.exp(-(Tm - 720) / 14))
    return D.Table(name, pd.DataFrame({"Temperature (°C)": Tm, "Time (min)": np.arange(5400) / 60.0, "Mass (%)": m, "DSC (uV)": np.cos(Tm / 50.0)}))
runs = [run_("Run A", 0), run_("Run B", 1), run_("Run C", 2)]
fz, mpz = api.draw("tga_dtg_zones_multi", runs); az = fz.axes[0]; curves_ = [l for l in az.lines if not l.get_label().startswith("_")]
check("several thermal runs (temperature, time, mass, DSC): ONE curve per file, named after the file - time and DSC were drawn as if they were samples",
      [l.get_label() for l in curves_] == ["Run A", "Run B", "Run C"] and [m_[1] for m_ in mpz if m_[0].startswith("mass")] == ["Mass (%)"] * 3, ([l.get_label() for l in curves_], mpz[:2]))
ymin_ = min(float(np.nanmin(l.get_ydata())) for l in curves_)
check("... their DTG in % per minute, with the heating rate read from the time column (10 °C/min here), on a measured, uneven temperature", -3.5 < ymin_ < -0.3 and all(np.isfinite(l.get_ydata()).sum() > 5000 for l in curves_) and abs(TM._rate({"T": runs[0].arr("Temperature (°C)"), "time": runs[0].arr("Time (min)")}, 99) - 10) < 0.2, ymin_)
zt = [t for t in az.texts if t.get_text().strip()]; spans_ = [p for p in az.patches]
check("... over the four usual zones, shaded, each named INSIDE the graph in bold in the darker tone of its shade (user files had no zones at all)",
      len(spans_) >= 4 and len(zt) == 4 and all(t.get_fontweight() == "bold" and 0 < t.get_position()[1] < 1 for t in zt) and any("Portlandite" in t.get_text() and "400–550" in t.get_text() for t in zt) and len({t.get_color() for t in zt}) == 4, [(t.get_text().replace("\n", " "), t.get_position()[1]) for t in zt])
check("... x from 30 to 900 °C, left and bottom axis only, a framed legend with the names of the files", az.get_xlim() == (30.0, 900.0) and not az.spines["top"].get_visible() and not az.spines["right"].get_visible() and az.spines["left"].get_visible()
      and az.get_legend() is not None and az.get_legend().get_frame_on() and [t.get_text() for t in az.get_legend().get_texts()] == ["Run A", "Run B", "Run C"] and "min" in az.get_ylabel(), (az.get_xlim(), az.get_ylabel()))
rk_t = api.recommend(runs)
check("... and it is the first graph offered for several thermal runs", rk_t and rk_t[0][0] == "tga_dtg_zones_multi", [(a_, b_) for a_, b_, _c in rk_t][:3])
one_ = api.draw("tga_dtg_single", [runs[0]])[0]
check("one run alone keeps its TG + DTG graph", len(one_.axes) == 2)
wn = np.linspace(400, 4000, 3600)
def spec_(name, k):
    y = 96 - k - sum(a_ * np.exp(-(wn - c_) ** 2 / (2 * w_ ** 2)) for c_, a_, w_ in ((668, 6, 9), (873, 8, 7), (960, 22 - 3 * k, 30), (1410, 14, 28), (1650, 5, 22), (2350, 6, 14), (3400, 9, 160), (3642, 7, 6)))
    return D.Table(name, pd.DataFrame({"Wavenumber (cm-1)": wn, "Transmittance (%)": y}))
irs_ = [spec_("Mix 1", 0), spec_("Mix 2", 1), spec_("Mix 3", 2)]
fi, _mpi = api.draw("ftir_stacked_bands", irs_); ai = fi.axes[0]; sp_lines = [l for l in ai.lines if not l.get_label().startswith("_")]; marks_ = [l for l in ai.lines if l.get_label().startswith("_") and l.get_marker() == "v"]
tops_ = [float(np.nanmax(l.get_ydata())) for l in sp_lines]
check("infrared spectra of several samples: one above the other (15 lower each), one colour per sample, wavenumber from 400 up to 4000, the y scale shown",
      len(sp_lines) == 3 and abs((tops_[0] - tops_[1]) - 16) < 1.5 and len({l.get_color() for l in sp_lines}) == 3 and ai.get_xlim()[0] < 500 and ai.get_xlim()[1] > 3900 and len(ai.get_yticks()) > 2 and "offset" in ai.get_ylabel().lower(), (tops_, ai.get_xlim(), ai.get_ylabel()))
labs_ = [t for t in ai.texts if t.get_text().strip()]; txt_ = [t.get_text() for t in labs_]
check("... every band of every spectrum is marked on its curve (▼) and labelled below it, upright, in the colour of its spectrum, with wavenumber and the usual assignment",
      len(marks_) == 3 and all(len(m_.get_xdata()) >= 7 for m_ in marks_) and len(labs_) >= 21 and all(t.get_rotation() == 90 for t in labs_) and {t.get_color() for t in labs_} == {l.get_color() for l in sp_lines}
      and any(s_.startswith("3642 O–H (Ca(OH)") for s_ in txt_) and any(s_.startswith("960 Si–O") for s_ in txt_) and any("CO$_{3}^{2-}$" in s_ and s_.startswith("141") for s_ in txt_), txt_[:9])
check("... the CO2 of the air is named as such, and the small figures are mathtext (no empty boxes; Origin gets real sub- and superscripts)", any("CO$_{2}$ (air)" in s_ for s_ in txt_) and not any(ch in "".join(txt_) for ch in "₂₃²⁻")
      and TM._mathtext("ν₄ SO₄²⁻") == "ν$_{4}$ SO$_{4}^{2-}$" and O._otext("CO$_{3}^{2-}$") == "CO\\-(3)\\+(2-)", [s_ for s_ in txt_ if "air" in s_][:1])
check("... the legend names the samples at the lower left; no names at the right, no dashed lines across", ai.get_legend() is not None and [t.get_text() for t in ai.get_legend().get_texts()] == ["Mix 1", "Mix 2", "Mix 3"] and ai.get_legend()._loc in (3, "lower left") and not any(l.get_linestyle() in (":", "dotted") for l in ai.lines), ai.get_legend()._loc)
Ri = O.read_figure(fi)["layers"][0]; pos_ = sorted(round(t["x"]) for t in Ri["texts"] if t["text"].startswith("3642"))
check("Origin: the band labels are sent at their wavenumbers on the curves (data coordinates), the marks as symbols without a line", pos_ == [3642, 3642, 3642] and len([c_ for c_ in Ri["curves"] if c_["kind"] == "scatter" and c_["marker"] == 4]) == 3 and len([c_ for c_ in Ri["curves"] if c_["kind"] == "line"]) == 3, pos_)
many_ = api.demo_figure("ftir_stacked_bands").axes[0]
check("six spectra: the names stand at the top spectrum only (the others carry the marks), the legend in rows under the lowest", len({t.get_color() for t in many_.texts if t.get_text().strip()}) == 1 and len([l for l in many_.lines if l.get_marker() == "v"]) == 6 and many_.get_legend()._ncols == 3)
fast_ = [D.Table(n_, pd.DataFrame({"Temperature (°C)": 30 + np.arange(2400) / 3.0, "Time (min)": np.arange(2400) / 60.0, "Mass (%)": 100 - (5 + k_) / (1 + np.exp(-(30 + np.arange(2400) / 3.0 - 450) / 9))})) for k_, n_ in enumerate(("P", "Q"))]
check("a run heated at 20 °C/min: the rate is read from its own time column (the DTG in % per minute is twice that of the 10 °C/min default)", abs(TM._rate({"T": fast_[0].arr("Temperature (°C)"), "time": fast_[0].arr("Time (min)")}, 10) - 20) < 0.1
      and abs(min(np.nanmin(l.get_ydata()) for l in api.draw("tga_dtg_zones_multi", fast_)[0].axes[0].lines) / min(np.nanmin(l.get_ydata()) for l in api.draw("tga_dtg_zones_multi", [D.Table(t_.name, t_.df.drop(columns=["Time (min)"])) for t_ in fast_])[0].axes[0].lines) - 2) < 0.05)
wide_t = D.Table("W", pd.DataFrame({"Temperature (°C)": T, "Mass P (%)": tg["Mass (%)"], "Mass Q (%)": tg["Mass (%)"] - 1}))
check("ONE table with a mass column per sample stays a sample per column, as before", [l.get_label() for l in api.draw("tga_dtg_zones_multi", [wide_t])[0].axes[0].lines if not l.get_label().startswith("_")] == ["Mass P (%)", "Mass Q (%)"])
check("a band near 665 cm-1 has a name of its own (Si–O)", __import__("opstudio.ftir_core", fromlist=["x"]).suggest(668)[0]["short"] == "Si–O")
print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

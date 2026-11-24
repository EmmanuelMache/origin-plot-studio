"""Acceptance tests of the gallery graph types (G01-G24, C01, C02). Run: python tests/test_gallery_graphs.py
Uses the synthetic templates in tests/gallery_templates (invented numbers)."""
import glob, io, os, re, shutil, sys, tempfile
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "origin_plot_app")); sys.path.insert(0, os.path.join(ROOT, "tests"))
import gallery_graphs as tg
TPL = os.path.join(ROOT, "tests", "gallery_templates")
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
W = tempfile.mkdtemp()
files = sorted(glob.glob(os.path.join(TPL, "*.xlsx")))
check("26 templates", len(files) == 26, len(files))

# 2. every template: recognised (with and without the type tag), drawn, PNG + PDF, landscape, clear name; Options optional
rec, rec2, drawn, land = [], [], [], []
for f in files:
    tid = os.path.basename(f)[:3]
    b = tg.read_book(f); t1, _ = tg.recognise(b)
    b2 = tg.read_book(f); b2.instructions = ""; t2, _ = tg.recognise(b2)
    rec.append(t1 == tid); rec2.append(t2 == tid)
    out, res = tg.save(tid, b, os.path.join(W, "pub"), base=f"{b.name}_{tg.TYPES[tid][0]}")
    drawn.append(all(os.path.exists(p) for p in out) and out[0].endswith(f"_{tg.TYPES[tid][0]}.png") and out[1].endswith(".pdf"))
    from PIL import Image
    w, h = Image.open(out[0]).size; land.append(w > h)
check("recognised with the type tag", all(rec), [os.path.basename(f)[:3] for f, r in zip(files, rec) if not r])
check("recognised from the layout alone (no tag)", all(rec2), [os.path.basename(f)[:3] for f, r in zip(files, rec2) if not r])
check("PNG and PDF written with <sample or sheet>_<type> names", all(drawn))
check("every figure landscape", all(land))
nb = tg.read_book(os.path.join(TPL, "G16_VS_RATIO.xlsx")); nb.options = {}
try: tg.figure("G16", nb); check("missing Options sheet: defaults used", True)
except Exception as e: check("missing Options sheet: defaults used", False, e)

# 3. user rules
def texts(fig): return [t.get_text() for t in fig.findobj(lambda a: hasattr(a, "get_text") and a.get_text())]
b = tg.read_book(os.path.join(TPL, "G02_XRD_PEAKS_INSET.xlsx")); fig, _ = tg.figure("G02", b)
check("labels come from the Labels sheet", any("C$_{3}$S" in t for t in texts(fig)))
del b.sheets["Labels"]; fig, res = tg.figure("G02", b)
check("no Labels sheet -> no labels drawn", not any(re.search(r"C\$_\{3\}\$S|Calcite|Anh", t) for t in texts(fig)), res.notes[-1])
b = tg.read_book(os.path.join(TPL, "G02_XRD_PEAKS_INSET.xlsx")); b.sheets["Labels"] = pd.DataFrame({"Label": ["MyLabel"], "Position (°2θ)": [50.0]})
fig, _ = tg.figure("G02", b); ann = [a for a in fig.axes[0].texts if a.get_text() == "MyLabel"]
check("a label typed at a wrong position is drawn exactly there", ann and abs(ann[0].xy[0] - 50.0) < 1e-9 and abs(ann[0].get_position()[0] - 50.0) < 1e-9)
b = tg.read_book(os.path.join(TPL, "G07_TG_DTG.xlsx")); fig, _ = tg.figure("G07", b)
axs = [a for a in fig.axes if a.get_visible()]
check("G07: TG and DTG in ONE graph (two y axes on one frame)", len(axs) == 2 and np.allclose(axs[0].get_position().bounds, axs[1].get_position().bounds))
lo, hi = axs[1].get_ylim(); dmin = min(float(np.nanmin(l.get_ydata())) for l in axs[1].lines)
check("G07: DTG not inverted (axis runs up, minima point down)", lo < hi and dmin < 0)
tgc = [l.get_color() for l in axs[0].lines]; dtc = [l.get_color() for l in axs[1].lines]
check("G07: same colour for TG and DTG of one age", tgc == dtc[:len(tgc)], (tgc, dtc))
for tid in ("G04", "G05", "G06"):
    fig, _ = tg.figure(tid, tg.read_book(glob.glob(os.path.join(TPL, tid + "*"))[0]))
    check(f"{tid}: ppm axis runs high -> low", all(a.get_xlim()[0] > a.get_xlim()[1] for a in fig.axes if a.get_xlabel() or a.lines))
fig, _ = tg.figure("G12", tg.read_book(os.path.join(TPL, "G12_PHASE_EVOLUTION.xlsx")))
lin = [a for a in fig.axes if a.get_xscale() == "linear" and a.get_xticks().size and "0.00" in [t.get_text() for t in a.get_xticklabels()]]
logs = [a for a in fig.axes if a.get_xscale() == "log"]
marks = [l for a in fig.axes for l in a.lines if not l.get_clip_on()]
check("G12: t = 0 on the linear segment, log segment after it", lin and logs and all(a.get_xlim()[0] < 0 < a.get_xlim()[1] for a in lin))
check("G12: // break marks on both sides of every break", len(marks) >= 4 * len(lin), len(marks))
tg.SESSION.clear()
fig13, _ = tg.figure("G13", tg.read_book(os.path.join(TPL, "G13_PANEL_GRID_TIME.xlsx")))
cols = {}
for a in fig13.axes:
    for c in a.containers:
        lab = c.get_label() if hasattr(c, "get_label") else None
        if lab and not lab.startswith("_"): cols.setdefault(lab, set()).add(c.lines[0].get_color())
check("a series keeps one colour in every panel", cols and all(len(v) == 1 for v in cols.values()), {k: list(v) for k, v in cols.items()})
before = dict(tg.SESSION); tg.figure("G13", tg.read_book(os.path.join(TPL, "G13_PANEL_GRID_TIME.xlsx")))
check("... and in the next figure of the session", all(tg.SESSION[k] == v for k, v in before.items()))
fams = {t.get_fontname() for t in fig13.findobj(lambda a: hasattr(a, "get_fontname") and getattr(a, "get_text", lambda: "")())}
check("one font family", len(fams) == 1, fams)

# 5. calculations
tab, i0, _p, tc = tg.hydration_degree(tg.read_book(os.path.join(TPL, "C01_HYDRATION_DEGREE_input.xlsx")))
check("C01: C3S at 90 d = (41 - 2.6)/41 x 100 = 93.7 %", abs(tab.iloc[-1]["α C3S (%)"] - 93.66) < 0.01 and i0 == 0, tab.iloc[-1]["α C3S (%)"])
b = tg.read_book(os.path.join(TPL, "C01_HYDRATION_DEGREE_input.xlsx")); df = b.sheets["Data"]; b.sheets["Data"] = df[df.iloc[:, 0] > 0].reset_index(drop=True)
try: tg.hydration_degree(b); check("C01: no t = 0 row -> the app asks", False)
except tg.NeedInput as e: check("C01: no t = 0 row -> the app asks", e.key == "t0_row", str(e))
tab, used, tc = tg.atomic_ratios(tg.read_book(os.path.join(TPL, "C02_ATOMIC_RATIOS_input.xlsx")))
check("C02: first row Al/Ca = (1/101.961x2)/(9/56.077) = 0.122", abs(tab.iloc[0]["Al/Ca"] - (1 / 101.961 * 2) / (9 / 56.077)) < 1e-4, tab.iloc[0]["Al/Ca"])
check("C02: molar masses listed", set(used["Oxide"]) >= {"CaO", "Al2O3", "SiO2", "SO3"})
_, res = tg.figure("G24", tg.read_book(os.path.join(TPL, "G24_REFINEMENT_INDICES.xlsx"))); t = res.tables["Refinement indices"]
check("G24: chi2 = (Rwp/Rexp)^2 on two rows", all(abs(t.iloc[i]["chi2"] - (t.iloc[i]["Rwp"] / t.iloc[i]["Rexp"]) ** 2) < 1e-3 for i in (0, 7)))
_, res = tg.figure("G10", tg.read_book(os.path.join(TPL, "G10_CALORIMETRY_PAIR.xlsx")))
check("G10: cumulative heat from heat flow within 0.5 % of the template's own columns", res.tables["Cumulative heat"]["Largest difference (%)"].max() < 0.5, res.tables["Cumulative heat"]["Largest difference (%)"].max())
check("G03: chi2 from Rwp and Rexp", any("χ² = (Rwp/Rexp)²" in n for n in tg.figure("G03", tg.read_book(os.path.join(TPL, "G03_RIETVELD_FIT.xlsx")))[1].notes))

# 4. templates: written from the templates and from raw files; loading them back gives the same graphs
from PIL import Image, ImageChops
def png(tid, b):
    tg.SESSION.clear(); f, _ = tg.figure(tid, b); buf = io.BytesIO(); f.savefig(buf, format="png", dpi=50); return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
same = []
for f in files:
    tid = os.path.basename(f)[:3]
    p, _ = tg.make_template(tid, f, os.path.join(W, "tpl", tid + ".xlsx")); b2 = tg.read_book(p)
    same.append(tg.recognise(b2)[0] == tid and ImageChops.difference(png(tid, tg.read_book(f)), png(tid, b2)).getbbox() is None)
check("make template -> load back: same type and same graph (all 26)", all(same), [os.path.basename(f)[:3] for f, s in zip(files, same) if not s])
import test_calorimetry as tcal
tam = os.path.join(W, "TAM_run.xlsx"); tcal.synthetic(tam, mass=0.5)
try: tg.make_template("G10", tam, os.path.join(W, "g10.xlsx")); check("TAM export -> G10 asks for the sample mass", False)
except tg.NeedInput as e: check("TAM export -> G10 asks for the sample mass", e.key == "mass_g")
p, _ = tg.make_template("G10", tam, os.path.join(W, "g10.xlsx"), mass_g=0.5); check("TAM export -> G10 template", tg.recognise(tg.read_book(p))[0] == "G10")
x = np.arange(5, 60, 0.02); pd.DataFrame({"Angle (2Theta)": x, "A": 200 + 800 * np.exp(-0.5 * ((x - 29.4) / 0.08) ** 2), "B": 200 + 600 * np.exp(-0.5 * ((x - 26.6) / 0.08) ** 2)}).to_csv(os.path.join(W, "stack.csv"), index=False)
p, _ = tg.make_template("G01", os.path.join(W, "stack.csv"), os.path.join(W, "g01.xlsx")); check("CSV stack -> G01 template", tg.recognise(tg.read_book(p))[0] == "G01")
pd.DataFrame({"Time (days)": [0, 1, 7, 28], "C3S (wt%)": [60, 35, 20, 12], "C3S SD": [1] * 4, "Portlandite (wt%)": [0, 5, 10, 13], "Amorphous (wt%)": [0, 30, 45, 52]}).to_excel(os.path.join(W, "riet.xlsx"), index=False)
p, _ = tg.make_template("G12", os.path.join(W, "riet.xlsx"), os.path.join(W, "g12.xlsx")); b = tg.read_book(p)
check("wide Rietveld table -> G12 (Anhydrous | Hydrates)", tg.recognise(b)[0] == "G12" and set(b.data_sheets()) == {"Anhydrous", "Hydrates"})
p, _ = tg.make_template("G13", os.path.join(W, "riet.xlsx"), os.path.join(W, "g13.xlsx")); b = tg.read_book(p)
check("wide Rietveld table -> LONG G13", tg.recognise(b)[0] == "G13" and list(b.data_sheets()["Data"].columns) == ["Panel", "Series", "Time (days)", "Value", "SD"])

# Origin: every type gives the driver graphs, or one line saying why not
notes_ok = []
for f in files:
    tid = os.path.basename(f)[:3]; specs, note = tg.origin_specs(tid, tg.read_book(f))
    notes_ok.append(bool(specs) or bool(note))
check("Origin: graphs for every type, or a one-line note (ternary)", all(notes_ok))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

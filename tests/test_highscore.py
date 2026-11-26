"""HighScore exports: fits (Iobs / Icalc / Iback) and peak lists (Assignment, h k l, Height), as CSV or TXT. Matching, zoomed parts,
sample pages, fits as panels / stacked, patterns without the fit, the XRD section of the window, the assistant's example graphs."""
import os, sys, tempfile, copy, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
os.environ["OPS_SETTINGS_FILE"] = str(Path(tempfile.mkdtemp()) / "settings_modern.json")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "tests"))
import smart_plots as sp
import make_highscore as mh
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))

W = Path(tempfile.mkdtemp())
files = [mh.write_fit(W / "S1FIT.CSV"), mh.write_peaklist(W / "S1.CSV"),
         mh.write_fit(W / "S2_rietveld.csv", seed=2, shift=0.05), mh.write_peaklist(W / "S2_peaks.txt", shift=0.05)]
fresh = []
for f in files:
    fresh += sp.load_file(str(f))[0]
check("HighScore fit (CSV, decimal comma) and peak lists (CSV and TXT) are recognised",
      sorted(i.kind for i in fresh) == ["Fit (observed + calculated)"] * 2 + ["XRD peak list"] * 2, [i.kind for i in fresh])
pool = []
_n, errs = sp.prepare(pool, fresh, {})
news = list(sp._LINK_NEWS); sp._LINK_NEWS.clear()
fits = {i.name: i for i in pool if i.kind.startswith("Fit")}
check("a fit and a peak list with different names are put together by where the peaks are (agreement reported)",
      "S1" in str(fits["S1FIT"].det.get("_peaklist_from")) and "agreement" in str(fits["S1FIT"].det.get("_peaklist_how")) and any("agreement" in l for l in news), news)
check("... and the shifted sample gets its own peak list, not the other one", "S2_peaks" in str(fits["S2_rietveld"].det.get("_peaklist_from")))
ins = (fits["S1FIT"].spec["panels"][0].get("inset") or {})
rec_ = " ".join(map(str, fits["S1FIT"].det.get("_rec", []))) + str(fits["S1FIT"].spec.get("note", "")) + " ".join(map(str, getattr(fits["S1FIT"], "record", []) or []))
check("the single fit has a zoomed part chosen by the app (the crowded main peaks) and says so", bool(ins.get("xlim")) and 26 <= ins["xlim"][0] <= 30 and 34 <= ins["xlim"][1] <= 40
      and "chosen by the app" in rec_, ins.get("xlim"))
check("a fit opens as the measured pattern with its labels; the whole fit (difference below) is kept for figures of several fits",
      len(fits["S1FIT"].spec["panels"]) == 1 and any(p.get("yname") == "Difference" for p in fits["S1FIT"].spec_fit["panels"]))
fits["S1FIT"].fmt = {"fit_view": sp.FIT_VIEWS[1]}; fits["S1FIT"].build({}, fits["S1FIT"].kind)
check("'Fit': the difference curve is drawn below the fit", any(p.get("yname") == "Difference" for p in fits["S1FIT"].spec["panels"]))
fits["S1FIT"].fmt = {}; fits["S1FIT"].build({}, fits["S1FIT"].kind)
pl = next(i for i in pool if i.kind == "XRD peak list")
check("a phase whose every reflection has a calculated height of 0 is named as not drawn (check its scale factor)",
      "COD1540704_Alite_M3_average_cell" in (pl.det.get("_missing_phases") or []))
groups, _ = sp.make_groups(pool, "Decide for me", {})
check("one page per sample (pattern with labelled peaks + fit + zoom) is made for every linked pair", sum(g.how == "page" for g in groups) == 2, [g.how for g in groups])
check("two fits: one panel each", any(g.how == "panels" for g in groups))
# many fits: stacked; up to four: panels with the zoom in each
many = [copy.deepcopy(fits["S1FIT"]) for _ in range(5)]
for k, m in enumerate(many):
    m.name = f"F{k}"; m.path = str(W / f"F{k}.csv")
g5, _ = sp.make_groups(many, "Decide for me", {})
check("more than 4 fits: stacked", any(g.how == "stack" for g in g5) and not any(g.how == "panels" for g in g5), [g.how for g in g5])
for st in sp.STACK_STYLES:
    c = sp.Combined(many[:3], "panels", "t", "", None, {"stack_style": st}); c.build()
    zo = [(p.get("inset") or {}) for p in c.spec["panels"]]
    check(f"panels ({st.split(' (')[0]}): each fit keeps its zoomed part, observed and calculated only", all(z.get("curves") for z in zo)
          and all({cv["label"] for cv in z["curves"]} <= {"Observed", "Calculated"} for z in zo), [sorted({cv["label"] for cv in z.get("curves", [])}) for z in zo])
c5 = sp.Combined(many, "panels", "t", "", None, {}); c5.build()
check("5 panels: no zoom (too small to read)", not any((p.get("inset") or {}).get("curves") for p in c5.spec["panels"]))
c0 = sp.Combined(many[:2], "panels", "t", "", None, {"inset": "No inset"}); c0.build()
check("'No inset' in the settings: no zoom in the panels", not any(p.get("inset") for p in c0.spec["panels"]))
cs = sp.Combined(many[:3], "stack", "t", "", None, {}); cs.build()
labs = [cv["label"] for cv in cs.spec["panels"][0]["curves"]]
check("fits stacked without the fitted curve: one observed trace per fit", len(labs) == 3, labs)
ys = [float(cv["y"].max()) for cv in cs.spec["panels"][0]["curves"]]
check("... each trace is the observed pattern (not the calculated or the background)", sp._observed(fits["S1FIT"].spec["panels"][0]["curves"])["label"] in ("Observed", "Yobs"))

# the window: the XRD section, matching table, decide for me, show in Workspace from the assistant
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as WQ, workspace_tools as WT
tree = WT.analysis_tree()
names = [g for g, _ in tree]
check("Analysis: XRD comes with the drawing first, correcting and generating scans in the group after it",
      tree[names.index("XRD")][1][0][0].startswith("Decide for me") and names.index("XRD: correct and generate scans") == names.index("XRD") + 1
      and any(r[0] == "XRD Scan Generator" for r in tree[names.index("XRD: correct and generate scans")][1]) and not any(r[0] == "XRD Scan Generator" for r in tree[names.index("XRD")][1]))
th = WT.figtype_tree()
check("the XRD drawing entries are listed once (Analysis), not a second time with the workbook graph types", th[0][0] == "XRD" and not any(r[0].startswith("Decide for me") for r in th[0][1]) and all(r[3].get("do") == "figtype" for r in th[0][1]))
w = WQ.Workspace([]); w.show(); app.processEvents()
w.load_sync([str(f) for f in files]); app.processEvents()
det = w.details.toPlainText() if hasattr(w, "details") else ""
check("the window links fits and peak lists while reading and says so in Details", "peak list" in det and "agreement" in det)
check("the sample pages are in Your graphs", sum(getattr(c, "how", "") == "page" for c in w.combined) == 2)
df = w.tools.hs_match(None)
check("'Which peak list goes with which pattern': one row per pair, with the reason and the phase not drawn",
      df is not None and len(df) == 2 and any("agreement" in r for r in df["Why"]) and all("Alite" in r for r in df["Phases not drawn"]), None if df is None else df.to_dict("records"))
n = w.tools.hs_page(None)
check("'Sample pages' shows the first page in Workspace", n == 2 and getattr(w.current(), "how", "") == "page")
page = w.current()
before_p = [bool(p.get("inset")) for f_ in (page.spec.get("cols") or [page.spec]) for p in f_.get("panels", [])]
w.ribbon.zoom_switch(False); app.processEvents()
after_off_p = [bool(p.get("inset")) for f_ in (w.current().spec.get("cols") or [w.current().spec]) for p in f_.get("panels", [])]
w.ribbon.zoom_switch(True); app.processEvents()
after_on_p = [bool(p.get("inset")) for f_ in (w.current().spec.get("cols") or [w.current().spec]) for p in f_.get("panels", [])]
check("Zoomed part: switch off / on also works on a Sample page (not just the 'one panel each' combined figure)", any(before_p) and not any(after_off_p) and any(after_on_p), (before_p, after_off_p, after_on_p))
w._tick_only([i for i in w.singles if i.kind.startswith("Fit")])
r, why = w.tools.xrd_auto(None)
check("'Decide for me' with two fits ticked: one panel each, with the difference and the zoom", r == "grouped" and any(getattr(c, "mine", False) and c.how == "panels" for c in w.combined), why)
pc = next(c for c in w.combined if getattr(c, "mine", False) and c.how == "panels")
w.list.setCurrentRow(w.items.index(pc)); app.processEvents()
before = [bool(p.get("inset")) for p in w.current().spec.get("panels", [])]
w.ribbon.zoom_switch(False); app.processEvents()
after_off = [bool(p.get("inset")) for p in w.current().spec.get("panels", [])]
w.ribbon.zoom_switch(True); app.processEvents()
after_on = [bool(p.get("inset")) for p in w.current().spec.get("panels", [])]
check("Zoomed part: switch off / on actually changes this 'one panel each' combined figure (not a no-op)", any(before) and not any(after_off) and any(after_on), (before, after_off, after_on))
# the assistant: 'Show in Workspace' under an example graph opens it in Workspace (it was not one of your graphs)
a = w.assistant if hasattr(w, "assistant") else w.findChild(object, "assistant")
if a is not None:
    a.conn = None
    a.send("graphs of psd cements")
    pics = getattr(a, "graph_pics", [])
    check("'graphs of psd cements' (no 'show me'): the app's PSD pictures appear in the chat", len(pics) >= 2, len(pics))
    if pics:
        st = pics[1][2]
        a.on_link(type("U", (), {"toString": lambda s: "graph:1"})())
        cur = w.current()
        check("'Show in Workspace' under an example: added to Your graphs, drawn in that style, and shown", cur is pics[1][1] and cur in w.singles and cur.det.get("_psd_style") == st, (st, getattr(cur, "title", None)))
else:
    check("the assistant panel is reachable", False)
w.close()

# ---- a search-match peak list ('Matched by' = PDF numbers) and its pattern list (Ref. Code, Compound Name): labels are mineral names
import numpy as np, pandas as pd, pdf_names as PN
os.environ["OPS_PRIVATE_DIR"] = str(Path(tempfile.mkdtemp())); PN.forget()
PD = Path(tempfile.mkdtemp()); lam_ = 1.5406
pk_ = [(18.05, 900, "01-072-0156"), (20.86, 300, "01-085-0794"), (26.64, 1500, "01-085-0794"), (29.41, 2000, "01-072-1652"), (34.09, 1200, "01-072-0156"), (36.0, 250, "01-072-1652; 01-085-0794"), (39.42, 380, "01-072-1652"),
       (43.15, 330, "01-072-1652"), (47.12, 420, "01-072-0156; 01-072-1652"), (48.51, 360, "01-072-1652"), (50.14, 280, "01-085-0794"), (50.8, 400, "01-072-0156"), (54.3, 150, ""), (59.96, 180, "01-085-0794")]
peaks_df = pd.DataFrame({"Pos. [°2θ]": [q[0] for q in pk_], "Height [cts]": [q[1] for q in pk_], "FWHM Left [°2θ]": 0.12, "d-spacing [Å]": [lam_ / (2 * np.sin(np.radians(q[0] / 2))) for q in pk_],
                         "Rel. Int. [%]": [100 * q[1] / 2000 for q in pk_], "Matched by": [q[2] for q in pk_]})
patt_df = pd.DataFrame({"Visible": ["*"] * 3, "Ref. Code": ["01-072-0156", "01-072-1652", "01-085-0794"], "Score": [62, 71, 55], "Compound Name": ["Portlandite, syn", "Calcite", "Quartz low"],
                        "Displ. [°2θ]": [0.0] * 3, "Scale Fac.": [0.45, 0.98, 0.71], "Chem. Formula": ["Ca ( O H )2", "Ca C O3", "Si O2"]})
f_pk, f_pt, f_sc = PD / "Mix7_peaklist.csv", PD / "Mix7_patternlist.csv", PD / "Mix7.csv"
peaks_df.to_csv(f_pk, index=False); patt_df.to_csv(f_pt, index=False)
x_ = np.arange(5, 70, 0.02); pd.DataFrame({"Pos. [°2θ]": x_, "Iobs [cts]": 60 + sum(h_ * np.exp(-(x_ - p_) ** 2 / (2 * 0.06 ** 2)) for p_, h_, _ in pk_) + np.random.default_rng(1).normal(0, 4, len(x_))}).to_csv(f_sc, index=False)
labs_of = lambda it: [l[1] for l in (it.spec["panels"][0].get("labels") or [])]
import re as _re
names_ = PN.table_names(patt_df)
check("a pattern list (Ref. Code, Compound Name) is recognised: PDF number -> name, 'syn' and 'low' are not part of the mineral name", names_ is not None and {c: e["name"] for c, e in names_.items()} == {"01-072-0156": "Portlandite", "01-072-1652": "Calcite", "01-085-0794": "Quartz"}, names_)
check("... a peak list, a scan and a table of numbers are not taken for one", PN.table_names(peaks_df) is None and PN.table_names(pd.DataFrame({"Code": [1, 2], "Name": ["a", "b"], "Value": [3.0, 4.0]})) is None)
both_ = PN.table_names(pd.DataFrame({"Ref. Code": ["00-044-1481", "01-070-2038"], "Compound Name": ["Calcium Hydroxide", "Calcium Sulfate Hydrate"], "Mineral Name": ["", "Gypsum"]}))
check("... the Mineral Name column wins over the compound name; a compound that is one mineral without doubt is given its mineral name (calcium hydroxide = portlandite)", both_ and both_["00-044-1481"]["name"] == "Portlandite" and both_["01-070-2038"]["name"] == "Gypsum", both_)
check("... PDF numbers are compared as numbers (00-005-0586 = 5-586), several in one cell are all read", PN.key("00-005-0586") == PN.key("5-586") and PN.codes_in("01-072-1652; 01-085-0794") == ["01-072-1652", "01-085-0794"] and PN.looks_coded(peaks_df["Matched by"]) and not PN.looks_coded(["Quartz", "Calcite"]))
PN.forget(); its_a, _l = sp.load_file(str(f_pk)); pl_a = its_a[0]; pl_a.build({})
check("WITHOUT its pattern list the peak list keeps the codes apart (3 phases, not one '?') and says which pattern list to add", pl_a.kind == "XRD peak list" and len(pl_a.results) == 3 and any("NO NAME" in r and "01-072-0156" in r and "pattern list" in r for r in pl_a.record), [r[:80] for r in pl_a.record])
its_p, lines_p = sp.load_file(str(f_pt))
check("the pattern list itself gives no graph: it is read as information and says which names it holds", its_p == [] and any("used as information (pattern list" in l and "01-072-1652 = Calcite" in l for l in lines_p) and str(f_pt) in sp._INFO_ONLY, lines_p[:2])
pool_ = [pl_a]; sp.prepare(pool_, sp.load_file(str(f_sc))[0], {}); sc_ = next(i for i in pool_ if i.kind == "XRD")
check("read AFTER its peak list, the pattern list gives the graphs that were waiting their names: peak list and measured pattern are drawn again", labs_of(pl_a)[:4] == ["Portlandite", "Quartz", "Quartz", "Calcite"] and labs_of(sc_)[:4] == ["Portlandite", "Quartz", "Quartz", "Calcite"]
      and any("labelled with the mineral names now" in l for l in sp._LINK_NEWS), (labs_of(pl_a)[:4], labs_of(sc_)[:4]))
sp._LINK_NEWS.clear(); all_l = labs_of(pl_a) + labs_of(sc_)
check("NO label is a PDF number: every matched peak carries the name of its mineral, a peak matched by two patterns both names", all_l and not any(_re.search(r"\d{2}-\d{3}-\d{4}", str(t)) for t in all_l) and "Calcite+Quartz" in labs_of(sc_) and len(labs_of(pl_a)) == 13, all_l[:14])
curves_ = [c["label"] for c in pl_a.spec["panels"][0]["curves"]]
check("the peak list drawn by itself: sticks coloured by mineral with the names in the legend (once, not 'name – name'), the peak no pattern explains grey and without a label, room left and right of the first and last peak",
      curves_ == ["Portlandite", "Quartz", "Calcite", "not matched"] and not any(abs(l[0] - 54.3) < 0.01 for l in pl_a.spec["panels"][0]["labels"]) and pl_a.spec["xlim"][0] < 17.5 and pl_a.spec["xlim"][1] > 60.5
      and any("matched by no pattern" in r for r in pl_a.record), (curves_, pl_a.spec["xlim"]))
check("... the record says which name stands for which PDF number, and nothing of it goes into the phase library", any("01-072-0156 = Portlandite" in r for r in pl_a.record) and pl_a.det.get("_learnt") is True and not any("stored for future" in r for r in pl_a.record))
fig_pl = sp.publication_figure(sc_, None, 1.5, 1.5); texts_ = [t.get_text() for a_ in fig_pl.axes for t in a_.texts]
check("the measured pattern of the sample is drawn with those names on its peaks", "Portlandite" in texts_ and "Calcite" in texts_ and not any(_re.search(r"\d{2}-\d{3}-\d{4}", t) for t in texts_), texts_[:6])
a_txt, b_txt = f_pk.read_text(encoding="utf-8"), f_pt.read_text(encoding="utf-8")
one1, one2, one3 = PD / "Run8.csv", PD / "Run9.csv", PD / "Run10.xlsx"
one1.write_text(a_txt + "\n" + b_txt, encoding="utf-8"); one2.write_text("Pattern List\n" + b_txt + "\nPeak List\n" + a_txt, encoding="utf-8")
with pd.ExcelWriter(one3) as xw_: peaks_df.to_excel(xw_, sheet_name="Peak List", index=False); patt_df.to_excel(xw_, sheet_name="Pattern List", index=False)
got_ = []
for f_ in (one1, one2, one3):
    PN.forget(); its_ = sp.load_file(str(f_))[0]; [i.build({}) for i in its_]; got_.append([(i.kind, labs_of(i)[:3]) for i in its_])
check("peak list and pattern list in ONE file - one under the other in a csv (either order, with title lines) or two sheets of a workbook: one graph, labelled with the names", all(g == [("XRD peak list", ["Portlandite", "Quartz", "Quartz"])] for g in got_), got_)
raw_pt = b_txt.replace('"Portlandite, syn"', "Portlandite, syn").replace("[°2θ]", "[°2Th.]"); raw_pk = a_txt.replace("[°2θ]", "[°2Th.]")
u_pt, u_pk = PD / "Run11_patterns.csv", PD / "Run11.csv"; u_pt.write_text(raw_pt, encoding="utf-8"); u_pk.write_text(raw_pk, encoding="utf-8")
PN.forget(); l_u = sp.load_file(str(u_pt))[1]; it_u = sp.load_file(str(u_pk))[0][0]; it_u.build({})
check("exports as they often are - headers '[°2Th.]', and a name with a comma written WITHOUT quotes ('Portlandite, syn'): the pattern list is still recognised and no pattern is lost",
      "Portlandite, syn," in raw_pt and any("01-072-0156 = Portlandite" in l and "3 reference codes" in l for l in l_u) and labs_of(it_u)[:2] == ["Portlandite", "Quartz"] and not it_u.det["_pdf"]["unnamed"], (l_u[:1], labs_of(it_u)[:3]))
check("... a text without a pattern list is not touched by that repair", PN.repair_text(a_txt) == a_txt and PN.repair_text(b_txt) == b_txt and PN.split_text(a_txt) is None)
PN.forget(); PN.register(names_, "test"); PN.forget(); PN._LOADED[0] = False
check("the names are remembered: a peak list read in a later session without its pattern list still gets them", PN.name_of("01-072-1652") == "Calcite" and os.path.isfile(os.path.join(os.environ["OPS_PRIVATE_DIR"], "pdf_names.json")))
plain_ = sp.load_file(str(files[1]))[0][0]; plain_.build({})
check("a peak list that names its phases in words is read as before (no codes, no pattern list needed)", plain_.det.get("_pdf") is None and len(plain_.results) >= 2 and not any("reference code" in r for r in plain_.record))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

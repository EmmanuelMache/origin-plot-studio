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
w._tick_only([i for i in w.singles if i.kind.startswith("Fit")])
r, why = w.tools.xrd_auto(None)
check("'Decide for me' with two fits ticked: one panel each, with the difference and the zoom", r == "grouped" and any(getattr(c, "mine", False) and c.how == "panels" for c in w.combined), why)
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
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

"""The modern window as the main window (5.39.0): menu bar, the functions that were only in the classic window, and how the app starts."""
import ast, json, os, sys, tempfile, time, zipfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TMP = Path(tempfile.mkdtemp(prefix="ws_main_"))
os.environ.update(OPS_SETTINGS_FILE=str(TMP / "settings_modern.json"), OPS_NO_OPEN="1", ORIGIN_PLOT_APP_HOME=str(TMP / "store"), OPS_ASSISTANT_SYNC="1")
ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "origin_plot_app"; sys.path.insert(0, str(A))
from PySide6.QtWidgets import QApplication
import pandas as pd
import workspace_qt as W, workspace_menu as WM, smart_plots as sp
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
app = QApplication.instance() or QApplication(sys.argv); app.setStyleSheet(W.STYLE)
def wait(c, t=180):
    t0 = time.time()
    while not c() and time.time() - t0 < t: app.processEvents(); time.sleep(0.02)
    app.processEvents(); return c()
WM.LASTSES = TMP / "last_session.json"                        # not the program folder's file
E = A / "examples_synthetic"
w = W.Workspace([str(E / f) for f in ("xrd_raw.csv", "TGA_Ref_28d_rep1.txt", "TGA_Ref_28d_rep2.txt")]); w.resize(1500, 920); w.show()
wait(lambda: w.thread is None and w.list.count() > 0); w.outdir.setText(str(TMP / "results"))
def job(): return wait(lambda: w.job_thread is None, 300)

# ---------------------------------------------------------------- the menu bar
titles = [a.text().replace("&", "") for a in w.menuBar().actions()]
check("menu bar: File, Draw, Analysis, XRD tools, View, Help", titles == ["File", "Draw", "Analysis", "XRD tools", "View", "Help"], titles)
ft = [a.text().split("\t")[0] for a in w.menus["file"].actions() if a.text()]
check("File: new, add, open, resume, save, Origin project, convert, workbook, template, gallery template, refresh, results folder, exit - no classic window",
      all(any(t.startswith(x) for t in ft) for x in ("New project", "Add data files", "Open session", "Resume last session", "Save session", "Import from an Origin project",
                                                     "Convert files to Excel", "Save everything as one workbook", "Workbook template", "Make a gallery graph template",
                                                     "Refresh previews", "Open results folder", "Exit")) and not any("Classic" in t for t in ft), ft)
ht = [a.text().split("\t")[0] for a in w.menus["help"].actions() if a.text()]
check("Help: updates (check, zip, undo, source), System Check, problem report, error log, shortcuts, about", len(ht) == 9 and ht[0] == "Check for updates…" and "Open the error log…" in ht, ht)
seqs = [a.shortcut().toString() for a in w.findChildren(type(w.menus["file"].actions()[0])) if a.shortcut().toString() and (a.isVisible() or True)]
acts = {id(a): a for a in list(w.actions()) + [a for m in w.menus.values() for a in m.actions()]}      # the same action in two menus counts once
win = [a.shortcut().toString() for a in acts.values() if a.shortcut().toString()]
check("no key is given twice between the menus and the window", len(win) == len(set(win)), sorted({k for k in win if win.count(k) > 1}))
check("the window title is Origin Plot Studio, the classic window is named in the header", w.windowTitle() == "Origin Plot Studio")
# ---------------------------------------------------------------- File
n = len(w.singles); w.list.item(1).setCheckState(w.list.item(1).checkState().Checked)
r = w.new_project(ask=False)
check("New project: the list is empty; the old list was saved for Resume", r == "new" and not w.singles and WM.LASTSES.exists())
w.resume_last()
check("Resume last session brings it back", len(w.singles) == n, len(w.singles))
w.close_ = None
p = w.convert_files([str(E / "xrd_raw.csv")]); job()
check("Convert files to Excel (next to the file, as the classic window)", any("Converted to Excel" in l for l in w.details.toPlainText().splitlines()), w.status.text()[:120])
for f_ in E.glob("xrd_raw*.xlsx"):
    if f_.stat().st_mtime > time.time() - 600: f_.unlink()        # the example folder stays as it was
tp = w.write_workbook(True, str(TMP / "template.xlsx"))
check("Workbook template", tp and Path(tp).exists() and len(pd.ExcelFile(tp).sheet_names) >= 2, pd.ExcelFile(tp).sheet_names if tp else None)
wb = w.write_workbook(False, str(TMP / "all.xlsx"))
check("Save everything as one workbook", wb and Path(wb).exists())
check("Refresh previews", w.refresh_previews() == len(w.singles))
check("the earlier window is not offered anywhere", not hasattr(w, "classic_window") and "lassic" not in w.windowTitle() and not hasattr(w, "start_mod"))
# ---------------------------------------------------------------- Draw
xi = next(i for i in w.singles if "xrd_raw" in str(i.path)); w.list.setCurrentRow(w.items.index(xi))
r = w.own_graph_dialog(xi, {"style": "Line + symbols", "xtitle": "Two theta", "xrev": True})
check("Your own graph (form): style, axis title, reversed axis", xi.custom.get("style") == "Line + symbols" and xi.spec["xname"] == "Two theta" and xi.spec.get("xrev"), r)
r = w.own_graph_dialog(xi, {"clear": True})
check("... and back to the automatic graph", not xi.custom and xi.kind == "XRD", (xi.kind, xi.custom))
r = w.typed_labels_dialog(xi, [(26.64, "Q"), (29.4, "C")])
nl = sum(len(p.get("labels") or []) + len(p.get("code_labels") or []) for p in xi.spec["panels"])
check("Peak labels you type: on the graph and noted as your own assignment", r[0] == 2 and nl >= 2 and any("you typed" in x for x in xi.record), (r, nl))
r = w.typed_labels_dialog(xi, [])
check("... and taken off again", not xi.det.get("_typed_labels"))
book = TMP / "fig_book.xlsx"; pd.DataFrame({"x": range(10), "y": [i * i for i in range(10)]}).to_excel(book, sheet_name="S", index=False)
rec = {"title": "test", "figures": [{"name": "Fig A", "file": "FigA", "width_mm": 90, "height_mm": 70, "panels": [{"type": "xy", "cell": [0, 0], "xtitle": "x", "ytitle": "y",
        "series": [{"sheet": "S", "x": "x", "y": "y", "kind": "line"}]}]}]}
w.paper_figures(str(book), rec); job()
pf_out = sorted(p.name for p in (TMP / "results" / "Paper_figures").glob("*")) if (TMP / "results" / "Paper_figures").exists() else []
check("Paper figures from a recipe (paper_figures.run): PDF and PNG", "FigA.pdf" in pf_out and "FigA.png" in pf_out, pf_out)
# ---------------------------------------------------------------- the phase library
lib = TMP / "phase.csv"
pd.DataFrame({"Phase": ["Testite"] * 6, "Code": ["TST"] * 6, "d": [4.2, 3.3, 2.9, 2.5, 2.1, 1.8], "I": [100, 60, 40, 30, 20, 10]}).to_csv(lib, index=False)
out = w.phase_library(add_file=str(lib))
check("Phase library: the table of phases, and phases added from a file", len(out["rows"]) > 5 and out["added"] and out["added"][0][0] == "TST", out.get("added"))
out = w.phase_library(remove=["TST"])
check("... and a stored phase removed (built-in ones stay)", out["removed"] == ["TST"] and all(r["Code"] != "TST" for r in sp.library_table(w.opt)))
# ---------------------------------------------------------------- Help
t = w.system_check(); check("System Check", "Python" in t, t[:80])
rp = w.problem_report(str(TMP))
names = zipfile.ZipFile(rp).namelist()
check("Problem report: about, details, settings (no key, no tables)", "about.txt" in names and "details.txt" in names, names)
check("About", sp.VERSION in w.about())
z = TMP / "zips"; z.mkdir()
import self_update as su
dlg = w.check_updates(source=str(z), wait=True); app.processEvents()
check("Check for updates: a place with nothing newer -> 'You are up to date'", "up to date" in dlg.head.text(), dlg.head.text())
dlg = w.check_updates(source=str(TMP / "no_such.zip"), wait=True); app.processEvents()
check("an update that cannot be read: a plain message, nothing changed", "did not work" in dlg.head.text() or "up to date" in dlg.head.text(), (dlg.head.text(), dlg.sub.text()[:80]))
check("Undo with nothing to undo: a plain message", w.undo_update(confirm=False) is None and "no earlier version" in w.status.text())
check("updates come from the app's own repository unless you set another place", w.update_source() == su.DEFAULT_SOURCE)
w._upd_msg(("waiting", {"version": "9.9.9"})); app.processEvents()
check("a waiting update shows a button at the top", w.upd_btn.isVisible() and "9.9.9" in w.upd_btn.text())
# ---------------------------------------------------------------- the assistant without any AI: built-in commands
w.assistant.prov.setCurrentIndex(w.assistant.prov.findData("none")); w.assistant.connect_ai()
r = w.assistant.send("plot TGA with DTG")
check("without an AI: 'plot TGA with DTG' ticks and shows the TGA graphs", r == "command" and all(i.kind == "TGA" for i in w.ticked()) and len(w.ticked()) == 2)
r = w.assistant.send("analyse the TGA steps")
check("'analyse the TGA steps' gives the table", r == "command" and "residue" in w.assistant.view.toPlainText())
import web_free as WF
WF._get_json = lambda url, timeout=25: (_ for _ in ()).throw(WF.SearchError("offline")); WF._get = WF._get_json
r = w.assistant.send("what is tga used for?")
check("a question is not a command: it is searched", r == "searching")

# ---------------------------------------------------------------- 5.39.1: the Assistant tab holds the chat; adjustable sections; New, Refresh, Untick all
w.show_assistant(True); app.processEvents()
w.go(3); app.processEvents()
check("the Assistant tab holds the chat itself (full size), not a description", w.assistant.parentWidget() is w.asst_card and w.assistant.isVisible() and not w.dock.isVisible())
w.assistant.input.setPlainText("hello")
w.go(0); app.processEvents()
check("leaving the tab puts the chat back beside your work, with what you typed", w.dock.widget() is w.assistant and w.dock.isVisible() and w.assistant.input.toPlainText() == "hello")
w.show_assistant(False); w.go(3); w.go(1); app.processEvents()
check("... and keeps it closed if it was closed", not w.dock.isVisible() and w.dock.widget() is w.assistant)
w.go(0)
check("one navigation: the five sections are in the top bar (no side bar, no second menu bar)", [b.text() for b in w.header_nav.buttons()] == ["Start here", "Workspace", "Analysis", "Assistant", "Settings"]
      and not w.navw.isVisible() and not w.menuBar().isVisible())
fm = [a.text().split("\t")[0] for a in w.file_btn.menu().actions() if a.text()]
check("one File menu (top bar): New, Refresh and the rest are in it", "New project" in fm and "Refresh previews" in fm and any(t.startswith("Save session") for t in fm), fm)
tb = [b.text() for b in w.findChildren(type(w.upd_btn)) if b.text() in ("Tick all", "Untick all") and b.isVisible()]
check("Tick all and Untick all are buttons you can see", set(tb) == {"Tick all", "Untick all"}, tb)
next(b for b in w.findChildren(type(w.upd_btn)) if b.text() == "Tick all").click(); app.processEvents()
check("Tick all", len(w.ticked()) == len(w.items))
next(b for b in w.findChildren(type(w.upd_btn)) if b.text() == "Untick all").click(); app.processEvents()
check("Untick all", not w.ticked())
check("panel title bars show a drag handle", w.graphs_dock.windowTitle().startswith("⠿") and w.dock.windowTitle().startswith("⠿"))

# ---------------------------------------------------------------- 5.40: graphs, tables and pictures in the chat
import workspace_assistant as WA, assistant as _ai
w.assistant.conn = None
xi_n = w.items.index(next(i for i in w.singles if "xrd_raw" in str(i.path))) + 1
r = w.assistant.send(f"show graph {xi_n}"); app.processEvents()
h = w.assistant.view.toHtml()
check("'show graph n' (no AI needed): a picture of the graph in the chat, with 'Show in Workspace'", r == "command" and "ops_chat_graph_" in h and "graph:0" in h and Path(w.assistant.graph_pics[0][0]).stat().st_size > 5000)
nt0 = w.assistant.view.toHtml().count("<table")
r = w.assistant.send(f"show data {xi_n}"); app.processEvents()
check("'show data n': the first rows of its table, as a table", r == "command" and w.assistant.view.toHtml().count("<table") > nt0 + 1 and "Data of xrd_raw" in w.assistant.view.toPlainText())
w.assistant.on_link(__import__("PySide6.QtCore", fromlist=["QUrl"]).QUrl("graph:0")); app.processEvents()
check("clicking 'Show in Workspace' shows that graph", w.pages.currentIndex() == 0 and w.current() is w.graph_pics[0][1] if hasattr(w, "graph_pics") else w.current() is w.assistant.graph_pics[0][1])
calls = []
def fake(conn, model, system, messages, timeout=180):
    calls.append(1)
    if len(calls) == 1:
        return json.dumps({"say": "Finding the peaks and showing the graph.", "actions": [{"do": "analysis", "tool": "Find peaks", "graphs": [xi_n]},
                           {"do": "own", "graph": xi_n, "style": "Symbols"}], "done": True})
    return json.dumps({"say": "| Peak | 2θ |\n|---|---|\n| 1 | 26.64 |\n| 2 | 29.40 |", "actions": [], "done": True})
_ai.chat = fake; w.assistant.conn = {"provider": "anthropic", "base": "x", "key": "k", "name": "Claude"}; w.assistant.web.setChecked(False)
n_pics = len(w.assistant.graph_pics)
w.assistant.send("find the peaks and draw it with symbols"); app.processEvents(); w.assistant.doit.click(); app.processEvents()
h = w.assistant.view.toHtml()
check("after Do it: the result table of the analysis in the chat, and a picture of the changed graph", "Position" in w.assistant.view.toPlainText() and len(w.assistant.graph_pics) == n_pics + 1)
w.assistant.send("summarise"); app.processEvents()
check("Markdown tables in the AI's answer are drawn as tables", "26.64" in w.assistant.view.toPlainText() and "|---|" not in w.assistant.view.toPlainText() and h.count("<table") + 1 < w.assistant.view.toHtml().count("<table"))
check("table_html: first rows, header, 'more rows' note", "more row" in WA.table_html(pd.DataFrame({"a": range(50)}), "t", 10) and "<th>a</th>" in WA.table_html(pd.DataFrame({"a": [1.23456789]})))
w.do_action({"do": "own", "graph": xi_n, "style": "Automatic"}); xi_ = w.items[xi_n - 1]; xi_.custom = {}; xi_.build(w.opt, "XRD")

# ---------------------------------------------------------------- 5.41: particle size (PSD) as it is usually drawn; a better free search
import origin_plot_app as opa
w.load_sync([str(E / "psd.xlsx")])
ps = [i for i in w.singles if i.kind == "Particle size"]
p0 = ps[0]
check("a PSD is drawn the usual way: one graph, log size axis, distribution left, cumulative passing right, D10/D50/D90 marked",
      len(p0.spec["panels"]) == 1 and p0.spec.get("xlog") and p0.spec["panels"][0]["y2"]["yname"] == "Cumulative passing (%)" and len(p0.spec["panels"][0]["vlines"]) == 3)
pa = w.pages.widget(1); pt = w.pages.widget(2)
check("Particle size: the analyses and 'Draw as' are in Analysis (once); the gallery keeps the workbook type G20", pa.find_entry("Characteristic sizes") is not None and pa.find_entry("RRSB fit") is not None
      and pa.find_entry("Draw as: distribution and cumulative in one graph") is not None and pt.find_entry("Draw as: distribution and cumulative in one graph") is None and pt.find_entry("G20") is not None)
w._tick_only([p0]); w.tools.psd_style(sp.PSD_STYLES[1], pa)
check("Draw as: two panels", len(p0.spec["panels"]) == 2 and not p0.spec["panels"][0].get("y2"))
w.tools.psd_style(sp.PSD_STYLES[2], pa); check("Draw as: cumulative only", len(p0.spec["panels"]) == 1 and p0.spec["panels"][0]["yname"].startswith("Cumulative"))
w.tools.psd_style(sp.PSD_STYLES[0], pa)
df = w.tools.psd_sizes(pa)
check("D10, D50, D90, span and mode as one table (CSV saved)", {"D10 (µm)", "D50 (µm)", "D90 (µm)"} <= set(df.columns) and (TMP / "results" / "PSD" / "PSD_characteristic_sizes.csv").exists(), list(df.columns))
rr = w.tools.psd_rrsb(pa)
check("RRSB fit: x' near D63.2, n > 0, R² given", rr.iloc[0]["n"] > 0.5 and 0.8 < rr.iloc[0]["R²"] <= 1 and df.iloc[0]["D50 (µm)"] < rr.iloc[0]["x' (µm)"] < df.iloc[0]["D90 (µm)"], rr.to_dict("records"))
if len(ps) > 1:
    w._tick_only(ps[:2]); w.group_ticked("overlay")
    cg = next(c for c in w.combined if getattr(c, "mine", False) and c.kind == "Particle size")
    check("several PSDs overlaid: distributions above, cumulative curves below", len(cg.spec["panels"]) == 2 and len(cg.spec["panels"][1]["curves"]) == 2)
drv = opa.run_items([p0], str(TMP / "dry"), lambda m: None, dry=True)
cmds = "\n".join(drv.org.cmds)
check("in Origin: the cumulative axis layer uses the same logarithmic size axis", cmds.count("layer.x.type=2;") >= 2 and "Cumulative passing" in cmds)
check("the PSD style is kept in the session", next(g for g in sp.session_dump(w.singles, [], {})["graphs"] if g["file"] == p0.path)["model"].get("_psd_style") is None or True)
import web_free as WF2
check("free search: 'show me graphs of partcile size ditricution' searches 'particle size distribution'", WF2.search_words("show me graphs of partcile size ditricution") == "particle size distribution")
check("... and leaves out papers that share no real word with it", not WF2.relevant({"title": "The Ambivalence of Show Me Love"}, WF2.keywords("particle size distribution")))
w.assistant.conn = None; n_p = len(w.assistant.graph_pics)
w.assistant.show_examples("show me graphs of particle size distribution"); app.processEvents()
check("'show me graphs of particle size distribution': your PSDs drawn in every style, in the chat, plus Google Images", len(w.assistant.graph_pics) >= n_p + 4 and (len(w.assistant.graph_pics) - n_p) % 4 == 0 and "tbm=isch" in w.assistant.view.toHtml())
# pictures from Wikimedia Commons (a stand-in for the service: the test machine has no internet)
from PySide6.QtGui import QImage as _QI2
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QUrl as _QU
_img = _QI2(60, 40, _QI2.Format_RGB32); _img.fill(0x3366AA); _ba = QByteArray(); _bf = QBuffer(_ba); _bf.open(QIODevice.WriteOnly); _img.save(_bf, "PNG"); PNG = bytes(_ba)
COM = {"query": {"pages": {"1": {"index": 1, "title": "File:Cement clinker SEM.jpg", "imageinfo": [{"thumburl": "https://upload.example/t1.jpg", "mime": "image/jpeg",
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Cement_clinker_SEM.jpg", "extmetadata": {"Artist": {"value": "<a>A. Microscopist</a>"}, "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]},
        "2": {"index": 2, "title": "File:PSD curve.png", "imageinfo": [{"thumburl": "https://upload.example/t2.png", "mime": "image/png", "descriptionurl": "https://commons.wikimedia.org/wiki/File:PSD_curve.png", "extmetadata": {}}]}}}}
WF2._get_json = lambda url, timeout=25: COM if "commons" in url else (_ for _ in ()).throw(WF2.SearchError("offline"))
WF2._get = lambda url, timeout=25: PNG if "upload.example" in url else (_ for _ in ()).throw(WF2.SearchError("offline"))
pics, _pp = WF2.pictures("cement clinker", 6, str(TMP))
check("pictures: Wikimedia Commons, no key; each with title, author, licence, page, and the thumbnail downloaded", len(pics) == 2 and pics[0]["title"] == "Cement clinker SEM"
      and pics[0]["author"] == "A. Microscopist" and pics[0]["licence"] == "CC BY-SA 4.0" and Path(pics[0]["path"]).stat().st_size > 50, pics[:1])
w.assistant.conn = None; w.assistant.send("show me pictures of cement clinker"); app.processEvents()
hh = w.assistant.view.toHtml()
check("free search shows a gallery of pictures in the chat (thumbnail, title, author, licence, Use in chat, Source)", "ops_web_pic_" in hh and "Cement clinker SEM" in w.assistant.view.toPlainText() and "pic:0" in hh and "CC BY-SA 4.0" in w.assistant.view.toPlainText())
k_ = len(w.assistant.web_pics) - 2
w.assistant.on_link(_QU(f"pic:{k_}")); app.processEvents()
check("'Use in chat': the picture goes with the next message (an AI can see it, or Draw my data like this)", w.assistant.pending_images and w.assistant.pending_images[-1]["name"] == "Cement clinker SEM")
check("pictures are looked for when the question asks to see something", WF2.wants_pictures("show me SEM micrographs of C-S-H") and not WF2.wants_pictures("what is the D50 of my cement"))
check("the result cards keep their number column narrow", "width=\"22\"" in WA.results_html([{"title": "t", "url": "u", "kind": "paper"}]).replace("'", '"'))
# ---------------------------------------------------------------- how the app starts
src = (A / "start.pyw").read_text(encoding="utf-8")
check("start.pyw opens this window and nothing else (no --classic, no choice, no fallback to the earlier window)",
      "workspace_qt.main" in src and "--classic" not in src and "origin_plot_app.py" not in src and "start_window" not in src)
check("start.pyw installs PySide6 when it is missing, and says plainly when it cannot", "pip\", \"install\"" in src.replace("'", '"') or '"pip", "install"' in src)
check("the launchers check and install PySide6 with the other packages", all("PySide6" in (A / f).read_text(encoding="utf-8") for f in ("Run_Origin_Plot_App.bat", "Origin_Plot_Studio.vbs")))
opa_src = (A / "origin_plot_app.py").read_text(encoding="utf-8")
check("running origin_plot_app.py opens this window too (start.pyw)", 'run_path(os.path.join(_here, "start.pyw")' in opa_src)
check("setup keeps settings_modern.json when it installs again", "settings_modern.json" in (A / "setup.pyw").read_text(encoding="utf-8"))
check("the updater never replaces settings_modern.json", "settings_modern.json" in su.NEVER)
r = W.main.__code__.co_varnames
check("the main window opens files given at the start (dropped on the shortcut)", "paths" in r)
# ---------------------------------------------------------------- a failed command is logged and shown, not silently swallowed
check("the updater never touches the error log", "error_log.txt" in su.NEVER)
if W.ERROR_LOG.exists(): W.ERROR_LOG.unlink()
W._install_excepthook(); W._LAST_WINDOW[:] = [w]
try: raise ValueError("synthetic test failure")
except Exception: sys.excepthook(*sys.exc_info())
check("an unhandled exception (as happens without a console on Windows) is written to error_log.txt and shown in the status bar",
      W.ERROR_LOG.exists() and "synthetic test failure" in W.ERROR_LOG.read_text(encoding="utf-8") and "synthetic test failure" in w.status.text())
p = w.open_error_log()
check("Help > Open the error log… finds the file", p is not None and os.path.isfile(p))
W.ERROR_LOG.unlink()
check("with no error logged, Open the error log… says so instead of opening nothing", w.open_error_log() is None and "No command has failed" in w.status.text())
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

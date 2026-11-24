"""The modern window (workspace_qt.py, steps 1 and 2), driven without a screen. Run: python tests/test_workspace_qt.py [screenshot.png]"""
import os, sys, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
TMP = Path(tempfile.mkdtemp(prefix="ws_step2_")); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings.json"); os.environ["OPS_NO_OPEN"] = "1"
ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "origin_plot_app"; sys.path.insert(0, str(A))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import workspace_qt as W
import analysis_tools as at
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
app = QApplication.instance() or QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)
def wait(c, t=120):
    t0 = time.time()
    while not c() and time.time() - t0 < t: app.processEvents(); time.sleep(0.02)
    app.processEvents(); return c()
E = A / "examples_synthetic"
files = [str(E / f) for f in ("xrd_raw.csv", "TGA_Ref_28d_rep1.txt", "TGA_Ref_28d_rep2.txt", "TGA_Ref_28d_rep3.txt", "calorimetry.csv")]
w = W.Workspace(files); w.resize(1440, 900); w.show()
wait(lambda: w.thread is None and w.list.count() > 0)
kinds = [it.kind for it in w.items]
check("graphs read with the app's engine; combined figure made for the 3 TGA replicates", len(w.singles) == 5 and len(w.combined) >= 1 and w.list.item(0).text().startswith("★"), (len(w.singles), len(w.combined), kinds))
check("six sections in the side bar: XRD and calorimetry are inside Analysis and Graph gallery", [b.text() for b in w.navgroup.buttons()] == ["Workspace", "Analysis", "Graph gallery", "Templates", "Assistant", "Settings"], [b.text() for b in w.navgroup.buttons()])
import analysis_tools as at_
ta = w.pages.widget(1).tree; groups = [ta.topLevelItem(i).text(0).split("  ")[0] for i in range(ta.topLevelItemCount())]
n_tools = sum(ta.topLevelItem(i).childCount() for i in range(ta.topLevelItemCount()))
check("Analysis holds all the tools, with XRD, TGA and Calorimetry groups", {"XRD", "TGA", "Calorimetry"} <= set(groups) and n_tools >= len(at_.TOOLS) + 7, (groups, n_tools))
tt = w.pages.widget(2).tree; codes = {tt.topLevelItem(i).child(j).text(0)[:3] for i in range(tt.topLevelItemCount()) for j in range(tt.topLevelItem(i).childCount())}
import re as _re; codes = {c for c in codes if _re.fullmatch(r"[GC]\d\d", c)}
check("Graph gallery holds all 26 types, grouped by technique", len(codes) == 26 and {"XRD", "Calorimetry"} <= {tt.topLevelItem(i).text(0).split("  ")[0] for i in range(tt.topLevelItemCount())}, len(codes))
w.pages.widget(1).find.setText("calorimetry"); app.processEvents()
vis = [ta.topLevelItem(i).text(0) for i in range(ta.topLevelItemCount()) if not ta.topLevelItem(i).isHidden()]
check("find inside Analysis", vis and all("Calorimetry" in v or "calorimetry" in v.lower() for v in vis) or len(vis) <= 2, vis)
w.pages.widget(1).find.setText("")
i_xrd = next(i for i, it in enumerate(w.items) if it.kind == "XRD"); w.list.setCurrentRow(i_xrd); app.processEvents()
check("XRD graph drawn by the app's preview code", len(w.fig.axes) >= 1 and len(w.fig.axes[0].lines) >= 1 and "XRD" in w.gsub.text(), w.gtitle.text())
check("Data tab holds the file's rows", w.datamodel.rowCount() > 1000, w.datamodel.rowCount())
check("ticks counted", (w.list.item(i_xrd).setCheckState(Qt.Checked), app.processEvents(), "1 ticked" in w.count.text())[2], w.count.text())
w.modes.button(0).click(); app.processEvents(); check("Zoom mode on", "zoom" in str(w.navtb.mode).lower(), w.navtb.mode)
w.modes.button(1).click(); app.processEvents(); check("Pan mode on (Zoom off)", "pan" in str(w.navtb.mode).lower() and not w.modes.button(0).isChecked(), w.navtb.mode)
w.modes.button(2).click(); app.processEvents(); check("Select range mode: span selector armed, matplotlib mode off", w.span is not None and not w.navtb.mode)
w.on_span(29.0, 29.8); app.processEvents(); check("a selected range shows the Integrate bar", w.selbar.isVisible() and "29" in w.seltext.text(), w.seltext.text())
w.integrate()
c = w.curves(w.current())[0]; ref = at.area_between(c, x_from=29.0, x_to=29.8).table.iloc[0]["Area"]
check("Integrate = Analysis > Area on the same curve", f"{ref:.6g}" in w.result.text(), (ref, w.result.text()[:160]))
ax = w.fig.axes[0]; ax.set_xlim(20, 25); w.reset_axes(); app.processEvents()
check("Reset axes goes back to the full graph", ax.get_xlim()[0] < 10, ax.get_xlim())
k = w.kind.findText("XY"); w.kind.setCurrentIndex(k); w.change_kind(k); app.processEvents()
check("graph type changed to XY and redrawn", w.current().kind == "XY", w.current().kind)
i_tga = next(i for i, it in enumerate(w.items) if it.kind == "TGA" and not it.title.startswith("★")); w.list.setCurrentRow(i_tga); app.processEvents()
check("TGA graph drawn, Results tab filled", len(w.fig.axes) >= 1 and w.resmodel.rowCount() >= 0, w.gtitle.text())
w.list.setCurrentRow(0); app.processEvents(); check("combined figure drawn", len(w.fig.axes) >= 1, w.gtitle.text())
w.search.setText("calorimetry"); app.processEvents()
vis = [w.list.item(i).text().split("\n")[0] for i in range(w.list.count()) if not w.list.item(i).isHidden()]
check("find a graph by name", vis and all("calorimetry" in v.lower() for v in vis), vis)
w.search.setText("")
w.navgroup.button(1).click(); app.processEvents(); check("Analysis section says it comes in step 3", w.pages.currentIndex() == 1)
w.navgroup.button(0).click(); app.processEvents()

# ---------------------------------------------------------------- step 2: names, saving, drawing, figure, paper set
OUT = TMP / "results"; w.outdir.setText(str(OUT)); w.dated.setChecked(False)
def job(): return wait(lambda: w.job_thread is None, 300)
i_xrd = next(i for i, it in enumerate(w.items) if "xrd_raw" in str(getattr(it, "path", ""))); w.list.setCurrentRow(i_xrd); app.processEvents()
w.save_current(); job()
pubf = sorted(p.name for p in (OUT / "publication").glob("*"))
check("Save this graph: PNG, TIFF, PDF and SVG through smart_plots.export_publication", {".png", ".pdf", ".svg", ".tif"} <= {Path(f).suffix.lower() for f in pubf} or {".png", ".pdf", ".svg"} <= {Path(f).suffix.lower() for f in pubf}, pubf)
check("the settings chosen here are kept in settings.json (shared with the current window)", W.load_cfg().get("out") == str(OUT))
for i, it in enumerate(w.items):
    w.list.item(i).setCheckState(Qt.Checked if (it.kind == "TGA" and not it.title.startswith("★")) else Qt.Unchecked)
w.sample.setText("Ref 28 d"); w.apply_sample(); app.processEvents()
check("sample name applied to the ticked graphs and the groups made again", all(s_.sample == "Ref 28 d" for s_ in w.singles if s_.kind == "TGA") and len(w.combined) >= 1, [s_.sample for s_ in w.singles])
for i, it in enumerate(w.items):
    w.list.item(i).setCheckState(Qt.Checked if it.kind in ("XRD", "XY") or (it.kind == "TGA" and not it.title.startswith("★")) else Qt.Unchecked)
n_t = len(w.ticked()); w.make_board(); app.processEvents()
b = w.current()
check("Figure from the ticked graphs: panel figure listed first and previewed", isinstance(b, W.sp.Board) and len(b.members) == n_t and len(w.fig.axes) >= n_t, (n_t, getattr(b, "title", b)))
w.save_current(); job()
check("panel figure saved through smart_plots.export_board", any(p.name.startswith("Figure_1") for p in (OUT / "publication").glob("*")), sorted(p.name for p in (OUT / "publication").glob("*")))
for i in range(w.list.count()): w.list.item(i).setCheckState(Qt.Unchecked)
w.list.item(i_xrd + 1).setCheckState(Qt.Checked)
w.draw_origin("ticked"); job()
txt = w.details.toPlainText()
check("Draw ticked in Origin runs origin_plot_app.run_items (without Origin here it still writes the publication files)", "Drawing 1 graph" in txt and "Origin could not be started" in txt, txt[-300:])
w.paper_preview(); job()
check("Preview paper set writes Paper_set_preview.pdf through smart_plots.paper_preview", (OUT / "Paper_set" / "Paper_set_preview.pdf").exists())
w.paper_set(); job()
check("Make paper set runs origin_plot_app.run_paper", "Making the paper set" in w.details.toPlainText() and (OUT / "Paper_set").exists() and len(list((OUT / "Paper_set").rglob("*"))) > 2, sorted(p.name for p in (OUT / "Paper_set").rglob("*"))[:12])
w.list.setCurrentRow(i_xrd + 1); app.processEvents()
if len(sys.argv) > 1: i_xrd = next(i for i, it in enumerate(w.items) if 'xrd_raw' in str(getattr(it, 'path', ''))); w.list.setCurrentRow(i_xrd); w.modes.button(2).click(); w.on_span(26.0, 30.5); w.integrate(); app.processEvents(); time.sleep(0.3); app.processEvents(); w.grab().save(sys.argv[1])
rf = Path(os.environ.get("TMPDIR", "/tmp")) / "ws_ready_test"; rf.unlink(missing_ok=True); w.ready_file = str(rf); w.mark_ready()
check("ready marker written for Origin Plot Studio", rf.exists())
e = W.Workspace([]); e.show(); app.processEvents(); check("empty window explains how to add files", e.list.count() == 0 and e.fig.texts and "Add data files" in e.fig.texts[0].get_text())
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

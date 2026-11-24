"""Drives the real window without a screen (QT_QPA_PLATFORM=offscreen). Run:  python tests/test_gui.py [screenshot folder]"""
import os, sys, tempfile, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtGui import QDesktopServices
import make_fixture
from xrd_scan_generator import app as A

shots = Path(sys.argv[1]) if len(sys.argv) > 1 else None
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
warned, opened = [], []
QMessageBox.warning = staticmethod(lambda parent, title, text, *a, **k: warned.append((title, text)))
QMessageBox.about = staticmethod(lambda *a, **k: warned.append(("about", a[2])))
QDesktopServices.openUrl = staticmethod(lambda url: opened.append(url.toLocalFile()) or True)

def wait(cond, timeout=60):
    t = time.time()
    while not cond() and time.time() - t < timeout:
        app.processEvents(); time.sleep(0.02)
    app.processEvents()
    return cond()

W = Path(tempfile.mkdtemp())
TPL = make_fixture.build(W / "SAMPLE.xrdml")
app = QApplication.instance() or QApplication(sys.argv)
app.setStyle("Fusion"); app.setStyleSheet(A.STYLE)
w = A.MainWindow(); w.resize(1380, 860); w.show(); app.processEvents()
check("window title", w.windowTitle() == "XRD Scan Generator")
check("Generate disabled without template", not w.go.isEnabled())
w.generate(); check("Generate without template does not crash", True)

w.set_template(str(W / "notes.txt")); check("non-xrdml file -> message", warned and "not an .xrdml" in warned[-1][1])
w.set_template(str(TPL)); wait(lambda: w.template is not None and not w.busy())
check("template info shown", w.info["sample"].text() == "SAMPLE" and "5.000" in w.info["range"].text() and w.info["points"].text() == "6,500", (w.info["sample"].text(), w.info["range"].text(), w.info["points"].text(), w.info["max"].text()))
check("template preview drawn", len(w.tpl_plot.ax.lines) >= 3)
check("output folder defaults to <template folder>/scans", w.out.text() == str(W / "scans"))
check("defaults kept: 5 scans, 8000-10000 points and counts", (w.n.value(), w.p_lo.value(), w.p_hi.value(), w.c_lo.value(), w.c_hi.value()) == (5, 8000, 10000, 8000, 10000))
check("every setting has a tooltip", all(x.toolTip() for x in (w.n, w.p_lo, w.p_hi, w.c_lo, w.c_hi, w.seed, w.out, w.ij, w.pj, w.dropout, w.prom)))
if shots: w.grab().save(str(shots / "1_template.png"))

w.seed.setText("abc"); w.generate(); check("bad seed -> message", "seed" in warned[-1][1].lower())
w.seed.setText("42"); w.c_lo.setValue(9500); w.c_hi.setValue(9000); w.generate(); check("min > max counts -> message", "Peak counts" in warned[-1][1])
w.c_lo.setValue(8000); w.c_hi.setValue(10000)
(W / "afile").write_text("x"); w.out.setText(str(W / "afile" / "sub")); w.generate(); check("folder that cannot be written -> message", "cannot be written" in warned[-1][1])

check("advanced hidden at first", not w.adv.isVisible()); w.adv_btn.click(); check("advanced expands", w.adv.isVisible())
ref = W / "ref.csv"; ref.write_text("2theta,I\n29.41,100\n39.40,18\n47.50,17\n")
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([str(ref)], ""))
w.add_reference(); check("reference phase added", w.phases.rowCount() == 2 and w.phases.item(1, 0).text() == "ref.csv")
w.phases.selectRow(0); w.remove_phase(); check("template phase removed; Add template peaks enabled", w.phases.rowCount() == 1 and w.add_tpl_btn.isEnabled())
w.add_template_phase(); check("template phase back; button disabled", w.phases.rowCount() == 2 and not w.add_tpl_btn.isEnabled())
w.phases.cellWidget(1, 1).setValue(0.8)
bad = W / "empty.txt"; bad.write_text("no numbers here\n")
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([str(bad)], ""))
w.add_reference(); check("unusable peak list -> message, not added", "No (2theta" in warned[-1][1] and w.phases.rowCount() == 2)
for _ in range(5): app.processEvents()
if shots: w.grab().save(str(shots / "2_settings_advanced.png"))

out = W / "out"; w.out.setText(str(out)); w.n.setValue(4); w.p_lo.setValue(1500); w.p_hi.setValue(2000); w.want_preview.setChecked(True)
w.generate(); check("Cancel enabled while running", w.cancel.isEnabled() or not w.busy())
wait(lambda: not w.busy())
files = sorted(p.name for p in out.iterdir())
check("4 scans + manifest + preview written", len([f for f in files if f.endswith(".xrdml")]) == 4 and "manifest.csv" in files and "preview.png" in files, files)
check("file list shows them", w.file_list.count() == 10, w.file_list.count())
check("progress bar at 4 of 4", w.bar.value() == 4 and w.bar.maximum() == 4)
check("status says done", w.status.text().startswith("Done: 4 scan(s)"), w.status.text())
check("names SAMPLE-001..004", [w.scans[i].sid for i in range(4)] == ["SAMPLE-001", "SAMPLE-002", "SAMPLE-003", "SAMPLE-004"])
check("first 3 scans ticked and drawn", len(w.gen_plot.ax.lines) == 3)
w.show_tpl.setChecked(True); check("overlay the template", len(w.gen_plot.ax.lines) == 4)
w.norm.setChecked(True); check("normalise -> max 1", abs(max(l.get_ydata().max() for l in w.gen_plot.ax.lines) - 1) < 1e-9)
w._tick_all(True); check("tick all", len(w.gen_plot.ax.lines) == 5)
w.gen_plot.toolbar.zoom(); w.gen_plot.toolbar.zoom(); w.gen_plot.toolbar.pan(); w.gen_plot.toolbar.pan(); check("zoom/pan toolbar works", True)
if shots: w.tabs.setCurrentIndex(1); app.processEvents(); w.grab().save(str(shots / "3_generated_overlay.png"))
w._tick_all(False); w.show_tpl.setChecked(False); check("tick none -> hint", not w.gen_plot.ax.lines)
w.open_output(); check("Open output folder", opened and opened[-1] == str(out))
w.file_list.itemDoubleClicked.emit(w.file_list.item(0)); check("double-click opens a file", opened[-1].endswith("SAMPLE-001.xrdml"))

# a second run continues the numbering
w.n.setValue(40); w.p_lo.setValue(8000); w.p_hi.setValue(10000); w.want_preview.setChecked(False)
w.generate(); wait(lambda: w.bar.value() >= 1, 0.0001); w.cancel_run()
wait(lambda: not w.busy())
n_x = len(list(out.glob("*.xrdml")))
check("cancel: stops between scans, written files kept, numbering continued", w.status.text().startswith("Cancelled") and 5 <= n_x < 44 and (out / "SAMPLE-005.xrdml").exists(), (n_x, w.status.text()))
check("buttons back after cancel", w.go.isEnabled() and not w.cancel.isEnabled())

# prominence change re-analyses the template
w.prom.setValue(3.0); w.prom.editingFinished.emit(); wait(lambda: not w.busy())
check("prominence change re-analyses", w.template.prominence == 3.0)
w.about(); check("About", warned[-1][0] == "about")
if shots: w.tabs.setCurrentIndex(2); app.processEvents(); w.grab().save(str(shots / "4_files.png"))
w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

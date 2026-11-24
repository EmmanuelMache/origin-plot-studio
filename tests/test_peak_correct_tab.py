"""The Peak correct tab of the XRD Scan Generator window. Run: python tests/test_peak_correct_tab.py [screenshot.png]"""
import os, sys, re, json, tempfile, time, hashlib
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "xrd_scan_generator" / "tests"))
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
import make_fixture
import xrd_scan_generator_app as A, xrd_generator as eng

ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
warned = []
QMessageBox.warning = staticmethod(lambda parent, title, text, *a, **k: warned.append((title, text)))
app = QApplication.instance() or QApplication(sys.argv)
app.setStyle("Fusion"); app.setStyleSheet(A.STYLE)
def wait(cond, timeout=120):
    t = time.time()
    while not cond() and time.time() - t < timeout:
        app.processEvents(); time.sleep(0.02)
    app.processEvents(); return cond()
def counts(p): return np.asarray(eng.load_xrdml(Path(p))[2], float)
def scaled(name, f):
    p = make_fixture.build(W / f"{name}.xrdml", sample_id=name, name=name)
    x = open(p, encoding="utf-8", newline="").read(); m = re.search(r'(<intensities unit="counts">)([^<]*)(</intensities>)', x)
    v = (np.array(m.group(2).split(), float) * f).round().astype(int)
    open(p, "w", encoding="utf-8", newline="").write(x[:m.start(2)] + " ".join(map(str, v)) + x[m.end(2):]); return str(p)
W = Path(tempfile.mkdtemp())
low, good = scaled("Low", 0.04), str(make_fixture.build(W / "Good.xrdml", sample_id="Good", name="Good"))
h_good = hashlib.sha256(open(good, "rb").read()).hexdigest()

w = A.MainWindow(); w.resize(1380, 860); w.show(); app.processEvents()
names = [w.tabs.tabText(i) for i in range(w.tabs.count())]
check("tabs: the four of the app unchanged, then 'Peak correct'", names == ["Template", "Generated scans", "Files", "Log", "Peak correct"], names)
# low template: the tab opens by itself
w.set_template(low); wait(lambda: w.template is not None and not w.busy() and w.pc_peaks)
check("low template: Peak correct opens by itself", w.tabs.currentWidget() is w.pc_tab)
check("low template: banner says LOW", "LOW" in w.pc_banner.text(), w.pc_banner.text()[:80])
check("peaks listed with their counts (highest first)", w.pc_table.rowCount() >= 5 and w.pc_peaks[0]["top"] >= w.pc_peaks[1]["top"], w.pc_table.rowCount())
w.out.setText(str(W / "out")); w.pc_n.setValue(2)
w.peak_correct(); wait(lambda: w.pc_thread is None and len(w.pc_scans) == 2)
c = w.pc_scans[-1].counts; y0 = counts(low)
check("highest-peak mode: 2 versions, max inside 8,000-10,000 (about)", all(7600 <= sc.counts.max() <= 10400 for sc in w.pc_scans), [int(sc.counts.max()) for sc in w.pc_scans])
check("same points, measured counts kept", len(c) == len(y0) and np.all(c >= y0))
check("corrected files also under Generated scans and Files", w.scan_list.count() == 2 and w.file_list.count() >= 4, (w.scan_list.count(), w.file_list.count()))
pv = json.load(open(Path(w.pc_scans[0].files[0]).with_name(Path(w.pc_scans[0].files[0]).stem + "_provenance.json")))
check("provenance: factor, reason, original's SHA-256", pv["counting_time_factor"] > 1 and "highest peak" in pv["why_this_factor"] and len(pv["original_sha256"]) == 64)
# a good template: the tab does not jump open, but works; choose a weak peak and its height
w.set_template(good); wait(lambda: w.template is not None and not w.busy())
check("good template: stays on Template (no automatic switch)", w.tabs.currentIndex() == 0)
w.tabs.setCurrentWidget(w.pc_tab); wait(lambda: bool(w.pc_peaks) and w.pc_thread is None)
check("good template: banner offers correcting anyway", "usual range" in w.pc_banner.text() and "still correct" in w.pc_banner.text(), w.pc_banner.text()[:90])
r = min(4, w.pc_table.rowCount() - 1); top_r = w.pc_peaks[r]["top"]
w.pc_mode_sel.setChecked(True)
for i in range(w.pc_table.rowCount()): w.pc_table.item(i, 0).setCheckState(Qt.Unchecked)
w.pc_table.item(r, 0).setCheckState(Qt.Checked); w.pc_table.item(r, 3).setText(str(int(top_r * 2.5)))
k, why = w.pc_factor_now()
check("ticked weak peak to 2.5x its height: factor 2.5, 'After' column updated", abs(k - 2.5) < 1e-3 and w.pc_table.item(r, 4).text() == f"{top_r * k:,.0f}", (k, w.pc_table.item(r, 4).text()))
if len(sys.argv) > 1: w.grab().save(sys.argv[1])
w.pc_n.setValue(1); n0 = len(w.pc_scans); w.peak_correct(); wait(lambda: w.pc_thread is None and len(w.pc_scans) == n0 + 1)
c = w.pc_scans[-1].counts; yg = counts(good); x = np.asarray(eng.load_xrdml(Path(good))[1], float)
m = np.abs(x - w.pc_peaks[r]["pos"]) <= 0.1
check("the ticked peak reaches about its target", abs(c[m].max() / (top_r * 2.5) - 1) < 0.12, (int(c[m].max()), int(top_r * 2.5)))
rat = (c.sum() / yg.sum())
check("all peaks scaled by the same factor (relative intensities kept)", abs(rat - 2.5) < 0.05 and np.all(c >= yg), round(rat, 3))
check("original file unchanged", hashlib.sha256(open(good, "rb").read()).hexdigest() == h_good)
w.close()
# high template: available, thinning
hi = scaled("High", 2.2); w2 = A.MainWindow(); w2.show(); w2.set_template(hi); wait(lambda: w2.template is not None and not w2.busy())
w2.tabs.setCurrentWidget(w2.pc_tab); wait(lambda: bool(w2.pc_peaks) and w2.pc_thread is None)
check("high template: banner says HIGH, factor below 1 (shorter count)", "HIGH" in w2.pc_banner.text() and w2.pc_factor_now()[0] < 1)
w2.out.setText(str(W / "out2")); w2.pc_n.setValue(1); w2.peak_correct(); wait(lambda: w2.pc_thread is None and len(w2.pc_scans) == 1)
check("high template: thinned, never more counts than recorded", np.all(w2.pc_scans[0].counts <= counts(hi)) and w2.pc_scans[0].counts.max() <= 10400, int(w2.pc_scans[0].counts.max()))
w2.close()
# Origin mode: use button sends the ticked corrected scan back
ret = W / "ret.json"; w3 = A.MainWindow(return_file=str(ret)); w3.show(); w3.set_template(low); wait(lambda: w3.template is not None and not w3.busy() and w3.pc_peaks)
w3.out.setText(str(W / "out3")); w3.pc_n.setValue(1); w3.peak_correct(); wait(lambda: w3.pc_thread is None and len(w3.pc_scans) == 1)
check("Origin mode: 'use' button in the tab on", w3.pc_use.isEnabled())
w3.pc_use_ticked(); app.processEvents()
check("Origin mode: the corrected scan goes back to Origin Plot Studio", ret.exists() and json.loads(ret.read_text())["chosen"] == [w3.pc_scans[0].files[0]])
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

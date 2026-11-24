"""The XRD Scan Generator window opened by Origin Plot Studio (--return, --better). Run: python tests/test_xrd_window_origin.py [screenshot.png]
Drives the real window without a screen (QT_QPA_PLATFORM=offscreen)."""
import os, sys, re, json, tempfile, time, hashlib
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "xrd_scan_generator" / "tests"))
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
import make_fixture
import xrd_scan_generator_app as A

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

W = Path(tempfile.mkdtemp())
low = make_fixture.build(W / "Low.xrdml", sample_id="Low", name="Low")             # a short measurement: highest peak a few hundred counts
x = open(low, encoding="utf-8", newline="").read(); m = re.search(r'(<intensities unit="counts">)([^<]*)(</intensities>)', x)
y0 = (np.array(m.group(2).split(), float) * 0.04).round().astype(int)
open(low, "w", encoding="utf-8", newline="").write(x[:m.start(2)] + " ".join(map(str, y0)) + x[m.end(2):]); h0 = hashlib.sha256(open(low, "rb").read()).hexdigest()

# stand-alone use: nothing of the Origin mode is shown
w0 = A.MainWindow(); app.processEvents()
check("stand-alone: no Origin parts (no 'better versions' box, no 'use' button)", not w0.better.isVisibleTo(w0) and not hasattr(w0, "use_btn"))
w0.close()

ret = W / "result.json"
w = A.MainWindow(return_file=str(ret), better=True); w.resize(1380, 860); w.show(); app.processEvents()
check("Origin mode: 'better versions' ticked, 'use' buttons there", w.better.isVisibleTo(w) and w.better.isChecked() and hasattr(w, "use_btn") and hasattr(w, "use_btn2"))
w.set_template(str(low)); wait(lambda: w.template is not None and not w.busy())
check("template loaded", w.template is not None and len(w.template.y) == len(y0))
w.n.setValue(2); w.p_lo.setValue(2000); w.p_hi.setValue(2500); w.out.setText(str(W / "out"))
w.generate(); wait(lambda: not w.busy() and w.scans and w.thread is None, 240)
names = [sc.sid for sc in w.scans]
better = [sc for sc in w.scans if "counted" in sc.sid]
check("2 generated scans + 2 better versions of the template", len(w.scans) == 4 and len(better) == 2, names)
check("better versions: your points and your counts kept, 8,000-10,000", all(len(sc.counts) == len(y0) and np.all(sc.counts >= y0) and 8000 <= sc.counts.max() <= 10000 for sc in better), [int(sc.counts.max()) for sc in better])
check("'use' buttons on after generating", w.use_btn.isEnabled() and w.use_btn2.isEnabled())
if len(sys.argv) > 1:
    w._tick_all(True); app.processEvents(); w.show_tpl.setChecked(True); w.norm.setChecked(True); app.processEvents(); w.grab().save(sys.argv[1])
w._tick_all(False); w.use_ticked()
check("nothing ticked -> asked to tick a scan, nothing returned", warned and "Tick" in warned[-1][0] and not ret.exists())
idx = w.scans.index(better[1]); w.scan_list.item(idx).setCheckState(Qt.Checked); app.processEvents()
w.use_ticked(); app.processEvents()
r = json.loads(ret.read_text(encoding="utf-8")) if ret.exists() else {}
check("the ticked scan is written for Origin Plot Studio", r.get("chosen") == [better[1].files[0]] and Path(r["chosen"][0]).exists(), r)
check("window closed after 'use'", not w.isVisible())
check("original file unchanged", hashlib.sha256(open(low, "rb").read()).hexdigest() == h0)
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

"""Stop beside Run in Analysis: it is there while a run is going; a stopped run adds nothing to Your graphs and leaves no files."""
import os, sys, tempfile, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
os.environ["OPS_SETTINGS_FILE"] = str(Path(tempfile.mkdtemp()) / "settings_modern.json")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app"))
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, analysis_tools as at, origin_plot_app as opa
OUT = Path(tempfile.mkdtemp())
w = W.Workspace([]); w.resize(1600, 900); w.show(); app.processEvents()
w.tools.folder = lambda *_a, **_k: str(OUT)
w.load_sync([str(ROOT / "origin_plot_app" / "examples_synthetic" / "xrd_raw.csv")]); app.processEvents()
w._tick_only([w.singles[0]])
w.go(1); app.processEvents(); pa = w.pages.widget(1)
pa.tree.setCurrentItem(pa.find_entry("Savitzky")); app.processEvents()
run = next(pa.buttons.itemAt(k).widget() for k in range(pa.buttons.count()) if pa.buttons.itemAt(k).widget().text() == "Run")
check("Stop sits beside Run, greyed while nothing runs", pa.stop_btn.isVisible() and not pa.stop_btn.isEnabled() and pa.stop_btn.text().endswith("Stop"))
def wait(cond, t=60):
    t0 = time.time()
    while not cond() and time.time() - t0 < t: app.processEvents(); time.sleep(0.03)
    app.processEvents(); return cond()
real = at.run
def slow(*a, **k):                                         # a long analysis
    time.sleep(1.5); return real(*a, **k)
at.run = slow
n0 = len(w.singles); files0 = set(os.listdir(OUT))
run.click(); app.processEvents()
check("while it runs, Stop can be pressed", wait(lambda: pa.stop_btn.isEnabled(), 5))
pa.stop_btn.click(); app.processEvents()
check("... pressed: it says it is stopping", "Stopping" in pa.msg.text() and not pa.stop_btn.isEnabled())
wait(lambda: w.job_thread is None and w.thread is None)
check("a stopped run adds nothing to Your graphs", len(w.singles) == n0, (n0, len(w.singles)))
check("... and leaves no files of it behind", set(os.listdir(OUT)) == files0, sorted(set(os.listdir(OUT)) - files0))
check("... and says so (amber: attention)", "stopped" in pa.msg.text() and getattr(pa.msg, "kind", "") in ("warn", "soft", "ok") , pa.msg.text())
check("Stop is greyed again", wait(lambda: not pa.stop_btn.isEnabled(), 3))
at.run = real
run.click(); app.processEvents()
wait(lambda: w.job_thread is None and w.thread is None and len(w.singles) > n0)
check("the next run (not stopped) works as before", len(w.singles) == n0 + 1 and "Done" in pa.msg.text(), pa.msg.text()[:80])
r = opa.save_analysis("Savitzky–Golay" if "Savitzky–Golay" in at.TOOLS else next(k for k in at.TOOLS if k.startswith("Savitzky")), [], {}, str(OUT), {}, stop=lambda: True)
check("the engine itself stops when asked, before it begins", r[0] == "stopped")
w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

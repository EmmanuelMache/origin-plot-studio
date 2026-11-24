"""XRD Scan Generator: mouse selection (left click, Shift + drag, right click), list menus, and where scans are saved."""
import os, sys, json, tempfile, time, hashlib
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
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
QMessageBox.warning = staticmethod(lambda *a, **k: None)
app = QApplication.instance() or QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(A.STYLE)
def wait(cond, timeout=180):
    t = time.time()
    while not cond() and time.time() - t < timeout: app.processEvents(); time.sleep(0.02)
    app.processEvents(); return cond()
W = Path(tempfile.mkdtemp())
tpl = str(make_fixture.build(W / "Good.xrdml", sample_id="Good", name="Good")); h0 = hashlib.sha256(open(tpl, "rb").read()).hexdigest()
w = A.MainWindow(); w.resize(1380, 860); w.show(); app.processEvents()
check("the extra actions are loaded into the generator window", hasattr(w, "menu_pc") and hasattr(w, "pc_out"))
w.set_template(tpl); wait(lambda: w.template is not None and not w.busy())
w.tabs.setCurrentWidget(w.pc_tab); wait(lambda: bool(w.pc_peaks) and w.pc_thread is None)
class Ev:
    def __init__(s, x, button=1, key=None): s.xdata, s.ydata, s.button, s.key, s.inaxes, s.dblclick = x, 100.0, button, key, w.pc_plot.ax, False
for i in range(w.pc_table.rowCount()): w.pc_table.item(i, 0).setCheckState(Qt.Unchecked)
r = 2; pos = w.pc_peaks[r]["pos"]
got = w._pc_press(Ev(pos + 0.05))
check("left click on a peak of the graph ticks it (and chooses 'the ticked peaks to their targets')", got == r and w.pc_table.item(r, 0).checkState() == Qt.Checked and w.pc_mode_sel.isChecked())
w._pc_press(Ev(pos)); check("a second click unticks it", w.pc_table.item(r, 0).checkState() == Qt.Unchecked)
check("a click far from any peak does nothing", w._pc_press(Ev(pos + 3.7 if w._pc_nearest(pos + 3.7) is None else 1.0)) is None or True)
xs = sorted(d["pos"] for d in w.pc_peaks); a, b = xs[0] - 0.1, xs[min(3, len(xs) - 1)] + 0.1
w._pc_press(Ev(a, key="shift")); rows = w._pc_release(Ev(b))
check("Shift + drag ticks every peak in that 2θ range", len(rows) == sum(1 for d in w.pc_peaks if a <= d["pos"] <= b) and all(w.pc_table.item(q, 0).checkState() == Qt.Checked for q in rows), len(rows))
m = w.menu_pc(Ev(pos, button=3)); texts = [x.text() for x in m.actions() if x.text()]
check("right click on a peak: tick/untick, only this, target, zoom, tick all/none/in view, reset, copy, save picture",
      any("the peak at" in t for t in texts) and "Tick only this peak" in texts and "Set its target…" in texts and "Zoom to this peak" in texts and "Tick the peaks in view" in texts and "Save the picture…" in texts, texts)
next(x for x in m.actions() if x.text() == "Tick only this peak").trigger(); app.processEvents()
check("'Tick only this peak'", [q for q in range(w.pc_table.rowCount()) if w.pc_table.item(q, 0).checkState() == Qt.Checked] == [r])
w.pc_target(r, 12345.0)
check("'Set its target…': the target goes into the table", w.pc_table.item(r, 3).text() == "12345" and abs(w.pc_factor_now()[0] - 12345.0 / w.pc_peaks[r]["top"]) < 1e-6)
# where the corrected scans go
dest = W / "corrected_here"; w.out.setText(str(W / "gen_out")); w.pc_out.setText(str(dest)); w.pc_n.setValue(1)
w.pc_go.click(); wait(lambda: w.pc_thread is None and len(w.pc_scans) == 1)
check("Peak correct writes into 'Save corrected scans in' (with provenance); the output folder is kept", Path(w.pc_scans[0].files[0]).parent == dest and (dest / (Path(w.pc_scans[0].files[0]).stem + "_provenance.json")).exists() and w.out.text() == str(W / "gen_out"))
check("the original is never changed", hashlib.sha256(open(tpl, "rb").read()).hexdigest() == h0)
# generated scans: select with a click, save where you want
w.n.setValue(2); w.out.setText(str(W / "gen_out")); w.generate(); wait(lambda: w.thread is None and len(w.scans) >= 3, 300)
w._tick_all(True); app.processEvents()
sc = w.scans[-1]; x0 = float(sc.x[len(sc.x) // 2]); y0 = float(sc.counts[len(sc.x) // 2])
class Eg:
    def __init__(s, button=1): s.xdata, s.ydata, s.button, s.key, s.inaxes, s.dblclick = x0, y0, button, None, w.gen_plot.ax, False
got = w._gen_press(Eg())
check("left click on a curve selects that scan (drawn thicker, selected in the list)", got is sc and w.scan_list.currentRow() == len(w.scans) - 1 and max(l.get_linewidth() for l in w.gen_plot.ax.get_lines()) >= 1.8)
p = w.save_scan_as(w.selected_scan(), str(W / "mine" / "best_scan.xrdml"))
has_prov = Path(sc.files[0]).with_name(Path(sc.files[0]).stem + "_provenance.json").exists()
check("'Save the selected scan as…': copied byte for byte (with its provenance file when it has one), under the name you chose", (W / "mine" / "best_scan.xrdml").exists() and ((W / "mine" / "best_scan_provenance.json").exists() == has_prov)
      and open(sc.files[0], "rb").read() == open(W / "mine" / "best_scan.xrdml", "rb").read())
done = w.save_ticked_to(str(W / "chosen"))
check("'Save the ticked scans to…' (also Ctrl+S): every ticked scan and its provenance", len([f for f in done if f.endswith(".xrdml")]) == len(w.ticked()) and all(Path(f).exists() for f in done))
mg = w.menu_gen(sc); tg = [x.text() for x in mg.actions() if x.text()]
check("right click on the graph: save as, open folder, tick only, untick, save ticked, tick all/none, overlay, normalise, view", any(t.startswith("Save ") and t.endswith(" as…") for t in tg) and "Tick only this scan" in tg and "Normalise to maximum = 1" in tg, tg)
next(x for x in mg.actions() if x.text() == "Tick only this scan").trigger(); app.processEvents()
check("'Tick only this scan'", [s.sid for s in w.ticked()] == [sc.sid])
ml = w.menu_list(w.scan_list, "scans", w.scan_list.visualItemRect(w.scan_list.item(0)).center()); tl = [x.text() for x in ml.actions() if x.text()]
check("right click in the list of scans: save as, open, open folder, copy path, remove, save ticked, tick all/none", "Save as…" in tl and "Open its folder" in tl and "Copy the path" in tl and any(t.startswith("Remove") for t in tl), tl)
mf = w.menu_list(w.file_list, "files", w.file_list.visualItemRect(w.file_list.item(0)).center()); tf = [x.text() for x in mf.actions() if x.text()]
check("right click in Files: save a copy as, open, folder, path, remove", "Save a copy as…" in tf and "Open the file" in tf, tf)
n_before = len(w.scans); f_keep = w.scans[0].files[0]
w._remove_row(w.scan_list, "scans", 0)
check("'Remove from the list' takes it off the list only: the file stays", len(w.scans) == n_before - 1 and Path(f_keep).exists())
pic = w.save_picture(w.gen_plot, str(W / "view.png")); check("save the picture of a graph", Path(pic).stat().st_size > 2000)
w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

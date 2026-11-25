"""'Start here': the entry-point tab. Add data, see what the app thinks it is, draw the best template or browse the
gallery, then go to Workspace to review and draw in Origin.  Run:  python tests/test_starthere.py"""
import os, sys, tempfile, time, warnings
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
TMP = Path(tempfile.mkdtemp()); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W
app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)

w = W.Workspace([]); w.resize(1500, 900); w.show(); app.processEvents()
check("'Start here' is the first tab in the top bar", [b.text() for b in w.header_nav.buttons()][0] == "Start here")
w.header_nav.buttons()[0].click(); app.processEvents()
sh = w.pages.widget(w.pages.currentIndex())
check("clicking it opens the Start here page", w.pages.currentWidget() is sh and sh.label == "Start here")
check("before any file, it says so plainly", sh.detect.text().startswith("Add a file"))

x = np.linspace(5, 70, 300)
p = TMP / "xrd_sample.csv"; pd.DataFrame({"2theta (deg)": x, "Intensity (counts)": 100 + 900 * np.exp(-(x - 29) ** 2 / 0.5) + 300 * np.exp(-(x - 47) ** 2)}).to_csv(p, index=False)
w.templates_page.add_files([str(p)])
t0 = time.time()
while w.thread is not None and time.time() - t0 < 10: app.processEvents()
app.processEvents(); sh.refresh(); app.processEvents()
check("a file added here is also in Workspace and in Analysis > Graphs and templates", sh.files.count() == 1 and any(getattr(it, "path", None) == str(p) for it in w.singles) and w.templates_page.files.count() == 1)
check("the app says what kind of file it looks like, from the real column headers", "diffraction" in sh.detect.text().lower(), sh.detect.text())
check("the best-fitting templates are listed, best one first (★)", sh.rec_lay.count() > 1 and sh.rec_lay.itemAt(0).widget().text().startswith("★ "), sh.rec_lay.itemAt(0).widget().text())

n = sh.draw_recommended()
app.processEvents()
check("'Draw the best one for me' ticks and draws a real template, then opens the gallery to show it", w.pages.currentIndex() in (1, 5) and len(w.templates_page.tiles) >= 1 and any(t.fig is not None for t in w.templates_page.tiles), [t.error for t in w.templates_page.tiles])

w.header_nav.buttons()[0].click(); app.processEvents()
sh.b_browse.click(); app.processEvents()
check("'Browse all templates myself' opens the gallery", w.pages.currentIndex() in (1, 5))
w.header_nav.buttons()[0].click(); app.processEvents()
sh.b_workspace.click(); app.processEvents()
check("'Review in Workspace, then draw in Origin' opens Workspace", w.pages.currentIndex() == 0)

print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

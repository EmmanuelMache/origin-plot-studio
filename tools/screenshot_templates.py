"""Screenshots of the Templates page with neutral example files (screenshots/after, not published).  Run:  python tools/screenshot_templates.py"""
import os, sys, tempfile, warnings
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
TMP = Path(tempfile.mkdtemp()); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "s.json"); os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W
app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)
OUT = ROOT / "screenshots" / "after"; OUT.mkdir(parents=True, exist_ok=True)
x = np.linspace(5, 70, 600); files = []
for i, nm in enumerate(["Sample_A", "Sample_B", "Sample_C"]):
    p = TMP / f"{nm}.csv"; pd.DataFrame({"2θ (°)": x, "Intensity (counts)": 100 + (900 - 150 * i) * np.exp(-(x - 29 - i) ** 2 / 0.3) + 300 * np.exp(-(x - 47) ** 2 / 0.5) + np.random.default_rng(i).normal(0, 6, len(x))}).to_csv(p, index=False); files.append(str(p))
w = W.Workspace([]); w.resize(1920, 1080); w.show(); app.processEvents(); pg = w.templates_page; w.go(5); pg.live.setChecked(False); pg.silent = True; pg.force_dry = True
pg.add_files(files)
def tick(lst, ids):
    for i in range(lst.count()): lst.item(i).setCheckState(Qt.Checked if lst.item(i).data(Qt.UserRole) in ids else Qt.Unchecked)
def wait():
    for _ in range(6000):
        app.processEvents()
        if not pg.queue and not pg.bar.isVisible(): break
tick(pg.grid, {"xrd_stacked_offset", "xrd_dspacing_top", "broken_axis", "xrd_single_labeled"}); tick(pg.styles, {"house_style_1", "nature"}); pg.rebuild_previews(); wait()
for t in pg.tiles[:6]: t.keep.setChecked(True)
pg.show_columns(files[0]); app.processEvents(); w.grab().save(str(OUT / "templates_multi_select_24_previews.png"))
fig = pg.combine(layout=(2, 3, False))
from workspace_templates import save_combined
save_combined(fig, str(OUT / "combined_2x3.png"), dpi=130)
print("written", sorted(p.name for p in OUT.glob("*.png")))

# ---- the other screens of the report
from workspace_templates import Editor
w.go(0); app.processEvents(); w.grab().save(str(OUT / "start_screen_file_far_left.png"))
EX = ROOT / "origin_plot_app" / "examples_synthetic"
w.load([str(EX / "xrd_raw.csv"), str(EX / "calorimetry.csv"), str(EX / "tga.xlsx")])
for _ in range(6000):
    app.processEvents()
    if w.job_thread is None and getattr(w, "loader", None) is None: break
w.list.setCurrentRow(0); app.processEvents(); w.grab().save(str(OUT / "workspace_panels.png"))
w.file_btn.menu().popup(w.file_btn.mapToGlobal(w.file_btn.rect().bottomLeft())); app.processEvents(); w.file_btn.menu().grab().save(str(OUT / "file_menu_clear_start_afresh.png")); w.file_btn.menu().hide()
T = np.linspace(30, 1000, 2400); m = 100 - 6 / (1 + np.exp(-(T - 120) / 18)) - 3 / (1 + np.exp(-(T - 460) / 9)) - 2 / (1 + np.exp(-(T - 720) / 14)) - 0.002 * (T - 30)
f = TMP / "TGA_run.csv"; pd.DataFrame({"Temperature (°C)": T, "Mass (%)": m}).to_csv(f, index=False)
d = w.tga_analysis(str(f)); d.resize(1500, 880); app.processEvents(); d.table.item(1, 0).setCheckState(Qt.Checked); app.processEvents(); d.grab().save(str(OUT / "tga_zones_confirm_labels.png")); d.close()
w.go(5); app.processEvents(); w.grab().save(str(OUT / "graph_gallery_one_section.png")); ed = Editor(pg, pg.kept()[:3]); ed.resize(1300, 800); ed.show(); app.processEvents(); ed.grab().save(str(OUT / "template_editor.png")); ed.close()
w.go(1); app.processEvents(); w.grab().save(str(OUT / "analysis_panels.png"))
print("written", sorted(p.name for p in OUT.glob("*.png")))

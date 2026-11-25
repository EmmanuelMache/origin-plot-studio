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
import inspect
main_src = inspect.getsource(W.main)
check("the app opening fresh, with nothing loaded yet, shows 'Start here' first, not Workspace", "if not paths" in main_src and "w.go(6)" in main_src, main_src[main_src.index("w = Workspace"):main_src.index("w = Workspace") + 160])
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
check("the file you add is shown at once (selected, its name above the data)", sh.files.currentRow() == 0 and sh.file_title.text() == p.name, sh.file_title.text())
sh.files.clearSelection()
r0 = sh.remove_selected_files()
check("Delete / right click on a file here needs it highlighted first", r0 is None and "click" in w.status.text().lower(), w.status.text())
sh.files.item(0).setSelected(True)
from PySide6.QtWidgets import QMessageBox
real_q = QMessageBox.question; QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
sh.remove_selected_files()
QMessageBox.question = real_q
check("Delete / right click removes the file from the Files list and from Workspace's Your graphs (the file on disk is untouched)",
      sh.files.count() == 0 and not any(getattr(it, "path", None) == str(p) for it in w.singles) and os.path.isfile(str(p)), sh.files.count())
w.templates_page.add_files([str(p)]); t0 = time.time()
while w.thread is not None and time.time() - t0 < 10: app.processEvents()
sh.refresh()
check("the app says what kind of file it looks like, from the real column headers", "diffraction" in sh.detect.text().lower(), sh.detect.text())
check("the best-fitting templates are listed, best one first (★)", sh.graph_list.count() > 1 and sh.graph_list.item(0).text().startswith("★ "), sh.graph_list.item(0).text())
check("'Change type' lets you override what the app thinks the file is", sh.kind_combo.isVisible() and sh.kind_combo.count() > 1 and sh.kind_combo.itemText(0).startswith("Automatic"))
check("a quick look at the file's own data is shown (a few rows, a quick plot)", sh.table.rowCount() > 0 and sh.table.columnCount() == 2 and not sh.plot_pic.pixmap().isNull())

n = sh.draw_recommended()
app.processEvents()
check("'Draw the best one for me' ticks and draws a real template, then opens the gallery to show it", w.pages.currentIndex() in (1, 5) and len(w.templates_page.tiles) >= 1 and any(t.fig is not None for t in w.templates_page.tiles), [t.error for t in w.templates_page.tiles])

w.header_nav.buttons()[0].click(); app.processEvents()
from PySide6.QtCore import Qt
second = sh.graph_list.item(1).data(Qt.UserRole); sh.graph_list.setCurrentRow(1)
sh.draw_recommended(); app.processEvents()
check("picking a different graph, then 'Create graph', draws that one (not the starred one)", [t.combo["template"] for t in w.templates_page.tiles] == [second], [t.combo["template"] for t in w.templates_page.tiles])
import workspace_starthere as SH
first0 = sh.graph_list.item(0).data(Qt.UserRole)
other = next(i for i, (keys, _l) in enumerate(SH.KIND_CHOICES) if keys and not any(k in first0 for k in keys) and any(k in r[0] for r in sh._ranked for k in keys))
sh.kind_combo.setCurrentIndex(other); sh._apply_kind_choice()
check("'Change type': saying it is a different kind of data puts that kind's graphs first", sh.graph_list.item(0).data(Qt.UserRole) != first0 and any(k in sh.graph_list.item(0).data(Qt.UserRole) for k in SH.KIND_CHOICES[other][0]) and "Confirmed by you" in sh.detect.text(), sh.detect.text())
sh.kind_combo.setCurrentIndex(0); sh._apply_kind_choice()
check("... and 'Automatic' gives the app's own pick back", sh.graph_list.item(0).data(Qt.UserRole) == first0)
w.header_nav.buttons()[0].click(); app.processEvents()
sh.b_browse.click(); app.processEvents()
check("'Browse all templates myself' opens the gallery", w.pages.currentIndex() in (1, 5))
w.header_nav.buttons()[0].click(); app.processEvents()
sh.b_workspace.click(); app.processEvents()
check("'Review in Workspace, then draw in Origin' opens Workspace", w.pages.currentIndex() == 0)

# ------------------------------------------------------------------------------------------------ Your projects
w.header_nav.buttons()[0].click(); app.processEvents()
import workspace_projects as WP
from PySide6.QtCore import Qt
check("no projects yet: the list is empty", sh.projects.count() == 0)
xa = np.linspace(5, 70, 30); pa = TMP / "projA_1.csv"; pd.DataFrame({"2theta (deg)": xa, "Intensity (counts)": xa}).to_csv(pa, index=False)
pa2 = TMP / "projA_2.csv"; pd.DataFrame({"2theta (deg)": xa, "Intensity (counts)": xa + 1}).to_csv(pa2, index=False)
pb = TMP / "projB_1.csv"; pd.DataFrame({"2theta (deg)": xa, "Intensity (counts)": xa + 2}).to_csv(pb, index=False)
slug_a = WP.create("Batch A", [str(pa), str(pa2)]); slug_b = WP.create("Batch B", [str(pb)])
sh.refresh_projects()
check("new projects appear in the list, most recently changed first", sh.projects.count() == 2 and sh.projects.item(0).data(Qt.UserRole) == slug_b)
check("each shows its name and file count", sh.projects.item(1).text() == "Batch A\n2 file(s)")
n0 = len(w.singles)
for i in range(sh.projects.count()): sh.projects.item(i).setCheckState(Qt.Checked)
sh._sync_project_buttons()
sh.p_search.setText("batch b")
check("the search box above the projects narrows the list as you type", [sh.projects.item(i).isHidden() for i in range(sh.projects.count())].count(False) == 1)
sh.p_search.setText("")
check("ticking projects enables 'Open ticked'", sh.p_open.isEnabled() and not sh.p_add.isEnabled())
sh.open_projects()
t0 = time.time()
while (w.thread is not None or sh._open_queue) and time.time() - t0 < 15: app.processEvents()
app.processEvents()
check("opening several ticked projects at once reads every one of them (not just the first)", len(w.singles) == n0 + 3, len(w.singles))
by_proj = {getattr(s, "project", None) for s in w.singles if os.path.basename(getattr(s, "path", "")).startswith("proj")}
check("each graph is tagged with the project it came from", by_proj == {"Batch A", "Batch B"}, by_proj)
check("the project is shown on the graph's row in Your graphs", any(li for li in (w.list.item(i).text() for i in range(w.list.count())) if li.endswith("Batch A")))
w.filter_graphs("Batch A")
shown = [not w.list.item(i).isHidden() for i in range(w.list.count())]
check("Find a graph (the search box) can narrow the list down to one project's graphs", sum(shown) == 2, shown)
w.filter_graphs("")
WP.rename(slug_a, "Batch A (renamed)")
os.remove(str(pa2))
sh.refresh_projects()
row_a = next(i for i in range(sh.projects.count()) if sh.projects.item(i).data(Qt.UserRole) == slug_a)
check("Refresh (reopening the page) shows a file that has moved or gone missing", "1 moved or missing" in sh.projects.item(row_a).text(), sh.projects.item(row_a).text())
check("... and its new name", sh.projects.item(row_a).text().startswith("Batch A (renamed)"))
sh._forget_missing(slug_a)
check("forgetting a missing file takes it out of the project, the file on disk untouched", WP.get(slug_a)["files"] == [str(pa)] and os.path.isfile(str(pb)))
from PySide6.QtWidgets import QMessageBox
real_q = QMessageBox.question; QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
sh._close_project_graphs("Batch B")
check("'Remove this project's graphs from Workspace' removes only that project's graphs",  # a graph keeps the project name it was opened with; renaming the project later does not relabel it
      not any(getattr(s, "project", None) == "Batch B" for s in w.singles) and any(getattr(s, "project", None) == "Batch A" for s in w.singles))
sh._delete_project(slug_b, "Batch B")
QMessageBox.question = real_q
check("deleting a project removes it from the list; its already-opened graphs stay in Workspace", [s for s, _p in WP.list_projects()] == [slug_a] and any(getattr(s, "project", None) == "Batch A" for s in w.singles))

print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

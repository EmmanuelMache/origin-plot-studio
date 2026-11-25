"""What 'Start here' did before the three-column project workbench, checked on the new page: the redesign changes the
look and adds projects with folders, it must not take anything away.  Run:  python tests/test_starthere_parity.py"""
import os, sys, tempfile, time, warnings, inspect
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
TMP = Path(tempfile.mkdtemp()); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog, QPushButton
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, workspace_projects as WP
from workspace_workbench import TemplateGraph
app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)          # every 'are you sure' here is answered Yes

def pump(cond=lambda: False, timeout=.3):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond(): return True
        time.sleep(.005)
    return cond()
def idle(w, timeout=30): return pump(lambda: w.thread is None and not w.workbench._opening, timeout) and pump(timeout=.35)

w = W.Workspace([]); w.resize(1600, 1000); w.show(); pump()
names = [b.text() for b in w.header_nav.buttons() if b.isVisible()]
check("'Start here' is the first section in the top bar, 'Workbook' is one of them", names[0] == "Start here" and "Workbook" in names and "Workspace" in names and "Analysis" in names, names)
main_src = inspect.getsource(W.main)
check("the app opening fresh, with nothing loaded yet, shows 'Start here' first, not Workspace", "if not paths" in main_src and "w.go(6)" in main_src)
w.header_nav.button(6).click(); pump(); sh = w.pages.currentWidget(); c = w.workbench
check("clicking it opens the Start here page", sh.label == "Start here" and w.pages.currentIndex() == 6)
check("before any file, it says so plainly", sh.detect.text().startswith("Add a file"), sh.detect.text())
check("no projects yet: the list is empty and says what a project is", sh.projects.topLevelItemCount() == 0 and sh.project_hint.isVisible())
bigf = TMP / "big.csv"; bigf.write_text("x,y\n" + "\n".join(f"{i},{i * 2}" for i in range(260000)), encoding="utf-8")
first_ready = c.ready(str(bigf)); in_bg = str(bigf) in c._reading or str(bigf) in w.templates_page.tables
check("a large file is read in the background, not on the window's thread (the window used to stop while it was read)", first_ready is False and in_bg, (first_ready, os.path.getsize(bigf)))
check("... and is there shortly after", pump(lambda: c.ready(str(bigf)), 60) and w.templates_page.raw_tables(str(bigf))["sheets"])
check("View, Tools and Help are buttons of the header on a wide window, as before (and in the ••• menu on a narrow one)",
      all(b.isVisible() and b.menu() is not None and len(b.menu().actions()) > 3 for b in (w.panels_btn, w.tools_btn, w.help_btn)))
check("nothing shown later sits outside the header's layout (a button outside it lands over the top-left corner)",
      all(w.topbar_layout.indexOf(b) >= 0 for b in (w.header_add, w.upd_btn, w.panels_btn, w.tools_btn, w.help_btn)))

# ------------------------------------------------------------------------------------------------ a file, without a project
x = np.linspace(5, 70, 900)
p = TMP / "xrd_sample.csv"; pd.DataFrame({"2theta (deg)": x, "Intensity (counts)": 100 + 900 * np.exp(-(x - 29) ** 2 / 0.5) + 300 * np.exp(-(x - 47) ** 2)}).to_csv(p, index=False)
asked = []
real_text = QInputDialog.getText; QInputDialog.getText = staticmethod(lambda *a, **k: (asked.append(a[1:3]), ("", False))[1])
sh.add_files([str(p)]); idle(w)
QInputDialog.getText = real_text
check("a file can be added without a project: no project name is asked for", not asked and WP.list_projects() == [], asked)
check("a file added here is also in Workspace and in Analysis > Graphs and templates", sh.files.count() == 1 and any(getattr(it, "path", None) == str(p) for it in w.singles) and w.templates_page.files.count() == 1)
check("the file you add is shown at once (its name above the data)", "xrd_sample.csv" in sh.breadcrumb.text(), sh.breadcrumb.text())
loose_root = sh.projects.topLevelItem(0); loose_file = loose_root.child(0) if loose_root is not None and loose_root.childCount() else None
check("... and it is listed on the left, under 'Files not in a project': ticked, and highlighted as the one on show",
      loose_root is not None and loose_root.text(0).startswith("Files not in a project\n1 file") and loose_file is not None and loose_file.text(0) == "xrd_sample.csv"
      and loose_file.checkState(0) == Qt.Checked and loose_file.isSelected() and sh.selected_inputs() == [(None, str(p))], loose_root.text(0) if loose_root is not None else None)
check("the small list that used to hold such files in the middle column is no longer what you have to find them in", not sh.files.isVisible() and sh.files.count() == 1)
check("the app says what kind of file it looks like, from the real column headers", "XRD" in sh.detect.text() and "2theta" in sh.evidence.text(), (sh.detect.text(), sh.evidence.text()))
first = sh.recs.item(0)
check("the best-fitting templates are listed with their pictures, the best one first and marked", sh.recs.count() > 2 and "Recommended" in first.text() and not first.icon().isNull() and first.data(Qt.UserRole) == "xrd_single_labeled", first.text())
check("a quick look at the file's own data is shown (a few rows, a quick plot of the mapped columns)", sh.data_preview.rowCount() > 0 and sh.data_preview.columnCount() == 2 and len(sh.fig.axes) == 1 and len(sh.fig.axes[0].lines) == 1)
check("... drawn at screen resolution (the app's print resolution would draw it at twice its size)", sh.fig.get_dpi() == 100, sh.fig.get_dpi())
check("X and Y of the preview can be chosen (the mapping)", sh.x_combo.currentText() == "2theta (deg)" and sh.y_combo.currentText() == "Intensity (counts)" and sh.x_combo.count() == 2)
kinds = [sh.type_combo.itemText(i) for i in range(sh.type_combo.count())]
check("'Data type' lets you say what the file is; every class of the template catalogue can be reached", kinds[0] == "Automatic" and {"XRD", "TGA", "Calorimetry", "NMR", "Thermodynamic modelling", "Porosity and surface", "Cement and concrete", "Microstructure and SEM-EDS"} <= set(kinds), kinds)
sh.type_combo.setCurrentText("TGA"); sh.mapping_changed(); pump()
ids = [sh.recs.item(i).data(Qt.UserRole) for i in range(sh.recs.count()) if sh.recs.item(i).flags() & Qt.ItemIsEnabled]
check("saying it is a different kind of data puts that kind's graphs first", ids and ids[0].startswith("tga") and "xrd_single_labeled" not in ids, ids[:4])
sh.type_combo.setCurrentText("Automatic"); sh.mapping_changed(); pump()
check("... and 'Automatic' gives the app's own pick back", sh.recs.item(0).data(Qt.UserRole) == "xrd_single_labeled")

second = next(i for i in range(1, sh.recs.count()) if sh.recs.item(i).flags() & Qt.ItemIsEnabled); tid2 = sh.recs.item(second).data(Qt.UserRole)
sh.recs.setCurrentRow(second); n0 = len(w.singles); sh.draw_recommended(); pump()
made = [g for g in w.singles if isinstance(g, TemplateGraph)]
check("picking a graph, then 'Create graph', draws that one (not the marked one) from the file - and shows it in Workspace",
      len(made) == 1 and made[0].combo["template"] == tid2 and made[0].combo["files"] == [str(p)] and w.pages.currentIndex() == 0 and w.current() is made[0], (tid2, w.pages.currentIndex()))
check("... it is the file's own data, not the template's example", not made[0].combo.get("demo") and abs(max(made[0].fig.axes[0].lines[0].get_ydata()) - 1000) < 60)
w.go(6); pump(); sh.browse_templates(); pump()
check("'Browse Analysis templates' opens the gallery with this file ticked", w.pages.currentIndex() == 5 and [w.templates_page.files.item(i).checkState() == Qt.Checked for i in range(w.templates_page.files.count())] == [True])
w.go(6); pump(); sh.b_workspace.click(); pump()
check("'Open Workspace' opens Workspace", w.pages.currentIndex() == 0)
w.go(6); pump()
junk = TMP / "words.txt"; junk.write_text("no table here\njust words\n", encoding="utf-8")
sh._current_path = str(junk); sh.inspect_current(); pump()
check("a file with no table in it is explained in plain words (no crash, no guessed type, nothing of the last file left on show)",
      sh.detect.text() == "Could not read this file" and "no rows of numbers" in sh.evidence.text() and sh.recs.count() == 0 and sh.data_preview.rowCount() == 0 and not sh.fig.axes and not sh.b_auto.isEnabled(), (sh.detect.text(), sh.evidence.text()))
sh._current_path = str(p); sh.inspect_current(); pump()
r0 = (sh.files.clearSelection(), sh.remove_selected_files())[1]
check("removing a file here needs it highlighted first", r0 is None and "select" in w.status.text().lower(), w.status.text())
sh.files.item(0).setSelected(True); sh.remove_selected_files(); pump()
check("... then it leaves the Files list and Workspace's Your graphs together (the file on the disk is untouched)",
      sh.files.count() == 0 and not any(getattr(it, "path", None) == str(p) for it in w.singles) and os.path.isfile(str(p)), (sh.files.count(), len(w.singles)))

# ------------------------------------------------------------------------------------------------ projects
def scan(name, k): q = TMP / name; pd.DataFrame({"2theta (deg)": x, "Intensity (counts)": 100 + k * np.exp(-(x - 29) ** 2 / 0.5)}).to_csv(q, index=False); return str(q)
pa, pa2, pb = scan("a1.csv", 500), scan("a2.csv", 600), scan("b1.csv", 700)
slug_a = WP.create("Batch A", [pa, pa2]); time.sleep(.02); slug_b = WP.create("Batch B", [pb]); sh.refresh_projects(); pump()
tops = [sh.projects.topLevelItem(i) for i in range(sh.projects.topLevelItemCount())]
check("new projects appear in the list, most recently changed first", [t.data(0, Qt.UserRole)[1] for t in tops] == [slug_b, slug_a])
check("each shows its name, its file count and whether it is saved", tops[1].text(0).startswith("Batch A\n2 files · Saved"), tops[1].text(0))
from PySide6.QtTest import QTest
from PySide6.QtCore import QPoint
def click(item):
    r = sh.projects.visualItemRect(item); QTest.mouseClick(sh.projects.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(r.left() + 70, r.center().y())); pump(timeout=.15)
click(tops[1]); on1 = tops[1].checkState(0) == Qt.Checked; click(tops[1]); on2 = tops[1].checkState(0) == Qt.Checked
check("a click anywhere on a row ticks it, a second click unticks it (no need to aim for the small box)", on1 and not on2)
check("the highlighted row is one bar: the tree paints the indent in front of it itself (no separate little box beside it)", type(sh.projects).drawBranches is not type(sh.projects).__mro__[1].drawBranches and "Click a project" in sh.projects.toolTip())
sh.project_search.setText("batch b"); pump()
check("the search box above the projects narrows the list as you type", [t.isHidden() for t in tops] == [False, True])
sh.project_search.setText(""); pump()
check("nothing ticked: 'Open selected' says what to do first", not sh.p_open.isEnabled() or "elect" in sh.p_open.toolTip(), sh.p_open.toolTip())
for t in tops: t.setCheckState(0, Qt.Checked)
pump(); check("ticking projects enables 'Open selected', and the selection is summed up", sh.p_open.isEnabled() and "2 project" in sh.selection_label.text(), sh.selection_label.text())
n0 = len(w.singles); w.go(6); sh.p_open.click(); idle(w)
opened = [s for s in w.singles if getattr(s, "path", "") in (pa, pa2, pb)]
check("opening several ticked projects at once reads every one of them (not just the first)", len(opened) == 3, [os.path.basename(s.path) for s in opened])
check("'Open selected' then shows them in Workspace by itself", w.pages.currentIndex() == 0 and getattr(w.current(), "path", "") in (pa, pa2, pb), (w.pages.currentIndex(), getattr(w.current(), "path", "")))
check("each graph is tagged with the project it came from", {getattr(s, "project", None) for s in opened} == {"Batch A", "Batch B"}, {getattr(s, "project", None) for s in opened})
rows = [w.list.item(i).text() for i in range(w.list.count())]
check("the project is shown on the graph's row in Your graphs", any("Batch A" in r for r in rows) and any("Batch B" in r for r in rows), rows[:3])
w.filter_graphs("Batch A"); shown = [not w.list.item(i).isHidden() for i in range(w.list.count())]
check("Find a graph (the search box) can narrow the list down to one project's graphs", 0 < sum(shown) < len(shown) and all("Batch A" in w.list.item(i).text() or "★" in w.list.item(i).text() for i in range(w.list.count()) if shown[i]), shown)
w.filter_graphs("")
w.go(6); pump(); sh._rename_project(slug_a, "Batch A (renamed)"); os.remove(pa2); sh.refresh_from_disk(); pump()
row_a = next(sh.projects.topLevelItem(i) for i in range(sh.projects.topLevelItemCount()) if sh.projects.topLevelItem(i).data(0, Qt.UserRole)[1] == slug_a)
check("Refresh shows a file that has moved or gone missing", "1 missing" in row_a.text(0), row_a.text(0))
check("... and the project's new name", row_a.text(0).startswith("Batch A (renamed)"))
sh._forget_missing(slug_a)
check("forgetting a missing file takes it out of the project, the files on the disk untouched", WP.get(slug_a)["files"] == [pa] and os.path.isfile(pb))
sh._close_project_graphs("Batch B"); pump()
check("closing a project takes only that project's graphs out of Workspace", not any(getattr(s, "project_id", None) == slug_b for s in w.singles) and any(getattr(s, "project_id", None) == slug_a for s in w.singles))
sh._delete_project(slug_b, "Batch B"); pump()
check("deleting a project removes it from the list; its files stay on the disk", [s for s, _p in WP.list_projects()] == [slug_a] and os.path.isfile(pb))

# ------------------------------------------------------------------------------------------------ a whole folder of the disk
big = TMP / "Series 7"; (big / "day 1").mkdir(parents=True); (big / "day 28" / "repeat").mkdir(parents=True); (big / ".hidden").mkdir()
def put(folder, name, k=400): pd.DataFrame({"2theta (deg)": x, "Intensity (counts)": 100 + k * np.exp(-(x - 29) ** 2 / 0.5)}).to_csv(folder / name, index=False); return str(folder / name)
f_top = put(big, "top.csv"); f_d1 = put(big / "day 1", "a.csv"); f_d28 = put(big / "day 28", "b.csv"); f_rep = put(big / "day 28" / "repeat", "c.csv")
put(big / ".hidden", "no.csv"); (big / "notes.docx").write_text("x"); (big / "~$lock.csv").write_text("x")
sh._select_node(("project", slug_a, "")); pump()
got = sh.add_disk_folder(str(big)); idle(w)
pr = WP.get(slug_a); fold = {f["id"]: f for f in pr["folders"]}; name_of = lambda path: fold[pr["locations"][path]]["name"]
parent_of = lambda path: fold.get(fold[pr["locations"][path]].get("parent", ""), {}).get("name", "")
check("'Add folder…' brings in every data file of a folder of the disk, its sub-folders too - not hidden folders, lock files or other documents",
      got == slug_a and {f_top, f_d1, f_d28, f_rep} <= set(pr["files"]) and not any("no.csv" in f or "lock" in f or "docx" in f for f in pr["files"]), [os.path.basename(f) for f in pr["files"]])
check("... under a folder of the same name in the selected project, with its sub-folders as folders inside it",
      (name_of(f_top), name_of(f_d1), parent_of(f_d1), name_of(f_rep), parent_of(f_rep)) == ("Series 7", "day 1", "Series 7", "repeat", "day 28"), (name_of(f_top), name_of(f_d1), name_of(f_rep), parent_of(f_rep)))
check("... its files are read like any other: in Workspace, tagged with the project", {f_top, f_d1, f_d28, f_rep} <= {getattr(i, "path", "") for i in w.singles if getattr(i, "project_id", None) == slug_a})
n_fold = len(pr["folders"]); sh._select_node(("project", slug_a, "")); pump(); sh.add_disk_folder(str(big)); idle(w)
check("adding the same folder again makes nothing double", len(WP.get(slug_a)["folders"]) == n_fold and len(WP.get(slug_a)["files"]) == len(pr["files"]))
sh.projects.setCurrentItem(None); sh.projects.clearSelection(); sh._current_project = None; n_proj = len(WP.list_projects())
lone = TMP / "Loose scans"; lone.mkdir(); f_l = put(lone, "l1.csv"); got2 = sh.add_disk_folder(str(lone)); idle(w)
check("with no project selected, a folder becomes a project named after it", len(WP.list_projects()) == n_proj + 1 and WP.get(got2)["name"] == "Loose scans" and WP.get(got2)["files"] == [f_l] and not WP.get(got2)["folders"], WP.get(got2)["name"] if got2 else got2)
empty = TMP / "Nothing here"; empty.mkdir(); n_proj = len(WP.list_projects())
check("a folder with no data files says so and adds nothing", sh.add_disk_folder(str(empty)) is None and "No data files" in w.status.text() and len(WP.list_projects()) == n_proj, w.status.text())
fm_all = [a.text().split("\t")[0] for a in w.file_btn.menu().actions() if a.text()]
check("File ▸ 'Add a folder of data files…' is right under 'Add data files…'", "Add a folder of data files…" in fm_all and fm_all.index("Add a folder of data files…") == next(i for i, t in enumerate(fm_all) if t.startswith("Add data files")) + 1, fm_all[:8])

# ------------------------------------------------------------------------------------------------ every button says what it does
from PySide6.QtWidgets import QAbstractButton, QToolButton
miss = []
for i in (6, 7):
    w.go(i); pump()
    miss += [(i, b.text()) for b in w.pages.widget(i).findChildren(QAbstractButton) if isinstance(b, (QPushButton, QToolButton)) and b.isVisible() and not b.toolTip().strip()]
check("every button of Start here and Workbook has a tooltip", not miss, miss)

print(f"\n{N[0]} passed, {N[1]} failed"); sys.stdout.flush(); os._exit(1 if N[1] else 0)

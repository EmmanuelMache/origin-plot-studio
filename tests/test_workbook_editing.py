"""Delete, hide and remove where the work is done: cells, rows and columns of the Workbook table, files of its list -
and the rule that a file which is not ticked on Start here is nowhere else in the app.
Run:  python tests/test_workbook_editing.py"""
import os, sys, tempfile, time, warnings
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
TMP = Path(tempfile.mkdtemp()); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private"); os.environ["ORIGIN_PLOT_APP_HOME"] = str(TMP / "store")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
from PySide6.QtCore import Qt, QItemSelectionModel, QItemSelection
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, workspace_workbook as WB
app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
def pump(cond=lambda: False, timeout=.3):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond(): return True
        time.sleep(.005)
    return cond()
def idle(w, timeout=90): return pump(lambda: w.thread is None and not w.workbench._opening, timeout) and pump(timeout=.4)

# ---------------------------------------------------------------- the table model on its own
df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0], "n": [10, 20, 30, 40, 50], "t": ["a", "b", "c", "d", "e"]}); ident = id(df); hits = []
m = WB.WorkingTableModel(df, lambda: hits.append(1))
check("emptying cells: numbers become empty, words become empty words, a whole-number column still holds numbers", m.clear_cells([(0, 0), (1, 1), (2, 2)]) == 3 and np.isnan(df.iat[0, 0]) and np.isnan(df.iat[1, 1]) and df.iat[2, 2] == "" and df.iat[0, 1] == 10 and len(hits) == 1)
m.undo_edit(); check("... one Undo edit puts all of them back", df.iat[0, 0] == 1.0 and df.iat[1, 1] == 20 and df.iat[2, 2] == "c" and id(m.df) == ident)
m.redo_edit(); check("... and Redo empties them again", np.isnan(df.iat[0, 0]) and df.iat[2, 2] == ""); m.undo_edit()
check("deleting rows: they go, the others close up", m.delete_rows([1, 3]) == 2 and list(df["x"]) == [1.0, 3.0, 5.0] and list(df.index) == [0, 1, 2] and m.rowCount() == 3)
m.undo_edit(); check("... Undo edit brings the rows back in their place, in the same table", list(df["x"]) == [1.0, 2.0, 3.0, 4.0, 5.0] and list(df["t"]) == list("abcde") and id(m.df) == ident and m.rowCount() == 5)
check("deleting a column", m.delete_columns([1]) == ["n"] and list(df.columns) == ["x", "t"] and m.columnCount() == 2)
m.undo_edit(); check("... Undo edit brings it back where it was", list(df.columns) == ["x", "n", "t"] and list(df["n"]) == [10, 20, 30, 40, 50])
check("a table keeps at least one column", m.delete_columns([0, 1, 2]) == [] and len(df.columns) == 3)
m.setData(m.index(0, 0), "9.5", Qt.EditRole); m.delete_rows([4]); m.undo_edit(); m.undo_edit()
check("typed cells and deletions undo in the order they were made", df.iat[0, 0] == 1.0 and len(df) == 5)
ro = WB.WorkingTableModel(df.copy(), lambda: None); ro.read_only = True
check("a table made by the app is not changed", ro.clear_cells([(0, 0)]) == 0 and ro.delete_rows([0]) == 0 and ro.delete_columns([0]) == [])

# ---------------------------------------------------------------- in the app
w = W.Workspace([]); w.resize(1600, 1000); w.show(); pump(); w.go(6); sh = w.pages.widget(6); c = w.workbench
T = np.linspace(25, 1000, 400); files = []
for k in range(3):
    f = TMP / f"run_{k + 1}.csv"; pd.DataFrame({"Temperature (°C)": T, "Time (min)": (T - 25) / 10.0, "Mass (%)": 100 - (5 + k) / (1 + np.exp(-(T - 450) / 12)), "DSC (uV)": np.sin(T / 90)}).to_csv(f, index=False); files.append(str(f))
sh.add_files(files); idle(w); pump(timeout=1.0)
for p in files: pump(lambda: c.ready(p), 60)
sh.open_projects(); idle(w); pump(timeout=1.0)
graphs = lambda p: [i for i in w.singles if getattr(i, "path", "") == p]
check("three files added and opened: each has graphs in Workspace", all(graphs(p) for p in files) and w.pages.currentIndex() == 0, [len(graphs(p)) for p in files])
w.go(7); pump(timeout=.8); wb = c.workbook
check("Workbook lists the three ticked files", wb.paths == files, [os.path.basename(p) for p in wb.paths])
keys = lambda widget: [s.key().toString() for s in widget.findChildren(QShortcut)]
check("the Delete key works on the table, on the list of files and on the list of columns", "Del" in keys(wb.table) and "Del" in keys(wb.files) and "Del" in keys(wb.columns), (keys(wb.table), keys(wb.files), keys(wb.columns)))
check("each of them has a right-click menu, the column headers and row numbers of the table too", all(x.contextMenuPolicy() == Qt.CustomContextMenu for x in (wb.table, wb.files, wb.columns, wb.table.horizontalHeader(), wb.table.verticalHeader())))
sm = wb.table.selectionModel(); mdl = wb.model; n_rows = len(mdl.df)
sm.select(QItemSelection(mdl.index(2, 2), mdl.index(4, 2)), QItemSelectionModel.ClearAndSelect); pump()
r = wb.delete_in_table(); pump(timeout=.5)
empty_ = lambda col, a, b: all(str(v).strip() in ("", "nan") for v in mdl.df[col].iloc[a:b])
check("Delete with cells selected empties them in the working copy; the file on the disk is unchanged", r == 3 and empty_("Mass (%)", 2, 5) and not empty_("Mass (%)", 5, 8) and len(mdl.df) == n_rows and not pd.read_csv(files[0])["Mass (%)"].iloc[2:5].isna().any(), (r, list(mdl.df["Mass (%)"].iloc[1:6])))
check("... the graphs of the file are made without those values", c.table_for(files[0]).num["Mass (%)"].iloc[2:5].isna().all())
check("... the edit is kept with the file (saved with the project)", "" in c.settings_for(files[0]).get("edited_sheets", {}))
wb.undo_edit(); pump(timeout=.4); check("... 'Undo edit' takes it back", not empty_("Mass (%)", 2, 5))
sm.select(QItemSelection(mdl.index(0, 0), mdl.index(1, mdl.columnCount() - 1)), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows); pump()
r = wb.delete_in_table(); pump(timeout=.5)
check("Delete with whole rows selected deletes the rows", r == 2 and len(mdl.df) == n_rows - 2 and str(n_rows - 2) in wb.info.text().replace(",", ""), (r, len(mdl.df), wb.info.text()))
t_after = c.table_for(files[0]); check("... and the graphs of the file are made from the shorter table", len(t_after.df) == n_rows - 2)
wb.undo_edit(); pump(timeout=.4)
col = list(mdl.df.columns).index("DSC (uV)")
sm.select(QItemSelection(mdl.index(0, col), mdl.index(len(mdl.df) - 1, col)), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Columns); pump()
r = wb.delete_in_table(); pump(timeout=.6)
check("Delete with a whole column selected deletes the column from the working copy", r == 1 and "DSC (uV)" not in mdl.df.columns and "DSC (uV)" not in [wb.columns.item(i).text() for i in range(wb.columns.count())] and "DSC (uV)" in pd.read_csv(files[0]).columns, list(mdl.df.columns))
wb.undo_edit(); pump(timeout=.6); check("... 'Undo edit' brings the column back", "DSC (uV)" in mdl.df.columns)
n = wb.hide_columns(False, ["Time (min)"]); pump(timeout=.8)
check("hiding a column leaves it in the table but out of the graphs", n == 1 and "Time (min)" in mdl.df.columns and "Time (min)" not in c.table_for(files[0]).cols and "not carried to Workspace" in w.status.text(), w.status.text())
n = wb.hide_columns(True, ["Time (min)"]); pump(timeout=.8); check("... and it can be used again", n == 1 and "Time (min)" in c.table_for(files[0]).cols)
import inspect
src = inspect.getsource(WB.WorkbookPage.table_menu)
check("the right-click menu of the table offers: empty cells, delete rows, delete column, hide column, leave out in all files, undo", all(t in src for t in ("Empty", "Delete the", "Delete column", "Hide '", "out in all files", "Undo edit")))

# ---- X and Y chosen in the table, and the graph that follows
hdr = lambda: [mdl.headerData(i, Qt.Horizontal) for i in range(mdl.columnCount())]
check("the column headers say which column is X and which is Y", "Temperature (°C)   [X]" in hdr() and "Mass (%)   [Y]" in hdr(), hdr())
pump(timeout=.6)
check("under the table the app suggests the graph for the data as it is chosen, with the reason, and a button to create it", wb.suggest.text().startswith("Suggested graph: ") and wb.b_suggest.isVisibleTo(wb) and wb._suggested is not None, wb.suggest.text()[:120])
first_s = wb.suggest.text()
ok_ = wb.set_role("Time (min)", "X"); pump(timeout=.8); t_ = c.table_for(files[0])
check("'Use as X' on a column header: that column is X, Y stays; the headers and the graphs follow", ok_ and t_.x == "Time (min)" and t_.ys[0] == "Mass (%)" and "Time (min)   [X]" in hdr(), (t_.x, t_.ys, hdr()))
ok_ = wb.set_role("Temperature (°C)", "Y"); pump(timeout=.8); t_ = c.table_for(files[0])
check("'Use as Y': that column is the first Y", ok_ and t_.x == "Time (min)" and t_.ys[0] == "Temperature (°C)", (t_.x, t_.ys))
ok_ = wb.set_role("Temperature (°C)", "X"); pump(timeout=.8); t_ = c.table_for(files[0])
check("taking the Y column as X swaps the two", ok_ and t_.x == "Temperature (°C)" and t_.ys[0] == "Time (min)", (t_.x, t_.ys))
wb.set_role("Mass (%)", "Y"); pump(timeout=.8); t_ = c.table_for(files[0]); check("... and back: mass against temperature", t_.x == "Temperature (°C)" and t_.ys[0] == "Mass (%)")
order0 = list(mdl.df.columns); k_ = order0.index("Time (min)")
check("'Move column right' moves it in the working copy; Undo edit puts it back", wb.move_column(k_, 1) and list(mdl.df.columns)[k_ + 1] == "Time (min)" and (wb.undo_edit() or True) and list(mdl.df.columns) == order0, list(mdl.df.columns))
src2 = inspect.getsource(WB.WorkbookPage.table_menu)
check("the header menu offers: use as X, use as Y, move left, move right", all(t in src2 for t in ("as X", "as Y", "Move column left", "Move column right")))
n_g = len(w.singles); r_ = wb.create_suggested(); idle(w); pump(timeout=1.0)
check("'Create this graph' draws the suggested graph and shows it in Workspace", len(w.singles) == n_g + 1 and w.pages.currentIndex() == 0, (len(w.singles), n_g, w.pages.currentIndex()))
w.singles = w.singles[:n_g]; w.regroup(); w.refresh_list(); w.go(7); pump(timeout=.8)

# ---- a file taken off the list is nowhere in the app
wb.files.setCurrentRow(1); pump(timeout=.4); n_before = len(w.singles); gone = files[1]
r = wb.remove_files(); pump(timeout=.8)
check("Delete on a file of the Workbook list takes it off the list", r == 1 and wb.paths == [files[0], files[2]], [os.path.basename(p) for p in wb.paths])
check("... its graphs leave Workspace; the other files keep theirs", not graphs(gone) and graphs(files[0]) and graphs(files[2]) and len(w.singles) < n_before)
ticked = [p for _s, p in sh.ticked_inputs()]
check("... it is unticked on Start here (the others stay ticked), and still listed there", gone not in ticked and files[0] in ticked and files[2] in ticked and gone in [p for _s, p in sh.listed_inputs()], [os.path.basename(p) for p in ticked])
check("... the file on the disk is untouched", os.path.isfile(gone))
w.undo_any(); pump(timeout=.6); check("Undo in Workspace brings its graphs back", bool(graphs(gone)))

# ---- what is not ticked on Start here is nowhere else
w.go(6); pump(timeout=.6)
check("back on Start here the file is still unticked", gone not in [p for _s, p in sh.ticked_inputs()])
w.go(0); pump(timeout=1.0); idle(w)
check("leaving Start here: the graphs of the unticked file are not in Workspace", not graphs(gone) and graphs(files[0]) and "not ticked on Start here" in w.status.text(), w.status.text()[:120])
tp_ticked = [w.templates_page.files.item(i).data(Qt.UserRole) for i in range(w.templates_page.files.count()) if w.templates_page.files.item(i).checkState() == Qt.Checked]
check("... Analysis has only the ticked files ticked", sorted(tp_ticked) == sorted([files[0], files[2]]), [os.path.basename(p) for p in tp_ticked])
w.go(7); pump(timeout=.8); check("... Workbook lists only the ticked files", wb.paths == [files[0], files[2]])
w.go(6); pump(timeout=.5)
node = next(i for i in sh._walk() if tuple(i.data(0, Qt.UserRole))[0] == "file" and tuple(i.data(0, Qt.UserRole))[2] == gone); node.setCheckState(0, Qt.Checked); pump(timeout=.5)
w.go(0); idle(w); pump(timeout=1.5); idle(w)
check("ticked again on Start here: going to Workspace reads it and its graphs are there", bool(graphs(gone)), [len(graphs(p)) for p in files])
w.go(7); pump(timeout=.8); check("... and Workbook lists all three again", sorted(wb.paths) == sorted(files))
# nothing ticked, one file highlighted: that file is the selection
w.go(6); pump(timeout=.5)
for n_ in list(sh._walk()): n_.setCheckState(0, Qt.Unchecked)
pump(timeout=.2); sh.projects.setCurrentItem(next(i for i in sh._walk() if tuple(i.data(0, Qt.UserRole))[0] == "file" and tuple(i.data(0, Qt.UserRole))[2] == files[2])); pump(timeout=.4)
w.header_nav.button(7).click(); pump(timeout=.8)
check("nothing ticked but a file highlighted on Start here: clicking 'Workbook' shows that file (it was an empty page)", len(sh.ticked_inputs()) == 0 and wb.paths == [files[2]] and wb.model is not None and wb.model.rowCount() > 0 and "run_3" in wb.caption.text(), (wb.paths, wb.caption.text()))
w.go(6); pump(timeout=.4)
for n_ in [i for i in sh._walk() if tuple(i.data(0, Qt.UserRole))[0] == "file" and tuple(i.data(0, Qt.UserRole))[2] in files]: n_.setCheckState(0, Qt.Checked)
pump(timeout=.3); w.header_nav.button(7).click(); pump(timeout=.8)
check("files ticked on Start here, 'Workbook' clicked in the top bar: the Workbook is filled with exactly those files, the first one shown", sorted(wb.paths) == sorted(files) and wb.model.rowCount() > 0 and wb.files.currentRow() >= 0, [os.path.basename(p) for p in wb.paths])
w.go(0); idle(w); pump(timeout=1.0); idle(w)
# a file added on another page is ticked when Start here first shows it
extra = TMP / "later.csv"; pd.DataFrame({"x": T, "y": T * 2}).to_csv(extra, index=False)
w.go(0); pump(); w.load([str(extra)]); idle(w); pump(timeout=1.0); had = bool(graphs(str(extra)))
w.go(6); pump(timeout=.8); sh.refresh_projects(); pump(timeout=.4)
check("a file added in Workspace is ticked when Start here first lists it (it is in use)", had and str(extra) in [p for _s, p in sh.ticked_inputs()], [os.path.basename(p) for _s, p in sh.ticked_inputs()])
w.go(0); pump(timeout=1.0); idle(w); check("... so visiting Start here and coming back does not take its graphs away", bool(graphs(str(extra))))
print(f"\n{N[0]} passed, {N[1]} failed"); sys.stdout.flush(); os._exit(1 if N[1] else 0)

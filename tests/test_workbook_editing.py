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

# ---------------------------------------------------------------- the tools of a spreadsheet, on the model
d2 = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [10.0, 20.0, 30.0], "t": ["a", "b", "c"]}); m2 = WB.WorkingTableModel(d2, lambda: None); id2 = id(d2)
check("paste: a block copied in Excel goes in from the chosen cell", m2.paste(1, 0, [["7", "70"], ["8", "80"]]) == (2, 2) and list(d2["x"]) == [1.0, 7.0, 8.0] and list(d2["y"]) == [10.0, 70.0, 80.0] and id(m2.df) == id2)
m2.undo_edit(); check("... one Undo edit takes the whole block back", list(d2["x"]) == [1.0, 2.0, 3.0] and list(d2["y"]) == [10.0, 20.0, 30.0])
check("paste past the end of the table adds the rows and columns it needs", m2.paste(2, 2, [["p", "1.5"], ["q", "2,5"]]) == (2, 2) and len(d2) == 4 and list(d2.columns) == ["x", "y", "t", "New column"] and list(d2["t"])[2:] == ["p", "q"]
      and list(d2["New column"])[2:] == [1.5, 2.5] and np.isnan(d2["x"].iloc[3]), d2.to_dict("list"))
m2.undo_edit(); check("... and Undo edit removes them again", d2.shape == (3, 3))
check("insert a row: an empty row at that place", m2.insert_rows(1) == 1 and len(d2) == 4 and np.isnan(d2.iat[1, 0]) and d2.iat[2, 0] == 2.0)
m2.undo_edit()
check("insert a column, and no second column of the same name", m2.insert_column(1, "note") and list(d2.columns) == ["x", "note", "y", "t"] and not m2.insert_column(0, "note"))
check("rename a column; not to a name that is taken", m2.rename_column(1, "remark") and list(d2.columns)[1] == "remark" and not m2.rename_column(1, "x"))
m2.undo_edit(); m2.undo_edit(); check("... both undone", list(d2.columns) == ["x", "y", "t"])
check("sort by a column, largest first: whole rows move together", m2.sort_by(0, False) and list(d2["x"]) == [3.0, 2.0, 1.0] and list(d2["t"]) == ["c", "b", "a"])
m2.undo_edit(); check("... undone: the order of the file again", list(d2["x"]) == [1.0, 2.0, 3.0])
check("fill down: the top selected cell into the selected cells below it", m2.fill_down([(0, 1), (1, 1), (2, 1)]) == 2 and list(d2["y"]) == [10.0, 10.0, 10.0])
m2.undo_edit()
check("the columns have Excel's letters", m2.letters() == ["A", "B", "C"] and WB.WorkingTableModel(pd.DataFrame(np.zeros((1, 28))), lambda: None).letters()[25:] == ["Z", "AA", "AB"])
check("a calculated column from a formula with those letters", m2.add_calculated("ratio", "=B/A") == "" and list(d2["ratio"]) == [10.0, 10.0, 10.0] and list(d2.columns)[-1] == "ratio")
check("... with functions and a column's own maximum (per cent of the largest value)", m2.add_calculated("pct", "B/B.max()*100") == "" and np.allclose(d2["pct"], [100 / 3, 200 / 3, 100.0]) and m2.add_calculated("lg", "log10(B)") == "" and np.allclose(d2["lg"], np.log10([10, 20, 30])))
check("... a formula that cannot be worked out, or tries something else, adds nothing and says why", "could not be worked out" in m2.add_calculated("bad", "B/Q") and "only column letters" in m2.add_calculated("bad2", "__import__('os')") and "name" in m2.add_calculated("pct", "A")
      and list(d2.columns) == ["x", "y", "t", "ratio", "pct", "lg"])
for _ in range(3): m2.undo_edit()
check("... calculated columns are undone like any other edit", list(d2.columns) == ["x", "y", "t"])

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

# ---- copy, paste and the Table menu on the page
tools = [a.text() for a in wb.table_tools.actions() if a.text()]
check("a 'Table' button holds the tools of a spreadsheet: copy, cut, paste, insert rows and columns, rename, sort, fill down, calculated column, delete", wb.b_table.isVisibleTo(wb) and all(any(k in t for t in tools) for k in ("Copy", "Cut", "Paste", "Insert a row above", "Insert a column", "Rename", "Sort by", "Fill down", "calculated column", "Delete the selected rows")), tools)
check("Ctrl+C, Ctrl+V, Ctrl+X and Ctrl+D work on the table", all(k in keys(wb.table) for k in ("Ctrl+C", "Ctrl+V", "Ctrl+X", "Ctrl+D")), keys(wb.table))
sm.select(QItemSelection(mdl.index(0, 0), mdl.index(1, 1)), QItemSelectionModel.ClearAndSelect); pump()
copied = wb.copy_cells(); clip = QApplication.clipboard().text()
check("Copy puts the selected cells on the clipboard as rows and columns (what Excel reads)", copied == clip and clip.count("\n") == 1 and clip.count("\t") == 2 and clip.startswith(str(mdl.df.iat[0, 0])), repr(clip[:60]))
sm.select(QItemSelection(mdl.index(3, 2), mdl.index(3, 2)), QItemSelectionModel.ClearAndSelect); wb.table.setCurrentIndex(mdl.index(3, 2)); pump()
done_ = wb.paste_cells("11.5\t0.25\n12.5\t0.75"); pump(timeout=.5)
check("Paste writes a block copied in Excel into the table from the selected cell; the graphs of the file follow", done_ == (2, 2) and float(mdl.df.iat[3, 2]) == 11.5 and float(mdl.df.iat[4, 3]) == 0.75 and float(c.table_for(files[0]).num.iloc[3, list(c.table_for(files[0]).num.columns).index("Mass (%)")]) == 11.5, (done_, mdl.df.iloc[3:5, 2:4].values.tolist()))
wb.undo_edit(); pump(timeout=.4)
err_ = wb.add_calculated("Loss (%)", "100-C"); pump(timeout=.5)
check("a calculated column on the page: 100 - mass as 'Loss (%)', listed under Columns and used by the graphs", err_ == "" and "Loss (%)" in mdl.df.columns and abs(float(mdl.df["Loss (%)"].iloc[-1]) - (100 - float(mdl.df["Mass (%)"].iloc[-1]))) < 1e-9
      and "Loss (%)" in [wb.columns.item(i).text() for i in range(wb.columns.count())] and "Loss (%)" in c.table_for(files[0]).cols, list(mdl.df.columns))
ok_ = wb.rename_column(list(mdl.df.columns).index("Loss (%)"), "Mass loss (%)"); pump(timeout=.5)
check("renaming a column (or double click on its header)", ok_ and "Mass loss (%)" in mdl.df.columns and "Loss (%)" not in mdl.df.columns)
wb.undo_edit(); wb.undo_edit(); pump(timeout=.5); check("... both undone with Undo edit", "Loss (%)" not in mdl.df.columns and "Mass loss (%)" not in mdl.df.columns)

# ---- sheets: add, duplicate, remove
check("the Table menu offers: add a sheet, duplicate this sheet, remove this sheet", all(any(k in t for t in tools) for k in ("Add a sheet", "Duplicate this sheet", "Remove this sheet")))
n_cols0 = mdl.columnCount(); first_sheet = wb.sheet.currentText()
nm = wb.add_sheet("Notes"); pump(timeout=.6)
check("Add a sheet: a new, empty sheet of the working copy, shown at once", nm == "Notes" and wb.sheet.currentText() == "Notes" and "Notes" in c.raw_sheets(files[0]) and list(wb.model.df.columns) == ["X", "Y"] and wb.model.rowCount() == 20, (nm, wb.sheet.currentText()))
wb.paste_cells("1\t10\n2\t20\n3\t30"); pump(timeout=.5)
check("... data pasted into it is kept with the file's settings (saved with the project)", list(wb.model.df["Y"].iloc[:3]) == [10.0, 20.0, 30.0] and "Notes" in c.settings_for(files[0]).get("edited_sheets", {}))
check("no second sheet of the same name", wb.add_sheet("Notes") is None and "not used yet" in w.status.text())
wb.sheet.setCurrentText(first_sheet); pump(timeout=.5); dup = wb.add_sheet("Copy of data", copy=True); pump(timeout=.6)
check("Duplicate this sheet: a copy of the sheet on show under a new name", dup == "Copy of data" and wb.sheet.currentText() == "Copy of data" and wb.model.rowCount() == n_rows and "Mass (%)" in wb.model.df.columns)
ok_ = wb.remove_sheet("Copy of data"); pump(timeout=.6)
check("Remove this sheet takes it out of the working copy; the file on the disk is not changed", ok_ and "Copy of data" not in c.raw_sheets(files[0]) and "Copy of data" not in wb.sheet_names() and "Copy of data" in c.settings_for(files[0]).get("removed_sheets", []) and os.path.isfile(files[0]))
c.working.pop((c.project_for(files[0]), files[0]), None); again_ = c.raw_sheets(files[0])
check("... what was added and removed is remembered when the file is read again", "Notes" in again_ and "Copy of data" not in again_, list(again_))
wb.open_file(wb.files.currentRow()); pump(timeout=.5); wb.remove_sheet("Notes"); pump(timeout=.5); wb.sheet.setCurrentText(first_sheet); pump(timeout=.5); mdl = wb.model; sm = wb.table.selectionModel()
check("the only sheet of a file is not removed (the file is taken off the list instead)", len(wb.sheet_names()) == 1 and wb.remove_sheet() is False and "only sheet" in w.status.text(), wb.sheet_names())
hdr_w = wb.table.columnWidth(0); from PySide6.QtGui import QFontMetrics as _FM
check("a column is as wide as its header needs (the first header was cut off)", hdr_w >= wb.table.horizontalHeader().fontMetrics().horizontalAdvance(str(mdl.headerData(0, Qt.Horizontal))) + 10, hdr_w)

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
# an XRD pattern: the peaks its graph found and named can be read in the Workbook
xr = TMP / "pattern.csv"; xx = np.linspace(5, 70, 2600); yy = 80 + sum(a_ * np.exp(-(xx - c_) ** 2 / 0.006) for a_, c_ in [(900, 29.4), (400, 32.2), (300, 34.1), (250, 47.5)])
pd.DataFrame({"2theta (deg)": xx, "Intensity (counts)": yy}).to_csv(xr, index=False)
w.go(6); pump(timeout=.4); sh.add_files([str(xr)]); idle(w); pump(timeout=1.0); pump(lambda: c.ready(str(xr)), 60); sh.open_projects(); idle(w); pump(timeout=1.0)
xi_ = next((i for i in w.singles if getattr(i, "path", "") == str(xr) and str(i.kind).startswith("XRD")), None)
w.go(7); pump(timeout=.8); wb.files.setCurrentRow(wb.paths.index(str(xr))) if str(xr) in wb.paths else None; pump(timeout=.6)
import related as R_
has_ = wb.sheet.findText(R_.PEAKS_SHEET) >= 0
if has_: wb.sheet.setCurrentText(R_.PEAKS_SHEET); pump(timeout=.5)
check("an XRD pattern has the Peaks sheet too: the table of peaks of its graph (what is labelled there), to read and export; it is not edited here", xi_ is not None and xi_.results is not None and has_ and wb.model is not None and wb.model.read_only
      and len(wb.model.df) == len(xi_.results) and "changed with the graph" in wb.info.text(), (xi_ is not None, has_, wb.info.text()[:80]))
# a file added on another page is ticked when Start here first shows it
extra = TMP / "later.csv"; pd.DataFrame({"x": T, "y": T * 2}).to_csv(extra, index=False)
w.go(0); pump(); w.load([str(extra)]); idle(w); pump(timeout=1.0); had = bool(graphs(str(extra)))
w.go(6); pump(timeout=.8); sh.refresh_projects(); pump(timeout=.4)
check("a file added in Workspace is ticked when Start here first lists it (it is in use)", had and str(extra) in [p for _s, p in sh.ticked_inputs()], [os.path.basename(p) for _s, p in sh.ticked_inputs()])
w.go(0); pump(timeout=1.0); idle(w); check("... so visiting Start here and coming back does not take its graphs away", bool(graphs(str(extra))))
# ---- Analysis: Delete on the list of files
tp = w.templates_page; w.go(5); pump(timeout=.6)
check("the list of files on Analysis has the Delete key", "Del" in keys(tp.files), keys(tp.files))
row_ = next((i for i in range(tp.files.count()) if tp.files.item(i).data(Qt.UserRole) == files[0]), None)
if row_ is not None:
    tp.files.clearSelection(); tp.files.item(row_).setSelected(True); pump(); had_ = bool(graphs(files[0])); tp.remove_files(); pump(timeout=.8)
    check("Remove (or Delete) on a highlighted file takes it out of the app's lists - its graphs leave Workspace too, it is unticked on Start here, and the file stays on the disk",
          had_ and not graphs(files[0]) and files[0] not in [p for _s, p in sh.ticked_inputs()] and os.path.isfile(files[0]) and "left Workspace" in w.status.text(), w.status.text()[:120])
    w.undo_any(); pump(timeout=.6); check("... Undo in Workspace brings the graphs back", bool(graphs(files[0])))
else: check("the file is listed on Analysis", False, [tp.files.item(i).text() for i in range(tp.files.count())])
print(f"\n{N[0]} passed, {N[1]} failed"); sys.stdout.flush(); os._exit(1 if N[1] else 0)

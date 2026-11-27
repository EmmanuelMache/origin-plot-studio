"""Origin Plot Studio - the menu bar of the window (File, Draw, Analysis, XRD tools, View, Help), with what the earlier window had:
new project, resume the last session (saved by itself), import from an Origin project, convert files to Excel, one workbook /
the workbook template, gallery templates, refresh, paper figures from a recipe, your own graph, peak labels you type, the phase
library, updates (check, install, from a zip, undo, where they come from), the System Check, the problem report and About.

Each item calls the engine's own functions (smart_plots, paper_figures, self_update, system_check ...). Since 5.40.0 this is the
only window of the app.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import threading
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

import smart_plots as sp

HERE = Path(__file__).resolve().parent
LASTSES = HERE / "last_session.json"                 # also read when you update from a version that had the earlier window


class Pipe(QObject):
    """Messages from a worker thread to the window (updates)."""
    msg = Signal(object)


def _noopen():
    return bool(os.environ.get("OPS_NO_OPEN"))


def install(w):
    import types
    for name, fn in METHODS.items():
        setattr(w, name, types.MethodType(fn, w))
    mb = w.menuBar()
    mb.setNativeMenuBar(False)
    def add(menu, text, fn, key=None, shown_key=None):
        a = menu.addAction(text + (f"\t{shown_key}" if shown_key else ""), fn)
        if key:
            a.setShortcut(QKeySequence(key))
        return a
    f = mb.addMenu("&File")
    add(f, "New project", w.new_project, "Ctrl+N")
    add(f, "Add data files…", w.add_files, shown_key="Ctrl+O")
    add(f, "Open session…", w.open_session, shown_key="Ctrl+Shift+O")
    add(f, "Resume last session", w.resume_last, "Ctrl+Shift+R")
    add(f, "Save session…", w.save_session, shown_key="Ctrl+S")
    f.addSeparator()
    add(f, "Import from an Origin project…", w.import_origin)
    add(f, "Convert files to Excel…", w.convert_files)
    add(f, "Save everything as one workbook…", lambda: w.write_workbook(False))
    add(f, "Workbook template…", lambda: w.write_workbook(True))
    add(f, "Make a gallery graph template… (G01–G24, C01, C02)", w.figtype_template_any)
    f.addSeparator()
    add(f, "Refresh previews", w.refresh_previews)
    add(f, "Open results folder", w.open_results)
    f.addSeparator()
    add(f, "Exit", w.close, "Ctrl+Q")
    d = mb.addMenu("&Draw")
    add(d, "Draw ticked graphs in Origin", lambda: w.draw_origin("ticked"), shown_key="F5")
    add(d, "Draw all graphs in Origin", lambda: w.draw_origin("all"), shown_key="Shift+F5")
    add(d, "Save this graph (PNG 600 dpi · TIFF · PDF · SVG)", w.save_current, shown_key="Ctrl+E")
    d.addSeparator()
    add(d, "Your own graph… (columns, style, axes)", w.own_graph_dialog, "Ctrl+Shift+D")
    add(d, "Peak labels you type…", w.typed_labels_dialog, "Ctrl+Shift+L")
    add(d, "Label peaks automatically (positions)", lambda: w.tools.labels_auto({"n": 8, "prom": 5, "digits": 4}), shown_key="Ctrl+L")
    add(d, "Figure from the ticked graphs (panels a, b …)", w.make_board)
    d.addSeparator()
    add(d, "Preview paper set (PDF)", w.paper_preview)
    add(d, "Make paper set", w.paper_set)
    add(d, "Paper figures from a recipe…", w.paper_figures)
    add(d, "Paper figures from a recipe, also in Origin…", lambda: w.paper_figures(origin=True))
    add(d, "Make a figure recipe from a workbook…", w.make_recipe)
    wf = d.addMenu("Workbooks of figures")               # how a workbook with whole figures (a figure plan, label / tick sheets) is listed
    from PySide6.QtGui import QActionGroup
    grp = QActionGroup(wf); grp.setExclusive(True); w.figure_mode_actions = {}
    for key, text in (("auto", "Let the app decide (recommended)"), ("both", "Figures and all sheets"), ("figures", "Figures only"),
                      ("sheets", "Sheets only (as before 5.55)")):
        a_ = wf.addAction(text); a_.setCheckable(True); grp.addAction(a_); w.figure_mode_actions[key] = a_
        a_.triggered.connect(lambda _=False, k=key: w.set_figure_mode(k))
    w.set_figure_mode((getattr(w, "cfg", None) or {}).get("figure_workbooks", "auto"), save=False)
    a = mb.addMenu("&Analysis")
    add(a, "All analyses…", lambda: w.go(1))
    add(a, "Graph gallery…", lambda: w.go(2))
    a.addSeparator()
    for label, entry, page in (("TGA: mass loss in temperature intervals", "Mass loss in temperature", 1), ("Calorimetry (TAM III)…", "Calorimetry (TAM III)", 1),
                               ("FTIR: band areas…", "Band areas", 1), ("Thermodynamic modelling…", "Phase assemblage (stacked areas)", 1),
                               ("Find peaks", "Find peaks", 1)):
        add(a, label, lambda e=entry, p=page: w.open_entry(p, e))
    x = mb.addMenu("&XRD tools")
    add(x, "XRD Scan Generator…", lambda: w.tools.xrd_app(False))
    add(x, "Peak correct / improve an XRD scan…", lambda: w.tools.xrd_app(True))
    add(x, "Phase library…", w.phase_library)
    v = mb.addMenu("&View")
    for key, label, _s in w.PANELS:
        v.addAction(w.panel_actions[key])
    v.addSeparator()
    for act in w.panels_btn.menu().actions():
        if act.text() and act not in w.panel_actions.values():
            v.addAction(act)
    h = mb.addMenu("&Help")
    add(h, "Check for updates…", lambda: w.check_updates())
    add(h, "Install an update from a zip file…", w.update_from_zip)
    add(h, "Undo the last update", w.undo_update)
    add(h, "Where updates come from…", w.update_source_dialog)
    h.addSeparator()
    add(h, "System Check", w.system_check)
    add(h, "Problem report…", w.problem_report)
    h.addSeparator()
    add(h, "Privacy and connections…", lambda: __import__("workspace_privacy").open_dialog(w))
    add(h, "Learning (what the app remembers)…", lambda: __import__("workspace_learning").open_history(w))
    add(h, "Open the error log…", w.open_error_log)
    add(h, "Mouse actions and keyboard shortcuts", w.show_shortcuts, shown_key="F1")
    add(h, "About Origin Plot Studio", w.about)
    w.menus = {"file": f, "draw": d, "analysis": a, "xrd": x, "view": v, "help": h}
    # the update badge in the top bar (shown when a newer version is waiting)
    top = w.panels_btn.parentWidget().layout()
    w.upd_btn = QPushButton("", objectName="accent")
    w.upd_btn.hide()
    w.upd_btn.clicked.connect(lambda: w.check_updates())
    top.insertWidget(1, w.upd_btn)
    w.upd_known = None
    w.pipe = Pipe()
    w.pipe.msg.connect(w._upd_msg)
    QTimer.singleShot(1500, w.startup_checks)


# ---------------------------------------------------------------------------------------------- File
def new_project(self, ask=True):
    if self.job_thread is not None:
        self.set_status("One moment: the current job is still running (Stop first).")
        return "busy"
    if ask and self.singles and not _noopen():
        r = QMessageBox.question(self, "New project", "Start a new, empty project?\nThe list of graphs is cleared. Your data files and the results "
                                 "already saved are not touched.\n(File > Resume last session brings this list back.)")
        if r != QMessageBox.Yes:
            return "kept"
    self.autosave()
    self.singles, self.combined, self.boards, self.user_groups = [], [], [], []
    self.refresh_list()
    self.show_empty()
    self.datamodel.set(None)
    self.resmodel.set(None)
    self.set_status("New project. Add your data files (Ctrl+O, or drop them on the window).")
    return "new"


def autosave(self):
    """What is in the list now, so File > Resume last session brings it back."""
    if not self.singles:
        return None
    try:
        return self.save_session(str(LASTSES)) if hasattr(self, "save_session") else None
    except Exception:
        return None


def resume_last(self):
    if not LASTSES.exists():
        self.set_status("There is no earlier session yet. It is saved by itself when you close the app or start a new project.")
        return None
    return self.open_session(str(LASTSES))


def import_origin(self, path=None):
    """Read the workbooks of an Origin project (.opju / .opj) into Your graphs (OriginPro reads them; nothing in the project changes)."""
    import re
    import origin_plot_app as opa
    if path is None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose an Origin project", "", "Origin project (*.opju *.opj);;All files (*.*)")
        if not path:
            return None
    dest = os.path.join(self.run_folder(), "imported_from_origin", re.sub(r"[^A-Za-z0-9_-]+", "_", Path(path).stem) + datetime.datetime.now().strftime("_%H%M%S"))
    def work(log, progress):
        return opa.import_origin_project(path, dest, log)
    def after(files):
        if files:
            self.load(list(files), tick=True)
        else:
            self.set_status("The Origin project could not be imported: see Details.")
            self.tabs.setCurrentWidget(self.details)
    self.start_job(work, "Opening the Origin project and reading its workbooks", after)
    return "started"


def convert_files(self, paths=None):
    """Instrument and data files to clean Excel workbooks, next to the files."""
    if paths is None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose the files to convert to Excel", "", "Instrument and data files (*.xrdml *.brml *.uxd *.ras *.spa "
                                                "*.ngb-ds3 *.ngb-ss3 *.xy *.xye *.asc *.dat *.txt *.csv *.sel);;All files (*.*)")
        if not paths:
            return None
    keep = [s.path for s in self.singles]
    def work(log, progress):
        return sp.convert_to_excel(list(paths), None, keep)
    def after(res):
        if not res:
            return
        outs, lines = res
        self.log(f"Converted to Excel ({len(outs)} of {len(paths)} files; each workbook is next to its file):\n" + "\n".join(lines))
        bad = len(paths) - len(outs)
        self.set_status((f"{len(outs)} file(s) converted to Excel, next to the original files." if outs else "Nothing could be converted.")
                        + (f" {bad} file(s) could NOT be converted: see Details." if bad else ""))
    self.start_job(work, "Converting to Excel", after)
    return "started"


def write_workbook(self, template=False, path=None):
    if path is None:
        name = "XRD_workbook_template.xlsx" if template else f"{self.project_name()}_XRD_workbook.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Workbook template" if template else "Save the loaded graphs as one workbook",
                                              str(Path(self.outdir.text().strip() or Path.home()) / name), "Excel workbook (*.xlsx)")
        if not path:
            return None
    try:
        lines = sp.write_workbook([] if template else self.singles, path, template=template)
        self.log("\n".join(lines))
        self.set_status(lines[0])
        return path
    except Exception:
        self.log("!! The workbook could not be written:\n" + traceback.format_exc())
        self.set_status("The workbook could not be written: see Details.")
        return None


def figtype_template_any(self):
    import gallery_graphs as tg
    names = [f"{k}  {v[0]}  -  {v[1]}" for k, v in tg.TYPES.items()]
    t, ok = QInputDialog.getItem(self, "Make a gallery graph template", "Graph type:", names, 0, False)
    if ok and t:
        return self.tools.figtype_template(t.split()[0], self.pages.widget(2))
    return None


def refresh_previews(self):
    n = 0
    for it in self.singles:
        try:
            it.build(self.opt, it.kind)
            n += 1
        except Exception as e:
            self.log(f"   {it.title.strip()}: not redrawn ({e})")
    self.regroup()
    row = self.list.currentRow()
    self.refresh_list()
    if 0 <= row < self.list.count():
        self.list.setCurrentRow(row)
        self.show_item(row)
    self.set_status(f"{n} graph(s) drawn again.")
    return n


def open_entry(self, page, name):
    self.go(page)
    pg = self.pages.widget(page)
    e = pg.find_entry(name)
    if e is not None:
        pg.tree.setCurrentItem(e)
    return e


# ---------------------------------------------------------------------------------------------- Draw
def paper_figures(self, workbook=None, recipe=None, auto=None, origin=False):
    """Figures for a paper, composed by a recipe from the sheets of a workbook (paper_figures.py): PDF and PNG at 600 dpi.
    No saved recipe fits the workbook: the app offers to make one from the workbook itself (auto_recipe.py), keeps it in your
    own recipe folder and draws from it. origin=True: every figure is also built in Origin (one .opju per figure)."""
    import paper_figures as pf
    if workbook is None:
        workbook, _ = QFileDialog.getOpenFileName(self, "The workbook with the data of the figures", "", "Excel workbook (*.xlsx *.xlsm *.xls);;All files (*.*)")
        if not workbook:
            return None
    if recipe is None:
        recipe = pf.recipe_for(workbook)
        if recipe is None:
            if auto is None and not _noopen():
                box = QMessageBox(self); box.setWindowTitle("Paper figures"); box.setIcon(QMessageBox.Question)
                box.setText(f"No saved recipe fits '{os.path.basename(workbook)}'.\n\nThe app can make one from the workbook: it reads what every sheet holds "
                            "(patterns, fits, tick and label lists, series, tables, a figure plan if there is one) and lays out the figures. You can edit it later.")
                mk = box.addButton("Make one from the workbook", QMessageBox.AcceptRole); ch = box.addButton("Choose a recipe file…", QMessageBox.ActionRole)
                box.addButton(QMessageBox.Cancel); box.exec()
                auto = True if box.clickedButton() is mk else (False if box.clickedButton() is ch else None)
                if auto is None: return None
            if auto:
                recipe = self.make_recipe(workbook)
                if not recipe: return None
            else:
                recipe, _ = QFileDialog.getOpenFileName(self, "The recipe for these figures (.json)", pf.RECIPE_DIR if os.path.isdir(pf.RECIPE_DIR) else str(HERE),
                                                        "Figure recipe (*.json)")
                if not recipe:
                    return None
    rec = recipe if isinstance(recipe, dict) else pf.load_recipe(recipe)
    folder = os.path.join(self.run_folder(), "Paper_figures")
    drv = None
    if origin:
        import origin_plot_app as opa
        def drv(f, _log=self.log):
            if os.environ.get("OPS_ORIGIN_DRY"): return opa.Driver(f, _log, dry=True)
            try: return opa.Driver(f, _log, dry=False)
            except Exception as e:
                _log(f"   Origin is not available ({str(e)[:80]}): the commands are written as a script beside each figure instead."); return opa.Driver(f, _log, dry=True)
    def work(log, progress):
        return pf.run(workbook, rec, folder, log=log, stop=lambda: self.cancel[0], origin=drv)
    def after(res):
        if not res:
            self.set_status("The paper figures were not made: see Details.")
            return
        for n in res.get("notes") or []:
            self.log("   note: " + n)
        for o in res.get("origin") or []:
            for d_ in o.get("differences") or []: self.log(f"   Origin, {o['figure']}: {d_}")
        self.set_status(res["text"] + ".  Folder: " + folder)
        self.last_folder = folder
        self.last_paper_figures = res
    self.start_job(work, f"Drawing the paper figures from {os.path.basename(workbook)}" + (" (and in Origin)" if origin else ""), after)
    return "started"


def set_figure_mode(self, mode, save=True):
    """How a workbook of figures is listed. 'auto' (the app decides): a workbook made for figures (your saved recipe fits it,
    or it has a figure plan) gives its figures and every sheet no figure uses; a workbook with only label or tick sheets
    gives the graphs of its sheets as before, with its figures after them; any other file as before. 'both': the figures
    and all sheets; 'figures': only the figures; 'sheets': exactly as before 5.55. A saved session always gets back
    every graph it had. Files already in the list keep their graphs; files added from now on follow the choice."""
    mode = mode if mode in ("auto", "both", "figures", "sheets") else "auto"
    sp.COMPOSED_MODE = mode
    for k, a_ in (getattr(self, "figure_mode_actions", None) or {}).items(): a_.setChecked(k == mode)
    if save:
        try:
            import workspace_qt as WQ
            WQ.save_cfg({"figure_workbooks": mode}); self.cfg["figure_workbooks"] = mode
        except Exception: pass
        self.set_status({"auto": "Workbooks of figures: the app decides for each workbook (figures where the workbook is made for them).",
                         "both": "Workbooks of figures: their figures first, then one graph per sheet (as before).", "figures": "Workbooks of figures: only their figures.",
                         "sheets": "Workbooks of figures: one graph per sheet, exactly as before 5.55."}[mode] + " Files added from now on follow this.")
    return mode


def make_recipe(self, workbook=None):
    """A figure recipe made from a workbook by reading its sheets (auto_recipe.py). Saved in your own recipe folder
    (never in the app's folder, which is public), so the next time the workbook is opened the recipe is found by its name."""
    import auto_recipe as ar, paper_figures as pf
    if workbook is None:
        workbook, _ = QFileDialog.getOpenFileName(self, "The workbook to make a figure recipe for", "", "Excel workbook (*.xlsx *.xlsm *.xls);;All files (*.*)")
        if not workbook:
            return None
    base = os.path.splitext(os.path.basename(workbook))[0]
    try:
        rec, report = ar.build(workbook, base)
    except Exception as e:
        self.set_status(f"No recipe could be made from {base}: {type(e).__name__}: {str(e)[:120]}"); return None
    if not rec["figures"]:
        self.set_status(f"{base}: no sheet that the app can draw was found (see Details)."); [self.log("   " + r) for r in report]; return None
    folder = os.environ.get("OPS_RECIPE_DIR") or pf.plugin_dirs()[1]
    path = ar.save(rec, folder, base + "_auto")
    self.log(f"Recipe made from {base}: {len(rec['figures'])} figure(s) -> {path}")
    for r in report: self.log("   " + r)
    self.set_status(f"Recipe made: {len(rec['figures'])} figure(s). Saved as {os.path.basename(path)} in your recipe folder.")
    self.last_recipe = path
    return path


def own_graph_dialog(self, it=None, values=None):
    """Your own graph: x column, y columns, style, axis titles, log x, reversed x, layout."""
    it = it or self.current()
    if not isinstance(it, sp.Item):
        self.set_status("Click a single graph (not a ★ combined figure) first.")
        return None
    cols = [str(c) for c in (it.det.get("nums") or {})]
    cu = dict(getattr(it, "custom", None) or {})
    dlg = QDialog(self)
    dlg.setWindowTitle(f"Your own graph: {it.title.strip()[:60]}")
    fl = QFormLayout(dlg)
    xc = QComboBox()
    xc.addItems(cols)
    xc.setCurrentText(str(cu.get("x") or it.det.get("x") or (cols[0] if cols else "")))
    ys = QListWidget()
    ys.setSelectionMode(QAbstractItemView.MultiSelection)
    ys.addItems(cols)
    want = [str(c) for c in (cu.get("ys") or it.det.get("ys") or [])]
    for i in range(ys.count()):
        ys.item(i).setSelected(ys.item(i).text() in want)
    ys.setMaximumHeight(140)
    st = QComboBox()
    st.addItems(sp.OWN_STYLES)
    st.setCurrentText(str(cu.get("style") or "Automatic"))
    lay = QComboBox()
    lay.addItems(sp.OWN_LAYOUTS)
    lay.setCurrentText(str(cu.get("layout") or "Automatic"))
    xt, yt = QLineEdit(str(cu.get("xtitle") or "")), QLineEdit(str(cu.get("ytitle") or ""))
    xt.setPlaceholderText("as in the file")
    yt.setPlaceholderText("as in the file")
    lg, rv = QCheckBox("Logarithmic x axis"), QCheckBox("x axis from high to low")
    lg.setChecked(bool(cu.get("xlog")))
    rv.setChecked(bool(cu.get("xrev")))
    for lab, wdg in (("x", xc), ("y (one or more)", ys), ("Style", st), ("Layout", lay), ("x-axis title", xt), ("y-axis title", yt), ("", lg), ("", rv)):
        fl.addRow(lab, wdg)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
    bb.button(QDialogButtonBox.Reset).setText("Back to the automatic graph")
    fl.addRow(bb)
    res = {"done": None}
    def apply(clear=False):
        if clear:
            it.custom = {}
            it.build(self.opt, it.det.get("kind") or it.kind)
            res["done"] = "automatic"
        else:
            sel = [ys.item(i).text() for i in range(ys.count()) if ys.item(i).isSelected()]
            a = {"do": "own", "graph": self.items.index(it) + 1, "x": xc.currentText(), "ys": sel, "style": st.currentText(), "layout": lay.currentText(),
                 "xtitle": xt.text().strip(), "ytitle": yt.text().strip(), "xlog": lg.isChecked(), "xrev": rv.isChecked()}
            try:
                res["done"] = self.do_action(a)
            except ValueError as e:
                QMessageBox.warning(self, "Your own graph", str(e)) if not _noopen() else None
                res["done"] = f"not drawn: {e}"
                return
        self.regroup()
        self.refresh_list()
        self.list.setCurrentRow(self.items.index(it))
        dlg.accept()
    bb.accepted.connect(lambda: apply(False))
    bb.rejected.connect(dlg.reject)
    bb.button(QDialogButtonBox.Reset).clicked.connect(lambda: apply(True))
    self.own_dlg = dlg
    if values is not None:                                  # tests: fill and press OK
        for k, val in values.items():
            {"x": lambda v_: xc.setCurrentText(v_), "style": lambda v_: st.setCurrentText(v_), "xtitle": lambda v_: xt.setText(v_),
             "xlog": lambda v_: lg.setChecked(v_), "xrev": lambda v_: rv.setChecked(v_), "clear": lambda v_: None}[k](val)
        if values.get("ys") is not None:
            for i in range(ys.count()):
                ys.item(i).setSelected(ys.item(i).text() in values["ys"])
        apply(bool(values.get("clear")))
        return res["done"]
    dlg.exec()
    if res["done"]:
        self.set_status(f"Your own graph: {res['done']}")
    return res["done"]


def typed_labels_dialog(self, it=None, rows=None):
    """Peak labels you type (position and text): your own assignment, drawn on the peak nearest to each position."""
    it = it or self.current()
    if not isinstance(it, sp.Item):
        self.set_status("Click a single graph first.")
        return None
    if "_given_file" not in it.det:
        it.det["_given_file"] = list(it.given or [])
    typed = [t for t in (it.given or []) if t not in it.det["_given_file"]]
    dlg = QDialog(self)
    dlg.setWindowTitle(f"Peak labels: {it.title.strip()[:60]}")
    v = QVBoxLayout(dlg)
    v.addWidget(QLabel("One label per row: the position on the x axis and the text (e.g. 29.4 and C or Calcite). Your own assignment: it is noted "
                       "in the processing record. Labels from your files stay.", wordWrap=True))
    t = QTableWidget(max(6, len(typed) + 3), 2)
    t.setHorizontalHeaderLabels(["Position (x)", "Label"])
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    for i, (x, txt, _y) in enumerate(typed):
        t.setItem(i, 0, QTableWidgetItem(f"{x:g}"))
        t.setItem(i, 1, QTableWidgetItem(str(txt)))
    v.addWidget(t)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    v.addWidget(bb)
    res = {"n": None}
    def apply():
        new, bad = [], []
        for r in range(t.rowCount()):
            a, b = t.item(r, 0), t.item(r, 1)
            xs, tx = (a.text().strip() if a else ""), (b.text().strip() if b else "")
            if not xs and not tx:
                continue
            try:
                new.append((float(xs.replace(",", ".")), tx, None))
            except ValueError:
                bad.append(xs or tx)
        it.given = sorted(list(it.det["_given_file"]) + [n for n in new if n[1]], key=lambda q: q[0])
        it.det["_typed_labels"] = [f"{q[1]} at {q[0]:g}" for q in new if q[1]]
        it.build(self.opt, it.kind)
        on = sum(len(p.get("labels") or []) + len(p.get("code_labels") or []) for p in it.spec["panels"])
        res["n"] = (len(new), on)
        self.regroup()
        self.refresh_list()
        self.list.setCurrentRow(self.items.index(it))
        self.set_status(f"{len(new)} label(s) typed; the graph shows {on} label(s)." + (f" Not a position: {', '.join(bad)}" if bad else ""))
        dlg.accept()
    bb.accepted.connect(apply)
    bb.rejected.connect(dlg.reject)
    if rows is not None:                                     # tests
        for i, (x, txt) in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(x)))
            t.setItem(i, 1, QTableWidgetItem(txt))
        for i in range(len(rows), t.rowCount()):
            t.setItem(i, 0, QTableWidgetItem(""))
            t.setItem(i, 1, QTableWidgetItem(""))
        apply()
        return res["n"]
    dlg.exec()
    return res["n"]


# ---------------------------------------------------------------------------------------------- the phase library
def phase_library(self, add_file=None, remove=None):
    """The phases the app knows: built in, stored from your files, added by you. Remove stored ones; add phases from a file."""
    import pandas as pd
    dlg = QDialog(self)
    dlg.setWindowTitle("Phase library")
    dlg.resize(980, 560)
    v = QVBoxLayout(dlg)
    v.addWidget(QLabel("The phases used for peak suggestions. 'Built in' come with the app; 'stored' were kept from your files; 'your file' are phase "
                       "files you put next to the app or in a plugin folder. Only stored phases can be removed here.", wordWrap=True))
    t = QTableWidget(0, 7)
    t.setHorizontalHeaderLabels(["Code", "Phase", "Lines", "Kind", "Origin", "Added", "Removable"])
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    v.addWidget(t, 1)
    msg = QLabel("", wordWrap=True)
    v.addWidget(msg)
    def fill():
        rows = sp.library_table(self.opt)
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, k in enumerate(("Code", "Phase", "Lines", "Kind", "Origin", "Added", "Removable")):
                t.setItem(i, j, QTableWidgetItem("yes" if r[k] is True else "" if r[k] is False else str(r[k])))
        return rows
    def do_remove(codes=None):
        codes = codes if codes is not None else [t.item(i.row(), 0).text() for i in t.selectionModel().selectedRows() if t.item(i.row(), 6).text() == "yes"]
        if not codes:
            msg.setText("Select stored phases (Removable = yes) first.")
            return []
        gone = sp.remove_stored(codes, self.opt)
        msg.setText(f"Removed: {', '.join(gone)}" if gone else "Nothing removed (only stored phases can be removed).")
        fill()
        return gone
    def do_add(path=None):
        if path is None:
            path, _ = QFileDialog.getOpenFileName(dlg, "A file with phase lines: columns Phase, Code, d and I", "", "Table (*.csv *.xlsx *.xls *.txt)")
            if not path:
                return None
        try:
            df = pd.read_excel(path) if path.lower().endswith((".xlsx", ".xls")) else pd.read_csv(path, sep=None, engine="python")
            low = {str(c).strip().lower(): c for c in df.columns}
            pick = lambda *ks: next((low[k] for k in ks if k in low), None)
            cols = {"Phase": pick("phase", "name"), "Code": pick("code", "id"), "d": pick("d", "d (a)", "d-spacing", "d (å)"), "I": pick("i", "i (%)", "intensity", "i_rel (%)")}
            if any(c is None for c in cols.values()):
                raise ValueError("the file needs the columns Phase, Code, d and I")
            rows = pd.DataFrame({k: df[c] for k, c in cols.items()})
            done, skip = sp.store_phases(rows, self.opt, os.path.basename(path), replace=True)
            msg.setText((f"Added: {', '.join(f'{c} = {n} ({k} lines)' for c, n, k in done)}" if done else "Nothing added.") + ("\n" + "\n".join(skip[:6]) if skip else ""))
            fill()
            return done
        except Exception as e:
            msg.setText(f"Not added: {e}")
            return None
    row = QHBoxLayout()
    for text, fn in (("Add phases from a file…", lambda: do_add()), ("Remove the selected stored phases", lambda: do_remove()),
                     ("Open the folder", lambda: self.tools.library())):
        b = QPushButton(text)
        b.clicked.connect(fn)
        row.addWidget(b)
    row.addStretch(1)
    close = QPushButton("Close")
    close.clicked.connect(dlg.accept)
    row.addWidget(close)
    v.addLayout(row)
    rows = fill()
    self.library_dlg = dlg
    if add_file is not None or remove is not None or _noopen():
        out = {"rows": rows, "table": t, "msg": msg}
        if add_file is not None:
            out["added"] = do_add(add_file)
        if remove is not None:
            out["removed"] = do_remove(remove)
        return out
    dlg.exec()
    return rows


# ---------------------------------------------------------------------------------------------- Help: updates
def _upd_store():
    return os.path.join(os.path.dirname(os.path.abspath(sp.store_dir())), "program_backups")


def update_source(self):
    import self_update as su
    raw = str(self.cfg.get("update_source") or "").strip()
    v = su.normalize_source(raw)
    return "" if v == "off" else (v or su.DEFAULT_SOURCE)


def _upd_token(self):
    """The read-only access token of a private update repository: read from the app's protected store (secure_store). A token an
    older version kept in the settings file is moved there once and removed from the file - also when this system has no protected
    store (then it lives until the app closes)."""
    import self_update as su
    try:
        r = su.load_token(self.cfg.get("update_token"))
        if r.get("drop_legacy"):
            from workspace_qt import save_cfg
            save_cfg({"update_token": ""})                    # the copy in the settings file is gone
            self.cfg["update_token"] = ""
        if r.get("note"):
            self.log(r["note"])
    except Exception:
        su.TOKEN = ""


def startup_checks(self):
    """Once, after the window is up: old program files removed, plugin folders and the System Check into Details, and a quiet look for
    a new version (a button at the top when there is one; nothing is installed without your click)."""
    import origin_plot_app as opa
    try:                                                          # the lessons and learned file layouts of earlier versions are taken into the structured memory (once; the original files stay)
        import workspace_learning as WL
        WL.controller(self).migrate_once()
        WL.controller(self).auto_evidence()                       # the automatic evidence file, only when the user switched it on (a local write; paused in local-only mode)
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None and not getattr(self, "_auto_evidence_hooked", False):
            self._auto_evidence_hooked = True; app.aboutToQuit.connect(lambda ws=self: WL.controller(ws).auto_evidence())
    except Exception:
        pass
    gone = []
    for f, mark in getattr(opa, "REMOVED_FILES", {}).items():
        p = HERE / f
        try:
            if p.is_file() and mark in p.read_text(encoding="utf-8", errors="replace")[:4000]:
                p.unlink()
                gone.append(f)
        except Exception:
            pass
    if gone:
        self.log("Removed old program files: " + ", ".join(gone))
    try:
        import paper_figures as pf
        for p in pf.load_plugins()["problems"]:
            self.log("!! plugin file not used: " + p)
    except Exception:
        pass
    try:
        import system_check as sc
        for n, s, d in sc.run():
            if s != "ok":
                self.log(f"   System Check: {n}: {d}")
    except Exception:
        pass
    try:
        import self_update as su
        done = su.recover(str(HERE), _upd_store())            # an install that was cut off (power loss, a crash) is finished or undone
        if done:
            self.log("!! " + done)
            self.set_status(done)
    except Exception:
        self.log("!! Recovering an interrupted install:\n" + traceback.format_exc())
    if os.environ.get("OPS_NO_UPDATE_CHECK") or os.environ.get("OPS_NO_OPEN"):
        return
    src = self.update_source()
    if not src:
        return
    self._upd_token()
    def look():
        import self_update as su
        try:                                                  # (local-only mode, or update checks switched off in Privacy: find_update refuses and nothing is asked)
            part = su.incomplete(str(HERE))                   # a folder of this version is missing here (the update came through an older updater)
            r = su.find_update(src, "0.0.0" if part else sp.VERSION)
        except Exception:
            return
        if r:
            if part: r = dict(r); r["completes"] = True
            self.pipe.msg.emit(("waiting", r))
    threading.Thread(target=look, daemon=True).start()


def _upd_msg(self, m):
    kind = m[0]
    if kind == "waiting":
        self.upd_known = m[1]
        v = str(m[1].get("version") or "")
        if m[1].get("completes"):
            self.upd_btn.setText("↑ Finish the update (one click)")
            self.upd_btn.show()
            self.set_status("One part of the new version (the template library) is still to be installed: press 'Finish the update' at the top.")
            return
        self.upd_btn.setText(f"↑ Update {v} available" if v else "↑ Update available")
        self.upd_btn.show()
        self.set_status(f"Version {v} is available: press 'Update {v} available' at the top to install it.")
        return
    dlg = getattr(self, "upd_dlg", None)
    if dlg is None:
        return
    if kind == "none":
        dlg.bar.setValue(100); dlg.head.setText("You are up to date"); dlg.sub.setText(f"Version {sp.VERSION} is the newest."); dlg.close_b.setText("Close")
    elif kind == "found":
        dlg.bar.setValue(12); dlg.head.setText(f"Downloading version {m[1]} …")
    elif kind == "checking":
        dlg.bar.setValue(30); dlg.head.setText(f"Checking version {m[1]} …"); dlg.sub.setText("The example files are drawn with the new version and compared with today's result.")
    elif kind == "line":
        dlg.line.setText(str(m[1])[:200])
    elif kind == "bar":
        dlg.bar.setValue(int(m[1]))
    elif kind == "fail":
        dlg.bar.setValue(0); dlg.head.setText("The update did not work"); dlg.sub.setText(m[1]); dlg.line.setText("Nothing was changed."); dlg.close_b.setText("Close")
    elif kind == "checked":
        _k, trial, c, v, note = m
        if c["ok"]:
            dlg.line.setText(f"All {c['same']} example files are drawn exactly as before." + (f"  New: {note}" if note else ""))
            self._upd_install(trial, v)
        else:
            dlg.head.setText(f"Version {v} draws some examples differently")
            dlg.sub.setText("A new version can change drawings on purpose. What differs is listed below; install only if you want it.")
            dlg.detail.setPlainText(__import__("self_update").verification_note(trial) + "\n\n" + "\n".join(c.get("lines") or []))      # signed by the publisher, or NOT verified: said before the button
            dlg.detail.show()
            dlg.main_b.setText("Install this version")
            dlg.main_b.clicked.connect(lambda: self._upd_install(trial, v))
            dlg.main_b.show()
            dlg.close_b.setText("Do not install")


def _upd_install(self, trial, v):
    import self_update as su
    dlg = self.upd_dlg
    try:
        how = su.verification_note(trial)                     # said plainly: signed by the publisher, or NOT verified
        b, ch = su.install(trial, str(HERE), _upd_store(), f"update {sp.VERSION} to {v}")
        self.log(f"Updated {sp.VERSION} to {v}: {len(ch)} file(s) changed. Backup: {b}. {how}")
        dlg.bar.setValue(100); dlg.head.setText(f"Version {v} is installed"); dlg.sub.setText("Restart the app to use it. Help > Undo the last update brings the earlier version back.")
        dlg.line.setText(f"{len(ch)} file(s) changed. {how}")
        try:
            dlg.main_b.clicked.disconnect()
        except Exception:
            pass
        dlg.main_b.setText("Restart now")
        dlg.main_b.clicked.connect(self.restart_app)
        dlg.main_b.show()
        dlg.close_b.setText("Later")
        self.upd_btn.hide()
        self.set_status(f"Version {v} is installed. It is used after a restart.")
        return ch
    except Exception as e:
        dlg.head.setText("The update could not be installed"); dlg.sub.setText(str(e)[:200])
        dlg.line.setText("Nothing you had was lost. Help > Undo the last update puts the earlier program back if files were already copied.")
        self.log("!! Update install:\n" + traceback.format_exc())
        return None


def check_updates(self, source=None, wait=False):
    """One click: look for a new version, download it, draw the example files with it, install it when they are drawn the same,
    offer to restart. A version that draws an example differently is shown first and installed only on your click."""
    import shutil
    import self_update as su
    src = str(source or self.update_source()).strip()
    if not src:
        self.set_status("Update checks are switched off: Help > Where updates come from switches them on.")
        return None
    self._upd_token()
    dlg = QDialog(self)
    dlg.setWindowTitle("Update")
    dlg.resize(560, 300)
    v = QVBoxLayout(dlg)
    dlg.head = QLabel("Looking for a new version …", objectName="h2")
    dlg.sub = QLabel(f"You have version {sp.VERSION}.", objectName="soft", wordWrap=True)
    dlg.bar = QProgressBar()
    dlg.bar.setValue(4)
    dlg.line = QLabel("", objectName="soft", wordWrap=True)
    dlg.detail = QPlainTextEdit()
    dlg.detail.setReadOnly(True)
    dlg.detail.hide()
    for wdg in (dlg.head, dlg.sub, dlg.bar, dlg.line, dlg.detail):
        v.addWidget(wdg)
    row = QHBoxLayout()
    row.addStretch(1)
    dlg.main_b = QPushButton("", objectName="accent")
    dlg.main_b.hide()
    dlg.close_b = QPushButton("Cancel")
    dlg.close_b.clicked.connect(dlg.reject)
    row.addWidget(dlg.main_b)
    row.addWidget(dlg.close_b)
    v.addLayout(row)
    self.upd_dlg = dlg
    work = os.path.join(_upd_store(), "_trial")
    stop = {"stop": False}
    dlg.rejected.connect(lambda: stop.__setitem__("stop", True))
    emit = self.pipe.msg.emit
    def worker():
        try:
            part = su.incomplete(str(HERE))                    # a folder of this version is missing here: fetch the same version again, completely
            info = self.upd_known if (self.upd_known and not source) else su.find_update(src, "0.0.0" if part else sp.VERSION)
            if not info:
                emit(("none",))
                return
            ver = info.get("version") or "new"
            emit(("found", ver))
            shutil.rmtree(work, ignore_errors=True)
            trial = su.fetch_and_unpack(info, work, current=sp.VERSION, allow_same=part)       # the signature is checked here, before anything of the update runs
            ver = su.version_of(trial) or ver
            if not su.newer(ver, sp.VERSION) and not part:
                emit(("none",))
                return
            emit(("checking", ver))
            emit(("line", su.verification_note(trial)))
            c = su.check(trial, str(HERE), quick=True, stop=lambda: stop["stop"], log=lambda t: emit(("line", t)), progress=lambda fr: emit(("bar", 30 + 60 * fr)))
            if not stop["stop"]:
                emit(("checked", trial, c, ver, str(info.get("notes") or "").split("\n")[0][:140]))
        except su.UpdateError as e:
            emit(("fail", str(e)[:480]))
        except Exception as e:
            emit(("fail", su.explain(e)[:480]))
            self.log("Update: " + traceback.format_exc())
    if wait:
        worker()
        return dlg
    threading.Thread(target=worker, daemon=True).start()
    if not _noopen():
        dlg.show()
    return dlg


def update_from_zip(self, path=None):
    if path is None:
        path, _ = QFileDialog.getOpenFileName(self, "The zip of the new version (as you downloaded it)", str(Path.home() / "Downloads"), "Zip (*.zip);;All files (*.*)")
        if not path:
            return None
    return self.check_updates(source=path)


def undo_update(self, confirm=True):
    import self_update as su
    bs = su.backups(_upd_store())
    if not bs:
        self.set_status("There is no earlier version to go back to.")
        return None
    if confirm and not _noopen() and QMessageBox.question(self, "Undo", f"Put back the program as it was before the last update?\n({os.path.basename(bs[-1])})") != QMessageBox.Yes:
        return None
    try:
        t = su.undo(str(HERE), _upd_store())
        self.log("Undo: " + t)
        if not _noopen() and QMessageBox.question(self, "Undone", t + "\n\nRestart the app now?") == QMessageBox.Yes:
            self.restart_app()
        return t
    except Exception as e:
        self.set_status(f"Undo did not work: {e}")
        return None


def update_source_dialog(self):
    import self_update as su
    v, ok = QInputDialog.getText(self, "Where new versions come from", "New versions come from the app's own repository. Change this only if someone gave you "
                                 "another place:\na folder with zips, a link to a .zip or latest.json, or github:owner/repository.\nOnly use a place you trust. "
                                 "Type  off  to switch update checks off; leave empty for the app's own repository.", text=str(self.cfg.get("update_source") or ""))
    if not ok:
        return None
    from workspace_qt import save_cfg
    save_cfg({"update_source": v.strip()})
    self.cfg["update_source"] = v.strip()
    self.set_status("Updates come from: " + (self.update_source() or "nowhere (switched off)"))
    return self.update_source()


def restart_app(self):
    exe = sys.executable
    pw = Path(exe).parent / "pythonw.exe"
    try:
        if not _noopen():
            subprocess.Popen([str(pw) if pw.is_file() else exe, str(HERE / "start.pyw")], cwd=str(HERE))
        QTimer.singleShot(200, self.close)
    except Exception as e:
        self.set_status(f"I could not restart by myself ({e}). Close the app and start it again.")


# ---------------------------------------------------------------------------------------------- Help: checks, report, about
def system_check(self):
    import system_check as sc
    t = sc.text()
    self.log(t)
    if not _noopen():
        box = QMessageBox(self)
        box.setWindowTitle("System Check")
        box.setText("<pre style='font-family:Consolas,monospace;font-size:9pt'>" + t.replace("&", "&amp;").replace("<", "&lt;") + "</pre>")
        box.exec()
    return t


def problem_report(self, folder=None):
    """One zip for a problem report, safe to send: versions, the privacy level, recent messages and the kinds of graphs -
    with the names of your samples, files and folders replaced, and no data tables, settings values or keys. It is
    written to the results folder and sent nowhere. MANIFEST.txt inside says exactly what it holds."""
    import platform
    import zipfile
    import diagnostics
    folder = folder or self.outdir.text().strip() or __import__("origin_plot_app").default_results_folder()
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, "OriginPlotStudio_problem_report_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ".zip")
    names = []                                                    # what this window has open: replaced wherever it turns up
    for it in list(self.items)[:400]:
        for v in (getattr(it, "name", ""), getattr(it, "file", ""), getattr(it, "sample", ""), getattr(it, "path", "")):
            if v: names.append(str(v))
    out = diagnostics.build_bundle(p, names=names)
    san = diagnostics.Sanitizer(diagnostics.known_names(str(HERE), names), str(HERE))
    kinds = {}
    for it in self.items: kinds[getattr(it, "kind", "?")] = kinds.get(getattr(it, "kind", "?"), 0) + 1
    about = [f"Origin Plot Studio {sp.VERSION} (main window)", f"Python {sys.version.split()[0]} on {platform.system()} {platform.release()}", "",
             "Graphs in the list (kinds and counts only):"] + [f"  {n} x {k}" for k, n in sorted(kinds.items())]
    with zipfile.ZipFile(p, "a", zipfile.ZIP_DEFLATED) as z:
        z.writestr("about.txt", "\n".join(about))
        z.writestr("details.txt", san.clean(self.details.toPlainText()))
    self.set_status(f"Problem report written: {p} (versions, messages and kinds of graphs with names, folders and keys removed; no tables). Read MANIFEST.txt in it before you send it. Nothing was sent.")
    return p


def open_error_log(self):
    """A command that failed is written here (full error), even though the app has no console window. Problem report… includes it too."""
    p = HERE / "error_log.txt"
    if not p.exists() or not p.read_text(encoding="utf-8", errors="replace").strip():
        self.set_status("No command has failed since the app was last installed: error_log.txt is empty or does not exist yet.")
        return None
    try:
        if os.name == "nt": os.startfile(str(p))
        else: __import__("subprocess").Popen(["xdg-open", str(p)])
    except Exception:
        self.set_status(f"The error log is here: {p}")
    return str(p)


def about(self):
    import PySide6
    t = (f"<h3>Origin Plot Studio {sp.VERSION}</h3><p>Graphs from XRD, TGA, FTIR, calorimetry, particle size, thermodynamic models and any table, "
         f"drawn in OriginPro and as publication files.</p><p>Program folder: {HERE}<br>Python {sys.version.split()[0]} · PySide6 {PySide6.__version__}</p>"
         "")
    if not _noopen():
        QMessageBox.about(self, "About Origin Plot Studio", t)
    return t


METHODS = {f.__name__: f for f in (new_project, autosave, resume_last, import_origin, convert_files, write_workbook, figtype_template_any, refresh_previews,
                                   open_entry, paper_figures, make_recipe, set_figure_mode, own_graph_dialog, typed_labels_dialog, phase_library, update_source, _upd_token,
                                   startup_checks, _upd_msg, _upd_install, check_updates, update_from_zip, undo_update, update_source_dialog, restart_app,
                                   system_check, problem_report, open_error_log, about)}

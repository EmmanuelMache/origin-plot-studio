"""Origin Plot Studio - "Start here": three columns - your projects, a look at the data you add (what it is, its
columns, a quick preview), and the graphs that fit it, picked for you. Pick one (or let the app pick) and it is drawn
at once; from there, review it in Workspace and draw it in Origin. Every step here calls code the Templates page
(workspace_templates.py) and Workspace already have and test - this page only orchestrates and shows them, so a file
added here is the same file everywhere else in the app."""
from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
                                QListWidgetItem, QMenu, QMessageBox, QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

import workspace_projects as WP

try:
    from opstudio.api import RULES as _KIND_RULES          # the same rules 'what the app thinks your data is' already uses
except Exception:
    _KIND_RULES = []
KIND_CHOICES = [(None, "Automatic (let the app decide)")] + [(keys, why[0].upper() + why[1:]) for _pat, keys, why in _KIND_RULES]

PREVIEW_ROWS = 6                   # the data table here is a look at the file, not the whole thing - Workspace shows all of it
GRAPH_THUMB = (128, 86)           # the picture of each template in 'Choose a graph'


class StartHerePage(QWidget):
    label = "Start here"

    def __init__(self, ws):
        super().__init__()
        self.ws = ws
        self._table = None                                  # the opstudio.data.Table of the file on show here (for the quick plot / data preview)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        head = QHBoxLayout()
        htxt = QVBoxLayout()
        htxt.addWidget(QLabel("Start here", objectName="title"))
        sub = QLabel("Open a project, add your data, and create a graph.", objectName="soft")
        htxt.addWidget(sub)
        head.addLayout(htxt, 1)
        self.p_new = QPushButton("+ New project", objectName="accent")
        self.p_new.setToolTip("Name a project, then add data files to it (right away, or any time after with 'Add files to it')")
        self.p_new.clicked.connect(self.new_project)
        head.addWidget(self.p_new)
        self.p_open = QPushButton("Open ticked")
        self.p_open.setToolTip("Tick one or several projects on the left, then open them: their files come into Workspace and Analysis, kept apart by project")
        self.p_open.clicked.connect(self.open_projects)
        head.addWidget(self.p_open)
        outer.addLayout(head)

        cols = QHBoxLayout()
        cols.setSpacing(14)
        cols.addWidget(self._left_column(), 0)
        cols.addWidget(self._center_column(), 1)
        cols.addWidget(self._right_column(), 0)
        outer.addLayout(cols, 1)
        self.refresh()

    def _card(self):
        f = QFrame(objectName="card")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        return f, lay

    # ------------------------------------------------------------------------------------------------ left: projects
    def _left_column(self):
        card, lay = self._card()
        card.setFixedWidth(280)
        lay.addWidget(QLabel("Your projects", objectName="h3"))
        self.p_search = QLineEdit(placeholderText="Search projects and files…")
        self.p_search.textChanged.connect(self._filter_projects)
        lay.addWidget(self.p_search)
        prow = QHBoxLayout()
        self.p_add = QPushButton("Add files to it…")
        self.p_add.setToolTip("Tick one project first, then add more data files to it")
        self.p_add.clicked.connect(self.add_to_project)
        prow.addWidget(self.p_add)
        lay.addLayout(prow)
        self.projects = QListWidget()
        self.projects.setToolTip("Tick one or several, then Open ticked; right click one for more; type above to search")
        self.projects.setContextMenuPolicy(Qt.CustomContextMenu)
        self.projects.customContextMenuRequested.connect(self._project_menu)
        self.projects.itemChanged.connect(lambda _i: self._sync_project_buttons())
        lay.addWidget(self.projects, 1)
        note = QLabel("A project is a name for a set of data files you come back to. Right click one to rename, delete "
                       "it, or see which files have moved.", objectName="soft")
        note.setWordWrap(True)
        lay.addWidget(note)
        return card

    # ------------------------------------------------------------------------------------------------ centre: the data
    def _center_column(self):
        card, lay = self._card()
        lay.addWidget(QLabel("Inspect data", objectName="h3"))
        self.add_btn = QPushButton("Drop files here, or Add files…", objectName="primary")
        self.add_btn.setToolTip("Excel, CSV or text files. They are only read, never changed, and appear here, in Workspace and in Analysis ▸ Graphs and templates alike")
        self.add_btn.clicked.connect(self.add_files)
        lay.addWidget(self.add_btn)
        self.files = QListWidget()
        self.files.setMaximumHeight(124)
        self.files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.files.setToolTip("Your data files this session. Click one to inspect it here; Delete or right-click to remove")
        self.files.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files.customContextMenuRequested.connect(self._file_menu)
        self.files.currentItemChanged.connect(lambda *_a: self._show_selected_file())
        del_sc = QShortcut(QKeySequence(Qt.Key_Delete), self.files); del_sc.setContext(Qt.WidgetShortcut); del_sc.activated.connect(self.remove_selected_files)
        lay.addWidget(self.files)

        self.file_title = QLabel("", objectName="h3")
        lay.addWidget(self.file_title)
        drow = QHBoxLayout()
        self.detect = QLabel("Add a file above to see this.", objectName="soft")
        self.detect.setWordWrap(True)
        drow.addWidget(self.detect, 1)
        self.kind_combo = QComboBox()
        for _keys, label in KIND_CHOICES: self.kind_combo.addItem(label)
        self.kind_combo.setToolTip("Not what this is? Pick the right kind yourself; the graphs on the right follow it")
        self.kind_combo.activated.connect(lambda _i: self._apply_kind_choice())
        drow.addWidget(self.kind_combo)
        lay.addLayout(drow)

        self.table = QTableWidget(0, 0)
        self.table.setMaximumHeight(170)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setToolTip("The first rows of the file on show (read only - Workspace > Data shows the whole table)")
        lay.addWidget(self.table)

        self.plot_pic = QLabel("", objectName="soft")
        self.plot_pic.setAlignment(Qt.AlignCenter)
        self.plot_pic.setMinimumHeight(150)
        self.plot_pic.setStyleSheet("background: white; border: 1px solid #D8E1EC; border-radius: 6px;")
        self.plot_pic.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.plot_pic, 1)
        return card

    # ------------------------------------------------------------------------------------------------ right: choose a graph
    def _right_column(self):
        card, lay = self._card()
        card.setFixedWidth(364)
        lay.addWidget(QLabel("Choose a graph", objectName="h3"))
        lay.addWidget(QLabel("Compatible with this dataset", objectName="soft"))
        self.graph_list = QListWidget()
        self.graph_list.setViewMode(QListWidget.IconMode); self.graph_list.setMovement(QListWidget.Static); self.graph_list.setResizeMode(QListWidget.Adjust)
        self.graph_list.setIconSize(QSize(*GRAPH_THUMB)); self.graph_list.setGridSize(QSize(GRAPH_THUMB[0] + 20, GRAPH_THUMB[1] + 64))
        self.graph_list.setWordWrap(True); self.graph_list.setUniformItemSizes(True)
        self.graph_list.setToolTip("The best-fitting templates for the file on show, best first (★ Recommended)")
        self.graph_list.itemSelectionChanged.connect(self._sync_create_button)
        lay.addWidget(self.graph_list, 1)
        self.b_browse = QPushButton("Browse all templates myself")
        self.b_browse.setToolTip("Open the full gallery (Analysis ▸ Graphs and templates): every template, searchable and filterable")
        self.b_browse.clicked.connect(lambda: self.ws.go(self.ws.gallery_last if hasattr(self.ws, "gallery_last") else 5))
        lay.addWidget(self.b_browse)
        self.b_auto = QPushButton("Create graph →", objectName="accent")
        self.b_auto.setToolTip("Draws the selected template (or the best-fitting one) from your data, in Analysis ▸ Graphs and templates")
        self.b_auto.clicked.connect(self.draw_recommended)
        lay.addWidget(self.b_auto)
        self.b_workspace = QPushButton("Review in Workspace →", objectName="teal")
        self.b_workspace.setToolTip("Review in Workspace, then draw in Origin. Workspace: zoom, pan and check the graph, then 'Draw in Origin' for the full, editable graph with your data in worksheets")
        self.b_workspace.clicked.connect(lambda: self.ws.go(0))
        lay.addWidget(self.b_workspace)
        return card

    # ------------------------------------------------------------------------------------------------ projects
    def refresh_projects(self):
        ticked = {self.projects.item(i).data(Qt.UserRole) for i in range(self.projects.count()) if self.projects.item(i).checkState() == Qt.Checked}
        self.projects.blockSignals(True)
        self.projects.clear()
        for slug, p in WP.list_projects():
            miss = len(WP.missing_files(slug))
            sub = f"{len(p.get('files') or [])} file(s)" + (f" · {miss} moved or missing" if miss else "")
            li = QListWidgetItem(f"{p.get('name', slug)}\n{sub}")
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Checked if slug in ticked else Qt.Unchecked)
            li.setData(Qt.UserRole, slug)
            self.projects.addItem(li)
        self.projects.blockSignals(False)
        self._filter_projects(self.p_search.text())
        self._sync_project_buttons()

    def _filter_projects(self, text):
        t = text.strip().lower()
        for i in range(self.projects.count()):
            self.projects.item(i).setHidden(bool(t) and t not in self.projects.item(i).text().lower())

    def _ticked_projects(self):
        return [self.projects.item(i).data(Qt.UserRole) for i in range(self.projects.count()) if self.projects.item(i).checkState() == Qt.Checked]

    def _sync_project_buttons(self):
        n = len(self._ticked_projects())
        self.p_add.setEnabled(n == 1); self.p_add.setToolTip("Tick one project first, then add more data files to it" if n != 1 else "Add more data files to this project")
        self.p_open.setEnabled(n > 0)

    def new_project(self):
        name, ok = QInputDialog.getText(self, "New project", "Name this project (e.g. a sample set, a paper, a batch of scans):")
        if not ok or not name.strip(): return
        slug = WP.create(name)
        self.refresh_projects()
        paths, _ = QFileDialog.getOpenFileNames(self, f"Add data files to '{name.strip()}'", "", "Data files (*.xlsx *.xlsm *.xls *.csv *.txt *.dat *.xy *.asc *.tsv);;All files (*.*)")
        if paths:
            WP.add_files(slug, paths); self.refresh_projects()
        self.ws.set_status(f"Project '{name.strip()}' created" + (f" with {len(paths)} file(s)." if paths else " (empty: 'Add files to it…' any time)."))

    def add_to_project(self):
        sel = self._ticked_projects()
        if len(sel) != 1: self.ws.set_status("Tick one project first, then add files to it."); return
        slug = sel[0]; p = WP.get(slug) or {}
        paths, _ = QFileDialog.getOpenFileNames(self, f"Add data files to '{p.get('name', slug)}'", "", "Data files (*.xlsx *.xlsm *.xls *.csv *.txt *.dat *.xy *.asc *.tsv);;All files (*.*)")
        if not paths: return
        WP.add_files(slug, paths); self.refresh_projects()
        self.ws.set_status(f"{len(paths)} file(s) added to '{p.get('name', slug)}'.")

    def open_projects(self):
        """Ticked projects, one after another (Workspace reads one batch of files at a time, so several at once would
        silently drop all but the first)."""
        sel = self._ticked_projects()
        if not sel: self.ws.set_status("Tick one or more projects first."); return
        jobs = []
        for slug in sel:
            p = WP.get(slug)
            if not p: continue
            have = [f for f in p.get("files") or [] if os.path.isfile(f)]
            if have: jobs.append((p.get("name", slug), have))
        if not jobs: self.ws.set_status("The ticked project(s) have no files on disk to open."); return
        miss = sum(len(WP.missing_files(s)) for s in sel)
        self._open_queue = jobs; self._opened = {"n": 0, "names": []}; self._open_miss = miss
        self._open_next()

    def _open_next(self):
        if not self._open_queue:
            self.ws.set_status(f"Opened {', '.join(self._opened['names'])}: {self._opened['n']} file(s)." +
                               (f" {self._open_miss} file(s) of these projects have moved or are missing." if self._open_miss else ""))
            self.refresh()
            return
        name, paths = self._open_queue.pop(0)
        self._opened["names"].append(name); self._opened["n"] += len(paths)
        tp = getattr(self.ws, "templates_page", None)
        if tp is not None and hasattr(tp, "add_files"): tp.add_files(paths, project=name, on_done=lambda _items: self._open_next())
        else: self.ws.load(paths, project=name, on_done=lambda _items: self._open_next())

    def _project_menu(self, pos):
        it = self.projects.itemAt(pos)
        if it is None: return
        slug = it.data(Qt.UserRole); p = WP.get(slug) or {}
        m = QMenu(self.projects)
        m.addAction("Rename…", lambda: self._rename_project(slug))
        m.addAction("Add files to it…", lambda: (self.projects.item(self.projects.row(it)).setCheckState(Qt.Checked), self.add_to_project()))
        miss = WP.missing_files(slug)
        if miss:
            m.addAction(f"{len(miss)} file(s) have moved or are missing (forget them)", lambda: self._forget_missing(slug))
        m.addAction("Remove this project's graphs from Workspace", lambda: self._close_project_graphs(p.get("name", slug)))
        m.addSeparator()
        m.addAction("Delete this project (the files themselves are not touched)", lambda: self._delete_project(slug, p.get("name", slug)))
        m.exec(self.projects.mapToGlobal(pos))

    def _rename_project(self, slug):
        p = WP.get(slug) or {}
        name, ok = QInputDialog.getText(self, "Rename project", "New name:", text=p.get("name", slug))
        if ok and name.strip(): WP.rename(slug, name.strip()); self.refresh_projects()

    def _forget_missing(self, slug):
        for f in WP.missing_files(slug): WP.remove_file(slug, f)
        self.refresh_projects()

    def _close_project_graphs(self, name):
        if not hasattr(self.ws, "singles"): return
        its = [i for i in self.ws.singles if getattr(i, "project", None) == name]
        if not its: self.ws.set_status(f"No graphs of '{name}' are in Workspace right now."); return
        if QMessageBox.question(self, "Remove this project's graphs", f"Remove {len(its)} graph(s) of '{name}' from Your graphs? Undo: Ctrl+Z.") != QMessageBox.Yes: return
        ids = {id(i) for i in its}; self.ws.singles = [s for s in self.ws.singles if id(s) not in ids]
        self.ws.regroup(); self.ws.refresh_list()
        self.ws.set_status(f"{len(its)} graph(s) of '{name}' removed from Your graphs.")

    def _delete_project(self, slug, name):
        if QMessageBox.question(self, "Delete project", f"Delete the project '{name}'? Its files on disk are not touched; its graphs already in Workspace stay there too.") != QMessageBox.Yes: return
        WP.delete(slug); self.refresh_projects()
        self.ws.set_status(f"Project '{name}' deleted.")

    # ------------------------------------------------------------------------------------------------ files
    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add data files", "", "Data files (*.xlsx *.xlsm *.xls *.csv *.txt *.dat *.xy *.asc *.tsv);;All files (*.*)")
        if not paths: return
        tp = getattr(self.ws, "templates_page", None)
        if tp is not None and hasattr(tp, "add_files"): tp.add_files(paths)       # also pushes them into Workspace: one file, everywhere
        else: self.ws.load(paths, tick=True)
        self.refresh()

    def remove_selected_files(self):
        """Delete / right-click > Remove here: the file leaves the app entirely (Files list, Workspace graphs and all) -
        only the file on the disk is untouched; Add data files… brings it back."""
        sel = [i.data(Qt.UserRole) for i in self.files.selectedItems()]
        if not sel:
            self.ws.set_status("Click a file above (or Ctrl / Shift-click several) to remove it first."); return
        if QMessageBox.question(self, "Remove files", f"Remove {len(sel)} file(s) from the app? They stay on the disk.") != QMessageBox.Yes:
            return
        tp = getattr(self.ws, "templates_page", None)
        if tp is not None and hasattr(tp, "extra_files"):
            tp.extra_files = [p for p in tp.extra_files if p not in sel]; tp.refresh_files(); tp.schedule()
        sel_abs = {os.path.abspath(p) for p in sel}
        its = [i for i in getattr(self.ws, "singles", []) if os.path.abspath(str(getattr(i, "path", "") or "")) in sel_abs]
        if its:
            ids = {id(i) for i in its}
            self.ws.singles = [s for s in self.ws.singles if id(s) not in ids]
            self.ws.regroup(); self.ws.refresh_list()
            if not self.ws.items: self.ws.show_empty()
        self.refresh()
        self.ws.set_status(f"{len(sel)} file(s) removed from the app.")

    def _file_menu(self, pos):
        if not self.files.itemAt(pos): return
        n = len(self.files.selectedItems())
        m = QMenu(self.files)
        a = m.addAction(f"Remove {n} file(s) from the app" if n > 1 else "Remove this file from the app", self.remove_selected_files)
        a.setToolTip("The file itself stays on the disk; Add data files… brings it back"); a.setEnabled(n > 0)
        m.exec(self.files.mapToGlobal(pos))

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    # ------------------------------------------------------------------------------------------------ what the data looks like
    def refresh(self):
        self.refresh_projects()
        tp = getattr(self.ws, "templates_page", None)
        paths = []
        if tp is not None and hasattr(tp, "files"):
            for i in range(tp.files.count()): paths.append(tp.files.item(i).data(Qt.UserRole))
        keep = self.files.currentItem().data(Qt.UserRole) if self.files.currentItem() is not None else None
        self.files.blockSignals(True)
        self.files.clear()
        row = 0
        for i, p in enumerate(paths):
            it = QListWidgetItem(os.path.basename(p)); it.setToolTip(p); it.setData(Qt.UserRole, p); self.files.addItem(it)
            if p == keep: row = i
        self.files.blockSignals(False)
        if paths:
            self.files.setCurrentRow(row)
        self._show_selected_file()

    def _show_selected_file(self):
        """The file clicked in the Files list above: what it looks like, its first rows, a quick plot, and the
        templates that fit it (★ the best one)."""
        it = self.files.currentItem()
        tp = getattr(self.ws, "templates_page", None)
        if it is None or tp is None or not hasattr(tp, "table_of"):
            self.file_title.setText(""); self.detect.setText("Add a file above to see this."); self.kind_combo.setVisible(False)
            self.table.setRowCount(0); self.table.setColumnCount(0); self._set_plot(None)
            self._fill_graphs([]); self._table = None
            return
        path = it.data(Qt.UserRole)
        self.file_title.setText(os.path.basename(path))
        try:
            table, *_rest = tp.table_of(path)
        except Exception as e:
            self.detect.setText(f"This file could not be read: {e}"); self.kind_combo.setVisible(False)
            self.table.setRowCount(0); self.table.setColumnCount(0); self._set_plot(None); self._fill_graphs([]); self._table = None
            return
        self._table = table
        self._fill_table(table)
        try: self._ranked = tp.api.recommend([table])
        except Exception: self._ranked = []
        self.kind_combo.setVisible(bool(self._ranked))
        self.kind_combo.blockSignals(True); self.kind_combo.setCurrentIndex(0); self.kind_combo.blockSignals(False)
        self._apply_kind_choice(initial=True)

    def _fill_table(self, table):
        df = table.df.head(PREVIEW_ROWS)
        self.table.setColumnCount(len(df.columns)); self.table.setRowCount(len(df))
        self.table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(len(df)):
            for c, col in enumerate(df.columns):
                v = df.iloc[r, c]
                self.table.setItem(r, c, QTableWidgetItem(f"{v:.6g}" if isinstance(v, float) else str(v)))
        xs = table.numeric[:1]; ys = table.numeric[1:2]
        self._set_plot(table if xs and ys else None, xs[0] if xs else None, ys[0] if ys else None)

    def _set_plot(self, table, xcol=None, ycol=None):
        if table is None or xcol is None or ycol is None:
            self.plot_pic.setPixmap(QPixmap()); self.plot_pic.setText("No preview (needs two numeric columns)" if table is not None else "")
            return
        try:
            from matplotlib.figure import Figure
            from opstudio import api as opapi
            x, y = table.arr(xcol), table.arr(ycol)
            fig = Figure(figsize=(6.4, 2.9), dpi=100)
            ax = fig.add_subplot(111); ax.plot(x, y, color="#2563EB", lw=1.1)
            ax.set_xlabel(xcol, fontsize=8); ax.set_ylabel(ycol, fontsize=8); ax.tick_params(labelsize=7)
            fig.tight_layout()
            pm = QPixmap(); pm.loadFromData(opapi.png(fig, 640))
            self.plot_pic.setPixmap(pm); self.plot_pic.setText("")
        except Exception as e:
            self.plot_pic.setPixmap(QPixmap()); self.plot_pic.setText(f"Preview not drawn: {e}")

    def _apply_kind_choice(self, initial=False):
        ranked = list(self._ranked)
        if not ranked:
            self.detect.setText("Could not tell what kind of data this is from its columns yet. Browse the gallery yourself below.")
            self._fill_graphs([]); return
        i = self.kind_combo.currentIndex()
        keys = KIND_CHOICES[i][0] if 0 <= i < len(KIND_CHOICES) else None
        if keys:
            ranked = sorted(ranked, key=lambda r: 0 if any(k in r[0] for k in keys) else 1)
        why = ranked[0][2]
        self.detect.setText((f"Looks like {why}." if why != "the columns fit" else "The columns fit several kinds of graph.") +
                            (" · Confirmed by you" if keys and not initial else ""))
        self._fill_graphs(ranked)

    def _fill_graphs(self, ranked):
        tp = getattr(self.ws, "templates_page", None)
        cat = {r["id"]: r for r in tp.catalogue} if tp is not None else {}
        self.graph_list.clear()
        for i, (tid, _score, _why) in enumerate(ranked[:8]):
            row = cat.get(tid, {})
            li = QListWidgetItem(("★ " if i == 0 else "") + (row.get("name") or tid))
            li.setData(Qt.UserRole, tid)
            prev = row.get("preview")
            if prev and os.path.isfile(prev):
                pm = QPixmap(prev)
                if not pm.isNull(): li.setIcon(QIcon(pm.scaled(QSize(*GRAPH_THUMB), Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            li.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            li.setToolTip(("Recommended: the best fit for this file. " if i == 0 else "") + (row.get("name") or tid) + "\n" + (row.get("use") or ""))
            self.graph_list.addItem(li)
        if self.graph_list.count(): self.graph_list.setCurrentRow(0)
        self._sync_create_button()

    def _sync_create_button(self):
        self.b_auto.setEnabled(self.graph_list.count() > 0)

    def selected_template(self):
        it = self.graph_list.currentItem()
        return it.data(Qt.UserRole) if it is not None else None

    def draw_recommended(self):
        """'Create graph': the template selected on the right, drawn from the file on show here - ticks that one file
        and that one template in the gallery (Analysis ▸ Graphs and templates) and draws it, the same as picking it
        there yourself."""
        try:
            return self._draw_recommended()
        except Exception as e:
            import traceback; traceback.print_exc()
            self.ws.set_status(f"'Create graph' failed: {type(e).__name__}: {e}"); return None

    def _draw_recommended(self):
        from workspace_templates import set_checked
        tp = getattr(self.ws, "templates_page", None)
        it = self.files.currentItem()
        if tp is None or it is None:
            self.ws.set_status("Add and inspect a file first."); return None
        tid = self.selected_template()
        if tid is None:
            self.ws.set_status("No template fits this file yet: Browse all templates myself, or try a different file."); return None
        path = it.data(Qt.UserRole)
        set_checked(tp.files, range(tp.files.count()), False)
        rows = [i for i in range(tp.files.count()) if tp.files.item(i).data(Qt.UserRole) == path]
        set_checked(tp.files, rows, True)
        idx = next((i for i in range(tp.grid.count()) if tp.grid.item(i).data(Qt.UserRole) == tid), None)
        if idx is None:
            self.ws.set_status(f"The template ('{tid}') is not in the gallery right now."); return None
        tp.source.blockSignals(True); tp.source.setCurrentIndex(0); tp.source.blockSignals(False)
        tp.field.blockSignals(True); tp.field.setCurrentIndex(0); tp.field.blockSignals(False)
        set_checked(tp.grid, range(tp.grid.count()), False); set_checked(tp.grid, [idx], True); tp.filter_templates()
        tp._timer.stop(); tp.rebuild_previews()
        self.ws.go(self.ws.gallery_last if hasattr(self.ws, "gallery_last") else 5)
        return len(tp.tiles)

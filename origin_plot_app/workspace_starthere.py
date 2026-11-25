"""Origin Plot Studio - "Start here": add your data, see what the app thinks it is and which templates fit, then either
let the app draw the best one at once or go browse the gallery yourself; from there, review it in Workspace and draw it
in Origin. Every step here calls code the Templates page (workspace_templates.py) and Workspace already have and test -
this page only orchestrates them, so a file added here is the same file everywhere else in the app."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                                QPushButton, QScrollArea, QVBoxLayout, QWidget)

import workspace_projects as WP


class StartHerePage(QWidget):
    label = "Start here"

    def __init__(self, ws):
        super().__init__()
        self.ws = ws
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)
        outer.addWidget(QLabel("Start here", objectName="title"))
        sub = QLabel("Add your data. The app looks at its columns and tells you what it thinks it is, with the "
                      "templates that fit it marked ★ - draw the best one at once, or pick one yourself. From there, "
                      "review the graph in Workspace and draw it in Origin.", objectName="soft")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        pcard, play = self._card()
        play.addWidget(QLabel("Your projects", objectName="h3"))
        psub = QLabel("A project is a name for a set of data files you come back to - add several kinds (CSV, TSV, Excel …) to "
                       "one, then open it (or several together) to bring all of it into Workspace and Analysis at once. Right "
                       "click a project to rename, delete it, or see which of its files have moved.", objectName="soft")
        psub.setWordWrap(True)
        play.addWidget(psub)
        prow = QHBoxLayout()
        self.p_new = QPushButton("New project…", objectName="primary")
        self.p_new.setToolTip("Name a project, then add data files to it (right away, or any time after with 'Add files to it')")
        self.p_new.clicked.connect(self.new_project)
        prow.addWidget(self.p_new)
        self.p_add = QPushButton("Add files to it…")
        self.p_add.setToolTip("Tick one project first, then add more data files to it")
        self.p_add.clicked.connect(self.add_to_project)
        prow.addWidget(self.p_add)
        self.p_open = QPushButton("Open ticked", objectName="teal")
        self.p_open.setToolTip("Tick one or several projects, then open them: their files come into Workspace and Analysis, kept apart by project")
        self.p_open.clicked.connect(self.open_projects)
        prow.addWidget(self.p_open)
        prow.addStretch(1)
        play.addLayout(prow)
        self.projects = QListWidget()
        self.projects.setMaximumHeight(140)
        self.projects.setToolTip("Tick one or several, then 'Open ticked'; right click one for more")
        self.projects.setContextMenuPolicy(Qt.CustomContextMenu)
        self.projects.customContextMenuRequested.connect(self._project_menu)
        self.projects.itemChanged.connect(lambda _i: self._sync_project_buttons())
        play.addWidget(self.projects)
        outer.addWidget(pcard)

        card, lay = self._card()
        self.add_btn = QPushButton("Add data files…", objectName="primary")
        self.add_btn.setToolTip("Excel, CSV or text files. They are only read, never changed, and appear here, in Workspace and in Analysis ▸ Graphs and templates alike")
        self.add_btn.clicked.connect(self.add_files)
        lay.addWidget(self.add_btn)
        self.files = QListWidget()
        self.files.setMaximumHeight(110)
        self.files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.files.setToolTip("Your data files this session (added here, in Workspace, or in Analysis ▸ Graphs and templates). Click (or Ctrl / Shift-click several), then Delete or right-click to remove")
        self.files.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files.customContextMenuRequested.connect(self._file_menu)
        del_sc = QShortcut(QKeySequence(Qt.Key_Delete), self.files); del_sc.setContext(Qt.WidgetShortcut); del_sc.activated.connect(self.remove_selected_files)
        lay.addWidget(self.files)
        outer.addWidget(card)

        card2, lay2 = self._card()
        lay2.addWidget(QLabel("What the app thinks your data is", objectName="h3"))
        self.detect = QLabel("Add a file above to see this.", objectName="soft")
        self.detect.setWordWrap(True)
        lay2.addWidget(self.detect)
        self.sc = QScrollArea()
        self.sc.setWidgetResizable(True)
        self.sc.setMaximumHeight(150)
        self.rec_list = QWidget()
        self.rec_lay = QVBoxLayout(self.rec_list)
        self.rec_lay.setContentsMargins(4, 4, 4, 4)
        self.rec_lay.setSpacing(4)
        self.rec_lay.addStretch(1)
        self.sc.setWidget(self.rec_list)
        lay2.addWidget(self.sc)
        outer.addWidget(card2)

        row = QHBoxLayout()
        self.b_auto = QPushButton("Draw the best one for me", objectName="accent")
        self.b_auto.setToolTip("The app picks the best-fitting template for your added files and draws it at once, in Analysis ▸ Graphs and templates")
        self.b_auto.clicked.connect(self.draw_recommended)
        row.addWidget(self.b_auto)
        self.b_browse = QPushButton("Browse all templates myself")
        self.b_browse.setToolTip("Open the full gallery (Analysis ▸ Graphs and templates): every template, searchable and filterable")
        self.b_browse.clicked.connect(lambda: self.ws.go(self.ws.gallery_last if hasattr(self.ws, "gallery_last") else 5))
        row.addWidget(self.b_browse)
        self.b_workspace = QPushButton("Review in Workspace, then draw in Origin", objectName="teal")
        self.b_workspace.setToolTip("Workspace: zoom, pan and check the graph, then 'Draw in Origin' for the full, editable graph with your data in worksheets")
        self.b_workspace.clicked.connect(lambda: self.ws.go(0))
        row.addWidget(self.b_workspace)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        self.refresh()

    def _card(self):
        f = QFrame(objectName="card")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        return f, lay

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
        self._sync_project_buttons()

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
        self.files.clear()
        for p in paths:
            it = QListWidgetItem(os.path.basename(p)); it.setToolTip(p); it.setData(Qt.UserRole, p); self.files.addItem(it)
        while self.rec_lay.count() > 1: self.rec_lay.takeAt(0).widget().deleteLater()
        if tp is None or not hasattr(tp, "ticked_tables"):
            self.detect.setText("Add a file above to see this."); return
        tabs = [t for _p, t in tp.ticked_tables()]
        if not tabs:
            self.detect.setText("Add a file above to see this." if not paths else "Tick a file in the Files list (Analysis ▸ Graphs and templates) to see this."); return
        try: ranked = tp.api.recommend(tabs[:1])
        except Exception: ranked = []
        if not ranked:
            self.detect.setText("Could not tell what kind of data this is from its columns yet. Browse the gallery yourself below."); return
        why = ranked[0][2]
        self.detect.setText(f"Looks like {why}." if why != "the columns fit" else "The columns fit several kinds of graph.")
        names = {r["id"]: r["name"] for r in tp.catalogue}
        for tid, _score, _why in ranked[:5]:
            lab = QLabel(("★ " if tid == ranked[0][0] else "• ") + names.get(tid, tid), objectName="soft")
            self.rec_lay.insertWidget(self.rec_lay.count() - 1, lab)

    def draw_recommended(self):
        tp = getattr(self.ws, "templates_page", None)
        if tp is None or not hasattr(tp, "use_recommended"):
            self.ws.set_status("The template gallery is not available."); return
        n = tp.use_recommended()
        if n is not None: self.ws.go(self.ws.gallery_last if hasattr(self.ws, "gallery_last") else 5)

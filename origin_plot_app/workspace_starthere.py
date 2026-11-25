"""Origin Plot Studio - "Start here": add your data, see what the app thinks it is and which templates fit, then either
let the app draw the best one at once or go browse the gallery yourself; from there, review it in Workspace and draw it
in Origin. Every step here calls code the Templates page (workspace_templates.py) and Workspace already have and test -
this page only orchestrates them, so a file added here is the same file everywhere else in the app."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QVBoxLayout, QWidget


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

        card, lay = self._card()
        self.add_btn = QPushButton("Add data files…", objectName="primary")
        self.add_btn.setToolTip("Excel, CSV or text files. They are only read, never changed, and appear here, in Workspace and in Analysis ▸ Graphs and templates alike")
        self.add_btn.clicked.connect(self.add_files)
        lay.addWidget(self.add_btn)
        self.files = QListWidget()
        self.files.setMaximumHeight(110)
        self.files.setToolTip("Your data files this session (added here, in Workspace, or in Analysis ▸ Graphs and templates)")
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

    # ------------------------------------------------------------------------------------------------ files
    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add data files", "", "Data files (*.xlsx *.xlsm *.xls *.csv *.txt *.dat *.xy *.asc *.tsv);;All files (*.*)")
        if not paths: return
        tp = getattr(self.ws, "templates_page", None)
        if tp is not None and hasattr(tp, "add_files"): tp.add_files(paths)       # also pushes them into Workspace: one file, everywhere
        else: self.ws.load(paths, tick=True)
        self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    # ------------------------------------------------------------------------------------------------ what the data looks like
    def refresh(self):
        tp = getattr(self.ws, "templates_page", None)
        paths = []
        if tp is not None and hasattr(tp, "files"):
            for i in range(tp.files.count()): paths.append(tp.files.item(i).data(Qt.UserRole))
        self.files.clear()
        for p in paths:
            it = QListWidgetItem(os.path.basename(p)); it.setToolTip(p); self.files.addItem(it)
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

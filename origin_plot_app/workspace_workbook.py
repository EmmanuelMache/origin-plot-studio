"""Arrange a workbook: when one file gives several graphs (a workbook of figures, or several sheets each drawn as a
picture), decide the order they are drawn in - in Your graphs, in 'Draw all in Origin' (each project named in that
order) and in the paper set - and which of them to tick for 'Draw ticked'. Nothing about the workbook file itself
changes; this only reorders and ticks the graphs already read from it, the same way dragging rows in Your graphs does."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout


class WorkbookDialog(QDialog):
    def __init__(self, ws, path, figures):
        super().__init__(ws)
        self.setWindowTitle(f"Arrange: {os.path.basename(path)}")
        self.resize(520, 440)
        v = QVBoxLayout(self)
        lab = QLabel(f"The {len(figures)} graph(s) read from this file, in the order they are drawn. Drag to reorder (or "
                     "Move up / down); untick one to leave it out of 'Draw ticked' and the paper set.")
        lab.setWordWrap(True)
        v.addWidget(lab)
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        ticked_ids = {id(i) for i in ws.ticked()} if hasattr(ws, "ticked") else set()
        for f in figures:
            li = QListWidgetItem(_name(f))
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Checked if id(f) in ticked_ids else Qt.Unchecked)
            li.setData(Qt.UserRole, f)
            self.list.addItem(li)
        v.addWidget(self.list)
        row = QHBoxLayout()
        up = QPushButton("Move up"); up.clicked.connect(lambda: self._move(-1)); row.addWidget(up)
        down = QPushButton("Move down"); down.clicked.connect(lambda: self._move(1)); row.addWidget(down)
        row.addStretch(1)
        v.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _move(self, d):
        r = self.list.currentRow()
        if r < 0:
            return
        r2 = r + d
        if not (0 <= r2 < self.list.count()):
            return
        it = self.list.takeItem(r); self.list.insertItem(r2, it); self.list.setCurrentRow(r2)

    def ordered(self):
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def ticks(self):
        return {id(self.list.item(i).data(Qt.UserRole)): self.list.item(i).checkState() == Qt.Checked for i in range(self.list.count())}


def _name(it):
    return (it.title.strip().split("\n")[0] if getattr(it, "title", "") else str(getattr(it, "name", it)))[:70]


def arrange_workbook(w, it=None):
    """Right click a graph of a workbook (or a composed figure) > 'Arrange this workbook's figures…'."""
    it = it or w.current()
    if it is None or not getattr(it, "path", ""):
        w.set_status("Show a graph read from a file first."); return None
    path = it.path
    figures = [s for s in w.singles if getattr(s, "path", "") == path]
    if len(figures) < 2:
        w.set_status("This file gives only one graph: nothing to arrange."); return None
    dlg = WorkbookDialog(w, path, figures)
    if not dlg.exec():
        return "cancelled"
    new_order, ticks = dlg.ordered(), dlg.ticks()
    ids = {id(f) for f in figures}
    out, placed = [], False
    for s in w.singles:
        if id(s) in ids:
            if not placed:
                out.extend(new_order); placed = True
            continue
        out.append(s)
    if not placed:
        out.extend(new_order)
    keep = w.current()
    w.singles = out
    w.regroup(); w.refresh_list()
    for i in range(w.list.count()):
        item = w.list.item(i).data(Qt.UserRole + 1)
        if id(item) in ticks:
            w.list.item(i).setCheckState(Qt.Checked if ticks[id(item)] else Qt.Unchecked)
    if keep in w.items:
        w.list.setCurrentRow(w.items.index(keep))
    w.set_status(f"{len(new_order)} graph(s) of {os.path.basename(path)} arranged; Draw in Origin and the paper set follow this order.")
    return "arranged"

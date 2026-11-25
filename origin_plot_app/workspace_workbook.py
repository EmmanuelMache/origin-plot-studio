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


# Project workbook: editable working copies; source files are never overwritten.
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QTimer
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHeaderView, QInputDialog,
                              QMessageBox, QSplitter, QTableView, QTabWidget, QWidget)
import copy
from pathlib import Path
import pandas as pd
import numpy as np


class WorkingTableModel(QAbstractTableModel):
    def __init__(self, frame, changed, parent=None):
        super().__init__(parent); self.df=frame; self.changed=changed; self.undo=[]; self.redo=[]
    def rowCount(self,parent=QModelIndex()): return 0 if parent.isValid() else len(self.df)
    def columnCount(self,parent=QModelIndex()): return 0 if parent.isValid() else len(self.df.columns)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid(): return None
        value=self.df.iat[index.row(),index.column()]
        if role in (Qt.DisplayRole,Qt.EditRole): return '' if pd.isna(value) else str(value)
    def headerData(self,section,orientation,role=Qt.DisplayRole):
        if role==Qt.DisplayRole: return str(self.df.columns[section]) if orientation==Qt.Horizontal else str(section+1)
    def flags(self,index): return super().flags(index)|Qt.ItemIsEditable
    def setData(self,index,value,role=Qt.EditRole):
        if role!=Qt.EditRole or not index.isValid(): return False
        r,c=index.row(),index.column(); before=self.df.iat[r,c]
        if pd.api.types.is_numeric_dtype(self.df.iloc[:,c]):
            try: value=float(value) if str(value).strip() else np.nan
            except ValueError: return False
            if pd.api.types.is_integer_dtype(self.df.iloc[:,c]) and (pd.isna(value) or value!=int(value)):
                self.df[self.df.columns[c]]=self.df.iloc[:,c].astype(float)
        else: value=str(value)
        self.undo.append((r,c,before,value)); self.redo.clear(); self.df.iat[r,c]=value
        self.dataChanged.emit(index,index); self.changed(); return True
    def undo_edit(self):
        if not self.undo: return
        r,c,old,new=self.undo.pop(); self.redo.append((r,c,old,new)); self.df.iat[r,c]=old
        idx=self.index(r,c); self.dataChanged.emit(idx,idx); self.changed()
    def redo_edit(self):
        if not self.redo: return
        r,c,old,new=self.redo.pop(); self.undo.append((r,c,old,new)); self.df.iat[r,c]=new
        idx=self.index(r,c); self.dataChanged.emit(idx,idx); self.changed()


class WorkbookPage(QWidget):
    label='Workbook'
    def __init__(self,ws,controller):
        super().__init__(); self.ws=ws; self.controller=controller; self.paths=[]; self.models={}; self._loading=False
        self.setObjectName('workbookPage'); outer=QVBoxLayout(self); outer.setContentsMargins(22,20,22,18); outer.setSpacing(14)
        row=QHBoxLayout(); title=QVBoxLayout(); title.addWidget(QLabel('Workbook',objectName='pageTitle'))
        title.addWidget(QLabel('Edit working copies, arrange columns, merge data and prepare your graphs.',objectName='soft'))
        row.addLayout(title,1)
        for text,fn in [('Add files',lambda:ws.add_files()),('Save project',lambda:controller.save_project()),('Choose a graph →',self.choose_graph)]:
            b=QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        outer.addLayout(row)
        split=QSplitter(Qt.Horizontal); outer.addWidget(split,1)
        left=QFrame(objectName='card'); lv=QVBoxLayout(left); lv.setContentsMargins(16,16,16,16)
        lv.addWidget(QLabel('Selected files',objectName='sectionTitle'))
        self.files=QListWidget(); self.files.setDragDropMode(QAbstractItemView.InternalMove)
        self.files.currentRowChanged.connect(self.open_file); self.files.model().rowsMoved.connect(self.files_reordered)
        lv.addWidget(self.files,1)
        row=QHBoxLayout()
        for name,delta in [('Move up',-1),('Move down',1)]:
            b=QPushButton(name); b.clicked.connect(lambda _=False,d=delta:self.move_file(d)); row.addWidget(b)
        lv.addLayout(row)
        self.merge=QComboBox(); self.merge.addItems(['Append rows — matching columns','Join columns — matching X values'])
        lv.addWidget(self.merge); b=QPushButton('Merge selected files…'); b.clicked.connect(self.merge_files); lv.addWidget(b)
        note=QLabel('File order determines graph and export order. Each file keeps its own data and mapping.',objectName='soft')
        note.setWordWrap(True); lv.addWidget(note); split.addWidget(left)
        center=QFrame(objectName='card'); cv=QVBoxLayout(center); cv.setContentsMargins(16,16,16,16)
        self.caption=QLabel('Select a file',objectName='sectionTitle'); cv.addWidget(self.caption)
        row=QHBoxLayout(); self.sheet=QComboBox(); self.sheet.currentTextChanged.connect(self.open_sheet)
        row.addWidget(QLabel('Sheet')); row.addWidget(self.sheet,1)
        for name,fn in [('Undo edit',self.undo_edit),('Redo edit',self.redo_edit),('Export data…',self.export_data)]:
            b=QPushButton(name); b.clicked.connect(fn); row.addWidget(b)
        cv.addLayout(row)
        self.table=QTableView(); self.table.setAlternatingRowColors(True); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(160); cv.addWidget(self.table,1)
        self.info=QLabel('Source files stay unchanged. Save the project to retain your working-copy edits.',objectName='soft'); self.info.setWordWrap(True); cv.addWidget(self.info)
        split.addWidget(center)
        right=QFrame(objectName='card'); rv=QVBoxLayout(right); rv.setContentsMargins(16,16,16,16)
        rv.addWidget(QLabel('Columns and mapping',objectName='sectionTitle'))
        text=QLabel('Drag columns to arrange them. The first enabled numeric column is X; the remaining numeric columns are series.',objectName='soft'); text.setWordWrap(True); rv.addWidget(text)
        self.columns=QListWidget(); self.columns.setDragDropMode(QAbstractItemView.InternalMove)
        self.columns.itemChanged.connect(self.columns_changed); self.columns.model().rowsMoved.connect(self.columns_changed)
        rv.addWidget(self.columns,1)
        self.x=QComboBox(); self.y=QComboBox(); self.x.activated.connect(self.map_changed); self.y.activated.connect(self.map_changed)
        rv.addWidget(QLabel('X column')); rv.addWidget(self.x); rv.addWidget(QLabel('Primary Y column')); rv.addWidget(self.y)
        self.type=QComboBox(); from opstudio.detection import KINDS
        self.type.addItems(['Automatic']+KINDS); self.type.activated.connect(self.map_changed)
        rv.addWidget(QLabel('Measurement type')); rv.addWidget(self.type)
        split.addWidget(right); split.setSizes([260,820,260]); split.setStretchFactor(1,3)
        self.path=None; self.model=None

    def set_paths(self,paths):
        paths=list(dict.fromkeys(paths))
        if paths==self.paths:
            if self.path and self.model is not None:
                try:
                    selected=self.controller.table_of(self.path)[1]
                    frame=self.controller.raw_sheets(self.path)[selected]
                    if self.model.df is not frame or self.sheet.currentText()!=selected:self.open_file(self.files.currentRow())
                except Exception:pass
            return
        current=self.path; self.paths=paths; self._loading=True; self.files.clear()
        for p in paths:
            item=QListWidgetItem(os.path.basename(p)); item.setData(Qt.UserRole,p)
            item.setToolTip(p); item.setFlags(item.flags()|Qt.ItemIsUserCheckable); item.setCheckState(Qt.Checked); self.files.addItem(item)
        self._loading=False
        if paths: self.files.setCurrentRow(paths.index(current) if current in paths else 0)
        else:
            self.path=None; self.model=None; self.table.setModel(None); self.columns.clear(); self.caption.setText('Select files from Start Here or Analysis')

    def open_file(self,index):
        if self._loading or not 0<=index<self.files.count(): return
        self.path=self.files.item(index).data(Qt.UserRole)
        try:
            table,selected,names,_cols,_prefs=self.controller.table_of(self.path)
            self._loading=True; self.sheet.clear(); self.sheet.addItems(names); self.sheet.setCurrentText(selected); self._loading=False
            self.open_sheet(selected)
        except Exception as e: self.info.setText('Could not open file: '+str(e)); self._loading=False

    def open_sheet(self,name):
        if self._loading or self.path is None: return
        slug=self.controller.project_for(self.path)
        try:
            frame=self.controller.raw_sheets(self.path,slug)[name]; prefs=self.controller.settings_for(self.path,slug); prefs['sheet']=name
            key=(slug,self.path,name)
            if key not in self.models or self.models[key].df is not frame:
                self.models[key]=WorkingTableModel(frame,lambda p=self.path,s=slug,n=name:self.edited(p,s,n),self)
            self.model=self.models[key]; self.table.setModel(self.model)
            self.caption.setText(os.path.basename(self.path)+' / '+(name or 'Data'))
            self.info.setText(f'{len(frame):,} rows · {len(frame.columns)} columns · Working copy; source file unchanged')
            self.refresh_columns()
        except Exception as e: self.info.setText('Could not open sheet: '+str(e))

    def edited(self,path,slug,sheet):
        frame=self.controller.raw_sheets(path,slug)[sheet]
        prefs=self.controller.settings_for(path,slug)
        # JSON-compatible, lossless for imported scalar data; null represents missing cells.
        clean=frame.astype(object).where(pd.notna(frame),None)
        import json, workspace_projects as WP
        values=json.loads(json.dumps(clean.values.tolist(),default=WP._json_default))
        prefs.setdefault('edited_sheets',{})[sheet]={'columns':[str(c) for c in frame.columns],'data':values}
        self.controller.changed(path,slug); self.ws.templates_page._sheet_pick_cache.clear()
        self.ws.templates_page.filter_templates()
        QTimer.singleShot(0, lambda: self.controller.refresh_source_graphs(path, slug))

    def refresh_columns(self):
        if not self.path: return
        from opstudio.detection import detect
        table,_,_,cols,prefs=self.controller.table_of(self.path)
        self._loading=True; self.columns.clear()
        order=list(prefs.get('order') or cols); order += [c for c in cols if c not in order]
        for c in order:
            if c not in cols: continue
            item=QListWidgetItem(c); item.setFlags(item.flags()|Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if c in prefs.get('off',[]) else Qt.Checked); self.columns.addItem(item)
        for box,value in [(self.x,table.x),(self.y,table.ys[0] if table.ys else '')]:
            box.clear(); box.addItems(table.numeric)
            if value: box.setCurrentText(value)
        self.type.setCurrentText(prefs.get('type') or 'Automatic'); self._loading=False

    def columns_changed(self,*_):
        if self._loading or not self.path: return
        prefs=self.controller.mapping_for(self.path)
        prefs['order']=[self.columns.item(i).text() for i in range(self.columns.count())]
        prefs['off']=[self.columns.item(i).text() for i in range(self.columns.count()) if self.columns.item(i).checkState()!=Qt.Checked]
        self.controller.changed(self.path); self.ws.templates_page.filter_templates()
        QTimer.singleShot(0,self.refresh_columns)

    def map_changed(self,*_):
        if self._loading or not self.path: return
        if self.x.currentText()==self.y.currentText(): self.ws.set_status('X and Y must use different columns.'); return
        self.controller.set_mapping(self.path,self.x.currentText(),self.y.currentText(),self.sheet.currentIndex(),self.type.currentText())
        self.refresh_columns()

    def move_file(self,delta):
        index=self.files.currentRow(); target=index+delta
        if index<0 or not 0<=target<self.files.count(): return
        item=self.files.takeItem(index); self.files.insertItem(target,item); self.files.setCurrentRow(target); self.files_reordered()

    def files_reordered(self,*_):
        if self._loading: return
        self.paths=[self.files.item(i).data(Qt.UserRole) for i in range(self.files.count())]
        slug=self.controller.active_project
        if slug:
            import workspace_projects as WP
            WP.reorder(slug,self.paths)
        order={p:i for i,p in enumerate(self.paths)}
        self.ws.singles.sort(key=lambda i:order.get(getattr(i,'path',''),len(order)))
        self.ws.regroup(); self.ws.refresh_list(); self.controller.select_inputs(self.paths)

    def undo_edit(self):
        if self.model: self.model.undo_edit()
    def redo_edit(self):
        if self.model: self.model.redo_edit()

    def merge_files(self):
        paths=[self.files.item(i).data(Qt.UserRole) for i in range(self.files.count()) if self.files.item(i).checkState()==Qt.Checked]
        if len(paths)<2: self.ws.set_status('Select at least two files to merge.'); return
        try:
            from workbook_data import merge_tables
            result=merge_tables([(p,self.controller.table_for(p)) for p in paths],self.merge.currentIndex())
            name,ok=QInputDialog.getText(self,'Merged dataset','Dataset name:',text='Merged data')
            if not ok or not name.strip(): return
            import workspace_projects as WP
            import workspace_qt as WQ
            slug=self.controller.active_project
            if not slug: self.ws.set_status('Create or select a project before merging.'); return
            folder=WQ.cfg_path().parent/'project_data'/slug/'derived'; folder.mkdir(parents=True,exist_ok=True)
            import re,uuid
            base=re.sub(r'[^\w.-]+','_',name.strip()); path=folder/(base+'_'+uuid.uuid4().hex[:6]+'.csv')
            result.to_csv(path,index=False); WP.add_files(slug,[str(path)])
            self.ws.templates_page.add_files([str(path)],project=WP.get(slug)['name'],
                on_done=lambda items:[setattr(i,'project_id',slug) for i in items])
            self.set_paths(paths+[str(path)]); self.files.setCurrentRow(self.files.count()-1)
            self.controller.changed(str(path),slug); self.ws.set_status('Merged data created as a separate dataset. Original files are unchanged.')
        except Exception as e: self.ws.set_status('Merge could not be completed: '+str(e))

    def export_data(self):
        if self.model is None: return
        path,_=QFileDialog.getSaveFileName(self,'Export working data',Path(self.path).stem+'_edited.csv','CSV (*.csv);;TSV (*.tsv);;Excel (*.xlsx)')
        if not path: return
        try:
            if path.lower().endswith('.xlsx'): self.model.df.to_excel(path,index=False)
            else: self.model.df.to_csv(path,index=False,sep='\t' if path.lower().endswith('.tsv') else ',')
            self.ws.set_status('Working data exported: '+path)
        except Exception as e: self.ws.set_status('Export failed: '+str(e))

    def choose_graph(self):
        self.controller.select_inputs(self.paths)
        sh=self.ws.pages.widget(6)
        if self.path: sh._current_path=self.path
        self.ws.go(6)

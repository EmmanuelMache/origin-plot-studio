"""Arrange a workbook: when one file gives several graphs (a workbook of figures, or several sheets each drawn as a
picture), decide the order they are drawn in - in Your graphs, in 'Draw all in Origin' (each project named in that
order) and in the paper set - and which of them to tick for 'Draw ticked'. Nothing about the workbook file itself
changes; this only reorders and ticks the graphs already read from it, the same way dragging rows in Your graphs does."""
from __future__ import annotations

import os
import re

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
    read_only=False               # a table made by the app (files side by side): looked at and exported, not edited
    only=None                     # names of the only columns that can be edited (the Label column of a peak table)
    def flags(self,index): return super().flags(index)|(Qt.NoItemFlags if (self.read_only or (self.only is not None and str(self.df.columns[index.column()]) not in self.only)) else Qt.ItemIsEditable)
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
        self.merge=QComboBox(); self.merge.addItems(['Append rows — matching columns','Join columns — matching X values','Side by side — each file keeps its own X'])
        self.merge.setCurrentIndex(2)
        self.merge.setToolTip('How the ticked files are put into one table. Side by side: for every file its X column and its Y columns next to each other (and the DTG curve of a thermal run) - nothing is interpolated. '
                              'Append rows: the rows of all files under each other (the same columns in every file). Join columns: one X column for all (identical X values in the same order)')
        lv.addWidget(self.merge); b=QPushButton('Merge selected files…'); b.clicked.connect(self.merge_files); lv.addWidget(b)
        b.setToolTip('Make one table of the ticked files and add it as a dataset of its own: it is listed here and in Your graphs, and can be drawn and exported. The files themselves stay as they are')
        note=QLabel('File order determines graph and export order. Each file keeps its own data and mapping. Files that belong together (the same kind of data, names built the same way) '
                    'also get a table of all of them side by side, made by the app: it is the last entry of the list.',objectName='soft')
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
        from PySide6.QtWidgets import QCheckBox
        self.draw_labels=QCheckBox('Draw these labels on the graph'); self.draw_labels.setVisible(False); self.draw_labels.toggled.connect(self.labels_toggled)
        self.draw_labels.setToolTip('On: the TGA / FTIR graphs of this file in Workspace write the Label of each peak beside its position. The labels are yours: type in the Label column, '
                                    'take the question mark away when you are sure, clear a cell to leave a peak unnamed. Off: the graphs show the positions only, as before')
        cv.addWidget(self.draw_labels)
        self.info=QLabel('Source files stay unchanged. Save the project to retain your working-copy edits.',objectName='soft'); self.info.setWordWrap(True); cv.addWidget(self.info)
        split.addWidget(center)
        right=QFrame(objectName='card'); rv=QVBoxLayout(right); rv.setContentsMargins(16,16,16,16)
        rv.addWidget(QLabel('Columns and mapping',objectName='sectionTitle'))
        text=QLabel('Drag columns to arrange them. The first enabled numeric column is X; the remaining numeric columns are series.',objectName='soft'); text.setWordWrap(True); rv.addWidget(text)
        self.columns=QListWidget(); self.columns.setDragDropMode(QAbstractItemView.InternalMove)
        self.columns.itemChanged.connect(self.columns_changed); self.columns.model().rowsMoved.connect(self.columns_changed)
        self.columns.setContextMenuPolicy(Qt.CustomContextMenu); self.columns.customContextMenuRequested.connect(self.columns_menu)
        self.columns.setToolTip('Untick a column to leave it out: it is not carried to Workspace, and the graphs offered and made no longer count on it. Right click: leave it out (or use it) in all files')
        rv.addWidget(self.columns,1)
        self.b_all=QPushButton('Use these column choices for all files'); self.b_all.clicked.connect(self.columns_to_all)
        self.b_all.setToolTip('The columns unticked here are left out in every file of the list that has a column of that name (and the ticked ones are used again). The order of the columns stays as it is in each file')
        rv.addWidget(self.b_all)
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
        self.add_series_entries()
        self._loading=False
        if paths: self.files.setCurrentRow(paths.index(current) if current in paths else 0)
        else:
            self.path=None; self.model=None; self.table.setModel(None); self.columns.clear(); self.caption.setText('Select files from Start Here or Analysis')

    def series_groups(self):
        """The files of the list that belong together: the same kind of measurement (recognised, not guessed) and names
        built the same way. [(label, [paths], why)]"""
        import related
        from opstudio.detection import detect
        kinds={}
        for p in self.paths:
            try:
                if not self.controller.ready(p): continue
                t=self.controller.table_for(p); d=detect(t,getattr(t,'measurement_type',None))
                if not d.needs_confirmation and t.x and t.ys: kinds.setdefault(d.kind,[]).append(p)
            except Exception: continue
        out=[]
        for kind,ps in kinds.items():
            for g in related.groups(ps): out.append((related.series_label(g),g,related.series(g)['why']))
        return out

    def add_series_entries(self):
        """One entry per set of files that belong together: all of them side by side, made by the app."""
        for i in reversed(range(self.files.count())):
            if not isinstance(self.files.item(i).data(Qt.UserRole),str): self.files.takeItem(i)
        try: groups=self.series_groups()
        except Exception: groups=[]
        for label,ps,why in groups:
            item=QListWidgetItem(f"\u29c9 All of '{label}' side by side \u00b7 {len(ps)} files"); item.setData(Qt.UserRole,('series',tuple(ps),label))
            f=item.font(); f.setItalic(True); item.setFont(f); item.setFlags((item.flags()|Qt.ItemIsEnabled|Qt.ItemIsSelectable)&~Qt.ItemIsUserCheckable&~Qt.ItemIsDragEnabled)
            item.setToolTip(f"Made by the app: {why}. For every file its X column and its Y columns next to each other (and the DTG curve of a thermal run); nothing is interpolated. "
                            "'Export data…' saves it; 'Merge selected files…' adds such a table as a dataset of its own")
            self.files.addItem(item)

    def worked_columns(self,path,table):
        """[(name, values)] the app works out for a file: the DTG curve of a thermal run."""
        import related
        try: d=related.dtg_column(table)
        except Exception: d=None
        return [(d[0],d[1])] if d else []

    def open_series(self,data):
        import related
        _kind,ps,label=data; self.path=None
        try:
            frame=related.side_by_side([(p,self.controller.table_for(p)) for p in ps],extra=self.worked_columns)
            self.model=WorkingTableModel(frame,lambda:None,self); self.model.read_only=True; self.table.setModel(self.model); self._series_label=label
            self._loading=True; self.sheet.clear(); self.columns.clear(); self.x.clear(); self.y.clear(); self._loading=False
            self.caption.setText(f"All of '{label}' side by side")
            self.info.setText(f'{len(frame):,} rows \u00b7 {len(frame.columns)} columns \u00b7 made by the app from {len(ps)} files; every file keeps its own X values, nothing is interpolated. Export data\u2026 saves it')
        except Exception as e: self.info.setText('The files could not be put side by side: '+str(e))

    def open_file(self,index):
        if self._loading or not 0<=index<self.files.count(): return
        data=self.files.item(index).data(Qt.UserRole)
        if not isinstance(data,str): return self.open_series(data)
        self.path=data
        try:
            table,selected,names,_cols,_prefs=self.controller.table_of(self.path)
            self._loading=True; self.sheet.clear(); self.sheet.addItems(names)
            import related
            try:
                if self.controller.peak_frame(self.path)[0] is not None:
                    self.sheet.addItem(related.PEAKS_SHEET); self.sheet.setItemData(self.sheet.count()-1,'The peaks the app found in this file (steps of mass loss of a thermal run, bands of an infrared spectrum), what each may be, and a Label column of your own',Qt.ToolTipRole)
            except Exception: pass
            self.sheet.setCurrentText(selected); self._loading=False
            self.open_sheet(selected)
        except Exception as e: self.info.setText('Could not open file: '+str(e)); self._loading=False

    def open_peaks(self):
        """The peak table of the file on show: read it, type your labels, switch them on for the graph."""
        import related
        frame,kind=self.controller.peak_frame(self.path)
        if frame is None: return
        path=self.path; key=(self.controller.project_for(path),path,related.PEAKS_SHEET)
        if key not in self.models or self.models[key].df is not frame:
            self.models[key]=WorkingTableModel(frame,lambda p=path:self.controller.set_peak_labels(p),self); self.models[key].only=('Label',)
        self.model=self.models[key]; self.table.setModel(self.model); self.table.resizeColumnsToContents()
        self.caption.setText(os.path.basename(path)+' / peaks')
        what='steps of mass loss (minima of the DTG curve)' if kind=='TGA' else 'bands'
        self.info.setText(f"{len(frame)} {what} found by the app. 'May be' is the usual event or bond at that position, the most likely first - a possibility to check, not a finding. "
                          "The Label column is yours to type in. Export data\u2026 saves this table.")
        slug=self.controller.project_for(path); sel=self.controller._table(path,slug)[1]
        on=bool(self.controller.settings_for(path,slug).get('sheet_settings',{}).get(sel,{}).get('peak_names_on'))
        self._loading=True; self.draw_labels.setChecked(on); self.draw_labels.setVisible(True); self.columns.clear(); self._loading=False

    def labels_toggled(self,on):
        if self._loading or not self.path: return
        self.controller.set_peak_labels(self.path,on=bool(on))
        self.ws.set_status(('The labels of this table are drawn on the TGA / FTIR graphs of this file in Workspace.' if on else 'The graphs of this file show the positions only again.'))

    def open_sheet(self,name):
        if self._loading or self.path is None: return
        import related
        self.draw_labels.setVisible(False)
        if name==related.PEAKS_SHEET: return self.open_peaks()
        slug=self.controller.project_for(self.path)
        try:
            frame=self.controller.raw_sheets(self.path,slug)[name]; prefs=self.controller.settings_for(self.path,slug); prefs['sheet']=name
            self.add_worked_columns(frame,slug,name)
            key=(slug,self.path,name)
            if key not in self.models or self.models[key].df is not frame:
                self.models[key]=WorkingTableModel(frame,lambda p=self.path,s=slug,n=name:self.edited(p,s,n),self)
            self.model=self.models[key]; self.table.setModel(self.model)
            self.caption.setText(os.path.basename(self.path)+' / '+(name or 'Data'))
            self.info.setText(f'{len(frame):,} rows · {len(frame.columns)} columns · Working copy; source file unchanged')
            self.refresh_columns()
        except Exception as e: self.info.setText('Could not open sheet: '+str(e))

    def add_worked_columns(self,frame,slug,name):
        """The DTG curve of a thermal run as a column of the working copy (once): there to be seen and exported. It is
        left out of the graphs - they work out their own - unless you tick it under Columns."""
        try:
            scoped=self.controller.settings_for(self.path,slug).setdefault('sheet_settings',{}).setdefault(name,{})
            if scoped.get('derived'): return
            table=self.controller._table(self.path,slug,name)[0]
            for col,values in self.worked_columns(self.path,table):
                if col in frame.columns or len(values)!=len(frame): continue
                frame[col]=values; scoped.setdefault('derived',[]).append(col)
        except Exception: pass

    def edited(self,path,slug,sheet):
        frame=self.controller.raw_sheets(path,slug)[sheet]
        prefs=self.controller.settings_for(path,slug)
        # JSON-compatible, lossless for imported scalar data; null represents missing cells.
        clean=frame.astype(object).where(pd.notna(frame),None)
        import json, workspace_projects as WP
        values=json.loads(json.dumps(clean.values.tolist(),default=WP._json_default))
        prefs.setdefault('edited_sheets',{})[sheet]={'columns':[str(c) for c in frame.columns],'data':values}
        self.controller.changed(path,slug); self.ws.templates_page._sheet_pick_cache.clear()
        for k in [k for k in self.controller._peak_frames if k[1]==path]: self.controller._peak_frames.pop(k,None)      # other numbers: the peaks are looked for again
        self.ws.templates_page.filter_templates()
        QTimer.singleShot(0, lambda: self.controller.refresh_source_graphs(path, slug))

    def refresh_columns(self):
        if not self.path: return
        from opstudio.detection import detect
        table,_,_,cols,prefs=self.controller.table_of(self.path)
        self._loading=True; self.columns.clear()
        order=list(prefs.get('order') or table.cols); order += [c for c in cols if c not in order]
        for c in order:
            if c not in cols: continue
            item=QListWidgetItem(c); item.setFlags(item.flags()|Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if c in prefs.get('off',[]) else Qt.Checked); self.columns.addItem(item)
        for c in prefs.get('derived',[]):                        # worked out by the app: listed, unticked (not in the graphs) until you tick it
            if c in cols: continue
            item=QListWidgetItem(c+'  (worked out by the app)'); item.setData(Qt.UserRole,c); item.setFlags((item.flags()|Qt.ItemIsUserCheckable)&~Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Unchecked); item.setToolTip('The app worked this column out from the file (see the table). It is exported with the data. Tick it to use it in graphs as well'); self.columns.addItem(item)
        for box,value in [(self.x,table.x),(self.y,table.ys[0] if table.ys else '')]:
            box.clear(); box.addItems(table.numeric)
            if value: box.setCurrentText(value)
        self.type.setCurrentText(prefs.get('type') or 'Automatic'); self._loading=False

    def columns_changed(self,*_):
        if self._loading or not self.path: return
        prefs=self.controller.mapping_for(self.path); items=[self.columns.item(i) for i in range(self.columns.count())]
        worked=set(prefs.get('derived',[])); name=lambda it: it.data(Qt.UserRole) or it.text()
        prefs['derived_on']=[name(it) for it in items if name(it) in worked and it.checkState()==Qt.Checked]
        prefs['order']=[name(it) for it in items if not (name(it) in worked and it.checkState()!=Qt.Checked)]
        prefs['off']=[name(it) for it in items if it.checkState()!=Qt.Checked and name(it) not in worked]
        self.controller.changed(self.path); self.ws.templates_page._sheet_pick_cache.clear(); self.ws.templates_page.filter_templates()
        path=self.path; QTimer.singleShot(0,lambda: self.controller.refresh_source_graphs(path))
        QTimer.singleShot(0,self.refresh_columns)

    def set_column_everywhere(self,column,use):
        """Leave a column out (use=False) or use it again (True) in every file of the list that has a column of that name.
        Returns the number of files changed."""
        n=0
        for p in self.paths:
            try:
                _t,_sel,_names,cols,prefs=self.controller.table_of(p)
                if column not in cols: continue
                off=[c for c in (prefs.get('off') or []) if c!=column]+([] if use else [column])
                if sorted(off)==sorted(prefs.get('off') or []) and 'off' in prefs: continue
                prefs['off']=off; prefs.setdefault('order',list(prefs.get('order') or cols)); n+=1
                self.controller.changed(p); self.controller.refresh_source_graphs(p)
            except Exception: continue
        self.ws.templates_page._sheet_pick_cache.clear(); self.ws.templates_page.filter_templates(); self.refresh_columns()
        return n

    def columns_to_all(self):
        """The ticks of the columns on show, for every file of the list."""
        if not self.path: return 0
        items=[(self.columns.item(i).text(),self.columns.item(i).checkState()==Qt.Checked) for i in range(self.columns.count()) if not self.columns.item(i).data(Qt.UserRole)]; n=0
        for name,used in items: n=max(n,self.set_column_everywhere(name,used))            # (a column the app worked out belongs to its own file)
        off=[name for name,used in items if not used]
        self.ws.set_status((f"Left out in all {len(self.paths)} file(s) that have them: {', '.join(off)}. They are not carried to Workspace." if off else 'Every column is used in all files again.'))
        return n

    def columns_menu(self,pos):
        it=self.columns.itemAt(pos)
        if it is None or it.data(Qt.UserRole): return
        from PySide6.QtWidgets import QMenu
        m=QMenu(self); c=it.text()
        m.addAction(f"Leave '{c}' out in all files",lambda: self.ws.set_status(f"'{c}' is left out in {self.set_column_everywhere(c,False)} file(s): not carried to Workspace, not counted for the graphs offered."))
        m.addAction(f"Use '{c}' in all files",lambda: self.ws.set_status(f"'{c}' is used again in {self.set_column_everywhere(c,True)} file(s)."))
        m.exec(self.columns.mapToGlobal(pos))

    def map_changed(self,*_):
        if self._loading or not self.path: return
        if self.x.currentText()==self.y.currentText(): self.ws.set_status('X and Y must use different columns.'); return
        self.controller.set_mapping(self.path,self.x.currentText(),self.y.currentText(),self.sheet.currentIndex(),self.type.currentText())
        self.refresh_columns()

    def move_file(self,delta):
        index=self.files.currentRow(); target=index+delta
        if index<0 or not 0<=target<len(self.paths) or not isinstance(self.files.item(index).data(Qt.UserRole),str): return      # the tables of the app stay last
        item=self.files.takeItem(index); self.files.insertItem(target,item); self.files.setCurrentRow(target); self.files_reordered()

    def files_reordered(self,*_):
        if self._loading: return
        self.paths=[self.files.item(i).data(Qt.UserRole) for i in range(self.files.count()) if isinstance(self.files.item(i).data(Qt.UserRole),str)]
        self._loading=True; self.add_series_entries(); self._loading=False
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
        paths=[self.files.item(i).data(Qt.UserRole) for i in range(self.files.count()) if self.files.item(i).checkState()==Qt.Checked and isinstance(self.files.item(i).data(Qt.UserRole),str)]
        if len(paths)<2: self.ws.set_status('Select at least two files to merge.'); return None
        try:
            from workbook_data import merge_tables
            import related
            inputs=[(p,self.controller.table_for(p)) for p in paths]; mode=self.merge.currentIndex()
            result=related.side_by_side(inputs,extra=self.worked_columns) if mode==2 else merge_tables(inputs,mode)
            name,ok=QInputDialog.getText(self,'Merged dataset','Dataset name:',text=(related.series_label(paths) if related.series(paths)['related'] else 'Merged data'))
            if not ok or not name.strip(): return None
            import workspace_projects as WP
            import workspace_qt as WQ
            slug=self.controller.active_project if self.controller.active_project and all(self.controller.project_for(p)==self.controller.active_project for p in paths) else None
            # files that are in no project are merged too: the table is kept with the app's own data, as a file of this session
            folder=WQ.cfg_path().parent/'project_data'/(slug or '_session')/'derived'; folder.mkdir(parents=True,exist_ok=True)
            import re,uuid
            base=re.sub(r'[^\w.-]+','_',name.strip()); path=folder/(base+'_'+uuid.uuid4().hex[:6]+'.csv')
            result.to_csv(path,index=False)
            if slug:
                WP.add_files(slug,[str(path)])
                self.ws.templates_page.add_files([str(path)],project=WP.get(slug)['name'],on_done=lambda items:[setattr(i,'project_id',slug) for i in items])
            else: self.ws.templates_page.add_files([str(path)])
            self.set_paths(self.paths+[str(path)]); self.files.setCurrentRow(self.paths.index(str(path)))
            self.controller.changed(str(path),slug)
            self.ws.set_status(f"'{name.strip()}' is a dataset of its own now: the entry selected in this list, also in Your graphs and on Start here. The {len(paths)} files are unchanged.")
            return str(path)
        except Exception as e: self.ws.set_status('Merge could not be completed: '+str(e)); return None

    def export_data(self):
        if self.model is None: return None
        start=(Path(self.path).stem+'_edited.csv') if self.path else (re.sub(r'[^\w.-]+','_',getattr(self,'_series_label','merged'))+'_side_by_side.csv')
        path,_=QFileDialog.getSaveFileName(self,'Export working data',start,'CSV (*.csv);;TSV (*.tsv);;Excel (*.xlsx)')
        if not path: return None
        try:
            peaks=None
            if self.path and self.sheet.currentText()!=__import__('related').PEAKS_SHEET:
                try: peaks=self.controller.peak_frame(self.path)[0]
                except Exception: peaks=None
            if path.lower().endswith('.xlsx'):
                with pd.ExcelWriter(path) as xw:
                    self.model.df.to_excel(xw,index=False,sheet_name='Data')
                    if peaks is not None: peaks.to_excel(xw,index=False,sheet_name='Peaks')            # the peaks of the file and what they may be, beside its data
            else: self.model.df.to_csv(path,index=False,sep='\t' if path.lower().endswith('.tsv') else ',')
            self.ws.set_status('Working data exported: '+path+(' (sheets Data and Peaks)' if peaks is not None and path.lower().endswith('.xlsx') else '')); return path
        except Exception as e: self.ws.set_status('Export failed: '+str(e)); return None

    def choose_graph(self):
        self.controller.select_inputs(self.paths)
        sh=self.ws.pages.widget(6)
        if self.path: sh._current_path=self.path
        self.ws.go(6)

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
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QHeaderView, QInputDialog,
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
    roles={}                      # column name -> 'X' or 'Y': shown in the header
    def headerData(self,section,orientation,role=Qt.DisplayRole):
        if role==Qt.DisplayRole:
            if orientation!=Qt.Horizontal: return str(section+1)
            name=str(self.df.columns[section]); r=self.roles.get(name)
            return f"{name}   [{r}]" if r else name
    def move_column(self,c,delta):
        """A column one place to the left (-1) or right (+1) in the working copy."""
        t=c+delta
        if self.locked() or not (0<=c<len(self.df.columns) and 0<=t<len(self.df.columns)): return False
        order=list(range(len(self.df.columns))); order[c],order[t]=order[t],order[c]; snap=self.df.iloc[:,order].copy()
        before=self.df.copy(); self._put(snap); self.undo.append(('table',before,self.df.copy())); del self.undo[:-40]; self.redo.clear(); self.changed(); return True
    read_only=False               # a table made by the app (files side by side): looked at and exported, not edited
    only=None                     # names of the only columns that can be edited (the Label column of a peak table)
    def flags(self,index): return super().flags(index)|(Qt.NoItemFlags if (self.read_only or (self.only is not None and str(self.df.columns[index.column()]) not in self.only)) else Qt.ItemIsEditable)
    def setData(self,index,value,role=Qt.EditRole):
        if role!=Qt.EditRole or not index.isValid() or self.read_only: return False
        r,c=index.row(),index.column(); before=self.df.iat[r,c]
        if pd.api.types.is_numeric_dtype(self.df.iloc[:,c]):
            try: value=float(value) if str(value).strip() else np.nan
            except ValueError: return False
            if pd.api.types.is_integer_dtype(self.df.iloc[:,c]) and (pd.isna(value) or value!=int(value)):
                self.df[self.df.columns[c]]=self.df.iloc[:,c].astype(float)
        else: value=str(value)
        self.undo.append((r,c,before,value)); self.redo.clear(); self.df.iat[r,c]=value
        self.dataChanged.emit(index,index); self.changed(); return True
    def locked(self): return self.read_only or self.only is not None
    def _put(self,snap):
        """The working copy takes the content of 'snap' - the same table object stays in use everywhere."""
        self.beginResetModel()
        self.df.drop(index=self.df.index,inplace=True); self.df.drop(columns=list(self.df.columns),inplace=True)
        for k,c in enumerate(snap.columns): self.df.insert(k,c,snap.iloc[:,k].to_numpy())
        self.endResetModel()
    def _change(self,fn):
        """A change of several cells, rows or columns as ONE step of Undo."""
        before=self.df.copy(); self.beginResetModel(); fn(); self.endResetModel()
        self.undo.append(('table',before,self.df.copy())); del self.undo[:-40]; self.redo.clear(); self.changed()
    def clear_cells(self,cells):
        """Empty these (row, column) cells."""
        cells=[(r,c) for r,c in cells if 0<=r<len(self.df) and 0<=c<len(self.df.columns)]
        if not cells or self.locked(): return 0
        def go():
            for c in sorted({c for _r,c in cells}):
                rows=[r for r,cc in cells if cc==c]; name=self.df.columns[c]
                if pd.api.types.is_integer_dtype(self.df.iloc[:,c]): self.df[name]=self.df.iloc[:,c].astype(float)
                self.df.iloc[rows,c]=np.nan if pd.api.types.is_numeric_dtype(self.df.iloc[:,c]) else ''
        self._change(go); return len(cells)
    def delete_rows(self,rows):
        rows=sorted({r for r in rows if 0<=r<len(self.df)})
        if not rows or self.locked(): return 0
        def go(): self.df.drop(index=self.df.index[rows],inplace=True); self.df.reset_index(drop=True,inplace=True)
        self._change(go); return len(rows)
    def delete_columns(self,cols):
        names=[self.df.columns[c] for c in sorted({c for c in cols if 0<=c<len(self.df.columns)})]
        if not names or self.locked() or len(names)>=len(self.df.columns): return []
        self._change(lambda: self.df.drop(columns=names,inplace=True)); return [str(n) for n in names]
    # ---- the tools of a spreadsheet: each is one step of Undo edit
    @staticmethod
    def _value(text,numeric):
        t=str(text).strip()
        if not numeric: return str(text)
        if not t: return np.nan
        try: return float(t.replace(',','.')) if t.count(',')==1 and '.' not in t else float(t)
        except ValueError: return str(text)
    def paste(self,r0,c0,rows):
        """A block of cells (rows of texts, as copied from Excel or from this table) with its top-left corner at (r0, c0).
        Rows and columns are added when the block reaches past the table. Returns (rows, columns) pasted."""
        rows=[list(r) for r in rows if r is not None]
        if not rows or self.locked() or r0<0 or c0<0: return (0,0)
        width=max(len(r) for r in rows)
        def go():
            need_r=r0+len(rows)-len(self.df)
            for k in range(max(0,c0+width-len(self.df.columns))):
                name='New column'; j=2
                while name in self.df.columns: name=f'New column {j}'; j+=1
                self.df[name]=np.nan
            if need_r>0:
                extra=pd.DataFrame({c:[np.nan]*need_r for c in self.df.columns}); base=self.df.copy()
                self._fill(pd.concat([base,extra],ignore_index=True))
            for c in range(width):
                col=self.df.columns[c0+c]; numeric=pd.api.types.is_numeric_dtype(self.df[col]); vals=[self._value(r[c] if c<len(r) else '',numeric) for r in rows]
                if numeric and any(isinstance(v,str) for v in vals): self.df[col]=self.df[col].astype(object)
                elif pd.api.types.is_integer_dtype(self.df[col]): self.df[col]=self.df[col].astype(float)
                self.df.iloc[r0:r0+len(rows),c0+c]=vals
        self._change(go); return (len(rows),width)
    def _fill(self,snap):
        self.df.drop(index=self.df.index,inplace=True); self.df.drop(columns=list(self.df.columns),inplace=True)
        for k,c in enumerate(snap.columns): self.df.insert(k,c,snap.iloc[:,k].to_numpy())
    def insert_rows(self,r,n=1):
        """n empty rows before row r (r = number of rows: at the end)."""
        if self.locked() or n<1: return 0
        r=max(0,min(r,len(self.df)))
        def go():
            empty=pd.DataFrame({c:[np.nan]*n for c in self.df.columns}); base=self.df.copy()
            self._fill(pd.concat([base.iloc[:r],empty,base.iloc[r:]],ignore_index=True))
        self._change(go); return n
    def insert_column(self,c,name):
        name=str(name).strip()
        if self.locked() or not name or name in [str(x) for x in self.df.columns]: return False
        self._change(lambda: self.df.insert(max(0,min(c,len(self.df.columns))),name,np.nan)); return True
    def rename_column(self,c,name):
        name=str(name).strip()
        if self.locked() or not name or not 0<=c<len(self.df.columns) or name in [str(x) for i,x in enumerate(self.df.columns) if i!=c]: return False
        old=self.df.columns[c]
        if str(old)==name: return False
        self._change(lambda: self.df.rename(columns={old:name},inplace=True)); return True
    def sort_by(self,c,ascending=True):
        if self.locked() or not 0<=c<len(self.df.columns): return False
        col=self.df.columns[c]
        def go():
            key=pd.to_numeric(self.df[col],errors='coerce'); order=(key if key.notna().any() else self.df[col].astype(str)).sort_values(ascending=ascending,kind='stable',na_position='last').index
            self._fill(self.df.loc[order].reset_index(drop=True).copy())
        self._change(go); return True
    def fill_down(self,cells):
        """In each selected column: the value of its top selected cell in all selected cells below it."""
        if self.locked() or not cells: return 0
        by={}
        for r,c in cells: by.setdefault(c,[]).append(r)
        by={c:sorted(rs) for c,rs in by.items() if len(rs)>1}
        if not by: return 0
        def go():
            for c,rs in by.items(): self.df.iloc[rs[1:],c]=self.df.iat[rs[0],c]
        self._change(go); return sum(len(rs)-1 for rs in by.values())
    def letters(self):
        """Excel's letters for the columns: A, B ... Z, AA ..."""
        out=[]
        for i in range(len(self.df.columns)):
            s='';k=i
            while True:
                s=chr(65+k%26)+s; k=k//26-1
                if k<0: break
            out.append(s)
        return out
    def add_calculated(self,name,formula):
        """A new last column worked out from the others. The formula uses the letters of the columns as in Excel (A, B,
        C ...) and + - * / ** ( ), with log, log10, exp, sqrt, abs, sin, cos, tan, pi, cumsum, diff, mean, min, max:
        '=C/C.max()*100' or '(B-A)/2'. Returns '' or what is wrong with it."""
        name=str(name).strip(); f=str(formula).strip().lstrip('=').replace('^','**')
        if self.locked(): return 'this table cannot be changed'
        if not name or name in [str(x) for x in self.df.columns]: return 'give the new column a name that is not used yet'
        if not f: return 'type a formula, for example  B*2  or  (C-B)/A'
        ns={l:pd.to_numeric(self.df.iloc[:,i],errors='coerce') for i,l in enumerate(self.letters())}
        fn={'log':np.log,'ln':np.log,'log10':np.log10,'exp':np.exp,'sqrt':np.sqrt,'abs':np.abs,'sin':np.sin,'cos':np.cos,'tan':np.tan,'pi':np.pi,
            'cumsum':lambda s:s.cumsum(),'diff':lambda s:s.diff(),'mean':lambda s:s.mean(),'min':lambda s:s.min(),'max':lambda s:s.max()}
        if re.search(r'__|import|lambda|\[|\{|;',f): return 'only column letters, numbers, + - * / ** ( ) and the listed functions are understood'
        try:
            with np.errstate(all='ignore'): out=eval(f,{'__builtins__':{}},{**fn,**ns})
        except Exception as e: return f'the formula could not be worked out: {e}'
        try: values=np.broadcast_to(np.asarray(out,dtype=float),(len(self.df),)).copy()
        except Exception: return 'the formula does not give one number per row'
        self._change(lambda: self.df.insert(len(self.df.columns),name,values)); return ''
    def undo_edit(self):
        if not self.undo: return
        step=self.undo.pop(); self.redo.append(step)
        if step[0]=='table': self._put(step[1]); self.changed(); return
        r,c,old,new=step; self.df.iat[r,c]=old
        idx=self.index(r,c); self.dataChanged.emit(idx,idx); self.changed()
    def redo_edit(self):
        if not self.redo: return
        step=self.redo.pop(); self.undo.append(step)
        if step[0]=='table': self._put(step[2]); self.changed(); return
        r,c,old,new=step; self.df.iat[r,c]=new
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
        self.merge.setToolTip('How the ticked files are put into one dataset. Side by side: ONE Excel workbook with a sheet for every file (its X, its Y columns, DTG and peak names) and a last sheet with all files next to each other, every column labelled with its file - nothing is interpolated; graphs are drawn from it file by file. '
                              'Append rows: the rows of all files under each other (the same columns in every file). Join columns: one X column for all (identical X values in the same order)')
        lv.addWidget(self.merge); b=QPushButton('Merge selected files…'); b.clicked.connect(self.merge_files); lv.addWidget(b)
        b.setToolTip('Make one table of the ticked files and add it as a dataset of its own: it is listed here and in Your graphs, and can be drawn and exported. The files themselves stay as they are')
        note=QLabel('Delete (or a right click) takes a file off this list - and out of Workspace. File order determines graph and export order. Each file keeps its own data and mapping. Files that belong together (the same kind of data, names built the same way) '
                    'also get a table of all of them side by side, made by the app: it is the last entry of the list.',objectName='soft')
        note.setWordWrap(True); lv.addWidget(note); split.addWidget(left)
        center=QFrame(objectName='card'); cv=QVBoxLayout(center); cv.setContentsMargins(16,16,16,16)
        self.caption=QLabel('Select a file',objectName='sectionTitle'); cv.addWidget(self.caption)
        row=QHBoxLayout(); self.sheet=QComboBox(); self.sheet.currentTextChanged.connect(self.open_sheet)
        row.addWidget(QLabel('Sheet')); row.addWidget(self.sheet,1)
        for name,fn in [('Undo edit',self.undo_edit),('Redo edit',self.redo_edit),('Export data…',self.export_data)]:
            b=QPushButton(name); b.clicked.connect(fn); row.addWidget(b)
        cv.addLayout(row)
        self.b_peaks=QPushButton('Peaks…'); self.b_peaks.setVisible(False); self.b_peaks.clicked.connect(self.show_peaks); row.insertWidget(2,self.b_peaks)
        self.b_peaks.setToolTip('The peaks the app found in this file and what each may be (steps of mass loss of a thermal run, bands of an infrared spectrum), with a Label column of your own. Press again for the data')
        self.table=QTableView(); self.table.setAlternatingRowColors(True); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(160); cv.addWidget(self.table,1)
        # delete and hide, where you work: the Delete key and a right click on cells, rows, column headers, files and columns
        from PySide6.QtGui import QShortcut, QKeySequence
        self.table.setContextMenuPolicy(Qt.CustomContextMenu); self.table.customContextMenuRequested.connect(lambda p: self.table_menu(self.table.viewport().mapToGlobal(p), self.table.indexAt(p).column()))
        hh=self.table.horizontalHeader(); hh.setContextMenuPolicy(Qt.CustomContextMenu); hh.customContextMenuRequested.connect(lambda p: self.table_menu(hh.mapToGlobal(p), hh.logicalIndexAt(p), header=True))
        vh=self.table.verticalHeader(); vh.setContextMenuPolicy(Qt.CustomContextMenu); vh.customContextMenuRequested.connect(lambda p: self.table_menu(vh.mapToGlobal(p), -1))
        self.table.setToolTip('Right click a column header: use it as X or as Y, move it left or right, hide or delete it. Delete empties the selected cells; with whole rows or whole columns selected (click their headers) it deletes them. Right click for the same and for hiding a column. '
                              'Only the working copy changes - the file on the disk never does. Undo edit takes it back')
        for widget,fn in ((self.table,self.delete_in_table),(self.files,self.remove_files)):
            sc=QShortcut(QKeySequence(Qt.Key_Delete),widget,activated=fn); sc.setContext(Qt.WidgetWithChildrenShortcut)
        for seq,fn in ((QKeySequence.Copy,self.copy_cells),(QKeySequence.Paste,self.paste_cells),(QKeySequence.Cut,self.cut_cells),(QKeySequence('Ctrl+D'),self.fill_down)):
            sc=QShortcut(QKeySequence(seq),self.table,activated=fn); sc.setContext(Qt.WidgetWithChildrenShortcut)
        self.table.horizontalHeader().sectionDoubleClicked.connect(self.rename_column)
        from PySide6.QtWidgets import QToolButton, QMenu
        tb=QToolButton(); tb.setText('Table \u25be'); tb.setPopupMode(QToolButton.InstantPopup); tb.setToolTip('The tools of a spreadsheet for the table on show: copy, cut, paste (also from Excel), insert rows and columns, rename, sort, fill down, a calculated column. Each is one step of Undo edit; the file on the disk is never changed')
        tm=QMenu(tb); self.table_tools=tm
        for text,fn,tip in (('Copy  (Ctrl+C)',self.copy_cells,'The selected cells to the clipboard, ready for Excel'),('Cut  (Ctrl+X)',self.cut_cells,'Copy the selected cells and empty them'),
                            ('Paste  (Ctrl+V)',self.paste_cells,'Cells copied in Excel (or here) into the table, from the selected cell; rows and columns are added when the block is larger'),(None,None,None),
                            ('Insert a row above',lambda: self.insert_row(False),'An empty row above the selected one'),('Insert a row below',lambda: self.insert_row(True),'An empty row below the selected one'),
                            ('Insert a column\u2026',self.insert_column,'An empty column left of the selected one'),('Rename this column\u2026',lambda: self.rename_column(),'Also: double click the column header'),(None,None,None),
                            ('Sort by this column, smallest first',lambda: self.sort_column(True),'All rows are reordered'),('Sort by this column, largest first',lambda: self.sort_column(False),'All rows are reordered'),
                            ('Fill down  (Ctrl+D)',self.fill_down,'The top selected cell of each column into the selected cells below it'),
                            ('Add a calculated column\u2026',self.add_calculated,'A new column from a formula with the letters of the columns, as in Excel:  C/C.max()*100'),(None,None,None),
                            ('Add a sheet\u2026',self.add_sheet,'A new, empty sheet in the working copy of this file: type or paste data into it'),
                            ('Duplicate this sheet\u2026',lambda: self.add_sheet(copy=True),'A copy of the sheet on show under a new name: change it and keep the original'),
                            ('Remove this sheet',self.remove_sheet,'Take the sheet on show out of the working copy (its graphs leave Workspace). The file on the disk keeps it'),(None,None,None),
                            ('Remember the last merge as a workflow\u2026',self.save_workflow,'After a merge: remember HOW the files were put together (append, join on X, side by side) for this kind of data. No values are kept'),(None,None,None),
                            ('Delete the selected rows',lambda: self.delete_rows(),''),('Delete the selected columns',lambda: self.delete_columns(),''),('Empty the selected cells  (Delete)',self.delete_in_table,'')):
            if text is None: tm.addSeparator(); continue
            a=tm.addAction(text,fn); a.setToolTip(tip)
        tm.setToolTipsVisible(True); tb.setMenu(tm); row.insertWidget(2,tb); self.b_table=tb
        self.files.setContextMenuPolicy(Qt.CustomContextMenu); self.files.customContextMenuRequested.connect(self.files_menu)
        self.files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        srow=QHBoxLayout(); self.suggest=QLabel('',objectName='soft'); self.suggest.setWordWrap(True); srow.addWidget(self.suggest,1)
        self.b_suggest=QPushButton('Create this graph \u2192'); self.b_suggest.setObjectName('primary'); self.b_suggest.setVisible(False); self.b_suggest.clicked.connect(self.create_suggested); srow.addWidget(self.b_suggest)
        self.b_suggest.setToolTip('Draw the suggested graph from the columns as they are chosen here (X, Y, the columns left out). It opens in Workspace')
        b=QPushButton('Other graphs\u2026'); b.clicked.connect(self.choose_graph); b.setToolTip('All graphs that fit this data, on Start here'); srow.addWidget(b); self.b_other=b
        cv.addLayout(srow); self._suggested=None
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
        from PySide6.QtGui import QShortcut as _QS, QKeySequence as _QK
        sc=_QS(_QK(Qt.Key_Delete),self.columns,activated=lambda: self.hide_columns(False)); sc.setContext(Qt.WidgetWithChildrenShortcut)      # Delete on a column of this list: left out of the graphs
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
        # personal learning, as on Start here: 'Remember this import mapping' after YOU corrected the type or the columns
        self.learn_bar=None
        try:
            import workspace_learning as WL
            self.learn_bar=WL.MappingBar(self.ws,lambda: self.path,self.refresh_columns); rv.addWidget(self.learn_bar)
        except Exception: self.learn_bar=None
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

    # ------------------------------------------------------------ delete, hide, remove
    def _sel(self):
        """(cells, whole rows, whole columns) selected in the table."""
        sm=self.table.selectionModel()
        if sm is None or self.model is None: return [],[],[]
        return [(i.row(),i.column()) for i in sm.selectedIndexes()],[i.row() for i in sm.selectedRows()],[i.column() for i in sm.selectedColumns()]

    def _locked(self):
        if self.model is None: return True
        if self.model.read_only: self.ws.set_status('This table is made by the app from the files of the series: change the files themselves (or leave columns out there).'); return True
        if self.model.only is not None: self.ws.set_status("In the table of peaks only the Label column is yours: clear a Label to leave a peak unnamed."); return True
        return False

    def delete_in_table(self):
        """The Delete key: whole columns selected -> they are deleted from the working copy; whole rows -> deleted; else the
        selected cells are emptied. One Undo edit takes it back; the file on the disk is never changed."""
        cells,rows,cols=self._sel()
        if self.model is not None and self.model.only is not None:               # the table of peaks: a Label is cleared
            lab=list(self.model.df.columns).index('Label'); n=0
            for r in sorted({r for r,c in cells if c==lab}): n+=bool(self.model.setData(self.model.index(r,lab),'',Qt.EditRole))
            self.ws.set_status(f'{n} label(s) cleared.' if n else "Select cells of the Label column to clear them."); return n
        if self._locked(): return 0
        if cols: return self.delete_columns(cols)
        if rows: return self.delete_rows(rows)
        n=self.model.clear_cells(cells)
        self.ws.set_status(f'{n} cell(s) emptied in the working copy. Undo edit takes it back.' if n else 'Select cells first (click, drag, or Ctrl / Shift-click).'); return n

    def delete_rows(self,rows=None):
        if self._locked(): return 0
        rows=rows if rows is not None else sorted({r for r,_c in self._sel()[0]})
        n=self.model.delete_rows(rows)
        if n: self.info.setText(f'{len(self.model.df):,} rows \u00b7 {len(self.model.df.columns)} columns \u00b7 Working copy; source file unchanged')
        self.ws.set_status(f'{n} row(s) deleted from the working copy (the file is unchanged). Undo edit takes it back.' if n else 'Select the rows to delete first.'); return n

    def delete_columns(self,cols=None):
        if self._locked(): return 0
        cols=cols if cols is not None else sorted({c for _r,c in self._sel()[0]})
        names=self.model.delete_columns(cols)
        if names:
            self.info.setText(f'{len(self.model.df):,} rows \u00b7 {len(self.model.df.columns)} columns \u00b7 Working copy; source file unchanged'); self.refresh_columns()
        self.ws.set_status((f"Deleted from the working copy: {', '.join(names)} (the file is unchanged). Undo edit takes it back." if names else 'Select a column to delete first (a table keeps at least one column).')); return len(names)

    def hide_columns(self,use,names=None):
        """Leave columns out of the graphs (use=False) or use them again: the ticks of the Columns list. The data stays in the table."""
        if not self.path: return 0
        if names is None: names=[(i.data(Qt.UserRole) or i.text()) for i in self.columns.selectedItems()]
        n=0; self._loading=True
        for i in range(self.columns.count()):
            it=self.columns.item(i)
            if (it.data(Qt.UserRole) or it.text()) in names and (it.checkState()==Qt.Checked)!=bool(use): it.setCheckState(Qt.Checked if use else Qt.Unchecked); n+=1
        self._loading=False
        if n: self.columns_changed()
        self.ws.set_status((f"{'Used again' if use else 'Left out of the graphs'}: {', '.join(names)}." + ('' if use else ' It stays in the table and its export; it is not carried to Workspace.')) if n else 'Select a column in the list first.'); return n

    # ------------------------------------------------------------ the tools of a spreadsheet
    def _cur(self):
        i=self.table.currentIndex(); cells=self._sel()[0]
        if cells: return min(r for r,_c in cells),min(c for _r,c in cells)
        return (i.row(),i.column()) if i.isValid() else (0,0)

    def copy_cells(self):
        cells=self._sel()[0]
        if not cells or self.model is None: return ''
        rows=sorted({r for r,_c in cells}); cols=sorted({c for _r,c in cells}); have=set(cells)
        text='\n'.join('\t'.join(('' if (r,c) not in have or pd.isna(self.model.df.iat[r,c]) else str(self.model.df.iat[r,c])) for c in cols) for r in rows)
        QApplication.clipboard().setText(text); self.ws.set_status(f'{len(rows)} x {len(cols)} cell(s) copied: paste them here or in Excel.'); return text

    def cut_cells(self):
        text=self.copy_cells()
        if text and not self._locked(): self.model.clear_cells(self._sel()[0])
        return text

    def paste_cells(self,text=None):
        if self._locked(): return (0,0)
        text=QApplication.clipboard().text() if text is None else text
        rows=[ln.split('\t') for ln in str(text).replace('\r\n','\n').replace('\r','\n').split('\n')]
        while rows and rows[-1]==['']: rows.pop()
        if not rows: self.ws.set_status('There is nothing to paste: copy cells in Excel or here first.'); return (0,0)
        r,c=self._cur(); done=self.model.paste(r,c,rows); self._after_table_change()
        self.ws.set_status(f'{done[0]} row(s) x {done[1]} column(s) pasted from row {r+1}. Undo edit takes it back.'); return done

    def _after_table_change(self):
        if self.model is not None: self.info.setText(f'{len(self.model.df):,} rows \u00b7 {len(self.model.df.columns)} columns \u00b7 Working copy; source file unchanged')
        self.refresh_columns()

    def insert_row(self,below=False):
        if self._locked(): return 0
        r,_c=self._cur(); n=self.model.insert_rows(r+(1 if below else 0)); self._after_table_change(); self.ws.set_status('An empty row is added. Undo edit takes it back.'); return n

    def insert_column(self,name=None):
        if self._locked(): return False
        if name is None:
            name,ok=QInputDialog.getText(self,'Insert a column','Name of the new column:',text='New column')
            if not ok: return False
        _r,c=self._cur(); ok=self.model.insert_column(c,name); self._after_table_change()
        self.ws.set_status(f"Column '{name}' added." if ok else 'The column was not added: give it a name that is not used yet.'); return ok

    def rename_column(self,col=None,name=None):
        if self._locked(): return False
        col=self._cur()[1] if col is None or col is False else int(col)
        if not 0<=col<len(self.model.df.columns): return False
        old=str(self.model.df.columns[col])
        if name is None:
            name,ok=QInputDialog.getText(self,'Rename the column','New name:',text=old)
            if not ok: return False
        ok=self.model.rename_column(col,name)
        if ok and self.path:                                           # the choices made for the column follow its new name
            prefs=self.controller.mapping_for(self.path)
            for key in ('order','off','derived','derived_on'):
                if key in prefs: prefs[key]=[str(name).strip() if c==old else c for c in prefs[key]]
        self._after_table_change(); self.ws.set_status(f"'{old}' is now '{str(name).strip()}'." if ok else 'The column keeps its name (the new one is empty or already used).'); return ok

    def sort_column(self,ascending=True):
        if self._locked(): return False
        ok=self.model.sort_by(self._cur()[1],ascending); self._after_table_change()
        self.ws.set_status(('All rows sorted by the selected column. Undo edit takes it back.') if ok else 'Select a cell of the column to sort by first.'); return ok

    def fill_down(self):
        if self._locked(): return 0
        n=self.model.fill_down(self._sel()[0]); self.ws.set_status(f'{n} cell(s) filled with the value above them.' if n else 'Select two or more cells of a column: the top one is copied into those below.'); return n

    def add_calculated(self,name=None,formula=None):
        if self._locked(): return 'locked'
        if name is None or formula is None:
            hint=', '.join(f'{l} = {c}' for l,c in zip(self.model.letters(),self.model.df.columns))[:400]
            formula,ok=QInputDialog.getText(self,'Add a calculated column',f'Formula with the letters of the columns, as in Excel.\n{hint}\n\nFor example  C/C.max()*100   or   (B-A)/2   or   log10(C)\nFormula:')
            if not ok: return 'cancelled'
            name,ok=QInputDialog.getText(self,'Add a calculated column','Name of the new column:',text='Calculated')
            if not ok: return 'cancelled'
        err=self.model.add_calculated(name,formula); self._after_table_change()
        self.ws.set_status(f"Column '{name}' = {formula} added as the last column." if not err else f'No column was added: {err}.'); return err

    # ------------------------------------------------------------ sheets
    def sheet_names(self):
        import related
        return [self.sheet.itemText(i) for i in range(self.sheet.count()) if self.sheet.itemText(i)!=related.PEAKS_SHEET]

    def add_sheet(self,name=None,copy=False):
        """A new sheet in the working copy of the file on show: empty (two columns to start with), or a copy of the
        sheet on show. Kept with the project like any edit; the file on the disk is not changed."""
        import related
        if not self.path or self.model is None or self.sheet.currentText()==related.PEAKS_SHEET or self.model.read_only:
            self.ws.set_status('Open the data of a file first (not a table made by the app).'); return None
        slug=self.controller.project_for(self.path); sheets=self.controller.raw_sheets(self.path,slug); cur=self.sheet.currentText()
        if name is None:
            base=((cur or 'Data')+' copy') if copy else 'Sheet'; k=2; start=base
            while start in sheets: start=f'{base} {k}'; k+=1
            name,ok=QInputDialog.getText(self,'Duplicate this sheet' if copy else 'Add a sheet','Name of the new sheet:',text=start)
            if not ok: return None
        name=str(name).strip()
        if not name or name in sheets or name==related.PEAKS_SHEET: self.ws.set_status('The sheet was not added: give it a name that is not used yet.'); return None
        sheets[name]=sheets[cur].copy() if copy and cur in sheets else pd.DataFrame({'X':[np.nan]*20,'Y':[np.nan]*20})
        prefs=self.controller.settings_for(self.path,slug); prefs['removed_sheets']=[n for n in prefs.get('removed_sheets',[]) if n!=name]
        self.edited(self.path,slug,name)                              # written down with the file's settings
        self._loading=True; self.sheet.insertItem(len(self.sheet_names()),name); self._loading=False; self.sheet.setCurrentText(name)
        self.ws.set_status(f"Sheet '{name}' added to the working copy" + (' as a copy of ' + (cur or 'the data') if copy else ': type or paste your data (Table \u25be \u203a Paste), rename its columns with a double click on the header') + '.'); return name

    def remove_sheet(self,name=None):
        """Take a sheet out of the working copy. Its graphs leave Workspace; the file on the disk keeps the sheet."""
        import related
        if not self.path or self.model is None: return False
        name=self.sheet.currentText() if name is None else name; names=self.sheet_names()
        if name==related.PEAKS_SHEET or name not in names: self.ws.set_status('Show the sheet to remove first.'); return False
        if len(names)<2: self.ws.set_status('This is the only sheet of the file: take the file off the list instead (Delete on the file).'); return False
        if not os.environ.get('OPS_NO_OPEN') and QMessageBox.question(self,'Remove this sheet',f"Remove the sheet '{name}' from the working copy?\nIts graphs leave Workspace. The file on the disk keeps the sheet.")!=QMessageBox.Yes: return False
        slug=self.controller.project_for(self.path); path=self.path; sheets=self.controller.raw_sheets(path,slug); sheets.pop(name,None)
        prefs=self.controller.settings_for(path,slug); prefs.setdefault('removed_sheets',[]); prefs['removed_sheets']=[n for n in prefs['removed_sheets'] if n!=name]+[name]
        prefs.get('edited_sheets',{}).pop(name,None); prefs.get('sheet_settings',{}).pop(name,None)
        if prefs.get('sheet')==name: prefs.pop('sheet',None)
        for k in [k for k in self.models if k[1]==path and k[2]==name]: self.models.pop(k,None)
        for k in [k for k in self.controller._peak_frames if k[1]==path]: self.controller._peak_frames.pop(k,None)
        n=self.controller._drop_graphs([g for g in self.ws.singles if getattr(g,'path','')==path and getattr(g,'det',{}).get('_source_sheet')==name],f"sheet '{name}' removed")
        self.controller.changed(path,slug); self.ws.templates_page._sheet_pick_cache.clear(); self.open_file(self.files.currentRow())
        self.ws.set_status(f"Sheet '{name}' removed from the working copy" + (f'; {n} graph(s) left Workspace' if n else '') + '. The file on the disk still has it.'); return True

    def table_menu(self,where,col=-1,header=False):
        from PySide6.QtWidgets import QMenu
        if self.model is None: return
        m=QMenu(self); cells,rows,cols=self._sel(); lock=self.model.locked(); name=str(self.model.df.columns[col]) if 0<=col<len(self.model.df.columns) else ''
        if not header:
            a=m.addAction(f'Empty the {len(cells)} selected cell(s)  (Delete)' if len(cells)!=1 else 'Empty this cell  (Delete)',lambda: self.model.clear_cells(cells) and self.ws.set_status(f'{len(cells)} cell(s) emptied. Undo edit takes it back.')); a.setEnabled(bool(cells) and not lock)
            rr=sorted({r for r,_c in cells})
            a=m.addAction(f'Delete the {len(rr)} selected row(s)' if len(rr)!=1 else f'Delete row {rr[0]+1}' if rr else 'Delete the selected rows',lambda: self.delete_rows(rr)); a.setEnabled(bool(rr) and not lock)
        if name:
            if not header: m.addSeparator()
            if self.path and not lock:
                m.addAction(f"Use '{name}' as X",lambda: self.set_role(name,'X')); m.addAction(f"Use '{name}' as Y",lambda: self.set_role(name,'Y'))
                a=m.addAction('Move column left',lambda: self.move_column(col,-1)); a.setEnabled(col>0)
                a=m.addAction('Move column right',lambda: self.move_column(col,1)); a.setEnabled(col<len(self.model.df.columns)-1)
                m.addSeparator()
            a=m.addAction(f"Delete column '{name}' from the working copy",lambda: self.delete_columns([col])); a.setEnabled(not lock)
            if self.path and not lock:
                off=name in (self.controller.mapping_for(self.path).get('off') or [])
                m.addAction(f"Use '{name}' in the graphs again" if off else f"Hide '{name}': leave it out of the graphs",lambda: self.hide_columns(off,[name]))
                m.addAction(f"Leave '{name}' out in all files",lambda: self.ws.set_status(f"'{name}' is left out in {self.set_column_everywhere(name,False)} file(s)."))
        if not lock:
            m.addSeparator(); m.addAction('Copy  (Ctrl+C)',self.copy_cells); m.addAction('Cut  (Ctrl+X)',self.cut_cells); m.addAction('Paste  (Ctrl+V)',self.paste_cells)
            if not header: m.addAction('Insert a row above',lambda: self.insert_row(False)); m.addAction('Insert a row below',lambda: self.insert_row(True)); m.addAction('Fill down  (Ctrl+D)',self.fill_down)
            if name:
                m.addAction(f"Rename '{name}'\u2026",lambda: self.rename_column(col)); m.addAction('Insert a column here\u2026',self.insert_column)
                m.addAction(f"Sort by '{name}', smallest first",lambda: (self.table.setCurrentIndex(self.model.index(max(0,self._cur()[0]),col)),self.sort_column(True)))
                m.addAction(f"Sort by '{name}', largest first",lambda: (self.table.setCurrentIndex(self.model.index(max(0,self._cur()[0]),col)),self.sort_column(False)))
            m.addAction('Add a calculated column\u2026',self.add_calculated)
        m.addSeparator(); m.addAction('Undo edit',self.undo_edit); m.addAction('Redo edit',self.redo_edit)
        m.exec(where)

    # ------------------------------------------------------------ X, Y and the graph that follows from them
    def set_role(self,name,role):
        """Make a column the X or the (first) Y of the file on show. The other one keeps its place; taking its column swaps them."""
        if not self.path or self._locked(): return False
        table=self.controller.table_of(self.path)[0]; x=table.x; y=table.ys[0] if table.ys else ''
        if name not in table.numeric: self.ws.set_status(f"'{name}' holds no numbers: it cannot be X or Y. (Left out or hidden columns are ticked again under Columns.)"); return False
        if role=='X': x,y=name,(x if y==name else y)
        else: y,x=name,(y if x==name else x)
        if not x or not y or x==y: self.ws.set_status('X and Y must be two different columns.'); return False
        self.controller.set_mapping(self.path,x,y,self.sheet.currentIndex(),self.type.currentText()); self.refresh_columns()
        self.ws.set_status(f"X = {x}, Y = {y}. The graphs of this file follow; the suggestion under the table too."); return True

    def move_column(self,col,delta):
        if self._locked() or self.model is None: return False
        ok=self.model.move_column(col,delta)
        if ok: self.refresh_columns(); self.ws.set_status('Column moved in the working copy. Undo edit takes it back.')
        return ok

    def update_suggestion(self):
        """The graph the app would draw from the file on show as its columns are chosen now - for a file of a series,
        the graph of the whole series - with the reason. 'Create this graph' draws it."""
        self._suggested=None
        try:
            if not self.path or self.model is None or self.model.locked(): raise LookupError
            group=next((ps for _l,ps,_w in self.series_groups() if self.path in ps),None)
            rows=self.controller.recommendations(group,together=True,series=True) if group else self.controller.recommendations([self.path])
            row=next((r for r in rows if r.get('compatible')),None)
            if row is None: raise LookupError
            self._suggested=(row['id'],list(group) if group else [self.path],bool(group))
            self.suggest.setText(f"Suggested graph: {row['name']}" + (f" - the {len(group)} files of the series together" if group else '') + f". {row.get('reason','')}")
            self.b_suggest.setVisible(True)
        except Exception:
            self.suggest.setText('' if (self.model is None or self.model.locked()) else 'No graph is suggested yet: choose X and Y (right click a column header), or set the measurement type on the right.')
            self.b_suggest.setVisible(False)

    def create_suggested(self):
        if not self._suggested: return None
        tid,paths,together=self._suggested
        return self.controller.create_graphs(paths,tid,together)

    def remove_files(self,paths=None):
        """Take files off this list. A file that is not selected is nowhere in the app: it is unticked on Start here, and
        its graphs leave Workspace (Undo there brings them back). The file on the disk is not touched."""
        if paths is None: paths=[i.data(Qt.UserRole) for i in self.files.selectedItems() if isinstance(i.data(Qt.UserRole),str)]
        if not paths: self.ws.set_status('Select one or more files of the list first (the tables made by the app go when their files go).'); return 0
        left=[p for p in self.paths if p not in paths]
        n=self.controller.deselect_inputs(paths); self.set_paths(left)
        self.ws.set_status(f"{len(paths)} file(s) taken off the list: unticked on Start here, {n} graph(s) left Workspace. The files on the disk are not touched."); return len(paths)

    def files_menu(self,pos):
        from PySide6.QtWidgets import QMenu
        it=self.files.itemAt(pos)
        if it is None or not isinstance(it.data(Qt.UserRole),str): return
        if not it.isSelected(): self.files.setCurrentItem(it)
        sel=[i.data(Qt.UserRole) for i in self.files.selectedItems() if isinstance(i.data(Qt.UserRole),str)]
        m=QMenu(self); m.addAction(f'Remove the {len(sel)} selected files from the list  (Delete)' if len(sel)>1 else 'Remove this file from the list  (Delete)',lambda: self.remove_files(sel))
        m.addAction('Move up',lambda: self.move_file(-1)); m.addAction('Move down',lambda: self.move_file(1))
        m.exec(self.files.mapToGlobal(pos))

    def show_peaks(self):
        """The Peaks button: the table of peaks of the file on show, and back to its data."""
        import related
        if self.sheet.currentText()==related.PEAKS_SHEET: self.sheet.setCurrentIndex(0)
        elif self.sheet.findText(related.PEAKS_SHEET)>=0: self.sheet.setCurrentText(related.PEAKS_SHEET)

    def worked_columns(self,path,table,sheet=None,peaks=True,n_rows=None):
        """[(name, values)] the app works out for a file: the DTG curve of a thermal run and - peaks=True - three columns
        that list its peaks from the first row down (where, label, what it may be). peaks=False for a merge: there the
        sheets of the files hold data only and the peaks of all files stand on a sheet of their own."""
        import related
        out=[]
        try:
            d=related.dtg_column(table)
            if d: out.append((d[0],d[1]))
        except Exception: pass
        if peaks:
            try:
                frame,kind=self.controller.peak_frame(path,sheet=sheet)
                if frame is not None and kind in ('TGA','FTIR'): out+=related.peak_columns(kind,n_rows if n_rows is not None else len(table.df),frame)
            except Exception: pass
        return out

    def refresh_peak_column(self,path):
        """Your labels changed: the peak column of the data shows them."""
        import related
        try:
            slug=self.controller.project_for(path); table,sel=self.controller._table(path,slug)[:2]; frame=self.controller.raw_sheets(path,slug)[sel]
            peaks,kind=self.controller.peak_frame(path); changed=False
            for name,values in (related.peak_columns(kind,len(frame),peaks) if peaks is not None and kind in ('TGA','FTIR') else []):
                if name in frame.columns and len(values)==len(frame): frame[name]=values; changed=True
            m=self.models.get((slug,path,sel))
            if changed and m is not None: m.layoutChanged.emit()
        except Exception: pass

    def open_series(self,data):
        import related
        _kind,ps,label=data; self.path=None
        try:
            frame=related.side_by_side([(p,self.controller.table_for(p)) for p in ps],extra=lambda p,t: self.worked_columns(p,t,peaks=False))
            self.model=WorkingTableModel(frame,lambda:None,self); self.model.read_only=True; self.table.setModel(self.model); self._series_label=label
            self._loading=True; self.sheet.clear(); self.columns.clear(); self.x.clear(); self.y.clear(); self._loading=False; self.b_peaks.setVisible(False); self.draw_labels.setVisible(False); self.update_suggestion()
            self.caption.setText(f"All of '{label}' side by side")
            self.info.setText(f'{len(frame):,} rows \u00b7 {len(frame.columns)} columns \u00b7 made by the app from {len(ps)} files; every file keeps its own X values, nothing is interpolated. Export data\u2026 saves it')
        except Exception as e: self.info.setText('The files could not be put side by side: '+str(e))

    def open_file(self,index):
        if self._loading or not 0<=index<self.files.count(): return
        data=self.files.item(index).data(Qt.UserRole)
        if not isinstance(data,str): return self.open_series(data)
        self.path=data
        try:                                       # opening a file is not a correction: only the baseline a later change of yours is compared with
            import workspace_learning as WL
            WL.controller(self.ws).baseline(self.path)
        except Exception: pass
        try:
            table,selected,names,_cols,_prefs=self.controller.table_of(self.path)
            self._loading=True; self.sheet.clear(); self.sheet.addItems(names)
            import related
            try:
                if self.controller.peak_frame(self.path)[0] is not None:
                    self.sheet.addItem(related.PEAKS_SHEET); self.sheet.setItemData(self.sheet.count()-1,'The peaks the app found in this file (steps of mass loss of a thermal run, bands of an infrared spectrum), what each may be, and a Label column of your own',Qt.ToolTipRole)
            except Exception: pass
            # a workbook the app merged opens on 'All side by side' - the merged result - until you choose another of its sheets
            views=self.__dict__.setdefault('_views',{})
            if self.sheet.findText(related.OVERVIEW_SHEET)>=0 and views.get(self.path,related.OVERVIEW_SHEET)==related.OVERVIEW_SHEET: selected=related.OVERVIEW_SHEET
            elif views.get(self.path)==related.PEAKS_OVERVIEW and self.sheet.findText(related.PEAKS_OVERVIEW)>=0: selected=related.PEAKS_OVERVIEW
            self.sheet.setCurrentText(selected); self._loading=False
            has=self.sheet.findText(related.PEAKS_SHEET)>=0; self.b_peaks.setVisible(has)
            if has:
                try: self.b_peaks.setText(f"Peaks ({len(self.controller.peak_frame(self.path)[0])})\u2026")
                except Exception: self.b_peaks.setText('Peaks\u2026')
            self.open_sheet(selected)
        except Exception as e: self.info.setText('Could not open file: '+str(e)); self._loading=False

    def open_peaks(self):
        """The peak table of the file on show: read it, type your labels, switch them on for the graph."""
        import related
        frame,kind=self.controller.peak_frame(self.path)
        if frame is None: return
        path=self.path; key=(self.controller.project_for(path),path,related.PEAKS_SHEET)
        if kind=='XRD':                                              # the peak table of the pattern's graph: read here, changed with the graph (labels, phases)
            self.model=WorkingTableModel(frame,lambda:None,self); self.model.read_only=True; self.table.setModel(self.model); self.table.resizeColumnsToContents()
            self.caption.setText(os.path.basename(path)+' / peaks')
            self.info.setText(f"{len(frame)} peaks of the pattern as its graph in Workspace found and named them (positions, d-spacings, phases of your library). "
                              "Read and export them here; labels and phases are changed with the graph (Workspace: right click the graph, Peak labels). Export data\u2026 saves this table.")
            self._loading=True; self.draw_labels.setVisible(False); self.columns.clear(); self._loading=False; self.update_suggestion(); return
        if key not in self.models or self.models[key].df is not frame:
            self.models[key]=WorkingTableModel(frame,lambda p=path:(self.controller.set_peak_labels(p),self.refresh_peak_column(p)),self); self.models[key].only=('Label',)
        self.model=self.models[key]; self.table.setModel(self.model); self.table.resizeColumnsToContents()
        self.caption.setText(os.path.basename(path)+' / peaks')
        what='steps of mass loss (minima of the DTG curve)' if kind=='TGA' else 'bands'
        self.info.setText(f"{len(frame)} {what} found by the app. 'May be' is the usual event or bond at that position, the most likely first - a possibility to check, not a finding. "
                          "The Label column is yours to type in. Export data\u2026 saves this table.")
        slug=self.controller.project_for(path); sel=self.controller._table(path,slug)[1]
        on=bool(self.controller.settings_for(path,slug).get('sheet_settings',{}).get(sel,{}).get('peak_names_on'))
        self._loading=True; self.draw_labels.setChecked(on); self.draw_labels.setVisible(True); self.columns.clear(); self._loading=False; self.update_suggestion()

    def labels_toggled(self,on):
        if self._loading or not self.path: return
        self.controller.set_peak_labels(self.path,on=bool(on))
        self.ws.set_status(('The labels of this table are drawn on the TGA / FTIR graphs of this file in Workspace.' if on else 'The graphs of this file show the positions only again.'))

    def open_sheet(self,name):
        if self._loading or self.path is None: return
        import related
        self.draw_labels.setVisible(False)
        if name and name!=related.PEAKS_SHEET: self.__dict__.setdefault('_views',{})[self.path]=name
        if name==related.PEAKS_SHEET: return self.open_peaks()
        slug=self.controller.project_for(self.path)
        if name in (related.OVERVIEW_SHEET,related.PEAKS_OVERVIEW):
            # the two sheets of a merged workbook that show ALL its files: looked at and exported here; the graphs keep
            # being drawn from the sheets of the single files (a view, not the sheet chosen for the graphs)
            try:
                frame=self.controller.raw_sheets(self.path,slug)[name]
                self.model=WorkingTableModel(frame,lambda:None,self); self.model.read_only=True; self.table.setModel(self.model); self.fit_headers()
                self.caption.setText(os.path.basename(self.path)+' / '+name)
                n_files=len([s for s in self.controller.raw_sheets(self.path,slug) if s not in (related.OVERVIEW_SHEET,related.PEAKS_OVERVIEW)])
                self.info.setText((f'MERGED: {n_files} files side by side \u00b7 {len(frame):,} rows \u00b7 {len(frame.columns)} columns. Every file has its own X and Y columns, named after the file; nothing is interpolated. '
                                   if name==related.OVERVIEW_SHEET else f'The peaks of all {n_files} files in one table \u00b7 {len(frame):,} rows. ')
                                  +'To look at only: the sheet of each file is in the Sheet box above, and those are what the graphs are drawn from. Export data\u2026 saves this table.')
                self._loading=True; self.columns.clear(); self.x.clear(); self.y.clear(); self._loading=False; self.update_suggestion()
            except Exception as e: self.info.setText('Could not open sheet: '+str(e))
            return
        try:
            frame=self.controller.raw_sheets(self.path,slug)[name]; prefs=self.controller.settings_for(self.path,slug); prefs['sheet']=name
            self.add_worked_columns(frame,slug,name)
            key=(slug,self.path,name)
            if key not in self.models or self.models[key].df is not frame:
                self.models[key]=WorkingTableModel(frame,lambda p=self.path,s=slug,n=name:self.edited(p,s,n),self)
            self.model=self.models[key]; self.table.setModel(self.model); self.fit_headers()
            self.caption.setText(os.path.basename(self.path)+' / '+(name or 'Data'))
            self.info.setText(f'{len(frame):,} rows · {len(frame.columns)} columns · Working copy; source file unchanged')
            self.refresh_columns()
        except Exception as e: self.info.setText('Could not open sheet: '+str(e))

    def fit_headers(self):
        """Every column as wide as its header and its numbers need (a header was cut off: 'Navenumber'), within limits."""
        try:
            hh=self.table.horizontalHeader(); fm=hh.fontMetrics()
            for c in range(self.model.columnCount() if self.model is not None else 0):
                w_=fm.horizontalAdvance(str(self.model.headerData(c,Qt.Horizontal)))+34; self.table.setColumnWidth(c,max(110,min(320,max(w_,150))))
        except Exception: pass

    def add_worked_columns(self,frame,slug,name):
        """The DTG curve of a thermal run as a column of the working copy (once): there to be seen and exported. It is
        left out of the graphs - they work out their own - unless you tick it under Columns."""
        import related
        try:
            scoped=self.controller.settings_for(self.path,slug).setdefault('sheet_settings',{}).setdefault(name,{}); derived=scoped.setdefault('derived',[])
            old=[c for c in ('Peak (may be)','Band (may be)','What it may be') if c in frame.columns and not any(p in frame.columns for p in related.PEAK_POSITION.values())]
            table=self.controller._table(self.path,slug,name)[0]
            for col,values in self.worked_columns(self.path,table,name,n_rows=len(frame)):
                if len(values)!=len(frame): continue
                if col in frame.columns and col not in related.WORKED_NAMES: continue      # a DTG column that is there already (the file's own, or made before) stays
                if col in frame.columns: frame[col]=values                                  # the app's own peak columns are written anew
                else: frame[col]=values
                if col not in derived: derived.append(col)
            for col in old:                                                                 # the peak columns of 5.58.1 / 5.58.2 (a name in the row of its peak) with no list to replace them: emptied, not data
                if col not in derived: derived.append(col)
            for col in related.WORKED_NAMES:                                                # in a file the app merged or exported: its peak columns are the app's, not data
                if col in frame.columns and col not in derived: derived.append(col)
            if not derived: scoped.pop('derived',None)
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
        if self.model is not None and not self.model.locked():      # the headers say which column is X and which is the first Y
            self.model.roles={table.x:'X',**({table.ys[0]:'Y'} if table.ys else {})} if table.x else {}
            self.model.headerDataChanged.emit(Qt.Horizontal,0,max(0,self.model.columnCount()-1)); self.fit_headers()
        QTimer.singleShot(0,self.update_suggestion)

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
        try:                                       # the same staging and confirmation as on Start here (one shared path)
            import workspace_learning as WL
            WL.controller(self.ws).user_changed(self.path)
        except Exception: pass

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
            result=None if mode==2 else merge_tables(inputs,mode)
            data_only=lambda p,t: self.worked_columns(p,t,peaks=False)
            def peaks_of(p):
                fr,kd=self.controller.peak_frame(p); return fr if kd in ('TGA','FTIR') else None
            name,ok=QInputDialog.getText(self,'Merged dataset','Dataset name:',text=(related.series_label(paths) if related.series(paths)['related'] else 'Merged data'))
            if not ok or not name.strip(): return None
            import workspace_projects as WP
            import workspace_qt as WQ
            slug=self.controller.active_project if self.controller.active_project and all(self.controller.project_for(p)==self.controller.active_project for p in paths) else None
            # files that are in no project are merged too: the table is kept with the app's own data, as a file of this session
            folder=WQ.cfg_path().parent/'project_data'/(slug or '_session')/'derived'; folder.mkdir(parents=True,exist_ok=True)
            import re,uuid
            base=re.sub(r'[^\w.-]+','_',name.strip()); path=folder/(base+'_'+uuid.uuid4().hex[:6]+('.xlsx' if mode==2 else '.csv'))
            if mode==2: related.merged_workbook(str(path),inputs,extra=data_only,peaks=peaks_of)      # one Excel workbook: a sheet per file, and all files side by side with labelled columns on the last sheet
            else: result.to_csv(path,index=False)
            if slug:
                WP.add_files(slug,[str(path)])
                self.ws.templates_page.add_files([str(path)],project=WP.get(slug)['name'],on_done=lambda items:[setattr(i,'project_id',slug) for i in items])
            else: self.ws.templates_page.add_files([str(path)])
            self.set_paths(self.paths+[str(path)]); self.files.setCurrentRow(self.paths.index(str(path)))
            self.controller.changed(str(path),slug)
            self._last_workflow=(paths[0],[{'op':'append_rows','params':{'match':'headers','require_same_units':True}}] if mode==0 else
                                 [{'op':'join_columns','params':{'on_role':'x','require_equal_x':True}}] if mode==1 else [{'op':'arrange_sheets','params':{'order_by':'source_order'}}])
            self.ws.set_status(f"'{name.strip()}' is a dataset of its own now" + (f": an Excel workbook with a sheet for each of the {len(paths)} files and all of them side by side on the last sheet '{related.OVERVIEW_SHEET}'" if mode==2 else '')
                               + f". It is the entry selected in this list, also in Your graphs and on Start here. The {len(paths)} files are unchanged. {path}")
            return str(path)
        except Exception as e: self.ws.set_status('Merge could not be completed: '+str(e)); return None

    def save_workflow(self):
        """'Remember this workflow': the merge that was just completed, as a step from the app's own list of operations
        (how the files were put together - never the values in them). Only when you ask for it."""
        last=getattr(self,'_last_workflow',None)
        if not last: self.ws.set_status('There is nothing to remember yet: merge the ticked files first, then save that as a workflow.'); return None
        try:
            import workspace_learning as WL
            result,text=WL.controller(self.ws).save_workflow(last[0],last[1])
        except Exception: result,text=None,'The workflow could not be remembered.'
        self.ws.set_status(text); return result

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
            from safe_export import safe_frame                                                           # text that would be read as a formula stays text; numbers are untouched
            if path.lower().endswith('.xlsx'):
                with pd.ExcelWriter(path) as xw:
                    safe_frame(self.model.df).to_excel(xw,index=False,sheet_name='Data')
                    if peaks is not None: safe_frame(peaks).to_excel(xw,index=False,sheet_name='Peaks')            # the peaks of the file and what they may be, beside its data
            else: safe_frame(self.model.df).to_csv(path,index=False,sep='\t' if path.lower().endswith('.tsv') else ',')
            self.ws.set_status('Working data exported: '+path+(' (sheets Data and Peaks)' if peaks is not None and path.lower().endswith('.xlsx') else '')); return path
        except Exception as e: self.ws.set_status('Export failed: '+str(e)); return None

    def choose_graph(self):
        self.controller.select_inputs(self.paths)
        sh=self.ws.pages.widget(6)
        if self.path: sh._current_path=self.path
        self.ws.go(6)

"""Independent graph and panel editor backed by the same figure sent to Origin."""
import copy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox,QComboBox,QDialog,QDoubleSpinBox,QFileDialog,QFormLayout,
 QFrame,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QScrollArea,QVBoxLayout,QWidget)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT


class GraphEditor(QDialog):
    def __init__(self,controller,graph,parent=None):
        super().__init__(parent or controller.ws); self.controller=controller; self.graph=graph
        self.setWindowTitle('Edit graph — '+graph.sample); self.resize(1220,800)
        self._loading=False; self._original=copy.deepcopy(graph.combo); self.history=[]; self.future=[]; self._applied_once=False; self.unsupported=[]
        outer=QHBoxLayout(self); left=QVBoxLayout(); outer.addLayout(left,3)
        left.addWidget(QLabel(graph.sample,objectName='sectionTitle'))
        self.canvas=FigureCanvasQTAgg(graph.fig); left.addWidget(NavigationToolbar2QT(self.canvas,self)); left.addWidget(self.canvas,1)
        side=QWidget(); right=QVBoxLayout(side); right.setSpacing(12)
        right.addWidget(QLabel('Graph components',objectName='sectionTitle'))
        note=QLabel('Changes affect this graph. Choose a panel to edit it independently.',objectName='soft'); note.setWordWrap(True); right.addWidget(note)
        self.target=QComboBox(); self.target.addItem('Whole graph','all')
        mains=[a for a in graph.fig.axes if not getattr(a,'_ops_auxiliary',False)]
        self.panels=sorted(set(getattr(a,'_ops_panel',i) for i,a in enumerate(mains)))
        if len(self.panels)>1:
            for index in self.panels: self.target.addItem(f'Panel {index+1}',str(index))
        self.target.currentIndexChanged.connect(self.load_options); right.addWidget(self.target)
        self.markers=QCheckBox('Show point markers on other curves'); self.observed_markers=QCheckBox('Show markers on measured data'); self.fitted_markers=QCheckBox('Show markers on fitted curves'); self.zoom=QCheckBox('Show zoom inset')
        self.difference=QCheckBox('Show difference / residual row'); self.bragg=QCheckBox('Show Bragg reflection rows')
        self.background=QCheckBox('Show background / baseline curve')
        self.peak_labels=QCheckBox('Show peak labels')
        for box in [self.observed_markers,self.fitted_markers,self.markers,self.zoom,self.difference,self.bragg,self.background,self.peak_labels]:
            box.toggled.connect(self.apply); right.addWidget(box)
        self.xmin=QLineEdit(); self.xmax=QLineEdit(); self.xmin.setPlaceholderText('From'); self.xmax.setPlaceholderText('To')
        row=QHBoxLayout(); row.addWidget(self.xmin); row.addWidget(self.xmax); right.addWidget(QLabel('Inset X range')); right.addLayout(row)
        self.xmin.editingFinished.connect(self.apply); self.xmax.editingFinished.connect(self.apply)
        self.title=QLineEdit(); self.xlabel=QLineEdit(); self.ylabel=QLineEdit(); form=QFormLayout()
        for label,field in [('Graph title',self.title),('X axis title',self.xlabel),('Y axis title',self.ylabel)]:
            form.addRow(label,field); field.editingFinished.connect(self.apply)
        right.addLayout(form)
        self.style=QComboBox()
        for sid,name,_ in controller.tp.api.styles(): self.style.addItem(name,sid)
        self.style.activated.connect(self.apply); right.addWidget(QLabel('Publication style')); right.addWidget(self.style)
        self.apply_all=QCheckBox('Apply component settings to all graphs in this project')
        self.apply_all.setToolTip('Explicit batch action: otherwise every change stays on this graph')
        right.addWidget(self.apply_all)
        # personal learning: the look of this graph (or of one panel) can be remembered - presentation only, and only when
        # you ask for it. Undo and Redo below restore the graph; they never save or count anything.
        row=QHBoxLayout(); self.save_style_btn=QPushButton('Save style…'); self.save_style_btn.setToolTip('Remember the component settings and the publication style - no titles, ranges or data. You choose what it is for.')
        self.save_style_btn.clicked.connect(lambda: self.save_style()); row.addWidget(self.save_style_btn)
        self.use_style_btn=QPushButton('Use saved style'); self.use_style_btn.setToolTip('Put a style you saved on THIS graph (or the panel chosen above). Other graphs are not changed.')
        self.use_style_btn.clicked.connect(self.use_saved_style); row.addWidget(self.use_style_btn); right.addLayout(row)
        remove=QPushButton('Remove component…'); remove.clicked.connect(self.remove_component); right.addWidget(remove)
        self.message=QLabel('',objectName='soft'); self.message.setWordWrap(True); right.addWidget(self.message)
        row=QHBoxLayout(); undo=QPushButton('Undo'); undo.clicked.connect(self.undo); row.addWidget(undo)
        redo=QPushButton('Redo'); redo.clicked.connect(self.redo); row.addWidget(redo); right.addLayout(row)
        right.addStretch(1)
        for text,fn,name in [('Send to Origin',self.origin,'accent'),('Export figure…',self.export,None),('Done',self.accept,'primary')]:
            button=QPushButton(text); button.clicked.connect(fn)
            if name: button.setObjectName(name)
            right.addWidget(button)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(side); scroll.setMinimumWidth(320); outer.addWidget(scroll,1)
        self.load_options()

    def options(self):
        switches=self.graph.combo.get('switches') or {}; selected=self.target.currentData()
        value=dict(switches)
        if selected!='all': value.update((switches.get('panel_options') or {}).get(selected,{}))
        return value

    def load_options(self,*_):
        self._loading=True; combo=self.graph.combo; options=self.options(); params=combo.get('params') or {}
        self.markers.setChecked(bool(options.get('markers',False)))
        self.observed_markers.setChecked(bool(options.get('observed_markers', options.get('markers',False))))
        self.fitted_markers.setChecked(bool(options.get('fitted_markers',False)))
        self.zoom.setChecked(bool(options.get('inset',params.get('inset',True))))
        self.difference.setChecked(bool(options.get('show_difference',True))); self.bragg.setChecked(bool(options.get('show_bragg',True)))
        mapping=dict(getattr(self.graph,'mapping',None) or [])
        lines=[str(l.get_label()).lower() for a in self.graph.fig.axes for l in a.lines]
        drawn_background=any('background' in l or 'baseline' in l for l in lines)
        fit_background='background' in mapping                     # a pattern-and-fit file that names its background column
        self.background.setChecked(bool(options.get('show_background',drawn_background and not fit_background)))
        from opstudio import side_tables as SD_
        has_labels=SD_.has_labels(self.graph.fig)
        self.peak_labels.setChecked(bool(has_labels and options.get('peak_labels',True)))
        zoom=options.get('zoom') or params.get('zoom') or []
        self.xmin.setText(str(zoom[0]) if len(zoom)>1 else ''); self.xmax.setText(str(zoom[1]) if len(zoom)>1 else '')
        ov=combo.get('overrides') or {}
        self.title.setText(str(ov.get('title',''))); self.xlabel.setText(str(ov.get('x_label',''))); self.ylabel.setText(str(ov.get('y_label','')))
        self.style.setCurrentIndex(max(0,self.style.findData(combo['style'])))
        fit=combo['template'].startswith('rietveld')
        self.observed_markers.setVisible(fit); self.fitted_markers.setVisible(fit)
        # A control is offered only where the graph has that component; otherwise it is greyed out and says why.
        has_ticks='tick rows' in mapping
        has_insets=any(a.child_axes for a in self.graph.fig.axes)
        can_zoom=fit or has_insets or 'zoom' in combo['template'] or 'inset' in combo['template']
        for box,on,why in [(self.difference,fit,'Only a pattern-and-fit graph (observed and calculated curves) has a difference row'),
                           (self.bragg,fit and has_ticks,'No reflection (tick) list is ticked with this fit: tick the list beside the data, the app does not invent reflections' if fit else 'Only a pattern-and-fit graph has Bragg reflection rows'),
                           (self.background,drawn_background or fit_background,'This graph\'s data has no background or baseline curve; the app does not make one up'),
                           (self.zoom,can_zoom,'This template has no zoom inset'),
                           (self.peak_labels,has_labels,'This graph has no labels on its peaks: tick a label list beside the data, the app does not invent labels')]:
            box.setEnabled(bool(on)); box.setToolTip('' if on else why)
        self.unsupported=[why for box,on,why in [(self.bragg,fit and has_ticks,'Bragg rows: no reflection list with this graph'),(self.background,drawn_background or fit_background,'Background: none in this graph\'s data'),
                                                  (self.difference,fit,'Difference row: pattern-and-fit graphs only'),(self.zoom,can_zoom,'Zoom inset: not part of this template')] if not on]
        if not self._applied_once: self.message.setText(('Not available for this graph - ' + '; '.join(self.unsupported) + '.') if self.unsupported else '')
        self._loading=False
        self.refresh_style_offer()

    def apply(self,*_):
        if self._loading: return
        new=copy.deepcopy(self.graph.combo); switches=new.setdefault('switches',{})
        target=self.target.currentData(); options=switches if target=='all' else switches.setdefault('panel_options',{}).setdefault(target,{})
        options.update(markers=self.markers.isChecked(),observed_markers=self.observed_markers.isChecked(),fitted_markers=self.fitted_markers.isChecked(),inset=self.zoom.isChecked(),show_difference=self.difference.isChecked(),
                       show_bragg=self.bragg.isChecked())
        if self.background.isEnabled(): options['show_background']=self.background.isChecked()
        if self.peak_labels.isEnabled():
            if self.peak_labels.isChecked(): options.pop('peak_labels',None)          # on is how the template draws it: nothing to store
            else: options['peak_labels']=False
        if target=='all':
            for value in switches.get('panel_options',{}).values():
                for key in ('markers','observed_markers','fitted_markers','inset','show_difference','show_bragg','show_background','peak_labels'): value.pop(key,None)
        if self.xmin.text().strip() or self.xmax.text().strip():
            try:
                lo,hi=float(self.xmin.text()),float(self.xmax.text())
                if not lo<hi: raise ValueError()
                options['zoom']=[lo,hi]
            except ValueError: self.message.setText('Enter a valid inset range with From less than To.'); return
        else: options.pop('zoom',None)
        enabled={'inset':self.zoom.isChecked(),'show_difference':self.difference.isChecked(),'show_bragg':self.bragg.isChecked(),'show_background':self.background.isChecked()}
        if new.get('removed_components'):
            new['removed_components']=[key for key in new['removed_components'] if not enabled.get(key,False)]
        new['style']=self.style.currentData(); ov=new.setdefault('overrides',{})
        for key,edit in [('title',self.title),('x_label',self.xlabel),('y_label',self.ylabel)]:
            if edit.text().strip(): ov[key]=edit.text().strip()
            else: ov.pop(key,None)
        if new==self.graph.combo: return
        self.history.append(copy.deepcopy(self.graph.combo)); self.future.clear(); self.graph.combo=new
        if not self.redraw(): self.graph.combo=self.history.pop(); return
        if self.apply_all.isChecked():
            for graph in self.controller.ws.singles:
                if graph is self.graph or not hasattr(graph,'combo') or graph.project_id!=self.graph.project_id: continue
                graph.combo['switches']=copy.deepcopy(switches); graph.build()
        if self.graph.project_id: self.controller._changed.add(self.graph.project_id)
        self._applied_once=True
        self.message.setText('Applied to '+('this graph.' if target=='all' else f'panel {int(target)+1}.'))

    def _learning(self):
        try:
            import workspace_learning as WL
            return WL.controller(self.controller.ws)
        except Exception: return None

    def _panel(self):
        t=self.target.currentData()
        return None if t=='all' else int(t)

    def refresh_style_offer(self):
        lc=self._learning(); found=[]
        try: found=lc.style_suggestions(self.graph,self._panel()) if lc is not None else []
        except Exception: found=[]
        self._style_offer=found[0] if found else None
        if hasattr(self,'use_style_btn'): self.use_style_btn.setVisible(bool(found))

    def save_style(self,target=None):
        """target: 'graph' | 'panel' | 'family' (asked for when not given). Returns the result or None."""
        lc=self._learning()
        if lc is None: self.message.setText('The style could not be remembered.'); return None
        panel=self._panel()
        if target is None:
            from PySide6.QtWidgets import QMenu
            from PySide6.QtGui import QCursor
            m=QMenu(self); picked=[]
            if panel is not None: m.addAction(f'For panel {panel+1} of this graph',lambda: picked.append('panel'))
            m.addAction('For this graph',lambda: picked.append('graph'))
            m.addAction('For graphs of this kind of data',lambda: picked.append('family'))
            m.exec(QCursor.pos())
            if not picked: return None
            target=picked[0]
        result,text=lc.save_style(self.graph,target=target,panel=panel if target=='panel' else None)
        self.message.setText(text); return result

    def use_saved_style(self):
        lc=self._learning(); offer=getattr(self,'_style_offer',None)
        if lc is None or offer is None: return False
        before=copy.deepcopy(self.graph.combo); changed,text=lc.apply_style(self.graph,offer,panel=self._panel())
        if changed:
            self.history.append(before); self.future.clear()
            if not self.redraw(): self.graph.combo=self.history.pop(); return False
            if self.graph.project_id: self.controller._changed.add(self.graph.project_id)
            self.load_options()
        self.message.setText(text); return changed

    def redraw(self):
        try:
            self.graph.build(); self.canvas.figure=self.graph.fig; self.graph.fig.set_canvas(self.canvas); self.canvas.draw_idle()
            self.controller.ws.draw(); return True
        except Exception as e: self.message.setText('Could not apply settings: '+str(e)); return False

    def undo(self):
        if self.history:
            self.future.append(copy.deepcopy(self.graph.combo)); self.graph.combo=self.history.pop(); self.redraw(); self.load_options()
    def redo(self):
        if self.future:
            self.history.append(copy.deepcopy(self.graph.combo)); self.graph.combo=self.future.pop(); self.redraw(); self.load_options()

    def remove_component(self):
        from PySide6.QtWidgets import QInputDialog
        names=['Zoom inset','Difference / residual row','Bragg reflection rows','Background / baseline curve']
        text,ok=QInputDialog.getItem(self,'Remove graph component','Component to remove:',names,editable=False)
        if not ok: return
        box=[self.zoom,self.difference,self.bragg,self.background][names.index(text)]
        before=copy.deepcopy(self.graph.combo)
        box.setChecked(False);self.apply()
        key=['inset','show_difference','show_bragg','show_background'][names.index(text)]
        removed=self.graph.combo.setdefault('removed_components',[])
        if key not in removed:
            if self.graph.combo==before:self.history.append(before)
            removed.append(key)
        if self.graph.project_id:self.controller._changed.add(self.graph.project_id)
        self.message.setText(text+' removed from this graph configuration. Its source data is retained; enable it to add it again.')

    def origin(self):
        class Tile:
            combo=self.graph.combo; fig=self.graph.fig
        self.controller.tp.draw_all_in_origin([Tile()])
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'Export figure',self.graph.sample+'.png','PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;TIFF (*.tiff)')
        if path:
            try: self.controller.tp.api.export(self.graph.fig,path,dpi=600); self.message.setText('Exported: '+path)
            except Exception as e: self.message.setText(str(e))


class NativePanelEditor(QDialog):
    """Per-graph controls for existing multi-graph previews, including Sample pages."""
    def __init__(self,ws,item,parent=None):
        super().__init__(parent or ws);self.ws=ws;self.item=item;self.loading=False
        self.setWindowTitle('Panel controls — '+item.title[:70]);self.resize(450,410)
        layout=QVBoxLayout(self)
        label=QLabel('Select the graph to change. Other graphs in the preview keep their settings.',objectName='soft');label.setWordWrap(True);layout.addWidget(label)
        self.target=QComboBox()
        subs=item.spec.get('cols') or [item.spec]
        for index,sub in enumerate(subs):self.target.addItem(f'Graph {index+1}: '+str(sub.get('title') or sub.get('xname') or 'Preview')[:35],str(index))
        layout.addWidget(self.target)
        self.zoom=QCheckBox('Show zoom inset');self.markers=QCheckBox('Show point markers')
        self.diff=QCheckBox('Show difference / residual row');self.bragg=QCheckBox('Show Bragg reflection rows')
        for box in [self.zoom,self.markers,self.diff,self.bragg]:layout.addWidget(box)
        row=QHBoxLayout();self.low=QLineEdit();self.high=QLineEdit();self.low.setPlaceholderText('Inset X from');self.high.setPlaceholderText('Inset X to')
        row.addWidget(self.low);row.addWidget(self.high);layout.addLayout(row)
        self.message=QLabel('',objectName='soft');self.message.setWordWrap(True);layout.addWidget(self.message)
        row=QHBoxLayout();apply=QPushButton('Apply to this graph');apply.clicked.connect(self.apply);row.addWidget(apply)
        close=QPushButton('Done');close.clicked.connect(self.accept);row.addWidget(close);layout.addLayout(row)
        self.target.currentIndexChanged.connect(self.load);self.load()

    def load(self,*_):
        import smart_plots as sp
        self.loading=True;key=self.target.currentData();sub=(self.item.spec.get('cols') or [self.item.spec])[int(key)]
        saved=(getattr(self.item,'fmt',None) or {}).get('native_panels',{}).get(key,{})
        self.zoom.setChecked(saved.get('inset',any(p.get('inset') for p in sub.get('panels',[]))))
        self.markers.setChecked(saved.get('markers',any(c.get('kind') in ('scatter','linesymbol') for p in sub.get('panels',[]) for c in p.get('curves',[]))))
        self.diff.setChecked(saved.get('show_difference',True));self.bragg.setChecked(saved.get('show_bragg',True))
        bounds=saved.get('zoom') or []
        self.low.setText(str(bounds[0]) if len(bounds)>1 else '');self.high.setText(str(bounds[1]) if len(bounds)>1 else '')
        self.loading=False

    def apply(self):
        if self.loading:return
        fmt=copy.deepcopy(getattr(self.item,'fmt',None) or {});key=self.target.currentData()
        options={'inset':self.zoom.isChecked(),'markers':self.markers.isChecked(),
                 'show_difference':self.diff.isChecked(),'show_bragg':self.bragg.isChecked()}
        if self.low.text().strip() or self.high.text().strip():
            try:
                lo,hi=float(self.low.text()),float(self.high.text())
                if lo>=hi:raise ValueError()
                options['zoom']=[lo,hi]
            except ValueError:self.message.setText('Enter a valid inset range: From must be less than To.');return
        fmt.setdefault('native_panels',{})[key]=options
        result=self.ws.ribbon.replace_fmt(self.item,fmt)
        self.message.setText('Applied to graph '+str(int(key)+1)+'. Other graphs were kept. Undo: Ctrl+Z.')

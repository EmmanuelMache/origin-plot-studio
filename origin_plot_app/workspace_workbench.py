"""Shared project, selection and template graph controller for all application pages."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import uuid
import pandas as pd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox
import smart_plots as sp
import workspace_projects as WP
from opstudio import data as OD
from opstudio.detection import detect, compatibility, family_matches, FAMILIES


class TemplateGraph(sp.Item):
    """An editable Analysis template displayed as an ordinary Workspace graph."""
    def __init__(self, controller, combo):
        self.controller = controller; self.combo = copy.deepcopy(combo)
        self.combo.setdefault('graph_id', uuid.uuid4().hex)
        path = self.combo['files'][0]
        table = controller.table_for(path, self.combo.get('project_id'))
        det = sp.detect(table.name, table.df, {})
        det.update(name=table.name, nums={c: pd.Series(table.arr(c)) for c in table.numeric},
                   _df=table.df.copy(), _template_graph=True)
        super().__init__(path, det, [])
        self.name = table.name + ' · ' + self.combo['graph_id'][:8]
        self.sample = self.combo.get('sample', table.name)
        self.project_id = self.combo.get('project_id')
        self.project = (WP.get(self.project_id) or {}).get('name')
        self._template_name = controller.template_name(self.combo['template'])
        self.kind = 'Template · ' + self._template_name
        self.fig = None; self.build()

    @property
    def title(self):
        return f'{self.sample}  [{self._template_name}]  ({os.path.basename(self.path)})'

    def build(self, opt=None, kind=None):
        self.fig, self.mapping = self.controller.draw_combo(self.combo)
        from matplotlib.colors import to_rgb
        panels = []
        for ax in self.fig.axes:
            if getattr(ax, '_ops_auxiliary', False): continue
            curves = []
            for index, line in enumerate(ax.lines):
                if not line.get_visible() or len(line.get_xdata()) < 3: continue
                label = str(line.get_label())
                if label.startswith('_'): label = self.sample if len(ax.lines) == 1 else f'Series {index+1}'
                try:
                    colour = tuple(int(round(v*255)) for v in to_rgb(line.get_color()))
                    curves.append(sp.curve(label, line.get_xdata(), line.get_ydata(), colour))
                except (TypeError,ValueError): continue
            if curves: panels.append(sp.panel(ax.get_ylabel(), curves, legend=False))
        self.spec = sp.finish(dict(title=self.title, xname=self.fig.axes[0].get_xlabel(), panels=panels)) if panels else {'title':self.title,'panels':[]}
        self.spec['_template_graph'] = True
        self.record = ['Analysis template: ' + self.combo['template']] + [f'{a}: {b}' for a,b in self.mapping]
        self.results = None; self.warnings = []; return self


class Workbench:
    def __init__(self, ws):
        self.ws = ws; self.tp = ws.templates_page; self.active_project = None
        self.open_projects = set(); self.working = {}; self.preferences = {}; self._source_stamps = {}
        self._original_table_of = self.tp.table_of
        self._opening = False; self._open_jobs = []; self._changed = set()
        self.tp.table_of = self.table_of
        def warm_examples():                                    # every template's example (what it takes) is made once, here, in the background:
            try:                                                # the first look at 'Choose a graph' then does not stop the window to make all of them
                for row in self.tp.api.all_templates():
                    try: OD._example(self.tp.api.resolve(row['id'])[0])
                    except Exception: pass
            except Exception: pass
        import threading
        QTimer.singleShot(1200, lambda: threading.Thread(target=warm_examples, daemon=True, name='ops-template-examples').start())
        self.ws._warm_tables = self.tp.raw_tables              # read by the file reader's own thread, so the window does not stop to read each file a second time
        original_combos = self.tp.combos
        def combos():
            out = original_combos()
            for combo in out:
                if combo.get('files'):
                    combo['project_id'] = self.project_for(combo['files'][0])
                    combo['params'] = copy.deepcopy(self.tp.params.get(combo['template']) or {})
                    combo.setdefault('switches', copy.deepcopy(self.tp.current_switches()))
            return out
        self.tp.combos = combos
        original_draw_combo = self.tp.draw_combo
        self._original_draw_combo = original_draw_combo
        self.tp.draw_combo = self.draw_combo
        self._wrap_workspace()
        from workspace_workbook import WorkbookPage
        self.workbook = WorkbookPage(ws, self); ws.pages.addWidget(self.workbook)
        self._install_header(); self._install_actions()
        original_add=self.tp.add_files
        def add_files(paths=None, project=None, on_done=None):
            if paths is None and self.active_project:
                return self.ws.pages.widget(6).add_files()
            slug=self.active_project
            if project and (not slug or (WP.get(slug) or {}).get('name')!=project):
                slug=next((s for s,p in WP.list_projects() if p['name']==project),None)
            if slug and paths:
                WP.add_files(slug,paths); self.open_projects.add(slug); self._changed.add(slug)
                project=WP.get(slug)['name']
            def done(items):
                if slug:
                    for item in items: item.project_id=slug; item.project=project
                if on_done:on_done(items)
            if self.ws.thread is not None:
                # Workspace reads one batch at a time. The files are listed (and ticked) at once, as always; only the
                # reading waits its turn - and it does not tick them a second time when its turn comes.
                new=[p for p in (paths or []) if os.path.isfile(p)]
                for path in new:
                    if path not in self.tp.extra_files:self.tp.extra_files.append(path)
                self.tp.refresh_files(); self.tp.tick_files(new)
                def later():
                    if self.ws.thread is not None: QTimer.singleShot(150,later); return
                    have={os.path.abspath(str(getattr(item,'path','') or '')) for item in self.ws.singles}
                    todo=[p for p in new if os.path.abspath(p) not in have]
                    if todo: self.ws.load(todo,project=project,on_done=done)
                    else: done([])
                QTimer.singleShot(150,later); return
            collisions=bool(slug and paths and any(getattr(item,'path','') in paths and getattr(item,'project_id',None) not in (None,slug) for item in self.ws.singles))
            if collisions:
                for path in paths:
                    if path not in self.tp.extra_files:self.tp.extra_files.append(path)
                self.tp.refresh_files(); return self.ws.load(paths,project=project,on_done=done)
            return original_add(paths,project,done)
        self.tp.add_files=add_files
        ws.pages.currentChanged.connect(self.page_changed)
        self._save_timer = QTimer(ws); self._save_timer.setInterval(60000)
        self._save_timer.timeout.connect(self.save_open_projects); self._save_timer.start()

    def project_for(self, path):
        p = WP.get(self.active_project) if self.active_project else None
        if p and path in p['files']: return self.active_project
        return next((s for s,p in WP.list_projects() if s in self.open_projects and path in p['files']), None)

    def settings_for(self, path, slug=None):
        slug = slug or self.project_for(path)
        key = (slug, path)
        if key not in self.preferences:
            self.preferences[key] = copy.deepcopy(((WP.get(slug) or {}).get('file_settings') or {}).get(path) or {})
        return self.preferences[key]

    def has_working_state(self, path, slug=None):
        """Does this input have anything of its own saved over the source file - edited cells, a chosen sheet, a column
        order / selection or a data type? If not, its graphs are exactly what reading the file gives."""
        st = self.settings_for(path, slug)
        if st.get('edited_sheets') or st.get('sheet') or any(st.get(k) for k in ('order', 'off', 'type')): return True
        return any(v.get('order') or v.get('off') or v.get('type') for v in (st.get('sheet_settings') or {}).values())

    def raw_sheets(self, path, slug=None):
        slug = slug or self.project_for(path); key = (slug, path)
        if key not in self.working:
            raw = self.tp.raw_tables(path)
            sheets = {s: df.copy() for s, df in raw['sheets'].items()}
            settings = self.settings_for(path, slug)
            for name, frame in settings.get('edited_sheets', {}).items():
                sheets[name] = pd.DataFrame(frame['data'], columns=frame['columns'])
            self.working[key] = sheets
            try: self._source_stamps[path] = os.stat(path).st_mtime_ns
            except OSError: pass
        return self.working[key]

    def refresh_sources(self):
        for path, previous in list(self._source_stamps.items()):
            try: stamp = os.stat(path).st_mtime_ns
            except OSError: continue
            if stamp == previous: continue
            self.tp.tables.pop(path, None); self.tp._sheet_pick_cache.clear()
            for key in [k for k in self.working if k[1] == path]:
                if not self.settings_for(path, key[0]).get('edited_sheets'):
                    self.working.pop(key, None)
                else:
                    self.ws.log(os.path.basename(path) + ': source changed; saved working-copy edits have been retained.')
            self._source_stamps[path] = stamp

    def table_for(self, path, slug=None):
        return self._table(path, slug)[0]

    def table_of(self, path): return self._table(path, self.project_for(path))

    def _table(self, path, slug, sheet=None):
        """sheet: read this sheet (with its own mapping) instead of the file's selected one - used to find the sheet that fits a template."""
        sheets = self.raw_sheets(path, slug); prefs = self.settings_for(path, slug)
        names = list(sheets)
        selected = sheet if sheet in sheets else prefs.get('sheet')
        if selected not in sheets:
            selected = next((n for n in names if n.strip().lower() == 'data'), None)
            if selected is None: selected = self.tp._best_sheet(sheets)
        base = prefs
        scoped = base.setdefault('sheet_settings', {}).setdefault(selected, {})
        # Migrate a legacy per-file mapping only on its selected sheet.
        if not scoped:
            for key in ('order','off','type'):
                if key in base: scoped[key] = copy.deepcopy(base[key])
        prefs = scoped
        df = sheets[selected].copy(); df.columns = [str(c) for c in df.columns]
        order = prefs.get('order') or []
        off = prefs.get('off') or []
        cols = list(df.columns)
        if 'order' not in prefs and 'off' not in prefs:        # no choice made for this file yet: the one remembered for files with the same headers
            remembered = (self.tp._cfg().get('mappings') or {}).get(self.tp._pattern(cols)) or {}
            order = remembered.get('order') or []; off = remembered.get('off') or []
        selected_cols = [c for c in order if c in cols and c not in off]
        selected_cols += [c for c in cols if c not in selected_cols and c not in off]
        if selected_cols or off: df = df[selected_cols]
        table = OD.Table(Path(path).stem, df)
        table.measurement_type = prefs.get('type')
        return table, selected, names, cols, prefs

    def set_mapping(self, path, x, y, sheet_index, measurement):
        slug = self.project_for(path); prefs = self.settings_for(path, slug)
        sheets = list(self.raw_sheets(path, slug))
        if 0 <= sheet_index < len(sheets): prefs['sheet'] = sheets[sheet_index]
        selected_sheet = prefs['sheet']
        prefs = prefs.setdefault('sheet_settings', {}).setdefault(selected_sheet, {})
        df = self.raw_sheets(path, slug)[selected_sheet]
        cols = [str(c) for c in df.columns]
        if x and y and x != y: prefs['order'] = [x,y] + [c for c in cols if c not in (x,y)]
        if measurement and measurement != 'Automatic': prefs['type'] = measurement
        else: prefs.pop('type', None)
        self.changed(path, slug); self.tp._sheet_pick_cache.clear(); self.refresh_source_graphs(path, slug); self.tp.filter_templates(); self.tp.schedule()

    def mapping_for(self, path, slug=None):
        return self._table(path, slug or self.project_for(path))[4]

    def refresh_source_graphs(self, path, slug=None):
        slug = slug or self.project_for(path)
        try:
            selected_table, selected_sheet, names, _cols, _prefs = self._table(path, slug)
            sheets = self.raw_sheets(path, slug)
        except Exception: return
        for item in self.ws.singles:
            if getattr(item, 'path', '') != path: continue
            if slug and getattr(item, 'project_id', None) not in (slug, None): continue
            try:
                if isinstance(item, TemplateGraph): item.build(); continue
                # Structured workbook figures retain their own recipes and specialised readers.
                if item.det.get('_composed') or sp.figtype_id(item.kind):
                    item._working_sheets = {name:frame.copy() for name,frame in sheets.items()}
                    item.build(self.ws.opt, item.kind); continue
                source_sheet = item.det.get('_source_sheet')
                if source_sheet not in sheets:
                    if len(sheets) > 1: continue
                    source_sheet = selected_sheet
                if source_sheet == selected_sheet:
                    table = selected_table; prefs = _prefs
                else:
                    table = OD.Table(item.name, sheets[source_sheet].copy())
                    prefs = self.settings_for(path, slug).get('sheet_settings', {}).get(source_sheet, {})
                    table.reorder(prefs.get('order') or [])
                det = sp.detect(item.name, table.df, item.det.get('units') or {})
                if det.get('kind') == 'skip':
                    self.ws.log('No usable graph columns in '+os.path.basename(path)+'. Correct the Workbook mapping.'); continue
                metadata = {k:v for k,v in item.det.items() if str(k).startswith('_') and k not in ('_df','_raw')}
                det.update(metadata); det['_source_sheet'] = source_sheet
                override = prefs.get('type')
                kind = {'General XY':'XY', 'Unknown':'XY', 'Raman':'FTIR', 'Rheology':'XY',
                        'Electrochemistry':'XY', 'Strength':'XY'}.get(override, override)
                if kind and kind in sp.BUILDERS and det.get('kind') != kind: det = sp.coerce(det, kind)
                det['_df'] = table.df.copy()
                if 'x' in det and table.x: det['x'] = table.x
                if 'ys' in det:
                    prior = [c for c in item.det.get('ys', []) if c in table.ys]
                    det['ys'] = prior if getattr(item, 'nfile', 1) > 1 and prior else table.ys
                item.det = det; item.build(self.ws.opt, det.get('kind'))
            except Exception as e: self.ws.log('Could not rebuild '+os.path.basename(path)+': '+str(e))
        self.ws.regroup(); self.ws.refresh_list()
        if self.ws.current() is not None: self.ws.draw()

    def changed(self, path, slug=None):
        slug = slug or self.project_for(path)
        if slug: self._changed.add(slug)
        self.ws.set_status('Project has unsaved changes. Save project to keep data edits and graph settings.')

    def select_inputs(self, paths, project_inputs=None):
        paths = list(dict.fromkeys(paths)); self.tp._timer.stop()
        for path in paths:
            if path not in self.tp.extra_files: self.tp.extra_files.append(path)
        self.tp.refresh_files(); self.tp.files.blockSignals(True)
        for i in range(self.tp.files.count()):
            self.tp.files.item(i).setCheckState(Qt.Checked if self.tp.files.item(i).data(Qt.UserRole) in paths else Qt.Unchecked)
        self.tp.files.blockSignals(False); self.tp.files.sync(); self.tp.filter_templates()
        ids = {os.path.abspath(p) for p in paths}
        for i, item in enumerate(self.ws.items):
            belongs = os.path.abspath(str(getattr(item, 'path', '') or '')) in ids
            project_id = getattr(item, 'project_id', None)
            if project_inputs is not None:
                belongs = belongs and (project_id, getattr(item,'path','')) in set(project_inputs)
            elif project_id and self.active_project and project_id != self.active_project: belongs = False
            self.ws.list.item(i).setCheckState(Qt.Checked if belongs else Qt.Unchecked)
        self.ws.update_count()
        return paths

    def workbook_recommendations(self, paths, together=False):
        if not paths or together and len(paths) > 1: return []
        import gallery_graphs as TG
        codes=[]; reason=''
        for path in paths:
            if not path.lower().endswith(('.xlsx','.xlsm','.xls')): return []
            try:
                book=TG.book_from_frames(self.raw_sheets(path),Path(path).stem)
                code,reason=TG.recognise(book)
                if not code: return []
                codes.append(code)
            except Exception: return []
        if len(set(codes)) != 1: return []
        tid='wb:'+codes[0]
        row=next((r for r in self.tp.catalogue if r['id']==tid and r['available']),None)
        return [dict(row,compatible=True,reason=reason,score=12)] if row else []

    def recommendations(self, paths, together=False, focus=None):
        """focus: the file being looked at. With separate graphs (not combined) the templates are those that fit THAT
        file - a selection of mixed kinds (scans, thermal runs, a workbook) has no template that fits them all, and
        would otherwise offer nothing but the plain plot. 'Create graph' then draws each selected file the template fits."""
        if focus and not together and focus in paths: paths = [focus]
        # Refresh from the catalogue owned by Analysis, including private templates.
        self.tp.catalogue = self.tp._catalogue()
        tables = []
        for path in paths:
            try: tables.append(self.table_for(path))
            except Exception: continue
        workbook_rows = self.workbook_recommendations(paths, together)
        if not tables: return workbook_rows
        results = [detect(t, getattr(t,'measurement_type',None)) for t in tables]
        result = results[0]
        if any(r.needs_confirmation for r in results):
            # Not identified yet: no specialised template is offered, but the data can always be looked at as a plain
            # plot of the mapped columns (the installed Line plot of the Analysis catalogue), without guessing what it is.
            rows = list(workbook_rows)
            row = next((r for r in self.tp.catalogue if r['id'] == 'scientific_line' and r['available']), None)
            if row is not None:
                try:
                    template, _p, _s, _st, ov = self.tp.api.resolve('scientific_line')
                    for group in ([tables] if together else [[t] for t in tables]): OD.bundle(template, group, ov)
                    rows.append(dict(row, compatible=True, score=0, reason='Plain plot of the mapped columns. Confirm the data type to see the specialised templates'))
                    if not any(r.get('recommended') for r in rows): rows[-1]['recommended'] = True
                except Exception: pass
            return rows
        groups = [tables] if together else [[t] for t in tables]
        ranks = [self.tp.api.recommend(g) for g in groups]
        scores = {tid: score for tid,score,_why in ranks[0]}
        for ranked in ranks[1:]:
            other = {tid:score for tid,score,_why in ranked}
            scores = {tid: min(score,other[tid]) for tid,score in scores.items() if tid in other}
        rows = list(workbook_rows)
        for row in self.tp.catalogue:
            if not row['available'] or row['id'].startswith('wb:'): continue
            try:
                template, _p, _s, _st, ov = self.tp.api.resolve(row['id'])
                family = (template.id+' '+template.category).lower()
                if result.kind in FAMILIES and not family_matches(template, result.kind): continue
                checks = [compatibility(template,g,detect(g[0],getattr(g[0],'measurement_type',None)),ov) for g in groups]
                ok = all(x[0] for x in checks)
                reason = next((why for good,why in checks if not good), 'Required inputs available')
                if ok and row['id'] not in scores: continue
                rows.append(dict(row, compatible=ok, reason=reason, score=scores.get(row['id'],-100)))
            except Exception: continue
        rows.sort(key=lambda r:(not r['compatible'],-r['score'],r['name']))
        good = next((r for r in rows if r['compatible']),None)
        if good: good['recommended'] = True
        return rows

    def template_name(self, tid):
        return next((r['name'] for r in self.tp.catalogue if r['id']==tid),tid)

    def draw_combo(self, combo, width=None, target=None):
        previous = self.active_project
        self.active_project = combo.get('project_id') or previous
        try:
            if str(combo['template']).startswith('wb:') and not combo.get('demo'):
                if target is not None: raise self.tp.api.Unfit('Workbook templates occupy a complete figure')
                import gallery_graphs as TG
                from opstudio.graph_components import apply
                book=TG.book_from_frames(self.raw_sheets(combo['files'][0]),Path(combo['files'][0]).stem)
                fig,result=TG.figure(combo['template'][3:],book)
                style=self.tp.ops.load_style(combo.get('style') or self.tp.style0)
                self.tp.api._post(fig,combo.get('switches') or {},style); apply(fig,combo.get('switches') or {})
                return fig,[('workbook',Path(combo['files'][0]).name),('template',combo['template'])]
            if combo.get('demo'): return self._original_draw_combo(combo,width,target)
            return self.tp.api.draw(combo['template'], [self.tp._table_for_template(path, combo['template']) for path in combo['files']],   # the sheet that fits this template, unless you chose one
                style=combo.get('style') or self.tp.style0,
                params=combo.get('params', self.tp.params.get(combo['template']) or None),
                switches=combo.get('switches',self.tp.current_switches()), overrides=combo.get('overrides'),
                width=width,target=target)
        finally: self.active_project = previous

    def create_graphs(self, paths, tid, together=False):
        if not paths: return
        skipped = []
        if together:
            valid = {r['id']:r for r in self.recommendations(paths,True)}
            if tid not in valid or not valid[tid]['compatible']:
                self.ws.set_status('This template does not fit the selected data. Review data type, mapping and required inputs.'); return
        else:                                   # one graph per file: each file is checked on its own; a file the template does not fit is left out and named
            fits = [p for p in paths if (lambda rows: any(r['id']==tid and r['compatible'] for r in rows))(self.recommendations([p],False))]
            skipped = [p for p in paths if p not in fits]
            if not fits:
                self.ws.set_status('This template does not fit the selected data. Review data type, mapping and required inputs.'); return
            paths = fits
        self.select_inputs(paths); groups = [paths] if together else [[p] for p in paths]
        graphs = []; errors=[]
        for group in groups:
            slug = self.project_for(group[0]); self.open_projects.add(slug) if slug else None
            name = Path(group[0]).stem if len(group)==1 else f'{len(group)} selected scans'
            combo = {'files':list(group),'template':tid,'style':self.tp.style0,'sample':name,
                     'title':name,'caption':self.template_name(tid),'project_id':slug,
                     'params':copy.deepcopy(self.tp.params.get(tid) or {}),
                     'switches':{'markers':False}}
            try: graphs.append(TemplateGraph(self,combo))
            except Exception as e: errors.append(f'{name}: {e}')
        self.ws.singles.extend(graphs); self.ws.regroup(); self.ws.refresh_list()
        if graphs:
            self.ws._tick_only(graphs); self.ws.list.setCurrentRow(self.ws.items.index(graphs[0])); self.ws.go(0)
            if self.active_project: self._changed.add(self.active_project)
        self.ws.set_status(f'{len(graphs)} graph(s) created from Analysis templates. Each graph keeps independent settings.'+
                           (' '+ '; '.join(errors) if errors else '')+
                           (f' Left out, the template does not fit them: '+', '.join(os.path.basename(p) for p in skipped[:6])+(' …' if len(skipped)>6 else '')+'.' if skipped else ''))
        return graphs

    def open_inputs(self, pairs, then_workspace=False):
        """then_workspace: show Workspace when the reading is done ('Open selected' on Start here) - the graphs are there."""
        if self._opening or self.ws.thread is not None:
            self.ws.set_status('An import is running. Wait for it to finish before opening another selection.'); return
        pairs = list(dict.fromkeys(pairs))
        if not pairs: self.ws.set_status('Select a project, folder or file first.'); return
        self._open_goto = bool(then_workspace)
        self._opening = True; self._open_jobs = []
        groups = {}
        for slug,path in pairs: groups.setdefault(slug,[]).append(path)
        self._input_order = list(pairs)
        self._open_paths = [path for _,path in pairs]
        for slug,paths in groups.items(): self._open_jobs.append((slug,paths))
        self._next_open()

    def _next_open(self):
        if not self._open_jobs:
            self._opening = False
            rank = {key:index for index,key in enumerate(self._input_order)}
            indexed = list(enumerate(self.ws.singles))
            indexed.sort(key=lambda pair:(rank.get((getattr(pair[1],'project_id',None),getattr(pair[1],'path','')),len(rank)), pair[0]))
            self.ws.singles = [item for _,item in indexed]; self.ws.regroup(); self.ws.refresh_list()
            self.select_inputs(self._open_paths, self._input_order)
            if self._input_order:
                slug,path=self._input_order[0]
                candidates=[i for i in self.ws.singles if getattr(i,'project_id',None)==slug and getattr(i,'path','')==path]
                saved=((WP.get(slug) or {}).get('state') or {}).get('current_graph')
                focused=next((i for i in candidates if (i.combo.get('graph_id') if isinstance(i,TemplateGraph) else sp.key_of(i))==saved),None)
                focused=focused or (candidates[0] if candidates else None)
                if focused in self.ws.items:self.ws.list.setCurrentRow(self.ws.items.index(focused))
            self.workbook.set_paths(self._open_paths)
            sh = self.ws.pages.widget(6); sh.refresh()
            if getattr(self, '_open_goto', False):
                self._open_goto = False; self.ws.go(0)
                self.ws.set_status(f'Opened {len(self._open_paths)} selected input(s) in Workspace. Workbook and Analysis have them too.'); return
            self.ws.set_status(f'Opened {len(self._open_paths)} selected input(s). Continue in Workbook, Analysis or Workspace.'); return
        slug, paths = self._open_jobs.pop(0); project = WP.get(slug)
        if not project: return self._next_open()
        self.active_project = slug; self.open_projects.add(slug)
        existing = {(getattr(it,'project_id',None),getattr(it,'path','')) for it in self.ws.singles}
        new_paths = [p for p in paths if os.path.isfile(p) and (slug,p) not in existing]
        state = project.get('state') or {}; session = state.get('session') or {}
        have_graphs = [it for it in self.ws.singles if getattr(it,'project_id',None)==slug]
        if session.get('graphs') and new_paths:
            snapshot = copy.deepcopy(session)
            snapshot['files'] = [p for p in snapshot['files'] if p in new_paths]
            snapshot['graphs'] = [g for g in snapshot['graphs'] if g.get('file') in new_paths]
            singles,boards,lines = sp.session_load(snapshot,self.ws.opt)
            for it in singles: it.project_id=slug; it.project=project['name']
            self.ws.singles.extend(singles); self.ws.boards.extend(boards)
            for path in paths: self.refresh_source_graphs(path, slug)
            for line in lines: self.ws.log(line)
            restored = {it.path for it in singles}; new_paths = [p for p in new_paths if p not in restored]
        for combo in state.get('templates',[]):
            if not all(p in paths for p in combo['files']): continue
            if any(isinstance(it,TemplateGraph) and it.project_id==slug and it.combo.get('graph_id')==combo.get('graph_id') for it in self.ws.singles): continue
            try: self.ws.singles.append(TemplateGraph(self,combo))
            except Exception as e: self.ws.log('Saved graph could not be restored: '+str(e))
        def done(items):
            if not hasattr(self.ws,'group_fmt'): self.ws.group_fmt={}
            for keys,fmt in state.get('group_formats',[]): self.ws.group_fmt[tuple(keys)]=copy.deepcopy(fmt)
            for how,keys in state.get('groups',[]):
                entry = (how, list(keys))
                if entry not in self.ws.user_groups: self.ws.user_groups.append(entry)
            for it in items: it.project_id=slug; it.project=project['name']
            self.ws.regroup(); self.ws.refresh_list()
            for path in paths:
                if self.has_working_state(path, slug): self.refresh_source_graphs(path, slug)     # only a file with saved edits or mappings differs from what was just read
            QTimer.singleShot(0,self._next_open)
        # Load independently of another project's copy of the same input.
        for p in paths:
            if p not in self.tp.extra_files: self.tp.extra_files.append(p)
        self.tp.refresh_files()
        if new_paths: self.ws.load(new_paths,project=project['name'],on_done=done)
        else: done([])

    def capture_project(self, slug):
        project = WP.get(slug)
        if not project: return {}
        singles = [i for i in self.ws.singles if not isinstance(i,TemplateGraph) and
                   (getattr(i,'project_id',None)==slug or (not getattr(i,'project_id',None) and getattr(i,'project',None)==project['name']))]
        templates = [copy.deepcopy(i.combo) for i in self.ws.singles if isinstance(i,TemplateGraph) and i.project_id==slug]
        for tile in self.tp.tiles:
            if tile.fig is None or tile.combo.get('demo') or not tile.keep.isChecked(): continue
            if tile.combo.get('project_id') != slug: continue
            tile.combo.setdefault('graph_id', uuid.uuid4().hex)
            if not any(c.get('graph_id') == tile.combo['graph_id'] for c in templates): templates.append(copy.deepcopy(tile.combo))
        keys = {sp.key_of(i) for i in self.ws.singles if getattr(i,'project_id',None)==slug or i in singles}
        boards = [b for b in self.ws.boards if b.keys and all(k in keys for k in b.keys)]
        groups = [[how,list(ks)] for how,ks in self.ws.user_groups if all(k in keys for k in ks)]
        settings={}
        for path in project['files']:
            prefs = copy.deepcopy(self.settings_for(path,slug))
            settings[path]=prefs
        session = sp.session_dump(singles,boards,self.ws.settings_now())
        session['info_files'] = [p for p in session.get('info_files',[]) if p in project['files']]
        current = self.ws.current()
        current_key = current.combo.get('graph_id') if isinstance(current,TemplateGraph) else sp.key_of(current) if current is not None else None
        return {'session':session,'templates':templates, 'current_graph':current_key,
                'groups':groups,'group_formats':[[list(k),copy.deepcopy(v)] for k,v in getattr(self.ws,'group_fmt',{}).items() if all(key in keys for key in k)],'file_settings':settings,
                'selected':[self.tp.files.item(i).data(Qt.UserRole) for i in range(self.tp.files.count()) if self.tp.files.item(i).checkState()==Qt.Checked and self.tp.files.item(i).data(Qt.UserRole) in project['files']],
                'page':self.ws.pages.currentIndex()}

    def save_project(self, slug=None, silent=False):
        slug = slug or self.active_project
        if not slug or not WP.get(slug):
            if not silent: self.ws.set_status('Select or create a project first.')
            return False
        state = self.capture_project(slug)
        if slug not in self.open_projects and not any(getattr(i,'project_id',None)==slug for i in self.ws.singles):
            # Saving an unopened project must not discard saved graphs.
            old = WP.get(slug).get('state') or {}
            state['session']=old.get('session',state['session']); state['templates']=old.get('templates',[])
        try:
            for path,prefs in state.pop('file_settings').items(): WP.set_file_settings(slug,path,prefs)
            WP.save_state(slug,state)
        except Exception as e:
            self.ws.set_status('Project could not be saved: '+str(e)); self.ws.log('Project save failed: '+str(e)); return False
        self._changed.discard(slug)
        if not silent: self.ws.set_status(f"Project '{WP.get(slug)['name']}' saved.")
        return True

    def session_extras(self):
        return {'workbench_group_formats':[[list(k),copy.deepcopy(v)] for k,v in getattr(self.ws,'group_fmt',{}).items()], 'template_graphs':[copy.deepcopy(i.combo) for i in self.ws.singles if isinstance(i,TemplateGraph)],
                'workbench_files':[{'project_id':slug,'path':path,'settings':copy.deepcopy(prefs)}
                                   for (slug,path),prefs in self.preferences.items()]}

    def restore_session_extras(self, snapshot):
        self.ws.group_fmt={tuple(k):copy.deepcopy(v) for k,v in snapshot.get('workbench_group_formats',[])}
        for item in snapshot.get('workbench_files',[]):
            key=(item.get('project_id'),item['path']); self.preferences[key]=copy.deepcopy(item['settings'])
            self.working.pop(key,None)
        for combo in snapshot.get('template_graphs',[]):
            try: self.ws.singles.append(TemplateGraph(self,combo))
            except Exception as e: self.ws.log('Saved template could not be restored: '+str(e))
        self.ws.regroup(); self.ws.refresh_list()

    def save_open_projects(self):
        if self.ws.thread is not None or self.ws.job_thread is not None: return
        for slug in list(self.open_projects | self._changed): self.save_project(slug,silent=True)

    def close_project(self, slug, save=True):
        if not slug or not WP.get(slug): return
        if save and not self.save_project(slug,silent=True): return False
        p=WP.get(slug); paths=set(p['files'])
        self.ws.singles=[i for i in self.ws.singles if not (getattr(i,'project_id',None)==slug or
             (not getattr(i,'project_id',None) and getattr(i,'project',None)==p['name']))]
        still={getattr(i,'path','') for i in self.ws.singles}
        self.tp.extra_files=[f for f in self.tp.extra_files if f not in paths or f in still]
        self.open_projects.discard(slug); self._changed.discard(slug)
        if self.active_project==slug: self.active_project=next(iter(self.open_projects),None)
        self.ws.regroup(); self.ws.refresh_list(); self.tp.refresh_files()
        remaining=[self.tp.files.item(i).data(Qt.UserRole) for i in range(self.tp.files.count()) if self.tp.files.item(i).checkState()==Qt.Checked]
        self.workbook.set_paths(remaining)
        if not self.ws.items: self.ws.show_empty(); self.ws.go(6)
        self.ws.set_status(f"Project '{p['name']}' saved and closed.")

    def remove_input(self, slug, path):
        self.ws.singles = [i for i in self.ws.singles if not ((getattr(i,'path','')==path or path in (getattr(i,'combo',{}).get('files') or [])) and
                            (slug is None or getattr(i,'project_id',None) in (None,slug)))]
        if not any(getattr(i,'path','')==path for i in self.ws.singles):
            self.tp.extra_files=[p for p in self.tp.extra_files if p!=path]
        self.ws.regroup(); self.ws.refresh_list(); self.tp.refresh_files()
        if not self.ws.items: self.ws.show_empty()

    def page_changed(self, index):
        if index==6:
            self.ws.set_status('Select projects, folders or files. Inspect data, then choose an Analysis template.')
        if index==7:
            paths=[self.tp.files.item(i).data(Qt.UserRole) for i in range(self.tp.files.count()) if self.tp.files.item(i).checkState()==Qt.Checked]
            self.workbook.set_paths(paths)
        current=self.ws.current()
        self.ws.ribbon.setVisible(index==0 and bool(self.ws.items) and self.ws.ribbon.display!=2)
        if hasattr(self.ws,'export_btn'): self.ws.export_btn.setEnabled(bool(self.ws.items))
        self.graph_edit.setEnabled(current is not None)
        if hasattr(self.ws,'_adaptive_header'): self.ws._adaptive_header.update()      # 'Add files…' in the header: not on Start here, and only when it fits

    def _wrap_workspace(self):
        w=self.ws; original_draw=w.draw
        original_load=w.load
        def load(paths,tick=False,project=None,on_done=None):
            slug=self.active_project if self.active_project and WP.get(self.active_project) else None
            if slug and project is None:
                WP.add_files(slug,paths);self.open_projects.add(slug);self._changed.add(slug)
                project=WP.get(slug)['name']
            elif project and slug and WP.get(slug)['name']!=project:
                slug=next((s for s,p in WP.list_projects() if p['name']==project),None)
            def done(items):
                if slug:
                    for item in items:item.project_id=slug
                if on_done:on_done(items)
            return original_load(paths,tick,project,done)
        w.load=load
        def draw():
            it=w.current()
            if not isinstance(it,TemplateGraph): return original_draw()
            try:
                from opstudio.origin import read_figure
                # The exact figure (including independent insets/components) is displayed and exported.
                old=w.canvas.figure; new=it.fig
                w.canvas.figure=new; new.set_canvas(w.canvas); w.fig=new
                w.canvas.draw_idle(); w.navtb.update(); w.navtb.push_current()
                w.gtitle.setText(it.sample); w.gsub.setText(self.template_name(it.combo['template'])+' · '+(it.project or 'Session'))
            except Exception as e: w.set_status(f'Graph preview failed: {e}')
        def restore_canvas():
            if isinstance(w.current(),TemplateGraph): return
            from matplotlib.figure import Figure
            if getattr(w.fig,'_ops',None):
                f=Figure(figsize=(7.2,5.0),dpi=100,facecolor="white"); w.fig=f; w.canvas.figure=f; f.set_canvas(w.canvas)
        w.draw=lambda: (restore_canvas(),draw())[-1]
        refresh_list=w.refresh_list
        def refresh():
            result=refresh_list()
            if hasattr(self,'graph_edit'): self.page_changed(w.pages.currentIndex())
            return result
        w.refresh_list=refresh
        origin=w.draw_origin
        def draw_origin(which):
            chosen=w.ticked() if which=='ticked' else w.items if which=='all' else [w.current()]
            templates=[i for i in chosen if isinstance(i,TemplateGraph)]
            if not templates: return origin(which)
            # Templates use the existing figure-to-Origin driver, including all current component edits.
            class Tile:
                def __init__(self,it): self.combo=it.combo; self.fig=it.fig
            result = self.tp.draw_all_in_origin([Tile(it) for it in templates])
            regular = [i for i in chosen if not isinstance(i, TemplateGraph)]
            if regular:
                previous = w.ticked(); w._tick_only(regular)
                try: origin('ticked')
                finally: w._tick_only(previous)
            return result
        w.draw_origin=draw_origin
        save_current=w.save_current
        def export_current():
            it=w.current()
            if not isinstance(it,TemplateGraph): return save_current()
            path,_=QFileDialog.getSaveFileName(w,'Export figure',it.sample+'.png','PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;TIFF (*.tiff)')
            if path:
                try: self.tp.api.export(it.fig,path,dpi=600); w.set_status('Figure exported: '+path)
                except Exception as e: w.set_status('Export failed: '+str(e))
        w.save_current=export_current
        close_event=w.closeEvent
        def closed(event): self.save_open_projects(); return close_event(event)
        w.closeEvent=closed
        # A template graph must never be silently merged by automatic graph grouping.
        old_regroup=w.regroup
        def regroup():
            singles=w.singles; w.singles=[i for i in singles if not isinstance(i,TemplateGraph)]
            try: result=old_regroup()
            finally: w.singles=singles
            by_key={sp.key_of(i):i for i in singles}
            for how,keys in w.user_groups:
                members=[by_key[key] for key in keys if key in by_key]
                if len(members)<2 or not any(isinstance(i,TemplateGraph) for i in members): continue
                try:
                    group=sp.Combined(members,how,'Arranged explicitly in Workspace','',None,w.opt)
                    group.fmt=getattr(w,'group_fmt',{}).get(tuple(keys)) or {}; group.build(); group.mine=True
                    w.combined.insert(0,group)
                except Exception as e: result.append('Could not arrange selected graphs: '+str(e))
            return result
        w.regroup=regroup
        original_save=w.save
        w.save=lambda: self.save_project(self.active_project) if self.active_project else original_save()

    def _install_actions(self):
        w=self.ws
        from PySide6.QtWidgets import QPushButton
        self.graph_edit=QPushButton('Edit this graph…'); self.graph_edit.setToolTip('Independent panel zoom, markers, difference and Bragg rows')
        self.graph_edit.clicked.connect(self.edit_graph)
        # Visible beside the current graph, rather than global graph configuration.
        layout=w.gtitle.parentWidget().layout()
        if layout: layout.insertWidget(1,self.graph_edit)
        w.list.currentRowChanged.connect(lambda *_: self.graph_edit.setEnabled(w.current() is not None))
        self.graph_edit.setEnabled(False)
        sh=w.pages.widget(6)
        fm=w.file_btn.menu()
        fm.addAction('Open portable project…',sh.import_project)
        fm.addAction('Export portable project…',sh.export_project); fm.addAction('Close active project',sh.close_project)
        # All entry points share project-aware imports.
        w.add_files=lambda: sh.add_files()
        w.dropEvent=lambda event: sh.dropEvent(event)

    def edit_graph(self):
        it=self.ws.current()
        if isinstance(it,TemplateGraph):
            from workspace_graph_editor import GraphEditor
            return GraphEditor(self,it).exec()
        if it is not None:
            from workspace_ribbon import EditDialog
            return self.ws.ribbon.edit_dialog(it)

    def _install_header(self):
        from workspace_design import install_header
        install_header(self.ws,self)


def install(ws):
    controller=Workbench(ws); ws.workbench=controller
    from workspace_design import install_tooltips
    install_tooltips(ws); return controller

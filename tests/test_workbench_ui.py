"""Real-widget integration checks. Run with PySide6 and QT_QPA_PLATFORM=offscreen."""
import os,sys,tempfile,time,unittest
from pathlib import Path
TMP=Path(tempfile.mkdtemp(prefix='ops-workbench-'))
os.environ['OPS_NO_OPEN']='1';os.environ['OPS_SETTINGS_FILE']=str(TMP/'settings.json');os.environ['OPS_PRIVATE_DIR']=str(TMP/'private')
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'origin_plot_app'))
import numpy as np,pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import workspace_qt as W
import workspace_projects as WP
from workspace_workbench import TemplateGraph
app=QApplication.instance() or QApplication([]);app.setStyle('Fusion');app.setStyleSheet(W.STYLE)


def pump(condition=lambda:False,timeout=.2):
    start=time.time()
    while time.time()-start<timeout:
        app.processEvents()
        if condition(): return
        time.sleep(.005)


class WorkbenchIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws=W.Workspace([]);cls.ws.resize(1600,1000);cls.ws.go(6);cls.ws.show();pump(timeout=.3)
        cls.c=cls.ws.workbench;cls.sh=cls.ws.pages.widget(6)
        x=np.linspace(5,80,800);y=100+900*np.exp(-(x-29.4)**2/.2)+500*np.exp(-(x-47)**2/.1)
        cls.paths=[]
        for i in range(3):
            p=TMP/f'sample_{i+1}.csv';pd.DataFrame({'2θ (°)':x,'Intensity (counts)':y*(1+i*.1)}).to_csv(p,index=False);cls.paths.append(str(p))
        fit=TMP/'fit.csv';pd.DataFrame({'2θ (°)':x,'Yobs':y,'Ycalc':y*.98}).to_csv(fit,index=False);cls.fit=str(fit)
        cls.slug=WP.create('Hydration study',cls.paths+[cls.fit]);cls.folder=WP.add_folder(cls.slug,'XRD scans')
        WP.add_files(cls.slug,cls.paths,cls.folder);cls.c.active_project=cls.slug;cls.sh._current_project=cls.slug
    @classmethod
    def tearDownClass(cls):
        cls.ws.close();pump(timeout=.1)
    def test_01_open_selected_files(self):
        self.c.open_inputs([(self.slug,p) for p in self.paths[:2]])
        pump(lambda:not self.c._opening and self.ws.thread is None,30)
        self.assertFalse(self.c._opening)
        self.assertEqual({i.path for i in self.ws.singles},set(self.paths[:2]))
        self.assertTrue(all(i.project_id==self.slug for i in self.ws.singles))
    def test_02_recommendations_from_catalogue(self):
        self.sh._current_path=self.paths[0];self.sh.refresh();pump(timeout=.3);self.sh.inspect_current()
        rows=self.c.recommendations(self.paths[:1]);good=[r for r in rows if r['compatible']]
        self.assertTrue(good);self.assertEqual(good[0]['id'],'xrd_single_labeled')
        self.assertTrue(all(r['id'] in {x['id'] for x in self.ws.templates_page.catalogue} for r in rows))
        self.assertTrue(any(not r['compatible'] and 'two' in r['reason'] for r in rows))
        self.assertIn('XRD',self.sh.detect.text())
    def test_03_independent_graphs_and_workspace(self):
        graphs=self.c.create_graphs(self.paths[:2],'xrd_single_labeled',False)
        self.assertEqual(len(graphs),2);self.assertIsNot(graphs[0].combo,graphs[1].combo)
        self.assertEqual(self.ws.pages.currentIndex(),0);self.assertIs(self.ws.current(),graphs[0])
        graphs[0].combo['switches']['markers']=True;graphs[0].build()
        self.assertFalse(graphs[1].combo['switches']['markers'])
        self.ws.list.setCurrentRow(self.ws.items.index(graphs[1]));pump(timeout=.1)
        self.assertIs(self.ws.canvas.figure,graphs[1].fig)
    def test_04_workbook_edit_preserves_source(self):
        before=Path(self.paths[0]).read_bytes();self.c.workbook.set_paths(self.paths[:2])
        model=self.c.workbook.model;self.assertIsNotNone(model)
        self.assertTrue(model.setData(model.index(0,1),'4321'))
        pump(timeout=.2)
        self.assertEqual(float(self.c.table_for(self.paths[0]).df.iloc[0,1]),4321)
        self.assertEqual(Path(self.paths[0]).read_bytes(),before)
        model.undo_edit();self.assertNotEqual(float(model.df.iloc[0,1]),4321);model.redo_edit()
        self.assertEqual(float(model.df.iloc[0,1]),4321)
    def test_05_saved_project_restores_graphs_and_edits(self):
        self.c.save_project(self.slug);saved=WP.get(self.slug)
        self.assertEqual(len(saved['state']['templates']),2)
        self.c.close_project(self.slug);self.assertFalse(any(getattr(i,'project_id',None)==self.slug for i in self.ws.singles))
        self.c.open_inputs([(self.slug,p) for p in self.paths[:2]])
        pump(lambda:not self.c._opening and self.ws.thread is None,30)
        graphs=[i for i in self.ws.singles if isinstance(i,TemplateGraph)]
        self.assertEqual(len(graphs),2);self.assertTrue(graphs[0].combo['switches']['markers'])
        self.assertFalse(graphs[1].combo['switches']['markers'])
        self.assertEqual(float(self.c.table_for(self.paths[0]).df.iloc[0,1]),4321)
    def test_06_export_and_import_project(self):
        self.c.save_project(self.slug);dest=TMP/'study.opsproject';WP.export_project(self.slug,dest)
        new=WP.import_project(dest);project=WP.get(new)
        self.assertNotEqual(new,self.slug);self.assertTrue(all(Path(f).is_file() for f in project['files']))
        self.assertEqual(len(project['folders']),1)
        for combo in project['state']['templates']:
            self.assertIn(combo['files'][0],project['files'])
    def test_07_fit_components_and_editor(self):
        self.c.active_project=self.slug
        graphs=self.c.create_graphs([self.fit],'rietveld_fit_diff_ticks',False)
        self.assertTrue(graphs)
        graph=graphs[0]
        from workspace_graph_editor import GraphEditor
        editor=GraphEditor(self.c,graph);editor.show();pump(timeout=.1)
        editor.difference.setChecked(False);editor.zoom.setChecked(False);pump(timeout=.1)
        self.assertEqual(len(graph.fig.axes),1)
        self.assertFalse(graph.combo['switches']['markers'])
        self.assertTrue(all(l.get_marker() in ('None',None,'') for l in graph.fig.axes[0].lines))
        editor.close();pump(timeout=.1)
    def test_08_folder_and_file_selections(self):
        self.sh.refresh_projects();node=self.sh._select_node(('folder',self.slug,self.folder));node.setCheckState(0,Qt.Checked)
        self.assertEqual({p for s,p in self.sh.selected_inputs()},set(self.paths))
        node.setCheckState(0,Qt.Unchecked)
    def test_09_empty_state(self):
        self.sh._current_path=None;self.sh._current_project=None;self.sh.inspect_current()
        self.assertFalse(self.sh.b_auto.isEnabled())
    def test_10_imported_project_restores_independent_data(self):
        self.c.save_project(self.slug);dest=TMP/'restored.opsproject';WP.export_project(self.slug,dest)
        new=WP.import_project(dest);project=WP.get(new)
        self.assertTrue(all(c['project_id']==new for c in project['state']['templates']))
        original=self.paths[0]; imported=next(p for p in project['files'] if Path(p).name==Path(original).name)
        self.c.open_inputs([(new,imported)])
        pump(lambda:not self.c._opening and self.ws.thread is None,30)
        self.assertEqual(float(self.c.table_for(imported,new).df.iloc[0,1]),4321)
        self.assertTrue(any(isinstance(i,TemplateGraph) and i.project_id==new for i in self.ws.singles))
        self.c.close_project(new)
        self.c.active_project=self.slug
    def test_11_session_preserves_template_graphs(self):
        dest=TMP/'session.json'; self.ws.save_session(str(dest))
        count=sum(isinstance(i,TemplateGraph) for i in self.ws.singles)
        self.assertGreater(count,0);self.ws.open_session(str(dest))
        self.assertEqual(sum(isinstance(i,TemplateGraph) for i in self.ws.singles),count)
    def test_12_resize(self):
        from PySide6.QtWidgets import QWidget
        self.ws.go(6);self.ws.resize(1200,850);pump(timeout=.2)
        self.assertLessEqual(QWidget.width(self.ws),1250)
        self.assertFalse(self.ws.cmd.isVisible())
        self.ws.resize(1600,1000);pump(timeout=.1)
    def test_13_analysis_reads_created_graph_curves(self):
        graph=next(i for i in self.ws.singles if isinstance(i,TemplateGraph))
        curves=self.ws.curves(graph);self.assertTrue(curves)
        self.assertGreater(len(curves[0].x),100)
    def test_14_sheets_keep_independent_mapping(self):
        file=TMP/'mixed.xlsx'
        with pd.ExcelWriter(file) as out:
            pd.DataFrame({'2θ (°)':np.linspace(5,80,600),'Intensity':np.ones(600)}).to_excel(out,sheet_name='XRD',index=False)
            pd.DataFrame({'Temperature':np.linspace(30,900,600),'Mass (%)':np.linspace(100,80,600)}).to_excel(out,sheet_name='TGA',index=False)
        slug=WP.create('Mixed workbook',[str(file)]);self.c.active_project=slug
        self.c.set_mapping(str(file),'2θ (°)','Intensity',0,'XRD')
        self.c.settings_for(str(file),slug)['sheet']='TGA'
        table=self.c.table_for(str(file),slug)
        from opstudio.detection import detect
        self.assertEqual(detect(table,getattr(table,'measurement_type',None)).kind,'TGA')
        self.c.active_project=self.slug
    def test_15_ui_screenshot(self):
        self.c.active_project=self.slug;self.sh._current_project=self.slug;self.sh._current_path=self.paths[0]
        self.ws.go(6);self.sh.refresh_projects();self.sh._select_node(('file',self.slug,self.paths[0]));self.sh.inspect_current();pump(timeout=.3)
        out=os.environ.get('OPS_TEST_SCREENSHOT')
        if out: self.assertTrue(self.ws.grab().save(out))
        self.assertEqual(self.ws.pages.count(),8)


if __name__=='__main__':unittest.main(verbosity=2)

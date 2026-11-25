"""Scientific detection, input validation, graph components, merges and project archives.
Run: python tests/test_workbench_core.py (no Qt dependency).
"""
import copy,io,json,os,sys,tempfile,types,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
os.environ['MPLBACKEND']='Agg'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'origin_plot_app'))
import numpy as np,pandas as pd
import smart_plots as sp
from opstudio import api,core,data
from opstudio.detection import detect,normalise
from opstudio.origin import read_figure
from workbook_data import merge_tables
import workspace_projects as WP


def scan(name='sample',header='2θ (°)',n=800):
    x=np.linspace(5,80,n);y=100+800*np.exp(-(x-29.4)**2/.1)
    return data.Table(name,pd.DataFrame({header:x,'Intensity (counts)':y}))


def fit(name='sample'):
    t=scan(name);df=t.df.copy();df.columns=['2θ (°)','Yobs'];df['Ycalc']=df['Yobs']*.99
    return data.Table(name,df)


class FitMappingTests(unittest.TestCase):
    """A pattern-and-fit export read by the names of its columns, not their position (an instrument export with a
    leading row number and a background column must not have its curves shifted by one)."""
    def export(self):
        x=np.linspace(5,80,400);obs=100+800*np.exp(-(x-29.4)**2/.1);calc=obs*.98;back=np.full_like(x,95.)
        return data.Table('fit',pd.DataFrame({'No.':np.arange(1,401),'Pos. [°2Th.]':x,'Iobs [cts]':obs,'Icalc [cts]':calc,'Iback [cts]':back,'d-spacing [Å]':1.5406/(2*np.sin(np.radians(x/2)))})),x,obs,calc,back
    def test_named_columns_win_over_position(self):
        t,x,obs,calc,back=self.export();tp=api.resolve('rietveld_fit_diff_ticks')[0]
        b,mp=data.bundle(tp,[t]);m=dict(mp)
        np.testing.assert_allclose(b['x'],x);np.testing.assert_allclose(b['obs'],obs);np.testing.assert_allclose(b['calc'],calc)
        np.testing.assert_allclose(b['diff'],obs-calc);np.testing.assert_allclose(b['background'],back)
        self.assertEqual((m['x'],m['observed'],m['calculated'],m['background']),('Pos. [°2Th.]','Iobs [cts]','Icalc [cts]','Iback [cts]'))
        self.assertIn('observed - calculated',m['difference'])
    def test_unnamed_columns_keep_their_order(self):
        x=np.linspace(5,80,50);t=data.Table('f',pd.DataFrame({'x':x,'a':x*2,'b':x*3,'c':x*.1}))
        b,_mp=data.bundle(api.resolve('rietveld_fit_diff_ticks')[0],[t])
        np.testing.assert_allclose(b['obs'],x*2);np.testing.assert_allclose(b['calc'],x*3);np.testing.assert_allclose(b['diff'],x*.1)
    def test_background_drawn_only_when_switched_on(self):
        t=self.export()[0]
        labels=lambda sw:[l.get_label() for a in api.draw('rietveld_fit_diff_ticks',[t],switches=sw)[0].axes for l in a.lines]
        self.assertNotIn('Background',labels({}));self.assertIn('Background',labels({'show_background':True}))
    def test_fit_table_is_a_fit_not_a_stack(self):
        from opstudio.detection import compatibility,xrd_form
        t=self.export()[0];d=detect(t);self.assertEqual((d.kind,d.confidence,d.form),('XRD','high','fit'))
        ranked=api.recommend([t]);self.assertEqual(ranked[0][0],'rietveld_fit_diff_ticks')
        ok,why=compatibility(api.resolve('xrd_stacked_offset')[0],[t],d);self.assertFalse(ok);self.assertIn('one fit',why)
        self.assertEqual(xrd_form(scan()),'scan')
    def test_peak_list_is_not_a_scan(self):
        from opstudio.detection import compatibility
        t=data.Table('peaks',pd.DataFrame({'No.':[1,2,3,4],'Pos. [°2Th.]':[18.1,29.4,34.2,47.1],'FWHM Left [°2Th.]':[.1,.12,.11,.15],'Area [cts*°2Th.]':[50,400,120,90.],'Source':['a','b','a','b']}))
        d=detect(t);self.assertEqual((d.kind,d.form),('XRD','peak list'));self.assertFalse(d.needs_confirmation)
        ids={r[0] for r in api.recommend([t])};self.assertIn('scientific_line',ids);self.assertNotIn('sankey_mass_energy',ids)
        for tid in ('xrd_single_labeled','xrd_stack_with_zoom','xrd_peak_shift'):
            ok,why=compatibility(api.resolve(tid)[0],[t],d);self.assertFalse(ok,tid);self.assertIn('peak list',why)
    def test_every_catalogue_class_can_be_chosen(self):
        from opstudio.detection import KINDS,CATEGORY_KINDS,family_matches
        classes={api.resolve(r['id'])[0].category for r in api.all_templates()}
        self.assertTrue(set(CATEGORY_KINDS.values())<=classes)                       # the kinds name real classes of the installed catalogue
        reach={c for c in classes if c in ('Basic 2D & layout','General scientific & statistics')}
        for row in api.all_templates():
            tp=api.resolve(row['id'])[0]
            if any(family_matches(tp,k) for k in KINDS if k not in ('Unknown','Category table','General XY') and tp.id!='scientific_line'): reach.add(tp.category)
        self.assertEqual(classes-reach,set())
    def test_other_kinds_from_their_headers(self):
        T=np.linspace(600,1450,40)
        thermo=data.Table('t',pd.DataFrame({'Temperature (°C)':T,'Liquid (wt.%)':T*0+5,'Alite C3S (wt.%)':T*0+60,'Belite C2S (wt.%)':T*0+20}))
        d=detect(thermo);self.assertEqual(d.kind,'Thermodynamic modelling');self.assertTrue(d.needs_confirmation);self.assertEqual(api.recommend([thermo]),[])
        thermo.measurement_type='Thermodynamic modelling';self.assertTrue(all(api.resolve(r[0])[0].category=='Thermodynamic modelling' or r[0]=='scientific_line' for r in api.recommend([thermo])))
        nmr=data.Table('n',pd.DataFrame({'Chemical shift (ppm)':np.linspace(-60,-120,50),'Intensity (a.u.)':np.ones(50)}));self.assertEqual(detect(nmr).kind,'NMR')
        mip=data.Table('m',pd.DataFrame({'Pore diameter (nm)':np.logspace(0,5,50),'Cumulative intrusion (mL/g)':np.linspace(.2,0,50)}));self.assertEqual(detect(mip).kind,'Porosity and surface')
    def test_no_table_is_said_in_words(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'words.txt';p.write_text('no table here\njust words\n',encoding='utf-8')
            with self.assertRaises(data.NeedData) as e: data.read_tables(str(p))
            self.assertIn('no rows of numbers',str(e.exception))
    def test_template_example_is_made_once_and_not_shared(self):
        tp=api.resolve('xrd_stacked_offset')[0];a=data._example(tp);b=data._example(tp)
        self.assertIsNot(a,b);self.assertEqual(list(a),list(b))
        first=next(v for v in a.values() if isinstance(v,(list,dict)));first.clear()
        self.assertTrue(next(v for v in data._example(tp).values() if isinstance(v,(list,dict))))    # changing a copy does not change the kept example


class WorkbookCacheTests(unittest.TestCase):
    """A workbook is parsed once per version of the file, however many parts of the app ask for its sheets."""
    def test_one_parse_copies_and_reparse_on_change(self):
        import workbook_cache, paper_figures as pf, auto_recipe as AR
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/'book.xlsx')
            with pd.ExcelWriter(p) as w:
                pd.DataFrame({'x':[1,2,3],'y':[4,5,6]}).to_excel(w,sheet_name='Data',index=False)
                pd.DataFrame({'a':[1.0]}).to_excel(w,sheet_name='Other',index=False)
            workbook_cache.forget(); calls=[]; real=pd.read_excel
            def counting(*a,**k): calls.append(a); return real(*a,**k)
            with patch.object(pd,'read_excel',counting):
                one=pf.load_sheets(p); two=AR.load(p); three=pf.load_sheets(p); tabs=data.read_tables(p)
                self.assertEqual(len(calls),1)                                    # four readers, one parse
                self.assertEqual(list(one),['Data','Other']);self.assertEqual(tabs[0].df.shape,(3,2))
                one['Data'].iloc[0,0]=999;one['Data'].columns=['p','q']             # what one reader does to its sheets ...
                self.assertEqual(list(pf.load_sheets(p)['Data'].columns),['x','y']) # ... reaches no other
                self.assertEqual(int(pf.load_sheets(p)['Data'].iloc[0,0]),1)
                with pd.ExcelWriter(p) as w: pd.DataFrame({'x':[7,8],'y':[9,10],'z':[0,0]}).to_excel(w,sheet_name='Data',index=False)
                os.utime(p,ns=(os.stat(p).st_atime_ns,os.stat(p).st_mtime_ns+5_000_000_000))
                self.assertEqual(list(pf.load_sheets(p)['Data'].columns),['x','y','z'])   # the file changed: read again
                self.assertEqual(len(calls),2)


class DetectionTests(unittest.TestCase):
    def test_unicode_and_header_variations(self):
        for header in ['2θ (°)','2Theta','2-theta (deg)','Two theta','2ϑ']:
            with self.subTest(header=header):
                t=scan(header=header);self.assertEqual(detect(t).kind,'XRD')
                self.assertEqual(sp.detect('s',t.df,{})['kind'],'XRD')
    def test_numeric_scan_requires_confirmation(self):
        t=scan();t.df.columns=['x','y'];t=data.Table('unnamed',t.df)
        self.assertTrue(detect(t).needs_confirmation);self.assertEqual(api.recommend([t]),[])
        t.measurement_type='XRD';self.assertTrue(api.recommend([t]))
    def test_other_measurements(self):
        cases=[('FTIR',{'Wavenumber (cm⁻¹)':[4000,3000,2000],'Absorbance':[.1,.2,.3]}),
               ('Raman',{'Raman shift (cm-1)':[100,200,300],'Intensity':[3,4,5]}),
               ('TGA',{'Temperature (°C)':[30,100,500],'Mass (%)':[100,95,90]}),
               ('DSC',{'Temperature (°C)':[30,100,500],'Heat flow (mW)':[1,2,3]}),
               ('Calorimetry',{'Time (h)':[0,1,2],'Heat flow (mW/g)':[1,2,1]}),
               ('Particle size',{'Diameter (µm)':[1,2,3],'Volume (%)':[10,50,90]}),
               ('Rheology',{'Shear rate (1/s)':[1,2,3],'Viscosity':[3,2,1]}),
               ('Strength',{'Age (days)':[1,7,28],'Strength (MPa)':[10,20,40]})]
        for kind,frame in cases:
            with self.subTest(kind=kind):self.assertEqual(detect(data.Table(kind,pd.DataFrame(frame))).kind,kind)
    def test_unrelated_values_not_xrd(self):
        table=data.Table('data',pd.DataFrame({'x':[1,2,3,4],'y':[4,2,5,1]}))
        self.assertEqual(detect(table).kind,'General XY')
    def test_no_extension_guess(self):
        t=data.Table('xrd_scan.csv',pd.DataFrame({'Temperature':[30,60,90],'Mass (%)':[100,99,90]}))
        self.assertEqual(detect(t).kind,'TGA')
    def test_explicit_type_wins(self):self.assertEqual(detect(scan(),'FTIR').kind,'FTIR')
    def test_recommend_simple_xrd_first(self):
        self.assertEqual(api.recommend([scan()],top=1)[0][0],'xrd_single_labeled')
    def test_multiple_input_requirements(self):
        single={t[0] for t in api.recommend([scan()])};multiple={t[0] for t in api.recommend([scan('a'),scan('b')])}
        self.assertNotIn('xrd_stacked_offset',single);self.assertIn('xrd_stacked_offset',multiple)
        self.assertNotIn('williamson_hall',single);self.assertNotIn('lattice_param_vs_x',single)
    def test_multiple_raw_scans_are_not_a_fit(self):
        table=scan();table.df['Second intensity']=table.df.iloc[:,1]*.8;table=data.Table('multiple',table.df)
        ids={r[0] for r in api.recommend([table])}
        self.assertNotIn('rietveld_fit_diff_ticks',ids)
        self.assertNotIn('xrd_heatmap_contour',ids)
    def test_ftir_has_safe_single_spectrum_template(self):
        table=data.Table('FTIR',pd.DataFrame({'Wavenumber (cm-1)':[4000,3000,2000,1000],'Absorbance':[.1,.2,.3,.4]}))
        ids={r[0] for r in api.recommend([table])};self.assertIn('scientific_line',ids)
        self.assertFalse(any('nmr' in tid for tid in ids))
    def test_private_template_in_recommendations(self):
        with tempfile.TemporaryDirectory() as d:
            old=list(api.USER_DIRS)
            try:
                api.save_user_template(d,'my_scan','My scan','xrd_single_labeled')
                self.assertIn('my_scan',{r[0] for r in api.recommend([scan()])})
            finally:api.USER_DIRS[:]=old
    def test_read_formats_keep_first_numeric_row(self):
        with tempfile.TemporaryDirectory() as d:
            for ext,sep in [('csv',','),('tsv','\t'),('xy',' ')]:
                with self.subTest(ext=ext):
                    p=Path(d)/('scan.'+ext);np.savetxt(p,np.array([[5,100],[6,200],[7,150]]),delimiter=sep)
                    t=data.read_tables(str(p))[0];self.assertEqual(len(t.df),3);self.assertEqual(float(t.df.iloc[0,0]),5)
    def test_excel_multiple_sheets(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'mixed.xlsx'
            with pd.ExcelWriter(p) as out:
                scan().df.to_excel(out,sheet_name='Data',index=False)
                pd.DataFrame({'Notes':['example']}).to_excel(out,sheet_name='Guide',index=False)
            t=data.read_tables(str(p))[0];self.assertEqual(detect(t).kind,'XRD')


class ComponentTests(unittest.TestCase):
    def test_line_only_and_no_difference(self):
        f,_=api.draw('rietveld_fit_diff_ticks',[fit()],switches={'markers':False,'show_difference':False,'inset':False})
        self.assertEqual(len(f.axes),1)
        self.assertTrue(all(l.get_marker() in ('None',None,'') for l in f.axes[0].lines))
        self.assertEqual({str(l.get_label()):l.get_linestyle() for l in f.axes[0].lines},{'Observed':'-','Calculated':'--'})    # a solid line and a dashed one: both seen
    def test_every_fit_graph_has_observed_solid_and_calculated_dashed(self):
        look=lambda fig:{str(l.get_label()):(l.get_linestyle(),l.get_marker() not in ('None',None,'')) for a in fig.axes for l in a.lines if str(l.get_label()) in ('Observed','Calculated','Fit','Yobs','Ycalc')}
        want={'Observed':('-',False),'Calculated':('--',False)}
        self.assertEqual(look(api.draw('rietveld_fit_diff_ticks',[fit()])[0]),want)                      # Analysis template, no switches given
        self.assertEqual(look(api.demo_figure('rietveld_grid_2x3')),want)
        self.assertEqual(look(api.demo_figure('nmr_29si_deconv')),{'Observed':('-',False),'Fit':('--',False)})
        dotted=look(api.draw('rietveld_fit_diff_ticks',[fit()],switches={'observed_markers':True})[0])
        self.assertEqual(dotted,{'Observed':('None',True),'Calculated':('-',False)})                      # dots when asked for: then the calculated line is solid
        import gallery_graphs as TG
        self.assertEqual(look(TG.figure('G03',TG.read_book(str(ROOT/'tests'/'gallery_templates'/'G03_RIETVELD_FIT.xlsx')))[0]),want)
        t=fit();cs=[sp.curve('Observed',t.arr(t.x),t.arr('Yobs'),(0,0,0)),sp.curve('Calculated',t.arr(t.x),t.arr('Ycalc'),(224,0,0),dash=True)]
        self.assertNotIn('dash',cs[0]);self.assertTrue(cs[1]['dash'])
        fig=sp.preview_figure(sp.finish(dict(title='f',xname='2θ',panels=[sp.panel('Counts',cs)])))
        self.assertEqual(look(fig),want)                                                                  # the app's own Fit view
    def test_independent_panels(self):
        sw={'markers':False,'inset':True,'panel_options':{'0':{'inset':False,'show_difference':False},'1':{'markers':True}}}
        f,_=api.draw('rietveld_grid_2x3',[fit('a'),fit('b')],switches=sw)
        mains=[a for a in f.axes if getattr(a,'_ops_role','')=='main']
        self.assertEqual(len(mains),2);self.assertEqual(len(mains[0].child_axes),0);self.assertEqual(len(mains[1].child_axes),1)
        self.assertEqual(mains[0].lines[0].get_marker(),'None');self.assertEqual(mains[1].lines[0].get_marker(),'o')
        self.assertFalse(any(getattr(a,'_ops_panel',None)==0 and getattr(a,'_ops_role','')=='difference' for a in f.axes))
        self.assertTrue(any(getattr(a,'_ops_panel',None)==1 and getattr(a,'_ops_role','')=='difference' for a in f.axes))
    def test_input_not_mutated(self):
        t=fit();before=t.df.copy(deep=True)
        api.draw('rietveld_fit_diff_ticks',[t],switches={'markers':False,'show_difference':False})
        pd.testing.assert_frame_equal(t.df,before)
    def test_origin_reads_visible_components_only(self):
        f,_=api.draw('rietveld_fit_diff_ticks',[fit()],switches={'markers':False,'show_difference':False,'inset':False})
        result=read_figure(f);self.assertEqual(len(result['layers']),1)
        self.assertEqual(len(result['layers'][0]['curves']),2)
    def test_graph_switches_independent(self):
        a,_=api.draw('rietveld_fit_diff_ticks',[fit()],switches={'markers':False,'inset':False})
        b,_=api.draw('rietveld_fit_diff_ticks',[fit()],switches={'markers':True,'inset':True})
        self.assertEqual(a.axes[0].lines[0].get_marker(),'None');self.assertEqual(b.axes[0].lines[0].get_marker(),'o')
    def test_measured_and_fitted_markers_independent(self):
        f,_=api.draw('rietveld_fit_diff_ticks',[fit()],switches={'markers':False,'observed_markers':True,'fitted_markers':False,'inset':False})
        self.assertEqual(f.axes[0].lines[0].get_marker(),'o')
        self.assertEqual(f.axes[0].lines[1].get_marker(),'None')
    def test_existing_sample_page_independent_zoom(self):
        table=fit();item=sp.Item('sample.csv',sp.detect('sample',table.df,{}),[]).build({'inset':'On every XRD pattern and fit'})
        page=sp.SamplePage(item,{'inset':'On every XRD pattern and fit'}).build()
        page.fmt={'native_panels':{'0':{'inset':False},'1':{'inset':True,'show_difference':False}}};page.build()
        self.assertFalse(page.spec['cols'][0]['panels'][0].get('inset'))
        self.assertTrue(page.spec['cols'][1]['panels'][0].get('inset'))
        self.assertNotIn('Difference',[c['label'] for p in page.spec['cols'][1]['panels'] for c in p['curves']])
        sp.preview_figure(page.spec).canvas.draw()
    def test_composed_figures_use_working_data(self):
        x=np.arange(5.)
        figure={'name':'Working figure','width_mm':175,'height_mm':100,
                'panels':[{'type':'xy','cell':[0,0],'series':[{'sheet':'Data','x':'X','y':'Y'}]}]}
        det={'name':'Figure','kind':sp.COMPOSED_KIND,'_composed':('unavailable.xlsx',{},figure)}
        item=sp.Item('unavailable.xlsx',det,[])
        item._working_sheets={'Data':pd.DataFrame({'X':x,'Y':x*3})};item.build()
        fig=sp.composed_draw(item.spec)
        np.testing.assert_array_equal(fig.axes[0].lines[0].get_ydata(),x*3)
    def test_export_svg(self):
        f,_=api.draw('rietveld_fit_diff_ticks',[fit()],switches={'markers':False,'inset':False})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'graph.svg';api.export(f,str(p));self.assertGreater(p.stat().st_size,1000)


class MergeTests(unittest.TestCase):
    def test_append_rows_and_source(self):
        a=scan('a',n=20);b=scan('b',n=20);out=merge_tables([('a.csv',a),('b.csv',b)],0)
        self.assertEqual(len(out),40);self.assertEqual(list(out['Source file'].unique()),['a.csv','b.csv'])
    def test_append_rejects_mismatched_columns(self):
        with self.assertRaises(ValueError):merge_tables([('a',scan()),('b',fit())],0)
    def test_join_columns_without_interpolation(self):
        out=merge_tables([('a.csv',scan('a')),('b.csv',scan('b'))],1)
        self.assertEqual(out.shape,(800,3));self.assertEqual(len(set(out.columns)),3)
    def test_join_rejects_misaligned_x(self):
        with self.assertRaises(ValueError):merge_tables([('a',scan(n=800)),('b',scan(n=799))],1)
    def test_join_rejects_duplicate_x(self):
        t=scan();t.df.iloc[1,0]=t.df.iloc[0,0];t=data.Table('b',t.df)
        with self.assertRaises(ValueError):merge_tables([('a',scan()),('b',t)],1)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.store={}
        self.stub=types.ModuleType('workspace_qt');self.stub.load_cfg=lambda:copy.deepcopy(self.store)
        def save(changes):self.store.update(copy.deepcopy(changes));return True
        self.stub.save_cfg=save;self.stub.cfg_path=lambda:self.root/'settings.json'
        self.patch=patch.dict(sys.modules,{'workspace_qt':self.stub});self.patch.start();self.addCleanup(self.patch.stop)
        self.file=self.root/'scan.csv';scan(n=100).df.to_csv(self.file,index=False)
        self.slug=WP.create('Project',[str(self.file)])
    def test_folder_move_and_order(self):
        a=WP.add_folder(self.slug,'A');b=WP.add_folder(self.slug,'B',a)
        WP.add_files(self.slug,[str(self.file)],b);self.assertEqual(WP.folder_files(self.slug,a),[str(self.file)])
        with self.assertRaises(ValueError):WP.move_folder(self.slug,a,b)
        WP.remove_folder(self.slug,a);self.assertEqual(WP.get(self.slug)['files'],[str(self.file)])
        self.assertTrue(self.file.exists())
    def test_dedup_in_same_batch(self):
        WP.add_files(self.slug,[str(self.file)]*3);self.assertEqual(len(WP.get(self.slug)['files']),1)
    def test_v1_migration(self):
        self.store['projects']={'legacy':{'name':'Legacy','files':[str(self.file)]}}
        p=WP.get('legacy');self.assertEqual(p['folders'],[]);self.assertEqual(p['state'],{})
    def test_archive_round_trip(self):
        f=WP.add_folder(self.slug,'Scans');WP.add_files(self.slug,[str(self.file)],f)
        WP.save_state(self.slug,{'templates':[{'files':[str(self.file)],'switches':{'markers':False}}]})
        dest=self.root/'p.opsproject';WP.export_project(self.slug,dest)
        imported=WP.import_project(dest);p=WP.get(imported)
        self.assertNotEqual(imported,self.slug);self.assertTrue(Path(p['files'][0]).exists())
        self.assertEqual(p['state']['templates'][0]['files'][0],p['files'][0]);self.assertEqual(p['folders'][0]['id'],f)
    def test_missing_inputs_reported(self):
        self.file.unlink();self.assertEqual(WP.missing_files(self.slug),[str(self.file)])
        with self.assertRaises(ValueError):WP.export_project(self.slug,self.root/'p.opsproject')
    def test_archive_rejects_traversal(self):
        p={'schema':WP.SCHEMA,'name':'Unsafe','files':['inputs/../../escape.csv']}
        dest=self.root/'bad.opsproject'
        with zipfile.ZipFile(dest,'w') as out:out.writestr('project.json',json.dumps(p));out.writestr('inputs/../../escape.csv','data')
        with self.assertRaises(ValueError):WP.import_project(dest)
        self.assertFalse((self.root/'escape.csv').exists())
    def test_delete_keeps_original(self):
        WP.delete(self.slug);self.assertIsNone(WP.get(self.slug));self.assertTrue(self.file.is_file())
    def test_save_failure_not_reported_as_success(self):
        self.stub.save_cfg=lambda changes:False
        with self.assertRaises(OSError):WP.rename(self.slug,'Changed')


if __name__=='__main__':unittest.main(verbosity=2)

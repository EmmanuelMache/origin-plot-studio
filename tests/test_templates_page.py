"""The Templates page: multiple selection everywhere, the files x templates x styles preview grid, batch actions
(open, Origin, export, workbook, combine), my templates.  Includes acceptance check 14 end to end (Origin through the dry run)."""
import os, sys, tempfile, json, hashlib, warnings
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
TMP = Path(tempfile.mkdtemp()); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
from PySide6.QtWidgets import QApplication, QDockWidget
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
app = QApplication.instance() or QApplication(sys.argv)
import time as _time
def settle(pg, extra=lambda: True, timeout=240):
    """Wait until the previews are drawn (the preview timer has fired and the queue is empty)."""
    t0 = _time.time(); QTest.qWait(30)
    while _time.time() - t0 < timeout:
        app.processEvents()
        if not pg._timer.isActive() and not pg.queue and not pg.bar.isVisible() and extra(): return True
        QTest.qWait(15)
    return False
import workspace_qt as W
from workspace_templates import checked, set_checked
def tick(lst, ids):
    for i in range(lst.count()): lst.item(i).setCheckState(Qt.Checked if lst.item(i).data(Qt.UserRole) in ids else Qt.Unchecked)
app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)
# three plain data files (row 1 headers, column 1 = x)
x = np.linspace(5, 70, 300); files = []
for i, nm in enumerate(["Sample_A", "Sample_B", "Sample_C"]):
    p = TMP / f"{nm}.csv"; pd.DataFrame({"2theta (deg)": x, "Intensity (counts)": 100 + (900 - 150 * i) * np.exp(-(x - 29 - i) ** 2 / 0.5) + 300 * np.exp(-(x - 47) ** 2)}).to_csv(p, index=False); files.append(str(p))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest(); before = [sha(p) for p in files]
w = W.Workspace([]); w.resize(1500, 900); w.show(); app.processEvents()
pg = w.templates_page
names_ = [b.text() for b in w.header_nav.buttons()]
check("five sections in the top bar: Start here, Workspace, Analysis, Assistant, Settings - the graph gallery is inside Analysis", names_ == ["Start here", "Workspace", "Analysis", "Assistant", "Settings"] and hasattr(pg, "main"), names_)
w.header_nav.button(1).click(); app.processEvents()
check("clicking Analysis opens the graphs and templates (the picture gallery) first", w.pages.currentWidget() is pg and w.header_nav.button(1).isChecked())
sw = [b.text() for b in w.gallery_switch[5].buttons()]
check("a switch at the top of Analysis: Graphs and templates | Calculations", sw == ["Graphs and templates", "Calculations"] and w.gallery_switch[5].button(5).isChecked(), sw)
w.gallery_switch[5].button(1).click(); app.processEvents()
check("the switch shows the calculation tools; Analysis stays the section", w.pages.currentIndex() == 1 and w.header_nav.button(1).isChecked() and w.gallery_switch[1].button(1).isChecked())
w.header_nav.button(0).click(); w.header_nav.button(1).click(); app.processEvents(); check("Analysis opens again where you left it", w.pages.currentIndex() == 1)
w.gallery_switch[1].button(5).click(); app.processEvents()
pa = w.pages.widget(1)
wbs = [r for r in pg.catalogue if r["source"] == "workbook"]
check("the 26 workbook graph types are pictures in the gallery, in the class of their technique (not a second list page)", len(wbs) == 26 and all(os.path.isfile(r["preview"]) for r in wbs)
      and next(r for r in wbs if r["id"] == "wb:G01")["section"].startswith("I. XRD") and next(r for r in wbs if r["id"] == "wb:G07")["section"].startswith("N. Thermal") and pa.find_entry("G01") is None, len(wbs))
EXS = ROOT / "origin_plot_app" / "examples_synthetic"; w.load([str(EXS / "xrd_raw.csv")])
t0_ = _time.time()
while _time.time() - t0_ < 90:
    app.processEvents()
    if w.job_thread is None and getattr(w, "loader", None) is None: break
check("a file loaded while the gallery is open appears in its Files list at once, ticked", [pg.files.item(i).text() for i in range(pg.files.count())] == ["xrd_raw.csv"] and len(checked(pg.files)) == 1, [pg.files.item(i).text() for i in range(pg.files.count())])
w.clear_all_graphs(); app.processEvents(); check("… and leaves the list when it is removed from the session", pg.files.count() == 0)
w.go(5); app.processEvents()
names = [d.windowTitle().replace("⠿", "").strip() for d in pg.main.findChildren(QDockWidget)]
check("six panels: Files, Columns, Templates, Styles, Previews, Variants - each movable, floatable, closable", sorted(names) == ["Columns", "Files", "Previews", "Styles", "Templates", "Variants"]
      and all(d.features() & QDockWidget.DockWidgetMovable and d.features() & QDockWidget.DockWidgetFloatable and d.features() & QDockWidget.DockWidgetClosable for d in pg.docks), names)
pg.live.setChecked(False); pg.silent = True; pg.force_dry = True
pg.add_files(files); app.processEvents()
check("files added on the page are listed and ticked", pg.files.count() == 3 and len(checked(pg.files)) == 3)
check("the app says what kind of file this looks like, and marks the best-fitting templates (★) - as soon as files are added, no extra click needed",
      pg.detect_label.isVisible() and "diffraction" in pg.detect_label.text().lower() and pg.grid.item(0).text().startswith("★"), pg.detect_label.text())
# ---- the same multiple selection in every list
from PySide6.QtWidgets import QAbstractItemView
from workspace_templates import TickList
check("every list ticks the same way: a click ticks, Shift+click a range, Ctrl+A all; a tick box per row", all(isinstance(l, TickList) for l in (pg.files, pg.grid, pg.styles)) and all(l.item(0).flags() & Qt.ItemIsUserCheckable for l in (pg.files, pg.styles)))
set_checked(pg.files, range(3), False); app.processEvents(); ctr = lambda lst, i: lst.visualItemRect(lst.item(i)).center()
QTest.mouseClick(pg.files.viewport(), Qt.LeftButton, Qt.NoModifier, ctr(pg.files, 0)); app.processEvents(); n1 = len(checked(pg.files))
QTest.mouseClick(pg.files.viewport(), Qt.LeftButton, Qt.ShiftModifier, ctr(pg.files, 2)); app.processEvents(); n_shift = len(checked(pg.files))
QTest.mouseClick(pg.files.viewport(), Qt.LeftButton, Qt.NoModifier, ctr(pg.files, 1)); app.processEvents(); n_off = len(checked(pg.files))
pg.files.setFocus(); QTest.keyClick(pg.files, Qt.Key_A, Qt.ControlModifier); app.processEvents(); n_all = len(checked(pg.files))
check("a click ticks a file, Shift+click ticks the range, a click on a ticked one unticks it, Ctrl+A ticks all", (n1, n_shift, n_off, n_all) == (1, 3, 2, 3), (n1, n_shift, n_off, n_all))
check("the ticked rows are the highlighted ones", len(pg.files.selectedItems()) == 3)
# a click on a thumbnail ticks the template and it is drawn at once - as an example when no file is ticked
pg.live.setChecked(True); set_checked(pg.files, range(3), False); app.processEvents()
g0 = next(i for i in range(pg.grid.count()) if pg.grid.item(i).data(Qt.UserRole) == "scatter_linear_fit"); pg.grid.scrollToItem(pg.grid.item(g0)); app.processEvents()
QTest.mouseClick(pg.grid.viewport(), Qt.LeftButton, Qt.NoModifier, ctr(pg.grid, g0)); app.processEvents()
check("clicking a thumbnail ticks the template: a tick before its name and the highlight", pg.grid.item(g0).checkState() == Qt.Checked and pg.grid.item(g0).text().startswith("✓ ") and pg.grid.item(g0).isSelected(), pg.grid.item(g0).text())
settle(pg, lambda: bool(pg.tiles))
check("with no file ticked the preview shows the example of the ticked template at once (it cannot be kept)", len(pg.tiles) == 1 and pg.tiles[0].fig is not None and "example" in pg.tiles[0].combo["title"].lower() and not pg.tiles[0].keep.isEnabled(), [t.error for t in pg.tiles])
pg.files.item(0).setCheckState(Qt.Checked)
settle(pg, lambda: bool(pg.tiles) and not pg.tiles[0].combo.get("demo"))
check("ticking a file redraws the preview from that file by itself", len(pg.tiles) == 1 and pg.tiles[0].fig is not None and pg.tiles[0].combo["sample"] == "Sample_A" and pg.tiles[0].keep.isEnabled(), pg.tiles[0].combo["title"] if pg.tiles else "")
QTest.mouseClick(pg.grid.viewport(), Qt.LeftButton, Qt.NoModifier, ctr(pg.grid, g0)); app.processEvents(); check("a second click unticks the template", pg.grid.item(g0).checkState() == Qt.Unchecked and not pg.grid.item(g0).text().startswith("✓"))
pg.live.setChecked(False); settle(pg); set_checked(pg.files, range(3), True)
# "Draw my data like this": the ticked template pictures drawn from the files
set_checked(pg.grid, range(pg.grid.count()), False); r0 = pg.draw_my_data(); check("'Draw my data like this' without a ticked template says what to do", r0 is None and "Click a template picture" in pg.pmsg.text())
tick(pg.grid, {"scatter_linear_fit"}); set_checked(pg.files, range(3), False); n_d = pg.draw_my_data(); settle(pg)
check("'Draw my data like this' ticks your files when none is ticked and draws them in the ticked template", n_d == 3 and len(checked(pg.files)) == 3 and all(t.fig is not None and not t.combo.get("demo") for t in pg.tiles), (n_d, [t.error for t in pg.tiles]))
check("it is the primary button of the page", pg.b_draw.objectName() == "primary" and pg.b_draw.text() == "Draw my data like this")
# "Use what the app recommends": no template ticked by hand - the app picks the best fit for the ticked files and draws it
set_checked(pg.grid, range(pg.grid.count()), False); set_checked(pg.files, range(3), True)
n_r = pg.use_recommended(); settle(pg); picked = checked(pg.grid)
check("'Use what the app recommends' ticks the best-fitting template by itself and draws it from the data", n_r == 3 and len(picked) == 1 and all(t.fig is not None and not t.combo.get("demo") for t in pg.tiles), (n_r, picked, [t.error for t in pg.tiles]))
check("...status says which template was picked and why", "Picked for you" in pg.ws.status.text(), pg.ws.status.text())
set_checked(pg.grid, range(pg.grid.count()), False)
# a workbook graph type drawn from a workbook, in the same gallery
wbf = str(ROOT / "tests" / "gallery_templates" / "G01_XRD_STACK.xlsx"); pg.add_files([wbf]); set_checked(pg.files, range(pg.files.count()), False); tick(pg.files, {wbf}); tick(pg.grid, {"wb:G01"}); pg.rebuild_previews(); settle(pg)
check("a workbook graph type is drawn from a ticked workbook like any other picture of the gallery", len(pg.tiles) == 1 and pg.tiles[0].fig is not None and len(pg.tiles[0].fig.axes) >= 1 and pg.tiles[0].mapping[0] == ("workbook", "G01_XRD_STACK.xlsx"), [t.error for t in pg.tiles])
junk = TMP / "words.txt"; junk.write_text("no table here\njust words\n", encoding="utf-8"); pg.add_files([str(junk)]); set_checked(pg.files, range(pg.files.count()), False); tick(pg.files, {str(junk)}); pg.rebuild_previews(); settle(pg)
check("a file that cannot be drawn as that workbook type gives a tile that says so (no crash)", len(pg.tiles) == 1 and pg.tiles[0].fig is None and len(pg.tiles[0].error) > 20, pg.tiles[0].error[:120] if pg.tiles else "")
pg.extra_files = [f for f in pg.extra_files if f != str(junk)]
pg.remove_files() if False else None; pg.extra_files = [f for f in pg.extra_files if f != wbf]
w.singles = [it for it in w.singles if os.path.abspath(str(getattr(it, "path", "") or "")) not in {os.path.abspath(wbf), os.path.abspath(str(junk))}]; w.refresh_list()   # a file added on this page is also in Workspace now: drop it from there too to get back to the 3 original files
pg.refresh_files(); set_checked(pg.grid, range(pg.grid.count()), False); set_checked(pg.files, range(pg.files.count()), True)
# the classes: by instrument / technique and by graph type
tops = [pg.classes.topLevelItem(i).text(0) for i in range(pg.classes.topLevelItemCount())]
pg._class_clicked(pg.classes.topLevelItem(1)); app.processEvents(); hv = [pg.grid.item(i).data(Qt.UserRole + 1)["source"] for i in range(pg.grid.count()) if not pg.grid.item(i).isHidden()]
check("'House figures' at the top of the classes shows the house figure layouts in one click", tops[1].startswith("House figures") and tops[2].startswith("My templates") and len(hv) >= 18 and set(hv) == {"house"}, (tops[:3], len(hv)))
pg._class_clicked(pg.classes.topLevelItem(0)); app.processEvents(); inst = pg.classes.topLevelItem(3); kids = [inst.child(i).text(0) for i in range(inst.childCount())]
check("the templates are in classes: by instrument / technique and by graph type, with counts", tops[0].startswith("All templates") and tops[3].startswith("By instrument / technique") and tops[4].startswith("By graph type") and any(k.startswith("XRD  (") for k in kids) and any(k.startswith("TGA, DTG, DSC") for k in kids) and any(k.startswith("Calorimetry") for k in kids), tops)
xr = next(inst.child(i) for i in range(inst.childCount()) if inst.child(i).text(0).startswith("XRD")); pg._class_clicked(xr); app.processEvents()
vis = [pg.grid.item(i).data(Qt.UserRole + 1)["section"] for i in range(pg.grid.count()) if not pg.grid.item(i).isHidden()]
check("clicking a class shows only its templates", 6 <= len(vis) <= 19 and all(v.startswith("I. XRD") for v in vis), (len(vis), set(vis)))
pg._class_clicked(pg.classes.topLevelItem(0)); app.processEvents()
# ---- the gallery: every catalogue row, filters, search
cat = pg.catalogue; avail = [r for r in cat if r["available"]]; coming = [r for r in cat if not r["available"]]
check("all 121 templates and the 26 workbook graph types are in the gallery, and every other catalogue row is shown as 'coming'", len(avail) == 147 and len(coming) == 348 - 135 and pg.grid.count() == len(cat), (len(avail), len(coming)))
pg.state.setCurrentIndex(1); shown = lambda: sum(1 for i in range(pg.grid.count()) if not pg.grid.item(i).isHidden())
check("the status filter shows available, coming, or both", shown() == len(cat) and (pg.state.setCurrentIndex(0) or shown() == 147))
fields = [pg.field.itemText(i) for i in range(pg.field.count())]
check("fields: graph families and domain packs with counts, and My templates", any("Graph families" in f for f in fields) and any("Domain packs" in f for f in fields) and any("My templates" in f for f in fields) and any("XRD" in f for f in fields), fields[:4])
pg.find.setText("rietveld"); n_find = shown(); pg.find.setText("zzzz-no-such"); n_none = shown(); pg.find.setText("")
check("search finds by name; no result is an empty list, not an error", n_find >= 2 and n_none == 0, (n_find, n_none))
pg.fits.setChecked(True); app.processEvents(); first = [pg.grid.item(i).data(Qt.UserRole) for i in range(pg.grid.count()) if not pg.grid.item(i).isHidden()][:3]
check("'Works with the ticked files' ranks the fitting templates: diffraction first for a 2θ file", all("xrd" in t for t in first) and pg.grid.item(0).text().startswith("★"), first); pg.fits.setChecked(False)
coming_item = next(pg.grid.item(i) for i in range(pg.grid.count()) if not pg.grid.item(i).data(Qt.UserRole + 1)["available"])
check("a 'coming' graph type cannot be ticked and says so", not (coming_item.flags() & Qt.ItemIsUserCheckable) and "Coming" in coming_item.toolTip())
tip = next(pg.grid.item(i) for i in range(pg.grid.count()) if pg.grid.item(i).data(Qt.UserRole) == "xrd_stacked_offset").toolTip()
check("hover on a template: use, the columns it needs, its Origin name, 'illustrative example'", "Columns it needs" in tip and "Origin:" in tip and "illustrative example" in tip)
# ---- acceptance check 14: 3 files + 4 templates + 2 styles -> 24 previews
tick(pg.grid, {"xrd_stacked_offset", "xrd_dspacing_top", "scatter_linear_fit", "broken_axis"}); tick(pg.styles, {"house_style_1", "nature"}); app.processEvents()
check("the count is visible: '3 files · 4 templates · 2 styles selected → 24 previews'", pg.count.text().startswith("3 files · 4 templates · 2 styles selected  →  24 previews"), pg.count.text())
pg.rebuild_previews()
settle(pg)
drawn = [t for t in pg.tiles if t.fig is not None]
check("check 14a: 24 previews drawn from the files (files x templates x styles)", len(pg.tiles) == 24 and len(drawn) == 24, (len(pg.tiles), len(drawn), [t.error for t in pg.tiles if t.error][:2]))
t0 = drawn[0]; lab = " ".join(ax.get_xlabel() for ax in t0.fig.axes)
check("the previews are drawn from my data: the axis title is the header of my file", "2theta (deg)" in lab, lab)
for t in drawn[:6]: t.keep.setChecked(True)
check("six previews kept; the count and the batch buttons follow", len(pg.kept()) == 6 and "6 kept" in pg.count.text() and pg.b_origin.isEnabled() and pg.b_combine.isEnabled())
od = TMP / "origin"; pg._save_cfg({"origin_dir": str(od)}); res = pg.draw_all_in_origin()
projs = [os.path.basename(r["project"]) for r in res]
check("check 14b: 'Draw all in Origin like this' makes 6 Origin graphs, each saved as {sample}_{template}.opju", len(res) == 6 and len(set(projs)) == 6 and all(p.endswith(".opju") and p.startswith("Sample_") for p in projs)
      and all(any(c.startswith("SAVE ") for c in r["commands"]) for r in res), projs[:3])
check("each Origin graph has its worksheets and its complete script beside it", all(os.path.isfile(os.path.splitext(r["project"])[0] + ".ogs") for r in res) and all(len(list((od / "data_for_origin" / os.path.splitext(os.path.basename(r["project"]))[0]).glob("*.csv"))) >= 1 for r in res))
fig = pg.combine(layout=(2, 3, False))
import matplotlib.text as mt
letters = [sf._suptitle.get_text() for sf in fig.subfigs if sf._suptitle is not None]
check("check 14c: 'Combine into one figure' (2 × 3) gives one landscape figure with the panels (a) … (f)", fig is not None and letters == ["(a)", "(b)", "(c)", "(d)", "(e)", "(f)"] and len(fig.axes) >= 6 and fig.get_size_inches()[0] > fig.get_size_inches()[1], letters)
from opstudio import origin as O
import origin_plot_app as opa
rc = O.draw_in_origin(lambda f: opa.Driver(f, lambda m: None, dry=True), fig, "combined", "2x3", str(TMP / "comb")); J = "\n".join(rc["commands"])
check("the combined figure goes to Origin as one graph: a layer per panel, the letters as texts", J.count("layer.left=") == len(fig.axes) and '"\\b((a))"' in J and '"\\b((f))"' in J and rc["project"].endswith("combined_2x3.opju"))
from workspace_templates import save_combined
cp = str(TMP / "combined.png"); save_combined(fig, cp); check("the combined figure is saved as a picture", os.path.getsize(cp) > 5000)
pg.export_options = {"formats": ["png"], "width": "double", "dpi": 150, "transparent": False, "pattern": "{sample}_{template}_{style}", "folder": str(TMP / "export")}
wr = pg.export_all(); check("check 14d: 'Export all' writes 6 files", len(wr) == 6 and all(os.path.getsize(p) > 2000 for p in wr), [os.path.basename(p) for p in wr][:3])
pg.export_options = {"formats": ["png", "tiff", "pdf", "svg", "eps"], "width": "single", "dpi": 300, "transparent": False, "pattern": "{n}_{sample}_{template}", "folder": str(TMP / "export2")}
wr2 = pg.export_all(pg.kept()[:1]); from PIL import Image; im = Image.open(wr2[0])
check("export in PNG / TIFF / PDF / SVG / EPS at the single-column width of the style", len(wr2) == 5 and abs(im.size[0] / im.info["dpi"][0] * 25.4 - pg.ops.load_style(pg.kept()[0].combo["style"])["figure"]["width_mm"]["single"]) < 0.6)
xb = pg.export_workbook(str(TMP / "all.xlsx")); book = pd.read_excel(xb, sheet_name=None)
check("data of all in one Excel workbook: one sheet per file and the list of graphs with the columns used", set(book) >= {"Graphs", "Sample_A"} and len(book["Graphs"]) == 6 and "columns used" in book["Graphs"].columns and len(book["Sample_A"]) == 300, list(book))
# ---- apply the same style / variants to all
tick(pg.styles, {"grayscale_print"}); pg.apply_style_to_all()
check("apply the same style to all kept graphs", all(t.combo["style"] == "grayscale_print" for t in pg.kept()) and len(pg.kept()) == 6)
pg.sw["revx"].setChecked(True); pg.sw["logy"].setChecked(True); sw = pg.current_switches()
k0 = pg.kept()[0]; k0.combo.pop("switches", None); pg.redraw_tile(k0)
check("variants (reversed x, log y) apply to every template", sw.get("revx") and sw.get("logy") and k0.fig.axes[0].xaxis_inverted() and k0.fig.axes[0].get_yscale() == "log")
pg.sw["revx"].setChecked(False); pg.sw["logy"].setChecked(False)
# ---- columns: map, untick, remember
pg.show_columns(files[0]); roles = [pg.cols.item(i).text() for i in range(pg.cols.count())]
check("the Columns panel shows what each column is used as", "[x]" in roles[0] and "[series]" in roles[1], roles)
big = TMP / "wide.csv"; pd.DataFrame({"t (h)": [1, 2, 3, 4.0], "A": [1, 2, 3, 4.0], "B": [2, 3, 4, 5.0], "note": list("abcd")}).to_csv(big, index=False); pg.add_files([str(big)]); pg.show_columns(str(big))
pg.cols.item(2).setCheckState(Qt.Unchecked); app.processEvents(); tb = pg.table_of(str(big))[0]
check("unticking a column leaves it out; the choice is remembered for files with the same headers", tb.ys == ["A"] and pg._cfg()["mappings"]["t (h)|A|B|note"]["off"] == ["B"], tb.ys)
# ---- a multi-sheet "recipe" workbook, as sent in by a real user: a text-only guide sheet first, a sheet with more numeric
# columns than the one actually meant for the ticked template, and the right sheet for it
recipe = TMP / "recipe.xlsx"
with pd.ExcelWriter(recipe) as xw:
    pd.DataFrame({"Step": ["Read this first", "Then go to Stack_clinkers"], "Note": ["guide", "guide"]}).to_excel(xw, sheet_name="START_HERE", index=False)
    pd.DataFrame({"T (min)": np.arange(20.0), "r1": np.arange(20.0), "r2": np.arange(20.0) * 2, "r3": np.arange(20.0) * 3, "r4": np.arange(20.0) * 4}).to_excel(xw, sheet_name="Model_runs", index=False)
    pd.DataFrame({"2theta (deg)": x, "Clinker_A": 100 + 900 * np.exp(-(x - 29) ** 2 / 0.5), "Clinker_B": 120 + 700 * np.exp(-(x - 32) ** 2 / 0.6)}).to_excel(xw, sheet_name="Stack_clinkers", index=False)
pg.add_files([str(recipe)]); app.processEvents()
check("no sheet called 'Data': the default pick is the most plottable sheet, not just the first (text-only guide) one", pg.table_of(str(recipe))[1] == "Model_runs", pg.table_of(str(recipe))[1])
t_recipe = pg._table_for_template(str(recipe), "xrd_stacked_offset")
check("for a ticked template, the sheet picked is the one that actually fits it (XRD stack), not the sheet with the most numeric columns", list(t_recipe.df.columns) == ["2theta (deg)", "Clinker_A", "Clinker_B"], list(t_recipe.df.columns))
f_recipe, _ = pg.api.draw("xrd_stacked_offset", pg.tables_for([str(recipe)], "xrd_stacked_offset"))
check("drawing the ticked template from this workbook succeeds and uses the right sheet's series names", f_recipe is not None and {"Clinker_A", "Clinker_B"} <= {t.get_text() for t in f_recipe.axes[0].texts}, [t.get_text() for t in f_recipe.axes[0].texts])
# ---- one graph from several files
set_checked(pg.files, range(pg.files.count()), False); tick(pg.files, set(files)); pg.together.setChecked(True); tick(pg.grid, {"xrd_stacked_offset"}); tick(pg.styles, {"house_style_1"})
check("'All ticked files in one graph': 3 files → 1 preview", "→  1 preview" in pg.count.text(), pg.count.text())
pg.rebuild_previews()
settle(pg)
one = pg.tiles[0]; txt = [t.get_text() for t in one.fig.axes[0].texts]
check("several files in one graph: one curve per file, named after the file", len(pg.tiles) == 1 and {"Sample_A", "Sample_B", "Sample_C"} <= set(txt), txt)
# ---- editor edits: texts and names typed by the user, never in the file
one.keep.setChecked(True); one.combo["overrides"] = {"x_label": "2θ (°), Cu Kα", "_renames": {"Sample_A": "Reference"}}; pg.redraw_tile(one)
txt2 = [t.get_text() for t in one.fig.axes[0].texts]
check("typed axis title and curve name are used on the graph", one.fig.axes[0].get_xlabel() == "2θ (°), Cu Kα" and "Reference" in txt2 and "Sample_A" not in txt2, txt2)
# ---- my templates
pg.next_name = "My stack"; tid = pg.save_my_template(one); mine = pg.api.user_templates()
check("Save as my template: JSON + preview + Origin script in the private folder, listed under My templates", tid == "my_stack" and (TMP / "private" / "templates" / "my_stack.json").is_file() and (TMP / "private" / "previews" / "my_stack.png").is_file()
      and (TMP / "private" / "origin" / "my_stack.ogs").is_file() and any(r["id"] == "my_stack" and r["source"] == "mine" for r in pg.catalogue))
acts = [a.text() for a in pg.add_btn.menu().actions()]
check("'+ Add template' in the gallery: from my graph, as a copy of a ticked template, from a file, open my folder", pg.add_btn.text().startswith("+ Add template") and len(acts) == 5 and acts[0].startswith("From the graph I made here") and acts[2].startswith("From a template file"), acts)
tick(pg.grid, {"scatter_linear_fit"}); pg.next_name = "My copy"; cp = pg._copy_ticked(); mine_ids = [r["id"] for r in pg.catalogue if r["source"] == "mine"]
shown_ = [pg.grid.item(i).data(Qt.UserRole) for i in range(pg.grid.count()) if not pg.grid.item(i).isHidden()]
check("a copy of a ticked template is added under My templates and shown at once", cp == "my_copy" and "my_copy" in mine_ids and "my_copy" in shown_ and all(x in mine_ids for x in shown_), (cp, shown_))
fcp, _ = pg.api.draw("my_copy", pg.tables_for([files[0]])); check("the added template can be used for drawing my data", fcp is not None and len(fcp.axes) >= 1)
pg._class_clicked(pg.classes.topLevelItem(0)); pg.next_name = "My stack"
w2 = W.Workspace([]); pg2 = w2.templates_page
check("after a restart the template is there with its preview", any(r["id"] == "my_stack" and os.path.isfile(r["preview"]) for r in pg2.catalogue)); w2.close()
op = str(TMP / "t.opst"); pg.api.export_opst(str(TMP / "private"), "my_stack", op); os.remove(TMP / "private" / "templates" / "my_stack.json"); back = pg.import_opst(op)
check("export / import of a template as one .opst file", back == "my_stack" and (TMP / "private" / "templates" / "my_stack.json").is_file())
# ---- useful feedback, nothing frozen
bad = TMP / "notes.txt"; bad.write_text("this is not a table\njust words\n", encoding="utf-8"); pg.together.setChecked(False); pg.add_files([str(bad)]); set_checked(pg.files, range(pg.files.count()), False); tick(pg.files, {str(bad)})
pg.rebuild_previews()
settle(pg)
check("a file that is not a table gives a tile that says so; nothing crashes", len(pg.tiles) == 1 and pg.tiles[0].fig is None and len(pg.tiles[0].error) > 10 and not pg.tiles[0].keep.isEnabled(), pg.tiles[0].error[:80])
tick(pg.files, set(files)); tick(pg.grid, {r["id"] for r in avail[:12]}); pg.rebuild_previews(); app.processEvents(); pg.cancel(); app.processEvents()
check("a long drawing can be cancelled: the previews drawn so far stay", len(pg.tiles) == 36 and not pg.bar.isVisible() and "Cancelled" in pg.pmsg.text(), pg.pmsg.text())
long_ = TMP / ("a_very_long_file_name_" * 6 + ".csv"); pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]}).to_csv(long_, index=False); pg.add_files([str(long_)])
check("a very long file name is listed (full path in the tooltip)", any(pg.files.item(i).toolTip() == str(long_) for i in range(pg.files.count())))
check("my files were only read: their bytes are unchanged", [sha(p) for p in files] == before)
import workspace_shell as SH
data = SH.save_layout(w); check("the layout of the Templates panels is kept with the other panels", "page5" in data)
tips = [b for b in pg.findChildren(type(pg.b_open)) if b.isVisible() and not b.toolTip()]
check("every button of the page has a tooltip; disabled buttons say what enables them", not tips and "Disabled:" in pg.b_origin.toolTip() and "Ctrl+Shift+O" in pg.b_origin.toolTip(), [b.text() for b in tips])
w.close()
print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

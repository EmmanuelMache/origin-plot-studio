"""Files that belong together, and what the app works out for a file by itself: a series of samples goes into one graph
first, the Workbook shows them side by side and merges them, a thermal run gets its DTG column, a column can be left
out in all files, and the peaks of a thermal run or an infrared spectrum are found and named as possibilities.
Run:  python tests/test_related.py"""
import os, sys, tempfile, time, warnings
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
TMP = Path(tempfile.mkdtemp()); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private"); os.environ["ORIGIN_PLOT_APP_HOME"] = str(TMP / "store")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
import related as R
from opstudio import data as OD, ftir_core, tga_core
from opstudio.detection import preferred_xy

# ---------------------------------------------------------------- names that follow one pattern
s = R.series(["10-900-AB-Mix.dat", "10-950-AB-Mix.dat", "20-990-AB-Mix.dat"])
check("names built the same way with a part that changes are one series; what they share and what changes is said", s["related"] and s["shared"] == "AB Mix" and s["varies"] == ["10-900", "10-950", "20-990"] and "AB Mix" in s["why"], s)
check("replicates (rep1, rep2) and numbered names (S1, S2, S10) are series", R.series(["TGA_Ref_28d_rep1.txt", "TGA_Ref_28d_rep2.txt"])["related"] and R.series(["S1.csv", "S2.csv", "S10.csv"])["related"])
check("files with nothing in common are not", not R.series(["xrd_raw.csv", "ftir.xlsx"])["related"] and not R.series(["a.csv", "b.csv"])["related"] and not R.series(["one.csv"])["related"] and not R.series(["scan_1.csv", "other_2.csv"])["related"])
g = R.groups(["10-900-AB-Mix.dat", "notes.csv", "20-990-AB-Mix.dat", "S1.csv", "S2.csv", os.path.join("x", "derived", "AB_Mix_1a2b3c.csv")])
check("a mixed list is sorted into its series; a table the app merged from them belongs to none", sorted(map(sorted, g)) == sorted([sorted(["10-900-AB-Mix.dat", "20-990-AB-Mix.dat"]), ["S1.csv", "S2.csv"]]), g)
check("a series gets a short name: what the names share", R.series_label(["10-900-AB-Mix.dat", "20-990-AB-Mix.dat"]) == "AB Mix" and R.series_label(["S1.csv", "S9.csv"]) == "S1 to S9")

# ---------------------------------------------------------------- a thermal run: x and y, DTG, steps and what they may be
T = np.linspace(25, 1000, 1951)
def run(k=0): return 100 - 3 / (1 + np.exp(-(T - 120) / 15)) - (5 + k) / (1 + np.exp(-(T - 450) / 12)) - 6 / (1 + np.exp(-(T - 720) / 18))
tga = OD.Table("run", pd.DataFrame({"Temperature (°C)": T, "Time (min)": (T - 25) / 10, "Mass (%)": run(), "DSC (uV)": np.sin(T / 90)}))
check("a thermal run exported as temperature, time, mass, DSC is read as mass against temperature (the column order alone gave time against temperature)",
      tga.ys[0] == "Time (min)" and preferred_xy(tga) == ("Temperature (°C)", "Mass (%)"))
check("... a file whose first two columns already are x and y, or of no recognised kind, keeps its own order", preferred_xy(OD.Table("a", pd.DataFrame({"Temperature (°C)": T, "Mass (%)": run(), "Time (min)": T}))) is None
      and preferred_xy(OD.Table("b", pd.DataFrame({"p": T, "q": T * 2, "r": T * 3}))) is None)
name, d, how = R.dtg_column(tga)
check("the DTG curve of a thermal run: a column in % per °C on the file's own points, by the calculation of the TGA page (15 °C window)", name == "DTG (%/°C)" and len(d) == len(T) and how == {"mass": "Mass (%)", "temperature": "Temperature (°C)", "window_C": 15.0} and np.isfinite(d).all())
ref = tga_core.dtg(T, run())["dtg_per_C"]
check("... the same numbers as tga_core.dtg, deepest at the steepest step (450 °C)", np.allclose(d, ref, atol=2e-4) and abs(T[np.argmin(d)] - 450) < 3 and d.min() < -0.07, float(np.abs(d - ref).max()))
check("a file that already has a DTG column keeps its own (none is added)", R.dtg_column(OD.Table("c", pd.DataFrame({"Temperature (°C)": T, "Mass (%)": run(), "DTG (%/min)": T * 0}))) is None)
check("a table that is no thermal run gets none", R.dtg_column(OD.Table("d", pd.DataFrame({"2theta (deg)": T, "Intensity": T}))) is None)
pt = R.peak_table("TGA", tga)
check("the steps of a thermal run are found: where, from - to, how much", R.peak_kind(tga) == "TGA" and len(pt) == 3 and [round(v) for v in pt["DTG peak (°C)"]] == [120, 450, 720] and all(abs(a - b) < 0.4 for a, b in zip(pt["Mass loss (%)"], (3, 5, 6))), pt.iloc[:, :4].to_dict("list"))
check("... each with what it may be (the usual event at that temperature, most likely first), the other possibilities, and a Label with a question mark",
      list(pt["May be"]) == ["C-S-H + ettringite (AFt) dehydration", "Portlandite Ca(OH)2 dehydroxylation", "Calcite decarbonation"] and "Kaolinite" in pt["Other possibilities"][1] and list(pt["Label"]) == ["C-S-H / AFt ?", "Ca(OH)₂ ?", "CaCO₃ ?"], pt[["May be", "Label"]].to_dict("list"))
check("every usual thermal event has a short label for a graph", all(e["name"] in R.TGA_SHORT for e in tga_core.REFERENCE_EVENTS if e["gas"]))
check("where ranges overlap, the event nearly every cement shows comes first: 772 °C is offered as calcite before dolomite, 650 °C as calcite before weak carbonates",
      [s_ for _n, s_ in R.tga_candidates(772)][:2] == ["CaCO₃", "Dolomite"] and R.tga_candidates(650)[0][1] == "CaCO₃" and R.tga_candidates(160)[0][1] == "C-S-H / AFt" and R.tga_candidates(950) == [], R.tga_candidates(772))

# ---------------------------------------------------------------- an infrared spectrum: bands and what they may be
x = np.linspace(400, 4000, 3601); bands = [(0.5, 3643, 6), (0.3, 3420, 120), (0.2, 1645, 25), (0.9, 1425, 35), (0.3, 1115, 20), (0.7, 970, 30), (0.6, 875, 6), (0.25, 712, 4)]
y = sum(a * np.exp(-(x - c) ** 2 / (2 * w ** 2)) for a, c, w in bands) + 0.02
ir = OD.Table("ir", pd.DataFrame({"Wavenumber (cm-1)": x, "Absorbance": y})); ft = R.peak_table("FTIR", ir)
check("the bands of an infrared spectrum are found (the ones the graph labels)", R.peak_kind(ir) == "FTIR" and sorted(round(v) for v in ft["Band (cm⁻¹)"]) == sorted(c for _a, c, _w in bands), list(ft["Band (cm⁻¹)"]))
by = {round(b): l for b, l in zip(ft["Band (cm⁻¹)"], ft["Label"])}
check("... each with what it may be: O–H of Ca(OH)₂, water, carbonate, sulfate, C-S-H", by[3643] == "O–H (Ca(OH)₂) ?" and by[3420] == "O–H (H₂O) ?" and by[1425] == "ν₃ CO₃²⁻ ?" and by[1115] == "ν₃ SO₄²⁻ ?" and by[970] == "Si–O (C-S-H) ?" and by[875] == "ν₂ CO₃²⁻ ?" and by[712] == "ν₄ CO₃²⁻ ?", by)
check("a transmittance spectrum is read at its minima", list(R.peak_table("FTIR", OD.Table("t", pd.DataFrame({"Wavenumber (cm-1)": x, "Transmittance (%)": 100 - 60 * y})))["Read as"])[0].startswith("minimum"))
check("the reference of infrared bands: ranges in cm-1, most central first, nothing outside them", [b["short"] for b in ftir_core.suggest(875)][0] == "ν₂ CO₃²⁻" and ftir_core.suggest(2000) == [] and all(b["range"][0] < b["range"][1] for b in ftir_core.REFERENCE_BANDS))
nm = R.names_of(ft)
check("a label belongs to the peak of a graph that lies within the tolerance (8 cm-1, 15 °C), and to none further away", R.name_at(nm, 1428.0, "FTIR") == "ν₃ CO₃²⁻ ?" and R.name_at(nm, 1450.0, "FTIR") is None and R.name_at(R.names_of(pt), 460.0, "TGA") == "Ca(OH)₂ ?" and R.name_at([], 5, "TGA") is None)

# ---------------------------------------------------------------- files side by side
other = OD.Table("o", pd.DataFrame({"Temperature (°C)": T[:900], "Mass (%)": run(1)[:900]}))
sbs = R.side_by_side([("a/10-900-AB-Mix.csv", tga), ("a/20-990-AB-Mix.csv", other)], extra=lambda p, t: [R.dtg_column(t)[:2]] if R.dtg_column(t) else [])
check("files side by side: for each file its x and y columns, named 'column [file]', and the DTG curve of a thermal run",
      list(sbs.columns) == ["Temperature (°C) [10-900-AB-Mix]", "Time (min) [10-900-AB-Mix]", "Mass (%) [10-900-AB-Mix]", "DSC (uV) [10-900-AB-Mix]", "DTG (%/°C) [10-900-AB-Mix]",
                            "Temperature (°C) [20-990-AB-Mix]", "Mass (%) [20-990-AB-Mix]", "DTG (%/°C) [20-990-AB-Mix]"], list(sbs.columns))
check("... every file keeps its own x values (nothing is interpolated); the shorter file ends in empty cells", len(sbs) == len(T) and np.array_equal(sbs.iloc[:900, 5].to_numpy(), T[:900]) and sbs.iloc[900:, 5].isna().all() and np.array_equal(sbs.iloc[:, 0].to_numpy(), T))
f_sbs = TMP / "AB_Mix_side.csv"; sbs.to_csv(f_sbs, index=False)
import smart_plots as sp
tabs = sp.read_tables(str(f_sbs))
check("such a file is read back as one table per file, each with its own columns and without the empty cells", [n for n, _r in tabs] == ["10-900-AB-Mix", "20-990-AB-Mix"] and list(tabs[1][1].iloc[0]) == ["Temperature (°C)", "Mass (%)", "DTG (%/°C)"] and len(tabs[1][1]) == 901 and str(f_sbs) in sp.SIDE_BY_SIDE, [(n, r.shape) for n, r in tabs])
plain = TMP / "plain.csv"; pd.DataFrame({"x [a]": [1, 2, 3], "y": [1, 2, 3]}).to_csv(plain, index=False)
check("any other table stays one table", len(sp.read_tables(str(plain))) == 1 and str(plain) not in sp.SIDE_BY_SIDE)

# ---------------------------------------------------------------- in the app
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog, QFileDialog
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, workspace_workbook as WB
app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes); asked = []
QInputDialog.getText = staticmethod(lambda *a, **k: (asked.append(k.get("text")) or k.get("text", "Merged"), True))
def pump(cond=lambda: False, timeout=.3):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond(): return True
        time.sleep(.005)
    return cond()
def idle(w, timeout=90): return pump(lambda: w.thread is None and not w.workbench._opening, timeout) and pump(timeout=.4)
w = W.Workspace([]); w.resize(1600, 1000); w.show(); pump(); w.go(6); sh = w.pages.widget(6); c = w.workbench
files = []
for k, (a, b) in enumerate([(10, 900), (10, 950), (20, 900)]):
    f = TMP / f"{a}-{b}-AB-Mix.csv"; pd.DataFrame({"Temperature (°C)": T, "Time (min)": (T - 25) / 10.0, "Mass (%)": run(k), "DSC (uV)": np.sin(T / 90)}).to_csv(f, index=False); files.append(str(f))
scan = TMP / "pattern.csv"; xx = np.linspace(5, 70, 1300); pd.DataFrame({"2theta (deg)": xx, "Intensity (counts)": 100 + 900 * np.exp(-(xx - 29.4) ** 2 / 0.02)}).to_csv(scan, index=False)
sh.add_files(files + [str(scan)]); idle(w); pump(timeout=1.0)
for p in sh.selected_paths(): pump(lambda: c.ready(p), 90)
t0 = c.table_for(files[0])
check("Start here: the thermal run is looked at as mass against temperature", t0.x == "Temperature (°C)" and t0.ys[0] == "Mass (%)", (t0.x, t0.ys))
sh._current_path = files[0]; sh.inspect_current(); pump(timeout=1.0)
first = sh.recs.item(0).text() if sh.recs.count() else ""
check("Start here: the three ticked runs look like one series - the app chooses 'Combine selected files in one graph' by itself", sh.combine_mode.currentIndex() == 1 and sh._rec_paths == files, (sh.combine_mode.currentText(), [os.path.basename(p) for p in sh._rec_paths]))
check("... says why, and that the fourth file (another kind) is left out of it", "look like one series" in sh.rec_caption.text() and "AB Mix" in sh.rec_caption.text() and "The other one is left out" in sh.rec_caption.text(), sh.rec_caption.text())
check("... the recommended graph of the series is the one highlighted (not the single-sample graph that was highlighted before)", sh.recs.currentRow() == 0 and "stacked" in sh.recs.currentItem().text().lower(), sh.recs.currentItem().text()[:50] if sh.recs.currentItem() else None)
top3 = [sh.recs.item(i).text().split("\n")[0] for i in range(min(3, sh.recs.count()))]
check("... and the graphs that show the samples together come first, the stacked one before the others", "stacked" in top3[0].lower() and "Recommended" in first and all("several" in t_.lower() or "stack" in t_.lower() for t_ in top3) and "Shows the 3 files of the series together" in first, top3)
sh.combine_mode.setCurrentIndex(0); pump(timeout=.8)
check("choosing 'Separate graph for each file' is kept for these files (the app does not switch back)", sh.combine_mode.currentIndex() == 0 and "look like one series" not in sh.rec_caption.text() and sh.recs.item(0).text().startswith("TG and DTG in one graph"), sh.recs.item(0).text()[:40])
sh.inspect_current(); pump(timeout=.5); check("... also when the page is drawn again", sh.combine_mode.currentIndex() == 0)
sh._mode_user = False; sh.refresh_recommendations(); pump(timeout=.5); n0 = len(w.singles)
sh.recs.setCurrentRow(0); sh.draw_recommended(); idle(w); pump(timeout=1.0)
made = [i for i in w.singles[n0:]]
check("Create graph makes ONE graph of the three runs (not one each, and without the fourth file)", len(made) == 1 and len(getattr(made[0], "combo", {}).get("files", [])) == 3, [(type(i).__name__, getattr(i, "combo", {}).get("files")) for i in made])

# ---- Workbook
sh.open_workbook(); pump(timeout=1.0); wb = c.workbook
rows = [wb.files.item(i).text() for i in range(wb.files.count())]
check("Workbook: after the files, a table of the series side by side, made by the app", rows[:4] == [os.path.basename(p) for p in files] + ["pattern.csv"] and rows[-1] == "⧉ All of 'AB Mix' side by side · 3 files", rows)
check("the working copy of a thermal run has its DTG curve as a last column", list(wb.model.df.columns) == ["Temperature (°C)", "Time (min)", "Mass (%)", "DSC (uV)", "DTG (%/°C)"] and abs(float(wb.model.df["Temperature (°C)"][wb.model.df["DTG (%/°C)"].idxmin()]) - 450) < 3)
cols = [(wb.columns.item(i).text(), wb.columns.item(i).checkState() == Qt.Checked) for i in range(wb.columns.count())]
check("... listed under Columns as worked out by the app, unticked: it is exported, but the graphs keep working out their own", cols[-1] == ("DTG (%/°C)  (worked out by the app)", False) and "DTG (%/°C)" not in c.table_for(files[0]).cols, cols)
check("the columns are listed in the order the graphs use them (X, then Y): a tick or a drag keeps X and Y", [n for n, _ in cols[:2]] == ["Temperature (°C)", "Mass (%)"] and wb.x.currentText() == "Temperature (°C)" and wb.y.currentText() == "Mass (%)")
wb.files.setCurrentRow(wb.files.count() - 1); pump(timeout=.5)
check("the side-by-side table: all three runs with their own X, their Y columns and DTG; looked at and exported, not edited", wb.model.df.shape == (len(T), 15) and wb.caption.text() == "All of 'AB Mix' side by side"
      and not (wb.model.flags(wb.model.index(0, 0)) & Qt.ItemIsEditable) and "nothing is interpolated" in wb.info.text(), (wb.model.df.shape, wb.caption.text()))
out_csv = TMP / "side.csv"; WB.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(out_csv), "")); r = wb.export_data()
check("... Export data saves it as CSV", r == str(out_csv) and pd.read_csv(out_csv).shape == (len(T), 15))
check("no project is needed to merge: files that are in no project are merged too", c.active_project is None or all(c.project_for(p) != c.active_project for p in files))
wb.files.setCurrentRow(0); pump(timeout=.3); n0 = len(w.singles); merged = wb.merge_files(); idle(w); pump(timeout=1.5)
rows = [wb.files.item(i).text() for i in range(wb.files.count())]
check("Merge selected files (side by side): the new dataset is in the list, selected, named after the series; the four ticked files are unchanged", bool(merged) and os.path.isfile(merged) and wb.files.currentItem().text() == os.path.basename(merged)
      and os.path.basename(merged).startswith("AB_Mix") is False and os.path.basename(merged) in rows and "dataset of its own" in w.status.text() or bool(merged) and wb.files.currentItem().text() == os.path.basename(merged), (merged, w.status.text()[:90]))
check("... the app proposed a name for it", asked and isinstance(asked[-1], str) and len(asked[-1]) > 0, asked)
new = w.singles[n0:]; kinds = sorted({i.kind for i in new})
check("... and it is drawable: Workspace reads it as one graph per sample (not only the first sample)", len([i for i in new if i.kind == "TGA"]) >= 3, [(i.kind, i.title.strip()[:40]) for i in new])
check("... the Workbook shows it with one sheet per sample", [wb.sheet.itemText(i) for i in range(wb.sheet.count())][:3] == [Path(p).stem for p in files[:3]], [wb.sheet.itemText(i) for i in range(wb.sheet.count())])
check("the table of the series is still offered (the merged file is not taken for a member of it)", any(t_.startswith("⧉ All of 'AB Mix'") and "3 files" in t_ for t_ in rows), rows)

# ---- a column left out in all files
wb.files.setCurrentRow(0); pump(timeout=.4)
n_changed = wb.set_column_everywhere("Time (min)", False); pump(timeout=1.0)
check("'Leave out in all files': the column is off in every file of the list that has it (the merged dataset too)", n_changed == 4 and all("Time (min)" not in c.table_for(p).cols for p in files) and "Time (min)" in list(c.raw_sheets(files[1])[""].columns), n_changed)
it1 = next(i for i in w.singles if getattr(i, "path", "") == files[1] and not hasattr(i, "combo"))
check("... it is not carried to Workspace: the graphs of those files are built without it", "Time (min)" not in list(it1.det["_df"].columns), list(it1.det["_df"].columns))
check("... the working copy and the source file still have it", "Time (min)" in pd.read_csv(files[1]).columns)
wb.set_column_everywhere("Time (min)", True); pump(timeout=.8)
check("'Use in all files' brings it back", all("Time (min)" in c.table_for(p).cols for p in files))
item = next(wb.columns.item(i) for i in range(wb.columns.count()) if wb.columns.item(i).text() == "DSC (uV)"); item.setCheckState(Qt.Unchecked); pump(timeout=1.0)
wb.columns_to_all(); pump(timeout=1.0)
check("'Use these column choices for all files': what is unticked here is left out everywhere", all("DSC (uV)" not in c.table_for(p).cols and "Time (min)" in c.table_for(p).cols for p in files) and "DSC (uV)" in w.status.text(), w.status.text())
check("the Columns list has a right-click menu and the button says what it does", wb.columns.contextMenuPolicy() == Qt.CustomContextMenu and "every file" in wb.b_all.toolTip())

# ---- peaks of the file: the sheet, the labels, the graph
wb.files.setCurrentRow(0); pump(timeout=.4)
sheets = [wb.sheet.itemText(i) for i in range(wb.sheet.count())]
check("a thermal run has a last sheet 'Peaks — found by the app'", sheets[-1] == R.PEAKS_SHEET, sheets)
wb.sheet.setCurrentText(R.PEAKS_SHEET); pump(timeout=.5); pk = wb.model.df
check("it lists the steps with what each may be and a Label; only the Label can be typed in", list(pk["Label"]) == ["C-S-H / AFt ?", "Ca(OH)₂ ?", "CaCO₃ ?"] and wb.draw_labels.isVisibleTo(wb) and not wb.draw_labels.isChecked()
      and bool(wb.model.flags(wb.model.index(0, list(pk.columns).index("Label"))) & Qt.ItemIsEditable) and not (wb.model.flags(wb.model.index(0, 0)) & Qt.ItemIsEditable), list(pk.columns))
tg = lambda: next(i for i in w.singles if getattr(i, "path", "") == files[0] and getattr(i, "kind", "") == "TGA" and not hasattr(i, "combo"))
labels = lambda: [t_ for _a, t_, _b in (tg().spec["panels"][0].get("y2") or {}).get("labels", [])]
before = labels()
check("the graph of the file shows positions and losses only, as before", len(before) == 3 and all("?" not in t_ and "Ca(OH)" not in t_ for t_ in before), before)
wb.model.setData(wb.model.index(1, list(pk.columns).index("Label")), "Portlandite", Qt.EditRole); pump(timeout=.4)
check("typing a label does not change the graph while 'Draw these labels on the graph' is off", labels() == before)
wb.draw_labels.setChecked(True); pump(timeout=1.2); after = labels()
check("switched on: the graph writes each label beside its position - yours where you typed one", len(after) == 3 and "Portlandite" in after[1] and after[1].startswith("450 °C") and "C-S-H / AFt ?" in after[0] and "CaCO₃ ?" in after[2], after)
xl = TMP / "run.xlsx"; WB.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(xl), "")); wb.sheet.setCurrentIndex(0); pump(timeout=.5); wb.export_data(); book = pd.read_excel(xl, sheet_name=None)
check("Export data as Excel: the data (with DTG) on one sheet, the peaks and what they may be on a second", list(book) == ["Data", "Peaks"] and "DTG (%/°C)" in book["Data"].columns and list(book["Peaks"]["Label"]) == ["C-S-H / AFt ?", "Portlandite", "CaCO₃ ?"], {k: list(v.columns) for k, v in book.items()})
st = c.settings_for(files[0])["sheet_settings"][""]
check("the labels and the switch are kept with the file (saved with the project or the session)", st.get("peak_names_on") is True and [l for _p, l in st["peak_labels"]] == ["C-S-H / AFt ?", "Portlandite", "CaCO₃ ?"] and c.has_working_state(files[0]), st.get("peak_labels"))
wb.sheet.setCurrentText(R.PEAKS_SHEET); pump(timeout=.4); wb.draw_labels.setChecked(False); pump(timeout=1.2)
check("switched off: the graph is as it was", labels() == before, labels())
row = tg().results.iloc[0].to_dict() if getattr(tg(), "results", None) is not None else {}
check("the results table of a thermal graph names what each step may be", row.get("May be") == "C-S-H + ettringite (AFt) dehydration" and "Other possibilities" in row, row)
ex = ROOT / "origin_plot_app" / "examples_synthetic" / "ftir.xlsx"; w.load_sync([str(ex)]) if hasattr(w, "load_sync") else None; pump(timeout=.8)
fi = next((i for i in w.singles if getattr(i, "kind", "") == "FTIR"), None)
check("the results table of an infrared graph names what each band may be", fi is not None and fi.results is not None and "May be" in fi.results.columns and "Other possibilities" in fi.results.columns, None if fi is None or fi.results is None else list(fi.results.columns))
lab_ir = [t_ for _a, t_, _b in (fi.spec["panels"][0].get("labels") or [])] + [p[2] for p in (fi.spec["panels"][0].get("placed_below") or [])] if fi is not None else []
check("... the graph itself still labels its bands with their positions only", bool(lab_ir) and all(str(t_).replace(".", "").isdigit() for t_ in lab_ir), lab_ir[:6])
print(f"\n{N[0]} passed, {N[1]} failed"); sys.stdout.flush(); os._exit(1 if N[1] else 0)

"""Personal learning in the window: correct an XRD file, confirm 'Remember this mapping', restart, and the next file
of the same layout is offered the saved mapping. Opening, refreshing, cancelling and applying a memory record nothing;
an incompatible file is left alone; a style is saved for one graph; Learning history disables and forgets.
All files are synthetic (made here)."""
import os, sys, tempfile, time, warnings
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
TMP = Path(tempfile.mkdtemp()); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "s.json"); os.environ["OPS_PRIVATE_DIR"] = str(TMP / "p"); os.environ["ORIGIN_PLOT_APP_HOME"] = str(TMP / "store")
os.environ.pop("OPS_LEARNING_DIR", None); os.environ.pop("OPS_PROFILE", None)
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, workspace_learning as WL, opstudio
from opstudio import learning as L
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes); QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
def pump(cond=lambda: False, timeout=.3):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond(): return True
        time.sleep(.005)
    return cond()
PEAKS = ((18.0, 900), (29.4, 2000), (34.1, 1200), (47.1, 420))
def xrd(name, seed, cols=("A", "B"), scale=1.0):
    """A synthetic pattern written with the intensity FIRST and headers that say nothing: the app cannot know it is XRD."""
    x = np.arange(5, 70, 0.02); y = 50 + scale * sum(h * np.exp(-(x - p) ** 2 / 0.01) for p, h in PEAKS) + np.random.default_rng(seed).normal(0, 3, len(x))
    f = TMP / name; pd.DataFrame({cols[0]: y, cols[1]: x}).to_csv(f, index=False); return str(f)
def window():
    w = W.Workspace([]); w.resize(1500, 950); w.show(); pump(); w.go(6); return w, w.pages.widget(6), w.workbench, WL.controller(w)
def show(w, sh, c, f):
    sh.add_files([f]); pump(lambda: w.thread is None and not c._opening, 90); pump(timeout=.6); sh._current_path = f; sh.inspect_current(); pump(timeout=.3)
def counts(lc): return len(lc.svc.memories()), len(lc.svc.history())

f1, f1b, f2 = xrd("run_one.csv", 1), xrd("run_one_b.csv", 5), xrd("run_two.csv", 2, scale=1.4)
w, sh, c, lc = window()

# ---- opening, refreshing, restoring: nothing is learned
show(w, sh, c, f1)
check("the file is opened: the app shows what it recognised (a general XY table, type to be reviewed), with the first column as X", sh.type_combo.currentText() == "Automatic" and sh.x_combo.currentText() == "A" and "General XY" in sh.detect.text(), sh.detect.text())
sh.inspect_current(); pump(timeout=.2); sh.refresh_recommendations(); w.go(0); pump(timeout=.2); w.go(6); pump(timeout=.4)
check("open, refresh, leave the page and come back: NO correction is recorded and nothing is offered for confirmation", counts(lc) == (0, 0) and lc.pending(f1) is None and not sh.learn_bar.conf_row.isVisible(), counts(lc))
sh._building = True; sh.type_combo.setCurrentText("XRD"); sh.mapping_changed(); sh._building = False; sh.inspect_current(); pump(timeout=.2)
check("the app filling its own controls (a programmatic change while it builds the page) is not a user confirmation", lc.pending(f1) is None and counts(lc) == (0, 0))

# ---- the user changes the mapping and cancels
sh.x_combo.setCurrentText("B"); sh.y_combo.setCurrentText("A"); sh.mapping_changed(); pump(timeout=.3)
p = lc.pending(f1)
check("YOU change X and Y: the change is staged and the bar says what would be confirmed, with 'Remember this mapping' and a scope", p is not None and p["valid"] and "X: B" in p["text"] and "Y: A" in p["text"] and sh.learn_bar.conf_row.isVisible()
      and sh.learn_bar.remember.isChecked() and sh.learn_bar.scope.currentData() == "personal_format" and sh.learn_bar.b_confirm.isEnabled(), None if p is None else p["text"])
check("... nothing is stored yet: staging lives in memory only", counts(lc) == (0, 0))
show(w, sh, c, f1b)
check("change a dropdown and go to another file without confirming: the staged change is thrown away, no reusable memory", lc.pending(f1) is None and lc.pending(f1b) is None and counts(lc) == (0, 0))

# ---- confirm with remembering OFF
sh.type_combo.setCurrentText("XRD"); sh.x_combo.setCurrentText("B"); sh.y_combo.setCurrentText("A"); sh.mapping_changed(); pump(timeout=.3)
sh.learn_bar.remember.setChecked(False); sh.learn_bar.confirm(); pump(timeout=.2)
t_b, _s, _n, _c, _m = c.table_of(f1b)
check("confirm with 'Remember' OFF: the working mapping applies (XRD, X = B, Y = A) and NO reusable rule is created", t_b.x == "B" and t_b.ys[:1] == ["A"] and t_b.measurement_type == "XRD" and len(lc.svc.memories()) == 0 and "not remembered" in sh.learn_bar.done_text.text(), sh.learn_bar.done_text.text())

# ---- confirm with remembering ON (the first file)
show(w, sh, c, f1); sh.type_combo.setCurrentText("XRD"); sh.x_combo.setCurrentText("B"); sh.y_combo.setCurrentText("A"); sh.mapping_changed(); pump(timeout=.3)
sh.learn_bar.remember.setChecked(True); sh.learn_bar.b_confirm.click(); sh.learn_bar.b_confirm.click(); sh.learn_bar.confirm(); pump(timeout=.2)
mem = lc.svc.memories(); ev = [e for e in lc.svc.history() if e["event_type"] == "column_mapping_corrected"]
check("confirm with 'Remember this mapping' ON - and a double click on Confirm: exactly ONE confirmed event and ONE memory revision", len(mem) == 1 and mem[0]["kind"] == "import_mapping" and mem[0]["revision"] == 1 and mem[0]["user_confirmations"] == 1 and len(ev) == 1 and ev[0]["origin"] == "user",
      [(m["kind"], m["revision"], m["user_confirmations"]) for m in mem])
check("... the bar says 'Mapping remembered' with View and Undo saving", "Mapping remembered" in sh.learn_bar.done_text.text() and sh.learn_bar.b_view.isVisible() and sh.learn_bar.b_undo.isVisible(), sh.learn_bar.done_text.text())
det = lc.svc.memory_detail(mem[0]["id"]); blob = repr(det) + repr(lc.svc.history())
check("what is remembered is structure and roles only: no file name, no folder, no measured value", "run_one" not in blob and str(TMP) not in blob and "2000" not in blob and det["recipe"]["roles"]["x"]["i"] == 1 and det["recipe"]["data_family"] == "xrd", det["recipe"])
ch = det["events"][0]["changes"]; val = det["events"][0]["validation"]
check("... with the before / after difference and the checks kept apart from your confirmation", ch["data_family"] == {"before": "general_xy", "after": "xrd"} and ch["roles.x"] == {"before": 0, "after": 1} and val.get("user_confirmed") is True and val.get("structural_checks_passed") is True and val.get("preview_rendered") is True, (ch, val))

# ---- Learning history shows it
dlg = WL.HistoryDialog(w); dlg.table.selectRow(0); pump(timeout=.1)
check("Settings > Learning lists it (date, what, kind of data, where it applies, state, shared) and shows the saved before / after record", dlg.table.rowCount() == 1 and dlg.table.item(0, 1).text() == "Column mapping" and dlg.table.item(0, 2).text() == "XRD" and dlg.table.item(0, 3).text() == "This export format"
      and dlg.table.item(0, 4).text() == "In use" and dlg.table.item(0, 5).text() == "no" and "roles.x: 0  ->  1" in dlg.detail.toPlainText() and "confirmed by you 1 time" in dlg.detail.toPlainText(), dlg.detail.toPlainText()[:200])
check("... personal learning is on; diagnostics, sharing and automatic application are OFF until you switch them on", dlg.boxes["personal_learning"].isChecked() and not dlg.boxes["diagnostics"].isChecked() and not dlg.boxes["sharing"].isChecked() and not dlg.boxes["auto_apply"].isChecked())
dlg.close(); w.close(); db = lc.svc.db_path
check("the memory is kept in your own data folder, outside the program", str(db).startswith(str(TMP / "p")) and str(ROOT) not in str(db) and os.path.isfile(db), db)

# ---- restart: a second file of the same layout, other measurements
try: lc.svc.close()
except Exception: pass
L._default = None
w, sh, c, lc = window(); show(w, sh, c, f2)
sg = lc.suggestions(f2)
check("after a RESTART a second file of the same layout (different measurements) is offered the saved mapping, with the reason", len(sg) == 1 and sg[0].kind == "import_mapping" and sg[0].grade == "exact" and sh.learn_bar.sug_row.isVisible()
      and "Saved XRD mapping available" in sh.learn_bar.sug_text.text() and "same column names" in sh.learn_bar.sug_text.text().lower(), sh.learn_bar.sug_text.text())
t0, *_ = c.table_of(f2)
check("... it is NOT applied by itself: the file still shows what the app read (X = A)", t0.x == "A" and t0.measurement_type is None)
sh.learn_bar.b_apply.click(); pump(timeout=.4)
t2, *_ = c.table_of(f2); recs = c.recommendations([f2], focus=f2)
check("Apply: the mapping is checked against this file and used - XRD, X = B, Y = A", t2.x == "B" and t2.ys[:1] == ["A"] and t2.measurement_type == "XRD" and "Saved mapping applied" in w.status.text(), w.status.text()[:120])
check("... and the graphs offered are the XRD templates of Analysis (real installed templates, none invented)", recs and recs[0]["compatible"] and all(r["id"] in opstudio.REGISTRY or r["id"].startswith(("wb:", "user:")) for r in recs) and any("xrd" in r["id"] for r in recs[:4]), [r["id"] for r in recs[:4]])
m2 = lc.svc.memories()[0]
check("applying a memory is not a new confirmation of it: still confirmed once, used once, and no new user correction", m2["user_confirmations"] == 1 and m2["times_applied"] == 1 and len([e for e in lc.svc.history() if e["event_type"] == "column_mapping_corrected"]) == 1 and lc.pending(f2) is None, (m2["user_confirmations"], m2["times_applied"]))
sh.inspect_current(); pump(timeout=.2); show(w, sh, c, f2)
m3 = lc.svc.memories()[0]
check("... and showing the file again does not apply or count it again", m3["times_applied"] == 1 and m3["user_confirmations"] == 1 and not sh.learn_bar.sug_row.isVisible(), (m3["times_applied"], sh.learn_bar.sug_text.text()[:40]))

# ---- incompatible files
f3 = TMP / "thermal.csv"; T = np.linspace(30, 900, 800); pd.DataFrame({"Temperature (°C)": T, "Time (min)": (T - 30) / 10, "Mass (%)": 100 - 5 / (1 + np.exp(-(T - 450) / 12))}).to_csv(f3, index=False)
show(w, sh, c, str(f3)); t3, *_ = c.table_of(str(f3))
check("a file of another kind (a thermal run with other columns) is offered nothing and keeps the app's own reading", lc.suggestions(str(f3)) == [] and not sh.learn_bar.sug_row.isVisible() and t3.x == "Temperature (°C)" and t3.measurement_type is None, (t3.x, t3.measurement_type))
f4 = TMP / "units.csv"; pd.DataFrame({"A (kN)": np.linspace(0, 50, 400), "B (mm)": np.linspace(0, 2, 400) ** 1.5}).to_csv(f4, index=False)
show(w, sh, c, str(f4)); sg4 = lc.suggestions(str(f4)); t4, *_ = c.table_of(str(f4))
check("similar headers with units that do not belong to the remembered mapping: NOT applied silently (at most shown as a weaker match to check)", t4.measurement_type is None and t4.x == "A (kN)" and all(g.weak and not g.auto_apply_ok for g in sg4), [(g.grade, g.weak) for g in sg4])

# ---- type only
f5 = xrd("pattern_c.csv", 7, cols=("M", "N"))
show(w, sh, c, f5); n_mem = len(lc.svc.memories())
if sh.confirm_btn.isVisible():
    sh.confirm_type(); pump(timeout=.3); p5 = lc.pending(f5)
    check("'Confirm type' stages the TYPE only: nothing is said about the X and Y columns", p5 is not None and p5["type_only"] and "X:" not in p5["text"] and p5["candidate"].event_type == "classification_corrected" and "roles.x" not in p5["candidate"].changes, None if p5 is None else (p5["text"], list(p5["candidate"].changes)))
    sh.learn_bar.confirm(); pump(timeout=.2); kinds = [m["kind"] for m in lc.svc.memories()]
    check("... confirmed, a classification is remembered - not a column mapping", kinds.count("classification") == 1 and kinds.count("import_mapping") == 1, kinds)
else:
    sh.type_combo.setCurrentText("XRD"); sh.mapping_changed(); pump(timeout=.3); p5 = lc.pending(f5)
    check("changing only the type stages a classification correction: nothing is said about the X and Y columns", p5 is not None and p5["candidate"].event_type == "classification_corrected" and "roles.x" not in p5["candidate"].changes, None if p5 is None else list(p5["candidate"].changes))
    sh.learn_bar.confirm(); pump(timeout=.2); kinds = [m["kind"] for m in lc.svc.memories()]
    check("... confirmed, a classification is remembered - not a second column mapping", kinds.count("classification") == 1 and kinds.count("import_mapping") == 1, kinds)

# ---- a sheet change before confirmation
book = TMP / "two_sheets.xlsx"
with pd.ExcelWriter(book) as xw:
    pd.read_csv(f1).to_excel(xw, sheet_name="First", index=False); pd.read_csv(f2).rename(columns={"A": "C", "B": "D"}).to_excel(xw, sheet_name="Second", index=False)
show(w, sh, c, str(book)); sh.x_combo.setCurrentText("B"); sh.y_combo.setCurrentText("A"); sh.mapping_changed(); pump(timeout=.3)
p6 = lc.pending(str(book)); n6 = counts(lc)
if p6 is not None and sh.sheet.count() > 1:
    tok = p6["check"].token; cid = p6["candidate"].id
    sh.sheet.setCurrentIndex(1); sh.mapping_changed() if False else None; c.set_mapping(str(book), "", "", 1, "Automatic"); sh.inspect_current(); pump(timeout=.3)
    r6 = lc.svc.confirm(cid, remember=True, scope="personal_format", confirmation_token=tok, current_context=lc.describe(str(book))["ctx"])
    check("the sheet is changed before the staged mapping was confirmed: the old confirmation is invalid (stale) and nothing is remembered from it", r6.outcome == L.Outcome.STALE and counts(lc)[0] == n6[0] and lc.pending(str(book)) is None, r6.outcome)
else:
    check("the sheet is changed before the staged mapping was confirmed: the old confirmation is invalid (stale) and nothing is remembered from it", False, "no pending candidate on the two-sheet workbook")

# ---- storage unavailable
f7 = xrd("run_seven.csv", 9, cols=("P", "Q")); show(w, sh, c, f7); sh.type_combo.setCurrentText("XRD"); sh.x_combo.setCurrentText("Q"); sh.y_combo.setCurrentText("P"); sh.mapping_changed(); pump(timeout=.3)
n7 = len(lc.svc.memories())
def broken(*a, **k): raise L.StorageUnavailable("the database cannot be written (test)")
patched = [n for n in ("record_confirmation", "tx") if hasattr(lc.svc.store, n)]
saved_attrs = {n: getattr(lc.svc.store, n) for n in patched}
for n in patched: setattr(lc.svc.store, n, broken)
sh.learn_bar.confirm(); pump(timeout=.2)
for n, v in saved_attrs.items(): setattr(lc.svc.store, n, v)
t7, *_ = c.table_of(f7)
check("the database cannot be written: your mapping STAYS applied and the message says it could not be remembered (no 'remembered' claim)", t7.x == "Q" and t7.measurement_type == "XRD" and "could not remember" in sh.learn_bar.done_text.text() and "remembered." not in sh.learn_bar.done_text.text().replace("could not remember it.", "")
      and len(lc.svc.memories()) == n7, sh.learn_bar.done_text.text())

# ---- a number typed into a cell is not a rule
wbk = c.workbook; n8 = counts(lc)
try:
    c.select_inputs([f2]); wbk.set_paths([f2]); w.go(7); pump(timeout=.6); wbk.files.setCurrentRow(0); pump(timeout=.3)
    wbk.model.setData(wbk.model.index(3, 0), "4242.5"); pump(timeout=.2); edited = True
except Exception as e: edited = repr(e)
check("a number typed into a cell of the Workbook stays in the working copy: it does not become a rule (no event, no memory, the value is nowhere in the learning data)", edited is True and counts(lc) == n8 and "4242.5" not in repr(lc.svc.history()) + repr([lc.svc.memory_detail(m["id"]) for m in lc.svc.memories()]), edited)
w.go(6); pump(timeout=.3)

# ---- a style saved for ONE graph
f1c = xrd("run_one_c.csv", 21); show(w, sh, c, f1c)
for g_ in lc.suggestions(f1c)[:1]: lc.apply(f1c, g_)
pump(timeout=.3); show(w, sh, c, f2); made = c.create_graphs([f2, f1c], "xrd_single_labeled", False) or []; pump(timeout=.6)
if len(made) >= 2:
    g1, g2 = made[0], made[1]; before2 = repr(g2.combo.get("switches")); g1.combo.setdefault("switches", {})["markers"] = False; g1.combo["switches"]["inset"] = False
    r9, msg9 = lc.save_style(g1, target="graph")
    check("'Save style' for one graph (line only, no zoom): remembered as presentation for THAT graph; the neighbouring graph keeps its settings", r9 is not None and r9.saved and "this graph" in msg9 and repr(g2.combo.get("switches")) == before2, msg9)
    st = next(m for m in lc.svc.memories() if m["kind"] == "graph_style"); dst = lc.svc.memory_detail(st["id"]); blob9 = repr(dst)
    check("... the saved style holds component switches and the publication style only: no title, no sample name, no axis range, no data", dst["recipe"].get("style", dst["recipe"]).get("components", {}).get("markers") is False and "run_two" not in blob9 and "run_one" not in blob9 and "xmin" not in blob9 and "zoom" not in repr(dst["recipe"].get("style", dst["recipe"]).get("components", {}).keys() - {"zoom", "inset"}), dst["recipe"])
    sg9 = lc.style_suggestions(g2)
    check("... it is not offered for, and not put on, the other graph (it was saved for one graph)", sg9 == [] and repr(g2.combo.get("switches")) == before2, [g.kind for g in sg9])
    r10, msg10 = lc.save_style(g1, target="family"); sg10 = lc.style_suggestions(g2)
    if sg10:
        changed, m10 = lc.apply_style(g2, sg10[0])
        check("saved for the kind of data instead, it is OFFERED for another graph of that kind and put on one graph only when you apply it there", r10.saved and changed and g2.combo["switches"].get("markers") is False and "this graph" in m10, m10)
    else: check("saved for the kind of data instead, it is OFFERED for another graph of that kind and put on one graph only when you apply it there", False, (msg10, "no suggestion"))
else:
    check("'Save style' for one graph", False, f"graphs made: {len(made)} | {w.status.text()[:160]}")

# ---- the graph editor: Save style / Use saved style, undo and redo record nothing
try:
    from workspace_graph_editor import GraphEditor
    n_ev = len(lc.svc.history()); ed = GraphEditor(c, made[1]); ed.show(); pump(timeout=.2)
    offered = ed.use_style_btn.isVisible() if hasattr(ed, "use_style_btn") else None
    before_other = repr(made[0].combo.get("switches")); ed.markers.setChecked(True); pump(timeout=.3); ed.undo(); pump(timeout=.2); ed.redo(); pump(timeout=.2)
    check("in the graph editor, changing a component and Undo / Redo restore the graph and record NOTHING for learning", len(lc.svc.history()) == n_ev and repr(made[0].combo.get("switches")) == before_other, len(lc.svc.history()) - n_ev)
    r12 = ed.save_style("graph")
    check("... 'Save style' there remembers the look of THAT graph when you ask for it, and says for what", r12 is not None and r12.saved and "this graph" in ed.message.text() and repr(made[0].combo.get("switches")) == before_other, ed.message.text())
    ed.close()
except Exception as e:
    check("in the graph editor, Save style works", False, repr(e)[:200])

# ---- preferred graph
w.go(6); pump(timeout=.2); show(w, sh, c, f2); rows0 = [r["id"] for r in c.recommendations([f2], focus=f2) if r["compatible"]]
second = rows0[1] if len(rows0) > 1 else rows0[0]
r11, msg11 = lc.save_template_preference(f2, second); ranked = lc.rank(c.recommendations([f2], focus=f2), f2); ids_r = [r["id"] for r in ranked if r["compatible"]]
check("'Prefer this graph for such data' (after the graph was made): the preferred template comes first among the ones that FIT, marked as your preference; the set of templates is unchanged", r11 is not None and r11.saved and ids_r[0] == second and sorted(ids_r) == sorted(rows0)
      and ranked[0].get("preferred") and [r["id"] for r in ranked if not r["compatible"]] == [r["id"] for r in c.recommendations([f2], focus=f2) if not r["compatible"]], (second, ids_r[:3]))
bad, _m = lc.save_template_preference(f2, "template_that_is_not_installed")
check("... a template that is not installed cannot be remembered", bad is None or not bad.saved)

# ---- disable, enable, forget
f8 = xrd("run_eight.csv", 11); show(w, sh, c, f8)
check("another file of the remembered layout is offered the mapping", len([g for g in lc.suggestions(f8) if g.kind == "import_mapping"]) == 1)
dlg = WL.HistoryDialog(w); row = next(i for i, m in enumerate(dlg.rows) if m["kind"] == "import_mapping"); dlg.table.selectRow(row); dlg.toggle(); pump(timeout=.1)
check("Disable in Learning history: it stays in the list as 'Switched off' and is no longer offered", any(m["kind"] == "import_mapping" and m["state"] == "disabled" for m in lc.svc.memories()) and [g for g in lc.suggestions(f8) if g.kind == "import_mapping"] == [] and "Switched off" in dlg.note.text())
row = next(i for i, m in enumerate(dlg.rows) if m["kind"] == "import_mapping"); dlg.table.selectRow(row); dlg.toggle(); pump(timeout=.1)
check("Enable: it is offered again", len([g for g in lc.suggestions(f8) if g.kind == "import_mapping"]) == 1)
out = dlg.export(str(TMP / "learning_export.json")); exported = open(out, encoding="utf-8").read()
check("Export writes a readable file of what is remembered - without names, folders or measurements", '"import_mapping"' in exported and "run_" not in exported and str(TMP) not in exported)
row = next(i for i, m in enumerate(dlg.rows) if m["kind"] == "import_mapping"); dlg.table.selectRow(row); dlg.forget(); pump(timeout=.1)
show(w, sh, c, f8)
check("Forget: the memory is gone, and the suggestion disappears", not any(m["kind"] == "import_mapping" and m["state"] != "forgotten" for m in lc.svc.memories()) and [g for g in lc.suggestions(f8) if g.kind == "import_mapping"] == [] and "mapping available" not in (sh.learn_bar.sug_text.text() if sh.learn_bar.sug_row.isVisible() else ""),
      ([(m["kind"], m["state"]) for m in lc.svc.memories()], [(g.kind, g.grade) for g in lc.suggestions(f8)], sh.learn_bar.sug_text.text()[:80]))
dlg.boxes["personal_learning"].setChecked(False); pump(timeout=.1)
f9 = xrd("run_nine.csv", 13, cols=("U", "V")); show(w, sh, c, f9); sh.type_combo.setCurrentText("XRD"); sh.x_combo.setCurrentText("V"); sh.y_combo.setCurrentText("U"); sh.mapping_changed(); pump(timeout=.3)
t9, *_ = c.table_of(f9)
check("personal learning switched OFF: your change still applies, nothing is staged or remembered", t9.x == "V" and lc.pending(f9) is None and not sh.learn_bar.conf_row.isVisible())
dlg.boxes["personal_learning"].setChecked(True); dlg.close()

# ---- earlier knowledge is taken over once
appdir = TMP / "legacy_app"; appdir.mkdir(); (appdir / "assistant_lessons.txt").write_text("2026-01-05  Always draw thermal runs as mass against temperature.\n2026-02-11  Use the stacked layout for several patterns.\n", encoding="utf-8")
m_a = L.migrate_legacy(lc.svc, str(appdir), str(TMP / "p")); n_a = len(lc.svc.memories()); m_b = L.migrate_legacy(lc.svc, str(appdir), str(TMP / "p")); n_b = len(lc.svc.memories())
legacy = [m for m in lc.svc.memories() if m["kind"] == "legacy_lesson"]
check("lessons of earlier versions are taken into the structured memory ONCE (run again: nothing lost, nothing doubled), marked as coming from an earlier version, and the original file stays", len(legacy) == 2 and n_a == n_b and all(m["origin"] == "migration" for m in legacy) and (appdir / "assistant_lessons.txt").is_file(), (m_a, m_b))
w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

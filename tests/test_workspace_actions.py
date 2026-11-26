"""Modern window: right-click menus, mouse actions, the Save menu and keyboard shortcuts (real key presses), without a screen."""
import json, os, sys, tempfile, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TMP = Path(tempfile.mkdtemp(prefix="ws_actions_"))
os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_NO_OPEN"] = "1"; os.environ["ORIGIN_PLOT_APP_HOME"] = str(TMP / "store")
ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "origin_plot_app"; sys.path.insert(0, str(A))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import numpy as np
import workspace_qt as W, workspace_actions as WA, smart_plots as sp
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
app = QApplication.instance() or QApplication(sys.argv); app.setStyleSheet(W.STYLE)
def wait(c, t=120):
    t0 = time.time()
    while not c() and time.time() - t0 < t: app.processEvents(); time.sleep(0.02)
    app.processEvents(); return c()
E = A / "examples_synthetic"
w = W.Workspace([str(E / f) for f in ("xrd_raw.csv", "TGA_Ref_28d_rep1.txt", "TGA_Ref_28d_rep2.txt", "ftir.xlsx")]); w.resize(1500, 920); w.show()
wait(lambda: w.thread is None and w.list.count() > 0); w.outdir.setText(str(TMP / "results")); w.activateWindow(); app.processEvents()
saved = {}
WA.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (saved["path"], ""))
WA.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (saved["path"], ""))
def key(k, mod=Qt.NoModifier, target=None):
    QTest.keyClick(target or w, k, mod); app.processEvents()

# ---------------------------------------------------------------- keyboard
key(Qt.Key_F1)
check("F1 shows the card of mouse actions and shortcuts", hasattr(w, "shortcut_box") and "Ctrl+S" in w.shortcut_box.text() and "Right click" in w.shortcut_box.text())
dup = [k for k in WA.SHORTCUTS if k[2] is not None]; seqs = [a.shortcut().toString() for a in w.actions() if a.shortcut().toString()]          # the window-wide keys (list / graph keys are local to them)
check("no shortcut is given twice (a doubled key would do nothing)", len(seqs) == len(set(seqs)), sorted(s for s in seqs if seqs.count(s) > 1))
key(Qt.Key_2, Qt.ControlModifier | Qt.ShiftModifier)
check("Ctrl+Shift+2 opens Analysis", w.pages.currentIndex() == 1)
key(Qt.Key_1, Qt.ControlModifier | Qt.ShiftModifier)
i_x = next(i for i, it in enumerate(w.items) if "xrd_raw" in str(getattr(it, "path", "")))
w.list.setFocus(); w.list.setCurrentRow(i_x); app.processEvents()
key(Qt.Key_Space, target=w.list)
check("Space ticks the graph on show (in Your graphs)", w.list.item(i_x).checkState() == Qt.Checked)
key(Qt.Key_Space, target=w.list)
check("... and unticks it", w.list.item(i_x).checkState() == Qt.Unchecked)
key(Qt.Key_A, Qt.ControlModifier, target=w.list)
check("Ctrl+A ticks all", all(w.list.item(i).checkState() == Qt.Checked for i in range(w.list.count())))
key(Qt.Key_A, Qt.ControlModifier | Qt.ShiftModifier, target=w.list)
check("Ctrl+Shift+A unticks all", not w.ticked())
key(Qt.Key_F, Qt.ControlModifier)
check("Ctrl+F goes to the search box", w.search.hasFocus())
w.list.setFocus(); w.list.setCurrentRow(i_x); app.processEvents()
saved["path"] = str(TMP / "s1.json"); w.list.item(i_x).setCheckState(Qt.Checked)
key(Qt.Key_S, Qt.ControlModifier)
d = json.load(open(TMP / "s1.json", encoding="utf-8")) if (TMP / "s1.json").exists() else {}
check("Ctrl+S saves the session (the current window's format, plus ticks and your groups)", "files" in d and "graphs" in d and len(d["modern_ticked"]) == 1, list(d)[:8])
key(Qt.Key_E, Qt.ControlModifier); wait(lambda: w.job_thread is None, 200)
pub = sorted(p.suffix for p in (TMP / "results" / "publication").glob("*")) if (TMP / "results" / "publication").exists() else []
check("Ctrl+E saves this graph (PNG, PDF, SVG ...)", {".png", ".pdf", ".svg"} <= set(pub), pub)
ax = w.fig.axes[0]; x0 = ax.get_xlim()
w.canvas.setFocus(); key(Qt.Key_Z, target=w.canvas)
check("Z on the graph: zoom mode", "zoom" in str(w.navtb.mode).lower())
key(Qt.Key_S, target=w.canvas)
check("S on the graph: select-range mode (a letter, so only on the graph)", w.span is not None)
key(Qt.Key_Escape)
# ---------------------------------------------------------------- mouse
class Ev:  # a wheel event as matplotlib gives it
    def __init__(s, up): s.inaxes, s.button, s.xdata, s.ydata = ax, "up" if up else "down", 30.0, 1000.0
w.wheel_zoom(Ev(True)); x1 = ax.get_xlim()
check("mouse wheel up zooms in around the pointer", (x1[1] - x1[0]) < (x0[1] - x0[0]) and x1[0] < 30 < x1[1], (x0, x1))
w.reset_axes(); check("double click / Ctrl+R resets the axes", abs(ax.get_xlim()[0] - x0[0]) < 1e-6)
li = w.list.item(i_x); w.list.itemDoubleClicked.emit(li)
check("double click a graph in the list: tick / untick", li.checkState() == Qt.Unchecked)
# drag to change the order
first_single = next(i for i, it in enumerate(w.items) if it in w.singles); last = w.list.count() - 1
before = [s.title for s in w.singles]
it_ = w.list.takeItem(last); w.list.insertItem(first_single, it_); w.reorder_from_list()
check("dragging a graph in Your graphs changes the order of the graphs", [s.title for s in w.singles] == [before[-1]] + before[:-1], [s.title[:12] for s in w.singles])
# ---------------------------------------------------------------- right click
i_x = next(i for i, it in enumerate(w.items) if "xrd_raw" in str(getattr(it, "path", "")))
rect = w.list.visualItemRect(w.list.item(i_x)); m = w.menu_graphs(rect.center())
texts = [a.text() for a in m.actions()]
check("right click on a graph: tick, sample name, graph type, analyse, peak labels, group, draw, save, folder, remove",
      all(any(t.startswith(x) for t in texts) for x in ("Tick", "Sample name", "Graph type", "Analyse", "Peak labels", "Group the ticked", "Draw in Origin", "Save:", "Open the file", "Remove")), texts)
next(a for a in m.actions() if a.text() == "Tick only this one").trigger(); app.processEvents()
check("'Tick only this one' from the menu", [w.items.index(i) for i in w.ticked()] == [i_x])
r = w.quick_tool(w.items[i_x], "Find peaks"); job_done = wait(lambda: w.job_thread is None, 120)
check("right click > Analyse > Find peaks runs the tool on that graph", w.pages.widget(1).resmodel.rowCount() >= 3, w.pages.widget(1).msg.text()[:80])
w.go(0); w.list.setCurrentRow(i_x); app.processEvents()
mc = w.menu_canvas(w.canvas.rect().center())
check("right click on the graph: reset, zoom, pan, range, labels, copy, save view, save, draw", len([a for a in mc.actions() if a.text()]) >= 9, [a.text() for a in mc.actions() if a.text()])
w.copy_view(); check("copy the picture to the clipboard", not QApplication.clipboard().pixmap().isNull())
p = w.save_view(str(TMP / "view.svg")); check("save the view (with your zoom) as SVG / PNG / PDF", Path(p).exists() and Path(p).stat().st_size > 1000)
from PySide6.QtCore import QItemSelectionModel as _SM
w.dataview.selectionModel().select(w.datamodel.index(0, 0), _SM.SelectionFlag.Select); w.dataview.selectionModel().select(w.datamodel.index(1, 1), _SM.SelectionFlag.Select)
t = w.copy_table(w.dataview)
check("right click on the Data table: copy the selected cells (tab-separated, for Excel or Origin)", t.count("\n") == 2 and "\t" in t, t[:80])
mt = w.menu_table(w.dataview.rect().center(), w.dataview, "data"); check("table menu: copy, copy all, save", len([a for a in mt.actions() if a.text()]) == 3)
check("save the data table as CSV and as Excel", Path(w.save_table("data", str(TMP / "d.csv"))).exists() and Path(w.save_table("data", str(TMP / "d.xlsx"))).exists())
w.assistant.say("ai", "Hello **there**")
mch = w.menu_chat(w.assistant.view.rect().center()); check("right click in the chat: copy, copy all, save, new chat", any(a.text() == "Save the chat…" for a in mch.actions()))
check("save the chat as text", "Hello there" in open(w.save_chat(str(TMP / "chat.txt")), encoding="utf-8").read())
# remove, then open the session again in a new window
n = len(w.singles); w.list.setCurrentRow(i_x); w.list.setFocus(); key(Qt.Key_Delete, target=w.list)
check("Delete removes the graph from the list (not the file)", len(w.singles) == n - 1 and (E / "xrd_raw.csv").exists())
w2 = W.Workspace([]); w2.show(); saved["path"] = str(TMP / "s1.json"); r = w2.open_session()
check("Open a session (Ctrl+Shift+O): graphs, graph types and ticks come back", r == len(d["graphs"]) and len(w2.ticked()) == 1, r)
names = [a.text() for a in w.save_btn.menu().actions() if a.text()]
check("Save ▾ menu: graph, view, copy, PowerPoint, Word, data, results, session, open session, chat, results folder", len(names) == 11 and any("Ctrl+S" in x for x in names) and any("PowerPoint" in x for x in names) and any("Word" in x for x in names), names)
# ---------------------------------------------------------------- the graph as a picture in PowerPoint / Word
import zipfile, struct, office_export as OE
def png_size(b): return struct.unpack(">II", b[16:24])
exp = [a.text() for a in w.export_btn.menu().actions() if a.text()]
check("Export ▾ offers 'Send to PowerPoint' and 'Send to Word'", any("PowerPoint" in x for x in exp) and any("Word" in x and "600" in x for x in exp), exp)
w.tick_all(False); w.list.setCurrentRow(i_x); app.processEvents()
pp = w.send_to_office("pptx"); z = zipfile.ZipFile(pp) if pp else None
check("Send to PowerPoint: a .pptx in the results folder with the graph on show as a picture on one slide", bool(pp) and pp.endswith(".pptx") and str(TMP / "results") in pp and sum(n.startswith("ppt/slides/slide") for n in z.namelist()) == 1 and z.read("ppt/media/image1.png")[:8] == b"\x89PNG\r\n\x1a\n", pp)
pic = z.read("ppt/slides/slide1.xml").decode(); import re as _re
m_ = _re.search(r'<a:off x="(\d+)" y="(\d+)"/><a:ext cx="(\d+)" cy="(\d+)"/>', pic); x_, y_, cx_, cy_ = [int(v) / 914400 for v in m_.groups()]; pw_, ph_ = png_size(z.read("ppt/media/image1.png"))
check("... the picture keeps its proportions, fills the slide up to a margin and is centred", abs(cx_ / cy_ - pw_ / ph_) < 0.01 and x_ >= 0.3 and y_ >= 0.3 and abs(x_ * 2 + cx_ - 13.333) < 0.01 and abs(y_ * 2 + cy_ - 7.5) < 0.01 and (abs(cx_ - 12.633) < 0.01 or abs(cy_ - 6.8) < 0.01), (x_, y_, cx_, cy_))
wd = w.send_to_office("docx"); zd = zipfile.ZipFile(wd) if wd else None
dw, dh = png_size(zd.read("word/media/image1.png")); ext = _re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"/>', zd.read("word/document.xml").decode()); ew = int(ext.group(1)) / 914400
check("Send to Word: a .docx with the graph as a picture of 600 dots per inch at its printed size (at most the width of the text)", bool(wd) and wd.endswith(".docx") and ew <= 6.31 and dw / ew >= 599, (dw, dh, ew, dw / ew))
pp2 = w.send_to_office("pptx")
check("an earlier presentation is never written over (it may be open in PowerPoint): the next one gets a number", pp2 != pp and os.path.isfile(pp) and os.path.isfile(pp2), pp2)
for r_ in range(w.list.count()):
    if isinstance(w.items[r_], sp.Item) and sum(i.checkState() == Qt.Checked for i in [w.list.item(k) for k in range(w.list.count())]) < 3: w.list.item(r_).setCheckState(Qt.Checked)
app.processEvents(); nt_ = len([i for i in w.ticked() if isinstance(i, (sp.Item, sp.Combined, sp.Board))])
pp3 = w.send_to_office("pptx"); z3 = zipfile.ZipFile(pp3)
check("with several graphs ticked: one slide for each", nt_ == 3 and sum(1 for n in z3.namelist() if _re.fullmatch(r"ppt/slides/slide\d+\.xml", n)) == 3 and z3.read("ppt/presentation.xml").decode().count("<p:sldId ") == 3 and z3.read("[Content_Types].xml").decode().count("presentationml.slide+xml") == 3, nt_)
try:
    from pptx import Presentation; from docx import Document
    P_ = Presentation(pp3); D_ = Document(wd)
    check("the files open as real Office files (read back with python-pptx and python-docx)", len(P_.slides) == 3 and all(len(s.shapes) == 1 and s.shapes[0].shape_type == 13 for s in P_.slides) and len(D_.inline_shapes) == 1)
except ImportError:
    print("SKIP  python-pptx / python-docx are not installed here: the files were checked as zip packages only")
import self_update as SU_
prog = [f.replace("\\", "/") for f in SU_.program_files(str(A))]
check("the two empty Office files are among the files the app's updater installs (in a folder of their own an updated app did not get them, and the export wrote nothing)",
      "opstudio/office/blank.pptx" in prog and "opstudio/office/blank.docx" in prog and os.path.isfile(OE.template("blank.pptx")) and os.path.isfile(OE.template("blank.docx")), [f for f in prog if "office" in f])
import importlib, glob as _glob
needed = [p for p in _glob.glob(str(A / "**" / "*"), recursive=True) if os.path.isfile(p) and "__pycache__" not in p and os.path.splitext(p)[1].lower() in (".pptx", ".docx", ".xlsx", ".csv", ".json", ".ogs", ".png")]
outside = sorted(os.path.relpath(p, A).replace("\\", "/") for p in needed if os.path.relpath(p, A).replace("\\", "/") not in prog and os.path.basename(p) not in SU_.NEVER
                 and not os.path.relpath(p, A).replace("\\", "/").startswith(("dry_out", "examples_synthetic/dry_out", "config/")))          # (config/ holds an example of a settings file of yours, not a part of the program)
check("no data file of the program lies outside what the updater installs", outside == [], outside[:8])
real_tpl = OE.TEMPLATES; OE.TEMPLATES = str(TMP / "nowhere"); bad = w.send_to_office("pptx"); OE.TEMPLATES = real_tpl
check("an installation without the Office files says so plainly instead of doing nothing", bad is None and "missing from this installation" in w.status.text() and "Update the app once more" in w.status.text(), w.status.text()[:160])
# ---- a figure of two graphs: each graph for itself
two = next((i for i in w.items if isinstance(i, sp.Combined) and len((getattr(i, "spec", None) or {}).get("panels", [])) == 2), None)
if two is None:
    for i in w.items:
        if isinstance(i, sp.Combined):
            try: i.build(w.opt) if getattr(i, "spec", None) is None else None
            except Exception: pass
    two = next((i for i in w.items if isinstance(i, sp.Combined) and len((getattr(i, "spec", None) or {}).get("panels", [])) == 2), None)
check("the thermal runs give a figure of two graphs (mass above, DTG below)", two is not None, [type(i).__name__ for i in w.items][:6])
if two is not None:
    w.go(0); w.list.setCurrentRow(w.items.index(two)); app.processEvents(); w.canvas.draw(); axs = w.main_axes()
    check("the figure on show has one axes per graph", len(axs) == 2, len(axs))
    w.modes.button(2).setChecked(False); app.processEvents(); w.modes.button(2).setChecked(True); app.processEvents(); axs = w.main_axes()
    check("Select range can be dragged in every graph of the figure (it could only be dragged in the first)", len(getattr(w, "spans", [])) == 2 and {id(s_.ax) for s_ in w.spans} == {id(a) for a in axs})
    w.on_span(200.0, 300.0, axs[1]); app.processEvents(); names_b = [c_.yname for c_ in w.curves(two)]
    check("a range selected in graph (b) belongs to graph (b): the line says so, and what is worked out uses the curves of graph (b)", w.sel == (200.0, 300.0) and w.sel_panel == 1 and "graph (b) of 2" in w.seltext.text()
          and names_b and all(n_ == str(two.spec["panels"][1].get("yname")) for n_ in names_b), (w.seltext.text(), names_b[:2]))
    w.on_span(200.0, 300.0, axs[0]); names_a = [c_.yname for c_ in w.curves(two)]
    check("... and one selected in graph (a) to graph (a)", w.sel_panel == 0 and names_a and all(n_ == str(two.spec["panels"][0].get("yname")) for n_ in names_a), names_a[:2])
    w.clear_selection(); w.modes.button(2).setChecked(False); app.processEvents()
    full = [a.get_ylim() for a in axs]
    for a in axs: lo_, hi_ = a.get_ylim(); a.set_ylim(lo_ + 0.25 * (hi_ - lo_), hi_ - 0.25 * (hi_ - lo_))
    zoomed = [a.get_ylim() for a in axs]; w._last_ax = axs[1]; w._reset_one = None; r_ = w.reset_axes()
    check("Reset axes brings back the graph you last worked in; the other graph keeps its view", r_ == "one" and np.allclose(axs[1].get_ylim(), full[1]) and np.allclose(axs[0].get_ylim(), zoomed[0]) and "other graphs keep their view" in w.status.text(), (r_, axs[0].get_ylim(), zoomed[0]))
    r_ = w.reset_axes(); app.processEvents()
    check("... a second Reset brings back all graphs", r_ == "all")
# ---- straight into the open PowerPoint / Word (Windows automation, here with stand-ins that write down what they are asked)
import types as _types
calls = []
class _Rec:
    def __init__(self, name, **kw): self.__dict__["_n"] = name; self.__dict__.update(kw)
    def __setattr__(self, k, v): calls.append((self._n + "." + k, v)); self.__dict__[k] = v
class _Slides:
    def __init__(self): self.Count = 2
    def Add(self, index, layout):
        calls.append(("Slides.Add", index, layout)); self.Count += 1
        shapes = _types.SimpleNamespace(AddPicture=lambda f, link, save, l, t, w_, h_: (calls.append(("AddPicture", os.path.basename(f), link, save, round(l, 1), round(t, 1), round(w_, 1), round(h_, 1))) or _Rec("pic")))
        return _types.SimpleNamespace(Shapes=shapes, SlideIndex=index)
pres_ = _types.SimpleNamespace(Slides=_Slides(), PageSetup=_types.SimpleNamespace(SlideWidth=960.0, SlideHeight=540.0), Name="Talk.pptx")
ppt_ = _Rec("ppt", Presentations=_types.SimpleNamespace(Count=1, Add=lambda: pres_), ActivePresentation=pres_, ActiveWindow=_types.SimpleNamespace(View=_types.SimpleNamespace(GotoSlide=lambda i: calls.append(("GotoSlide", i)))), Activate=lambda: None)
sel_ = _Rec("sel", InlineShapes=_types.SimpleNamespace(AddPicture=lambda f, link, save: (calls.append(("Word.AddPicture", os.path.basename(f), link, save)) or _Rec("shape", Width=900.0))), ParagraphFormat=_Rec("para"), TypeParagraph=lambda: calls.append(("TypeParagraph",)))
doc_ = _types.SimpleNamespace(PageSetup=_types.SimpleNamespace(PageWidth=595.0, LeftMargin=70.0, RightMargin=70.0), Name="Paper.docx")
word_ = _Rec("word", Documents=_types.SimpleNamespace(Count=1, Add=lambda: doc_), ActiveDocument=doc_, Selection=sel_, Activate=lambda: None)
real_office = OE._office; OE._office = lambda name: ppt_ if name.startswith("PowerPoint") else word_
w.tick_all(False); app.processEvents(); w._office_live = True; w.list.setCurrentRow(i_x); app.processEvents()
r1 = w.send_to_office("pptx"); add_ = next((c for c in calls if c[0] == "AddPicture"), None)
check("Send to PowerPoint puts the graph on a NEW slide at the end of the presentation you have open, as a picture that fits the slide, and shows that slide",
      r1 == "live" and ("Slides.Add", 3, 12) in calls and add_ is not None and add_[2] is False and add_[3] is True and add_[4] >= 25 and add_[5] >= 25 and abs(add_[4] * 2 + add_[6] - 960) < 1 and abs(add_[5] * 2 + add_[7] - 540) < 1
      and ("GotoSlide", 3) in calls and "the open presentation 'Talk.pptx'" in w.status.text(), (add_, w.status.text()[:110]))
calls.clear(); r2 = w.send_to_office("docx")
check("Send to Word inserts the picture at the cursor of the document you have open, no wider than its text, centred, in its own paragraph",
      r2 == "live" and any(c[0] == "Word.AddPicture" and c[2] is False and c[3] is True for c in calls) and ("shape.Width", 455.0) in calls or r2 == "live" and any(c[0] == "shape.Width" and c[1] <= 455.0 for c in calls) and ("TypeParagraph",) in calls
      and "the open document 'Paper.docx'" in w.status.text(), (calls[:6], w.status.text()[:100]))
def _refuse(name): raise RuntimeError("the program is not installed")
OE._office = _refuse; n_files = len(list((TMP / "results").rglob("*.pptx"))); r3 = w.send_to_office("pptx")
check("PowerPoint not there (or refusing): the presentation is written as a file instead, as before", isinstance(r3, str) and r3.endswith(".pptx") and os.path.isfile(r3) and len(list((TMP / "results").rglob("*.pptx"))) == n_files + 1, r3)
OE._office = real_office; w._office_live = False
w.tick_all(False); app.processEvents()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

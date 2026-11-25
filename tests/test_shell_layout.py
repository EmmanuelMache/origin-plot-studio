"""The redesigned window: one top bar, panels everywhere (move, resize, close, reopen, kept between sessions, reset), Analysis and Gallery
graphs as browser / setup / preview (and gallery), every entry opening at once, the workflow from files to Workspace, readable at common
desktop sizes."""
import os, sys, tempfile, json, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
SET = Path(tempfile.mkdtemp()) / "settings_modern.json"; os.environ["OPS_SETTINGS_FILE"] = str(SET)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "tests"))
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
from PySide6.QtWidgets import QApplication, QDockWidget, QScrollArea
from PySide6.QtCore import Qt
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W, smart_plots as sp, workspace_shell as SH
app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)
EX = ROOT / "origin_plot_app" / "examples_synthetic"
SET.write_text(json.dumps({"layout": "Side by side", "panel_layout": "not an arrangement"}), encoding="utf-8")   # older settings with a 'layout' of their own
w = W.Workspace([]); w.resize(1366, 768); w.show(); app.processEvents()
check("starts with older settings that have a 'layout' entry of their own (and a damaged arrangement)", w.isVisible() and W.load_cfg().get("layout") == "Side by side")
# ---------------------------------------------------------------- one top bar
check("one top bar: the sections, Find, File / View / Tools / Help, Add files; no menu bar, no side bar",
      [b.text() for b in w.header_nav.buttons()] == ["Start here", "Workbook", "Workspace", "Analysis", "Settings"] and w.file_btn.isVisible()
      and w.panels_btn.text().startswith("View") and w.assistant_toggle.isVisible() and not w.menuBar().isVisible() and not w.navw.isVisible())
check("the colours: navy top bar, blue primary, orange only for Origin", "#17324D" in W.STYLE and "#2563EB" in W.STYLE and W.ACCENT == "#B4532A" and w.b_draw.objectName() == "accent")
check("the keyboard shortcuts of the old menus still work (window actions)", any(a.shortcut().toString() == "Ctrl+N" for a in w.actions()))
w.header_nav.button(1).click(); app.processEvents()
check("a click on Analysis opens its graphs and templates; the formatting ribbon is for Workspace only", w.pages.currentIndex() == 5 and not w.ribbon.isVisible())
w.gallery_switch[5].button(1).click(); app.processEvents()
check("the switch at the top of Analysis shows the calculations", w.pages.currentIndex() == 1 and w.header_nav.button(1).isChecked())
# ---------------------------------------------------------------- Analysis: every entry opens at once
pa = w.pages.widget(1); pt = w.pages.widget(2)
check("Analysis: browser, setup, preview and gallery are panels", all(isinstance(d, QDockWidget) for d in pa.docks) and len(pa.docks) == 4)
check("... the first entry is open as soon as the page is seen (no extra click)", pa.entry_row is not None and pa.title.text() == pa.entry_row[0])
bad = []
for p_ in (pa, pt):
    for i in range(p_.tree.topLevelItemCount()):
        top = p_.tree.topLevelItem(i)
        for j in range(top.childCount()):
            try:
                p_.tree.setCurrentItem(top.child(j)); app.processEvents()
                if p_.title.text() != top.child(j).text(0) or (p_.buttons.count() == 0 and p_.form.rowCount() == 0 and p_.extra.count() == 0):
                    bad.append(top.child(j).text(0))
            except Exception as e:
                bad.append(f"{top.child(j).text(0)}: {e}")
n_all = sum(p_.tree.topLevelItem(i).childCount() for p_ in (pa, pt) for i in range(p_.tree.topLevelItemCount()))
check(f"every one of the {n_all} entries of Analysis and Graph gallery opens its setup directly (settings and a Run button)", not bad, bad[:5])
top = pa.tree.topLevelItem(2); pa.tree.setCurrentItem(None); pa.group_clicked(top)
check("a click on a category opens its first entry", pa.entry_row is not None and pa.entry_row[0] == top.child(0).text(0))
pa.tree.setCurrentItem(pa.find_entry("Savitzky")); app.processEvents()
check("without files: an illustration, said to be one", "Illustrative example" in pa.pcaption.text() and not pa.open_ws.isEnabled(), pa.pcaption.text())
check("the gallery of Analysis: a picture for each kind of analysis", pa.gallery.count() >= 15, pa.gallery.count())
# ---------------------------------------------------------------- files -> inspect -> preview -> run -> Workspace
w.load_sync([str(EX / "xrd_raw.csv")]); app.processEvents()
w._tick_only([w.singles[0]]); pa.update_workson(); app.processEvents()
check("Files: the chosen file and its data columns are shown", pa.inputs.rowCount() == 1 and "xrd_raw" in pa.inputs.item(0, 0).text() and pa.inputs.item(0, 2).text(), pa.inputs.item(0, 2).text() if pa.inputs.rowCount() else "")
check("Preview: your own data (not an illustration)", pa.pcaption.text().startswith("✓ Your data") and pa.pbox.isVisible() and pa.open_ws.isEnabled())
pa.inputs.selectRow(0); app.processEvents()
check("Inspect: the data table of that file", pa.dmodel.rowCount() > 100)
form_before = None
le = [c for c in pa.formbox.findChildren(W.QLineEdit)]
if le:
    le[0].setText("31"); form_before = le[0].text()
pa.tree.setCurrentItem(pa.find_entry("Moving average")); app.processEvents(); pa.tree.setCurrentItem(pa.find_entry("Savitzky")); app.processEvents()
le2 = [c for c in pa.formbox.findChildren(W.QLineEdit)]
check("going back to an entry: your settings are still there", form_before is None or (le2 and le2[0].text() == form_before), (form_before, le2[0].text() if le2 else None))
n0 = len(w.singles)
run = next(pa.buttons.itemAt(k).widget() for k in range(pa.buttons.count()) if pa.buttons.itemAt(k).widget().objectName() == "primary")
run.click(); app.processEvents()
t0 = time.time()
while (w.job_thread is not None or w.thread is not None or not pa.pcaption.text().startswith("✓ Result")) and time.time() - t0 < 60: app.processEvents(); time.sleep(0.05)
check("Run: the result comes to Your graphs and is previewed here", len(w.singles) == n0 + 1 and pa.pcaption.text().startswith("✓ Result"), pa.pcaption.text())
res = pa._shown
pa.open_ws.click(); app.processEvents()
check("Open in Workspace: the result is shown there, to edit and export", w.pages.currentIndex() == 0 and w.current() is res)
w.go(1); w._tick_only([]); w.list.setCurrentRow(-1); pa.update_workson()
pa.tree.setCurrentItem(pa.find_entry("Mass loss")); app.processEvents()
b_ = next(pa.buttons.itemAt(k).widget() for k in range(pa.buttons.count()))
b_.click(); app.processEvents()
check("a message that needs attention is shown beside Run, coloured (with its words)", pa.msg.text() and getattr(pa.msg, "kind", "") in ("warn", "error"), (pa.msg.text()[:80], getattr(pa.msg, "kind", "")))
# ---------------------------------------------------------------- Graph gallery: the gallery
w.go(2); app.processEvents()
pt.tree.setCurrentItem(pt.find_entry("G07")); app.processEvents()
check("Graph gallery: a gallery beside the categories, with a picture of each type of the category", pt.gallery_dock.isVisible() and pt.gallery.count() >= 3
      and all(pt.gallery.item(i).icon() is not None for i in range(pt.gallery.count())))
check("... the chosen type is shown as chosen in the gallery", pt.gallery.currentItem() is not None and pt.gallery.currentItem().data(Qt.UserRole).startswith("G07"))
it8 = next(pt.gallery.item(i) for i in range(pt.gallery.count()) if str(pt.gallery.item(i).data(Qt.UserRole)).startswith("G08"))
pt.gallery_chosen(it8); app.processEvents()
check("a click on a picture opens that type", pt.entry_row[0].startswith("G08") and "Illustrative" in pt.pcaption.text())
check("26 figtype pictures are shipped", len(list((ROOT / "origin_plot_app" / "gallery").glob("type_*.png"))) == 26)
pt.gallery_dock.close(); app.processEvents(); check("the gallery can be closed …", not pt.gallery_dock.isVisible())
pt.gallery_dock.toggleViewAction().trigger(); app.processEvents(); check("… and reopened (View › Panels)", pt.gallery_dock.isVisible())
# ---------------------------------------------------------------- Workspace panels
w.go(0); app.processEvents()
check("Workspace: Your graphs, Graph, Data, Results, Details and Graph settings are panels (each with a header to drag)",
      len(w.ws_docks) == 6 and all(d.features() & QDockWidget.DockWidgetMovable and d.features() & QDockWidget.DockWidgetClosable for d in w.ws_docks))
items0 = list(w.items); singles0 = list(w.singles)
w.graph_dock.close(); w.graphs_dock.close(); app.processEvents()
check("closing panels loses nothing (graphs, files, results)", w.items == items0 and w.singles == singles0)
w.graph_dock.toggleViewAction().trigger(); w.graphs_dock.toggleViewAction().trigger(); app.processEvents()
check("View › Panels reopens them", w.graph_dock.isVisible() and w.graphs_dock.isVisible())
w.settings_dock.setFloating(True); app.processEvents()
check("a panel can be taken out as its own window", w.settings_dock.isFloating())
w.settings_dock.setFloating(False)
w.wsmain.resizeDocks([w.graphs_dock], [230], Qt.Horizontal); app.processEvents(); a_ = w.graphs_dock.width()
w.wsmain.resizeDocks([w.graphs_dock], [330], Qt.Horizontal); app.processEvents(); b_ = w.graphs_dock.width()
check("panels can be resized (wider, narrower)", b_ > a_ + 30, (a_, b_))
w.tabs.setCurrentWidget(w.details); app.processEvents()
check("Details comes to the front when it has news", w.details_dock.isVisible())
check("the graph keeps its proportions", abs(w.canvas.width() / max(1, w.canvas.height()) - w.canvas_box.ratio) < 0.05, (w.canvas.width(), w.canvas.height(), w.canvas_box.ratio))
sec = list(w.sections)
check("Graph settings in sections that fold: " + ", ".join(sec), len(sec) >= 4)
SH.fold_section(w, sec[2], True); app.processEvents()
check("... folding a section hides its fields and is remembered", not any(x.isVisible() for x in w.sections[sec[2]]["widgets"]) and sec[2] in W.load_cfg().get("folded_sections", []))
SH.fold_section(w, sec[2], False)
long_ = [w.list.item(i).text() for i in range(w.list.count())]
check("Your graphs: concise names, the whole name on hover", all(w.list.item(i).toolTip() for i in range(w.list.count())))
# ---------------------------------------------------------------- the layout: kept between sessions, reset
w.details_dock.close(); w.graphs_dock.close(); app.processEvents()
pa.gallery_dock.close()
w.close(); app.processEvents()
lay = W.load_cfg().get("panel_layout") or {}
check("closing the window saves the arrangement", lay.get("v") == SH.LAYOUT_VERSION and lay.get("ws") and lay.get("page1"))
w2 = W.Workspace([]); w2.resize(1366, 768); w2.show(); app.processEvents()
check("restart: your arrangement is back (the panels you closed stay closed)", not w2.graphs_dock.isVisible() and not w2.details_dock.isVisible() and w2.graph_dock.isVisible())
w2.reset_layout(); app.processEvents()
check("View › Reset layout: every panel back in place", w2.graphs_dock.isVisible() and w2.settings_dock.isVisible() and w2.graph_dock.isVisible()
      and all(d.isVisible() or w2.wsmain.tabifiedDockWidgets(d) for d in w2.ws_docks) and W.load_cfg().get("panel_layout") == {})
check("Reset layout is in the View menu", any(a.text() == "Reset layout" for a in w2.panels_btn.menu().actions()))
# ---------------------------------------------------------------- common desktop sizes: nothing out of reach
for size in ((1366, 768), (1600, 900), (1920, 1080)):
    w2.resize(*size); app.processEvents()
    hdr_ok = all(b.geometry().right() <= w2.rect().width() for b in (w2.file_btn, w2.panels_btn, w2.tools_btn, w2.help_btn, w2.header_add))
    sa = next(x for x in w2.settings_card.findChildren(QScrollArea))
    clip = sa.widget().minimumSizeHint().width() > sa.viewport().width() + 2
    check(f"{size[0]}×{size[1]}: the top bar fits, Graph settings fit their panel (or scroll), the graph has the largest area",
          hdr_ok and (not clip or sa.horizontalScrollBar().maximum() > 0) and w2.graph_dock.width() >= max(w2.graphs_dock.width(), w2.settings_dock.width()),
          (hdr_ok, clip, w2.graph_dock.width(), w2.graphs_dock.width(), w2.settings_dock.width()))
w2.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

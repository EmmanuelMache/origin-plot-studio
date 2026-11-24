"""Lists every command of the running window (menus, ribbon, graph tool bar, shortcuts, panels) as a Markdown table.
Run: python tools/command_inventory.py > inventory.md   (no screen needed: QT_QPA_PLATFORM=offscreen)"""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
os.environ.setdefault("OPS_SETTINGS_FILE", tempfile.mktemp(suffix=".json"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "origin_plot_app"))
from PySide6.QtWidgets import QApplication, QToolButton, QPushButton, QDockWidget
from PySide6.QtGui import QShortcut
app = QApplication.instance() or QApplication([])
import workspace_qt as W
w = W.Workspace([]); w.show(); app.processEvents()
rows = []
def walk(menu, path):
    for a in menu.actions():
        if a.isSeparator(): continue
        t = a.text().replace("&", "").split("\t")
        if a.menu() is not None: walk(a.menu(), path + " ▸ " + t[0]); continue
        rows.append((t[0], path, a.shortcut().toString() or (t[1] if len(t) > 1 else ""), (a.toolTip() or "") if a.toolTip() != a.text() else ""))
for name, btn in (("File", w.file_btn), ("View", w.panels_btn), ("Tools", w.tools_btn), ("Help", w.help_btn)):
    walk(btn.menu(), "Top bar ▸ " + name)
rb = w.ribbon
for i in range(rb.count()):
    for b in rb.stack.widget(i).findChildren(QToolButton):
        if b.text() or b.toolTip(): rows.append((b.text() or b.toolTip().split(" (")[0], f"Ribbon ▸ {rb.tabText(i)}", "", b.toolTip()))
for b in w.findChildren(QPushButton):
    if b.text() and b.isVisibleTo(w) and b.objectName() not in ("navtab", "menu", "section"):
        rows.append((b.text(), "Workspace (button)", "", b.toolTip()))
for sc in w.findChildren(QShortcut):
    rows.append(("(shortcut)", "window", sc.key().toString(), ""))
for d in w.findChildren(QDockWidget):
    rows.append((d.windowTitle().replace("⠿", "").strip(), "Panel (" + d.objectName() + ")", "", "movable, floatable, closable"))
print("| Command | Location | Shortcut | Tooltip |\n|---|---|---|---|")
for r in rows: print("| " + " | ".join(str(x).replace("|", "/").replace("\n", " ")[:110] for x in r) + " |")
print(f"\n{len(rows)} entries; {sum(1 for r in rows if r[1].startswith(('Ribbon', 'Workspace')) and not r[3])} buttons without a tooltip", file=sys.stderr)

"""Origin Plot Studio - modern window: mouse actions, right-click menus, the Save menu and keyboard shortcuts.

  Right click   Your graphs (show, tick, sample name, graph type, analyse, label peaks, group, draw, save, remove, open the folder),
                the graph (reset, zoom, pan, select range, integrate, copy, save the view, label peaks), the Data and Results tables
                (copy, save as CSV or Excel) and the chat (copy, save, clear).
  Left click    a graph shows it; double click ticks or unticks it; drag graphs to change their order; drop files on the window.
  On the graph  the mouse wheel zooms around the pointer; double click resets the axes.
  Save ▾        this graph (PNG 600 dpi, TIFF, PDF, SVG), the view as a picture, the data table, the results, the session, the chat.
  Shortcuts     listed in SHORTCUTS and on the card that F1 (or Help ▸ Keyboard shortcuts) shows.
Every action calls a function the window already has; nothing here calculates.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import QAbstractItemView, QApplication, QFileDialog, QInputDialog, QMenu, QMessageBox, QPushButton

import smart_plots as sp
from workspace_workbook import arrange_workbook

# (shortcut, what it does, method name on the window or a callable taking the window)
SHORTCUTS = [
    ("Ctrl+O", "Add data files", None),
    ("Ctrl+S", "Save the session (files, graph types, sample names, figures)", lambda w: (w.save() if hasattr(w, "save") else w.save_session())),
    ("Ctrl+Shift+O", "Open a saved session", "open_session"),
    ("Ctrl+E", "Save this graph: PNG 600 dpi, TIFF, PDF, SVG (journal size)", "save_current"),
    ("Ctrl+Shift+E", "Save the view on screen as a picture", "save_view"),
    ("Ctrl+Shift+C", "Copy the graph on screen as a picture", "copy_view"),
    ("F5", "Draw the ticked graphs in Origin", lambda w: w.draw_origin("ticked")),
    ("Shift+F5", "Draw all graphs in Origin", lambda w: w.draw_origin("all")),
    ("Ctrl+A", "Tick all graphs", lambda w: w.tick_all(True)),
    ("Ctrl+Shift+A", "Untick all graphs", lambda w: w.tick_all(False)),
    ("Space", "Tick / untick the graph on show (in Your graphs)", "toggle_tick"),
    ("Delete", "Remove the highlighted graph(s), or the graph on show, from the list (the file stays)", "remove_current_or_selected"),
    ("Ctrl+F", "Find a graph by name", lambda w: (w.go(0), w.search.setFocus(), w.search.selectAll())),
    ("Ctrl+R", "Reset the axes of the graph", "reset_axes"),
    ("Z", "Zoom mode on the graph (drag a box)", lambda w: w.modes.button(0).click()),
    ("P", "Pan mode on the graph", lambda w: w.modes.button(1).click()),
    ("S", "Select-range mode on the graph", lambda w: w.modes.button(2).click()),
    ("Ctrl+I", "Integrate the selected range", "integrate"),
    ("Ctrl+L", "Label the peaks of the ticked graphs (positions)", lambda w: w.tools.labels_auto({"n": 8, "prom": 5, "digits": 4})),
    ("Ctrl+G", "Stack the ticked graphs (your group)", lambda w: w.group_ticked("stack")),
    ("Ctrl+Shift+G", "Overlay the ticked graphs (your group)", lambda w: w.group_ticked("overlay")),
    ("Ctrl+K", "Show the assistant and type", lambda w: w.show_assistant(True)),
    ("Ctrl+Return", "Send the message (in the assistant)", None),
    ("Ctrl+1 … Ctrl+4", "Show / minimise side bar, Your graphs, graph settings, assistant", None),
    ("F11", "Focus on the graph (everything else minimised)", None),
    ("Ctrl+Shift+1 … 5", "Workspace, Analysis, Graph gallery, Assistant, Settings", None),
    ("Esc", "Clear the selected range", None),
    ("F1", "This list", "show_shortcuts"),
]


def install(w):
    """Add the actions to a Workspace window."""
    import types
    for name, fn in METHODS.items():
        setattr(w, name, types.MethodType(fn, w))
    typing = {"Space", "Delete", "Z", "P", "S", "Ctrl+A", "Ctrl+Shift+A"}         # keys that are letters in a text box: only on the graph and the list
    w.shortcut_actions = {}
    for key, what, target in SHORTCUTS:
        if target is None:
            continue
        fn = (lambda _c=False, m=target: getattr(w, m)()) if isinstance(target, str) else (lambda _c=False, f=target: f(w))
        a = QAction(what, w)
        a.setShortcut(QKeySequence(key))
        a.triggered.connect(fn)
        if key in typing:
            a.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            (w.list if key in ("Space", "Delete", "Ctrl+A", "Ctrl+Shift+A") else w.canvas).addAction(a)
            if key in ("Ctrl+A", "Ctrl+Shift+A"):
                b = QAction(what, w)
                b.setShortcut(QKeySequence(key))
                b.setShortcutContext(Qt.WidgetWithChildrenShortcut)
                b.triggered.connect(fn)
                w.canvas.addAction(b)
        else:
            w.addAction(a)
        w.shortcut_actions[key] = a
    for i in range(5):
        a = QAction(w)
        a.setShortcut(QKeySequence(f"Ctrl+Shift+{i + 1}"))
        a.triggered.connect(lambda _c=False, i=i: w.go(i))
        w.addAction(a)
    w.canvas.setFocusPolicy(Qt.ClickFocus)
    # right-click menus
    for widget, builder in ((w.list, w.menu_graphs), (w.canvas, w.menu_canvas), (w.dataview, lambda p: w.menu_table(p, w.dataview, "data")),
                            (w.resview, lambda p: w.menu_table(p, w.resview, "results")), (w.assistant.view, w.menu_chat)):
        widget.setContextMenuPolicy(Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(builder)
    for v in (w.dataview, w.resview):
        v.setSelectionMode(QAbstractItemView.ExtendedSelection)
    # left click / drag: double click ticks; drag to change the order
    w.list.itemDoubleClicked.connect(lambda it: it.setCheckState(Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked))
    w.list.setDragDropMode(QAbstractItemView.InternalMove)
    w.list.setDefaultDropAction(Qt.MoveAction)
    w.list.model().rowsMoved.connect(lambda *_a: w.reorder_from_list())
    # the graph: wheel zoom around the pointer, double click resets
    w.canvas.mpl_connect("scroll_event", w.wheel_zoom)
    w.canvas.mpl_connect("button_press_event", lambda e: (None if (hasattr(w, "ribbon") and w.ribbon.on_double(e)) else w.reset_axes())
                         if getattr(e, "dblclick", False) and e.button == 1 else None)          # double click on a title: type it; elsewhere: reset the axes
    # Save ▾ and Help in the top bar
    top = w.panels_btn.parentWidget().layout()
    sb = QPushButton("Save ▾")
    sb.setToolTip("Save this graph, the view, the data or results table, the session, the chat (Ctrl+S saves the session)")
    m = QMenu(sb)
    for text, fn, key in (("This graph: PNG 600 dpi · TIFF · PDF · SVG", w.save_current, "Ctrl+E"), ("The view on screen as a picture…", w.save_view, "Ctrl+Shift+E"),
                          ("Copy the view to the clipboard", w.copy_view, "Ctrl+Shift+C"),
                          ("Send to PowerPoint: the graph as a picture on a slide", lambda: w.send_to_office("pptx"), ""), ("Send to Word: the graph as a high-definition picture (600 dpi)", lambda: w.send_to_office("docx"), ""), (None, None, None),
                          ("Data table as CSV or Excel…", lambda: w.save_table("data"), ""), ("Results table as CSV or Excel…", lambda: w.save_table("results"), ""),
                          (None, None, None), ("Session…", w.save_session, "Ctrl+S"), ("Open a session…", w.open_session, "Ctrl+Shift+O"),
                          ("The chat as a text file…", w.save_chat, ""), (None, None, None), ("Open the results folder", w.open_results, "")):
        if text is None:
            m.addSeparator()
            continue
        m.addAction(text + (f"\t{key}" if key else ""), fn)          # the key is shown; the window's own shortcut does the work
    sb.setMenu(m)
    top.insertWidget(top.indexOf(w.panels_btn), sb)
    hb = QPushButton("?")
    hb.setToolTip("Mouse actions and keyboard shortcuts (F1)")
    hb.setFixedWidth(34)
    hb.clicked.connect(w.show_shortcuts)
    top.insertWidget(top.indexOf(w.panels_btn) + 1, hb)
    w.save_btn = sb


# ---------------------------------------------------------------------------------------------- the actions (methods of the window)
def tick_all(self, on=True):
    for i in range(self.list.count()):
        if not self.list.item(i).isHidden():
            self.list.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)
    self.update_count()


def toggle_tick(self):
    li = self.list.currentItem()
    if li is not None:
        li.setCheckState(Qt.Unchecked if li.checkState() == Qt.Checked else Qt.Checked)


def remove_current(self, it=None):
    """Remove a graph from the list (the file itself stays; Add files brings it back)."""
    it = it or self.current()
    if it is None:
        return "none"
    if isinstance(it, sp.Board):
        self.boards = [b for b in self.boards if b is not it]
    elif it in self.singles:
        self.singles = [s for s in self.singles if s is not it]
        self.regroup()
    elif getattr(it, "mine", False):
        self.list.setCurrentRow(self.items.index(it))
        return self.ungroup()
    else:                                                       # a ★ figure the app made: it leaves the list and is not made again (its graphs stay)
        entry = (it.how, tuple(sp.key_of(m) for m in it.members))
        if entry not in getattr(self, "hidden_groups", []): self.hidden_groups = list(getattr(self, "hidden_groups", [])) + [entry]
        self.regroup()
    row = self.list.currentRow()
    self.refresh_list()
    if self.items:
        self.list.setCurrentRow(min(max(row, 0), len(self.items) - 1))
    else:
        self.show_empty()
    self.set_status(f"Removed from the list: {it.title.strip()[:60]} (the file is not changed).")
    return "removed"


def remove_current_or_selected(self):
    """The Delete key: the highlighted row(s) if any are highlighted (click, or Ctrl / Shift-click several), else the graph on show."""
    return self.remove_selected() if self.selected() else self.remove_current()


def reorder_from_list(self):
    """After you drag graphs in Your graphs: the single graphs keep the new order (figures and groups stay on top)."""
    order = []
    for i in range(self.list.count()):
        it = self.list.item(i).data(Qt.UserRole + 1)
        if it is not None and it in self.singles:
            order.append(it)
    if len(order) == len(self.singles) and order != self.singles:
        keep = self.current()
        self.singles = order
        self.regroup()
        self.refresh_list()
        if keep in self.items:
            self.list.setCurrentRow(self.items.index(keep))
        self.set_status("New order kept; Draw in Origin and the paper set follow it.")


def wheel_zoom(self, e):
    """The mouse wheel zooms around the pointer (x and y); Ctrl+wheel only x."""
    ax = e.inaxes
    if ax is None:
        return
    f = 0.8 if e.button == "up" else 1.25
    from PySide6.QtWidgets import QApplication as _A
    only_x = bool(_A.keyboardModifiers() & Qt.ControlModifier)
    x0, x1 = ax.get_xlim()
    ax.set_xlim(e.xdata - (e.xdata - x0) * f, e.xdata + (x1 - e.xdata) * f)
    if not only_x:
        y0, y1 = ax.get_ylim()
        ax.set_ylim(e.ydata - (e.ydata - y0) * f, e.ydata + (y1 - e.ydata) * f)
    self.canvas.draw_idle()


def copy_view(self):
    QApplication.clipboard().setPixmap(self.canvas.grab())
    self.set_status("The graph on screen is copied: paste it with Ctrl+V (Word, PowerPoint, e-mail).")


def office_pictures(self, dpi):
    """The graphs that go to PowerPoint or Word, each as (png, width in, height in, name): the ticked graphs when two or
    more are ticked, else the one on show. A graph is drawn in its final form (the figure that 'Save this graph' writes);
    one that has no such form (a page of panels, a template graph) is taken as it is on show."""
    cur = self.current(); its = [i for i in self.ticked() if isinstance(i, (sp.Item, sp.Combined, sp.Board))]
    if len(its) < 2: its = [cur] if cur is not None else []
    import office_export as oe
    st = self.style(); pw = self.pub_width(); journal = self.journal.currentText(); out = []; left = []
    for it in its:
        name = str(getattr(it, "title", "") or getattr(it, "name", "") or "graph").strip(); fig = None
        if isinstance(it, (sp.Item, sp.Combined)) and getattr(it, "spec", None):
            try:
                ja, _c = sp.journal_args(it, journal) if journal else ({}, "")
                if pw: ja["width_mm"] = pw
                fig = sp.publication_figure(it, ja.pop("width_mm", None), st.curve, st.axis, **{k: v for k, v in ja.items() if k in ("fs", "max_h_mm")})
            except Exception: fig = None
        if fig is None and it is cur: fig = self.fig
        if fig is None: left.append(name); continue
        png, w_, h_ = oe.figure_png(fig, dpi); out.append((png, w_, h_, name))
    return out, left


def send_to_office(self, kind, path=None):
    """The graph on show (or the ticked graphs, one each) as a picture in a new PowerPoint presentation (kind 'pptx': one
    slide per graph, 300 dpi) or a new Word document (kind 'docx': 600 dpi, at the printed size of the figure). The file is
    written to the results folder and opened."""
    import office_export as oe
    word = kind == "docx"; what = "Word document" if word else "PowerPoint presentation"
    if self.current() is None and not self.ticked():
        self.set_status("Click a graph first."); return None
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        pics, left = office_pictures(self, 600 if word else 300)
        if not pics:
            self.set_status(f"No graph could be drawn for the {what}."); return None
        if path is None:
            folder = Path(self.run_folder()); folder.mkdir(parents=True, exist_ok=True)
            base = re.sub(r'[\\/:*?"<>|]+', "_", pics[0][3])[:60].strip() or "graph"
            if len(pics) > 1: base = f"{len(pics)}_graphs"
            path = folder / f"{base}.{kind}"; k = 2
            while path.exists(): path = folder / f"{base}_{k}.{kind}"; k += 1                    # an earlier file (perhaps open in Word or PowerPoint) is never written over
        path = str(path); (oe.write_docx if word else oe.write_pptx)(path, pics)
    except Exception as e:
        self.set_status(f"The {what} could not be written: {e}"); return None
    finally:
        QApplication.restoreOverrideCursor()
    self.last_folder = os.path.dirname(path)
    self.set_status(f"{len(pics)} graph(s) as {'600 dpi pictures' if word else 'pictures, one slide each'} in {path}" + (f"  (left out, no final form: {', '.join(left[:3])})" if left else ""))
    self.open_path(path)
    return path


def save_view(self, path=None):
    """The view on screen (with your zoom) as PNG (300 dpi), PDF or SVG. For publication files use Save this graph."""
    if path is None:
        it = self.current()
        nm = (it.title.strip() if it else "graph")[:60]
        path, _ = QFileDialog.getSaveFileName(self, "Save the view as", str(Path(self.outdir.text().strip() or Path.home()) / f"{nm}_view.png"),
                                              "PNG picture (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not path:
            return None
    self.fig.savefig(path, dpi=300, bbox_inches="tight")
    self.set_status(f"View saved: {path}")
    return path


def save_table(self, which="data", path=None):
    df = self.datamodel.df if which == "data" else self.resmodel.df
    if df is None or not len(df):
        self.set_status(f"The {which} table of this graph is empty.")
        return None
    if path is None:
        it = self.current()
        nm = (it.title.strip() if it else which)[:60]
        path, _ = QFileDialog.getSaveFileName(self, f"Save the {which} table as", str(Path(self.outdir.text().strip() or Path.home()) / f"{nm}_{which}.csv"),
                                              "CSV (*.csv);;Excel workbook (*.xlsx)")
        if not path:
            return None
    if path.lower().endswith(".xlsx"):
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    self.set_status(f"{which.capitalize()} table saved: {path}")
    return path


def copy_table(self, view, everything=False):
    """Selected cells (or the whole table) as tab-separated text: paste into Excel or Origin."""
    model = view.model()
    df = model.df
    if df is None:
        return ""
    if everything or not view.selectionModel().selectedIndexes():
        text = df.to_csv(sep="\t", index=False)
    else:
        idx = view.selectionModel().selectedIndexes()
        rows, cols = sorted({i.row() for i in idx}), sorted({i.column() for i in idx})
        sel = {(i.row(), i.column()) for i in idx}
        lines = ["\t".join(str(df.columns[c]) for c in cols)]
        for r in rows:
            lines.append("\t".join(model.data(model.index(r, c)) if (r, c) in sel else "" for c in cols))
        text = "\n".join(lines)
    QApplication.clipboard().setText(text)
    self.set_status("Copied: paste it into Excel or an Origin worksheet with Ctrl+V.")
    return text


def save_session(self, path=None):
    """The session as the current window saves it (files, graph types, sample names, panel figures) plus your groups.
    Both windows can open it."""
    if not self.singles:
        self.set_status("Nothing to save yet: add files first.")
        return None
    if path is None:
        path, _ = QFileDialog.getSaveFileName(self, "Save the session as", str(Path(self.outdir.text().strip() or Path.home()) / "session.json"), "Session (*.json)")
        if not path:
            return None
    regular = [i for i in self.singles if not getattr(i.det, 'get', lambda *a: False)('_template_graph')]
    d = sp.session_dump(regular, self.boards, self.settings_now())
    if hasattr(self, 'workbench'): d.update(self.workbench.session_extras())
    d["modern_groups"] = [[how, list(keys)] for how, keys in self.user_groups]
    d["modern_hidden_groups"] = [[how, list(keys)] for how, keys in getattr(self, "hidden_groups", [])]      # the ★ figures you removed stay removed when the session is opened again
    d["modern_ticked"] = [sp.key_of(i) for i in self.ticked() if isinstance(i, sp.Item)]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1, default=str)
    self.set_status(f"Session saved: {path}  (File > Open session in either window opens it)")
    return path


def open_session(self, path=None):
    if path is None:
        path, _ = QFileDialog.getOpenFileName(self, "Open a saved session", str(Path(self.outdir.text().strip() or Path.home())), "Session (*.json);;All files (*.*)")
        if not path:
            return None
    try:
        data = json.load(open(path, encoding="utf-8-sig"))
        if not isinstance(data, dict) or "files" not in data:
            raise ValueError("this is not a session file of Origin Plot Studio")
        singles, boards, lines = sp.session_load(data, self.opt, os.path.dirname(path))
    except Exception as e:
        self.set_status(f"The session could not be opened: {e}")
        return None
    self.singles, self.boards = singles, boards
    if hasattr(self, 'workbench'): self.workbench.restore_session_extras(data)
    self.user_groups = [(g[0], [tuple(k) if isinstance(k, list) else k for k in g[1]]) for g in data.get("modern_groups", [])]
    self.hidden_groups = [(g[0], tuple(tuple(k) if isinstance(k, list) else k for k in g[1])) for g in data.get("modern_hidden_groups", [])]
    self.regroup()
    self.refresh_list()
    want = {tuple(k) if isinstance(k, list) else k for k in data.get("modern_ticked", [])}
    for i, it in enumerate(self.items):
        if isinstance(it, sp.Item) and sp.key_of(it) in want:
            self.list.item(i).setCheckState(Qt.Checked)
    if self.items:
        self.list.setCurrentRow(0)
    for l_ in lines:
        self.log(l_)
    self.set_status(f"Session opened: {len(self.singles)} graph(s)" + (f"; {len(lines)} note(s) in Details" if lines else ""))
    return len(self.singles)


def save_chat(self, path=None):
    if path is None:
        path, _ = QFileDialog.getSaveFileName(self, "Save the chat as", str(Path(self.outdir.text().strip() or Path.home()) / "assistant_chat.txt"),
                                              "Text (*.txt);;Web page (*.html)")
        if not path:
            return None
    v = self.assistant.view
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(v.toHtml() if path.lower().endswith((".html", ".htm")) else v.toPlainText())
    self.set_status(f"Chat saved: {path}")
    return path


def show_shortcuts(self):
    rows = "".join(f"<tr><td style='padding:2px 14px 2px 0'><b>{k}</b></td><td>{t}</td></tr>" for k, t, _f in SHORTCUTS)
    mouse = ("<tr><td style='padding:2px 14px 2px 0'><b>Right click</b></td><td>a menu on Your graphs, the graph, the Data and Results tables and the chat</td></tr>"
             "<tr><td><b>Double click</b></td><td>a graph in the list: tick / untick it; on the graph: reset the axes</td></tr>"
             "<tr><td><b>Drag</b></td><td>graphs in Your graphs to change their order; files from Explorer onto the window to add them (ticked)</td></tr>"
             "<tr><td><b>Mouse wheel</b></td><td>on the graph: zoom around the pointer (with Ctrl: only the x axis)</td></tr>")
    box = QMessageBox(self)
    box.setWindowTitle("Mouse actions and keyboard shortcuts")
    box.setTextFormat(Qt.RichText)
    box.setText(f"<h3>Mouse</h3><table>{mouse}</table><h3>Keyboard</h3><table>{rows}</table>")
    if os.environ.get("OPS_NO_OPEN"):
        self.shortcut_box = box
        return box
    box.exec()
    return box


# ---------------------------------------------------------------------------------------------- right-click menus
def menu_graphs(self, pos):
    li = self.list.itemAt(pos)
    m = QMenu(self)
    if li is None:
        m.addAction("Add data files…", self.add_files)
        m.addAction("Tick all", lambda: self.tick_all(True))
        m.addAction("Untick all", lambda: self.tick_all(False))
        return _show(self, m, self.list, pos)
    row = self.list.row(li)
    it = self.items[row]
    self.list.setCurrentRow(row)
    single = isinstance(it, sp.Item) and it in self.singles
    if getattr(it, "spec", None) is not None and not isinstance(it, sp.Board) and hasattr(self, "ribbon"):
        ed = m.addAction("✎  Edit this graph…", lambda: self.ribbon.edit_dialog(it)); f_ = ed.font(); f_.setBold(True); ed.setFont(f_)
        m.addSeparator()
    m.addAction("Untick" if li.checkState() == Qt.Checked else "Tick", lambda: self.toggle_tick())
    m.addAction("Tick only this one", lambda: self._tick_only([it]))
    m.addSeparator()
    if single:
        m.addAction("Sample name…", lambda: self.rename_sample(it))
        km = m.addMenu("Graph type")
        for k in [k for k in sp.KINDS if not k.startswith("Gallery")]:
            a = km.addAction(k, lambda k=k: (self.kind.setCurrentText(k), self.change_kind(0)))
            a.setCheckable(True)
            a.setChecked(k == it.kind)
        am = m.addMenu("Analyse")
        for lab in ("Find peaks", "Savitzky-Golay", "Asymmetric least squares (ALS)", "To maximum = 1", "First derivative", "Descriptive statistics"):
            am.addAction(lab, lambda lab=lab: self.quick_tool(it, lab))
        am.addSeparator()
        am.addAction("All tools…", lambda: self.go(1))
        lm = m.addMenu("Peak labels")
        lm.addAction("Label peaks automatically (positions)", lambda: (self._tick_only([it]), self.tools.labels_auto({"n": 8, "prom": 5, "digits": 4})))
        lm.addAction("Remove the automatic labels", lambda: (self._tick_only([it]), self.tools.labels_clear()))
        if it.det.get("thermo") or it.det.get("pore"):
            tm = m.addMenu("Thermodynamic chart")
            for st in sp.THERMO_CHARTS + [sp.PORE_CHART]:
                tm.addAction(st, lambda st=st: (self._tick_only([it]), self.tools.thermo_chart(st)))
        if it.kind == "FTIR":
            fm = m.addMenu("FTIR: read as")
            for sig, t in (("Absorbance", "absorbance (bands at maxima)"), ("Transmittance", "transmittance (bands at minima)"), ("", "decided from the file")):
                fm.addAction(t, lambda sig=sig: (self._tick_only([it]), self.tools.ftir_read(sig)))
    gm = m.addMenu("Group the ticked graphs")
    gm.addAction("Stack (Ctrl+G)", lambda: self.group_ticked("stack"))
    gm.addAction("Overlay (Ctrl+Shift+G)", lambda: self.group_ticked("overlay"))
    gm.addAction("One figure with panels (a), (b) …", self.make_board)
    if getattr(it, "mine", False):
        gm.addAction("Ungroup this", self.ungroup)
    m.addSeparator()
    m.addAction("Draw in Origin", lambda: (self._tick_only([it]), self.draw_origin("ticked")))
    m.addAction("Save: PNG 600 dpi · TIFF · PDF · SVG", self.save_current)
    m.addAction("Copy the picture", self.copy_view)
    m.addSeparator()
    if single and getattr(it, "path", ""):
        m.addAction("Open the file's folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(it.path).parent))))
        m.addAction("Copy the file path", lambda: QApplication.clipboard().setText(str(it.path)))
        if sum(1 for s in self.singles if getattr(s, "path", "") == it.path) > 1:
            m.addAction("Arrange this workbook's figures…", lambda: self.arrange_workbook(it))
    m.addAction("Remove from the list (Delete)", lambda: self.remove_current(it))
    return _show(self, m, self.list, pos)


def menu_canvas(self, pos):
    m = QMenu(self)
    if hasattr(self, "ribbon"):                                  # what is under the pointer first: edit it here
        self.ribbon.menu_items(m, pos)
    m.addAction("Reset axes (double click, Ctrl+R)", self.reset_axes)
    for i, t in enumerate(("Zoom (Z)", "Pan (P)", "Select range (S)")):
        m.addAction(t, lambda i=i: self.modes.button(i).click())
    if self.sel is not None:
        m.addAction(f"Integrate {self.sel[0]:.4g} to {self.sel[1]:.4g} (Ctrl+I)", self.integrate)
        m.addAction("Clear the range (Esc)", self.clear_selection)
    m.addSeparator()
    it = self.current()
    if isinstance(it, sp.Item):
        m.addAction("Label peaks automatically (Ctrl+L)", lambda: (self._tick_only([it]), self.tools.labels_auto({"n": 8, "prom": 5, "digits": 4})))
        m.addAction("Find peaks (table)", lambda: self.quick_tool(it, "Find peaks"))
    m.addSeparator()
    m.addAction("Copy the picture (Ctrl+Shift+C)", self.copy_view)
    m.addAction("Save the view as a picture… (Ctrl+Shift+E)", self.save_view)
    m.addAction("Save this graph: PNG 600 dpi · TIFF · PDF · SVG (Ctrl+E)", self.save_current)
    m.addAction("Send to PowerPoint (picture on a slide)", lambda: self.send_to_office("pptx"))
    m.addAction("Send to Word (high-definition picture)", lambda: self.send_to_office("docx"))
    m.addAction("Draw in Origin", lambda: (self._tick_only([it]) if it else None, self.draw_origin("ticked")))
    return _show(self, m, self.canvas, pos)


def menu_table(self, pos, view, which):
    m = QMenu(self)
    m.addAction("Copy the selected cells", lambda: self.copy_table(view))
    m.addAction("Copy the whole table", lambda: self.copy_table(view, True))
    m.addSeparator()
    m.addAction("Save as CSV or Excel…", lambda: self.save_table(which))
    return _show(self, m, view.viewport(), pos)


def menu_chat(self, pos):
    v = self.assistant.view
    m = v.createStandardContextMenu(pos)
    m.addSeparator()
    m.addAction("Copy the whole chat", lambda: QApplication.clipboard().setText(v.toPlainText()))
    m.addAction("Save the chat…", self.save_chat)
    m.addAction("New chat", self.assistant.new_chat)
    return _show(self, m, v.viewport(), pos)


def _show(self, m, widget, pos):
    self.last_menu = m
    if not os.environ.get("OPS_NO_OPEN"):
        m.exec(widget.mapToGlobal(pos))
    return m


def rename_sample(self, it):
    name, ok = QInputDialog.getText(self, "Sample name", "Sample name for this graph:", text=getattr(it, "sample", "") or "")
    if ok:
        self._tick_only([it])
        self.sample.setText(name.strip())
        self.apply_sample()


def quick_tool(self, it, label):
    """One analysis tool on this graph with its default settings (right click > Analyse)."""
    self._tick_only([it])
    self.go(1)
    page = self.pages.widget(1)
    e = page.find_entry(label)
    if e is not None:
        page.tree.setCurrentItem(e)
    return self.tools.run_tool(label, page.settings(), page)


METHODS = {f.__name__: f for f in (tick_all, toggle_tick, remove_current, remove_current_or_selected, reorder_from_list, wheel_zoom, copy_view, send_to_office, save_view, save_table, copy_table,
                                   save_session, open_session, save_chat, show_shortcuts, menu_graphs, menu_canvas, menu_table, menu_chat, rename_sample,
                                   quick_tool, arrange_workbook)}

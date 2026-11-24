"""The shell of the window: one top bar, panels everywhere, the layout kept between sessions.

  The top bar (navy): the name, the five sections (Workspace, Analysis, Graph gallery, Assistant, Settings), Find a graph, and four menus -
  File, View, Tools, Help - with Add files as the one visible action. The old menu bar and side bar are gone (their entries are in these
  menus; their keyboard shortcuts still work). The ribbon (graph formatting) shows in Workspace only.
  Workspace: every part is a panel - Your graphs, Graph, Data, Results, Details, Graph settings: drag it by its header, resize it at its
  edges, put it beside or under another one or out as a window of its own, close it (View brings it back). Closing a panel never loses
  files, settings or results. The arrangement is kept for the next start; View > Reset layout puts everything back.
  The graph keeps its proportions when its panel changes size. Export and Draw in Origin sit above the graph: one primary action.
  Graph settings are in sections that fold (their state is kept)."""
import base64

from PySide6.QtCore import QByteArray, QEvent, QObject, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
                               QFrame, QLayout)

import smart_plots as sp

LAYOUT_VERSION = 2                       # a saved arrangement of an older shape is not restored


# ---------------------------------------------------------------------------------------------- small parts
class PanelTabs:
    """What the Graph / Data / Results / Details tabs were: setCurrentWidget(...) now brings that panel to the front."""
    def __init__(self, ws, docks):
        self.ws, self.docks, self.cur = ws, docks, None

    def setCurrentWidget(self, widget):
        d = self.docks.get(id(widget))
        if d is not None:
            d.show(); d.raise_()
        self.cur = widget

    def currentWidget(self):
        return self.cur

    def widget_dock(self, widget):
        return self.docks.get(id(widget))


class AspectBox(QWidget):
    """The graph in its own proportions (width / height of its page), as large as the panel allows, centred."""
    def __init__(self, child, ratio=1.44):
        super().__init__()
        self.child, self.ratio = child, ratio
        child.setParent(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(240, 180)

    def set_ratio(self, r):
        r = max(0.35, min(3.5, float(r or 1.44)))
        if abs(r - self.ratio) > 1e-3:
            self.ratio = r
            self._place()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place()

    def _place(self):
        W, H = self.width(), self.height()
        w = min(W, H * self.ratio); h = w / self.ratio
        fig = getattr(self.child, "figure", None)
        if fig is not None:                       # a small panel: the whole graph still fits (drawn as on a 7-inch page, scaled down)
            try:
                d = max(38.0, min(100.0, w / 7.0)); r = getattr(self.child, "device_pixel_ratio", 1.0) or 1.0
                if abs(getattr(fig, "_original_dpi", fig.dpi) - d) > 0.5:
                    fig._original_dpi = d; fig._set_dpi(d * r, forward=False)
            except Exception:
                pass
        self.child.setGeometry(int((W - w) / 2), int((H - h) / 2), int(w), int(h))
        if fig is not None:
            try:
                self.child.draw_idle()
            except Exception:
                pass


def short_name(name, n=30):
    """A long file name, shortened in the middle (the full name is in the tooltip)."""
    name = str(name)
    return name if len(name) <= n else name[: n // 2 - 1] + "…" + name[-(n - n // 2):]


def _widgets_of(item):
    """The widgets of a layout item (a widget, or every widget of a layout inside it)."""
    if item.widget() is not None:
        return [item.widget()]
    lay = item.layout()
    out = []
    if lay is not None:
        for i in range(lay.count()):
            out += _widgets_of(lay.itemAt(i))
    return out


# ---------------------------------------------------------------------------------------------- the top bar
def _header(w):
    import workspace_qt as WQ
    tb_lay = w.topbar_layout
    tb = tb_lay.parentWidget()
    tb.setObjectName("header")
    holder = QWidget(w); holder.hide(); holder.setFixedSize(0, 0); w._header_spare = holder           # the old buttons: kept (other parts may use them), not shown
    keep = {id(w.search), id(w.panels_btn)} | ({id(w.upd_btn)} if getattr(w, "upd_btn", None) is not None else set())
    while tb_lay.count():
        it = tb_lay.takeAt(0)
        wd = it.widget()
        if wd is not None and id(wd) not in keep:
            wd.setParent(holder)
    tb_lay.setContentsMargins(14, 6, 14, 6); tb_lay.setSpacing(6)
    from pathlib import Path as _P
    from PySide6.QtGui import QPixmap
    logo = QLabel(); pm = QPixmap(str(_P(__file__).resolve().parent / "app.png"))
    if not pm.isNull():
        logo.setPixmap(pm.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)); tb_lay.addWidget(logo)
    brand = QLabel("Origin Plot Studio" if not pm.isNull() else "◆  Origin Plot Studio", objectName="brand"); brand.setToolTip(f"Version {sp.VERSION}")
    tb_lay.addWidget(brand); tb_lay.addSpacing(18)
    w.header_nav = QButtonGroup(w); w.header_nav.setExclusive(True)
    for i in WQ.NAV_ORDER:
        _k, name, _t = WQ.SECTIONS[i]
        b = QPushButton(name, objectName="navtab"); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(f"{name} (Ctrl+{i + 6})" if i < 4 else name)
        b.clicked.connect(lambda _c=False, i=i: w.go(i))
        w.header_nav.addButton(b, i); tb_lay.addWidget(b)
    w.header_nav.button(w.pages.currentIndex()).setChecked(True)
    w.pages.currentChanged.connect(lambda i: w.header_nav.button(i).setChecked(True) if w.header_nav.button(i) else None)
    tb_lay.addStretch(1)
    w.search.setMinimumWidth(170); w.search.setMaximumWidth(260); w.search.setPlaceholderText("Find a graph")
    tb_lay.addWidget(w.search)
    mb = w.menuBar()
    menus = {a.text().replace("&", ""): a.menu() for a in mb.actions() if a.menu() is not None}
    def menu_button(text, menu):
        b = QPushButton(text + " ▾", objectName="menu"); b.setMenu(menu); tb_lay.addWidget(b)
        return b
    # File: the one File menu (the old File menu, the Save ▾ entries, New, Refresh)
    fm = QMenu(w)
    for a in (menus.get("File").actions() if menus.get("File") else []):
        fm.addAction(a)
    if getattr(w, "save_btn", None) is not None and w.save_btn.menu() is not None:
        sm = fm.addMenu("Save and export")
        for a in w.save_btn.menu().actions():
            sm.addAction(a)
    w.file_btn = menu_button("File", fm)
    # View: the panels, the layout, the ribbon
    vm = w.panels_btn.menu() or QMenu(w)
    vm.addSeparator()
    w.view_panels_menu = vm.addMenu("Panels")
    ra = QAction("Reset layout", w); ra.triggered.connect(lambda: reset_layout(w)); vm.addAction(ra); w.reset_layout_action = ra
    rbm = vm.addMenu("Formatting ribbon")
    for i_, t_ in enumerate(getattr(w.ribbon, "MODES", [])):
        rbm.addAction(t_, lambda i_=i_: w.ribbon.set_display(i_))
    if menus.get("View"):
        om = vm.addMenu("More")
        for a in menus["View"].actions():
            om.addAction(a)
    w._old_panels_btn = w.panels_btn; w.panels_btn.setParent(holder); w.panels_btn = menu_button("View", vm)
    # Tools: Draw, Analysis, XRD tools of the old menu bar
    tm = QMenu(w)
    for name in ("Draw", "Analysis", "XRD tools"):
        if menus.get(name):
            sub = tm.addMenu(name)
            for a in menus[name].actions():
                sub.addAction(a)
    w.tools_btn = menu_button("Tools", tm)
    hm = QMenu(w)
    for a in (menus.get("Help").actions() if menus.get("Help") else []):
        hm.addAction(a)
    w.help_btn = menu_button("Help", hm)
    if getattr(w, "upd_btn", None) is not None:              # 'A new version is ready' - shown only when there is one
        w.upd_btn.setObjectName("teal"); tb_lay.addWidget(w.upd_btn)
    add = QPushButton("Add files…", objectName="primary"); add.setToolTip("Add data files (Ctrl+O); you can also drop them on the window")
    add.clicked.connect(lambda: w.add_files()); tb_lay.addWidget(add); w.header_add = add
    # the menu bar goes; every shortcut of its entries keeps working
    def every(menu):
        for a in menu.actions():
            if a.menu() is not None:
                yield from every(a.menu())
            else:
                yield a
    for m in menus.values():
        for a in every(m):
            if not a.shortcut().isEmpty() and a not in w.actions():
                w.addAction(a)
    mb.setVisible(False)
    w.navw.hide()                                            # the sections are in the top bar now
    w.navw.setMaximumWidth(0)


# ---------------------------------------------------------------------------------------------- Workspace: everything a panel
def _workspace(w):
    main = w.wsmain
    card = main.takeCentralWidget()                          # the graph card: a panel of its own
    lay = card.layout()
    g, dv, rw, det = (w.tabs.widget(i) for i in range(4))
    lay.removeWidget(w.tabs)
    w.tabs.setParent(None)
    # the title row of the graph: its name, and the actions (Export ▾, Draw in Origin) on the right
    for x in (w.gtitle, w.gsub):
        lay.removeWidget(x)
    row = QHBoxLayout(); col = QVBoxLayout(); col.setSpacing(0); col.addWidget(w.gtitle); col.addWidget(w.gsub)
    row.addLayout(col, 1)
    w.gsub.setWordWrap(False); w.gsub.setTextInteractionFlags(Qt.TextSelectableByMouse)
    ex = QPushButton("Export ▾"); em = QMenu(ex)
    em.addAction("Save this graph: PNG 600 dpi · TIFF · PDF · SVG (Ctrl+E)", lambda: w.b_save.click())
    em.addAction("Save the view as a picture…", lambda: w.save_view())
    em.addAction("Copy the picture", lambda: w.copy_view())
    em.addSeparator()
    em.addAction("Figure from the ticked graphs (panels a, b …)", lambda: w.b_board.click())
    em.addAction("Preview the paper set (PDF)", lambda: w.b_prev.click())
    em.addAction("Make the paper set", lambda: w.b_paper.click())
    em.addSeparator(); em.addAction("Open the results folder", lambda: w.b_open.click())
    ex.setMenu(em); w.export_btn = ex
    dm = QMenu(w.b_draw)
    dm.addAction("Draw the ticked graphs (F5)", lambda: w.b_draw.click()); dm.addAction("Draw all graphs (Shift+F5)", lambda: w.b_all.click())
    w.b_draw.setText("Draw in Origin"); w.b_draw.setToolTip("Draw the ticked graphs in Origin (or the one on show): Origin does the final work")
    more = QToolButton(); more.setText("▾"); more.setMenu(dm); more.setPopupMode(QToolButton.InstantPopup); more.setToolTip("Draw all graphs in Origin")
    for b in (w.b_all, w.b_save, w.b_board, w.b_open, w.b_prev, w.b_paper):
        b.setParent(w._header_spare if hasattr(w, "_header_spare") else None)
    row.addWidget(w.b_cancel); row.addWidget(ex); row.addWidget(w.b_draw); row.addWidget(more)
    lay.insertLayout(0, row)
    # the canvas keeps the proportions of the graph
    gl = g.layout()
    idx = gl.indexOf(w.canvas); gl.removeWidget(w.canvas)
    w.canvas_box = AspectBox(w.canvas)
    gl.insertWidget(idx, w.canvas_box, 1)
    lay.insertWidget(1, g, 1)
    g.setVisible(True)
    card.setMinimumWidth(360)
    mk = w._panel_dock
    w.graph_dock = mk("Graph", "graphDock", card, Qt.RightDockWidgetArea, main)
    main.removeDockWidget(w.settings_dock)
    main.splitDockWidget(w.graph_dock, w.settings_dock, Qt.Horizontal); w.settings_dock.show()
    w.data_dock = mk("Data", "dataDock", dv, Qt.BottomDockWidgetArea, main)
    rw.setMinimumHeight(80)
    w.results_dock = mk("Results", "resultsDock", rw, Qt.BottomDockWidgetArea, main)
    w.details_dock = mk("Details", "detailsDock", det, Qt.BottomDockWidgetArea, main)
    main.removeDockWidget(w.data_dock); main.removeDockWidget(w.results_dock); main.removeDockWidget(w.details_dock)
    main.tabifyDockWidget(w.graph_dock, w.data_dock); main.tabifyDockWidget(w.data_dock, w.results_dock); main.tabifyDockWidget(w.results_dock, w.details_dock)
    for d in (w.data_dock, w.results_dock, w.details_dock):
        d.show()
    w.graph_dock.raise_()                                     # the graph gets the whole height; Data, Results and Details are tabs beside it (drag one out to see both)
    main.setTabPosition(Qt.AllDockWidgetAreas, __import__("PySide6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget.North)
    main.resizeDocks([w.graphs_dock, w.graph_dock, w.settings_dock], [260, 900, 360], Qt.Horizontal)
    w.tabs = PanelTabs(w, {id(dv): w.data_dock, id(rw): w.results_dock, id(det): w.details_dock, id(g): w.graph_dock})
    w.ws_docks = [w.graphs_dock, w.graph_dock, w.settings_dock, w.data_dock, w.results_dock, w.details_dock]
    orig_draw = w.draw
    def draw():                                                  # the proportions of the graph's own page
        it = w.current()
        r = 1.44
        try:
            sp_ = getattr(it, "spec", None) or {}
            if isinstance(it, sp.Board):
                a_, b_ = it.size_in(); r = a_ / b_
            elif sp_.get("page_in"):
                r = sp_["page_in"][0] / sp_["page_in"][1]
            elif len(sp_.get("panels") or []) > 2 or any(p.get("side") for p in sp_.get("panels") or []):
                r = 1.3
        except Exception:
            pass
        w.canvas_box.set_ratio(r)
        return orig_draw()
    w.draw = draw


def _settings_sections(w):
    """Graph settings in sections that fold (as the panels of Word's dialogs); their state is kept."""
    import workspace_qt as WQ
    inner = [x for x in w.settings_card.findChildren(QWidget) if x.objectName() == "card" and x.layout() is not None
             and any(isinstance(c, QLabel) and c.objectName() == "h2" for c in x.findChildren(QLabel))]
    if not inner:
        return
    lay = inner[0].layout()
    folded = set(WQ.load_cfg().get("folded_sections") or [])
    w.sections = {}
    cur = None
    items = [lay.itemAt(i) for i in range(lay.count())]
    for it in items:
        wd = it.widget()
        if isinstance(wd, QLabel) and wd.objectName() == "h2":
            title = wd.text()
            b = QPushButton("▾  " + title, objectName="section"); b.setCheckable(True); b.setChecked(title not in folded)
            lay.replaceWidget(wd, b); wd.setParent(None)
            cur = w.sections[title] = {"button": b, "widgets": [], "hidden": set()}
            b.toggled.connect(lambda on, t=title: fold_section(w, t, not on))
            continue
        if isinstance(wd, QFrame) and wd.frameShape() == QFrame.HLine:
            wd.hide(); continue
        if cur is not None:
            cur["widgets"] += _widgets_of(it)
    for t in folded:
        if t in w.sections:
            fold_section(w, t, True, save=False)


def fold_section(w, title, fold, save=True):
    import workspace_qt as WQ
    s = w.sections[title]
    s["button"].setText(("▸  " if fold else "▾  ") + title)
    if s["button"].isChecked() == fold:
        s["button"].blockSignals(True); s["button"].setChecked(not fold); s["button"].blockSignals(False)
    if fold:
        s["hidden"] = {id(x) for x in s["widgets"] if x.isVisibleTo(x.parentWidget() or x)}
        for x in s["widgets"]:
            x.setVisible(False)
    else:
        for x in s["widgets"]:
            if id(x) in s["hidden"] or not s["hidden"]:
                x.setVisible(True)
        if w.b_cancel in s["widgets"] and w.job_thread is None:
            w.b_cancel.hide()
    if save:
        f = sorted(t for t, v in w.sections.items() if not v["button"].isChecked())
        WQ.save_cfg({"folded_sections": f})
    return fold


def _settings_fit(w):
    """No clipped controls in Graph settings: fields shrink to the panel, a scroll bar appears only when it is narrower than that."""
    from PySide6.QtWidgets import QComboBox, QLineEdit, QScrollArea
    for sa in w.settings_card.findChildren(QScrollArea):
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    for c in w.settings_card.findChildren(QComboBox):
        c.setMinimumContentsLength(6); c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon); c.setMinimumWidth(70)
        c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    for e in w.settings_card.findChildren(QLineEdit):
        e.setMinimumWidth(60); e.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    for l in w.settings_card.findChildren(QLabel):
        if l.objectName() == "soft":
            l.setWordWrap(True)
    w.settings_card.setMinimumWidth(300)


def _concise_names(w):
    """Your graphs: the file name shortened in the middle, the whole name (and the path) on hover."""
    from pathlib import Path
    orig = w.refresh_list
    def refresh_list():
        r = orig()
        for i, it in enumerate(w.items):
            li = w.list.item(i)
            if li is None:
                continue
            full = li.text()
            p = str(getattr(it, "path", "") or "")
            if isinstance(it, sp.Item) and p:
                nm = Path(p).name
                if nm in full and len(nm) > 30:
                    li.setText(full.replace(nm, short_name(nm)))
            li.setToolTip(full + (f"\n{p}" if p else ""))
        return r
    w.refresh_list = refresh_list
    w.refresh_list()


def _context_ribbon(w):
    """The formatting ribbon: in Workspace only, under the top bar (its tabs and its buttons together)."""
    rb = w.ribbon
    head = rb.head
    if head.parentWidget() is not rb:
        try:
            w.topbar_layout.removeWidget(head)
        except Exception:
            pass
        rb.layout().insertWidget(0, head)
    head.show()
    for x in getattr(w, "brand", []):
        x.hide()
    def show_for(i):
        rb.setVisible(i == 0 and rb.display != 2)
    w.pages.currentChanged.connect(show_for)
    show_for(w.pages.currentIndex())


# ---------------------------------------------------------------------------------------------- the layout: kept, restored, reset
def _mains(w):
    """Every window with panels: the main window, Workspace, Analysis, Graph gallery."""
    out = [("main", w), ("ws", w.wsmain)]
    for i in range(w.pages.count()):
        pg = w.pages.widget(i)
        if getattr(pg, "main", None) is not None:
            out.append((f"page{i}", pg.main))
    return out


def _b64(state):
    return base64.b64encode(bytes(state)).decode("ascii")


def save_layout(w):
    import workspace_qt as WQ
    data = {"v": LAYOUT_VERSION, "geometry": _b64(w.saveGeometry())}
    for k, m in _mains(w):
        data[k] = _b64(m.saveState(LAYOUT_VERSION))
    WQ.save_cfg({"panel_layout": data})
    return data


def restore_layout(w, data=None):
    import workspace_qt as WQ
    data = data if data is not None else WQ.load_cfg().get("panel_layout")
    if not isinstance(data, dict) or data.get("v") != LAYOUT_VERSION:          # none yet, an older shape, or something else: the default arrangement
        return False
    ok = True
    for k, m in _mains(w):
        if data.get(k):
            try:
                r = bool(m.restoreState(QByteArray(base64.b64decode(str(data[k]))), LAYOUT_VERSION))
            except Exception:                                   # a damaged arrangement is ignored, never a reason not to start
                r = False
            ok &= r
            pg = m.parentWidget()
            if r and pg is not None and hasattr(pg, "docks"):
                pg._restored = True
    if data.get("geometry"):
        try:
            w.restoreGeometry(QByteArray(base64.b64decode(str(data["geometry"]))))
        except Exception:
            pass
    return ok


def reset_layout(w):
    """View > Reset layout: every panel back where it was when the app was installed, shown, docked."""
    import workspace_qt as WQ
    for k, m in _mains(w):
        st = w._default_layout.get(k)
        for d in m.findChildren(__import__("PySide6.QtWidgets", fromlist=["QDockWidget"]).QDockWidget):
            if d.parent() is m and d.isFloating():
                d.setFloating(False)
        if st is not None:
            m.restoreState(st, LAYOUT_VERSION)
    for d in getattr(w, "ws_docks", []):
        d.show()
    for pg in (w.pages.widget(i) for i in range(w.pages.count())):
        for d in getattr(pg, "docks", []):
            d.show()
    w.ribbon.set_display(0)
    WQ.save_cfg({"panel_layout": {}})
    w.set_status("Layout reset: every panel is back in its place.")
    return True


class Balancer(QObject):
    """When the window changes size the main panel (the graph, the preview) takes the space; the side panels keep the width you gave
    them (at most 30 % each). A width you set by dragging an edge is remembered; one that came from the window being resized is not."""
    def __init__(self, main, big, sides, pref=None):
        super().__init__(main); self.main, self.big, self.sides = main, big, sides; self.resizing = False
        self.pref = {id(d): v for d, v in (pref or {}).items()}
        main.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if obj is self.main:
            if ev.type() == QEvent.Resize:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self.balance)
            elif ev.type() == QEvent.MouseButtonRelease:            # you dragged an edge between panels: those widths are yours
                for d in self.sides:
                    if d.isVisible() and not d.isFloating():
                        self.pref[id(d)] = d.width()
        return False

    def balance(self):
        try:
            if self.big.isFloating() or not self.big.isVisible():
                return
            W = self.main.width()
            row = [d for d in self.sides if d.isVisible() and not d.isFloating() and self.main.dockWidgetArea(d) in (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea)
                   and abs(d.geometry().top() - self.big.geometry().top()) < 60]
            for d in row:
                self.pref.setdefault(id(d), d.width())
            ws_ = [min(self.pref[id(d)], int(0.3 * W)) for d in row]
            rest = W - sum(ws_) - 12 * (len(row) + 1)
            if rest > 200:
                self.main.resizeDocks(row + [self.big], ws_ + [rest], Qt.Horizontal)
        except RuntimeError:
            pass


class _Keeper(QObject):
    """Saves the arrangement of the panels when the window closes."""
    def __init__(self, w):
        super().__init__(w); self.w = w

    def eventFilter(self, obj, ev):
        if obj is self.w and ev.type() == QEvent.Close:
            try:
                save_layout(self.w)
            except Exception:
                pass
        return False


def _view_panels(w):
    """View > Panels: every panel of every section, to show or close."""
    m = w.view_panels_menu
    m.clear()
    for d in getattr(w, "ws_docks", []):
        a = d.toggleViewAction(); a.setText("Workspace: " + d.windowTitle().replace("⠿", "").strip()); m.addAction(a)
    for i in range(w.pages.count()):
        pg = w.pages.widget(i)
        for d in getattr(pg, "docks", []):
            a = d.toggleViewAction(); a.setText(f"{pg.label}: " + d.windowTitle().replace("⠿", "").strip()); m.addAction(a)
    a = w.dock.toggleViewAction(); a.setText("Assistant beside the work"); m.addAction(a)


def install(w):
    _install(w)
    return w


def _safe(fn, *a):
    """A part of the arrangement that fails is left out (and written to Details); the app always starts."""
    try:
        return fn(*a)
    except Exception as e:
        import traceback
        try:
            w_ = a[0] if a else None
            if w_ is not None and hasattr(w_, "log"):
                w_.log("!! layout: " + "".join(traceback.format_exception_only(type(e), e)).strip())
        except Exception:
            pass
        return None


def _install(w):
    _header(w)
    _workspace(w)
    _settings_sections(w)
    _settings_fit(w)
    _concise_names(w)
    _context_ribbon(w)
    _view_panels(w)
    w._balancers = [Balancer(w.wsmain, w.graph_dock, [w.graphs_dock, w.settings_dock], {w.graphs_dock: 270, w.settings_dock: 340})]
    for i in range(w.pages.count()):
        pg = w.pages.widget(i)
        if getattr(pg, "docks", None):
            big = pg.gallery_dock if pg.label.startswith("Graph gallery") else pg.preview_dock
            w._balancers.append(Balancer(pg.main, big, [d for d in pg.docks if d is not big]))
    w._default_layout = {k: m.saveState(LAYOUT_VERSION) for k, m in _mains(w)}
    _safe(restore_layout, w)
    w._keeper = _Keeper(w); w.installEventFilter(w._keeper)
    w.reset_layout = lambda: reset_layout(w)
    w.save_layout = lambda: save_layout(w)
    return w

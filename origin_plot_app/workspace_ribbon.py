"""The formatting ribbon of Workspace, laid out as in Word: a quick-access bar (Save, Undo, Redo), the tabs Home, Insert, Draw,
Design, Layout, Axes, Lines (File is the one File menu of the top bar), and in each tab groups of large and small buttons with the group's name underneath. ⌃ folds the ribbon to
its tabs (or hides it; Ctrl+F1), ⚙ chooses which groups are shown.

Everything works on the graph on show (Workspace) - or click on a text, a curve or the axes in the graph, double click a title to type
it, right click for more. Text: font, size, A↑ A↓, bold, italic, colour, X² superscript and X₂ subscript (written ^{...} and _{...},
shown as real superscript and subscript here, in the publication files and in Origin). Design: ready-made looks, as Word's Styles.
Every change is kept with the graph (and in a saved session) and can be undone (Ctrl+Z) and redone (Ctrl+Y).
No number of your data is changed by any of this."""
import copy
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFontDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QScrollArea, QStackedWidget, QTabBar, QToolButton, QVBoxLayout, QWidget)
import smart_plots as sp

ROLE_TEXT = {"title": "Graph title", "axis_titles": "Axis titles", "numbers": "Axis numbers", "labels": "Peak labels and other text", "legend": "Legend"}
SIZES = ["6", "7", "8", "9", "10", "11", "12", "14", "16", "18", "20", "24", "28", "32", "36"]
ROLES_ALL = list(ROLE_TEXT)
LOOKS = [   # Design > Looks, as Word's Styles: (name, what it does, the format)
    ("App look", "How the app draws it", None),
    ("Black & white", "Black text, axes and curves", {"text": {r: {"colour": "#000000"} for r in ROLES_ALL}, "axis": {"colour": "#000000"}, "lines": {"*": {"colour": "#000000"}}}),
    ("Bold paper", "Bold letters, heavier axes and curves", {"text": {r: {"bold": True} for r in ROLES_ALL}, "axis": {"width": 2.0}, "lines": {"*": {"width": 2.0}}}),
    ("Light", "Normal letters, fine axes and curves", {"text": {r: {"bold": False} for r in ROLES_ALL}, "axis": {"width": 0.8}, "lines": {"*": {"width": 1.0}}}),
    ("Slides", "Large letters for a presentation", {"text": {"title": {"size": 18, "bold": True}, "axis_titles": {"size": 16, "bold": True}, "numbers": {"size": 14}, "labels": {"size": 13}, "legend": {"size": 13}}, "axis": {"width": 2.0}, "lines": {"*": {"width": 2.5}}}),
    ("Serif", "Times New Roman everywhere", {"text": {r: {"family": "Times New Roman"} for r in ROLES_ALL}}),
    ("Navy", "Dark blue axes and titles", {"text": {"title": {"colour": "#00205b"}, "axis_titles": {"colour": "#00205b"}, "numbers": {"colour": "#00205b"}}, "axis": {"colour": "#00205b"}}),
]
_ICONS = {}


def icon(glyph, colour="#18222F", size=32):
    """A button picture drawn from a symbol (no picture files to install)."""
    key = (glyph, colour, size)
    if key not in _ICONS:
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm); f = QFont("Segoe UI Symbol"); f.setPixelSize(int(size * 0.78)); p.setFont(f); p.setPen(QColor(colour))
        p.drawText(pm.rect(), Qt.AlignCenter, glyph); p.end()
        _ICONS[key] = QIcon(pm)
    return _ICONS[key]


def _big(glyph, text, tip, fn, checkable=False):
    """A large button: the picture over its name (as Paste in Word)."""
    b = QToolButton(); b.setText(text); b.setToolTip(tip); b.setIcon(icon(glyph)); b.setIconSize(QSize(30, 30)); b.setCheckable(checkable)
    b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); b.setAutoRaise(True); b.setMinimumWidth(58); b.setObjectName("big")
    b.clicked.connect(lambda *_: fn())
    return b


def _small(glyph, text, tip, fn, checkable=False, colour="#18222F"):
    """A small button: the picture beside its name (as Cut, Copy in Word)."""
    b = QToolButton(); b.setText(text); b.setToolTip(tip); b.setIcon(icon(glyph, colour, size=18)); b.setIconSize(QSize(16, 16)); b.setCheckable(checkable)
    b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon if text else Qt.ToolButtonIconOnly); b.setAutoRaise(True)
    b.clicked.connect(lambda *_: fn())
    return b


def _btn(text, tip, fn, checkable=False, width=None):
    b = QToolButton(); b.setText(text); b.setToolTip(tip); b.setCheckable(checkable); b.setAutoRaise(True)
    if width: b.setFixedWidth(width); b.setObjectName("mini")
    b.clicked.connect(lambda *_: fn())
    return b


def _col(*widgets):
    """Small buttons one above the other."""
    w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(1)
    for x in widgets:
        v.addWidget(x)
    v.addStretch(1)
    return w


def _row(*widgets):
    w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(2)
    for x in widgets:
        h.addWidget(x)
    h.addStretch(1)
    return w


def _group(title, *widgets, launcher=None):
    """A group of the ribbon: its controls, its name underneath and - where there is more - ↘ for the full dialog (as in Word)."""
    f = QFrame(objectName="ribgroup")
    v = QVBoxLayout(f); v.setContentsMargins(6, 2, 4, 0); v.setSpacing(1)
    h = QHBoxLayout(); h.setSpacing(3)
    for w_ in widgets:
        h.addWidget(w_)
    v.addLayout(h, 1)
    foot = QHBoxLayout(); foot.setContentsMargins(0, 0, 0, 0)
    lab = QLabel(title, objectName="ribname"); lab.setAlignment(Qt.AlignCenter)
    foot.addWidget(lab, 1)
    if launcher:
        l_ = QToolButton(); l_.setText("↘"); l_.setAutoRaise(True); l_.setToolTip(f"More: {title}"); l_.setObjectName("launch"); l_.clicked.connect(lambda *_: launcher())
        foot.addWidget(l_)
    v.addLayout(foot)
    f.title = title
    return f


class Ribbon(QWidget):
    """The ribbon: its tabs (self.head) sit in the top bar of the window, beside the buttons there; the buttons of the chosen tab below."""
    MODES = ["Always show the ribbon", "Show tabs only", "Hide the ribbon (Ctrl+F1 shows it)"]

    def __init__(self, w):
        super().__init__()
        self.w = w; self.setObjectName("ribbon")
        self.bar = QTabBar(objectName="ribtabs"); self.bar.setDrawBase(False); self.bar.setExpanding(False)
        self.stack = QStackedWidget(objectName="ribbody")
        lay_ = QVBoxLayout(self); lay_.setContentsMargins(6, 0, 6, 4); lay_.addWidget(self.stack)
        self.bar.currentChanged.connect(self.stack.setCurrentIndex)
        self.tabBarClicked = self.bar.tabBarClicked; self.tabBarDoubleClicked = self.bar.tabBarDoubleClicked
        self.undo_st, self.redo_st = {}, {}
        self.groups = {}                       # "Tab / Group" -> frame (Customise the ribbon)
        # ------------------------------------------------------------ the controls (kept by name: the rest of the app uses them)
        self.role = QComboBox(); self.role.addItems(list(ROLE_TEXT.values())); self.role.setToolTip("What to change - or click on it in the graph")
        self.role.currentIndexChanged.connect(lambda *_: self.show_state())
        self.edit = QLineEdit(); self.edit.setMinimumWidth(230); self.edit.setPlaceholderText("Type the title (X² superscript, X₂ subscript), Enter")
        self.edit.returnPressed.connect(self.apply_text)
        self.which = QComboBox(); self.which.addItems(["x axis", "y axis"]); self.which.setToolTip("Which axis title you type")
        self.which.currentIndexChanged.connect(lambda *_: self.show_state())
        self.family = QComboBox(); self.family.setEditable(True); self.family.addItems([""] + sp.FONT_FAMILIES); self.family.setToolTip("Font"); self.family.setMinimumWidth(140)
        self.family.lineEdit().setPlaceholderText("Font")
        self.family.activated.connect(lambda *_: self.style_text(family=self.family.currentText().strip() or None))
        self.size = QComboBox(); self.size.setEditable(True); self.size.addItems([""] + SIZES); self.size.setToolTip("Font size (pt)"); self.size.setFixedWidth(56)
        self.size.activated.connect(lambda *_: self._size())
        self.size.lineEdit().returnPressed.connect(self._size)
        self.bold = _btn("B", "Bold (Ctrl+B)", lambda: self.style_text(bold=self.bold.isChecked()), True, 26)
        self.italic = _btn("I", "Italic (Ctrl+Shift+I)", lambda: self.style_text(italic=self.italic.isChecked()), True, 26)
        f_ = self.bold.font(); f_.setBold(True); self.bold.setFont(f_); f_ = self.italic.font(); f_.setItalic(True); self.italic.setFont(f_)
        self.sup = _btn("x²", "Superscript: the selected letters (Ctrl+Shift++)", lambda: self.wrap("^"), width=28)
        self.sub = _btn("x₂", "Subscript: the selected letters (Ctrl+=)", lambda: self.wrap("_"), width=28)
        self.tcol = _btn("A", "Text colour", lambda: self.pick_colour("text"), width=28); self.tcol.setStyleSheet("border-bottom: 3px solid #C00000; font-weight: 600;")
        grow = _btn("A↑", "Bigger letters", lambda: self.step_size(+1), width=30); shrink = _btn("A↓", "Smaller letters", lambda: self.step_size(-1), width=30)
        clear = _small("⌫", "", "Clear the format of this text", self.clear_text)
        self.kind = QComboBox(); self.kind.addItems([k for k in sp.KINDS if not k.startswith("Gallery")]); self.kind.setToolTip("Change the kind of graph (how the file is read)")
        self.kind.activated.connect(lambda *_: self.change_kind())
        self.legend = QComboBox(); self.legend.addItems(["Legend: automatic", "Legend: on", "Legend: off"])
        self.legend.activated.connect(lambda *_: self.set_fmt(legend={0: None, 1: "on", 2: "off"}[self.legend.currentIndex()]))
        self.title_on = QComboBox(); self.title_on.addItems(["Title: automatic", "Title: hidden"])
        self.title_on.activated.connect(lambda *_: self.set_fmt(hide_title=bool(self.title_on.currentIndex()) or None))
        self.orient = QComboBox(); self.orient.addItems(sp.ORIENTATIONS); self.orient.setToolTip("Landscape or portrait page")
        self.orient.activated.connect(lambda *_: (w.orient.setCurrentText(self.orient.currentText()), w.look_changed()) if hasattr(w, "orient") else None)
        self.x0, self.x1, self.y0, self.y1 = (QLineEdit() for _ in range(4))
        for e_, t_ in ((self.x0, "x from"), (self.x1, "x to"), (self.y0, "y from"), (self.y1, "y to")):
            e_.setPlaceholderText(t_); e_.setFixedWidth(66); e_.returnPressed.connect(self.apply_ranges)
        self.axw = QDoubleSpinBox(); self.axw.setRange(0, 6); self.axw.setSingleStep(0.25); self.axw.setSpecialValueText("auto"); self.axw.setSuffix(" pt")
        self.axw.setToolTip("Axis line weight"); self.axw.editingFinished.connect(lambda: self.set_axis(width=self.axw.value() or None))
        self.curve = QComboBox(); self.curve.setMinimumWidth(170); self.curve.setToolTip("Which curve - or all")
        self.curve.currentIndexChanged.connect(lambda *_: self.show_state())
        self.lw = QDoubleSpinBox(); self.lw.setRange(0, 10); self.lw.setSingleStep(0.25); self.lw.setSpecialValueText("auto"); self.lw.setSuffix(" pt")
        self.lw.setToolTip("Line weight"); self.lw.editingFinished.connect(lambda: self.set_line(width=self.lw.value() or None))
        mode = lambda i: (lambda: w.modes.button(i).click())
        # ------------------------------------------------------------ the tabs
        self._add("Home", [
            _group("Clipboard", _big("⧉", "Copy", "Copy the picture of the graph (Ctrl+Shift+C)", lambda: w.copy_view()), _col(_small("🖼", "Save picture", "Save the picture", lambda: w.save_view()),
                   _small("⟲", "Reset look", "Back to how the app draws this graph", self.reset))),
            _group("Font", _col(_row(self.family, self.size, grow, shrink), _row(self.bold, self.italic, self.sub, self.sup, self.tcol, clear)), launcher=self.font_dialog),
            _group("Text (or click it in the graph)", _col(_row(self.role, self.which), _row(self.edit, _btn("Apply", "Apply the typed title", self.apply_text)))),
            _group("Editing", _col(_small("↶", "Undo", "Undo the last change of this graph's look (Ctrl+Z)", self.undo), _small("↷", "Redo", "Redo (Ctrl+Y)", self.redo),
                   _small("✎", "Edit on the graph", "Click a text, a curve or the axes in the graph; double click a title to type it; right click for more", lambda: self._say("Click a text, a curve or the axes in the graph; double click a title to type it; right click for more."))))
        ])
        self._add("Insert", [
            _group("Design", _big("✏", "Sketch a design", "Draw how the figure should look (frames, the zoom, curves, titles, legend) - or trace a photo of a sketch - and the app lays your graphs out that way", self.sketch)),
            _group("Graphs", _big("➕", "Add files", "Add data files (Ctrl+O)", lambda: w.add_files()), _big("▦", "Panel figure", "A figure for a paper: the ticked graphs as (a), (b) …", lambda: w.make_board() if hasattr(w, "make_board") else None)),
        ])
        self._add("Draw", [
            _group("Draw", _big("✍", "Draw freely", "Draw your design with a pen, your finger (touch screen) or the mouse", lambda: self.sketch_pen())),
            _group("Mouse on the graph", _big("🔍", "Zoom", "Drag a box to zoom (Z)", mode(0)), _big("✋", "Pan", "Drag to move (P)", mode(1)), _big("↔", "Select range", "Drag a 2θ / x range (S)", mode(2)),
                   _big("⤢", "Reset axes", "The whole graph again (double click on it, Ctrl+R)", lambda: w.reset_axes())),
        ])
        self.gallery = QWidget(); gl = QHBoxLayout(self.gallery); gl.setContentsMargins(0, 0, 0, 0); gl.setSpacing(3)
        for name, tip, fmt in LOOKS:
            b = QToolButton(); b.setText(name.replace("&", "&&")); b.setToolTip(tip); b.setObjectName("look"); b.setFixedSize(92, 52)
            if fmt:
                st = (fmt.get("text") or {}).get("axis_titles") or (fmt.get("text") or {}).get("title") or {}
                ff = b.font(); ff.setBold(bool(st.get("bold"))); ff.setPointSizeF(9.5 if st.get("size", 0) < 15 else 11.5)
                if st.get("family"): ff.setFamily(st["family"])
                b.setFont(ff)
                if st.get("colour") and st["colour"] != "#000000": b.setStyleSheet(f"color: {st['colour']};")
            b.clicked.connect(lambda *_, f=fmt, n=name: self.apply_look(f, n))
            gl.addWidget(b)
        self._add("Design", [
            _group("Looks", self.gallery),
            _group("Page and parts", _col(self.orient, self.title_on, self.legend)),
        ])
        self._add("Layout", [
            _group("Put the ticked graphs together", _big("☰", "Stack", "One above the other with an offset", lambda: w.tools.group("stack")), _big("≋", "Overlay", "On common axes", lambda: w.tools.group("overlay")),
                   _big("▤", "Panels", "One panel each", lambda: w.tools.group("panels")), _big("✨", "Decide for me", "XRD fits and patterns: the app decides", lambda: w.tools.xrd_auto()),
                   _big("▦", "Panel figure", "A figure for a paper: the ticked graphs as (a), (b) …", lambda: w.make_board() if hasattr(w, "make_board") else None)),
            _group("Graph type", _col(self.kind)),
        ])
        self._add("Axes", [
            _group("Range (Enter applies)", _col(_row(self.x0, self.x1), _row(self.y0, self.y1)), _col(_btn("Apply", "Use these ranges", self.apply_ranges), _btn("Automatic", "The app's ranges again", self.auto_ranges))),
            _group("Axes", _big("▭", "Axis colour", "Colour of the axes, ticks included", lambda: self.pick_colour("axis")), _col(QLabel("Weight"), self.axw)),
        ])
        self._add("Lines", [
            _group("Curves", _col(self.curve, _row(QLabel("Weight"), self.lw)), _big("╱", "Line colour", "Colour of this curve (or of all)", lambda: self.pick_colour("line")),
                   _big("⟲", "Automatic", "The app's colours and weights again", lambda: self.set_fmt(lines=None))),
        ])
        # ------------------------------------------------------------ quick access (left) and the ribbon's own buttons (right)
        qa = QWidget(); qh = QHBoxLayout(qa); qh.setContentsMargins(4, 0, 8, 0); qh.setSpacing(0)
        for g_, tip, fn in (("💾", "Save the session (Ctrl+S)", lambda: w.save_session()), ("↶", "Undo (Ctrl+Z)", self.undo), ("↷", "Redo (Ctrl+Y)", self.redo)):
            qh.addWidget(_small(g_, "", tip, fn))

        rc = QWidget(); rh = QHBoxLayout(rc); rh.setContentsMargins(0, 0, 4, 0); rh.setSpacing(0)
        self.fold = _small("⌃", "", "Show tabs only / the whole ribbon (Ctrl+F1 hides it)", self.toggle_fold)
        opts = QToolButton(); opts.setText("⚙"); opts.setAutoRaise(True); opts.setToolTip("Ribbon display options and Customise the ribbon"); opts.setPopupMode(QToolButton.InstantPopup)
        om = QMenu(opts)
        for i, t in enumerate(self.MODES):
            om.addAction(t, lambda i=i: self.set_display(i))
        om.addSeparator(); om.addAction("Customise the ribbon…", self.customise)
        opts.setMenu(om)
        rh.addWidget(self.fold); rh.addWidget(opts)
        self.head = QWidget(objectName="ribhead"); hh = QHBoxLayout(self.head); hh.setContentsMargins(6, 0, 6, 0); hh.setSpacing(4)
        hh.addWidget(qa); hh.addWidget(self.bar); hh.addStretch(1); hh.addWidget(rc)
        self.tabBarDoubleClicked.connect(lambda *_: self.toggle_fold())
        self.tabBarClicked.connect(lambda *_: self.set_display(0) if self.display == 1 else None)
        self.setCurrentIndex(0)
        try:
            import workspace_qt as WQ
            cfg = WQ.load_cfg()
        except Exception:
            cfg = {}
        self.hidden = set(cfg.get("ribbon_hidden") or [])
        self.apply_hidden()
        self.display = 0
        mode0 = cfg.get("ribbon_mode")
        if mode0 is None:                                              # a small screen: the ribbon starts folded to its tabs (a click opens it)
            try:
                from PySide6.QtWidgets import QApplication
                mode0 = 1 if QApplication.primaryScreen().availableGeometry().height() < 900 else 0
            except Exception:
                mode0 = 0
        self.set_display(int(mode0), save=False)
        for key, fn in (("Ctrl+Z", self.undo), ("Ctrl+Y", self.redo), ("Ctrl+B", lambda: (self.bold.toggle(), self.style_text(bold=self.bold.isChecked()))),
                        ("Ctrl+Shift+I", lambda: (self.italic.toggle(), self.style_text(italic=self.italic.isChecked()))), ("Ctrl+=", lambda: self.wrap("_")),
                        ("Ctrl+Shift++", lambda: self.wrap("^")), ("Ctrl+F1", lambda: self.set_display(0 if self.display == 2 else 2))):
            sc = QShortcut(QKeySequence(key), w); sc.setContext(Qt.WindowShortcut); sc.activated.connect(fn)

    # ------------------------------------------------------------------ the ribbon itself: tabs, folding, customising
    def _add(self, name, groups):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(4, 3, 4, 1); h.setSpacing(2)
        for i, g in enumerate(groups):
            if i:
                ln = QFrame(); ln.setFrameShape(QFrame.VLine); ln.setObjectName("ribsep"); h.addWidget(ln); g.sep = ln
            h.addWidget(g); self.groups[f"{name} / {g.title}"] = g
        h.addStretch(1)
        self.addTab(w, name)

    # a tab widget's calls, kept
    def addTab(self, w, name):
        self.stack.addWidget(w); return self.bar.addTab(name)

    def count(self):
        return self.bar.count()

    def tabText(self, i):
        return self.bar.tabText(i)

    def currentIndex(self):
        return self.bar.currentIndex()

    def setCurrentIndex(self, i):
        self.bar.setCurrentIndex(i); self.stack.setCurrentIndex(i)

    def tabBar(self):
        return self.bar

    def goto(self, name):
        """Open a tab by its name."""
        for i in range(self.count()):
            if self.tabText(i) == name:
                self.setCurrentIndex(i); return i
        return -1

    def set_display(self, mode, save=True):
        """0 the whole ribbon, 1 tabs only (a click on a tab opens it), 2 hidden (Ctrl+F1, or View)."""
        self.display = mode
        full = mode == 0
        self.stack.setVisible(full)                                    # the buttons of the tab (tabs only: they fold away)
        pages = getattr(self.w, "pages", None)
        self.setVisible(mode != 2 and (pages is None or pages.currentIndex() == 0))      # Workspace only; hidden: Ctrl+F1
        self.fold.setText("⌃" if full else "⌄"); self.fold.setIcon(icon("⌃" if full else "⌄", size=18))
        if save:
            try:
                import workspace_qt as WQ
                WQ.save_cfg({"ribbon_mode": mode})
            except Exception:
                pass
            self._say(self.MODES[mode] + ".")
        return mode

    def toggle_fold(self):
        return self.set_display(1 if self.display == 0 else 0)

    def apply_hidden(self):
        for k, g in self.groups.items():
            g.setVisible(k not in self.hidden)
            if hasattr(g, "sep"):
                g.sep.setVisible(k not in self.hidden)

    def customise(self, keep=None):
        """Customise the ribbon: tick the groups you want to see (keep: a set of 'Tab / Group' names, without the dialog)."""
        if keep is None:
            d = QDialog(self.w); d.setWindowTitle("Customise the ribbon"); v = QVBoxLayout(d)
            v.addWidget(QLabel("The groups shown in the ribbon (untick what you do not need):"))
            grid = QGridLayout(); boxes = {}
            for i, k in enumerate(self.groups):
                cb = QCheckBox(k); cb.setChecked(k not in self.hidden); grid.addWidget(cb, i % 12, i // 12); boxes[k] = cb
            v.addLayout(grid)
            bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults); v.addWidget(bb)
            bb.accepted.connect(d.accept); bb.rejected.connect(d.reject)
            bb.button(QDialogButtonBox.RestoreDefaults).clicked.connect(lambda: [cb.setChecked(True) for cb in boxes.values()])
            if not d.exec():
                return None
            keep = {k for k, cb in boxes.items() if cb.isChecked()}
        self.hidden = set(self.groups) - set(keep)
        self.apply_hidden()
        try:
            import workspace_qt as WQ
            WQ.save_cfg({"ribbon_hidden": sorted(self.hidden)})
        except Exception:
            pass
        return sorted(self.hidden)

    def step_size(self, d):
        it = self.item()
        if it is None:
            return self._say("Show a graph first.")
        st = (((getattr(it, "fmt", None) or {}).get("text") or {}).get(self.role_key()) or {})
        cur = st.get("size")
        if cur is None:
            ts = sp._role_texts(self.w.fig, self.role_key())
            cur = ts[0].get_fontsize() if ts else 10.0
        return self.style_text(size=max(4.0, round(float(cur) + d, 1)))

    def font_dialog(self):
        """↘ of the Font group: the whole font dialog (family, size, bold, italic) for the chosen text."""
        ts = sp._role_texts(self.w.fig, self.role_key())
        f0 = QFont(self.family.currentText() or "Arial"); f0.setPointSizeF(float(ts[0].get_fontsize()) if ts else 10.0)
        ok, f = QFontDialog.getFont(f0, self.w, "Font")
        if isinstance(ok, QFont):
            ok, f = f, ok
        if not ok:
            return "cancelled"
        return self.style_text(family=f.family(), size=round(f.pointSizeF(), 1), bold=f.bold(), italic=f.italic())

    def apply_look(self, fmt, name=""):
        """Design > Looks: a ready-made look for this graph (its texts, axes and lines); your titles and ranges stay."""
        it = self.item()
        if it is None:
            return self._say("Show a graph first.")
        r = self.set_fmt(text=copy.deepcopy(fmt.get("text")) if fmt else None, axis=copy.deepcopy(fmt.get("axis")) if fmt else None,
                         lines=copy.deepcopy(fmt.get("lines")) if fmt else None)
        self._say(f"Look '{name}' for this graph. Undo: Ctrl+Z.")
        return r

    def sketch_pen(self):
        d = self.sketch()
        try:
            d.pad.tool = "pen"
        except Exception:
            pass
        return d

    # ------------------------------------------------------------------ helpers
    def item(self):
        it = self.w.current()
        return it if it is not None and getattr(it, "spec", None) is not None and not isinstance(it, sp.Board) else None

    def role_key(self):
        return list(ROLE_TEXT)[self.role.currentIndex()]

    def _say(self, t):
        self.w.set_status(t)
        return t

    def set_fmt(self, _it=None, **changes):
        """Change this graph's format; kept for undo; the graph is drawn again (rebuilt: titles and ranges are part of the drawing)."""
        it = _it or self.item()
        if it is None:
            return self._say("Show a graph in Workspace first (a panel figure takes the look of its graphs).")
        old = copy.deepcopy(getattr(it, "fmt", None) or {})
        new = copy.deepcopy(old)
        for k, v in changes.items():
            if v is None or v == {}:
                new.pop(k, None)
            else:
                new[k] = v
        if new == old:
            return "same"
        self.undo_st.setdefault(id(it), []).append(old); self.redo_st[id(it)] = []
        return self._apply(it, new)

    def replace_fmt(self, it, new):
        """The whole format of a graph at once (the Edit window): one step to undo."""
        old = copy.deepcopy(getattr(it, "fmt", None) or {})
        new = {k: v for k, v in (new or {}).items() if v not in (None, {}, [], "")}
        if new == old:
            return "same"
        self.undo_st.setdefault(id(it), []).append(old); self.redo_st[id(it)] = []
        return self._apply(it, new)

    def edit_dialog(self, it=None):
        """Edit this graph…: titles, fonts, axes, curves, legend, look (and the zoom / pattern-or-fit of XRD) in one window."""
        it = it or self.item()
        if it is None:
            return self._say("Show a graph first.")
        d = EditDialog(self, it)
        self._edit_dlg = d
        d.show()
        return d

    def _apply(self, it, fmt):
        it.fmt = fmt
        if isinstance(it, sp.Combined):                               # a combined figure is made again when the list changes: its look is kept by its graphs
            if not hasattr(self.w, "group_fmt"):
                self.w.group_fmt = {}
            self.w.group_fmt[tuple(sp.key_of(m) for m in it.members)] = fmt
        try:
            if isinstance(it, sp.Item):
                it.build(self.w.opt, it.kind)
            else:
                it.build()
        except Exception as e:
            return self._say(f"Not drawn with that change: {e}")
        self.w.draw()
        self.show_state()
        return self._say("Changed: " + it.title.strip()[:60] + ". Undo: Ctrl+Z.")

    def undo(self):
        it = self.item()
        st = self.undo_st.get(id(it)) if it is not None else None
        if not st:
            return self._say("Nothing to undo for this graph.")
        self.redo_st.setdefault(id(it), []).append(copy.deepcopy(getattr(it, "fmt", None) or {}))
        return self._apply(it, st.pop())

    def redo(self):
        it = self.item()
        st = self.redo_st.get(id(it)) if it is not None else None
        if not st:
            return self._say("Nothing to redo.")
        self.undo_st.setdefault(id(it), []).append(copy.deepcopy(getattr(it, "fmt", None) or {}))
        return self._apply(it, st.pop())

    def reset(self):
        it = self.item()
        if it is None or not getattr(it, "fmt", None):
            return self._say("This graph has the app's own look.")
        self.undo_st.setdefault(id(it), []).append(copy.deepcopy(it.fmt))
        return self._apply(it, {})

    # ------------------------------------------------------------------ text
    def current_text(self):
        it = self.item()
        if it is None:
            return ""
        f = getattr(it, "fmt", None) or {}
        r = self.role_key()
        if r == "title":
            return f.get("title") if f.get("title") is not None else str(it.spec.get("title", ""))
        if r == "axis_titles":
            if self.which.currentIndex() == 0:
                return f.get("xtitle") or str(it.spec.get("xname", ""))
            named = [p for p in it.spec.get("panels", []) if str(p.get("yname", "")).strip()]
            return f.get("ytitle") or (str(named[0]["yname"]) if named else "")
        return ""

    def show_state(self):
        """The ribbon shows the format of what is chosen."""
        it = self.item()
        r = self.role_key()
        self.which.setVisible(r == "axis_titles")
        self.edit.setEnabled(r in ("title", "axis_titles"))
        self.edit.setText(self.current_text())
        st = (((getattr(it, "fmt", None) or {}).get("text") or {}).get(r) or {}) if it is not None else {}
        self.family.setCurrentText(st.get("family") or ""); self.size.setCurrentText(str(st.get("size") or "").rstrip("0").rstrip(".") if st.get("size") else "")
        self.bold.setChecked(bool(st.get("bold"))); self.italic.setChecked(bool(st.get("italic")))
        if it is not None:
            labs = ["All curves"] + list(dict.fromkeys(str(c.get("label")) for p in it.spec.get("panels", []) for c in p.get("curves", []) if not str(c.get("label", "")).startswith("_")))
            if [self.curve.itemText(i) for i in range(self.curve.count())] != labs:
                self.curve.blockSignals(True); self.curve.clear(); self.curve.addItems(labs); self.curve.blockSignals(False)
            k = self.kind.findText(it.kind)
            if k >= 0:
                self.kind.setCurrentIndex(k)
            f = getattr(it, "fmt", None) or {}
            xl, yl = f.get("xlim"), f.get("ylim")
            for e_, v in ((self.x0, xl and xl[0]), (self.x1, xl and xl[1]), (self.y0, yl and yl[0]), (self.y1, yl and yl[1])):
                e_.setText("" if v in (None, "") else f"{float(v):g}")
            self.legend.setCurrentIndex({None: 0, "on": 1, "off": 2}.get(f.get("legend"), 0))
            self.title_on.setCurrentIndex(1 if f.get("hide_title") else 0)

    def apply_text(self):
        r = self.role_key(); t = self.edit.text()
        if r == "title":
            return self.set_fmt(title=t)
        if r == "axis_titles":
            return self.set_fmt(**({"xtitle": t or None} if self.which.currentIndex() == 0 else {"ytitle": t or None}))
        return self._say("Peak labels, numbers and the legend come from your data: change their font, size and colour here.")

    def wrap(self, mark):
        """X² / X₂: the selected letters of the title box become superscript / subscript (^{..} / _{..})."""
        e = self.edit
        if not e.isEnabled():
            self.role.setCurrentIndex(1)
        s, n = e.selectionStart(), len(e.selectedText())
        t = e.text()
        if s < 0 or n == 0:
            e.insert(mark + "{}"); e.setCursorPosition(e.cursorPosition() - 1)
            return self._say("Type the superscript / subscript letters between the braces, then Enter.")
        e.setText(t[:s] + mark + "{" + t[s:s + n] + "}" + t[s + n:])
        return self.apply_text()

    def style_text(self, **kw):
        it = self.item()
        if it is None:
            return self._say("Show a graph first.")
        r = self.role_key()
        txt = copy.deepcopy((getattr(it, "fmt", None) or {}).get("text") or {})
        st = dict(txt.get(r) or {})
        for k, v in kw.items():
            if v is None or v == "":
                st.pop(k, None)
            else:
                st[k] = v
        if st:
            txt[r] = st
        else:
            txt.pop(r, None)
        return self.set_fmt(text=txt or None)

    def _size(self):
        try:
            v = float(self.size.currentText().replace(",", ".")) if self.size.currentText().strip() else None
        except ValueError:
            return self._say("The size is a number of points, e.g. 10.")
        return self.style_text(size=v)

    def clear_text(self):
        return self.style_text(family=None, size=None, bold=None, italic=None, colour=None)

    # ------------------------------------------------------------------ colours, axes, lines
    def pick_colour(self, what, colour=None):
        if colour is None:
            c = QColorDialog.getColor(QColor(0, 0, 0), self, "Colour")
            if not c.isValid():
                return "cancelled"
            colour = "#%02x%02x%02x" % (c.red(), c.green(), c.blue())
        if what == "text":
            return self.style_text(colour=colour)
        if what == "axis":
            return self.set_axis(colour=colour)
        return self.set_line(colour=colour)

    def set_axis(self, **kw):
        it = self.item()
        if it is None:
            return self._say("Show a graph first.")
        a = dict((getattr(it, "fmt", None) or {}).get("axis") or {})
        a.update({k: v for k, v in kw.items() if v is not None}); [a.pop(k) for k, v in kw.items() if v is None and k in a]
        return self.set_fmt(axis=a or None)

    def set_line(self, **kw):
        it = self.item()
        if it is None:
            return self._say("Show a graph first.")
        key = "*" if self.curve.currentIndex() <= 0 else self.curve.currentText()
        ln = copy.deepcopy((getattr(it, "fmt", None) or {}).get("lines") or {})
        d = dict(ln.get(key) or {})
        d.update({k: v for k, v in kw.items() if v is not None}); [d.pop(k) for k, v in kw.items() if v is None and k in d]
        if d:
            ln[key] = d
        else:
            ln.pop(key, None)
        return self.set_fmt(lines=ln or None)

    def apply_ranges(self):
        def num(e):
            t = e.text().strip().replace(",", ".")
            return float(t) if t else None
        try:
            x0, x1, y0, y1 = (num(e) for e in (self.x0, self.x1, self.y0, self.y1))
        except ValueError:
            return self._say("The ranges are numbers.")
        it = self.item()
        if it is None:
            return self._say("Show a graph first.")
        xs = it.spec.get("xlim") or (None, None); ys = (it.spec.get("panels") or [{}])[0].get("ylim") or (None, None)
        xl = [x0 if x0 is not None else min(xs), x1 if x1 is not None else max(xs)] if (x0 is not None or x1 is not None) and None not in xs else None
        yl = [y0 if y0 is not None else ys[0], y1 if y1 is not None else ys[1]] if (y0 is not None or y1 is not None) and None not in ys else None
        return self.set_fmt(xlim=xl, ylim=yl)

    def auto_ranges(self):
        return self.set_fmt(xlim=None, ylim=None)

    def set_zoom(self, mode=None, rng_text=None):
        """The zoomed part of this graph: 0 as in Settings, 1 on (your range or the app's), 2 off."""
        import re
        mode = 1 if mode is None else mode
        t = self.w.xrd_zoom_rng.text() if rng_text is None else rng_text
        m = re.findall(r"-?\d+(?:[.,]\d+)?", t or "")
        rng = sorted(float(v.replace(",", ".")) for v in m[:2]) if len(m) >= 2 and mode == 1 else None
        it0 = self.item()
        if mode == 1 and not rng and it0 is not None and not str(it0.kind).startswith(("XRD", "Fit")):      # other graphs: the busiest part of the curve
            try:
                c = it0.spec["panels"][0]["curves"][0]; z = sp.auto_zoom(c["x"], c["y"]); rng = list(z) if z else None
            except Exception:
                rng = None
        r = self.set_fmt(zoom_off=True if mode == 2 else None, zoom_on=True if mode == 1 and not rng else None, zoom=rng)
        it = self.item()
        if mode == 1 and it is not None and not any(p.get("inset") for p in (it.spec.get("panels") or []) + [q for c in (it.spec.get("cols") or []) for q in c.get("panels", [])]):
            return self._say("No zoomed part for this graph: type a range inside its x axis (e.g. 27-37), narrower than the whole axis.")
        return r

    def change_kind(self):
        it = self.item()
        if not isinstance(it, sp.Item):
            return self._say("Show a single graph to change its kind.")
        k = self.kind.currentText()
        try:
            it.build(self.w.opt, k)
        except Exception as e:
            return self._say(f"Not drawn as {k}: {e}")
        self.w.regroup(); self.w.refresh_list()
        if it in self.w.items:
            self.w.list.setCurrentRow(self.w.items.index(it))
        return self._say(f"{it.title.strip()[:50]} drawn as {k}.")

    # ------------------------------------------------------------------ editing on the graph itself (click, double click, right click, drag)
    def hit(self, e):
        """What is under the pointer: ('text', role, artist) / ('inset', parent axes, inset axes) / ('curve', label, line) / ('axis', axes) / None."""
        fig = self.w.fig
        for r in ("title", "axis_titles", "legend", "labels", "numbers"):
            for t in sp._role_texts(fig, r):
                try:
                    if t.get_visible() and t.contains(e)[0]:
                        return ("text", r, t)
                except Exception:
                    pass
        for ax in fig.axes:
            for iax in getattr(ax, "child_axes", []):
                try:
                    if iax.get_window_extent().contains(e.x, e.y):
                        return ("inset", ax, iax)
                except Exception:
                    pass
        for ax in fig.axes:
            for ln in ax.get_lines():
                lab = str(ln.get_label())
                if lab.startswith("_") or len(ln.get_xdata()) <= 3:
                    continue
                try:
                    if ln.contains(e)[0]:
                        return ("curve", lab, ln)
                except Exception:
                    pass
        for ax in fig.axes:
            try:
                bb = ax.get_window_extent()
                if (bb.x0 - 6 <= e.x <= bb.x1 + 6 and bb.y0 - 6 <= e.y <= bb.y1 + 6) and not (bb.x0 + 6 < e.x < bb.x1 - 6 and bb.y0 + 6 < e.y < bb.y1 - 6):
                    return ("axis", ax)
            except Exception:
                pass
        return None

    def mark(self, artist):
        """A thin frame round what is chosen, so you see it."""
        from matplotlib.patches import Rectangle
        fig = self.w.fig
        for p_ in list(fig.patches) + list(fig.artists):
            if p_.get_gid() == "chosen":
                try:
                    p_.remove()
                except Exception:
                    pass
        try:
            r = self.w.canvas.get_renderer(); bb = artist.get_window_extent(r).transformed(fig.transFigure.inverted())
            fig.add_artist(Rectangle((bb.x0 - 0.004, bb.y0 - 0.004), bb.width + 0.008, bb.height + 0.008, transform=fig.transFigure, fill=False,
                                     ec="#2563EB", lw=1.2, ls="--", gid="chosen"))
            self.w.canvas.draw_idle()
        except Exception:
            pass

    def choose(self, h):
        """Click: the ribbon opens on what was clicked, ready to change."""
        kind = h[0]
        if kind == "text":
            r, t = h[1], h[2]
            self.role.setCurrentIndex(list(ROLE_TEXT).index(r))
            if r == "axis_titles":
                self.which.setCurrentIndex(0 if any(t is a.xaxis.label for a in self.w.fig.axes) else 1)
            self.goto("Home"); self.show_state(); self.mark(t)
            if r in ("title", "axis_titles"):
                self.edit.setFocus(); self.edit.selectAll()
            self._say(f"Chosen: {ROLE_TEXT[r].lower()}. Double click to retype it" if r in ("title", "axis_titles") else f"Chosen: {ROLE_TEXT[r].lower()}.")
            return r
        if kind == "curve":
            self.show_state(); k = self.curve.findText(h[1])
            if k >= 0:
                self.curve.setCurrentIndex(k)
            self.goto("Lines"); self.mark(h[2])
            self._say(f"Chosen: the curve '{h[1]}'. Line colour and weight in Lines, or right click.")
            return "curve"
        if kind == "axis":
            self.goto("Axes"); self.mark(h[1])
            self._say("Chosen: the axes. Range, colour and weight in Axes, or right click.")
            return "axis"
        if kind == "inset":
            self.mark(h[2]); self._say("The zoomed part: drag it to move it; right click to switch it off.")
            return "inset"
        return None

    def on_click(self, e):
        if e.button != 1 or getattr(e, "dblclick", False) or any(b.isChecked() for b in self.w.modes.buttons()):      # Zoom / Pan / Select range: they own the mouse
            return None
        h = self.hit(e)
        if h is None:
            return None
        if h[0] == "text" and h[1] == "labels":                        # a peak label or a curve's name: drag it to where you want it
            lab = self.find_label(h[2])
            if lab is not None:
                self._ldrag = dict(key=lab, art=h[2], x=e.x, y=e.y, moved=False)
                self.mark(h[2]); self._say("Drag the label to where you want it. Right click › Put the labels back undoes it.")
                return "label"
        if h[0] == "inset":                                            # start moving the zoomed part
            bb = h[1].get_window_extent(); ib = h[2].get_window_extent()
            self._drag = dict(x=e.x, y=e.y, parent=(bb.x0, bb.y0, bb.width, bb.height), rect=((ib.x0 - bb.x0) / bb.width, (ib.y0 - bb.y0) / bb.height, ib.width / bb.width, ib.height / bb.height), iax=h[2])
        return self.choose(h)

    def find_label(self, art):
        """The label of the graph that this text on the screen is: its key for 'moved by you', or None."""
        it = self.item(); ax = art.axes
        if it is None or ax is None or art.get_transform() != ax.transData:
            return None
        x, y = art.get_position()
        for pi, p_ in enumerate(sp.all_panels(it.spec)):
            y0, y1 = p_.get("ylim") or (0, 1); tol = 1e-6 * (abs(y1 - y0) or 1.0)
            for q in p_.get("placed") or []:
                if abs(q[3] - x) < 1e-9 + 1e-9 * abs(x) and abs(q[4] - y) <= tol and sp._lb(q[2]) == art.get_text():
                    return sp.label_key(pi, q)
            for q in p_.get("texts") or []:
                if abs(q[0] - x) < 1e-9 + 1e-9 * abs(x) and abs(q[1] - y) <= tol and str(q[2]) == art.get_text():
                    return f"{pi}|name|{q[2]}"
        return None

    def on_motion(self, e):
        ld = getattr(self, "_ldrag", None)
        if ld and e.x is not None:
            if abs(e.x - ld["x"]) + abs(e.y - ld["y"]) < 4 and not ld["moved"]:
                return None
            a = ld["art"]; x, y = a.axes.transData.inverted().transform((e.x, e.y))
            a.set_position((x, y)); ld["moved"] = True; ld["new"] = (float(x), float(y))
            for p_ in list(self.w.fig.artists):
                if p_.get_gid() == "chosen":
                    p_.remove()
            self.w.canvas.draw_idle()
            return ld["new"]
        d = getattr(self, "_drag", None)
        if not d or e.x is None:
            return None
        px, py, pw, ph = d["parent"]; fx, fy, fw, fh = d["rect"]
        nx = min(max(fx + (e.x - d["x"]) / pw, 0.0), 1 - fw); ny = min(max(fy + (e.y - d["y"]) / ph, 0.0), 1 - fh)
        try:
            from matplotlib.transforms import Bbox
            fig = self.w.fig; inv = fig.transFigure.inverted()
            (x0, y0), (x1, y1) = inv.transform([(px + nx * pw, py + ny * ph), (px + (nx + fw) * pw, py + (ny + fh) * ph)])
            d["iax"].set_axes_locator(None); d["iax"].set_position(Bbox([[x0, y0], [x1, y1]])); self.w.canvas.draw_idle()
        except Exception:
            pass
        d["new"] = (round(nx, 3), round(ny, 3), round(fw, 3), round(fh, 3))
        return d["new"]

    def on_release(self, e):
        ld = getattr(self, "_ldrag", None); self._ldrag = None
        if ld:
            if not ld.get("moved"):
                return self.choose(("text", "labels", ld["art"]))     # a plain click: the label is chosen, as before
            it = self.item()
            mv = dict((getattr(it, "fmt", None) or {}).get("moved") or {}); mv[ld["key"]] = [ld["new"][0], ld["new"][1]]
            return self.set_fmt(moved=mv)
        d = getattr(self, "_drag", None); self._drag = None
        if not d or not d.get("new") or d["new"] == tuple(round(v, 3) for v in d["rect"]):
            return None
        return self.set_fmt(inset_rect=list(d["new"]))

    def on_double(self, e):
        """Double click on a title or an axis title: type it again (X² as ^{2}, X₂ as _{2}). True when it was a text."""
        from PySide6.QtWidgets import QInputDialog
        h = self.hit(e)
        if not h or h[0] != "text" or h[1] not in ("title", "axis_titles"):
            return False
        self.choose(h)
        t, ok = QInputDialog.getText(self.w, "Edit the text", "Text (superscript ^{...}, subscript _{...}):", text=self.edit.text())
        if ok:
            self.edit.setText(t); self.apply_text()
        return True

    def menu_items(self, m, pos):
        """Right click on the graph: what can be changed about the thing under the pointer, first."""
        c = self.w.canvas; dpr = c.devicePixelRatioF() if hasattr(c, "devicePixelRatioF") else 1.0
        ev = type("E", (), {})(); ev.x = pos.x() * dpr; ev.y = (c.height() - pos.y()) * dpr; ev.button = 3; ev.dblclick = False; ev.inaxes = None
        h = self.hit(ev); it = self.item()
        if it is None:
            return None
        ed = m.addAction("✎  Edit this graph…", lambda: self.edit_dialog(it)); f_ = ed.font(); f_.setBold(True); ed.setFont(f_)
        if not h:                                                 # on the graph but not on one part of it: the whole graph
            m.addAction("Title…", lambda: (self.role.setCurrentIndex(0), self._ask_text("title")))
            m.addAction("x axis title…", lambda: self._ask_text("x"))
            m.addAction("y axis title…", lambda: self._ask_text("y"))
            lk = m.addMenu("Look")
            for n_, tip_, f_l in LOOKS:
                lk.addAction(n_, lambda f_l=f_l, n_=n_: self.apply_look(f_l, n_))
            lg = m.addMenu("Legend")
            for t_, v_ in (("Automatic", None), ("On", "on"), ("Off", "off")):
                lg.addAction(t_, lambda v_=v_: self.set_fmt(legend=v_))
            m.addAction("Axis range…", lambda: self.edit_dialog(it).tabs.setCurrentIndex(2))
        m.addSeparator()
        if h and h[0] == "text":
            self.choose(h); r = h[1]
            if r in ("title", "axis_titles"):
                m.addAction("Edit the text… (double click)", lambda: self.on_double(ev))
            st = ((getattr(it, "fmt", None) or {}).get("text") or {}).get(r) or {}
            size0 = float(st.get("size") or h[2].get_fontsize())
            m.addAction("Bigger letters", lambda: self.style_text(size=round(size0 + 1, 1)))
            m.addAction("Smaller letters", lambda: self.style_text(size=max(4.0, round(size0 - 1, 1))))
            m.addAction("Bold on / off", lambda: self.style_text(bold=not bool(st.get("bold", h[2].get_fontweight() in ("bold", 700)))))
            m.addAction("Italic on / off", lambda: self.style_text(italic=not bool(st.get("italic"))))
            m.addAction("Colour…", lambda: self.pick_colour("text"))
            m.addAction("Back to the app's look for this text", self.clear_text)
        if (getattr(it, "fmt", None) or {}).get("moved"):
            if h and h[0] == "text" and h[1] == "labels" and self.find_label(h[2]) in it.fmt["moved"]:
                k_ = self.find_label(h[2])
                m.addAction("Put this label back", lambda: self.set_fmt(moved={a: b for a, b in it.fmt["moved"].items() if a != k_} or None))
            m.addAction("Put all moved labels back", lambda: self.set_fmt(moved=None))
        elif h and h[0] == "curve":
            self.choose(h); lab = h[1]; w0 = float(h[2].get_linewidth())
            m.addAction(f"Colour of '{lab}'…", lambda: self.pick_colour("line"))
            m.addAction("Thicker", lambda: self.set_line(width=round(w0 + 0.5, 2)))
            m.addAction("Thinner", lambda: self.set_line(width=max(0.25, round(w0 - 0.5, 2))))
        elif h and h[0] == "axis":
            m.addAction("Axis colour…", lambda: self.pick_colour("axis"))
            m.addAction("Thicker axes", lambda: self.set_axis(width=round(float(((it.fmt or {}).get("axis") or {}).get("width") or 1.5) + 0.5, 2)))
            m.addAction("Axis range… (Axes tab)", lambda: (self.goto("Axes"), self.x0.setFocus()))
        if str(getattr(it, "kind", "")).startswith(("XRD", "Fit")):
            on = self.has_zoom(it)
            m.addAction("Zoomed part: switch off" if on else "Zoomed part: switch on", lambda: self.w.xrd_zoom.setChecked(not on))
        m.addSeparator()
        m.addAction("Undo (Ctrl+Z)", self.undo); m.addAction("Redo (Ctrl+Y)", self.redo); m.addAction("Back to the app's look", self.reset)
        m.addSeparator()
        return h

    def _ask_text(self, which):
        """Title / x axis title / y axis title: typed in a small window (^{..} superscript, _{..} subscript)."""
        from PySide6.QtWidgets import QInputDialog
        it = self.item()
        if it is None:
            return None
        f = getattr(it, "fmt", None) or {}
        cur = {"title": f.get("title") if f.get("title") is not None else it.spec.get("title", ""), "x": f.get("xtitle") or it.spec.get("xname", ""),
               "y": f.get("ytitle") or next((p.get("yname") for p in it.spec.get("panels", []) if str(p.get("yname", "")).strip()), "")}[which]
        t, ok = QInputDialog.getText(self.w, "Edit the text", {"title": "Graph title", "x": "x axis title", "y": "y axis title"}[which] + " (^{..} superscript, _{..} subscript):", text=str(cur))
        if not ok:
            return None
        return self.set_fmt(**({"title": t} if which == "title" else {"xtitle": t or None} if which == "x" else {"ytitle": t or None}))

    def has_zoom(self, it):
        return any(p.get("inset") for p in (it.spec.get("panels") or []) + [q for c in (it.spec.get("cols") or []) for q in c.get("panels", [])])

    def xrd_bar(self):
        """Beside Zoom / Pan / Select range, for XRD graphs only: the zoomed part on or off, and the middle part of a fit."""
        it = self.item(); w = self.w
        xrd = it is not None and str(getattr(it, "kind", "")).startswith(("XRD", "Fit"))
        for wd in (w.xrd_zoom, w.xrd_zoom_rng):
            wd.setVisible(xrd)
        fit = xrd and str(it.kind).startswith("Fit")
        w.xrd_view.setVisible(fit)
        pattern = fit and sp.fit_view(it, w.opt) == sp.FIT_VIEWS[0]
        w.xrd_mid.setVisible(fit and not pattern); w.xrd_mid_lab.setVisible(fit and not pattern)
        if fit:
            w.xrd_view.blockSignals(True); w.xrd_view.setCurrentText(sp.fit_view(it, w.opt)); w.xrd_view.blockSignals(False)
        if xrd:
            w.xrd_zoom.blockSignals(True); w.xrd_zoom.setChecked(self.has_zoom(it)); w.xrd_zoom.blockSignals(False)
            f = getattr(it, "fmt", None) or {}
            w.xrd_zoom_rng.setText(f"{f['zoom'][0]:g}-{f['zoom'][1]:g}" if f.get("zoom") else "")
        if fit:
            w.xrd_mid.blockSignals(True); w.xrd_mid.setCurrentText((getattr(it, "fmt", None) or {}).get("fit_middle") or sp.FIT_MIDDLE[0]); w.xrd_mid.blockSignals(False)

    def zoom_switch(self, on):
        r = self.set_zoom(1 if on else 2, self.w.xrd_zoom_rng.text())
        self.xrd_bar()
        return r

    def sketch(self):
        import sketch_pad
        return sketch_pad.open_pad(self.w)


class EditDialog(QDialog):
    """Edit this graph (right click on it): everything about its look in one window, as Plot Details in Origin. Apply / OK make one
    step that Ctrl+Z undoes; Cancel changes nothing. No number of your data is changed."""
    def __init__(self, rb, it):
        from PySide6.QtWidgets import QTabWidget, QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView
        super().__init__(rb.w)
        self.rb, self.it = rb, it
        self.setWindowTitle("Edit this graph - " + it.title.strip()[:60]); self.resize(620, 520)
        f0 = copy.deepcopy(getattr(it, "fmt", None) or {}); self.f0 = f0
        v = QVBoxLayout(self)
        self.tabs = QTabWidget(); v.addWidget(self.tabs, 1)
        # titles
        t = QWidget(); fl = QFormLayout(t)
        sp_ = it.spec
        self.e_title = QLineEdit(f0.get("title") if f0.get("title") is not None else str(sp_.get("title", "")))
        self.e_x = QLineEdit(f0.get("xtitle") or str(sp_.get("xname", "")))
        self.e_y = QLineEdit(f0.get("ytitle") or next((str(p.get("yname")) for p in sp_.get("panels", []) if str(p.get("yname", "")).strip()), ""))
        self.c_hide = QCheckBox("Hide the title"); self.c_hide.setChecked(bool(f0.get("hide_title")))
        fl.addRow("Graph title", self.e_title); fl.addRow("x axis title", self.e_x); fl.addRow("y axis title", self.e_y); fl.addRow("", self.c_hide)
        row = QHBoxLayout()
        for txt, mark in (("x² superscript", "^"), ("x₂ subscript", "_")):
            b = QPushButton(txt); b.clicked.connect(lambda _c=False, mk=mark: self.wrap(mk)); row.addWidget(b)
        row.addStretch(1); fl.addRow("Selected letters", row)
        fl.addRow(QLabel("Select letters in a title and press x² or x₂ (written ^{..} and _{..}; real superscript and subscript in the graph and in Origin).", objectName="soft", wordWrap=True))
        self.tabs.addTab(t, "Titles")
        # text
        t = QWidget(); fl = QFormLayout(t)
        self.txt = copy.deepcopy(f0.get("text") or {})
        self.r_role = QComboBox(); self.r_role.addItems(list(ROLE_TEXT.values())); fl.addRow("Text", self.r_role)
        self.r_family = QComboBox(); self.r_family.setEditable(True); self.r_family.addItems([""] + sp.FONT_FAMILIES); fl.addRow("Font", self.r_family)
        self.r_size = QComboBox(); self.r_size.setEditable(True); self.r_size.addItems([""] + SIZES); fl.addRow("Size (pt)", self.r_size)
        self.r_bold = QComboBox(); self.r_bold.addItems(["As the app draws it", "Bold", "Normal"]); fl.addRow("Weight", self.r_bold)
        self.r_italic = QCheckBox("Italic"); fl.addRow("", self.r_italic)
        self.r_col = QPushButton("Colour…"); self.r_col.clicked.connect(lambda: self.pick("text")); fl.addRow("Colour", self.r_col)
        self._role_prev = 0
        self.r_role.currentIndexChanged.connect(self.role_changed); self.load_role(0)
        self.tabs.addTab(t, "Text")
        # axes
        t = QWidget(); fl = QFormLayout(t)
        xs, ys = sp_.get("xlim") or (None, None), (sp_.get("panels") or [{}])[0].get("ylim") or (None, None)
        xl, yl = f0.get("xlim") or [None, None], f0.get("ylim") or [None, None]
        self.a_x0, self.a_x1, self.a_y0, self.a_y1 = (QLineEdit("" if v_ is None else f"{float(v_):g}") for v_ in (xl[0], xl[1], yl[0], yl[1]))
        for e_, ph in ((self.a_x0, xs[0]), (self.a_x1, xs[1]), (self.a_y0, ys[0]), (self.a_y1, ys[1])):
            e_.setPlaceholderText("automatic" + (f" ({float(ph):.4g})" if ph is not None else ""))
        rx = QHBoxLayout(); rx.addWidget(self.a_x0); rx.addWidget(QLabel("to")); rx.addWidget(self.a_x1); fl.addRow("x from", rx)
        ry = QHBoxLayout(); ry.addWidget(self.a_y0); ry.addWidget(QLabel("to")); ry.addWidget(self.a_y1); fl.addRow("y from", ry)
        self.axis = copy.deepcopy(f0.get("axis") or {})
        self.a_col = QPushButton("Colour…"); self.a_col.clicked.connect(lambda: self.pick("axis")); fl.addRow("Axis colour", self.a_col)
        self.a_w = QDoubleSpinBox(); self.a_w.setRange(0, 6); self.a_w.setSingleStep(0.25); self.a_w.setSpecialValueText("automatic"); self.a_w.setSuffix(" pt")
        self.a_w.setValue(float(self.axis.get("width") or 0)); fl.addRow("Axis weight", self.a_w)
        self.tabs.addTab(t, "Axes")
        # curves
        t = QWidget(); vl = QVBoxLayout(t)
        labs = ["All curves"] + list(dict.fromkeys(str(c.get("label")) for p in sp_.get("panels", []) for c in p.get("curves", []) if not str(c.get("label", "")).startswith("_")))
        self.lines = copy.deepcopy(f0.get("lines") or {})
        self.tab = QTableWidget(len(labs), 3); self.tab.setHorizontalHeaderLabels(["Curve", "Colour", "Weight (pt)"]); self.tab.verticalHeader().hide()
        self.tab.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.curve_keys = []
        for r, lab in enumerate(labs):
            key = "*" if r == 0 else lab; self.curve_keys.append(key)
            self.tab.setItem(r, 0, QTableWidgetItem(lab))
            b = QPushButton(self.lines.get(key, {}).get("colour") or "automatic"); b.clicked.connect(lambda _c=False, k=key, b=b: self.pick_line(k, b)); self.tab.setCellWidget(r, 1, b)
            sw = QDoubleSpinBox(); sw.setRange(0, 10); sw.setSingleStep(0.25); sw.setSpecialValueText("automatic"); sw.setValue(float(self.lines.get(key, {}).get("width") or 0))
            sw.valueChanged.connect(lambda val, k=key: self.lines.setdefault(k, {}).__setitem__("width", val or None)); self.tab.setCellWidget(r, 2, sw)
        vl.addWidget(self.tab)
        self.tabs.addTab(t, "Curves")
        # layout and look
        t = QWidget(); fl = QFormLayout(t)
        self.l_leg = QComboBox(); self.l_leg.addItems(["Automatic", "On", "Off"]); self.l_leg.setCurrentIndex({None: 0, "on": 1, "off": 2}.get(f0.get("legend"), 0)); fl.addRow("Legend", self.l_leg)
        self.l_look = QComboBox(); self.l_look.addItems(["(keep)"] + [n for n, _t, _f in LOOKS]); fl.addRow("Look", self.l_look)
        xrd = str(getattr(it, "kind", "")).startswith(("XRD", "Fit"))
        self.l_zoom = QComboBox(); self.l_zoom.addItems(["As in Settings", "On", "Off"])
        self.l_zoom.setCurrentIndex(2 if f0.get("zoom_off") else 1 if (f0.get("zoom_on") or f0.get("zoom")) else 0)
        self.l_zr = QLineEdit(f"{f0['zoom'][0]:g}-{f0['zoom'][1]:g}" if f0.get("zoom") else ""); self.l_zr.setPlaceholderText("2θ range, e.g. 27-37 (empty: the app chooses)")
        if xrd:
            fl.addRow("Zoomed part", self.l_zoom); fl.addRow("Zoom range", self.l_zr)
        self.l_view = QComboBox(); self.l_view.addItems(sp.FIT_VIEWS); self.l_view.setCurrentText(sp.fit_view(it, rb.w.opt) if str(it.kind).startswith("Fit") else sp.FIT_VIEWS[0])
        if str(getattr(it, "kind", "")).startswith("Fit"):
            fl.addRow("Fit file shows", self.l_view)
        self.tabs.addTab(t, "Layout")
        self.msg = QLabel("", objectName="soft", wordWrap=True); v.addWidget(self.msg)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        bb.button(QDialogButtonBox.Reset).setText("Back to the app's look")
        bb.accepted.connect(lambda: (self.apply(), self.accept())); bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.Apply).clicked.connect(self.apply)
        bb.button(QDialogButtonBox.Reset).clicked.connect(lambda: (self.rb.reset(), self.close()))
        v.addWidget(bb)

    def wrap(self, mark):
        e = next((x for x in (self.e_title, self.e_x, self.e_y) if x.hasFocus() or x.hasSelectedText()), self.e_title)
        s_, n_ = e.selectionStart(), len(e.selectedText()); t = e.text()
        if s_ < 0 or n_ == 0:
            e.insert(mark + "{}"); e.setCursorPosition(e.cursorPosition() - 1)
        else:
            e.setText(t[:s_] + mark + "{" + t[s_:s_ + n_] + "}" + t[s_ + n_:])

    def _role_key(self, i=None):
        return list(ROLE_TEXT)[self.r_role.currentIndex() if i is None else i]

    def save_role(self, i):
        st = dict(self.txt.get(self._role_key(i)) or {})
        st["family"] = self.r_family.currentText().strip() or None
        try:
            st["size"] = float(self.r_size.currentText().replace(",", ".")) if self.r_size.currentText().strip() else None
        except ValueError:
            st["size"] = None
        st["bold"] = {0: None, 1: True, 2: False}[self.r_bold.currentIndex()]
        st["italic"] = True if self.r_italic.isChecked() else None
        st = {k: v for k, v in st.items() if v is not None}
        if st: self.txt[self._role_key(i)] = st
        else: self.txt.pop(self._role_key(i), None)

    def load_role(self, i):
        st = self.txt.get(self._role_key(i)) or {}
        self.r_family.setCurrentText(st.get("family") or ""); self.r_size.setCurrentText(f"{st['size']:g}" if st.get("size") else "")
        self.r_bold.setCurrentIndex(0 if st.get("bold") is None else 1 if st["bold"] else 2); self.r_italic.setChecked(bool(st.get("italic")))
        self.r_col.setText(st.get("colour") or "Colour…")

    def role_changed(self, i):
        self.save_role(self._role_prev); self.load_role(i); self._role_prev = i

    def pick(self, what):
        c = QColorDialog.getColor(QColor(0, 0, 0), self, "Colour")
        if not c.isValid():
            return None
        hx = "#%02x%02x%02x" % (c.red(), c.green(), c.blue())
        if what == "text":
            self.txt.setdefault(self._role_key(), {})["colour"] = hx; self.r_col.setText(hx)
        else:
            self.axis["colour"] = hx; self.a_col.setText(hx)
        return hx

    def pick_line(self, key, b):
        c = QColorDialog.getColor(QColor(0, 0, 0), self, "Colour of " + ("all curves" if key == "*" else key))
        if c.isValid():
            hx = "#%02x%02x%02x" % (c.red(), c.green(), c.blue()); self.lines.setdefault(key, {})["colour"] = hx; b.setText(hx)

    def collect(self):
        """The format the window shows, as one dictionary."""
        import re as _re
        self.save_role(self.r_role.currentIndex())
        f = copy.deepcopy(self.f0)
        sp_ = self.it.spec
        app_title = str(sp_.get("title", "")) if self.f0.get("title") is None else None
        f["title"] = None if (app_title is not None and self.e_title.text() == app_title) else self.e_title.text()
        f["xtitle"] = self.e_x.text() if self.e_x.text() != str(sp_.get("xname", "")) or self.f0.get("xtitle") else None
        y0 = next((str(p.get("yname")) for p in sp_.get("panels", []) if str(p.get("yname", "")).strip()), "")
        f["ytitle"] = self.e_y.text() if self.e_y.text() != y0 or self.f0.get("ytitle") else None
        f["hide_title"] = True if self.c_hide.isChecked() else None
        f["text"] = self.txt or None
        def num(e):
            t_ = e.text().strip().replace(",", ".")
            return float(t_) if t_ else None
        x0, x1, y0_, y1 = (num(e) for e in (self.a_x0, self.a_x1, self.a_y0, self.a_y1))
        xs = sp_.get("xlim") or (None, None); ys = (sp_.get("panels") or [{}])[0].get("ylim") or (None, None)
        f["xlim"] = [x0 if x0 is not None else min(xs), x1 if x1 is not None else max(xs)] if (x0 is not None or x1 is not None) and None not in xs else None
        f["ylim"] = [y0_ if y0_ is not None else ys[0], y1 if y1 is not None else ys[1]] if (y0_ is not None or y1 is not None) and None not in ys else None
        self.axis["width"] = self.a_w.value() or None
        ax_ = {k: v for k, v in self.axis.items() if v is not None}; f["axis"] = ax_ or None
        ln = {k: {kk: vv for kk, vv in d_.items() if vv is not None} for k, d_ in self.lines.items()}; ln = {k: d_ for k, d_ in ln.items() if d_}; f["lines"] = ln or None
        f["legend"] = {0: None, 1: "on", 2: "off"}[self.l_leg.currentIndex()]
        if self.l_look.currentIndex() > 0:
            lk = LOOKS[self.l_look.currentIndex() - 1][2] or {}
            f["text"] = copy.deepcopy(lk.get("text")) if lk else None; f["axis"] = copy.deepcopy(lk.get("axis")) if lk else None; f["lines"] = copy.deepcopy(lk.get("lines")) if lk else None
        if str(getattr(self.it, "kind", "")).startswith(("XRD", "Fit")):
            m_ = _re.findall(r"-?\d+(?:[.,]\d+)?", self.l_zr.text() or "")
            rng = sorted(float(v_.replace(",", ".")) for v_ in m_[:2]) if len(m_) >= 2 and self.l_zoom.currentIndex() == 1 else None
            f["zoom_off"] = True if self.l_zoom.currentIndex() == 2 else None
            f["zoom_on"] = True if self.l_zoom.currentIndex() == 1 and not rng else None
            f["zoom"] = rng
        if str(getattr(self.it, "kind", "")).startswith("Fit"):
            f["fit_view"] = self.l_view.currentText()
        return f

    def apply(self):
        r = self.rb.replace_fmt(self.it, self.collect())
        self.f0 = copy.deepcopy(getattr(self.it, "fmt", None) or {})
        self.msg.setText("Applied. Undo: Ctrl+Z." if r != "same" else "Nothing changed.")
        try:
            self.rb.xrd_bar()
        except Exception:
            pass
        return r


def install(w):
    rb = Ribbon(w)
    w.ribbon = rb
    root = w.centralWidget().layout()
    root.insertWidget(1, rb)
    rb.layout().insertWidget(0, rb.head)                               # the tabs above their buttons
    rb.set_display(rb.display, save=False)
    w.canvas.mpl_connect("button_press_event", rb.on_click)
    w.canvas.mpl_connect("motion_notify_event", rb.on_motion)
    w.canvas.mpl_connect("button_release_event", rb.on_release)
    # XRD only, beside Zoom / Pan / Select range: the zoomed part on or off (and its range), and what a fit shows between fit and difference
    from PySide6.QtWidgets import QCheckBox
    w.xrd_zoom = QCheckBox("Zoomed part"); w.xrd_zoom.setToolTip("XRD: show the zoomed part (inset) of this graph or not")
    w.xrd_zoom.toggled.connect(rb.zoom_switch)
    w.xrd_zoom_rng = QLineEdit(); w.xrd_zoom_rng.setPlaceholderText("2θ range, e.g. 27-37"); w.xrd_zoom_rng.setFixedWidth(160)
    w.xrd_zoom_rng.setToolTip("Your range for the zoomed part (Enter); empty: the app chooses the crowded region of the main peaks")
    w.xrd_zoom_rng.returnPressed.connect(lambda: (w.xrd_zoom.blockSignals(True), w.xrd_zoom.setChecked(True), w.xrd_zoom.blockSignals(False), rb.zoom_switch(True)))
    w.xrd_view = QComboBox(); w.xrd_view.addItems(sp.FIT_VIEWS)
    w.xrd_view.setToolTip("A fit file: the measured pattern with its peak labels (the basic graph), or the fit - observed, calculated, difference")
    w.xrd_view.activated.connect(lambda *_: (rb.set_fmt(fit_view=w.xrd_view.currentText()), rb.xrd_bar()))
    w.xrd_mid = QComboBox(); w.xrd_mid.addItems(sp.FIT_MIDDLE); w.xrd_mid.setToolTip("Fit: what is drawn between the fit and the difference curve")
    w.xrd_mid_lab = QLabel("Middle part:")
    w.xrd_mid.activated.connect(lambda *_: (rb.set_fmt(fit_middle=None if w.xrd_mid.currentIndex() == 0 else w.xrd_mid.currentText()), rb.xrd_bar()))
    gt = getattr(w, "graph_tools", None)
    if gt is not None:                                           # XRD only: a row of its own under Zoom / Pan / Select range (nothing is squeezed)
        from PySide6.QtWidgets import QHBoxLayout as _HB
        xr = _HB(); xr.setSpacing(6)
        for wd in (w.xrd_zoom, w.xrd_zoom_rng, w.xrd_view, w.xrd_mid_lab, w.xrd_mid):
            xr.addWidget(wd)
        xr.addStretch(1)
        host = gt.parentWidget().layout() if gt.parentWidget() is not None else None
        if host is not None:
            k = next((i for i in range(host.count()) if host.itemAt(i).layout() is gt), 0)
            host.insertLayout(k + 1, xr)
        w.xrd_row = xr
    w.list.currentRowChanged.connect(lambda *_: (rb.show_state(), rb.xrd_bar()))
    rb.show_state(); rb.xrd_bar()
    return rb

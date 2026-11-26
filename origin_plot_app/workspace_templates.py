"""The Templates page: Graph = Template x Style x Data, with multiple selection everywhere.

  Files       the files of the session (and files added here): tick several, Ctrl / Shift + click, Ctrl+A
  Columns     the sheet and columns of the file on show: what is x, what is a series, in which order (remembered per header pattern)
  Templates   every graph type of the catalogue, searchable, filtered by field / source / "works with my files"; tick several
  Styles      the style presets (house style, journals, slides ...): tick several
  Previews    every ticked combination files x templates x styles drawn from your data; enlarge a tile, tick the ones to keep
  Variants    the switches that work on every template (log, reversed, markers, normalise, offset ...) and its parameters

Batch actions on the kept previews: open all in the editor, draw all in Origin like this, export all at journal size,
apply the same style or switches to all, data of all into one Excel workbook, combine into one figure, remove.
Nothing is labelled by the app: every text on a graph comes from your file or from what you type."""
import io, json, os, re, time
from PySide6.QtCore import Qt, QSize, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap, QKeySequence, QShortcut, QAction, QColor, QBrush
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QTreeWidget,
                               QTreeWidgetItem, QComboBox, QCheckBox, QScrollArea, QGridLayout, QFrame, QProgressBar, QFileDialog, QMessageBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QSpinBox, QFormLayout, QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QHeaderView,
                               QToolButton, QSizePolicy, QInputDialog, QPlainTextEdit, QApplication)

FAMILIES = "ABCDEFGH"            # catalogue sections A-H are graph families, I-X are domain packs
SHORT = {"A": "Lines and scatter", "B": "Bars, pies and areas", "C": "Several panels or axes", "D": "Statistics", "E": "Maps, contours, images", "F": "Ternary, polar, special", "G": "Flows and hierarchies", "H": "3D",
         "I": "XRD", "J": "FTIR, Raman, NMR, XRF", "K": "Microscopy (SEM, EDS)", "L": "Particle size and porosity", "M": "Rheology and mechanics", "N": "TGA, DTG, DSC, kinetics", "O": "Calorimetry",
         "P": "Thermodynamic modelling", "Q": "Strength and durability", "R": "CO2 and sustainability", "S": "Electrochemistry", "T": "Life science", "U": "Analytical chemistry", "V": "Physics and signals",
         "W": "Environment", "X": "Chemical kinetics"}
CAT_LETTER = {"XRD & Rietveld": "I", "Phase & chemical composition": "P", "Thermal analysis (TGA / DTG / DSC)": "N", "Isothermal calorimetry": "O", "Particle size, porosity & surface": "L",
              "Spectroscopy (FTIR / Raman / NMR)": "J", "Thermodynamic modelling": "P", "Cement & concrete engineering": "Q", "Microstructure & SEM-EDS": "K", "Sustainability & CO2": "R",
              "General scientific & statistics": "D", "Basic 2D & layout": "A", "Rheology & mechanics": "M", "Electrochemistry & energy": "S", "Life science & medicine": "T", "Analytical chemistry": "U",
              "Physics & signal": "V", "Environment & geoscience": "W"}
TILE_W = 300


def _clean(name):
    """The short name of a class of templates (by instrument or by graph type)."""
    m = re.match(r"^([A-Z])\.\s*(.*)", str(name)); return SHORT.get(m.group(1), m.group(2)) if m else str(name)


class Tile(QFrame):
    """One preview: a file (or several) in one template in one style."""
    toggled = Signal()
    opened = Signal(object)

    def __init__(self, combo):
        super().__init__(); self.combo = combo; self.fig = None; self.error = ""; self.mapping = []
        self.setObjectName("tile"); self.setFrameShape(QFrame.StyledPanel); self.setFixedWidth(TILE_W + 16)
        v = QVBoxLayout(self); v.setContentsMargins(6, 6, 6, 6); v.setSpacing(4)
        self.keep = QCheckBox(combo["title"]); self.keep.setToolTip("Tick to keep this graph: the batch actions (Origin, export, combine …) work on the kept graphs")
        self.keep.toggled.connect(lambda _c: (self._look(), self.toggled.emit())); v.addWidget(self.keep)
        self.pic = QLabel("waiting …"); self.pic.setAlignment(Qt.AlignCenter); self.pic.setMinimumSize(TILE_W, int(TILE_W / 1.6)); self.pic.setWordWrap(True)
        self.pic.setStyleSheet("background: white; border: 1px solid #D8E1EC; border-radius: 6px; color: #526277;"); v.addWidget(self.pic)
        self.cap = QLabel(combo["caption"], objectName="soft"); self.cap.setWordWrap(True); v.addWidget(self.cap)
        self.setCursor(Qt.PointingHandCursor); self._look()

    def _look(self):
        self.setStyleSheet("#tile { background: %s; border: %s; border-radius: 8px; }" % (("#EAF2FF", "2px solid #2563EB") if self.keep.isChecked() else ("#FFFFFF", "1px solid #D8E1EC")))

    def show_figure(self, fig, png_bytes, mapping):
        self.fig, self.mapping, self.error = fig, mapping, ""
        pm = QPixmap(); pm.loadFromData(png_bytes); self.pic.setPixmap(pm.scaledToWidth(TILE_W, Qt.SmoothTransformation))
        self.pic.setToolTip("Double click: enlarge.  Columns used:\n" + "\n".join(f"  {a}: {b}" for a, b in mapping))

    def show_error(self, msg):
        self.fig = None; self.error = msg; self.pic.setPixmap(QPixmap()); self.pic.setText(msg); self.pic.setToolTip(msg); self.keep.setChecked(False); self.keep.setEnabled(False)

    def mouseDoubleClickEvent(self, e):
        if self.fig is not None: self.opened.emit(self)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.keep.isEnabled() and not self.keep.geometry().contains(e.position().toPoint()) and (e.modifiers() & Qt.ControlModifier):
            self.keep.toggle()
        super().mousePressEvent(e)


class TickList(QListWidget):
    """A list where selecting IS ticking: a click ticks or unticks the row (or thumbnail), Shift+click ticks the range from the
    last click, Ctrl+A ticks all that are shown, Space toggles. The ticked rows are the highlighted ones."""
    def __init__(self):
        super().__init__(); self.setSelectionMode(QAbstractItemView.MultiSelection); self._anchor = None; self.itemChanged.connect(lambda _i: self.sync())

    def _can(self, it): return it is not None and bool(it.flags() & Qt.ItemIsUserCheckable) and not it.isHidden()

    def sync(self):
        """The highlight follows the ticks."""
        self.blockSignals(True)
        for i in range(self.count()):
            it = self.item(i); on = it.checkState() == Qt.Checked and bool(it.flags() & Qt.ItemIsUserCheckable)
            if it.isSelected() != on: it.setSelected(on)
        self.blockSignals(False)

    def mousePressEvent(self, e):
        it = self.itemAt(e.position().toPoint())
        if e.button() != Qt.LeftButton or not self._can(it): return super().mousePressEvent(e) if e.button() != Qt.LeftButton else None
        r = self.row(it)
        if (e.modifiers() & Qt.ShiftModifier) and self._anchor is not None:
            lo, hi = sorted((self._anchor, r)); self.blockSignals(True)
            for k in range(lo, hi + 1):
                if self._can(self.item(k)): self.item(k).setCheckState(Qt.Checked)
            self.blockSignals(False); self.itemChanged.emit(it)
        else:
            it.setCheckState(Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked); self._anchor = r
        self.setCurrentItem(it, __import__("PySide6.QtCore", fromlist=["QItemSelectionModel"]).QItemSelectionModel.NoUpdate); self.sync(); self.setFocus()

    def mouseReleaseEvent(self, e): self.sync()
    def mouseMoveEvent(self, e): pass
    def mouseDoubleClickEvent(self, e): self.mousePressEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_A and (e.modifiers() & Qt.ControlModifier):
            self.blockSignals(True)
            for k in range(self.count()):
                if self._can(self.item(k)): self.item(k).setCheckState(Qt.Checked)
            self.blockSignals(False); self.itemChanged.emit(self.item(0)) if self.count() else None; return
        super().keyPressEvent(e); self.sync()

    def selected_rows(self): return [i for i in range(self.count()) if self.item(i).checkState() == Qt.Checked and not self.item(i).isHidden()]


def multi_list(tooltip="", tick_on_click=True):
    """Every list of the page: click = tick / untick, Shift+click = a range, Ctrl+A = all shown; the ticked rows are highlighted.
    tick_on_click=False (the Columns list, whose rows are dragged): click selects, the tick box ticks."""
    w = TickList() if tick_on_click else QListWidget()
    if not tick_on_click: w.setSelectionMode(QAbstractItemView.ExtendedSelection)
    w.setToolTip(tooltip); w.setUniformItemSizes(False)
    w.setStyleSheet("QListWidget::item:selected { background: #EAF2FF; color: #172B4D; border: 1px solid #2563EB; border-radius: 6px; }")
    return w


def set_checked(lst, rows, on=True):
    lst.blockSignals(True)
    for i in rows: lst.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked) if lst.item(i).flags() & Qt.ItemIsUserCheckable else None
    lst.blockSignals(False); lst.itemChanged.emit(lst.item(0)) if lst.count() else None


def checked(lst):
    return [lst.item(i).data(Qt.UserRole) for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked and not lst.item(i).isHidden()]


class TemplatePage(QWidget):
    label = "Graphs and templates"

    def __init__(self, ws):
        super().__init__(); self.ws = ws
        import opstudio; from opstudio import api
        self.ops, self.api = opstudio, api
        try:
            import private_store
            api.add_user_dir(private_store.private_dir(make=False))
            self.my_dir = private_store.private_dir
            self.style0 = api.default_style(private_store.default("default_style"))
        except Exception:
            self.my_dir = lambda make=False: os.path.join(os.path.expanduser("~"), "OriginPlotStudio_my_templates"); self.style0 = api.default_style()
        self.tables = {}                     # path -> [Table]
        self._sheet_pick_cache = {}          # (path, template) -> the sheet that fits that template (a workbook with many sheets)
        self.extra_files = []                # files added on this page
        self.tiles = []; self.queue = []; self.switches = {}; self.params = {}; self.cancelled = False
        self.catalogue = self._catalogue()
        outer = QVBoxLayout(self); outer.setContentsMargins(8, 8, 8, 8); outer.setSpacing(6)
        outer.addLayout(self._action_bar())
        self.main = QMainWindow(); self.main.setObjectName("templatesMain"); self.main.setDockNestingEnabled(True)
        self.main.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks); outer.addWidget(self.main, 1)
        mk = ws._panel_dock
        self.files_dock = mk("Files", "templatesFilesDock", self._files_panel(), Qt.LeftDockWidgetArea, self.main)
        self.columns_dock = mk("Columns", "templatesColumnsDock", self._columns_panel(), Qt.LeftDockWidgetArea, self.main)
        self.templates_dock = mk("Templates", "templatesGalleryDock", self._templates_panel(), Qt.RightDockWidgetArea, self.main)
        self.styles_dock = mk("Styles", "templatesStylesDock", self._styles_panel(), Qt.RightDockWidgetArea, self.main)
        self.preview_dock = mk("Previews", "templatesPreviewDock", self._preview_panel(), Qt.RightDockWidgetArea, self.main)
        self.variants_dock = mk("Variants", "templatesVariantsDock", self._variants_panel(), Qt.RightDockWidgetArea, self.main)
        self.templates_dock.widget().setMinimumWidth(650)      # room for the classes and two to three pictures side by side
        self.files_dock.widget().setMinimumWidth(190); self.preview_dock.widget().setMinimumWidth(330)
        self.docks = [self.files_dock, self.columns_dock, self.templates_dock, self.styles_dock, self.preview_dock, self.variants_dock]
        self.gallery_dock = self.templates_dock
        self.main.splitDockWidget(self.files_dock, self.columns_dock, Qt.Vertical)
        self.main.splitDockWidget(self.templates_dock, self.preview_dock, Qt.Horizontal)
        self.main.splitDockWidget(self.templates_dock, self.styles_dock, Qt.Vertical)
        self.main.splitDockWidget(self.preview_dock, self.variants_dock, Qt.Vertical)
        self.main.resizeDocks([self.files_dock, self.templates_dock, self.preview_dock], [220, 760, 520], Qt.Horizontal)
        self.main.resizeDocks([self.templates_dock, self.styles_dock], [520, 190], Qt.Vertical); self.main.resizeDocks([self.preview_dock, self.variants_dock], [560, 150], Qt.Vertical)
        # Ctrl+Shift+O / Ctrl+Shift+E / Ctrl+Shift+G act on this page while it is on show (see workspace_session.install)
        self._timer = QTimer(self); self._timer.setSingleShot(True); self._timer.setInterval(350); self._timer.timeout.connect(self.rebuild_previews)
        self.fill_templates(); self.fill_styles(); self.refresh_files(); self.update_count()

    # ------------------------------------------------------------------------------------------------ the catalogue
    def _catalogue(self):
        """Every row of the catalogue of graph types joined with the installed templates: status available / coming."""
        api = self.api; rows = []; seen = set()
        try: cat = json.load(open(os.path.join(os.path.dirname(api.__file__), "catalogue_all_graph_types.json"), encoding="utf-8"))
        except Exception: cat = []
        info = {t["id"]: t for t in api.all_templates()}
        for r in cat:
            tid = r.get("template_id")
            if tid and tid in info:
                if tid in seen: continue
                seen.add(tid); t = info[tid]
                rows.append(dict(id=tid, name=t["name"], section=r["section"], use=t["use_case"], source=t.get("source", "generic"), available=True, roles=t["data_roles"], origin=t.get("origin_hint", ""),
                                 preview=t["preview"], kind=t["data_kind"], tier=r["status"], alias=r["name"]))
            else:
                rows.append(dict(id="coming:" + str(r.get("catalogue_id")), name=r["name"], section=r["section"], use=f"Roles: {r.get('data_roles', '')}", source="generic", available=False,
                                 roles={}, origin=r.get("origin_path", ""), preview=None, kind="", tier=r["status"], alias=""))
        by_letter = {r_["section"][:1]: r_["section"] for r_ in cat if r_["section"][1:2] == "."}
        try:                                             # the 26 workbook graph types: pictures in the class of their technique
            import gallery_graphs as TG; from workspace_tools import GALLERY_GROUPS
            here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gallery"); L = {"XRD": "I", "NMR": "J", "TGA": "N", "Calorimetry": "O", "Phases and composition": "P", "Particle size": "L", "General plots": "A"}; done = set()
            for g, codes in GALLERY_GROUPS:
                for c in codes:
                    if c in done or c not in TG.TYPES: continue
                    done.add(c); nm, what = TG.TYPES[c][0], TG.TYPES[c][1]
                    rows.append(dict(id="wb:" + c, name=f"{c}  {what}", section=by_letter.get(L.get(g, "A"), g), use=f"{what}. Drawn from a workbook in the layout of {c} ({nm}); + Add template makes that workbook from a raw file.",
                                     source="workbook", available=True, roles={"workbook": f"a workbook in the layout of {c} (its sheets: Data, Labels, Options …)"}, origin="the app's own Origin graphs of this type (Workspace: Draw in Origin)",
                                     preview=os.path.join(here, f"type_{c}.png"), kind="workbook", tier="implemented", alias=f"{c} {nm} workbook graph type"))
        except Exception: pass
        for tid, t in info.items():
            if tid not in seen:                          # a template without a row in the catalogue: classed by its own category
                rows.append(dict(id=tid, name=t["name"], section="My templates" if t.get("source") == "mine" else by_letter.get(CAT_LETTER.get(t.get("category", ""), ""), t.get("category", "Other")), use=t["use_case"], source=t.get("source", "generic"),
                                 available=True, roles=t["data_roles"], origin=t.get("origin_hint", ""), preview=t["preview"], kind=t.get("data_kind", ""), tier="implemented", alias=""))
        return rows

    # ------------------------------------------------------------------------------------------------ panels
    def _btn(self, text, tip, fn, name=None, key=None):
        b = QPushButton(text); b.setToolTip(tip + (f"  ({key})" if key else "")); b.setStatusTip(tip); b.clicked.connect(fn)
        if name: b.setObjectName(name)
        return b

    def _action_bar(self):
        h = QHBoxLayout(); h.setSpacing(6)
        self.count = QLabel("", objectName="soft"); self.count.setToolTip("What is ticked now, and how many previews that makes")
        h.addWidget(self.count); h.addStretch(1)
        self.live = QCheckBox("Preview with my data"); self.live.setChecked(True)
        self.live.setToolTip("On: every ticked combination is drawn from your ticked files as you tick. Off: nothing is drawn until you press Preview")
        self.live.toggled.connect(lambda on: self.schedule() if on else None); h.addWidget(self.live)
        self.b_recommend = self._btn("Use what the app recommends", "Not sure which template to use? Tick your data file(s) and press this: the app picks the best-fitting template for them (the same ranking as 'Works with the ticked files', ★) and draws it at once. You can keep it, or tick a different template yourself afterwards", self.use_recommended, "teal")
        h.addWidget(self.b_recommend)
        self.b_draw = self._btn("Draw my data like this", "Draw your ticked files in every ticked template and style. No file ticked yet: it asks for your data files first. No template ticked: click a template picture first", self.draw_my_data, "primary")
        h.addWidget(self.b_draw)
        self.b_open = self._btn("Open all in editor", "Open the kept graphs in the editor (or, with none ticked 'keep', every preview on show): variants, parameters, texts, style. Disabled: there is no preview yet", self.open_all)
        self.b_origin = self._btn("Draw all in Origin like this", "Send every kept graph to Origin as the same graph: same layout, panels, ranges, colours, fonts; your data in worksheets; each saved as {sample}_{template}.opju. The kept graphs, or every preview on show when none is ticked 'keep'. Disabled: there is no preview yet", self.draw_all_in_origin, "origin", "Ctrl+Shift+O")
        self.b_export = self._btn("Export all…", "Save every kept graph as PNG / TIFF / PDF / SVG / EPS at the journal size and dpi of its style. The kept graphs, or every preview on show when none is ticked 'keep'. Disabled: there is no preview yet", self.export_all, None, "Ctrl+Shift+E")
        self.b_combine = self._btn("Combine into one figure…", "Put the kept graphs - or, with fewer than two ticked 'keep', all previews on show - into one figure (1×2, 2×2, 2×3, stacked or your own grid) with panel labels (a), (b) …; it is shown at once, and can be sent to Origin or saved from there. Disabled: fewer than two previews are on show", self.combine, None, "Ctrl+Shift+G")
        more = QToolButton(); more.setText("More ▾"); more.setPopupMode(QToolButton.InstantPopup); more.setToolTip("Data of all to one Excel workbook, save as my template, import / export a template file, apply the style to all")
        m = QMenu(more)
        for text, tip, fn in (("Data and results of all → one Excel workbook…", "One sheet per file with its data, and a sheet that lists the kept graphs and the columns they use", self.export_workbook),
                              ("Apply the first ticked style to all kept graphs", "Every kept graph is redrawn in the first ticked style", self.apply_style_to_all),
                              ("Save as my template…", "Keep the graph on show (template + style + variants + parameters) as a template of your own, with a preview, in your private folder", self.save_my_template),
                              ("Export a template as one file (.opst)…", "One file with the JSON, the preview and the Origin script of one of your templates", self.export_opst),
                              ("Import a template file (.opst)…", "Add a template someone gave you to your private folder", self.import_opst),
                              ("Build Origin templates (.otpu) for the ticked templates…", "Needs Origin: draws each ticked template in Origin and stores it as an Origin graph template beside the template", self.build_otpu),
                              ("Change the Origin output folder…", "Draw in Origin like this / Draw all in Origin like this use this folder from now on without asking again; pick a different one here", self._pick_origin_folder)):
            a = QAction(text, m); a.setToolTip(tip); a.setStatusTip(tip); a.triggered.connect(fn); m.addAction(a)
        m.setToolTipsVisible(True); more.setMenu(m)
        self.b_workbook = self._btn("Edit data in Workbook", "Open the ticked files in the Workbook: edit cells, delete or hide columns, choose X and Y, merge. The previews here follow what you change there", self.to_workbook)
        for b in (self.b_open, self.b_origin, self.b_export, self.b_combine, self.b_workbook, more): h.addWidget(b)
        return h

    def to_workbook(self):
        """The ticked files of this page in the Workbook."""
        paths = [self.files.item(i).data(Qt.UserRole) for i in range(self.files.count()) if self.files.item(i).checkState() == Qt.Checked]
        ctrl = getattr(self.ws, "workbench", None)
        if ctrl is None: return None
        if not paths: self.ws.set_status("Tick the data files to edit first (the list on the left)."); return None
        ctrl.workbook.set_paths(paths); self.ws.go(7); return paths

    def _files_panel(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(8, 8, 8, 8)
        self.files = multi_list("Your files. Click a file to tick or untick it; Shift+click ticks a range; Ctrl+A ticks all. The ticked files are drawn. Drop files here to add them")
        self.files.itemChanged.connect(lambda _i: (self.update_count(), self.schedule(), self.filter_templates()))
        self.files.currentItemChanged.connect(lambda cur, _p: self.show_columns(cur.data(Qt.UserRole) if cur else None))
        self.files.setContextMenuPolicy(Qt.CustomContextMenu); self.files.customContextMenuRequested.connect(self._files_menu)
        self.files.setAcceptDrops(True); self.setAcceptDrops(True); v.addWidget(self.files, 1)
        v.addWidget(self._btn("Add files…", "Add data files to this page (Excel, CSV, text). They are only read, never changed", self.add_files, "primary"))
        h = QHBoxLayout()
        h.addWidget(self._btn("Tick selected", "Tick the highlighted files", lambda: self._tick_selected(self.files, True)))
        h.addWidget(self._btn("Clear", "Untick every file", lambda: set_checked(self.files, range(self.files.count()), False)))
        v.addLayout(h)
        h2 = QHBoxLayout(); self.together = QCheckBox("All ticked files in one graph"); self.together.setToolTip("On: the ticked files go into ONE graph per template (one curve or one panel per file). Off: one graph per file")
        self.together.toggled.connect(lambda _c: (self.update_count(), self.schedule())); h2.addWidget(self.together)
        h2.addWidget(self._btn("Remove", "Remove the highlighted files from this page (they stay on the disk and in Workspace)", self.remove_files)); v.addLayout(h2)
        return w

    def _columns_panel(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(8, 8, 8, 8)
        self.col_head = QLabel("Click a file to see its columns.", objectName="soft"); self.col_head.setWordWrap(True); v.addWidget(self.col_head)
        self.sheet = QComboBox(); self.sheet.setToolTip("The sheet of the workbook that is drawn"); self.sheet.currentIndexChanged.connect(self._sheet_changed); v.addWidget(self.sheet)
        self.cols = multi_list(tick_on_click=False, tooltip="The columns of the sheet, in the order they are used: the first ticked numeric column is x, the others are series. Untick a column to leave it out; "
                               "drag rows (or Move up / down) to change the order. The choice is remembered for files with the same headers")
        self.cols.setDragDropMode(QAbstractItemView.InternalMove); self.cols.itemChanged.connect(lambda _i: self._columns_changed())
        self.cols.model().rowsMoved.connect(lambda *a: self._columns_changed()); v.addWidget(self.cols, 1)
        h = QHBoxLayout()
        h.addWidget(self._btn("Set as x", "Make the highlighted column the x column (moves it to the top)", self._set_x))
        h.addWidget(self._btn("Tick", "Tick the highlighted columns", lambda: self._tick_selected(self.cols, True)))
        h.addWidget(self._btn("Untick", "Leave the highlighted columns out", lambda: self._tick_selected(self.cols, False)))
        v.addLayout(h); self._col_path = None
        return w

    def _templates_panel(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(8, 8, 8, 8)
        self.find = QLineEdit(placeholderText="Find a template: name, field, Origin name …  (Ctrl+F)"); self.find.setClearButtonEnabled(True); self.find.textChanged.connect(lambda _t: self.filter_templates()); v.addWidget(self.find)
        self.detect_label = QLabel("", objectName="illustr"); self.detect_label.setWordWrap(True); self.detect_label.setVisible(False)
        self.detect_label.setToolTip("What the app thinks your ticked file(s) are, from their columns and headers - the same guess 'Use what the app recommends' and the ★ marks use")
        v.addWidget(self.detect_label)
        f = QHBoxLayout()
        self.field = QComboBox(); self.field.setToolTip("Field: a graph family (basic 2D, bars, statistics …) or a domain pack (diffraction, thermal analysis, electrochemistry …)")
        self.source = QComboBox(); self.source.addItems(["All sources", "House figures", "Generic", "Workbook types", "My templates"]); self.source.setToolTip("Where the template comes from")
        self.state = QComboBox(); self.state.addItems(["Available", "Available and coming", "Coming"]); self.state.setToolTip("Available: can be drawn now. Coming: in the catalogue, not built yet")
        for c in (self.field, self.source, self.state): c.currentIndexChanged.connect(lambda _i: self.filter_templates()); f.addWidget(c)
        v.addLayout(f)
        f2 = QHBoxLayout(); self.fits = QCheckBox("Works with the ticked files"); self.fits.setToolTip("Show only the templates the ticked files can fill, best fit first (by columns, headers and units)")
        self.fits.toggled.connect(lambda _c: self.filter_templates()); f2.addWidget(self.fits); f2.addStretch(1)
        add = QToolButton(); add.setText("+ Add template ▾"); add.setObjectName("teal"); add.setPopupMode(QToolButton.InstantPopup)
        add.setToolTip("Add a template of your own to the gallery: from the graph you made here, from a template file someone gave you, or as a copy of a ticked template. It appears under 'My templates' and can be drawn like any other")
        am = QMenu(add); am.setToolTipsVisible(True)
        for text, tip, fn in (("From the graph I made here (kept preview)…", "Keep a preview you ticked - template, style, variants, parameters, your texts - as a template of your own", lambda: self.save_my_template()),
                              ("As a copy of the ticked template…", "A copy of the first ticked template under your own name, with the variants and parameters set now", lambda: self._copy_ticked()),
                              ("From a template file (.opst)…", "Add a template someone gave you", lambda: self.import_opst()),
                              ("Workbook for a workbook graph type (G01–G24, C01, C02)…", "Write a workbook in the layout of one of the 26 workbook graph types from a raw file of yours, then load it", lambda: self.ws.figtype_template_any()),
                              ("Open my template folder", "The folder on this computer where your own templates, styles and previews are kept", lambda: self._reveal(os.path.join(self.my_dir(True), "templates", "x")))):
            a_ = am.addAction(text, fn); a_.setToolTip(tip); a_.setStatusTip(tip)
        add.setMenu(am); self.add_btn = add; f2.addWidget(add)
        f2.addWidget(self._btn("Select all in this category", "Tick every template that is shown now", lambda: self._tick_shown(True)))
        f2.addWidget(self._btn("Clear selection", "Untick every template", lambda: set_checked(self.grid, range(self.grid.count()), False))); v.addLayout(f2)
        self.grid = multi_list("Click a template to tick it (click again to untick); Shift+click ticks a range; Ctrl+A ticks all that are shown. Every ticked template is drawn in Previews. Hover: what it is for, the columns it needs and its Origin name")
        self.grid.setViewMode(QListWidget.IconMode); self.grid.setIconSize(QSize(168, 110)); self.grid.setResizeMode(QListWidget.Adjust); self.grid.setMovement(QListWidget.Static)
        self.grid.setSpacing(6); self.grid.setWordWrap(True); self.grid.setGridSize(QSize(184, 170))
        self.grid.setStyleSheet("QListWidget::item { border: 1px solid #D8E1EC; border-radius: 8px; background: white; } QListWidget::item:selected { border: 3px solid #2563EB; background: #DCE9FF; color: #172B4D; font-weight: bold; }")
        self.grid.itemChanged.connect(lambda _i: (self._marks(), self.update_count(), self.schedule(), self._show_variants()))
        self.grid.setContextMenuPolicy(Qt.CustomContextMenu); self.grid.customContextMenuRequested.connect(self._grid_menu)
        # ---- the classes: by instrument / technique and by graph type (click one: the grid shows that class)
        from PySide6.QtWidgets import QSplitter
        self.classes = QTreeWidget(); self.classes.setHeaderHidden(True); self.classes.setMinimumWidth(215); self.classes.setIndentation(12); self.classes.setToolTip("The templates in classes: by instrument or technique, and by graph type. Click a class to see its templates; the numbers are 'can be drawn now' of 'in the catalogue'")
        self.classes.itemClicked.connect(self._class_clicked)
        sp_ = QSplitter(Qt.Horizontal); sp_.addWidget(self.classes); sp_.addWidget(self.grid); sp_.setStretchFactor(1, 1); sp_.setSizes([240, 560]); sp_.setCollapsible(0, False); self.field.hide()
        v.addWidget(sp_, 1)
        sc = QShortcut(QKeySequence("Ctrl+F"), w); sc.setContext(Qt.WidgetWithChildrenShortcut); sc.activated.connect(self.find.setFocus)
        return w

    def _styles_panel(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(8, 8, 8, 8)
        self.styles = multi_list("Click a style to tick it. Tick several to compare: house style, journal presets (sizes and minimum text sizes from the publishers' guides), slides, greyscale, colour-blind safe")
        self.styles.itemChanged.connect(lambda _i: (self.update_count(), self.schedule())); v.addWidget(self.styles, 1)
        return w

    def _preview_panel(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(8, 8, 8, 8)
        h = QHBoxLayout(); self.pmsg = QLabel("Tick files, templates and styles: every combination is drawn here from your data.", objectName="soft"); self.pmsg.setWordWrap(True); h.addWidget(self.pmsg, 1)
        self.bar = QProgressBar(); self.bar.setMaximumWidth(180); self.bar.hide(); h.addWidget(self.bar)
        self.b_stop = self._btn("Cancel", "Stop drawing the remaining previews", self.cancel); self.b_stop.hide(); h.addWidget(self.b_stop)
        h.addWidget(self._btn("Keep all", "Tick every preview that could be drawn", lambda: self._keep_all(True)))
        h.addWidget(self._btn("Keep none", "Untick every preview", lambda: self._keep_all(False))); v.addLayout(h)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.host = QWidget(); self.gridl = QGridLayout(self.host); self.gridl.setSpacing(8)
        self.gridl.setAlignment(Qt.AlignTop | Qt.AlignLeft); self.scroll.setWidget(self.host); v.addWidget(self.scroll, 1)
        return w

    def _variants_panel(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(8, 8, 8, 8)
        t = QLabel("Variants that work on every template. They change the drawing, never your file.", objectName="soft"); t.setWordWrap(True); v.addWidget(t)
        g = QGridLayout(); self.sw = {}; r = c = 0
        for key, (label, kind) in self.api.SWITCHES.items():
            if kind == "bool":
                b = QCheckBox(label); b.setTristate(key in ("markers", "grid")); b.setToolTip(label + (" (half-ticked = as the template draws it)" if b.isTristate() else ""))
                if b.isTristate(): b.setCheckState(Qt.PartiallyChecked)
                b.stateChanged.connect(lambda _s: self._switch_changed()); self.sw[key] = b; g.addWidget(b, r, c)
            elif kind == "float":
                b = QDoubleSpinBox(); b.setRange(0, 5); b.setSingleStep(0.1); b.setPrefix("offset "); b.setToolTip(label); b.valueChanged.connect(lambda _v: self._switch_changed()); self.sw[key] = b; g.addWidget(b, r, c)
            elif kind.startswith("choice"):
                b = QComboBox(); b.addItems(["top axis: " + x for x in kind.split(":")[1].split("|")]); b.setToolTip(label); b.currentIndexChanged.connect(lambda _i: self._switch_changed()); self.sw[key] = b; g.addWidget(b, r, c)
            else:
                b = QLineEdit(placeholderText=label); b.setMaximumWidth(110); b.setToolTip(label + " (empty = automatic)"); b.editingFinished.connect(self._switch_changed); self.sw[key] = b; g.addWidget(b, r, c)
            c += 1
            if c == 4: r += 1; c = 0
        v.addLayout(g)
        self.pform_head = QLabel("", objectName="soft"); v.addWidget(self.pform_head)
        self.pform = QFormLayout(); v.addLayout(self.pform); self.pwidgets = {}; v.addStretch(1)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(w); sc.setFrameShape(QFrame.NoFrame)
        return sc

    # ------------------------------------------------------------------------------------------------ filling the lists
    def fill_templates(self):
        self.catalogue = self._catalogue(); keep = set(checked(self.grid)) if hasattr(self, "grid") else set()
        self.grid.blockSignals(True); self.grid.clear(); sections = []
        order = {}
        for r in self.catalogue: order.setdefault(r["section"], len(order))
        dom_first = lambda r: (0 if not (r["section"][:1] in FAMILIES and r["section"][1:2] == ".") and r["section"] != "My templates" else 1, order[r["section"]], not r["available"])
        for r in sorted(self.catalogue, key=dom_first):                    # instruments first, then graph types; inside a class the drawable ones first
            it = QListWidgetItem(r["name"]); it.setData(Qt.UserRole, r["id"]); it.setData(Qt.UserRole + 1, r)
            if r["available"]:
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked if r["id"] in keep else Qt.Unchecked)
                if r["preview"] and os.path.isfile(r["preview"]): it.setIcon(QIcon(r["preview"]))
                badge = {"house": "from the house figures", "mine": "my template", "workbook": "workbook graph type (its own fixed look; styles do not apply)"}.get(r["source"], "generic")
                roles = "\n".join(f"   {k}: {v}" for k, v in (r["roles"] or {}).items())
                it.setToolTip(f"{r['name']}\n{r['use']}\n\n{badge}  ·  illustrative example (your graph is drawn from your data)\nColumns it needs:\n{roles}\n\nOrigin: {r['origin']}")
            else:
                it.setFlags(Qt.ItemIsEnabled); it.setForeground(QBrush(QColor("#8A97A8")))
                it.setToolTip(f"{r['name']}\nComing: this graph type is in the catalogue ({r['tier']}) and is not built yet.\n{r['use']}\nOrigin: {r['origin']}")
                it.setText(r["name"] + "\n(coming)")
            it.setSizeHint(QSize(178, 164)); self.grid.addItem(it)
            if r["section"] not in sections: sections.append(r["section"])
        self.grid.blockSignals(False)
        fam = [s for s in sections if s[:1] in FAMILIES and s[1:2] == "."]; dom = [s for s in sections if s not in fam and s != "My templates"]
        cur = self.field.currentData(); self.field.blockSignals(True); self.field.clear(); self.field.addItem(f"All fields  ({sum(1 for r in self.catalogue if r['available'])} available, {len(self.catalogue)} in the catalogue)", None)
        n = lambda s: sum(1 for r in self.catalogue if r["section"] == s and r["available"]); tot = lambda s: sum(1 for r in self.catalogue if r["section"] == s)
        self.field.addItem("— Graph families —", "__fam"); [self.field.addItem(f"    {_clean(s)}  ({n(s)} of {tot(s)})", s) for s in fam]
        self.field.addItem("— Domain packs —", "__dom"); [self.field.addItem(f"    {_clean(s)}  ({n(s)} of {tot(s)})", s) for s in dom]
        self.field.addItem(f"My templates  ({n('My templates')})", "My templates")
        i = self.field.findData(cur); self.field.setCurrentIndex(max(0, i)); self.field.blockSignals(False)
        self.classes.clear(); bold = lambda it: (it.setFont(0, (lambda f: (f.setBold(True), f)[1])(it.font(0))), it)[1]
        na = sum(1 for r in self.catalogue if r["available"]); top = bold(QTreeWidgetItem([f"All templates  ({na})"])); top.setData(0, Qt.UserRole, None); self.classes.addTopLevelItem(top)
        for title, key, secs in (("By instrument / technique", "__dom", dom), ("By graph type", "__fam", fam)):
            g = bold(QTreeWidgetItem([f"{title}  ({sum(n(x) for x in secs)})"])); g.setData(0, Qt.UserRole, key); self.classes.addTopLevelItem(g)
            for x in secs:
                c = QTreeWidgetItem([f"{_clean(x)}  ({n(x)})"]); c.setData(0, Qt.UserRole, x); c.setToolTip(0, f"{re.sub(r'^[A-Z][.] *', '', x)}: {n(x)} template(s) can be drawn now; {tot(x)} graph types of this class are in the catalogue"); g.addChild(c)
            g.setExpanded(True)
        nh = sum(1 for r in self.catalogue if r["source"] == "house")
        hs = bold(QTreeWidgetItem([f"House figures  ({nh})"])); hs.setData(0, Qt.UserRole, "__house"); hs.setToolTip(0, "The figure layouts of the house style: stacked XRD with zoom, fit with tick rows, TG-DTG panels, calorimetry, particle size … Click to see only these")
        hn = lambda s: sum(1 for r in self.catalogue if r["source"] == "house" and r["section"] == s)
        for x in sorted({r["section"] for r in self.catalogue if r["source"] == "house"}, key=lambda s: order.get(s, 999)):
            c = QTreeWidgetItem([f"{_clean(x)}  ({hn(x)})"]); c.setData(0, Qt.UserRole, x); c.setToolTip(0, f"House figures for {re.sub(r'^[A-Z][.] *', '', x)}: {hn(x)} template(s). Click to see only these"); hs.addChild(c)
        self.classes.insertTopLevelItem(1, hs)
        mine = bold(QTreeWidgetItem([f"My templates  ({n('My templates')})"])); mine.setData(0, Qt.UserRole, "My templates"); mine.setToolTip(0, "Templates you added with '+ Add template'"); self.classes.insertTopLevelItem(2, mine)
        self.filter_templates()

    def _class_clicked(self, it, _col=0):
        key = it.data(0, Qt.UserRole); in_house = it.parent() is not None and it.parent().data(0, Qt.UserRole) == "__house"
        if key == "__house" or in_house:                   # the house figure layouts: all of them, or - grouped like the main tree - just one instrument / technique
            self.source.blockSignals(True); self.source.setCurrentText("House figures"); self.source.blockSignals(False)
            self.field.blockSignals(True); self.field.setCurrentIndex(max(0, self.field.findData(key)) if in_house else 0); self.field.blockSignals(False); self.filter_templates(); return
        if self.source.currentText() == "House figures": self.source.blockSignals(True); self.source.setCurrentIndex(0); self.source.blockSignals(False)
        i = self.field.findData(key); self.field.setCurrentIndex(max(0, i)); self.filter_templates()

    def _marks(self):
        """A ticked thumbnail says so: a tick before its name (and the blue frame of the highlight)."""
        self.grid.blockSignals(True)
        for i in range(self.grid.count()):
            it = self.grid.item(i); r = it.data(Qt.UserRole + 1)
            if not r["available"]: continue
            base = it.text().replace("✓ ", "", 1); want = ("✓ " + base) if it.checkState() == Qt.Checked else base
            if it.text() != want: it.setText(want)
        self.grid.blockSignals(False); self.grid.sync()

    def fill_styles(self):
        self.styles.blockSignals(True); self.styles.clear()
        for sid, name, where in self.api.styles():
            it = QListWidgetItem(f"{name}" + ("  (yours)" if where == "yours" else "")); it.setData(Qt.UserRole, sid); it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if sid == self.style0 else Qt.Unchecked)
            try:
                st = self.ops.load_style(sid); wm = st["figure"]["width_mm"]; lim = st.get("limits") or {}
                it.setToolTip(f"{st.get('description', '')}\nWidths: " + " / ".join(f"{v:g}" for v in wm.values()) + " mm" + (f"\nMinimum text {lim.get('min_font_pt')} pt, lines {lim.get('min_line_pt')} pt" if lim else "") + f"\nPanel labels: {st.get('panel_label', {}).get('format', '(a)')}")
            except Exception: pass
            self.styles.addItem(it)
        self.styles.blockSignals(False); self.styles.sync()

    def refresh_files(self):
        """The files of the session (Workspace) and the files added here."""
        paths = []
        for it in getattr(self.ws, "singles", []):
            p = getattr(it, "path", None)
            if p and p not in paths and os.path.isfile(p): paths.append(p)
        for p in self.extra_files:
            if p not in paths and os.path.isfile(p): paths.append(p)
        have = {self.files.item(i).data(Qt.UserRole): self.files.item(i).checkState() for i in range(self.files.count())}
        if list(have) == paths: return
        self.files.blockSignals(True); self.files.clear()
        for p in paths:
            it = QListWidgetItem(os.path.basename(p)); it.setData(Qt.UserRole, p); it.setToolTip(p); it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            it.setCheckState(have.get(p, Qt.Checked if (not have and len(paths) <= 6) else Qt.Unchecked)); self.files.addItem(it)      # the first time: your files are ticked, so that a ticked template is drawn at once
        self.files.blockSignals(False); self.files.sync(); self.filter_templates(); self.schedule()   # filter_templates() also calls update_count() and recomputes the best-fit ★ marks / detected-file-kind message

    def tick_files(self, paths):
        """Tick these files in one step. Each tick used to re-rank every template against all ticked files - for ten
        files that is ten rankings, each reading more files, with the window stopped meanwhile; the result is the same
        after one ranking at the end."""
        paths = set(paths); todo = [self.files.item(i) for i in range(self.files.count()) if self.files.item(i).data(Qt.UserRole) in paths and self.files.item(i).checkState() != Qt.Checked]
        if not todo: return
        self.files.blockSignals(True)
        for it in todo: it.setCheckState(Qt.Checked)
        self.files.blockSignals(False); self.files.sync()
        self.update_count(); self.schedule(); self.filter_templates()

    def showEvent(self, e):
        super().showEvent(e); self.refresh_files()
        if not getattr(self, "_sized", False) and "page5" not in ((__import__("workspace_qt").load_cfg().get("panel_layout") or {}) if isinstance(__import__("workspace_qt").load_cfg().get("panel_layout"), dict) else {}):
            self._sized = True; W_ = max(900, self.width())      # the first time: files narrow, the gallery wide enough for the classes and three pictures, the previews the rest
            QTimer.singleShot(0, lambda: self.main.resizeDocks([self.files_dock, self.templates_dock, self.preview_dock], [int(W_ * 0.13), int(W_ * 0.47), int(W_ * 0.40)], Qt.Horizontal))

    # ------------------------------------------------------------------------------------------------ files and columns
    def add_files(self, paths=None, project=None, on_done=None):
        """on_done(items): called once the files are in Workspace (project= several projects, opened one after another: the
        next can only start once this is really done - Workspace reads one batch of files at a time)."""
        if not paths:
            paths, _ = QFileDialog.getOpenFileNames(self, "Add data files", self._cfg().get("last_dir", ""), "Data files (*.xlsx *.xlsm *.xls *.csv *.txt *.dat *.xy *.asc *.tsv);;All files (*.*)")
        new = [p for p in (paths or []) if os.path.isfile(p)]
        if not new:
            if on_done: on_done([])
            return
        self._save_cfg({"last_dir": os.path.dirname(new[0])})
        for p in new:
            if p not in self.extra_files: self.extra_files.append(p)
        self.refresh_files()
        self.tick_files(new)
        have_ws = {os.path.abspath(str(getattr(it, "path", "") or "")) for it in getattr(self.ws, "singles", [])}
        to_ws = [p for p in new if os.path.abspath(p) not in have_ws]
        if to_ws:
            self.ws.load(to_ws, project=project, on_done=on_done)    # a file you add here is also in Workspace's Your graphs - not kept to this page only
            return
        if project:                                                  # already in Workspace (e.g. added again under a project): tag what's there now
            for it in getattr(self.ws, "singles", []):
                if os.path.abspath(str(getattr(it, "path", "") or "")) in {os.path.abspath(p) for p in new}: it.project = project
        if on_done: on_done([])

    def remove_files(self):
        sel = [i.data(Qt.UserRole) for i in self.files.selectedItems()]
        if not sel: self.ws.set_status("Highlight the files to remove first."); return
        own = [p for p in sel if p in self.extra_files]
        if QMessageBox.question(self, "Remove files", f"Remove {len(own)} file(s) from this page? They stay on the disk." + ("" if len(own) == len(sel) else f"\n{len(sel) - len(own)} file(s) belong to Workspace and stay in the list.")) != QMessageBox.Yes: return
        self._removed = list(own); self.extra_files = [p for p in self.extra_files if p not in own]; self.refresh_files(); self.schedule()
        self.ws.set_status(f"{len(own)} ticked file(s) removed from this page. Add files… brings them back.")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        self.add_files([u.toLocalFile() for u in e.mimeData().urls()])

    def _tick_selected(self, lst, on):
        rows = [lst.row(i) for i in lst.selectedItems()] or ([lst.currentRow()] if lst.currentRow() >= 0 else [])
        if not rows: self.ws.set_status("Highlight rows first (click, Ctrl+click, Shift+click or Ctrl+A)."); return
        set_checked(lst, rows, on)

    def _tick_shown(self, on):
        set_checked(self.grid, [i for i in range(self.grid.count()) if not self.grid.item(i).isHidden()], on)

    def _files_menu(self, pos):
        m = QMenu(self); it = self.files.itemAt(pos)
        m.addAction("Tick the highlighted files", lambda: self._tick_selected(self.files, True)); m.addAction("Untick the highlighted files", lambda: self._tick_selected(self.files, False))
        m.addAction("Tick all", lambda: set_checked(self.files, range(self.files.count()), True)); m.addSeparator()
        if it:
            p = it.data(Qt.UserRole)
            m.addAction("Show columns", lambda: self.show_columns(p)); m.addAction("Templates that fit this file (best first)", lambda: self._fit_for(it))
            m.addAction("Reveal in folder", lambda: self._reveal(p))
        m.addAction("Add files…", self.add_files); m.addAction("Remove from this page", self.remove_files); m.exec(self.files.mapToGlobal(pos))

    def _fit_for(self, it):
        set_checked(self.files, range(self.files.count()), False); it.setCheckState(Qt.Checked); self.fits.setChecked(True); self.filter_templates()

    def _reveal(self, p):
        from PySide6.QtGui import QDesktopServices; from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(p)))

    def _cfg(self):
        import workspace_qt as WQ
        return WQ.load_cfg().get("templates_page") or {}

    def _save_cfg(self, changes):
        import workspace_qt as WQ
        c = self._cfg(); c.update(changes); WQ.save_cfg({"templates_page": c})

    def raw_tables(self, path):
        if path not in self.tables:
            try: self.tables[path] = self._read_all(path)
            except Exception as e: self.tables[path] = e
        t = self.tables[path]
        if isinstance(t, Exception): raise self.api.Unfit(f"this file could not be read as a table ({t})")
        return t

    def _read_all(self, path):
        import pandas as pd
        D = self.ops.data; low = path.lower(); name = os.path.splitext(os.path.basename(path))[0]
        if low.endswith((".xlsx", ".xlsm", ".xls")):
            import workbook_cache
            book = workbook_cache.sheets(path)
            out = {s: df for s, df in book.items() if df.shape[1] >= 1 and len(df)}
            if not out: raise ValueError("no sheet with data")
            return {"name": name, "sheets": out}
        tabs = D.read_tables(path)
        import smart_plots as sp_
        if len(tabs) > 1 and path in sp_.SIDE_BY_SIDE:            # files side by side (the Workbook's merge): one sheet per file
            return {"name": name, "sheets": {t.name: t.df for t in tabs}}
        return {"name": name, "sheets": {"": tabs[0].df}}

    def _pattern(self, cols): return "|".join(str(c) for c in cols)

    def _best_sheet(self, sheets_dict):
        """Which sheet to show first when there is no sheet called 'Data' and none remembered: the one that looks most like
        a plottable table (most numeric columns; ties broken by the most rows), not just the first one. A workbook with many
        sheets (a recipe workbook, a guide sheet first, lookup tables …) would otherwise open on a sheet with no numbers in it."""
        names = list(sheets_dict)
        if len(names) <= 1: return names[0]
        import smart_plots as sp_
        def score(nm):
            try:
                if sp_.side_by_side_columns(list(sheets_dict[nm].columns)): return (-1, 0)       # the overview of a merged workbook (all files side by side): its sheets per file are the ones to draw from
                t = self.ops.data.Table(nm, sheets_dict[nm])
            except Exception: return (-1, 0)
            return (len(t.numeric), len(t.df))
        return max(names, key=score)

    def table_of(self, path):
        """The Table of a file as the user mapped it: the chosen sheet, the ticked columns in the chosen order."""
        raw = self.raw_tables(path); m = self._cfg().get("mappings") or {}; sheets = list(raw["sheets"])
        pick = (self._cfg().get("sheets") or {}).get(os.path.basename(path))
        s = pick if pick in raw["sheets"] else (next((x for x in sheets if x.strip().lower() == "data"), None) or self._best_sheet(raw["sheets"]))
        df = raw["sheets"][s]; cols = [str(c) for c in df.columns]; mp = m.get(self._pattern(cols))
        df = df.copy(); df.columns = cols
        if mp:
            order = [c for c in mp.get("order", []) if c in cols and c not in mp.get("off", [])]
            if order: df = df[order + [c for c in cols if c not in order and c not in mp.get("off", [])]]
        return self.ops.data.Table(raw["name"], df), s, sheets, cols, (mp or {})

    def show_columns(self, path):
        self._col_path = path; self.cols.blockSignals(True); self.sheet.blockSignals(True); self.cols.clear(); self.sheet.clear()
        if not path: self.cols.blockSignals(False); self.sheet.blockSignals(False); return
        try: t, s, sheets, cols, mp = self.table_of(path)
        except Exception as e:
            self.col_head.setText(str(e)); self.cols.blockSignals(False); self.sheet.blockSignals(False); return
        self.sheet.addItems([x or "(the file)" for x in sheets]); self.sheet.setCurrentIndex(sheets.index(s)); self.sheet.setVisible(len(sheets) > 1)
        order = [c for c in mp.get("order", []) if c in cols] + [c for c in cols if c not in mp.get("order", [])]; off = set(mp.get("off", []))
        full = self.ops.data.Table("x", (self.ws.workbench.raw_sheets(path) if hasattr(self.ws, "workbench") else self.raw_tables(path)["sheets"])[s].copy())
        first_num = next((c for c in order if c in full.numeric and c not in off), None)
        for c in order:
            role = "x" if c == first_num else "error" if self.ops.data.ERR_RE.search(c) and c in full.numeric else "series" if c in full.numeric else "names"
            it = QListWidgetItem(f"{c}    [{role}]"); it.setData(Qt.UserRole, c); it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            it.setCheckState(Qt.Unchecked if c in off else Qt.Checked); it.setToolTip(f"{c}: used as {role}. Untick to leave it out; drag to change the order"); self.cols.addItem(it)
        self.col_head.setText(f"{os.path.basename(path)}: {len(order)} columns, {len(full.df)} rows. The first ticked numeric column is x."); self.cols.blockSignals(False); self.sheet.blockSignals(False)

    def _columns_changed(self):
        if not self._col_path: return
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl is not None:
            prefs = ctrl.mapping_for(self._col_path)
            prefs['order'] = [self.cols.item(i).data(Qt.UserRole) for i in range(self.cols.count())]
            prefs['off'] = [self.cols.item(i).data(Qt.UserRole) for i in range(self.cols.count()) if self.cols.item(i).checkState() != Qt.Checked]
            m = dict(self._cfg().get("mappings") or {}); m[self._pattern(ctrl._table(self._col_path, ctrl.project_for(self._col_path))[3])] = {"order": list(prefs['order']), "off": list(prefs['off'])}
            self._save_cfg({"mappings": m})                    # also remembered for other files with the same headers, as before
            ctrl.changed(self._col_path); self._sheet_pick_cache.clear()
            ctrl.refresh_source_graphs(self._col_path); self.show_columns(self._col_path); self.filter_templates(); self.schedule(); return
        order = [self.cols.item(i).data(Qt.UserRole) for i in range(self.cols.count())]; off = [self.cols.item(i).data(Qt.UserRole) for i in range(self.cols.count()) if self.cols.item(i).checkState() != Qt.Checked]
        raw = self.raw_tables(self._col_path); _t, s, _sh, cols, _mp = self.table_of(self._col_path)
        m = dict(self._cfg().get("mappings") or {}); m[self._pattern([str(c) for c in raw["sheets"][s].columns])] = {"order": order, "off": off}; self._save_cfg({"mappings": m})
        getattr(self, "_sheet_pick_cache", {}).clear(); self.show_columns(self._col_path); self.schedule()

    def _set_x(self):
        sel = self.cols.selectedItems()
        if not sel: self.ws.set_status("Highlight the column that is x first."); return
        r = self.cols.row(sel[0]); it = self.cols.takeItem(r); self.cols.insertItem(0, it); it.setCheckState(Qt.Checked); self._columns_changed()

    def _sheet_changed(self, i):
        if not self._col_path or i < 0: return
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl is not None:
            sheets = list(ctrl.raw_sheets(self._col_path))
            if i >= len(sheets): return
            ctrl.settings_for(self._col_path)['sheet'] = sheets[i]
            ctrl.changed(self._col_path); self._sheet_pick_cache.clear(); self.show_columns(self._col_path); self.filter_templates(); self.schedule(); return
        raw = self.raw_tables(self._col_path); sheets = list(raw["sheets"]); s = dict(self._cfg().get("sheets") or {}); s[os.path.basename(self._col_path)] = sheets[i]
        self._save_cfg({"sheets": s}); getattr(self, "_sheet_pick_cache", {}).clear(); self.show_columns(self._col_path); self.schedule()

    # ------------------------------------------------------------------------------------------------ filtering and counting
    def ticked_tables(self, first_only=False):
        """first_only: stop at the first ticked file that reads as a table (the ranking of the templates uses only that
        one unless 'all ticked files in one graph' is on) - not every ticked file is read just to rank."""
        out = []
        for p in checked(self.files):
            try: out.append((p, self.table_of(p)[0]))
            except Exception: pass
            if first_only and out: break
        return out

    def filter_templates(self):
        q = self.find.text().strip().lower(); sec = self.field.currentData(); src = self.source.currentText(); st = self.state.currentText(); rank = {}
        tabs = [t for _p, t in self.ticked_tables(first_only=not self.together.isChecked())]   # the best-fitting templates move to the top (★) as soon as a file is ticked,
        detected = ""                                              # even without "Works with the ticked files" - that box only hides the rest
        if tabs:
            ranked = self.api.recommend(tabs[:1] if not self.together.isChecked() else tabs)
            rank = {tid: (i, why) for i, (tid, _s, why) in enumerate(ranked)}
            mine = self.api.user_templates()
            for tid, u in mine.items():
                if u["base"] in rank: rank[tid] = rank[u["base"]]
            if ranked and ranked[0][2] != "the columns fit": detected = f"Looks like {ranked[0][2]}. "   # "a 2θ column: diffraction" -> "Looks like a 2θ column: diffraction."
        self.detect_label.setText(detected.strip()); self.detect_label.setVisible(bool(detected))
        shown = 0
        for i in range(self.grid.count()):
            it = self.grid.item(i); r = it.data(Qt.UserRole + 1)
            ok = (not q or q in (r["name"] + " " + r["use"] + " " + r["section"] + " " + r["origin"] + " " + r["id"] + " " + r["alias"]).lower())
            ok = ok and (sec is None or (sec == "__fam" and r["section"][:1] in FAMILIES and r["section"][1:2] == ".") or (sec == "__dom" and not (r["section"][:1] in FAMILIES and r["section"][1:2] == ".") and r["section"] != "My templates") or r["section"] == sec)
            ok = ok and (src == "All sources" or (src == "House figures" and r["source"] == "house") or (src == "Generic" and r["source"] == "generic") or (src == "Workbook types" and r["source"] == "workbook") or (src == "My templates" and r["source"] == "mine"))
            ok = ok and ((st == "Available" and r["available"]) or st == "Available and coming" or (st == "Coming" and not r["available"]))
            if self.fits.isChecked() and rank: ok = ok and r["id"] in rank
            it.setHidden(not ok); shown += ok
        if rank:                                # best fit first
            hidden = {id(self.grid.item(i)): self.grid.item(i).isHidden() for i in range(self.grid.count())}      # QListWidget.takeItem() forgets
            items = [self.grid.takeItem(0) for _ in range(self.grid.count())]; items.sort(key=lambda it: rank.get(it.data(Qt.UserRole), (9999, ""))[0])
            self.grid.blockSignals(True)
            for k, it in enumerate(items):
                self.grid.addItem(it); it.setHidden(hidden.get(id(it), False))   # an item's hidden state: it must be reapplied once taken out and back in
                tid = it.data(Qt.UserRole)
                tk = "✓ " if it.checkState() == Qt.Checked else ""
                if tid in rank and rank[tid][0] < 3 and not it.isHidden(): it.setText(tk + "★ " + it.data(Qt.UserRole + 1)["name"])
                elif it.data(Qt.UserRole + 1)["available"]: it.setText(tk + it.data(Qt.UserRole + 1)["name"])
            self.grid.blockSignals(False)
        self.ws.set_status(detected + f"{shown} graph types shown" + (" - best fit for your file first (★ = top 3)" if rank else "")) if self.isVisible() else None
        self.update_count()

    def combos(self):
        """Every ticked combination: files x templates x styles (or all files together x templates x styles)."""
        files = checked(self.files); tpls = [t for t in checked(self.grid) if not str(t).startswith("coming:")]; styles = checked(self.styles) or [self.style0]
        groups = [files] if (self.together.isChecked() and files) else [[f] for f in files]; out = []; names = {r["id"]: r["name"] for r in self.catalogue}
        if not files:                           # no file ticked yet: the illustrative example of every ticked template, so that a tick always shows something
            return [{"files": [], "template": t, "style": s, "sample": "example", "title": "Illustrative example (tick a file to see your data)", "caption": f"{names.get(t, t)}  ·  {s}", "demo": True} for t in tpls for s in (styles[:1] if str(t).startswith("wb:") else styles)]
        for g in groups:
            sample = os.path.splitext(os.path.basename(g[0]))[0] if len(g) == 1 else f"{len(g)} files"
            for t in tpls:
                if str(t).startswith("wb:"):               # a workbook graph type: one graph per workbook, in its own look
                    out += [{"files": [f], "template": t, "style": styles[0], "sample": os.path.splitext(os.path.basename(f))[0], "title": os.path.splitext(os.path.basename(f))[0], "caption": f"{names.get(t, t)}  ·  own look"} for f in (g if len(g) > 1 or not self.together.isChecked() else g)]
                    continue
                for s in styles:
                    out.append({"files": list(g), "template": t, "style": s, "sample": sample, "title": f"{sample}", "caption": f"{names.get(t, t)}  ·  {s}"})
        return out

    def kept(self): return [t for t in self.tiles if t.keep.isChecked() and t.fig is not None]

    def chosen(self, least=1):
        """The previews an action of the bar works on: the kept ones (ticked 'keep') when there are at least 'least' of
        them, else every preview on show. Nothing had to be ticked to see the previews, so nothing has to be ticked to
        use them - the buttons stayed grey, and seemed to do nothing, until previews were ticked one by one."""
        k = self.kept()
        return k if len(k) >= least else [t for t in self.tiles if t.fig is not None]

    def _nothing(self, what, least=1):
        """Say plainly why an action has nothing to work on."""
        msg = (f"{what} needs {'two or more previews' if least > 1 else 'a preview'}.\n\nTick your data files on the left and one or more templates in the gallery: "
               "the previews appear on the right. " + ("Two files in one template, or one file in two templates, give two previews." if least > 1 else ""))
        self.ws.set_status(msg.replace("\n\n", " "))
        if not getattr(self, "silent", False) and not os.environ.get("OPS_NO_OPEN"): QMessageBox.information(self, what, msg)

    def update_count(self):
        nf, nt, ns = len(checked(self.files)), len([t for t in checked(self.grid) if not str(t).startswith("coming:")]), len(checked(self.styles))
        n = (1 if self.together.isChecked() and nf else (nf or 1)) * nt * max(ns, 1); k = len(self.kept())
        self.count.setText(f"{nf} file{'s' * (nf != 1)} · {nt} template{'s' * (nt != 1)} · {ns} style{'s' * (ns != 1)} selected  →  {n} preview{'s' * (n != 1)}" + (f"  ·  {k} kept" if self.tiles else ""))
        why = "Disabled: no graph is kept (tick previews)"
        shown = len([t for t in self.tiles if t.fig is not None])
        for b in (self.b_open, self.b_origin, self.b_export): b.setEnabled(shown > 0)       # they work on the kept previews, or on all that are on show
        self.b_combine.setEnabled(shown > 1)

    # ------------------------------------------------------------------------------------------------ previews
    def schedule(self):
        if self.live.isChecked(): self._timer.start()

    def draw_my_data(self):
        """The ticked template pictures drawn from the user's data: asks for files when none is ticked."""
        try:
            return self._draw_my_data()
        except Exception as e:
            import traceback; traceback.print_exc()
            self.ws.set_status(f"'Draw my data like this' failed: {type(e).__name__}: {e}"); self.pmsg.setText(f"This did not work: {type(e).__name__}: {e}"); return None

    def _draw_my_data(self):
        if not [t for t in checked(self.grid) if not str(t).startswith("coming:")]:
            self.ws.set_status("Click a template picture first (it gets a tick and a blue frame), then press 'Draw my data like this'."); self.pmsg.setText("Click a template picture on the left first: it gets a ✓ and a blue frame."); return None
        if not checked(self.files):
            if self.files.count(): set_checked(self.files, range(self.files.count()), True)
            elif not getattr(self, "silent", False):
                self.ws.set_status("No files are loaded yet: choose your data files."); self.window().raise_() if self.window() else None; self.add_files(); self.window().raise_() if self.window() else None
            if not checked(self.files): self.ws.set_status("Add your data files first (Add files…): they are drawn in the ticked templates."); return None
        self._timer.stop(); self.rebuild_previews(); return len(self.tiles)

    def use_recommended(self):
        """'Prefer not to pick a template yourself': tick the best-fitting one for your ticked files and draw it at once."""
        try:
            return self._use_recommended()
        except Exception as e:
            import traceback; traceback.print_exc()
            self.ws.set_status(f"'Use what the app recommends' failed: {type(e).__name__}: {e}"); return None

    def _use_recommended(self):
        if not checked(self.files):
            if self.files.count(): set_checked(self.files, range(self.files.count()), True)
            else:
                self.ws.set_status("Add your data files first (Add files…): the app looks at their columns to recommend a template.")
                self.window().raise_() if self.window() else None; self.add_files(); self.window().raise_() if self.window() else None
            if not checked(self.files): return None
        tabs = [t for _p, t in self.ticked_tables()]
        if not tabs: self.ws.set_status("Your ticked file(s) could not be read as a table."); return None
        ranked = self.api.recommend(tabs[:1] if not self.together.isChecked() else tabs)
        if not ranked: self.ws.set_status("No template fits your ticked file(s) yet: browse the gallery and tick one yourself."); return None
        tid, _score, why = ranked[0]
        idx = next((i for i in range(self.grid.count()) if self.grid.item(i).data(Qt.UserRole) == tid), None)
        if idx is None: self.ws.set_status(f"The recommended template ('{tid}') is not in the gallery right now."); return None
        self.source.blockSignals(True); self.source.setCurrentIndex(0); self.source.blockSignals(False)           # "All sources": the pick is visible,
        self.field.blockSignals(True); self.field.setCurrentIndex(0); self.field.blockSignals(False)              # whatever class or source it is in
        set_checked(self.grid, range(self.grid.count()), False); set_checked(self.grid, [idx], True); self.filter_templates()
        name = self.grid.item(idx).data(Qt.UserRole + 1)["name"]
        self.ws.set_status(f"Picked for you: '{name}'  ·  {why}. Tick a different template yourself any time to use that instead.")
        self._timer.stop(); self.rebuild_previews(); return len(self.tiles)

    def cancel(self):
        self.cancelled = True; self.queue = []; self._done_drawing("Cancelled: the previews drawn so far are kept.")

    def rebuild_previews(self):
        combos = self.combos(); old = {(tuple(t.combo["files"]), t.combo["template"], t.combo["style"], t.sig): t for t in self.tiles}
        sig = json.dumps([self.current_switches(), self.params, self._cfg().get("mappings"), self._cfg().get("sheets")], sort_keys=True, default=str)
        while self.gridl.count():
            w = self.gridl.takeAt(0).widget()
            if w: w.setParent(None)
        self.tiles = []; self.queue = []; self.cancelled = False
        cols = max(1, (self.scroll.viewport().width() - 10) // (TILE_W + 24))
        for i, c in enumerate(combos):
            t = old.get((tuple(c["files"]), c["template"], c["style"], sig))
            if t is None:
                t = Tile(c); t.sig = sig; t.toggled.connect(self.update_count); t.opened.connect(self.enlarge); self.queue.append(t)
                t.setContextMenuPolicy(Qt.CustomContextMenu); t.customContextMenuRequested.connect(lambda pos, t=t: self._tile_menu(t, pos))
            self.tiles.append(t); self.gridl.addWidget(t, i // cols, i % cols)
        if len(combos) > 60 and self.queue:
            if QMessageBox.question(self, "Many previews", f"{len(combos)} previews will be drawn. This can take a few minutes; you can cancel at any time. Go on?") != QMessageBox.Yes:
                self.queue = []
        self.total = len(self.queue); self.update_count()
        if not combos: self.pmsg.setText("Click a template on the left to tick it: it is drawn here - from your ticked files, or as an example when no file is ticked."); return
        if self.queue:
            self.bar.setRange(0, self.total); self.bar.setValue(0); self.bar.show(); self.b_stop.show(); self.pmsg.setText(f"Drawing {self.total} preview(s) …"); QTimer.singleShot(0, self._draw_next)
        else: self._done_drawing()

    def tables_for(self, files, template=None):
        """The Table of each file. When a template is given, the sheet that best fits THIS template is used - not just
        the sheet with the most numeric columns overall, and not a sheet chosen (in the Columns panel) for a DIFFERENT
        template if it no longer fits this one. A workbook with many sheets (a recipe workbook, raw profiles, Bragg
        lists, a guide sheet …) then draws the right data for each template picture, without the user having to pick
        a sheet by hand every time they tick a different template."""
        out = []
        for p in files:
            if template is None or str(template).startswith("wb:") or str(template).startswith("coming:"):
                out.append(self.table_of(p)[0]); continue
            picked = (self._cfg().get("sheets") or {}).get(os.path.basename(p))
            if picked:                                              # a sheet was explicitly chosen for this file: honour it, but only if it
                t = self.table_of(p)[0]                              # actually fits the ticked template - a choice made for another template
                try:                                                 # (e.g. a guide sheet, or one meant for a different graph) must not silently
                    base, *_rest = self.api.resolve(template); self.ops.data.bundle(base, [t]); out.append(t); continue
                except Exception: pass                                # break every other template for this file
            out.append(self._table_for_template(p, template))
        return out

    def _table_for_template_wb(self, ctrl, path, template):
        """The same choice with the project workbench: among the working sheets of the file (your edits and each
        sheet's own column mapping included), the one this template can draw. A sheet you chose yourself is kept
        when it fits the template."""
        slug = ctrl.project_for(path); key = (slug, path, template); cache = getattr(self, "_sheet_pick_cache", None)
        if cache is None: cache = self._sheet_pick_cache = {}
        if key in cache: return cache[key]
        default_t = self.table_of(path)[0]; names = list(ctrl.raw_sheets(path, slug))
        if len(names) <= 1: cache[key] = default_t; return default_t
        try: base, *_rest = self.api.resolve(template)
        except Exception: cache[key] = default_t; return default_t
        def fits(t):
            try: self.ops.data.bundle(base, [t]); return True
            except Exception: return False
        if ctrl.settings_for(path, slug).get("sheet") and fits(default_t): cache[key] = default_t; return default_t
        tid_l = str(template).lower(); best = None; best_score = None
        for s in names:
            try: t = ctrl._table(path, slug, s)[0]
            except Exception: continue
            head = " | ".join(t.cols).lower()
            matches = any(re.search(pat, head) and any(k in tid_l for k in keys) for pat, keys, _ in self.api.RULES)
            score = (fits(t), matches, len(t.numeric), len(t.df))
            if best is None or score > best_score: best, best_score = t, score
        picked = best if (best is not None and best_score[0]) else default_t
        cache[key] = picked; return picked

    def _table_for_template(self, path, template):
        """Among the sheets of `path`, the Table that this template can actually draw - cached per (file, template)."""
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl is not None: return self._table_for_template_wb(ctrl, path, template)
        key = (path, template); cache = getattr(self, "_sheet_pick_cache", None)
        if cache is None: cache = self._sheet_pick_cache = {}
        if key in cache: return cache[key]
        default_t, s_default, sheets, cols, mp = self.table_of(path)
        if len(sheets) <= 1: cache[key] = default_t; return default_t
        try: base, *_rest = self.api.resolve(template)
        except Exception: cache[key] = default_t; return default_t
        tid_l = str(template).lower()
        best = None; best_score = None
        raw = self.raw_tables(path); m = self._cfg().get("mappings") or {}
        for s in sheets:
            try:
                df = raw["sheets"][s]; c = [str(x) for x in df.columns]; mp_s = m.get(self._pattern(c))
                d2 = df.copy(); d2.columns = c
                if mp_s:
                    order = [x for x in mp_s.get("order", []) if x in c and x not in mp_s.get("off", [])]
                    if order: d2 = d2[order + [x for x in c if x not in order and x not in mp_s.get("off", [])]]
                t = self.ops.data.Table(raw["name"], d2)
            except Exception: continue
            try: self.ops.data.bundle(base, [t]); fits = True
            except self.ops.data.NeedData: fits = False
            except Exception: fits = False
            head = " | ".join(t.cols).lower()                           # among sheets that fit, prefer one whose headers
            matches = any(re.search(pat, head) and any(k in tid_l for k in keys) for pat, keys, _ in self.api.RULES)  # actually match the template's domain
            score = (fits, matches, len(t.numeric), len(t.df))
            if best is None or score > best_score: best, best_score = t, score
        picked = best if (best is not None and best_score[0]) else default_t
        cache[key] = picked; return picked

    def draw_workbook_type(self, combo):
        """A workbook graph type (G01-G24, C01, C02) drawn from a ticked workbook by the app's own drawing of that type."""
        import gallery_graphs as TG
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib import image as mimg
        code = combo["template"][3:]; fig = Figure(figsize=(TG.FIG_W, TG.FIG_H), dpi=100); FigureCanvasAgg(fig)
        if combo.get("demo"):
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gallery", f"type_{code}.png"); ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
            if os.path.isfile(p): ax.imshow(mimg.imread(p)); ax.set_aspect("auto")
            return fig, [("data", "illustrative example - tick a workbook in the layout of this type")]
        path = combo["files"][0]
        try: TG.draw(code, TG.read_book(path), fig)
        except TG.NeedInput as e: raise self.api.Unfit(f"{code} needs an answer first: {e} (open the workbook's Options sheet, or use Workspace)")
        except Exception as e: raise self.api.Unfit(f"this file is not a workbook in the layout of {code}: {str(e)[:150]}. '+ Add template' > 'Workbook for a workbook graph type' writes one from a raw file.")
        fig.canvas.draw(); return fig, [("workbook", os.path.basename(path)), ("graph type", f"{code} {TG.TYPES[code][0]}")]

    def draw_combo(self, combo, width=None, target=None):
        if str(combo["template"]).startswith("wb:"):
            if target is not None: raise self.api.Unfit("a workbook graph type cannot be a panel of a combined figure (it is a whole page of its own)")
            return self.draw_workbook_type(combo)
        if combo.get("demo"):
            fig = self.api.demo_figure(combo["template"], combo["style"]); return fig, [("data", "illustrative example - tick a file to draw your own data")]
        return self.api.draw(combo["template"], self.tables_for(combo["files"], combo["template"]), style=combo["style"], params=combo.get("params", self.params.get(combo["template"]) or None),
                             switches=combo.get("switches", self.current_switches()), overrides=combo.get("overrides"), width=width, target=target)

    def _draw_next(self):
        if not self.queue or self.cancelled: return self._done_drawing() if not self.cancelled else None
        t = self.queue.pop(0)
        try:
            fig, mp = self.draw_combo(t.combo); t.show_figure(fig, self.api.png(fig, TILE_W * 2), mp)
            if t.combo.get("demo"): t.keep.setEnabled(False); t.keep.setToolTip("An example cannot be kept: tick one of your files and it is drawn from your data")
        except self.api.Unfit as e: t.show_error(str(e))
        except Exception as e: t.show_error(f"could not be drawn: {type(e).__name__}: {e}")
        self.bar.setValue(self.total - len(self.queue)); QTimer.singleShot(0, self._draw_next)

    def _done_drawing(self, msg=None):
        self.bar.hide(); self.b_stop.hide(); ok = sum(1 for t in self.tiles if t.fig is not None); bad = sum(1 for t in self.tiles if t.error)
        self.pmsg.setText(msg or (f"{ok} preview(s) drawn from your data" + (f"; {bad} could not be drawn (the tile says what is missing)" if bad else "") + ". Double click a tile to enlarge it; tick the ones to keep."))
        self.update_count()

    def _keep_all(self, on):
        for t in self.tiles:
            if t.fig is not None: t.keep.setChecked(on)
        self.update_count()

    def _tile_menu(self, t, pos):
        m = QMenu(self)
        if t.fig is not None:
            m.addAction("Enlarge / edit", lambda: self.enlarge(t)); m.addAction("Keep" if not t.keep.isChecked() else "Do not keep", t.keep.toggle)
            m.addAction("Draw in Origin like this  (Ctrl+Shift+O)", lambda: self.draw_all_in_origin([t])); m.addAction("Export this graph…", lambda: self.export_all([t]))
            m.addAction("Copy the picture", lambda: self._copy(t)); m.addAction("Save as my template…", lambda: self.save_my_template(t))
        m.addAction("Remove this preview", lambda: self._remove_tile(t)); m.exec(t.mapToGlobal(pos))

    def _grid_menu(self, pos):
        it = self.grid.itemAt(pos); m = QMenu(self)
        if it and (it.flags() & Qt.ItemIsUserCheckable):
            m.addAction("Preview with the ticked files", lambda: (it.setCheckState(Qt.Checked), self.rebuild_previews())); m.addAction("Add to selection" if it.checkState() != Qt.Checked else "Remove from selection", lambda: it.setCheckState(Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked))
            m.addAction("Details", lambda: QMessageBox.information(self, it.data(Qt.UserRole + 1)["name"], it.toolTip()))
            m.addAction("Duplicate as my template…", lambda: self.save_my_template(None, base=it.data(Qt.UserRole)))
        if it and (it.flags() & Qt.ItemIsUserCheckable): m.addAction("Draw my data like this (only this template)", lambda: (set_checked(self.grid, range(self.grid.count()), False), it.setCheckState(Qt.Checked), self.draw_my_data()))
        m.addAction("Tick the highlighted templates", lambda: self._tick_selected(self.grid, True)); m.addAction("Select all in this category", lambda: self._tick_shown(True)); m.addAction("Clear selection", lambda: set_checked(self.grid, range(self.grid.count()), False))
        m.exec(self.grid.mapToGlobal(pos))

    def _remove_tile(self, t):
        self.tiles.remove(t); t.setParent(None); self.update_count()

    def _copy(self, t):
        pm = QPixmap(); pm.loadFromData(self.api.png(t.fig, 1800)); QApplication.clipboard().setPixmap(pm); self.ws.set_status("The picture is on the clipboard (paste it into Word or PowerPoint).")

    # ------------------------------------------------------------------------------------------------ variants
    def current_switches(self):
        sw = {}
        for key, w in self.sw.items():
            kind = self.api.SWITCHES[key][1]
            if kind == "bool":
                if w.isTristate():
                    if w.checkState() != Qt.PartiallyChecked: sw[key] = w.checkState() == Qt.Checked
                elif w.isChecked(): sw[key] = True
            elif kind == "float":
                if w.value() > 0: sw[key] = w.value()
            elif kind.startswith("choice"):
                v = w.currentText().split(": ", 1)[1]
                if v != "none": sw[key] = v
            else:
                try: sw[key] = float(w.text().replace(",", "."))
                except ValueError: pass
        return sw

    def _switch_changed(self): self.schedule()

    def _show_variants(self):
        """The parameters of the first ticked template (they apply to every graph of that template)."""
        tids = [t for t in checked(self.grid) if not str(t).startswith("coming:")]
        while self.pform.rowCount(): self.pform.removeRow(0)
        self.pwidgets = {}
        if not tids: self.pform_head.setText(""); return
        tid = tids[0]
        try: base, p0, _s, _st, _o = self.api.resolve(tid)
        except Exception: return
        cur = dict(base.params); cur.update(p0); cur.update(self.params.get(tid) or {})
        if not cur: self.pform_head.setText(f"{base.name}: no parameters of its own."); return
        self.pform_head.setText(f"Parameters of '{base.name}' (for every graph of this template):")
        for k, v in cur.items():
            if isinstance(v, bool):
                w = QCheckBox(); w.setChecked(v); w.toggled.connect(lambda on, k=k, tid=tid: self._param(tid, k, on))
            elif isinstance(v, (int, float)):
                w = QLineEdit(f"{v:g}"); w.setMaximumWidth(120); w.editingFinished.connect(lambda k=k, tid=tid, w=w, typ=type(v): self._param(tid, k, w.text(), typ))
            elif isinstance(v, (list, tuple)) and all(isinstance(x, (int, float)) for x in v):
                w = QLineEdit(", ".join(f"{x:g}" for x in v)); w.setMaximumWidth(160); w.setToolTip("numbers separated by commas"); w.editingFinished.connect(lambda k=k, tid=tid, w=w: self._param(tid, k, w.text(), list))
            elif isinstance(v, str):
                w = QLineEdit(v); w.editingFinished.connect(lambda k=k, tid=tid, w=w: self._param(tid, k, w.text(), str))
            else: continue
            self.pform.addRow(k.replace("_", " "), w); self.pwidgets[k] = w

    def _param(self, tid, k, v, typ=None):
        try:
            if typ in (int, float): v = typ(float(str(v).replace(",", ".")))
            elif typ is list: v = [float(x) for x in re.split(r"[;,\s]+", str(v).strip()) if x]
        except ValueError:
            self.ws.set_status(f"'{v}' is not a number: the parameter keeps its value."); return
        self.params.setdefault(tid, {})[k] = v; self.schedule()

    # ------------------------------------------------------------------------------------------------ enlarge / edit
    def enlarge(self, tile):
        Editor(self, [tile]).exec(); self.update_count()

    def open_all(self):
        k = self.chosen()
        if not k: return self._nothing("Open all in editor")
        Editor(self, k).exec(); self.update_count()

    def redraw_tile(self, t):
        try:
            fig, mp = self.draw_combo(t.combo); t.show_figure(fig, self.api.png(fig, TILE_W * 2), mp); t.keep.setEnabled(True)
        except self.api.Unfit as e: t.show_error(str(e))

    def apply_style_to_all(self):
        st = checked(self.styles); k = self.kept()
        if not st or not k: self.ws.set_status("Tick a style and keep at least one preview first."); return
        for t in k:
            t.combo["style"] = st[0]; t.combo["caption"] = re.sub(r"·\s*\S+$", "· " + st[0], t.combo["caption"]); t.cap.setText(t.combo["caption"]); self.redraw_tile(t)
        self.ws.set_status(f"{len(k)} graph(s) redrawn in the style '{st[0]}'.")

    # ------------------------------------------------------------------------------------------------ batch: Origin, export, workbook, combine
    def out_folder(self, sub):
        try: base = self.ws.outdir.text().strip()
        except Exception: base = ""
        base = base or self._cfg().get("out_dir") or os.path.join(os.path.expanduser("~"), "Documents", "Origin plot results")
        return os.path.join(base, sub) if sub else base

    def _progress(self, title, n):
        from PySide6.QtWidgets import QProgressDialog
        d = QProgressDialog(title, "Cancel", 0, n, self); d.setWindowModality(Qt.WindowModal); d.setMinimumDuration(0); d.setValue(0); return d

    def make_driver(self, folder):
        import origin_plot_app as opa
        log = getattr(self.ws, "log", lambda m: None)
        if getattr(self, "force_dry", False): return opa.Driver(folder, log, dry=True)
        try: return opa.Driver(folder, log, dry=False)
        except Exception as e:
            self.no_origin = str(e); return opa.Driver(folder, log, dry=True)

    def _pick_origin_folder(self, folder=None):
        """Ask where {sample}_{template}.opju goes, and remember it: Draw in Origin then goes straight to Origin
        without asking again, until you come back here (More ▾ > Change the Origin output folder…) to change it."""
        folder = folder or self._cfg().get("origin_dir") or self.out_folder("Origin")
        folder = QFileDialog.getExistingDirectory(self, "Folder for the Origin projects ({sample}_{template}.opju)", folder if os.path.isdir(folder) else os.path.dirname(folder))
        if folder: self._save_cfg({"origin_dir": folder})
        return folder

    def draw_all_in_origin(self, tiles=None, ask_folder=False):
        from opstudio import origin as O
        tiles = tiles or self.chosen()
        if not tiles: self._nothing("Draw all in Origin like this"); return []
        remembered = self._cfg().get("origin_dir")
        folder = remembered or self.out_folder("Origin")
        if not getattr(self, "silent", False) and (ask_folder or not remembered or not os.path.isdir(remembered)):
            # asked once, the first time (or when you choose "Change the Origin output folder…"): after that, Draw in
            # Origin goes straight to Origin with the folder you already picked, instead of asking again every time
            folder = self._pick_origin_folder(folder)
            if not folder: return []
        self.no_origin = ""; out = []; dlg = self._progress(f"Drawing {len(tiles)} graph(s) in Origin …", len(tiles)) if not getattr(self, "silent", False) else None
        for i, t in enumerate(tiles):
            if dlg and dlg.wasCanceled(): break
            st = self.ops.load_style(t.combo["style"]); wmm = st["figure"]["width_mm"].get(st["figure"].get("default_width", "double"), 190)
            try:
                r = O.draw_in_origin(self.make_driver, t.fig, t.combo["sample"], t.combo["template"] + ("" if len(checked(self.styles)) < 2 else "_" + t.combo["style"]), folder, keep_open=True,
                                     export_dpi=st.get("export", {}).get("raster_dpi", 600), width_mm=wmm)
                out.append(r)
            except Exception as e:
                out.append({"project": "", "differences": [f"not drawn: {e}"], "commands": []})
            if dlg: dlg.setValue(i + 1); QApplication.processEvents()
        if dlg: dlg.close()
        self.last_origin = out; done = [r for r in out if r["project"]]; diffs = []
        for r in done:
            for x in r["differences"]:
                if x not in diffs: diffs.append(x)
        msg = (f"{len(done)} Origin graph(s) made in {folder}: " + ", ".join(os.path.basename(r["project"]) for r in done[:6]) + (" …" if len(done) > 6 else ""))
        if self.no_origin: msg = (f"Origin could not be started ({self.no_origin}). The worksheets (CSV) and the Origin script (.ogs) of {len(done)} graph(s) were written to {folder}; run them on a computer with Origin.")
        if diffs: msg += "\nDifferent in Origin:\n  - " + "\n  - ".join(diffs)
        self.ws.set_status(msg.split("\n")[0])
        try: self.ws.log(msg)
        except Exception: pass
        if not getattr(self, "silent", False): QMessageBox.information(self, "Draw in Origin like this", msg)
        return out

    def export_all(self, tiles=None):
        tiles = tiles or self.chosen()
        if not tiles: self._nothing("Export all"); return []
        opt = getattr(self, "export_options", None)
        if opt is None:
            d = ExportDialog(self, tiles)
            if d.exec() != QDialog.Accepted: return []
            opt = d.options(); self._save_cfg({"export": {k: v for k, v in opt.items()}})
        os.makedirs(opt["folder"], exist_ok=True); written = []; warns = []
        dlg = self._progress(f"Exporting {len(tiles)} graph(s) …", len(tiles)) if not getattr(self, "silent", False) else None
        for i, t in enumerate(tiles):
            if dlg and dlg.wasCanceled(): break
            name = opt["pattern"].format(sample=_safe(t.combo["sample"]), template=t.combo["template"], style=t.combo["style"], date=time.strftime("%Y-%m-%d"), n=i + 1)
            for ext in opt["formats"]:
                p = os.path.join(opt["folder"], f"{name}.{ext}")
                try:
                    w = self.api.export(t.fig, p, opt["width"], dpi=opt["dpi"], transparent=opt["transparent"]); written.append(p)
                    for x in w:
                        if x not in warns: warns.append(x)
                except Exception as e: warns.append(f"{os.path.basename(p)} not written: {e}")
            if dlg: dlg.setValue(i + 1); QApplication.processEvents()
        if dlg: dlg.close()
        msg = f"{len(written)} file(s) written to {opt['folder']}" + (("\nCheck before submission:\n  - " + "\n  - ".join(warns)) if warns else "")
        self.ws.set_status(msg.split("\n")[0]); self.last_export = written
        if not getattr(self, "silent", False): QMessageBox.information(self, "Export all", msg)
        return written

    def export_workbook(self, path=None, tiles=None):
        """Data of every file of the kept graphs (one sheet per file) + a sheet that lists the graphs and the columns they use."""
        import pandas as pd
        tiles = tiles or self.kept() or [t for t in self.tiles if t.fig is not None]
        files = []
        for t in tiles:
            for p in t.combo["files"]:
                if p not in files: files.append(p)
        if not files: files = checked(self.files)
        if not files: self.ws.set_status("Tick files (or keep previews) first."); return None
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Data and results of all in one workbook", os.path.join(self.out_folder(""), "all_data.xlsx"), "Excel workbook (*.xlsx)")
            if not path: return None
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True); used = set()
        with pd.ExcelWriter(path, engine="openpyxl") as xw:
            rows = [{"graph": i + 1, "file(s)": "; ".join(os.path.basename(p) for p in t.combo["files"]), "template": t.combo["template"], "style": t.combo["style"],
                     "columns used": "; ".join(f"{a} = {b}" for a, b in t.mapping), "variants": json.dumps(t.combo.get("switches", self.current_switches()))} for i, t in enumerate(tiles)]
            pd.DataFrame(rows or [{"note": "no graph kept: the sheets hold the data of the ticked files"}]).to_excel(xw, sheet_name="Graphs", index=False)
            for p in files:
                tb = self.table_of(p)[0]; nm = re.sub(r"[\[\]:*?/\\]", "_", tb.name)[:31] or "data"; k = 2
                while nm.lower() in used: nm = nm[:28] + f"_{k}"; k += 1
                used.add(nm.lower()); tb.df.to_excel(xw, sheet_name=nm, index=False)
        self.ws.set_status(f"Workbook written: {path} (one sheet per file, {len(files)} file(s), and the sheet 'Graphs')."); return path

    def combine(self, layout=None, tiles=None):
        tiles = tiles or self.chosen(2)
        if len(tiles) < 2: self._nothing("Combine into one figure", 2); return None
        if layout is None:
            d = CombineDialog(self, len(tiles))
            if d.exec() != QDialog.Accepted: return None
            layout = d.layout_()
        rows, cols, share = layout
        try:
            fns = [(lambda cell, c=t.combo: self.draw_combo(c, target=cell)) for t in tiles]
            fig = self.api.combine(fns, rows, cols, tiles[0].combo["style"], share_x=share)
        except Exception as e:
            QMessageBox.warning(self, "Combine", f"The figure could not be combined: {e}") if not getattr(self, "silent", False) else None; return None
        fig._ops_combo = {"sample": "combined", "template": f"{rows}x{cols}", "style": tiles[0].combo["style"]}
        self.last_combined = fig
        if not getattr(self, "silent", False): CombinedView(self, fig).exec()
        return fig

    # ------------------------------------------------------------------------------------------------ my templates
    def save_my_template(self, tile=None, base=None):
        tile = tile or (self.kept() or [None])[0]
        if tile is None and base is None: self.ws.set_status("Keep a preview first: it becomes your template (or right-click a template: Duplicate as my template)."); return None
        base = base or tile.combo["template"]; style = tile.combo["style"] if tile else (checked(self.styles) or [self.style0])[0]
        if str(base).startswith("wb:"): self.ws.set_status("A workbook graph type has its own fixed layout: it cannot be saved as a template of yours. Use a template picture instead."); return None
        name = getattr(self, "next_name", None)
        if name is None:
            name, ok = QInputDialog.getText(self, "Save as my template", "Name of your template:", text=f"My {self.api.info(base)['name']}"[:60])
            if not ok or not name.strip(): return None
        folder = self.my_dir(True)
        png = self.api.png(tile.fig, 760) if tile and tile.fig is not None else self.api.png(self.api.demo_figure(base, style), 760)
        p = self.api.save_user_template(folder, name, name.strip(), base, style=style, params=self.params.get(base), switches=tile.combo.get("switches", self.current_switches()) if tile else self.current_switches(),
                                        overrides=(tile.combo.get("overrides") if tile else None), preview_png=png)
        tid = os.path.splitext(os.path.basename(p))[0]
        if tile and tile.fig is not None:                       # its Origin script, and - with Origin - its .otpu
            try:
                from opstudio import origin as O; import origin_plot_app as opa, tempfile
                od = os.path.join(folder, "origin"); os.makedirs(od, exist_ok=True)
                r = O.draw_in_origin(lambda f: opa.Driver(f, lambda m: None, dry=True), tile.fig, "demo", tid, tempfile.mkdtemp())
                O.write_ogs(r["commands"], os.path.join(od, tid + ".ogs"), f"My template {tid}")
            except Exception: pass
        self.fill_templates(); self.ws.set_status(f"Template '{name}' saved in your private folder ({folder}). It is under 'My templates': click it to draw your data like it."); return tid

    def _copy_ticked(self):
        t = [x for x in checked(self.grid) if not str(x).startswith("coming:")]
        if not t: self.ws.set_status("Click a template picture first; it becomes the base of your own template."); return None
        tid = self.save_my_template(None, base=t[0])
        if tid: i = self.field.findData("My templates"); self.field.setCurrentIndex(max(0, i))
        return tid

    def export_opst(self):
        mine = self.api.user_templates()
        if not mine: self.ws.set_status("You have no template of your own yet (More ▾ > Save as my template)."); return
        tid, ok = QInputDialog.getItem(self, "Export a template", "Template:", sorted(mine), 0, False)
        if not ok: return
        path, _ = QFileDialog.getSaveFileName(self, "Template file", tid + ".opst", "Origin Plot Studio template (*.opst)")
        if path: self.api.export_opst(mine[tid]["_dir"], tid, path); self.ws.set_status(f"Template written: {path}")

    def import_opst(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Template file", "", "Origin Plot Studio template (*.opst)")
            if not path: return None
        try: tid = self.api.import_opst(path, self.my_dir(True))
        except Exception as e:
            self.ws.set_status(f"This template file could not be read: {e}"); return None
        self.fill_templates(); self.ws.set_status(f"Template '{tid}' added to My templates."); return tid

    def build_otpu(self):
        """With Origin: draw each ticked template from its illustrative data and store the graph as an Origin template (.otpu)."""
        from opstudio import origin as O
        tids = [t for t in checked(self.grid) if not str(t).startswith("coming:")]
        if not tids: self.ws.set_status("Tick the templates first."); return
        folder = os.path.join(self.my_dir(True), "origin"); os.makedirs(folder, exist_ok=True); self.no_origin = ""; n = 0
        dlg = self._progress(f"Building {len(tids)} Origin template(s) …", len(tids))
        for i, tid in enumerate(tids):
            if dlg.wasCanceled(): break
            try:
                fig = self.api.demo_figure(tid, (checked(self.styles) or [self.style0])[0])
                O.draw_in_origin(self.make_driver, fig, "template", tid, folder, keep_open=True, save_otpu=os.path.join(folder, tid + ".otpu")); n += 1
            except Exception as e: self.ws.log(f"{tid}: {e}")
            dlg.setValue(i + 1); QApplication.processEvents()
        dlg.close()
        QMessageBox.information(self, "Origin templates", (f"Origin could not be started ({self.no_origin}). The scripts (.ogs) were written to {folder}; run this on a computer with Origin to get the .otpu files." if self.no_origin
                                                            else f"{n} Origin template(s) stored in {folder} (<id>.otpu). Origin: Plot > Templates > Template Library shows them after you add this folder."))


def _safe(s): return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_") or "graph"


# ---------------------------------------------------------------------------------------------------- combine
class CombineDialog(QDialog):
    def __init__(self, parent, n):
        super().__init__(parent); self.setWindowTitle("Combine into one figure"); f = QFormLayout(self)
        self.lay = QComboBox(); self.n = n
        for name, rc in (("1 × 2 (side by side)", (1, 2)), ("2 × 2", (2, 2)), ("2 × 3", (2, 3)), ("Stacked (one column)", (n, 1)), ("One row", (1, n)), ("Custom …", None)): self.lay.addItem(name, rc)
        best = {2: 0, 3: 2, 4: 1, 5: 2, 6: 2}.get(n, 2); self.lay.setCurrentIndex(best); self.lay.setToolTip("Where the kept graphs go, in the order of the previews")
        self.r = QSpinBox(); self.r.setRange(1, 8); self.c = QSpinBox(); self.c.setRange(1, 8); self.r.setValue(2); self.c.setValue(3)
        self.share = QCheckBox("Shared x axis in each column (numbers and title only at the bottom)"); self.share.setToolTip("Use it when the graphs of a column have the same x axis")
        f.addRow(f"{n} graphs. Layout:", self.lay); f.addRow("Custom rows:", self.r); f.addRow("Custom columns:", self.c); f.addRow(self.share)
        f.addRow(QLabel("Panel labels (a), (b) … are added in the format of the style. The same figure can be sent to Origin.", objectName="soft"))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); f.addRow(bb)
        self.lay.currentIndexChanged.connect(lambda _i: (self.r.setEnabled(self.lay.currentData() is None), self.c.setEnabled(self.lay.currentData() is None))); self.r.setEnabled(False); self.c.setEnabled(False)

    def layout_(self):
        rc = self.lay.currentData() or (self.r.value(), self.c.value()); return rc[0], rc[1], self.share.isChecked()


class CombinedView(QDialog):
    def __init__(self, page, fig):
        super().__init__(page); self.page, self.fig = page, fig; self.setWindowTitle("Combined figure"); self.resize(1100, 720); v = QVBoxLayout(self)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        self.canvas = FigureCanvasQTAgg(fig); v.addWidget(self.canvas, 1); h = QHBoxLayout(); h.addStretch(1)
        b1 = QPushButton("Draw in Origin like this", objectName="origin"); b1.setToolTip("The same combined figure in Origin: one layer per panel at the same place, saved as combined_<layout>.opju"); b1.clicked.connect(self.origin)
        b2 = QPushButton("Export…"); b2.setToolTip("Save the combined figure (PNG / TIFF / PDF / SVG) at the double-column width of the style"); b2.clicked.connect(self.export)
        b3 = QPushButton("Close"); b3.clicked.connect(self.accept)
        for b in (b1, b2, b3): h.addWidget(b)
        v.addLayout(h)

    def _tile(self):
        t = type("T", (), {})(); t.fig = self.fig; t.combo = dict(self.fig._ops_combo, files=[]); t.mapping = []; return t

    def origin(self): self.page.draw_all_in_origin([self._tile()])

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save the combined figure", os.path.join(self.page.out_folder(""), "combined.png"), "PNG (*.png);;TIFF (*.tiff);;PDF (*.pdf);;SVG (*.svg)")
        if path: save_combined(self.fig, path); self.page.ws.set_status(f"Combined figure written: {path}")


def save_combined(fig, path, dpi=None):
    from opstudio import core
    kw = {"pil_kwargs": {"compression": "tiff_lzw"}} if path.lower().endswith((".tif", ".tiff")) else {}
    import matplotlib
    with matplotlib.rc_context():
        core.apply_style(fig._ops_style); matplotlib.rcParams["savefig.bbox"] = None
        fig.savefig(path, dpi=dpi or fig._ops_style.get("export", {}).get("raster_dpi", 300), **kw)
    return path


# ---------------------------------------------------------------------------------------------------- export dialog
class ExportDialog(QDialog):
    def __init__(self, page, tiles):
        super().__init__(page); self.page = page; self.setWindowTitle(f"Export {len(tiles)} graph(s)"); f = QFormLayout(self); last = page._cfg().get("export") or {}
        self.fm = {}; h = QHBoxLayout()
        for ext in ("png", "tiff", "pdf", "svg", "eps", "jpg"):
            b = QCheckBox(ext.upper()); b.setChecked(ext in (last.get("formats") or ["png", "pdf"])); b.setToolTip({"tiff": "TIFF with LZW compression", "pdf": "vector, fonts embedded", "svg": "vector, text stays text", "eps": "vector (no transparency)"}.get(ext, ext.upper())); self.fm[ext] = b; h.addWidget(b)
        f.addRow("Formats:", h)
        self.wsel = QComboBox(); self.wsel.setToolTip("The widths of each graph's own style (journal column widths in mm)")
        for name, key in (("Single column", "single"), ("1.5 column", "one_and_half"), ("Double column", "double"), ("Custom (mm) …", None)): self.wsel.addItem(name, key)
        self.wsel.setCurrentIndex({"single": 0, "one_and_half": 1, "double": 2}.get(last.get("width"), 2)); self.mm = QDoubleSpinBox(); self.mm.setRange(30, 500); self.mm.setValue(120); self.mm.setSuffix(" mm")
        self.mm.setEnabled(False); self.wsel.currentIndexChanged.connect(lambda _i: self.mm.setEnabled(self.wsel.currentData() is None)); f.addRow("Size:", self.wsel); f.addRow("Custom width:", self.mm)
        self.dpi = QComboBox(); self.dpi.addItems(["From the style", "300", "600", "1200"]); self.dpi.setToolTip("Resolution of PNG / TIFF / JPG"); f.addRow("Resolution (dpi):", self.dpi)
        self.transp = QCheckBox("Transparent background"); f.addRow(self.transp)
        self.pattern = QLineEdit(last.get("pattern") or "{sample}_{template}"); self.pattern.setToolTip("File name: {sample} {template} {style} {date} {n}"); f.addRow("File name:", self.pattern)
        self.folder = QLineEdit(last.get("folder") or page.out_folder("Template_graphs")); b = QPushButton("…"); b.clicked.connect(lambda: self.folder.setText(QFileDialog.getExistingDirectory(self, "Folder", self.folder.text()) or self.folder.text()))
        hh = QHBoxLayout(); hh.addWidget(self.folder, 1); hh.addWidget(b); f.addRow("Folder:", hh)
        self.warn = QLabel("", objectName="soft"); self.warn.setWordWrap(True); f.addRow(self.warn)
        f.addRow(QLabel("EMF is not written here: paste the copied picture, or use Origin's own EMF export after 'Draw in Origin like this'.", objectName="soft"))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); f.addRow(bb)
        w = []
        for t in tiles:
            for x in page.api.min_size_warnings(t.fig, page.ops.load_style(t.combo["style"])):
                if x not in w: w.append(x)
        self.warn.setText(("Check before submission: " + "; ".join(w)) if w else "")

    def options(self):
        return {"formats": [e for e, b in self.fm.items() if b.isChecked()] or ["png"], "width": self.wsel.currentData() or self.mm.value(), "dpi": None if self.dpi.currentIndex() == 0 else int(self.dpi.currentText()),
                "transparent": self.transp.isChecked(), "pattern": self.pattern.text().strip() or "{sample}_{template}", "folder": self.folder.text().strip()}


# ---------------------------------------------------------------------------------------------------- the editor
class Editor(QDialog):
    """One or several kept graphs: the big picture, the columns it uses, its texts and variants. Edits can go to all open graphs."""
    def __init__(self, page, tiles):
        super().__init__(page); self.page, self.tiles, self.i = page, tiles, 0; self.setWindowTitle("Graph editor"); self.resize(1180, 760)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        h = QHBoxLayout(self); left = QVBoxLayout(); h.addLayout(left, 3)
        nav = QHBoxLayout(); self.prev = QPushButton("◀"); self.next = QPushButton("▶"); self.head = QLabel(""); self.prev.clicked.connect(lambda: self.go(-1)); self.next.clicked.connect(lambda: self.go(1))
        self.prev.setToolTip("Previous graph (Page Up)"); self.next.setToolTip("Next graph (Page Down)")
        nav.addWidget(self.prev); nav.addWidget(self.head, 1); nav.addWidget(self.next); left.addLayout(nav)
        self.holder = QVBoxLayout(); left.addLayout(self.holder, 1); self.canvas = None; self.FC = FigureCanvasQTAgg
        right = QVBoxLayout(); h.addLayout(right, 1)
        right.addWidget(QLabel("Texts (typed by you; empty = from the file):", objectName="soft")); f = QFormLayout(); self.txt = {}
        for key, lab in (("x_label", "x axis title"), ("y_label", "y axis title"), ("y2_label", "right axis title"), ("title", "title")):
            e = QLineEdit(); e.setToolTip(f"{lab}: sub / superscript as $_{{2}}$ and $^{{-1}}$"); e.editingFinished.connect(self.apply); self.txt[key] = e; f.addRow(lab, e)
        right.addLayout(f)
        right.addWidget(QLabel("Names of the curves (one per line: name in the file = name on the graph):", objectName="soft"))
        self.names = QPlainTextEdit(); self.names.setMaximumHeight(110); self.names.setToolTip("Renaming changes the graph only, never your file"); right.addWidget(self.names)
        right.addWidget(QLabel("Notes with an arrow (one per line: panel; your text; x; y; text x; text y):", objectName="soft"))
        self.notes = QPlainTextEdit(); self.notes.setMaximumHeight(80); self.notes.setToolTip("Your own notes on the graph, e.g.  1; my note; 460; 92; 200; 90  - the arrow points to (x, y), the text sits at (text x, text y). Only for templates with notes (TG-DTG panels)"); right.addWidget(self.notes)
        b = QPushButton("Apply"); b.clicked.connect(self.apply); right.addWidget(b)
        self.style = QComboBox(); [self.style.addItem(n, s) for s, n, _w in page.api.styles()]; self.style.currentIndexChanged.connect(lambda _i: self.apply()); right.addWidget(QLabel("Style:", objectName="soft")); right.addWidget(self.style)
        self.all = QCheckBox("Apply these edits to all open graphs"); self.all.setToolTip("Style, texts and names go to every graph opened in this editor"); right.addWidget(self.all)
        self.map = QLabel("", objectName="soft"); self.map.setWordWrap(True); right.addWidget(self.map); right.addStretch(1)
        for text, tip, fn in (("Draw in Origin like this", "This graph in Origin, the same", lambda: page.draw_all_in_origin([self.t])), ("Export…", "Save this graph at journal size", lambda: page.export_all([self.t])),
                              ("Copy picture", "Put the picture on the clipboard", lambda: page._copy(self.t)), ("Save as my template…", "Keep template + style + variants + texts as your own template", lambda: page.save_my_template(self.t))):
            bb = QPushButton(text); bb.setToolTip(tip); bb.clicked.connect(fn); right.addWidget(bb)
        c = QPushButton("Close"); c.clicked.connect(self.accept); right.addWidget(c)
        QShortcut(QKeySequence(Qt.Key_PageDown), self).activated.connect(lambda: self.go(1)); QShortcut(QKeySequence(Qt.Key_PageUp), self).activated.connect(lambda: self.go(-1))
        components = QPushButton('Edit components / panel zoom…')
        components.clicked.connect(self.edit_components); right.insertWidget(1, components)
        self.show_tile()

    def edit_components(self):
        ctrl = getattr(self.page.ws, 'workbench', None)
        if ctrl is None or self.t.combo.get('demo'): return
        from workspace_workbench import TemplateGraph
        from workspace_graph_editor import GraphEditor
        combo = dict(self.t.combo)
        if not combo.get('project_id') and combo.get('files'): combo['project_id'] = ctrl.project_for(combo['files'][0])
        graph = TemplateGraph(ctrl, combo)
        GraphEditor(ctrl, graph, self).exec()
        self.t.combo = graph.combo; self.page.redraw_tile(self.t); self.show_tile()

    @property
    def t(self): return self.tiles[self.i]

    def go(self, d):
        self.i = (self.i + d) % len(self.tiles); self.show_tile()

    def show_tile(self):
        t = self.t; self.head.setText(f"{self.i + 1} of {len(self.tiles)}:  {t.combo['title']}  ·  {t.combo['caption']}"); self.prev.setEnabled(len(self.tiles) > 1); self.next.setEnabled(len(self.tiles) > 1)
        if self.canvas is not None: self.holder.removeWidget(self.canvas); self.canvas.setParent(None)
        fig = self.page.draw_combo(t.combo)[0] if t.fig is not None else None
        if fig is None: return
        t.fig = fig; self.canvas = self.FC(fig); self.holder.addWidget(self.canvas)
        ov = t.combo.get("overrides") or {}
        for k, e in self.txt.items(): e.blockSignals(True); e.setText(str(ov.get(k, ""))); e.blockSignals(False)
        self.names.blockSignals(True); self.names.setPlainText("\n".join(f"{a} = {b}" for a, b in (t.combo.get("renames") or {}).items())); self.names.blockSignals(False)
        self.style.blockSignals(True); self.style.setCurrentIndex(max(0, self.style.findData(t.combo["style"]))); self.style.blockSignals(False)
        self.map.setText("Columns used:\n" + "\n".join(f"  {a}: {b}" for a, b in t.mapping))

    def apply(self):
        ov = {k: e.text() for k, e in self.txt.items() if e.text().strip()}; ren = {}
        for line in self.names.toPlainText().splitlines():
            if "=" in line: a, b = line.split("=", 1); ren[a.strip()] = b.strip()
        notes = []
        for line in self.notes.toPlainText().splitlines():
            q = [x.strip() for x in line.split(";")]
            try:
                if len(q) >= 4: notes.append({"panel": int(float(q[0])), "text": q[1], "at": [float(q[2]), float(q[3])], **({"text_at": [float(q[4]), float(q[5])]} if len(q) >= 6 else {})})
            except ValueError: self.page.ws.set_status(f"This note line could not be read: {line}")
        if notes: ov["notes"] = notes
        for t in (self.tiles if self.all.isChecked() else [self.t]):
            t.combo["overrides"] = dict(ov); t.combo["renames"] = dict(ren); t.combo["style"] = self.style.currentData(); t.combo.setdefault("switches", dict(self.page.current_switches()))
            t.combo["caption"] = re.sub(r"·\s*\S+$", "· " + t.combo["style"], t.combo["caption"]); t.cap.setText(t.combo["caption"])
            if ren: t.combo["overrides"]["_renames"] = ren
            self.page.redraw_tile(t)
        self.show_tile()

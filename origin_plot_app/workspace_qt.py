"""Origin Plot Studio - modern workspace (Qt).

A new window over the same engine as the current one (smart_plots, analysis_tools): Your graphs with ticks, the live graph
(zoom, pan, select a range and integrate it), the data and results of each graph and its graph type; step 2: sample names, drawing in
OriginPro, publication files (PNG, TIFF, PDF, SVG) at journal sizes, panel figures and the paper set - through the very functions the
current window uses (origin_plot_app.run_items / run_paper, smart_plots.export_publication / paper_preview); step 3: the Analysis and
Graph gallery sections run their tools (workspace_tools.py); step 4: the assistant panel (workspace_assistant.py) and Settings, including
which window opens at start. Its own settings are kept in settings_modern.json, started from the current window's. Started by Origin Plot Studio
(File > Modern window) with the graphs that are open there; it closes together with it (--parent PID). Your files are only read.

Command line:  workspace_qt.py [--files list.json] [--parent PID] [--ready-file PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QPlainTextEdit, QScrollArea, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSizePolicy,
                               QSplitter, QStackedWidget, QTableView, QTabWidget, QVBoxLayout, QWidget)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.widgets import SpanSelector  # noqa: E402

import smart_plots as sp  # noqa: E402

TITLE = "Origin Plot Studio"
# the interface colours (never used for the graphs themselves: curve colours and publication styles are the app's / yours)
ACCENT, BLUE, INK, SOFT, LINE, GROUND = "#B4532A", "#2563EB", "#172B4D", "#526277", "#D8E1EC", "#F3F6FA"      # Origin orange, primary blue, text, secondary text, borders, background
NAVY, TEAL, SELECTED, PANEL = "#17324D", "#0F766E", "#EAF2FF", "#FFFFFF"
SUCCESS, WARNING, ERROR = "#15803D", "#A16207", "#B91C1C"
SECTIONS = [("workspace", "Workspace", None),
            ("analysis", "Analysis", "Every analysis in one place: XRD, TGA, calorimetry and composition first, then the 44 data-analysis tools. "
                                     "Click one, set it, press Run: it works on the graphs ticked in Your graphs (or the one on show)."),
            ("figtype", "Graph gallery", "The 26 graph types that are drawn from a filled-in workbook, grouped by technique. Draw ticked workbooks as a type, or make a "
                                        "workbook template in that layout from a raw file. (The analyses are in Analysis.)"),
            ("assistant", "Assistant", ""),
            ("settings", "Settings", ""),
            ("templates", "Templates", "Graph = template × style × your data. Tick files, templates and styles: every combination is drawn; keep the ones you want, "
                                       "then draw them in Origin, export them or combine them into one figure.")]
NAV_ORDER = [0, 1, 2, 3, 4]             # the sections shown in the top bar. Section 5 (Templates) is inside Graph gallery: a switch at the top of both pages
GALLERY_PAGES = (5, 2)                  # Graph gallery = the templates (first) and the 26 workbook graph types
from workspace_tools import GALLERY_GROUPS, analysis_tree, figtype_tree  # noqa: E402,F401


STYLE = f"""
QWidget {{ font-family: "Segoe UI", "IBM Plex Sans", sans-serif; font-size: 10pt; color: {INK}; }}
QMainWindow, #ground {{ background: {GROUND}; }}
QToolTip {{ background: {NAVY}; color: white; border: 0; padding: 6px 8px; }}
/* panels: a header to drag, edges to resize */
QMainWindow::separator {{ background: {LINE}; width: 6px; height: 6px; }}
QMainWindow::separator:hover {{ background: {BLUE}; }}
QSplitter::handle {{ background: {LINE}; }}
QSplitter::handle:hover {{ background: {BLUE}; }}
QDockWidget {{ font-weight: 600; color: {NAVY}; titlebar-close-icon: none; }}
QDockWidget::title {{ background: #E8EEF6; padding: 7px 10px; text-align: left; border: 1px solid {LINE}; border-bottom: 0; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
QDockWidget > QWidget {{ background: {PANEL}; border: 1px solid {LINE}; border-top: 0; }}
/* the one top bar */
#header {{ background: {NAVY}; }}
#header QLabel#brand {{ color: white; font-size: 12pt; font-weight: 600; }}
#header QPushButton#navtab {{ color: #D5E2F2; background: transparent; border: 0; border-radius: 6px; padding: 7px 14px; font-weight: 600; min-height: 22px; }}
#header QPushButton#navtab:hover {{ background: #24496E; color: white; }}
#header QPushButton#navtab:checked {{ background: {SELECTED}; color: {NAVY}; }}
#header QPushButton#menu {{ color: white; background: transparent; border: 1px solid #3B5C7E; border-radius: 6px; padding: 6px 12px; }}
#header QPushButton#menu:hover {{ background: #24496E; }}
#header QPushButton#menu::menu-indicator {{ image: none; width: 0; }}
#header QLineEdit {{ background: #24496E; color: white; border: 1px solid #3B5C7E; }}
#topbar, #nav, #card, #status {{ background: {PANEL}; }}
#topbar {{ border-bottom: 1px solid {LINE}; }}
#nav {{ border-right: 1px solid {LINE}; }}
#card {{ border: 1px solid {LINE}; border-radius: 10px; }}
#status {{ border-top: 1px solid {LINE}; color: {SOFT}; }}
#title {{ font-size: 12pt; font-weight: 600; color: {NAVY}; }}
#h2 {{ font-size: 11.5pt; font-weight: 600; color: {NAVY}; }}
#h3 {{ font-size: 10pt; font-weight: 600; color: {NAVY}; }}
#soft {{ color: {SOFT}; }}
#ok {{ color: {SUCCESS}; }}
#warn {{ color: {WARNING}; }}
#error {{ color: {ERROR}; font-weight: 600; }}
#illustr {{ color: {TEAL}; font-weight: 600; }}
#navbtn {{ text-align: left; padding: 10px 12px; border: 0; border-radius: 8px; background: transparent; }}
#navbtn:hover {{ background: #EEF3F9; }}
#navbtn:checked {{ background: {SELECTED}; color: {BLUE}; font-weight: 600; }}
/* buttons: one primary (blue) per area, Origin actions orange, previews teal */
QPushButton {{ min-height: 22px; padding: 5px 14px; border: 1px solid #C5D0DE; border-radius: 6px; background: {PANEL}; color: {INK}; }}
QPushButton:hover {{ background: #F1F6FD; border-color: #9DB3CF; }}
QPushButton:pressed {{ background: #E2ECFA; }}
QPushButton:focus {{ border: 1px solid {BLUE}; }}
QPushButton:checked {{ background: {SELECTED}; border-color: {BLUE}; color: {BLUE}; }}
QPushButton:disabled {{ color: #93A1B3; background: #F3F6FA; border-color: #E1E7EF; }}
#accent {{ background: {ACCENT}; color: #FFFFFF; border: 0; font-weight: 600; }}
#accent:hover {{ background: #9A4521; }}
#accent:disabled {{ background: #E9D3C6; color: #7A5A48; }}
#primary {{ background: {BLUE}; color: #FFFFFF; border: 0; font-weight: 600; }}
#primary:hover {{ background: #1D4FD0; }}
#primary:disabled {{ background: #BFD0F5; color: #F3F6FA; }}
#stop {{ background: {PANEL}; color: {ERROR}; border: 1px solid {ERROR}; font-weight: 600; }}
#stop:hover {{ background: #FDF2F2; }}
#stop:disabled {{ color: #B8C2CF; border-color: #E1E7EF; background: {PANEL}; }}
#teal {{ background: {PANEL}; color: {TEAL}; border: 1px solid {TEAL}; font-weight: 600; }}
#teal:hover {{ background: #E8F5F3; }}
QToolButton {{ border-radius: 5px; }}
QToolButton:hover {{ background: #EEF3F9; }}
QToolButton:checked {{ background: {SELECTED}; color: {BLUE}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ min-height: 22px; padding: 3px 8px; border: 1px solid #C5D0DE; border-radius: 6px; background: {PANEL}; selection-background-color: {BLUE}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {BLUE}; }}
QLineEdit:disabled, QComboBox:disabled {{ background: #F3F6FA; color: #93A1B3; }}
QLineEdit[invalid="true"] {{ border: 1px solid {ERROR}; background: #FDF2F2; }}
QCheckBox {{ spacing: 6px; }}
QListWidget {{ border: 0; background: transparent; outline: 0; }}
QListWidget::item {{ padding: 7px 8px; margin: 2px 0; border: 1px solid #E3E9F1; border-radius: 8px; background: {PANEL}; }}
QListWidget::item:hover {{ border-color: #B8C8DD; }}
QListWidget::item:selected {{ background: {SELECTED}; border-color: {BLUE}; color: {INK}; }}
QListWidget::indicator {{ width: 16px; height: 16px; border: 1px solid #8A99AD; border-radius: 4px; background: #FFFFFF; }}
QListWidget::indicator:checked {{ background: {BLUE}; border-color: {BLUE}; image: none; }}
QTreeWidget {{ border: 0; background: {PANEL}; outline: 0; }}
QTreeWidget::item {{ padding: 5px 4px; border-radius: 5px; }}
QTreeWidget::item:hover {{ background: #F1F6FD; }}
QTreeWidget::item:selected {{ background: {SELECTED}; color: {BLUE}; }}
QTabWidget::pane {{ border: 0; }}
QTabBar::tab {{ padding: 6px 14px; border: 0; background: transparent; color: {SOFT}; margin-right: 2px; }}
QTabBar::tab:hover {{ color: {INK}; }}
QTabBar::tab:selected {{ color: {BLUE}; font-weight: 600; border-bottom: 2px solid {BLUE}; }}
QTableView {{ border: 1px solid #E3E9F1; gridline-color: #E3E9F1; font-family: "IBM Plex Mono", Consolas, monospace; selection-background-color: {SELECTED}; selection-color: {INK}; }}
QHeaderView::section {{ background: #F3F6FA; color: {NAVY}; border: 0; border-right: 1px solid {LINE}; border-bottom: 1px solid {LINE}; padding: 4px 6px; font-weight: 600; }}
QScrollArea {{ border: 0; background: transparent; }}
#selbar {{ background: {PANEL}; border: 1px solid #C5D0DE; border-radius: 8px; }}
#section {{ text-align: left; padding: 6px 4px; border: 0; border-bottom: 1px solid {LINE}; border-radius: 0; background: transparent; font-weight: 600; color: {NAVY}; }}
#section:hover {{ background: #F1F6FD; }}
QToolButton#step {{ padding: 3px 8px; color: {SOFT}; border-radius: 12px; }}
QToolButton#step:checked {{ color: {BLUE}; background: {SELECTED}; font-weight: 600; }}
#thumb {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px; padding: 6px; }}
#thumb:hover {{ border-color: #9DB3CF; }}
#thumb:checked {{ border: 2px solid {BLUE}; background: {SELECTED}; }}
/* the ribbon (Workspace only): compact, light */
#ribbody {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px; }}
#ribhead {{ background: transparent; }}
QTabBar#ribtabs::tab {{ padding: 5px 12px; background: transparent; color: {SOFT}; border: none; font-weight: 600; }}
QTabBar#ribtabs::tab:hover {{ color: {INK}; }}
QTabBar#ribtabs::tab:selected {{ color: {BLUE}; border-bottom: 2px solid {BLUE}; }}
#ribbon QLabel#ribname {{ color: {SOFT}; font-size: 8pt; }}
#ribbon QToolButton {{ padding: 3px 6px; border-radius: 4px; }}
#ribbon QToolButton#big {{ padding: 2px 4px; font-size: 8.5pt; }}
#ribbon QToolButton#mini {{ padding: 1px 1px; }}
#ribbon QToolButton#launch {{ padding: 0px; font-size: 8pt; color: {SOFT}; }}
#ribbon QToolButton#look {{ background: white; border: 1px solid {LINE}; border-radius: 4px; }}
#ribbon QToolButton#look:hover {{ border: 1px solid {BLUE}; }}
#ribbon QComboBox, #ribbon QLineEdit, #ribbon QDoubleSpinBox {{ min-height: 20px; padding: 1px 4px; }}
#ribsep {{ color: {LINE}; }}
QProgressBar#busy {{ border: 1px solid {LINE}; border-radius: 6px; background: white; text-align: center; font-size: 8pt; }}
QProgressBar#busy::chunk {{ background: {BLUE}; border-radius: 5px; }}
"""


def parent_alive(pid):
    """Is Origin Plot Studio (the program that opened this window) still running?"""
    try:
        if os.name == "nt":
            import ctypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, int(pid))
            if not h:
                return False
            code = ctypes.c_ulong()
            k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return code.value == 259
        os.kill(int(pid), 0)
        try:
            return Path(f"/proc/{int(pid)}/stat").read_text().split(")")[-1].split()[0] != "Z"
        except OSError:
            return True
    except (OSError, ValueError):
        return False


def options():
    """The analysis settings of the current window (settings.json), as the current window passes them to the engine."""
    o = {"max_labels": 15, "xrd_max": 15, "stack_labels": 15, "label_peaks": False, "app_dir": str(HERE)}
    cfg = load_cfg()
    for k, v in cfg.items():
        if isinstance(v, (str, int, float, bool)) and k not in o:
            o[k] = v
    o["label_peaks"] = bool(cfg.get("labxy", False))                 # as the current window passes them: 'Label peaks on XY graphs'
    try:
        n = max(1, int(float(cfg.get("peak_labels", "all"))))
        o.update(max_labels=n, xrd_max=n, stack_labels=n)
    except (TypeError, ValueError):                                     # "all": every XRD peak gets its label
        o.update(max_labels=15, xrd_max=None, stack_labels=None)
    return o


def cfg_path():
    """This window's own settings. The current window rewrites settings.json with its own values when it closes, so the two windows
    keep separate files; this one starts from the current window's settings (load_cfg)."""
    return Path(os.environ.get("OPS_SETTINGS_FILE") or HERE / "settings_modern.json")


def load_cfg():
    cfg = {}
    for f in (HERE / "settings.json", cfg_path()):
        try:
            cfg.update(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def save_cfg(changes):
    """Write the keys changed here into this window's settings file."""
    try:
        cfg = json.loads(cfg_path().read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    cfg.update(changes)
    try:
        tmp = cfg_path().with_name(cfg_path().name + ".modern.tmp")
        tmp.write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, cfg_path())
    except Exception:
        pass


class Job(QObject):
    """One drawing / saving job off the window's thread; log lines and progress come back as signals."""
    line = Signal(str)
    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, work):
        super().__init__()
        self.work = work

    def run(self):
        try:
            self.done.emit(self.work(self.line.emit, self.progress.emit))
        except Exception:
            self.failed.emit(traceback.format_exc(limit=6))


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df=None):
        super().__init__()
        self.df = df

    def rowCount(self, parent=QModelIndex()):
        return 0 if self.df is None else min(len(self.df), 100000)

    def columnCount(self, parent=QModelIndex()):
        return 0 if self.df is None else len(self.df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or self.df is None:
            return None
        v = self.df.iat[index.row(), index.column()]
        if isinstance(v, float):
            return f"{v:.6g}"
        return "" if v is None else str(v)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or self.df is None:
            return None
        return str(self.df.columns[section]) if orientation == Qt.Horizontal else str(section + 1)

    def set(self, df):
        import pandas as pd
        self.beginResetModel()
        self.df = df if isinstance(df, pd.DataFrame) else None
        self.endResetModel()


class Loader(QObject):
    """Reads the files and builds their graphs with the same engine as the current window (off the window's thread)."""
    done = Signal(object, object)          # [items], [messages]

    def __init__(self, paths, opt, existing=()):
        super().__init__()
        self.paths, self.opt, self.existing = paths, opt, list(existing)

    def run(self):
        """Read the files and build their graphs as the engine does (sp.prepare): peak lists first, then the names and phase amounts of
        the files, then each pattern or fit is matched with its peak list - by sample name, or because the listed peaks sit on its
        peaks - so it gets phase labels and tick rows; then the patterns are built."""
        fresh, msgs = [], []
        for p in self.paths:
            try:
                its, lines = sp.load_file(p)
                fresh += its
                msgs += [l for l in (lines or []) if isinstance(l, str)][:4]
            except Exception as e:
                msgs.append(f"{Path(p).name}: not read ({e})")
        pool = list(self.existing)
        try:
            _n, errs = sp.prepare(pool, fresh, self.opt)
            msgs += errs
            news = list(getattr(sp, "_LINK_NEWS", []))
            if news:
                msgs += [l.strip() for l in news]
                sp._LINK_NEWS.clear()
        except Exception as e:
            msgs.append(f"not all graphs were built ({e})")
        self.done.emit(pool[len(self.existing):], msgs)


class Workspace(QMainWindow):
    def __init__(self, paths=(), ready_file=None):
        super().__init__()
        self.setWindowTitle(TITLE)
        self.resize(1440, 900)
        self.opt = options()
        self.singles, self.combined, self.boards, self.items = [], [], [], []
        self.user_groups = []                                  # [(how, [member keys])]: groups you made, kept when the graphs are grouped again
        self.cfg = load_cfg()
        self.job_thread = None
        self.cancel = [False]
        self.ready_file = ready_file
        self.span = None
        self.sel = None
        self.thread = None
        self.tick_paths = set()
        self.setAcceptDrops(True)
        root = QWidget(objectName="ground")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._topbar())
        body = QSplitter(Qt.Horizontal)                        # the side bar can be made wider or narrower, or folded away (drag its edge)
        body.setObjectName("bodysplit")
        body.setHandleWidth(6)
        self.bodysplit = body
        self.navw = self._nav()
        body.addWidget(self.navw)
        from workspace_tools import Tools, ToolPage
        self.tools = Tools(self)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._workspace())
        self.pages.addWidget(ToolPage(self, "Analysis", SECTIONS[1][2], analysis_tree()))
        self.pages.addWidget(ToolPage(self, "Graph gallery", SECTIONS[2][2], figtype_tree()))
        self.pages.addWidget(self._assistant_page())
        self.pages.addWidget(self._settings_page())
        try:
            from workspace_templates import TemplatePage
            self.templates_page = TemplatePage(self)
        except Exception as e:                                  # the template library is not installed yet (it arrives with the next update)
            self.templates_page = QLabel(f"The template library is not installed yet. Run Help > Check for updates once more.\n\n({e})"); self.templates_page.setAlignment(Qt.AlignCenter)
        self.pages.addWidget(self.templates_page)
        body.addWidget(self.pages)
        body.setStretchFactor(1, 1)
        body.setCollapsible(0, True)
        body.setSizes([200, 1300])
        v.addWidget(body, 1)
        self.status = QLabel("Ready.", objectName="status")
        self.status.setContentsMargins(16, 6, 16, 6)
        from PySide6.QtWidgets import QProgressBar
        srow = QHBoxLayout(); srow.setContentsMargins(0, 0, 12, 0)
        srow.addWidget(self.status, 1)
        self.pbar = QProgressBar(objectName="busy")                    # moves while the app draws or saves; fills up as the graphs are done
        self.pbar.setFixedWidth(220); self.pbar.setFixedHeight(14); self.pbar.setTextVisible(True); self.pbar.hide()
        srow.addWidget(self.pbar)
        v.addLayout(srow)
        self._dock()
        self._panels_menu()
        import workspace_actions
        workspace_actions.install(self)
        import workspace_menu
        workspace_menu.install(self)
        import workspace_ribbon
        workspace_ribbon.install(self)                        # File, Home, Graph, Axes, Lines, Insert at the top, as in Word
        try:
            import workspace_shell
            workspace_shell.install(self)                     # one top bar, panels everywhere, the layout kept between sessions
        except Exception:                                     # the arrangement must never keep the app from starting
            self.log("!! the panel layout could not be set up; the app works without it:\n" + traceback.format_exc(limit=4))
        try:
            import workspace_session
            workspace_session.install(self)                   # File far left, one Undo / Redo, clear / start afresh with undo, recent sessions, autosave, command search
        except Exception:
            self.log("!! the session commands could not be set up; the app works without them:\n" + traceback.format_exc(limit=4))
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.add_files)
        QShortcut(QKeySequence("Escape"), self, activated=self.clear_selection)
        if paths:
            self.load(list(paths))
        else:
            self.show_empty()

    # ------------------------------------------------------------------ layout
    def _topbar(self):
        w = QWidget(objectName="topbar")
        h = QHBoxLayout(w)
        h.setContentsMargins(16, 10, 16, 10)
        h.setContentsMargins(8, 4, 12, 4)
        mark = QLabel("◆")
        mark.setStyleSheet(f"color: {ACCENT}; font-size: 18pt;")
        h.addWidget(mark)
        name_ = QLabel("Origin Plot Studio", objectName="title")
        name_.setToolTip(f"Version {sp.VERSION} (Help › About)")
        h.addWidget(name_)
        self.brand = [mark, name_]                                       # replaced by the ribbon's tabs (workspace_ribbon)
        self.topbar_layout = h
        h.addStretch(1)
        self.search = QLineEdit(placeholderText="Find a graph by name")
        self.search.setMinimumWidth(200)
        self.search.textChanged.connect(self.filter_graphs)
        h.addWidget(self.search)
        h.addStretch(1)
        self.panels_btn = QPushButton("Panels ▾")
        self.panels_btn.setToolTip("Minimise the parts you do not need (side bar, Your graphs, graph settings, assistant), or focus on the graph")
        h.addWidget(self.panels_btn)
        self.ai_btn = QPushButton("Assistant")
        self.ai_btn.setCheckable(True)
        self.ai_btn.setToolTip("Show or hide the assistant beside your work (drag its title bar to make it a window of its own)")
        self.ai_btn.clicked.connect(lambda on: self.show_assistant(on))
        h.addWidget(self.ai_btn)
        add = QPushButton("Add files…")
        add.clicked.connect(self.add_files)
        h.addWidget(add)
        newb = QPushButton("New")
        newb.setToolTip("Start afresh: an empty project (Ctrl+N). Your files and saved results are not touched; File › Resume last session brings the list back")
        newb.clicked.connect(lambda: self.new_project())
        h.addWidget(newb)
        refb = QPushButton("↻ Refresh")
        refb.setToolTip("Draw every graph again with the current settings (File › Refresh previews)")
        refb.clicked.connect(lambda: self.refresh_previews())
        h.addWidget(refb)
        draw = QPushButton("Draw ticked in Origin", objectName="accent")
        draw.clicked.connect(lambda: self.draw_origin("ticked"))
        h.addWidget(draw)
        return w

    def _nav(self):
        w = QWidget(objectName="nav")
        w.setMinimumWidth(110)
        w.setMaximumWidth(360)
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 14, 10, 14)
        v.setSpacing(4)
        self.navgroup = QButtonGroup(self)
        for i in NAV_ORDER:
            key, label, _t = SECTIONS[i]
            b = QPushButton(label, objectName="navbtn")
            b.setCheckable(True)
            b.setMinimumHeight(40)
            b.clicked.connect(lambda _c=False, i=i: self.go(i))
            self.navgroup.addButton(b, i)
            v.addWidget(b)
            if i == 0:
                b.setChecked(True)
        v.addStretch(1)
        note = QLabel("Drag the edges to resize; Panels ▾ and the View menu show, hide and move the parts. F1: mouse and keys.", objectName="soft")
        note.setWordWrap(True)
        v.addWidget(note)
        return w

    def _card(self):
        f = QFrame(objectName="card")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        return f, lay

    def _later(self, label, text):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 24, 24, 24)
        f, lay = self._card()
        lay.addWidget(QLabel(label, objectName="h2"))
        t = QLabel(text, objectName="soft")
        t.setWordWrap(True)
        lay.addWidget(t)
        v.addWidget(f)
        v.addStretch(1)
        return w

    def go(self, i):
        if SECTIONS[i][0] == "assistant":
            self._assistant_to_page()
        else:
            self._assistant_to_dock()
        self.pages.setCurrentIndex(i)
        nb = self.navgroup.button(2 if i in GALLERY_PAGES else i)
        if nb is not None: nb.setChecked(True)
        if i in GALLERY_PAGES: self.gallery_last = i
        if SECTIONS[i][0] == "assistant":
            self.assistant.input.setFocus()

    # ------------------------------------------------------------------ step 4: the assistant beside your work
    def _dock(self):
        from PySide6.QtWidgets import QDockWidget
        from workspace_assistant import AssistantPanel
        self.assistant = AssistantPanel(self)
        self.dock = QDockWidget("⠿  Assistant", self)
        self.dock.setObjectName("assistantDock")
        self.dock.setWidget(self.assistant)
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.dock.setMinimumWidth(340)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.visibilityChanged.connect(self._ai_btn_sync)
        self.dock.setVisible(bool(self.cfg.get("assistant_open", False)))

    def _ai_btn_sync(self, v):
        try:
            self.ai_btn.setChecked(v)
        except RuntimeError:                                   # the window is closing
            pass

    PANELS = [("nav", "Side bar", "Ctrl+1"), ("graphs", "Your graphs", "Ctrl+2"), ("settings", "Graph settings", "Ctrl+3"), ("assistant", "Assistant", "Ctrl+4")]

    def _panel_widget(self, key):
        return {"nav": self.navw, "graphs": self.graphs_dock, "settings": self.settings_dock, "assistant": self.dock}[key]

    def _panels_menu(self):
        """Panels ▾: show or minimise each part; 'Focus on the graph' leaves only the graph; remembered for the next start."""
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QMenu
        m = QMenu(self.panels_btn)
        self.panel_actions = {}
        hidden = set(self.cfg.get("hidden_panels") or [])
        for key, label, sc in self.PANELS:
            a = QAction(label, self, checkable=True)
            a.setShortcut(QKeySequence(sc))
            a.setChecked(self._panel_widget(key).isVisible() if key == "assistant" else key not in hidden)
            a.toggled.connect(lambda on, k=key: self.set_panel(k, on))
            m.addAction(a)
            self.addAction(a)                                  # the shortcut works anywhere in the window
            self.panel_actions[key] = a
            if key != "assistant":
                self._panel_widget(key).setVisible(key not in hidden)
        m.addSeparator()
        f = QAction("Focus on the graph", self)
        f.setShortcut(QKeySequence("F11"))
        f.triggered.connect(self.focus_graph)
        m.addAction(f)
        self.addAction(f)
        a = QAction("Show everything", self)
        a.triggered.connect(lambda: [self.panel_actions[k].setChecked(True) for k, _l, _s in self.PANELS if k != "assistant"])
        m.addAction(a)
        m.addSeparator()
        for d, t in ((self.graphs_dock, "Your graphs"), (self.settings_dock, "Graph settings"), (self.dock, "Assistant")):
            m.addAction(f"{t} as its own window", lambda d=d: self.panel_as_window(d))
        b = QAction("Put the panels back in place", self)
        b.triggered.connect(self.dock_back)
        m.addAction(b)
        self.panels_btn.setMenu(m)
        self.dock.visibilityChanged.connect(lambda v: self.panel_actions["assistant"].setChecked(v) if self.panel_actions["assistant"].isChecked() != v else None)

    def set_panel(self, key, on):
        if key == "assistant":
            if self.dock.isVisible() != on:
                self.show_assistant(on)
            return
        if key == "nav":                                       # the side bar with the sections (they are also in the top bar)
            self.navw.setMaximumWidth(360 if on else 0)
            if on:
                self.navw.setMinimumWidth(150); s_ = self.bodysplit.sizes(); self.bodysplit.setSizes([190, max(400, sum(s_) - 190)])
        self._panel_widget(key).setVisible(on)
        hidden = [k for k, _l, _s in self.PANELS if k != "assistant" and not self.panel_actions[k].isChecked()]
        save_cfg({"hidden_panels": hidden})

    def focus_graph(self):
        """Only the graph: side bar, Your graphs, settings and assistant minimised (Panels > Show everything brings them back)."""
        self.go(0)
        for k, _l, _s in self.PANELS:
            self.panel_actions[k].setChecked(False)
        self.set_status("Only the graph is shown. Panels ▾ > Show everything (or Ctrl+1 … Ctrl+4) brings the parts back.")

    def show_assistant(self, on=True):
        if getattr(self, "asst_in_page", False):              # on the Assistant tab: the chat is already full size
            if on:
                self.assistant.input.setFocus()
                return
            self._assistant_to_dock()
        self.dock.setVisible(on)
        if on:
            self.dock.raise_()
            self.assistant.input.setFocus()
        save_cfg({"assistant_open": bool(on)})

    def _assistant_page(self):
        """The Assistant tab: the chat itself, full size. Leaving the tab puts the chat back beside your work (if it was there)."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 12, 16, 12)
        head = QHBoxLayout()
        head.addWidget(QLabel("Assistant", objectName="h2"))
        hint = QLabel("The same chat is also beside your work in the other sections (View › Panels › Assistant beside the work, or Ctrl+K).", objectName="soft")
        head.addWidget(hint, 1)
        v.addLayout(head)
        self.asst_card, self.asst_host = self._card()
        self.asst_host.setContentsMargins(6, 6, 6, 6)
        v.addWidget(self.asst_card, 1)
        self.asst_in_page = False
        return w

    def _assistant_to_page(self):
        if self.asst_in_page:
            return
        self._dock_was_open = self.dock.isVisible()
        self.asst_in_page = True
        self.asst_host.addWidget(self.assistant)                  # taken out of the side panel
        self.assistant.show()
        self.dock.hide()

    def _assistant_to_dock(self):
        if not self.asst_in_page:
            return
        self.asst_in_page = False
        self.dock.setWidget(self.assistant)
        if getattr(self, "_dock_was_open", False):
            self.dock.show()

    # ------------------------------------------------------------------ step 4: settings
    SETTING_FORM = [
        ("XRD", [("wavelength", "X-ray tube / wavelength", "TUBES"), ("xrd_phases", "Phases on the patterns", "XRD_PHASES"),
                 ("xrd_labels", "Peak labels", "XRD_LABELS"), ("xrd_background", "Background", "XRD_BG"), ("fit_view", "Fit files open as", "FIT_VIEWS"), ("fit_style", "Fit style", "FIT_STYLES"),
                 ("fit_colours", "Fit colours", "FIT_COLOURS"), ("stack_style", "Stacked patterns", "STACK_STYLES"),
                 ("inset", "Zoomed part (inset)", "INSETS"), ("xrd_store", "Store the phases found in your files", bool)]),
        ("TGA", [("tga_mass", "Mass axis", "TGA_MASS"), ("tga_curves", "Curves", "TGA_CURVES"), ("tga_material", "Material", "TGA_MATERIAL"),
                 ("tga_ranges", "Temperature intervals (e.g. 50-200, 400-500)", None), ("tga_m0", "Reference mass at (°C)", None)]),
        ("FTIR", [("ftir_signal", "Signal", "FTIR_SIGNAL")]),
        ("Particle size", [("psd_style", "How a PSD is drawn", "PSD_STYLES")]),
        ("Calorimetry", [("calo_excl", "Exclusion window (min)", None), ("calo_from", "Start at (h)", None), ("calo_ages", "Ages", None),
                         ("calo_info", "Information on the figure", None)]),
        ("Figures", [("replicates", "Replicates", "REPLICATES"), ("orientation", "Orientation", "ORIENTATIONS"), ("per_fig", "Graphs per figure", "PER_FIG"),
                     ("label_text", "Label text", "LABEL_TEXT"), ("pointers", "Label pointers", "POINTERS"),
                     ("page_layout", "Page layout", "PAGE_LAYOUTS"), ("label_size", "Label size", "LABEL_SIZES"), ("tick", "Tick weight (pt)", None)]),
        ("Peak labels", [("labxy", "Label peaks automatically on XY graphs", bool), ("peak_labels", "Most peak labels per graph ('all' or a number)", None)]),
    ]

    def _settings_page(self):
        import assistant as ai
        from PySide6.QtWidgets import QFormLayout, QRadioButton
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 16, 16, 16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        inner = QWidget(objectName="ground")
        grid = QHBoxLayout(inner)
        grid.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        left, right = QVBoxLayout(), QVBoxLayout()
        grid.addLayout(left, 1)
        grid.addLayout(right, 1)
        c = self.cfg
        # the AI
        f, lay = self._card()
        lay.addWidget(QLabel("AI for the assistant", objectName="h2"))
        lay.addWidget(QLabel("<b>Web search without any key:</b> in the assistant choose 'Free web search' (OpenAlex, Semantic Scholar, Crossref and arXiv papers with a preview of each, "
                             "and links to the same search in Google and Google Scholar), or 'Ask in your browser' with your ChatGPT, Claude or "
                             "Gemini account.<br><b>Google's own search inside the assistant:</b> a free Gemini key from Google AI Studio "
                             "('Get a key…' with Gemini chosen) - Gemini answers with Google Search and lists the pages (Google's free "
                             "limits apply).", objectName="soft", wordWrap=True, textFormat=Qt.RichText))
        lay.addWidget(QLabel("Paste the key of your AI: the app sees whose it is. The key is stored encrypted by Windows, in the same place as "
                             "the current window's assistant, and never written to your results, logs or the repository.", objectName="soft", wordWrap=True))
        form = QFormLayout()
        self.ai_choice = QComboBox()
        self.ai_choice.addItems(ai.CHOICES)
        self.ai_key = QLineEdit()
        self.ai_key.setEchoMode(QLineEdit.Password)
        self.ai_key.setPlaceholderText("paste the key (not needed for a local model)")
        self.ai_addr = QLineEdit()
        self.ai_addr.setPlaceholderText("only for 'Other service', e.g. https://openrouter.ai/api/v1")
        form.addRow("AI", self.ai_choice)
        form.addRow("Key", self.ai_key)
        form.addRow("Address", self.ai_addr)
        lay.addLayout(form)
        row = QHBoxLayout()
        b = QPushButton("Connect and save", objectName="primary")
        b.clicked.connect(self.ai_save_key)
        row.addWidget(b)
        g = QPushButton("Get a key…")
        g.clicked.connect(self.ai_get_key)
        row.addWidget(g)
        rm = QPushButton("Remove this AI's key")
        rm.clicked.connect(self.ai_remove_key)
        row.addWidget(rm)
        row.addStretch(1)
        lay.addLayout(row)
        self.ai_msg = QLabel("", objectName="soft", wordWrap=True)
        lay.addWidget(self.ai_msg)
        row2 = QHBoxLayout()
        for text, fn in (("Edit my instructions", lambda: self.open_path(ai.instructions_file(self.assistant.home))),
                         ("What it has learned", lambda: self.open_path(ai.lessons_file(self.assistant.home)))):
            bb = QPushButton(text)
            bb.clicked.connect(fn)
            row2.addWidget(bb)
        row2.addStretch(1)
        lay.addLayout(row2)
        left.addWidget(f)
        left.addStretch(1)
        # analysis settings
        f, lay = self._card()
        lay.addWidget(QLabel("Analysis and figure settings", objectName="h2"))
        lay.addWidget(QLabel("The same settings as Analysis settings in the current window. They start from that window's and are kept for "
                             "this window. Apply redraws your graphs with them.", objectName="soft", wordWrap=True))
        self.set_fields = {}
        for group, rows in self.SETTING_FORM:
            lay.addWidget(QLabel(group, objectName="h2"))
            fl = QFormLayout()
            for key, label, choices in rows:
                if choices is bool:
                    wdg = QCheckBox()
                    wdg.setChecked(bool(c.get(key, key != "labxy")))
                elif choices:
                    vals = [str(x) for x in (getattr(sp, choices, None) or [])]
                    wdg = QComboBox()
                    wdg.setMinimumContentsLength(14)
                    wdg.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
                    wdg.setEditable(key in ("wavelength", "inset"))          # the zoom: also a typed 2θ range such as 27-37
                    wdg.addItems(vals)
                    cur = str(c.get(key, vals[0] if vals else ""))
                    if cur and wdg.findText(cur) < 0 and key in ("wavelength", "inset"):
                        wdg.addItem(cur)
                    wdg.setCurrentText(cur)
                else:                                           # the current window's defaults
                    wdg = QLineEdit(str(c.get(key, {"calo_excl": "45", "calo_from": "0", "tick": "0.75", "peak_labels": "all"}.get(key, ""))))
                self.set_fields[key] = wdg
                fl.addRow(label, wdg)
            lay.addLayout(fl)
        ap = QPushButton("Apply to my graphs", objectName="primary")
        ap.clicked.connect(self.apply_settings)
        lay.addWidget(ap, 0, Qt.AlignLeft)
        right.addWidget(f)
        right.addStretch(1)
        return w

    def open_path(self, p):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if not os.environ.get("OPS_NO_OPEN"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def apply_settings(self):
        ch = {}
        for k, wdg in self.set_fields.items():
            ch[k] = wdg.isChecked() if isinstance(wdg, QCheckBox) else wdg.currentText() if isinstance(wdg, QComboBox) else wdg.text().strip()
        save_cfg(ch)
        self.cfg.update(ch)
        self.opt = options()
        n = 0
        for it in self.singles:
            try:
                it.build(self.opt, it.kind)
                n += 1
            except Exception as e:
                self.log(f"   {it.title.strip()}: not redrawn ({e})")
        self.regroup()
        row = self.list.currentRow()
        self.refresh_list()
        if 0 <= row < self.list.count():
            self.list.setCurrentRow(row)
            self.show_item(row)
        self.set_status(f"Settings saved; {n} graph(s) redrawn with them.")
        return n

    def ai_save_key(self):
        import assistant as ai
        try:
            conn = ai.detect(self.ai_key.text(), self.ai_addr.text(), self.ai_choice.currentText())
        except ai.AIError as e:
            self.ai_msg.setText(str(e))
            return "error"
        self.ai_msg.setText(f"Linking to {conn['name']} …")
        QApplication.processEvents()
        try:
            ids = ai.models(conn)
        except ai.AIError as e:
            self.ai_msg.setText(f"Not linked: {e}")
            return "error"
        h = self.assistant.home
        c = ai.load_settings(h)
        keys = {k: ai.reveal_key(v) for k, v in (c.get("keys") or {}).items()}
        keys = {k: v for k, v in keys.items() if v}
        if conn.get("key"):
            keys[conn["provider"]] = conn["key"]
        addrs = dict(c.get("addresses") or {})
        if self.ai_addr.text().strip():
            addrs[conn["provider"]] = self.ai_addr.text().strip()
        models = dict(c.get("models") or {})
        if ids and models.get(conn["provider"]) not in ids:
            models[conn["provider"]] = ids[0]
        lost = ai.save_settings(h, {**c, "choice": ai.PROVIDERS[conn["provider"]]["name"], "keep_key": True, "keys": keys, "models": models, "addresses": addrs})
        self.ai_key.clear()
        self.ai_msg.setText(f"Linked to {conn['name']}: {len(ids)} model(s)." + (" Windows could not store the key safely, so it is kept only "
                            "until you close the app." if lost else " Saved.") + " The assistant uses it now.")
        self.assistant.reload()
        return "linked"

    def ai_remove_key(self):
        import assistant as ai
        pr = ai.provider_of(self.ai_choice.currentText())
        if pr is None:
            self.ai_msg.setText("Choose the AI in the list first.")
            return
        h = self.assistant.home
        c = ai.load_settings(h)
        keys = {k: ai.reveal_key(v) for k, v in (c.get("keys") or {}).items() if k != pr}
        ai.save_settings(h, {**c, "keys": {k: v for k, v in keys.items() if v}})
        self.ai_msg.setText(f"The key of {ai.PROVIDERS[pr]['name']} is removed.")
        self.assistant.reload()

    def ai_get_key(self):
        import assistant as ai
        pr = ai.provider_of(self.ai_choice.currentText())
        page = ai.PROVIDERS[pr]["keypage"] if pr else ""
        self.ai_msg.setText(ai.GUIDES.get(pr, ai.GUIDES[None]))
        if page and not os.environ.get("OPS_NO_OPEN"):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(page))

    # ------------------------------------------------------------------ the assistant's actions (only these; each confirmed by you)
    def load_sync(self, paths):
        """Read files now (for the assistant: the next action may need them)."""
        ld = Loader(list(paths), self.opt, self.singles)
        ld.done.connect(self.loaded)
        ld.run()

    def _graphs(self, v):
        if v == "all":
            return list(self.items)
        if v in ("ticked", None, ""):
            return self.ticked()
        if v == "none":
            return []
        vs = v if isinstance(v, list) else [v]
        out = []
        for n in vs:
            n = int(n)
            if not 1 <= n <= len(self.items):
                raise ValueError(f"there is no graph {n} (the list has {len(self.items)})")
            out.append(self.items[n - 1])
        return out

    def table_for_chat(self, a):
        """(table, title) of one graph for the chat: its data or its results."""
        it = self._graphs(a.get("graph"))[0]
        what = "results" if str(a.get("what", "data")).startswith("result") else "data"
        df = getattr(it, "results", None) if what == "results" else self.table_of(it)
        import pandas as pd
        if not isinstance(df, pd.DataFrame):
            df = None
        rows = max(1, min(int(a.get("rows") or 20), 60))
        return (df.head(rows) if df is not None else None), f"{what.capitalize()} of {it.title.strip()[:60]}"

    def _tick_only(self, its):
        ids = {id(i) for i in its}
        for i, it in enumerate(self.items):
            self.list.item(i).setCheckState(Qt.Checked if id(it) in ids else Qt.Unchecked)
        self.update_count()

    def do_action(self, a, user_texts=()):
        """One action of the assistant, after you pressed Do it. Returns a short line for the chat and for the AI."""
        import assistant as ai
        d = a.get("do")
        if d == "look":
            it = self._graphs(a.get("graph"))[0]
            info = {"name": it.title.strip(), "kind": getattr(it, "kind", "panel figure"), "file": os.path.basename(str(getattr(it, "path", "") or ""))}
            df = self.table_of(it)
            if df is not None:
                cols = {}
                for c in list(df.columns)[:14]:
                    try:
                        s_ = df[c].astype(float)
                        cols[str(c)] = f"{s_.min():.6g} to {s_.max():.6g} ({s_.notna().sum()} values)"
                    except Exception:
                        cols[str(c)] = "text"
                info["columns"] = cols
            res = getattr(it, "results", None)
            if res is not None and hasattr(res, "head"):
                info["results"] = res.head(8).to_string(index=False)
            info["record"] = (getattr(it, "record", None) or [])[:5]
            return json.dumps(info, ensure_ascii=False, default=str)[:3000]
        if d == "show":
            it = self._graphs(a.get("graph"))[0]
            self.go(0)
            self.list.setCurrentRow(self.items.index(it))
            return f"showing {it.title.strip()[:60]}"
        if d == "show_graph":
            it = self._graphs(a.get("graph"))[0]
            self.list.setCurrentRow(self.items.index(it))
            return f"picture of {it.title.strip()[:60]} in the chat"
        if d == "show_table":
            df, title = self.table_for_chat(a)
            return f"{title}: {0 if df is None else len(df)} row(s) shown in the chat"
        if d == "tick":
            its = self._graphs(a.get("graphs"))
            self._tick_only(its)
            return f"{len(its)} ticked"
        if d == "sample":
            its = [i for i in self._graphs(a.get("graphs")) if isinstance(i, sp.Item) and i in self.singles]
            self._tick_only(its)
            self.sample.setText(str(a.get("name", "")).strip())
            self.apply_sample()
            return f"{len(its)} graph(s) named '{a.get('name')}'"
        if d == "kind":
            it = self._graphs(a.get("graph"))[0]
            it.build(self.opt, str(a.get("kind")))
            self.refresh_list()
            return f"graph is now {it.kind}"
        if d == "analysis":
            import analysis_tools as at
            tool = str(a.get("tool", ""))
            if tool not in at.TOOLS:
                raise ValueError(f"unknown tool {tool}")
            self._tick_only(self._graphs(a.get("graphs")))
            r = self.tools.run_tool(tool, dict(a.get("settings") or {}), self.pages.widget(1), sync=True)
            if isinstance(r, tuple) and r and r[0] == "error":
                return f"not done: {r[1]}"
            files, tables, notes = r
            out = f"done ({notes[0] if notes else ''}); {len(files)} new graph(s) at the end of the list"
            for n_, t_ in tables[:3]:
                out += f"\n{n_}:\n" + t_.head(12).to_string(index=False, float_format=lambda v: f"{v:.6g}")
            return out
        if d == "tga_steps":
            if a.get("graphs"):
                self._tick_only(self._graphs(a.get("graphs")))
            r = self.tools.tga_steps(self.pages.widget(1))
            return r[1] if isinstance(r, tuple) else r.to_string(index=False)
        if d == "figtype":
            if a.get("graphs"):
                self._tick_only(self._graphs(a.get("graphs")))
            r = self.tools.figtype_draw(str(a.get("type", "")).upper(), self.pages.widget(2))
            return r[1] if isinstance(r, tuple) else r
        if d == "figure":
            self._tick_only([i for i in self._graphs(a.get("graphs")) if not isinstance(i, sp.Board)])
            self.make_board()
            return f"figure made: {self.boards[-1].title}" if self.boards else "no figure"
        if d == "folder":
            p = str(a.get("path", "")).strip()
            if not p:
                raise ValueError("no folder given")
            self.outdir.setText(p)
            self.remember()
            return f"results folder: {p}"
        if d == "save":
            it = self._graphs(a.get("graph"))[0]
            self.list.setCurrentRow(self.items.index(it))
            self.save_current()
            return "saving the publication files (see the status bar)"
        if d == "draw":
            v = a.get("graphs", "ticked")
            if v not in ("ticked", "all"):
                self._tick_only(self._graphs(v))
                v = "ticked"
            self.draw_origin(v)
            return "drawing in Origin (see the status bar and Details)"
        if d == "paper_preview":
            self.paper_preview()
            return "making the preview"
        if d == "paper_set":
            self.paper_set()
            return "making the paper set"
        if d == "xrd_app":
            it = self._graphs(a.get("graph"))[0] if a.get("graph") else None
            return self.tools.xrd_app(False, str(getattr(it, "path", "")) if it is not None and str(getattr(it, "path", "")).lower().endswith(".xrdml") else None)
        if d == "own":
            it = self._graphs(a.get("graph"))[0]
            if not isinstance(it, sp.Item):
                raise ValueError("'own' works on a single graph (not a combined figure)")
            cu = {k: a[k] for k in ("x", "ys", "style", "xtitle", "ytitle", "xlog", "xrev", "layout") if k in a and a[k] not in (None, "", [])}
            if cu.get("style") and cu["style"] not in sp.OWN_STYLES:
                raise ValueError(f"'{cu['style']}' is not one of the styles {sp.OWN_STYLES}")
            if cu.get("layout") and cu["layout"] not in sp.OWN_LAYOUTS:
                cu.pop("layout")
            cols = {str(c) for c in (it.det.get("nums") or {})}
            bad = [c for c in ([cu.get("x")] if cu.get("x") else []) + list(cu.get("ys") or []) if str(c) not in cols]
            if bad:
                raise ValueError(f"no column {bad} in this table (its columns: {sorted(cols)[:20]})")
            old = getattr(it, "custom", None)
            it.custom = dict(old or {}, **cu)
            try:
                it.build(self.opt, "XY")
            except Exception as e:
                it.custom = old
                it.build(self.opt, it.kind)
                raise ValueError(f"not drawn that way ({e})")
            self.regroup()
            self.refresh_list()
            self.go(0)
            self.list.setCurrentRow(self.items.index(it))
            return "drawn: " + ", ".join(f"{k}={v}" for k, v in cu.items())
        if d == "thermo_software":
            its = [i for i in self._graphs(a.get("graphs") or "ticked") if isinstance(i, sp.Item)]
            return self.tools.thermo_software(str(a.get("software", "")), str(a.get("database", "")), its)
        if d in ("psd_style", "psd_sizes", "psd_rrsb"):
            if a.get("graphs"):
                self._tick_only([i for i in self._graphs(a.get("graphs")) if isinstance(i, sp.Item)])
            if d == "psd_style":
                st = str(a.get("style", ""))
                st = next((x for x in sp.PSD_STYLES if x.lower().startswith(st.lower()[:10])), sp.PSD_STYLES[0])
                r = self.tools.psd_style(st, self.pages.widget(1))
            else:
                r = (self.tools.psd_sizes if d == "psd_sizes" else self.tools.psd_rrsb)(self.pages.widget(1))
            return r[1] if isinstance(r, tuple) else (r.to_string(index=False) if hasattr(r, "to_string") else r)
        if d in ("thermo_chart", "thermo_extract"):
            if a.get("graphs"):
                self._tick_only([i for i in self._graphs(a.get("graphs")) if isinstance(i, sp.Item)])
            if d == "thermo_chart":
                st = str(a.get("style", ""))
                st = next((c for c in sp.THERMO_CHARTS + [sp.PORE_CHART] if c.lower().startswith(st.lower()[:12])), sp.THERMO_CHARTS[0]) if st else sp.THERMO_CHARTS[0]
                r = self.tools.thermo_chart(st, self.pages.widget(1))
            else:
                r = self.tools.thermo_extract(str(a.get("what", "si")), self.pages.widget(1), sync=True)
            return r[1] if isinstance(r, tuple) else (f"{len(r)} new graph(s)" if isinstance(r, list) else r)
        if d in ("labels_auto", "labels_clear", "ftir_read", "ftir_areas", "group"):
            if a.get("graphs"):
                self._tick_only([i for i in self._graphs(a.get("graphs")) if not isinstance(i, sp.Board)])
            if d == "labels_auto":
                return self.tools.labels_auto({"n": a.get("n", 8), "prom": a.get("prominence", 5), "digits": a.get("digits", 4)}, self.pages.widget(1))
            if d == "labels_clear":
                return self.tools.labels_clear(self.pages.widget(1))
            if d == "ftir_read":
                sig = {"absorbance": "Absorbance", "transmittance": "Transmittance"}.get(str(a.get("signal", "")).lower(), "")
                r = self.tools.ftir_read(sig, self.pages.widget(1))
                return r[1] if isinstance(r, tuple) else r
            if d == "ftir_areas":
                regs = a.get("regions") or []
                txt = "\n".join(f"{r.get('from')}-{r.get('to')} {r.get('name', '')}" if isinstance(r, dict) else str(r) for r in regs)
                r = self.tools.ftir_areas(txt, self.pages.widget(1))
                return r[1] if isinstance(r, tuple) else r.to_string(index=False)
            return self.tools.group("stack" if a.get("how") == "stack" else "overlay", "", self.pages.widget(2))
        if d == "remember":
            t = ai.learn(self.assistant.home, a.get("text", ""))
            return f"remembered: {t}" if t else "already known"
        raise ValueError(f"'{d}' is not an action of this window")

    def _workspace(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(16, 16, 16, 16)
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        h.addWidget(split)
        # Your graphs
        f, lay = self._card()
        head = QHBoxLayout()
        head.addWidget(QLabel("Your graphs", objectName="h2"))
        head.addStretch(1)
        self.count = QLabel("", objectName="soft")
        head.addWidget(self.count)
        lay.addLayout(head)
        tk_ = QHBoxLayout()
        for text, on in (("Tick all", True), ("Untick all", False)):
            b_ = QPushButton(text)
            b_.setStyleSheet("padding: 3px 8px; min-width: 0px;")
            b_.setToolTip("Ctrl+A" if on else "Ctrl+Shift+A")
            b_.clicked.connect(lambda _c=False, on=on: self.tick_all(on))
            tk_.addWidget(b_)
        tk_.addStretch(1)
        lay.addLayout(tk_)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)     # Ctrl / Shift + click selects several graphs (Stack, Overlay … use them)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setWordWrap(True)
        self.list.setTextElideMode(Qt.ElideNone)
        self.list.currentRowChanged.connect(self.show_item)
        self.list.itemChanged.connect(lambda _i: self.update_count())
        lay.addWidget(self.list, 1)
        gr = QHBoxLayout()
        gr.addWidget(QLabel("Group", objectName="soft"))
        self.groupmode = QComboBox()
        self.groupmode.addItems(sp.MODES)
        self.groupmode.setCurrentText(self.cfg.get("mode", sp.MODES[0]) if self.cfg.get("mode") in sp.MODES else sp.MODES[0])
        self.groupmode.setToolTip("How graphs of the same kind are put together in combined figures (★), as 'Several files of the same kind' in the current window")
        self.groupmode.activated.connect(lambda _i: (save_cfg({"mode": self.groupmode.currentText()}), self.regroup(), self.refresh_list()))
        gr.addWidget(self.groupmode, 1)
        lay.addLayout(gr)
        gb = QHBoxLayout()
        for text, how in (("Stack", "stack"), ("Overlay", "overlay")):
            b = QPushButton(text)
            b.setToolTip(f"Your own group: the ticked graphs of one kind in one figure, {'stacked with an offset' if how == 'stack' else 'on common axes'}")
            b.clicked.connect(lambda _c=False, h=how: self.group_ticked(h))
            gb.addWidget(b)
        ub = QPushButton("Ungroup")
        for b_ in [gb.itemAt(k).widget() for k in range(gb.count())] + [ub]:
            b_.setStyleSheet("padding: 4px 6px; min-width: 0px;")
        ub.setToolTip("Remove the group you made that is ticked or on show")
        ub.clicked.connect(self.ungroup)
        gb.addWidget(ub)
        lay.addLayout(gb)
        addb = QPushButton("+ Add data files")
        addb.clicked.connect(self.add_files)
        lay.addWidget(addb)
        hint = QLabel("Combined figures (★) are made for you from graphs of the same kind; ◆ are your own groups.", objectName="soft")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        f.setMinimumWidth(240)
        self.graphs_card = f
        split.addWidget(f)
        # graph
        f, lay = self._card()
        self.gtitle = QLabel("No graph yet", objectName="h2")
        self.gsub = QLabel("", objectName="soft")
        lay.addWidget(self.gtitle)
        lay.addWidget(self.gsub)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        g = QWidget()
        gl = QVBoxLayout(g)
        gl.setContentsMargins(0, 6, 0, 0)
        tools = QHBoxLayout()
        self.modes = QButtonGroup(self)
        self.modes.setExclusive(False)
        for i, label in enumerate(("Zoom", "Pan", "Select range")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.clicked.connect(lambda on, i=i: self.set_mode(i, on))
            self.modes.addButton(b, i)
            tools.addWidget(b)
        reset = QPushButton("Reset axes")
        reset.clicked.connect(self.reset_axes)
        tools.addWidget(reset)
        tools.addStretch(1)
        self.graph_tools = tools
        gl.addLayout(tools)
        self.fig = Figure(figsize=(7.2, 5.0), dpi=100, facecolor="white")
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.navtb = NavigationToolbar2QT(self.canvas, g)
        self.navtb.hide()                                    # the buttons above drive it
        gl.addWidget(self.canvas, 1)
        self.selbar = QFrame(objectName="selbar")
        sb = QHBoxLayout(self.selbar)
        sb.setContentsMargins(10, 6, 10, 6)
        self.seltext = QLabel("")
        sb.addWidget(self.seltext, 1)
        integ = QPushButton("Integrate", objectName="primary")
        integ.clicked.connect(self.integrate)
        sb.addWidget(integ)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear_selection)
        sb.addWidget(clear)
        self.selbar.hide()
        gl.addWidget(self.selbar)
        self.result = QLabel("", objectName="soft")
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        gl.addWidget(self.result)
        self.tabs.addTab(g, "Graph")
        self.datamodel = DataFrameModel()
        dv = self.dataview = QTableView()
        dv.setModel(self.datamodel)
        dv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabs.addTab(dv, "Data")
        self.resmodel = DataFrameModel()
        rv = self.resview = QTableView()
        rv.setModel(self.resmodel)
        rv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        rw = QWidget()
        rl = QVBoxLayout(rw)
        rl.setContentsMargins(0, 6, 0, 0)
        self.notes = QLabel("", objectName="soft")
        self.notes.setWordWrap(True)
        rl.addWidget(self.notes)
        rl.addWidget(rv, 1)
        self.tabs.addTab(rw, "Results")
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setStyleSheet("font-family: Consolas, 'IBM Plex Mono', monospace; font-size: 9pt;")
        self.tabs.addTab(self.details, "Details")
        f.setMinimumWidth(480)
        split.addWidget(f)
        # graph settings, drawing and saving
        f, lay0 = self._card()
        lay0.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("card")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        scroll.setWidget(inner)
        lay0.addWidget(scroll)
        c = self.cfg
        def label(t):
            lay.addWidget(QLabel(t, objectName="soft"))
        def rule():
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet(f"color: {LINE};")
            lay.addWidget(line)
        lay.addWidget(QLabel("Graph settings", objectName="h2"))
        label("Graph type")
        self.kind = QComboBox()
        self.kind.addItems([k for k in sp.KINDS if not k.startswith("Gallery")])
        self.kind.activated.connect(self.change_kind)
        lay.addWidget(self.kind)
        label("Sample name (for the ticked graphs, or the one on show)")
        sr = QHBoxLayout()
        self.sample = QLineEdit()
        self.sample.returnPressed.connect(self.apply_sample)
        sr.addWidget(self.sample, 1)
        sb = QPushButton("Apply")
        sb.clicked.connect(self.apply_sample)
        sr.addWidget(sb)
        lay.addLayout(sr)
        rule()
        lay.addWidget(QLabel("Size and look", objectName="h2"))
        label("Journal")
        self.journal = QComboBox()
        self.journal.addItems(list(sp.JOURNALS))
        j = self.journal.findText(str(c.get("journal", "")))
        self.journal.setCurrentIndex(j if j >= 0 else 0)
        lay.addWidget(self.journal)
        g2 = QHBoxLayout()
        self.width = QLineEdit(str(c.get("pub_width", "Automatic")))
        self.width.setToolTip("Width of the publication files in mm, or Automatic (the journal's column, else your own size)")
        self.curvew = QLineEdit(str(c.get("curve", "1.5")))
        self.axisw = QLineEdit(str(c.get("axis", "1.5")))
        for t, wdg in (("Width (mm)", self.width), ("Curve (pt)", self.curvew), ("Axis (pt)", self.axisw)):
            col = QVBoxLayout()
            col.addWidget(QLabel(t, objectName="soft"))
            col.addWidget(wdg)
            g2.addLayout(col)
        lay.addLayout(g2)
        for wdg in (self.curvew, self.axisw):
            wdg.editingFinished.connect(self.look_changed)
        # page and letters: orientation, letter size, weight and colour, the colour of black curves
        g3 = QHBoxLayout()
        self.orient = QComboBox(); self.orient.addItems(sp.ORIENTATIONS)
        self.orient.setCurrentText(str(c.get("orientation") or sp.ORIENTATIONS[0]))
        self.orient.setToolTip("Landscape or portrait page for the figures (stacked patterns and panels, sample pages, publication files)")
        self.fscale = QComboBox(); self.fscale.addItems(["80 %", "90 %", "100 %", "110 %", "120 %", "135 %", "150 %"]); self.fscale.setEditable(True)
        self.fscale.setCurrentText(str(c.get("font_scale_pct") or "100 %"))
        self.fscale.setToolTip("Size of all letters (axis titles, numbers, peak labels), relative to the app's sizes")
        self.fweight = QComboBox(); self.fweight.addItems(sp.FONT_WEIGHTS)
        self.fweight.setCurrentText(str(c.get("font_weight") or sp.FONT_WEIGHTS[0]))
        for t, wdg in (("Orientation", self.orient), ("Letters", self.fscale)):
            col = QVBoxLayout(); col.addWidget(QLabel(t, objectName="soft")); col.addWidget(wdg); g3.addLayout(col)
        lay.addLayout(g3)
        g5 = QHBoxLayout()                                   # two fields a row: nothing is cut off in a narrow panel
        g4 = QHBoxLayout()
        self.tcolour = QComboBox(); self.tcolour.addItems(list(sp.COLOUR_CHOICES)); self.tcolour.setEditable(True)
        self.tcolour.setCurrentText(str(c.get("text_colour") or "Automatic"))
        self.tcolour.setToolTip("Colour of the black text (axis titles, numbers, names). Coloured labels keep their colours. Or type #rrggbb.")
        self.ccolour = QComboBox(); self.ccolour.addItems(list(sp.COLOUR_CHOICES)); self.ccolour.setEditable(True)
        self.ccolour.setCurrentText(str(c.get("curve_colour") or "Automatic"))
        self.ccolour.setToolTip("Colour of the curves the app draws black (single graphs, observed patterns). Coloured curves keep their colours. Or type #rrggbb.")
        for t, wdg, row_ in (("Font weight", self.fweight, g5), ("Text colour", self.tcolour, g5), ("Line colour", self.ccolour, g4)):
            col = QVBoxLayout(); col.addWidget(QLabel(t, objectName="soft")); col.addWidget(wdg); row_.addLayout(col)
        g4.addStretch(1)
        lay.addLayout(g5); lay.addLayout(g4)
        for cb in (self.orient, self.fweight, self.tcolour, self.ccolour, self.fscale):
            cb.activated.connect(lambda *_: self.look_changed())
        for cb in (self.tcolour, self.ccolour, self.fscale):
            cb.lineEdit().editingFinished.connect(self.look_changed)
        self.set_look()
        rule()
        lay.addWidget(QLabel("Files", objectName="h2"))
        self.png = QCheckBox("PNG from Origin")
        self.png.setChecked(bool(c.get("png", True)))
        self.pdf = QCheckBox("PDF from Origin")
        self.pdf.setChecked(bool(c.get("pdf", True)))
        self.pub = QCheckBox("Publication files (PNG 600 dpi, TIFF, PDF, SVG)")
        self.pub.setChecked(bool(c.get("pub", True)))
        self.keep = QCheckBox("Keep Origin open afterwards")
        self.keep.setChecked(bool(c.get("keep", True)))
        self.dated = QCheckBox("A new dated folder for every run")
        self.dated.setChecked(bool(c.get("dated", False)))
        for cb in (self.png, self.pdf, self.pub, self.keep, self.dated):
            lay.addWidget(cb)
        label("Results folder")
        fr = QHBoxLayout()
        self.outdir = QLineEdit(str(c.get("out") or ""))
        self.outdir.setPlaceholderText("the app's results folder")
        fr.addWidget(self.outdir, 1)
        br = QPushButton("…")
        br.setToolTip("Choose the results folder")
        br.clicked.connect(self.choose_out)
        fr.addWidget(br)
        lay.addLayout(fr)
        label("Origin project name")
        self.project = QLineEdit(str(c.get("project", "My_graphs")))
        lay.addWidget(self.project)
        rule()
        self.b_draw = QPushButton("Draw ticked in Origin", objectName="accent")
        self.b_draw.clicked.connect(lambda: self.draw_origin("ticked"))
        self.b_all = QPushButton("Draw all in Origin")
        self.b_all.clicked.connect(lambda: self.draw_origin("all"))
        self.b_save = QPushButton("Save this graph (PNG · TIFF · PDF · SVG)")
        self.b_save.clicked.connect(self.save_current)
        self.b_board = QPushButton("Figure from the ticked graphs (panels a, b …)")
        self.b_board.clicked.connect(self.make_board)
        self.b_open = QPushButton("Open results folder")
        self.b_open.clicked.connect(self.open_results)
        for b_ in (self.b_draw, self.b_all, self.b_save, self.b_board, self.b_open):
            lay.addWidget(b_)
        rule()
        lay.addWidget(QLabel("Paper set", objectName="h2"))
        label("Samples in the main text (the rest go to the supplementary)")
        self.pmain = QLineEdit(str(c.get("paper_main") or sp.PAPER_MAIN))
        lay.addWidget(self.pmain)
        self.b_prev = QPushButton("Preview paper set (PDF)")
        self.b_prev.clicked.connect(self.paper_preview)
        self.b_paper = QPushButton("Make paper set")
        self.b_paper.clicked.connect(self.paper_set)
        lay.addWidget(self.b_prev)
        lay.addWidget(self.b_paper)
        self.b_cancel = QPushButton("Stop after the current graph")
        self.b_cancel.clicked.connect(lambda: (self.cancel.__setitem__(0, True), self.set_status("Stopping after the current graph …")))
        self.b_cancel.hide()
        lay.addWidget(self.b_cancel)
        lay.addStretch(1)
        f.setMinimumWidth(280)
        self.settings_card = f
        split.addWidget(f)
        # the panels: Your graphs and Graph settings can be moved to any side, floated as windows (minimise, maximise), or closed
        cards = [split.widget(i) for i in range(split.count())]
        h.removeWidget(split)
        inner = QMainWindow()
        inner.setObjectName("workspaceMain")
        inner.setDockNestingEnabled(True)
        inner.setCentralWidget(cards[1])
        self.graphs_dock = self._panel_dock("Your graphs", "graphsDock", cards[0], Qt.LeftDockWidgetArea, inner)
        self.settings_dock = self._panel_dock("Graph settings", "settingsDock", cards[2], Qt.RightDockWidgetArea, inner)
        inner.resizeDocks([self.graphs_dock, self.settings_dock], [280, 380], Qt.Horizontal)
        split.setParent(None)
        split.deleteLater()
        h.addWidget(inner)
        self.wsmain = inner
        return w

    def _panel_dock(self, title, name, widget, area, win):
        from PySide6.QtWidgets import QDockWidget
        d = QDockWidget("⠿  " + title, win)
        d.setObjectName(name)
        d.setWidget(widget)
        d.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        d.setToolTip("Drag the title bar (the ⠿ strip) to move this panel: drop it on another side, or on another panel to make tabs. Double click the title to float it or put it back")
        win.addDockWidget(area, d)
        d.topLevelChanged.connect(lambda floating, d=d: self._float_window(d, floating))
        try: self._panel_titlebar(d, title)
        except Exception: pass
        return d

    def _panel_titlebar(self, d, title):
        """The title strip of a panel: its name (drag it to move the panel) and three clear buttons - fold, float, close."""
        from PySide6.QtWidgets import QToolButton
        bar = QWidget(objectName="paneltitle"); h = QHBoxLayout(bar); h.setContentsMargins(10, 3, 4, 3); h.setSpacing(2)
        lab = QLabel("⠿  " + title, objectName="paneltitlelabel"); lab.setToolTip("Drag here to move the panel: drop it on another side, or on another panel to make tabs"); h.addWidget(lab, 1)
        def btn(text, tip, fn):
            b = QToolButton(objectName="panelbtn"); b.setText(text); b.setToolTip(tip); b.setStatusTip(tip); b.setAutoRaise(True); b.setFixedSize(26, 22); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(fn); h.addWidget(b); return b
        def fold():
            w_ = d.widget(); on = not w_.isVisible(); w_.setVisible(on); d._folded = not on
            d.setMaximumHeight(16777215 if on else bar.sizeHint().height() + 6); d.fold_btn.setText("▾" if on else "▸"); d.fold_btn.setToolTip(f"Fold {title} away (only its title stays)" if on else f"Unfold {title}")
        d.fold_btn = btn("▾", f"Fold {title} away (only its title stays)", fold); d.fold = fold
        d.float_btn = btn("⧉", f"Float {title} as a loose panel, or put it back (double click on the title does the same)", lambda: d.setFloating(not d.isFloating()))
        d.close_btn = btn("✕", f"Close {title}. Bring it back with View ▸ Panels", d.close)
        bar.setStyleSheet("#paneltitle { background: #E7EEF7; border-bottom: 1px solid #D8E1EC; } #paneltitlelabel { font-weight: 600; color: #17324D; } "
                          "#panelbtn { border: 0; border-radius: 4px; font-size: 11pt; color: #17324D; } #panelbtn:hover { background: #C9D9EE; }")
        d.setTitleBarWidget(bar)

    def _float_window(self, d, floating):
        """A panel that you DRAG stays a panel: it floats while you move it and docks where you drop it (another side, or on
        another panel to make tabs). Only 'as its own window' (View menu) makes it a normal window with minimise / maximise.
        (Making every floating panel a window at once stopped the drag: a panel could not be moved to another side.)"""
        if not floating:
            d._popped = False; return
        if getattr(d, "_as_window", False) and not getattr(d, "_popped", False):
            d._popped = True; d._as_window = False
            d.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint | Qt.WindowTitleHint)
            d.show()

    def panel_as_window(self, d):
        """View > '… as its own window': a normal window (minimise, maximise). 'Put the panels back in place' docks it again."""
        d._as_window = True; d._popped = False; d.show()
        if d.isFloating(): self._float_window(d, True)
        else: d.setFloating(True)
        d.raise_()

    def dock_back(self):
        """Every panel back in its place: Your graphs left, Graph settings and the assistant right."""
        for d, win, area in ((self.graphs_dock, self.wsmain, Qt.LeftDockWidgetArea), (self.settings_dock, self.wsmain, Qt.RightDockWidgetArea),
                             (self.dock, self, Qt.RightDockWidgetArea)):
            d._popped = False
            if d.isFloating() or d.isWindow():
                d.setFloating(False)
            win.addDockWidget(area, d)
            if d is not self.dock:
                d.show()
        self.wsmain.resizeDocks([self.graphs_dock, self.settings_dock], [280, 380], Qt.Horizontal)
        self.set_status("Panels back in place.")

    # ------------------------------------------------------------------ data
    def add_files(self, tick=False):
        """Choose data files; they come to Your graphs (ticked when added from a tool page or the assistant, so the tool works on them)."""
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose your data files", str(Path.home()),
                                                "Data files (*.xlsx *.xlsm *.xls *.csv *.txt *.dat *.xy *.xrdml *.brml *.ras *.uxd *.spa *.ngb-ds3 *.ngb-ss3 *.sel *.res *.out);;All files (*.*)")
        if paths:
            self.load(paths, tick=tick)
        return paths

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        """Files dropped anywhere on the window come to Your graphs, ticked."""
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
        if paths:
            self.load(paths, tick=True)
            e.acceptProposedAction()

    def load(self, paths, tick=False):
        if self.thread is not None:
            self.set_status("Still reading the previous files: add these again in a moment.")
            return
        if tick:
            self.tick_paths |= {os.path.abspath(p) for p in paths}
        self.busy_on(f"Reading {len(paths)} file(s)")
        self.set_status(f"Reading {len(paths)} file(s) …")
        self.thread = QThread(self)
        self.loader = Loader(paths, self.opt, self.singles)
        self.loader.moveToThread(self.thread)
        self.thread.started.connect(self.loader.run)
        self.loader.done.connect(self.loaded)
        self.loader.done.connect(self.thread.quit)
        self.thread.finished.connect(self._thread_done)
        self.thread.start()

    def _thread_done(self):
        self.thread = None
        if self.job_thread is None:
            self.busy_off()

    def loaded(self, items, msgs):
        self.singles += items
        for m_ in msgs:
            self.log(m_)
        msgs += self.regroup()
        try:                                                  # thermal analysis files (TG + DSC together): a page per sample and a comparison
            nb = sp.auto_boards(self.singles, self.combined, self.boards)
            if nb:
                self.boards += nb
                msgs.append(f"{len(nb)} thermal-analysis figure(s) made for you: " + ", ".join(b.name for b in nb))
        except Exception as e:
            self.log(f"!! thermal-analysis figures not made: {e}")
        self.refresh_list()
        self.set_status(f"{len(items)} graph(s) read." + (" " + " ".join(m.strip() for m in msgs[:2]) if msgs else ""))
        if self.items and self.list.currentRow() < 0:
            self.list.setCurrentRow(0)
        elif not self.items:
            self.show_empty()

    def regroup(self):
        """Combined figures again: the app's (mode of the Group list, the same make_groups as the current window) and yours."""
        msgs = []
        mode = self.groupmode.currentText() if hasattr(self, "groupmode") else "Decide for me"
        try:
            groups, _why = sp.make_groups(self.singles, mode, self.opt)
            for g in groups:
                g.fmt = getattr(self, "group_fmt", {}).get(tuple(sp.key_of(m) for m in g.members)) or {}      # your look of this figure stays
                g.build(self.opt)
        except Exception as e:
            msgs.append(f"combined figures not made ({e})")
            groups = []
        mine = []
        by_key = {sp.key_of(it): it for it in self.singles}
        for how, keys in self.user_groups:
            mem = [by_key[k] for k in keys if k in by_key]
            if len(mem) < 2:
                continue
            try:
                c = sp.Combined(mem, how, {"stack": "stacked with an offset, as you grouped them", "panels": "one panel each, as you grouped them"}.get(how, "overlaid on common axes, as you grouped them"), "", None, self.opt)
                c.fmt = getattr(self, "group_fmt", {}).get(tuple(sp.key_of(m) for m in mem)) or {}
                c.build()
                c.mine = True
                mine.append(c)
            except Exception as e:
                msgs.append(f"your group of {len(mem)} {mem[0].kind} graphs: not drawn ({e})")
        self.combined = mine + groups
        return msgs

    def group_ticked(self, how):
        its = [i for i in self.ticked() if isinstance(i, sp.Item) and i in self.singles]
        if len(its) < 2:                                              # graphs selected in the list (click, Ctrl / Shift + click) count too
            sel = [self.items[self.list.row(li)] for li in self.list.selectedItems() if 0 <= self.list.row(li) < len(self.items)]
            sel = [i for i in sel if isinstance(i, sp.Item) and i in self.singles]
            if len(sel) >= 2:
                its = sel; self._tick_only(sel)
        if len(its) < 2:
            self.set_status("Tick (or select with Ctrl / Shift + click) two or more single graphs (without a star) to group them.")
            return "too few"
        kinds = {i.kind for i in its}
        if len(kinds) > 1:
            self.set_status("A group holds graphs of one kind: you ticked " + ", ".join(sorted(kinds)) + ". Tick graphs of one kind.")
            return "mixed"
        self.user_groups.append((how, [sp.key_of(i) for i in its]))
        msgs = self.regroup()
        if its[0].kind == "FTIR":
            ys = {str(((i.spec or {}).get("panels") or [{}])[0].get("yname", "")).split("(")[0].strip().lower() for i in its}
            if len(ys) > 1:
                msgs.insert(0, "Note: these spectra mix " + " and ".join(sorted(ys)) + "; convert one with Analysis > FTIR first so they share one axis.")
        self.refresh_list()
        row = next((r for r, it in enumerate(self.items) if getattr(it, "mine", False)), 0)
        self.go(0)                                                    # the preview of the new figure, in Workspace; Origin does the final work
        self.list.setCurrentRow(row)
        self.set_status(f"Your group: {len(its)} {its[0].kind} graphs " + {"stack": "stacked.", "panels": "one panel each."}.get(how, "overlaid.") + (" " + msgs[0] if msgs else ""))
        return "grouped"

    def ungroup(self):
        cands = [i for i in self.ticked() + [self.current()] if getattr(i, "mine", False)]
        if not cands:
            self.set_status("Tick or show one of your own groups (◆) to ungroup it.")
            return "none"
        keys = {tuple(sp.key_of(m) for m in c.members) for c in cands}
        self.user_groups = [g for g in self.user_groups if tuple(k for k in g[1]) not in keys]
        self.regroup()
        self.refresh_list()
        self.set_status("Group removed; the graphs stay in Your graphs.")
        return "ungrouped"

    def refresh_list(self):
        keep = {id(it) for it in self.ticked()} if self.list.count() == len(self.items) else set()     # ticks stay when the list is rebuilt
        pool = list(self.combined) + list(self.singles)
        self.boards = [b for b in self.boards if b.resolve(pool)]
        for b in self.boards:
            b.build()
        self.items = list(self.boards) + pool
        names = sp.display_names(self.singles) if self.singles else []
        self.list.blockSignals(True)
        self.list.clear()
        for b in self.boards:
            li = QListWidgetItem(f"{b.title}\nPanel figure")
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Unchecked)
            self.list.addItem(li)
        for it in self.combined:
            mine = getattr(it, "mine", False)
            li = QListWidgetItem(f"{'◆' if mine else '★'} {it.title.replace('★ Combined: ', '').strip()}\n{'Your group' if mine else 'Combined'} · {it.kind} · {it.how}")
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Unchecked)
            self.list.addItem(li)
        for it, nm in zip(self.singles, names):
            li = QListWidgetItem(f"{nm}\n{it.kind} · {Path(getattr(it, 'path', '') or '').name}")
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Unchecked)
            self.list.addItem(li)
        for i, it in enumerate(self.items):
            self.list.item(i).setData(Qt.UserRole + 1, it)           # the graph of each row (dragging rows changes the order)
        newly = {os.path.abspath(str(getattr(it, "path", "") or "")) for it in self.items} & self.tick_paths
        for i, it in enumerate(self.items):
            p = os.path.abspath(str(getattr(it, "path", "") or "")) if isinstance(it, sp.Item) else ""
            if id(it) in keep or (p and p in newly):
                self.list.item(i).setCheckState(Qt.Checked)
        self.tick_paths -= newly
        self.list.blockSignals(False)
        self.update_count()
        self.filter_graphs(self.search.text())

    def update_count(self):
        n = self.list.count()
        t = sum(1 for i in range(n) if self.list.item(i).checkState() == Qt.Checked)
        self.count.setText(f"{n} graph{'s' if n != 1 else ''} · {t} ticked")

    def ticked(self):
        return [self.items[i] for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.Checked]

    def filter_graphs(self, text):
        t = text.strip().lower()
        for i in range(self.list.count()):
            self.list.item(i).setHidden(bool(t) and t not in self.list.item(i).text().lower())

    # ------------------------------------------------------------------ graph
    def show_empty(self):
        self.fig.clear()
        self.fig.text(0.5, 0.5, "Add data files (Ctrl+O) or open this window from Origin Plot Studio\nwith graphs in Your graphs.",
                      ha="center", va="center", fontsize=11, color=SOFT)
        self.canvas.draw_idle()
        self.gtitle.setText("No graph yet")
        self.gsub.setText("")

    def current(self):
        i = self.list.currentRow()
        return self.items[i] if 0 <= i < len(self.items) else None

    def show_item(self, i):
        it = self.current()
        if it is None:
            return
        self.clear_selection()
        nm = self.list.item(i).text().split("\n")[0]
        self.gtitle.setText(nm)
        kind_ = getattr(it, "kind", "") or "Panel figure"
        self.gsub.setText(f"{kind_} · " + ("drawn as one figure with panels a, b …" if isinstance(it, sp.Board) else (Path(getattr(it, 'path', '') or '').name or 'combined figure')))
        self.sample.setText(getattr(it, "sample", "") or nm.lstrip("★ ") if isinstance(it, sp.Item) else "")
        k = self.kind.findText(kind_)
        self.kind.setEnabled(isinstance(it, sp.Item) and k >= 0)
        if k >= 0:
            self.kind.setCurrentIndex(k)
        self.draw()
        self.datamodel.set(self.table_of(it))
        self.resmodel.set(getattr(it, "results", None))
        rec = (getattr(it, "record", None) or []) + ["note: " + w for w in (getattr(it, "warnings", None) or [])]
        self.notes.setText("\n".join(str(r) for r in rec[:8]))
        self.set_status(f"Showing {nm}. Drag with Zoom or Pan; Select range marks a region to integrate.")

    def table_of(self, it):
        """The graph's numbers as a table (the engine keeps them as a DataFrame in _df, or as columns in nums)."""
        import pandas as pd
        if not isinstance(it, sp.Item):
            return None
        d = it.det
        if isinstance(d.get("_df"), pd.DataFrame):
            return d["_df"]
        n = d.get("nums")
        if isinstance(n, pd.DataFrame):
            return n
        try:
            return pd.DataFrame(n) if isinstance(n, dict) else None
        except Exception:
            return None

    def draw(self):
        it = self.current()
        if it is None or (getattr(it, "spec", None) is None and not isinstance(it, sp.Board)):
            return
        try:
            if isinstance(it, sp.Board):
                sp.board_figure(it, self.fig, self.num(self.curvew, 1.5), self.num(self.axisw, 1.5))
            else:
                sp.preview_figure(it.spec, fig=self.fig, curve_w=self.num(self.curvew, 1.5), axis_w=self.num(self.axisw, 1.5))
        except Exception as e:
            self.fig.clear()
            self.fig.text(0.5, 0.5, f"This graph could not be drawn:\n{e}", ha="center", va="center", color="#8B1E28")
        self.canvas.draw_idle()
        self.navtb.update()                                  # new graph: Reset goes back to this view
        self.navtb.push_current()
        if self.modes.button(2).isChecked():
            self.arm_span()

    def change_kind(self, _i):
        it = self.current()
        if not isinstance(it, sp.Item):
            return
        kind = self.kind.currentText()
        try:
            it.build(self.opt, kind)
            li = self.list.currentItem()
            li.setText(li.text().split("\n")[0] + f"\n{it.kind} · {Path(getattr(it, 'path', '') or '').name}")
            self.set_status(f"Drawn as {kind}.")
        except Exception as e:
            self.set_status(f"Could not draw it as {kind}: {e}")
        self.show_item(self.list.currentRow())

    def set_mode(self, i, on):
        for j in range(3):
            if j != i:
                self.modes.button(j).setChecked(False)
        if self.navtb.mode:                                   # leave matplotlib's zoom/pan mode first
            (self.navtb.zoom if "rect" in str(self.navtb.mode) else self.navtb.pan)()      # "zoom rect" or "pan/zoom"
        if self.span is not None:
            self.span.set_active(False)
            self.span = None
        if on and i == 0:
            self.navtb.zoom()
        elif on and i == 1:
            self.navtb.pan()
        elif on and i == 2:
            self.arm_span()

    def arm_span(self):
        if not self.fig.axes:
            return
        self.span = SpanSelector(self.fig.axes[0], self.on_span, "horizontal", useblit=True, interactive=True,
                                 props=dict(alpha=0.12, facecolor=BLUE))

    def on_span(self, a, b):
        if abs(b - a) <= 0:
            return
        self.sel = (min(a, b), max(a, b))
        self.seltext.setText(f"Selected {self.sel[0]:.6g} to {self.sel[1]:.6g}")
        self.selbar.show()

    def clear_selection(self):
        self.sel = None
        self.selbar.hide()
        self.result.setText("")
        if self.span is not None:
            try:
                self.span.clear()
            except Exception:
                pass

    def reset_axes(self):
        self.navtb.home()

    def curves(self, it):
        """The visible curves of the graph's first panel, as the Analysis menu reads them."""
        import analysis_tools as at
        if not getattr(it, "spec", None):
            return []
        p0 = (it.spec or {}).get("panels", [{}])[0]
        out = []
        for c in p0.get("curves", []):
            if not str(c.get("label", "")).startswith("_") and len(c.get("x", [])) > 2:
                out.append(at.Curve(str(c.get("label", "")), c["x"], c["y"], str(it.spec.get("xname") or "x"), str(p0.get("yname") or "y")))
        return out

    def integrate(self):
        it = self.current()
        if it is None or self.sel is None:
            return
        import analysis_tools as at
        lines = []
        for c in self.curves(it):
            try:
                r = at.area_between(c, x_from=self.sel[0], x_to=self.sel[1])
                row = r.table.iloc[0]
                lines.append(f"{c.name or it.kind}: area {row['Area']:.6g} over {int(row['Points'])} points")
            except Exception as e:
                lines.append(f"{c.name or it.kind}: {e}")
        self.result.setText(f"Integrated from {self.sel[0]:.6g} to {self.sel[1]:.6g} (trapezoidal rule, the points inside the range; "
                            "same as Analysis > Calculus > Area):\n" + "\n".join(lines[:6]))
        self.set_status("Integration done.")
        self.last_integration = lines

    # ------------------------------------------------------------------ step 2: names, drawing, saving, paper set
    def num(self, w, d):
        try:
            return max(0.1, float(str(w.text()).replace(",", ".")))
        except Exception:
            return d

    def pub_width(self):
        try:
            return min(400.0, max(50.0, float(self.width.text().replace(",", "."))))
        except Exception:
            return None                                       # Automatic

    def style(self):
        import origin_plot_app as opa
        c = self.cfg
        def f(k, d):
            try:
                return max(0.1, float(str(c.get(k, d)).replace(",", ".")))
            except Exception:
                return d
        return opa.Style(self.num(self.curvew, 1.5), self.num(self.axisw, 1.5), f("tick", 0.75), f("zoom_curve", 3.8), f("zoom_label", 24), f("zoom_axis", 3.8))

    def set_look(self):
        """Size and look into the engine (preview, publication files and Origin read sp.LOOK)."""
        import re as _re
        try:
            pct = float(_re.sub(r"[^0-9.,]", "", self.fscale.currentText()).replace(",", ".") or 100)
        except ValueError:
            pct = 100.0
        sp.LOOK.update(font_weight=self.fweight.currentText(), text_colour=self.tcolour.currentText().strip() or "Automatic",
                       curve_colour=self.ccolour.currentText().strip() or "Automatic", font_scale=min(2.5, max(0.5, pct / 100.0)))
        return dict(sp.LOOK)

    def look_changed(self):
        """A change under Size and look: saved, and the graphs redrawn (the orientation changes how pages are built)."""
        look = self.set_look()
        ch = {"orientation": self.orient.currentText(), "font_weight": look["font_weight"], "text_colour": look["text_colour"],
              "curve_colour": look["curve_colour"], "font_scale_pct": self.fscale.currentText(), "curve": self.curvew.text().strip(), "axis": self.axisw.text().strip()}
        bad = [n for n, v in (("text colour", look["text_colour"]), ("line colour", look["curve_colour"])) if v != "Automatic" and sp.look_colour(v) is None]
        save_cfg(ch); self.cfg.update(ch)
        if self.opt.get("orientation") != ch["orientation"]:
            self.opt = options()
            with self.busy_while("Redrawing the graphs for the new page orientation"):
                for it in self.singles:
                    try:
                        it.build(self.opt, it.kind)
                    except Exception as e:
                        self.log(f"   {it.title.strip()}: not redrawn ({e})")
                self.regroup()
                row = self.list.currentRow(); self.refresh_list()
                if 0 <= row < self.list.count():
                    self.list.setCurrentRow(row)
        self.draw()
        self.set_status("Size and look: " + f"{ch['orientation'].lower()}, letters {self.fscale.currentText()}, {look['font_weight'].split(' (')[0].lower()}, text {look['text_colour'].lower()}, lines {look['curve_colour'].lower()}"
                        + (f". Not a colour: {', '.join(bad)} (choose one from the list or type #rrggbb)" if bad else "") + ".")
        return look

    def remember(self):
        changes = {"journal": self.journal.currentText(), "pub_width": self.width.text().strip() or "Automatic", "curve": self.curvew.text().strip(),
                   "axis": self.axisw.text().strip(), "png": self.png.isChecked(), "pdf": self.pdf.isChecked(), "pub": self.pub.isChecked(),
                   "keep": self.keep.isChecked(), "dated": self.dated.isChecked(), "out": self.outdir.text().strip(),
                   "project": self.project.text().strip() or "My_graphs", "paper_main": self.pmain.text().strip()}
        self.cfg.update(changes)
        save_cfg(changes)

    def run_folder(self):
        import datetime
        import origin_plot_app as opa
        p = self.outdir.text().strip() or opa.default_results_folder()
        return os.path.join(p, datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")) if self.dated.isChecked() else p

    def project_name(self):
        import re
        return re.sub(r'[\\/:*?"<>|]', "_", self.project.text().strip()) or "My_graphs"

    def settings_now(self):
        return {"several files of the same kind": "Decide for me", "curve weight (pt)": self.num(self.curvew, 1.5), "axis weight (pt)": self.num(self.axisw, 1.5),
                "journal template": self.journal.currentText(), "drawn from": "modern window"}

    def choose_out(self):
        p = QFileDialog.getExistingDirectory(self, "Results folder", self.outdir.text() or str(Path.home()))
        if p:
            self.outdir.setText(p)

    def open_results(self):
        import origin_plot_app as opa
        p = self.outdir.text().strip() or opa.default_results_folder()
        os.makedirs(p, exist_ok=True)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def log(self, text):
        self.details.appendPlainText(str(text))

    def apply_sample(self):
        name = self.sample.text().strip()
        chosen = [it for it in self.ticked() if isinstance(it, sp.Item)] or [it for it in [self.current()] if isinstance(it, sp.Item)]
        if not chosen:
            self.set_status("Tick one or more single graphs (without a star) first, then type the sample name.")
            return
        keep = sp.key_of(chosen[0])
        for it in chosen:
            it.sample = name
        self.regroup()
        self.refresh_list()
        row = next((i for i, it in enumerate(self.items) if sp.key_of(it) == keep), 0)
        self.list.setCurrentRow(row)
        self.set_status(f"{len(chosen)} graph(s) now belong to the sample '{name}'.")

    def make_board(self):
        chosen = [it for it in self.ticked() if not isinstance(it, sp.Board)][:9]
        if not chosen:
            self.set_status("Tick the graphs for the figure first.")
            return
        w = self.pub_width() or 175.0
        b = sp.Board([sp.key_of(c) for c in chosen], 0, w, max([b.number for b in self.boards] + [0]) + 1)
        self.boards.append(b)
        self.refresh_list()
        self.list.setCurrentRow(self.items.index(b))
        self.set_status(f"{b.name} made from {len(chosen)} graph(s). Tick it and draw it, or save it.")

    def busy(self):
        if self.job_thread is not None:
            self.set_status("Still working on the previous job: wait for it, or press Stop.")
            return True
        return False

    def start_job(self, work, what, after=None):
        self.cancel[0] = False
        self.details.appendPlainText(f"--- {what}")
        self.job_thread = QThread(self)
        self.job = Job(work)
        self.job.moveToThread(self.job_thread)
        self.job_thread.started.connect(self.job.run)
        self.job.line.connect(self.log)
        self.job.progress.connect(self.set_status)
        self._after = after
        self.job.done.connect(self._job_finished)            # a method of this window: runs on the window's thread (a lambda would not)
        self.job.failed.connect(self.job_failed)
        self.job.done.connect(self.job_thread.quit)
        self.job.failed.connect(self.job_thread.quit)
        self.job_thread.finished.connect(self._job_thread_done)
        for b_ in (self.b_draw, self.b_all, self.b_paper, self.b_prev, self.b_save):
            b_.setEnabled(False)
        self.b_cancel.show()
        self.busy_on(what)
        self.set_status(what + " …")
        self.job_thread.start()

    def _job_thread_done(self):
        self.job_thread = None
        self.busy_off()
        for b_ in (self.b_draw, self.b_all, self.b_paper, self.b_prev, self.b_save):
            b_.setEnabled(True)
        self.b_cancel.hide()

    def _job_finished(self, r):
        self.job_done(r, self._after)

    def job_done(self, r, after):
        self.last_job = r
        if after:
            after(r)

    def job_failed(self, msg):
        self.log("!! " + msg)
        self.set_status("That did not work: see the Details tab.")
        self.tabs.setCurrentWidget(self.details)

    def draw_origin(self, which):
        if self.busy():
            return
        if not self.items:
            self.set_status("Add a file first.")
            return
        chosen = self.ticked() if which == "ticked" else list(self.items)
        if not chosen:
            self.set_status("No graph is ticked. Tick the graphs you want, or press Draw all in Origin.")
            return
        self.remember()
        folder, st, journal, pw = self.run_folder(), self.style(), self.journal.currentText(), self.pub_width()
        png, pdf, keep, pub, project = self.png.isChecked(), self.pdf.isChecked(), self.keep.isChecked(), self.pub.isChecked(), self.project_name()
        settings = self.settings_now()
        session = sp.session_dump(self.singles, self.boards, settings)
        def work(log, progress):
            import origin_plot_app as opa
            return opa.run_items(chosen, folder, log, st, png=png, pdf=pdf, keep_open=keep, project=project, settings=settings, session=session,
                                 stop=lambda: self.cancel[0], pub=pub, pub_width=pw, journal=journal,
                                 progress=lambda i, m, nm: progress(f"Drawing graph {i} of {m} in Origin: {nm}"))
        def after(drv):
            r = (getattr(drv, "result", None) or {}) if drv is not None else {}
            self.set_status((r.get("text") or "Done.").split("\n")[0] + f"  Files in {getattr(drv, 'out', folder)}")
            self.last_folder = getattr(drv, "out", folder)
        self.start_job(work, f"Drawing {len(chosen)} graph(s) in Origin", after)

    def save_current(self):
        it = self.current()
        if it is None:
            self.set_status("Click a graph first.")
            return
        if self.busy():
            return
        self.remember()
        folder, st, journal, pw = self.run_folder(), self.style(), self.journal.currentText(), self.pub_width()
        def work(log, progress):
            import origin_plot_app as opa
            pubdir = os.path.join(folder, "publication")
            os.makedirs(pubdir, exist_ok=True)
            if isinstance(it, sp.Board):
                it.build()
                files = sp.export_board(it, pubdir, st.curve, st.axis, True, True)
                log(f"{it.name}: " + ", ".join(os.path.basename(f) for f in files))
                return pubdir, files
            ja, _col = sp.journal_args(it, journal) if journal else ({}, "")
            if pw:
                ja["width_mm"] = pw
            fl, size = sp.export_publication(it, pubdir, ja.pop("width_mm", None), st.curve, st.axis, name=opa.tag_of(it), **ja)
            log(f"{it.title.strip()}: {size[0]:.0f} x {size[1]:.0f} mm: " + ", ".join(fl))
            return pubdir, fl
        def after(r):
            self.set_status(f"Saved: {len([f for f in r[1] if not str(f).startswith('(')])} file(s) in {r[0]}")
            self.last_folder = r[0]
        self.start_job(work, "Saving the publication files of the graph on show", after)

    def paper_set(self):
        if self.busy():
            return
        if not self.singles:
            self.set_status("Add your data first.")
            return
        self.remember()
        folder = os.path.join(self.run_folder(), "Paper_set")
        st, journal, pw, main = self.style(), self.journal.currentText(), self.pub_width(), self.pmain.text().strip()
        png, pdf, keep, project = self.png.isChecked(), self.pdf.isChecked(), self.keep.isChecked(), self.project_name()
        settings = self.settings_now()
        settings["paper set, sample pages in the main text"] = main
        singles, opt = list(self.singles), self.opt
        def work(log, progress):
            import origin_plot_app as opa
            return opa.run_paper(singles, opt, main, folder, log, style=st, png=png, pdf=pdf, keep_open=keep, project=project, settings=settings,
                                 stop=lambda: self.cancel[0], pub=True, pub_width=pw, journal=journal,
                                 progress=lambda i, m, nm: progress(f"Paper set: drawing graph {i} of {m} in Origin: {nm}"))
        def after(drv):
            r = (getattr(drv, "result", None) or {}) if drv is not None else {}
            self.set_status((r.get("text") or "Paper set done.").split("\n")[0] + f"  Files in {folder}")
            self.last_folder = folder
        self.start_job(work, "Making the paper set", after)

    def paper_preview(self):
        if self.busy():
            return
        if not self.singles:
            self.set_status("Add your data first.")
            return
        self.remember()
        path = os.path.join(self.run_folder(), "Paper_set", "Paper_set_preview.pdf")
        singles, opt, main, journal, cw, aw = list(self.singles), self.opt, self.pmain.text().strip(), self.journal.currentText(), self.num(self.curvew, 1.5), self.num(self.axisw, 1.5)
        def work(log, progress):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            plan = sp.paper_preview(singles, opt, main, journal, path, cw, aw)
            for line_ in plan or []:
                log(line_)
            return plan
        def after(plan):
            self.set_status("Preview written: " + path)
            self.last_preview = path
            if plan and os.path.exists(path):
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices
                if not os.environ.get("OPS_NO_OPEN"):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.start_job(work, "Making the preview of the paper set (nothing is drawn in Origin)", after)

    def closeEvent(self, e):
        try:
            self.remember()
        except Exception:
            pass
        try:
            self.autosave()                                    # File > Resume last session brings the list back (in either window)
        except Exception:
            pass
        if self.job_thread is not None:
            self.cancel[0] = True
            self.job_thread.wait(30000)
        try:
            import workspace_session
            workspace_session.closed_properly(self)            # closed properly: nothing to recover next time
        except Exception:
            pass
        e.accept()

    # ------------------------------------------------------------------ misc
    def set_status(self, t):
        self.status.setText(t)
        if self.pbar.isVisible():                                      # 'graph 3 of 10': the bar fills up
            import re as _re
            m = _re.search(r"\b(\d+) of (\d+)\b", str(t))
            if m and int(m.group(2)) > 0:
                self.pbar.setRange(0, int(m.group(2))); self.pbar.setValue(min(int(m.group(1)), int(m.group(2))))
                self.pbar.setFormat(f"%v of %m graphs")

    def busy_on(self, what=""):
        """Something moves on the screen while the app works: a running bar (it fills up once the number of graphs is known)."""
        self.pbar.setRange(0, 0); self.pbar.setFormat(what[:40] if what else ""); self.pbar.show()
        QApplication.setOverrideCursor(Qt.BusyCursor)
        QApplication.processEvents()

    def busy_off(self):
        if self.pbar.isVisible():
            self.pbar.hide()
            QApplication.restoreOverrideCursor()

    def busy_while(self, what):
        """with self.busy_while('Drawing …'): the bar runs for a job on the window's own thread."""
        from contextlib import contextmanager
        @contextmanager
        def _cm():
            self.busy_on(what); self.set_status(what + " …")
            try:
                yield
            finally:
                self.busy_off()
        return _cm()

    def mark_ready(self):
        if self.ready_file:
            try:
                Path(self.ready_file).write_text("ready", encoding="utf-8")
            except OSError:
                pass


def main(argv=None):
    a = argparse.ArgumentParser(description=TITLE)
    a.add_argument("--files", help="JSON file with the paths of the graphs to open")
    a.add_argument("--parent", help="process id of Origin Plot Studio: close together with it")
    a.add_argument("--ready-file", help=argparse.SUPPRESS)
    a.add_argument("paths", nargs="*", help="data files to open (e.g. dropped on the shortcut)")
    o = a.parse_args(argv)
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OriginPlotStudio.App" if not o.parent else "OriginPlotStudio.ModernWindow")
        except Exception:
            pass
    paths = []
    if o.files:
        try:
            paths = [p for p in json.loads(Path(o.files).read_text(encoding="utf-8")) if Path(p).is_file()]
        except Exception:
            paths = []
    paths += [str(Path(p).resolve()) for p in o.paths if Path(p).is_file()]
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        from PySide6.QtGui import QIcon
        if (HERE / "app.ico").is_file():
            app.setWindowIcon(QIcon(str(HERE / "app.ico")))
    except Exception:
        pass
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(GROUND))
    pal.setColor(QPalette.Highlight, QColor(BLUE))
    app.setPalette(pal)
    app.setStyleSheet(STYLE)
    w = Workspace(paths, o.ready_file or os.environ.get("OPS_READY_FILE"))
    w.show()
    QTimer.singleShot(200, w.mark_ready)
    if o.parent:
        t = QTimer(w)
        t.setInterval(2000)
        t.timeout.connect(lambda: None if parent_alive(o.parent) else app.quit())
        t.start()
        w._parent_timer = t
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        msg = traceback.format_exc()
        print(msg, file=sys.stderr)
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "Modern window", "The modern window could not start:\n\n" + msg[-1500:])
        except Exception:
            pass
        sys.exit(1)

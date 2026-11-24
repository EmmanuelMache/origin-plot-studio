"""XRD Scan Generator: the window.

The science lives in engine.py; this module only collects settings, runs the engine in a background thread and
shows the results. Every control on the screen does something.
"""
import os
import sys
import threading
import traceback
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QSettings, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPalette
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from . import __version__
from . import engine as eng

APP_TITLE = "XRD Scan Generator"
HERE = Path(__file__).resolve().parent

# colour-blind-safe palette (Okabe-Ito) for the overlay
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]

STYLE = """
QMainWindow, QWidget#root { background: #F4F6FB; }
QLabel { color: #1F2937; }
QLabel#title { font-size: 20px; font-weight: 700; color: #1E3A8A; }
QLabel#subtitle { color: #4B5563; }
QFrame#card { background: white; border: 1px solid #E3E8F2; border-radius: 12px; }
QLabel#cardTitle { font-size: 14px; font-weight: 700; color: #111827; }
QLabel#step { background: #2563EB; color: white; border-radius: 11px; font-weight: 700; min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px; qproperty-alignment: AlignCenter; }
QLabel#drop { border: 2px dashed #93C5FD; border-radius: 10px; background: #EFF6FF; color: #1E40AF; padding: 14px; }
QLabel#drop[active="true"] { background: #DBEAFE; border-color: #2563EB; }
QLabel#info { color: #374151; }
QLabel#key { color: #6B7280; }
QLabel#status { color: #1F2937; font-weight: 600; }
QPushButton { background: white; border: 1px solid #CBD5E1; border-radius: 8px; padding: 6px 12px; color: #1F2937; }
QPushButton:hover { background: #F1F5F9; }
QPushButton:disabled { color: #9CA3AF; background: #F3F4F6; }
QPushButton#primary { background: #F97316; border: none; color: white; font-weight: 700; font-size: 15px; padding: 10px 18px; }
QPushButton#primary:hover { background: #EA580C; }
QPushButton#primary:disabled { background: #FDBA74; }
QPushButton#danger { color: #B91C1C; border-color: #FCA5A5; }
QToolButton#expander { border: none; font-weight: 700; color: #1E3A8A; padding: 4px 0; }
QProgressBar { border: 1px solid #CBD5E1; border-radius: 7px; background: white; height: 14px; text-align: center; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2563EB, stop:1 #10B981); border-radius: 6px; }
QTabWidget::pane { border: 1px solid #E3E8F2; border-radius: 10px; background: white; top: -1px; }
QTabBar::tab { background: #E8EDF7; color: #374151; padding: 7px 16px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 3px; }
QTabBar::tab:selected { background: white; color: #1E3A8A; font-weight: 700; }
QLineEdit { background: white; border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px 6px; }
QLineEdit:focus { border-color: #2563EB; }
QSpinBox, QDoubleSpinBox { min-height: 24px; }
QListWidget, QTableWidget, QPlainTextEdit { background: white; border: 1px solid #E3E8F2; border-radius: 8px; }
"""


# ----------------------------------------------------------------------------- small helpers
def card(title, step=None):
    """A white rounded panel with a numbered title. Returns (frame, body layout)."""
    f = QFrame(objectName="card")
    v = QVBoxLayout(f)
    v.setContentsMargins(14, 12, 14, 14)
    v.setSpacing(8)
    h = QHBoxLayout()
    if step:
        h.addWidget(QLabel(str(step), objectName="step"))
    h.addWidget(QLabel(title, objectName="cardTitle"))
    h.addStretch(1)
    v.addLayout(h)
    return f, v


def spin(lo, hi, val, step=1, tip="", suffix=""):
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(val)
    s.setSingleStep(step)
    s.setGroupSeparatorShown(True)
    if suffix:
        s.setSuffix(suffix)
    s.setToolTip(tip)
    return s


def dspin(lo, hi, val, step, decimals, tip="", suffix=""):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setValue(val)
    s.setSingleStep(step)
    if suffix:
        s.setSuffix(suffix)
    s.setToolTip(tip)
    return s


def range_row(a, b):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.addWidget(a, 1)
    h.addWidget(QLabel("to"))
    h.addWidget(b, 1)
    return w


def open_path(p):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))


class PlotPanel(QWidget):
    """A matplotlib graph with the zoom / pan toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure(figsize=(8, 4.5), dpi=100, facecolor="white")   # fixed: a matplotlibrc with another dpi must not change the text size
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.addWidget(self.toolbar)
        v.addWidget(self.canvas, 1)
        self.ax = self.fig.add_subplot(111)
        self.empty("No data yet")

    def style(self, ax):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.tick_params(direction="out", labelsize=9)
        ax.set_xlabel("2θ (°)", fontsize=10)
        ax.set_ylabel("Intensity (counts)", fontsize=10)

    def empty(self, text):
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.text(0.5, 0.5, text, ha="center", va="center", color="#6B7280", fontsize=11, transform=self.ax.transAxes)
        self.canvas.draw_idle()

    def begin(self):
        self.ax.clear()
        self.ax.set_axis_on()
        self.style(self.ax)
        self.toolbar.update()          # a new graph: home of the zoom history is the new view
        return self.ax

    def finish(self, right=0.97):
        try:
            self.fig.tight_layout(rect=(0, 0, right, 1))
        except Exception:
            pass
        self.canvas.draw_idle()

    def end_labels(self, ax, items, size=9):
        """Names at the right end of the curves, pushed apart so they never overlap (no legend box).
        items: [(text, y in data units, colour)]."""
        if not items:
            return
        lo, hi = ax.get_ylim()
        gap = (hi - lo) * 0.045
        placed = []
        for text, y, col in sorted(items, key=lambda t: t[1]):
            y2 = max(y, placed[-1] + gap) if placed else y
            placed.append(y2)
            ax.annotate(text, xy=(1.0, y2), xycoords=("axes fraction", "data"), xytext=(5, 0), textcoords="offset points",
                        color=col, fontsize=size, va="center", ha="left", annotation_clip=False)


# ----------------------------------------------------------------------------- background work
class Worker(QObject):
    progress = Signal(int, int, object)     # done, total, Scan
    message = Signal(str)
    finished = Signal(object)               # Result
    failed = Signal(str)

    def __init__(self, settings, template):
        super().__init__()
        self.settings, self.template, self.stop = settings, template, threading.Event()

    def run(self):
        try:
            r = eng.generate(self.settings, self.template, progress=lambda d, t, s: self.progress.emit(d, t, s),
                             cancelled=self.stop.is_set, log=self.message.emit)
            self.finished.emit(r)
        except eng.XrdError as e:
            self.failed.emit(str(e))
        except Exception:
            self.failed.emit("An unexpected error stopped the generation:\n\n" + traceback.format_exc(limit=4))


class Loader(QObject):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path, prominence):
        super().__init__()
        self.path, self.prominence = path, prominence

    def run(self):
        try:
            self.done.emit(eng.load_template(self.path, self.prominence))
        except eng.XrdError as e:
            self.failed.emit(str(e))
        except Exception:
            self.failed.emit("The template could not be analysed:\n\n" + traceback.format_exc(limit=4))


class DropLabel(QLabel):
    """The drop zone for the template."""
    dropped = Signal(str)

    def __init__(self, text):
        super().__init__(text, objectName="drop")
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setAcceptDrops(True)
        self.setMinimumHeight(70)

    def _set(self, on):
        self.setProperty("active", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set(True)

    def dragLeaveEvent(self, e):
        self._set(False)

    def dropEvent(self, e):
        self._set(False)
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.dropped.emit(urls[0])


# ----------------------------------------------------------------------------- the window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        ico = HERE / "icon.png"
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))
        self.resize(1380, 860)
        self.setAcceptDrops(True)
        self.store = QSettings("XRDScanGenerator", "XRDScanGenerator")
        self.template = None
        self.scans = []
        self.thread = None
        self.worker = None
        self.out_auto = True          # the output folder follows the template until you choose one

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 12, 16, 12)
        head = QVBoxLayout()
        head.setSpacing(0)
        head.addWidget(QLabel(APP_TITLE, objectName="title"))
        head.addWidget(QLabel("Randomised XRD scans from a measured .xrdml template: same peaks, new noise, "
                              "background and sample displacement; optional phase mixtures.", objectName="subtitle"))
        outer.addLayout(head)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)
        split.addWidget(self._left())
        split.addWidget(self._right())
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([470, 900])

        self._menu()
        self.statusBar().showMessage("Choose a template .xrdml file to begin.")
        self._update_buttons()

    # ------------------------------------------------------------------ layout
    def _menu(self):
        m = self.menuBar().addMenu("&File")
        a = QAction("Open template…", self, shortcut="Ctrl+O", triggered=self.browse_template)
        m.addAction(a)
        m.addAction(QAction("Open output folder", self, triggered=self.open_output))
        m.addSeparator()
        m.addAction(QAction("Quit", self, shortcut="Ctrl+Q", triggered=self.close))
        h = self.menuBar().addMenu("&Help")
        h.addAction(QAction("About", self, triggered=self.about))

    def _left(self):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 8, 8, 8)
        v.setSpacing(12)

        # 1 template
        f, b = card("Template scan", 1)
        self.drop = DropLabel("Drop an .xrdml file here\nor")
        self.drop.dropped.connect(self.set_template)
        b.addWidget(self.drop)
        btn = QPushButton("Browse for template…")
        btn.setToolTip("A measured PANalytical .xrdml scan. Its peaks, peak widths and background are used.")
        btn.clicked.connect(self.browse_template)
        b.addWidget(btn)
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        self.info = {}
        for r, (k, label) in enumerate((("file", "File"), ("sample", "Sample ID"), ("range", "Angular range"),
                                        ("points", "Points"), ("max", "Max intensity"), ("peaks", "Peaks found"))):
            g.addWidget(QLabel(label, objectName="key"), r, 0)
            lab = QLabel("—", objectName="info")
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lab.setWordWrap(True)
            g.addWidget(lab, r, 1)
            self.info[k] = lab
        b.addLayout(g)
        v.addWidget(f)

        # 2 settings
        f, b = card("Generation settings", 2)
        fl = QFormLayout()
        fl.setLabelAlignment(Qt.AlignLeft)
        d = eng.DEFAULTS
        self.n = spin(1, 10000, d["n"], 1, "How many scans to write.", " scans")
        self.p_lo = spin(100, 1_000_000, d["points"][0], 500, "Smallest number of data points per scan. Each scan gets a random number between minimum and maximum.", " pts")
        self.p_hi = spin(100, 1_000_000, d["points"][1], 500, "Largest number of data points per scan.", " pts")
        self.c_lo = spin(50, 100_000_000, int(d["counts"][0]), 500, "Lowest allowed maximum intensity of a scan, after Poisson noise. Each scan's maximum is drawn at random between minimum and maximum and is always inside this range.", " counts")
        self.c_hi = spin(50, 100_000_000, int(d["counts"][1]), 500, "Highest allowed maximum intensity of a scan, after Poisson noise.", " counts")
        seedrow = QWidget()
        sh = QHBoxLayout(seedrow)
        sh.setContentsMargins(0, 0, 0, 0)
        self.seed = QLineEdit()
        self.seed.setPlaceholderText("empty = different every run")
        self.seed.setToolTip("A whole number. The same template, settings and seed always give identical files.")
        sh.addWidget(self.seed, 1)
        fl.addRow("Number of scans", self.n)
        fl.addRow("Points per scan", range_row(self.p_lo, self.p_hi))
        fl.addRow("Peak counts (max)", range_row(self.c_lo, self.c_hi))
        fl.addRow("Random seed", seedrow)
        outrow = QWidget()
        oh = QHBoxLayout(outrow)
        oh.setContentsMargins(0, 0, 0, 0)
        self.out = QLineEdit()
        self.out.setToolTip("Where the scans, manifest.csv and the preview image are written. Existing files are never overwritten: numbering continues.")
        self.out.textEdited.connect(lambda _t: setattr(self, "out_auto", False))
        ob = QPushButton("Browse…")
        ob.clicked.connect(self.browse_out)
        oh.addWidget(self.out, 1)
        oh.addWidget(ob)
        fl.addRow("Output folder", outrow)
        self.want_preview = QCheckBox("Also save preview.png (first 4 scans)")
        self.want_preview.setToolTip("A 2 × 2 picture of the first four scans, like the script's --preview option.")
        fl.addRow("", self.want_preview)
        b.addLayout(fl)
        v.addWidget(f)

        # 3 advanced
        f, b = card("Phase mixtures and advanced options", 3)
        self.adv_btn = QToolButton(objectName="expander")
        self.adv_btn.setCheckable(True)
        self.adv_btn.setText("▸  Show advanced options")
        self.adv_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.adv_btn.toggled.connect(self._toggle_adv)
        b.addWidget(self.adv_btn)
        self.adv = QWidget()
        av = QVBoxLayout(self.adv)
        av.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("Each scan mixes these phases. A reference peak list is a text/CSV file with 2θ and relative "
                      "intensity on each line (header lines are skipped). Weights are relative amounts.")
        hint.setWordWrap(True)
        hint.setObjectName("key")
        av.addWidget(hint)
        self.phases = QTableWidget(0, 2)
        self.phases.setHorizontalHeaderLabels(["Phase", "Weight"])
        self.phases.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.phases.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.phases.verticalHeader().setVisible(False)
        self.phases.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.phases.setMinimumHeight(120)
        av.addWidget(self.phases)
        pr = QHBoxLayout()
        for text, fn, tip in (("Add reference…", self.add_reference, "Add a reference peak list (2θ, intensity)."),
                              ("Add template peaks", self.add_template_phase, "Include the template's own peaks as a phase."),
                              ("Remove", self.remove_phase, "Remove the selected phase.")):
            bt = QPushButton(text)
            bt.setToolTip(tip)
            bt.clicked.connect(fn)
            pr.addWidget(bt)
            if text == "Add template peaks":
                self.add_tpl_btn = bt
        av.addLayout(pr)
        fa = QFormLayout()
        self.ij = dspin(0, 2, d["intensity_jitter"], 0.02, 3, "Random change of each template peak's height (sigma of a log-normal factor). 0 keeps the relative peak strengths exactly as in the template.")
        self.pj = dspin(0, 2, d["phase_jitter"], 0.05, 3, "Random change of each phase's amount per scan (sigma of a log-normal factor). Moves all peaks of a phase together.")
        self.dropout = dspin(0, 1, d["dropout"], 0.05, 2, "Fraction of weak lines (below 8 % relative intensity) left out at random. 0 keeps every peak.")
        self.prom = dspin(0.1, 10, d["prominence"], 0.1, 2, "How clearly a template peak must stand out from its neighbours to be taken (in units of the median noise sigma). Every peak must also exceed 3 sigma of the local noise.")
        self.prom.editingFinished.connect(self._reanalyse)
        fa.addRow("Peak intensity jitter (σ)", self.ij)
        fa.addRow("Phase amount jitter (σ)", self.pj)
        fa.addRow("Weak-line dropout (fraction)", self.dropout)
        fa.addRow("Peak detection prominence (× noise σ)", self.prom)
        av.addLayout(fa)
        self.adv.setVisible(False)
        b.addWidget(self.adv)
        v.addWidget(f)
        self._add_phase_row("template", 1.0)

        # 4 run
        f, b = card("Generate", 4)
        rr = QHBoxLayout()
        self.go = QPushButton("Generate scans", objectName="primary")
        self.go.setToolTip("Write the scans, manifest.csv and (if chosen) preview.png.")
        self.go.clicked.connect(self.generate)
        self.cancel = QPushButton("Cancel", objectName="danger")
        self.cancel.setToolTip("Stop after the scan that is being written now. Files already written are kept.")
        self.cancel.clicked.connect(self.cancel_run)
        rr.addWidget(self.go, 1)
        rr.addWidget(self.cancel)
        b.addLayout(rr)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.bar.setFormat("%v of %m scans")
        b.addWidget(self.bar)
        self.status = QLabel("Ready when a template is chosen.", objectName="status")
        self.status.setWordWrap(True)
        b.addWidget(self.status)
        v.addWidget(f)
        v.addStretch(1)
        sc.setWidget(w)
        sc.setMinimumWidth(430)
        return sc

    def _right(self):
        self.tabs = QTabWidget()
        self.tpl_plot = PlotPanel()
        self.tpl_plot.empty("Choose a template to see it here")
        self.tabs.addTab(self.tpl_plot, "Template")

        gen = QWidget()
        gh = QHBoxLayout(gen)
        side = QVBoxLayout()
        side.addWidget(QLabel("Tick scans to overlay them:"))
        self.scan_list = QListWidget()
        self.scan_list.itemChanged.connect(lambda _i: self.plot_scans())
        self.scan_list.setMaximumWidth(230)
        side.addWidget(self.scan_list, 1)
        self.show_tpl = QCheckBox("Overlay the template")
        self.show_tpl.setToolTip("Draw the template scan behind the selected scans for comparison.")
        self.show_tpl.toggled.connect(self.plot_scans)
        self.norm = QCheckBox("Normalise to maximum = 1")
        self.norm.setToolTip("Scale every curve to the same height so the peak positions and shapes can be compared.")
        self.norm.toggled.connect(self.plot_scans)
        side.addWidget(self.show_tpl)
        side.addWidget(self.norm)
        allb = QPushButton("Tick all")
        allb.clicked.connect(lambda: self._tick_all(True))
        noneb = QPushButton("Tick none")
        noneb.clicked.connect(lambda: self._tick_all(False))
        tr = QHBoxLayout()
        tr.addWidget(allb)
        tr.addWidget(noneb)
        side.addLayout(tr)
        gh.addLayout(side)
        self.gen_plot = PlotPanel()
        self.gen_plot.empty("Generated scans appear here")
        gh.addWidget(self.gen_plot, 1)
        self.tabs.addTab(gen, "Generated scans")

        files = QWidget()
        fv = QVBoxLayout(files)
        fv.addWidget(QLabel("Written files (double-click to open):"))
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(lambda it: open_path(it.data(Qt.UserRole)))
        fv.addWidget(self.file_list, 1)
        self.open_out = QPushButton("Open output folder")
        self.open_out.clicked.connect(self.open_output)
        fv.addWidget(self.open_out, 0, Qt.AlignLeft)
        self.tabs.addTab(files, "Files")

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.tabs.addTab(self.log, "Log")
        return self.tabs

    # ------------------------------------------------------------------ template
    def browse_template(self):
        start = self.store.value("last_dir", str(Path.home()))
        p, _ = QFileDialog.getOpenFileName(self, "Choose a template scan", start, "XRDML scans (*.xrdml);;All files (*.*)")
        if p:
            self.set_template(p)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.set_template(urls[0])

    def set_template(self, path):
        if self.busy():
            return
        if not str(path).lower().endswith(".xrdml"):
            self.error("Unsupported file", f"{Path(path).name} is not an .xrdml file.\n\nDrop or choose a PANalytical .xrdml scan as the template.")
            return
        self.store.setValue("last_dir", str(Path(path).parent))
        self._start_load(path)

    def _reanalyse(self):
        if self.template is not None and not self.busy() and abs(self.prom.value() - self.template.prominence) > 1e-9:
            self._start_load(self.template.path)

    def _start_load(self, path):
        self.set_status(f"Analysing {Path(path).name} …")
        self.go.setEnabled(False)
        self.load_thread = QThread(self)
        self.loader = Loader(path, self.prom.value())
        self.loader.moveToThread(self.load_thread)
        self.load_thread.started.connect(self.loader.run)
        self.loader.done.connect(self._template_ready)
        self.loader.failed.connect(self._template_failed)
        self.loader.done.connect(self.load_thread.quit)
        self.loader.failed.connect(self.load_thread.quit)
        self.load_thread.finished.connect(self._update_buttons)
        self.load_thread.start()

    def _template_failed(self, msg):
        self.set_status("The template could not be used.")
        self.error("Template not usable", msg)

    def _template_ready(self, t):
        self.template = t
        s = t.summary()
        self.info["file"].setText(s["file"])
        self.info["sample"].setText(s["sample_id"] + (f"   (name: {s['name']})" if s["name"] and s["name"] != s["sample_id"] else ""))
        self.info["range"].setText(f"{s['range'][0]:.3f} – {s['range'][1]:.3f}° 2θ")
        self.info["points"].setText(f"{s['points']:,}")
        self.info["max"].setText(f"{s['max_counts']:,.0f} counts")
        b = s["bands"]
        self.info["peaks"].setText(f"{s['peaks']} above 3σ noise (tops below 5000: {b[0]}, 5000–8000: {b[1]}, above 8000: {b[2]})")
        self.drop.setText(f"✔  {s['file']}\nDrop another .xrdml file to replace it")
        if self.out_auto or not self.out.text().strip():
            self.out.setText(str(Path(t.path).parent / "scans"))
            self.out_auto = True
        ax = self.tpl_plot.begin()
        ax.plot(t.x, t.y, lw=0.6, color="#1E3A8A", label="template")
        ax.plot(t.x, t.bg, lw=1.0, color="#F97316", ls="--")
        tops = t.peaks[:, 1] + np.interp(t.peaks[:, 0], t.x, t.bg)
        ax.plot(t.peaks[:, 0], tops, ls="none", marker="v", ms=5, color="#10B981")
        ax.set_title(f"{s['sample_id']}  —  {s['peaks']} peaks used (green marks)", fontsize=10, loc="left")
        ax.set_xlim(t.x[0], t.x[-1])
        self.tpl_plot.end_labels(ax, [("background", float(t.bg[-1]), "#F97316")])
        self.tpl_plot.finish(right=0.88)
        self.tabs.setCurrentIndex(0)
        self.logline(f"Template {s['file']}: sample {s['sample_id']}, {s['points']} points, {s['range'][0]:.3f}-{s['range'][1]:.3f} deg, "
                     f"max {s['max_counts']:.0f} counts, {s['peaks']} peaks, median FWHM {s['median_fwhm']:.3f} deg")
        self.set_status(f"Template ready: {s['sample_id']}. Files will be called {eng.safe_stem(s['sample_id'])}-001, -002, …")

    # ------------------------------------------------------------------ phases
    def _toggle_adv(self, on):
        self.adv.setVisible(on)
        self.adv_btn.setText(("▾  Hide" if on else "▸  Show") + " advanced options")

    def _add_phase_row(self, name, weight):
        r = self.phases.rowCount()
        self.phases.insertRow(r)
        it = QTableWidgetItem("Template's own peaks" if name == "template" else Path(name).name)
        it.setData(Qt.UserRole, name)
        it.setToolTip("The peaks found in the template" if name == "template" else name)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.phases.setItem(r, 0, it)
        w = dspin(0.001, 1000, weight, 0.1, 3, "Relative amount of this phase.")
        self.phases.setCellWidget(r, 1, w)
        self._update_buttons()

    def _phase_names(self):
        return [self.phases.item(r, 0).data(Qt.UserRole) for r in range(self.phases.rowCount())]

    def add_reference(self):
        start = self.store.value("last_ref_dir", self.store.value("last_dir", str(Path.home())))
        paths, _ = QFileDialog.getOpenFileNames(self, "Reference peak lists", start, "Peak lists (*.csv *.txt *.dat *.xy);;All files (*.*)")
        for p in paths:
            try:
                ref = eng.load_phase(p)
            except eng.XrdError as e:
                self.error("Reference peak list not usable", str(e))
                continue
            self.store.setValue("last_ref_dir", str(Path(p).parent))
            self._add_phase_row(p, 1.0)
            self.logline(f"Reference phase {Path(p).name}: {len(ref)} lines")

    def add_template_phase(self):
        if "template" not in self._phase_names():
            self._add_phase_row("template", 1.0)

    def remove_phase(self):
        rows = sorted({i.row() for i in self.phases.selectedIndexes()}, reverse=True)
        if not rows and self.phases.rowCount():
            rows = [self.phases.rowCount() - 1]
        for r in rows:
            self.phases.removeRow(r)
        self._update_buttons()

    # ------------------------------------------------------------------ output
    def browse_out(self):
        p = QFileDialog.getExistingDirectory(self, "Output folder", self.out.text() or str(Path.home()))
        if p:
            self.out.setText(p)
            self.out_auto = False

    def open_output(self):
        p = Path(self.out.text().strip()) if self.out.text().strip() else None
        if p is None:
            self.error("No output folder", "Choose an output folder first.")
            return
        if not p.is_dir():
            self.error("Folder not found", f"The output folder does not exist yet:\n{p}\n\nIt is created when scans are generated.")
            return
        open_path(p)

    # ------------------------------------------------------------------ run
    def collect(self):
        seed_t = self.seed.text().strip()
        seed = None
        if seed_t:
            try:
                seed = int(seed_t)
            except ValueError:
                raise eng.XrdError("Random seed must be a whole number (or empty).")
        phases = []
        for r in range(self.phases.rowCount()):
            phases.append((self.phases.item(r, 0).data(Qt.UserRole), float(self.phases.cellWidget(r, 1).value())))
        return eng.Settings(template=self.template.path if self.template else "", out_dir=self.out.text().strip(),
                            n=int(self.n.value()), points=(int(self.p_lo.value()), int(self.p_hi.value())),
                            counts=(float(self.c_lo.value()), float(self.c_hi.value())), seed=seed, phases=phases,
                            intensity_jitter=float(self.ij.value()), phase_jitter=float(self.pj.value()),
                            dropout=float(self.dropout.value()), prominence=float(self.prom.value()),
                            preview=self.want_preview.isChecked())

    def generate(self):
        if self.busy():
            return
        if self.template is None:
            self.error("No template", "Choose a template .xrdml file first.")
            return
        try:
            s = self.collect()
        except eng.XrdError as e:
            self.error("Check the settings", str(e))
            return
        problems = eng.check_settings(s)
        if problems:
            self.error("Check the settings", "\n".join("• " + p for p in problems))
            return
        try:
            eng.check_output_folder(s.out_dir)
        except eng.XrdError as e:
            self.error("Output folder", str(e))
            return
        self.scans = []
        self.scan_list.clear()
        self.file_list.clear()
        self.gen_plot.empty("Generating …")
        self.bar.setRange(0, s.n)
        self.bar.setValue(0)
        self.logline(f"--- generating {s.n} scan(s) into {s.out_dir} (seed {s.seed if s.seed is not None else 'random'})")
        self.thread = QThread(self)
        self.worker = Worker(s, self.template)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.message.connect(self.logline)
        self.worker.finished.connect(self._finished)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self._thread_done)
        self.set_status(f"Generating {s.n} scan(s) …")
        self.thread.start()
        self._update_buttons()

    def cancel_run(self):
        if self.worker is not None and self.busy():
            self.worker.stop.set()
            self.cancel.setEnabled(False)
            self.set_status("Cancelling after the current scan …")

    def _progress(self, done, total, scan):
        self.bar.setValue(done)
        self.set_status(f"Scan {done} of {total} written: {scan.sid} (max {int(scan.counts.max()):,} counts)")
        self.scans.append(scan)
        it = QListWidgetItem(f"{scan.sid}   max {int(scan.counts.max()):,}")
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        self.scan_list.blockSignals(True)
        it.setCheckState(Qt.Checked if len(self.scans) <= 3 else Qt.Unchecked)
        self.scan_list.addItem(it)
        self.scan_list.blockSignals(False)
        for f in scan.files:
            self._add_file(f)
        if len(self.scans) <= 3 or done == total:
            self.plot_scans()

    def _add_file(self, f):
        it = QListWidgetItem(Path(f).name)
        it.setData(Qt.UserRole, f)
        it.setToolTip(f)
        self.file_list.addItem(it)

    def _finished(self, r):
        listed = {self.file_list.item(i).data(Qt.UserRole) for i in range(self.file_list.count())}
        for f in r.files:
            if f not in listed:
                self._add_file(f)
        n = len(r.scans)
        if r.cancelled:
            self.set_status(f"Cancelled: {n} scan(s) were written and kept, with manifest.csv." if n else "Cancelled before the first scan; nothing was written.")
        else:
            self.set_status(f"Done: {n} scan(s) written to {r.out_dir}" + (" with preview.png." if r.preview else "."))
        self.plot_scans()
        self.tabs.setCurrentIndex(1)

    def _failed(self, msg):
        self.set_status("Generation stopped: see the message.")
        self.logline("ERROR: " + msg)
        self.error("Generation stopped", msg + ("\n\nFiles written before the error are kept." if self.scans else ""))

    def _thread_done(self):
        self.worker = None
        self.thread = None
        self._update_buttons()

    def busy(self):
        return (self.thread is not None and self.thread.isRunning()) or (getattr(self, "load_thread", None) is not None and self.load_thread.isRunning())

    def _update_buttons(self):
        if not hasattr(self, "go"):
            return                      # still building the window
        running = self.thread is not None and self.thread.isRunning()
        loading = getattr(self, "load_thread", None) is not None and self.load_thread.isRunning()
        self.go.setEnabled(not running and not loading and self.template is not None and self.phases.rowCount() > 0)
        self.cancel.setEnabled(running)
        self.add_tpl_btn.setEnabled("template" not in self._phase_names())
        for wdg in (self.n, self.p_lo, self.p_hi, self.c_lo, self.c_hi, self.seed, self.out, self.phases, self.ij, self.pj, self.dropout, self.prom, self.want_preview):
            wdg.setEnabled(not running)

    # ------------------------------------------------------------------ plots
    def _tick_all(self, on):
        self.scan_list.blockSignals(True)
        for i in range(self.scan_list.count()):
            self.scan_list.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)
        self.scan_list.blockSignals(False)
        self.plot_scans()

    def plot_scans(self):
        chosen = [self.scans[i] for i in range(min(self.scan_list.count(), len(self.scans))) if self.scan_list.item(i).checkState() == Qt.Checked]
        if not chosen and not (self.show_tpl.isChecked() and self.template is not None):
            self.gen_plot.empty("Tick one or more scans in the list" if self.scans else "Generated scans appear here")
            return
        ax = self.gen_plot.begin()
        norm = self.norm.isChecked()
        labels = []
        if self.show_tpl.isChecked() and self.template is not None:
            t = self.template
            yt = t.y / (t.y.max() if norm else 1)
            ax.plot(t.x, yt, lw=1.2, color="#9CA3AF", alpha=0.8, zorder=1)
            labels.append(("template", float(np.median(yt[-80:])), "#6B7280"))
        for k, sc in enumerate(chosen):
            y = sc.counts / (sc.counts.max() if norm else 1)
            col = PALETTE[k % len(PALETTE)]
            ax.plot(sc.x, y, lw=0.6, color=col, zorder=2 + k)
            labels.append((sc.sid, float(np.median(y[-80:])), col))
        if norm:
            ax.set_ylabel("Intensity (normalised)", fontsize=10)
        xs = [sc.x for sc in chosen] + ([self.template.x] if self.show_tpl.isChecked() and self.template is not None else [])
        ax.set_xlim(min(x[0] for x in xs), max(x[-1] for x in xs))
        ax.set_ylim(bottom=0)
        self.gen_plot.end_labels(ax, labels[:12])
        self.gen_plot.finish(right=0.85)

    # ------------------------------------------------------------------ messages
    def set_status(self, t):
        self.status.setText(t)
        self.statusBar().showMessage(t)

    def logline(self, t):
        self.log.appendPlainText(t)

    def error(self, title, text):
        QMessageBox.warning(self, title, text)

    def about(self):
        QMessageBox.about(self, APP_TITLE, f"<b>{APP_TITLE}</b> {__version__}<br><br>Randomised XRD scans from a measured .xrdml "
                          "template, for testing software and pipelines. Peaks: pseudo-Voigt with Kα1/Kα2 doublets; "
                          "noise: Poisson counting statistics; the maximum of every scan lies inside the chosen range.<br><br>"
                          "Generated scans are synthetic test data, not measurements.")

    def closeEvent(self, e):
        if self.thread is not None and self.thread.isRunning():
            if QMessageBox.question(self, APP_TITLE, "Scans are still being generated. Stop after the current scan and quit?") != QMessageBox.Yes:
                e.ignore()
                return
            self.worker.stop.set()
            self.thread.quit()
            self.thread.wait(30000)
        lt = getattr(self, "load_thread", None)
        if lt is not None and lt.isRunning():
            lt.wait(30000)
        e.accept()


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("XRDScanGenerator.App")   # own taskbar icon
        except Exception:
            pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor("#F4F6FB"))
    pal.setColor(QPalette.Highlight, QColor("#2563EB"))
    app.setPalette(pal)
    app.setStyleSheet(STYLE)
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".xrdml"):
        w.set_template(sys.argv[1])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

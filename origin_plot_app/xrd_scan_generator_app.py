"""XRD Scan Generator: the window (the stand-alone XRD Scan Generator 1.0.0, unchanged), opened by Origin Plot Studio.

The science lives in xrd_generator.py (the generator's engine with the later fixes: weak real peaks kept, true noise
measured). Started by Origin Plot Studio with a template, the window also offers, besides the generated scans:
  * better versions of the template itself (counted longer: your counts and 2-theta points kept, see xrd_generator.improve_candidates);
  * "Use the ticked scans in Origin Plot Studio": the ticked scans go back to Your graphs.
Command line:  xrd_scan_generator_app.py [template.xrdml] [--return result.json] [--better] [--parent PID]
(--parent: the window closes when that program, Origin Plot Studio, is closed)
"""
import os
import sys
import threading
import traceback
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QSettings, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPalette
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget, QRadioButton, QButtonGroup)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

import xrd_generator as eng

__version__ = "1.0.0"

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
class PeakLoader(QObject):
    """The peaks of the template with their expected top counts (the fit of the correction), for the Peak correct tab."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path, prominence):
        super().__init__()
        self.path, self.prominence = path, prominence

    def run(self):
        try:
            self.done.emit(eng.peak_table(self.path, self.prominence))
        except eng.XrdError as e:
            self.failed.emit(str(e))
        except Exception:
            self.failed.emit("The peaks could not be analysed:\n\n" + traceback.format_exc(limit=4))


class PeakCorrector(QObject):
    """Peak correct: n versions of the template counted `factor` times as long (each its own random draw)."""
    one = Signal(object)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, path, factor, n, out_dir, why):
        super().__init__()
        self.path, self.factor, self.n, self.out_dir, self.why = path, factor, n, out_dir, why

    def run(self):
        try:
            import types
            for i in range(self.n):
                f, k, how = eng.count_longer(self.path, self.factor, out_dir=self.out_dir, draw=i + 1, suffix=f"_peakcorrected_{i + 1:02d}", why=self.why)
                _t, x, y, _s, _n = eng.load_xrdml(Path(f))
                self.one.emit(types.SimpleNamespace(sid=Path(f).stem + f"  (counted {k:.3g}\u00d7 {'longer' if k >= 1 else 'as long'})",
                                                    x=np.asarray(x, float), counts=np.asarray(y), files=[f]))
            self.finished.emit()
        except eng.XrdError as e:
            self.failed.emit(str(e))
        except Exception:
            self.failed.emit("The peaks could not be corrected:\n\n" + traceback.format_exc(limit=4))


class BetterWorker(Worker):
    """The generation, then better versions of the template itself (counted longer), each its own random draw."""
    def __init__(self, settings, template, better):
        super().__init__(settings, template)
        self.better = better

    def run(self):
        try:
            r = eng.generate(self.settings, self.template, progress=lambda d, t, s: self.progress.emit(d, t, s),
                             cancelled=self.stop.is_set, log=self.message.emit) if self.settings.n > 0 else None
            extra = []
            if self.better and not self.stop.is_set():
                import types
                n0 = len(r.scans) if r is not None else 0
                lo, hi = eng.improve_counts(float(np.max(self.template.y)))
                def one(i, n, res):
                    _t, x, y, _s, _n = eng.load_xrdml(Path(res[0]))
                    sc = types.SimpleNamespace(sid=Path(res[0]).stem + f"  (your scan counted {res[1]:.3g}\u00d7 longer)" if res[1] >= 1 else Path(res[0]).stem + "  (shorter count)",
                                               x=np.asarray(x, float), counts=np.asarray(y), files=[res[0]])
                    extra.append(sc); self.progress.emit(n0 + i, n0 + n, sc)
                self.message.emit(f"better versions of {Path(self.template.path).name}: your counts kept + Poisson counts of the extra counting time, {lo:,.0f}-{hi:,.0f} counts")
                eng.improve_candidates(self.template.path, max(1, min(self.settings.n, 5)), counts=(lo, hi), out_dir=self.settings.out_dir,
                                       progress=one, cancelled=self.stop.is_set)
            if r is None:
                import types
                r = types.SimpleNamespace(scans=[], files=[], out_dir=self.settings.out_dir, cancelled=self.stop.is_set(), preview=None)
            r.scans = list(r.scans) + extra
            r.files = list(r.files) + [f for sc in extra for f in sc.files]
            self.finished.emit(r)
        except eng.XrdError as e:
            self.failed.emit(str(e))
        except Exception:
            self.failed.emit("An unexpected error stopped the generation:\n\n" + traceback.format_exc(limit=4))


class MainWindow(QMainWindow):
    def __init__(self, return_file=None, better=False):
        super().__init__()
        self.return_file = return_file          # opened by Origin Plot Studio: the ticked scans go back to it
        self.better_default = better
        self.setWindowTitle(APP_TITLE)
        ico = next((p for p in (HERE / "icon.png", HERE / "app.png") if p.exists()), HERE / "icon.png")
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
        try:                                     # mouse selection, right-click menus, where to save (xrd_scan_generator_actions.py)
            import xrd_scan_generator_actions
            xrd_scan_generator_actions.install(self)
        except Exception as e:
            self.statusBar().showMessage(f"Choose a template .xrdml file to begin.  (Extra mouse actions not loaded: {e})")

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
        self.bg_mode = QComboBox()
        for key_, text_ in eng.BG_MODES.items():
            self.bg_mode.addItem(text_, key_)
        self.bg_mode.setCurrentIndex(0)
        self.bg_mode.setToolTip("The background of the generated scans. 'Keep': exactly the shape and level of your template's background "
                                "(only the counting noise is new). The other two change it on purpose, as earlier versions did.")
        fl.addRow("Background", self.bg_mode)
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
        self.better = QCheckBox("Also make better versions of the template itself (counted longer: your counts and points kept)")
        self.better.setToolTip("Each is your measured scan plus Poisson counts for extra counting time, like measuring longer. "
                               "Up to 5 versions; if the scan is already in 8,000-10,000 counts they count 2-3 times longer.")
        self.better.setChecked(bool(self.better_default))
        self.better.setVisible(bool(self.return_file))
        b.addWidget(self.better)
        v.addWidget(f)
        if self.return_file:                    # 5: back to Origin Plot Studio
            f, b = card("Continue in Origin Plot Studio", 5)
            hint = QLabel("Tick the scan(s) you like under 'Generated scans' (compare them with the template overlaid), then:")
            hint.setWordWrap(True)
            hint.setObjectName("key")
            b.addWidget(hint)
            self.use_btn = QPushButton("Use the ticked scans in Origin Plot Studio", objectName="primary")
            self.use_btn.setToolTip("The ticked scans are added to Your graphs (the first one takes the place of the template if Origin asked for a better scan). Your original file is not changed.")
            self.use_btn.clicked.connect(self.use_ticked)
            b.addWidget(self.use_btn)
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
        if self.return_file:
            self.use_btn2 = QPushButton("Use the ticked scans", objectName="primary")
            self.use_btn2.setToolTip("Back to Origin Plot Studio with the ticked scans.")
            self.use_btn2.clicked.connect(self.use_ticked)
            side.addWidget(self.use_btn2)
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
        self.pc_tab = self._peak_correct_tab()
        self.tabs.addTab(self.pc_tab, "Peak correct")
        self.tabs.currentChanged.connect(lambda _i: self._pc_maybe_load())
        return self.tabs

    # ------------------------------------------------------------------ Peak correct tab
    def _peak_correct_tab(self):
        """Correct the peak intensities of the template, also when they are fine: choose the peaks and the height you want. The whole
        scan is counted longer (or shorter) by one factor, so the peaks keep their relative intensities."""
        self.pc_peaks = []
        self.pc_scans = []
        self.pc_thread = None
        w = QWidget()
        v = QVBoxLayout(w)
        self.pc_banner = QLabel("Choose a template to correct its peaks.", objectName="subtitle")
        self.pc_banner.setWordWrap(True)
        v.addWidget(self.pc_banner)
        top = QHBoxLayout()
        left = QVBoxLayout()
        self.pc_mode_max = QRadioButton("Highest peak into this range")
        self.pc_mode_sel = QRadioButton("The ticked peaks to the heights I give (column 'Target')")
        self.pc_mode_max.setChecked(True)
        grp = QButtonGroup(w)
        grp.addButton(self.pc_mode_max)
        grp.addButton(self.pc_mode_sel)
        left.addWidget(self.pc_mode_max)
        self.pc_lo = spin(50, 100_000_000, 8000, 500, "Lowest wanted maximum (counts).", " counts")
        self.pc_hi = spin(50, 100_000_000, 10000, 500, "Highest wanted maximum (counts).", " counts")
        left.addWidget(range_row(self.pc_lo, self.pc_hi))
        left.addWidget(self.pc_mode_sel)
        self.pc_table = QTableWidget(0, 5)
        self.pc_table.setHorizontalHeaderLabels(["\u2713", "2\u03b8 (\u00b0)", "Now", "Target", "After"])
        for c_, tip_ in enumerate(("Tick the peaks to correct", "Peak position", "Counts at the peak top now", "The height you want (counts); you can type it", "Counts at the peak top after the correction")):
            self.pc_table.horizontalHeaderItem(c_).setToolTip(tip_)
        self.pc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        left.addWidget(QLabel("Peaks (counts at the top). Tick the ones to correct and type their target:", objectName="key"))
        self.pc_table.verticalHeader().setVisible(False)
        self.pc_table.setMinimumHeight(200)
        self.pc_table.itemChanged.connect(lambda it: (self._pc_update(), self._pc_plot() if it.column() == 0 and not self.pc_scans else None))
        left.addWidget(self.pc_table, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Versions"))
        self.pc_n = spin(1, 10, 3, 1, "How many corrected versions to make (each its own random draw), to compare and choose from.", "")
        row.addWidget(self.pc_n)
        row.addStretch(1)
        left.addLayout(row)
        self.pc_factor = QLabel("", objectName="status")
        self.pc_factor.setWordWrap(True)
        left.addWidget(self.pc_factor)
        self.pc_go = QPushButton("Correct peaks", objectName="primary")
        self.pc_go.setToolTip("Write the corrected version(s) next to the output folder's scans, with a provenance file each. Your original is not changed.")
        self.pc_go.clicked.connect(self.peak_correct)
        left.addWidget(self.pc_go)
        note = QLabel("One counting-time factor for the whole scan: the ticked peaks reach (at least) their targets and all other peaks change in "
                      "proportion, so the relative intensities stay those of your measurement. Longer: your counts are kept and Poisson counts of the "
                      "extra time are added; shorter: binomial thinning. Each file says inside that it is a statistical simulation.")
        note.setWordWrap(True)
        note.setObjectName("key")
        left.addWidget(note)
        top.addLayout(left, 2)
        right = QVBoxLayout()
        self.pc_plot = PlotPanel()
        self.pc_plot.empty("The template and its corrected versions appear here")
        right.addWidget(self.pc_plot, 1)
        right.addWidget(QLabel("Corrected versions (tick to compare):"))
        self.pc_list = QListWidget()
        self.pc_list.setMaximumHeight(110)
        self.pc_list.itemChanged.connect(lambda _i: self._pc_plot())
        right.addWidget(self.pc_list)
        if self.return_file:
            self.pc_use = QPushButton("Use the ticked corrected scan(s) in Origin Plot Studio", objectName="primary")
            self.pc_use.clicked.connect(self.pc_use_ticked)
            right.addWidget(self.pc_use)
        top.addLayout(right, 3)
        v.addLayout(top, 1)
        for wdg in (self.pc_mode_max, self.pc_mode_sel):
            wdg.toggled.connect(lambda _on: self._pc_update())
        for wdg in (self.pc_lo, self.pc_hi):
            wdg.valueChanged.connect(lambda _v: self._pc_update())
        return w

    def _pc_status(self):
        t = self.template
        if t is None:
            return "Choose a template to correct its peaks."
        m = float(np.max(t.y)); lo, hi = eng.USUAL_COUNTS
        if m < lo:
            return f"\u26a0  The peaks of this scan are LOW: highest {m:,.0f} counts (usual {lo:,.0f}\u2013{hi:,.0f}). Correct them here."
        if m > hi:
            return f"The peaks of this scan are HIGH: highest {m:,.0f} counts (usual {lo:,.0f}\u2013{hi:,.0f}). You can bring them down here (a shorter count)."
        return f"This scan is in the usual range (highest {m:,.0f} counts). You can still correct its peaks here, e.g. to give a weak peak more counts."

    def _pc_reset(self):
        self.pc_peaks = []
        self.pc_table.blockSignals(True)
        self.pc_table.setRowCount(0)
        self.pc_table.blockSignals(False)
        self.pc_banner.setText(self._pc_status())
        m = float(np.max(self.template.y)) if self.template is not None else 0
        lo, hi = eng.improve_counts(m) if self.template is not None and eng.USUAL_COUNTS[0] <= m <= eng.USUAL_COUNTS[1] else eng.USUAL_COUNTS
        self.pc_lo.setValue(int(lo)); self.pc_hi.setValue(int(hi))
        self.pc_factor.setText("")
        self._pc_plot()

    def _pc_maybe_load(self):
        if self.tabs.currentWidget() is self.pc_tab and self.template is not None and not self.pc_peaks and self.pc_thread is None:
            self._pc_load()

    def _pc_load(self):
        self.pc_factor.setText("Finding and fitting the peaks \u2026")
        self.pc_go.setEnabled(False)
        self.pc_thread = QThread(self)
        self.pc_loader = PeakLoader(self.template.path, self.prom.value())
        self.pc_loader.moveToThread(self.pc_thread)
        self.pc_thread.started.connect(self.pc_loader.run)
        self.pc_loader.done.connect(self._pc_peaks_ready)
        self.pc_loader.failed.connect(self._pc_failed)
        self.pc_loader.done.connect(self.pc_thread.quit)
        self.pc_loader.failed.connect(self.pc_thread.quit)
        self.pc_thread.finished.connect(self._pc_thread_done)
        self.pc_thread.start()

    def _pc_failed(self, msg):                                  # slots of the window: they run in the window's thread
        self.pc_factor.setText("Peak correct stopped: see the message.")
        self.error("Peak correct", msg)

    def _pc_finished(self):
        self.set_status(f"Peak correct: {len(self.pc_scans)} corrected version(s) written. Tick one to compare it"
                        + (", then use it in Origin Plot Studio." if self.return_file else "."))

    def _pc_thread_done(self):
        self.pc_thread = None
        self._pc_update()
        self._update_buttons()

    def _pc_peaks_ready(self, peaks):
        self.pc_peaks = peaks
        tb = self.pc_table
        tb.blockSignals(True)
        tb.setRowCount(len(peaks))
        k0 = 0.5 * (self.pc_lo.value() + self.pc_hi.value()) / max(peaks[0]["top"], 1e-9) if peaks else 1.0
        for r, d in enumerate(peaks):
            c = QTableWidgetItem("")
            c.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            c.setCheckState(Qt.Checked if r == 0 else Qt.Unchecked)
            tb.setItem(r, 0, c)
            for col, val in ((1, f"{d['pos']:.3f}"), (2, f"{d['top']:,.0f}")):
                it = QTableWidgetItem(val)
                it.setFlags(Qt.ItemIsEnabled)
                tb.setItem(r, col, it)
            tg = QTableWidgetItem(f"{d['top'] * k0:.0f}")
            tg.setToolTip("The height you want for this peak (counts at its top). Used when 'The ticked peaks to the heights I give' is chosen.")
            tb.setItem(r, 3, tg)
            af = QTableWidgetItem("")
            af.setFlags(Qt.ItemIsEnabled)
            tb.setItem(r, 4, af)
        tb.blockSignals(False)
        self.logline(f"Peak correct: {len(peaks)} peaks of {self.template.filename} with their expected top counts")
        self._pc_update()
        self._pc_plot()

    def pc_factor_now(self):
        """(counting-time factor, why) for the current choice, or raise XrdError."""
        if not self.pc_peaks:
            raise eng.XrdError("The peaks are still being analysed.")
        if self.pc_mode_max.isChecked():
            lo, hi = float(self.pc_lo.value()), float(self.pc_hi.value())
            if hi < lo:
                raise eng.XrdError("The range: the highest must not be below the lowest.")
            return 0.5 * (lo + hi) / self.pc_peaks[0]["top"], f"highest peak to about {0.5 * (lo + hi):,.0f} counts"
        targets = {}
        for r in range(self.pc_table.rowCount()):
            if self.pc_table.item(r, 0).checkState() == Qt.Checked:
                try:
                    tv = float(self.pc_table.item(r, 3).text().replace(",", "").strip())
                except ValueError:
                    raise eng.XrdError(f"The target of the peak at {self.pc_peaks[r]['pos']:.3f}\u00b0 must be a number of counts.")
                if tv <= 0:
                    raise eng.XrdError(f"The target of the peak at {self.pc_peaks[r]['pos']:.3f}\u00b0 must be above 0.")
                targets[r] = tv
        k = eng.factor_for_targets(self.pc_peaks, targets)
        return k, "ticked peaks to their targets: " + ", ".join(f"{self.pc_peaks[r]['pos']:.2f}\u00b0 \u2192 {t:,.0f}" for r, t in targets.items())

    def _pc_update(self):
        if not self.pc_peaks:
            return
        try:
            k, _why = self.pc_factor_now()
        except eng.XrdError as e:
            self.pc_factor.setText(str(e))
            return
        self.pc_table.blockSignals(True)
        for r, d in enumerate(self.pc_peaks):
            self.pc_table.item(r, 4).setText(f"{d['top'] * k:,.0f}")
        self.pc_table.blockSignals(False)
        top = self.pc_peaks[0]["top"] * k
        self.pc_factor.setText(f"Counting time \u00d7{k:.3g} ({'longer' if k >= 1 else 'shorter: binomial thinning'}). "
                               f"The highest peak becomes about {top:,.0f} counts" + ("  (above the usual 10,000)" if top > eng.USUAL_COUNTS[1] and self.pc_mode_sel.isChecked() else "") + ".")

    def peak_correct(self):
        if self.template is None:
            self.error("No template", "Choose a template .xrdml file first.")
            return
        try:
            k, why = self.pc_factor_now()
        except eng.XrdError as e:
            self.error("Peak correct", str(e))
            return
        out = self.out.text().strip() or str(Path(self.template.path).parent / "scans")
        try:
            eng.check_output_folder(out)
        except eng.XrdError as e:
            self.error("Output folder", str(e))
            return
        self.logline(f"--- Peak correct: {self.template.filename}, counting time x{k:.4g} ({why}), {int(self.pc_n.value())} version(s) into {out}")
        self.pc_go.setEnabled(False)
        self.set_status(f"Correcting the peaks (counting time \u00d7{k:.3g}) \u2026")
        self.pc_thread = QThread(self)
        self.pc_worker = PeakCorrector(self.template.path, k, int(self.pc_n.value()), out, why)
        self.pc_worker.moveToThread(self.pc_thread)
        self.pc_thread.started.connect(self.pc_worker.run)
        self.pc_worker.one.connect(self._pc_one)
        self.pc_worker.failed.connect(self._pc_failed)
        self.pc_worker.finished.connect(self._pc_finished)
        self.pc_worker.finished.connect(self.pc_thread.quit)
        self.pc_worker.failed.connect(self.pc_thread.quit)
        self.pc_thread.finished.connect(self._pc_thread_done)
        self.pc_thread.start()

    def _pc_one(self, sc):
        self.pc_scans.append(sc)
        it = QListWidgetItem(f"{sc.sid}   max {int(sc.counts.max()):,}")
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        self.pc_list.blockSignals(True)
        for i in range(self.pc_list.count()):
            self.pc_list.item(i).setCheckState(Qt.Unchecked)
        it.setCheckState(Qt.Checked)
        self.pc_list.addItem(it)
        self.pc_list.blockSignals(False)
        self.scans.append(sc)                                   # also under 'Generated scans' and 'Files'
        g = QListWidgetItem(f"{sc.sid}   max {int(sc.counts.max()):,}")
        g.setFlags(g.flags() | Qt.ItemIsUserCheckable)
        self.scan_list.blockSignals(True)
        g.setCheckState(Qt.Unchecked)
        self.scan_list.addItem(g)
        self.scan_list.blockSignals(False)
        for f in sc.files:
            self._add_file(f)
            self._add_file(str(Path(f).with_name(Path(f).stem + "_provenance.json")))
        self.logline(f"Peak correct: {Path(sc.files[0]).name}, max {int(sc.counts.max()):,} counts")
        self._pc_plot()
        self._update_buttons()

    def _pc_plot(self):
        t = self.template
        if t is None:
            self.pc_plot.empty("The template and its corrected versions appear here")
            return
        for extra in list(self.pc_plot.ax.figure.axes):        # the template's own axis of an earlier view goes
            if extra is not self.pc_plot.ax:
                extra.remove()
        ax = self.pc_plot.begin()
        chosen = [self.pc_scans[i] for i in range(min(self.pc_list.count(), len(self.pc_scans))) if self.pc_list.item(i).checkState() == Qt.Checked]
        labels = []
        if chosen:
            fk = float(np.sum(chosen[0].counts)) / max(float(np.sum(t.y)), 1.0)       # the counting-time factor of these versions
            ax.plot(t.x, t.y * fk, lw=1.0, color="#9CA3AF", alpha=0.85, zorder=1)
            labels.append((f"template \u00d7{fk:.3g}", float(np.median(t.y[-80:] * fk)), "#6B7280"))
            for k, sc in enumerate(chosen):
                col = PALETTE[k % len(PALETTE)]
                ax.plot(sc.x, sc.counts, lw=0.6, color=col, zorder=2 + k)
                labels.append((sc.sid.split("  (")[0].replace(Path(t.path).stem + "_", ""), float(np.median(sc.counts[-80:])), col))
            ax.set_title("Corrected (colour) and the template \u00d7 the same factor (grey)", fontsize=10, loc="left")
        else:
            ax.plot(t.x, t.y, lw=0.6, color="#1E3A8A")
            labels.append(("template", float(np.median(t.y[-80:])), "#1E3A8A"))
            if self.pc_peaks:
                ticked = [d for r, d in enumerate(self.pc_peaks) if self.pc_table.rowCount() > r and self.pc_table.item(r, 0) is not None and self.pc_table.item(r, 0).checkState() == Qt.Checked]
                ax.plot([d["pos"] for d in self.pc_peaks], [d["top"] for d in self.pc_peaks], ls="none", marker="v", ms=4, color="#9CA3AF")
                ax.plot([d["pos"] for d in ticked], [d["top"] for d in ticked], ls="none", marker="v", ms=7, color="#F97316")
            ax.set_title("Template: the ticked peaks are marked orange", fontsize=10, loc="left")
        ax.set_xlim(t.x[0], t.x[-1])
        ax.set_ylim(bottom=0)
        self.pc_plot.end_labels(ax, labels[:8])
        self.pc_plot.finish(right=0.85)

    def pc_use_ticked(self):
        chosen = [self.pc_scans[i] for i in range(min(self.pc_list.count(), len(self.pc_scans))) if self.pc_list.item(i).checkState() == Qt.Checked]
        if not chosen:
            self.error("Tick a scan", "Make a corrected version and tick it in the list first.")
            return
        import json
        Path(self.return_file).write_text(json.dumps({"chosen": [sc.files[0] for sc in chosen]}), encoding="utf-8")
        self.close()

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
        self.pc_scans = []
        self.pc_list.clear()
        self._pc_reset()
        if s["max_counts"] < eng.USUAL_COUNTS[0]:                  # low peaks: the Peak correct tab opens by itself
            self.tabs.setCurrentWidget(self.pc_tab)
        self._pc_maybe_load()
        self.logline(f"Template {s['file']}: sample {s['sample_id']}, {s['points']} points, {s['range'][0]:.3f}-{s['range'][1]:.3f} deg, "
                     f"max {s['max_counts']:.0f} counts, {s['peaks']} peaks, median FWHM {s['median_fwhm']:.3f} deg")
        self.set_status(f"Template ready: {s['sample_id']}. Files will be called {eng.safe_stem(s['sample_id'])}-001, -002, …"
                        + ("  Its peaks are low: see the Peak correct tab." if s["max_counts"] < eng.USUAL_COUNTS[0] else "  Peak correct tab: correct its peaks." if s["max_counts"] > eng.USUAL_COUNTS[1] else ""))

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
                            dropout=float(self.dropout.value()), prominence=float(self.prom.value()), bg_mode=self.bg_mode.currentData(),
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
        self.bar.setRange(0, s.n + (max(1, min(s.n, 5)) if self.return_file and self.better.isChecked() else 0))
        self.bar.setValue(0)
        self.logline(f"--- generating {s.n} scan(s) into {s.out_dir} (seed {s.seed if s.seed is not None else 'random'})")
        self.thread = QThread(self)
        self.worker = BetterWorker(s, self.template, self.better.isChecked()) if self.return_file else Worker(s, self.template)
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
        if self.return_file and r.scans:
            self.set_status(self.status.text() + "  Tick the one(s) you like and press 'Use the ticked scans in Origin Plot Studio'.")

    def _failed(self, msg):
        self.set_status("Generation stopped: see the message.")
        self.logline("ERROR: " + msg)
        self.error("Generation stopped", msg + ("\n\nFiles written before the error are kept." if self.scans else ""))

    def _thread_done(self):
        self.worker = None
        self.thread = None
        self._update_buttons()

    def busy(self):
        return (self.thread is not None and self.thread.isRunning()) or (getattr(self, "load_thread", None) is not None and self.load_thread.isRunning()) \
            or (getattr(self, "pc_thread", None) is not None and self.pc_thread.isRunning())

    def ticked(self):
        return [self.scans[i] for i in range(min(self.scan_list.count(), len(self.scans))) if self.scan_list.item(i).checkState() == Qt.Checked]

    def use_ticked(self):
        """Origin Plot Studio goes on with the ticked scans (written to the return file, then the window closes)."""
        chosen = self.ticked()
        if not chosen:
            self.error("Tick a scan", "Tick the scan(s) you want in the list under 'Generated scans' first.")
            return
        import json
        Path(self.return_file).write_text(json.dumps({"chosen": [sc.files[0] for sc in chosen]}), encoding="utf-8")
        self.close()

    def _update_buttons(self):
        if not hasattr(self, "go"):
            return                      # still building the window
        running = self.thread is not None and self.thread.isRunning()
        loading = getattr(self, "load_thread", None) is not None and self.load_thread.isRunning()
        self.go.setEnabled(not running and not loading and self.template is not None and self.phases.rowCount() > 0)
        self.cancel.setEnabled(running)
        self.add_tpl_btn.setEnabled("template" not in self._phase_names())
        for wdg in (self.n, self.p_lo, self.p_hi, self.c_lo, self.c_hi, self.seed, self.out, self.phases, self.ij, self.pj, self.dropout, self.prom, self.want_preview, self.better, self.bg_mode):
            wdg.setEnabled(not running)
        if hasattr(self, "pc_go"):
            pc_busy = getattr(self, "pc_thread", None) is not None
            self.pc_go.setEnabled(not running and not loading and not pc_busy and bool(self.pc_peaks))
            if hasattr(self, "pc_use"):
                self.pc_use.setEnabled(not pc_busy and bool(self.pc_scans))
        for wdg in (getattr(self, "use_btn", None), getattr(self, "use_btn2", None)):
            if wdg is not None:
                wdg.setEnabled(not running and bool(self.scans))

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
        for lt in (getattr(self, "load_thread", None), getattr(self, "pc_thread", None)):
            if lt is not None and lt.isRunning():
                lt.wait(30000)
        e.accept()


def parent_alive(pid):
    """Is the program that opened this window (Origin Plot Studio) still running?"""
    try:
        if os.name == "nt":
            import ctypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, int(pid))            # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return code.value == 259                                # STILL_ACTIVE
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


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
    args = sys.argv[1:]
    ret = args[args.index("--return") + 1] if "--return" in args and args.index("--return") + 1 < len(args) else None
    w = MainWindow(return_file=ret, better="--better" in args)
    if ret:
        w.setWindowTitle(APP_TITLE + "  \u2013  Origin Plot Studio")
    w.show()
    if "--parent" in args and args.index("--parent") + 1 < len(args):     # opened by Origin Plot Studio: close together with it
        from PySide6.QtCore import QTimer
        ppid = args[args.index("--parent") + 1]
        def watch():
            if not parent_alive(ppid):
                if w.worker is not None:
                    w.worker.stop.set()
                if w.thread is not None:
                    w.thread.quit(); w.thread.wait(30000)
                app.quit()
        w._parent_timer = QTimer(w, interval=2000, timeout=watch)
        w._parent_timer.start()
    tpl = next((a for a in args if a.lower().endswith(".xrdml")), None)
    if tpl:
        w.set_template(tpl)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

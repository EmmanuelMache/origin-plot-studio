"""Origin Plot Studio - modern window, step 3: the Analysis and Graph gallery sections run their tools here.

Every entry calls the same code as the current window:
  data-analysis tools   origin_plot_app.save_analysis (analysis_tools.run + CSV, results and provenance files)
  XRD                   the XRD Scan Generator app (xrd_scan_generator_app.py), as XRD tools in the current window opens it
  TGA                   smart_plots.analyze_tga_steps
  Calorimetry           calorimetry.run (mass, reaction start, exclusion window, figures C1-C5)
  Graph gallery         Item.build with the gallery kind; gallery_graphs.make_template for a template from a raw file
Nothing here changes your numbers; new results are new files in the results folder.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (QToolButton, QFrame, QListWidget, QListWidgetItem, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QPushButton, QTableView, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

import smart_plots as sp

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------------------------- what the sections hold
XRD_DRAW = [        # drawing comes first; correcting and generating scans is its own group after it
    ("Decide for me (fits and patterns)", "The ticked XRD graphs, drawn the way the app thinks best: up to 4 Rietveld / HighScore fits as one panel "
     "each (observed, calculated, difference below, and the zoomed part); more than 4 stacked; patterns stacked.", "Group: Decide for me",
     {"do": "xrd_auto"}),
    ("Sample pages: pattern with labelled peaks + fit + zoom", "One page per sample when a fit (Iobs / Icalc / Iback) and a peak list "
     "(Assignment, h k l, Height) of that sample are loaded: (a) the pattern with its peaks labelled from the peak list, (b) the fit with the "
     "difference below and the zoomed region of the main peaks. Made by the app as soon as both files are in.", "Your graphs: ★ Sample page",
     {"do": "hs_page"}),
    ("Zoomed part (inset): on or off", "Include the zoomed part or not, for the ticked XRD graphs (or the one on show): on - the app chooses the "
     "crowded region of the main peaks, or the 2θ range you type - or off. For every graph at once: Settings > XRD > Zoomed part.",
     "Ribbon: Graph > Zoomed part", {"do": "zoom"}),
    ("Fits: observed, calculated, difference (one panel each)", "The ticked fits, one panel each, sharing the 2θ axis: observed, calculated, "
     "the difference below, the main peaks labelled from the peak list and, up to 4 panels, the zoomed part of each.", "Group: Panels",
     {"do": "group", "how": "panels", "kind": "Fit"}),
    ("Fits without the fitted curve, stacked", "Only the observed pattern of each ticked fit, one above the other with an offset (peaks "
     "labelled from the peak list).", "Group: Stack them", {"do": "group", "how": "stack", "kind": "Fit"}),
    ("Fits without the fitted curve, overlaid", "Only the observed pattern of each ticked fit, on common axes.", "Group: Overlay them",
     {"do": "group", "how": "overlay", "kind": "Fit"}),
    ("XRD patterns stacked", "The ticked XRD patterns one above the other with an offset, peaks labelled.", "Group: Stack them",
     {"do": "group", "how": "stack", "kind": "XRD"}),
    ("XRD patterns overlaid", "The ticked XRD patterns on common axes.", "Group: Overlay them", {"do": "group", "how": "overlay", "kind": "XRD"}),
    ("Which peak list goes with which pattern", "A table: every peak list, the pattern or fit it was put with, and why (the same sample "
     "name, or the listed peaks sitting on the pattern's peaks, with the agreement), and the phases that are listed but not drawn.",
     "Details", {"do": "hs_match"}),
]


def _analysis_tree_core():
    """(group, [(name, what it does, where it is in the current window, action)]) - your techniques first, then the 44 tools."""
    out, general = [], []
    try:
        import analysis_tools as at
        for g in at.GROUPS:
            general.append((g, [(lab, str(t[3]), f"Analysis > {g} > {lab}", {"do": "tool", "label": lab}) for lab, t in at.TOOLS.items() if t[0] == g]))
    except Exception:
        pass
    out.append(("XRD", XRD_DRAW))
    out.append(("XRD: correct and generate scans", [
        ("XRD Scan Generator", "Generate XRD scans from a template scan, and correct peaks (Peak correct tab). The scans you send back "
         "come to Your graphs.", "XRD tools > XRD Scan Generator (app)", {"do": "xrd", "better": False}),
        ("Peak correct / improve a scan", "Better versions of the ticked .xrdml scan, whatever its counts: count longer, correct the peaks you "
         "choose. You compare and choose; the original file is never changed.", "XRD tools > Peak correct / improve an XRD scan", {"do": "xrd", "better": True}),
        ("Phase library", "The phases the app knows (built in, stored from your files, added by you), used for peak suggestions.",
         "XRD tools > Phase library", {"do": "library"})]))
    out.append(("TGA", [("Mass loss in temperature intervals", "Mass loss of each TGA graph in the temperature intervals of Settings > TGA "
                         "(or the app's standard intervals), with the total and the residue.", "Analysis > TGA: mass loss in temperature intervals",
                         {"do": "tga"})]))
    out.append(("FTIR", [
        ("Read as absorbance (bands are maxima)", "For the ticked FTIR graphs: the signal is absorbance, so the bands are found and labelled at the "
         "maxima. Only how the graph is read changes; your numbers stay.", "Analysis settings > FTIR signal", {"do": "ftir_read", "signal": "Absorbance"}),
        ("Read as transmittance (bands are minima)", "For the ticked FTIR graphs: the signal is transmittance, so the bands are found and "
         "labelled at the minima.", "Analysis settings > FTIR signal", {"do": "ftir_read", "signal": "Transmittance"}),
        ("Read automatically (from the header and values)", "The app decides from the column header and the values, as it does when a file "
         "is read.", "Analysis settings > FTIR signal", {"do": "ftir_read", "signal": ""}),
        ("Transmittance to absorbance (new curve)", "A = -log10(T), T in % or 0-1. The new spectrum comes to Your graphs.",
         "Analysis > Transform and convert > FTIR: transmittance to absorbance", {"do": "tool", "label": "FTIR: transmittance to absorbance"}),
        ("Absorbance to transmittance (new curve)", "%T = 100·10^-A. The new spectrum comes to Your graphs.",
         "Analysis > Transform and convert > FTIR: absorbance to transmittance", {"do": "tool", "label": "FTIR: absorbance to transmittance"}),
        ("Band areas in wavenumber regions", "The area of each region you list (from-to, and a name if you like), on a straight-line baseline "
         "between the region's ends; transmittance is turned into absorbance first. One table for all ticked spectra.",
         "Analysis > Calculus > Area between two x values (one region at a time)", {"do": "ftir_areas"}),
        ("Wavenumber to wavelength (new curve)", "µm = 10⁴ / cm⁻¹.", "Analysis > Transform and convert > FTIR: wavenumber to wavelength",
         {"do": "tool", "label": "FTIR: wavenumber to wavelength"})]))
    out.append(("Peak labels", [
        ("Label peaks automatically", "Finds the peaks (or the bands) of the ticked graphs and labels them with their positions. The labels are "
         "numbers only - never a guessed phase - and go to Origin and the publication files with the graph.", "Analysis settings > peak labels",
         {"do": "labels_auto"}),
        ("Remove the automatic labels", "Takes the automatic labels off the ticked graphs; labels from your own files stay.", "", {"do": "labels_clear"})]))
    out.append(MODELLING)
    out.append(("Particle size (PSD)", psd_rows()))
    out.append(("Calorimetry", [("Calorimetry (TAM III): workbook and figures C1–C5", "One row per sample: the mass is required; label, regime and "
                                 "alite fraction are optional. Reaction start, exclusion window (45 min), heat flow in mW/g, cumulative heat in J/g, "
                                 "then figures C1–C5.", "Analysis > Calorimetry (TAM III)", {"do": "calo"})]))
    out.append(("Phases and composition", [
        ("Hydration degree from phase amounts (C01)", "Degree of hydration from the phase contents of the ticked workbook.",
         "Analysis > Hydration degree (C01)", {"do": "figtype", "type": "C01"}),
        ("Atomic ratios (C02)", "Atomic ratios from the oxide contents of the ticked workbook.", "Analysis > Atomic ratios (C02)", {"do": "figtype", "type": "C02"})]))
    return out + general


FIGURE_STYLES = [("FTIR", [("FTIR spectra stacked (offset)", "The ticked FTIR spectra in one figure, one above the other, the usual way to "
                             "compare bands. Read as absorbance or transmittance: Analysis > FTIR.", "Group: Stack them", {"do": "group", "how": "stack", "kind": "FTIR"}),
                            ("FTIR spectra overlaid", "The ticked FTIR spectra on common axes.", "Group: Overlay them", {"do": "group", "how": "overlay", "kind": "FTIR"})]),
                 ("XRD, TGA and other figures", [("Stack the ticked graphs", "The ticked graphs of one kind in one figure with an offset.", "Group: Stack them",
                                                  {"do": "group", "how": "stack", "kind": ""}),
                                                 ("Overlay the ticked graphs", "The ticked graphs of one kind on common axes.", "Group: Overlay them",
                                                  {"do": "group", "how": "overlay", "kind": ""})])]

MODEL_INFO = ("Read as they are, nothing calculated: tables of phase amounts from GEMS (GEM-Selektor, CEMGEMS), FactSage (Equilib "
              "results exported to Excel or CSV), Thermo-Calc (NP(...), NPM(...), BPW(...) columns), HCh, PHREEQC selected output (.sel) "
              "and any table with an ordered column (temperature, time, replacement level ...) and columns named like phases. Units in "
              "the headers (g, mol, wt%, cm3/100 g) are kept.")
SOFTWARE = ["Automatic (from the file)", "GEMS (GEM-Selektor)", "CEMGEMS", "GEMS3K", "FactSage", "Thermo-Calc", "PHREEQC", "HCh", "Perple_X",
            "OLI Studio", "MTDATA", "ChemApp / ChemSheet", "Thermo-Calc (TC-Python)", "Other (type its name)"]
SOFTWARE_NOTES = {
    "GEMS (GEM-Selektor)": "Read: tables exported from GEM-Selektor (Process / graph data saved as text or CSV): a time, temperature or composition column "
                           "and one column per phase (g, mol, cm3/100 g ...). Usual databases: CEMDATA18, PSI-Nagra.",
    "CEMGEMS": "Read: the CSV / Excel tables CEMGEMS exports (phase volumes or masses against time, composition or temperature).",
    "GEMS3K": "Read: tables written from GEMS3K results (one row per step, one column per phase).",
    "FactSage": "Read: Equilib results exported to Excel or CSV (T and one column per phase, e.g. g-Slag-liq#1). Usual databases: FToxid, FactPS. "
                "The plain text report is not read: export the table.",
    "Thermo-Calc": "Read: tables with NP(...), NPM(...), BPW(...), VPV(...) columns against T (the phase names are taken from inside the brackets).",
    "Thermo-Calc (TC-Python)": "Read: the tables your TC-Python script writes (CSV / Excel), named like NP(...) or by phase.",
    "PHREEQC": "Read: SELECTED_OUTPUT files (.sel): the EQUILIBRIUM_PHASES amounts against time or step; saturation indices (si_), solution (m_, tot_) "
               "and pH / pe as their own graphs.",
    "HCh": "Read: tables exported from HCh (one column per phase or species).",
    "Perple_X": "Read: WERAMI tables saved as CSV or Excel with one header row (one column per phase). Not tested with your own files yet: "
                "if one is not recognised, send a sample.",
    "OLI Studio": "Read: survey tables exported to Excel / CSV (a temperature or composition column, one column per solid or species).",
    "MTDATA": "Read: tables exported to CSV / Excel.", "ChemApp / ChemSheet": "Read: the result tables of your ChemApp program or ChemSheet workbook."}

MODELLING = ("Thermodynamic modelling", [
    ("Program and database used", "Say which program (and database) calculated the ticked tables: GEMS, CEMGEMS, FactSage, Thermo-Calc, PHREEQC, HCh, "
     "Perple_X, OLI, MTDATA, ChemApp and others. It is written under the figure (in Origin and the publication files), in the processing "
     "record and in the session.", "", {"do": "thermo_software"}),
    ("Phase assemblage (stacked areas)", "Phases stacked on each other against temperature, time or composition; the top line is the total. "
     + MODEL_INFO, "Analysis settings > own graph > Phase assemblage", {"do": "thermo_chart", "style": "Phase assemblage (stacked areas)"}),
    ("Phase amounts (lines)", "One line per phase. " + MODEL_INFO, "own graph > Phase amounts", {"do": "thermo_chart", "style": "Phase amounts (lines)"}),
    ("Phase assemblage per composition (stacked bars)", "One bar per composition or run, the phases stacked. " + MODEL_INFO, "own graph",
     {"do": "thermo_chart", "style": "Phase assemblage (stacked bars)"}),
    ("Change against the first row", "How much each phase changes against the first composition or run. " + MODEL_INFO, "own graph",
     {"do": "thermo_chart", "style": "Change against the first row"}),
    ("Pore solution (logarithmic)", "Concentrations of the pore solution (GEMS, PHREEQC, measured), on a logarithmic axis.", "own graph",
     {"do": "thermo_chart", "style": "Pore solution (logarithmic)"}),
    ("Saturation indices", "The saturation indices of the model (si_ columns of PHREEQC, SI columns of GEMS) as a new graph: above 0 "
     "oversaturated, below 0 undersaturated.", "", {"do": "thermo_extract", "what": "si"}),
    ("Solution composition", "The concentrations in solution (m_ / tot_ columns, molal, mol/kg, mmol/l) as a new graph.", "", {"do": "thermo_extract", "what": "solution"}),
    ("pH, pe and Eh", "pH, pe and Eh of the model as a new graph.", "", {"do": "thermo_extract", "what": "ph"})])

PSD_DRAW = [("Draw as: distribution and cumulative in one graph", "The usual way: logarithmic size axis, the distribution (volume %) on the left "
             "axis, the cumulative passing (%) on the right axis, D10, D50 and D90 marked.", sp.PSD_STYLES[0]),
            ("Draw as: two panels (distribution above, cumulative below)", "Distribution and cumulative curve in two panels on the same size axis.", sp.PSD_STYLES[1]),
            ("Draw as: cumulative only", "The cumulative passing curve with D10, D50, D90.", sp.PSD_STYLES[2]),
            ("Draw as: distribution only", "The distribution (volume %) with D10, D50, D90.", sp.PSD_STYLES[3])]


def psd_rows(where="Analysis"):
    rows = [("Characteristic sizes: D10, D50, D90, span, mode", "One table for all ticked PSDs: D10, D50 and D90 from the cumulative curve (log "
             "interpolation), span = (D90 - D10)/D50, and the mode (peak of the distribution). Saved as CSV.", "the Results tab of each PSD", {"do": "psd_sizes"}),
            ("RRSB fit (Rosin-Rammler-Sperling-Bennett)", "The usual description of cement and powder fineness: position parameter x' (size at 63.2 % passing) "
             "and slope n, fitted on the cumulative curve between 5 and 95 %, with R². Saved as CSV.", "", {"do": "psd_rrsb"})]
    rows += [(t, w, "Settings > Particle size", {"do": "psd_style", "style": st}) for t, w, st in PSD_DRAW]
    rows += [("Overlay the ticked PSDs (one figure)", "The ticked particle size distributions of your samples in one figure: distributions above, "
              "cumulative curves below, one colour per sample.", "Group: Overlay", {"do": "group", "how": "overlay", "kind": "Particle size"})]
    return rows


GALLERY_GROUPS = [("XRD", ["G01", "G02", "G03", "G09", "G24"]), ("NMR", ["G04", "G05", "G06"]), ("TGA", ["G07", "G08", "G09"]),
                 ("Calorimetry", ["G10", "G11"]), ("Phases and composition", ["G12", "G15", "G21", "G22", "G23", "C01", "C02"]),
                 ("Particle size", ["G20"]), ("General plots", ["G13", "G14", "G16", "G17", "G18", "G19"])]


def analysis_tree():
    """Everything that works on your loaded graphs, once: the analyses, and the figures from several graphs (stack / overlay)."""
    out = [(g, list(rows)) for g, rows in _analysis_tree_core()]
    for g, rows in out:
        if g == "FTIR": rows[0:0] = FIGURE_STYLES[0][1]                       # FTIR: the stacked / overlaid figures first
    return out + [("Figures from several graphs", list(FIGURE_STYLES[1][1]))]


def figtype_tree():
    try:
        import gallery_graphs as tg
        types = tg.TYPES
    except Exception:
        return []
    th = [(g, [(f"{c}  {types[c][1]}", f"{c} ({types[c][0]}): {types[c][1]}.", "File > Make a gallery graph template",
                {"do": "figtype", "type": c}) for c in codes if c in types]) for g, codes in GALLERY_GROUPS]
    return [(g, rows) for g, rows in th if rows]          # only the 26 workbook graph types here: the analyses (XRD drawing, FTIR, particle size, modelling ...) are in Analysis, once


# ---------------------------------------------------------------------------------------------- the page
class StatusLabel(QLabel):
    """The message under Run, coloured by what it says: red for a failure, amber for something to do first, green when done."""
    ERR = re.compile(r"(?i)(could not|cannot|failed|error|invalid|not drawn|not read|did not work|went wrong)")
    WARN = re.compile(r"(?i)(^tick |tick the|tick two|nothing |^no |choose |first\b|missing|needs? )")
    OK = re.compile(r"(?i)(written|made|drawn|saved|done|added|opened|applied|shown|changed|figure made|stacked|overlaid|grouped)")

    def setText(self, t):
        t = str(t)
        kind = "error" if self.ERR.search(t) else "warn" if self.WARN.search(t) else "ok" if self.OK.search(t) else "soft"
        col = {"error": "#B91C1C", "warn": "#A16207", "ok": "#15803D", "soft": "#526277"}[kind]
        self.setStyleSheet(f"color: {col};" + (" font-weight: 600;" if kind in ("error", "warn") else ""))
        self.kind = kind
        return super().setText(t)


class ToolPage(QWidget):
    """Left: the groups and entries, with a search box. Right: the chosen entry - what it does, its settings, Run, and its results."""

    def __init__(self, ws, label, text, groups):
        super().__init__()
        self.ws, self.label, self.groups_ = ws, label, groups
        from PySide6.QtWidgets import QMainWindow, QScrollArea, QTabWidget
        from workspace_qt import DataFrameModel
        figtype = label.startswith("Graph gallery")
        slug = "figtype" if figtype else "analysis"
        outer = QVBoxLayout(self); outer.setContentsMargins(8, 8, 8, 8)
        self.main = QMainWindow(); self.main.setObjectName(f"{slug}Main"); self.main.setDockNestingEnabled(True)
        self.main.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks)
        outer.addWidget(self.main)
        # ---- the browser: categories and entries, searchable
        bw = QWidget(); bl = QVBoxLayout(bw); bl.setContentsMargins(10, 10, 10, 10)
        t = QLabel(text, objectName="soft"); t.setWordWrap(True); bl.addWidget(t)
        self.find = QLineEdit(placeholderText=f"Find in {label} …"); bl.addWidget(self.find)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True)
        for g, rows in groups:
            top = QTreeWidgetItem([f"{g}  ({len(rows)})"])
            fnt = top.font(0); fnt.setBold(True); top.setFont(0, fnt)
            top.setData(0, Qt.UserRole + 2, g)
            for row in rows:
                c = QTreeWidgetItem([row[0]]); c.setData(0, Qt.UserRole, row); c.setToolTip(0, str(row[1])[:300])
                top.addChild(c)
            self.tree.addTopLevelItem(top)
        self.tree.expandAll()
        bl.addWidget(self.tree, 1)
        bw.setMinimumWidth(230)
        # ---- the setup: workflow, the files it works on (and their columns), the settings, Run, messages
        sw = QWidget(); self.dl = QVBoxLayout(sw); self.dl.setContentsMargins(14, 10, 14, 10); self.dl.setSpacing(8)
        flow = QHBoxLayout(); flow.setSpacing(2)
        self.steps = []
        for i, (st, tip, fn) in enumerate((("Choose", "Choose an analysis or graph type in the browser", lambda: self.tree.setFocus()),
                                           ("Files", "Add or select the files to work on", lambda: ws.add_files(tick=True)),
                                           ("Inspect", "See the data of the chosen file", lambda: self.show_preview_tab("Data")),
                                           ("Configure", "Set the settings below", lambda: self.formbox.setFocus()),
                                           ("Preview", "See the result before anything else", lambda: self.show_preview_tab("Preview")),
                                           ("Workspace", "Edit the graph in Workspace", lambda: ws.go(0)),
                                           ("Export", "Publication files or Origin (Workspace › Export / Draw in Origin)", lambda: (ws.go(0), ws.export_btn.showMenu() if hasattr(ws, "export_btn") else None)))):
            b_ = QToolButton(); b_.setText(f"{i + 1} {st}"); b_.setToolTip(tip); b_.setCheckable(True); b_.clicked.connect(lambda _c=False, f=fn: f()); b_.setObjectName("step")
            flow.addWidget(b_); self.steps.append(b_)
            if i < 6:
                flow.addWidget(QLabel("›", objectName="soft"))
        flow.addStretch(1)
        fw = QFrame(objectName="card"); fw.setLayout(flow); flow.setContentsMargins(10, 4, 10, 4)
        outer.insertWidget(0, fw)
        self.title = QLabel("Choose an entry in the browser.", objectName="h2"); self.title.setWordWrap(True); self.dl.addWidget(self.title)
        self.info = QLabel("", objectName="soft"); self.info.setWordWrap(True); self.info.setTextInteractionFlags(Qt.TextSelectableByMouse); self.dl.addWidget(self.info)
        inb = QFrame(objectName="card"); il = QVBoxLayout(inb); il.setContentsMargins(10, 8, 10, 8)
        il.addWidget(QLabel("Files and data", objectName="h3"))
        ih = QHBoxLayout()
        up = QPushButton("Add files…"); up.setToolTip("Add data files here: they come to Your graphs, ticked, so this works on them. You can also drop files on the window.")
        up.clicked.connect(lambda: ws.add_files(tick=True)); ih.addWidget(up)
        gw = QPushButton("Choose in Workspace"); gw.setToolTip("Tick the graphs to work on in Your graphs"); gw.clicked.connect(lambda: ws.go(0)); ih.addWidget(gw); ih.addStretch(1)
        il.addLayout(ih)
        self.workson = QLabel("", objectName="soft"); self.workson.setWordWrap(True); il.addWidget(self.workson)
        self.inputs = QTableWidget(0, 3); self.inputs.setHorizontalHeaderLabels(["File", "Kind", "Columns"])
        self.inputs.verticalHeader().hide(); self.inputs.setEditTriggers(QTableWidget.NoEditTriggers); self.inputs.setSelectionBehavior(QTableWidget.SelectRows)
        self.inputs.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents); self.inputs.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.inputs.horizontalHeader().setStretchLastSection(True); self.inputs.setMaximumHeight(130); self.inputs.setStyleSheet("font-family: 'Segoe UI'; font-size: 9pt;")
        self.inputs.itemSelectionChanged.connect(self.input_chosen)
        il.addWidget(self.inputs)
        self.dl.addWidget(inb)
        self.formbox = QWidget(); self.form = QFormLayout(self.formbox); self.form.setContentsMargins(0, 6, 0, 6)
        self.form.setRowWrapPolicy(QFormLayout.WrapLongRows); self.form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.dl.addWidget(self.formbox)
        self.extra = QVBoxLayout(); self.dl.addLayout(self.extra)
        brow = QHBoxLayout(); self.buttons = QHBoxLayout(); brow.addLayout(self.buttons, 1)
        self.stop_btn = QPushButton("■  Stop", objectName="stop"); self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("Stop the run in progress: nothing of it comes to Your graphs")
        self.stop_btn.clicked.connect(self.stop_run); brow.addWidget(self.stop_btn)
        self.dl.addLayout(brow)
        self._stop_timer = QTimer(self); self._stop_timer.setInterval(250); self._stop_timer.timeout.connect(self.update_stop)
        self.msg = StatusLabel(""); self.msg.setWordWrap(True); self.msg.setTextInteractionFlags(Qt.TextSelectableByMouse); self.dl.addWidget(self.msg)
        self.dl.addStretch(1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(sw); scroll.setMinimumWidth(320)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # ---- preview and results: the user's data (or an illustration, clearly labelled), the data table, the results
        pw = QWidget(); pl = QVBoxLayout(pw); pl.setContentsMargins(8, 8, 8, 8)
        self.ptabs = QTabWidget()
        pv = QWidget(); pvl = QVBoxLayout(pv); pvl.setContentsMargins(0, 4, 0, 0)
        self.pcaption = QLabel("", objectName="soft"); self.pcaption.setWordWrap(True); pvl.addWidget(self.pcaption)
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        self.pfig = Figure(figsize=(5.6, 4.0), dpi=90, facecolor="white"); self.pcanvas = FigureCanvasQTAgg(self.pfig)
        from workspace_shell import AspectBox
        self.pbox = AspectBox(self.pcanvas); pvl.addWidget(self.pbox, 1)
        self.pimage = QLabel(); self.pimage.setAlignment(Qt.AlignCenter); self.pimage.hide(); pvl.addWidget(self.pimage, 1)
        ob = QHBoxLayout(); ob.addStretch(1)
        self.open_ws = QPushButton("Open in Workspace", objectName="teal"); self.open_ws.setToolTip("Edit this graph in Workspace (formatting, export, Origin)")
        self.open_ws.clicked.connect(self.open_in_workspace); ob.addWidget(self.open_ws); pvl.addLayout(ob)
        self.ptabs.addTab(pv, "Preview")
        self.dmodel = DataFrameModel(); self.dview = QTableView(); self.dview.setModel(self.dmodel); self.ptabs.addTab(self.dview, "Data")
        self.resmodel = DataFrameModel()
        self.restable = QTableView(); self.restable.setModel(self.resmodel)
        self.restable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.ptabs.addTab(self.restable, "Results")
        pl.addWidget(self.ptabs)
        # ---- the gallery: a picture of each graph type (Graph gallery) or of each kind of analysis
        self.gallery = QListWidget(); self.gallery.setViewMode(QListWidget.IconMode); self.gallery.setIconSize(QSize(210, 146))
        self.gallery.setResizeMode(QListWidget.Adjust); self.gallery.setMovement(QListWidget.Static); self.gallery.setSpacing(8); self.gallery.setWordWrap(True)
        self.gallery.setGridSize(QSize(236, 214)); self.gallery.setStyleSheet("QListWidget::item { border: 1px solid #D8E1EC; border-radius: 8px; background: white; } "
                                                                         "QListWidget::item:selected { border: 2px solid #2563EB; background: #EAF2FF; color: #172B4D; }")
        self.gallery.itemClicked.connect(self.gallery_chosen)
        mk = ws._panel_dock
        self.browser_dock = mk("Graph types" if figtype else "Analyses", f"{slug}BrowserDock", bw, Qt.LeftDockWidgetArea, self.main)
        self.config_dock = mk("Setup", f"{slug}SetupDock", scroll, Qt.RightDockWidgetArea, self.main)
        self.preview_dock = mk("Preview and results", f"{slug}PreviewDock", pw, Qt.RightDockWidgetArea, self.main)
        self.gallery_dock = mk("Gallery", f"{slug}GalleryDock", self.gallery, Qt.RightDockWidgetArea, self.main)
        for d in (self.config_dock, self.preview_dock, self.gallery_dock):
            self.main.removeDockWidget(d)
        if figtype:          # categories | gallery | setup over preview
            self.main.addDockWidget(Qt.RightDockWidgetArea, self.gallery_dock)
            self.main.splitDockWidget(self.gallery_dock, self.config_dock, Qt.Horizontal)
            self.main.splitDockWidget(self.config_dock, self.preview_dock, Qt.Vertical)
            self.main.resizeDocks([self.browser_dock, self.gallery_dock, self.config_dock], [260, 760, 440], Qt.Horizontal)
        else:               # analyses | setup | preview (the gallery behind the preview)
            self.main.addDockWidget(Qt.RightDockWidgetArea, self.config_dock)
            self.main.splitDockWidget(self.config_dock, self.preview_dock, Qt.Horizontal)
            self.main.tabifyDockWidget(self.preview_dock, self.gallery_dock)
            self.main.resizeDocks([self.browser_dock, self.config_dock, self.preview_dock], [280, 470, 640], Qt.Horizontal)
        for d in (self.config_dock, self.preview_dock, self.gallery_dock):
            d.show()
        self.preview_dock.raise_()
        self.docks = [self.browser_dock, self.config_dock, self.preview_dock, self.gallery_dock]
        self.saved_forms = {}
        self.fill_gallery()
        ws.list.itemChanged.connect(lambda _i: self.update_workson())
        ws.list.currentRowChanged.connect(lambda _r: self.update_workson())
        ws.list.model().rowsInserted.connect(lambda *_a: self.update_workson())
        ws.list.model().modelReset.connect(lambda *_a: self.update_workson())
        self.tree.currentItemChanged.connect(self.choose)
        self.tree.itemClicked.connect(self.group_clicked)
        self.find.textChanged.connect(self.filter)
        self.fields, self.entry, self.calo_table = {}, None, None
        self.update_workson()

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_sized", False):                     # the first time it is seen: sensible widths, and the first entry open
            self._sized = True
            W = max(900, self.width())
            if getattr(self, "_restored", False):
                pass                                                 # your own arrangement from the last session stays
            elif self.label.startswith("Graph gallery"):
                self.main.resizeDocks([self.browser_dock, self.gallery_dock, self.config_dock], [int(W * 0.18), int(W * 0.47), int(W * 0.35)], Qt.Horizontal)
            else:
                self.main.resizeDocks([self.browser_dock, self.config_dock, self.preview_dock], [int(W * 0.22), int(W * 0.36), int(W * 0.42)], Qt.Horizontal)
            if self.tree.currentItem() is None and self.tree.topLevelItemCount() and self.tree.topLevelItem(0).childCount():
                self.tree.setCurrentItem(self.tree.topLevelItem(0).child(0))
        self.update_workson()

    def running(self):
        ws = self.ws
        return getattr(ws, "job_thread", None) is not None or bool(getattr(self, "_busy_sync", False))

    def update_stop(self):
        """Stop is there while a run is going (and greyed when nothing runs)."""
        try:
            on = self.running() and not self.ws.cancel[0]
            self.stop_btn.setEnabled(on)
            if not self.running() and not self.isVisible():
                self._stop_timer.stop()
        except RuntimeError:
            pass

    def stop_run(self):
        """Stop: the run in progress ends at its next step; what it made is not kept."""
        if not self.running():
            return "nothing to stop"
        self.ws.cancel[0] = True
        self.stop_btn.setEnabled(False)
        self.msg.setText("Stopping - nothing of this run will be kept …")
        self.ws.set_status("Stopping …")
        return "stopping"

    # ------------------------------------------------------------------ the preview panel, the gallery, the inputs
    def show_preview_tab(self, name):
        for i in range(self.ptabs.count()):
            if self.ptabs.tabText(i) == name:
                self.ptabs.setCurrentIndex(i)
        self.preview_dock.show(); self.preview_dock.raise_()

    def gallery_image(self, key):
        p = HERE / "gallery" / f"{key}.png"
        return str(p) if p.exists() else None

    def fill_gallery(self, group=None):
        """Graph gallery: a picture of each type (of the chosen category, or all); Analysis: one per kind of analysis."""
        from PySide6.QtGui import QIcon
        self.gallery.clear()
        figtype = self.label.startswith("Graph gallery")
        for g, rows in self.groups_:
            if figtype:
                if group and g != group:
                    continue
                for row in rows:
                    code = (row[3] or {}).get("type")
                    img = self.gallery_image(f"type_{code}") if code else None
                    if not img:
                        continue
                    it = QListWidgetItem(QIcon(img), row[0].replace("  ", "\n", 1)); it.setData(Qt.UserRole, row[0]); it.setToolTip(str(row[1]))
                    self.gallery.addItem(it)
            else:
                img = self.gallery_image("analysis_" + re.sub(r"[^a-z0-9]+", "_", g.lower()).strip("_"))
                if not img:
                    continue
                it = QListWidgetItem(QIcon(img), f"{g}\n({len(rows)})"); it.setData(Qt.UserRole + 2, g); it.setToolTip(f"{g}: {len(rows)} entries")
                self.gallery.addItem(it)
        return self.gallery.count()

    def gallery_chosen(self, item):
        """A click on a picture opens that type (or the first entry of that kind of analysis) at once."""
        name, g = item.data(Qt.UserRole), item.data(Qt.UserRole + 2)
        if name:
            hit = self.find_entry(name)
        else:
            top = next((self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount()) if self.tree.topLevelItem(i).data(0, Qt.UserRole + 2) == g), None)
            hit = top.child(0) if top is not None and top.childCount() else None
        if hit is not None:
            self.tree.setCurrentItem(hit)
        return hit

    def group_clicked(self, item, _col=0):
        """A click on a category opens its first entry (no separate step), and the gallery shows that category."""
        if item.data(0, Qt.UserRole) is None and item.childCount():
            if self.label.startswith("Graph gallery"):
                self.fill_gallery(item.data(0, Qt.UserRole + 2))
            self.tree.setCurrentItem(item.child(0))

    def input_chosen(self):
        rows = sorted({i.row() for i in self.inputs.selectedIndexes()})
        its = getattr(self, "_inputs", [])
        if rows and rows[0] < len(its):
            self.preview_item(its[rows[0]])

    def preview_item(self, it, caption=None):
        """The preview of one graph from your data (as Workspace draws it), and its data table."""
        import pandas as pd
        self.pimage.hide(); self.pbox.show()
        try:
            if isinstance(it, sp.Board):
                sp.board_figure(it, self.pfig, 1.5, 1.5)
            else:
                sp.preview_figure(it.spec, fig=self.pfig)
            pin = (getattr(it, "spec", None) or {}).get("page_in")
            self.pbox.set_ratio(pin[0] / pin[1] if pin else 1.44)
        except Exception as e:
            self.pfig.clear(); self.pfig.text(0.5, 0.5, f"No preview: {e}", ha="center", va="center", wrap=True)
        self.pcanvas.draw_idle()
        self.pcaption.setObjectName("ok"); self.pcaption.setStyleSheet("")
        self.pcaption.setText(caption or f"✓ Your data: {it.title.strip()[:80]}")
        self._shown = it
        self._hold_result = bool(caption and caption.startswith("✓ Result"))     # a result stays in view until you choose another entry
        try:
            tb = self.ws.table_of(it)
            self.dmodel.set(tb.head(2000) if isinstance(tb, pd.DataFrame) else None)
        except Exception:
            self.dmodel.set(None)
        self.open_ws.setEnabled(True)
        self.steps[4].setChecked(True)
        return it

    def preview_illustration(self, key, what=""):
        """No file of yours yet: an illustration, said plainly to be one."""
        from PySide6.QtGui import QPixmap
        img = self.gallery_image(key)
        self.pbox.hide(); self.pimage.show()
        if img:
            pm = QPixmap(img); self.pimage.setPixmap(pm.scaled(560, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.pimage.setText("No picture for this entry.")
        self.pcaption.setObjectName("illustr")
        self.pcaption.setStyleSheet("color: #0F766E; font-weight: 600;")
        self.pcaption.setText("Illustrative example - not your data. " + (what or "Add files (or tick graphs in Workspace) to see your own data here."))
        self._shown = None
        self.dmodel.set(None)
        self.open_ws.setEnabled(False)
        return img

    def refresh_preview(self):
        """Your data when there is any (the ticked graphs, else the one on show); otherwise the illustration of the chosen entry."""
        its = getattr(self, "_inputs", [])
        if its:
            return self.preview_item(its[0])
        r = self.entry_row
        if r is None:
            return None
        act = r[3] or {}
        if act.get("do") == "figtype" and act.get("type"):
            return self.preview_illustration(f"type_{act['type']}", f"This is how {act['type']} looks. Tick a workbook of yours and press the button to draw it from your data.")
        g = getattr(self, "entry_group", "") or ""
        return self.preview_illustration("analysis_" + re.sub(r"[^a-z0-9]+", "_", g.lower()).strip("_"))

    def open_in_workspace(self):
        it = getattr(self, "_shown", None)
        ws = self.ws
        ws.go(0)
        if it is not None and it in ws.items:
            ws.list.setCurrentRow(ws.items.index(it))
        self.steps[5].setChecked(True)
        return it

    def update_workson(self):
        """Which graphs a Run works on: the ticked ones, else the one on show."""
        try:
            self._workson()
        except RuntimeError:                       # the window is closing
            pass

    def _workson(self):
        ws = self.ws
        try:
            its = ws.tools.pool()
        except Exception:
            its = []
        self._inputs = list(its)
        self.inputs.blockSignals(True)                             # refilling the table is not a choice of yours
        self.inputs.setRowCount(0)
        for it in its[:50]:
            r = self.inputs.rowCount(); self.inputs.insertRow(r)
            tb = ws.table_of(it) if hasattr(ws, "table_of") else None
            cols = [str(c) for c in (list(tb.columns) if tb is not None and hasattr(tb, "columns") else [])]
            nm = Path(str(getattr(it, "path", "") or "")).name or it.title.strip()
            from workspace_shell import short_name
            for c, v, tip in ((0, short_name(nm, 26), str(getattr(it, "path", "") or it.title)), (1, str(getattr(it, "kind", "")), ""),
                              (2, ", ".join(cols[:6]) + (" …" if len(cols) > 6 else ""), ", ".join(cols))):
                x = QTableWidgetItem(v); x.setToolTip(tip or v); self.inputs.setItem(r, c, x)
        self.inputs.blockSignals(False)
        self.inputs.setVisible(bool(its))
        if its:
            self.steps[1].setChecked(True)
        if getattr(self, "entry_row", None) is not None and self.isVisible() and not getattr(self, "_hold_result", False):
            self.refresh_preview()
        if not ws.items:
            self.workson.setText("No data yet: press Add files… (or drop files on the window).")
        elif not its:
            self.workson.setText("Nothing ticked: tick graphs in Workspace, or Add files… here.")
        else:
            names = [i.title.replace("★ Combined: ", "★ ").strip()[:40] for i in its]
            self.workson.setText(f"Works on {len(its)} graph(s): " + "; ".join(names[:4]) + (" …" if len(names) > 4 else ""))

    # ------------------------------------------------------------------ choosing an entry
    def filter(self, q):
        q = q.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            shown = 0
            for j in range(top.childCount()):
                c = top.child(j)
                hide = bool(q) and q not in c.text(0).lower() and q not in top.text(0).lower()
                c.setHidden(hide)
                shown += not hide
            top.setHidden(shown == 0)

    def find_entry(self, name):
        """The tree item whose name starts with `name` (for the assistant and the tests)."""
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).text(0).startswith(name):
                    return top.child(j)
        return None

    def _clear(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        for lay in (self.extra, self.buttons):
            while lay.count():
                w = lay.takeAt(0).widget()
                if w is not None:
                    w.hide()                       # gone at once (deleteLater alone waits for the event loop)
                    w.setParent(None)
                    w.deleteLater()
        self.fields, self.calo_table = {}, None
        self.msg.setText("")
        self.resmodel.set(None)
        self.restable.hide()

    def _button(self, text, fn, accent=False):
        b = QPushButton(text, objectName="primary" if accent else "")
        def run(*_):                                              # the bar at the bottom runs while the entry works
            bw = getattr(self.ws, "busy_while", None)
            if bw is None or getattr(self.ws, "job_thread", None) is not None:
                return fn()
            before = {id(i) for i in self.ws.items}
            self.ws.cancel[0] = False
            self._stop_timer.start()
            self._busy_sync = True
            try:
                with bw(text.rstrip("…")):
                    r = fn()
            finally:
                self._busy_sync = False
            self.update_stop()
            def show_result():                                    # the result: a new graph is previewed, a table is under Results
                try:
                    if getattr(self.ws, "job_thread", None) is not None or getattr(self.ws, "thread", None) is not None:      # a job, then its files read: shown when done
                        QTimer.singleShot(150, show_result); return
                    new = [i for i in self.ws.items if id(i) not in before and getattr(i, "spec", None) is not None]
                    if new:
                        self.preview_item(new[-1], f"✓ Result: {new[-1].title.strip()[:80]} - Open in Workspace to edit and export it.")
                except RuntimeError:
                    pass
            show_result()
            return r
        b.clicked.connect(run)
        self.buttons.addWidget(b)
        return b

    def _form_values(self):
        out = []
        for c in self.formbox.findChildren(QWidget):
            if isinstance(c, QLineEdit) and not isinstance(c.parent(), QComboBox): out.append(c.text())
            elif isinstance(c, QComboBox): out.append(c.currentText())
            elif isinstance(c, QCheckBox): out.append(c.isChecked())
        return out

    def _restore_values(self, vals):
        k = 0
        for c in self.formbox.findChildren(QWidget):
            if isinstance(c, QLineEdit) and not isinstance(c.parent(), QComboBox) or isinstance(c, (QComboBox, QCheckBox)):
                if k >= len(vals): break
                v = vals[k]; k += 1
                try:
                    if isinstance(c, QComboBox): c.setCurrentText(str(v))
                    elif isinstance(c, QCheckBox): c.setChecked(bool(v))
                    else: c.setText(str(v))
                except Exception:
                    pass

    def choose(self, cur, _prev=None):
        r = cur.data(0, Qt.UserRole) if cur is not None else None
        if getattr(self, "entry_row", None) is not None:                  # going back to an entry: your settings are still there
            self.saved_forms[self.entry_row[0]] = self._form_values()
        self._clear()
        self._hold_result = False
        self.entry_row = r
        if not r:
            if cur is not None and cur.childCount():
                self.tree.setCurrentItem(cur.child(0))           # a category opens its first entry
                return
            if cur is not None:
                self.title.setText(cur.text(0).split("  (")[0])
                self.info.setText("Choose an entry of this category.")
            self.entry = None
            return
        self.entry_group = (cur.parent().data(0, Qt.UserRole + 2) if cur.parent() is not None else "") or ""
        for b_ in self.steps[:4]:
            b_.setChecked(True)
        name, what, where, act = r
        self.entry = act
        self.title.setText(name)
        self.info.setText(f"{what}<br><span style='color:#4D5B6B'>Also in the current window: {where}</span>")
        d = act["do"]
        if d == "tool":
            self._tool_form(act["label"])
        elif d == "xrd":
            self._button("Open the XRD Scan Generator" if not act["better"] else "Improve the ticked scan…", lambda: self.ws.tools.xrd_app(act["better"]), True)
        elif d == "library":
            self._button("Open the phase library folder", self.ws.tools.library, True)
        elif d == "zoom":
            zc = QComboBox(); zc.addItems(["On (the app chooses the region)", "Off", "As in Settings"])
            zr = QLineEdit(); zr.setPlaceholderText("or a 2θ range, e.g. 27-37")
            self.form.addRow("Zoomed part", zc); self.form.addRow("Range", zr)
            self._button("Apply to the ticked graphs", lambda: self.ws.tools.zoom_ticked(zc.currentIndex(), zr.text(), self), True)
        elif d == "xrd_auto":
            self._button("Draw the ticked XRD graphs", lambda: self.ws.tools.xrd_auto(self), True)
        elif d == "hs_page":
            self._button("Show the sample pages", lambda: self.ws.tools.hs_page(self), True)
        elif d == "hs_match":
            self._button("Show the table", lambda: self.ws.tools.hs_match(self), True)
        elif d == "tga":
            self._button("Run on the TGA graphs (ticked, or all)", lambda: self.ws.tools.tga_steps(self), True)
        elif d == "calo":
            self._calo_form()
        elif d == "ftir_read":
            self._button("Apply to the ticked FTIR graphs", lambda: self.ws.tools.ftir_read(act["signal"], self), True)
        elif d == "ftir_areas":
            w = QPlainTextEditLite("3700-3000 O-H\n1700-1580 H-O-H\n1550-1350 carbonate\n1200-850 Si-O")
            self.fields["regions"] = w
            self.extra.addWidget(QLabel("Regions, one per line: from-to (cm⁻¹) and a name if you like. Change them to your own.",
                                        objectName="soft", wordWrap=True))
            self.extra.addWidget(w)
            self._button("Measure the band areas", lambda: self.ws.tools.ftir_areas(w.toPlainText(), self), True)
        elif d == "labels_auto":
            for key, lab, dflt in (("n", "Most labels per graph", "8"), ("prom", "Minimum prominence (% of the range)", "5"),
                                   ("digits", "Significant digits", "4")):
                le = QLineEdit(dflt)
                self.fields[key] = le
                self.form.addRow(lab, le)
            self._button("Label the ticked graphs", lambda: self.ws.tools.labels_auto(self.settings(), self), True)
        elif d == "labels_clear":
            self._button("Remove from the ticked graphs", lambda: self.ws.tools.labels_clear(self), True)
        elif d == "psd_style":
            self._button("Draw the ticked PSDs this way", lambda: self.ws.tools.psd_style(act["style"], self), True)
        elif d == "psd_sizes":
            self._button("Make the table", lambda: self.ws.tools.psd_sizes(self), True)
        elif d == "psd_rrsb":
            self._button("Fit the ticked PSDs", lambda: self.ws.tools.psd_rrsb(self), True)
        elif d == "thermo_software":
            cb = QComboBox()
            cb.addItems(SOFTWARE)
            cb.setEditable(True)
            db = QLineEdit()
            db.setPlaceholderText("e.g. CEMDATA18, FToxid, TCOX, phreeqc.dat (optional)")
            self.fields.update(software=cb, database=db)
            self.form.addRow("Program", cb)
            self.form.addRow("Database", db)
            hint = QLabel("", objectName="soft", wordWrap=True)
            cb.currentTextChanged.connect(lambda t: hint.setText(SOFTWARE_NOTES.get(t, "")))
            self.extra.addWidget(hint)
            self._button("Apply to the ticked tables", lambda: self.ws.tools.thermo_software(cb.currentText(), db.text(), None, self), True)
        elif d == "thermo_chart":
            self._button("Draw the ticked tables this way", lambda: self.ws.tools.thermo_chart(act["style"], self), True)
        elif d == "thermo_extract":
            self._button("Make the graph from the ticked tables", lambda: self.ws.tools.thermo_extract(act["what"], self), True)
        elif d == "group":
            self._button("Make the figure from the ticked graphs", lambda: self.ws.tools.group(act["how"], act["kind"], self), True)
        elif d == "figtype":
            self._button(f"Draw the ticked workbook(s) as {act['type']}", lambda: self.ws.tools.figtype_draw(act["type"], self), True)
            self._button("Make a template from a raw file…", lambda: self.ws.tools.figtype_template(act["type"], self))
        self.after_choose()

    def after_choose(self):
        vals = self.saved_forms.get(self.entry_row[0]) if getattr(self, "entry_row", None) else None
        if vals:
            self._restore_values(vals)
        name = self.entry_row[0] if getattr(self, "entry_row", None) else None
        g = getattr(self, "entry_group", None)
        if self.label.startswith("Graph gallery") and name and not any(self.gallery.item(i).data(Qt.UserRole) == name for i in range(self.gallery.count())):
            self.fill_gallery(g)                                    # the gallery of this category
        for i in range(self.gallery.count()):                       # the picture of the chosen entry is shown as chosen
            it = self.gallery.item(i)
            if (it.data(Qt.UserRole) and it.data(Qt.UserRole) == name) or (not it.data(Qt.UserRole) and it.data(Qt.UserRole + 2) == g):
                self.gallery.blockSignals(True); self.gallery.setCurrentItem(it); self.gallery.blockSignals(False)
                break
        self.refresh_preview()

    # ------------------------------------------------------------------ forms
    def _tool_form(self, label):
        import analysis_tools as at
        _g, _f, spec, _d, how = at.TOOLS[label]
        sel = getattr(self.ws, "sel", None)
        for s in spec:
            key, lab, typ, dflt = s[0], s[1], s[2], s[3]
            if typ is at.B:
                w = QCheckBox()
                w.setChecked(bool(dflt))
            elif typ == at.C:
                w = QComboBox()
                w.addItems([str(c) for c in s[4]])
                w.setCurrentText(str(dflt))
            else:
                v = dflt
                if sel and key in ("x_from", "x_to"):
                    v = round(sel[0] if key == "x_from" else sel[1], 6)       # the range selected on the graph
                w = QLineEdit(str(v))
            self.fields[key] = w
            self.form.addRow(lab, w)
        need = {1: "one or more curves", 2: "exactly two curves", "all": "two or more curves"}.get(how, "")
        self.extra.addWidget(QLabel(f"Runs on the graphs ticked in Your graphs, or on the graph on show ({need}). New curves come to Your graphs; "
                                    "tables are shown here and saved as CSV with a provenance file in the results folder, under Analysis.",
                                    objectName="soft", wordWrap=True))
        self._button("Run", lambda: self.ws.tools.run_tool(label, self.settings(), self), True)

    def settings(self):
        out = {}
        for k, w in self.fields.items():
            out[k] = w.isChecked() if isinstance(w, QCheckBox) else w.currentText() if isinstance(w, QComboBox) else w.text().strip()
        return out

    def _calo_form(self):
        t = QTableWidget(0, 5)
        t.setHorizontalHeaderLabels(["Excel file", "Mass (g)", "Label", "Regime", "Alite fraction"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        t.setMinimumHeight(160)
        self.calo_table = t
        for it in self.ws.singles:
            p = str(getattr(it, "path", ""))
            if it.kind == "Calorimetry" and p.lower().endswith((".xlsx", ".xlsm")):
                self.calo_add(p)
        self.extra.addWidget(t)
        for key, lab, dflt in (("excl", "Exclusion window (min), all files", "45"), ("row", "Reaction-start row (empty = detect automatically)", ""),
                               ("bar", "Bar chart: heat at time (h) (empty = end of the shortest run)", "")):
            try:
                import calorimetry as cal
                dflt = str(cal.DEFAULT_EXCLUSION_MIN) if key == "excl" else dflt
            except Exception:
                pass
            w = QLineEdit(dflt)
            self.fields[key] = w
            self.form.addRow(lab, w)
        self._button("Add files…", self.calo_pick)
        self._button("Process", lambda: self.ws.tools.calorimetry(self), True)

    def calo_add(self, path="", mass=""):
        t = self.calo_table
        r = t.rowCount()
        t.insertRow(r)
        for c, v in enumerate((path, str(mass), Path(path).stem if path else "", "", "")):
            t.setItem(r, c, QTableWidgetItem(v))

    def calo_pick(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Calorimetry (TAM) Excel files", "", "Excel workbook (*.xlsx *.xlsm)")
        for p in ps:
            self.calo_add(p)

    def show_table(self, df, text=""):
        self.resmodel.set(df)
        self.restable.setVisible(df is not None)
        if df is not None:
            self.show_preview_tab("Results")
        if text:
            self.msg.setText(text)


# ---------------------------------------------------------------------------------------------- what the entries do
def QPlainTextEditLite(text):
    from PySide6.QtWidgets import QPlainTextEdit
    w = QPlainTextEdit(text)
    w.setFixedHeight(110)
    return w


class Tools:
    def __init__(self, ws):
        self.ws = ws
        self.procs = []

    # ---------------------------------------------------------------- helpers
    def pool(self):
        """The ticked graphs, or the one on show (never a panel figure)."""
        ws = self.ws
        ok = lambda i: i is not None and not isinstance(i, sp.Board)              # single graphs and combined figures, as in the current window
        return [i for i in ws.ticked() if ok(i)] or [i for i in [ws.current()] if ok(i)]

    def curves(self, its):
        """The curves of the graphs, as the current window's Analysis menu reads them (first panel, helpers left out)."""
        import numpy as np
        import analysis_tools as at
        out = []
        for it in its:
            spc = getattr(it, "spec", None) or {}
            pans = spc.get("panels") or []
            if not pans:
                continue
            p0 = pans[0]
            cs = [c for c in p0.get("curves", []) if not str(c.get("label", "")).startswith("_") and len(c.get("x", [])) > 2]
            nm0 = sp.display_names([it])[0] if isinstance(it, sp.Item) else it.title.replace("★ Combined: ", "").strip()[:60]
            for c in cs:
                nm = nm0 if len(cs) == 1 else f"{nm0} {c.get('label', '')}".strip()
                out.append(at.Curve(nm, np.asarray(c["x"], float), np.asarray(c["y"], float), str(spc.get("xname") or "x"),
                                    str(p0.get("yname") or c.get("label", "y"))))
        return out

    def folder(self, sub):
        p = os.path.join(self.ws.run_folder(), sub)
        os.makedirs(p, exist_ok=True)
        return p

    # ---------------------------------------------------------------- the 44 tools
    def run_tool(self, label, settings, page=None, sync=False):
        """Analysis > <tool> on the ticked graphs (or the one on show). Returns (files, tables) when sync, else starts a job."""
        import origin_plot_app as opa
        pool = self.pool()
        curves = self.curves(pool)
        if not curves:
            msg = "Tick the graph(s) to analyse in Your graphs first (or click one to show it)."
            if page:
                page.msg.setText(msg)
            self.ws.set_status(msg)
            return ("error", msg)
        folder = self.folder("Analysis")
        src = {c.name: getattr(it, "path", "") for it in pool for c in self.curves([it])}
        def work(log=None, progress=None):
            return opa.save_analysis(label, curves, settings, folder, src, stop=lambda: self.ws.cancel[0])
        def after(r):
            if r is not None and (r[0] == "stopped" or (self.ws.cancel[0] and r[0] != "error")):     # Stop: nothing comes to Your graphs
                if r[0] != "stopped":
                    for f in r[0]:
                        try: os.remove(f)
                        except OSError: pass
                m = f"{label}: stopped - nothing was added to Your graphs."
                self.ws.log(m); self.ws.set_status(m)
                if page:
                    page.msg.setText(m)
                return
            if r is None or r[0] == "error":
                m = f"{label}: not done: {r[1] if r else 'see Details'}"
                self.ws.log(m)
                self.ws.set_status(m)
                if page:
                    page.msg.setText(m)
                return
            files, tables, notes = r
            self.ws.log(f"Analysis > {label} on {len(curves)} curve(s): {notes[0] if notes else ''}")
            for n_, t_ in tables:
                self.ws.log(f"   {n_}\n" + t_.to_string(index=False, float_format=lambda v: f"{v:.6g}"))
            text = (f"Done on {len(curves)} curve(s)" + (f"; {len(files)} new graph(s) added to Your graphs" if files else "")
                    + (f"; {len(tables)} result table(s)" if tables else "") + f". Files in {folder}")
            if page:
                page.show_table(tables[0][1] if tables else None, text + ("" if len(tables) < 2 else "  (all tables: Workspace > Details)"))
            self.ws.set_status(f"{label}: " + text)
            if files:
                self.ws.load_sync(files) if sync else self.ws.load(files)
        if sync:
            r = work()
            after(r)
            return r
        self.ws.start_job(work, f"Analysis > {label}", after)
        return "started"

    # ---------------------------------------------------------------- XRD
    def xrd_app(self, better=False, template=None):
        """The XRD Scan Generator app, as XRD tools in the current window opens it; the scans you send back come to Your graphs."""
        ws = self.ws
        if template is None:
            template = next((str(getattr(i, "path", "")) for i in self.pool() if str(getattr(i, "path", "")).lower().endswith(".xrdml")), None)
        if better and not template:
            template, _ = QFileDialog.getOpenFileName(ws, "The XRD scan to improve", "", "PANalytical XRD scan (*.xrdml);;All files (*.*)")
            if not template:
                return "no scan"
        app = HERE / "xrd_scan_generator_app.py"
        if not app.is_file():
            ws.set_status("xrd_scan_generator_app.py is missing from the program folder: update the app.")
            return "missing"
        exe = sys.executable
        if os.name == "nt" and Path(exe).name.lower() == "python.exe" and (Path(exe).parent / "pythonw.exe").is_file():
            exe = str(Path(exe).parent / "pythonw.exe")
        fd, rf = tempfile.mkstemp(suffix=".json", prefix="xrdgen_")
        os.close(fd)
        os.remove(rf)
        args = [exe, str(app)] + ([template] if template else []) + ["--return", rf, "--parent", str(os.getpid())] + (["--better"] if better else [])
        try:
            proc = subprocess.Popen(args, cwd=str(HERE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            ws.set_status(f"The XRD Scan Generator could not be started: {e}")
            return "failed"
        self.procs.append(proc)
        ws.log("XRD Scan Generator opened" + (f" with {Path(template).name}" if template else "") + (" (better versions offered)" if better else ""))
        ws.set_status("The XRD Scan Generator is open: tick the scan(s) you like there and press 'Use the ticked scans in Origin Plot Studio'.")
        def poll():
            if proc.poll() is None:
                QTimer.singleShot(500, poll)
                return
            try:
                chosen = [p for p in json.load(open(rf, encoding="utf-8")).get("chosen", []) if os.path.isfile(p)]
            except Exception:
                chosen = []
            if chosen:
                ws.load(chosen)
                ws.set_status(f"{len(chosen)} scan(s) from the XRD Scan Generator added to Your graphs.")
        QTimer.singleShot(800, poll)
        return "opened"

    def library(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        p = sp.store_dir(self.ws.opt)
        os.makedirs(p, exist_ok=True)
        if not os.environ.get("OPS_NO_OPEN"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        self.ws.set_status(f"Phase library folder: {p}. Adding and editing phases: XRD tools > Phase library in the current window.")
        return p

    # ---------------------------------------------------------------- TGA
    def tga_steps(self, page=None):
        import hashlib
        import pandas as pd
        its = [i for i in self.pool() if isinstance(i, sp.Item) and i.kind == "TGA"] or [i for i in self.ws.singles if i.kind == "TGA"]
        if not its:
            m = "No TGA graph: add a TGA file first."
            if page:
                page.msg.setText(m)
            return ("error", m)
        rows, folder = [], self.folder("TGA_steps")
        for it in its:
            r = sp.analyze_tga_steps(it, None, self.ws.opt)
            for iv in r["intervals"]:
                rows.append({"graph": sp.display_names([it])[0], "from (°C)": iv["from"], "to (°C)": iv["to"], "mass loss (%)": iv["mass_loss_pct"]})
            rows.append({"graph": sp.display_names([it])[0], "from (°C)": "total", "to (°C)": "", "mass loss (%)": r["total_mass_loss_pct"]})
            rows.append({"graph": sp.display_names([it])[0], "from (°C)": "residue", "to (°C)": "", "mass loss (%)": r["residual_mass_pct"]})
            try:
                import paper_figures as pf
                pth = str(getattr(it, "path", ""))
                sha = hashlib.sha256(open(pth, "rb").read()).hexdigest() if os.path.isfile(pth) else ""
                pf.write_provenance(os.path.join(folder, re.sub(r'[\\/:*?"<>|]+', "_", it.file + "_TGA_steps")),
                                    {"what": "TGA mass loss in temperature intervals", "inputs": [{"file": os.path.basename(pth), "sha256": sha}],
                                     "temperature_intervals": r["intervals"], "total_mass_loss_pct": r["total_mass_loss_pct"],
                                     "residual_mass_pct": r["residual_mass_pct"], "made_in": "modern window"}, sp.PROVENANCE_VERSION)
            except Exception as e:
                self.ws.log(f"   provenance not written: {e}")
        df = pd.DataFrame(rows)
        f = os.path.join(folder, "TGA_mass_loss_intervals.csv")
        df.to_csv(f, index=False, encoding="utf-8-sig")
        text = f"{len(its)} TGA graph(s). Table saved: {f}"
        self.ws.log("TGA mass loss in temperature intervals\n" + df.to_string(index=False))
        if page:
            page.show_table(df, text)
        self.ws.set_status(text)
        return df

    # ---------------------------------------------------------------- calorimetry
    def calorimetry(self, page, wait=False):
        import calorimetry as cal
        import pandas as pd
        def num(x, what):
            x = str(x or "").strip().replace(",", ".")
            if not x:
                return None
            try:
                return float(x)
            except ValueError:
                raise ValueError(f"{what} must be a number (you typed “{x}”)")
        try:
            ex = num(page.fields["excl"].text(), "The exclusion window")
            rr = num(page.fields["row"].text(), "The reaction-start row")
            bar = num(page.fields["bar"].text(), "The bar-chart time")
            ins, t = [], page.calo_table
            for r in range(t.rowCount()):
                cell = lambda c: (t.item(r, c).text().strip() if t.item(r, c) else "")
                if not cell(0):
                    continue
                m = num(cell(1), "The sample mass")
                if not m or m <= 0:
                    raise ValueError(f"Enter the sample mass in grams (above zero) for {os.path.basename(cell(0))}. Nothing is processed without it.")
                al = num(cell(4), "The alite fraction")
                if al is not None and al > 1:
                    al = al / 100.0
                ins.append({"path": cell(0), "mass_g": m, "exclusion_min": cal.DEFAULT_EXCLUSION_MIN if ex is None else ex,
                            "reaction_row": int(rr) if rr else None, "label": cell(2), "name": cell(2) or None, "regime": cell(3), "alite": al})
        except ValueError as e:
            page.msg.setText(str(e))
            return ("error", str(e))
        if not ins:
            page.msg.setText("Choose at least one Excel file (Add files…).")
            return ("error", "no file")
        if bar:
            ins[0]["bar_at_h"] = bar
        folder = self.folder("Calorimetry")
        def work(log=None, progress=None):
            return cal.run(ins, folder, sp.PROVENANCE_VERSION, log or self.ws.log)
        def after(res):
            if not res:
                page.msg.setText("The calorimetry files were not processed: see Workspace > Details.")
                return
            df = pd.DataFrame([{"sample": s.get("name", ""), "total heat (J/g)": s.get("total_Jg")} for s in res["samples"]])
            page.show_table(df, f"Processed {len(res['samples'])} file(s). Figures and workbook in {folder}"
                            + (("\n" + "\n".join(res["warnings"])) if res.get("warnings") else ""))
            self.ws.set_status(f"Calorimetry processed. Files in {folder}")
        if wait:
            r = work()
            after(r)
            return r
        self.ws.start_job(work, "Calorimetry (TAM III)", after)
        return "started"

    # ---------------------------------------------------------------- gallery graphs
    def figtype_kind(self, tid):
        return next((k for k in sp.KINDS if sp.figtype_id(k) == tid), None)

    def figtype_draw(self, tid, page=None, answers=None):
        """Draw the ticked workbooks (or the one on show, or all) as gallery type tid; ask what the graph needs (t0 row, sample mass)."""
        kind = self.figtype_kind(tid)
        if not kind:
            return ("error", f"unknown gallery graph type {tid}")
        ws = self.ws
        pool = self.pool() or list(ws.singles)
        done, fail = [], []
        for it in pool:
            if not isinstance(it, sp.Item) or not str(getattr(it, "path", "")).lower().endswith((".xlsx", ".xlsm", ".csv")):
                continue
            try:
                it.build(ws.opt, kind)
                (done if it.spec is not None else fail).append(it)
            except Exception as e:
                fail.append(it)
                ws.log(f"   {it.title.strip()}: not drawn as {tid} ({e})")
        if not done:
            m = (f"No ticked workbook could be drawn as {tid}. Add a workbook in that layout, or press 'Make a template from a raw file…'.")
            if page:
                page.msg.setText(m)
            ws.set_status(m)
            return ("error", m)
        for it in done:
            self.ask_needs(it, answers)
        ws.refresh_list()
        row = next((i for i, x in enumerate(ws.items) if x is done[0]), 0)
        ws.list.setCurrentRow(row)
        m = f"{len(done)} graph(s) drawn as {tid}: " + ", ".join(i.title.strip()[:40] for i in done[:4]) + ". See Workspace."
        if page:
            page.msg.setText(m)
        ws.set_status(m)
        return m

    def ask_needs(self, it, answers=None):
        """A gallery graph that waits for an answer (which row is t0, the sample mass): ask it; nothing is assumed."""
        nd = it.det.get("_need") if isinstance(it, sp.Item) else None
        if not nd:
            return
        key, q = nd
        if answers is not None:
            v, ok = answers, True
        elif key == "t0_row":
            v, ok = QInputDialog.getInt(self.ws, "Gallery graph", q + "\n\nRow number of t0 (1 = first data row):", 1, 1)
        else:
            v, ok = QInputDialog.getDouble(self.ws, "Gallery graph", q, 1.0, 0.000001, 1e9, 6)
        if not ok:
            self.ws.log(f"   {it.title.strip()}: no answer given; the graph waits ({q})")
            return
        if key == "calo_mass":
            it.det["calo_mass"] = float(v)
        else:
            it.det["_figtype_book"][1].options[key] = (int(v) - 1) if key == "t0_row" else float(v)
        try:
            it.build(self.ws.opt, it.kind)
            self.ws.log(f"   {it.title.strip()}: {key} = {v} (your answer)")
        except Exception as e:
            self.ws.log(f"   {it.title.strip()}: not drawn after your answer ({e})")

    def figtype_template(self, tid, page=None, raw=None, out=None, mass=None):
        """A template in the layout of gallery type tid, written from your raw file, then loaded."""
        import gallery_graphs as tg
        ws = self.ws
        if raw is None:
            raw, _ = QFileDialog.getOpenFileName(ws, "The raw file", "", "Data files (*.xlsx *.xlsm *.csv *.txt *.xrdml *.xy *.dat *.spa *.ngb-ds3);;All files (*.*)")
            if not raw:
                return "no file"
        if out is None:
            sug = str(Path(raw).with_name(f"{Path(raw).stem}_{tg.TYPES[tid][0]}_template.xlsx"))
            out, _ = QFileDialog.getSaveFileName(ws, "Save the template as", sug, "Excel workbook (*.xlsx)")
            if not out:
                return "no file"
        for _ in range(2):
            try:
                path, notes = tg.make_template(tid, raw, out, mass_g=mass)
                break
            except tg.NeedInput as e:
                mass, ok = QInputDialog.getDouble(ws, "Template", str(e), 1.0, 0.000001, 1e9, 6)
                if not ok:
                    return "cancelled"
            except Exception as e:
                m = f"Template not written: {e}"
                if page:
                    page.msg.setText(m)
                return ("error", m)
        else:
            return "cancelled"
        ws.log(f"Gallery template {tid} written: {path}" + "".join("\n   " + n for n in notes))
        ws.load(([path]))
        m = f"Template {tid} written and added to Your graphs: {path}"
        if page:
            page.msg.setText(m)
        ws.set_status(m)
        return path

    # ---------------------------------------------------------------- FTIR
    def ftir_items(self):
        its = [i for i in self.pool() if isinstance(i, sp.Item) and i.kind == "FTIR"]
        return its or ([i for i in self.ws.singles if i.kind == "FTIR"] if not self.ws.ticked() else [])

    def ftir_read(self, signal, page=None):
        """How the ticked FTIR graphs are read (absorbance: bands at maxima; transmittance: at minima); '' = automatic."""
        its = self.ftir_items()
        if not its:
            m = "No FTIR graph ticked: tick FTIR graphs, or add an FTIR file (Add files…)."
            if page:
                page.msg.setText(m)
            return ("error", m)
        for it in its:
            if signal:
                it.det["_ftir_signal"] = signal
            else:
                it.det.pop("_ftir_signal", None)
            it.build(self.ws.opt, it.kind)
        self.ws.regroup()
        self.ws.refresh_list()
        self.ws.show_item(self.ws.list.currentRow()) if self.ws.list.currentRow() >= 0 else None
        m = f"{len(its)} FTIR graph(s) read as {signal.lower() if signal else 'decided from the file'}; bands labelled again."
        if page:
            page.msg.setText(m)
        self.ws.set_status(m)
        return m

    def ftir_areas(self, regions_text, page=None):
        """Band areas over wavenumber regions (analysis_tools.area_between with the straight-line baseline), absorbance."""
        import numpy as np
        import pandas as pd
        import analysis_tools as at
        regs = []
        for line in str(regions_text).splitlines():
            m = re.match(r"\s*([0-9.]+)\s*[-–to]+\s*([0-9.]+)\s*(.*)$", line)
            if m:
                a, b = float(m.group(1)), float(m.group(2))
                regs.append((min(a, b), max(a, b), m.group(3).strip() or f"{max(a, b):g}-{min(a, b):g}"))
        if not regs:
            m_ = "Type one region per line, e.g. 1200-850 Si-O."
            if page:
                page.msg.setText(m_)
            return ("error", m_)
        its = self.ftir_items()
        if not its:
            m_ = "No FTIR graph ticked: tick FTIR graphs, or add an FTIR file (Add files…)."
            if page:
                page.msg.setText(m_)
            return ("error", m_)
        rows = []
        for it in its:
            for c in self.curves([it]):
                y = np.asarray(c.y, float)
                trans = (it.det.get("_ftir_signal") == "Transmittance") or ("transmit" in c.yname.lower() or "%t" in c.yname.lower())
                cc = c
                if trans:
                    cc = at.Curve(c.name, c.x, at.transmittance_to_absorbance(c, percent=bool(np.nanmax(y) > 1.5)).curves[0][2], c.xname, "Absorbance")
                for lo, hi, nm in regs:
                    try:
                        t = at.area_between(cc, x_from=lo, x_to=hi, subtract_line=True).table.iloc[0]
                        area = float(t["Area"])
                    except Exception:
                        area = float("nan")
                    rows.append({"spectrum": c.name, "region": nm, "from (cm-1)": hi, "to (cm-1)": lo, "area (absorbance·cm-1)": area,
                                 "read as": "transmittance → absorbance" if trans else "absorbance"})
        df = pd.DataFrame(rows)
        folder = self.folder("FTIR")
        f = os.path.join(folder, "FTIR_band_areas.csv")
        df.to_csv(f, index=False, encoding="utf-8-sig")
        with open(os.path.join(folder, "FTIR_band_areas_provenance.json"), "w", encoding="utf-8") as fh:
            json.dump({"what": "FTIR band areas (straight-line baseline between the ends of each region)", "regions": regs,
                       "inputs": [os.path.basename(str(getattr(i, "path", ""))) for i in its], "app_version": sp.VERSION}, fh, indent=1)
        self.ws.log("FTIR band areas\n" + df.to_string(index=False))
        if page:
            page.show_table(df, f"{len(its)} spectrum/spectra, {len(regs)} region(s). Saved: {f}")
        self.ws.set_status(f"FTIR band areas saved: {f}")
        return df

    # ---------------------------------------------------------------- automatic peak labels (positions only)
    def labels_auto(self, st, page=None):
        import analysis_tools as at
        try:
            n = max(1, int(float(st.get("n", 8))))
            prom = float(st.get("prom", 5))
            dig = min(8, max(2, int(float(st.get("digits", 4)))))
        except ValueError:
            m = "The settings must be numbers."
            if page:
                page.msg.setText(m)
            return ("error", m)
        its = [i for i in self.pool() if isinstance(i, sp.Item)]
        if not its:
            m = "Tick the graphs to label (single graphs, not ★ combined ones)."
            if page:
                page.msg.setText(m)
            return ("error", m)
        done, notes = 0, []
        for it in its:
            if it.kind == "FTIR":                         # FTIR labels its bands itself (maxima or minima, as it is read)
                notes.append(f"{it.title.strip()[:30]}: FTIR bands are labelled already (Analysis > FTIR to read as absorbance or transmittance)")
                continue
            cs = self.curves([it])
            if not cs:
                continue
            tab = at.find_peaks_table(cs[0], min_prominence_pct=prom).table
            tab = tab.sort_values("Height", ascending=False).head(n).sort_values("Position") if len(tab) else tab
            if "_given_file" not in it.det:
                it.det["_given_file"] = list(it.given or [])
            new = [(float(p), f"{float(p):.{dig}g}", None) for p in tab["Position"]] if len(tab) else []
            it.given = sorted(list(it.det["_given_file"]) + new, key=lambda t: t[0])
            it.det["_auto_labels"] = [t[1] for t in new]
            try:
                it.build(self.ws.opt, it.kind)
                shown = sum(len(p.get("labels") or []) for p in (it.spec or {}).get("panels", []))
                done += 1
                notes.append(f"{it.title.strip()[:30]}: {len(new)} peak(s) found, {shown} label(s) on the graph")
            except Exception as e:
                notes.append(f"{it.title.strip()[:30]}: not labelled ({e})")
        self.ws.regroup()
        self.ws.refresh_list()
        if self.ws.list.currentRow() >= 0:
            self.ws.show_item(self.ws.list.currentRow())
        m = f"{done} graph(s) labelled with peak positions." + ("\n" + "\n".join(notes) if notes else "")
        if page:
            page.msg.setText(m)
        self.ws.set_status(m.splitlines()[0])
        return m

    def labels_clear(self, page=None):
        its = [i for i in self.pool() if isinstance(i, sp.Item) and "_given_file" in i.det]
        for it in its:
            it.given = list(it.det.pop("_given_file"))
            it.det.pop("_auto_labels", None)
            it.build(self.ws.opt, it.kind)
        self.ws.regroup()
        self.ws.refresh_list()
        m = f"Automatic labels removed from {len(its)} graph(s)."
        if page:
            page.msg.setText(m)
        self.ws.set_status(m)
        return m

    # ---------------------------------------------------------------- figures from the ticked graphs
    def group(self, how, kind="", page=None):
        ws = self.ws
        if kind:
            ok_ = lambda i: i.kind == kind or (kind == "Fit" and i.kind.startswith("Fit"))
            its = [i for i in ws.ticked() if isinstance(i, sp.Item) and ok_(i)] or [i for i in ws.singles if ok_(i)]
            if len(its) >= 2:
                ws._tick_only(its)
        r = ws.group_ticked(how)
        m = {"grouped": "Figure made: it is at the top of Your graphs (◆). See Workspace.", "too few": f"Tick two or more {kind or 'single'} graphs (Add files… to add more).",
             "mixed": "Tick graphs of one kind."}.get(r, r)
        if page:
            page.msg.setText(m)
        return r

    # ---------------------------------------------------------------- XRD: fits and peak lists (HighScore and other Rietveld programs)
    def xrd_auto(self, page=None):
        """Fits: up to ZOOM_PANELS_MAX one panel each (with difference and zoom), more stacked (observed only). Patterns: stacked."""
        ws = self.ws
        tk = [i for i in ws.ticked() if isinstance(i, sp.Item)]
        fits = [i for i in tk if i.kind.startswith("Fit")] or ([] if tk else [i for i in ws.singles if i.kind.startswith("Fit")])
        pats = [i for i in tk if i.kind == "XRD"] or ([] if tk else [i for i in ws.singles if i.kind == "XRD"])
        if len(fits) >= 2:
            how = "panels" if len(fits) <= sp.ZOOM_PANELS_MAX else "stack"
            r = self.group(how, "Fit", page)
            why = (f"{len(fits)} fits: one panel each, with the difference and the zoomed part" if how == "panels"
                   else f"{len(fits)} fits: more than {sp.ZOOM_PANELS_MAX}, so stacked (observed patterns, peaks labelled); tick up to {sp.ZOOM_PANELS_MAX} for panels with the fit")
        elif len(pats) >= 2:
            r = self.group("stack", "XRD", page); why = f"{len(pats)} patterns: stacked"
        elif len(fits) == 1 or len(pats) == 1:
            one = (fits or pats)[0]
            ws.go(0); ws.list.setCurrentRow(ws.items.index(one)) if one in ws.items else None
            r = "single"; why = "one graph: shown on its own (a fit with the difference below and the zoomed part)"
        else:
            r = "none"; why = "No XRD pattern or fit ticked. Add files… (HighScore: the fit as CSV with Iobs / Icalc / Iback, the peak list as CSV or TXT)."
        if page:
            page.msg.setText(why + ("" if r in ("none", "single") else ". See Workspace."))
        ws.log("XRD, decide for me: " + why)
        return r, why

    def zoom_ticked(self, mode, rng_text="", page=None):
        """The zoomed part on (0, the app's region or your range) / off (1) / as in Settings (2), for the ticked graphs or the one on show."""
        import re
        ws = self.ws
        its = [i for i in ws.ticked() if isinstance(i, (sp.Item, sp.Combined))] or ([ws.current()] if isinstance(ws.current(), (sp.Item, sp.Combined)) else [])
        if not its:
            m = "Tick the graphs (or show one) first."
        else:
            nums = re.findall(r"-?\d+(?:[.,]\d+)?", rng_text or "")
            rng = sorted(float(v.replace(",", ".")) for v in nums[:2]) if len(nums) >= 2 and mode == 0 else None
            n_in = 0
            for it in its:
                ws.ribbon.set_fmt(it, zoom_off=True if mode == 1 else None, zoom_on=True if mode == 0 and not rng else None, zoom=rng)
                n_in += any(p.get("inset") for p in (it.spec.get("panels") or []) + [q for c in (it.spec.get("cols") or []) for q in c.get("panels", [])])
            ws.regroup(); ws.refresh_list(); ws.draw()
            m = (f"Zoomed part {'on' if mode == 0 else 'off' if mode == 1 else 'as in Settings'} for {len(its)} graph(s)"
                 + (f"; {n_in} of them now have one" if mode != 1 else "") + ".")
            if mode == 0 and n_in < len(its):
                m += " A graph without one: its data have no clearly crowded region, or the range is outside its x axis."
        if page:
            page.msg.setText(m)
        ws.set_status(m)
        return m

    def hs_page(self, page=None):
        ws = self.ws
        pages = [c for c in ws.combined if getattr(c, "how", "") == "page"]
        if not pages:
            m = ("No sample page yet: it needs a fit (Iobs / Icalc / Iback) and the peak list of the same sample (Assignment, h k l, Height). "
                 "Add both files from HighScore (CSV or TXT); the app puts them together by name or by where the peaks are.")
        else:
            ws.go(0)
            ws.list.setCurrentRow(ws.items.index(pages[0]))
            m = f"{len(pages)} sample page(s) at the top of Your graphs (★ Sample page). The first one is shown in Workspace."
        if page:
            page.msg.setText(m)
        return len(pages)

    def hs_match(self, page=None):
        """Which peak list was put with which pattern or fit, and why."""
        import pandas as pd
        ws = self.ws
        pls = [i for i in ws.singles if i.kind == "XRD peak list"]
        rows = []
        for pl in pls:
            mates = [s for s in ws.singles if s.det.get("_peaklist_from") == pl.title]
            miss = ", ".join(pl.det.get("_missing_phases") or [])
            if not mates:
                rows.append({"Peak list": pl.name, "File": Path(pl.path or pl.file or "").name, "Put with": "(none)", "Why": "no pattern or fit of the same "
                             "sample, and no loaded pattern has its peaks where this list has them", "Phases not drawn": miss})
            for s in mates:
                how = s.det.get("_peaklist_how") or "the same sample name"
                rows.append({"Peak list": pl.name, "File": Path(pl.path or pl.file or "").name, "Put with": f"{s.name} ({s.kind})", "Why": how, "Phases not drawn": miss})
        df = pd.DataFrame(rows) if rows else None
        m = (f"{len(pls)} peak list(s)." if pls else "No peak list loaded. Add the peak list exported from HighScore (CSV or TXT with Assignment, h k l, Height).")
        if any(r["Phases not drawn"] for r in rows):
            m += " A phase 'not drawn' has a calculated height of 0 or less for every reflection in that list: check its scale factor in the refinement."
        if page:
            page.show_table(df, m)
        ws.log("Peak lists and patterns: " + m)
        return df

    # ---------------------------------------------------------------- thermodynamic modelling (GEMS, FactSage, Thermo-Calc, PHREEQC ...)
    def model_items(self):
        its = [i for i in self.pool() if isinstance(i, sp.Item)]
        return its or [i for i in self.ws.singles if i.det.get("thermo") or i.det.get("pore")]

    def thermo_chart(self, style, page=None):
        """Draw the ticked modelling tables in one of the app's thermodynamic charts (the same drawing as the current window)."""
        pore = style == sp.PORE_CHART
        its = [i for i in self.model_items() if (i.det.get("pore") if pore else i.det.get("thermo"))]
        if not its:
            m = ("No pore-solution table ticked." if pore else "No table of phase amounts ticked.") + " Tick one, or Add files… (GEMS, FactSage, Thermo-Calc, PHREEQC .sel ...)."
            if page:
                page.msg.setText(m)
            return ("error", m)
        done = []
        for it in its:
            old = getattr(it, "custom", None)
            it.custom = dict(old or {}, style=style)
            try:
                it.build(self.ws.opt, "XY")
                done.append(it)
            except Exception as e:
                it.custom = old
                self.ws.log(f"   {it.title.strip()}: not drawn as {style} ({e})")
        self.ws.regroup()
        self.ws.refresh_list()
        if done:
            self.ws.list.setCurrentRow(self.ws.items.index(done[0]))
        m = f"{len(done)} table(s) drawn as {style}. Draw in Origin from Workspace." if done else f"Not drawn as {style}: see Details."
        if page:
            page.msg.setText(m)
        self.ws.set_status(m)
        return m

    def thermo_extract(self, what, page=None, sync=False):
        """Saturation indices, solution composition or pH/pe/Eh of a model as a new table (CSV in the results folder) and graph."""
        import numpy as np
        import pandas as pd
        pats = {"si": r"(?i)^(si[_ ]|si\(|saturation)", "solution": r"(?i)^(m_|tot_)|molal|mol/kg|mmol/l|mol/l", "ph": r"(?i)^(ph|pe|eh)(\b|\s|\(|$)"}[what]
        names = {"si": "saturation_indices", "solution": "solution_composition", "ph": "pH_pe_Eh"}[what]
        made, folder = [], self.folder("Modelling")
        for it in self.model_items():
            df = self.ws.table_of(it)
            if df is None:
                continue
            ys = [c for c in df.columns if re.search(pats, str(c).strip())]
            if not ys:
                continue
            th = it.det.get("thermo") or {}
            xc = th.get("x") if th.get("x") in df.columns else next((c for c in df.columns if str(c).lower() in ("time", "step", "t", "t (c)", "t(c)", "temp", "reaction") and
                                                                     pd.to_numeric(df[c], errors="coerce").nunique() > 1), None)
            out = pd.DataFrame({str(xc) if xc is not None else "Row": pd.to_numeric(df[xc], errors="coerce") if xc is not None else np.arange(1, len(df) + 1)})
            for c in ys:
                v = pd.to_numeric(df[c], errors="coerce")
                v = v.where(v > -98.5)                      # PHREEQC writes -99 / -999 where a value does not exist
                nm = re.sub(r"(?i)^(si_|m_|tot_)", "", str(c)).strip()
                out[nm + (" (SI)" if what == "si" else " (mol/kg)" if what == "solution" and str(c).lower().startswith(("m_", "tot_")) else "")] = v
            out = out.dropna(how="all", subset=list(out.columns[1:]))
            f = os.path.join(folder, re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{Path(str(getattr(it, 'path', '') or 'model')).stem}_{names}") + ".csv")
            out.to_csv(f, index=False, encoding="utf-8-sig")
            with open(f[:-4] + "_provenance.json", "w", encoding="utf-8") as fh:
                json.dump({"what": f"{names.replace('_', ' ')} taken from the model table as they are (nothing calculated)", "input": os.path.basename(str(getattr(it, "path", ""))),
                           "columns": [str(c) for c in ys], "x": str(xc), "app_version": sp.VERSION}, fh, indent=1)
            made.append(f)
        if not made:
            m = {"si": "No saturation-index columns (si_..., SI...) in the ticked tables.", "solution": "No solution columns (m_..., tot_..., molal, mmol/l) in the ticked tables.",
                 "ph": "No pH, pe or Eh column in the ticked tables."}[what]
            if page:
                page.msg.setText(m)
            return ("error", m)
        self.ws.load_sync(made) if sync else self.ws.load(made, tick=True)
        m = f"{len(made)} new graph(s) added to Your graphs (tables in {folder})."
        if page:
            page.msg.setText(m)
        self.ws.set_status(m)
        return made

    def thermo_software(self, software, database="", its=None, page=None):
        """The program and database you name for the ticked model tables: on the figure, in the record and the session (nothing else changes)."""
        its = its if its is not None else [i for i in self.model_items() if isinstance(i, sp.Item)]
        if not its:
            m = "Tick the model tables first (or Add files…)."
            if page:
                page.msg.setText(m)
            return ("error", m)
        auto = not software or software.startswith("Automatic")
        sw = "" if auto else software.replace("Other (type its name)", "").strip()
        for it in its:
            if sw:
                it.det["_software"] = sw
                if database.strip():
                    it.det["_database"] = database.strip()
                else:
                    it.det.pop("_database", None)
            else:
                it.det.pop("_software", None)
                it.det.pop("_database", None)
            it.build(self.ws.opt, it.kind)
        self.ws.regroup()
        self.ws.refresh_list()
        if self.ws.list.currentRow() >= 0:
            self.ws.show_item(self.ws.list.currentRow())
        m = (f"{len(its)} table(s): calculated with {sw}" + (f", {database.strip()}" if database.strip() else "") + " - written under the figure."
             if sw else f"{len(its)} table(s): no program named.")
        if page:
            page.msg.setText(m)
        self.ws.set_status(m)
        return m

    # ---------------------------------------------------------------- particle size (PSD)
    def psd_items(self):
        its = [i for i in self.pool() if isinstance(i, sp.Item) and i.kind == "Particle size"]
        return its or ([i for i in self.ws.singles if i.kind == "Particle size"] if not self.ws.ticked() else [])

    def _no_psd(self, page):
        m = "No particle size graph ticked: tick PSDs, or Add files… (laser diffraction exports, sieve tables ...)."
        if page:
            page.msg.setText(m)
        return ("error", m)

    def psd_style(self, style, page=None):
        its = self.psd_items()
        if not its:
            return self._no_psd(page)
        for it in its:
            it.det["_psd_style"] = style
            it.build(self.ws.opt, it.kind)
        self.ws.regroup()
        self.ws.refresh_list()
        self.ws.list.setCurrentRow(self.ws.items.index(its[0]))
        m = f"{len(its)} PSD(s) drawn as: {style.lower()}. In Origin and the publication files the same."
        if page:
            page.msg.setText(m)
        self.ws.set_status(m)
        return m

    def psd_sizes(self, page=None):
        import pandas as pd
        its = self.psd_items()
        if not its:
            return self._no_psd(page)
        rows = []
        for it in its:
            r = it.results
            if r is None or "Quantity" not in r:
                continue
            row = {"sample": sp.display_names([it])[0]}
            for _, q in r.iterrows():
                row[str(q["Quantity"]) + (f" ({q['Unit']})" if q.get("Unit") else "")] = q["Value"]
            rows.append(row)
        df = pd.DataFrame(rows)
        f = os.path.join(self.folder("PSD"), "PSD_characteristic_sizes.csv")
        df.to_csv(f, index=False, encoding="utf-8-sig")
        self.ws.log("Particle size: characteristic sizes\n" + df.to_string(index=False))
        if page:
            page.show_table(df, f"{len(rows)} PSD(s). Saved: {f}")
        self.ws.set_status(f"PSD sizes saved: {f}")
        return df

    def psd_rrsb(self, page=None):
        """RRSB: Q(x) = 100 (1 - exp(-(x/x')^n)); ln(-ln(1 - Q/100)) = n ln x - n ln x'; fitted between 5 and 95 % passing."""
        import numpy as np
        import pandas as pd
        its = self.psd_items()
        if not its:
            return self._no_psd(page)
        rows = []
        for it in its:
            two = (it.spec or {}).get("split") or (it.spec or {}).get("panels") or []
            cum = next((c for p in two for c in p.get("curves", []) if c.get("label") == "Cumulative"), None)
            if cum is None:
                continue
            x, q = np.asarray(cum["x"], float), np.asarray(cum["y"], float)
            k = np.isfinite(x) & np.isfinite(q) & (x > 0) & (q > 5) & (q < 95)
            if k.sum() < 3:
                rows.append({"sample": sp.display_names([it])[0], "note": "fewer than 3 points between 5 and 95 % passing"})
                continue
            X, Y = np.log(x[k]), np.log(-np.log(1 - q[k] / 100.0))
            n, b = np.polyfit(X, Y, 1)
            yhat = n * X + b
            r2 = 1 - np.sum((Y - yhat) ** 2) / np.sum((Y - Y.mean()) ** 2)
            u = (it.spec.get("xname") or "").split("(")[-1].rstrip(")") or "µm"
            rows.append({"sample": sp.display_names([it])[0], f"x' ({u})": round(float(np.exp(-b / n)), 4), "n": round(float(n), 4), "R²": round(float(r2), 5),
                         "points used": int(k.sum()), "range": "5-95 % passing"})
        df = pd.DataFrame(rows)
        folder = self.folder("PSD")
        f = os.path.join(folder, "PSD_RRSB_fit.csv")
        df.to_csv(f, index=False, encoding="utf-8-sig")
        with open(os.path.join(folder, "PSD_RRSB_fit_provenance.json"), "w", encoding="utf-8") as fh:
            json.dump({"what": "RRSB (Rosin-Rammler-Sperling-Bennett) fit of the cumulative curve", "model": "Q = 100 (1 - exp(-(x/x')^n))",
                       "linearised": "ln(-ln(1 - Q/100)) = n ln x - n ln x'", "points": "5 % < Q < 95 %",
                       "inputs": [os.path.basename(str(getattr(i, "path", ""))) for i in its], "app_version": sp.VERSION}, fh, indent=1)
        self.ws.log("RRSB fit\n" + df.to_string(index=False))
        if page:
            page.show_table(df, f"RRSB fit of {len(rows)} PSD(s). Saved: {f}")
        self.ws.set_status(f"RRSB fit saved: {f}")
        return df


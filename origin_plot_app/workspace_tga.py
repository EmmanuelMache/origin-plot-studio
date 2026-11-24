"""TGA / DTG analysis: DTG, peaks, onset / endset, transition zones (drag their edges on the graph), mass loss per zone by
the stepwise and the tangent method side by side, Ca(OH)2 / CaCO3 / Mg(OH)2 from zones you assigned, bound water, basis,
and one-click export to Excel (Data, Peaks, Zones, Summary, Chart).

Zone names are never assigned by the app: every zone starts as a suggestion with a '?', listed in the Confirm labels
table (suggested name, other candidates, confidence, source). Only names you confirmed are written on exported graphs
and into the Excel file. Confirmed names are remembered per material and offered first next time.
The file is only read. The calculations are those of opstudio.tga_core (known-answer tests: tests/test_tga_core.py)."""
import json, os, re
import numpy as np

from opstudio import tga_core as tc

SPECIES = [("", "—"), ("CH", "Ca(OH)₂"), ("CaCO3", "CaCO₃"), ("MgOH2", "Mg(OH)₂")]
ZONE_COLOURS = ["#DCE9F8", "#FBE5D6", "#E2F0D9", "#EADCF4", "#FFF2CC", "#D9EAD3", "#F4CCCC"]


def guess_species(name):
    """A species only follows from a name the user confirmed (or typed)."""
    n = name.lower()
    if "portlandite" in n or "ca(oh)" in n: return "CH"
    if "calcite" in n or "caco3" in n or "decarbonation" in n and "dolomite" not in n: return "CaCO3"
    if "brucite" in n or "mg(oh)" in n: return "MgOH2"
    return ""


class TgaAnalysis:
    """The numbers of one TGA run. No window needed (used by the dialog and by the tests)."""

    def __init__(self, T, mass, name="sample", settings=None):
        T = np.asarray(T, dtype=float); mass = np.asarray(mass, dtype=float); ok = np.isfinite(T) & np.isfinite(mass)
        self.T_raw, self.mass_raw, self.name = T[ok], mass[ok], str(name)
        self.settings = {"temperature_unit": "°C", "normalise": "initial", "T_ref": 105.0, "window_C": 15.0, "poly": 2, "heating_rate": None, "dtg_unit": "% °C⁻¹",
                         "method": "tangent", "ignited_T": None, "bw_low": 50.0, "bw_high": 550.0, "subtract_ch_water": False, "binder_factor": None, "prominence": 0.03, "min_sep_C": 25.0}
        self.settings.update(settings or {}); self.zones = []; self.compute(new_zones=True)

    # ---- the curves
    def compute(self, new_zones=False):
        s = self.settings; T = self.T_raw - (273.15 if s["temperature_unit"] == "K" else 0.0)
        o = np.argsort(T); T = T[o]; m = self.mass_raw[o]; keep = np.concatenate([[True], np.diff(T) > 0]); T, m = T[keep], m[keep]
        if s["normalise"] == "initial": self.mass, self.norm = tc.normalise(T, m, "initial")
        else: self.mass, self.norm = tc.normalise(T, m, "dry" if s["normalise"] == "dry" else "ignited", float(s["T_ref"]))
        self.T = T; d = tc.dtg(T, self.mass, float(s["window_C"]), int(s["poly"]), s["heating_rate"]); self.dtg_info = d
        self.dtg = d["dtg_per_C"]; self.peaks = tc.find_dtg_peaks(T, self.dtg, float(s["prominence"]), float(s["min_sep_C"]))
        for p in self.peaks:
            oe = tc.onset_endset(T, self.mass, self.dtg, p["T_peak"]); p["onset"], p["endset"] = oe.get("onset"), oe.get("endset")
        if new_zones:
            self.zones = [{"T": list(z["T"]), "T_peak": z["T_peak"], "suggested": z["suggested"], "candidates": list(z["candidates"]), "confidence": z["confidence"], "source": z["source"],
                           "name": "", "confirmed": False, "species": ""} for z in tc.suggest_zones(T, self.dtg, self.peaks)]
        return self

    def dtg_shown(self):
        s = self.settings
        if s["dtg_unit"] == "% min⁻¹" and s["heating_rate"]: return self.dtg * float(s["heating_rate"]), "DTG (% min$^{-1}$)"
        return self.dtg, "DTG (% °C$^{-1}$)"

    # ---- zones
    def label_of(self, z, final=False):
        """What is written for a zone: its confirmed name; in a preview an unconfirmed suggestion with '?'; in an export nothing."""
        if z["confirmed"]: return z["name"]
        return "" if final else ((z["suggested"] + " ?") if z["suggested"] and z["suggested"] != "Unassigned" else "?")

    def confirm(self, i, name=None, species=None):
        z = self.zones[i]; z["name"] = (name if name is not None else (z["name"] or z["suggested"])).strip(); z["confirmed"] = bool(z["name"])
        z["species"] = species if species is not None else (z["species"] or guess_species(z["name"])); return z

    def unconfirm(self, i): self.zones[i].update(confirmed=False, name="", species="")

    def set_edge(self, i, which, T):
        z = self.zones[i]; lo, hi = float(self.T[0]), float(self.T[-1]); T = float(min(max(T, lo), hi))
        if which == 0: z["T"][0] = min(T, z["T"][1] - 2.0)
        else: z["T"][1] = max(T, z["T"][0] + 2.0)
        w = (self.T >= z["T"][0]) & (self.T <= z["T"][1])
        if w.sum() > 2: z["T_peak"] = float(self.T[w][np.argmin(self.dtg[w])])
        return z

    def add_zone(self, T1, T2):
        T1, T2 = sorted((float(T1), float(T2))); w = (self.T >= T1) & (self.T <= T2)
        Tp = float(self.T[w][np.argmin(self.dtg[w])]) if w.sum() > 2 else (T1 + T2) / 2
        cands = [e["name"] for e in tc.REFERENCE_EVENTS if e["gas"] and e["T"][0] <= Tp <= e["T"][1]]
        self.zones.append({"T": [T1, T2], "T_peak": Tp, "suggested": cands[0] if cands else "Unassigned", "candidates": cands, "confidence": "low" if cands else "none", "source": tc.SOURCE_NOTE,
                           "name": "", "confirmed": False, "species": ""}); self.zones.sort(key=lambda z: z["T"][0]); return self.zones

    def delete_zone(self, i): return self.zones.pop(i)

    def merge(self, i):
        """Zone i and the next one become one zone (its name must be confirmed again)."""
        if i + 1 >= len(self.zones): return None
        a, b = self.zones[i], self.zones.pop(i + 1); a["T"] = [min(a["T"][0], b["T"][0]), max(a["T"][1], b["T"][1])]; a.update(confirmed=False, name="", species="")
        self.set_edge(i, 0, a["T"][0]); return a

    def split(self, i, T):
        z = self.zones[i]
        if not (z["T"][0] + 2 < T < z["T"][1] - 2): return None
        hi = z["T"][1]; z["T"][1] = float(T); z.update(confirmed=False, name="", species=""); self.set_edge(i, 1, T); self.add_zone(T, hi); return self.zones

    # ---- results
    def rows(self, final=False):
        """One row per zone, both methods side by side. final=True: only confirmed names are written (exports)."""
        s = self.settings; out = []; ign = float(np.interp(s["ignited_T"], self.T, self.mass)) if s["ignited_T"] else None; f = s["binder_factor"]
        for z in self.zones:
            T1, T2 = z["T"]; sw = tc.stepwise_loss(self.T, self.mass, T1, T2)
            try: tg = tc.tangent_step(self.T, self.mass, T1, T2)["dm"]
            except Exception: tg = None                     # too close to the ends of the run for the two straight lines
            used = tg if (s["method"] == "tangent" and tg is not None) else sw
            pk = min(self.peaks, key=lambda p: abs(p["T_peak"] - z["T_peak"])) if self.peaks else {}
            row = {"zone": self.label_of(z, final), "confirmed": z["confirmed"], "T1": T1, "T2": T2, "T_peak": z["T_peak"], "onset": pk.get("onset") if pk and abs(pk["T_peak"] - z["T_peak"]) < 15 else None,
                   "endset": pk.get("endset") if pk and abs(pk["T_peak"] - z["T_peak"]) < 15 else None, "dm_stepwise": sw, "dm_tangent": tg, "dm_used": used,
                   "method": s["method"] if (s["method"] == "stepwise" or tg is not None) else "stepwise (tangent not possible here)"}
            sp = z["species"] if z["confirmed"] else ""
            if sp:
                nm, fac = {"CH": ("Ca(OH)2", tc.M["CaOH2"] / tc.M["H2O"]), "CaCO3": ("CaCO3", tc.M["CaCO3"] / tc.M["CO2"]), "MgOH2": ("Mg(OH)2", tc.M["MgOH2"] / tc.M["H2O"])}[sp]
                row["content_name"], row["content"] = nm, used * fac
                if ign: row["content_ignited_basis"] = row["content"] / ign * 100
                if f: row["content_per_binder"] = row["content"] / float(f)
            if ign: row["dm_ignited_basis"] = used / ign * 100
            out.append(row)
        return out

    def summary(self):
        s = self.settings; rows = self.rows(); ch_w = sum(r["dm_used"] for r in rows if r.get("content_name") == "Ca(OH)2") if s["subtract_ch_water"] else 0.0
        bw = tc.bound_water(self.T, self.mass, float(s["bw_low"]), float(s["bw_high"]), s["ignited_T"], ch_w)
        out = {"sample": self.name, "total_loss (%)": float(self.mass[0] - self.mass[-1]), "residual mass (%)": float(self.mass[-1]), "T range (°C)": f"{self.T[0]:.0f} - {self.T[-1]:.0f}",
               "bound water (%)": bw["bound_water"], "bound water limits (°C)": f"{bw['T_low']:g} - {bw['T_high']:g}", "CH water subtracted from bound water": bool(s["subtract_ch_water"])}
        if "bound_water_ignited_basis" in bw: out["bound water, ignited basis (%)"] = bw["bound_water_ignited_basis"]
        for r in rows:
            if r.get("content_name"): out[f"{r['content_name']} (wt.%)"] = r["content"]
        return out

    def settings_text(self):
        s = self.settings
        return {"mass reference": {"initial": "initial mass (first point)", "dry": f"mass at {s['T_ref']:g} °C (dry)", "ignited": f"mass at {s['T_ref']:g} °C (ignited)"}[s["normalise"]],
                "DTG": f"Savitzky-Golay derivative, window {s['window_C']:g} °C ({self.dtg_info['window_points']} points), order {s['poly']}; natural sign (mass loss is negative)",
                "DTG unit": s["dtg_unit"] + (f" (heating rate {s['heating_rate']:g} °C/min)" if s["heating_rate"] else ""), "mass loss used": s["method"],
                "tangent method": "straight lines fitted 25 °C before T1 and after T2; the loss is read at the DTG peak of the zone",
                "ignited basis": f"mass at {s['ignited_T']:g} °C" if s["ignited_T"] else "not used", "binder factor": s["binder_factor"] or "not used",
                "peak detection": f"prominence {s['prominence']:g} of the highest peak, at least {s['min_sep_C']:g} °C apart"}

    def export_excel(self, path):
        """Data, Peaks, Zones, Summary (settings and formulas written out), Chart (TG + DTG on a second axis, DTG not reversed)."""
        rows = self.rows(final=True)
        for r in rows:
            if not r["confirmed"]: r["zone"] = ""           # an unconfirmed suggestion is never exported as a name
        peaks = [dict(p, label="") for p in self.peaks]
        for p in peaks:
            z = next((z for z in self.zones if z["confirmed"] and z["T"][0] <= p["T_peak"] <= z["T"][1]), None)
            if z: p["label"] = z["name"]
        summ = dict(self.summary()); summ["zones without a confirmed name"] = sum(1 for z in self.zones if not z["confirmed"])
        return tc.export_excel(path, self.name, self.T, self.mass, self.dtg, peaks, rows, summ, self.settings_text())

    def table_text(self):
        """The results table as tab-separated text (for pasting)."""
        head = ["Zone", "T1 (°C)", "T2 (°C)", "T peak (°C)", "Onset (°C)", "Endset (°C)", "Δm stepwise (%)", "Δm tangent (%)", "Δm used (%)", "Phase", "Content (wt.%)", "Content, ignited basis (wt.%)"]
        f = lambda v, n=2: "" if v is None or (isinstance(v, float) and not np.isfinite(v)) else (f"{v:.{n}f}" if isinstance(v, (int, float)) else str(v))
        lines = ["\t".join(head)]
        for r in self.rows(final=True):
            lines.append("\t".join([r["zone"], f(r["T1"], 0), f(r["T2"], 0), f(r["T_peak"], 0), f(r["onset"], 0), f(r["endset"], 0), f(r["dm_stepwise"]), f(r["dm_tangent"]), f(r["dm_used"]),
                                    r.get("content_name", ""), f(r.get("content")), f(r.get("content_ignited_basis"))]))
        return "\n".join(lines)

    # ---- the graph: TG and DTG in one graph, DTG at its natural sign
    def figure(self, style=None, final=False, fig=None):
        import matplotlib
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from opstudio import core, api
        st = core.load_style(style or api.DEFAULT_STYLE)
        with matplotlib.rc_context():
            core.apply_style(st)
            if fig is None: fig = Figure(figsize=core.fig_size(st, "double")); FigureCanvasAgg(fig)
            fig.clear(); ax = fig.add_subplot(111); ax2 = ax.twinx(); d, dl = self.dtg_shown(); c1, c2 = "#000000", st["palette"]["series"][2]
            for i, z in enumerate(self.zones):
                ax.axvspan(z["T"][0], z["T"][1], color=ZONE_COLOURS[i % len(ZONE_COLOURS)], alpha=0.75, lw=0, zorder=0)
                lab = self.label_of(z, final)
                if lab: ax.text((z["T"][0] + z["T"][1]) / 2, 0.985, lab, transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=st["font"]["size_pt"]["annotation"], rotation=90 if len(lab) > 14 else 0,
                                color="#172B4D" if z["confirmed"] else "#A16207")
            ax.plot(self.T, self.mass, color=c1, label="TG"); ax2.plot(self.T, d, color=c2, lw=st["lines"]["width_pt"] * 0.9, label="DTG")
            ax.set_xlabel("Temperature (°C)"); ax.set_ylabel("Mass (%)"); ax2.set_ylabel(dl, color=c2); ax2.tick_params(axis="y", colors=c2); ax.set_xlim(self.T[0], self.T[-1])
            core.finish(ax, st); ax.tick_params(right=False); ax2.tick_params(direction=st["axes"]["tick_direction"])
            h = ax.get_lines()[:1] + ax2.get_lines()[:1]; ax.legend(h, ["TG", "DTG"], loc="lower left")
            fig.canvas.draw() if fig.canvas is not None else None
        fig._ops_style = st; self.ax = ax
        return fig


def replicate_stats(analyses):
    """Mean, SD and CoV of the summary values of several runs of the same sample."""
    keys = [k for k, v in analyses[0].summary().items() if isinstance(v, float)]; out = []
    for k in keys:
        v = np.array([a.summary().get(k, np.nan) for a in analyses], dtype=float); v = v[np.isfinite(v)]
        if len(v): m = float(v.mean()); sd = float(v.std(ddof=1)) if len(v) > 1 else 0.0; out.append({"quantity": k, "n": int(len(v)), "mean": m, "SD": sd, "CoV (%)": (sd / m * 100) if m else float("nan")})
    return out


# ---------------------------------------------------------------------------------------------------- label memory
def _memory():
    import workspace_qt as WQ
    return dict(WQ.load_cfg().get("label_memory") or {})


def remember_labels(material, analysis):
    """Confirmed zone names of this material, offered first next time (never applied without confirmation)."""
    import workspace_qt as WQ
    if not material.strip(): return
    m = _memory(); m[f"TGA|{material.strip().lower()}"] = [{"T": z["T"], "T_peak": z["T_peak"], "name": z["name"], "species": z["species"]} for z in analysis.zones if z["confirmed"]]
    WQ.save_cfg({"label_memory": m})


def offer_remembered(material, analysis):
    """Names confirmed earlier for this material become the first suggestion of the zones at the same peak (still with '?')."""
    mem = _memory().get(f"TGA|{material.strip().lower()}") or []; n = 0
    for z in analysis.zones:
        hit = next((q for q in mem if abs(q["T_peak"] - z["T_peak"]) <= 25), None)
        if hit and not z["confirmed"]:
            z["suggested"] = hit["name"]; z["candidates"] = [hit["name"]] + [c for c in z["candidates"] if c != hit["name"]]; z["confidence"] = "confirmed by you before for this material"; z["_species"] = hit.get("species", ""); n += 1
    return n


def read_tga_file(path, t_col=None, m_col=None):
    """(T, mass, name, columns, used) from a table file: temperature and mass columns found by their headers, else the first two numeric ones."""
    from opstudio import data as D
    t = D.read_tables(path)[0]; num = t.numeric
    if len(num) < 2: raise ValueError("this file needs a temperature column and a mass column")
    tc_ = t_col or next((c for c in num if re.search(r"temp|°c|\bt\b|\(k\)", c.lower())), num[0])
    mc = m_col or next((c for c in num if c != tc_ and re.search(r"mass|weight|\btg\b|%", c.lower()) and not re.search(r"dtg|deriv", c.lower())), next(c for c in num if c != tc_))
    unit = "K" if re.search(r"\(k\)|kelvin", tc_.lower()) else "°C"
    return t.arr(tc_), t.arr(mc), t.name, num, (tc_, mc, unit)


# ---------------------------------------------------------------------------------------------------- the window
def open_dialog(ws, path=None):
    from PySide6.QtWidgets import QFileDialog
    if path is None:
        it = ws.current() if hasattr(ws, "current") else None; path = getattr(it, "path", None)
        if not path or not os.path.isfile(path) or "tg" not in (getattr(it, "kind", "") or "").lower():
            path, _ = QFileDialog.getOpenFileName(ws, "A TGA file (temperature and mass)", "", "Data files (*.xlsx *.xls *.csv *.txt *.dat);;All files (*.*)")
            if not path: return None
    try: d = dialog_class()(ws, path)
    except Exception as e:
        ws.set_status(f"This file could not be read as a TGA run: {e}"); return None
    d.show(); ws._tga_dialog = d; return d


def _dialog_class():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, QComboBox, QDoubleSpinBox, QCheckBox, QLineEdit, QTableWidget, QTableWidgetItem,
                                   QHeaderView, QFileDialog, QMessageBox, QApplication, QSplitter, QWidget, QInputDialog, QAbstractItemView)
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure

    class TgaDialog(QDialog):
        COLS = ["Confirm", "Zone name (suggestion until you confirm)", "Phase", "T1", "T2", "T peak", "Onset", "Endset", "Δm step", "Δm tangent", "Content", "Ignited basis", "Confidence / source"]

        def __init__(self, ws, path):
            super().__init__(ws); self.ws, self.path = ws, path; self.setWindowTitle("TGA / DTG analysis"); self.resize(1400, 860); self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
            T, m, name, cols, used = read_tga_file(path); self.a = TgaAnalysis(T, m, name, {"temperature_unit": used[2]}); self.cols, self.used = cols, used; self._drag = None; self._busy = False
            root = QVBoxLayout(self); sp = QSplitter(Qt.Horizontal); root.addWidget(sp, 1)
            left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
            self.fig = Figure(); self.canvas = FigureCanvasQTAgg(self.fig); lv.addWidget(self.canvas, 1)
            hint = QLabel("Drag the edge of a shaded zone to move it. Alt + drag on the graph adds a zone. Names with '?' are suggestions: confirm them in the table.", objectName="soft"); hint.setWordWrap(True); lv.addWidget(hint)
            sp.addWidget(left)
            right = QWidget(); rv = QVBoxLayout(right); f = QFormLayout()
            self.tcol = QComboBox(); self.mcol = QComboBox(); [c.addItems(cols) for c in (self.tcol, self.mcol)]; self.tcol.setCurrentText(used[0]); self.mcol.setCurrentText(used[1])
            self.tcol.setToolTip("The temperature column of your file"); self.mcol.setToolTip("The mass column of your file (mg or %)")
            hh = QHBoxLayout(); hh.addWidget(self.tcol); hh.addWidget(self.mcol); f.addRow("Temperature / mass column:", hh)
            self.unit = QComboBox(); self.unit.addItems(["°C", "K"]); self.unit.setCurrentText(used[2]); self.unit.setToolTip("Unit of the temperature column (K is converted to °C)")
            self.norm = QComboBox(); self.norm.addItems(["initial mass", "dry mass at T", "ignited mass at T"]); self.norm.setToolTip("What 100 % is: the first point, the mass at a drying temperature, or the mass at an ignition temperature")
            self.tref = QDoubleSpinBox(); self.tref.setRange(20, 1500); self.tref.setValue(105); self.tref.setSuffix(" °C"); self.tref.setToolTip("The temperature of the dry or ignited reference mass")
            h2 = QHBoxLayout(); h2.addWidget(self.unit); h2.addWidget(self.norm); h2.addWidget(self.tref); f.addRow("Unit / mass reference:", h2)
            self.win = QDoubleSpinBox(); self.win.setRange(1, 100); self.win.setValue(15); self.win.setSuffix(" °C"); self.win.setToolTip("Savitzky-Golay window of the DTG, in °C")
            self.rate = QDoubleSpinBox(); self.rate.setRange(0, 200); self.rate.setValue(0); self.rate.setSuffix(" °C/min"); self.rate.setSpecialValueText("heating rate not given"); self.rate.setToolTip("Needed only for DTG in % per minute")
            self.dunit = QComboBox(); self.dunit.addItems(["% °C⁻¹", "% min⁻¹"]); self.dunit.setToolTip("Unit of the DTG axis (% per minute needs the heating rate)")
            h3 = QHBoxLayout(); h3.addWidget(self.win); h3.addWidget(self.rate); h3.addWidget(self.dunit); f.addRow("DTG smoothing / rate / unit:", h3)
            self.method = QComboBox(); self.method.addItems(["tangent", "stepwise"]); self.method.setToolTip("Which mass loss is used for the contents. Both are always shown side by side")
            self.ign = QDoubleSpinBox(); self.ign.setRange(0, 1500); self.ign.setValue(0); self.ign.setSuffix(" °C"); self.ign.setSpecialValueText("no ignited basis"); self.ign.setToolTip("Contents per ignited mass: the temperature of the ignited mass (e.g. 550 or 1000 °C)")
            self.binder = QDoubleSpinBox(); self.binder.setRange(0, 1); self.binder.setDecimals(3); self.binder.setSingleStep(0.05); self.binder.setSpecialValueText("no binder factor"); self.binder.setToolTip("Mass fraction of binder (or clinker) in the sample: contents are also given per binder mass")
            h4 = QHBoxLayout(); h4.addWidget(self.method); h4.addWidget(self.ign); h4.addWidget(self.binder); f.addRow("Method / ignited basis / binder:", h4)
            self.bwl = QDoubleSpinBox(); self.bwh = QDoubleSpinBox()
            for b, v in ((self.bwl, 50), (self.bwh, 550)): b.setRange(20, 1500); b.setValue(v); b.setSuffix(" °C")
            self.subch = QCheckBox("minus CH water"); self.subch.setToolTip("Bound water without the water of the confirmed Ca(OH)₂ zone")
            h5 = QHBoxLayout(); h5.addWidget(self.bwl); h5.addWidget(self.bwh); h5.addWidget(self.subch); f.addRow("Bound water from / to:", h5)
            self.material = QLineEdit(placeholderText="e.g. hydrated paste, raw meal"); self.material.setToolTip("Your confirmed zone names are remembered for this material and offered first next time"); self.material.editingFinished.connect(self._material)
            f.addRow("Material (for remembered names):", self.material); rv.addLayout(f)
            cl = QLabel("<b>Confirm labels</b> – the app never names a zone by itself. Tick Confirm (or type your own name, or leave it unlabelled).", objectName="soft"); cl.setWordWrap(True); rv.addWidget(cl)
            self.table = QTableWidget(0, len(self.COLS)); self.table.setHorizontalHeaderLabels(self.COLS); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setSelectionMode(QAbstractItemView.ExtendedSelection); self.table.itemChanged.connect(self._item_changed); rv.addWidget(self.table, 1)
            self.table.setContextMenuPolicy(Qt.CustomContextMenu); self.table.customContextMenuRequested.connect(self._zone_menu)
            zb = QHBoxLayout()
            for text, tip, fn in (("Confirm all shown names", "Confirm every suggested name as it is shown (you take the responsibility for the names)", self.confirm_all), ("Add zone…", "Add a zone between two temperatures (or Alt + drag on the graph)", self.add_zone),
                                  ("Merge with next", "The selected zone and the next one become one zone", self.merge), ("Split…", "Split the selected zone at a temperature", self.split), ("Delete", "Delete the selected zones", self.delete)):
                b = QPushButton(text); b.setToolTip(tip); b.clicked.connect(fn); zb.addWidget(b)
            rv.addLayout(zb)
            self.sumlab = QLabel("", objectName="soft"); self.sumlab.setWordWrap(True); self.sumlab.setTextInteractionFlags(Qt.TextSelectableByMouse); rv.addWidget(self.sumlab)
            eb = QHBoxLayout()
            for text, tip, fn, name in (("Export results → Excel", "One workbook: Data, Peaks, Zones, Summary (settings and formulas), Chart (TG + DTG, DTG not reversed). Only confirmed names are written", self.export, "primary"),
                                        ("Copy table", "The results table as text for pasting into Excel or Word", self.copy, None), ("Draw in Origin like this", "The same TG + DTG graph in Origin, saved as {sample}_tga_dtg.opju", self.origin, "origin"),
                                        ("Save graph…", "Save the graph (PNG / TIFF / PDF / SVG); unconfirmed names are left out", self.save_graph, None)):
                b = QPushButton(text); b.setToolTip(tip); b.clicked.connect(fn); b.setObjectName(name) if name else None; eb.addWidget(b)
            rv.addLayout(eb); sp.addWidget(right); sp.setSizes([760, 640])
            for w_ in (self.tcol, self.mcol): w_.currentTextChanged.connect(lambda _t: self.reload())
            for w_ in (self.unit, self.norm, self.dunit, self.method): w_.currentIndexChanged.connect(lambda _i: self.settings_changed())
            for w_ in (self.tref, self.win, self.rate, self.ign, self.binder, self.bwl, self.bwh): w_.valueChanged.connect(lambda _v: self.settings_changed())
            self.subch.toggled.connect(lambda _c: self.settings_changed())
            self.canvas.mpl_connect("button_press_event", self._press); self.canvas.mpl_connect("motion_notify_event", self._move); self.canvas.mpl_connect("button_release_event", self._release)
            self.refresh()

        # ---- settings
        def reload(self):
            T, m, name, cols, used = read_tga_file(self.path, self.tcol.currentText(), self.mcol.currentText()); self.a = TgaAnalysis(T, m, name, self._settings()); self.refresh()

        def _settings(self):
            return {"temperature_unit": self.unit.currentText(), "normalise": ["initial", "dry", "ignited"][self.norm.currentIndex()], "T_ref": self.tref.value(), "window_C": self.win.value(),
                    "heating_rate": self.rate.value() or None, "dtg_unit": self.dunit.currentText(), "method": self.method.currentText(), "ignited_T": self.ign.value() or None,
                    "binder_factor": self.binder.value() or None, "bw_low": self.bwl.value(), "bw_high": self.bwh.value(), "subtract_ch_water": self.subch.isChecked()}

        def settings_changed(self):
            old = (self.a.settings["temperature_unit"], self.a.settings["normalise"], self.a.settings["T_ref"], self.a.settings["window_C"]); self.a.settings.update(self._settings())
            new = (self.a.settings["temperature_unit"], self.a.settings["normalise"], self.a.settings["T_ref"], self.a.settings["window_C"]); self.a.compute(new_zones=(old[0] != new[0])); self.refresh()

        def _material(self):
            n = offer_remembered(self.material.text(), self.a)
            if n: self.ws.set_status(f"{n} zone name(s) you confirmed before for '{self.material.text()}' are offered first - confirm them again for this run."); self.refresh()

        # ---- table and graph
        def refresh(self):
            self._busy = True; a = self.a; rows = a.rows(); self.table.setRowCount(len(rows)); f = lambda v, n=2: "" if v is None or not np.isfinite(v) else f"{v:.{n}f}"
            for i, (z, r) in enumerate(zip(a.zones, rows)):
                c = QTableWidgetItem(); c.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable); c.setCheckState(Qt.Checked if z["confirmed"] else Qt.Unchecked); c.setToolTip("Tick: this name is yours and is written on exports. Untick: it stays a suggestion with '?'"); self.table.setItem(i, 0, c)
                nm = QTableWidgetItem(z["name"] if z["confirmed"] else (z["suggested"] + " ?")); nm.setToolTip("Suggested: " + z["suggested"] + ("\nOther candidates: " + "; ".join(z["candidates"][1:]) if len(z["candidates"]) > 1 else "") + "\nType your own name to replace it; empty = unlabelled"); self.table.setItem(i, 1, nm)
                cb = QComboBox(); [cb.addItem(lab, key) for key, lab in SPECIES]; cb.setCurrentIndex(max(0, [k for k, _l in SPECIES].index(z["species"] if z["confirmed"] else ""))); cb.setEnabled(z["confirmed"])
                cb.setToolTip("The phase whose content is calculated from this zone. Only for a zone whose name you confirmed"); cb.currentIndexChanged.connect(lambda _i, i=i, cb=cb: self._species(i, cb.currentData())); self.table.setCellWidget(i, 2, cb)
                vals = [f(r["T1"], 0), f(r["T2"], 0), f(r["T_peak"], 0), f(r["onset"], 0), f(r["endset"], 0), f(r["dm_stepwise"]), f(r["dm_tangent"]), (f"{r['content_name']} {r['content']:.2f} wt.%" if r.get("content_name") else ""),
                        f(r.get("content_ignited_basis")), z["confidence"]]
                for j, v in enumerate(vals):
                    it = QTableWidgetItem(v); it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | (Qt.ItemIsEditable if j < 2 else Qt.NoItemFlags)); it.setToolTip(z["source"] if j == 9 else ("Type a temperature to move this edge" if j < 2 else "")); self.table.setItem(i, 3 + j, it)
            s = a.summary(); self.sumlab.setText("  ·  ".join(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}" for k, v in s.items() if k != "sample") + f"\nUnconfirmed names: {sum(1 for z in a.zones if not z['confirmed'])} (shown with '?', never exported).")
            a.figure(fig=self.fig); self.canvas.draw_idle(); self._busy = False

        def _item_changed(self, it):
            if self._busy: return
            i, j = it.row(), it.column(); z = self.a.zones[i]
            if j == 0:
                if it.checkState() == Qt.Checked: self.a.confirm(i, (self.table.item(i, 1).text().replace(" ?", "").strip() or z["suggested"]), z.get("_species") or None)
                else: self.a.unconfirm(i)
            elif j == 1:
                t = it.text().replace(" ?", "").strip()
                if t and t != z["suggested"]: self.a.confirm(i, t)          # a name typed by the user is the user's
                elif not t: self.a.unconfirm(i); z["suggested"] = ""
            elif j in (3, 4):
                try: self.a.set_edge(i, j - 3, float(it.text().replace(",", ".")))
                except ValueError: pass
            remember_labels(self.material.text(), self.a); self.refresh()

        def _species(self, i, key):
            if self._busy: return
            self.a.zones[i]["species"] = key or ""; self.refresh()

        def _sel(self): return sorted({i.row() for i in self.table.selectedItems()})

        def _zone_menu(self, pos):
            from PySide6.QtWidgets import QMenu
            r = self.table.rowAt(pos.y()); m = QMenu(self)
            if r >= 0:
                z = self.a.zones[r]; self.table.selectRow(r)
                m.addAction("Edit limits…", lambda: self._limits(r)); m.addAction("Rename (confirm)…", lambda: self._rename(r))
                sub = m.addMenu("Use a candidate name")
                for c in z["candidates"] or ["(no candidate for this temperature)"]: sub.addAction(c, lambda c=c: (self.a.confirm(r, c), self.refresh())) if z["candidates"] else sub.addAction(c).setEnabled(False)
                m.addAction("Leave unlabelled", lambda: (self.a.unconfirm(r), self.a.zones[r].update(suggested=""), self.refresh()))
                m.addAction("Compute mass loss here", lambda: QMessageBox.information(self, "Mass loss", self._loss_text(r))); m.addAction("Delete", self.delete)
            m.addAction("Add zone…", self.add_zone); m.exec(self.table.viewport().mapToGlobal(pos))

        def _loss_text(self, r):
            x = self.a.rows()[r]; return f"{x['T1']:.0f} – {x['T2']:.0f} °C\nstepwise: {x['dm_stepwise']:.2f} %\ntangent: " + (f"{x['dm_tangent']:.2f} %" if x["dm_tangent"] is not None else "not possible this close to the end of the run")

        def _limits(self, r):
            z = self.a.zones[r]; t, ok = QInputDialog.getText(self, "Zone limits", "From, to (°C):", text=f"{z['T'][0]:.0f}, {z['T'][1]:.0f}")
            if ok:
                try: a, b = [float(x) for x in re.split(r"[;,\s]+", t.strip()) if x][:2]; self.a.set_edge(r, 0, min(a, b)); self.a.set_edge(r, 1, max(a, b)); self.refresh()
                except Exception: self.ws.set_status("Type two temperatures, e.g. 400, 530.")

        def _rename(self, r):
            z = self.a.zones[r]; t, ok = QInputDialog.getItem(self, "Name of the zone", "Your name for this zone (it is written on exports):", [z["name"] or z["suggested"]] + [c for c in z["candidates"] if c != z["suggested"]], 0, True)
            if ok and t.strip(): self.a.confirm(r, t.strip()); remember_labels(self.material.text(), self.a); self.refresh()

        def confirm_all(self):
            for i, z in enumerate(self.a.zones):
                if not z["confirmed"] and z["suggested"] and z["suggested"] != "Unassigned": self.a.confirm(i, z["suggested"], z.get("_species") or None)
            remember_labels(self.material.text(), self.a); self.refresh()

        def add_zone(self, T1=None, T2=None):
            if T1 is None:
                t, ok = QInputDialog.getText(self, "Add zone", "From, to (°C):", text="400, 530")
                if not ok: return
                try: T1, T2 = [float(x) for x in re.split(r"[;,\s]+", t.strip()) if x][:2]
                except Exception: self.ws.set_status("Type two temperatures, e.g. 400, 530."); return
            self.a.add_zone(T1, T2); self.refresh()

        def merge(self):
            s = self._sel()
            if s: self.a.merge(s[0]); self.refresh()

        def split(self):
            s = self._sel()
            if not s: return
            z = self.a.zones[s[0]]; t, ok = QInputDialog.getDouble(self, "Split zone", "Split at (°C):", (z["T"][0] + z["T"][1]) / 2, z["T"][0], z["T"][1], 0)
            if ok: self.a.split(s[0], t); self.refresh()

        def delete(self):
            for i in reversed(self._sel()): self.a.delete_zone(i)
            self.refresh()

        # ---- dragging zone edges on the graph
        def _near(self, e):
            if e.inaxes is None or e.xdata is None: return None
            x0, x1 = self.a.ax.get_xlim(); tol = abs(x1 - x0) * 0.012; best = None
            for i, z in enumerate(self.a.zones):
                for k in (0, 1):
                    dd = abs(e.xdata - z["T"][k])
                    if dd < tol and (best is None or dd < best[2]): best = (i, k, dd)
            return best

        def _press(self, e):
            from PySide6.QtWidgets import QApplication as QA
            if e.button != 1 or e.xdata is None: return
            if QA.keyboardModifiers() & Qt.AltModifier: self._drag = ("new", e.xdata); return
            n = self._near(e)
            if n: self._drag = ("edge", n[0], n[1])

        def _move(self, e):
            if self._drag is None:
                self.canvas.setCursor(Qt.SizeHorCursor if self._near(e) else Qt.ArrowCursor); return
            if e.xdata is None: return
            if self._drag[0] == "edge": self.a.set_edge(self._drag[1], self._drag[2], e.xdata); self.a.figure(fig=self.fig); self.canvas.draw_idle()

        def _release(self, e):
            d, self._drag = self._drag, None
            if d is None: return
            if d[0] == "new" and e.xdata is not None and abs(e.xdata - d[1]) > 3: self.a.add_zone(d[1], e.xdata)
            self.refresh()

        # ---- out
        def _folder(self):
            try: base = self.ws.outdir.text().strip()
            except Exception: base = ""
            return base or os.path.dirname(self.path)

        def export(self, path=None):
            if not path:
                path, _ = QFileDialog.getSaveFileName(self, "Export results to Excel", os.path.join(self._folder(), f"{self.a.name}_TGA_results.xlsx"), "Excel workbook (*.xlsx)")
                if not path: return None
            n = sum(1 for z in self.a.zones if not z["confirmed"]); self.a.export_excel(path)
            self.ws.set_status(f"Excel written: {path} (Data, Peaks, Zones, Summary, Chart)" + (f". {n} zone(s) have no confirmed name: they are exported without a name." if n else "")); return path

        def copy(self):
            QApplication.clipboard().setText(self.a.table_text()); self.ws.set_status("The results table is on the clipboard (paste it into Excel or Word).")

        def save_graph(self, path=None):
            from opstudio import core
            if not path:
                path, _ = QFileDialog.getSaveFileName(self, "Save the graph", os.path.join(self._folder(), f"{self.a.name}_TG_DTG.png"), "PNG (*.png);;TIFF (*.tiff);;PDF (*.pdf);;SVG (*.svg)")
                if not path: return None
            fig = self.a.figure(final=True); core.save(fig, path, exact=True, **({"pil_kwargs": {"compression": "tiff_lzw"}} if path.lower().endswith((".tif", ".tiff")) else {})); self.ws.set_status(f"Graph written: {path} (names without your confirmation are left out)."); return path

        def origin(self, folder=None):
            from opstudio import origin as O
            import origin_plot_app as opa
            folder = folder or os.path.join(self._folder(), "Origin"); fig = self.a.figure(final=True); note = [""]
            def mk(f):
                if getattr(self, "force_dry", False): return opa.Driver(f, self.ws.log, dry=True)
                try: return opa.Driver(f, self.ws.log, dry=False)
                except Exception as e: note[0] = str(e); return opa.Driver(f, self.ws.log, dry=True)
            r = O.draw_in_origin(mk, fig, self.a.name, "tga_dtg", folder)
            self.ws.set_status((f"Origin could not be started ({note[0]}): the worksheets and the script were written to {folder}" if note[0] else f"Drawn in Origin: {r['project']}")); return r

    return TgaDialog


_CLS = []
def dialog_class():
    """The window class (made on first use, so that the calculations can be used without Qt)."""
    if not _CLS: _CLS.append(_dialog_class())
    return _CLS[0]

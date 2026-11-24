"""
tga_core.py - reference implementation of the TGA / DTG calculations the app must offer.

Every function returns plain numbers + the exact settings used, so the app can show them, store them in the
project and export them to Excel. Nothing here assigns a phase name with certainty: `suggest_zones` returns
candidate names with a `needs_confirmation` flag and the app MUST ask the user to confirm or rename them.

Conventions
-----------
* mass in % of a reference mass (initial, dried at T_dry, or ignited at T_ign - user's choice, stored).
* DTG = dm/dT in % per °C (natural sign: mass loss -> negative). %/min = (%/°C) x heating rate (°C/min).
* Temperatures in °C.
"""
from __future__ import annotations
import numpy as np
from scipy.signal import savgol_filter, find_peaks

M = {"H2O": 18.015, "CO2": 44.009, "CaOH2": 74.093, "CaCO3": 100.087, "MgOH2": 58.320, "CaO": 56.077}

# Default zone suggestions for cementitious / raw materials. Shown as SUGGESTIONS with a source note; user confirms.
REFERENCE_EVENTS = [
    {"name": "Free / adsorbed water", "T": [30, 105], "gas": "H2O", "applies_to": "all"},
    {"name": "C-S-H + ettringite (AFt) dehydration", "T": [50, 200], "gas": "H2O", "applies_to": "hydrated paste"},
    {"name": "Gypsum -> hemihydrate/anhydrite", "T": [100, 170], "gas": "H2O", "applies_to": "cement, raw gypsum"},
    {"name": "AFm phases (monosulfate, hemi/monocarbonate)", "T": [150, 250], "gas": "H2O", "applies_to": "hydrated paste"},
    {"name": "Hydrotalcite / brucite", "T": [330, 420], "gas": "H2O", "applies_to": "slag, MgO-rich"},
    {"name": "Portlandite Ca(OH)2 dehydroxylation", "T": [400, 550], "gas": "H2O", "applies_to": "hydrated paste, slaked lime"},
    {"name": "Kaolinite dehydroxylation", "T": [450, 600], "gas": "H2O", "applies_to": "clays"},
    {"name": "Weakly bound / amorphous carbonates", "T": [480, 700], "gas": "CO2", "applies_to": "carbonated paste"},
    {"name": "Calcite decarbonation", "T": [600, 800], "gas": "CO2", "applies_to": "raw material, carbonated paste, lime mud"},
    {"name": "Dolomite decarbonation (two steps)", "T": [700, 850], "gas": "CO2", "applies_to": "dolomitic raw materials"},
    {"name": "Mica (muscovite/illite) dehydroxylation", "T": [600, 900], "gas": "H2O", "applies_to": "tailings, clays"},
    {"name": "alpha-beta quartz inversion (no mass change; DSC/DTA only)", "T": [570, 576], "gas": None, "applies_to": "quartz-bearing"},
]
SOURCE_NOTE = ("Typical ranges from the cement TGA literature (e.g. RILEM TC-238 practical guide, Lothenbach et al.); "
               "ranges overlap and shift with heating rate, sample mass and atmosphere - always confirm per dataset.")


# ----------------------------------------------------------------------------------------------- basics
def normalise(T, mass, mode="initial", T_ref=None):
    """mode: 'initial' (first point), 'dry' (mass at T_ref, e.g. 40 or 105 °C), 'ignited' (mass at T_ref, e.g. 550 or 1000 °C)."""
    T = np.asarray(T, float); mass = np.asarray(mass, float)
    if mode == "initial":
        ref = mass[0]
    else:
        ref = float(np.interp(T_ref, T, mass))
    return mass / ref * 100.0, {"mode": mode, "T_ref": T_ref, "ref_mass": ref}


def dtg(T, mass, window_C=15.0, poly=2, heating_rate=None):
    """Savitzky-Golay derivative on a uniform grid. Returns DTG in %/°C (and %/min if heating_rate given)."""
    T = np.asarray(T, float); mass = np.asarray(mass, float)
    dT = np.median(np.diff(T))
    win = max(poly + 3, int(round(window_C / dT)) | 1)
    d = savgol_filter(mass, win, poly, deriv=1, delta=dT)
    out = {"dtg_per_C": d, "window_points": win, "window_C": window_C, "poly": poly}
    if heating_rate:
        out["dtg_per_min"] = d * heating_rate
    return out


def find_dtg_peaks(T, d, prominence_frac=0.03, min_sep_C=25.0):
    """Mass-loss peaks = minima of DTG (natural sign). Returns list of dicts with T_peak, DTG value, bounds."""
    T = np.asarray(T, float); y = -np.asarray(d, float)
    dT = np.median(np.diff(T))
    idx, props = find_peaks(y, prominence=prominence_frac * np.nanmax(y), distance=max(1, int(min_sep_C / dT)))
    peaks = []
    for i, k in enumerate(idx):
        peaks.append({"T_peak": float(T[k]), "dtg_peak": float(-y[k]), "T_left": float(T[props["left_bases"][i]]),
                      "T_right": float(T[props["right_bases"][i]]), "prominence": float(props["prominences"][i])})
    return peaks


def onset_endset(T, mass, d, T_peak, fit_C=20.0):
    """Extrapolated onset/endset: tangent at the DTG extremum (inflection of TG) intersected with the
    linear baselines fitted just before/after the step (fit_C wide)."""
    T = np.asarray(T, float); mass = np.asarray(mass, float)
    k = int(np.argmin(abs(T - T_peak)))
    slope = d[k]; icpt = mass[k] - slope * T[k]
    # walk outwards until |DTG| < 10 % of peak to locate plateaux
    thr = 0.1 * abs(d[k]); l = k
    while l > 0 and abs(d[l]) > thr:
        l -= 1
    r = k
    while r < len(T) - 1 and abs(d[r]) > thr:
        r += 1
    pre = (T >= T[l] - fit_C) & (T <= T[l]); post = (T >= T[r]) & (T <= T[r] + fit_C)
    res = {"T_peak": float(T[k])}
    for nm, m in (("onset", pre), ("endset", post)):
        if m.sum() >= 3:
            b1, a1 = np.polyfit(T[m], mass[m], 1)
            res[nm] = float((a1 - icpt) / (slope - b1)) if slope != b1 else float("nan")
        else:
            res[nm] = float("nan")
    return res


def stepwise_loss(T, mass, T1, T2):
    return float(np.interp(T1, T, mass) - np.interp(T2, T, mass))


def tangent_step(T, mass, T1, T2, fit_C=25.0):
    """Tangent (step) method: linear fits on TG before T1 and after T2; Δm read at the DTG peak temperature
    inside [T1, T2]. Removes the background loss of C-S-H etc. that continues through the step."""
    T = np.asarray(T, float); mass = np.asarray(mass, float)
    pre = (T >= T1 - fit_C) & (T <= T1); post = (T >= T2) & (T <= T2 + fit_C)
    pl = np.polyfit(T[pre], mass[pre], 1); ql = np.polyfit(T[post], mass[post], 1)
    w = (T >= T1) & (T <= T2); dd = np.gradient(mass[w], T[w]); Tm = float(T[w][np.argmin(dd)])
    m_pre = float(np.polyval(pl, Tm)); m_post = float(np.polyval(ql, Tm))
    return {"T1": T1, "T2": T2, "T_mid": Tm, "m_pre": m_pre, "m_post": m_post, "dm": m_pre - m_post,
            "pre_line": pl, "post_line": ql, "fit_C": fit_C}


def suggest_zones(T, d, peaks=None):
    """Split the curve at DTG returns-to-baseline between peaks and attach candidate names from REFERENCE_EVENTS.
    Every zone has needs_confirmation=True. The app must ask the user to confirm/rename in the moment."""
    T = np.asarray(T, float); d = np.asarray(d, float)
    peaks = sorted(peaks or find_dtg_peaks(T, d), key=lambda p: p["T_peak"])
    ks = [int(np.argmin(abs(T - p["T_peak"]))) for p in peaks]
    zones = []
    for j, (p, k) in enumerate(zip(peaks, ks)):
        thr = max(0.05 * abs(d[k]), 1.5 * float(np.median(abs(d))))  # ignore slow background drift
        # left/right limits: return to near-baseline, or the DTG maximum (closest to zero) between neighbouring peaks
        lo = ks[j - 1] + int(np.argmax(d[ks[j - 1]:k])) if j > 0 else None
        hi = k + int(np.argmax(d[k:ks[j + 1]])) if j < len(ks) - 1 else None
        l = k
        while l > (lo or 0) and abs(d[l]) > thr:
            l -= 1
        r = k
        while r < (hi if hi is not None else len(T) - 1) and abs(d[r]) > thr:
            r += 1
        cands = [e for e in REFERENCE_EVENTS if e["gas"] and e["T"][0] <= p["T_peak"] <= e["T"][1]]
        cands.sort(key=lambda e: abs(p["T_peak"] - np.mean(e["T"])) / ((e["T"][1] - e["T"][0]) / 2))  # most central first
        zones.append({"T": [float(T[l]), float(T[r])], "T_peak": p["T_peak"],
                      "candidates": [c["name"] for c in cands], "suggested": cands[0]["name"] if cands else "Unassigned",
                      "confidence": "medium" if len(cands) == 1 else ("low" if cands else "none"),
                      "needs_confirmation": True, "source": SOURCE_NOTE})
    return zones


def quantify(T, mass, zones_confirmed, method="tangent", ignited_T=None):
    """zones_confirmed: list of {name, T:[T1,T2], species: 'CH'|'CaCO3'|'MgOH2'|None}.
    Returns per-zone losses and derived contents. Ignited-basis values if ignited_T given."""
    T = np.asarray(T, float); mass = np.asarray(mass, float)
    ign = float(np.interp(ignited_T, T, mass)) if ignited_T else None
    rows = []
    for z in zones_confirmed:
        T1, T2 = z["T"]
        sw = stepwise_loss(T, mass, T1, T2)
        tg = tangent_step(T, mass, T1, T2)["dm"] if method == "tangent" else None
        dm = tg if tg is not None else sw
        row = {"zone": z["name"], "T1": T1, "T2": T2, "dm_stepwise": sw, "dm_tangent": tg, "dm_used": dm, "method": method}
        sp = z.get("species")
        if sp == "CH":
            row["content_name"], row["content"] = "Ca(OH)2", dm * M["CaOH2"] / M["H2O"]
        elif sp == "CaCO3":
            row["content_name"], row["content"] = "CaCO3", dm * M["CaCO3"] / M["CO2"]
        elif sp == "MgOH2":
            row["content_name"], row["content"] = "Mg(OH)2", dm * M["MgOH2"] / M["H2O"]
        if ign:
            row["dm_ignited_basis"] = dm / ign * 100
            if "content" in row:
                row["content_ignited_basis"] = row["content"] / ign * 100
        rows.append(row)
    summary = {"total_loss": float(mass[0] - mass[-1]), "residue": float(mass[-1]), "ignited_mass": ign,
               "ignited_T": ignited_T, "method": method}
    return rows, summary


def bound_water(T, mass, T_low=50.0, T_high=550.0, ignited_T=None, subtract_CH_water=0.0):
    """H_bound = m(T_low) - m(T_high) (minus CH water if the user wants 'non-CH bound water'); ignited basis optional."""
    w = stepwise_loss(T, mass, T_low, T_high) - subtract_CH_water
    out = {"T_low": T_low, "T_high": T_high, "bound_water": w}
    if ignited_T:
        ign = float(np.interp(ignited_T, T, mass)); out["bound_water_ignited_basis"] = w / ign * 100; out["ignited_T"] = ignited_T
    return out


# ----------------------------------------------------------------------------------------------- export
def export_excel(path, sample, T, mass, d, peaks, rows, summary, settings):
    """Sheets: Data, Peaks, Zones, Summary (settings + formulas), Chart (TG + DTG on secondary axis, DTG not reversed)."""
    from openpyxl import Workbook
    from openpyxl.chart import ScatterChart, Reference, Series
    from openpyxl.styles import Font
    wb = Workbook(); ws = wb.active; ws.title = "Data"
    ws.append(["Temperature (°C)", f"{sample} mass (%)", f"{sample} DTG (% °C-1)"])
    for a, b, c in zip(T, mass, d):
        ws.append([float(a), float(b), float(c)])
    p = wb.create_sheet("Peaks"); p.append(["T_peak (°C)", "DTG at peak (% °C-1)", "Onset (°C)", "Endset (°C)", "Label (user-confirmed)"])
    for q in peaks:
        p.append([q["T_peak"], q["dtg_peak"], q.get("onset"), q.get("endset"), q.get("label", "")])
    z = wb.create_sheet("Zones"); z.append(["Zone (user-confirmed)", "T1 (°C)", "T2 (°C)", "Δm stepwise (%)", "Δm tangent (%)", "Δm used (%)",
                                            "Derived phase", "Content (wt.%)", "Content, ignited basis (wt.%)"])
    for r in rows:
        z.append([r["zone"], r["T1"], r["T2"], r["dm_stepwise"], r["dm_tangent"], r["dm_used"], r.get("content_name", ""),
                  r.get("content"), r.get("content_ignited_basis")])
    s = wb.create_sheet("Summary")
    for k, v in {**summary, **settings}.items():
        s.append([k, str(v) if isinstance(v, (list, dict)) else v])
    s.append([]); s.append(["Formulas", "CH = Δm(H2O) × 74.09/18.02 ; CaCO3 = Δm(CO2) × 100.09/44.01 ; ignited basis = value / m(T_ign) × 100"])
    s.append(["Zone names", "Confirmed by the user in the app; suggestions are never exported as confirmed labels."])
    for wsx in (ws, p, z, s):
        for c in wsx[1]:
            c.font = Font(bold=True)
    ch = ScatterChart(); ch.title = f"{sample}: TG and DTG"; ch.x_axis.title = "Temperature (°C)"; ch.y_axis.title = "Mass (%)"
    n = len(T) + 1; x = Reference(ws, min_col=1, min_row=2, max_row=n)
    s1 = Series(Reference(ws, min_col=2, min_row=1, max_row=n), x, title_from_data=True); s1.marker.symbol = "none"; ch.series.append(s1)
    ch2 = ScatterChart(); s2 = Series(Reference(ws, min_col=3, min_row=1, max_row=n), x, title_from_data=True); s2.marker.symbol = "none"
    ch2.series.append(s2); ch2.y_axis.axId = 200; ch2.y_axis.title = "DTG (% °C-1)"; ch2.y_axis.crosses = "max"
    ch += ch2; ch.width, ch.height = 24, 13
    wb.create_sheet("Chart").add_chart(ch, "A1")
    wb.save(path)
    return path

"""
smart_plots.py - reads a data file, works out what each table is (XRD, fit, FTIR, TGA,
particle size distribution, calorimetry, or plain XY), does the analysis that kind of
graph needs, and returns a "spec" that can be drawn either as a preview (matplotlib) or
in Origin (see origin_plot_app.py).

Only numpy and pandas are needed for the analysis; matplotlib only for the preview.
"""
import os, sys, re, io, csv, math, json, hashlib, datetime
import numpy as np
import pandas as pd
import xrd_smart as xs

# colours for several series: the Okabe-Ito set, which stays distinguishable for colour-blind readers and in print
PALETTE = [(0, 0, 0), (213, 94, 0), (0, 114, 178), (0, 158, 115), (204, 121, 167), (230, 159, 0), (86, 180, 233), (110, 110, 110), (136, 34, 85), (51, 34, 136)]
FONTS = ["Arial", "Helvetica", "Liberation Sans", "Nimbus Sans", "DejaVu Sans"]      # Arial on Windows; the others only where Arial is missing
PUB_WIDTHS = {"single": 140.0, "combined": 175.0}                                   # mm: one graph (1.5 columns), stacked / combined figure (full width)

_SUP = {"\u207b": "-", "\u207a": "+", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3", "\u2070": "0", "\u2074": "4", "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9"}
_MARK = re.compile(r"(?<!\$)([\^_])\{([^{}]*)\}")
def _mark_mt(t, bold=False):
    """Typed superscript ^{...} and subscript _{...} (the X² and X₂ buttons) -> mathtext."""
    def one(m):
        body = re.sub(r"([\\#%&{}])", r"\\\1", m.group(2)).replace(" ", "\\ ").replace("-", "\u2212")
        return "$" + m.group(1) + "{" + ("\\mathbf{" + body + "}" if bold else body) + "}$"
    return _MARK.sub(one, t)

def _mt(t):
    """Unicode superscript/subscript characters -> mathtext, so cm-1 and CaCO3 are typeset properly in every font; ^{..} and _{..} typed
    in the app (X² / X₂) too."""
    t = str(t)
    if "$" in t: return t
    t = re.sub("[" + "".join(_SUP) + "]+", lambda m: "$^{" + "".join(_SUP[c] for c in m.group(0)).replace("-", "\u2212") + "}$", t)
    t = re.sub("[\u2080-\u2089]+", lambda m: "$_{" + "".join(str(ord(c) - 0x2080) for c in m.group(0)) + "}$", t)
    return _mark_mt(t)

def _lb(t):
    """A bold peak label: subscript characters as bold mathtext (C3S with a real subscript 3)."""
    return _mark_mt(re.sub("[\u2080-\u2089]+", lambda m: "$_{\\mathbf{" + "".join(str(ord(c) - 0x2080) for c in m.group(0)) + "}}$", str(t)), bold=True)

def apply_style():
    """One house style for every figure the app draws: sans-serif (Arial), text kept as text in PDF/SVG, ticks pointing in."""
    import matplotlib
    matplotlib.rcParams.update({"font.family": "sans-serif", "font.sans-serif": FONTS, "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
                                "mathtext.default": "regular", "mathtext.fontset": "custom", "mathtext.rm": "sans", "mathtext.it": "sans:italic", "mathtext.bf": "sans:bold", "mathtext.cal": "sans", "mathtext.sf": "sans", "mathtext.tt": "monospace",
                                "axes.unicode_minus": True, "savefig.facecolor": "white", "figure.facecolor": "white", "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
                                "text.color": "black", "axes.labelcolor": "black", "xtick.color": "black", "ytick.color": "black", "axes.edgecolor": "black"})
NAVY = (0, 0, 139)
VERSION = "5.54.5"
PROVENANCE_VERSION = "v5.15.0"          # the version written into the provenance file of every figure

class Cancelled(Exception):
    """The user pressed Cancel."""
TUBES = {"Automatic (from the file, else Cu Kα1)": 0, "Cu Kα1 (1.5406 Å)": 1.5406, "Co Kα1 (1.7890 Å)": 1.78897, "Fe Kα1 (1.9360 Å)": 1.93604, "Cr Kα1 (2.2897 Å)": 2.28970, "Mo Kα1 (0.7093 Å)": 0.70930, "Ag Kα1 (0.5594 Å)": 0.55941}
TGA_MATERIAL = ["No chemical assignment (mass-loss steps only)", "Cementitious sample: suggest Ca(OH)2 and CaCO3 (check them)"]
TGA_MASS = ["Automatic", "Already in %", "Absolute (mg or g): convert to % of the first point"]
TGA_CURVES = ["TG and DTG (two y axes)", "TG only (mass)", "DTG only (rate of mass loss)"]
TGA_PRESET_INTERVALS = [(50.0, 200.0), (400.0, 500.0), (600.0, 800.0)]        # the usual windows: bound water, Ca(OH)2, CaCO3
FTIR_SIGNAL = ["Automatic", "Absorbance", "Transmittance"]
PSD_STYLES = ["Distribution and cumulative in one graph (two y axes)", "Two panels (distribution above, cumulative below)", "Cumulative only", "Distribution only"]
REPLICATES = ["Mean with ± SD band", "Every curve"]
CEMENT_TGA = "40-105, 105-400, 400-500 CH, 600-800 CC"
TGA_TAGS = {"CH": ("Ca(OH)2", 74.093 / 18.015, "mass loss x 74.09 / 18.02 (H2O)"), "CC": ("CaCO3", 100.087 / 44.010, "mass loss x 100.09 / 44.01 (CO2)")}

XRD_PHASES = ["All phases in the library", "Clinker and cement: A B B' C F L P G Cal Q R Z", "Raw materials and minerals: Q Ab Mc Or Ms Bt Crd Cal Dol R Z"]
# Phase labels are only written when YOUR files give them (a label sheet, or the peak list / Bragg table of the same sample).
# The app's own phase suggestions from the library are an extra choice, never the default: a suggestion is not an identification.
XRD_LABELS = ["Only labels from my files (no guessing)", "Suggest phases from the library (check them)", "2θ values", "d-spacings (Å)", "No labels"]
XRD_BG = ["Not drawn", "Draw it (thin grey line)", "Subtract it (plot net intensity)"]
KEY_NOTE = "? = suggested phase without a strong peak of its own."
INSETS = ["Automatic on sample pages", "On every XRD pattern and fit", "No inset"]          # or a typed 2-theta range such as 27-37 (then single graphs get the inset too)
def zoom_auto(opt, every=False):
    """Does the app choose a zoomed part itself? 'Automatic' (fits and sample pages) or 'On every XRD pattern and fit' (every=True asks for the latter)."""
    v = str((opt or {}).get("inset") or INSETS[0])
    return v.startswith("On every") if every else v.startswith(("Auto", "On every"))
FIT_COLOURS = ["Black / red / blue (observed / calculated / difference)", "HighScore (observed red, calculated blue)"]
OBS_COL, CALC_COL, DIF_COL = (0, 0, 0), (224, 0, 0), (0, 0, 224)
LABEL_TEXT = ["Letters with a key (clean)", "Phase names on the peaks (C3S, C2S, Calcite ...)"]
POINTERS = ["Thin lines", "Arrows"]
LABEL_SIZES = ["Normal", "Large", "Extra large"]            # peak labels, in every graph
def label_mult(opt): return {"Large": 1.25, "Extra large": 1.5}.get(str((opt or {}).get("label_size") or LABEL_SIZES[0]), 1.0)
OWN_STYLES = ["Automatic", "Line", "Symbols", "Line + symbols", "Bars", "Histogram", "Box plot", "Contour map",
              "Phase assemblage (stacked areas)", "Phase amounts (lines)", "Phase assemblage (stacked bars)", "Change against the first row", "Pore solution (logarithmic)"]
INSET_RECT = (0.505, 0.45, 0.48, 0.52)             # zoomed inset: left, bottom, width, height as fractions of the panel (top right corner)
BRACKET_NOTE = "( ) = phase included in the refinement, no individually resolved peak"
SHORT_NAMES = {"A": "C3S", "B": "C2S", "B'": "\u03b1'-C2S", "C": "C3A", "F": "C4AF", "L": "CaO", "P": "MgO", "R": "Rutile", "Z": "ZnO", "G": "Gypsum", "Q": "Quartz",
               "Cal": "Calcite", "Dol": "Dolomite", "CH": "CH", "AFt": "AFt", "Hc": "Hc", "Mc*": "Mc"}
FIT_VIEWS = ["Pattern with labels (measured only)", "Fit: observed, calculated, difference"]      # how a fit file opens: the plain pattern first
FIT_MIDDLE = ["As the fit style", "Bragg tick rows", "Peaks with labels (from the peak list)", "Peaks with labels and tick rows", "Nothing"]
FIT_STYLES = ["HighScore look (pattern + difference curve)", "HighScore look + Bragg tick rows + difference curve", "HighScore look, pattern only (no difference curve)",
              "Paper style (black/red, tick rows, difference)"]
TUBE_NAMES = [(1.5406, "Copper (Cu)"), (1.78897, "Cobalt (Co)"), (1.93604, "Iron (Fe)"), (2.28970, "Chromium (Cr)"), (0.70930, "Molybdenum (Mo)"), (0.55941, "Silver (Ag)")]

STACK_STYLES = ["Clean (black / red / blue, main peaks labelled)", "Detailed (Bragg tick rows, wt% column)"]
HS_OBS, HS_CALC, DIFF_COL = (255, 0, 0), (0, 0, 255), (0, 139, 139)       # HighScore observed/calculated, GSAS-II-like teal difference
STACK_TICK = [(0, 128, 0), (255, 0, 255), (255, 140, 0), (128, 0, 128), (139, 69, 19), (0, 0, 0), (128, 128, 0), (220, 20, 60), (70, 130, 180), (105, 105, 105)]

def _quant_lines(rows, width=34):
    """'A 56.1, B 20.7, F 4.0 ...' lines (wt%) for a small box; amorphous written out."""
    parts = []
    for r in rows:
        nm = r["name"]; c = "Amorph." if nm.lower().startswith("amorph") else (r.get("code") or xs.code_for(nm))
        parts.append(f"{c} {r['wt']:.1f}")
    out, cur = [], ""
    for p_ in parts:
        if cur and len(cur) + len(p_) + 2 > width: out.append(cur + ","); cur = p_
        else: cur = (cur + ", " + p_) if cur else p_
    if cur: out.append(cur + " wt%")
    return out

def _wrap_key(entries, width=95):
    """[(colour, text), ...] -> lines of entries that fit the width (in characters)."""
    lines, cur, n = [], [], 0
    for col, txt in entries:
        if cur and n + len(txt) + 4 > width: lines.append(cur); cur, n = [], 0
        cur.append((col, txt)); n += len(txt) + 4
    if cur: lines.append(cur)
    return lines

def tube_name(lam):
    v, nm = min(TUBE_NAMES, key=lambda t_: abs(t_[0] - lam)); return nm if abs(v - lam) < 0.01 else f"λ = {lam:.4f} Å"

def wavelength(opt, d=None):
    """X-ray wavelength in Å: from the file when the setting is Automatic, otherwise from the settings (a tube name or a typed number)."""
    v = (opt or {}).get("wavelength", 0)
    if isinstance(v, str) and v.startswith("Automatic") or v in (0, None, ""): return float((d or {}).get("lam_file") or 1.5406)
    if isinstance(v, str):
        if v in TUBES: return TUBES[v]
        m = re.search(r"\d+[.,]\d+", v) or re.search(r"\d+", v); v = float(m.group(0).replace(",", ".")) if m else 1.5406
    return float(v) if 0.1 < float(v) < 5 else 1.5406

def phase_filter(opt):
    v = str((opt or {}).get("xrd_phases") or XRD_PHASES[0])
    if v.startswith("All"): return None
    codes = [c.strip(" ,;") for c in v.split(":")[-1].split()]; return [c for c in codes if c] or None

_LIB = {}
STORE_FILE = "stored_phases.csv"; STORE_COLS = ["Phase", "Code", "d (A)", "I_rel (%)", "Origin", "Added"]; STORE_MIN = 3; STORE_NEWS = []
def store_dir(opt=None):
    """Where your own phases are kept. It is outside the app folder, so the phases stay when you unzip a new version of the app."""
    v = (opt or {}).get("store_dir") or os.environ.get("ORIGIN_PLOT_APP_HOME")
    if not v: v = os.path.join(os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config"), "OriginPlotApp")
    return os.path.join(v, "phase_library")

def library(opt):
    """(phase library, signature). The library is the built-in one plus everything in your own store."""
    folder = (opt or {}).get("app_dir") or os.path.dirname(os.path.abspath(__file__)); extra = (store_dir(opt),)
    try:                                                     # phase files that were put into a plugin folder count like your own store
        import paper_figures as pf_
        extra = extra + tuple(d_ for d_ in pf_.plugin_dirs() if os.path.isdir(d_))
    except Exception: pass
    sig = tuple((f, os.path.getmtime(f), os.path.getsize(f)) for f in xs.library_files(folder, extra))
    if _LIB.get("sig") != sig:
        _LIB.update(sig=sig, lib=xs.load_library(folder, extra))
        for c, nm in _LIB["lib"].drop_duplicates("Code")[["Code", "Phase"]].values:          # the key of a graph names your own phases too
            nm = re.sub(r"\s*\(" + re.escape(str(c)) + r"\)\s*$", "", str(nm)).strip()
            if nm and nm.lower() != "nan": xs.CODE_NAMES.setdefault(str(c), nm[:1].lower() + nm[1:] if nm[1:2].islower() else nm)
    return _LIB["lib"], sig

def _stored(opt):
    f = os.path.join(store_dir(opt), STORE_FILE)
    try: t = pd.read_csv(f, encoding="utf-8-sig", dtype={"Code": str, "Phase": str}) if os.path.exists(f) else None
    except Exception: t = None
    if t is None or not set(STORE_COLS[:4]) <= set(t.columns): t = pd.DataFrame(columns=STORE_COLS)
    for c in STORE_COLS:
        if c not in t.columns: t[c] = ""
    return t[STORE_COLS], f

def _unwanted(opt, add=(), drop=()):
    """Codes you removed from the store: the app does not store them again by itself (adding the phase yourself lifts this)."""
    f = os.path.join(store_dir(opt), "removed_by_you.txt")
    try: have = [l.strip() for l in open(f, encoding="utf-8").read().splitlines() if l.strip()] if os.path.exists(f) else []
    except Exception: have = []
    new = [c for c in dict.fromkeys(have + [str(c) for c in add]) if c not in set(str(c) for c in drop)]
    if new != have:
        try: os.makedirs(os.path.dirname(f), exist_ok=True); open(f, "w", encoding="utf-8").write("\n".join(new) + ("\n" if new else ""))
        except Exception: pass
    return set(new)

def _write_store(t, f):
    os.makedirs(os.path.dirname(f), exist_ok=True); tmp = f + ".tmp"
    t.to_csv(tmp, index=False, encoding="utf-8-sig"); os.replace(tmp, f)

def store_phases(rows, opt, origin, replace=False):
    """Keep the phases of `rows` (Phase, Code, d, I) for future phase suggestions. A phase is stored when the library does
    not have its code yet and it has at least STORE_MIN lines with an intensity. replace=True (a phase you add yourself)
    also replaces a phase stored earlier; built-in phases are never changed. Returns (stored [(code, name, lines)], skipped lines)."""
    opt = opt or {}; done, skip = [], []
    if rows is None or not len(rows): return done, skip
    lib, _ = library(opt); old, f = _stored(opt); src = dict(zip(lib["Code"].astype(str), lib["Source"].astype(str)))        # code -> the file its lines come from
    r = rows.copy(); r["Code"] = r["Code"].astype(str).str.strip(); r["d"] = pd.to_numeric(r["d"], errors="coerce"); r["I"] = pd.to_numeric(r["I"], errors="coerce")
    r = r[np.isfinite(r["d"]) & np.isfinite(r["I"]) & (r["I"] > 0) & (r["d"] > 0.3) & (r["d"] < 60)]
    import datetime as _dt
    day = _dt.date.today().isoformat(); add = []; no = set() if replace else _unwanted(opt)
    for c in dict.fromkeys(r["Code"]):
        if c in no: continue                               # you removed this phase from the store: it is not stored again by itself
        g = r[r["Code"] == c].sort_values("d", ascending=False); g = g[~g["d"].round(4).duplicated()]; nm = str(g["Phase"].iloc[0]).strip() if len(g) else c
        nm = re.sub(r"\s*\(" + re.escape(c) + r"\)\s*$", "", nm) or nm                    # 'Portlandite (CH)' -> Portlandite
        if not c or c.lower() in ("nan", "none", "?"): continue
        if c in src and not (replace and src[c] == f):          # the library has this code already (a phase you stored yourself may be replaced by you)
            if replace: skip.append(f"{c} = {nm}: the library already has the code {c} ({lib.loc[lib['Code'] == c, 'Phase'].iloc[0]}). Built-in phases are kept; give your phase another code, for example '{nm} ({c}2).csv'")
            continue
        if len(g) < STORE_MIN: skip.append(f"{c} = {nm}: only {len(g)} line(s) with an intensity; at least {STORE_MIN} are needed to recognise a phase"); continue
        I = 100 * g["I"] / g["I"].max()
        add.append(pd.DataFrame({"Phase": nm, "Code": c, "d (A)": g["d"].round(5).values, "I_rel (%)": I.round(2).values, "Origin": origin, "Added": day})); done.append((c, nm, len(g)))
    if add:
        keep = old[~old["Code"].astype(str).isin([c for c, _, _ in done])]
        _write_store(pd.concat([keep] + add, ignore_index=True) if len(keep) else pd.concat(add, ignore_index=True), f); _LIB.clear()
        if replace: _unwanted(opt, drop=[c for c, _, _ in done])
        STORE_NEWS.extend(f"stored for future phase suggestions: {c} = {nm} ({n} lines), {origin}" for c, nm, n in done)
    return done, skip

def store_news():
    """The phases stored since the last call (for the log of the app)."""
    out = list(dict.fromkeys(STORE_NEWS)); STORE_NEWS.clear(); return out

def library_table(opt):
    """One row per phase of the library: Code, Phase, Lines, Kind (built in / stored / your file), Origin, Added, Removable."""
    folder = (opt or {}).get("app_dir") or os.path.dirname(os.path.abspath(__file__)); lib, _ = library(opt); old, f = _stored(opt); rows = []
    for c in dict.fromkeys(lib["Code"]):
        g = lib[lib["Code"] == c]; src = str(g["Source"].iloc[0]); o = old[old["Code"].astype(str) == str(c)]
        if src == f and len(o): kind, origin, added, rem = "stored", str(o["Origin"].iloc[0]), str(o["Added"].iloc[0]), True
        elif src == "xrd_phase_library.csv": kind, origin, added, rem = "built in", "built-in phase library (delivered with the app)", "", False
        else: kind, origin, added, rem = "your file", os.path.basename(src) + (" (next to the app)" if os.sep not in src else ""), "", False
        rows.append({"Code": str(c), "Phase": str(g["Phase"].iloc[0]), "Lines": len(g), "Kind": kind, "Origin": origin, "Added": added, "Removable": rem})
    return rows

def remove_stored(codes, opt):
    """Take phases out of your store. Built-in phases and your own csv files are not touched. Returns the codes removed."""
    old, f = _stored(opt); codes = [str(c) for c in codes]; gone = [c for c in dict.fromkeys(old["Code"].astype(str)) if c in codes]
    if gone: _write_store(old[~old["Code"].astype(str).isin(gone)], f); _LIB.clear(); _unwanted(opt, add=gone)
    return gone

def add_phase_file(path, opt):
    """Add the phase(s) of a file to your store: a table with d (Å) or 2θ (Cu Kα1) and relative intensities, for example a
    reference card exported from HighScore, or a peak list with Phase Assignment. Without a phase column the file name is
    the phase name; a code in brackets at its end is the label, e.g. 'Portlandite (CH).csv'. Returns (stored, message lines)."""
    name = os.path.splitext(os.path.basename(path))[0]; msgs = []; u = None
    try:                                                   # a peak list with phase assignment (HighScore): read the way the app reads it for drawing
        items, _ = load_file(path); parts = []
        for it in items:
            if it.det.get("kind") != "XRD peak list" or it.det.get("phase") is None: continue
            r = peaklist_rows(it.det, wavelength(opt, it.det))
            if r.attrs.get("markers") or not len(r): continue
            parts.append(pd.DataFrame({"Phase": r["Phase"].values, "Code": r["Code"].values, "d": r["d"].values, "I": r["height"].values}))
        if parts: u = pd.concat(parts, ignore_index=True)
    except Exception: u = None
    if u is None:                                          # a plain table: d or 2θ, intensity, optionally phase and code
        try:
            if path.lower().endswith((".xlsx", ".xlsm", ".xls")): tabs = [t for _, t in _excel_tables(path)]; raw = True
            else:
                tabs = []; raw = False
                for sep_ in (None, ",", ";", "\t", r"\s+"):
                    try: tabs.append(pd.read_csv(path, encoding="utf-8-sig", sep=sep_, engine="python"))
                    except Exception: pass
                if not tabs: raise ValueError("not a table of numbers")
        except Exception as e: return [], [f"{os.path.basename(path)}: could not be read ({str(e)[:160]})"]
        for t in tabs:
            for h in (range(min(12, len(t))) if raw else [None]):
                if h is None: t2 = t.copy()
                else: t2 = t.iloc[h + 1:].copy(); t2.columns = [str(c) for c in t.iloc[h].values]
                t2.columns = [str(c) for c in t2.columns]
                if len(set(t2.columns)) < len(t2.columns): continue
                try: u = xs.phase_frame(t2.reset_index(drop=True), name)
                except Exception: u = None
                if u is not None: break
            if u is not None: break
    if u is None: return [], [f"{os.path.basename(path)}: no column with d-spacings (d, d (A)) or 2θ was found. The table needs d or 2θ and, if possible, relative intensities"]
    u = u[~u["Phase"].astype(str).str.lower().isin(["", "nan", "none", "unassigned", "-"])]
    done, skip = store_phases(u, opt, f"added by you from {os.path.basename(path)}", replace=True)
    msgs += [f"stored: {c} = {nm} ({n} lines)" for c, nm, n in done] + ["not stored: " + s_ for s_ in skip]
    if not done and not skip: msgs.append(f"{os.path.basename(path)}: nothing new - the library already has these phases")
    return done, msgs

def lines_from_pattern(rows, code, pk, lam=1.5406):
    """Relative intensities for the Bragg positions of one phase, read from the measured pattern: only measured peaks that
    no other phase of the table shares are used (net height above the background)."""
    tt = rows["tt"].values; cd = rows["Code"].astype(str).values; out = {}
    for p in pk:
        if p.get("ka2") or not p.get("net", 0) > 0: continue
        near = np.abs(tt - p["pos"]) <= max(0.06, 0.6 * float(p.get("fwhm") or 0.1))
        if not near.any() or set(cd[near]) != {code}: continue
        j = np.flatnonzero(near)[np.argmin(np.abs(tt[near] - p["pos"]))]; out[j] = max(out.get(j, 0.0), float(p["net"]))
    if not out: return pd.DataFrame(columns=["Phase", "Code", "d", "I"])
    j = np.array(sorted(out)); return pd.DataFrame({"Phase": rows["Phase"].values[j], "Code": code, "d": xs.d_of(tt[j], lam), "I": [out[k] for k in j]})          # d with the wavelength of the pattern the positions belong to

def t95(df):
    """Two-sided 95 % Student t value."""
    T = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086]
    df = int(df); return float("nan") if df < 1 else T[df - 1] if df <= 20 else 1.96 + 2.5 / df

def parse_ranges(text):
    """'40-105, 400-500 CH' -> [(40, 105, ''), (400, 500, 'CH')]"""
    out = []
    for a, b, tag in re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:-|–|to)\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z]{0,4})", str(text or "")):
        a, b = float(a.replace(",", ".")), float(b.replace(",", "."))
        if b > a: out.append((a, b, tag.upper()))
    return out

KINDS = ["Automatic", "XRD", "Fit (observed + calculated)", "XRD peak list", "FTIR", "TGA", "Particle size", "Calorimetry", "DSC", "XY"]
try:                                                       # the gallery graph types G01-G24 and the calculations C01-C02 (gallery_graphs.py)
    import gallery_graphs as TG
    GALLERY_KINDS = [f"Gallery: {k} {v[0]}" for k, v in TG.TYPES.items()]
except Exception:                                          # noqa: BLE001
    TG, GALLERY_KINDS = None, []
KINDS = KINDS + GALLERY_KINDS
GALLERY_FIT = {}                                            # path -> (type id, why): a plain file that also fits a gallery type (offered under Suggestions)

def figtype_id(kind):
    m = re.match(r"^(?:Gallery|Thesis):\s*([GC]\d\d)\b", str(kind or ""))          # the second word: sessions saved before 5.51
    return m.group(1) if m else None

# ============================================================================= reading
def norm(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())

def _num(v):
    if isinstance(v, (int, float, np.integer, np.floating)) and not (isinstance(v, float) and math.isnan(v)): return True
    try: float(str(v).replace(",", ".")); return True
    except Exception: return False

def _excel_tables(path):
    """Every sheet of an Excel file as a raw table. An old-format .xls needs a reader package that is not always there:
    the app tries pandas' own reader, then 'calamine', then installs the small package 'xlrd' itself, then asks Excel."""
    def read(engine=None):
        import io, warnings, contextlib
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):      # the readers print remarks about slightly unusual files
            warnings.simplefilter("ignore")
            x = pd.ExcelFile(path) if engine is None else pd.ExcelFile(path, engine=engine)
            return [(n, pd.read_excel(x, sheet_name=n, header=None)) for n in x.sheet_names]
    try: return read()
    except ImportError as e: first = e                           # the reader package for this kind of Excel file is missing
    for eng in ("calamine", "xlrd"):
        try: return read(eng)
        except Exception: pass
    try:                                                         # get the reader (once); needs the internet for a few seconds
        import subprocess, importlib
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "xlrd", "python-calamine"], timeout=240, capture_output=True)
        importlib.invalidate_caches()
        for eng in ("xlrd", "calamine"):
            try: return read(eng)
            except Exception: pass
    except Exception: pass
    try: return _excel_com_tables(path)
    except Exception: pass
    raise ValueError("this is an old-format Excel file (.xls) and the package that reads it ('xlrd') is not installed and could not be installed "
                     "automatically. Either open the file in Excel and save it as .xlsx, or type in a command window:  py -3 -m pip install xlrd  and add the file again")

def _excel_com_tables(path):
    """Let Excel itself open the workbook and hand over the cells (Windows with Excel installed)."""
    import pythoncom, win32com.client
    pythoncom.CoInitialize(); xl = win32com.client.DispatchEx("Excel.Application"); xl.Visible = False; xl.DisplayAlerts = False
    try:
        wb = xl.Workbooks.Open(os.path.abspath(path), 0, True); out = []
        for ws in wb.Worksheets:
            v = ws.UsedRange.Value
            if v is None: continue
            if not isinstance(v, tuple): v = ((v,),)
            out.append((str(ws.Name), pd.DataFrame([list(r) for r in v])))
        wb.Close(False); return out
    finally:
        try: xl.Quit()
        except Exception: pass

COL_UNIT_RE = re.compile(r"(?i)\s*[\(\[]\s*(y|x|counts?|cts|cps|a\.?\s?u\.?|arb\.?\s?units?|intensity)\s*[\)\]]\s*$")

def split_samples(d):
    """A table with one angle column and several intensity columns holds one XRD pattern per column (for example a file made
    by PowDLL: X, S1 (Y), S2 (Y), PC (Y) ...). Returns one description per sample column, named after the column; a column
    that repeats an earlier one exactly is left out. Any other table is returned as it is."""
    if d.get("kind") != "XRD" or d.get("x") is None: return [d], []
    nums, n = d["nums"], d["n"]; x = d["x"]; bad = SKIP_Y + ("calc", "back", "bkg", "diff", "resid", "dspac", "fit", "model")
    cols = [c for c in nums if c != x and not any(k in n[c] for k in bad)]
    cols = [c for c in cols if pd.Series(nums[c]).notna().sum() >= 0.5 * len(pd.Series(nums[x]).dropna()) and float(np.nanmin(np.asarray(nums[c], float))) >= 0]
    if len(cols) < 2: return [d], []
    out, notes, kept, used = [], [], [], {}
    for c in cols:
        v = np.asarray(nums[c], float)
        twin = next((k for k in kept if len(np.asarray(nums[k], float)) == len(v) and np.allclose(np.asarray(nums[k], float), v, equal_nan=True)), None)
        if twin is not None: notes.append(f"column '{c}' repeats column '{twin}' exactly and is left out"); continue
        kept.append(c); nm = COL_UNIT_RE.sub("", re.sub(r"_\d+$", "", str(c))).strip() or str(c)
        used[nm] = used.get(nm, 0) + 1
        if used[nm] > 1: nm = f"{nm} ({used[nm]})"                 # the same sample measured again: a replicate
        e = dict(d, name=nm, ys=[c]); e["_from_table"] = d["name"]; out.append(e)
    return (out, notes) if len(out) >= 2 else ([d], [])

def read_tables(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in xs.READERS: return xs.READERS[ext](path)
    import instrument_files as inst_                          # binary instrument files the app reads itself
    if ext == ".spa":                                           # Thermo OMNIC spectrum (FTIR)
        tabs_, m_ = inst_.spa_tables(path); xs.META.setdefault(path, {})["spa"] = {k_: v_ for k_, v_ in m_.items() if k_ != "history"}; return tabs_
    if inst_.is_ngb(path):                                      # NETZSCH Proteus measurement: turned into the text export the app already knows
        tmp_, r_ = inst_.ngb_as_text_file(path)
        try:
            hx = _read_hash_export(tmp_)
            if hx is None: raise ValueError("the NETZSCH file was read, but its table could not be understood")
            xs.META[path] = xs.META.pop(tmp_, {}); xs.META[path]["ngb_notes"] = list(r_["notes"])
            return [(os.path.splitext(os.path.basename(path))[0], hx[0][1])]
        finally:
            try: os.remove(tmp_)
            except Exception: pass
    if ext in (".raw", ".rd", ".sd", ".dat_raw"): raise ValueError("this is a binary instrument file; export it as .xy, .csv or .xrdml from the instrument software")
    if ext in (".hpf2", ".hpf", ".hpf2_bak"): raise ValueError("this is a HighScore project file, a closed format that only HighScore can read. In HighScore open the project and export the pattern (File > Save As / Export > .xrdml, .xy or ASCII; the calculated profile: Reports or Export > profile as CSV), then add or convert that file")
    if ext in (".opju", ".opj", ".ogwu", ".ogw", ".ogg", ".oggu"): raise ValueError("this is an Origin file. Use File > Import from an Origin project, or export the workbook in Origin (File > Export > ASCII) and add that file")
    with open(path, "rb") as fb_: head_ = fb_.read(4096)
    if ext not in (".xlsx", ".xlsm", ".xls") and (head_[:2] == b"PK" or head_[:4] == b"%PDF" or head_[:3] == b"\xff\xd8\xff" or head_[:8] == b"\x89PNG\r\n\x1a\n" or head_.count(b"\x00") > 40):
        raise ValueError("this file holds no readable table of numbers (it is a binary file, a picture, a PDF or a program's own project file). Export the data from its program as CSV, text or Excel and add that file")
    if ext in (".xlsx", ".xlsm", ".xls"): return _excel_tables(path)
    hx = _read_hash_export(path)
    if hx is not None: return hx
    text = _text(path); sample = text[:20000]; stem = os.path.splitext(os.path.basename(path))[0]
    dc = _read_decimal_commas(text)
    if dc is not None:
        xs.META.setdefault(path, {})["decimal_commas"] = dc[1]
        return [(stem, dc[0])]
    try: sep = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except Exception: sep = r"\s+"
    dec = "," if sep == ";" and re.search(r"\d,\d", sample) else "."
    try: df = pd.read_csv(io.StringIO(text), sep=sep, header=None, engine="python", decimal=dec)
    except Exception:                                   # ragged lines (instrument headers): keep the lines that fit the data
        df = pd.read_csv(io.StringIO(text), sep=sep, header=None, engine="python", decimal=dec, on_bad_lines="skip", skiprows=_header_lines(path, sep))
    return [(stem, df)]

def _text(path):
    """The text of a file whatever its encoding: UTF-8 (with or without mark), UTF-16, or the Windows western set that
    HighScore and many instrument programs write (the degree sign and the angstrom sign are single bytes there)."""
    with open(path, "rb") as f: b = f.read()
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try: return b.decode("utf-16")
        except Exception: pass
    for enc in ("utf-8-sig", "cp1252"):
        try: return b.decode(enc)
        except Exception: pass
    return b.decode("latin-1")

_DC_INT = re.compile(r"^\s*[-+]?\d+\s*$"); _DC_FRAC = re.compile(r"^\d+([eE][-+]?\d+)?(\(\d+\))?\s*$")
_DC_DEC_HINT = re.compile(r"(?i)[\[\(]|pos|fwhm|area|spacing|size|strain|obs|calc|back|shape|height|width|breadth|intens")
_DC_INT_HINT = re.compile(r"(?i)^\s*(no\.?|nr\.?|#|h|k|l|m|mult\w*|index|id)\s*$")

def _read_decimal_commas(text):
    """A table written with the comma BOTH between the columns and as the decimal sign, without quotes. HighScore writes
    its CSV files like this on a computer with Swedish (or German, French ...) number format:
        No.,Pos. [°2Th.],Iobs [cts]      header: 3 columns
        1,6,0043,307,9961                a row:   5 pieces, meaning 1 | 6.0043 | 307.9961
    The pieces of every row are put together again. Which columns are decimal numbers is decided for the whole file, not row
    by row: a piece that begins with a zero ('0043') can only be the decimals of the piece before it, a negative piece or a
    piece of text can only begin a column, and a column keeps its number of decimals. Returns (table with the header as first
    row, note) or None when the file is not of this kind."""
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 4: return None
    h = next((i for i, l in enumerate(lines[:60]) if l.count(",") >= 1 and sum(not _num(t) and bool(t.strip()) for t in l.split(",")) >= max(2, 0.6 * len(l.split(",")))), None)
    if h is None or ";" in lines[h] or "\t" in lines[h] or '"' in lines[h]: return None
    hdr = [t.strip() for t in lines[h].split(",")]; N = len(hdr); body = [l.split(",") for l in lines[h + 1:]]
    if N < 2 or len(body) < 3 or any('"' in l for l in lines[h + 1:h + 30]): return None
    if sum(N < len(r) <= 2 * N for r in body) < 0.9 * len(body): return None
    def words(t): return bool(re.search(r"[A-Za-z]", t)) and not _DC_FRAC.match(t.strip())
    for k, r in enumerate(body):                                   # a name with a comma in it ('Quartz, syn') is one piece
        if any(t[:1] == " " and words(t) for t in r[1:]):
            m_ = [r[0]]
            for t in r[1:]:
                if t[:1] == " " and words(t) and words(m_[-1]): m_[-1] = m_[-1] + "," + t
                else: m_.append(t)
            body[k] = m_
    proof = sum(any(_DC_INT.match(a) and re.match(r"^0\d", b_) and _DC_FRAC.match(b_) for a, b_ in zip(r, r[1:])) for r in body)
    if proof < max(2, 0.02 * len(body)): return None               # no piece like '0043' after a whole number anywhere: not this kind of file
    def pair(a, b_):
        a = a.strip(); d = a.lstrip("+-")
        return bool(_DC_INT.match(a) and _DC_FRAC.match(b_) and not (len(d) > 1 and d[0] == "0"))
    def vectors(r, cap=40000):
        out = []
        def go(i, j, acc):
            lt, lc = len(r) - i, N - j
            if lt < lc or lt > 2 * lc or len(out) >= cap: return
            if j == N: out.append(tuple(acc)); return
            if i + 1 < len(r) and pair(r[i], r[i + 1]): go(i + 2, j + 1, acc + [2])
            go(i + 1, j + 1, acc + [1])
        go(0, 0, []); return out
    def fits(v, r):
        i = 0
        for a in v:
            if a == 2:
                if not pair(r[i], r[i + 1]): return False
            i += a
        return True
    groups = {}
    for k, r in enumerate(body):
        if N <= len(r) <= 2 * N: groups.setdefault(len(r), []).append(k)
    chosen = {}; cands = {}
    for n_, idx in groups.items():
        if n_ == N: chosen[n_] = (1,) * N; continue
        start = min(idx[:200], key=lambda k: sum(pair(a, b_) for a, b_ in zip(body[k], body[k][1:])))      # the row that leaves the fewest ways open
        cv = {v: 0 for v in vectors(body[start])}
        if not cv: continue
        for k in idx:
            alive = [v for v in cv if cv[v] >= 0]
            for v in alive:
                if fits(v, body[k]): cv[v] += 1
            best = max(cv.values())
            if len(alive) > 50:                                    # drop the ones that are clearly behind
                for v in alive:
                    if cv[v] < best - 5: cv[v] = -1
        best = max(cv.values()); cands[n_] = [v for v in cv if cv[v] == best]
        if best < 0.9 * len(idx): return None
    if not cands and not chosen: return None
    def widths(v, idx):                                            # how even the number of decimals is in the columns taken as decimal numbers
        bad = 0; wide = 0
        for j, a in enumerate(v):
            if a != 2: continue
            pos = sum(v[:j]); ws = {}
            for k in idx[:400]:
                w = len(re.sub(r"\(.*", "", body[k][pos + 1]).strip()); ws[w] = ws.get(w, 0) + 1
            bad += len(idx[:400]) - max(ws.values()); wide += max(ws, key=ws.get)
        return bad, -wide                                          # decimals are written with a fixed number of digits, and usually with several
    def odd(v, idx):                                               # whole numbers written with leading zeros ('00290') are not whole numbers
        bad = 0
        for k in idx[:400]:
            i = 0
            for a in v:
                bad += a == 1 and bool(re.match(r"^0\d+\s*$", body[k][i])); i += a
        return bad
    def hints(v): return sum((a == 1 and bool(_DC_DEC_HINT.search(hdr[j])) and not _DC_INT_HINT.match(hdr[j])) or (a == 2 and bool(_DC_INT_HINT.match(hdr[j]))) for j, a in enumerate(v))
    for n_ in sorted(cands, key=lambda n_: len(cands[n_])):
        others = list(chosen.values())
        chosen[n_] = min(cands[n_], key=lambda v: (sum(sum(a != b_ for a, b_ in zip(v, o)) for o in others), odd(v, groups[n_]), hints(v), widths(v, groups[n_])))   # like the lines already settled; then the column names; then even decimals
    out = [hdr]; lost = 0
    for r in body:
        v = chosen.get(len(r))
        if v is None or not fits(v, r): lost += 1; continue
        row = []; i = 0
        for a in v:
            row.append(r[i].strip() if a == 1 else r[i].strip() + "." + r[i + 1].strip()); i += a
        out.append(row)
    if len(out) - 1 < 0.9 * len(body): return None
    dec = sorted({hdr[j] for v in chosen.values() for j, a in enumerate(v) if a == 2}, key=hdr.index)
    note = (f"this file uses the comma both between the columns and as the decimal sign (HighScore on a computer with Swedish number format); the numbers were put together again "
            f"({len(dec)} of {N} columns are decimal numbers: {', '.join(dec)})" + (f"; {lost} line(s) that did not fit were left out" if lost else ""))
    return pd.DataFrame(out), note

def _read_hash_export(path):
    """Instrument text exports with a '#KEY: value' header block and a column line starting with '##' (NETZSCH thermal analysis).
    Returns [(name, table)] with the header row first, and stores the header facts in xs.META[path]['hash']."""
    try: lines = _text(path).splitlines()
    except Exception: return None
    if len(lines) < 12 or sum(l.startswith("#") for l in lines[:40]) < 8: return None
    h = next((i for i, l in enumerate(lines[:200]) if l.startswith("##")), None)
    if h is None: return None
    sep = ";" if lines[h].count(";") > lines[h].count(",") else ","
    meta = {}
    for l in lines[:h]:
        if l.startswith("#") and ":" in l:
            k, _, v = l[1:].partition(":"); v = v.strip().strip(sep + " ").split(sep)[0].strip()
            if v: meta[k.strip().upper()] = v
    rows = []; rblk = []; blocks = 1; unread = 0; stopped = False
    for l in lines[h + 1:]:
        f = l.split(sep)
        if stopped: unread += bool(f and _num(f[0])); continue
        if not f or not _num(f[0]):
            if rows and l.startswith("##"):               # a further data block
                if l.strip() == lines[h].strip(): blocks += 1
                else: stopped = True                       # other columns than the first block: not read, but reported
            continue
        rows.append(f); rblk.append(blocks)
    if len(rows) < 3: return None
    hdr = [x.strip() for x in lines[h].lstrip("#").split(sep)]
    keep, names = [], []
    for j, c in enumerate(hdr):
        if not c: continue
        nm, _, un = c.partition("/"); nm = nm.strip(); un = un.strip()
        if un.startswith("(") and un.endswith(")"): un = un[1:-1]
        if re.match(r"(?i)temp", nm):
            nm = "Temperature"; un = un if un in ("K", "\u00b0C", "C") else "\u00b0C"
        names.append(f"{nm} ({un})" if un else nm); keep.append(j)
    if len(keep) < 2: return None
    body = [[(r[j].strip() if j < len(r) else "") for j in keep] for r in rows]
    if blocks > 1: names.append("Block"); body = [b_ + [str(k_)] for b_, k_ in zip(body, rblk)]      # several data blocks in one export: all are read, each row says which block it is from
    mr = re.search(r"([\d.]+)\s*\(K/min\)", meta.get("RANGE", "") + " " + meta.get("SEG. 1", ""))
    info = dict(sample=meta.get("SAMPLE") or meta.get("IDENTITY"), mass_mg=_fnum(meta.get("SAMPLE MASS /MG")) if "SAMPLE MASS /MG" in meta else None, instrument=meta.get("INSTRUMENT"),
                rate=float(mr.group(1)) if mr else None, kind=meta.get("MTYPE"), date=meta.get("DATE/TIME"))
    # the whole header is kept (atmosphere, crucible, calibration and correction files, segments), not only the facts used for drawing
    info.update(header=dict(meta), exo=meta.get("EXO"), segments=[f"{k}: {v}" for k, v in meta.items() if re.match(r"SEG\. ?\d+", k)], blocks=blocks, unread_rows=unread,
                crucible=meta.get("TYPE OF CRUCIBLE"), reference=meta.get("REFERENCE"), correction=meta.get("CORR. FILE"), tempcal=meta.get("TEMPCAL"), sensitivity=meta.get("SENSITIVITY"))
    xs.META.setdefault(path, {})["hash"] = info
    return [(os.path.splitext(os.path.basename(path))[0], pd.DataFrame([names] + body))]

def _header_lines(path, sep):
    """Number of leading lines before the block of lines that all have the same number of fields."""
    lines = _text(path).splitlines()[:5000]
    cnt = [len(re.split(sep, l.strip())) if l.strip() else 0 for l in lines]
    if not cnt: return 0
    common = max(set(cnt), key=cnt.count)
    for i in range(len(cnt)):
        if cnt[i] == common and all(c == common for c in cnt[i:i + 5]): return max(0, i - 1)
    return 0

def parse_table(raw):
    """Find header row, units row and data block -> (DataFrame, {column: unit}) or None."""
    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if raw.shape[0] < 2 or raw.shape[1] < 2: return None
    isnum = raw.apply(lambda col: col.map(lambda v: (not pd.isna(v)) and _num(v))); filled = raw.notna()
    mask = [tuple(r) for r in isnum.to_numpy(dtype=bool).tolist()]; nnum = isnum.sum(axis=1).to_numpy(); nfill = filled.sum(axis=1).to_numpy()      # rows as plain tuples: the same test, without asking pandas for every row
    def same(i): return nnum[i] >= 1 and mask[i] == mask[i + 1] and (i + 2 >= len(raw) or mask[i] == mask[i + 2] or nnum[i] >= 0.6 * nfill[i])
    start = next((i for i in range(len(raw) - 1) if same(i)), None)
    if start is None: return None
    hdr, units = None, {}
    strcount = [(int((filled.iloc[i] & ~isnum.iloc[i]).sum()), i) for i in range(start)]
    if strcount and max(strcount)[0] > 0:
        best = max(c for c, _ in strcount); hdr = min(i for c, i in strcount if c == best)
        if hdr + 1 < start: units = {j: str(raw.iloc[hdr + 1, j]).strip() for j in range(raw.shape[1]) if filled.iloc[hdr + 1, j] and not isnum.iloc[hdr + 1, j]}
    names = [str(raw.iloc[hdr, j]).strip() if hdr is not None and filled.iloc[hdr, j] else f"Col{j + 1}" for j in range(raw.shape[1])]
    seen = {}
    for j, n in enumerate(names):
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1: names[j] = f"{n}_{seen[n]}"
    df = raw.iloc[start:].reset_index(drop=True); df.columns = names
    return df, {names[j]: u for j, u in units.items()}

_ESD_RE = re.compile(r"(?<=\d)\s*\(\d+\)\s*$")

def numeric_cols(df):
    out = {}
    for c in df.columns:
        v = pd.to_numeric(df[c].map(lambda t: _ESD_RE.sub("", str(t).replace(",", ".")) if isinstance(t, str) else t), errors="coerce")   # '24(64)' = 24 with its uncertainty in brackets
        if v.notna().sum() >= max(2, 0.8 * df[c].notna().sum()): out[c] = v
    return out

def unit_of(col, units):
    if col in units: return units[col]
    m = re.search(r"[\(\[]([^\)\]]*)[\)\]]\s*$", str(col)); return m.group(1).strip() if m else ""

def titled(col, units):
    u = units.get(col); return f"{col} ({u})" if u and u not in str(col) else str(col)

# ============================================================================= numerics
def savgol(y, window, poly=2, deriv=0):
    """Savitzky-Golay smoothing (uniform spacing assumed), numpy only. Edges are reflected."""
    y = np.asarray(y, float); n = len(y); window = int(window) | 1; window = max(poly + 1 + (poly % 2), min(window, (n - 1) | 1 if n > 3 else 3))
    if window < 3 or n < window: return y.copy()
    h = window // 2; A = np.vander(np.arange(-h, h + 1), poly + 1, increasing=True)
    coef = np.linalg.pinv(A)[deriv] * math.factorial(deriv)
    ypad = np.concatenate([2 * y[0] - y[h:0:-1], y, 2 * y[-1] - y[-2:-h - 2:-1]])
    return np.convolve(ypad, coef[::-1], mode="valid")

def noise_level(y):
    """Robust noise estimate from the difference between the data and a light smooth."""
    r = np.asarray(y, float) - savgol(y, 7, 2); return 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-300

def find_peaks(x, y, max_n=15, k_noise=6.0, min_rel=0.02, smooth=None, min_sep=None):
    """
    Peaks (maxima) of y(x). Each peak must rise above its surroundings (prominence) by at least
    k_noise x noise and min_rel x data range. The position is refined by a parabola through the
    top of the lightly smoothed data, so it is not limited to the measurement step.
    Returns list of dicts sorted by x: pos, height (raw maximum near the peak), prominence, index.
    """
    x = np.asarray(x, float); y = np.asarray(y, float); n = len(y)
    if n < 7: return []
    w = smooth or (5 if n < 400 else 7 if n < 3000 else 9); ys = savgol(y, w, 2)
    noise = noise_level(y); rng = float(np.nanmax(ys) - np.nanmin(ys)) or 1.0
    idx = np.where((ys[1:-1] > ys[:-2]) & (ys[1:-1] >= ys[2:]))[0] + 1
    out = []
    for i in idx:
        l = i
        while l > 0 and ys[l - 1] <= ys[i]: l -= 1
        r = i
        while r < n - 1 and ys[r + 1] <= ys[i]: r += 1
        lmin = ys[l:i + 1].min(); rmin = ys[i:r + 1].min()
        prom = ys[i] - (max(lmin, rmin) if (l > 0 and r < n - 1) else (lmin if r == n - 1 and l > 0 else rmin if l == 0 and r < n - 1 else min(lmin, rmin)))
        if prom < k_noise * noise or prom < min_rel * rng: continue
        a, b, c = ys[i - 1], ys[i], ys[i + 1]; den = a - 2 * b + c
        d = 0.5 * (a - c) / den if den != 0 else 0.0; d = float(np.clip(d, -0.5, 0.5))
        pos = x[i] + d * (x[i + 1] - x[i] if d >= 0 else x[i] - x[i - 1])
        out.append(dict(pos=float(pos), height=float(y[max(0, i - 2):i + 3].max()), prominence=float(prom), index=int(i)))
    out.sort(key=lambda p: -p["prominence"])
    if min_sep:
        kept = []
        for p in out:
            if all(abs(p["pos"] - q["pos"]) >= min_sep for q in kept): kept.append(p)
        out = kept
    return sorted(out[:max_n], key=lambda p: p["pos"])

def snap_labels(x, y, labels, tol):
    """Move each given label (pos, text, y) onto the real peak top near it; report labels with no peak there."""
    x = np.asarray(x, float); y = np.asarray(y, float); ys = savgol(y, 7, 2); noise = noise_level(y); out, warn = [], []
    order = np.argsort(x); xs, yss, yr = x[order], ys[order], y[order]
    for pos, text, _ in labels:
        m = np.where(np.abs(xs - pos) <= tol)[0]
        if len(m) == 0: warn.append(f"label '{text}' at {pos:g} is outside the data"); continue
        i = m[np.argmax(yss[m])]; lo, hi = max(0, i - 40), min(len(xs), i + 41)
        prom = yss[i] - max(yss[lo:i + 1].min(), yss[i:hi].min())
        if 0 < i < len(xs) - 1:
            a, b, c = yss[i - 1], yss[i], yss[i + 1]; den = a - 2 * b + c; d = float(np.clip(0.5 * (a - c) / den, -0.5, 0.5)) if den != 0 else 0.0
            p = xs[i] + d * (xs[i + 1] - xs[i] if d >= 0 else xs[i] - xs[i - 1])
        else: p = xs[i]
        if prom < 3 * noise: warn.append(f"label '{text}' at {pos:.2f}: no clear peak there (left at the given position)"); p = pos
        out.append((float(p), str(text), float(yr[max(0, i - 2):i + 3].max())))
    return out, warn

NUDGE = 0.02           # a label may be moved this far (share of the x range) to let the leader line of a neighbour pass; it stays over its own peak

class _Beside(str):
    """The text of a label that was moved a little to the side to make way; it is still over its peak and gets no leader line."""
    beside = True

def place_labels(labels, x, y, x0, x1, y0, y1, vertical, blocked=(), hscale=1.0, wscale=1.0, side=3):
    """
    Put each label (pos, text, peak_y) just above the curve without overlapping the curve or other labels.
    When the space above a peak is taken, the label may move a little to the side (a thin leader line then joins
    it to its peak); otherwise it moves up. Returns [(pos, peak_y, text, label_x, label_y_bottom)] and the highest y used.
    """
    x = np.asarray(x, float); y = np.asarray(y, float); xs_ = abs(x1 - x0) or 1.0; ysp = (y1 - y0) or 1.0; pad = 0.02 * ysp
    lo_x, hi_x = min(x0, x1), max(x0, x1); placed, out, top = list(blocked), [], y1
    def clear(lx, ly, w, h): return not any(abs(lx - qx) < (w + qw) / 2 + 0.002 * xs_ and ly < qy + qh and qy < ly + h for qx, qy, qw, qh in placed)
    def floor(lx, w):
        m = np.abs(x - lx) <= w / 2 + 0.003 * xs_; return float(np.nanmax(y[m])) if m.any() else None
    nb = len(placed)                                     # the boxes given from outside (inset, legend) come first; labels follow, in step with `out`
    def make_way(pos, py, ly):
        """The new label sits straight above its peak, higher up, and its leader line would run through a label placed
        earlier (two peaks close together: the labels are stacked). The lower label is moved a little to the side, so that
        the line passes beside it. It stays over its own peak, so it needs no leader line of its own."""
        for qi in range(nb, len(placed)):
            qx, qy, qw, qh = placed[qi]; o = out[qi - nb]
            if not (abs(pos - qx) < qw / 2 + 0.003 * xs_ and py < qy + qh and qy < ly) or abs(o[3] - o[0]) > 1e-9: continue
            need = qw / 2 + 0.002 * xs_ - abs(pos - qx); sgn = -1.0 if qx <= pos else 1.0
            if need <= 0 or need > NUDGE * xs_ or need > qw / 2: continue          # its own peak stays under the label
            nx = qx + sgn * need
            if nx - qw / 2 < lo_x or nx + qw / 2 > hi_x: continue
            fl = floor(nx, qw)
            if fl is not None and fl + 0.5 * pad > qy: continue
            if any(k != qi and abs(nx - bx) < (qw + bw) / 2 + 0.002 * xs_ and qy < by + bh and by < qy + qh for k, (bx, by, bw, bh) in enumerate(placed)): continue
            placed[qi] = (nx, qy, qw, qh); out[qi - nb] = (o[0], o[1], _Beside(o[2]), nx, o[4])
    for pos, text, py in sorted(labels, key=lambda t: -t[2]):
        n = max(len(str(text)), 1)
        w = (0.016 * xs_ if vertical else (0.0105 * n + 0.008) * xs_) * wscale
        h = ((0.019 * n + 0.012) * ysp if vertical else 0.055 * ysp) * hscale
        best = None
        for k, dx in enumerate([0, -1, 1, -2, 2, -3, 3][:2 * side + 1] if len(labels) <= 24 else [0, -1, 1]):      # crowded: stay over the peak, so leaders do not cross
            lx = pos + dx * 0.9 * w
            if lx - w / 2 < lo_x or lx + w / 2 > hi_x: continue
            fl = floor(lx, w); fl = py if fl is None else fl; ly = max(fl, py) + pad * (1 if dx == 0 else 2.0)     # never below its own peak top
            for _ in range(300):
                if clear(lx, ly, w, h): break
                ly += 0.015 * ysp
            cost = ly + 0.05 * ysp * abs(dx)                    # prefer straight above; move sideways only if that saves height
            if best is None or cost < best[0]: best = (cost, lx, ly)
        _, lx, ly = best if best else (0, pos, py + pad)
        if abs(lx - pos) < 1e-9 and ly - py >= 0.03 * ysp: make_way(pos, py, ly)
        placed.append((lx, ly, w, h)); out.append((pos, py, str(text), lx, ly)); top = max(top, ly + h)
    return sorted(out), top

# ============================================================================= spec helpers
def curve(label, x, y, colour, kind="line", width=None):
    return dict(label=label, x=np.asarray(x, float), y=np.asarray(y, float), colour=colour, kind=kind, width=width)

def panel(yname, curves, weight=1.0, labels=(), vlines=(), ylim=None, vertical=True, legend=True):
    return dict(yname=yname, curves=curves, weight=weight, labels=list(labels), vlines=list(vlines), ylim=ylim, vertical=vertical, legend=legend)

def visible(p):
    """Curves that get a legend entry (labels starting with _ are helpers, e.g. individual points)."""
    return [(j, c) for j, c in enumerate(p["curves"]) if not str(c["label"]).startswith("_")]

def _envelope(p):
    """Upper envelope of the curves of a panel that share the x values of the first one (labels sit above it)."""
    c0 = p["curves"][0]; ys = [c["y"] for c in p["curves"] if len(c["x"]) == len(c0["x"]) and not str(c["label"]).startswith("_") and np.array_equal(c["x"], c0["x"])]
    return c0["x"], (np.nanmax(np.vstack(ys), axis=0) if len(ys) > 1 else c0["y"])

def _lab_box(text, vertical, xs_, ysp, hscale, wscale):
    n = max(len(str(text)), 1)
    return (0.016 * xs_ if vertical else (0.0105 * n + 0.008) * xs_) * wscale, ((0.019 * n + 0.012) * ysp if vertical else 0.055 * ysp) * hscale

def _fit_inset(p, ins, lo, hi, y0, y1, ytop, rev=False):
    """Make room for the zoomed inset in the top right corner (the curve and the labels below it stay clear of it) and
    prepare what the inset shows: the same curves inside its range, on their own y scale, with the labels of that range."""
    a, b = ins["xlim"]; fx, fy, fw, fh = ins.get("rect_in") or (_BUILD_FMT or {}).get("inset_rect") or INSET_RECT; ex, ey = _envelope(p)
    if ins.get("auto_side"):                                          # a panel of several: the zoom goes to the emptier top corner
        u = (hi - ex) / (hi - lo) if rev else (ex - lo) / (hi - lo)          # 0 at the left edge of the panel, 1 at the right
        lft = float(np.nanmax(ey[u <= fw + 0.05])) if (u <= fw + 0.05).any() else y0; rgt = float(np.nanmax(ey[u >= 1 - fw - 0.05])) if (u >= 1 - fw - 0.05).any() else y0
        fx = 0.015 if lft < rgt else 1 - fw - 0.015
        if fx < 0.5 and p.get("corner"): p["corner_r"] = [(t_, True) for t_ in p.pop("corner")]
        if fx > 0.5 and p.get("corner_r"): p["corner"] = [t_[0] for t_ in p.pop("corner_r")]      # the sample name moves to the free corner
    xa = (hi - (fx - 0.035) * (hi - lo)) if rev else lo + (fx - 0.035) * (hi - lo); xb_ = (hi - (fx + fw + 0.035) * (hi - lo)) if rev else lo + (fx + fw + 0.035) * (hi - lo)
    inside_ = lambda v: ((v <= xa) & (v >= xb_)) if rev else ((v >= xa) & (v <= xb_))
    m = inside_(ex); U = float(np.nanmax(ey[m])) if m.any() else y0
    sh_, sw_ = p.get("_sc", (p.get("lab_scale", 1.0), 1.0)); pt = p.get("lab_pt", 15); hs = sh_ * pt / 15.0; ws = sw_ * pt / 15.0
    for pos, py, txt, lx, ly in p.get("placed", []):
        w, h = _lab_box(txt, p["vertical"], hi - lo, y1 - y0, hs, ws)
        if inside_(np.array([lx - w / 2])).any() or inside_(np.array([lx + w / 2])).any() or inside_(np.array([lx])).any(): U = max(U, ly + h)
    if fy - ins.get("tick_room", 0.085) > 0.25: ytop = max(ytop, y0 + (U - y0) / (fy - ins.get("tick_room", 0.085)))     # room for the tick labels under the inset (more in a short panel); an inset you put low is left where you put it
    cv = []
    only = ins.get("only")                                            # e.g. observed and calculated only (not the difference or the tick rows of a panel)
    for c in p["curves"]:
        mk = (c["x"] >= a) & (c["x"] <= b)
        if not str(c["label"]).startswith("_") and mk.sum() > 3 and (not only or c["label"] in only): cv.append(dict(c, x=c["x"][mk], y=c["y"][mk]))
    if not cv: ins.clear(); return ytop
    ys = np.concatenate([c["y"] for c in cv]); ys = ys[np.isfinite(ys)]; i0, i1 = float(ys.min()), float(ys.max()); s = (i1 - i0) or 1.0; i0 -= 0.04 * s; i1 += 0.05 * s
    ex2 = cv[0]["x"]; ey2 = np.nanmax(np.vstack([np.interp(ex2, c["x"], c["y"]) for c in cv]), axis=0)
    labs = [l_ for l_ in (ins.get("labels") or p.get("labels") or []) if a + 0.04 * (b - a) < l_[0] < b - 0.04 * (b - a)]; ipt = max(9, int(round(pt)))                # the labels of the zoomed part are as large as those of the main graph
    placed, top = place_labels(labs, ex2, ey2, a, b, i0, i1, p["vertical"], (), sh_ * (ipt / 15.0) / fh, sw_ * (ipt / 15.0) / fw, side=1) if labs else ([], i1)      # a label stays over its own peak (short pointers)
    if ins.get("max_lift"): placed = [q_ for q_ in placed if q_[4] - q_[1] <= ins["max_lift"] * (i1 - i0) and abs(q_[3] - q_[0]) <= ins.get("max_side", 0.09) * (b - a)]; top = max([i1] + [q_[4] + _lab_box(q_[2], p["vertical"], b - a, i1 - i0, sh_ * (ipt / 15.0) / fh, sw_ * (ipt / 15.0) / fw)[1] for q_ in placed])
    ins["xdraw"] = (b, a) if rev else (a, b)
    ins.update(curves=cv, placed=placed, ylim=(i0, max(top + 0.02 * (i1 - i0), i1)), lab_pt=ipt, rect=(fx, fy, fw, fh), vertical=p["vertical"])
    return ytop

def finish(spec):
    """Axis limits, label positions and leader lines for every panel."""
    xs = np.concatenate([c["x"] for p in spec["panels"] for c in p["curves"]]); xs = xs[np.isfinite(xs)]
    lo, hi = float(xs.min()), float(xs.max())
    if spec.get("xlog"): lo = float(xs[xs > 0].min())
    if not spec.get("xlog") and any(c["kind"] != "line" for p in spec["panels"] for c in p["curves"]):      # symbols must not sit on the frame
        pad = 0.04 * ((hi - lo) or 1.0); lo, hi = lo - pad, hi + pad
    if spec.get("xlog") and any(c["kind"] != "line" for p in spec["panels"] for c in p["curves"]): lo, hi = lo / 1.12, hi * 1.12      # symbols must not sit on the frame
    spec["xlim"] = (hi, lo) if spec.get("xrev") else (lo, hi)
    cw_, ch_ = spec.get("cell", (1.0, 1.0)); fsc_ = spec.get("font_scale", 1.0)      # a graph that fills only part of a page: letters are relatively larger
    for p in spec["panels"]:
        p["_sc"] = (p.get("lab_scale", 1.0) * fsc_ / ch_, fsc_ / cw_)
        ys = np.concatenate([c["y"] for c in p["curves"]] + [s[1] for s in p.get("segs", [])] + [b[k] for b in p.get("bands", []) for k in (1, 2)]); ys = ys[np.isfinite(ys)]
        y0, y1 = p["ylim"] if p["ylim"] else (float(ys.min()), float(ys.max()))
        if not p["ylim"]:
            s = (y1 - y0) or 1.0; y0 = y0 - 0.04 * s if y0 < 0 or y0 > 0.2 * s else min(y0, 0) - 0.02 * s; y1 = y1 + 0.05 * s
        box = p.get("legendbox"); blocked = []; ins = p.get("inset") if not spec.get("xlog") else None
        lloc_ = str((_BUILD_FMT or {}).get("legend_loc") or "")
        ir_ = (_BUILD_FMT or {}).get("inset_rect") if ins else None
        if box and ir_: box["force"] = "right" if ir_[0] < 0.4 else "left"          # your zoom where you drew it: the legend box takes the other side
        elif box and lloc_: box["force"] = "left" if "left" in lloc_ else "right"     # where you put the legend in your sketch
        if ins and box and not box.get("force"): box["force"] = "left"           # the inset takes the top right corner
        if box:                                   # keep a top corner free for the legend box (HighScore style): the side that needs less room
            tw = sum(q["weight"] for q in spec["panels"]); dy = min(0.11, 0.052 * tw / p["weight"])
            nl = 1.15 + len(box.get("keys", [])) + len(box.get("entries", [])) + len(box.get("lines", [])); dy = min(dy, 0.62 / nl); hb = 0.03 + dy * nl
            room = 0.11 if p["labels"] else 0.03          # space for a label between a peak and the bottom of the box
            wfrac = min(0.55, 0.06 + 0.0092 * max([len(str(box.get("title", ""))) * 1.15] + [len(t_) + 3 for _, t_ in box.get("entries", [])] + [len(t_) for t_ in box.get("lines", [])]))
            ex, ey = _envelope(p); best = None
            for side in ([box["force"]] if box.get("force") else ("left", "right")):
                a_ = lo + (0 if side == "left" else 1 - wfrac) * (hi - lo); b_ = a_ + wfrac * (hi - lo)
                if spec.get("xrev"): a_, b_ = lo + hi - b_, lo + hi - a_
                m = (ex >= a_) & (ex <= b_); peak = float(np.nanmax(ey[m])) if m.any() else y0
                need = max(y1, (peak + room * (y1 - y0) - hb * y0) / (1 - hb))
                if best is None or need < best[0] - 1e-9: best = (need, side, (a_ + b_) / 2)
            y1, side, bx = best
            box.update(wfrac=wfrac, hfrac=hb, dy=dy, side=side)
            blocked = [(bx, y1 - hb * (y1 - y0), wfrac * (hi - lo), hb * (y1 - y0) * 1.5)]
        top = y1
        if p["labels"]:
            nl_ = len(p["labels"]); pt = p.setdefault("lab_pt", 15 if nl_ <= 24 else 13 if nl_ <= 45 else 12)      # many labels: smaller letters
            if not p.get("_lm"): pt = p["lab_pt"] = int(round(pt * spec.get("label_mult", 1.0))); p["_lm"] = True      # your choice of label size
            ex, ey = _envelope(p); p["placed"], top = place_labels(p["labels"], ex, ey, lo, hi, y0, y1, p["vertical"], blocked, p["_sc"][0] * pt / 15.0, p["_sc"][1] * pt / 15.0)
            if p.get("max_lift"):                 # names on the peaks: a small peak beside a tall one would get a label far above it on a long pointer; it is left to the inset
                keep_ = [q_ for q_ in p["placed"] if q_[4] - q_[1] <= p["max_lift"] * (y1 - y0) and abs(q_[3] - q_[0]) <= p.get("max_side", 1.0) * (hi - lo)]
                if len(keep_) < len(p["placed"]):
                    p["placed"] = keep_; top = max([y1] + [q_[4] + _lab_box(q_[2], p["vertical"], hi - lo, y1 - y0, p["_sc"][0] * pt / 15.0, p["_sc"][1] * pt / 15.0)[1] for q_ in keep_])
            top = top + 0.02 * (y1 - y0)
        elif "placed" not in p: p["placed"] = []
        elif p["placed"] and not p.get("_lm") and spec.get("label_mult", 1.0) != 1.0: p["lab_pt"] = int(round(p.get("lab_pt", 15) * spec["label_mult"])); p["_lm"] = True
        elif p["placed"]: top = max([top] + [ly + 0.06 * (y1 - y0) for _, _, _, _, ly in p["placed"]])
        if p["legend"] and len(visible(p)) > 1 and top <= y1 + 1e-12: top = y1 + (0.03 + 0.07 * min(4, len(visible(p)))) * (y1 - y0)
        yt = max(top, y1)
        if p.get("corner") and spec.get("cell") and not (spec.get("xrev") or spec.get("xlog")):      # sample name / Rwp in the top left corner: curve and labels stay below it
            sh_, sw_ = p["_sc"]; wfr = min(0.7, (0.0118 * max(len(str(t_)) for t_ in p["corner"]) + 0.035) * sw_); hfr = 0.07 + (0.055 / ch_) * len(p["corner"])
            xr_ = lo + wfr * (hi - lo); ex, ey = _envelope(p); m_ = ex <= xr_; U = float(np.nanmax(ey[m_])) if m_.any() else y0; pt_ = p.get("lab_pt", 15)
            for q_ in p.get("placed", []):
                w_, h_ = _lab_box(q_[2], p["vertical"], hi - lo, y1 - y0, sh_ * pt_ / 15.0, sw_ * pt_ / 15.0)
                if q_[3] - w_ / 2 <= xr_: U = max(U, q_[4] + h_)
            yt = max(yt, y0 + (U - y0) / (1 - hfr))
        p["ylim"] = (y0, _fit_inset(p, ins, lo, hi, y0, y1, yt, bool(spec.get("xrev"))) if ins else yt)
        y2 = p.get("y2")
        if y2:                                                         # second y axis (for example DTG next to TG): its labels are placed in its own coordinates
            a0, a1 = y2["ylim"]; c2 = y2["curves"][0]; pt2 = y2.setdefault("lab_pt", 12)
            if not y2.get("_lm"): pt2 = y2["lab_pt"] = int(round(pt2 * spec.get("label_mult", 1.0))); y2["_lm"] = True
            y2["placed"], _ = place_labels(y2.get("labels") or [], c2["x"], np.nan_to_num(c2["y"], nan=a0), lo, hi, a0, a1, False, (), 1.3 * pt2 / 15.0, pt2 / 15.0)
    return spec

# ============================================================================= detection
X_HINTS = {"xrd": ("2theta", "2th", "twotheta", "angle", "pos2"), "ftir": ("wavenumber", "wavenum", "cm1", "ramanshift"),
           "temp": ("temperature", "temp", "degc", "celsius"), "time": ("time", "zeit", "tid", "hours", "minutes", "seconds", "age"),
           "size": ("size", "diameter", "particle", "micron", "channel")}
SKIP_Y = ("weight", "esd", "error", "sigma", "stdev", "uncert")

def _ucls(col):
    """counts or cps, from a column name such as 'Iobs [cps]' or 'Intensity [Counts]'."""
    s = str(col).lower()
    if "cps" in s or "/s" in s or "count rate" in s: return "cps"
    if "cts" in s or "count" in s: return "cts"
    return ""

def _even(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    if len(v) < 20: return False
    d = np.diff(v); return bool(np.all(d > 0) and np.std(d) < 0.05 * np.mean(d))

def detect_xrd(name, df, nums, texts, n, units):
    """HighScore-style XRD tables: a profile (observed with/without calculated), a scan, or a peak list."""
    find = lambda keys, pool: next((c for c in pool if any(k in n[c] for k in keys)), None)
    cols = list(nums); pos = find(("2theta", "2th", "twotheta", "pos2", "angle"), cols)
    if pos is None: return None
    base = dict(name=name, nums=nums, units=units, n=n, t=lambda c: titled(c, units))
    hcol = find(("height", "calcpeakheight", "relint", "irel", "intensity%", "area"), [c for c in cols if c != pos])
    phase = find(("phase", "assign", "mineral", "compound", "matched"), texts) or next((c for c in texts if n[c].split("|")[0] == "name"), None); code = find(("code",), texts)
    hkl = all(any(n[c].split("|")[0] == k for c in cols) for k in ("h", "k", "l")); widthc = find(("fwhmtotal", "fwhm", "integralbreadth"), cols)
    if hcol is None and (phase or code or hkl):       # a list of reflections whose height column is simply called 'Intensity' or 'Counts'
        hcol = find(("intens", "counts", "cts"), [c for c in cols if c != pos and n[c].split("|")[0] not in ("h", "k", "l")])
    if hcol is not None and not _even(nums[pos].values) and (phase or code or hkl or widthc or find(("dspacing",), cols)):
        hc = find(("heightcts", "heightcounts", "calcpeakheight", "height"), cols) or hcol
        return dict(base, kind="XRD peak list", x=pos, height=hc, phase=phase, code=code, fwhm=widthc, ys=[hc])
    if not _even(nums[pos].values): return None
    skip = ("dspacing", "dspacings", "q1", "ct", "no", "esd", "sigma", "error", "time", "step")
    ok = [c for c in cols if c != pos and n[c].split("|")[0] not in skip and not any(n[c].startswith(k) for k in ("dspac", "q1a", "ct", "no"))]
    obs = [c for c in ok if any(k in n[c] for k in ("yobs", "iobs", "obs", "measured", "intensitycounts", "intensitycts", "rawintensity"))]
    if not obs: obs = [c for c in ok if any(k in n[c] for k in ("intens", "counts", "cts", "cps")) and not any(k in n[c] for k in ("calc", "back", "bkg", "diff"))]
    calc = [c for c in ok if any(k in n[c] for k in ("ycalc", "icalc", "calc", "yfit", "fitted", "model"))]
    back = [c for c in ok if any(k in n[c] for k in ("iback", "yback", "background", "bkg", "bkgd"))]
    rank = lambda c: (0 if _ucls(c) == "cts" else 1 if _ucls(c) == "" else 2)
    obs.sort(key=rank)
    if calc:
        for o in obs:
            cs = [c for c in calc if _ucls(c) == _ucls(o)] or ([c for c in calc if _ucls(c) == "cts"] if _ucls(o) == "" else [])
            if cs:
                bs = [c for c in back if _ucls(c) == _ucls(cs[0])]; e = find(("esd", "sigma", "error"), [c for c in cols if c not in (pos, o, cs[0])])
                return dict(base, kind="Fit (observed + calculated)", x=pos, obs=o, calc=cs[0], back=bs[0] if bs else None, esd=e if e and _ucls(e) in ("", _ucls(o)) else None,
                            diff=find(("diff", "resid", "yobsycalc"), [c for c in ok if c not in (o, cs[0])]))
    if obs: return dict(base, kind="XRD", x=pos, ys=[obs[0]] + [c for c in back if _ucls(c) == _ucls(obs[0])][:0])
    return None

def detect(name, df, units, min_rows=5):
    nums = numeric_cols(df); texts = [c for c in df.columns if c not in nums]; n = {c: norm(c) + "|" + norm(units.get(c, "")) for c in df.columns}
    def find(keys, pool): return next((c for c in pool if any(k in n[c] for k in keys)), None)
    labcol = next((c for c in texts if n[c].split("|")[0] in ("label", "labels", "labeltext", "peaklabel")), None)
    if labcol is not None and len(df) <= 3000:
        xl = next((c for c in nums if any(k in n[c] for k in ("2theta", "2th", "pos", "position", "wavenumber", "temperature")) and "label" not in n[c]), None) or next((c for c in nums if "label" not in n[c]), None)
        if xl is not None:
            sc = next((c for c in texts if "sample" in n[c] or "sheet" in n[c]), None); ft = next((c for c in texts if "figure" in n[c]), None)
            return dict(kind="labels", name=name, x=nums[xl], text=df[labcol].astype(str), y=None, sample=df[sc].astype(str) if sc else None, ftype=df[ft] if ft else None)
    wide = [c for c in df.columns if re.search(r"(?i)[ _-]*(2 ?theta|2th|pos(ition)?)$", str(c).strip()) and re.sub(r"(?i)[ _-]*(2 ?theta|2th|pos(ition)?)$", "", str(c).strip())]
    if len(wide) >= 2 or (len(wide) == 1 and any(re.search(r"(?i)marker$", str(c)) for c in df.columns)):
        parts = []                                   # Bragg positions, one column (pair) per phase: an Origin-ready tick table
        for c in wide:
            ph = re.sub(r"(?i)[ _-]*(2 ?theta|2th|pos(ition)?)$", "", str(c).strip()); v = pd.to_numeric(df[c], errors="coerce").dropna().values.astype(float)
            if len(v): parts.append(pd.DataFrame({"Code": xs.code_for(ph), "Phase": ph, "tt": v, "d": xs.d_of(v, 1.5406), "height": 1.0, "fwhm": np.nan}))
        if parts:
            rows = pd.concat(parts, ignore_index=True); rows.attrs["markers"] = True
            return dict(name=name, nums=nums, units=units, n=n, t=lambda c: titled(c, units), kind="XRD peak list", x=wide[0], height=None, phase="wide", code=None, fwhm=None, ys=[wide[0]], wide=rows)
    if len(nums) >= 2 and len(df) >= 3:
        r = detect_xrd(name, df, nums, texts, n, units)
        if r: return r
    allx = [k for v in X_HINTS.values() for k in v]
    xc = [c for c in nums if any(k in n[c] for k in allx) or n[c].split("|")[0] in ("x", "q", "t", "d")]
    lablike = any(any(k in n[c] for k in ("label", "code", "phase", "peak", "assign", "hkl")) for c in texts)
    ser = None if lablike else next((c for c in texts if 2 <= df[c].astype(str).nunique() <= 12 and len(df) >= 2 * df[c].astype(str).nunique()), None)
    if ser is not None and len(nums) >= 2:
        rp = [c for c in nums if 2 <= nums[c].nunique() <= 0.6 * len(df)]
        xs_ = next((c for c in rp if any(k in n[c] for k in X_HINTS["time"] + ("dose", "content", "replacement", "level", "temp"))), rp[0] if rp else None)
        ys_ = [c for c in nums if c != xs_ and not any(k in n[c] for k in SKIP_Y)]
        if xs_ is not None and ys_:
            return dict(name=name, nums=nums, units=units, n=n, t=lambda c: titled(c, units), kind="XY", x=xs_, ys=ys_[:1], series=df[ser].astype(str), series_col=ser)
    if ser is not None and not any(k in n[c] for c in nums for k in ("2theta", "2th", "pos", "wavenumber", "angle", "peak", "shift")):
        vals_ = [c for c in nums if pd.Series(np.asarray(nums[c])).nunique() > 1 and not any(k in n[c] for k in SKIP_Y)]          # groups in a text column and numbers, no x axis: a table for bars
        if vals_: return dict(name=name, nums=nums, units=units, n=n, t=lambda c: titled(c, units), kind="XY", x=next((c for c in nums if c not in vals_), vals_[0]), ys=vals_[:6], series=df[ser].astype(str), series_col=ser, cat_only=True)
    if texts and len(df) <= 400 and xc and len(nums) <= 3:
        pool = [c for c in texts if "ident" not in n[c] and "sample" not in n[c]]
        code = find(("label", "code", "phase", "peak", "name", "assign"), pool) or (pool[0] if pool else texts[0])
        ycol = find(("yobs", "height", "top", "intens", "counts"), [c for c in nums if c != xc[0]]); sc = find(("sample", "sheet", "dataset"), texts)
        ft = find(("figuretype", "figure"), texts); idc = find(("ident", "meaning", "fullname", "phasename", "mineral"), [c for c in texts if c not in (code, sc, ft)])
        idmap = {str(a).strip(): str(b).strip() for a, b in zip(df[code], df[idc]) if pd.notna(a) and pd.notna(b)} if idc else {}
        return dict(kind="labels", name=name, x=nums[xc[0]], text=df[code].astype(str), y=nums.get(ycol), sample=df[sc].astype(str) if sc else None, ftype=df[ft] if ft else None, idmap=idmap)
    if len(nums) < 2 or len(df) < min_rows: return dict(kind="skip", name=name, why="no numeric data table" if len(nums) < 2 else f"only {len(df)} rows of numbers")
    cols = list(nums); rest = lambda x: [c for c in cols if c != x and not any(k in n[c] for k in SKIP_Y)]
    t = lambda c: titled(c, units)
    base = dict(name=name, nums=nums, units=units, n=n, t=t)
    # observed + calculated
    obs = find(("yobs", "iobs", "obs", "measured"), cols); calc = find(("ycalc", "icalc", "calc", "yfit", "fitted", "model"), [c for c in cols if c != obs])
    x_xrd = find(X_HINTS["xrd"], cols); x_ftir = find(X_HINTS["ftir"], cols); x_temp = find(X_HINTS["temp"], cols); x_time = find(X_HINTS["time"], cols); x_size = find(X_HINTS["size"], cols)
    mass = find(("mass", "weight", "tg", "massloss"), [c for c in cols if c not in (x_temp, x_time) and "dtg" not in n[c] and "deriv" not in n[c]])
    heat = find(("heatflow", "heatflux", "power", "thermalpower", "normalizedheatflow", "dsc"), [c for c in cols if c not in (x_temp, x_time)])
    if obs and calc:
        x = x_xrd or next((c for c in cols if c not in (obs, calc) and nums[c].dropna().is_monotonic_increasing), cols[0])
        return dict(base, kind="Fit (observed + calculated)", x=x, obs=obs, calc=calc, diff=find(("diff", "resid", "obscalc", "yobsycalc"), [c for c in cols if c not in (x, obs, calc)]))
    if x_size and any(k in n[x_size] for k in ("um", "µm", "micron", "size", "diameter")) and not x_xrd:
        return dict(base, kind="Particle size", x=x_size, ys=rest(x_size))
    scan = False
    if heat and x_temp:                                # a temperature that changes by more than 15 K is a temperature programme (DSC), not an isothermal run
        T_ = pd.to_numeric(pd.Series(nums[x_temp]), errors="coerce").dropna(); scan = len(T_) > 5 and float(T_.max() - T_.min()) > 15.0
    if mass and (x_temp or x_time): return dict(base, kind="TGA", x_temp=x_temp, x_time=x_time, mass=mass, dsc=heat if scan else None)
    if heat and scan: return dict(base, kind="DSC", x_temp=x_temp, x_time=x_time, heat=heat)
    if x_ftir or find(("absorb", "transmit"), cols):
        x = x_ftir or cols[0]; return dict(base, kind="FTIR", x=x, ys=rest(x))
    if x_xrd: return dict(base, kind="XRD", x=x_xrd, ys=rest(x_xrd))
    if heat and x_time: return dict(base, kind="Calorimetry", x=x_time, heat=heat, ys=rest(x_time))
    x = (xc[0] if xc else next((c for c in cols if nums[c].dropna().is_monotonic_increasing or nums[c].dropna().is_monotonic_decreasing), cols[0]))
    xv = nums[x].dropna().values
    if len(xv) > 50 and xv.min() >= 300 and xv.max() <= 4500 and (xv.max() - xv.min()) > 1500: return dict(base, kind="FTIR", x=x, ys=rest(x))
    ys = rest(x)
    if not ys: return dict(kind="skip", name=name, why="only one usable numeric column")
    yv = nums[ys[0]].dropna().values
    if len(xv) >= 300 and _even(xv) and 1 <= xv.min() and xv.max() <= 170 and np.median(np.diff(xv)) <= 0.2 and (xv.max() - xv.min()) >= 8 and np.nanmin(yv) >= 0:
        return dict(base, kind="XRD", x=x, ys=ys[:1], guessed=True)
    return dict(base, kind="XY", x=x, ys=ys)

# ============================================================================= builders (analysis)
def _clean(x, *ys):
    x = np.asarray(x, float); m = np.isfinite(x)
    for y in ys: m &= np.isfinite(np.asarray(y, float))
    return (x[m],) + tuple(np.asarray(y, float)[m] for y in ys)

def _sub(t):
    """C3S -> C\u2083S: a digit after a letter or a bracket becomes a subscript (drawn properly by matplotlib and by Origin)."""
    return re.sub(r"(?<=[A-Za-z)])\d+", lambda m: "".join(chr(0x2080 + int(c)) for c in m.group(0)), str(t))

def short_name(code, idmap=None):
    """The name written on a peak for a phase code: cement notation for the clinker phases, the mineral name when it is short."""
    if code in SHORT_NAMES: return SHORT_NAMES[code]
    nm = re.sub(r"\s*\(.*?\)", "", str((idmap or {}).get(code) or xs.CODE_NAMES.get(code) or "")).strip()
    if nm and len(nm) <= 11 and " " not in nm: return nm[:1].upper() + nm[1:]
    return None

def names_on(lab, idmap=None):
    """Labels with phase names instead of letters: A+B -> C3S/C2S. Returns (labels, codes that stay letters, any bracketed label)."""
    out, left, br = [], [], False
    for pos, t, y in lab:
        if re.match(r"^[\d.]+$", str(t)): out.append((pos, t, y)); continue
        parts = []
        for c in str(t).split("+"):
            b = c.strip().startswith("("); k = c.strip().strip("()"); q = k.endswith("?"); k = k.rstrip("?"); nm = short_name(k, idmap); br = br or b
            if nm is None: nm = k; left.append(c)
            parts.append(("(" if b else "") + _sub(nm) + ("?" if q else "") + (")" if b else ""))
        out.append((pos, "/".join(parts), y))
    return out, left, br

NAME_FRAC = 0.05          # names on the peaks: the main graph labels peaks of at least 5 % of the strongest one (names are long); the inset labels all of its range
def main_peaks(lab, x, bg, frac=None):
    """The labels of the stronger peaks (height above the background), plus bracketed phases."""
    if not lab: return lab
    net = [h_ - float(np.interp(p_, x, bg)) for p_, _, h_ in lab]; mx = max(net) or 1.0
    return [l_ for l_, n_ in zip(lab, net) if n_ >= (frac or NAME_FRAC) * mx or str(l_[1]).startswith("(")]

def _names_key(left, br, idmap=None):
    k = _key(left, idmap) if left else ""
    if br and "( ) =" not in k: k = (k + ". " if k else "") + BRACKET_NOTE
    return k

def parse_inset(opt, x):
    """The typed x range of the zoomed inset ('27-37'), in the units of the graph's own x axis, or None. It must lie inside
    the data of this graph and be clearly narrower than it, so a range meant for one kind of graph leaves the others alone."""
    m = re.findall(r"\d+(?:[.,]\d+)?", str((opt or {}).get("inset") or ""))
    if len(m) < 2: return None
    a, b = sorted(float(v.replace(",", ".")) for v in m[:2]); lo_, hi_ = float(np.nanmin(x)), float(np.nanmax(x)); span = (hi_ - lo_) or 1.0
    if a < lo_ - 0.02 * span or b > hi_ + 0.02 * span: return None
    a, b = max(a, lo_), min(b, hi_)
    return (a, b) if 0.02 * span <= b - a < 0.6 * span else None

def auto_inset(x, y, bg=None, width=10.0):
    """The 2-theta window (whole degrees) that holds the most diffracted intensity above the background: the crowded
    region of the main peaks, which is what a zoomed inset is for. None for a short scan."""
    x = np.asarray(x, float); y = np.asarray(y, float); span = float(x[-1] - x[0])
    if span < 3 * width or len(x) < 200: return None
    if bg is None or len(bg) != len(x):
        k = max(5, len(x) // 60); n_ = len(x) // k * k; bg = np.interp(x, x[:n_].reshape(-1, k).mean(1), y[:n_].reshape(-1, k).min(1))
    net = np.clip(y - np.asarray(bg, float), 0, None); c = np.concatenate([[0.0], np.cumsum(net)]); best = None
    for a in np.arange(math.ceil(x[0]), x[-1] - width + 1e-9, 1.0):
        i0, i1 = np.searchsorted(x, a), np.searchsorted(x, a + width); v = c[i1] - c[i0]
        if best is None or v > best[0] * 1.0001: best = (v, float(a))
    return (best[1], best[1] + width) if best else None

ZOOM_PANELS_MAX = 4                                                       # fits drawn as panels: each gets its zoomed part up to this many

def _panel_zoom(p, m, n, opt):
    """A fit drawn as one panel of several: the same zoomed part as its own graph (your range under Settings > Inset, or the region the
    app chose), observed and calculated only, when there are at most ZOOM_PANELS_MAX panels."""
    if n > ZOOM_PANELS_MAX or str((opt or {}).get("inset") or INSETS[0]).startswith("No"):
        return
    rng = ((m.spec["panels"][0].get("inset") or {}).get("xlim"))
    if rng:
        p["inset"] = dict(xlim=tuple(rng), only=("Observed", "Calculated"), auto_side=True, rect_in=(0.0, 0.50, 0.34, 0.47), tick_room=0.19)

def _observed(curves):
    """The measured curve of a panel (a fit has observed and calculated; drawn in the paper style the calculated one comes first)."""
    return next((c for c in curves if str(c.get("label", "")).lower() in ("observed", "yobs", "iobs")), curves[0])

def _codelabs(p):
    """The labels of a panel as phase codes (combined figures always use the letters, also when a single graph shows names)."""
    return p.get("code_labels") if p.get("code_labels") is not None else p.get("labels")

TICKCOL = [(0, 0, 255), (0, 128, 0), (255, 0, 255), (255, 128, 0), (0, 139, 139), (128, 0, 128), (139, 69, 19), (128, 128, 0), (220, 20, 60), (70, 70, 70)]

def _key(codes, idmap=None):
    """'A = alite (C3S), B = belite ...' for the codes used, in the usual order (clinker phases first).
    Names given in your own files (a label sheet with a phase-identity column, a label key) come first."""
    idmap = idmap or {}
    cs = []; br = False
    for c in codes:
        br = br or c.strip().startswith("("); c = c.strip().strip("()").rstrip("?")
        if c and c not in cs and not re.match(r"^[\d.]+$", c): cs.append(c)
    order = list(xs.CODE_NAMES); cs.sort(key=lambda c: order.index(c) if c in order else 99)
    nm = lambda c: idmap.get(c) or xs.CODE_NAMES.get(c, c)
    cs = [c for c in cs if str(nm(c)).strip().lower() != c.strip().lower()]          # a label that is already a full name ('quartz') needs no line in the key
    if br: return ", ".join(f"{c} = {nm(c)}" for c in cs) + ". ( ) = phase included in the refinement, no individually resolved peak"
    return ", ".join(f"{c} = {nm(c)}" for c in cs)

def _xrd_analysis(d, x, y, lam, opt, given, bg=None, label_y=None):
    """Peaks, phases and labels of one pattern. Returns (labels, peak table, phase table, record lines, warnings, background, codes used)."""
    rec, warn = [], []; mode = opt.get("xrd_labels"); mode = mode if mode in XRD_LABELS else XRD_LABELS[0]; lib, sig = library(opt); only = phase_filter(opt)
    xfull = x; nfull = len(x)
    if nfull > 30000:                                 # very long scan: analyse block averages (the curve drawn keeps every point)
        k_ = int(math.ceil(nfull / 20000)); m_ = nfull // k_ * k_
        x = x[:m_].reshape(-1, k_).mean(1); y = y[:m_].reshape(-1, k_).mean(1)
        if bg is not None: bg = np.asarray(bg, float)[:m_].reshape(-1, k_).mean(1)
        if label_y is not None: label_y = np.asarray(label_y, float)[:m_].reshape(-1, k_).max(1)
        rec.append(f"{nfull} points: peaks were searched in averages of {k_} neighbouring points; the curve drawn keeps every point")
    key = (round(lam, 5), tuple(only or ()), sig, None if bg is None else float(np.nansum(bg)), id(d.get("_peaklist")), mode)
    if d.get("_cache_key") == key: pk, b, info, ph, pats, inf = d["_cache"]
    else:
        pk, b, info = xs.find_xrd_peaks(x, y, lam, bg=bg); ph, pats, inf = {}, {}, {}
        marks = d.get("_peaklist") is not None and bool(d["_peaklist"].attrs.get("markers"))
        if marks and opt.get("xrd_store", True):      # a phase of your Bragg table that the library does not know: keep it, with intensities read from this pattern
            try:
                rows_ = d["_peaklist"]; unknown = [c for c in dict.fromkeys(rows_["Code"].astype(str)) if c not in set(lib["Code"].astype(str))]
                for c_ in unknown:
                    g_ = lines_from_pattern(rows_, c_, pk, lam); tot_ = int((rows_["Code"].astype(str) == c_).sum())
                    new_, skip_ = store_phases(g_, opt, f"Bragg positions of {(re.findall(r'\(([^()]*)\)\s*$', str(d.get('_peaklist_from') or '')) or [d.get('name', 'your file')])[0]}; intensities read from the measured pattern at the {len(g_)} of {tot_} lines that no other phase shares")
                    if new_: rec.append(f"new phase stored for future phase suggestions: {new_[0][0]} = {new_[0][1]} ({new_[0][2]} lines). Its Bragg table gives positions only, so the relative intensities were read from this pattern at the peaks no other phase shares - an estimate; a reference card (Phase library > Add phase from file) is better")
                    elif c_ in _unwanted(opt): pass
                    else: rec.append(f"phase {c_} of your Bragg table is not in the phase library and could not be stored: fewer than {STORE_MIN} of its lines are free of other phases. Add its reference card under XRD tools > Phase library")
                if unknown: lib, sig = library(opt); key = key[:2] + (sig,) + key[3:]
            except Exception: pass
        if marks: only = sorted(set(d["_peaklist"]["Code"]) | {"R", "Z"})        # the phases of your refinement, plus the internal standards
        if d.get("_peaklist") is not None and not marks:
            pats = xs.patterns_from_peaklist(x, d["_peaklist"], lam, fwf=xs.width_model(pk)[0]); xs.assign(pk, x, pats); [p.__setitem__("shares", p["shares"]) for p in pk]
        elif not mode.startswith(("2θ", "d-", "No")) and not given and len(lib) and (mode.startswith("Suggest") or marks):
            ph, pats, inf = xs.identify(x, y, pk, lib, lam, b, only=only)
            if marks:                                 # an internal standard that is not in your phase list needs several peaks of its own
                for c_ in ("R", "Z"):
                    if c_ in ph and c_ not in set(d["_peaklist"]["Code"]) and ph[c_]["own_peaks"] < 3: ph.pop(c_); pats.pop(c_, None)
            xs.assign(pk, x, pats)
        else: xs.assign(pk, x, {})
        d["_cache_key"] = key; d["_cache"] = (pk, b, info, ph, pats, inf)
    rec.append(f"background: SNIP algorithm (features broader than {info.get('bg_width', 2):g}° are background); peaks need a signal-to-noise ratio of at least 5 (noise from counting statistics) and 1 % of the strongest peak")
    if info: rec.append(f"{len(pk)} peaks found; typical width {info['fwhm_typical']:.3f}°; smoothing used only for finding peaks ({info['smooth_window']} points); {info['n_ka2']} peaks recognised as K-alpha2 partners and not labelled. The curve drawn is the measured data")
    low = set(); marks = d.get("_peaklist") is not None and bool(d["_peaklist"].attrs.get("markers"))
    if marks: rec.append(f"the Bragg table of the same sample ({d.get('_peaklist_from', 'linked sheet')}) gives positions without intensities: it is used for the tick rows and to limit the phase labels to the phases of your refinement (plus the internal standards rutile and zincite)")
    if d.get("_peaklist") is not None and not marks:
        rec.append(f"phase labels from the peak list of the same sample ({d.get('_peaklist_from', 'linked file')}): the phases and reflections of your own refinement")
        if d.get("_peaklist_how"): rec.append(d["_peaklist_how"])
    elif ph:
        for c, v in ph.items():
            if v["own_peaks"] == 0 or (v["own_peaks"] == 1 and v["share"] < 0.02): low.add(c)
        rec.append(f"phase suggestions: whole-pattern match against {inf['tested']} library phases" + (f" (only {' '.join(only)})" if only else "") +
                   f"; zero shift {inf['shift']:+.3f}°, K-alpha2 {'present' if inf['ka2'] else 'not present'} in the data, {100 * inf['explained']:.0f} % of the weighted peak intensity explained. "
                   "A phase is kept only if the fit gets clearly worse without it and it has a measured peak of its own. These are suggestions, not an identification: check them")
        if low: warn.append("weakly supported phases (marked with ?): " + ", ".join(sorted(low)))
    if given:
        lab, w2 = snap_labels(x, y if label_y is None else label_y, given, tol=max(0.15, 3 * float(np.median(np.abs(np.diff(x)))))); warn += w2
        rec.append(f"{len(lab)} peak labels from your label sheet, each moved onto the measured peak top"); d["_given_pos"] = [p_ for p_, _, _ in lab]
        if opt.get("xrd_store", True) and not d.get("_stored_labels"):          # a phase of your label sheet that the library does not know, with its name in the key
            d["_stored_labels"] = True
            try:
                idm = d.get("_idmap") or {}; known = set(lib["Code"].astype(str)); yy = np.asarray(y if label_y is None else label_y, float); rows_ = []
                for p_, t_, h_ in lab:
                    t_ = str(t_).strip()
                    if t_ in known or t_ not in idm or not re.match(r"^[A-Za-z][A-Za-z'*]{0,5}$", t_): continue
                    rows_.append({"Phase": str(idm[t_]), "Code": t_, "d": float(xs.d_of(p_, lam)), "I": float(np.interp(p_, x, yy) - np.interp(p_, x, b))})
                if rows_:
                    new_, skip_ = store_phases(pd.DataFrame(rows_), opt, f"your peak labels of {d.get('_display') or d.get('name', 'your file')} (measured peak heights)")
                    if new_: rec.append("new phases stored for future phase suggestions, from your peak labels: " + ", ".join(f"{c} = {nm} ({n} lines)" for c, nm, n in new_) + ". Only the peaks you labelled are known, so a reference card (Phase library > Add phase from file) is better")
            except Exception: pass
        if opt.get("xrd_max") is None and mode.startswith(("Only", "Suggest")):          # every other measured peak that the peak list explains gets its label too
            tol = max(0.12, 3 * float(np.median(np.abs(np.diff(x))))); have = [p_ for p_, _, _ in lab]; add = []
            for p in pk:
                if p["ka2"] or not p.get("phases") or any(abs(p["pos"] - h_) < max(tol, 0.7 * p["fwhm"]) for h_ in have): continue
                if min(p["pos"] - x[0], x[-1] - p["pos"]) < 0.4: continue          # cut off by the end of the scan: not a resolved peak
                add.append((p["pos"], "+".join(p["phases"]), p["top"] if label_y is None else float(np.interp(p["pos"], x, label_y)))); have.append(p["pos"])
            if add: lab = sorted(lab + add); rec.append(f"{len(add)} further measured peaks labelled from the peak list of the same sample (phases giving at least 30 % of the calculated intensity at the peak, at most two)")
    elif mode.startswith("No"): lab = []
    elif mode.startswith("Only") and d.get("_peaklist") is None:
        lab = []; rec.append("no phase labels: your files give none for this sample (no label sheet, no peak list or Bragg table of it), and the app does not guess. "
                             "For the app's own suggestions choose 'Suggest phases from the library' under Analysis settings > XRD > Peak labels")
    else:
        m = "2theta" if mode.startswith("2θ") else "d" if mode.startswith("d-") else "phase"
        lab = xs.choose_labels(pk, opt.get("xrd_max"), m)
        if opt.get("xrd_max") is None: lab = [l_ for l_ in lab if min(l_[0] - x[0], x[-1] - l_[0]) >= 0.4]
        lab = [(p_, "+".join(c + ("?" if c in low else "") for c in t_.split("+")) if m == "phase" and not re.match(r"^[\d.]+$", t_) else t_, h_) for p_, t_, h_ in lab]
        if label_y is not None: lab = [(p_, t_, float(np.interp(p_, x, label_y))) for p_, t_, h_ in lab]
    mx = max([p["net"] for p in pk] or [1.0])
    if lab and not mode.startswith(("2θ", "d-", "No")):
        left = [p for p in pk if not p["ka2"] and not any(abs(p["pos"] - l_[0]) < max(0.12, 0.7 * p["fwhm"]) for l_ in lab)]
        if left: rec.append(f"{len(left)} small measured peaks carry no label (strongest {100 * max(p['net'] for p in left) / mx:.1f} % of the main peak): " + ("no reflection of the peak list explains them" if d.get("_peaklist") is not None else "no phase explains them") + "; they are listed in the analysis table")
        d["_unlabelled"] = len(left)
    table = [{"2theta (deg)": round(p["pos"], 3), "d (A)": round(p["d"], 4), "Height above background": round(p["net"], 1), "Rel. intensity (%)": round(100 * p["net"] / mx, 1),
              "FWHM (deg)": round(p["fwhm"], 3), "Signal/noise": round(p["snr"], 1), "K-alpha2 partner": "yes" if p["ka2"] else "",
              "Phase(s)": "+".join(p.get("phases", [])), "Shares": "; ".join(f"{k} {100 * v:.0f} %" for k, v in sorted(p.get("shares", {}).items(), key=lambda kv: -kv[1]))} for p in pk]
    ptab = [{"Code": c, "Phase": xs.CODE_NAMES.get(c, v["name"]), "Share of the fitted peak intensity (%) - not wt%": round(100 * v["share"], 1), "Peaks of its own": v["own_peaks"],
             "Confidence": "low (?)" if c in low else ("good" if v["own_peaks"] >= 3 else "medium")} for c, v in sorted(ph.items(), key=lambda kv: -kv[1]["share"])]
    codes = [c for _, t_, _ in lab for c in t_.split("+") if not re.match(r"^[\d.]+$", c)]
    if nfull > 30000: b = np.interp(xfull, x, b)
    return lab, table, ptab, rec, warn, b, codes

def build_xrd(d, opt, given):
    x, y = _clean(d["nums"][d["x"]].values, d["nums"][d["ys"][0]].values); o = np.argsort(x); x, y = x[o], y[o]
    lam = wavelength(opt, d); ycol = d["ys"][0]; bgm = opt.get("xrd_background") or XRD_BG[0]
    rec = d.setdefault("_rec", [])
    rec.append(f"wavelength {lam:.5f} Å " + ("(read from the instrument file)" if d.get("lam_file") and str(opt.get("wavelength", "Automatic")).startswith("Automatic") else "(from Analysis settings)") + "; d = λ / (2 sin θ)")
    if d.get("guessed"): rec.append("recognised as XRD from the values (evenly spaced angles, no column names)")
    lab, table, ptab, r2, warn, b, codes = _xrd_analysis(d, x, y, lam, opt, given)
    rec += r2; yp = y - b if bgm.startswith("Subtract") else y
    if bgm.startswith("Subtract"): lab = [(p_, t_, float(np.interp(p_, x, yp))) for p_, t_, h_ in lab]; rec.append("plotted: measured intensity minus the SNIP background")
    u = _ucls(ycol); yname = "Net intensity (counts)" if bgm.startswith("Subtract") and u != "cps" else "Intensity (counts)" if u == "cts" or "count" in d["n"][ycol] else "Intensity (cps)" if u == "cps" else "Intensity (a.u.)"
    cs = [curve(str(ycol), x, yp, PALETTE[0])]
    if bgm.startswith("Draw"): cs.append(curve("background", x, b, (150, 150, 150)))
    named = str(opt.get("label_text") or LABEL_TEXT[0]).startswith("Phase names"); lab0 = lab
    if named:
        lab, left_, br_ = names_on(lab, d.get("_idmap")); full_ = lab; lab = main_peaks(lab, x, np.zeros_like(x) if bgm.startswith("Subtract") else b)
        rec.append(f"peak labels written as phase names (cement notation) instead of letters; {len(lab)} of {len(full_)} peaks carry a name in the main graph (at least {100 * NAME_FRAC:g} % of the strongest peak), the zoomed inset names every peak of its range")
    vert = not all(re.match(r"^[A-Za-z'+?]{1,9}$", t_) for _, t_, _ in lab) if lab else True
    p = panel(yname, cs, labels=lab, vertical=vert, legend=bgm.startswith("Draw"))
    p["ylim"] = None
    if named: p["code_labels"] = lab0; p["max_lift"] = 0.22
    rng = parse_inset(opt, x); auto_ = False
    if not rng and zoom_auto(opt, every=True):                     # 'On every XRD pattern and fit': the crowded region of the main peaks
        rng = auto_inset(x, yp, np.zeros_like(x) if bgm.startswith("Subtract") else b); auto_ = bool(rng)
    if rng: p["inset"] = dict(xlim=rng, labels=full_ if named else lab); rec.append(f"zoomed inset of {rng[0]:g}-{rng[1]:g}° 2θ: the same data on its own intensity scale" + (" (chosen by the app: the 10° window with the most diffracted intensity; Settings > XRD > Zoomed part)" if auto_ else ""))
    sp = dict(title=d["name"], xname="2θ (°)" + (f", λ = {lam:.4f} Å" if abs(lam - 1.5406) > 0.002 else ""), panels=[p], lam=lam, arrows=str(opt.get("pointers") or POINTERS[0]).startswith("Arrow"))
    k = _names_key(left_, br_, d.get("_idmap")) if named else _key(codes, d.get("_idmap"))
    if k: sp["note"] = k + (". " + KEY_NOTE if any(t_.endswith("?") or "?+" in t_ for _, t_, _ in lab) else "")
    d["_extra"] = {"phases": pd.DataFrame(ptab)} if ptab else {}
    return sp, table, warn

def build_fit(d, opt, given):
    nums = d["nums"]; cols = [nums[d["x"]].values, nums[d["obs"]].values, nums[d["calc"]].values]
    hasb = d.get("back") is not None; hase = d.get("esd") is not None
    if hasb: cols.append(nums[d["back"]].values)
    if hase: cols.append(nums[d["esd"]].values)
    x = np.asarray(cols[0], float); m = np.isfinite(x) & np.isfinite(np.asarray(cols[1], float)) & np.isfinite(np.asarray(cols[2], float))
    o = np.argsort(x[m]); x = x[m][o]; yo = np.asarray(cols[1], float)[m][o]; yc = np.asarray(cols[2], float)[m][o]
    yb = np.asarray(cols[3], float)[m][o] if hasb else None; es = np.asarray(cols[-1], float)[m][o] if hase else None
    rec = d.setdefault("_rec", []); lam = wavelength(opt, d); warn = []; info = d.get("_info") or {}
    style = opt.get("fit_style") if opt.get("fit_style") in FIT_STYLES else FIT_STYLES[0]; hs = style.startswith("HighScore")
    withdiff = style != FIT_STYLES[2]; withticks = style in (FIT_STYLES[1], FIT_STYLES[3])
    R, how = xs.rwp(yo, yc, es); rec.append(f"Rwp = {R:.2f} % recomputed from the observed and calculated columns of this file ({how})")
    if info.get("rwp") is not None:
        rec.append(f"Rwp written in your file: {info['rwp']:.2f} %")
        if abs(info["rwp"] - R) > 0.1: warn.append(f"the Rwp written in your file ({info['rwp']:.2f} %) differs from the one recomputed from the curves ({R:.2f} %); the graph shows the recomputed value")
    if _ucls(d["obs"]) != _ucls(d["calc"]) and _ucls(d["obs"]) and _ucls(d["calc"]): warn.append(f"observed ({d['obs']}) and calculated ({d['calc']}) are in different units")
    rec.append(f"observed = '{d['obs']}', calculated = '{d['calc']}'" + (f", background = '{d['back']}'" if hasb else "") + (f", ESD = '{d['esd']}'" if hase else ""))
    lab, table, ptab, r2, w2, b, codes = _xrd_analysis(d, x, yo, lam, opt, given, bg=yb, label_y=np.maximum(yo, yc))
    rec += r2; warn += w2
    cps = _ucls(d["obs"]) == "cps"
    # phases for the legend and the tick rows: your phase table (with wt%) > linked peak list > names from the label sheet > suggestions
    pl = d.get("_peaklist"); idmap = d.get("_idmap") or {}
    if info.get("phases"):
        for i, r in enumerate(info["phases"]): r["colour"] = r.get("colour") or TICKCOL[i % len(TICKCOL)]
        ents = [(r["colour"], f"{r['name']}  {r['wt']:.1f} wt%" if r.get("wt") is not None else r["name"]) for i, r in enumerate(info["phases"])]
        rec.append("phase legend from the phase table in your file" + (" (with wt%)" if any(r.get("wt") is not None for r in info["phases"]) else ""))
    elif pl is not None and len(pl):
        ents = [(TICKCOL[i % len(TICKCOL)], str(pl.loc[pl["Code"] == c, "Phase"].iloc[0])) for i, c in enumerate(dict.fromkeys(pl["Code"]))]
    else:
        used = []
        for _, t_, _ in lab:
            for c_ in t_.split("+"):
                c_ = c_.strip("()?")
                if c_ and not re.match(r"^[\d.]+$", c_) and c_ not in used: used.append(c_)
        ents = [(TICKCOL[i % len(TICKCOL)], f"{idmap.get(c_) or xs.CODE_NAMES.get(c_, c_)} ({c_})") for i, c_ in enumerate(used)]
    disp = d.get("_display") or d["name"]
    brb = not str(opt.get("fit_colours") or FIT_COLOURS[0]).startswith("HighScore")           # observed black, calculated red, difference blue
    if hs:
        cs = [curve("Observed", x, yo, OBS_COL if brb else (255, 0, 0)), curve("Calculated", x, yc, CALC_COL if brb else (0, 0, 255))]      # calculated on top
        yname = "Counts per second" if cps else "Counts"; xn = f"Position [°2θ] ({tube_name(lam)})"
    else:
        cs = [curve("Ycalc", x, yc, (200, 0, 0)), curve("Yobs", x, yo, (0, 0, 0))]                 # paper: calculated first, measured black on top so red never hides it
        yname = "Intensity (cps)" if cps else "Intensity (counts)"; xn = "2θ (°)" + (f", λ = {lam:.4f} Å" if abs(lam - 1.5406) > 0.002 else "")
    if hasb and str(opt.get("xrd_background") or "").startswith("Draw"): cs.append(curve("Background", x, yb, (0, 128, 0)))
    named = str(opt.get("label_text") or LABEL_TEXT[0]).startswith("Phase names"); lab0 = lab
    if named:
        lab, left_, br_ = names_on(lab, idmap); codes = list(left_); full_ = lab; lab = main_peaks(lab, x, b)
        rec.append(f"peak labels written as phase names (cement notation) instead of letters; {len(lab)} of {len(full_)} peaks carry a name in the main graph (at least {100 * NAME_FRAC:g} % of the strongest peak), the zoomed inset names every peak of its range")
    top = panel(yname, cs, weight=3.6, labels=lab, vertical=named and any(len(t_) > 3 for _, t_, _ in lab), legend=False)
    if named: top["code_labels"] = lab0; top["max_lift"] = 0.22
    top["_bg"] = b
    rng = parse_inset(opt, x); auto_ = False
    if not rng and zoom_auto(opt) and withdiff:        # a fit: the crowded region of the main peaks, chosen by the app
        rng = auto_inset(x, yo, b); auto_ = bool(rng)
    if rng: top["inset"] = dict(xlim=rng, labels=full_ if named else lab); rec.append(f"zoomed inset of {rng[0]:g}-{rng[1]:g}° 2θ: observed and calculated on their own intensity scale" + (" (chosen by the app: the 10° window with the most diffracted intensity above the background; type another range under Settings > Inset)" if auto_ else ""))
    ents = [(c_ if (withticks and withdiff and pl is not None and len(pl)) else None, re.sub(r"_+", " ", t_)) for c_, t_ in ents]      # a colour square only when tick rows of that colour are drawn
    keys = [(c["colour"], c["label"]) for c in cs]
    pfit = bool(re.search(r"(?i)profile fit|empirical|no crystal|pawley|le ?bail", str(info.get("fit") or "")))      # a fit without crystal structures is named as such on the graph
    if pfit: rec.append("your sample sheet says this calculated curve is a profile fit without crystal structures: the graph writes 'Rwp (profile fit)', and it is not a Rietveld refinement")
    lines = [f"Rwp (profile fit) = {R:.2f} %" if pfit else f"Rwp = {R:.2f} %"] + ([f"Amorphous = {info['amorphous']:.1f} wt%"] if info.get("amorphous") is not None and not any("amorph" in e[1].lower() for e in ents) else [])
    q = [r for r in (info.get("phases") or []) if r.get("wt") is not None]
    if q:
        d["_quant"] = pd.DataFrame([{"Phase": r["name"], "Code": "" if r["name"].lower().startswith("amorph") else (r.get("code") or xs.code_for(r["name"])), "wt%": r["wt"]} for r in q])
        if not hs: lines += _quant_lines(q)                       # paper style has no phase legend: amounts as text
        rec.append("phase amounts (wt%) from the phase table in your files: " + ", ".join(f"{r['name']} {r['wt']:g}" for r in q))
    else:
        d["_quant"] = None
        if ents and not pfit: warn.append("no phase amounts (wt%) found for this sample in the loaded files; add a phase table (see phase_amounts_template.csv) to show them")
    top["legendbox"] = dict(title=disp, keys=keys, entries=ents if hs else [], lines=lines)
    if rng:                                           # with an inset the corner box stays small (name, curve key, Rwp); the phase amounts move to a column right of the graph
        side_ = ([t_ for _, t_ in ents] if hs else []) + lines[1:]
        top["legendbox"] = dict(title=disp, keys=keys, entries=[], lines=lines[:1])
        if side_: top["side"] = [("Phases", True)] + [(re.sub(r"\s{2,}", "  ", t_.strip()), False) for t_ in side_]
    pans = [top]
    mid = (_BUILD_FMT or {}).get("fit_middle") or opt.get("fit_middle") or FIT_MIDDLE[0]          # the part between the fit and the difference
    if mid not in FIT_MIDDLE: mid = FIT_MIDDLE[0]
    if mid != FIT_MIDDLE[0]: withticks = mid in (FIT_MIDDLE[1], FIT_MIDDLE[3])
    sticks = mid in (FIT_MIDDLE[2], FIT_MIDDLE[3])
    if sticks and (pl is None or not len(pl) or "height" not in pl):
        rec.append("peaks with labels were asked for, but no peak list with heights (Height) is linked to this fit: add the peak list exported from HighScore"); sticks = False
    if sticks:                                                    # each listed peak as a line as high as its calculated height, coloured by phase, the strong ones labelled
        cmap_ = {(r.get("code") or xs.code_for(r["name"])): r["colour"] for r in (info.get("phases") or []) if r.get("colour")}
        q = pl[(pl["tt"] >= x.min()) & (pl["tt"] <= x.max()) & (pl["height"] > 0)]
        hmax = float(q["height"].max()) if len(q) else 1.0; sk = []
        for i, c in enumerate(dict.fromkeys(q["Code"])):
            r_ = q[q["Code"] == c]; tt = r_["tt"].values; hh = r_["height"].values / hmax
            sx = np.repeat(tt, 3); sy = np.column_stack([np.zeros_like(hh), hh, np.full_like(hh, np.nan)]).ravel(); sx[2::3] = np.nan
            sk.append(curve(c, sx, sy, cmap_.get(c, TICKCOL[i % len(TICKCOL)])))
        grp = []                                                   # peaks closer than 0.12° share one label ("B+C")
        for t_, c_, h_ in sorted(zip(q["tt"].values, q["Code"].values, q["height"].values / hmax)):
            if grp and t_ - grp[-1][0] < 0.12: g0 = grp[-1]; grp[-1] = (g0[0], g0[1] + ([c_] if c_ not in g0[1] else []), max(g0[2], h_))
            else: grp.append((t_, [c_], h_))
        nlab = int(opt.get("xrd_max") or 25) if opt.get("xrd_max") else 25
        labs_ = sorted(grp, key=lambda g_: -g_[2])[:nlab]; labs_ = [(g_[0], "+".join(g_[1]), g_[2]) for g_ in sorted(labs_) if g_[2] >= 0.03]
        spn = panel("Peaks", sk, weight=1.6, labels=labs_, vertical=False, legend=False); spn["yticks"] = False; spn["ylim"] = None
        pans.append(spn); rec.append(f"peaks with labels: the {len(q)} reflections of the linked peak list as lines of their calculated height (relative), coloured by phase, the {len(labs_)} strongest labelled")
        codes = codes + [c_ for c_ in dict.fromkeys(q["Code"]) if c_ not in codes]
    if withdiff or withticks:
        if withticks and pl is not None and len(pl):
            codes_pl = list(dict.fromkeys(pl["Code"])); tk = []; rows = []
            cmap = {(r.get("code") or xs.code_for(r["name"])): r["colour"] for r in (info.get("phases") or []) if r.get("colour")}      # same colours as the legend
            for i, c in enumerate(codes_pl):
                tt = pl.loc[pl["Code"] == c, "tt"].values; tt = tt[(tt >= x.min()) & (tt <= x.max())]; yv = len(codes_pl) - 1 - i; col = cmap.get(c, TICKCOL[i % len(TICKCOL)])
                tx = np.repeat(tt, 3); ty = np.tile([yv + 0.15, yv + 0.85, np.nan], len(tt)); tx[2::3] = np.nan
                tk.append(curve(c, tx, ty, col)); rows.append((yv + 0.5, c, col))
            tp = panel("", tk, weight=max(0.5, 0.2 * len(codes_pl)), ylim=(0, len(codes_pl)), legend=False); tp["yticks"] = False; tp["rows"] = rows; tp["thin"] = True
            pans.append(tp); rec.append("Bragg positions (tick rows) from the linked peak list, one row per phase"); codes = codes + codes_pl
    if withdiff:
        dif = yo - yc; mdf = float(np.abs(dif).max()) * 1.1 or 1.0
        pans.append(panel("Difference" if hs else "Diff.", [curve("Yobs − Ycalc", x, dif, DIF_COL if brb else (0, 0, 0) if hs else PALETTE[2])], weight=1.0, legend=False, ylim=(-mdf, mdf)))
    rec.append(f"look: {style}")
    sp = dict(title=disp, xname=xn, panels=pans, lam=lam, arrows=str(opt.get("pointers") or POINTERS[0]).startswith("Arrow"))
    k = _key(codes, idmap)
    if named: k = _names_key([c_ for c_ in codes], br_, idmap)
    if k and not hs: sp["note"] = k + (". " + KEY_NOTE if any("?" in t_ for _, t_, _ in lab) else "")
    elif k and hs and lab: sp["note"] = "Labels: " + k + (". " + KEY_NOTE if any("?" in t_ for _, t_, _ in lab) else "")
    d["_extra"] = {"phases": pd.DataFrame(ptab)} if ptab else {}
    if d.get("_quant") is not None: d["_extra"]["quantification"] = d["_quant"]
    table = [dict(r, **{"Rwp (%)": round(R, 2)}) if i == 0 else r for i, r in enumerate(table)]
    return sp, table, warn

def _lam_from_d(d):
    """The wavelength of a table that has a 2theta column and a d-spacing column: λ = 2 d sin θ. A HighScore peak list of a
    refinement lists every reflection twice, for Kα1 and for Kα2; the Kα2 rows are found by their longer wavelength.
    Returns (wavelength of the Kα1 rows in Å, True for every Kα2 row) or None when the two columns do not agree."""
    try:
        nums, n = d["nums"], d["n"]; x = d["x"]
        dc = next((c for c in nums if c != x and (n[c].split("|")[0].startswith("dspac") or n[c].split("|")[0] == "d")), None)
        if dc is None: return None
        tt = np.asarray(nums[x], float); dd = np.asarray(nums[dc], float); ok = np.isfinite(tt) & np.isfinite(dd) & (tt > 1) & (tt < 179) & (dd > 0.3)
        if ok.sum() < 5: return None
        lam = np.full(len(tt), np.nan); lam[ok] = 2 * dd[ok] * np.sin(np.radians(tt[ok] / 2))
        l1 = float(np.median(lam[ok][lam[ok] <= np.nanpercentile(lam[ok], 5) * 1.0008]))
        if not 0.3 < l1 < 3.0: return None
        a2 = ok & (lam > l1 * 1.0015) & (lam < l1 * 1.004); odd = ok & ~a2 & (np.abs(lam - l1) > 0.001 * l1)
        if odd.sum() > 0.05 * ok.sum(): return None
        near = min(TUBES.values(), key=lambda v: abs(v - l1))
        return (float(near) if abs(near - l1) < 0.0006 else round(l1, 5)), a2
    except Exception: return None

KA2_RATIO = [(1.5406, 1.002485), (1.78897, 1.002167), (1.93604, 1.002034), (2.28970, 1.001709), (0.70930, 1.006048), (0.55941, 1.007886)]     # λ(Kα2) / λ(Kα1) of the usual tubes

def _ka2_partners(tt, h, ph, lam):
    """True for the rows of a peak list that are the Kα2 partner of another row: same phase, the position that the same
    d-spacing has with the second wavelength of the tube, and about half the height. Used when the list has no d-spacing
    column. Returns None unless at least 30 % of the rows are such partners (a refinement lists every reflection twice)."""
    try:
        lam0, ratio = min(KA2_RATIO, key=lambda t_: abs(t_[0] - lam))
        if abs(lam0 - lam) > 0.01: return None
        tt = np.asarray(tt, float); h = np.asarray(h, float); out = np.zeros(len(tt), bool)
        for p_ in set(ph):
            idx = np.where((np.asarray(ph, dtype=object) == p_) & np.isfinite(tt) & np.isfinite(h) & (tt > 1) & (tt < 170))[0]
            if len(idx) < 2: continue
            idx = idx[np.argsort(tt[idx])]; t = tt[idx]; want = 2 * np.degrees(np.arcsin(np.clip(ratio * np.sin(np.radians(t / 2)), 0, 1)))
            j = np.searchsorted(t, want)
            for a, w in enumerate(want):
                if out[idx[a]]: continue                           # a Kα2 row has no partner of its own
                for b_ in (j[a] - 1, j[a], j[a] + 1):
                    if 0 <= b_ < len(t) and b_ != a and not out[idx[b_]] and abs(t[b_] - w) <= 0.004 and (h[idx[a]] <= 0 or 0.4 <= h[idx[b_]] / h[idx[a]] <= 0.6 or h[idx[a]] < 3):
                        out[idx[b_]] = True; break
        return out if out.sum() >= 0.3 * len(tt) else None
    except Exception: return None

def peaklist_rows(d, lam):
    """Code, Phase, tt, d, height, fwhm of a peak-list table (for linking and learning)."""
    if d.get("wide") is not None:
        r = d["wide"]
        if abs(lam - 1.5406) > 1e-6: m_ = r.attrs.get("markers"); r = r.assign(d=xs.d_of(r["tt"].values, lam)); r.attrs["markers"] = m_
        return r
    nums = d["nums"]; tt = nums[d["x"]].values.astype(float); h = nums[d["height"]].values.astype(float)
    df = d.get("_df"); ph = df[d["phase"]].map(lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip()).values if d.get("phase") is not None else np.array(["peaks"] * len(tt))
    cd = df[d["code"]].astype(str).values if d.get("code") is not None else np.array([xs.code_for(p) for p in ph])
    fw = nums[d["fwhm"]].values.astype(float) if d.get("fwhm") is not None else np.full(len(tt), np.nan)
    ph = np.array([re.sub(r"\s*_+\s*", " ", str(p_)).strip() for p_ in ph], dtype=object)          # HighScore writes 'Quartz_alpha', 'Zinc_oxide'
    if d.get("code") is None: cd = np.array([xs.code_for(p_) for p_ in ph])
    r = pd.DataFrame({"Code": cd, "Phase": ph, "tt": tt, "d": xs.d_of(tt, lam), "height": h, "fwhm": fw})
    k2 = d.get("_ka2"); nk2 = 0
    if k2 is None and d.get("phase") is not None: k2 = _ka2_partners(tt, h, ph, lam)
    if k2 is not None and len(k2) == len(r) and 0 < int(np.sum(k2)) < len(r):          # the same reflections seen with Kα2: one tick, one label and one stored line per reflection
        nk2 = int(np.sum(k2)); r = r[~np.asarray(k2, bool)]
    r = r.dropna(subset=["tt", "height"]); r.attrs["ka2"] = nk2
    r = r[~r["Phase"].str.lower().isin(["", "nan", "none", "unassigned", "-"])]
    r = r[r["height"] > 0.01 * r.groupby("Code")["height"].transform("max")]          # leave out reflections with almost no intensity
    if r["fwhm"].isna().any(): r["fwhm"] = np.nan
    r.attrs["ka2"] = nk2
    return r

def build_peaklist(d, opt, given):
    lam = wavelength(opt, d); r = peaklist_rows(d, lam); rec = d.setdefault("_rec", [])
    known_lam = bool(d.get("lam_file")) or not str(opt.get("wavelength", "Automatic") or "Automatic").startswith("Automatic")
    rec.append(f"d-spacings of the peak list: d = λ / (2 sin θ) with λ = {lam:.5f} Å " + ("(read from the file)" if d.get("lam_file") and str(opt.get("wavelength", "Automatic")).startswith("Automatic") else "(from Analysis settings)" if known_lam
               else "(ASSUMED copper Kα1: the peak list does not give its wavelength. If the pattern was measured with another tube, choose it under Analysis settings > XRD)"))
    if r.attrs.get("ka2"): rec.append(f"{r.attrs['ka2']} rows of the peak list are the Kα2 partners of the other reflections (same d-spacing, the second wavelength of the tube); they are left out, so every reflection has one tick and one label")
    if r.attrs.get("markers"):                        # positions without intensities: leave out the reflections the library knows to be very weak
        lib, _ = library(opt); keep = []; thinned = []
        for c in dict.fromkeys(r["Code"]):
            g = r[r["Code"] == c]; L = lib[(lib["Code"] == c) & (lib["I"] >= 1.5)]
            if len(g) > 120 and len(L) >= 10:
                lt = np.sort(xs.two_theta(L["d"].values, lam)); lt = lt[np.isfinite(lt)]; j = np.clip(np.searchsorted(lt, g["tt"].values), 1, len(lt) - 1)
                near = np.minimum(np.abs(g["tt"].values - lt[j - 1]), np.abs(g["tt"].values - lt[j])) <= 0.06
                if near.sum() >= 10: thinned.append(f"{c} {len(g)} -> {int(near.sum())}"); g = g[near]
            keep.append(g)
        r2 = pd.concat(keep, ignore_index=True); r2.attrs["markers"] = True; r = r2
        if thinned: rec.append("tick rows thinned to the reflections with at least 1.5 % relative intensity in the phase library: " + ", ".join(thinned))
    d["_rows"] = r
    try:                                              # phases of the list that were left out because none of their reflections has a height
        df_ = d.get("_df"); pc_ = next((c for c in df_.columns if re.search(r"(?i)^assign|^phase", str(c))), None) if df_ is not None else None
        if pc_ is not None:
            got_ = {re.sub(r"[_\s]+", " ", str(v)).strip().lower() for v in r["Phase"]}
            miss_ = [v for v in dict.fromkeys(df_[pc_].astype(str)) if v.strip() and v.lower() != "nan" and re.sub(r"[_\s]+", " ", v).strip().lower() not in got_]
            if miss_:
                d["_missing_phases"] = miss_
                rec.append("in the peak list but NOT drawn: " + ", ".join(re.sub(r"_+", " ", v) for v in miss_) + " - every one of its reflections has a calculated "
                           "height of 0 or less, so it has no intensity in this refinement (check its scale factor in HighScore)")
    except Exception: pass
    codes = list(dict.fromkeys(r["Code"])); cs = []; tab = []
    for i, c in enumerate(codes):
        g = r[r["Code"] == c]; tx = np.repeat(g["tt"].values, 3); ty = np.tile([0.0, 1.0, np.nan], len(g)) * np.repeat(g["height"].values, 3); tx[2::3] = np.nan; ty[2::3] = np.nan
        cs.append(curve(f"{c} – {xs.CODE_NAMES.get(c, g['Phase'].iloc[0])}", tx, ty, TICKCOL[i % len(TICKCOL)]))
        s = g.sort_values("height", ascending=False)
        tab.append({"Code": c, "Phase": g["Phase"].iloc[0], "Reflections": len(g), "Strongest at 2theta (deg)": "; ".join(f"{v:.3f}" for v in s["tt"].values[:3]), "Strongest d (A)": "; ".join(f"{v:.4f}" for v in s["d"].values[:3])})
    marks = bool(r.attrs.get("markers"))
    rec.append(f"peak list: {len(r)} reflections of {len(codes)} phase(s), " + ("Bragg positions only (no intensities), drawn as ticks" if marks else f"drawn as sticks with their heights ('{d['height']}')"))
    if opt.get("app_dir") and d.get("phase") is not None and not d.get("_learnt") and not marks:
        lr = r.assign(I=r.groupby("Code")["height"].transform(lambda v: 100 * v / (v.max() or 1)))
        d["_learnt"] = True
        if opt.get("xrd_store", True):
            try:
                new, skip = store_phases(lr, opt, f"peak list with phase assignment ({d.get('name', 'your file')}); λ = {lam:.4f} Å" + ("" if known_lam else " assumed"))
                if new: rec.append("new phases stored for future phase suggestions: " + ", ".join(f"{c} = {nm} ({n} lines)" for c, nm, n in new) + ". They are kept in your own phase store (XRD tools > Phase library)")
                if skip: rec.append("not stored: " + "; ".join(skip))
            except Exception: pass
    if marks:                                         # one row of ticks per phase
        cs = []
        for i, c in enumerate(codes):
            tt = r.loc[r["Code"] == c, "tt"].values; yv = len(codes) - 1 - i; tx = np.repeat(tt, 3); ty = np.tile([yv + 0.15, yv + 0.85, np.nan], len(tt)); tx[2::3] = np.nan
            cs.append(curve(f"{c} – {r.loc[r['Code'] == c, 'Phase'].iloc[0]}", tx, ty, TICKCOL[i % len(TICKCOL)]))
        p = panel("Bragg positions", cs, legend=False, ylim=(0, len(codes))); p["yticks"] = False; p["thin"] = True
        p["rows"] = [(len(codes) - 1 - i + 0.5, f"{c} – {r.loc[r['Code'] == c, 'Phase'].iloc[0]}", TICKCOL[i % len(TICKCOL)]) for i, c in enumerate(codes)]
        return dict(title=d["name"], xname="2θ (°)", panels=[p]), tab, []
    sp = dict(title=d["name"], xname="2θ (°)", panels=[panel(d["t"](d["height"]), cs, legend=True)])
    return sp, tab, []

def build_ftir(d, opt, given):
    nums = d["nums"]; ycol = d["ys"][0]; x, y = _clean(nums[d["x"]].values, nums[ycol].values); o = np.argsort(x); x, y = x[o], y[o]
    auto = "transmit" in d["n"][ycol] or "%t" in str(ycol).lower() or (not "absorb" in d["n"][ycol] and np.median(y) > 0.6 * np.max(y) and np.min(y) >= 0)
    sig = d.get("_ftir_signal") or opt.get("ftir_signal", "Automatic"); trans = auto if sig not in FTIR_SIGNAL[1:] else sig == "Transmittance"      # _ftir_signal: chosen for this graph alone
    d.setdefault("_rec", []).append("signal treated as " + ("transmittance, so bands are labelled at the minima" if trans else "absorbance, so bands are labelled at the maxima")
                                    + (" (my reading of the header and the values; change it under Analysis settings if wrong)" if sig not in FTIR_SIGNAL[1:] else " (your choice)"))
    pk = find_peaks(x, -y if trans else y, max_n=opt.get("max_labels", 15), min_rel=0.03, min_sep=8)
    lab = [(p["pos"], f"{p['pos']:.0f}", float(np.interp(p["pos"], x, y))) for p in pk]
    res = [{"Wavenumber (cm-1)": round(p["pos"], 1), d["t"](ycol): round(float(np.interp(p["pos"], x, y)), 4), "Band": "minimum (transmittance)" if trans else "maximum (absorbance)"} for p in pk]
    pn = panel(d["t"](ycol) if unit_of(ycol, d["units"]) else ("Transmittance (%)" if trans else "Absorbance (a.u.)"), [curve(ycol, x, y, PALETTE[0])])
    if trans:      # labels hang below the minima: mirror, place, mirror back
        sp0 = finish(dict(panels=[panel("", [curve("", x, -y, PALETTE[0])], labels=[(a, t, -b) for a, t, b in lab])]))
        y0m, y1m = sp0["panels"][0]["ylim"]; pn["ylim"] = (-y1m, float(y.max()) + 0.05 * (y.max() - y.min()))
        pn["placed_below"] = [(pos, -py, txt, lx, -ly) for pos, py, txt, lx, ly in sp0["panels"][0]["placed"]]
    else: pn["labels"] = lab
    return dict(title=d["name"], xname="Wavenumber (cm⁻¹)", xrev=True, panels=[pn]), res, []

def build_tga(d, opt, given):
    nums = d["nums"]; mcol = d["mass"]; xt, xm = d["x_temp"], d["x_time"]; rec = d.setdefault("_rec", []); warn = []
    T = nums[xt].values if xt else None; ok = T is not None and np.mean(np.diff(T[np.isfinite(T)]) >= -1e-9) > 0.95
    xcol = xt if ok else (xm or xt); x, m = _clean(nums[xcol].values, nums[mcol].values)
    u = unit_of(mcol, d["units"]); head = f"{mcol} {u}"
    # a unit written in the file decides; the values are only looked at when the file gives no unit
    um = re.search(r"(?<![A-Za-z])(mg|µg|μg|ug|kg|g)(?![A-Za-z])", u) or re.search(r"[\(\[/]\s*(mg|µg|μg|ug|kg|g)\s*[\)\]]?\s*$", str(mcol)); has_pct = "%" in head
    auto = True if has_pct else False if um else bool(90 <= m[0] <= 110 and m.max() <= 110); how = "the unit in the file" if (has_pct or um) else "the values, because the file gives no unit"
    choice = opt.get("tga_mass", "Automatic"); pct = auto if choice not in TGA_MASS[1:] else choice == TGA_MASS[1]
    if choice in TGA_MASS[1:] and (has_pct or um) and pct != auto:
        warn.append(f"the file gives the mass in {'%' if has_pct else um.group(1)}, but Analysis settings > TGA > Mass column is set to '{choice}': your setting was used. Set it to Automatic if that is not intended")
    loss = bool(re.search(r"(?i)loss|verlust", str(mcol))) and "dtg" not in norm(mcol)          # a column of mass LOSS, not of remaining mass
    if loss:
        if pct: mp = 100.0 - m if abs(np.nanmax(m)) >= abs(np.nanmin(m)) else 100.0 + m; ref = "100 % at the start"
        else:
            try: m0 = float(str(opt.get("tga_m0") or (d.get("hash") or {}).get("mass_mg") or "").replace(",", "."))
            except Exception: m0 = float("nan")
            if not (m0 > 0): raise ValueError(f"'{mcol}' is a mass LOSS in {um.group(1) if um else 'an absolute unit'}, and the file does not give the initial sample mass. Type it under Analysis settings > TGA > Initial sample mass, in the same unit")
            mp = 100.0 * (m0 - m) / m0 if abs(np.nanmax(m)) >= abs(np.nanmin(m)) else 100.0 * (m0 + m) / m0; ref = f"the initial sample mass {m0:g} {um.group(1) if um else ''}".strip()
        rec.append(f"'{mcol}' is a mass loss: remaining mass = initial mass - loss, in % of {ref}")
    else:
        mp = m if pct else 100.0 * m / m[0]; ref = "as given" if pct else f"the first data point ({m[0]:.6g} {um.group(1) if um else u or 'file units'})"
    rec.append(("mass taken as % exactly as given in the file" if pct else f"mass converted to % of {ref}") + (f" (decided from {how}" + ("; change it under Analysis settings if wrong)" if not (has_pct or um) else ")") if choice not in TGA_MASS[1:] else " (your choice)"))
    rec.append(f"mass: original unit {'%' if has_pct else um.group(1) if um else 'not given in the file'}; plotted unit %; reference mass (100 %) = {ref}")
    w = max(7, int(len(x) * 0.015) | 1); ms = savgol(mp, w, 2)
    dx = np.gradient(x); dx[dx == 0] = np.nan; dtg = savgol(np.nan_to_num(np.gradient(ms) / dx), w, 2)      # % per x unit
    # the DTG curve that is drawn: natural sign (mass loss = negative), per minute when there is a time column; the instrument's own DTG column when it agrees
    mk = np.isfinite(np.asarray(nums[xcol].values, float)) & np.isfinite(np.asarray(nums[mcol].values, float)); dplot, dun = dtg, f"%/{unit_of(xcol, d['units']) or 'unit'}"
    if xm and xm in nums and "min" in (unit_of(xm, d["units"]) or "min").lower():
        tm = np.asarray(nums[xm].values, float)[mk]; g_ = np.gradient(tm); g_[g_ == 0] = np.nan; dplot = savgol(np.nan_to_num(np.gradient(ms) / g_), w, 2); dun = "%/min"
    icol = next((c for c in nums if "dtg" in norm(c) and c != mcol), None); src_ = "calculated from the mass"
    if icol is not None:
        inst = np.asarray(nums[icol].values, float)[mk]; okk = np.isfinite(inst)
        if okk.sum() > 50 and abs(np.corrcoef(inst[okk], dplot[okk])[0, 1]) > 0.7:
            dplot = savgol(np.nan_to_num(inst) * (1 if np.corrcoef(inst[okk], dplot[okk])[0, 1] > 0 else -1), w, 2); dun = unit_of(icol, d["units"]) or dun; src_ = f"the instrument's own DTG column '{icol}'"
    rec.append(f"DTG drawn as it is (mass loss is negative): {src_}; smoothed lightly for drawing. Peaks and step limits come from the derivative of the smoothed mass (Savitzky-Golay, window {w} points, 2nd order); the TG curve drawn is the measured one")
    pk = find_peaks(x, -dtg, max_n=opt.get("max_labels", 8), min_rel=0.04, k_noise=4, smooth=w, min_sep=(x.max() - x.min()) * 0.02)
    xu = unit_of(xcol, d["units"]) or ("°C" if xcol == xt else ""); res, lab = [], []
    bounds = [x[0]] + [float(x[pk[i]["index"] + int(np.argmin(-dtg[pk[i]["index"]:pk[i + 1]["index"] + 1]))]) for i in range(len(pk) - 1)] + [x[-1]]
    degc = xcol == xt and ok and "C" in xu; steps = []                 # steps: (x from, x to, loss, tag)
    cement = str(opt.get("tga_material") or TGA_MATERIAL[0]).startswith("Cement")          # chemistry is only proposed for a material you declared
    for i, p in enumerate(pk):
        loss = float(np.interp(bounds[i], x, ms) - np.interp(bounds[i + 1], x, ms)); tag = ""
        if degc and cement and not parse_ranges(opt.get("tga_ranges")):            # cement (your choice of material): the DTG peak decides which step is Ca(OH)2 (dehydroxylation) and which CaCO3 (decarbonation)
            tag = "CH" if 400 <= p["pos"] <= 570 else "CC" if 570 < p["pos"] <= 900 else ""
        lab.append((p["pos"], f"{p['pos']:.0f} {xu}".replace("  ", " ") + (f" {tag}" if tag else "") + (f" ({-loss:+.1f} %)".replace("-", "\u2212") if abs(loss) >= 0.3 else ""), float(np.interp(p["pos"], x, dplot))))
        row = {"Event": i + 1, f"DTG peak ({xu})": round(p["pos"], 1), f"From ({xu})": round(bounds[i], 1), f"To ({xu})": round(bounds[i + 1], 1), "Mass loss (%)": round(loss, 2)}
        if tag and loss * TGA_TAGS[tag][1] > 100.0:           # more than the whole sample: this step cannot be that phase alone
            warn.append(f"the step at {p['pos']:.0f} {xu} loses {loss:.1f} %: as {TGA_TAGS[tag][0]} that would be {loss * TGA_TAGS[tag][1]:.0f} % of the sample, which is impossible. No assignment was made; is this a cementitious sample?"); tag = ""
            lab[-1] = (lab[-1][0], re.sub(r" (CH|CC)(?= |$)", "", lab[-1][1]), lab[-1][2])
        if tag: nm_, f_, how_ = TGA_TAGS[tag]; row.update({"Assigned to": nm_, "Content (% of start mass)": round(loss * f_, 2), "Calculation": how_, "Basis of the assignment": "SUGGESTION of the app from the DTG peak temperature (cementitious sample declared by you). Check it before reporting"})
        res.append(row); steps.append((bounds[i], bounds[i + 1], loss, tag))
    res.append({"Event": "total", f"From ({xu})": round(float(x[0]), 1), f"To ({xu})": round(float(x[-1]), 1), "Mass loss (%)": round(float(ms[0] - ms[-1]), 2), "Residual mass (%)": round(float(ms[-1]), 2)})
    rng = parse_ranges(opt.get("tga_ranges")) if (xcol == xt and ok) else []; vl = []
    if rng:
        o = np.argsort(x); xs_, mps = x[o], mp[o]; res = []
        for a, b, tag in rng:
            if a < xs_[0] - 1 or b > xs_[-1] + 1: warn.append(f"the range {a:g}-{b:g} {xu} is outside the measurement and was left out"); continue
            loss = float(np.interp(a, xs_, mps) - np.interp(b, xs_, mps)); row = {f"From ({xu})": a, f"To ({xu})": b, "Mass loss (% of start mass)": round(loss, 3)}
            if tag in TGA_TAGS:
                nm, f, how = TGA_TAGS[tag]; row.update({"Assigned to": nm, "Content (% of start mass)": round(loss * f, 2), "Calculation": how, "Basis of the assignment": "your range and tag (Analysis settings > TGA)"})
            res.append(row); vl += [a, b]
        res.append({f"From ({xu})": round(float(xs_[0]), 1), f"To ({xu})": round(float(xs_[-1]), 1), "Mass loss (% of start mass)": round(float(mps[0] - mps[-1]), 3), "Assigned to": "total", "Residual mass (%)": round(float(mps[-1]), 2)})
        rec.append("mass losses between your fixed limits (" + "; ".join(f"{a:g}-{b:g}" + (f" {t}" if t else "") for a, b, t in rng) + f" {xu}) are the difference of the measured TG curve at the two limits (step method, no tangential baseline correction). "
                   "Basis: mass at the start of the measurement. Every loss inside a range is counted, so Ca(OH)2 and CaCO3 from these ranges are upper estimates")
    else:
        rec.append("mass-loss steps: the limits between events are the DTG minima between neighbouring DTG peaks (found automatically)")
        if not cement: rec.append("no chemical assignment: the steps are measured mass losses only. A temperature alone does not identify a phase. For a cementitious sample choose "
                                  "'Cementitious sample: suggest Ca(OH)2 and CaCO3' under Analysis settings > TGA > Material, or give your own ranges with tags (400-500 CH, 600-800 CC)")
        if any(t_ for *_, t_ in steps): rec.append("cement: the step whose DTG peak lies at 400-570 °C is taken as Ca(OH)2 (CH), the step at 570-900 °C as CaCO3 (CC); contents = mass loss x 4.11 and x 2.274. This is my suggestion from the peak positions: other phases that lose mass in the same step make these upper estimates")
    xn = d["t"](xcol) if unit_of(xcol, d["units"]) else ("Temperature (°C)" if xcol == xt else str(xcol))
    mt = d.get("hash") or {}
    if mt.get("header"):
        gas_ = [f"{c_}: " + (f"{float(np.nanmin(v_)):g}" if float(np.nanmin(v_)) == float(np.nanmax(v_)) else f"{float(np.nanmin(v_)):g} to {float(np.nanmax(v_)):g}") for c_ in nums if re.match(r"(?i)gas flow", str(c_)) for v_ in [np.asarray(nums[c_], float)] if np.isfinite(v_).any()]
        rec.append("conditions from the file header (kept in full in the processing record): " + "; ".join(f"{k_} {v_}" for k_, v_ in (("instrument", mt.get("instrument")), ("sample mass (mg)", mt.get("mass_mg")), ("crucible", mt.get("crucible")),
                   ("reference", mt.get("reference")), ("correction file", mt.get("correction")), ("temperature calibration", mt.get("tempcal")), ("segments", "; ".join(mt.get("segments") or [])), ("gas flows (ml/min)", ", ".join(gas_))) if v_ not in (None, "")))
        rec.append("full header of the file: " + " | ".join(f"{k_} = {v_}" for k_, v_ in mt["header"].items()))
        if mt.get("blocks", 1) > 1: rec.append(f"the export holds {mt['blocks']} data blocks: all were read; the column 'Block' says which block a row is from")
        if mt.get("unread_rows"): warn.append(f"{mt['unread_rows']} data rows of a further block with other columns were NOT read: this kind of export is not supported yet. Export that block on its own")
    ed = 2 * w; dd = dplot.copy(); dd[:ed] = np.nan; dd[-ed:] = np.nan          # the smoothing is unreliable at both ends of the run
    dmin = float(np.nanmin(dd)); dmin = dmin if dmin < 0 else -1.0; mend = float(np.nanmin(ms)); drop = max(100.0 - mend, 1.0)
    ylo = mend - 1.15 * drop; yhi = max(float(np.nanmax(mp)), 100.0) + 0.04 * drop                      # mass in the upper half, DTG in the lower half
    H = -dmin / 0.34; y2lo, y2hi = -0.40 * H, 0.60 * H                                                    # DTG: baseline at 40 % of the height, the deepest dip at 6 %
    info_ = [f"m\u2080 = {mt['mass_mg']:g} mg" if mt.get("mass_mg") else "", f"{mt['rate']:g} K/min" if mt.get("rate") else ""]; info_ = " · ".join(t_ for t_ in info_ if t_)
    tgc = curve("TG", x, mp, (0, 0, 0)); dtc = curve("DTG", x, dd, (200, 0, 0))
    ptg = panel("Mass (%)", [tgc], weight=1.0, legend=False, ylim=(ylo, yhi), vlines=[(v, "") for v in sorted(set(vl))])
    ptg["y2"] = dict(curves=[dtc], yname=f"DTG ({dun})", ylim=(y2lo, y2hi), labels=lab)
    ptg["corner_r"] = [(d["name"] if not mt.get("sample") else mt["sample"], True, (0, 0, 0))] + ([(info_, False, (0, 0, 0))] if info_ else []) + [("TG (left axis)", False, (0, 0, 0)), (f"DTG (right axis)", False, (200, 0, 0))]
    # the same two curves as two stacked panels (used when several TGA files are overlaid)
    split = [panel("Mass (%)", [curve("TG", x, mp, (0, 0, 0))], weight=1.4, legend=False, vlines=[(v, "") for v in sorted(set(vl))]),
             panel(f"DTG (%/{unit_of(xcol, d['units']) or xu or 'unit'})", [curve("DTG", x, np.where(np.isfinite(dd), dtg, np.nan), (200, 0, 0))], weight=1.0, legend=False)]
    which = opt.get("tga_curves", TGA_CURVES[0]); name_ = d["name"] if not mt.get("sample") else mt["sample"]
    if which == TGA_CURVES[1]:                              # the mass curve alone: one y axis, the whole height for it
        ptg = panel("Mass (%)", [tgc], weight=1.0, legend=False, ylim=(mend - 0.08 * drop, max(float(np.nanmax(mp)), 100.0) + 0.04 * drop), vlines=[(v, "") for v in sorted(set(vl))])
        ptg["corner_r"] = [(name_, True, (0, 0, 0))] + ([(info_, False, (0, 0, 0))] if info_ else []); split = split[:1]
        rec.append("only the TG (mass) curve is drawn, as chosen under Analysis settings > TGA > Curves; the DTG peaks and steps are still in the results table")
    elif which == TGA_CURVES[2]:                            # the DTG curve alone: one y axis, with the labels of its peaks
        ptg = panel(f"DTG ({dun})", [dtc], weight=1.0, legend=False, ylim=(1.22 * dmin, -0.85 * dmin), labels=lab, vlines=[(v, "") for v in sorted(set(vl))])
        ptg["corner_r"] = [(name_, True, (0, 0, 0))] + ([(info_, False, (0, 0, 0))] if info_ else []); split = split[1:]
        rec.append("only the DTG curve is drawn, as chosen under Analysis settings > TGA > Curves; the mass losses of the steps are still in the results table")
    sp = dict(title=d["name"], xname=xn, panels=[ptg], split=split, no_title=True, page_in=(6.6, 5.4))
    cont = [(r_["Assigned to"], r_["Content (% of start mass)"]) for r_ in res if r_.get("Assigned to") and r_["Assigned to"] != "total" and r_.get("Content (% of start mass)") is not None]
    foot = []
    tg_ = sorted({t_ for *_, t_ in steps if t_})
    if tg_: foot.append([((0, 0, 0), "   ".join({"CH": "CH = Ca(OH)\u2082 (dehydroxylation)", "CC": "CC = CaCO\u2083 (decarbonation)"}[t_] for t_ in tg_) + "; mass loss of each step in brackets")])
    if foot: sp["footer"] = foot
    return sp, res, warn

def analyze_tga_steps(item, intervals=None, opt=None):
    """Mass loss inside given temperature intervals of a TGA table, on the TG curve the app draws (TG left axis, DTG right axis,
    DTG with its natural sign). intervals: [[from, to], ...] in the unit of the temperature column; None = TGA_PRESET_INTERVALS.
    The item is built again with these intervals, so its graph shows them. Returns {"intervals": [{"from", "to", "mass_loss_pct",
    "dtg_peak_at"}], "total_mass_loss_pct", "residual_mass_pct"}.  Plain arithmetic on the numbers of the file."""
    iv = [(float(a), float(b)) for a, b in (intervals if intervals else TGA_PRESET_INTERVALS)]
    if not iv or any(not (math.isfinite(a) and math.isfinite(b)) or b <= a for a, b in iv): raise ValueError("every interval needs two temperatures, the second higher than the first")
    if getattr(item, "kind", None) != "TGA": raise ValueError("this graph is not a TGA table")
    o = dict(opt or {}); o["tga_ranges"] = ", ".join(f"{a:g}-{b:g}" for a, b in iv); item.build(o, "TGA")
    if item.results is None: raise ValueError("the TGA table gave no result for these intervals")
    r = item.results; lab = (item.spec["panels"][0].get("y2") or {}).get("labels") or item.spec["panels"][0].get("labels") or []; rows = []
    for a, b in iv:
        m = r[(r["From (\u00b0C)"].astype(float).round(6) == round(a, 6)) & (r["To (\u00b0C)"].astype(float).round(6) == round(b, 6))]
        peak = next((float(x_) for x_, _t, _y in lab if a <= float(x_) <= b), None)
        rows.append({"from": a, "to": b, "mass_loss_pct": float(m["Mass loss (% of start mass)"].iloc[0]) if len(m) else None, "dtg_peak_at": peak})
    tot = r[r["Assigned to"].astype(str) == "total"]
    return {"intervals": rows, "total_mass_loss_pct": float(tot["Mass loss (% of start mass)"].iloc[0]) if len(tot) else None, "residual_mass_pct": float(tot["Residual mass (%)"].iloc[0]) if len(tot) else None,
            "ranges_text": o["tga_ranges"]}

def build_psd(d, opt, given):
    nums = d["nums"]; n = d["n"]; cum = next((c for c in d["ys"] if any(k in n[c] for k in ("cum", "passing", "undersize", "q3", "finer"))), None)
    dif = next((c for c in d["ys"] if c != cum), None); src = cum or dif; x, y = _clean(nums[d["x"]].values, nums[src].values)
    m = x > 0; x, y = x[m], y[m]; o = np.argsort(x); x, y = x[o], y[o]
    if cum is None and np.all(np.diff(y) >= -1e-9) and y[-1] > 0.9 * y.max() and y[0] < 0.2 * y.max(): cum, dif = src, None     # looks cumulative
    if cum:
        c = y / y.max() * 100.0 if y.max() > 0 else y
        f = _clean(nums[d["x"]].values, nums[dif].values) if dif else None
        if f: fo = np.argsort(f[0]); fx, fy = f[0][fo], f[1][fo]
        else: fx, fy = x, np.diff(np.concatenate([[0.0], c]))
    else:
        fx, fy = x, y; c = np.cumsum(y); c = c / c[-1] * 100.0
    lx = np.log10(x); res = {}
    for q in (10, 50, 90):
        res[q] = float(10 ** np.interp(q, c, lx)) if c[0] <= q <= c[-1] else float("nan")
    span = (res[90] - res[10]) / res[50] if all(np.isfinite(list(res.values()))) else float("nan")
    u = unit_of(d["x"], d["units"]) or "µm"; vl = [(res[q], f"D{q} = {res[q]:.3g} {u}") for q in (10, 50, 90) if np.isfinite(res[q])]
    rows = [{"Quantity": f"D{q}", "Value": round(res[q], 4), "Unit": u} for q in (10, 50, 90)] + [{"Quantity": "Span (D90-D10)/D50", "Value": round(span, 4), "Unit": ""},
            {"Quantity": "Mode (peak of distribution)", "Value": round(float(fx[int(np.argmax(fy))]), 4), "Unit": u}]
    dn = d["t"](dif) if dif else "Volume (%)"
    two = [panel(dn, [curve("Distribution", fx, fy, PALETTE[0])], legend=False),
           panel("Cumulative (%)", [curve("Cumulative", x, c, PALETTE[1])], vlines=vl, ylim=(0, 118), legend=False)]
    st = d.get("_psd_style") or opt.get("psd_style") or PSD_STYLES[0]          # the usual way: one graph, log size, distribution left, cumulative right
    rec = d.setdefault("_rec", [])
    if st == PSD_STYLES[1]: pans = two
    elif st == PSD_STYLES[2]: pans = [two[1]]
    elif st == PSD_STYLES[3]: pans = [panel(dn, [curve("Distribution", fx, fy, PALETTE[0])], vlines=vl, legend=False)]
    else:
        st = PSD_STYLES[0]
        top_ = float(np.nanmax(fy)) if len(fy) else 1.0
        p0 = panel(dn, [curve("Distribution", fx, fy, PALETTE[0])], vlines=vl, ylim=(0.0, top_ * 1.12 if top_ > 0 else 1.0), legend=False)
        p0["y2"] = dict(curves=[curve("Cumulative", x, c, PALETTE[1])], yname="Cumulative passing (%)", ylim=(0.0, 105.0), labels=[])
        pans = [p0]
    rec.append(f"particle size drawn as: {st.lower()}; logarithmic size axis; D10, D50 and D90 read from the cumulative curve (log interpolation)")
    sp = dict(title=d["name"], xname=f"Particle size ({u})", xlog=True, panels=pans, split=two)
    return sp, rows, []

def _reaction_start(path, x_col):
    """Time (in the file's own time unit) at the 'Reaction start' marker of a TAM export, or None: read with calorimetry.read."""
    if not path or not str(path).lower().endswith((".xlsx", ".xlsm")): return None
    try:
        import calorimetry as cal_
        p_ = cal_.read(path)
        if not p_.get("reaction_row"): return None
        return next((float(t_) for r_, t_, _h in p_["rows"] if r_ == p_["reaction_row"]), None)
    except Exception: return None

def build_calorimetry(d, opt, given):
    """Isothermal calorimetry as in the calorimetry skill (iso-calorimetry-excel-processor):
    Time (h) = (t - t at the 'Reaction start' marker) / 3600 (no marker: the first data point);
    heat flow (mW/g) = heat flow x 1000 / sample mass when the file gives W (mW: / mass), as given when it is already per gram;
    rows before the cutoff (reaction start + exclusion window, 45 min unless you set another) are left out ('Null'): not drawn, not integrated;
    cumulative heat (J/g) = trapezoidal sum from 0 at the first valid row: (q_i + q_i-1)/2 x (t_i - t_i-1) x 3.6 (mW/g x h -> J/g)."""
    nums = d["nums"]; x, y = _clean(nums[d["x"]].values, nums[d["heat"]].values); xu = unit_of(d["x"], d["units"]).lower(); yu = unit_of(d["heat"], d["units"])
    rec = d.setdefault("_rec", []); d.pop("_need", None)
    sec = {"s": 1.0, "sec": 1.0, "min": 60.0, "h": 3600.0, "hr": 3600.0, "hours": 3600.0, "d": 86400.0, "days": 86400.0}.get(xu)
    pw = 1e-3 if re.search(r"mW\s*/\s*g", yu) else 1.0 if re.search(r"(?<!m)W\s*/\s*g", yu) else None        # factor to W/g
    mass = d.get("calo_mass")
    if pw is None and re.fullmatch(r"\s*(m?W)\s*", yu or ""):                      # raw TAM signal (W or mW): per gram only with the sample mass
        if mass: pw = (1e-3 if yu.strip() == "mW" else 1.0) / float(mass); rec.append(f"heat flow in {yu.strip()} divided by the sample mass {float(mass):g} g (your answer) -> mW/g")
        else: d["_need"] = ("calo_mass", f"{d['name']}: the heat flow is in {yu.strip()}, not per gram. Enter the sample mass in grams (heat flow x 1000 / mass gives mW/g, as in your calorimetry skill).")
    pans = [panel(d["t"](d["heat"]), [curve(d["heat"], x, y, PALETTE[0])], legend=False)]; res = []; warn = []
    pk = find_peaks(x, y, max_n=3, min_rel=0.05, min_sep=(x.max() - x.min()) * 0.02)
    pans[0]["labels"] = [(p["pos"], f"{p['pos']:.3g} {xu}".strip(), p["height"]) for p in pk]; pans[0]["vertical"] = False
    res += [{"Quantity": "Heat-flow peak", "Position": round(p["pos"], 4), "Value": round(p["height"], 4)} for p in pk]
    if sec and pw:
        try: excl = max(0.0, float(str(opt.get("calo_excl") if opt.get("calo_excl") not in (None, "") else 45).replace(",", ".")))
        except Exception: excl = 45.0
        try: t0h = max(0.0, float(str(opt.get("calo_from") or 0).replace(",", ".")))       # older setting: start (h) after the first point
        except Exception: t0h = 0.0
        ts = _reaction_start(d.get("_src"), d["x"]); marker = ts is not None
        if ts is None: ts = float(x[0])
        cut = max(ts + excl * 60.0 / sec, float(x[0]) + t0h * 3600.0 / sec)
        th = (x - ts) * sec / 3600.0                                               # Time (h) from the reaction start
        hf = y * pw * 1e3                                                          # mW/g
        ok_ = x >= cut
        q = np.full(len(x), np.nan)
        if ok_.any():
            iv = np.flatnonzero(ok_); inc = 0.5 * (hf[iv][1:] + hf[iv][:-1]) * np.diff(th[iv]) * 3.6
            q[iv] = np.concatenate([[0.0], np.cumsum(inc)])
        else: warn.append(f"the exclusion window ({excl:g} min) is longer than the measurement: no row is left and the cumulative heat is zero")
        hfd = np.where(ok_, hf, np.nan)
        if ok_.sum() > 3:                                                           # only the kept rows are drawn, and their peaks labelled
            pans[0]["curves"] = [curve(d["heat"], x[ok_], y[ok_], PALETTE[0])]
            pk = find_peaks(x[ok_], y[ok_], max_n=3, min_rel=0.05, min_sep=(x.max() - x.min()) * 0.02)
            pans[0]["labels"] = [(p["pos"], f"{p['pos']:.3g} {xu}".strip(), p["height"]) for p in pk]
            res = [r_ for r_ in res if r_["Quantity"] != "Heat-flow peak"] + [{"Quantity": "Heat-flow peak", "Position": round(p["pos"], 4), "Value": round(p["height"], 4)} for p in pk]
        cq = [curve("Cumulative heat", x[ok_], q[ok_], PALETTE[1])] if ok_.any() else [curve("Cumulative heat", x, np.zeros(len(x)), PALETTE[1])]
        mcol_ = next((c for c in nums if c not in (d["x"], d["heat"]) and re.search(r"(?i)cumul|total heat|integral|^heat\b(?!.*flow)", str(c)) and re.search(r"(?i)J\s*/\s*g", f"{c} {unit_of(c, d['units'])}")), None)
        if mcol_ is not None:                                   # the instrument's own cumulative heat: kept and drawn beside the calculated one, never replaced
            xm_, qm_ = _clean(nums[d["x"]].values, nums[mcol_].values); kq = 1e3 if re.search(r"(?i)kJ\s*/\s*g", f"{mcol_} {unit_of(mcol_, d['units'])}") else 1.0
            cq = cq[:1] + [curve(f"as given in the file ({mcol_})", xm_, qm_ * kq, PALETTE[2])]; cq[0]["label"] = "calculated from the heat flow"
            res.append({"Quantity": f"Cumulative heat at end, as given in the file '{mcol_}' (J/g)", "Position": round(float(xm_[-1]), 4), "Value": round(float(qm_[-1] * kq), 3)})
            rec.append(f"the file has its own cumulative heat ('{mcol_}'): it is drawn beside the heat calculated here from the heat flow; both are kept")
        pans.append(panel("Cumulative heat (J/g)", cq, legend=mcol_ is not None))
        qv = q[ok_]; tv = th[ok_]
        for h in [float(v.replace(",", ".")) for v in re.findall(r"\d+(?:[.,]\d+)?", str(opt.get("calo_ages") or ""))]:
            if len(tv) and tv[0] <= h <= tv[-1]: res.append({"Quantity": f"Cumulative heat at {h:g} h (J/g)", "Position": h, "Value": round(float(np.interp(h, tv, qv)), 3)})
            else: warn.append(f"{h:g} h is outside the measurement, so no heat value was given for it")
        if len(qv): res.append({"Quantity": "Cumulative heat at end (J/g)", "Position": round(float(tv[-1]), 4), "Value": round(float(qv[-1]), 3)})
        if len(qv) and qv[-1] < 0: warn.append("negative total heat: check for baseline drift")
        calo_ = dict(t_h=th, hf=hfd, q=q)
        rec.append(f"as in the calorimetry skill: time from the {'Reaction start marker' if marker else 'first data point (no Reaction start marker in the file)'}"
                   + f"; rows before {excl:g} min after it are left out (exclusion window{'; ' + format(t0h, 'g') + ' h start also set' if t0h > 0 else ''})"
                   + "; heat flow in mW/g; cumulative heat = trapezoidal sum from 0 at the first valid row x 3.6 (mW/g x h -> J/g)")
    elif d.get("_need"): warn.append(d["_need"][1])
    else: warn.append("cumulative heat not calculated: time unit (s/min/h) or heat-flow unit (mW/g, W/g, or W/mW with the sample mass) not recognised in the headers")
    sp_ = dict(title=d["name"], xname=d["t"](d["x"]), panels=pans)
    if sec and pw: sp_["_calo"] = calo_
    return sp_, res, warn

def calo_style(spec, members, opt):
    """Calorimetry is drawn like the house figures (G10): heat flow with an inset of the first hours beside cumulative heat, regime labels
    and brackets, and with two or more samples the bar chart of Q at a time. members = [(name, the _calo numbers)]. Regimes and alite
    fractions only from Analysis settings > Calorimetry (or nothing). The older two-panel spec stays for the Origin driver."""
    if TG is None or not members or any(c_ is None for _, c_ in members): return spec
    info = TG.parse_calo_info((opt or {}).get("calo_info"))
    ages = [float(v.replace(",", ".")) for v in re.findall(r"\d+(?:[.,]\d+)?", str((opt or {}).get("calo_ages") or ""))]
    end = min(float(np.nanmax(c_["t_h"])) for _, c_ in members); bar = next((h for h in sorted(ages, reverse=True) if h <= end), None)
    sm = [dict(name=nm, label=nm, regime=(info.get(TG.norm(nm)) or {}).get("regime"), alite=(info.get(TG.norm(nm)) or {}).get("alite"), **c_) for nm, c_ in members]
    try: book = TG.calo_book(sm, bar_at_h=bar, name=spec.get("title") or "calorimetry")
    except Exception: return spec
    spec.update(figtype="G10", figtype_name=TG.TYPES["G10"][0], _book=book)
    try: spec["origin_specs"], spec["origin_note"] = TG.origin_specs("G10", book)
    except Exception: pass
    return spec

def _segments(T, t=None, tsec=None):
    """Heating, cooling and isothermal parts of a temperature programme in the order they were measured:
    [(first index, last index, 'heating' | 'cooling' | 'isothermal', rate in K/min or None)]."""
    n = len(T); w = max(5, int(n * 0.01) | 1); Ts = savgol(T, w, 2) if n > 3 * w else np.asarray(T, float); dT = np.gradient(Ts)
    thr = 0.1 * float(np.nanpercentile(np.abs(dT), 90)) if n > 3 else 0.0; k = np.where(dT > thr, 1, np.where(dT < -thr, -1, 0))
    runs = []; i0 = 0
    for i in range(1, n + 1):
        if i == n or k[i] != k[i0]: runs.append([i0, i - 1, int(k[i0])]); i0 = i
    short = max(5, n // 100); j = 0
    while len(runs) > 1 and j < len(runs):               # a very short run is noise at a turning point: it joins its neighbour
        if runs[j][1] - runs[j][0] + 1 < short:
            m = j - 1 if j > 0 else j + 1; runs[m][0] = min(runs[m][0], runs[j][0]); runs[m][1] = max(runs[m][1], runs[j][1]); runs.pop(j); j = 0; continue
        j += 1
    out = []
    for a, b, kk in runs:
        if out and out[-1][2] == kk: out[-1][1] = b; continue
        out.append([a, b, kk])
    res = []
    for a, b, kk in out:
        rate = None
        if t is not None and tsec and b > a and t[b] > t[a]: rate = float((T[b] - T[a]) / ((t[b] - t[a]) * tsec / 60.0))
        res.append((a, b, {1: "heating", -1: "cooling", 0: "isothermal"}[kk], rate))
    return res

def _dsc_events(xT, y, tt, max_n=6):
    """Thermal events of one heating or cooling segment. A straight baseline is drawn between the two limits of each event
    (where the smoothed signal has become flat again); onset and endset are where the tangents at the steepest points of the
    two flanks meet that baseline; the area is integrated against time. Returns a list of dictionaries."""
    n = len(y)
    if n < 40: return []
    w = max(7, int(n * 0.015) | 1); ys = savgol(y, w, 2); o = 1 if xT[-1] >= xT[0] else -1; rngy = float(np.nanmax(ys) - np.nanmin(ys)) or 1.0
    line = np.interp(np.arange(n), [0, n - 1], [np.median(ys[:w]), np.median(ys[-w:])]); out = []; dy = np.gradient(ys)
    for sgn in (1, -1):
        for p in find_peaks(xT[::o], (sgn * (ys - line))[::o], max_n=max_n, min_rel=0.05, k_noise=6, smooth=w, min_sep=abs(xT[-1] - xT[0]) * 0.02):
            i = int(np.argmin(np.abs(xT - p["pos"]))); flat = 0.04 * float(np.nanmax(np.abs(dy[max(0, i - n // 6):i + n // 6 + 1])) or 1.0); need = max(3, w // 2)
            a = i
            while a > need and not np.all(np.abs(dy[a - need:a]) < flat): a -= 1
            b = i
            while b < n - need - 1 and not np.all(np.abs(dy[b + 1:b + need + 1]) < flat): b += 1
            a = max(0, a - need // 2); b = min(n - 1, b + need // 2)
            if b - a < 6: continue
            base = np.interp(np.arange(a, b + 1), [a, b], [ys[a], ys[b]]); net = sgn * (y[a:b + 1] - base); ip = a + int(np.argmax(sgn * (ys[a:b + 1] - base)))
            if not (a < ip < b) or float(np.max(sgn * (ys[a:b + 1] - base))) < 0.03 * rngy: continue
            if ip < 0.03 * n: continue                       # the first moments of a segment are the start-up of the instrument, not an event of the sample
            def meet(lo, hi):                                # tangent at the steepest point of a flank, met with the baseline
                if hi - lo < 2: return None
                jj = lo + int(np.argmax(np.abs(dy[lo:hi + 1]))); sl = dy[jj] / ((xT[min(jj + 1, n - 1)] - xT[max(jj - 1, 0)]) / 2.0 or 1.0)
                bs = (ys[b] - ys[a]) / ((xT[b] - xT[a]) or 1.0)
                if abs(sl - bs) < 1e-12: return None
                xv = (ys[a] - bs * xT[a] - ys[jj] + sl * xT[jj]) / (sl - bs); return float(xv) if min(xT[a], xT[b]) <= xv <= max(xT[a], xT[b]) else None
            area = float(np.sum(0.5 * (net[1:] + net[:-1]) * np.abs(np.diff(tt[a:b + 1])))) if tt is not None else None
            out.append(dict(sign=sgn, a=a, b=b, ip=ip, peak=float(xT[ip]), height=float(sgn * (ys[ip] - base[ip - a])), onset=meet(a, ip), endset=meet(ip, b), area=area, x0=float(xT[a]), x1=float(xT[b]), ytop=float(y[ip])))
    out.sort(key=lambda e: e["a"]); keep = []
    for e in out:                                        # one event per place: the stronger of two that overlap
        if keep and e["a"] < keep[-1]["b"] and (e["sign"] == keep[-1]["sign"] or min(e["b"], keep[-1]["b"]) - e["a"] > 0.5 * min(e["b"] - e["a"], keep[-1]["b"] - keep[-1]["a"])):
            if e["height"] > keep[-1]["height"]: keep[-1] = e
            continue
        keep.append(e)
    return keep

def build_dsc(d, opt, given):
    """Heat flow against temperature (DSC, or the DSC signal of a simultaneous TG-DSC run), with the segments of the
    temperature programme kept in the order they were measured."""
    nums = d["nums"]; rec = d.setdefault("_rec", []); warn = []; res = []; hc = d["heat"]; xt = d.get("x_temp"); xm = d.get("x_time"); mt = d.get("hash") or {}
    cols = [c for c in dict.fromkeys([xt, xm, hc]) if c]; a = pd.DataFrame({c: pd.to_numeric(pd.Series(np.asarray(nums[c])), errors="coerce") for c in cols}).dropna()      # the order of the measurement is kept
    if len(a) < 10: raise ValueError("fewer than 10 rows with a temperature (or time) and a heat-flow value")
    T = a[xt].values if xt else None; t = a[xm].values if xm else None; y = a[hc].values; yu = unit_of(hc, d["units"]) or "".join(re.findall(r"[\(\[]([^\)\]]*)[\)\]]", str(hc))[:1]).strip(); xu = (unit_of(xt, d["units"]) or "°C") if xt else ""
    tu = (unit_of(xm, d["units"]) or "").lower() if xm else ""; tsec = {"s": 1.0, "sec": 1.0, "min": 60.0, "h": 3600.0, "hr": 3600.0}.get(tu)
    ex = str(mt.get("exo") or "").strip(); me = re.search(r"(?i)exo\w*[\s:=]*(up|down|\^|↑|↓)", f"{hc} {yu}")
    exo = "down" if ex.startswith("-") else "up" if ex in ("1", "+1", "1.0") else ("up" if me and me.group(1).lower() in ("up", "^", "↑") else "down" if me else None)
    rec.append("exothermic direction: " + (f"{exo} (" + ("from the file header, EXO = " + ex if ex else "from the column name") + ")" if exo else "NOT given in the file, so peaks are reported as upward or downward, not as endothermic or exothermic"))
    segs = _segments(T, t, tsec) if T is not None else [(0, len(y) - 1, "isothermal", None)]; moving = [g for g in segs if g[2] != "isothermal"]
    if T is None or not moving: raise ValueError("the temperature does not change in this table, so this is not a DSC scan. Choose the graph type Calorimetry (heat flow against time) or XY")
    # joule per gram needs W/g (= mW/mg); mW needs the sample mass; microvolt is an uncalibrated signal
    yn = re.sub(r"\s", "", yu); perg = 1.0 if re.fullmatch(r"(?i)mW/mg|W/g", yn) else 1e-3 if re.fullmatch(r"(?i)mW/g", yn) else None; m0 = mt.get("mass_mg")
    if perg is None and re.fullmatch(r"(?i)mW", yn) and m0: perg = 1.0 / float(m0); rec.append(f"heat flow in mW divided by the sample mass of the file header ({m0:g} mg) for the enthalpies")
    aunit = "J/g" if perg else (f"{yu or 'signal'}·s" if (tsec or mt.get("rate")) else f"{yu or 'signal'}·{xu}")
    cs = []; lab = []; cnt = {"heating": 0, "cooling": 0, "isothermal": 0}; colours = {"heating": [(200, 0, 0), (230, 120, 0), (150, 0, 90)], "cooling": [(0, 60, 200), (0, 150, 190), (60, 0, 150)]}
    for (i0, i1, kind_, rate) in segs:
        cnt[kind_] += 1; nm = f"{kind_} {cnt[kind_]}"; rate_ = rate if rate is not None else (mt.get("rate") if kind_ == "heating" and len(moving) == 1 else None)
        res.append({"Segment": nm, f"From ({xu})": round(float(T[i0]), 1), f"To ({xu})": round(float(T[i1]), 1), "Rate (K/min)": None if rate_ is None else round(abs(float(rate_)), 2),
                    "Duration": None if t is None else f"{t[i1] - t[i0]:.4g} {tu}", "Points": int(i1 - i0 + 1)})
        if kind_ == "isothermal": continue
        xs_, ys_ = T[i0:i1 + 1], y[i0:i1 + 1]
        tt = t[i0:i1 + 1] * tsec if (t is not None and tsec) else (np.abs(xs_ - xs_[0]) / abs(float(rate_)) * 60.0 if rate_ else None)        # seconds
        cs.append(curve(nm + (f" ({abs(rate_):.3g} K/min)" if rate_ else ""), xs_, ys_, colours[kind_][(cnt[kind_] - 1) % 3]))
        for k_, e in enumerate(_dsc_events(xs_, ys_, tt, max_n=min(6, int(opt.get("max_labels") or 6))), 1):
            dirn = ("exothermic" if (e["sign"] > 0) == (exo == "up") else "endothermic") if exo else ("upward peak" if e["sign"] > 0 else "downward peak")
            area = None if e["area"] is None else abs(e["area"]) * (perg or 1.0)
            res.append({"Segment": nm, "Event": k_, "Direction": dirn, f"Onset ({xu})": None if e["onset"] is None else round(e["onset"], 1), f"Peak ({xu})": round(e["peak"], 1),
                        f"Endset ({xu})": None if e["endset"] is None else round(e["endset"], 1), f"Limits ({xu})": f"{e['x0']:.1f} to {e['x1']:.1f}",
                        f"Area ({aunit})": None if area is None else float(f"{area:.4g}"), "Basis": "SUGGESTED limits; straight baseline between them; " + ("integrated against time" if tt is not None else "not integrated: the file gives no time and no heating rate") + ". Review before reporting"})
            if cnt[kind_] == 1: lab.append((e["peak"], f"{e['peak']:.0f} {xu}".replace("  ", " "), e["ytop"]))
    rec.append("temperature programme: " + "; ".join(f"{r_['Segment']} {r_[f'From ({xu})']:g} to {r_[f'To ({xu})']:g} {xu}" + (f" at {r_['Rate (K/min)']:g} K/min" if r_.get("Rate (K/min)") else "") for r_ in res if "Event" not in r_) + ". Segments are drawn in the order they were measured; isothermal holds are listed, not drawn")
    rec.append(f"events: found on the lightly smoothed signal (Savitzky-Golay), limits where the signal is flat again, straight baseline between the limits; onset and endset by the tangent method; areas in {aunit}"
               + ("" if perg else " - NOT an enthalpy in J/g: the heat-flow unit is not W/g or mW/mg" + ("" if m0 else " and the file gives no sample mass")) + ". These are suggestions for you to review, not a validated evaluation")
    if mt.get("header"):
        rec.append("conditions from the file header: " + "; ".join(f"{k_} {v_}" for k_, v_ in (("instrument", mt.get("instrument")), ("sample mass (mg)", mt.get("mass_mg")), ("crucible", mt.get("crucible")), ("reference", mt.get("reference")),
                   ("correction file", mt.get("correction")), ("temperature calibration", mt.get("tempcal")), ("sensitivity calibration", mt.get("sensitivity"))) if v_ not in (None, "")))
    yname = (d["t"](hc) if unit_of(hc, d["units"]) else f"Heat flow ({yu})" if yu else str(hc)) + (f"   exo {'↓' if exo == 'down' else '↑'}" if exo else "")
    p = panel(yname, cs, labels=lab, legend=len(cs) > 1); p["vertical"] = False
    return dict(title=f"{mt['sample']} DSC" if mt.get("sample") else d["name"], xname=d["t"](xt) if unit_of(xt, d["units"]) else "Temperature (°C)", panels=[p]), res, warn

def _stats(x, y):
    ux = np.unique(x); n = np.array([(x == v).sum() for v in ux]); m = np.array([y[x == v].mean() for v in ux])
    s = np.array([y[x == v].std(ddof=1) if (x == v).sum() > 1 else np.nan for v in ux]); return ux, m, s, n

def build_xy(d, opt, given):
    nums = d["nums"]; rec = d.setdefault("_rec", []); ser = d.get("series"); xcol = d["x"]
    if ser is not None:
        ycol = d["ys"][0]; yname = d["t"](ycol)
        groups = [(str(s), *_clean(nums[xcol][ser == s].values, nums[ycol][ser == s].values)) for s in pd.unique(ser)]
        rec.append(f"one curve per value of the column '{d.get('series_col')}'")
    else:
        ys = d["ys"][:10]; yname = d["t"](ys[0]) if len(ys) == 1 else ""
        groups = [(c, *_clean(nums[xcol].values, nums[c].values)) for c in ys]
    groups = [g for g in groups if len(g[1])]
    if not d.get("no_replicates") and any(len(np.unique(g[1])) < len(g[1]) for g in groups) and all(len(g[1]) < 400 for g in groups):      # repeated x = replicates
        cs, pts, segs, res = [], [], [], []; cap = 0.012 * (float(np.ptp(np.concatenate([g[1] for g in groups]))) or 1.0)
        stats = {g[0]: _stats(g[1], g[2]) for g in groups}
        ref = next((g[0] for g in groups if re.search(r"(?i)(^|[^a-z])(ref|reference|control)", str(g[0]))), None)
        refm = dict(zip(stats[ref][0], stats[ref][1])) if ref is not None else {}
        for i, (name, x, y) in enumerate(groups):
            col = PALETTE[i % len(PALETTE)]; ux, m, s, n = stats[name]; sx, sy = [], []
            cs.append(curve(str(name), ux, m, col, kind="linesymbol")); pts.append(curve("_" + str(name), x, y, col, kind="scatter"))
            for v, mm, ss, nn in zip(ux, m, s, n):
                if np.isfinite(ss) and ss > 0:
                    sx += [v, v, np.nan, v - cap, v + cap, np.nan, v - cap, v + cap, np.nan]; sy += [mm - ss, mm + ss, np.nan, mm - ss, mm - ss, np.nan, mm + ss, mm + ss, np.nan]
                row = {"Series": str(name), d["t"](xcol): v, "n": int(nn), "Mean": round(float(mm), 4), "SD": round(float(ss), 4) if np.isfinite(ss) else "",
                       "95 % CI (±)": round(t95(nn - 1) * ss / math.sqrt(nn), 4) if np.isfinite(ss) else "", "Individual values": "; ".join(f"{q:g}" for q in y[x == v])}
                if ref is not None and name != ref and refm.get(v): row[f"% of {ref}"] = round(100 * mm / refm[v], 1)
                res.append(row)
            if sx: segs.append((np.array(sx, float), np.array(sy, float), col))
        p = panel(yname, cs + pts); p["segs"] = segs; note = "Large symbols and line: mean. Bars: ± 1 standard deviation. Small symbols: individual values."
        rec.append("values measured at the same x are replicates: large symbols and line = mean, bars = ± 1 standard deviation (n − 1), small symbols = the individual values; 95 % CI = t x SD / sqrt(n)")
        if ref is not None: rec.append(f"'% of {ref}' compares each mean with the mean of '{ref}' at the same x")
        return dict(title=d["name"], xname=d["t"](xcol), panels=[p], note=note), res, []
    few = max(len(g[1]) for g in groups) < 40
    cs = [curve(nm, x, y, PALETTE[i % len(PALETTE)], kind="linesymbol" if few else "line") for i, (nm, x, y) in enumerate(groups)]
    spans = [float(np.ptp(c["y"])) or 1e-300 for c in cs]
    if ser is None and len(cs) > 1 and max(spans) / min(spans) > 20: pans = [panel(d["t"](c["label"]), [c], legend=False) for c in cs]
    else: pans = [panel(yname, cs)]
    res, warn = [], []
    if given:
        lab, warn = snap_labels(cs[0]["x"], cs[0]["y"], given, tol=0.004 * float(np.ptp(cs[0]["x"]))); pans[0]["labels"] = lab; pans[0]["vertical"] = False
    elif opt.get("label_peaks"):
        pk = find_peaks(cs[0]["x"], cs[0]["y"], max_n=opt.get("max_labels", 15)); pans[0]["labels"] = [(p["pos"], f"{p['pos']:.4g}", p["height"]) for p in pk]
        res = [{"Peak position": round(p["pos"], 4), "Height": round(p["height"], 4)} for p in pk]
    return dict(title=d["name"], xname=d["t"](xcol), panels=pans), res, warn

BUILDERS = {"XRD": build_xrd, "Fit (observed + calculated)": build_fit, "XRD peak list": build_peaklist, "FTIR": build_ftir, "TGA": build_tga, "DSC": build_dsc, "Particle size": build_psd, "Calorimetry": build_calorimetry, "XY": build_xy}
def _figtype_builder(d, opt, given): raise ValueError("gallery graph types are built from the whole workbook (Item.build)")
for _k in GALLERY_KINDS: BUILDERS[_k] = _figtype_builder

# ============================================================================= charts for any table, guesses and suggestions
CHARTS = ["Bars", "Histogram", "Box plot", "Contour map", "Phase assemblage (stacked areas)", "Phase amounts (lines)", "Phase assemblage (stacked bars)", "Change against the first row", "Pore solution (logarithmic)"]
OWN_LAYOUTS = ["Automatic", "All in one graph", "One panel per signal"]

def _colnum(nums, c): return pd.to_numeric(pd.Series(np.asarray(nums[c])), errors="coerce").values.astype(float)

def build_chart(d, opt, cu):
    """Bar chart, histogram, box plot or contour map of any table (chosen on the tab 'Own graph' or among the suggestions)."""
    if str(cu.get("style")) == PORE_CHART:
        if not d.get("pore"): raise ValueError("this graph is for a pore solution: a table with at least three columns named after dissolved elements or ions (Na, K, Ca, Si, Al, S, OH ...)")
        return build_pore(d, opt, cu)
    if str(cu.get("style")) in THERMO_CHARTS:
        if not d.get("thermo"): raise ValueError("this kind of graph is for results of a thermodynamic calculation: a table with a temperature (or one row per composition) and columns named after phases")
        return build_thermo(d, opt, cu)
    nums = d["nums"]; rec = d.setdefault("_rec", []); st = str(cu.get("style")); xcol = d["x"]; ys = [c for c in (d.get("ys") or []) if c != xcol][:10]; t = d["t"]; ser = d.get("series"); res = []; warn = []
    if not ys: raise ValueError("choose at least one column for y")
    if st == "Bars":
        if ser is not None: cats = [str(s) for s in pd.unique(pd.Series(ser).dropna())]; key = pd.Series(ser).astype(str).values; names = cats
        else:
            xv = _colnum(nums, xcol); cats = [v for v in pd.unique(xv[np.isfinite(xv)])]; key = xv; names = [f"{v:g}" for v in cats]
        if len(cats) > 40: raise ValueError(f"{len(cats)} different x values are too many for bars (40 at most). Draw this table as lines or symbols")
        cs = []; segs = []; w = 0.8 / len(ys); top = 0.0; low = 0.0
        for j, c in enumerate(ys):
            y = _colnum(nums, c); m = []; sd = []; n = []
            for k in cats:
                v = y[(key == k) & np.isfinite(y)]; m.append(float(np.mean(v)) if len(v) else np.nan); sd.append(float(np.std(v, ddof=1)) if len(v) > 1 else np.nan); n.append(len(v))
            pos = np.arange(1, len(cats) + 1) - 0.4 + w * (j + 0.5); col = ([(170, 170, 170)] + list(PALETTE[1:]))[j % len(PALETTE)]; b = curve(t(c), pos, m, col, kind="bar"); b["barw"] = w * 0.92; cs.append(b)
            sx, sy = [], []
            for p_, mm, ss in zip(pos, m, sd):
                if np.isfinite(ss) and ss > 0: sx += [p_, p_, np.nan, p_ - 0.15 * w, p_ + 0.15 * w, np.nan]; sy += [mm - ss, mm + ss, np.nan, mm + ss, mm + ss, np.nan]
            if sx: segs.append((np.array(sx), np.array(sy), (0, 0, 0)))
            top = max(top, float(np.nanmax(np.array(m) + np.nan_to_num(sd)))); low = min(low, float(np.nanmin(np.array(m) - np.nan_to_num(sd))))
            res += [{"Category": nm, "Column": str(c), "n": k_, "Mean": round(mm, 5), "SD": "" if not np.isfinite(ss) else round(ss, 5)} for nm, k_, mm, ss in zip(names, n, m, sd)]
        p = panel(t(ys[0]) if len(ys) == 1 else "", cs, ylim=(low * 1.08 if low < 0 else 0.0, top * 1.1 or 1.0), legend=len(ys) > 1); p["segs"] = segs
        rec.append("bar chart: one bar per " + (f"value of '{d.get('series_col')}'" if ser is not None else f"value of '{xcol}'") + "; several rows with the same value are averaged, the line on a bar is ± 1 standard deviation (n − 1)")
        return dict(title=d["name"], xname=str(d.get("series_col") or "") if ser is not None else t(xcol), panels=[p], xcats=list(zip(range(1, len(cats) + 1), names)), _xlim=(0.4, len(cats) + 0.6)), res, warn
    if st == "Histogram":
        c = ys[0]; v = _colnum(nums, c); v = v[np.isfinite(v)]
        if len(v) < 8: raise ValueError("a histogram needs at least 8 values")
        q1, q3 = np.percentile(v, [25, 75]); h = 2 * (q3 - q1) / len(v) ** (1 / 3); nb = int(np.clip(np.ceil((v.max() - v.min()) / h) if h > 0 else 10, 5, 40)); cnt, edges = np.histogram(v, bins=nb)
        b = curve("_" + t(c), 0.5 * (edges[1:] + edges[:-1]), cnt, (170, 170, 170), kind="bar"); b["barw"] = float(edges[1] - edges[0]) * 0.96
        res = [{"From": round(float(a), 5), "To": round(float(e), 5), "Count": int(k)} for a, e, k in zip(edges[:-1], edges[1:], cnt)]
        res.append({"From": "n", "To": len(v), "Count": ""}); res.append({"From": "mean", "To": round(float(v.mean()), 5), "Count": ""}); res.append({"From": "SD", "To": round(float(v.std(ddof=1)), 5), "Count": ""})
        rec.append(f"histogram of '{c}': {len(v)} values in {nb} classes of equal width (Freedman-Diaconis rule, between 5 and 40 classes)")
        w_ = float(edges[1] - edges[0]); return dict(title=d["name"], xname=t(c), panels=[panel("Count", [b], ylim=(0.0, float(cnt.max()) * 1.1), legend=False)], _xlim=(float(edges[0]) - 0.5 * w_, float(edges[-1]) + 0.5 * w_)), res, warn
    if st == "Box plot":
        if ser is not None: groups = [(str(s), _colnum(nums, ys[0])[pd.Series(ser).astype(str).values == str(s)]) for s in pd.unique(pd.Series(ser).dropna())]; yname = t(ys[0])
        else: groups = [(str(c), _colnum(nums, c)) for c in ([xcol] if cu.get("box_x") else []) + ys]; yname = ""
        groups = [(n_, v[np.isfinite(v)]) for n_, v in groups]; groups = [g for g in groups if len(g[1]) >= 4]
        if not groups: raise ValueError("a box needs at least 4 values")
        bx, by, mx, my, ox_, oy_ = [], [], [], [], [], []
        for i, (n_, v) in enumerate(groups, 1):
            q1, md, q3 = np.percentile(v, [25, 50, 75]); iq = q3 - q1; lo_ = float(v[v >= q1 - 1.5 * iq].min()); hi_ = float(v[v <= q3 + 1.5 * iq].max()); a, b_ = i - 0.3, i + 0.3
            bx += [a, b_, b_, a, a, np.nan, i, i, np.nan, i, i, np.nan, i - 0.15, i + 0.15, np.nan, i - 0.15, i + 0.15, np.nan]; by += [q1, q1, q3, q3, q1, np.nan, q3, hi_, np.nan, q1, lo_, np.nan, hi_, hi_, np.nan, lo_, lo_, np.nan]
            mx += [a, b_, np.nan]; my += [md, md, np.nan]; out = v[(v < lo_) | (v > hi_)]; ox_ += [i] * len(out); oy_ += list(out)
            res.append({"Group": n_, "n": len(v), "Minimum": float(v.min()), "Q1": float(q1), "Median": float(md), "Q3": float(q3), "Maximum": float(v.max()), "Mean": round(float(v.mean()), 5), "SD": round(float(v.std(ddof=1)), 5), "Outside the whiskers": len(out)})
        cs = [curve("_box", bx, by, (0, 0, 0)), curve("_median", mx, my, (224, 0, 0))] + ([curve("_outside", ox_, oy_, (0, 0, 0), kind="scatter")] if ox_ else [])
        rec.append("box plot: box = first to third quartile, red line = median, whiskers = the furthest values within 1.5 x the interquartile range, circles = values outside the whiskers")
        return dict(title=d["name"], xname="", panels=[panel(yname, cs, legend=False)], xcats=[(i, n_) for i, (n_, _) in enumerate(groups, 1)], _xlim=(0.4, len(groups) + 0.6)), res, warn
    if st == "Contour map":
        if len(ys) < 2: raise ValueError("a contour map needs three columns: x, y and the value z")
        x, y, z = _colnum(nums, xcol), _colnum(nums, ys[0]), _colnum(nums, ys[1]); k = np.isfinite(x) & np.isfinite(y) & np.isfinite(z); x, y, z = x[k], y[k], z[k]
        if len(z) < 6 or len(np.unique(x)) < 2 or len(np.unique(y)) < 2: raise ValueError("a contour map needs at least 6 points that are spread in x and in y")
        p = panel(t(ys[0]), [curve("_points", x, y, (90, 90, 90), kind="scatter")], legend=False); p["contour"] = dict(x=x, y=y, z=z, zname=t(ys[1])); i = int(np.argmax(z)); j = int(np.argmin(z))
        res = [{"Quantity": "highest " + t(ys[1]), t(xcol): float(x[i]), t(ys[0]): float(y[i]), "Value": float(z[i])}, {"Quantity": "lowest " + t(ys[1]), t(xcol): float(x[j]), t(ys[0]): float(y[j]), "Value": float(z[j])}]
        rec.append(f"contour map of '{ys[1]}' over '{xcol}' and '{ys[0]}': 12 colour steps, interpolated linearly between the {len(z)} measured points (triangulation); the grey circles are the measured points")
        warn.append("the contour map is drawn by the app (preview and publication files). In Origin you get the measured points; for the map there, select the three columns in the workbook and choose Plot > Contour")
        return dict(title=d["name"], xname=t(xcol), panels=[p]), res, warn
    raise ValueError(f"unknown chart '{st}'")

# ============================================================================= thermodynamic calculations (phase amounts from FactSage, GEMS, Thermo-Calc ...)
THERMO_CHARTS = ["Phase assemblage (stacked areas)", "Phase amounts (lines)", "Phase assemblage (stacked bars)", "Change against the first row"]
PHASE_RE = re.compile(r"(?i)(liquid|slag|melt|c3s|c2s|c3a|c4af|c12a7|c4a3|alite|belite|aluminate|ferrite|lime|cao|mgo|periclase|spinel|melilite|gehlenite|akermanite|merwinite|wollastonite|rankinite|anhydrite|caso4|arcanite|k2so4|"
                      r"aphthitalite|langbeinite|ye.?elimite|mayenite|ternesite|quartz|sio2|cristobalite|tridymite|mullite|anorthite|hematite|magnetite|wustite|monoxide|olivine|pyroxene|nepheline|leucite|feldspar|\bgas\b|bredigite|perovskite|brownmillerite|hatrurite|larnite|portlandite|ettringite|c-s-h|csh|calcite|monosulf|hydrotalcite|hydrogarnet|pore solution|ca\d*(si|al|fe|mg)\w*o\d+|\bmeo|c2af|c6af2|c6a2f|"
                      r"c-?a-?s-?h|cshq|m-?s-?h|\baft\b|\bafm\b|monocarb|hemicarb|c4a[sc]\w*h\d+|c3ah6|c3\(?a|katoite|str.tlingite|c2ash8|gypsum|brucite|friedel|kuzel|thaumasite|siliceous|aq_gen|aqueous|\bwater\b|solution|unreacted|unhydrated|anhydrous|"
                      r"clinker|fly ash|silica fume|metakaolin|limestone|tailings|\bggbs\b|pores?\b|shrinkage|gel)")
HYDRATE_RE = re.compile(r"(?i)c-?s-?h|cshq|c-?a-?s-?h|portlandite|ettringite|\baft\b|\bafm\b|monosulf|monocarb|hemicarb|hydrotalcite|hydrogarnet|katoite|str.tlingite|pore solution|aq_gen|aqueous|unreacted|unhydrated|gypsum|brucite|m-?s-?h")
PHASE_COLOURS = [(r"pore solution|aq_gen|aqueous|\bwater\b|solution", (170, 215, 245)), (r"c-?s-?h|cshq|c-?a-?s-?h", (120, 150, 190)), (r"portlandite", (40, 90, 200)), (r"ettringite|\baft\b", (220, 40, 40)), (r"monosulf|c4ash", (240, 150, 60)),
                 (r"monocarb|c4ach", (150, 200, 60)), (r"hemicarb|c4ac0", (90, 160, 90)), (r"hydrotalcite", (0, 160, 160)), (r"hydrogarnet|katoite|c3ah6|siliceous", (160, 90, 190)), (r"str.tlingite|c2ash8", (200, 120, 200)), (r"calcite|lime ?stone", (150, 150, 150)), (r"gypsum", (230, 200, 60)),
                 (r"shrinkage|pores?\b", (255, 255, 255)), (r"liquid|slag|melt", (230, 120, 0)), (r"c3s|alite|hatrurite", (0, 60, 200)), (r"c2s|belite|larnite|bredigite", (0, 150, 70)), (r"c3a|aluminate", (150, 0, 150)), (r"c4af|ferrite|brownmillerite", (130, 70, 20)),
                 (r"lime|\bcao\b", (110, 110, 110)), (r"mgo|periclase", (0, 150, 160)), (r"\bgas\b", (200, 200, 200)), (r"anhydrite|caso4|k2so4|arcanite|aphthitalite|langbeinite", (200, 170, 0))]
SPARE_COLOURS = [(220, 0, 80), (90, 60, 200), (0, 190, 220), (160, 200, 0), (255, 150, 150), (60, 60, 60), (120, 200, 160), (200, 120, 220)]

TC_FUNC = re.compile(r"(?i)^\s*(np|npm|bpw|bp|vpv|vp)\s*\(\s*([^()]+?)\s*\)\s*$")       # Thermo-Calc: NP(LIQUID), BPW(C3S) ...

def phase_label(c, unit_txt=None):
    """A column name of a thermodynamic program without its unit: 'g-Slag-liq#1' -> 'Slag-liq', 'NP(LIQUID)' -> 'LIQUID'. The name itself is not changed."""
    m_ = TC_FUNC.match(str(c))
    if m_: return re.sub(r"#\d+$", "", m_.group(2)).strip()
    c = re.sub(r"\s*[\(\[]\s*" + re.escape(unit_txt) + r"\s*[\)\]]\s*$", "", str(c)) if unit_txt else c
    s = re.sub(r"(?i)^\s*(g|gram|grams|kg|wt\.?\s*%|mass\s*%|mol|mole|vol\.?\s*%)\s*[-_: ]\s*", "", str(c)); s = re.sub(r"#\d+\s*$", "", s); s = re.sub(r"\s*[\(\[]\s*(g|gram|wt\.?\s*%|mass\s*%|mol|%|vol\.?\s*%)\s*[\)\]]\s*$", "", s, flags=re.I)
    return s.strip(" _-") or str(c)

def _phase_colours(names):
    out = []; spare = 0
    for nm in names:
        col = next((c for rx, c in PHASE_COLOURS if re.search(rx, nm, flags=re.I) and c not in out), None)
        if col is None: col = SPARE_COLOURS[spare % len(SPARE_COLOURS)]; spare += 1
        out.append(col)
    return out

def thermo_info(d, df):
    """Is this table the result of a thermodynamic calculation: amounts of phases against temperature, or for several
    compositions or runs? Returns what was found (mode, x, phases, labels, unit, why) or None."""
    nums = d.get("nums")
    if not nums or len(nums) < 3: return None
    n = d["n"]; cols = list(nums); units = d.get("units") or {}
    low = {str(c).lower(): c for c in cols}
    if any(k.startswith(("si_", "d_")) for k in low) and ({"sim", "soln", "state", "step"} & set(low)):          # PHREEQC selected output
        ph = [c for c in cols if "d_" + str(c).lower() in low and not str(c).lower().startswith(("si_", "d_", "m_", "la_", "tot_", "k_"))]
        if ph:
            xo = next((low[k] for k in ("time", "step", "dist_x", "reaction", "temp", "temp(c)") if k in low and np.nanstd(_colnum(nums, low[k])) > 0), None)
            if xo is not None:
                return dict(mode="T", x=xo, phases=ph, labels=None, unit="mol", unit_txt=None, hyd=False, axis="ordered",
                            why=f"PHREEQC selected output: {len(ph)} equilibrium phase(s) ({', '.join(str(c) for c in ph[:4])}) against '{xo}'")
    tcol = next((c for c in cols if not PHASE_RE.search(str(c)) and ("temp" in n[c].split("|")[0] or re.match(r"(?i)^\s*t\s*[\(\[/]?\s*(°?\s*c|k|deg)", str(c)) or re.fullmatch(r"(?i)\s*t\s*", str(c)))), None)
    ph = [c for c in cols if c != tcol and (PHASE_RE.search(str(c)) or TC_FUNC.match(str(c))) and not re.search(r"(?i)total|sum|ratio|modul|lsf|activity|enthalp|entrop|gibbs|\bcp\b", str(c))]
    rest = [c for c in cols if c != tcol]
    if len(ph) < 2 or len(ph) < 0.4 * len(rest): return None
    head = " ".join(f"{c} {units.get(c, '')}" for c in ph)
    unit = "wt%" if re.search(r"(?i)wt\.?\s*%|mass\s*%", head) else "mol" if re.search(r"(?i)\bmol", head) else "g" if re.search(r"(?i)(^|\s)(g|gram)\s*[-_(\[]|\(g\)|\[g\]", head) else ""
    tot = np.nansum(np.c_[tuple(_colnum(nums, c) for c in ph)], axis=1)
    if not unit and len(tot) and np.all(np.abs(tot - 100) < 1.5): unit = "%"
    texts = [c for c in df.columns if c not in nums]; rows = len(df); T = _colnum(nums, tcol) if tcol is not None else None
    br_ = [re.search(r"[\(\[]([^\(\)\[\]]+)[\)\]]\s*$", str(c)) for c in ph]; same_ = {b.group(1).strip() for b in br_ if b}       # the same unit in brackets behind every phase name, e.g. (cm3/100 g)
    utxt = same_.pop() if all(br_) and len(same_) == 1 else None
    if utxt and re.search(r"(?i)\bg\b|%|cm|ml|mol|vol|wt|kg", utxt): unit = utxt.replace("cm3", "cm³").replace("cm^3", "cm³")
    else: utxt = None
    hyd = any(HYDRATE_RE.search(str(c)) for c in ph)        # a hydrated system (GEMS and the like): 'slag' is then a solid binder, not a liquid
    unit = unit or ("cm³" if re.search(r"(?i)cm.?3|\bml\b|vol", head + " " + " ".join(str(units.get(c, "")) for c in ph)) else "")
    def axis_ok(v): v = v[np.isfinite(v)]; return len(v) >= 6 and len(np.unique(v)) >= 0.8 * rows and bool(np.all(np.diff(v) > 0) or np.all(np.diff(v) < 0))
    xs = [c for c in rest if c not in ph and not PHASE_RE.search(str(c)) and axis_ok(_colnum(nums, c))]
    if T is not None and rows >= 5 and float(np.nanmax(T) - np.nanmin(T)) > 20 and len(np.unique(T[np.isfinite(T)])) >= 0.8 * rows: xs = [tcol] + xs
    pref = lambda c: next((k for k, keys in enumerate((("time", "age", "day", "hour"), ("temp",), ("hydrat", "react", "degree"), ("replac", "content", "dosage", "substit", "addition", "amount", "ratio", "wb", "wc"))) if any(q in n[c] for q in keys)), 9)
    if xs:
        xc = tcol if (tcol in xs and not hyd) else sorted(xs, key=pref)[0]; kind_ = "temperature" if xc == tcol else "ordered"
        return dict(mode="T", x=xc, phases=ph, labels=None, unit=unit, unit_txt=utxt, hyd=hyd, axis=kind_, why=f"an ordered column ('{xc}') and {len(ph)} columns named like phases ({', '.join(phase_label(c, utxt) for c in ph[:4])} ...)")
    if rows > 40: return None
    lab = next((c for c in texts if df[c].astype(str).nunique() == rows), None) or (texts[0] if texts else None)
    xn = next((c for c in rest if c not in ph and not PHASE_RE.search(str(c))), None)
    labels = [str(v).strip() for v in df[lab]] if lab is not None else ([f"{v:g}" for v in _colnum(nums, xn)] if xn is not None else [str(i + 1) for i in range(rows)])
    return dict(mode="runs", hyd=hyd, unit_txt=utxt, x=xn, phases=ph, labels=labels, label_col=str(lab) if lab is not None else (str(xn) if xn is not None else "Run"), unit=unit, fixed_T=None if T is None or not np.isfinite(T).any() else float(np.nanmedian(T)),
                why=f"{rows} rows (compositions or runs) and {len(ph)} columns named like phases ({', '.join(phase_label(c, utxt) for c in ph[:4])} ...)")

def build_thermo(d, opt, cu):
    """Phase amounts from a thermodynamic calculation: against temperature (areas or lines) or per composition / run (stacked bars, lines, change against the first row)."""
    th = d["thermo"]; nums = d["nums"]; rec = d.setdefault("_rec", []); st = str(cu.get("style")); res = []; warn = []; ttl = d.get("_display") or d["name"]
    cm = {str(c): c for c in nums}; ph = [cm[str(c)] for c in (cu.get("ys") or []) if str(c) in cm and cm[str(c)] in th["phases"]] or list(th["phases"])
    Y = np.c_[tuple(np.nan_to_num(_colnum(nums, c)) for c in ph)]; keep = [j for j in range(len(ph)) if np.nanmax(np.abs(Y[:, j])) > 0]; ph = [ph[j] for j in keep]; Y = Y[:, keep]
    if not ph: raise ValueError("every phase column is zero")
    top_ = r"(?i)pore solution|aq_gen|aqueous|\bwater\b|solution|shrinkage|pores?\b|\bgas\b" if th.get("hyd") else r"(?i)liquid|slag|melt|\bgas\b|pore solution"
    last = lambda c: bool(re.search(top_, str(c)))             # the liquid (in a hydrated paste: the pore solution) goes on top of the solids
    first = lambda c: bool(th.get("hyd") and not re.search(r"(?i)c-?s-?h|cshq|portlandite|ettringite|mono|hemi|hydro|str.tl|gypsum|brucite|pore|aq_gen|aqueous|solution", str(c)) and re.search(r"(?i)alite|belite|c3s|c2s|c3a\b|c4af|aluminate|ferrite|clinker|unreacted|unhydrated|anhydrous|slag|fly ash|silica fume|metakaolin|limestone|tailings|ggbs|quartz", str(c)))
    order = [j for j in range(len(ph)) if first(ph[j]) and not last(ph[j])] + [j for j in range(len(ph)) if not first(ph[j]) and not last(ph[j])] + [j for j in range(len(ph)) if last(ph[j])]; ph = [ph[j] for j in order]; Y = Y[:, order]      # unreacted binder at the bottom, hydrates, pore solution on top
    names = [phase_label(c, th.get("unit_txt")) for c in ph]; cols = _phase_colours(names); unit = th.get("unit") or ""; yname = "Phase amount" + (f" ({unit})" if unit else "")
    rec.append(f"read as the result of a thermodynamic calculation: {th['why']}. The numbers are drawn as they are in the file; nothing is calculated. Phase names are the column names without their unit")
    if th["mode"] == "T":
        x = _colnum(nums, th["x"]); k = np.isfinite(x); x, Y = x[k], Y[k]; o = np.argsort(x, kind="stable"); cooling = bool(len(x) > 1 and x[0] > x[-1]); x, Y = x[o], Y[o]; xname = d["t"](th["x"]) if th.get("axis") == "ordered" else "Temperature (K)" if re.search(r"(?i)[\(\[/]\s*k\s*[\)\]]?\s*$|kelvin", f"{th['x']} {unit_of(th['x'], d['units'])}") else "Temperature (°C)"
        xlog = bool(th.get("axis") == "ordered" and re.search(r"(?i)time|age|day|hour", str(th["x"])) and x.min() > 0 and x.max() / x.min() >= 100)          # hydration time over decades: logarithmic axis
        tot = Y.sum(axis=1); tiny = 1e-3 * float(np.nanmax(tot) or 1.0)
        for j, nm in enumerate(names):
            on = Y[:, j] > tiny; i = int(np.argmax(Y[:, j]))
            res.append({"Phase": nm, "Present from": float(x[on].min()) if on.any() else "", "to": float(x[on].max()) if on.any() else "", "Largest amount": round(float(Y[i, j]), 4), "at": float(x[i]), f"At {x[0]:g}": round(float(Y[0, j]), 4), f"At {x[-1]:g}": round(float(Y[-1, j]), 4)})
        if cooling: rec.append("the rows run from high to low (for a temperature: a cooling calculation); the graph is drawn with the axis rising to the right")
        if xlog: rec.append("the time axis is logarithmic, because the times span more than a factor of 100")
        rec.append("'Present from ... to' = the values of the axis at which the phase is more than 0.1 % of the largest total; read from the rows of the file, not interpolated")
        if st == THERMO_CHARTS[1]:
            cs = [curve(nm, x, Y[:, j], cols[j]) for j, nm in enumerate(names)]; return dict(title=ttl, xname=xname, xlog=xlog, panels=[panel(yname, cs, ylim=(0.0, float(Y.max()) * 1.08))]), res, warn
        cum = np.cumsum(Y, axis=1); cs = []
        for j in range(len(names) - 1, -1, -1):                # the top area first, so that in Origin each area lies on the ones below it
            c = curve(names[j], x, cum[:, j], cols[j], kind="area"); c["base"] = cum[:, j - 1] if j else np.zeros(len(x)); cs.append(c)
        rec.append("stacked areas: each phase lies on top of the ones below it, so the height of a band is the amount of that phase and the top line is the total")
        return dict(title=ttl, xname=xname, xlog=xlog, panels=[panel(yname, cs, ylim=(0.0, float(cum[:, -1].max()) * 1.02))], _xlim=(float(x.min()), float(x.max()))), res, warn
    labels = list(th["labels"])[:len(Y)]; n = len(labels); pos = np.arange(1, n + 1.0)
    for i, lb in enumerate(labels): res.append(dict({th.get("label_col", "Run"): lb}, **{nm: round(float(Y[i, j]), 4) for j, nm in enumerate(names)}, Total=round(float(Y[i].sum()), 4)))
    if th.get("fixed_T") is not None: rec.append(f"all rows are at about {th['fixed_T']:g} (temperature column of the file)")
    if st == THERMO_CHARTS[1]:
        cs = [curve(nm, pos, Y[:, j], cols[j], kind="linesymbol") for j, nm in enumerate(names)]
        return dict(title=ttl, xname=str(th.get("label_col") or ""), panels=[panel(yname, cs, ylim=(0.0, float(Y.max()) * 1.08))], xcats=list(zip(range(1, n + 1), labels)), _xlim=(0.5, n + 0.5)), res, warn
    if st == THERMO_CHARTS[3]:
        if n < 2: raise ValueError("a change needs at least two rows")
        D = Y[1:] - Y[0]; m = len(names); w = 0.8 / (n - 1); cs = []
        for i in range(n - 1):
            b = curve(labels[i + 1], np.arange(1, m + 1) - 0.4 + w * (i + 0.5), D[i], ([(170, 170, 170)] + list(PALETTE[1:]))[i % len(PALETTE)], kind="bar"); b["barw"] = w * 0.92; cs.append(b)
        res = [dict({"Phase": nm}, **{f"{labels[i + 1]} - {labels[0]}": round(float(D[i, j]), 4) for i in range(n - 1)}) for j, nm in enumerate(names)]
        rec.append(f"change against the first row: each bar is the amount in that row minus the amount in '{labels[0]}', in the unit of the file")
        lo, hi = float(min(D.min(), 0)), float(max(D.max(), 0)); pad = 0.08 * ((hi - lo) or 1.0)
        return dict(title=ttl, xname="", panels=[panel(f"Change against {labels[0]}" + (f" ({unit})" if unit else ""), cs, ylim=(lo - pad, hi + pad), legend=n > 2)], xcats=list(zip(range(1, m + 1), names)), _xlim=(0.4, m + 0.6)), res, warn
    cum = np.cumsum(Y, axis=1); cs = []
    for j in range(len(names) - 1, -1, -1):                    # the tallest bar first; each shorter one covers its lower part, which gives the stack
        b = curve(names[j], pos, cum[:, j], cols[j], kind="bar"); b["barw"] = 0.62; cs.append(b)
    rec.append("stacked bars: each bar is one row of the file; the height of a coloured part is the amount of that phase")
    return dict(title=ttl, xname=str(th.get("label_col") or ""), panels=[panel(yname, cs, ylim=(0.0, float(cum[:, -1].max()) * 1.18))], xcats=list(zip(range(1, n + 1), labels)), _xlim=(0.4, n + 0.6)), res, warn

ION_RE = re.compile(r"(?i)^\s*\[?\s*(na|k|ca|si|al|s|so4|oh|mg|fe|cl|li|co3|dic|c)\s*(\(?[ivx]+\)?)?\s*[\]\+\-\d]*\s*$")
PORE_CHART = "Pore solution (logarithmic)"

def pore_info(d, df):
    """Is this table a pore solution: concentrations of elements or ions (Na, K, Ca, Si, Al, S, OH ...), perhaps with a pH,
    against time, a replacement level or per mix? Returns what was found or None."""
    nums = d.get("nums")
    if not nums or len(nums) < 3: return None
    units = d.get("units") or {}; cols = list(nums); bare = lambda c: re.sub(r"\s*[\(\[].*$", "", str(c)).strip()
    ions = [c for c in cols if ION_RE.match(bare(c))]; ph = next((c for c in cols if re.fullmatch(r"(?i)ph", bare(c))), None)
    if len(ions) < 3: return None
    head = " ".join(f"{c} {units.get(c, '')}" for c in ions); m = re.search(r"(?i)(mmol\s*/\s*(l|kg)|mol\s*/\s*(l|kg)|µmol\s*/\s*l|\bmm\b|mg\s*/\s*l|\bm\b)", head); unit = m.group(1) if m else ""
    rows = len(df); rest = [c for c in cols if c not in ions and c != ph]
    def axis_ok(v): v = v[np.isfinite(v)]; return len(v) >= 4 and len(np.unique(v)) == len(v) and bool(np.all(np.diff(v) > 0) or np.all(np.diff(v) < 0))
    xc = next((c for c in rest if axis_ok(_colnum(nums, c))), None); texts = [c for c in df.columns if c not in nums]
    lab = next((c for c in texts if df[c].astype(str).nunique() == rows), None)
    labels = None if xc is not None else ([str(v).strip() for v in df[lab]] if lab is not None else [str(i + 1) for i in range(rows)])
    return dict(x=xc, ions=ions, ph=ph, unit=unit, labels=labels, label_col=str(lab) if lab is not None else "Mix", why=f"{len(ions)} columns named like dissolved elements or ions ({', '.join(bare(c) for c in ions[:5])} ...)" + (" and a pH" if ph is not None else ""))

def build_pore(d, opt, cu):
    """Concentrations of the pore solution on a logarithmic axis (they span several decades), the pH in a panel of its own."""
    po = d["pore"]; nums = d["nums"]; rec = d.setdefault("_rec", []); ttl = d.get("_display") or d["name"]; res = []; warn = []
    if po["x"] is not None: x = _colnum(nums, po["x"]); xname = d["t"](po["x"]); xcats = None; xlog = bool(re.search(r"(?i)time|age|day|hour", str(po["x"])) and np.nanmin(x) > 0 and np.nanmax(x) / np.nanmin(x) >= 100)
    else: x = np.arange(1, len(po["labels"]) + 1.0); xname = po["label_col"]; xcats = list(zip(range(1, len(x) + 1), po["labels"])); xlog = False
    cs = []; lo, hi = np.inf, 0.0; below = []
    for j, c in enumerate(po["ions"]):
        y = _colnum(nums, c); k = np.isfinite(x) & np.isfinite(y) & (y > 0)
        if (np.isfinite(y) & (y <= 0)).any(): below.append(str(c))
        if k.sum() < 1: continue
        cs.append(curve(re.sub(r"\s*[\(\[].*$", "", str(c)).strip(), x[k], y[k], PALETTE[j % len(PALETTE)], kind="linesymbol")); lo = min(lo, float(y[k].min())); hi = max(hi, float(y[k].max()))
        res.append({"Species": cs[-1]["label"], "Lowest": float(y[k].min()), "Highest": float(y[k].max()), "First row": float(y[k][0]), "Last row": float(y[k][-1])})
    if not cs: raise ValueError("no concentration above zero")
    p = panel("Concentration" + (f" ({po['unit']})" if po["unit"] else ""), cs); p["ylog"] = True; p["_ylog_lim"] = (10 ** np.floor(np.log10(lo) - 0.05), 10 ** np.ceil(np.log10(hi) + 0.3 + (0.5 * np.log10(hi / lo) if len(cs) > 1 else 0.0))); pans = [p]      # room above the curves for the legend
    rec.append(f"read as a pore solution: {po['why']}. Concentrations are drawn on a logarithmic axis as they are in the file; nothing is calculated")
    if below: warn.append("values of zero or below cannot be shown on a logarithmic axis and are left out: " + ", ".join(below[:6]))
    if po["ph"] is not None:
        y = _colnum(nums, po["ph"]); k = np.isfinite(x) & np.isfinite(y)
        if k.any(): pp = panel("pH", [curve("_pH", x[k], y[k], (0, 0, 0), kind="linesymbol")], weight=0.45, legend=False); pans.append(pp); res.append({"Species": "pH", "Lowest": float(y[k].min()), "Highest": float(y[k].max()), "First row": float(y[k][0]), "Last row": float(y[k][-1])})
    sp_ = dict(title=ttl, xname=xname, xlog=xlog, panels=pans)
    if xcats: sp_.update(xcats=xcats, _xlim=(0.5, len(x) + 0.5))
    return sp_, res, warn

GENERIC_NAME = re.compile(r"(?i)^(col(umn)?\s*\d+|unnamed.*|[xyz]\d*|\d+([.,]\d+)?|v(ar)?\d+|field\s*\d+|[a-z])(_\d+)?$")

def guess_kind(d):
    """A table without column names: what the NUMBERS look like. Returns [(kind, why)] with the most likely first, or [].
    Only the first two columns are judged. This is a guess and is always reported as one."""
    nums = d["nums"]; cols = list(nums)
    if len(cols) < 2 or not all(GENERIC_NAME.match(str(c).strip()) for c in cols) or any(d.get("units", {}).get(c) for c in cols): return []
    x, y = _colnum(nums, cols[0]), _colnum(nums, cols[1]); k = np.isfinite(x) & np.isfinite(y); x, y = x[k], y[k]; n = len(x); out = []
    if n < 20: return []
    dx = np.diff(x); mono = bool(np.all(dx > 0) or np.all(dx < 0)); span = float(abs(x[-1] - x[0])); lo, hi = float(x.min()), float(x.max()); step = float(np.median(np.abs(dx))) if n > 1 else 0.0
    even = mono and step > 0 and float(np.std(np.abs(dx))) < 0.05 * step
    if mono and lo > 0 and 20 <= n <= 400 and np.all(dx > 0):
        r = np.diff(np.log(x))
        if float(np.std(r)) < 0.05 * float(np.mean(r)) and hi / lo > 30 and y.min() >= -0.01 and y.max() <= 100.5:
            out.append(("Particle size", f"the first column grows by a constant factor from {lo:g} to {hi:g} (size classes) and the second lies between 0 and 100 (%)"))
    if mono and 350 <= lo and hi <= 8000 and span >= 1000 and (y.min() > -0.5 and y.max() < 6 or (y.min() >= -1 and 20 < y.max() <= 110)):
        out.append(("FTIR", f"the first column runs from {x[0]:g} to {x[-1]:g} like wavenumbers (cm-1) and the second looks like " + ("absorbance" if y.max() < 6 else "transmittance in %")))
    if even and np.all(dx > 0) and 1 <= lo and hi <= 165 and span >= 15 and 0.002 <= step <= 0.11 and n >= 300 and y.min() > -0.02 * y.max() and y.max() > 3 * max(float(np.median(y)), 1e-12):
        out.append(("XRD", f"the first column goes from {lo:g} to {hi:g} in even steps of {step:g} like 2θ in degrees, and the second has sharp peaks on a low background like counts"))
    if mono and np.all(dx > 0) and 10 <= lo <= 80 and 200 <= hi <= 1700 and n >= 50 and y[0] > 0:
        w = max(5, n // 50) | 1; ysm = np.convolve(y, np.ones(w) / w, mode="valid"); fall = float(np.mean(np.diff(ysm) <= 1e-4 * abs(y[0]))); loss = (y[0] - y.min()) / y[0]
        if fall > 0.85 and 0.002 < loss <= 1.0: out.append(("TGA", f"the first column rises from {lo:g} to {hi:g} like a temperature in °C and the second only falls, by {100 * loss:.1f} % of its start, like a sample mass"))
    return out

def suggest(it, opt=None):
    """Graphs that fit this table, the most likely first: [{title, why, kind, custom}]. Nothing is changed; apply one with
    it.custom = s['custom']; it.build(opt, s['kind'])."""
    if figtype_id(it.kind):                                 # a gallery template: its own type first, then the other gallery types that may fit
        t0 = figtype_id(it.kind)
        return [dict(title=f"Gallery graph {t0} {TG.TYPES[t0][0]}", why=TG.TYPES[t0][1] + " (recognised from the template)", kind=it.kind, custom={})]
    d = it.det; nums = d["nums"]; cols = [c for c in nums]; ser = d.get("series"); out = []; cur = dict(getattr(it, "custom", None) or {})
    x = d.get("x") or d.get("x_temp") or d.get("x_time") or cols[0]; skip = lambda c: any(k in d["n"].get(c, "") for k in SKIP_Y) if d.get("n") else False
    ys = [c for c in (d.get("ys") or cols) if c != x and not skip(c)] or [c for c in cols if c != x]
    xv = _colnum(nums, x); xf = xv[np.isfinite(xv)]; nrow = len(xf); mono = nrow > 2 and bool(np.all(np.diff(xf) > 0) or np.all(np.diff(xf) < 0)); uniq = len(np.unique(xf))
    def add(title, why, kind, custom=None):
        if not any(o["kind"] == kind and o["custom"] == (custom or {}) for o in out): out.append(dict(title=title, why=why, kind=kind, custom=custom or {}))
    base = {"x": str(x), "ys": [str(c) for c in ys[:10]]}
    g = d.get("type_guess") or ([("XRD", "the first column is evenly spaced like 2θ and the table has no column names")] if d.get("guessed") is True else [])
    if it.det["kind"] != "XY":
        add(f"{it.det['kind']}" + (" (guessed)" if g else ""), (g[0][1] if g else "recognised from the column names and units") + ". Drawn with the analysis of this kind of measurement.", it.det["kind"])
        for kind, why in g[1:]: add(f"{kind} (guessed)", why, kind)
    line = "Line" if nrow >= 40 else "Line + symbols"; th = d.get("thermo")
    if d.get("pore"):
        add("Pore solution on a logarithmic axis", "thermodynamic or measured pore solution: " + d["pore"]["why"] + ". The concentrations span decades, so the axis is logarithmic; the pH gets its own panel", "XY", {"style": PORE_CHART})
        add("One panel per species", "each concentration on its own linear scale", "XY", dict(base, ys=[str(c) for c in d["pore"]["ions"][:8]], layout="One panel per signal", style="Line + symbols"))
        return out
    if th:
        why = "thermodynamic calculation: " + th["why"]
        if th["mode"] == "T":
            add("Phase assemblage against " + ("temperature" if th.get("axis") != "ordered" else str(th["x"])), why + ". Each phase as a band on top of the others; the top is the total", "XY", {"style": THERMO_CHARTS[0]})
            add("Phase amounts as lines", "each phase as its own curve; exact values are easier to read", "XY", {"style": THERMO_CHARTS[1]})
            lq = [] if th.get("hyd") else [str(c) for c in th["phases"] if re.search(r"(?i)liquid|slag|melt", str(c))]
            if lq: add("Liquid only", "the amount of liquid (melt) against temperature, for burnability", "XY", {"style": THERMO_CHARTS[1], "ys": lq})
            hy = [str(c) for c in th["phases"] if HYDRATE_RE.search(str(c)) and not re.search(r"(?i)pore solution|aq_gen|aqueous|unreacted|unhydrated", str(c))] if th.get("hyd") else []
            if len(hy) >= 2: add("Hydrates only", "the hydrate phases as lines, without the unreacted binder and the pore solution", "XY", {"style": THERMO_CHARTS[1], "ys": hy})
        else:
            add("Phase assemblage as stacked bars", why + ". One bar per row, the coloured parts are the phases", "XY", {"style": THERMO_CHARTS[2]})
            add("Phase amounts as lines", "each phase as a line across the rows; shows which phase grows or disappears", "XY", {"style": THERMO_CHARTS[1]})
            add("Change against the first row", f"each row minus '{th['labels'][0]}', per phase; for a sensitivity study", "XY", {"style": THERMO_CHARTS[3]})
        return out
    if ser is not None:
        bars = lambda: add("Bars: mean of each group", "one bar per group with ± 1 standard deviation, for comparing groups", "XY", dict(base, style="Bars"))
        if d.get("cat_only"): bars()
        else: add("One curve per group", f"one curve for each value of '{d.get('series_col')}'", "XY")
        if int(pd.Series(ser).value_counts().min()) >= 4: add("Box plot of each group", "median, quartiles and spread of each group", "XY", dict(base, ys=[str(ys[0])], style="Box plot"))
        bars()
    elif mono or nrow < 6:
        if len(ys) > 1:
            add("All signals in one graph", f"{len(ys[:10])} curves on a common y axis; good when they have the same unit and size", "XY", dict(base, layout="All in one graph", style=line))
            add("One panel per signal", "each signal on its own y scale, one under the other, sharing the x axis; good when sizes differ", "XY", dict(base, layout="One panel per signal", style=line))
        add("Line" if nrow >= 40 else "Line with symbols", f"'{ys[0]}' against '{x}'", "XY", dict(base, ys=[str(ys[0])], style=line))
        if nrow <= 200: add("Symbols only", "every measured point as a symbol, no joining line; honest for few or scattered points", "XY", dict(base, ys=[str(ys[0])], style="Symbols"))
        if len(xf) and xf.min() > 0 and xf.max() / xf.min() >= 100: add("Logarithmic x axis", f"x spans {xf.max() / xf.min():.0f} times from smallest to largest", "XY", dict(base, style=line, xlog=True))
        if uniq <= 25: add("Bars", f"{uniq} x values: one bar each", "XY", dict(base, style="Bars"))
    else:                                                  # the first column is not an ordered axis: the columns are variables measured together
        c3 = [str(c) for c in cols if not skip(c)]; v1 = _colnum(nums, cols[0]); v2 = _colnum(nums, cols[1]) if len(cols) > 1 else v1
        if len(c3) >= 3 and nrow >= 6 and 2 <= len(np.unique(v1[np.isfinite(v1)])) < nrow and len(np.unique(v2[np.isfinite(v2)])) >= 2:
            add(f"Contour map of {c3[2]}", f"'{c3[2]}' as colours over '{c3[0]}' and '{c3[1]}' (their values repeat, as on a grid)", "XY", dict(x=c3[0], ys=[c3[1], c3[2]], style="Contour map"))
        cA, cB = (c3 + [str(x), str(ys[0])])[:2] if len(c3) >= 2 else (str(x), str(ys[0]))
        add("Symbols: one column against another", f"'{cB}' against '{cA}', every row a point, no joining line; shows whether the two go together", "XY", dict(x=cA, ys=[cB], style="Symbols", raw=True))
        if nrow >= 8: add("Box plot of the columns", "median, quartiles and spread of each column side by side", "XY", dict(base, style="Box plot", box_x=True))
        if nrow >= 20: add(f"Histogram of {ys[-1]}", f"how the {nrow} values of '{ys[-1]}' are distributed", "XY", dict(base, ys=[str(ys[-1])], style="Histogram"))
        if uniq <= 25: add("Bars", f"{uniq} different values of '{x}': one bar each, rows with the same value averaged with ± 1 SD", "XY", dict(base, style="Bars"))
        if uniq == nrow: add("Line", "the rows joined in the order of x", "XY", dict(base, ys=[str(ys[0])], style=line))
    tf_ = GALLERY_FIT.get(getattr(it, "path", None))
    fits_ = {"XRD": ("G01", "G02"), "Fit (observed + calculated)": ("G03",), "TGA": ("G07", "G08"), "DSC": (), "Calorimetry": ("G10",), "Particle size": ("G20",), "FTIR": (), "XRD peak list": ()}
    if tf_ and it.kind in fits_ and tf_[0] not in fits_[it.kind]: tf_ = None          # only a gallery type of the same kind of measurement
    if tf_ and TG is not None and not figtype_id(it.kind):
        add(f"Gallery graph {tf_[0]} {TG.TYPES[tf_[0]][0]}", f"{TG.TYPES[tf_[0]][1]}: {tf_[1]}", f"Gallery: {tf_[0]} {TG.TYPES[tf_[0]][0]}")
    if it.det["kind"] != "XY": add("Plain XY graph", "the columns as they are, without the analysis of the measurement type", "XY", dict(base, ys=[str(ys[0])], style="Line" if nrow >= 40 else "Line + symbols"))
    if cur and not any(o["custom"] == cur for o in out): out.insert(0, dict(title="As it is now", why="your present choice on the tab 'Own graph'", kind=it.kind, custom=cur))
    return out[:8]

def suggestion_item(it, s, opt=None):
    """A copy of the graph drawn as suggestion s (the graph itself is not changed)."""
    import copy
    t = copy.copy(it); t.det = dict(it.det); t.custom = dict(s.get("custom") or {}); t.build(opt or {}, s["kind"]); return t

def suggestion_png(it, s, opt=None, dpi=38):
    """A small picture of suggestion s, as PNG bytes."""
    import io
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = preview_figure(suggestion_item(it, s, opt).spec); FigureCanvasAgg(fig); buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=dpi); return buf.getvalue()

def coerce(d, kind):
    """Re-interpret a detected table as another kind when the user overrides the choice."""
    cols = list(d["nums"]); n = d["n"]; x = d.get("x") or d.get("x_temp") or d.get("x_time") or cols[0]
    rest = [c for c in cols if c != x and not any(k in n[c] for k in SKIP_Y)]; e = dict(d, kind=kind)
    if not rest: raise ValueError("this table has only one usable numeric column")
    if kind == "XRD peak list": raise ValueError("only a table with peak positions and heights (and a phase column) can be a peak list")
    if kind in ("XRD", "FTIR", "XY", "Particle size"): e.update(x=x, ys=rest)
    elif kind == "TGA": e.update(x_temp=d.get("x_temp") or x, x_time=d.get("x_time"), mass=d.get("mass") or rest[0])
    elif kind == "Calorimetry": e.update(x=x, heat=d.get("heat") or rest[0], ys=rest)
    elif kind == "DSC":
        xt_ = d.get("x_temp") or next((c for c in cols if "temp" in n[c]), None); xm_ = d.get("x_time") or next((c for c in cols if "time" in n[c]), None)
        if xt_ is None and xm_ is None: xt_ = x
        e.update(x_temp=xt_, x_time=xm_, heat=d.get("heat") or d.get("dsc") or next(c for c in rest if c not in (xt_, xm_)))
    elif kind.startswith("Fit"):
        if len(rest) < 2: raise ValueError("a fit plot needs an observed and a calculated column")
        e.update(x=x, obs=d.get("obs") or rest[0], calc=d.get("calc") or rest[1], diff=None, back=d.get("back"), esd=d.get("esd"))
    return e

def load_reference(path):
    try:
        r = pd.read_csv(path); return [(str(c), float(t)) for c, t in zip(r.iloc[:, 1], r.iloc[:, 2])]
    except Exception: return []

def key_of(it):
    """A stable name for a graph in the list (used by panel figures and saved sessions)."""
    return f"Combined|{it.name}" if isinstance(it, Combined) else f"{it.path}|{it.name}"

INFO = {}          # path -> {"samples": {key: {...}}, "phases": {key: [...]}, "idmap": {...}}
_INFO_ONLY = set()  # files that hold information sheets but no graphs (they apply to every loaded file)

def _small_table(raw):
    """A plain table (header row + rows) from a raw sheet, also when it is tiny."""
    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    for h in range(min(6, len(raw) - 1)):
        row = raw.iloc[h]
        if sum(isinstance(v, str) for v in row) >= max(2, 0.6 * row.notna().sum()):
            df = raw.iloc[h + 1:].copy(); df.columns = [str(v).strip() for v in row]; return df.reset_index(drop=True)
    return None

def _fnum(v):
    try:
        f = float(v); return f if np.isfinite(f) else None
    except (TypeError, ValueError): return None

def read_info(name, raw, prefix=""):
    """Is this sheet information about the samples (display names, Rwp, amorphous) or their phases (names, wt%, colours)?
    Returns (kind, payload) or None."""
    df = _small_table(raw)
    if df is None or len(df) == 0 or len(df) > 2000: return None
    n = {c: re.sub(r"[^a-z0-9%]", "", c.lower()) for c in df.columns}
    f = lambda *ks: next((c for k in ks for c in df.columns if k in n[c]), None)          # keys in order of preference
    code, mean = f("code"), f("meaning", "identity", "description")
    if code and mean and len(df.columns) <= 4 and f("sample") is None:
        return "idmap", {str(a).strip(): str(b).strip() for a, b in zip(df[code], df[mean]) if pd.notna(a) and pd.notna(b)}
    smp = f("sample", "specimen")
    key = lambda v: norm(clean_name(str(v), prefix))
    phase = f("phasedisplay", "phasename", "phasehighscore", "phase", "mineral", "compound")
    def isnum(c):                                    # numbers in (almost) every filled cell; empty cells are allowed (phase absent)
        v = pd.to_numeric(df[c], errors="coerce"); filled = df[c].notna() & (df[c].astype(str).str.strip() != "")
        return v.notna().sum() >= 1 and v.notna().sum() >= 0.8 * filled.sum()
    wt = next((c for c in df.columns if (any(k in n[c] for k in ("weight", "wt%", "wt", "quant", "massfraction", "amount", "content", "conc", "fraction")) or n[c].endswith("%"))
               and not any(k in n[c] for k in ("weighting", "fwhm", "area", "width", "esd", "error", "sigma", "2theta", "dspacing")) and isnum(c)), None)
    if smp is None:
        if phase is None: return None
        nums_ = [c for c in df.columns if c != phase and isnum(c) and not any(k in n[c] for k in ("esd", "error", "sigma", "2theta", "pos", "dspacing", "height", "fwhm", "area", "count", "intens"))]
        if not nums_ or len(df) > 80: return None
        cd0 = f("labelcode", "code"); out = {}
        cols_ = [wt] if (wt is not None and len(nums_) == 1) else nums_
        for c in cols_:                              # one column per sample (wide table), or a single column for a one-sample file
            k_ = "*" if len(cols_) == 1 and (wt is not None or n[c].endswith("%")) else key(c)
            out[k_] = [dict(name=str(r[phase]).strip(), wt=_fnum(r[c]), code=str(r[cd0]).strip() if cd0 and pd.notna(r[cd0]) else "", colour=(0, 0, 0) if str(r[phase]).lower().startswith("amorph") else None)
                       for _, r in df.iterrows() if pd.notna(r[phase]) and _fnum(r[c]) is not None]
        out = {k_: sorted(v_, key=lambda r: r["name"].lower().startswith("amorph")) for k_, v_ in out.items() if v_}      # amorphous last
        return ("phases", out) if out else None
    if phase is not None and wt is not None:
        role, col, cd = f("role"), f("colour", "color", "hex"), f("labelcode", "code")
        out = {}
        for _, r in df.iterrows():
            if pd.isna(r[smp]) or pd.isna(r[phase]): continue
            c = str(r[col]).strip() if col and pd.notna(r[col]) else ""
            rgbc = tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if re.match(r"^#?[0-9a-fA-F]{6}$", c) else None
            if role and str(r[role]).lower().startswith("amorph"): rgbc = (0, 0, 0)
            out.setdefault(key(r[smp]), []).append(dict(name=str(r[phase]).strip(), wt=_fnum(r[wt]), code=str(r[cd]).strip() if cd and pd.notna(r[cd]) else "", colour=rgbc))
        return "phases", out
    disp, rwpc, amc = f("displayname", "display"), next((c for c in df.columns if n[c].startswith("rwp") and "highscore" not in n[c]), None) or f("rwp"), f("amorph")
    grp = next((c for c in df.columns if n[c] in ("group", "series", "category", "set", "batch")), None)
    fitc = next((c for c in df.columns if n[c].startswith("calculatedcurve") or n[c] in ("fittype", "fit", "model", "method", "refinement")), None)      # what kind of calculated curve this is
    if disp or rwpc or amc or grp:
        out = {}
        for _, r in df.iterrows():
            if pd.isna(r[smp]): continue
            out[key(r[smp])] = dict(display=str(r[disp]).strip() if disp and pd.notna(r[disp]) else "", rwp=_fnum(r[rwpc]) if rwpc else None, amorphous=_fnum(r[amc]) if amc else None,
                                    group=str(r[grp]).strip() if grp and pd.notna(r[grp]) else "", fit=str(r[fitc]).strip() if fitc and pd.notna(r[fitc]) else "")
        return "samples", out
    if phase is not None: return "summary", None
    return None

def clean_name(s, prefix=""):
    """'REAL Quartz' -> 'Quartz', 'C1_Profile' -> 'C1', '2_C1' -> 'C1', upload prefixes removed."""
    s = UP_RE.sub("", str(s)).strip()
    if prefix and s.lower().startswith(prefix.lower()) and len(s) > len(prefix): s = s[len(prefix):].strip(" _-")
    s = TAB_RE.sub("", s); s = _drop_tail_words(s); s = re.sub(r"^\d{1,3}[ _.]+(?=\S)", "", s)          # '2_S1' -> 'S1'; '15-AB-S4' stays, there the number is part of the name
    return s.strip(" _-") or str(s)

TAIL_WORDS = ("rietveld", "refinement", "refined", "profile", "peaks", "peak", "peaklist", "list", "labels", "label", "peaklabels", "pattern", "scan", "bragg", "fit", "fitted",
              "calc", "calculated", "observed", "reflections", "hkl", "xrd")

def _tail_word(t):
    """Is this last word of a file name a description of the content ('Rietveld', 'peak labels') and not part of the sample name?
    Typing slips count too: 'RETVELT' is Rietveld, 'lables' is labels."""
    t = str(t).lower()
    if t in TAIL_WORDS: return True
    if len(t) < 5: return False
    import difflib
    return any(w[0] == t[0] and len(w) >= 5 and difflib.SequenceMatcher(None, t, w).ratio() >= 0.8 for w in TAIL_WORDS)

def _drop_tail_words(s):
    """'S1_RETVELT' -> 'S1', 'S1_peak_lables' -> 'S1'. The first word always stays."""
    parts = re.split(r"([ _-]+)", str(s).strip(" _-"))
    while len(parts) >= 3 and _tail_word(parts[-1]): parts = parts[:-2]
    return "".join(parts)

def apply_info(singles, opt=None):
    """Give every graph the information found in the loaded files: suggested display name, Rwp written in the file,
    amorphous content and the phase table (names, wt%, colours). Rebuilds the graphs that changed."""
    paths = list(dict.fromkeys([s.path for s in singles] + [p for p in INFO if p in _INFO_ONLY]))
    has = {}                                         # which samples each file draws itself
    for s in singles: has.setdefault(s.path, set()).add(norm(s.auto))
    for s in singles:
        k = norm(s.auto); inf, idmap = {}, {}; k2 = norm(clean_name(s.name))          # a file with one sample is named after the file; its sheet name still finds its own rows
        # information from the graph's own file first; from another file only if that file does not draw this sample itself
        for p in [s.path] + [q for q in paths if q != s.path and k not in has.get(q, set())]:
            I = INFO.get(p) or {}
            if not inf and k in (I.get("samples") or {}): inf = dict(I["samples"][k])
            elif not inf and p == s.path and k2 in (I.get("samples") or {}): inf = dict(I["samples"][k2])
            if "phases" not in inf and k in (I.get("phases") or {}): inf["phases"] = I["phases"][k]
            elif "phases" not in inf and p == s.path and k2 in (I.get("phases") or {}): inf["phases"] = I["phases"][k2]
            if "phases" not in inf and "*" in (I.get("phases") or {}) and (p != s.path or getattr(s, "nfile", 1) == 1): inf["phases"] = I["phases"]["*"]
            for c_, v_ in (I.get("idmap") or {}).items(): idmap.setdefault(c_, v_)
        inf.setdefault("phases", None)
        new = (inf, idmap)
        if s.det.get("_info_sig") != repr(new):
            s.det["_info_sig"] = repr(new); s.det["_info"] = inf; s.det["_idmap"] = dict(idmap, **(s.det.get("_idmap_file") or {}))
            s.suggest = inf.get("display") or ""
            if s.spec is not None:
                try: s.build(opt or {}, s.kind)
                except Exception: pass

class Item:
    """One drawable table of a file."""
    def __init__(self, path, det, given):
        self.path, self.det, self.given = path, det, given; self.kind = det["kind"]; self.name = det["name"]; self.sample = ""; self.record = []; self.suggest = ""; self.auto = det["name"]
        self.file = os.path.splitext(os.path.basename(path))[0]; self.spec = self.results = None; self.warnings = []
        self.custom = {}                                   # your own graph: x column, y columns, axis titles, log / reversed x, curve style
    @property
    def title(self): return f"{display_names([self])[0]}  [{self.kind}]   ({self.file} / {self.name})"
    def build_figtype(self, opt, kind):
        """A gallery graph type: drawn from the whole workbook by gallery_graphs (labels only from the file, formulas shown)."""
        tid = figtype_id(kind); bk = self.det.get("_figtype_book")
        if bk is None or bk[0] != self.path: bk = (self.path, TG.read_book(self.path)); self.det["_figtype_book"] = bk
        book = bk[1]; self.kind = kind; self.det["_display"] = display_names([self])[0]
        from matplotlib.figure import Figure; from matplotlib.backends.backend_agg import FigureCanvasAgg
        f_ = Figure(figsize=(TG.FIG_W, TG.FIG_H), dpi=40); FigureCanvasAgg(f_); self.det.pop("_need", None)
        try: res = TG.draw(tid, book, f_)                     # tables and notes of the drawing (formulas, inputs)
        except TG.NeedInput as e:                             # an answer is missing (e.g. which row is t0): the window asks, nothing is assumed
            self.det["_need"] = (e.key, str(e)); res = TG.Result(); res.notes.append("waiting for your answer: " + str(e))
        try: specs, note = TG.origin_specs(tid, book) if "_need" not in self.det else ([], "")
        except TG.NeedInput: specs, note = [], ""
        if specs: sp_ = dict(specs[0][1])
        else:
            ds_ = next(iter(book.data_sheets().values())); xs_ = np.arange(max(2, len(ds_)), dtype=float)
            sp_ = finish(dict(title=book.name, xname="", panels=[panel("", [curve("_", xs_, xs_ * 0, (255, 255, 255))], legend=False)]))
        sp_.update(figtype=tid, figtype_name=TG.TYPES[tid][0], origin_specs=specs, origin_note=note, title=f"{book.name} {TG.TYPES[tid][0]}", _book=book)
        self.det["_figtype_res"] = res
        self.spec = sp_; tabs = list(res.tables.items())
        self.results = tabs[0][1] if tabs else None; self.extra = {re.sub(r"[^A-Za-z0-9]+", "_", k_).strip("_"): v_ for k_, v_ in tabs[1:]}
        self.warnings = [self.det["_need"][1]] if self.det.get("_need") else []; why = self.det.get("_figtype_why", "")
        self.record = [f"table read as {kind} (" + ("your choice" if why == "" else f"recognised: {why}") + ")"] + list(res.notes) + ([f"Origin: {note}"] if note else [])
        return self

    def build(self, opt=None, kind=None):
        k_ = kind if kind and kind != "Automatic" else None
        if TG is not None and figtype_id(k_ or self.det.get("kind")): return self.build_figtype(opt or {}, k_ or self.det["kind"])
        opt = opt or {}; changed = bool(kind and kind != "Automatic" and kind != self.det["kind"]); self.det["_display"] = display_names([self])[0]
        if changed: det = coerce(self.det, kind); self.kind = kind
        else: det = self.det; self.kind = det["kind"]
        cu = getattr(self, "custom", None) or {}
        if not cu and det.get("cat_only") and self.kind == "XY": cu = {"style": "Bars"}          # groups and numbers without an x axis: bars
        if not cu and det.get("pore") and self.kind == "XY": cu = {"style": PORE_CHART}          # concentrations of a pore solution
        if not cu and det.get("thermo") and self.kind == "XY": cu = {"style": THERMO_CHARTS[0] if det["thermo"]["mode"] == "T" else THERMO_CHARTS[2]}      # phase amounts of a thermodynamic calculation
        own = bool(cu) and self.kind == "XY"
        if own:                                            # any table of numbers, drawn the way you chose
            det = dict(det); cm = {str(c): c for c in det["nums"]}
            if str(cu.get("x")) in cm: det["x"] = cm[str(cu["x"])]
            ys = [cm[str(c)] for c in (cu.get("ys") or []) if str(c) in cm and cm[str(c)] != det["x"]]
            det["no_replicates"] = bool(cu.get("raw"))          # every row as its own point, also when x values repeat
            if ys and str(cu.get("style")) not in THERMO_CHARTS and str(cu.get("style")) != PORE_CHART: det["ys"] = ys; det["series"] = det.get("series") if str(cu.get("style")) in CHARTS else None      # bars and boxes keep the groups of the table
            elif det["x"] in (det.get("ys") or []): det["ys"] = [c for c in det["ys"] if c != det["x"]]
        det["_rec"] = []
        if own and str(cu.get("style")) in CHARTS: sp, res, warn = build_chart(det, opt, cu)
        else:
            if self.kind == "Calorimetry": det["_src"] = self.path                  # the Reaction start marker is read from the file itself
            sp, res, warn = BUILDERS[self.kind](det, opt, self.given)
        if own and str(cu.get("style")) not in CHARTS and not any(p_.get("segs") for p_ in sp["panels"]):
            cv_ = [c_ for p_ in sp["panels"] for c_ in p_["curves"]]
            if cu.get("layout") == OWN_LAYOUTS[2] and len(cv_) > 1: sp["panels"] = [panel(det["t"](c_["label"]) if c_["label"] in det["nums"] else str(c_["label"]), [c_], legend=False) for c_ in cv_]
            elif cu.get("layout") == OWN_LAYOUTS[1] and len(sp["panels"]) > 1: sp["panels"] = [panel("", cv_)]
        if own:
            if cu.get("xtitle"): sp["xname"] = str(cu["xtitle"])
            if cu.get("ytitle"): [p_.__setitem__("yname", str(cu["ytitle"])) for p_ in (sp["panels"] if len(sp["panels"]) == 1 else sp["panels"][:1])]
            if cu.get("xrev"): sp["xrev"] = True
            st_ = {"Line": "line", "Symbols": "scatter", "Line + symbols": "linesymbol"}.get(str(cu.get("style") or ""))
            if str(cu.get("style")) in CHARTS: cu = dict(cu, xlog=False)
            for p_ in sp["panels"]:
                for c_ in p_["curves"]:
                    if cu.get("xlog"):
                        k_ = c_["x"] > 0; c_["x"], c_["y"] = c_["x"][k_], c_["y"][k_]
                    if st_ and not str(c_["label"]).startswith("_"): c_["kind"] = st_
            if cu.get("xlog"): sp["xlog"] = True; p_ = sp["panels"][0]; p_["labels"] = [l_ for l_ in (p_.get("labels") or []) if l_[0] > 0]
            det["_rec"].append("your own graph: columns, titles and axis type as you chose them on the tab 'Own graph'")
        # settings that hold for every kind of graph: pointers, zoomed inset, page orientation
        sp.setdefault("arrows", str(opt.get("pointers") or POINTERS[0]).startswith("Arrow")); sp["label_mult"] = label_mult(opt)
        if not self.kind.startswith(("XRD", "Fit")) and not sp.get("xlog") and sp.get("panels"):
            xs_ = np.concatenate([c_["x"] for c_ in sp["panels"][0]["curves"]]); xs_ = xs_[np.isfinite(xs_)]; rng_ = parse_inset(opt, xs_) if len(xs_) else None
            if rng_: sp["panels"][0]["inset"] = dict(xlim=rng_); det["_rec"].append(f"zoomed inset of {rng_[0]:g}-{rng_[1]:g} on the x axis: the same data on its own y scale")
        if not landscape(opt) and not sp.get("page_in"): sp["page_in"] = (LANDSCAPE[1], LANDSCAPE[0])
        if self.kind.startswith("Fit") and getattr(self, "note", ""): sp["note"] = "Calculated curve: " + self.note
        used = [f"{k} = '{det[k]}'" for k in ("x", "x_temp", "x_time", "mass", "obs", "calc", "heat") if det.get(k) is not None] + (["y = " + ", ".join(f"'{c}'" for c in det["ys"][:10])] if det.get("ys") else [])
        gs_ = (det.get("type_guess") or ([("XRD", "the first column is evenly spaced like 2θ and the second looks like counts")] if det.get("guessed") is True else None)) if not changed else None
        if gs_ and self.kind == gs_[0][0]: warn = list(warn) + [f"this table has no column names, so its type is a GUESS from the numbers: {self.kind}, because {gs_[0][1]}. Check it; if it is wrong, change the graph type or pick another one under Suggestions"]
        self.record = [f"table read as {self.kind} " + ("(your choice)" if changed else "(GUESSED from the numbers alone, the table has no column names: " + gs_[0][1] + ")" if gs_ and self.kind == gs_[0][0] else "(recognised from the column names and values)"), "columns used: " + "; ".join(used)] + det["_rec"]
        dcn_ = (xs.META.get(self.path) or {}).get("decimal_commas")
        if dcn_: self.record.insert(0, dcn_)
        if self.det.get("_software"):                      # the modelling program (and database) you named: on the figure and in the record
            sw_ = str(self.det["_software"]) + (f", {self.det['_database']}" if self.det.get("_database") else "")
            sp["note"] = ((sp["note"] + " ") if sp.get("note") else "") + f"Calculated with {sw_}."; self.record.append(f"calculated with {sw_} (as you stated)")
        if det.get("_typed_labels"): self.record.append("peak labels you typed in the assistant (your own assignment, not from a file): " + ", ".join(det["_typed_labels"][:40]))
        self.extra = det.get("_extra", {}) if self.kind.startswith(("XRD", "Fit")) else {}
        if not self.kind == "XY": sp["title"] = display_names([self])[0]
        self.spec = finish(sp); self.results = pd.DataFrame(res) if res else None; self.warnings = warn
        if self.kind == "Calorimetry" and sp.get("_calo") is not None: calo_style(self.spec, [(display_names([self])[0], sp["_calo"])], opt)
        if sp.get("_xlim"): self.spec["xlim"] = sp["_xlim"]          # bars and boxes: half a step of room on either side
        for p_ in self.spec["panels"]:                               # a logarithmic y axis keeps the limits it was given
            if p_.get("ylog"): p_["ylim"] = p_["_ylog_lim"]
        return self

GALLERY_SHEETS = ("options", "instructions", "labels", "ranges (optional)", "reference lines", "annotations")
NEW_ONLY = {"G05", "G09", "G11", "G12", "G13", "G14", "G15", "G17", "G19", "G22", "G23", "G24", "C01", "C02"}

def load_figtype(path):
    """A workbook in the layout of a gallery graph type becomes ONE graph of that type. Used for templates (an Options or Instructions
    sheet, or the type tag) and for layouts the older kinds could not draw at all; a plain measurement file keeps its old graphs and
    the fitting gallery type is only offered under Suggestions (so the graphs of existing files do not change)."""
    GALLERY_FIT.pop(path, None)
    if TG is None or not str(path).lower().endswith((".xlsx", ".xlsm", ".csv")): return None
    try:
        book = TG.read_book(path); tid, why = TG.recognise(book)
    except Exception: return None
    if not tid: return None
    sheets = {k.lower() for k in book.sheets} | ({"options"} if book.options else set()) | ({"instructions"} if book.instructions.strip() else set())
    template = bool(sheets & set(GALLERY_SHEETS)) or bool(TG.TAG_RE.search(book.instructions or ""))
    if not (template or tid in NEW_ONLY):
        GALLERY_FIT[path] = (tid, why); return None
    first = next(iter(book.data_sheets().values())); nums = first.apply(pd.to_numeric, errors="coerce")
    kind = f"Gallery: {tid} {TG.TYPES[tid][0]}"
    d = dict(kind=kind, name=TG.TYPES[tid][0], nums=nums, n={c: norm(c) for c in nums.columns}, x=nums.columns[0], ys=list(nums.columns[1:]), units={}, t=lambda c: str(c),
             series=None, cat_only=False, _df=first, _figtype_book=(path, book), _figtype_why=why)
    it = Item(path, d, []); it.auto = book.name; it.nfile = 1
    it.paper_name = it.file if TG.TYPES[tid][0].lower() in it.file.lower() else f"{it.file}_{TG.TYPES[tid][0]}"      # files: <sample or sheet>_<type>
    return [it], [f"  recognised as gallery graph {tid} {TG.TYPES[tid][0]} ({TG.TYPES[tid][1]}): {why}"]

def load_file(path):
    """Return (items to draw, text lines describing what was found)."""
    lf_ = apply_learned(path)                          # a layout the assistant converted before: read the same way, without asking again
    if lf_:
        items_, lines_ = load_file(lf_[0])
        if items_: return items_, lf_[1] + lines_
    import_stamp(path)
    th_ = load_figtype(path)
    if th_: return th_
    dets = []; note = ""; tables = read_tables(path); info = {"samples": {}, "phases": {}, "idmap": {}}; infolines = []; file_lam = None; split_notes = []
    for name, raw in tables:                           # a workbook made by 'Convert files to Excel' remembers the wavelength of the instrument file
        if str(name).lower() == "file_info" and raw.shape[1] >= 2:
            for a, b in zip(raw.iloc[:, 0], raw.iloc[:, 1]):
                if str(a).strip().lower() == "wavelength" and _fnum(b): file_lam = float(_fnum(b))
    for name, raw in tables:
        # a notes sheet that says what the calculated curve is: keep that sentence for the figure
        if raw.shape[1] >= 2 and raw.shape[0] <= 60:
            for a, b in zip(raw.iloc[:, 0], raw.iloc[:, 1]):
                if isinstance(a, str) and isinstance(b, str) and "calculated" in a.lower() and not note: note = b.strip()
        p = parse_table(raw); d0 = detect(name, *p) if p else dict(kind="skip", name=name, why="no numeric data table")
        if p and d0.get("kind") == "skip" and len(tables) == 1 and 3 <= len(p[0]) < 5: d0 = detect(name, *p, min_rows=3)      # a file that is one small table (3 or 4 points, often pasted) is still a graph
        if p and d0.get("kind") in ("XY", "TGA", "DSC", "Calorimetry") and d0.get("nums"):          # phase amounts from a thermodynamic program (FactSage, GEMS ...)
            try:
                th_ = thermo_info(d0, p[0])
                if th_: d0 = dict(d0 if d0["kind"] == "XY" else coerce(d0, "XY"), thermo=th_, series=None, cat_only=False)
                else:
                    po_ = pore_info(d0, p[0])
                    if po_: d0 = dict(d0 if d0["kind"] == "XY" else coerce(d0, "XY"), pore=po_, series=None, cat_only=False)
            except Exception: pass
        if d0.get("kind") == "XY" and d0.get("series") is None and not d0.get("thermo") and not d0.get("pore"):      # no column names: look at the numbers and say what they look like (reported as a guess)
            try:
                gs_ = guess_kind(d0)
                if gs_: d0 = dict(coerce(d0, gs_[0][0]), type_guess=gs_)
            except Exception: pass
        parts, notes_ = split_samples(d0)
        if d0.get("kind") == "TGA" and d0.get("dsc") and d0.get("x_temp"):          # simultaneous TG-DSC: both signals are kept, as two graphs of the same sample
            parts.append(dict(d0, kind="DSC", name=f"{d0['name']} DSC", heat=d0["dsc"])); notes_.append(f"{name}: the table has a mass and a DSC signal (simultaneous TG-DSC). Both are drawn: a TG-DTG graph and a DSC graph")
        sta_ = d0.get("kind") == "TGA" and d0.get("dsc") and d0.get("x_temp")
        what_ = "one XRD pattern per column" if d0.get("kind") == "XRD" else "one graph per column"
        split_notes += [f"  {name}: {what_} ({len(parts)} samples)"] * (len(parts) > 1 and not sta_) + ["  " + q_ for q_ in notes_]
        meta = xs.META.get(path) or {}
        for d1 in parts:
            dets.append(d1); d1["_raw"] = raw
            if p: d1["_df"] = p[0]
            if meta.get("wavelength"): d1["lam_file"] = meta["wavelength"]
            elif file_lam: d1["lam_file"] = file_lam
            elif d1.get("kind") in ("XRD", "Fit (observed + calculated)", "XRD peak list") and d1.get("nums") is not None and d1.get("wide") is None:
                ld_ = _lam_from_d(d1)                      # a table with 2theta and d-spacing columns says which wavelength it was measured with
                if ld_: d1["lam_file"], d1["_ka2"] = ld_
            if meta.get("hash"): d1["hash"] = meta["hash"]
    # the common first word of the sheet names (for example 'REAL ' in 'REAL Quartz', 'REAL S2') is not part of the sample name
    names = [d["name"] for d in dets if d["kind"] not in ("skip", "labels")]
    first = {re.split(r"[ _]", s_, 1)[0] for s_ in names if re.search(r"[ _]", s_)}
    prefix = first.pop() if len(names) >= 2 and len(first) == 1 and all(re.search(r"[ _]", s_) for s_ in names) else ""
    for d in dets:
        if d["kind"] == "labels": continue
        r = read_info(d["name"], d["_raw"], prefix)
        if r is None: continue
        k, payload = r
        if k == "summary": d.update(kind="skip", why="summary table of phases per sample (not drawn)"); continue
        if k == "idmap": info["idmap"].update(payload); infolines.append(f"  {d['name']}: phase names for the label codes"); d.update(kind="skip", why="label key (used for the names of the label codes)"); continue
        for k2, v2 in payload.items(): info[k].setdefault(k2, v2)                    # the first table of a kind wins
        d.update(kind="skip", why=("sample information: display names, Rwp, amorphous content (used, not drawn)" if k == "samples" else "phase table: names, wt%, colours (used for the phase legend, not drawn)"))
    labels = [d for d in dets if d["kind"] == "labels"]; items, lines = [], []
    for L in labels: info["idmap"].update(L.get("idmap") or {})
    INFO[path] = info
    for d in dets:
        if d["kind"] == "skip": lines.append(f"  {d['name']}: {'used as information' if d['why'].startswith(('sample information', 'phase table', 'label key')) else 'skipped'} ({d['why']})"); continue
        if d["kind"] == "labels": lines.append(f"  {d['name']}: label table ({len(d['x'])} labels)"); continue
        got = []
        for L in labels:
            m = np.array((L["sample"].map(lambda v: norm(clean_name(str(v), prefix))) == norm(clean_name(d["name"], prefix))).values, bool) if L["sample"] is not None else np.ones(len(L["x"]), bool)
            if L.get("ftype") is not None: m = m & ~np.array(L["ftype"].astype(str).str.lower().str.contains("stack").values, bool)
            got += [(float(L["x"].iloc[i]), L["text"].iloc[i], None) for i in np.where(m)[0] if pd.notna(L["x"].iloc[i])]
        d["_idmap_file"] = dict(info["idmap"]); d["_idmap"] = dict(info["idmap"]); d.pop("_raw", None)
        it = Item(path, d, sorted(got)); it.note = note; it.nfile = sum(1 for e in dets if e["kind"] not in ("skip", "labels"))
        single = sum(1 for e in dets if e["kind"] not in ("skip", "labels")) == 1
        it.auto = (d.get("hash") or {}).get("sample") or clean_name(it.file, "") if single else clean_name(d["name"], prefix)
        items.append(it)
        lines.append(f"  {d['name']}: {d['kind']}" + (f", {len(got)} labels from the label sheet" if got else "") + (f", wavelength {d['lam_file']} Å from the file" if d.get("lam_file") else ""))
    if not items and (info["samples"] or info["phases"] or info["idmap"]): _INFO_ONLY.add(path); lines.append("  this file holds only information (names, Rwp, wt%); it is used for the graphs of the other files")
    else: _INFO_ONLY.discard(path)
    lines += split_notes
    if (xs.META.get(path) or {}).get("decimal_commas"): lines.insert(0, "  " + xs.META[path]["decimal_commas"])
    if items:
        apply_info(items)                                  # suggested names from this file's information sheets
        lines.append("  names I suggest: " + ", ".join(display_names(items)))
    fits_ = {"XRD": ("G01", "G02"), "Fit (observed + calculated)": ("G03",), "TGA": ("G07", "G08"), "DSC": (), "Calorimetry": ("G10",), "Particle size": ("G20",), "FTIR": (), "XRD peak list": ()}
    if path in GALLERY_FIT and items and all(i.kind in fits_ and GALLERY_FIT[path][0] not in fits_[i.kind] for i in items): GALLERY_FIT.pop(path, None)
    if path in GALLERY_FIT: lines.append(f"  this file also fits gallery graph {GALLERY_FIT[path][0]} {TG.TYPES[GALLERY_FIT[path][0]][0]} ({GALLERY_FIT[path][1]}): see Suggestions")
    return items, lines

# ============================================================================= several files together
MODES = ["Decide for me", "Stack them", "Overlay them", "One page per sample (pattern + fit)", "Keep them separate"]
PAGE_LAYOUTS = ["Decide for me", "Side by side", "One above the other"]
RULES = {   # what "Decide for me" does, and why
    "XRD": ("stack", "stacked with an offset, because overlaid patterns hide each other's peaks"),
    "FTIR": ("stack", "stacked with an offset, the usual way to compare spectra band by band"),
    "Fit (observed + calculated)": ("panels", "one panel per sample, each with its own fit and difference curve"),
    "TGA": ("overlay", "overlaid on common axes, so mass losses can be read against each other"),
    "Particle size": ("overlay", "overlaid on a common size axis, so the distributions can be compared directly"),
    "Calorimetry": ("overlay", "overlaid on a common time axis, so heat flow and total heat can be compared"),
    "DSC": ("overlay", "overlaid on a common temperature axis"),
    "XY": ("overlay", "overlaid on common axes, because they share the same quantities"),
}
MAXN = {"stack": 8, "panels": 6, "overlay": 8}
ORIENTATIONS = ["Landscape", "Portrait"]
FONT_WEIGHTS = ["Bold (as now)", "Normal"]
COLOUR_CHOICES = {"Automatic": None, "Black": (0, 0, 0), "Dark blue": (0, 0, 139), "Blue": (0, 0, 224), "Red": (224, 0, 0), "Dark red": (139, 0, 0),
                  "Green": (0, 128, 0), "Dark grey": (64, 64, 64), "Orange": (230, 120, 0), "Purple": (110, 0, 140)}
LOOK = {"font_weight": FONT_WEIGHTS[0], "text_colour": "Automatic", "curve_colour": "Automatic", "font_scale": 1.0}      # set from Graph settings > Size and look

def look_colour(name):
    """A colour choice of the Look settings: None (Automatic), an (r, g, b) from the list, or a typed #rrggbb."""
    if name in COLOUR_CHOICES: return COLOUR_CHOICES[name]
    m = re.match(r"^#?([0-9a-fA-F]{6})$", str(name or "").strip())
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if m else None

def apply_look(fig, fmt=None):
    """Font weight, text colour, font size and the colour of black curves, as chosen under Size and look - on every figure the app
    draws (preview, publication files). Coloured text and coloured curves (phases, samples, fit colours) keep their colours."""
    from matplotlib.text import Text
    from matplotlib.colors import to_rgb
    bold = str(LOOK.get("font_weight", FONT_WEIGHTS[0])).startswith("Bold"); tc = look_colour(LOOK.get("text_colour")); cc = look_colour(LOOK.get("curve_colour"))
    sc = float(LOOK.get("font_scale") or 1.0)
    if bold and tc is None and cc is None and abs(sc - 1.0) < 1e-9: return fmt_figure(fig, fmt)
    black = lambda c: max(abs(v) for v in to_rgb(c)) < 0.02
    for t in fig.findobj(Text):
        if not t.get_text(): continue
        if not bold and t.get_fontweight() in ("bold", 700, "heavy"): t.set_fontweight("normal")
        if tc is not None and black(t.get_color()): t.set_color(tuple(v / 255 for v in tc))
        if abs(sc - 1.0) > 1e-9: t.set_fontsize(t.get_fontsize() * sc)
    for ax in fig.axes:                                               # the numbers on the axes are made again at every draw: set them here
        kw = {}
        if tc is not None: kw["labelcolor"] = tuple(v / 255 for v in tc)
        if abs(sc - 1.0) > 1e-9:
            try: kw["labelsize"] = ax.xaxis.get_ticklabels()[0].get_fontsize() if ax.xaxis.get_ticklabels() else None
            except Exception: pass
            if not kw.get("labelsize"): kw.pop("labelsize", None)
        if kw: ax.tick_params(axis="both", which="both", **kw)
    if cc is not None:
        for ax in fig.axes:
            leg = ax.get_legend()
            for ln in list(ax.get_lines()) + (list(leg.get_lines()) if leg else []):       # curves, the keys of the legend box and of the legend
                key_ = ln.get_transform() == ax.transAxes or (leg is not None and ln in leg.get_lines())
                if ln.get_linestyle() not in ("None", "") and black(ln.get_color()) and (len(ln.get_xdata()) > 3 or key_): ln.set_color(tuple(v / 255 for v in cc))
    return fmt_figure(fig, fmt)
LANDSCAPE = (11.0, 7.7)                                   # page of a stacked figure in landscape (inches); panels are wide, so labels spread out
def landscape(opt): return not str((opt or {}).get("orientation") or ORIENTATIONS[0]).startswith("Port")
PER_FIG = ["3 per figure (best quality)", "2 per figure", "4 per figure", "All in one figure"]
def max_in(how, opt):
    """most samples in one figure; the user's 'Samples per figure' choice limits it (stacked panels only; overlays keep their group)"""
    if how != "panels": return MAXN[how]
    m = re.match(r"\s*(\d+)", str((opt or {}).get("per_fig") or PER_FIG[0]))
    return min(MAXN[how], int(m.group(1))) if m else MAXN[how]

def sample_names(members):
    """Short, distinct names: the file name when it has one drawable sheet, otherwise the sheet name."""
    per_file = {}
    for m in members: per_file[m.path] = per_file.get(m.path, 0) + 1
    names = [m.file if per_file[m.path] == 1 else m.name for m in members]
    if len(set(names)) < len(names): names = [f"{m.file} / {m.name}" for m in members]
    return names

REP_RE = re.compile(r"(?i)(?:[ _-]+(?:rep(?:licate)?|run|trial|specimen|meas(?:urement)?)[ _-]?\d+|\s*\(\d+\))$")

TAB_RE = re.compile(r"(?i)[ _-]*(profile|bragg|peaks?|peak[ _-]?list|pattern|scan|refinement)$")
UP_RE = re.compile(r"^[0-9a-f]{8}-(?=.)")

def display_names(members):
    """The sample name of each graph: the name you typed; otherwise the display name from an information sheet in your files
    (for example 'Sample A (4 % additive)'); otherwise the file or sheet name cleaned up ('REAL Quartz' -> 'Quartz', 'C1_Profile' -> 'C1')
    without a replicate ending (_rep1, _run2, (3))."""
    out = []
    for m in members:
        if getattr(m, "sample", ""): out.append(m.sample); continue
        if getattr(m, "suggest", ""): out.append(m.suggest); continue
        a = getattr(m, "auto", None) or m.name; out.append(REP_RE.sub("", a) or a)
    return out

def prepare(singles, fresh, opt=None, progress=None):
    """Add newly loaded graphs to the list, building each one only once: peak lists first, then names/amounts and
    the links between peak lists and patterns, then the patterns. Returns (number added, error lines)."""
    opt = opt or {}; errs = []; n0 = len(singles)
    pls = [s for s in fresh if s.kind == "XRD peak list"]; rest = [s for s in fresh if s.kind != "XRD peak list"]; tot = len(fresh); k = 0
    for s in pls:
        k += 1
        if progress: progress(k, tot, s.name)
        try: s.build(opt, getattr(s, "want_kind", None)); singles.append(s)
        except Exception as e: errs.append(f"  {s.file} / {s.name}: {e}")
    pool = singles + rest
    apply_info(pool, opt); _LINK_NEWS.extend(link_xrd(pool, opt, keep=True))
    for s in rest:
        k += 1
        if progress: progress(k, tot, s.name)
        try: s.build(opt, getattr(s, "want_kind", None)); singles.append(s)
        except Exception as e: errs.append(f"  {s.file} / {s.name}: {e}")
    return len(singles) - n0, errs

def link_xrd(singles, opt=None, keep=False):
    """Give every XRD pattern or fit the peak list of the same sample (same sample name), so its labels and tick rows
    use the phases of your own refinement. Returns the lines for the message box."""
    opt = opt or {}; lines = []
    pls = [s for s in singles if s.kind == "XRD peak list" and s.spec is not None]
    targets = [s for s in singles if s.kind in ("XRD", "Fit (observed + calculated)")]
    draws = {}                                       # samples each file draws as a pattern or fit
    for s in targets: draws.setdefault(s.path, set()).add(norm(s.auto))
    def pick(s):
        keys = [k for k in (norm(s.sample), norm(s.auto)) if k]
        cand = [p for p in pls if keys and ({norm(p.auto), norm(p.sample)} & set(keys))]
        same = [p for p in cand if p.path == s.path]
        # a peak list from another file only if that file does not have its own pattern of this sample
        other = [p for p in cand if p.path != s.path and not ({norm(p.auto)} & draws.get(p.path, set()))]
        return (same or other or [None])[0]
    picked = {id(s): pick(s) for s in targets}
    # names that do not match: a peak list nobody asked for and a pattern without a peak list are put together when the listed
    # peaks sit on the peaks of that pattern. Not when you typed different sample names for the two.
    how = {}
    free_pl = [p for p in pls if not any(v is p for v in picked.values()) and p.det.get("_rows") is not None and len(p.det["_rows"]) >= 5]
    free_t = [s for s in targets if picked[id(s)] is None]
    if free_pl and free_t:
        score = {(id(p), id(s)): _pl_agreement(p, s) for p in free_pl for s in free_t if not (p.sample and s.sample and norm(p.sample) != norm(s.sample))}
        for p in free_pl:
            mine = {id(s): score.get((id(p), id(s)), 0.0) for s in free_t}; top = max(mine.values(), default=0.0)
            for s in free_t:
                r_ = mine[id(s)]; rivals = [score.get((id(q), id(s)), 0.0) for q in free_pl if q is not p]
                if r_ >= 0.6 and r_ >= top - 0.02 and all(r_ >= v + 0.1 for v in rivals) and picked[id(s)] is None:
                    picked[id(s)] = p; how[id(s)] = r_
    for s in targets:
        pl = picked[id(s)]; new = pl.det.get("_rows") if pl is not None else None
        if (new is None) != (s.det.get("_peaklist") is None) or (new is not None and new is not s.det.get("_peaklist")):
            s.det["_peaklist"] = new; s.det["_peaklist_from"] = pl.title if pl is not None else None
            s.det["_peaklist_how"] = (f"the peak list and this pattern have different names; they were put together because the listed peaks sit on the peaks of this pattern "
                                      f"(agreement {how[id(s)]:.2f} of 1)") if id(s) in how else None
            if s.spec is not None:                       # not built yet: it will be built once, with the link in place
                try: s.build(opt, s.kind)
                except Exception as e: lines.append(f"  {s.title}: {e}"); continue
            if pl is not None:
                lines.append(f"  {s.file} / {s.name}: phase labels and tick rows from the peak list {pl.file} / {pl.name}" + (f" (the names differ; put together because the listed peaks sit on the peaks "
                             f"of this pattern, agreement {how[id(s)]:.2f} of 1. If that is wrong, type a different sample name for each)" if id(s) in how else ""))
    if not keep: lines = _LINK_NEWS + lines; _LINK_NEWS.clear()          # links made while the files were being read are reported with the next call
    return lines

_LINK_NEWS = []

def _pl_agreement(pl, s):
    """How well the peaks of a peak list sit on the peaks of a pattern: the correlation (0 to 1) between the listed heights and
    the measured intensity above the background, both in steps of 0.1°. Near 1 for the peak list of this very measurement."""
    try:
        d = s.det; nums = d["nums"]; ycol = d.get("obs") or (d.get("ys") or [None])[0]
        x, y = _clean(nums[d["x"]].values, nums[ycol].values); o = np.argsort(x); x, y = x[o], y[o]
        r = pl.det["_rows"]; tt = np.asarray(r["tt"], float); h = np.asarray(r["height"], float)
        if r.attrs.get("markers") or len(x) < 100: return 0.0
        m = (tt >= x[0]) & (tt <= x[-1]) & np.isfinite(h)
        if m.sum() < 5 or m.sum() < 0.5 * len(tt): return 0.0
        step = 0.1; nb = int((x[-1] - x[0]) / step) + 1
        if nb < 30: return 0.0
        bi = np.clip(((x - x[0]) / step).astype(int), 0, nb - 1); obs = np.zeros(nb); np.maximum.at(obs, bi, y)
        w = max(3, int(round(4.0 / step)) | 1); pad = np.pad(obs, w // 2, mode="edge"); base = np.array([pad[i:i + w].min() for i in range(nb)]); obs = obs - base
        sim = np.zeros(nb); np.add.at(sim, np.clip(((tt[m] - x[0]) / step).astype(int), 0, nb - 1), h[m]); sim = np.convolve(sim, [0.25, 0.5, 0.25], mode="same")
        if sim.std() == 0 or obs.std() == 0: return 0.0
        return max(0.0, float(np.corrcoef(sim, obs)[0, 1]))
    except Exception: return 0.0

def _xr(spec):
    a, b = spec["xlim"]; return min(a, b), max(a, b)

def _unit(s):
    m = re.search(r"[\(\[]([^\)\]]*)[\)\]]\s*$", str(s)); return norm(m.group(1).replace("µ", "u").replace("μ", "u")) if m else ""

def _compatible(a, b):
    if a.kind != b.kind or len(a.spec["panels"]) != len(b.spec["panels"]): return False
    if a.kind.startswith("Fit") and a.path != b.path and (getattr(a, "nfile", 1) > 1 or getattr(b, "nfile", 1) > 1): return False   # fits of one workbook stay together
    (a0, a1), (b0, b1) = _xr(a.spec), _xr(b.spec); ov = min(a1, b1) - max(a0, b0); un = max(a1, b1) - min(a0, b0)
    if un <= 0 or ov / un < 0.5: return False
    if _unit(a.spec["xname"]) != _unit(b.spec["xname"]): return False                      # e.g. hours against minutes
    if abs((a.spec.get("lam") or 0) - (b.spec.get("lam") or 0)) > 0.002: return False         # XRD with different X-ray tubes
    if RULES.get(a.kind, ("overlay",))[0] == "overlay" and [_unit(p["yname"]) for p in a.spec["panels"]] != [_unit(p["yname"]) for p in b.spec["panels"]]: return False
    if a.kind == "XY": return norm(a.spec["xname"]) == norm(b.spec["xname"]) and norm(a.spec["panels"][0]["yname"]) == norm(b.spec["panels"][0]["yname"])
    return True

def _average(cvs):
    """Mean and standard deviation of replicate curves on the x grid of the first one (over the range they share)."""
    xs = [np.asarray(c["x"], float) for c in cvs]; lo = max(np.nanmin(v) for v in xs); hi = min(np.nanmax(v) for v in xs)
    g = np.sort(xs[0][(xs[0] >= lo) & (xs[0] <= hi)]); Y = []
    for c in cvs:
        o = np.argsort(c["x"]); Y.append(np.interp(g, np.asarray(c["x"], float)[o], np.asarray(c["y"], float)[o]))
    Y = np.array(Y); return g, Y.mean(0), Y.std(0, ddof=1)

def _summarise(ms, names):
    """Mean and SD of the analysis results of replicates (only when every replicate gave the same rows)."""
    rows, skipped = [], []
    for u in dict.fromkeys(names):
        rs = [m.results for m, nm in zip(ms, names) if nm == u and m.results is not None]
        if len(rs) < 2: continue
        numc = [c for c in rs[0].columns if pd.api.types.is_numeric_dtype(rs[0][c])]; txt = [c for c in rs[0].columns if c not in numc]
        if any(r.shape != rs[0].shape or list(r.columns) != list(rs[0].columns) or not r[txt].astype(str).reset_index(drop=True).equals(rs[0][txt].astype(str).reset_index(drop=True)) for r in rs[1:]):
            skipped.append(u); continue
        A = np.array([r[numc].to_numpy(float) for r in rs])
        same = [j for j in range(len(numc)) if np.all((A[1:, :, j] == A[0, :, j]) | (np.isnan(A[1:, :, j]) & np.isnan(A[0, :, j])))]      # e.g. the fixed range limits
        for i in range(rs[0].shape[0]):
            row = {"Sample": u, "n": len(rs)}; row.update({c: rs[0][c].iloc[i] for c in txt})
            for j, c in enumerate(numc):
                v = A[:, i, j]
                if j in same: row[c] = v[0]
                elif np.isfinite(v).sum() >= 2: row[c + " (mean)"] = round(float(np.nanmean(v)), 4); row[c + " (SD)"] = round(float(np.nanstd(v, ddof=1)), 4)
            rows.append(row)
    return (pd.DataFrame(rows) if rows else None), skipped

class Combined:
    """Several sheets/files of the same kind drawn in one figure."""
    path = ""; file = "Combined"
    def __init__(self, members, how, why, part="", cmap=None, opt=None):
        self.members, self.how, self.why = members, how, why; self.kind = members[0].kind; self.warnings = []; self.spec = self.results = self.summary = None
        self.cmap = cmap or {}; self.opt = opt or {}; self.record = []; self.part = part
        nm_ = "_".join(dict.fromkeys(re.sub(r"\s*\(.*?\)", "", n_) for n_ in display_names(members)))[:40]
        self.name = re.sub(r"[^A-Za-z0-9]+", "_", f"{self.kind.split(' ')[0]}_{how}_{nm_}{part}").strip("_")
        self.label = {"stack": "stacked", "panels": "one panel each", "overlay": "overlaid"}[how]
    @property
    def title(self):
        nm = ", ".join(dict.fromkeys(display_names(self.members))); nm = nm if len(nm) <= 46 else nm[:44] + "…"
        return f"\u2605 Combined: {len(self.members)} x {self.kind}  ({self.label}): {nm}"
    def build(self, opt=None, kind=None):
        opt = opt or self.opt; ms = self.members; names = display_names(ms); s0 = ms[0].spec; n = len(ms); self.warnings = []
        uniq = list(dict.fromkeys(names)); has_rep = len(uniq) < n; local = {}
        for nm_ in uniq:                                  # the sample's own colour, unless another sample of this figure already has it
            c_ = self.cmap.get(nm_, PALETTE[0])
            if c_ in local.values(): c_ = next((q_ for q_ in PALETTE if q_ not in local.values()), c_)
            local[nm_] = c_
        col = lambda nm: local.get(nm, PALETTE[0])
        tags = [f"{nm} #{names[:i + 1].count(nm)}" if names.count(nm) > 1 else nm for i, nm in enumerate(names)]
        avg = has_rep and self.how == "overlay" and self.kind != "XY" and (opt.get("replicates") or REPLICATES[0]) == REPLICATES[0]
        notes = list(dict.fromkeys(m.spec["note"] for m in ms if m.spec.get("note") and not m.kind.startswith(("XRD", "Fit"))))
        if self.how == "panels":
            allc = [c_ for m in ms for p_ in m.spec["panels"] for _, t_, _ in (_codelabs(p_) or []) for c_ in t_.split("+")]
            fitn = list(dict.fromkeys(m.spec["note"].split("Calculated curve:")[-1].strip() for m in ms if "Calculated curve:" in m.spec.get("note", "")))
            if _key(allc): notes.append(_key(allc) + "." + (" " + KEY_NOTE if any(c_.endswith("?") for c_ in allc) else ""))
            notes += ["Calculated curve: " + f_ for f_ in fitn]
        ttl = ", ".join(uniq); base = dict(title=f"{self.kind}: " + ttl if len(ttl) < 70 else f"{self.kind}: {len(uniq)} samples", xname=s0["xname"], xrev=s0.get("xrev"), xlog=s0.get("xlog"))
        self.record = [f"{n} graphs of the kind {self.kind} drawn together, {self.why}", "graphs: " + "; ".join(f"{m.file} / {m.name}" for m in ms)]
        if self.how == "stack":
            cs, texts = [], []; lab_any = self.kind == "XRD" and any(_codelabs(m.spec["panels"][0]) for m in ms); nlab = max([len(_codelabs(m.spec["panels"][0]) or []) for m in ms] + [0]); lim = self.opt.get("stack_labels") or 10 ** 6
            many = min(nlab, lim) > 12; step = (1.6 if many else 1.36) if lab_any else 1.12; placed = []; used = []
            for i, (m, nm) in enumerate(zip(ms, tags)):
                c = _observed(m.spec["panels"][0]["curves"]); y = c["y"]; lo, hi = float(np.nanmin(y)), float(np.nanmax(y)); yn = (y - lo) / ((hi - lo) or 1.0) + i * step
                cl = col(names[i]); cs.append(curve(nm, c["x"], yn, cl))
                x0, x1 = float(np.nanmin(c["x"])), float(np.nanmax(c["x"])); fr = max(0.80, 0.975 - 0.0085 * len(nm)); xr = x0 + ((1 - fr) if s0.get("xrev") else fr) * (x1 - x0)
                near = np.abs(c["x"] - xr) <= 0.05 * (x1 - x0); texts.append((xr, float(np.nanmax(yn[near])) + 0.06 if near.any() else i * step + 0.3, nm, cl))
                if lab_any:
                    lb = sorted(_codelabs(m.spec["panels"][0]) or [], key=lambda t_: -float(np.interp(t_[0], c["x"], yn)))[:int(lim)]
                    lb = [(p_, t_, float(np.interp(p_, c["x"], yn))) for p_, t_, _ in lb if not re.match(r"^[\d.]+$", t_)]
                    pl_, _ = place_labels(lb, c["x"], yn, x0, x1, i * step, i * step + 1.0, False, (), 0.67 if many else 1.0, 0.67 if many else 1.0); placed += pl_; used += [k_ for _, t_, _ in lb for k_ in t_.split("+")]
            p = panel("Intensity (a.u.)" if self.kind == "XRD" else s0["panels"][0]["yname"].split("(")[0].strip() + " (offset)", cs, legend=False, ylim=(-0.05, (n - 1) * step + (1.5 if many else 1.32)))
            p["texts"] = texts; p["yticks"] = False; base["panels"] = [p]
            if placed: p["placed"] = placed; p["vertical"] = False; p["lab_pt"] = 10 if many else 15
            if used and _key(used): notes.insert(0, _key(used) + "." + (" " + KEY_NOTE if any(u_.endswith("?") for u_ in used) else ""))
            if self.kind == "XRD":
                kk = _key(used, {k_: v_ for m in ms for k_, v_ in (m.det.get("_idmap") or {}).items()}) if used else ""
                base.update(no_title=True, xname=s0["xname"], page_in=LANDSCAPE if landscape(self.opt) else (7.0, round((1.35 if many else 0.95) * len(ms) + 3.2, 2)))
                base["footer"] = _wrap_key([((0, 0, 139), e_.strip()) for e_ in kk.split(". ( )")[0].split(", ") if e_.strip()]) if kk else []
                if any(u_.endswith("?") for u_ in used): base["footer"].append([((0, 0, 0), KEY_NOTE)])
            notes.append("Each trace is scaled to its own maximum and shifted upwards, so compare positions and shapes, not heights."); self.record.append("each trace was scaled from 0 to 1 (its own minimum and maximum) and shifted upwards by a fixed step")
        elif self.how == "panels" and str(self.opt.get("stack_style") or STACK_STYLES[0]).startswith("Clean"):
            # clean publication figure: one panel per sample, touching, shared 2theta axis. Observed black, calculated red on top,
            # difference blue below the pattern inside the same panel; sample name and Rwp top right; main peaks labelled
            # (a label needs a peak of at least 'stack_frac' of the strongest one, or a bracket for a phase without own peak)
            idm = {}; used = []; pans = []; frac = float(self.opt.get("stack_frac", 0.05 if landscape(self.opt) and len(ms) <= 3 else 0.10)); lim = self.opt.get("stack_labels")
            for m in ms: idm.update(m.det.get("_idmap") or {})
            for i, (m, nm) in enumerate(zip(ms[::-1], tags[::-1])):          # first file at the bottom
                cv = m.spec["panels"][0]["curves"]
                ob = next((c for c in cv if c["label"] in ("Observed", "Yobs")), cv[0]); ca = next((c for c in cv if c["label"] in ("Calculated", "Ycalc")), cv[-1])
                top = float(np.nanmax(ob["y"])) or 1.0; x = ob["x"]; yo = ob["y"] / top; yc = np.interp(x, ca["x"], ca["y"]) / top; dif = yo - yc
                dm = float(np.nanmax(np.abs(dif))) or 0.01; dbase = -0.22 - dm
                cs = [curve("Observed", x, yo, (0, 0, 0)), curve("Calculated", x, yc, (224, 0, 0)), curve("Difference", x, dif + dbase, (0, 0, 224))]
                allab = _codelabs(m.spec["panels"][0]) or []; gp = m.det.get("_given_pos")
                if gp: allab = [l_ for l_ in allab if any(abs(l_[0] - g_) < 1e-9 for g_ in gp)]          # your own (checked) labels; the extra ones stay in the single graph
                lab_ = [(a_, t_, float(np.interp(a_, x, np.maximum(yo, yc)))) for a_, t_, _ in allab]
                keep = [l_ for l_ in lab_ if l_[2] >= frac or l_[1].startswith("(")]
                if lim: keep = sorted(keep, key=lambda t_: -t_[2])[:int(lim)]
                used += [c_.strip("()?") for _, t_, _ in keep for c_ in t_.split("+")]
                rw = next((l_ for l_ in (m.spec["panels"][0].get("legendbox") or {}).get("lines", []) if l_.startswith("Rwp")), "")
                p = panel("", cs, labels=keep, vertical=False, legend=False); p["yticks"] = False; p["lab_pt"] = 15 if not (landscape(self.opt) and len(ms) > 3) else 12      # more than three panels on a landscape page: smaller labels
                p["lab_scale"] = 2.0 * (2.0 / 7.0) / (((LANDSCAPE[1] - 1.9) / len(ms)) / LANDSCAPE[0]) if landscape(self.opt) else 2.0
                p["corner_r"] = [(nm, True)] + ([(rw.replace("Rwp", "R_wp"), False)] if rw else []); pans.append(p)
                _panel_zoom(p, m, len(ms), self.opt)
            pans[len(pans) // 2]["yname"] = "Intensity (a.u.)"; base["panels"] = pans
            base["page_in"] = LANDSCAPE if landscape(self.opt) else (7.0, round(2.0 * len(ms) + 2.0, 2))
            base.update(no_title=True, hspace=0.0, xname="2θ (°), Cu Kα" if abs((s0.get("lam") or 1.5406) - 1.5406) < 0.002 else "2θ (°)",
                        legend_row=[((0, 0, 0), "Observed"), ((224, 0, 0), "Calculated"), ((0, 0, 224), "Difference")])
            ks = [c_ for c_ in dict.fromkeys(used) if c_ and not re.match(r"^[\d.]+$", c_)]; order = list(xs.CODE_NAMES); ks.sort(key=lambda c_: order.index(c_) if c_ in order else 99)
            key_ = [((0, 0, 0), f"{c_} = {idm.get(c_) or xs.CODE_NAMES.get(c_, c_)}") for c_ in ks]
            base["footer"] = _wrap_key(key_, 80) + ([[((0, 0, 0), "( ) = phase included in the refinement, no individually resolved peak")]] if any(t_.startswith("(") for t_ in [l_[1] for m in ms for l_ in (_codelabs(m.spec["panels"][0]) or [])] ) and any(c_ for c_ in used) else [])
            notes.append("Each panel is scaled to the maximum of its observed pattern. Main peaks are labelled."); self.record.append(f"clean publication layout: observed black, calculated red, difference blue; each panel divided by the maximum of its observed curve; peaks labelled when at least {100 * frac:g} % of the strongest peak (plus bracketed phases without a resolved peak)")
        elif self.how == "panels":
            # publication figure, GSAS-II layout with HighScore colours: one panel per sample, panels touching, shared 2theta axis;
            # in each panel observed (red) and calculated (blue, on top), Bragg tick rows below the pattern, the difference curve
            # below the ticks; sample name and Rwp top right; one legend row above, a colour-coded phase key below the axis
            allc = []; idm = {}
            for m in ms:
                pl_ = m.det.get("_peaklist")
                if pl_ is not None: allc += [c_ for c_ in dict.fromkeys(pl_["Code"]) if c_ not in allc]
                idm.update(m.det.get("_idmap") or {})
            order = list(xs.CODE_NAMES); allc.sort(key=lambda c_: order.index(c_) if c_ in order else 99)
            tcol = {c_: STACK_TICK[k_ % len(STACK_TICK)] for k_, c_ in enumerate(allc)}
            nmax = max([len(set(m.det["_peaklist"]["Code"])) if m.det.get("_peaklist") is not None else 0 for m in ms] + [0])
            pans = []; used = []; lim = self.opt.get("stack_labels") or 10 ** 6
            many = min(max([len(_codelabs(m.spec["panels"][0]) or []) for m in ms] + [0]), lim) > 12; ph_in = 2.3 if many else 1.55      # panel height in inches
            for i, (m, nm) in enumerate(zip(ms[::-1], tags[::-1])):          # first file at the bottom
                cv = m.spec["panels"][0]["curves"]
                ob = next((c for c in cv if c["label"] in ("Observed", "Yobs")), cv[0]); ca = next((c for c in cv if c["label"] in ("Calculated", "Ycalc")), cv[-1])
                top = float(np.nanmax(ob["y"])) or 1.0; x = ob["x"]; yo = ob["y"] / top; yc = np.interp(x, ca["x"], ca["y"]) / top; dif = yo - yc
                cs = [curve("Observed", x, yo, HS_OBS), curve("Calculated", x, yc, HS_CALC)]
                pl_ = m.det.get("_peaklist"); codes = list(dict.fromkeys(pl_["Code"])) if pl_ is not None else []
                t0 = min(0.0, float(np.nanmin(yo))) - 0.06; pitch = 0.075
                for r_, c_ in enumerate(codes):
                    tt = pl_.loc[pl_["Code"] == c_, "tt"].values; tt = tt[(tt >= x.min()) & (tt <= x.max())]
                    tx = np.repeat(tt, 3); ty = np.tile([t0 - r_ * pitch, t0 - r_ * pitch - 0.05, np.nan], len(tt)); tx[2::3] = np.nan
                    cs.append(curve(c_, tx, ty, tcol[c_], width="thin"))
                dm = float(np.nanmax(np.abs(dif))) or 0.01; dbase = t0 - max(len(codes), 1 if nmax else 0) * pitch - 0.03 - dm
                cs.append(curve("Difference", x, dif + dbase, DIFF_COL))
                lab_ = sorted(_codelabs(m.spec["panels"][0]) or [], key=lambda t_: -t_[2])[:int(lim)]
                lab_ = [(a_, t_, float(np.interp(a_, x, np.maximum(yo, yc)))) for a_, t_, _ in lab_]; used += [c_ for _, t_, _ in lab_ for c_ in t_.split("+")]
                rw = next((l_ for l_ in (m.spec["panels"][0].get("legendbox") or {}).get("lines", []) if l_.startswith("Rwp")), "")
                p = panel("", cs, labels=lab_, vertical=False, legend=False); p["yticks"] = False; p["lab_pt"] = 10 if many else 15; p["lab_scale"] = 2.4 * 1.55 / ph_in      # short panels: text is taller relative to the axis
                qn = [r for r in ((m.det.get("_info") or {}).get("phases") or []) if r.get("wt") is not None]
                p["side"] = [(nm, True)] + ([(rw, False)] if rw else []) + [(l_, False) for l_ in _quant_lines(qn, width=24)]      # column right of the panel
                pans.append(p)
                _panel_zoom(p, m, len(ms), self.opt)
            pans[len(pans) // 2]["yname"] = "Intensity (a.u.)"; base["panels"] = pans
            base["page_in"] = LANDSCAPE if landscape(self.opt) else (8.6, round(ph_in * len(ms) + 2.0, 2))
            base.update(no_title=True, hspace=0.0, xname="2θ (°)" + ("" if abs((s0.get("lam") or 1.5406) - 1.5406) > 0.002 else ", Cu Kα"),
                        legend_row=[(HS_OBS, "Observed"), (HS_CALC, "Calculated"), (DIFF_COL, "Difference")] + ([((0, 0, 0), "Bragg positions (colours below)")] if allc else []))
            key_ = [(tcol[c_], f"{c_} = {idm.get(c_) or xs.CODE_NAMES.get(c_, c_)}") for c_ in allc]
            extra = [c_.strip("()?") for c_ in used if c_.strip("()?") and c_.strip("()?") not in allc and not re.match(r"^[\d.]+$", c_.strip("()?"))]
            key_ += [((0, 0, 139), f"{c_} = {idm.get(c_) or xs.CODE_NAMES.get(c_, c_)}") for c_ in dict.fromkeys(extra)]
            base["footer"] = _wrap_key(key_) + ([[((0, 0, 0), "( ) = phase included in the refinement, no individually resolved peak")]] if any(c_.startswith("(") for c_ in used) else [])
            notes.append("Each panel is scaled to the maximum of its observed pattern; observed (red), calculated (blue), Bragg positions (tick rows) and difference (teal, offset).")
            self.record.append("publication layout (GSAS-II arrangement, HighScore colours): each panel divided by the maximum of its observed curve; tick rows from the linked peak lists; difference curve offset below the ticks")
        else:
            pans = []
            P0 = lambda m: m.spec.get("split") or m.spec["panels"]
            for k in range(len(P0(ms[0]))):
                cs, bands = [], []
                if avg:
                    for u_ in uniq:
                        cvs = [P0(m)[k]["curves"][0] for m, nm in zip(ms, names) if nm == u_]
                        if len(cvs) == 1: cs.append(curve(u_, cvs[0]["x"], cvs[0]["y"], col(u_), kind=cvs[0]["kind"])); continue
                        g, mean, sd = _average(cvs); cs.append(curve(f"{u_} (mean, n = {len(cvs)})", g, mean, col(u_))); bands.append((g, mean - sd, mean + sd, col(u_)))
                else:
                    for i, (m, nm) in enumerate(zip(ms, tags)):
                        cv = P0(m)[k]["curves"]
                        for c in ([_observed(cv)] if self.kind != "XY" else [c for c in cv if not str(c["label"]).startswith("_")]):
                            cs.append(curve(nm if len(cv) == 1 or self.kind != "XY" else f"{nm}: {c['label']}", c["x"], c["y"], col(names[i]) if self.kind != "XY" else PALETTE[len(cs) % len(PALETTE)], kind=c["kind"]))
                p = panel(P0(ms[0])[k]["yname"], cs, weight=P0(ms[0])[k]["weight"], legend=(k == 0)); p["bands"] = bands; pans.append(p)
            base["panels"] = pans
            if avg:
                notes.append("Lines: mean of the replicates. Shaded band: ± 1 standard deviation.")
                self.record.append("replicates (graphs with the same sample name) were interpolated onto the x values of the first replicate, over the range they share; the line is their mean and the band ± 1 standard deviation (n − 1)")
            if len({tuple(norm(p["yname"]) for p in P0(m)) for m in ms}) > 1:
                self.warnings.append("these files do not name their y axes the same way (" + " | ".join(dict.fromkeys(P0(m)[0]["yname"] for m in ms)) + "); check that they really are the same quantity before using this overlay")
        if notes: base["note"] = " ".join(notes)
        res = [m.results.assign(Sample=nm, Replicate=names[:i + 1].count(nm)) for i, (m, nm) in enumerate(zip(ms, names)) if m.results is not None]
        if res:
            r = pd.concat(res, ignore_index=True); lead = ["Sample"] + (["Replicate"] if has_rep else []); self.results = r[lead + [c for c in r.columns if c not in ("Sample", "Replicate")]]
        self.summary = None
        if has_rep:
            self.summary, skipped = _summarise(ms, names)
            if skipped: self.warnings.append("no mean ± SD table for " + ", ".join(skipped) + ": the replicates did not give the same rows (for TGA, set fixed temperature ranges under Analysis settings)")
        base.setdefault("arrows", str(opt.get("pointers") or POINTERS[0]).startswith("Arrow")); base["label_mult"] = label_mult(opt)
        if not landscape(opt) and not base.get("page_in"): base["page_in"] = (LANDSCAPE[1], LANDSCAPE[0])
        self.spec = finish(base)
        if self.kind == "Calorimetry": calo_style(self.spec, [(nm_, m.spec.get("_calo")) for nm_, m in zip(tags, ms)], opt)
        return self

class SamplePage(Combined):
    """One sample on one page: (a) the measured pattern with its assigned peaks, (b) the refined pattern
    (observed, calculated and the difference curve below). The two graphs sit side by side or one above the other."""
    def __init__(self, member, opt=None, part=""):
        self.members = [member]; self.how = "page"; self.kind = member.kind; self.warnings = []; self.spec = self.results = self.summary = None
        self.cmap = {}; self.opt = opt or {}; self.record = []; self.part = part; nm = display_names([member])[0]
        self.name = re.sub(r"[^A-Za-z0-9]+", "_", "Page_" + re.sub(r"\s*\(.*?\)", "", nm) + part).strip("_"); self.label = "pattern + fit on one page"
        self.why = "one page for this sample: the measured pattern with its assigned peaks next to its refined pattern"
    @property
    def title(self): return f"\u2605 Sample page: {display_names(self.members)[0]}  ((a) pattern with assigned peaks, (b) fit)"
    def build(self, opt=None, kind=None):
        opt = opt or self.opt; m = self.members[0]; p0 = m.spec["panels"][0]; cv = p0["curves"]; nm = display_names([m])[0]; self.warnings = []
        ob = next((c for c in cv if c["label"] in ("Observed", "Yobs")), cv[0]); ca = next((c for c in cv if c["label"] in ("Calculated", "Ycalc")), cv[-1])
        x = ob["x"]; yo = ob["y"]; yc = np.interp(x, ca["x"], ca["y"]); dif = yo - yc; top = float(np.nanmax(yo)) or 1.0; dm = float(np.nanmax(np.abs(dif))) or 1.0
        named = p0.get("code_labels") is not None; labs = list(p0.get("labels") or []); nall = len(_codelabs(p0) or [])
        lay = str(opt.get("page_layout") or PAGE_LAYOUTS[0]); land = landscape(opt); side = lay.startswith("Side") or (lay.startswith("Decide") and land)
        frac = PAGE_FRAC_SIDE if side else NAME_FRAC               # part of a page per graph: the main peaks (a narrow graph holds fewer labels)
        if p0.get("_bg") is not None and len(p0["_bg"]) == len(x) and (side or not named): labs = main_peaks(labs, x, p0["_bg"], frac)
        cell, fsc, lp = ((0.45, 1.0), 0.85, 16) if side else ((1.0, 0.46), 0.9, 16) if land else ((0.72, 0.9), 0.9, 16)      # peak labels of a sample page: as large as in a single graph
        ylab = "Intensity (cps)" if re.search(r"(?i)cps|second", p0.get("yname") or "") else "Intensity (counts)"
        lam = m.spec.get("lam") or 1.5406; xn = "2\u03b8 (\u00b0), Cu K\u03b1" if abs(lam - 1.5406) < 0.002 else f"2\u03b8 (\u00b0), \u03bb = {lam:.4f} \u00c5"
        ins = p0.get("inset") or {}; rng = ins.get("xlim"); ilabs = ins.get("labels")
        if not rng and zoom_auto(opt):          # the app chooses the crowded region of the main peaks
            rng = auto_inset(x, yo, p0.get("_bg"))
            ilabs = names_on(p0["code_labels"], m.det.get("_idmap"))[0] if named else list(p0.get("labels") or [])
        rw = next((l_ for l_ in (p0.get("legendbox") or {}).get("lines", []) if l_.startswith("Rwp")), "")
        common = dict(xname=xn, lam=lam, arrows=m.spec.get("arrows"), no_title=True, cell=cell, font_scale=fsc, label_mult=label_mult(opt))
        pa = panel(ylab, [curve("Observed", x, yo, (0, 0, 0))], labels=labs, vertical=bool(p0.get("vertical")) if named else False, legend=False); pa["ylim"] = None; pa["lab_pt"] = lp; pa["corner"] = [nm]
        pa["max_lift"] = 0.22 if named else 0.16 if side else 0.30      # a label that would sit far above its peak on a long pointer is left to the inset and the single graph
        if side: pa["max_side"] = 0.05
        if rng and ilabs:                                  # the zoomed part names the peaks that stand out in it (at least 5 % of its strongest); a tiny peak would only add a long pointer
            ilabs = [l_ for l_ in ilabs if rng[0] < l_[0] < rng[1]]
            if p0.get("_bg") is not None and len(p0["_bg"]) == len(x): ilabs = main_peaks(ilabs, x, p0["_bg"], 0.05)
        if rng: pa["inset"] = dict(xlim=rng, labels=ilabs or labs, max_lift=0.5, max_side=0.2)
        A = finish(dict(common, title=nm, panels=[pa]))
        dbase = -(0.10 * top + dm)
        pb = panel(ylab, [curve("Observed", x, yo, (0, 0, 0)), curve("Calculated", x, yc, (224, 0, 0)), curve("Difference", x, dif + dbase, (0, 0, 224))], legend=False)
        pb["ylim"] = None; pb["lab_pt"] = lp; pb["corner"] = [nm] + ([rw.replace("Rwp", "R_wp")] if rw else [])
        if rng: pb["inset"] = dict(xlim=rng, labels=[])
        B = finish(dict(common, title=nm, panels=[pb], legend_row=[((0, 0, 0), "Observed"), ((224, 0, 0), "Calculated"), ((0, 0, 224), "Difference")]))
        pin = LANDSCAPE if land else (LANDSCAPE[1], LANDSCAPE[0])
        shown = [q_[2] for q_ in A["panels"][0].get("placed", [])] + [q_[2] for q_ in (A["panels"][0].get("inset") or {}).get("placed", [])]      # the key explains exactly the letters on this page
        idm_ = m.det.get("_idmap") or {}
        codes_ = ([c_ for t_ in shown for c_ in str(t_).split("+")] if not named else                                   # names on the peaks: only the codes that stayed letters need the key
                  [c_ for t_ in shown for c_ in (q_.strip("()?") for q_ in str(t_).split("/")) if (c_ in idm_ or c_ in xs.CODE_NAMES) and short_name(c_, idm_) is None])
        kk = _key(codes_, m.det.get("_idmap")) if codes_ else ""
        foot = _wrap_key([((0, 0, 0), e_.strip()) for e_ in kk.split(". ( )")[0].split(", ") if e_.strip()], 125) if kk else []
        if any(str(t_).startswith("(") or "(" in str(t_)[:1] for t_ in shown) or any("/(" in str(t_) for t_ in shown): foot.append([((0, 0, 0), BRACKET_NOTE)])
        if any("?" in str(t_) for t_ in shown): foot.append([((0, 0, 0), KEY_NOTE)])
        A["o_footer"] = foot; B["footer_pad"] = len(foot)       # Origin: the key is written under graph (a); graph (b) leaves the same room
        self.spec = dict(title=f"{nm}: pattern and fit", xname=xn, cols=[A, B], layout="side" if side else "stack", page_in=pin, no_title=True, panels=A["panels"] + B["panels"], xlim=A["xlim"], lam=lam, footer=foot)
        pf = "profile fit" in rw
        self.caption_text = (f"(a) X-ray diffractogram of {nm} with assigned peaks. (b) " + ("Profile fit (no crystal structures; not a Rietveld refinement)" if pf else "Refined pattern from the Rietveld analysis") + f" of {nm}: "
                             "the measured pattern is shown in black, the calculated pattern in red and the difference between them in blue (shifted below the pattern)."
                             + (f" {rw}." if rw else "") + (f" Insets: {rng[0]:g}-{rng[1]:g}\u00b0 2\u03b8." if rng else "") + (" " + m.spec["note"] if m.spec.get("note") else ""))
        self.record = [f"sample page, {'side by side' if side else 'one above the other'} on a {'landscape' if land else 'portrait'} page: (a) the observed pattern with {len(labs)} of its {nall} peak labels "
                       f"(peaks of at least {100 * frac:g} % of the strongest; every label is in the single graph), (b) observed, calculated and their difference shifted down by {-dbase:.4g}; nothing was rescaled"]
        return self

PAGE_FRAC_SIDE = 0.08     # side by side: (a) labels the peaks of at least 8 % of the strongest one

BOTH_WAYS = ("TGA", "DSC", "DTA", "Calorimetry", "FTIR", "XRD", "Raman", "NMR", "Particle size")      # several of these: stacked AND overlaid


def auto_boards(singles, combined, boards):
    """Figures the app makes on its own for thermal analysis files that hold TG and DSC together (NETZSCH .ngb, STA exports):
    one page per sample - (a) TG with DTG, (b) DSC on the same temperature axis - and, for several samples, a comparison -
    (a) the TG curves overlaid, (b) the DSC curves overlaid. Returns the new Boards (none twice)."""
    have = {tuple(b.keys) for b in boards}
    out = []; num = max([b.number for b in boards] + [0])
    by_file = {}
    for it in singles:
        p_ = str(getattr(it, "path", "") or "")
        if p_ and it.kind in ("TGA", "DSC", "DTA"):
            by_file.setdefault(p_, {})[it.kind] = it
    pairs = [(d["TGA"], d.get("DSC") or d.get("DTA")) for d in by_file.values() if "TGA" in d and (d.get("DSC") or d.get("DTA"))]
    for tg_, ds_ in pairs:
        keys = [key_of(tg_), key_of(ds_)]
        if tuple(keys) in have: continue
        num += 1; b = Board(keys, 1, 160.0, num); b.auto = "sample"; b.name = re.sub(r"[^A-Za-z0-9]+", "_", f"Thermal_{display_names([tg_])[0]}").strip("_")
        out.append(b); have.add(tuple(keys))
    if len(pairs) >= 2:
        ov = {c.kind: c for c in combined if getattr(c, "how", "") == "overlay" and c.kind in ("TGA", "DSC", "DTA") and not getattr(c, "mine", False)}
        if "TGA" in ov and (ov.get("DSC") or ov.get("DTA")):
            keys = [key_of(ov["TGA"]), key_of(ov.get("DSC") or ov.get("DTA"))]
            if tuple(keys) not in have:
                num += 1; b = Board(keys, 1, 175.0, num); b.auto = "compare"; b.name = "Thermal_comparison"
                out.append(b)
    return out


def make_groups(singles, mode="Decide for me", opt=None):
    """Group sheets of the same kind (and overlapping x range) into combined figures. Returns (combined items, explanation lines)."""
    if mode == "Keep them separate": return [], []
    # bar charts, box plots, maps and phase-assemblage graphs stand on their own: they are not overlaid with other tables
    ready = [it for it in singles if it.spec is not None and it.kind != "XRD peak list" and not figtype_id(it.kind) and not (it.det.get("thermo") or it.det.get("pore") or it.det.get("cat_only") or str((getattr(it, "custom", None) or {}).get("style")) in CHARTS)]; cmap = {}
    for nm in display_names(ready): cmap.setdefault(nm, PALETTE[len(cmap) % len(PALETTE)])      # one colour per sample, the same in every figure
    groups = []
    for it in ready:
        g = next((g for g in groups if _compatible(g[0], it)), None)
        if g: g.append(it)
        else: groups.append([it])
    out, lines = [], []
    split = []                                    # a Group column in your sample information keeps groups apart (e.g. clinkers / raw materials)
    for g in groups:
        by = {}
        for it in g: by.setdefault(((it.det.get("_info") or {}).get("group") or ""), []).append(it)
        split += list(by.values())
        if len(by) > 1: lines.append(f"  {g[0].kind}: split by the Group column of your sample information: " + ", ".join(k or "(no group)" for k in by))
    groups = split; pages_only = str(mode).startswith("One page")
    for g in groups:
        if len(g) < 2 or pages_only: continue
        how, why = RULES.get(g[0].kind, ("overlay", "overlaid on common axes"))
        if g[0].kind.startswith("Fit") and len(g) > 4 and mode == "Decide for me":
            how, why = "stack", "stacked with an offset (observed patterns): more than four fits read better stacked than as small panels; each fit with its difference curve is on its own sample page"
        if mode == "Stack them" and how != "panels": how, why = "stack", "stacked with an offset, as you asked"
        if mode == "Overlay them" and how != "panels": how, why = "overlay", "overlaid on common axes, as you asked"
        mx_ = max_in(how, opt); chunks = [g[i:i + mx_] for i in range(0, len(g), mx_)]
        if len(chunks) > 1 and len(chunks[-1]) == 1:
            last_ = chunks.pop(); chunks[-1] = chunks[-1] + last_
        hows = [(how, why)]
        if mode == "Decide for me" and how in ("stack", "overlay") and g[0].kind in BOTH_WAYS:      # several files of one kind: both ways, always
            other = "overlay" if how == "stack" else "stack"
            hows.append((other, "stacked with an offset as well (each curve on its own level, easy to compare shapes)" if other == "stack" else "overlaid as well (on common axes, easy to compare values)"))
        for how_, why_ in hows:
            for k, ch in enumerate(chunks):
                c = Combined(ch, how_, why_, f"_{k + 1}" if len(chunks) > 1 else "", cmap, opt)
                try: c.build(); out.append(c)
                except Exception as e: lines.append(f"!! could not combine the {g[0].kind} graphs: {e}"); continue
        nrep = (len(g) - len(set(display_names(g)))) if how != "panels" else 0
        lines.append(f"  {len(g)} {g[0].kind} graphs -> {why}" + (f" ({len(chunks)} figures, at most {mx_} in each)" if len(chunks) > 1 else "") + (f"; {nrep + len(set(n_ for n_ in display_names(g) if display_names(g).count(n_) > 1))} of them are replicates of the same sample" if nrep else ""))
    fits = [it for it in ready if it.kind.startswith("Fit")] if (pages_only or mode == "Decide for me") else []
    if fits:                                       # one page per sample: its pattern with assigned peaks and its fit
        seen = {}; npg = 0; lays = set()
        for it in fits:
            nm_ = display_names([it])[0]; seen[nm_] = seen.get(nm_, 0) + 1
            try:
                pg = SamplePage(it, opt, f"_{seen[nm_]}" if seen[nm_] > 1 else ""); pg.build(); out.append(pg); npg += 1; lays.add(pg.spec["layout"])
            except Exception as e: lines.append(f"!! could not make the sample page of {nm_}: {e}")
        if npg: lines.append(f"  {npg} fit graphs -> one page per sample as well: (a) the pattern with its assigned peaks, (b) the fit with the difference curve; " + " / ".join("side by side" if l_ == "side" else "one above the other" for l_ in sorted(lays)))
    kinds = {}
    for g in groups: kinds[g[0].kind] = kinds.get(g[0].kind, 0) + 1
    for k, v in kinds.items():
        if v > 1: lines.append(f"  the {k} graphs were kept in {v} separate sets, because they differ in x range, units, X-ray wavelength or panel layout")
    return out, lines

# ============================================================================= panel figures for papers
class Board:
    """A figure for a paper: one or several graphs side by side as panels (a), (b) ... at an exact width."""
    path = ""; file = "Figure"; kind = "Panel figure"; results = None; summary = None; spec = None
    def __init__(self, keys, cols=0, width_mm=175.0, number=1):
        self.keys = list(keys); self.cols = int(cols or 0); self.width_mm = float(width_mm); self.number = number; self.name = f"Figure_{number}"; self.members = []; self.warnings = []; self.record = []
    def resolve(self, pool):
        d = {key_of(i): i for i in pool}; self.members = [d[k] for k in self.keys if k in d]; self.keys = [key_of(m) for m in self.members]; return bool(self.members)
    @property
    def grid(self):
        n = max(1, len(self.members)); c = min(n, self.cols or (1 if n == 1 else 2 if n <= 4 else 3)); return math.ceil(n / c), c
    def size_in(self):
        r, c = self.grid; w = self.width_mm / 25.4; return w, r * (w / c) * 0.80 + 0.12
    @property
    def title(self):
        n = len(self.members); return f"▣ {self.name}: " + (f"{n} panels (a)-({chr(96 + n)})" if n > 1 else "1 graph") + f", {self.width_mm:g} mm wide"
    def build(self, opt=None, kind=None):
        w, h = self.size_in(); r, c = self.grid
        self.record = [f"panel figure, {r} x {c} panels, {self.width_mm:g} mm wide x {h * 25.4:.0f} mm high, made from: " + "; ".join(m.title for m in self.members)]; return self

# ============================================================================= your own format of one graph (the ribbon at the top)
FMT_ROLES = {"Graph title": "title", "Axis titles": "axis_titles", "Axis numbers": "numbers", "Peak labels and other text": "labels", "Legend": "legend"}
FONT_FAMILIES = ["Arial", "Helvetica", "Calibri", "Times New Roman", "Cambria", "Georgia", "Verdana", "Tahoma", "Segoe UI", "Courier New"]
ORIGIN_PT = 2.2          # Origin text size for 1 pt of the preview (axis titles: 10 pt here, 22 in Origin)

def all_panels(spec):
    """Every panel of a graph, in drawing order (the parts of a page one after the other)."""
    return [p_ for c_ in spec["cols"] for p_ in c_.get("panels", [])] if spec.get("cols") else list(spec.get("panels") or [])

def label_key(pi, q):
    """The name of one peak label for 'moved by you': its panel, the peak it belongs to and its text."""
    return f"{pi}|{float(q[0]):.6g}|{q[2]}"

def fit_view(obj, opt=None):
    """'Pattern with labels' or 'Fit …' for a fit graph: yours (this graph), else Settings > XRD, else the pattern."""
    v = (getattr(obj, "fmt", None) or {}).get("fit_view") or (opt or {}).get("fit_view") or FIT_VIEWS[0]
    return v if v in FIT_VIEWS else FIT_VIEWS[0]

def _pattern_only(spec):
    """A fit drawn as the measured pattern alone, with its peak labels (and its zoomed part): no calculated curve, no difference."""
    top = dict(spec["panels"][0]); cv = top["curves"]
    ob = [c for c in cv if str(c.get("label")) in ("Observed", "Yobs", "Iobs")] or cv[:1]
    top["curves"] = ob
    if top.get("legendbox"):
        bx = dict(top["legendbox"]); bx["keys"] = [k for k in bx.get("keys", []) if str(k[1]) in ("Observed", "Yobs", "Iobs")]
        bx["lines"] = [l for l in bx.get("lines", []) if not str(l).startswith(("Rwp", "R_wp", "Rexp", "GOF", "χ"))]
        top["legendbox"] = bx
    if top.get("inset") and top["inset"].get("curves"):
        ins = dict(top["inset"]); ins["curves"] = [c for c in ins["curves"] if str(c.get("label")) in ("Observed", "Yobs", "Iobs")] or ins["curves"][:1]; top["inset"] = ins
    out = dict(spec); out["panels"] = [top]; out["view"] = "pattern"
    return out

def apply_fmt(obj, opt=None):
    """Your own changes to one graph (titles, legend, axis ranges; and the styles drawn by fmt_figure / Origin), on its spec."""
    fmt = getattr(obj, "fmt", None) or {}; sp_ = getattr(obj, "spec", None)
    if sp_ is not None and isinstance(obj, Item):
        obj.spec_fit = None
        if str(obj.kind).startswith("Fit") and not sp_.get("cols") and fit_view(obj, opt) == FIT_VIEWS[0] and len(sp_.get("panels") or []) >= 1:
            obj.spec_fit = sp_; sp_ = obj.spec = _pattern_only(sp_)     # the combined figures and sample pages keep the whole fit (spec_fit)
    if not sp_ or not fmt: return obj
    subs = sp_.get("cols") or [sp_]
    if fmt.get("title") is not None:
        sp_["title"] = fmt["title"]
        if fmt["title"]: sp_.pop("no_title", None)
    if fmt.get("hide_title"): sp_["no_title"] = True
    for q in subs:
        if fmt.get("xtitle"): q["xname"] = fmt["xtitle"]
        named = [p_ for p_ in q.get("panels", []) if str(p_.get("yname", "")).strip()]
        if fmt.get("ytitle") and named: named[0]["yname"] = fmt["ytitle"]
        if fmt.get("ytitles"):                                  # one per panel
            for p_, t_ in zip(q.get("panels", []), fmt["ytitles"]):
                if t_: p_["yname"] = t_
        if fmt.get("legend") in ("off", "on"):
            for p_ in q.get("panels", []):
                p_["legend"] = fmt["legend"] == "on" and not p_.get("legendbox")       # a graph with its own legend box keeps just that one
                if fmt["legend"] == "off": p_.pop("legendbox", None)
            if fmt["legend"] == "off": q.pop("legend_row", None)
    if fmt.get("xlim") and len(fmt["xlim"]) == 2:
        a_, b_ = float(fmt["xlim"][0]), float(fmt["xlim"][1])
        if a_ != b_:
            for q in ([sp_] + list(sp_.get("cols") or [])):
                q["xlim"] = (max(a_, b_), min(a_, b_)) if q.get("xrev") else (min(a_, b_), max(a_, b_))
    if fmt.get("ylim") and len(fmt["ylim"]) == 2 and sp_.get("panels") and not sp_.get("cols"):
        a_, b_ = float(fmt["ylim"][0]), float(fmt["ylim"][1])
        if a_ < b_: sp_["panels"][0]["ylim"] = (a_, b_); sp_["panels"][0].pop("_ylog_lim", None) if not sp_["panels"][0].get("ylog") else None
    if fmt.get("moved"):                                        # labels you dragged: they stay where you put them (the pointer still goes to the peak)
        for pi, p_ in enumerate(all_panels(sp_)):
            for li, q_ in enumerate(p_.get("placed") or []):
                xy = fmt["moved"].get(label_key(pi, q_))
                if xy: p_["placed"][li] = (q_[0], q_[1], q_[2], float(xy[0]), float(xy[1]))
            for li, q_ in enumerate(p_.get("texts") or []):
                xy = fmt["moved"].get(f"{pi}|name|{q_[2]}")
                if xy: p_["texts"][li] = (float(xy[0]), float(xy[1]), q_[2], q_[3])
    if fmt.get("inset_rect") and sp_.get("panels"):
        ins_ = sp_["panels"][0].get("inset")
        if ins_: ins_["rect"] = tuple(fmt["inset_rect"])
    sp_["fmt"] = fmt
    return obj

_BUILD_FMT = None          # the format of the graph being built: where you want the zoom and the legend (read while the page is laid out)

def auto_zoom(x, y, frac=0.15):
    """A zoom range for any curve: the window of 'frac' of the x span with the most signal above the median (the busiest part)."""
    x = np.asarray(x, float); y = np.asarray(y, float); ok_ = np.isfinite(x) & np.isfinite(y); x, y = x[ok_], y[ok_]
    if len(x) < 10: return None
    o = np.argsort(x); x, y = x[o], y[o]; w = frac * (x[-1] - x[0]); a = np.clip(y - np.median(y), 0, None)
    cs = np.r_[0, np.cumsum(a)]; j = np.searchsorted(x, x + w); tot = cs[np.minimum(j, len(x))] - cs[np.arange(len(x))]
    i = int(np.argmax(tot)); m_ = (x >= x[i]) & (x <= x[i] + w)
    cg = float(np.sum(x[m_] * a[m_]) / np.sum(a[m_])) if np.sum(a[m_]) > 0 else float(x[i] + w / 2)      # centred on the signal in that window
    lo = float(max(x[0], min(cg - w / 2, x[-1] - w))); hi = float(min(x[-1], lo + w))
    return (round(lo, 3), round(hi, 3)) if hi > lo else None

def _with_fmt(build):
    def run(self, *a, **k):
        global _BUILD_FMT
        fmt = getattr(self, "fmt", None) or {}
        want = "No inset" if fmt.get("zoom_off") else (f"{fmt['zoom'][0]:g}-{fmt['zoom'][1]:g}" if fmt.get("zoom") else ("On every XRD pattern and fit" if fmt.get("zoom_on") else None))
        if want and isinstance(self, Item):                            # this graph: zoom off, your range, or on (the app's range)
            a = list(a); o_ = dict(a[0] if a and a[0] else k.pop("opt", None) or {}); o_["inset"] = want
            if a: a[0] = o_
            else: a = [o_]
        elif want and isinstance(self, Combined):
            a = list(a); o_ = dict((a[0] if a and a[0] else k.pop("opt", None)) or self.opt or {}); o_["inset"] = want
            if a: a[0] = o_
            else: a = [o_]
        _BUILD_FMT = fmt
        swapped = []
        if isinstance(self, Combined):                          # figures of several fits: drawn from the whole fit of each
            for m_ in getattr(self, "members", []):
                if getattr(m_, "spec_fit", None) is not None:
                    swapped.append((m_, m_.spec)); m_.spec = m_.spec_fit
        try: r = build(self, *a, **k)
        finally:
            _BUILD_FMT = None
            for m_, s_ in swapped: m_.spec = s_
        o_ = a[0] if a else k.get("opt")
        apply_fmt(self, o_ if isinstance(o_, dict) else getattr(self, "opt", None)); return r
    run.__doc__ = build.__doc__; run._fmt = True
    return run

def fmt_curve(fmt, label, colour, width):
    """The colour and weight of one curve after your changes: the curve's own entry, else 'all curves' ('*')."""
    ln = (fmt or {}).get("lines") or {}
    for key in (str(label), "*"):
        d = ln.get(key) or {}
        if d:
            c_ = look_colour(d.get("colour")) if isinstance(d.get("colour"), str) else (tuple(d["colour"]) if d.get("colour") else None)
            return (c_ or colour), (float(d["width"]) if d.get("width") else width)
    return colour, width

def _role_texts(fig, role):
    out = []
    for ax in fig.axes:
        tt = [t for t in (ax.title, getattr(ax, "_left_title", None), getattr(ax, "_right_title", None)) if t is not None and t.get_text()]
        at = [t for t in (ax.xaxis.label, ax.yaxis.label) if t.get_text()]
        nm = [t for t in ax.get_xticklabels(which="both") + ax.get_yticklabels(which="both")]
        lg = list(ax.get_legend().get_texts()) if ax.get_legend() else []
        if role == "title": out += tt
        elif role == "axis_titles": out += at
        elif role == "numbers": out += nm
        elif role == "legend": out += lg
        elif role == "labels": out += [t for t in ax.texts if t.get_text()]
    if role == "labels": out += [t for t in fig.texts if t.get_text()]
    if role == "title": out += [t for t in fig.texts if t.get_text() and t.get_fontweight() in ("bold", 700) and t.get_position()[1] > 0.9]
    return out

def fmt_figure(fig, fmt):
    """Draw your own format into a finished figure: per kind of text (font, size, bold, italic, colour), the axes (colour, weight),
    the curves (colour, weight per curve or all)."""
    from matplotlib.colors import to_rgb
    if not fmt: return fig
    import logging; logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)      # a font this computer lacks: the next one is used, quietly
    col = lambda c: tuple(v / 255 for v in (look_colour(c) if isinstance(c, str) else c)) if c and (not isinstance(c, str) or look_colour(c)) else None
    for role, st in (fmt.get("text") or {}).items():
        if not st: continue
        ts = _role_texts(fig, role)
        for t in ts:
            if st.get("family"): t.set_fontfamily([st["family"], "Arial", "Liberation Sans", "DejaVu Sans"])
            if st.get("size"): t.set_fontsize(float(st["size"]))
            if st.get("bold") is not None: t.set_fontweight("bold" if st["bold"] else "normal")
            if st.get("italic") is not None: t.set_fontstyle("italic" if st["italic"] else "normal")
            if col(st.get("colour")): t.set_color(col(st["colour"]))
        if role == "numbers":
            kw = {}
            if st.get("size"): kw["labelsize"] = float(st["size"])
            if col(st.get("colour")): kw["labelcolor"] = col(st["colour"])
            if kw:
                for ax in fig.axes: ax.tick_params(axis="both", which="both", **kw)
    ax_ = fmt.get("axis") or {}
    if ax_:
        for ax in fig.axes:
            for sp_ in ax.spines.values():
                if col(ax_.get("colour")): sp_.set_color(col(ax_["colour"]))
                if ax_.get("width"): sp_.set_linewidth(float(ax_["width"]))
            kw = {}
            if col(ax_.get("colour")): kw["color"] = col(ax_["colour"])
            if ax_.get("width"): kw["width"] = float(ax_["width"]) * 0.75
            if kw: ax.tick_params(axis="both", which="both", **kw)
    if fmt.get("legend_loc"):
        for ax in fig.axes:
            lg = ax.get_legend()
            if lg is not None:
                try: lg.set_loc(fmt["legend_loc"])
                except Exception:
                    from matplotlib.legend import Legend as _L
                    lg._loc = _L.codes.get(fmt["legend_loc"], lg._loc)
    if fmt.get("notes") and fig.axes:
        ax0 = fig.axes[0]; st = (fmt.get("text") or {}).get("labels") or {}
        for fx, fy, txt in fmt["notes"]:
            ax0.text(float(fx), float(fy), _mt(txt), transform=ax0.transAxes, ha="left", va="center", fontsize=float(st.get("size") or 9),
                     fontweight="bold" if st.get("bold") else "normal", color=col(st.get("colour")) or "black", clip_on=False)
    if fmt.get("lines"):
        for ax in fig.axes:
            for ln in ax.get_lines():
                if len(ln.get_xdata()) <= 3: continue
                c0 = tuple(int(round(v * 255)) for v in to_rgb(ln.get_color())); w0 = ln.get_linewidth()
                c1, w1 = fmt_curve(fmt, ln.get_label(), c0, w0)
                if c1 != c0: ln.set_color(tuple(v / 255 for v in c1))
                if w1 != w0: ln.set_linewidth(w1)
    return fig

for _c in (Item, Combined, SamplePage):
    if not getattr(_c.build, "_fmt", False) and "build" in _c.__dict__: _c.build = _with_fmt(_c.build)

# ============================================================================= preview (matplotlib)
def _draw(spec, fig, cell, curve_w=1.5, axis_w=1.5, fs=10.0, title=True, letter=None):
    """Draw one spec into a cell of a figure."""
    import textwrap
    if spec.get("cols"):                               # a page of several graphs: (a), (b) ... side by side or one above the other
        n_ = len(spec["cols"]); sg = cell.subgridspec(1, n_, wspace=0.27) if spec.get("layout") == "side" else cell.subgridspec(n_, 1, hspace=0.40); axs = []
        ends = []
        for k_, sub in enumerate(spec["cols"]):
            a_ = _draw(sub, fig, sg[k_], curve_w, axis_w, fs * sub.get("font_scale", 1.0), title=False, letter=chr(97 + k_)); axs += a_; ends.append(a_[-1])
        foot_ = spec.get("footer") or []
        if foot_:                                          # the key to the letters, under the page (left edge of the first graph, the full width of the page)
            anchor = ends[0] if spec.get("layout") == "side" else ends[-1]; fsf = fs * spec["cols"][0].get("font_scale", 1.0)
            aw_ = cell.get_position(fig).width * fig.get_size_inches()[0] * 72
            ffs = max(5.0, min(fsf - 1.0, aw_ / (max(sum(len(t_) + 3 for _, t_ in line) for line in foot_) * 0.55)))
            for k_, line in enumerate(foot_):
                txt = "     ".join(t_ for _, t_ in line)
                anchor.annotate(_mt(txt), xy=(0, 0), xycoords="axes fraction", xytext=(0, -(fsf * 3.6) - ffs * 1.4 * k_), textcoords="offset points", fontsize=ffs, color="black", va="top", ha="left", annotation_clip=False)
        return axs
    gs = cell.subgridspec(len(spec["panels"]), 1, height_ratios=[p["weight"] for p in spec["panels"]], hspace=spec.get("hspace", 0.06))
    f = lambda c: tuple(v / 255 for v in c); axes = []; small = fs - 2
    for i, p in enumerate(spec["panels"]):
        ax = fig.add_subplot(gs[i], sharex=axes[0] if axes else None); axes.append(ax)
        for x_, lo_, hi_, col in p.get("bands", []): ax.fill_between(x_, lo_, hi_, color=f(col), alpha=0.20, lw=0)
        for c in p["curves"]:
            lw = curve_w * (4 / 3 if c["width"] == "obs" else 1) * (0.55 if p.get("thin") or c["width"] == "thin" else 1)
            if c["kind"] == "area": ax.fill_between(c["x"], c.get("base", 0.0), c["y"], facecolor=f(c["colour"]), edgecolor="black", linewidth=0.35 * axis_w, label=c["label"])
            elif c["kind"] == "bar": ax.bar(c["x"], c["y"], width=c.get("barw", 0.8), color=f(c["colour"]), edgecolor="black", linewidth=0.5 * axis_w, label=c["label"])
            elif c["kind"] == "scatter": ax.plot(c["x"], c["y"], "o", ms=3, mfc="none", mew=0.7, color=f(c["colour"]), label=c["label"])
            elif c["kind"] == "linesymbol": ax.plot(c["x"], c["y"], "o-", ms=5, lw=lw, color=f(c["colour"]), label=c["label"])
            else: ax.plot(c["x"], c["y"], "-", lw=lw, color=f(c["colour"]), label=c["label"])
        for sx, sy, col in p.get("segs", []): ax.plot(sx, sy, "-", lw=max(0.8, curve_w / 2), color=f(col))
        if p.get("contour"):                                       # the value z as colours between the measured points
            cn = p["contour"]
            try: cf = ax.tricontourf(cn["x"], cn["y"], cn["z"], levels=12, cmap="viridis", zorder=0)
            except Exception: cf = ax.scatter(cn["x"], cn["y"], c=cn["z"], cmap="viridis", s=14, zorder=0)
            cb = fig.colorbar(cf, ax=ax, pad=0.02, fraction=0.05); cb.set_label(cn["zname"], fontsize=fs); cb.ax.tick_params(labelsize=small, width=0.6 * axis_w); cb.outline.set_linewidth(axis_w)
        def lead(a_, pos, py, lx, ly, span, beside=False):         # thin leader line, or an arrow pointing at the peak
            if not (ly - py > 0.04 * span or (abs(lx - pos) > 1e-9 and not beside)): return
            if spec.get("arrows"): a_.annotate("", xy=(pos, py + 0.008 * span), xytext=(lx, ly), arrowprops=dict(arrowstyle="->", lw=0.6, color=f(NAVY), shrinkA=0, shrinkB=0, mutation_scale=max(4.0, 0.6 * fs)))
            else: a_.plot([pos, lx], [py + 0.005 * span, ly], "-", lw=0.6, color=f(NAVY))
        for pos, py, txt, lx, ly in p.get("placed", []):
            ax.text(lx, ly, _lb(txt), rotation=90 if p["vertical"] else 0, ha="center", va="bottom", fontsize=max(5.5 if not spec.get("cell") else 4.5, small * p.get("lab_pt", 15) / 15.0), fontweight="bold", color=f(NAVY))
            lead(ax, pos, py, lx, ly, p["ylim"][1] - p["ylim"][0], getattr(txt, "beside", False))
        ins = p.get("inset")
        if ins and ins.get("curves"):                              # zoomed inset: the same curves in a narrow range, on their own scale
            iax = ax.inset_axes(ins["rect"]); isp = ins["ylim"][1] - ins["ylim"][0]
            for c in ins["curves"]: iax.plot(c["x"], c["y"], "-", lw=curve_w * (4 / 3 if c["width"] == "obs" else 1), color=f(c["colour"]), label=c["label"])
            for pos, py, txt, lx, ly in ins["placed"]:
                iax.text(lx, ly, _lb(txt), rotation=90 if ins["vertical"] else 0, ha="center", va="bottom", fontsize=max(5.5, small * ins["lab_pt"] / 15.0), fontweight="bold", color=f(NAVY))
                lead(iax, pos, py, lx, ly, isp, getattr(txt, "beside", False))
            iax.set_xlim(*ins.get("xdraw", ins["xlim"])); iax.set_ylim(*ins["ylim"])
            iax.tick_params(direction="in", which="both", top=True, right=True, labelleft=False, labelsize=max(5.5, fs - 1.5), width=0.6 * axis_w, length=0.3 * fs, pad=2)
            from matplotlib.ticker import AutoMinorLocator as _AML
            iax.xaxis.set_minor_locator(_AML(2))
            for sp_ in iax.spines.values(): sp_.set_linewidth(axis_w)
            for t_ in iax.get_xticklabels(): t_.set_fontweight("bold")
        for pos, py, txt, lx, ly in p.get("placed_below", []):
            ax.text(lx, ly, txt, rotation=90, ha="center", va="top", fontsize=small, fontweight="bold", color=f(NAVY))
        for tx, ty, txt, col in p.get("texts", []):
            ax.text(tx, ty, txt, ha="center", va="bottom", fontsize=small + 0.5, fontweight="bold", color=f(col))
        if not p.get("yticks", True): ax.set_yticks([])
        ycr = 0.95; xcr = 0.985; ph_in_ = ax.get_position().height * ax.figure.get_figheight(); inline_ = ph_in_ < 1.25 and len(p.get("corner_r", [])) <= 2
        for it_ in p.get("corner_r", []):
            txt, b_ = it_[0], it_[1]; col_ = f(it_[2]) if len(it_) > 2 else "black"
            ax.text(0.985, ycr, _mt(txt.replace("R_wp", "R$_{wp}$")), transform=ax.transAxes, ha="right", va="top", fontsize=(fs + 0.5) if b_ else fs - 1.5, fontweight="bold" if b_ else "normal", color=col_) if not inline_ else None
            if inline_:                                    # short panel: name and the lines after it side by side on one line, from the right
                t_ = ax.text(xcr, 0.93, _mt(txt.replace("R_wp", "R$_{wp}$")), transform=ax.transAxes, ha="right", va="top", fontsize=(fs + 0.5) if b_ else fs - 1.0, fontweight="bold" if b_ else "normal", color=col_)
                try: wd_ = t_.get_window_extent(ax.figure.canvas.get_renderer()).width / ax.get_window_extent().width
                except Exception: wd_ = len(txt) * 0.0075
                xcr -= wd_ + 0.012
            else: ycr -= max(0.12 if b_ else 0.075, ((fs + 2.5) / 72.0) / max(ph_in_, 0.2))
        cdy_ = (0.055 if spec.get("cell") else 0.075) / spec.get("cell", (1.0, 1.0))[1]
        for k_, txt in enumerate(p.get("corner", [])): ax.text(0.015, 0.96 - cdy_ * k_, _mt(txt.replace("R_wp", "R$_{wp}$")), transform=ax.transAxes, ha="left", va="top", fontsize=fs - 1, fontweight="bold" if k_ == 0 and spec.get("cell") else "normal")
        bx = p.get("legendbox")
        if bx:
            _bx_art = []; dy = bx.get("dy", 0.055); x0_ = 0.012 if bx.get("side", "left") == "left" else 1 - bx.get("wfrac", 0.3) + 0.004; yy = 0.975
            ax_h = ax.get_position().height * fig.get_size_inches()[1]; fsz = max(5.5, min(small + 0.5, dy * ax_h * 72 / 1.45))
            _bx_art.append(ax.text(x0_, yy, bx.get("title", ""), transform=ax.transAxes, ha="left", va="top", fontsize=fsz + 1, fontweight="bold")); yy -= dy * 1.15
            for col, txt in bx.get("keys", []):
                _bx_art.extend(ax.plot([x0_ + 0.002, x0_ + 0.024], [yy - dy * 0.42] * 2, transform=ax.transAxes, color=f(col), lw=curve_w)); _bx_art.append(ax.text(x0_ + 0.030, yy, txt, transform=ax.transAxes, ha="left", va="top", fontsize=fsz)); yy -= dy
            for col, txt in bx.get("entries", []):
                if col is not None: _bx_art.append(ax.text(x0_, yy, "\u25a0", transform=ax.transAxes, ha="left", va="top", fontsize=fsz + 1.5, color=f(col)))
                _bx_art.append(ax.text(x0_ + (0.030 if col is not None else 0.0), yy, _mt(txt), transform=ax.transAxes, ha="left", va="top", fontsize=fsz)); yy -= dy
            for txt in bx.get("lines", []): _bx_art.append(ax.text(x0_, yy, _mt(txt.replace("Rwp", "R$_{wp}$")), transform=ax.transAxes, ha="left", va="top", fontsize=fsz)); yy -= dy
            if bx.get("side") == "right":                    # a box at the right edge: kept inside the frame, measured on the real letters
                try:
                    rr = fig.canvas.get_renderer(); aw = ax.get_window_extent(rr)
                    over = max((t_.get_window_extent(rr).x1 - aw.x1) / aw.width for t_ in _bx_art if hasattr(t_, "get_text")) + 0.012
                    if over > 0:
                        from matplotlib.transforms import ScaledTranslation as _ST
                        for t_ in _bx_art: t_.set_transform(t_.get_transform() + _ST(-over * aw.width / fig.dpi, 0, fig.dpi_scale_trans))
                except Exception:
                    pass
        if p.get("side"):
            ax_h = max(0.2, ax.get_position().height * fig.get_size_inches()[1]); nl_ = len(p["side"])
            fsz = max(4.5, min(small, ax_h * 72 * 0.92 / (nl_ * 1.4 + 0.3))); dyf = (fsz * 1.4 / 72) / ax_h      # always fits the panel height
            for k_, (txt, b_) in enumerate(p["side"]):
                ax.text(1.02, 0.96 - k_ * dyf, txt, transform=ax.transAxes, ha="left", va="top", fontsize=fsz + (0.8 if b_ else 0), fontweight="bold" if b_ else "normal", clip_on=False)
        if p.get("rows"):
            import matplotlib.transforms as mt; tr = mt.blended_transform_factory(ax.transAxes, ax.transData)
            for yy, txt, col in p["rows"]: ax.text(1.005, yy, txt, transform=tr, ha="left", va="center", fontsize=small, color=f(col), clip_on=False)
        for xv, txt in p["vlines"]:
            ax.axvline(xv, color=f(NAVY), lw=0.8, ls="--")
            if txt: ax.text(xv, p["ylim"][1] * 0.985, " " + txt, rotation=90, ha="right", va="top", fontsize=small, color=f(NAVY))
        ax.set_ylim(*(p.get("_ylog_lim") or p["ylim"])); ax.set_ylabel(_mt(p["yname"]), fontsize=fs)
        if p.get("ylog"): ax.set_yscale("log"); ax.set_ylim(*p["_ylog_lim"])
        if spec.get("xlog"): ax.set_xscale("log")
        ax.tick_params(direction="in", which="both", top=True, right=True, labelbottom=(i == len(spec["panels"]) - 1), labelsize=fs - 1, width=0.6 * axis_w, pad=3)
        ax.tick_params(which="major", length=0.42 * fs); ax.tick_params(which="minor", length=0.24 * fs)
        if not spec.get("xlog"):
            from matplotlib.ticker import AutoMinorLocator
            ax.xaxis.set_minor_locator(AutoMinorLocator(5 if (abs(spec["xlim"][1] - spec["xlim"][0]) > 30 and spec.get("lam")) else 2))
            if p.get("yticks", True): ax.yaxis.set_minor_locator(AutoMinorLocator(2))
        for sp_ in ax.spines.values(): sp_.set_linewidth(axis_w)
        y2 = p.get("y2")
        if y2:
            ax2 = ax.twinx(); ax.tick_params(right=False)
            for c in y2["curves"]: ax2.plot(c["x"], c["y"], "-", lw=curve_w, color=f(c["colour"]))
            ax2.set_ylim(*y2["ylim"]); ax2.set_ylabel(_mt(y2["yname"]), fontsize=fs, color=f(y2["curves"][0]["colour"]))
            ax2.tick_params(direction="in", which="both", labelsize=fs - 1, width=0.6 * axis_w, length=0.42 * fs, pad=3); ax2.axhline(0, color=f(y2["curves"][0]["colour"]), lw=0.5, alpha=0.5, zorder=0)
            for sp_ in ax2.spines.values(): sp_.set_linewidth(axis_w)
            for pos, py, txt, lx, ly in y2.get("placed", []):
                ax2.text(lx, ly, txt, ha="center", va="bottom", fontsize=max(5.5, small * y2.get("lab_pt", 12) / 15.0), fontweight="bold", color=f(NAVY))
                if ly - py > 0.06 * (y2["ylim"][1] - y2["ylim"][0]) or abs(lx - pos) > 1e-9: ax2.plot([pos, lx], [py + 0.005 * (y2["ylim"][1] - y2["ylim"][0]), ly], "-", lw=0.6, color=f(NAVY))
        if p["legend"] and len(visible(p)) > 1: ax.legend(frameon=False, fontsize=small, loc="upper left" if (p.get("inset") or {}).get("curves") else "upper right", ncol=2 if p.get("ylog") and len(visible(p)) > 4 else 1)
    axes[0].set_xlim(*spec["xlim"]); axes[-1].set_xlabel(_mt(spec["xname"]), fontsize=fs)
    if spec.get("xcats"):                                          # names instead of numbers under the axis (bars, boxes)
        axes[-1].set_xticks([q_[0] for q_ in spec["xcats"]]); axes[-1].set_xticklabels([str(q_[1]) for q_ in spec["xcats"]], fontsize=small, rotation=0 if max(len(str(q_[1])) for q_ in spec["xcats"]) * len(spec["xcats"]) < 70 else 30, ha="center" if max(len(str(q_[1])) for q_ in spec["xcats"]) * len(spec["xcats"]) < 70 else "right")
        for a_ in axes: a_.tick_params(axis="x", which="minor", bottom=False, top=False); a_.tick_params(axis="x", which="major", top=False)
    if spec.get("legend_row"):
        from matplotlib.lines import Line2D
        hd = [Line2D([], [], color=f(c_), lw=curve_w if not l_.startswith("Bragg") else 0, marker="|" if l_.startswith("Bragg") else None, ms=8, mew=1.2) for c_, l_ in spec["legend_row"]]
        axes[0].legend(hd, [l_ for _, l_ in spec["legend_row"]], loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(hd), frameon=False, fontsize=small, handlelength=1.8, columnspacing=1.4)
    foot_ = spec.get("footer") or []
    if foot_:
        aw_ = axes[-1].get_position().width * fig.get_size_inches()[0] * 72                        # axis width in points
        ffs = max(4.5, min(small, aw_ / (max(sum(len(t_) + 3 for _, t_ in line) for line in foot_) * 0.55)))
        for k_, line in enumerate(foot_):
            xo = 0.0
            if len({c_ for c_, _ in line}) == 1: line = [(line[0][0], "     ".join(t_ for _, t_ in line))]      # one colour: one evenly spaced line of text
            for col, txt in line:
                axes[-1].annotate(_mt(txt), xy=(0, 0), xycoords="axes fraction", xytext=(xo, -(fs * 3.4) - ffs * 1.35 * k_), textcoords="offset points", fontsize=ffs, color=f(col), va="top", ha="left", annotation_clip=False)
                xo += (len(txt) + 3) * ffs * 0.55
    if title and spec.get("no_title"): pass
    elif title:
        note = textwrap.wrap(spec.get("note", ""), 95)
        axes[0].set_title(spec["title"], fontsize=fs, loc="left", fontweight="bold", pad=6 + 11 * len(note))
        if note: axes[0].text(0, 1.01, "\n".join(note), transform=axes[0].transAxes, fontsize=small, va="bottom", ha="left")
    elif letter: axes[0].set_title(f"({letter})", fontsize=fs + 1, loc="left", fontweight="bold", pad=3)
    return axes

def _engine(fig, name):
    try: fig.set_layout_engine(name)
    except Exception: pass

def preview_figure(spec, fig=None, curve_w=1.5, axis_w=1.5, keep_aspect=False):
    """keep_aspect: show a figure that has its own page size (stacked figures) in those proportions inside the canvas."""
    from matplotlib.figure import Figure
    if spec.get("figtype") and spec.get("_book") is not None and TG is not None:
        fig = fig or Figure(figsize=(TG.FIG_W, TG.FIG_H), dpi=100)
        try: TG.draw(spec["figtype"], spec["_book"], fig)
        except TG.NeedInput as e: fig.clear(); fig.text(0.5, 0.5, str(e), ha="center", va="center", wrap=True, fontsize=12)
        return fig
    apply_style(); fig = fig or Figure(figsize=(7.2, 5.2), dpi=100); fig.clear(); _engine(fig, "none")
    side = any(p.get("side") for p in spec["panels"])
    nf = len(spec.get("footer") or []); win, hin = fig.get_size_inches()
    x0, wf, y0, hf = 0.0, 1.0, 0.0, 1.0
    if keep_aspect and spec.get("page_in"):
        tgt = spec["page_in"][0] / spec["page_in"][1]
        if win / hin > tgt: wf = tgt * hin / win; x0 = (1 - wf) / 2
        else: hf = (win / tgt) / hin; y0 = (1 - hf) / 2
    heff = hin * hf
    bottom = min(0.42, (0.68 + 0.19 * nf) / heff) if nf else 0.1
    top = 1 - 0.42 / heff if spec.get("legend_row") else 0.93 if spec.get("cols") else 0.88
    _draw(spec, fig, fig.add_gridspec(1, 1, left=x0 + (0.085 if spec.get("cols") else 0.1) * wf, right=x0 + (0.76 if side else 0.975 if spec.get("cols") else 0.9) * wf, top=y0 + top * hf, bottom=y0 + bottom * hf)[0], curve_w, axis_w); return apply_look(fig, spec.get("fmt"))

def board_figure(board, fig=None, curve_w=1.5, axis_w=1.5, fs=8.0):
    """The panel figure. Without a figure given, one of exactly the chosen size is made (for saving)."""
    from matplotlib.figure import Figure
    apply_style(); fig = fig or Figure(figsize=board.size_in(), dpi=100); fig.clear(); _engine(fig, "constrained")
    try: fig.get_layout_engine().set(h_pad=0.03, w_pad=0.03, hspace=0, wspace=0)
    except Exception: pass
    r, c = board.grid; outer = fig.add_gridspec(r, c); n = len(board.members)
    for i, m in enumerate(board.members): _draw(m.spec, fig, outer[i // c, i % c], curve_w, axis_w, fs, title=False, letter=chr(97 + i) if n > 1 else None)
    return apply_look(fig)

def export_board(board, outdir, curve_w=1.5, axis_w=1.5, png=True, pdf=True):
    """Save the panel figure at its exact size: PNG (600 dpi), PDF and SVG with text kept as text."""
    import matplotlib; from matplotlib.backends.backend_agg import FigureCanvasAgg
    matplotlib.rcParams["svg.fonttype"] = "none"; matplotlib.rcParams["pdf.fonttype"] = 42
    fig = board_figure(board, None, curve_w, axis_w); FigureCanvasAgg(fig); out = []
    for ext, on in ((".png", png), (".pdf", pdf), (".svg", True)):
        if on: fig.savefig(os.path.join(outdir, board.name + ext), dpi=600); out.append(board.name + ext)
    return out

def final_size(it, width_mm=None, max_h_mm=None, fs=None):
    """The printed size of a figure and its letter size: (width in, height in, pt). ONE place decides this, for the app's own
    publication files and for the page of the Origin graph, so a journal choice gives both the same size."""
    spec = it.spec; comb = isinstance(it, Combined) or len(spec["panels"]) > 2 or any(p_.get("inset") for p_ in spec["panels"])      # a graph with an inset needs the full width
    W = (width_mm or PUB_WIDTHS["combined" if comb else "single"]) / 25.4
    pi = spec.get("page_in"); fs = float(fs) if fs else (8.0 if W < 6.2 else 9.0)
    npan = len(spec["panels"]); H = W * (pi[1] / pi[0]) if pi else W * (0.62 if npan == 1 else 0.74)
    if pi and spec.get("hspace") == 0.0 and npan > 2: H = min(H, 9.3)                 # a stacked figure must still fit a page (236 mm)
    if max_h_mm: H = min(H, max_h_mm / 25.4)                                         # the journal's page depth
    return W, H, fs

def publication_figure(it, width_mm=None, curve_w=1.5, axis_w=1.5, fs=None, max_h_mm=None, sheet=None):
    """The figure at its final printed size. Width: full page width for combined figures, 1.5 columns for one graph (or your own
    value, or the column width of the chosen journal). Letters are 8-9 pt unless the journal template says otherwise; no title
    inside the figure. sheet=(header, caption): the figure is put at its true size on an A4 sheet with a header, a dashed
    outline of its final size and its draft caption (the preview of a paper set)."""
    from matplotlib.figure import Figure; from matplotlib.backends.backend_agg import FigureCanvasAgg
    if it.spec.get("figtype") and TG is not None:                 # gallery graph types: landscape page of their own
        fig = Figure(figsize=(TG.FIG_W, TG.FIG_H), dpi=100); FigureCanvasAgg(fig); TG.draw(it.spec["figtype"], it.spec["_book"], fig); fig.final_mm = (TG.FIG_W * 25.4, TG.FIG_H * 25.4); return fig
    apply_style(); spec = it.spec; W, H, fs = final_size(it, width_mm, max_h_mm, fs); pi = spec.get("page_in"); npan = len(spec["panels"])
    Wc, Hc, x0, y0 = W, H, 0.0, 0.0
    if sheet: Wc, Hc = max(8.27, W + 0.6), max(11.69, H + 2.6); x0 = (Wc - W) / 2; y0 = Hc - 0.95 - H
    fig = Figure(figsize=(Wc, Hc), dpi=100); FigureCanvasAgg(fig); _engine(fig, "none")
    side = any(p.get("side") for p in spec["panels"]); rows = any(p.get("rows") for p in spec["panels"]); y2 = any(p.get("y2") for p in spec["panels"]); nf = len(spec.get("footer") or [])
    left = (fs * (5.4 if any(p.get('yticks', True) for p in spec['panels']) else 3.0)) / 72; right = 1.75 if side else (fs * 5.4) / 72 if y2 else 0.42 if rows else 0.20
    top = (fs * 2.6) / 72 if (spec.get("legend_row") or spec.get("cols")) else 0.08; bottom = (fs * 3.9) / 72 + nf * (fs * 1.5) / 72
    _draw(spec, fig, fig.add_gridspec(1, 1, left=(x0 + left) / Wc, right=(x0 + W - right) / Wc, top=(y0 + H - top) / Hc, bottom=(y0 + bottom) / Hc)[0], curve_w, axis_w, fs, title=False)
    fig.final_mm = (W * 25.4, H * 25.4)
    if sheet:
        import textwrap; from matplotlib.patches import Rectangle
        fig.add_artist(Rectangle((x0 / Wc, y0 / Hc), W / Wc, H / Hc, transform=fig.transFigure, fill=False, ls=(0, (4, 4)), lw=0.5, ec=(0.6, 0.6, 0.6)))
        fig.text(x0 / Wc, 1 - 0.45 / Hc, sheet[0] if len(sheet[0]) <= 88 else sheet[0][:86] + " …", fontsize=11, fontweight="bold", va="top", ha="left")
        fig.text(x0 / Wc, 1 - 0.70 / Hc, f"final size {W * 25.4:.0f} x {H * 25.4:.0f} mm (dashed outline), letters {fs:g} pt, shown at true size when printed at 100 %", fontsize=8, color=(0.35, 0.35, 0.35), va="top", ha="left")
        fig.text(x0 / Wc, (y0 - 0.25) / Hc, "\n".join(textwrap.wrap("Draft caption: " + sheet[1], int(W * 25.4 * 0.62))[:9]), fontsize=8, va="top", ha="left")
    return apply_look(fig, (getattr(it, "spec", None) or {}).get("fmt"))

EXPORTS = {}                                              # base name -> what was really made (size, smallest letters, font, resolution), for the journal check
def write_figure_provenance(base, it, settings=None, confirmed=None):
    """<base>_provenance.json for a saved figure of the app: when, which version, the SHA-256 of the input file(s), the recipe in use, peak labels,
    phase library entries, temperature intervals and the settings. No data rows, no keys."""
    import hashlib, datetime, json as _j
    members = list(getattr(it, "members", None) or [it]); inputs = []
    for m in members:
        p = getattr(m, "path", None)
        try:
            if p and os.path.isfile(p):
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for blk in iter(lambda: f.read(1 << 20), b""): h.update(blk)
                if not any(i["file"] == os.path.basename(p) for i in inputs): inputs.append({"file": os.path.basename(p), "sha256": h.hexdigest()})
        except OSError: pass
    labels, ivs, phases = [], [], []
    for m in members:
        for pn in ((getattr(m, "spec", None) or {}).get("panels") or []):
            for x_, t_, _y in list(pn.get("labels") or []) + list((pn.get("y2") or {}).get("labels") or []):
                try: labels.append({"x": float(x_), "text": str(t_)})
                except (TypeError, ValueError): pass
        r = getattr(m, "results", None)
        try:
            if getattr(m, "kind", "") == "TGA" and r is not None and "From (\u00b0C)" in r.columns:
                ivs += [{"from": float(a), "to": float(b)} for a, b in zip(r["From (\u00b0C)"], r["To (\u00b0C)"])]
        except Exception: pass
        if getattr(m, "kind", "") == "XRD": phases += [str(x) for x in (getattr(m, "record", None) or []) if "phase" in str(x).lower()][:20]
    appdir = (settings or {}).get("app_dir") or os.path.dirname(os.path.abspath(__file__)); lf = os.path.join(appdir, "learned_formats.json"); rec = None
    try:
        if os.path.isfile(lf): rec = {"learned_formats.json": hashlib.sha256(open(lf, "rb").read()).hexdigest()}
    except OSError: pass
    d = {"written": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "app": "Origin Plot Studio", "app_version": PROVENANCE_VERSION, "app_build": VERSION, "figure": os.path.basename(base),
         "input_files": inputs, "active_recipe": rec, "peak_labels": labels, "phase_library_entries": phases, "temperature_intervals": ivs,
         "recipe_configuration": {"kind": getattr(it, "kind", ""), "custom": getattr(it, "custom", None) or None, "options": {k: v for k, v in (settings or {}).items() if isinstance(v, (str, int, float, bool)) and "key" not in k.lower()}},
         "confirmed_assistant_actions": list(confirmed or [])}
    p = base + "_provenance.json"
    with open(p, "w", encoding="utf-8") as f: _j.dump(d, f, indent=1, ensure_ascii=False, default=str)
    return p

def export_publication(it, outdir, width_mm=None, curve_w=1.5, axis_w=1.5, name=None, fs=None, max_h_mm=None, eps=False, dpi=600):
    """Save one graph in journal form: PNG at 600 dpi, TIFF at the resolution the journal asks for bitmap line art (600 dpi
    without a journal), PDF and SVG (and EPS for a journal template) with the text kept as text. Returns the file names."""
    os.makedirs(outdir, exist_ok=True); fig = publication_figure(it, width_mm, curve_w, axis_w, fs, max_h_mm); out = []
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", name or f"{getattr(it, 'file', 'figure')}_{it.name}").strip("_")
    try:
        import matplotlib.text as _mt, matplotlib.font_manager as _fm
        sizes_ = [t_.get_fontsize() for t_ in fig.findobj(_mt.Text) if t_.get_visible() and str(t_.get_text()).strip()]
        font_ = _fm.FontProperties(fname=_fm.findfont(_fm.FontProperties(family=__import__("matplotlib").rcParams["font.family"]))).get_name()
    except Exception: sizes_, font_ = [], ""
    EXPORTS[base] = dict(min_pt=min(sizes_) if sizes_ else None, font=font_, tif_dpi=int(dpi), curve=curve_w, axis=axis_w, eps=bool(eps), folder=outdir)
    for ext, kw in ((".png", dict(dpi=600)), (".tif", dict(dpi=int(dpi), pil_kwargs={"compression": "tiff_lzw"})), (".pdf", {}), (".svg", {})) + (((".eps", {}),) if eps else ()):
        try:
            import warnings, logging; logging.getLogger("matplotlib.backends.backend_ps").setLevel(logging.ERROR)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore"); fig.savefig(os.path.join(outdir, base + ext), **kw)      # (EPS has no transparency: a shaded band is drawn solid there)
            out.append(base + ext)
        except Exception as e: out.append(f"({ext} not saved: {e})")
    sp_ = getattr(it, "spec", None) or {}
    if sp_.get("figtype") and sp_.get("_book") is not None:      # e.g. G10 with several samples: the bar chart of Q at a time as its own figure
        try:
            for suf, drawer in TG.extra_figures(sp_["figtype"], sp_["_book"]):
                out += [os.path.basename(f_) for f_ in TG.save_extra(drawer, sp_["_book"], outdir, f"{base}_{suf}", ("png", "pdf", "svg"), dpi=600)]
        except Exception as e: out.append(f"(extra figure not saved: {e})")
    w, h = fig.get_size_inches(); EXPORTS[base].update(width_mm=w * 25.4, height_mm=h * 25.4, files=list(out))
    try:
        with open(os.path.join(outdir, "captions.txt"), "a", encoding="utf-8") as f: f.write(f"{base}  ({w * 25.4:.0f} x {h * 25.4:.0f} mm)\n   {caption(it)}\n\n")
    except Exception: pass
    return out, (w * 25.4, h * 25.4)

# ============================================================================= journal templates
# Figure requirements as the publishers state them on their own author pages (read in November 2026). A journal can ask for
# something else in its own guide for authors: that guide wins. None = the publisher gives no number.
JOURNALS = {
    "My own settings (no journal)": None,
    "Elsevier (Cem. Concr. Res., Constr. Build. Mater., Cem. Concr. Compos. ...)": dict(single=90, onehalf=140, double=190, max_h=None, fs=8, text="7 pt for normal text, nothing below 6 pt", fonts="Arial, Helvetica, Times, Courier, Symbol",
        line=(0.1, 1.5), dpi="bitmap line art 1000 dpi, photographs 300 dpi, combinations 500 dpi", files="EPS or PDF for line art; TIFF or JPEG for photographs",
        source="elsevier.com > artwork and media instructions (artwork sizing, artwork types)"),
    "Springer (Materials and Structures, J. Mater. Sci. ...)": dict(single=84, onehalf=None, double=174, max_h=234, fs=10, text="lettering 8-12 pt", fonts="Helvetica or Arial",
        line=(0.3, None), dpi="bitmap line art 1200 dpi, photographs 300 dpi, combinations 600 dpi", files="EPS for vector graphics; TIFF for photographs",
        source="link.springer.com > submission guidelines > Artwork and Illustrations Guidelines"),
    "Royal Society of Chemistry (RSC Advances, Green Chem. ...)": dict(single=83, onehalf=None, double=171, max_h=233, fs=8, text="clearly legible (7 pt Arial/Helvetica is asked for chemical structures)", fonts="Arial or Helvetica",
        line=(None, None), dpi="600 dpi or more", files="TIFF preferred; EPS or PDF are converted to TIFF", source="rsc.org > prepare and format > figures, graphics, images"),
    "Wiley": dict(single=80, onehalf=None, double=180, max_h=None, fs=8, text="large enough for easy reading (no number given)", fonts="not stated",
        line=(None, None), dpi="line art 600 dpi, photographs 300 dpi", files="PDF for line art; PNG or TIFF for images", source="authors.wiley.com > guidelines for the preparation of figures"),
    "Nature journals": dict(single=89, onehalf=136, double=183, max_h=247, fs=7, text="5-7 pt, panel letters 8 pt bold", fonts="Helvetica or Arial",
        line=(0.25, 1.0), dpi="photographs 300-600 dpi", files="PDF, EPS or AI for graphs; TIFF for photographs", source="nature.com > for authors > final submission"),
    "Taylor & Francis": dict(single=None, onehalf=None, double=None, max_h=None, fs=8, text="consistent size (no number given)", fonts="Times, Helvetica, Arial or Symbol, embedded",
        line=(0.3, None), dpi="line art 1200 dpi, greyscale 600 dpi, colour 300 dpi", files="EPS/PS for line art; TIFF or JPEG for review", source="authorservices.taylorandfrancis.com > submit electronic artwork"),
    "MDPI (Materials, Buildings, Minerals ...)": dict(single=None, onehalf=None, double=None, max_h=None, fs=8, text="no number given for figures", fonts="not stated",
        line=(None, None), dpi="preferably 600 dpi or more", files="PNG, JPEG or TIFF", source="mdpi.com > instructions for authors > preparing figures, schemes and tables"),
}

# Requirements that can be checked on the finished files: resolution of bitmap line art (dpi), the smallest letters allowed (pt).
# url = the publisher's page; checked = when it was read; profile = version of this entry. A journal's own guide for authors wins.
for _k, _e in (("Elsevier", dict(dpi_n=1000, min_pt=6, url="https://www.elsevier.com/en-gb/about/policies-and-standards/author/artwork-and-media-instructions/artwork-types")),
               ("Springer", dict(dpi_n=1200, min_pt=8, url="https://link.springer.com/journal/11527/submission-guidelines")), ("Royal", dict(dpi_n=600, min_pt=None, url="")),
               ("Wiley", dict(dpi_n=600, min_pt=None, url="")), ("Nature", dict(dpi_n=600, min_pt=5, url="")), ("Taylor", dict(dpi_n=1200, min_pt=None, url="")), ("MDPI", dict(dpi_n=600, min_pt=None, url=""))):
    for _n, _v in JOURNALS.items():
        if _v and _n.startswith(_k): _v.update(_e, checked="November 2026", profile="2")

def check_publication(base, journal):
    """Check the FILES that were made for one figure against the profile of the journal (not the settings that were asked for):
    size, resolution of the TIFF, vector files, smallest letters, line weights, font. Returns (lines, number failed)."""
    t = JOURNALS.get(str(journal)) if journal else None; e = EXPORTS.get(base)
    if not t or not e: return [], 0
    out = []; bad = 0; d = e["folder"]
    def line(ok, what):
        nonlocal bad
        bad += (ok is False); out.append(("PASS  " if ok else "FAIL  " if ok is False else "INFO  ") + what)
    wide = [w_ for w_ in (t.get("single"), t.get("onehalf"), t.get("double")) if w_]
    if wide: line(any(abs(e["width_mm"] - w_) <= 0.6 for w_ in wide), f"width {e['width_mm']:.1f} mm (column widths of the publisher: {', '.join(f'{w_:g}' for w_ in wide)} mm)")
    else: line(None, f"width {e['width_mm']:.1f} mm (the publisher gives no column width)")
    if t.get("max_h"): line(e["height_mm"] <= t["max_h"] + 0.6, f"height {e['height_mm']:.1f} mm (at most {t['max_h']:g} mm)")
    f = os.path.join(d, base + ".tif")
    if os.path.exists(f) and os.path.getsize(f) > 0:
        try:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(f) as im: px = im.size[0]
            real = px / (e["width_mm"] / 25.4); line(real >= t["dpi_n"] - 2, f"TIFF: {px} pixels wide = {real:.0f} dpi at the printed width (bitmap line art: at least {t['dpi_n']} dpi)")
        except Exception as ex: line(False, f"TIFF could not be opened to check it ({str(ex)[:80]})")
    else: line(False, "TIFF was not made" + "".join(f" {x_}" for x_ in e.get("files", []) if x_.startswith("(.tif")))
    for ext in (".pdf", ".eps"):
        f = os.path.join(d, base + ext); line(os.path.exists(f) and os.path.getsize(f) > 0, f"vector file {ext} made (text kept as text)")
    if e.get("min_pt") is not None:
        if t.get("min_pt"): line(e["min_pt"] >= t["min_pt"] - 0.05, f"smallest letters {e['min_pt']:.1f} pt (not below {t['min_pt']:g} pt; {t['text']})")
        else: line(None, f"smallest letters {e['min_pt']:.1f} pt (the publisher gives no number: {t['text']})")
    lo, hi = t.get("line") or (None, None)
    for nm_, v_ in (("curves", e["curve"]), ("axes", e["axis"])):
        if lo is None and hi is None: line(None, f"{nm_} {v_:g} pt (the publisher gives no line weight)")
        else: line((lo is None or v_ >= lo) and (hi is None or v_ <= hi), f"{nm_} {v_:g} pt (allowed: " + (f"from {lo:g} pt" if lo is not None else "") + (" " if lo is not None and hi is not None else "") + (f"up to {hi:g} pt" if hi is not None else "") + ")")
    want = str(t.get("fonts") or "")
    if e.get("font") and want and want != "not stated": line(any(w_.strip().lower() in e["font"].lower() for w_ in re.split(r",| or ", want) if w_.strip()), f"font used: {e['font']} (asked for: {want})")
    elif e.get("font"): line(None, f"font used: {e['font']}")
    return out, bad

def write_journal_check(pubdir, journal, checks):
    """journal_check.txt: every figure with its checks. checks = [(base, lines, failed)]."""
    t = JOURNALS.get(str(journal)) if journal else None
    if not t or not checks: return None
    f = os.path.join(pubdir, "journal_check.txt")
    with open(f, "w", encoding="utf-8") as h:
        h.write(f"Journal check of the publication files made by the app (drawn by the app itself with matplotlib, not by Origin)\nProfile: {journal}\n"
                f"Source: {t.get('url') or t.get('source')}  (read {t.get('checked')}; profile version {t.get('profile')})\n"
                "The files themselves were measured. PASS / FAIL refer to the publisher's general artwork rules for line art; the guide for authors of your journal wins.\n"
                "Not checked: colour mode, embedded fonts in EPS, file size limits, and the graph windows in Origin.\n\n")
        for base, lines, bad in checks: h.write(f"{base}: " + ("all checks passed" if not bad else f"{bad} check(s) FAILED") + "\n" + "".join(f"   {l_}\n" for l_ in lines) + "\n")
    return f

def journal_args(it, name):
    """Size, letters and files of one figure for the chosen journal: (arguments for export_publication, words for the plan)."""
    t = JOURNALS.get(str(name)) if name else None
    if not t: return {}, ""
    spec = it.spec; wide = isinstance(it, Combined) or bool(spec.get("cols")) or len(spec["panels"]) > 2 or any(p_.get("inset") or p_.get("side") for p_ in spec["panels"])
    w = t["double"] if wide else (t.get("onehalf") or t["double"]); col = "double column" if (wide or not t.get("onehalf")) else "1.5 columns"
    return dict(width_mm=w, fs=t["fs"], max_h_mm=t.get("max_h"), eps=True, dpi=t.get("dpi_n", 600)), (col if w else "size of your own settings")

def journal_lines(name, curve_w=1.5):
    """What the chosen journal asks for, and what does not fit it, as lines of text."""
    t = JOURNALS.get(str(name)) if name else None
    if not t: return ["Journal template: none. Figures use your own settings: 140 mm for one graph, 175 mm for combined figures, 8-9 pt letters."]
    L = [f"Journal template: {name}", "  widths: " + (f"single column {t['single']} mm" + (f", 1.5 columns {t['onehalf']} mm" if t.get("onehalf") else "") + f", double column {t['double']} mm" if t.get("double") else "not stated: your own settings are used")
         + (f"; not higher than {t['max_h']} mm" if t.get("max_h") else ""), f"  letters: {t['text']}; fonts: {t['fonts']}. The app uses Arial at {t['fs']} pt for the axis titles.",
         f"  resolution: {t['dpi']}. files: {t['files']}.", "  The app writes PDF, EPS and SVG as vector files (no resolution limit) and PNG and TIFF at 600 dpi.", f"  source: {t['source']}. The journal's own guide for authors wins: check it."]
    lo, hi = t["line"]
    if hi and curve_w > hi + 1e-9: L.append(f"  !! your curves are {curve_w:g} pt; this publisher asks for lines of at most {hi:g} pt. Lower 'Curves' under Look and saving if the journal insists.")
    if lo and curve_w < lo - 1e-9: L.append(f"  !! your curves are {curve_w:g} pt; this publisher asks for lines of at least {lo:g} pt.")
    return L

def paper_preview(singles, opt, main_names, journal, path, curve_w=1.5, axis_w=1.5):
    """Paper_set_preview.pdf: page 1 lists every figure and table of the paper set with its final size and what the journal
    asks for; then every figure at its true printed size on its own A4 sheet, with its draft caption. Nothing is drawn in
    Origin. Returns the lines of the plan."""
    from matplotlib.figure import Figure; from matplotlib.backends.backend_agg import FigureCanvasAgg; from matplotlib.backends.backend_pdf import PdfPages
    ps = paper_set(singles, opt, main_names); plan = journal_lines(journal, curve_w) + [""]; pages = []
    try:
        for group, items, lines in (("Main text", ps["main"], ps["lines_main"]), ("Supplementary", ps["supp"], ps["lines_supp"])):
            plan.append(group); k = 0
            for ln in lines:
                if not ln.strip().startswith("Figure"): plan.append(ln); continue
                it = items[k]; k += 1; args, col = journal_args(it, journal); args.pop("eps", None); args.pop("dpi", None)
                fig = publication_figure(it, args.get("width_mm"), curve_w, axis_w, args.get("fs"), args.get("max_h_mm"), sheet=(ln.strip(), caption(it)))
                w, h = fig.final_mm; plan.append(f"{ln}   [{w:.0f} x {h:.0f} mm" + (f", {col}" if col else "") + "]"); pages.append(fig)
            plan.append("")
        if ps["missing"]: plan.append("!! not found among the fit graphs: " + ", ".join(ps["missing"]))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with PdfPages(path) as pdf:
            per = 62
            for i in range(0, len(plan), per):
                f0 = Figure(figsize=(8.27, 11.69), dpi=100); FigureCanvasAgg(f0); apply_style()
                f0.text(0.07, 0.95, "Paper set - preview" + ("" if i == 0 else " (continued)"), fontsize=14, fontweight="bold", va="top")
                f0.text(0.07, 0.92, "\n".join(l_[:118] for l_ in plan[i:i + per]), fontsize=8, va="top", family="sans-serif", linespacing=1.45)
                pdf.savefig(f0)
            for fig in pages: pdf.savefig(fig)
    finally:
        for it in ps["main"] + ps["supp"]: it.__dict__.pop("paper_name", None)
    return plan

# ============================================================================= record of what was done
# ============================================================================= record of what was done
WHAT = {"XRD": ("XRD pattern", "XRD patterns"), "FTIR": ("FTIR spectrum", "FTIR spectra"), "TGA": ("TG (left axis) and DTG (right axis; mass loss is negative) curves", "TG (top) and DTG (bottom; mass loss is negative) curves"),
        "Particle size": ("Particle size distribution (top) and cumulative curve (bottom)", "Particle size distributions (top) and cumulative curves (bottom)"),
        "Calorimetry": ("Isothermal calorimetry curve", "Isothermal calorimetry curves"), "DSC": ("DSC curve", "DSC curves"), "Fit (observed + calculated)": ("Observed and calculated patterns with the difference curve", "Observed and calculated patterns with the difference curves")}

def _join(names): return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]

def caption(it):
    """A first draft of a caption. It only states what the figure shows and how it was scaled; the author must edit it."""
    if getattr(it, "caption_text", None): return it.caption_text
    if isinstance(it, Board):
        if len(it.members) == 1: return caption(it.members[0])
        return " ".join(f"({chr(97 + i)}) {caption(m)}" for i, m in enumerate(it.members))
    names = list(dict.fromkeys(display_names(it.members))) if isinstance(it, Combined) else display_names([it]); s = it.spec
    if it.kind in WHAT:
        what = WHAT[it.kind][len(names) > 1]
        if it.kind == "Calorimetry" and len(s["panels"]) > 1: what += " (top: heat flow; bottom: cumulative heat)"
    else:
        what = (s["panels"][0]["yname"] or "Data").split(" (")[0] + " against " + s["xname"].split(" (")[0].lower(); vis = [c["label"] for _, c in visible(s["panels"][0])]
        if isinstance(it, Item) and len(vis) > 1: names = [str(v) for v in vis]
    return f"{what} of {_join(names)}." + (" " + s["note"] if s.get("note") else "")

IMPORTED = {}                                             # path -> what was read at import: full SHA-256, size, times, a private copy of the bytes
def import_stamp(path):
    """Note exactly which bytes are read: hash, size and a private copy (so a results folder can carry its inputs, and a file
    that changes on disk afterwards is noticed). Files above 200 MB are hashed but not copied."""
    try:
        b = open(path, "rb").read(); h = hashlib.sha256(b).hexdigest(); st = os.stat(path); now = datetime.datetime.now()
        info = dict(sha256=h, size=len(b), modified=f"{datetime.datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M:%S}", imported=f"{now:%Y-%m-%d %H:%M:%S}", copy=None, reader="Origin plot app " + VERSION)
        if len(b) <= 200e6:
            import tempfile
            d = os.path.join(tempfile.gettempdir(), "OriginPlotApp_imports"); os.makedirs(d, exist_ok=True); c = os.path.join(d, h[:16] + "_" + os.path.basename(path))
            if not os.path.exists(c):
                with open(c, "wb") as f: f.write(b)
            info["copy"] = c
        IMPORTED[path] = info
    except Exception: pass

def source_state(path):
    """'same' | 'changed' | 'missing' | 'unknown': the file on disk now, compared with what was imported."""
    i = IMPORTED.get(path)
    if not i: return "unknown"
    if not os.path.exists(path): return "missing"
    try: return "same" if hashlib.sha256(open(path, "rb").read()).hexdigest() == i["sha256"] else "changed"
    except Exception: return "unknown"

def _source(path):
    i = IMPORTED.get(path)
    if i:
        st = source_state(path)
        return (f"{path}  ({i['size']} bytes, last changed {i['modified'][:16]}, imported {i['imported'][:16]}, SHA-256 {i['sha256']})"
                + ("" if st == "same" else "  !! THE FILE ON DISK HAS CHANGED SINCE IT WAS IMPORTED: the graphs show the data as imported" if st == "changed" else "  !! the file is no longer at this place" if st == "missing" else ""))
    try:
        h = hashlib.sha256(open(path, "rb").read()).hexdigest(); st = os.stat(path)
        return f"{path}  ({st.st_size} bytes, last changed {datetime.datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M}, SHA-256 {h}, hashed when this record was written)"
    except Exception: return str(path)

def save_inputs(items, outdir):
    """Copy the data files of these graphs, as they were imported, into <outdir>/inputs with a list of their hashes, so the
    results folder is complete on its own: 'Open session' finds the files there on another computer. Returns message lines."""
    paths = list(dict.fromkeys(getattr(m, "path", None) for it in items for m in (getattr(it, "members", None) or [it]) if getattr(m, "path", None))); lines = []
    if not paths: return lines
    import shutil
    d = os.path.join(outdir, "inputs"); os.makedirs(d, exist_ok=True); rows = []; used = {}
    for p in paths:
        i = IMPORTED.get(p); nm = os.path.basename(p)
        if used.get(nm.lower(), p) != p: nm = f"{len(used)}_{nm}"
        used[nm.lower()] = p
        try:
            if i and i.get("copy") and os.path.exists(i["copy"]): shutil.copyfile(i["copy"], os.path.join(d, nm)); how = "the bytes that were imported"
            elif os.path.exists(p): shutil.copyfile(p, os.path.join(d, nm)); how = "the file as it is on disk NOW (no copy was kept at import)"; lines.append(f"note: {nm}: copied as it is now, not as imported")
            else: lines.append(f"note: {nm} could not be copied into inputs: the file is gone"); continue
            st = source_state(p)
            if st == "changed": lines.append(f"note: {p} has changed on disk since it was imported. The graphs and the copy in 'inputs' are the data as imported at {i['imported']}")
            rows.append(f"{nm}\n   from: {p}\n   SHA-256: {(i or {}).get('sha256', 'not recorded')}\n   size: {(i or {}).get('size', '?')} bytes; imported: {(i or {}).get('imported', '?')}; read by: {(i or {}).get('reader', 'Origin plot app ' + VERSION)}\n   copy holds: {how}\n")
        except Exception as e: lines.append(f"note: {nm} could not be copied into inputs ({str(e)[:100]})")
    try:
        with open(os.path.join(d, "inputs.txt"), "w", encoding="utf-8") as f: f.write("Data files of this results folder, as they were imported. With session.json this folder can be opened on another computer (File > Open session).\n\n" + "\n".join(rows))
    except Exception: pass
    return lines

def write_record(items, outdir, settings=None, outputs=None):
    """processing_record.txt / .json: for every figure, where the data came from and exactly what was done to it."""
    outputs = outputs or {}; now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M"); data = {"app": "Origin plot app " + VERSION, "written": now, "settings": settings or {}, "figures": []}
    L = [f"Processing record  -  Origin plot app {VERSION}", f"Written: {now}", "",
         "Your data files were only read; nothing in them was changed. The curves drawn are the measured values,",
         "unless a line below says that they were scaled, converted or averaged.", "", "Settings used:"]
    L += [f"  {k}: {v}" for k, v in (settings or {}).items()] + [""]
    for k, it in enumerate(items, 1):
        members = it.members if isinstance(it, (Combined, Board)) else [it]; leaves = []
        for m in members: leaves += m.members if isinstance(m, Combined) else [m]
        src = list(dict.fromkeys(_source(m.path) + f"  table '{m.name}'" for m in leaves)); cap = caption(it)
        steps = list(it.record)
        if isinstance(it, Combined):
            for m in it.members: steps += [f"[{m.file} / {m.name}] {r}" for r in m.record]
        L += [f"{k}. {it.title.strip()}", "   Files written: " + (", ".join(outputs.get(id(it), [])) or "-"), "   Data from:"] + ["     " + s for s in src] + ["   What was done:"] + ["     - " + s for s in steps]
        if it.warnings: L += ["   Please check:"] + ["     - " + w for w in it.warnings]
        L += ["   Draft caption (edit before you use it):", "     " + cap, ""]
        data["figures"].append({"title": it.title.strip(), "files": outputs.get(id(it), []), "sources": src, "steps": steps, "check": list(it.warnings), "draft_caption": cap})
    open(os.path.join(outdir, "processing_record.txt"), "w", encoding="utf-8").write("\n".join(L))
    json.dump(data, open(os.path.join(outdir, "processing_record.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    return "processing_record.txt"

# ============================================================================= the set of figures for a paper
PAPER_MAIN = "Reference"
try:
    import private_store as _ps; PAPER_MAIN = str(_ps.default("paper_main", PAPER_MAIN))          # your own default, from your private folder
except Exception: pass

def _rwp_line(it): return next((l_ for l_ in (it.spec["panels"][0].get("legendbox") or {}).get("lines", []) if l_.startswith("Rwp")), "")

def phase_table(fits):
    """Phase amounts (wt%) and Rwp of the refined samples as one table: a row per phase, a column per sample.
    The amounts are the ones in your files; Rwp is the value recomputed from the observed and calculated curves."""
    order = list(xs.CODE_NAMES); rows = {}; cols = []; rwp = {}; amo = {}
    for it in fits:
        nm = display_names([it])[0]; cols.append(nm); info = it.det.get("_info") or {}; idm = it.det.get("_idmap") or {}
        m = re.search(r"([\d.]+)\s*%", _rwp_line(it)); rwp[nm] = float(m.group(1)) if m else None
        if info.get("amorphous") is not None: amo[nm] = float(info["amorphous"])
        for r in info.get("phases") or []:
            if r.get("wt") is None: continue
            if str(r["name"]).lower().startswith("amorph"): amo[nm] = float(r["wt"]); continue
            cd = r.get("code") or xs.code_for(r["name"]); mean = idm.get(cd) or xs.CODE_NAMES.get(cd) or str(r["name"])
            k = (order.index(cd) if cd in order else 99, cd, mean[:1].upper() + mean[1:])
            rows.setdefault(k, {}); rows[k][nm] = rows[k].get(nm, 0.0) + float(r["wt"])
    out = [dict({"Phase": k[2], "Label": k[1]}, **{c: (round(v[c], 1) if c in v else "") for c in cols}) for k, v in sorted(rows.items())]
    if amo: out.append(dict({"Phase": "Amorphous / not identified", "Label": ""}, **{c: (round(amo[c], 1) if c in amo else "") for c in cols}))
    out.append(dict({"Phase": "Rwp (%)", "Label": ""}, **{c: (round(rwp[c], 2) if rwp.get(c) is not None else "") for c in cols}))
    return pd.DataFrame(out, columns=["Phase", "Label"] + cols)

PAPER_ORDER = ["XRD", "FTIR", "TGA", "DSC", "Particle size", "Calorimetry", "XY"]
PAPER_WHAT = {"XRD": "XRD patterns", "FTIR": "FTIR spectra", "TGA": "TG-DTG curves", "Particle size": "particle size distributions", "Calorimetry": "calorimetry curves", "DSC": "DSC curves", "XY": "data"}

def paper_set(singles, opt, main_names=PAPER_MAIN):
    """What a paper needs from everything that is loaded.
    XRD fits - main text: one stacked comparison of all refined samples, the sample pages you named, the table of phase
    amounts; supplementary: the other sample pages and the stacked profile fits.
    Every other kind of graph (XRD scans, FTIR, TG-DTG, particle size, calorimetry, your own data) - main text: the figure
    that compares the samples (stacked or overlaid, as the app decides), or the single graph when there is only one sample,
    and the table of its results; supplementary: the single graph of every sample."""
    opt = dict(opt or {}); fits = [s_ for s_ in singles if isinstance(s_, Item) and s_.kind.startswith("Fit") and s_.spec is not None]
    others = [s_ for s_ in singles if isinstance(s_, Item) and s_.spec is not None and not s_.kind.startswith("Fit") and s_.kind != "XRD peak list"]
    if not fits and not others: raise ValueError("there is no graph in the list, so there is nothing to make a paper set from")
    riet = [s_ for s_ in fits if "profile fit" not in _rwp_line(s_)]; prof = [s_ for s_ in fits if "profile fit" in _rwp_line(s_)]
    names = display_names(fits); cmap = {nm: PALETTE[i % len(PALETTE)] for i, nm in enumerate(dict.fromkeys(names))}
    short = lambda it: re.sub(r"\s*\(.*?\)", "", display_names([it])[0]).strip(); safe = lambda t: re.sub(r"[^A-Za-z0-9]+", "_", str(t)).strip("_")
    want = [w.strip() for w in re.split(r"[,;]+", str(main_names or "")) if w.strip()] if fits else []; chosen = []; missing = []
    for w in want:
        pool = [s_ for s_ in fits if not any(s_ is c for c in chosen)]
        hit = next((s_ for s_ in pool if norm(short(s_)) == norm(w)), None) or next((s_ for s_ in pool if norm(short(s_)).startswith(norm(w)) or norm(display_names([s_])[0]).startswith(norm(w))), None)
        if hit is not None: chosen.append(hit)
        else: missing.append(w)
    main, supp, lm, ls, tables = [], [], [], [], []; n = k = tn = 0
    def stacked(members):
        out = []; o2 = dict(opt, per_fig="All in one figure"); mx = MAXN["panels"]
        if len(members) > 3: o2["orientation"] = ORIENTATIONS[1]                    # more than three panels need a tall page
        for i in range(0, len(members), mx):
            ch = members[i:i + mx]
            if len(ch) < 2: continue
            c = Combined(ch, "panels", RULES["Fit (observed + calculated)"][1], f"_{i // mx + 1}" if len(members) > mx else "", cmap, o2); c.build(); out.append(c)
        return out
    for c in stacked(riet):
        n += 1; c.paper_name = f"Figure_{n}_XRD_fits_stacked"; main.append(c); lm.append(f"  Figure {n}: XRD fits, stacked comparison of " + _join(list(dict.fromkeys(display_names(c.members)))))
    for it in chosen:
        n += 1; pg = SamplePage(it, opt); pg.build(); pg.paper_name = f"Figure_{n}_XRD_{safe(short(it))}"; main.append(pg); lm.append(f"  Figure {n}: {display_names([it])[0]} - XRD pattern with assigned peaks and fit")
    for it in [s_ for s_ in riet + prof if not any(s_ is c for c in chosen)]:
        k += 1; pg = SamplePage(it, opt); pg.build(); pg.paper_name = f"Figure_S{k}_XRD_{safe(short(it))}"; supp.append(pg); ls.append(f"  Figure S{k}: {display_names([it])[0]} - XRD pattern with assigned peaks and fit")
    for c in stacked(prof):
        k += 1; c.paper_name = f"Figure_S{k}_XRD_profile_fits_stacked"; supp.append(c); ls.append(f"  Figure S{k}: stacked profile fits of " + _join(list(dict.fromkeys(display_names(c.members)))))
    if riet:
        tn += 1; tables.append(dict(file=f"Table_{tn}_XRD_phase_amounts", table=phase_table(riet), where="main", title=f"Table {tn}. Phase amounts (wt%) from the Rietveld refinements, and the weighted profile R-factor Rwp.",
                                   note="Phase amounts as given in your refinement files; Rwp recomputed from the observed and calculated curves. Check before use."))
        lm.append(f"  Table {tn}: phase amounts (wt%) and Rwp of " + _join(display_names(riet)))
    # every other kind of graph
    comb, _ = make_groups(others, "Decide for me", opt) if others else ([], []); comb = [c for c in comb if not isinstance(c, SamplePage)]
    inside = {id(m_) for c in comb for m_ in c.members}; ts = 0
    for kind in PAPER_ORDER + sorted({s_.kind for s_ in others} - set(PAPER_ORDER)):
        ss = [s_ for s_ in others if s_.kind == kind]; what = PAPER_WHAT.get(kind, kind)
        if not ss: continue
        for c in [c for c in comb if c.kind == kind]:
            n += 1; c.paper_name = f"Figure_{n}_{safe(kind)}_{c.label.replace(' ', '_')}{c.part}"; main.append(c)
            lm.append(f"  Figure {n}: {what}, {c.label}: " + _join(list(dict.fromkeys(display_names(c.members)))))
        for s_ in ss:
            if id(s_) in inside:
                k += 1; s_.paper_name = f"Figure_S{k}_{safe(kind)}_{safe(short(s_))}"; supp.append(s_); ls.append(f"  Figure S{k}: {display_names([s_])[0]} - {what}, single graph")
            else:
                n += 1; s_.paper_name = f"Figure_{n}_{safe(kind)}_{safe(short(s_))}"; main.append(s_); lm.append(f"  Figure {n}: {display_names([s_])[0]} - {what}")
        rows = [s_.results.assign(**{"Sample": display_names([s_])[0]}) for s_ in ss if s_.results is not None and len(s_.results)]
        if rows and kind != "XRD":                         # the peak table of an XRD scan is too long for a paper table; it is saved with the graph
            df = pd.concat(rows, ignore_index=True); df = df[["Sample"] + [c_ for c_ in df.columns if c_ != "Sample"]]
            if len(df) <= 40:
                tn += 1; tables.append(dict(file=f"Table_{tn}_{safe(kind)}", table=df, where="main", title=f"Table {tn}. Results from the {what}.", note="Computed by the app from your data as described in processing_record.txt. Check before use.")); lm.append(f"  Table {tn}: results from the {what}")
            else:
                ts += 1; tables.append(dict(file=f"Table_S{ts}_{safe(kind)}", table=df, where="supp", title=f"Table S{ts}. Results from the {what}.", note="Computed by the app from your data as described in processing_record.txt. Check before use.")); ls.append(f"  Table S{ts}: results from the {what} ({len(df)} rows)")
    return dict(main=main, supp=supp, tables=tables, lines_main=lm, lines_supp=ls, missing=missing, n_main=len(main), n_supp=len(supp))

class _whole_file:
    """Write an Excel file under a temporary name and give it its real name only when it is complete, so a write that
    fails never leaves a broken workbook behind."""
    def __init__(self, path): self.path = path; self.tmp = os.path.splitext(path)[0] + "_being_written.xlsx"
    def __enter__(self):
        try: os.remove(self.tmp)
        except OSError: pass
        return self.tmp
    def __exit__(self, et, ev, tb):
        if et is None: os.replace(self.tmp, self.path)
        else:
            try: os.remove(self.tmp)
            except OSError: pass
        return False

def write_table(table, path, note="", title="Table"):
    """The table as an Excel file (formatted, ready to copy into Word) and as CSV."""
    table.to_csv(os.path.splitext(path)[0] + ".csv", index=False, encoding="utf-8-sig")
    with _whole_file(path) as tmp_, pd.ExcelWriter(tmp_, engine="openpyxl") as w:
        table.to_excel(w, sheet_name="Table", index=False, startrow=1)
        try:
            from openpyxl.styles import Font, Alignment, Border, Side
            ws = w.book["Table"]; ws["A1"] = title; ws["A1"].font = Font(name="Arial", bold=True, size=10)
            thin = Side(style="thin"); nr = len(table) + 2; nc = len(table.columns); last_bold = str(table.iloc[-1, 0]).startswith("Rwp")
            for r in ws.iter_rows(min_row=2, max_row=nr, max_col=nc):
                for c in r:
                    c.font = Font(name="Arial", size=10, bold=(c.row == 2 or (c.row == nr and last_bold))); c.alignment = Alignment(horizontal="left" if c.column <= 2 else "center")
                    if isinstance(c.value, float): c.number_format = "0.00" if (c.row == nr and last_bold) else "0.0" if last_bold else "General"
                    if c.row == 2: c.border = Border(top=thin, bottom=thin)
                    if c.row == nr: c.border = Border(bottom=thin, top=thin if last_bold else None)
            for j in range(1, nc + 1):
                L = max([len(str(ws.cell(row=2, column=j).value))] + [len(str(v)) for v in table.iloc[:, j - 1].astype(str).head(60)]); ws.column_dimensions[ws.cell(row=2, column=j).column_letter].width = min(48, max(10, L + 2))
            if note: ws.cell(row=nr + 2, column=1, value=note).font = Font(name="Arial", size=9, italic=True)
        except Exception: pass

# ============================================================================= the standard workbook
WB_README = [("What this is", "One workbook with everything the Origin plot app needs for XRD fit graphs. Fill it in (or let the app write it with 'Save as one workbook'), then add it to the app."),
             ("Sheet Samples", "One row per sample. Sample = short name (it must be the start of the sheet names below). Display_name = the name written on the graphs. Group = samples with the same group are drawn in one stacked figure. Calculated_curve = 'Rietveld refinement' or 'Profile fit' (a profile fit is named as such on the graph)."),
             ("Sheets <Sample>_Profile", "The pattern: 2theta_deg, Yobs_counts, Ycalc_counts, Ydiff_counts (= Yobs - Ycalc), Background_counts (optional). One row per measured point."),
             ("Sheet Phases", "Optional. One row per phase of a sample: Phase_display_name, Label_code (the letter used on the peaks), Label_meaning, Weight_pct (from your refinement)."),
             ("Sheet Peak_Labels", "Optional. Your own checked peak labels: Sample, Label (a code such as A, or A+B, or (B) for a phase without a resolved peak), 2theta_deg. Without this sheet the app suggests labels itself."),
             ("Sheet Label_Key", "Optional. What each label code means: Label_code, Meaning."),
             ("Sheets <Sample>_Bragg", "Optional. Reflection positions of each phase (for tick rows): Phase_HighScore_name, Label_code, 2theta_deg."),
             ("Sheet Graphs", "A list of every graph in this workbook: its data sheet, the graph type the app gave it and the sample name. For your information; the app recognises each sheet again from its columns."),
             ("Other data sheets", "Any other table (XRD scan, FTIR, TGA, particle size, calorimetry, your own data): one sheet per table, the first row holds the column names with their units, the numbers follow. This is all the app needs to draw it."),
             ("Rule", "The app only reads this workbook. It never changes your numbers: Rwp is recomputed from Yobs and Ycalc, and a calculated curve is always drawn as it is given here.")]

def _sheet(name, used):
    b = re.sub(r"[^A-Za-z0-9]+", "_", str(name)).strip("_")[:22] or "Sample"; k = b; i = 2
    while k.lower() in used: k = f"{b}{i}"; i += 1
    used.add(k.lower()); return k

def convert_to_excel(paths, outdir=None, keep=()):
    """Turn data files of any kind the app reads (.xrdml, .brml, .ras, .uxd, instrument text files, CSV ...) into Excel
    workbooks: one workbook per file, next to the file (or in outdir), with a sheet per table, clean column names and a
    sheet File_info (source, wavelength, instrument). Returns (workbook paths, lines for the message box)."""
    outs, lines = [], []
    for p in paths:
        nm = os.path.basename(p)
        try:
            fresh, _ = load_file(p); ss = []; prepare(ss, fresh, {})
            ss = [s_ for s_ in ss if s_.spec is not None]
            if not ss: lines.append(f"  {nm}: I found no table of numbers in it"); continue
            base = os.path.splitext(nm)[0]; d_ = outdir or os.path.dirname(os.path.abspath(p)); os.makedirs(d_, exist_ok=True)
            out = os.path.join(d_, base + ("_app_format.xlsx" if p.lower().endswith((".xlsx", ".xlsm", ".xls")) else ".xlsx"))
            meta = xs.META.get(p) or {}; flat = []
            for k_, v_ in meta.items(): flat += [(f"{k_}: {a_}", b_) for a_, b_ in v_.items()] if isinstance(v_, dict) else [(k_, v_)]
            info = [("Source file", os.path.abspath(p)), ("Converted by", "Origin plot app " + VERSION), ("Converted on", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))] + [(str(a_), "" if b_ is None else str(b_)) for a_, b_ in flat]
            write_workbook(ss, out, info=info); outs.append(out)
            lines.append(f"  {nm}  ->  {os.path.basename(out)}: " + ", ".join(f"{display_names([s_])[0]} [{s_.kind}]" for s_ in ss[:8]) + (" ..." if len(ss) > 8 else ""))
        except Exception as e: lines.append(f"  {nm}: could not be converted ({e})")
        finally:
            if p not in keep: INFO.pop(p, None); _INFO_ONLY.discard(p)           # a converted file is not part of your list
    return outs, lines

PEEK_TYPES = (".csv", ".txt", ".dat", ".xy", ".xye", ".asc", ".tsv", ".prn", ".out", ".xlsx", ".xlsm", ".xls")

def _raw_rows(path, sheet=None, delimiter="auto"):
    """The cells of a file as text, row by row, exactly as they stand: (rows, sheet name or None). Rows are numbered from 1."""
    if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
        xl = pd.ExcelFile(path); nm = sheet if sheet in xl.sheet_names else next((n_ for n_ in xl.sheet_names if str(n_).strip().lower() == str(sheet or "").strip().lower()), None)
        if sheet and nm is None: raise ValueError(f"there is no sheet '{sheet}'. Sheets: " + ", ".join(map(str, xl.sheet_names)))
        nm = nm or xl.sheet_names[0]; df = xl.parse(nm, header=None, dtype=object)
        return [["" if (v is None or (isinstance(v, float) and np.isnan(v))) else v for v in r] for r in df.values.tolist()], nm
    lines = _text(path).splitlines(); d = str(delimiter or "auto").strip().lower()
    d = {"tab": "\t", "\\t": "\t", "semicolon": ";", "comma": ",", "space": " ", "spaces": " ", "whitespace": " ", "pipe": "|"}.get(d, d)
    if d == "auto":
        body = [l for l in lines if l.strip()][-40:]; d = max(("\t", ";", ",", "|", " "), key=lambda c: (sum(l.count(c) > 0 for l in body), -(" ,;|\t".index(c))))
    return [(l.split() if d == " " else [c.strip() for c in l.split(d)]) for l in lines], None

def peek_file(path, lines=40, width=220):
    """The beginning of a data file as text with row numbers, for deciding how to read it. Excel: the first rows of each sheet."""
    if not path.lower().endswith(PEEK_TYPES):
        with open(path, "rb") as f: b_ = f.read(4000)
        if b_[:2] not in (b"\xff\xfe", b"\xfe\xff") and sum(c < 9 or 13 < c < 32 for c in b_) > 0.02 * max(1, len(b_)):
            raise ValueError("this is not a text file (it is binary: a document, picture or instrument format). It cannot be read as a table; ask the user to export it as CSV, text or Excel")
    out = [f"FILE {os.path.basename(path)}"]
    if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
        xl = pd.ExcelFile(path)
        for nm in xl.sheet_names[:6]:
            df = xl.parse(nm, header=None, dtype=object, nrows=max(8, lines // min(3, len(xl.sheet_names)))); out.append(f"SHEET '{nm}' (first {len(df)} rows; cells separated by |)")
            for i, r in enumerate(df.values.tolist(), 1): out.append(f"{i:>4}: " + " | ".join("" if (v is None or (isinstance(v, float) and np.isnan(v))) else str(v) for v in r)[:width])
        if len(xl.sheet_names) > 6: out.append(f"... and {len(xl.sheet_names) - 6} more sheets: " + ", ".join(map(str, xl.sheet_names[6:20])))
    else:
        ls = _text(path).splitlines(); out.append(f"{len(ls)} lines in the file; the first {min(lines, len(ls))} and the last 3 follow, with their line numbers")
        for i, l in enumerate(ls[:lines], 1): out.append(f"{i:>4}: {l[:width]}")
        if len(ls) > lines + 3: out.append("   ...")
        for i in range(max(lines, len(ls) - 3), len(ls)): out.append(f"{i + 1:>4}: {ls[i][:width]}")
    return "\n".join(out)

def convert_by_recipe(path, recipe, outdir):
    """Turn a table the app could not read into a clean workbook the app draws. The recipe only says WHERE the table is and what
    the columns are called; the numbers are read from your file by this code and are not typed by anyone:
        sheet            Excel only: the sheet
        delimiter        text files: auto, comma, semicolon, tab, space or |          decimal: . or ,
        header_row       row number with the column names (0 = none)
        first_data_row   first row with numbers          last_data_row: last one (0 = to the end of the file)
        transpose        true when every ROW is one quantity (name first, then its values)
        columns          optional [{column: 1, name: "Temperature", unit: "°C"}, ...]: the columns to keep, numbered from 1, with clean names
        sample           name of the sample (becomes the name of the sheet)
    Returns (workbook path, table, lines for the message box)."""
    r = dict(recipe or {}); num = lambda k, d_=0: int(float(r.get(k) or d_))
    rows, sheet = _raw_rows(path, r.get("sheet"), r.get("delimiter", "auto")); dec = str(r.get("decimal") or ".").strip()
    h, a, b = num("header_row"), num("first_data_row", 1), num("last_data_row")
    if not 1 <= a <= len(rows): raise ValueError(f"first_data_row {a} is outside the file (it has {len(rows)} rows)")
    b = len(rows) if not b or b > len(rows) else b
    if b < a: raise ValueError("last_data_row is before first_data_row")
    body = [list(x) for x in rows[a - 1:b] if any(str(c).strip() for c in x)]
    if not body: raise ValueError("there is nothing in these rows")
    if r.get("transpose") in (True, "true", "True", 1, "1", "yes"):
        names = [str(x[0]).strip() for x in body]; n_ = max(len(x) for x in body) - 1
        body = [[(x[k + 1] if k + 1 < len(x) else "") for x in body] for k in range(n_)]
    else:
        w = max(len(x) for x in body); body = [x + [""] * (w - len(x)) for x in body]
        hdr = rows[h - 1] if 1 <= h <= len(rows) else []; names = [str(hdr[k]).strip() if k < len(hdr) and str(hdr[k]).strip() else f"Column {k + 1}" for k in range(w)]
    def val(c):
        if isinstance(c, (int, float, np.integer, np.floating)) and not isinstance(c, bool): return float(c)
        t = str(c).strip().replace("\u2212", "-")
        if dec == ",": t = t.replace(".", "").replace(",", ".") if re.match(r"^[-+]?\d{1,3}(\.\d{3})+,\d+$", t) else t.replace(",", ".")
        t = re.sub(r"(?<=\d)[ \u00a0](?=\d{3}\b)", "", t)
        try: return float(t)
        except Exception: return None
    keep = r.get("columns") or [{"column": k + 1} for k in range(len(names))]; out = {}; notes = []
    for c in keep:
        k = int(float(c.get("column", 0))) - 1
        if not 0 <= k < len(names): raise ValueError(f"there is no column {k + 1}; the table has {len(names)} columns: " + ", ".join(names[:12]))
        cells = [x[k] for x in body]; filled = [v for v in cells if str(v).strip() != ""]; vals = [val(v) if str(v).strip() != "" else None for v in cells]
        nm = str(c.get("name") or names[k]).strip() or f"Column {k + 1}"; u = str(c.get("unit") or "").strip()
        if u and not re.search(r"[(\[]", nm): nm = f"{nm} ({u})"
        while nm in out: nm += "_"
        good = sum(v is not None for v in vals)
        if filled and good >= 0.8 * len(filled):
            out[nm] = [np.nan if v is None else v for v in vals]
            if good < len(filled): notes.append(f"column '{nm}': {len(filled) - good} cell(s) are not numbers and were left empty")
        elif filled: out[nm] = [str(v).strip() for v in cells]
    df = pd.DataFrame(out)
    numeric = [c for c in df.columns if df[c].dtype.kind in "fi"]
    if len(numeric) < 1 or len(df) < 2: raise ValueError("no column of numbers came out of this recipe; look at the file again (read_file) and check the delimiter, the decimal sign and the rows")
    df = df.dropna(how="all", subset=numeric).reset_index(drop=True)
    used = set(); smp = _sheet(clean_name(str(r.get("sample") or sheet or os.path.splitext(os.path.basename(path))[0])), used)
    os.makedirs(outdir, exist_ok=True); outp = os.path.join(outdir, re.sub(r"[^A-Za-z0-9_.-]+", "_", str(r.get("sample") or os.path.splitext(os.path.basename(path))[0])).strip("_") + ".xlsx")
    if os.path.abspath(outp) == os.path.abspath(path): outp = outp[:-5] + "_table.xlsx"
    info = [("Source file", os.path.abspath(path)), ("Converted by", "Origin plot app " + VERSION + ", with a reading recipe " + ("learned earlier" if r.get("_learned") else "from the assistant")), ("Converted on", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("Recipe", json.dumps({k: v for k, v in r.items() if not str(k).startswith("_")}, ensure_ascii=False)), ("Note", "The numbers were read from the source file by the app. The recipe only says where the table is and what the columns are called.")]
    with _whole_file(outp) as tmp_, pd.ExcelWriter(tmp_, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=smp[:31], index=False); pd.DataFrame(info, columns=["Item", "Value"]).to_excel(w, sheet_name="File_info", index=False)
    lines = [f"Converted: {os.path.basename(path)} -> {outp}", f"  {len(df)} rows, columns: " + ", ".join(map(str, df.columns[:12])) + (" ..." if len(df.columns) > 12 else "")] + ["  " + n_ for n_ in notes]
    return outp, df, lines

# ----------------------------------------------------------------------------- file layouts the app has learned
def _home(opt=None):
    d = os.path.dirname(os.path.abspath(store_dir(opt))); os.makedirs(d, exist_ok=True); return d

def layout_signature(path):
    """What stays the same between two files of the same layout: the kind of file and the words that begin its first lines
    (numbers, sample names and values after a colon or separator do not count). Two exports of the same program give the same signature."""
    try:
        if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
            xl = pd.ExcelFile(path); nm = xl.sheet_names[0]; df = xl.parse(nm, header=None, dtype=object, nrows=14)
            first = [next((str(v) for v in r if not (v is None or (isinstance(v, float) and np.isnan(v))) and str(v).strip()), "") for r in df.values.tolist()]; kind = "excel:" + str(nm).lower()
        else:
            with open(path, "rb") as f: b_ = f.read(4000)
            if b_[:2] not in (b"\xff\xfe", b"\xfe\xff") and sum(c < 9 or 13 < c < 32 for c in b_) > 0.02 * max(1, len(b_)): return None
            first = [l for l in _text(path).splitlines() if l.strip()][:14]; kind = "text"
        words = []
        for l in first:
            w = re.split(r"[:;,\t|=]| {2,}", str(l).strip(), maxsplit=1)[0].strip().lower(); w = re.sub(r"\d+([.,]\d+)?", "0", w)
            w = "#" if re.match(r"^[-+0.,e ]*$", w) else w[:40]
            if not (w == "#" and words and words[-1] == "#"): words.append(w)
        if not any(w != "#" for w in words): return None
        return kind + "|" + "|".join(words)
    except Exception: return None

def learned_formats(opt=None):
    try:
        with open(os.path.join(_home(opt), "learned_formats.json"), "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def learn_format(path, recipe, opt=None):
    """Remember how a file of this layout is read, so the next one like it is read without help. Returns True when it was saved."""
    sig = layout_signature(path)
    if not sig: return False
    r = {k: v for k, v in dict(recipe).items() if not str(k).startswith("_") and k not in ("path", "do")}; r.pop("sample", None)      # the sample name belongs to one file, not to the layout
    try:
        if int(float(r.get("last_data_row") or 0)) > 0:                    # counted from the end, so a longer or shorter file of the same layout fits
            n_ = len(_raw_rows(path, r.get("sheet"), r.get("delimiter", "auto"))[0]); r["_rows_after_table"] = max(0, n_ - int(float(r["last_data_row"]))); r.pop("last_data_row")
    except Exception: pass
    d = learned_formats(opt); d[sig] = {"recipe": r, "learned_from": os.path.basename(path), "on": datetime.date.today().isoformat()}
    with open(os.path.join(_home(opt), "learned_formats.json"), "w", encoding="utf-8") as f: json.dump(d, f, indent=1, ensure_ascii=False)
    return True

def apply_learned(path, opt=None):
    """A file whose layout was learned earlier: convert it with the saved recipe. Returns (workbook, lines) or None."""
    if os.path.basename(os.path.dirname(os.path.abspath(path))) == "converted_tables": return None
    d = learned_formats(opt)
    if not d: return None
    hit = d.get(layout_signature(path) or "")
    if not hit: return None
    r = dict(hit["recipe"]); r["_learned"] = True
    try:
        if "_rows_after_table" in r:
            n_ = len(_raw_rows(path, r.get("sheet"), r.get("delimiter", "auto"))[0]); r["last_data_row"] = n_ - int(r.pop("_rows_after_table"))
        if r.get("transpose") in (True, "true", 1): pass
        outp, df, lines = convert_by_recipe(path, r, os.path.join(_home(opt), "converted_tables"))
    except Exception as e: return None
    return outp, [f"  this layout was learned on {hit.get('on', '?')} from {hit.get('learned_from', 'an earlier file')}: read with the saved recipe ({len(df)} rows, columns " + ", ".join(map(str, df.columns[:6])) + ")"]

def write_workbook(items, path, template=False, info=None):
    """Write the loaded fit graphs (or, for a template, one small made-up sample) as one workbook in the standard format.
    Returns the lines for the message box."""
    fits = [it for it in items if isinstance(it, Item) and it.kind.startswith("Fit") and it.spec is not None]
    smp, phs, labs, key, sheets, used, lines = [], [], [], {}, [], set(), []
    if template:
        x = np.round(np.arange(10.0, 70.0, 0.02), 4); pk = [(27.4, 900, "R"), (29.4, 700, "A"), (32.2, 800, "A"), (32.6, 1000, "A+B"), (34.4, 650, "A"), (41.3, 400, "A"), (51.7, 300, "A"), (54.3, 500, "R")]
        bg = 60 + 200 * np.exp(-(x - 10) / 12); yc = bg + sum(h * np.exp(-0.5 * ((x - p_) / 0.06) ** 2) for p_, h, _ in pk); rng_ = np.random.default_rng(1); yo = np.round(yc + rng_.normal(0, np.sqrt(yc)), 1)
        sheets.append(("Example_Profile", pd.DataFrame({"2theta_deg": x, "Yobs_counts": yo, "Ycalc_counts": np.round(yc, 2), "Ydiff_counts": np.round(yo - yc, 2), "Background_counts": np.round(bg, 2)})))
        smp.append(dict(Sample="Example", Display_name="Example (made-up data)", Group="My series", Profile_sheet="Example_Profile", Bragg_sheet="", Points=len(x), Rwp_pct="", Amorphous_wt_pct="", Calculated_curve="Rietveld refinement"))
        phs += [dict(Sample="Example", Phase_display_name="Alite M3", Label_code="A", Label_meaning="alite (C3S)", Weight_pct=62.0), dict(Sample="Example", Phase_display_name="Belite beta", Label_code="B", Label_meaning="belite (beta-C2S)", Weight_pct=18.0),
                dict(Sample="Example", Phase_display_name="Rutile", Label_code="R", Label_meaning="rutile (int. std.)", Weight_pct="")]
        labs += [dict(Sample="Example", Label=c_, **{"2theta_deg": p_}) for p_, _, c_ in pk]; key = {"A": "alite (C3S)", "B": "belite (beta-C2S)", "R": "rutile (int. std.)"}
    for it in fits:
        d = it.det; nums = d["nums"]; info = d.get("_info") or {}; k = _sheet(clean_name(it.sample or it.auto or it.name), used); p0 = it.spec["panels"][0]
        x = np.asarray(nums[d["x"]].values, float); yo = np.asarray(nums[d["obs"]].values, float); yc = np.asarray(nums[d["calc"]].values, float); m = np.isfinite(x) & np.isfinite(yo) & np.isfinite(yc)
        df = pd.DataFrame({"2theta_deg": x[m], "Yobs_counts": yo[m], "Ycalc_counts": yc[m], "Ydiff_counts": yo[m] - yc[m]})
        if d.get("back") is not None: df["Background_counts"] = np.asarray(nums[d["back"]].values, float)[m]
        sheets.append((k + "_Profile", df)); pl = d.get("_peaklist"); bs = ""
        if pl is not None and len(pl):
            bs = k + "_Bragg"; sheets.append((bs, pd.DataFrame({"Phase_HighScore_name": pl["Phase"].values, "Label_code": pl["Code"].values, "2theta_deg": np.round(pl["tt"].values, 4)})))
        rw = next((l_ for l_ in (p0.get("legendbox") or {}).get("lines", []) if l_.startswith("Rwp")), ""); rv = re.search(r"([\d.]+)\s*%", rw)
        smp.append(dict(Sample=k, Display_name=display_names([it])[0], Group=info.get("group") or "", Profile_sheet=k + "_Profile", Bragg_sheet=bs, Points=int(m.sum()), Rwp_pct=float(rv.group(1)) if rv else "",
                        Amorphous_wt_pct=info.get("amorphous") if info.get("amorphous") is not None else "", Calculated_curve=info.get("fit") or ("Profile fit" if "profile fit" in rw else "Rietveld refinement")))
        for r in info.get("phases") or []:
            cd = r.get("code") or xs.code_for(r["name"]); phs.append(dict(Sample=k, Phase_display_name=r["name"], Label_code=cd, Label_meaning=(d.get("_idmap") or {}).get(cd) or xs.CODE_NAMES.get(cd, ""), Weight_pct=r.get("wt") if r.get("wt") is not None else ""))
        for pos, txt, hgt in (_codelabs(p0) or []):
            if not re.match(r"^[\d.]+$", str(txt)): labs.append(dict(Sample=k, Label=txt, **{"2theta_deg": round(float(pos), 4), "Peak_top_counts": round(float(hgt), 2)}))
            for c_ in str(txt).split("+"):
                c_ = c_.strip("()?")
                if c_ and not re.match(r"^[\d.]+$", c_): key.setdefault(c_, (d.get("_idmap") or {}).get(c_) or xs.CODE_NAMES.get(c_, ""))
        lines.append(f"  {display_names([it])[0]}: {int(m.sum())} points, {len(_codelabs(p0) or [])} peak labels" + (f", {len(info.get('phases') or [])} phases" if info.get("phases") else "") + (", Bragg positions" if bs else ""))
    # every other loaded table (XRD scans, FTIR, TGA, particle size, calorimetry, your own graphs): its numbers as the app read them,
    # one sheet per table with clean column headers, so the workbook loads back as the same graphs
    gidx = [dict(Sheet=r["Profile_sheet"], Graph_type="Fit (observed + calculated)", Sample=r["Display_name"], Source="") for r in smp]; seen = {}
    for it in ([] if template else items):
        if not isinstance(it, Item) or it.spec is None or it.kind.startswith("Fit") or it.kind == "XRD peak list": continue
        nums = pd.DataFrame({c: pd.Series(np.asarray(v)) for c, v in dict(it.det["nums"]).items()}); nm_ = display_names([it])[0]
        try: body_ = __import__("hashlib").sha1(np.ascontiguousarray(nums.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)).tobytes()).hexdigest()
        except Exception: body_ = id(it)
        # one table drawn as two graphs (cumulative and differential, absorbance and transmittance) is written once. Two tables are the same
        # table only when their numbers are the same: equal column names and length are not enough (two samples measured the same way)
        sig = (it.path, tuple(str(c) for c in nums.columns), len(nums), body_, None if it.det.get("series") is None else tuple(map(str, it.det["series"])))
        if sig not in seen:
            df = nums.copy(); tt = it.det.get("t"); df.columns = [str(tt(c)) if callable(tt) else str(c) for c in nums.columns]
            if it.kind == "XRD" and all(re.match(r"^Col\d+$", str(c)) for c in df.columns):      # a file without column names (.xy, .xrdml): say what the columns are
                xc = str(it.det.get("x")); yc = [str(c) for c in (it.det.get("ys") or [])][:1]
                df.columns = ["2theta (deg)" if str(c) == xc else "Intensity" if [str(c)] == yc else str(c) for c in nums.columns]
            if it.det.get("series") is not None and len(it.det["series"]) == len(df): df.insert(0, str(it.det.get("series_col") or "Series"), list(it.det["series"]))
            b_ = clean_name(it.sample or it.auto or it.name)
            if re.sub(r"[^A-Za-z0-9]+", "_", b_).strip("_")[:22].lower() in used: b_ = f"{b_}_{it.kind.split()[0]}"      # the same sample measured another way: S1 -> S1_TGA
            seen[sig] = _sheet(b_, used); sheets.append((seen[sig], df))
            lines.append(f"  {nm_} [{it.kind}]: {len(df)} rows, columns " + ", ".join(str(c) for c in df.columns[:6]) + (" ..." if len(df.columns) > 6 else ""))
        gidx.append(dict(Sheet=seen[sig], Graph_type=it.kind, Sample=nm_, Source=os.path.basename(it.path)))
    if not smp and not seen: return ["There is no graph in the list, so there is nothing to write."]
    with _whole_file(path) as tmp_, pd.ExcelWriter(tmp_, engine="openpyxl") as w:
        pd.DataFrame(WB_README + ([("Written by", "Origin plot app " + VERSION + (" - template with made-up data: replace the Example rows and sheets with your own" if template else " - from the files loaded in the app"))]), columns=["Item", "Description"]).to_excel(w, sheet_name="ReadMe", index=False)
        pd.DataFrame(gidx).to_excel(w, sheet_name="Graphs", index=False)
        if info: pd.DataFrame(info, columns=["Item", "Value"]).to_excel(w, sheet_name="File_info", index=False)
        if smp: pd.DataFrame(smp).to_excel(w, sheet_name="Samples", index=False)
        if phs: pd.DataFrame(phs).to_excel(w, sheet_name="Phases", index=False)
        if labs: pd.DataFrame(labs).to_excel(w, sheet_name="Peak_Labels", index=False)
        if key: pd.DataFrame(sorted(key.items()), columns=["Label_code", "Meaning"]).to_excel(w, sheet_name="Label_Key", index=False)
        for nm, df in sheets: df.to_excel(w, sheet_name=nm[:31], index=False)
        try:
            for ws in w.book.worksheets:
                ws.freeze_panes = "A2"
                for col in ws.columns: ws.column_dimensions[col[0].column_letter].width = min(60, max(12, len(str(col[0].value or "")) + 3))
            w.book["ReadMe"].column_dimensions["B"].width = 120
        except Exception: pass
    return [f"Workbook written: {path}", f"  {len(gidx)} graph(s) in {len(sheets)} data sheet(s)" + (f"; fit samples: " + ", ".join(r["Display_name"] for r in smp) if smp else "")] + lines

# ============================================================================= sessions
def session_dump(singles, boards, settings):
    return {"app": VERSION, "files": list(dict.fromkeys(s.path for s in singles)), "info_files": sorted(_INFO_ONLY), "settings": settings,
            "sources": {p: {k: v for k, v in IMPORTED[p].items() if k != "copy"} for p in dict.fromkeys(s.path for s in singles) if p in IMPORTED},
            "graphs": [{"file": s.path, "table": s.name, "kind": s.kind, "sample": s.sample, "custom": getattr(s, "custom", None) or {}, "fmt": getattr(s, "fmt", None) or {},
                "model": {k: s.det[k] for k in ("_software", "_database", "_ftir_signal", "_psd_style") if s.det.get(k)}} for s in singles],
            "figures": [{"keys": b.keys, "cols": b.cols, "width_mm": b.width_mm, "number": b.number} for b in boards]}

def session_load(data, opt, folder=""):
    """Read the files of a saved session again and restore graph types, sample names and panel figures."""
    singles, lines, moved, fresh = [], [], {}, []
    def _old(v): return re.sub(r"^Thesis:", "Gallery:", v) if isinstance(v, str) else v
    for g in data.get("graphs", []):                   # sessions saved before 5.51 name the gallery kinds with another word
        for k_ in list(g): g[k_] = _old(g[k_])
    for p in data.get("info_files", []):               # files that only hold names / amounts
        q = p if os.path.exists(p) else os.path.join(folder, os.path.basename(p))
        if not os.path.exists(q): lines.append(f"  MISSING: {p} (names or phase amounts came from this file; add it again with Add files…)"); continue
        try: load_file(q)
        except Exception as e: lines.append(f"  I could not read {q}: {e}")
    want = {(g["file"], g["table"]): g for g in data.get("graphs", [])}
    known = data.get("sources") or {}
    def _sha(f_):
        try: return hashlib.sha256(open(f_, "rb").read()).hexdigest()
        except Exception: return None
    for p in data.get("files", []):
        want_h = (known.get(p) or {}).get("sha256"); cands = [p, os.path.join(folder, os.path.basename(p)), os.path.join(folder, "inputs", os.path.basename(p))]; cands = [c for c in cands if os.path.exists(c)]
        q = next((c for c in cands if want_h and _sha(c) == want_h), None) or (cands[0] if cands else os.path.join(folder, os.path.basename(p)))      # the file with the bytes of the session first
        if cands and want_h and _sha(q) != want_h:
            lines.append(f"  CHANGED: {q} is not the file this session was made from (other content than when it was saved on {(known.get(p) or {}).get('imported', '?')}). Its graphs show the file as it is now")
        elif cands and q != p and os.path.exists(p) and want_h: lines.append(f"  {os.path.basename(p)}: the file at its old place has changed, so the copy saved with the results (inputs) is used: the graphs are those of the session")
        if not os.path.exists(q): lines.append(f"  MISSING: {p} (its graphs are not in the list; put the file back or add it again with Add files…)"); continue
        if q != p: moved[p] = q; lines.append(f"  {os.path.basename(p)} was found next to the session file")
        try: new, _ = load_file(q)
        except Exception as e: lines.append(f"  I could not read {q}: {e}"); continue
        for it in new:
            g = want.get((p, it.name))
            if g is None: continue                      # a table you had removed from the list
            it.sample = g.get("sample", ""); it.want_kind = g.get("kind"); it.custom = g.get("custom") or {}; it.fmt = g.get("fmt") or {}; it.det.update(g.get("model") or {}); fresh.append(it)
    _, errs = prepare(singles, fresh, opt); lines += errs
    boards = []
    for f_ in data.get("figures", []):
        keys = [(moved.get(k.rsplit("|", 1)[0], k.rsplit("|", 1)[0]) + "|" + k.rsplit("|", 1)[1]) if not k.startswith("Combined|") else k for k in f_.get("keys", [])]
        boards.append(Board(keys, f_.get("cols", 0), f_.get("width_mm", 175.0), f_.get("number", len(boards) + 1)))
    return singles, boards, lines

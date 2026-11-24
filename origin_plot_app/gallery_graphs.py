"""Gallery graph types G01-G24 and calculations C01-C02 (see CHANGELOG_gallery_graphs.md and the graph catalogue).

A template workbook has an 'Instructions' sheet, one or more data sheets, and optionally 'Labels' and 'Options' (Key | Value).
This module reads such a workbook (or a plain table), recognises which of the 26 types it is, draws the figure with matplotlib in
the app's house style (landscape, one font family, 1.5 pt curves and axes, figure bigger than the words), computes what the type
needs (cumulative heat, chi2, hydration degree, atomic ratios, difference curves) and says which formula and which inputs it used,
gives the Origin driver equivalent graphs where it can draw them, and writes the templates.

Rules that hold everywhere:
- Labels (peak, phase, NMR component names) come only from the user's file: the Labels sheet or the column names. Nothing is guessed.
- A series (sample, age, method, phase) keeps the same colour and symbol in every panel and every figure of a session (SESSION).
- TG and DTG are one graph (TG left axis, DTG right axis) and DTG keeps its natural sign.
"""
import math
import os
import re

import numpy as np
import pandas as pd

TYPES = {
    "G01": ("XRD_STACK", "XRD patterns stacked with offset"), "G02": ("XRD_PEAKS_INSET", "XRD pattern with peak labels and inset"),
    "G03": ("RIETVELD_FIT", "Rietveld fit: observed, calculated, difference"), "G04": ("NMR_STACK", "NMR spectra stacked, one panel per sample"),
    "G05": ("NMR_DECONV", "NMR deconvolution: full range and zoom per age"), "G06": ("NMR_ANNOTATED", "NMR spectrum with annotated peaks"),
    "G07": ("TG_DTG", "TG and DTG in one graph (TG left, DTG right)"), "G08": ("DTG_COMPARE", "DTG curves compared (overlay or offset)"),
    "G09": ("XRD_DTG_PAIR", "XRD patterns beside their DTG curves"), "G10": ("CALORIMETRY_PAIR", "Heat flow with inset beside cumulative heat"),
    "G11": ("DUAL_Y_LOG", "Concentrations (log) with heat flow on the right axis"), "G12": ("PHASE_EVOLUTION", "Phase contents vs time, split time axis"),
    "G13": ("PANEL_GRID_TIME", "Grid of small graphs vs time, shared legend"), "G14": ("METHOD_COMPARISON", "Same quantity from several methods, per mix"),
    "G15": ("MASS_BALANCE", "Oxide budgets vs time with reference lines"), "G16": ("VS_RATIO", "Property against a mix variable"),
    "G17": ("SCATTER_TREND", "Labelled points with a linear trend"), "G18": ("GROUPED_BAR_ERR", "Grouped bars with error bars"),
    "G19": ("BAR_LINE_COMBO", "Bars with a line over them"), "G20": ("PSD_CUMULATIVE", "Cumulative particle size, one panel per group"),
    "G21": ("STACKED_AREA", "Phase assemblage as stacked areas"), "G22": ("TERNARY_POINTS", "Compositions in a ternary diagram"),
    "G23": ("TERNARY_CONTOUR", "Contour maps over the ternary diagram"), "G24": ("REFINEMENT_INDICES", "Rietveld agreement indices and chi2"),
    "C01": ("HYDRATION_DEGREE", "Degree of hydration from phase contents"), "C02": ("ATOMIC_RATIOS", "Atomic ratios from oxide contents"),
}
ORDER = list(TYPES)

FIG_W, FIG_H = 11.7, 6.5                     # landscape, the size of the app's other figures
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000", "#999999", "#882255", "#332288"]
MARKERS = ["s", "o", "^", "D", "v", "<", ">", "p", "h", "*"]
METHOD_STYLES = {                             # G14: a method keeps this style in every figure
    "qxrd": ("#000000", "s"), "xrd": ("#000000", "s"), "rietveld": ("#000000", "s"), "tga": ("#0072B2", "o"), "tg": ("#0072B2", "o"),
    "stoich": ("#E69F00", "^"), "calc": ("#E69F00", "^"), "nmr": ("#CC79A7", "D"), "27al": ("#CC79A7", "D"), "29si": ("#009E73", "v"),
}
PHASE_COLOURS = {                             # G21: a phase name keeps this colour in every figure
    "anhydrous": "#BDBDBD", "clinker": "#BDBDBD", "csh": "#6E6E6E", "c-s-h": "#6E6E6E", "portlandite": "#9ECAE1", "ch": "#9ECAE1",
    "ettringite": "#F4A582", "aft": "#F4A582", "ah3": "#1B7837", "gibbsite": "#1B7837", "ms": "#E08214", "monosulfate": "#E08214",
    "mc": "#B2ABD2", "monocarbonate": "#B2ABD2", "hc": "#8073AC", "hemicarbonate": "#8073AC", "stratlingite": "#A6DBA0",
    "hydrogarnet": "#D9F0D3", "katoite": "#D9F0D3", "calcite": "#FEE090", "aqua": "#C6E2F5", "poresolution": "#C6E2F5", "gypsum": "#FDAE61",
    "anhydrite": "#FDAE61", "ht": "#DFC27D", "hydrotalcite": "#DFC27D", "fh3": "#8C510A",
}
SESSION = {}                                  # series name -> (colour, marker, filled); kept for the whole session


class GalleryError(ValueError):
    """Something the user can fix (a missing column, a missing t0 row ...)."""


class NeedInput(GalleryError):
    """The app needs one more answer from the user (for example: which row is t0)."""
    def __init__(self, msg, key):
        super().__init__(msg)
        self.key = key


# ------------------------------------------------------------------------------------------------ reading
def _clean_df(df):
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df.reset_index(drop=True)


class Book:
    """The sheets of a workbook (or one table) with its Options, Labels and Instructions."""
    def __init__(self, path, sheets, extra_opt=None):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0] if path else "table"
        self.instructions = ""
        self.options = {}
        self.sheets = {}
        for k, df in sheets.items():
            kl = k.strip().lower()
            if kl == "instructions":
                self.instructions = " ".join(str(v) for v in df.iloc[:, 0].dropna()) if df.shape[1] else ""
                self.instructions += " " + " ".join(str(c) for c in df.columns)
                continue
            if kl == "options" and df.shape[1] >= 2:
                for a, b in zip(df.iloc[:, 0], df.iloc[:, 1]):
                    if pd.notna(a) and str(a).strip():
                        self.options[str(a).strip().lower()] = "" if (b is None or (isinstance(b, float) and math.isnan(b))) else b
                continue
            df = _clean_df(df)
            if df.shape[0] or kl.startswith(("labels", "xrd labels", "dtg labels", "ranges", "reference", "annotations", "regions", "samples")):
                self.sheets[k.strip()] = df
        if extra_opt:
            self.options.update({str(k).lower(): v for k, v in extra_opt.items()})

    def opt(self, key, default=None):
        v = self.options.get(key, "")
        return default if v is None or (isinstance(v, str) and not v.strip()) else v

    def num_opt(self, key, default=None):
        v = self.opt(key)
        try:
            return float(str(v).replace(",", ".").split()[0])
        except (TypeError, ValueError, IndexError):
            return default

    def choice(self, key, default=""):
        """The chosen word(s) of an option, without the explanation in brackets or after ' or ' (e.g. 'solid colours (or hatch ...)' -> 'solid colours')."""
        v = str(self.opt(key, default) or default)
        return re.split(r"\(|\bor\b", v, maxsplit=1)[0].strip().lower()

    def yes(self, key, default=False):
        v = self.opt(key)
        return default if v is None else str(v).strip().lower().startswith(("yes", "y", "true", "1", "on"))

    def sheet(self, *names):
        """The first sheet whose name starts with one of names (case does not matter)."""
        for n in names:
            for k, v in self.sheets.items():
                if k.lower().startswith(n.lower()):
                    return v
        return None

    def data_sheets(self):
        skip = ("labels", "xrd labels", "dtg labels", "ranges", "reference", "annotations", "regions", "hydration degree", "atomic ratios", "long", "table", "samples")
        return {k: v for k, v in self.sheets.items() if not k.lower().startswith(skip)}


def read_book(path, extra_opt=None):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        sheets = pd.read_excel(path, sheet_name=None)
        if ext != ".xls":                         # pandas turns text cells such as '20' into numbers: keep text columns as text
            try:
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                for ws in wb.worksheets:
                    if ws.title not in sheets:
                        continue
                    rows = list(ws.iter_rows(min_row=1, max_row=60))
                    if len(rows) < 2:
                        continue
                    df = sheets[ws.title]
                    for j, hc in enumerate(rows[0]):
                        if hc.value is None or j >= len(df.columns):
                            continue
                        cells = [r[j] for r in rows[1:] if j < len(r) and r[j].value is not None]
                        if cells and all(c.data_type == "s" for c in cells):
                            col = df.columns[j]
                            raw = [r[0] for r in ws.iter_rows(min_row=2, max_row=1 + len(df), min_col=j + 1, max_col=j + 1, values_only=True)]
                            raw += [None] * (len(df) - len(raw))
                            df[col] = [None if v is None else str(v) for v in raw[:len(df)]]
                wb.close()
            except Exception:          # noqa: BLE001
                pass
    elif ext in (".csv", ".txt"):
        sheets = {"Data": pd.read_csv(path, sep=None, engine="python")}
    else:
        raise GalleryError(f"{os.path.basename(path)}: gallery graph types read Excel workbooks or CSV tables")
    return Book(path, sheets, extra_opt)


def book_from_frames(frames, name="table", options=None):
    b = Book("", frames, options)
    b.name = name
    return b


def parse_calo_info(text):
    """'Reference: I, 0.62; Sample A (4 wt.%): II, 55 %' -> {norm(name): {"regime", "alite"}}: what you typed under Analysis settings >
    Calorimetry. Each entry is  name: regime[, alite fraction]  (a fraction, or a percentage); entries apart by ';' or new lines."""
    out = {}
    for part in re.split(r"[;\n]+", str(text or "")):
        if ":" not in part:
            continue
        nm, rest = part.rsplit(":", 1)
        bits = [b.strip() for b in rest.split(",") if b.strip()]
        rg, al = None, None
        for b in bits:
            m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(%?)", b)
            if m and al is None and (rg is not None or "." in b or "," in b or m.group(2) or float(m.group(1).replace(",", ".")) > 9):
                v = float(m.group(1).replace(",", "."))
                al = v / 100.0 if (m.group(2) or v > 1.5) else v
            elif rg is None:
                rg = b
        if nm.strip():
            out[norm(nm)] = {"regime": rg, "alite": al}
    return out


def calo_book(samples, bar_at_h=None, name="calorimetry"):
    """A G10 workbook from calorimetry already processed in the app: samples = [{"name", "t_h", "hf" (mW/g), "q" (J/g or None),
    optional "label", "regime", "alite", "colour"}]. One sheet per sample, plus the Samples sheet (only what was given)."""
    frames, rows = {}, []
    for k, s_ in enumerate(samples):
        key = re.sub(r'[\\/:*?"<>|\[\]]+', "_", str(s_["name"]))[:31] or f"sample {k + 1}"
        while key in frames:
            key = (key[:28] + f"_{k + 1}")[:31]
        t = np.asarray(s_["t_h"], float); hf = np.asarray(s_["hf"], float)
        d = {"Time (h)": t, f"Heat flow {key} (mW/g)": hf}
        if s_.get("q") is not None:
            d[f"Cumulative heat {key} (J/g)"] = np.asarray(s_["q"], float)
        frames[key] = pd.DataFrame(d)
        rows.append({"Sample": key, "Label": s_.get("label") or s_["name"], "Regime": s_.get("regime") or "",
                     "Alite fraction": s_.get("alite") if s_.get("alite") else "", "Colour": s_.get("colour") or ""})
    if any(r["Regime"] or r["Alite fraction"] or r["Colour"] for r in rows) or len(rows) > 1:
        frames["Samples"] = pd.DataFrame(rows)
    opts = {"exclusion_min": 0}
    if bar_at_h:
        opts["bar_at_h"] = bar_at_h
    return book_from_frames(frames, name, opts)


# ------------------------------------------------------------------------------------------------ small helpers
def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def nums(df, col):
    return pd.to_numeric(df[col], errors="coerce").to_numpy(float)


def is_num(df, col, frac=0.8):
    v = pd.to_numeric(df[col], errors="coerce")
    return len(v) > 0 and v.notna().mean() >= frac


def is_text_cats(df, col):
    """True when the cells of the column are text in the file (categories such as '20', '0.25', 'S1'), not numbers."""
    vals = df[col].dropna()
    return len(vals) > 0 and all(isinstance(v, str) for v in vals)


SD_RE = re.compile(r"^(.*?)\s*(?:±\s*SD|SD|err(?:or)?|std|stdev)\s*$", re.I)


def sd_of(name):
    m = SD_RE.match(str(name))
    return m.group(1).strip() if m and m.group(1).strip() else None


def base_name(col):
    """'C3S (g/100 g paste)' -> 'C3S'; 'TG 6 h (%)' stays readable."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(col)).strip()


def unit(col):
    m = re.search(r"\(([^)]*)\)\s*$", str(col))
    return m.group(1) if m else ""


def value_sd_pairs(df, xcol):
    """[(value column, sd column or None)] for every numeric column that is not x and not itself an SD column."""
    cols = [c for c in df.columns if c != xcol and is_num(df, c)]
    sds = {}
    for c in cols:
        b = sd_of(c)
        if b:
            sds[norm(b)] = c
    out = []
    for c in cols:
        if sd_of(c):
            continue
        out.append((c, sds.get(norm(base_name(c))) or sds.get(norm(c))))
    return out


FORMULA_RE = re.compile(r"(?<![A-Za-z0-9])((?:[A-Z][a-z]?\d*){2,})(?![A-Za-z0-9])")


def chem(s):
    """Subscripts for chemical formulas with at least two element parts (C3S, Al2O3, AH3, SO3, CaCO3) and superscripts for Q0..Q4.
    Sample names such as S1-WP, ages such as 28 d and numbers stay exactly as typed."""
    s = str(s)
    s = re.sub(r"\bQ([0-4])", r"Q$^{\1}$", s)
    s = re.sub(r"\b(\d{1,3})(Al|Si|Ca|Na|Mg|H|C|N|O|P|F|S|K)\b", r"$^{\1}$\2", s)     # isotopes: 27Al, 29Si

    def sub(m):
        tok = m.group(1)
        if not re.search(r"\d", tok):
            return tok
        return re.sub(r"(?<=[A-Za-z])(\d+)", r"$_{\1}$", tok)
    return FORMULA_RE.sub(sub, s).replace("$$", "")


def wrap_title(t, width=30):
    import textwrap
    t = str(t)
    return "\n".join(textwrap.wrap(t, width)) if len(t) > width else t


def style_for(name, method=False):
    """Colour and marker of a series; the same name keeps them for the whole session."""
    key = norm(name)
    if method:
        for k, v in METHOD_STYLES.items():
            if key.startswith(k) or k in key:
                SESSION.setdefault(key, (v[0], v[1], True))
                return SESSION[key]
    if key not in SESSION:
        i = len(SESSION)
        SESSION[key] = (OKABE[i % len(OKABE)], MARKERS[i % len(MARKERS)], (i // len(MARKERS)) % 2 == 0)
    return SESSION[key]


def labels_of(book, sheet_names=("labels",), pos_hint=("position", "temperature", "ppm", "2theta", "2θ")):
    """[(text, position, target or '', extra dict)] from a Labels sheet; [] when there is none (then nothing is labelled)."""
    df = book.sheet(*sheet_names)
    if df is None or df.empty:
        return []
    cols = list(df.columns)
    tcol = next((c for c in cols if norm(c).startswith(("label", "text", "name"))), cols[0])
    pcol = next((c for c in cols if c != tcol and any(h in str(c).lower() for h in pos_hint)), None)
    if pcol is None:
        pcol = next((c for c in cols if c != tcol and is_num(df, c)), None)
    if pcol is None:
        return []
    other = [c for c in cols if c not in (tcol, pcol)]
    tgt = next((c for c in other if norm(c).startswith(("pattern", "sample", "curve", "series", "age"))), None)
    out = []
    for _, r in df.iterrows():
        try:
            pos = float(str(r[pcol]).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if not str(r[tcol]).strip() or str(r[tcol]).strip().lower() == "nan":
            continue
        extra = {norm(c): r[c] for c in other}
        extra["_raw_pos"] = r[pcol]
        t = "" if tgt is None or pd.isna(r[tgt]) else str(r[tgt]).strip()
        out.append((str(r[tcol]).strip(), pos, t, extra))
    return out


def _fmt_num(v):
    if isinstance(v, str):
        return v.strip()
    f = float(v)
    s = repr(round(f, 6))
    return s[:-2] if s.endswith(".0") and abs(f) >= 100 else s


# ------------------------------------------------------------------------------------------------ house style
def house_style():
    import matplotlib
    try:
        import smart_plots as sp
        sp.apply_style()
    except Exception:          # noqa: BLE001
        pass
    matplotlib.rcParams.update({
        "font.size": 12, "axes.labelsize": 13, "axes.titlesize": 12, "legend.fontsize": 10.5, "xtick.labelsize": 11, "ytick.labelsize": 11,
        "axes.linewidth": 1.5, "lines.linewidth": 1.5, "lines.markersize": 6, "xtick.direction": "in", "ytick.direction": "in",
        "xtick.top": True, "ytick.right": True, "xtick.major.width": 1.5, "ytick.major.width": 1.5, "xtick.minor.width": 0.75,
        "ytick.minor.width": 0.75, "xtick.major.size": 5, "ytick.major.size": 5, "xtick.minor.size": 3, "ytick.minor.size": 3,
        "legend.frameon": False, "mathtext.default": "regular", "axes.unicode_minus": True,
    })


def panel_letter(ax, i, y=1.02):
    ax.text(0.0, y, f"({chr(97 + i)})", transform=ax.transAxes, fontsize=13, fontweight="bold", va="bottom", ha="left")


def _new_ax(fig, rect=(0.09, 0.12, 0.86, 0.82)):
    return fig.add_axes(rect)


def end_labels(ax, rows, x_end, size=10.5, right=True, gap_frac=0.045):
    """Names at the end of curves, pushed apart so they never overlap. rows: [(text, y, colour)]."""
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * gap_frac
    last = None
    for text, y, col in sorted(rows, key=lambda r: r[1]):
        y2 = y if last is None else max(y, last + gap)
        last = y2
        ax.annotate(text, xy=(x_end, y2), xytext=(4 if right else -4, 0), textcoords="offset points", color=col, fontsize=size,
                    va="center", ha="left" if right else "right", annotation_clip=False)


# ------------------------------------------------------------------------------------------------ recognition
TAG_RE = re.compile(r"\b([GC]\d\d)\s+([A-Z_]{4,})")


def _first_col(df):
    return df.columns[0] if df is not None and len(df.columns) else None


def _kind_of_x(name):
    n = str(name).lower()
    if re.search(r"2\s*θ|2\s*theta|2theta|two.?theta|angle|°2θ", n):
        return "2theta"
    if re.search(r"δ|ppm|chemical shift|shift", n):
        return "ppm"
    if re.search(r"temp|°c\b|\(°c\)|celsius", n):
        return "temperature"
    if re.search(r"particle|size|diameter|µm|um\b|micron", n):
        return "size"
    if re.search(r"time|days?\b|age|hours?|\(h\)|\(d\)", n):
        return "time"
    return ""


def recognise(book):
    """(type id, reason). Uses the type tag the app writes into the Instructions sheet of its own templates when present, and
    otherwise the sheet names, column names and numbers. (None, reason) when the workbook is not one of the gallery types."""
    m = TAG_RE.search(book.instructions or "")
    if m and m.group(1) in TYPES and TYPES[m.group(1)][0] == m.group(2):
        return m.group(1), f"the Instructions sheet names the type ({m.group(1)} {m.group(2)})"
    tid, why = _recognise_structure(book)
    return tid, why


def _recognise_structure(book):
    ds = book.data_sheets()
    names = {k.lower(): k for k in book.sheets}
    if not ds:
        return None, "no data sheet"
    first = next(iter(ds.values()))
    cols = [str(c) for c in first.columns]
    ncols = {norm(c) for c in cols}
    # LONG layout
    if {"panel", "series", "value"} <= ncols:
        if any(k.startswith("reference") for k in names):
            return "G15", "LONG layout (Panel | Series | X | Value) with a 'Reference lines' sheet"
        ser = " ".join(str(s).lower() for s in first[[c for c in cols if norm(c) == "series"][0]].dropna().unique())
        if sum(w in ser for w in ("qxrd", "tga", "stoich", "nmr", "calculation")) >= 2:
            return "G14", "LONG layout whose series are methods (QXRD, TGA, stoichiometry, NMR)"
        return "G13", "LONG layout (Panel | Series | X | Value): one small graph per Panel"
    if "rwp" in ncols and "rexp" in ncols:
        return "G24", "columns Rwp and Rexp"
    if "xrd" in names and "dtg" in names:
        return "G09", "sheets 'XRD' and 'DTG'"
    if any(k.startswith("concentration") for k in names) and any(k.startswith("heat flow") for k in names):
        return "G11", "sheets 'Concentrations' and 'Heat flow'"
    comp = [c for c in cols if re.search(r"mass.?%|wt.?%|mole.?%|mol.?%", c.lower()) or norm(base_name(c)) in ("opc", "cac", "sulphate", "sulfate", "cement", "slag")]
    if len(comp) >= 3:
        rest = [c for c in cols if c not in comp and is_num(first, c)]
        if rest:
            return "G23", "three composition columns and value columns: contour maps over the ternary diagram"
        return "G22", "three composition columns: points in a ternary diagram"
    if cols and is_text_cats(first, cols[0]) and len([c for c in cols[1:] if is_num(first, c)]) >= 1 and norm(cols[0]) != "label":
        vals = [c for c in cols[1:] if is_num(first, c)]
        if any(re.search(r"stoich|calculat|model|line", c.lower()) for c in vals) and len(vals) >= 3:
            return "G19", "categories (text), bar columns and a calculated line column"
        return "G18", "categories (text) and value columns"
    xk = _kind_of_x(cols[0]) if cols else ""
    if xk == "ppm":
        if len(ds) >= 2 and all("experimental" in {str(c).lower() for c in v.columns} for v in ds.values()):
            return "G05", "one sheet per age with δ, Experimental and fitted components"
        lab = book.sheet("labels")
        if (lab is not None and any("write" in str(c).lower() or "colour" in str(c).lower() or "color" in str(c).lower() for c in lab.columns)) or (len(ds) == 1 and len(cols) == 2):
            return "G06", "one spectrum (δ and intensity) with an annotation Labels sheet"
        return "G04", "δ (ppm) first column and one column per age: stacked NMR spectra"
    if xk == "2theta":
        if "observed" in {norm(c) for c in cols} and "calculated" in ncols:
            return "G03", "2θ with Observed and Calculated columns"
        ints = [c for c in cols[1:] if is_num(first, c)]
        if len(ints) == 1:
            return "G02", "2θ and one intensity column"
        return "G01", f"2θ and {len(ints)} intensity columns"
    if xk == "temperature":
        if any(norm(c).startswith("tg") and not norm(c).startswith("tga") for c in cols) and any(norm(c).startswith("dtg") for c in cols):
            return "G07", "Temperature with TG and DTG column pairs"
        return "G08", "Temperature and one DTG column per curve"
    if xk == "size":
        return "G20", "particle size and cumulative columns"
    if xk == "time" and any("heat flow" in c.lower() for c in cols):
        return "G10", "Time and 'Heat flow' columns"
    oxides = [c for c in cols if norm(base_name(c)) in OXIDES]
    if xk == "time" and len(oxides) >= 2:
        return "C02", "oxide contents over time: atomic ratios"
    if xk == "time":
        t = nums(first, cols[0])
        has_sd = any(sd_of(c) for c in cols)
        sheets_ph = any(k.lower().startswith(("anhydrous", "hydrates")) for k in ds)
        if sheets_ph or (has_sd and np.nanmin(t) == 0):
            return "G12", "time with a t = 0 row, phase contents and SD columns (or Anhydrous/Hydrates sheets)"
        vals = [c for c in cols[1:] if is_num(first, c)]
        if vals and np.nanmin(t) > 0 and len(t) >= 8:
            rows = first[vals].apply(pd.to_numeric, errors="coerce").sum(axis=1)
            if abs(np.nanmedian(rows) - 100) < 3 or any(norm(c).startswith("aqua") for c in cols):
                return "G21", "phase amounts that add up to 100 (thermodynamic modelling)"
        if np.nanmin(t) == 0:
            return "C01", "phase contents over time with a t = 0 row: degree of hydration"
        return "G16", "a variable and value columns"
    # text first column
    if cols and not is_num(first, cols[0]):
        if norm(cols[0]) == "label" and len([c for c in cols[1:] if is_num(first, c)]) >= 2:
            return "G17", "a Label column and two numeric columns"
        vals = [c for c in cols[1:] if is_num(first, c)]
        if any(re.search(r"stoich|calculat|model|line", c.lower()) for c in vals) and len(vals) >= 3:
            return "G19", "categories, bar columns and a calculated line column"
        if vals:
            return "G18", "categories (text) and value columns"
    if cols and is_num(first, cols[0]):
        vals = [c for c in cols[1:] if is_num(first, c)]
        if vals and len(first) <= 40:
            return "G16", "a mix variable and value columns"
    return None, "no gallery graph layout recognised"


OXIDES = {"cao": (56.077, "Ca", 1), "al2o3": (101.961, "Al", 2), "sio2": (60.084, "Si", 1), "so3": (80.063, "S", 1), "mgo": (40.304, "Mg", 1),
          "fe2o3": (159.687, "Fe", 2), "na2o": (61.979, "Na", 2), "k2o": (94.196, "K", 2), "co2": (44.009, "C", 1), "tio2": (79.866, "Ti", 1)}


# ------------------------------------------------------------------------------------------------ drawing entry point
class Result:
    def __init__(self):
        self.tables = {}            # name -> DataFrame (results table, computed sheets)
        self.notes = []             # what was done, formulas and inputs
        self.origin_note = ""


def draw(tid, book, fig, result=None):
    """Draw type tid of book into fig. Returns a Result with the tables and notes."""
    house_style()
    res = result or Result()
    fig.clear()
    fn = DRAWERS.get(tid)
    if fn is None:
        raise GalleryError(f"unknown graph type {tid}")
    fn(book, fig, res)
    return res


def figure(tid, book):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(FIG_W, FIG_H), dpi=100, facecolor="white")
    FigureCanvasAgg(fig)
    res = draw(tid, book, fig)
    return fig, res


def save(tid, book, outdir, base=None, formats=("png", "pdf"), dpi=600, extra_scale=0.85):
    """Publication files <sample or sheet>_<type>.png/.pdf in outdir. Returns (files, Result)."""
    os.makedirs(outdir, exist_ok=True)
    fig, res = figure(tid, book)
    base = base or f"{re.sub(r'[^A-Za-z0-9_-]+', '_', book.name).strip('_')}_{TYPES[tid][0]}"
    files = []
    for ext in formats:
        p = os.path.join(outdir, f"{base}.{ext}")
        fig.savefig(p, dpi=dpi if ext == "png" else None, facecolor="white")
        files.append(p)
    for suf, drawer in extra_figures(tid, book):
        files += save_extra(drawer, book, outdir, f"{base}_{suf}", formats, res, dpi=dpi, scale=extra_scale)
    return files, res


def save_extra(drawer, book, outdir, base, formats=("png", "pdf"), res=None, dpi=600, scale=0.85):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    house_style()
    fig = Figure(figsize=(FIG_W * scale, FIG_H * scale), dpi=100, facecolor="white")
    FigureCanvasAgg(fig)
    drawer(book, fig, res or Result())
    out = []
    for ext in formats:
        p = os.path.join(outdir, f"{base}.{ext}")
        fig.savefig(p, dpi=dpi if ext == "png" else None, facecolor="white")
        out.append(p)
    return out


# ------------------------------------------------------------------------------------------------ G01 / G09a XRD stack
def _stack_offsets(curves, gap_frac=0.06, step_frac=0.6):
    """Vertical offsets: each pattern is lifted by step_frac of the tallest pattern, and more where needed so that it lies
    above the one below it everywhere (they never touch)."""
    offs = [0.0]
    span = max(float(np.nanmax(y) - np.nanmin(y)) for _, y in curves) or 1.0
    for (x0, y0), (x1, y1) in zip(curves[:-1], curves[1:]):
        yi = np.interp(x1, x0, y0)
        need = float(np.nanmax(yi + offs[-1] - y1)) + gap_frac * span
        offs.append(max(need, offs[-1] + step_frac * span))
    return offs


def _xrd_stack(ax, x, cols, df, labels, opt_book, colours=None, lo=None, hi=None, guide=False, highlight=None, xtitle=None, oldest_top=True):
    lo = float(np.nanmin(x)) if lo is None else lo
    hi = float(np.nanmax(x)) if hi is None else hi
    m = (x >= lo) & (x <= hi)
    order = list(cols) if oldest_top else list(cols)[::-1]
    curves = [(x[m], nums(df, c)[m]) for c in order]
    offs = _stack_offsets(curves)
    for k, (c, (xx, yy), off) in enumerate(zip(order, curves, offs)):
        col = colours[c] if colours else "#000000"
        ax.plot(xx, yy + off, color=col, lw=1.2)
        e = max(5, len(yy) // 30)
        ax.annotate(str(c), xy=(hi, float(np.nanmedian(yy[-e:])) + off), xytext=(-4, 6), textcoords="offset points", ha="right", va="bottom",
                    fontsize=11.5, color=col)
    top_x, top_y = curves[-1]
    top_off = offs[-1]
    ymax = float(np.nanmax(top_y + top_off))
    ymin = float(np.nanmin(curves[0][1] + offs[0]))
    pad = 0.04 * (ymax - ymin)
    placed = []
    for text, pos, target, _ in labels:
        if not (lo <= pos <= hi):
            continue
        if target and target in order:
            i = order.index(target)
            xx, yy = curves[i]
            off = offs[i]
        else:
            xx, yy, off = top_x, top_y, top_off
        w = (xx > pos - 0.15) & (xx < pos + 0.15)
        base = float(np.nanmax(yy[w])) + off if w.any() else float(np.interp(pos, xx, yy)) + off
        lvl = 0
        while any(abs(pos - p) < 0.012 * (hi - lo) * 6 and l == lvl for p, l in placed):
            lvl += 1
        placed.append((pos, lvl))
        ax.text(pos, base + pad * (1 + 1.4 * lvl), chem(text), ha="center", va="bottom", fontsize=10.5)
        if guide:
            ax.axvline(pos, color="0.45", ls="--", lw=0.8, zorder=0)
    top = ymax + pad * (3 + 1.4 * max([l for _, l in placed] or [0]))
    if highlight:
        from matplotlib.patches import Rectangle
        a, b = highlight
        ax.add_patch(Rectangle((a, ymin - pad), b - a, top - ymin, fill=False, ec="#D00000", ls="--", lw=1.5, zorder=5))
    ax.set_xlim(lo, hi)
    ax.set_ylim(ymin - 2 * pad, top + pad)
    ax.set_yticks([])
    ax.tick_params(axis="y", which="both", left=False, right=False)
    ax.set_xlabel(xtitle or "2θ (°)")
    return offs


def draw_g01(book, fig, res):
    ds = book.data_sheets()
    labels = labels_of(book)
    hl = (book.num_opt("highlight_from"), book.num_opt("highlight_to"))
    zl = (book.num_opt("zoom_from"), book.num_opt("zoom_to"))
    zoom = zl if None not in zl else None
    hl = hl if None not in hl else None
    guide = book.yes("guide_lines") or (zoom is not None and str(book.opt("guide_lines", "")).strip() == "")
    oldest_top = "bottom" not in str(book.opt("order", "oldest on top")).lower()
    n = len(ds)
    axs = [fig.add_axes([0.06 + i * (0.9 / n), 0.12, 0.9 / n - 0.03, 0.8]) for i in range(n)]
    xt = str(book.opt("x_title", "2θ (°)"))
    xr = None
    for i, (sh, df) in enumerate(ds.items()):
        xc = df.columns[0]
        x = nums(df, xc)
        cols = [c for c in df.columns[1:] if is_num(df, c)]
        lo, hi = (min(zoom), max(zoom)) if zoom else (float(np.nanmin(x)), float(np.nanmax(x)))
        if xr is None:
            xr = (lo, hi)
        lo, hi = xr                                   # same 2θ range in every panel
        lab = [l for l in labels if not l[2] or l[2] in cols or l[2] == sh]
        _xrd_stack(axs[i], x, cols, df, lab, book, None, lo, hi, guide=guide and zoom is not None or book.yes("guide_lines"), highlight=hl if not zoom else None, xtitle=xt, oldest_top=oldest_top)
        if n > 1:
            panel_letter(axs[i], i)
            axs[i].set_title(sh, fontsize=11, loc="right")
    axs[0].set_ylabel(str(book.opt("y_title", "Intensity (a.u.)")))
    res.notes.append(f"{n} panel(s); patterns offset so they never touch; {'oldest on top' if oldest_top else 'oldest at the bottom'}; "
                     f"{len(labels)} label(s) from the Labels sheet" + (f"; dashed box {hl[0]:g}-{hl[1]:g}°" if hl and not zoom else "") + (f"; zoom {zoom[0]:g}-{zoom[1]:g}° with guide lines" if zoom else ""))
    if not labels:
        res.notes.append("no Labels sheet: no peak labels drawn (labels are never guessed)")


# ------------------------------------------------------------------------------------------------ G02 / G03
def _inset(ax, rect, lo, hi, curves, bold=True):
    ins = ax.inset_axes(rect)
    for x, y, kw in curves:
        m = (x >= lo) & (x <= hi)
        ins.plot(x[m], y[m], **kw)
    ins.set_xlim(lo, hi)
    ins.tick_params(labelsize=11)
    if bold:
        for t in ins.get_xticklabels() + ins.get_yticklabels():
            t.set_fontweight("bold")
    for s in ins.spines.values():
        s.set_linewidth(1.5)
    return ins


def draw_g02(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    x = nums(df, df.columns[0])
    ycol = [c for c in df.columns[1:] if is_num(df, c)][0]
    y = nums(df, ycol)
    ax = _new_ax(fig)
    ax.plot(x, y, color="#000000", lw=1.2)
    labels = labels_of(book)
    top = float(np.nanmax(y))
    vertical = "vert" in str(book.opt("label_orientation", "vertical")).lower()
    arrows = book.yes("arrows", True)
    for text, pos, _t, _e in labels:
        w = (x > pos - 0.15) & (x < pos + 0.15)
        yp = float(np.nanmax(y[w])) if w.any() else float(np.interp(pos, x, y))
        if arrows:
            ax.annotate(chem(text), (pos, yp + 0.02 * top), (pos, yp + 0.22 * top), ha="center", va="bottom", rotation=90 if vertical else 0,
                        fontsize=10.5, arrowprops=dict(arrowstyle="->", lw=0.9))
        else:
            ax.text(pos, yp + 0.03 * top, chem(text), ha="center", va="bottom", rotation=90 if vertical else 0, fontsize=10.5)
    ax.set_xlim(float(np.nanmin(x)), float(np.nanmax(x)))
    ax.set_ylim(0, top * 1.5)
    ax.set_xlabel(str(book.opt("x_title", "2θ (°)")))
    ax.set_ylabel(str(book.opt("y_title", base_name(ycol) + (f" ({unit(ycol)})" if unit(ycol) else ""))))
    a, b = book.num_opt("inset_from"), book.num_opt("inset_to")
    if a is not None and b is not None:
        _inset(ax, [0.6, 0.55, 0.37, 0.4], min(a, b), max(a, b), [(x, y, dict(color="#000000", lw=1.5))])
        res.notes.append(f"inset {min(a, b):g}-{max(a, b):g}°, numbers bold")
    res.notes.append(f"{len(labels)} label(s) from the Labels sheet" if labels else "no Labels sheet: no labels drawn")


def draw_g03(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    cmap = {norm(c): c for c in df.columns}
    x = nums(df, df.columns[0])
    obs, calc = nums(df, cmap["observed"]), nums(df, cmap["calculated"])
    if "difference" in cmap:
        diff = nums(df, cmap["difference"])
        res.notes.append("difference curve from the file")
    else:
        diff = obs - calc
        res.notes.append("difference = Observed - Calculated (computed; the file has no Difference column)")
    off = book.num_opt("difference_offset")
    if off is None:
        off = -0.06 * float(np.nanmax(obs)) - float(np.nanmax(diff))
    ax = _new_ax(fig)
    ax.plot(x, obs, color="#1F3BFF", lw=1.5, label="Observed")
    ax.plot(x, calc, color="#E00000", lw=1.2, label="Calculated")
    ax.plot(x, diff + off, color="0.5", lw=1.0, label="Difference")
    ax.axhline(off, color="0.8", lw=0.6, zorder=0)
    ax.set_xlim(float(np.nanmin(x)), float(np.nanmax(x)))
    ax.set_ylim(off + float(np.nanmin(diff)) * 1.3, float(np.nanmax(obs)) * 1.12)
    ax.set_xlabel(str(book.opt("x_title", "2θ (°)")))
    ax.set_ylabel(str(book.opt("y_title", "Intensity (counts)")))
    ax.legend(loc="upper left")
    rwp, rexp = book.num_opt("rwp"), book.num_opt("rexp")
    if rwp and rexp:
        chi2 = (rwp / rexp) ** 2
        ax.text(0.02, 0.80, f"R$_{{wp}}$ = {rwp:g}   R$_{{exp}}$ = {rexp:g}   χ$^2$ = {chi2:.2f}", transform=ax.transAxes, ha="left", va="top", fontsize=11)
        res.notes.append(f"χ² = (Rwp/Rexp)² = ({rwp:g}/{rexp:g})² = {chi2:.3f}")
        res.tables["Agreement indices"] = pd.DataFrame([{"Rwp": rwp, "Rexp": rexp, "chi2 = (Rwp/Rexp)^2": round(chi2, 4)}])
    a, b = book.num_opt("inset_from"), book.num_opt("inset_to")
    if a is not None and b is not None:
        _inset(ax, [0.6, 0.48, 0.37, 0.45], min(a, b), max(a, b), [(x, obs, dict(color="#1F3BFF", lw=1.5)), (x, calc, dict(color="#E00000", lw=1.2)), (x, diff + off, dict(color="0.5", lw=1.0))])


# ------------------------------------------------------------------------------------------------ NMR
def _ppm_title(book, col):
    nuc = str(book.opt("nucleus", "") or "").strip()
    m = re.search(r"(\d+)\s*([A-Z][a-z]?)", str(col))
    if not nuc and m:
        nuc = m.group(1) + m.group(2)
    mm = re.match(r"(\d+)\s*([A-Za-z]+)", nuc)
    if not mm:
        return "δ$_{iso}$ (ppm)"
    return "δ$_{iso}$ $^{" + mm.group(1) + "}$" + mm.group(2) + " (ppm)"


def draw_g04(book, fig, res):
    ds = book.data_sheets()
    labels = labels_of(book)
    n = len(ds)
    xf, xt = book.num_opt("x_from"), book.num_opt("x_to")
    guide = book.yes("guide_lines", True)
    axs = [fig.add_axes([0.05 + i * (0.92 / n), 0.12, 0.92 / n - 0.025, 0.76]) for i in range(n)]
    for i, (sh, df) in enumerate(ds.items()):
        ax = axs[i]
        col = style_for(sh)[0]
        x = nums(df, df.columns[0])
        cols = [c for c in df.columns[1:] if is_num(df, c)]
        a = xf if xf is not None else float(np.nanmax(x))
        b = xt if xt is not None else float(np.nanmin(x))
        hi_, lo_ = max(a, b), min(a, b)
        m = (x <= hi_) & (x >= lo_)
        curves = [(x[m][::-1], nums(df, c)[m][::-1]) for c in cols]
        offs = _stack_offsets(curves, 0.08)
        for c, (xx, yy), off in zip(cols, curves, offs):
            ax.plot(xx, yy + off, color=col, lw=1.3)
            ax.annotate(str(c), xy=(lo_, float(np.nanmedian(yy[: max(3, len(yy) // 25)])) + off), xytext=(4, 4), textcoords="offset points",
                        ha="left", va="bottom", fontsize=10.5, color="#000000")
        top = float(np.nanmax(curves[-1][1] + offs[-1]))
        bot = float(np.nanmin(curves[0][1]))
        span = top - bot
        mine = sorted([l for l in labels if not l[2] or l[2] == sh], key=lambda l: -l[1])
        # labels fanned out when crowded: text positions spread evenly, thin leader lines to the true position
        minsep = 0.06 * (hi_ - lo_)
        tx = []
        for text, pos, _t, _e in mine:
            p = pos
            if tx and tx[-1] - p < minsep:
                p = tx[-1] - minsep
            tx.append(p)
        for (text, pos, _t, _e), p in zip(mine, tx):
            if guide:
                ax.axvline(pos, color="0.35", ls=":", lw=0.9, zorder=0)
            ax.annotate(text, xy=(pos, top + 0.06 * span), xytext=(p, top + 0.16 * span), rotation=90, ha="center", va="bottom", fontsize=10,
                        arrowprops=dict(arrowstyle="-", lw=0.6, color="0.3") if abs(p - pos) > 1e-9 else None)
        ax.set_xlim(hi_, lo_)                             # high -> low
        ax.set_ylim(bot - 0.04 * span, top + 0.62 * span)
        ax.set_yticks([])
        ax.tick_params(axis="y", which="both", left=False, right=False)
        ax.set_xlabel(_ppm_title(book, df.columns[0]))
        ax.set_title(sh, fontsize=11.5, loc="right")
        if n > 1:
            panel_letter(ax, i)
    axs[0].set_ylabel(str(book.opt("y_title", "Intensity (a.u.)")))
    res.notes.append(f"{n} panel(s), ppm axis high → low, {len(labels)} label(s) from the Labels sheet" if labels else f"{n} panel(s), ppm axis high → low; no Labels sheet: no labels")


def draw_g05(book, fig, res):
    ds = book.data_sheets()
    rows = len(ds)
    full = (book.num_opt("full_from"), book.num_opt("full_to"))
    zoom = (book.num_opt("zoom_from"), book.num_opt("zoom_to"))
    gs = fig.add_gridspec(rows, 2, width_ratios=[1.45, 1], left=0.04, right=0.80, top=0.95, bottom=0.11, hspace=0.12, wspace=0.08)
    handles = {}
    for i, (sh, df) in enumerate(ds.items()):
        x = nums(df, df.columns[0])
        cmap = {norm(c): c for c in df.columns}
        exp_c = cmap.get("experimental")
        comps = [c for c in df.columns[1:] if c != exp_c and norm(c) not in ("sumoffit", "sum", "fit", "total") and is_num(df, c)]
        if "sumoffit" in cmap or "sum" in cmap:
            tot = nums(df, cmap.get("sumoffit") or cmap.get("sum"))
        else:
            tot = np.nansum([nums(df, c) for c in comps], axis=0)
            if i == 0:
                res.notes.append("'Sum of fit' = sum of the components (computed; the sheet has no such column)")
        for j, (a, b) in enumerate((full, zoom)):
            ax = fig.add_subplot(gs[i, j])
            a = float(np.nanmax(x)) if a is None else a
            b = float(np.nanmin(x)) if b is None else b
            hi_, lo_ = max(a, b), min(a, b)
            m = (x <= hi_) & (x >= lo_)
            if exp_c:
                h, = ax.plot(x[m], nums(df, exp_c)[m], color="#000000", lw=1.4)
                handles.setdefault("Experimental", h)
            for c in comps:
                h, = ax.plot(x[m], nums(df, c)[m], color=style_for(c)[0], lw=1.3)
                handles.setdefault(c, h)
            h, = ax.plot(x[m], tot[m], color="0.35", lw=1.2, ls="--")
            handles.setdefault("Sum of fit", h)
            ax.set_xlim(hi_, lo_)
            ax.set_yticks([])
            ax.tick_params(axis="y", which="both", left=False, right=False)
            if j == 0:
                ax.text(0.02, 0.85, sh, transform=ax.transAxes, fontsize=12)
            if i == rows - 1:
                ax.set_xlabel(_ppm_title(book, df.columns[0]))
            else:
                ax.set_xticklabels([])
    fig.legend(list(handles.values()), [chem(k) for k in handles], loc="center left", bbox_to_anchor=(0.81, 0.5))
    res.notes.append(f"{rows} row(s) (one per sheet); full range | zoom; component names are the column names")


def draw_g06(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    x = nums(df, df.columns[0])
    y = nums(df, [c for c in df.columns[1:] if is_num(df, c)][0])
    ax = _new_ax(fig)
    ax.plot(x, y, color="#000000", lw=1.4)
    top = float(np.nanmax(y))
    labels = sorted(labels_of(book), key=lambda l: -l[1])
    n = len(labels)
    lo_, hi_ = float(np.nanmin(x)), float(np.nanmax(x))
    minsep = 0.09 * (hi_ - lo_)
    placed = []                                                     # text x positions, pushed apart only when they would overlap
    for text, pos, _t, e in labels:                                  # labels sorted high -> low ppm (left -> right on the reversed axis)
        p = pos
        if placed and placed[-1] - p < minsep:
            p = placed[-1] - minsep
        placed.append(p)
    for (text, pos, _t, e), tx in zip(labels, placed):
        colour = str(e.get("colour") or e.get("color") or "black")
        colour = colour if colour.strip() and colour.lower() != "nan" else "black"
        w = np.abs(x - pos) < 0.6
        yp = float(np.nanmax(y[w])) if w.any() else float(np.interp(pos, x[::-1], y[::-1]))
        ax.annotate(chem(text), (pos, yp + 0.04 * top), (tx, yp + 0.30 * top), color=colour, ha="center", va="bottom", fontsize=11.5,
                    arrowprops=dict(arrowstyle="->", color=colour, lw=1.2, shrinkA=2, shrinkB=2))
        wv = str(e.get("writepositionvalue", "yes")).strip().lower()
        if wv.startswith("y"):
            ax.annotate(_fmt_num(e.get("_raw_pos", pos)), (pos, yp), xytext=(-7, 2), textcoords="offset points", rotation=90, color=colour,
                        ha="center", va="bottom", fontsize=10)
    ax.set_xlim(max(x), min(x))
    ax.set_ylim(min(0, float(np.nanmin(y))) - 0.05 * top, top * 1.5)
    ax.set_yticks([])
    ax.tick_params(axis="y", which="both", left=False, right=False)
    ax.set_xlabel(_ppm_title(book, df.columns[0]))
    res.notes.append(f"{n} label(s) from the Labels sheet, colours and ppm values as typed" if n else "no Labels sheet: no labels drawn")


# ------------------------------------------------------------------------------------------------ thermal analysis
def _tg_pairs(df):
    """[(name, TG column or None, DTG column or None)] from 'TG <name>' / 'DTG <name>' columns."""
    out = {}
    for c in df.columns[1:]:
        m = re.match(r"^\s*(D?TG)\s*(.*)$", str(c), re.I)
        if not m or not is_num(df, c):
            continue
        nm = base_name(m.group(2)) or m.group(1)
        d = out.setdefault(nm, [None, None])
        d[1 if m.group(1).upper() == "DTG" else 0] = c
    return [(k, v[0], v[1]) for k, v in out.items()]


def draw_g07(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    T = nums(df, df.columns[0])
    pairs = _tg_pairs(df)
    ax = fig.add_axes([0.09, 0.12, 0.80, 0.82])
    ax2 = ax.twinx()
    tg_all, dtg_all, dtg_curves = [], [], {}
    computed = []
    for name, tgc, dtgc in pairs:
        col = style_for(name)[0]
        if tgc:
            tg = nums(df, tgc)
            ax.plot(T, tg, color=col, lw=1.5, label=name)
            tg_all.append(tg)
        if dtgc:
            dtg = nums(df, dtgc)
        elif tgc:
            dtg = np.gradient(nums(df, tgc), T)                      # natural sign: mass loss gives negative values
            computed.append(name)
        else:
            continue
        ax2.plot(T, dtg, color=col, lw=1.5)
        dtg_all.append(dtg)
        dtg_curves[name] = dtg
    if computed:
        res.notes.append("DTG = dTG/dT computed for: " + ", ".join(computed) + " (%/°C, natural sign)")
    tmin, tmax = float(np.nanmin(np.concatenate(tg_all))), float(np.nanmax(np.concatenate(tg_all)))
    dmin, dmax = float(np.nanmin(np.concatenate(dtg_all))), float(np.nanmax(np.concatenate(dtg_all)))
    ts, dsp = (tmax - tmin) or 1, (dmax - dmin) or 1
    ax.set_ylim(tmin - 1.25 * ts, tmax + 0.08 * ts)                  # TG in the upper part ...
    ax2.set_ylim(dmin - 0.08 * dsp, dmax + 1.35 * dsp)               # ... DTG in the lower part, natural sign, no inversion
    ax.set_xlim(float(np.nanmin(T)), float(np.nanmax(T)))
    ax.set_xlabel(str(book.opt("x_title", "Temperature (°C)")))
    ax.set_ylabel(str(book.opt("y_title", "TG (%)")))
    du = unit(pairs[0][2]) if pairs and pairs[0][2] else ("%/°C" if computed else "%/min")
    ax2.set_ylabel(f"DTG ({du})")
    ax.tick_params(right=False)
    ax2.tick_params(direction="in")
    for s in ("left", "right", "top", "bottom"):
        ax2.spines[s].set_linewidth(1.5)
    ax.legend(loc="upper right")
    # labels with arrows at the DTG minima of the oldest age (last pair) unless a label row names a curve
    oldest = list(dtg_curves)[-1] if dtg_curves else None
    for text, pos, target, _e in labels_of(book):
        cur = target if target in dtg_curves else oldest
        if cur is None:
            continue
        d = dtg_curves[cur]
        w = (T > pos - 25) & (T < pos + 25)
        j = np.where(w)[0][np.argmin(d[w])] if w.any() else int(np.argmin(abs(T - pos)))
        ax2.annotate(chem(text), (T[j], d[j]), (T[j] + 0.04 * (T[-1] - T[0]), d[j] - 0.18 * dsp), fontsize=10.5, va="top",
                     arrowprops=dict(arrowstyle="->", lw=0.9))
    rng = book.sheet("ranges")
    if rng is not None and not rng.empty:
        cols = list(rng.columns)
        for k, r in rng.reset_index(drop=True).iterrows():          # in the gap between the TG band and the DTG band
            try:
                a, b = float(r[cols[1]]), float(r[cols[2]])
            except (TypeError, ValueError):
                continue
            yy = 0.475 - (k % 2) * 0.035
            ax.annotate("", (a, yy), (b, yy), xycoords=("data", "axes fraction"), textcoords=("data", "axes fraction"),
                        arrowprops=dict(arrowstyle="|-|", lw=1.2, mutation_scale=4))
            ax.annotate(chem(r[cols[0]]), ((a + b) / 2, yy), xycoords=("data", "axes fraction"), xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=10)
        res.notes.append(f"{len(rng)} temperature range bar(s) from the Ranges sheet, on the same graph")
    res.notes.append("ONE graph: TG on the left axis, DTG on the right axis, DTG with its natural sign (not inverted); same colour for the TG and DTG of one age")


def draw_g08(book, fig, res, ax=None, colours=None, df=None, labels=None):
    df = df if df is not None else book.sheet("dtg") if book.sheet("dtg") is not None and ax is not None else next(iter(book.data_sheets().values()))
    T = nums(df, df.columns[0])
    cols = [c for c in df.columns[1:] if is_num(df, c)]
    xto = book.num_opt("x_to") or book.num_opt("dtg_x_to")
    m = T <= xto if xto else np.ones(len(T), bool)
    own = ax is None
    ax = ax or _new_ax(fig)
    mode = "offset" if book.choice("mode", "overlay").startswith("offset") else "overlay"
    curves = {c: nums(df, c)[m] for c in cols}
    span = max(float(np.nanmax(v) - np.nanmin(v)) for v in curves.values()) or 1
    off = 0.0
    rows = []
    for c in cols:
        col = (colours or {}).get(c) or style_for(c)[0]
        ax.plot(T[m], curves[c] + off, color=col, lw=1.5, label=c)
        rows.append((c, float(np.nanmedian(curves[c][-max(3, len(curves[c]) // 25):])) + off, col))
        if mode == "offset":
            off += 1.15 * span
    ax.set_xlim(float(np.nanmin(T[m])), float(np.nanmax(T[m])))
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("DTG " + (f"({unit(cols[0])})" if unit(cols[0]) else "") + (", offset" if mode == "offset" else ""))
    if mode == "offset":
        ax.set_yticks([])
        end_labels(ax, rows, float(np.nanmax(T[m])), right=False)
    else:
        ax.legend(loc="lower right")
    labs = labels if labels is not None else labels_of(book, ("dtg labels", "labels"))
    allv = np.vstack([curves[c] for c in cols])
    for text, pos, target, _e in labs:
        w = (T[m] > pos - 25) & (T[m] < pos + 25)
        if not w.any():
            continue
        j = np.where(w)[0][np.argmin(allv[:, w].min(axis=0))]
        yv = float(allv[:, j].min())
        ax.annotate(chem(text), (T[m][j], yv), (T[m][j] + 0.07 * (T[m][-1] - T[m][0]), yv + 0.25 * span), fontsize=10.5, va="bottom",
                    arrowprops=dict(arrowstyle="->", lw=0.9))
    if own:
        res.notes.append(f"{len(cols)} DTG curve(s), {mode}")


def draw_g09(book, fig, res):
    xrd, dtg = book.sheet("xrd"), book.sheet("dtg")
    ax1 = fig.add_axes([0.06, 0.12, 0.42, 0.78])
    ax2 = fig.add_axes([0.56, 0.12, 0.41, 0.78])
    names = [c for c in xrd.columns[1:] if is_num(xrd, c)]
    miss = [c for c in names if c not in dtg.columns]
    if miss:
        res.notes.append("sample names not found in the DTG sheet: " + ", ".join(map(str, miss)))
    colours = {c: style_for(c)[0] for c in list(names) + [c for c in dtg.columns[1:] if c not in names]}
    _xrd_stack(ax1, nums(xrd, xrd.columns[0]), names, xrd, labels_of(book, ("xrd labels",)), book, colours, xtitle=str(book.opt("x_title", "2θ (°)")))
    ax1.set_ylabel("Intensity (a.u.)")
    draw_g08(book, fig, res, ax=ax2, colours=colours, df=dtg, labels=labels_of(book, ("dtg labels",)))
    panel_letter(ax1, 0)
    panel_letter(ax2, 1)
    res.notes.append("(a) XRD stack | (b) DTG; one colour per sample in both panels")


# ------------------------------------------------------------------------------------------------ calorimetry
def cumulative(t_h, hf):
    """Trapezoid rule, mW/g x h x 3.6 = J/g, starting at 0 at the first point."""
    t_h, hf = np.asarray(t_h, float), np.asarray(hf, float)
    q = np.zeros_like(hf)
    q[1:] = np.cumsum(0.5 * (hf[1:] + hf[:-1]) * np.diff(t_h) * 3.6)
    return q


def hf_columns(df):
    return [c for c in df.columns if "heat flow" in str(c).lower() and "cumulative" not in str(c).lower() and is_num(df, c)]


def hf_name(c, fallback="heat flow"):
    n = base_name(re.sub(r"(?i)\b(normali[sz]ed|specific)\b|\bheat flow\b", "", str(c))).strip(" -_:")
    return n or fallback


REGIME_COLOURS = ["#000000", "#1B7F1B", "#6A3D9A", "#B15928", "#1F78B4", "#E31A1C"]


def calo_samples(book):
    """Per sample: name, time (h), heat flow (mW/g), cumulative heat (J/g or None), from one table ('Heat flow <name>' columns) or
    from one sheet per sample. Plus the Samples sheet (Sample | Label | Regime | Alite fraction | Colour) when there is one."""
    out = []
    for sh, df in book.data_sheets().items():
        if sh.lower().startswith("samples"):
            continue
        t = nums(df, df.columns[0])
        cums = {norm(base_name(re.sub(r"(?i)cumulative\s*(heat)?(\s*flow)?", "", str(c))).strip(" -_:")): c for c in df.columns if "cumulative" in str(c).lower()}
        hfs = hf_columns(df)
        for c in hfs:
            nm = hf_name(c, sh if len(book.data_sheets()) > 1 else book.name)
            if len(hfs) == 1 and len(book.data_sheets()) > 1:
                nm = sh
            given = cums.get(norm(hf_name(c, ""))) or (next(iter(cums.values())) if len(hfs) == 1 and len(cums) == 1 else None)
            out.append({"name": nm, "t": t, "hf": nums(df, c), "cum": nums(df, given) if given is not None else None})
    info = {}
    sm = book.sheet("samples")
    if sm is not None and not sm.empty:
        cols = {norm(c): c for c in sm.columns}
        key = cols.get("sample") or sm.columns[0]
        for _, r in sm.iterrows():
            k = str(r[key]).strip()
            if not k or k.lower() == "nan":
                continue
            g = lambda *names: next((r[cols[n]] for n in names if n in cols and pd.notna(r[cols[n]]) and str(r[cols[n]]).strip()), None)
            af = g("alitefraction", "alite", "alitecontent", "alitewt", "alitewt%")
            try:
                af = float(str(af).replace(",", ".").replace("%", "")) if af is not None else None
                if af is not None and af > 1.5:
                    af = af / 100.0                                   # typed as % -> fraction
            except ValueError:
                af = None
            info[norm(k)] = {"label": str(g("label", "displayname") or k), "regime": None if g("regime", "group") is None else str(g("regime", "group")).strip(),
                             "alite": af, "colour": g("colour", "color")}
    return out, info


def _regime_text(r):
    r = str(r)
    return r if re.match(r"(?i)^regime\b", r) else f"Regime {r}"


def _calo_style(samples, info):
    """Colour per sample (Samples sheet, else the session colour) and colour per regime (in order of appearance)."""
    regimes = []
    for s_ in samples:
        rg = (info.get(norm(s_["name"])) or {}).get("regime")
        if rg and rg not in regimes:
            regimes.append(rg)
    rcol = {rg: REGIME_COLOURS[i % len(REGIME_COLOURS)] for i, rg in enumerate(regimes)}
    col = {}
    for s_ in samples:
        c = (info.get(norm(s_["name"])) or {}).get("colour")
        col[s_["name"]] = str(c) if c else style_for(s_["name"])[0]
    return col, rcol, regimes


def _cum_of(s_, excl_min=0.0):
    if s_["cum"] is not None and np.isfinite(s_["cum"]).any():
        return s_["cum"], True
    t, y = s_["t"], s_["hf"]
    keep = t >= t[0] + excl_min / 60.0
    q = np.full_like(y, np.nan)
    q[keep] = cumulative(t[keep], y[keep])
    return q, False


def main_peak(t, y):
    """(index of the end of the initial wetting spike, index of the main hydration peak or None). The spike is over at the lowest point of
    the first 3 h (or the first 5 % of the run, if shorter); a curve that only falls after it has no main peak."""
    fin = np.where(np.isfinite(y) & np.isfinite(t))[0]
    if len(fin) < 3:
        return (int(fin[0]) if len(fin) else 0), None
    ts = t[fin[0]]
    span = float(np.nanmax(t[fin]) - ts)
    early = fin[t[fin] <= ts + min(3.0, 0.05 * span if span > 0 else 3.0)]
    if len(early) < 3:
        early = fin[:5]
    i0 = int(early[np.nanargmin(y[early])])
    if i0 >= len(y) - 2:
        return i0, None
    j = i0 + int(np.nanargmax(y[i0:]))
    if j <= i0 + 1 or j >= len(y) - 2 or y[j] <= y[i0] * 1.05:
        return i0, None
    return i0, j


def draw_g10(book, fig, res):
    samples, info = calo_samples(book)
    if not samples:
        raise GalleryError("no heat flow column found (a column named 'heat flow' in mW/g)")
    excl_min = book.num_opt("exclusion_min", 0.0) or 0.0
    col, rcol, regimes = _calo_style(samples, info)
    tmax = max(float(np.nanmax(s_["t"])) for s_ in samples)
    xin = book.num_opt("inset_x_to_h") or (12.0 if tmax >= 48 else 1.0)
    lab = lambda s_: (info.get(norm(s_["name"])) or {}).get("label", s_["name"])
    ax1 = fig.add_axes([0.065, 0.12, 0.40, 0.80])
    ax2 = fig.add_axes([0.545, 0.12, 0.345 if regimes else 0.43, 0.80])
    rows, comp, peak = [], [], 0.0
    for s_ in samples:
        t, y = s_["t"], s_["hf"]
        c = col[s_["name"]]
        ax1.plot(t, y, color=c, lw=1.5, label=lab(s_))
        i0, pk_i = main_peak(t, y)                                               # the initial (wetting) spike does not set the scale
        peak = max(peak, float(np.nanmax(y[i0:])) if np.isfinite(y[i0:]).any() else 0.0)
        s_["_peak"] = (float(t[pk_i]), float(y[pk_i])) if pk_i is not None else None
        q, from_file = _cum_of(s_, excl_min)
        if from_file:
            calc, _ = _cum_of(dict(s_, cum=None), excl_min)
            ok = np.isfinite(calc) & np.isfinite(q) & (np.abs(q) > 1)
            dev = float(np.nanmax(np.abs(calc[ok] - q[ok]) / np.abs(q[ok]))) * 100 if ok.any() else float("nan")
            comp.append({"Curve": lab(s_), "Total from heat flow (J/g)": round(float(calc[np.isfinite(calc)][-1]), 2), "Total in the file (J/g)": round(float(q[np.isfinite(q)][-1]), 2), "Largest difference (%)": round(dev, 3)})
        else:
            comp.append({"Curve": lab(s_), "Total from heat flow (J/g)": round(float(q[np.isfinite(q)][-1]), 2), "Total in the file (J/g)": None, "Largest difference (%)": None})
        s_["_q"] = q
        ax2.plot(t, q, color=c, lw=1.5, label=lab(s_))
        rows.append((s_, float(q[np.isfinite(q)][-1])))
    ax1.set_xlim(float(min(s_["t"][0] for s_ in samples)), tmax)
    ax1.set_ylim(0, peak * 1.08)
    ax2.set_xlim(float(min(s_["t"][0] for s_ in samples)), tmax)
    ax2.set_ylim(bottom=0)
    ax1.set_xlabel("Time (h)")
    ax1.set_ylabel("Heat flow (mW g$^{-1}$)")
    ax2.set_xlabel("Time (h)")
    ax2.set_ylabel("Cumulative heat (J g$^{-1}$)")
    # regime names above the main peak of each curve (only when your Samples sheet gives them)
    placed = []                                                       # labels of peaks that lie close together are set side by side, never over each other
    xspan = (tmax - float(min(s_["t"][0] for s_ in samples))) or 1.0
    for s_ in sorted(samples, key=lambda s_: (s_.get("_peak") or (0, 0))[1]):
        rg = (info.get(norm(s_["name"])) or {}).get("regime")
        if rg and s_.get("_peak"):
            tx, ty = s_["_peak"]
            dx = 0
            while any(abs(tx - px) < 0.05 * xspan and abs(ty - py) < 0.08 * (peak or 1) and abs(dx - pd) < 20 for px, py, pd in placed):
                dx += 22                                              # side by side, to the right of the label already there
            placed.append((tx, ty, dx))
            ax1.annotate(rg if len(rg) <= 4 else rg[:4], (tx, ty), xytext=(dx, 6), textcoords="offset points", ha="center", va="bottom", fontsize=12,
                         fontweight="bold", color=rcol[rg], annotation_clip=False)
    ins = ax1.inset_axes([0.5, 0.47, 0.47, 0.46])
    for s_ in samples:
        m = s_["t"] <= float(np.nanmin(s_["t"])) + xin
        ins.plot(s_["t"][m], s_["hf"][m], color=col[s_["name"]], lw=1.3)
    ins.set_xlim(float(min(s_["t"][0] for s_ in samples)), float(min(s_["t"][0] for s_ in samples) + xin))
    ins.set_ylim(0, peak * 1.08)                                       # same scale as the main panel: the hydration peaks, not the wetting spike
    ins.set_title(f"first {xin:g} h", fontsize=10.5)
    ins.tick_params(labelsize=10)
    for tk_ in ins.get_xticklabels() + ins.get_yticklabels():
        tk_.set_fontweight("bold")
    for sp_ in ins.spines.values():
        sp_.set_linewidth(1.2)
    ax2.legend(loc="upper left", frameon=True, fancybox=False, edgecolor="0.6", fontsize=10.5)
    if regimes:                                                        # brackets at the right that group the curves by regime
        lo, hi = ax2.get_ylim()
        groups = []
        for rg in regimes:
            ends = [v for s_, v in rows if (info.get(norm(s_["name"])) or {}).get("regime") == rg]
            if ends:
                groups.append((min(ends), max(ends), rg))
        groups.sort()                                                  # brackets stay at the true end values; only their names are spread apart
        pad = 0.012 * (hi - lo); gap = 0.065 * (hi - lo)
        want = [(a_ + b_) / 2 for a_, b_, _ in groups]; pos = list(want)
        for _ in range(50):                                            # push apart, then keep the set centred on the true values, inside the axis
            for i in range(1, len(pos)):
                if pos[i] - pos[i - 1] < gap:
                    mid = (pos[i] + pos[i - 1]) / 2; pos[i - 1], pos[i] = mid - gap / 2, mid + gap / 2
            sh = float(np.mean(want) - np.mean(pos)) if pos else 0.0
            pos = [p_ + sh for p_ in pos]
            over = (pos[-1] - (hi - 0.02 * (hi - lo))) if pos else 0.0
            if over > 0: pos = [p_ - over for p_ in pos]
        for (a_, b_, rg), yl in zip(groups, pos):
            a_, b_ = a_ - pad, b_ + pad
            xb = 1.015
            ax2.plot([xb, xb + 0.012, xb + 0.012, xb], [a_, a_, b_, b_], transform=ax2.get_yaxis_transform(), clip_on=False, color=rcol[rg], lw=1.3)
            ym = (a_ + b_) / 2
            if abs(yl - ym) > 0.004 * (hi - lo):                    # name moved: a thin line from the bracket to it
                ax2.plot([xb + 0.012, xb + 0.028], [ym, yl], transform=ax2.get_yaxis_transform(), clip_on=False, color=rcol[rg], lw=0.8)
            ax2.text(xb + 0.03, yl, _regime_text(rg), transform=ax2.get_yaxis_transform(), va="center", ha="left", fontsize=12, fontweight="bold", color=rcol[rg], clip_on=False)
    panel_letter(ax1, 0)
    panel_letter(ax2, 1)
    res.tables["Cumulative heat"] = pd.DataFrame(comp)
    res.notes.append(f"cumulative heat Q = Σ ½(q_i + q_i-1)(t_i - t_i-1) × 3.6 (mW/g × h → J/g), from {excl_min:g} min after the first point (or the file's own cumulative columns); "
                     f"inset: first {xin:g} h; heat-flow axis scaled to the main peaks after the initial spike"
                     + ("; regimes, labels and colours from your Samples sheet" if info else ""))


def bar_q(book, at_h=None):
    """Q at time at_h for every sample (J/g, or per unit alite when the Samples sheet gives the alite fraction). Returns (rows, at_h, per_alite)."""
    samples, info = calo_samples(book)
    if not samples:
        raise GalleryError("no heat flow column found")
    excl_min = book.num_opt("exclusion_min", 0.0) or 0.0
    at_h = at_h or book.num_opt("bar_at_h") or min(float(np.nanmax(s_["t"])) for s_ in samples)
    per_alite = all((info.get(norm(s_["name"])) or {}).get("alite") for s_ in samples) and bool(info)
    rows = []
    for s_ in samples:
        q, _ = _cum_of(s_, excl_min)
        ok = np.isfinite(q)
        if at_h > float(np.nanmax(s_["t"][ok])) + 1e-9:
            raise GalleryError(f"{s_['name']}: the measurement ends at {np.nanmax(s_['t'][ok]):g} h, before {at_h:g} h")
        qv = float(np.interp(at_h, s_["t"][ok], q[ok]))
        inf = info.get(norm(s_["name"])) or {}
        val = qv / inf["alite"] if per_alite else qv
        rows.append({"Sample": s_["name"], "Label": inf.get("label", s_["name"]), "Regime": inf.get("regime"), f"Q at {at_h:g} h (J/g)": round(qv, 2),
                     **({"Alite fraction": inf["alite"], f"Q at {at_h:g} h per unit alite (J/g alite)": round(val, 2)} if per_alite else {}), "_v": val})
    return rows, at_h, per_alite


def draw_g10_bar(book, fig, res):
    rows, at_h, per_alite = bar_q(book)
    samples, info = calo_samples(book)
    col, rcol, regimes = _calo_style(samples, info)
    ax = fig.add_axes([0.09, 0.16, 0.88, 0.76])
    x = np.arange(len(rows))
    vals = np.array([r["_v"] for r in rows])
    ax.bar(x, vals, 0.62, color=[col[r["Sample"]] for r in rows], edgecolor="#000000", lw=1.0, zorder=3)
    top = float(np.nanmax(vals))
    for xi, v in zip(x, vals):
        ax.text(xi, v + 0.012 * top, f"{v:.0f}", ha="center", va="bottom", fontsize=12.5, fontweight="bold")
    labs = [re.sub(r"\s*\(", "\n(", str(r["Label"]), count=1) for r in rows]
    ax.set_xticks(x)
    ax.set_xticklabels(labs)
    ax.tick_params(axis="x", which="both", top=False, length=0)
    ax.set_xlim(-0.6, len(rows) - 0.4)
    q_lab = f"Q$_{{{at_h:g}}}$"
    ax.set_ylabel(f"{q_lab} per unit alite (J g$^{{-1}}$ alite)" if per_alite else f"{q_lab} (J g$^{{-1}}$)")
    ax.set_xlabel(str(book.opt("bar_x_title", "Sample")))
    for sp_ in ("top", "right"):
        ax.spines[sp_].set_visible(False)
    ax.tick_params(right=False, top=False)
    ylim_top = top * 1.08
    for rg in regimes:                                                  # bracket over each regime group
        idx = [i for i, r in enumerate(rows) if r["Regime"] == rg]
        if not idx:
            continue
        h = max(vals[i] for i in idx) + 0.09 * top
        ax.plot([min(idx) - 0.3, min(idx) - 0.3, max(idx) + 0.3, max(idx) + 0.3], [h - 0.02 * top, h, h, h - 0.02 * top], color=rcol[rg], lw=1.5)
        ax.text((min(idx) + max(idx)) / 2, h + 0.012 * top, _regime_text(rg), ha="center", va="bottom", fontsize=12.5, fontweight="bold", color=rcol[rg])
        ylim_top = max(ylim_top, h + 0.09 * top)
    ax.set_ylim(0, ylim_top)
    res.tables["Q at time"] = pd.DataFrame([{k: v for k, v in r.items() if k != "_v"} for r in rows])
    res.notes.append(f"Q at {at_h:g} h interpolated on the cumulative heat curve" + ("; divided by the alite fraction of your Samples sheet (J/g alite)" if per_alite else ""))


def extra_figures(tid, book):
    """Further figures a type makes besides its main one: [(name suffix, drawer)]. G10: the bar chart of Q at a time (2 or more samples)."""
    if tid == "G10":
        try:
            samples, _ = calo_samples(book)
        except Exception:          # noqa: BLE001
            return []
        if len(samples) >= 2:
            return [("Q_bar", draw_g10_bar)]
    return []


def draw_g11(book, fig, res):
    con = book.sheet("concentration")
    hf = book.sheet("heat flow")
    ax = fig.add_axes([0.09, 0.12, 0.80, 0.82])
    ax2 = ax.twinx()
    t = nums(con, con.columns[0])
    hs = []
    for k, c in enumerate([c for c in con.columns[1:] if is_num(con, c)]):
        col, mk, filled = style_for(base_name(c))
        h, = ax.plot(t, nums(con, c), color=col, marker=mk, mfc=col if filled else "white", lw=1.2, label=chem(base_name(c)))
        hs.append(h)
    ax.set_yscale("log")
    t2 = nums(hf, hf.columns[0])
    hcol = [c for c in hf.columns[1:] if is_num(hf, c)][0]
    h2, = ax2.plot(t2, nums(hf, hcol), "k--", lw=1.5, label=base_name(hcol).lower())
    ax.set_xlabel(con.columns[0])
    ax.set_ylabel("Concentration " + (f"({unit(con.columns[1])})" if unit(con.columns[1]) else ""))
    ax2.set_ylabel(base_name(hcol) + (f" ({unit(hcol)})" if unit(hcol) else ""))
    ax.tick_params(right=False)
    ax.set_xlim(min(float(np.nanmin(t)), float(np.nanmin(t2))), max(float(np.nanmax(t)), float(np.nanmax(t2))))
    ax.legend(hs + [h2], [h.get_label() for h in hs + [h2]], loc="center right")
    res.notes.append("left axis logarithmic (symbols + lines), right axis linear (dashed); the two sheets keep their own time points")


# ------------------------------------------------------------------------------------------------ split time axis (G12, G13 split)
def split_axes(fig, cell, lin_to=0.04, log_from=0.06, log_to=130.0, ybreak=None, width_ratios=(1, 4.5)):
    """Axes for a time axis with a short linear segment (shows t = 0), a // break and a log segment.
    ybreak=(a, b): a y-axis break as well (two rows). Returns (grid of axes [row][col], list of all axes)."""
    rows = 2 if ybreak else 1
    gs = cell.subgridspec(rows, 2, width_ratios=list(width_ratios), wspace=0.05, hspace=0.06, height_ratios=[1, 2.2] if ybreak else None)
    grid = [[None, None] for _ in range(rows)]
    for r in range(rows):
        grid[r][0] = fig.add_subplot(gs[r, 0], sharey=grid[r - 1][0] if False else None)
        grid[r][1] = fig.add_subplot(gs[r, 1], sharey=grid[r][0])
    for r in range(rows):
        a0, a1 = grid[r]
        a0.set_xlim(-0.12 * lin_to, lin_to)
        a0.set_xticks([0])
        a0.set_xticklabels(["0.00"])
        a1.set_xscale("log")
        a1.set_xlim(log_from, log_to)
        a0.spines["right"].set_visible(False)
        a1.spines["left"].set_visible(False)
        a0.tick_params(right=False, which="both")
        a1.tick_params(left=False, labelleft=False, which="both")
        kw = dict(color="k", clip_on=False, lw=1.2)
        wr = width_ratios[1] / width_ratios[0]
        for ax, xx, sc in ((a0, 1, wr), (a1, 0, 1)):
            for yy in (0, 1):
                d = 0.012
                ax.plot([xx - d * sc, xx + d * sc], [yy - 0.025, yy + 0.025], transform=ax.transAxes, **kw)
        if ybreak and r == 0:
            for ax in (a0, a1):
                ax.spines["bottom"].set_visible(False)
                ax.tick_params(bottom=False, labelbottom=False, which="both")
        if ybreak and r == 1:
            for ax in (a0, a1):
                ax.spines["top"].set_visible(False)
                ax.tick_params(top=False, which="both")
    return grid, [a for row in grid for a in row]


def _errplot(ax, x, y, e, name, ls="--", method=False):
    col, mk, filled = style_for(name, method)
    ax.errorbar(x, y, yerr=e, color=col, marker=mk, ms=5.5, ls=ls, lw=1.0, capsize=2.5, elinewidth=1.0, mfc=col if filled else "white", mec=col, label=chem(name))


def _y_break(book, key):
    v = book.opt(key)
    if not v or re.search(r"e\.g\.|optional|example", str(v).lower()):
        return None
    m = re.findall(r"[-+]?\d+(?:[.,]\d+)?", str(v))
    return (float(m[0].replace(",", ".")), float(m[1].replace(",", "."))) if len(m) >= 2 else None


def draw_g12(book, fig, res):
    ds = book.data_sheets()
    n = len(ds)
    gs = fig.add_gridspec(1, n, left=0.08, right=0.98, top=0.95, bottom=0.12, wspace=0.28)
    connect = "none" not in str(book.opt("connect", "dashed")).lower()
    lin_to = book.num_opt("split_linear_to", 0.04) or 0.04
    log_from = book.num_opt("split_log_from", 0.06) or 0.06
    for i, (sh, df) in enumerate(ds.items()):
        t = nums(df, df.columns[0])
        pairs = value_sd_pairs(df, df.columns[0])
        tmax = float(np.nanmax(t))
        yb = _y_break(book, "y_break_right") if i == n - 1 and n > 1 else _y_break(book, "y_break") if n == 1 else None
        grid, axs = split_axes(fig, gs[i], lin_to, log_from, 10 ** math.ceil(math.log10(tmax * 1.2)) if tmax > 0 else 100, yb)
        for vc, sc in pairs:
            y = nums(df, vc)
            e = nums(df, sc) if sc else None
            for ax in axs:
                _errplot(ax, t, y, e, base_name(vc), "--" if connect else "none")
        allv = np.concatenate([nums(df, vc) + (np.nan_to_num(nums(df, sc)) if sc else 0) for vc, sc in pairs])
        top = float(np.nanmax(allv)) * 1.1
        if yb:
            lo_, hi_ = min(yb), max(yb)
            for ax in grid[1]:
                ax.set_ylim(0, lo_)
            for ax in grid[0]:
                ax.set_ylim(hi_, max(top, hi_ * 1.05))
            grid[1][0].set_ylabel(_ytitle(book, pairs))
        else:
            grid[0][0].set_ylim(0, top)
            grid[0][0].set_ylabel(_ytitle(book, pairs))
        grid[-1][1].set_xlabel(str(book.opt("x_title", "Time (days)")), x=0.4)
        grid[0][1].legend(loc="upper right" if i == 0 else "upper left", fontsize=10)
        if n > 1:
            panel_letter(grid[0][0], i)
            grid[0][1].set_title(sh, fontsize=11.5, loc="right")
    res.notes.append(f"time axis: linear 0-{lin_to:g} d, // break, log from {log_from:g} d; error bars from the SD columns; points joined by dashed lines (guide to the eye)")


def _ytitle(book, pairs):
    if book.opt("y_title"):
        return str(book.opt("y_title"))
    u = unit(pairs[0][0]) if pairs else ""
    return f"Phase content ({u})" if u else "Phase content"


# ------------------------------------------------------------------------------------------------ LONG grids (G13 G14 G15, C01 C02 graphs)
def to_long(book):
    """LONG table Panel | Series | X | Value | SD from the LONG layout, from WIDE columns '<Panel> | <Series>', or from one sheet per panel."""
    ds = book.data_sheets()
    first = next(iter(ds.values()))
    cmap = {norm(c): c for c in first.columns}
    if {"panel", "series", "value"} <= set(cmap):
        xcol = next(c for c in first.columns if norm(c) not in ("panel", "series", "value", "sd") and not sd_of(c))
        out = pd.DataFrame({"Panel": first[cmap["panel"]].astype(str), "Series": first[cmap["series"]].astype(str), "X": nums(first, xcol),
                            "Value": nums(first, cmap["value"]), "SD": nums(first, cmap["sd"]) if "sd" in cmap else np.nan})
        return out, xcol, False
    rows = []
    xname = first.columns[0]
    for sh, df in ds.items():
        x = nums(df, df.columns[0])
        for vc, sc in value_sd_pairs(df, df.columns[0]):
            if "|" in str(vc):
                p, s = [q.strip() for q in str(vc).split("|", 1)]
            else:
                p, s = (sh, base_name(vc)) if len(ds) > 1 else (base_name(vc), "")
            v = nums(df, vc)
            e = nums(df, sc) if sc else np.full(len(v), np.nan)
            rows += [(p, s, a, b, c) for a, b, c in zip(x, v, e)]
    return pd.DataFrame(rows, columns=["Panel", "Series", "X", "Value", "SD"]), xname, True


def draw_long(book, fig, res, method=False, refs=None, ann=None, long=None, xname=None, y_title=None):
    if long is None:
        long, xname, wide = to_long(book)
        if wide:
            res.tables["LONG table made from your sheet"] = long
            res.notes.append("WIDE input converted to the LONG layout Panel | Series | X | Value | SD (shown in the results table)")
    panels = list(dict.fromkeys(long["Panel"]))
    series = list(dict.fromkeys(long["Series"]))
    ncol = int(book.num_opt("columns", 2 if len(panels) > 1 else 1) or 2)
    ncol = max(1, min(ncol, len(panels)))
    nr = math.ceil(len(panels) / ncol)
    xlog = book.yes("x_log", True)
    split = book.yes("split_axis")
    same_y = book.yes("same_y_range")
    legend_h = 0.10 if len(series) > 1 or refs is not None else 0.02
    gs = fig.add_gridspec(nr, ncol, left=0.08, right=0.98, top=0.94, bottom=0.10 + legend_h, hspace=0.42, wspace=0.26)
    handles = {}
    ymax = float(np.nanmax(long["Value"] + np.nan_to_num(long["SD"]))) * 1.12
    for i, p in enumerate(panels):
        cell = gs[i // ncol, i % ncol]
        q = long[long.Panel == p]
        if split:
            tmax = float(np.nanmax(long["X"]))
            grid, axs = split_axes(fig, cell, 0.04, 0.06, 10 ** math.ceil(math.log10(tmax * 1.2)))
            main = grid[0][0]
        else:
            ax = fig.add_subplot(cell)
            axs = [ax]
            main = ax
        for s in series:
            r = q[q.Series == s]
            if r.empty:
                continue
            for ax in axs:
                if not split and xlog and (r.X <= 0).any():
                    rr = r[r.X > 0]
                else:
                    rr = r
                _errplot(ax, rr.X.to_numpy(), rr.Value.to_numpy(), rr.SD.to_numpy() if rr.SD.notna().any() else None, s or p, method=method)
            hh, ll = axs[-1].get_legend_handles_labels()
            if ll:
                handles.setdefault(s or p, hh[-1])
        if not split and xlog:
            axs[0].set_xscale("log")
        if refs is not None:
            for _, rf in refs[refs.iloc[:, 0].astype(str) == str(p)].iterrows():
                for ax in axs:
                    h = ax.axhline(float(rf.iloc[2]), color="0.45", ls="-.", lw=1.2, label=str(rf.iloc[1]))
                handles.setdefault(str(rf.iloc[1]), h)
        if ann is not None:
            for _, an in ann[ann.iloc[:, 0].astype(str) == str(p)].iterrows():
                axs[-1].text(float(an.iloc[1]), float(an.iloc[2]), str(an.iloc[3]), ha="right", va="bottom", fontsize=10.5, color="#0072B2")
        if same_y:
            main.set_ylim(0, ymax)
        else:
            top = float(np.nanmax(q.Value + np.nan_to_num(q.SD)))
            if refs is not None:
                rv = refs[refs.iloc[:, 0].astype(str) == str(p)]
                if len(rv):
                    top = max(top, float(rv.iloc[:, 2].astype(float).max()))
            main.set_ylim(0, top * 1.18 if top > 0 else 1)
        main.text(0.05, 0.9, chem(p), transform=main.transAxes, fontsize=11.5, va="top")
        (axs[-1] if split else main).set_xlabel(xname or "Time (days)")
        main.set_ylabel(wrap_title(y_title or str(book.opt("y_title", "Value")), 30 if nr > 1 else 45))
        if len(panels) > 1:
            panel_letter(main, i)
    if len(handles) > 1 or refs is not None:
        fig.legend(list(handles.values()), [chem(k) for k in handles], loc="lower center", ncol=min(len(handles), 5), bbox_to_anchor=(0.5, 0.005))
    res.notes.append(f"{len(panels)} panel(s) in {nr} × {ncol}; {len(series)} series, each with one colour and symbol in every panel; one shared legend under the grid")


def draw_g13(book, fig, res):
    draw_long(book, fig, res)


def draw_g14(book, fig, res):
    draw_long(book, fig, res, method=True)
    res.notes.append("methods keep fixed styles: QXRD black squares, TGA blue circles, stoichiometric calculation orange triangles, NMR pink diamonds")


def draw_g15(book, fig, res):
    refs = book.sheet("reference")
    ann = book.sheet("annotations")
    draw_long(book, fig, res, refs=refs if refs is not None and not refs.empty else None, ann=ann if ann is not None and not ann.empty else None)
    res.notes.append("reference lines dash-dot grey (in the legend); annotations only as typed in the Annotations sheet")


# ------------------------------------------------------------------------------------------------ against a variable, scatter, bars
def draw_g16(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    xc = df.columns[0]
    x = nums(df, xc)
    ax = _new_ax(fig)
    pairs = value_sd_pairs(df, xc)
    for vc, sc in pairs:
        _errplot(ax, x, nums(df, vc), nums(df, sc) if sc else None, base_name(vc), "--" if "none" not in str(book.opt("connect", "dashed")).lower() else "none")
    xt = str(book.opt("x_title", base_name(xc)))
    if book.yes("x_title_arrow"):
        xt += "  →"
    ax.set_xlabel(xt)
    ax.set_ylabel(str(book.opt("y_title", f"({unit(pairs[0][0])})" if pairs and unit(pairs[0][0]) else "Value")))
    pad = 0.05 * (np.nanmax(x) - np.nanmin(x))
    ax.set_xlim(np.nanmin(x) - pad, np.nanmax(x) + pad)
    ax.legend(loc="best")
    res.notes.append(f"{len(pairs)} series; SD columns as error bars")


def draw_g17(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    cols = list(df.columns)
    lab = next((c for c in cols if norm(c) == "label"), None)
    numc = [c for c in cols if c != lab and is_num(df, c)]
    xc = next((c for c in numc if norm(c) == norm(book.opt("x", ""))), numc[0])
    yc = next((c for c in numc if norm(c) == norm(book.opt("y", ""))), [c for c in numc if c != xc][0])
    x, y = nums(df, xc), nums(df, yc)
    ax = _new_ax(fig)
    ax.plot(x, y, "D", color="#1F3BFF", ms=7, mec="#000000", mew=0.6)
    if lab:
        for xi, yi, t in zip(x, y, df[lab].astype(str)):
            ax.annotate(t, (xi, yi), xytext=(6, 5), textcoords="offset points", fontsize=10)
    fit = str(book.opt("fit", "none")).lower()
    if fit.startswith("linear"):
        ok = np.isfinite(x) & np.isfinite(y)
        p = np.polyfit(x[ok], y[ok], 1)
        xx = np.linspace(np.nanmin(x), np.nanmax(x), 50)
        ax.plot(xx, np.polyval(p, xx), "--", color="#E69F00", lw=1.5)
        r2 = 1 - np.sum((y[ok] - np.polyval(p, x[ok])) ** 2) / np.sum((y[ok] - y[ok].mean()) ** 2)
        if not str(book.opt("show_equation", "yes")).lower().startswith("no"):
            sig = lambda v: f"{v:.3g}"
            ax.text(0.97, 0.94, f"y = {sig(p[0])}x {'+' if p[1] >= 0 else '−'} {sig(abs(p[1]))}    R² = {r2:.3f}", transform=ax.transAxes, ha="right", va="top", fontsize=11.5)
        res.tables["Linear fit"] = pd.DataFrame([{"slope": p[0], "intercept": p[1], "R2": r2, "points": int(ok.sum())}])
        res.notes.append(f"linear least-squares fit y = a·x + b: a = {p[0]:.4g}, b = {p[1]:.4g}, R² = {r2:.4f} ({int(ok.sum())} points)")
    ax.set_xlabel(xc)
    ax.set_ylabel(yc)
    pad = 0.12 * (np.nanmax(x) - np.nanmin(x))
    ax.set_xlim(np.nanmin(x) - 0.05 * pad, np.nanmax(x) + pad)


HATCHES = ["", "///", "\\\\\\", "xxx", "...", "---", "+++", "ooo"]


def draw_g18(book, fig, res, line_col=None):
    df = next(iter(book.data_sheets().values()))
    cat = df.columns[0]
    pairs = [(v, s) for v, s in value_sd_pairs(df, cat) if v != line_col]
    bars = [p for p in pairs]
    bar_list = str(book.opt("bars", "") or "")
    if bar_list and line_col is not None:
        want = [norm(b) for b in re.split(r"[,;]", bar_list) if b.strip()]
        bars = [p for p in pairs if norm(p[0]) in want] or bars
    ax = fig.add_axes([0.09, 0.2 if line_col is not None else 0.12, 0.88, 0.74 if line_col is not None else 0.82])
    x = np.arange(len(df))
    w = 0.8 / max(len(bars), 1)
    hatch = book.choice("fill").startswith("hatch")
    for k, (vc, sc) in enumerate(bars):
        col = style_for(vc)[0]
        e = nums(df, sc) if sc else None
        ax.bar(x + (k - (len(bars) - 1) / 2) * w, nums(df, vc), w, yerr=e, color="white" if hatch else col, ec="#000000", lw=1.0,
               hatch=HATCHES[k % len(HATCHES)] if hatch else None, capsize=4, error_kw=dict(lw=1.2, capthick=1.2), label=chem(vc))
    ax.set_xticks(x)
    ax.set_xticklabels(df[cat].astype(str))
    ax.set_xlabel(cat)
    ax.set_ylabel(str(book.opt("y_title", "Value")))
    ax.set_xlim(-0.6, len(df) - 0.4)
    top = max(float(np.nanmax(nums(df, vc) + (np.nan_to_num(nums(df, sc)) if sc else 0))) for vc, sc in bars)
    if line_col is not None:
        ly = nums(df, line_col)
        top = max(top, float(np.nanmax(ly)))
        col, mk, _f = style_for(line_col, method=True)
        ax.plot(x, ly, marker=mk, ls="--", color=col, lw=1.5, ms=7, label=chem(line_col))
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=len(bars) + 1)
    else:
        ax.legend(loc="upper left")
    ax.set_ylim(0, top * 1.2)
    ax.tick_params(axis="x", which="both", top=False)
    res.notes.append(f"{len(bars)} bar series per group" + ("; hatch fills" if hatch else "") + "; SD columns as error bars with caps")


def draw_g19(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    cat = df.columns[0]
    vals = [c for c in df.columns[1:] if is_num(df, c) and not sd_of(c)]
    line = str(book.opt("line", "") or "")
    lc = next((c for c in vals if line and norm(c) in norm(line.split("(")[0])), None) or next((c for c in vals if re.search(r"stoich|calculat|model", c.lower())), vals[-1])
    if not any(norm(c) == "difference" for c in df.columns):
        nmr = next((c for c in vals if "nmr" in c.lower()), None)
        xrd = next((c for c in vals if "xrd" in c.lower()), None)
        if nmr and xrd:
            df = df.copy()
            df["Difference"] = nums(df, nmr) - nums(df, xrd)
            res.notes.append(f"Difference = {nmr} - {xrd} (computed; the file has no Difference column)")
            book.sheets[next(iter(book.data_sheets()))] = df
    draw_g18(book, fig, res, line_col=lc)
    res.notes.append(f"'{lc}' drawn as a dashed line with symbols over the bars")


def draw_g20(book, fig, res):
    ds = book.data_sheets()
    n = len(ds)
    marks = book.yes("d_values")
    axs = [fig.add_axes([0.07 + i * (0.91 / n), 0.13, 0.91 / n - 0.025, 0.78]) for i in range(n)]
    rows = []
    for i, (sh, df) in enumerate(ds.items()):
        ax = axs[i]
        x = nums(df, df.columns[0])
        for c in [c for c in df.columns[1:] if is_num(df, c)]:
            nm = re.sub(r"\s*cumulative.*$", "", base_name(c), flags=re.I) or base_name(c)
            y = nums(df, c)
            ax.plot(x, y, color=style_for(nm)[0], lw=1.5, label=nm)
            o = np.argsort(y)
            for q in (10, 50, 90):
                d = float(10 ** np.interp(q, y[o], np.log10(x[o]))) if y.min() <= q <= y.max() else float("nan")
                rows.append({"Group": sh, "Material": nm, f"D{q} (µm)": round(d, 3)})
                if marks and np.isfinite(d):
                    ax.plot([d], [q], "|", color=style_for(nm)[0], ms=10, mew=1.5)
        ax.set_xscale("log")
        ax.set_ylim(0, 102)
        ax.set_xlabel(df.columns[0])
        ax.legend(loc="upper left")
        ax.set_title(f"({chr(97 + i)}) {sh}" if n > 1 else sh, fontsize=11.5, loc="left")
        if i:
            ax.set_yticklabels([])
    axs[0].set_ylabel(str(book.opt("y_title", "Cumulative volume (%)")))
    t = pd.DataFrame(rows).groupby(["Group", "Material"], sort=False).first().reset_index()
    res.tables["D10 D50 D90"] = t
    res.notes.append("one panel per sheet, log size axis; D10/D50/D90 interpolated on the log axis (results table)")


def phase_colour(name, k):
    key = norm(name)
    for p, c in PHASE_COLOURS.items():
        if key == norm(p) or key.startswith(norm(p)):
            return c
    return OKABE[k % len(OKABE)]


def draw_g21(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    x = nums(df, df.columns[0])
    cols = [c for c in df.columns[1:] if is_num(df, c)]
    ax = fig.add_axes([0.08, 0.12, 0.74, 0.82])
    base = np.zeros(len(x))
    small = []
    xlog = book.yes("x_log", x.min() > 0 and x.max() / max(x.min(), 1e-12) > 50)
    for k, c in enumerate(cols):
        v = np.nan_to_num(nums(df, c))
        nm = base_name(c)
        hatch = "///" if norm(nm).startswith(("anhydrous", "clinker", "unreacted")) else ("..." if norm(nm) in ("ms", "monosulfate") else None)
        ax.fill_between(x, base, base + v, facecolor=phase_colour(nm, k), edgecolor="0.25", lw=0.6, hatch=hatch, label=chem(nm))
        a_, b_ = int(0.15 * len(x)), max(int(0.85 * len(x)), int(0.15 * len(x)) + 1)
        j = a_ + int(np.argmax(v[a_:b_]))                    # widest place of the band, away from the edges
        if v[j] >= 3.0:
            ax.text(x[j], base[j] + v[j] / 2, chem(nm), ha="center", va="center", fontsize=11)
        else:
            small.append(nm)
        base = base + v
    if xlog:
        ax.set_xscale("log")
    ax.set_xlim(float(np.nanmin(x)), float(np.nanmax(x)))
    ax.set_ylim(0, book.num_opt("y_max", max(100.0, float(np.nanmax(base)))))
    ax.set_xlabel(df.columns[0])
    ax.set_ylabel(str(book.opt("y_title", unit(cols[0]) or "g/100 g paste")))
    if small:
        hs, ls = ax.get_legend_handles_labels()
        keep = [i for i, l in enumerate(ls) if l in [chem(s) for s in small]]
        ax.legend([hs[i] for i in keep], [ls[i] for i in keep], loc="center left", bbox_to_anchor=(1.01, 0.5))
        res.notes.append("bands thinner than 3 g/100 g are named in the legend: " + ", ".join(small))
    res.notes.append("stacked in column order (first at the bottom); fixed colour per phase name; anhydrous hatched")


# ------------------------------------------------------------------------------------------------ ternary
def tern_xy(a, b, c):
    """Barycentric (bottom-left a, bottom-right b, top c) -> x, y."""
    a, b, c = np.asarray(a, float), np.asarray(b, float), np.asarray(c, float)
    s = a + b + c
    return (b + 0.5 * c) / s, (np.sqrt(3) / 2) * c / s


def tern_frame(ax, names, grid=True, ticks=True):
    h = np.sqrt(3) / 2
    ax.plot([0, 1, 0.5, 0], [0, 0, h, 0], "k", lw=1.5, zorder=3)
    if grid:
        for f in (0.25, 0.5, 0.75):
            for p, q in (((f, 1 - f, 0), (f, 0, 1 - f)), ((1 - f, f, 0), (0, f, 1 - f)), ((1 - f, 0, f), (0, 1 - f, f))):
                x, y = tern_xy(*np.array([p, q]).T)
                ax.plot(x, y, color="0.8", lw=0.7, zorder=0)
    if ticks:
        for f in (0, 25, 50, 75, 100):
            x, y = tern_xy(100 - f, f, 0)
            ax.text(x, y - 0.045, str(f), ha="center", va="top", fontsize=10)          # along the bottom: % of the right corner
            x, y = tern_xy(f, 0, 100 - f)
            ax.text(x - 0.035, y, str(100 - f), ha="right", va="center", fontsize=10)  # left side: % of the top corner
            x, y = tern_xy(0, 100 - f, f)
            ax.text(x + 0.035, y, str(100 - f), ha="left", va="center", fontsize=10)   # right side: % of the right corner
    ax.text(-0.05, -0.06, names[0], ha="right", va="top", fontsize=13, fontweight="bold")
    ax.text(1.05, -0.06, names[1], ha="left", va="top", fontsize=13, fontweight="bold")
    ax.text(0.5, h + 0.05, names[2], ha="center", va="bottom", fontsize=13, fontweight="bold")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-0.2, 1.2)
    ax.set_ylim(-0.14, h + 0.14)


def _corners(book, comp):
    """Order of the composition columns as (bottom-left, bottom-right, top), from the Options 'corners' text when given."""
    spec = str(book.opt("corners", "") or "").lower()
    names = {c: norm(base_name(c)) for c in comp}
    if spec:
        pos = {}
        for key in ("bottom-left", "bottom-right", "top"):
            i = spec.find(key)
            if i < 0:
                continue
            seg = spec[i + len(key):].split(",")[0]
            for c, n in names.items():
                if n and n in norm(seg):
                    pos[key] = c
        if len(set(pos.values())) == 3:
            return [pos["bottom-left"], pos["bottom-right"], pos["top"]]
    find = lambda *keys: next((c for c, n in names.items() if any(n.startswith(k) for k in keys)), None)
    cac, opc, sul = find("cac", "calciumaluminate"), find("opc", "portland", "cement"), find("sulph", "sulf", "gypsum", "anhydrite", "cs")
    if cac and opc and sul and len({cac, opc, sul}) == 3:
        return [cac, opc, sul]                       # convention: CAC bottom-left, PC bottom-right, sulphate top
    return list(comp[:3])


def _comp_cols(df):
    return [c for c in df.columns if (re.search(r"mass.?%|wt.?%|mole.?%|mol.?%", str(c).lower()) or norm(base_name(c)) in ("opc", "cac", "sulphate", "sulfate")) and is_num(df, c)][:3]


def draw_g22(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    comp = _comp_cols(df)
    order = _corners(book, comp)
    a, b, c = (nums(df, k) for k in order)
    s = a + b + c
    bad = np.abs(s - 100) > 1
    if bad.any():
        res.notes.append(f"{int(bad.sum())} row(s) do not add up to 100 % and were normalised: " + ", ".join(f"{df.iloc[i, 0]} ({s[i]:.1f})" for i in np.where(bad)[0]))
    ax = fig.add_axes([0.1, 0.04, 0.8, 0.92])
    tern_frame(ax, [base_name(k) for k in order])
    x, y = tern_xy(a, b, c)
    ax.plot(x, y, "o", color="#C00000", ms=9, mec="#000000", mew=0.8, zorder=4)
    lab = next((k for k in df.columns if norm(k) == "label"), df.columns[0] if not is_num(df, df.columns[0]) else None)
    if lab:
        for xi, yi, t in zip(x, y, df[lab].astype(str)):
            ax.annotate(t, (xi, yi), xytext=(7, 6), textcoords="offset points", fontsize=11)
    res.notes.append(f"corners: bottom-left {order[0]}, bottom-right {order[1]}, top {order[2]}; gridlines every 25 %")


def draw_g23(book, fig, res):
    df = next(iter(book.data_sheets().values()))
    comp = _comp_cols(df)
    order = _corners(book, comp)
    vals = [c for c in df.columns if c not in comp and is_num(df, c)]
    n = len(vals)
    ncol = 2 if n > 1 else 1
    nr = math.ceil(n / ncol)
    cm_txt = book.choice("colour_map") or book.choice("color_map")
    cmap = "jet" if ("jet" in cm_txt or "blue-green-yellow-red" in cm_txt or "rainbow" in cm_txt) else "viridis"
    levels = int(book.num_opt("levels", 20) or 20)
    x, y = tern_xy(*(nums(df, k) for k in order))
    gs = fig.add_gridspec(nr, ncol, left=0.02, right=0.98, top=0.97, bottom=0.03, wspace=0.05, hspace=0.12)
    for k, vc in enumerate(vals):
        ax = fig.add_subplot(gs[k // ncol, k % ncol])
        z = nums(df, vc)
        ok = np.isfinite(z) & np.isfinite(x)
        cs = ax.tricontourf(x[ok], y[ok], z[ok], levels=levels, cmap=cmap)
        tern_frame(ax, [base_name(q) for q in order], grid=False, ticks=True)
        cb = fig.colorbar(cs, ax=ax, shrink=0.85, pad=0.01)
        cb.set_label(chem(vc), fontsize=10.5)
        cb.ax.tick_params(labelsize=9.5)
        if n > 1:
            panel_letter(ax, k, 0.96)
    res.notes.append(f"{n} panel(s); points triangulated; {levels} levels; colour map {cmap}")


# ------------------------------------------------------------------------------------------------ G24, C01, C02
def draw_g24(book, fig, res):
    df = next(iter(book.data_sheets().values())).copy()
    cmap = {norm(c): c for c in df.columns}
    fcol = next((c for c in df.columns if not is_num(df, c)), df.columns[0])
    tcol = next(c for c in df.columns if _kind_of_x(c) == "time")
    if "chi2" in cmap or "χ2" in cmap:
        df["chi2"] = nums(df, cmap.get("chi2") or cmap["χ2"])
        res.notes.append("χ² from the file")
    else:
        df["chi2"] = (nums(df, cmap["rwp"]) / nums(df, cmap["rexp"])) ** 2
        res.notes.append("χ² = (Rwp / Rexp)² computed for every row (results table)")
    ax = _new_ax(fig)
    for f in dict.fromkeys(df[fcol].astype(str)):
        q = df[df[fcol].astype(str) == f]
        col, mk, filled = style_for(f)
        ax.plot(nums(q, tcol), q["chi2"], marker=mk, ls="--", color=col, mfc=col if filled else "white", lw=1.2, label=f)
    ax.set_xscale("log")
    ax.set_xlabel(tcol)
    ax.set_ylabel("χ$^2$ = (R$_{wp}$/R$_{exp}$)$^2$")
    ax.legend(loc="best")
    df["chi2"] = df["chi2"].round(4)
    res.tables["Refinement indices"] = df


def hydration_degree(book, t0_row=None):
    df = next(iter(book.data_sheets().values()))
    tcol = df.columns[0]
    t = nums(df, tcol)
    if t0_row is None:
        t0_row = book.num_opt("t0_row")
    if t0_row is None or not np.isfinite(t0_row):
        z = np.where(t == 0)[0]
        if not len(z):
            raise NeedInput("The table has no row with time 0. Which row is t0 (the content before hydration)?", "t0_row")
        i0 = int(z[0])
    else:
        i0 = int(t0_row)
    phases = [c for c in df.columns[1:] if is_num(df, c) and not sd_of(c)]
    out = {tcol: t}
    for c in phases:
        w = nums(df, c)
        out[f"α {base_name(c)} (%)"] = np.round((w[i0] - w) / w[i0] * 100, 2)
    return pd.DataFrame(out), i0, phases, tcol


def draw_c01(book, fig, res):
    tab, i0, phases, tcol = hydration_degree(book)
    res.tables["Hydration degree"] = tab
    res.notes.append(f"α(t) = (w(t0) - w(t)) / w(t0) × 100 [definition]; t0 = row {i0 + 1} of the data (time {tab[tcol].iloc[i0]:g})")
    rows = []
    for c in tab.columns[1:]:
        for x, v in zip(tab[tcol], tab[c]):
            if x > 0:
                rows.append((re.sub(r"^α\s*|\s*\(%\)$", "", c), "", x, v, np.nan))
    long = pd.DataFrame(rows, columns=["Panel", "Series", "X", "Value", "SD"])
    draw_long(book, fig, res, long=long, xname=tcol, y_title="Degree of hydration α (%)")


def atomic_ratios(book, ratios=None):
    df = next(iter(book.data_sheets().values()))
    tcol = df.columns[0]
    mol = {}
    used = []
    for c in df.columns[1:]:
        k = norm(base_name(c))
        if k in OXIDES and is_num(df, c):
            M, el, n = OXIDES[k]
            mol[el] = nums(df, c) / M * n
            used.append({"Oxide": base_name(c), "Molar mass (g/mol)": M, "Atoms per formula": n, "Element": el})
    want = ratios or [r.strip() for r in re.split(r"[,;]", str(book.opt("ratios", "Al/Ca, S/Al, Al/Si, Ca/Si"))) if "/" in r]
    out = {tcol: nums(df, tcol)}
    for r in want:
        a, b = [q.strip() for q in r.split("/", 1)]
        if a in mol and b in mol:
            out[f"{a}/{b}"] = np.round(mol[a] / mol[b], 4)
    return pd.DataFrame(out), pd.DataFrame(used), tcol


def draw_c02(book, fig, res):
    tab, used, tcol = atomic_ratios(book)
    res.tables["Atomic ratios"] = tab
    res.tables["Molar masses used"] = used
    res.notes.append("n(element) = m(oxide) / M(oxide) × atoms per formula (Al2O3 → 2 Al); ratios of the moles (molar masses in the results table)")
    rows = [(c, "", x, v, np.nan) for c in tab.columns[1:] for x, v in zip(tab[tcol], tab[c])]
    draw_long(book, fig, res, long=pd.DataFrame(rows, columns=["Panel", "Series", "X", "Value", "SD"]), xname=tcol, y_title="Atomic ratio (mol/mol)")


DRAWERS = {"G01": draw_g01, "G02": draw_g02, "G03": draw_g03, "G04": draw_g04, "G05": draw_g05, "G06": draw_g06, "G07": draw_g07, "G08": draw_g08,
           "G09": draw_g09, "G10": draw_g10, "G11": draw_g11, "G12": draw_g12, "G13": draw_g13, "G14": draw_g14, "G15": draw_g15, "G16": draw_g16,
           "G17": draw_g17, "G18": draw_g18, "G19": draw_g19, "G20": draw_g20, "G21": draw_g21, "G22": draw_g22, "G23": draw_g23, "G24": draw_g24,
           "C01": draw_c01, "C02": draw_c02}


# ------------------------------------------------------------------------------------------------ Origin: equivalent graphs for the app's Origin driver
def _rgb(h):
    h = h.lstrip("#")
    if len(h) != 6:
        return (0, 0, 0)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _segs(x, y, e, col):
    sx, sy = [], []
    for xi, yi, ei in zip(x, y, e):
        if np.isfinite(xi) and np.isfinite(yi) and np.isfinite(ei) and ei > 0:
            sx += [xi, xi, np.nan]
            sy += [yi - ei, yi + ei, np.nan]
    return (np.array(sx, float), np.array(sy, float), col) if sx else None


def origin_specs(tid, book):
    """Equivalent graphs for the Origin driver: (list of (name suffix, spec), one-line note of what Origin does not get)."""
    import smart_plots as sp
    C, P = sp.curve, sp.panel

    def mk(title, xname, panels, xlog=False, xrev=False, xcats=None):
        s = dict(title=title, xname=xname, panels=panels, xlog=xlog, xrev=xrev)
        if xcats is not None:
            s["xcats"] = list(zip(range(1, len(xcats) + 1), xcats))
        s = sp.finish(s)
        if xcats is not None:
            s["xlim"] = (0.4, len(xcats) + 0.6)
        for p_ in s["panels"]:
            if p_.get("ylog"):
                p_["ylim"] = p_.get("_ylog_lim") or p_["ylim"]
        return s

    def lab(labels, curves):
        """(position, text, peak height) for the driver; the height is the highest curve near the position."""
        out_ = []
        for t, pos, _g, _e in labels:
            hs = []
            for c in curves:
                w = np.abs(c["x"] - pos) < 0.15 * max(1.0, abs(float(np.nanmax(c["x"]) - np.nanmin(c["x"]))) / 35)
                if w.any():
                    hs.append(float(np.nanmax(c["y"][w])))
            if hs:
                out_.append((float(pos), chem(t).replace("$_{", "").replace("$^{", "").replace("}$", ""), max(hs)))
        return out_

    out, note = [], ""
    ds = book.data_sheets()
    if tid in ("G01", "G04"):
        for sh, df in ds.items():
            x = nums(df, df.columns[0])
            cols = [c for c in df.columns[1:] if is_num(df, c)]
            curves = [(x, nums(df, c)) for c in cols]
            offs = _stack_offsets(curves, 0.08 if tid == "G04" else 0.06)
            col = _rgb(style_for(sh)[0]) if tid == "G04" else (0, 0, 0)
            cv = [C(str(c), x, y + o, col) for c, (x, y), o in zip(cols, curves, offs)]
            p = P(str(book.opt("y_title", "Intensity (a.u.)")), cv, labels=lab([l for l in labels_of(book) if not l[2] or l[2] in cols or l[2] == sh], cv[-1:]), legend=False)
            p["yticks"] = False
            out.append((sh, mk(sh, _ppm_title(book, df.columns[0]).replace("$_{iso}$", "iso").replace("$^{", "").replace("}$", "") if tid == "G04" else str(book.opt("x_title", "2θ (°)")), [p], xrev=tid == "G04")))
        note = "the dashed highlight box, the zoom guide lines and the age names at the curve ends are in the publication files" if tid == "G01" else "fanned labels and age names are in the publication files"
    elif tid in ("G02", "G03", "G06"):
        df = next(iter(ds.values()))
        x = nums(df, df.columns[0])
        cmap = {norm(c): c for c in df.columns}
        if tid == "G03":
            obs, calc = nums(df, cmap["observed"]), nums(df, cmap["calculated"])
            diff = nums(df, cmap["difference"]) if "difference" in cmap else obs - calc
            off = book.num_opt("difference_offset") or (-0.06 * float(np.nanmax(obs)) - float(np.nanmax(diff)))
            cv = [C("Observed", x, obs, (31, 59, 255)), C("Calculated", x, calc, (224, 0, 0)), C("Difference", x, diff + off, (128, 128, 128))]
            p = P(str(book.opt("y_title", "Intensity (counts)")), cv)
        else:
            y = nums(df, [c for c in df.columns[1:] if is_num(df, c)][0])
            cv = [C("pattern", x, y, (0, 0, 0))]
            p = P(str(book.opt("y_title", "Intensity")), cv, labels=lab(labels_of(book), cv), legend=False)
            if tid == "G06":
                p["yticks"] = False
        a, b = book.num_opt("inset_from"), book.num_opt("inset_to")
        if a is not None and b is not None:
            p["inset"] = dict(xlim=(min(a, b), max(a, b)))
        out.append(("", mk(book.name, "δ iso (ppm)" if tid == "G06" else str(book.opt("x_title", "2θ (°)")), [p], xrev=tid == "G06")))
        note = "χ² text is in the publication files" if tid == "G03" else ""
    elif tid == "G05":
        for sh, df in ds.items():
            x = nums(df, df.columns[0])
            cv = [C(str(c), x, nums(df, c), (0, 0, 0) if norm(c) == "experimental" else _rgb(style_for(c)[0])) for c in df.columns[1:] if is_num(df, c)]
            p = P("Intensity (a.u.)", cv)
            p["yticks"] = False
            out.append((sh, mk(sh, "δ iso (ppm)", [p], xrev=True)))
        note = "the zoom column of the deconvolution grid is in the publication files"
    elif tid == "G07":
        df = next(iter(ds.values()))
        T = nums(df, df.columns[0])
        tg_c, dtg_c = [], []
        for name, tgc, dtgc in _tg_pairs(df):
            col = _rgb(style_for(name)[0])
            if tgc:
                tg_c.append(C(name, T, nums(df, tgc), col))
            if dtgc or tgc:
                dtg_c.append(C("DTG " + name, T, nums(df, dtgc) if dtgc else np.gradient(nums(df, tgc), T), col))
        p = P("TG (%)", tg_c)
        ys = np.concatenate([c["y"] for c in dtg_c])
        lo, hi = float(np.nanmin(ys)), float(np.nanmax(ys))
        p["y2"] = dict(curves=dtg_c, yname="DTG", ylim=(lo - 0.08 * (hi - lo), hi + 1.35 * (hi - lo)), labels=[])
        p["labels"] = []
        tys = np.concatenate([c["y"] for c in tg_c])
        a_, b_ = float(np.nanmin(tys)), float(np.nanmax(tys))
        p["ylim"] = (a_ - 1.25 * (b_ - a_), b_ + 0.08 * (b_ - a_))
        out.append(("", mk(book.name, "Temperature (°C)", [p])))
        note = "the phase arrows at the DTG minima and the range bars are in the publication files"
    elif tid in ("G08", "G09"):
        if tid == "G09":
            xr = book.sheet("xrd")
            x = nums(xr, xr.columns[0])
            cols = [c for c in xr.columns[1:] if is_num(xr, c)]
            offs = _stack_offsets([(x, nums(xr, c)) for c in cols])
            cvx = [C(str(c), x, nums(xr, c) + o, _rgb(style_for(c)[0])) for c, o in zip(cols, offs)]
            p = P("Intensity (a.u.)", cvx, labels=lab(labels_of(book, ("xrd labels",)), cvx[-1:]), legend=False)
            p["yticks"] = False
            out.append(("XRD", mk(book.name + " XRD", "2θ (°)", [p])))
        df = book.sheet("dtg") if tid == "G09" else next(iter(ds.values()))
        T = nums(df, df.columns[0])
        cols = [c for c in df.columns[1:] if is_num(df, c)]
        out.append(("DTG", mk(book.name + " DTG", "Temperature (°C)", [P("DTG", [C(str(c), T, nums(df, c), _rgb(style_for(c)[0])) for c in cols])])))
    elif tid == "G10":
        samples, info = calo_samples(book)
        col, _rc, _rg = _calo_style(samples, info)
        lab = lambda s_: (info.get(norm(s_["name"])) or {}).get("label", s_["name"])
        p1 = P("Heat flow (mW/g)", [C(lab(s_), s_["t"], s_["hf"], _rgb(col[s_["name"]])) for s_ in samples])
        peaks = []
        for s_ in samples:
            i0, _j = main_peak(s_["t"], s_["hf"])
            peaks.append(float(np.nanmax(s_["hf"][i0:])))
        p1["ylim"] = (0, 1.08 * max(peaks))
        tmax = max(float(np.nanmax(s_["t"])) for s_ in samples)
        xin = book.num_opt("inset_x_to_h") or (12.0 if tmax >= 48 else 1.0)
        t0 = float(min(s_["t"][0] for s_ in samples))
        p1["inset"] = dict(xlim=(t0, t0 + xin))
        p2 = P("Cumulative heat (J/g)", [C(lab(s_), s_["t"], _cum_of(s_, book.num_opt("exclusion_min", 0.0) or 0.0)[0], _rgb(col[s_["name"]])) for s_ in samples])
        out += [("heat flow", mk(book.name + " heat flow", "Time (h)", [p1])), ("cumulative", mk(book.name + " cumulative heat", "Time (h)", [p2]))]
        note = "regime labels and brackets, and the bar chart of Q, are in the publication files"
    elif tid == "G11":
        con, hfs = book.sheet("concentration"), book.sheet("heat flow")
        t = nums(con, con.columns[0])
        cv = [C(base_name(c), t, nums(con, c), _rgb(style_for(base_name(c))[0]), kind="linesymbol") for c in con.columns[1:] if is_num(con, c)]
        p = P("Concentration (mmol/L)", cv)
        ys = np.concatenate([c["y"] for c in cv])
        ys = ys[ys > 0]
        p["ylog"] = True
        p["_ylog_lim"] = (10 ** math.floor(math.log10(ys.min())), 10 ** math.ceil(math.log10(ys.max())))
        hc = [c for c in hfs.columns[1:] if is_num(hfs, c)][0]
        yv = nums(hfs, hc)
        p["y2"] = dict(curves=[C("heat flow", nums(hfs, hfs.columns[0]), yv, (0, 0, 0))], yname=base_name(hc) + (f" ({unit(hc)})" if unit(hc) else ""), ylim=(0, float(np.nanmax(yv)) * 1.1), labels=[])
        out.append(("", mk(book.name, con.columns[0], [p])))
        note = "the heat flow is a solid line in Origin (dashed in the publication files)"
    elif tid in ("G12", "G16", "G24"):
        for sh, df in ds.items():
            if tid == "G24":
                d2 = df.copy()
                cm = {norm(c): c for c in df.columns}
                fcol = next((c for c in df.columns if not is_num(df, c)), df.columns[0])
                tcol = next(c for c in df.columns if _kind_of_x(c) == "time")
                chi = nums(df, cm["chi2"]) if "chi2" in cm else (nums(df, cm["rwp"]) / nums(df, cm["rexp"])) ** 2
                cv = []
                for f in dict.fromkeys(df[fcol].astype(str)):
                    m = (df[fcol].astype(str) == f).to_numpy()
                    cv.append(C(f, nums(d2, tcol)[m], chi[m], _rgb(style_for(f)[0]), kind="linesymbol"))
                out.append((sh, mk(sh, tcol, [P("chi2 = (Rwp/Rexp)^2", cv)], xlog=True)))
                continue
            x = nums(df, df.columns[0])
            keep = x > 0 if tid == "G12" else np.isfinite(x)
            cv, segs = [], []
            for vc, sc in value_sd_pairs(df, df.columns[0]):
                col = _rgb(style_for(base_name(vc))[0])
                y = nums(df, vc)
                cv.append(C(base_name(vc), x[keep], y[keep], col, kind="linesymbol"))
                if sc:
                    s_ = _segs(x[keep], y[keep], nums(df, sc)[keep], col)
                    if s_:
                        segs.append(s_)
            p = P(str(book.opt("y_title", "Phase content")), cv)
            p["segs"] = segs
            out.append((sh, mk(sh, df.columns[0], [p], xlog=tid == "G12")))
        if tid == "G12":
            note = "Origin gets a log time axis without the t = 0 point; the split linear | log axis with // marks is in the publication files"
    elif tid in ("G13", "G14", "G15", "C01", "C02"):
        if tid == "C01":
            tab, i0, _ph, tc = hydration_degree(book)
            long = pd.DataFrame([(re.sub(r"^α\s*|\s*\(%\)$", "", c), "", a, b, np.nan) for c in tab.columns[1:] for a, b in zip(tab[tc], tab[c]) if a > 0], columns=["Panel", "Series", "X", "Value", "SD"])
            xname, yt = tc, "Degree of hydration (%)"
        elif tid == "C02":
            tab, _u, tc = atomic_ratios(book)
            long = pd.DataFrame([(c, "", a, b, np.nan) for c in tab.columns[1:] for a, b in zip(tab[tc], tab[c])], columns=["Panel", "Series", "X", "Value", "SD"])
            xname, yt = tc, "Atomic ratio (mol/mol)"
        else:
            long, xname, _w = to_long(book)
            yt = str(book.opt("y_title", "Value"))
        refs = book.sheet("reference") if tid == "G15" else None
        xlog = book.yes("x_log", True)
        for pn in dict.fromkeys(long["Panel"]):
            q = long[long.Panel == pn]
            cv, segs = [], []
            for s in dict.fromkeys(q["Series"]):
                r = q[q.Series == s]
                r = r[r.X > 0] if xlog else r
                col = _rgb(style_for(s or pn, tid == "G14")[0])
                cv.append(C(s or pn, r.X.to_numpy(), r.Value.to_numpy(), col, kind="linesymbol"))
                s_ = _segs(r.X.to_numpy(), r.Value.to_numpy(), r.SD.to_numpy(), col)
                if s_:
                    segs.append(s_)
            if refs is not None:
                xs_ = q.X[q.X > 0] if xlog else q.X
                for _, rf in refs[refs.iloc[:, 0].astype(str) == str(pn)].iterrows():
                    cv.append(C(str(rf.iloc[1]), np.array([xs_.min(), xs_.max()], float), np.array([float(rf.iloc[2])] * 2), (115, 115, 115)))
            p = P(yt, cv)
            p["segs"] = segs
            out.append((str(pn), mk(str(pn), xname or "Time (days)", [p], xlog=xlog)))
        note = "one Origin graph per panel (merge them with Graph > Merge Graph Windows); the shared legend" + (", the annotations" if tid == "G15" else "") + (" and the split axes" if book.yes("split_axis") else "") + " are in the publication files"
    elif tid in ("G18", "G19"):
        df = next(iter(ds.values()))
        cat = df.columns[0]
        xi = np.arange(1, len(df) + 1, dtype=float)
        cv, segs = [], []
        vals = value_sd_pairs(df, cat)
        line = None
        if tid == "G19":
            line = next((c for c, _ in vals if re.search(r"stoich|calculat|model", c.lower())), vals[-1][0])
        for vc, sc in vals:
            if vc == line:
                continue
            col = _rgb(style_for(vc)[0])
            cv.append(C(vc, xi, nums(df, vc), col, kind="bar"))
        if line:
            cv.append(C(line, xi, nums(df, line), _rgb(style_for(line, True)[0]), kind="linesymbol"))
        p = P(str(book.opt("y_title", "Value")), cv)
        out.append(("", mk(book.name, cat, [p], xcats=list(df[cat].astype(str)))))
        note = "error bars and hatch fills of the bars are in the publication files"
    elif tid == "G20":
        for sh, df in ds.items():
            x = nums(df, df.columns[0])
            cv = [C(re.sub(r"\s*cumulative.*$", "", base_name(c), flags=re.I), x, nums(df, c), _rgb(style_for(re.sub(r"\s*cumulative.*$", "", base_name(c), flags=re.I))[0])) for c in df.columns[1:] if is_num(df, c)]
            out.append((sh, mk(sh, df.columns[0], [P(str(book.opt("y_title", "Cumulative volume (%)")), cv)], xlog=True)))
    elif tid == "G21":
        df = next(iter(ds.values()))
        x = nums(df, df.columns[0])
        cols = [c for c in df.columns[1:] if is_num(df, c)]
        tops = np.cumsum([np.nan_to_num(nums(df, c)) for c in cols], axis=0)
        cv = [C(base_name(c), x, tops[k], _rgb(phase_colour(base_name(c), k)), kind="area") for k, c in reversed(list(enumerate(cols)))]
        p = P(str(book.opt("y_title", "g/100 g paste")), cv)
        p["ylim"] = (0, max(100.0, float(np.nanmax(tops))))
        out.append(("", mk(book.name, df.columns[0], [p], xlog=book.yes("x_log", x.min() > 0 and x.max() / max(x.min(), 1e-12) > 50))))
        note = "names inside the areas and the hatching are in the publication files"
    elif tid in ("G22", "G23"):
        note = "ternary diagrams are drawn in the publication files only; the app's Origin driver has no ternary layer (in Origin: Plot > Specialized > Ternary with the three composition columns)"
    elif tid == "G17":
        df = next(iter(ds.values()))
        numc = [c for c in df.columns if is_num(df, c) and norm(c) != "label"]
        xc = next((c for c in numc if norm(c) == norm(book.opt("x", ""))), numc[0])
        yc = next((c for c in numc if norm(c) == norm(book.opt("y", ""))), [c for c in numc if c != xc][0])
        x, y = nums(df, xc), nums(df, yc)
        cv = [C("points", x, y, (31, 59, 255), kind="scatter")]
        if str(book.opt("fit", "none")).lower().startswith("linear"):
            ok = np.isfinite(x) & np.isfinite(y)
            pf = np.polyfit(x[ok], y[ok], 1)
            xx = np.linspace(np.nanmin(x), np.nanmax(x), 20)
            cv.append(C("linear fit", xx, np.polyval(pf, xx), (230, 159, 0)))
        out.append(("", mk(book.name, xc, [P(yc, cv, legend=False)])))
        note = "point labels and the fit equation are in the publication files"
    return out, note


# ------------------------------------------------------------------------------------------------ templates
OPTION_DEFAULTS = {
    "G01": {"x_title": "2θ (°) CuKα", "y_title": "Intensity (a.u.)", "offset": "auto", "order": "oldest on top", "highlight_from": "", "highlight_to": "", "zoom_from": "", "zoom_to": "", "guide_lines": "no", "y_numbers": "hide"},
    "G02": {"inset_from": "", "inset_to": "", "label_orientation": "vertical", "arrows": "yes"},
    "G03": {"inset_from": "", "inset_to": "", "difference_offset": "auto", "Rwp": "", "Rexp": ""},
    "G04": {"nucleus": "", "x_reversed": "yes", "x_from": "", "x_to": "", "guide_lines": "yes"},
    "G05": {"x_reversed": "yes", "full_from": "", "full_to": "", "zoom_from": "", "zoom_to": ""},
    "G06": {"x_reversed": "yes"},
    "G07": {"layout": "ONE graph, TG left axis, DTG right axis", "dtg_sign": "natural (not inverted)", "dtg_from_tg": "compute dTG/dT if DTG columns are missing"},
    "G08": {"mode": "overlay", "x_to": ""},
    "G09": {"layout": "(a) XRD stack | (b) DTG overlay", "dtg_x_to": ""},
    "G10": {"inset_x_to_h": "", "bar_at_h": "", "exclusion_min": 0},
    "G11": {"left_axis": "log, symbols + line", "right_axis": "linear, dashed line"},
    "G12": {"y_title": "", "y_break_right": "", "connect": "dashed", "split_linear_to": 0.04, "split_log_from": 0.06},
    "G13": {"y_title": "", "columns": 2, "x_log": "yes", "same_y_range": "no", "split_axis": "no"},
    "G14": {"y_title": "", "columns": 2, "x_log": "yes"},
    "G15": {"y_title": "", "columns": 3, "x_log": "yes"},
    "G16": {"x_title": "", "x_title_arrow": "no", "y_title": "", "connect": "dashed"},
    "G17": {"x": "", "y": "", "fit": "none", "show_equation": "yes"},
    "G18": {"y_title": "", "fill": "solid colours"},
    "G19": {"bars": "", "line": "", "y_title": ""},
    "G20": {"y_title": "Cumulative volume (%)", "d_values": "no"},
    "G21": {"x_log": "", "y_max": 100, "y_title": "g/100 g paste"},
    "G22": {"corners": "", "normalise": "yes"},
    "G23": {"colour_map": "viridis", "levels": 20},
    "G24": {},
    "C01": {"t0_row": ""},
    "C02": {"ratios": "Al/Ca, S/Al, Al/Si, Ca/Si"},
}
INSTRUCTIONS = {
    "G01": ["Data: first column 2θ, then one intensity column per age or sample (column name = curve label).", "Labels: Label | Position (°2θ) | Pattern (blank = top pattern). Only these labels are drawn.", "Options: highlight_from/to (dashed box), zoom_from/to (window with guide lines)."],
    "G02": ["Data: 2θ and one intensity column. Labels: Label | Position (°2θ). Options: inset_from/to."],
    "G03": ["Data: 2θ, Observed, Calculated, optional Difference (computed if missing). Options: inset_from/to, Rwp, Rexp (χ² = (Rwp/Rexp)² is written)."],
    "G04": ["One sheet per sample: δ (ppm) then one column per age. Labels: Label | Position (ppm) | Sample (blank = all). ppm axis high → low."],
    "G05": ["One sheet per age: δ, Experimental, one column per component, optional 'Sum of fit' (sum of the components if missing). Component names are your column names."],
    "G06": ["Data: δ and Intensity. Labels: Label | Position (ppm) | Write position value (yes/no) | Colour."],
    "G07": ["Data: Temperature (°C), then 'TG <name> (%)' and 'DTG <name> (%/min)' pairs (DTG computed if missing).", "Labels: Label | Temperature (°C). Ranges: Label | From (°C) | To (°C). TG and DTG in ONE graph, DTG with its natural sign."],
    "G08": ["Data: Temperature (°C) and one DTG column per curve. Options: mode (overlay or offset), x_to."],
    "G09": ["Sheets XRD (G01 layout) and DTG (G08 layout), 'XRD labels' and 'DTG labels'. Sample names must match in both sheets."],
    "G10": ["Data: Time (h), 'Heat flow <name> (mW/g)' columns, optional 'Cumulative heat <name> (J/g)' (integrated if missing: mW/g × h × 3.6 = J/g). Or one sheet per sample.",
            "Samples (optional): Sample | Label | Regime | Alite fraction | Colour. Regimes are drawn only from this sheet (labels at the peaks, brackets);",
            "with an alite fraction the bar chart gives Q per unit alite. Options: inset_x_to_h (12 for long runs), bar_at_h (e.g. 168)."],
    "G11": ["Sheets 'Concentrations' (Time + ion columns, log axis) and 'Heat flow' (Time + one column, right axis)."],
    "G12": ["Sheets 'Anhydrous' and 'Hydrates': Time (days) with a t = 0 row, '<phase> (g/100 g paste)' and '<phase> SD' columns.", "Time axis split: linear segment for t = 0, // break, log axis."],
    "G13": ["LONG layout: Panel | Series | Time (days) | Value | SD. One small graph per Panel, one curve per Series, one shared legend."],
    "G14": ["LONG layout as G13 with Panel = mix and Series = method (QXRD, TGA, stoichiometric calculation, NMR): fixed styles per method."],
    "G15": ["LONG layout as G13. 'Reference lines': Panel | Label | Value. 'Annotations': Panel | X | Y | Text."],
    "G16": ["Data: x variable (w/b ratio, mole %) then value columns with optional '<name> SD' columns."],
    "G17": ["Data: Label, X, Y. Options: fit (none or linear), show_equation."],
    "G18": ["Data: categories (text) then value columns with optional '<name> SD'. Options: fill (solid colours or hatch)."],
    "G19": ["Data: categories, bar columns and one line column. Options: bars, line. Difference = NMR - QXRD computed if missing."],
    "G20": ["One sheet per material group: size (µm) then one cumulative % column per material."],
    "G21": ["Data: x (time or ratio) then one column per phase in stacking order (first = bottom). Fixed colour per phase name."],
    "G22": ["Data: Label + three composition columns (their names become the corner labels). Rows not adding up to 100 are normalised (warned)."],
    "G23": ["Data: three composition columns then one column per quantity (one contour panel each)."],
    "G24": ["Data: Formulation | Time (days) | Rwp | Rexp. χ² = (Rwp/Rexp)² computed and plotted vs time."],
    "C01": ["Data: Time (days) with a t = 0 row, then phase contents. α(t) = (w(t0) - w(t)) / w(t0) × 100 (definition)."],
    "C02": ["Data: Time (days) then oxide contents (CaO, Al2O3, SiO2, SO3 ...). n = m / M × atoms per formula; ratios of the moles."],
}
ANHYDROUS = re.compile(r"(?i)^(c3s|c2s|c3a|c4af|ca|ca2|c12a7|c2as|cs|alite|belite|ferrite|aluminate|anhydrite|gypsum|bassanite|hemihydrate|quartz|calcite|periclase|free lime|lime|mayenite|gehlenite|ye.?elimite|c4a3s|limestone|slag|fly ash)\b")


def _raw_tables(path):
    """The tables of any file the app reads (instrument files too), as {name: DataFrame with header}."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls", ".csv", ".txt"):
        try:
            b = read_book(path)
            if b.data_sheets():
                return b.data_sheets(), b
        except Exception:          # noqa: BLE001
            pass
    import smart_plots as sp
    out = {}
    for name, raw in sp.read_tables(path):
        p = sp.parse_table(raw)
        if p:
            out[str(name)] = p[0]
    return out, None


def _tam(path):
    """The calorimetry reader's view of a TAM-like workbook, or None."""
    if not str(path).lower().endswith((".xlsx", ".xlsm")):
        return None
    try:
        import calorimetry
        d = calorimetry.read(path)
        return d if d.get("rows") else None
    except Exception:          # noqa: BLE001
        return None


def make_template(tid, src, out_path, mass_g=None):
    """Write the template of type tid from a raw file (or from a template): Instructions, data sheet(s), Labels/Options in the
    documented layout. Returns (path, notes). Raises NeedInput when an answer is missing (sample mass for a W heat flow)."""
    tabs, book = _raw_tables(src)
    if not tabs:
        raise GalleryError(f"{os.path.basename(src)}: no table found to put into the template")
    notes = []
    first_name, first = next(iter(tabs.items()))
    sheets = {}
    keep_extra = {}
    if book is not None:                                  # a template or workbook already in a layout: keep its helper sheets
        for k, v in book.sheets.items():
            if k.lower().startswith(("labels", "xrd labels", "dtg labels", "ranges", "reference", "annotations", "regions", "samples")):
                keep_extra[k] = v
    if tid == "G07":
        T = next((c for c in first.columns if _kind_of_x(c) == "temperature"), first.columns[0])
        df = pd.DataFrame({"Temperature (°C)": nums(first, T)})
        first = first[[T] + [c for c in first.columns if c != T and _kind_of_x(c) != "time"]]
        pairs = _tg_pairs(first)
        if pairs:
            for nm, tgc, dtgc in pairs:
                if tgc:
                    df[f"TG {nm} (%)"] = nums(first, tgc)
                if dtgc:
                    df[f"DTG {nm} ({unit(dtgc) or '%/min'})"] = nums(first, dtgc)
        else:
            for c in [c for c in first.columns[1:] if is_num(first, c)]:
                v = nums(first, c)
                cl = str(c).lower()
                if re.search(r"dtg|dm/dt|deriv|%/min|%/°c", cl):
                    df[f"DTG {os.path.splitext(os.path.basename(src))[0]} ({unit(c) or '%/min'})"] = v
                else:
                    if not re.search(r"%", cl) and np.nanmax(v) > 0:
                        v = v / v[np.isfinite(v)][0] * 100
                        notes.append(f"'{c}' converted to % of the first point")
                    df[f"TG {os.path.splitext(os.path.basename(src))[0]} (%)"] = v
        sheets["Data"] = df
    elif tid == "G10" and _tam(src):
        cal = _tam(src)                                    # a TAM export: columns found by their headers and the units row (calorimetry.py)
        rows = np.array([(r[1], r[2]) for r in cal["rows"]], float)
        tu, hu = cal["units"]["time"].lower(), cal["units"]["heat"].lower().replace(" ", "")
        tv = rows[:, 0] / {"s": 3600.0, "min": 60.0, "h": 1.0}.get(tu, 3600.0)
        tv = tv - tv[0]
        v = rows[:, 1]
        if hu in ("w", "mw"):
            if not mass_g or mass_g <= 0:
                raise NeedInput(f"the heat flow of {os.path.basename(src)} is in {cal['units']['heat']}: the sample mass (g) is needed to give mW/g.", "mass_g")
            v = v * (1000.0 if hu == "w" else 1.0) / float(mass_g)
            notes.append(f"heat flow normalised: {cal['units']['heat']} → mW/g with sample mass {mass_g:g} g (heat × {'1000 / ' if hu == 'w' else '1 / '}mass)")
        elif hu == "w/g":
            v = v * 1000.0
        notes.append(f"TAM export read by its headers: time column {cal['columns']['time']} ({cal['units']['time']}), heat flow column {cal['columns']['heat']} ({cal['units']['heat']}); time set to 0 at the first row")
        df = pd.DataFrame({"Time (h)": tv, f"Heat flow {os.path.splitext(os.path.basename(src))[0]} (mW/g)": v})
        sheets["Data"] = df
    elif tid == "G10":
        t = first.columns[0]
        tv = nums(first, t)
        if re.search(r"\(s\)|sec", str(t).lower()):
            tv = (tv - tv[np.isfinite(tv)][0]) / 3600.0
            notes.append("time converted from s to h")
        elif re.search(r"\(min\)|min\b", str(t).lower()):
            tv = tv / 60.0
            notes.append("time converted from min to h")
        df = pd.DataFrame({"Time (h)": tv})
        name = os.path.splitext(os.path.basename(src))[0]
        for c in [c for c in first.columns[1:] if is_num(first, c)]:
            u = (unit(c) or "").lower().replace(" ", "")
            if "cumulative" in str(c).lower() or u in ("j/g",):
                cn = base_name(re.sub(r"(?i)cumulative\s*(heat)?(\s*flow)?", "", str(c))).strip(" -_:") or name
                df[f"Cumulative heat {cn} (J/g)"] = nums(first, c)
                continue
            if "heat" not in str(c).lower() and u not in ("mw/g", "w/g", "w", "mw"):
                continue
            v = nums(first, c)
            if u in ("mw/g", ""):
                pass
            elif u == "w/g":
                v = v * 1000
            elif u in ("w", "mw"):
                if not mass_g or mass_g <= 0:
                    raise NeedInput(f"'{c}' is in {unit(c)}: the sample mass (g) is needed to give mW/g.", "mass_g")
                v = v * (1000 if u == "w" else 1) / float(mass_g)
                notes.append(f"heat flow normalised: {unit(c)} → mW/g with sample mass {mass_g:g} g")
            df[f"Heat flow {hf_name(c, name)} (mW/g)"] = v
        if not hf_columns(sheets.get("Data", df)):
            raise GalleryError("no heat flow column found (a column named 'heat flow' in mW/g, W/g, W or mW)")
        sheets.setdefault("Data", df)
    elif tid in ("G12", "G13", "G14", "G15"):
        long_in = {"panel", "series", "value"} <= {norm(c) for c in first.columns}
        if tid == "G12" and not long_in and len(tabs) > 1:
            sheets.update(tabs)                                # already one sheet per group (Anhydrous | Hydrates)
        elif tid == "G12" and not long_in:
            t = first.columns[0]
            pairs = value_sd_pairs(first, t)
            groups = {"Anhydrous": [], "Hydrates": []}
            for vc, sc in pairs:
                groups["Anhydrous" if ANHYDROUS.match(base_name(vc)) else "Hydrates"].append((vc, sc))
            for gname, cols in groups.items():
                if cols:
                    d = {"Time (days)": nums(first, t)}
                    for vc, sc in cols:
                        d[vc if unit(vc) else f"{vc} (g/100 g paste)"] = nums(first, vc)
                        if sc:
                            d[f"{base_name(vc)} SD"] = nums(first, sc)
                    sheets[gname] = pd.DataFrame(d)
            notes.append("phases sorted into Anhydrous and Hydrates by their names (check the two sheets)")
        elif long_in:
            sheets["Data"] = first
        else:
            series_name = os.path.splitext(os.path.basename(src))[0]
            bk = book or book_from_frames(tabs, series_name)
            long, xname, _w = to_long(bk)
            if (long["Series"] == "").all():
                long["Series"] = series_name
            sheets["Data"] = long.rename(columns={"X": xname if _kind_of_x(xname) == "time" else "Time (days)"})
            notes.append("wide table turned into the LONG layout Panel | Series | Time | Value | SD")
    else:
        for k, v in tabs.items():
            sheets[k if len(tabs) > 1 else "Data"] = v
    if tid == "G01" and book is None:
        notes.append("each intensity column is one pattern; type the peak labels into the Labels sheet")
    sheets.update(keep_extra)
    if tid == "G10" and not any(k.lower().startswith("samples") for k in sheets):
        names = [hf_name(c, os.path.splitext(os.path.basename(src))[0]) for c in hf_columns(sheets.get("Data", pd.DataFrame()))] if "Data" in sheets else []
        sheets["Samples"] = pd.DataFrame({"Sample": names, "Label": names, "Regime": [""] * len(names), "Alite fraction": [""] * len(names), "Colour": [""] * len(names)})
    if tid in ("G01", "G02", "G04", "G06", "G07", "G08") and not any(k.lower().startswith("labels") for k in sheets):
        sheets["Labels"] = pd.DataFrame(columns=["Label", "Position (ppm)" if tid in ("G04", "G06") else "Temperature (°C)" if tid in ("G07", "G08") else "Position (°2θ)"] + (["Write position value", "Colour"] if tid == "G06" else []))
    opts = dict(OPTION_DEFAULTS.get(tid, {}))
    if book is not None:
        opts.update({k: v for k, v in book.options.items()})
    ins = [f"{tid} {TYPES[tid][0]} - {TYPES[tid][1]}."] + INSTRUCTIONS.get(tid, []) + [f"Made by Origin Plot Studio from {os.path.basename(src)}. Labels are only what you type; nothing is guessed."]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        pd.DataFrame({"Instructions": ins}).to_excel(w, sheet_name="Instructions", index=False)
        for k, df in sheets.items():
            df.to_excel(w, sheet_name=str(k)[:31], index=False)
        pd.DataFrame({"Key": list(opts.keys()), "Value": [("" if v is None else v) for v in opts.values()]}).to_excel(w, sheet_name="Options", index=False)
        for ws in w.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(12, min(60, max(len(str(c.value or "")) for c in col[:200]) + 2))
    return out_path, notes

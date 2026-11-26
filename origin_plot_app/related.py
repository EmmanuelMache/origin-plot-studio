"""Files that belong together, and what the app works out for a file by itself.

    series(names)                 do these file names follow one pattern (the same words, a number or code that changes)?
    side_by_side(inputs)          the data of several files next to each other in one table, every file with its own x
    dtg_column(table)             the DTG curve of a thermogravimetric table, as a column
    peak_table(kind, table)       the peaks of a DTG curve or the bands of an FTIR spectrum, each with what it may be

Nothing here names a phase or a bond with certainty: the names are the usual ones for where the peak lies, they are
written as possibilities, and the label you type yourself is the one that is drawn."""
import os, re
import numpy as np
import pandas as pd

SPLIT = re.compile(r"[\s_\-.,;()\[\]]+")


def stem(name):
    return os.path.splitext(os.path.basename(str(name)))[0]


def _shape(tok):
    """A token as a pattern: letters -> a, digits -> 9 (runs collapsed), so 'rep1' and 'rep12' are the same kind of word."""
    return re.sub(r"9+", "9", re.sub(r"a+", "a", re.sub(r"[0-9]", "9", re.sub(r"[^\W\d_]", "a", tok))))


def series(names):
    """Do these names follow one pattern? Returns {"related", "shared", "varies", "why"}.

    They do when every name is built the same way (the same number of parts, each part the same kind of word) and at
    least one part is the same in all of them while another changes - '10-900-AB-Mix', '20-950-AB-Mix' - or when the
    names are one word with a changing number ('S1', 'S2', 'S3'), or share a long beginning or ending."""
    stems = [stem(n) for n in names]; out = {"related": False, "shared": "", "varies": [], "why": ""}
    if len(stems) < 2 or len(set(stems)) < 2: return out
    toks = [[t for t in SPLIT.split(s) if t] for s in stems]
    if all(toks) and len({len(t) for t in toks}) == 2:
        # 'A-40-X' and 'A-40-X-2': the second is a repeat of the same kind of sample. A last part of one or two digits that
        # only the longer names have is counted with the part before it, so the names are built the same way again.
        short = min(len(t) for t in toks)
        if all(len(t) == short or (len(t) == short + 1 and re.fullmatch(r"\d{1,2}", t[-1])) for t in toks):
            toks = [t if len(t) == short else t[:-2] + [t[-2] + "-" + t[-1]] for t in toks]
            if len({t[-1].lower().split("-")[0] for t in toks}) == 1:      # the part before the repeat number is the shared one: compare without the number
                toks = [t[:-1] + [t[-1].split("-")[0]] for t in toks]; stems_rep = True
    if all(toks) and len({len(t) for t in toks}) == 1:
        n = len(toks[0]); same = [k for k in range(n) if len({t[k].lower() for t in toks}) == 1]; shapes_ok = all(len({_shape(t[k]) for t in toks}) == 1 for k in range(n))
        moving = [k for k in range(n) if k not in same]
        if moving and shapes_ok and (same or all(re.search(r"\d", t[k]) for t in toks for k in moving)):
            words = [k for k in same if re.search(r"[^\W\d_]", toks[0][k])]
            if words or (not same and n == 1) or len(same) >= 1:
                out.update(related=True, shared=" ".join(toks[0][k] for k in same), varies=["-".join(t[k] for k in moving) for t in toks])
                if locals().get("stems_rep"): out["varies"] = [v + ("" if len(SPLIT.split(s_)) == len(toks[0]) else " (repeat " + SPLIT.split(s_)[-1] + ")") for v, s_ in zip(out["varies"], [x for x in stems])]
                out["why"] = (f"the names share '{out['shared']}' and differ in " if out["shared"] else "the names differ only in ") + ", ".join(out["varies"][:4]) + (" …" if len(stems) > 4 else "")
                return out
    low = [s.lower() for s in stems]; pre = os.path.commonprefix(low); suf = os.path.commonprefix([s[::-1] for s in low])[::-1]
    for part in (pre, suf):
        if len(re.sub(r"[\W\d_]", "", part)) >= 4:                       # at least four letters in common at one end
            cut = (lambda s: s[len(part):]) if part is pre else (lambda s: s[:len(s) - len(part)])
            out.update(related=True, shared=stems[0][:len(part)] if part is pre else stems[0][len(stems[0]) - len(part):], varies=[cut(s).strip(" _-.") or s for s in stems])
            out["why"] = f"the names share '{out['shared'].strip(' _-.')}'"; return out
    return out


def groups(names):
    """The names sorted into sets that each follow one pattern (two or more names per set), the largest first found.
    A file a merge of the app made (kept in a 'derived' folder) belongs to none: it is made of the others."""
    left = [n for n in names if "derived" not in re.split(r"[\\/]", str(n))[:-1]]; out = []
    while len(left) >= 2:
        if series(left)["related"]: out.append(list(left)); break
        best = []
        for seed in left:
            g = [n for n in left if n == seed or series([seed, n])["related"]]
            if len(g) > len(best) and len(g) >= 2 and series(g)["related"]: best = g
        if not best: break
        out.append(best); left = [n for n in left if n not in best]
    return out


def series_label(names):
    """A short name for the set: what the names share, else the first and the last."""
    s = series(names)
    if s["related"] and s["shared"].strip(" _-."): return s["shared"].strip(" _-.")
    st = [stem(n) for n in names]
    return f"{st[0]} to {st[-1]}" if len(st) > 1 else (st[0] if st else "data")


def dtg_column(table, window_C=15.0):
    """(name, values) of the DTG curve of a table with a mass and a temperature column, or None.

    DTG = dm/dT in % per °C, smoothed over 15 °C (opstudio.tga_core.dtg - the calculation of the TGA page), on the
    file's own temperature points. A file that already has a DTG / derivative column keeps its own."""
    from opstudio.detection import normalise
    cols = list(table.numeric); names = {c: normalise(c) for c in cols}
    find = lambda *keys: next((c for c in cols if any(k in names[c] for k in keys)), None)
    if find("dtg", "derivative", "dmdt", "dmdtemp", "deriv"): return None
    mass = find("mass", "weight", "tgpercent"); temp = find("temperature", "temp", "celsius", "degc")
    if not mass or not temp: return None
    T = table.arr(temp); m = table.arr(mass); ok = np.isfinite(T) & np.isfinite(m)
    if ok.sum() < 20: return None
    from opstudio import tga_core
    Tg = T[ok]; mg = m[ok]; order = np.argsort(Tg, kind="stable"); Ts = Tg[order]; ms = mg[order]
    keep = np.concatenate([[True], np.diff(Ts) > 0])                      # one value per temperature (the derivative needs rising T)
    if keep.sum() < 20: return None
    grid = np.linspace(Ts[keep][0], Ts[keep][-1], int(min(max(keep.sum(), 200), 6000)))
    d = tga_core.dtg(grid, np.interp(grid, Ts[keep], ms[keep]), window_C=window_C)["dtg_per_C"]
    out = np.full(len(T), np.nan); out[ok] = np.interp(Tg, grid, d)
    unit = "%" if "%" in mass or "pct" in names[mass] or "percent" in names[mass] else re.sub(r".*\((.*?)\).*", r"\1", mass) if "(" in mass else "mass unit"
    return f"DTG ({unit}/°C)", out, {"mass": mass, "temperature": temp, "window_C": window_C}


def side_by_side(inputs, extra=None):
    """One table with the columns of every file next to each other: for each file its x column and its y columns, named
    'column [file]'. Every file keeps its own x values - nothing is interpolated - and shorter files end in empty cells.
    inputs: [(path, table)]; extra(path, table) -> [(name, values)] adds worked-out columns (the DTG curve)."""
    if len(inputs) < 2: raise ValueError("Select at least two datasets")
    cols = {}; n = 0
    for path, table in inputs:
        if table.x is None or not table.ys: raise ValueError(f"{os.path.basename(path)}: needs an X column and at least one Y column")
        tag = stem(path); own = [(table.x, table.arr(table.x))] + [(c, table.arr(c)) for c in table.ys] + list(extra(path, table) if extra else [])
        for name, values in own:
            key = f"{name} [{tag}]"; k = 2
            while key in cols: key = f"{name} [{tag}] ({k})"; k += 1
            v = np.asarray(values); cols[key] = v.astype(object) if v.dtype.kind in "OUS" else v.astype(float); n = max(n, len(v))      # a column of words (the names of the peaks) stays words
    pad = lambda v: np.concatenate([v, np.full(n - len(v), "" if v.dtype == object else np.nan, dtype=v.dtype)])
    return pd.DataFrame({k: pad(v) for k, v in cols.items()})


# ----------------------------------------------------------------------------------------------- peaks and what they may be
TGA_SHORT = {"Free / adsorbed water": "H₂O (free)", "C-S-H + ettringite (AFt) dehydration": "C-S-H / AFt", "Gypsum -> hemihydrate/anhydrite": "Gypsum",
             "AFm phases (monosulfate, hemi/monocarbonate)": "AFm", "Hydrotalcite / brucite": "Ht / brucite", "Portlandite Ca(OH)2 dehydroxylation": "Ca(OH)₂",
             "Kaolinite dehydroxylation": "Kaolinite", "Weakly bound / amorphous carbonates": "Carbonates (weak)", "Calcite decarbonation": "CaCO₃",
             "Dolomite decarbonation (two steps)": "Dolomite", "Mica (muscovite/illite) dehydroxylation": "Mica"}
TOLERANCE = {"TGA": 15.0, "FTIR": 8.0}        # how far a name may lie from a peak of the graph and still be its name (°C, cm-1)
PEAKS_SHEET = "Peaks \u2014 found by the app"


TGA_COMMON = ("Free / adsorbed water", "C-S-H + ettringite (AFt) dehydration", "Portlandite Ca(OH)2 dehydroxylation", "Calcite decarbonation")


def tga_candidates(T_peak):
    """Usual thermal events at this temperature (°C): [(name, short label)]. The four that nearly every cement paste and
    raw meal shows (water, C-S-H / ettringite, portlandite, calcite) come first, then the others; within each, the one
    whose range the temperature lies most centrally in. A step at 770 °C is thus offered as calcite before dolomite."""
    from opstudio import tga_core
    c = [e for e in tga_core.REFERENCE_EVENTS if e["gas"] and e["T"][0] <= T_peak <= e["T"][1]]
    c.sort(key=lambda e: (e["name"] not in TGA_COMMON, abs(T_peak - (e["T"][0] + e["T"][1]) / 2.0) / ((e["T"][1] - e["T"][0]) / 2.0)))
    return [(e["name"], TGA_SHORT.get(e["name"], e["name"])) for e in c]


def ftir_candidates(position):
    from opstudio import ftir_core
    return [(b["name"], b["short"]) for b in ftir_core.suggest(position)]


def candidates(kind, position):
    return tga_candidates(position) if kind == "TGA" else ftir_candidates(position) if kind == "FTIR" else []


def peak_kind(table):
    """'TGA' or 'FTIR' when the app can look for peaks in this table and say what they may be, else None."""
    from opstudio.detection import detect
    try: d = detect(table, getattr(table, "measurement_type", None))
    except Exception: return None
    if d.needs_confirmation or d.kind not in ("TGA", "FTIR"): return None
    if d.kind == "TGA" and dtg_column(table) is None and not _own_dtg(table): return None
    return d.kind if table.x and table.ys else None


def _own_dtg(table):
    from opstudio.detection import normalise
    return next((c for c in table.numeric if any(k in normalise(c) for k in ("dtg", "derivative", "dmdt", "deriv"))), None)


def peak_table(kind, table):
    """The peaks of a thermal run (DTG minima = steps of mass loss) or the bands of an infrared spectrum, one row each:
    where it is, how large, what it may be (the usual event or bond there, most likely first), the other possibilities,
    and a Label - the short name of the most likely one with a question mark, for you to keep, change or clear."""
    from opstudio.detection import normalise
    rows = []
    if kind == "TGA":
        from opstudio import tga_core
        cols = list(table.numeric); names = {c: normalise(c) for c in cols}
        find = lambda *keys: next((c for c in cols if any(k in names[c] for k in keys)), None)
        mass = find("mass", "weight", "tgpercent"); temp = find("temperature", "temp", "celsius", "degc")
        if not mass or not temp: return pd.DataFrame()
        T = table.arr(temp); m = table.arr(mass); ok = np.isfinite(T) & np.isfinite(m); T, m = T[ok], m[ok]
        o = np.argsort(T, kind="stable"); T, m = T[o], m[o]; keep = np.concatenate([[True], np.diff(T) > 0]); T, m = T[keep], m[keep]
        if len(T) < 20: return pd.DataFrame()
        grid = np.linspace(T[0], T[-1], int(min(max(len(T), 400), 6000))); mg = np.interp(grid, T, m)
        if abs(mg[0]) > 1e-9 and not ("%" in mass or "percent" in names[mass] or "pct" in names[mass]): mg = mg / mg[0] * 100.0      # an absolute mass: in % of the first point
        d = tga_core.dtg(grid, mg)["dtg_per_C"]
        try: zones = tga_core.suggest_zones(grid, d)
        except Exception: zones = []
        first = float(grid[0]) + max(15.0, 0.02 * float(grid[-1] - grid[0]))
        for z in zones:
            loss = tga_core.stepwise_loss(grid, mg, z["T"][0], z["T"][1]); c = tga_candidates(z["T_peak"])
            if loss < 0.05 or z["T_peak"] <= first: continue               # no step worth a name; the first degrees are the balance settling
            rows.append({"DTG peak (°C)": round(z["T_peak"], 1), "From (°C)": round(z["T"][0], 1), "To (°C)": round(z["T"][1], 1), "Mass loss (%)": round(loss, 2),
                         "May be": c[0][0] if c else "", "Other possibilities": "; ".join(n for n, _s in c[1:]), "Label": (c[0][1] + " ?") if c else ""})
        return pd.DataFrame(rows, columns=["DTG peak (°C)", "From (°C)", "To (°C)", "Mass loss (%)", "May be", "Other possibilities", "Label"])
    if kind == "FTIR":
        import smart_plots as sp
        ycol = table.ys[0]; x = table.arr(table.x); y = table.arr(ycol); ok = np.isfinite(x) & np.isfinite(y); x, y = x[ok], y[ok]; o = np.argsort(x); x, y = x[o], y[o]
        if len(x) < 20: return pd.DataFrame()
        n = normalise(ycol); trans = "transmit" in n or "%t" in str(ycol).lower() or ("absorb" not in n and np.median(y) > 0.6 * np.max(y) and np.min(y) >= 0)
        pk, _left = sp.ftir_bands(x, y, trans, 15)                                             # the bands the graph labels (not the CO2 of the air, not the ends of the range)
        for p in sorted(pk, key=lambda q: -q["pos"]):
            c = ftir_candidates(p["pos"])
            rows.append({"Band (cm⁻¹)": round(p["pos"], 1), str(ycol): round(float(np.interp(p["pos"], x, y)), 4), "Read as": "minimum (transmittance)" if trans else "maximum (absorbance)",
                         "May be": c[0][0] if c else "", "Other possibilities": "; ".join(nm for nm, _s in c[1:]), "Label": (c[0][1] + " ?") if c else ""})
        return pd.DataFrame(rows, columns=["Band (cm⁻¹)", str(ycol), "Read as", "May be", "Other possibilities", "Label"])
    return pd.DataFrame()


def names_of(frame):
    """[(position, label)] of the rows of a peak table that have a label."""
    if frame is None or not len(frame) or "Label" not in frame.columns: return []
    out = []
    for pos, lab in zip(frame.iloc[:, 0], frame["Label"]):
        lab = "" if lab is None or (isinstance(lab, float) and np.isnan(lab)) else str(lab).strip()
        try: pos = float(pos)
        except Exception: continue
        if lab: out.append((pos, lab))
    return out


def name_at(names, position, kind):
    """The label given for the peak at this position (the nearest within the tolerance of the kind), or None."""
    if not names: return None
    pos, lab = min(names, key=lambda n: abs(n[0] - position))
    return lab if abs(pos - position) <= TOLERANCE.get(kind, 0.0) else None


PEAK_COLUMN = {"TGA": "Peak (may be)", "FTIR": "Band (may be)"}
PEAK_POSITION = {"TGA": "Peak at (°C)", "FTIR": "Band at (cm⁻¹)"}


def peak_columns(kind, n_rows, peaks):
    """[(name, values)]: three columns for the data table that LIST the peaks from the first row down - where each is,
    its label, what it may be in full - and are empty below the list. In the table they are seen at once, beside the
    numbers, and they go into every export. (Written into the row of each peak instead, ten names were lost among
    thousands of rows.)"""
    if kind not in PEAK_COLUMN or peaks is None or not len(peaks) or n_rows < 1: return []
    k = min(len(peaks), n_rows); pos = np.full(n_rows, np.nan); lab = np.full(n_rows, "", dtype=object); what = np.full(n_rows, "", dtype=object)
    for i in range(k):
        try: pos[i] = float(peaks.iloc[i, 0])
        except Exception: pass
        v = peaks["Label"].iloc[i] if "Label" in peaks.columns else ""; lab[i] = "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)
        w = peaks["May be"].iloc[i] if "May be" in peaks.columns else ""; what[i] = "" if w is None or (isinstance(w, float) and np.isnan(w)) else str(w)
    return [(PEAK_POSITION[kind], pos), (PEAK_COLUMN[kind], lab), (MEANING_COLUMN, what)]


WORKED_NAMES = ("Peak (may be)", "Band (may be)", "What it may be", "Peak at (°C)", "Band at (cm⁻¹)")      # columns only the app makes: never data for a graph
MEANING_COLUMN = "What it may be"


def peak_column(kind, table, peaks):
    """(name, values) of a column for the data table itself: empty, except in the row of each peak, where its Label
    stands - so the names are seen beside the numbers and go into every export. peaks: the table of peak_table."""
    from opstudio.detection import normalise
    name = PEAK_COLUMN.get(kind)
    if not name or peaks is None or not len(peaks): return None
    if kind == "TGA":
        xcol = next((c for c in table.numeric if any(k in normalise(c) for k in ("temperature", "temp", "celsius", "degc"))), None)
    else: xcol = table.x
    if not xcol: return None
    x = table.arr(xcol); out = np.full(len(x), "", dtype=object)
    if not np.isfinite(x).any(): return None
    for pos, lab in names_of(peaks):
        out[int(np.nanargmin(np.abs(x - pos)))] = lab
    return name, out


MEANING_COLUMN = "What it may be"


def meaning_column(kind, table, peaks):
    """(name, values): beside the label of each peak, in the same row, what the peak may be in full - the usual event or
    bond at that position - so the table itself says what a label stands for."""
    from opstudio.detection import normalise
    if peaks is None or not len(peaks) or "May be" not in peaks.columns: return None
    xcol = next((c for c in table.numeric if any(k in normalise(c) for k in ("temperature", "temp", "celsius", "degc"))), None) if kind == "TGA" else table.x
    if not xcol: return None
    x = table.arr(xcol); out = np.full(len(x), "", dtype=object)
    if not np.isfinite(x).any(): return None
    for pos, what in zip(peaks.iloc[:, 0], peaks["May be"]):
        try: out[int(np.nanargmin(np.abs(x - float(pos))))] = str(what or "")
        except Exception: continue
    return MEANING_COLUMN, out


OVERVIEW_SHEET = "All side by side"


def sheet_name(name, used):
    """A name Excel accepts for a sheet (31 characters, none of []:*?/\\), not used yet."""
    base = re.sub(r"[\[\]:*?/\\]", "_", str(name)).strip("'")[:31] or "Sheet"; out = base; k = 2
    while out.lower() in {u.lower() for u in used}: tail = f" ({k})"; out = base[:31 - len(tail)] + tail; k += 1
    used.append(out); return out


PEAKS_OVERVIEW = "Peaks of all files"


def merged_workbook(path, inputs, extra=None, peaks=None):
    """The files merged into ONE Excel workbook: a sheet per file - its X column, its Y columns and what the app worked
    out for it (DTG, the names of its peaks), under their own column names - and a last sheet with all files side by
    side, every column labelled 'column [file]'. The app draws from the sheets (one graph per file, and the figure of
    all of them); the last sheet is the one to look at, copy or take into Origin. Returns the sheet names."""
    if len(inputs) < 2: raise ValueError("Select at least two datasets")
    wide = side_by_side(inputs, extra=extra); used = [OVERVIEW_SHEET]; names = []
    with pd.ExcelWriter(path) as xw:
        for p, table in inputs:
            cols = [(table.x, table.arr(table.x))] + [(c, table.arr(c)) for c in table.ys] + list(extra(p, table) if extra else [])
            n = max(len(v) for _c, v in cols); frame = pd.DataFrame({c: list(v) + [np.nan] * (n - len(v)) for c, v in cols})
            nm = sheet_name(stem(p), used); names.append(nm); frame.to_excel(xw, index=False, sheet_name=nm)
        rows = []
        for (p, _table), nm in zip(inputs, names):                         # peaks(path) -> the table of peaks of that file, or None
            pk = peaks(p) if peaks else None
            if pk is not None and len(pk):
                for _i, r in pk.iterrows(): rows.append({"File": nm, "Position": r.iloc[0], "Label": r.get("Label", ""), "What it may be": r.get("May be", ""), "Other possibilities": r.get("Other possibilities", "")})
        if rows: pd.DataFrame(rows).to_excel(xw, index=False, sheet_name=PEAKS_OVERVIEW)
        wide.to_excel(xw, index=False, sheet_name=OVERVIEW_SHEET)
    return names + ([PEAKS_OVERVIEW] if rows else []) + [OVERVIEW_SHEET]

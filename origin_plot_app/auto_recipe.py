"""
auto_recipe.py - a figure recipe for ANY workbook, worked out from its sheets.

    import auto_recipe as ar
    recipe, report = ar.build("my_workbook.xlsx")          # recipe: the dict paper_figures.run() draws; report: what each sheet was taken as

What it looks at (only what is in the workbook; nothing is invented):
  * a figure-plan sheet (columns such as Figure / Sheets to use / X title / Y title / Layout / Extras): one figure per row,
    using the sheets that row names (also "*_Profile"-style wildcards with the sample names listed in the row);
  * colour keys written anywhere as "<name> <code> #RRGGBB" (or "<code> #RRGGBB"), and key tables (code + meaning);
  * the kind of every data sheet: diffraction / spectrum patterns, fits (observed + calculated [+ difference]), Bragg tick
    lists, peak-label lists, zoom windows, already-offset stacks, x-y series, category tables, agreement indices (Rwp).
Without a plan sheet, the sheets are grouped into figures by kind and by their names (sheets of one family = one figure).
"""
import os, re, math
import numpy as np
import pandas as pd

try:
    from opstudio import side_tables as SD
except Exception:                                   # run from another folder
    import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from opstudio import side_tables as SD

norm = SD.norm
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
MEASURED_WORDS = ("measured", "experimental", "observed", "rietveld", "qxrd", "qpa", "exp")
SPECTRAL_X = ("2theta", "twotheta", "ppm", "wavenumber", "ramanshift", "cm1", "bindingenergy", "ev", "wavelength", "nm")
TEMP_X = ("temperature", "degc", "kelvin")
ERR = re.compile(r"(^|[^a-z])(sd|std|stdev|err|error|se|sem|±|\+/-|unc|uncertainty)([^a-z]|$)", re.I)


# ============================================================================================ reading
def load(path):
    if isinstance(path, dict): return {str(k): v for k, v in path.items()}
    return {str(k): v for k, v in pd.read_excel(path, sheet_name=None).items()}


def _num(df, c):
    return pd.to_numeric(df[c], errors="coerce")


def numeric_cols(df, share=0.8):
    return [str(c) for c in df.columns if len(df) and _num(df, c).notna().mean() >= share and _num(df, c).notna().sum() >= 1]


def text_cols(df):
    return [str(c) for c in df.columns if str(c) not in numeric_cols(df, 0.5) and df[c].notna().any()]


def strip_unit(h):
    h = str(h)
    h = re.sub(r"\s*\((?:wt\.?\s*%|wt%|%|counts|a\.u\.|mass\s*%|g\s*/\s*100\s*g|j/g|mw/g)\)\s*$", "", h, flags=re.I)
    return h.strip()


def unit_of(h):
    m = re.search(r"\(([^()]*)\)\s*$", str(h))
    return m.group(1) if m else ""


def axis_title(h):
    """A column header as an axis title: the same words, with the usual symbols ('2theta_deg' -> '2θ (°)', 'cm-1' -> 'cm⁻¹')."""
    h = str(h); n = norm(h)
    if n in ("2theta", "2thetadeg", "twotheta", "2th", "tth", "2thetadegree", "2thetadegrees", "angle2theta"): return "2θ (°)"
    h = re.sub(r"cm-1|cm\^-1|1/cm", "cm$^{-1}$", h)
    return h.replace("_", " ")


FORMULA = re.compile(r"(?<![\w$])((?:[A-Z][a-z]?\d*){2,}'?|[A-Z][a-z]?\d+[A-Z][\w]*)(?![\w$])")


def chem(text):
    """Chemical formulas in a title or a legend entry with their numbers as subscripts: Na2O -> Na$_2$O, C3S -> C$_3$S,
    Ca2Fe2O5 -> Ca$_2$Fe$_2$O$_5$. A sample name such as S1 or P12 (one symbol and a number) is left as it is."""
    def one(m):
        t = m.group(0)
        if not re.search(r"\d", t) or re.fullmatch(r"[A-Z][a-z]?\d+", t): return t
        if len(re.findall(r"[A-Z]", t)) < 2: return t
        return re.sub(r"(\d+)", r"$_{\1}$", t)
    return FORMULA.sub(one, str(text))


def bracket_note(sheets):
    """The workbook's own sentence on labels in brackets (if it has one), for the note under a figure."""
    for df in sheets.values():
        for v in [str(c) for c in df.columns] + [str(x) for x in df.values.ravel().tolist()]:
            for sent in re.split(r"(?<=[.!?])\s+", v):
                if "bracket" in sent.lower() and len(sent) < 200 and any(w in sent.lower() for w in ("label", "letter", "code", "phase")): return sent.strip()
    return None


def pretty(name):
    return re.sub(r"[_]+", " ", str(name)).strip()


# ============================================================================================ colour keys
def colour_keys(sheets):
    """[{code, name, color}] from text like 'Phase one P1 #112233 | Phase two P2 #445566' (first table found wins per code),
    plus {code: meaning} from key tables (two text columns: a short code and its meaning)."""
    entries, meaning = [], {}
    for sh, df in sheets.items():
        cells = [str(v) for v in df.astype(str).values.ravel() if HEX.search(str(v))] + [str(c) for c in df.columns if HEX.search(str(c))]
        for cell in cells:
            for part in re.split(r"[|;\n]+", cell):
                m = HEX.search(part)
                if not m: continue
                before = part[:m.start()].strip(" :,=-\t")
                before = before.split(":")[-1].strip() if ":" in before and len(before.split(":")[-1].split()) <= 4 else before
                toks = before.split()
                if not toks or len(toks) > 6: continue
                code = toks[-1]; name = " ".join(toks[:-1]) or code
                entries.append({"code": code, "name": name, "color": m.group(0).upper(), "sheet": sh})
        tc = text_cols(df)
        if len(df.columns) >= 2 and len(tc) >= 2 and len(df) <= 80:
            a, b = tc[0], tc[1]
            av = df[a].dropna().astype(str)
            if len(av) and av.str.len().median() <= 4 and ("code" in norm(a) or "label" in norm(a) or "symbol" in norm(a)):
                for k, v in zip(df[a], df[b]):
                    if str(k) not in ("", "nan") and str(v) not in ("", "nan"): meaning.setdefault(str(k).strip(), str(v).strip())
    return entries, meaning


def phases_from(entries, meaning, codes_wanted=None):
    """The phase table of a recipe: letter, name, colour. Codes that are explained in a key table get that name."""
    seen, out = set(), []
    for e in entries:
        if e["code"] in seen: continue
        if codes_wanted is not None and e["code"] not in codes_wanted: continue
        seen.add(e["code"])
        nm = e["name"] if e["name"] != e["code"] else meaning.get(e["code"], e["code"])
        out.append({"letter": e["code"], "name": nm, "color": e["color"], "also": []})
    return out


# ============================================================================================ what is each sheet
def classify(name, df):
    """One of: plan, guide, labels, ticks, rwp, key, zoom, fit, pattern, stack, xy, category, long, other."""
    cols = [str(c) for c in df.columns]; n = norm(" ".join(cols))
    if df.empty or len(cols) < 2: return "guide"
    if any(norm(c) == "figure" or norm(c).startswith("figure") for c in cols) and any("sheet" in norm(c) for c in cols): return "plan"
    num = numeric_cols(df)
    if SD.is_label_table(df): return "labels"
    if SD.is_tick_table(df): return "ticks"
    if any("rwp" in norm(c) for c in cols) and text_cols(df): return "rwp"
    if not num:
        return "key" if len(df) <= 80 and len(cols) <= 4 else "guide"
    x = num[0]; xs = norm(x)
    has_obs = any(re.search(r"obs", norm(c)) for c in num); has_calc = any(re.search(r"calc", norm(c)) for c in num)
    xr = _num(df, x).dropna()
    if has_obs and has_calc:
        span = float(xr.max() - xr.min()) if len(xr) else 0
        return "zoom" if (span <= 8 and any(s in xs for s in SPECTRAL_X)) or "zoom" in norm(name) else "fit"
    if "offset" in n and len(num) >= 3: return "stack"
    if any(s in xs for s in SPECTRAL_X) and len(df) >= 200:
        return "spectra" if len([c for c in num[1:] if not ERR.search(c)]) >= 3 and not has_obs else "pattern"
    tc = text_cols(df)
    if tc and cols.index(tc[0]) == 0 and len(num) >= 1 and len(df) <= 60: return "category"
    if len(num) >= 2: return "xy"
    return "other"


def x_kind(df):
    num = numeric_cols(df)
    if not num: return ""
    xs = norm(num[0])
    if any(s in xs for s in SPECTRAL_X): return "spectral"
    if any(s in xs for s in TEMP_X): return "temperature"
    return "x"


# ============================================================================================ pieces of a recipe
def _obs_calc_diff(df):
    num = numeric_cols(df); x = num[0]
    o = next((c for c in num if "obs" in norm(c)), num[1] if len(num) > 1 else None)
    c_ = next((c for c in num if "calc" in norm(c)), None)
    d = next((c for c in num if "diff" in norm(c) and "lift" not in norm(c)), None)
    return x, o, c_, d


def _label_sheets_for(target_names, label_sheets, sheets):
    """Label sheets whose Sample values (or own names) belong to the given data names: [(sheet, {target: sample value})]."""
    out = []
    for ls in label_sheets:
        df = sheets[ls]; sc = next((c for c in df.columns if norm(c) in ("sample", "series", "pattern", "curve", "name")), None)
        if sc is None:
            out.append((ls, {})); continue
        vals = [str(v) for v in pd.unique(df[sc].dropna())]
        hit = {}
        for t in target_names:
            i = SD.best_match(t, vals)
            if i is not None: hit[t] = vals[i]
        if hit: out.append((ls, hit))
    return out


def _codes_in_labels(df):
    lab = next((c for c in df.columns if norm(c) in ("label", "labels", "text", "peaklabel", "annotation", "phaselabel")), None)
    col = next((c for c in df.columns if "colour" in norm(c) or "color" in norm(c)), None)
    codes = {}
    if lab is None: return codes
    for _, r in df.iterrows():
        parts = [q for q in re.split(r"[+/,\s()\[\]]+", str(r[lab])) if q and q != "nan"]
        c = str(r[col]).strip() if col is not None and str(r[col]).strip().startswith("#") else None
        for k, part in enumerate(parts):
            if len(parts) == 1 and c: codes[part] = c                      # a label that is the code alone decides its colour
            elif part not in codes: codes[part] = c if k == 0 else None     # 'R+F' is coloured like R: it says nothing about F
    return codes


def _legend_codes(label_sheet_names, sheets, phases, meaning):
    """Legend items for the label codes used in these label sheets: '<code>, <name>' in the colour of the labels."""
    codes = {}
    for ls in label_sheet_names:
        for k, v in _codes_in_labels(sheets[ls]).items():
            if codes.get(k) is None: codes[k] = v
    if not codes: return []
    ph = {p["letter"]: p for p in phases}
    order = [p["letter"] for p in phases if p["letter"] in codes] + [k for k in codes if k not in ph]
    items = []
    for k in order:
        nm = (ph.get(k) or {}).get("name") or meaning.get(k) or ""
        col = codes.get(k) or (ph.get(k) or {}).get("color") or "#000000"
        items.append({"label": chem(f"{k}, {nm}" if nm and nm != k else k), "color": col, "kind": "square"})
    return items


def _strip_common(names):
    """Sheet names of one family without their shared start and end ('Run_S1', 'Run_S2' -> 'S1', 'S2'); only whole
    parts between _ - or spaces are cut ('Run_20C', 'Run_40C' -> '20C', '40C', never '2', '4')."""
    if len(names) < 2: return [pretty(n) for n in names]
    parts = [re.split(r"([_\-\s]+)", n) for n in names]
    k = 0
    while all(len(p_) > k + 1 for p_ in parts) and len({p_[k] for p_ in parts}) == 1: k += 1
    pre = "".join(parts[0][:k]) if k else ""
    j = 0
    while all(len(p_) > j + 1 + k for p_ in parts) and len({p_[-1 - j] for p_ in parts}) == 1: j += 1
    suf = "".join(parts[0][len(parts[0]) - j:]) if j else ""
    cut = []
    for n in names:
        m = n[len(pre):len(n) - len(suf) if suf else None].strip(" _-")
        cut.append(pretty(m) if m else pretty(n))
    return cut


def _letters(i): return f"({'abcdefghijklmnopqrstuvwxyz'[i]})"


# ============================================================================================ figure makers
def fig_patterns(name, pats, sheets, labels, phases, meaning, xlim=None, xtitle=None, ytitle=None, titles=None):
    """Patterns (observed only), one panel each, shared x."""
    n = len(pats); lab = _label_sheets_for(pats, labels, sheets); panels = []
    titles = titles or _strip_common(pats)
    for i, sh in enumerate(pats):
        df = sheets[sh]; num = numeric_cols(df); x = num[0]
        o = next((c for c in num[1:] if "obs" in norm(c)), num[1])
        pn = {"cell": [i, 0], "letter": f"{_letters(i)} {titles[i]}", "ytitle": ytitle if ytitle is not None else strip_unit(o) if "count" not in norm(o) else "Counts",
              "yfrom0": True, "ymax_factor": 1.1, "series": [{"sheet": sh, "x": x, "y": o, "color": "#000000", "lw": 0.6}]}
        if xlim: pn["xlim"] = xlim
        ls = [{"sheet": s, "sample": hit[sh]} for s, hit in lab if sh in hit]
        if ls: pn["labels"] = ls if len(ls) > 1 else ls[0]
        if i == n - 1: pn["xtitle"] = xtitle or axis_title(x)
        panels.append(pn)
    leg = _legend_codes([s for s, h in lab if any(p in h for p in pats)], sheets, phases, meaning)
    f = {"name": name, "width_mm": 175, "height_mm": 26 + 38 * n + (5 * math.ceil(len(leg) / 4) if leg else 0),
         "layout": {"rows": [1] * n, "cols": [1], "sharex": True, "hspace": 0.06, "bottom_mm": 13}, "panels": panels}
    if leg: f["legend"] = {"where": "below", "rows": math.ceil(len(leg) / 4), "ncol": 4, "items": leg}
    return f


def fig_stack(name, sh, sheets, labels, phases, meaning, xlim=None, zoom=None, xtitle=None, ytitle=None, hide_y=True):
    df = sheets[sh]; num = numeric_cols(df); x = num[0]; ys = num[1:]
    xr = _num(df, x).dropna(); full = [float(xr.min()), float(xr.max())]
    lab_all = [ls for ls in labels if _label_sheets_for([strip_unit(y) for y in ys], [ls], sheets) or SD.name_score(ls, sh) >= 0.34]
    rng = {}
    for ls in lab_all:                                       # a label sheet whose positions lie in a narrow window belongs to a zoom panel
        d_ = sheets[ls]; xc = next((c for c in d_.columns if "theta" in norm(c) or norm(c) in ("x", "position")), None)
        v = _num(d_, xc).dropna() if xc else pd.Series(dtype=float)
        rng[ls] = (float(v.min()), float(v.max())) if len(v) else full
    names_raw = [re.sub(r"\s*(intensity)?\s*\+?\s*offset.*$", "", y, flags=re.I).strip() or y for y in ys]
    display = list(names_raw)
    for ls in lab_all:                                       # the fuller names the label sheet uses for the same samples
        hit = dict(_label_sheets_for(names_raw, [ls], sheets) or [(ls, {})])[ls] if _label_sheets_for(names_raw, [ls], sheets) else {}
        display = [hit.get(n, d) for n, d in zip(names_raw, display)]
    wide = [ls for ls in lab_all if rng[ls][1] - rng[ls][0] > 0.4 * (full[1] - full[0])]
    narrow = [ls for ls in lab_all if ls not in wide]
    if zoom is None and narrow:
        lo = min(rng[l][0] for l in narrow); hi = max(rng[l][1] for l in narrow); zoom = [math.floor(lo), math.ceil(hi)]
    a = {"cell": [0, 0], "letter": "(a)", "xtitle": xtitle or axis_title(x), "ytitle": ytitle or "Intensity (offset)", "hide_yticklabels": hide_y,
         "series": [{"sheet": sh, "x": x, "y": "others", "color": "#000000", "lw": 0.5}], "names_left": display[::-1] if _first_on_top(df, ys) is False else display}
    if xlim: a["xlim"] = xlim
    if wide: a["labels"] = [{"sheet": l} for l in wide] if len(wide) > 1 else {"sheet": wide[0]}
    panels = [a]; cols = [1]
    if zoom:
        b = {"cell": [0, 1], "letter": "(b)", "xlim": zoom, "xtitle": xtitle or axis_title(x), "hide_yticklabels": hide_y,
             "series": [{"sheet": sh, "x": x, "y": "others", "color": "#000000", "lw": 0.6}]}
        if narrow: b["labels"] = [{"sheet": l} for l in narrow] if len(narrow) > 1 else {"sheet": narrow[0]}
        panels.append(b); cols = [2.4, 1]
    leg = _legend_codes(lab_all, sheets, phases, meaning)
    note = bracket_note(sheets) if any(re.search(r"\(\w+'?\)", str(t)) for ls in lab_all for t in _label_texts(sheets[ls])) else None
    f = {"name": name, "width_mm": 175, "height_mm": (125 if leg else 115) + (6 if note else 0), "layout": {"rows": [1], "cols": cols, "wspace": 0.04, "bottom_mm": 13, "sharey": True}, "panels": panels}
    if leg: f["legend"] = {"where": "below", "rows": math.ceil(len(leg) / 6), "ncol": 6, "items": leg}
    if note: f["note"] = note
    return f


def _label_texts(df):
    lab = next((c for c in df.columns if norm(c) in ("label", "labels", "text", "peaklabel", "annotation", "phaselabel")), None)
    return [str(v) for v in df[lab].dropna()] if lab is not None else []


def fig_spectra(name, sh, sheets, xtitle=None, ytitle=None):
    """Several spectra in one sheet (not offset in the file): stacked by the app, names at the right of each trace."""
    df = sheets[sh]; num = numeric_cols(df); x = num[0]; xv = _num(df, x).dropna()
    rev = any(k in norm(x) for k in ("wavenumber", "cm1", "ppm", "bindingenergy"))          # these axes run from high to low by custom
    pn = {"cell": [0, 0], "layout_mode": "stacked_offset", "offset_mode": "auto_percent", "offset_value": 80, "letter": None,
          "series": [{"sheet": sh, "x": x, "y": [c for c in num[1:] if not ERR.search(c)]}], "xtitle": xtitle or axis_title(x), "ytitle": ytitle or "Intensity (offset)",
          "palette": ["#000000"] * 12}
    f = {"name": name, "width_mm": 175, "height_mm": 110, "layout": {"rows": [1], "cols": [1], "right_mm": 26, "bottom_mm": 12}, "panels": [pn]}
    if rev: pn["xreverse"] = True
    return f


def _first_on_top(df, ys):
    """True when the first series column is drawn highest (already-offset stacks)."""
    try:
        m = [float(_num(df, y).median()) for y in ys]
        return m[0] > m[-1]
    except Exception:
        return None


def _pick(name, cands, sheets=None):
    """The candidate sheet that belongs to `name`; on a tie a tick sheet in the pair layout wins over a long list."""
    if not cands: return None
    sc = [SD.name_score(name, c) for c in cands]; top = max(sc)
    if top < 0.34: return None
    best = [c for c, v in zip(cands, sc) if v == top]
    if len(best) > 1 and sheets is not None:
        best = [c for c in best if SD.tick_pairs(sheets[c])] or best
    return best[0] if len(best) == 1 else None


def _riet_parts(fit_sheets, sheets, kinds, only=None):
    pool = only or list(kinds)
    ticks = [s for s in pool if kinds.get(s) == "ticks"]; zooms = [s for s in pool if kinds.get(s) == "zoom"]
    if only and not ticks: ticks = [s for s, k in kinds.items() if k == "ticks"]
    if only and not zooms: zooms = [s for s, k in kinds.items() if k == "zoom"]
    return {fs: {"ticks": _pick(fs, ticks, sheets), "zoom": _pick(fs, zooms, sheets)} for fs in fit_sheets}


def fig_fits(name, fits, sheets, kinds, labels, rwp, phases, meaning, ncols=None, titles=None, with_labels=True, xtitle=None, ytitle=None, xlim=None, only=None):
    parts = _riet_parts(fits, sheets, kinds, only); n = len(fits)
    nc = ncols or (1 if n <= 2 else 3 if n > 4 else 2); nr = math.ceil(n / nc)
    lab = _label_sheets_for(fits, labels, sheets) if with_labels else []
    panels = []
    for i, fs in enumerate(fits):
        df = sheets[fs]; x, o, c, d = _obs_calc_diff(df); xr = _num(df, x).dropna()
        rng = [float(xr.min()), float(xr.max())]
        if xlim is None and parts[fs]["ticks"]:               # the refined range: where the reflection list has positions
            try:
                tp = np.concatenate([v for _, v, _ in __import__("paper_figures").tick_rows(sheets[parts[fs]["ticks"]]) if len(v)])
                lo_, hi_ = math.floor(float(np.nanmin(tp))), math.ceil(float(np.nanmax(tp)))
                if hi_ - lo_ > 0.3 * (rng[1] - rng[0]): rng = [max(rng[0], lo_), min(rng[1], hi_)]
            except Exception: pass
        pn = {"cell": [i // nc, i % nc], "type": "rietveld", "letter": _letters(i), "title": chem(titles[i] if titles else pretty(fs)),
              "profile": fs, "x": x, "obs": o, "calc": c, "xlim": xlim or rng,
              "ytitle": (ytitle or "Intensity (counts)") if i % nc == 0 else None, "xtitle": (xtitle or axis_title(x)) if i // nc == nr - 1 else None,
              "legend_in_panel": i == 0 and nc == 1, "rwp_newline": nc > 1}
        if d: pn["diff"] = d
        if parts[fs]["ticks"]: pn["ticks"] = parts[fs]["ticks"]
        if parts[fs]["zoom"]:
            zx = _num(sheets[parts[fs]["zoom"]], numeric_cols(sheets[parts[fs]["zoom"]])[0]).dropna()
            pn["zoom"] = parts[fs]["zoom"]; pn["zoom_xlim"] = [round(float(zx.min()), 2), round(float(zx.max()), 2)]; pn["shade"] = pn["zoom_xlim"]
        r = SD.rwp_for(fs, rwp) if rwp else None
        if r is not None: pn["rwp"] = r
        ls = [{"sheet": s, "sample": hit[fs]} for s, hit in lab if fs in hit]
        if ls and nc == 1: pn["labels"] = ls[0]
        panels.append(pn)
    W = 175 if nc <= 2 else 260; H = (75 if nc == 1 else 86) * nr + 12
    f = {"name": name, "width_mm": W, "height_mm": H, "layout": {"rows": [1] * nr, "cols": [1] * nc, "hspace": 0.16 if nc == 1 else 0.3, "wspace": 0.16, "bottom_mm": 12}, "panels": panels}
    if nc > 1: f["legend"] = {"where": "below", "rows": 1, "items": [{"label": "Observed", "kind": "markers", "marker": "o", "filled": False, "color": "#000000"},
                                                                   {"label": "Calculated", "kind": "line", "color": "#CC0000"}, {"label": "Difference", "kind": "line", "color": "#555555"}]}
    return f


LINE_STYLES = [dict(color="#000000", ls="-", marker="o", filled=True), dict(color="#0072B2", ls="--", marker="s", filled=False),
               dict(color="#D55E00", ls=":", marker="^", filled=False), dict(color="#009E73", ls="-.", marker="D", filled=False),
               dict(color="#CC79A7", ls="--", marker="v", filled=False), dict(color="#E69F00", ls=":", marker="P", filled=False)]


def fig_xy(name, group, sheets, phases, xtitle=None, ytitle=None, titles=None, ylim=None, xreverse=None, legend_cell=True):
    """One panel per sheet; series that play the same role share one style (or one phase colour) in every panel."""
    n = len(group); legend_cell = legend_cell and n > 1
    total = n + (1 if legend_cell else 0)                  # the legend takes the cell after the last panel
    nc = 3 if total > 4 else 2 if total == 4 else total; nr = math.ceil(total / nc)
    heads = [h for sh in group for h in numeric_cols(sheets[sh])[1:]]; grp = [i for i, sh in enumerate(group) for _ in numeric_cols(sheets[sh])[1:]]
    keys = SD.role_keys([strip_unit(h) for h in heads], floor=0.45, groups=grp); it = iter(keys)
    ph_names = [p["name"] for p in phases]
    use_phase = sum(1 for h in heads if any(norm(pn) and norm(pn) in norm(h) for pn in ph_names)) >= 0.6 * len(heads) if phases else False
    few = all(len(sheets[sh]) <= 15 for sh in group)
    units = {unit_of(h) for h in heads}
    yt = ytitle if ytitle is not None else (next(iter(units)) if len(units) == 1 and next(iter(units)) else "")
    tt = titles or _strip_common(group)
    panels, first = [], {}
    allx = []
    for i, sh in enumerate(group):
        df = sheets[sh]; num = numeric_cols(df); x = num[0]; ser = []
        xv = _num(df, x).dropna(); allx.append(xv)
        for h in num[1:]:
            k = next(it); first.setdefault(k, strip_unit(h))
            if use_phase:
                ser.append({"sheet": sh, "x": x, "y": h, "phase_colors": True, "lw": 1.1, "label": None})
            else:
                st = LINE_STYLES[k % len(LINE_STYLES)]
                ser.append({"sheet": sh, "x": x, "y": h, "kind": "line+markers" if few else "line", "color": st["color"], "ls": st["ls"], "marker": st["marker"],
                            "filled": st["filled"], "lw": 1.0, "label": chem(first[k])})
        for s_ in ser:
            if s_.get("label") is None: s_.pop("label")
        pn = {"cell": [i // nc, i % nc], "letter": _letters(i), "title": chem(tt[i]), "series": ser, "xtitle": xtitle or axis_title(x), "ytitle": yt, "yfrom0": True}
        if few:
            u = sorted(set(float(v) for v in xv))
            if 2 <= len(u) <= 8: pn["xticks"] = u
        if ylim: pn["ylim"] = ylim
        rev = xreverse if xreverse is not None else (len(xv) > 2 and xv.iloc[0] > xv.iloc[-1])
        if rev: pn["xlim"] = [float(xv.max()), float(xv.min())]
        panels.append(pn)
    if ylim is None and len(group) > 1 and x_kind(sheets[group[0]]) == "temperature":     # the same y range in every panel of a series
        top = max(float(_num(sheets[sh], h).max()) for sh in group for h in numeric_cols(sheets[sh])[1:])
        for pn in panels: pn["ylim"] = [0, round(top * 1.1, 1)]
    f = {"name": name, "width_mm": 175, "height_mm": 18 + 52 * nr, "layout": {"rows": [1] * nr, "cols": [1] * nc, "hspace": 0.55, "wspace": 0.42, "bottom_mm": 10, "left_mm": 14},
         "panels": panels}
    if legend_cell:
        f["panels"].append({"cell": [n // nc, n % nc], "type": "legend"})
    else:
        f["legend"] = {"where": "below", "rows": 1}; f["height_mm"] += 8
    return f


def fig_bars(name, group, sheets, xtitle=None, ytitles=None, titles=None, points_last=None):
    hatches = [None, "//", "\\\\", "xx", "..", "++"]; colors = ["#595959", "#E69F00", "#56B4E9", "#D55E00", "#009E73", "#CC79A7"]
    panels = []; n = len(group); tt = titles or (_strip_common(group) if n > 1 else [""])
    ymax = 0
    for i, sh in enumerate(group):
        df = sheets[sh]; num = numeric_cols(df); cat = text_cols(df)[0]
        vals = [c for c in num if not ERR.search(c)]
        errs = {c: (num[num.index(c) + 1] if num.index(c) + 1 < len(num) and ERR.search(num[num.index(c) + 1]) else None) for c in vals}
        last = vals[-1]; pts = points_last if points_last is not None else (len(vals) > 2 and any(w in norm(last) for w in MEASURED_WORDS))
        bars_c = vals[:-1] if pts else vals
        bars = [{"column": c, "label": chem(strip_unit(c)), "color": colors[j % len(colors)], **({"hatch": hatches[j % len(hatches)]} if hatches[j % len(hatches)] else {}),
                 **({"error": errs[c]} if errs.get(c) else {})} for j, c in enumerate(bars_c)]
        cats = [str(v) for v in df[cat]]
        if max(len(c) for c in cats) * len(cats) > 40: cats = [c.replace(" (", "\n(", 1) if " (" in c else c.replace(" ", "\n", 1) for c in cats]
        units = {unit_of(c) for c in vals}
        pn = {"cell": [0, i], "type": "bars", "letter": _letters(i) if n > 1 else None, "title": chem(tt[i]), "sheet": sh, "bars": bars, "categories": cats,
              "xtitle": xtitle or axis_title(cat), "ytitle": (ytitles[i] if ytitles else (next(iter(units)) if len(units) == 1 else ""))}
        if pts: pn["points"] = {"column": last, "label": chem(strip_unit(last))}
        ymax = max(ymax, float(np.nanmax(df[num].apply(pd.to_numeric, errors="coerce").to_numpy())))
        panels.append(pn)
    for pn in panels: pn["ylim"] = [0, round(ymax * 1.15, 1)]
    pl = [pn["points"]["label"] for pn in panels if pn.get("points")]
    if len(set(pl)) > 1:                                   # one legend entry for the measured points of all panels
        ws = [p_.split() for p_ in pl]; k = 0
        while all(len(w) > k for w in ws) and len({w[k] for w in ws}) == 1: k += 1
        head = " ".join(ws[0][:k]) or "Measured"
        rest = ", ".join(f"{' '.join(w[k:]) or '-'} in {pn['letter'].strip('()')}" for w, pn in zip(ws, [q for q in panels if q.get("points")]))
        for pn in panels:
            if pn.get("points"): pn["points"]["label"] = f"{head} ({rest})"
    return {"name": name, "width_mm": 175, "height_mm": 90, "layout": {"rows": [1], "cols": [1] * n, "wspace": 0.2, "bottom_mm": 16},
            "legend": {"where": "below", "rows": 1}, "panels": panels}


# ============================================================================================ plan sheet
def _sheet_refs(text, names):
    """The sheet names a cell of the plan names, in their order (longest names first, so 'A_B' is not read as 'A')."""
    text = str(text); found = []
    for nm in sorted(names, key=len, reverse=True):
        for m in re.finditer(r"(?<![\w-])" + re.escape(nm) + r"(?![\w-])", text):
            if not any(m.start() < e and m.end() > s for s, e, _ in found): found.append((m.start(), m.end(), nm))
    for pat in re.findall(r"(\*?[\w-]*\*[\w-]*)", text):        # wildcards such as *_Profile, Ticks_*
        rx = "^" + re.escape(pat).replace(r"\*", ".*") + "$"
        for nm in names:
            if re.match(rx, nm) and nm not in [f[2] for f in found]: found.append((10 ** 6 + len(found), 0, nm))
    out = []
    for f in sorted(found):
        if f[2] not in out: out.append(f[2])
    return out


def _range(text, key=None):
    """'x 6 to 70', '10-60°', 'y 0 to 72', 'zoom 31-35' -> [lo, hi]."""
    t = str(text)
    pat = (rf"{key}\s*(?:from\s*)?(-?\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(-?\d+(?:\.\d+)?)" if key else r"(-?\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(-?\d+(?:\.\d+)?)\s*°?")
    m = re.search(pat, t, re.I)
    return [float(m.group(1)), float(m.group(2))] if m else None


def _plan_rows(df):
    cols = {norm(c): c for c in df.columns}
    g = lambda r, *keys: next((str(r[cols[k]]) for k in cols if any(k.startswith(w) for w in keys) and str(r[cols[k]]) not in ("", "nan")), "")
    rows = []
    for _, r in df.iterrows():
        fig = g(r, "figure")
        if not fig: continue
        rows.append({"figure": fig, "content": g(r, "content", "title", "description"), "layout": g(r, "layout"), "sheets": g(r, "sheetstouse", "sheets", "data"),
                     "xtitle": g(r, "xtitle", "xaxis"), "ytitle": g(r, "ytitle", "yaxis"), "series": g(r, "seriesandstyle", "series", "style"),
                     "extras": g(r, "extras", "notes", "options")})
    return rows


def _title_of(t):
    """An axis title from the plan without its instructions: 'Temperature (°C), axis reversed 1450 to 900' -> 'Temperature (°C)'."""
    t = re.split(r";|, axis| axis reversed|, hide| hide ", str(t))[0].strip()
    return t


def _names_in(text, candidates):
    """Sample names the plan row lists ('for S1, S2, S3 ...') that match the candidate sheets."""
    toks = re.findall(r"[A-Za-z][\w']*", str(text)); out = []
    for c in candidates:
        if any(SD.name_score(t, c) >= 0.9 and len(t) >= 2 for t in toks): out.append(c)
    return out


# ============================================================================================ build
def build(path_or_sheets, name_hint=""):
    sheets = load(path_or_sheets)
    kinds = {s: classify(s, df) for s, df in sheets.items()}
    entries, meaning = colour_keys(sheets)
    phases = phases_from(entries, meaning)
    labels = [s for s, k in kinds.items() if k == "labels"]
    rwp = {}
    for s, k in kinds.items():
        if k == "rwp":
            try: rwp.update(SD.rwp_of(sheets[s]))
            except Exception: pass
    report = [f"{s}: {k}" for s, k in kinds.items()]
    figures, used = [], set()
    plan = next((s for s, k in kinds.items() if k == "plan"), None)
    if plan:
        for row in _plan_rows(sheets[plan]):
            refs = [r for r in _sheet_refs(row["sheets"] + " " + row["extras"], list(sheets)) if r != plan]
            f = _from_plan(row, refs, sheets, kinds, labels, rwp, phases, meaning)
            if f: figures.append(f); used.update(refs); report.append(f"plan row '{row['figure']}' -> {f['name']} ({', '.join(refs)})")
            else: report.append(f"plan row '{row['figure']}': no sheet of it could be drawn")
    else:
        figures = _by_kind(sheets, kinds, labels, rwp, phases, meaning, used)
    have = {p["letter"] for p in phases}
    for ls in labels:                                      # codes whose only colour is the one of their labels (tick rows use it too)
        for k, c in _codes_in_labels(sheets[ls]).items():
            if c and k not in have: phases.append({"letter": k, "name": meaning.get(k, k), "color": c, "also": []}); have.add(k)
    recipe = {"name": f"Figures from {name_hint or 'workbook'} (made automatically)", "made_by": "auto_recipe", "workbook_hint": [name_hint] if name_hint else [],
              "phases": phases, "figures": figures}
    left = [s for s, k in kinds.items() if s not in used and k in ("pattern", "fit", "stack", "spectra", "xy", "category")]
    if left and plan: report.append("data sheets the plan does not use: " + ", ".join(left))
    return recipe, report


def _by_kind(sheets, kinds, labels, rwp, phases, meaning, used):
    figs = []
    fits = [s for s, k in kinds.items() if k == "fit"]
    ticks = [s for s, k in kinds.items() if k == "ticks"]
    with_ticks = [f for f in fits if _pick(f, ticks, sheets) is not None]
    pats = [s for s, k in kinds.items() if k == "pattern"] + [f for f in fits if f not in with_ticks]
    if pats: figs.append(fig_patterns("Patterns", pats, sheets, labels, phases, meaning)); used.update(pats)
    for s, k in kinds.items():
        if k == "stack": figs.append(fig_stack(f"Stack {pretty(s)}", s, sheets, labels, phases, meaning)); used.add(s)
        if k == "spectra": figs.append(fig_spectra(pretty(s), s, sheets)); used.add(s)
    if with_ticks:
        figs.append(fig_fits("Fits", with_ticks, sheets, kinds, labels, rwp, phases, meaning)); used.update(with_ticks)
    for kind_, maker in (("xy", fig_xy), ("category", fig_bars)):
        groups = _families([s for s, k in kinds.items() if k == kind_], sheets)
        for g in groups:
            nm = (os.path.commonprefix(g).strip(" _-") or pretty(g[0])) if len(g) > 1 else pretty(g[0])
            figs.append(maker(nm, g, sheets, phases) if kind_ == "xy" else maker(nm, g, sheets)); used.update(g)
    return figs


def _families(names, sheets):
    """Sheets of one family: the same start of the name (before _ or space) and the same x column."""
    fam = {}
    for s in names:
        head = re.split(r"[_\s]", s)[0] if re.search(r"[_\s]", s) else s
        x = norm(numeric_cols(sheets[s])[0]) if numeric_cols(sheets[s]) else ""
        fam.setdefault((head.lower(), x), []).append(s)
    return list(fam.values())


def _from_plan(row, refs, sheets, kinds, labels, rwp, phases, meaning):
    name = re.sub(r"[^\w-]+", "_", f"{row['figure']} {row['content']}").strip("_")[:60]
    data = [r for r in refs if kinds.get(r) in ("pattern", "fit", "stack", "spectra", "xy", "category")]
    labs = [r for r in refs if kinds.get(r) == "labels"]
    text = " ".join(row.values())
    xt = _title_of(row["xtitle"]) or None; yt_all = row["ytitle"]
    yt = [_title_of(t) for t in re.split(r";", yt_all)] if yt_all else []
    xlim = _range(row["extras"], "x") or _range(row["layout"], r"\(a\)")
    ylim = _range(row["extras"], "y")
    hide = "hide y tick" in text.lower()
    if not data: return None
    kinds_ = [kinds[d] for d in data]
    if "stack" in kinds_:
        sh = data[kinds_.index("stack")]
        xa = _range(row["layout"], r"\(a\)") or _range(row["extras"], r"\(a\)[^;]*?x")   # the range of panel (a); an x range written for panel (b) is the zoom
        f = fig_stack(name, sh, sheets, labs or labels, phases, meaning, xlim=xa, zoom=_range(row["layout"], "zoom"), xtitle=xt, ytitle=yt[0] if yt else None, hide_y=hide or True)
        return f
    if "spectra" in kinds_:
        return fig_spectra(name, data[kinds_.index("spectra")], sheets, xtitle=xt, ytitle=yt[0] if yt else None)
    fits = [d for d in data if kinds[d] == "fit"]
    ticks = [r for r in refs if kinds.get(r) == "ticks"]
    if fits and ticks:
        sel = fits
        if "*" in row["sheets"]:                       # 'Same as Fig 3 for S1, S2, ... (use the matching *_Profile ...)'
            sel = [f for f in fits if _pick(f, ticks, sheets) is not None]
            named = _names_in(row["sheets"] + " " + row["content"] + " " + row["layout"], sel)
            sel = sorted(named, key=lambda f: _order_in(f, row["sheets"])) if named else sel
        nc = 3 if re.search(r"3\s*x\s*2|2\s*x\s*3|2\s*×\s*3|3\s*×\s*2", row["layout"]) else None
        rt = _riet_titles(sel, labels, sheets)
        return fig_fits(name, sel, sheets, kinds, labs or labels, rwp, phases, meaning, ncols=nc, titles=rt, with_labels=bool(labs), xtitle=xt,
                        ytitle=(yt[0] if yt else None), xlim=xlim, only=refs)
    if all(kinds[d] in ("pattern", "fit") for d in data):
        return fig_patterns(name, data, sheets, labs or labels, phases, meaning, xlim=xlim, xtitle=xt, ytitle=(yt[0] if yt else None))
    if all(kinds[d] == "xy" for d in data):
        rev = True if "revers" in text.lower() else None
        xl = _range(row["xtitle"]) if rev else None
        f = fig_xy(name, data, sheets, phases, xtitle=xt, ytitle=(yt[0] if yt else None), ylim=ylim, xreverse=rev)
        if xl:
            for pn in f["panels"]:
                if pn.get("type") != "legend": pn["xlim"] = xl
        if "legend" in text.lower() and ("6th cell" in text.lower() or "free cell" in text.lower() or "last cell" in text.lower()):
            pass
        return f
    if all(kinds[d] == "category" for d in data):
        pts = True if re.search(r"last column.*(diamond|point|marker)|(diamond|point|marker).*last column", text, re.I) else None
        return fig_bars(name, data, sheets, xtitle=xt, ytitles=yt if len(yt) == len(data) else None, titles=None, points_last=pts)
    return None


def _order_in(name, text):
    toks = re.findall(r"[A-Za-z][\w']*", str(text))
    for i, t in enumerate(toks):
        if SD.name_score(t, name) >= 0.9: return i
    return 10 ** 6


def _riet_titles(fits, labels, sheets):
    """Titles of fits: the fuller sample name a label sheet uses for that fit, else the sheet name."""
    out = []
    for f in fits:
        best = None
        for ls, hit in _label_sheets_for([f], labels, sheets):
            if f in hit: best = hit[f]; break
        out.append(best or pretty(re.sub(r"[_\s]*profile$", "", f, flags=re.I)))
    return out


def save(recipe, folder, name):
    import json
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, re.sub(r"[^\w-]+", "_", name).strip("_") + ".json")
    with open(p, "w", encoding="utf-8") as fh: json.dump(recipe, fh, ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    import sys, json
    r, rep = build(sys.argv[1], os.path.splitext(os.path.basename(sys.argv[1]))[0])
    print("\n".join(rep))
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as fh: json.dump(r, fh, ensure_ascii=False, indent=1)
        print("written", sys.argv[2])

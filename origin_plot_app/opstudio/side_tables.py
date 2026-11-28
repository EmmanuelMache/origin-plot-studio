"""Side tables that decorate a graph: peak-label lists, Bragg-tick lists and agreement indices (Rwp).

The user ticks them beside the data tables; nothing here is guessed. A label table needs a text column of labels and a
position column; a tick table holds pairs "<code> 2θ (°)" + "<code> row" or a long list (phase/code + position); an Rwp
table holds a name column and a column whose header contains "Rwp". Every value comes from those tables.
Also here: matching a side table (or a label's Sample value) to the data table it belongs to, and matching the series
of several panels to each other (same role -> same style), both by the words in their names."""
import re
import numpy as np
import pandas as pd

GENERIC = {"profile", "profiles", "ticks", "tick", "bragg", "labels", "label", "zoom", "sheet", "data", "fit", "fits",
           "pattern", "patterns", "xrd", "the", "of", "and", "for", "counts", "wt", "deg", "2theta", "theta", "x", "y",
           "lists", "list", "file", "table", "peak", "peaks", "row", "rows", "rietveld"}


def norm(s):
    t = str(s).lower().replace("θ", "theta").replace("°", "deg").replace("′", "'")
    return re.sub(r"[^a-z0-9']+", "", t)


def words(s):
    t = str(s).lower().replace("θ", "theta").replace("°", " ")
    return [w for w in re.split(r"[^a-z0-9'.]+", t) if w and w not in GENERIC]


def similarity(a, b):
    """How much two names mean the same thing (0..1). A word counts when it is equal, or when one is the start of the
    other (ref / reference), so sheet names and the names in a Sample column can be matched."""
    A, B = words(a), words(b)
    if not A or not B: return 0.0
    hit = 0
    for w in A:
        if any(w == v or (len(w) >= 2 and len(v) >= 2 and (v.startswith(w) or w.startswith(v))) for v in B): hit += 1
    return hit / max(len(A), len(B))


def name_score(a, b):
    """How well two NAMES of one thing match (sheet names, Sample values, file names): pure numbers are left out
    (they are mostly ranges such as 31-35), the share of the shorter name that is found counts most, and the first
    word (usually the sample's own name) gives a bonus. 0..1.2"""
    A = [w for w in words(a) if not re.fullmatch(r"[\d.]+", w)]; B = [w for w in words(b) if not re.fullmatch(r"[\d.]+", w)]
    if not A or not B: return 0.0
    eq = lambda w, v: w == v or (len(w) >= 2 and len(v) >= 2 and (v.startswith(w) or w.startswith(v)))
    hit = sum(1 for w in A if any(eq(w, v) for v in B))
    sc = 0.7 * hit / min(len(A), len(B)) + 0.3 * hit / max(len(A), len(B))
    return sc + (0.2 if eq(A[0], B[0]) else 0.0)


def best_match(name, candidates, floor=0.34):
    """The index of the candidate whose name means the same as `name`, or None (also None on a tie)."""
    sc = [name_score(name, c) for c in candidates]
    if not sc: return None
    i = int(np.argmax(sc))
    if sc[i] < floor: return None
    if sum(1 for v in sc if v == sc[i]) > 1: return None              # a tie is not a match
    return i


def role_score(a, b):
    """similarity(), but two names whose numbers differ ('Model 1' / 'Model 2', 'Sample A' / 'Sample B') are different roles."""
    sc = similarity(a, b)
    na = {w for w in words(a) if re.fullmatch(r"[\d.]+|[a-z]", w)}; nb = {w for w in words(b) if re.fullmatch(r"[\d.]+|[a-z]", w)}
    if na and nb and not (na & nb): sc *= 0.4
    return sc


def role_keys(names, floor=0.45, groups=None):
    """Series of several panels that play the same role get the same key: [key per name], keys in first-seen order.
    'Model 1, equilibrium 1450 °C' and 'Model 1 liquid, 1450 °C' share a key; 'Model 3 ...' gets its own.
    groups: the panel of each name; two series of one panel never share a key."""
    keys, reps = [], []
    groups = groups if groups is not None else list(range(len(names)))
    for n, g in zip(names, groups):
        taken = {k for k, g2 in zip(keys, groups) if g2 == g}
        sc = [(role_score(n, r), k) for k, r in enumerate(reps) if k not in taken]
        sc = [q for q in sc if q[0] >= floor]
        if sc: k = max(sc)[1]
        else: reps.append(n); k = len(reps) - 1
        keys.append(k)
    return keys


# ------------------------------------------------------------------------------------------------- classify
def _is_text(col):
    """A column of names (object or string dtype, mostly not numbers)."""
    v = col.dropna()
    return len(v) > 0 and pd.to_numeric(v, errors="coerce").isna().mean() > 0.5

def _col(cols, *want, avoid=()):
    for c in cols:
        n = norm(c)
        if any(w in n for w in want) and not any(a in n for a in avoid): return c
    return None


def is_label_table(df):
    cols = [str(c) for c in df.columns]
    lab = next((c for c in cols if norm(c) in ("label", "labels", "text", "peaklabel", "annotation", "phaselabel")), None)
    if lab is None: return False
    spectral = _col(cols, "2theta", "ppm", "wavenumber", "ramanshift", avoid=("height", "top", "stagger", "row"))
    deco = _col(cols, "labelheight", "peaktop", "stagger", "colour", "color")
    x = spectral or (_col(cols, "position", "temperature", "x", avoid=("height", "top", "stagger", "row")) if deco else None)
    return x is not None and pd.to_numeric(df[x], errors="coerce").notna().mean() > 0.6     # a plain "Label, x, y" table is data, not a label list


def tick_pairs(df):
    X_TAIL = re.compile(r"[\s_]*(2\s*θ|2\s*theta|two\s*theta|tth|position|pos\b).*$", re.I)
    ROW = re.compile(r"^(.*?)[\s_]*row\s*$", re.I)
    cols = [str(c) for c in df.columns]; out = []
    for c in cols:
        m = ROW.match(c)
        if not m: continue
        code = m.group(1).strip()
        xc = next((d for d in cols if d != c and not ROW.match(d) and X_TAIL.search(d) and X_TAIL.sub("", d).strip() == code), None)
        if xc: out.append((code, xc, c))
    return out


def is_tick_table(df):
    if tick_pairs(df): return True
    cols = [str(c) for c in df.columns]
    code = next((c for c in cols if norm(c) in ("phase", "code", "labelcode", "phasecode")), None)
    x = _col(cols, "2theta")
    hkl = sum(1 for c in cols if norm(c) in ("h", "k", "l"))
    return bool(code and x and (hkl == 3 or "bragg" in " ".join(cols).lower()))


def is_rwp_table(df):
    cols = [str(c) for c in df.columns]
    return any("rwp" in norm(c) for c in cols) and any(_is_text(df[c]) for c in df.columns)


def kind(table):
    """'labels' | 'ticks' | 'rwp' | None for a Table (data.Table) or a DataFrame."""
    df = getattr(table, "df", table)
    try:
        if is_label_table(df): return "labels"
        if is_tick_table(df): return "ticks"
        if is_rwp_table(df): return "rwp"
    except Exception:
        return None
    return None


# ------------------------------------------------------------------------------------------------- read
def labels_of(df):
    """[{x, text, y?, top?, leader, color?, sample?}] in the order of the table."""
    cols = [str(c) for c in df.columns]
    lab = next(c for c in cols if norm(c) in ("label", "labels", "text", "peaklabel", "annotation", "phaselabel"))
    x = _col(cols, "2theta", "position", "ppm", "wavenumber", "temperature", "x", avoid=("height", "top", "stagger", "row"))
    y = _col(cols, "labelheight", "height", "labely")
    top = _col(cols, "peaktop", "top")
    stag = _col(cols, "stagger")
    colr = _col(cols, "colour", "color")
    smp = next((c for c in cols if norm(c) in ("sample", "series", "curve", "pattern", "name")), None)
    out = []
    for _, r in df.iterrows():
        t = str(r[lab]).strip()
        xv = pd.to_numeric(pd.Series([r[x]]), errors="coerce").iloc[0]
        if t in ("", "nan") or not np.isfinite(xv): continue
        g = lambda c: (pd.to_numeric(pd.Series([r[c]]), errors="coerce").iloc[0] if c else np.nan)
        it = {"x": float(xv), "text": t}
        if y and np.isfinite(g(y)): it["y"] = float(g(y))
        if top and np.isfinite(g(top)): it["top"] = float(g(top))
        it["leader"] = bool(stag and np.isfinite(g(stag)) and g(stag) > 0)
        if colr and str(r[colr]).strip().startswith("#"): it["color"] = str(r[colr]).strip()
        if smp and str(r[smp]) not in ("", "nan"): it["sample"] = str(r[smp])
        out.append(it)
    return out


def ticks_of(df):
    """{code: array of positions} in the file's order (top row first when the file numbers its rows)."""
    pairs = tick_pairs(df)
    if pairs:
        rows = []
        for code, xc, rc in pairs:
            v = pd.to_numeric(df[xc], errors="coerce").dropna().to_numpy()
            r = pd.to_numeric(df[rc], errors="coerce").dropna()
            rows.append((code, v, float(r.iloc[0]) if len(r) else 0.0))
        if any(r[2] for r in rows): rows.sort(key=lambda r: -r[2])
        return {c: v for c, v, _ in rows}
    cols = [str(c) for c in df.columns]
    code = next((c for c in cols if norm(c) in ("phase", "code", "labelcode", "phasecode")), None)
    x = _col(cols, "2theta")
    if not (code and x): return {}
    out = {}
    for k, g in df.groupby(code, sort=False):
        v = pd.to_numeric(g[x], errors="coerce").dropna().to_numpy()
        if len(v): out[str(k)] = v
    return out


def rwp_of(df):
    """{name: Rwp} from a table with a name column and an Rwp column (the first Rwp column)."""
    cols = [str(c) for c in df.columns]
    rc = next(c for c in cols if "rwp" in norm(c))
    names = [c for c in cols if _is_text(df[c])]
    out = {}
    for _, r in df.iterrows():
        v = pd.to_numeric(pd.Series([r[rc]]), errors="coerce").iloc[0]
        if np.isfinite(v):
            for c in names:
                if str(r[c]) not in ("", "nan"): out[str(r[c])] = float(v)
    return out


def rwp_for(name, rwp_map):
    """The Rwp of a fit by its name. Several names of one row (sample, display name, sheet name) may match equally well:
    that is fine when they all carry the same value; two different values are never guessed between."""
    if not rwp_map: return None
    keys = list(rwp_map); sc = [name_score(name, k) for k in keys]
    if not sc or max(sc) < 0.34: return None
    vals = {rwp_map[k] for k, v in zip(keys, sc) if v == max(sc)}
    return vals.pop() if len(vals) == 1 else None


# ------------------------------------------------------------------------------------------------- draw
PEAK_LABEL = "ops_peak_label"        # the gid of every artist that is a peak label (text, mark or leader): the 'Peak labels' switch shows or hides exactly these


def _artists(ax): return list(ax.texts) + list(ax.lines) + list(ax.collections) + list(ax.patches)


def tag_labels(ax, before):
    """Mark everything drawn on ax since 'before' (a set of ids from _artists) as a peak label."""
    for a in _artists(ax):
        if id(a) not in before: a.set_gid(PEAK_LABEL)


def show_labels(fig, ax, on):
    """Show or hide the peak labels of one panel (and of its insets). Returns how many artists it has. Curves stay."""
    n = 0
    for a_ in [ax] + list(getattr(ax, "child_axes", [])):
        for a in _artists(a_):
            if a.get_gid() == PEAK_LABEL: a.set_visible(bool(on)); n += 1
    return n


def has_labels(fig):
    return any(a.get_gid() == PEAK_LABEL for ax in fig.axes for a_ in [ax] + list(getattr(ax, "child_axes", [])) for a in _artists(a_))


def draw_labels(ax, labels, curves, names=None, size=6.0, color_of=None, leader_color="#8A8A8A"):
    """draw_labels_untagged, with everything it draws marked as a peak label (see PEAK_LABEL)."""
    before = {id(a) for a in _artists(ax)}
    n = draw_labels_untagged(ax, labels, curves, names, size, color_of, leader_color)
    tag_labels(ax, before)
    return n


def draw_labels_untagged(ax, labels, curves, names=None, size=6.0, color_of=None, leader_color="#8A8A8A"):
    """Labels from the user's list at their own peaks. curves: [(x, y)]; names: the curve names (to match a label's
    Sample value). A label with a height is put there; otherwise just above the highest point of its own curve near x.
    Labels never sit on their own curve or on another label; a moved label gets a thin leader line."""
    if not labels: return 0
    x0, x1 = sorted(ax.get_xlim()); y0, y1 = sorted(ax.get_ylim()); span = (y1 - y0) or 1.0; w = 0.004 * (x1 - x0)
    def lmax(c, x):
        m = (c[0] >= x - w) & (c[0] <= x + w)
        return float(np.nanmax(c[1][m])) if m.any() else None
    placed = []
    for lb in labels:
        x = lb["x"]
        if not (x0 <= x <= x1): continue
        own = None
        if lb.get("sample") is not None and names:
            own = best_match(lb["sample"], names)
        if own is None and curves:                            # nearest curve below the label's reference height
            ref = lb.get("top", lb.get("y"))
            if ref is not None:
                sc = []
                for c in curves:
                    m_ = lmax(c, x); sc.append(np.inf if m_ is None else (abs(ref - m_) if ref >= m_ - 0.02 * span else 10 * abs(ref - m_)))
                own = int(np.argmin(sc)) if np.isfinite(min(sc)) else None
            elif len(curves) == 1: own = 0
        top = lb.get("top")
        if top is None and own is not None: top = lmax(curves[own], x)
        y = lb.get("y", (top + 0.03 * span) if top is not None else None)
        if y is None: continue
        col = lb.get("color") or (color_of(lb["text"]) if color_of else "k")
        t = ax.text(x, y, lb["text"], ha="center", va="bottom", fontsize=size, fontweight="bold", color=col, zorder=12, clip_on=True)
        placed.append({"t": t, "x": x, "top": top, "own": own, "leader": lb.get("leader", False), "y": y})
    if not placed: return 0
    fig = ax.figure; fig.canvas.draw(); rd = fig.canvas.get_renderer(); inv = ax.transData.inverted(); boxes = []
    def box(t):
        b = t.get_window_extent(rd); (a0, b0), (a1, b1) = inv.transform((b.x0, b.y0)), inv.transform((b.x1, b.y1)); return [min(a0, a1), min(b0, b1), max(a0, a1), max(b0, b1)]
    for pl in sorted(placed, key=lambda q: (q["y"], q["x"])):
        b = box(pl["t"]); moved = False
        if pl["own"] is not None:
            cx, cy = curves[pl["own"]]; m = (cx >= b[0]) & (cx <= b[2])
            if m.any():
                hi = float(np.nanmax(cy[m]))
                if b[1] < hi + 0.008 * span:
                    d = hi + 0.012 * span - b[1]; b[1] += d; b[3] += d; moved = d > 0.02 * span; pl["t"].set_y(b[1])
        for _ in range(12):
            if not any(not (b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3]) for o in boxes): break
            b[1] += 0.045 * span; b[3] += 0.045 * span; moved = True; pl["t"].set_y(b[1])
        boxes.append(b)
        if (moved or pl["leader"]) and pl["top"] is not None and b[1] > pl["top"]:
            ax.plot([pl["x"], pl["x"]], [pl["top"], b[1]], color=leader_color, lw=0.3, zorder=11)
    hi = max(b[3] for b in boxes)
    if hi > y1: ax.set_ylim(y0, hi + 0.02 * span)
    return len(placed)

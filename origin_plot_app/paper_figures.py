"""
paper_figures.py - composed figures for a paper, drawn from a workbook by a recipe.

A recipe (a .json file in the folder figure_recipes, or one the assistant writes) says which sheets and
columns go into which panel and how they look. This module reads the numbers from the workbook exactly as
they are (nothing is edited, sorted or fitted) and writes every figure as PDF and as PNG (600 dpi).

    import paper_figures as pf
    report = pf.run("figures_workbook.xlsx", pf.load_recipe("my_figures"), "out_folder")

Panel types:  "xy" (lines / symbols, label sheets, shading, names at the curves)   "rietveld" (fit + difference +
Bragg tick rows + zoomed inset)   "bars" (grouped bars with hatch and overlaid points)   "legend" (a cell that
holds the legend and a note).   Columns are named exactly, or by {"contains": "..."} , or by position (0 = first).
A sheet or column that is not there is never guessed: the figure is still drawn without it and the report says so.
"""
import os, re, json, math

RECIPE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figure_recipes")
MM = 1 / 25.4


class Missing(Exception):
    pass


# ---------------------------------------------------------------------------------------------- reading
def norm(s):
    """Names are compared without case, spaces and punctuation; θ and 'theta' are the same."""
    t = str(s).lower().replace("θ", "theta").replace("°", "deg").replace("′", "'")
    return re.sub(r"[^a-z0-9']+", "", t)

def load_sheets(path):
    import pandas as pd
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"): return {str(k): v for k, v in pd.read_excel(path, sheet_name=None).items()}
    if os.path.isdir(path): return {os.path.splitext(f)[0]: pd.read_csv(os.path.join(path, f)) for f in sorted(os.listdir(path)) if f.lower().endswith(".csv")}
    raise Missing(f"'{os.path.basename(path)}' is not an Excel workbook (.xlsx) or a folder of .csv sheets")

def app_data_dir():
    """%APPDATA%\\OriginPlotApp on Windows; ~/.config/OriginPlotApp elsewhere."""
    base = os.environ.get("APPDATA") if os.name == "nt" else None
    return os.path.join(base or os.path.join(os.path.expanduser("~"), ".config"), "OriginPlotApp")

def plugin_dirs():
    """Folders for your own additions (figure recipes as .json, phase files as .csv): next to the app, and in your user folder."""
    return [os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_plugins"), os.path.join(app_data_dir(), "custom_plugins")]

def load_plugins():
    """Look through the plugin folders. A file that cannot be used is reported, never fatal.
    Returns {"recipes": {name: path}, "phase_libraries": [path], "problems": ["file: why"]}."""
    out = {"recipes": {}, "phase_libraries": [], "problems": []}
    for d in plugin_dirs():
        if not os.path.isdir(d): continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f); ext = os.path.splitext(f)[1].lower()
            try:
                if ext == ".json":
                    with open(p, encoding="utf-8") as fh: r = json.load(fh)
                    if not isinstance(r, dict) or not isinstance(r.get("figures"), list) or not r["figures"] or not all(isinstance(g, dict) and isinstance(g.get("panels"), list) for g in r["figures"]):
                        raise ValueError('a figure recipe needs "figures": [{"name": ..., "panels": [...]}]')
                    out["recipes"][os.path.splitext(f)[0]] = p
                elif ext == ".csv":
                    with open(p, encoding="utf-8-sig", errors="replace") as fh: lines = [l for l in fh.read().splitlines() if l.strip()]
                    nums = [l for l in lines if len(re.findall(r"[-+]?\d+(?:[.,]\d+)?", l)) >= 2]
                    if len(nums) < 1: raise ValueError("a phase file needs lines with a position (d or 2theta) and an intensity")
                    out["phase_libraries"].append(p)
            except Exception as e: out["problems"].append(f"{p}: {str(e)[:160]}")
    return out

def recipes():
    """The recipes that come with the app, were put into figure_recipes, or lie in a plugin folder: {name: path}."""
    try: out = {os.path.splitext(f)[0]: os.path.join(RECIPE_DIR, f) for f in sorted(os.listdir(RECIPE_DIR)) if f.lower().endswith(".json")}
    except Exception: out = {}
    try:
        for k, v in load_plugins()["recipes"].items(): out.setdefault(k, v)
    except Exception: pass
    return out

def load_recipe(name_or_path):
    p = name_or_path if os.path.isfile(str(name_or_path)) else recipes().get(str(name_or_path))
    if not p:
        hit = [v for k, v in recipes().items() if norm(name_or_path) in norm(k)]
        if not hit: raise Missing(f"there is no recipe '{name_or_path}'. Recipes: " + (", ".join(recipes()) or "none"))
        p = hit[0]
    with open(p, encoding="utf-8") as f: return json.load(f)

def recipe_for(workbook_path):
    """The recipe whose 'workbook_hint' is in the name of the workbook, or None."""
    for k, p in recipes().items():
        try:
            r = load_recipe(p)
            if any(norm(h) in norm(os.path.basename(workbook_path)) for h in (r.get("workbook_hint") or [])): return k
        except Exception: pass
    return None


class Book:
    """The sheets of the workbook, with forgiving look-up of sheet and column names and a list of what was not found."""
    def __init__(self, sheets): self.sheets = sheets; self.notes = []
    def note(self, text):
        if text not in self.notes: self.notes.append(text)
    def sheet(self, name):
        if name in self.sheets: return self.sheets[name]
        n = norm(name); hit = [k for k in self.sheets if norm(k) == n]
        if hit: return self.sheets[hit[0]]
        raise Missing(f"sheet '{name}' is not in the workbook")
    def col(self, df, sel, sheet="", optional=False):
        """One column of a sheet as its real name. sel: a name, a position (0 = first, -1 = last) or {"contains": text or [texts]}."""
        cols = list(df.columns)
        try:
            if isinstance(sel, bool): raise Missing("bad column")
            if isinstance(sel, int): return cols[sel]
            if isinstance(sel, dict):
                want = sel.get("contains"); want = [want] if isinstance(want, str) else list(want or []); no = sel.get("not"); no = [no] if isinstance(no, str) else list(no or [])
                hit = [c for c in cols if all(norm(w) in norm(c) for w in want) and not any(norm(x) in norm(c) for x in no)]
                if hit: return hit[0]
                raise Missing(f"no column with {' + '.join(want)} in sheet '{sheet}' (columns: {', '.join(map(str, cols))})")
            if sel in cols: return sel
            n = norm(sel); hit = [c for c in cols if norm(c) == n] or [c for c in cols if n and n in norm(c)]
            if hit: return hit[0]
            raise Missing(f"column '{sel}' is not in sheet '{sheet}' (columns: {', '.join(map(str, cols))})")
        except (Missing, IndexError) as e:
            if optional: return None
            raise Missing(str(e) if isinstance(e, Missing) else f"sheet '{sheet}' has no column number {sel}")
    def xy(self, sheet, x, y):
        import pandas as pd
        df = self.sheet(sheet); cx, cy = self.col(df, x, sheet), self.col(df, y, sheet)
        d = pd.DataFrame({"x": pd.to_numeric(df[cx], errors="coerce"), "y": pd.to_numeric(df[cy], errors="coerce")}).dropna()
        return d["x"].to_numpy(), d["y"].to_numpy(), str(cy)


# ---------------------------------------------------------------------------------------------- style
def _style(recipe):
    st = {"font": "Arial", "axis_title": 8.5, "tick_label": 7.5, "letter": 8.5, "axis_lw": 0.8, "label_size": 6.0, "legend": 7.0, "leader": "#8A8A8A", "leader_lw": 0.3, "dpi": 600}
    st.update(recipe.get("style") or {}); return st

def _apply_axes(ax, st, p=None):
    p = p or {}
    for s in ax.spines.values(): s.set_linewidth(st["axis_lw"]); s.set_visible(True)
    ax.tick_params(direction="in", top=True, right=True, width=st["axis_lw"], length=3, labelsize=st["tick_label"])
    ax.grid(False); ax.set_facecolor("white")
    if p.get("xtitle") is not None: ax.set_xlabel(p["xtitle"], fontsize=st["axis_title"])
    if p.get("ytitle") is not None: ax.set_ylabel(p["ytitle"], fontsize=st["axis_title"])
    if p.get("xlim"): ax.set_xlim(*p["xlim"])
    if p.get("xticks") is not None: ax.set_xticks(p["xticks"])
    if p.get("xticklabels") is not None: ax.set_xticklabels(p["xticklabels"])
    if p.get("xreverse"):
        lo, hi = sorted(ax.get_xlim()); ax.set_xlim(hi, lo)
    if p.get("hide_yticklabels"): ax.set_yticklabels([]); ax.tick_params(axis="y", labelleft=False)

def _letter(ax, p, st):
    t = " ".join(str(v) for v in (p.get("letter"),) if v)
    if p.get("title"): ax.set_title((t + " " if t else "") + str(p["title"]), fontsize=st["axis_title"], loc="left", fontweight="bold", pad=3)
    elif t: ax.text(0.012, 0.965, t, transform=ax.transAxes, ha="left", va="top", fontsize=st["letter"], fontweight="bold", zorder=20)

def phase_of(name, phases):
    """The entry of the phase table that a column name or a letter means: {"letter", "name", "color"}."""
    n = norm(name); best = None
    for ph in phases or []:
        keys = [ph.get("name", "")] + list(ph.get("also") or [])
        if str(name).strip() == ph.get("letter"): return ph
        for k in keys:
            if k and norm(k) in n and (best is None or len(norm(k)) > best[0]): best = (len(norm(k)), ph)
    return best[1] if best else None


# ---------------------------------------------------------------------------------------------- pieces
def _series(ax, book, s, phases, drawn, st):
    """One entry of "series": a column, a list of columns, or "others" (every column except x)."""
    import pandas as pd
    df = book.sheet(s["sheet"]); cx = book.col(df, s.get("x", 0), s["sheet"]); ys = s.get("y", "others")
    if ys == "others": cols = [c for c in df.columns if c != cx and pd.to_numeric(df[c], errors="coerce").notna().any()]
    else:
        cols = []
        for y in (ys if isinstance(ys, list) else [ys]):
            c = book.col(df, y, s["sheet"], optional=bool(s.get("optional")))
            if c is not None: cols.append(c)
    out = []
    for c in cols:
        d = pd.DataFrame({"x": pd.to_numeric(df[cx], errors="coerce"), "y": pd.to_numeric(df[c], errors="coerce")}).dropna()
        if d.empty: continue
        ph = phase_of(c, phases) if s.get("phase_colors") else None
        col = (ph or {}).get("color") or s.get("color", "#000000"); lw = (s.get("lw_by", {}) or {}).get((ph or {}).get("name", ""), s.get("lw", 0.8))
        kind = s.get("kind", "line"); mk = s.get("marker", "o"); ms = s.get("ms", 3.2); filled = s.get("filled", True)
        kw = dict(color=col, zorder=s.get("z", 3))
        if kind == "markers": ax.plot(d.x, d.y, linestyle="none", marker=mk, ms=ms, mfc=col if filled else "none", mec=col, mew=s.get("mew", 0.45), **kw)
        elif kind == "line+markers": ax.plot(d.x, d.y, linestyle=s.get("ls", "-"), lw=lw, marker=mk, ms=ms, mfc=col if filled else "white", mec=col, mew=s.get("mew", 0.8), **kw)
        else: ax.plot(d.x, d.y, linestyle=s.get("ls", "-"), lw=lw, **kw)
        lab = s.get("label") or ((ph or {}).get("name") if ph else str(c))
        drawn.append({"label": lab, "color": col, "kind": kind, "ls": s.get("ls", "-"), "lw": lw, "marker": mk, "filled": filled, "ms": ms})
        out.append((d.x.to_numpy(), d.y.to_numpy()))
    return out

def _labels(ax, book, spec, curves, st, fig):
    """Peak labels from a label sheet: text at (2θ, label height), in its own colour, with a thin leader when it is staggered.
    Afterwards no label may sit on a curve or on another label: such a label goes up, step by step, and keeps its colour."""
    import numpy as np, pandas as pd
    if not spec: return 0
    sheet = spec["sheet"]; df = book.sheet(sheet)
    cl = book.col(df, spec.get("text", "Label"), sheet); cxx = book.col(df, spec.get("x", {"contains": "2theta", "not": ["height", "top"]}), sheet); cy = book.col(df, spec.get("y", {"contains": "label height"}), sheet)
    cc = book.col(df, spec.get("color", {"contains": "colour"}), sheet, optional=True) or book.col(df, {"contains": "color"}, sheet, optional=True)
    cs = book.col(df, {"contains": "stagger"}, sheet, optional=True); ct = book.col(df, {"contains": "peak top"}, sheet, optional=True); csm = book.col(df, "Sample", sheet, optional=True)
    rows = df
    if spec.get("sample") and csm is not None:
        want = [norm(w) for w in ([spec["sample"]] if isinstance(spec["sample"], str) else spec["sample"])]
        keep = df[csm].map(lambda v: any(w == norm(v) or (len(w) > 1 and (norm(v).startswith(w) or w.startswith(norm(v)) and len(norm(v)) > 1)) for w in want)); rows = df[keep]
        if rows.empty: book.note(f"sheet '{sheet}': no rows with Sample = {spec['sample']} (it holds: {', '.join(sorted(set(map(str, df[csm].dropna()))))[:120]})")
    x0, x1 = sorted(ax.get_xlim()); size = spec.get("size", st["label_size"]); placed = []
    for _, r in rows.iterrows():
        try: x, y = float(r[cxx]), float(r[cy])
        except Exception: continue
        if not (x0 <= x <= x1) or str(r[cl]).strip() in ("", "nan"): continue
        col = str(r[cc]).strip() if cc is not None and str(r[cc]).strip().startswith("#") else "#000000"
        try: stag = float(r[cs]) if cs is not None else 0.0
        except Exception: stag = 0.0
        try: top = float(r[ct]) if ct is not None else None
        except Exception: top = None
        if top is not None and not math.isfinite(top): top = None
        t = ax.text(x, y, str(r[cl]).strip(), ha="center", va="bottom", fontsize=size, fontweight="bold", color=col, zorder=12, clip_on=True)
        placed.append({"t": t, "x": x, "y": y, "top": top, "leader": stag > 0, "moved": False})
    if not placed: return 0
    fig.canvas.draw(); rend = fig.canvas.get_renderer(); inv = ax.transData.inverted(); ylo, yhi = sorted(ax.get_ylim()); step = 0.045 * (yhi - ylo); boxes = []
    def box(t):
        b = t.get_window_extent(rend); (ax0, ay0), (ax1, ay1) = inv.transform((b.x0, b.y0)), inv.transform((b.x1, b.y1)); return [min(ax0, ax1), min(ay0, ay1), max(ax0, ax1), max(ay0, ay1)]
    moved = 0
    for pl in sorted(placed, key=lambda q: (q["y"], q["x"])):
        b = box(pl["t"])
        for (cxs, cys) in curves:                          # not on a curve: at least a little above the highest point under the text
            m = (cxs >= b[0]) & (cxs <= b[2])
            if m.any():
                hi_ = float(np.nanmax(cys[m]))
                if b[1] < hi_ + 0.008 * (yhi - ylo): d = hi_ + 0.012 * (yhi - ylo) - b[1]; b[1] += d; b[3] += d; pl["moved"] = True
        for _ in range(12):                                # not on another label
            if not any(not (b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3]) for o in boxes): break
            b[1] += step; b[3] += step; pl["moved"] = True
        if pl["moved"]: pl["t"].set_y(b[1]); moved += 1
        boxes.append(b); pl["yy"] = b[1]
        if (pl["leader"] or pl["moved"]) and pl["top"] is not None and b[1] > pl["top"]:
            ax.plot([pl["x"], pl["x"]], [pl["top"], b[1]], color=st["leader"], lw=st["leader_lw"], zorder=11, solid_capstyle="butt")
    if moved: book.note(f"{moved} label(s) from '{sheet}' were moved up to keep them clear of a curve or of another label (same colour, with a leader line).")
    return len(placed)

def _names_left(ax, curves, names, st, size=None):
    """The name of each pattern of a stack at the left of its baseline: names from the top pattern down."""
    import numpy as np
    if not names or not curves: return
    x0, x1 = sorted(ax.get_xlim()); base = []
    for cx, cy in curves:
        m = (cx >= x0) & (cx <= x0 + 0.12 * (x1 - x0)); seg = cy[m] if m.any() else cy
        base.append(float(np.nanpercentile(seg, 20)))
    order = sorted(range(len(curves)), key=lambda i: -base[i]); ylo, yhi = sorted(ax.get_ylim())
    for nm, i in zip(names, order):
        ax.text(x0 + 0.012 * (x1 - x0), base[i] + 0.012 * (yhi - ylo), nm, ha="left", va="bottom", fontsize=size or st["tick_label"] - 1, zorder=13, bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.85))

def _ylim(ax, p, curves):
    import numpy as np
    if p.get("ylim"): ax.set_ylim(*p["ylim"]); return
    x0, x1 = sorted(ax.get_xlim()); tops = [float(np.nanmax(cy[(cx >= x0) & (cx <= x1)])) for cx, cy in curves if ((cx >= x0) & (cx <= x1)).any()]
    if p.get("ymax_factor") and tops:
        lows = [float(np.nanmin(cy[(cx >= x0) & (cx <= x1)])) for cx, cy in curves if ((cx >= x0) & (cx <= x1)).any()]
        lo = 0.0 if p.get("yfrom0", True) else min(lows); ax.set_ylim(min(lo, min(lows)) if min(lows) < 0 else lo, p["ymax_factor"] * max(tops))
    elif p.get("yfrom0") and tops: ax.set_ylim(0, max(tops) * 1.12 if max(tops) > 0 else 1)

def _panel_xy(fig, ax, book, p, recipe, st, drawn):
    if p.get("layout_mode") == "stacked_offset": return _panel_stacked(fig, ax, book, p, recipe, st, drawn)
    _apply_axes(ax, st, {k: p.get(k) for k in ("xlim",)}); curves = []
    for s in p.get("series") or []:
        try: curves += _series(ax, book, s, recipe.get("phases"), drawn, st)
        except Missing as e: book.note(f"{p.get('_fig', '')} {p.get('letter', '')}: {e}")
    _apply_axes(ax, st, p)
    if p.get("xreverse"): pass
    _ylim(ax, p, curves)
    if p.get("shade"): ax.axvspan(p["shade"][0], p["shade"][1], color="#000000", alpha=p.get("shade_alpha", 0.13), lw=0, zorder=0)
    _names_left(ax, curves, p.get("names_left"), st)
    try: _labels(ax, book, p.get("labels"), curves, st, fig)
    except Missing as e: book.note(f"{p.get('_fig', '')} {p.get('letter', '')}: labels not drawn, {e}")
    _letter(ax, p, st)

OKABE_ITO = ["#000000", "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#7F7F7F"]          # safe for colour-blind readers

def draw_stacked(ax, traces, offset_mode="auto_percent", offset_value=None, palette=None, guides=(), xlim=None, label_size=8.0, lw=0.8):
    """Traces one above the other on common axes (a waterfall). traces: [(label, x, y)], the first at the bottom.
    offset_mode "auto_percent": every trace is lifted by offset_value % (default 100) of the tallest trace;
    "fixed_value": by offset_value in the unit of y. The name of each trace stands at its right end, outside the axes; there is no legend box.
    guides: x positions (or (x, text)) of thin vertical lines through all traces, for peaks they share. Returns the step used."""
    import numpy as np
    traces = [(str(l), np.asarray(x, float), np.asarray(y, float)) for l, x, y in traces]
    if not traces: raise Missing("there is no trace to stack")
    if offset_mode not in ("auto_percent", "fixed_value"): raise Missing('offset_mode must be "auto_percent" or "fixed_value"')
    if xlim: traces = [(l, x[(x >= min(xlim)) & (x <= max(xlim))], y[(x >= min(xlim)) & (x <= max(xlim))]) for l, x, y in traces]
    span = max(float(np.nanmax(y) - np.nanmin(y)) for _, _, y in traces if y.size)
    if offset_mode == "fixed_value":
        if offset_value is None: raise Missing('offset_mode "fixed_value" needs offset_value')
        step = float(offset_value)
    else: step = (100.0 if offset_value is None else float(offset_value)) / 100.0 * span
    pal = list(palette or OKABE_ITO); top = 0.0
    for k, (label, x, y) in enumerate(traces):
        if not y.size: continue
        col = pal[k % len(pal)]; yy = y - float(np.nanmin(y)) + k * step; ax.plot(x, yy, color=col, lw=lw, zorder=3 + k); top = max(top, float(np.nanmax(yy)))
        i = int(np.argmax(x)); n = max(1, x.size // 40); base = float(np.nanmedian(yy[np.argsort(x)[-n:]]))
        ax.annotate(label, xy=(float(x[i]), base), xytext=(5, 0), textcoords="offset points", ha="left", va="center", fontsize=label_size, color=col, annotation_clip=False)
    for g in guides or ():
        gx, gt = (g[0], g[1]) if isinstance(g, (list, tuple)) else (g, "")
        ax.axvline(float(gx), color="#9A9A9A", lw=0.4, ls=(0, (4, 3)), zorder=1)
        if gt: ax.annotate(str(gt), xy=(float(gx), 1.0), xycoords=("data", "axes fraction"), xytext=(0, 2), textcoords="offset points", ha="center", va="bottom", fontsize=label_size - 1, color="#555555", annotation_clip=False)
    ax.set_ylim(-0.03 * max(top, 1e-9), top * 1.04 if top > 0 else 1); ax.set_yticks([])
    if xlim: ax.set_xlim(*xlim)
    else: ax.set_xlim(min(float(np.nanmin(x)) for _, x, _ in traces if x.size), max(float(np.nanmax(x)) for _, x, _ in traces if x.size))
    return step

def _panel_stacked(fig, ax, book, p, recipe, st, drawn):
    """A recipe panel with "layout_mode": "stacked_offset": its series become stacked traces."""
    import pandas as pd
    traces = []
    for s in p.get("series") or []:
        try:
            df = book.sheet(s["sheet"]); cx = book.col(df, s.get("x", 0), s["sheet"]); ys = s.get("y", "others")
            cols = [c for c in df.columns if c != cx and pd.to_numeric(df[c], errors="coerce").notna().any()] if ys == "others" else [book.col(df, y, s["sheet"]) for y in (ys if isinstance(ys, list) else [ys])]
            for c in cols:
                d = pd.DataFrame({"x": pd.to_numeric(df[cx], errors="coerce"), "y": pd.to_numeric(df[c], errors="coerce")}).dropna()
                if not d.empty: traces.append((s.get("label") if (s.get("label") and len(cols) == 1) else str(c), d.x.to_numpy(), d.y.to_numpy()))
        except Missing as e: book.note(f"{p.get('_fig', '')} {p.get('letter', '')}: {e}")
    _apply_axes(ax, st, {k: p.get(k) for k in ("xtitle", "ytitle")})
    draw_stacked(ax, traces, p.get("offset_mode", "auto_percent"), p.get("offset_value"), p.get("palette"), p.get("shared_peak_guides") or (), p.get("xlim"), st["tick_label"], p.get("lw", 0.8))
    ax.spines["right"].set_visible(False); ax.spines["top"].set_visible(False); ax.tick_params(top=False, right=False); _letter(ax, p, st)

def _panel_bars(fig, ax, book, p, recipe, st, drawn):
    import numpy as np, pandas as pd
    df = book.sheet(p["sheet"]); n = len(df); bars = p.get("bars") or []; k = len(bars); w = 0.8 / max(1, k); xs = np.arange(n)
    for j, b in enumerate(bars):
        c = book.col(df, b["column"], p["sheet"]); v = pd.to_numeric(df[c], errors="coerce").fillna(0).to_numpy(); xo = xs - 0.4 + w * (j + 0.5)
        ax.bar(xo, v, width=w * 0.94, color=b.get("color", "#595959"), edgecolor="black", linewidth=0.5, hatch=b.get("hatch") or None, zorder=3)
        if p.get("zero_labels", True):
            for xi, vi in zip(xo, v):
                if vi == 0: ax.text(xi, 0, "0", ha="center", va="bottom", fontsize=st["tick_label"] - 1.5, zorder=6)
        drawn.append({"label": b.get("label") or str(c), "color": b.get("color", "#595959"), "kind": "bar", "hatch": b.get("hatch")})
    pt = p.get("points")
    if pt:
        c = book.col(df, pt.get("column", -1), p["sheet"]); v = pd.to_numeric(df[c], errors="coerce")
        ax.plot(xs, v, linestyle="none", marker=pt.get("marker", "D"), ms=pt.get("ms", 5.5), mfc=pt.get("color", "#000000"), mec="white", mew=0.9, zorder=8)
        drawn.append({"label": pt.get("label") or str(c), "color": pt.get("color", "#000000"), "kind": "markers", "marker": pt.get("marker", "D"), "filled": True, "ms": pt.get("ms", 5.5), "mec": "white"})
    cats = p.get("categories") or [str(v) for v in df[book.col(df, p.get("category", 0), p["sheet"])]]
    ax.set_xticks(xs); ax.set_xticklabels(cats[:n]); ax.set_xlim(-0.6, n - 0.4)
    _apply_axes(ax, st, {k_: p.get(k_) for k_ in ("xtitle", "ytitle")}); ax.tick_params(axis="x", length=0)
    if p.get("ylim"): ax.set_ylim(*p["ylim"])
    _letter(ax, p, st)

def _ticks(ax, book, sheet, recipe, st, size=None):
    """Bragg tick rows: the columns come in pairs "<phase> 2θ (°)" and "<phase> row"."""
    import pandas as pd
    df = book.sheet(sheet); rows = []
    for c in df.columns:
        m = re.match(r"^(.*?)[\s_]*row\s*$", str(c), re.I)
        if not m: continue
        name = m.group(1).strip(); xc = next((d for d in df.columns if d != c and norm(d).startswith(norm(name)) and "theta" in norm(d)), None)
        if xc is None: book.note(f"sheet '{sheet}': column '{c}' has no partner '<phase> 2θ (°)'"); continue
        d = pd.DataFrame({"x": pd.to_numeric(df[xc], errors="coerce"), "y": pd.to_numeric(df[c], errors="coerce")}).dropna()
        if not d.empty: rows.append((name, d, phase_of(name, recipe.get("phases")) or {}))
    if not rows: raise Missing(f"sheet '{sheet}' has no pairs of columns '<phase> 2θ (°)' and '<phase> row'")
    pos, labs, cols = [], [], []
    for name, d, ph in rows:
        col = ph.get("color", "#000000"); ax.plot(d.x, d.y, linestyle="none", marker="|", ms=6, mew=0.7, color=col, zorder=3)
        pos.append(float(d.y.iloc[0])); labs.append(ph.get("letter") or name); cols.append(col)
    lo, hi = min(pos), max(pos); pad = 0.6 * ((hi - lo) / max(1, len(pos) - 1) if hi > lo else 1.0); ax.set_ylim(lo - pad, hi + pad)
    top = next((y for (nm, d, ph), y in zip(rows, pos) if ph.get("name", "").lower().startswith("alite")), None)
    if top is not None and top < (lo + hi) / 2: ax.invert_yaxis()            # alite is the top row
    ax.set_yticks(pos); ax.set_yticklabels(labs, fontsize=size or st["tick_label"] - 1.5, fontweight="bold")
    for t, col in zip(ax.get_yticklabels(), cols): t.set_color(col)
    ax.tick_params(axis="y", length=0)

def _block_rietveld(fig, cell, book, p, recipe, st, drawn):
    """One sample: fit (observed circles, calculated line), difference, Bragg tick rows, and the zoomed inset in the fit row."""
    import numpy as np
    hr = p.get("heights", [3.0, 0.85, 0.95]); gs = cell.subgridspec(3, 1, height_ratios=hr, hspace=0.0)
    a1 = fig.add_subplot(gs[0]); a2 = fig.add_subplot(gs[1], sharex=a1); a3 = fig.add_subplot(gs[2], sharex=a1); xl = p.get("xlim", [10, 70]); tag = f"{p.get('_fig', '')} {p.get('letter', '')}"
    for a in (a1, a2, a3): _apply_axes(a, st)
    curves = []
    try:
        x, yo, _ = book.xy(p["profile"], p.get("x", "2theta_deg"), p.get("obs", "Yobs_counts")); a1.plot(x, yo, linestyle="none", marker="o", ms=p.get("obs_ms", 1.6), mfc="none", mec="#000000", mew=0.35, zorder=3); curves.append((x, yo))
        xc, yc, _ = book.xy(p["profile"], p.get("x", "2theta_deg"), p.get("calc", "Ycalc_counts")); a1.plot(xc, yc, color="#CC0000", lw=0.7, zorder=4)
        m = (x >= xl[0]) & (x <= xl[1]); a1.set_ylim(0, p.get("ymax_factor", 1.8) * float(np.nanmax(yo[m] if m.any() else yo)))
        if not any(d["label"] == "Observed" for d in drawn):
            drawn.append({"label": "Observed", "color": "#000000", "kind": "markers", "marker": "o", "filled": False, "ms": 3}); drawn.append({"label": "Calculated", "color": "#CC0000", "kind": "line", "lw": 0.9, "ls": "-"})
    except Missing as e: book.note(f"{tag}: fit not drawn, {e}")
    try:
        xd, yd, _ = book.xy(p["profile"], p.get("x", "2theta_deg"), p.get("diff", "Ydiff_counts")); a2.axhline(0, color="#9A9A9A", lw=0.4, zorder=1); a2.plot(xd, yd, color="#555555", lw=0.5, zorder=3)
        if not any(d["label"] == "Difference" for d in drawn): drawn.append({"label": "Difference", "color": "#555555", "kind": "line", "lw": 0.8, "ls": "-"})
    except Missing as e: book.note(f"{tag}: difference not drawn, {e}")
    try: _ticks(a3, book, p["ticks"], recipe, st, p.get("tick_letter_size"))
    except Missing as e: book.note(f"{tag}: tick rows not drawn, {e}")
    a1.set_xlim(*xl)
    if p.get("shade"): a1.axvspan(p["shade"][0], p["shade"][1], color="#000000", alpha=0.13, lw=0, zorder=0)
    from matplotlib.ticker import MaxNLocator
    a1.tick_params(labelbottom=False); a2.tick_params(labelbottom=False); a2.tick_params(axis="y", labelsize=st["tick_label"] - 1.5)
    a1.yaxis.set_major_locator(MaxNLocator(nbins=6, prune="lower")); a2.yaxis.set_major_locator(MaxNLocator(nbins=2, prune="both", symmetric=True))       # the numbers of two rows never run into each other
    if p.get("ytitle") is not None: a1.set_ylabel(p["ytitle"], fontsize=st["axis_title"])
    if p.get("diff_title", "Diff.") and p.get("ytitle") is not None: a2.set_ylabel(p.get("diff_title", "Diff."), fontsize=st["tick_label"])
    if p.get("xtitle") is not None: a3.set_xlabel(p["xtitle"], fontsize=st["axis_title"])
    else: a3.tick_params(labelbottom=bool(p.get("xnumbers", True)))
    if p.get("title"): a1.set_title(((str(p.get("letter")) + " ") if p.get("letter") else "") + str(p["title"]), fontsize=st["axis_title"], loc="left", fontweight="bold", pad=3, linespacing=1.15)
    if p.get("zoom"):
        r = p.get("inset", [0.60, 0.50, 0.38, 0.46]); ins = a1.inset_axes(r); _apply_axes(ins, st); ins.tick_params(labelsize=st["tick_label"] - 1.5, length=2); zs = p["zoom"]; zr = p.get("zoom_xlim", [31, 35])
        try:
            zx, zo, _ = book.xy(zs, p.get("zoom_x", 0), {"contains": "observed"}); ins.plot(zx, zo, linestyle="none", marker="o", ms=1.8, mfc="none", mec="#000000", mew=0.35, zorder=3)
            zx2, zc, _ = book.xy(zs, p.get("zoom_x", 0), {"contains": "calculated"}); ins.plot(zx2, zc, color="#CC0000", lw=0.7, zorder=4)
            try: zx3, zd, _ = book.xy(zs, p.get("zoom_x", 0), {"contains": "difference"}); ins.plot(zx3, zd, color="#555555", lw=0.5, zorder=2)
            except Missing as e: book.note(f"{tag}: inset without difference, {e}")
        except Missing as e: book.note(f"{tag}: inset not drawn, {e}")
        ins.set_xlim(*zr); ins.set_yticklabels([]); ins.tick_params(axis="y", labelleft=False)
        ins.text(0.5, 0.97, p.get("zoom_text", "Zoom of shaded region"), transform=ins.transAxes, ha="center", va="top", fontsize=st["tick_label"] - 2)
    if p.get("labels"):
        try: _labels(a1, book, p["labels"], curves, st, fig)
        except Missing as e: book.note(f"{tag}: labels not drawn, {e}")
    if p.get("legend_in_panel"):
        h = _handles([d for d in drawn if d["label"] in ("Observed", "Calculated")]); a1.legend(handles=h, loc="upper left", fontsize=st["legend"], frameon=False, handlelength=1.6, borderaxespad=0.6)
    return a1

def _handles(items):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    out = []
    for d in items:
        k = d.get("kind", "line")
        if k in ("bar", "square"): out.append(Patch(facecolor=d["color"], edgecolor="black" if k == "bar" else d["color"], linewidth=0.5 if k == "bar" else 0, hatch=d.get("hatch") or None, label=d["label"]))
        elif k == "markers": out.append(Line2D([], [], linestyle="none", marker=d.get("marker", "o"), ms=max(3.5, d.get("ms", 4)), mfc=d["color"] if d.get("filled", True) else "none", mec=d.get("mec", d["color"]), mew=0.7, label=d["label"]))
        elif k == "line+markers": out.append(Line2D([], [], color=d["color"], lw=d.get("lw", 1), linestyle=d.get("ls", "-"), marker=d.get("marker", "o"), ms=4, mfc=d["color"] if d.get("filled", True) else "white", mec=d["color"], label=d["label"]))
        else: out.append(Line2D([], [], color=d["color"], lw=d.get("lw", 1), linestyle=d.get("ls", "-"), label=d["label"]))
    return out

def _legend_items(book, leg, recipe, drawn):
    """The entries of a legend: listed ones (colour from the phase table or from a label sheet), or everything that was drawn."""
    items = leg.get("items")
    if not items:
        seen, out = set(), []
        for d in drawn:
            if d["label"] not in seen: seen.add(d["label"]); out.append(d)
        return out
    colmap = {}
    if leg.get("colors_from_labels"):
        for sh in ([leg["colors_from_labels"]] if isinstance(leg["colors_from_labels"], str) else leg["colors_from_labels"]):
            try:
                df = book.sheet(sh); cl = book.col(df, "Label", sh); cc = book.col(df, {"contains": "colour"}, sh, optional=True) or book.col(df, {"contains": "color"}, sh)
                for _, r in df.iterrows():
                    for part in re.split(r"[+/,\s()\[\]]+", str(r[cl])):
                        if part and part not in colmap and str(r[cc]).startswith("#"): colmap[part] = str(r[cc]).strip()
            except Missing as e: book.note(f"legend colours: {e}")
    out = []
    for it in items:
        if "code" in it:
            ph = next((p for p in recipe.get("phases") or [] if p.get("letter") == it["code"]), None); col = it.get("color") or colmap.get(it["code"]) or (ph or {}).get("color")
            if not col: col = "#000000"; book.note(f"legend: no colour found for '{it['code']}' (black used)")
            out.append({"label": f"{it['code']} {it.get('text', '')}".strip(), "color": col, "kind": "square"})
        else: out.append(next((d for d in drawn if d["label"] == it.get("label")), {"label": it.get("label", ""), "color": it.get("color", "#000000"), "kind": it.get("kind", "line"), "hatch": it.get("hatch"), "ls": it.get("ls", "-"), "marker": it.get("marker", "o"), "filled": it.get("filled", True), "lw": it.get("lw", 1)}))
    return out


# ---------------------------------------------------------------------------------------------- one figure
def draw_figure(f, book, recipe):
    """Draw one figure of a recipe. Returns the matplotlib Figure."""
    import matplotlib
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    st = _style(recipe); st.update(f.get("style") or {})
    with matplotlib.rc_context({"font.family": "sans-serif", "font.sans-serif": [st["font"], "Arial", "Liberation Sans", "DejaVu Sans"], "pdf.fonttype": 42, "svg.fonttype": "none", "hatch.linewidth": 0.5, "axes.unicode_minus": True, "mathtext.default": "regular"}):
        W = f.get("width_mm", 175) * MM; H = f.get("height_mm", 120) * MM
        fig = Figure(figsize=(W, H), facecolor="white"); FigureCanvasAgg(fig)
        lay = f.get("layout") or {}; rows = lay.get("rows", [1]); cols = lay.get("cols", [1]); leg = f.get("legend") or {}; below = leg.get("where", "below") == "below" and bool(leg)
        nlines = (leg.get("rows", 1) if below else 0) + (1.2 if f.get("note") else 0)
        bottom = (lay.get("bottom_mm", 11) + 4.6 * nlines) * MM / H
        gs = fig.add_gridspec(len(rows), len(cols), height_ratios=rows, width_ratios=cols, left=lay.get("left_mm", 15) * MM / W, right=1 - lay.get("right_mm", 4) * MM / W, top=1 - lay.get("top_mm", 6) * MM / H, bottom=bottom,
                              hspace=lay.get("hspace", 0.0 if lay.get("sharex") else 0.34), wspace=lay.get("wspace", 0.22))
        drawn = []; first = None; legend_cell = None
        for p in f.get("panels") or []:
            p = dict(p); p["_fig"] = f.get("name", ""); r, c = p.get("cell", [0, 0]); kind = p.get("type", "xy")
            try:
                if kind == "legend": legend_cell = (gs[r, c], p); continue
                if kind == "rietveld": _block_rietveld(fig, gs[r, c], book, p, recipe, st, drawn); continue
                ax = fig.add_subplot(gs[r, c], sharex=first if (lay.get("sharex") and first is not None) else None); first = first or ax
                (_panel_bars if kind == "bars" else _panel_xy)(fig, ax, book, p, recipe, st, drawn)
                if lay.get("sharex") and r < len(rows) - 1: ax.tick_params(labelbottom=False); ax.set_xlabel("")
            except Missing as e: book.note(f"{f.get('name', '')} {p.get('letter', '')}: not drawn, {e}")
        if legend_cell:
            cell, p = legend_cell; ax = fig.add_subplot(cell); ax.axis("off"); it = _legend_items(book, p.get("legend") or leg, recipe, drawn)
            if it: ax.legend(handles=_handles(it), loc="upper left", fontsize=st["legend"], frameon=False, handlelength=2.6, borderaxespad=0.2, labelspacing=0.55)
            if p.get("note"): ax.text(0.02, 0.02, p["note"], transform=ax.transAxes, ha="left", va="bottom", fontsize=st["legend"] - 0.5, color="#333333", linespacing=1.3)
        elif below:
            it = _legend_items(book, leg, recipe, drawn)
            if it:
                ncol = leg.get("ncol") or math.ceil(len(it) / max(1, leg.get("rows", 1)))
                fig.legend(handles=_handles(it), loc="lower center", bbox_to_anchor=(0.5, (1.6 + (5.2 if f.get("note") else 0)) * MM / H), ncol=ncol, fontsize=st["legend"], frameon=False, handlelength=1.1 if all(d.get("kind") == "square" for d in it) else 2.2, handleheight=0.9, columnspacing=1.0, handletextpad=0.4, borderaxespad=0)
        if f.get("note"): fig.text(0.5, 1.6 * MM / H, f["note"], ha="center", va="bottom", fontsize=st["legend"] - 0.5, color="#333333")
        if f.get("ytitle"): fig.text(2.2 * MM / W, (bottom + 1 - lay.get("top_mm", 6) * MM / H) / 2, f["ytitle"], rotation=90, ha="left", va="center", fontsize=st["axis_title"])
        if f.get("xtitle"): fig.text(0.5, bottom - 8.2 * MM / H, f["xtitle"], ha="center", va="top", fontsize=st["axis_title"])
        fig._pf_rc = {"font.family": "sans-serif", "font.sans-serif": [st["font"], "Arial", "Liberation Sans", "DejaVu Sans"], "pdf.fonttype": 42, "hatch.linewidth": 0.5}; fig._pf_dpi = st["dpi"]
        fig.canvas.draw()
    return fig

CONFIRMED_ACTIONS = []          # the assistant actions the user confirmed in this session; written into the provenance of the figures that follow

def _sha256(path):
    import hashlib
    try:
        with open(path, "rb") as f: return hashlib.sha256(f.read()).hexdigest()
    except Exception: return None

def write_provenance(base, facts, app_version=""):
    """<base>_provenance.json next to a figure: when, which version, which input files (SHA-256), which settings. Never a key, never data rows."""
    import datetime
    d = {"written": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "app": "Origin Plot Studio", "app_version": app_version}
    d.update(facts); p = base + "_provenance.json"
    with open(p, "w", encoding="utf-8") as f: json.dump(d, f, indent=1, ensure_ascii=False, default=str)
    return p

FIG_SIZE = (11.7, 6.5)          # landscape, the size of the preview figure
FIG_FONT = ["Arial", "Liberation Sans", "DejaVu Sans"]
FIG_PT = {"axis_title": 13, "tick_label": 11, "label": 10}

def _figure():
    import matplotlib
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    rc = {"font.family": "sans-serif", "font.sans-serif": FIG_FONT, "pdf.fonttype": 42, "axes.unicode_minus": True, "mathtext.default": "regular", "hatch.linewidth": 0.5}
    return matplotlib, Figure, FigureCanvasAgg, rc

def _plain_axes(ax, lw=0.9):
    for s_ in ax.spines.values(): s_.set_linewidth(lw)
    ax.tick_params(direction="in", width=lw, length=4, labelsize=FIG_PT["tick_label"]); ax.grid(False); ax.set_facecolor("white")

def _save_figure(fig, rc, base, dpi=300):
    import matplotlib
    out = []
    with matplotlib.rc_context(rc):
        for ext in ("png", "pdf"): fig.savefig(f"{base}.{ext}", dpi=dpi if ext == "png" else None, facecolor="white"); out.append(f"{base}.{ext}")
    return out

def stacked_figure(traces, base, offset_mode="auto_percent", offset_value=None, palette=None, shared_peak_guides=(), xtitle="2\u03b8 (\u00b0)", ytitle="Intensity (offset)", xlim=None, facts=None, app_version=""):
    """Several patterns stacked with a vertical offset, in one landscape figure. Writes PNG, PDF and the provenance file. Returns the files."""
    matplotlib, Figure, Canvas, rc = _figure()
    with matplotlib.rc_context(rc):
        fig = Figure(figsize=FIG_SIZE, facecolor="white"); Canvas(fig); ax = fig.add_axes([0.07, 0.13, 0.76, 0.82]); _plain_axes(ax)
        step = draw_stacked(ax, traces, offset_mode, offset_value, palette, shared_peak_guides, xlim, FIG_PT["label"], 0.9)
        ax.spines["right"].set_visible(False); ax.spines["top"].set_visible(False); ax.set_xlabel(xtitle, fontsize=FIG_PT["axis_title"]); ax.set_ylabel(ytitle, fontsize=FIG_PT["axis_title"])
    files = _save_figure(fig, rc, base)
    d = {"what": "stacked patterns (waterfall)", "layout_mode": "stacked_offset", "offset_mode": offset_mode, "offset_value": offset_value, "offset_step_used": step, "palette": list(palette or OKABE_ITO), "shared_peak_guides": [list(g) if isinstance(g, (list, tuple)) else g for g in shared_peak_guides or ()],
         "traces": [t[0] for t in traces], "confirmed_assistant_actions": list(CONFIRMED_ACTIONS)}; d.update(facts or {})
    return files + [write_provenance(base, d, app_version)]

def read_phase_amounts(path):
    """Phase amounts as in phase_amounts_template.csv: columns Sample, Phase, Code, wt%. Returns [{"sample", "phase", "code", "wt"}]."""
    import csv
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f); cols = {norm(c): c for c in rd.fieldnames or []}
        need = [k for k in ("sample", "phase") if k not in cols] + ([] if any(k in cols for k in ("wt", "wtpct", "wtpercent", "amount")) else ["wt%"])
        if need: raise Missing(f"the phase-amounts file needs the columns Sample, Phase, Code, wt% (missing: {', '.join(need)})")
        wc = next(cols[k] for k in ("wt", "wtpct", "wtpercent", "amount") if k in cols)
        for r in rd:
            try: w = float(str(r[wc]).replace(",", "."))
            except (TypeError, ValueError): continue
            if str(r[cols["sample"]]).strip(): rows.append({"sample": str(r[cols["sample"]]).strip(), "phase": str(r[cols["phase"]]).strip(), "code": str(r.get(cols.get("code", ""), "") or "").strip(), "wt": w})
    if not rows: raise Missing("the phase-amounts file holds no rows with a sample and a number")
    return rows

def rietveld_two_panel(x, yobs, ycalc, ticks, amounts, base, title=None, phases=None, samples=None, facts=None, app_version=""):
    """Panel A: observed (circles), calculated (line) and their difference drawn below them with an offset, with tick rows of the phases.
    Panel B: stacked bars of the phase amounts (rows of read_phase_amounts) for the samples. One landscape figure; names stand at the bars, not in a box."""
    import numpy as np
    matplotlib, Figure, Canvas, rc = _figure(); x, yobs, ycalc = np.asarray(x, float), np.asarray(yobs, float), np.asarray(ycalc, float)
    if not (x.size == yobs.size == ycalc.size and x.size > 2): raise Missing("observed and calculated patterns need the same number of points")
    table = phases or []; pal = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#8C564B", "#7F7F7F", "#A6761D", "#9467BD", "#000000"]
    def colour(name, k): return (phase_of(name, table) or {}).get("color") or pal[k % len(pal)]
    with matplotlib.rc_context(rc):
        fig = Figure(figsize=FIG_SIZE, facecolor="white"); Canvas(fig); gs = fig.add_gridspec(1, 2, width_ratios=[2.3, 1], left=0.075, right=0.90, top=0.92, bottom=0.20, wspace=0.26)
        a = fig.add_subplot(gs[0]); b = fig.add_subplot(gs[1]); _plain_axes(a); _plain_axes(b)
        top = float(np.nanmax(yobs)); diff = yobs - ycalc; dspan = float(np.nanmax(diff) - np.nanmin(diff)) or 1.0; names = list(ticks or {}); row_h = 0.045 * top
        d0 = -0.06 * top - float(np.nanmax(diff)); tick0 = d0 + float(np.nanmin(diff)) - 0.05 * top               # the difference sits under the pattern, the tick rows under the difference
        a.plot(x, yobs, ls="none", marker="o", ms=2.2, mfc="none", mec="#000000", mew=0.4, zorder=3); a.plot(x, ycalc, color="#CC0000", lw=1.0, zorder=4); a.plot(x, diff + d0, color="#555555", lw=0.7, zorder=2)
        a.axhline(d0, color="#BBBBBB", lw=0.4, zorder=1)
        for k, nm in enumerate(names):
            y_ = tick0 - k * row_h; pos = np.asarray(ticks[nm], float); col = colour(nm, k)
            a.plot(pos, np.full(pos.size, y_), ls="none", marker="|", ms=7, mew=0.8, color=col, zorder=3)
            a.annotate((phase_of(nm, table) or {}).get("letter") or nm, xy=(1.0, y_), xycoords=("axes fraction", "data"), xytext=(4, 0), textcoords="offset points", ha="left", va="center", fontsize=FIG_PT["label"] - 1, color=col, fontweight="bold", annotation_clip=False)
        a.set_xlim(float(x.min()), float(x.max())); a.set_ylim(tick0 - (len(names) + 0.3) * row_h, top * 1.10); a.set_xlabel("2\u03b8 (\u00b0)", fontsize=FIG_PT["axis_title"]); a.set_ylabel("Intensity (counts)", fontsize=FIG_PT["axis_title"])
        ip = int(np.argmax(yobs)); a.annotate("Observed", xy=(x[ip], yobs[ip]), xytext=(14, -2), textcoords="offset points", fontsize=FIG_PT["label"], color="#000000", va="top")
        a.annotate("Calculated", xy=(x[ip], yobs[ip]), xytext=(14, -16), textcoords="offset points", fontsize=FIG_PT["label"], color="#CC0000", va="top")
        a.annotate("Difference", xy=(float(x.min()), d0), xytext=(6, 5), textcoords="offset points", fontsize=FIG_PT["label"], color="#555555", va="bottom")
        a.set_title(("(a) " + title) if title else "(a)", loc="left", fontsize=FIG_PT["axis_title"], fontweight="bold", pad=6)
        order = samples or list(dict.fromkeys(r["sample"] for r in amounts)); kinds = list(dict.fromkeys((r["code"] or r["phase"]) for r in amounts if r["sample"] in order)); bottoms = np.zeros(len(order)); ends = []
        for k, ph in enumerate(kinds):
            v = np.array([sum(r["wt"] for r in amounts if r["sample"] == s_ and (r["code"] or r["phase"]) == ph) for s_ in order]); col = colour(next((r["phase"] for r in amounts if (r["code"] or r["phase"]) == ph), ph), k)
            b.bar(np.arange(len(order)), v, bottom=bottoms, width=0.62, color=col, edgecolor="white", linewidth=0.6, zorder=3)
            for i, (vi, bi) in enumerate(zip(v, bottoms)):
                if vi >= 5: b.text(i, bi + vi / 2, f"{vi:.0f}", ha="center", va="center", fontsize=FIG_PT["label"] - 1, color="white", zorder=5)
            if v[-1] > 0: ends.append((bottoms[-1] + v[-1] / 2, ph, col))
            bottoms = bottoms + v
        gap = 4.0; last = None                                  # names at the last bar, pushed apart so they never overlap
        for yy, ph, col in sorted(ends):
            yy2 = yy if last is None or yy - last >= gap else last + gap; last = yy2
            b.annotate(ph, xy=(len(order) - 1 + 0.31, yy), xytext=(6, 0), textcoords="offset points", ha="left", va="center", fontsize=FIG_PT["label"] - 1, color=col, fontweight="bold", annotation_clip=False) if yy2 == yy else b.annotate(ph, xy=(len(order) - 1 + 0.31, yy), xytext=(6, (yy2 - yy) * 4), textcoords="offset points", ha="left", va="center", fontsize=FIG_PT["label"] - 1, color=col, fontweight="bold", annotation_clip=False)
        b.set_xticks(np.arange(len(order))); b.set_xticklabels(order, rotation=30 if max(len(s_) for s_ in order) > 6 else 0, ha="right" if max(len(s_) for s_ in order) > 6 else "center"); b.set_xlim(-0.6, len(order) - 0.4); b.set_ylim(0, max(100.0, float(bottoms.max()) * 1.02))
        b.set_ylabel("Phase content (wt.%)", fontsize=FIG_PT["axis_title"]); b.spines["top"].set_visible(False); b.spines["right"].set_visible(False); b.tick_params(axis="x", length=0); b.set_title("(b) Phase amounts", loc="left", fontsize=FIG_PT["axis_title"], fontweight="bold", pad=6)
    files = _save_figure(fig, rc, base)
    d = {"what": "Rietveld fit with phase amounts (two panels)", "phases_ticked": names, "phase_library_entries": [{"letter": p_.get("letter"), "name": p_.get("name")} for p_ in table], "samples": order, "phase_amounts": amounts, "confirmed_assistant_actions": list(CONFIRMED_ACTIONS)}; d.update(facts or {})
    return files + [write_provenance(base, d, app_version)]

def save_spec_figure(spec, base, facts=None, app_version="", curve_w=1.5, axis_w=1.5):
    """A figure spec of the app (for example a TGA graph: TG on the left axis, DTG on the right) as a landscape PNG and PDF with its provenance file."""
    import smart_plots as sp
    matplotlib, Figure, Canvas, rc = _figure()
    with matplotlib.rc_context(rc):
        fig = Figure(figsize=FIG_SIZE, dpi=100, facecolor="white"); Canvas(fig); sp.preview_figure(spec, fig, curve_w, axis_w, keep_aspect=False)
    files = _save_figure(fig, rc, base); d = {"confirmed_assistant_actions": list(CONFIRMED_ACTIONS)}; d.update(facts or {})
    return files + [write_provenance(base, d, app_version)]

def run(workbook, recipe, outdir, only=None, log=None, stop=None, formats=("pdf", "png"), app_version=""):
    """Draw the figures of a recipe from a workbook into outdir. Returns {"files": [...], "notes": [...], "figures": [...], "text": summary}."""
    import matplotlib
    say = log or (lambda m: None); book = Book(load_sheets(workbook)); os.makedirs(outdir, exist_ok=True); files, done, failed = [], [], []
    want = [norm(o) for o in (only or [])]
    for f in recipe.get("figures") or []:
        nm = f.get("name", "Figure"); fn = f.get("file") or re.sub(r"[^A-Za-z0-9_-]+", "_", nm)
        if want and not any(w and (w == norm(nm) or w in norm(nm) or w in norm(fn)) for w in want): continue
        if stop and stop(): break
        try:
            fig = draw_figure(f, book, recipe)
            with matplotlib.rc_context(fig._pf_rc):
                for ext in formats:
                    p = os.path.join(outdir, fn + "." + ext); fig.savefig(p, dpi=fig._pf_dpi if ext != "pdf" else None, facecolor="white"); files.append(p)
            try: write_provenance(os.path.join(outdir, fn), {"what": "composed paper figure", "figure": nm, "recipe": recipe.get("title", ""), "recipe_configuration": f, "inputs": [{"file": os.path.basename(workbook), "sha256": _sha256(workbook)}],
                                                            "phase_library_entries": [{"letter": ph.get("letter"), "name": ph.get("name"), "color": ph.get("color")} for ph in recipe.get("phases") or []],
                                                            "label_sheets": sorted({(q.get("labels") or {}).get("sheet") for q in f.get("panels") or [] if (q.get("labels") or {}).get("sheet")}), "notes": list(book.notes), "confirmed_assistant_actions": list(CONFIRMED_ACTIONS)}, app_version)
            except Exception: pass
            done.append(nm); say(f"{nm}: saved as {fn}.pdf and {fn}.png (600 dpi)")
        except Exception as e:
            failed.append(nm); book.note(f"{nm}: NOT drawn ({type(e).__name__}: {e})"); say(f"!! {nm} could not be drawn: {type(e).__name__}: {e}")
    text = f"{len(done)} figure(s) drawn" + (f", {len(failed)} not drawn ({', '.join(failed)})" if failed else "") + (f"; {len(book.notes)} note(s)" if book.notes else "")
    try:
        with open(os.path.join(outdir, "figures_report.txt"), "w", encoding="utf-8") as fh:
            fh.write(f"Workbook: {workbook}\nRecipe: {recipe.get('title', '')}\n{text}\nNo number of the workbook was changed and no sheet was sorted: the sheets are only read.\n\n" + ("Notes (what was missing or moved):\n" + "\n".join("- " + n for n in book.notes) if book.notes else "Everything the recipe asks for was found."))
    except Exception: pass
    return {"files": files, "notes": list(book.notes), "figures": done, "failed": failed, "text": text, "folder": outdir}

SPEC_DOC = ('A figure = {"name","file","width_mm","height_mm","layout":{"rows":[ratios],"cols":[ratios],"sharex":bool},"panels":[...],"legend":{"where":"below","rows":1,"items":[{"label":..}]},"note":".."}. '
            'Panel "type":"xy": {"cell":[row,col],"letter":"(a)","title","xtitle","ytitle","xlim","ylim","xticks","xreverse","yfrom0","series":[{"sheet","x":column,"y":column|[columns]|"others","kind":"line|markers|line+markers","color":"#hex","lw","ls":"-|--|:","marker":"o|s|^|D","filled":bool,"label","optional":bool}]}. '
            'Panel "type":"bars" (grouped bars, one group per row of the sheet): {"cell","sheet","categories":[names],"bars":[{"column","color","hatch":"/|\\\\|x","label"}],"points":{"column","label"},"xtitle","ytitle","ylim"}. '
            'A column is its exact name, {"contains":"text"} or a position (0 = first, -1 = last).')


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3: print("use: python paper_figures.py <workbook.xlsx> <recipe name or .json> [output folder] [FigA FigB ...]"); sys.exit(1)
    res = run(sys.argv[1], load_recipe(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "Paper_figures"), only=sys.argv[4:] or None, log=print)
    print(res["text"]); print("\n".join("- " + n for n in res["notes"]))

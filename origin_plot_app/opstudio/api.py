"""What the app calls: the list of templates and styles, drawing a template from the user's tables, the recommender,
the variant switches that work on every template, and the user's own templates (.opst)."""
import copy, io, json, os, re, zipfile
import numpy as np
from . import core, data
from .core import REGISTRY
from .data import NeedData, Table, read_tables

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STYLE = "house_style_1"
USER_DIRS = []                 # folders with the user's own templates (templates/*.json) and styles (styles/*.json)
SWITCHES = {                   # the variant switches of every template: key -> (label, kind)
    "logx": ("Log x axis", "bool"), "logy": ("Log y axis", "bool"), "revx": ("Reverse x axis", "bool"), "revy": ("Reverse y axis", "bool"),
    "markers": ("Markers on lines", "bool"), "normalise": ("Normalise each series to its maximum", "bool"),
    "offset": ("Offset between series (fraction of the range)", "float"), "grid": ("Grid lines", "bool"),
    "legend_off": ("Hide the legend", "bool"), "hatch": ("Hatched bars", "bool"), "top_axis": ("Second x axis on top (d-spacing for 2θ, 1000/T for T)", "choice:none|d-spacing|1000/T"),
    "xmin": ("x from", "float?"), "xmax": ("x to", "float?"), "ymin": ("y from", "float?"), "ymax": ("y to", "float?")}


class Unfit(Exception):
    """The ticked data cannot be drawn in this template; the message says why, in plain words."""


def add_user_dir(folder):
    if folder and folder not in USER_DIRS and os.path.isdir(folder):
        USER_DIRS.append(folder); s = os.path.join(folder, "styles")
        if os.path.isdir(s) and s not in core.STYLE_DIRS: core.STYLE_DIRS.append(s)


def styles():
    """[(id, name, where)] - built-in first, then the user's own (a private one with the same id replaces the built-in one)."""
    out = {}
    for d in core.STYLE_DIRS:
        try: names = sorted(os.listdir(d))
        except OSError: continue
        for f in names:
            if f.endswith(".json"):
                try: j = json.load(open(os.path.join(d, f), encoding="utf-8"))
                except Exception: continue
                out[j.get("id") or f[:-5]] = (j.get("id") or f[:-5], j.get("name") or f[:-5], "built in" if d == core.STYLE_DIR else "yours")
    return list(out.values())


def default_style(preferred=None):
    ids = [s[0] for s in styles()]
    return preferred if preferred in ids else DEFAULT_STYLE


def user_templates():
    """The user's own templates: {id: json}. A user template is a built-in template (its 'base') with saved parameters,
    switches, style and texts."""
    out = {}
    for d in USER_DIRS:
        td = os.path.join(d, "templates")
        try: names = sorted(os.listdir(td))
        except OSError: continue
        for f in names:
            if f.endswith(".json"):
                try: j = json.load(open(os.path.join(td, f), encoding="utf-8"))
                except Exception: continue
                if j.get("base") in REGISTRY: j["_dir"] = d; out[j["id"]] = j
    return out


def info(tid):
    """The opstudio.template/1 description of a template (built in or the user's)."""
    if tid in REGISTRY:
        j = core.template_json(REGISTRY[tid]); j["preview"] = os.path.join(HERE, "previews", tid + ".png")
        o = os.path.join(HERE, "origin", tid + ".ogs"); j["origin_template"] = {"script": o if os.path.isfile(o) else "", "otpu": tid + ".otpu"}
        return j
    u = user_templates().get(tid)
    if u is None: raise KeyError(tid)
    j = dict(info(u["base"])); j.update({k: v for k, v in u.items() if not k.startswith("_")}); j["source"] = "mine"
    j["preview"] = os.path.join(u["_dir"], "previews", tid + ".png"); return j


def all_templates():
    return [info(t) for t in REGISTRY] + [info(t) for t in user_templates()]


def resolve(tid):
    """(base template, params, switches, style or None, overrides) of a built-in or user template id."""
    if tid in REGISTRY: return REGISTRY[tid], {}, {}, None, {}
    u = user_templates().get(tid)
    if u is None: raise Unfit(f"template '{tid}' is not installed")
    return REGISTRY[u["base"]], dict(u.get("params") or {}), dict(u.get("switches") or {}), u.get("style"), dict(u.get("overrides") or {})


# ------------------------------------------------------------------------------------------------ drawing
def _pre(b, sw):
    """Switches that change the numbers that are drawn (never the file): normalise and offset of series."""
    if not (sw.get("normalise") or sw.get("offset")): return b
    b = copy.copy(b)
    def fix(series):
        out = []; off = 0.0
        for s in series:
            s = dict(s); y = np.asarray(s["y"], dtype=float)
            if sw.get("normalise"):
                m = np.nanmax(np.abs(y)) if np.isfinite(y).any() else 0
                if m: y = y / m
            if sw.get("offset"):
                y = y + off; off += float(sw["offset"]) * (np.nanmax(y) - np.nanmin(y) if np.isfinite(y).any() else 1.0)
            s["y"] = y; out.append(s)
        return out
    if isinstance(b.get("series"), list) and b["series"] and "y" in b["series"][0]: b["series"] = fix(b["series"])
    if isinstance(b.get("panels"), list): b["panels"] = [dict(p, series=fix(p["series"])) for p in b["panels"]]
    return b


def _post(fig, sw, st):
    for ax in fig.axes:
        if getattr(ax, "name", "") in ("polar", "3d"): continue
        try:
            if sw.get("logx"): ax.set_xscale("log")
            if sw.get("logy"): ax.set_yscale("log")
            if sw.get("revx") and not ax.xaxis_inverted(): ax.invert_xaxis()
            if sw.get("revy") and not ax.yaxis_inverted(): ax.invert_yaxis()
            if sw.get("xmin") is not None or sw.get("xmax") is not None: ax.set_xlim(sw.get("xmin"), sw.get("xmax"))
            if sw.get("ymin") is not None or sw.get("ymax") is not None: ax.set_ylim(sw.get("ymin"), sw.get("ymax"))
            if "grid" in sw: ax.grid(bool(sw["grid"]), lw=0.4, alpha=0.5)
            if sw.get("legend_off") and ax.get_legend(): ax.get_legend().remove()
            if "markers" in sw:
                for i, ln in enumerate(ax.get_lines()):
                    if len(ln.get_xdata()) > 2 and ln.get_linestyle() not in ("None", "none", ""):
                        ln.set_marker("osD^vP*X"[i % 8] if sw["markers"] else "None"); ln.set_markersize(st["lines"]["marker_size_pt"]); ln.set_markerfacecolor("white")
                        if sw["markers"]: ln.set_markevery(max(1, len(ln.get_xdata()) // 25))
            if sw.get("hatch"):
                hs = ["///", "\\\\\\", "xxx", "...", "+++", "ooo"]
                for i, c in enumerate(ax.containers):
                    for r in getattr(c, "patches", []): r.set_hatch(hs[i % len(hs)]); r.set_edgecolor("k")
        except Exception: pass
    top = sw.get("top_axis")
    if top in ("d-spacing", "1000/T") and fig.axes:
        ax = fig.axes[0]
        try:
            if top == "d-spacing":
                lam = float(sw.get("wavelength") or 1.5406)
                f = lambda tt: lam / (2 * np.sin(np.radians(np.clip(np.asarray(tt, dtype=float), 0.5, 179) / 2)))
                g = lambda dd: 2 * np.degrees(np.arcsin(np.clip(lam / (2 * np.clip(np.asarray(dd, dtype=float), 1e-6, None)), -1, 1)))
                sec = ax.secondary_xaxis("top", functions=(f, g)); sec.set_xlabel("d (Å)")
            else:
                f = lambda T: 1000.0 / (np.asarray(T, dtype=float) + 273.15); g = lambda u: 1000.0 / np.clip(np.asarray(u, dtype=float), 1e-9, None) - 273.15
                sec = ax.secondary_xaxis("top", functions=(f, g)); sec.set_xlabel("1000/T (K$^{-1}$)")
        except Exception: pass


def draw(tid, tables, style=None, params=None, switches=None, overrides=None, illustrative=False, width=None, target=None):
    """The figure of template `tid` from the user's tables, in a style. Returns (figure, mapping). Raises Unfit."""
    t, p0, s0, st0, o0 = resolve(tid)
    p = dict(p0); p.update(params or {}); sw = dict(s0); sw.update(switches or {}); ov = dict(o0); ov.update(overrides or {})
    style = style or st0 or DEFAULT_STYLE
    try: b, mp = data.bundle(t, tables, ov)
    except NeedData as e: raise Unfit(str(e))
    try: st = core.load_style(style)
    except FileNotFoundError: raise Unfit(f"style '{style}' is not installed")
    import matplotlib, warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fig = core.render(t.id, _pre(b, sw), st, p, illustrative_mark=illustrative, width=width, target=target)
            if sw:
                with matplotlib.rc_context():
                    core.apply_style(st); _post(fig, sw, st)
                    if target is None: fig.canvas.draw()
    except Exception as e:
        raise Unfit(f"this data does not fit the template ({type(e).__name__}: {str(e)[:120]}). It needs: " + "; ".join(f"{k} = {v}" for k, v in t.roles.items()))
    if target is not None: return fig, mp
    fig._ops = {"template": tid, "style": style, "params": p, "switches": sw, "mapping": mp}
    fig._redraw = lambda width_: draw(tid, tables, style, params, switches, overrides, illustrative, width_)[0]
    return fig, mp


def demo_figure(tid, style=None):
    t = resolve(tid)[0]
    return core.render(t.id, t.demo(), core.load_style(style or DEFAULT_STYLE), illustrative_mark=True)


def png(fig, width_px=520):
    buf = io.BytesIO(); w = fig.get_size_inches()[0]
    core.save(fig, buf, dpi=max(40, width_px / w), format="png"); return buf.getvalue()


def export(fig, path, width="double", dpi=None, transparent=False):
    """Save at a size of the style: width 'single' / '1.5' / 'double' (mm from the style) or a number in mm. The graph is
    drawn again at that width (texts keep the point size of the style; nothing is scaled). Returns the warnings."""
    st = getattr(fig, "_ops_style", None) or core.load_style(DEFAULT_STYLE)
    w = width if isinstance(width, str) and width in st["figure"]["width_mm"] else float(width)
    f2 = fig._redraw(w) if hasattr(fig, "_redraw") else fig
    warn = min_size_warnings(f2, st)
    kw = {"transparent": transparent}
    if path.lower().endswith((".tif", ".tiff")): kw["pil_kwargs"] = {"compression": "tiff_lzw"}
    core.save(f2, path, dpi=dpi, exact=True, **kw)
    return warn


def min_size_warnings(fig, st, scale=1.0):
    """Texts and lines that fall below the minimum of the style at the final size (the export dialog shows them)."""
    lim = st.get("limits") or {}; mf = lim.get("min_font_pt"); ml = lim.get("min_line_pt"); out = []
    import matplotlib.text as mt
    if mf:
        small = sorted({round(t.get_fontsize() * scale, 1) for t in fig.findobj(mt.Text) if t.get_text().strip() and t.get_visible() and t.get_fontsize() * scale < mf - 0.05})
        if small: out.append(f"text of {small[0]:g} pt is below the {mf:g} pt minimum of '{st.get('name', st.get('id'))}'")
    if ml:
        thin = sorted({round(l.get_linewidth() * scale, 2) for ax in fig.axes for l in ax.get_lines() if l.get_visible() and l.get_linestyle() not in ("None", "none", "") and 0 < l.get_linewidth() * scale < ml - 0.01})
        if thin: out.append(f"lines of {thin[0]:g} pt are below the {ml:g} pt minimum of '{st.get('name', st.get('id'))}'")
    return out


# ------------------------------------------------------------------------------------------------ recommender
RULES = [  # (pattern on the headers, data kinds / template ids / categories that fit, why)
    (r"2\s*(θ|theta|th)\b|two.?theta|d.?spacing", ("xrd",), "a 2θ column: diffraction"),
    (r"temp.*\b|°c|\(k\)", ("tga", "tg_", "dsc", "dta", "thermal"), "temperature"),
    (r"mass|weight|\btg\b", ("tga", "tg_"), "temperature and mass: thermogravimetry"),
    (r"\bmw\b|heat ?flow|j/g|w/g", ("calorimetry", "heatflow", "dsc"), "time and heat flow: calorimetry"),
    (r"µm|um\b|micron|particle size|diameter", ("psd", "rrsb", "mip"), "a size in µm: particle or pore size"),
    (r"cm.?-?1|wavenumber|raman shift", ("ftir", "raman"), "wavenumbers: FTIR / Raman"),
    (r"shear rate|1/s|s-1|viscosity|shear stress", ("rheo",), "shear rate: rheology"),
    (r"potential|voltage|\be\b.*\bv\b", ("cv_", "tafel", "eis"), "potential and current: voltammetry"),
    (r"z'|zre|zim|z''|impedance", ("eis",), "Z' and Z'': impedance"),
    (r"dose|concentration.*response|ec50|ic50", ("dose_response",), "dose and response"),
    (r"event|censor|survival", ("kaplan",), "time and event: survival"),
    (r"conc|standard|signal|absorbance|peak area", ("calibration",), "concentration and signal: calibration"),
    (r"frequency|\bhz\b|\btime\b.*\b(s|ms)\b", ("fft", "time_series"), "a signal over time or frequency"),
    (r"\bsource\b.*\btarget\b|\btarget\b.*\bsource\b|\bfrom\b.*\bto\b|\bto\b.*\bfrom\b", ("sankey",), "source / target / value: flows"),
    (r"strength|mpa", ("strength", "abrams", "stress"), "strength values"),
    (r"depth", ("depth_profile", "chloride", "carbonation"), "a depth column")]


def recommend(tables, top=None):
    """Templates ranked for these tables: [(id, score, why)]. A template scores when the file can fill it; headers and
    units add to it. Nothing is labelled or drawn here."""
    if not tables: return []
    t = tables[0]; head = " | ".join(t.cols).lower(); out = []
    hits = [(set(keys), why) for pat, keys, why in RULES if re.search(pat, head)]
    tern = len(t.numeric) >= 3 and np.allclose(np.nansum(np.column_stack([t.arr(c) for c in t.numeric[:3]]), axis=1), 100, atol=1.5)
    for tid, tp in REGISTRY.items():
        try: data.bundle(tp, tables)
        except NeedData: continue
        except Exception: continue
        score, why = 1.0, []
        for keys, w in hits:
            if any(k in tid for k in keys): score += 3; why.append(w)
        if tern and "ternary" in tid: score += 4; why.append("three columns that sum to 100: ternary")
        if tp.data_kind == "category_table" and t.cat: score += 1.5; why.append("a column of names and value columns")
        if tp.data_kind == "xy_series" and t.cat is None and len(t.numeric) >= 2: score += 0.5
        if tp.data_kind in ("table", "matrix") and len(t.numeric) >= 5 and tid in ("pca_biplot", "correlation_heatmap"): score += 2; why.append("many numeric columns: statistics")
        if len(tables) > 1 and ("panel" in tid or "grid" in tid or "stack" in tid): score += 1; why.append("several files")
        out.append((tid, score, "; ".join(dict.fromkeys(why)) or "the columns fit"))
    out.sort(key=lambda x: (-x[1], x[0]))
    return out[:top] if top else out


# ------------------------------------------------------------------------------------------------ the user's own templates
def save_user_template(folder, tid, name, base, style=None, params=None, switches=None, overrides=None, preview_png=None, note=""):
    """Write templates/<id>.json (+ previews/<id>.png) into the user's folder. Returns the path of the JSON."""
    tid = re.sub(r"[^a-z0-9_]+", "_", tid.lower()).strip("_") or "my_template"
    b = REGISTRY[base] if base in REGISTRY else resolve(base)[0]
    j = {"schema": "opstudio.template/1", "id": tid, "name": name, "base": b.id, "category": "My templates", "use_case": note or b.use_case, "source": "mine",
         "style": style, "params": _plain(params or {}), "switches": _plain(switches or {}), "overrides": _plain(overrides or {}),
         "origin_template": {"script": f"origin/{tid}.ogs", "otpu": f"origin/{tid}.otpu"}}
    os.makedirs(os.path.join(folder, "templates"), exist_ok=True); os.makedirs(os.path.join(folder, "previews"), exist_ok=True)
    p = os.path.join(folder, "templates", tid + ".json"); json.dump(j, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if preview_png: open(os.path.join(folder, "previews", tid + ".png"), "wb").write(preview_png)
    add_user_dir(folder); return p


def _plain(v):
    if isinstance(v, dict): return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [_plain(x) for x in v]
    if isinstance(v, np.ndarray): return v.tolist()
    if isinstance(v, (np.floating, np.integer)): return v.item()
    return v


def export_opst(folder, tid, path):
    """One file to share a template: a zip of its JSON, its preview and its Origin script / template when present."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in (f"templates/{tid}.json", f"previews/{tid}.png", f"origin/{tid}.ogs", f"origin/{tid}.otpu"):
            f = os.path.join(folder, rel)
            if os.path.isfile(f): z.write(f, rel)
    return path


def import_opst(path, folder):
    """Unpack a .opst into the user's folder (only the four kinds of files, no other paths). Returns the template id."""
    tid = None
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            m = re.fullmatch(r"(templates|previews|origin)/([a-z0-9_]+)\.(json|png|ogs|otpu)", n)
            if not m: continue
            os.makedirs(os.path.join(folder, m.group(1)), exist_ok=True)
            open(os.path.join(folder, n), "wb").write(z.read(n))
            if m.group(1) == "templates": tid = m.group(2)
    if tid is None: raise Unfit("this file holds no template")
    add_user_dir(folder); return tid


def combine(draw_fns, rows, cols, style=None, share_x=False, labels=True):
    """One landscape figure of rows x cols cells. Each draw_fn(cell) draws one graph into its cell (a matplotlib SubFigure),
    e.g. lambda cell: draw(tid, tables, style, target=cell). Panel letters (a), (b) ... in the format of the style."""
    import matplotlib, warnings
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    st = core.load_style(style or DEFAULT_STYLE) if not isinstance(style, dict) else style
    n = len(draw_fns); rows, cols = max(1, int(rows)), max(1, int(cols))
    if rows * cols < n: rows = -(-n // cols)
    W = st["figure"]["width_mm"].get("double", 190) / 25.4; H = W / cols / st["figure"]["aspect_w_h"] * rows
    if H > W * 0.98: H = W * 0.98                                     # landscape is the rule
    fig = Figure(figsize=(W, H), layout="constrained"); FigureCanvasAgg(fig); cells = fig.subfigures(rows, cols, squeeze=False, wspace=0.03, hspace=0.05)
    fmt = st.get("panel_label", {}).get("format", "(a)"); pt = st["font"]["size_pt"]["panel_label"]; errors = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for i, fn in enumerate(draw_fns):
            r, c = divmod(i, cols); cell = cells[r][c]
            try: fn(cell)
            except Exception as e:
                errors.append(f"panel {i + 1}: {e}"); cell.text(0.5, 0.5, str(e)[:160], ha="center", va="center", wrap=True, fontsize=6); continue
            if share_x and r < rows - 1 and i + cols < n:
                for ax in cell.axes: ax.tick_params(labelbottom=False); ax.set_xlabel("")
            if labels:
                ch = "abcdefghijklmnopqrstuvwxyz"[i % 26]
                with matplotlib.rc_context():
                    core.apply_style(st); cell.suptitle(ch if fmt == "a" else f"({ch})", x=0.01, ha="left", fontsize=pt + 1, fontweight="bold")      # the layout keeps room for it
        with matplotlib.rc_context():
            core.apply_style(st); fig.canvas.draw()
    fig._ops_style = st; fig._ops_errors = errors
    return fig

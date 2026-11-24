"""
opstudio_core.py  -  reference style engine for Origin Plot Studio templates.

This is a REFERENCE IMPLEMENTATION (matplotlib) that shows how a template = style + layout + data roles
can be applied to any uploaded data. The app may use its own renderer and Origin; the JSON files are the
contract, this code is the worked example. See ../README_template_library.md.

Key ideas
---------
* STYLE (styles/*.json)  : fonts, sizes, tick direction, palette, export settings. Independent of graph type.
* TEMPLATE (templates/*.json + a draw function): layout, axes, decorations, data roles, default params.
* DATA BUNDLE            : plain dict produced by an adapter from the user's file (see adapters below).
Any template can be combined with any style -> multi-select previews = cartesian product (data x template x style).
"""
from __future__ import annotations
import json, math, os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any
import numpy as np
import matplotlib
import matplotlib.pyplot as plt          # only for rcParams, colour maps and locators: figures are plain Figure objects
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.ticker import AutoMinorLocator

HERE = os.path.dirname(os.path.abspath(__file__))
STYLE_DIR = os.path.join(HERE, "styles")
STYLE_DIRS = [STYLE_DIR]          # the app adds the user's own folders (private styles win over built-in ones)
MM = 1 / 25.4


# --------------------------------------------------------------------------------------------- styles
def load_style(style_id: str = "house_style_1") -> dict:
    for d in reversed(STYLE_DIRS):
        p = os.path.join(d, style_id + ".json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(f"style '{style_id}' not found")


CURRENT = {"panel_label_format": "(a)", "width": None, "target": None}


def apply_style(st: dict) -> None:
    CURRENT["panel_label_format"] = st.get("panel_label", {}).get("format", "(a)")
    fs = st["font"]["size_pt"]
    ax = st["axes"]
    plt.rcdefaults()
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": st["font"]["family"],
        "font.size": fs["base"],
        "axes.labelsize": fs["axis_label"],
        "axes.titlesize": fs["panel_label"],
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "xtick.labelsize": fs["tick"],
        "ytick.labelsize": fs["tick"],
        "legend.fontsize": fs["legend"],
        "legend.frameon": st["legend"]["frame"],
        "legend.handlelength": st["legend"]["handle_length"],
        "axes.linewidth": ax["linewidth_pt"],
        "xtick.direction": ax["tick_direction"],
        "ytick.direction": ax["tick_direction"],
        "xtick.top": ax["ticks_all_sides"],
        "ytick.right": ax["ticks_all_sides"],
        "xtick.major.size": ax["major_tick_len_pt"],
        "ytick.major.size": ax["major_tick_len_pt"],
        "xtick.minor.size": ax["minor_tick_len_pt"],
        "ytick.minor.size": ax["minor_tick_len_pt"],
        "xtick.major.width": ax["linewidth_pt"],
        "ytick.major.width": ax["linewidth_pt"],
        "lines.linewidth": st["lines"]["width_pt"],
        "lines.markersize": st["lines"]["marker_size_pt"],
        "axes.grid": ax["grid"],
        "axes.prop_cycle": plt.cycler(color=st["palette"]["series"]),
        "mathtext.default": "regular",
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
        "figure.dpi": 150,
    })


def fig_size(st: dict, width: str | float = "double", aspect: float | None = None):
    w = st["figure"]["width_mm"]
    if CURRENT.get("width") is not None: width = CURRENT["width"]      # the export size chosen by the user: the graph is drawn at that width
    wmm = w.get(width, w.get("double", 190)) if isinstance(width, str) else float(width)
    a = aspect or st["figure"]["aspect_w_h"]
    if a < 1:  # landscape is a user rule: never return portrait
        a = 1 / a
    return (wmm * MM, wmm * MM / a)


def new_fig(st, nrows=1, ncols=1, width="double", aspect=None, **kw):
    fig = make_fig(fig_size(st, width, aspect))
    axs = fig.subplots(nrows, ncols, **kw)
    return fig, axs


def make_fig(figsize):
    """A figure of its own (not a pyplot figure: nothing global, nothing to close)."""
    if CURRENT.get("target") is not None: return CURRENT["target"]      # a cell of a combined figure: the template draws straight into it
    fig = Figure(figsize=figsize); FigureCanvasAgg(fig)
    return fig


def finish(ax, st, minor=True):
    if minor and st["axes"]["minor_ticks"]:
        if ax.get_xscale() == "linear":
            ax.xaxis.set_minor_locator(AutoMinorLocator())
        if ax.get_yscale() == "linear":
            ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.tick_params(which="both", direction=st["axes"]["tick_direction"],
                   top=st["axes"]["ticks_all_sides"], right=st["axes"]["ticks_all_sides"])


def panel_title(ax, letter_idx: int | None, title: str = "", st=None):
    ch = "abcdefghijklmnopqrstuvwxyz"[letter_idx] if letter_idx is not None else ""
    lab = (ch if CURRENT["panel_label_format"] == "a" else f"({ch})") if ch else ""
    ax.set_title((lab + " " + title).strip(), loc="left", fontweight="bold", pad=3)


def series_color(st, name: str, i: int):
    for key, col in st["palette"]["samples"].items():
        if name == key or name.startswith(key + " ") or name.startswith(key + ","):
            return col
    for key, col in st["palette"]["phases"].items():
        if name.lower().startswith(key.lower()):
            return col
    pal = st["palette"]["series"]
    return pal[i % len(pal)]


def distinct_colors(st, names, start=1):
    """Named colours where known (samples/phases), otherwise the next unused palette colour - never two equal colours."""
    pal = st["palette"]["series"]; used, out = set(), []
    for i, n in enumerate(names):
        c = series_color(st, n, i + start)
        if c in used:
            c = next((q for q in pal[start:] + pal[:start] if q not in used), c)
        used.add(c); out.append(c)
    return out


def illustrative(fig, text="Illustrative example - synthetic data"):
    fig.text(0.995, 0.003, text, ha="right", va="bottom", fontsize=5.5, color="#9AA5B1")


# --------------------------------------------------------------------------------------------- registry
@dataclass
class Template:
    id: str
    name: str
    category: str
    use_case: str
    data_kind: str
    roles: Dict[str, str]
    draw: Callable
    demo: Callable
    params: Dict[str, Any] = field(default_factory=dict)
    origin_hint: str = ""
    source: str = "generic"           # 'house' when it reproduces a house figure
    recommended_for: List[str] = field(default_factory=list)
    calculations: List[str] = field(default_factory=list)


REGISTRY: Dict[str, Template] = {}


def template(id, name, category, use_case, data_kind, roles, demo, params=None, origin_hint="",
             source="generic", recommended_for=None, calculations=None):
    def deco(fn):
        REGISTRY[id] = Template(id, name, category, use_case, data_kind, roles, fn, demo, params or {},
                                origin_hint, source, recommended_for or [], calculations or [])
        return fn
    return deco


def render(template_id: str, data: dict, style_id="house_style_1", params=None, illustrative_mark=False, width=None, target=None):
    t = REGISTRY[template_id]
    st = load_style(style_id) if isinstance(style_id, str) else style_id
    with matplotlib.rc_context():          # the style never leaks into the other figures of the app
        apply_style(st)
        p = dict(t.params); p.update(params or {})
        CURRENT["width"] = width; CURRENT["target"] = target
        try: fig = t.draw(data, st, p)
        finally: CURRENT["width"] = None; CURRENT["target"] = None
        if illustrative_mark:
            illustrative(fig)
        if target is None: fig.canvas.draw()   # texts and ticks are laid out while the style is active
    fig._ops_style = st
    return fig


def save(fig, path, dpi=None, exact=False, **kw):
    """Save in the style of the figure. exact=True: the file has exactly the size of the figure (journal widths);
    otherwise the white margin is trimmed (previews)."""
    st = getattr(fig, "_ops_style", None)
    with matplotlib.rc_context():
        if st: apply_style(st)
        if exact:
            plt.rcParams["savefig.bbox"] = None
            if not getattr(fig, "_ops_tight", False):
                try:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore"); fig.tight_layout(pad=0.5)
                except Exception: pass
                fig._ops_tight = True
        fig.savefig(path, dpi=dpi or (st or {}).get("export", {}).get("raster_dpi", 300), **kw)
    return path


def template_json(t: Template) -> dict:
    return {"schema": "opstudio.template/1", "id": t.id, "name": t.name, "category": t.category,
            "use_case": t.use_case, "source": t.source, "data_kind": t.data_kind, "data_roles": t.roles,
            "default_params": t.params, "origin_hint": t.origin_hint,
            "recommended_for": t.recommended_for, "calculations": t.calculations,
            "preview": f"previews/{t.id}.png", "orientation": "landscape",
            "styles": "any (styles/*.json)", "label_policy": "labels/peak names only from user files or user confirmation"}


# --------------------------------------------------------------------------------------------- adapters
def _num(df):
    import pandas as pd
    return df.apply(pd.to_numeric, errors="coerce")


def adapt(df, kind: str, **meta) -> dict:
    """Turn a plain table (row 1 headers, col 1 = x/category) into a data bundle for `kind`.
    The app must SHOW this mapping to the user and let them change it before drawing."""
    cols = list(df.columns)
    if kind == "xy_series":
        x = _num(df[cols[0]]).to_numpy()
        return {"x_label": str(cols[0]), "y_label": meta.get("y_label", ""),
                "series": [{"name": str(c), "x": x, "y": _num(df[c]).to_numpy()} for c in cols[1:]]}
    if kind == "category_table":
        vals = _num(df[cols[1:]]).to_numpy()
        return {"categories": [str(v) for v in df[cols[0]]], "groups": [str(c) for c in cols[1:]],
                "values": vals, "x_label": str(cols[0]), "y_label": meta.get("y_label", "")}
    if kind == "rietveld":
        d = _num(df)
        return {"x": d[cols[0]].to_numpy(), "obs": d[cols[1]].to_numpy(), "calc": d[cols[2]].to_numpy(),
                "diff": d[cols[3]].to_numpy() if len(cols) > 3 else d[cols[1]].to_numpy() - d[cols[2]].to_numpy(),
                "name": meta.get("name", ""), "rwp": meta.get("rwp"), "ticks": meta.get("ticks", {})}
    if kind == "thermal":
        d = _num(df)
        T = d[cols[0]].to_numpy()
        return {"samples": [{"name": meta.get("name", str(cols[1])), "T": T, "mass": d[cols[1]].to_numpy()}],
                "zones": meta.get("zones", [])}
    raise ValueError(kind)


def short_name(header: str) -> str:
    """'Sample A (offset, counts)' -> 'Sample A'. Never invents text, only trims unit tails."""
    h = header
    for tail in [" (offset, counts)", " (counts)", " (wt.%)", " (wt%)"]:
        if h.endswith(tail):
            h = h[: -len(tail)]
    return h

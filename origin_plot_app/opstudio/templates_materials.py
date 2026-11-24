"""
opstudio_templates.py - graph template library (reference implementation).
Every template registers: id, name, category, use case, data kind, data roles, a demo-data function and a
draw(data, style, params) function. Draw functions never invent labels: every text comes from `data`
(user file / user confirmation) or `params` (user-editable).
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
from matplotlib.lines import Line2D
from .core import (template, new_fig, finish, panel_title, series_color, fig_size, MM, distinct_colors, make_fig)
from . import synthetic as S

CAT_XRD = "XRD & Rietveld"
CAT_PHASE = "Phase & chemical composition"
CAT_TH = "Thermal analysis (TGA / DTG / DSC)"
CAT_CAL = "Isothermal calorimetry"
CAT_PSD = "Particle size, porosity & surface"
CAT_SPEC = "Spectroscopy (FTIR / Raman / NMR)"
CAT_THERMO = "Thermodynamic modelling"
CAT_ENG = "Cement & concrete engineering"
CAT_MICRO = "Microstructure & SEM-EDS"
CAT_SUS = "Sustainability & CO2"
CAT_GEN = "General scientific & statistics"


def _legend(ax, **kw):
    kw.setdefault("loc", "best")
    ax.legend(**kw)


def _xy_lines(ax, data, st, markers=False, ls_cycle=False):
    mk = ["o", "s", "^", "D", "v", "P", "X", "h"]
    lss = ["-", "--", ":", "-."]
    for i, s in enumerate(data["series"]):
        kw = dict(color=s.get("color") or series_color(st, s["name"], i), label=s["name"])
        if markers:
            kw.update(marker=mk[i % len(mk)], markerfacecolor="white" if i else kw["color"], markeredgewidth=0.9)
        if ls_cycle:
            kw.update(ls=lss[i % len(lss)])
        if s.get("yerr") is not None:
            ax.errorbar(s["x"], s["y"], yerr=s["yerr"], capsize=2.5, **kw)
        else:
            ax.plot(s["x"], s["y"], **kw)


# ================================================================================================ XRD
def demo_xrd_single():
    x, y = S.xrd_pattern(1)
    return {"x_label": "2θ (°), Cu Kα", "y_label": "Intensity (counts)", "series": [{"name": "Sample B", "x": x, "y": y}],
            "labels": [{"x": p, "text": ph} for ph, ps in S.XRD_PHASES.items() for p in ps[:2]],
            "key": {"A": "Alite", "B": "Belite", "C": "Aluminate", "F": "Ferrite", "R": "Rutile (std)", "P": "Periclase"}}


@template("xrd_single_labeled", "XRD pattern with phase labels", CAT_XRD,
          "One diffractogram; phase letters above confirmed peaks; letter key below the graph.", "xy_series",
          {"x": "2θ column", "y": "intensity column", "labels": "peak list from user's HighScore file (x, phase)"},
          demo_xrd_single, {"label_offset_frac": 0.04, "show_key": True},
          "Origin: Line plot; labels via Text objects at peak x; key as legend text block.", "generic", ["XRD"])
def draw_xrd_single(d, st, p):
    fig, ax = new_fig(st)
    s = d["series"][0]
    ax.plot(s["x"], s["y"], color="k", lw=0.8)
    ymax = np.nanmax(s["y"])
    for lab in [q for q in d.get("labels", []) if s["x"].min() <= q["x"] <= s["x"].max()]:
        i = np.argmin(abs(s["x"] - lab["x"]))
        y0 = np.nanmax(s["y"][max(0, i - 8): i + 8])
        ax.text(lab["x"], y0 + p["label_offset_frac"] * ymax, lab["text"], ha="center", va="bottom", fontsize=7,
                color=series_color(st, d.get("key", {}).get(lab["text"], ""), 0) if d.get("key") else "k", fontweight="bold")
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.set_xlim(s["x"].min(), s["x"].max())
    ax.set_ylim(0, ymax * 1.15)
    if p["show_key"] and d.get("key"):
        key = "   ".join(f"{k}, {v}" for k, v in d["key"].items())
        fig.text(0.5, -0.02, key, ha="center", va="top", fontsize=7)
    finish(ax, st)
    return fig


def demo_stack():
    ser = []
    for i, n in enumerate(S.SAMPLES):
        x, y = S.xrd_pattern(i, scale=1 - 0.1 * i)
        ser.append({"name": n, "x": x, "y": y})
    return {"x_label": "2θ (°), Cu Kα", "y_label": "Intensity (counts, offset)", "series": ser}


@template("xrd_stacked_offset", "Stacked XRD patterns (offset)", CAT_XRD,
          "Compare several samples; constant or auto offset; sample name at the right of each trace.", "xy_series",
          {"x": "2θ", "series": "one Y column per sample"}, demo_stack,
          {"offset": "auto", "already_offset": False, "name_position": "right", "color_by_sample": False},
          "Origin: Stacked Lines by Y Offsets (Plot > Multi-Curve > Stacked Lines by Y Offsets).", "house",
          ["XRD", "FTIR", "Raman"])
def draw_xrd_stacked(d, st, p):
    fig, ax = new_fig(st)
    _stack(ax, d, st, p)
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.set_yticks([])
    finish(ax, st)
    return fig


def _stack(ax, d, st, p, names=True):
    ser = d["series"]
    off = 0.0
    step = 0 if p.get("already_offset") else (np.nanmax([np.nanmax(s["y"]) - np.nanmin(s["y"]) for s in ser]) * 0.75
                                               if p.get("offset", "auto") == "auto" else float(p["offset"]))
    for i, s in enumerate(ser):
        col = series_color(st, s["name"], i) if p.get("color_by_sample") else "#222222"
        y = s["y"] + off
        ax.plot(s["x"], y, color=col, lw=0.7)
        if names:  # label sits just above the flat left part of its own trace
            left = y[: max(5, int(0.12 * len(y)))]
            span = np.nanmax([np.nanmax(q["y"]) for q in ser]) - np.nanmin([np.nanmin(q["y"]) for q in ser]) + step * len(ser)
            ax.text(s["x"].min() + 0.01 * np.ptp(s["x"]), np.nanpercentile(left, 95) + 0.012 * span, s["name"], fontsize=7, va="bottom")
        off += step
    ax.set_xlim(np.nanmin(ser[0]["x"]), np.nanmax(ser[0]["x"]))


@template("xrd_stack_with_zoom", "Stacked XRD + zoom panel", CAT_XRD,
          "Full range stack (a) next to a zoom of a diagnostic window (b), e.g. 31-35° for C3S/C2S.", "xy_series",
          {"x": "2θ", "series": "one Y column per sample"}, demo_stack,
          {"show_zoom": True, "zoom": [31.0, 35.0], "width_ratio": [3, 1], "already_offset": False},
          "Origin: two layers (Graph > Merge or Layer Management) sharing Y offset; second layer rescaled X.",
          "house", ["XRD"])
def draw_xrd_stack_zoom(d, st, p):
    z0, z1 = sorted(p["zoom"]) if p.get("zoom") else (0, 0)
    has = z1 > z0 and any(np.any((np.asarray(s["x"]) >= z0) & (np.asarray(s["x"]) <= z1)) for s in d["series"])
    if not p.get("show_zoom", True) or not has:            # zoom unticked (or no data in the window): the full-range stack alone
        fig, a = new_fig(st); _stack(a, d, st, p); a.set_yticks([]); a.set_xlabel(d["x_label"]); a.set_ylabel(d["y_label"]); finish(a, st)
        return fig
    fig, (a, b) = new_fig(st, 1, 2, gridspec_kw={"width_ratios": p["width_ratio"], "wspace": 0.04})
    _stack(a, d, st, p)
    dz = {"series": [{**s, "x": s["x"][(s["x"] >= z0) & (s["x"] <= z1)], "y": s["y"][(s["x"] >= z0) & (s["x"] <= z1)]}
                     for s in d["series"]]}
    _stack(b, dz, st, {**p, "offset": "auto"}, names=False)
    a.axvspan(z0, z1, color="#DDDDDD", alpha=0.5, lw=0)
    for ax, t in ((a, 0), (b, 1)):
        ax.set_yticks([]); ax.set_xlabel(d["x_label"]); finish(ax, st); panel_title(ax, t, "")
    a.set_ylabel(d["y_label"])
    return fig


def demo_three_panels():
    ser = []
    for i, n in enumerate(["Material 1", "Material 2", "Material 3"]):
        x, y = S.xrd_pattern(10 + i, scale=1.5)
        ser.append({"name": n, "x": x, "y": y})
    return {"x_label": "2θ (°), Cu Kα", "y_label": "Counts", "series": ser}


@template("xrd_multi_panel_shared_x", "XRD panels sharing one x axis", CAT_XRD,
          "Raw materials or very different intensities: one panel per pattern, own y scale, one shared x label.",
          "xy_series", {"x": "2θ", "series": "one Y column per panel"}, demo_three_panels, {"hspace": 0.08},
          "Origin: Plot > Multi-Panel > Stack (shared X, independent Y).", "house", ["XRD"])
def draw_xrd_multi(d, st, p):
    n = len(d["series"])
    fig, axs = new_fig(st, n, 1, sharex=True, gridspec_kw={"hspace": p["hspace"]}, aspect=1.35)
    for i, (ax, s) in enumerate(zip(np.atleast_1d(axs), d["series"])):
        ax.plot(s["x"], s["y"], color="k", lw=0.7)
        ax.text(0.01, 0.92, f"({'abcdefgh'[i]}) {s['name']}", transform=ax.transAxes, fontweight="bold", va="top", fontsize=7.5)
        ax.set_ylabel(d["y_label"]); finish(ax, st)
    np.atleast_1d(axs)[-1].set_xlabel(d["x_label"])
    return fig


def demo_rietveld(seed=3, name="Sample B"):
    x, obs = S.xrd_pattern(seed, x=np.linspace(10, 70, 3000), noise=6)
    from scipy.signal import savgol_filter
    calc = savgol_filter(obs, 9, 3) * 0.985
    ticks = {k: v for k, v in S.XRD_PHASES.items()}
    return {"x": x, "obs": obs, "calc": calc, "diff": obs - calc, "name": name, "rwp": 9.5, "ticks": ticks,
            "x_label": "2θ (°), Cu Kα", "y_label": "Intensity (counts)"}


@template("rietveld_fit_diff_ticks", "Rietveld fit: observed / calculated / difference / Bragg ticks", CAT_XRD,
          "Publication Rietveld plot with Rwp in title, shaded zoom window and inset, tick rows per phase.",
          "rietveld", {"x": "2θ", "obs": "observed", "calc": "calculated", "diff": "difference (optional)",
                       "ticks": "reflection list per phase (from refinement output)"},
          demo_rietveld, {"zoom": [31, 35], "inset": True, "obs_marker": "o"},
          "Origin: 3 stacked layers (fit, difference, ticks) + inset layer; ticks as '|' scatter.", "house",
          ["XRD Rietveld", "GSAS-II", "HighScore"])
def draw_rietveld(d, st, p):
    fig = make_fig(fig_size(st, "double", 1.75))
    has_ticks = bool(d.get("ticks"))  # no reflection list in the file -> no empty tick panel
    gs = fig.add_gridspec(3 if has_ticks else 2, 1, height_ratios=[4, 1, 1.1] if has_ticks else [4, 1], hspace=0.06)
    a = fig.add_subplot(gs[0]); b = fig.add_subplot(gs[1], sharex=a); c = fig.add_subplot(gs[2], sharex=a) if has_ticks else b
    a.plot(d["x"], d["obs"], ls="none", marker="o", ms=1.6, mfc="none", mec="#555555", mew=0.4, label="Observed")
    a.plot(d["x"], d["calc"], color="#C0141E", lw=0.8, label="Calculated")
    z0, z1 = sorted(p["zoom"]) if p.get("zoom") else (0, 0); x_ = np.asarray(d["x"], float)
    zoom_on = bool(p.get("inset")) and z1 > z0 and np.any((x_ >= z0) & (x_ <= z1))      # unticked, or no data in the window: no band and no inset
    if zoom_on: a.axvspan(z0, z1, color="#DDDDDD", alpha=0.6, lw=0)
    ttl = d.get("name", "") + (f", $R_{{wp}}$ = {d['rwp']:.2f} %" if d.get("rwp") else "")
    panel_title(a, 0, ttl); a.set_ylabel(d.get("y_label", "Intensity (counts)")); a.legend(loc="upper left", bbox_to_anchor=(0, 0.9))
    if zoom_on:
        ins = a.inset_axes([0.6, 0.55, 0.38, 0.4])
        m = (d["x"] >= z0) & (d["x"] <= z1)
        ins.plot(d["x"][m], d["obs"][m], "o", ms=1.5, mfc="none", mec="#555555", mew=0.4)
        ins.plot(d["x"][m], d["calc"][m], color="#C0141E", lw=0.8)
        ins.plot(d["x"][m], d["diff"][m] - abs(d["diff"]).max() * 1.2, color="#444444", lw=0.5)
        ins.set_yticks([]); ins.tick_params(labelsize=6); ins.set_title("Zoom of shaded region", fontsize=6, loc="left", fontweight="normal")
    b.plot(d["x"], d["diff"], color="#444444", lw=0.5); b.axhline(0, color="#999999", lw=0.4); b.set_ylabel("Diff.")
    for i, (ph, pos) in enumerate((d.get("ticks") or {}).items()):
        c.plot(pos, [-i] * len(pos), "|", ms=6, color=series_color(st, {"A": "Alite", "B": "Belite", "C": "Aluminate",
               "F": "Ferrite", "P": "Periclase", "R": "Rutile"}.get(ph, ph), i))
    if has_ticks:
        c.set_yticks(range(0, -len(d["ticks"]), -1)); c.set_yticklabels(list(d["ticks"].keys()), fontsize=6)
        c.set_ylim(-len(d["ticks"]) + 0.3, 0.7)
    c.set_xlabel(d.get("x_label", "2θ (°)")); c.set_xlim(d["x"].min(), d["x"].max())
    for ax in ((a, b) if has_ticks else (a,)):
        plt.setp(ax.get_xticklabels(), visible=False)
    for ax in {a, b, c}:
        finish(ax, st)
    return fig


@template("rietveld_grid_2x3", "Rietveld fits as small multiples (2 x 3)", CAT_XRD,
          "All six refinements on one page with identical axes; each tile = fit + diff + ticks.", "rietveld",
          {"items": "list of rietveld bundles (one per file)"}, lambda: {"items": [demo_rietveld(i, n) for i, n in
                                                                                   enumerate(S.SAMPLES)]},
          {"ncols": 3}, "Origin: Graph > Merge Graph Windows (3 columns) from six fit graphs.", "house", ["XRD Rietveld"])
def draw_rietveld_grid(d, st, p):
    items = d["items"]; nc = p["ncols"]; nr = int(np.ceil(len(items) / nc))
    fig = make_fig(fig_size(st, "double", 1.5))
    outer = fig.add_gridspec(nr, nc, hspace=0.35, wspace=0.25)
    for k, it in enumerate(items):
        g = outer[k // nc, k % nc].subgridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
        a = fig.add_subplot(g[0]); b = fig.add_subplot(g[1], sharex=a)
        a.plot(it["x"], it["obs"], ".", ms=0.8, color="#777777"); a.plot(it["x"], it["calc"], color="#C0141E", lw=0.5)
        b.plot(it["x"], it["diff"], color="#444444", lw=0.3)
        a.set_title(f"({'abcdefghij'[k]}) {it['name']}", fontsize=6.5, loc="left")
        plt.setp(a.get_xticklabels(), visible=False)
        for ax in (a, b):
            ax.tick_params(labelsize=5.5); finish(ax, st)
        if k // nc == nr - 1:
            b.set_xlabel("2θ (°), Cu Kα", fontsize=6.5)
    return fig


def demo_insitu():
    temps = np.arange(25, 1400, 100)
    ser = []
    for i, T in enumerate(temps):
        x, y = S.xrd_pattern(20 + i, scale=0.6 + i / len(temps))
        ser.append({"name": f"{T} °C", "x": x, "y": y})
    return {"x_label": "2θ (°), Cu Kα", "y_label": "Intensity (a.u.)", "series": ser, "z_label": "Temperature (°C)"}


@template("xrd_waterfall_3d", "Waterfall (pseudo-3D) for in-situ / temperature series", CAT_XRD,
          "In-situ heating, hydration time series or a dosage series: traces shifted in x and y.", "xy_series",
          {"x": "2θ", "series": "one column per temperature / time"}, demo_insitu, {"dx": 0.6, "dy_frac": 0.35},
          "Origin: Plot > 3D > Waterfall (or 2D Waterfall with X/Y offset).", "generic", ["XRD", "FTIR", "Raman"])
def draw_waterfall(d, st, p):
    fig, ax = new_fig(st)
    ser = d["series"]; rng = max(np.ptp(s["y"]) for s in ser)
    cmap = plt.get_cmap("viridis")
    for i, s in enumerate(ser):
        ax.plot(s["x"] + i * p["dx"], s["y"] + i * p["dy_frac"] * rng, color=cmap(i / max(1, len(ser) - 1)), lw=0.6, zorder=len(ser) - i)
        ax.text(s["x"].max() + i * p["dx"] + 0.5, np.nanmedian(s["y"]) + i * p["dy_frac"] * rng, s["name"], fontsize=6, va="center")
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.set_yticks([]); finish(ax, st)
    return fig


def demo_heatmap():
    x = np.linspace(10, 60, 800); t = np.linspace(0, 48, 60)
    Z = np.array([S.peaks(x, [29.4, 32.2, 18.1, 34.1], [800 * np.exp(-tt / 30), 600 * np.exp(-tt / 30),
                                                          900 * (1 - np.exp(-tt / 10)), 400 * (1 - np.exp(-tt / 10))], 0.35) for tt in t])
    return {"x": x, "y": t, "z": Z + 50, "x_label": "2θ (°), Cu Kα", "y_label": "Hydration time (h)", "z_label": "Intensity (counts)"}


@template("xrd_heatmap_contour", "Contour / colour map (2θ vs time or temperature)", CAT_XRD,
          "Many patterns at once: phase appearance and disappearance becomes visible as bands.", "matrix",
          {"x": "2θ", "y": "time/temperature per pattern", "z": "intensity matrix"}, demo_heatmap,
          {"cmap": "viridis", "log_z": False}, "Origin: Plot > Contour > Contour-Color Fill (or Heatmap) from matrix.",
          "generic", ["in-situ XRD", "calorimetry maps"])
def draw_heatmap(d, st, p):
    fig, ax = new_fig(st)
    m = ax.pcolormesh(d["x"], d["y"], d["z"], shading="auto", cmap=p["cmap"])
    cb = fig.colorbar(m, ax=ax, pad=0.01); cb.set_label(d["z_label"])
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); finish(ax, st, minor=False)
    return fig


def demo_peak_shift():
    x = np.linspace(31, 35, 600); ser = []
    for i, n in enumerate(S.SAMPLES):
        ser.append({"name": n, "x": x, "y": S.peaks(x, [32.2 - 0.03 * i, 32.6 - 0.03 * i, 34.3 - 0.02 * i], [900, 700, 800], 0.12)})
    return {"x_label": "2θ (°), Cu Kα", "y_label": "Normalised intensity (offset)", "series": ser, "ref_lines": [32.2, 34.3]}


@template("xrd_peak_shift", "Peak-shift / diagnostic window", CAT_XRD,
          "Zoom on a few peaks with reference lines to show peak shifts or splitting (polymorphs, substitution).",
          "xy_series", {"x": "2θ", "series": "one per sample", "ref_lines": "user-supplied reference positions"},
          demo_peak_shift, {"normalise": True, "offset": "auto", "color_by_sample": True},
          "Origin: Stacked lines + vertical reference lines (Insert > Line).", "generic", ["XRD"])
def draw_peak_shift(d, st, p):
    fig, ax = new_fig(st)
    if p["normalise"]:
        d = {**d, "series": [{**s, "y": s["y"] / np.nanmax(s["y"])} for s in d["series"]]}
    _stack(ax, d, st, {**p, "offset": 0.8})
    for r in d.get("ref_lines", []):
        ax.axvline(r, color="#888888", ls=":", lw=0.7)
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.set_yticks([]); finish(ax, st)
    return fig


def demo_wh():
    x = np.array([1.2, 1.5, 1.9, 2.3, 2.8, 3.1]); y = 0.0021 * x + 0.004 + np.random.default_rng(1).normal(0, 0.0003, 6)
    return {"series": [{"name": "Alite", "x": x, "y": y}], "x_label": "4 sin θ", "y_label": "β cos θ (rad)"}


@template("williamson_hall", "Williamson–Hall plot with linear fit", CAT_XRD,
          "Crystallite size (intercept) and microstrain (slope) from peak broadening.", "xy_series",
          {"x": "4 sin θ", "y": "β cos θ"}, demo_wh, {"show_equation": True},
          "Origin: Scatter + Analysis > Fitting > Linear Fit; report table to sheet.", "generic", ["XRD"],
          ["linear regression: slope = strain, intercept = Kλ/D (K, λ user-confirmed)"])
def draw_wh(d, st, p):
    return draw_scatter_fit(d, st, {"ci": False, "show_equation": p["show_equation"]})


def demo_lattice():
    x = np.array([0, 5, 10, 15, 20]); y = 5.584 + 0.004 * x
    return {"series": [{"name": "Ferrite a", "x": x, "y": y, "yerr": np.full(5, 0.002)}],
            "x_label": "Additive (wt.%)", "y_label": "Lattice parameter a (Å)"}


@template("lattice_param_vs_x", "Lattice parameter vs composition (Vegard-type)", CAT_XRD,
          "Refined cell parameters with esd error bars vs substitution level.", "xy_series",
          {"x": "composition", "y": "parameter", "yerr": "esd"}, demo_lattice, {},
          "Origin: Line + Symbol with Y error bars.", "generic", ["Rietveld"])
def draw_lattice(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.4)
    _xy_lines(ax, d, st, markers=True)
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); finish(ax, st)
    return fig


# ================================================================================================ PHASE / COMPOSITION
def demo_qpa():
    phases = ["Alite", "Belite", "Aluminate", "Ferrite", "Free lime", "Amorphous"]
    v = np.array([[62, 15, 8, 9, 1, 5], [57, 20, 9, 2, 0.8, 11], [56, 21, 3, 4, 0.7, 15],
                  [53, 9, 11, 2.5, 0.5, 23], [22, 30, 11, 4.5, 0.3, 32], [8, 33, 11, 4.2, 0.0, 43]], float)
    return {"categories": S.SAMPLES, "groups": phases, "values": v, "x_label": "Sample", "y_label": "Content (wt.%)"}


@template("qpa_stacked_bar_100", "Phase assemblage – stacked bars", CAT_PHASE,
          "Rietveld QPA (incl. amorphous) per sample as stacked bars summing to 100 wt.%.", "category_table",
          {"categories": "samples (column 1)", "groups": "phases (one column each)"}, demo_qpa,
          {"show_values": False, "horizontal": False}, "Origin: Column > Stacked Column.", "generic", ["Rietveld QPA"])
def draw_qpa_stacked(d, st, p):
    fig, ax = new_fig(st)
    bottom = np.zeros(len(d["categories"])); cols = distinct_colors(st, d["groups"])
    for j, g in enumerate(d["groups"]):
        v = d["values"][:, j]
        ax.bar(d["categories"], v, bottom=bottom, color=cols[j], edgecolor="k", lw=0.4, label=g, width=0.65)
        bottom += np.nan_to_num(v)
    ax.set_ylabel(d["y_label"]); ax.set_xlabel(d["x_label"]); ax.set_ylim(0, max(100, bottom.max() * 1.02) if p.get("sum_to_100", True) else bottom.max() * 1.1)
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left"); finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


@template("qpa_grouped_bar", "Grouped bars with error bars", CAT_PHASE,
          "Compare one quantity per phase across samples (or per sample across phases).", "category_table",
          {"categories": "x groups", "groups": "bars within group", "errors": "optional ± table"}, demo_qpa,
          {"show_values": False}, "Origin: Column > Grouped Columns (Indexed); Y error from second sheet.", "generic",
          ["Rietveld QPA", "strength", "oxides"])
def draw_grouped_bar(d, st, p):
    fig, ax = new_fig(st)
    _grouped(ax, d, st, p)
    ax.set_ylabel(d["y_label"]); ax.set_xlabel(d["x_label"]); finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


def _grouped(ax, d, st, p, hatches=None, colors=None):
    n = len(d["groups"]); w = 0.8 / n; x = np.arange(len(d["categories"]))
    colors = colors or distinct_colors(st, d["groups"])
    for j, g in enumerate(d["groups"]):
        err = d.get("errors")[:, j] if d.get("errors") is not None else None
        bars = ax.bar(x + (j - (n - 1) / 2) * w, d["values"][:, j], w, yerr=err, capsize=2, label=g, edgecolor="k", lw=0.4,
                      color=colors[j], hatch=(hatches[j] if hatches else None))
        if p.get("show_values"):
            ax.bar_label(bars, fmt=p.get("value_fmt", "%.1f"), fontsize=6, padding=1)
    ax.set_xticks(x); ax.set_xticklabels(d["categories"]); ax.legend(ncols=min(n, 4), loc="upper right")


def demo_vs_dosage():
    x = np.array([0, 5, 10, 15, 20])
    return {"x_label": "Additive (wt.%)", "y_label": "Content (wt.%)", "panels": [
        {"title": "Alite, C$_3$S", "series": [{"name": "Rietveld QPA (measured)", "x": x, "y": np.array([60, 55, 48, 40, 30])},
                                               {"name": "Series 1", "x": x, "y": np.array([62, 55, 52, 32, 0])},
                                               {"name": "Series 2", "x": x, "y": np.array([62, 54, 53, 31, 1])}]},
        {"title": "Belite, C$_2$S", "series": [{"name": "Rietveld QPA (measured)", "x": x, "y": np.array([20, 21, 9, 30, 33])},
                                                {"name": "Series 1", "x": x, "y": np.array([7, 21, 0, 17, 39])},
                                                {"name": "Series 2", "x": x, "y": np.array([23, 31, 20, 37, 64])}]},
        {"title": "Amorphous / liquid", "series": [{"name": "Rietveld QPA (measured)", "x": x, "y": np.array([11, 15, 23, 32, 43])},
                                                    {"name": "Series 1", "x": x, "y": np.array([30, 24, 44, 51, 61])},
                                                    {"name": "Series 2", "x": x, "y": np.array([7, 4, 10, 11, 15])}]}]}


@template("phase_vs_dosage_lines", "Measured vs modelled, one panel per phase", CAT_PHASE,
          "Lines + open markers; measured solid black, models dashed/dotted; shared legend in last cell.",
          "xy_series", {"panels": "one file (or sheet) per phase: x + measured + model columns"}, demo_vs_dosage,
          {"ncols": 3}, "Origin: Line+Symbol, then Merge Graph Windows; legend in a free layer.", "house",
          ["measured vs modelled", "models vs measured"])
def draw_vs_dosage(d, st, p):
    pan = d["panels"]; nc = min(p["ncols"], len(pan)); nr = int(np.ceil(len(pan) / nc))
    fig, axs = new_fig(st, nr, nc, aspect=1.6 if nr == 1 else 1.25, gridspec_kw={"wspace": 0.35, "hspace": 0.45})
    axs = np.atleast_1d(axs).ravel()
    sty = [dict(color="k", marker="o", ls="-", mfc="k"), dict(color="#1F77B4", marker="s", ls="--", mfc="white"),
           dict(color="#E07020", marker="^", ls=":", mfc="white")]
    for k, (ax, pn) in enumerate(zip(axs, pan)):
        for i, s in enumerate(pn["series"]):
            ax.plot(s["x"], s["y"], label=s["name"], **sty[i % 3])
        panel_title(ax, k, pn["title"]); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); finish(ax, st)
    axs[0].legend(loc="best", fontsize=6)
    for ax in axs[len(pan):]:
        ax.axis("off")
    return fig


def demo_parity():
    r = np.random.default_rng(4); m = np.array([55, 22, 10, 3, 10, 50, 25, 5, 6, 14, 20, 28, 12, 5, 35])
    return {"points": [{"name": "Bogue", "x": m, "y": m * 1.08 + r.normal(0, 3, len(m))},
                       {"name": "Model", "x": m, "y": m * 0.95 + r.normal(0, 4, len(m))}],
            "x_label": "Rietveld QPA (wt.%)", "y_label": "Calculated (wt.%)"}


@template("parity_plot", "Parity plot (calculated vs measured)", CAT_PHASE,
          "Bogue / model vs Rietveld with 1:1 line and ±band; RMSE in legend.", "scatter",
          {"x": "measured", "y": "calculated", "group": "method"}, demo_parity, {"band": 5},
          "Origin: Scatter + Insert > Line (y = x) + band via fill-between series.", "generic", ["QPA", "models"],
          ["RMSE and bias per method"])
def draw_parity(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.25)
    allv = np.concatenate([np.r_[q["x"], q["y"]] for q in d["points"]]); lo, hi = 0, np.nanmax(allv) * 1.05
    ax.plot([lo, hi], [lo, hi], color="k", lw=0.8); ax.fill_between([lo, hi], [lo - p["band"], hi - p["band"]], [lo + p["band"], hi + p["band"]], color="#EEEEEE", lw=0)
    for i, q in enumerate(d["points"]):
        rmse = np.sqrt(np.nanmean((q["y"] - q["x"]) ** 2))
        ax.plot(q["x"], q["y"], "os^D"[i % 4], mfc="white", color=st["palette"]["series"][i + 1], label=f"{q['name']} (RMSE {rmse:.1f})")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal"); ax.legend(); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); finish(ax, st)
    return fig


def demo_donut():
    return {"categories": ["Alite", "Belite", "Aluminate", "Ferrite", "Amorphous"], "values": [55, 22, 10, 3, 10], "title": "Sample B"}


@template("donut_composition", "Donut chart (single composition)", CAT_PHASE,
          "Only for a single sample summary on slides; prefer bars for comparisons.", "category_table",
          {"categories": "phase", "values": "wt.%"}, demo_donut, {}, "Origin: Plot > 2D > Doughnut.", "generic", ["slides"])
def draw_donut(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.4)
    cols = [series_color(st, c, i + 1) for i, c in enumerate(d["categories"])]
    w, _ = ax.pie(d["values"], colors=cols, startangle=90, counterclock=False, wedgeprops=dict(width=0.38, edgecolor="white"))
    ax.legend(w, [f"{c} {v:.0f} %" for c, v in zip(d["categories"], d["values"])], loc="center left", bbox_to_anchor=(1, 0.5))
    ax.text(0, 0, d.get("title", ""), ha="center", va="center", fontweight="bold"); ax.set_aspect("equal")
    return fig


def demo_xrf():
    ox = ["CaO", "SiO$_2$", "Al$_2$O$_3$", "Fe$_2$O$_3$", "MgO", "SO$_3$", "K$_2$O", "Na$_2$O", "TiO$_2$"]
    v = np.array([[64.5, 20.5, 5.2, 3.1, 1.9, 0.6, 0.7, 0.3, 0.25], [8.2, 56.0, 14.8, 7.9, 3.4, 1.2, 3.1, 2.8, 0.6]]).T
    return {"categories": ox, "groups": ["Sample B", "Additive"], "values": v, "x_label": "", "y_label": "Content (wt.%)"}


@template("xrf_oxide_bar", "Oxide composition bars (XRF)", CAT_PHASE,
          "Major and minor oxides; optional log scale or split axis so minor oxides stay visible.", "category_table",
          {"categories": "oxides", "groups": "materials"}, demo_xrf, {"log_y": True},
          "Origin: Grouped Column; Y log10 scale (Axis dialog).", "generic", ["XRF", "raw meal design"])
def draw_xrf(d, st, p):
    fig, ax = new_fig(st)
    _grouped(ax, d, st, p)
    if p["log_y"]:
        ax.set_yscale("log")
    ax.set_ylabel(d["y_label"]); finish(ax, st, minor=False)
    return fig


def demo_moduli():
    return {"categories": S.SAMPLES[1:], "groups": ["LSF", "SM", "AM"],
            "values": np.array([[0.96, 2.5, 1.6], [0.95, 2.4, 1.5], [0.94, 2.3, 1.4], [0.93, 2.2, 1.3], [0.92, 2.1, 1.2]]),
            "targets": {"LSF": [0.92, 0.98], "SM": [2.0, 3.0], "AM": [1.0, 4.0]}, "x_label": "Raw meal", "y_label": ""}


@template("raw_meal_moduli", "Raw-meal moduli (LSF, SM, AM) with target bands", CAT_PHASE,
          "One small panel per modulus; shaded target window supplied by the user.", "category_table",
          {"categories": "mixes", "groups": "LSF/SM/AM columns", "targets": "user-supplied ranges"}, demo_moduli, {},
          "Origin: three Column layers; target band = Insert > Rectangle in axis units.", "generic", ["raw meal design"],
          ["LSF = CaO/(2.8SiO2+1.18Al2O3+0.65Fe2O3); SM = SiO2/(Al2O3+Fe2O3); AM = Al2O3/Fe2O3"])
def draw_moduli(d, st, p):
    n = len(d["groups"]); fig, axs = new_fig(st, 1, n, gridspec_kw={"wspace": 0.4})
    for j, (ax, g) in enumerate(zip(axs, d["groups"])):
        ax.bar(d["categories"], d["values"][:, j], color=st["palette"]["series"][1], edgecolor="k", lw=0.4, width=0.6)
        if g in d.get("targets", {}):
            lo, hi = d["targets"][g]; ax.axhspan(lo, hi, color="#2CA02C", alpha=0.12, lw=0)
        panel_title(ax, j, g); ax.set_ylim(min(d["values"][:, j].min(), d.get("targets", {}).get(g, [9e9])[0]) * 0.9,
                                            max(d["values"][:, j].max(), d.get("targets", {}).get(g, [0, 0])[1]) * 1.05)
        finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator()); ax.tick_params(axis="x", labelsize=6.5)
    return fig


def _tern(a, b, c):
    s = a + b + c; a, b, c = a / s, b / s, c / s
    return 0.5 * (2 * b + c), np.sqrt(3) / 2 * c


def demo_ternary():
    return {"apexes": ["SiO$_2$", "CaO", "Al$_2$O$_3$"],  # a (bottom-left), b (bottom-right), c (top)
            "regions": [{"name": "Portland clinker", "pts": [(17, 76, 7), (28, 65, 7), (26, 62, 12), (16, 70, 14)]},
                        {"name": "Slag", "pts": [(30, 55, 15), (45, 40, 15), (40, 38, 22), (28, 50, 22)]},
                        {"name": "Siliceous fly ash", "pts": [(45, 5, 50), (65, 5, 30), (60, 15, 25), (42, 15, 43)]}],
            "points": [{"name": "Material 2", "a": 5, "b": 93, "c": 2}, {"name": "Additive", "a": 62, "b": 8, "c": 16},
                       {"name": "Material 1", "a": 78, "b": 4, "c": 13}, {"name": "Sample B", "a": 22, "b": 70, "c": 6}, {"name": "Sample F", "a": 27, "b": 62, "c": 9}]}


@template("ternary_cas", "Ternary diagram (CaO–SiO2–Al2O3 or any 3 components)", CAT_PHASE,
          "Place raw materials, raw meals and clinkers in composition space; optional shaded fields.", "ternary",
          {"a,b,c": "three component columns (normalised to 100)", "name": "label column", "regions": "optional polygons"},
          demo_ternary, {"grid_step": 10}, "Origin: Plot > Specialized > Ternary.", "generic", ["raw meal design", "SCM screening"])
def draw_ternary(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.15)
    tri = np.array([[0, 0], [1, 0], [0.5, np.sqrt(3) / 2], [0, 0]]); ax.plot(tri[:, 0], tri[:, 1], "k", lw=0.8)
    for g in np.arange(p["grid_step"], 100, p["grid_step"]):
        for (a1, b1, c1), (a2, b2, c2) in [((g, 100 - g, 0), (g, 0, 100 - g)), ((100 - g, g, 0), (0, g, 100 - g)), ((100 - g, 0, g), (0, 100 - g, g))]:
            x1, y1 = _tern(a1, b1, c1); x2, y2 = _tern(a2, b2, c2); ax.plot([x1, x2], [y1, y2], color="#DDDDDD", lw=0.4, zorder=0)
    for i, r in enumerate(d.get("regions", [])):
        xy = np.array([_tern(*q) for q in r["pts"]]); ax.add_patch(Polygon(xy, closed=True, alpha=0.2, color=st["palette"]["series"][i + 6 if i + 6 < len(st["palette"]["series"]) else i]))
        ax.text(*xy.mean(0), r["name"], fontsize=6, ha="center")
    for i, q in enumerate(d["points"]):
        x, y = _tern(q["a"], q["b"], q["c"]); ax.plot(x, y, "o", color=series_color(st, q["name"], i), ms=4); ax.annotate(q["name"], (x, y), fontsize=6, xytext=(3, 3), textcoords="offset points")
    A = d["apexes"]; ax.text(-0.03, -0.04, A[0], ha="right"); ax.text(1.03, -0.04, A[1], ha="left"); ax.text(0.5, 0.89, A[2], ha="center")
    ax.set_aspect("equal"); ax.axis("off")
    return fig


def demo_radar():
    return {"categories": ["Early strength", "28-d strength", "CO$_2$ saving", "Workability", "Cost", "Waste use"],
            "groups": ["Sample B", "Sample D", "Sample F"], "values": np.array([[0.8, 0.6, 0.4], [0.9, 0.7, 0.5], [0.2, 0.5, 0.8], [0.7, 0.7, 0.6], [0.6, 0.7, 0.8], [0.1, 0.5, 0.9]])}


@template("radar_properties", "Radar chart (multi-criteria)", CAT_PHASE,
          "Normalised (0-1) performance scores for a few mixes; for slides and discussion only.", "category_table",
          {"categories": "criteria", "groups": "mixes"}, demo_radar, {}, "Origin: Plot > Specialized > Radar.", "generic", ["slides"])
def draw_radar(d, st, p):
    fig = make_fig(fig_size(st, "single", 1.3)); ax = fig.add_subplot(projection="polar")
    ang = np.linspace(0, 2 * np.pi, len(d["categories"]), endpoint=False).tolist(); ang += ang[:1]
    for j, g in enumerate(d["groups"]):
        v = d["values"][:, j].tolist(); v += v[:1]; c = series_color(st, g, j)
        ax.plot(ang, v, color=c, label=g); ax.fill(ang, v, color=c, alpha=0.1)
    ax.set_xticks(ang[:-1]); ax.set_xticklabels(d["categories"], fontsize=6.5); ax.set_yticklabels([]); ax.legend(bbox_to_anchor=(1.25, 1.05))
    return fig


# ================================================================================================ THERMAL
ZONES_CEMENT = [  # DEFAULT suggestions only - user confirms/edits in the app (see 05_analysis_reference)
    {"name": "C-S-H / AFt (dehydration)", "T": [30, 200], "color": "#9EC5E8"},
    {"name": "AFm zone", "T": [150, 250], "color": "#A8D5A2"},
    {"name": "Portlandite Ca(OH)$_2$", "T": [400, 550], "color": "#F6C89F"},
    {"name": "Calcite (CO$_2$)", "T": [600, 800], "color": "#C9C9DD"},
]


def demo_tg(names=S.SAMPLES):
    T = np.linspace(30, 1000, 1500); out = []
    for i, n in enumerate(names):
        steps = [(110 + 5 * i, 18, 6 - 0.6 * i), (470 + 4 * i, 10, max(0.4, 3.5 - 0.6 * i)), (720, 18, 2.5 if n == "Sample A" else 0.6)]
        m = S.tga_curve(T, steps, seed=i)
        out.append({"name": n, "T": T, "mass": m})
    return {"samples": out, "zones": ZONES_CEMENT, "x_label": "Temperature (°C)", "y_label": "Mass (%)", "y2_label": "DTG (% °C$^{-1}$)"}


def _dtg(s):
    from .tga_core import dtg
    return dtg(s["T"], s["mass"])["dtg_per_C"]  # always smoothed derivative; raw instrument DTG may be offered as option


@template("tga_dtg_single", "TG and DTG in one graph (DTG natural sign, right axis)", CAT_TH,
          "One sample: TG left axis, DTG right axis drawn with its natural (negative) sign; mass-loss steps annotated.",
          "thermal", {"T": "temperature", "mass": "mass % (or mg -> converted)", "dtg": "optional; computed if absent"},
          lambda: {**demo_tg(["Sample B"]), "annotations": True}, {"show_steps": True, "dtg_units": "% °C⁻¹"},
          "Origin: Plot > Multi-Curve > Double-Y; DTG on Layer 2 right axis, NOT reversed.", "house",
          ["TGA"], ["DTG = dm/dT (Savitzky–Golay)", "step mass loss between user-confirmed limits"])
def draw_tga_single(d, st, p):
    fig, ax = new_fig(st); s = d["samples"][0]; ax2 = ax.twinx()
    ax.plot(s["T"], s["mass"], color="k", label="TG (mass)")
    ax2.plot(s["T"], _dtg(s), color="#C0141E", label="DTG")
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax2.set_ylabel(d["y2_label"], color="#C0141E"); ax2.tick_params(axis="y", colors="#C0141E")
    if p["show_steps"]:
        for z in d["zones"][::2]:
            m = (s["T"] >= z["T"][0]) & (s["T"] <= z["T"][1]); dm = s["mass"][m][0] - s["mass"][m][-1]
            ax.annotate(f"Δm = {dm:.2f} %\n{z['T'][0]}–{z['T'][1]} °C", (np.mean(z["T"]), s["mass"][m].mean()), xytext=(10, 18),
                        textcoords="offset points", fontsize=6.5, arrowprops=dict(arrowstyle="-", lw=0.5))
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels(); ax.legend(h1 + h2, l1 + l2, loc="lower left")
    ax.set_xlim(s["T"].min(), s["T"].max()); finish(ax, st); ax.tick_params(right=False); ax2.tick_params(direction=st["axes"]["tick_direction"])
    return fig


@template("tga_dtg_zones_multi", "DTG of several samples with shaded decomposition zones", CAT_TH,
          "Overlay DTG of all samples; shaded and labelled zones (C-S-H/AFt, AFm, portlandite, calcite).", "thermal",
          {"samples": "one T/mass (or DTG) pair per sample", "zones": "user-confirmed temperature windows"},
          demo_tg, {"label_zones": True, "heating_rate_C_per_min": 10}, "Origin: Line plot + Insert > Rectangle (axis-scaled) per zone.",
          "house", ["TGA"], ["zone mass loss", "peak temperature per zone"])
def draw_tga_zones(d, st, p):
    fig, ax = new_fig(st)
    for k, z in enumerate(d["zones"]):
        ax.axvspan(*z["T"], color=z["color"], alpha=0.35, lw=0)
        if p["label_zones"]:
            ax.text(np.mean(z["T"]), 1.01 + 0.09 * (k % 2), f"{z['name']}\n({z['T'][0]}–{z['T'][1]} °C)", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=6)
    for i, s in enumerate(d["samples"]):
        ax.plot(s["T"], _dtg(s) * p["heating_rate_C_per_min"], color=series_color(st, s["name"], i), label=s["name"])
    ax.set_xlabel(d["x_label"]); ax.set_ylabel("DTG (% min$^{-1}$)"); ax.legend(loc="lower left"); ax.set_xlim(30, 900); finish(ax, st)
    return fig


@template("tga_multi_sample_tg", "TG curves of several samples (mass %)", CAT_TH,
          "Overlay of normalised mass curves; residual mass at end labelled per sample.", "thermal",
          {"samples": "T + mass per sample"}, demo_tg, {"label_residual": True},
          "Origin: Line plot; mass normalised to 100 % at T_ref (Column > Set Column Values).", "generic", ["TGA"],
          ["normalise to initial or ignited mass"])
def draw_tg_multi(d, st, p):
    fig, ax = new_fig(st)
    for i, s in enumerate(d["samples"]):
        c = series_color(st, s["name"], i); ax.plot(s["T"], s["mass"], color=c, label=s["name"])
        if p["label_residual"]:
            ax.text(s["T"][-1] + 8, s["mass"][-1], f"{s['mass'][-1]:.1f}", color=c, fontsize=6, va="center")
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); finish(ax, st)
    return fig


@template("tga_stacked_panels", "TG–DTG panels stacked (one material per panel)", CAT_TH,
          "One TG–DTG graph per material (twin axis, DTG at its natural sign), the total mass loss written in each panel, your reference lines and your notes with arrows.", "thermal",
          {"samples": "one per panel", "notes": "your notes (typed in the editor): panel; text; x; y; text x; text y", "ref_lines": "your reference temperatures"},
          lambda: demo_tg(["Material 2", "Material 1", "Additive"]), {"show_total_loss": True, "ref_lines": []},
          "Origin: Double-Y graphs merged vertically (Merge Graph Windows, 1 column); notes via Insert > Text and Arrow.", "house", ["TGA raw materials"],
          ["total mass loss = first mass − last mass", "DTG = smoothed derivative of the mass"])
def draw_tga_panels(d, st, p):
    n = len(d["samples"]); fig, axs = new_fig(st, n, 1, sharex=True, aspect=1.2, gridspec_kw={"hspace": 0.25}); fa = st["font"]["size_pt"]["annotation"]; red = "#C0141E"; pan = list(np.atleast_1d(axs))
    for k, (ax, s) in enumerate(zip(pan, d["samples"])):
        ax2 = ax.twinx(); ax.plot(s["T"], s["mass"], "k", label="TG"); ax2.plot(s["T"], _dtg(s), color=red, label="DTG")
        panel_title(ax, k, s["name"]); ax.set_ylabel("Mass (%)"); ax2.set_ylabel("DTG (% °C$^{-1}$)", color=red); ax2.tick_params(axis="y", colors=red); finish(ax, st); ax.tick_params(right=False)
        if p.get("show_total_loss"):
            m_ = np.asarray(s["mass"], float); T_ = np.asarray(s["T"], float); ok = np.isfinite(m_)
            ax.text(0.02, 0.95, f"Total mass loss: {m_[ok][0] - m_[ok][-1]:.2f} % (up to {T_[ok][-1]:.0f} °C)", transform=ax.transAxes, va="top", fontsize=fa)
        for x_ in p.get("ref_lines") or []: ax.axvline(float(x_), color="#8A97A8", ls="--", lw=0.8)
        h = ax.get_lines()[:1] + ax2.get_lines()[:1]; ax.legend(h, ["TG", "DTG"], loc="lower left")
    for q in d.get("notes") or []:                        # the user's own notes, with an arrow to the point they are about
        try:
            ax = pan[int(q.get("panel", 1)) - 1]; kw = dict(fontsize=fa, color=q.get("color", red), fontstyle="italic")
            if q.get("text_at"): ax.annotate(str(q["text"]), xy=tuple(q["at"]), xytext=tuple(q["text_at"]), arrowprops=dict(arrowstyle="->", color=kw["color"], lw=0.8), **kw)
            else: ax.text(q["at"][0], q["at"][1], str(q["text"]), **kw)
        except Exception: continue
    pan[-1].set_xlabel(d["x_label"])
    return fig


def demo_ml():
    return {"categories": S.SAMPLES, "groups": ["30–200 °C", "200–400 °C", "400–550 °C", "550–800 °C"],
            "values": np.array([[9.5, 2.1, 3.8, 2.4], [8.8, 1.9, 3.2, 0.6], [9.6, 2.0, 2.9, 0.5], [7.1, 1.6, 2.0, 0.6], [3.5, 0.8, 0.6, 0.5], [2.1, 0.5, 0.3, 0.4]]),
            "x_label": "Sample", "y_label": "Mass loss (wt.%, ignited basis)"}


@template("tga_massloss_stacked_bar", "Mass loss per temperature window (stacked bars)", CAT_TH,
          "Result table from the TGA module drawn directly: one stacked bar per sample.", "category_table",
          {"categories": "sample", "groups": "temperature windows"}, demo_ml, {"sum_to_100": False}, "Origin: Stacked Column.", "generic",
          ["TGA results"])
def draw_ml(d, st, p):
    return draw_qpa_stacked(d, st, p)


def demo_ch():
    return {"categories": S.SAMPLES, "groups": ["Portlandite (CH)", "CaCO$_3$"], "values": np.array([[15.6, 5.5], [13.1, 1.4], [11.9, 1.1], [8.2, 1.4], [2.5, 1.1], [1.2, 0.9]]),
            "errors": np.full((6, 2), 0.4), "x_label": "Sample", "y_label": "Content (wt.%, ignited basis)"}


@template("ch_cc_content_bar", "Portlandite and CaCO3 content from TGA", CAT_TH,
          "Stoichiometric conversion of the confirmed mass-loss steps; error bars from replicates.", "category_table",
          {"categories": "sample", "groups": "CH, CaCO3"}, demo_ch, {"show_values": True}, "Origin: Grouped Column + error bars.",
          "generic", ["TGA results"], ["CH = Δm(H2O) × 74.09/18.02", "CaCO3 = Δm(CO2) × 100.09/44.01"])
def draw_ch(d, st, p):
    return draw_grouped_bar(d, st, p)


def demo_bw():
    t = np.array([1, 3, 7, 28, 90]); return {"x_label": "Age (days)", "y_label": "Bound water (wt.%)", "series": [
        {"name": n, "x": t, "y": (18 - 2.5 * i) * (1 - np.exp(-t / 6)) + 2, "yerr": np.full(5, 0.5)} for i, n in enumerate(S.SAMPLES)]}


@template("bound_water_vs_age", "Bound water / CH vs age (log time)", CAT_TH,
          "Hydration progress from TGA at several ages.", "xy_series", {"x": "age", "series": "per sample", "yerr": "optional"},
          demo_bw, {"log_x": True}, "Origin: Line+Symbol, X axis log10.", "generic", ["TGA ages"])
def draw_bw(d, st, p):
    fig, ax = new_fig(st); _xy_lines(ax, d, st, markers=True)
    if p["log_x"]:
        ax.set_xscale("log")
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(ncols=2); finish(ax, st)
    return fig


def demo_dsc():
    T = np.linspace(30, 1000, 1500)
    hf = -S.peaks(T, [120, 460, 730], [1.2, 0.8, 0.6], 60) + S.peaks(T, [880], [0.3], 40) + 0.0004 * T
    return {"series": [{"name": "Sample B", "x": T, "y": hf}], "x_label": "Temperature (°C)", "y_label": "Heat flow (W g$^{-1}$)"}


@template("dsc_heatflow", "DSC / DTA heat flow with exo/endo indicator", CAT_TH,
          "Heat flow with an 'exo ↑' arrow (direction set by the user/instrument convention) and shaded peak areas.",
          "xy_series", {"x": "T", "y": "heat flow"}, demo_dsc, {"exo": "up"},
          "Origin: Line plot + arrow annotation; Peak Analyzer for areas.", "generic", ["DSC", "DTA"], ["peak area (J/g) between limits"])
def draw_dsc(d, st, p):
    fig, ax = new_fig(st); _xy_lines(ax, d, st)
    ax.annotate("", xy=(0.04, 0.9), xytext=(0.04, 0.75), xycoords="axes fraction", arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.text(0.055, 0.82, f"exo {'↑' if p['exo'] == 'up' else '↓'}", transform=ax.transAxes, fontsize=7)
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); finish(ax, st)
    return fig


def demo_tgms():
    dd = demo_tg(["Sample B"]); T = dd["samples"][0]["T"]
    dd["ms"] = [{"name": "m/z 18 (H$_2$O)", "y": S.peaks(T, [120, 460], [1, 0.6], 60)}, {"name": "m/z 44 (CO$_2$)", "y": S.peaks(T, [720], [0.4], 60)}]
    return dd


@template("tg_ms", "TG + evolved gas (MS / FTIR) panels", CAT_TH,
          "Top: TG (+DTG); bottom: ion currents for H2O and CO2 to assign each step.", "thermal",
          {"samples": "TG", "ms": "ion current columns"}, demo_tgms, {}, "Origin: 2 stacked layers sharing X.", "generic", ["TG-MS"])
def draw_tgms(d, st, p):
    fig, (a, b) = new_fig(st, 2, 1, sharex=True, gridspec_kw={"height_ratios": [2, 1], "hspace": 0.06})
    s = d["samples"][0]; a.plot(s["T"], s["mass"], "k"); a.set_ylabel("Mass (%)")
    for i, m in enumerate(d["ms"]):
        b.plot(s["T"], m["y"], color=st["palette"]["series"][i + 1], label=m["name"])
    b.set_ylabel("Ion current (a.u.)"); b.set_xlabel(d["x_label"]); b.legend(); finish(a, st); finish(b, st)
    return fig


@template("tangent_method_demo", "Tangent (step) method view for one decomposition step", CAT_TH,
          "Analysis view: TG with tangents before/after the step and the read-off Δm; shows exactly what was integrated.",
          "thermal", {"samples": "one sample", "window": "user-confirmed onset/endset"}, lambda: demo_tg(["Sample B"]),
          {"window": [400, 550]}, "Origin: Line plot + two fitted straight lines + vertical Δm bracket.", "generic",
          ["TGA"], ["tangent method Δm at T_peak(DTG)"])
def draw_tangent(d, st, p):
    from .tga_core import tangent_step
    s = d["samples"][0]; r = tangent_step(s["T"], s["mass"], *p["window"])
    fig, ax = new_fig(st); m = (s["T"] > p["window"][0] - 80) & (s["T"] < p["window"][1] + 80)
    ax.plot(s["T"][m], s["mass"][m], "k")
    for line in (r["pre_line"], r["post_line"]):
        xx = s["T"][m]; ax.plot(xx, np.polyval(line, xx), "--", color="#1F77B4", lw=0.8)
    ax.annotate("", xy=(r["T_mid"], r["m_pre"]), xytext=(r["T_mid"], r["m_post"]), arrowprops=dict(arrowstyle="<->", color="#C0141E"))
    ax.text(r["T_mid"] + 8, (r["m_pre"] + r["m_post"]) / 2, f"Δm = {r['dm']:.2f} %", color="#C0141E")
    ax.axvspan(*p["window"], color="#F6C89F", alpha=0.3, lw=0)
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); finish(ax, st)
    return fig


# ================================================================================================ CALORIMETRY
def demo_cal():
    t = np.linspace(0.01, 168, 3000); ser = []
    for i, n in enumerate(S.SAMPLES):
        hf = S.heat_flow(t, amp=2.0 - 0.33 * i, t_peak=10 + 7 * i, w=6 + 3 * i, seed=i)
        ser.append({"name": n, "x": t, "y": hf, "cum": np.cumsum(hf) * np.gradient(t) * 3.6})
    return {"series": ser, "x_label": "Time (h)", "y_label": "Heat flow (mW g$^{-1}$)", "y2_label": "Cumulative heat (J g$^{-1}$)"}


@template("calorimetry_heatflow_inset", "Heat flow with early-age inset", CAT_CAL,
          "Normalised heat flow vs time; inset zooms the first hours; exclusion window respected.", "xy_series",
          {"x": "time (h)", "series": "heat flow per sample"}, demo_cal, {"inset": True, "inset_range": [0, 12], "x_max": 168},
          "Origin: Line plot + Graph > New Layer (inset) via Plot > Multi-Panel > Inset.", "house",
          ["TAM Air / TAM III"], ["mW/g = mW / sample mass", "exclude first X h (user-set)"])
def draw_cal_inset(d, st, p):
    fig, ax = new_fig(st); _xy_lines(ax, d, st)
    if p.get("inset", True) and any(np.any((s["x"] > 0.5) & (s["x"] < p["inset_range"][1])) for s in d["series"]):
        ins = ax.inset_axes([0.45, 0.45, 0.33, 0.45]); _xy_lines(ins, d, st); ins.set_xlim(*p["inset_range"]); ins.tick_params(labelsize=6)
        ins.set_ylim(0, max(np.nanmax(s["y"][(s["x"] > 0.5) & (s["x"] < p["inset_range"][1])]) for s in d["series"] if np.any((s["x"] > 0.5) & (s["x"] < p["inset_range"][1]))) * 1.15)
    ax.set_xlim(0, p["x_max"]); ax.set_ylim(0, max(np.nanmax(s["y"][s["x"] > 0.5]) for s in d["series"]) * 1.1)
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(loc="upper right"); finish(ax, st)
    return fig


@template("calorimetry_cumulative", "Cumulative heat with regime brackets", CAT_CAL,
          "Cumulative heat; right-hand brackets group samples into user-named regimes.", "xy_series",
          {"x": "time", "series": "cumulative heat per sample", "regimes": "user-defined groups"},
          lambda: {**demo_cal(), "regimes": [{"name": "Group I", "members": ["Sample A", "Sample B", "Sample C"]},
                                             {"name": "Group II", "members": ["Sample D"]}, {"name": "Group III", "members": ["Sample E", "Sample F"]}]},
          {"cum_factor": 3.6}, "Origin: Line plot + bracket via Insert > Line objects.", "house", ["calorimetry"], ["∫ heat flow dt"])
def draw_cal_cum(d, st, p):
    fig, ax = new_fig(st)
    for i, s in enumerate(d["series"]):
        ax.plot(s["x"], s["cum"], color=series_color(st, s["name"], i), label=s["name"])
    xm = max(s["x"].max() for s in d["series"])
    for r in d.get("regimes", []):
        ys = [s["cum"][-1] for s in d["series"] if s["name"] in r["members"]]
        lo, hi = min(ys) - 3, max(ys) + 3; ax.plot([xm * 1.01, xm * 1.025, xm * 1.025, xm * 1.01], [lo, lo, hi, hi], "k", lw=0.7, clip_on=False)
        ax.text(xm * 1.035, (lo + hi) / 2, r["name"], va="center", fontsize=7, fontweight="bold")
    ax.set_xlim(0, xm); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y2_label"]); ax.legend(loc="upper left"); finish(ax, st)
    return fig


@template("calorimetry_two_panel", "Heat flow (a) + cumulative heat (b)", CAT_CAL,
          "Standard two-panel calorimetry figure.", "xy_series", {"x": "time", "series": "heat flow (cumulative computed)"},
          demo_cal, {"x_max": 168, "cum_factor": 3.6}, "Origin: two graphs merged 1 × 2.", "house", ["calorimetry"], ["cumulative heat (J/g) = integral of heat flow (mW/g) over time (h) × 3.6"])
def draw_cal_two(d, st, p):
    fig, (a, b) = new_fig(st, 1, 2, gridspec_kw={"wspace": 0.28})
    _xy_lines(a, d, st); a.set_ylim(0, max(np.nanmax(s["y"][s["x"] > 0.5]) for s in d["series"]) * 1.1)
    for i, s in enumerate(d["series"]):
        b.plot(s["x"], s["cum"], color=series_color(st, s["name"], i), label=s["name"])
    for k, (ax, yl) in enumerate(((a, d["y_label"]), (b, d["y2_label"]))):
        ax.set_xlim(0, p["x_max"]); ax.set_xlabel(d["x_label"]); ax.set_ylabel(yl); panel_title(ax, k); finish(ax, st)
    b.legend(loc="upper left")
    return fig


def demo_q_bar():
    return {"categories": ["Sample A", "Sample B", "Sample C\n(5 wt.%)", "Sample D\n(10 wt.%)", "Sample E\n(15 wt.%)", "Sample F\n(20 wt.%)"], "groups": ["Q"],
            "values": np.array([[310], [265], [250], [180], [90], [60]]), "x_label": "Sample (additive level)",
            "y_label": "Q$_{168}$ per unit alite (J g$^{-1}$ alite)",
            "regimes": [{"name": "Group I", "idx": [0, 2]}, {"name": "Group II", "idx": [3, 3]}, {"name": "Group III", "idx": [4, 5]}]}


@template("normalised_heat_bar_regimes", "Bars with value labels and regime brackets", CAT_CAL,
          "One value per sample, value printed on the bar, horizontal brackets naming groups.", "category_table",
          {"categories": "sample", "values": "one column", "regimes": "user-defined index ranges + names"}, demo_q_bar, {},
          "Origin: Column + Label (Plot Details > Label tab) + bracket lines.", "house", ["calorimetry", "any one-value-per-sample"])
def draw_q_bar(d, st, p):
    fig, ax = new_fig(st); v = d["values"][:, 0]; x = np.arange(len(v))
    cols = [series_color(st, c.split()[0], i) for i, c in enumerate(d["categories"])]
    bars = ax.bar(x, v, color=cols, edgecolor="k", lw=0.5, width=0.62); ax.bar_label(bars, fmt="%.0f", fontweight="bold", padding=2)
    top = v.max() * 1.12
    for r in d.get("regimes", []):
        i0, i1 = r["idx"]; y = max(v[i0:i1 + 1]) + v.max() * 0.12; c = cols[i0]
        ax.plot([i0 - 0.35, i0 - 0.35, i1 + 0.35, i1 + 0.35], [y - v.max() * 0.025, y, y, y - v.max() * 0.025], color=c if i0 else "k", lw=1.2)
        ax.text((i0 + i1) / 2, y + v.max() * 0.01, r["name"], ha="center", va="bottom", fontweight="bold", color=c if i0 else "k"); top = max(top, y * 1.12)
    ax.set_xticks(x); ax.set_xticklabels(d["categories"]); ax.set_ylim(0, top); ax.set_ylabel(d["y_label"]); ax.set_xlabel(d["x_label"])
    finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


@template("heatflow_vs_cumheat", "Heat flow vs cumulative heat", CAT_CAL,
          "Kinetic view that removes time; compares reaction regimes and sulfate depletion.", "xy_series",
          {"series": "heat flow + cumulative per sample"}, demo_cal, {}, "Origin: Line plot of two computed columns.", "generic", ["calorimetry"])
def draw_hf_cum(d, st, p):
    fig, ax = new_fig(st)
    for i, s in enumerate(d["series"]):
        m = s["x"] > 0.5; ax.plot(s["cum"][m], s["y"][m], color=series_color(st, s["name"], i), label=s["name"])
    ax.set_xlabel(d["y2_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); finish(ax, st)
    return fig


# ================================================================================================ PSD / POROSITY
def demo_psd():
    dd = np.logspace(-1, 3, 400); ser = []; dv = []
    for i, (n, d50, sg) in enumerate([("Material 1", 35, 1.0), ("Additive", 110, 0.9), ("Material 2", 14, 1.1), ("Sample B", 16, 0.8), ("Sample F", 12, 0.75)]):
        q, c = S.lognormal_psd(dd, d50, sg); ser.append({"name": n, "x": dd, "y": q, "cum": c})
        dv.append([np.interp(k, c, dd) for k in (10, 50, 90)])
    return {"series": ser, "dvals": dv, "x_label": "Particle size (µm)", "y_label": "Differential volume (%)", "y2_label": "Cumulative volume (%)"}


@template("psd_diff_cum_2x2", "Particle size: differential + cumulative (log x)", CAT_PSD,
          "Laser diffraction PSD: differential and cumulative side by side, d10/d50/d90 table inset.", "xy_series",
          {"x": "size (µm)", "series": "volume % per material"}, demo_psd, {"table": True},
          "Origin: Line plot, X log10; table via Insert > Table (linked to sheet).", "house", ["laser diffraction"], ["d10/d50/d90 by interpolation of cumulative curve"])
def draw_psd(d, st, p):
    fig, (a, b) = new_fig(st, 1, 2, gridspec_kw={"wspace": 0.28})
    for i, s in enumerate(d["series"]):
        c = series_color(st, s["name"], i); a.plot(s["x"], s["y"], color=c, label=s["name"]); b.plot(s["x"], s["cum"], color=c)
    for k, (ax, yl) in enumerate(((a, d["y_label"]), (b, d["y2_label"]))):
        ax.set_xscale("log"); ax.set_xlabel(d["x_label"]); ax.set_ylabel(yl); panel_title(ax, k); finish(ax, st)
    a.legend()
    if p["table"]:
        rows = [[s["name"]] + [f"{v:.1f}" for v in dv] for s, dv in zip(d["series"], d["dvals"])]
        t = b.table(cellText=rows, colLabels=["Material", "d$_{10}$", "d$_{50}$", "d$_{90}$"], loc="upper left", bbox=[0.03, 0.55, 0.5, 0.42])
        t.auto_set_font_size(False); t.set_fontsize(5.5)
    return fig


def demo_dval():
    dd = demo_psd(); return {"categories": [s["name"] for s in dd["series"]], "groups": ["d$_{10}$", "d$_{50}$", "d$_{90}$"],
                             "values": np.array(dd["dvals"]), "x_label": "Material", "y_label": "Particle size (µm)"}


@template("psd_dvalues_bar", "d10 / d50 / d90 grouped bars (log y)", CAT_PSD,
          "Compact comparison of fineness.", "category_table", {"categories": "material", "groups": "d10, d50, d90"}, demo_dval,
          {"log_y": True}, "Origin: Grouped Column, Y log.", "generic", ["laser diffraction"])
def draw_dval(d, st, p):
    return draw_xrf(d, st, p)


def demo_rrsb():
    dd = demo_psd(); ser = []
    for s in dd["series"][:3]:
        m = (s["cum"] > 1) & (s["cum"] < 99); ser.append({"name": s["name"], "x": np.log(s["x"][m]), "y": np.log(-np.log(1 - s["cum"][m] / 100))})
    return {"series": ser, "x_label": "ln d (µm)", "y_label": "ln[−ln(1 − Q(d))]"}


@template("rrsb_plot", "RRSB (Rosin–Rammler) linearised plot", CAT_PSD,
          "Slope n (uniformity) and position parameter d' from a straight-line fit.", "xy_series",
          {"x": "size", "y": "cumulative passing"}, demo_rrsb, {}, "Origin: Set Column Values (transform) + Linear Fit.", "generic",
          ["grinding / fineness"], ["n = slope; d' = exp(−intercept/n)"])
def draw_rrsb(d, st, p):
    fig, ax = new_fig(st); _xy_lines(ax, d, st); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); finish(ax, st)
    return fig


def demo_mip():
    dd = np.logspace(-3, 2, 300); ser = []
    for i, n in enumerate(["Sample B 28 d", "Sample D 28 d", "Sample F 28 d"]):
        q, c = S.lognormal_psd(dd, 0.03 * (1 + i), 0.9); ser.append({"name": n, "x": dd, "y": q / 300, "cum": (100 - c) * (0.12 + 0.03 * i) / 100})
    return {"series": ser, "x_label": "Pore entry diameter (µm)", "y_label": "Log differential intrusion (mL g$^{-1}$)", "y2_label": "Cumulative intrusion (mL g$^{-1}$)"}


@template("mip_pore", "MIP: cumulative + log-differential intrusion", CAT_PSD,
          "Pore structure of pastes; x axis reversed (large → small) as is conventional for intrusion.", "xy_series",
          {"x": "pore diameter", "series": "dV/dlogD and cumulative"}, demo_mip, {"reverse_x": True},
          "Origin: two layers, X log10 reversed.", "generic", ["MIP"], ["critical pore diameter = max of dV/dlogD"])
def draw_mip(d, st, p):
    fig, (a, b) = new_fig(st, 1, 2, gridspec_kw={"wspace": 0.3})
    for i, s in enumerate(d["series"]):
        c = st["palette"]["series"][i + 1]; a.plot(s["x"], s["cum"], color=c, label=s["name"]); b.plot(s["x"], s["y"], color=c)
    for k, (ax, yl) in enumerate(((a, d["y2_label"]), (b, d["y_label"]))):
        ax.set_xscale("log"); ax.set_xlabel(d["x_label"]); ax.set_ylabel(yl); panel_title(ax, k); finish(ax, st)
        if p["reverse_x"]:
            ax.invert_xaxis()
    a.legend()
    return fig


def demo_bet():
    pp = np.linspace(0.01, 0.99, 60); ads = 20 * pp / (1 - pp) ** 0.3 + 5; des = ads + 8 * np.exp(-((pp - 0.7) / 0.15) ** 2) * (pp > 0.45)
    return {"series": [{"name": "Adsorption", "x": pp, "y": ads}, {"name": "Desorption", "x": pp, "y": des}],
            "x_label": "Relative pressure p/p$_0$", "y_label": "Quantity adsorbed (cm$^3$ g$^{-1}$ STP)"}


@template("bet_isotherm", "N2 sorption isotherm (adsorption / desorption)", CAT_PSD,
          "Hysteresis loop; filled = adsorption, open = desorption.", "xy_series", {"x": "p/p0", "series": "ads, des"}, demo_bet, {},
          "Origin: Line+Symbol, two series.", "generic", ["BET"])
def draw_bet(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.35); _xy_lines(ax, d, st, markers=True); ax.legend(); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); finish(ax, st)
    return fig


# ================================================================================================ SPECTROSCOPY
def demo_ftir():
    wn = np.linspace(4000, 500, 2000); ser = []
    for i, n in enumerate(S.SAMPLES):
        y = 100 - (S.peaks(wn, [3643], [3 * (i < 3)], 15) + S.peaks(wn, [3400], [2], 300) + S.peaks(wn, [1640], [1.5], 40) +
                   S.peaks(wn, [1420], [max(0.5, 6 - i)], 70) + S.peaks(wn, [970], [8 + i], 90) + S.peaks(wn, [875], [3], 15))
        ser.append({"name": n, "x": wn, "y": y})
    return {"series": ser, "x_label": "Wavenumber (cm$^{-1}$)", "y_label": "Transmittance (%), spectra offset",
            "bands": [{"x": 3643, "label": "Ca(OH)$_2$ O–H"}, {"x": 1640, "label": "H–O–H bend"}, {"x": 1420, "label": "CO$_3^{2-}$"}, {"x": 970, "label": "Si–O (C–S–H)"}],
            "shade": [800, 1100]}


@template("ftir_stacked_bands", "FTIR stacked spectra with band lines", CAT_SPEC,
          "Reversed wavenumber axis, offset spectra, dashed band lines labelled at top, one shaded region; names at right in sample colour.",
          "xy_series", {"x": "wavenumber", "series": "one per sample", "bands": "user-confirmed band list"}, demo_ftir,
          {"offset": 8}, "Origin: Stacked Lines by Y Offsets, X reversed (From 4000 To 500).", "house", ["FTIR", "ATR"])
def draw_ftir(d, st, p):
    fig, ax = new_fig(st)
    for i, s in enumerate(d["series"]):
        c = series_color(st, s["name"], i); y = s["y"] - i * p["offset"]; ax.plot(s["x"], y, color=c, lw=0.8)
        ax.text(s["x"].min() - 40, y[-1], s["name"], color=c, fontweight="bold", va="center", fontsize=7)
    if d.get("shade"):
        ax.axvspan(*d["shade"], color="#9EC5E8", alpha=0.45, lw=0)
    for b in d.get("bands", []):
        ax.axvline(b["x"], color="#888888", ls=":", lw=0.7)
        ax.text(b["x"], 1.01, f"{b['label']}, {b['x']}", rotation=90, transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=6)
    ax.set_xlim(max(d["series"][0]["x"]), min(d["series"][0]["x"])); ax.set_yticks([])
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); finish(ax, st)
    return fig


def demo_raman():
    x = np.linspace(100, 1200, 1500)
    return {"series": [{"name": n, "x": x, "y": S.peaks(x, [356, 1085, 850 + 3 * i], [1, 2, 1.5 - 0.2 * i], [15, 8, 20]) + 0.05} for i, n in enumerate(S.SAMPLES[1:])],
            "x_label": "Raman shift (cm$^{-1}$)", "y_label": "Intensity (a.u., offset)"}


@template("raman_stacked", "Raman stacked spectra", CAT_SPEC,
          "Same mechanics as stacked XRD; normal (increasing) x.", "xy_series", {"x": "Raman shift", "series": "per sample"},
          demo_raman, {"offset": "auto", "color_by_sample": True}, "Origin: Stacked Lines by Y Offsets.", "generic", ["Raman"])
def draw_raman(d, st, p):
    return draw_xrd_stacked(d, st, p)


def demo_nmr():
    x = np.linspace(-60, -110, 800)
    comps = [{"name": "Q$^0$", "c": -71.5, "h": 1.0, "w": 2}, {"name": "Q$^1$", "c": -79, "h": 0.8, "w": 4}, {"name": "Q$^2$(1Al)", "c": -82, "h": 0.35, "w": 4}, {"name": "Q$^2$", "c": -85, "h": 0.5, "w": 4}]
    for c in comps:
        c["y"] = S.peaks(x, [c["c"]], [c["h"]], c["w"])
    tot = sum(c["y"] for c in comps); obs = tot + np.random.default_rng(1).normal(0, 0.015, len(x))
    return {"x": x, "obs": obs, "fit": tot, "components": comps, "x_label": "$^{29}$Si chemical shift (ppm)", "y_label": "Intensity (a.u.)"}


@template("nmr_29si_deconv", "Deconvolution plot (e.g. 29Si MAS NMR, XPS, DTG)", CAT_SPEC,
          "Observed, fitted sum, shaded components, residual below; reversed ppm axis when relevant.", "deconvolution",
          {"x": "x", "obs": "observed", "components": "fitted peaks (from Fitting module)"}, demo_nmr, {"reverse_x": True},
          "Origin: Peak Analyzer (Fit Peaks Pro) output graph.", "generic", ["NMR", "XPS", "DTG deconvolution"], ["component areas %, MCL = 2(Q1+Q2+1.5Q2(1Al))/Q1 (user-confirmed)"])
def draw_nmr(d, st, p):
    fig, (a, b) = new_fig(st, 2, 1, sharex=True, gridspec_kw={"height_ratios": [4, 1], "hspace": 0.05})
    a.plot(d["x"], d["obs"], "k", lw=0.8, label="Observed"); a.plot(d["x"], d["fit"], color="#C0141E", lw=0.8, label="Fit")
    for i, c in enumerate(d["components"]):
        a.fill_between(d["x"], c["y"], color=st["palette"]["series"][i + 1], alpha=0.35, lw=0, label=c["name"])
    b.plot(d["x"], d["obs"] - d["fit"], color="#555555", lw=0.5); b.set_ylabel("Res.")
    if p["reverse_x"]:
        a.set_xlim(max(d["x"]), min(d["x"]))
    a.legend(ncols=2); a.set_ylabel(d["y_label"]); b.set_xlabel(d["x_label"]); finish(a, st); finish(b, st)
    return fig


# ================================================================================================ THERMODYNAMIC MODELLING
def demo_scheil():
    T = np.linspace(1400, 1000, 120); panels = []
    for i, n in enumerate(["Sample B", "Sample C, 5 wt.%", "Sample D, 10 wt.%", "Sample F, 20 wt.%"]):
        liq = (30 + 10 * i) * np.clip((T - 950) / 500, 0, 1) ** 0.8 + 5
        al = np.full_like(T, 62 - 12 * i); be = (8 + 8 * i) + (60 - liq) * 0.4
        fe = np.where(T < 1200, (1200 - T) / 30, 0); c3a = np.where(T < 1250, (1250 - T) / 60, 0)
        panels.append({"title": n, "series": [{"name": "Liquid", "x": T, "y": liq}, {"name": "Alite, C$_3$S", "x": T, "y": al},
                                              {"name": "Belite, C$_2$S", "x": T, "y": be}, {"name": "Aluminate, C$_3$A", "x": T, "y": c3a},
                                              {"name": "Ferrite, Ca$_2$Fe$_2$O$_5$", "x": T, "y": fe}]})
    return {"panels": panels, "x_label": "Temperature (°C)", "y_label": "Phase content (wt.%)", "note": "Cooling runs from left (1400 °C) to right (1000 °C)."}


@template("phase_assemblage_vs_T_panels", "Phase evolution vs temperature (Scheil / equilibrium), multi-panel", CAT_THERMO,
          "Thermodynamic software output: one panel per composition, x reversed (cooling left→right), legend in a free cell.",
          "xy_series", {"panels": "one file per composition: T + one column per phase"}, demo_scheil, {"ncols": 3, "reverse_x": True},
          "Origin: Line plots, X From 1400 To 1000; Merge Graph Windows 2 × 3 with legend layer.", "house",
          ["thermodynamic software (Thermo-Calc, GEMS ...)"])
def draw_scheil(d, st, p):
    pan = d["panels"]; nc = p["ncols"]; nr = int(np.ceil((len(pan) + 1) / nc))
    fig, axs = new_fig(st, nr, nc, aspect=1.3, gridspec_kw={"wspace": 0.3, "hspace": 0.5}); axs = np.atleast_1d(axs).ravel()
    for k, (ax, pn) in enumerate(zip(axs, pan)):
        for i, s in enumerate(pn["series"]):
            ax.plot(s["x"], s["y"], color=series_color(st, s["name"].split(",")[0], i), label=s["name"])
        if p["reverse_x"]:
            ax.set_xlim(max(pn["series"][0]["x"]), min(pn["series"][0]["x"]))
        ax.set_ylim(bottom=0); panel_title(ax, k, pn["title"]); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); finish(ax, st)
    la = axs[len(pan)]; la.axis("off"); h, l = axs[0].get_legend_handles_labels(); la.legend(h, l, loc="upper left")
    if d.get("note"):
        la.text(0.02, 0.1, d["note"], transform=la.transAxes, fontsize=6.5, wrap=True)
    for ax in axs[len(pan) + 1:]:
        ax.axis("off")
    return fig


def demo_area():
    x = np.linspace(0, 15, 50)
    return {"x": x, "x_label": "Additive (wt.%)", "y_label": "Phase assemblage (g / 100 g)",
            "series": [{"name": "C-S-H", "y": 40 - 0.5 * x}, {"name": "Portlandite", "y": np.maximum(0, 18 - 1.2 * x)},
                       {"name": "Ettringite", "y": 8 + 0.1 * x}, {"name": "AFm", "y": 4 + 0.3 * x}, {"name": "Calcite", "y": np.full_like(x, 1.5)},
                       {"name": "Unreacted clinker", "y": 20 + 0.6 * x}, {"name": "Pore solution", "y": 10 - 0.1 * x}]}


@template("phase_assemblage_stacked_area", "Stacked-area phase assemblage (GEMS-style)", CAT_THERMO,
          "Hydrate assemblage vs replacement level, time or degree of reaction.", "xy_series",
          {"x": "replacement / time", "series": "one column per phase"}, demo_area, {}, "Origin: Plot > Area > Stacked Area.", "generic", ["GEMS", "hydration modelling"])
def draw_area(d, st, p):
    fig, ax = new_fig(st)
    ys = [s["y"] for s in d["series"]]; cols = [series_color(st, s["name"], i + 1) for i, s in enumerate(d["series"])]
    ax.stackplot(d["x"], ys, labels=[s["name"] for s in d["series"]], colors=cols, edgecolor="k", lw=0.3, alpha=0.85)
    ax.set_xlim(d["x"].min(), d["x"].max()); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", reverse=True); finish(ax, st)
    return fig


def demo_hatched():
    cats = ["Sample B\n(0)", "Sample C\n(5)", "Sample D\n(10)", "Sample E\n(15)", "Sample F\n(20)"]
    v = np.array([[30, 22, 27, 17], [24, 20, 19, 13], [44, 36, 39, 28], [51, 39, 41, 25], [61, 50, 49, 37]], float)
    return {"categories": cats, "groups": ["All oxides", "Without Na$_2$O", "Without K$_2$O", "Without Na$_2$O and K$_2$O"], "values": v,
            "markers": {"name": "Rietveld (amorphous)", "values": np.array([11, 15, 23, 32, 43])},
            "x_label": "Sample (additive, wt.%)", "y_label": "Liquid or amorphous (wt.%)", "title": "Liquid at 1400 °C"}


@template("grouped_hatched_bars_markers", "Grouped hatched bars + measured markers", CAT_THERMO,
          "Model scenarios as hatched bars, measured value as black diamonds on top; prints well in greyscale.", "category_table",
          {"categories": "clinker", "groups": "scenario columns", "markers": "last column = measured"}, demo_hatched, {},
          "Origin: Grouped Column with pattern fill + Scatter layer (diamond) on same axes.", "house", ["model scenarios"])
def draw_hatched(d, st, p):
    fig, ax = new_fig(st)
    _grouped(ax, d, st, p, hatches=[None, "////", "\\\\\\\\", "xxxx"], colors=["#555555", "#E6A800", "#5DADE2", "#D35400"])
    if d.get("markers"):
        ax.plot(np.arange(len(d["categories"])), d["markers"]["values"], "D", color="k", ms=5, label=d["markers"]["name"], mec="white")
    ax.legend(ncols=3, loc="upper left", fontsize=6.5); ax.set_ylabel(d["y_label"]); ax.set_xlabel(d["x_label"])
    if d.get("title"):
        panel_title(ax, 0, d["title"])
    finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


def demo_liq():
    T = np.linspace(1200, 1500, 100)
    return {"series": [{"name": n, "x": T, "y": np.clip((T - 1250 + 15 * i) / 3, 0, None) ** 0.9 * (1 + 0.1 * i)} for i, n in enumerate(S.SAMPLES[1:])],
            "x_label": "Temperature (°C)", "y_label": "Liquid fraction (wt.%)"}


@template("liquid_fraction_vs_T", "Liquid fraction vs temperature", CAT_THERMO,
          "Melt formation of raw meals; vertical line at sintering temperature (user-set).", "xy_series",
          {"x": "T", "series": "liquid per mix"}, demo_liq, {"vline": 1400}, "Origin: Line plot + reference line.", "generic", ["thermodynamic software"])
def draw_liq(d, st, p):
    fig, ax = new_fig(st); _xy_lines(ax, d, st)
    if p.get("vline"):
        ax.axvline(p["vline"], color="#888888", ls="--", lw=0.7)
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); finish(ax, st)
    return fig


# ================================================================================================ ENGINEERING
AGES = ["2 d", "7 d", "28 d", "90 d"]


def demo_strength():
    v = np.array([[24, 38, 52, 58], [20, 34, 49, 56], [18, 32, 47, 55], [12, 25, 41, 50], [6, 15, 30, 41], [4, 11, 24, 35]], float)
    return {"categories": S.SAMPLES, "groups": AGES, "values": v, "errors": v * 0.05, "x_label": "Mix", "y_label": "Compressive strength (MPa)"}


@template("strength_vs_age_bars", "Compressive strength by age (grouped bars ± SD)", CAT_ENG,
          "EN 196-1 style mortar prism results; bars = ages, groups = mixes; optional class lines (user-set).", "category_table",
          {"categories": "mix", "groups": "age columns", "errors": "SD table"}, demo_strength, {"class_lines": []},
          "Origin: Grouped Column + Y error; reference lines via Insert > Straight Line.", "generic", ["mechanical testing"],
          ["mean ± SD of replicates", "relative strength vs reference (%)"])
def draw_strength(d, st, p):
    fig, ax = new_fig(st); _grouped(ax, d, st, p, colors=["#C6DBEF", "#6BAED6", "#2171B5", "#08306B"])
    for v in p["class_lines"]:
        ax.axhline(v, color="#B91C1C", ls="--", lw=0.7)
    ax.set_ylabel(d["y_label"]); ax.set_xlabel(d["x_label"]); finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


def demo_str_lines():
    t = np.array([1, 2, 7, 28, 90]); return {"x_label": "Age (days)", "y_label": "Compressive strength (MPa)", "series": [
        {"name": n, "x": t, "y": (58 - 5 * i) * np.exp(-((4 + 2 * i) / t) ** 0.6), "yerr": np.full(5, 1.5)} for i, n in enumerate(S.SAMPLES)]}


@template("strength_vs_age_lines_log", "Strength development (log age)", CAT_ENG,
          "Lines + markers with SD; log age axis shows early and late age evenly.", "xy_series", {"x": "age", "series": "per mix"},
          demo_str_lines, {"log_x": True}, "Origin: Line+Symbol, X log10, Y error bars.", "generic", ["mechanical testing"])
def draw_str_lines(d, st, p):
    return draw_bw(d, st, p)


def demo_sai():
    return {"categories": ["Sample C", "Sample D", "Sample E", "Sample F"], "groups": ["7 d", "28 d", "90 d"], "values": np.array([[92, 95, 97], [74, 82, 88], [45, 58, 70], [30, 46, 60]], float),
            "x_label": "Mix", "y_label": "Relative strength (% of reference)"}


@template("strength_activity_index", "Relative strength / activity index with threshold line", CAT_ENG,
          "Strength as % of reference; threshold line value comes from the user (e.g. a standard's limit), never assumed.",
          "category_table", {"categories": "mix", "groups": "ages"}, demo_sai, {"threshold": None, "threshold_label": ""},
          "Origin: Grouped Column + labelled reference line.", "generic", ["mechanical testing"], ["100 × f(mix)/f(reference)"])
def draw_sai(d, st, p):
    fig, ax = new_fig(st); _grouped(ax, d, st, p); ax.axhline(100, color="k", lw=0.6)
    if p.get("threshold"):
        ax.axhline(p["threshold"], color="#B91C1C", ls="--", lw=0.8); ax.text(len(d["categories"]) - 0.5, p["threshold"] + 1, p.get("threshold_label", ""), color="#B91C1C", ha="right", fontsize=6.5)
    ax.set_ylabel(d["y_label"]); ax.set_xlabel(d["x_label"]); finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


def demo_setting():
    return {"categories": S.SAMPLES, "groups": ["Initial", "Final"], "values": np.array([[150, 210], [165, 230], [175, 250], [210, 300], [280, 390], [320, 450]], float),
            "x_label": "Mix", "y_label": "Time (min)"}


@template("setting_time_bar", "Setting time as floating bars (initial → final)", CAT_ENG,
          "Each bar spans initial to final set (Vicat); compact and readable.", "category_table",
          {"categories": "mix", "groups": "initial, final"}, demo_setting, {}, "Origin: Floating Column (Plot > Column > Floating Column).", "generic", ["Vicat"])
def draw_setting(d, st, p):
    fig, ax = new_fig(st); y = np.arange(len(d["categories"]))
    ax.barh(y, d["values"][:, 1] - d["values"][:, 0], left=d["values"][:, 0], color=[series_color(st, c, i) for i, c in enumerate(d["categories"])], edgecolor="k", lw=0.4, height=0.55)
    for i, (a, b) in enumerate(d["values"][:, :2]):
        ax.text(a - 4, i, f"{a:.0f}", ha="right", va="center", fontsize=6.5); ax.text(b + 4, i, f"{b:.0f}", ha="left", va="center", fontsize=6.5)
    ax.set_xlim(d["values"].min() - 40, d["values"].max() + 40)
    ax.set_yticks(y); ax.set_yticklabels(d["categories"]); ax.invert_yaxis(); ax.set_xlabel(d["y_label"]); finish(ax, st); ax.yaxis.set_minor_locator(plt.NullLocator())
    return fig


def demo_flow():
    return {"categories": S.SAMPLES, "groups": ["Flow diameter"], "values": np.array([[182], [178], [175], [170], [160], [152]], float), "errors": np.full((6, 1), 3.0),
            "x_label": "Mix", "y_label": "Flow (mm)"}


@template("flow_slump_bar", "Workability (flow / slump) bars", CAT_ENG, "One value per mix with SD.", "category_table",
          {"categories": "mix", "values": "flow"}, demo_flow, {"show_values": True}, "Origin: Column + error bars.", "generic", ["fresh properties"])
def draw_flow(d, st, p):
    return draw_grouped_bar(d, st, p)


def demo_shrink():
    t = np.array([1, 3, 7, 14, 28, 56, 90]); return {"x_label": "Drying time (days)", "y_label": "Drying shrinkage (µm m$^{-1}$)", "series": [
        {"name": n, "x": t, "y": -(600 + 60 * i) * (1 - np.exp(-t / 20)), "yerr": np.full(7, 25)} for i, n in enumerate(S.SAMPLES[1:])]}


@template("shrinkage_vs_time", "Shrinkage / expansion vs time (± band)", CAT_ENG,
          "Length change with shaded SD band instead of error bars.", "xy_series", {"x": "time", "series": "per mix", "yerr": "SD"},
          demo_shrink, {}, "Origin: Line + Y error as band (Plot Details > Error Bar > fill).", "generic", ["durability"])
def draw_shrink(d, st, p):
    fig, ax = new_fig(st)
    for i, s in enumerate(d["series"]):
        c = series_color(st, s["name"], i); ax.plot(s["x"], s["y"], "-o", color=c, label=s["name"], mfc="white")
        ax.fill_between(s["x"], s["y"] - s["yerr"], s["y"] + s["yerr"], color=c, alpha=0.15, lw=0)
    ax.axhline(0, color="k", lw=0.5); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); finish(ax, st)
    return fig


def demo_ss():
    e = np.linspace(0, 0.004, 200)
    return {"x_label": "Strain (–)", "y_label": "Stress (MPa)", "series": [
        {"name": n, "x": e, "y": np.where(e < 0.0022 + 0.0002 * i, (50 - 6 * i) * (2 * e / (0.0022 + 0.0002 * i) - (e / (0.0022 + 0.0002 * i)) ** 2),
                                         np.maximum(0, (50 - 6 * i) * (1 - 180 * (e - 0.0022 - 0.0002 * i))))} for i, n in enumerate(["Sample B", "Sample D", "Sample F"])]}


@template("stress_strain", "Stress–strain curves", CAT_ENG, "Uniaxial compression curves; peak and modulus annotated on request.",
          "xy_series", {"x": "strain", "series": "stress per specimen/mix"}, demo_ss, {}, "Origin: Line plot.", "generic", ["mechanical testing"],
          ["E-modulus = slope 10–40 % f_c (user-confirmed)"])
def draw_ss(d, st, p):
    fig, ax = new_fig(st); _xy_lines(ax, d, st); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); ax.set_ylim(bottom=0); finish(ax, st)
    return fig


def demo_abrams():
    wc = np.array([0.35, 0.4, 0.45, 0.5, 0.55, 0.6]); return {"x_label": "w/c ratio (–)", "y_label": "28-d compressive strength (MPa)",
            "points": [{"name": "Measured", "x": wc, "y": 120 / 8 ** wc + np.random.default_rng(2).normal(0, 1.5, 6)}]}


@template("abrams_wc_strength", "Strength vs w/c with Abrams-type fit", CAT_ENG,
          "f = A / B^(w/c) fitted; equation printed; points from user's mixes.", "scatter", {"x": "w/c", "y": "strength"}, demo_abrams, {},
          "Origin: Nonlinear Curve Fit with user-defined function A/B^x.", "generic", ["mix design"], ["nonlinear least squares A, B"])
def draw_abrams(d, st, p):
    from scipy.optimize import curve_fit
    fig, ax = new_fig(st, width="single", aspect=1.35); q = d["points"][0]
    (A, B), _ = curve_fit(lambda x, A, B: A / B ** x, q["x"], q["y"], p0=[100, 5]); xx = np.linspace(q["x"].min(), q["x"].max(), 100)
    ax.plot(q["x"], q["y"], "o", color="k", label=q["name"]); ax.plot(xx, A / B ** xx, "--", color="#1F77B4", label=f"f = {A:.0f} / {B:.1f}$^{{w/c}}$")
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); finish(ax, st)
    return fig


def demo_carb():
    t = np.array([0, 7, 28, 56, 90]); return {"x_label": "√t (√days)", "y_label": "Carbonation depth (mm)", "series": [
        {"name": n, "x": np.sqrt(t), "y": (0.8 + 0.3 * i) * np.sqrt(t) + np.random.default_rng(i).normal(0, 0.2, 5)} for i, n in enumerate(S.SAMPLES[1:4])]}


@template("carbonation_depth_sqrt_t", "Carbonation depth vs √t with k coefficient", CAT_ENG,
          "Linear fit through origin per mix; slope = carbonation coefficient k (mm/√day or mm/√year, user unit).",
          "xy_series", {"x": "time (converted to √t)", "series": "depth per mix"}, demo_carb, {}, "Origin: Linear Fit with fixed intercept 0.",
          "generic", ["durability"], ["k = slope of depth vs √t"])
def draw_carb(d, st, p):
    fig, ax = new_fig(st)
    for i, s in enumerate(d["series"]):
        c = series_color(st, s["name"], i); k = np.sum(s["x"] * s["y"]) / np.sum(s["x"] ** 2)
        ax.plot(s["x"], s["y"], "o", color=c, mfc="white"); ax.plot(s["x"], k * s["x"], "-", color=c, label=f"{s['name']}: k = {k:.2f}")
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); finish(ax, st)
    return fig


def demo_cl():
    x = np.linspace(1, 30, 10); from scipy.special import erfc
    return {"x_label": "Depth (mm)", "y_label": "Chloride (wt.% of binder)", "points": [
        {"name": n, "x": x, "y": (0.9 - 0.1 * i) * erfc(x / 1000 / (2 * np.sqrt((8 - 2 * i) * 1e-12 * 90 * 86400))) + 0.03} for i, n in enumerate(["Sample B", "Sample D", "Sample F"])]}


@template("chloride_profile", "Chloride profile with Fick's 2nd-law fit", CAT_ENG,
          "Profile points + erfc fit; apparent D and Cs reported in legend.", "scatter", {"x": "depth", "y": "chloride", "group": "mix"},
          demo_cl, {"exposure_days": 90}, "Origin: Nonlinear fit with erfc user function.", "generic", ["durability"], ["C(x)=Cs·erfc(x/(2√(D·t)))+Ci"])
def draw_cl(d, st, p):
    from scipy.optimize import curve_fit
    from scipy.special import erfc
    fig, ax = new_fig(st); t = p["exposure_days"] * 86400
    for i, q in enumerate(d["points"]):
        c = series_color(st, q["name"], i); f = lambda x, Cs, D: Cs * erfc(x / 1000 / (2 * np.sqrt(D * 1e-12 * t))) + 0.03
        (Cs, D), _ = curve_fit(f, q["x"], q["y"], p0=[0.8, 5]); xx = np.linspace(0, q["x"].max(), 100)
        ax.plot(q["x"], q["y"], "o", color=c, mfc="white"); ax.plot(xx, f(xx, Cs, D), color=c, label=f"{q['name']}: D = {D:.1f}×10$^{{-12}}$ m$^2$/s")
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); finish(ax, st)
    return fig


def demo_fcao():
    return {"categories": S.SAMPLES, "groups": ["f-CaO"], "values": np.array([[0.79], [0.76], [0.71], [0.54], [0.32], [np.nan]]),
            "errors": np.array([[0.04], [0.04], [0.035], [0.03], [0.015], [0]]), "x_label": "", "y_label": "f-CaO (wt.%)", "missing_text": "n.d."}


@template("free_lime_bar", "Single-quantity bars with SD and 'not detected' marking", CAT_ENG,
          "Free lime (or any titration result); missing values shown as 'n.d.' text, not as zero.", "category_table",
          {"categories": "sample", "values": "one column", "errors": "SD"}, demo_fcao, {}, "Origin: Column + error bars + text label.", "house", ["f-CaO", "any single quantity"])
def draw_fcao(d, st, p):
    fig, ax = new_fig(st); v = d["values"][:, 0]; x = np.arange(len(v))
    ax.bar(x, np.nan_to_num(v), yerr=d["errors"][:, 0], capsize=3, color="#1F6E8C", edgecolor="k", lw=0.4, width=0.6)
    for i, vv in enumerate(v):
        if np.isnan(vv):
            ax.text(i, 0.01 * np.nanmax(v), d.get("missing_text", "n.d."), ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(d["categories"]); ax.set_ylabel(d["y_label"]); finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


# ================================================================================================ MICRO / SEM-EDS
def demo_eds():
    r = np.random.default_rng(3); n = 300
    si = np.clip(r.normal(0.55, 0.08, n), 0.1, 1); al = np.clip(r.normal(0.06, 0.03, n) + 0.1 * (r.random(n) < 0.2), 0, 0.7)
    return {"points": [{"name": "Sample B", "x": si, "y": al}, {"name": "Sample F", "x": si * 1.1, "y": al * 1.3}],
            "refs": [{"name": "CH", "x": 0, "y": 0}, {"name": "AFt", "x": 0, "y": 0.33}, {"name": "AFm", "x": 0, "y": 0.5}],
            "x_label": "Si/Ca (atomic ratio)", "y_label": "Al/Ca (atomic ratio)"}


@template("eds_atomic_ratio", "SEM-EDS atomic ratio plot (Al/Ca vs Si/Ca)", CAT_MICRO,
          "Point analyses of C-(A-)S-H; reference phase positions supplied by the user; density colouring optional.", "scatter",
          {"x": "Si/Ca", "y": "Al/Ca", "group": "sample", "refs": "user-confirmed reference compositions"}, demo_eds, {},
          "Origin: Scatter with transparency + labelled reference points.", "generic", ["SEM-EDS"], ["atomic ratios from at.% columns"])
def draw_eds(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.25)
    for i, q in enumerate(d["points"]):
        ax.plot(q["x"], q["y"], "o", ms=2, alpha=0.4, color=series_color(st, q["name"], i), label=q["name"], mec="none")
    for r in d.get("refs", []):
        ax.plot(r["x"], r["y"], "k*", ms=7); ax.annotate(r["name"], (r["x"], r["y"]), xytext=(4, 2), textcoords="offset points", fontsize=6.5)
    ax.set_xlim(left=-0.02); ax.set_ylim(bottom=-0.02); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(markerscale=2.5); finish(ax, st)
    return fig


def demo_sem():
    r = np.random.default_rng(0); imgs = []
    for i in range(4):
        z = r.random((200, 300)); from scipy.ndimage import gaussian_filter
        imgs.append(gaussian_filter(z, 3 + i))
    return {"images": imgs, "titles": ["Sample B, BSE", "Sample D, BSE", "Sample F, BSE", "Sample F, EDS Ca map"], "scale_um": 50, "px_um": 0.5}


@template("sem_panel_layout", "SEM / optical image panel grid with scale bars", CAT_MICRO,
          "2 × 2 image grid, (a)–(d) labels on white boxes, scale bars drawn from pixel size (from image metadata or user).",
          "image_grid", {"images": "image files", "px_um": "pixel size", "titles": "panel captions"}, demo_sem, {"ncols": 2},
          "Origin: Image graphs merged; or insert pictures into a layout page.", "generic", ["SEM", "optical microscopy"])
def draw_sem(d, st, p):
    nc = p["ncols"]; nr = int(np.ceil(len(d["images"]) / nc)); fig, axs = new_fig(st, nr, nc, aspect=1.45, gridspec_kw={"wspace": 0.03, "hspace": 0.03})
    for k, (ax, im) in enumerate(zip(np.atleast_1d(axs).ravel(), d["images"])):
        ax.imshow(im, cmap="gray"); ax.set_xticks([]); ax.set_yticks([])
        ax.text(0.02, 0.96, f"({'abcd'[k]}) {d['titles'][k]}", transform=ax.transAxes, va="top", fontsize=6.5, fontweight="bold", bbox=dict(fc="white", ec="none", pad=1.5))
        L = d["scale_um"] / d["px_um"]; h, w = im.shape; ax.add_patch(Rectangle((w - L - 12, h - 16), L, 5, color="white"))
        ax.text(w - L / 2 - 12, h - 20, f"{d['scale_um']} µm", color="white", ha="center", fontsize=6)
    return fig


# ================================================================================================ SUSTAINABILITY
def demo_co2():
    return {"categories": ["Baseline", "Sample D", "Alt-CaO clinker"], "groups": ["Calcination", "Fuel", "Electricity"],
            "values": np.array([[520, 300, 50], [480, 290, 50], [40, 300, 55]], float), "x_label": "", "y_label": "CO$_2$ (kg t$^{-1}$ clinker)"}


@template("co2_emissions_stacked", "CO2 per tonne clinker (stacked by source)", CAT_SUS,
          "Process vs fuel vs electricity emissions; totals printed above bars. All factors from the user.", "category_table",
          {"categories": "scenario", "groups": "emission source"}, demo_co2, {"totals": True, "sum_to_100": False}, "Origin: Stacked Column + labels.", "generic", ["LCA"])
def draw_co2(d, st, p):
    fig = draw_qpa_stacked(d, st, p); ax = fig.axes[0]; tot = np.nansum(d["values"], 1)
    for i, t in enumerate(tot):
        ax.text(i, t + 10, f"{t:.0f}", ha="center", fontsize=7, fontweight="bold")
    ax.set_ylim(0, tot.max() * 1.15)
    return fig


def demo_wf():
    return {"steps": [("Reference", 870), ("Replace raw material", -480), ("Lower kiln T", -25), ("Fuel switch", -60), ("Result", None)], "y_label": "CO$_2$ (kg t$^{-1}$)"}


@template("waterfall_co2", "Waterfall chart (step-wise reduction)", CAT_SUS, "Shows contribution of each measure to a total change.",
          "steps", {"steps": "label + delta; first = start, last = result"}, demo_wf, {}, "Origin: Plot > Column > Waterfall.", "generic", ["LCA", "cost"])
def draw_wf(d, st, p):
    fig, ax = new_fig(st); run = 0
    for i, (lab, v) in enumerate(d["steps"]):
        if i == 0 or v is None:
            v0 = run if v is None else v; ax.bar(i, v0, color="#17324D"); run = v0 if i == 0 else run; ax.text(i, v0 + 10, f"{v0:.0f}", ha="center", fontsize=7)
        else:
            ax.bar(i, v, bottom=run, color="#15803D" if v < 0 else "#B91C1C"); ax.text(i, run + 10, f"{v:+.0f}", ha="center", fontsize=7); run += v
    ax.set_xticks(range(len(d["steps"]))); ax.set_xticklabels([s[0] for s in d["steps"]], fontsize=7); ax.set_ylabel(d["y_label"]); finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


# ================================================================================================ GENERAL
def demo_fit():
    x = np.linspace(0, 15, 12); r = np.random.default_rng(5)
    return {"series": [{"name": "Data", "x": x, "y": 57 - 3.1 * x + r.normal(0, 3, len(x))}], "x_label": "Additive (wt.%)", "y_label": "Alite (wt.%)"}


@template("scatter_linear_fit", "Scatter + linear fit with 95 % confidence band", CAT_GEN,
          "Correlation between two measured quantities; equation and R² in legend.", "xy_series", {"x": "x", "y": "y"}, demo_fit,
          {"ci": True, "show_equation": True}, "Origin: Linear Fit with Confidence Bands checked.", "generic", ["any"], ["OLS slope, intercept, R², 95 % CI"])
def draw_scatter_fit(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.35); s = d["series"][0]; x, y = np.asarray(s["x"], float), np.asarray(s["y"], float)
    b, a = np.polyfit(x, y, 1); yh = a + b * x; r2 = 1 - np.sum((y - yh) ** 2) / np.sum((y - y.mean()) ** 2)
    xx = np.linspace(x.min(), x.max(), 100); ax.plot(x, y, "o", color="k", mfc="white", label=s["name"])
    ax.plot(xx, a + b * xx, color="#C0141E", label=f"y = {b:.3g}x + {a:.3g}, R$^2$ = {r2:.3f}" if p.get("show_equation") else "Fit")
    if p.get("ci"):
        n = len(x); se = np.sqrt(np.sum((y - yh) ** 2) / (n - 2)); from scipy.stats import t as tt
        h = tt.ppf(0.975, n - 2) * se * np.sqrt(1 / n + (xx - x.mean()) ** 2 / np.sum((x - x.mean()) ** 2)); ax.fill_between(xx, a + b * xx - h, a + b * xx + h, color="#C0141E", alpha=0.12, lw=0)
    ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"]); ax.legend(); finish(ax, st)
    return fig


def demo_corr():
    names = ["Additive", "Alite", "Belite", "Amorphous", "f-CaO", "Q$_{168}$"]; r = np.random.default_rng(1); M = r.uniform(-1, 1, (6, 6)); M = (M + M.T) / 2; np.fill_diagonal(M, 1)
    return {"labels": names, "matrix": M}


@template("correlation_heatmap", "Correlation matrix heatmap", CAT_GEN, "Pearson r between variables; values printed in cells.", "matrix",
          {"table": "samples × variables"}, demo_corr, {}, "Origin: Statistics > Correlation Coefficient → Heatmap.", "generic", ["statistics"], ["Pearson / Spearman r"])
def draw_corr(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.15); M = d["matrix"]; im = ax.imshow(M, cmap="RdBu_r", vmin=-1, vmax=1)
    for i in range(len(M)):
        for j in range(len(M)):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=6, color="white" if abs(M[i, j]) > 0.6 else "k")
    ax.set_xticks(range(len(M))); ax.set_yticks(range(len(M))); ax.set_xticklabels(d["labels"], rotation=45, ha="right"); ax.set_yticklabels(d["labels"])
    fig.colorbar(im, ax=ax, fraction=0.046).set_label("r")
    return fig


def demo_box():
    r = np.random.default_rng(2); return {"groups": [{"name": n, "values": r.normal(50 - 5 * i, 2 + 0.3 * i, 6)} for i, n in enumerate(S.SAMPLES)], "y_label": "Compressive strength (MPa)"}


@template("box_strip", "Box plot with individual points", CAT_GEN, "Replicate spread; every specimen visible.", "groups",
          {"groups": "one column per group (replicates in rows)"}, demo_box, {}, "Origin: Box Chart with data overlap.", "generic", ["replicates"])
def draw_box(d, st, p):
    fig, ax = new_fig(st); vals = [g["values"] for g in d["groups"]]
    ax.boxplot(vals, widths=0.5, medianprops=dict(color="k"), showfliers=False)
    for i, g in enumerate(d["groups"]):
        ax.plot(np.full(len(g["values"]), i + 1) + np.random.default_rng(i).uniform(-0.08, 0.08, len(g["values"])), g["values"], "o", ms=3, color=series_color(st, g["name"], i), alpha=0.8)
    ax.set_xticks(range(1, len(vals) + 1)); ax.set_xticklabels([g["name"] for g in d["groups"]]); ax.set_ylabel(d["y_label"]); finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


def demo_dual():
    x = np.array([0, 5, 10, 15, 20]); return {"x_label": "Additive (wt.%)", "series": [{"name": "Alite (wt.%)", "x": x, "y": np.array([60, 55, 48, 40, 30])}],
                                             "series2": [{"name": "Q$_{168}$ (J g$^{-1}$)", "x": x, "y": np.array([150, 145, 85, 7, 2])}]}


@template("dual_y_axis", "Double-Y graph (two quantities, one x)", CAT_GEN, "Left and right axes coloured like their series.", "xy_series",
          {"x": "shared x", "series": "left", "series2": "right"}, demo_dual, {}, "Origin: Plot > Multi-Curve > Double-Y.", "generic", ["any"])
def draw_dual(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.35); ax2 = ax.twinx(); c1, c2 = "#1F77B4", "#D62728"
    s = d["series"][0]; t = d["series2"][0]; ax.plot(s["x"], s["y"], "-o", color=c1); ax2.plot(t["x"], t["y"], "--s", color=c2, mfc="white")
    ax.set_ylabel(s["name"], color=c1); ax2.set_ylabel(t["name"], color=c2); ax.tick_params(axis="y", colors=c1); ax2.tick_params(axis="y", colors=c2, direction=st["axes"]["tick_direction"])
    ax.set_xlabel(d["x_label"]); finish(ax, st); ax.tick_params(right=False)
    return fig


def demo_broken():
    x, y = S.xrd_pattern(2); y[np.argmin(abs(x - 27.4)) - 5: np.argmin(abs(x - 27.4)) + 5] += 15000
    return {"series": [{"name": "Material 1", "x": x, "y": y}], "x_label": "2θ (°), Cu Kα", "y_label": "Counts", "break": [2500, 14000]}


@template("broken_axis", "Broken y axis (one dominant peak)", CAT_GEN, "Keeps a dominant peak (e.g. quartz, rutile) without flattening the rest.",
          "xy_series", {"x": "x", "y": "y", "break": "user-set lower/upper"}, demo_broken, {}, "Origin: Axis dialog > Breaks tab.", "generic", ["XRD", "any"])
def draw_broken(d, st, p):
    fig, (a, b) = new_fig(st, 2, 1, sharex=True, gridspec_kw={"height_ratios": [1, 3], "hspace": 0.06}); s = d["series"][0]
    if d.get("break"): lo, hi = d["break"]
    else:                       # no break given: just above the 99th percentile, up to 60 % of the highest point
        yy = s["y"][np.isfinite(s["y"])]; lo = float(np.percentile(yy, 99)) * 1.1; hi = max(float(yy.max()) * 0.6, lo * 1.05)
    for ax in (a, b):
        ax.plot(s["x"], s["y"], "k", lw=0.6); finish(ax, st)
    a.set_ylim(hi, s["y"].max() * 1.05); b.set_ylim(0, lo); a.spines["bottom"].set_visible(False); b.spines["top"].set_visible(False); a.tick_params(bottom=False, labelbottom=False)
    kw = dict(marker=[(-1, -0.5), (1, 0.5)], ms=8, ls="none", color="k", mec="k", mew=0.8, clip_on=False)
    a.plot([0, 1], [0, 0], transform=a.transAxes, **kw); b.plot([0, 1], [1, 1], transform=b.transAxes, **kw)
    b.set_xlabel(d["x_label"]); b.set_ylabel(d["y_label"]); b.yaxis.set_label_coords(-0.07, 0.65)
    return fig


def demo_contour():
    x = np.linspace(0, 15, 60); y = np.linspace(1350, 1500, 60); X, Y = np.meshgrid(x, y)
    return {"x": x, "y": y, "z": 60 - 3 * X + 0.15 * (Y - 1350) - 0.002 * (Y - 1400) ** 2, "x_label": "Additive (wt.%)", "y_label": "Sintering temperature (°C)", "z_label": "Alite (wt.%)"}


@template("contour_response_surface", "Contour response surface (two factors)", CAT_GEN,
          "Design-of-experiments / optimisation map with labelled iso-lines.", "matrix", {"x": "factor 1", "y": "factor 2", "z": "response grid"},
          demo_contour, {"levels": 10}, "Origin: Contour from XYZ (Plot > Contour > Color Fill).", "generic", ["optimisation"])
def draw_contour(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.3); cs = ax.contourf(d["x"], d["y"], d["z"], levels=p["levels"], cmap="viridis")
    cl = ax.contour(d["x"], d["y"], d["z"], levels=p["levels"], colors="k", linewidths=0.4); ax.clabel(cl, fontsize=5.5)
    fig.colorbar(cs, ax=ax).set_label(d["z_label"]); ax.set_xlabel(d["x_label"]); ax.set_ylabel(d["y_label"])
    return fig

"""Tier 1 of the catalogue of graph types: kinetics (isoconversional lines, Friedman), reference stick rows, log-time
calorimetry, phase evolution, method comparisons and the other first-priority types. Illustrative data only."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from .core import template, new_fig, finish, panel_title, series_color, distinct_colors, make_fig, fig_size
from . import kinetics as K
from .templates_materials import _tern, CAT_XRD, CAT_TH, CAT_CAL, CAT_PHASE, CAT_ENG, CAT_MICRO, CAT_SUS, CAT_THERMO

MK = "osD^vP*X"


def _xy(ax, d, st, markers=True, line=True, err=True, colours=None):
    cols = colours or distinct_colors(st, [s["name"] for s in d["series"]])
    for i, (s, c) in enumerate(zip(d["series"], cols)):
        kw = dict(color=c, label=s["name"], marker=MK[i % 8] if markers else None, mfc="white", ls="-" if line else "none")
        if err and "yerr" in s and np.any(np.asarray(s["yerr"]) > 0): ax.errorbar(s["x"], s["y"], yerr=s["yerr"], capsize=st["lines"]["errorbar_capsize_pt"], **kw)
        else: ax.plot(s["x"], s["y"], **kw)
    ax.set_xlabel(d.get("x_label", "")); ax.set_ylabel(d.get("y_label", ""))
    if len(d["series"]) > 1 or d["series"][0]["name"]: ax.legend()


def _linfit(ax, x, y, st, band=True):
    """Least squares line with R2; returns (slope, intercept, r2)."""
    x, y = np.asarray(x, float), np.asarray(y, float); ok = np.isfinite(x) & np.isfinite(y); x, y = x[ok], y[ok]
    if len(x) < 3 or np.ptp(x) == 0: return None
    sl, ic, se, r2 = K._fit(x, y); xx = np.linspace(x.min(), x.max(), 60); ax.plot(xx, sl * xx + ic, color="#C0141E", lw=st["lines"]["width_pt"], label=f"y = {sl:.3g} x + {ic:.3g},  R$^2$ = {r2:.3f}")
    return sl, ic, r2


# ------------------------------------------------------------------------------------------------ kinetics
def demo_runs():
    cs = []
    for b in (2, 5, 10, 20):
        T, a, _ = K.simulate_first_order(180.0, 1e10, b, 600, 1200); cs.append({"beta": b, "T": T, "alpha": a})
    return {"curves": cs, "x_label": "Temperature (°C)", "y_label": "Conversion α"}


@template("ofw_kas_plot", "Isoconversional lines (OFW / KAS) for α = 0.1 … 0.9", CAT_TH, "One straight line per conversion level from runs at three or more heating rates; the slopes give Eα.",
          "kinetics", {"T": "temperature", "alpha per heating rate": "one conversion column per run (the heating rate is read from the header)"}, demo_runs, {"method": "KAS"},
          "Origin: scatter + Linear Fit per conversion level (Analysis > Fitting > Linear Fit).", "generic", ["thermal kinetics", "TGA", "DSC"],
          ["T at each α by interpolation", "OFW: ln β vs 1/T, slope = −1.052 E/R", "KAS: ln(β/T²) vs 1/T, slope = −E/R"])
def draw_ofw_kas(d, st, p):
    r = K.isoconversional(d["curves"]); m = "OFW" if str(p.get("method", "KAS")).upper().startswith("O") else "KAS"
    fig, ax = new_fig(st); cm = plt.get_cmap("viridis")
    for i, (a, q) in enumerate(zip(r["alpha"], r[m])):
        c = cm(i / max(1, len(r["alpha"]) - 1)); ax.plot(q["x"], q["y"], "o", color=c, mfc="white"); xx = np.array([q["x"].min(), q["x"].max()])
        ax.plot(xx, q["slope"] * xx / 1000 + q["intercept"], color=c, label=f"α = {a:.1f}:  {q['Ea_kJ_mol']:.0f} ± {q['se_kJ_mol']:.0f} kJ mol$^{{-1}}$")
    ax.set_xlabel("1000/T (K$^{-1}$)"); ax.set_ylabel("ln β" if m == "OFW" else "ln(β/T$^2$)"); ax.legend(fontsize=st["font"]["size_pt"]["legend"] - 1, ncol=2); finish(ax, st)
    return fig


@template("friedman_plot", "Friedman plot: ln(dα/dt) vs 1/T at each conversion", CAT_TH, "Differential isoconversional method; no approximation of the temperature integral.",
          "kinetics", {"T": "temperature", "alpha per heating rate": "one conversion column per run (the heating rate is read from the header)"}, demo_runs, {},
          "Origin: scatter + Linear Fit per conversion level.", "generic", ["thermal kinetics"], ["dα/dt = β dα/dT", "ln(dα/dt) vs 1/T, slope = −E/R"])
def draw_friedman(d, st, p):
    r = K.isoconversional(d["curves"]); fig, ax = new_fig(st); cm = plt.get_cmap("viridis")
    for i, (a, q) in enumerate(zip(r["alpha"], r["Friedman"])):
        c = cm(i / max(1, len(r["alpha"]) - 1)); ax.plot(q["x"], q["y"], "s", color=c, mfc="white"); xx = np.array([q["x"].min(), q["x"].max()])
        ax.plot(xx, q["slope"] * xx / 1000 + q["intercept"], color=c, label=f"α = {a:.1f}:  {q['Ea_kJ_mol']:.0f} ± {q['se_kJ_mol']:.0f} kJ mol$^{{-1}}$")
    ax.set_xlabel("1000/T (K$^{-1}$)"); ax.set_ylabel("ln(dα/dt) (min$^{-1}$)"); ax.legend(fontsize=st["font"]["size_pt"]["legend"] - 1, ncol=2); finish(ax, st)
    return fig


# ------------------------------------------------------------------------------------------------ diffraction
def demo_ref_ticks():
    from . import synthetic as S
    x, y = S.xrd_pattern(2); return {"series": [{"name": "pattern", "x": x, "y": y}], "x_label": "2θ (°), Cu Kα", "y_label": "Intensity (counts)",
                                      "sticks": {k: v for k, v in list(S.XRD_PHASES.items())[:4]}}


@template("xrd_ref_ticks", "Pattern(s) with reference stick rows per phase", CAT_XRD, "Measured pattern above one row of reference positions per phase. The positions come from your peak list or reference file.",
          "xy_series", {"x": "2θ", "y": "intensity per pattern", "sticks": "phase name + position from a second table (a peak list); none in the file = no rows"}, demo_ref_ticks, {"row_height": 0.06},
          "Origin: line plot + one scatter layer per phase with vertical-bar symbols (Plot Details > Symbol).", "generic", ["XRD", "phase identification"])
def draw_ref_ticks(d, st, p):
    sticks = d.get("sticks") or {}; n = len(sticks)
    fig, (a, b) = new_fig(st, 2, 1, sharex=True, gridspec_kw={"height_ratios": [1, max(0.12, p["row_height"] * max(1, n) * 2.2)], "hspace": 0.04})
    cols = distinct_colors(st, [s["name"] for s in d["series"]], start=0)
    for s, c in zip(d["series"], cols): a.plot(s["x"], s["y"], color=c, lw=0.7, label=s["name"])
    a.set_ylabel(d.get("y_label", "")); finish(a, st); a.tick_params(labelbottom=False)
    if len(d["series"]) > 1: a.legend()
    pc = distinct_colors(st, list(sticks), start=1)
    for i, ((ph, pos), c) in enumerate(zip(sticks.items(), pc)):
        b.plot(pos, np.full(len(pos), n - i), "|", color=c, ms=7, mew=1.0); b.text(1.005, n - i, str(ph), transform=b.get_yaxis_transform(), va="center", ha="left", fontsize=st["font"]["size_pt"]["annotation"], color=c)
    b.set_ylim(0.3, n + 0.7); b.set_yticks([]); b.set_xlabel(d.get("x_label", "")); finish(b, st, minor=False)
    if not n: b.text(0.5, 0.5, "no reference positions in the file", transform=b.transAxes, ha="center", va="center", fontsize=6, color="#8A97A8")
    return fig


def demo_area_t():
    t = np.array([0.5, 1, 3, 7, 28, 90.0]); return {"series": [{"name": "Phase 1", "x": t, "y": 100 * np.exp(-t / 9), "yerr": np.full(6, 3.0)}, {"name": "Phase 2", "x": t, "y": 60 * (1 - np.exp(-t / 5)), "yerr": np.full(6, 2.5)}],
                                                    "x_label": "Time (days)", "y_label": "Integrated peak area (a.u.)"}


@template("xrd_peak_area_vs_t", "Integrated peak area or phase amount against time or temperature", CAT_XRD, "How a reflection (or a phase) grows or disappears with time or temperature.",
          "xy_series", {"x": "time or temperature", "y": "area or amount per phase", "yerr": "optional"}, demo_area_t, {"logx": True},
          "Origin: Line + Symbol with Y error; X axis log10.", "generic", ["in-situ XRD", "hydration"], ["peak integration (Analysis > Peaks) when areas are not in the file"])
def draw_area_t(d, st, p):
    fig, ax = new_fig(st); _xy(ax, d, st)
    if p.get("logx") and all(np.all(np.asarray(s["x"]) > 0) for s in d["series"]): ax.set_xscale("log")
    finish(ax, st); return fig


# ------------------------------------------------------------------------------------------------ calorimetry and hydration
def demo_cal_log():
    from . import synthetic as S
    t = np.logspace(-1.3, 2.2, 1500); return {"series": [{"name": n, "x": t, "y": S.heat_flow(t, 2.4 - 0.3 * i, 9 + 2 * i, 5, seed=i)} for i, n in enumerate(S.SAMPLES[:4])], "x_label": "Time (h)", "y_label": "Heat flow (mW g$^{-1}$)"}


@template("calorimetry_log_time", "Heat flow on a logarithmic time axis", CAT_CAL, "Shows the first minutes and the long tail in one graph; stages can be marked by you.",
          "xy_series", {"x": "time", "y": "heat flow per sample"}, demo_cal_log, {"stages": []}, "Origin: Line plot, X axis log10 (Axis dialog > Scale > Type).", "generic", ["isothermal calorimetry"])
def draw_cal_log(d, st, p):
    fig, ax = new_fig(st); _xy(ax, d, st, markers=False)
    ax.set_xscale("log")
    for t0, t1, name in (p.get("stages") or []): ax.axvspan(t0, t1, color="#EEF2F7", zorder=0); ax.text(np.sqrt(t0 * t1), 0.97, name, transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=st["font"]["size_pt"]["annotation"])
    finish(ax, st); return fig


def demo_sulfate():
    from . import synthetic as S
    t = np.linspace(0.05, 72, 1500); return {"series": [{"name": f"{v:g} %", "x": t, "y": S.heat_flow(t, 2.2, 8 + 1.5 * i, 5, seed=i) + 0.5 * np.exp(-0.5 * ((t - 14 - 5 * i) / 3) ** 2), "param": v} for i, v in enumerate([2.0, 2.5, 3.0, 3.5, 4.0])],
                                             "x_label": "Time (h)", "y_label": "Heat flow (mW g$^{-1}$)", "param_label": "Sulfate (wt.% SO$_3$)"}


@template("sulfate_balance", "Heat-flow curves against sulfate dosage", CAT_CAL, "Overlays coloured by the dosage: the position of the sulfate-depletion shoulder shows the balance.",
          "xy_series", {"x": "time", "y": "heat flow per dosage (the dosage is read from the header)"}, demo_sulfate, {}, "Origin: Line plot with Colour Mapped lines (Plot Details > Line > Colour > By Points / Map).", "generic", ["sulfate optimisation"])
def draw_sulfate(d, st, p):
    fig, ax = new_fig(st); v = np.array([s.get("param", i) for i, s in enumerate(d["series"])], float); cm = plt.get_cmap("viridis"); lo, hi = v.min(), v.max()
    for s, q in zip(d["series"], v): ax.plot(s["x"], s["y"], color=cm((q - lo) / (hi - lo) if hi > lo else 0.5), label=s["name"])
    ax.set_xlabel(d.get("x_label", "")); ax.set_ylabel(d.get("y_label", "")); ax.legend(title=d.get("param_label") or None); finish(ax, st); return fig


def demo_doh():
    t = np.array([1, 3, 7, 28, 90.0]); return {"series": [{"name": m, "x": t, "y": 100 * (1 - np.exp(-(t / (4 + i)) ** 0.6)) * (0.9 - 0.04 * i), "yerr": np.full(5, 2.5)} for i, m in enumerate(["Method 1", "Method 2", "Method 3"])],
                                               "x_label": "Time (days)", "y_label": "Degree of reaction (%)"}


@template("hydration_degree", "Degree of reaction against time (methods compared)", CAT_CAL, "The same quantity from several methods on one time axis, with error bars.",
          "xy_series", {"x": "time", "y": "degree of reaction per method", "yerr": "optional"}, demo_doh, {"logx": True}, "Origin: Line + Symbol with Y error; X axis log10.", "generic", ["hydration", "reactivity"])
def draw_doh(d, st, p):
    fig, ax = new_fig(st); _xy(ax, d, st)
    if p.get("logx") and all(np.all(np.asarray(s["x"]) > 0) for s in d["series"]): ax.set_xscale("log")
    finish(ax, st); return fig


def _scatter_fit(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.35); cols = distinct_colors(st, [s["name"] for s in d["series"]], start=0); X, Y = [], []
    for i, (s, c) in enumerate(zip(d["series"], cols)): ax.plot(s["x"], s["y"], MK[i % 8], color=c, mfc="white", label=s["name"] if len(d["series"]) > 1 else None); X += list(s["x"]); Y += list(s["y"])
    if p.get("fit", True): _linfit(ax, X, Y, st)
    ax.set_xlabel(d.get("x_label", "")); ax.set_ylabel(d.get("y_label", "")); ax.legend(); finish(ax, st); return fig


def demo_sq():
    r = np.random.default_rng(3); q = np.array([80, 140, 190, 240, 290, 330.0]); return {"series": [{"name": "", "x": q, "y": 0.16 * q - 6 + r.normal(0, 1.5, 6)}], "x_label": "Cumulative heat (J g$^{-1}$)", "y_label": "Compressive strength (MPa)"}


@template("strength_vs_cumheat", "Strength against cumulative heat (or degree of reaction)", CAT_CAL, "A straight line through strength and heat links the calorimeter to the press.",
          "xy_series", {"x": "cumulative heat or α", "y": "strength"}, demo_sq, {"fit": True}, "Origin: Scatter + Linear Fit.", "generic", ["calorimetry", "mechanical testing"], ["least squares line, R²"])
def draw_sq(d, st, p): return _scatter_fit(d, st, p)


def demo_r3():
    r = np.random.default_rng(5); bw = np.array([2.1, 3.4, 4.8, 6.0, 7.5, 9.1]); return {"series": [{"name": "", "x": bw, "y": 55 * bw + 20 + r.normal(0, 12, 6)}], "x_label": "Bound water (g per 100 g)", "y_label": "Heat at 7 d (J g$^{-1}$)"}


@template("r3_heat_vs_bw", "Reactivity test: heat against bound water", CAT_CAL, "The two outputs of a reactivity test against each other, with the regression line.",
          "xy_series", {"x": "bound water", "y": "heat"}, demo_r3, {"fit": True}, "Origin: Scatter + Linear Fit.", "generic", ["reactivity of additions"], ["least squares line, R²"])
def draw_r3(d, st, p): return _scatter_fit(d, st, p)


# ------------------------------------------------------------------------------------------------ phases and composition
def demo_age_area():
    t = np.array([0.01, 0.5, 1, 3, 7, 28, 90.0]); f = 1 - np.exp(-(t / 3) ** 0.7)
    return {"x": t, "x_label": "Age (days)", "y_label": "Phase content (g per 100 g)", "series": [{"name": n, "y": y} for n, y in (("Anhydrous 1", 55 * (1 - f)), ("Anhydrous 2", 18 * (1 - 0.6 * f)), ("Hydrate 1", 45 * f), ("Hydrate 2", 14 * f), ("Hydrate 3", 9 * f ** 0.5), ("Other", np.full(7, 6.0)))]}


@template("qpa_vs_age_area", "Phase evolution against age (stacked areas)", CAT_PHASE, "Anhydrous phases shrink and hydrates grow, stacked to the total; log age shows the first day.",
          "xy_series", {"x": "age", "y": "one column per phase"}, demo_age_area, {"logx": True}, "Origin: Stacked Area (Plot > Basic 2D > Stacked Area), X axis log10.", "generic", ["quantitative XRD", "hydration"])
def draw_age_area(d, st, p):
    fig, ax = new_fig(st); names = [s["name"] for s in d["series"]]; cols = distinct_colors(st, names); x = np.asarray(d["x"], float)
    ax.stackplot(x, [np.nan_to_num(s["y"]) for s in d["series"]], labels=names, colors=cols, edgecolor="k", linewidth=0.3)
    if p.get("logx") and np.all(x > 0): ax.set_xscale("log")
    ax.set_xlim(x.min(), x.max()); ax.set_xlabel(d.get("x_label", "")); ax.set_ylabel(d.get("y_label", "")); ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5)); finish(ax, st); return fig


def demo_parity2():
    r = np.random.default_rng(8); q = np.array([62, 14, 8, 10.0, 58, 18, 6, 11]); return {"points": [{"name": "Phases", "x": q, "y": q + r.normal(0, 3, 8)}], "x_label": "Measured (wt.%)", "y_label": "Calculated (wt.%)"}


@template("bogue_vs_qpa", "Calculated against measured composition (parity)", CAT_PHASE, "Every phase as a point; the 1:1 line and a ± band show where the calculation departs from the measurement.",
          "scatter", {"x": "measured", "y": "calculated"}, demo_parity2, {"band": 5.0}, "Origin: Scatter + a y = x reference line (Insert > Straight Line).", "generic", ["phase composition"], ["difference to the 1:1 line", "mean absolute difference"])
def draw_parity2(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.1); cols = distinct_colors(st, [q["name"] for q in d["points"]], start=0); allv = np.concatenate([np.r_[q["x"], q["y"]] for q in d["points"]]); lo, hi = float(np.nanmin(allv)), float(np.nanmax(allv)); pad = 0.06 * (hi - lo or 1)
    for i, (q, c) in enumerate(zip(d["points"], cols)): ax.plot(q["x"], q["y"], MK[i % 8], color=c, mfc="white", label=q["name"])
    xx = np.array([lo - pad, hi + pad]); ax.plot(xx, xx, "k-", lw=0.7, label="1:1")
    if p.get("band"): ax.fill_between(xx, xx - p["band"], xx + p["band"], color="#DDDDDD", alpha=0.5, lw=0, label=f"± {p['band']:g}")
    mad = float(np.nanmean(np.abs(np.concatenate([np.asarray(q["y"], float) - np.asarray(q["x"], float) for q in d["points"]]))))
    ax.text(0.97, 0.04, f"mean |difference| = {mad:.2f}", transform=ax.transAxes, ha="right", fontsize=st["font"]["size_pt"]["annotation"])
    ax.set_xlim(xx); ax.set_ylim(xx); ax.set_aspect("equal"); ax.set_xlabel(d.get("x_label", "")); ax.set_ylabel(d.get("y_label", "")); ax.legend(); finish(ax, st); return fig


def demo_burn():
    T = np.array([1350, 1400, 1450, 1500.0]); return {"series": [{"name": n, "x": T, "y": (6.5 - i) * np.exp(-(T - 1350) / (55 + 10 * i)) + 0.3, "yerr": np.full(4, 0.15)} for i, n in enumerate(["Mix 1", "Mix 2", "Mix 3"])],
                                                      "x_label": "Burning temperature (°C)", "y_label": "Free lime (wt.%)"}


@template("free_lime_vs_T", "Burnability curve: free lime against burning temperature", CAT_PHASE, "One curve per mix; a limit line is drawn only when you give one.",
          "xy_series", {"x": "temperature", "y": "free lime per mix", "yerr": "optional"}, demo_burn, {"limit": None}, "Origin: Line + Symbol with Y error (+ Insert > Straight Line for your limit).", "generic", ["burnability"])
def draw_burn(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.35); _xy(ax, d, st)
    if p.get("limit") is not None: ax.axhline(float(p["limit"]), color="#8A97A8", ls="--", lw=0.8)
    finish(ax, st); return fig


# ------------------------------------------------------------------------------------------------ microanalysis
def demo_cloud():
    r = np.random.default_rng(2); pts = []
    for (a, b, c), n in (((55, 35, 10), 180), ((30, 50, 20), 120), ((70, 10, 20), 90)):
        q = np.clip(r.normal([a, b, c], [5, 5, 3.5], (n, 3)), 0.5, None); pts += [{"name": "", "a": x, "b": y, "c": z} for x, y, z in q]
    return {"apexes": ["Component 1", "Component 2", "Component 3"], "points": pts}


@template("eds_ternary_cloud", "Point analyses in a ternary diagram with density shading", CAT_MICRO, "Hundreds of point analyses as a cloud; the shading shows where they are dense.",
          "ternary", {"a,b,c": "three component columns", "name": "optional label column"}, demo_cloud, {"grid_step": 20, "shade": True}, "Origin: Plot > Specialized > Ternary (scatter); density: Ternary Contour.", "generic", ["SEM-EDS", "microprobe"],
          ["normalisation of the three components to 100", "kernel density of the points"])
def draw_cloud(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.15); tri = np.array([[0, 0], [1, 0], [0.5, np.sqrt(3) / 2], [0, 0]])
    for g in np.arange(p["grid_step"], 100, p["grid_step"]):
        for (a1, b1, c1), (a2, b2, c2) in [((g, 100 - g, 0), (g, 0, 100 - g)), ((100 - g, g, 0), (0, g, 100 - g)), ((100 - g, 0, g), (0, 100 - g, g))]:
            x1, y1 = _tern(a1, b1, c1); x2, y2 = _tern(a2, b2, c2); ax.plot([x1, x2], [y1, y2], color="#DDDDDD", lw=0.4, zorder=0)
    xy = np.array([_tern(float(q["a"]), float(q["b"]), float(q["c"])) for q in d["points"] if float(q["a"]) + float(q["b"]) + float(q["c"]) > 0])
    if p.get("shade") and len(xy) >= 20:
        try:
            from scipy.stats import gaussian_kde
            k = gaussian_kde(xy.T); gx, gy = np.mgrid[0:1:140j, 0:0.87:120j]; z = k(np.vstack([gx.ravel(), gy.ravel()])).reshape(gx.shape)
            inside = (gy <= np.sqrt(3) * gx + 1e-9) & (gy <= np.sqrt(3) * (1 - gx) + 1e-9); z = np.where(inside, z, np.nan); ax.contourf(gx, gy, z, levels=8, cmap="Blues", alpha=0.75, zorder=1)
        except Exception: pass
    ax.plot(xy[:, 0], xy[:, 1], ".", color="k", ms=2.2, alpha=0.6, zorder=2); ax.plot(tri[:, 0], tri[:, 1], "k", lw=0.8, zorder=3)
    A = d["apexes"]; ax.text(-0.03, -0.04, A[0], ha="right"); ax.text(1.03, -0.04, A[1], ha="left"); ax.text(0.5, 0.89, A[2], ha="center"); ax.set_aspect("equal"); ax.axis("off"); return fig


# ------------------------------------------------------------------------------------------------ decision support
def demo_eco():
    r = np.random.default_rng(4); perf = np.array([32, 41, 45, 52, 58, 63.0]); return {"points": [{"name": f"Mix {i + 1}", "x": perf[i:i + 1], "y": np.array([(820 - 60 * i + r.normal(0, 15)) / perf[i]])} for i in range(6)],
                                                                                    "x_label": "Performance (e.g. strength, MPa)", "y_label": "Intensity (e.g. kg CO$_2$ per unit performance)"}


@template("eco_efficiency", "Intensity against performance (eco-efficiency)", CAT_SUS, "Each option as a labelled point: lower and further right is better.",
          "scatter", {"x": "performance", "y": "intensity", "name": "one series per option"}, demo_eco, {}, "Origin: Scatter with data labels (Plot Details > Label).", "generic", ["mix design", "life-cycle assessment"], ["intensity = impact / performance when both are in the file"])
def draw_eco(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.35); cols = distinct_colors(st, [q["name"] for q in d["points"]], start=0)
    for i, (q, c) in enumerate(zip(d["points"], cols)):
        ax.plot(q["x"], q["y"], MK[i % 8], color=c, mfc="white")
        if q["name"] and len(q["x"]): ax.annotate(q["name"], (float(np.asarray(q["x"])[0]), float(np.asarray(q["y"])[0])), xytext=(4, 4), textcoords="offset points", fontsize=st["font"]["size_pt"]["annotation"])
    ax.set_xlabel(d.get("x_label", "")); ax.set_ylabel(d.get("y_label", "")); finish(ax, st); return fig


TIER1_ROWS = {  # catalogue row -> template
    "xrd_ref_ticks": "xrd_ref_ticks", "xrd_peak_area_vs_t": "xrd_peak_area_vs_t", "eds_ternary_cloud": "eds_ternary_cloud", "ofw_kas_plot": "ofw_kas_plot", "friedman_plot": "friedman_plot",
    "calorimetry_log_time": "calorimetry_log_time", "r3_heat_vs_bw": "r3_heat_vs_bw", "sulfate_balance": "sulfate_balance", "hydration_degree": "hydration_degree", "strength_vs_cumheat": "strength_vs_cumheat",
    "qpa_vs_age_area": "qpa_vs_age_area", "bogue_vs_qpa": "bogue_vs_qpa", "free_lime_vs_T": "free_lime_vs_T", "eco_efficiency": "eco_efficiency"}

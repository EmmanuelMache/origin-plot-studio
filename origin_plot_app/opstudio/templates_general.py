"""
opstudio_templates_general.py - general-science templates (any field), added after the graph-type survey
(03_template_library/GRAPH_TYPE_CATALOGUE.md). Same contract as opstudio_templates.py.
"""
import numpy as np
import matplotlib.pyplot as plt
from .core import template, new_fig, finish, panel_title, series_color, fig_size, distinct_colors

R = np.random.default_rng(11)
CAT_B2D = "Basic 2D & layout"
CAT_STAT = "General scientific & statistics"
CAT_TH = "Thermal analysis (TGA / DTG / DSC)"
CAT_RHEO = "Rheology & mechanics"
CAT_EC = "Electrochemistry & energy"
CAT_LIFE = "Life science & medicine"
CAT_ANA = "Analytical chemistry"
CAT_PHYS = "Physics & signal"
CAT_ENV = "Environment & geoscience"
CAT_SUS = "Sustainability & CO2"
CAT_XRD = "XRD & Rietveld"


def _lab(ax, d):
    ax.set_xlabel(d.get("x_label", "")); ax.set_ylabel(d.get("y_label", ""))


# ------------------------------------------------------------------ basic 2D & layout
def demo_band():
    x = np.linspace(0, 28, 60)
    return {"x_label": "Age (days)", "y_label": "Response (unit)", "series": [
        {"name": f"Group {k}", "x": x, "y": (10 + 4 * k) * (1 - np.exp(-x / (4 + k))), "yerr": 0.6 + 0.04 * x} for k in range(1, 4)]}


@template("error_band", "Line with shaded SD / CI band", CAT_B2D, "Mean curve with a translucent uncertainty band instead of error bars.",
          "xy_series", {"x": "x", "series": "mean per group", "yerr": "SD or CI half-width"}, demo_band, {"alpha": 0.18},
          "Origin: Plot > Basic 2D > Error Band.", "generic", ["any replicate data"])
def draw_band(d, st, p):
    fig, ax = new_fig(st); cols = distinct_colors(st, [s["name"] for s in d["series"]])
    for c, s in zip(cols, d["series"]):
        ax.plot(s["x"], s["y"], color=c, label=s["name"]); ax.fill_between(s["x"], s["y"] - s["yerr"], s["y"] + s["yerr"], color=c, alpha=p["alpha"], lw=0)
    _lab(ax, d); ax.legend(); finish(ax, st)
    return fig


def demo_cmapline():
    x = np.linspace(0, 10, 200)
    return {"x_label": "x (unit)", "y_label": "y (unit)", "param_label": "Temperature (°C)",
            "series": [{"name": f"{T} °C", "x": x, "y": np.exp(-x / (1 + T / 40)) * (1 + T / 100), "param": T} for T in range(20, 201, 20)]}


@template("colormap_line_series", "Colour-mapped line series (colour = parameter)", CAT_B2D,
          "Many curves whose order matters (temperature, time, concentration); colour bar replaces a long legend.", "xy_series",
          {"x": "x", "series": "one column per level", "param": "numeric level per column (from header or user)"}, demo_cmapline,
          {"cmap": "viridis"}, "Origin: Plot > Basic 2D > Colormapped Line Series.", "generic", ["series of spectra", "temperature series"])
def draw_cmapline(d, st, p):
    import matplotlib as mpl
    fig, ax = new_fig(st); v = [s["param"] for s in d["series"]]; norm = mpl.colors.Normalize(min(v), max(v)); cm = plt.get_cmap(p["cmap"])
    for s in d["series"]:
        ax.plot(s["x"], s["y"], color=cm(norm(s["param"])))
    cb = fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=cm), ax=ax, pad=0.01); cb.set_label(d["param_label"])
    _lab(ax, d); finish(ax, st)
    return fig


def demo_bubble():
    n = 18
    return {"x": R.uniform(20, 70, n), "y": R.uniform(200, 900, n), "s": R.uniform(1, 10, n), "z": R.uniform(0, 1, n),
            "x_label": "Performance (unit)", "y_label": "Impact (unit)", "s_label": "Size variable", "z_label": "Colour variable"}


@template("bubble_colormap", "Bubble chart with colour map (4 variables)", CAT_B2D,
          "x, y, bubble size and colour show four variables at once; size legend included.", "scatter",
          {"x": "x", "y": "y", "s": "size column", "z": "colour column"}, demo_bubble, {"cmap": "viridis"},
          "Origin: Plot > Basic 2D > Bubble + Color Mapped.", "generic", ["multi-variable comparison"])
def draw_bubble(d, st, p):
    fig, ax = new_fig(st); sc = ax.scatter(d["x"], d["y"], s=d["s"] * 25, c=d["z"], cmap=p["cmap"], edgecolor="k", lw=0.4, alpha=0.85)
    fig.colorbar(sc, ax=ax, pad=0.01).set_label(d["z_label"])
    for v in (np.min(d["s"]), np.median(d["s"]), np.max(d["s"])):
        ax.scatter([], [], s=v * 25, color="none", edgecolor="k", label=f"{v:.1f}")
    ax.legend(title=d["s_label"], loc="upper right", labelspacing=1.2); _lab(ax, d); finish(ax, st)
    return fig


def demo_lolli():
    g = ["Sample A", "Sample B", "Sample C", "Sample D", "Sample E", "Sample F"]
    return {"categories": g, "values": np.array([12.1, 9.4, 15.8, 7.2, 11.0, 13.3]), "values2": np.array([10.2, 8.8, 12.1, 7.9, 9.5, 12.9]),
            "x_label": "Value (unit)", "names": ["Before", "After"]}


@template("lollipop", "Lollipop / dumbbell chart", CAT_B2D, "Cleaner than bars for many categories; dumbbell shows before → after.",
          "category_table", {"categories": "labels", "values": "value 1", "values2": "optional value 2 (dumbbell)"}, demo_lolli, {"dumbbell": True},
          "Origin: Plot > Basic 2D > Lollipop.", "generic", ["rankings", "before/after"])
def draw_lolli(d, st, p):
    fig, ax = new_fig(st); y = np.arange(len(d["categories"])); c1, c2 = st["palette"]["series"][1], st["palette"]["series"][2]
    if p["dumbbell"] and d.get("values2") is not None:
        ax.hlines(y, d["values2"], d["values"], color="#999999", lw=1.5)
        ax.plot(d["values2"], y, "o", color=c2, label=d["names"][0]); ax.plot(d["values"], y, "o", color=c1, label=d["names"][1]); ax.legend()
    else:
        ax.hlines(y, 0, d["values"], color="#999999"); ax.plot(d["values"], y, "o", color=c1)
    ax.set_yticks(y); ax.set_yticklabels(d["categories"]); ax.set_xlabel(d["x_label"]); finish(ax, st); ax.yaxis.set_minor_locator(plt.NullLocator())
    return fig


def demo_barline():
    return {"categories": ["Mix 1", "Mix 2", "Mix 3", "Mix 4", "Mix 5"], "values": np.array([42, 38, 35, 30, 26.0]), "values2": np.array([7.1, 6.5, 6.2, 5.4, 4.9]),
            "y_label": "Quantity 1 (unit)", "y2_label": "Quantity 2 (unit)"}


@template("bar_line_combo", "Bars + line on a second y axis", CAT_B2D, "Two related quantities per category with different units.",
          "category_table", {"categories": "x", "values": "bars (left)", "values2": "line (right)"}, demo_barline, {},
          "Origin: Plot > Multi-Panel/Axis > Double-Y Column-Line Symbol.", "generic", ["any"])
def draw_barline(d, st, p):
    fig, ax = new_fig(st); x = np.arange(len(d["categories"])); c1, c2 = st["palette"]["series"][1], st["palette"]["series"][2]
    ax.bar(x, d["values"], color=c1, edgecolor="k", lw=0.4, width=0.6); ax2 = ax.twinx(); ax2.plot(x, d["values2"], "-o", color=c2, mfc="white")
    ax.set_ylabel(d["y_label"], color=c1); ax2.set_ylabel(d["y2_label"], color=c2); ax.set_xticks(x); ax.set_xticklabels(d["categories"])
    finish(ax, st); ax.tick_params(right=False); ax.xaxis.set_minor_locator(plt.NullLocator()); ax2.tick_params(direction=st["axes"]["tick_direction"])
    return fig


def demo_dtop():
    from . import synthetic as S
    x, y = S.xrd_pattern(4); return {"series": [{"name": "pattern", "x": x, "y": y}], "x_label": "2θ (°), Cu Kα", "y_label": "Intensity (counts)", "wavelength": 1.5406}


@template("xrd_dspacing_top", "Secondary top axis (e.g. d-spacing over 2θ, K over °C)", CAT_XRD,
          "Second, transformed x scale on top: d = λ / (2 sin θ); same mechanism for K↔°C, √t↔t, energy↔wavelength.", "xy_series",
          {"x": "x", "y": "y", "transform": "user-chosen function + inverse"}, demo_dtop, {},
          "Origin: Axis dialog > Top: Tick Labels with formula.", "generic", ["XRD", "any unit pair"])
def draw_dtop(d, st, p):
    fig, ax = new_fig(st); s = d["series"][0]; ax.plot(s["x"], s["y"], "k", lw=0.7); lam = d["wavelength"]
    f = lambda tt: lam / (2 * np.sin(np.radians(np.clip(tt, 1, 179) / 2))); inv = lambda dd: 2 * np.degrees(np.arcsin(np.clip(lam / (2 * np.clip(dd, 0.01, None)), -1, 1)))
    top = ax.secondary_xaxis("top", functions=(f, inv)); top.set_xlabel("d-spacing (Å)"); top.set_xticks([8, 5, 4, 3, 2.5, 2, 1.8, 1.6])
    ax.tick_params(top=False); ax.set_xlim(s["x"].min(), s["x"].max()); _lab(ax, d); finish(ax, st); ax.tick_params(top=False)
    return fig


# ------------------------------------------------------------------ statistics
def demo_groups():
    return {"groups": [{"name": f"G{i + 1}", "values": np.r_[R.normal(10 + i, 1 + 0.2 * i, 40), R.normal(13 + i, 0.6, 10 * (i % 2))]} for i in range(5)],
            "y_label": "Measured value (unit)"}


@template("violin", "Violin + box + points", CAT_STAT, "Distribution shape, quartiles and every observation together.",
          "groups", {"groups": "one column per group"}, demo_groups, {}, "Origin: Plot > Statistical > Violin with Box (ViolinBox.otpu).", "generic", ["replicates", "distributions"])
def draw_violin(d, st, p):
    fig, ax = new_fig(st); vals = [g["values"] for g in d["groups"]]; cols = distinct_colors(st, [g["name"] for g in d["groups"]])
    parts = ax.violinplot(vals, showextrema=False, widths=0.8)
    for b, c in zip(parts["bodies"], cols):
        b.set_facecolor(c); b.set_alpha(0.3); b.set_edgecolor(c)
    ax.boxplot(vals, widths=0.12, showfliers=False, medianprops=dict(color="k"))
    for i, (v, c) in enumerate(zip(vals, cols)):
        ax.plot(i + 1 + R.uniform(-0.05, 0.05, len(v)), v, "o", ms=2, color=c, alpha=0.7)
    ax.set_xticks(range(1, len(vals) + 1)); ax.set_xticklabels([g["name"] for g in d["groups"]]); ax.set_ylabel(d["y_label"]); finish(ax, st); ax.xaxis.set_minor_locator(plt.NullLocator())
    return fig


@template("raincloud", "Raincloud plot (half violin + box + rain)", CAT_STAT, "Same information as a violin, easier to read for many groups.",
          "groups", {"groups": "one column per group"}, demo_groups, {}, "Origin: Raincloud template (File Exchange fid 773).", "generic", ["distributions"])
def draw_rain(d, st, p):
    fig, ax = new_fig(st); vals = [g["values"] for g in d["groups"]]; cols = distinct_colors(st, [g["name"] for g in d["groups"]])
    parts = ax.violinplot(vals, vert=False, showextrema=False, widths=0.9)
    for i, (b, c) in enumerate(zip(parts["bodies"], cols)):
        verts = b.get_paths()[0].vertices; verts[:, 1] = np.clip(verts[:, 1], i + 1, None); b.set_facecolor(c); b.set_alpha(0.45); b.set_edgecolor(c)
        ax.plot(vals[i], i + 1 - 0.22 + R.uniform(-0.07, 0.07, len(vals[i])), "o", ms=2, color=c, alpha=0.7)
    ax.boxplot(vals, vert=False, widths=0.1, positions=np.arange(1, len(vals) + 1) - 0.06, showfliers=False, medianprops=dict(color="k"))
    ax.set_yticks(range(1, len(vals) + 1)); ax.set_yticklabels([g["name"] for g in d["groups"]]); ax.set_xlabel(d["y_label"]); finish(ax, st); ax.yaxis.set_minor_locator(plt.NullLocator())
    return fig


@template("ridgeline", "Ridgeline (joy) plot", CAT_STAT, "Offset density curves - many distributions in little space.", "groups",
          {"groups": "one column per group"}, demo_groups, {"overlap": 1.6}, "Origin: Plot > Statistical > Ridgeline.", "generic", ["distributions", "time series of distributions"])
def draw_ridge(d, st, p):
    from scipy.stats import gaussian_kde
    fig, ax = new_fig(st); allv = np.concatenate([g["values"] for g in d["groups"]]); xx = np.linspace(allv.min() - 1, allv.max() + 1, 300)
    cols = distinct_colors(st, [g["name"] for g in d["groups"]])
    for i, (g, c) in enumerate(zip(d["groups"], cols)):
        k = gaussian_kde(g["values"])(xx); k = k / k.max() * p["overlap"]; base = i
        ax.fill_between(xx, base, base + k, color=c, alpha=0.6, lw=0.8, edgecolor="k", zorder=len(cols) - i); ax.text(xx[0], base + 0.1, g["name"], fontsize=7)
    ax.set_yticks([]); ax.set_xlabel(d["y_label"]); finish(ax, st)
    return fig


def demo_hist():
    return {"values": np.r_[R.normal(50, 5, 300), R.normal(62, 3, 80)], "x_label": "Value (unit)", "y_label": "Count"}


@template("hist_kde", "Histogram + normal fit + KDE", CAT_STAT, "Distribution with fitted normal curve and kernel density; mean ± SD printed.",
          "values", {"values": "one column"}, demo_hist, {"bins": "auto"}, "Origin: Plot > Statistical > Histogram + Probabilities.", "generic", ["distributions"], ["mean, SD, KDE"])
def draw_hist(d, st, p):
    from scipy.stats import gaussian_kde, norm
    fig, ax = new_fig(st); v = d["values"]; n, b, _ = ax.hist(v, bins=p["bins"], color="#BFD3E6", edgecolor="k", lw=0.4)
    xx = np.linspace(v.min(), v.max(), 300); w = (b[1] - b[0]) * len(v)
    ax.plot(xx, norm.pdf(xx, v.mean(), v.std()) * w, "--", color="k", label=f"Normal (μ = {v.mean():.1f}, σ = {v.std():.1f})")
    ax.plot(xx, gaussian_kde(v)(xx) * w, color="#C0141E", label="KDE"); _lab(ax, d); ax.legend(); finish(ax, st)
    return fig


@template("qq", "Normal Q–Q plot with reference line", CAT_STAT, "Checks normality of residuals or replicate data.", "values",
          {"values": "one column"}, demo_hist, {}, "Origin: Plot > Statistical > Q-Q Plot.", "generic", ["statistics"])
def draw_qq(d, st, p):
    from scipy import stats
    fig, ax = new_fig(st, width="single", aspect=1.3); (osm, osr), (sl, ic, r) = stats.probplot(d["values"])
    ax.plot(osm, osr, "o", ms=3, mfc="white", color="k"); ax.plot(osm, sl * osm + ic, color="#C0141E", label=f"r = {r:.3f}")
    ax.set_xlabel("Theoretical quantiles"); ax.set_ylabel("Sample quantiles"); ax.legend(); finish(ax, st)
    return fig


def demo_reg():
    x = np.linspace(0, 10, 25); return {"x": x, "y": 2.1 * x + 3 + R.normal(0, 2, 25), "x_label": "x (unit)", "y_label": "y (unit)"}


@template("regression_bands", "Regression with 95 % confidence and prediction bands", CAT_STAT,
          "Fit line, CI of the mean (dark) and PI for new observations (light); equation, R², n.", "scatter",
          {"x": "x", "y": "y"}, demo_reg, {}, "Origin: Linear Fit > Confidence & Prediction Bands.", "generic", ["any fit"], ["OLS, CI, PI"])
def draw_reg(d, st, p):
    from scipy.stats import t as tt
    fig, ax = new_fig(st); x, y = d["x"], d["y"]; n = len(x); b, a = np.polyfit(x, y, 1); res = y - (a + b * x); s = np.sqrt(np.sum(res ** 2) / (n - 2))
    xx = np.linspace(x.min(), x.max(), 200); q = tt.ppf(0.975, n - 2); sx = np.sum((x - x.mean()) ** 2)
    ci = q * s * np.sqrt(1 / n + (xx - x.mean()) ** 2 / sx); pi = q * s * np.sqrt(1 + 1 / n + (xx - x.mean()) ** 2 / sx); yy = a + b * xx
    ax.fill_between(xx, yy - pi, yy + pi, color="#1F77B4", alpha=0.12, lw=0, label="95 % prediction band")
    ax.fill_between(xx, yy - ci, yy + ci, color="#1F77B4", alpha=0.3, lw=0, label="95 % confidence band")
    r2 = 1 - np.sum(res ** 2) / np.sum((y - y.mean()) ** 2)
    ax.plot(xx, yy, color="#1F77B4", label=f"y = {b:.3g}x + {a:.3g}  (R$^2$ = {r2:.3f}, n = {n})"); ax.plot(x, y, "o", color="k", mfc="white", ms=4)
    _lab(ax, d); ax.legend(loc="upper left"); finish(ax, st)
    return fig


@template("residuals_4", "Residual diagnostics (4 panels)", CAT_STAT, "Residuals vs fitted, vs x, histogram and Q–Q - to defend any fit.",
          "scatter", {"x": "x", "y": "y", "model": "fit from Fitting module"}, demo_reg, {}, "Origin: Fit report > Residual Plots.", "generic", ["any fit"])
def draw_res4(d, st, p):
    from scipy import stats
    fig, axs = new_fig(st, 2, 2, gridspec_kw={"hspace": 0.45, "wspace": 0.3}); axs = axs.ravel(); x, y = d["x"], d["y"]; b, a = np.polyfit(x, y, 1); f = a + b * x; r = y - f
    axs[0].plot(f, r, "o", ms=3, mfc="white", color="k"); axs[0].axhline(0, color="#C0141E"); axs[0].set_xlabel("Fitted"); axs[0].set_ylabel("Residual")
    axs[1].plot(x, r, "o", ms=3, mfc="white", color="k"); axs[1].axhline(0, color="#C0141E"); axs[1].set_xlabel(d["x_label"]); axs[1].set_ylabel("Residual")
    axs[2].hist(r, bins=8, color="#BFD3E6", edgecolor="k", lw=0.4); axs[2].set_xlabel("Residual"); axs[2].set_ylabel("Count")
    (osm, osr), (sl, ic, _) = stats.probplot(r); axs[3].plot(osm, osr, "o", ms=3, mfc="white", color="k"); axs[3].plot(osm, sl * osm + ic, color="#C0141E"); axs[3].set_xlabel("Theoretical quantiles"); axs[3].set_ylabel("Sample quantiles")
    for k, ax in enumerate(axs):
        panel_title(ax, k); finish(ax, st)
    return fig


def demo_pca():
    names = ["Var 1", "Var 2", "Var 3", "Var 4", "Var 5"]; G = ["Group A"] * 10 + ["Group B"] * 10 + ["Group C"] * 10
    X = np.r_[R.normal(0, 1, (10, 5)) + [2, 0, 0, 1, 0], R.normal(0, 1, (10, 5)) + [0, 2, 1, 0, 0], R.normal(0, 1, (10, 5)) + [0, 0, 0, -1, 2]]
    return {"X": X, "vars": names, "groups": G}


@template("pca_biplot", "PCA biplot (scores + loadings) with scree inset", CAT_STAT, "Which samples group together and which variables drive it.",
          "table", {"X": "samples × variables (numeric)", "groups": "optional group column"}, demo_pca, {}, "Origin: Statistics > Multivariate > PCA.", "generic", ["multi-variable data"], ["standardise, SVD, explained variance"])
def draw_pca(d, st, p):
    X = (d["X"] - d["X"].mean(0)) / d["X"].std(0); U, Sv, Vt = np.linalg.svd(X, full_matrices=False); sc = U[:, :2] * Sv[:2]; ev = Sv ** 2 / np.sum(Sv ** 2) * 100
    fig, ax = new_fig(st, width="single", aspect=1.2); gs = list(dict.fromkeys(d["groups"])); cols = distinct_colors(st, gs)
    for g, c in zip(gs, cols):
        m = np.array(d["groups"]) == g; ax.plot(sc[m, 0], sc[m, 1], "o", color=c, label=g, mfc="white")
    k = np.abs(sc).max() / np.abs(Vt[:2]).max() * 0.8
    for i, v in enumerate(d["vars"]):
        ax.arrow(0, 0, Vt[0, i] * k, Vt[1, i] * k, color="#C0141E", width=0.01, head_width=0.12); ax.text(Vt[0, i] * k * 1.12, Vt[1, i] * k * 1.12, v, color="#C0141E", fontsize=6.5)
    ax.axhline(0, color="#BBBBBB", lw=0.5); ax.axvline(0, color="#BBBBBB", lw=0.5); ax.set_xlabel(f"PC1 ({ev[0]:.0f} %)"); ax.set_ylabel(f"PC2 ({ev[1]:.0f} %)"); ax.legend(fontsize=6)
    ins = ax.inset_axes([0.72, 0.04, 0.26, 0.24]); ins.bar(range(1, len(ev) + 1), ev, color="#888888"); ins.set_title("Scree", fontsize=5.5); ins.tick_params(labelsize=5)
    finish(ax, st)
    return fig


def demo_ba():
    m1 = R.uniform(10, 60, 40); return {"m1": m1, "m2": m1 + R.normal(0.8, 1.5, 40), "names": ["Method A", "Method B"], "unit": "unit"}


@template("bland_altman", "Bland–Altman agreement plot", CAT_STAT, "Agreement between two methods: difference vs mean with bias and ±1.96 SD limits.",
          "paired", {"m1": "method 1", "m2": "method 2"}, demo_ba, {}, "Origin: Bland-Altman Plot app.", "generic", ["method comparison"], ["bias, limits of agreement"])
def draw_ba(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.4); mean = (d["m1"] + d["m2"]) / 2; diff = d["m2"] - d["m1"]; b = diff.mean(); s = diff.std(ddof=1)
    ax.plot(mean, diff, "o", ms=3.5, mfc="white", color="k")
    for v, l, ls in ((b, f"Bias {b:.2f}", "-"), (b + 1.96 * s, f"+1.96 SD {b + 1.96 * s:.2f}", "--"), (b - 1.96 * s, f"−1.96 SD {b - 1.96 * s:.2f}", "--")):
        ax.axhline(v, color="#C0141E", ls=ls, lw=0.8); ax.text(mean.max(), v, l, ha="right", va="bottom", fontsize=6.5, color="#C0141E")
    ax.set_xlabel(f"Mean of {d['names'][0]} and {d['names'][1]} ({d['unit']})"); ax.set_ylabel(f"{d['names'][1]} − {d['names'][0]} ({d['unit']})"); finish(ax, st)
    return fig


# ------------------------------------------------------------------ thermal kinetics
def _alpha_curves():
    betas = [2, 5, 10, 20]; T = np.linspace(500, 1100, 600); Ea, A = 180e3, 1e9; Rg = 8.314; out = []
    for b in betas:
        k = A * np.exp(-Ea / (Rg * (T + 273.15))); g = np.cumsum(k) * (T[1] - T[0]) / b; a = 1 - np.exp(-g); out.append({"beta": b, "T": T, "alpha": a})
    return out


def demo_conv():
    return {"curves": _alpha_curves(), "x_label": "Temperature (°C)", "y_label": "Conversion α (–)"}


@template("conversion_vs_T", "Conversion α vs T at several heating rates", CAT_TH, "S-curves from multi-rate TG/DSC; input for isoconversional kinetics.",
          "kinetics", {"curves": "one TG/DSC run per heating rate (β from file or user)"}, demo_conv, {},
          "Origin: line plot, colour-mapped by β.", "generic", ["thermal kinetics"], ["α = (m0 − m)/(m0 − m∞)"])
def draw_conv(d, st, p):
    fig, ax = new_fig(st); cm = plt.get_cmap("plasma")
    for i, c in enumerate(d["curves"]):
        ax.plot(c["T"], c["alpha"], color=cm(i / len(d["curves"])), label=f"β = {c['beta']} °C min$^{{-1}}$")
    _lab(ax, d); ax.legend(); finish(ax, st)
    return fig


def demo_kis():
    cs = _alpha_curves(); pts = []
    for c in cs:
        da = np.gradient(c["alpha"], c["T"]); Tp = c["T"][np.argmax(da)] + 273.15; pts.append((c["beta"], Tp))
    return {"points": pts}


@template("kissinger_plot", "Kissinger plot (activation energy)", CAT_TH, "ln(β/Tp²) vs 1000/Tp; slope = −Ea/R. Use ≥ 3 heating rates.",
          "kinetics", {"beta": "heating rates", "Tp": "peak temperatures (K)"}, demo_kis, {}, "Origin: scatter + Linear Fit.", "generic",
          ["thermal kinetics"], ["Ea = −slope × R"])
def draw_kis(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.35); b = np.array([q[0] for q in d["points"]], float); Tp = np.array([q[1] for q in d["points"]])
    x = 1000 / Tp; y = np.log(b / Tp ** 2); sl, ic = np.polyfit(x, y, 1)
    ax.plot(x, y, "o", color="k", mfc="white"); xx = np.linspace(x.min(), x.max(), 50); ax.plot(xx, sl * xx + ic, color="#C0141E", label=f"E$_a$ = {-sl * 8.314:.0f} kJ mol$^{{-1}}$")
    ax.set_xlabel("1000/T$_p$ (K$^{-1}$)"); ax.set_ylabel("ln(β/T$_p^2$)"); ax.legend(); finish(ax, st)
    return fig


def demo_ea():
    a = np.linspace(0.1, 0.9, 9)
    return {"alpha": a, "methods": [{"name": "Friedman", "Ea": 182 + 25 * (a - 0.5) ** 2 * 4, "err": np.full(9, 6)},
                                    {"name": "OFW", "Ea": 178 + 10 * (a - 0.5), "err": np.full(9, 4)}, {"name": "KAS", "Ea": 176 + 9 * (a - 0.5), "err": np.full(9, 4)}]}


@template("ea_vs_alpha", "Activation energy vs conversion (isoconversional)", CAT_TH,
          "Eα from Friedman / OFW / KAS compared with uncertainty bands; recommended default kinetics output.", "kinetics",
          {"alpha": "α levels", "methods": "Eα per method"}, demo_ea, {}, "Origin: Line + Error Band.", "generic", ["thermal kinetics"], ["isoconversional regression at each α"])
def draw_ea(d, st, p):
    fig, ax = new_fig(st); cols = distinct_colors(st, [m["name"] for m in d["methods"]])
    for m, c, mk in zip(d["methods"], cols, "osD"):
        ax.plot(d["alpha"], m["Ea"], "-" + mk, color=c, mfc="white", label=m["name"]); ax.fill_between(d["alpha"], m["Ea"] - m["err"], m["Ea"] + m["err"], color=c, alpha=0.12, lw=0)
    ax.set_xlabel("Conversion α (–)"); ax.set_ylabel("E$_α$ (kJ mol$^{-1}$)"); ax.legend(); finish(ax, st)
    return fig


def demo_dta():
    T = np.linspace(100, 1400, 1500)
    from . import synthetic as S
    y = -S.peaks(T, [550, 800, 1280, 1338], [0.6, 2.5, 0.4, 0.5], [60, 70, 25, 20]) + S.peaks(T, [1200], [0.35], 40) + 0.0002 * T
    return {"series": [{"name": "Raw meal", "x": T, "y": y}], "x_label": "Temperature (°C)", "y_label": "DTA (µV mg$^{-1}$)",
            "events": [{"T": [480, 620], "label": "Clay dehydroxylation?", "confirmed": False}, {"T": [700, 880], "label": "Decarbonation", "confirmed": True},
                       {"T": [1150, 1250], "label": "Belite formation?", "confirmed": False}, {"T": [1260, 1360], "label": "Melt / alite?", "confirmed": False}]}


@template("dta_raw_meal", "High-temperature DTA/DSC with event bands (labels to confirm)", CAT_TH,
          "Reaction sequence on heating; unconfirmed event names are shown with '?' until the user confirms them.", "xy_series",
          {"x": "T", "y": "DTA/DSC signal", "events": "temperature windows + labels (user-confirmed)"}, demo_dta, {"exo": "up"},
          "Origin: line + rectangles + text.", "generic", ["DTA", "DSC", "clinkering", "ceramics", "glass"], ["onset/peak per event"])
def draw_dta(d, st, p):
    fig, ax = new_fig(st); s = d["series"][0]; ax.plot(s["x"], s["y"], "k")
    for i, e in enumerate(d["events"]):
        ax.axvspan(*e["T"], color="#9EC5E8" if e["confirmed"] else "#F6C89F", alpha=0.35, lw=0)
        ax.text(np.mean(e["T"]), 1.01 + 0.08 * (i % 2), e["label"], transform=ax.get_xaxis_transform(), ha="center", fontsize=6.5,
                color="k" if e["confirmed"] else "#A16207", fontstyle="normal" if e["confirmed"] else "italic")
    ax.text(0.02, 0.92, "exo ↑", transform=ax.transAxes, fontsize=7); _lab(ax, d); ax.set_xlim(s["x"].min(), s["x"].max()); finish(ax, st)
    fig.text(0.01, 0.01, "Orange = suggested label awaiting confirmation (never exported as final)", fontsize=6, color="#A16207")
    return fig


@template("arrhenius_plot", "Arrhenius plot (ln k vs 1000/T)", CAT_PHYS, "Rate constants at several temperatures; Ea from the slope. Works for any kinetics.",
          "scatter", {"T": "temperature", "k": "rate constant"}, lambda: {"T": np.array([20, 30, 40, 50, 60]) + 273.15,
                                                                          "k": np.exp(12 - 45e3 / (8.314 * (np.array([20, 30, 40, 50, 60]) + 273.15))) * R.uniform(0.93, 1.07, 5)},
          {}, "Origin: scatter + Linear Fit on transformed columns.", "generic", ["kinetics", "calorimetry at several T", "conductivity"], ["Ea = −slope·R"])
def draw_arr(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.35); x = 1000 / d["T"]; y = np.log(d["k"]); sl, ic = np.polyfit(x, y, 1)
    ax.plot(x, y, "o", color="k", mfc="white"); ax.plot(x, sl * x + ic, color="#C0141E", label=f"E$_a$ = {-sl * 8.314:.1f} kJ mol$^{{-1}}$")
    top = ax.secondary_xaxis("top", functions=(lambda v: 1000 / np.clip(v, 1e-3, None) - 273.15, lambda v: 1000 / (v + 273.15))); top.set_xlabel("Temperature (°C)")
    ax.set_xlabel("1000/T (K$^{-1}$)"); ax.set_ylabel("ln k"); ax.legend(); finish(ax, st); ax.tick_params(top=False)
    return fig


# ------------------------------------------------------------------ rheology & mechanics
def demo_flow():
    g = np.logspace(-1, 2.5, 40)
    return {"series": [{"name": n, "x": g, "y": t0 + K * g ** nn} for n, t0, K, nn in [("Paste 1", 12, 1.2, 0.8), ("Paste 2", 25, 1.8, 0.75), ("Paste 3", 6, 0.9, 0.9)]],
            "x_label": "Shear rate (s$^{-1}$)", "y_label": "Shear stress (Pa)"}


@template("rheo_flow_curve", "Rheology flow curve with Herschel–Bulkley fit and viscosity", CAT_RHEO,
          "Shear stress (left) and apparent viscosity (right) vs shear rate, log-log; yield stress from the fit.", "xy_series",
          {"x": "shear rate", "series": "shear stress per sample"}, demo_flow, {}, "Origin: Double-Y, log axes, NLFit (Herschel-Bulkley).", "generic",
          ["pastes", "suspensions", "polymers", "food"], ["τ = τ0 + K·γ̇ⁿ; η = τ/γ̇"])
def draw_flow(d, st, p):
    from scipy.optimize import curve_fit
    fig, ax = new_fig(st); ax2 = ax.twinx(); cols = distinct_colors(st, [s["name"] for s in d["series"]])
    for s, c in zip(d["series"], cols):
        (t0, K, n), _ = curve_fit(lambda g, a, b, c_: a + b * g ** c_, s["x"], s["y"], p0=[5, 1, 0.8], maxfev=8000)
        ax.plot(s["x"], s["y"], "o", ms=3, mfc="white", color=c); ax.plot(s["x"], t0 + K * s["x"] ** n, color=c, label=f"{s['name']}: τ$_0$ = {t0:.1f} Pa")
        ax2.plot(s["x"], s["y"] / s["x"], "--", color=c, lw=0.8)
    for a in (ax, ax2):
        a.set_xscale("log"); a.set_yscale("log")
    ax2.set_ylabel("Apparent viscosity (Pa s), dashed"); _lab(ax, d); ax.legend(loc="lower right"); finish(ax, st, minor=False); ax.tick_params(right=False)
    return fig


def demo_amp():
    g = np.logspace(-3, 2, 50); Gp = 5e4 / (1 + (g / 0.05) ** 1.2); Gpp = 4e3 * (1 + g / 0.02) / (1 + (g / 0.4) ** 1.1)
    return {"x": g, "Gp": Gp, "Gpp": Gpp, "x_label": "Shear strain γ (%)", "y_label": "G′, G″ (Pa)"}


@template("rheo_amp_sweep", "Amplitude sweep (G′, G″) with LVE limit and crossover", CAT_RHEO,
          "Oscillatory strain sweep: linear viscoelastic limit (G′ drops 5 %) and G′ = G″ crossover marked.", "oscillation",
          {"x": "strain", "Gp": "storage modulus", "Gpp": "loss modulus"}, demo_amp, {"lve_drop": 0.05}, "Origin: log-log line+symbol.", "generic",
          ["pastes", "gels", "polymers"], ["LVE limit, crossover strain"])
def draw_amp(d, st, p):
    fig, ax = new_fig(st); x = d["x"]; ax.loglog(x, d["Gp"], "-o", ms=3, color="#1F77B4", mfc="#1F77B4", label="G′"); ax.loglog(x, d["Gpp"], "-s", ms=3, color="#D62728", mfc="white", label="G″")
    i = np.argmax(d["Gp"] < d["Gp"][0] * (1 - p["lve_drop"])); ax.axvline(x[i], color="#555555", ls=":", lw=0.8); ax.text(x[i], ax.get_ylim()[0] * 1.5, " LVE limit", fontsize=6.5)
    j = np.argmax(d["Gp"] < d["Gpp"])
    if j:
        ax.plot(x[j], d["Gp"][j], "k*", ms=8, label=f"Crossover γ ≈ {x[j]:.2g} %")
    _lab(ax, d); ax.legend(); finish(ax, st, minor=False)
    return fig


def demo_nyq():
    w = np.logspace(-2, 5, 80); Rs, Rct, C = 20, 120, 1e-4; Z = Rs + Rct / (1 + 1j * w * Rct * C) + (1 - 1j) * 30 / np.sqrt(w)
    return {"Zre": Z.real, "Zim": -Z.imag, "f": w / (2 * np.pi)}


@template("eis_nyquist", "EIS Nyquist plot (equal axes) with frequency labels", CAT_EC, "−Z″ vs Z′ with equal aspect; selected frequencies annotated.",
          "impedance", {"Zre": "Z′", "Zim": "−Z″", "f": "frequency"}, demo_nyq, {}, "Origin: scatter, axis ratio 1:1.", "generic",
          ["corrosion", "batteries", "cementitious conductivity"], ["equivalent-circuit fit (external)"])
def draw_nyq(d, st, p):
    fig, ax = new_fig(st); ax.plot(d["Zre"], d["Zim"], "o-", ms=3, mfc="white", color="#1F77B4")
    for k in np.linspace(5, len(d["f"]) - 5, 5).astype(int):
        ax.annotate(f"{d['f'][k]:.2g} Hz", (d["Zre"][k], d["Zim"][k]), xytext=(4, 4), textcoords="offset points", fontsize=6)
    ax.set_aspect("equal", adjustable="datalim"); ax.set_xlabel("Z′ (Ω)"); ax.set_ylabel("−Z″ (Ω)"); finish(ax, st)
    return fig


# ------------------------------------------------------------------ electrochemistry
def demo_cv():
    E = np.r_[np.linspace(-0.2, 0.6, 200), np.linspace(0.6, -0.2, 200)]
    out = []
    for v in (10, 25, 50, 100):
        s = np.sqrt(v / 10); i = s * (8 * np.exp(-((E - 0.25) / 0.06) ** 2) * (np.arange(400) < 200) - 7 * np.exp(-((E - 0.18) / 0.06) ** 2) * (np.arange(400) >= 200)) + 0.5 * s * np.sign(200 - np.arange(400))
        out.append({"name": f"{v} mV s$^{{-1}}$", "x": E, "y": i})
    return {"series": out, "x_label": "Potential (V vs Ag/AgCl)", "y_label": "Current (µA)"}


@template("cv_voltammogram", "Cyclic voltammograms at several scan rates", CAT_EC, "Closed CV loops colour-ordered by scan rate.", "xy_series",
          {"x": "potential", "series": "current per scan rate"}, demo_cv, {}, "Origin: Line, colour-mapped series.", "generic", ["electrochemistry"], ["peak currents, ΔEp"])
def draw_cv(d, st, p):
    fig, ax = new_fig(st); cm = plt.get_cmap("viridis")
    for i, s in enumerate(d["series"]):
        ax.plot(s["x"], s["y"], color=cm(i / len(d["series"])), label=s["name"])
    ax.axhline(0, color="#BBBBBB", lw=0.5); _lab(ax, d); ax.legend(); finish(ax, st)
    return fig


def demo_ragone():
    return {"points": [{"name": n, "x": np.logspace(a, a + 1.5, 6), "y": e * np.logspace(0, -0.8, 6)} for n, a, e in
                       [("Device A", 1, 150), ("Device B", 2, 40), ("Device C", 3, 8)]], "x_label": "Power density (W kg$^{-1}$)", "y_label": "Energy density (Wh kg$^{-1}$)"}


@template("ragone_plot", "Ragone plot (energy vs power, log-log)", CAT_EC, "Energy storage comparison.", "scatter", {"x": "power", "y": "energy", "group": "device"},
          demo_ragone, {}, "Origin: log-log Line+Symbol.", "generic", ["energy storage"])
def draw_ragone(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.35); cols = distinct_colors(st, [q["name"] for q in d["points"]])
    for q, c in zip(d["points"], cols):
        ax.loglog(q["x"], q["y"], "-o", ms=3, color=c, mfc="white", label=q["name"])
    _lab(ax, d); ax.legend(); finish(ax, st, minor=False)
    return fig


# ------------------------------------------------------------------ life science
def demo_dr():
    dose = np.logspace(-2, 2, 9); f = lambda x, b, t, ec, h: b + (t - b) / (1 + (ec / x) ** h)
    return {"series": [{"name": n, "x": dose, "y": f(dose, 2, 100, ec, 1.2) + R.normal(0, 3, 9), "yerr": np.full(9, 4)} for n, ec in [("Compound A", 0.8), ("Compound B", 6)]],
            "x_label": "Concentration (µM)", "y_label": "Response (%)"}


@template("dose_response_4pl", "Dose–response with 4-parameter logistic fit (EC50)", CAT_LIFE, "Log-concentration x axis, fitted sigmoid, EC50/IC50 in legend.",
          "xy_series", {"x": "dose", "series": "response per compound", "yerr": "SD"}, demo_dr, {}, "Origin: NLFit DoseResp, X log.", "generic",
          ["pharmacology", "toxicity", "adsorption"], ["4PL: bottom, top, EC50, Hill slope"])
def draw_dr(d, st, p):
    from scipy.optimize import curve_fit
    f = lambda x, b, t, ec, h: b + (t - b) / (1 + (ec / x) ** h); fig, ax = new_fig(st); cols = distinct_colors(st, [s["name"] for s in d["series"]])
    for s, c in zip(d["series"], cols):
        pr, _ = curve_fit(f, s["x"], s["y"], p0=[0, 100, 1, 1], maxfev=10000); xx = np.logspace(np.log10(s["x"].min()), np.log10(s["x"].max()), 200)
        ax.errorbar(s["x"], s["y"], yerr=s["yerr"], fmt="o", ms=3.5, mfc="white", color=c, capsize=2); ax.plot(xx, f(xx, *pr), color=c, label=f"{s['name']}: EC$_{{50}}$ = {pr[2]:.2g}")
    ax.set_xscale("log"); _lab(ax, d); ax.legend(); finish(ax, st, minor=False)
    return fig


def demo_km():
    def km(n, scale):
        t = np.sort(R.exponential(scale, n)); e = R.random(n) < 0.8; return t, e
    return {"groups": [{"name": n, "t": km(60, s)[0], "event": km(60, s)[1]} for n, s in [("Group A", 20), ("Group B", 35)]], "x_label": "Time (months)", "y_label": "Survival probability"}


@template("kaplan_meier", "Kaplan–Meier survival / time-to-failure curves", CAT_LIFE, "Step curves with censor ticks; also for time-to-failure of specimens.",
          "survival", {"t": "time", "event": "1 = event, 0 = censored", "group": "group"}, demo_km, {}, "Origin: Statistics > Survival Analysis > Kaplan-Meier.", "generic",
          ["medicine", "reliability", "durability failure"], ["KM estimator", "log-rank (external)"])
def draw_km(d, st, p):
    fig, ax = new_fig(st); cols = distinct_colors(st, [g["name"] for g in d["groups"]])
    for g, c in zip(d["groups"], cols):
        o = np.argsort(g["t"]); t, e = g["t"][o], np.asarray(g["event"])[o].astype(bool); n = len(t); s = 1.0; xs, ys = [0], [1.0]
        for i, (ti, ei) in enumerate(zip(t, e)):
            if ei:
                s *= 1 - 1 / (n - i)
            xs.append(ti); ys.append(s)
        ax.step(xs, ys, where="post", color=c, label=g["name"]); ax.plot(t[~e], np.interp(t[~e], xs, ys), "|", color=c, ms=6)
    ax.set_ylim(0, 1.02); _lab(ax, d); ax.legend(); finish(ax, st)
    return fig


def demo_roc():
    y = np.r_[np.ones(100), np.zeros(100)]; s1 = np.r_[R.normal(1.2, 1, 100), R.normal(0, 1, 100)]; s2 = np.r_[R.normal(0.6, 1, 100), R.normal(0, 1, 100)]
    return {"truth": y, "scores": [{"name": "Classifier A", "s": s1}, {"name": "Classifier B", "s": s2}]}


@template("roc_curve", "ROC curve with AUC", CAT_LIFE, "Classifier / diagnostic test performance; diagonal = chance.", "classification",
          {"truth": "0/1 column", "scores": "score per model"}, demo_roc, {}, "Origin: Statistics > ROC Curve.", "generic", ["diagnostics", "machine learning"], ["TPR, FPR, AUC"])
def draw_roc(d, st, p):
    fig, ax = new_fig(st, width="single", aspect=1.2); cols = distinct_colors(st, [q["name"] for q in d["scores"]])
    for q, c in zip(d["scores"], cols):
        th = np.sort(np.unique(q["s"]))[::-1]; P = d["truth"].sum(); N = len(d["truth"]) - P
        tpr = np.r_[0, [((q["s"] >= t) & (d["truth"] == 1)).sum() / P for t in th]]; fpr = np.r_[0, [((q["s"] >= t) & (d["truth"] == 0)).sum() / N for t in th]]
        ax.plot(fpr, tpr, color=c, label=f"{q['name']} (AUC = {np.trapezoid(tpr, fpr):.2f})")
    ax.plot([0, 1], [0, 1], ":", color="#888888"); ax.set_aspect("equal"); ax.set_xlabel("False positive rate"); ax.set_ylabel("True positive rate"); ax.legend(loc="lower right"); finish(ax, st)
    return fig


# ------------------------------------------------------------------ analytical
def demo_cal():
    c = np.array([0, 1, 2, 5, 10, 20, 50.0]); return {"x": c, "y": 0.02 + 0.051 * c + R.normal(0, 0.012, 7), "x_label": "Concentration (mg L$^{-1}$)", "y_label": "Signal (a.u.)"}


@template("calibration_lod", "Calibration curve with LOD/LOQ and residual panel", CAT_ANA, "Linear calibration; LOD = 3.3 s/b, LOQ = 10 s/b shown; residuals below.",
          "scatter", {"x": "standard concentration", "y": "signal"}, demo_cal, {}, "Origin: Linear Fit + residual plot.", "generic", ["ICP", "IC", "UV-Vis", "any calibration"], ["slope, intercept, LOD, LOQ"])
def draw_cal(d, st, p):
    fig, (a, b) = new_fig(st, 2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1], "hspace": 0.06}); x, y = d["x"], d["y"]
    sl, ic = np.polyfit(x, y, 1); r = y - (sl * x + ic); s = np.sqrt(np.sum(r ** 2) / (len(x) - 2)); lod, loq = 3.3 * s / sl, 10 * s / sl
    a.plot(x, y, "o", color="k", mfc="white"); a.plot(x, sl * x + ic, color="#1F77B4", label=f"y = {sl:.4f}x + {ic:.4f}\nLOD = {lod:.2f}, LOQ = {loq:.2f}")
    a.axvline(lod, color="#A16207", ls=":", lw=0.8); a.axvline(loq, color="#B91C1C", ls=":", lw=0.8); a.legend(loc="upper left"); a.set_ylabel(d["y_label"])
    b.plot(x, r, "o", color="k", mfc="white", ms=3.5); b.axhline(0, color="#1F77B4"); b.set_ylabel("Resid."); b.set_xlabel(d["x_label"]); finish(a, st); finish(b, st)
    return fig


def demo_chrom():
    from . import synthetic as S
    t = np.linspace(0, 15, 3000); peaks = [(2.1, 30, 0.08, "Peak 1"), (4.6, 55, 0.1, "Peak 2"), (5.1, 22, 0.1, "Peak 3"), (9.8, 40, 0.15, "Peak 4")]
    y = S.peaks(t, [q[0] for q in peaks], [q[1] for q in peaks], [q[2] for q in peaks]) + 1 + R.normal(0, 0.2, len(t))
    return {"x": t, "y": y, "peaks": peaks, "x_label": "Retention time (min)", "y_label": "Detector signal (mV)"}


@template("chromatogram", "Chromatogram with integrated, labelled peaks", CAT_ANA, "Peak areas shaded; labels from the user's peak table.", "xy_series",
          {"x": "time", "y": "signal", "peaks": "peak table (Rt, name) from user"}, demo_chrom, {}, "Origin: Peak Analyzer > Integrate Peaks.", "generic", ["HPLC", "GC", "IC"], ["peak areas, Rt"])
def draw_chrom(d, st, p):
    fig, ax = new_fig(st); ax.plot(d["x"], d["y"], "k", lw=0.7); cols = distinct_colors(st, [q[3] for q in d["peaks"]])
    for (c0, h, w, nm), c in zip(d["peaks"], cols):
        m = (d["x"] > c0 - 3 * w) & (d["x"] < c0 + 3 * w); ax.fill_between(d["x"][m], 1, d["y"][m], color=c, alpha=0.4, lw=0)
        ax.text(c0, d["y"][m].max() + 1.5, f"{nm}\n{c0:.2f} min", ha="center", fontsize=6.5)
    _lab(ax, d); ax.set_xlim(d["x"].min(), d["x"].max()); finish(ax, st)
    return fig


# ------------------------------------------------------------------ physics & signal
def demo_fft():
    t = np.linspace(0, 1, 2000, endpoint=False); y = np.sin(2 * np.pi * 50 * t) + 0.5 * np.sin(2 * np.pi * 120 * t) + R.normal(0, 0.4, len(t))
    return {"t": t, "y": y, "x_label": "Time (s)", "y_label": "Signal (V)"}


@template("fft_spectrum", "Signal + amplitude spectrum (FFT)", CAT_PHYS, "Time signal above, single-sided amplitude spectrum below with dominant peaks marked.",
          "signal", {"t": "time", "y": "signal"}, demo_fft, {}, "Origin: Analysis > Signal Processing > FFT.", "generic", ["vibration", "acoustics", "sensors", "AE"], ["FFT, dominant frequencies"])
def draw_fft(d, st, p):
    fig, (a, b) = new_fig(st, 2, 1, gridspec_kw={"hspace": 0.45}); t, y = d["t"], d["y"]; a.plot(t, y, color="#1F77B4", lw=0.5); a.set_xlabel(d["x_label"]); a.set_ylabel(d["y_label"])
    n = len(t); f = np.fft.rfftfreq(n, t[1] - t[0]); A = 2 * np.abs(np.fft.rfft(y)) / n; b.plot(f, A, "k", lw=0.7)
    for k in np.argsort(A)[-2:]:
        b.annotate(f"{f[k]:.0f} Hz", (f[k], A[k]), xytext=(4, 0), textcoords="offset points", fontsize=6.5)
    b.set_xlim(0, f.max() / 4); b.set_xlabel("Frequency (Hz)"); b.set_ylabel("Amplitude (V)")
    for k, ax in enumerate((a, b)):
        panel_title(ax, k); finish(ax, st)
    return fig


# ------------------------------------------------------------------ environment
def demo_ts():
    t = np.arange(0, 730); y = 10 + 8 * np.sin(2 * np.pi * t / 365) + R.normal(0, 2.5, len(t))
    return {"t": t, "y": y, "x_label": "Day", "y_label": "Temperature (°C)", "window": 30}


@template("time_series_band", "Time series with moving average and min–max band", CAT_ENV, "Long monitoring records: raw (light), rolling mean (bold), rolling range band.",
          "signal", {"t": "time", "y": "value"}, demo_ts, {"window": 30}, "Origin: Line + Smoothing (Adjacent Averaging) + band.", "generic", ["monitoring", "climate", "sensors"], ["rolling mean, rolling min/max"])
def draw_ts(d, st, p):
    import pandas as pd
    fig, ax = new_fig(st); s = pd.Series(d["y"]); w = p["window"]; m = s.rolling(w, center=True).mean(); lo = s.rolling(w, center=True).min(); hi = s.rolling(w, center=True).max()
    ax.plot(d["t"], d["y"], color="#BBBBBB", lw=0.5, label="Raw"); ax.fill_between(d["t"], lo, hi, color="#1F77B4", alpha=0.15, lw=0, label=f"{w}-point range")
    ax.plot(d["t"], m, color="#1F77B4", lw=1.4, label=f"{w}-point mean"); _lab(ax, d); ax.legend(ncols=3, loc="upper right"); finish(ax, st)
    return fig


def demo_depth():
    z = np.linspace(0, 40, 30)
    return {"depth": z, "vars": [{"name": "Chloride (wt.%)", "v": 0.8 * np.exp(-z / 8) + 0.05}, {"name": "pH", "v": 12.8 - 2.5 * np.exp(-z / 5)},
                                  {"name": "Porosity (%)", "v": 14 - 3 * (1 - np.exp(-z / 6)) + R.normal(0, 0.3, 30)}], "depth_label": "Depth (mm)"}


@template("depth_profile", "Depth profiles (depth downward, shared y)", CAT_ENV, "Several variables against depth in side-by-side panels; depth axis reversed.",
          "profile", {"depth": "depth column", "vars": "one column per variable"}, demo_depth, {}, "Origin: Multi-panel horizontal, Y reversed.", "generic",
          ["soil", "sediment", "concrete cores", "oceanography"])
def draw_depth(d, st, p):
    n = len(d["vars"]); fig, axs = new_fig(st, 1, n, sharey=True, gridspec_kw={"wspace": 0.12}); cols = distinct_colors(st, [v["name"] for v in d["vars"]])
    for k, (ax, v, c) in enumerate(zip(np.atleast_1d(axs), d["vars"], cols)):
        ax.plot(v["v"], d["depth"], "-o", ms=3, color=c, mfc="white"); ax.set_xlabel(v["name"]); panel_title(ax, k); finish(ax, st)
    axs[0].invert_yaxis(); axs[0].set_ylabel(d["depth_label"])
    return fig


# ------------------------------------------------------------------ sustainability / decision
def demo_pareto():
    n = 40; x = R.uniform(20, 80, n); y = 900 - 6 * x + R.uniform(0, 250, n); s = R.uniform(1, 5, n)
    return {"x": x, "y": y, "s": s, "x_label": "Performance (unit) →", "y_label": "← Impact (unit)", "s_label": "Cost"}


@template("pareto_front", "Pareto front (trade-off of two objectives, third as colour)", CAT_SUS,
          "All options as points; non-dominated set highlighted and joined.", "scatter", {"x": "objective to maximise", "y": "objective to minimise", "s": "optional third"},
          demo_pareto, {}, "Origin: Bubble/colour scatter + line through front.", "generic", ["design optimisation", "LCA", "mix design"], ["non-dominated sorting"])
def draw_pareto(d, st, p):
    fig, ax = new_fig(st); x, y = d["x"], d["y"]; sc = ax.scatter(x, y, c=d["s"], cmap="viridis", s=22, edgecolor="k", lw=0.3)
    front = [i for i in range(len(x)) if not np.any((x >= x[i]) & (y <= y[i]) & ((x > x[i]) | (y < y[i])))]; front = sorted(front, key=lambda i: x[i])
    ax.plot(x[front], y[front], "-o", color="#C0141E", mfc="none", ms=7, label="Pareto front"); fig.colorbar(sc, ax=ax, pad=0.01).set_label(d["s_label"])
    _lab(ax, d); ax.legend(); finish(ax, st)
    return fig


def demo_sankey():
    return {"flows": [("Raw material A", "Process", 60), ("Raw material B", "Process", 30), ("Fuel", "Process", 10),
                      ("Process", "Product", 62), ("Process", "Emissions", 28), ("Process", "Losses", 10)], "unit": "t"}


@template("sankey_mass_energy", "Sankey diagram (mass / energy flows)", CAT_SUS, "Inputs → process → outputs with widths proportional to flow; balance checked.",
          "flows", {"source": "from", "target": "to", "value": "amount"}, demo_sankey, {}, "Origin: Plot > Categorical > Sankey (Sankey.otpu).", "generic",
          ["mass balance", "energy balance", "LCA"], ["input = output check"])
def draw_sankey(d, st, p):
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch, Rectangle
    fig, ax = new_fig(st); nodes = list(dict.fromkeys([f[0] for f in d["flows"]] + [f[1] for f in d["flows"]]))
    level = {}
    for n in nodes:
        level[n] = 0 if all(f[1] != n for f in d["flows"]) else (1 if any(f[0] == n for f in d["flows"]) else 2)
    tot = {n: max(sum(f[2] for f in d["flows"] if f[0] == n), sum(f[2] for f in d["flows"] if f[1] == n)) for n in nodes}
    scale = 0.8 / max(sum(tot[n] for n in nodes if level[n] == L) for L in (0, 1, 2)); pos = {}; gap = 0.03
    for L in (0, 1, 2):
        y = 0.05
        for n in [n for n in nodes if level[n] == L]:
            h = tot[n] * scale; pos[n] = [L * 0.45 + 0.02, y, h, y, y]; y += h + gap
    cols = distinct_colors(st, nodes)
    for n, c in zip(nodes, cols):
        x0, y0, h, _, _ = pos[n]; ax.add_patch(Rectangle((x0, y0), 0.03, h, color=c))
        ax.text(x0 + (0.04 if level[n] < 2 else -0.01), y0 + h / 2, f"{n} ({tot[n]:.0f} {d['unit']})", va="center", ha="left" if level[n] < 2 else "right", fontsize=6.5)
    for a, b, v in d["flows"]:
        h = v * scale; xa = pos[a][0] + 0.03; ya = pos[a][3]; xb = pos[b][0]; yb = pos[b][4]; pos[a][3] += h; pos[b][4] += h; xm = (xa + xb) / 2
        verts = [(xa, ya), (xm, ya), (xm, yb), (xb, yb), (xb, yb + h), (xm, yb + h), (xm, ya + h), (xa, ya + h), (xa, ya)]
        codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.LINETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts, codes), color=cols[nodes.index(a)], alpha=0.35, lw=0))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    return fig


def demo_tornado():
    return {"params": ["Parameter A", "Parameter B", "Parameter C", "Parameter D", "Parameter E"], "low": np.array([-18, -11, -7, -4, -2.0]),
            "high": np.array([15, 13, 6, 5, 1.5]), "base": 0, "x_label": "Change in result (%)"}


@template("sensitivity_tornado", "Tornado diagram (sensitivity)", CAT_SUS, "Effect of low/high setting of each parameter on a result, sorted by impact.",
          "sensitivity", {"params": "names", "low": "result change at low", "high": "result change at high"}, demo_tornado, {},
          "Origin: Floating Bar.", "generic", ["LCA", "cost", "uncertainty"])
def draw_tornado(d, st, p):
    fig, ax = new_fig(st); o = np.argsort(np.abs(d["high"] - d["low"])); y = np.arange(len(o))
    ax.barh(y, d["low"][o], color="#1F77B4", label="Low setting"); ax.barh(y, d["high"][o], color="#D62728", label="High setting"); ax.axvline(d["base"], color="k", lw=0.8)
    ax.set_yticks(y); ax.set_yticklabels(np.array(d["params"])[o]); ax.set_xlabel(d["x_label"]); ax.legend(loc="lower right"); finish(ax, st); ax.yaxis.set_minor_locator(plt.NullLocator())
    return fig

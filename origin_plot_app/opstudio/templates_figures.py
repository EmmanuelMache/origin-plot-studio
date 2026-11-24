"""Composed figures: several panels that belong together in one figure (two rows of size distributions with their tables,
heat flow with inset beside cumulative heat with group brackets, a flow diagram of a procedure). Illustrative data only."""
import numpy as np
from matplotlib.patches import FancyBboxPatch, Circle
from .core import template, new_fig, finish, panel_title, series_color, distinct_colors, make_fig, fig_size
from . import synthetic as S
from .templates_materials import CAT_PSD, CAT_CAL, CAT_GEN


def _cum(y):
    """Cumulative curve of a size distribution given as volume % per size class: running sum, scaled to 100."""
    y = np.nan_to_num(np.asarray(y, float)); c = np.cumsum(y); return c / c[-1] * 100 if c[-1] else c


def _dvals(x, cum): return [float(np.interp(q, cum, x)) for q in (10, 50, 90)]


def demo_psd_groups():
    dd = np.logspace(-1, 3, 300); out = []
    for title, rows in (("Group 1", [("Material 1", 35, 1.0), ("Material 2", 110, 0.9), ("Material 3", 14, 1.1), ("Material 4", 12, 1.3)]), ("Group 2", [("Sample A", 16, 1.1), ("Sample B", 17, 0.8), ("Sample C", 15, 0.85), ("Sample D", 13, 0.9)])):
        out.append({"title": title, "series": [{"name": n, "x": dd, "y": S.lognormal_psd(dd, d50, sg)[0]} for n, d50, sg in rows]})
    return {"panels": out, "x_label": "Particle size (µm)", "y_label": "Differential volume (%)", "y2_label": "Cumulative volume (%)"}


@template("psd_groups_2x2", "Particle size, two groups: differential + cumulative with d-value tables (2 × 2)", CAT_PSD,
          "One row per group of materials (one file per group): differential and cumulative curves, the legend above the row, d10 / d50 / d90 in a table in the cumulative panel.",
          "xy_series", {"x": "size (µm)", "series": "volume % per material", "panels": "one file (or sheet) per row"}, demo_psd_groups, {"table": True, "dashed": []},
          "Origin: four line graphs, X log10, merged 2 × 2 (Graph > Merge Graph Windows); table via Insert > Table.", "house", ["laser diffraction"],
          ["cumulative = running sum of the volume % per size class, scaled to 100", "d10 / d50 / d90 by interpolation of the cumulative curve"])
def draw_psd_groups(d, st, p):
    n = len(d["panels"]); fig, axs = new_fig(st, n, 2, aspect=1.0 if n > 1 else 1.9, gridspec_kw={"wspace": 0.24, "hspace": 0.55}, squeeze=False)
    fs = st["font"]["size_pt"]; k = 0
    for r, pan in enumerate(d["panels"]):
        a, b = axs[r]; names = [s["name"] for s in pan["series"]]; cols = distinct_colors(st, names); rows = []
        for i, (s, c) in enumerate(zip(pan["series"], cols)):
            cum = np.asarray(s["cum"]) if "cum" in s and p.get("cum_from_file") else _cum(s["y"]); ls = "--" if (i + 1) in [int(v) for v in p.get("dashed") or []] else "-"
            a.plot(s["x"], s["y"], color=c, ls=ls, label=s["name"]); b.plot(s["x"], cum, color=c, ls=ls); rows.append((s["name"], c, _dvals(np.asarray(s["x"], float), cum)))
        for ax, yl in ((a, d.get("y_label", "")), (b, d.get("y2_label", ""))):
            ax.set_xscale("log"); ax.set_xlabel(d.get("x_label", "")); ax.set_ylabel(yl); panel_title(ax, k, pan.get("title", "") + (": cumulative" if ax is b and pan.get("title") else "")); k += 1; finish(ax, st)
            ax.set_ylim(bottom=0)
        b.set_ylim(0, 100)
        h, l = a.get_legend_handles_labels(); pa, pb = a.get_position(), b.get_position()
        fig.legend(h, l, loc="lower center", bbox_to_anchor=((pa.x0 + pb.x1) / 2, pa.y1 + 0.045 / max(1, n) * 2), ncol=min(len(l), 6), frameon=False, fontsize=fs["legend"])
        if p.get("table"):
            x0, y0, dy = 0.04, 0.95, 0.075; tf = fs["annotation"]
            b.add_patch(FancyBboxPatch((x0 - 0.015, y0 - dy * (len(rows) + 1.25)), 0.56, dy * (len(rows) + 1.45), transform=b.transAxes, boxstyle="square,pad=0", fc="white", ec="#BBBBBB", lw=0.5, zorder=5))
            for j, hname in enumerate(("Material", "d$_{10}$", "d$_{50}$", "d$_{90}$")):
                b.text(x0 + (0 if j == 0 else 0.20 + 0.115 * j), y0 - dy * 0.9, hname, transform=b.transAxes, fontsize=tf, fontweight="bold", ha="left" if j == 0 else "right", va="center", zorder=6)
            for i, (nm, c, dv) in enumerate(rows):
                yy = y0 - dy * (i + 1.9); b.text(x0, yy, nm[:16], transform=b.transAxes, fontsize=tf, color=c, va="center", zorder=6)
                for j, v in enumerate(dv): b.text(x0 + 0.20 + 0.115 * (j + 1), yy, f"{v:.2f}" if v < 100 else f"{v:.1f}", transform=b.transAxes, fontsize=tf, ha="right", va="center", zorder=6)
    return fig


def demo_cal_pair():
    t = np.linspace(0.01, 168, 3000); ser = []
    for i, n in enumerate(S.SAMPLES):
        hf = S.heat_flow(t, amp=2.0 - 0.33 * i, t_peak=10 + 7 * i, w=6 + 3 * i, seed=i); ser.append({"name": n, "x": t, "y": hf})
    return {"series": ser, "x_label": "Time (h)", "y_label": "Heat flow (mW g$^{-1}$)", "y2_label": "Cumulative heat (J g$^{-1}$)",
            "regimes": [{"name": "Group I", "members": S.SAMPLES[:3]}, {"name": "Group II", "members": S.SAMPLES[3:4]}, {"name": "Group III", "members": S.SAMPLES[4:]}]}


@template("calorimetry_pair_inset_groups", "Heat flow with inset (a) + cumulative heat with group brackets (b)", CAT_CAL,
          "The complete calorimetry figure: heat flow with the first hours as an inset, beside cumulative heat with brackets that group the samples. Groups are yours; without groups no bracket is drawn.",
          "xy_series", {"x": "time (h)", "series": "heat flow per sample", "regimes": "your groups: a name and the samples in it"}, demo_cal_pair, {"inset": True, "inset_range": [0, 12], "x_max": 168, "cum_factor": 3.6},
          "Origin: two line graphs merged 1 × 2; inset via Graph > New Layer; brackets via Insert > Line.", "house", ["isothermal calorimetry"],
          ["cumulative heat (J/g) = integral of heat flow (mW/g) over time (h) × 3.6"])
def draw_cal_pair(d, st, p):
    fig, (a, b) = new_fig(st, 1, 2, aspect=2.3, gridspec_kw={"wspace": 0.3}); names = [s["name"] for s in d["series"]]; cols = [series_color(st, n, i) for i, n in enumerate(names)]
    xm = float(p.get("x_max") or max(np.nanmax(s["x"]) for s in d["series"])); f = float(p.get("cum_factor") or 1.0); cums = {}
    for s, c in zip(d["series"], cols):
        x, y = np.asarray(s["x"], float), np.asarray(s["y"], float); a.plot(x, y, color=c, label=s["name"])
        cum = np.concatenate([[0.0], np.cumsum(0.5 * (y[1:] + y[:-1]) * np.diff(x))]) * f; cums[s["name"]] = (x, cum); b.plot(x, cum, color=c, label=s["name"])
    lo, hi = p.get("inset_range") or [0, 12]; late = [np.asarray(s["y"])[(np.asarray(s["x"]) > 0.5)] for s in d["series"]]
    if p.get("inset", True):                              # unticked: no inset
        ins = a.inset_axes([0.47, 0.42, 0.5, 0.52])
        for s, c in zip(d["series"], cols): ins.plot(s["x"], s["y"], color=c, lw=st["lines"]["width_pt"] * 0.8)
        ins.set_xlim(lo, hi)
        ins.set_ylim(0, max(float(np.nanmax(np.asarray(s["y"])[(np.asarray(s["x"]) > 0.5) & (np.asarray(s["x"]) < hi)])) if np.any((np.asarray(s["x"]) > 0.5) & (np.asarray(s["x"]) < hi)) else 1.0 for s in d["series"]) * 1.15)
        ins.tick_params(labelsize=st["font"]["size_pt"]["tick"] - 2); ins.set_title(f"first {hi:g} h", fontsize=st["font"]["size_pt"]["annotation"], fontweight="normal", loc="center", pad=2)
    a.set_xlim(0, xm); a.set_ylim(0, max(float(np.nanmax(y)) for y in late if len(y)) * 1.08); a.set_xlabel(d.get("x_label", "")); a.set_ylabel(d.get("y_label", "")); panel_title(a, 0); finish(a, st)
    b.set_xlim(0, xm); b.set_ylim(bottom=0); b.set_xlabel(d.get("x_label", "")); b.set_ylabel(d.get("y2_label", "")); panel_title(b, 1); b.legend(loc="upper left"); finish(b, st)
    for r in d.get("regimes") or []:
        ys = [float(np.interp(xm, *cums[n])) for n in r.get("members", []) if n in cums]
        if not ys: continue
        pad = 0.012 * b.get_ylim()[1]; y0, y1 = min(ys) - pad * 2, max(ys) + pad * 2; col = cols[names.index(next(n for n in r["members"] if n in cums))]
        b.plot([xm * 1.012, xm * 1.03, xm * 1.03, xm * 1.012], [y0, y0, y1, y1], color="k", lw=0.7, clip_on=False)
        b.text(xm * 1.045, (y0 + y1) / 2, r["name"], va="center", ha="left", fontsize=st["font"]["size_pt"]["annotation"], fontweight="bold", color=col, clip_on=False)
    return fig


def demo_flow():
    return {"flow_steps": [{"stage": 1, "title": "Raw materials", "detail": "three materials + two correctives"}, {"stage": 1, "title": "Drying + grinding", "detail": "105 °C, below 125 µm"}, {"stage": 1, "title": "Wet milling", "detail": "solid + water"},
                           {"stage": 1, "title": "Slurry drying", "detail": "24 h"}, {"stage": 2, "title": "Firing", "detail": "temperature, time"}, {"stage": 2, "title": "Cooling", "detail": "air"}, {"stage": 2, "title": "Products", "detail": "five compositions"},
                           {"stage": 3, "title": "Method 1", "detail": "phase content"}, {"stage": 3, "title": "Method 2", "detail": "chemistry"}, {"stage": 3, "title": "Method 3", "detail": "heat of reaction"}, {"stage": 3, "title": "Method 4", "detail": "titration"}],
            "stage_names": {}}


@template("process_flow_steps", "Flow diagram of a procedure (numbered stages, boxes and arrows)", CAT_GEN,
          "The experimental procedure as a diagram: one row per stage, one box per step, arrows between the steps. Texts come from your table. Photographs and icons are not drawn (add them in Origin or PowerPoint).",
          "steps", {"title": "first text column: the step", "detail": "second text column (optional): conditions", "stage": "a number column (optional): the row of the diagram"}, demo_flow, {"arrows": True},
          "Origin: Insert > Text and Insert > Arrow on an empty graph page (no plot type of its own).", "generic", ["methods section", "graphical abstract"])
def draw_flow(d, st, p):
    steps = d["flow_steps"]; stages = []
    for s in steps:
        if s["stage"] not in stages: stages.append(s["stage"])
    rows = [[s for s in steps if s["stage"] == g] for g in stages]; n = len(rows); m = max(len(r) for r in rows)
    fig = make_fig(fig_size(st, "double", max(1.25, 2.6 / max(1, n) * 1.5))); ax = fig.add_axes([0.01, 0.02, 0.98, 0.96]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    fs = st["font"]["size_pt"]; rh = 1.0 / n; blue = st["palette"]["series"][1] if len(st["palette"]["series"]) > 1 else "#1F77B4"; names = d.get("stage_names") or {}
    for r, row in enumerate(rows):
        yc = 1 - rh * (r + 0.5); bw = min(0.2, 0.86 / len(row) * 0.78); gap = (0.88 - bw * len(row)) / max(1, len(row) - 1) if len(row) > 1 else 0; bh = min(0.62 * rh, 0.22)
        ax.add_patch(Circle((0.035, yc), 0.022, transform=ax.transAxes, fc="#DCE9F8", ec="k", lw=0.6)); ax.text(0.035, yc, str(names.get(str(row[0]["stage"]), row[0]["stage"])), ha="center", va="center", fontsize=fs["base"], fontweight="bold")
        for i, s in enumerate(row):
            x0 = 0.09 + i * (bw + gap); ax.add_patch(FancyBboxPatch((x0, yc - bh / 2), bw, bh, boxstyle="round,pad=0.004,rounding_size=0.015", fc="white", ec="k", lw=0.8))
            ax.text(x0 + bw / 2, yc + (bh * 0.14 if s.get("detail") else 0), s["title"], ha="center", va="center", fontsize=fs["base"], fontweight="bold", wrap=True)
            if s.get("detail"): ax.text(x0 + bw / 2, yc - bh * 0.22, s["detail"], ha="center", va="center", fontsize=fs["annotation"], wrap=True)
            if p.get("arrows", True) and i < len(row) - 1 and gap > 0.01: ax.annotate("", xy=(x0 + bw + gap - 0.004, yc), xytext=(x0 + bw + 0.004, yc), arrowprops=dict(arrowstyle="-|>", color=blue, lw=1.6))
        if r < n - 1: ax.plot([0.02, 0.98], [1 - rh * (r + 1)] * 2, color=blue, lw=0.8)
    return fig

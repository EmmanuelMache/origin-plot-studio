"""Make the thumbnails of the galleries (origin_plot_app/gallery): one per gallery graph type (drawn by the app from the gallery templates)
and one per Analysis group (drawn by the app from its example files, or a labelled illustration). Run: python tools/make_gallery.py"""
import os, re, sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "origin_plot_app"
sys.path.insert(0, str(APP))
import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import smart_plots as sp
import gallery_graphs as tg

OUT = APP / "gallery"; OUT.mkdir(exist_ok=True)
TPL = ROOT / "tests" / "gallery_templates"
EX = APP / "examples_synthetic"
W, H, DPI = 3.6, 2.5, 100


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=DPI, facecolor="white")
    print("written", name)


def from_item(path, name, kind=None, opt=None, pick=0):
    its, _ = sp.load_file(str(path))
    pool = []
    sp.prepare(pool, its, opt or {})
    it = [i for i in pool if (kind is None or i.kind == kind)][pick]
    fig = Figure(figsize=(W * 1.6, H * 1.6)); FigureCanvasAgg(fig)
    sp.preview_figure(it.spec, fig=fig)
    fig.set_size_inches(W * 1.6, H * 1.6)
    fig.savefig(OUT / f"{name}.png", dpi=DPI / 1.6, facecolor="white")
    print("written", name)


def figtype():
    for tid in tg.TYPES:
        f = sorted(glob.glob(str(TPL / f"{tid}_*.xlsx")))
        if not f:
            print("no template for", tid); continue
        try:
            book = tg.read_book(f[0])
            fig, _ = tg.figure(tid, book)
            fig.savefig(OUT / f"type_{tid}.png", dpi=40, facecolor="white")
            print("written", tid)
        except Exception as e:
            print("failed", tid, e)


def sketch(name, draw):
    fig = Figure(figsize=(W, H)); FigureCanvasAgg(fig); ax = fig.add_axes([0.12, 0.16, 0.84, 0.76])
    draw(ax); ax.tick_params(labelsize=7, direction="in")
    for s in ax.spines.values(): s.set_linewidth(1.0)
    save(fig, name)


def analysis():
    x = np.linspace(0, 10, 400); rng = np.random.default_rng(3)
    pk = lambda c, w, h: h * np.exp(-0.5 * ((x - c) / w) ** 2)
    sig = pk(3, 0.35, 1.0) + pk(6, 0.5, 0.7) + pk(8, 0.3, 0.45)
    def smoothing(ax):
        y = sig + rng.normal(0, 0.06, len(x)); ax.plot(x, y, color="0.6", lw=0.8, label="raw")
        from scipy.signal import savgol_filter; ax.plot(x, savgol_filter(y, 31, 3), color="#C00000", lw=1.6, label="smoothed"); ax.legend(fontsize=7, frameon=False)
    def baseline(ax):
        b = 0.15 + 0.05 * x; ax.plot(x, sig + b, color="k", lw=1.2); ax.plot(x, b, "--", color="#C00000", lw=1.2); ax.fill_between(x, b, sig + b, color="#C00000", alpha=0.08)
    def normalise(ax):
        ax.plot(x, sig / sig.max(), color="k", lw=1.2); ax.plot(x, 0.6 * pk(5, 0.8, 1) / 0.6, color="#1F77B4", lw=1.2); ax.set_ylabel("normalised", fontsize=7)
    def calculus(ax):
        ax.plot(x, sig, color="k", lw=1.2); m = (x > 2) & (x < 4); ax.fill_between(x[m], 0, sig[m], color="#2CA02C", alpha=0.3); ax.text(3, 0.45, "area", fontsize=8, ha="center")
    def peaks(ax):
        y = sig + rng.normal(0, 0.02, len(x)); ax.plot(x, y, color="k", lw=1.2)
        for c, h in ((3, 1.0), (6, 0.7), (8, 0.45)): ax.annotate(f"{c:.1f}", (c, h), (c, h + 0.15), fontsize=7, ha="center", arrowprops=dict(arrowstyle="-", lw=0.6))
        ax.set_ylim(top=1.3)
    def fitting(ax):
        xs = np.linspace(0, 10, 25); ys = 0.2 + 0.12 * xs + rng.normal(0, 0.08, len(xs)); ax.plot(xs, ys, "o", ms=4, mfc="none", color="k")
        ax.plot(x, 0.2 + 0.12 * x, color="#C00000", lw=1.5); ax.text(0.5, 1.3, "y = a + b x", fontsize=8)
    def transform(ax):
        ax.plot(x + 0.1, np.exp(-x / 3) * 10, color="k", lw=1.2); ax.set_yscale("log"); ax.set_ylabel("log y", fontsize=7)
    def arithmetic(ax):
        a = sig; b = 0.8 * pk(3, 0.35, 1.0) + 0.3; ax.plot(x, a, color="k", lw=1.0, label="A"); ax.plot(x, b, color="#1F77B4", lw=1.0, label="B"); ax.plot(x, a - b, color="#C00000", lw=1.3, label="A − B"); ax.legend(fontsize=7, frameon=False)
    def frequency(ax):
        f = np.linspace(0, 5, 300); ax.plot(f, pk(0, 1, 1)[:300] * 0 + np.exp(-0.5 * ((f - 1.2) / 0.08) ** 2) + 0.4 * np.exp(-0.5 * ((f - 2.6) / 0.1) ** 2), color="k", lw=1.2); ax.set_xlabel("frequency", fontsize=7)
    def stats(ax):
        d = rng.normal(40, 6, 400); ax.hist(d, bins=18, color="#9EB9D4", edgecolor="#17324D", lw=0.6); ax.axvline(d.mean(), color="#C00000", lw=1.3); ax.text(d.mean() + 1, 60, "mean", fontsize=7, color="#C00000")
    def phases(ax):
        lab = ["C3S", "C2S", "C3A", "C4AF"]; v = [62, 14, 8, 11]; ax.bar(lab, v, color=["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728"]); ax.set_ylabel("wt.%", fontsize=7)
    def correct(ax):
        y = sig * 800 + 150 + rng.poisson(20, len(x)); ax.plot(x, y, color="0.55", lw=0.8, label="measured"); ax.plot(x, sig * 1100 + 150, color="#C00000", lw=1.2, label="improved"); ax.legend(fontsize=7, frameon=False)
    for name, f in (("Smoothing", smoothing), ("Baseline", baseline), ("Normalise", normalise), ("Calculus", calculus), ("Peaks", peaks), ("Curve fitting", fitting),
                    ("Transform and convert", transform), ("Curve arithmetic", arithmetic), ("Frequency", frequency), ("Statistics", stats),
                    ("Phases and composition", phases), ("XRD: correct and generate scans", correct)):
        sketch("analysis_" + slug(name), f)
    for name, path, kind, opt in (("XRD", EX / "xrd_raw.csv", None, {}), ("Peak labels", EX / "xrd_raw.csv", None, {"label_peaks": True}), ("TGA", EX / "tga.xlsx", None, {}),
                                  ("FTIR", EX / "ftir.xlsx", None, {}), ("Particle size (PSD)", EX / "psd.xlsx", None, {}), ("Calorimetry", EX / "calorimetry.csv", None, {}),
                                  ("Thermodynamic modelling", ROOT / "tests" / "modelling" / "gems_hydration.csv", None, {})):
        try:
            from_item(path, "analysis_" + slug(name), kind, opt)
        except Exception as e:
            print("failed", name, e)


if __name__ == "__main__":
    figtype()
    analysis()

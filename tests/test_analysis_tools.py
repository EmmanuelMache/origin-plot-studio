"""Known answers for the Analysis menu (origin_plot_app/analysis_tools.py).  Run: python tests/test_analysis_tools.py"""
import sys, warnings
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "origin_plot_app"))
import analysis_tools as T

ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))

warnings.simplefilter("error")
rng = np.random.default_rng(1)
x = np.linspace(10, 60, 2001)
pk = lambda c, h, w: h * np.exp(-4 * np.log(2) * ((x - c) / w) ** 2)
truth = 200 + 2 * x + pk(26.6, 5000, 0.15) + pk(29.4, 3000, 0.2) + pk(29.8, 1500, 0.2)
S1 = T.Curve("S1", x, rng.poisson(truth).astype(float), "2θ (°)", "Intensity (counts)")
S2 = T.Curve("S2", x, rng.poisson(truth).astype(float), "2θ (°)", "Intensity (counts)")

bad = []
for lab, (g, fn, spec, d, how) in T.TOOLS.items():
    kw = {"Area between two x values": dict(x_from=26, x_to=27), "Crop to an x range": dict(x_from=20, x_to=40),
          "Fit peaks (deconvolution)": dict(x_from=28.8, x_to=30.4, peaks=2), "Relative to the value at an x": dict(at_x=40)}.get(lab, {})
    try:
        T.run(lab, [S1] if how == 1 else [S1, S2], **kw)
    except Exception as e:
        bad.append((lab, repr(e)[:120]))
check(f"all {len(T.TOOLS)} tools run without error or warning", not bad, bad)

r = T.run("Fit peaks (deconvolution)", [S1], x_from=28.8, x_to=30.4, peaks=2, shape="Gaussian")[0][1].table
check("deconvolution of two overlapping peaks: centres, heights, widths", np.allclose(r["Centre"], [29.4, 29.8], atol=0.01) and np.allclose(r["Height"], [3000, 1500], rtol=0.05) and np.allclose(r["FWHM"], [0.2, 0.2], rtol=0.05), r[["Centre", "Height", "FWHM"]].round(3).values.tolist())
p = T.run("Find peaks", [S1], min_prominence_pct=5)[0][1].table
check("find peaks: 26.6, 29.4, 29.8", np.allclose(sorted(p["Position"])[:3], [26.6, 29.4, 29.8], atol=0.03), p["Position"].round(3).tolist())
lin = T.Curve("lin", x, 3 + 0.5 * x + rng.normal(0, 0.1, len(x)), "t", "y")
f = T.run("Fit a model", [lin], model="Linear: y = a + b·x")[0][1].table.set_index("Parameter")["Value"]
check("linear fit: a = 3, b = 0.5", abs(f["a"] - 3) < 0.05 and abs(f["b"] - 0.5) < 0.002, (round(f["a"], 4), round(f["b"], 5)))
ex = T.Curve("e", x, 7 * np.exp(-0.05 * x) + 1, "t", "y")
f = T.run("Fit a model", [ex], model="Exponential: y = a·exp(b·x) + c")[0][1].table.set_index("Parameter")["Value"]
check("exponential fit: a = 7, b = -0.05, c = 1", np.allclose([f["a"], f["b"], f["c"]], [7, -0.05, 1], rtol=1e-3), [round(f[k], 5) for k in "abc"])
av = T.Curve("av", x, 0.9 * (1 - np.exp(-(0.08 * (x - 10)) ** 2.5)), "t", "alpha")
f = T.run("Fit a model", [av], model="Avrami (JMAK): y = ymax·(1 - exp(-(k·(x-x0))^n))")[0][1].table.set_index("Parameter")["Value"]
check("Avrami fit: n = 2.5, k = 0.08", abs(f["n"] - 2.5) < 0.05 and abs(f["k"] - 0.08) < 0.002, (round(f["n"], 3), round(f["k"], 4)))
one = T.Curve("one", x, np.ones_like(x))
check("area of y = 1 from 20 to 30 is 10", abs(T.run("Area between two x values", [one], x_from=20, x_to=30)[0][1].table["Area"][0] - 10) < 1e-9)
sq = T.Curve("sq", x, x ** 2)
d1 = T.run("First derivative", [sq])[0][1].curves[0][2]
check("derivative of x² is 2x", np.allclose(d1[10:-10], 2 * x[10:-10], rtol=1e-6))
ci = T.run("Cumulative integral", [T.Curve("c", x, 2 * x)])[0][1].curves[0][2]
check("integral of 2x from 10 is x² - 100", np.allclose(ci, x ** 2 - 100, rtol=1e-6, atol=1e-6))
bl = T.Curve("bl", x, 200 + 2 * x + pk(30, 1000, 0.3), "2θ (°)", "I (counts)")
b = T.run("Polynomial (iterative)", [bl], order=1)[0][1].curves
check("polynomial baseline removes the sloping background", abs(np.median(b[0][2])) < 2 and abs(b[0][2].max() - 1000) < 20, (round(float(np.median(b[0][2])), 2), round(float(b[0][2].max()), 1)))
tt = T.run("XRD: 2θ to d-spacing", [T.Curve("q", np.array([26.64, 29.41, 33.0]), np.array([1, 2, 3.0]), "2θ (°)", "I")], wavelength=1.540598)[0][1]
check("Bragg: 26.64° (Cu Kα1) is d = 3.343 Å (quartz 101)", abs(tt.curves[0][1][-1] - 3.3434) < 0.001, round(float(tt.curves[0][1][-1]), 4))
check("transmittance 10 % is absorbance 1", abs(T.run("FTIR: transmittance to absorbance", [T.Curve("t", x[:3], np.array([10.0, 50.0, 100.0]))])[0][1].curves[0][2][0] - 1) < 1e-12)
a = T.Curve("A", x, np.full_like(x, 5.0)); bb = T.Curve("B", x, np.full_like(x, 2.0))
check("A - B and A / B", np.allclose(T.run("Difference A - B", [a, bb])[0][1].curves[0][2], 3) and np.allclose(T.run("Ratio A / B", [a, bb])[0][1].curves[0][2], 2.5))
try:
    T.run("Difference A - B", [a, bb, S1]); check("A - B with three curves is refused", False)
except T.AnalysisError as e:
    check("A - B with three curves is refused with a plain message", "exactly two" in str(e))
g1 = T.Curve("g1", np.arange(30.0), rng.normal(10, 1, 30)); g2 = T.Curve("g2", np.arange(30.0), rng.normal(13, 1, 30))
tt_ = T.run("t-test (two groups)", [g1, g2])[0][1].table
check("t-test: means 10 vs 13 differ (p < 0.001)", tt_["p (t-test)"][0] < 1e-3)
ds = T.run("Descriptive statistics", [T.Curve("d", np.arange(5.0), np.array([1, 2, 3, 4, 5.0]))])[0][1].table
check("descriptive statistics of 1..5: mean 3, SD 1.5811, median 3", abs(ds["Mean"][0] - 3) < 1e-12 and abs(ds["SD"][0] - 1.5811388) < 1e-6 and ds["Median"][0] == 3)
sn = T.Curve("sine", np.arange(0, 100, 0.1), np.sin(2 * np.pi * 0.5 * np.arange(0, 100, 0.1)), "t (s)", "y")
fr = T.run("FFT amplitude spectrum", [sn])[0][1].curves[0]
check("FFT of a 0.5 Hz sine peaks at 0.5", abs(fr[1][np.argmax(fr[2])] - 0.5) < 0.011, round(float(fr[1][np.argmax(fr[2])]), 3))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

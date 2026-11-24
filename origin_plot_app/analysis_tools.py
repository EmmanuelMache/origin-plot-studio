"""Analysis menu: data-analysis tools for the curves in Your graphs.

Every tool is a plain, deterministic calculation (numpy / scipy). Nothing here is guessed or made up by a model: the tools
only take the numbers of your curves and the settings you give, and they say exactly what they did (`note`), so the
provenance file can record it.

A tool takes curves  [Curve(name, x, y, xname, yname)]  and its settings, and returns a Result with
  curves  new curves to save and draw  [(column name, x, y)]  (all on one x axis, or several tables when the x differ)
  table   a results table (peak list, fit parameters, statistics) or None
  note    the formula / method in words
TOOLS maps the menu label to (group, function, settings, description, how many curves: 1 = each curve on its own,
"all" = all chosen curves together, 2 = exactly two).
"""
import math
import re
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

GROUPS = ["Smoothing", "Baseline", "Normalise", "Calculus", "Peaks", "Curve fitting", "Transform and convert",
          "Curve arithmetic", "Frequency", "Statistics"]


class AnalysisError(Exception):
    pass


@dataclass
class Curve:
    name: str
    x: np.ndarray
    y: np.ndarray
    xname: str = "x"
    yname: str = "y"


@dataclass
class Result:
    curves: list = field(default_factory=list)      # [(column name, x, y)]
    table: object = None                           # pandas DataFrame or None
    note: str = ""
    xname: str = ""


# ------------------------------------------------------------------------------------------------ helpers
def unit(name):
    m = re.search(r"\(([^()]*)\)\s*$", str(name))
    return m.group(1).strip() if m else ""


def base(name):
    return re.sub(r"\s*\([^()]*\)\s*$", "", str(name)).strip() or str(name)


def named(name, what, u=None):
    u = unit(name) if u is None else u
    return f"{base(name)} {what}" + (f" ({u})" if u else "")


def clean(c):
    x = np.asarray(c.x, float)
    y = np.asarray(c.y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 3:
        raise AnalysisError(f"{c.name}: fewer than 3 points with numbers")
    if np.any(np.diff(x) < 0):
        o = np.argsort(x, kind="stable")
        x, y = x[o], y[o]
    return x, y


def odd(n, at_most):
    n = int(max(3, n)) | 1
    return min(n, at_most if at_most % 2 else at_most - 1)


def _scipy():
    try:
        import scipy  # noqa: F401
    except Exception:
        raise AnalysisError("this tool needs the Python package SciPy (py -m pip install scipy)")


def _trapz(y, x):
    f = getattr(np, "trapezoid", None) or np.trapz
    return f(y, x)


def r2(y, f):
    ss = float(np.sum((y - np.mean(y)) ** 2))
    return 1.0 - float(np.sum((y - f) ** 2)) / ss if ss > 0 else float("nan")


# ------------------------------------------------------------------------------------------------ smoothing
def moving_average(c, window=5):
    x, y = clean(c)
    w = odd(window, len(y))
    k = np.ones(w) / w
    ys = np.convolve(np.pad(y, w // 2, mode="edge"), k, mode="valid")
    return Result([(named(c.yname, f"moving average {w}"), x, ys)], None, f"centred moving average over {w} points (edges padded with the end values)")


def savitzky_golay(c, window=11, order=3):
    _scipy()
    from scipy.signal import savgol_filter
    x, y = clean(c)
    w = odd(window, len(y))
    o = min(int(order), w - 1)
    return Result([(named(c.yname, f"Savitzky-Golay {w}/{o}"), x, savgol_filter(y, w, o))], None, f"Savitzky-Golay smoothing: window {w} points, polynomial order {o}")


def gaussian_smooth(c, sigma=2.0):
    _scipy()
    from scipy.ndimage import gaussian_filter1d
    x, y = clean(c)
    return Result([(named(c.yname, f"Gaussian {sigma:g}"), x, gaussian_filter1d(y, float(sigma), mode="nearest"))], None, f"Gaussian smoothing, sigma = {sigma:g} points")


def median_filter(c, window=5):
    _scipy()
    from scipy.signal import medfilt
    x, y = clean(c)
    w = odd(window, len(y))
    return Result([(named(c.yname, f"median {w}"), x, medfilt(y, w))], None, f"running median over {w} points (removes spikes)")


# ------------------------------------------------------------------------------------------------ baseline
def _baseline_result(c, x, y, b, what):
    return Result([(named(c.yname, "baseline-corrected"), x, y - b), (named(c.yname, f"baseline ({what})"), x, b)], None,
                  f"baseline: {what}; corrected = data - baseline")


def baseline_linear(c, points=10):
    x, y = clean(c)
    n = max(1, min(int(points), len(y) // 2))
    x0, y0, x1, y1 = np.mean(x[:n]), np.mean(y[:n]), np.mean(x[-n:]), np.mean(y[-n:])
    b = y0 + (y1 - y0) * (x - x0) / ((x1 - x0) or 1.0)
    return _baseline_result(c, x, y, b, f"straight line through the means of the first and last {n} points")


def baseline_polynomial(c, order=3, iterations=100):
    x, y = clean(c)
    o = max(0, int(order))
    t = (x - x.mean()) / (np.ptp(x) or 1.0)
    w = y.copy()
    for _ in range(int(iterations)):
        p = np.polyval(np.polyfit(t, w, o), t)
        nw = np.minimum(w, p)
        if np.allclose(nw, w, rtol=0, atol=1e-9 * (np.ptp(y) or 1.0)):
            break
        w = nw
    return _baseline_result(c, x, y, np.polyval(np.polyfit(t, w, o), t), f"iterative polynomial of order {o} (modified polyfit: points above the fit are clipped to it)")


def baseline_als(c, smoothness=1e5, asymmetry=0.01, iterations=10):
    _scipy()
    from scipy import sparse
    from scipy.sparse.linalg import spsolve
    x, y = clean(c)
    n = len(y)
    D = sparse.diags([1.0, -2.0, 1.0], [0, -1, -2], shape=(n, n - 2), dtype=float)
    DD = float(smoothness) * D.dot(D.transpose())
    w = np.ones(n)
    for _ in range(int(iterations)):
        W = sparse.spdiags(w, 0, n, n)
        z = spsolve((W + DD).tocsc(), w * y)
        w = asymmetry * (y > z) + (1 - asymmetry) * (y < z)
    return _baseline_result(c, x, y, z, f"asymmetric least squares (Eilers & Boelens), smoothness {smoothness:g}, asymmetry {asymmetry:g}, {int(iterations)} iterations")


def baseline_snip(c, iterations=40):
    x, y = clean(c)
    v = np.log(np.log(np.sqrt(np.clip(y, 0, None) + 1) + 1) + 1)
    n = len(v)
    for k in range(1, int(iterations) + 1):
        a = v.copy()
        a[k:n - k] = np.minimum(v[k:n - k], 0.5 * (v[:n - 2 * k] + v[2 * k:]))
        v = a
    b = (np.exp(np.exp(v) - 1) - 1) ** 2 - 1
    return _baseline_result(c, x, y, b, f"SNIP (statistics-sensitive non-linear iterative peak clipping, LLS operator), {int(iterations)} iterations")


# ------------------------------------------------------------------------------------------------ normalise
def norm_max(c):
    x, y = clean(c)
    m = float(np.max(np.abs(y))) or 1.0
    return Result([(named(c.yname, "normalised to maximum 1", "a.u."), x, y / m)], None, f"y / {m:g} (the largest absolute value)")


def norm_area(c):
    x, y = clean(c)
    a = float(_trapz(y, x)) or 1.0
    return Result([(named(c.yname, "normalised to area 1", "a.u."), x, y / a)], None, f"y / {a:g} (the area under the curve, trapezoidal rule)")


def norm_minmax(c):
    x, y = clean(c)
    lo, hi = float(np.min(y)), float(np.max(y))
    return Result([(named(c.yname, "scaled 0-1", "a.u."), x, (y - lo) / ((hi - lo) or 1.0))], None, f"(y - {lo:g}) / ({hi:g} - {lo:g})")


def norm_z(c):
    x, y = clean(c)
    m, s = float(np.mean(y)), float(np.std(y, ddof=1)) or 1.0
    return Result([(named(c.yname, "z-score", ""), x, (y - m) / s)], None, f"(y - mean {m:g}) / SD {s:g}")


def norm_at(c, at_x=0.0):
    x, y = clean(c)
    v = float(np.interp(float(at_x), x, y))
    if v == 0:
        raise AnalysisError(f"{c.name}: the value at x = {at_x:g} is 0")
    return Result([(named(c.yname, f"relative to x = {at_x:g}", ""), x, y / v)], None, f"y / y({at_x:g}) = y / {v:g} (linear interpolation)")


# ------------------------------------------------------------------------------------------------ calculus
def _sg_deriv(c, d, window):
    _scipy()
    from scipy.signal import savgol_filter
    x, y = clean(c)
    step = float(np.median(np.diff(x)))
    w = odd(window, len(y))
    if np.allclose(np.diff(x), step, rtol=1e-3):
        dy = savgol_filter(y, w, max(d + 1, 3), deriv=d, delta=step)
        how = f"Savitzky-Golay derivative (window {w}, order {max(d + 1, 3)})"
    else:
        dy = np.gradient(y, x) if d == 1 else np.gradient(np.gradient(y, x), x)
        how = "finite differences (the x steps are uneven)"
    return x, dy, how


def derivative1(c, window=7):
    x, dy, how = _sg_deriv(c, 1, window)
    u, ux = unit(c.yname), unit(c.xname)
    return Result([(named(c.yname, "first derivative", f"{u}/{ux}" if u and ux else ""), x, dy)], None, f"dy/dx: {how}")


def derivative2(c, window=11):
    x, dy, how = _sg_deriv(c, 2, window)
    u, ux = unit(c.yname), unit(c.xname)
    return Result([(named(c.yname, "second derivative", f"{u}/{ux}²" if u and ux else ""), x, dy)], None, f"d²y/dx²: {how}")


def cumulative_integral(c):
    x, y = clean(c)
    q = np.concatenate([[0.0], np.cumsum(0.5 * (y[1:] + y[:-1]) * np.diff(x))])
    u, ux = unit(c.yname), unit(c.xname)
    return Result([(named(c.yname, "cumulative integral", f"{u}·{ux}" if u and ux else ""), x, q)], None, "running trapezoidal integral from the first point")


def area_between(c, x_from=0.0, x_to=0.0, subtract_line=False):
    x, y = clean(c)
    a, b = sorted((float(x_from), float(x_to)))
    if b <= a:
        a, b = float(x[0]), float(x[-1])
    m = (x >= a) & (x <= b)
    if m.sum() < 2:
        raise AnalysisError(f"{c.name}: fewer than 2 points between {a:g} and {b:g}")
    xs, ys = x[m], y[m]
    line = ys[0] + (ys[-1] - ys[0]) * (xs - xs[0]) / ((xs[-1] - xs[0]) or 1.0) if subtract_line else 0.0
    area = float(_trapz(ys - line, xs))
    t = pd.DataFrame([{"Curve": c.name, "From": a, "To": b, "Area": area, "Straight line between the ends subtracted": bool(subtract_line), "Points": int(m.sum())}])
    return Result([], t, f"trapezoidal area between x = {a:g} and {b:g}" + (" above the straight line joining the two ends" if subtract_line else ""))


# ------------------------------------------------------------------------------------------------ peaks
def find_peaks_table(c, min_prominence_pct=5.0, min_distance_x=0.0, valleys=False):
    _scipy()
    from scipy.signal import find_peaks, peak_widths
    x, y = clean(c)
    s = -y if valleys else y
    step = float(np.median(np.diff(x))) or 1.0
    dist = max(1, int(round(float(min_distance_x) / step))) if min_distance_x else 1
    ip, pr = find_peaks(s, prominence=float(min_prominence_pct) / 100.0 * (np.ptp(s) or 1.0), distance=dist)
    rows = []
    if len(ip):
        wd, wh, l, r = peak_widths(s, ip, rel_height=0.5)
        for k, i in enumerate(ip):
            xl, xr = np.interp(l[k], np.arange(len(x)), x), np.interp(r[k], np.arange(len(x)), x)
            m = (x >= xl) & (x <= xr)
            rows.append({"Position": float(x[i]), "Height": float(y[i]), "Prominence": float(pr["prominences"][k]) * (-1 if valleys else 1),
                         "FWHM": float(xr - xl), "Area (within the FWHM)": float(_trapz(y[m], x[m])) if m.sum() > 1 else float("nan")})
    t = pd.DataFrame(rows)
    if len(t):
        t.insert(0, "Curve", c.name)
    return Result([], t, f"{'valleys' if valleys else 'peaks'} with a prominence of at least {min_prominence_pct:g} % of the curve's range"
                  + (f", at least {min_distance_x:g} apart" if min_distance_x else "") + "; FWHM at half prominence")


def _profile(kind):
    def g(x, h, c, w):
        return h * np.exp(-4 * np.log(2) * ((x - c) / w) ** 2)

    def lz(x, h, c, w):
        return h / (1 + 4 * ((x - c) / w) ** 2)
    if kind == "Gaussian":
        return g, 3
    if kind == "Lorentzian":
        return lz, 3
    return (lambda x, h, c, w, eta: eta * lz(x, h, c, w) + (1 - eta) * g(x, h, c, w)), 4


def fit_peaks(c, x_from=0.0, x_to=0.0, shape="pseudo-Voigt", peaks=0, min_prominence_pct=5.0):
    """Several peaks (Gaussian, Lorentzian or pseudo-Voigt) on a straight-line background, by least squares."""
    _scipy()
    from scipy.optimize import least_squares
    from scipy.signal import find_peaks, peak_widths
    x, y = clean(c)
    a, b = sorted((float(x_from), float(x_to)))
    if b > a:
        m = (x >= a) & (x <= b)
        x, y = x[m], y[m]
    if len(x) < 8:
        raise AnalysisError(f"{c.name}: too few points in the range to fit")
    prof, npar = _profile(shape)
    s = y - np.min(y)
    ip, pr = find_peaks(s, prominence=float(min_prominence_pct) / 100.0 * (np.ptp(s) or 1.0))
    if not len(ip):
        ip = np.array([int(np.argmax(y))])
    ip = ip[np.argsort(-s[ip])][: int(peaks)] if int(peaks) > 0 else ip
    ip = np.sort(ip)
    wd = peak_widths(s, ip, rel_height=0.5)[0] * float(np.median(np.diff(x)))
    p0, lo, hi = [float(np.min(y)), 0.0], [-np.inf, -np.inf], [np.inf, np.inf]
    for i, w in zip(ip, wd):
        w = max(float(w), 2 * float(np.median(np.diff(x))))
        p0 += [float(s[i]), float(x[i]), w] + ([0.5] if npar == 4 else [])
        lo += [0.0, float(x[0]), 1e-9] + ([0.0] if npar == 4 else [])
        hi += [np.inf, float(x[-1]), float(np.ptp(x))] + ([1.0] if npar == 4 else [])
    t0 = float(x[0])

    def model(p, xx):
        out = p[0] + p[1] * (xx - t0)
        for k in range(len(ip)):
            out = out + prof(xx, *p[2 + k * npar: 2 + (k + 1) * npar])
        return out
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        r = least_squares(lambda p: model(p, x) - y, p0, bounds=(lo, hi), max_nfev=4000)
    p = r.x
    fit = model(p, x)
    try:
        J = r.jac
        cov = np.linalg.pinv(J.T @ J) * float(np.sum(r.fun ** 2)) / max(len(y) - len(p), 1)
        se = np.sqrt(np.clip(np.diag(cov), 0, None))
    except Exception:
        se = np.full(len(p), np.nan)
    rows, comps = [], []
    for k in range(len(ip)):
        q = p[2 + k * npar: 2 + (k + 1) * npar]
        e = se[2 + k * npar: 2 + (k + 1) * npar]
        comp = prof(x, *q)
        comps.append((f"peak {k + 1} ({shape})", x, comp + p[0] + p[1] * (x - t0)))
        rows.append({"Curve": c.name, "Peak": k + 1, "Centre": q[1], "Centre SE": e[1], "Height": q[0], "Height SE": e[0], "FWHM": q[2], "FWHM SE": e[2],
                     **({"Lorentzian fraction (eta)": q[3]} if npar == 4 else {}), "Area": float(_trapz(comp, x))})
    t = pd.DataFrame(rows)
    t.attrs["fit"] = {"R²": r2(y, fit), "RMSE": float(np.sqrt(np.mean((y - fit) ** 2)))}
    t["R² of the whole fit"] = r2(y, fit)
    curves = [(named(c.yname, "data"), x, y), (named(c.yname, "fit"), x, fit), (named(c.yname, "residual"), x, y - fit)] + comps
    return Result(curves, t, f"{len(ip)} {shape} peak(s) on a straight-line background, least squares (scipy least_squares); "
                  f"R² = {r2(y, fit):.5f}; standard errors from the Jacobian" + (f"; range {a:g}-{b:g}" if b > a else ""))


# ------------------------------------------------------------------------------------------------ curve fitting
MODELS = {
    "Linear: y = a + b·x": (lambda x, a, b: a + b * x, ["a", "b"]),
    "Exponential: y = a·exp(b·x) + c": (lambda x, a, b, c: a * np.exp(b * x) + c, ["a", "b", "c"]),
    "Power law: y = a·x^b": (lambda x, a, b: a * np.power(np.clip(x, 1e-300, None), b), ["a", "b"]),
    "Logarithmic: y = a + b·ln(x)": (lambda x, a, b: a + b * np.log(np.clip(x, 1e-300, None)), ["a", "b"]),
    "Gaussian: y = y0 + A·exp(-4ln2·(x-xc)²/w²)": (lambda x, y0, A, xc, w: y0 + A * np.exp(-4 * np.log(2) * ((x - xc) / w) ** 2), ["y0", "A", "xc", "w"]),
    "Lorentzian: y = y0 + A/(1+4(x-xc)²/w²)": (lambda x, y0, A, xc, w: y0 + A / (1 + 4 * ((x - xc) / w) ** 2), ["y0", "A", "xc", "w"]),
    "Sigmoid (Boltzmann): y = A2 + (A1-A2)/(1+exp((x-x0)/dx))": (lambda x, A1, A2, x0, dx: A2 + (A1 - A2) / (1 + np.exp(np.clip((x - x0) / dx, -700, 700))), ["A1", "A2", "x0", "dx"]),
    "Avrami (JMAK): y = ymax·(1 - exp(-(k·(x-x0))^n))": (lambda x, ymax, k, n, x0: ymax * (1 - np.exp(-np.power(np.clip(k * (x - x0), 0, None), n))), ["ymax", "k", "n", "x0"]),
    "Hyperbolic (saturation): y = a·x/(b + x)": (lambda x, a, b: a * x / (b + x), ["a", "b"]),
}


def _guess(model, x, y):
    lo, hi, span = float(np.min(y)), float(np.max(y)), float(np.ptp(x)) or 1.0
    if model.startswith("Linear"):
        return list(np.polyfit(x, y, 1)[::-1])
    if model.startswith("Exponential"):                 # y = a·exp(b·x) + c is linear in a and c once b is fixed: try rates of both signs
        best = None
        x0 = float(x[0])
        for kb in (-10, -3, -1, -0.3, -0.1, 0.1, 0.3, 1, 3, 10):
            bb = kb / span
            e = np.exp(np.clip(bb * (x - x0), -700, 700))
            A = np.vstack([e, np.ones_like(x)]).T
            (aa, cc), res, *_ = np.linalg.lstsq(A, y, rcond=None)
            rss = float(np.sum((A @ [aa, cc] - y) ** 2))
            if best is None or rss < best[0]:
                best = (rss, [float(aa) * math.exp(-bb * x0) if abs(bb * x0) < 700 else float(aa), bb, float(cc)])
        return best[1]
    if model.startswith("Power"):
        ok = (x > 0) & (y > 0)
        if ok.sum() > 2:
            b, la = np.polyfit(np.log(x[ok]), np.log(y[ok]), 1)
            return [float(np.exp(la)), float(b)]
        return [1.0, 1.0]
    if model.startswith("Logarithmic"):
        ok = x > 0
        return list(np.polyfit(np.log(x[ok]), y[ok], 1)[::-1]) if ok.sum() > 2 else [lo, 1.0]
    if model.startswith(("Gaussian", "Lorentzian")):
        return [lo, hi - lo, float(x[np.argmax(y)]), span / 6]
    if model.startswith("Sigmoid"):
        return [float(y[0]), float(y[-1]), float(np.median(x)), span / 10]
    if model.startswith("Avrami"):
        return [hi, 1.0 / (span / 2), 2.0, float(x[0])]
    if model.startswith("Hyperbolic"):
        return [hi, float(np.median(x)) or 1.0]
    return None


def fit_curve(c, model="Linear: y = a + b·x", x_from=0.0, x_to=0.0):
    _scipy()
    from scipy.optimize import curve_fit
    if model.startswith("Polynomial"):
        return fit_polynomial(c)
    if model not in MODELS:
        raise AnalysisError(f"unknown model {model}")
    f, names = MODELS[model]
    x, y = clean(c)
    a, b = sorted((float(x_from), float(x_to)))
    if b > a:
        m = (x >= a) & (x <= b)
        x, y = x[m], y[m]
    if len(x) <= len(names):
        raise AnalysisError(f"{c.name}: too few points for {len(names)} parameters")
    try:
        with warnings.catch_warnings(), np.errstate(all="ignore"):     # trial parameters may overflow on the way: not an error
            warnings.simplefilter("ignore")
            p, cov = curve_fit(f, x, y, p0=_guess(model, x, y), maxfev=20000)
    except Exception as e:
        raise AnalysisError(f"{c.name}: the fit did not converge ({e})")
    se = np.sqrt(np.clip(np.diag(cov), 0, None)) if np.all(np.isfinite(cov)) else np.full(len(p), np.nan)
    with np.errstate(all="ignore"):
        fy = f(x, *p)
    n, k = len(y), len(p)
    rss = float(np.sum((y - fy) ** 2))
    R2 = r2(y, fy)
    rows = [{"Curve": c.name, "Model": model, "Parameter": nm, "Value": float(v), "Standard error": float(e)} for nm, v, e in zip(names, p, se)]
    rows += [{"Curve": c.name, "Model": model, "Parameter": q, "Value": v, "Standard error": float("nan")} for q, v in
             (("R²", R2), ("adjusted R²", 1 - (1 - R2) * (n - 1) / max(n - k - 1, 1)), ("RMSE", math.sqrt(rss / n)),
              ("AIC", n * math.log(rss / n) + 2 * k if rss > 0 else float("-inf")), ("points", n))]
    return Result([(named(c.yname, "data"), x, y), (named(c.yname, "fit"), x, fy), (named(c.yname, "residual"), x, y - fy)], pd.DataFrame(rows),
                  f"{model}, least squares (scipy curve_fit); R² = {R2:.5f}; standard errors from the covariance matrix")


def fit_polynomial(c, order=2):
    x, y = clean(c)
    o = int(order)
    if len(x) <= o + 1:
        raise AnalysisError(f"{c.name}: too few points for order {o}")
    p, cov = np.polyfit(x, y, o, cov=True)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    fy = np.polyval(p, x)
    rows = [{"Curve": c.name, "Model": f"Polynomial order {o}", "Parameter": f"a{o - i} (x^{o - i})", "Value": float(v), "Standard error": float(e)} for i, (v, e) in enumerate(zip(p, se))]
    rows.append({"Curve": c.name, "Model": f"Polynomial order {o}", "Parameter": "R²", "Value": r2(y, fy), "Standard error": float("nan")})
    return Result([(named(c.yname, "data"), x, y), (named(c.yname, f"polynomial fit {o}"), x, fy), (named(c.yname, "residual"), x, y - fy)], pd.DataFrame(rows),
                  f"polynomial of order {o}, least squares (numpy polyfit); R² = {r2(y, fy):.5f}")


# ------------------------------------------------------------------------------------------------ transform and convert
def crop(c, x_from=0.0, x_to=0.0):
    x, y = clean(c)
    a, b = sorted((float(x_from), float(x_to)))
    m = (x >= a) & (x <= b)
    if m.sum() < 2:
        raise AnalysisError(f"{c.name}: fewer than 2 points between {a:g} and {b:g}")
    return Result([(c.yname, x[m], y[m])], None, f"only x from {a:g} to {b:g}", xname=c.xname)


def resample(c, step=0.02):
    x, y = clean(c)
    st = float(step)
    if st <= 0:
        raise AnalysisError("the step must be above 0")
    xn = np.arange(x[0], x[-1] + st / 2, st)
    if len(xn) > 2_000_000:
        raise AnalysisError("that step gives more than 2 million points")
    return Result([(c.yname, xn, np.interp(xn, x, y))], None, f"linear interpolation onto an even step of {st:g}", xname=c.xname)


def scale_offset(c, factor=1.0, offset=0.0):
    x, y = clean(c)
    return Result([(named(c.yname, f"x{factor:g} {offset:+g}"), x, y * float(factor) + float(offset))], None, f"y·{factor:g} + {offset:g}")


def log10_y(c):
    x, y = clean(c)
    ok = y > 0
    return Result([(f"log10 {base(c.yname)}", x[ok], np.log10(y[ok]))], None, "log10(y); points with y <= 0 left out")


def twotheta_to_d(c, wavelength=1.540598):
    x, y = clean(c)
    d = float(wavelength) / (2 * np.sin(np.radians(x / 2)))
    o = np.argsort(d)
    return Result([(c.yname, d[o], y[o])], None, f"Bragg's law d = λ / (2 sin θ), λ = {wavelength:g} Å", xname="d-spacing (Å)")


def d_to_twotheta(c, wavelength=1.540598):
    x, y = clean(c)
    s = float(wavelength) / (2 * x)
    ok = (s > 0) & (s < 1)
    tt = 2 * np.degrees(np.arcsin(s[ok]))
    o = np.argsort(tt)
    return Result([(c.yname, tt[o], y[ok][o])], None, f"2θ = 2 asin(λ / 2d), λ = {wavelength:g} Å", xname="2θ (°)")


def twotheta_to_q(c, wavelength=1.540598):
    x, y = clean(c)
    return Result([(c.yname, 4 * np.pi * np.sin(np.radians(x / 2)) / float(wavelength), y)], None, f"Q = 4π sin θ / λ, λ = {wavelength:g} Å", xname="Q (Å⁻¹)")


def wavenumber_to_wavelength(c):
    x, y = clean(c)
    ok = x > 0
    wl = 1e4 / x[ok]
    o = np.argsort(wl)
    return Result([(c.yname, wl[o], y[ok][o])], None, "λ (µm) = 10⁴ / wavenumber (cm⁻¹)", xname="Wavelength (µm)")


def transmittance_to_absorbance(c, percent=True):
    x, y = clean(c)
    T = y / 100.0 if percent else y
    ok = T > 0
    return Result([("Absorbance (a.u.)", x[ok], -np.log10(T[ok]))], None, "A = -log10(T)" + (" with T = %T / 100" if percent else ""))


def absorbance_to_transmittance(c):
    x, y = clean(c)
    return Result([("Transmittance (%)", x, 100 * np.power(10.0, -y))], None, "%T = 100 · 10^(-A)")


def celsius_to_kelvin(c):
    x, y = clean(c)
    return Result([(c.yname, x + 273.15, y)], None, "T (K) = T (°C) + 273.15", xname="Temperature (K)")


def kelvin_to_celsius(c):
    x, y = clean(c)
    return Result([(c.yname, x - 273.15, y)], None, "T (°C) = T (K) - 273.15", xname="Temperature (°C)")


# ------------------------------------------------------------------------------------------------ several curves
def _common(curves):
    xs = [clean(c) for c in curves]
    lo = max(float(x[0]) for x, _ in xs)
    hi = min(float(x[-1]) for x, _ in xs)
    if hi <= lo:
        raise AnalysisError("the curves have no x range in common")
    x0 = xs[0][0]
    xg = x0[(x0 >= lo) & (x0 <= hi)]
    return xg, [np.interp(xg, x, y) for x, y in xs]


def difference(curves):
    if len(curves) != 2:
        raise AnalysisError("tick exactly two graphs (or a graph with two curves): A - B")
    x, (a, b) = _common(curves)
    return Result([(f"{curves[0].name} - {curves[1].name}" + (f" ({unit(curves[0].yname)})" if unit(curves[0].yname) else ""), x, a - b)], None,
                  "A - B on the x of A where both exist (B linearly interpolated)", xname=curves[0].xname)


def ratio(curves):
    if len(curves) != 2:
        raise AnalysisError("tick exactly two graphs (or a graph with two curves): A / B")
    x, (a, b) = _common(curves)
    ok = b != 0
    return Result([(f"{curves[0].name} / {curves[1].name}", x[ok], a[ok] / b[ok])], None, "A / B (B interpolated onto the x of A; points with B = 0 left out)", xname=curves[0].xname)


def add_curves(curves):
    x, ys = _common(curves)
    return Result([("Sum" + (f" ({unit(curves[0].yname)})" if unit(curves[0].yname) else ""), x, np.sum(ys, axis=0))], None,
                  f"sum of {len(curves)} curves on a common x (linear interpolation)", xname=curves[0].xname)


def mean_sd(curves):
    if len(curves) < 2:
        raise AnalysisError("tick two or more graphs (or a graph with several curves)")
    x, ys = _common(curves)
    a = np.vstack(ys)
    u = f" ({unit(curves[0].yname)})" if unit(curves[0].yname) else ""
    return Result([("Mean" + u, x, a.mean(axis=0)), ("SD" + u, x, a.std(axis=0, ddof=1)), ("Mean - SD" + u, x, a.mean(axis=0) - a.std(axis=0, ddof=1)),
                   ("Mean + SD" + u, x, a.mean(axis=0) + a.std(axis=0, ddof=1))], None,
                  f"mean and sample SD (n - 1) of {len(curves)} curves on a common x (linear interpolation)", xname=curves[0].xname)


# ------------------------------------------------------------------------------------------------ frequency
def fft_spectrum(c):
    x, y = clean(c)
    step = float(np.median(np.diff(x)))
    xn = np.arange(x[0], x[-1] + step / 2, step)
    yn = np.interp(xn, x, y)
    yn = (yn - yn.mean()) * np.hanning(len(yn))
    amp = np.abs(np.fft.rfft(yn)) * 2 / len(yn)
    f = np.fft.rfftfreq(len(yn), step)
    ux = unit(c.xname)
    return Result([("Amplitude (a.u.)", f[1:], amp[1:])], None, f"FFT amplitude spectrum (mean removed, Hann window, even step {step:g})",
                  xname=f"Frequency (1/{ux})" if ux else "Frequency")


# ------------------------------------------------------------------------------------------------ statistics
def descriptive(curves):
    _scipy()
    from scipy import stats
    rows = []
    for c in curves:
        v = np.asarray(c.y, float)
        v = v[np.isfinite(v)]
        if not len(v):
            continue
        n = len(v)
        sd = float(np.std(v, ddof=1)) if n > 1 else float("nan")
        ci = stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n) if n > 1 else float("nan")
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        rows.append({"Data": c.name, "n": n, "Mean": float(v.mean()), "SD": sd, "SE": sd / math.sqrt(n) if n > 1 else float("nan"), "95 % CI ±": ci,
                     "CV (%)": 100 * sd / v.mean() if v.mean() else float("nan"), "Median": float(med), "Q1": float(q1), "Q3": float(q3),
                     "Min": float(v.min()), "Max": float(v.max()), "Skewness": float(stats.skew(v)) if n > 2 else float("nan"),
                     "Shapiro-Wilk p (normality)": float(stats.shapiro(v).pvalue) if 3 <= n <= 5000 else float("nan")})
    return Result([], pd.DataFrame(rows), "descriptive statistics of the y values: sample SD (n - 1), 95 % CI of the mean with Student's t, Shapiro-Wilk normality test")


def correlation(curves):
    _scipy()
    from scipy import stats
    if len(curves) < 2:
        if len(curves) == 1:
            x, y = clean(curves[0])
            pr, sr = stats.pearsonr(x, y), stats.spearmanr(x, y)
            return Result([], pd.DataFrame([{"A": curves[0].xname, "B": curves[0].name, "Pearson r": pr.statistic, "Pearson p": pr.pvalue,
                                             "Spearman rho": sr.statistic, "Spearman p": sr.pvalue, "n": len(x)}]), "Pearson and Spearman correlation of x and y")
        raise AnalysisError("tick a graph")
    x, ys = _common(curves)
    rows = []
    for i in range(len(curves)):
        for j in range(i + 1, len(curves)):
            pr, sr = stats.pearsonr(ys[i], ys[j]), stats.spearmanr(ys[i], ys[j])
            rows.append({"A": curves[i].name, "B": curves[j].name, "Pearson r": pr.statistic, "Pearson p": pr.pvalue, "Spearman rho": sr.statistic, "Spearman p": sr.pvalue, "n": len(x)})
    return Result([], pd.DataFrame(rows), "Pearson and Spearman correlation between the curves on a common x")


def t_test(curves, paired=False):
    _scipy()
    from scipy import stats
    if len(curves) != 2:
        raise AnalysisError("tick exactly two graphs (or a graph with two columns of values)")
    a = np.asarray(curves[0].y, float); b = np.asarray(curves[1].y, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if paired:
        n = min(len(a), len(b)); r = stats.ttest_rel(a[:n], b[:n]); how = "paired t-test"
    else:
        r = stats.ttest_ind(a, b, equal_var=False); how = "Welch's t-test (unequal variances)"
    mw = stats.mannwhitneyu(a, b, alternative="two-sided")
    t = pd.DataFrame([{"A": curves[0].name, "B": curves[1].name, "Mean A": a.mean(), "Mean B": b.mean(), "Difference": a.mean() - b.mean(),
                       "t": float(r.statistic), "p (t-test)": float(r.pvalue), "Mann-Whitney U": float(mw.statistic), "p (Mann-Whitney)": float(mw.pvalue),
                       "n A": len(a), "n B": len(b), "Significant at 0.05 (t-test)": bool(r.pvalue < 0.05)}])
    return Result([], t, f"{how}, two-sided; Mann-Whitney U as the test without a normal distribution")


def anova(curves):
    _scipy()
    from scipy import stats
    if len(curves) < 2:
        raise AnalysisError("tick two or more graphs (each graph's values are one group)")
    g = [np.asarray(c.y, float)[np.isfinite(np.asarray(c.y, float))] for c in curves]
    f = stats.f_oneway(*g)
    kw = stats.kruskal(*g)
    rows = [{"Test": "one-way ANOVA", "Statistic": float(f.statistic), "p": float(f.pvalue)}, {"Test": "Kruskal-Wallis", "Statistic": float(kw.statistic), "p": float(kw.pvalue)}]
    try:
        tk = stats.tukey_hsd(*g)
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                rows.append({"Test": f"Tukey HSD: {curves[i].name} vs {curves[j].name}", "Statistic": float(g[i].mean() - g[j].mean()), "p": float(tk.pvalue[i, j])})
    except Exception:
        pass
    return Result([], pd.DataFrame(rows), "one-way ANOVA and Kruskal-Wallis across the groups (each chosen curve = one group); Tukey HSD for the pairs")


def linear_regression(c):
    _scipy()
    from scipy import stats
    x, y = clean(c)
    r = stats.linregress(x, y)
    n = len(x)
    tq = stats.t.ppf(0.975, n - 2)
    fy = r.intercept + r.slope * x
    s = math.sqrt(float(np.sum((y - fy) ** 2)) / max(n - 2, 1))
    sx = float(np.sum((x - x.mean()) ** 2))
    band = tq * s * np.sqrt(1 / n + (x - x.mean()) ** 2 / sx)
    t = pd.DataFrame([{"Curve": c.name, "Slope": r.slope, "Slope SE": r.stderr, "Intercept": r.intercept, "Intercept SE": r.intercept_stderr,
                       "R²": r.rvalue ** 2, "p (slope = 0)": r.pvalue, "n": n}])
    return Result([(named(c.yname, "data"), x, y), (named(c.yname, "regression line"), x, fy), (named(c.yname, "95 % confidence band, lower"), x, fy - band),
                   (named(c.yname, "95 % confidence band, upper"), x, fy + band)], t, "ordinary least-squares line with the 95 % confidence band of the mean")


# ------------------------------------------------------------------------------------------------ the menu
F, I, B, C = float, int, bool, "choice"
TOOLS = {
    # label: (group, function, [(key, label, type, default[, choices])], description, curves)
    "Moving average": ("Smoothing", moving_average, [("window", "Window (points)", I, 5)], "Centred running mean", 1),
    "Savitzky-Golay": ("Smoothing", savitzky_golay, [("window", "Window (points)", I, 11), ("order", "Polynomial order", I, 3)], "Keeps peak heights better than a running mean", 1),
    "Gaussian": ("Smoothing", gaussian_smooth, [("sigma", "Sigma (points)", F, 2.0)], "Gaussian kernel", 1),
    "Median (remove spikes)": ("Smoothing", median_filter, [("window", "Window (points)", I, 5)], "Running median", 1),
    "Straight line between the ends": ("Baseline", baseline_linear, [("points", "Points averaged at each end", I, 10)], "Line through both ends", 1),
    "Polynomial (iterative)": ("Baseline", baseline_polynomial, [("order", "Order", I, 3), ("iterations", "Iterations", I, 100)], "Modified polyfit", 1),
    "Asymmetric least squares (ALS)": ("Baseline", baseline_als, [("smoothness", "Smoothness (lambda)", F, 1e5), ("asymmetry", "Asymmetry (p)", F, 0.01), ("iterations", "Iterations", I, 10)], "Eilers & Boelens", 1),
    "SNIP (XRD, Raman)": ("Baseline", baseline_snip, [("iterations", "Iterations (about half a peak's width in points)", I, 40)], "Peak clipping", 1),
    "To maximum = 1": ("Normalise", norm_max, [], "y / max|y|", 1),
    "To area = 1": ("Normalise", norm_area, [], "y / area", 1),
    "Min-max to 0-1": ("Normalise", norm_minmax, [], "(y - min) / (max - min)", 1),
    "z-score": ("Normalise", norm_z, [], "(y - mean) / SD", 1),
    "Relative to the value at an x": ("Normalise", norm_at, [("at_x", "x", F, 0.0)], "y / y(x0)", 1),
    "First derivative": ("Calculus", derivative1, [("window", "Smoothing window (points)", I, 7)], "dy/dx", 1),
    "Second derivative": ("Calculus", derivative2, [("window", "Smoothing window (points)", I, 11)], "d²y/dx²", 1),
    "Cumulative integral": ("Calculus", cumulative_integral, [], "Running trapezoidal integral", 1),
    "Area between two x values": ("Calculus", area_between, [("x_from", "From x", F, 0.0), ("x_to", "To x (empty or equal: whole curve)", F, 0.0), ("subtract_line", "Subtract the straight line between the ends", B, False)], "Trapezoidal area", 1),
    "Find peaks": ("Peaks", find_peaks_table, [("min_prominence_pct", "Minimum prominence (% of the range)", F, 5.0), ("min_distance_x", "Minimum distance between peaks (x units)", F, 0.0)], "Position, height, FWHM, area", 1),
    "Find valleys (minima)": ("Peaks", lambda c, min_prominence_pct=5.0, min_distance_x=0.0: find_peaks_table(c, min_prominence_pct, min_distance_x, True), [("min_prominence_pct", "Minimum prominence (% of the range)", F, 5.0), ("min_distance_x", "Minimum distance (x units)", F, 0.0)], "Minima, e.g. DTG", 1),
    "Fit peaks (deconvolution)": ("Peaks", fit_peaks, [("x_from", "From x (0 and 0: whole curve)", F, 0.0), ("x_to", "To x", F, 0.0), ("shape", "Peak shape", C, "pseudo-Voigt", ["pseudo-Voigt", "Gaussian", "Lorentzian"]), ("peaks", "Number of peaks (0: as found)", I, 0), ("min_prominence_pct", "Peak finding: minimum prominence (%)", F, 5.0)], "Overlapping peaks on a linear background", 1),
    "Fit a model": ("Curve fitting", fit_curve, [("model", "Model", C, "Linear: y = a + b·x", list(MODELS)), ("x_from", "From x (0 and 0: whole curve)", F, 0.0), ("x_to", "To x", F, 0.0)], "Parameters ± SE, R², RMSE, AIC", 1),
    "Polynomial fit": ("Curve fitting", fit_polynomial, [("order", "Order", I, 2)], "y = Σ aᵢ xⁱ", 1),
    "Linear regression with confidence band": ("Curve fitting", linear_regression, [], "Slope, intercept, R², p, 95 % band", 1),
    "Crop to an x range": ("Transform and convert", crop, [("x_from", "From x", F, 0.0), ("x_to", "To x", F, 0.0)], "Keep part of the curve", 1),
    "Resample to an even step": ("Transform and convert", resample, [("step", "Step (x units)", F, 0.02)], "Linear interpolation", 1),
    "Scale and offset": ("Transform and convert", scale_offset, [("factor", "Multiply by", F, 1.0), ("offset", "Then add", F, 0.0)], "y·a + b", 1),
    "log10 of y": ("Transform and convert", log10_y, [], "log10(y)", 1),
    "XRD: 2θ to d-spacing": ("Transform and convert", twotheta_to_d, [("wavelength", "Wavelength (Å; Cu Kα1 = 1.540598)", F, 1.540598)], "Bragg's law", 1),
    "XRD: d-spacing to 2θ": ("Transform and convert", d_to_twotheta, [("wavelength", "Wavelength (Å)", F, 1.540598)], "Bragg's law", 1),
    "XRD: 2θ to Q": ("Transform and convert", twotheta_to_q, [("wavelength", "Wavelength (Å)", F, 1.540598)], "Q = 4π sinθ/λ", 1),
    "FTIR: wavenumber to wavelength": ("Transform and convert", wavenumber_to_wavelength, [], "µm = 10⁴/cm⁻¹", 1),
    "FTIR: transmittance to absorbance": ("Transform and convert", transmittance_to_absorbance, [("percent", "Transmittance in %", B, True)], "A = -log10 T", 1),
    "FTIR: absorbance to transmittance": ("Transform and convert", absorbance_to_transmittance, [], "%T = 100·10^-A", 1),
    "Temperature: °C to K": ("Transform and convert", celsius_to_kelvin, [], "+273.15", 1),
    "Temperature: K to °C": ("Transform and convert", kelvin_to_celsius, [], "-273.15", 1),
    "Difference A - B": ("Curve arithmetic", difference, [], "Two curves", 2),
    "Ratio A / B": ("Curve arithmetic", ratio, [], "Two curves", 2),
    "Sum": ("Curve arithmetic", add_curves, [], "Two or more curves", "all"),
    "Mean ± SD of curves": ("Curve arithmetic", mean_sd, [], "Replicates", "all"),
    "FFT amplitude spectrum": ("Frequency", fft_spectrum, [], "Periodic components", 1),
    "Descriptive statistics": ("Statistics", descriptive, [], "n, mean, SD, SE, CI, median, quartiles, normality", "all"),
    "Correlation (Pearson, Spearman)": ("Statistics", correlation, [], "Between curves, or x and y", "all"),
    "t-test (two groups)": ("Statistics", t_test, [("paired", "Paired", B, False)], "Welch or paired; Mann-Whitney", 2),
    "ANOVA (several groups) + Tukey": ("Statistics", anova, [], "One-way ANOVA, Kruskal-Wallis, Tukey HSD", "all"),
}


def run(label, curves, **settings):
    """Apply the tool to the curves: one Result per curve (tools for one curve) or one Result for all."""
    if label not in TOOLS:
        raise AnalysisError(f"unknown tool {label}")
    group, fn, spec, _d, how = TOOLS[label]
    kw = {}
    for s in spec:
        k, typ, dflt = s[0], s[2], s[3]
        v = settings.get(k, dflt)
        try:
            if typ is B:
                kw[k] = v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "yes", "on")
            elif typ is C:
                kw[k] = v
            elif typ is I:
                kw[k] = int(round(float(str(v).replace(",", "."))))
            else:
                kw[k] = float(str(v).replace(",", "."))
        except ValueError:
            raise AnalysisError(f"{s[1]}: '{v}' is not a number")
    if not curves:
        raise AnalysisError("tick at least one graph in Your graphs")
    if how == 1:
        out = []
        for c in curves:
            r = fn(c, **kw)
            r.xname = r.xname or c.xname
            out.append((c, r))
        return out
    if how == 2 and len(curves) != 2:
        raise AnalysisError(f"'{label}' needs exactly two curves: tick two graphs (or one graph with two curves); you chose {len(curves)}")
    r = fn(curves, **kw)
    r.xname = r.xname or curves[0].xname
    return [(None, r)]

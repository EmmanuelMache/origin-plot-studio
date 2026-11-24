"""Kinetics of thermal reactions from runs at several heating rates.

  conversion(T, signal)         alpha(T) from a mass or heat signal between its start and its end
  isoconversional(curves, ...)  E_alpha by Ozawa-Flynn-Wall (Doyle), Kissinger-Akahira-Sunose and Friedman
  kissinger(betas, Tp)          E from the shift of the peak temperature

curves: [{"beta": heating rate in K/min, "T": temperature in degC, "alpha": conversion 0..1}].
Every function returns the numbers and what was done. R = 8.314462618 J/(mol K)."""
import numpy as np

R = 8.314462618


def conversion(T, signal):
    """alpha = (s - s0) / (s_end - s0) for a signal that goes one way (mass, cumulative heat)."""
    s = np.asarray(signal, dtype=float); return (s - s[0]) / (s[-1] - s[0])


def _fit(x, y):
    """Straight line and its standard errors: (slope, intercept, se_slope, r2)."""
    x, y = np.asarray(x, float), np.asarray(y, float); n = len(x); sl, ic = np.polyfit(x, y, 1); res = y - (sl * x + ic)
    sxx = float(np.sum((x - x.mean()) ** 2)); s2 = float(np.sum(res ** 2) / max(1, n - 2)); se = float(np.sqrt(s2 / sxx)) if sxx > 0 else float("nan")
    ss = float(np.sum((y - y.mean()) ** 2)); return float(sl), float(ic), se, (1 - float(np.sum(res ** 2)) / ss) if ss > 0 else 1.0


def kissinger(betas, Tp_C):
    """ln(beta / Tp^2) against 1/Tp: slope = -E/R. Returns E in kJ/mol with its standard error."""
    b = np.asarray(betas, float); Tp = np.asarray(Tp_C, float) + 273.15
    if len(b) < 3: raise ValueError("Kissinger needs the peak temperature at three or more heating rates")
    sl, ic, se, r2 = _fit(1 / Tp, np.log(b / Tp ** 2))
    return {"Ea_kJ_mol": -sl * R / 1000, "se_kJ_mol": se * R / 1000, "r2": r2, "x": 1000 / Tp, "y": np.log(b / Tp ** 2), "slope": sl, "intercept": ic, "method": "Kissinger: ln(beta/Tp^2) vs 1/Tp, slope = -E/R"}


def isoconversional(curves, alphas=None):
    """E at each conversion level by three methods. Returns {"alpha", "T" (K, level x run), "OFW", "KAS", "Friedman": [{Ea_kJ_mol, se_kJ_mol, r2, x, y}]}.
    OFW (Doyle):  ln(beta)          vs 1/T, slope = -1.052 E/R
    KAS:          ln(beta / T^2)    vs 1/T, slope = -E/R
    Friedman:     ln(beta dalpha/dT) vs 1/T, slope = -E/R   (dalpha/dt = beta dalpha/dT)"""
    if len(curves) < 3: raise ValueError("isoconversional methods need runs at three or more heating rates")
    alphas = np.asarray(alphas if alphas is not None else np.arange(0.1, 0.91, 0.1), float); betas = np.array([float(c["beta"]) for c in curves])
    TT = np.zeros((len(alphas), len(curves))); RR = np.zeros_like(TT)
    for j, c in enumerate(curves):
        T = np.asarray(c["T"], float) + 273.15; a = np.clip(np.asarray(c["alpha"], float), 0, 1); ok = np.isfinite(T) & np.isfinite(a); T, a = T[ok], a[ok]
        o = np.argsort(T); T, a = T[o], np.maximum.accumulate(a[o]); da = np.gradient(a, T)
        keep = np.concatenate([[True], np.diff(a) > 0])                     # alpha must rise for the inversion T(alpha)
        TT[:, j] = np.interp(alphas, a[keep], T[keep]); RR[:, j] = np.interp(TT[:, j], T, da) * betas[j]
    out = {"alpha": alphas, "T": TT, "beta": betas, "OFW": [], "KAS": [], "Friedman": [], "methods": {"OFW": "ln(beta) vs 1/T, slope = -1.052 E/R (Doyle approximation)", "KAS": "ln(beta/T^2) vs 1/T, slope = -E/R", "Friedman": "ln(beta dalpha/dT) vs 1/T, slope = -E/R"}}
    for i in range(len(alphas)):
        x = 1 / TT[i]
        for name, y, k in (("OFW", np.log(betas), 1.052), ("KAS", np.log(betas / TT[i] ** 2), 1.0), ("Friedman", np.log(np.clip(RR[i], 1e-300, None)), 1.0)):
            sl, ic, se, r2 = _fit(x, y); out[name].append({"Ea_kJ_mol": -sl * R / k / 1000, "se_kJ_mol": se * R / k / 1000, "r2": r2, "x": 1000 * x, "y": y, "slope": sl, "intercept": ic})
    return out


def simulate_first_order(E_kJ, A_per_min, beta, T0=300.0, T1=1300.0, n=4000):
    """alpha(T) of a first-order reaction at heating rate beta (K/min), for tests and illustrative previews.
    Returns (T in degC, alpha, dalpha/dT)."""
    T = np.linspace(T0, T1, n); k = A_per_min / beta * np.exp(-E_kJ * 1000 / (R * T))
    integ = np.concatenate([[0.0], np.cumsum(0.5 * (k[1:] + k[:-1]) * np.diff(T))]); a = 1 - np.exp(-integ)
    return T - 273.15, a, k * (1 - a)

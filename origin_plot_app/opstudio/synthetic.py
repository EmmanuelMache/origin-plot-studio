"""Synthetic demo data for template previews. ILLUSTRATIVE ONLY - never shown as user results."""
import numpy as np
_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")      # numpy 2 / numpy 1

RNG = np.random.default_rng(7)
SAMPLES = ["Sample A", "Sample B", "Sample C", "Sample D", "Sample E", "Sample F"]


def peaks(x, centers, heights, width=0.08, shape="pv"):
    y = np.zeros_like(x, dtype=float)
    widths = np.broadcast_to(np.asarray(width, float), (len(centers),))
    for c, h, width in zip(centers, heights, widths):
        g = np.exp(-4 * np.log(2) * ((x - c) / width) ** 2)
        l = 1 / (1 + 4 * ((x - c) / width) ** 2)
        y += h * (0.6 * g + 0.4 * l)
    return y


XRD_PHASES = {  # illustrative letter keys + approximate positions for demo only
    "A": [29.4, 32.2, 32.6, 34.3, 41.3, 51.7, 56.6], "B": [31.0, 32.1, 32.7, 39.4, 41.2],
    "C": [33.2, 47.6, 59.4], "F": [12.2, 33.9, 44.2], "R": [27.4, 36.1, 41.2, 54.3], "P": [42.9, 62.3],
}


def xrd_pattern(seed=0, x=None, scale=1.0, noise=12):
    r = np.random.default_rng(seed)
    x = np.linspace(10, 60, 2500) if x is None else x
    y = 120 + 30 * np.exp(-(x - 10) / 15)
    for i, (ph, pos) in enumerate(XRD_PHASES.items()):
        h = r.uniform(150, 900, len(pos)) * scale * (1.6 if ph in "AR" else 0.8)
        y += peaks(x, pos, h, width=0.12)
    y += r.normal(0, noise, len(x))
    return x, y


def tga_curve(T, steps, seed=0, start=100.0):
    """steps: list of (T_mid, width, loss_%)"""
    m = np.full_like(T, start, dtype=float)
    for Tm, w, loss in steps:
        m -= loss / (1 + np.exp(-(T - Tm) / w))
    m -= 1.5 * (1 - np.exp(-(T - T[0]) / 80))  # free / adsorbed water drift
    return m + np.random.default_rng(seed).normal(0, 0.01, len(T))


def heat_flow(t, amp=2.0, t_peak=10, w=5, dormant=2, seed=0):
    r = np.random.default_rng(seed)
    initial = 3.5 * np.exp(-t / 0.25)
    main = amp * np.exp(-0.5 * ((np.log(np.maximum(t, 1e-3)) - np.log(t_peak)) / (w / t_peak * 2)) ** 2)
    shoulder = 0.35 * amp * np.exp(-0.5 * ((t - 1.8 * t_peak) / (0.6 * t_peak)) ** 2)
    tail = 0.08 * amp * np.exp(-t / 300)
    return initial + main + shoulder + tail + r.normal(0, 0.004, len(t))


def lognormal_psd(d, d50, sigma):
    q = np.exp(-0.5 * ((np.log(d) - np.log(d50)) / sigma) ** 2)
    q = q / _trapz(q, np.log10(d)) * 100
    cum = np.cumsum(q * np.gradient(np.log10(d)))
    return q, cum / cum[-1] * 100

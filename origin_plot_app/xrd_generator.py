"""XRD scan generator inside Origin Plot Studio (XRD tools > Generate XRD scans).

Same engine as the stand-alone XRD Scan Generator (xrd_scan_generator/engine.py in the repository).

The template analysis, peak synthesis, noise model, phase mixtures and writers are those of xrd_generator_v2.py
(the version with the sample-name, count-range, weak-peak and relative-strength fixes). This module has no user
interface; it raises XrdError with a readable message instead of exiting, and generate() reports progress and can
be cancelled between scans. With the same settings and seed it writes the same files as the command-line script.
"""
import datetime as dt
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import warnings

import numpy as np

try:                                   # SciPy is needed only for the template analysis; the rest of the app runs without it
    from scipy.signal import find_peaks, peak_widths, savgol_coeffs, savgol_filter
    SCIPY_MISSING = ""
except Exception as _e:                # noqa: BLE001
    SCIPY_MISSING = f"{type(_e).__name__}: {_e}"


class XrdError(Exception):
    """A problem the user can fix: a wrong file, an invalid setting, a folder that cannot be written."""


KA1 = 1.5405980   # Cu Ka1, Angstrom
KA2 = 1.5444260   # Cu Ka2, Angstrom
KA21_RATIO = 0.5  # Ka2/Ka1 intensity ratio
class _Stockholm(dt.tzinfo):
    """Europe/Stockholm without a time-zone database (Windows without the tzdata package): CET, and CEST from the
    last Sunday of March 01:00 UTC to the last Sunday of October 01:00 UTC (EU rule since 1996)."""
    @staticmethod
    def _last_sunday(year, month):
        d = dt.datetime(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.datetime(year, 12, 31)
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)
    def utcoffset(self, d):
        return dt.timedelta(hours=1) + self.dst(d)
    def dst(self, d):
        if d is None:
            return dt.timedelta(0)
        naive = d.replace(tzinfo=None)
        start = self._last_sunday(d.year, 3).replace(hour=2)        # 01:00 UTC = 02:00 local standard time
        end = self._last_sunday(d.year, 10).replace(hour=3)          # 01:00 UTC = 03:00 local summer time
        return dt.timedelta(hours=1) if start <= naive < end else dt.timedelta(0)
    def tzname(self, d):
        return "CEST" if self.dst(d) else "CET"


try:
    TZ = ZoneInfo("Europe/Stockholm")
except Exception:                      # noqa: BLE001
    TZ = _Stockholm()
NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def odd(n, upper):
    n = int(min(n, upper))
    return n if n % 2 else n - 1


def pseudo_voigt(dx, fwhm, eta):
    """Unit-height pseudo-Voigt centred at 0."""
    g = np.exp(-4.0 * np.log(2.0) * (dx / fwhm) ** 2)
    l = 1.0 / (1.0 + 4.0 * (dx / fwhm) ** 2)
    return eta * l + (1.0 - eta) * g


def ka2_shift(two_theta_deg):
    """2theta offset of the Ka2 line for a Ka1 reflection at two_theta_deg."""
    th = np.deg2rad(np.asarray(two_theta_deg) / 2.0)
    s2 = np.clip((KA2 / KA1) * np.sin(th), -1.0, 1.0)
    return 2.0 * np.rad2deg(np.arcsin(s2)) - two_theta_deg


def parse_range(s, cast):
    parts = s.split("-")
    return cast(parts[0]), cast(parts[-1])


# ----------------------------------------------------------------------------
# template loading
# ----------------------------------------------------------------------------
def load_xrdml(path):
    """Read a PANalytical .xrdml scan. Returns (text, 2theta, counts, sample, original <name>).
    Raises XrdError with a readable message for files that are not supported."""
    p = Path(path)
    if p.suffix.lower() != ".xrdml":
        raise XrdError(f"{p.name} is not an .xrdml file. Choose a PANalytical .xrdml scan.")
    try:
        with open(p, encoding="utf-8") as fh:
            txt = fh.read()
    except UnicodeDecodeError:
        raise XrdError(f"{p.name} is not a text XML file (it may be a binary or damaged file).")
    except OSError as e:
        raise XrdError(f"{p.name} could not be opened: {e.strerror or e}")
    mpos = re.search(r'<positions axis="2Theta"[^>]*>\s*<startPosition>([^<]+)</startPosition>'
                     r'\s*<endPosition>([^<]+)</endPosition>', txt)
    mint = re.search(r'<(intensities|counts)\b[^>]*>([^<]*)</\1>', txt)
    if not mpos or not mint:
        raise XrdError(f"{p.name} does not look like a supported .xrdml scan: it needs a 2Theta start/end "
                       "position and an <intensities> or <counts> data block.")
    try:
        y = np.array([float(v) for v in mint.group(2).split()])
        x0, x1 = float(mpos.group(1)), float(mpos.group(2))
    except ValueError:
        raise XrdError(f"{p.name}: the scan data contain values that are not numbers.")
    if len(y) < 50 or not (x1 > x0) or not np.all(np.isfinite(y)):
        raise XrdError(f"{p.name}: the scan is too short or its angular range is invalid ({len(y)} points, {x0:g}-{x1:g} deg).")
    x = np.linspace(x0, x1, len(y))
    blk = re.search(r'<sample\b[^>]*>(.*?)</sample>', txt, re.S)
    inner = blk.group(1) if blk else ""
    mid = re.search(r'<id>([^<]*)</id>', inner)
    mname = re.search(r'<name>([^<]*)</name>', inner)
    sid = mid.group(1).strip() if mid else ""
    sname = mname.group(1).strip() if mname else ""
    # the name the files are called after: <id>, then <name>, then the file name. Never a made-up name.
    sample = sid or sname or p.stem
    return txt, x, y, sample, sname


def safe_stem(name):
    """The sample name as a file name: characters Windows does not allow become '_'."""
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("._") or "scan"


# ----------------------------------------------------------------------------
# template analysis (noise aware)
# ----------------------------------------------------------------------------
def snip(y, half_window):
    v = np.log(np.log(np.sqrt(np.clip(y, 0, None) + 1) + 1) + 1)
    n = len(v)
    for p in range(1, half_window + 1):
        a = v.copy()
        a[p:n - p] = np.minimum(v[p:n - p], 0.5 * (v[:n - 2 * p] + v[2 * p:]))
        v = a
    return (np.exp(np.exp(v) - 1) - 1) ** 2 - 1


def noise_ratio(y):
    """Point-to-point noise of the raw counts relative to Poisson counting noise (1.0 = pure counting noise).
    Robust (median absolute deviation) and independent of any background estimate."""
    y = np.clip(np.asarray(y, float), 0, None)
    z = np.diff(y) / np.sqrt(np.clip(y[1:] + y[:-1], 1, None))
    return float(1.4826 * np.median(np.abs(z - np.median(z))))


PEAK_HEIGHT_SIGMA = 4.5      # a peak must rise this many sigma (of the smoothed curve) above the background ...
PEAK_PROMINENCE_SIGMA = 3.0  # ... and stand this many sigma above its neighbouring valleys


def _local_fit(x, xb, yb, half=2.0, minpts=60, near=0.3):
    """Background through the background points (xb, yb): a local quadratic in log counts with tricube weights, evaluated where
    background points are close by and bridged in log counts across runs of peaks. Nothing is padded at the ends: there the fit is
    one-sided (a straight line in log counts), so the background keeps its own shape up to the first and last point."""
    g = np.unique(np.r_[np.arange(x[0], x[-1], 0.05), xb[0], xb[-1]])
    j = np.searchsorted(xb, g)
    dn = np.minimum(np.abs(xb[np.clip(j, 0, len(xb) - 1)] - g), np.abs(xb[np.clip(j - 1, 0, len(xb) - 1)] - g))
    g = np.unique(np.r_[x[0], g[dn <= near], x[-1]])
    ly = np.log(np.clip(yb, 0.5, None))
    out = np.empty(len(g))
    for k, c in enumerate(g):
        d = np.abs(xb - c)
        h = max(half, np.sort(d)[min(minpts, len(d)) - 1] * 1.0001)
        m = d < h
        u = xb[m] - c
        w = np.sqrt((1 - (d[m] / h) ** 3) ** 3)
        inside = u.min() < 0 < u.max()
        deg = 2 if inside else 1
        A = np.vstack([u ** q for q in range(deg + 1)]).T * w[:, None]
        v = np.linalg.lstsq(A, ly[m] * w, rcond=None)[0][0]
        lo, hi = ly[m].min(), ly[m].max()
        out[k] = min(max(v, lo), hi) if inside else min(max(v, lo - 0.7), hi + 0.7)
    return np.exp(np.interp(x, g, out))


def template_background(x, y):
    """The background of a scan, as it is - also at the first and last degrees (a falling low-angle background is not bent flat).
    Background points are chosen on a moving average (it cannot ring below the counts beside sharp peaks), within 2 sigma of the
    counting noise; the first and last 0.15 deg are always background (no peak sits right at the edge of a scan)."""
    from scipy.ndimage import uniform_filter1d
    x = np.asarray(x, float); y = np.asarray(y, float)
    n, step = len(y), x[1] - x[0]
    bg = savgol_filter(snip(savgol_filter(y, odd(31, n), 2), max(1, int(1.0 / step))), odd(501, n), 2, mode="interp")
    bg = np.clip(bg, 0.5, None)
    k = max(5, int(round(0.25 / step)) | 1)
    yb = uniform_filter1d(y, k, mode="nearest")
    kb = noise_ratio(y) / np.sqrt(k)
    edge = (x - x[0] < 0.15) | (x[-1] - x < 0.15)
    for _ in range(8):
        z = (yb - bg) / np.sqrt(np.clip(bg, 1, None))
        is_bg = z < 2.0 * kb
        if is_bg.sum() < 0.15 * n:
            is_bg = z <= np.quantile(z, 0.3)
        is_bg |= edge
        bg = _local_fit(x, x[is_bg], yb[is_bg])
    return np.clip(bg, 0.5, None)


def analyse_template(x, y, prominence=1.0):
    """Return background, local noise sigma and peak table (pos, rel_height, fwhm_ka1).

    The noise is measured from the point-to-point differences of the raw counts (it does not depend on the
    background estimate, so a background that is off in a peak-rich region can no longer inflate it and hide weak
    peaks). sigma is the noise of the smoothed curve the peaks are found on. A peak counts when it rises
    PEAK_HEIGHT_SIGMA sigma above the background and PEAK_PROMINENCE_SIGMA sigma above its neighbouring valleys
    (checked on invented scans with known peaks: no false and no missed peaks). `prominence` (in units of the
    median sigma) is an extra lower limit for the prominence."""
    n, step = len(y), x[1] - x[0]
    w25 = odd(25, n)
    ys = savgol_filter(y, w25, 4)
    gain = float(np.sqrt(np.sum(savgol_coeffs(w25, 4) ** 2)))     # noise of the smoothed curve / noise of the raw counts
    ksm = noise_ratio(y) * gain
    bg = template_background(x, y)
    net = ys - bg
    sigma = ksm * np.sqrt(bg)

    ip, _ = find_peaks(net, height=PEAK_HEIGHT_SIGMA * sigma,
                       prominence=np.maximum(prominence * np.median(sigma), PEAK_PROMINENCE_SIGMA * sigma),
                       distance=max(1, int(0.2 / step)))
    if len(ip) == 0:
        raise XrdError("No peaks above the noise level were found in the template scan.")

    net15 = savgol_filter(y, odd(15, n), 4) - bg           # sharper copy for measuring
    rows = []
    for i in ip:
        lo, hi = max(0, i - 4), min(n, i + 5)
        j = lo + int(np.argmax(net15[lo:hi]))
        h = net15[j]
        if h <= 0:
            continue
        w = peak_widths(net15, [j], rel_height=0.5)[0][0] * step
        w = float(np.clip(w, 2.5 * step, 1.0))
        d2 = float(ka2_shift(x[j]))
        h1 = h / (1.0 + KA21_RATIO * float(pseudo_voigt(d2, w, 0.45)))   # remove Ka2 share
        w1 = max(w - 0.30 * d2, 2.5 * step)                               # remove Ka2 broadening
        rows.append((x[j], h1, w1))
    peaks = np.array(rows)
    return bg, sigma, peaks


def count_candidates(x, y, bg, sigma, prominence):
    """How many maxima pass the 3 sigma test at a given prominence (for the printed check)."""
    n, step = len(y), x[1] - x[0]
    net = savgol_filter(y, odd(25, n), 4) - bg
    ip, _ = find_peaks(net, height=PEAK_HEIGHT_SIGMA * sigma,
                       prominence=np.maximum(prominence * np.median(sigma), PEAK_PROMINENCE_SIGMA * sigma),
                       distance=max(1, int(0.2 / step)))
    return len(ip)


def bands(apex_counts):
    """Number of peaks whose top lies below 5000, at 5000-8000, and above 8000 counts."""
    a = np.asarray(apex_counts, float)
    return int((a < 5000).sum()), int(((a >= 5000) & (a <= 8000)).sum()), int((a > 8000).sum())


def make_fwhm_model(peaks, step):
    """Smooth FWHM(2theta) from the template peaks, used for reference phases."""
    strong = peaks[peaks[:, 1] >= 0.1 * peaks[:, 1].max()]
    if len(strong) < 4:
        strong = peaks
    deg = 2 if len(strong) >= 6 else 1
    c = np.polyfit(strong[:, 0], strong[:, 2], deg)
    return lambda tt: np.clip(np.polyval(c, tt), 2.5 * step, 1.0)


def load_phase(path):
    rows = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
    except OSError as e:
        raise XrdError(f"{Path(path).name} could not be opened: {e.strerror or e}")
    for line in lines:
        nums = NUM.findall(line)
        if len(nums) >= 2:
            rows.append((float(nums[0]), float(nums[1])))
    if not rows:
        raise XrdError(f"No (2theta, intensity) lines were found in {Path(path).name}.")
    a = np.array(rows)
    a[:, 1] = 100.0 * a[:, 1] / a[:, 1].max()
    return a


# ----------------------------------------------------------------------------
# synthesis
# ----------------------------------------------------------------------------
def synthesize_peaks(x_new, phases, h_unit, fwhm_model, rng, intensity_jitter=0.0,
                     phase_jitter=0.25, dropout=0.0):
    """Noise-free peak pattern. phases: list of (name, table[pos, rel, fwhm|nan], weight).

    intensity_jitter: sigma of an independent log-normal factor per peak (0 = the relative
                      strengths of the peaks stay exactly as in the template).
    phase_jitter:     sigma of one log-normal factor per phase (changes all its peaks alike).
    dropout:          fraction of weak lines (below 8 % relative intensity) left out; 0 = none."""
    step = x_new[1] - x_new[0]
    pat = np.zeros_like(x_new)
    zero_shift = rng.uniform(-0.012, 0.012)       # sample displacement
    width_scale = np.exp(rng.normal(0, 0.12))     # crystallite size / strain
    used = []
    centres = []                                   # (phase, shifted position, template position) of every line drawn
    for name, tab, weight in phases:
        wj = weight * (np.exp(rng.normal(0, phase_jitter)) if phase_jitter > 0 else 1.0)   # phase content variation
        lattice = rng.normal(0, 0.012) if name != "template" else 0.0
        used.append((name, wj))
        for pos, rel, fwhm in tab:
            if dropout > 0 and rel < 8 and rng.random() < dropout:
                continue                                      # weak line dropout (off unless asked for)
            p = pos + zero_shift + lattice + rng.normal(0, 0.004)
            h = h_unit * rel / 100.0 * wj
            if intensity_jitter > 0:
                h *= np.exp(rng.normal(0, intensity_jitter))
            f0 = fwhm if np.isfinite(fwhm) else float(fwhm_model(pos))
            f = max(f0 * width_scale * np.exp(rng.normal(0, 0.08)), step + 1e-4)
            eta = rng.uniform(0.3, 0.6)
            d2 = float(ka2_shift(p))
            s = (x_new >= p - 8 * f) & (x_new <= p + d2 + 8 * f)
            if not s.any():
                continue
            centres.append((name, p, pos))
            pat[s] += h * pseudo_voigt(x_new[s] - p, f, eta)
            pat[s] += h * KA21_RATIO * pseudo_voigt(x_new[s] - p - d2, f * 1.02, eta)
    return pat, dict(zero_shift=zero_shift, width_scale=width_scale, phases=used, centres=centres)


BG_MODES = {"keep": "Keep the template's background (its shape and level; only the counting noise is new)",
            "small": "Small variations (level ±15 %, slight tilt; no added hump)",
            "vary": "Vary it (level, tilt and a random amorphous hump, as before)"}


def synthesize_background(x_new, x_tpl, bg_tpl, rng, mode="vary"):
    """The background of a generated scan. 'keep': the template's own background (shape and level) on the new 2θ points;
    'small': its level ±15 % and a slight tilt; 'vary': also a random amorphous hump (the generator's original behaviour)."""
    bg = np.interp(x_new, x_tpl, bg_tpl)
    if mode == "keep":
        return np.clip(bg, 0.5, None), dict(bg_scale=1.0, hump=0.0)
    scale = rng.uniform(0.85, 1.15)
    bg = bg * scale
    tilt = rng.uniform(-0.15, 0.15) * (x_new - x_new.mean()) / np.ptp(x_new)
    bg = bg * (1.0 + tilt)
    hump = 0.0
    if mode == "vary" and rng.random() < 0.7:     # amorphous / glass hump
        c, w = rng.uniform(15, 45), rng.uniform(3, 10)
        hump = rng.uniform(0.05, 0.25) * bg.max()
        bg = bg + hump * np.exp(-0.5 * ((x_new - c) / w) ** 2)
    return np.clip(bg, 0.5, None), dict(bg_scale=scale, hump=hump)


def make_scan(x_tpl, bg_tpl, phases, h_unit, fwhm_model, lo, hi, n_points,
              c_lo, c_hi, rng, intensity_jitter=0.0, phase_jitter=0.25, dropout=0.0, bg_mode="vary"):
    """One generated scan. The maximum of the noisy counts lies in [c_lo, c_hi], or an error is raised."""
    x_new = lo + (hi - lo) * np.arange(n_points) / (n_points - 1)
    bg, bmeta = synthesize_background(x_new, x_tpl, bg_tpl, rng, bg_mode)
    pat, pmeta = synthesize_peaks(x_new, phases, h_unit, fwhm_model, rng,
                                  intensity_jitter, phase_jitter, dropout)
    shape = bg + pat
    shape = shape / shape.max()                    # the whole pattern is scaled as one: peaks keep their ratios
    target = float(rng.uniform(c_lo, c_hi))        # the maximum this scan aims at
    t = target
    for attempt in range(1, 101):
        counts = rng.poisson(shape * t)
        achieved = int(counts.max())
        if c_lo <= achieved <= c_hi:
            apex = [float(np.interp(p, x_new, shape * t)) for name, p, _ in pmeta["centres"] if name == "template"]
            return x_new, counts, {**bmeta, **pmeta, "target": target, "attempts": attempt,
                                   "scale": t, "apex_counts": apex}
        desired = min(max(target, c_lo + 0.02 * (c_hi - c_lo)), c_hi - 0.02 * (c_hi - c_lo))
        t *= desired / max(achieved, 1)                    # noise moved the maximum: correct by the ratio and draw again
    raise RuntimeError(f"no scan with a maximum inside {c_lo:g}-{c_hi:g} counts after 100 attempts "
                       f"(last maximum {achieved}); the scan was not written")


# ----------------------------------------------------------------------------
# writers
# ----------------------------------------------------------------------------
def write_xrdml(txt, x_new, counts, sample_id, out_path, rng):
    """Write one scan. <id> gets the numbered stem; the original <name> of the template is left as it is."""
    start = dt.datetime(2026, 1, 1, tzinfo=TZ) + dt.timedelta(
        seconds=int(rng.integers(0, 330 * 24 * 3600)))
    end = start + dt.timedelta(seconds=int(rng.integers(3600, 9000)))
    out = txt
    def set_id(m):
        inner = m.group(2)
        if re.search(r'<id>[^<]*</id>', inner):
            inner = re.sub(r'(<id>)[^<]*(</id>)', lambda k: k.group(1) + sample_id + k.group(2), inner, count=1)
        else:
            inner = "\n\t\t<id>" + sample_id + "</id>" + inner
        return m.group(1) + inner + m.group(3)
    out = re.sub(r'(<sample\b[^>]*>)(.*?)(</sample>)', set_id, out, count=1, flags=re.S)
    if "SIMULATED SYNTHETIC TEST DATA" not in out:
        out = re.sub(r'(<comment>\s*)', lambda m: m.group(1) + "<entry>SIMULATED SYNTHETIC TEST DATA - generated from a real template scan; "
                     "NOT an experimental measurement.</entry>" + m.group(1)[len("<comment>"):], out, count=1)
    out = re.sub(r'<startTimeStamp>[^<]*</startTimeStamp>',
                 f'<startTimeStamp>{start.isoformat(timespec="seconds")}</startTimeStamp>', out, count=1)
    out = re.sub(r'<endTimeStamp>[^<]*</endTimeStamp>',
                 f'<endTimeStamp>{end.isoformat(timespec="seconds")}</endTimeStamp>', out, count=1)
    for axis, vals in (("2Theta", x_new), ("Omega", x_new / 2.0)):   # theta/theta gonio
        pat = re.compile(r'(<positions axis="%s"[^>]*>\s*<startPosition>)[^<]+'
                         r'(</startPosition>\s*<endPosition>)[^<]+(</endPosition>)' % axis)
        out = pat.sub(lambda m: m.group(1) + f"{vals[0]:.8f}" + m.group(2)
                      + f"{vals[-1]:.8f}" + m.group(3), out, count=1)
    out = re.sub(r'(<(intensities|counts)\b[^>]*>)[^<]*(</\2>)',
                 lambda m: m.group(1) + " ".join(map(str, counts)) + m.group(3), out, count=1)
    with open(out_path, "x", encoding="utf-8", newline="\r\n") as f:      # "x": never over an existing file
        f.write(out)


def write_csv(x_new, counts, out_path):
    if Path(out_path).exists():
        raise FileExistsError(out_path)
    np.savetxt(out_path, np.column_stack([x_new, counts]), delimiter=",",
               fmt=["%.5f", "%d"], header="2theta_deg,intensity_counts", comments="")



# ----------------------------------------------------------------------------
# intensity check and correction of a measured scan (no SciPy needed)
# ----------------------------------------------------------------------------
USUAL_COUNTS = (8000.0, 10000.0)
CORRECT_TARGET = 9000.0


def intensity_check(path, usual=USUAL_COUNTS):
    """('low' | 'high' | 'ok', highest count) of an .xrdml scan. Raises XrdError for files that cannot be read."""
    _txt, _x, y, _s, _n = load_xrdml(path)
    m = float(np.max(y))
    return ("low" if m < usual[0] else "high" if m > usual[1] else "ok"), m


def peak_model(x, params):
    """Sum of K-alpha1/K-alpha2 pseudo-Voigt pairs (the same peak shape the generator draws).
    params rows: position (K-alpha1), height (K-alpha1), FWHM, eta."""
    out = np.zeros_like(np.asarray(x, float))
    for p, h, f, eta in params:
        d2 = float(ka2_shift(p))
        lo, hi = np.searchsorted(x, [p - 12 * f, p + d2 + 12 * f])
        xs = x[lo:hi]
        out[lo:hi] += h * (pseudo_voigt(xs - p, f, eta) + KA21_RATIO * pseudo_voigt(xs - p - d2, f * 1.02, eta))
    return out


def fit_peaks(x, y, bg, peaks, max_nfev=80):
    """Least-squares fit (Poisson weights) of position, height, width and shape (eta) of every peak on the
    background. Peaks whose +/- 6 FWHM windows overlap are fitted together; separate groups are independent."""
    from scipy.optimize import least_squares
    if len(peaks) == 0:
        return np.zeros((0, 4))
    pk = peaks[np.argsort(peaks[:, 0])]
    spans = [(p - 6 * f, p + float(ka2_shift(p)) + 6 * f) for p, _h, f in pk]
    groups, cur = [], [0]
    for i in range(1, len(pk)):
        if spans[i][0] <= max(spans[j][1] for j in cur):
            cur.append(i)
        else:
            groups.append(cur)
            cur = [i]
    groups.append(cur)
    out = []
    for g in groups:
        a = np.searchsorted(x, min(spans[i][0] for i in g) - 6 * pk[g[0], 2])
        b = np.searchsorted(x, max(spans[i][1] for i in g) + 6 * pk[g[-1], 2])
        xs, ys, bs = x[a:b], y[a:b], bg[a:b]
        w = 1.0 / np.sqrt(np.clip(ys, 1, None))
        m = len(g)
        p0 = np.column_stack([pk[g, 0], np.maximum(pk[g, 1], 1.0), pk[g, 2], np.full(m, 0.45)])
        lo = np.column_stack([p0[:, 0] - 0.5 * p0[:, 2], np.zeros(m), 0.4 * p0[:, 2], np.zeros(m)])
        hi = np.column_stack([p0[:, 0] + 0.5 * p0[:, 2], 3.0 * p0[:, 1] + 10, 2.5 * p0[:, 2], np.ones(m)])
        try:
            r = least_squares(lambda v: (bs + peak_model(xs, v.reshape(-1, 4)) - ys) * w, p0.ravel(),
                              bounds=(lo.ravel(), hi.ravel()), x_scale="jac", max_nfev=max_nfev)
            out.append(r.x.reshape(-1, 4))
        except Exception:      # noqa: BLE001
            out.append(p0)
    return np.vstack(out)


def expected_counts(x, y, prominence=1.0):
    """Estimate of the noise-free counts behind a measured scan (what the detector would average to).
    Background from the template analysis; every peak fitted as a K-alpha1/K-alpha2 pseudo-Voigt pair; what the fit
    does not catch (peak asymmetry, very small peaks) is added back after smoothing with a Gaussian kernel, which
    cannot ring (no dips beside peaks, no false bumps). Returns (expected counts, number of peaks, residual
    smoothing in points)."""
    need_scipy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bg, _sigma, peaks = analyse_template(x, y, prominence)
        prm = fit_peaks(x, np.asarray(y, float), bg, peaks)
    from scipy.ndimage import gaussian_filter1d
    step = float(x[1] - x[0])
    model = bg + peak_model(x, prm)
    fw = float(np.median(prm[:, 2])) if len(prm) else 0.1
    sm = max(1.0, 0.3 * fw / step)
    lam = model + gaussian_filter1d(np.asarray(y, float) - model, sm, mode="nearest")
    return np.clip(lam, 0.05, None), int(len(prm)), round(float(sm), 2)


def correct_intensity(path, target=CORRECT_TARGET, out_dir=None, usual=USUAL_COUNTS, draw=0, suffix="_corrected"):
    """Bring the highest peak of a measured scan into the usual range the way a different counting time would.

    Too low (a longer measurement is needed): a measurement k times longer is exactly this measurement plus an
      independent measurement (k-1) times as long. So your measured counts are kept, and the counts of the extra
      counting time are drawn as Poisson counts from the estimated noise-free scan (expected_counts). In the background
      the noise is then that of a real k-times-longer scan; on the peaks the scatter is about 1.4x that of a real one
      (the information a longer count collects is not in a short scan), against about 1.75x for plain multiplication.
    Too high (a shorter measurement): binomial thinning: every recorded count is kept with probability 1/k. This is
      exactly what a k-times-shorter measurement gives; nothing has to be estimated.
    The random numbers are seeded from the file's SHA-256, so the same file always gives the same result. The maximum
    lies inside `usual` (redrawn up to 100 times). The scan is saved as <stem>_corrected.xrdml (never over a file) with
    <stem>_corrected_provenance.json describing what was done; the original file is never changed.
    draw > 0 gives another, independent random draw of the same kind (for several candidates to choose from); suffix
    names the file (<stem><suffix>.xrdml). A scan already inside `usual` is counted longer when `usual` lies above it.
    Returns (new path, factor k, method)."""
    import hashlib, json
    p = Path(path)
    raw = p.read_bytes()
    crlf = b"\r\n" in raw
    sha = hashlib.sha256(raw).hexdigest()
    txt, x, y, sample, sname = load_xrdml(p)
    y = np.clip(np.asarray(y, float), 0, None)
    m = float(np.max(y))
    if m <= 0:
        raise XrdError(f"{p.name}: the scan has no counts above zero, so it cannot be corrected.")
    rng = np.random.default_rng([int(sha[:16], 16), int(draw)]) if draw else np.random.default_rng(int(sha[:16], 16))
    lo_u, hi_u = usual
    if not (lo_u <= target <= hi_u):
        target = 0.5 * (lo_u + hi_u)
    info = {}
    if m > hi_u:                                                     # shorter measurement: exact binomial thinning
        keep = float(target) / m
        method = "binomial thinning (a shorter measurement)"
        yi = np.rint(y).astype(np.int64)
        for attempt in range(1, 101):
            counts = rng.binomial(yi, keep)
            if lo_u <= counts.max() <= hi_u:
                break
        else:
            raise XrdError(f"{p.name}: no corrected scan with a maximum inside {lo_u:,.0f}-{hi_u:,.0f} counts was found.")
        factor = keep
    else:                                                            # longer measurement: your counts + the extra counting time
        key_ = (sha, len(y))
        if key_ not in _EXPECTED_CACHE:                              # the fit is the slow part: done once per file
            _EXPECTED_CACHE.clear(); _EXPECTED_CACHE[key_] = expected_counts(x, y)
        lam, npk, win = _EXPECTED_CACHE[key_]
        method = ("your measured counts plus new Poisson counts for the extra counting time "
                  "(a measurement k times longer = this measurement + an independent one (k-1) times as long)")
        info = {"peaks_fitted": npk, "residual_smoothing_sigma_points": win,
                "shape_estimate": "background of the template analysis + every peak fitted as a K-alpha1/K-alpha2 pseudo-Voigt pair + Gaussian-smoothed residual",
                "measured_counts_kept": True}
        t = float(target) / float(lam.max())
        if t <= 1.0:
            t = 1.0 + 1e-9
        yi = np.rint(y).astype(np.int64)
        for attempt in range(1, 101):
            counts = yi + rng.poisson(lam * (t - 1.0))
            if lo_u <= counts.max() <= hi_u:
                break
            t = 1.0 + (t - 1.0) * (float(target) - float(yi.max())) / max(float(counts.max()) - float(yi.max()), 1.0) if counts.max() > yi.max() else t * float(target) / max(int(counts.max()), 1)
            t = max(t, 1.0 + 1e-9)
        else:
            raise XrdError(f"{p.name}: no corrected scan with a maximum inside {lo_u:,.0f}-{hi_u:,.0f} counts was found.")
        factor = t
    out = re.sub(r'(<(intensities|counts)\b[^>]*>)[^<]*(</\2>)',
                 lambda k: k.group(1) + " ".join(map(str, counts)) + k.group(3), txt, count=1)
    note = (f"COUNTING TIME CORRECTED (statistical simulation, x{factor:.3g}) by Origin Plot Studio from {p.name}: "
            + ("measured counts kept, extra counting time added as Poisson counts" if factor > 1 else "binomial thinning")
            + "; not a new measurement.")
    out = re.sub(r'(<comment>\s*)', lambda m: m.group(1) + "<entry>" + note.replace("&", "&amp;").replace("<", "&lt;") + "</entry>" + m.group(1)[len("<comment>"):], out, count=1)
    folder = Path(out_dir) if out_dir else p.parent
    folder.mkdir(parents=True, exist_ok=True)
    k, dest = 1, folder / f"{p.stem}{suffix}.xrdml"
    while dest.exists():                                        # never over an existing file
        k += 1
        dest = folder / f"{p.stem}{suffix}_{k}.xrdml"
    with open(dest, "x", encoding="utf-8", newline="\r\n" if crlf else "\n") as f:
        f.write(out)
    prov = {"what": "peak intensities corrected to the usual range by simulating a different counting time",
            "original_file": p.name, "original_sha256": sha, "original_highest_count": m,
            "corrected_file": dest.name, "corrected_highest_count": int(counts.max()), "usual_range_counts": [lo_u, hi_u],
            "method": method, "counting_time_factor": factor, "random_seed": "first 16 hex digits of the original's SHA-256" + (f", draw {int(draw)}" if draw else ""),
            "note": "The corrected scan is a statistical simulation of a measurement with a different counting time, "
                    "not a new measurement. The original file is unchanged.", **info}
    with open(dest.with_name(dest.stem + "_provenance.json"), "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=1)
    return str(dest), factor, method


_EXPECTED_CACHE = {}


def _expected(path):
    """(text, x, y, sample, name, sha256, crlf, expected counts, number of fitted peaks, smoothing) of a scan, the fit cached per file."""
    import hashlib
    p = Path(path)
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    txt, x, y, sample, sname = load_xrdml(p)
    y = np.clip(np.asarray(y, float), 0, None)
    key_ = (sha, len(y))
    if key_ not in _EXPECTED_CACHE:
        _EXPECTED_CACHE.clear(); _EXPECTED_CACHE[key_] = expected_counts(x, y)
    lam, npk, win = _EXPECTED_CACHE[key_]
    return txt, np.asarray(x, float), y, sample, sname, sha, b"\r\n" in raw, lam, npk, win


def peak_table(path, prominence=1.0):
    """The peaks of a measured scan for the Peak correct tab: [{"pos" (2θ), "fwhm", "top" (expected counts at the top, background
    included), "net" (top minus background)}], highest first. Uses the same analysis and fit as the correction."""
    txt, x, y, *_rest, lam, _n, _w = _expected(path)
    bg, _s, peaks = analyse_template(x, y, prominence)
    out = []
    for pos, _h, fw in peaks:
        m = np.abs(x - pos) <= max(float(fw), 2 * float(x[1] - x[0]))
        if not m.any():
            continue
        i = np.flatnonzero(m)[int(np.argmax(lam[m]))]
        out.append({"pos": float(x[i]), "fwhm": float(fw), "top": float(lam[i]), "net": float(lam[i] - bg[i])})
    return sorted(out, key=lambda d: -d["top"])


def count_longer(path, factor, out_dir=None, draw=0, suffix="_peakcorrected", why=""):
    """The whole scan as if counted `factor` times as long: factor > 1: your measured counts + Poisson counts of the extra time
    (drawn from the estimated noise-free scan, see correct_intensity); factor < 1: binomial thinning (a shorter count). Every point gets
    the same factor, so the relative intensities of the peaks stay those of your measurement. Saved as <stem><suffix>.xrdml with a
    provenance file; the original is never changed. Returns (new path, factor, method)."""
    import json
    factor = float(factor)
    if not (factor > 0):
        raise XrdError("The counting-time factor must be above 0.")
    p = Path(path)
    txt, x, y, sample, sname, sha, crlf, lam, npk, win = _expected(p)
    rng = np.random.default_rng([int(sha[:16], 16), 7919, int(draw)])
    yi = np.rint(y).astype(np.int64)
    if factor >= 1:
        counts = yi + rng.poisson(lam * (factor - 1.0))
        method = (f"counted {factor:.3g}x longer: your measured counts plus new Poisson counts for the extra counting time "
                  "(a measurement k times longer = this measurement + an independent one (k-1) times as long)")
    else:
        counts = rng.binomial(yi, factor)
        method = f"counted {factor:.3g}x as long (binomial thinning: a shorter measurement)"
    out = re.sub(r'(<(intensities|counts)\b[^>]*>)[^<]*(</\2>)', lambda k: k.group(1) + " ".join(map(str, counts)) + k.group(3), txt, count=1)
    note = (f"PEAK CORRECT (statistical simulation, counting time x{factor:.3g}) by Origin Plot Studio from {p.name}"
            + (f" - {why}" if why else "") + "; the same factor at every point, so relative intensities are kept; not a new measurement.")
    out = re.sub(r'(<comment>\s*)', lambda m: m.group(1) + "<entry>" + note.replace("&", "&amp;").replace("<", "&lt;") + "</entry>" + m.group(1)[len("<comment>"):], out, count=1)
    folder = Path(out_dir) if out_dir else p.parent
    folder.mkdir(parents=True, exist_ok=True)
    k, dest = 1, folder / f"{p.stem}{suffix}.xrdml"
    while dest.exists():
        k += 1
        dest = folder / f"{p.stem}{suffix}_{k}.xrdml"
    with open(dest, "x", encoding="utf-8", newline="\r\n" if crlf else "\n") as f:
        f.write(out)
    prov = {"what": "Peak correct: the scan as if counted for a different time (the same factor at every point)",
            "original_file": p.name, "original_sha256": sha, "original_highest_count": float(y.max()),
            "corrected_file": dest.name, "corrected_highest_count": int(counts.max()), "counting_time_factor": factor,
            "why_this_factor": why, "method": method, "random_seed": f"first 16 hex digits of the original's SHA-256, draw {int(draw)}",
            "peaks_fitted": npk, "residual_smoothing_sigma_points": win, "measured_counts_kept": factor >= 1,
            "note": "A statistical simulation of a measurement with a different counting time, not a new measurement. "
                    "Relative peak intensities are those of the original. The original file is unchanged."}
    with open(dest.with_name(dest.stem + "_provenance.json"), "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=1)
    return str(dest), factor, method


def factor_for_targets(peaks, targets):
    """The counting-time factor that brings every chosen peak to at least its target: max(target / top). peaks: peak_table rows;
    targets: {index: counts}. All peaks get this factor, so the others rise in proportion."""
    ks = [float(t) / peaks[i]["top"] for i, t in targets.items() if t and peaks[i]["top"] > 0]
    if not ks:
        raise XrdError("Tick at least one peak and give it a target height (counts).")
    return max(ks)


def improve_counts(max_counts, usual=USUAL_COUNTS):
    """The count range for better versions of a scan: the usual range for a scan below or above it; for a scan already
    inside it, 2-3 times its own counts (counting 2-3 times longer: less relative noise)."""
    lo_u, hi_u = usual
    if max_counts < lo_u or max_counts > hi_u:
        return float(lo_u), float(hi_u)
    return float(round(2 * max_counts, -2)), float(round(3 * max_counts, -2))


def improve_candidates(path, n=3, counts=None, out_dir=None, progress=None, cancelled=None):
    """n better versions of one measured scan to choose from: each is the scan counted longer (your counts kept + Poisson counts
    of the extra time, see correct_intensity) or thinned, with its own target spread over `counts` and its own random draw.
    Same 2θ grid, same points, same peaks as your scan: nothing is re-drawn from a peak list. Returns [(path, factor, method)]."""
    m = float(np.max(np.clip(np.asarray(load_xrdml(Path(path))[2], float), 0, None)))
    lo, hi = counts or improve_counts(m)
    out = []
    for i in range(int(n)):
        if cancelled and cancelled():
            break
        tgt = lo + (hi - lo) * (i + 1) / (int(n) + 1)               # spread inside the range: 25 %, 50 %, 75 % for three
        r = correct_intensity(path, target=tgt, out_dir=out_dir, usual=(lo, hi), draw=i + 1, suffix=f"_better_{i + 1:02d}")
        out.append(r)
        if progress:
            progress(i + 1, int(n), r)
    return out


# ----------------------------------------------------------------------------
# API used by the application (and by the command line below)
# ----------------------------------------------------------------------------
DEFAULTS = dict(n=5, points=(8000, 10000), counts=(8000.0, 10000.0), seed=None, out_dir="./scans",
                intensity_jitter=0.0, phase_jitter=0.25, dropout=0.0, prominence=1.0, preview=False)


@dataclass
class Template:
    path: str
    text: str
    x: np.ndarray
    y: np.ndarray
    sample: str             # the name the output files are called after
    original_name: str      # <name> as written in the template
    bg: np.ndarray
    sigma: np.ndarray
    peaks: np.ndarray       # rows: position, Ka1 height, Ka1 FWHM
    h_unit: float
    table: np.ndarray       # rows: position, relative intensity (%), FWHM
    fwhm_model: object
    prominence: float

    @property
    def filename(self):
        return Path(self.path).name

    def summary(self):
        b = bands(self.peaks[:, 1] + np.interp(self.peaks[:, 0], self.x, self.bg))
        return {"file": self.filename, "sample_id": self.sample, "name": self.original_name,
                "range": (float(self.x[0]), float(self.x[-1])), "points": int(len(self.x)),
                "max_counts": float(self.y.max()), "peaks": int(len(self.peaks)),
                "median_fwhm": float(np.median(self.peaks[:, 2])), "bands": b}


def need_scipy():
    if SCIPY_MISSING:
        raise XrdError("The XRD generator needs the Python package SciPy, which is not installed (" + SCIPY_MISSING + ").")


def suggest_counts(max_counts, default=(8000.0, 10000.0)):
    """The count range to propose for a template: the script's default when the template's own maximum lies in it,
    otherwise about +/-10 % around the template's maximum (rounded to 100 counts, at least 50).
    Returns (low, high, sentence)."""
    m = float(max_counts)
    lo_d, hi_d = default
    if lo_d <= m <= hi_d:
        return lo_d, hi_d, f"The template's maximum is {m:,.0f} counts, inside the usual range {lo_d:,.0f}–{hi_d:,.0f}: that range is used."
    lo = max(50.0, round(m * 0.9 / 100.0) * 100.0)
    hi = max(lo + 100.0, round(m * 1.1 / 100.0) * 100.0)
    if m < 1000:                        # small numbers: round to 10 instead
        lo = max(50.0, round(m * 0.9 / 10.0) * 10.0)
        hi = max(lo + 10.0, round(m * 1.1 / 10.0) * 10.0)
    return lo, hi, (f"The template's maximum is {m:,.0f} counts, outside the usual range {lo_d:,.0f}–{hi_d:,.0f}: "
                    f"the range is set to {lo:,.0f}–{hi:,.0f} counts (about ±10 % around it). Change it if you want.")


def load_template(path, prominence=1.0):
    """Read and analyse a template scan. Raises XrdError."""
    need_scipy()
    txt, x, y, sample, sname = load_xrdml(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")          # scipy's notes on very narrow peaks; the numbers are the same
        bg, sigma, peaks = analyse_template(x, y, prominence)
    if len(peaks) == 0:
        raise XrdError("No peaks above the noise level were found in the template scan.")
    h_unit = float(peaks[:, 1].max())
    table = np.column_stack([peaks[:, 0], 100.0 * peaks[:, 1] / h_unit, peaks[:, 2]])
    return Template(str(path), txt, x, y, sample, sname, bg, sigma, peaks, h_unit, table,
                    make_fwhm_model(peaks, x[1] - x[0]), prominence)


@dataclass
class Settings:
    template: str
    out_dir: str
    n: int = 5
    points: tuple = (8000, 10000)
    counts: tuple = (8000.0, 10000.0)
    seed: object = None
    phases: list = field(default_factory=lambda: [("template", 1.0)])   # ("template" or a peak-list file, weight)
    intensity_jitter: float = 0.0
    phase_jitter: float = 0.25
    dropout: float = 0.0
    prominence: float = 1.0
    preview: bool = False
    bg_mode: str = "keep"          # the template's background is kept unless you choose otherwise (BG_MODES)


def check_settings(s):
    """All problems with the settings, as readable sentences ([] = fine)."""
    e = []
    if not s.template:
        e.append("Choose a template .xrdml file.")
    elif not Path(s.template).is_file():
        e.append(f"The template file was not found: {s.template}")
    if not isinstance(s.n, int) or s.n < 1 or s.n > 10000:
        e.append("Number of scans must be a whole number from 1 to 10000.")
    p_lo, p_hi = s.points
    if not (isinstance(p_lo, int) and isinstance(p_hi, int)) or p_lo < 100 or p_hi < p_lo or p_hi > 1_000_000:
        e.append("Points per scan: the minimum must be at least 100 and not larger than the maximum (at most 1,000,000).")
    c_lo, c_hi = s.counts
    if not (c_lo > 0 and c_hi >= c_lo):
        e.append("Peak counts: the minimum must be above 0 and not larger than the maximum.")
    elif c_lo < 50:
        e.append("Peak counts: the minimum should be at least 50 counts, or Poisson noise cannot keep the maximum inside the range.")
    if s.seed is not None and (not isinstance(s.seed, int) or s.seed < 0 or s.seed > 2**63 - 1):
        e.append("Seed must be empty or a whole number of 0 or more.")
    if not s.phases:
        e.append("At least one phase is needed (the template's own peaks, or a reference peak list).")
    for name, w in s.phases:
        if not (w > 0):
            e.append(f"Phase weight of {Path(name).name if name != 'template' else 'the template'} must be above 0.")
        if name != "template" and not Path(name).is_file():
            e.append(f"Reference peak list not found: {name}")
    for label, v, hi in (("Intensity jitter", s.intensity_jitter, 2.0), ("Phase jitter", s.phase_jitter, 2.0), ("Dropout", s.dropout, 1.0)):
        if not (0 <= v <= hi):
            e.append(f"{label} must be between 0 and {hi:g}.")
    if getattr(s, "bg_mode", "keep") not in BG_MODES:
        e.append("Background: choose one of " + "; ".join(BG_MODES.values()) + ".")
    if not s.out_dir:
        e.append("Choose an output folder.")
    return e


def check_output_folder(path):
    """Create the folder if needed and make sure files can be written there. Raises XrdError."""
    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".write_test_", dir=p)
        os.close(fd)
        os.remove(tmp)
    except OSError as e:
        raise XrdError(f"The output folder cannot be written to: {p}\n({e.strerror or e}). Choose another folder.")
    return p


def build_phases(s, tpl):
    phases = []
    for name, weight in s.phases:
        if name == "template":
            phases.append(("template", tpl.table, float(weight)))
        else:
            ref = load_phase(name)
            phases.append((Path(name).stem, np.column_stack([ref, np.full(len(ref), np.nan)]), float(weight)))
    return phases


@dataclass
class Scan:
    sid: str
    x: np.ndarray
    counts: np.ndarray
    meta: dict
    files: list


@dataclass
class Result:
    scans: list
    files: list
    manifest: str = ""
    preview: str = ""
    cancelled: bool = False
    out_dir: str = ""


MANIFEST_HEADER = ("file,original_sample_name,seed,points,max_counts,target_max,peaks_below_5000,peaks_5000_8000,"
                   "peaks_above_8000,zero_shift_deg,width_scale,bg_scale,hump,phases")


def generate(s, tpl=None, progress=None, cancelled=None, log=None):
    """Write s.n scans. progress(done, total, scan), cancelled() -> True stops before the next scan, log(text).
    Raises XrdError for invalid settings; a scan whose maximum cannot be put in the range raises XrdError too."""
    say = log or (lambda m: None)
    errs = check_settings(s)
    if errs:
        raise XrdError("\n".join(errs))
    out_dir = check_output_folder(s.out_dir)
    tpl = tpl if tpl is not None and tpl.path == str(s.template) and tpl.prominence == s.prominence else load_template(s.template, s.prominence)
    phases = build_phases(s, tpl)
    master = np.random.default_rng(s.seed)
    p_lo, p_hi = s.points
    c_lo, c_hi = float(s.counts[0]), float(s.counts[1])
    stem0 = safe_stem(tpl.sample)
    rows, scans, files, number, stopped = [], [], [], 0, False
    for k in range(1, s.n + 1):
        if cancelled and cancelled():
            stopped = True
            say(f"Cancelled after {k - 1} of {s.n} scans.")
            break
        seed_k = int(master.integers(0, 2**31 - 1))
        rng = np.random.default_rng(seed_k)
        n_pts = int(rng.integers(p_lo, p_hi + 1))
        try:
            x_new, counts, meta = make_scan(tpl.x, tpl.bg, phases, tpl.h_unit, tpl.fwhm_model, tpl.x[0], tpl.x[-1],
                                            n_pts, c_lo, c_hi, rng, s.intensity_jitter, s.phase_jitter, s.dropout,
                                            getattr(s, "bg_mode", "keep"))
        except RuntimeError as e:
            raise XrdError(f"Scan {k}: {e}")
        while True:                               # the next free number: an existing file is never overwritten
            number += 1
            sid = f"{stem0}-{number:03d}"
            if not (out_dir / f"{sid}.xrdml").exists() and not (out_dir / f"{sid}.csv").exists():
                break
        try:
            write_xrdml(tpl.text, x_new, counts, sid, out_dir / f"{sid}.xrdml", rng)
            write_csv(x_new, counts, out_dir / f"{sid}.csv")
        except OSError as e:
            raise XrdError(f"{sid} could not be written to {out_dir}: {e.strerror or e}")
        ph = ";".join(f"{n}={w:.3f}" for n, w in meta["phases"])
        b5, b58, b8 = bands(meta["apex_counts"])
        rows.append(f"{sid}.xrdml,{tpl.sample},{seed_k},{n_pts},{counts.max()},{meta['target']:.0f},{b5},{b58},{b8},"
                    f"{meta['zero_shift']:+.4f},{meta['width_scale']:.3f},{meta['bg_scale']:.3f},{meta['hump']:.0f},{ph}")
        sc = Scan(sid, x_new, counts, dict(meta, seed=seed_k, points=n_pts), [str(out_dir / f"{sid}.xrdml"), str(out_dir / f"{sid}.csv")])
        scans.append(sc)
        files += sc.files
        say(f"{sid}: max {counts.max()} counts (target {meta['target']:.0f}), {n_pts} points; "
            f"template peaks below 5000: {b5}, 5000-8000: {b58}, above 8000: {b8}")
        if progress:
            progress(k, s.n, sc)
    mpath = out_dir / "manifest.csv"
    if rows:
        if mpath.exists():                         # a second run into the same folder: add its lines, keep the old ones
            with open(mpath, "a", newline="\n") as f:
                f.write("\n".join(rows) + "\n")
        else:
            with open(mpath, "w", newline="\n") as f:
                f.write("\n".join([MANIFEST_HEADER] + rows) + "\n")
        files.append(str(mpath))
    prev = ""
    if s.preview and scans:
        prev = str(write_preview(scans[:4], out_dir, c_hi))
        files.append(prev)
    return Result(scans, files, str(mpath) if rows else "", prev, stopped, str(out_dir))


def write_preview(scans, out_dir, c_hi):
    """preview.png of the first scans (as the command-line --preview), without overwriting an earlier one."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(11.7, 6.5))
    FigureCanvasAgg(fig)
    axs = fig.subplots(2, 2)
    for ax, sc in zip(axs.flat, scans):
        ax.plot(sc.x, sc.counts, lw=0.5, color="#1f3b73")
        ax.set_title(sc.sid, fontsize=9)
        ax.set_ylim(0, c_hi * 1.05)
    for ax in list(axs.flat)[len(scans):]:
        ax.set_visible(False)
    fig.tight_layout()
    p = Path(out_dir) / "preview.png"
    k = 1
    while p.exists():
        k += 1
        p = Path(out_dir) / f"preview_{k}.png"
    fig.savefig(p, dpi=130)
    return p


def parse_phase_spec(spec):
    name, _, w = spec.rpartition(":") if re.search(r":[\d.]+$", spec) else (spec, "", "1.0")
    return name, float(w or 1.0)


def main(argv=None):  # noqa: C901
    """Command line, same options as xrd_generator_v2.py."""
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="XRD scan generator")
    ap.add_argument("template")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--out-dir", default="./scans")
    ap.add_argument("--points", default="8000-10000")
    ap.add_argument("--counts", default="8000-10000")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--phase", action="append", default=[], metavar="FILE[:WEIGHT]")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--intensity-jitter", type=float, default=0.0)
    ap.add_argument("--phase-jitter", type=float, default=0.25)
    ap.add_argument("--dropout", type=float, default=0.0)
    ap.add_argument("--prominence", type=float, default=1.0)
    a = ap.parse_args(argv)
    s = Settings(a.template, a.out_dir, a.n, parse_range(a.points, int), parse_range(a.counts, float), a.seed,
                 [parse_phase_spec(p) for p in (a.phase or ["template:1.0"])], a.intensity_jitter, a.phase_jitter,
                 a.dropout, a.prominence, a.preview)
    try:
        r = generate(s, log=print)
    except XrdError as e:
        sys.exit(f"ERROR: {e}")
    print(f"done -> {Path(r.out_dir).resolve()}")


if __name__ == "__main__":
    main()

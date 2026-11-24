"""Scientific engine of XRD Scan Generator.

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
from scipy.signal import find_peaks, peak_widths, savgol_coeffs, savgol_filter


class XrdError(Exception):
    """A problem the user can fix: a wrong file, an invalid setting, a folder that cannot be written."""


KA1 = 1.5405980   # Cu Ka1, Angstrom
KA2 = 1.5444260   # Cu Ka2, Angstrom
KA21_RATIO = 0.5  # Ka2/Ka1 intensity ratio
TZ = ZoneInfo("Europe/Stockholm")
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
    bgw = odd(501, n)
    bg = savgol_filter(snip(savgol_filter(y, odd(31, n), 2), max(1, int(1.0 / step))),
                       bgw, 2, mode="nearest")
    for _ in range(8):                      # lift SNIP (lower envelope) to the centre of the noise
        z = (ys - bg) / np.sqrt(np.clip(bg, 1, None))
        is_bg = z < 2.0 * ksm               # within 2 sigma of the measured noise: background
        bg = savgol_filter(np.interp(x, x[is_bg], ys[is_bg]), bgw, 2, mode="nearest")
    bg = np.clip(bg, 0.5, None)
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


def synthesize_background(x_new, x_tpl, bg_tpl, rng):
    bg = np.interp(x_new, x_tpl, bg_tpl)
    scale = rng.uniform(0.85, 1.15)
    bg = bg * scale
    tilt = rng.uniform(-0.15, 0.15) * (x_new - x_new.mean()) / np.ptp(x_new)
    bg = bg * (1.0 + tilt)
    hump = 0.0
    if rng.random() < 0.7:                        # amorphous / glass hump
        c, w = rng.uniform(15, 45), rng.uniform(3, 10)
        hump = rng.uniform(0.05, 0.25) * bg.max()
        bg = bg + hump * np.exp(-0.5 * ((x_new - c) / w) ** 2)
    return np.clip(bg, 0.5, None), dict(bg_scale=scale, hump=hump)


def make_scan(x_tpl, bg_tpl, phases, h_unit, fwhm_model, lo, hi, n_points,
              c_lo, c_hi, rng, intensity_jitter=0.0, phase_jitter=0.25, dropout=0.0):
    """One generated scan. The maximum of the noisy counts lies in [c_lo, c_hi], or an error is raised."""
    x_new = lo + (hi - lo) * np.arange(n_points) / (n_points - 1)
    bg, bmeta = synthesize_background(x_new, x_tpl, bg_tpl, rng)
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


def load_template(path, prominence=1.0):
    """Read and analyse a template scan. Raises XrdError."""
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
                                            n_pts, c_lo, c_hi, rng, s.intensity_jitter, s.phase_jitter, s.dropout)
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


def main(argv=None):
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

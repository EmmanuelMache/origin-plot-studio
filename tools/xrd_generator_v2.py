#!/usr/bin/env python3
"""
xrd_generator_v2.py - XRD scan generator for software/pipeline testing.

Merges the original synth_xrd_generator.py with a noise-aware template analysis.
Takes a REAL measured .xrdml scan as a template and writes any number of randomised
generated scans (.xrdml + .csv) plus a ground-truth manifest.csv.

What the generator does
  * Template analysis that is robust to counting noise: iterative background
    (centred through the noise, not the lower envelope), local-Poisson noise level,
    peaks accepted only if they exceed 3 sigma of the local noise (no fake peaks).
  * Kalpha2 is removed from the template peak heights/widths before synthesis,
    then added back as a Ka1/Ka2 doublet (ratio 0.5), so it is not counted twice.
  * Pseudo-Voigt peaks with per-peak position / width jitter, global zero shift
    (sample displacement), crystallite-size-like width scale. The relative strengths
    of the template peaks are kept (--intensity-jitter 0 by default).
  * Every template peak that passes the 3 sigma noise test is kept, weak ones too.
  * The sample name of the template is kept: files are <name>-NNN, never overwritten.
  * Background from the template with random scale, tilt and optional amorphous hump.
  * True Poisson counting statistics; the maximum of the noisy counts is strictly
    inside the requested range, or the scan is not written.
  * Optional PHASE MIXTURES from reference stick patterns (2theta, intensity), e.g. an
    exported HighScore reference card. Weights are jittered per scan and written to
    manifest.csv as ground truth for testing search-match / quantification software.
  * Output files keep the instrument's Windows line endings and metadata and get a
    time stamp (Europe/Stockholm, correct UTC offset for the date).

Usage
    python xrd_generator_v2.py TEMPLATE.xrdml [--n 5] [--out-dir ./scans]
        [--points 8000-10000] [--counts 8000-10000] [--seed 42]
        [--phase ref1.csv:0.7 --phase template:0.2 --phase ref2.txt:0.1] [--preview]
        [--intensity-jitter 0] [--phase-jitter 0.25] [--dropout 0] [--prominence 1.0]

  --phase FILE[:WEIGHT]   reference peak list (2theta and relative intensity, one line
                          per reflection, any delimiter, header lines ignored). Lines
                          are taken as Ka1 positions. Use the name "template" to include
                          the template's own peaks. Without --phase only the template's
                          peaks are used.

"""

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from scipy.signal import find_peaks, peak_widths, savgol_coeffs, savgol_filter

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
    txt = open(path, encoding="utf-8").read()
    mpos = re.search(r'<positions axis="2Theta"[^>]*>\s*<startPosition>([^<]+)</startPosition>'
                     r'\s*<endPosition>([^<]+)</endPosition>', txt)
    mint = re.search(r'<intensities[^>]*>([^<]*)</intensities>', txt)
    if not mpos or not mint:
        sys.exit(f"ERROR: {path} does not look like a supported .xrdml scan")
    y = np.array([float(v) for v in mint.group(1).split()])
    x = np.linspace(float(mpos.group(1)), float(mpos.group(2)), len(y))
    blk = re.search(r'<sample\b[^>]*>(.*?)</sample>', txt, re.S)
    inner = blk.group(1) if blk else ""
    mid = re.search(r'<id>([^<]*)</id>', inner)
    mname = re.search(r'<name>([^<]*)</name>', inner)
    sid = mid.group(1).strip() if mid else ""
    sname = mname.group(1).strip() if mname else ""
    # the name the files are called after: <id>, then <name>, then the file name. Never a made-up name.
    sample = sid or sname or Path(path).stem
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
        sys.exit("ERROR: no peaks above the noise level found in template scan")

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
    for line in open(path, encoding="utf-8", errors="ignore"):
        nums = NUM.findall(line)
        if len(nums) >= 2:
            rows.append((float(nums[0]), float(nums[1])))
    if not rows:
        sys.exit(f"ERROR: no (2theta, intensity) lines found in {path}")
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
        t *= desired / achieved                    # noise moved the maximum: correct by the ratio and draw again
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
    out = re.sub(r'(<intensities[^>]*>)[^<]*(</intensities>)',
                 lambda m: m.group(1) + " ".join(map(str, counts)) + m.group(2), out, count=1)
    with open(out_path, "x", encoding="utf-8", newline="\r\n") as f:      # "x": never over an existing file
        f.write(out)


def write_csv(x_new, counts, out_path):
    if Path(out_path).exists():
        raise FileExistsError(out_path)
    np.savetxt(out_path, np.column_stack([x_new, counts]), delimiter=",",
               fmt=["%.5f", "%d"], header="2theta_deg,intensity_counts", comments="")


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="XRD scan generator")
    ap.add_argument("template", help="real .xrdml scan used as template")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--out-dir", default="./scans")
    ap.add_argument("--points", default="8000-10000", help="points per scan, fixed or min-max")
    ap.add_argument("--counts", default="8000-10000", help="max peak counts, fixed or min-max")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--phase", action="append", default=[], metavar="FILE[:WEIGHT]")
    ap.add_argument("--preview", action="store_true", help="write preview.png of the first scans")
    ap.add_argument("--intensity-jitter", type=float, default=0.0, metavar="SIGMA",
                    help="independent intensity variation per peak (log-normal sigma); 0 keeps the template's ratios")
    ap.add_argument("--phase-jitter", type=float, default=0.25, metavar="SIGMA",
                    help="variation of each phase weight per scan (log-normal sigma)")
    ap.add_argument("--dropout", type=float, default=0.0, metavar="FRACTION",
                    help="fraction of weak lines (below 8 %% relative intensity) left out at random; 0 keeps all")
    ap.add_argument("--prominence", type=float, default=1.0, metavar="FACTOR",
                    help="peak prominence needed, in units of the median noise sigma")
    a = ap.parse_args()

    master = np.random.default_rng(a.seed)
    p_lo, p_hi = parse_range(a.points, int)
    c_lo, c_hi = parse_range(a.counts, float)

    if c_lo > c_hi or c_lo <= 0:
        sys.exit("ERROR: --counts must be MIN-MAX with 0 < MIN <= MAX")
    txt, x, y, sample, sample_name = load_xrdml(a.template)
    stem0 = safe_stem(sample)
    step = x[1] - x[0]
    bg, sigma, tpl_peaks = analyse_template(x, y, a.prominence)
    h_unit = tpl_peaks[:, 1].max()
    fwhm_model = make_fwhm_model(tpl_peaks, step)
    tpl_table = np.column_stack([tpl_peaks[:, 0], 100.0 * tpl_peaks[:, 1] / h_unit, tpl_peaks[:, 2]])

    phases = []
    for spec in a.phase or ["template:1.0"]:
        name, _, w = spec.rpartition(":") if re.search(r":[\d.]+$", spec) else (spec, "", "1.0")
        weight = float(w or 1.0)
        if name == "template":
            phases.append(("template", tpl_table, weight))
        else:
            ref = load_phase(name)
            phases.append((Path(name).stem, np.column_stack([ref, np.full(len(ref), np.nan)]), weight))

    print(f"template: {a.template}")
    print(f"  {len(x)} pts, {x[0]:.3f}-{x[-1]:.3f} deg, max {y.max():.0f} counts")
    print(f"  {len(tpl_peaks)} peaks above 3 sigma, background {bg.min():.0f}-{bg.max():.0f} counts, "
          f"median FWHM(Ka1) {np.median(tpl_peaks[:, 2]):.3f} deg")
    print("  phases: " + ", ".join(f"{n}:{w}" for n, _, w in phases))
    print(f"  sample name kept: {sample!r} (<name> in the file: {sample_name!r})")
    print("  peaks passing the 3 sigma test at prominence " + ", ".join(
        f"{f:g}: {count_candidates(x, y, bg, sigma, f)}" for f in (2.0, 1.0, 0.5)) + f"  (used: {a.prominence:g})")
    tb = bands(tpl_peaks[:, 1] + np.interp(tpl_peaks[:, 0], x, bg))
    print(f"  template peaks by height of their top: below 5000: {tb[0]}, 5000-8000: {tb[1]}, above 8000: {tb[2]}")

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = ["file,original_sample_name,seed,points,max_counts,target_max,peaks_below_5000,peaks_5000_8000,"
                "peaks_above_8000,zero_shift_deg,width_scale,bg_scale,hump,phases"]
    number = 0
    prev = []

    for k in range(1, a.n + 1):
        seed_k = int(master.integers(0, 2**31 - 1))
        rng = np.random.default_rng(seed_k)
        n_pts = int(rng.integers(p_lo, p_hi + 1))
        x_new, counts, meta = make_scan(x, bg, phases, h_unit, fwhm_model,
                                        x[0], x[-1], n_pts, c_lo, c_hi, rng,
                                        a.intensity_jitter, a.phase_jitter, a.dropout)
        while True:                               # the next free number: an existing file is never overwritten
            number += 1
            sid = f"{stem0}-{number:03d}"
            if not (out_dir / f"{sid}.xrdml").exists() and not (out_dir / f"{sid}.csv").exists():
                break
        write_xrdml(txt, x_new, counts, sid, out_dir / f"{sid}.xrdml", rng)
        write_csv(x_new, counts, out_dir / f"{sid}.csv")
        ph = ";".join(f"{n}={w:.3f}" for n, w in meta["phases"])
        b5, b58, b8 = bands(meta["apex_counts"])
        manifest.append(f"{sid}.xrdml,{sample},{seed_k},{n_pts},{counts.max()},{meta['target']:.0f},{b5},{b58},{b8},"
                        f"{meta['zero_shift']:+.4f},{meta['width_scale']:.3f},{meta['bg_scale']:.3f},{meta['hump']:.0f},{ph}")
        print(f"  {sid}: max {counts.max()} counts (target {meta['target']:.0f}, {meta['attempts']} draw(s)), {n_pts} pts; "
              f"template peaks below 5000: {b5}, 5000-8000: {b58}, above 8000: {b8}")
        if k <= 4:
            prev.append((sid, x_new, counts))

    mpath = out_dir / "manifest.csv"
    if mpath.exists():                             # a second run into the same folder: add its lines, keep the old ones
        manifest = manifest[1:] if mpath.read_text().startswith(manifest[0]) else manifest
        with open(mpath, "a", newline="\n") as f:
            f.write("\n".join(manifest) + "\n")
    else:
        with open(mpath, "w", newline="\n") as f:
            f.write("\n".join(manifest) + "\n")
    if a.preview:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(2, 2, figsize=(11.7, 6.5))
        for ax, (sid, xx, cc) in zip(axs.flat, prev):
            ax.plot(xx, cc, lw=0.5, color="#1f3b73")
            ax.set_title(sid, fontsize=9)
            ax.set_ylim(0, c_hi * 1.05)
        fig.tight_layout()
        fig.savefig(out_dir / "preview.png", dpi=130)
    print(f"done -> {out_dir.resolve()}")


if __name__ == "__main__":
    main()

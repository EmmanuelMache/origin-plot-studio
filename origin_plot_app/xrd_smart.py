"""
xrd_smart.py - everything XRD-specific for the Origin plot app.

  * readers for instrument files: PANalytical .xrdml, Bruker .brml and .uxd, Rigaku .ras
    (the X-ray wavelength is taken from the file when it is there)
  * background by the SNIP algorithm, noise from counting statistics
  * peak finding on the background-corrected pattern with FWHM, signal-to-noise and
    K-alpha2 recognition (a K-alpha2 shoulder is never labelled as a peak of its own)
  * a phase library (d-spacings and relative intensities) and a simple search-match that
    suggests which phase each peak belongs to; peak lists exported from HighScore (with
    Phase Assignment) are used directly and are also learnt into the library
  * Rwp of observed/calculated profiles

numpy and pandas only.
"""
import os, re, io, glob, math, zipfile
import numpy as np
import pandas as pd
from xml.etree import ElementTree as ET

# K-alpha1 -> K-alpha2 wavelengths (Å)
KA2 = {1.5406: 1.54443, 1.78897: 1.79285, 1.93604: 1.93998, 2.28970: 2.29361, 0.70930: 0.71359, 0.55941: 0.56380}

def ka2_of(lam):
    k = min(KA2, key=lambda v: abs(v - lam)); return KA2[k] * lam / k if abs(k - lam) < 0.01 else None

def two_theta(d, lam):
    s = lam / (2.0 * np.asarray(d, float)); out = np.full(s.shape, np.nan); ok = s < 1
    out[ok] = 2 * np.degrees(np.arcsin(s[ok])); return out

def d_of(tt, lam):
    return lam / (2 * np.sin(np.radians(np.asarray(tt, float) / 2)))

# ============================================================================= instrument files
META = {}            # path -> {"wavelength": ..., "instrument": ...}

def _frame(xname, yname, x, y):
    return pd.DataFrame([[xname, yname]] + [[a, b] for a, b in zip(x, y)])

def _local(tag): return tag.rsplit("}", 1)[-1]

def read_xrdml(path):
    root = ET.parse(path).getroot(); out = []; lam = None
    for el in root.iter():
        if _local(el.tag) == "kAlpha1" and el.text:
            try: lam = float(el.text)
            except ValueError: pass
    k = 0
    for scan in root.iter():
        if _local(scan.tag) != "dataPoints": continue
        x = y = None; ct = None
        for el in scan:
            t = _local(el.tag)
            if t == "positions" and el.get("axis") in ("2Theta", "2theta"):
                d = {_local(c.tag): c.text for c in el}
                if "listPositions" in d: x = np.array(d["listPositions"].split(), float)
                else: x0, x1 = float(d["startPosition"]), float(d["endPosition"]); x = ("lin", x0, x1)
            elif t in ("counts", "intensities") and el.text: y = np.array(el.text.split(), float); unit = el.get("unit", "counts")
            elif t == "commonCountingTime" and el.text: ct = float(el.text)
        if y is None or x is None: continue
        if isinstance(x, tuple): x = np.linspace(x[1], x[2], len(y))
        k += 1; out.append((f"{os.path.splitext(os.path.basename(path))[0]}" + (f"_scan{k}" if k > 1 else ""), _frame("2Theta (deg)", f"Intensity ({unit})", x, y)))
    META[path] = {"wavelength": lam, "instrument": "PANalytical (.xrdml)"}; return out

def read_ras(path):
    txt = open(path, "r", encoding="latin-1", errors="replace").read(); lam = None
    m = re.search(r'\*HW_XG_WAVE_LENGTH_ALPHA1\s+"?([\d.]+)', txt)
    if m: lam = float(m.group(1))
    out = []
    for k, block in enumerate(re.findall(r"\*RAS_INT_START(.*?)\*RAS_INT_END", txt, re.S), 1):
        rows = [l.split() for l in block.strip().splitlines() if l.strip() and not l.startswith("*")]
        a = np.array([[float(v) for v in r[:2]] for r in rows if len(r) >= 2])
        if len(a): out.append((os.path.splitext(os.path.basename(path))[0] + (f"_scan{k}" if k > 1 else ""), _frame("2Theta (deg)", "Intensity (counts)", a[:, 0], a[:, 1])))
    META[path] = {"wavelength": lam, "instrument": "Rigaku (.ras)"}; return out

def read_uxd(path):
    lines = open(path, "r", encoding="latin-1", errors="replace").read().splitlines(); kv = {}; data = []
    for l in lines:
        s = l.strip()
        if not s or s.startswith(";"): continue
        if s.startswith("_"):
            if "=" in s: a, b = s[1:].split("=", 1); kv[a.strip().upper()] = b.strip()
            continue
        try: data.append([float(v) for v in s.replace(",", " ").split()])
        except ValueError: pass
    lam = None
    for key in ("WL1", "WLA1"):
        try: lam = float(kv[key]); break
        except (KeyError, ValueError): pass
    if data and len(data[0]) >= 2: a = np.array([r[:2] for r in data if len(r) >= 2]); x, y = a[:, 0], a[:, 1]
    else:
        y = np.array([v for r in data for v in r]); x0 = float(kv.get("START", kv.get("2THETA", 0))); st = float(kv.get("STEPSIZE", 0.02)); x = x0 + st * np.arange(len(y))
    META[path] = {"wavelength": lam, "instrument": "Bruker (.uxd)"}
    return [(os.path.splitext(os.path.basename(path))[0], _frame("2Theta (deg)", "Intensity (counts)", x, y))]

def read_brml(path):
    out = []; lam = None
    with zipfile.ZipFile(path) as z:
        for nm in sorted(n for n in z.namelist() if re.search(r"RawData\d*\.xml$", n)):
            root = ET.fromstring(z.read(nm)); rows = []
            for el in root.iter():
                t = _local(el.tag)
                if t in ("WaveLengthAlpha1", "KAlpha1") and lam is None:
                    try: lam = float(el.get("Value") or el.text)
                    except (TypeError, ValueError): pass
                if t == "Datum" and el.text:
                    try: rows.append([float(v) for v in el.text.split(",")])
                    except ValueError: pass
            if not rows: continue
            a = np.array([r for r in rows if len(r) == len(rows[0])]); xi = None
            for j in range(a.shape[1] - 1):
                c = a[:, j]; dd = np.diff(c)
                if 1 <= c.min() and c.max() <= 170 and np.all(dd > 0) and np.median(dd) < 0.3: xi = j          # 2theta: last increasing angle-like column
            if xi is None: continue
            out.append((os.path.splitext(os.path.basename(path))[0] + (f"_{len(out) + 1}" if out else ""), _frame("2Theta (deg)", "Intensity (counts)", a[:, xi], a[:, -1])))
    META[path] = {"wavelength": lam, "instrument": "Bruker (.brml)"}; return out

READERS = {".xrdml": read_xrdml, ".ras": read_ras, ".uxd": read_uxd, ".brml": read_brml}
EXTS = tuple(READERS)

# ============================================================================= background, noise, peaks
def _smooth(y, w):
    w = int(w) | 1
    if w < 3 or len(y) < w + 2: return np.asarray(y, float).copy()
    h = w // 2; A = np.vander(np.arange(-h, h + 1), 3, increasing=True); c = np.linalg.pinv(A)[0]
    yp = np.concatenate([2 * y[0] - y[h:0:-1], y, 2 * y[-1] - y[-2:-h - 2:-1]]); return np.convolve(yp, c[::-1], mode="valid")

def background(x, y, width_deg=2.0):
    """SNIP background (Ryan et al. 1988) on the LLS-transformed, lightly smoothed pattern.
    width_deg: features narrower than this are peaks, broader ones (amorphous humps) background."""
    y = np.asarray(y, float); step = float(np.median(np.abs(np.diff(x)))) or 0.02
    m = int(np.clip(round(width_deg / step / 2), 3, 600)); ys = np.clip(_smooth(y, 5), 0, None)
    v = np.log(np.log(np.sqrt(ys + 1) + 1) + 1)
    for k in range(1, m + 1):
        v[k:-k] = np.minimum(v[k:-k], 0.5 * (v[:-2 * k] + v[2 * k:]))
    b = (np.exp(np.exp(v) - 1) - 1) ** 2 - 1
    return np.minimum(b, ys)

def _fwhm_points(net, i):
    h = net[i] / 2.0; l = i
    while l > 0 and net[l] > h: l -= 1
    r = i
    while r < len(net) - 1 and net[r] > h: r += 1
    fl = l + (h - net[l]) / (net[l + 1] - net[l]) if net[l + 1] != net[l] else l
    fr = r - (h - net[r]) / (net[r - 1] - net[r]) if net[r - 1] != net[r] else r
    return max(1.0, fr - fl)

def find_xrd_peaks(x, y, lam=1.5406, min_rel=0.01, snr=5.0, bg_width=2.0, bg=None):
    """Peaks of an XRD pattern. Returns (peaks, background, info). Each peak: pos, d, top (raw counts at the top),
    net (above background), fwhm (deg), snr, ka2 (True when it is the K-alpha2 partner of a stronger peak)."""
    x = np.asarray(x, float); y = np.asarray(y, float); o = np.argsort(x); x, y = x[o], y[o]; n = len(x)
    if n < 20: return [], np.zeros_like(y), {}
    step = float(np.median(np.diff(x)))
    b = background(x, y, bg_width) if bg is None else np.asarray(bg, float)[o]
    # noise: counting statistics, sigma proportional to sqrt(background) (also right for cps data, just scaled)
    r = (y - _smooth(y, 5)) / np.sqrt(np.clip(b, 1e-12, None) + 1e-12)
    s = 1.4826 * np.median(np.abs(r - np.median(r))) / 0.6          # the 5-point smoother removes part of the noise
    g = 1.4826 * np.median(np.abs((y - _smooth(y, 5)) - np.median(y - _smooth(y, 5)))) / 0.6
    sig = np.sqrt((s * np.sqrt(np.clip(b, 0, None))) ** 2 + (0.3 * g) ** 2) + 1e-12
    net0 = _smooth(y, 5) - b
    # typical peak width from the strongest maxima, then a smoothing window that does not distort the peaks
    sig = np.maximum(sig, 1e-4 * float(np.max(np.abs(net0)) or 1.0))           # noise-free (simulated) data
    cand = np.where((net0[1:-1] > net0[:-2]) & (net0[1:-1] >= net0[2:]) & (net0[1:-1] > 8 * sig[1:-1]) & (net0[1:-1] > 0.05 * net0.max()))[0] + 1
    top = cand[np.argsort(-net0[cand])][:15] if len(cand) else []
    fws = sorted(_fwhm_points(net0, i) for i in top)
    fw = float(np.percentile(fws, 35)) if fws else 6.0                         # lower part: overlapping clusters look broader
    w = int(np.clip(0.7 * fw, 5, 41)) | 1
    net = _smooth(y, w) - b; sigs = sig / math.sqrt(max(1.0, w / 3.0))
    mx = float(np.max(net)) or 1.0
    idx = np.where((net[1:-1] > net[:-2]) & (net[1:-1] >= net[2:]))[0] + 1; peaks = []
    for i in idx:
        if net[i] < min_rel * mx or net[i] < snr * sigs[i]: continue
        l = i
        while l > 0 and net[l - 1] <= net[i] and i - l < 6 * fw: l -= 1
        rr = i
        while rr < n - 1 and net[rr + 1] <= net[i] and rr - i < 6 * fw: rr += 1
        prom = net[i] - max(net[l:i + 1].min(), net[i:rr + 1].min())
        if prom < 0.6 * snr * sigs[i] or prom < 0.25 * net[i]: continue
        a, bb, c = net[i - 1], net[i], net[i + 1]; den = a - 2 * bb + c
        dd = float(np.clip(0.5 * (a - c) / den, -0.5, 0.5)) if den != 0 else 0.0
        pos = x[i] + dd * step
        j0, j1 = max(0, i - 2), min(n, i + 3); topv = float(y[j0:j1].max())
        peaks.append(dict(pos=float(pos), d=float(d_of(pos, lam)), top=topv, net=float(net[i]), fwhm=float(_fwhm_points(net0, i) * step), snr=float(net[i] / sig[i]), ka2=False, index=int(i)))
    # merge maxima closer than half a peak width (noise on a peak top)
    peaks.sort(key=lambda p: -p["net"]); kept = []
    for p in peaks:
        if all(abs(p["pos"] - q["pos"]) > 0.5 * max(p["fwhm"], q["fwhm"], 2 * step) for q in kept): kept.append(p)
    # K-alpha2 partners
    l2 = ka2_of(lam)
    if l2:
        for p in kept:
            if p["ka2"]: continue
            s1 = math.sin(math.radians(p["pos"] / 2)) * l2 / lam
            if s1 >= 1: continue
            pos2 = 2 * math.degrees(math.asin(s1)); dl = pos2 - p["pos"]
            if dl < 0.6 * p["fwhm"]: continue
            for q in kept:
                if q is not p and not q["ka2"] and abs(q["pos"] - pos2) < max(0.35 * p["fwhm"], 1.5 * step) and 0.25 <= q["net"] / p["net"] <= 0.75: q["ka2"] = True
    info = dict(step=step, fwhm_typical=fw * step, smooth_window=w, noise_sigma=float(np.median(sig)), bg_width=bg_width, n_ka2=sum(p["ka2"] for p in kept))
    inv = np.empty_like(o); inv[o] = np.arange(n)
    return sorted(kept, key=lambda p: p["pos"]), b[inv], info

# ============================================================================= phase library
CODE_NAMES = {"A": "alite (C3S)", "B": "belite (β-C2S)", "B'": "α'H-C2S", "C": "aluminate (C3A)", "F": "ferrite (C4AF)", "L": "free lime (CaO)", "P": "periclase (MgO)",
              "G": "gypsum", "R": "rutile (TiO2)", "Q": "quartz", "Ab": "albite", "Mc": "microcline", "Or": "K-feldspar (orthoclase)", "Ms": "muscovite", "Bt": "biotite",
              "Crd": "cordierite", "Cal": "calcite", "Dol": "dolomite", "Z": "zincite (ZnO)", "CH": "portlandite", "AFt": "ettringite", "Hc": "hemicarbonate", "Mc*": "monocarbonate"}
NAME_TO_CODE = [(r"m3.?c3s|alite|c3s", "A"), (r"alpha.?prime|alphaprime|c2s.?alpha", "B'"), (r"beta.?c2s|belite|larnite|c2s", "B"), (r"c3a|aluminate", "C"), (r"c4af|brownmillerite|ferrite", "F"),
                (r"^cao$|lime", "L"), (r"periclase|^mgo", "P"), (r"gypsum", "G"), (r"rutile|anatase|tio2", "R"), (r"quartz", "Q"), (r"albite", "Ab"), (r"microcline", "Mc"),
                (r"orthoclase|sanidine|potassium.?aluminum.?silicate", "Or"), (r"muscovite", "Ms"), (r"biotite", "Bt"), (r"cordierite", "Crd"), (r"calcite", "Cal"),
                (r"dolomite", "Dol"), (r"zincite|^zno|zinc.?oxide", "Z"), (r"oligoclase", "Olg"), (r"portlandite", "CH"), (r"ettringite", "AFt")]

def code_for(name):
    m = re.search(r"\(([A-Za-z'*]{1,4})\)\s*$", str(name))
    if m: return m.group(1)
    s = re.sub(r"^cod\d+[ _]", "", str(name).strip().lower())
    for pat, c in NAME_TO_CODE:
        if re.search(pat, s): return c
    w = re.sub(r"[^A-Za-z]", "", str(name)); return (w[:1].upper() + w[1:3].lower()) if w else "?"

def library_files(folder, extra=()):
    """The files of the phase library, in order of priority: the built-in library, phases learnt by older versions,
    the csv files in phase_library/ next to the app, then your own store (stored_phases.csv first) in each extra folder."""
    fs = [os.path.join(folder, "xrd_phase_library.csv"), os.path.join(folder, "learnt_phases.csv")] + sorted(glob.glob(os.path.join(folder, "phase_library", "*.csv")))
    try:
        import private_store; pd_ = private_store.private_dir()
        if os.path.isdir(pd_): fs = sorted(glob.glob(os.path.join(pd_, "*.csv"))) + fs      # your private phase files first
    except Exception: pass
    for e in extra or ():
        fs += [os.path.join(e, "stored_phases.csv")] + [f for f in sorted(glob.glob(os.path.join(e, "*.csv"))) if os.path.basename(f) != "stored_phases.csv"]
    return [f for f in fs if os.path.exists(f)]

def phase_frame(t, fallback):
    """A table with d or 2theta, intensities and (optionally) phase names and codes -> Phase, Code, d, I (strongest line of each phase = 100). None when it has no d or 2theta column."""
    if True:
        n = {c: re.sub(r"[^a-z0-9]", "", c.lower()) for c in t.columns}
        dcol = next((c for c in t.columns if n[c].startswith("d") and ("a" in n[c][1:4] or "spacing" in n[c] or n[c] in ("d", "da"))), None)
        tcol = next((c for c in t.columns if "2th" in n[c] or "twotheta" in n[c] or "2theta" in n[c]), None)
        icol = next((c for c in t.columns if n[c].startswith("irel") or n[c] in ("i", "i%", "int", "intensity", "relint", "relintensity") or n[c].startswith("relint") or n[c].startswith("i%") or n[c] == "ip"), None)
        if icol is None: icol = next((c for c in t.columns if n[c].startswith("i") and c not in (dcol, tcol)), None)
        pcol = next((c for c in t.columns if n[c] in ("phase", "phasename", "mineral", "name")), None); ccol = next((c for c in t.columns if n[c] == "code"), None)
        if dcol is None and tcol is None: return None
        d = pd.to_numeric(t[dcol], errors="coerce") if dcol else pd.Series(d_of(pd.to_numeric(t[tcol], errors="coerce"), 1.5406))
        I = pd.to_numeric(t[icol], errors="coerce") if icol else pd.Series(np.full(len(t), 100.0))
        ph = t[pcol].astype(str) if pcol else pd.Series([fallback] * len(t))
        cd = t[ccol].astype(str) if ccol else ph.map(code_for)
        u = pd.DataFrame({"Phase": ph.values, "Code": cd.values, "d": d.values, "I": I.values}).dropna(subset=["d"])
        u = u[(u["d"] > 0.3) & (u["d"] < 60)]
        if u.empty: return None
        u["I"] = u.groupby("Code")["I"].transform(lambda v: 100 * v / (v.max() or 1)); return u

def load_library(folder, extra=()):
    """Every file of library_files() as one table (one phase per file, or several with a Phase column; for example
    a reference-card peak list exported from HighScore: d, I %, h k l). A code keeps the lines of the first file that has it."""
    parts = []
    for f in library_files(folder, extra):
        try:
            t = pd.read_csv(f, encoding="utf-8-sig", sep=None, engine="python")
        except Exception: continue
        u = phase_frame(t, os.path.splitext(os.path.basename(f))[0])
        if u is None: continue
        u["Source"] = os.path.basename(f) if os.path.dirname(f).startswith(folder) else f; parts.append(u)
    if not parts: return pd.DataFrame(columns=["Phase", "Code", "d", "I", "Source"])
    lib = pd.concat(parts, ignore_index=True)
    first = lib.drop_duplicates("Code")[["Code", "Source"]]                 # one source per code: the first file that has it
    return lib.merge(first, on=["Code", "Source"])

def learn(peaklist_rows, folder):
    """Add the phases of a HighScore peak list (Phase Assignment) to learnt_phases.csv. Returns the codes that were new."""
    lib = load_library(folder); have = set(lib["Code"]); f = os.path.join(folder, "learnt_phases.csv")
    new = peaklist_rows[~peaklist_rows["Code"].isin(have)]
    if new.empty: return []
    keep = new[["Phase", "Code", "d", "I"]].rename(columns={"d": "d (A)", "I": "I_rel (%)"})
    old = pd.read_csv(f, encoding="utf-8-sig") if os.path.exists(f) else None
    (pd.concat([old, keep]) if old is not None else keep).to_csv(f, index=False, encoding="utf-8-sig")
    return sorted(new["Code"].unique())

# ============================================================================= search-match (whole-pattern)
def nnls(A, b, iters=None):
    """Lawson-Hanson non-negative least squares: min |Ax - b| with x >= 0 (numpy only)."""
    m, n = A.shape; x = np.zeros(n); P = np.zeros(n, bool); w = A.T @ (b - A @ x); it = 0; iters = iters or 3 * n
    while (~P).any() and w[~P].max() > 1e-10 * (abs(w).max() + 1e-300) and it < iters:
        it += 1; j = int(np.argmax(np.where(P, -np.inf, w))); P[j] = True
        while True:
            z = np.zeros(n); z[P] = np.linalg.lstsq(A[:, P], b, rcond=None)[0]
            if (z[P] > 0).all(): x = z; break
            neg = P & (z <= 0); a = np.min(x[neg] / (x[neg] - z[neg] + 1e-300)); x = x + a * (z - x); P &= x > 1e-12
            if not P.any(): break
        w = A.T @ (b - A @ x)
    return x

def _pv(x, c, fw, eta=0.5):
    dx = (x - c) / (fw / 2); return eta / (1 + dx * dx) + (1 - eta) * np.exp(-math.log(2) * dx * dx)

def phase_pattern(x, tt, I, fw_fun, lam, ka2=True, broad=1.0):
    """Calculated pattern of one phase on the grid x (peak height = I for K-alpha1)."""
    y = np.zeros_like(x); l2 = ka2_of(lam) if ka2 else None
    for c, h in zip(tt, I):
        f = fw_fun(c) * broad; lo, hi = np.searchsorted(x, [c - 8 * f, c + 8 * f + 0.6]); xs = x[lo:hi]
        y[lo:hi] += h * _pv(xs, c, f)
        if l2:
            s = math.sin(math.radians(c / 2)) * l2 / lam
            if s < 1: y[lo:hi] += 0.5 * h * _pv(xs, 2 * math.degrees(math.asin(s)), f)
    return y

def width_model(peaks):
    """FWHM(2theta) = a + b tan(theta), fitted to clean, strong, single peaks (Caglioti-like, robust)."""
    p = [q for q in peaks if not q["ka2"] and q["snr"] > 15]
    if len(p) < 4: f = float(np.median([q["fwhm"] for q in peaks])) if peaks else 0.1; return lambda tt: f, (f, 0.0)
    tt = np.array([q["pos"] for q in p]); fw = np.array([q["fwhm"] for q in p]); keep = fw <= np.quantile(fw, 0.5) * 1.6     # leave out overlapped clusters
    X = np.c_[np.ones(keep.sum()), np.tan(np.radians(tt[keep] / 2))]; a, b = np.linalg.lstsq(X, fw[keep], rcond=None)[0]
    a = max(a, 0.3 * float(np.median(fw[keep]))); b = max(b, 0.0)
    return (lambda t: a + b * math.tan(math.radians(t / 2))), (float(a), float(b))

def identify(x, y, peaks, lib, lam, bg=None, only=None, min_gain=0.01, log=None):
    """Whole-pattern search-match. Each library phase becomes a calculated pattern (its lines broadened like the
    measured peaks, K-alpha2 added, a narrow and a broad version), a small global zero-shift is scanned, and the
    measured pattern minus background is fitted with non-negative amounts of the phases (weighted by counting
    statistics). A phase is kept only if (1) leaving it out makes the fit worse by at least 0.4 % of the misfit
    (weighted chi-square) and (2) it has a measured peak of its own (where it gives >= 50 % of the fitted
    intensity and that peak is clearly above the noise).
    Returns (phases {code: info}, phase patterns {code: array on x}, details dict)."""
    x = np.asarray(x, float); y = np.asarray(y, float); o = np.argsort(x); x, y = x[o], y[o]
    if lib is None or lib.empty or len(x) < 50: return {}, {}, {}
    b = background(x, y) if bg is None else np.asarray(bg, float)[o]
    net = np.clip(y - b, 0, None) if True else None; sd = np.sqrt(np.clip(y, 1, None)) if np.nanmedian(y) > 20 else np.sqrt(np.clip(y, 1e-6, None)) * 0 + max(1e-9, float(np.std(y - _smooth(y, 5))))
    fwf, (fa, fb) = width_model(peaks); x0, x1 = x[0], x[-1]
    codes, cols, names = [], [], {}
    for code, g in lib.groupby("Code"):
        if only is not None and code not in only: continue
        tt = two_theta(g["d"].values, lam); I = g["I"].values; ok = np.isfinite(tt) & (tt >= x0 - 1) & (tt <= x1 + 1)
        if ok.sum() == 0 or I[ok].max() < 5: continue
        codes.append(code); names[code] = (g["Phase"].iloc[0], tt[ok], I[ok])
    if not codes: return {}, {}, {}
    # peak width, K-alpha2 (present or stripped) and a small zero shift: chosen by the best fit
    sub = slice(None, None, max(1, len(x) // 6000)); rhs = net / sd
    def build(ka2, wf): return {c: [phase_pattern(x, names[c][1], names[c][2], lambda t_: wf * fwf(t_), lam, ka2, 1.0), phase_pattern(x, names[c][1], names[c][2], lambda t_: wf * fwf(t_), lam, ka2, 3.0)] for c in codes}
    tags = [(c, k) for c in codes for k in (0, 1)]
    def score(base, shift):
        cc = [np.interp(x - shift, x, base[c][k]) for c, k in tags]; A_ = np.array(cc).T / sd[:, None]; s_ = nnls(A_[sub], rhs[sub])
        return float(np.sum((A_[sub] @ s_ - rhs[sub]) ** 2)), s_, cc
    best = None
    for ka2 in ([True, False] if ka2_of(lam) else [False]):
        for wf in (0.45, 0.65, 0.9):
            base = build(ka2, wf)
            for shift in (-0.06, -0.03, 0.0, 0.03, 0.06):
                chi, s_, cc = score(base, shift)
                if best is None or chi < best[0]: best = (chi, shift, ka2, wf, s_, cc, base)
    chi, shift, ka2, wf, s, cols, base = best
    for sh in np.arange(shift - 0.025, shift + 0.026, 0.005):
        ch, ss, cc = score(base, sh)
        if ch < chi: chi, shift, s, cols = ch, float(sh), ss, cc
    A = np.array(cols).T / sd[:, None]; rhs = net / sd; chi0 = float(np.sum(rhs ** 2))
    active = sorted({tags[i][0] for i in np.where(s > 0)[0]})
    def fit(keep):
        idx = [i for i, (c, k) in enumerate(tags) if c in keep]
        if not idx: return chi0, np.zeros(len(tags))
        ss = np.zeros(len(tags)); ss[idx] = nnls(A[sub][:, idx], rhs[sub]); return float(np.sum((A[sub] @ ss - rhs[sub]) ** 2)), ss
    # backward elimination: drop the phase whose removal costs least, while it costs less than min_gain of chi0
    keep = list(active)
    while keep:
        full, _ = fit(keep); costs = {c: fit([k for k in keep if k != c])[0] - full for c in keep}
        c, cost = min(costs.items(), key=lambda kv: kv[1])
        if cost < max(min_gain * full, 1e-3 * chi0): keep.remove(c)
        else: break
    full, s = fit(keep)
    pats = {}
    for i, (c, k) in enumerate(tags):
        if s[i] > 0: pats[c] = pats.get(c, 0) + s[i] * cols[i]
    total = sum(pats.values()) if pats else np.zeros_like(x)
    # own-evidence test on the measured peaks
    out = {}; thr = {}
    for p in peaks:
        if p["ka2"]: continue
        j = int(np.argmin(np.abs(x - p["pos"]))); tot = total[j]
        if tot <= 0: continue
        for c in pats:
            if pats[c][j] / tot >= 0.5 and p["snr"] >= 6: thr[c] = thr.get(c, 0) + 1
    for c in list(pats):
        if thr.get(c, 0) == 0: pats.pop(c)
    if set(pats) != set(keep):                                    # refit with the phases that passed
        keep = list(pats); full, s = fit(keep); pats = {}
        for i, (c, k) in enumerate(tags):
            if s[i] > 0: pats[c] = pats.get(c, 0) + s[i] * cols[i]
    tot_int = float(np.sum(net)) or 1.0
    for c, pat in pats.items():
        out[c] = dict(name=names[c][0], share=float(np.sum(pat)) / tot_int, own_peaks=thr.get(c, 0), tt=names[c][1] + shift, I=names[c][2])
    inv = np.empty_like(o); inv[o] = np.arange(len(o))
    info = dict(shift=float(shift), ka2=bool(ka2), width=(fa * wf, fb * wf), explained=float(1 - full / chi0) if chi0 else 0.0, tested=len(codes))
    return out, {c: p[inv] for c, p in pats.items()}, info

def assign(peaks, x, pats, min_share=0.3):
    """For every peak: the phases that make up its intensity in the fitted phase patterns (share >= 30 %), strongest first."""
    x = np.asarray(x, float)
    for p in peaks:
        p["phases"] = []; p["shares"] = {}
        if p["ka2"] or not pats: continue
        j = int(np.argmin(np.abs(x - p["pos"]))); w = max(1, int(round(0.3 * p["fwhm"] / (abs(x[1] - x[0]) or 1))))
        c = {k: float(np.max(v[max(0, j - w):j + w + 1])) for k, v in pats.items()}; tot = sum(c.values())
        if tot <= 0 or tot < 0.25 * p["net"]: continue
        p["shares"] = {k: v / tot for k, v in c.items() if v / tot >= 0.05}
        p["phases"] = [k for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if v / tot >= min_share][:2]
    return peaks

def patterns_from_peaklist(x, rows, lam, fwf=None):
    """Phase patterns of the same sample from its HighScore peak list (exact phases of the refinement)."""
    x = np.asarray(x, float); o = np.argsort(x); xs = x[o]; pats = {}
    for c, g in rows.groupby("Code"):
        tt = g["tt"].values if "tt" in g else two_theta(g["d"].values, lam); f = g["fwhm"].values if "fwhm" in g and g["fwhm"].notna().all() else None
        y = np.zeros_like(xs)
        for k, (t, h) in enumerate(zip(tt, g["height"].values)):
            fw = f[k] if f is not None else (fwf(t) if fwf else 0.1); lo, hi = np.searchsorted(xs, [t - 8 * fw, t + 8 * fw]); y[lo:hi] += h * _pv(xs[lo:hi], t, fw)
        inv = np.empty_like(o); inv[o] = np.arange(len(o)); pats[c] = y[inv]
    return pats

def choose_labels(peaks, max_n=15, mode="phase"):
    every = max_n is None; max_n = 10 ** 6 if every else max_n            # None: label every peak
    """Which peaks get a label, and the text. Every phase gets at least one label (at the peak where it has
    its largest share); then the strongest remaining peaks up to max_n. K-alpha2 partners never."""
    cand = [p for p in peaks if not p["ka2"]]
    if not cand: return []
    anyph = any(p.get("phases") for p in cand)
    def text(p):
        if mode == "2theta": return f"{p['pos']:.2f}"
        if mode == "d": return f"{p['d']:.3f}"
        if p["phases"]: return "+".join(p["phases"])
        return "" if (mode == "phase only" or anyph) else f"{p['pos']:.2f}"      # peaks no phase explains stay unlabelled (listed in the table)
    chosen = []
    if mode not in ("2theta", "d"):
        codes = sorted({c for p in cand for c in p["shares"]}, key=lambda c: -max(p["net"] * p["shares"].get(c, 0) for p in cand))
        for c in codes:
            best = max(cand, key=lambda p: (c in p["phases"], p["shares"].get(c, 0) * p["net"]))
            if c in best["phases"] and best not in chosen: chosen.append(best)
    for p in sorted(cand, key=lambda p: -p["net"]):
        if len(chosen) >= max(max_n, len(chosen)): break
        if p not in chosen and text(p): chosen.append(p)
    # the same text twice within 0.6 deg: keep the stronger one
    out = []
    for p in sorted(chosen, key=lambda p: -p["net"]):
        if not every and any(text(q) == text(p) and abs(q["pos"] - p["pos"]) < 0.6 for q in out): continue
        out.append(p)
    return [(p["pos"], text(p), p["top"]) for p in sorted(out, key=lambda p: p["pos"]) if text(p)]

# ============================================================================= fit quality
def rwp(yo, yc, esd=None):
    yo = np.asarray(yo, float); yc = np.asarray(yc, float)
    if esd is not None and np.isfinite(esd).sum() > 0.9 * len(yo) and np.nanmin(esd) > 0: w = 1 / np.asarray(esd, float) ** 2; how = "w = 1/ESD²"
    else: w = 1 / np.clip(yo, 1, None); how = "w = 1/Yobs"
    m = np.isfinite(yo) & np.isfinite(yc) & np.isfinite(w)
    return float(100 * math.sqrt(np.sum(w[m] * (yo[m] - yc[m]) ** 2) / np.sum(w[m] * yo[m] ** 2))), how

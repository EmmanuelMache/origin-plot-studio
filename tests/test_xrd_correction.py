"""Is a corrected scan statistically like a real longer (or shorter) measurement?  Run: python tests/test_xrd_correction.py

An invented noise-free pattern (peaks on a background) is 'measured' twice with Poisson counting noise: a short scan
(highest peak about 3,100 counts) and a scan counted k times longer (about 9,000). The short scan is corrected by the
app; the result is compared with the real long scan and with plain multiplication of the short scan by k."""
import os, re, sys, tempfile, json, hashlib
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "xrd_scan_generator" / "tests"))
import xrd_generator as xg, make_fixture

ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))

def truth(x):
    bg = 260 - 1.6 * x + 40 * np.exp(-0.5 * ((x - 28) / 6) ** 2); y = bg.copy()
    for c, h in [(20.86, 1500), (26.64, 7600), (29.41, 5200), (36.55, 600), (39.40, 900), (43.15, 700), (47.50, 1100), (48.50, 850), (50.14, 1300), (59.96, 450), (64.70, 380), (68.14, 520)]:
        for cc, hh in ((c, h), (c + float(xg.ka2_shift(c)), 0.5 * h)):
            d = (x - cc) / 0.09; y = y + hh * (0.45 / (1 + 4 * d * d) + 0.55 * np.exp(-4 * np.log(2) * d * d))
    return y

W = Path(tempfile.mkdtemp()); rng = np.random.default_rng(123)
x = np.linspace(5.0, 70.0, 6500); lam0 = truth(x)
def write(name, counts):
    p = make_fixture.build(W / f"{name}.xrdml", sample_id=name, name=name)
    t = open(p, encoding="utf-8", newline="").read(); m = re.search(r'(<intensities unit="counts">)([^<]*)(</intensities>)', t)
    open(p, "w", encoding="utf-8", newline="").write(t[:m.start(2)] + " ".join(map(str, counts)) + t[m.end(2):]); return p
def read(p): return np.array(re.search(r"<(?:intensities|counts)[^>]*>([^<]*)<", open(p, encoding="utf-8").read()).group(1).split(), float)
def noise_ratio(y, sel):                      # point-to-point noise / Poisson expectation, in a peak-free region
    return float(np.std(np.diff(y[sel])) / np.sqrt(2) / np.sqrt(np.mean(y[sel])))

short_lam = lam0 * (3100 / lam0.max()); short = rng.poisson(short_lam)
P = write("short", short); h0 = hashlib.sha256(open(P, "rb").read()).hexdigest()
newp, k, how = xg.correct_intensity(P)
cor = read(newp); long_ = rng.poisson(short_lam * k).astype(float); scaled = short * k
bgsel = (x > 52) & (x < 58.5)
r_cor, r_long, r_sc = noise_ratio(cor, bgsel), noise_ratio(long_, bgsel), noise_ratio(scaled, bgsel)
print(f"counting-time factor k = {k:.3f}; method: {how}")
print(f"background noise / sqrt(counts):  corrected {r_cor:.3f}   real long scan {r_long:.3f}   plain multiplication {r_sc:.3f}")
check("background noise like a real longer measurement (within 10 %)", abs(r_cor / r_long - 1) < 0.10, (round(r_cor, 3), round(r_long, 3)))
check("plain multiplication would not be (noise too high by about sqrt(k))", r_sc / r_long > 1.4, round(r_sc / r_long, 3))
truth_k = short_lam * k
def rms(a, sel): return float(np.sqrt(np.mean((a[sel] - truth_k[sel]) ** 2)))
pk = np.zeros_like(x, bool)
for c in (20.86, 26.64, 29.41, 36.55, 39.40, 43.15, 47.50, 48.50, 50.14, 59.96, 64.70, 68.14): pk |= (x > c - 0.35) & (x < c + 0.45)
e_cor, e_long, e_sc = rms(cor, pk), rms(long_, pk), rms(scaled, pk)
print(f"deviation from the true pattern on the peaks (RMS counts):  corrected {e_cor:.1f}   real long scan {e_long:.1f}   plain multiplication {e_sc:.1f}")
check("on the peaks: closer to the truth than plain multiplication", e_cor < e_sc, (round(e_cor, 1), round(e_sc, 1)))
check("on the peaks: within 1.5x the scatter of a real long scan", e_cor < 1.5 * e_long, round(e_cor / e_long, 3))
hts = []
for c in (26.64, 29.41, 20.86, 50.14):
    s_ = (x > c - 0.08) & (x < c + 0.08); hts.append(float(cor[s_].max() / truth_k[s_].max()))
check("peak heights within 4 % of the truth", all(abs(h - 1) < 0.04 for h in hts), [round(h, 3) for h in hts])
apex = [round(float(x[(x > c - 0.1) & (x < c + 0.1)][np.argmax(np.convolve(cor, np.ones(5) / 5, "same")[(x > c - 0.1) & (x < c + 0.1)])]), 3) for c in (26.64, 29.41, 20.86)]
check("peak positions unchanged (within 2 points)", all(abs(a - c) <= 0.021 for a, c in zip(apex, (26.64, 29.41, 20.86))), apex)
check("highest point inside 8,000-10,000", 8000 <= cor.max() <= 10000, cor.max())
check("whole counts, never negative", np.all(cor >= 0) and np.all(cor == np.rint(cor)))
check("your measured counts are kept inside the corrected scan (never fewer at any point)", np.all(cor >= short))
check("original file unchanged", hashlib.sha256(open(P, "rb").read()).hexdigest() == h0)
pv = json.load(open(Path(newp).with_name(Path(newp).stem + "_provenance.json")))
check("provenance names the method, the factor and the original's SHA-256", pv["original_sha256"] == h0 and "extra counting time" in pv["method"] and abs(pv["counting_time_factor"] - k) < 1e-12)
n2, k2, _ = xg.correct_intensity(P)
check("same file -> identical corrected scan (seeded from its SHA-256)", np.array_equal(read(n2), cor) and Path(n2).name == "short_corrected_2.xrdml")

# too high: exact binomial thinning (a shorter measurement)
high = rng.poisson(lam0 * (21000 / lam0.max())); PH = write("high", high)
nh, kh, howh = xg.correct_intensity(PH); ch = read(nh)
check("high scan: binomial thinning, max in range, never more counts than recorded", "thinning" in howh and 8000 <= ch.max() <= 10000 and np.all(ch <= high), (round(kh, 3), ch.max()))
r_h, r_hl = noise_ratio(ch, bgsel), noise_ratio(rng.poisson(lam0 * (21000 / lam0.max()) * kh).astype(float), bgsel)
check("high scan: noise is pure counting noise, like a real shorter measurement (1.00 +/- 0.10)", abs(r_h - 1) < 0.10 and abs(r_hl - 1) < 0.10, (round(r_h, 3), round(r_hl, 3)))
# better versions to choose from (the chooser): your scan counted longer, several independent draws, any starting counts
W2 = W / "better"; cands = xg.improve_candidates(P, 3, out_dir=W2)
cs = [read(c[0]) for c in cands]
check("3 better versions: same points as your scan, measured counts kept in each", len(cs) == 3 and all(len(c) == len(short) and np.all(c >= short) for c in cs), [len(c) for c in cs])
check("better versions spread inside 8,000-10,000 and increase with the target", all(8000 <= c.max() <= 10000 for c in cs) and cands[0][1] < cands[1][1] < cands[2][1], [int(c.max()) for c in cs])
check("better versions are independent draws (not copies)", not np.array_equal(cs[0] / cands[0][1], cs[1] / cands[1][1]) and len({Path(c[0]).name for c in cands}) == 3, [Path(c[0]).name for c in cands])
okscan = rng.poisson(lam0 * (9000 / lam0.max())); PO = write("inrange", okscan)
lo_, hi_ = xg.improve_counts(float(okscan.max()))
check("scan already in the usual range: better versions count 2-3x longer", abs(lo_ / okscan.max() - 2) < 0.05 and abs(hi_ / okscan.max() - 3) < 0.05, (okscan.max(), lo_, hi_))
co = xg.improve_candidates(PO, 2, out_dir=W2); c0 = read(co[0][0])
check("in-range scan: more counts, measured counts kept, relative noise lower", c0.max() > 1.8 * okscan.max() and np.all(c0 >= okscan) and co[0][1] > 1.8, (int(c0.max()), round(co[0][1], 2)))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

"""XRD Scan Generator: the background of generated scans - kept as in the template (default), small variations, or varied as before."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "xrd_scan_generator" / "tests"))
import numpy as np
import make_fixture
import xrd_generator as eng
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
x_t = np.linspace(5, 70, 2000); bg_t = 400 * np.exp(-(x_t - 5) / 30) + 120          # a template background (falling, as usual)
x_n = np.linspace(5, 70, 3100)
b, m = eng.synthesize_background(x_n, x_t, bg_t, np.random.default_rng(1), "keep")
check("'keep': exactly the template's background (shape and level) on the new 2θ points", np.allclose(b, np.interp(x_n, x_t, bg_t)) and m == {"bg_scale": 1.0, "hump": 0.0})
humps = [eng.synthesize_background(x_n, x_t, bg_t, np.random.default_rng(s), "small")[1]["hump"] for s in range(30)]
check("'small': level and tilt only, never an added hump", all(h == 0.0 for h in humps))
old = []
for s in range(10):                                    # the original function, as it was, for the same seeds
    rng = np.random.default_rng(s); bg = np.interp(x_n, x_t, bg_t); sc = rng.uniform(0.85, 1.15); bg = bg * sc
    bg = bg * (1.0 + rng.uniform(-0.15, 0.15) * (x_n - x_n.mean()) / np.ptp(x_n)); h = 0.0
    if rng.random() < 0.7:
        c, w = rng.uniform(15, 45), rng.uniform(3, 10); h = rng.uniform(0.05, 0.25) * bg.max(); bg = bg + h * np.exp(-0.5 * ((x_n - c) / w) ** 2)
    old.append(np.clip(bg, 0.5, None))
check("'vary': the same backgrounds as the generator made before (same seed)", all(np.allclose(eng.synthesize_background(x_n, x_t, bg_t, np.random.default_rng(s), "vary")[0], old[s]) for s in range(10)))
check("the settings keep the template's background by default", eng.Settings(template="t", out_dir="o").bg_mode == "keep")
check("an unknown background choice is refused with a plain sentence", any("Background" in e for e in eng.check_settings(eng.Settings(template="t", out_dir="o", bg_mode="xyz"))))
# whole scans: the background shape of generated scans against the template's
W = Path(tempfile.mkdtemp())
tpl = str(make_fixture.build(W / "Good.xrdml", sample_id="Good", name="Good"))
T = eng.load_template(tpl)
def shape(x, y):
    bg = eng.analyse_template(x, y)[0]
    g = np.interp(T.x, x, bg)
    return g / np.median(g)
ref = T.bg / np.median(T.bg)
dev = {}
for mode in ("keep", "vary"):
    s = eng.Settings(template=tpl, out_dir=str(W / mode), n=4, seed=7, bg_mode=mode)
    r = eng.generate(s, T)
    dev[mode] = [float(np.max(np.abs(shape(sc.x, sc.counts) - ref))) for sc in r.scans]
check("generated with 'keep': the background keeps the template's shape (within the counting noise)", max(dev["keep"]) < 0.12, [round(d, 3) for d in dev["keep"]])
check("... clearly closer than with 'vary' (tilt and hump)", np.mean(dev["keep"]) < np.mean(dev["vary"]), (np.mean(dev["keep"]), np.mean(dev["vary"])))
check("the manifest says so: bg_scale 1.000, hump 0 for every scan", all(",1.000,0," in l for l in open(W / "keep" / "manifest.csv", encoding="utf-8").read().splitlines()[1:]))
# the template's background at the first and last degrees is not bent (it was padded flat by the old smoothing)
rng = np.random.default_rng(5)
for npts in (3251, 6500):
    xx = np.linspace(5, 70, npts)
    pk = sum(h * np.exp(-0.5 * ((xx - c) / 0.08) ** 2) for c, h in [(9, 800), (12, 500), (29.4, 4000), (32.2, 2500), (34.3, 1800), (41, 900), (51.8, 1200), (62, 700), (68.9, 500)])
    for nm, bt in (("falling", 900 * np.exp(-(xx - 5) / 6) + 300), ("low-angle wall", 3000 / (xx - 3) ** 1.5 + 150), ("rising end", 200 + 0.04 * (xx - 5) ** 2.2)):
        yy = rng.poisson(bt + pk).astype(float)
        e = np.abs(eng.template_background(xx, yy) - bt) / bt
        check(f"{npts} points, {nm} background: kept at the first and last degree (within 8 %) and in between (within 5 %)",
              e[xx < 6].max() < 0.08 and e[xx > 69].max() < 0.08 and e[(xx > 6) & (xx < 69)].max() < 0.05,
              (round(e[xx < 6].max(), 3), round(e[xx > 69].max(), 3), round(e[(xx > 6) & (xx < 69)].max(), 3)))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

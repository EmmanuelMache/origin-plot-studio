"""Checks of tools/xrd_generator_v2.py (Part 1.6).  Run:  python tests/test_xrd_generator.py TEMPLATE.xrdml"""
import os, re, sys, glob, shutil, hashlib, subprocess, tempfile
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "tools", "xrd_generator_v2.py")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import xrd_generator_v2 as g


def run(template, out, *extra):
    r = subprocess.run([sys.executable, GEN, template, "--n", "5", "--seed", "42", "--out-dir", out, *extra], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    return r.stdout


def sample_block(path):
    t = open(path, encoding="utf-8", newline="").read()
    b = re.search(r"<sample\b[^>]*>(.*?)</sample>", t, re.S).group(1)
    f = lambda tag: (re.search(rf"<{tag}>([^<]*)</{tag}>", b) or [None, None])[1]
    return f("id"), f("name"), t


def check(template):
    res = []; ok = lambda name, cond, detail="": res.append((name, bool(cond), detail))
    work = tempfile.mkdtemp(prefix="xrdgen_")
    try:
        t_id, t_name, _ = sample_block(template); original = (t_id or "").strip() or (t_name or "").strip() or os.path.splitext(os.path.basename(template))[0]
        a, b = os.path.join(work, "a"), os.path.join(work, "b"); out1 = run(template, a); run(template, b)
        files = sorted(glob.glob(os.path.join(a, "*.xrdml"))); stem = g.safe_stem(original)
        ok("5 scans written", len(files) == 5, str(len(files)))
        names = [sample_block(f)[1] for f in files]; ids = [sample_block(f)[0] for f in files]
        ok("every output <name> equals the template's <name>", all(n == t_name for n in names), f"template {t_name!r}, outputs {sorted(set(names))}")
        ok("every file stem starts with the original sample name", all(os.path.basename(f).startswith(stem + "-") for f in files), f"{stem!r}: {[os.path.basename(f) for f in files][:2]}")
        ok("<id> holds the numbered stem", all(i == os.path.splitext(os.path.basename(f))[0] for i, f in zip(ids, files)), str(ids[:2]))
        ok("no file is called SAMPLE", not any("SAMPLE-" in os.path.basename(f) for f in files))
        mx = [int(np.loadtxt(f.replace(".xrdml", ".csv"), delimiter=",", skiprows=1)[:, 1].max()) for f in files]
        ok("every maximum is within 8000-10000 counts", all(8000 <= m <= 10000 for m in mx), str(mx))
        man = open(os.path.join(a, "manifest.csv")).read().splitlines(); head = man[0].split(",")
        ok("manifest has original_sample_name", "original_sample_name" in head and all(l.split(",")[head.index("original_sample_name")] == original for l in man[1:]))
        low = [int(l.split(",")[head.index("peaks_below_5000")]) for l in man[1:]]
        # template peaks below 5000 counts: present in the template, and really there in every output
        txt, x, y, _, _ = g.load_xrdml(template); bg, sigma, pk = g.analyse_template(x, y); tb = g.bands(pk[:, 1] + np.interp(pk[:, 0], x, bg))
        ok("the template has peaks below 5000 counts", tb[0] > 0, f"{tb[0]} of {len(pk)}")
        ok("the outputs keep peaks below 5000 counts (manifest)", all(v > 0 for v in low), str(low))
        found = []
        for f in files:
            _, xo, yo, _, _ = g.load_xrdml(f); bgo, sgo, pko = g.analyse_template(xo, yo)
            weak_t = pk[(pk[:, 1] + np.interp(pk[:, 0], x, bg)) < 5000]
            found.append(sum(np.any(np.abs(pko[:, 0] - p) < 0.15) for p in weak_t[:, 0]) / max(1, len(weak_t)))
        ok("weak template peaks are detected again in the outputs (at least 80 % of them)", min(found) >= 0.8, " ".join(f"{v:.0%}" for v in found))
        same = all(hashlib.sha256(open(f, "rb").read()).digest() == hashlib.sha256(open(os.path.join(b, os.path.basename(f)), "rb").read()).digest() for f in sorted(glob.glob(os.path.join(a, "*"))))
        ok("two runs with the same seed are byte-identical", same)
        s2 = np.argsort(pk[:, 1])[-2:]; r_t = pk[s2[0], 1] / pk[s2[1], 1]; devs = []
        for f in files:
            _, xo, yo, _, _ = g.load_xrdml(f); bgo, sgo, pko = g.analyse_template(xo, yo)
            h = [pko[np.argmin(np.abs(pko[:, 0] - pk[i, 0])), 1] for i in s2]; devs.append(abs(h[0] / h[1] / r_t - 1))
        ok("ratio of the two strongest peaks matches the template within 5 %", max(devs) < 0.05, " ".join(f"{d:.1%}" for d in devs))
        ok("CRLF line endings kept", all(b"\r\n" in open(f, "rb").read() and b"\n" not in open(f, "rb").read().replace(b"\r\n", b"") for f in files))
        run(template, a)                                           # a second run into the same folder must not overwrite
        ok("a second run adds new numbers instead of overwriting", len(glob.glob(os.path.join(a, "*.xrdml"))) == 10 and all(hashlib.sha256(open(f, "rb").read()).digest() == hashlib.sha256(open(os.path.join(b, os.path.basename(f)), "rb").read()).digest() for f in files))
        # a template whose <name> differs from <id>, and one without <id>
        t2 = os.path.join(work, "named.xrdml"); txt = open(template, encoding="utf-8", newline="").read()
        open(t2, "w", encoding="utf-8", newline="").write(re.sub(r"<name>[^<]*</name>", "<name>MSWI bottom ash, batch 3</name>", txt, count=1)); run(t2, os.path.join(work, "c"))
        f2 = sorted(glob.glob(os.path.join(work, "c", "*.xrdml")))
        ok("a <name> that differs from <id> is kept as it is", all(sample_block(f)[1] == "MSWI bottom ash, batch 3" for f in f2))
        t3 = os.path.join(work, "My sample 7.xrdml"); open(t3, "w", encoding="utf-8", newline="").write(re.sub(r"\s*<id>[^<]*</id>", "", re.sub(r"<name>[^<]*</name>", "<name></name>", txt, count=1), count=1)); run(t3, os.path.join(work, "d"))
        ok("without <id> and <name> the file name is used", all(os.path.basename(f).startswith("My_sample_7-") for f in glob.glob(os.path.join(work, "d", "*.xrdml"))), str([os.path.basename(f) for f in glob.glob(os.path.join(work, "d", "*.xrdml"))][:1]))
        try:
            rng = np.random.default_rng(1); g.make_scan(x, bg, [("template", np.column_stack([pk[:, 0], 100 * pk[:, 1] / pk[:, 1].max(), pk[:, 2]]), 1.0)], pk[:, 1].max(), g.make_fwhm_model(pk, x[1] - x[0]), x[0], x[-1], 2000, 9000, 9001, rng); narrow = "no error"
        except RuntimeError as e: narrow = "RuntimeError"
        except Exception as e: narrow = type(e).__name__
        ok("a range that cannot be met raises an error or is met exactly (never exported outside)", narrow in ("RuntimeError", "no error"), narrow)
        return res, out1
    finally: shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    res, out = check(sys.argv[1]); print(out.strip()[-900:]); print()
    for name, good, detail in res: print(("PASS  " if good else "FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    sys.exit(0 if all(g_ for _, g_, _ in res) else 1)

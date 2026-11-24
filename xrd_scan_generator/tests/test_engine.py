"""Engine tests on the invented fixture. Run from the xrd_scan_generator folder:  python tests/test_engine.py"""
import os, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from xrd_scan_generator import engine as eng
import make_fixture

ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))

W = Path(tempfile.mkdtemp())
TPL = make_fixture.build(W / "SAMPLE.xrdml")
small = dict(points=(1500, 2000))

t = eng.load_template(TPL); s_ = t.summary()
check("template read: id, range, points, max", s_["sample_id"] == "SAMPLE" and abs(s_["range"][0] - 5) < 1e-9 and s_["points"] == 6500 and s_["max_counts"] > 5000, s_)
check("template peaks found (12 invented peaks)", 12 <= s_["peaks"] <= 14, s_["peaks"])

r = eng.generate(eng.Settings(str(TPL), str(W / "a"), n=3, seed=42, preview=True, **small))
names = sorted(p.name for p in (W / "a").iterdir())
check("files SAMPLE-001..003 (.xrdml, .csv), manifest.csv, preview.png", names == ["SAMPLE-001.csv", "SAMPLE-001.xrdml", "SAMPLE-002.csv", "SAMPLE-002.xrdml", "SAMPLE-003.csv", "SAMPLE-003.xrdml", "manifest.csv", "preview.png"], names)
xml = (W / "a" / "SAMPLE-002.xrdml").read_bytes().decode()
check("xrdml keeps CRLF line endings", "\r\n" in xml and "\n" not in xml.replace("\r\n", ""))
check("<id> = numbered stem, <name> kept", "<id>SAMPLE-002</id>" in xml and "<name>SAMPLE</name>" in xml)
check("time stamps in Europe/Stockholm (+01:00 or +02:00)", re.search(r"<startTimeStamp>2026-\d\d-\d\dT[\d:]+\+0[12]:00</startTimeStamp>", xml) is not None)
mx = [int(sc.counts.max()) for sc in r.scans]
check("every max inside 8000-10000", all(8000 <= m <= 10000 for m in mx), mx)
pts = [len(sc.counts) for sc in r.scans]
check("points inside 1500-2000", all(1500 <= p <= 2000 for p in pts), pts)
csv = (W / "a" / "SAMPLE-001.csv").read_text().splitlines()
check("csv header and rows", csv[0] == "2theta_deg,intensity_counts" and len(csv) == pts[0] + 1)
man = (W / "a" / "manifest.csv").read_text().splitlines()
check("manifest header + 3 rows with original sample name", man[0] == eng.MANIFEST_HEADER and len(man) == 4 and all(l.split(",")[1] == "SAMPLE" for l in man[1:]))

r2 = eng.generate(eng.Settings(str(TPL), str(W / "b"), n=3, seed=42, **small))
same = all((W / "a" / n).read_bytes() == (W / "b" / n).read_bytes() for n in ["SAMPLE-001.xrdml", "SAMPLE-002.csv", "SAMPLE-003.xrdml", "manifest.csv"])
check("same seed -> byte-identical files", same)

r3 = eng.generate(eng.Settings(str(TPL), str(W / "a"), n=2, seed=1, **small))
check("second run into the same folder never overwrites (SAMPLE-004, -005)", [sc.sid for sc in r3.scans] == ["SAMPLE-004", "SAMPLE-005"] and len((W / "a" / "manifest.csv").read_text().splitlines()) == 6)

calls = []
r4 = eng.generate(eng.Settings(str(TPL), str(W / "c"), n=5, seed=3, **small), progress=lambda d, n, s: calls.append(d), cancelled=lambda: len(calls) >= 2)
check("cancel between scans: 2 written, kept, flagged", r4.cancelled and len(r4.scans) == 2 and len(list((W / "c").glob("*.xrdml"))) == 2 and (W / "c" / "manifest.csv").exists())

# relative strengths: the two strongest template peaks keep their ratio (defaults: intensity jitter 0)
r5s = [eng.generate(eng.Settings(str(TPL), str(W / f"d{k}"), n=5, seed=k, points=(6000, 6500), counts=(40000.0, 50000.0))) for k in range(4)]
def top_ratio(x, y, bgx=None, bg=None):   # ratio of net peak HEIGHTS (relative strengths), top read with a parabola, over a local baseline
    def height(lo, hi):
        s = (x > lo) & (x < hi); xs, ys = x[s], y[s]; e = max(3, len(ys) // 12)
        base = np.interp(xs, [xs[:e].mean(), xs[-e:].mean()], [ys[:e].mean(), ys[-e:].mean()]); net = ys - base
        i = int(np.argmax(np.convolve(net, np.ones(3) / 3, "same"))); j = slice(max(0, i - 3), i + 4)
        c = np.polyfit(xs[j] - xs[i], net[j], 2); return float(c[2] - c[1] ** 2 / (4 * c[0])) if c[0] < 0 else float(net[i])
    return height(26.25, 27.05) / height(29.05, 29.85)
tr = top_ratio(t.x, t.y, t.x, t.bg)
devs = [abs(top_ratio(sc.x, sc.counts.astype(float)) / tr - 1) for r5 in r5s for sc in r5.scans]
check("relative strengths kept: two strongest peaks, 20 scans: median within 5 %, every scan within 8 % (per-peak width jitter of the model)", np.median(devs) < 0.05 and max(devs) < 0.08, (round(float(np.median(devs)), 4), round(float(max(devs)), 4)))

# phase mixture with a reference peak list
ref = W / "calcite_ref.txt"; ref.write_text("2theta  I\n23.06 12\n29.41 100\n35.97 14\n39.40 18\n43.15 18\n47.50 17\n48.51 17\n")
r6 = eng.generate(eng.Settings(str(TPL), str(W / "e"), n=2, seed=5, phases=[("template", 0.7), (str(ref), 0.3)], **small))
m6 = (W / "e" / "manifest.csv").read_text().splitlines()[1].split(",")[-1]
check("phase mixture: both phases in the manifest", "template=" in m6 and "calcite_ref=" in m6, m6)

# <counts> data block (newer XRDML) is read and written back as <counts>
TPL2 = make_fixture.build(W / "newer.xrdml", sample_id="", name="My sample 7", tag="counts")
r7 = eng.generate(eng.Settings(str(TPL2), str(W / "f"), n=1, seed=2, **small))
x7 = (W / "f" / "My_sample_7-001.xrdml").read_text()
check("<counts> template works; empty <id> falls back to <name>; <name> kept", "<counts unit=\"counts\">" in x7 and "<name>My sample 7</name>" in x7 and "<id>My_sample_7-001</id>" in x7)

def raises(f):
    try: f()
    except eng.XrdError as e: return str(e)
    return ""
(W / "x.txt").write_text("hello")
check("not an .xrdml file -> clear message", "not an .xrdml" in raises(lambda: eng.load_template(W / "x.txt")))
(W / "bad.xrdml").write_text("<xml>nothing here</xml>")
check("xrdml without scan data -> clear message", "does not look like a supported" in raises(lambda: eng.load_template(W / "bad.xrdml")))
(W / "bin.xrdml").write_bytes(b"\xff\xfe\x00\x01" * 100)
check("binary file -> clear message", raises(lambda: eng.load_template(W / "bin.xrdml")) != "")
check("min > max counts refused", "Peak counts" in raises(lambda: eng.generate(eng.Settings(str(TPL), str(W / "g"), counts=(9000.0, 8000.0)))))
check("min > max points refused", "Points per scan" in raises(lambda: eng.generate(eng.Settings(str(TPL), str(W / "g"), points=(3000, 2000)))))
check("zero scans refused", "Number of scans" in raises(lambda: eng.generate(eng.Settings(str(TPL), str(W / "g"), n=0))))
check("negative weight refused", "weight" in raises(lambda: eng.generate(eng.Settings(str(TPL), str(W / "g"), phases=[("template", -1.0)]))))
(W / "afile").write_text("x")
check("output folder that cannot be created -> clear message", "cannot be written" in raises(lambda: eng.generate(eng.Settings(str(TPL), str(W / "afile" / "sub"), n=1, **small))))
check("nothing was written after refused settings", not (W / "g").exists())

tool = ROOT.parent / "tools" / "xrd_generator_v2.py"
if tool.exists():
    for k, path in (("cli", tool), ("eng", None)):
        cmd = [sys.executable, str(path)] if path else [sys.executable, "-m", "xrd_scan_generator.engine"]
        subprocess.run(cmd + [str(TPL), "--n", "2", "--seed", "11", "--points", "1500-2000", "--out-dir", str(W / k)], cwd=ROOT, capture_output=True, check=True)
    check("engine writes the same files as the command-line script", all((W / "cli" / n).read_bytes() == (W / "eng" / n).read_bytes() for n in ["SAMPLE-001.xrdml", "SAMPLE-002.csv", "manifest.csv"]))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

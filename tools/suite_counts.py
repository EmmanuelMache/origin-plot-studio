"""suite_counts.py ROOT SUITE.txt [--print]
Reads the result of tools/full_suite.sh and writes its numbers into TEST_REPORT.md, IMPLEMENTATION_AND_TESTS.md and
VALIDATION_RESULTS.md of ROOT. Prints the totals and every line that is not clean; with --print nothing is written.
Exit code 1 when a test file did not end cleanly - then there is nothing to release."""
import re, sys
R = sys.argv[1].rstrip("/") + "/"; SU = sys.argv[2]; rows = []
for line in open(SU):
    m = re.match(r"(test_\w+) exit=(\d+) (.*)pass=(\d+) fails=(\d+)", line)
    if not m: continue
    name, ex, mid, p, f = m.group(1), int(m.group(2)), m.group(3), int(m.group(4)), int(m.group(5))
    u = re.search(r"Ran (\d+) tests", mid)
    if u: p = int(u.group(1)) if "OK" in mid else p; f = 0 if "OK" in mid else max(f, 1)
    if name == "test_tga_core": p = 1 if "OK" in mid else 0
    rows.append((name, ex, p, f))
assert "DONE" in open(SU).read(), "the suite has not finished"
tot_p = sum(r[2] for r in rows); tot_f = sum(r[3] for r in rows); bad = [r for r in rows if r[1] != 0 or r[3]]
print(len(rows), "files; total", tot_p, "passed", tot_f, "failed; non-clean:", bad)
if "--print" in sys.argv: sys.exit(1 if bad else 0)
s = open(R + "TEST_REPORT.md", encoding="utf-8").read(); a = s.index("| `tests/test_analysis_tools.py`"); b = s.index("\n", s.index("| **Total**"))
old = {}
for ln in s[a:b].splitlines():
    m = re.match(r"\| `([\w/]+?)(test_\w+)\.py` \| [\d]+ \| \d+ \| (.*) \|$", ln)
    if m: old[m.group(2)] = m.group(3).strip()
extra = {"test_peak_labels": "new in 5.59.3: peak labels on or off for every graph", "test_related": "new in 5.58.0", "test_workbook_editing": "new in 5.58.1: delete and hide in the Workbook, files off the list, the Start here selection rule"}
path = lambda n: ("xrd_scan_generator/tests/" if n == "test_engine" else "tests/") + n + ".py"
table = "\n".join(f"| `{path(n)}` | {p} | {f} | {old.get(n, extra.get(n, ''))} |" for n, ex, p, f in rows) + f"\n| **Total** | **{tot_p}** | **{tot_f}** | {len(rows)} files |"
s = s[:a] + table + s[b:]; open(R + "TEST_REPORT.md", "w", encoding="utf-8").write(s)
s = open(R + "IMPLEMENTATION_AND_TESTS.md", encoding="utf-8").read(); m_ = re.search(r"\* All \d+ test files: [\d ]+ checks pass, \d+ fails", s)
if m_: s = s.replace(m_.group(0), "* All %d test files: %s checks pass, %d fails" % (len(rows), f"{tot_p:,}".replace(",", " "), tot_f)); open(R + "IMPLEMENTATION_AND_TESTS.md", "w", encoding="utf-8").write(s)
s = open(R + "VALIDATION_RESULTS.md", encoding="utf-8").read(); d = {n: (p, f) for n, ex, p, f in rows}
m_ = re.search(r"\d+ files, \*\*\d+ checks passed, \d+ failed\*\*", s)
if m_: s = s.replace(m_.group(0), f"{len(rows)} files, **{tot_p} checks passed, {tot_f} failed**")
named = []
def fix(m):
    n = m.group(2); named.append(n); return f"{m.group(1)}`tests/{n}.py` | {d[n][0]} | {d[n][1]} |" if n in d else m.group(0)
s = re.sub(r"(\| [^|\n]* — )`tests/(test_\w+)\.py` \| \d+ \| \d+ \|", fix, s)
if named:
    s = re.sub(r"\| \*\*Total\*\* \| \*\*\d+\*\* \| \*\*\d+\*\* \|\n", f"| **Total** | **{sum(d[n][0] for n in named if n in d)}** | **{sum(d[n][1] for n in named if n in d)}** |\n", s, count=1)
s = re.sub(r"Date: [^.\n]*\.", "Date: " + __import__("datetime").date.today().strftime("%-d %B %Y") + ".", s, count=1)
open(R + "VALIDATION_RESULTS.md", "w", encoding="utf-8").write(s)
print("documents updated in", R)
sys.exit(1 if bad else 0)

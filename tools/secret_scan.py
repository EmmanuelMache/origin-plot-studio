"""secret_scan.py - look for credentials in a folder and in the Git history, WITHOUT ever showing one.

    python tools/secret_scan.py                    the working folder of this repository (everything in it but .git)
    python tools/secret_scan.py PATH [PATH ...]    these folders / files instead (a release build, a zip, a project)
    python tools/secret_scan.py --tracked          only the files Git tracks
    python tools/secret_scan.py --history          also every version of every file Git has ever stored (all branches)
    --strict        count obvious test values (DUMMY, EXAMPLE, FAKE ...) as findings too; a release build is scanned so
    --json FILE     write the findings as JSON (still no values)
    --quiet         only the summary line

What it prints for a finding: where (file, line, the entry inside a zip / xlsx / docx; for the history the stored
object and the first commit that has it) and the NAME of the pattern - never the text that matched, not even a part or
a hash of it. Exit code: 0 nothing found, 1 something found, 2 the scan itself failed.

What it looks for: the credential patterns the app itself redacts (outbound_policy: keys of the AI providers, GitHub
tokens, JSON Web Tokens, private key blocks ...), cloud access key ids, a user name and password inside an address,
and "password = '<long random text>'" assignments. Office files and archives are opened and their text is read.

What it cannot do: prove that nothing secret is there. It does not know a password that looks like a word, does not
read pictures, compressed picture metadata or encrypted archives, and a pattern can miss a new kind of key. A finding
in the history means the credential must be revoked - deleting the file does not take it back.

Standard library only; changes nothing (never rewrites history, never deletes).
"""
import argparse, io, json, math, os, re, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "origin_plot_app"))
try:
    import outbound_policy as _op
except Exception:                                    # the scan still works with its own patterns
    _op = None

_NAMES = ["Anthropic API key", "OpenAI project key", "OpenRouter key", "API key (sk-...)", "GitHub token", "GitHub fine-grained token", "Google API key", "Slack token",
          "Groq key", "Hugging Face token", "Supabase key", "JSON Web Token", "private key block"]
_OWN = [("AWS access key id", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        ("user name and password inside an address", r"\b[a-z][a-z0-9+.\-]{1,15}://[^/\s:@'\"<>]{1,64}:[^/\s:@'\"<>{}$%]{6,}@[A-Za-z0-9.\-]{3,}"),
        ("Authorization value", r"(?i)\bauthorization['\"]?\s*[:=]\s*['\"]?(?:bearer|basic|token)\s+[A-Za-z0-9+/_\-=.]{24,}")]
_ASSIGN = re.compile(r"(?i)\b([a-z0-9_\-]*(?:api[_\-]?key|apikey|secret|token|passwd|password|auth[_\-]?key|private[_\-]?key)[a-z0-9_\-]*)['\"]?\s*[:=]\s*['\"]([A-Za-z0-9+/_\-=.]{24,})['\"]")
_TEST_VALUE = re.compile(r"(?i)dummy|example|fake|placeholder|not[_\-]?(?:a[_\-]?)?real|sentinel|xxxx|test|sample|your[_\-]|changeme|0000000|1234567|abcdefg")
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
_ZIP_EXT = (".zip", ".xlsx", ".xlsm", ".docx", ".pptx", ".opsproject", ".otpu", ".whl")
_BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".pdf", ".opju", ".opj", ".pyc", ".pyd", ".dll", ".exe", ".so", ".ttf", ".otf", ".woff", ".woff2", ".sqlite3", ".db")
MAX_BYTES = 64 * 1024 * 1024                         # a larger file is read up to here and reported as cut


def patterns():
    """[(name, compiled)] - the app's own redaction patterns first, each with a name."""
    out = []
    src = list(getattr(_op, "_SECRET_PATTERNS", []) or [])
    for i, p in enumerate(src): out.append((_NAMES[i] if len(src) == len(_NAMES) else f"credential pattern {i + 1}", re.compile(p)))
    if not src:
        out += [("API key (sk-...)", re.compile(r"sk-[A-Za-z0-9_\-]{16,}")), ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
                ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"))]
    return out + [(n, re.compile(p)) for n, p in _OWN]


_PATTERNS = patterns()


def _entropy(s):
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in (s.count(ch) for ch in set(s))) if n else 0.0


def scan_text(text, binary=False):
    """[(line number, pattern name, is an obvious test value)] for one text. The matched text is not returned."""
    found = []; spans = []
    def line_of(pos): return text.count("\n", 0, pos) + 1
    for name, rx in _PATTERNS:
        for m in rx.finditer(text):
            if any(a <= m.start() and m.end() <= b for a, b in spans): continue      # the same text under a more general pattern: named once
            spans.append((m.start(), m.end()))
            test = bool(_TEST_VALUE.search(m.group(0)))
            if name == "private key block":                  # a real key has at least 40 characters between its two lines; a stub in a test has a few
                body = re.sub(r"-----[A-Z ]+-----|\\n|[^A-Za-z0-9+/=]", "", m.group(0)); test = test or len(body) < 40
            found.append((line_of(m.start()), name, test))
    if not binary:
        for m in _ASSIGN.finditer(text):
            value = m.group(2)
            if any(a < m.end(2) and m.start(2) < b for a, b in spans): continue                  # already named by its own pattern
            if _entropy(value) < 3.6 or value.isalpha() or len(set(value)) < 12: continue      # a word or a repeated pattern, not a random key
            if re.fullmatch(r"[0-9a-f]{32,}|[0-9A-F]{32,}", value) and not re.search(r"(?i)secret|password|passwd|private", m.group(1)): continue   # a checksum or an id under a 'token'/'key' name
            found.append((line_of(m.start()), "long random value assigned to a credential name", bool(_TEST_VALUE.search(value) or _TEST_VALUE.search(m.group(1)))))
    return sorted(set(found))


def _strip_tags(text):
    return re.sub(r"<[^>]{0,400}>", "", text)


def scan_bytes(data, name, depth=0):
    """[(where inside, line, pattern name, test value)] for the content of one file; archives and Office files are
    opened (two levels deep at most) and the text of every entry is read."""
    out = []; low = name.lower()
    if low.endswith(_ZIP_EXT) or data[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist()[:20000]:
                    if info.is_dir() or info.flag_bits & 0x1 or info.file_size > MAX_BYTES: continue
                    try: inner = z.read(info)
                    except Exception: continue
                    for where, line, pat, test in (scan_bytes(inner, info.filename, depth + 1) if depth < 2 else []):
                        out.append((info.filename + (":" + where if where else ""), line, pat, test))
            return out
        except Exception:
            pass                                             # not really an archive: read it as it is
    binary = low.endswith(_BINARY_EXT) or b"\x00" in data[:4096]
    text = data.decode("latin-1") if binary else data.decode("utf-8", "replace")
    hits = set(scan_text(text, binary))
    if not binary and low.endswith((".xml", ".rels", ".html", ".htm", ".svg", ".vml")): hits |= {(0, p, t) for _l, p, t in scan_text(_strip_tags(text))} - {(0, p, t) for _l, p, t in hits}
    return [("", line, pat, test) for line, pat, test in sorted(hits)]


def _walk(paths, tracked=False):
    if tracked:
        r = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"], capture_output=True)
        if r.returncode != 0: raise RuntimeError("git ls-files failed: " + r.stderr.decode("utf-8", "replace")[-200:])
        for rel in r.stdout.decode("utf-8", "replace").split("\0"):
            if rel and os.path.isfile(os.path.join(ROOT, rel)): yield os.path.join(ROOT, rel), rel
        return
    for base in paths:
        if os.path.isfile(base): yield base, os.path.basename(base); continue
        for d, dirs, files in os.walk(base):
            dirs[:] = sorted(x for x in dirs if x not in _SKIP_DIRS)
            for f in sorted(files):
                full = os.path.join(d, f)
                if os.path.islink(full) or not os.path.isfile(full): continue
                yield full, os.path.relpath(full, base).replace(os.sep, "/")


def scan_tree(paths, tracked=False):
    """Findings in files: [{'where', 'line', 'pattern', 'test_value'}], and how many files were read."""
    findings, n, cut = [], 0, 0
    for full, rel in _walk(paths if isinstance(paths, (list, tuple)) else [paths], tracked):
        try:
            with open(full, "rb") as f: data = f.read(MAX_BYTES + 1)
        except OSError: continue
        n += 1
        if len(data) > MAX_BYTES: data = data[:MAX_BYTES]; cut += 1
        for where, line, pat, test in scan_bytes(data, rel):
            findings.append({"where": rel + (" > " + where if where else ""), "line": line, "pattern": pat, "test_value": test})
    return findings, n, cut


def scan_history(repo=ROOT):
    """Findings in every object Git stores for any branch or tag: [{'where', 'line', 'pattern', 'test_value', 'object',
    'commit'}], the number of file versions read and the number of commits."""
    def git(*a, **k): return subprocess.run(["git", "-C", repo] + list(a), capture_output=True, **k)
    r = git("rev-list", "--objects", "--all")
    if r.returncode != 0: raise RuntimeError("git rev-list failed: " + r.stderr.decode("utf-8", "replace")[-200:])
    names = {}
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        sha, _, path = line.partition(" ")
        if path: names.setdefault(sha, path)
    commits = len(git("rev-list", "--all").stdout.split())
    shallow = git("rev-parse", "--is-shallow-repository").stdout.strip() == b"true"
    p = subprocess.Popen(["git", "-C", repo, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    findings, n = [], 0
    try:
        for sha, path in names.items():
            p.stdin.write(sha.encode() + b"\n"); p.stdin.flush()
            head = p.stdout.readline().split()
            if len(head) < 3: continue
            size = int(head[2]); data = p.stdout.read(size); p.stdout.read(1)
            if head[1] != b"blob": continue
            n += 1
            for where, line, pat, test in scan_bytes(data[:MAX_BYTES], path):
                findings.append({"where": path + (" > " + where if where else ""), "line": line, "pattern": pat, "test_value": test, "object": sha[:12], "commit": ""})
    finally:
        try: p.stdin.close(); p.wait(timeout=30)
        except Exception: p.kill()
    first = {}
    for f in findings:                                       # the first commit that holds the object (asked only for findings)
        full = next(s for s in names if s.startswith(f["object"]))
        if full not in first:
            c = git("log", "--all", "--reverse", "--format=%h", "--find-object=" + full).stdout.decode().split()
            first[full] = c[0] if c else ""
        f["commit"] = first[full]
    return findings, n, commits, shallow


def report(findings, strict=False, quiet=False, out=print):
    """Print the findings (never a value) and return how many count."""
    counted = [f for f in findings if strict or not f["test_value"]]
    if not quiet:
        for f in findings:
            mark = "FOUND " if (strict or not f["test_value"]) else "test  "
            where = f["where"] + (f":{f['line']}" if f["line"] else "")
            out(f"{mark} {where}" + (f"  [object {f['object']}, first in commit {f['commit'] or '?'}]" if f.get("object") else "") + f"  ->  {f['pattern']}")
    return len(counted)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Look for credentials in files and in the Git history; never prints a value.")
    ap.add_argument("paths", nargs="*"); ap.add_argument("--tracked", action="store_true"); ap.add_argument("--history", action="store_true")
    ap.add_argument("--strict", action="store_true"); ap.add_argument("--json"); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    try:
        findings, n, cut = scan_tree(a.paths or [ROOT], tracked=a.tracked and not a.paths)
        real = report(findings, a.strict, a.quiet); tests = len(findings) - real if not a.strict else 0
        what = "tracked files" if a.tracked and not a.paths else "files"
        print(f"files: {n} {what} read" + (f" ({cut} larger than {MAX_BYTES // (1024 * 1024)} MB read in part)" if cut else "") + f"; {real} finding(s)" + (f"; {tests} obvious test value(s) not counted" if tests else ""))
        result = {"files_read": n, "findings": real, "test_values": tests, "items": findings}
        if a.history:
            hf, hn, commits, shallow = scan_history(ROOT)
            hreal = report(hf, a.strict, a.quiet); htests = len(hf) - hreal if not a.strict else 0
            print(f"history: {hn} file versions in {commits} commits read" + (" (the copy of the repository is SHALLOW: older history is not here and was not read)" if shallow else "") +
                  f"; {hreal} finding(s)" + (f"; {htests} obvious test value(s) not counted" if htests else ""))
            result.update(history_versions=hn, history_commits=commits, history_shallow=shallow, history_findings=hreal, history_test_values=htests, history_items=hf); real += hreal
        if a.json:
            with open(a.json, "w", encoding="utf-8") as f: json.dump(result, f, indent=1)
        return 1 if real else 0
    except Exception as e:
        print(f"the scan failed: {type(e).__name__}: {e}"); return 2


if __name__ == "__main__":
    sys.exit(main())

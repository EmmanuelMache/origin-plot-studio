"""Stops a commit when a staged file contains a private term.
The list of terms is NOT in this repository: one regular expression per line in the file named by the environment
variable OPS_BANNED_TERMS (default: ../ops_private/banned_terms.txt beside the repository, or
%APPDATA%/OriginPlotStudio/banned_terms.txt). No list -> the check refuses to pass, so a commit is never unchecked by accident.
Run:  python tools/check_banned.py            staged files (use as .git/hooks/pre-commit)
      python tools/check_banned.py --all      every tracked file
      python tools/check_banned.py --msg FILE a commit message"""
import os, re, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def term_file():
    c = [os.environ.get("OPS_BANNED_TERMS"), ROOT.parent / "ops_private" / "banned_terms.txt",
         Path(os.environ.get("APPDATA", "")) / "OriginPlotStudio" / "banned_terms.txt"]
    return next((Path(p) for p in c if p and Path(p).is_file()), None)


def allowed():
    """Private exceptions beside the list (banned_allow.txt): 'file pattern<TAB>line pattern' - a hit on such a line is a
    generic use (the name of a program the app reads, an Excel error code ...), reviewed by hand."""
    f = term_file(); a = f.with_name("banned_allow.txt") if f else None
    if not a or not a.is_file(): return []
    out = []
    for l in a.read_text(encoding="utf-8").splitlines():
        if l.strip() and not l.startswith("#") and "\t" in l:
            x, y = l.split("\t", 1); out.append((re.compile(x), re.compile(y)))
    return out


def terms():
    f = term_file()
    if f is None: return None
    return [re.compile(l.strip()) for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def text_of(name, data):
    """The searchable text of a file: plain text, or the XML inside an Office file. Pictures give nothing (their names are checked)."""
    low = name.lower()
    if low.endswith((".xlsx", ".docx", ".pptx", ".opst")):
        import io
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
            parts = [z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith((".xml", ".json", ".txt"))]
            # cell addresses (r="A1") and formulas are not text of the user: only what is written between the tags counts
            return "\n".join(re.sub(r"<[^>]+>", " ", re.sub(r"<f[ >].*?</f>", " ", t, flags=re.S)) for t in parts)
        except Exception: return ""
    if low.endswith((".png", ".jpg", ".jpeg", ".ico", ".tif", ".tiff", ".pdf", ".gif", ".zip", ".pyc")): return ""
    return data.decode("utf-8", "replace")


def scan(names, read):
    pats = terms(); bad = []; ok = allowed()
    if pats is None:
        print("check_banned: no private term list found (OPS_BANNED_TERMS). Refusing."); return 2
    for n in names:
        try: body = text_of(n, read(n))
        except Exception: body = ""
        for where, txt in (("name", n), ("text", body)):
            for p in pats:
                for m in p.finditer(txt):
                    line = txt.count("\n", 0, m.start()) + 1 if where == "text" else 0
                    full = txt[txt.rfind("\n", 0, m.start()) + 1: (txt.find("\n", m.end()) + 1 or len(txt) + 1) - 1]
                    if any(x.search(n) and y.search(full) for x, y in ok): continue
                    bad.append(f"  {n}:{line or 'file name'}  /{p.pattern}/"); break
    if bad:
        print(f"check_banned: {len(bad)} private term(s) found - commit stopped:"); print("\n".join(bad[:200])); return 1
    print(f"check_banned: {len(names)} file(s) clean"); return 0


def git(*a): return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True).stdout


def main(argv):
    if "--msg" in argv:
        f = argv[argv.index("--msg") + 1]; return scan([f], lambda n: Path(n).read_bytes())
    if "--all" in argv:
        names = git("ls-files", "-z").decode().split("\0")
    else:
        names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")
    names = [n for n in names if n]
    return scan(names, lambda n: git("show", ":" + n))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

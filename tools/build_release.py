"""build_release.py - a release zip made from a list of reviewed files, never by zipping a working folder.

    python tools/build_release.py --profile friends --out dist
          builds   dist/Origin_Plot_Studio_<version>/      the release as a folder (for looking at it)
                   dist/Origin_Plot_Studio_<version>.zip   the release
                   dist/Origin_Plot_Studio_<version>.zip.sha256
          and prints the sha256 of the zip.

    --profile friends|owner   written into the build as security_profile.json ({"profile": "friends"}): a 'friends'
                              build starts local-only, refuses unsigned updates and has no client-side AI repair
                              (see outbound_policy.profile). Default: friends.
    --out DIR                 where to build (default: dist/ beside the repository's files; made new each time)
    --ref COMMIT              the commit to build (default HEAD). Files are read from that COMMIT, not from the
                              folder: what is not committed cannot get into a release.
    --worktree                read the tracked files from the folder instead (to try a build before committing).
                              The result is marked "NOT A RELEASE BUILD".
    --source DIR              another repository / folder than this one;  --no-git: DIR is a plain folder (tests)

How a file gets in: its path must match ALLOW (the reviewed program assets) and must not match the exclusion rules
(runtime and personal data: settings, sessions, logs, lessons, learned formats, credentials, the outbound policy,
caches, project archives, private templates, tests, tools, .github, backend). After the build the finished folder and
the zip are checked against the exclusion rules again, the secret scan (tools/secret_scan.py, strict) is run over the
build, and - when the owner's private term list is on the machine (OPS_BANNED_TERMS, see tools/check_banned.py) - the
private-term check too. Any hit stops the build with exit code 1 and removes
the zip.

RELEASE_CONTENTS.md (inside the build) lists every file with its size and sha256; the bundled data files, documents
and pictures are listed first, for the owner to review before publishing: only approved, synthetic demo data may ship.

The zip is deterministic for one commit and one Python/zlib: entries sorted, one fixed time (the commit's), fixed
permissions. It is NOT signed here. Signing is a separate step with the owner's key: tools/sign_release.py.

Standard library only. Reads the repository; writes only under --out.
"""
import argparse, datetime, hashlib, io, json, os, re, shutil, struct, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = "origin_plot_app"

# ---------------------------------------------------------------------------------------------- what may be in a release
# '*' stays inside one folder, '**' crosses folders. A new kind of file has to be added here, on purpose.
ALLOW = [
    APP + "/*.py", APP + "/*.pyw", APP + "/*.bat", APP + "/*.vbs",                       # the program and its launchers
    APP + "/app.ico", APP + "/app.png",
    APP + "/HOW_TO_INSTALL.txt", APP + "/README.txt", APP + "/WHATS_NEW.txt", APP + "/UI_REFRESH_NOTES.txt", APP + "/CHANGELOG_gallery_graphs.md",
    APP + "/requirements.txt", APP + "/requirements.lock",                               # the tested package set
    APP + "/XRD_workbook_template.xlsx", APP + "/phase_amounts_template.csv", APP + "/xrd_phase_library.csv",
    APP + "/config/assistant.example.json", APP + "/phase_library/README.txt",
    APP + "/gallery/*.png",                                                              # pictures of the graph types
    APP + "/examples_synthetic/*",                                                       # demo data: synthetic only (owner review)
    APP + "/opstudio/**",                                                                # the graph engine, its templates and previews
    "README.md", "LICENSE", "SECURITY.md", "PRIVACY.md",                                 # what a user needs to read
]
# The program files go to the top of the release (Setup.bat is the first thing one sees); the four documents beside them.
REQUIRED = ["origin_plot_app.py", "smart_plots.py", "start.pyw", "setup.pyw", "Setup.bat", "requirements.txt", "requirements.lock", "LICENSE", "SECURITY.md", "PRIVACY.md"]

# ---------------------------------------------------------------------------------------------- what may never be in one
DENY_NAMES = ["settings*.json", "last_session.json", "last_run_log.txt", "assistant_lessons.txt", "learned_formats.json", "credentials.json", "outbound_policy.json",
              "pdf_names.json", "console_output.txt", "startup_error.txt", "error_log.txt", "slow_log.txt", "running.flag", "secrets.dat", "defaults.json",
              "install_journal.json", "dry_commands.txt", ".env", ".env.*", "*.local.json",
              "*.sqlite3", "*.sqlite", "*.db", "*.log", "*.pyc", "*.pyo", "*.tmp", "*.bak", "*.orig", "*.opsproject", "*.opju", "*.opj", "*.pem", "*.key", "*.p12", "*.pfx",
              "manifest.sig", "Thumbs.db", ".DS_Store"]
DENY_DIRS = ["__pycache__", ".git", ".github", "tests", "tools", "backend", "logs", "log", "cache", "caches", ".cache", "my_templates", "ops_private", "private",
             "converted_tables", "examples_your_data", "sample_data", "screenshots", "project_data", "dry_out", "_upgrade_pack", "figure_recipes", "reference_figures",
             "node_modules", ".venv", "venv", ".idea", ".vscode"]
DATA_EXT = (".xlsx", ".xlsm", ".xls", ".csv", ".tsv", ".txt", ".dat", ".docx", ".pptx", ".pdf", ".xy", ".asc", ".spa", ".raw")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".tif", ".tiff", ".webp")
_TOOL_DEFAULTS = {"openpyxl", "python-docx", "python-pptx", "xlsxwriter", "steve canny", "microsoft office user", "user", "author"}      # what the libraries write when nobody sets an author
PROGRAM_TEXT = ("HOW_TO_INSTALL.txt", "README.txt", "WHATS_NEW.txt", "UI_REFRESH_NOTES.txt", "requirements.txt")


class BuildError(Exception):
    pass


def _glob(pattern):
    rx = "".join(".*" if tok == "**" else "[^/]*" if tok == "*" else "[^/]" if tok == "?" else re.escape(tok) for tok in re.split(r"(\*\*|\*|\?)", pattern))
    return re.compile("^" + rx + "$")


_ALLOW_RX = [_glob(p) for p in ALLOW]
_DENY_RX = [_glob(p) for p in DENY_NAMES]


def allowed(path): return any(rx.match(path) for rx in _ALLOW_RX)


def denied(path):
    """Why a path may never be in a release ('' = it may). Looked at with lower case: Windows does not tell case apart."""
    parts = path.replace("\\", "/").split("/")
    for d in parts[:-1]:
        if d.lower() in DENY_DIRS: return f"the folder '{d}' is runtime, private or development data"
    name = parts[-1].lower()
    for pat, rx in zip(DENY_NAMES, _DENY_RX):
        if rx.match(name): return f"'{pat}' is runtime or personal data"
    return ""


def release_path(path):
    """Where a repository file sits inside the release: the program folder becomes the top of the release."""
    return path[len(APP) + 1:] if path.startswith(APP + "/") else path


# ---------------------------------------------------------------------------------------------- reading the source
def _git(source, *args, binary=False):
    r = subprocess.run(["git", "-C", source] + list(args), capture_output=True)
    if r.returncode != 0: raise BuildError("git " + " ".join(args[:3]) + " failed: " + r.stderr.decode("utf-8", "replace").strip()[-300:])
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def source_files(source, ref="HEAD", worktree=False, no_git=False):
    """({repository path: bytes}, facts about where it came from). Committed content unless worktree / no_git."""
    facts = {"commit": "", "commit_time": 0, "mode": "commit", "dirty": False}
    if no_git:
        files = {}
        for d, dirs, names in os.walk(source):
            dirs[:] = sorted(x for x in dirs if x != ".git")
            for n in sorted(names):
                full = os.path.join(d, n)
                if os.path.islink(full) or not os.path.isfile(full): continue
                rel = os.path.relpath(full, source).replace(os.sep, "/")
                if allowed(rel) or denied(rel): files[rel] = None                   # read later, and only when it gets in
        for rel in [r for r in files if allowed(r) and not denied(r)]: files[rel] = open(os.path.join(source, rel), "rb").read()
        facts.update(mode="folder (no Git)", commit_time=1577836800); return files, facts
    facts["commit"] = _git(source, "rev-parse", ref).strip(); facts["commit_time"] = int(_git(source, "log", "-1", "--format=%ct", ref).strip())
    facts["dirty"] = bool(_git(source, "status", "--porcelain").strip())
    if worktree:
        facts["mode"] = "tracked files of the working folder"; files = {}
        for rel in _git(source, "ls-files", "-z").split("\0"):
            full = os.path.join(source, rel)
            if rel and os.path.isfile(full) and not os.path.islink(full): files[rel] = open(full, "rb").read() if allowed(rel) and not denied(rel) else None
        return files, facts
    files = {}; wanted = []
    for line in _git(source, "ls-tree", "-r", "-z", ref).split("\0"):
        if not line: continue
        meta, _, rel = line.partition("\t"); mode, kind, sha = meta.split()[:3]
        files[rel] = None
        if kind == "blob" and mode in ("100644", "100755") and allowed(rel) and not denied(rel): wanted.append((rel, sha))      # no links, no submodules
    p = subprocess.Popen(["git", "-C", source, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for rel, sha in wanted:
            p.stdin.write(sha.encode() + b"\n"); p.stdin.flush()
            head = p.stdout.readline().split(); data = p.stdout.read(int(head[2])); p.stdout.read(1); files[rel] = data
    finally:
        p.stdin.close(); p.wait()
    return files, facts


def version_of(files):
    m = re.search(rb'^VERSION\s*=\s*["\']([0-9][0-9.]*)["\']', files.get(APP + "/smart_plots.py") or b"", re.M)
    if not m: raise BuildError("the version was not found (VERSION = \"...\" in origin_plot_app/smart_plots.py)")
    return m.group(1).decode()


# ---------------------------------------------------------------------------------------------- the inventory
def _metadata_note(name, data):
    """What a document or picture carries besides its content - the KIND of metadata only, never a value (a value can
    be a person's name)."""
    low = name.lower(); notes = []
    try:
        if low.endswith((".xlsx", ".xlsm", ".docx", ".pptx")):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
                if "docProps/core.xml" in names:
                    core = z.read("docProps/core.xml").decode("utf-8", "replace")
                    for tag, word in (("dc:creator", "author"), ("cp:lastModifiedBy", "last modified by"), ("dc:title", "title"), ("cp:keywords", "keywords"), ("dc:description", "comments")):
                        m = re.search(rf"<{tag}[^>]*>([^<]+)</{tag}>", core)
                        if m and m.group(1).strip():
                            tool = m.group(1).strip().lower() in _TOOL_DEFAULTS or "generated by" in m.group(1).lower()
                            notes.append(word + (" (default text of the library that wrote the file)" if tool else " - REVIEW: a text somebody typed or a name"))
                if "docProps/custom.xml" in names: notes.append("custom properties")
                if any(n.lower().endswith(("vbaproject.bin", ".bin")) and "vba" in n.lower() for n in names): notes.append("MACROS")
                if any("externalLink" in n for n in names): notes.append("links to other workbooks")
                if any(n.startswith("xl/comments") or n.startswith("word/comments") for n in names): notes.append("comments")
        elif low.endswith(".png") and data[:8] == b"\x89PNG\r\n\x1a\n":
            at = 8; keys = []
            while at + 8 <= len(data):
                size, kind = struct.unpack(">I4s", data[at:at + 8])
                if kind in (b"tEXt", b"zTXt", b"iTXt"): keys.append(data[at + 8:at + 8 + size].split(b"\0", 1)[0].decode("latin-1")[:20])
                if kind == b"eXIf": keys.append("EXIF")
                at += 12 + size
            if keys: notes.append("text: " + ", ".join(sorted(set(keys))))
        elif low.endswith((".jpg", ".jpeg")) and b"Exif\0\0" in data[:65536]: notes.append("EXIF")
    except Exception: notes.append("could not be read")
    return "; ".join(notes)


def contents_markdown(build, facts, version, profile, name):
    rows = sorted(build.items())
    def kind(p):
        low = p.lower()
        if low.endswith(IMAGE_EXT): return "image"
        if low.endswith(DATA_EXT) and os.path.basename(p) not in PROGRAM_TEXT and not low.endswith("readme.txt"): return "data"
        return "program"
    data = [(p, d) for p, d in rows if kind(p) == "data"]; images = [(p, d) for p, d in rows if kind(p) == "image"]; rest = [(p, d) for p, d in rows if kind(p) == "program"]
    when = datetime.datetime.fromtimestamp(facts["commit_time"], datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [f"# Contents of {name}", "",
         "Generated by `tools/build_release.py`. Every file of this release is listed with its size and SHA-256.", "",
         f"- Version: {version}", f"- Security profile: {profile}",
         f"- Built from: {facts['mode']}" + (f", commit {facts['commit']}" if facts["commit"] else "") + f" ({when})"]
    if facts["mode"] != "commit" or facts.get("dirty_build"): L.append("- **NOT A RELEASE BUILD**: it was not made from committed files only. Build a release from a commit (the default).")
    L += [f"- Files: {len(rows)} ({len(data)} data files and documents, {len(images)} pictures, {len(rest)} program and text files)",
          "- Not included, by rule: settings, sessions, logs, lessons, learned formats, credentials, the outbound policy, caches, project archives, private templates, tests, tools.", "",
          "## For the owner to review before publishing", "",
          "The data files, documents and pictures below travel with the program. Only **synthetic or otherwise approved demo data**",
          "may be among them: no unpublished measurements, no sample names of real work, no pictures of confidential results.",
          "The column \"carries\" names the kind of metadata a file holds besides its content (never the value). The build cannot",
          "judge whether a dataset is synthetic - a person has to.", "",
          f"### Data files and documents ({len(data)})", "", "| File | Bytes | SHA-256 | Carries |", "| --- | ---: | --- | --- |"]
    L += [f"| {p} | {len(d)} | `{hashlib.sha256(d).hexdigest()}` | {_metadata_note(p, d)} |" for p, d in data]
    L += ["", f"### Pictures ({len(images)})", "", "| File | Bytes | SHA-256 | Carries |", "| --- | ---: | --- | --- |"]
    L += [f"| {p} | {len(d)} | `{hashlib.sha256(d).hexdigest()}` | {_metadata_note(p, d)} |" for p, d in images]
    L += ["", f"## Program and text files ({len(rest)})", "", "| File | Bytes | SHA-256 |", "| --- | ---: | --- |"]
    L += [f"| {p} | {len(d)} | `{hashlib.sha256(d).hexdigest()}` |" for p, d in rest]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------------------------- building
def write_zip(path, top, build, when):
    """One zip, the same bytes every time for the same content: sorted names, one time stamp, fixed permissions."""
    t = datetime.datetime.fromtimestamp(max(when, 315532800), datetime.timezone.utc); stamp = (t.year, t.month, t.day, t.hour, t.minute, t.second - t.second % 2)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(build):
            info = zipfile.ZipInfo(top + "/" + rel, date_time=stamp); info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3; info.external_attr = (0o100644 << 16)
            z.writestr(info, build[rel], compresslevel=9)


def verify_build(folder, zip_path, top):
    """The finished build, looked at again from outside: nothing excluded by rule is in the folder or in the zip, the
    zip holds exactly the folder, every name is safe on Windows. Returns the list of problems (empty = fine)."""
    bad = []; on_disk = set()
    for d, _dirs, names in os.walk(folder):
        for n in names:
            rel = os.path.relpath(os.path.join(d, n), folder).replace(os.sep, "/"); on_disk.add(rel)
            why = denied(rel)
            if why: bad.append(f"{rel}: {why}")
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist(); seen = set()
        for n in names:
            if not n.startswith(top + "/"): bad.append(f"{n}: not inside the release folder"); continue
            rel = n[len(top) + 1:]
            why = denied(rel)
            if why: bad.append(f"{rel} (in the zip): {why}")
            if re.search(r'[\\:<>"|?*\x00-\x1f]', rel) or any(p in ("", ".", "..") or p != p.rstrip(". ") for p in rel.split("/")): bad.append(f"{rel}: a name that is not safe on Windows")
            if rel.lower() in seen: bad.append(f"{rel}: the same name twice (Windows does not tell capital letters apart)")
            seen.add(rel.lower())
        if {n[len(top) + 1:] for n in names if n.startswith(top + "/")} != on_disk: bad.append("the zip and the build folder do not hold the same files")
        if z.testzip() is not None: bad.append("the zip is damaged")
    return bad


def build(source=ROOT, out=None, profile="friends", ref="HEAD", worktree=False, no_git=False, name=None, log=print):
    """Build the release. Returns {'zip', 'folder', 'sha256', 'version', 'files', 'excluded', 'not_listed', 'problems'}.
    Raises BuildError when the result may not be published (and removes the zip)."""
    if profile not in ("friends", "owner"): raise BuildError("the profile is 'friends' or 'owner'")
    source = os.path.abspath(source); out = os.path.abspath(out or os.path.join(source, "dist"))
    files, facts = source_files(source, ref, worktree, no_git)
    version = version_of(files); name = name or f"Origin_Plot_Studio_{version}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}", name): raise BuildError("the name of the release may hold letters, digits, '.', '_' and '-' only")
    build_files, excluded, not_listed, came_from = {}, [], [], {}
    for rel in sorted(files):
        why = denied(rel)
        if why: excluded.append((rel, why)); continue
        if not allowed(rel): not_listed.append(rel); continue
        if rel == APP + "/security_profile.json": continue                                # written below: the build decides the profile, not the tree
        dest = release_path(rel)
        if dest in build_files: raise BuildError(f"two files would become {dest} in the release")
        build_files[dest] = files[rel]; came_from[dest] = rel
    build_files["security_profile.json"] = (json.dumps({"profile": profile}) + "\n").encode()
    missing = [r for r in REQUIRED if r not in build_files]
    if missing: raise BuildError("the release would be incomplete; missing: " + ", ".join(missing) + (" (are they committed? a release is built from the commit, not from the folder)" if facts["mode"] == "commit" else ""))
    facts["dirty_build"] = facts["mode"] != "commit"
    build_files["RELEASE_CONTENTS.md"] = contents_markdown(build_files, facts, version, profile, name).encode("utf-8")
    folder = os.path.join(out, name); zip_path = os.path.join(out, name + ".zip")
    if os.path.isdir(folder): shutil.rmtree(folder)
    for stale in (zip_path, zip_path + ".sha256"):
        if os.path.exists(stale): os.remove(stale)
    for rel, data in build_files.items():
        full = os.path.join(folder, *rel.split("/")); os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f: f.write(data)
    write_zip(zip_path, name, build_files, facts["commit_time"])
    problems = verify_build(folder, zip_path, name)
    # credentials: the scan that never prints a value, in its strict form (a test value counts too: none belongs in a release)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import secret_scan
    found, n_scanned, _cut = secret_scan.scan_tree([folder])
    lines = []; n_found = secret_scan.report(found, strict=True, out=lines.append)
    if n_found: problems.append(f"the secret scan found {n_found} possible credential(s):\n    " + "\n    ".join(lines))
    hits = _banned_hits(build_files, came_from)
    banned = "not run (no private term list on this machine: OPS_BANNED_TERMS)" if hits is None else f"{len(build_files)} files, {len(hits)} with a private term"
    if hits: problems.append("private terms (the owner's list, OPS_BANNED_TERMS) in: " + ", ".join(hits[:20]) + (" ..." if len(hits) > 20 else ""))
    if problems:
        for f in (zip_path, zip_path + ".sha256"):
            if os.path.exists(f): os.remove(f)
        raise BuildError("the build may not be published:\n  - " + "\n  - ".join(problems))
    digest = hashlib.sha256(open(zip_path, "rb").read()).hexdigest()
    with open(zip_path + ".sha256", "w", encoding="ascii", newline="\n") as f: f.write(f"{digest}  {name}.zip\n")
    log(f"version {version}, profile {profile}, from {facts['mode']}" + (f" {facts['commit'][:12]}" if facts["commit"] else "") + (" - NOT A RELEASE BUILD" if facts["dirty_build"] else ""))
    if facts["mode"] == "commit" and facts["dirty"]: log("note: the working folder has uncommitted changes; they are NOT in this build (it holds the commit).")
    log(f"{len(build_files)} files in the release; {len(excluded)} excluded by rule; {len(not_listed)} tracked files not on the list of release files (tests, tools, development notes ...)")
    log(f"checked again after building: exclusion rules ok, names ok, zip complete; secret scan: {n_scanned} files, 0 findings; private-term check: {banned}")
    log(f"zip:    {zip_path}  ({os.path.getsize(zip_path)} bytes)")
    log(f"sha256: {digest}")
    log("next:   review RELEASE_CONTENTS.md, then sign with tools/sign_release.py (see docs/RELEASE_PROCESS.md)")
    return {"zip": zip_path, "folder": folder, "sha256": digest, "version": version, "files": sorted(build_files), "excluded": excluded, "not_listed": not_listed, "problems": []}


def _banned_hits(build_files, came_from):
    """Files of the build that hold a private term, found with the repository's own check (tools/check_banned.py: its
    term list, which stays outside the repository, and its reviewed exceptions). None when there is no list on this
    machine. Only file names are returned - a term is never printed."""
    try: import check_banned
    except Exception: return None
    pats = check_banned.terms()
    if pats is None: return None
    ok = check_banned.allowed(); hits = []
    for dest in sorted(build_files):
        name = came_from.get(dest, dest)                          # the exceptions are written for the paths of the repository
        try: body = check_banned.text_of(name, build_files[dest])
        except Exception: body = ""
        for txt in (name, body):
            bad = False
            for p_ in pats:
                for m in p_.finditer(txt):
                    full = txt[txt.rfind("\n", 0, m.start()) + 1: (txt.find("\n", m.end()) + 1 or len(txt) + 1) - 1]
                    if any(x.search(name) and y.search(full) for x, y in ok): continue
                    bad = True; break
                if bad: break
            if bad: hits.append(dest); break
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a clean release zip of Origin Plot Studio from the reviewed list of files.")
    ap.add_argument("--profile", choices=("friends", "owner"), default="friends"); ap.add_argument("--out"); ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--worktree", action="store_true"); ap.add_argument("--source", default=ROOT); ap.add_argument("--no-git", action="store_true"); ap.add_argument("--name")
    a = ap.parse_args(argv)
    try:
        build(a.source, a.out, a.profile, a.ref, a.worktree, a.no_git, a.name)
        return 0
    except BuildError as e:
        print("BUILD FAILED: " + str(e)); return 1


if __name__ == "__main__":
    sys.exit(main())

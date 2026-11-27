"""diagnostics.py - a SANITIZED problem report: one zip you can read and then attach to a message.

    import diagnostics
    info = diagnostics.build_bundle("C:/.../ops_diagnostics.zip")          # writes the file; sends nothing
    info["path"], info["files"], info["replaced"]

What the zip holds (MANIFEST.txt inside says the same, with the numbers of this bundle, so you can check before sending):
    MANIFEST.txt         what is inside, what was replaced, what is not inside
    about.json           version of the app, of Python and of the packages; the system (name and version, NOT the name
                         of the computer or of the user); the security profile and the outbound level; where keys
                         would be kept (the kind of store, never a key)
    program_files.json   the program files that are installed, each with size and sha256, compared with the list of the
                         release (same / changed / missing). Other files in the program folder are only counted.
    errors.json          the kinds of errors in the logs (class names and the program file / line they came from)
    log.txt              the last lines of the app's logs, sanitized (only with include_log=True)

What is done to every text before it goes in:
    credentials  -> [removed]      (outbound_policy.redact: keys of every provider, tokens, Authorization headers ...)
    paths        -> <folder>       (a program file keeps its own name: <app>/smart_plots.py; nothing of the path)
    your names   -> <file 1>, <sample 2> ...   the files, samples, graphs and projects the app knows from your session
                                   and settings, the name of your user account and of the computer
    data files   -> <file>         anything else that looks like the name of a data file
    numbers      -> <numbers>      four or more numbers in a row (a row of a table)

What is NEVER inside: measurement data, data files, project files, settings, sessions, lessons, learned formats,
credentials, real paths.

It cannot know a name it has never seen: read log.txt before you send it.

This module only writes a local file. It has no upload. Should one be added, it must ask
outbound_policy.require("diagnostics", url) before it connects (off by default, and never in local-only mode).

Standard library + outbound_policy; importable without Qt and without the plotting libraries.
"""
import datetime, getpass, hashlib, json, os, platform, re, sys, zipfile

import outbound_policy

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_FILES = ("startup_error.txt", "error_log.txt", "last_run_log.txt", "console_output.txt", "slow_log.txt")
MAX_LOG_LINES = 400                       # of each log, from its end
MAX_LINE = 600                            # characters of one line
PROGRAM_EXT = (".py", ".pyw", ".bat", ".vbs")
DATA_EXT = "xlsx|xlsm|xls|csv|tsv|txt|dat|xy|asc|spa|raw|opju|opj|otpu|json|docx|pptx|pdf|png|jpg|jpeg|tif|tiff|opsproject|zip|brml|xrdml|ras"
_GENERIC = {"users", "user", "home", "documents", "desktop", "downloads", "appdata", "local", "roaming", "programs", "program files", "onedrive", "temp", "tmp", "data",
            "origin plot studio", "originplotstudio", "origin_plot_app", "inputs", "derived", "project_data", "results", "table", "sheet1", "sheet", "graph", "sample", "samples",
            "combined", "figure", "time", "temperature", "xrd", "tga", "dtg", "ftir", "psd", "none", "true", "false", "untitled project", "project", "file", "files", "name",
            "folder", "computer", "numbers", "removed", "app", "python", "error", "line", "modern window", "decide for me"}
_NAME_KEYS = {"sample": "sample", "samples": "sample", "table": "graph", "title": "graph", "name": "name", "project": "project", "file": "file", "files": "file", "path": "file",
              "info_files": "file", "workbench_files": "file", "last_dir": "file", "out": "file", "recent_sessions": "file", "label": "sample", "legend": "sample",
              "projects": "projects"}
_ALIAS = re.compile(r"<(?:file|sample|graph|name|project) \d+>|<(?:folder|file|user|computer|numbers|app|python)>|\[removed\]")

_WIN_PATH = re.compile(r"(?:(?<![A-Za-z])[A-Za-z]:[\\/]+|\\\\+)(?:[^\\/:*?\"<>|\r\n]+[\\/]+)*(?:[^\\/:*?\"<>|\r\n\s]+(?: [^\\/:*?\"<>|\r\n\s]+){0,6}?\.\w{1,10}\b|[^\\/:*?\"<>|\r\n\s]*)")
_POSIX_PATH = re.compile(r"(?<![\w.:/<>])/(?:[^/\r\n\"'<>|:]+/)+[^/\s\"'<>|:]+(?: [^/\s\"'<>|:]+){0,6}?\.\w{1,10}\b|(?<![\w.:/<>])/(?:[^/\s\"'<>|:]+/)+[^/\s\"'<>|:]*")
_FILE_TOKEN = re.compile(r"(?i)(?<![\w<])[^\s\"'<>|/\\:=(){}\[\],;]+\.(?:" + DATA_EXT + r")\b")
_QUOTED_FILE = re.compile(r"(?i)(['\"])[^'\"\r\n]{1,200}?\.(?:" + DATA_EXT + r")\1")
_NUMBER_ROW = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?(?:[ \t,;]+[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?){3,}(?![\w.])")
_ERROR_LINE = re.compile(r"^\s*((?:[A-Za-z_]\w*\.)*[A-Z]\w*(?:Error|Exception|Warning|Interrupt|Exit|Blocked|Failure|Fault))\b")
_FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')


def app_version(app_dir=None):
    try:
        m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', open(os.path.join(app_dir or HERE, "smart_plots.py"), encoding="utf-8").read(), re.M)
        return m.group(1) if m else ""
    except OSError: return ""


# ------------------------------------------------------------------------------------------------ the names to take out
def _collect(obj, out, kind="name", depth=0):
    """Strings of a saved session / of the settings that name the user's work: (kind, text) pairs. Read only to know
    what to replace - nothing of it is written into the bundle."""
    if depth > 12 or len(out) > 20000: return
    if isinstance(obj, dict):
        if kind == "projects": out += [("project", k) for k in obj if isinstance(k, str)]; kind = "name"          # the ids of projects are made from their names
        for k, v in obj.items():
            if isinstance(k, str) and (os.sep in k or "/" in k or "\\" in k): _collect(k.split("|")[0], out, "file", depth + 1)
            _collect(v, out, _NAME_KEYS.get(str(k).lower(), kind if isinstance(v, (dict, list)) else ""), depth + 1)
    elif isinstance(obj, list):
        for v in obj: _collect(v, out, kind, depth + 1)
    elif isinstance(obj, str) and kind and 0 < len(obj) < 400:
        out.append((kind, obj))


def known_names(app_dir=None, extra=()):
    """{text: kind} of everything that must not be in a bundle: files, samples, graphs and projects of the session and
    the settings, the parts of their paths, the user and the computer."""
    app_dir = app_dir or HERE; found = []
    for f in (os.path.join(app_dir, "last_session.json"), os.path.join(app_dir, "settings.json"), os.path.join(app_dir, "settings_modern.json"), os.environ.get("OPS_SETTINGS_FILE") or ""):
        try:
            if f and os.path.isfile(f) and os.path.getsize(f) < 64 * 1024 * 1024: _collect(json.load(open(f, encoding="utf-8")), found)
        except Exception: pass
    names = {}
    def add(text, kind):
        t = str(text).strip()
        if len(t) < 3 or t.lower() in _GENERIC or re.fullmatch(r"[\d\s.,:;_\-+/\\]*", t): return
        names.setdefault(t, kind)
    for kind, text in found:
        if kind == "file" or re.search(r"[\\/]", text):
            parts = [p for p in re.split(r"[\\/|]+", text) if p and not re.fullmatch(r"[A-Za-z]:", p)]
            for i, p in enumerate(parts):
                last = i == len(parts) - 1
                add(p, "file" if last else "folder")
                if last and "." in p: add(p.rsplit(".", 1)[0], "file")
        else: add(text, kind)
    for text in extra: add(text, "name")
    for text, kind in ((_user(), "user"), (os.path.basename(os.path.expanduser("~")), "user"), (platform.node(), "computer"), (platform.node().split(".")[0], "computer")):
        if text and len(text) >= 3 and text.lower() not in _GENERIC and text.lower() not in ("root", "admin", "administrator", "localhost"): names.setdefault(text, kind)
    return names


def _user():
    try: return getpass.getuser()
    except Exception: return os.environ.get("USERNAME") or os.environ.get("USER") or ""


# ------------------------------------------------------------------------------------------------ making a text safe
class Sanitizer:
    """Turns a text of the app (a log, an error) into one without credentials, paths, names of the user's work or rows
    of numbers. counts says how often each kind was replaced."""
    def __init__(self, names=None, app_dir=None):
        self.app_dir = app_dir or HERE; self.counts = {"credentials": 0, "paths": 0, "names": 0, "files": 0, "numbers": 0}
        self.alias = outbound_policy.Aliases(); self.rules = []
        try: self.program = {f.lower() for f in os.listdir(self.app_dir) if f.lower().endswith(PROGRAM_EXT)}
        except OSError: self.program = set()
        for text, kind in sorted((names or {}).items(), key=lambda kv: -len(kv[0])):
            body = re.escape(text)
            rx = re.compile(body if len(text) >= 6 else r"(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])", re.I)
            self.rules.append((rx, "<user>" if kind == "user" else "<computer>" if kind == "computer" else "<folder>" if kind == "folder" else "<" + self.alias.alias(kind, text).lower() + ">"))

    def _path(self, m):
        self.counts["paths"] += 1
        p = m.group(0); base = re.split(r"[\\/]", p.rstrip("\\/"))[-1]
        if base.lower().endswith((".py", ".pyw", ".pyd", ".so", ".dll")):                       # code: keep which file, drop where it is
            return ("<app>/" if base.lower() in self.program else "<python>/") + base
        return "<folder>"

    def clean(self, text):
        t = str(text)
        red = outbound_policy.redact(t); self.counts["credentials"] += red.count("[removed]") - t.count("[removed]"); t = red
        t = _WIN_PATH.sub(self._path, t); t = _POSIX_PATH.sub(self._path, t)
        before = t.count("<folder>"); t = outbound_policy.strip_paths(t); self.counts["paths"] += t.count("<folder>") - before
        for rx, alias in self.rules:
            t, n = rx.subn(alias, t); self.counts["names"] += n
        t, n = _QUOTED_FILE.subn(lambda m: m.group(1) + "<file>" + m.group(1), t); self.counts["files"] += n
        t, n = _FILE_TOKEN.subn(lambda m: m.group(0) if m.group(0).lower() in self.program else "<file>", t); self.counts["files"] += n
        t, n = _NUMBER_ROW.subn("<numbers>", t); self.counts["numbers"] += n
        return t


def _tail(path, lines):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 400_000)); data = f.read()
        return [l[:MAX_LINE] for l in data.decode("utf-8", "replace").splitlines()[-lines:]]
    except OSError: return []


# ------------------------------------------------------------------------------------------------ the parts
def about(app_dir=None):
    d = {"app": "Origin Plot Studio", "version": app_version(app_dir), "made": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
         "python": platform.python_version(), "python_implementation": platform.python_implementation(), "bits": 64 if sys.maxsize > 2 ** 32 else 32,
         "system": platform.system(), "system_release": platform.release(), "system_version": platform.version()[:80], "machine": platform.machine()}
    try: d["security_profile"] = outbound_policy.profile(); d["outbound_level"] = outbound_policy.level(); d["outbound_channels"] = {c: outbound_policy.channel_on(c) for c in outbound_policy.CHANNELS}
    except Exception as e: d["security_profile"] = d["outbound_level"] = "unknown (" + type(e).__name__ + ")"
    try:
        import secure_store
        d["key_store"] = secure_store.backend()                       # the kind of store only
    except Exception: d["key_store"] = "unknown"
    d["packages"] = packages(app_dir)
    return d


def packages(app_dir=None):
    """{name: {'installed', 'tested'}} for the packages of requirements.lock (or requirements.txt)."""
    import importlib.metadata as md
    want = {}
    for f in ("requirements.lock", "requirements.txt"):
        try: text = open(os.path.join(app_dir or HERE, f), encoding="utf-8").read()
        except OSError: continue
        for m in re.finditer(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)", text, re.M): want.setdefault(m.group(1), m.group(2))
        if want: break
    out = {}
    for name in sorted(want or {n: "" for n in ("numpy", "pandas", "scipy", "matplotlib", "openpyxl", "PySide6", "cryptography")}, key=str.lower):
        try: have = md.version(name)
        except Exception: have = ""
        out[name] = {"installed": have or "not installed", "tested": want.get(name, "")}
    return out


def program_files(app_dir=None):
    """The program files that are installed: {'files': [{'name', 'bytes', 'sha256', 'release'}], 'other_files': n,
    'compared_with_release': bool}. 'release' is same / changed / not in the release list. A file the release lists
    and that is not there is 'missing'. Files that are not program files (yours, logs, settings) are only counted."""
    app_dir = app_dir or HERE; listed = {}
    try:
        for m in re.finditer(r"^\| ([^|]+?) \| (\d+) \| `([0-9a-f]{64})`", open(os.path.join(app_dir, "RELEASE_CONTENTS.md"), encoding="utf-8").read(), re.M): listed[m.group(1)] = m.group(3)
    except OSError: pass
    rows, other = [], 0
    for d, dirs, names in os.walk(app_dir):
        dirs[:] = sorted(x for x in dirs if x not in ("__pycache__", ".git", "project_data", "dry_out"))
        for n in sorted(names):
            full = os.path.join(d, n); rel = os.path.relpath(full, app_dir).replace(os.sep, "/")
            is_program = rel in listed or ("/" not in rel and n.lower().endswith(PROGRAM_EXT)) or (rel.startswith("opstudio/") and n.endswith(".py"))
            if not is_program or os.path.islink(full): other += 1; continue
            try:
                h = hashlib.sha256()
                with open(full, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
                digest = h.hexdigest(); size = os.path.getsize(full)
            except OSError: continue
            rows.append({"name": rel, "bytes": size, "sha256": digest, "release": ("same" if listed[rel] == digest else "changed") if rel in listed else ("not in the release list" if listed else "")})
    here = {r["name"] for r in rows}
    for rel in sorted(listed):
        if rel not in here and rel != "RELEASE_CONTENTS.md": rows.append({"name": rel, "bytes": 0, "sha256": "", "release": "missing"})
    return {"files": rows, "other_files": other, "compared_with_release": bool(listed)}


def error_classes(lines):
    """[{'error', 'count', 'where'}] - which kinds of errors the log lines hold; where = program file:line of the last
    frame before the error (the name of the file only)."""
    found = {}; last = ""
    for l in lines:
        m = _FRAME.search(l)
        if m: last = re.split(r"[\\/]", m.group(1))[-1] + ":" + m.group(2); continue
        m = _ERROR_LINE.match(l)
        if m:
            key = (m.group(1), last if last.split(":")[0].lower().endswith((".py", ".pyw")) else "")
            found[key] = found.get(key, 0) + 1; last = ""
    return [{"error": k[0], "where": k[1], "count": n} for k, n in sorted(found.items(), key=lambda kv: (-kv[1], kv[0]))]


# ------------------------------------------------------------------------------------------------ the bundle
def build_bundle(dest_zip, *, include_log=True, app_dir=None, log_files=None, names=(), max_log_lines=MAX_LOG_LINES):
    """Write the sanitized diagnostic bundle to dest_zip (a local file; nothing is sent anywhere).

    include_log     False leaves log.txt out (errors.json still says which kinds of errors there were)
    app_dir         the program folder (default: where this file is)
    log_files       paths of logs to read instead of the usual ones in app_dir
    names           more names to replace (the window can pass the samples and files it has open)
    Returns {'path', 'files', 'log_lines', 'replaced': {...}, 'leftover': n} - leftover is the number of known names,
    paths or credentials still found by the last check (0 unless something is wrong; the text is then cut out)."""
    app_dir = os.path.abspath(app_dir or HERE)
    known = known_names(app_dir, names); san = Sanitizer(known, app_dir)
    sources = list(log_files) if log_files is not None else [os.path.join(app_dir, f) for f in LOG_FILES]
    home = os.environ.get("ORIGIN_PLOT_APP_HOME")
    if log_files is None and home: sources.append(os.path.join(home, "slow_log.txt"))
    raw, log_out = [], []
    for i, path in enumerate(sources, 1):
        lines = _tail(path, max_log_lines)
        if not lines: continue
        raw += lines; label = os.path.basename(path) if os.path.basename(path) in LOG_FILES else f"log {i}"
        log_out.append(f"===== {label} (last {len(lines)} lines) =====")
        log_out += [san.clean(l) for l in lines]
    errors = error_classes(raw)
    for e in errors: e["error"] = san.clean(e["error"]); e["where"] = san.clean(e["where"])
    parts = {"about.json": json.dumps(about(app_dir), indent=1, ensure_ascii=False),
             "program_files.json": json.dumps(program_files(app_dir), indent=1, ensure_ascii=False),
             "errors.json": json.dumps(errors, indent=1, ensure_ascii=False)}
    if include_log: parts["log.txt"] = "\n".join(log_out) + "\n" if log_out else "(the logs are empty)\n"
    # the last check, on what is really going into the file
    leftover = 0; home_dir = os.path.expanduser("~")
    for name in ("errors.json", "log.txt", "about.json"):
        text = parts.get(name)
        if text is None: continue
        bare = _ALIAS.sub(" ", text)                                 # the stand-ins themselves are not names
        bad = outbound_policy.has_secret(text) or (len(home_dir) > 3 and home_dir in text) or any(rx.search(bare) for rx, _a in san.rules)
        if bad:
            leftover += 1; parts[name] = "(left out: the last check still found a name, a path or a credential in this part)\n" if name != "about.json" else san.clean(text)
    manifest = _manifest(parts, san, len(raw), include_log, leftover, len(known))
    dest_zip = os.path.abspath(dest_zip); os.makedirs(os.path.dirname(dest_zip), exist_ok=True); tmp = dest_zip + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MANIFEST.txt", manifest)
        for name, text in parts.items(): z.writestr(name, text)
    os.replace(tmp, dest_zip)
    return {"path": dest_zip, "files": ["MANIFEST.txt"] + list(parts), "log_lines": len(raw), "replaced": dict(san.counts), "leftover": leftover}


def _manifest(parts, san, n_lines, include_log, leftover, n_known):
    c = san.counts
    L = ["Origin Plot Studio - diagnostic bundle", "=" * 38, "",
         "This file lists exactly what is in this zip. Please look through it (log.txt above all) before you send it.",
         "The bundle was written to your disk only. The app has not sent it anywhere.", "",
         "IN THIS ZIP", ""]
    what = {"about.json": "versions of the app, Python and the packages; the system (not the name of the computer or the user); the security profile, the outbound level and which outbound channels are on; the kind of key store",
            "program_files.json": "the installed program files with size and SHA-256, compared with the list of the release; other files in the program folder are only counted, not named",
            "errors.json": "the kinds of errors found in the logs (class name, program file and line, how often)",
            "log.txt": f"the last lines of the app's logs ({n_lines} lines read), sanitized as described below"}
    for name in ["MANIFEST.txt"] + list(parts):
        L.append(f"  {name:<20} {what.get(name, 'this list')}" + (f"  [{len(parts[name].encode('utf-8'))} bytes]" if name in parts else ""))
    if not include_log: L.append("  (log.txt was left out on request)")
    L += ["", "REPLACED BEFORE WRITING", "",
          f"  credentials (keys, tokens, Authorization values)   -> [removed]     {c['credentials']} time(s)",
          f"  paths of folders and files                         -> <folder>      {c['paths']} time(s)   (program files keep their own name: <app>/name.py)",
          f"  names the app knows as yours ({n_known} names)".ljust(53) + f"-> <file 1> ...  {c['names']} time(s)   (files, samples, graphs, projects, your user name, the computer)",
          f"  other names of data files                          -> <file>        {c['files']} time(s)",
          f"  rows of numbers (four or more in a row)            -> <numbers>     {c['numbers']} time(s)", "",
          "NOT IN THIS ZIP", "",
          "  measurement data and data files; project files and project archives; settings; saved sessions; lessons and",
          "  learned formats of the assistant; credentials; the names above; real paths.", "",
          "WHAT THIS CANNOT PROMISE", "",
          "  A name the app has never seen (typed into a message, part of an error text of another program) can still be in",
          "  log.txt. Read it. If you are not sure, send the bundle without it (errors.json is usually enough to start).", ""]
    if leftover: L += [f"NOTE: the last check still found a name, a path or a credential in {leftover} part(s); those parts were left out.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "ops_diagnostics.zip")
    info = build_bundle(out)
    print("written: " + info["path"]); print("replaced: " + ", ".join(f"{k} {v}" for k, v in info["replaced"].items()))

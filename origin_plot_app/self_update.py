"""
self_update.py - new versions and AI repairs, each behind the same safety net.

Nothing here installs anything by itself. Every path ends in a question to the user, and every install first
copies the current program into a backup folder, so "Undo the last update or fix" brings it back.

1. UPDATES FROM A PLACE YOU CONTROL
   source = a folder (the newest Origin_Plot_App_*.zip in it), a link to a .zip, a link to a small
   latest.json ({"version": "5.16", "url": "https://.../Origin_Plot_App_5.16.zip", "notes": "..."}),
   or "github:owner/repository" (its latest release).
   There is no signature on a zip: only point the app at a place that you, or someone you trust, control.

2. AI REPAIRS WITH A TRIAL COPY
   The traceback of the last problem and the functions it names are sent to the AI you linked. Its answer is a
   list of exact text replacements. They are applied to a TRIAL COPY of the program. The trial copy must compile
   and must produce exactly the same Origin commands as the current program for every example file. Only then is
   "Install this fix" offered.
   Limits, said plainly: the check only covers what the example files cover; a fix for a new kind of file cannot be
   fully verified; the composed paper figures (paper_figures.py) are not part of the check; parts of the program
   code leave this computer and go to the AI.
"""
import os, re, sys, json, shutil, zipfile, tempfile, subprocess, datetime, difflib

PROGRAM_EXT = (".py", ".pyw", ".bat", ".vbs", ".ico")
PROGRAM_FILES = ("app.png", "WHATS_NEW.txt", "HOW_TO_INSTALL.txt", "README.txt", "UI_REFRESH_NOTES.txt", "XRD_workbook_template.xlsx", "phase_amounts_template.csv", "xrd_phase_library.csv")
PROGRAM_DIRS = ("figure_recipes", "phase_library", "examples_synthetic", "gallery", "opstudio")
NEVER = ("settings.json", "settings_modern.json", "last_session.json", "last_run_log.txt", "console_output.txt", "startup_error.txt", "error_log.txt")           # yours: never replaced, never put into a backup


class UpdateError(Exception):
    pass


# ---------------------------------------------------------------------------------------------- versions
def version_of(folder):
    try:
        m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', open(os.path.join(folder, "smart_plots.py"), encoding="utf-8").read(), re.M)
        return m.group(1) if m else ""
    except Exception: return ""

def vkey(v): return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)

def newer(a, b): return vkey(a) > vkey(b)

def incomplete(app_dir):
    """True when a part of the program is missing here (a folder added by a newer version that an older updater did not copy).
    Then the same version is fetched once more and installed completely."""
    need = (os.path.join("opstudio", "__init__.py"), os.path.join("opstudio", "catalog.json"))
    return any(not os.path.isfile(os.path.join(app_dir, f)) for f in need)


def program_files(folder):
    """The files that are the program (relative paths). Your settings, sessions and results are not among them."""
    out = []
    for f in sorted(os.listdir(folder)):
        p = os.path.join(folder, f)
        if os.path.isfile(p) and f not in NEVER and (f.lower().endswith(PROGRAM_EXT) or f in PROGRAM_FILES): out.append(f)
    for d in PROGRAM_DIRS:
        for base, _, files in os.walk(os.path.join(folder, d)):
            for f in sorted(files):
                if "__pycache__" not in base: out.append(os.path.relpath(os.path.join(base, f), folder))
    return out


# ---------------------------------------------------------------------------------------------- finding a new version
TOKEN = ""            # only for a private GitHub repository: a read-only access token, set by the app from its settings

def _get(url, timeout=60, raw=False):
    """Download over https. The certificate is always checked; net.py tries Windows' own tools when Python cannot verify it."""
    import net
    if not str(url).lower().startswith("https://"): raise UpdateError("only https links are used for updates")
    h = {"User-Agent": "origin-plot-app-updater", "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json, application/json, */*"}
    if TOKEN and "github" in str(url).lower(): h["Authorization"] = "Bearer " + TOKEN
    return net.fetch(url, h, timeout)

def explain(e, what="the place for updates"):
    """A download problem in plain words: what happened and what the user can do."""
    import net
    if isinstance(e, net.CertificateProblem) or net.is_certificate_error(e):
        return net.WHY_CERTIFICATE + " You can still update: download the zip of the new version in your browser and use Help > 'Install an update from a zip file\u2026'."
    if isinstance(e, net.HttpError):
        if e.code == 404: return f"I could not find {what}. Is the name right, and is it public (or is a token set)?"
        if e.code in (403, 429): return "GitHub is refusing requests from this network for the moment (too many in one hour). Try again in a while."
        if e.code == 401: return "The access token for the private repository was not accepted."
        return f"The server answered with an error ({e.code}). Try again later."
    return f"I could not connect ({str(e)[:160]}). Check the internet connection, then try again."

def find_update(source, current):
    """Is there a newer version at `source`? Returns {"version", "zip" (a path or a link), "notes"} or None."""
    source = normalize_source(source) or str(source or "").strip().strip('"')
    if not source or source == "off": raise UpdateError("no place for updates is set")
    best = None
    if os.path.isdir(source):
        for f in os.listdir(source):
            if not f.lower().endswith(".zip"): continue
            v = _zip_version(os.path.join(source, f))
            if v and newer(v, current) and (best is None or newer(v, best["version"])): best = {"version": v, "zip": os.path.join(source, f), "notes": ""}
        return best
    if os.path.isfile(source) and source.lower().endswith(".zip"):
        v = _zip_version(source); return {"version": v, "zip": source, "notes": ""} if v and newer(v, current) else None
    if source.lower().startswith("github:"):
        # A GitHub repository: its latest release if it has releases, otherwise simply what is on its main branch.
        # So whoever looks after the app only has to put the new files into the repository; the app sees the higher VERSION.
        repo = source.split(":", 1)[1].strip().strip("/"); api = "https://api.github.com/repos/" + repo
        if not TOKEN:
            # A public repository is read as plain files, not through GitHub's API: the API allows only 60 requests an hour for a
            # whole network, which several people in one university would use up between them.
            last = None
            for folder in ("origin_plot_app/", ""):
                try: txt = _get(f"https://raw.githubusercontent.com/{repo}/main/{folder}smart_plots.py?t={int(__import__('time').time())}").decode("utf-8", "replace")
                except Exception as e: last = e; continue
                m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', txt, re.M); v = m.group(1) if m else ""
                if not v: continue
                if not newer(v, current): return None
                notes = ""
                try: notes = next((l.strip() for l in _get(f"https://raw.githubusercontent.com/{repo}/main/{folder}WHATS_NEW.txt?t={int(__import__('time').time())}").decode("utf-8", "replace").splitlines() if l.strip() and not l.startswith("#")), "")[:300]
                except Exception: pass
                return {"version": v, "zip": f"https://github.com/{repo}/archive/refs/heads/main.zip", "notes": notes, "page": f"https://github.com/{repo}/archive/refs/heads/main.zip"}
            raise UpdateError(explain(last, f"the repository {repo}") if last is not None else f"The repository {repo} holds no smart_plots.py with a VERSION, so it is not a copy of this app.")
        try:
            d = json.loads(_get(api + "/releases/latest").decode("utf-8")); v = str(d.get("tag_name") or d.get("name") or "")
            z = next((a["browser_download_url"] for a in d.get("assets") or [] if str(a.get("name", "")).lower().endswith(".zip")), None) or d.get("zipball_url")
            if z and newer(v, current): return {"version": v.lstrip("vV"), "zip": z, "notes": str(d.get("body") or "")[:1500]}
        except Exception: pass                               # no releases: look at the branch
        last = None
        for path in ("smart_plots.py", "origin_plot_app/smart_plots.py"):
            try: txt = _get(api + "/contents/" + path, raw=True).decode("utf-8", "replace")
            except Exception as e: last = e; continue
            m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', txt, re.M); v = m.group(1) if m else ""
            if not v: continue
            notes = ""
            try: notes = str(json.loads(_get(api + "/commits?per_page=1").decode("utf-8"))[0]["commit"]["message"])[:600]
            except Exception: pass
            return {"version": v, "zip": api + "/zipball", "notes": notes} if newer(v, current) else None
        raise UpdateError(explain(last, f"the repository {repo}") if last is not None else f"The repository {repo} holds no smart_plots.py with a VERSION, so it is not a copy of this app.")
    if source.lower().endswith(".json"):
        d = json.loads(_get(source).decode("utf-8")); v = str(d.get("version", ""))
        return {"version": v, "zip": d.get("url"), "notes": str(d.get("notes") or "")[:1500]} if d.get("url") and newer(v, current) else None
    if source.lower().startswith("https://"): return {"version": "", "zip": source, "notes": "the version is known after the download"}
    raise UpdateError("the place for updates must be a folder, a .zip, a link to a .zip or latest.json, or github:owner/repository")

def _zip_version(path):
    try:
        with zipfile.ZipFile(path) as z:
            n = next((m for m in z.namelist() if m.replace("\\", "/").endswith("smart_plots.py")), None)
            if not n: return ""
            m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', z.read(n).decode("utf-8", "replace"), re.M); return m.group(1) if m else ""
    except Exception: return ""

def fetch_and_unpack(info, work):
    """Get the zip (download it when it is a link) and unpack it safely. Returns the folder that holds origin_plot_app.py."""
    z = info["zip"]; os.makedirs(work, exist_ok=True)
    if str(z).lower().startswith("https://"):
        local = os.path.join(work, "update.zip")
        with open(local, "wb") as f: f.write(_get(z, timeout=300))
        z = local
    if not os.path.isfile(z): raise UpdateError(f"the update file is not there: {z}")
    dest = os.path.join(work, "unpacked"); root = os.path.abspath(dest)
    with zipfile.ZipFile(z) as zf:
        for m in zf.infolist():                               # no file may land outside the trial folder
            t = os.path.abspath(os.path.join(dest, m.filename))
            if not (t == root or t.startswith(root + os.sep)): raise UpdateError("the zip holds a file with an unsafe path; it is not installed")
        zf.extractall(dest)
    for base, _, files in os.walk(dest):
        if "origin_plot_app.py" in files and "smart_plots.py" in files: return os.path.abspath(base)
    raise UpdateError("the zip does not hold the program (origin_plot_app.py and smart_plots.py)")


# ---------------------------------------------------------------------------------------------- the check
def _dry(app_dir, data_file, work):
    """The Origin commands that the program in app_dir makes for one data file (no Origin needed). Returns (ok, text)."""
    d = os.path.join(work, "data"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d); f = os.path.join(d, os.path.basename(data_file)); shutil.copy2(data_file, f)
    env = dict(os.environ); env["PYTHONDONTWRITEBYTECODE"] = "1"; env["MPLBACKEND"] = "Agg"
    try: r = subprocess.run([sys.executable, os.path.join(app_dir, "origin_plot_app.py"), "--dry-run", f], cwd=d, env=env, capture_output=True, text=True, timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e: return False, f"could not be run: {e}"
    cmds = os.path.join(d, "dry_commands.txt")
    if r.returncode != 0 or not os.path.isfile(cmds): return False, (r.stderr or r.stdout or "no output")[-1500:]
    t = open(cmds, encoding="utf-8", errors="replace").read()
    for a in (d, d.replace("\\", "/"), d.replace("\\", "\\\\")): t = t.replace(a, "<DATA>")
    t = re.sub(r"\d{4}-\d{2}-\d{2}[ _T]\d{2}[:.]?\d{2}[:.]?\d{2}", "<TIME>", t)
    return True, t

DEFAULT_SOURCE = "github:EmmanuelMache/origin-plot-studio"          # where new versions of this app are published

def normalize_source(text):
    """Whatever was typed or pasted as the place for updates, in the one form the app uses. "" = not understood.
    A web address of a GitHub repository, 'owner/repository' and 'github: owner/repository' all mean the same."""
    t = str(text or "").strip().strip('"').strip("'").strip()
    if not t: return ""
    if t.lower() == "off": return "off"
    if os.path.isdir(t) or (os.path.isfile(t) and t.lower().endswith(".zip")): return t
    m = re.search(r"github\.com[/:]+([\w.-]+)/([\w.-]+)", t, re.I) or re.match(r"^(?:github\s*:\s*)?([\w.-]+)\s*/\s*([\w.-]+?)/?$", t, re.I)
    if m and not t.lower().endswith((".zip", ".json")):
        repo = m.group(2)[:-4] if m.group(2).lower().endswith(".git") else m.group(2)
        return f"github:{m.group(1)}/{repo}"
    if t.lower().startswith("https://"): return t
    return ""

def examples(app_dir, quick=False):
    """The example files the check redraws. quick: one file of each kind (the replicate files _rep2, _rep3 ... add nothing new)."""
    d = os.path.join(app_dir, "examples_synthetic")
    fs = [os.path.join(d, f) for f in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, f))] if os.path.isdir(d) else []
    if not quick: return fs
    seen, out = set(), []
    for f in fs:
        k = re.sub(r"_rep\d+$", "", os.path.splitext(os.path.basename(f))[0])
        if k not in seen: seen.add(k); out.append(f)
    return out

def check(trial_dir, app_dir, log=None, stop=None, quick=False, progress=None):
    """The trial copy must compile and must make the same Origin commands as the current program for every example file.
    The examples are redrawn several at a time. Returns {"ok": bool, "lines": [what was checked], "same": n, "different": [...], "covered": n}."""
    import py_compile
    from concurrent.futures import ThreadPoolExecutor
    say = log or (lambda m: None); lines = []; different = []; same = 0; trial_dir, app_dir = os.path.abspath(trial_dir), os.path.abspath(app_dir)
    for f in sorted(os.listdir(trial_dir)):
        if f.endswith((".py", ".pyw")):
            try: py_compile.compile(os.path.join(trial_dir, f), cfile=os.path.join(tempfile.gettempdir(), "opa_check.pyc"), doraise=True)
            except Exception as e: return {"ok": False, "lines": [f"{f} does not compile: {str(e)[-400:]}"], "same": 0, "different": [f], "covered": 0}
    lines.append("every program file compiles")
    work = tempfile.mkdtemp(prefix="opa_check_"); ex = examples(app_dir, quick); done = [0]
    def one(job):
        i, f = job
        if stop and stop(): return (os.path.basename(f), "stopped", "", "")
        ok0, a = _dry(app_dir, f, os.path.join(work, f"now{i}"))
        ok1, b = _dry(trial_dir, f, os.path.join(work, f"trial{i}")) if ok0 else (False, "")
        done[0] += 1; say(f"Checked {done[0]} of {len(ex)} example files")
        if progress: progress(done[0] / max(1, len(ex)))
        return (os.path.basename(f), "skip" if not ok0 else "same" if (ok1 and a == b) else "failed" if not ok1 else "different", a, b)
    try:
        with ThreadPoolExecutor(max_workers=max(1, min(4, (os.cpu_count() or 2) - 1))) as pool: results = list(pool.map(one, enumerate(ex)))
    finally: shutil.rmtree(work, ignore_errors=True)
    for nm, how, a, b in results:
        if how == "skip": lines.append(f"{nm}: left out (the current program cannot draw it either)")
        elif how == "same": same += 1; lines.append(f"{nm}: same Origin commands ({a.count(chr(10)) + 1} lines)")
        elif how == "stopped": different.append("stopped"); lines.append("stopped before all examples were compared")
        elif how == "failed": different.append(nm); lines.append(f"{nm}: the trial copy FAILED: {b[-300:]}")
        else:
            different.append(nm); d_ = [l for l in difflib.unified_diff(a.splitlines(), b.splitlines(), "now", "trial", lineterm="", n=0)][:12]; lines.append(f"{nm}: DIFFERENT Origin commands:\n      " + "\n      ".join(d_))
    if not ex: lines.append("there are no example files, so the drawing could not be compared")
    return {"ok": not different and same > 0, "lines": lines, "same": same, "different": different, "covered": len(ex)}


# ---------------------------------------------------------------------------------------------- install and undo
def backup(app_dir, store, why=""):
    """Copy the current program into a new folder of `store`. Returns that folder."""
    d = os.path.join(store, datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_v" + re.sub(r"[^0-9A-Za-z.]+", "_", version_of(app_dir) or "x"))
    for rel in program_files(app_dir):
        t = os.path.join(d, rel); os.makedirs(os.path.dirname(t), exist_ok=True); shutil.copy2(os.path.join(app_dir, rel), t)
    with open(os.path.join(d, "backup.json"), "w", encoding="utf-8") as f: json.dump({"version": version_of(app_dir), "why": why, "files": program_files(app_dir)}, f, indent=1)
    return d

def install(trial_dir, app_dir, store, why="", only=None):
    """Back up the current program, then copy the program files of the trial copy over it. Returns (backup folder, files changed)."""
    b = backup(app_dir, store, why); changed = []
    for rel in (only or program_files(trial_dir)):
        s, t = os.path.join(trial_dir, rel), os.path.join(app_dir, rel)
        if os.path.basename(rel) in NEVER or not os.path.isfile(s): continue
        try: same = os.path.isfile(t) and open(s, "rb").read() == open(t, "rb").read()
        except Exception: same = False
        if not same: os.makedirs(os.path.dirname(t), exist_ok=True); shutil.copy2(s, t); changed.append(rel)
    try:
        j = os.path.join(b, "backup.json"); d = json.load(open(j, encoding="utf-8")); d["changed"] = changed; d["installed"] = version_of(app_dir); json.dump(d, open(j, "w", encoding="utf-8"), indent=1)
    except Exception: pass
    shutil.rmtree(os.path.join(app_dir, "__pycache__"), ignore_errors=True)
    return b, changed

def backups(store):
    try: return sorted([os.path.join(store, d) for d in os.listdir(store) if os.path.isfile(os.path.join(store, d, "backup.json"))])
    except Exception: return []

def undo(app_dir, store):
    """Put back the newest backup. Files the update had added are removed. Returns a line that says what was restored."""
    bs = backups(store)
    if not bs: raise UpdateError("there is no earlier version to go back to")
    b = bs[-1]; d = json.load(open(os.path.join(b, "backup.json"), encoding="utf-8")); had = set(d.get("files") or [])
    for rel in d.get("changed") or []:
        if rel not in had and os.path.basename(rel) not in NEVER:
            try: os.remove(os.path.join(app_dir, rel))
            except Exception: pass
    for rel in had:
        s = os.path.join(b, rel)
        if os.path.isfile(s): os.makedirs(os.path.dirname(os.path.join(app_dir, rel)), exist_ok=True); shutil.copy2(s, os.path.join(app_dir, rel))
    shutil.rmtree(os.path.join(app_dir, "__pycache__"), ignore_errors=True)
    shutil.move(b, b + "_restored")
    return f"version {d.get('version') or '?'} is back" + (f" (undone: {d.get('why')})" if d.get("why") else "")


# ---------------------------------------------------------------------------------------------- AI repair
REPAIR_SYSTEM = ("You repair a bug in a Python desktop program (Tkinter, pandas, matplotlib; it draws scientific graphs in Origin). You are given the traceback and the functions it names. "
                 "Answer with ONE JSON object and nothing else: {\"explanation\": \"<two plain sentences: the cause and what you change>\", \"edits\": [{\"file\": \"<file name>\", \"old\": \"<exact text that is in the file once>\", \"new\": \"<its replacement>\"}]}. "
                 "Rules: the smallest change that fixes this error; 'old' must be copied exactly from the code you were shown, with its indentation, and be long enough to occur only once; at most 4 edits; "
                 "never change what is drawn for inputs that work today; no new imports of packages that are not already used; no network access, no file deletion, no subprocess, no eval or exec. "
                 "If you cannot fix it safely from what you see, answer {\"explanation\": \"<why not>\", \"edits\": []}.")
FORBIDDEN = (r"\beval\s*\(", r"\bexec\s*\(", r"\bos\.system\b", r"\bsubprocess\b", r"\burllib\b", r"\brequests\b", r"\bsocket\b", r"\bshutil\.rmtree\b", r"\bos\.remove\b", r"\b__import__\b", r"\bctypes\b")

def code_for(problem, app_dir, around=45, limit=14000):
    """The parts of the program that the traceback names: {file: text with line numbers}. Only files of the program itself."""
    out = {}; total = 0
    for m in re.finditer(r'File "([^"]+)", line (\d+)', problem):
        p, ln = m.group(1), int(m.group(2)); nm = os.path.basename(p)
        if os.path.dirname(os.path.abspath(p)) != os.path.abspath(app_dir) or not nm.endswith(".py"): continue
        try: src = open(os.path.join(app_dir, nm), encoding="utf-8").read().splitlines()
        except Exception: continue
        a, b = max(0, ln - 1 - around), min(len(src), ln + around); part = "\n".join(l[:900] for l in src[a:b])
        if total + len(part) > limit: break
        total += len(part); out.setdefault(nm, []).append(f"--- {nm}, lines {a + 1} to {b} (the error is in line {ln})\n{part}")
    return {k: "\n\n".join(v) for k, v in out.items()}

def repair_message(problem, app_dir):
    code = code_for(problem, app_dir)
    if not code: raise UpdateError("the last problem does not point into the program's own code, so there is nothing I could ask the AI to repair")
    return "TRACEBACK:\n" + problem[-3500:] + "\n\nCODE:\n" + "\n\n".join(code.values()), sorted(code)

def parse_edits(reply):
    m = re.search(r"\{.*\}", str(reply), re.S)
    if not m: raise UpdateError("the AI did not answer with a repair I can read")
    try: d = json.loads(m.group(0))
    except Exception as e: raise UpdateError(f"the AI's answer is not valid JSON ({e})")
    ed = [e for e in (d.get("edits") or []) if isinstance(e, dict) and e.get("file") and isinstance(e.get("old"), str) and isinstance(e.get("new"), str)]
    return str(d.get("explanation") or "").strip(), ed[:4]

def make_trial(app_dir, edits, work):
    """A full copy of the program with the edits applied. Raises when an edit does not fit exactly or does something a repair may not do."""
    if not edits: raise UpdateError("the AI proposed no change")
    trial = os.path.join(work, "trial"); shutil.rmtree(trial, ignore_errors=True)
    for rel in program_files(app_dir):
        t = os.path.join(trial, rel); os.makedirs(os.path.dirname(t), exist_ok=True); shutil.copy2(os.path.join(app_dir, rel), t)
    touched = []
    for e in edits:
        nm = os.path.basename(str(e["file"]))
        if not nm.endswith(".py") or not os.path.isfile(os.path.join(trial, nm)) or nm == "self_update.py": raise UpdateError(f"the repair wants to change '{e['file']}', which is not a program file it may change")
        p = os.path.join(trial, nm); src = open(p, encoding="utf-8").read()
        if src.count(e["old"]) != 1: raise UpdateError(f"the repair does not fit {nm}: the text to replace is there {src.count(e['old'])} times, not once")
        for pat in FORBIDDEN:
            if re.search(pat, e["new"]) and not re.search(pat, e["old"]): raise UpdateError(f"the repair adds something a repair may not add ({pat.strip(chr(92) + 'b()')}); it is not tried")
        open(p, "w", encoding="utf-8").write(src.replace(e["old"], e["new"])); touched.append(nm)
    return trial, sorted(set(touched))

def diff_text(app_dir, trial_dir, files):
    out = []
    for nm in files:
        a = open(os.path.join(app_dir, nm), encoding="utf-8").read().splitlines(); b = open(os.path.join(trial_dir, nm), encoding="utf-8").read().splitlines()
        out += [l[:400] for l in difflib.unified_diff(a, b, nm + " (now)", nm + " (with the fix)", lineterm="", n=2)]
    return "\n".join(out)

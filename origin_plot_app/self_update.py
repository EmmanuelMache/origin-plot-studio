"""
self_update.py - new versions and AI repairs, each behind the same safety net.

Nothing here installs anything by itself. Every path ends in a question to the user, and every install first
copies the current program into a backup folder, so "Undo the last update or fix" brings it back.

1. UPDATES
   source = a folder (the newest zip in it), a link to a .zip, a link to a small latest.json
   ({"version": "5.16", "url": "https://.../Origin_Plot_App_5.16.zip", "notes": "...", "manifest": "...", "sig": "..."}),
   or "github:owner/repository".

   SIGNED RELEASES (update_verify.py). A release carries manifest.json and manifest.sig (an Ed25519 signature of the
   publisher; the public key is part of the installed program, update_trust.py). They are found
     - on GitHub as the release assets manifest.json, manifest.sig and the zip the manifest names;
     - for a zip on your disk ("Install an update from a zip file"): either the zip is a SIGNED BUNDLE (one zip that
       holds manifest.json, manifest.sig and the program zip - made by tools/sign_release.py bundle), or the two files
       lie beside it as <name>.zip.manifest.json / <name>.zip.manifest.sig, or as manifest.json / manifest.sig;
     - for a link: the linked zip is a signed bundle, or latest.json names "manifest" and "sig".
   The signature, the size and SHA-256 of the zip, the version, the system and the structure of the zip are checked
   BEFORE a single file of the update is compiled, imported or run. A manifest that is present but wrong always stops
   the update, in every profile.

   The profile of this copy (outbound_policy.profile()) decides what happens without a signature:
     'friends'   refused. A zip is not trusted because of its name or because it came from the right place.
                 The trial check below (which RUNS the new program) is never started on an unverified update.
     'owner'     the developer's own copy: installed as before from the place you set, and the window and the log say
                 plainly that it is NOT verified.

   The trial check draws the example files with the new version and compares the Origin commands. It runs the new
   program as you, with your rights: it is a comparison of drawings, not a sandbox.

2. AI REPAIRS WITH A TRIAL COPY ('owner' profile only; not available in a 'friends' build)
   The traceback of the last problem and the functions it names are sent to the AI you linked. Its answer is a
   list of exact text replacements. They are applied to a TRIAL COPY of the program. The trial copy must compile
   and must produce exactly the same Origin commands as the current program for every example file. Only then is
   "Install this fix" offered.
   Limits, said plainly: the check only covers what the example files cover; a fix for a new kind of file cannot be
   fully verified; the composed paper figures (paper_figures.py) are not part of the check; parts of the program
   code leave this computer and go to the AI; the trial copy is code written by a model and it is RUN on this computer
   with your rights - the list of forbidden words below is a filter, not isolation.

3. INSTALLING is done in two steps with a journal (<backups>/install_journal.json): the new files are first copied
   beside the old ones under a temporary name, then each is put in place with one rename. recover() finishes or rolls
   back an install that was cut off (power loss, a crash); the app calls it at its next start.
"""
import os, re, sys, json, shutil, zipfile, tempfile, subprocess, datetime, difflib, base64, hashlib, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM_EXT = (".py", ".pyw", ".bat", ".vbs", ".ico")
PROGRAM_FILES = ("app.png", "WHATS_NEW.txt", "HOW_TO_INSTALL.txt", "README.txt", "UI_REFRESH_NOTES.txt", "XRD_workbook_template.xlsx", "phase_amounts_template.csv", "xrd_phase_library.csv", "security_profile.json",
                 "requirements.txt", "requirements.lock")          # the tested package set travels with the program: Setup and the launchers install from the lock of THIS version
PROGRAM_DIRS = ("figure_recipes", "phase_library", "examples_synthetic", "gallery", "opstudio")
NEVER = ("settings.json", "settings_modern.json", "last_session.json", "last_run_log.txt", "console_output.txt", "startup_error.txt", "error_log.txt")           # yours: never replaced, never put into a backup
# Part of the program, but replaced ONLY by an update whose signature was verified: the publisher keys this copy trusts and
# the profile of this build. An unsigned update, an AI repair or anything imported cannot change them.
PROTECTED = ("update_trust.py", "security_profile.json")
JOURNAL = "install_journal.json"
STAGE_EXT = ".ops_new"
TOKEN_NAME = "github:update_token"


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
                if "__pycache__" not in base and not f.endswith(STAGE_EXT): out.append(os.path.relpath(os.path.join(base, f), folder))
    return out


# ---------------------------------------------------------------------------------------------- the profile of this copy
def profile():
    """'friends' or 'owner' (outbound_policy.profile()). When that cannot be asked, the stricter one."""
    try:
        import outbound_policy
        return outbound_policy.profile()
    except Exception:
        return "friends"

def signed_only(): return profile() == "friends"

UNSIGNED_REFUSED = ("This update is not signed by the publisher, so it is not installed. This build installs only signed versions: "
                    "a zip is not trusted because of its name or the place it came from. Ask whoever gave you the app for the signed release.")
NO_SIGNED_RELEASE = ("No signed version is published at the place for updates yet. This build installs only versions signed by the publisher; nothing was changed.")
NOT_RUN_UNVERIFIED = ("The trial check runs the new program on this computer, so it is only started for an update whose signature was verified. "
                      "This one was not verified; nothing of it was run.")
_VERIFIED = {}                # folder of an unpacked update -> its verified manifest (kept in memory only: a zip cannot write it)
_TRUSTED_DIRS = set()         # folders of the installed program that check() was given by the app

def _real(p): return os.path.normcase(os.path.realpath(os.path.abspath(str(p))))

def verified(trial_dir):
    """The signed manifest this unpacked update was verified with, or None (not verified)."""
    return _VERIFIED.get(_real(trial_dir))

def verification_note(trial_dir):
    """One plain line for the window and the log."""
    m = verified(trial_dir)
    if m: return f"Verified: version {m['version']} is signed by the publisher (key {m['key_id']})."
    return ("NOT verified: this update carries no signature of the publisher. It comes from the place set under 'Where updates come from'; "
            "install it only if that place is yours or you trust it.")


# ---------------------------------------------------------------------------------------------- finding a new version
TOKEN = ""            # only for a private GitHub repository: a read-only access token, kept in the protected store (set_token / load_token)
_REPO = [""]          # the repository the configured place for updates names: the only one the token is for
MAX_JSON = 5 * 1024 * 1024

def _repo_ok(repo):
    parts = str(repo or "").split("/")
    return len(parts) == 2 and all(re.fullmatch(r"[\w.-]{1,100}", p) and p not in (".", "..") for p in parts)

def token_allowed(url, repo=None):
    """May the update token be sent to this address? Only to https://api.github.com (port 443) on the routes
    /repos/<owner>/<repository>/... of the configured repository. Not to raw.githubusercontent.com, codeload, the hosts
    that store release files, a host that looks similar, an address that only has 'github' in its path, another port, or
    an address with a user name in it. The address is parsed; nothing is decided by searching for a word."""
    repo = repo or _REPO[0]
    if not _repo_ok(repo): return False
    try:
        import outbound_policy as op
        if not op.token_allowed(url, [("api.github.com", 443, ["/repos"])]): return False
        path = urllib.parse.urlsplit(str(url).strip()).path
    except Exception: return False
    low = path.lower(); segs = path.split("/")
    if "\\" in path or any(x in low for x in ("%2e", "%2f", "%5c", "%00")) or any(s in (".", "..") for s in segs): return False
    owner, name = repo.lower().split("/")
    return len(segs) >= 4 and segs[1] == "repos" and segs[2].lower() == owner and segs[3].lower() == name

def _allowed(channel, url=None):
    """The outbound policy, asked where the request is made. Local-only mode ends here with a plain message."""
    import outbound_policy as op
    try: return op.require(channel, url)
    except op.Blocked as e: raise UpdateError(str(e))

def _get(url, timeout=60, raw=False, *, repo=None, accept=None, channel="update_check", max_bytes=None):
    """Download over https. The certificate is always checked; net.py tries Windows' own tools when Python cannot verify it.
    The policy is asked first (and again by net.py at every redirect); the token goes only where token_allowed says."""
    import net, outbound_policy as op
    if not str(url).lower().startswith("https://"): raise UpdateError("only https links are used for updates")
    _allowed(channel, url)
    repo = repo or _REPO[0]
    h = {"User-Agent": "origin-plot-app-updater", "Accept": accept or ("application/vnd.github.raw+json" if raw else "application/vnd.github+json, application/json, */*")}
    keep = lambda u: token_allowed(u, repo)
    if TOKEN and keep(url): h["Authorization"] = "Bearer " + TOKEN
    try: return net.fetch(url, h, timeout, channel=channel, max_bytes=max_bytes, keep_credentials=keep)
    except op.Blocked as e: raise UpdateError(str(e))
    except net.TooLarge: raise UpdateError("The download is larger than it may be (larger than its signed manifest states, or than the app accepts). It was stopped; nothing was changed.")

def set_token(value):
    """Keep (or, with an empty value, forget) the read-only GitHub token of a private update repository. It goes into the
    protected store of the app (secure_store), never into a settings file. Returns 'dpapi', 'keyring', 'session' (kept
    only until the app closes) or '' (removed)."""
    global TOKEN
    import secure_store
    v = str(value or "").strip(); TOKEN = v
    if not v: secure_store.delete(TOKEN_NAME); return ""
    return secure_store.put(TOKEN_NAME, v)

def load_token(legacy=None):
    """Read the token from the protected store into TOKEN. `legacy` is what an older version kept in the settings file
    (key 'update_token'): it is moved into the store once. Returns {"token": bool, "drop_legacy": bool, "note": str};
    when drop_legacy is True the caller removes 'update_token' from its settings file - also when this system has no
    protected store (then the token lives until the app closes and is asked for again)."""
    global TOKEN
    out = {"token": False, "drop_legacy": False, "note": ""}
    try:
        import secure_store
        tok = secure_store.get(TOKEN_NAME)
        if legacy:
            out["drop_legacy"] = True
            if not tok:
                try:
                    import assistant
                    old = assistant.reveal_key(legacy)
                except Exception: old = ""
                if old:
                    how, _ = secure_store.migrate_plain(TOKEN_NAME, old); tok = old
                    out["note"] = ("The access token for updates was moved from the settings file into the protected store of this system." if how in ("dpapi", "keyring") else
                                   "This system has no protected store the app can use: the access token for updates was removed from the settings file and is kept only until the app closes. Enter it again next time.")
                else: out["note"] = "The access token for updates in the settings file could not be read on this computer; it was removed. Enter it again if the repository is private."
        TOKEN = tok or ""; out["token"] = bool(TOKEN)
    except Exception:
        TOKEN = ""
    return out

def explain(e, what="the place for updates"):
    """A download problem in plain words: what happened and what the user can do."""
    import net
    if isinstance(e, UpdateError) or isinstance(e, PermissionError) and type(e).__name__ == "Blocked": return str(e)
    if isinstance(e, net.CertificateProblem) or net.is_certificate_error(e):
        return net.WHY_CERTIFICATE + " You can still update: download the zip of the new version in your browser and use Help > 'Install an update from a zip file…'."
    if isinstance(e, net.HttpError):
        if e.code == 404: return f"I could not find {what}. Is the name right, and is it public (or is a token set)?"
        if e.code in (403, 429): return "GitHub is refusing requests from this network for the moment (too many in one hour). Try again in a while."
        if e.code == 401: return "The access token for the private repository was not accepted."
        return f"The server answered with an error ({e.code}). Try again later."
    return f"I could not connect ({_redact(e)[:160]}). Check the internet connection, then try again."

def _redact(text):
    try:
        import outbound_policy
        return outbound_policy.redact(str(text))
    except Exception: return "details withheld"

def _b64(b): return base64.b64encode(bytes(b)).decode("ascii")

def _signed_github(repo, api, current):
    """The latest SIGNED release of a GitHub repository: its manifest is fetched and its signature verified here, before
    anything else of the release is looked at. Returns the info for fetch_and_unpack, or None when it is not newer."""
    import net, update_verify as uv
    try:
        if TOKEN:                                            # a private repository: through the API, the files as API assets
            d = json.loads(_get(api + "/releases/latest", repo=repo, max_bytes=MAX_JSON).decode("utf-8"))
            assets = {str(a.get("name")): str(a.get("url") or "") for a in d.get("assets") or [] if isinstance(a, dict)}
            if not assets.get(uv.MANIFEST_NAME) or not assets.get(uv.SIG_NAME): raise UpdateError(NO_SIGNED_RELEASE)
            mb = _get(assets[uv.MANIFEST_NAME], repo=repo, accept="application/octet-stream", max_bytes=uv.MAX_MANIFEST)
            sb = _get(assets[uv.SIG_NAME], repo=repo, accept="application/octet-stream", max_bytes=uv.MAX_SIG)
            m = uv.verify_manifest(mb, sb)
            if not assets.get(m["artifact"]): raise UpdateError("The release does not hold the file its signed manifest names. Nothing was changed.")
            z = assets[m["artifact"]]
        else:                                                # a public repository: three plain files of its latest release, no API
            base = f"https://github.com/{repo}/releases/latest/download/"
            mb = _get(base + uv.MANIFEST_NAME, repo=repo, max_bytes=uv.MAX_MANIFEST); sb = _get(base + uv.SIG_NAME, repo=repo, max_bytes=uv.MAX_SIG)
            m = uv.verify_manifest(mb, sb)
            tag = str(m.get("tag") or "")
            z = (f"https://github.com/{repo}/releases/download/{tag}/" if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}", tag) else base) + m["artifact"]
    except uv.VerifyError as e: raise UpdateError(str(e))
    except net.HttpError as e:
        raise UpdateError(NO_SIGNED_RELEASE if e.code == 404 else explain(e, f"the repository {repo}"))
    if not newer(m["version"], current): return None
    return {"version": m["version"], "zip": z, "notes": str(m.get("notes") or "")[:1500], "repo": repo, "accept": "application/octet-stream",
            "signed": {"manifest": _b64(mb), "sig": _b64(sb)}}

def find_update(source, current):
    """Is there a newer version at `source`? Returns {"version", "zip" (a path or a link), "notes"} or None.
    Nothing of a candidate is run here. In a 'friends' build a GitHub place is only asked for its SIGNED release."""
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
        if not _repo_ok(repo): raise UpdateError("the place for updates must be written as github:owner/repository")
        _REPO[0] = repo
        _allowed("update_check")                             # local-only mode, or update checks switched off: nothing is asked
        if signed_only(): return _signed_github(repo, api, current)      # the branch of a repository carries no signature: never offered here
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
                return {"version": v, "zip": f"https://github.com/{repo}/archive/refs/heads/main.zip", "notes": notes, "page": f"https://github.com/{repo}/archive/refs/heads/main.zip", "repo": repo}
            raise UpdateError(explain(last, f"the repository {repo}") if last is not None else f"The repository {repo} holds no smart_plots.py with a VERSION, so it is not a copy of this app.")
        try:
            d = json.loads(_get(api + "/releases/latest").decode("utf-8")); v = str(d.get("tag_name") or d.get("name") or "")
            # with a token the files of a release are read as API assets (api.github.com/repos/<owner>/<repo>/releases/assets/<id>):
            # the only addresses the token is sent to. The storage host GitHub redirects to never gets it (net.py drops it there).
            assets = {str(a.get("name", "")): str(a.get("url") or "") for a in d.get("assets") or [] if isinstance(a, dict)}
            signed = None; want = ""
            if assets.get("manifest.json") and assets.get("manifest.sig"):      # a signed release: its manifest is verified in fetch_and_unpack
                mb = _get(assets["manifest.json"], accept="application/octet-stream", max_bytes=64 * 1024); sb = _get(assets["manifest.sig"], accept="application/octet-stream", max_bytes=1024)
                signed = {"manifest": _b64(mb), "sig": _b64(sb)}
                try: want = str(json.loads(mb.decode("utf-8")).get("artifact") or "")
                except Exception: want = ""
            name = want if assets.get(want) else next((n for n in assets if n.lower().endswith(".zip") and assets[n]), "")
            z = assets.get(name) or d.get("zipball_url")
            if z and newer(v, current):
                return {"version": v.lstrip("vV"), "zip": z, "notes": str(d.get("body") or "")[:1500], "repo": repo, **({"accept": "application/octet-stream"} if name else {}), **({"signed": signed} if signed else {})}
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
            return {"version": v, "zip": api + "/zipball", "notes": notes, "repo": repo} if newer(v, current) else None
        raise UpdateError(explain(last, f"the repository {repo}") if last is not None else f"The repository {repo} holds no smart_plots.py with a VERSION, so it is not a copy of this app.")
    if source.lower().endswith(".json"):
        d = json.loads(_get(source, max_bytes=MAX_JSON).decode("utf-8")); v = str(d.get("version", ""))
        extra = {"manifest_url": str(d["manifest"]), "sig_url": str(d["sig"])} if d.get("manifest") and d.get("sig") else {}
        return {"version": v, "zip": d.get("url"), "notes": str(d.get("notes") or "")[:1500], **extra} if d.get("url") and newer(v, current) else None
    if source.lower().startswith("https://"): return {"version": "", "zip": source, "notes": "the version is known after the download"}
    raise UpdateError("the place for updates must be a folder, a .zip, a link to a .zip or latest.json, or github:owner/repository")

def _zip_version(path):
    """The version a zip on disk says it holds (read as text; nothing is run, and nothing is believed before the
    signature is checked in fetch_and_unpack). A signed bundle states it in its manifest."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "manifest.json" in names and "manifest.sig" in names and z.getinfo("manifest.json").file_size <= 64 * 1024:
                v = str(json.loads(z.read("manifest.json").decode("utf-8")).get("version") or "")
                if re.fullmatch(r"\d+(\.\d+){1,3}", v): return v
            n = next((m for m in names if m.replace("\\", "/").endswith("smart_plots.py")), None)
            if not n or z.getinfo(n).file_size > 20 * 1024 * 1024: return ""
            m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', z.read(n).decode("utf-8", "replace"), re.M); return m.group(1) if m else ""
    except Exception: return ""

def _sibling_signature(z):
    """manifest and signature lying beside a zip on disk: <zip>.manifest.json + <zip>.manifest.sig, or manifest.json +
    manifest.sig in the same folder. Returns (manifest bytes, signature bytes) or None."""
    d = os.path.dirname(os.path.abspath(z))
    for a, b in ((z + ".manifest.json", z + ".manifest.sig"), (os.path.join(d, "manifest.json"), os.path.join(d, "manifest.sig"))):
        try:
            if os.path.isfile(a) and os.path.isfile(b) and os.path.getsize(a) <= 64 * 1024 and os.path.getsize(b) <= 1024:
                return open(a, "rb").read(), open(b, "rb").read()
        except OSError: continue
    return None

def fetch_and_unpack(info, work, *, current=None, allow_same=False):
    """Get the zip (download it when it is a link), VERIFY it, and unpack it safely. Returns the folder that holds
    origin_plot_app.py. Nothing of the update is compiled, imported or run here.
    A signed manifest (see the module text) is verified before the zip is unpacked; one that is present but wrong stops
    the update in every profile. Without one: refused in a 'friends' build; unpacked and marked NOT verified in the
    'owner' profile. info["verified"] and info["verify_note"] say which it was.
    current: the installed version (default: the one beside this file); allow_same: the same version may be fetched
    again (to complete an install), an older one never."""
    import update_verify as uv
    z = info["zip"]; os.makedirs(work, exist_ok=True); repo = info.get("repo") or ""
    current = current or version_of(HERE) or "0"; m = None; mb = sb = None
    try:
        s = info.get("signed") or {}
        if s.get("manifest") and s.get("sig"): mb, sb = base64.b64decode(s["manifest"]), base64.b64decode(s["sig"])
        elif info.get("manifest_url") and info.get("sig_url"):
            mb = _get(info["manifest_url"], repo=repo, channel="update_download", max_bytes=uv.MAX_MANIFEST); sb = _get(info["sig_url"], repo=repo, channel="update_download", max_bytes=uv.MAX_SIG)
        if mb is not None:                                    # the small signed part first: a wrong signature ends it before the download
            m = uv.verify_manifest(mb, sb); uv.check_compat(m, current, allow_same=allow_same)
        if str(z).lower().startswith("https://"):
            local = os.path.join(work, "update.zip")
            data = _get(z, timeout=300, repo=repo, accept=info.get("accept"), channel="update_download", max_bytes=(m["size"] if m else uv.MAX_ARTIFACT))
            with open(local, "wb") as f: f.write(data)
            z = local
        if not os.path.isfile(z): raise UpdateError(f"the update file is not there: {z}")
        if m is None:
            parts = uv.bundle_parts(z)                        # one zip that holds manifest.json, manifest.sig and the program zip
            if parts:
                mb, sb = parts; m = uv.verify_manifest(mb, sb); uv.check_compat(m, current, allow_same=allow_same)
                inner = os.path.join(work, "artifact.zip"); uv.extract_bundle_artifact(z, m, inner); z = inner
            elif os.path.abspath(os.path.dirname(z)) != os.path.abspath(work):
                sib = _sibling_signature(z)                   # a zip you chose on disk, with its two files beside it
                if sib: mb, sb = sib; m = uv.verify_manifest(mb, sb); uv.check_compat(m, current, allow_same=allow_same)
        if m is not None: uv.verify_artifact(z, m)
        elif signed_only(): raise UpdateError(UNSIGNED_REFUSED)
        uv.check_archive(z)
        dest = os.path.join(work, "unpacked"); shutil.rmtree(dest, ignore_errors=True)
        uv.safe_extract(z, dest, checked=True)                # no file may land outside the trial folder
    except uv.VerifyError as e: raise UpdateError(str(e))
    trial = None
    for base, _, files in os.walk(dest):
        if "origin_plot_app.py" in files and "smart_plots.py" in files: trial = os.path.abspath(base); break
    if trial is None: raise UpdateError("the zip does not hold the program (origin_plot_app.py and smart_plots.py)")
    if m is not None and vkey(version_of(trial)) != vkey(m["version"]):
        raise UpdateError(f"The zip holds version {version_of(trial) or '?'}, but its signed manifest states {m['version']}. It is not installed.")
    if m is not None: _VERIFIED[_real(trial)] = dict(m)
    else: _VERIFIED.pop(_real(trial), None)
    try: info["verified"] = m is not None; info["verify_note"] = verification_note(trial)
    except Exception: pass
    return trial


# ---------------------------------------------------------------------------------------------- the check
def _dry(app_dir, data_file, work):
    """The Origin commands that the program in app_dir makes for one data file (no Origin needed). Returns (ok, text).
    This RUNS origin_plot_app.py of that folder as you ('--dry-run' only says what the program is asked to do; it does not
    confine it). So in a 'friends' build it is refused for every folder that is neither the installed program nor an
    update whose signature was verified."""
    if signed_only() and _real(app_dir) != _real(HERE) and _real(app_dir) not in _TRUSTED_DIRS and not verified(app_dir): raise UpdateError(NOT_RUN_UNVERIFIED)
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
    The examples are redrawn several at a time. In a 'friends' build this is refused (UpdateError) unless the trial copy is an
    update whose signature was verified by fetch_and_unpack. Returns {"ok": bool, "lines": [what was checked], "same": n, "different": [...], "covered": n}."""
    import py_compile
    from concurrent.futures import ThreadPoolExecutor
    say = log or (lambda m: None); lines = []; different = []; same = 0; trial_dir, app_dir = os.path.abspath(trial_dir), os.path.abspath(app_dir)
    if signed_only() and not verified(trial_dir): raise UpdateError(NOT_RUN_UNVERIFIED)          # before the first file of the candidate is compiled or run
    _TRUSTED_DIRS.add(_real(app_dir))                             # the installed program the app compares with
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

def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""): h.update(part)
    return h.hexdigest()

def _safe_rel(rel):
    """A relative path of a program file that stays inside its folder (journals and file lists are checked with it)."""
    r = str(rel).replace("\\", "/")
    return bool(r) and not r.startswith("/") and not re.match(r"^[A-Za-z]:", r) and all(p not in ("", ".", "..") for p in r.split("/"))

def _write_json(path, d):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1); f.flush()
        try: os.fsync(f.fileno())
        except OSError: pass
    os.replace(tmp, path)

_replace = os.replace          # one rename puts a staged file in place (a name of its own, so the tests can cut an install off here)

def install(trial_dir, app_dir, store, why="", only=None):
    """Back up the current program, then put the program files of the trial copy in its place. Returns (backup folder, files changed).
    Two steps, written down in <store>/install_journal.json: every new file is first copied beside the old one under a temporary
    name (the program is untouched until all of them are there), then each is put in place with one rename. If that is cut off,
    recover() finishes it or puts the backup back. If a rename fails, the earlier program is put back at once.
    In a 'friends' build only an update whose signature was verified is installed. The files in PROTECTED are replaced only by
    a verified update, in every profile."""
    ok = verified(trial_dir) is not None
    if signed_only() and not ok: raise UpdateError(UNSIGNED_REFUSED)
    recover(app_dir, store)                                       # an earlier install that was cut off is settled first
    b = backup(app_dir, store, why); rels = []
    for rel in (only or program_files(trial_dir)):
        s, t = os.path.join(trial_dir, rel), os.path.join(app_dir, rel)
        if not _safe_rel(rel) or os.path.basename(rel) in NEVER or not os.path.isfile(s): continue
        if os.path.basename(rel) in PROTECTED and not ok: continue
        try: same = os.path.isfile(t) and open(s, "rb").read() == open(t, "rb").read()
        except Exception: same = False
        if not same: rels.append(rel)
    changed = _commit(trial_dir, app_dir, store, b, rels, why, ok) if rels else []
    try:
        j = os.path.join(b, "backup.json"); d = json.load(open(j, encoding="utf-8")); d["changed"] = changed; d["installed"] = version_of(app_dir); d["verified"] = ok; json.dump(d, open(j, "w", encoding="utf-8"), indent=1)
    except Exception: pass
    shutil.rmtree(os.path.join(app_dir, "__pycache__"), ignore_errors=True)
    return b, changed

def _commit(trial_dir, app_dir, store, b, rels, why, ok):
    os.makedirs(store, exist_ok=True); jp = os.path.join(store, JOURNAL)
    if os.path.isfile(jp):                                        # recover() left it: the record of ANOTHER copy of the app that shares this folder. Kept for that copy.
        n = 1
        while os.path.exists(f"{jp}.other{n}"): n += 1
        os.replace(jp, f"{jp}.other{n}")
    j = {"schema": "opstudio.install/1", "state": "staging", "app_dir": os.path.abspath(app_dir), "backup": os.path.abspath(b), "files": list(rels),
         "added": [r for r in rels if not os.path.isfile(os.path.join(app_dir, r))], "sha256": {r: _sha(os.path.join(trial_dir, r)) for r in rels},
         "why": why, "verified": bool(ok), "version": version_of(trial_dir)}
    _write_json(jp, j)
    try:
        for rel in rels:                                          # step 1: beside the old files; the program still runs as it was
            t = os.path.join(app_dir, rel); os.makedirs(os.path.dirname(t), exist_ok=True); shutil.copy2(os.path.join(trial_dir, rel), t + STAGE_EXT)
    except Exception:
        _unstage(app_dir, rels)
        try: os.remove(jp)
        except OSError: pass
        raise
    j["state"] = "committing"; _write_json(jp, j)
    try:
        for rel in rels: _replace(os.path.join(app_dir, rel) + STAGE_EXT, os.path.join(app_dir, rel))      # step 2: one rename per file
    except Exception as e:
        _rollback(app_dir, store, j, jp)
        raise UpdateError(f"A file of the program could not be replaced ({_redact(e)[:160]}). The earlier program was put back; nothing is half installed.")
    try: os.remove(jp)
    except OSError: pass
    return list(rels)

def _unstage(app_dir, rels):
    for rel in rels:
        try: os.remove(os.path.join(app_dir, rel) + STAGE_EXT)
        except OSError: pass

def _rollback(app_dir, store, j, jp):
    """Put the files of an unfinished install back from its backup; files it had added are removed. jp: its journal file."""
    b = j.get("backup") or ""; added = set(j.get("added") or [])
    _unstage(app_dir, j.get("files") or [])
    for rel in j.get("files") or []:
        t = os.path.join(app_dir, rel)
        if rel in added:
            try: os.remove(t)
            except OSError: pass
        elif os.path.isfile(os.path.join(b, rel)):
            shutil.copy2(os.path.join(b, rel), t + STAGE_EXT); os.replace(t + STAGE_EXT, t)
    shutil.rmtree(os.path.join(app_dir, "__pycache__"), ignore_errors=True)
    try: os.replace(os.path.join(b, "backup.json"), os.path.join(b, "backup_rolled_back.json"))      # no longer offered by Undo: nothing of it is installed
    except OSError: pass
    try: os.remove(jp)
    except OSError: pass

def recover(app_dir, store):
    """Settle an install that was cut off (power loss, a crash, the app closed in the middle). Called at the start of the app,
    and before every install and undo. Returns a line that says what was done, or None when there was nothing to do.
      cut off while the new files were still being copied beside the old ones: the copies are removed, the program is unchanged;
      cut off while they were being put in place: the remaining ones are put in place and every file is compared with the
      checksum written down before; if anything is missing or differs, the backup is put back instead."""
    import glob
    aside = [f for f in glob.glob(os.path.join(glob.escape(store), JOURNAL + ".other*")) if re.search(r"\.other\d+$", f)]        # set aside by another copy of the app
    for jp in [os.path.join(store, JOURNAL)] + sorted(aside):
        line = _recover_one(jp, app_dir, store)
        if line: return line
    return None

def _recover_one(jp, app_dir, store):
    if not os.path.isfile(jp): return None
    try: j = json.load(open(jp, encoding="utf-8"))
    except Exception: j = None
    ok = (isinstance(j, dict) and j.get("schema") == "opstudio.install/1" and isinstance(j.get("files"), list) and all(isinstance(r, str) and _safe_rel(r) for r in j["files"])
          and isinstance(j.get("sha256"), dict) and isinstance(j.get("added", []), list) and isinstance(j.get("backup"), str) and isinstance(j.get("app_dir"), str))
    if not ok:
        try: os.replace(jp, jp + ".unreadable")
        except OSError: pass
        return "The record of an install that was cut off could not be read. If the app misbehaves, Help > 'Undo the last update' puts the last backup back."
    if _real(j["app_dir"]) != _real(app_dir): return None             # the journal of another copy of the app: not ours to touch
    if not _real(j["backup"]).startswith(_real(store) + os.sep) or any(os.path.basename(r) in NEVER for r in j["files"]):
        try: os.replace(jp, jp + ".unreadable")
        except OSError: pass
        return "The record of an install that was cut off is not valid; it was set aside and nothing was changed."
    files = j["files"]
    if j.get("state") != "committing":
        _unstage(app_dir, files)
        try: os.remove(jp)
        except OSError: pass
        return "An install was cut off before any file of the program was changed. Its temporary files were removed; the program is as it was."
    finish = not (signed_only() and not j.get("verified"))            # a 'friends' build never completes something that was not verified
    if finish:
        try:
            for rel in files:
                t = os.path.join(app_dir, rel)
                if os.path.isfile(t + STAGE_EXT): os.replace(t + STAGE_EXT, t)
            finish = all(os.path.isfile(os.path.join(app_dir, r)) and _sha(os.path.join(app_dir, r)) == j["sha256"].get(r) for r in files)
        except Exception: finish = False
    if finish:
        try:
            bj = os.path.join(j["backup"], "backup.json"); d = json.load(open(bj, encoding="utf-8")); d["changed"] = files; d["installed"] = version_of(app_dir); d["verified"] = bool(j.get("verified")); json.dump(d, open(bj, "w", encoding="utf-8"), indent=1)
        except Exception: pass
        shutil.rmtree(os.path.join(app_dir, "__pycache__"), ignore_errors=True)
        try: os.remove(jp)
        except OSError: pass
        return f"An install that was cut off was finished: {len(files)} file(s) are in place" + (f" (version {j.get('version')})" if j.get("version") else "") + ". Help > 'Undo the last update' brings the earlier version back."
    _rollback(app_dir, store, j, jp)
    return "An install that was cut off could not be finished, so the earlier program was put back from its backup. Nothing is half installed."

def backups(store):
    try: return sorted([os.path.join(store, d) for d in os.listdir(store) if os.path.isfile(os.path.join(store, d, "backup.json"))])
    except Exception: return []

def undo(app_dir, store):
    """Put back the newest backup. Files the update had added are removed. Returns a line that says what was restored."""
    recover(app_dir, store)                                       # an install that was cut off is settled first
    bs = backups(store)
    if not bs: raise UpdateError("there is no earlier version to go back to")
    b = bs[-1]; d = json.load(open(os.path.join(b, "backup.json"), encoding="utf-8")); had = set(d.get("files") or [])
    for rel in d.get("changed") or []:
        if rel not in had and os.path.basename(rel) not in NEVER and os.path.basename(rel) not in PROTECTED and _safe_rel(rel):
            try: os.remove(os.path.join(app_dir, rel))
            except Exception: pass
    for rel in had:
        if not _safe_rel(rel): continue
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

REPAIR_OFF = ("Repairing the program with AI is not available in this build. A fix written by a model is new program code: it has to be reviewed and "
              "tested by the developer and comes to you as a signed update. Use 'Problem report\u2026' and send that file to whoever looks after the app.")
NO_REPAIR_OF = ("self_update.py", "update_trust.py", "update_verify.py", "outbound_policy.py", "secure_store.py", "net.py")     # what decides trust is never edited by a model

def repair_available():
    """Is client-side AI repair offered in this copy? Not in a 'friends' build (the functions below refuse there, whatever a window shows)."""
    return not signed_only()

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
    if not repair_available(): raise UpdateError(REPAIR_OFF)
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
    if not repair_available(): raise UpdateError(REPAIR_OFF)
    if not edits: raise UpdateError("the AI proposed no change")
    trial = os.path.join(work, "trial"); shutil.rmtree(trial, ignore_errors=True)
    for rel in program_files(app_dir):
        t = os.path.join(trial, rel); os.makedirs(os.path.dirname(t), exist_ok=True); shutil.copy2(os.path.join(app_dir, rel), t)
    touched = []
    for e in edits:
        nm = os.path.basename(str(e["file"]))
        if not nm.endswith(".py") or not os.path.isfile(os.path.join(trial, nm)) or nm in NO_REPAIR_OF: raise UpdateError(f"the repair wants to change '{e['file']}', which is not a program file it may change")
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

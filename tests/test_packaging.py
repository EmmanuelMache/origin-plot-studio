"""Packaging (B.5, SEC-07): a release is built from a reviewed list of committed files and never carries runtime or
personal data; the secret scan finds a planted credential and never prints it; the requirements are exact pins with a
hashed lock, and no launcher installs "the newest" of anything; the diagnostic file holds no name, path or credential.
Everything here is SYNTHETIC: made-up names and credentials built from pieces that are no key.
No network (Git is used on a temporary copy only). Run:  python tests/test_packaging.py"""
import os, sys, tempfile
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix="ops_packaging_"))
os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private"); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "cfg" / "settings_modern.json"); os.environ["ORIGIN_PLOT_APP_HOME"] = str(TMP / "store")
os.environ["OPS_NO_OPEN"] = "1"; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ.setdefault("MPLBACKEND", "Agg")
for _k in ("OPS_PROFILE", "OPS_LOCAL_ONLY"): os.environ.pop(_k, None)
# The build runs the private-term check with the list this variable names. Here: a made-up list with one made-up term, so
# the test does not depend on (and never reads) the real list of a machine.
TERM = "ZZQ" + "-PRIVATE-" + "TERM-5K"; (TMP / "terms").mkdir(); (TMP / "terms" / "banned_terms.txt").write_text("# synthetic list for this test\n" + TERM.replace("-", "\\-") + "\n", encoding="utf-8")
os.environ["OPS_BANNED_TERMS"] = str(TMP / "terms" / "banned_terms.txt")
import contextlib, hashlib, importlib.machinery, importlib.util, io, json, re, shutil, socket, subprocess, zipfile
ROOT = Path(__file__).resolve().parents[1]; APP = ROOT / "origin_plot_app"
sys.path.insert(0, str(APP)); sys.path.insert(0, str(ROOT / "tools"))
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" and not cond else ""))

def _no_network(*a, **k): raise AssertionError("a test tried to open a network connection")
socket.create_connection = _no_network; _real_connect = socket.socket.connect; socket.socket.connect = lambda self, *a, **k: _no_network()

import build_release as B, secret_scan as S, dependency_inventory as DI

def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args], capture_output=True, text=True)
    if r.returncode != 0: raise AssertionError("git " + " ".join(args[:2]) + ": " + r.stderr[-300:])
    return r.stdout
def fake_key(kind, seed):
    """Something a credential pattern matches, built at run time from pieces - not a key of anything."""
    body = hashlib.sha256(seed.encode()).hexdigest()
    return {"github": "gh" + "p_" + body[:36], "anthropic": "sk-" + "ant-" + body[:40], "aws": "AK" + "IA" + body[:16].upper(), "jwt": "ey" + "J" + body[:20] + "." + body[20:44] + "." + body[44:60]}[kind]

# ---------------------------------------------------------------- a copy of the repository with runtime and personal files planted in it
REPO = TMP / "repo"; REPO.mkdir()
listed = [n for n in subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"], capture_output=True).stdout.decode("utf-8").split("\0") if n]
for rel in listed:
    src = ROOT / rel
    if src.is_file() and not rel.startswith(("dist/", "tests/__pycache__")): (REPO / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, REPO / rel)
SENTINEL = "ZZ-RUNTIME-SENTINEL-7Q"
PLANTED = ["origin_plot_app/settings.json", "origin_plot_app/settings_modern.json", "origin_plot_app/settings_backup.json", "origin_plot_app/last_session.json", "origin_plot_app/last_run_log.txt",
           "origin_plot_app/assistant_lessons.txt", "origin_plot_app/learned_formats.json", "origin_plot_app/chat_cache.sqlite3", "origin_plot_app/credentials.json", "origin_plot_app/outbound_policy.json",
           "origin_plot_app/pdf_names.json", "origin_plot_app/error_log.txt", "origin_plot_app/startup_error.txt", "origin_plot_app/console_output.txt", "origin_plot_app/app.log",
           "origin_plot_app/logs/run.txt", "origin_plot_app/cache/chat.json", "origin_plot_app/__pycache__/smart_plots.cpython-313.pyc", "origin_plot_app/Synthetic_demo.opsproject",
           "origin_plot_app/my_templates/private_template.json", "origin_plot_app/figure_recipes/Synthetic_recipe.json", "origin_plot_app/project_data/abc/inputs/0001/Synthetic.csv",
           "origin_plot_app/examples_synthetic/last_session.json", "origin_plot_app/examples_synthetic/notes.sqlite3", "origin_plot_app/opstudio/settings_local.json",
           "origin_plot_app/opstudio/__pycache__/core.cpython-313.pyc", "origin_plot_app/opstudio/templates/my.local.json", "origin_plot_app/config/assistant.local.json", "origin_plot_app/secrets.dat",
           "origin_plot_app/.env", "origin_plot_app/signing.pem", "tests/Synthetic_test_note.txt", "tools/Synthetic_tool_note.txt", ".github/workflows/release.yml", "backend/server.py",
           "backend/settings.json", "sample_data/Synthetic_measurement.csv", "screenshots/Synthetic_screen.png", "ops_private/banned_terms.txt"]
for rel in PLANTED:
    (REPO / rel).parent.mkdir(parents=True, exist_ok=True); (REPO / rel).write_text(f"{SENTINEL} planted runtime or personal file: {rel}\n", encoding="utf-8")
(REPO / "origin_plot_app" / "security_profile.json").write_text('{"profile": "owner", "note": "' + SENTINEL + '"}', encoding="utf-8")     # the tree may not decide the profile of a build
git(REPO, "init", "-q", "."); git(REPO, "add", "-A", "-f", "."); git(REPO, "commit", "-q", "-m", "fixture: everything committed, also what must never ship")
(REPO / "origin_plot_app" / "uncommitted_module.py").write_text(f"# {SENTINEL} not committed\n", encoding="utf-8")                    # appears after the commit: not part of it
(REPO / "origin_plot_app" / "smart_plots.py").open("a", encoding="utf-8").write(f"\n# {SENTINEL} uncommitted change\n")

# ---------------------------------------------------------------- the build
OUT = TMP / "dist"; log = []
res = B.build(str(REPO), str(OUT), profile="friends", log=log.append)
zf = zipfile.ZipFile(res["zip"]); names = zf.namelist(); top = Path(res["zip"]).stem + "/"; inner = [n[len(top):] for n in names]
check("a release zip is built from the commit, and the tool says its version and SHA-256", Path(res["zip"]).is_file() and re.fullmatch(r"\d+\.\d+(\.\d+)*", res["version"]) is not None
      and res["sha256"] == hashlib.sha256(Path(res["zip"]).read_bytes()).hexdigest() and any(res["sha256"] in l for l in log) and Path(res["zip"] + ".sha256").read_text().split()[0] == res["sha256"], log)
check("everything in it is inside one folder named after the release", all(n.startswith(top) for n in names) and top.startswith("Origin_Plot_Studio_"))
bad_names = [n for n in inner if B.denied(n)]
check("no file excluded by rule is in the zip (settings, sessions, logs, lessons, learned formats, credentials, caches ...)", not bad_names, bad_names[:8])
gone = ["settings.json", "settings_modern.json", "settings_backup.json", "last_session.json", "last_run_log.txt", "assistant_lessons.txt", "learned_formats.json", "credentials.json", "outbound_policy.json", "pdf_names.json"]
check("... none of the named runtime files, at any depth", not [n for n in inner if n.split("/")[-1] in gone] and not [n for n in inner if n.endswith((".sqlite3", ".pyc", ".opsproject", ".log", ".pem", ".env", ".dat"))])
check("... no tests, tools, .github, backend, caches, private templates, project data or screenshots", not [n for n in inner if n.split("/")[0] in ("tests", "tools", ".github", "backend", "sample_data", "screenshots", "ops_private", "docs", "xrd_scan_generator")]
      and not [n for n in inner if any(part in ("__pycache__", "cache", "logs", "my_templates", "figure_recipes", "project_data") for part in n.split("/"))])
blob = b"".join(zf.read(n) for n in names)
check("the text planted in every runtime file is nowhere in the zip - also not from the uncommitted file and the uncommitted change", SENTINEL.encode() not in blob and "uncommitted_module.py" not in inner)
check("the build says what it left out and why", len(res["excluded"]) >= len(PLANTED) - 2 and all(why for _p, why in res["excluded"]) and {p_ for p_, _w in res["excluded"]} >= set(PLANTED))
for need in ("origin_plot_app.py", "smart_plots.py", "start.pyw", "setup.pyw", "Setup.bat", "Run_Origin_Plot_App.bat", "requirements.txt", "requirements.lock", "LICENSE", "README.md", "SECURITY.md", "PRIVACY.md",
             "HOW_TO_INSTALL.txt", "outbound_policy.py", "safe_export.py", "diagnostics.py", "opstudio/__init__.py", "RELEASE_CONTENTS.md", "security_profile.json"):
    if need not in inner: check(f"the release holds {need}", False)
check("the program, its launchers, the pinned requirements and the documents a user needs are in the release", all(n in inner for n in ("origin_plot_app.py", "Setup.bat", "requirements.lock", "LICENSE", "SECURITY.md", "PRIVACY.md", "HOW_TO_INSTALL.txt", "README.md")))
demos = sorted(n for n in inner if n.startswith("examples_synthetic/"))
check("the approved demo data is in the release (examples_synthetic), and only what was there before the planting", demos == sorted("examples_synthetic/" + f.name for f in (APP / "examples_synthetic").iterdir() if f.is_file() and not B.denied(f.name) and f.name in {Path(x).name for x in listed if x.startswith("origin_plot_app/examples_synthetic/")}) and len(demos) >= 5, demos)
check("a 'friends' build carries security_profile.json = {\"profile\": \"friends\"}, whatever the tree held", json.loads(zf.read(top + "security_profile.json")) == {"profile": "friends"})
contents = zf.read(top + "RELEASE_CONTENTS.md").decode("utf-8")
rows = dict(re.findall(r"^\| ([^|]+?) \| \d+ \| `([0-9a-f]{64})`", contents, re.M))
data_like = [n for n in inner if n.lower().endswith((".xlsx", ".xls", ".csv", ".png", ".jpg", ".ico", ".docx", ".pptx"))]
check("RELEASE_CONTENTS.md lists every bundled workbook, CSV and picture with its SHA-256, for the owner to review", len(data_like) > 50 and all(rows.get(n) == hashlib.sha256(zf.read(top + n)).hexdigest() for n in data_like), [n for n in data_like if n not in rows][:5])
check("... and every other file too; it names the version, the profile and the commit, and says what is excluded", set(rows) == set(inner) - {"RELEASE_CONTENTS.md"} and "Security profile: friends" in contents and git(REPO, "rev-parse", "HEAD").strip() in contents
      and "For the owner to review" in contents and "NOT A RELEASE BUILD" not in contents)
check("... kinds of metadata are named, never a value", "| Carries |" in contents)
check("the folder beside the zip holds exactly the same files", sorted(str(p_.relative_to(res["folder"])).replace(os.sep, "/") for p_ in Path(res["folder"]).rglob("*") if p_.is_file()) == sorted(inner))
infos = zf.infolist()
check("the zip is made the same way every time: names sorted, one time stamp, fixed permissions", names == sorted(names) and len({i.date_time for i in infos}) == 1 and {i.external_attr >> 16 for i in infos} == {0o100644} and {i.create_system for i in infos} == {3})
res2 = B.build(str(REPO), str(TMP / "dist2"), profile="friends", log=lambda *_: None)
check("building the same commit again gives the same zip, byte for byte", res2["sha256"] == res["sha256"])
res3 = B.build(str(REPO), str(TMP / "dist3"), profile="owner", log=lambda *_: None)
check("--profile owner writes that profile (and so gives another zip)", json.loads(zipfile.ZipFile(res3["zip"]).read(top + "security_profile.json")) == {"profile": "owner"} and res3["sha256"] != res["sha256"])
try:
    import update_verify
    try: info = update_verify.check_archive(res["zip"]); ok = info["entries"] == len(names)
    except Exception as e: ok = False; info = e
    check("the zip passes the structure check the updater applies to an update", ok, info)
except ImportError:
    check("(update_verify.py is not in this tree: the updater's structure check was not applied)", True)
with contextlib.redirect_stdout(io.StringIO()) as so: rc = B.main(["--source", str(REPO), "--out", str(TMP / "dist4"), "--profile", "friends"])
check("the command line does the same and prints the SHA-256", rc == 0 and res["sha256"] in so.getvalue())

# a build from the working folder is possible, and marked as not being a release
res_w = B.build(str(REPO), str(TMP / "dist_w"), profile="friends", worktree=True, log=lambda *_: None)
cw = zipfile.ZipFile(res_w["zip"]).read(top + "RELEASE_CONTENTS.md").decode("utf-8")
check("a trial build from the working folder takes tracked files only and is marked NOT A RELEASE BUILD", "NOT A RELEASE BUILD" in cw and "uncommitted_module.py" not in "".join(zipfile.ZipFile(res_w["zip"]).namelist())
      and not [n for n in zipfile.ZipFile(res_w["zip"]).namelist() if B.denied(n[len(top):])])
plain = TMP / "plain"; shutil.copytree(REPO, plain, ignore=shutil.ignore_patterns(".git"))
res_p = B.build(str(plain), str(TMP / "dist_p"), profile="friends", no_git=True, log=lambda *_: None)
check("a plain folder (no Git) can be built for tests; the same exclusions hold", not [n for n in zipfile.ZipFile(res_p["zip"]).namelist() if B.denied(n[len(top):])] and "settings.json" not in [n.split("/")[-1] for n in zipfile.ZipFile(res_p["zip"]).namelist()])

# a credential in a file that IS on the list of release files stops the build
secret = fake_key("github", "planted in a release file")
(REPO / "origin_plot_app" / "opstudio" / "planted_note.json").write_text(json.dumps({"note": "left here by mistake", "value": secret}), encoding="utf-8")
git(REPO, "add", "-A", "-f", "origin_plot_app/opstudio/planted_note.json"); git(REPO, "commit", "-q", "-m", "fixture: a credential in a release file")
try: B.build(str(REPO), str(TMP / "dist5"), profile="friends", log=lambda *_: None); stopped = False; msg = ""
except B.BuildError as e: stopped = True; msg = str(e)
check("a credential inside a file of the release stops the build, and the zip is removed", stopped and "secret scan" in msg and "planted_note.json" in msg and "GitHub token" in msg and not list((TMP / "dist5").glob("*.zip")), msg[:200])
check("... the message names the file and the kind of credential, never the value", secret not in msg and secret[4:16] not in msg)
git(REPO, "rm", "-q", "origin_plot_app/opstudio/planted_note.json"); git(REPO, "commit", "-q", "-m", "fixture: file removed again")
(REPO / "origin_plot_app" / "opstudio" / "planted_term.json").write_text(json.dumps({"label": "measured for " + TERM}), encoding="utf-8")
git(REPO, "add", "-A", "-f", "origin_plot_app/opstudio/planted_term.json"); git(REPO, "commit", "-q", "-m", "fixture: a private term in a release file")
try: B.build(str(REPO), str(TMP / "dist6"), profile="friends", log=lambda *_: None); stopped = False; msg = ""
except B.BuildError as e: stopped = True; msg = str(e)
check("a private term (the owner's list) inside a file of the release stops the build too; the file is named, the term is not", stopped and "private terms" in msg and "planted_term.json" in msg and TERM not in msg and not list((TMP / "dist6").glob("*.zip")), msg[:200])
git(REPO, "rm", "-q", "origin_plot_app/opstudio/planted_term.json"); git(REPO, "commit", "-q", "-m", "fixture: file removed again")
check("the first build ran the private-term check and found nothing", any("private-term check:" in l and "0 with a private term" in l for l in log), log)
check("the rules themselves: what is allowed, what is denied", B.allowed("origin_plot_app/smart_plots.py") and B.allowed("origin_plot_app/opstudio/templates/x.json") and not B.allowed("origin_plot_app/sub/x.py") and not B.allowed("tests/test_x.py")
      and not B.allowed("docs/RELEASE_PROCESS.md") and B.denied("origin_plot_app/Settings.JSON") and B.denied("a/__pycache__/b.pyc") and B.denied("x/settings_modern.json") and B.denied("my.opsproject") and B.denied("x.sqlite3")
      and not B.denied("origin_plot_app/opstudio/catalog.json") and not B.denied("origin_plot_app/workspace_session.py"))

# ---------------------------------------------------------------- the secret scan: finds, never prints
FIX = TMP / "scan"; (FIX / "sub").mkdir(parents=True)
k_git, k_ai, k_aws, k_jwt = fake_key("github", "a"), fake_key("anthropic", "b"), fake_key("aws", "c"), fake_key("jwt", "d")
k_pw = hashlib.sha256(b"e").hexdigest()[:20] + "Qw7" + hashlib.sha256(b"f").hexdigest()[:9].upper()
(FIX / "notes.txt").write_text(f"line one\nthe build machine uses {k_git} for uploads\n", encoding="utf-8")
(FIX / "sub" / "config.py").write_text(f'URL = "https://example.invalid"\nDB_PASSWORD = "{k_pw}"\nAWS = "{k_aws}"\n', encoding="utf-8")
with zipfile.ZipFile(FIX / "Synthetic_report.docx", "w") as z: z.writestr("word/document.xml", f"<w:document><w:t>key: {k_ai}</w:t></w:document>"); z.writestr("docProps/core.xml", "<cp:coreProperties/>")
with zipfile.ZipFile(FIX / "Synthetic_book.xlsx", "w") as z: z.writestr("xl/sharedStrings.xml", f"<sst><si><t>{k_jwt}</t></si></sst>"); z.writestr("xl/workbook.xml", "<workbook/>")
inner_zip = io.BytesIO()
with zipfile.ZipFile(inner_zip, "w") as z: z.writestr("deep/token.txt", "t = " + k_git)
with zipfile.ZipFile(FIX / "outer.zip", "w") as z: z.writestr("inner.zip", inner_zip.getvalue())
(FIX / "clean.txt").write_text("sha256 = \"" + hashlib.sha256(b"x").hexdigest() + "\"\npassword = \"correct horse\"\ntoken_count = 12\nsk-short\n", encoding="utf-8")
(FIX / "test_values.py").write_text('KEY = "sk-' + 'ant-DUMMY-EXAMPLE-NOT-REAL-0000000000"\n', encoding="utf-8")
with contextlib.redirect_stdout(io.StringIO()) as so: rc = S.main([str(FIX)])
out = so.getvalue()
check("the secret scan finds the planted credentials in text files and ends with exit code 1", rc == 1 and "notes.txt:2" in out and "GitHub token" in out and "sub/config.py:2" in out and "long random value assigned to a credential name" in out and "AWS access key id" in out, out)
check("... also inside a Word file, an Excel file and a zip in a zip", "Synthetic_report.docx > word/document.xml" in out and "Anthropic API key" in out and "Synthetic_book.xlsx > xl/sharedStrings.xml" in out and "JSON Web Token" in out and "outer.zip > inner.zip:deep/token.txt" in out, out)
leaks = [k for k in (k_git, k_ai, k_aws, k_jwt, k_pw) if k in out or k[5:17] in out or k[-12:] in out]
check("... and prints the place and the NAME of the pattern only: no value, no part of one", not leaks and "correct horse" not in out)
check("... ordinary lines are not findings (a checksum, a short word as a password, a counter)", "clean.txt" not in out)
check("... an obvious test value is shown as such and not counted, unless the scan is strict", "test   test_values.py:1" in out and re.search(r"; 6 finding\(s\); 1 obvious test value", out) is not None, out.splitlines()[-1])
with contextlib.redirect_stdout(io.StringIO()) as so: rc_strict = S.main([str(FIX / "test_values.py"), "--strict"])
(FIX / "only_clean").mkdir(); shutil.copyfile(FIX / "clean.txt", FIX / "only_clean" / "clean.txt")
with contextlib.redirect_stdout(io.StringIO()) as so2: rc_clean = S.main([str(FIX / "only_clean")])
check("strict mode counts it; a clean folder ends with exit code 0", rc_strict == 1 and "FOUND" in so.getvalue() and rc_clean == 0 and "0 finding(s)" in so2.getvalue())
jpath = TMP / "scan.json"
with contextlib.redirect_stdout(io.StringIO()): S.main([str(FIX), "--json", str(jpath), "--quiet"])
jtext = jpath.read_text(encoding="utf-8")
check("the JSON report holds places and pattern names, no value either", json.loads(jtext)["findings"] == 6 and not [k for k in (k_git, k_ai, k_aws, k_jwt, k_pw) if k in jtext])
# the history: a credential that was committed and later deleted is still found
H = TMP / "history"; H.mkdir(); git(H, "init", "-q", ".")
(H / "a.txt").write_text("nothing here\n", encoding="utf-8"); git(H, "add", "a.txt"); git(H, "commit", "-q", "-m", "one")
(H / "deploy.cfg").write_text(f"token = {k_git}\n", encoding="utf-8"); git(H, "add", "deploy.cfg"); git(H, "commit", "-q", "-m", "two")
bad_commit = git(H, "rev-parse", "--short", "HEAD").strip()
git(H, "rm", "-q", "deploy.cfg"); git(H, "commit", "-q", "-m", "three")
tree_f, tree_n, _c = S.scan_tree([str(H)]); hist_f, hist_n, commits, shallow = S.scan_history(str(H))
check("a credential that was committed and then deleted: the folder is clean, the history is not", not tree_f and len(hist_f) == 1 and hist_f[0]["pattern"] == "GitHub token" and hist_f[0]["where"] == "deploy.cfg" and commits == 3 and hist_n == 2 and not shallow, hist_f)
check("... the finding names the commit that brought it in, and still no value", hist_f[0]["commit"] == bad_commit and k_git not in json.dumps(hist_f))
check("the scan uses the patterns the app redacts with", {n for n, _r in S.patterns()} >= {"Anthropic API key", "GitHub token", "JSON Web Token", "private key block", "AWS access key id"})

# ---------------------------------------------------------------- SEC-07: pinned requirements, a hashed lock, no "install the newest"
req = DI.parse_requirements(str(APP / "requirements.txt")); lock = DI.parse_requirements(str(APP / "requirements.lock"))
check("every requirement is pinned to one exact version (==)", len(req) >= 10 and all(r["version"] and r["spec"].startswith("==") for r in req), [r["name"] for r in req if not r["version"]])
check("... the packages the app needs are there, with cryptography (update signatures); pywin32 only on Windows; keyring optional and not on Windows",
      {DI.canon(r["name"]) for r in req} >= {"numpy", "pandas", "scipy", "matplotlib", "openpyxl", "pyside6", "cryptography", "xlrd", "python-calamine", "certifi", "tzdata", "pywin32", "keyring"}
      and next(r for r in req if r["name"] == "pywin32")["marker"] == "sys_platform == 'win32'" and "win32" in next(r for r in req if r["name"] == "keyring")["marker"])
raw_req = (APP / "requirements.txt").read_text(encoding="utf-8")
check("... the file says which pins were not installed or tested where the tests ran", "NOT installed" in raw_req and "NOT tested" in raw_req and "requirements.lock" in raw_req)
problems = DI.check()
check("the lock matches the requirements: every direct package at the same version, everything pinned", problems == [], problems)
head = (APP / "requirements.lock").read_text(encoding="utf-8")[:3000]
hashed = bool(lock) and all(r["hashes"] for r in lock)
check("the lock holds the transitive set too, and either a sha256 for every package or a clear note at its top that hashes are missing", len(lock) > len(req) and all(r["version"] for r in lock) and (hashed or DI.NO_HASH_HEADER in head), (len(lock), len(req)))
if hashed: check("... (this lock has hashes: every entry at least one sha256, written as pip expects)", all(re.fullmatch(r"[0-9a-f]{64}", h) for r in lock for h in r["hashes"]) and "--require-hashes" in head)
with contextlib.redirect_stdout(io.StringIO()) as so: rc = DI.main(["--check"])
check("dependency_inventory --check says so and ends with 0", rc == 0 and "consistent" in so.getvalue())
bad_req = TMP / "bad_requirements.txt"; bad_req.write_text("numpy\npandas>=2\nscipy==1.*\nopenpyxl==3.1.5\n", encoding="utf-8")
check("... and reports a requirement that is not an exact pin", len([p_ for p_ in DI.check(str(bad_req), str(APP / "requirements.lock")) if "not pinned" in p_]) == 3)
with contextlib.redirect_stdout(io.StringIO()) as so: rc = DI.main(["--out", str(TMP / "inv")])
inv = json.loads((TMP / "inv" / "dependencies.json").read_text(encoding="utf-8")); md = (TMP / "inv" / "DEPENDENCIES.md").read_text(encoding="utf-8")
check("the dependency inventory is written as JSON and Markdown without the network: name, version, direct / transitive, licence, tested or not", rc == 0 and len(inv["packages"]) == len(lock)
      and {p_["kind"] for p_ in inv["packages"]} == {"direct", "transitive"} and sum(p_["kind"] == "direct" for p_ in inv["packages"]) == len(req) and all(p_["version"] and p_["licence"] and p_["build_environment"] for p_ in inv["packages"])
      and all(f"| {p_['name']} | {p_['version']} |" in md for p_ in inv["packages"]) and "Vulnerability check" in md)
check("the inventory kept in docs/ is the one of this lock", [(p_["name"], p_["version"]) for p_ in json.loads((ROOT / "docs" / "dependencies.json").read_text(encoding="utf-8"))["packages"]] == [(p_["name"], p_["version"]) for p_ in inv["packages"]]
      and (ROOT / "docs" / "DEPENDENCIES.md").is_file())

# the launchers and the installer
bat = (APP / "Run_Origin_Plot_App.bat").read_text(encoding="utf-8"); setup_bat = (APP / "Setup.bat").read_text(encoding="utf-8")
start = (APP / "start.pyw").read_text(encoding="utf-8"); setup = (APP / "setup.pyw").read_text(encoding="utf-8"); vbs = (APP / "Origin_Plot_Studio.vbs").read_text(encoding="utf-8")
def code_lines(text, comment): return [l for l in text.splitlines() if l.strip() and not l.strip().lower().startswith(comment)]
check("the launcher batch file installs nothing: it looks whether the packages are there and points to Setup", not any("pip" in l.lower() for l in code_lines(bat, ("rem", "echo"))) and "find_spec" in bat and "Setup.bat" in bat and "requirements.lock" in bat and "PySide6" in bat)
check("... Setup.bat and the .vbs launcher run no pip either", not any("pip" in l.lower() for l in code_lines(setup_bat, ("rem", "echo"))) and not any("pip" in l.lower() for l in code_lines(vbs, ("'",))))
check("... the batch files keep Windows line endings and ask for no administrator rights", b"\r\n" in (APP / "Run_Origin_Plot_App.bat").read_bytes() and b"\r\n" in (APP / "Setup.bat").read_bytes() and b"\n" not in (APP / "Setup.bat").read_bytes().replace(b"\r\n", b"")
      and not re.search(r"(?i)runas|--scope machine|/allusers", bat + setup_bat) and "--scope user" in setup_bat)
pip_lines = [l for src_ in (start, setup) for l in src_.splitlines() if re.search(r"""["']pip["'],\s*["']install["']""", l)]
check("every pip install in the program installs from a requirements file: exact versions, ready-made packages, hashes when the lock has them - never a package by name, never --upgrade",
      len(pip_lines) == 2 and all('"-r"' in l and '"--only-binary"' in l and '"--require-hashes"' in l for l in pip_lines) and not re.search(r"[\"']--upgrade[\"']|[\"']-U[\"']", start + setup)
      and not re.search(r"""["']install["'][^\n]*["'](?:PySide6|numpy|pandas|scipy|matplotlib|openpyxl|xlrd|pywin32|python-calamine)["']""", start + setup), pip_lines)
check("... starting the app asks before it installs anything and names the lock; a 'no' installs nothing", "_ask(" in start and "requirements.lock" in start and "Nothing is installed without your yes" in start and start.index("if not _ask(") < start.index('"pip", "install"'))
loader = importlib.machinery.SourceFileLoader("ops_setup_under_test", str(APP / "setup.pyw")); spec = importlib.util.spec_from_loader(loader.name, loader); SU = importlib.util.module_from_spec(spec); loader.exec_module(SU)
cmd = SU.pip_install_command("PY", "LOCK", True); cmd2 = SU.pip_install_command("PY", "LOCK", False)
check("Setup's one install command: pip install --only-binary :all: --require-hashes -r <lock>", cmd[:4] == ["PY", "-m", "pip", "install"] and cmd[-2:] == ["-r", "LOCK"] and "--require-hashes" in cmd and cmd[cmd.index("--only-binary") + 1] == ":all:"
      and "--upgrade" not in cmd and "--user" not in cmd and "--require-hashes" not in cmd2 and "--no-deps" in cmd2)
entries = SU.lock_entries(str(APP / "requirements.lock"))
check("Setup reads the same lock: every package with its exact version", [(DI.canon(n), v) for n, v, _m, _t in entries] == [(DI.canon(r["name"]), r["version"]) for r in lock] and SU.lock_hashed(str(APP / "requirements.lock")) == hashed)
fake_lock = TMP / "fake.lock"; fake_lock.write_text("# c\nopenpyxl==0.0.1 \\\n    --hash=sha256:" + "0" * 64 + "\n# only elsewhere\nnot-a-real-package-zz==1.0 ; sys_platform == 'no-such-system' \\\n    --hash=sha256:" + "1" * 64 +
                                                    "\nnot-installed-zz==2.0 \\\n    --hash=sha256:" + "2" * 64 + "\n", encoding="utf-8")
todo = SU.packages_to_install(str(fake_lock))
check("Setup works out what has to be installed: another version than the tested one, or missing; packages for another system are skipped", [(n, w) for n, w, _h in todo] == [("openpyxl", "0.0.1"), ("not-installed-zz", "2.0")] and todo[0][2] not in ("", "0.0.1") and todo[1][2] == ""
      and SU.marker_applies("") and not SU.marker_applies("sys_platform == 'no-such-system'") and SU.marker_applies("sys_platform != 'no-such-system'"))
try: SU.install_packages(folder=str(TMP)); raised = ""
except RuntimeError as e: raised = str(e)
check("without the lock Setup installs nothing and says the release is incomplete", "requirements.lock is missing" in raised)
ran = []; _real_run = SU.run_pip; SU.run_pip = lambda cmd_, say=None, each=None: (ran.append(cmd_), (True, ""))[1]
_real_missing = SU.missing_packages; SU.missing_packages = lambda: []
try:
    shutil.copyfile(fake_lock, TMP / "requirements.lock"); said = SU.install_packages(folder=str(TMP))
finally: SU.run_pip = _real_run; SU.missing_packages = _real_missing
check("with the lock it runs exactly that one command (pip itself was replaced by a stand-in here: nothing was installed)", len(ran) == 1 and ran[0][-2:] == ["-r", str(TMP / "requirements.lock")] and "--require-hashes" in ran[0] and "2 package(s)" in said)
check("Setup needs a Python the pinned packages install on, and says so", SU.MIN_PYTHON == (3, 12) and "MIN_PYTHON" in setup and "too old" in setup)
check("Setup still installs for the current user only, keeps your settings and can remove the app", "HKEY_CURRENT_USER" in setup and "LOCALAPPDATA" in setup and "settings_modern.json" in setup and "--uninstall" in setup and "HKEY_LOCAL_MACHINE" not in setup)

# ---------------------------------------------------------------- the diagnostic file
check("diagnostics can be loaded without Qt and without the plotting libraries", subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import diagnostics; "
      "bad = [m for m in ('PySide6', 'matplotlib', 'pandas', 'numpy', 'smart_plots') if m in sys.modules]; sys.exit(1 if bad else 0)", str(APP)], capture_output=True).returncode == 0)
import diagnostics as D
FAKE = TMP / "installed app"; FAKE.mkdir()
(FAKE / "smart_plots.py").write_text('VERSION = "9.8.7"\n', encoding="utf-8"); (FAKE / "start.pyw").write_text("# start\n", encoding="utf-8")
(FAKE / "requirements.lock").write_text("openpyxl==3.1.5 \\\n    --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
(FAKE / "ZZQ-Sentinel own data.xlsx").write_bytes(b"not a program file")
(FAKE / "RELEASE_CONTENTS.md").write_text(f"| smart_plots.py | 18 | `{hashlib.sha256((FAKE / 'smart_plots.py').read_bytes()).hexdigest()}` |\n| start.pyw | 8 | `{'0' * 64}` |\n| gone.py | 1 | `{'1' * 64}` |\n", encoding="utf-8")
SAMPLE, FILEN, WINP, POSP = "ZZQ-Sentinel-Mix-7", "ZZQ-Sentinel 28d run.xlsx", r"C:\Users\Zed Quux\Lab Data ZZQ", "/home/zedquux/zzq private"
json.dump({"graphs": [{"file": WINP + "\\" + FILEN, "table": "ZZQ-Sheet", "sample": SAMPLE, "project": "ZZQ-Project"}], "files": [WINP + "\\" + FILEN]}, open(FAKE / "last_session.json", "w", encoding="utf-8"))
dkey = fake_key("anthropic", "diagnostics"); dtok = fake_key("github", "diagnostics")
(FAKE / "error_log.txt").write_text("\n".join([
    "Traceback (most recent call last):",
    f'  File "{WINP}\\Programs\\Origin Plot Studio\\smart_plots.py", line 120, in load_file',
    '    raise ValueError("bad table")',
    f"ValueError: I could not read {WINP}\\{FILEN} (sample {SAMPLE}, project ZZQ-Project)",
    f"row of the table: 10.5 20.25 30.125 44.0 55.5 61",
    f"request failed: Authorization: Bearer {dkey}",
    f"update token={dtok} was refused",
    f"KeyError: 'Intensity' in {POSP}/other_unknown_name.csv and in 'Unlisted File.csv'",
    f"saved the graph of {SAMPLE} as {FILEN.replace('.xlsx', '.png')}"]) + "\n", encoding="utf-8")
(FAKE / "last_run_log.txt").write_text(f"opened {FILEN}\nplotted table ZZQ-Sheet\n", encoding="utf-8")
dest = TMP / "out" / "diag.zip"; sent = []
socket.socket.connect = lambda self, *a, **k: sent.append(a) or _no_network()
info = D.build_bundle(str(dest), app_dir=str(FAKE))
dz = zipfile.ZipFile(dest); parts = {n: dz.read(n).decode("utf-8") for n in dz.namelist()}; everything = "\n".join(parts.values())
check("the diagnostic file is written to disk, nothing is sent, and the result says what is in it", dest.is_file() and not sent and info["path"] == str(dest) and sorted(info["files"]) == sorted(parts) == sorted(["MANIFEST.txt", "about.json", "program_files.json", "errors.json", "log.txt"]) and info["leftover"] == 0)
planted = [SAMPLE, "ZZQ", "Zed", "Quux", "zedquux", "zzq private", "Lab Data", FILEN, dkey, dtok, "other_unknown_name", "Unlisted File", "20.25", "44.0"]
check("no sample name, file name, folder, user name, credential or row of numbers planted in the logs is in any part of it", not [w for w in planted if w in everything], [w for w in planted if w in everything])
check("... the log is still useful: the error, the program file and line, and stand-ins where names were", 'File "<app>/smart_plots.py", line 120, in load_file' in parts["log.txt"] and "ValueError: I could not read <folder>" in parts["log.txt"]
      and "<sample 1>" in parts["log.txt"] and "[removed]" in parts["log.txt"] and "<numbers>" in parts["log.txt"] and "KeyError: 'Intensity'" in parts["log.txt"], parts["log.txt"])
ab = json.loads(parts["about.json"]); pf = json.loads(parts["program_files.json"]); er = json.loads(parts["errors.json"])
check("about.json: versions of the app, Python and the packages, the system, the security profile and the outbound level - not the computer's or the user's name", ab["version"] == "9.8.7" and ab["python"].count(".") == 2 and ab["system"]
      and ab["security_profile"] in ("friends", "owner") and ab["outbound_level"] in ("local_only", "minimal", "metadata", "scientific") and set(ab["outbound_channels"]) == {"update_check", "update_download", "ai", "web_search", "diagnostics", "learning_sync"}
      and ab["packages"]["openpyxl"]["tested"] == "3.1.5" and ab["key_store"] in ("dpapi", "keyring", "session") and "node" not in ab and "user" not in ab)
byname = {f["name"]: f for f in pf["files"]}
check("program_files.json: the installed program files with size and SHA-256, compared with the release list; other files are counted, not named", byname["smart_plots.py"]["sha256"] == hashlib.sha256((FAKE / "smart_plots.py").read_bytes()).hexdigest()
      and byname["smart_plots.py"]["release"] == "same" and byname["start.pyw"]["release"] == "changed" and byname["gone.py"]["release"] == "missing" and pf["compared_with_release"] and pf["other_files"] >= 3
      and not [f for f in pf["files"] if "Sentinel" in f["name"] or f["name"].endswith((".json", ".txt", ".xlsx"))])
check("errors.json: the kinds of errors and where they came from", {"error": "ValueError", "where": "smart_plots.py:120", "count": 1} in er and any(e["error"] == "KeyError" for e in er))
man = parts["MANIFEST.txt"]
check("MANIFEST.txt describes exactly what is inside, what was replaced and what is not inside, so it can be reviewed before sending", all(n in man for n in parts) and "NOT IN THIS ZIP" in man and "measurement data" in man and "credentials" in man
      and "REPLACED BEFORE WRITING" in man and "has not sent it anywhere" in man and "Read it" in man and info["replaced"]["credentials"] >= 2 and info["replaced"]["names"] >= 3 and info["replaced"]["paths"] >= 3 and info["replaced"]["numbers"] == 1)
info2 = D.build_bundle(str(TMP / "out" / "diag_nolog.zip"), app_dir=str(FAKE), include_log=False, names=["Extra-Known-Name"])
z2 = zipfile.ZipFile(info2["path"])
check("include_log=False leaves the log out and the manifest says so", "log.txt" not in z2.namelist() and "left out on request" in z2.read("MANIFEST.txt").decode("utf-8") and "ValueError" in z2.read("errors.json").decode("utf-8"))
src_d = (APP / "diagnostics.py").read_text(encoding="utf-8")
check("the module has no way to send anything: no network library is imported; an upload would have to pass outbound_policy.require('diagnostics', ...)",
      not re.search(r"^\s*(?:import|from)\s+(?:urllib|http|socket|requests|ftplib|smtplib|net)\b", src_d, re.M) and 'outbound_policy.require("diagnostics", url)' in src_d and not hasattr(D, "upload") and not hasattr(D, "send"))
real = D.build_bundle(str(TMP / "out" / "diag_real.zip"), app_dir=str(APP), include_log=False)
check("it also runs on the real program folder (without the log)", zipfile.ZipFile(real["path"]).testzip() is None and "smart_plots.py" in zipfile.ZipFile(real["path"]).read("program_files.json").decode("utf-8"))

# ---------------------------------------------------------------- the documents
sec = (ROOT / "SECURITY.md").read_text(encoding="utf-8"); prv = (ROOT / "PRIVACY.md").read_text(encoding="utf-8"); rel = (ROOT / "docs" / "RELEASE_PROCESS.md").read_text(encoding="utf-8")
check("SECURITY.md: supported versions, a private way to report (GitHub's private vulnerability reporting), no e-mail address, no claim of certification", "Supported versions" in sec and "Report a vulnerability" in sec
      and "private vulnerability reporting" in sec and "/security/advisories/new" in sec and not re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", sec) and "not been audited or certified" in sec and "does not cover" in sec.replace("do not cover", "does not cover"))
check("PRIVACY.md: what is stored and where, what each outbound level lets out, how long, how to delete, how to switch everything off; shared learning is off and not deployed",
      all(w in prv for w in ("What is stored on your computer", "Local-only", "Minimal", "Approved metadata", "Approved scientific content", "How long things are kept", "How to delete", "How to switch everything off", "OPS_LOCAL_ONLY"))
      and "off by default and is not a deployed service" in prv and not re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", prv))
check("docs/RELEASE_PROCESS.md: build, scan, inventory, sign, publish; what only the owner can do; never switching off Defender or certificate checks",
      all(w in rel for w in ("build_release.py", "secret_scan.py", "dependency_inventory.py", "sign_release.py", "RELEASE_CONTENTS.md", "manifest.json", "manifest.sig")) and "owner" in rel.lower() and "Defender" in rel and "never" in rel.lower())
no_claims = [w for w in ("certified secure", "guaranteed", "100%", "military-grade", "unhackable", "fully secure") if w in (sec + prv + rel).lower()]
check("the documents make no claim of being certified or guaranteed", not no_claims, no_claims)

socket.socket.connect = _real_connect
print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

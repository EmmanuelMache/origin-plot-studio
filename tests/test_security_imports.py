"""SEC-08: a portable project (.opsproject) is somebody else's data. Importing one must not write outside its own
staging folder, must not replace or damage anything that exists, must stop at clear limits, and must not bring settings
that are not a project's. Exported spreadsheets must keep text as text and numbers as numbers.
Everything here is SYNTHETIC: made-up names, made-up numbers, credentials built from pieces that are no key.
No network. Run:  python tests/test_security_imports.py"""
import os, sys, tempfile
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix="ops_sec_imports_"))
os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private"); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "cfg" / "settings_modern.json"); os.environ["ORIGIN_PLOT_APP_HOME"] = str(TMP / "store")
os.environ["OPS_NO_OPEN"] = "1"; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ.setdefault("MPLBACKEND", "Agg")
for _k in ("OPS_IMPORT_MAX_FILE_MB", "OPS_IMPORT_MAX_TOTAL_MB", "OPS_IMPORT_MAX_ENTRIES", "OPS_IMPORT_MAX_MANIFEST_MB", "OPS_IMPORT_MAX_RATIO", "OPS_PROFILE", "OPS_LOCAL_ONLY"): os.environ.pop(_k, None)
import hashlib, json, stat, struct, threading, time, types, warnings, zipfile
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); warnings.filterwarnings("ignore")
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" and not cond else ""))

# The settings of the app, in a temporary file: the same three functions workspace_qt has, without the window.
CFG = Path(os.environ["OPS_SETTINGS_FILE"]); CFG.parent.mkdir(parents=True)
stub = types.ModuleType("workspace_qt"); stub.cfg_path = lambda: CFG
def _load_cfg():
    try: return json.loads(CFG.read_text(encoding="utf-8"))
    except Exception: return {}
def _save_cfg(changes):
    cfg = _load_cfg(); cfg.update(changes); CFG.write_text(json.dumps(cfg, indent=1), encoding="utf-8"); return True
stub.load_cfg = _load_cfg; stub.save_cfg = _save_cfg; sys.modules["workspace_qt"] = stub
import workspace_projects as WP
import outbound_policy, secure_store

DATA = CFG.parent / "project_data"; SRC = TMP / "source"; SRC.mkdir(); ARC = TMP / "archives"; ARC.mkdir()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_file() else ""
def snapshot():
    """Everything the app keeps (settings and project data), file by file."""
    return {str(Path(d, f).relative_to(CFG.parent)): sha(Path(d, f)) for d, _s, fs in os.walk(CFG.parent) for f in fs}
def staging_left(): return [d.name for d in DATA.iterdir() if d.name.startswith(".staging")] if DATA.is_dir() else []
def manifest(files, **more): return dict({"schema": WP.SCHEMA, "name": "Synthetic demo", "files": list(files)}, **more)
def make(name, files=None, man=None, extra=(), raw=None, method=zipfile.ZIP_DEFLATED):
    """An archive: files {name inside: bytes} are listed by the manifest; extra [(name, bytes, mode)] are not."""
    p = ARC / name; files = files or {}
    with zipfile.ZipFile(p, "w", method) as z:
        for n, data in files.items(): z.writestr(n, data)
        for n, data, mode in extra:
            zi = zipfile.ZipInfo(n)
            if mode: zi.external_attr = mode << 16
            z.writestr(zi, data)
        if raw is not False: z.writestr("project.json", raw if raw is not None else json.dumps(man if man is not None else manifest(files)))
    return p
def patch_central(path, entry, offset, fmt, value):
    """Change one field in the table of contents of a zip (what the archive SAYS about an entry)."""
    data = bytearray(Path(path).read_bytes()); at = 0; enc = entry.encode()
    while True:
        at = data.find(b"PK\x01\x02", at)
        if at < 0: raise AssertionError("entry not found")
        n = struct.unpack("<H", data[at + 28:at + 30])[0]
        if bytes(data[at + 46:at + 46 + n]) == enc: struct.pack_into(fmt, data, at + offset, value); break
        at += 4
    Path(path).write_bytes(bytes(data))
def refused(name, archive, contains=None, **kw):
    """The import is refused with a plain reason, and nothing at all has changed: not the settings, not the project
    data, not the archive; no staging folder is left."""
    before = snapshot(); a = sha(archive); n = len(WP.list_projects())
    try: WP.import_project(archive, **kw); ok = False; msg = "it was imported"
    except WP.ProjectImportError as e: ok = True; msg = str(e)
    except Exception as e: ok = False; msg = f"{type(e).__name__}: {e}"
    same = snapshot() == before and sha(archive) == a and len(WP.list_projects()) == n and not staging_left()
    good = ok and same and (contains is None or contains in msg)
    check(name, good, "" if good else (msg[:160] + ("" if same else " | SOMETHING CHANGED ON DISK")))
    return msg

# ---------------------------------------------------------------- a legitimate round trip: export -> import
a_csv = SRC / "Synthetic_A.csv"; a_csv.write_text("x,y\n1,2.5\n2,-3.5\n", encoding="utf-8")
b_csv = SRC / "Synthetic_B.csv"; b_csv.write_bytes(b"x;y\r\n" + b"".join(b"%d;%d\r\n" % (i, i * i) for i in range(2000)))
slug = WP.create("Existing synthetic project", [str(a_csv), str(b_csv)]); folder = WP.add_folder(slug, "Scans"); WP.add_files(slug, [str(a_csv)], folder)
WP.set_file_settings(slug, str(a_csv), {"x": "x", "ys": ["y"]})
WP.save_state(slug, {"templates": [{"files": [str(a_csv)], "graph_id": "g1", "switches": {"markers": False}}], "selected": [str(b_csv)], "page": 2, "current_graph": str(a_csv) + "|Sheet1",
                     "session": {"files": [str(a_csv)], "graphs": [{"file": str(a_csv), "table": "Sheet1", "sample": "Synthetic A", "project_id": slug}], "settings": {"curve weight (pt)": 1.5}}})
good = ARC / "good.opsproject"; WP.export_project(slug, good); good_sha = sha(good); src_sha = (sha(a_csv), sha(b_csv)); before = snapshot()
progress = []
new = WP.import_project(good, progress=lambda done, total: progress.append((done, total)))
p = WP.get(new)
check("a project exported by the app is imported again: the result is the id of the new project, as plain text", isinstance(new, str) and new != slug and p is not None and p["name"] == "Existing synthetic project (imported)", new)
check("... its files are there with the same bytes and the same file names", [Path(f).name for f in p["files"]] == ["Synthetic_A.csv", "Synthetic_B.csv"] and (sha(p["files"][0]), sha(p["files"][1])) == src_sha)
ok_place = all(Path(f).parent.parent.name == "inputs" and Path(f).parent.name.isdigit() and len(Path(f).parent.parent.parent.name) == 32 and Path(f).parent.parent.parent.parent == DATA for f in p["files"])
check("... under names made by the app itself: <project data>/<new id>/inputs/<number>/<file name>", ok_place, p["files"][0])
check("... folders, file settings and saved graphs point at the imported copies", p["folders"][0]["name"] == "Scans" and p["locations"] == {p["files"][0]: folder} and p["file_settings"] == {p["files"][0]: {"x": "x", "ys": ["y"]}}
      and p["state"]["templates"][0]["files"] == [p["files"][0]] and p["state"]["templates"][0]["project_id"] == new and p["state"]["selected"] == [p["files"][1]] and p["state"]["page"] == 2
      and p["state"]["current_graph"] == p["files"][0] + "|Sheet1" and p["state"]["session"]["graphs"][0]["file"] == p["files"][0] and p["state"]["session"]["graphs"][0]["project_id"] == new
      and p["state"]["session"]["settings"] == {"curve weight (pt)": 1.5})
check("... the result says what was done; nothing had to be left out of a project the app wrote itself", new.files == 2 and new.dropped == [] and new.ignored == [] and new.bytes == a_csv.stat().st_size + b_csv.stat().st_size and "imported" in new.summary() and WP.LAST_IMPORT["slug"] == new)
check("... progress was reported while the files were unpacked", bool(progress) and progress[-1][0] >= progress[-1][1] > 0 and all(x[0] <= y[0] for x, y in zip(progress, progress[1:])))
check("... the archive, the original input files and the project that existed are untouched", sha(good) == good_sha and (sha(a_csv), sha(b_csv)) == src_sha and WP.get(slug)["files"] == [str(a_csv), str(b_csv)]
      and all(v == snapshot().get(k) for k, v in before.items() if k != CFG.name) and not staging_left())
again = WP.import_project(good)
check("importing the same archive again makes another project; none is replaced", again not in (slug, new) and WP.get(again)["name"] == "Existing synthetic project (imported 2)" and WP.get(new)["files"] == p["files"] and len(WP.list_projects()) == 3)

# ---------------------------------------------------------------- paths: every variant, listed by the project or merely present
HOSTILE = {
    "'..' out of the project": "inputs/../../escape.csv", "'..' at the start": "../escape.csv", "an absolute path": "/abs/escape.csv", "a drive letter": "C:/Users/Public/escape.csv",
    "a drive letter without a slash": "C:escape.csv", "a drive letter further inside": "inputs/C:/escape.csv", "a UNC path (backslashes)": "\\\\server\\share\\escape.csv",
    "a UNC path (slashes)": "//server/share/escape.csv", "a Windows device path": "\\\\?\\C:\\escape.csv", "backslashes as separators": "inputs\\..\\..\\escape.csv",
    "a backslash inside a name": "inputs/a\\b.csv", "an alternate data stream": "inputs/data.csv:hidden", "an alternate data stream on a folder": "inputs/dir:stream/data.csv",
    "the device NUL": "inputs/NUL", "the device nul with an extension": "inputs/nul.txt", "the device CON": "inputs/CON.csv", "the device COM1": "inputs/sub/COM1.csv",
    "the device LPT9": "inputs/lpt9.dat", "the device AUX": "inputs/aux", "the device PRN with two extensions": "inputs/PRN.tar.gz", "a device name with a space before the dot": "inputs/NUL .txt",
    "a folder named like a device": "inputs/CON/data.csv", "a trailing dot": "inputs/data.csv.", "a trailing space": "inputs/data.csv ", "a folder with a trailing dot": "inputs/dir./data.csv",
    "an empty part (two slashes)": "inputs//data.csv", "a '.' part": "inputs/./data.csv", "a control character": "inputs/be\x07ll.csv", "a character Windows forbids (<)": "inputs/a<b.csv",
    "a character Windows forbids (|)": "inputs/a|b.csv", "a character Windows forbids (?)": "inputs/a?.csv", "a character Windows forbids (*)": "inputs/a*.csv",
    "a character Windows forbids (\")": 'inputs/a"b.csv', "a name of 500 characters": "inputs/" + "a" * 500 + ".csv", "a path outside inputs/": "elsewhere/data.csv"}
escape = [TMP / "escape.csv", CFG.parent / "escape.csv", DATA / "escape.csv", Path("/abs/escape.csv")]
for what, bad in HOSTILE.items():
    refused(f"a project that lists {what} is refused", make("p.opsproject", {bad: b"x,y\n1,2\n"}), "Unsafe project input path")
    if not bad.startswith("elsewhere"):                                  # an entry nobody lists, outside inputs/, is merely not unpacked (see below)
        refused(f"... and so is an archive that only HOLDS {what}, beside a harmless project", make("p.opsproject", {"inputs/ok/data.csv": b"x,y\n1,2\n"}, extra=[(bad, b"x", 0)]), "Unsafe project input path")
check("no file landed anywhere outside the project data", not any(e.exists() for e in escape) and not any(f.name == "escape.csv" for f in TMP.rglob("*")))
check("the reason is said in words (drive letter, device name, data stream)", "drive letter" in WP.unsafe_name_reason("C:/x") and "device" in WP.unsafe_name_reason("inputs/nul.txt") and "data stream" in WP.unsafe_name_reason("inputs/a:b")
      and WP.unsafe_name_reason("inputs/0001/Synthetic A (2).csv") == "" and WP.unsafe_name_reason("inputs/ab12/Probe_\u00e4\u00f6\u00fc 28d.xlsx") == "" and WP.unsafe_name_reason("inputs/x/CONFIG.csv") == "" and WP.unsafe_name_reason("inputs/x/com10.csv") == "")
deep = WP.import_project(make("deep.opsproject", {"inputs/aa/bb/cc/dd/Synthetic_deep.csv": b"1,2\n"}))
check("folders inside the archive are not recreated: the file goes to a path the app makes", Path(WP.get(deep)["files"][0]).parent.name == "0001" and Path(WP.get(deep)["files"][0]).name == "Synthetic_deep.csv" and not list(DATA.rglob("cc")))
extra_ok = WP.import_project(make("extra.opsproject", {"inputs/a/Synthetic_listed.csv": b"1,2\n"}, extra=[("notes/readme.txt", b"hello", 0), ("inputs/a/Synthetic_unlisted.csv", b"9,9\n", 0)]))
check("entries the project does not list are not unpacked, and the result names them", sorted(extra_ok.ignored) == ["inputs/a/Synthetic_unlisted.csv", "notes/readme.txt"] and not list(DATA.rglob("Synthetic_unlisted.csv")) and not list(DATA.rglob("readme.txt")))

# ---------------------------------------------------------------- the same name twice, names that differ only in capitals
dup = ARC / "dup.opsproject"
with zipfile.ZipFile(dup, "w") as z:
    z.writestr("inputs/a/data.csv", b"1,2\n"); z.writestr("inputs/a/data.csv", b"3,4\n"); z.writestr("project.json", json.dumps(manifest(["inputs/a/data.csv"])))
refused("an archive that holds the same name twice is refused", dup, "same name twice")
refused("... and one with two names that differ only in capital letters (one file on Windows)", make("case.opsproject", {"inputs/a/Data.csv": b"1\n", "inputs/a/data.csv": b"2\n"}), "capital letters")
refused("... and one where two folders differ only in capital letters", make("case2.opsproject", {"inputs/A/data.csv": b"1\n", "inputs/a/data.csv": b"2\n"}), "capital letters")
refused("... and one with the same accented name stored in two ways", make("nfc.opsproject", {"inputs/a/caf\u00e9.csv": b"1\n", "inputs/a/cafe\u0301.csv": b"2\n"}), "same name twice")
refused("a project that lists the same input twice is refused", make("twice.opsproject", {"inputs/a/data.csv": b"1\n"}, man=manifest(["inputs/a/data.csv", "inputs/a/data.csv"])), "same input twice")

# ---------------------------------------------------------------- links and special files
for what, mode in (("a symbolic link", stat.S_IFLNK | 0o777), ("a named pipe", stat.S_IFIFO | 0o644), ("a character device", stat.S_IFCHR | 0o644), ("a block device", stat.S_IFBLK | 0o644), ("a socket", stat.S_IFSOCK | 0o644)):
    refused(f"an archive that holds {what} is refused", make("special.opsproject", {"inputs/a/data.csv": b"1\n"}, extra=[("inputs/a/link", b"/etc/hostname", mode)]), "link" if "link" in what else "special file")
    refused(f"... also when the project lists it as an input", make("special.opsproject", {}, man=manifest(["inputs/a/link.csv"]), extra=[("inputs/a/link.csv", b"../../../../etc/hostname", mode)]), "Unsafe project input path")
enc = make("enc.opsproject", {"inputs/a/data.csv": b"1,2\n"}); patch_central(enc, "inputs/a/data.csv", 8, "<H", 0x1)
refused("an archive with a password-protected entry is refused", enc, "password")
refused("an archive with another kind of compression than the app writes is refused", make("lzma.opsproject", {"inputs/a/data.csv": b"1,2\n" * 50}, method=zipfile.ZIP_LZMA), "compression")
check("(a zip has no hard links: every entry is a file, a folder, or one of the kinds refused above)", True)

# ---------------------------------------------------------------- sizes: one file, all files, counted while unpacking
MBYTE = 1024 * 1024; noise = hashlib.sha256(b"synthetic").digest() * (3 * MBYTE // 32)           # 3 MB that do not pack well... (they repeat: stored below)
big = make("big.opsproject", {"inputs/a/Synthetic_big.dat": noise}, method=zipfile.ZIP_STORED)
m = refused("a file larger than the limit for one file is refused, and the message names the limit and how to raise it", big, "OPS_IMPORT_MAX_FILE_MB", limits={"file_mb": 1})
check("... in words a person can act on", "limit for one file" in m and "environment variable" in m and "1 MB" in m, m)
m = refused("all files together larger than the limit of a project are refused the same way", make("total.opsproject", {f"inputs/{i}/Synthetic_{i}.dat": noise[:MBYTE] for i in range(3)}, method=zipfile.ZIP_STORED), "OPS_IMPORT_MAX_TOTAL_MB", limits={"total_mb": 2})
check("... the size cap of a project is said as before ('Project is larger than')", m.startswith("Project is larger than 2 MB"), m)
lie = make("lie.opsproject", {"inputs/a/Synthetic_big.dat": noise}, method=zipfile.ZIP_STORED); patch_central(lie, "inputs/a/Synthetic_big.dat", 24, "<I", 10)
refused("an archive that SAYS a 3 MB file has 10 bytes is refused; nothing of it stays", lie, limits={"file_mb": 1})
lie2 = make("lie2.opsproject", {"inputs/a/Synthetic_big.dat": b"0123456789" * 1000}); patch_central(lie2, "inputs/a/Synthetic_big.dat", 24, "<I", 4_000_000_000)
refused("... and so is one that claims 4 GB for a small file", lie2)
_orig = WP._check_entries                                                 # the first look at the declared sizes is made blind: only the count while unpacking is left
WP._check_entries = lambda z, lim, size, cancel: _orig(z, dict(lim, file=10 ** 15, total=10 ** 15), size, cancel)
try:
    refused("the bytes are counted while they are unpacked: the file limit holds even when the declared sizes are not looked at", big, "OPS_IMPORT_MAX_FILE_MB", limits={"file_mb": 1})
    refused("... and the project limit too", make("total.opsproject", {f"inputs/{i}/Synthetic_{i}.dat": noise[:MBYTE] for i in range(3)}, method=zipfile.ZIP_STORED), "OPS_IMPORT_MAX_TOTAL_MB", limits={"total_mb": 2})
finally: WP._check_entries = _orig
check("the default limits are generous for measurement files and written down as constants", WP.IMPORT_MAX_FILE_MB >= 512 and WP.IMPORT_MAX_TOTAL_MB == 2048 and WP.IMPORT_MAX_ENTRIES >= 1000 and WP.import_limits()["total"] == 2 * 1024 ** 3
      and WP.import_limits()["file"] == WP.IMPORT_MAX_FILE_MB * MBYTE)
_default = WP.IMPORT_MAX_FILE_MB; WP.IMPORT_MAX_FILE_MB = 1                 # as if the default were small: the large-file path is the environment variable
try:
    refused("with a small default, the 3 MB file is refused ...", big, "OPS_IMPORT_MAX_FILE_MB")
    os.environ["OPS_IMPORT_MAX_FILE_MB"] = "8"
    large = WP.import_project(big)
    check("... and imported once OPS_IMPORT_MAX_FILE_MB is raised: a large legitimate file has an explicit way in", sha(WP.get(large)["files"][0]) == hashlib.sha256(noise).hexdigest())
    os.environ["OPS_IMPORT_MAX_FILE_MB"] = "not a number"
    check("a value that is no number in the variable is ignored (the default stays)", WP.import_limits()["file"] == 1 * MBYTE)
finally: WP.IMPORT_MAX_FILE_MB = _default; os.environ.pop("OPS_IMPORT_MAX_FILE_MB", None)

# ---------------------------------------------------------------- how many entries
many = make("many.opsproject", {f"inputs/{i:03d}/Synthetic_{i}.csv": b"1,2\n" for i in range(60)})
refused("an archive with more entries than the limit is refused before anything is read", many, "OPS_IMPORT_MAX_ENTRIES", limits={"entries": 50})
ok_many = WP.import_project(many)
check("... the same archive is fine under the default limit", len(WP.get(ok_many)["files"]) == 60 and all(Path(f).is_file() for f in WP.get(ok_many)["files"]))
refused("a project with thousands of folders is refused", make("folders.opsproject", {}, man=manifest([], folders=[{"id": f"f{i}", "name": "F"} for i in range(WP.IMPORT_MAX_FOLDERS + 1)])), "folders")

# ---------------------------------------------------------------- the manifest (project.json)
f1 = {"inputs/a/data.csv": b"1,2\n"}
refused("a project.json larger than its limit is refused", make("m.opsproject", f1, man=manifest(f1, state={"session": {"note": "n" * 60000}})), "OPS_IMPORT_MAX_MANIFEST_MB", limits={"manifest_mb": 0.01})
nest = {}; cur = nest
for _ in range(200): cur["k"] = {}; cur = cur["k"]
refused("a project.json nested 200 levels deep is refused", make("m.opsproject", f1, man=manifest(f1, state={"session": nest})), "nested too deeply")
refused("... and one nested 100 000 levels deep is refused without the app falling over", make("m.opsproject", f1, raw='{"schema": "' + WP.SCHEMA + '", "name": "n", "files": [], "state": ' + "[" * 100000 + "]" * 100000 + "}"), "nested too deeply")
refused("a project.json that is not JSON is refused", make("m.opsproject", f1, raw="{this is not json"), "cannot be read")
refused("a project.json that is not text is refused", make("m.opsproject", f1, raw=b"\xff\xfe\x00\x01 not utf-8 \x80"), "not text")
refused("a project.json that is a list, not an object, is refused", make("m.opsproject", f1, raw="[1, 2, 3]"), "Unsupported project format")
refused("a project.json of another format is refused", make("m.opsproject", f1, man=dict(manifest(f1), schema="something/else")), "Unsupported project format")
refused("a project.json that names a setting twice is refused", make("m.opsproject", f1, raw='{"schema": "' + WP.SCHEMA + '", "name": "a", "name": "b", "files": []}'), "twice")
refused("a project.json whose list of files is not a list is refused", make("m.opsproject", f1, man=dict(manifest(f1), files="inputs/a/data.csv")), "Unsupported project format")
refused("... or holds something that is not a name", make("m.opsproject", f1, man=dict(manifest(f1), files=[["inputs/a/data.csv"]])), "Unsafe project input path")
refused("a project.json with a text of several million characters is refused", make("m.opsproject", f1, man=manifest(f1, state={"session": {"note": "n" * (WP.IMPORT_MAX_STRING + 1)}})), "too long")
refused("an archive without project.json is refused", make("m.opsproject", f1, raw=False), "no project.json")
refused("a project that lists a file the archive does not hold is refused (as a plain reason, not a program error)", make("m.opsproject", f1, man=manifest(["inputs/a/data.csv", "inputs/b/missing.csv"])), "incomplete")
odd = WP.import_project(make("odd.opsproject", f1, man=dict(manifest(f1), name=["not", "text"], folders="none", locations=[1], file_settings=7, state="x", created="yesterday", id=5)))
check("values of the wrong type in project.json are not taken over (name, folders, locations, settings, state, dates)", WP.get(odd)["name"].startswith("Untitled project") and WP.get(odd)["folders"] == [] and WP.get(odd)["locations"] == {}
      and WP.get(odd)["file_settings"] == {} and WP.get(odd)["state"] == {} and "created" not in WP.get(odd) and WP.get(odd)["id"] == odd)

# ---------------------------------------------------------------- cut off, damaged, not an archive
whole = good.read_bytes()
for what, data in (("cut off near the end", whole[:-60]), ("cut in half", whole[:len(whole) // 2]), ("only its first bytes", whole[:20]), ("empty", b""), ("not an archive at all", b"x,y\n1,2\n" * 500),
                   ("an archive with its end damaged", whole[:-22] + b"\0" * 22)):
    t = ARC / "trunc.opsproject"; t.write_bytes(data)
    refused(f"a project file that is {what} is refused with a reason a person understands", t, "damaged or was cut off")
stored = make("crc.opsproject", {"inputs/a/Synthetic_crc.dat": noise[:200000]}, method=zipfile.ZIP_STORED); raw_ = bytearray(stored.read_bytes()); i0 = raw_.find(noise[:64]) + 5000
raw_[i0:i0 + 64] = bytes(64); stored.write_bytes(bytes(raw_))
refused("a project file whose content was changed after it was packed (checksum wrong) is refused; the part already unpacked is removed", stored, "damaged or was cut off")
refused("a path that is not a file is refused", ARC / "does_not_exist.opsproject", "not found")

# ---------------------------------------------------------------- an archive that unpacks to far more than it is
bomb = make("bomb.opsproject", {"inputs/a/Synthetic_zeros.dat": bytes(16 * MBYTE)})
check("(the test archive really is tiny: 16 MB packed into a few kB)", bomb.stat().st_size < 64 * 1024, bomb.stat().st_size)
m = refused("a file that unpacks to a thousand times its packed size is refused, with the limit and the variable named", bomb, "OPS_IMPORT_MAX_RATIO")
sparse = WP.import_project(bomb, limits={"ratio": 5000})
check("... a legitimate file of that kind (a detector map of zeros) is imported when the ratio is raised on purpose", Path(WP.get(sparse)["files"][0]).stat().st_size == 16 * MBYTE)
small_ratio = WP.import_project(make("smallzeros.opsproject", {"inputs/a/Synthetic_small_zeros.csv": b"0,0\n" * 100000}))
check("small files that pack very well are not affected by the ratio", Path(WP.get(small_ratio)["files"][0]).stat().st_size == 400000)
_orig = WP._check_entries; WP._check_entries = lambda z, lim, size, cancel: _orig(z, dict(lim, ratio=10 ** 9), size, cancel)
try: refused("the ratio is watched while unpacking too", bomb, "OPS_IMPORT_MAX_RATIO")
finally: WP._check_entries = _orig

# ---------------------------------------------------------------- cancel
three = make("three.opsproject", {f"inputs/{i}/Synthetic_{i}.dat": noise[:2 * MBYTE] for i in range(3)}, method=zipfile.ZIP_STORED)
calls = [0]
def stop_later(): calls[0] += 1; return calls[0] > 12                    # says stop in the middle of unpacking
before = snapshot(); n_before = len(WP.list_projects())
try: WP.import_project(three, cancel=stop_later); cancelled = False
except WP.ImportCancelled as e: cancelled = "cancelled" in str(e)
check("an import stopped in the middle is cancelled cleanly: no project, no staging folder, nothing changed", cancelled and calls[0] > 12 and snapshot() == before and len(WP.list_projects()) == n_before and not staging_left())
ev = threading.Event(); ev.set()
try: WP.import_project(three, cancel=ev); cancelled = False
except WP.ImportCancelled: cancelled = True
check("a threading.Event works as the stop signal too, before anything is unpacked", cancelled and snapshot() == before and not staging_left())
check("ImportCancelled and ProjectImportError are ValueErrors (the window shows their text like any other reason)", issubclass(WP.ImportCancelled, WP.ProjectImportError) and issubclass(WP.ProjectImportError, ValueError))
check("without a stop signal the same archive is imported", len(WP.get(WP.import_project(three, cancel=lambda: False))["files"]) == 3)
old = DATA / (".staging-" + "0" * 32); old.mkdir(); (old / "left.bin").write_bytes(b"x"); os.utime(old, (time.time() - 3 * 86400,) * 2)
fresh = DATA / (".staging-" + "1" * 32); fresh.mkdir()
WP.import_project(good)
check("what an import left behind when the app was closed mid-way is removed by a later import (older than a day only)", not old.exists() and fresh.exists())
fresh.rmdir()

# ---------------------------------------------------------------- a project cannot bring settings that are not a project's
key = "sk-" + "ant-" + hashlib.sha256(b"synthetic key 1").hexdigest()[:30]                 # built from pieces: not a real key
level0 = outbound_policy.level(); profile0 = outbound_policy.profile(); chan0 = {c: outbound_policy.channel_on(c) for c in outbound_policy.CHANNELS}
hostile = manifest(f1, credentials={"anthropic": key}, update_source="github:someone/else", update_token=key, trusted_update_keys=["AAAA"], outbound_policy={"level": "scientific"},
                   security_profile="owner", origin_exe="C:/evil/Origin.exe", python_exe="C:/evil/python.exe", settings={"dpi_aware": False}, projects={"other": {}}, api_key=key,
                   folders=[{"id": "f1", "name": "Scans", "parent": "", "security_profile": "owner"}],
                   locations={"inputs/a/data.csv": "f1", "C:/Windows/win.ini": "f1"},
                   file_settings={"inputs/a/data.csv": {"x": "x", "api_key": key, "origin_path": "C:/evil", "nested": {"update_source": "evil", "token": key, "keep": 1}}, "/etc/hostname": {"x": "x"}},
                   state={"session": {"files": ["inputs/a/data.csv", "\\\\evil-host\\share\\steal.csv", "C:\\Users\\victim\\private.xlsx", "/etc/hostname"],
                                      "info_files": ["//evil-host/share/names.csv"], "sources": {"inputs/a/data.csv": {"sha256": "0" * 64}, "\\\\evil-host\\share\\steal.csv": {}},
                                      "graphs": [{"file": "inputs/a/data.csv", "table": "t", "custom": {"label": "\\\\evil-host\\share\\picture.png", "Authorization": "Bearer " + key}},
                                                 {"file": "\\\\evil-host\\share\\steal.csv", "table": "t"}],
                                      "figures": [{"keys": ["inputs/a/data.csv|t"], "cols": 1}, {"keys": ["C:\\Users\\victim\\private.xlsx|t"], "cols": 1}],
                                      "password": "hunter2-synthetic", "ai_link": "http://evil.invalid"},
                          "templates": [{"files": ["inputs/a/data.csv"], "graph_id": "ok"}, {"files": ["\\\\evil-host\\share\\steal.csv"], "graph_id": "bad"}, {"graph_id": "no files"}],
                          "selected": ["inputs/a/data.csv", "\\\\evil-host\\share\\steal.csv"], "groups": [["overlay", ["inputs/a/data.csv|t"]], ["overlay", ["//evil-host/x|t"]]],
                          "group_formats": [[["inputs/a/data.csv|t"], {"colour": "red"}], [["/etc/hostname|t"], {}]], "current_graph": "\\\\evil-host\\share\\steal.csv|t",
                          "update_source": "evil", "security_profile": "owner", "outbound_level": "scientific", "page": 3, "startup_script": "calc.exe"})
cfg_before = {k: v for k, v in _load_cfg().items() if k != "projects"}
h = WP.import_project(make("hostile.opsproject", f1, man=hostile)); hp = WP.get(h); text = json.dumps(hp)
check("a project that carries credentials, an update source, update keys, the outbound policy, the security profile and program paths is imported WITHOUT them",
      all(k not in hp for k in ("credentials", "update_source", "update_token", "trusted_update_keys", "outbound_policy", "security_profile", "origin_exe", "python_exe", "settings", "projects", "api_key")) and set(hp) <= set(WP.PROJECT_KEYS))
check("... also where they hide inside the saved state and the file settings", key not in text and "evil" not in text and "hunter2" not in text and "calc.exe" not in text and "security_profile" not in text and "update_source" not in text
      and "origin_path" not in text and hp["file_settings"] == {hp["files"][0]: {"x": "x", "nested": {"keep": 1}}} and "startup_script" not in hp["state"] and "outbound_level" not in hp["state"], text[:300])
st = hp["state"]
check("... and no reference to a file outside the project survives: network paths, other folders, system files", "victim" not in text and "hostname" not in text and "win.ini" not in text and st["session"]["files"] == [hp["files"][0]]
      and st["session"]["info_files"] == [] and list(st["session"]["sources"]) == [hp["files"][0]] and len(st["session"]["graphs"]) == 1 and len(st["session"]["figures"]) == 1 and [t["graph_id"] for t in st["templates"]] == ["ok"]
      and st["selected"] == [hp["files"][0]] and len(st["groups"]) == 1 and len(st["group_formats"]) == 1 and "current_graph" not in st and st["page"] == 3 and hp["locations"] == {hp["files"][0]: "f1"}
      and hp["folders"] == [{"id": "f1", "name": "Scans", "parent": ""}])
said = " | ".join(h.dropped)
check("the result of the import says what was left out, by name and never by value", all(w in said for w in ("credentials", "update_source", "update_token", "trusted_update_keys", "outbound_policy", "security_profile", "origin_exe", "python_exe", "api_key", "password", "startup_script"))
      and "security or program setting" in said and "not part of the project" in said and key not in said and "hunter2" not in said and "Left out" in h.summary(), said[:400])
check("the settings of the app outside the list of projects are exactly as before", {k: v for k, v in _load_cfg().items() if k != "projects"} == cfg_before and set(_load_cfg()) == {"projects"})
outbound_policy.reload()
check("the outbound level, its channels and the security profile are as before; no credential was stored", outbound_policy.level() == level0 and outbound_policy.profile() == profile0 and {c: outbound_policy.channel_on(c) for c in outbound_policy.CHANNELS} == chan0
      and not secure_store.has("anthropic") and not (TMP / "private" / "credentials.json").exists())
check("names of files and graphs are not mistaken for settings (a file called token_data.csv keeps its settings)",
      WP.get(WP.import_project(make("tok.opsproject", {"inputs/a/token_data.csv": b"1\n"}, man=manifest(["inputs/a/token_data.csv"], file_settings={"inputs/a/token_data.csv": {"x": "x"}}, locations={"inputs/a/token_data.csv": ""}))))["file_settings"] != {})

# ---------------------------------------------------------------- export: names every system accepts, no settings that are not a project's
odd_file = SRC / "Synthetic a:b?.csv"
try: odd_file.write_text("1,2\n"); made = True
except OSError: made = False                                              # Windows cannot hold such a name: nothing to test there
if made:
    s2 = WP.create("Synthetic odd names", [str(odd_file)]); out = ARC / "odd_names.opsproject"; WP.export_project(s2, out)
    names = zipfile.ZipFile(out).namelist(); back = WP.import_project(out)
    check("a file whose name another system cannot hold is exported under a safe name, so the project can be imported everywhere", all(WP.unsafe_name_reason(n) == "" for n in names) and Path(WP.get(back)["files"][0]).name == "Synthetic a_b_.csv", names)
allp = _load_cfg()["projects"]; allp[slug]["update_token"] = key; allp[slug]["state"]["session"]["note"] = "see key " + key; allp[slug]["state"]["api_key"] = key; _save_cfg({"projects": allp})
out = ARC / "clean_export.opsproject"; WP.export_project(slug, out); exported = zipfile.ZipFile(out).read("project.json").decode("utf-8")
check("an exported project holds no setting that is not a project's and no credential, even when one got into its data", key not in exported and "update_token" not in exported and "api_key" not in exported and "[removed]" in exported)
check("... and is still a complete project", json.loads(exported)["files"] and json.loads(exported)["schema"] == WP.SCHEMA and WP.get(WP.import_project(out))["files"])

# ---------------------------------------------------------------- everything that existed is still there, byte for byte
check("after all of the above: the original input files, the first archive and the first project are unchanged", (sha(a_csv), sha(b_csv)) == src_sha and sha(good) == good_sha and (sha(p["files"][0]), sha(p["files"][1])) == src_sha
      and WP.get(new)["files"] == p["files"] and not staging_left())
made_here = {slug} | ({s2} if made else set()); imported = [(s_, pr) for s_, pr in WP.list_projects() if s_ not in made_here]
check("every file of every imported project lies inside the project data folder and nowhere else", len(imported) >= 12 and all(os.path.commonpath([os.path.realpath(f), os.path.realpath(DATA)]) == os.path.realpath(DATA) and Path(f).is_file() for _s, pr in imported for f in pr["files"]), len(imported))

# ---------------------------------------------------------------- export to spreadsheets: text stays text, numbers stay numbers
import numpy as np, pandas as pd
import safe_export as SE
esc = {"=1+1": "'=1+1", "+cmd|' /C calc'!A0": "'+cmd|' /C calc'!A0", "-2+3": "'-2+3", "@SUM(A1:A9)": "'@SUM(A1:A9)", "\t=1+1": "'\t=1+1", "\r=1+1": "'\r=1+1", "=HYPERLINK(\"http://example.invalid\")": "'=HYPERLINK(\"http://example.invalid\")",
       "-OH band": "'-OH band", "=C=O": "'=C=O"}
check("a text that a spreadsheet would read as a formula gets a single quote in front (= + - @ tab CR)", all(SE.escape_cell(k) == v for k, v in esc.items()), [k for k, v in esc.items() if SE.escape_cell(k) != v])
same = ["-1.5", "+3", "-2.5e-3", "-1,5", "1e5", "-", "--", "+", "", "plain text", "a=b", "5 - 3", "-inf", "+12 %", "\u22125"]
check("numbers written as text, a lone sign and ordinary text are left exactly as they are", all(SE.escape_cell(v) == v for v in same), [v for v in same if SE.escape_cell(v) != v])
real = [5, -5, -1.5, 0.0, np.float64(-2.25), np.int64(-7), None, True, float("inf")]
check("real numbers (and None) are returned as the same object type and value", all(SE.escape_cell(v) is v or (SE.escape_cell(v) == v and type(SE.escape_cell(v)) is type(v)) for v in real) and SE.escape_cell(float("nan")) != SE.escape_cell(float("nan")))
df = pd.DataFrame({"=SUM(A1)": [1.5, -2.5, 3.0], "Sample": ["Synthetic A", "=HYPERLINK(\"http://example.invalid\",\"x\")", "-3.2"], "n": np.array([-1, 2, 3], dtype="int64"), "@note": ["+cmd", None, "ok"],
                   "mixed": [1, "@x", -2.5], "-1.5": [0.1, 0.2, 0.3]})
sf = SE.safe_frame(df)
check("a table for export: formula-like headers and text cells are neutralised", list(sf.columns) == ["'=SUM(A1)", "Sample", "n", "'@note", "mixed", "-1.5"] and sf["Sample"].tolist() == ["Synthetic A", "'=HYPERLINK(\"http://example.invalid\",\"x\")", "-3.2"]
      and sf["'@note"].tolist()[0] == "'+cmd" and sf["mixed"].tolist() == [1, "'@x", -2.5], sf.to_dict("list"))
check("... numeric columns keep their values and their dtype, bit for bit", sf["'=SUM(A1)"].dtype == df["=SUM(A1)"].dtype == np.float64 and sf["n"].dtype == np.int64 and np.array_equal(sf["'=SUM(A1)"].to_numpy(), df["=SUM(A1)"].to_numpy())
      and np.array_equal(sf["n"].to_numpy(), df["n"].to_numpy()) and sf["-1.5"].tolist() == [0.1, 0.2, 0.3])
check("... the table that was given is not changed", list(df.columns)[0] == "=SUM(A1)" and df["Sample"].tolist()[1].startswith("=HYPERLINK") and df["mixed"].tolist()[1] == "@x")
nums = pd.DataFrame({"x": [1.0, 2.0], "y": [-0.5, 1e-9]})
check("... a table with nothing to change is passed through as it is", SE.safe_frame(nums) is nums)

# the real export of the Workbook page (CSV, TSV, Excel), and the merged workbook
sys.modules.pop("workspace_qt", None)                                     # from here on the app's own modules
import openpyxl
import workspace_workbook as WB, related as R
status = []
page = types.SimpleNamespace(model=types.SimpleNamespace(df=df), path=None, _series_label="Synthetic", sheet=None, controller=None, ws=types.SimpleNamespace(set_status=status.append))
def export_to(name):
    out_ = TMP / name; WB.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(out_), "")); return WB.WorkbookPage.export_data(page), out_
r, out_ = export_to("export.csv"); back = pd.read_csv(out_)
check("Workbook > Export as CSV: no cell or header starts a formula; the numbers read back as the same numbers", r == str(out_) and not any(l.startswith(("=", "+", "@")) or ",=" in l or ",@" in l or ",+" in l for l in out_.read_text(encoding="utf-8").splitlines())
      and back["'=SUM(A1)"].dtype == np.float64 and back["'=SUM(A1)"].tolist() == [1.5, -2.5, 3.0] and back["n"].tolist() == [-1, 2, 3] and back["n"].dtype == np.int64 and str(back["Sample"].tolist()[2]) == "-3.2" and back["-1.5"].tolist() == [0.1, 0.2, 0.3], out_.read_text(encoding="utf-8")[:200])
r, out_ = export_to("export.tsv"); back = pd.read_csv(out_, sep="\t")
check("Workbook > Export as TSV: the same", r == str(out_) and list(back.columns)[0] == "'=SUM(A1)" and back["'=SUM(A1)"].tolist() == [1.5, -2.5, 3.0] and back["Sample"].tolist()[1].startswith("'=HYPERLINK"))
r, out_ = export_to("export.xlsx"); ws_ = openpyxl.load_workbook(out_)["Data"]; cells = [c for row in ws_.iter_rows() for c in row]
check("Workbook > Export as Excel: no cell is a formula; text that looked like one is text with a quote", r == str(out_) and not any(c.data_type == "f" for c in cells) and ws_.cell(1, 1).value == "'=SUM(A1)" and ws_.cell(3, 2).value.startswith("'=HYPERLINK") and ws_.cell(2, 4).value == "'+cmd")
check("... the numbers are numbers in the file, with their values", [ws_.cell(2, 1).value, ws_.cell(3, 1).value, ws_.cell(4, 1).value] == [1.5, -2.5, 3.0] and all(ws_.cell(i, 1).data_type == "n" for i in (2, 3, 4)) and [ws_.cell(2, 3).value, ws_.cell(3, 3).value] == [-1, 2]
      and ws_.cell(2, 3).data_type == "n" and ws_.cell(4, 2).value == "-3.2")
check("the page still says where the file went", any("exported" in s for s in status), status)

class Table:                                                              # what merged_workbook needs of a table: the x column, the y columns, their numbers
    def __init__(self, x, ys, data): self.x = x; self.ys = ys; self._d = data
    def arr(self, c): return np.asarray(self._d[c], dtype=float)
t1 = Table("=cmd|' /C calc'!A0", ["-2+3 counts", "Mass (%)"], {"=cmd|' /C calc'!A0": [1.0, 2.0, 3.0], "-2+3 counts": [-1.5, 2.5, 1e-12], "Mass (%)": [99.5, 98.25, 97.125]})
t2 = Table("Temperature (\u00b0C)", ["@risk"], {"Temperature (\u00b0C)": [30.0, 40.0], "@risk": [-0.5, 0.5]})
peaks = lambda p_: pd.DataFrame({"Position": [2.0], "Label": ["=HYPERLINK(\"http://example.invalid\")"], "May be": ["+cmd"], "Other possibilities": ["-1.5"]}) if "one" in p_ else None
merged = TMP / "merged.xlsx"; sheets = R.merged_workbook(str(merged), [(str(TMP / "Synthetic_one.csv"), t1), (str(TMP / "Synthetic_two.csv"), t2)], peaks=peaks)
wb = openpyxl.load_workbook(merged); allc = [c for s in wb.worksheets for row in s.iter_rows() for c in row]; first = wb[sheets[0]]
check("merged workbook: no formula in any sheet; headers and peak labels that looked like one are text", not any(c.data_type == "f" for c in allc) and not any(isinstance(c.value, str) and c.value.startswith(("=", "@", "+")) for c in allc)
      and first.cell(1, 1).value.startswith("'=cmd") and first.cell(1, 2).value == "'-2+3 counts" and wb[R.PEAKS_OVERVIEW].cell(2, 3).value.startswith("'=HYPERLINK") and wb[R.PEAKS_OVERVIEW].cell(2, 4).value == "'+cmd")
check("... every number is the number that went in, as a number", [first.cell(2, 1).value, first.cell(3, 1).value, first.cell(4, 1).value] == [1.0, 2.0, 3.0] and [first.cell(2, 2).value, first.cell(3, 2).value, first.cell(4, 2).value] == [-1.5, 2.5, 1e-12]
      and [first.cell(2, 3).value, first.cell(4, 3).value] == [99.5, 97.125] and all(first.cell(row=r_, column=c_).data_type == "n" for r_ in (2, 3, 4) for c_ in (1, 2, 3)) and wb[R.PEAKS_OVERVIEW].cell(2, 2).value == 2.0
      and wb[R.PEAKS_OVERVIEW].cell(2, 5).value in ("-1.5", -1.5) and [wb[sheets[1]].cell(2, 2).value, wb[sheets[1]].cell(3, 2).value] == [-0.5, 0.5])

print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

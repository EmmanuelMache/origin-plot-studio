"""Updates are verified before anything of them runs, installed in two steps, and recovered when cut off (SEC-02, SEC-05).

Everything here is synthetic: the "program" is a few small files made by this test, the "release" is a zip of them, and the
signing key is made new in memory at every run (it is never written into the repository, and update_trust.py stays empty).
No request leaves the computer: the downloads are answered by a stand-in for the opener of net.py, on .invalid and on the
GitHub host names the updater would use; a real socket connection would fail the run.
What this cannot show: a real release on GitHub, the production key, and renaming program files on Windows while the
app runs - those need a check with a real release on a Windows computer.
Run:  python tests/test_security_update.py"""
import os, sys, io, json, base64, shutil, socket, hashlib, zipfile, tempfile, contextlib, subprocess, urllib.error, email.message
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix="ops_secupd_"))
os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private"); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json")
os.environ["OPS_NO_OPEN"] = "1"; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["OPS_PROFILE"] = "owner"; os.environ["OPS_NO_KEYRING"] = "1"; os.environ.pop("OPS_LOCAL_ONLY", None); os.environ.pop("OPS_ALLOW_TEST_KEYS", None)
MARK = TMP / "marks"; MARK.mkdir(); os.environ["OPS_TEST_MARK"] = str(MARK)
ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "origin_plot_app"; sys.path.insert(0, str(A)); sys.path.insert(0, str(ROOT / "tools"))
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{' '.join(str(info)[:300].split())}]" if info != "" else ""))
def raised(fn, *types):
    try: fn()
    except BaseException as e: return e if (not types or isinstance(e, types)) else None
    return None
def _no_network(*a, **k): raise AssertionError("a test tried to open a real network connection")
socket.socket.connect = _no_network; socket.create_connection = _no_network

import outbound_policy as op, net, self_update as su, update_verify as uv, update_trust, sign_release as SR
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
def profile(p, connected=True):
    """Switch the profile of the build. connected: the user has allowed connections (a 'friends' build starts local-only)."""
    os.environ["OPS_PROFILE"] = p; op.reload()
    if connected: op.set_level("minimal")
profile("owner")
check("the repository ships no publisher key yet (update_trust.TRUSTED_KEYS is empty until the owner adds the production key)", update_trust.TRUSTED_KEYS == {})
check("the files that decide trust are replaced only by a verified update", set(su.PROTECTED) == {"update_trust.py", "security_profile.json"} and "update_trust.py" in su.program_files(str(A)))

# ---------------------------------------------------------------- a key made for this run only, and the synthetic program
KEY = Ed25519PrivateKey.generate(); KID = "unit-key-of-this-run"
OTHER = Ed25519PrivateKey.generate()
update_trust.TRUSTED_KEYS = {KID: SR.public_b64(KEY)}           # in memory only: what an installed copy would hold
PLAT = uv.this_platform()

def program(folder, version, extra="", new_file=False, trust_text="TRUSTED_KEYS = {}\n"):
    """A tiny stand-in for the program: it answers --dry-run like the real one (and leaves a mark, so the test sees that it RAN)."""
    f = Path(folder); (f / "examples_synthetic").mkdir(parents=True, exist_ok=True); (f / "opstudio").mkdir(exist_ok=True)
    (f / "origin_plot_app.py").write_text("import os, sys\nif '--dry-run' in sys.argv:\n    m = os.environ.get('OPS_TEST_MARK')\n    if m: open(os.path.join(m, 'ran_" + version + "'), 'w').write('x')\n"
                                          "    open('dry_commands.txt', 'w').write('worksheet; plot ' + os.path.basename(sys.argv[-1]) + " + repr(extra) + " + '\\n')\n", encoding="utf-8")
    (f / "smart_plots.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
    (f / "helper.py").write_text(f"WHAT = 'helper of {version}'\n", encoding="utf-8")
    (f / "update_trust.py").write_text(trust_text, encoding="utf-8")
    (f / "WHATS_NEW.txt").write_text(f"synthetic notes of {version}\n", encoding="utf-8")
    (f / "examples_synthetic" / "synthetic_sample.csv").write_text("x,y\n1,2\n2,3\n", encoding="utf-8")
    (f / "opstudio" / "__init__.py").write_text("", encoding="utf-8"); (f / "opstudio" / "catalog.json").write_text("{}", encoding="utf-8")
    if new_file: (f / "added_by_update.py").write_text("NEW = 1\n", encoding="utf-8")
    return str(f)

def zip_of(folder, path, top="Origin_Plot_Studio/"):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(Path(folder).rglob("*")):
            if p.is_file(): z.write(p, top + p.relative_to(folder).as_posix())
    return str(path)

def release(name, version, key=KEY, kid=KID, platform=None, min_python="3.9", manifest_version=None, **prog):
    """A folder with <zip>, manifest.json and manifest.sig. Returns (folder, zip path, manifest bytes, signature bytes)."""
    d = TMP / "releases" / name; d.mkdir(parents=True)
    src = program(TMP / "src" / name, version, **prog); z = zip_of(src, d / f"Synthetic_Release_{version}.zip")
    m = SR.make_manifest(z, manifest_version or version, kid, platform or [PLAT], min_python); mb = uv.canonical(m); sb = SR.sign_bytes(mb, key)
    (d / "manifest.json").write_bytes(mb); (d / "manifest.sig").write_bytes(sb)
    return d, z, mb, sb

def installed(name, version="1.0.0"):
    return program(TMP / "apps" / name / "app", version), str(TMP / "apps" / name / "backups")

def snap(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).rglob("*")) if p.is_file() and "__pycache__" not in p.parts}

# what RUNS: every start of a program and every call of the trial check is written down
RAN = []; DRY = []
real_run, real_dry = subprocess.run, su._dry
def spy_run(cmd, *a, **k): RAN.append(list(cmd)); return real_run(cmd, *a, **k)
def spy_dry(app_dir, data_file, work): DRY.append(app_dir); return real_dry(app_dir, data_file, work)
subprocess.run = spy_run; su._dry = spy_dry
def nothing_ran(version=None): return RAN == [] and DRY == [] and (version is None or not (MARK / f"ran_{version}").exists())
def reset():
    del RAN[:]; del DRY[:]
    for p in MARK.iterdir(): p.unlink()

# ================================================================ the manifest and its signature
rd, rz, mb, sb = release("good", "2.0.0")
m = uv.verify_release(rz, mb, sb, current_version="1.0.0")
check("a release signed with the trusted key verifies: signature, size, SHA-256, version, system, structure", m["version"] == "2.0.0" and m["artifact"] == os.path.basename(rz) and m["key_id"] == KID and m["schema"] == "opstudio.release/1")
check("the manifest is canonical JSON with exactly the stated fields", mb == uv.canonical(json.loads(mb)) and set(json.loads(mb)) == {"schema", "version", "artifact", "sha256", "size", "platform", "min_python", "created", "key_id"})
def refused(fn, *words):
    e = raised(fn, uv.VerifyError); return e is not None and all(w.lower() in str(e).lower() for w in words)
changed = mb.replace(b'"version":"2.0.0"', b'"version":"9.0.0"')
check("invalid signature: a manifest changed after signing is refused", changed != mb and refused(lambda: uv.verify_manifest(changed, sb), "not valid"))
check("invalid signature: a signature made with another key (under the trusted key's name) is refused", refused(lambda: uv.verify_manifest(mb, SR.sign_bytes(mb, OTHER)), "not valid"))
check("a damaged or empty signature, an oversized manifest, a manifest that names a field twice: refused",
      refused(lambda: uv.verify_manifest(mb, b"not base64 !!"), "damaged") and refused(lambda: uv.verify_manifest(mb, b"")) and refused(lambda: uv.verify_manifest(mb + b" " * uv.MAX_MANIFEST, sb), "too large")
      and refused(lambda: uv.verify_manifest(b'{"key_id":"' + KID.encode() + b'","key_id":"x"}', sb), "twice"))
_, _, mb_u, sb_u = release("untrusted", "2.0.0", key=OTHER, kid="somebody-else")
check("untrusted key id: a release signed by a key this copy does not hold is refused (a manifest cannot bring its own key)", refused(lambda: uv.verify_manifest(mb_u, sb_u), "does not trust"))
check("... also when the caller hands over a table of keys that lacks it, and with an empty table (the state of the repository today)",
      refused(lambda: uv.verify_manifest(mb, sb, trusted={"another": SR.public_b64(OTHER)}), "does not trust") and refused(lambda: uv.verify_manifest(mb, sb, trusted={}), "no publisher key"))
_, _, mb_t, sb_t = release("testkey", "2.0.0", kid="TEST-abcd1234")
update_trust.TRUSTED_KEYS["TEST-abcd1234"] = SR.public_b64(KEY)
check("a key id that begins with TEST- is refused outside the tests, even if someone put it into the trust table", refused(lambda: uv.verify_manifest(mb_t, sb_t), "test key"))
os.environ["OPS_ALLOW_TEST_KEYS"] = "1"; ok_t = uv.verify_manifest(mb_t, sb_t)["key_id"] == "TEST-abcd1234"; os.environ.pop("OPS_ALLOW_TEST_KEYS"); update_trust.TRUSTED_KEYS.pop("TEST-abcd1234")
check("... and accepted only with the switch the tests set", ok_t)
# wrong hash / size
bad = TMP / "tampered.zip"; data = bytearray(Path(rz).read_bytes()); data[len(data) // 2] ^= 0xFF; bad.write_bytes(bytes(data))
check("wrong hash: a zip of the right size with one changed byte is refused", bad.stat().st_size == m["size"] and refused(lambda: uv.verify_release(str(bad), mb, sb, current_version="1.0.0"), "SHA-256"))
bad.write_bytes(Path(rz).read_bytes() + b"x")
check("wrong size: refused before the hash is even computed", refused(lambda: uv.verify_release(str(bad), mb, sb, current_version="1.0.0"), "wrong size"))
# version, system, Python
check("older or equal version: refused (going back is what Undo is for); the same version only when an install is being completed",
      refused(lambda: uv.verify_release(rz, mb, sb, current_version="2.0.1"), "not newer") and refused(lambda: uv.verify_release(rz, mb, sb, current_version="2.0.0"), "not newer")
      and uv.verify_release(rz, mb, sb, current_version="2.0.0", allow_same=True)["version"] == "2.0.0" and refused(lambda: uv.verify_release(rz, mb, sb, current_version="3.0", allow_same=True), "not newer"))
check("a version that cannot be read is refused when the manifest is made and when it is checked",
      raised(lambda: SR.make_manifest(rz, "two-point-oh", KID), uv.VerifyError) is not None and refused(lambda: uv.check_fields(dict(json.loads(mb), version="2.x")), "version"))
elsewhere = "macos" if PLAT != "macos" else "windows"
_, z_p, mb_p, sb_p = release("otherplatform", "2.0.0", platform=[elsewhere])
check("wrong platform: a release made for another system is refused; one made for 'any' is accepted",
      refused(lambda: uv.verify_release(z_p, mb_p, sb_p, current_version="1.0.0"), "not for this system") and uv.check_compat(dict(json.loads(mb), platform=["any"]), "1.0.0") is True
      and refused(lambda: uv.check_compat(json.loads(mb), "1.0.0", platform="windows" if PLAT != "windows" else "linux")))
_, z_y, mb_y, sb_y = release("newpython", "2.0.0", min_python="99.0")
check("unsupported Python: a release that needs a newer Python than this one is refused", refused(lambda: uv.verify_release(z_y, mb_y, sb_y, current_version="1.0.0"), "needs Python 99.0"))
# no 'cryptography': fail closed
gone = {k: sys.modules[k] for k in list(sys.modules) if k == "cryptography" or k.startswith("cryptography.")}
for k in gone: sys.modules[k] = None
e = raised(lambda: uv.verify_manifest(mb, sb), uv.VerifyError)
for k, v in gone.items(): sys.modules[k] = v
check("without the 'cryptography' package verification FAILS with a plain message (it is never skipped)", e is not None and "cryptography" in str(e) and "not installed" in str(e), str(e)[:120])
check("... and works again when the package is back", uv.verify_manifest(mb, sb)["version"] == "2.0.0")

# ================================================================ the structure of a zip
def crafted(name, entries, link=False):
    p = TMP / "crafted" / name; p.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(p, "w") as z:
        for n, content in entries:
            zi = zipfile.ZipInfo(n); zi.filename = n
            if link: zi.create_system = 3; zi.external_attr = (0o120777 << 16)
            z.writestr(zi, content)
    return str(p)
unsafe = {"a '..' path": [("Origin_Plot_Studio/../../evil.py", "x")], "an absolute path": [("/abs/evil.py", "x")], "a drive letter": [("C:/Windows/evil.py", "x")],
          "a UNC path": [("\\\\server\\share\\evil.py", "x")], "a backslash '..' path": [("app\\..\\..\\evil.py", "x")], "a reserved Windows name": [("app/CON.txt", "x")],
          "a reserved name as a folder": [("app/aux/x.py", "x")], "an alternate data stream": [("app/readme.txt:hidden", "x")], "a name ending in a space": [("app/x.py ", "x")],
          "a name ending in a dot": [("app/x.", "x")], "the same name in another case": [("app/Helper.py", "a"), ("app/helper.py", "b")], "the same name twice": [("app/a.py", "a"), ("app/a.py", "b")],
          "a file that is also a folder": [("app/a", "x"), ("app/a/b.py", "y")], "a control character": [("app/a\tb.py", "x")]}
import warnings; warnings.filterwarnings("ignore")
left = [k for k, ent in unsafe.items() if not refused(lambda: uv.check_archive(crafted(f"u{abs(hash(k))}.zip", ent)))]
check("archive structure: '..', absolute, drive, UNC, reserved Windows names, alternate data streams, trailing dot or space, case-insensitive and exact duplicates, file/folder clashes are refused", left == [], left)
check("... a symbolic link too", refused(lambda: uv.check_archive(crafted("link.zip", [("app/link", "/etc/passwd")], link=True)), "symbolic link"))
many = crafted("many.zip", [(f"app/f{i}.txt", "x") for i in range(30)])
check("... and limits: number of entries, unpacked bytes in total and per file", refused(lambda: uv.check_archive(many, max_entries=10), "too many") and refused(lambda: uv.check_archive(many, max_total=20), "more than")
      and refused(lambda: uv.check_archive(many, max_entry=0), "too large") and uv.check_archive(many) == {"entries": 30, "bytes": 30})
raw = Path(many).read_bytes(); i = raw.rfind(b"PK\x05\x06")
z64 = TMP / "crafted" / "z64.zip"; z64.write_bytes(raw[:i] + b"PK\x06\x07" + b"\0" * 16 + raw[i:])                                  # a 64-bit locator in front of the end record
huge = TMP / "crafted" / "huge.zip"; huge.write_bytes(raw[:i + 8] + (60000).to_bytes(2, "little") * 2 + raw[i + 12:])        # an end record that claims 60000 entries
check("... something that is not a zip, a 64-bit zip directory, or a directory that claims tens of thousands of entries is refused before the zip module reads it",
      refused(lambda: uv.check_archive(str(A / "smart_plots.py")), "not a zip") and refused(lambda: uv.check_archive(str(z64)), "64-bit") and refused(lambda: uv.check_archive(str(huge)), "too many"))
profile("owner"); outside = TMP / "evil.py"
e = raised(lambda: su.fetch_and_unpack({"zip": crafted("escape.zip", [("Origin_Plot_Studio/../../../evil.py", "x"), ("Origin_Plot_Studio/origin_plot_app.py", ""), ("Origin_Plot_Studio/smart_plots.py", 'VERSION = "2.0.0"')])}, str(TMP / "w_escape"), current="1.0.0"), su.UpdateError)
check("the updater refuses such a zip in every profile, and nothing is written outside the trial folder", e is not None and "unsafe path" in str(e) and not outside.exists() and not (TMP / "w_escape" / "unpacked").exists(), str(e)[:100])

# ================================================================ 'friends' build: signed or nothing
profile("friends"); reset()
app, store = installed("friends1")
before = snap(app)
plain_zip = zip_of(program(TMP / "src" / "plain2", "2.0.0", new_file=True), TMP / "Convincing_Official_Release_2.0.0.zip")
e = raised(lambda: su.fetch_and_unpack({"zip": plain_zip}, str(TMP / "w_f1"), current="1.0.0"), su.UpdateError)
check("friends: an unsigned zip ('install from a zip file') is refused with a plain message, whatever its name", e is not None and "not signed" in str(e) and "not installed" in str(e), str(e)[:140])
check("... nothing of it was unpacked, compiled or run", nothing_ran("2.0.0") and not (TMP / "w_f1" / "unpacked").exists())
info = su.find_update(str(Path(plain_zip).parent), "1.0.0")
check("... the same for a folder of zips as the place for updates", info is not None and raised(lambda: su.fetch_and_unpack(info, str(TMP / "w_f1b"), current="1.0.0"), su.UpdateError) is not None and nothing_ran("2.0.0"))
# an unverified folder can be neither checked (that would run it) nor installed
loose = program(TMP / "loose" / "app", "2.0.0", new_file=True)
e_check = raised(lambda: su.check(loose, app, quick=True), su.UpdateError); e_dry = raised(lambda: real_dry(loose, os.path.join(app, "examples_synthetic", "synthetic_sample.csv"), str(TMP / "w_dry")), su.UpdateError)
e_inst = raised(lambda: su.install(loose, app, store, "unverified"), su.UpdateError)
check("friends: the trial check (which RUNS the candidate) refuses an unverified folder before a single file is compiled or started", e_check is not None and e_dry is not None and "not verified" in str(e_check) and nothing_ran("2.0.0") and not any(Path(loose).rglob("*.pyc")), str(e_check)[:120])
check("friends: install() refuses it too, and the program is unchanged (enforced in the function, not by a hidden button)", e_inst is not None and snap(app) == before and su.backups(store) == [])
# AI repair is not available
tb = f'Traceback (most recent call last):\n  File "{os.path.join(app, "helper.py")}", line 1, in <module>\nValueError: synthetic\n'
e1 = raised(lambda: su.repair_message(tb, app), su.UpdateError); e2 = raised(lambda: su.make_trial(app, [{"file": "helper.py", "old": "helper of 1.0.0", "new": "fixed"}], str(TMP / "w_rep")), su.UpdateError)
check("friends: client-side AI repair is switched off in the functions themselves: no code is collected for the AI and no model-written copy is made",
      su.repair_available() is False and e1 is not None and e2 is not None and "not available in this build" in str(e1) and "not available in this build" in str(e2) and not (TMP / "w_rep").exists() and nothing_ran())
tk_src = (A / "origin_plot_app.py").read_text(encoding="utf-8")
check("... and the earlier window hides its menu entry and stops at the door", "repair_available(): mh.add_command(label=\"Repair the last problem with AI" in tk_src and "if not su.repair_available(): status.set(su.REPAIR_OFF); return" in tk_src)

# signed: a bundle (one file)
rd2, rz2, mb2, sb2 = release("friends_good", "2.0.0", new_file=True, trust_text="TRUSTED_KEYS = {'rotated-key': 'synthetic'}\n")
bundle = str(SR.write_bundle(rd2)); reset()
info = {"zip": bundle}; trial = su.fetch_and_unpack(info, str(TMP / "w_f2"), current="1.0.0")
check("friends: a signed bundle (one zip with manifest.json, manifest.sig and the program zip) is verified and unpacked - still nothing has run",
      su.verified(trial)["version"] == "2.0.0" and info["verified"] is True and "Verified" in info["verify_note"] and su.version_of(trial) == "2.0.0" and nothing_ran("2.0.0"))
c = su.check(trial, app, quick=True)
check("... only now the trial check runs the new version (and finds the same drawing commands)", c["ok"] and c["same"] == 1 and (MARK / "ran_2.0.0").exists() and len(DRY) == 2, c["lines"])
b, ch = su.install(trial, app, store, "update 1.0.0 to 2.0.0")
check("... and it is installed, with a backup; the journal is gone and no temporary file is left", su.version_of(app) == "2.0.0" and "added_by_update.py" in ch and os.path.isfile(os.path.join(b, "backup.json"))
      and not os.path.exists(os.path.join(store, su.JOURNAL)) and not any(Path(app).rglob("*" + su.STAGE_EXT)) and json.load(open(os.path.join(b, "backup.json")))["verified"] is True, ch)
check("a verified update may bring a new update_trust.py (that is how the publisher changes keys)", "rotated-key" in Path(app, "update_trust.py").read_text() and "update_trust.py" in ch)
t = su.undo(app, store)
check("rollback: Undo puts the earlier version back, removes what the update had added, and keeps the trust file in place", "1.0.0" in t and snap(app).keys() == before.keys() and su.version_of(app) == "1.0.0"
      and Path(app, "update_trust.py").read_text() == "TRUSTED_KEYS = {}\n" and {k: v for k, v in snap(app).items()} == before, t)
# signed: the two files beside the zip
reset(); side = TMP / "side"; side.mkdir(); z_side = str(side / "downloaded (1).zip"); shutil.copy(rz2, z_side); shutil.copy(rd2 / "manifest.json", z_side + ".manifest.json"); shutil.copy(rd2 / "manifest.sig", z_side + ".manifest.sig")
trial = su.fetch_and_unpack({"zip": z_side}, str(TMP / "w_f3"), current="1.0.0")
check("friends: a zip with <name>.zip.manifest.json and <name>.zip.manifest.sig beside it verifies too (the file name of the download does not matter, its SHA-256 does)", su.verified(trial) is not None and nothing_ran())
# signed, but wrong in one way each: all refused before anything runs
cases = {}
t1 = TMP / "c_tamper"; t1.mkdir(); z1 = str(t1 / "x.zip"); d1 = bytearray(Path(rz2).read_bytes()); d1[len(d1) // 2] ^= 0xFF; Path(z1).write_bytes(bytes(d1)); shutil.copy(rd2 / "manifest.json", z1 + ".manifest.json"); shutil.copy(rd2 / "manifest.sig", z1 + ".manifest.sig")
cases["wrong hash"] = ({"zip": z1}, "1.0.0", "sha-256")
t2 = TMP / "c_sig"; t2.mkdir(); z2 = str(t2 / "x.zip"); shutil.copy(rz2, z2); shutil.copy(rd2 / "manifest.json", z2 + ".manifest.json"); Path(z2 + ".manifest.sig").write_bytes(SR.sign_bytes(mb2, OTHER))
cases["invalid signature"] = ({"zip": z2}, "1.0.0", "not valid")
ru, zu, _, _ = release("friends_untrusted", "2.0.0", key=OTHER, kid="somebody-else"); cases["untrusted key"] = ({"zip": str(SR.write_bundle(ru))}, "1.0.0", "does not trust")
cases["older version"] = ({"zip": bundle}, "2.5.0", "not newer")
rp, _, _, _ = release("friends_platform", "2.0.0", platform=[elsewhere]); cases["wrong platform"] = ({"zip": str(SR.write_bundle(rp))}, "1.0.0", "not for this system")
rv, _, _, _ = release("friends_mismatch", "2.0.0", manifest_version="2.1.0"); cases["zip holds another version than the manifest states"] = ({"zip": str(SR.write_bundle(rv))}, "1.0.0", "signed manifest states 2.1.0")
bad = []
for why, (inf, cur, word) in cases.items():
    reset(); e = raised(lambda: su.fetch_and_unpack(dict(inf), str(TMP / ("w_c_" + str(abs(hash(why))))), current=cur), su.UpdateError)
    if e is None or word not in str(e).lower() and word not in str(e) or not nothing_ran("2.0.0"): bad.append((why, str(e)[:80]))
check("friends: wrong hash, invalid signature, untrusted key, older version, wrong platform, a zip that holds another version than signed - each refused, and in none of them did anything run", bad == [], bad)
reset(); gone = {k: sys.modules[k] for k in list(sys.modules) if k == "cryptography" or k.startswith("cryptography.")}
for k in gone: sys.modules[k] = None
e = raised(lambda: su.fetch_and_unpack({"zip": bundle}, str(TMP / "w_nocrypto"), current="1.0.0"), su.UpdateError)
for k, v in gone.items(): sys.modules[k] = v
check("friends: without 'cryptography' a signed update is NOT installed (no silent fall-back to 'unsigned')", e is not None and "cryptography" in str(e) and nothing_ran("2.0.0") and not (TMP / "w_nocrypto" / "unpacked").exists())
update_trust.TRUSTED_KEYS = {}; reset()
e = raised(lambda: su.fetch_and_unpack({"zip": bundle}, str(TMP / "w_nokeys"), current="1.0.0"), su.UpdateError)
update_trust.TRUSTED_KEYS = {KID: SR.public_b64(KEY)}
check("friends: with the empty trust table of today's repository no update is installed at all - the safe state until the production key is added", e is not None and "no publisher key" in str(e) and nothing_ran("2.0.0"))

# ---------------------------------------------------------------- GitHub as the place: only the signed release, never the branch
WORLD = {}; ASKED = []
class Resp:
    def __init__(self, b): self.b = b; self.status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, n=-1): return self.b if n is None or n < 0 else self.b[:n]
class Opener:
    def open(self, req, timeout=None):
        ASKED.append((req.full_url.split("?t=")[0], {k.lower(): v for k, v in req.header_items()}))
        a = WORLD.get(req.full_url.split("?t=")[0], ("http", 404))
        if a[0] == "ok": return Resp(a[1])
        hd = email.message.Message()
        if a[0] == "to": hd["Location"] = a[2]
        raise urllib.error.HTTPError(req.full_url, a[1], "x", hd, None)
real_opener = net._opener; net._opener = lambda: Opener()
REPO = "owner-x/repo-y"; GH = f"https://github.com/{REPO}/releases/latest/download/"; API = f"https://api.github.com/repos/{REPO}"
def public_world(mb_, sb_, zip_path):
    WORLD.clear(); del ASKED[:]
    art = json.loads(mb_)["artifact"]
    WORLD[GH + "manifest.json"] = ("to", 302, "https://release-storage.invalid/m"); WORLD["https://release-storage.invalid/m"] = ("ok", mb_)
    WORLD[GH + "manifest.sig"] = ("ok", sb_); WORLD[GH + art] = ("to", 302, "https://release-storage.invalid/z"); WORLD["https://release-storage.invalid/z"] = ("ok", Path(zip_path).read_bytes())
    WORLD[f"https://raw.githubusercontent.com/{REPO}/main/origin_plot_app/smart_plots.py"] = ("ok", b'VERSION = "7.7.7"\n')        # the unsigned branch, newer still
    WORLD[f"https://github.com/{REPO}/archive/refs/heads/main.zip"] = ("ok", Path(plain_zip).read_bytes())
su.TOKEN = ""; reset(); public_world(mb2, sb2, rz2)
os.remove(op._file()); profile("friends", connected=False)             # a 'friends' build as it is first started
e = raised(lambda: su.find_update("github:" + REPO, "1.0.0"), su.UpdateError)
check("friends: a fresh build is local-only - looking for an update asks nothing until the user allows connections", op.level() == "local_only" and e is not None and "Local-only" in str(e) and ASKED == [])
profile("friends")
info = su.find_update("github:" + REPO, "1.0.0")
check("friends, GitHub: the latest SIGNED release is asked for (manifest and signature first, verified at once); the unsigned branch is never looked at",
      info is not None and info["version"] == "2.0.0" and info["zip"] == GH + os.path.basename(rz2) and not any("raw.githubusercontent" in u or "archive/refs" in u for u, _ in ASKED) and nothing_ran(), [u for u, _ in ASKED])
trial = su.fetch_and_unpack(info, str(TMP / "w_gh1"), current="1.0.0")
check("... the zip is then downloaded, matched against the signed manifest, and unpacked - verified, nothing run yet", su.verified(trial)["version"] == "2.0.0" and info["verified"] is True and nothing_ran("2.0.0") and ASKED[-1][0] == "https://release-storage.invalid/z")
public_world(mb2, SR.sign_bytes(mb2, OTHER), rz2); reset()
e = raised(lambda: su.find_update("github:" + REPO, "1.0.0"), su.UpdateError)
check("friends, GitHub: a release whose signature is not valid is refused while looking - the zip is not even downloaded", e is not None and "NOT valid" in str(e) and not any(u.endswith(".zip") or u.endswith("/z") for u, _ in ASKED) and nothing_ran(), (str(e)[:60], [u for u, _ in ASKED]))
WORLD.clear(); del ASKED[:]; WORLD[f"https://raw.githubusercontent.com/{REPO}/main/origin_plot_app/smart_plots.py"] = ("ok", b'VERSION = "7.7.7"\n')
e = raised(lambda: su.find_update("github:" + REPO, "1.0.0"), su.UpdateError)
check("friends, GitHub: a repository without a signed release offers nothing (a plain message), even when its branch is newer", e is not None and "No signed version" in str(e) and all("releases/latest/download" in u for u, _ in ASKED), ([u for u, _ in ASKED], str(e)[:80]))
public_world(mb2, sb2, plain_zip); info = su.find_update("github:" + REPO, "1.0.0"); reset()
e = raised(lambda: su.fetch_and_unpack(info, str(TMP / "w_gh2"), current="1.0.0"), su.UpdateError)
check("friends, GitHub: a zip that is not the one the signed manifest describes (swapped on the way) is refused", e is not None and ("wrong size" in str(e) or "SHA-256" in str(e) or "larger" in str(e)) and nothing_ran("2.0.0"), str(e)[:100])
e = raised(lambda: su.fetch_and_unpack({"zip": f"https://github.com/{REPO}/archive/refs/heads/main.zip", "version": "7.7.7"}, str(TMP / "w_gh3"), current="1.0.0"), su.UpdateError)
check("friends: a bare link to an unsigned zip (the branch zip, any https zip) is refused after the download, unrun", e is not None and "not signed" in str(e) and nothing_ran("2.0.0"))
# a private repository: through the API with the token; the storage host never sees it
TOKEN = "ghp_" + "dummyTOKEN123" * 3; su.TOKEN = TOKEN; WORLD.clear(); del ASKED[:]; reset()
art = os.path.basename(rz2)
WORLD[API + "/releases/latest"] = ("ok", json.dumps({"tag_name": "v2.0.0", "assets": [{"name": n, "url": f"{API}/releases/assets/{i}", "browser_download_url": f"https://github.com/{REPO}/releases/download/v2.0.0/{n}"}
                                                                                 for i, n in enumerate(("manifest.json", "manifest.sig", art), 1)]}).encode())
for i, body in enumerate((mb2, sb2, Path(rz2).read_bytes()), 1):
    WORLD[f"{API}/releases/assets/{i}"] = ("to", 302, f"https://release-storage.invalid/a{i}"); WORLD[f"https://release-storage.invalid/a{i}"] = ("ok", body)
info = su.find_update("github:" + REPO, "1.0.0"); trial = su.fetch_and_unpack(info, str(TMP / "w_gh4"), current="1.0.0")
api_ok = all(h.get("authorization") == "Bearer " + TOKEN for u, h in ASKED if u.startswith("https://api.github.com/")); store_clean = all("authorization" not in h for u, h in ASKED if "release-storage" in u)
check("friends, private GitHub repository: the release files are read as API assets with the token; the storage host they redirect to never gets it; the update verifies",
      su.verified(trial) is not None and api_ok and store_clean and sum("release-storage" in u for u, _ in ASKED) == 3 and not any(u.startswith("https://github.com/") for u, _ in ASKED), [u for u, _ in ASKED])
su.TOKEN = ""

# ================================================================ 'owner' profile: the earlier flow keeps working, and says what it is
profile("owner"); reset(); app, store = installed("owner1"); before = snap(app)
info = {"zip": plain_zip}; trial = su.fetch_and_unpack(info, str(TMP / "w_o1"), current="1.0.0")
check("owner: an unsigned zip is unpacked as before, and the result says plainly that it is NOT verified", su.version_of(trial) == "2.0.0" and su.verified(trial) is None and info["verified"] is False and "NOT verified" in info["verify_note"] and "NOT verified" in su.verification_note(trial))
c = su.check(trial, app, quick=True)
check("owner: the trial check runs as before", c["ok"] and c["same"] == 1 and c["covered"] == 1 and (MARK / "ran_2.0.0").exists(), c["lines"])
Path(trial, "update_trust.py").write_text("TRUSTED_KEYS = {'planted': 'x'}\n"); Path(trial, "security_profile.json").write_text('{"profile": "owner"}'); Path(app, "security_profile.json").write_text('{"profile": "friends"}')
b, ch = su.install(trial, app, store, "update 1.0.0 to 2.0.0")
check("owner: it installs as before (backup, files changed, new file added)", su.version_of(app) == "2.0.0" and "added_by_update.py" in ch and "helper.py" in ch and su.backups(store) == [b] and json.load(open(os.path.join(b, "backup.json")))["verified"] is False, ch)
check("... but an update that is NOT verified cannot replace the trust table or the profile of the build", "planted" not in Path(app, "update_trust.py").read_text() and "friends" in Path(app, "security_profile.json").read_text() and "update_trust.py" not in ch and "security_profile.json" not in ch)
t = su.undo(app, store); os.remove(os.path.join(app, "security_profile.json"))
check("owner: Undo restores the earlier program exactly", snap(app) == before and "1.0.0" in t, t)
trial_d = program(TMP / "diff" / "app", "2.0.0", extra=" --different"); reset()
c = su.check(trial_d, app, quick=True)
check("owner: a version that draws differently is reported, not passed", c["ok"] is False and c["different"] == ["synthetic_sample.csv"])
info = {"zip": bundle}; trial = su.fetch_and_unpack(info, str(TMP / "w_o2"), current="1.0.0")
check("owner: when a signed manifest is present it is verified, and the note says so", info["verified"] is True and "Verified" in su.verification_note(trial))
e = raised(lambda: su.fetch_and_unpack({"zip": z2}, str(TMP / "w_o3"), current="1.0.0"), su.UpdateError)
check("owner: a manifest that is present but WRONG stops the update here too (no fall-back to 'unsigned')", e is not None and "NOT valid" in str(e), str(e)[:80])
# the unsigned GitHub branch flow of the owner
WORLD.clear(); del ASKED[:]; su.TOKEN = ""
WORLD[f"https://raw.githubusercontent.com/{REPO}/main/origin_plot_app/smart_plots.py"] = ("ok", b'VERSION = "2.0.0"\n'); WORLD[f"https://raw.githubusercontent.com/{REPO}/main/origin_plot_app/WHATS_NEW.txt"] = ("ok", b"# notes\nsynthetic line\n")
WORLD[f"https://github.com/{REPO}/archive/refs/heads/main.zip"] = ("to", 302, f"https://codeload.github.com/{REPO}/zip/refs/heads/main"); WORLD[f"https://codeload.github.com/{REPO}/zip/refs/heads/main"] = ("ok", Path(plain_zip).read_bytes())
info = su.find_update("github:" + REPO, "1.0.0")
check("owner, GitHub: the version is read from the main branch as before", info and info["version"] == "2.0.0" and info["zip"].endswith("/archive/refs/heads/main.zip") and info["notes"] == "synthetic line" and su.find_update("github:" + REPO, "2.0.0") is None, info)
trial = su.fetch_and_unpack(info, str(TMP / "w_o4"), current="1.0.0")
check("... and its zip is downloaded and unpacked as before, marked NOT verified", su.version_of(trial) == "2.0.0" and info["verified"] is False)
# AI repair stays for the owner, with the trust files out of its reach
msg, files = su.repair_message(f'Traceback (most recent call last):\n  File "{os.path.join(app, "helper.py")}", line 1, in <module>\nValueError: synthetic\n', app)
tr, touched = su.make_trial(app, [{"file": "helper.py", "old": "helper of 1.0.0", "new": "helper, repaired"}], str(TMP / "w_rep_o"))
e = raised(lambda: su.make_trial(app, [{"file": "update_trust.py", "old": "TRUSTED_KEYS = {}", "new": "TRUSTED_KEYS = {'x': 'y'}"}], str(TMP / "w_rep_o2")), su.UpdateError)
check("owner: AI repair works as before, and may not edit the files that decide trust", su.repair_available() and files == ["helper.py"] and touched == ["helper.py"] and "repaired" in Path(tr, "helper.py").read_text() and e is not None and "may change" in str(e))

# ================================================================ an install that is cut off
class Crash(BaseException): """Stands in for a power cut: no handler of the installer runs after it."""
def cut_rename_after(n, exc=Crash):
    seen = [0]
    def rep(a, b):
        seen[0] += 1
        if seen[0] > n: raise exc("stand-in: the rename did not happen")
        return os.replace(a, b)
    return rep
new_tree = program(TMP / "v2tree" / "app", "2.0.0", new_file=True)
def expect_new(app_): return all(snap(app_).get(r) == h for r, h in snap(new_tree).items() if r != "update_trust.py")

app, store = installed("cut1"); before = snap(app)
su._replace = cut_rename_after(2); e = raised(lambda: su.install(new_tree, app, store, "update 1.0.0 to 2.0.0"), Crash); su._replace = os.replace
j = json.load(open(os.path.join(store, su.JOURNAL)))
half = snap(app); temps = [p for p in Path(app).rglob("*" + su.STAGE_EXT)]
check("cut off while files were being put in place: the program is half old, half new, and the journal says exactly where it stopped", e is not None and j["state"] == "committing" and len(temps) == len(j["files"]) - 2 and half != before and not expect_new(app), (j["state"], len(temps)))
line = su.recover(app, store)
check("... the next start finishes it: every file is the new one (checked against the checksums written down before), no temporary file, no journal", line and "finished" in line and expect_new(app) and su.version_of(app) == "2.0.0"
      and not any(Path(app).rglob("*" + su.STAGE_EXT)) and not os.path.exists(os.path.join(store, su.JOURNAL)) and su.recover(app, store) is None, line)
t = su.undo(app, store)
check("... and Undo still brings the earlier version back afterwards", snap(app) == before, t)

app, store = installed("cut2"); before = snap(app)
su._replace = cut_rename_after(2); raised(lambda: su.install(new_tree, app, store, "update"), Crash); su._replace = os.replace
next(Path(app).rglob("*" + su.STAGE_EXT)).unlink()                   # one of the prepared files is lost: the install cannot be completed
line = su.recover(app, store)
check("cut off and one prepared file lost: it cannot be finished, so the earlier program is put back from the backup - nothing is half installed",
      line and "put back" in line and snap(app) == before and not os.path.exists(os.path.join(store, su.JOURNAL)) and su.backups(store) == [], line)

app, store = installed("cut3"); before = snap(app)
real_copy2 = shutil.copy2; staged = [0]
def copy_cut(s, d, **k):
    if str(d).endswith(su.STAGE_EXT):
        staged[0] += 1
        if staged[0] > 2: raise Crash("stand-in: stopped while preparing")
    return real_copy2(s, d, **k)
shutil.copy2 = copy_cut; e = raised(lambda: su.install(new_tree, app, store, "update"), Crash); shutil.copy2 = real_copy2
j = json.load(open(os.path.join(store, su.JOURNAL)))
check("cut off while the new files were still being prepared beside the old ones: no program file has changed yet",
      e is not None and j["state"] == "staging" and {k: v for k, v in snap(app).items() if not k.endswith(su.STAGE_EXT)} == before and len(list(Path(app).rglob("*" + su.STAGE_EXT))) == 2)
line = su.recover(app, store)
check("... the next start removes the prepared files; the program is as it was", line and "as it was" in line and snap(app) == before and not os.path.exists(os.path.join(store, su.JOURNAL)), line)

app, store = installed("cut4"); before = snap(app)
su._replace = cut_rename_after(2, PermissionError); e = raised(lambda: su.install(new_tree, app, store, "update"), su.UpdateError); su._replace = os.replace
check("a file that cannot be replaced (in use, no permission): the install stops and puts the earlier program back at once, with a plain message",
      e is not None and "put back" in str(e) and snap(app) == before and not os.path.exists(os.path.join(store, su.JOURNAL)) and su.backups(store) == [], str(e)[:120])
b, ch = su.install(new_tree, app, store, "update")
check("... and the same install works afterwards", expect_new(app) and len(ch) >= 4)

# a journal is data: it cannot point outside the program
app, store = installed("cut5"); before = snap(app); os.makedirs(store, exist_ok=True); victim = TMP / "apps" / "cut5" / "victim.txt"; victim.write_text("keep me")
bk = os.path.join(store, "2000-01-01_000000_vx"); os.makedirs(bk); json.dump({"version": "x", "files": []}, open(os.path.join(bk, "backup.json"), "w"))
json.dump({"schema": "opstudio.install/1", "state": "committing", "app_dir": app, "backup": bk, "files": ["../victim.txt"], "added": ["../victim.txt"], "sha256": {"../victim.txt": "0"}}, open(os.path.join(store, su.JOURNAL), "w"))
line = su.recover(app, store)
check("a journal that names a path outside the program folder is set aside; nothing outside is touched", line and victim.read_text() == "keep me" and snap(app) == before and not os.path.exists(os.path.join(store, su.JOURNAL)), line)
json.dump({"schema": "opstudio.install/1", "state": "committing", "app_dir": str(TMP / "some" / "other" / "copy"), "backup": bk, "files": ["helper.py"], "added": [], "sha256": {"helper.py": "0"}}, open(os.path.join(store, su.JOURNAL), "w"))
check("the journal of another copy of the app is left alone", su.recover(app, store) is None and os.path.exists(os.path.join(store, su.JOURNAL)) and snap(app) == before)
foreign = open(os.path.join(store, su.JOURNAL)).read(); b, ch = su.install(new_tree, app, store, "update")
check("... also by an install of this copy: the other copy's record is set aside unchanged, and this install goes through",
      expect_new(app) and open(os.path.join(store, su.JOURNAL + ".other1")).read() == foreign and not os.path.exists(os.path.join(store, su.JOURNAL)) and su.recover(app, store) is None)

# friends: a cut-off install of a verified update is finished; one that was not verified is never completed
profile("friends"); app, store = installed("cut6"); before = snap(app)
trial = su.fetch_and_unpack({"zip": bundle}, str(TMP / "w_cut6"), current="1.0.0")
su._replace = cut_rename_after(1); raised(lambda: su.install(trial, app, store, "update"), Crash); su._replace = os.replace
line = su.recover(app, store)
check("friends: a cut-off install of a VERIFIED update is finished at the next start", line and "finished" in line and su.version_of(app) == "2.0.0", line)
profile("owner"); app, store = installed("cut7"); before = snap(app)
su._replace = cut_rename_after(1); raised(lambda: su.install(new_tree, app, store, "update"), Crash); su._replace = os.replace
profile("friends"); line = su.recover(app, store)
check("friends: a cut-off install that was not verified is rolled back, never completed", line and "put back" in line and snap(app) == before, line)
profile("owner")

# ================================================================ the signing tool
out = io.StringIO(); kd = TMP / "keys"
with contextlib.redirect_stdout(out): rc = SR.main(["gen-test-key", str(kd)])
pem = (kd / "TEST_ONLY_private_key.pem").read_bytes(); pubinfo = json.loads((kd / "TEST_ONLY_public_key.json").read_text())
secret_body = pem.decode().splitlines()[1]
check("sign_release gen-test-key: a throw-away pair with a TEST- id and a loud warning; the private key is not printed", rc == 0 and pubinfo["key_id"].startswith("TEST-") and "NOT FOR RELEASES" in out.getvalue() and secret_body not in out.getvalue())
check("... and it refuses to write a key inside the repository", raised(lambda: SR.gen_test_key(ROOT / "tools" / "keys_never"), SystemExit) is not None and not (ROOT / "tools" / "keys_never").exists())
cli = TMP / "cli"; cli.mkdir(); zc = zip_of(program(TMP / "src" / "cli", "3.1.0"), cli / "Synthetic_Release_3.1.0.zip"); out = io.StringIO()
with contextlib.redirect_stdout(out):
    rc1 = SR.main(["make-manifest", zc, "--version", "3.1.0", "--key-id", pubinfo["key_id"], "--platform", PLAT])
    rc2 = SR.main(["sign", str(cli / "manifest.json"), "--private-key-file", str(kd / "TEST_ONLY_private_key.pem")])
    os.environ["OPS_ALLOW_TEST_KEYS"] = "1"; rc3 = SR.main(["verify", str(cli), "--public-key", pubinfo["public_key"]]); os.environ.pop("OPS_ALLOW_TEST_KEYS")
    rc4 = SR.main(["verify", str(cli), "--public-key", pubinfo["public_key"]])
    rc5 = SR.main(["bundle", str(cli)])
    rc6 = SR.main(["public-key", "--private-key-file", str(kd / "TEST_ONLY_private_key.pem"), "--key-id", "synthetic-id"])
text = out.getvalue()
check("sign_release make-manifest / sign / verify / bundle / public-key work from the command line; nothing private is printed",
      (rc1, rc2, rc3, rc5, rc6) == (0, 0, 0, 0, 0) and (cli / "manifest.sig").exists() and (cli / "Synthetic_Release_3.1.0_signed_bundle.zip").exists() and f'"synthetic-id": "{pubinfo["public_key"]}"' in text and secret_body not in text, text[-300:])
check("... verify says NOT ACCEPTED for a test key when the test switch is off", rc4 == 1 and "NOT ACCEPTED" in text)
os.environ["OPS_RELEASE_SIGNING_KEY"] = str(kd / "TEST_ONLY_private_key.pem"); k1 = SR.public_b64(SR.load_private_key()); os.environ["OPS_RELEASE_SIGNING_KEY"] = pem.decode(); k2 = SR.public_b64(SR.load_private_key()); os.environ.pop("OPS_RELEASE_SIGNING_KEY")
check("the signing key can come from the environment variable OPS_RELEASE_SIGNING_KEY (the key or the path of its file); without one the tool stops", k1 == k2 == pubinfo["public_key"] and raised(lambda: SR.load_private_key(), SystemExit) is not None)
(cli / "manifest.json").write_bytes((cli / "manifest.json").read_bytes().replace(b"3.1.0", b"3.1.1")); out = io.StringIO()
with contextlib.redirect_stdout(out): os.environ["OPS_ALLOW_TEST_KEYS"] = "1"; rc = SR.main(["verify", str(cli), "--public-key", pubinfo["public_key"]]); os.environ.pop("OPS_ALLOW_TEST_KEYS")
check("... and verify refuses a manifest edited after signing", rc == 1 and "NOT valid" in out.getvalue())
hits = [p.name for p in list((ROOT / "tools").glob("*.py")) + list(A.glob("update_*.py")) if "PRIVATE KEY-----\n" in p.read_text(encoding="utf-8", errors="replace")]
check("no private key is written in the tool or in the trust files of the repository", hits == [], hits)

subprocess.run = real_run; su._dry = real_dry; net._opener = real_opener
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

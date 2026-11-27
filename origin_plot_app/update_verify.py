"""update_verify.py - is this update really from the publisher? Checked BEFORE any file of it is imported or run.

A release is three files:

    <artifact>.zip    the program (built by tools/build_release.py)
    manifest.json     {"schema": "opstudio.release/1", "version", "artifact", "sha256", "size", "platform": [...],
                       "min_python", "created", "key_id"}   written as canonical JSON by tools/sign_release.py
    manifest.sig      base64 of the Ed25519 signature over the exact bytes of manifest.json

or ONE file, a "signed bundle": a zip that holds exactly those three at its top level (easier to pass on by hand).

What is checked, in this order, and every failure stops the update (nothing is unpacked, compiled or run):
  1. manifest.sig is a valid signature of manifest.json by a key in update_trust.TRUSTED_KEYS (the key id in the manifest
     only chooses WHICH trusted key is tried; a manifest cannot bring its own key);
  2. the fields of the manifest are well formed; the version is newer than the installed one; the platform list holds
     this system; this Python is not older than min_python;
  3. the zip has exactly the size and the SHA-256 the manifest states;
  4. the zip is structurally safe: a limited number of entries and of unpacked bytes, no absolute path, drive letter,
     UNC path, '..', no reserved Windows name, no alternate-data-stream name (':'), no symbolic link or special file,
     no two names that differ only in case.

A checksum beside an unsigned zip would only detect a damaged download; the signature is what says who published it.
Needs the 'cryptography' package for step 1. Without it verification FAILS (it is never skipped).
This module only reads bytes; it never imports, compiles or starts anything from an update. No signing code is here.
"""
import os, re, sys, json, base64, struct, hashlib, zipfile, unicodedata

SCHEMA = "opstudio.release/1"
MANIFEST_NAME, SIG_NAME = "manifest.json", "manifest.sig"
MAX_MANIFEST = 64 * 1024
MAX_SIG = 1024
MAX_ARTIFACT = 600 * 1024 * 1024            # the zip itself
MAX_ENTRIES = 20000
MAX_TOTAL = 1024 * 1024 * 1024              # all files unpacked
MAX_ENTRY = 300 * 1024 * 1024               # one file unpacked
MAX_DIRECTORY = 4 * 1024 * 1024             # the list of contents inside the zip
MAX_RATIO = 1000                            # unpacked : packed for one large entry (a 'zip bomb' is far above)
PLATFORMS = ("windows", "linux", "macos", "any")
_RESERVED = {"con", "prn", "aux", "nul", "conin$", "conout$"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
_FIELDS = ("schema", "version", "artifact", "sha256", "size", "platform", "min_python", "created", "key_id")


class VerifyError(Exception):
    """The update is not accepted. The text says why in plain words."""


# ---------------------------------------------------------------------------------------------- the manifest
def canonical(d):
    """The one way a manifest is written: sorted keys, no spaces, ASCII, one line feed at the end."""
    return (json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def vkey(v):
    """A version as numbers, or VerifyError when it is not 'N.N', 'N.N.N' or 'N.N.N.N'."""
    s = str(v).strip().lstrip("vV")
    if not re.fullmatch(r"\d{1,6}(\.\d{1,6}){1,3}", s): raise VerifyError(f"the version '{str(v)[:40]}' cannot be read")
    return tuple(int(x) for x in s.split("."))


def this_platform():
    return "windows" if sys.platform.startswith("win") else "macos" if sys.platform == "darwin" else "linux"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""): h.update(part)
    return h.hexdigest()


def _no_duplicates(pairs):
    d = {}
    for k, v in pairs:
        if k in d: raise VerifyError("the manifest names a field twice")
        d[k] = v
    return d


def _ed25519():
    """The verifying half of Ed25519 from the 'cryptography' package. No package, no verification, no update."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        return Ed25519PublicKey, InvalidSignature
    except Exception:
        raise VerifyError("The signature of the update cannot be checked: the Python package 'cryptography' is not installed (or does not load). "
                          "The update is not installed. Install the package (it is in requirements.txt), then try again.")


def trusted_keys():
    try:
        import update_trust
        t = update_trust.TRUSTED_KEYS
        return dict(t) if isinstance(t, dict) else {}
    except Exception:
        return {}


def check_fields(m):
    """The fields of a manifest are there and well formed (says nothing about who wrote it)."""
    if not isinstance(m, dict): raise VerifyError("the manifest is not a JSON object")
    miss = [k for k in _FIELDS if k not in m]
    if miss: raise VerifyError("the manifest lacks: " + ", ".join(miss))
    if m["schema"] != SCHEMA: raise VerifyError(f"the manifest is of a kind this version does not know ({str(m['schema'])[:40]})")
    vkey(m["version"])
    if not isinstance(m["artifact"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.zip", m["artifact"]) or unsafe_name(m["artifact"]): raise VerifyError("the manifest names a file that is not a plain zip name")
    if not isinstance(m["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", m["sha256"]): raise VerifyError("the manifest holds no valid SHA-256")
    if not isinstance(m["size"], int) or isinstance(m["size"], bool) or not (0 < m["size"] <= MAX_ARTIFACT): raise VerifyError("the manifest states an impossible size")
    if not isinstance(m["platform"], list) or not m["platform"] or not all(isinstance(p, str) and p in PLATFORMS for p in m["platform"]): raise VerifyError("the manifest holds no valid list of systems")
    if not isinstance(m["min_python"], str) or not re.fullmatch(r"\d{1,2}\.\d{1,3}(\.\d{1,3})?", m["min_python"]): raise VerifyError("the manifest holds no valid Python version")
    if not isinstance(m["created"], str) or not re.fullmatch(r"[0-9T:.Z+\- ]{8,40}", m["created"]): raise VerifyError("the manifest holds no valid date")
    if not isinstance(m["key_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", m["key_id"]): raise VerifyError("the manifest holds no valid key id")
    for k in ("notes", "tag"):
        if k in m and (not isinstance(m[k], str) or len(m[k]) > 4000): raise VerifyError(f"the manifest field '{k}' is not a short text")
    return m


def verify_manifest(manifest_bytes, sig_bytes, *, trusted=None):
    """The manifest as a dict when manifest_bytes carry a valid signature of a trusted key; VerifyError otherwise.
    trusted: {key id: base64 public key}; by default update_trust.TRUSTED_KEYS as it is at this moment."""
    if not isinstance(manifest_bytes, (bytes, bytearray)) or not isinstance(sig_bytes, (bytes, bytearray)): raise VerifyError("the manifest or its signature is missing")
    if not manifest_bytes or len(manifest_bytes) > MAX_MANIFEST: raise VerifyError("the manifest is empty or too large")
    if not sig_bytes or len(sig_bytes) > MAX_SIG: raise VerifyError("the signature is empty or too large")
    Ed25519PublicKey, InvalidSignature = _ed25519()                  # fail closed before anything is believed
    try: m = json.loads(bytes(manifest_bytes).decode("utf-8"), object_pairs_hook=_no_duplicates)
    except VerifyError: raise
    except Exception: raise VerifyError("the manifest cannot be read")
    kid = m.get("key_id") if isinstance(m, dict) else None
    if not isinstance(kid, str) or not kid: raise VerifyError("the manifest names no key")
    keys = trusted_keys() if trusted is None else dict(trusted)
    if not keys: raise VerifyError("This copy of the app holds no publisher key yet (update_trust.py), so no signature can be accepted. The update is not installed.")
    if kid not in keys: raise VerifyError(f"The update is signed with a key this app does not trust ('{kid[:40]}'). It is not installed.")
    if kid.upper().startswith("TEST-") and os.environ.get("OPS_ALLOW_TEST_KEYS") != "1": raise VerifyError("The update is signed with a test key. Test keys are not accepted outside the tests.")
    try:
        pub = base64.b64decode(str(keys[kid]).strip(), validate=True)
        if len(pub) != 32: raise ValueError("length")
        key = Ed25519PublicKey.from_public_bytes(pub)
    except Exception: raise VerifyError(f"the trusted key '{kid[:40]}' in update_trust.py is not a valid Ed25519 public key")
    try:
        sig = base64.b64decode(bytes(sig_bytes).strip(), validate=True)
        if len(sig) != 64: raise ValueError("length")
    except Exception: raise VerifyError("The signature of the update is damaged. It is not installed.")
    try: key.verify(sig, bytes(manifest_bytes))
    except InvalidSignature: raise VerifyError("The signature of the update is NOT valid: the manifest was changed, or it was not signed by the publisher. It is not installed.")
    except Exception: raise VerifyError("The signature of the update could not be checked. It is not installed.")
    return check_fields(m)


def check_compat(m, current_version, *, allow_same=False, platform=None, python=None):
    """Is this release for this computer, and newer than what is installed? (An older signed release is refused too:
    going back is what 'Undo the last update' is for.)"""
    new = vkey(m["version"])
    try: cur = vkey(current_version)
    except VerifyError: cur = tuple(int(x) for x in re.findall(r"\d+", str(current_version))[:4]) or (0,)
    if new < cur or (new == cur and not allow_same):
        raise VerifyError(f"Version {m['version']} is not newer than the installed version {current_version}. It is not installed.")
    plat = platform or this_platform()
    if "any" not in m["platform"] and plat not in m["platform"]: raise VerifyError(f"Version {m['version']} is made for {', '.join(m['platform'])}, not for this system ({plat}). It is not installed.")
    py = tuple(python or sys.version_info[:3]); need = tuple(int(x) for x in m["min_python"].split("."))
    if py[:len(need)] < need: raise VerifyError(f"Version {m['version']} needs Python {m['min_python']} or newer; this computer runs Python {'.'.join(map(str, py[:3]))}. It is not installed.")
    return True


def verify_artifact(path, m):
    """The zip is byte for byte the one the signed manifest describes."""
    try: size = os.path.getsize(path)
    except OSError: raise VerifyError("the update file is not there")
    if size != m["size"]: raise VerifyError(f"The update file has the wrong size ({size} bytes, the signed manifest states {m['size']}). It is not installed.")
    if sha256_file(path) != m["sha256"]: raise VerifyError("The update file does not match its signed manifest (wrong SHA-256): it was changed or damaged. It is not installed.")
    return True


# ---------------------------------------------------------------------------------------------- the archive
def unsafe_name(name):
    """Why a name inside a zip is not accepted, or '' when it is fine. Written for Windows as the target."""
    if not isinstance(name, str) or not name: return "an empty name"
    if any(ord(c) < 32 or ord(c) == 127 for c in name): return "a control character in a name"
    n = name.replace("\\", "/")
    if n.startswith("/"): return "an absolute or network (UNC) path"
    if re.match(r"^[A-Za-z]:", n): return "a drive letter"
    if len(n) > 240: return "a path that is too long"
    parts = n.split("/")
    if parts and parts[-1] == "": parts = parts[:-1]                 # a folder entry ends with '/'
    if not parts: return "an empty name"
    for part in parts:
        if part == "": return "an empty folder name"
        if part in (".", ".."): return "a '..' or '.' step"
        if ":" in part: return "a ':' in a name (a drive or an alternate data stream)"
        if any(c in part for c in '<>"|?*'): return "a character Windows does not allow in a name"
        if part != part.rstrip(". "): return "a name that ends with a dot or a space"
        if part.split(".")[0].strip().lower() in _RESERVED: return "a reserved Windows device name"
    return ""


def _directory_ok(path):
    """Look at the end of the zip before the zip module reads its list of contents: a huge or 64-bit list is refused
    (an update is far below those sizes), so a crafted file cannot make the app read gigabytes of names."""
    try:
        size = os.path.getsize(path)
        if size > MAX_ARTIFACT: raise VerifyError("the update file is larger than the app accepts")
        with open(path, "rb") as f:
            n = min(size, 65536 + 22 + 20); f.seek(size - n); tail = f.read(n)
    except VerifyError: raise
    except OSError: raise VerifyError("the update file cannot be read")
    i = tail.rfind(b"PK\x05\x06")
    if i < 0 or len(tail) - i < 22: raise VerifyError("the update file is not a zip")
    _sig, _disk, _cd_disk, here, total, cd_size, cd_off, _clen = struct.unpack("<4s4H2LH", tail[i:i + 22])
    if b"PK\x06\x07" in tail[max(0, i - 20):i] or total == 0xFFFF or here == 0xFFFF or cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF:
        raise VerifyError("the update file uses the 64-bit zip format, which an update never needs; it is not unpacked")
    if total > MAX_ENTRIES: raise VerifyError(f"the zip holds too many files ({total}; at most {MAX_ENTRIES})")
    if cd_size > MAX_DIRECTORY: raise VerifyError("the list of contents of the zip is too large")
    return True


def check_archive(path, *, max_entries=None, max_total=None, max_entry=None):
    """The structure of a zip, checked without unpacking anything. Returns {"entries", "bytes"}; VerifyError when unsafe."""
    max_entries = MAX_ENTRIES if max_entries is None else max_entries; max_total = MAX_TOTAL if max_total is None else max_total; max_entry = MAX_ENTRY if max_entry is None else max_entry
    _directory_ok(path)
    try: zf = zipfile.ZipFile(path)
    except Exception: raise VerifyError("the update file is not a zip that can be read")
    with zf:
        infos = zf.infolist()
        if len(infos) > max_entries: raise VerifyError(f"the zip holds too many files ({len(infos)}; at most {max_entries})")
        seen = {}; files = set(); total = 0
        for m in infos:
            why = unsafe_name(m.filename)
            if why: raise VerifyError(f"the zip holds a file with an unsafe path ({why}); it is not unpacked")
            if m.flag_bits & 0x1: raise VerifyError("the zip holds an encrypted file; it is not unpacked")
            kind = (m.external_attr >> 16) & 0o170000
            if kind not in (0, 0o100000, 0o040000): raise VerifyError("the zip holds a symbolic link or a special file; it is not unpacked")
            is_dir = m.filename.replace("\\", "/").endswith("/")
            if is_dir and m.file_size: raise VerifyError("the zip holds a folder entry with content; it is not unpacked")
            key = unicodedata.normalize("NFC", m.filename.replace("\\", "/").rstrip("/")).casefold()
            if key in seen: raise VerifyError("the zip holds two names that differ only in upper and lower case (or the same name twice); it is not unpacked")
            seen[key] = is_dir
            if not is_dir: files.add(key)
            if m.file_size > max_entry: raise VerifyError("the zip holds a file that is too large; it is not unpacked")
            if m.file_size > 10 * 1024 * 1024 and m.file_size > MAX_RATIO * max(1, m.compress_size): raise VerifyError("the zip holds a file that unpacks to far more than it should; it is not unpacked")
            total += m.file_size
            if total > max_total: raise VerifyError("the zip unpacks to more than the app accepts; it is not unpacked")
        for key in seen:                                             # a file cannot also be the folder of another entry
            parts = key.split("/")
            for j in range(1, len(parts)):
                if "/".join(parts[:j]) in files: raise VerifyError("the zip uses one name as a file and as a folder; it is not unpacked")
        return {"entries": len(infos), "bytes": total}


def safe_extract(path, dest, *, checked=False):
    """Unpack a zip into dest after check_archive. No file may land outside dest (the containment check the updater
    always had, kept), and no more bytes are written than the zip declares. Returns dest."""
    if not checked: check_archive(path)
    root = os.path.abspath(dest); os.makedirs(root, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        for m in zf.infolist():
            name = m.filename.replace("\\", "/")
            t = os.path.abspath(os.path.join(root, *[p for p in name.split("/") if p]))
            if not (t == root or t.startswith(root + os.sep)): raise VerifyError("the zip holds a file with an unsafe path; it is not installed")
            if name.endswith("/"): os.makedirs(t, exist_ok=True); continue
            os.makedirs(os.path.dirname(t), exist_ok=True)
            left = m.file_size
            with zf.open(m) as src, open(t, "wb") as out:
                while True:
                    part = src.read(1024 * 1024)
                    if not part: break
                    left -= len(part)
                    if left < 0: raise VerifyError("the zip holds more data than it declares; it is not installed")
                    out.write(part)
    return root


# ---------------------------------------------------------------------------------------------- a signed bundle (one file)
def bundle_parts(path):
    """(manifest bytes, signature bytes) when the zip is a signed bundle - manifest.json and manifest.sig at its top
    level - else None. Only these two small members are read; nothing is unpacked."""
    try:
        _directory_ok(path)
        with zipfile.ZipFile(path) as zf:
            names = {m.filename: m for m in zf.infolist()}
            if MANIFEST_NAME not in names or SIG_NAME not in names: return None
            if names[MANIFEST_NAME].file_size > MAX_MANIFEST or names[SIG_NAME].file_size > MAX_SIG: raise VerifyError("the manifest or the signature in the bundle is too large")
            return zf.read(MANIFEST_NAME), zf.read(SIG_NAME)
    except VerifyError: raise
    except Exception: return None


def extract_bundle_artifact(path, m, dest_file):
    """Copy the artifact the VERIFIED manifest names out of a bundle (never more bytes than the manifest states)."""
    with zipfile.ZipFile(path) as zf:
        try: info = zf.getinfo(m["artifact"])
        except KeyError: raise VerifyError(f"the bundle does not hold the file its manifest names ({m['artifact']})")
        if info.file_size != m["size"]: raise VerifyError("the file in the bundle has not the size its signed manifest states; it is not installed")
        with zf.open(info) as src, open(dest_file, "wb") as out:
            left = m["size"]
            while True:
                part = src.read(1024 * 1024)
                if not part: break
                left -= len(part)
                if left < 0: raise VerifyError("the file in the bundle is larger than its signed manifest states; it is not installed")
                out.write(part)
    return dest_file


def verify_release(zip_path, manifest_bytes, sig_bytes, *, current_version, allow_same=False, trusted=None, platform=None, python=None):
    """All checks for one release, in the order of the module text. Returns the manifest; VerifyError on the first failure."""
    m = verify_manifest(manifest_bytes, sig_bytes, trusted=trusted)
    check_compat(m, current_version, allow_same=allow_same, platform=platform, python=python)
    verify_artifact(zip_path, m)
    check_archive(zip_path)
    return m

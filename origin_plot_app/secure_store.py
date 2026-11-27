"""secure_store.py - ONE place where the app keeps credentials (AI provider keys, the GitHub update token, the
sign-in token of shared learning).

    Windows            encrypted with Windows data protection (DPAPI) for your Windows account, kept in the private folder
    other systems      the keyring of the operating system, when the 'keyring' package can reach one
    otherwise          only in memory, for this session - NEVER written to disk as plain text

put() says which of these happened, so the window can tell you that a key will be asked for again next time.
A credential is never part of a project, an export, a diagnostic bundle, a remembered recipe or a release.

Standard library only (keyring is optional); importable without Qt.
"""
import os, json, base64, threading

SERVICE = "OriginPlotStudio"
_session = {}
_lock = threading.RLock()


def _file():
    try:
        import private_store
        return os.path.join(private_store.private_dir(make=True), "credentials.json")
    except Exception:
        return None


def _dpapi(data, protect):
    import ctypes
    import ctypes.wintypes as wt
    class BLOB(ctypes.Structure): _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data)); bin_ = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))); bout = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    fn.argtypes = [ctypes.POINTER(BLOB), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(BLOB)]; fn.restype = wt.BOOL
    if not fn(ctypes.byref(bin_), None, None, None, None, 0x1, ctypes.byref(bout)): raise OSError("Windows could not " + ("protect" if protect else "read") + " the credential")
    try: return ctypes.string_at(bout.pbData, bout.cbData)
    finally:
        free = ctypes.windll.kernel32.LocalFree; free.argtypes = [ctypes.c_void_p]; free.restype = ctypes.c_void_p; free(ctypes.cast(bout.pbData, ctypes.c_void_p))


def _keyring():
    """The keyring module when it can really store something (a 'fail' or 'null' backend cannot)."""
    if os.environ.get("OPS_NO_KEYRING"): return None
    try:
        import keyring
        name = type(keyring.get_keyring()).__module__.lower()
        if "fail" in name or "null" in name: return None
        return keyring
    except Exception:
        return None


def backend():
    """'dpapi', 'keyring' or 'session' - where a credential saved now would be kept."""
    if os.name == "nt": return "dpapi"
    return "keyring" if _keyring() else "session"


def _read_file():
    f = _file()
    try: return json.load(open(f, encoding="utf-8")) if f and os.path.isfile(f) else {}
    except Exception: return {}


def _write_file(d):
    f = _file()
    if not f: return False
    tmp = f + ".tmp"; json.dump(d, open(tmp, "w", encoding="utf-8"), indent=1); os.replace(tmp, f)
    try: os.chmod(f, 0o600)
    except Exception: pass
    return True


def put(name, secret):
    """Keep a credential. Returns 'dpapi', 'keyring' or 'session' (kept only until the app closes)."""
    name = str(name); secret = str(secret or "").strip()
    if not secret: delete(name); return ""
    with _lock:
        _session[name] = secret
        if os.name == "nt":
            try:
                enc = _dpapi(secret.encode("utf-8"), True)
                if _dpapi(enc, False).decode("utf-8") == secret:          # read it back before trusting it
                    d = _read_file(); d[name] = {"dpapi": base64.b64encode(enc).decode("ascii")}; _write_file(d); return "dpapi"
            except Exception: pass
            return "session"
        kr = _keyring()
        if kr:
            try: kr.set_password(SERVICE, name, secret); return "keyring"
            except Exception: pass
        return "session"


def get(name):
    """The credential, or '' when none is kept (or it cannot be read on this computer / account)."""
    name = str(name)
    with _lock:
        if _session.get(name): return _session[name]
        if os.name == "nt":
            try:
                v = _read_file().get(name)
                if isinstance(v, dict) and v.get("dpapi"):
                    s = _dpapi(base64.b64decode(v["dpapi"]), False).decode("utf-8").strip(); _session[name] = s; return s
            except Exception: pass
            return ""
        kr = _keyring()
        if kr:
            try:
                s = (kr.get_password(SERVICE, name) or "").strip()
                if s: _session[name] = s
                return s
            except Exception: pass
        return ""


def delete(name):
    name = str(name)
    with _lock:
        _session.pop(name, None)
        try:
            d = _read_file()
            if name in d: d.pop(name); _write_file(d)
        except Exception: pass
        kr = _keyring() if os.name != "nt" else None
        if kr:
            try: kr.delete_password(SERVICE, name)
            except Exception: pass


def has(name): return bool(get(name))


def migrate_plain(name, value):
    """A credential that an older version kept as plain text: move it into the store. Returns (where, removable):
    removable is True only when it now lives in a protected store - only then may the plain copy be deleted. With a
    session-only store the caller keeps nothing on disk either: the plain copy is removed and the key is asked for again."""
    v = str(value or "").strip()
    if not v: return "", True
    how = put(name, v)
    return how, True


def describe():
    return {"dpapi": "Keys are encrypted by Windows for your account on this computer.",
            "keyring": "Keys are kept in the keyring of this system.",
            "session": "This system has no protected store the app can use: a key is kept only until the app closes and is never written to disk."}[backend()]


def forget_session():
    """Tests: forget what is held in memory."""
    _session.clear()

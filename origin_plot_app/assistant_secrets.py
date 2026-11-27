"""Where the API key of the sentence assistant lives: the environment variable ANTHROPIC_API_KEY, or the app's ONE protected
store (secure_store.py: Windows data protection, the keyring of other systems, or - when neither exists - only the memory of
this session). Never plain text on disk, never learned_formats.json, provenance files, logs, outputs or the repository.

A key that an earlier version kept in %APPDATA%\\OriginPlotApp\\secrets.dat (encrypted by Windows) or in the keyring entry
'OriginPlotApp' is read once, moved into the store, and the old copy is removed."""
import os, json, re

ENV = "ANTHROPIC_API_KEY"
NAME = "ai:anthropic.sentence"           # an entry of its own: clearing it does not remove the key of the main assistant
SERVICE = "https://api.anthropic.com"    # the service a key kept here is for

def data_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "OriginPlotApp")

def secrets_path(): return os.path.join(data_dir(), "secrets.dat")

def redact(text):
    """Any key-looking text becomes sk-...****, and every other credential the app knows (tokens, Authorization values,
    keys of the other providers) is removed; use before anything is printed or logged."""
    t = re.sub(r"(sk-[A-Za-z0-9_\-]{0,12})[A-Za-z0-9_\-]{8,}", "sk-...****", str(text))
    try:
        import outbound_policy
        return outbound_policy.redact(t)
    except Exception: return t

def mask(key):
    key = str(key or "")
    return "sk-...****" if key else ""

def dpapi_available():
    if os.name != "nt": return False
    try:
        import assistant; return assistant.reveal_key(assistant.protect_key("x")) == "x"
    except Exception: return False

def keyring_available():
    try:
        import secure_store
        if os.name != "nt": return secure_store.backend() == "keyring"
        import keyring; return True
    except Exception: return False

def _bind(key):
    try:
        import assistant; assistant.bind_key(key, SERVICE)
    except Exception: pass

def _drop_legacy():
    try: os.remove(secrets_path())
    except OSError: pass
    try: import keyring; keyring.delete_password("OriginPlotApp", "anthropic")
    except Exception: pass

def save(key):
    """Store the key. Returns 'dpapi', 'keyring' or '' (nothing stored on disk: it then lives only in memory, until the app closes)."""
    key = str(key or "").strip()
    if not key: return ""
    import secure_store
    how = secure_store.put(NAME, key); _bind(key); _drop_legacy()
    return how if how in ("dpapi", "keyring") else ""

def _legacy():
    """A key an earlier version stored: moved into the protected store, the old copy removed."""
    k = ""
    try:
        if os.path.isfile(secrets_path()):
            import assistant
            with open(secrets_path(), encoding="utf-8") as f: k = assistant.reveal_key(json.load(f).get("anthropic"))
    except Exception: k = ""
    if not k:
        try: import keyring; k = (keyring.get_password("OriginPlotApp", "anthropic") or "").strip()
        except Exception: k = ""
    if k:
        try:
            import secure_store
            secure_store.migrate_plain(NAME, k); _bind(k); _drop_legacy()
        except Exception: pass
    return k

def load():
    """The key, from the environment first, then the protected store. '' when there is none."""
    k = os.environ.get(ENV, "").strip()
    if k: return k
    try:
        import secure_store
        k = secure_store.get(NAME)
    except Exception: k = ""
    return k or _legacy()

def clear():
    try:
        import secure_store
        k = secure_store.get(NAME)
        if k:
            try: import assistant; assistant.unbind_key(k)
            except Exception: pass
        secure_store.delete(NAME)
    except Exception: pass
    _drop_legacy()

def status(key=None):
    """'not set', 'set' or 'invalid' (set but not shaped like an Anthropic key). No network."""
    k = load() if key is None else str(key).strip()
    if not k: return "not set"
    return "set" if re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", k) else "invalid"

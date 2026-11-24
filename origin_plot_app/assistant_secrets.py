"""Where the API key lives: the environment variable ANTHROPIC_API_KEY, or %APPDATA%\\OriginPlotApp\\secrets.dat encrypted with Windows
data protection (DPAPI), or the operating system keyring. Never learned_formats.json, provenance files, logs, outputs or the repository."""
import os, json, re

ENV = "ANTHROPIC_API_KEY"

def data_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "OriginPlotApp")

def secrets_path(): return os.path.join(data_dir(), "secrets.dat")

def redact(text):
    """Any key-looking text becomes sk-...****; use before anything is printed or logged."""
    return re.sub(r"(sk-[A-Za-z0-9_\-]{0,12})[A-Za-z0-9_\-]{8,}", "sk-...****", str(text))

def mask(key):
    key = str(key or "")
    return "sk-...****" if key else ""

def dpapi_available():
    if os.name != "nt": return False
    try:
        import assistant; return assistant.reveal_key(assistant.protect_key("x")) == "x"
    except Exception: return False

def keyring_available():
    try: import keyring; return True
    except Exception: return False

def save(key):
    """Store the key. Returns 'dpapi', 'keyring' or '' (nothing stored: it then lives only in memory)."""
    key = str(key or "").strip()
    if not key: return ""
    if dpapi_available():
        import assistant; v = assistant.protect_key(key)
        if v and "dpapi" in v:
            os.makedirs(data_dir(), exist_ok=True)
            with open(secrets_path(), "w", encoding="utf-8") as f: json.dump({"anthropic": v}, f)
            return "dpapi"
    if keyring_available():
        try: import keyring; keyring.set_password("OriginPlotApp", "anthropic", key); return "keyring"
        except Exception: pass
    return ""

def load():
    """The key, from the environment first, then the stored copy. '' when there is none."""
    k = os.environ.get(ENV, "").strip()
    if k: return k
    try:
        if os.path.isfile(secrets_path()):
            import assistant
            with open(secrets_path(), encoding="utf-8") as f: return assistant.reveal_key(json.load(f).get("anthropic"))
    except Exception: pass
    try: import keyring; return (keyring.get_password("OriginPlotApp", "anthropic") or "").strip()
    except Exception: return ""

def clear():
    try: os.remove(secrets_path())
    except OSError: pass
    try: import keyring; keyring.delete_password("OriginPlotApp", "anthropic")
    except Exception: pass

def status(key=None):
    """'not set', 'set' or 'invalid' (set but not shaped like an Anthropic key). No network."""
    k = load() if key is None else str(key).strip()
    if not k: return "not set"
    return "set" if re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", k) else "invalid"

"""outbound_policy.py - ONE policy for everything the app sends out of this computer.

Every network path of the app (update check and download, the AI assistant and its automatic continuations, the free web
search, diagnostics, shared learning) asks this module BEFORE it opens a connection. The check is made where the request
is sent, not where a button is shown: a hidden control does not stop a request, this does.

Levels (what may leave the computer):

    local_only   nothing the app starts itself: no update check, no AI, no web search, no diagnostics, no sync
    minimal      your prompt and generic type / role information (aliases instead of names and paths)
    metadata     + labels, structure and context you approved (still no measurements)
    scientific   + measurements, results, images and documents you explicitly selected

The level and the per-channel switches are USER data (the private folder), never part of a project or a template: an
imported project cannot change them. The profile ('friends' / 'owner') is part of the installed program.

Standard library only; importable without Qt.
"""
import os, re, json, threading, ipaddress, urllib.parse

LEVELS = ("local_only", "minimal", "metadata", "scientific")
CHANNELS = ("update_check", "update_download", "ai", "web_search", "diagnostics", "learning_sync")
# what each level lets an AI request carry (kinds of content)
PERMITS = {
    "local_only": frozenset(),
    "minimal": frozenset({"prompt", "generic"}),
    "metadata": frozenset({"prompt", "generic", "labels", "structure"}),
    "scientific": frozenset({"prompt", "generic", "labels", "structure", "paths", "measurements", "results", "images", "documents"}),
}
KINDS = ("prompt", "generic", "labels", "structure", "paths", "measurements", "results", "images", "documents")
HERE = os.path.dirname(os.path.abspath(__file__))
_lock = threading.RLock()
_state = {"loaded": False, "data": {}, "generation": 0, "listeners": [], "audit": []}


class Blocked(PermissionError):
    """The policy does not allow this request. The text says why in plain words."""


# ------------------------------------------------------------------------------------------------ profile and settings
def profile():
    """'friends' (a build given to other people: connected features start off, unsigned updates and client-side AI
    repair are unavailable) or 'owner' (the developer's own copy). Part of the installed program: the file
    security_profile.json beside it, written by the release build. OPS_PROFILE overrides it (tests)."""
    env = (os.environ.get("OPS_PROFILE") or "").strip().lower()
    if env in ("friends", "owner"): return env
    try:
        p = json.load(open(os.path.join(HERE, "security_profile.json"), encoding="utf-8")).get("profile", "")
        if str(p).lower() in ("friends", "owner"): return str(p).lower()
    except Exception: pass
    return "owner"


def _file():
    try:
        import private_store
        return os.path.join(private_store.private_dir(make=True), "outbound_policy.json")
    except Exception:
        return None


def _defaults():
    friends = profile() == "friends"
    return {"level": "local_only" if friends else "minimal", "channels": {c: True for c in CHANNELS} | {"diagnostics": False, "learning_sync": False},
            "ai_destination": "", "loopback_http_ports": [11434]}


def _load(force=False):
    with _lock:
        if _state["loaded"] and not force: return _state["data"]
        d = _defaults(); f = _file()
        try:
            if f and os.path.isfile(f):
                got = json.load(open(f, encoding="utf-8"))
                if isinstance(got, dict):
                    if got.get("level") in LEVELS: d["level"] = got["level"]
                    if isinstance(got.get("channels"), dict): d["channels"].update({k: bool(v) for k, v in got["channels"].items() if k in CHANNELS})
                    if isinstance(got.get("ai_destination"), str): d["ai_destination"] = got["ai_destination"][:300]
                    if isinstance(got.get("loopback_http_ports"), list): d["loopback_http_ports"] = [int(p) for p in got["loopback_http_ports"] if str(p).isdigit() and 0 < int(p) < 65536][:8]
        except Exception: pass
        if (os.environ.get("OPS_LOCAL_ONLY") or "").strip() in ("1", "true", "yes"): d["level"] = "local_only"
        _state["data"] = d; _state["loaded"] = True
        return d


def _save():
    f = _file()
    if not f: return False
    try:
        tmp = f + ".tmp"; json.dump(_state["data"], open(tmp, "w", encoding="utf-8"), indent=1); os.replace(tmp, f); return True
    except Exception: return False


def reload():
    """Read the settings again (tests, or after the private folder changed)."""
    _load(force=True)


def level(): return _load()["level"]
def local_only(): return level() == "local_only"
def generation(): return _state["generation"]


def on_change(callback):
    """callback(what) is called when the level, a channel or the AI destination changes: queued conversation history and
    collected context must be cleared or filtered again then."""
    _state["listeners"].append(callback)


def _changed(what):
    _state["generation"] += 1
    for cb in list(_state["listeners"]):
        try: cb(what)
        except Exception: pass


def set_level(new):
    if new not in LEVELS: raise ValueError(f"unknown level {new!r}")
    with _lock:
        d = _load()
        if d["level"] == new: return False
        d["level"] = new; _save()
    _changed("level"); return True


def set_channel(channel, on):
    if channel not in CHANNELS: raise ValueError(f"unknown channel {channel!r}")
    with _lock:
        d = _load()
        if d["channels"].get(channel) == bool(on): return False
        d["channels"][channel] = bool(on); _save()
    _changed("channel:" + channel); return True


def channel_on(channel): return bool(_load()["channels"].get(channel))


def set_ai_destination(origin_text):
    """Remember which service the AI requests go to. A change means: earlier context was collected for another service."""
    with _lock:
        d = _load(); new = str(origin_text or "")[:300]
        if d.get("ai_destination") == new: return False
        d["ai_destination"] = new; _save()
    _changed("ai_destination"); return True


def ai_destination():
    """The service the AI requests were last set to go to ('' = none yet)."""
    return str(_load().get("ai_destination") or "")


def loopback_ports():
    """The ports on THIS computer a local model may be reached on with plain http."""
    return list(_load()["loopback_http_ports"])


def approve_loopback_port(port, on=True):
    """Allow (or stop allowing) plain http to a model on this computer on one more port. Only loopback addresses are
    ever reached this way; another computer always needs https."""
    port = int(port)
    if not 0 < port < 65536: raise ValueError("not a port")
    with _lock:
        d = _load(); ports = [p for p in d["loopback_http_ports"] if p != port] + ([port] if on else [])
        if sorted(ports) == sorted(d["loopback_http_ports"]): return False
        d["loopback_http_ports"] = ports[-8:]; _save()
    _changed("loopback_ports"); return True


def permits(kind):
    """May this kind of content (see KINDS) be put into a request to the AI service at the present level?"""
    return kind in PERMITS[level()]


def allowed(channel):
    return (not local_only()) and channel in CHANNELS and channel_on(channel)


WHY = {"update_check": "looking for a new version", "update_download": "downloading an update", "ai": "the AI assistant", "web_search": "the web search",
       "diagnostics": "sending diagnostics", "learning_sync": "shared learning"}


def require(channel, url=None, *, loopback_http=False):
    """Call this right before a request is sent. Raises Blocked when the level or the channel switch forbids it, or when
    the address is not acceptable (see check_url). Returns the parsed address (or None)."""
    if channel not in CHANNELS: raise Blocked(f"unknown outbound channel {channel!r}: nothing is sent")
    if local_only(): raise Blocked(f"Local-only mode is on: {WHY[channel]} needs a connection and was not started. Settings > Privacy turns it on.")
    if not channel_on(channel): raise Blocked(f"{WHY[channel].capitalize()} is switched off in Settings > Privacy.")
    p = check_url(url, loopback_http=loopback_http) if url is not None else None
    with _lock:
        _state["audit"].append({"channel": channel, "host": (p.hostname if p else "") or ""}); del _state["audit"][:-200]
    return p


def audit():
    """The last requests the policy let through: channel and host only (never content)."""
    return list(_state["audit"])


# ------------------------------------------------------------------------------------------------ addresses
def is_loopback(host):
    """True only for the loopback names of THIS computer: 'localhost' exactly, 127.0.0.0/8, ::1. A name that merely
    contains 'localhost' (localhost.example.net) is not loopback."""
    h = str(host or "").strip().strip("[]").lower().rstrip(".")
    if h == "localhost": return True
    try: return ipaddress.ip_address(h).is_loopback
    except ValueError: return False


def check_url(url, *, loopback_http=False):
    """The parsed address when it is acceptable, else Blocked:
    https everywhere; plain http only for an explicitly allowed loopback service on an approved port; never a user name
    or password inside the address; a real host name."""
    try: p = urllib.parse.urlsplit(str(url).strip())
    except Exception: raise Blocked("the address cannot be read")
    scheme = (p.scheme or "").lower()
    try: port = p.port
    except ValueError: raise Blocked("the address has an invalid port")
    if p.username is not None or p.password is not None or "@" in (p.netloc or ""): raise Blocked("an address with a user name or password in it is not used")
    if not p.hostname: raise Blocked("the address has no host name")
    if scheme == "https": return p
    if scheme == "http":
        if loopback_http and is_loopback(p.hostname) and (port or 80) in set(_load()["loopback_http_ports"]): return p
        if is_loopback(p.hostname): raise Blocked(f"a model on this computer is reached only on an approved port ({', '.join(map(str, _load()['loopback_http_ports']))}); port {port or 80} is not approved")
        raise Blocked(f"{p.hostname} is not on this computer, so it must be reached with https:// - plain http would send your key and your text unprotected")
    raise Blocked(f"only https addresses are used (got {scheme or 'no scheme'}://)")


def origin(url):
    """(scheme, host, port) of an address, normalised - what 'the same place' means for credentials."""
    p = urllib.parse.urlsplit(str(url)); s = (p.scheme or "").lower()
    return s, (p.hostname or "").lower().rstrip("."), p.port or {"https": 443, "http": 80}.get(s, 0)


def same_origin(a, b): return origin(a) == origin(b)


def token_allowed(url, rules):
    """May a credential be attached to this address? rules = [(host, port, [path prefixes])]: the host must match
    EXACTLY (no sub-domains, no look-alikes), the port exactly, the scheme must be https, and the path must start with
    one of the prefixes at a path boundary. A word in the path or in the file name proves nothing."""
    try: p = check_url(url)
    except Blocked: return False
    if (p.scheme or "").lower() != "https": return False
    host = (p.hostname or "").lower().rstrip("."); port = p.port or 443; path = p.path or "/"
    low = urllib.parse.unquote(path).lower()
    if "/../" in low + "/" or "/./" in low + "/" or "//" in low or "\\" in low or "%" in urllib.parse.unquote(path): return False      # a path with steps back, doubled or still-encoded parts is not a route anyone was authorised for
    for h, prt, prefixes in rules:
        if host != str(h).lower() or port != int(prt): continue
        for pre in prefixes:
            pre = ("/" + str(pre).strip("/")).lower()
            if pre == "/" or low == pre or low.startswith(pre + "/"): return True
    return False


# ------------------------------------------------------------------------------------------------ redaction
_SECRET_PATTERNS = [
    r"sk-ant-[A-Za-z0-9_\-]{8,}", r"sk-proj-[A-Za-z0-9_\-]{8,}", r"sk-or-[A-Za-z0-9_\-]{8,}", r"sk-[A-Za-z0-9_\-]{16,}",          # AI providers
    r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",                                                              # GitHub
    r"AIza[0-9A-Za-z_\-]{20,}", r"xox[abprs]-[A-Za-z0-9\-]{10,}", r"gsk_[A-Za-z0-9]{20,}", r"hf_[A-Za-z0-9]{20,}",
    r"sb[ps]_[A-Za-z0-9_\-]{20,}", r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}",                            # Supabase keys, JWTs
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
]
_SECRET_RE = re.compile("|".join(f"(?:{p})" for p in _SECRET_PATTERNS))
_HEADER_RE = re.compile(r"(?i)\b(authorization|x-api-key|api[-_ ]?key|apikey|x-goog-api-key|token|password|secret)\b(\s*[:=]\s*)(?:(bearer|basic|token)\s+)?(\"[^\"]{4,}\"|'[^']{4,}'|[^\s,;&\"']{4,})")


def redact(text):
    """The text without credentials: keys of every supported provider, GitHub tokens, JWTs, private keys, and whatever
    follows 'Authorization:', 'api-key =', 'token=' ... For logs, error messages, diagnostics and exports."""
    t = str(text)
    t = _HEADER_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{(m.group(3) + ' ') if m.group(3) else ''}[removed]", t)
    return _SECRET_RE.sub("[removed]", t)


def has_secret(text):
    return bool(_SECRET_RE.search(str(text)))


# ------------------------------------------------------------------------------------------------ aliases
class Aliases:
    """Stable stand-ins for names that identify your work (samples, graphs, files, folders): 'Sample 1', 'Graph 2',
    'File 1', '<folder>'. The same name gets the same alias for as long as this object lives; the table never leaves
    the computer, so an answer that mentions 'Sample 2' can be shown to you with the real name again."""
    def __init__(self):
        self.to = {}; self.back = {}; self.n = {}

    def alias(self, kind, value):
        v = str(value or "").strip()
        if not v: return v
        k = (kind, v)
        if k not in self.to:
            self.n[kind] = self.n.get(kind, 0) + 1; a = f"{kind.capitalize()} {self.n[kind]}" if kind != "folder" else "<folder>"
            self.to[k] = a; self.back[a] = v
        return self.to[k]

    def scrub(self, text):
        """Every known name in the text replaced by its alias (longest names first)."""
        return self._swap(str(text), {v: a for (kind, v), a in self.to.items() if len(v) >= 3})

    def restore(self, text):
        return self._swap(str(text), {a: v for a, v in self.back.items() if a != "<folder>"})

    @staticmethod
    def _swap(text, table):
        """Every key of the table replaced by its value in ONE pass, longest first - so a real name that happens to
        look like a stand-in ('Sample 1') is not replaced a second time."""
        if not table: return text
        rx = re.compile("|".join(re.escape(k) for k in sorted(table, key=len, reverse=True)))
        return rx.sub(lambda m: table[m.group(0)], text)


_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/(?:home|Users|mnt|media|Volumes|root|tmp|var|opt|srv|data|net|run|usr|etc)/|(?<![\w/.:<])/(?=[\w.\-]+/[\w.\-]+/))[^\s\"'<>|]*")


def strip_paths(text):
    """Folder paths in a text replaced by '<folder>' (the file name at the end is dropped too: it often names the sample)."""
    return _PATH_RE.sub("<folder>", str(text))


def describe():
    """The policy in one line, for a status bar or the settings page."""
    lv = level()
    return {"local_only": "Local-only: nothing is sent from this app", "minimal": "Minimal: your prompt and generic type information only",
            "metadata": "Approved metadata: labels and structure, no measurements", "scientific": "Approved scientific content: what you select is sent to the service you chose"}[lv]

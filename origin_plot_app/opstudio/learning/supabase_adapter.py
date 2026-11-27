"""supabase_adapter.py - the remote adapter for optional shared learning: Supabase (PostgREST + GoTrue) over HTTPS.

STATUS - READ THIS: this adapter has NOT been run against a live Supabase project. There is no deployed backend for
this app yet. It is written against the documented REST interface and is exercised in tests/test_learning_sync.py only
through an injected FAKE HTTP transport that records the requests (addresses, headers, bodies). Those tests show what
the client sends and how it reacts to status codes; they do not show that a server accepts it or that any row-level
policy holds. Live validation - with ordinary user credentials against the real policies - is pending.

What the desktop holds: the PUBLIC client configuration only (project URL + anon / publishable key, in
'<learning folder>/remote.json') and the signed-in user's own access / refresh tokens (in secure_store under
'learning:supabase'). A service-role or secret key is refused outright: such a key bypasses row-level security and
belongs on trusted infrastructure, never in a desktop build.

Every request: https only; the address must be the configured origin (the anon key and the bearer token are never sent
anywhere else, and redirects are not followed); outbound_policy.require("learning_sync", url) is asked immediately
before the transport is used, so local-only mode and the channel switch stop the request where it is sent; a finite
timeout; a bounded response size.

Remote tables this adapter expects (the SQL lives with the backend, not here):
    contributions(id uuid pk, owner_id uuid, lab_id uuid null, scope text ['lab','community'],
                  status text ['pending','approved','rejected','revoked'], kind text, data_family text, signature text,
                  signature_version int, schema_version int, revision int, app_version text, payload jsonb,
                  created_at, updated_at, reviewed_by uuid null, reviewed_at)
    contribution_feedback(id uuid pk, contribution_id uuid, user_id uuid, operation_id text, outcome text, created_at;
                  unique(contribution_id, user_id, operation_id))
    tombstones(contribution_id uuid, version bigint, deleted_at)
    evidence(id uuid pk, owner_id uuid, payload jsonb, created_at)

What the SERVER must enforce (this client cannot, and does not pretend to): owner_id = auth.uid() on insert; status
forced to 'pending' on insert and changeable to 'approved' / 'rejected' only by a reviewer; an owner may only move
their own row to 'revoked' (that is how withdraw() works: PATCH status='revoked' on the owner's row) and a tombstone is
written for it; lab rows visible to lab members only; a newer stored revision answers an older one with 409; rate
limits. The client never sends status (except 'revoked' on its own row), reviewed_by or reviewed_at.

Standard library only (urllib; the verified TLS context of net.context() when that module is importable).
"""
import base64, json, os, re, ssl, time, urllib.error, urllib.parse, urllib.request, uuid

from . import models as M
from .store import default_dir
from .sync import Offline, AuthExpired, Denied, Rejected, RateLimited, Conflict

TOKEN_NAME = "learning:supabase"
MAX_BODY = 2 * 1024 * 1024
_FEEDBACK_NS = uuid.UUID("a3c1f7d2-0b54-4e7e-8f3b-2f6d1f0a9c11")
_COLUMNS = ("id", "lab_id", "scope", "kind", "data_family", "signature", "signature_version", "schema_version", "revision", "app_version", "payload")
_SELECT = "id,lab_id,scope,status,kind,data_family,signature,signature_version,schema_version,revision,app_version,payload,updated_at"


class ConfigError(Exception):
    """The remote configuration is missing or not acceptable (e.g. a secret key). The text never contains the key."""


def config_path(): return os.path.join(default_dir(), "remote.json")


def key_role(key):
    """What kind of Supabase key this is, without contacting anything: 'publishable' / 'secret' (new key format), or the
    role claim of a JWT key ('anon', 'service_role', ...), or 'unknown'."""
    k = str(key or "").strip()
    if k.startswith("sb_secret_"): return "secret"
    if k.startswith("sb_publishable_"): return "publishable"
    parts = k.split(".")
    if len(parts) == 3:
        try:
            pad = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(pad.encode("ascii")).decode("utf-8"))
            return str(claims.get("role") or "unknown") if isinstance(claims, dict) else "unknown"
        except Exception: return "unknown"
    return "unknown"


def check_public_key(key):
    """Raise ConfigError unless the key is a PUBLIC client key (JWT role 'anon', or 'sb_publishable_...'). A
    'service_role' JWT or an 'sb_secret_...' key is refused: it must never be in a desktop build. A key whose kind
    cannot be read is refused as well."""
    role = key_role(key)
    if role in ("service_role", "secret", "supabase_admin"): raise ConfigError("this is a secret / service-role key; the desktop app only accepts the public (anon / publishable) key")
    if role not in ("anon", "publishable"): raise ConfigError("the key is not a public client key (anon / publishable)")
    return role


def load_config(path=None):
    """{'url', 'anon_key'} from remote.json, or None when there is no such file. Raises ConfigError for an unusable one."""
    p = path or config_path()
    if not os.path.isfile(p): return None
    try:
        with open(p, encoding="utf-8") as f: d = json.load(f)
    except (OSError, ValueError): raise ConfigError("remote.json cannot be read")
    if not isinstance(d, dict): raise ConfigError("remote.json is not a configuration")
    return {"url": str(d.get("url") or ""), "anon_key": str(d.get("anon_key") or d.get("publishable_key") or "")}


def _urllib_transport(method, url, headers, body, timeout):
    """The real transport: (status, headers, body bytes). Certificates are verified; redirects are not followed."""
    try:
        import net
        ctx = net.context()
    except Exception:
        ctx = ssl.create_default_context()

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None

    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _NoRedirect)
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with opener.open(req, timeout=timeout) as r: return r.status, dict(r.headers), r.read(MAX_BODY + 1)
    except urllib.error.HTTPError as e:
        try: data = e.read(MAX_BODY + 1)
        except Exception: data = b""
        return e.code, dict(e.headers or {}), data
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Offline(type(e).__name__)


class SupabaseAdapter:
    """sync.SyncAdapter over Supabase REST. See the module text for what is and is not verified.

    config     {'url': 'https://<project>.supabase.co', 'anon_key': '<public key>'}; default: load_config()
    transport  callable(method, url, headers, body, timeout) -> (status, headers, body) - tests inject a fake one
    timeout    seconds per request (finite, default 10)"""

    def __init__(self, config=None, *, transport=None, timeout=10.0, clock=None):
        cfg = config if config is not None else load_config()
        if not cfg or not cfg.get("url") or not cfg.get("anon_key"): raise ConfigError("shared learning is not set up (remote.json with url and anon_key)")
        check_public_key(cfg["anon_key"])
        import outbound_policy
        try: p = outbound_policy.check_url(cfg["url"])
        except outbound_policy.Blocked as e: raise ConfigError(str(e))
        if p.path not in ("", "/") or p.query or p.fragment: raise ConfigError("the address must be the project address only (https://host)")
        self.url = f"https://{p.hostname}" + (f":{p.port}" if p.port and p.port != 443 else "")
        self._key = cfg["anon_key"]; self._transport = transport or _urllib_transport
        self.timeout = max(1.0, min(float(timeout), 60.0)); self.clock = clock or time.time

    # ---- tokens (the user's own; kept in the protected store, never in a file of this package)
    def _tokens(self):
        import secure_store
        try: t = json.loads(secure_store.get(TOKEN_NAME) or "{}")
        except ValueError: t = {}
        return t if isinstance(t, dict) else {}

    def _keep(self, data):
        import secure_store
        user = data.get("user") if isinstance(data.get("user"), dict) else {}
        t = {"access_token": str(data.get("access_token") or ""), "refresh_token": str(data.get("refresh_token") or ""),
             "expires_at": self.clock() + float(data.get("expires_in") or 3600), "user_id": str(user.get("id") or self._tokens().get("user_id") or "")}
        if not t["access_token"] or not M.is_uuid(t["user_id"]): raise AuthExpired("sign in again")
        how = secure_store.put(TOKEN_NAME, json.dumps(t))
        return {"user_id": t["user_id"], "kept": how}

    def signed_in(self): return bool(self._tokens().get("access_token"))

    def sign_out(self):
        """Forget the tokens on this computer."""
        import secure_store
        secure_store.delete(TOKEN_NAME)

    def _session(self):
        t = self._tokens()
        if not t.get("access_token"): raise AuthExpired("not signed in")
        if float(t.get("expires_at") or 0) <= self.clock() + 30:
            self.refresh(); t = self._tokens()
        return t

    # ---- one request
    def _request(self, method, path, *, query=None, body=None, bearer=None, prefer=None, channel="learning_sync"):
        if not path.startswith(("/rest/v1/", "/auth/v1/")): raise Rejected("path")
        url = self.url + path + ("?" + urllib.parse.urlencode(query, safe=".,()*") if query else "")
        import outbound_policy
        if not outbound_policy.same_origin(url, self.url): raise Rejected("origin")          # the key and the token go to the configured origin only
        outbound_policy.require(channel, url)                                                 # raises outbound_policy.Blocked: nothing is sent
        headers = {"apikey": self._key, "Authorization": "Bearer " + (bearer or self._key), "Accept": "application/json", "User-Agent": "OriginPlotStudio-learning"}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8"); headers["Content-Type"] = "application/json"
        if prefer: headers["Prefer"] = prefer
        status, rh, raw = self._transport(method, url, headers, data, self.timeout)
        raw = raw or b""
        if len(raw) > MAX_BODY: raise Rejected("response too large")
        if status in (401,): raise AuthExpired("expired")
        if status == 403: raise Denied("refused by the access rules")
        if status == 409: raise Conflict(0)
        if status == 429:
            ra = {str(k).lower(): v for k, v in (rh or {}).items()}.get("retry-after", "60")
            raise RateLimited(float(ra) if re.match(r"^\d+(\.\d+)?$", str(ra)) else 60.0)
        if status >= 500 or status == 408: raise Offline(f"server {status}")
        if status >= 400: raise Rejected(f"refused ({status})")
        if not raw.strip(): return None
        try: return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError): raise Rejected("unreadable answer")

    # ---- sign-in
    def sign_in(self, email, password):
        """Sign in with the user's own account. The password is used for this one request and never stored."""
        try: data = self._request("POST", "/auth/v1/token", query={"grant_type": "password"}, body={"email": str(email), "password": str(password)})
        except (Rejected, AuthExpired): raise Denied("the sign-in was not accepted")
        if not isinstance(data, dict): raise Denied("the sign-in was not accepted")
        return self._keep(data)

    def refresh(self):
        t = self._tokens()
        if not t.get("refresh_token"): raise AuthExpired("not signed in")
        try: data = self._request("POST", "/auth/v1/token", query={"grant_type": "refresh_token"}, body={"refresh_token": t["refresh_token"]})
        except (Rejected, AuthExpired, Denied):
            self.sign_out(); raise AuthExpired("sign in again")
        if not isinstance(data, dict): raise AuthExpired("sign in again")
        return self._keep(data)

    # ---- contributions
    def submit_contribution(self, contribution):
        """Upsert the user's own contribution by its stable id. Sends ONLY the content columns and owner_id (the
        signed-in user): never status, reviewed_by or reviewed_at. The answer's status is whatever the server says."""
        t = self._session(); c = contribution or {}
        if not M.is_uuid(c.get("id")): raise Rejected("id")
        row = {k: c.get(k) for k in _COLUMNS}; row["owner_id"] = t["user_id"]
        if row.get("lab_id") is not None and not M.is_uuid(row["lab_id"]): raise Rejected("lab_id")
        data = self._request("POST", "/rest/v1/contributions", query={"on_conflict": "id"}, body=row, bearer=t["access_token"],
                             prefer="resolution=merge-duplicates,return=representation")
        got = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else (data if isinstance(data, dict) else {})
        return {"id": c["id"], "status": got.get("status") if got.get("status") in M.STATUSES else "pending", "revision": got.get("revision") if isinstance(got.get("revision"), int) else c.get("revision")}

    def withdraw(self, contribution_id):
        """Mark the user's own contribution 'revoked' (the server policy must allow an owner exactly this change and must
        write the tombstone)."""
        t = self._session()
        if not M.is_uuid(contribution_id): raise Rejected("id")
        self._request("PATCH", "/rest/v1/contributions", query={"id": f"eq.{contribution_id}", "owner_id": f"eq.{t['user_id']}"}, body={"status": "revoked"},
                      bearer=t["access_token"], prefer="return=minimal")
        return {"id": contribution_id, "status": "revoked"}

    def fetch_approved(self, since_cursor):
        """Approved records the signed-in user may read (the server's row-level rules decide which), oldest change
        first. The cursor is the updated_at of the last record received."""
        t = self._session()
        q = {"select": _SELECT, "status": "eq.approved", "order": "updated_at.asc", "limit": "200"}
        cur = str(since_cursor or "")
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?(Z|[+\-]\d{2}:\d{2})$", cur): q["updated_at"] = f"gt.{cur}"
        else: cur = ""
        data = self._request("GET", "/rest/v1/contributions", query=q, bearer=t["access_token"])
        rows = [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []
        last = next((str(r.get("updated_at")) for r in reversed(rows) if r.get("updated_at")), cur)
        return rows, last

    def fetch_tombstones(self, since):
        t = self._session()
        v = int(since) if isinstance(since, int) or str(since or "").isdigit() else 0
        data = self._request("GET", "/rest/v1/tombstones", query={"select": "contribution_id,version,deleted_at", "version": f"gt.{v}", "order": "version.asc", "limit": "1000"}, bearer=t["access_token"])
        rows = [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []
        return rows, max([v] + [r["version"] for r in rows if isinstance(r.get("version"), int)])

    def submit_feedback(self, contribution_id, operation_id, outcome):
        """One row per (contribution, user, operation): a retry of the same operation is ignored by the unique key, so
        it can never count twice."""
        t = self._session()
        if not M.is_uuid(contribution_id) or outcome not in M.FEEDBACK_OUTCOMES: raise Rejected("feedback")
        op = re.sub(r"[^A-Za-z0-9_.:\-]", "", str(operation_id))[:80]
        row = {"id": str(uuid.uuid5(_FEEDBACK_NS, f"{contribution_id}:{t['user_id']}:{op}")), "contribution_id": contribution_id, "user_id": t["user_id"], "operation_id": op, "outcome": outcome}
        self._request("POST", "/rest/v1/contribution_feedback", query={"on_conflict": "contribution_id,user_id,operation_id"}, body=row, bearer=t["access_token"],
                      prefer="resolution=ignore-duplicates,return=minimal")
        return {"id": row["id"]}

    def submit_evidence(self, bundle):
        """Send a sanitised evidence bundle (evidence.build) to the 'evidence' table. This is a DIAGNOSTICS upload: it
        is asked of the 'diagnostics' channel of the outbound policy, which is off by default. Not part of SyncAdapter
        and never called by the sync worker; the app calls it only on the user's explicit action."""
        t = self._session()
        if not isinstance(bundle, dict) or bundle.get("schema") != M.EVIDENCE_SCHEMA: raise Rejected("evidence")
        row = {"id": str(uuid.uuid4()), "owner_id": t["user_id"], "payload": bundle}
        self._request("POST", "/rest/v1/evidence", body=row, bearer=t["access_token"], prefer="return=minimal", channel="diagnostics")
        return {"id": row["id"]}

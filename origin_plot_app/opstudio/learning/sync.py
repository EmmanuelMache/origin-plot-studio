"""sync.py - optional sharing: the adapter protocol, the contribution flow, and the background worker.

Sharing is OFF by default and local work never depends on it.

    personal memory
      -> preview_contribution(service, memory_id, scope=...)   the exact sanitised record (privacy.shareable), to be shown
      -> submit(service, memory_id, scope=..., consent=True, preview_digest=...)   explicit consent; the digest proves the
                                                               record queued is the record that was previewed
      -> sync_outbox (local queue)
      -> SyncWorker.run_once()  -> adapter.submit_contribution -> remote record, status 'pending'
      -> an AUTHORISED REVIEWER approves it on the server (never this client)
      -> adapter.fetch_approved -> authorised clients; a downloaded record stays INERT until it passes
         validate_remote() (schema, sizes, known family, recomputed signature, models.validate_recipe) and its template
         is installed

Scopes: 'personal' (never leaves the computer), 'lab', 'community'.

The worker: runs off the UI thread; every run has a time budget and every adapter call a finite timeout; retries back
off exponentially up to a cap; a contribution id is stable (uuid5 of installation, memory and scope) so a retry is the
same record, not a new one; offline, expired login, rate limit, a newer remote revision and remote deletions are each
handled explicitly; no database transaction is open while the network is used; and before any use of the network
outbound_policy.require("learning_sync", url) is asked - in local-only mode nothing is sent.

WHAT IS A MOCK HERE: FakeServer / FakeAdapter at the end of this file are an IN-MEMORY SIMULATION for tests. They are
not a backend and prove nothing about a deployed service. The real adapter is supabase_adapter.SupabaseAdapter.
"""
import copy, json, threading, time, uuid
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from . import matcher, models as M, privacy, signatures as sg
from .models import Outcome, ActionResult
from .store import StorageUnavailable

_NS = uuid.UUID("6f1d1c0e-5b0a-4c57-9d2e-0f3a7b1c9e42")          # namespace of contribution ids (a constant, not a secret)
MAX_RECORD_BYTES = 65536


# ------------------------------------------------------------------------------------------------ errors and protocol
class SyncError(Exception):
    """Base of what an adapter may raise. The text is a short word or sentence without content of the user."""
class Offline(SyncError):
    """No connection, a timeout or a server error: try again later."""
class AuthExpired(SyncError):
    """Not signed in, or the sign-in ran out and could not be refreshed: the user has to sign in again."""
class Denied(SyncError):
    """The server refused the request by its access rules (not the owner, not in this lab, not a reviewer ...)."""
class Rejected(SyncError):
    """The server refused the content (schema, size, unknown field)."""
class RateLimited(SyncError):
    def __init__(self, retry_after=60.0): super().__init__("rate limited"); self.retry_after = float(retry_after or 60.0)
class Conflict(SyncError):
    """The remote record has a newer revision than the one sent."""
    def __init__(self, remote_revision=0): super().__init__("remote revision is newer"); self.remote_revision = int(remote_revision or 0)


@runtime_checkable
class SyncAdapter(Protocol):
    """What a remote backend must offer. An institutional service can replace Supabase by implementing this.

    url                      the https origin the adapter talks to (asked of outbound_policy before any use)
    sign_in(email, password) -> {'user_id': ...}        refresh() -> {'user_id': ...}
    submit_contribution(c)   c = {'id', 'scope', 'lab_id', 'kind', 'data_family', 'signature', 'signature_version',
                             'schema_version', 'revision', 'app_version', 'payload'} -> {'id', 'status', 'revision'}.
                             The client never sends a status, an owner or a reviewer; the server sets them.
    withdraw(contribution_id) -> {'id', 'status'}
    fetch_approved(since_cursor) -> (records, next_cursor)    records as the remote 'contributions' rows
    fetch_tombstones(since)  -> ([{'contribution_id', 'version', 'deleted_at'}], latest_version)
    submit_feedback(contribution_id, operation_id, outcome) -> {...}
    Errors: Offline, AuthExpired, Denied, Rejected, RateLimited, Conflict."""
    url: str
    def sign_in(self, email, password): ...
    def refresh(self): ...
    def submit_contribution(self, contribution): ...
    def withdraw(self, contribution_id): ...
    def fetch_approved(self, since_cursor): ...
    def fetch_tombstones(self, since): ...
    def submit_feedback(self, contribution_id, operation_id, outcome): ...


# ------------------------------------------------------------------------------------------------ contribution flow
def contribution_id(installation, memory_id, scope):
    """The stable id of 'this memory shared at this scope from this installation'. Retries reuse it."""
    return str(uuid.uuid5(_NS, f"{installation}:{memory_id}:{scope}"))


def preview_contribution(service, memory_id, *, scope=None, role_overrides=None):
    """What would be shared, for the user to read BEFORE consenting. Returns
        {'ok', 'needs_review', 'reasons', 'scope', 'contribution_id', 'payload', 'text', 'digest'}
    payload is the exact record (privacy.shareable); text is the same as indented JSON for display; digest must be
    handed to submit() - if the memory is edited in between, the digest no longer matches and nothing is queued.
    Nothing is stored or sent by a preview."""
    s = service.get_settings(); scope = scope or s["sharing_scope"]
    out = {"ok": False, "needs_review": False, "reasons": [], "scope": scope, "contribution_id": "", "payload": None, "text": "", "digest": ""}
    if scope not in M.SHARE_SCOPES: out["reasons"].append("choose 'lab' or 'community'"); return out
    try: mem = service.store.memory(memory_id)
    except StorageUnavailable: out["reasons"].append("the memory could not be read"); return out
    if mem is None: out["reasons"].append("this memory no longer exists"); return out
    proj = privacy.shareable(mem, role_overrides)
    out.update(ok=proj["ok"], needs_review=proj["needs_review"], reasons=list(proj["reasons"]), payload=proj["payload"])
    if proj["payload"] is not None:
        out["contribution_id"] = contribution_id(service.installation_id(), memory_id, scope)
        out["text"] = json.dumps(proj["payload"], indent=1, ensure_ascii=False, sort_keys=True)
        out["digest"] = M.digest([scope, proj["payload"]], 40)
    return out


def submit(service, memory_id, *, scope, consent, preview_digest, role_overrides=None):
    """Queue a contribution. Requires: the sharing preference on ('disabled' otherwise), consent is True
    ('not_permitted'), a valid scope and - for 'lab' - a lab id in the settings, a shareable memory that does not need
    review ('validation_failed'), and the digest of the preview the user saw ('stale_candidate' when the record changed
    since). Nothing is sent here; the worker sends it. A repeat is 'already_saved'."""
    s = service.get_settings()
    if not s["sharing"]: return ActionResult(Outcome.DISABLED, "Sharing is switched off", memory_id=memory_id)
    if consent is not True: return ActionResult(Outcome.NOT_PERMITTED, "Nothing is shared without your consent", memory_id=memory_id)
    if scope not in M.SHARE_SCOPES: return ActionResult(Outcome.VALIDATION_FAILED, "Choose lab or community", memory_id=memory_id)
    if scope == "lab" and not s["lab_id"]: return ActionResult(Outcome.VALIDATION_FAILED, "No lab is set up for sharing", memory_id=memory_id)
    p = preview_contribution(service, memory_id, scope=scope, role_overrides=role_overrides)
    if p["payload"] is None or not p["ok"]:
        return ActionResult(Outcome.VALIDATION_FAILED, "This memory cannot be shared: " + "; ".join(p["reasons"]), memory_id=memory_id, detail={"needs_review": p["needs_review"], "reasons": p["reasons"]})
    if not preview_digest or preview_digest != p["digest"]: return ActionResult(Outcome.STALE, "The record changed since the preview; look at it again", memory_id=memory_id)
    try: res = service.store.queue_submit(memory_id, p["payload"]["revision"], p["contribution_id"], scope, s["lab_id"] if scope == "lab" else "", p["payload"])
    except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The contribution could not be queued", memory_id=memory_id)
    return ActionResult(res, {Outcome.SAVED: "Queued for sharing; it stays pending until a reviewer approves it"}.get(res, ""), memory_id=memory_id, detail={"contribution_id": p["contribution_id"], "scope": scope})


def withdraw(service, memory_id):
    """Take a contribution back, keeping the personal memory: a queued one is cancelled; for one that was sent the
    withdrawal is queued (detail['remote'] True). Copies other people already downloaded disappear when their app next
    synchronises the deletion record - a computer that stays offline keeps its copy until then."""
    try:
        mem = service.store.memory(memory_id)
        if mem is None: return ActionResult(Outcome.NOT_FOUND, "This memory no longer exists", memory_id=memory_id)
        n = service.store.cancel_queued(memory_id)
        if mem["remote_id"] and mem["visibility"] == "personal":
            res = service.store.queue_withdraw(memory_id, mem["remote_id"])
            return ActionResult(res, "Withdrawal queued", memory_id=memory_id, detail={"remote": True, "cancelled": n})
        return ActionResult(Outcome.SAVED if n else Outcome.ALREADY_SAVED, "Cancelled before it was sent" if n else "Nothing was shared", memory_id=memory_id, detail={"remote": False, "cancelled": n})
    except StorageUnavailable: return ActionResult(Outcome.STORAGE_UNAVAILABLE, "The withdrawal could not be saved", memory_id=memory_id)


# ------------------------------------------------------------------------------------------------ downloaded records
_STRUCTURE = M.Obj({"container": M.Enum(*M.CONTAINERS), "delimiter": M.Enum(*M.DELIMITERS), "decimal": M.Enum(*M.DECIMALS), "header": M.Bool(),
                    "column_count": M.Int(0, M.MAX_COLUMNS),
                    "columns": M.Arr(M.Obj({"role": M.Tok(r"^(-|[a-z0-9]{1,12}):[a-z_]{1,24}$", 40), "unit": M.Tok(r"^[A-Za-z0-9_]{0,24}$", 24)}, required=("role", "unit")), 0, M.MAX_COLUMNS)},
                   required=("container", "delimiter", "decimal", "header", "columns"))


def _refs(recipe, kind):
    if kind == "import_mapping":
        for v in (recipe.get("roles") or {}).values(): yield from (v if isinstance(v, list) else [v])
    elif kind == "unit_mapping":
        for e in recipe.get("units") or []: yield e.get("col") or {}


def validate_remote(record, installed):
    """A memory dict for the store from a downloaded record - or RecipeError. Until this passes a record is not stored
    as usable knowledge. Checked: the size; the id; scope, status 'approved', kind (no legacy kinds), data family,
    schema and signature versions; that every text is inert (no code, no instructions, no credential); the recipe
    against models.validate_recipe; that a shared mapping refers to columns by structural role only (no header text);
    that a shared style is for a data family and carries no axis limits; and that the signature the record claims is
    the one its own sanitised structure gives. A record whose template is not installed is kept but flagged
    needs_revalidation - it is not offered."""
    if not isinstance(record, dict): raise M.RecipeError("not_an_object", "record")
    try: size = len(json.dumps(record, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError): raise M.RecipeError("not_json", "record")
    if size > MAX_RECORD_BYTES: raise M.RecipeError("too_large", "record")
    rid = record.get("id")
    if not M.is_uuid(rid): raise M.RecipeError("bad_id", "record.id")
    if record.get("scope") not in M.SHARE_SCOPES: raise M.RecipeError("bad_scope", "record.scope")
    if record.get("status") != "approved": raise M.RecipeError("not_approved", "record.status")
    kind = record.get("kind")
    if kind not in M.KINDS or kind in M.LEGACY_KINDS: raise M.RecipeError("unknown_kind", "record.kind")
    fam = record.get("data_family")
    if fam not in M.FAMILIES: raise M.RecipeError("unknown_family", "record.data_family")
    if record.get("schema_version") != M.SCHEMA_VERSION: raise M.RecipeError("unsupported_schema", "record.schema_version")
    if record.get("signature_version") != sg.SIGNATURE_VERSION: raise M.RecipeError("unsupported_signature", "record.signature_version")
    rev = record.get("revision")
    if isinstance(rev, bool) or not isinstance(rev, int) or not 1 <= rev <= 1000000: raise M.RecipeError("bad_revision", "record.revision")
    payload = record.get("payload")
    if not isinstance(payload, dict): raise M.RecipeError("not_an_object", "record.payload")
    extra = set(payload) - {"schema", "kind", "data_family", "signature", "signature_version", "schema_version", "revision", "app_version", "structure", "recipe",
                            "template_id", "template_version", "validation"}
    if extra: raise M.RecipeError("unknown_key", "record.payload." + sorted(map(str, extra))[0][:24])
    M.assert_inert(payload, "record.payload")
    recipe = M.validate_recipe(kind, payload.get("recipe"))
    if recipe.get("data_family", fam) != fam: raise M.RecipeError("family_mismatch", "record.payload.recipe.data_family")
    for ref in _refs(recipe, kind):
        if "h" in ref or "role" not in ref: raise M.RecipeError("header_text_in_shared_record", "record.payload.recipe")
    if kind == "graph_style" and (recipe["target"]["scope"] != "family" or recipe.get("include_limits")): raise M.RecipeError("style_not_shareable", "record.payload.recipe")
    sig = record.get("signature") or ""; structure = payload.get("structure"); ctx = {}
    if structure is not None:
        structure = _STRUCTURE(structure, True, "record.payload.structure")
        roles = [c["role"].split(":", 1)[1] for c in structure["columns"]]
        if any(r not in sg.KNOWN_ROLES for r in roles): raise M.RecipeError("unknown_role", "record.payload.structure")
        units = [c["unit"] for c in structure["columns"]]
        if any(u and u != "other" and not sg.unit_known(u) for u in units): raise M.RecipeError("unknown_unit", "record.payload.structure")
        if sg.shareable_signature(structure["container"], structure["delimiter"], structure["decimal"], structure["header"], roles, units) != sig:
            raise M.RecipeError("signature_mismatch", "record.signature")
        ctx = {"container": structure["container"], "delimiter": structure["delimiter"], "decimal": structure["decimal"], "header_row": 0 if structure["header"] else -1,
               "column_count": len(structure["columns"]), "headers": [], "units": units, "roles": roles, "data_family": fam}
    elif sig: raise M.RecipeError("signature_mismatch", "record.signature")
    elif kind in ("import_mapping", "classification", "unit_mapping"): raise M.RecipeError("missing_key", "record.payload.structure")
    tids = [t for t in [recipe.get("template_id")] if t] + ([s["params"]["template_id"] for s in recipe.get("steps", []) if s["op"] == "draw_template" and s["params"].get("template_id")] if kind == "workflow" else [])
    missing = any(t not in installed for t in tids)
    tid = recipe.get("template_id") or ""
    val = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    lab = record.get("lab_id") if M.is_uuid(record.get("lab_id")) else ""
    return {"kind": kind, "signature": sig, "signature_version": sg.SIGNATURE_VERSION, "share_signature": sig, "data_family": fam,
            "scope": "personal_format" if kind in ("import_mapping", "classification", "unit_mapping") else "personal_family", "scope_key": "",
            "visibility": record["scope"], "status": "approved", "lab_id": lab, "origin": "system", "enabled": True, "needs_revalidation": missing,
            "recipe": recipe, "context": ctx, "constraints": {"template_id": tid, "template_version": installed.get(tid, ""), "signature_version": sg.SIGNATURE_VERSION},
            "validation": {"structural_checks_passed": bool(val.get("structural_checks_passed")), "preview_rendered": bool(val.get("preview_rendered")),
                           "user_confirmed": False, "reviewed": True},
            "provenance": {"origin": "system", "source": "shared", "scope": record["scope"], "contribution_id": rid, "remote_revision": rev},
            "template_id": tid, "template_version": installed.get(tid, ""), "remote_id": rid, "remote_revision": rev, "dedup_key": M.digest(["remote", rid], 40)}


# ------------------------------------------------------------------------------------------------ the worker
@dataclass
class SyncReport:
    """What one run did. outcome: 'ok' | 'disabled' (sharing off) | 'blocked' (privacy policy / local-only mode) |
    'offline' | 'auth_required' | 'rate_limited' | 'storage_unavailable'."""
    outcome: str = "ok"
    message: str = ""
    sent: int = 0
    withdrawn: int = 0
    failed: int = 0
    conflicts: int = 0
    retried_later: int = 0
    feedback: int = 0
    downloaded: int = 0            # records received
    activated: int = 0             # of those: validated and usable now
    inert: int = 0                 # stored but not offered (template not installed)
    rejected: int = 0              # refused by validation - never stored as knowledge
    tombstones: int = 0
    retry_after: float = 0.0
    errors: list = field(default_factory=list)


class SyncWorker:
    """Synchronises the outbox and the approved records in the background. run_once() is the whole job and can be
    called directly (tests, a 'Synchronise now' button on a worker thread); start() runs it periodically on its own
    daemon thread with its own database connection. Never call run_once() on the UI thread."""

    def __init__(self, service, adapter, *, url=None, base_delay=2.0, max_delay=900.0, run_budget=30.0, interval=900.0, max_batch=50, clock=None):
        self.service = service; self.adapter = adapter; self.url = url or getattr(adapter, "url", "")
        self.base_delay = float(base_delay); self.max_delay = float(max_delay); self.run_budget = float(run_budget); self.interval = float(interval)
        self.max_batch = int(max_batch); self.clock = clock or service.clock
        self._stop = threading.Event(); self._thread = None; self.last_report = None

    def backoff(self, attempts):
        """Seconds to wait after the n-th failed attempt: base * 2^n, never more than max_delay."""
        return min(self.max_delay, self.base_delay * (2 ** max(0, min(int(attempts), 30))))

    # ---- policy: asked before ANY use of the adapter
    def _permitted(self):
        try:
            import outbound_policy
        except Exception:
            return "the privacy policy of the app could not be read, so nothing is sent"
        try: outbound_policy.require("learning_sync", self.url)
        except outbound_policy.Blocked as e: return str(e)
        return ""

    def _call(self, fn, *args):
        """One adapter call; an expired sign-in is refreshed once and the call repeated once."""
        try: return fn(*args)
        except AuthExpired:
            self.adapter.refresh()                       # raises AuthExpired again when the user has to sign in
            return fn(*args)

    def run_once(self):
        rep = SyncReport(); st = self.service.store
        try:
            if not self.service.get_settings()["sharing"]: rep.outcome = "disabled"; rep.message = "Sharing is switched off"; return self._done(rep)
            why = self._permitted()
            if why: rep.outcome = "blocked"; rep.message = why; return self._done(rep)
            deadline = self.clock() + self.run_budget
            try:
                self._upload(rep, deadline)
                if self.clock() < deadline: self._upload_feedback(rep, deadline)
                if self.clock() < deadline: self._download(rep)
                if self.clock() < deadline: self._tombstones(rep)
                st.set_state("last_sync", M.now_iso(self.clock))
            except Offline as e: rep.outcome = "offline"; rep.message = "No connection; it will be tried again later"; rep.errors.append(type(e).__name__)
            except AuthExpired: rep.outcome = "auth_required"; rep.message = "Sign in again to continue sharing"
            except RateLimited as e: rep.outcome = "rate_limited"; rep.retry_after = e.retry_after; rep.message = "The service asked to slow down"
            except SyncError as e: rep.errors.append(type(e).__name__)
        except StorageUnavailable: rep.outcome = "storage_unavailable"; rep.message = "The learning database is not available"
        except Exception as e: rep.errors.append(type(e).__name__)          # a worker thread must not die on a surprise
        return self._done(rep)

    def _done(self, rep): self.last_report = rep; return rep

    def _contribution(self, row):
        p = row["payload"]
        return {"id": row["contribution_id"], "scope": row["scope"], "lab_id": row["lab_id"] or None, "kind": p.get("kind"), "data_family": p.get("data_family"),
                "signature": p.get("signature", ""), "signature_version": p.get("signature_version"), "schema_version": p.get("schema_version"),
                "revision": p.get("revision"), "app_version": p.get("app_version", ""), "payload": copy.deepcopy(p)}

    def _upload(self, rep, deadline):
        st = self.service.store; now = self.clock()
        rows = [r for r in st.outbox(states=("queued",)) if float(r["next_attempt_at"] or 0) <= now][:self.max_batch]          # read; no transaction stays open
        for k, row in enumerate(rows):
            if self.clock() >= deadline: break
            if row["action"] == "submit" and (st.tombstoned(memory_id=row["memory_id"]) or st.memory(row["memory_id"]) is None):
                st.update_outbox(row["id"], state="cancelled", last_error="forgotten"); continue          # a forgotten memory is never sent
            try:
                if row["action"] == "submit":
                    res = self._call(self.adapter.submit_contribution, self._contribution(row)) or {}          # network: no transaction open
                    how = st.mark_sent(row, res.get("status") or "pending", res.get("revision") or row["memory_revision"])
                    rep.sent += 1 if how == "sent" else 0
                else:
                    self._call(self.adapter.withdraw, row["contribution_id"])
                    st.update_outbox(row["id"], state="sent", last_error="")
                    with st.tx() as c: c.execute("UPDATE memories SET status='revoked' WHERE remote_id=? AND visibility='personal'", (row["contribution_id"],))
                    rep.withdrawn += 1
            except Offline:
                for r in rows[k:]:                                                             # everything that was due waits; each by its own count of attempts
                    n = int(r["attempts"]) + 1
                    st.update_outbox(r["id"], attempts=n, next_attempt_at=self.clock() + self.backoff(n), last_error="offline"); rep.retried_later += 1
                raise
            except RateLimited as e:
                st.update_outbox(row["id"], next_attempt_at=self.clock() + min(self.max_delay, e.retry_after), last_error="rate_limited"); rep.retried_later += 1
                raise
            except AuthExpired:
                raise                                                                          # the row stays queued, untouched
            except Conflict as e:
                st.update_outbox(row["id"], state="conflict", last_error=f"remote_revision:{e.remote_revision}"); rep.conflicts += 1
            except (Denied, Rejected) as e:
                st.update_outbox(row["id"], state="failed", last_error=type(e).__name__.lower()); rep.failed += 1
                if row["action"] == "submit":
                    with st.tx() as c: c.execute("UPDATE memories SET status='rejected' WHERE id=? AND remote_id=''", (row["memory_id"],))

    def _upload_feedback(self, rep, deadline):
        """Only the user's EXPLICIT answers about records received from others; automatic uses (origin 'memory') and
        everything about personal memories stay on this computer. One row per operation id - a retry is the same row."""
        st = self.service.store
        rows = st.q("SELECT f.id, f.operation_id, f.outcome, m.remote_id FROM feedback f JOIN memories m ON m.id=f.memory_id"
                    " WHERE f.synced=0 AND f.origin='user' AND m.visibility<>'personal' AND m.remote_id<>'' ORDER BY f.created_at, f.rowid LIMIT ?", (self.max_batch,))
        for fb in rows:
            if self.clock() >= deadline: break
            try: self._call(self.adapter.submit_feedback, fb["remote_id"], fb["operation_id"], fb["outcome"])
            except (Denied, Rejected, Conflict): pass              # not wanted by the server: do not retry forever
            st.mark_feedback_synced(fb["id"]); rep.feedback += 1

    def _download(self, rep):
        st = self.service.store
        cursor = st.state("approved_cursor", "")
        records, nxt = self._call(self.adapter.fetch_approved, cursor)          # network: no transaction open
        installed = self.service.templates(); quarantine = list(st.state("quarantine", []))
        for rec in list(records or [])[:1000]:
            rep.downloaded += 1
            rid = rec.get("id") if isinstance(rec, dict) else None
            if rid and st.tombstoned(remote_id=rid): continue                    # forgotten here: stays forgotten
            own = st.q("SELECT id FROM memories WHERE remote_id=? AND visibility='personal'", (rid,)) if rid else []
            if own:
                with st.tx() as c: c.execute("UPDATE memories SET status='approved', remote_revision=? WHERE id=?", (int(rec.get("revision") or 0) if isinstance(rec.get("revision"), int) else 0, own[0]["id"]))
                continue
            try: mem = validate_remote(rec, installed)
            except M.RecipeError as e:
                rep.rejected += 1
                quarantine.append({"id": rid if M.is_uuid(rid) else "", "reason": e.code, "at": M.now_iso(self.clock)})
                continue
            effect, _mid, _rev = st.put_memory(mem, reason="shared_download")
            if effect in ("created", "revised"):
                if mem["needs_revalidation"]: rep.inert += 1
                else: rep.activated += 1
        st.set_state("quarantine", quarantine[-50:])
        if nxt is not None: st.set_state("approved_cursor", nxt)

    def _tombstones(self, rep):
        st = self.service.store
        since = st.state("tombstone_version", 0)
        items, latest = self._call(self.adapter.fetch_tombstones, since)
        for t in list(items or [])[:5000]:
            if isinstance(t, dict) and M.is_uuid(t.get("contribution_id")):
                if st.apply_remote_tombstone(t["contribution_id"], t.get("version") if isinstance(t.get("version"), int) else 0) != "none": rep.tombstones += 1
        if isinstance(latest, int) and latest > int(since or 0): st.set_state("tombstone_version", latest)

    # ---- background thread
    def start(self):
        """Run periodically on a daemon thread (its own database connection). Returns immediately."""
        if self._thread and self._thread.is_alive(): return
        self._stop.clear()
        def loop():
            try:
                while not self._stop.is_set():
                    rep = self.run_once()
                    wait = self.interval
                    if rep.outcome in ("offline", "rate_limited"): wait = min(self.interval, max(self.base_delay, rep.retry_after or self.backoff(1)))
                    if self._stop.wait(wait): break
            finally:
                self.service.store.close()
        self._thread = threading.Thread(target=loop, name="ops-learning-sync", daemon=True); self._thread.start()

    def stop(self, timeout=5.0):
        """Ask the thread to stop and wait at most `timeout` seconds. A running network call ends by its own timeout."""
        self._stop.set()
        if self._thread: self._thread.join(timeout)


# ================================================================================================ TEST DOUBLES - NOT A BACKEND
class FakeServer:
    """IN-MEMORY MOCK of the remote service, FOR TESTS ONLY. It is not a database, not Supabase and not evidence that a
    deployed backend enforces anything. It simulates the server-side rules the real service must enforce so that the
    client logic can be exercised against refusals:
      * a contribution belongs to the signed-in user; its status always starts 'pending'; a client that sends a status,
        an owner or a reviewer field is refused
      * lab records are readable only by members of that lab; community records by everyone signed in
      * only a reviewer can approve or reject (for a lab record: a reviewer of that lab)
      * a rate limit on new contributions per user
      * idempotent ids: the same id and revision again is the same record, not a second one
      * withdrawal by the owner writes a versioned tombstone."""

    def __init__(self, clock=None, rate_limit=5, rate_window=60.0):
        self.clock = clock or time.time; self.rate_limit = int(rate_limit); self.rate_window = float(rate_window)
        self.users = {}; self.contributions = {}; self.feedback = {}; self.tombstones = []; self.seq = 0; self.version = 0
        self.offline = False; self.submissions = []; self.requests = 0

    def add_user(self, email, password, *, lab_id=None, reviewer=False):
        uid = str(uuid.uuid4()); self.users[email] = {"id": uid, "email": email, "password": password, "lab_id": lab_id, "reviewer": bool(reviewer)}
        return uid


class FakeAdapter:
    """IN-MEMORY MOCK adapter FOR TESTS ONLY: one signed-in user talking to a FakeServer. No network is used; the url
    is a reserved name that cannot exist ('learning.invalid'). See FakeServer for what is simulated. Passing tests with
    this adapter show that the CLIENT handles offline, expiry, refusals, limits, conflicts and tombstones - they do not
    show that any real server refuses anything."""
    url = "https://learning.invalid"

    def __init__(self, server, url=None):
        self.server = server; self.user = None; self.expired = False; self.refresh_works = True
        if url: self.url = url

    # ---- session
    def _up(self):
        self.server.requests += 1
        if self.server.offline: raise Offline("offline")

    def _auth(self):
        self._up()
        if self.user is None: raise AuthExpired("not signed in")
        if self.expired: raise AuthExpired("expired")
        return self.user

    def sign_in(self, email, password):
        self._up()
        u = self.server.users.get(email)
        if u is None or u["password"] != password: raise Denied("wrong sign-in")
        self.user = u; self.expired = False
        return {"user_id": u["id"]}

    def refresh(self):
        self._up()
        if self.user is None or not self.refresh_works: raise AuthExpired("sign in again")
        self.expired = False
        return {"user_id": self.user["id"]}

    # ---- contributions
    def submit_contribution(self, contribution):
        u = self._auth(); s = self.server; c = dict(contribution or {})
        if "status" in c or "reviewed_by" in c or "reviewed_at" in c: raise Denied("a client cannot set the review state")
        if c.get("owner_id") not in (None, u["id"]): raise Denied("a client cannot submit for someone else")
        if not M.is_uuid(c.get("id")) or c.get("scope") not in M.SHARE_SCOPES: raise Rejected("schema")
        if c["scope"] == "lab" and (not u["lab_id"] or c.get("lab_id") != u["lab_id"]): raise Denied("not a member of this lab")
        try:
            if c.get("kind") in M.LEGACY_KINDS: raise M.RecipeError("unknown_kind")
            M.validate_recipe(c.get("kind"), (c.get("payload") or {}).get("recipe"))
        except M.RecipeError: raise Rejected("schema")
        old = s.contributions.get(c["id"])
        if old is not None:
            if old["owner_id"] != u["id"]: raise Denied("not the owner")
            if int(c.get("revision") or 0) == old["revision"]: return {"id": old["id"], "status": old["status"], "revision": old["revision"]}      # replay: same record
            if int(c.get("revision") or 0) < old["revision"]: raise Conflict(old["revision"])
        now = s.clock()
        recent = [t for (uid, t) in s.submissions if uid == u["id"] and now - t < s.rate_window]
        if len(recent) >= s.rate_limit: raise RateLimited(s.rate_window - (now - min(recent)))
        s.submissions.append((u["id"], now)); s.seq += 1
        row = {"id": c["id"], "owner_id": u["id"], "lab_id": c.get("lab_id") if c["scope"] == "lab" else None, "scope": c["scope"], "status": "pending",
               "kind": c.get("kind"), "data_family": c.get("data_family"), "signature": c.get("signature", ""), "signature_version": c.get("signature_version"),
               "schema_version": c.get("schema_version"), "revision": int(c.get("revision") or 1), "app_version": c.get("app_version", ""),
               "payload": copy.deepcopy(c.get("payload")), "created_at": now if old is None else old["created_at"], "updated_at": now, "reviewed_by": None, "reviewed_at": None, "_seq": s.seq}
        s.contributions[c["id"]] = row
        return {"id": row["id"], "status": "pending", "revision": row["revision"]}

    def review(self, contribution_id, status):
        """TEST HELPER standing in for the reviewer's tool: approve or reject. Refused for anyone who is not a reviewer
        (for a lab record: not a reviewer of that lab)."""
        u = self._auth(); s = self.server; row = s.contributions.get(contribution_id)
        if row is None: raise Rejected("no such contribution")
        if status not in ("approved", "rejected"): raise Rejected("schema")
        if not u["reviewer"] or (row["scope"] == "lab" and row["lab_id"] != u["lab_id"]): raise Denied("only a reviewer can approve")
        s.seq += 1
        row.update(status=status, reviewed_by=u["id"], reviewed_at=s.clock(), updated_at=s.clock(), _seq=s.seq)
        return {"id": row["id"], "status": status}

    def withdraw(self, contribution_id):
        u = self._auth(); s = self.server; row = s.contributions.get(contribution_id)
        if row is None: return {"id": contribution_id, "status": "revoked"}
        if row["owner_id"] != u["id"]: raise Denied("not the owner")
        if row["status"] != "revoked":
            s.version += 1; s.seq += 1
            row.update(status="revoked", updated_at=s.clock(), _seq=s.seq)
            s.tombstones.append({"contribution_id": contribution_id, "version": s.version, "deleted_at": s.clock()})
        return {"id": contribution_id, "status": "revoked"}

    def _visible(self, row, u):
        return row["status"] == "approved" and (row["scope"] == "community" or (row["lab_id"] is not None and row["lab_id"] == u["lab_id"]))

    def fetch_approved(self, since_cursor):
        u = self._auth(); s = self.server
        since = int(since_cursor) if str(since_cursor or "").isdigit() else 0
        rows = sorted((r for r in s.contributions.values() if r["_seq"] > since and self._visible(r, u)), key=lambda r: r["_seq"])
        return [{k: copy.deepcopy(v) for k, v in r.items() if k != "_seq"} for r in rows], str(s.seq)

    def fetch_tombstones(self, since):
        self._auth(); s = self.server; since = int(since or 0)
        return [dict(t) for t in s.tombstones if t["version"] > since], s.version

    def submit_feedback(self, contribution_id, operation_id, outcome):
        u = self._auth(); s = self.server; row = s.contributions.get(contribution_id)
        if row is None or not self._visible(row, u): raise Denied("not visible")
        if outcome not in M.FEEDBACK_OUTCOMES: raise Rejected("schema")
        key = (contribution_id, u["id"], str(operation_id))
        if key not in s.feedback: s.feedback[key] = {"contribution_id": contribution_id, "user_id": u["id"], "operation_id": str(operation_id), "outcome": outcome, "created_at": s.clock()}
        return dict(s.feedback[key])

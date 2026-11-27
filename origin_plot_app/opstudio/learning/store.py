"""store.py - the local SQLite database of the learning system (standard library sqlite3 only).

Where:   <private folder>/learning/learning.sqlite3   (private_store.private_dir(); the folder named by the environment
         variable OPS_LEARNING_DIR replaces '<private folder>/learning'). User data: never inside the program folder,
         never in a release archive, never on a shared network drive.

How:     one connection per thread (thread-local; a connection is never handed to another thread), WAL journal where
         the file system allows it, parameterised SQL only, short BEGIN IMMEDIATE transactions - an event and the
         memory change it causes are committed together or not at all. No transaction is ever open during a network call
         (the sync worker reads, closes, talks to the network, then opens a new short transaction).

Schema:  versioned migrations (MIGRATIONS). Before a database that already holds data is migrated, a copy is written
         beside it ('learning.sqlite3.bak-v<old>-<time>'); every migration is idempotent and recorded in
         schema_migrations.

Tables:  schema_migrations, settings, learning_events, memories, memory_revisions, feedback, diagnostics (failures -
         kept apart from reusable memories and never promoted to one), tombstones, sync_outbox, sync_state,
         migration_markers.

Every failure of the database surfaces as StorageUnavailable; the service turns that into the outcome
'storage_unavailable' and the user's analysis goes on.
"""
import contextlib, json, os, sqlite3, threading, time

from . import models as M

DB_NAME = "learning.sqlite3"


class StorageUnavailable(Exception):
    """The learning database cannot be opened, read or written right now."""


def default_dir():
    """The folder of the learning database: $OPS_LEARNING_DIR, else '<private folder>/learning'."""
    d = os.environ.get("OPS_LEARNING_DIR")
    if d: return d
    try:
        import private_store
        base = private_store.private_dir()
    except Exception:
        base = os.environ.get("OPS_PRIVATE_DIR") or os.path.join(os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config"), "OriginPlotStudio", "my_templates")
    return os.path.join(base, "learning")


def default_path(): return os.path.join(default_dir(), DB_NAME)


# ------------------------------------------------------------------------------------------------ schema
def _run(c, script):
    """Execute the statements of a script one by one INSIDE the caller's transaction (executescript would commit it)."""
    import re
    for stmt in re.sub(r"--[^\n]*", "", script).split(";"):
        if stmt.strip(): c.execute(stmt)


def _m1(c):
    _run(c, """
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS memories(
        id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, kind TEXT NOT NULL,
        signature TEXT NOT NULL DEFAULT '', signature_version INTEGER NOT NULL DEFAULT 2, share_signature TEXT NOT NULL DEFAULT '',
        data_family TEXT NOT NULL DEFAULT 'unknown', instrument TEXT NOT NULL DEFAULT '',
        scope TEXT NOT NULL DEFAULT 'personal_format', scope_key TEXT NOT NULL DEFAULT '',
        visibility TEXT NOT NULL DEFAULT 'personal', status TEXT NOT NULL DEFAULT 'personal', owner_id TEXT NOT NULL DEFAULT '', lab_id TEXT NOT NULL DEFAULT '',
        origin TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, needs_revalidation INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1,
        recipe_json TEXT NOT NULL, context_json TEXT NOT NULL DEFAULT '{}', constraints_json TEXT NOT NULL DEFAULT '{}',
        validation_json TEXT NOT NULL DEFAULT '{}', provenance_json TEXT NOT NULL DEFAULT '{}',
        template_id TEXT NOT NULL DEFAULT '', template_version TEXT NOT NULL DEFAULT '', app_version TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        user_confirmations INTEGER NOT NULL DEFAULT 0,      -- distinct explicit confirmations by the user (origin 'user')
        times_applied INTEGER NOT NULL DEFAULT 0,           -- how often it was applied: says nothing about correctness
        times_rejected INTEGER NOT NULL DEFAULT 0,
        remote_id TEXT NOT NULL DEFAULT '', remote_revision INTEGER NOT NULL DEFAULT 0,
        dedup_key TEXT NOT NULL UNIQUE);
    CREATE INDEX IF NOT EXISTS memories_lookup ON memories(kind, signature, data_family, enabled);
    CREATE INDEX IF NOT EXISTS memories_remote ON memories(remote_id);
    CREATE TABLE IF NOT EXISTS memory_revisions(
        memory_id TEXT NOT NULL, revision INTEGER NOT NULL, recipe_json TEXT NOT NULL, prior_recipe_json TEXT,
        meta_json TEXT NOT NULL DEFAULT '{}', provenance_json TEXT NOT NULL DEFAULT '{}', reason TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL, app_version TEXT NOT NULL DEFAULT '', PRIMARY KEY(memory_id, revision));
    CREATE TABLE IF NOT EXISTS learning_events(
        id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, event_type TEXT NOT NULL, target_id TEXT NOT NULL, origin TEXT NOT NULL,
        created_at TEXT NOT NULL, app_version TEXT NOT NULL DEFAULT '', schema_version INTEGER NOT NULL DEFAULT 1,
        context_json TEXT NOT NULL DEFAULT '{}', before_json TEXT NOT NULL DEFAULT '{}', after_json TEXT NOT NULL DEFAULT '{}',
        validation_json TEXT NOT NULL DEFAULT '{}', remember INTEGER NOT NULL DEFAULT 0, scope TEXT NOT NULL DEFAULT '',
        memory_id TEXT, memory_revision INTEGER, effect TEXT NOT NULL DEFAULT '',
        UNIQUE(operation_id, event_type, target_id));
    CREATE INDEX IF NOT EXISTS events_memory ON learning_events(memory_id);
    CREATE TABLE IF NOT EXISTS feedback(
        id TEXT PRIMARY KEY, memory_id TEXT NOT NULL, revision INTEGER NOT NULL, operation_id TEXT NOT NULL, outcome TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT '', origin TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0,
        UNIQUE(memory_id, operation_id));
    CREATE TABLE IF NOT EXISTS diagnostics(
        id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, event_type TEXT NOT NULL, target_id TEXT NOT NULL, error_class TEXT NOT NULL DEFAULT '',
        data_family TEXT NOT NULL DEFAULT 'unknown', signature TEXT NOT NULL DEFAULT '', signature_version INTEGER NOT NULL DEFAULT 2,
        template_id TEXT NOT NULL DEFAULT '', app_version TEXT NOT NULL DEFAULT '', detail_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
        UNIQUE(operation_id, event_type, target_id));
    CREATE TABLE IF NOT EXISTS tombstones(
        memory_id TEXT PRIMARY KEY, remote_id TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 0, deleted_at TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '');
    CREATE INDEX IF NOT EXISTS tombstones_remote ON tombstones(remote_id);
    CREATE TABLE IF NOT EXISTS sync_outbox(
        id TEXT PRIMARY KEY, memory_id TEXT NOT NULL, memory_revision INTEGER NOT NULL DEFAULT 0, action TEXT NOT NULL, scope TEXT NOT NULL DEFAULT '',
        lab_id TEXT NOT NULL DEFAULT '', contribution_id TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}', state TEXT NOT NULL DEFAULT 'queued',
        attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at REAL NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(contribution_id, action, memory_revision));
    CREATE TABLE IF NOT EXISTS sync_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS migration_markers(
        source TEXT NOT NULL, entry_key TEXT NOT NULL, memory_id TEXT NOT NULL DEFAULT '', imported_at TEXT NOT NULL, PRIMARY KEY(source, entry_key));
    """)


MIGRATIONS = [(1, _m1)]                 # (version, function(connection)); append, never edit a released one

_MEM_JSON = ("recipe", "context", "constraints", "validation", "provenance")


def _j(v): return M.canonical_json(v if v is not None else {})


def _load(text, default=None):
    try: return json.loads(text) if text else (default if default is not None else {})
    except Exception: return default if default is not None else {}


def mem_row(row):
    """A memories row as the plain dict the rest of the package works with (JSON columns decoded)."""
    d = dict(row)
    for k in _MEM_JSON: d[k] = _load(d.pop(k + "_json", ""))
    d["enabled"] = bool(d.get("enabled")); d["needs_revalidation"] = bool(d.get("needs_revalidation"))
    return d


def event_row(row):
    d = dict(row)
    for k in ("context", "before", "after", "validation"): d[k] = _load(d.pop(k + "_json", ""))
    d["remember"] = bool(d.get("remember"))
    return d


class Store:
    def __init__(self, path=None, *, app_version="", clock=None, timeout=5.0):
        self.path = os.path.abspath(path or default_path()); self.app_version = str(app_version or ""); self.clock = clock or time.time
        self.timeout = float(timeout); self._local = threading.local(); self._lock = threading.RLock(); self._migrated = False
        self._all = []; self.last_backup = ""

    def now(self): return M.now_iso(self.clock)

    # -------------------------------------------------------------------------------------------- connections
    def _conn(self):
        c = getattr(self._local, "conn", None)
        if c is not None: return c
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            c = sqlite3.connect(self.path, timeout=self.timeout, isolation_level=None, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute(f"PRAGMA busy_timeout={int(self.timeout * 1000)}")
            try: c.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error: pass                       # a file system without shared memory: the default journal is fine
            c.execute("PRAGMA foreign_keys=ON")
            with self._lock:
                if not self._migrated: self._migrate(c); self._migrated = True
                self._all.append(c)
        except (sqlite3.Error, OSError) as e:
            try:
                if c is not None: c.close()
            except Exception: pass
            raise StorageUnavailable(f"{type(e).__name__}") from e
        self._local.conn = c
        return c

    def _migrate(self, c):
        c.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, app_version TEXT NOT NULL DEFAULT '')")
        done = {r[0] for r in c.execute("SELECT version FROM schema_migrations")}
        pending = [(v, fn) for v, fn in sorted(MIGRATIONS, key=lambda m: m[0]) if v not in done]
        if not pending: return
        if done:                                             # a database that already holds a schema: keep a copy before changing it
            self.last_backup = f"{self.path}.bak-v{max(done)}-{time.strftime('%Y%m%d%H%M%S', time.gmtime(self.clock()))}"
            b = sqlite3.connect(self.last_backup)
            try:
                c.backup(b)
                try: b.execute("PRAGMA journal_mode=DELETE")          # the copy is one self-contained file
                except sqlite3.Error: pass
            finally: b.close()
        for v, fn in pending:
            c.execute("BEGIN IMMEDIATE")
            try:
                fn(c)
                c.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at, app_version) VALUES (?,?,?)", (v, self.now(), self.app_version))
                c.execute("COMMIT")
            except BaseException:
                try: c.execute("ROLLBACK")
                except sqlite3.Error: pass
                raise

    def schema_version(self):
        r = self.q("SELECT MAX(version) AS v FROM schema_migrations")
        return int(r[0]["v"] or 0) if r else 0

    def close(self):
        """Close the connection of the calling thread."""
        c = getattr(self._local, "conn", None)
        if c is not None:
            try: c.close()
            except Exception: pass
            self._local.conn = None
            with self._lock:
                if c in self._all: self._all.remove(c)

    def close_all(self):
        """Close every connection this store opened (app exit, tests). Threads reopen on their next use."""
        with self._lock:
            conns, self._all = self._all, []
        for c in conns:
            try: c.close()
            except Exception: pass
        self._local = threading.local()

    @contextlib.contextmanager
    def tx(self):
        """A short write transaction. Any database error rolls back and is raised as StorageUnavailable."""
        c = self._conn()
        try: c.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as e: raise StorageUnavailable(type(e).__name__) from e
        try:
            yield c
            c.execute("COMMIT")
        except (sqlite3.Error, OSError) as e:
            try: c.execute("ROLLBACK")
            except sqlite3.Error: pass
            raise StorageUnavailable(type(e).__name__) from e
        except BaseException:
            try: c.execute("ROLLBACK")
            except sqlite3.Error: pass
            raise

    def q(self, sql, params=()):
        try: return [dict(r) for r in self._conn().execute(sql, params).fetchall()]
        except sqlite3.Error as e: raise StorageUnavailable(type(e).__name__) from e

    def available(self):
        try: self.q("SELECT 1"); return True
        except StorageUnavailable: return False

    # -------------------------------------------------------------------------------------------- settings / sync state
    def setting(self, key, default=None):
        r = self.q("SELECT value FROM settings WHERE key=?", (key,))
        return _load(r[0]["value"], default) if r else default

    def set_setting(self, key, value):
        with self.tx() as c: c.execute("INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def state(self, key, default=None):
        r = self.q("SELECT value FROM sync_state WHERE key=?", (key,))
        return _load(r[0]["value"], default) if r else default

    def set_state(self, key, value):
        with self.tx() as c: c.execute("INSERT INTO sync_state(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    # -------------------------------------------------------------------------------------------- events and memories
    def _add_event(self, c, ev):
        cur = c.execute("INSERT OR IGNORE INTO learning_events(id, operation_id, event_type, target_id, origin, created_at, app_version, schema_version,"
                        " context_json, before_json, after_json, validation_json, remember, scope, memory_id, memory_revision, effect) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (ev.get("id") or M.new_id(), ev["operation_id"], ev["event_type"], ev["target_id"], ev["origin"], self.now(), self.app_version, M.SCHEMA_VERSION,
                         _j(ev.get("context")), _j(ev.get("before")), _j(ev.get("after")), _j(ev.get("validation")), int(bool(ev.get("remember"))),
                         ev.get("scope") or "", ev.get("memory_id"), ev.get("memory_revision"), ev.get("effect") or ""))
        return cur.rowcount == 1

    def _meta(self, m):
        return {k: m.get(k) for k in ("context", "constraints", "validation", "template_id", "template_version", "data_family", "instrument", "signature",
                                      "signature_version", "share_signature")}

    def _insert_memory(self, c, mid, m, *, reason, confirmations=0):
        now = self.now()
        c.execute("INSERT INTO memories(id, schema_version, kind, signature, signature_version, share_signature, data_family, instrument, scope, scope_key, visibility,"
                  " status, owner_id, lab_id, origin, enabled, needs_revalidation, revision, recipe_json, context_json, constraints_json, validation_json, provenance_json,"
                  " template_id, template_version, app_version, created_at, updated_at, user_confirmations, remote_id, remote_revision, dedup_key)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (mid, M.SCHEMA_VERSION, m["kind"], m.get("signature") or "", int(m.get("signature_version") or 2), m.get("share_signature") or "",
                   m.get("data_family") or "unknown", m.get("instrument") or "", m.get("scope") or "personal_format", m.get("scope_key") or "",
                   m.get("visibility") or "personal", m.get("status") or "personal", m.get("owner_id") or "", m.get("lab_id") or "", m["origin"],
                   int(m.get("enabled", True)), int(bool(m.get("needs_revalidation"))), int(m.get("revision") or 1), _j(m["recipe"]), _j(m.get("context")),
                   _j(m.get("constraints")), _j(m.get("validation")), _j(m.get("provenance")), m.get("template_id") or "", m.get("template_version") or "",
                   m.get("app_version") or self.app_version, m.get("created_at") or now, now, int(confirmations), m.get("remote_id") or "",
                   int(m.get("remote_revision") or 0), m["dedup_key"]))
        c.execute("INSERT INTO memory_revisions(memory_id, revision, recipe_json, prior_recipe_json, meta_json, provenance_json, reason, created_at, app_version)"
                  " VALUES (?,?,?,?,?,?,?,?,?)", (mid, int(m.get("revision") or 1), _j(m["recipe"]), None, _j(self._meta(m)), _j(m.get("provenance")), reason, now, self.app_version))

    def _revise_memory(self, c, row, m, *, reason, confirmations=None):
        """A new revision of an existing memory row: the prior recipe is kept in memory_revisions."""
        rev = int(row["revision"]) + 1; now = self.now()
        merged = {**mem_row(row), **{k: v for k, v in m.items() if v is not None}}
        c.execute("INSERT OR REPLACE INTO memory_revisions(memory_id, revision, recipe_json, prior_recipe_json, meta_json, provenance_json, reason, created_at, app_version)"
                  " VALUES (?,?,?,?,?,?,?,?,?)", (row["id"], rev, _j(merged["recipe"]), row["recipe_json"], _j(self._meta(merged)), _j(merged.get("provenance")), reason, now, self.app_version))
        c.execute("UPDATE memories SET revision=?, recipe_json=?, context_json=?, constraints_json=?, validation_json=?, provenance_json=?, template_id=?, template_version=?,"
                  " data_family=?, instrument=?, signature=?, signature_version=?, share_signature=?, updated_at=?, app_version=?, needs_revalidation=?,"
                  " user_confirmations=COALESCE(?, user_confirmations), remote_revision=COALESCE(?, remote_revision) WHERE id=?",
                  (rev, _j(merged["recipe"]), _j(merged.get("context")), _j(merged.get("constraints")), _j(merged.get("validation")), _j(merged.get("provenance")),
                   merged.get("template_id") or "", merged.get("template_version") or "", merged.get("data_family") or "unknown", merged.get("instrument") or "",
                   merged.get("signature") or "", int(merged.get("signature_version") or 2), merged.get("share_signature") or "", now, self.app_version,
                   int(bool(m.get("needs_revalidation"))), confirmations, m.get("remote_revision"), row["id"]))
        return rev

    def record_confirmation(self, ev, mem):
        """ONE transaction: the confirmed event, and (when mem is given) the memory it creates, revises or confirms.
        Returns {'outcome', 'event_id', 'memory_id', 'revision', 'effect'}. The same (operation_id, event_type,
        target_id) a second time changes nothing and returns 'already_saved' with what was stored the first time."""
        ev = dict(ev); ev["id"] = ev.get("id") or M.new_id()
        with self.tx() as c:
            if not self._add_event(c, ev):
                r = c.execute("SELECT id, memory_id, memory_revision, effect FROM learning_events WHERE operation_id=? AND event_type=? AND target_id=?",
                              (ev["operation_id"], ev["event_type"], ev["target_id"])).fetchone()
                return {"outcome": M.Outcome.ALREADY_SAVED, "event_id": r["id"], "memory_id": r["memory_id"] or "", "revision": int(r["memory_revision"] or 0), "effect": r["effect"]}
            mid, rev, effect = "", 0, ""
            if mem is not None:
                row = c.execute("SELECT * FROM memories WHERE dedup_key=?", (mem["dedup_key"],)).fetchone()
                if row is None:
                    mid = M.new_id(); rev = 1; effect = "created"
                    self._insert_memory(c, mid, mem, reason=ev["event_type"], confirmations=1)
                elif row["recipe_json"] == _j(mem["recipe"]):
                    mid = row["id"]; rev = int(row["revision"]); effect = "confirmed"
                    c.execute("UPDATE memories SET user_confirmations=user_confirmations+1, updated_at=?, enabled=1, validation_json=? WHERE id=?", (self.now(), _j(mem.get("validation")), mid))
                else:
                    mid = row["id"]; effect = "revised"
                    rev = self._revise_memory(c, row, mem, reason=ev["event_type"], confirmations=1)
                    c.execute("UPDATE memories SET enabled=1 WHERE id=?", (mid,))          # the user just chose to remember it again
                c.execute("UPDATE learning_events SET memory_id=?, memory_revision=?, effect=? WHERE id=?", (mid, rev, effect, ev["id"]))
            return {"outcome": M.Outcome.SAVED, "event_id": ev["id"], "memory_id": mid, "revision": rev, "effect": effect}

    def undo_saving(self, event_id):
        """Reverse what one confirmed event did to the memory store (not the user's graph or workbook):
        'created' -> the memory is removed; 'revised' -> the previous revision is restored; 'confirmed' -> the
        confirmation is taken back. Returns (outcome, memory_id)."""
        with self.tx() as c:
            ev = c.execute("SELECT * FROM learning_events WHERE id=?", (event_id,)).fetchone()
            if ev is None: return M.Outcome.NOT_FOUND, ""
            mid = ev["memory_id"] or ""; effect = ev["effect"]
            row = c.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone() if mid else None
            if row is not None:
                if effect in ("created", "revised") and int(row["revision"]) != int(ev["memory_revision"] or 0): return M.Outcome.NOT_PERMITTED, mid      # revised again since
                if effect == "created":
                    self._delete_memory(c, row, reason="undo_saving", keep_events_of=None)
                elif effect == "revised":
                    prev = c.execute("SELECT * FROM memory_revisions WHERE memory_id=? AND revision=?", (mid, int(row["revision"]) - 1)).fetchone()
                    if prev is None: return M.Outcome.NOT_PERMITTED, mid
                    meta = _load(prev["meta_json"])
                    c.execute("UPDATE memories SET revision=?, recipe_json=?, context_json=?, constraints_json=?, validation_json=?, template_id=?, template_version=?,"
                              " data_family=?, instrument=?, signature=?, signature_version=?, share_signature=?, updated_at=? WHERE id=?",
                              (int(prev["revision"]), prev["recipe_json"], _j(meta.get("context")), _j(meta.get("constraints")), _j(meta.get("validation")),
                               meta.get("template_id") or "", meta.get("template_version") or "", meta.get("data_family") or "unknown", meta.get("instrument") or "",
                               meta.get("signature") or "", int(meta.get("signature_version") or 2), meta.get("share_signature") or "", self.now(), mid))
                    c.execute("DELETE FROM memory_revisions WHERE memory_id=? AND revision=?", (mid, int(row["revision"])))
                    c.execute("DELETE FROM sync_outbox WHERE memory_id=? AND memory_revision=? AND state IN ('queued','failed')", (mid, int(row["revision"])))
                elif effect == "confirmed":
                    c.execute("UPDATE memories SET user_confirmations=MAX(user_confirmations-1, 0), updated_at=? WHERE id=?", (self.now(), mid))
            c.execute("DELETE FROM learning_events WHERE id=?", (event_id,))
            return M.Outcome.SAVED, mid

    def _delete_memory(self, c, row, *, reason, keep_events_of=None):
        """Remove a memory and its local detail; write the tombstone when a remote copy may exist or a retry is queued."""
        mid = row["id"]
        out = c.execute("SELECT contribution_id, state, action FROM sync_outbox WHERE memory_id=?", (mid,)).fetchall()
        remote = row["remote_id"] or next((o["contribution_id"] for o in out if o["action"] == "submit"), "")
        sent = bool(row["remote_id"]) or any(o["action"] == "submit" and o["state"] in ("sent", "conflict") for o in out)
        c.execute("DELETE FROM sync_outbox WHERE memory_id=? AND action='submit'", (mid,))
        c.execute("DELETE FROM memory_revisions WHERE memory_id=?", (mid,))
        c.execute("DELETE FROM feedback WHERE memory_id=?", (mid,))
        c.execute("DELETE FROM learning_events WHERE memory_id=?", (mid,))
        # migration_markers stay on purpose: a forgotten legacy entry is not imported again by the next migration run
        c.execute("DELETE FROM memories WHERE id=?", (mid,))
        if remote or out or reason == "forgotten":
            v = c.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM tombstones").fetchone()[0]
            c.execute("INSERT OR REPLACE INTO tombstones(memory_id, remote_id, version, deleted_at, reason) VALUES (?,?,?,?,?)", (mid, remote, int(v), self.now(), reason))
        return remote, sent

    def forget_memory(self, memory_id, shared_action=None):
        """Remove the reusable memory with its revisions, feedback and events. What stays: one tombstone (ids and a time,
        nothing else) so that neither a queued upload nor a later download can bring it back, and one 'memory_forgotten'
        event without content. shared_action='withdraw' additionally queues the withdrawal of a contribution that was
        already sent. Returns (outcome, detail)."""
        with self.tx() as c:
            row = c.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                t = c.execute("SELECT 1 FROM tombstones WHERE memory_id=?", (memory_id,)).fetchone()
                return (M.Outcome.ALREADY_SAVED if t else M.Outcome.NOT_FOUND), {}
            own = row["visibility"] == "personal"
            remote, sent = self._delete_memory(c, row, reason="forgotten")
            queued = False
            if shared_action == "withdraw" and own and remote and sent:
                c.execute("INSERT OR IGNORE INTO sync_outbox(id, memory_id, memory_revision, action, scope, contribution_id, payload_json, state, created_at, updated_at)"
                          " VALUES (?,?,?,?,?,?,?,?,?,?)", (M.new_id(), memory_id, 0, "withdraw", "", remote, _j({"contribution_id": remote}), "queued", self.now(), self.now()))
                queued = True
            self._add_event(c, {"operation_id": M.new_id(), "event_type": "memory_forgotten", "target_id": memory_id, "origin": "user"})
            return M.Outcome.SAVED, {"remote_copy": bool(remote and sent), "withdrawal_queued": queued, "contribution_id": remote if (remote and sent) else ""}

    def set_enabled(self, memory_id, flag, operation_id):
        with self.tx() as c:
            row = c.execute("SELECT enabled FROM memories WHERE id=?", (memory_id,)).fetchone()
            if row is None: return M.Outcome.NOT_FOUND
            if bool(row["enabled"]) == bool(flag): return M.Outcome.ALREADY_SAVED
            c.execute("UPDATE memories SET enabled=?, updated_at=? WHERE id=?", (int(bool(flag)), self.now(), memory_id))
            self._add_event(c, {"operation_id": operation_id, "event_type": "memory_enabled" if flag else "memory_disabled", "target_id": memory_id, "origin": "user", "memory_id": memory_id})
            return M.Outcome.SAVED

    def edit_memory(self, memory_id, recipe, reason, operation_id, extra=None):
        """A user edit: always a new revision (the prior recipe stays in memory_revisions). Returns (outcome, revision)."""
        with self.tx() as c:
            row = c.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
            if row is None: return M.Outcome.NOT_FOUND, 0
            if row["recipe_json"] == _j(recipe): return M.Outcome.ALREADY_SAVED, int(row["revision"])
            m = {"recipe": recipe}; m.update(extra or {})
            rev = self._revise_memory(c, row, m, reason=reason)
            c.execute("DELETE FROM sync_outbox WHERE memory_id=? AND action='submit' AND state IN ('queued','failed')", (memory_id,))      # what was previewed is no longer what is stored
            self._add_event(c, {"operation_id": operation_id, "event_type": "memory_edited", "target_id": memory_id, "origin": "user", "memory_id": memory_id, "memory_revision": rev, "effect": "revised"})
            return M.Outcome.SAVED, rev

    def add_feedback(self, memory_id, revision, operation_id, outcome, reason, origin):
        """One explicit outcome per (memory, operation). An acceptance raises times_applied; it never touches
        user_confirmations. Returns outcome word."""
        with self.tx() as c:
            row = c.execute("SELECT id, revision FROM memories WHERE id=?", (memory_id,)).fetchone()
            if row is None: return M.Outcome.NOT_FOUND
            cur = c.execute("INSERT OR IGNORE INTO feedback(id, memory_id, revision, operation_id, outcome, reason, origin, created_at) VALUES (?,?,?,?,?,?,?,?)",
                            (M.new_id(), memory_id, int(revision), operation_id, outcome, reason or "", origin, self.now()))
            if cur.rowcount != 1: return M.Outcome.ALREADY_SAVED
            col = "times_applied" if outcome == "accepted" else "times_rejected"
            c.execute(f"UPDATE memories SET {col}={col}+1 WHERE id=?", (memory_id,))
            self._add_event(c, {"operation_id": operation_id, "event_type": "suggestion_" + outcome, "target_id": memory_id, "origin": origin,
                                "memory_id": memory_id, "memory_revision": int(revision)})
            return M.Outcome.SAVED

    def add_diagnostic(self, d):
        """A failure or an unremembered correction, kept apart from memories. Deduplicated by (operation, type, target)."""
        with self.tx() as c:
            cur = c.execute("INSERT OR IGNORE INTO diagnostics(id, operation_id, event_type, target_id, error_class, data_family, signature, signature_version, template_id,"
                            " app_version, detail_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (M.new_id(), d["operation_id"], d["event_type"], d["target_id"], d.get("error_class") or "", d.get("data_family") or "unknown",
                             d.get("signature") or "", int(d.get("signature_version") or 2), d.get("template_id") or "", self.app_version, _j(d.get("detail")), self.now()))
            return M.Outcome.SAVED if cur.rowcount == 1 else M.Outcome.ALREADY_SAVED

    def put_memory(self, m, *, reason):
        """Insert a memory that did not come from a confirmation (import, download, migration), or revise the one with
        the same dedup_key when the recipe or the remote revision differs. Returns (effect, memory_id, revision);
        effect is 'created', 'revised', 'unchanged' or 'tombstoned'."""
        with self.tx() as c: return self._put_memory(c, m, reason=reason)

    def _put_memory(self, c, m, *, reason):
        if m.get("remote_id") and c.execute("SELECT 1 FROM tombstones WHERE remote_id=?", (m["remote_id"],)).fetchone(): return "tombstoned", "", 0
        if m.get("id") and c.execute("SELECT 1 FROM tombstones WHERE memory_id=?", (m["id"],)).fetchone(): return "tombstoned", "", 0
        row = c.execute("SELECT * FROM memories WHERE dedup_key=?", (m["dedup_key"],)).fetchone()
        if row is None:
            mid = m.get("id") or M.new_id()
            if c.execute("SELECT 1 FROM memories WHERE id=?", (mid,)).fetchone(): mid = M.new_id()
            self._insert_memory(c, mid, m, reason=reason, confirmations=int(m.get("user_confirmations") or 0))
            return "created", mid, int(m.get("revision") or 1)
        if row["recipe_json"] == _j(m["recipe"]) and int(row["remote_revision"]) >= int(m.get("remote_revision") or 0):
            if m.get("status") and m["status"] != row["status"]: c.execute("UPDATE memories SET status=? WHERE id=?", (m["status"], row["id"]))
            return "unchanged", row["id"], int(row["revision"])
        return "revised", row["id"], self._revise_memory(c, row, m, reason=reason)

    def import_legacy(self, source, entries):
        """ONE transaction for all entries of one legacy file: (entry_key, memory dict). An entry whose marker exists
        is skipped. Returns (imported, skipped)."""
        done = skipped = 0
        with self.tx() as c:
            for key, m in entries:
                if c.execute("SELECT 1 FROM migration_markers WHERE source=? AND entry_key=?", (source, key)).fetchone(): skipped += 1; continue
                effect, mid, rev = self._put_memory(c, m, reason="legacy_imported")
                c.execute("INSERT INTO migration_markers(source, entry_key, memory_id, imported_at) VALUES (?,?,?,?)", (source, key, mid, self.now()))
                if effect in ("created", "revised"):
                    self._add_event(c, {"operation_id": f"migrate:{source}:{key}", "event_type": "legacy_imported", "target_id": key, "origin": "migration",
                                        "memory_id": mid, "memory_revision": rev, "effect": effect, "validation": {"structural_checks_passed": None, "user_confirmed": None}})
                    done += 1
                else: skipped += 1
        return done, skipped

    # -------------------------------------------------------------------------------------------- reading
    def memory(self, memory_id):
        r = self._rows("SELECT * FROM memories WHERE id=?", (memory_id,))
        return mem_row(r[0]) if r else None

    def _rows(self, sql, params=()):
        try: return self._conn().execute(sql, params).fetchall()
        except sqlite3.Error as e: raise StorageUnavailable(type(e).__name__) from e

    def memories(self, *, kinds=None, enabled=None, family=None, visibility=None, limit=2000):
        sql = "SELECT * FROM memories WHERE 1=1"; p = []
        if kinds: sql += " AND kind IN (%s)" % ",".join("?" * len(kinds)); p += list(kinds)
        if enabled is not None: sql += " AND enabled=?"; p.append(int(bool(enabled)))
        if family: sql += " AND data_family=?"; p.append(family)
        if visibility: sql += " AND visibility=?"; p.append(visibility)
        sql += " ORDER BY updated_at DESC, id LIMIT ?"; p.append(int(limit))
        return [mem_row(r) for r in self._rows(sql, p)]

    def revisions(self, memory_id):
        out = []
        for r in self._rows("SELECT * FROM memory_revisions WHERE memory_id=? ORDER BY revision", (memory_id,)):
            d = dict(r); d["recipe"] = _load(d.pop("recipe_json")); pr = d.pop("prior_recipe_json"); d["prior_recipe"] = _load(pr) if pr else None
            d["meta"] = _load(d.pop("meta_json")); d["provenance"] = _load(d.pop("provenance_json")); out.append(d)
        return out

    def events(self, *, memory_id=None, event_types=None, origin=None, since=None, limit=1000):
        sql = "SELECT * FROM learning_events WHERE 1=1"; p = []
        if memory_id: sql += " AND memory_id=?"; p.append(memory_id)
        if event_types: sql += " AND event_type IN (%s)" % ",".join("?" * len(event_types)); p += list(event_types)
        if origin: sql += " AND origin=?"; p.append(origin)
        if since: sql += " AND created_at>=?"; p.append(since)
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"; p.append(int(limit))
        return [event_row(r) for r in self._rows(sql, p)]

    def feedback(self, memory_id=None, unsynced=False):
        sql = "SELECT * FROM feedback WHERE 1=1"; p = []
        if memory_id: sql += " AND memory_id=?"; p.append(memory_id)
        if unsynced: sql += " AND synced=0"
        return [dict(r) for r in self._rows(sql + " ORDER BY created_at, rowid", p)]

    def diagnostics(self): return [dict(r, detail=_load(r["detail_json"])) for r in self._rows("SELECT * FROM diagnostics ORDER BY created_at, rowid")]

    def flag_revalidation(self, memory_id, flag=True):
        with self.tx() as c: c.execute("UPDATE memories SET needs_revalidation=? WHERE id=? AND needs_revalidation<>?", (int(flag), memory_id, int(flag)))

    # -------------------------------------------------------------------------------------------- sync outbox, tombstones
    def tombstoned(self, memory_id=None, remote_id=None):
        if memory_id and self._rows("SELECT 1 FROM tombstones WHERE memory_id=?", (memory_id,)): return True
        return bool(remote_id and self._rows("SELECT 1 FROM tombstones WHERE remote_id=?", (remote_id,)))

    def tombstones(self): return [dict(r) for r in self._rows("SELECT * FROM tombstones ORDER BY version")]

    def queue_submit(self, memory_id, revision, contribution_id, scope, lab_id, payload):
        """Queue a previewed, consented contribution. The memory must exist and must not be tombstoned. Idempotent."""
        with self.tx() as c:
            if c.execute("SELECT 1 FROM tombstones WHERE memory_id=?", (memory_id,)).fetchone(): return M.Outcome.NOT_FOUND
            if c.execute("SELECT 1 FROM memories WHERE id=?", (memory_id,)).fetchone() is None: return M.Outcome.NOT_FOUND
            cur = c.execute("INSERT OR IGNORE INTO sync_outbox(id, memory_id, memory_revision, action, scope, lab_id, contribution_id, payload_json, state, created_at, updated_at)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?)", (M.new_id(), memory_id, int(revision), "submit", scope, lab_id or "", contribution_id, _j(payload), "queued", self.now(), self.now()))
            if cur.rowcount != 1: return M.Outcome.ALREADY_SAVED
            c.execute("UPDATE memories SET status='pending' WHERE id=? AND status IN ('personal','rejected','revoked')", (memory_id,))
            return M.Outcome.SAVED

    def queue_withdraw(self, memory_id, contribution_id):
        with self.tx() as c:
            c.execute("DELETE FROM sync_outbox WHERE memory_id=? AND action='submit' AND state IN ('queued','failed')", (memory_id,))
            cur = c.execute("INSERT OR IGNORE INTO sync_outbox(id, memory_id, memory_revision, action, scope, contribution_id, payload_json, state, created_at, updated_at)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?)", (M.new_id(), memory_id, 0, "withdraw", "", contribution_id, _j({"contribution_id": contribution_id}), "queued", self.now(), self.now()))
            return M.Outcome.SAVED if cur.rowcount == 1 else M.Outcome.ALREADY_SAVED

    def outbox(self, states=None, memory_id=None):
        sql = "SELECT * FROM sync_outbox WHERE 1=1"; p = []
        if states: sql += " AND state IN (%s)" % ",".join("?" * len(states)); p += list(states)
        if memory_id: sql += " AND memory_id=?"; p.append(memory_id)
        return [dict(r, payload=_load(r["payload_json"])) for r in self._rows(sql + " ORDER BY created_at, rowid", p)]

    def update_outbox(self, row_id, **fields):
        allowed = {"state", "attempts", "next_attempt_at", "last_error"}
        sets = [k for k in fields if k in allowed]
        if not sets: return
        with self.tx() as c:
            c.execute("UPDATE sync_outbox SET " + ", ".join(f"{k}=?" for k in sets) + ", updated_at=? WHERE id=?", [fields[k] for k in sets] + [self.now(), row_id])

    def cancel_queued(self, memory_id=None):
        """Remove contributions that are queued but not yet sent (all, or those of one memory). Returns how many."""
        with self.tx() as c:
            sql = "SELECT id, memory_id FROM sync_outbox WHERE action='submit' AND state IN ('queued','failed')" + (" AND memory_id=?" if memory_id else "")
            rows = c.execute(sql, (memory_id,) if memory_id else ()).fetchall()
            for r in rows:
                c.execute("DELETE FROM sync_outbox WHERE id=?", (r["id"],))
                c.execute("UPDATE memories SET status='personal' WHERE id=? AND status='pending' AND remote_id=''", (r["memory_id"],))
            return len(rows)

    def mark_sent(self, row, status, remote_revision):
        """After a successful upload: one short transaction. If the memory was forgotten while the request was on its
        way, the upload is answered with a withdrawal instead of a link. Returns 'sent' or 'withdrawn'."""
        with self.tx() as c:
            gone = c.execute("SELECT 1 FROM tombstones WHERE memory_id=?", (row["memory_id"],)).fetchone() is not None
            if gone:
                c.execute("DELETE FROM sync_outbox WHERE id=?", (row["id"],))
                c.execute("INSERT OR IGNORE INTO sync_outbox(id, memory_id, memory_revision, action, scope, contribution_id, payload_json, state, created_at, updated_at)"
                          " VALUES (?,?,?,?,?,?,?,?,?,?)", (M.new_id(), row["memory_id"], 0, "withdraw", "", row["contribution_id"], _j({"contribution_id": row["contribution_id"]}), "queued", self.now(), self.now()))
                c.execute("UPDATE tombstones SET remote_id=? WHERE memory_id=?", (row["contribution_id"], row["memory_id"]))
                return "withdrawn"
            c.execute("UPDATE sync_outbox SET state='sent', last_error='', updated_at=? WHERE id=?", (self.now(), row["id"]))
            c.execute("UPDATE memories SET remote_id=?, remote_revision=?, status=? WHERE id=?", (row["contribution_id"], int(remote_revision or 0), status or "pending", row["memory_id"]))
            return "sent"

    def apply_remote_tombstone(self, contribution_id, version):
        """A contribution was revoked or deleted remotely: a downloaded copy is removed; an own memory stays (it is the
        user's) and is marked 'revoked'. Returns 'removed', 'revoked' or 'none'."""
        with self.tx() as c:
            row = c.execute("SELECT * FROM memories WHERE remote_id=?", (contribution_id,)).fetchone()
            if row is None: return "none"
            if row["visibility"] == "personal":
                c.execute("UPDATE memories SET status='revoked' WHERE id=?", (row["id"],)); return "revoked"
            for t in ("memory_revisions", "feedback", "learning_events"): c.execute(f"DELETE FROM {t} WHERE memory_id=?", (row["id"],))
            c.execute("DELETE FROM memories WHERE id=?", (row["id"],))
            c.execute("INSERT OR REPLACE INTO tombstones(memory_id, remote_id, version, deleted_at, reason) VALUES (?,?,?,?,?)", (row["id"], contribution_id, int(version or 0), self.now(), "remote"))
            return "removed"

    def mark_feedback_synced(self, feedback_id):
        with self.tx() as c: c.execute("UPDATE feedback SET synced=1 WHERE id=?", (feedback_id,))

"""The cadence gate of the fortnightly improvement cycle: ordinary code that decides whether a cycle is due and keeps
its books. No model takes part in this decision.

The state is one small JSON document (schema "opstudio.cycle/1"). The workflow keeps it on a branch of its own
(`automation-state`, file `cycle_state.json`); see docs/FORTNIGHTLY_CYCLE.md.

    {"schema": "opstudio.cycle/1", "timezone": "Europe/Stockholm", "anchor": "2026-12-10", "time": "06:00",
     "next_due_at": "2026-12-10T06:00:00+01:00", "last_cycle_id": null, "evidence_watermark": null,
     "cycles": {"cycle-2026-12-10": {"status": "running", "started_at": "...", "finished_at": null,
                                     "evidence_watermark": null, "pr_number": null, "report": null}}}

Rules
  * A cycle is due when now >= next_due_at. Its id comes from the scheduled local DATE ("cycle-2026-12-10"), so a run
    that starts five hours or five days late is still the same cycle and a second run of it is recognised.
  * When a cycle ends, next_due_at moves 14 CALENDAR days on at the same local wall-clock time (not 14 x 24 h: the UTC
    offset changes across a daylight-saving switch, the local time does not).
  * A local time that does not exist (spring forward) is moved forward by the length of the gap; a local time that
    exists twice (autumn) means its first occurrence. Both are decided by the code, never by chance.
  * If the scheduler was down for weeks, ONE cycle is resumed (the earliest missed one) and next_due_at then jumps to
    the first slot in the future on the 14-day grid counted from the anchor. There is no burst of catch-up cycles.
  * A cycle that is `running` blocks a second start ("already_running") unless it is older than the timeout: then it
    is retried under the same id. A `failed` cycle is retried on the next check until `max_attempts` is used up.
  * `pr_open` cycles are reported by every check, so the next cycle updates or defers instead of duplicating.
  * `--force` (manual dispatch) runs the scheduled cycle if one is due, otherwise a cycle with an id of its own
    ("cycle-<date>-manual"), which never moves next_due_at.
  * `no_evidence`, `no_change` and `deferred` are ordinary endings. Nothing here ever asks for a version bump or a
    release: every answer carries "version_bump": false.

Run:  python3 tools/cycle_due.py init   --state FILE --anchor 2026-12-10 --time 06:00 --timezone Europe/Stockholm
      python3 tools/cycle_due.py check  --state FILE [--now ISO] [--force]
      python3 tools/cycle_due.py start  --state FILE [--cycle-id ID] [--force] [--run-id N]
      python3 tools/cycle_due.py finish --state FILE --cycle-id ID --status no_change [--pr N] [--report FILE] [--watermark ISO]
      python3 tools/cycle_due.py set-pr --state FILE --cycle-id ID --pr-state merged
Every command prints one JSON object. With GITHUB_OUTPUT set, `check`, `start` and `finish` also write step outputs.
Exit code 0: the command worked (due or not due). 2: the state file is corrupt or the request makes no sense."""
import argparse, copy, json, os, re, sys, tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEMA = "opstudio.cycle/1"
INTERVAL_DAYS = 14
STATUSES = ("pending", "running", "evidence_processed", "pr_open", "published", "no_change", "no_evidence", "deferred", "failed")
IN_PROGRESS = ("running", "evidence_processed")                     # somebody is (or was) working on it
ENDED = ("pr_open", "published", "no_change", "no_evidence", "deferred")   # always final ("published": the scheduled review released the change itself)
WATERMARK_MOVES = ("evidence_processed", "pr_open", "published", "no_change", "no_evidence")   # the evidence was really processed
PR_STATES = ("open", "merged", "closed")
DEFAULT_STALE_MINUTES = 180
DEFAULT_MAX_ATTEMPTS = 3
KEEP_CYCLES = 80
REPORT_MAX_CHARS = 20000
CYCLE_ID = re.compile(r"^cycle-\d{4}-\d{2}-\d{2}(-manual(-\d{1,3})?)?$")


class StateError(Exception):
    """The state file is missing, corrupt, or a request does not fit it."""
    def __init__(self, reason, detail=""):
        super().__init__(f"{reason}: {detail}" if detail else reason); self.reason, self.detail = reason, detail


# ---------------------------------------------------------------- time
def zone(name):
    try: return ZoneInfo(str(name))
    except Exception as e: raise StateError("bad_timezone", f"{name!r} ({type(e).__name__})")


def parse_hhmm(text):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(text or ""))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59: raise StateError("bad_time", repr(text))
    return int(m.group(1)), int(m.group(2))


def parse_date(text):
    try: return date.fromisoformat(str(text))
    except Exception: raise StateError("bad_date", repr(text))


def parse_instant(text, tz=None):
    """An ISO date-time as an aware datetime. Without an offset it is read as local time in `tz` (UTC without `tz`)."""
    try: d = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except Exception: raise StateError("bad_datetime", repr(text))
    return d if d.tzinfo is not None else resolve_local(d.date(), f"{d.hour:02d}:{d.minute:02d}", tz or timezone.utc).replace(second=d.second)


def resolve_local(day, hhmm, tz):
    """The instant of wall-clock time `hhmm` on local date `day`.
    Does not exist (clocks went forward): moved forward by the gap, 02:30 becomes 03:30. Exists twice: the first one."""
    h, m = parse_hhmm(hhmm)
    naive = datetime(day.year, day.month, day.day, h, m)
    first = naive.replace(tzinfo=tz, fold=0)
    back = first.astimezone(timezone.utc).astimezone(tz)
    return back if back.replace(tzinfo=None) != naive else first


def iso(d): return d.isoformat(timespec="seconds")


def slot(state, k):
    """Slot k of the grid: the anchor date plus 14 k calendar days, at the configured local time."""
    return resolve_local(parse_date(state["anchor"]) + timedelta(days=INTERVAL_DAYS * k), state["time"], zone(state["timezone"]))


def slot_after(state, instant):
    """The first slot of the grid (never before the anchor) that lies strictly after `instant`."""
    tz = zone(state["timezone"])
    k = max(0, (instant.astimezone(tz).date() - parse_date(state["anchor"])).days // INTERVAL_DAYS - 1)
    while slot(state, k) <= instant: k += 1
    return slot(state, k)


def cycle_id_for(instant, tz): return "cycle-" + instant.astimezone(tz).date().isoformat()


# ---------------------------------------------------------------- the state document
def new_state(anchor, hhmm, tz_name, now):
    tz = zone(tz_name); parse_hhmm(hhmm); a = parse_date(anchor)
    s = {"schema": SCHEMA, "timezone": str(tz_name), "anchor": a.isoformat(), "time": "%02d:%02d" % parse_hhmm(hhmm), "interval_days": INTERVAL_DAYS,
         "next_due_at": "", "last_cycle_id": None, "evidence_watermark": None, "cycles": {}}
    first = slot(s, 0)
    s["next_due_at"] = iso(first if first > now else slot_after(s, now))     # an anchor in the past starts no cycle at once
    return s


def validate(state):
    if not isinstance(state, dict): raise StateError("state_corrupt", "not a JSON object")
    if state.get("schema") != SCHEMA: raise StateError("state_corrupt", f"schema is {state.get('schema')!r}, expected {SCHEMA!r}")
    for k in ("timezone", "anchor", "time", "next_due_at"):
        if not isinstance(state.get(k), str) or not state[k]: raise StateError("state_corrupt", f"{k} is missing")
    if state.get("interval_days", INTERVAL_DAYS) != INTERVAL_DAYS: raise StateError("state_corrupt", "interval_days must be 14")
    tz = zone(state["timezone"]); parse_date(state["anchor"]); parse_hhmm(state["time"])
    due = parse_instant(state["next_due_at"], tz)
    if not isinstance(state.get("cycles"), dict): raise StateError("state_corrupt", "cycles is not an object")
    for cid, rec in state["cycles"].items():
        if not CYCLE_ID.match(str(cid)) or not isinstance(rec, dict) or rec.get("status") not in STATUSES:
            raise StateError("state_corrupt", f"cycle {cid!r}")
        for k in ("started_at", "finished_at"):
            if rec.get(k): parse_instant(rec[k], tz)
    state.setdefault("last_cycle_id", None); state.setdefault("evidence_watermark", None)
    return due


def load_state(path):
    p = Path(path)
    if not p.is_file(): raise StateError("state_missing", str(path))
    try: state = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e: raise StateError("state_corrupt", f"{type(e).__name__}: {e}")
    try: validate(state)
    except StateError as e: raise StateError("state_corrupt", e.detail if e.reason == "state_corrupt" else f"{e.reason} {e.detail}".strip())
    return state


def save_state(path, state):
    """Written whole or not at all: a temporary file in the same folder, then one rename."""
    validate(state); p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f: f.write(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


# ---------------------------------------------------------------- deciding
def _is_manual(cid): return "-manual" in cid


def _stale(rec, now, tz, stale_minutes):
    if not rec.get("started_at"): return True
    return now - parse_instant(rec["started_at"], tz) >= timedelta(minutes=stale_minutes)


def _retriable(rec, max_attempts): return rec.get("status") == "failed" and int(rec.get("attempts") or 0) < max_attempts and not rec.get("final")


def _over(rec, max_attempts):
    """The cycle on the current slot is finished for good: the slot can be left."""
    return rec is not None and (rec["status"] in ENDED or (rec["status"] == "failed" and not _retriable(rec, max_attempts)))


def settle(state, now, stale_minutes=DEFAULT_STALE_MINUTES, max_attempts=DEFAULT_MAX_ATTEMPTS):
    """A copy of the state with the loose ends tied, without starting anything: a cycle left `running` beyond the
    timeout that has used all its attempts becomes `failed`, and a slot whose cycle is over is left for the next one."""
    s = copy.deepcopy(state); tz = zone(s["timezone"])
    for cid, rec in s["cycles"].items():
        if rec["status"] in IN_PROGRESS and _stale(rec, now, tz, stale_minutes) and int(rec.get("attempts") or 0) >= max_attempts:
            rec.update(status="failed", finished_at=iso(now.astimezone(tz)), final=True, note=f"abandoned: still running after {max_attempts} attempt(s)")
    for _ in range(4):
        due = parse_instant(s["next_due_at"], tz); rec = s["cycles"].get(cycle_id_for(due, tz))
        if not _over(rec, max_attempts): break
        done = parse_instant(rec["finished_at"], tz) if rec.get("finished_at") else due
        s["next_due_at"] = iso(slot_after(s, max(due, done)))
    return s


def _manual_id(s, now, tz, max_attempts):
    base = "cycle-" + now.astimezone(tz).date().isoformat() + "-manual"; n = 1
    while True:
        cid = base if n == 1 else f"{base}-{n}"; rec = s["cycles"].get(cid)
        if rec is None or rec["status"] == "pending" or _retriable(rec, max_attempts): return cid
        n += 1


def check(state, now, force=False, stale_minutes=DEFAULT_STALE_MINUTES, max_attempts=DEFAULT_MAX_ATTEMPTS):
    """Is a cycle due at `now`? Changes nothing. Returns the answer as a dict (see the keys below)."""
    s = settle(state, now, stale_minutes, max_attempts); tz = zone(s["timezone"])
    due_at = parse_instant(s["next_due_at"], tz); scheduled = cycle_id_for(due_at, tz)
    missed = 0                                                       # slots that passed while nothing ran
    if now >= due_at:
        nxt = slot_after(s, due_at)
        while nxt <= now and missed < 1000: missed += 1; nxt = slot_after(s, nxt)
    open_prs = sorted(({"cycle_id": cid, "pr_number": rec.get("pr_number")} for cid, rec in s["cycles"].items()
                       if rec["status"] == "pr_open" and rec.get("pr_state") not in ("merged", "closed")), key=lambda r: r["cycle_id"])
    out = {"due": False, "cycle_id": scheduled, "reason": "not_due", "forced": bool(force), "manual": False, "now": iso(now.astimezone(tz)),
           "timezone": s["timezone"], "next_due_at": s["next_due_at"], "scheduled_for": s["next_due_at"], "missed_slots": missed,
           "open_pr_cycles": open_prs, "attempt": 0, "evidence_watermark": s.get("evidence_watermark"), "version_bump": False, "release": False}

    def answer(due, cid, reason):
        rec = s["cycles"].get(cid) or {}
        out.update(due=due, cycle_id=cid, reason=reason, manual=_is_manual(cid), attempt=int(rec.get("attempts") or 0) + (1 if due else 0))
        if rec.get("scheduled_for"): out["scheduled_for"] = rec["scheduled_for"]
        elif _is_manual(cid): out["scheduled_for"] = out["now"]
        return out

    working = sorted(cid for cid, rec in s["cycles"].items() if rec["status"] in IN_PROGRESS)
    for cid in working:                                              # a cycle in progress comes before everything else
        if not _stale(s["cycles"][cid], now, tz, stale_minutes): return answer(False, cid, "already_running")
    if working: return answer(True, working[0], "retry_stale_running")
    if now >= due_at:
        rec = s["cycles"].get(scheduled)
        if rec is None or rec["status"] == "pending": return answer(True, scheduled, "resumed_after_outage" if missed else "due")
        if _retriable(rec, max_attempts): return answer(True, scheduled, "retry_failed")
        return answer(False, scheduled, "already_finished")           # cannot happen after settle(); kept as a safe answer
    if force: return answer(True, _manual_id(s, now, tz, max_attempts), "forced")
    return answer(False, scheduled, "not_due")


def start(state, now, cycle_id=None, force=False, run_id=None, stale_minutes=DEFAULT_STALE_MINUTES, max_attempts=DEFAULT_MAX_ATTEMPTS):
    """Marks the due cycle as running. Returns (new_state, answer); answer["started"] is False when nothing is due,
    when the cycle is already running, or when `cycle_id` is not the cycle that is due."""
    res = check(state, now, force, stale_minutes, max_attempts)
    if not res["due"]: return state, dict(res, started=False)
    if cycle_id and cycle_id != res["cycle_id"]: return state, dict(res, started=False, due=False, reason="cycle_id_mismatch", requested=cycle_id)
    s = settle(state, now, stale_minutes, max_attempts); tz = zone(s["timezone"]); cid = res["cycle_id"]
    rec = s["cycles"].setdefault(cid, {"status": "pending", "attempts": 0, "evidence_watermark": None, "pr_number": None, "report": None})
    rec.update(status="running", started_at=iso(now.astimezone(tz)), finished_at=None, attempts=int(rec.get("attempts") or 0) + 1,
               scheduled_for=res["scheduled_for"], manual=_is_manual(cid), reason=res["reason"])
    if run_id: rec["run_id"] = str(run_id)[:40]
    s["last_cycle_id"] = cid
    return s, dict(res, started=True)


def finish(state, cycle_id, status, now, pr=None, report=None, watermark=None, max_attempts=DEFAULT_MAX_ATTEMPTS):
    """Records how a cycle ended and, for a cycle of the grid that is over, moves next_due_at to the next slot.
    Returns (new_state, answer). `failed` keeps the slot until `max_attempts` starts were used."""
    if status not in STATUSES or status in ("pending", "running"): raise StateError("bad_status", repr(status))
    s = copy.deepcopy(state); tz = zone(s["timezone"]); rec = s["cycles"].get(cycle_id)
    if rec is None: raise StateError("unknown_cycle", repr(cycle_id))
    base = {"cycle_id": cycle_id, "status": rec["status"], "next_due_at": s["next_due_at"], "version_bump": False, "release": False}
    if rec["status"] in ENDED or (rec["status"] == "failed" and not _retriable(rec, max_attempts)):
        return state, dict(base, finished=False, terminal=True, retry=False, reason="already_finished")
    rec["status"] = status
    if pr is not None: rec["pr_number"] = int(pr); rec.setdefault("pr_state", "open")
    if report is not None: rec["report"] = str(report)
    if watermark and status in WATERMARK_MOVES: rec["evidence_watermark"] = s["evidence_watermark"] = str(watermark)
    retry = status == "failed" and int(rec.get("attempts") or 0) < max_attempts
    terminal = status in ENDED or (status == "failed" and not retry)
    if status != "evidence_processed": rec["finished_at"] = iso(now.astimezone(tz))
    if terminal and status == "failed": rec["final"] = True
    if terminal and not _is_manual(cycle_id):
        due = parse_instant(s["next_due_at"], tz)
        if cycle_id_for(due, tz) == cycle_id: s["next_due_at"] = iso(slot_after(s, max(due, now)))
    _prune(s)
    return s, dict(base, status=status, finished=True, terminal=terminal, retry=retry, next_due_at=s["next_due_at"], reason="recorded",
                   evidence_watermark=s["evidence_watermark"])


def set_pr(state, cycle_id, pr_state, pr=None):
    """Notes what became of a cycle's pull request. This is separate from the cycle's own status on purpose."""
    if pr_state not in PR_STATES: raise StateError("bad_pr_state", repr(pr_state))
    s = copy.deepcopy(state); rec = s["cycles"].get(cycle_id)
    if rec is None: raise StateError("unknown_cycle", repr(cycle_id))
    rec["pr_state"] = pr_state
    if pr is not None: rec["pr_number"] = int(pr)
    return s, {"cycle_id": cycle_id, "pr_state": pr_state, "pr_number": rec.get("pr_number")}


def _prune(s):
    keep = {cid for cid, rec in s["cycles"].items() if rec["status"] in IN_PROGRESS or (rec["status"] == "pr_open" and rec.get("pr_state") not in ("merged", "closed"))}
    rest = sorted((cid for cid in s["cycles"] if cid not in keep), reverse=True)
    for cid in rest[max(0, KEEP_CYCLES - len(keep)):]: del s["cycles"][cid]


# ---------------------------------------------------------------- command line
def _github_output(values):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path: return
    with open(path, "a", encoding="utf-8") as f:
        for k, v in values.items():
            v = ("true" if v else "false") if isinstance(v, bool) else json.dumps(v, separators=(",", ":")) if isinstance(v, (list, dict)) else "" if v is None else str(v)
            f.write(f"{k}={v.replace(chr(10), ' ').replace(chr(13), ' ')}\n")


def _now(args, tz=None): return parse_instant(args.now, tz) if getattr(args, "now", None) else datetime.now(timezone.utc)


def _emit(res, keys):
    print(json.dumps(res, indent=2, sort_keys=True, ensure_ascii=False)); _github_output({k: res.get(k) for k in keys})


def _store_report(state_path, cycle_id, report_file):
    """The report is copied beside the state (reports/<cycle id>.md) and the state keeps its relative path."""
    text = Path(report_file).read_text(encoding="utf-8", errors="replace")[:REPORT_MAX_CHARS]
    rel = Path("reports") / f"{cycle_id}.md"; dest = Path(state_path).parent / rel
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(text, encoding="utf-8", newline="\n")
    return rel.as_posix()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cadence gate of the fortnightly cycle (deterministic; no model involved).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, now=True):
        p.add_argument("--state", required=True, help="the JSON state file")
        if now: p.add_argument("--now", help="ISO date-time to use instead of the clock (for tests and dry runs)")
        p.add_argument("--stale-after-minutes", type=int, default=DEFAULT_STALE_MINUTES); p.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)

    p = sub.add_parser("init"); common(p); p.add_argument("--anchor", required=True); p.add_argument("--time", required=True)
    p.add_argument("--timezone", required=True); p.add_argument("--overwrite", action="store_true")
    p = sub.add_parser("check"); common(p); p.add_argument("--force", action="store_true")
    p = sub.add_parser("start"); common(p); p.add_argument("--force", action="store_true"); p.add_argument("--cycle-id"); p.add_argument("--run-id")
    p = sub.add_parser("finish"); common(p); p.add_argument("--cycle-id", required=True); p.add_argument("--status", required=True, choices=[x for x in STATUSES if x not in ("pending", "running")])
    p.add_argument("--pr", type=int); p.add_argument("--report"); p.add_argument("--watermark")
    p = sub.add_parser("set-pr"); common(p, now=False); p.add_argument("--cycle-id", required=True); p.add_argument("--pr-state", required=True, choices=PR_STATES); p.add_argument("--pr", type=int)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "init":
            if Path(a.state).exists() and not a.overwrite: raise StateError("state_exists", f"{a.state} (use --overwrite to replace it)")
            s = new_state(a.anchor, a.time, a.timezone, _now(a, zone(a.timezone))); save_state(a.state, s)
            _emit({"initialised": True, "next_due_at": s["next_due_at"], "timezone": s["timezone"], "anchor": s["anchor"], "time": s["time"]}, ("next_due_at",)); return 0
        try: state = load_state(a.state)
        except StateError as e:
            if e.reason == "state_missing" and a.cmd in ("check", "start"):          # not set up yet: nothing is due, and that is said
                _emit({"due": False, "started": False, "cycle_id": "", "reason": "state_missing", "detail": e.detail, "open_pr_cycles": [], "version_bump": False, "release": False},
                      ("due", "started", "cycle_id", "reason", "open_pr_cycles")); return 0
            raise
        tz = zone(state["timezone"]); keys = ("due", "cycle_id", "reason", "next_due_at", "scheduled_for", "forced", "manual", "attempt", "open_pr_cycles", "evidence_watermark", "branch")
        if a.cmd == "check":
            res = check(state, _now(a, tz), a.force, a.stale_after_minutes, a.max_attempts); res["branch"] = "cycle/" + res["cycle_id"]; _emit(res, keys); return 0
        if a.cmd == "start":
            s, res = start(state, _now(a, tz), a.cycle_id, a.force, a.run_id, a.stale_after_minutes, a.max_attempts); res["branch"] = "cycle/" + res["cycle_id"]
            if res["started"]: save_state(a.state, s)
            _emit(res, keys + ("started",)); return 0
        if a.cmd == "finish":
            if not CYCLE_ID.match(a.cycle_id): raise StateError("bad_cycle_id", repr(a.cycle_id))
            report = _store_report(a.state, a.cycle_id, a.report) if a.report else None
            s, res = finish(state, a.cycle_id, a.status, _now(a, tz), a.pr, report, a.watermark, a.max_attempts)
            if res["finished"]: save_state(a.state, s)
            _emit(res, ("cycle_id", "status", "finished", "terminal", "retry", "next_due_at", "version_bump")); return 0
        if a.cmd == "set-pr":
            s, res = set_pr(state, a.cycle_id, a.pr_state, a.pr); save_state(a.state, s); _emit(res, ("cycle_id", "pr_state")); return 0
    except StateError as e:
        _emit({"due": False, "started": False, "finished": False, "error": True, "reason": e.reason, "detail": e.detail, "version_bump": False, "release": False}, ("due", "started", "reason")); return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())

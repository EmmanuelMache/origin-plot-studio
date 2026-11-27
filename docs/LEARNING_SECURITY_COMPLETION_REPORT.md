# Learning, updates and security – completion report

Version 5.59.0, developed on the branch `integrate/learning-security` (pull request 3) and based on 5.58.6.
**Released to `main` on 27 November 2026** after the owner left the decision to the developer. The owner's own
copy updates as before. **Still not active:** the fortnightly cycle, shared learning, signed releases.
Requirement-by-requirement status: `docs/LEARNING_SECURITY_TRACKER.md`.

This report covers both workstreams separately. It distinguishes three things throughout:

* **working and tested here** – code plus an automated test in this repository;
* **written but never run against the real thing** – a mock, a fake transport, a workflow file, SQL on plain PostgreSQL;
* **needs the owner** – an account, a key, a platform or a decision.

It is not a security certification.

## Test results

Full suite, run on a clean copy of the branch (Linux, Python 3.13, offscreen Qt): **49 files, 2465 checks passed, 0 failed.**
The one check of `tests/test_xrd_generator.py` that had failed since 5.51.0 was corrected (it contradicted the name of
the bundled fixture), so no failure is known. `tests/test_xrd_generator_actions.py` stalled once inside the full run, as it
has before, and passed 19 of 19 when run alone; that result is the one counted.

New test files of this work:

| File | Checks | What it covers |
| --- | --- | --- |
| `tests/test_outbound_policy.py` | 32 | levels, channels, local-only at the point of sending, address rules, the credential routing rule, redaction, aliases, the credential store |
| `tests/test_security_net.py` | 93 | SEC-01, SEC-04, SEC-06: token routing and redirects on every transport, no credential on a command line, https / loopback rules, key bound to its service, no plain-text keys |
| `tests/test_security_update.py` | 79 | SEC-02, SEC-05: signature, hash, platform, version, archive structure, nothing run before verification, interrupted install, rollback, friends / owner profile |
| `tests/test_security_ai_disclosure.py` | 82 | SEC-03: every payload to an AI service at every level, history, automatic look / continuation, attachments, pictures, instruction injection |
| `tests/test_local_only.py` | 48 | local-only mode: no request leaves through any path while plotting works |
| `tests/test_security_imports.py` | 172 | SEC-08: limits, 35 hostile path forms, staging, cancel, forbidden settings, originals preserved, safe export |
| `tests/test_packaging.py` | 73 | SEC-07 and release hygiene: pins, lock, launchers, clean build, secret scan, diagnostics |
| `tests/test_learning_core.py` | 181 | the learning service without Qt: staging, confirmation, origins, deduplication, stale candidates, matching, privacy, migration, storage failure, evidence |
| `tests/test_learning_sync.py` | 96 | contribution flow, worker, retries, tombstones, isolation and review rules (in-memory test server), the Supabase adapter (fake transport) |
| `tests/test_learning_ui.py` | 42 | the acceptance rows of A.11.13 in the real window (offscreen), incl. the XRD demonstration |
| `tests/test_cycle_due.py` | 105 | the 14-day gate and the evidence bundle |
| `tests/test_workflows_static.py` | 112 | static checks of the three workflow files, the prompt, the backend files and the setup documents |

Also run:

* The updater's own regression check of this branch against the published 5.58.6: **10 of 10 example files give
  the same Origin commands** – the scientific drawing is unchanged.
* A simulated update: the *installed 5.58.6 updater* copied this version over a 5.58.6 folder; the app then starts as
  5.59.0 (owner profile, learning database available). The old updater does not copy `requirements.lock`; it arrives
  with the update after that.
* `backend/supabase/tests/rls_tests.sql` on a throw-away PostgreSQL 16: 96 checks passed.
* Secret scan (counts only): 0 findings in the tracked files, the working folder and the available Git history
  (44 commits). `pip-audit` on the locked set: 0 known vulnerabilities in 36 packages.
* The pinned commits of the GitHub Actions were compared with their tags on GitHub.

* The **CI workflow has run on GitHub** (two runs on the first pushed commit, 27 November 2026): static checks and
  secret scan, dependency audit and all four test groups passed.
* A simulated **"Undo the last update"** from 5.59.0: version 5.58.6 is back, the files 5.59.0 added are removed, the
  app starts.
* The published app has needed **Python 3.12 or newer** since at least 5.57.0 (two program files use syntax of
  3.12); the launchers check that packages are present, not their versions, so an existing installation starts as
  before.

**Not run:** anything on Windows (installer, launchers, DPAPI, curl.exe / PowerShell fallbacks, the window itself),
live Origin, any real AI service or web search, the fortnightly-cycle and release workflows, the Claude Code action,
a Supabase project, a production signing key.

---

## Workstream A – learning and updates

### A1. Personal learning – working and tested

* **One service.** `opstudio.learning.LearningService` with a versioned SQLite database in the user's private
  folder (`<private folder>/learning/learning.sqlite3`), outside the program and never part of a release. Screens
  call it through one controller (`workspace_learning.LearningController`).
* **What is captured, and when.** Only confirmed outcomes: a corrected type, a corrected column mapping, a preferred
  template, a saved graph style, a saved workflow, accepted and dismissed suggestions, and - only when the separate
  diagnostics switch is on - classes of failures. The order is stage → validate what is displayed → confirm →
  persist. Opening, refreshing or restoring a file is origin *system* and records nothing; applying a memory is
  origin *memory* and never counts as a new confirmation; a change that is not confirmed is discarded when the file
  or sheet changes; a double click is one confirmation; a database failure leaves the user's mapping applied and
  says "could not remember it".
* **What is stored.** Allowlisted structure only: container, separators, normalised headers, units, column roles (in
  the file's own column order), the data family, template ids, component switches. Never rows, cell values, file
  names, folders, sample names, titles or axis ranges (ranges only on explicit request).
* **Matching.** Versioned structural signatures; exact matches first, weaker ones shown as such and never applied by
  themselves; units and required roles are hard conditions; conflicting memories are both shown; a match grade is not
  a probability. No embeddings.
* **Recommendations** still come from the Analysis catalogue: file → detection → validated roles → templates that
  fit → your saved preference may reorder those → your choice. A preference cannot add a template or lift one that
  does not fit.
* **In the window.** Start here and the Workbook: the bar "Saved XRD mapping available … Apply / Dismiss" and "Use
  XRD · X: … · Y: …  ☑ Remember this mapping  [scope]  Confirm". Start here: "Prefer this graph for such data".
  Graph editor: "Save style…" (this graph / this panel / graphs of this kind of data) and "Use saved style" - other
  graphs are never changed; undo and redo record nothing. Workbook ▸ Table: "Remember the last merge as a workflow…".
  Help ▸ Learning: list, before / after detail, edit (new revision), disable, enable, export, import, forget,
  withdraw, and four separate switches (learning on, auto-apply off, diagnostics off, sharing off).
* **Earlier knowledge.** `assistant_lessons.txt` and `learned_formats.json` are imported once with their origin
  marked; the originals stay; running it again adds nothing.

**The owner's demonstration** (steps 1-8 of A.11.13) is automated in `tests/test_learning_ui.py`: open a synthetic
XRD file whose columns the app cannot know → correct type and roles → confirm Remember → the record in Learning →
restart → a second file of the same layout with other measurements → Apply → XRD templates of Analysis → an
incompatible file is not touched → a style for one graph leaves its neighbour alone → disable and forget make the
suggestion disappear. Steps 9 and 10 (sharing between two accounts; a manual cycle with a pull request) need the
owner's accounts and were not performed.

Limits: tested offscreen on Linux, not in a native Windows window. Detection rules for families other than XRD use
the same framework and the same tests for mapping, style and preference, but each family was not walked through by
hand. Edits made inside Origin are not observed.

### A2. Shared learning – written, not validated live

* The contribution flow (preview of the exact payload → consent → outbox → idempotent retries → withdrawal →
  tombstones) and a background worker with timeouts and backoff: tested against an **in-memory test server**.
* A Supabase adapter using only the public client key (it refuses a service-role or secret key): tested with a
  **fake HTTP transport**; its real transport was never executed.
* SQL migration with row-level security, triggers against self-approval, a rate limit and tombstones: run on
  **plain PostgreSQL 16** with stand-ins for the Supabase roles (96 checks), not on a Supabase project.
* Sharing is off by default at two places (the policy channel and the learning switch). Nothing is uploaded.

Needs the owner: a backend project, two ordinary users and a reviewer, the API-level access tests of
`docs/SHARED_LEARNING_SETUP.md`. Until then: not a deployed service.

### A3. Fortnightly improvement cycle – written, never executed

* `tools/cycle_due.py`: deterministic 14-calendar-day gate in a configured time zone with durable state, idempotent
  cycle ids, one resumed cycle after an outage, manual force. **Tested** (105 checks incl. month, year, leap-day and
  daylight-saving boundaries).
* `tools/evidence_bundle.py`: strict validation of untrusted evidence, watermark, de-duplication, bounds;
  preference-only evidence gives "no useful evidence". **Tested.** The app writes an evidence file only on request
  (Help ▸ Learning ▸ *Evidence file for the developer…*) and never uploads it.
* `.github/workflows/fortnightly-cycle.yml`: daily check → evidence → the official Claude Code action with
  **read-only** permissions → a separate job of ordinary code that refuses forbidden paths and opens or updates one
  draft pull request → report. It never merges, releases or bumps the version. **Statically checked only**; inert
  until merged to `main` and `FORTNIGHTLY_ENABLED` is `true`.
* `.github/workflows/ci.yml` (tests, audit, secret scan) and `release.yml` (manual, protected environment, builds,
  signs, verifies, uploads a draft release). **Statically checked only.**

Needs the owner: everything in `docs/FORTNIGHTLY_CYCLE.md` (Claude GitHub app, one billing route with a spending
limit, the state branch, a private evidence source, branch protection, the release environment and key, one manual
cycle), then the enabling variable.

### A4. Authenticated releases through the updater – working with a test key

Signed manifest (Ed25519) verified before anything is unpacked or run; staged installation with a journal; recovery
at the next start; rollback. Proven with a key generated inside the tests. `update_trust.TRUSTED_KEYS` is empty: no
production key exists yet, so a friends build installs **no** update until the owner adds one. The owner's own copy
(no `security_profile.json`) updates from the repository as before and says that such an update is not verified.

---

## Workstream B – security and data protection

| Finding | Outcome | Evidence | Remaining |
| --- | --- | --- | --- |
| SEC-01 token routing | **fixed** | `test_security_net.py`: exact host / port / route; look-alike host, word in path, user-info, other port, downgrade, cross-origin redirect never get the token, on urllib, curl and PowerShell paths; nothing on a command line | curl.exe and PowerShell were simulated, not run on Windows |
| SEC-02 unsigned updates | **fixed for the friends build; owner's copy unchanged by choice** | `test_security_update.py`: bad signature, hash, platform, version, untrusted key, missing crypto package all refuse; nothing is run before verification; interrupted install recovers; rollback | production signing key; a first signed release |
| SEC-03 AI disclosure | **fixed in the main window** | `test_security_ai_disclosure.py`: captured payloads at every level, incl. stored history and automatic continuations; injection text cannot trigger a change or more disclosure | the classic Tk window builds its own payloads (covered at the transport only); a name the app does not know cannot be recognised |
| SEC-04 AI endpoints | **fixed** | `test_security_net.py`, `test_outbound_policy.py` | – |
| SEC-05 AI source repair | **switched off in the friends build** (refused inside the functions) | `test_security_update.py` | in the owner's copy it still runs candidate code as the user - not a sandbox, as before |
| SEC-06 secret storage | **fixed** | no plain-text form is ever returned or written; old plain values are moved and removed | Windows protection and a real keyring were simulated |
| SEC-07 dependencies | **fixed** | 14 exact pins, lock of 36 packages with hashes, installed with `--require-hashes` in a clean environment, `pip-audit` clean; no start-up path installs "latest" | the lock was made on Linux: regenerate and test on Windows; **the tested set needs Python 3.12+** |
| SEC-08 imports | **fixed** | `test_security_imports.py` (172 checks) | – |

Also done: a real **local-only mode** enforced at every transport; a **friends profile** (`tools/build_release.py
--profile friends`: local-only at first start, signed updates only, no AI repair); a **clean release build** from
committed, allowlisted files with a contents inventory; a **secret scan** of tree and history; `SECURITY.md`,
`PRIVACY.md`; a **sanitized problem report**; safe export of text cells.

### Release gates

These gates are about a build for OTHER people. Releasing to the owner's own update channel does not pass them.

* **Gate A (private local beta):** code and tests exist for every point. Open: your review of the bundled demo
  files (`RELEASE_CONTENTS.md` from the build), a real build from a commit, and one clean Windows account:
  install, import, plot, save / reopen, export, uninstall without administrator rights. **Not run.**
* **Gate B (AI-enabled beta):** disclosure and key handling pass. Open: usage limits are set by each user at their
  provider; the classic window's assistant.
* **Gate C (shared learning, recurring releases):** not open.

---

## What needs you

1. **Update and look.** 5.59.0 is on `main`. If anything is wrong: *Help ▸ Undo the last update*.
2. **Windows check** of the installer, the launchers and the window (and Origin). Note the Python 3.12+ requirement
   of the pinned set: an installation on an older Python keeps running, but Setup asks for a newer Python.
3. **Production signing key**: create it offline, put the public half into `update_trust.py`, the private half into
   the protected `release` environment. Never into the repository.
4. **Demo data review** before a friends build.
5. **GitHub settings**: branch protection, secret scanning, push protection, Dependabot alerts, private
   vulnerability reporting.
6. **Fortnightly cycle** and **shared learning**: the steps of the two setup documents, when you want them.

## Known limits

* Mocks do not prove native behaviour. Everything Windows-specific was simulated.
* The learning database import pulls in matplotlib / numpy / pandas through the `opstudio` package (no Qt).
* A user who changes an AI service address must enter the key again (it is bound to the service it was entered for).
* After "Undo the last update" to a version before 5.59.0, AI keys are asked for again.
* `SECURITY.md` describes the reporting route without naming the repository, because of the private-term check.

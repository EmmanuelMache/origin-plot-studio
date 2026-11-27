# Learning, updates and security – implementation tracker

Version 5.59.2 (5.59.0 developed on `integrate/learning-security`, based on 5.58.6; on `main` since 27 November 2026). Two workstreams, tracked separately:
**A** learning and the fortnightly update cycle, **B** security and data protection.

States used here:

* **implemented / tested** – code exists and an automated test in this repository proves the behaviour named.
* **implemented / not validated live** – code and local tests exist, but the real service or platform was never used.
* **mitigated** – the risk is reduced or the feature is switched off in the friends build; not a full fix.
* **awaiting owner setup** – cannot be finished without an account, a key or a decision of the owner.
* **not run** – a check that needs a platform this work did not have (Windows, live Origin, GitHub, a backend).

Nothing here is a security certification. A workflow file is not proof that a job ran; a mock adapter is not a
deployed service. Test counts are those of the run recorded in `TEST_REPORT.md`.

## What was reproduced on 5.58.6 before changing it

| Finding | Reproduced how (dummy inputs, no network) | Result before the change |
| --- | --- | --- |
| SEC-01 | Read `self_update._get`: `if TOKEN and "github" in str(url).lower()` | the token would be attached to any address containing the word |
| SEC-04 | Read `assistant._http`: any `http://` address was sent; "local" decided by `host.split(":")[0] in (...)` | remote plain http accepted |
| SEC-06 | Read `assistant.protect_key`: `if os.name != "nt": return {"plain": key}` | plain-text key outside Windows |
| SEC-02 / 05 | Read `self_update._dry`, `check`, `make_trial`: candidate code is run with the user's rights; zips unsigned | confirmed by inspection |
| SEC-03 | Read `workspace_assistant` state / look / `run_pending` paths | names, folder and look results reached the request |
| SEC-07 | `requirements.txt` had no versions; `smart_plots` and the launchers ran `pip install` of latest versions | confirmed |
| SEC-08 | `workspace_projects.import_project`: path checks and a declared 2 GiB cap, no streamed / count / manifest limits | confirmed |

## Workstream B – security and data protection

| ID | Requirement | Where | Test evidence | State |
| --- | --- | --- | --- | --- |
| B-F1 | One outbound-data policy: levels local-only / minimal / metadata / scientific, per-channel switches, checked where a request is sent | `origin_plot_app/outbound_policy.py` | `tests/test_outbound_policy.py` | implemented / tested |
| B-F2 | One credential store: Windows protection, system keyring, else session only; never plain text on disk | `origin_plot_app/secure_store.py`, `assistant.py`, `assistant_secrets.py` | `tests/test_outbound_policy.py`, `tests/test_security_net.py` | implemented / tested (DPAPI and a real keyring: not run) |
| SEC-01 | Update token only to the exact host, port and route; every redirect hop re-checked; no credential in process arguments or messages | `self_update.py`, `net.py` | `tests/test_security_net.py` | implemented / tested with mocked transports (curl.exe / PowerShell on Windows: not run) |
| SEC-02 | Signed release manifest verified before any candidate code is run; staging, interruption recovery, rollback | `update_verify.py`, `update_trust.py`, `self_update.py`, `tools/sign_release.py` | `tests/test_security_update.py` | implemented / tested with a test key; production key: awaiting owner setup |
| SEC-03 | AI disclosure permissions on the first message, stored history, automatic look / continuation, attachments, pictures, web results; accurate wording | `workspace_assistant.py`, `workspace_qt.py` (`look_info`), `web_free.py` | `tests/test_security_ai_disclosure.py`, `tests/test_local_only.py` | implemented / tested with captured payloads (no live transmission test); the classic Tk window is covered at the transport only |
| SEC-04 | Remote AI endpoints need https; loopback http only for a real loopback address on an approved port; a key is not reused for another service | `assistant.py`, `assistant_backends.py`, `outbound_policy.check_url` | `tests/test_security_net.py`, `tests/test_outbound_policy.py` | implemented / tested |
| SEC-05 | Client-side AI source repair off in the friends build (refused in the functions, not only hidden) | `self_update.py`, `workspace_menu.py` | `tests/test_security_update.py` | mitigated (off in the friends profile; its purpose moves to the reviewed PR cycle of workstream A) |
| SEC-06 | No plain-text fallback; migration of old plain values; redaction for every provider | `assistant.py`, `secure_store.py`, `outbound_policy.redact` | `tests/test_security_net.py`, `tests/test_outbound_policy.py` | implemented / tested |
| SEC-07 | Pinned requirements, lock with hashes, controlled installation, inventory, vulnerability check | `origin_plot_app/requirements.txt`, `requirements.lock`, `setup.pyw`, `start.pyw`, the `.bat` files, `tools/dependency_inventory.py`, `docs/DEPENDENCIES.md` | `tests/test_packaging.py` | implemented / tested on Linux; the Windows installer path: not run |
| SEC-08 | Import limits (streamed bytes, counts, manifest size and depth), Windows path hazards, staging and cleanup, cancel, settings a project may not carry; safe export of text cells | `workspace_projects.py`, `safe_export.py` | `tests/test_security_imports.py` | implemented / tested |
| B-L1 | Local-only mode that blocks update check and download, AI, web search, diagnostics and shared sync at the transport, while local work and personal learning go on | `outbound_policy.py` + the transports above, `opstudio/learning/sync.py` | `tests/test_local_only.py`, `tests/test_outbound_policy.py`, `tests/test_learning_sync.py` | implemented / tested |
| B-R1 | Clean release build from an allowlist of committed files; friends profile; contents inventory; secret scan of tree and history | `tools/build_release.py`, `tools/secret_scan.py`, `docs/RELEASE_PROCESS.md` | `tests/test_packaging.py` | implemented / tested; review of bundled demo data: awaiting owner |
| B-D1 | `SECURITY.md`, `PRIVACY.md`, sanitized diagnostic file | repository root, `origin_plot_app/diagnostics.py`, `workspace_privacy.py` | `tests/test_packaging.py` | implemented / tested |
| B-U1 | Settings > Privacy and connections (level, channels, where keys are kept, diagnostic file, Learning) | `origin_plot_app/workspace_privacy.py`, Help menu | `tests/test_learning_ui.py` | implemented / tested offscreen |

## Workstream A – learning and the fortnightly cycle

| ID | Requirement | Where | Test evidence | State |
| --- | --- | --- | --- | --- |
| A-1 | `LearningService` and versioned SQLite in the user's data folder; events, memories, revisions, feedback, outbox, tombstones | `origin_plot_app/opstudio/learning/` (`models`, `store`, `service`) | `tests/test_learning_core.py` | implemented / tested |
| A-2 | Stage → validate → confirm → persist; origins user / system / memory / migration; operation ids, deduplication, stale previews, storage failure does not undo the user's work | `service.py`, `workspace_learning.py` | `tests/test_learning_core.py`, `tests/test_learning_ui.py` | implemented / tested |
| A-3 | Allowlisted snapshots; no rows, names, paths or titles in memories; stricter shareable projection | `privacy.py`, `models.py` | `tests/test_learning_core.py`, `tests/test_learning_ui.py` | implemented / tested |
| A-4 | Versioned structural signatures; explainable matching; grades, not probabilities; conflicts shown, never resolved by popularity | `signatures.py`, `matcher.py` | `tests/test_learning_core.py` | implemented / tested |
| A-5 | XRD slice in the window: correct type and roles → confirm Remember → history → restart → second file → apply → Analysis recommendations; incompatible file left alone | `workspace_starthere.py`, `workspace_learning.py` | `tests/test_learning_ui.py` | implemented / tested offscreen (native Windows window: not run) |
| A-6 | Remember this mapping in the Workbook; Save workflow after a merge | `workspace_workbook.py` | `tests/test_learning_ui.py`, `tests/test_workbook_editing.py` | implemented / tested |
| A-7 | Preferred template: ranks only templates that already fit; nothing added | `Workbench.recommendations` via `workspace_learning.rank` | `tests/test_learning_ui.py`, `tests/test_learning_core.py` | implemented / tested |
| A-8 | Save style for one graph, one panel or a kind of data; other graphs untouched; undo / redo record nothing | `workspace_graph_editor.py`, `workspace_learning.py` | `tests/test_learning_ui.py` | implemented / tested |
| A-9 | Learning history: view, edit (new revision), disable, enable, export, import, forget, withdraw; separate switches for learning, diagnostics, sharing, auto-apply | `workspace_learning.HistoryDialog` | `tests/test_learning_ui.py` | implemented / tested |
| A-10 | Migration of `assistant_lessons.txt` and `learned_formats.json`, idempotent, originals kept | `migrate.py` | `tests/test_learning_core.py`, `tests/test_learning_ui.py` | implemented / tested |
| A-11 | Sharing adapter protocol, contribution preview and consent, outbox, retries, tombstones, worker | `sync.py` | `tests/test_learning_sync.py` (against the in-memory test server) | implemented / not validated live |
| A-12 | Supabase adapter (REST, public client key only) and SQL migration with row-level security | `supabase_adapter.py`, `backend/supabase/` | fake HTTP transport in `tests/test_learning_sync.py`; SQL tests in `backend/supabase/tests/` | implemented / not validated live; a backend project: awaiting owner setup |
| A-13 | Sanitized evidence export and the bounded bundle for a cycle | `evidence.py`, `tools/evidence_bundle.py` | `tests/test_learning_core.py`, `tests/test_cycle_due.py` | implemented / tested |
| A-14 | Deterministic 14-day gate: time zone, durable state, idempotent cycle ids, one resumed cycle after an outage | `tools/cycle_due.py` | `tests/test_cycle_due.py` | implemented / tested |
| A-15 | Workflows: daily due check → evidence → Claude Code PR → report; CI; separate signed release | `.github/workflows/`, `automation/` | `tests/test_workflows_static.py` (static checks of the files); the CI workflow ran on GitHub, green | CI: implemented / ran on GitHub. Cycle and release workflows: never executed; awaiting owner setup |
| A-16 | Authenticated release through the updater | see SEC-02 | `tests/test_security_update.py` | implemented / tested with a test key; production key and a first signed release: awaiting owner setup |
| A-17 | Automatic evidence and a scheduled review (5.59.2): the app keeps its evidence file in a folder the user picks once; a Claude Code cloud scheduled task reads those files from the owner's Google Drive every 14 days and publishes a tested fix | `opstudio/learning/evidence.py` (`auto_set`, `auto_write`), `workspace_learning.py`, `automation/scheduled_review.md`, `tools/full_suite.sh`, `tools/suite_counts.py`, `tools/update_regression.py`, `tools/cycle_due.py` (`published`) | `tests/test_learning_ui.py`, `tests/test_cycle_due.py` | app side: implemented / tested offscreen. Scheduled task: set up on 27 November 2026 (bound to the owner's Claude Code conversation that holds the Drive connector), Drive search verified from that session; **no cycle has run yet** |

## Release gates (Appendix B.7)

| Gate | Status |
| --- | --- |
| A – private local beta | Code and tests for every point exist. Open: review of bundled demo data by the owner; a clean Windows account install / import / plot / export / uninstall (**not run**); a real release build from a commit. |
| B – AI-enabled beta | Disclosure levels, session-only or protected keys and instruction-injection tests pass with captured payloads. Open: API usage limits are set at the provider by each user (documented, not enforced by the app); the classic Tk window builds its own payloads and is covered at the transport only. |
| C – shared learning and recurring releases | **Not open.** No backend is deployed, the workflows have never run, there is no production signing key. Shared learning stays off by default until backend access tests pass with two ordinary users and a reviewer. |

## Not run in this work

* Native Windows: installer, launchers, DPAPI, `curl.exe` / PowerShell fallbacks, the PySide6 window on Windows.
* Live Origin.
* Any real AI service, web search, a run of the fortnightly-cycle or release workflow, Claude Code action run, Supabase project. (The CI workflow did run on GitHub.)
* A production signing key (verification was proven with a key generated inside the tests).

# The fortnightly improvement cycle – owner setup

## In use since 27 November 2026: a Claude Code cloud scheduled task

The owner chose the simpler of the two schedulers this document describes. It needs no API key, no GitHub secret and
no backend:

| Part | What it is |
| --- | --- |
| Evidence | Each installation that switched on *Help ▸ Learning ▸ Save the evidence file by itself* keeps `ops_evidence_<installation>.json` in a folder of the owner's Google Drive (5.59.2). The app sends nothing; the Drive program syncs the file. |
| Scheduler | A Claude Code cloud scheduled task, **"Origin Plot Studio 14-day review"**, wakes the owner's Claude Code conversation in which it was set up, every Friday at 02:43 (Europe/Stockholm). That conversation holds the owner's Google Drive connector. (A scheduled task that starts a fresh session each time could not be given the connector from here: it would have no Drive access.) |
| Cadence | `tools/cycle_due.py` and `cycle_state.json` on the branch `automation-state`: first cycle due **11 December 2026**, then every 14 days. On the Fridays in between the session stops after the check. |
| Instructions | `automation/scheduled_review.md` (and `automation/cycle_prompt.md` for the review itself). |
| Publishing | By the owner's decision of 27 November 2026 a fix is published by that session itself - to `main`, `upgrade-v2` and `integrate/project-workbench` - when the whole suite is clean on a clean copy (`tools/full_suite.sh`, `tools/suite_counts.py`), the updater's own check passes (`tools/update_regression.py`) and CI is green. Changes to update, security, privacy, learning-privacy, dependency and automation files, and changes of scientific defaults, are **not** published this way: they wait for the owner as a draft pull request. |

What was verified when it was set up: the Drive search from a cloud session works (it found no evidence file yet);
the gate answers "not due" before 11 December and "due" on it; the app writes and refreshes its file
(`tests/test_learning_ui.py`). **No cycle has run yet** - the first one will most likely end as `no_evidence`. What a
cycle did is in the summary written into that conversation and in `cycle_state.json`; this document is not updated
by a cycle. The review depends on that conversation: if it is archived or deleted, the review stops, and the owner
sets it up again (a new scheduled task created in the Claude scheduled-tasks page with the Google Drive connector
and the prompt of `automation/scheduled_review.md`).

To stop it: delete the scheduled task (claude.ai/code ▸ scheduled tasks). To stop one computer from contributing:
untick the box in *Help ▸ Learning*. The private term list of the maintainer's own machine is not available to the
scheduled session; it works only with sanitized evidence and fixtures it generates itself.

**Do not also enable the GitHub workflow below** (`FORTNIGHTLY_ENABLED`): two schedulers would compete. The rest of
this document describes that second route, which stays switched off.

## The GitHub Actions route

**Status: not active.** The cycle has never done anything on GitHub: the Claude Code action was not invoked, no
evidence source is configured and no release has been signed. The file is on `main` since 5.59.0, so GitHub starts
it once a day - and every job stops at once, because the variable `FORTNIGHTLY_ENABLED` is not set. What exists is
code and its local tests. A workflow file is not proof that a job ran. (Only the separate CI workflow has run.)

What was tested here, on Linux, without network:

| Part | Test | What it proves |
| --- | --- | --- |
| `tools/cycle_due.py` – the 14-day gate | `python3 tests/test_cycle_due.py` | due / not due, exactly 14 calendar days across month, year, leap day and both daylight-saving changes of Europe/Stockholm, one resumed cycle after an outage, duplicate runs, stale runs, manual force, no-evidence and no-change endings |
| `tools/evidence_bundle.py` – the bundle | same file | strict validation of untrusted evidence, watermark, de-duplication across installations, bounds, a preference-only backlog gives "no useful evidence" |
| the three workflow files | `python3 tests/test_workflows_static.py` | they parse; daily cron, no `*/14`; a concurrency group; every job gated; the model's job is read-only; no release or signing secret in the cycle; the release workflow is manual and uses the protected environment; actions pinned to commits |

The pinned commits of the actions were compared with the tags on GitHub on 26 November 2026
(`git ls-remote`): `actions/checkout` v7.0.1, `actions/setup-python` v7.1.0, `actions/upload-artifact` v7.0.2,
`actions/download-artifact` v8.0.2, `anthropics/claude-code-action` v1.0.290. Dependabot proposes newer ones.

## How it works

Three separate processes; only the third is this cycle:

1. Personal learning in the app – immediately, on the user's computer, no code change.
2. Shared learning – optional, see `docs/SHARED_LEARNING_SETUP.md`.
3. Product improvement – every 14 days: evidence → a tested pull request → (after your review) a signed release.

One scheduled workflow wakes **once a day** and asks ordinary code whether a cycle is due:

| Job | Who decides | Permissions | What it does |
| --- | --- | --- | --- |
| `due` | `tools/cycle_due.py` | contents: write (state branch only), pull-requests: read | reads the state; on 13 days of 14: not due, stop |
| `evidence` | `tools/evidence_bundle.py` | contents: read | builds a bounded, sanitized bundle from your private evidence source; none configured → a report says so |
| `claude` | the official Claude Code action | **contents: read, pull-requests: read** | works out a change with regression tests in a checkout of `cycle/<cycle id>`; its result leaves the job as a patch file |
| `publish` | ordinary code, no model | contents: write, pull-requests: write | refuses a patch that touches workflows, automation, release, signing, update, dependency or version files; pushes the cycle branch; opens or updates **one draft** pull request |
| `report` | `tools/cycle_due.py finish` | contents: write (state branch), issues: write | records the ending, moves the date on, writes the report |

It never merges, never pushes to `main`, never bumps the version and never publishes a release. It holds no signing
key and no database credential. Installed copies of the app do not contain Claude Code or any developer credential
and do not rewrite their own code.

The state (`cycle_state.json`) lives on an orphan branch `automation-state`. A cycle id is the scheduled local date
(`cycle-2026-12-10`), so a rerun of the same day is the same cycle. After a long outage exactly one pending cycle is
resumed and the next date is the next slot on the 14-day grid from the anchor. GitHub may start a scheduled run late
or drop it; this is a target rhythm, not a guaranteed time.

## Owner steps, in this order

Nothing below was done by this work.

1. **Done with 5.59.0:** the files are on `main`. A scheduled workflow runs only from the default branch; the daily
   job starts, sees that `FORTNIGHTLY_ENABLED` is not `true`, and stops at once.
2. **Protect `main`**: require a pull request, the `CI` checks, and your approval. Enable Dependabot alerts, secret
   scanning and push protection (Settings → Code security).
3. **Install the Claude GitHub app** on the repository: in Claude Code run `/install-github-app` (repository
   administrator needed). Reference: <https://code.claude.com/docs/en/github-actions>.
4. **Choose ONE way of paying** and add it as a repository secret:
   * `ANTHROPIC_API_KEY` – API billing. Set a monthly spending limit for that key in the Anthropic console.
   * `CLAUDE_CODE_OAUTH_TOKEN` – your Claude subscription (`claude setup-token`). Uses subscription limits.
   If both exist, set the repository variable `CLAUDE_AUTH_ROUTE` to `api_key` or `subscription`. With neither the
   job stops with a message. Optional variables: `CYCLE_MODEL`, `CYCLE_MAX_TURNS`.
5. **Create the state**: once, locally,
   `python3 tools/cycle_due.py init --state cycle_state.json --anchor <first local date> --time 06:00 --timezone Europe/Stockholm`,
   and push that file as the only file of a new orphan branch `automation-state`.
6. **Decide where evidence comes from.** The app writes an evidence file only when a user asks for it
   (Settings → Learning → *Evidence file for the developer…*) and never uploads it. You collect such files in a
   **private** place and point the workflow at it with repository variables: `EVIDENCE_REPOSITORY` (a private
   repository) + `EVIDENCE_REF` + `EVIDENCE_PATH`, with a read-only token in the secret `EVIDENCE_READ_TOKEN`; or
   `EVIDENCE_BRANCH` of this repository (refused while the repository is public). Without any of these the cycle
   ends as `no_evidence` with a report.
7. **Run one cycle by hand**: Actions → *Fortnightly cycle* → Run workflow, first with `dry_run`, then with `force`.
   Read the report and the draft pull request; run the tests it names.
8. **Create the `release` environment** (Settings → Environments) with yourself as required reviewer, and add the
   release signing key there as `OPS_RELEASE_SIGNING_KEY` (see `docs/RELEASE_PROCESS.md`). Put the matching public
   key into `origin_plot_app/update_trust.py` in a reviewed pull request. Test one release and one rollback.
9. Only then set the repository variable **`FORTNIGHTLY_ENABLED` = `true`**.

Use **one** scheduler for this job. Since 27 November 2026 that is the Claude Code cloud scheduled task described at
the top; enabling this workflow as well would make two systems work on the same evidence.

## What a cycle may end as

`published` (cloud scheduled task only: the fix was released by the session), `no_evidence` (nothing new, or no source), `no_change` (evidence read, no justified or reproducible code change –
preferences stay data), `pr_open` (one draft pull request), `deferred` (an earlier cycle's pull request is still
open on the same files), `failed` (recorded; tried once more the next day). None of these changes the version.

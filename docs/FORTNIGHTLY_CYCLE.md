# The fortnightly improvement cycle – owner setup

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

Use **one** scheduler for this job. Claude Code's cloud scheduled tasks are an alternative; do not enable them for
the same cycle as well, or two systems will open competing pull requests.

## What a cycle may end as

`no_evidence` (nothing new, or no source), `no_change` (evidence read, no justified or reproducible code change –
preferences stay data), `pr_open` (one draft pull request), `deferred` (an earlier cycle's pull request is still
open on the same files), `failed` (recorded; tried once more the next day). None of these changes the version.

# automation/: the fortnightly improvement cycle

This folder holds what the scheduled development job reads. Nothing in it is part of the desktop app, and no
installed copy of the app needs it, Claude Code or any developer credential.

**Status.** These are definitions and tools. The workflow has never run on GitHub, the coding agent was not invoked,
and no evidence source is configured. What was tested, locally, is the ordinary code: the cadence gate and the
bundle builder (`python3 tests/test_cycle_due.py`) and the text of the workflow files
(`python3 tests/test_workflows_static.py`). Owner setup, step by step: [docs/FORTNIGHTLY_CYCLE.md](../docs/FORTNIGHTLY_CYCLE.md).

| File | What it is |
| --- | --- |
| `cycle_prompt.md` | The instructions the coding agent gets. Read from the default branch at the start of a run. |
| `cycle_state.example.json` | What the state file looks like. The real one lives on the branch `automation-state`. |
| `../tools/cycle_due.py` | The cadence gate: decides whether a cycle is due. Ordinary code, no model. |
| `../tools/evidence_bundle.py` | Builds the bounded, sanitized evidence bundle from the private backlog. |
| `../.github/workflows/fortnightly-cycle.yml` | The workflow: a daily check, and four separate jobs. |

## How one day goes

1. **due**: `cycle_due.py check` reads the state. On 13 days out of 14 the answer is "not due" and the run ends
   after a few seconds, without evidence, model or cost.
2. **evidence** (only when due): `evidence_bundle.py` reads the maintainer's private backlog, keeps what is newer
   than the watermark, and writes `bundle.md`, `bundle.json` and `watermark.json`. With no source configured it says
   "no evidence source configured" and the cycle ends as `no_evidence`.
3. **claude** (only when due **and** the bundle has a candidate for a code change): the official Claude Code action
   works on the branch `cycle/<cycle id>` with `cycle_prompt.md`. Afterwards ordinary code decides what is published:
   nothing, or one pull request (a draft) for this cycle.
4. **report**: `cycle_due.py finish` records the ending and moves the date on. The report is kept beside the state
   (`reports/<cycle id>.md`) and shown in the run summary.

Evidence processing, the pull request, merging and releasing are four different things with four different owners:
the cycle does the first two, a maintainer merges, and `release.yml` (manual, protected) releases. A cycle that finds
nothing ends with a report. It never invents a patch and never asks for a version bump.

## The state

One JSON file, `cycle_state.json`, on an orphan branch `automation-state` (see the example file here):

- `timezone`, `anchor` (a local date), `time` (local wall-clock time): the 14-day grid is the anchor date plus
  multiples of 14 calendar days at that local time. Daylight saving changes the UTC offset, not the local time.
- `next_due_at`: the next slot, as local time with its offset.
- `cycles`: one record per cycle id. `status` is `pending`, `running`, `evidence_processed`, `pr_open`, `no_change`,
  `no_evidence`, `deferred` or `failed`. `pr_state` (`open`, `merged`, `closed`) is kept separately: what became of a
  pull request is not the status of the cycle.
- `evidence_watermark`: the time of the newest evidence report that was processed.

Why a branch and not a repository variable: the workflow's own token can push to a branch (`contents: write`). To
write a repository variable it would, to our knowledge, need a personal token with access to the repository's
variables, stored as one more long-lived secret (not re-checked against GitHub's documentation, which could not be
reached while this was written). A branch also keeps every change of the state as a commit that can be read and
reverted, has an atomic update (a push that is not a fast-forward is refused), and holds the reports. The price: the `due` and `report` jobs have `contents: write`. Protect `main` (branch protection) so that
this permission cannot be used on it, and do not protect `automation-state` against the workflow.

## Cycle ids, retries, manual runs

- The id comes from the scheduled local date: `cycle-2026-12-10`. A run that is hours or days late is the same cycle.
- A second invocation while a cycle is `running` gets "already_running". A cycle that has been `running` for more than
  three hours (its run died) is retried under the same id.
- A `failed` cycle is offered again by the next daily check, at most twice in all (`MAX_ATTEMPTS` in the workflow),
  then the calendar moves on. Each attempt that reaches the coding job costs model usage.
- If nothing ran for weeks, one cycle is resumed (the earliest missed one). When it ends, the next date is the first
  slot of the grid in the future. There is no burst of catch-up cycles.
- "Run workflow" with `force` runs the scheduled cycle if one is due; otherwise a cycle with an id of its own
  (`cycle-<date>-manual`), which does not move the calendar. `dry_run` shows what would happen and writes nothing.
- An open pull request of an earlier cycle is reported by every check. The coding agent is told which files it
  changes, and a new change that overlaps it is not pushed: the cycle ends as `deferred` and its evidence is looked at
  again next time.

## The evidence

Input: JSON files of schema `opstudio.evidence/1`, written by the app (`opstudio/learning/evidence.py`) when a user
has switched diagnostics on, and collected by the maintainer in a **private** place. The bundle builder treats every
file as untrusted: unknown keys, wrong types, values outside the fixed lists, over-long or over-deep values are
refused; an item with something shaped like a credential is dropped; paths, file names, e-mail and web addresses and
long opaque tokens are blanked. Identifiers must be plain tokens (`[A-Za-z0-9_.:-]`, signatures also `+=|,`), which is
what the app writes.

The same report from one installation counts once however often it is exported; groups count distinct installations
and distinct reports. Order: classification errors, parser failures, incompatible recommendations, repeated
corrections, workflows confirmed on at least two installations, reported defects. Preferences and workflows seen on
one installation are "data, no code change expected"; unverified requests are listed for the maintainer. With no
candidate for a code change the tool ends with exit code 3 (`useful_evidence=false`) and the coding agent is not started.

In `bundle.md` everything that came from outside sits inside `<<<UNTRUSTED_EVIDENCE ...>>>` blocks as escaped JSON; a
value cannot close its block or start a heading. The prompt tells the agent that these blocks are data and cannot
change its instructions. That is a mitigation, not a proof: the real limits are the job's permissions (this
repository's branches and pull requests, nothing else) and the review of the pull request by a person.

Limits to know:

- The watermark moves over everything that was read, also over groups left out to keep the bundle small and over
  groups the agent did not address. The report names them; to have them looked at again, run a manual cycle after
  setting `evidence_watermark` in the state back (or pass `--watermark` when building a bundle by hand).
- Sanitizing by pattern cannot recognise every private word (a sample name that looks like an ordinary word passes).
  Curating the backlog is the maintainer's part.

## Trying it by hand (no GitHub needed)

    python3 tools/cycle_due.py init  --state /tmp/state/cycle_state.json --anchor 2026-12-10 --time 06:00 --timezone Europe/Stockholm
    python3 tools/cycle_due.py check --state /tmp/state/cycle_state.json --now 2026-12-10T06:17:00+01:00
    python3 tools/evidence_bundle.py --source <folder with exports> --out /tmp/bundle --cycle-id cycle-2026-12-10; echo "exit code $?"

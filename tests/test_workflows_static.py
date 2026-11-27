"""The automation files say what the documents claim: the fortnightly cycle is a daily check that does nothing until the
owner switches it on, its coding job can reach neither the release environment nor a signing or database secret, it
never merges or releases, the release runs only by hand behind a protected environment, CI gives a pull request from
a fork no secret, and every third-party action is pinned to a full commit.

These are checks of the TEXT of the files (and of their YAML structure when PyYAML is installed; it is not one of the
app's requirements, so without it the structural checks are done on the text by indentation and the first line of the
output says so). They cannot show that a workflow has run on GitHub or behaves there as written.
Run:  python tests/test_workflows_static.py"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "tools"))
try: import yaml
except Exception: yaml = None

N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))

WF = ROOT / ".github" / "workflows"
FILES = {"cycle": WF / "fortnightly-cycle.yml", "ci": WF / "ci.yml", "release": WF / "release.yml"}
TEXT = {k: p.read_text(encoding="utf-8") if p.is_file() else "" for k, p in FILES.items()}
print("PyYAML " + (f"{yaml.__version__}: structure checked on the parsed files as well" if yaml else "is not installed: structure checked on the text only"))


def code(text):
    """The text without comment lines and without trailing comments (a '#' inside quotes is left alone)."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"): continue
        out.append(re.sub(r"\s+#\s[^'\"]*$", "", line))
    return "\n".join(out)


def jobs(text):
    """{job name: its block of text} by indentation: the jobs are the keys two spaces in under 'jobs:'."""
    out, name, on = {}, None, False
    for line in text.splitlines():
        if re.match(r"^jobs:\s*$", line): on = True; continue
        if not on: continue
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m: name = m.group(1); out[name] = []; continue
        if name: out[name].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def key_block(block, key, indent):
    """The lines under `key:` at the given indentation (deeper lines only), comments stripped."""
    lines = code(block).splitlines(); out = []; on = False
    for line in lines:
        if re.match(rf"^ {{{indent}}}{re.escape(key)}:", line):
            on = True; rest = line.split(":", 1)[1].strip()
            if rest: out.append(rest)
            continue
        if on:
            if line.strip() and len(line) - len(line.lstrip()) <= indent: break
            out.append(line.strip())
    return [l for l in out if l]


def perms(block, indent=4): return dict((l.split(":")[0].strip(), l.split(":")[1].split("#")[0].strip()) for l in key_block(block, "permissions", indent) if ":" in l and l != "{}")
def job_if(block): return " ".join(key_block(block, "if", 4)).replace(">-", "").strip()
def secrets_in(text): return set(re.findall(r"secrets\.([A-Za-z0-9_]+)", code(text)))
def uses(text): return re.findall(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$", text, re.M)
def run_blocks(text):
    """The shell scripts of the steps: 'run: |' blocks and one-line 'run:' values."""
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:-\s+)?run:\s*(.*)$", lines[i])
        if m:
            ind = len(lines[i]) - len(lines[i].lstrip()); body = [] if m.group(2).strip() in ("|", ">", "|-", ">-") else [m.group(2)]
            i += 1
            while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > ind): body.append(lines[i]); i += 1
            out.append("\n".join(body)); continue
        i += 1
    return out


for k, p in FILES.items(): check(f"{p.relative_to(ROOT).as_posix()} is there", p.is_file())
PARSED = {}
if yaml:
    for k in FILES:
        try: PARSED[k] = yaml.safe_load(TEXT[k]); ok = isinstance(PARSED[k], dict) and "jobs" in PARSED[k]
        except Exception as e: ok = False; PARSED[k] = {}
        check(f"{FILES[k].name} is valid YAML with jobs", ok)
    for k in FILES:
        same = sorted(jobs(TEXT[k])) == sorted((PARSED[k].get("jobs") or {}))
        check(f"{FILES[k].name}: the reading by indentation finds the same jobs as the YAML parser", same, sorted(jobs(TEXT[k])))
        same = all(perms(b) == {str(a): str(v) for a, v in ((PARSED[k]["jobs"][j].get("permissions")) or {}).items()} for j, b in jobs(TEXT[k]).items())
        check(f"{FILES[k].name}: ... and the same permissions for every job", same)
def on_of(k):
    """The triggers of a workflow, from the parser when there is one ('on' is read as True by YAML 1.1), else from the text."""
    if yaml and PARSED.get(k):
        v = PARSED[k].get("on", PARSED[k].get(True)); return set(v) if isinstance(v, dict) else {v} if isinstance(v, str) else set(v or [])
    m = re.search(r"^on:\s*\n((?:(?:  .*)?\n)+)", TEXT[k], re.M); return set(re.findall(r"^  ([a-z_]+):", m.group(1) if m else "", re.M))

# ================================================================ the fortnightly cycle
C = TEXT["cycle"]; CC = code(C); J = jobs(C)
crons = re.findall(r"cron:\s*[\"']([^\"']+)[\"']", CC)
check("the cycle has exactly one schedule, and it is a daily one (fixed minute and hour, every day)", len(crons) == 1 and bool(re.fullmatch(r"\d{1,2} \d{1,2} \* \* \*", crons[0])), crons)
check("... no '*/14' or any other day step is used to mean two weeks", "*/14" not in CC and not any("/" in c for c in crons), crons)
check("... the 14-day decision is taken by tools/cycle_due.py", "tools/cycle_due.py" in CC and "check --state" in CC and "start --state" in CC and "finish --state" in CC)
check("the cycle is started by the schedule or by hand, and by nothing else", on_of("cycle") == {"schedule", "workflow_dispatch"}, on_of("cycle"))
check("... the manual start has the inputs force and dry_run", bool(re.search(r"workflow_dispatch:\s*\n\s+inputs:\s*\n\s+force:", CC)) and bool(re.search(r"^\s+dry_run:\s*$", CC, re.M)))
check("a concurrency group keeps two runs from overlapping (a running one is not cancelled)", bool(re.search(r"^concurrency:\s*\n\s+group:\s*\S+", CC, re.M)) and bool(re.search(r"cancel-in-progress:\s*false", CC)))
check("at the top no permission is given at all; each job names its own", bool(re.search(r"^permissions:\s*\{\}\s*$", CC, re.M)) and all(perms(b) for b in J.values()), {k: perms(b) for k, b in J.items()})
check("the jobs are due, evidence, claude, publish and report", list(J) == ["due", "evidence", "claude", "publish", "report"], list(J))
gate = "vars.FORTNIGHTLY_ENABLED == 'true' || github.event_name == 'workflow_dispatch'"
check("every job is gated: it runs only when the owner's variable FORTNIGHTLY_ENABLED is 'true' or the run was started by hand", all(gate in job_if(b) for b in J.values()), {k: job_if(b)[:60] for k, b in J.items()})
check("... evidence, claude, publish and report also need a cycle that is really due", all("needs.due.outputs.due == 'true'" in job_if(J[k]) for k in ("evidence", "claude", "publish", "report")))
check("... the coding job also needs useful evidence, and never runs in a dry run", "needs.evidence.outputs.useful_evidence == 'true'" in job_if(J["claude"]) and "inputs.dry_run != true" in job_if(J["claude"]), job_if(J["claude"]))
check("the header says plainly that the file is not a running schedule", "not a running schedule" in C and "DEFAULT" in C and "FORTNIGHTLY_ENABLED" in C.split("name: Fortnightly cycle")[0])

cl = J["claude"]; clc = code(cl); pb = J["publish"]; pbc = code(pb)
check("the coding job (the model) can only READ the repository: it cannot push, open or change a pull request", perms(cl) == {"contents": "read", "pull-requests": "read"}, perms(cl))
check("... publishing is a separate job of ordinary code with exactly two write permissions (contents, pull-requests), and the model does not run in it", perms(pb) == {"contents": "write", "pull-requests": "write"}
      and not [u for u, _ in uses(pbc) if u.startswith("anthropics/")] and not (secrets_in(pb) & {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"}), (perms(pb), secrets_in(pb)))
check("... it names no environment, so the protected release environment is out of its reach", not re.search(r"^\s+environment:", clc, re.M))
check("... the only secrets it names are the two Claude credentials", secrets_in(cl) == {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"}, secrets_in(cl))
check("... no release, signing, database or evidence credential appears in it", not re.search(r"OPS_RELEASE|SIGNING|SUPABASE|SERVICE_ROLE|service_role|DATABASE_URL|EVIDENCE_READ_TOKEN|id-token", clc))
check("the whole cycle names three secrets at most: the two Claude credentials and the read-only evidence token", secrets_in(C) <= {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "EVIDENCE_READ_TOKEN"}, secrets_in(C))
check("... and the evidence token is used in the evidence job only", all("EVIDENCE_READ_TOKEN" not in code(J[k]) for k in ("due", "claude", "report")) and "EVIDENCE_READ_TOKEN" in code(J["evidence"]))
acts = [u for u, _ in uses(clc) if u.startswith("anthropics/")]
check("the coding job calls the official Claude Code action, once per credential route", len(acts) == 2 and all(a.startswith("anthropics/claude-code-action@") for a in acts), acts)
check("... with a prompt, a turn limit and a time limit", clc.count("prompt: ${{ steps.context.outputs.prompt }}") == 2 and "--max-turns" in clc and bool(re.search(r"^    timeout-minutes:\s*\d+", clc, re.M)) and clc.count("timeout-minutes: 40") == 2)
check("... the action works with this job's own token, so the job's permissions are the limit", clc.count("github_token: ${{ github.token }}") == 2)
check("... the allowed tools are a strict list, with pushing, committing, gh and the web denied to the agent", "--permission-mode default" in clc and "--allowedTools" in clc and all(x in clc for x in ("Bash(git push:*)", "Bash(git commit:*)", "Bash(gh:*)", "WebFetch", "WebSearch")))
check("both credential routes are supported, and exactly one is used", "anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}" in clc and "claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in clc
      and "steps.auth.outputs.route == 'api_key'" in clc and "steps.auth.outputs.route == 'subscription'" in clc)
check("... with neither secret the job stops with a clear message, and with both the owner must choose", "Neither the secret ANTHROPIC_API_KEY" in clc and "CLAUDE_AUTH_ROUTE" in clc and clc.count("exit 1") >= 2)
check("the instructions are taken from automation/cycle_prompt.md of the default branch, before the cycle branch is checked out",
      clc.index("cp automation/cycle_prompt.md") < clc.index('git switch -c "$CYCLE_BRANCH"') and "default_branch" in clc)
ctx = [r for r in run_blocks(cl) if "prompt<<" in r]
check("the evidence is handed over as a file to read; its text is never put into the prompt", len(ctx) == 1 and "bundle.md" in ctx[0] and not re.search(r"cat[^\n]*\.cycle/evidence|cat[^\n]*bundle\.(md|json)", ctx[0]))
check("ordinary code decides what is published: forbidden paths, the version line and overlap with an open cycle pull request are checked before any push",
      all(x in pbc for x in (r"\.github/", "automation/", "sign_release", "requirements", "VERSION")) and "must not touch" in pbc and pbc.index("must not touch") < pbc.index("git push origin")
      and not any(re.search(r"^\s*(git push|gh pr (create|edit|merge|close|review))\b", r, re.M) for r in run_blocks(cl)), [x for x in (r"\.github/", "automation/", "sign_release", "requirements", "VERSION", "must not touch") if x not in pbc])
check("one pull request per cycle: an open one for the cycle branch is updated, otherwise one is opened as a draft", 'gh pr list --head "$CYCLE_BRANCH"' in pbc and "gh pr edit" in pbc and "gh pr create --draft" in pbc)
pushes = re.findall(r"git push [^\n]*", CC)
check("the only pushes go to the cycle branch and to the state branch", len(pushes) == 3 and all(p.strip().endswith(('"HEAD:refs/heads/$CYCLE_BRANCH"', '"HEAD:refs/heads/$STATE_BRANCH"')) for p in pushes), pushes)
never = ("git push origin main", "gh pr merge", "gh release", "--admin", "gh pr review", "gh workflow run", "auto-merge", "gh secret", "gh variable")
forced = re.findall(r"git push[^\n]*(?:--force|-f\b)[^\n]*", CC); merges = re.findall(r"git merge(?!-base)[^\n]*", CC)
check("the cycle never merges, never pushes to main, never force-pushes, never publishes a release and never touches settings", not [x for x in never if x in CC] and not forced and not merges, ([x for x in never if x in CC], forced, merges))
ev = code(J["evidence"])
check("the evidence job can only read", perms(J["evidence"]) == {"contents": "read"}, perms(J["evidence"]))
check("... with no evidence source configured it reports that and goes on; it does not fail and invents nothing", "status=not_configured" in ev and "No evidence source is configured" in ev and "steps.source.outputs.status != 'not_configured'" in ev)
check("... evidence kept on a branch of this repository is refused unless the repository is private", ".private" in ev and "must not be kept in a public place" in ev)
check("... the bundle goes to the coding job only when it holds useful evidence", "steps.bundle.outputs.useful_evidence == 'true'" in ev and "tools/evidence_bundle.py" in ev)
rp = code(J["report"])
check("the report job records every ending, also failures and skipped jobs, and names 'no evidence source configured'", "always()" in job_if(J["report"]) and "No evidence source configured" in rp and all(s in rp for s in ("no_evidence", "no_change", "failed", "dry_run")))
check("... it says in every report that no version bump and no release happened", "version bump: none" in rp)
check("... a dry run records nothing", rp.count("env.DRY_RUN != 'true'") >= 2 and "env.DRY_RUN != 'true'" in code(J["due"]))
check("the state lives on its own branch and is written only by the due and report jobs", "STATE_BRANCH: automation-state" in CC and perms(J["due"]) == {"contents": "write", "pull-requests": "read"}
      and perms(J["report"]) == {"contents": "write", "issues": "write"} and "STATE_BRANCH" not in clc and "STATE_BRANCH" not in ev and "STATE_BRANCH" not in pbc,
      (perms(J["due"]), perms(J["report"]), "STATE_BRANCH" in clc, "STATE_BRANCH" in ev, "STATE_BRANCH" in pbc))

# ================================================================ all three workflows
for k, t in TEXT.items():
    check(f"{FILES[k].name}: no 'pull_request_target' trigger", "pull_request_target" not in code(t))
    bad = [r.strip().splitlines()[0][:60] for r in run_blocks(code(t)) if "${{" in r]
    check(f"{FILES[k].name}: no workflow expression is pasted into a shell script (values reach the shell through env)", not bad, bad)
    us = uses(t); pinned = [(u, c) for u, c in us if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}", u) and re.search(r"#\s*v\d+(\.\d+)*", c)]
    todo = [(u, c) for u, c in us if "TODO pin to commit SHA" in c]
    check(f"{FILES[k].name}: every action is pinned to a full 40-character commit with its version in a comment (or listed as a TODO)", us and len(pinned) + len(todo) == len(us), [u for u, c in us if (u, c) not in pinned + todo])
    check(f"{FILES[k].name}: ... none is left as a TODO or on a movable tag", not todo and not [u for u, _ in us if re.search(r"@(v\d|main|master|latest)", u)], todo)
    check(f"{FILES[k].name}: every job has a time limit and runs on a named image", all(re.search(r"^    timeout-minutes:\s*\d+", code(b), re.M) and re.search(r"^    runs-on:\s*ubuntu-\d\d\.\d\d", code(b), re.M) for b in jobs(t).values()))
allpins = {}
for t in TEXT.values():
    for u, c in uses(t): allpins.setdefault(u.split("@")[0], set()).add(u.split("@")[1])
check("each action is pinned to the same commit wherever it is used", all(len(v) == 1 for v in allpins.values()), {k: sorted(v) for k, v in allpins.items() if len(v) > 1})
check("only actions of GitHub itself and the official Claude Code action are used", set(allpins) <= {"actions/checkout", "actions/setup-python", "actions/upload-artifact", "actions/download-artifact", "anthropics/claude-code-action"}, sorted(allpins))

# ================================================================ CI
I = TEXT["ci"]; IC = code(I); IJ = jobs(I)
check("CI runs on pull requests and pushes", {"pull_request", "push"} <= on_of("ci") and "schedule" not in on_of("ci"), on_of("ci"))
check("CI can only read the repository and uses no secret and no environment: a pull request from a fork gets nothing", bool(re.search(r"^permissions:\s*\n\s+contents:\s*read\s*$", IC, re.M)) and not secrets_in(I)
      and "environment:" not in IC and not any(perms(b) for b in IJ.values()) and "write" not in " ".join(key_block(IC, "permissions", 0)))
check("CI installs the locked dependency set with its hashes", "--require-hashes --only-binary :all: -r origin_plot_app/requirements.lock" in IC)
check("CI runs the tests without a display, with the system libraries Qt needs", all(x in IC for x in ("QT_QPA_PLATFORM: offscreen", "MPLBACKEND: Agg", 'OPS_NO_OPEN: "1"', "libegl1", "libxkbcommon0", "libdbus-1-3", "fonts-dejavu-core")))
check("CI has the static check, the secret scan, the pin check and the dependency audit", all(x in IC for x in ("python -m compileall", "python3 tools/secret_scan.py .", "tools/dependency_inventory.py --check", "pip_audit -r origin_plot_app/requirements.lock")))
check("CI fails when a private or personal file is tracked", "No private or personal file is tracked" in IC and "ops_private" in IC and "examples_your_data" in IC)
check("the tests run in four groups that together cover every tests/test_*.py, and a group with a failing file fails", "group: [0, 1, 2, 3]" in IC and "i % 4" in IC and "ls tests/test_*.py" in IC and '[ "${#failed[@]}" -eq 0 ]' in IC and "fail-fast: false" in IC)
check("no test is left out of the groups and no job is allowed to fail quietly", "then continue; fi" not in IC.replace('if [ "$mine" -ne "$GROUP" ]; then continue; fi', "") and "continue-on-error" not in IC and "known-failure" not in IJ, sorted(IJ))
check("... the fixture it needs is in the repository", (ROOT / "xrd_scan_generator" / "tests" / "fixtures" / "SAMPLE.xrdml").is_file())

# ================================================================ release
R = TEXT["release"]; RC = code(R); RJ = jobs(R)
check("the release is started by hand only: not by a schedule, a push, a tag or a pull request", on_of("release") == {"workflow_dispatch"}, on_of("release"))
check("the release jobs are verify, build and sign; signing waits for both others", list(RJ) == ["verify", "build", "sign"] and "needs: [verify, build]" in RJ.get("sign", "") and "needs: verify" in RJ.get("build", ""))
check("the signing job runs in the protected environment 'release'", bool(re.search(r"^    environment:\s*release\s*$", code(RJ["sign"]), re.M)))
check("... and it is the only job of the repository that names an environment", "environment:" not in code(RJ["verify"]) and "environment:" not in code(RJ["build"]) and "environment:" not in CC and "environment:" not in IC)
check("the signing key is named in the signing job only, in the environment of one step", secrets_in(RJ["verify"]) == set() and secrets_in(RJ["build"]) == set() and secrets_in(R) == {"OPS_RELEASE_SIGNING_KEY"}
      and code(RJ["sign"]).count("OPS_RELEASE_SIGNING_KEY: ${{ secrets.OPS_RELEASE_SIGNING_KEY }}") == 1 and "OPS_RELEASE_SIGNING_KEY" not in CC and "OPS_RELEASE_SIGNING_KEY" not in IC)
check("... the jobs that build and test code can only read; only the signing job can create the draft", perms(RJ["verify"]) == {"contents": "read"} and perms(RJ["build"]) == {"contents": "read"} and perms(RJ["sign"]) == {"contents": "write"}
      and bool(re.search(r"^permissions:\s*\{\}\s*$", RC, re.M)))
check("the release builds the clean 'friends' release, writes the manifest, signs it and verifies it as the app will",
      "tools/build_release.py --profile friends --out dist" in RC and "tools/sign_release.py make-manifest" in RC and "tools/sign_release.py sign dist/manifest.json" in RC and "tools/sign_release.py verify dist" in RC
      and RC.index("sign_release.py sign dist") < RC.index("sign_release.py verify dist") < RC.index("gh release create"))
check("... the tests, the secret scan and the dependency audit run again before anything is built", all(x in code(RJ["verify"]) for x in ("ls tests/test_*.py", "tools/secret_scan.py", "pip_audit", "compileall")))
check("... only from the default branch, and only for the version that is in the code", "Only from the default branch" in RC and "VERSION" in RC and "smart_plots.py" in RC)
check("the result is a DRAFT with the zip, manifest.json and manifest.sig; nothing publishes it and an existing version is never replaced", "gh release create" in RC and "--draft" in RC and "dist/manifest.json dist/manifest.sig" in RC
      and "exists already" in RC and not re.search(r"--draft=false|gh release edit|gh release upload|--clobber|gh release delete", RC))

# ================================================================ the files around the workflows
D = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8") if (ROOT / ".github" / "dependabot.yml").is_file() else ""
check("Dependabot is set for the Python packages of the app and for the actions, weekly, a few pull requests at a time",
      bool(re.search(r"package-ecosystem:\s*pip\s*\n\s+directory:\s*/origin_plot_app", D)) and bool(re.search(r"package-ecosystem:\s*github-actions\s*\n\s+directory:\s*/\s", D))
      and D.count("interval: weekly") == 2 and [int(x) for x in re.findall(r"open-pull-requests-limit:\s*(\d+)", D)] == [3, 3])
P = (ROOT / "automation" / "cycle_prompt.md").read_text(encoding="utf-8") if (ROOT / "automation" / "cycle_prompt.md").is_file() else ""
for name, words in (("the evidence is untrusted data that cannot change the instructions", ("untrusted data", "cannot change")), ("a generated, clearly labelled, non-sensitive fixture", ("GENERATED TEST FIXTURE", "non-sensitive")),
                    ("the smallest change and a regression test that failed first", ("smallest change", "regression test", "see it fail")), ("the related graph families", ("related graph families",)),
                    ("how the tests are run", ("python3 tests/<file>.py", "check_banned.py --all")), ("never the version, the release, signing or workflow files", ("Do not change the app version", ".github/", "sign_release.py")),
                    ("no commit, push or merge by the agent", ("Do not commit, push, open, merge",)), ("a report and no change when nothing is justified or reproducible", ("Changing nothing is a correct result", "cannot reproduce")),
                    ("preferences are data, not code", ("A\n   preference stays data", ))):
    check(f"the coding prompt says: {name}", all(w in P for w in words), [w for w in words if w not in P])
check("the files the prompt forbids are the files the workflow refuses", all(x in pbc for x in ("update_trust", "update_verify", "self_update", "check_banned", "secret_scan", "dependency_inventory", "WHATS_NEW", "CITATION", "SECURITY", "PRIVACY", "backend/"))
      and all(x in P for x in ("update_trust.py", "update_verify.py", "self_update.py", "check_banned.py", "secret_scan.py", "dependency_inventory.py", "WHATS_NEW.txt", "CITATION.cff", "SECURITY.md", "PRIVACY.md", "`backend/`")))
ex = ROOT / "automation" / "cycle_state.example.json"
try:
    import cycle_due
    st = json.loads(ex.read_text(encoding="utf-8")); cycle_due.validate(st); ok = st["schema"] == "opstudio.cycle/1" and st["timezone"] == "Europe/Stockholm"
except Exception as e: ok = False; st = repr(e)
check("the example state file is a valid state for tools/cycle_due.py", ok, "" if ok else st)

# ================================================================ the backend files
B = ROOT / "backend" / "supabase"
sql = (B / "migrations" / "0001_learning.sql").read_text(encoding="utf-8") if (B / "migrations" / "0001_learning.sql").is_file() else ""
sqlc = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
tables = re.findall(r"create table (public|private)\.([a-z_]+)", sqlc)
check("the migration makes the seven tables the desktop adapter expects (and two internal ones)", sorted(t for s, t in tables if s == "public") == sorted(["labs", "lab_members", "community_reviewers", "contributions", "contribution_feedback", "tombstones", "evidence"])
      and sorted(t for s, t in tables if s == "private") == ["rate_log", "tombstone_scope"], tables)
check("row-level security is enabled on every one of them", all(re.search(rf"alter table {s}\.{t}\s+enable row level security", sqlc) for s, t in tables), [t for s, t in tables if not re.search(rf"alter table {s}\.{t}\s+enable row level security", sqlc)])
check("nothing is granted to the role of visitors who are not signed in, and no policy is written for it", not re.search(r"grant[^;]*\bto\b[^;]*\banon\b", sqlc) and not re.search(r"create policy[^;]*\bto\s+anon\b", sqlc) and not re.search(r"\bto\s+public\b(?!\.)", sqlc))
check("every policy is for signed-in users only", len(re.findall(r"create policy", sqlc)) == len(re.findall(r"create policy \w+ on public\.\w+ for (?:select|insert|update|delete) to authenticated", sqlc)) >= 12)
cfg = (B / "config.example.json").read_text(encoding="utf-8") if (B / "config.example.json").is_file() else "{}"
try: cj = json.loads(cfg)
except Exception: cj = {}
check("the example configuration for the desktop holds a URL and a public key as placeholders, and nothing else that could be a key",
      set(k for k in cj if not k.startswith("_")) == {"url", "anon_key"} and "YOUR" in cj.get("url", "") and "YOUR" in cj.get("anon_key", "") and not re.search(r"eyJ[A-Za-z0-9_-]{10,}|sb_secret_[A-Za-z0-9]{8,}|sb_publishable_[A-Za-z0-9]{8,}|service_role\"\s*:", cfg), sorted(cj))
for doc in ("docs/FORTNIGHTLY_CYCLE.md", "docs/SHARED_LEARNING_SETUP.md", "automation/README.md", "backend/supabase/README.md"):
    t = (ROOT / doc).read_text(encoding="utf-8") if (ROOT / doc).is_file() else ""
    check(f"{doc} is there and says what has not run", bool(t) and bool(re.search(r"has (not|never) (been )?(run|executed|deployed)|not deployed|never run|have never run|NOT DEPLOYED|was not invoked|has never been invoked", t)), len(t))
    check(f"{doc} holds nothing shaped like a key", not re.search(r"eyJ[A-Za-z0-9_-]{20,}\.|sb_secret_[A-Za-z0-9]{8,}|sk-ant-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY", t))

print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

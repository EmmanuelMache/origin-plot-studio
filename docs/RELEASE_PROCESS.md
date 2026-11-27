# Release process

How a release of Origin Plot Studio is made: **check the packages, scan, build clean, review, sign, publish**.
Each step is a command in this repository. Steps marked **OWNER** cannot be done by a coding agent or an ordinary
pull-request job: they need the owner's decision or the owner's signing key.

A release is never made by zipping a working folder or an installed copy. Those hold settings, sessions, logs and
sometimes research data.

Nobody is ever asked to switch off Windows Defender, SmartScreen, certificate (TLS) checking or any other protection
of the operating system - not to build, not to install, not to update. If a step seems to need that, the step is
wrong; stop and fix the step.

## The steps

Run everything from the top of the repository, on the commit that is to be released.

### 1. The package set (SEC-07)

```
python tools/dependency_inventory.py --check
```

Says whether every requirement in `origin_plot_app/requirements.txt` is an exact pin (`==`) and whether
`origin_plot_app/requirements.lock` holds the same versions, the transitive packages and a SHA-256 for every package.

Only when a version is changed on purpose (needs the network):

```
python tools/dependency_inventory.py --lock      # resolves the full set, reads the hashes from pypi.org
python tools/dependency_inventory.py --audit     # advisory database; uses pip-audit when it is installed
```

`--audit --audit-python <python of a tools environment>` uses a pip-audit that is kept apart from the release set.
Both commands rewrite `docs/DEPENDENCIES.md` and `docs/dependencies.json`. Review the diff of the lock, run the tests
with exactly that set installed (`pip install --require-hashes --only-binary :all: -r origin_plot_app/requirements.lock`
in a fresh environment), commit the four files together.

**OWNER:** make the lock again on the Windows machine the release is tested on and compare. The lock in the
repository was resolved on Linux; the Windows-only pin (pywin32) was looked up, not installed.

### 2. Tests

Run the test scripts in `tests/` with the locked set. For this process in particular:

```
python tests/test_security_imports.py
python tests/test_packaging.py
```

### 3. Credentials in the folder and in the history

```
python tools/secret_scan.py --tracked            # the files Git tracks
python tools/secret_scan.py --history            # plus every version of every file Git stores, all branches
```

The scan prints the place and the **name** of a pattern, never the text that matched. Exit code 1 means something was
found. A finding in the history means the credential has to be **revoked at the service that issued it** - deleting
the file, or rewriting history, does not take a published credential back.

**OWNER:** decide what to do with a finding. Revoking or rotating a real credential and rewriting history are
decisions of the owner; no tool here does either.

### 4. The clean build

```
python tools/build_release.py --profile friends --out dist
```

- The files are read from the **commit** (`--ref`, default `HEAD`), not from the folder. Uncommitted files and
  changes cannot get in.
- A file gets in only if it is on the list `ALLOW` in `tools/build_release.py` (the program, `opstudio/`, the
  gallery pictures, `examples_synthetic/`, the requirement files, README, HOW_TO_INSTALL, SECURITY.md, PRIVACY.md,
  LICENSE) and does not match an exclusion rule (settings, sessions, logs, lessons, learned formats, `*.sqlite3`,
  credentials, the outbound policy, `pdf_names.json`, caches, `__pycache__`, project archives, private templates,
  tests, tools, `.github`, `backend`).
- `--profile friends` writes `security_profile.json` = `{"profile": "friends"}` into the build: local-only at first
  start, unsigned updates refused, no client-side AI repair. `--profile owner` is the developer's own copy.
- After building, the folder and the zip are checked against the exclusion rules again, the secret scan runs over the
  build in its strict form, and - when the owner's private term list is on the machine (`OPS_BANNED_TERMS`) - the
  private-term check runs too. Any hit ends the build with exit code 1 and removes the zip.
- The zip is the same, byte for byte, for the same commit and the same Python/zlib. The tool prints its SHA-256 and
  writes `<name>.zip.sha256`.

The result:

```
dist/Origin_Plot_Studio_<version>/          the release as a folder
dist/Origin_Plot_Studio_<version>.zip       the release
dist/Origin_Plot_Studio_<version>.zip.sha256
```

### 5. Review of what ships - OWNER

Open `dist/Origin_Plot_Studio_<version>/RELEASE_CONTENTS.md`. It lists every file with size and SHA-256; the data
files, documents and pictures come first.

**OWNER:** confirm for each data file and picture that it is synthetic or approved for distribution: no unpublished
measurements, no sample names of real work, no pictures of confidential results. The column "Carries" names the kind
of metadata a file holds (an author field, comments, text chunks of a picture) without showing the value; open the
file where it says REVIEW. The build cannot judge whether a dataset is synthetic. A person has to.

If something must not ship: remove it from the repository or from `ALLOW`, commit, build again.

### 6. Signing - OWNER, with the owner's key

The build is **not signed** by `build_release.py`. Signing is a separate tool, `tools/sign_release.py`, and takes the
zip from step 4 as it is:

```
python tools/sign_release.py make-manifest dist/Origin_Plot_Studio_<version>.zip --version <version> --key-id <key id>
python tools/sign_release.py sign dist/manifest.json --private-key-file <path outside the repository>
python tools/sign_release.py verify dist
python tools/sign_release.py bundle dist          # optional: one file to pass on by hand
```

`manifest.json` states the name, size and SHA-256 of the zip, the version, the systems and the minimum Python;
`manifest.sig` is the Ed25519 signature over the exact bytes of `manifest.json`. The app verifies both with the
public key in `origin_plot_app/update_trust.py` before it unpacks anything. See the text at the top of
`tools/sign_release.py` and `origin_plot_app/update_verify.py` for the exact rules.

**OWNER:**

- Create the production signing key on a machine you control and keep the private half outside the repository,
  outside CI jobs that run pull-request code, and out of reach of coding agents.
- Put the **public** half into `origin_plot_app/update_trust.py` (a reviewed commit) before the first signed release.
- A test key is for tests only. A release signed with a test key is not a release.

After signing, do not rebuild: the manifest names this exact zip. If anything changes, build and sign again.

### 7. Publish - OWNER

Create the release on GitHub for the tag of the commit and attach exactly three files, under exactly these names:
`Origin_Plot_Studio_<version>.zip`, `manifest.json`, `manifest.sig`. Put the SHA-256 of the zip into the release
notes so that people who download by hand can compare it.

Then, on a clean Windows user account without administrator rights: download, check the SHA-256, unzip, run
`Setup.bat`, start the app, import a file, plot, save and reopen a project, export, uninstall. This check has to be
done on Windows by a person; nothing in this repository replaces it.

### 8. Repository settings - OWNER

These are settings of the GitHub repository or account, not files: private vulnerability reporting (SECURITY.md
relies on it), secret scanning with push protection, Dependabot alerts, code scanning where available, protection
of the release branch, and Actions pinned to reviewed commit ids. Jobs that run code from pull requests must not have
the signing key or any write-capable release credential.

## What a release contains and what it does not

Contains: the program files, `opstudio/`, the gallery pictures, the demo data in `examples_synthetic/`, the pinned
requirement files, `README.md`, `HOW_TO_INSTALL.txt`, `SECURITY.md`, `PRIVACY.md`, `LICENSE`, the generated
`RELEASE_CONTENTS.md` and `security_profile.json`.

Never contains: `settings*.json`, `last_session.json`, `last_run_log.txt` and the other logs,
`assistant_lessons.txt`, `learned_formats.json`, `*.sqlite3`, `credentials.json`, `outbound_policy.json`,
`pdf_names.json`, caches, `__pycache__`, project archives (`*.opsproject`), Origin projects, private templates and
recipes, tests, tools, `.github`, `backend`, development notes, the signing key.

## Recorded results

What was actually run while this process was set up, and what was not. These are results of one day on one machine,
not a statement about later versions.

Environment: Linux x86_64, Python 3.13.18, pip 24.0, 2026-11-26, branch `integrate/learning-security` at commit
`7bc4610` plus the uncommitted work of that branch.

| Check | Result |
| --- | --- |
| Secret scan, tracked files (`--tracked`) | 634 files read; **0 findings**; 1 obvious test value not counted (a dummy key in a test) |
| Secret scan, whole working folder (also files not yet committed) | 1163 files read; **0 findings**; 16 obvious test values not counted (dummy keys in tests) |
| Secret scan, Git history (`--history`) | 1545 file versions in 44 commits (all refs of this copy; not a shallow copy); **0 findings**; 6 obvious test values not counted (the same test line in 6 versions) |
| Secret scan of a trial release build (strict; the tree as it was at that hour) | 526 files; **0 findings** |
| Private-term check of the trial build (`OPS_BANNED_TERMS`) | 526 files; 0 with a private term |
| Lock with hashes | made; 36 packages (14 direct, 22 transitive), 890 SHA-256 values read from pypi.org through the network of the build machine |
| Install of the lock, `--require-hashes --only-binary :all:`, fresh environment ("locked environment") | succeeded on Linux / Python 3.13; 36 packages; `pip check`: no broken requirements |
| Tests in the locked environment | 12 test scripts, all passed: `test_security_imports` (172 checks), `test_packaging` (73), `test_related` (86), `test_workbook_editing` (85), `test_workbench_core` (46), `test_workbench_ui` (15), `test_workspace_main` (83), `test_thermal_photo` (18), `test_ribbon_sketch` (37), `test_gallery_graphs` (34), `test_starthere` (15), `test_starthere_parity` (54). The rest of the suite was **not** run there. |
| Vulnerability check (pip-audit 2.10.1) | first run: 42 advisories, all for Pillow 12.3.0 (fixed in 13.0.0). Pillow was then pinned to 13.0.0. Second run: **0 known vulnerabilities in 36 packages** (pywin32, a Windows-only package, looked up in the advisory data of pypi.org) |
| Trial build, twice from the same commit | the same SHA-256 both times |

Limits of these results:

- The scan looks for known credential patterns and long random values assigned to credential-like names. It cannot
  show that no secret of another shape exists, it does not read pictures, and it can only read the history that is in
  this copy of the repository.
- The trial build was made from a temporary copy of the tree, because the new files were not committed yet. It is
  not a release.
- The hashes in the lock were read through the HTTPS proxy of the build environment. Making the lock again on the
  release machine (step 1) is the independent check.
- **Not run:** anything on Windows - `Setup.bat`, `Run_Origin_Plot_App.bat`, `setup.pyw` with its window, the
  shortcuts, the entry in Windows' list of apps, the uninstall, an install of the lock on Windows, pywin32, OriginPro.
  The Python parts of the installer were run on Linux with pip replaced by a stand-in (`tests/test_packaging.py`).
- **Not done, by decision:** no credential was rotated, no history was rewritten, nothing was signed with a
  production key, nothing was published.

## Open points for the owner

1. Create the production signing key; put its public half into `update_trust.py`.
2. Review `RELEASE_CONTENTS.md` of the first real build: 15 data files and documents and about 170 pictures ship with
   the program. The demo files in `examples_synthetic/` look generated (plain column names, no instrument header
   blocks, no author field in the workbooks), but the repository holds no script that produces them, so their origin
   cannot be shown from the repository alone.
3. Run the whole test suite in an environment made from the lock (only 12 scripts were run that way; the main test
   environment has Pillow 12.3.0 and no xlrd, python-calamine, tzdata or keyring), and on Windows.
4. Make the lock again on Windows and compare; test xlrd, python-calamine, tzdata and pywin32 there.
5. Switch on private vulnerability reporting, secret scanning and push protection for the repository.
6. Do the clean-account Windows check of step 7.

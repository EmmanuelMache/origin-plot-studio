# Security

Origin Plot Studio is a desktop program for one user on one computer. This page says which versions get security
fixes, how to report a problem privately, and what the program's security measures cover and do not cover.

Nothing here is a certification. The program has not been audited or certified by a third party.

## Supported versions

| Version | Security fixes |
| --- | --- |
| the newest release (currently 5.58.x) | yes |
| older releases | no - update to the newest release |

A fix is published as a new release. There are no patches for older versions.

## Reporting a vulnerability

Please report it privately, not in a public issue:

1. Open the GitHub repository of this program - the page this file belongs to, and the page the releases are
   downloaded from (`origin-plot-studio`).
2. Choose **Security** > **Report a vulnerability** (GitHub's private vulnerability reporting). The address of that
   form is the address of the repository followed by `/security/advisories/new`.

Only the maintainer sees such a report. Please include the version (Help > About), what you did, what happened, and
what you expected. Do **not** attach research data, project archives, settings files or keys. If files are needed to
show the problem, use made-up data, or the sanitized diagnostic file the program can write (see `PRIVACY.md`,
"Diagnostic file") after reading it yourself.

If the **Report a vulnerability** button is not shown, private reporting is not switched on for the repository yet.
In that case open a public issue that says only "I would like to report a security problem privately" - without any
detail - and wait for the maintainer to open a private channel.

There is no bug bounty. Reports are read by one maintainer in their spare time; expect an answer within about two
weeks.

## What the security measures cover

These are properties of the code in this repository. Each is checked by automated tests with made-up data
(`tests/`); none of them was verified by an outside party.

- **What leaves the computer.** One outbound policy (`outbound_policy.py`) is asked before the program opens a
  connection: update check, update download, AI assistant, web search, diagnostics, shared learning. In local-only
  mode none of these is started. `PRIVACY.md` lists what each level allows.
- **Keys.** API keys and tokens are kept by Windows data protection (DPAPI) for your Windows account, or by the
  system keyring on other systems, or only in memory for the session. They are not written to disk as plain text and
  are not part of projects, exports or the diagnostic file (`secure_store.py`).
- **Updates.** A release is described by a signed manifest (Ed25519). A build for other people (the "friends"
  profile) refuses an update without a valid signature (`update_verify.py`, `tools/sign_release.py`).
- **Imported projects.** A `.opsproject` file is treated as untrusted data: size, count and nesting limits, strict
  checks of every name inside it (also the forms that are dangerous on Windows), unpacking into a staging folder under
  names the program makes itself, removal of the staging folder on any failure or cancel. A project cannot bring
  credentials, update settings, privacy settings, the security profile or program paths
  (`workspace_projects.py`, `tests/test_security_imports.py`).
- **Exported spreadsheets.** Text that a spreadsheet program would run as a formula is written as text; numbers are
  not changed (`safe_export.py`).
- **Dependencies.** Every Python package is pinned to one exact version; the complete set with SHA-256 hashes is in
  `origin_plot_app/requirements.lock`, and Setup installs from it with hash checking. Starting the program installs
  nothing without asking (`docs/DEPENDENCIES.md`).
- **Releases.** A release zip is built from a reviewed list of files of one commit, checked against exclusion rules
  and scanned for credentials (`tools/build_release.py`, `docs/RELEASE_PROCESS.md`).

## What they do not cover

- **Your computer and your account.** Anyone who can use your Windows account can read your files, your projects and
  the keys Windows protects for that account. Use a password on the account and disk encryption (BitLocker or
  similar) where the data requires it. Protecting keys does not encrypt your measurement data.
- **Files you open.** Workbooks, text files and pictures are read with third-party libraries (pandas, openpyxl,
  Pillow and others). They are pinned and checked against the advisory database at release time, but a fault in one
  of them is outside this program's control. Macros in workbooks are never run by the program.
- **OriginPro.** Graphs are drawn by sending commands to your own OriginPro installation. Its security is its own.
- **The service you connect.** When you link an AI service and choose a level above local-only, the text and data
  that level allows are sent to that service and are then subject to its terms. The program cannot take them back.
- **Code the program runs as you.** The program is ordinary Python running with your rights. There is no sandbox.
  The trial check of an update runs the new version on your computer after its signature was verified; it is a
  comparison of results, not isolation.
- **An unsigned copy.** A copy that did not come from a signed release, or that someone changed, is not covered by
  any of the above.
- **Shared learning.** It is switched off and no shared service is deployed. Nothing about it has been
  security-tested against a real server.

## For people who install it

- Install only a release from the repository's Releases page. Compare the SHA-256 of the zip with the one published
  there.
- You should never be asked to switch off Windows Defender, SmartScreen, certificate checking or any other protection
  of the system to install or update this program. If any instruction asks for that, do not follow it and report it.
- No administrator rights are needed. Setup installs for your user only.

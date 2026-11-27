# Privacy

Origin Plot Studio works on your computer with your files. This page says what it stores, where, what can leave the
computer and when, how long things are kept, and how to delete them or switch everything off.

Short version: in **local-only mode nothing leaves the computer**. A build made for other people starts in that mode.
Every connected feature is optional and has to be switched on.

## What is stored on your computer

The program has no account and no server of its own. Everything below is a file on your disk.

| What | Where | Contains |
| --- | --- | --- |
| Settings | `settings.json`, `settings_modern.json` in the program folder (`%LOCALAPPDATA%\Programs\Origin Plot Studio`) | window and graph settings, the list of your projects (names, the paths of their files, saved graph settings), recent folders |
| Last session | `last_session.json` in the program folder | which files and graphs were open, sample names, graph settings |
| Logs | `last_run_log.txt`, `error_log.txt`, `startup_error.txt`, `console_output.txt`, `slow_log.txt` in the program folder | messages and error texts; they can contain file names, sample names and paths |
| Imported projects | `project_data\` in the program folder (beside the settings file) | copies of the input files of projects you imported; tables the program derived |
| Your private folder | `%APPDATA%\OriginPlotStudio\my_templates` (or the folder named by `OPS_PRIVATE_DIR`) | your phase files, style presets, templates, `defaults.json`, the privacy choices (`outbound_policy.json`), names learned from PDF cards (`pdf_names.json`) |
| Keys | `credentials.json` in the private folder, encrypted by Windows for your account (DPAPI). On other systems: the system keyring, or memory only | API keys and tokens you entered. Never plain text. |
| Assistant memory | `assistant_lessons.txt`, `learned_formats.json` in `%APPDATA%\OriginPlotApp` | what you taught the assistant and file layouts it learned; they can name files and columns |
| Your phase library | `%APPDATA%\OriginPlotApp\phase_library` | phases you added |
| Results | the results folder you choose (default `Documents\Origin plot results`) | graphs, tables, Origin projects, reports you export |
| Backups before an update | `Origin Plot Studio program backups` in your user folder | the program files as they were before an update (no settings, no sessions) |

Your original measurement files are read and never changed.

None of these files is encrypted by the program, except the keys. Use the protection of your Windows account and
disk encryption if your data needs it.

## What can leave the computer

Only what you switch on. One setting - the **outbound level** - decides it for every connected feature, and it is
checked at the moment a request would be sent, not only in the window (Settings > Privacy, the "Privacy and connections"
window).

| Level | May leave the computer |
| --- | --- |
| **Local-only** | Nothing the program starts itself: no update check, no update download, no AI assistant, no web search, no diagnostics, no shared learning. |
| **Minimal** | Your question to the assistant and generic information (the kind of data, the roles of columns). Names of samples, graphs and files are replaced by stand-ins ("Sample 1", "File 2"), folders by `<folder>`. No measurements, no results. Update checks if that switch is on. |
| **Approved metadata** | In addition the real labels and the structure: column names, graph kinds, counts. Still no measurements, results, pictures or documents. |
| **Approved scientific content** | In addition the measurements, results, pictures and documents you select, sent to the service you chose. |

A higher level includes the lower ones. Beside the level there is one switch per channel; a channel that is off sends
nothing at any level:

| Channel | What it contacts | Default |
| --- | --- | --- |
| Look for a new version | the release page of the program's repository on GitHub; the request asks for the list of releases and carries none of your data | on, except in local-only mode |
| Download an update | the same place, when you ask for the update | on, except in local-only mode |
| AI assistant | the AI service **you** link with **your own** key (the address is shown when you link it); remote services only over HTTPS | on, except in local-only mode; does nothing until you link a service |
| Web search of the assistant | public literature and encyclopaedia services (OpenAlex, Semantic Scholar, Crossref, arXiv, Wikipedia / Wikimedia Commons); only search words are sent, never a file or data | on, except in local-only mode |
| Diagnostics | nothing - see "Diagnostic file" | **off** |
| Shared learning | a lab or community service | **off** - and no such service is deployed |

Defaults: a build for other people ("friends" profile) starts **local-only**. The developer's own copy starts at
**Minimal**. Setting the environment variable `OPS_LOCAL_ONLY=1` forces local-only mode whatever is stored.

What is never sent, at any level: your keys (a key goes only to the service it belongs to, as the login for that
service), your settings files, your projects as a whole, and anything in the background that you did not ask for.

The program has no telemetry, no usage statistics and no crash reporting.

### The AI service

When you link an AI service, what the level allows is sent to **that service** and handled under **its** terms and
retention rules, not the program's. The program cannot delete it there. Use the "Approved scientific content" level
only for work you are allowed to share with that service.

### Shared learning

Shared learning (exchanging learned recipes with other people) is **off by default and is not a deployed service**.
There is no server to send to. Personal learning - what the program remembers about your own files - stays on your
computer and works in local-only mode.

## Diagnostic file

To report a problem you can let the program write a diagnostic file (`diagnostics.build_bundle`). It is a zip **on
your disk**; the program does not send it. It holds: the versions of the program, Python and the packages, the system
type, the security profile and outbound level, the list of installed program files with checksums, the kinds of
errors in the logs, and the last log lines **after** keys, paths, known sample and file names and rows of numbers
were replaced. It holds no measurement data, no project files, no settings and no keys.

`MANIFEST.txt` inside the zip lists exactly what is in it. Read it, and `log.txt`, before you send the file: a name
the program had never seen can still be in a log line.

## Portable projects and exports

A project you export (`.opsproject`) contains **copies of its input files** and its saved graph settings - that is
its purpose. Send it only to people who may have that data. It does not contain keys, privacy settings or program
settings. Tables and graphs you export contain your data and labels as you see them.

## How long things are kept

The program deletes nothing on its own and sets no time limits. Settings, sessions, logs, projects and results stay
until you delete them. Logs are overwritten or grow as described by their names (`last_run_log.txt` holds the last
run).

## How to delete

- **A project:** right-click it > Remove selected. This removes the project from the list. Copies of an imported
  project's files stay in `project_data\` in the program folder; delete that project's folder there to remove them.
  Your original files are not touched.
- **Keys:** remove the key where you entered it (the assistant's connection settings), or delete `credentials.json`
  in the private folder. Also revoke the key at the service if you no longer use it.
- **Assistant memory:** delete `assistant_lessons.txt` and `learned_formats.json`.
- **Session and logs:** delete `last_session.json` and the log files in the program folder.
- **Everything:** uninstall the program (Windows Settings > Apps > Origin Plot Studio > Uninstall), then delete
  `%APPDATA%\OriginPlotStudio`, `%APPDATA%\OriginPlotApp`, the backups folder and, if you want, your results folder.
  Uninstalling removes the program folder with the settings, the session, the logs and `project_data\` in it. It does
  not remove the Python packages Setup installed.

## How to switch everything off

Settings > Privacy > **Local-only**. Or start the program with the environment variable
`OPS_LOCAL_ONLY=1`. In this mode the program opens no connection for updates, AI, web search, diagnostics or shared
learning. Reading files, analysis, graphs, projects, personal learning and OriginPro on this computer work as always.

Updates then have to be installed by hand from a release file (Help > Install an update from a zip file); its
signature is checked in the same way.

## Changes to this page

This page describes version 5.58.x. It is changed together with the program when what is stored or sent changes.

# Validation results — Origin Plot Studio 5.57.0

Date: 25 November 2026. Run on the final merged code of branch `integrate/project-workbench`.

**Where:** a Linux container, Python 3.13, **PySide6 (the real toolkit of the app)** with `QT_QPA_PLATFORM=offscreen`,
NumPy, pandas, SciPy, matplotlib, openpyxl. **Not Windows. No Origin.** Everything that needs Origin went through the
app's Origin driver in dry-run mode (it writes the LabTalk commands and the worksheets). The earlier validation of the
delivered update (228 checks, seven suites, on a Qt 5 stand-in) is prior evidence only; all of it was run again here.

`python -m compileall -q origin_plot_app tests`: clean.

## The seven suites named for this update

| Suite | Passed | Failed |
|---|---:|---:|
| Workbench core (detection, fit columns, merges, project archives) — `tests/test_workbench_core.py` | 44 | 0 |
| Desktop workflow (real widgets) — `tests/test_workbench_ui.py` | 15 | 0 |
| Template engine and Origin driver (dry run) — `tests/test_opstudio.py` | 63 | 0 |
| Composed figures (workbooks of figures) — `tests/test_figures_general.py` | 37 | 0 |
| Analysis tools (all 44) — `tests/test_analysis_tools.py` | 17 | 0 |
| HighScore / XRD workflows — `tests/test_highscore.py` | 27 | 0 |
| Workbook graph types (26) — `tests/test_gallery_graphs.py` | 34 | 0 |
| **Total** | **237** | **0** |

The workbench core suite has 9 checks more than the delivered one (fit columns by name, peak lists, the wider list of
data types, a file with no table, the template example cache).

## Every test file

35 files, **1067 checks passed, 1 failed**. The one failure is `tests/test_xrd_generator.py`, a check that
fails only with the bundled fixture and has done so since 5.51.0; nothing here touches it. The table of all files is in
`TEST_REPORT.md`, section 2.

New in this integration: `tests/test_starthere_parity.py` (43 checks) — everything the Start here page did at 5.56.0
(a file without a project, what kind it is, the graphs that fit, picking one, removing a file, projects: several at
once, tags in Your graphs, search, missing files, rename, close, delete) checked on the new page, plus the header
buttons and tooltips.

## Nothing taken away

* **Commands and menus.** The merged window was compared with the window of 5.56.0: no entry of the File (30), View (45),
  Tools (27) or Help (9) menus is missing, none of the 33 keyboard shortcuts, and no command of the command search
  other than five buttons of the old Start here page that have a renamed equivalent on the new one.
* **The app's own update check** (`self_update.check`, merged program against 5.56.0): the same Origin commands for
  **10 of 10** example files; every program file of 5.56.0 is present.

## All graph types

`tools/audit_graph_operations.py` drew each of the 122 Analysis templates (from its own example) and each of the 26
workbook graph types (from its test workbook) and tried every per-graph control on it. Result in
`docs/GRAPH_OPERATIONS_AUDIT.md`: 148 of 148 draw and go through the Origin driver; markers work on the 118 that have
curves with points, one-panel-only on the 35 with several panels, the zoom inset on the 10 that have one, the difference
and Bragg rows on the 2 pattern-and-fit templates; no control fails where it applies. The catalogue rows marked "Coming"
(213) are not graphs and are not counted.

## The owner's own files

The files that were first identified wrongly were available for this integration (kept outside the repository, named
nowhere in it). Thirteen files — diffraction scans, a fit export, a peak list, thermal runs, an infrared spectrum and a
50-sheet workbook — were added to a project in the merged app: each is identified as what it is; the fit export is drawn
with its own observed, calculated and background columns over its real 2θ range; the peak list is no longer offered the
scan templates. The longest stop of the window while they were read was 0.8 s (12–20 s before the changes described in
`IMPLEMENTATION_AND_TESTS.md`).

## Not verified

* **Windows with native PySide6**: start-up, display scaling, drag and drop from Explorer.
* **A live Origin / COM session.** Only the dry run.

Both need one try on the target computer. The code paths for them are those of 5.56.0.

No user settings, credentials, private projects, temporary extraction folders or test-only adapters are in the commit;
`tools/check_banned.py --all` is clean.

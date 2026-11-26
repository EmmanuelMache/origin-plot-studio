# Validation results — Origin Plot Studio 5.58.3

Date: 26 November 2026. Run on the final merged code of branch `integrate/project-workbench`.

**Where:** a Linux container, Python 3.13, **PySide6 (the real toolkit of the app)** with `QT_QPA_PLATFORM=offscreen`,
NumPy, pandas, SciPy, matplotlib, openpyxl. **Not Windows. No Origin.** Everything that needs Origin went through the
app's Origin driver in dry-run mode (it writes the LabTalk commands and the worksheets). The earlier validation of the
delivered update (228 checks, seven suites, on a Qt 5 stand-in) is prior evidence only; all of it was run again here.

`python -m compileall -q origin_plot_app tests`: clean.

## The seven suites named for this update

| Suite | Passed | Failed |
|---|---:|---:|
| Workbench core (detection, fit columns, merges, project archives) — `tests/test_workbench_core.py` | 46 | 0 |
| Desktop workflow (real widgets) — `tests/test_workbench_ui.py` | 15 | 0 |
| Template engine and Origin driver (dry run) — `tests/test_opstudio.py` | 93 | 0 |
| Composed figures (workbooks of figures) — `tests/test_figures_general.py` | 40 | 0 |
| Analysis tools (all 44) — `tests/test_analysis_tools.py` | 17 | 0 |
| HighScore / XRD workflows — `tests/test_highscore.py` | 43 | 0 |
| Workbook graph types (26) — `tests/test_gallery_graphs.py` | 34 | 0 |
| **Total** | **288** | **0** |

The workbench core suite has 11 checks more than the delivered one (fit columns by name, peak lists, the wider list of
data types, a file with no table, the template example cache, the one-parse workbook cache, the look of every fit graph).

## Every test file

37 files, **1342 checks passed, 1 failed**. The one failure is `tests/test_xrd_generator.py`, a check that
fails only with the bundled fixture and has done so since 5.51.0; nothing here touches it. The table of all files is in
`TEST_REPORT.md`, section 2.

New in this integration: `tests/test_starthere_parity.py` (54 checks) — everything the Start here page did at 5.56.0
(a file without a project, what kind it is, the graphs that fit, picking one, removing a file, projects: several at
once, tags in Your graphs, search, missing files, rename, close, delete) checked on the new page, plus the header
buttons and tooltips.

## Nothing taken away

* **Commands and menus.** The merged window was compared with the window of 5.56.0: no entry of the File (30), View (45),
  Tools (27) or Help (9) menus is missing, none of the 33 keyboard shortcuts, and no command of the command search
  other than five buttons of the old Start here page that have a renamed equivalent on the new one.
* **The app's own update check** (`self_update.check`): the same Origin commands for **10 of 10** example files against
  5.56.0 (the merge) and against 5.57.0 (this version); every program file of both is present.

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

## 5.57.1: the hang and the empty Origin graphs

* **Where the window stopped.** A scripted session on the owner's project (thirteen files, a 3 MB workbook of 50 sheets)
  did each everyday action and recorded the longest time the window could not respond, with what it was doing then.
  In 5.57.0 every stop of more than a second was in one place: `paper_figures.load_sheets`, the whole workbook read
  again from the disk for each drawing of one of its figures. Same computer, before -> after: clicking a figure of the
  workbook 5.3-6.3 s -> 0.3-0.5 s; switching one panel's zoom 10.2 s -> 0.9 s; Undo 10.0 s -> 1.0 s; opening
  Calculations 10.5 s -> 0.06 s; adding the files 68 s -> 30 s (background). No other action stops the window for more
  than 0.6 s in either version. (`tests/test_workbench_core.py` WorkbookCacheTests; `tests/test_figures_general.py`
  "drawn once".)
* **Empty graphs in Origin.** The owner's screenshot showed the layers of a workbook figure at Origin's default axes
  with no curves. The commands the app sends were followed one by one, keeping track of which window is active: in
  5.57.0, 224 plot, axis and legend commands of that figure were sent while a data workbook was the active window;
  now none (`tests/test_opstudio.py`, two checks, and the shipped scripts). **This is a check of the commands, not a
  run in Origin**: it has to be confirmed once in Origin on the owner's computer.

## 5.57.2: the look of a workbook figure in Origin

The owner's screenshots of Origin 2018 showed what 5.57.1 still got wrong. Each fault was traced to a command and
changed; the dry run on the same two figures now gives:

| | 5.57.1 | 5.57.2 |
|---|---|---|
| texts made at a negative position (lost in Origin) | 2 per bar-chart panel | 0 |
| layers for the six-panel figure | 6 (one empty, axes 0-1) | 5 |
| axis titles sent for panels after the first | through `xb` / `yl`, which those layers do not have | as texts, every panel |
| legend entries | none (bar figure), one legend object on the empty layer | 5 and 8 texts with the key of their curve |
| letter size sent for an 8.5 pt axis title | 9 | 13 (two panels), 23 (six panels): x 62 / layer width % |
| line weight sent for a 1.1 pt curve | 1.1 pt | 2.9 pt in a layer 23 % wide (Origin draws it at 0.37) |
| grouped columns | 0.8 wide over a step of 1 (covering each other) | the width of the figure (0.19) |

The factor 62 / width comes from two measurements on those screenshots (a layer 40.5 % of the page wide drew letters at
0.67 of their size, one 23.4 % wide at 0.37). It is an observation of Origin 2018 with its standard template, not a
documented rule. **None of this was run in Origin here.**

PowerPoint and Word: the files written by Export ▸ Send to PowerPoint / Word were read back with python-pptx and
python-docx and converted to PDF by LibreOffice (2 slides, 2 pictures). Not opened in Microsoft Office here.

## 5.58.0: series of files, the Workbook's own columns and tables, peaks

`tests/test_related.py`, 61 checks: the name patterns, DTG against `tga_core.dtg` (identical), the steps of a thermal
run built from three known steps (found at 120, 450 and 720 °C with 2.9, 4.9 and 5.9 % of the 3, 5 and 6 % put in), the
bands of a spectrum built from eight known bands (all eight found and named), the side-by-side table and its reading
back, and then the pages with real widgets: Start here combining a series and keeping your own choice, the Workbook's
DTG column, side-by-side entry, merge without a project, column choices for all files, the Peaks sheet, its labels on
the graph and off again.

On two real thermal files of the owner (private, not in the repository): mass against temperature, a DTG column, the
side-by-side table (9800 rows, 10 columns), three steps named, labels drawn and removed again without a difference.

The app's own update check still gives the same Origin commands for 10 of 10 example files: nothing that is drawn by
default changed. **The names of peaks are possibilities by position; no assignment was checked against a reference
measurement.**

## 5.58.1: editing, selection, the look of thermal and infrared graphs

New checks: Workbook editing and the Start here selection rule (38), removal of several graphs (12 more in the session
tests), peak column / Peaks button / publication look (11 more in `tests/test_related.py`). Looked at on two real
thermal files and one real infrared file of the owner (private): the thermal graph runs from 0 to 1000 °C without the
label at 21 °C, the two-sample figure has its DTG in % per minute, the infrared graph labels 3524, 1409, 957, 872 and
668 cm-1 and no longer 2360 / 2342 (air) or 418 / 406 (end of range).

The app's own update check (5.58.1 against 5.58.0) gives the same Origin commands for 6 of 10 example files and reports
the four thermal examples as different: the temperature axis from 0 instead of 30, and the places of labels that
follow from it - the intended changes above. The update window therefore asks before installing. **Whether a figure meets a journal's standard is the author's judgement; nothing here was compared
with a published figure.**

## 5.58.2: spreadsheet tools, direct PowerPoint / Word, one graph at a time

The spreadsheet tools were checked on the table model and on the page (paste of a block copied in Excel's form, rows
and columns added as needed, insert, rename, sort, fill down, calculated columns, each undone again). The direct way
into PowerPoint and Word was checked against stand-ins for the two programs that write down what they are asked: a new
slide at the end of the open presentation with the picture fitted and centred; a picture at the cursor of the open
document no wider than its text; and the file route when the program cannot be reached. **It was not run against
PowerPoint or Word.** Selecting and resetting one graph of a two-graph figure was checked on the app's own thermal
examples.

## Not verified

* **Windows with native PySide6**: start-up, display scaling, drag and drop from Explorer.
* **A live Origin / COM session.** Only the dry run.

Both need one try on the target computer. The code paths for them are those of 5.56.0.

No user settings, credentials, private projects, temporary extraction folders or test-only adapters are in the commit;
`tools/check_banned.py --all` is clean.

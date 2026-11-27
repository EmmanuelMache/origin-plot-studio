# Implementation and validation — 5.57 (5.57.0 the merge, 5.57.1 the fixes after it)

## Scope

The project-workbench update (written against 5.55.7, labelled 5.56.0) merged into the app as it stood at its own
5.56.0. The result is 5.57.0. The existing Qt application, its scientific engines, the 122 templates, the 26 workbook
graph types, the 44 analysis tools, the Assistant, the exports and the Origin driver are kept. The rule followed in the
merge: **the look and the new project features come from the update; how the app behaves stays as it was** — where the
update had changed or lost an existing behaviour, the existing behaviour was restored.

The table below maps the 118 requirements to code. It is a traceability map. What was actually checked, and how, is in
"Audit of the map" under it; what is not done is in "Incomplete".

## Architecture

- `workspace_projects.py`: project records, folders, file order, working state and portable archives (backward compatible with the projects of 5.55.5).
- `workspace_workbench.py`: project context shared by the pages, source ownership, per-sheet working data, graph creation and restoring, the hooks into the existing pages and sessions.
- `workspace_starthere.py`: Projects / Inspect data / Choose a graph.
- `workspace_design.py`: styling, the adaptive header (View / Tools / Help as buttons on a wide window, in ••• on a narrow one), command search, the Assistant toggle, the tooltips of the two new pages.
- `workspace_workbook.py` and `workbook_data.py`: working-copy editing, column choice and order, export, validated merges. The dialog "Arrange this workbook's figures…" of 5.55.7 is still in `workspace_workbook.py`.
- `opstudio/detection.py`: identification with its evidence, the form of an XRD table (scan / fit / peak list), the fit columns by name, and the input checks of the templates.
- `workspace_graph_editor.py` and `opstudio/graph_components.py`: per-graph and per-panel components of a template graph.
- `smart_plots.py`, `workspace_ribbon.py`, `paper_figures.py`: the same controls for native and composed figures, Sample pages included.

All paths are relative to `origin_plot_app/`, except those starting with `tests/`, `tools/` or `docs/`.

## Requirement map

| Item | Requirement | Main implementation |
|---:|---|---|
| 1 | Correct XRD recognition | `opstudio/detection.py; opstudio/api.py; opstudio/data.py; smart_plots.py` |
| 2 | Match graph types to scientific data | `opstudio/detection.py; opstudio/api.py; opstudio/data.py; smart_plots.py` |
| 3 | Correct the classification cause | `opstudio/detection.py; opstudio/api.py; opstudio/data.py; smart_plots.py` |
| 4 | Check other scientific types | `opstudio/detection.py; opstudio/api.py; opstudio/data.py; smart_plots.py` |
| 5 | Upload multiple files | `opstudio/detection.py; opstudio/api.py; opstudio/data.py; smart_plots.py` |
| 6 | Support mixed supported formats | `opstudio/detection.py; opstudio/api.py; opstudio/data.py; smart_plots.py` |
| 7 | Classify individual inputs | `opstudio/detection.py; opstudio/api.py; opstudio/data.py; smart_plots.py` |
| 8 | Use Start Here as the project entry point | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 9 | Create projects | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 10 | Name projects | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 11 | Provide project setup | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 12 | Keep project contents together | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 13 | Save project working state | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 14 | Restore saved projects | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 15 | Open projects from Start Here | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 16 | Close projects | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 17 | Import saved projects | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 18 | Select projects | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 19 | Refresh projects and file availability | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 20 | Remove projects, folders and files safely | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 21 | Create project folders | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 22 | Add files to folders | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 23 | Arrange folders | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 24 | Arrange files | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 25 | Display selectable project contents | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 26 | Open the chosen work | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 27 | Select individual files | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 28 | Select folders | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 29 | Allow multiple selections | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 30 | Carry selection between pages | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 31 | Show the current project and file | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 32 | Keep selected datasets separate | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 33 | Keep graph/source associations | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 34 | Preserve selection order | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 35 | Switch datasets without losing work | `workspace_projects.py; workspace_starthere.py; workspace_workbench.py` |
| 36 | Merge compatible files | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 37 | Edit working data | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 38 | Arrange Workbook datasets | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 39 | Control plot/export order | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 40 | Choose plotting behaviour | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 41 | Edit recommended graphs | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 42 | Arrange graphs | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 43 | Customise graph appearance | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 44 | Prepare Origin output | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 45 | Transfer supported settings to Origin | `workspace_workbook.py; workbook_data.py; workspace_workbench.py; opstudio/origin.py` |
| 46 | Per-graph zoom | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 47 | Enable one graph's zoom | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 48 | Disable one graph's zoom | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 49 | Independent zoom in shared previews | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 50 | Independent zoom ranges | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 51 | Show which graph is targeted | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 52 | Line-only curve display | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 53 | Measured-data markers | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 54 | Fitted-curve markers | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 55 | Preserve data when changing markers | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 56 | Independent graph marker settings | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 57 | Control residual plots | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 58 | Control supported lower plot components | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 59 | Add available graph components | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 60 | Remove graph components | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 61 | Distinguish hidden and removed state | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 62 | Edit components from the graph workspace | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 63 | Independent component settings | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 64 | Explicit apply-to-all action | `workspace_graph_editor.py; opstudio/graph_components.py; smart_plots.py; workspace_ribbon.py; paper_figures.py` |
| 65 | Find project-management actions easily | `workspace_starthere.py; workspace_design.py; workspace_workbench.py; tests/test_workbench_ui.py` |
| 66 | Preserve navigation context | `workspace_starthere.py; workspace_design.py; workspace_workbench.py; tests/test_workbench_ui.py` |
| 67 | Show selection/action feedback | `workspace_starthere.py; workspace_design.py; workspace_workbench.py; tests/test_workbench_ui.py` |
| 68 | Connect operational controls | `workspace_starthere.py; workspace_design.py; workspace_workbench.py; tests/test_workbench_ui.py` |
| 69 | Use consistent controls | `workspace_starthere.py; workspace_design.py; workspace_workbench.py; tests/test_workbench_ui.py` |
| 70 | Verify an end-to-end workflow | `workspace_starthere.py; workspace_design.py; workspace_workbench.py; tests/test_workbench_ui.py` |
| 71 | Three-stage opening screen | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 72 | Simplify the toolbar | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 73 | Distinct navigation tabs | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 74 | Workbook navigation | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 75 | Assistant panel toggle | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 76 | Adaptive toolbar | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 77 | Separate command and graph searches | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 78 | Short opening instructions | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 79 | Visual hierarchy | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 80 | Readable controls and spacing | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 81 | Consistent colour system | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 82 | Useful project browser metadata | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 83 | Expandable project contents | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 84 | Show file/project relationships | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 85 | Distinguish focus and selection | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 86 | Selection summary | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 87 | Discoverable project actions | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 88 | Explain disabled actions | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 89 | Use Open selected wording | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 90 | Clear file-import area | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 91 | Shared import workflow | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 92 | Informative file details | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 93 | Import progress and results | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 94 | Inspect tables, sheets, units and plots | `workspace_starthere.py; workspace_design.py; workspace_qt.py; workspace_workbench.py` |
| 95 | Detected data type presentation | `opstudio/detection.py; opstudio/api.py; workspace_starthere.py` |
| 96 | Detection evidence | `opstudio/detection.py; opstudio/api.py; workspace_starthere.py` |
| 97 | Avoid conclusive angle-only inference | `opstudio/detection.py; opstudio/api.py; workspace_starthere.py` |
| 98 | Manual measurement-type correction | `opstudio/detection.py; opstudio/api.py; workspace_starthere.py` |
| 99 | Visible X/Y mapping | `opstudio/detection.py; opstudio/api.py; workspace_starthere.py` |
| 100 | Usable graph-template chooser | `opstudio/detection.py; opstudio/api.py; workspace_starthere.py` |
| 101 | Explain recommendations | `opstudio/detection.py; opstudio/api.py; workspace_starthere.py` |
| 102 | Check scientific template inputs | `opstudio/detection.py; opstudio/api.py; workspace_starthere.py` |
| 103 | Selectable graph choices and previews | `opstudio/detection.py; opstudio/api.py; workspace_starthere.py` |
| 104 | Clear action labels | `workspace_starthere.py; workspace_design.py; workspace_workbench.py` |
| 105 | Separate graph creation and Origin transfer | `workspace_starthere.py; workspace_design.py; workspace_workbench.py` |
| 106 | One primary next action | `workspace_starthere.py; workspace_design.py; workspace_workbench.py` |
| 107 | Resizable usable panels | `workspace_starthere.py; workspace_design.py; workspace_workbench.py` |
| 108 | Useful empty/error states | `workspace_starthere.py; workspace_design.py; workspace_workbench.py` |
| 109 | Context-sensitive status | `workspace_starthere.py; workspace_design.py; workspace_workbench.py` |
| 110 | Consistent downstream design | `workspace_starthere.py; workspace_design.py; workspace_workbench.py` |
| 111 | Detection drives graph recommendations | `workspace_workbench.py; workspace_templates.py; opstudio/detection.py; opstudio/api.py` |
| 112 | Analysis owns the template catalogue | `workspace_workbench.py; workspace_templates.py; opstudio/detection.py; opstudio/api.py` |
| 113 | Dynamic compatible recommendations | `workspace_workbench.py; workspace_templates.py; opstudio/detection.py; opstudio/api.py` |
| 114 | Validate required inputs | `workspace_workbench.py; workspace_templates.py; opstudio/detection.py; opstudio/api.py` |
| 115 | Refresh recommendations with selection/mapping | `workspace_workbench.py; workspace_templates.py; opstudio/detection.py; opstudio/api.py` |
| 116 | Synchronise installed template availability | `workspace_workbench.py; workspace_templates.py; opstudio/detection.py; opstudio/api.py` |
| 117 | Browse Analysis with selection context | `workspace_workbench.py; workspace_templates.py; opstudio/detection.py; opstudio/api.py` |
| 118 | Confirm uncertain identification | `workspace_workbench.py; workspace_templates.py; opstudio/detection.py; opstudio/api.py` |

## Audit of the map

Checked on the merged code. "Test" names the automated check; where there is none, it says so.

| Items | What | How it was checked | Result |
|---|---|---|---|
| 1–7 | Identification from the contents; mixed formats; each input on its own | `tests/test_workbench_core.py` (DetectionTests, FitMappingTests: 2θ / 2Theta / 2-theta / Two theta / 2ϑ, headerless, decimal comma, metadata lines, fit and peak-list forms, other kinds). **Also run on the owner's own instrument files** (diffraction scans, a fit export, a peak list, thermal runs, an infrared spectrum, a 50-sheet workbook; kept outside the repository): each is identified as what it is | pass |
| 8–35 | Projects, folders, selection, opening, saving, closing, import / export, missing files, order, source identity | `tests/test_workbench_core.py` (ProjectTests), `tests/test_workbench_ui.py` (tests 01, 04–10), `tests/test_starthere_parity.py` (54 checks: everything Start here did at 5.56.0, on the new page) | pass |
| 36–45 | Workbook: working copies, columns, order, merges, export; Origin output | `tests/test_workbench_core.py` (MergeTests), `tests/test_workbench_ui.py` (04, 14), `tests/test_opstudio.py` (Origin dry run of all 122 templates) | pass; Origin only as dry run |
| 46–64 | Per-graph and per-panel controls | `tests/test_workbench_ui.py` (03, 09), `tests/test_highscore.py` and `tests/test_edit_graph.py` (composed figures, Sample pages), `tools/audit_graph_operations.py` → `docs/GRAPH_OPERATIONS_AUDIT.md` (every control tried on every one of the 148 graph types) | pass; see the audit for what applies where |
| 65–94, 104–110 | Header, navigation, feedback, empty states, tooltips, layout at 1366×768 … 1920×1080 | `tests/test_session_basics.py` (order of the header, nothing clipped at two sizes, a tooltip on every visible button of every section), `tests/test_shell_layout.py`, `tests/test_workbench_ui.py` (12), screenshots at 1366×768, 1500×900, 1600×960 and 1920×1080 looked at by eye | pass. Items 78–81 (short instructions, hierarchy, spacing, colours) are judgements: by eye only |
| 95–103, 111–118 | Evidence, confirmation, mapping, the chooser on the live Analysis catalogue, private templates, input checks | `tests/test_workbench_core.py` (private template in the recommendations, multiple raw scans are not a fit, peak list is not a scan, every catalogue class can be chosen), `tests/test_workbench_ui.py` (02) | pass |

Everything the app did before, on the merged code:

* All 49 test files: 2 465 checks pass, 0 fails. See `VALIDATION_RESULTS.md`.
* **Commands, menus, shortcuts:** an inventory of the merged window against the window of 5.56.0 — no entry of the File, View, Tools or Help menu is missing (30 / 45 / 27 / 9 entries), none of the 33 keyboard shortcuts, and no command of the command search except the five that were buttons of the old Start here page and have a renamed equivalent.
* **The app's own update check** (`self_update.check`, merged against 5.56.0): the same Origin commands for 10 of 10 example files; no program file of 5.56.0 is missing.

### Faults found in the delivered update and fixed in the merge

Found by running it with real PySide6 and the whole existing test suite (the update had been run on a Qt 5 stand-in, with seven of the suites):

1. "Add files…" and "Update available" were taken out of the header's layout; shown again later they covered the top-left corner of the window.
2. The Start here plot was drawn at the print resolution (200 dpi) on screen, twice its size; the Workspace canvas got the same resolution after a template graph had been shown.
3. The Projects column overlapped its own text on a 768-pixel-high window.
4. View / Tools / Help were only in the ••• menu; 18 buttons of the two new pages had no tooltip; the quick buttons had lost their "name (shortcut) – what – Disabled: …" form (`tests/test_session_basics.py`, 4 checks).
5. A file added while another was being read was not listed until later, and was ticked a second time when its turn came (`tests/test_templates_page.py`, 3 checks).
6. A column choice was no longer remembered for files with the same headers; the sheet that fits the ticked template was no longer picked (`tests/test_templates_page.py`, 3 checks).
7. A file with no table gave "cannot unpack non-iterable NoneType object" instead of words.
8. Adding a file on Start here, or with File ▸ Add data files, required creating a project.
9. With files of several kinds ticked, Choose a graph offered only the plain Line plot (it wanted one template for all of them).
10. Beside the highlighted row of the project tree the style drew the indent as a separate little box with corner marks; ticking needed a click on the small box. The tree now paints the row as one bar, and a click on the row ticks it.

### Faults that were in the app before and are fixed here

1. A pattern-and-fit table was read by column position: with a leading `No.` column the row number was drawn as 2θ, the position as "observed" and the observed curve as "calculated"; a background column after the calculated one was drawn as the difference. The columns are now taken by their names; unnamed columns keep their order (`FitMappingTests`). This was found with the owner's own fit export.
2. The window stopped while files were added: every file ticked re-ranked all 122 templates, each ranking rebuilt every template's example data and read every ticked file. Now one ranking, from the first ticked file, with the examples made once in the background; files are read on the reader's thread. Ten files: 3.6 s of stopped window before, 0.5 s now. The owner's thirteen files with the 50-sheet workbook: longest stop 0.8 s (12–20 s before these changes).

### Found after 5.57.0 was installed, fixed in 5.57.1

1. **Figures of a workbook, and "Draw in Origin like this", were empty in Origin.** `opstudio.origin.send` imported the data of each curve and plotted it at once; the import leaves the workbook as Origin's active window, so the plot and every later layer command were refused. It now writes the commands down and sends them in `Driver.draw_spec`'s order (workbooks, graph, layers, the rest) and calls `Driver.check`. Not verified in Origin itself.
2. **The window stopped for 5-10 s at every click on, or change of, a figure of a workbook**: each drawing re-read the whole workbook. `workbook_cache.sheets` parses it once per version of the file; a changed figure is drawn once and its picture kept (`smart_plots._composed_slot`).
3. A large file clicked in the project list was read on the window's thread (`Workbench.ready` reads it in the background); closing the app while files were being read waited up to 30 s and could abort ("QThread: Destroyed while thread is still running").
4. A file added without a project was shown only in a two-row list in the middle column; it is now a row of the project tree ("Files not in a project").
5. By request: every graph of a fit draws the observed curve as a solid line and the calculated one dashed over it (dots on request); "Add folder…" brings in a folder of the disk with its sub-folders.

### Found after 5.57.1 was installed, fixed in 5.57.2

1. **A workbook figure in Origin did not look like the figure in the app.** With 5.57.1 the curves were there, but: texts were missing and one lay as a jumble at the top of the page, axis titles were missing on every panel after the first, letters and lines were a half to a third of their size, there was no legend and a sixth, empty panel, grouped columns covered each other. Causes and fixes are listed in `CHANGELOG.md` (5.57.2) and, for whoever changes the code next, in `CLAUDE_CODE_HANDOFF.md`. Tested through the driver's dry run on a figure built for the purpose (`tests/test_opstudio.py`, 12 new checks) and on the owner's two figures (privately). **Not run in Origin.** Two things could not be settled without Origin: whether it accepts the hatch command, and the frame of panels after the first.
2. **Delete on a ★ figure of the app only showed a message** (the behaviour chosen in 5.55.3). It removes the figure now (`tests/test_session_basics.py`, 6 new checks).
3. By request: "Phase tick rows" on the Panel bar (`tests/test_edit_graph.py`, 5 new checks); Export ▸ Send to PowerPoint / Word (`tests/test_workspace_actions.py`, 8 new checks; the written files are also read back with python-pptx / python-docx and were opened with LibreOffice).

### By request, 5.58.0

Tested in `tests/test_related.py` (61 checks: the functions on their own, then the pages with real widgets).

1. Files of one series are combined by the app on Start here and the graphs of several samples come first; the choice of *Separate graph for each file* is kept. (Found while testing: the box switched back to *Combine* the moment it was changed - the page was drawn again before the change counted as the user's. Fixed.)
2. X and Y by what the columns are (`detection.preferred_xy`), only where nothing was chosen or remembered.
3. Workbook: DTG column, side-by-side table of a series, a third way to merge, merging without a project (it had refused after asking for a name), column choices for all files.
4. Peaks of thermal runs and bands of infrared spectra with what they may be; labels drawn on request.

What "may be" means: the reference events of `opstudio/tga_core.py` and the reference bands of `opstudio/ftir_core.py` whose range holds the position, the one it lies most centrally in first - for thermal events the four that nearly every cement paste and raw meal shows (water, C-S-H / ettringite, portlandite, calcite) before the others, so a step at 770 °C is offered as calcite before dolomite. Ranges overlap; a name is a possibility. Labels start with a question mark for that reason and are drawn only when switched on.

Not done: a side-by-side dataset is drawn sample by sample in Workspace, but on Start here it is offered the graphs of its first sheet only (one table per file is a deep assumption of the template engine). The peak table is made for the selected sheet of a file.

### By request, 5.58.1

Tested in `tests/test_workbook_editing.py` (49 checks), `tests/test_related.py` (78), `tests/test_session_basics.py` (66). Also: X / Y and moving columns from the header menu, the suggested graph under the table, merging into one Excel workbook, the Workbook filled from the ticks of Start here.

1. Workbook: delete / empty / hide for cells, rows, columns and files, each undoable; before, the table could only be typed in.
2. The ticks of Start here are the selection of the whole app (Workbook, Analysis, Workspace).
3. Your graphs: several graphs removed at once. Found while doing it: a right click collapsed a multi-row highlight to one row, and the list opened two context menus in a row.
4. A peak-name column in the data and a Peaks button.
5. Thermal and infrared graphs: round temperature axis, no event for the start-up dip, one DTG unit, no labels on air CO₂ or range ends. These change default drawings; the app's update check reports its thermal examples as different, as intended.

Not done: the right axis of a TG + DTG graph still carries tick numbers above zero where no curve is (the two curves share the height by design); restricting them would make the preview differ from Origin, where the tick range cannot be limited by the commands known to work.

### By request, 5.58.2

Tested in `tests/test_workbook_editing.py` (76 checks), `tests/test_workspace_actions.py` (50), `tests/test_templates_page.py` (70).

1. Spreadsheet tools on the Workbook table. "All the options Excel has" was read as: the operations needed to prepare a table for a graph. Left out and said so in the notes: recalculating cell formulas, formats, charts.
2. XRD peak table in the Workbook (read-only there; it belongs to the graph).
3. Send to PowerPoint / Word through Windows automation into the open presentation or document, with the file route as fall-back. **Not run against PowerPoint or Word** - there is neither here; the calls are checked against stand-ins that record them.
4. Each graph of a multi-graph figure for itself: Select range, the calculation on a selection, Reset axes. Zoom and Pan already acted on the graph under the mouse; graphs that share an x axis by design (stacked panels) still move together in x.
5. Analysis: Delete on the file list; Remove carries through the app.

### Learning, updates and security, 5.59.0

Requirements and evidence: `docs/LEARNING_SECURITY_TRACKER.md`; what works, what is a mock and what needs the owner:
`docs/LEARNING_SECURITY_COMPLETION_REPORT.md`.

1. Security foundations (`outbound_policy.py`, `secure_store.py`) and the fixes of SEC-01 to SEC-08, tested in `tests/test_outbound_policy.py`, `test_security_net.py`, `test_security_update.py`, `test_security_ai_disclosure.py`, `test_local_only.py`, `test_security_imports.py`, `test_packaging.py`.
2. Personal learning (`opstudio/learning/`, `workspace_learning.py`) with the XRD correct → remember → restart → reuse demonstration, tested in `tests/test_learning_core.py` and `tests/test_learning_ui.py`.
3. Sharing adapter, backend SQL, the 14-day gate and the workflows: written and tested locally (`tests/test_learning_sync.py`, `test_cycle_due.py`, `test_workflows_static.py`); none of it has run against a live service or on GitHub.
4. The CI workflow has run on GitHub (green). Not run: Windows, live Origin, real AI services, the fortnightly cycle and release workflows, a production signing key.
5. The old 'known failure' of `tests/test_xrd_generator.py` is gone: its assertion contradicted the name of the bundled fixture (the template itself is called SAMPLE); it now applies only to templates with another name, and the test runs without arguments.

### XRD stacked in every case, 5.58.6

Tested in `tests/test_highscore.py` (50 checks, 7 of them new).

1. Peak lists that no pattern of the list uses are stacked by `make_groups` like patterns; the figure is built from their stick graphs.
2. Names on stacked patterns are placed upright when they are whole names.
3. The stacked peak-list figure passes a dry run of the Origin driver (texts rotated, names sent); not checked in a running Origin.

### Peak lists with PDF numbers, 5.58.5

Tested in `tests/test_highscore.py` (43 checks, 17 of them new).

1. `pdf_names.py` reads a pattern list (reference code and compound / mineral name) and translates the codes in the *Matched by* column of a peak list; the names become the labels of the peak-list graph and of the measured pattern linked to it.
2. One file or two, either order, pattern list added later, names remembered between sessions; a code without a name stays a code and is reported.
3. Built on synthetic files in the usual export layout; not yet checked against a file of the owner.

### Drawn after the owner's two reference pictures, 5.58.4

Tested in `tests/test_opstudio.py` (93 checks) and `tests/test_related.py` (86).

1. The infrared template draws offset spectra in one colour per sample with every band marked and labelled on its own spectrum, legend at the lower left; the DTG template draws all runs in one graph over zones named inside it.
2. The DTG template was wrong for instrument files (time and DSC drawn as samples, no zones); a file with one mass column is one sample now, with its own heating rate.
3. After a merge the Workbook showed the first file again; it opens the merged workbook on its side-by-side sheet, as a read-only view. The sheets of a merged workbook no longer double the automatic combined figures.
4. Not checked here: a running Origin, and the look on Windows fonts.

### Found on the owner's screen with 5.58.2, fixed in 5.58.3

Tested in `tests/test_related.py` (82 checks) and `tests/test_workbook_editing.py` (85).

1. The peak columns were unusable as designed in 5.58.1: a name in the row of its peak cannot be found in a table of thousands of rows. They are a list from the first row now.
2. A merged workbook carried those columns as data; one infrared spectrum got no infrared graph; a repeat measurement fell out of its series; a header was cut off.
3. By request: sheets can be added, duplicated and removed in the working copy.

## Interpretation details

- Project folders are the app's own. Removing or arranging them does not move or delete files on the disk.
- A saved project keeps references to its source files; a portable `.opsproject` contains copies, the data edits and the graph settings, and is imported as a project of its own.
- A component is not made up by ticking a box: Bragg rows need a reflection list ticked with the fit, a background needs a background column in the file, d-spacing needs a confirmed wavelength, time / temperature layouts need that information. Where it is missing the control is greyed out and says so.
- The plain **Line plot** (`scientific_line`) is the one template added; it is the option when the kind of data is not established. 122 templates and 26 workbook graph types are installed. The 213 catalogue rows marked "Coming" are not implemented and are not counted anywhere as features.
- "Painting plot" in the request did not name a component. The difference row, Bragg rows, peak / stick rows and background keep their scientific names.
- With several files of different kinds ticked, the chooser follows the file you are looking at and a graph is made for each ticked file the template fits. This differs from the delivered update (one template for the whole selection) and is closer to 5.56.0 (the graph of the file on show).

## Incomplete

| What | Practical effect |
|---|---|
| **Windows and a live Origin were not available.** All checks ran with PySide6 6 on Linux without a screen (`QT_QPA_PLATFORM=offscreen`); Origin was the driver's dry run | Start-up on Windows, display scaling at 125 % / 150 %, drag and drop from Explorer and the COM session with Origin must be tried once on the target computer. The app's code paths for them are unchanged from 5.56.0 |
| A workbook with dozens of sheets is read several times by the different readers (about a minute for 3 MB / 50 sheets) | The window stays usable and says "Reading this file…", but the graphs of that workbook arrive late. Reading it once and sharing the result was left alone: it is in the reading code the figures depend on |
| Background curve: drawn only for a pattern-and-fit file that names its background column; no template example has one | The control is greyed out for every other graph (`docs/GRAPH_OPERATIONS_AUDIT.md`: 148 × n/a for the examples) |
| Identification of NMR, porosity and thermodynamic tables is by column names only; proprietary formats not listed in the reader are reported as unreadable | Such a file may come up as "General XY": choose its kind under Data type |
| Items 78–81 and 110 (wording, hierarchy, spacing, colours, consistency of the other sections) are not measurable | Looked at in screenshots only |
| The 118 requirements were not each given a test of their own | Grouped evidence as in the table above; an item without a named test was read in the code and tried by hand |

## Reproduce

From the repository root, with `origin_plot_app/requirements.txt` installed (set `QT_QPA_PLATFORM=offscreen` where there is no screen):

```text
python -m compileall -q origin_plot_app tests
python tests/test_workbench_core.py
python tests/test_workbench_ui.py
python tests/test_starthere_parity.py
python tests/test_opstudio.py
python tests/test_figures_general.py
python tests/test_analysis_tools.py
python tests/test_highscore.py
python tests/test_gallery_graphs.py
python tools/audit_graph_operations.py
```

and every other `tests/test_*.py` (see `VALIDATION_RESULTS.md`). `tests/test_starthere.py` runs the desktop-workflow suite; what Start here did before the redesign is checked by `tests/test_starthere_parity.py`.

# Implementation and validation — 5.56.0

## Scope

This package implements the project-workbench redesign in the existing Qt desktop application. The table below maps the 118 requirements to delivered code; it is a traceability map, not a claim that every Windows interaction has been separately acceptance-tested.

The source data that originally failed classification was not included with this request. Detection was exercised against constructed regression cases and shipped example files. The user's actual troublesome instrument exports still need an acceptance check.

## Architecture

- `workspace_projects.py`: backward-compatible project records, virtual folders, file order, working state, input settings and portable archives.
- `workspace_workbench.py`: shared project context, source ownership, per-sheet working data, graph creation/restoration, and integration with existing pages and sessions.
- `workspace_starthere.py`: Projects / Inspect data / Choose a graph.
- `workspace_design.py`: common styling, adaptive navigation, command search and Assistant toggle.
- `workspace_workbook.py` and `workbook_data.py`: working-copy data editing, column inclusion/order, export and validated merges.
- `opstudio/detection.py`: scientific identification, evidence and compatibility rules. A numeric fit in an adapter is insufficient by itself to recommend a scientific analysis.
- `workspace_graph_editor.py` and `opstudio/graph_components.py`: independent template-graph/panel components, measured/fitted markers and residual layout.
- `smart_plots.py`, `workspace_ribbon.py` and `paper_figures.py`: equivalent controls for existing native and composed figures, including Sample pages and working-copy data.

All paths below are relative to `origin_plot_app/`, except paths starting with `tests/`.

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

## Interpretation details

- Project folders are application-managed logical folders. Removing or arranging them does not move or delete the original files on disk.
- Local project records retain source-file references. Portable `.opsproject` exports contain source copies, saved data edits and graph settings; importing restores them into a separate project.
- The compact project tree and Inspect data view provide the opening-screen layout. **Project menu → File details** provides the tabular filename/format/type/rows/sheets/status view requested in item 92.
- A component cannot be fabricated by enabling a checkbox. Missing Bragg data, missing calculated intensities, absent time/temperature metadata and unconfirmed wavelengths have explicit compatibility limits.
- A plain Line plot was added to provide a safe display option without guessing a scientific analysis. The original 121 templates and 26 workbook types remain installed.
- The phrase “painting plot” did not name a recognisable component. Difference, Bragg rows, peak/stick panels and background/baseline controls cover the identifiable components; their scientific names are preserved.
- Graph transfer preserves what the existing Origin driver supports. Its difference reporting remains in place; a successful command-generation check is not a live Origin COM test.

## Validation environment and practical limits

Core tests ran under Python 3.12 with NumPy, pandas, SciPy, matplotlib and openpyxl.

PySide6 was unavailable in the execution environment and its package could not be downloaded through the network policy. Real-widget integration and screenshots were therefore exercised using a local Qt 5.15/PyQt compatibility test adapter. The delivered application continues to target PySide6. That adapter and its compiled compatibility helper are **not shipped** in this package.

Native Windows/PySide6 installation, display scaling and an actual installed Origin/OriginPro COM session were not available here. Those are the remaining platform acceptance checks. No claim is made that every proprietary instrument format or every possible Excel layout is supported; unreadable inputs are reported rather than being labelled with a guessed type.

## Reproduce checks on the supported desktop runtime

From the repository root, with the application's dependencies installed:

```text
python -m compileall -q origin_plot_app tests
python tests/test_workbench_core.py
python tests/test_workbench_ui.py
python tests/test_opstudio.py
python tests/test_figures_general.py
python tests/test_analysis_tools.py
python tests/test_highscore.py
```

`QT_QPA_PLATFORM=offscreen` can be used for automated widget checks. `test_starthere.py` remains a compatible entry point to the current Start Here integration suite; assertions tied to the replaced list-widget layout have been superseded.

See `VALIDATION_RESULTS.md` for the results captured for this package. Example screenshots are in `docs/` and show demonstration data.

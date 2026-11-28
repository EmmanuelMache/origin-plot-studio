# TEST_REPORT – upgrade v2, app version 5.58.3

Where it was run: a Linux container, Python 3.12, PySide6 with `QT_QPA_PLATFORM=offscreen`. **No Windows and no Origin were
available.** Everything that needs Origin was run through the app's own Origin driver in dry-run mode (it records the
LabTalk commands and writes the worksheets). What could only be checked in real Origin or on Windows is marked
**not verified**. Nothing below is reported as passed unless it was run.

## 1. Acceptance checks of the brief (section 13)

| # | Check | Performed | Result | Evidence |
|---|---|---|---|---|
| 1 | File left-most; Quick Access beside it; groups tidy at 1366×768 and 1920×1080 | yes, at 100 % scaling | **pass** for the order and "nothing clipped" at both sizes. 125 % and 150 % scaling: **not verified** (no display) | `tests/test_session_basics.py` (2 checks per size); `screenshots/after/start_screen_file_far_left.png` |
| 2 | Every icon shows name + shortcut + description (+ disabled reason); spot check ≥ 30 | yes | **pass**: every visible button in all six sections has a tooltip (163 checked, 0 missing); 118 describe the command, 29 name a shortcut, 9 say what enables them. **Partly**: not every tooltip follows the full "Name (shortcut) – description. Disabled: …" form; the older ones give description and shortcut only. Tooltip delay is the system's (not set to 400 ms) | `tests/test_session_basics.py` "check 2", "spot check" |
| 3 | New Session, Clear Graph, Clear All Graphs, Remove Selected / All Files, Start Afresh, Reset Layout, Recover Last Session; undoable | yes | **pass**: each works and Clear graph / Clear all / Remove ticked / Start afresh are undone and redone. Note: in this app a loaded file *is* its graphs, so "Remove files" and "Clear graphs" act on the same list | `tests/test_session_basics.py` (17 checks) |
| 4 | Panels in Workspace, each Analysis tool, Graph gallery / Templates, Assistant, Settings: move, resize, dock, tab, float, close, reopen; persist; reset | yes for Workspace, Analysis, Graph gallery, Templates | **pass** for those four sections (20 panels). **Fail** for Assistant and Settings: they are still fixed pages, not panels. Collapse buttons and named layouts ("Save layout as") are **missing** | `tests/test_shell_layout.py` (41), `tests/test_templates_page.py` ("six panels", "layout kept") |
| 5a | All implemented templates present, with family / domain trees and field filters | yes | **pass**: 118 templates; field list with graph families and domain packs and counts; source and status filters; search. It is a filter list, not a two-level tree widget | `tests/test_templates_page.py` |
| 5b | Every catalogue row visible, with status available or coming | yes | **pass**: 331 entries = 118 available + 213 coming | same |
| 5c | Tier 1 implemented, coverage per section | yes | **partly**: 14 of 17 Tier-1 rows built. Not built: isopleth / pseudo-binary phase diagram, element map grid, hot-stage microscopy. Coverage table: section 3 | `tests/test_opstudio.py` |
| 5d | Preview with my data: the reference sheet in ≥ 6 templates; 6 fit files × 1 template; one graph in 6 styles | yes, privately on the user's reference sheets (not in the repository) | **pass**: 8 templates, 6 of 6 fit files, 6 styles drawn. The comparison with the pack's `MULTI_SELECT_*.png` was done by eye on three pictures only | private run (`run_private_checks.py`, kept outside the repository); the same path with neutral files: `tests/test_templates_page.py` |
| 6 | Save as my template → reopen app → template with preview; export / import `.opst` | yes | **pass** | `tests/test_templates_page.py`, `tests/test_opstudio.py` |
| 7 | Right-click menus for canvas, curve, axis, legend, text, zone, file, thumbnail, table column; format painter | partly | **partly**: canvas, graph list (existing), file, template thumbnail, preview tile and TGA zone menus exist. Curve, axis, legend and table-column menus and the format painter are **missing** | menus are built in `workspace_templates.py`, `workspace_tga.py`; not all are covered by tests |
| 8 | Export PNG / TIFF / PDF / SVG / EMF, single and double column; vector stays vector; no selection handles | yes | **pass** for PNG, TIFF (LZW), PDF, SVG, EPS, JPG at exactly 89 mm and 183 mm (Nature preset); SVG holds text and paths, no picture. **EMF: missing** (matplotlib cannot write it) | `tests/test_opstudio.py`, `tests/test_templates_page.py` |
| 9 | TGA: CH within 0.5 % of 12.3, CaCO₃ within 0.5 % of 4.5 (tangent); onset / endset bracket 460 °C; names need confirmation; Excel with five sheets and chart, DTG not reversed | yes | **pass**: CH 12.28 wt.%, CaCO₃ 4.52 wt.%; onset 442 °C, endset 478 °C; nothing is calculated or exported under an unconfirmed name; five sheets, one chart, DTG at natural sign | `tests/test_tga_module.py` (37), `tests/test_tga_core.py` |
| 10 | Label policy: FTIR and TGA from files without labels → Confirm labels appears; "?" never exported; XRD unlabelled without a peak list | partly | **pass** for TGA (the Confirm labels table is there when the graph is drawn; unconfirmed names are left out of graph and Excel exports) and for XRD (existing behaviour; templates write only texts from the file). **Missing** for FTIR bands: no Confirm labels panel there | `tests/test_tga_module.py`, `tests/test_opstudio.py` ("texts … from the file only", "reference stick rows come only from the user's peak list") |
| 11 | Existing features unchanged: HighScore, Assistant providers, key reuse, history, Origin send, old projects | yes | **pass**: all earlier test files pass; the updater's own regression gives the same Origin commands as 5.50.0 for 10 of 10 example files; sessions saved with the old section name open | section 2; `self_update.check` |
| 12 | Long file names, unsupported file, invalid mapping, no search results, long operation with cancel | yes | **pass** on the Templates page | `tests/test_templates_page.py` (5 checks) |
| 13 | Template graph → Origin for the five named cases: preview and Origin graph look the same | scripts and worksheets: yes. Visual comparison: **no** | **Scripts built and tested: pass. Visual check: not verified (Origin not available).** For the four reference sheets and a TGA run the app drew the template and wrote the Origin commands: 2 / 3 / 1 / 3 / 2 layers, 12 / 3 / 3 / 7 / 2 curves, no listed difference. Side-by-side screenshots could not be made | private run; `tests/test_opstudio.py` (17 Origin checks: page size, layer places, ranges, reversed / log axes, curves, zones, texts, legend, export size, `.opju` name) |
| 14 | 3 files + 4 templates + 2 styles → 24 previews; keep 6 → 6 Origin graphs; Combine 2×3; Export all → 6 files | yes (Origin through the dry run) | **pass**: 24 previews; 6 projects named `{sample}_{template}_{style}.opju`; one landscape figure with (a)…(f); 6 files written. In real Origin: **not verified** | `tests/test_templates_page.py` "check 14a–14d"; `screenshots/after/templates_multi_select_24_previews.png`, `combined_2x3.png` |

## 2. Test files (all run on the final code)

| Test file | Passed | Failed | Note |
|---|---|---|---|
| `tests/test_analysis_tools.py` | 17 | 0 |  |
| `tests/test_assistant.py` | 35 | 0 |  |
| `tests/test_calorimetry.py` | 26 | 0 |  |
| `tests/test_cycle_due.py` | 106 | 0 |  |
| `tests/test_drag_labels.py` | 8 | 0 |  |
| `tests/test_edit_dialog.py` | 10 | 0 |  |
| `tests/test_edit_graph.py` | 45 | 0 |  |
| `tests/test_figures_general.py` | 40 | 0 |  |
| `tests/test_gallery_graphs.py` | 34 | 0 |  |
| `tests/test_highscore.py` | 50 | 0 |  |
| `tests/test_learning_core.py` | 181 | 0 |  |
| `tests/test_learning_sync.py` | 96 | 0 |  |
| `tests/test_learning_ui.py` | 63 | 0 |  |
| `tests/test_local_only.py` | 48 | 0 |  |
| `tests/test_look_progress.py` | 14 | 0 |  |
| `tests/test_opstudio.py` | 93 | 0 |  |
| `tests/test_outbound_policy.py` | 32 | 0 |  |
| `tests/test_packaging.py` | 73 | 0 |  |
| `tests/test_peak_correct_tab.py` | 18 | 0 |  |
| `tests/test_peak_labels.py` | 38 | 0 | new in 5.59.3: peak labels on or off for every graph |
| `tests/test_related.py` | 86 | 0 | new in 5.58.0: series of files, side-by-side tables, DTG column, columns for all files, peaks and what they may be |
| `tests/test_ribbon_sketch.py` | 37 | 0 |  |
| `tests/test_security_ai_disclosure.py` | 82 | 0 |  |
| `tests/test_security_imports.py` | 172 | 0 |  |
| `tests/test_security_net.py` | 93 | 0 |  |
| `tests/test_security_update.py` | 79 | 0 |  |
| `tests/test_session_basics.py` | 66 | 0 |  |
| `tests/test_shell_layout.py` | 42 | 0 |  |
| `tests/test_starthere.py` | 15 | 0 | runs the desktop-workflow suite of `test_workbench_ui.py` (kept as an entry point) |
| `tests/test_starthere_parity.py` | 54 | 0 | what Start here did at 5.56.0, checked on the new page |
| `tests/test_stop_analysis.py` | 9 | 0 |  |
| `tests/test_templates_page.py` | 70 | 0 |  |
| `tests/test_tga_core.py` | 1 | 0 | 3 known-answer functions (prints OK) |
| `tests/test_tga_module.py` | 37 | 0 |  |
| `tests/test_thermal_photo.py` | 18 | 0 |  |
| `tests/test_workbench_core.py` | 46 | 0 | detection, fit columns, merges, project archives (no Qt) |
| `tests/test_workbench_ui.py` | 15 | 0 | real widgets: projects, graphs, Workbook, save / reopen, portable projects |
| `tests/test_workbook_editing.py` | 85 | 0 | new in 5.58.1: delete and hide in the Workbook, files off the list, the Start here selection rule |
| `tests/test_workflows_static.py` | 112 | 0 |  |
| `tests/test_workspace_actions.py` | 50 | 0 |  |
| `tests/test_workspace_main.py` | 83 | 0 |  |
| `tests/test_workspace_qt.py` | 29 | 0 |  |
| `tests/test_workspace_steps34.py` | 89 | 0 |  |
| `tests/test_xrd_background.py` | 14 | 0 |  |
| `tests/test_xrd_correction.py` | 19 | 0 |  |
| `tests/test_xrd_generator.py` | 17 | 0 | All pass since 5.59.0: the fixture check now applies only to templates whose own name is not SAMPLE (the bundled fixture is called SAMPLE) |
| `tests/test_xrd_generator_actions.py` | 19 | 0 |  |
| `tests/test_xrd_window_origin.py` | 10 | 0 |  |
| `tests/test_zoom_pen.py` | 24 | 0 |  |
| `xrd_scan_generator/tests/test_engine.py` | 26 | 0 |  |
| **Total** | **2526** | **0** | 50 files |

The updater's own regression (`self_update.check`, the new program against 5.56.0): **the same Origin commands for 10 of 10 example files.**
`tools/check_banned.py --all`: clean.

## 3. Catalogue coverage (implemented / total per section)

The pack's catalogue file held 372 rows; 24 of them were table header rows. The real graph types are **348**.
135 rows are implemented by 118 templates; 3 Tier-1, 127 Tier-2 and 83 Tier-3 rows are still to do.

| Catalogue section | Implemented | Total |
|---|---|---|
| A. Basic 2D (line, scatter, error) | 6 | 23 |
| B. Column, bar, pie, area | 11 | 23 |
| C. Multi-panel and multi-axis | 9 | 14 |
| D. Statistical | 12 | 39 |
| E. Contour, heatmap, image | 2 | 14 |
| F. Specialized: polar, ternary, vector and others | 2 | 29 |
| G. Categorical, flow and hierarchy | 0 | 14 |
| H. 3D | 1 | 12 |
| I. XRD and diffraction | 14 | 19 |
| J. Spectroscopy | 4 | 14 |
| K. Microscopy and microanalysis | 3 | 8 |
| L. Particle size, surface area and porosity | 5 | 12 |
| M. Rheology, mechanics and other physical tests | 4 | 13 |
| N. Thermal analysis and kinetics | 16 | 22 |
| O. Calorimetry and hydration | 10 | 12 |
| P. Thermodynamic modelling and phase chemistry | 9 | 14 |
| Q. Engineering, durability and pore solution | 9 | 26 |
| R. Sustainability and decision support | 7 | 9 |
| S. Electrochemistry and energy | 2 | 6 |
| T. Life science and medicine | 3 | 6 |
| U. Analytical chemistry | 2 | 5 |
| V. Physics, signal and engineering | 2 | 6 |
| W. Environment and geoscience | 2 | 4 |
| X. Chemical kinetics and general chemistry | 0 | 4 |
| **All** | **135** | **348** |

Note on section G: the flow diagram template exists (`sankey_mass_energy`) but the catalogue maps it to another row; the count follows the catalogue file.

## 4. Draw in Origin like this – what was and was not checked

* Checked (dry run): all 118 templates go through the driver without an error; 66 have no listed difference. The differences of the others are one line each in `origin_plot_app/opstudio/origin/DIFFERENCES.md` (category names sent as texts; error whiskers and tick rows not sent as objects; filled bands as areas; colour maps, images, polar and 3-D panels as a picture; stacked bars as columns).
* **Not verified**: that Origin accepts every command and that the Origin graph looks the same as the preview. The legend commands, the right-axis layer link, hatch patterns, `insertImg2g` and `template_saveas` are sent as optional commands: a refusal by Origin is written to the command log and does not stop the drawing. The first run on a computer with Origin should be checked against the preview, starting with the five cases of check 13.
* `.otpu` files are **not shipped** (they can only be made by Origin). *Templates ▸ More ▸ Build Origin templates* makes them on the user's computer.

## 5. Known gaps (see GAP_LIST.md for the full list)

Assistant and Settings as panels, collapse and named layouts; object model with stable IDs, format painter, nudge keys and the remaining right-click menus; Insert menu items; EMF; the Convert-files unit conversions and the extra importers; Confirm labels for FTIR and other band labels; the remaining general tools (LOWESS, ALS baseline, Bland–Altman as a tool, Weibull) and domain calculations (clinker moduli, amorphous content by internal standard as a tool, carbonation and chloride fits); Tier 2 and Tier 3 of the catalogue.


## 5.55.0 – composed figures for any workbook

Run in the same container (Python 3.12, PySide6 offscreen, matplotlib 3.11, pandas 3.0). Origin: dry run only.

| Check | Result | Evidence |
|---|---|---|
| Tick rows pair only with the exact code (`X` / `X'` / `Xa`); a lone row is reported; long reflection lists are read | **pass** | `tests/test_figures_general.py` (4 checks) |
| A stack label stays at its own peak under a taller trace above it; the axis grows for a high label; a cut label is reported; an edge label turns inwards | **pass** | same (4 checks) |
| Two-line titles of a 2 × 3 grid inside the page; Rwp upright | **pass** | same (2 checks) |
| Side tables (labels, ticks, Rwp) recognised and used by the templates; a plain `Label, x, y` table stays data | **pass** | same (4 checks) |
| Roles: `Model 1` ≠ `Model 2`; series of one panel never share a style; a model keeps its style where another is missing; legend lists phases of later panels; hatched bars per table with "0" | **pass** | same (5 checks) |
| Automatic recipe on a neutral workbook without plan (fit + reflection list + labels + Rwp, FTIR, two calorimetry sheets, bars with SD, models): every sheet recognised, 5 figures drawn, ticks / labels / Rwp / colours / error bars / titles right; with a plan sheet: one figure per row with its titles and range | **pass** | same (11 checks) |
| Recipe figures in Origin: one project per figure with labels and panels | **pass in dry run**; real Origin **not verified** | same (1 check); `tests/test_workspace_main.py` (2 window checks) |
| All earlier suites | **pass** (unchanged counts) | `test_xrd_generator_actions.py` stalls after its last PASS in this container, the same on the unchanged 5.54.3 copy (not caused by this change) |

## 5.55.1 – workbooks of figures in the Workspace

| Check | Result | Evidence |
|---|---|---|
| *Add data files* with a workbook of figures gives one graph per figure (5 for the neutral book) | **pass** | `tests/test_workspace_main.py` |
| The figure is shown in the window as saved; never overlaid with another figure | **pass** | same (2 checks) |
| *Draw in Origin*: one Origin graph per figure and its publication file | **pass in dry run**; real Origin **not verified** | same |
| All other suites | **pass** (unchanged counts) | full run |

## 5.55.2 – hybrid (checked against the unchanged 5.54.3)

| Check | Result |
|---|---|
| *Sheets only* gives exactly the graphs of 5.54.3 for a workbook of figures (40 of 40, same names and kinds) | **pass** |
| *Let the app decide*: figure plan → figures first, then only sheets no figure uses; no plan → sheet graphs first as before, figures after; ordinary file unchanged | **pass** |
| A saved recipe that fits the workbook is used first | **pass** |
| A 5.54.3 session of a workbook of figures restores all 40 graphs | **pass** |
| Changed templates drawn from plain files: 8 of 9 pixel-identical to 5.54.3; the 9th (stack + zoom) differs only by the aligned zoom panel (fix) | **pass** |
| A recipe of 5.54.3 drawn by both versions: 2 of 7 identical; the 5 others differ only where a fault was fixed (cut label shown, tick-row pairing, titles / legend on the page, stack labels) | **pass** (checked region by region) |
| All suites | **pass** | 

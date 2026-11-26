# CLAUDE_CODE_HANDOFF.md – Origin Plot Studio

Read this file first. It says what exists in the code now, not what is intended.

## 1. Summary

* App version: **5.58.6** (branch `upgrade-v2`; `main` is the published branch the updater reads).
* Built and run on: Linux container, Python 3.12, PySide6 (offscreen), matplotlib, pandas, numpy, scipy, openpyxl.
  **Origin not available. Windows not available.**
* This round: publishing hygiene (no user data in the repository, private folder, privacy check before every commit);
  the template × style × data engine (118 templates, 9 styles); the Templates page with multiple selection, the preview
  grid and batch actions; "Draw in Origin like this"; command area and session basics; the TGA / DTG module; Tier 1 of
  the graph catalogue (14 of 17 rows).
* The repository's history was replaced by one clean commit at 5.51.0 (the owner asked for it). Do not restore old history.
* **5.57.0: the project workbench.** A delivered update (written against 5.55.7) was merged into the app at 5.56.0 on branch
  `integrate/project-workbench`: the package is one commit on its 5.55.7 baseline, merged three ways. Rule of the merge,
  from the owner: *the look and the new project features come from the update; nothing the app did before changes or goes
  missing.* Read section 2b before touching Start here, the header, Workbook or the recommender.

## 2b. The project workbench (5.57.0) - what exists now

| File / module | What it is | Tests |
|---|---|---|
| `workspace_workbench.py` (new) | `Workbench`, installed on the window as `ws.workbench` by `install(ws)` when the template library is present. Owns the active project, the working copies of each input (`raw_sheets`, `_table(path, slug, sheet=None)`), per-sheet settings (`settings_for`: sheet, order, off, type, edited sheets), `recommendations(paths, together, focus)`, `create_graphs`, `open_inputs(pairs, then_workspace)`, saving / closing / restoring projects. `TemplateGraph(sp.Item)` is a template drawn as an ordinary Workspace graph. **It wraps methods of the existing pages** (`tp.table_of`, `tp.combos`, `tp.draw_combo`, `tp.add_files`, `ws.load`, `ws.draw`, `ws.refresh_list`): a change to those methods must be tried with the workbench installed | `tests/test_workbench_ui.py` (15), `tests/test_starthere_parity.py` (54) |
| `workspace_starthere.py` | The three columns. `add_files` adds to the selected project, or to the session when none is selected (never forces a project). `add_disk_folder(directory)` = "Add folder…" / a dropped folder: the data files of a disk folder, sub-folders as project folders (a project named after the folder when none is selected). `open_projects` = "Open selected" (then Workspace); `open_workspace`. While files are being read, `inspect_current` waits for a file that is not read yet instead of reading it on the window's thread | same |
| `workspace_design.py` (new) | Style of the new pages; `install_header` rebuilds the header from the widgets the shell made. **Every widget that is shown later must be put back into `topbar_layout`** (the update lost two and they covered the top-left corner). `AdaptiveHeader` hides brand / search / quick buttons / View-Tools-Help / Add files by window width; these get minimum width 1 so the window can be made narrow. `PAGE_TIPS` + `install_tooltips`: the tooltips of Start here and Workbook | `tests/test_session_basics.py`, `tests/test_workbench_ui.py` (12) |
| `workspace_workbook.py`, `workbook_data.py` (new) | `WorkbookPage` (page 7) and `merge_tables` (append rows / join columns, both validated). The 5.55.7 dialog `arrange_workbook` is still in `workspace_workbook.py` | `tests/test_workbench_core.py` (MergeTests), `tests/test_edit_graph.py` |
| `workspace_graph_editor.py` (new) | `GraphEditor` (template graphs: whole graph or one panel) and `NativePanelEditor` (composed previews, Sample pages). Controls are enabled only where the graph has the component (`mapping` of the graph: `tick rows`, `background`) | `tests/test_workbench_ui.py` (09) |
| `opstudio/detection.py` (new) | `detect(table, override)` → `Detection(kind, confidence, evidence, confirmed, form)`; `xrd_form` (scan / fit / peak list); `fit_columns` (observed / calculated / difference / background by name); `KINDS` (the Data type list) with `CATEGORY_KINDS` naming whole classes of the catalogue; `compatibility(template, tables, detection, overrides)` = the input checks | `tests/test_workbench_core.py` (44) |
| `opstudio/graph_components.py` (new) | `render_rietveld` (per-panel options of the fit templates) and `apply(fig, switches)` (markers, insets, background of any template figure, per panel through `panel_options`) | `tools/audit_graph_operations.py` |
| `opstudio/data.py` | `_rietveld` takes its columns by name (`fit_columns`), by position only when unnamed; `read_tables` says in words when a file has no table; `_example(template)`: the template's example made once and copied (was rebuilt on every `bundle`) | `FitMappingTests` |
| `opstudio/api.py` | `recommend` = detection + `compatibility` (returns `[]` while the kind needs confirming); the fit templates are drawn through `render_rietveld`; `RULES` is still used by the per-template sheet picker | `tests/test_opstudio.py` (63) |
| `workspace_templates.py` | `tick_files` (ticks in one step, one ranking); `ticked_tables(first_only)`; `_table_for_template_wb` (the sheet that fits the ticked template, on the working copies); column choices are stored per file and sheet by the workbench **and** remembered per header pattern in `templates_page.mappings` as before | `tests/test_templates_page.py` (70) |
| `workspace_qt.py` | `Loader(..., warm=)`: the reader's thread also reads the tables the pages need (`ws._warm_tables`); `ActivePageStack`; page 7; `save_cfg` returns True / False | all |
| `tools/audit_graph_operations.py` (new) | Tries every per-graph control on every template and workbook graph type; writes `docs/GRAPH_OPERATIONS_AUDIT.md` | run it after changing `graph_components.py` or a template |

`workbook_cache.sheets(path)` (new, 5.57.1): one parse of an Excel workbook per version of the file, handed out as copies; used by `paper_figures.load_sheets`, `auto_recipe.load`, `TemplatePage._read_all` and `opstudio.data.read_tables`. Before it, every redraw of a composed figure re-read the workbook. `opstudio.origin.send` (5.57.1) writes its commands down and sends them in the driver's order (books, graph, layers, rest) and then calls `Driver.check` - sending them as they came left a workbook active when the plot commands ran, and the graph was empty in Origin. `Workbench.ready(path)` / `read_in_background`: large files are read off the window's thread. Files in no project are tree nodes `('session','','')` / `('file','',path)` in Start here.

`opstudio/origin.py` (5.57.2) - what Origin 2018 really did with a workbook figure, read from the owner's screenshots, and what the sender does about it. Keep these when touching it:
`label -a x y` with a negative number loses the text (the number is read as an option) -> texts are made at max(x, 0), max(y, 0) and then moved with `T.x=` / `T.y=` (the driver's own `text` does the same);
a layer made with `layer -n` has no `xb` / `yl` objects -> axis titles are texts at the figure's own place (`xlabel_at`, `ylabel_at` of `read_figure`), `xb` / `yl` are hidden;
Origin scales everything in a layer with the layer's width -> every size is multiplied by `_scale(L)` = 62 / width % (measured: 40.5 % wide -> 0.67, 23.4 % -> 0.37);
a legend-only axes is no layer; legends (`read_figure()["legends"]`, of axes and of the figure) are texts `\l(n) name`, n matched by name, else colour (+ hatch / symbol), attached to the layer with most matches;
a text of several lines is one text per line; grouped columns get one more x value at width / 0.8 with no height (column width = 80 % of the smallest x step); columns are plotted before curves;
`send` replays the axis commands of every layer after `Driver.check` (`plotxy` refills reset the axes).
Not confirmed in Origin: hatch (`set -pfv`), the frame of layers after the first (`showAxes=3`). `www.originlab.com` could not be reached from the session to read the LabTalk reference; the owner's `origin_commands_log.txt` is the evidence to ask for.
`office_export.py` (5.57.2): `write_pptx` / `write_docx` fill `opstudio/office/blank.pptx` / `blank.docx` (moved there in 5.58.1) (made once by `tools/build_office_templates.py` with python-pptx / python-docx; the app needs neither). `Workspace.send_to_office("pptx" | "docx")`.
`ws.hidden_groups` (5.57.2): the ★ figures of the app the user removed, as `(how, member keys)`; filtered in `regroup`, saved as `modern_hidden_groups`, part of the session Undo snapshot, cleared by a choice in the Group list.

5.58.0 - series of files, worked-out columns, peaks:
`related.py` (new): `series(names)` / `groups(names)` (names built the same way; a file in a `derived` folder belongs to no series), `side_by_side(inputs, extra)`, `dtg_column(table)`, `peak_table(kind, table)`, `names_of`, `name_at`, `TOLERANCE`, `PEAKS_SHEET`. `opstudio/ftir_core.py` (new): `REFERENCE_BANDS`, `suggest(position)`; thermal events stay in `opstudio/tga_core.REFERENCE_EVENTS`.
Start here: `StartHerePage.series_of(paths, focus)`; `_mode_user` (your own choice of the combine box for the ticked files - set by `currentIndexChanged`; the app's own changes block the signal), `_rec_paths` (the files the offered graphs are for). `Workbench.recommendations(..., series=True)` adds 6 (7 for "stack") to templates whose id or name matches `SEVERAL`.
`Workbench._table`: columns in `sheet_settings[sheet]['derived']` are dropped unless in `'derived_on'`; with no order chosen or remembered, X and Y come from `detection.preferred_xy(table)` (cached in `_xy_cache`).
Workbook: entries of the file list whose `Qt.UserRole` is not a string are the app's side-by-side tables (`('series', paths, label)`); `add_worked_columns`, `set_column_everywhere`, `columns_to_all`, `open_peaks`, `labels_toggled`. `Workbench.peak_frame / peak_names / set_peak_labels / apply_peak_names`; labels are stored as `sheet_settings[sheet]['peak_labels']` (`[[position, label]]`) and `'peak_names_on'`.
Builders: `det['_peak_names']` (`[(position, label)]`) makes `build_tga` / `build_ftir` write the label beside the position; without it the labels are unchanged (the updater's regression, `self_update.check`, still gives the same Origin commands for 10 of 10 example files). Results rows get `May be` / `Other possibilities`.
`smart_plots.read_tables`: a CSV whose headers are all `column [tag]` is returned as one table per tag (`_split_side_by_side`, path noted in `SIDE_BY_SIDE`); `TemplatePage._read_all` then gives one sheet per tag.

5.58.1: `WorkingTableModel.clear_cells / delete_rows / delete_columns` change the working frame IN PLACE (the same object is held by `Workbench.working`) and push `('table', before, after)` on the undo list; `_put` restores a snapshot in place. `WorkbookPage.delete_in_table / delete_rows / delete_columns / hide_columns / table_menu / remove_files / files_menu / show_peaks / refresh_peak_column`.
`Workbench.sync_selection(index)` runs from `page_changed` when the page before was Start here (6): `_drop_graphs` (one Workspace Undo step) for listed-but-unticked inputs, `select_inputs(ticked)`, and on page 0 `ws.load` for ticked loose files not read yet (`open_inputs` skips inputs without a project) / `open_inputs` for project files. `deselect_inputs(paths)` is the same from the Workbook. `StartHerePage.ticked_inputs / listed_inputs / untick_paths`; a file first listed while its graphs are in Workspace starts ticked (`_listed`).
Your graphs: `menu_graphs` keeps a multi-row highlight; `remove_file_graphs`; Shift+Delete = `remove_ticked`; the older `_graphs_list_menu` is disconnected in `workspace_actions.install`.
Drawing defaults changed on purpose (the updater reports different examples): `finish()` honours `spec['xround']` (TGA: 100); `build_tga` drops DTG peaks within max(15 °C, 2 %) of the start and uses `dplot` / `dun` in `split`; `ftir_bands()` leaves out `FTIR_AIR_CO2` and 25 cm-1 at both ends.
`self_update.program_files` installs top-level files by extension and the folders in `PROGRAM_DIRS` only: a data file the program needs must live inside one of those folders (the Office files moved to `opstudio/office` for that reason; `tests/test_workspace_actions.py` checks it for every data file). The updater that copies the files is the one of the INSTALLED version, so adding a folder to `PROGRAM_DIRS` does not help the update that introduces it.
Analysis: `TemplatePage.chosen(least)` = kept previews, else all previews on show; `_nothing(what, least)`; `to_workbook()`.
Merge (side by side) writes `related.merged_workbook` (.xlsx: a sheet per file + `OVERVIEW_SHEET`); `smart_plots._without_overview` drops that overview sheet when the workbook has two or more other sheets (or splits it when it is alone), `TemplatePage._best_sheet` never picks it.
A table with a column of words in every row is read by the Workspace loader as a label table, not as data - test files must not have one.

5.58.2: `WorkingTableModel.paste / insert_rows / insert_column / rename_column / sort_by / fill_down / add_calculated / letters` (all through `_change`; `_fill` replaces the frame's content in place); page: `copy_cells / cut_cells / paste_cells / insert_row / insert_column / rename_column / sort_column / fill_down / add_calculated`, `table_tools` menu. `add_calculated` evaluates the formula with `eval` in a namespace of column letters and a few numpy functions only, after refusing `__`, `import`, `lambda`, brackets and `;`.
`Workbench.peak_frame` falls back to the results table of a loaded XRD graph (kind `'XRD'`, read-only in `open_peaks`).
`office_export.send_live(kind, files)` (pywin32: `GetActiveObject` / `Dispatch` of `PowerPoint.Application` / `Word.Application`), tried first on Windows by `send_to_office`, file route on any exception; tests replace `office_export._office` with stand-ins and set `w._office_live`.
Workspace: `main_axes()`, `spans` (one SpanSelector per graph), `on_span(a, b, ax)` sets `sel_panel`, `curves(it)` reads that panel, `reset_axes()` returns 'one' / 'all' using `_home_limits` and `_last_ax` (set by `_note_graph` in `workspace_actions.install`).
Analysis: `remove_files` uses `Workbench.deselect_inputs`; Delete shortcut on `TemplatePage.files`.

5.58.6: XRD is stacked in every case. `make_groups` also stacks peak lists that no pattern in the list uses (`Combined(..., "stack", ..., "_peaks")`, kind "XRD peak list"); `Combined.build` has its own branch for that kind (baseline per sample, sticks divided by the sample's strongest peak, colour per curve label across samples, labels placed upright with `place_labels(..., vertical=True)`, sample names in `texts`). In the stack of measured patterns labels that are whole names (`upright`: any label part longer than 5 letters) are placed upright with step 1.6; letter codes are placed as before.

5.58.5: `pdf_names.py` (new): `table_names(df)` recognises a pattern list (a column of reference codes + Compound / Mineral Name, no position column), `register` keeps code -> name (also in `pdf_names.json` of the private folder), `name_of`, `codes_in`, `looks_coded`, `clean`, `mineral`, `split_text` (a peak list and a pattern list in one text file). `smart_plots.detect` returns such a table as `kind="skip"` with `pattern_list`; `peaklist_rows` expands a 'Matched by' column of codes to one row per code with Phase = Code = the name (`d["_pdf"] = {"named", "unnamed"}`); `build_peaklist` labels the sticks, draws unmatched peaks grey, sets `_xlim`, stores nothing in the phase library; `refresh_pdf_names(singles, opt)` (called by `prepare`) rebuilds peak lists that were waiting for names and the patterns linked to them.

5.58.4: the two Analysis graphs follow the user's reference pictures. `templates_materials.draw_ftir`: spectra offset by `offset` (15), x ascending, one marker line per spectrum (`_nolegend_`, symbols only) and `ax.text` labels in DATA coordinates (an `annotate` with offset points is read at the wrong place by `origin.read_figure`), names from `_ftir_labels` (`smart_plots.find_peaks` + `ftir_core.suggest`, `_mathtext` for the small figures), legend lower left; more than four spectra: names at the top one only. `draw_tga_zones`: `ZONES_CEMENT` when the data has no zones, names inside (`ZONE_INK`), `_rate(s, default)` reads °C/min from the run's time column, `_dtg` works on uneven measured temperature. `opstudio/data.py` thermal bundling: a table with exactly ONE mass column is one sample (its temperature and mass; time kept as `time`), several mass columns stay a sample per column. `api.recommend`: +5 for `tga_dtg_zones_multi` with several TGA tables. Workbook: `open_sheet` shows `related.OVERVIEW_SHEET` / `PEAKS_OVERVIEW` as read-only views that do not become `prefs['sheet']`; `open_file` opens a merged workbook on the overview until another sheet is chosen (`_views`); `WorkingTableModel.setData` refuses when `read_only`. `smart_plots.merged_copy(path)` / `without_copies(items)`: `Workspace.regroup` leaves the sheets of an app-merged workbook out of the automatic combined figures while their source files are loaded.

5.58.3: peak columns are a LIST from row 0 (`related.peak_columns(kind, n_rows, peaks)` -> position, label, meaning); `related.WORKED_NAMES` are never data (`Workbench._table` drops them, `add_worked_columns` marks them `derived`, also the sparse ones of 5.58.1 / 5.58.2). `related.peak_column` / `meaning_column` (sparse form) are no longer used by the app. `merged_workbook(path, inputs, extra, peaks)`: per-file sheets = data + DTG, `PEAKS_OVERVIEW` sheet, `OVERVIEW_SHEET` last; both extra sheets are skipped by `smart_plots._without_overview` and `TemplatePage._best_sheet`. `detection.compatibility`: `ftir_stacked_bands` / `raman_stacked` accept one series; `api.recommend` adds 4 for them. `related.series`: a trailing 1-2 digit part that only some names have is a repeat number. Sheets: `WorkbookPage.add_sheet / remove_sheet / sheet_names`, `removed_sheets` in the file's settings (applied in `Workbench.raw_sheets`), new sheets live in `edited_sheets`.

Not done / to know: Windows and a live Origin were not available (PySide6 offscreen on Linux, Origin dry run; the Origin order was checked by following the active window through the commands). A big workbook still needs one header-less parse and one normal parse. The `figures-5.55.2`
workbook-of-figures work is unchanged and its tests (`tests/test_figures_general.py`, 37) pass.

## 2. What was changed (file by file)

| File / module | Change | Why (brief section) | Tests covering it |
|---|---|---|---|
| `origin_plot_app/opstudio/` (new package) | Template × style × data engine | §6.1 | `tests/test_opstudio.py` (45) |
| `opstudio/core.py` | Styles, registry, `render`, `save`; figures are plain `Figure` objects inside `rc_context` (nothing global changes); `target` = draw into a cell of a combined figure; `width` = draw at an export width | §6.1, §6.6, §6.8.5 | same |
| `opstudio/data.py` | `Table`, `read_tables`, `bundle(template, tables)`: fills a bundle shaped like the template's demo from the user's tables and returns the mapping; `NeedData` says what is missing | §6.4 | same |
| `opstudio/api.py` | `draw`, `export`, `min_size_warnings`, `recommend`, `combine`, variant `SWITCHES`, user templates, `.opst` | §6.2–6.6, §6.8 | same |
| `opstudio/origin.py` | `read_figure` (figure → layers), `send` (layers → the app's Origin driver), `draw_in_origin` (`{sample}_{template}.opju` + `.ogs`), `write_ogs` | §6.7 | `tests/test_opstudio.py` (17 Origin checks) |
| `opstudio/templates_materials.py`, `templates_general.py` | The pack's 104 draw functions with neutral illustrative data | §6.5.2 | every template draws; previews rebuilt |
| `opstudio/templates_figures.py` | Composed figures: particle size 2 × 2 with tables, calorimetry pair with inset and group brackets, flow diagram | owner's reference layouts | `tests/test_opstudio.py` |
| `opstudio/templates_tier1.py`, `kinetics.py` | 14 Tier-1 templates; OFW / KAS / Friedman / Kissinger | §6.5.3, §11 | known-answer checks in `tests/test_opstudio.py` |
| `opstudio/tga_core.py` | The pack's TGA calculations, unchanged | §10 | `tests/test_tga_core.py` |
| `opstudio/templates/*.json`, `styles/*.json`, `previews/*.png`, `origin/*.ogs`, `catalog.json`, `catalogue_all_graph_types.json` | Built by `tools/build_template_library.py` and `tools/build_origin_scripts.py`; styles carry `limits` | §6.5–6.7 | `tests/test_opstudio.py` |
| `origin_plot_app/workspace_templates.py` (new) | The Templates page: six dock panels, multi-select lists, preview grid, editor, export dialog, combine, batch Origin, workbook, my templates | §6.2, §6.8 | `tests/test_templates_page.py` (41) |
| `origin_plot_app/workspace_session.py` (new) | File far left, quick Save / Undo / Redo, command search, clear / start afresh with undo, save / recent, autosave timer, recovery flag, tooltips for buttons that had none, TGA menu entry | §3, §4 | `tests/test_session_basics.py` (32) |
| `origin_plot_app/workspace_tga.py` (new) | `TgaAnalysis` (no Qt) and the dialog: zones, both methods, confirm labels, label memory, Excel, Origin | §9, §10 | `tests/test_tga_module.py` (37) |
| `origin_plot_app/private_store.py` (new) | The user's private folder | publishing rules | used by the tests through `OPS_PRIVATE_DIR` |
| `origin_plot_app/workspace_qt.py` | The gallery (page 5) is shown inside Analysis: `GALLERY_PAGES = (5, 1)` with a switch at the top of both pages (*Graphs and templates* · *Calculations*); `NAV_ORDER = [0, 1, 3, 4]` (four top-bar sections); page 2 (the old list of workbook graph types) is built but not shown – its 26 types are pictures in the gallery (`wb:G01` …); installs `workspace_session`; clears the running flag on close | §3, §6 | window tests |
| `origin_plot_app/workspace_shell.py` | Top bar buttons follow `NAV_ORDER` | §3 | `tests/test_shell_layout.py` |
| `origin_plot_app/workspace_ribbon.py` | `last_change` time stamp (for the one Undo), `quick_bar` (hidden: one visible Save / Undo / Redo) | §3 | `tests/test_ribbon_sketch.py` |
| `origin_plot_app/workspace_actions.py` | Ctrl+S calls Save | §4 | `tests/test_workspace_actions.py` |
| `origin_plot_app/self_update.py`, `workspace_menu.py` | `opstudio` is a program folder; `incomplete()` fetches the same version again when that folder is missing (first update from an older updater) | delivery | – |
| `origin_plot_app/smart_plots.py`, `xrd_smart.py` | Reads the private folder (phase files, `paper_main`); sessions with the old kind prefix still open | publishing rules | all earlier tests |
| `origin_plot_app/gallery_graphs.py` and others | Renamed module and neutral wording (no behaviour change) | publishing rules | `tests/test_gallery_graphs.py` (34) |
| `tools/check_banned.py` | Privacy check; the term list is outside the repository | publishing rules | runs as git hook |
| `tools/build_template_library.py`, `build_origin_scripts.py`, `screenshot_templates.py` | Rebuild JSON / previews / scripts; screenshots | §14 | – |

### Command map changes
See `COMMAND_MAP.md`. Commands removed: **none**. Ctrl+Q moved from Exit to the command search.

## 3. Claude Code MAY change

| Area | What is allowed | Constraints |
|---|---|---|
| Templates page layout, wording, tooltips | rearrange, add commands | every command stays reachable; update `COMMAND_MAP.md` |
| `opstudio/templates_*.py` | add templates (Tier 2, Tier 3) | `@template(...)` with roles, a neutral demo and the Origin hint; run both build tools; set `template_id` and `status` in the catalogue file; a known-answer check for every calculation |
| `opstudio/data.py` | new bundle shapes | never invent data; raise `NeedData` with what is missing; return the mapping |
| `opstudio/origin.py` | better Origin equivalents (stacked columns, error bars, category axes, contour) | keep `read_figure`'s structure; keep optional commands `soft`; update `DIFFERENCES.md` by the build tool |
| Styles | add presets | `opstudio.style/1`; landscape; `limits` when the publisher gives minimums |
| Panels | make Assistant and Settings panels; collapse; named layouts | closing a panel never deletes work; a damaged layout must not stop the start |

## 4. Claude Code MUST NOT change

| Protected item | Reason |
|---|---|
| **Nothing of the owner's work in the repository.** `tools/check_banned.py` must pass before every commit; the term list and the allow list live outside the repository (`OPS_BANNED_TERMS`). Never commit `_upgrade_pack/`, `screenshots/`, `sample_data/`, `my_templates/`, `ops_private/`, real data, real names or result values. Demo data stays neutral (Sample A–F, Series 1–3, Additive (wt.%)) | owner's publishing rule |
| The user's files are only read; derived values are new arrays | rule R2 |
| Label policy: texts on a graph come from the file or from the user; reference positions only from the user's peak list; TGA zone names are suggestions with "?" until confirmed and are never exported unconfirmed | rule R3, §9 |
| Landscape output; TG + DTG in one graph with DTG at its natural sign | rules R4–R5 |
| `opstudio/tga_core.py`, `opstudio/kinetics.py`, `calorimetry.py`, `analysis_tools.py` and their tests | validated calculations |
| Session file format (additive only); `figtype_id` and `session_load` accept the old kind prefix | old projects must open |
| Assistant: providers, key storage, history, upload, what is sent out | user workflow |
| The Origin driver in `origin_plot_app.py` (`Driver`, `run_items`) and the updater's check (`self_update.check`): the 10 example files must give the same Origin commands | user workflow, update safety |
| Section numbers 0–4 of `SECTIONS` (tests and shortcuts use them); new sections are appended and ordered with `NAV_ORDER` | stability |
| Panels: `_float_window` must not change window flags while a panel is dragged (that stops the drag); only `panel_as_window` makes a normal window | panels must be movable |
| Git history: no rewriting, no force push, unless the owner says so in those words | owner's rule |

## 5. Instructions for Claude Code (next tasks, in order)

1. **Verify in real Origin** (needs the owner's Windows computer): acceptance check 13 for the five cases, side by side with the preview. Fix refused commands (see `origin_commands_log.txt` beside each project). Then *Build Origin templates (.otpu)*.
2. **Finish Tier 1**: isopleth / pseudo-binary diagram, element map grid, hot-stage microscopy (they need image or polygon input: add those bundle shapes first).
3. **Panels**: Assistant and Settings as dock panels; collapse button; *Save layout as…*; per-section reset.
4. **Editing model** (§7): stable object IDs, curve / axis / legend context menus, format painter, nudge keys, Insert menu (reference line, bracket, shaded region, chemical formula).
5. **Export** (§8): EMF (file and clipboard), the Export dialog in Workspace, Convert files with unit conversions, the extra importers.
6. **Labels** (§9): Confirm labels panel for FTIR / Raman bands and other reference tables; label memory there too.
7. **Toolbox** (§11): LOWESS, ALS baseline, Weibull, Bland–Altman as a tool, clinker moduli, amorphous content by internal standard as a tool, carbonation and chloride fits – each with a known-answer test.
8. **Tier 2, then Tier 3** of the catalogue (127 and 83 rows).

### How to run
```
python -m venv venv && venv/bin/pip install PySide6 matplotlib pandas numpy scipy openpyxl pillow
venv/bin/python origin_plot_app/start.pyw                      # the app
QT_QPA_PLATFORM=offscreen venv/bin/python tests/test_templates_page.py    # one test file (each is a script; exit code 1 on a failure)
for t in tests/test_*.py; do QT_QPA_PLATFORM=offscreen venv/bin/python $t || echo FAILED $t; done
venv/bin/python tests/test_xrd_generator.py <any .xrdml scan that is not named SAMPLE>
venv/bin/python tools/build_template_library.py && venv/bin/python tools/build_origin_scripts.py
OPS_BANNED_TERMS=<private list> venv/bin/python tools/check_banned.py --all
```

### Definition of done for each task
* implemented in the engine or the window, not as a picture;
* its acceptance check re-run and recorded in `TEST_REPORT.md` as pass / fail / not verified;
* all test files pass; the updater's check still gives the same Origin commands for the example files;
* `tools/check_banned.py --all` is clean; `COMMAND_MAP.md` and `CHANGELOG.md` updated.

## 6. Open questions for the owner

1. **Old commits on GitHub.** All branches now point to the clean commit, but GitHub can still show an old commit to someone who has its address until GitHub removes unreferenced commits. To be certain: ask GitHub Support to purge them, or delete the repository and create it again from the clean branch. The two old branch names could not be deleted from here; they now hold the clean commit and can be deleted in GitHub's branch list.
2. **The account name is part of the repository address** (and of the updater's source). Changing it means a new address in `self_update.DEFAULT_SOURCE`.
3. *(answered by the owner: the gallery is inside Analysis since 5.54.0; no separate Graph gallery section.)*
4. **EMF**: is Origin's own EMF export after "Draw in Origin like this" enough, or is an EMF writer in the app needed?
5. **Amorphous content formula** (brief §11): not implemented as a tool yet; the formula in the brief will be used as written unless you say otherwise.

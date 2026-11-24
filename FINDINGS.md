# FINDINGS – Origin Plot Studio before the v2 upgrade

Step zero of `01_MASTER_PROMPT_Origin_Plot_Studio_v2.md`. Written on branch `upgrade-v2`, from app version 5.50.0.
Everything here was checked in the code or by running it; what could not be checked is marked.

## 1. Starting state (run, not assumed)

| Check | Result |
|---|---|
| Pack reference test `test_tga_core.py` | **passes**: CH 12.28 wt.% (expected 12.34), CaCO3 4.52 wt.% (expected 4.55); 3 zones suggested, each "ASK USER" |
| App test suites (25 files, run headless with `QT_QPA_PLATFORM=offscreen`) | **all pass**: 673 checks, 0 failures (list in section 8) |
| App starts (headless) and loads the example files | yes |
| Origin | **not available here** (Linux container). The Origin path is tested through the dry run only (`origin_plot_app.py --dry-run`, a mock that records the LabTalk commands). Nothing in this upgrade can be verified in real Origin by me. |
| Windows | **not available here.** Windows-only parts (DPAPI key storage, shortcuts, EMF clipboard) cannot be verified by me. |
| Pack `screenshots/` and `sample_data/` | not in the pack. Real sample files are in `04_user_reference_figures/…/plain_one_sheet_per_graph` (31 xlsx). |

## 2. Stack

* Python 3, **PySide6 (Qt 6)** desktop window; **matplotlib** renderer (`FigureCanvasQTAgg`); pandas, numpy, scipy, openpyxl.
* Entry point: `origin_plot_app/start.pyw` → `workspace_qt.main()`. `Setup.bat` / `setup.pyw` install to the user's programs folder.
* Origin bridge: **COM** (`win32com`, `Origin.ApplicationSI`) sending LabTalk, in `origin_plot_app.py` (`Driver`, `run_items`). No `originpro`.
* Self-update: `self_update.py` reads the `main` branch on GitHub and copies top-level program files plus four folders
  (`figure_recipes`, `phase_library`, `examples_synthetic`, `gallery`).
* The repository is **public**.

## 3. Architecture (who does what)

| Module | Lines | Role |
|---|---|---|
| `smart_plots.py` | ~4 400 | The engine: `load_file` (file → `Item`s), kind detection, `Item.build` → **spec** (the graph model: title, x name, panels, curves, labels, inset …), `Combined` / `SamplePage` / `Board` figures, `make_groups`, `preview_figure` (spec → matplotlib), per-graph format `fmt`, session dump/load |
| `origin_plot_app.py` | ~4 000 | Origin `Driver` (spec → LabTalk), `run_items`, publication files, `save_analysis`; the old Tk window (no longer reachable) |
| `workspace_qt.py` | ~2 100 | The window: pages, Workspace, settings, jobs, style sheet |
| `workspace_shell.py` | ~520 | Top bar, dock panels in Workspace, layout save / restore / reset |
| `workspace_ribbon.py` | ~1 150 | Formatting ribbon, per-graph `fmt` with undo/redo, click / double-click / right-click / drag editing, Edit dialog |
| `workspace_tools.py` | ~1 500 | Analysis and Graph gallery pages (browser / setup / preview / gallery docks), all tool actions |
| `workspace_menu.py`, `workspace_actions.py` | ~1 300 | Menus, sessions, updates, mouse and key actions, context menus |
| `workspace_assistant.py`, `assistant.py`, `web_free.py` | ~2 700 | Assistant panel, providers, key storage, web search |
| `analysis_tools.py` | 44 general tools (smoothing … statistics) with known-answer tests |
| `gallery_graphs.py` | 26 gallery graph types (G01–G24, C01, C02) drawn from workbooks |
| `sketch_pad.py`, `xrd_*`, `calorimetry.py`, `xrd_suggest.py` | sketch design, XRD scan generator and peak correction, calorimetry workflow, phase library |

**Trace file → export.** `load_file(path)` → `Item` (kind, `det` with the numbers; the file is never written) → `prepare` (links peak lists,
builds) → `Item.spec` → `apply_fmt` (the user's edits) → `preview_figure` (screen) / `publication_figure` (PNG 600 dpi, TIFF, PDF, SVG) /
`Driver` (Origin). Sessions: `session_dump` / `session_load` (JSON with files, kinds, sample names, custom forms, `fmt`).

## 4. Graph model and editing today

* The model is the **spec** dictionary per graph plus the user's **`fmt`** (titles, fonts per kind of text, axis ranges / colour / weight,
  curve colour / weight, legend, zoom, moved labels). `fmt` is applied after every build, so edits survive redraw, save / reopen, export and Origin.
* Undo / redo exist **per graph for formatting only** (ribbon). Removing graphs or files, grouping and sessions are not undoable.
* There are **no stable object IDs**; objects are addressed by role (title, axis titles, numbers, labels, legend), curve label and panel index.
* No inserted objects (arrows, shaded regions, free text) in the model, except notes from the sketch pad (preview / publication only).

## 5. Panels today (brief section 5)

| Section | State |
|---|---|
| Workspace | 6 `QDockWidget` panels: Your graphs, Graph, Data, Results, Details, Graph settings – movable, floatable, tabbable, closable |
| Analysis | 4 docks: Analyses, Setup, Preview and results, Gallery |
| Graph gallery | 4 docks: Graph types, Gallery, Setup, Preview and results |
| Assistant | a dock beside the work **or** a fixed full page; inside it nothing is a panel |
| Settings | a fixed two-column page; **not** panels |
| Layout | saved on close (`panel_layout` in `settings_modern.json`), restored at start, View › Reset layout. **No named layouts, no per-section reset, no collapse button** (only close / float) |

Why Assistant and Settings are fixed: they were written as plain pages before the dock system (`workspace_shell.py`) existed.

## 6. Gallery today (brief section 6)

* `origin_plot_app/gallery/` holds 45 PNG thumbnails (26 gallery types, 19 analysis groups) made by `tools/make_gallery.py`.
* Graph gallery page: a category tree (XRD, FTIR, NMR, TGA, Calorimetry, Phases, Particle size, General plots, Thermodynamic modelling)
  and a `QListWidget` icon grid. Single selection only. A click opens that type's setup.
* **No template / style / data separation**: each gallery type is a Python drawing function with its own workbook layout. No style presets
  (one house style in code, plus Size and look). No multi-select, no "preview with my data" across templates, no compare grid,
  no user templates, no `.opst`, no recommender beyond kind detection and `suggest()` for XY tables.

## 7. Command area today (brief section 3)

* One navy top bar: name, section tabs, Find a graph, then **File ▾, View ▾, Tools ▾, Help ▾ and Add files on the right** (the brief wants File far left).
* Formatting ribbon (Workspace only): Home, Insert, Draw, Design, Layout, Axes, Lines; quick Save / Undo / Redo at its left.
* **No command search.** Tooltips: 7 visible buttons have none (found by `tools/command_inventory.py`); tooltips do not give shortcut or the reason a command is disabled.
* Full inventory (170 entries: menus, ribbon, buttons, shortcuts, panels): **Appendix A**. It is the baseline for `COMMAND_MAP.md`.

## 8. Baseline tests (all pass)

```
tests/test_analysis_tools.py:      17 PASS 
tests/test_assistant.py:      35 PASS 
tests/test_calorimetry.py:      26 PASS 
tests/test_drag_labels.py:       8 PASS 
tests/test_edit_dialog.py:      10 PASS 
tests/test_edit_graph.py:      30 PASS 
tests/test_highscore.py:      25 PASS 
tests/test_look_progress.py:      14 PASS 
tests/test_peak_correct_tab.py:      18 PASS 
tests/test_ribbon_sketch.py:      37 PASS 
tests/test_shell_layout.py:      41 PASS 
tests/test_stop_analysis.py:       9 PASS 
tests/test_thermal_photo.py:      18 PASS 
tests/test_gallery_graphs.py:      34 PASS 
tests/test_workspace_actions.py:      30 PASS 
tests/test_workspace_main.py:      69 PASS 
tests/test_workspace_qt.py:      29 PASS 
tests/test_workspace_steps34.py:      89 PASS 
tests/test_xrd_background.py:      14 PASS 
tests/test_xrd_correction.py:      19 PASS 
tests/test_xrd_generator.py:      17 PASS 
tests/test_xrd_generator_actions.py:      19 PASS 
tests/test_xrd_window_origin.py:      10 PASS 
tests/test_zoom_pen.py:      24 PASS 
xrd_scan_generator/tests/test_engine.py:      26 PASS
```

## 9. Gaps against the brief (what the upgrade has to add)

| Brief | Gap |
|---|---|
| §3 | File far left; Quick Access beside it; tabs Home · Insert · Graph · Data · Analysis · Gallery Graphs · Export · View · Help; full tooltips; command search (Ctrl+Q); customise |
| §4 | Clear Graph / Clear All Graphs / Remove files with undo (soft delete), Start Afresh, Save As, Recent, timed autosave and recovery |
| §5 | Assistant and Settings as panels; collapse; named layouts; per-section reset |
| §6 | Template × style × data engine; 104 templates, 9 styles; trees, filters, multi-select, live previews, compare grid, batch, my templates, `.opst`, recommender, role mapping |
| §7 | Object selection model with IDs, insert objects, format painter, full context menus, nudge keys |
| §8 | Export dialog (EPS, EMF, JPG, sizes, patterns), convert tool, more importers |
| §9 | Confirm-labels panel, "?" labels never exported, label memory |
| §10 | TGA zones (draggable), tangent and stepwise loss, CH / CaCO3, Excel export – today only mass loss in intervals |
| §11 | Parts exist (44 tools, calorimetry, PSD d-values); missing: kinetics, PCA, ANOVA letters, clinker moduli, amorphous by internal standard … |

## 10. Decisions taken (and why)

1. **Stay on `upgrade-v2`; `main` is not touched until you say so.** Your installed app updates itself from `main`, and you said the
   current version works well; half-finished stages must not reach it.
2. **Your own figures and data are never committed.** The repository is public; `_upgrade_pack/` is git-ignored. Tests that use
   your real sheets run only when the pack folder is present, and are skipped (and reported as skipped) otherwise.
3. **The pack's templates, styles and synthetic previews are shipped with the app** (about 10 MB; previews are marked illustrative and contain no data of yours).
4. **The pack's reference renderer is used as the gallery's drawing code**, vendored as a package inside the app, rather than
   rewriting 104 draw functions into the spec engine. Reason: it is the tested contract; a rewrite would be weeks of work with new errors.
   Consequence: template graphs go to Origin as plain sheets plus the template's `origin_hint` (not through the LabTalk spec driver). Marked in the handoff.
5. **Keep Qt's own docking (`QDockWidget`)**, no new docking library: it is what the app has, and it does everything the brief lists except a collapse button, which is added.
6. **Existing 26 gallery types and all current commands stay**; they become entries of the new gallery ("Gallery (workbook types)").

## Appendix A – command inventory (baseline)

| Command | Location | Shortcut | Tooltip |
|---|---|---|---|
| New project | Top bar ▸ File | Ctrl+N |  |
| Add data files… | Top bar ▸ File | Ctrl+O | Add data files	Ctrl+O |
| Open session… | Top bar ▸ File | Ctrl+Shift+O | Open session	Ctrl+Shift+O |
| Resume last session | Top bar ▸ File | Ctrl+Shift+R |  |
| Save session… | Top bar ▸ File | Ctrl+S | Save session	Ctrl+S |
| Import from an Origin project… | Top bar ▸ File |  | Import from an Origin project |
| Convert files to Excel… | Top bar ▸ File |  | Convert files to Excel |
| Save everything as one workbook… | Top bar ▸ File |  | Save everything as one workbook |
| Workbook template… | Top bar ▸ File |  | Workbook template |
| Make a gallery graph template… (G01–G24, C01, C02) | Top bar ▸ File |  | Make a gallery graph template (G01–G24, C01, C02) |
| Refresh previews | Top bar ▸ File |  |  |
| Open results folder | Top bar ▸ File |  |  |
| Exit | Top bar ▸ File | Ctrl+Q |  |
| This graph: PNG 600 dpi · TIFF · PDF · SVG | Top bar ▸ File ▸ Save and export | Ctrl+E |  |
| The view on screen as a picture… | Top bar ▸ File ▸ Save and export | Ctrl+Shift+E | The view on screen as a picture	Ctrl+Shift+E |
| Copy the view to the clipboard | Top bar ▸ File ▸ Save and export | Ctrl+Shift+C |  |
| Data table as CSV or Excel… | Top bar ▸ File ▸ Save and export |  | Data table as CSV or Excel |
| Results table as CSV or Excel… | Top bar ▸ File ▸ Save and export |  | Results table as CSV or Excel |
| Session… | Top bar ▸ File ▸ Save and export | Ctrl+S | Session	Ctrl+S |
| Open a session… | Top bar ▸ File ▸ Save and export | Ctrl+Shift+O | Open a session	Ctrl+Shift+O |
| The chat as a text file… | Top bar ▸ File ▸ Save and export |  | The chat as a text file |
| Open the results folder | Top bar ▸ File ▸ Save and export |  |  |
| Side bar | Top bar ▸ View | Ctrl+1 |  |
| Your graphs | Top bar ▸ View | Ctrl+2 |  |
| Graph settings | Top bar ▸ View | Ctrl+3 |  |
| Assistant | Top bar ▸ View | Ctrl+4 |  |
| Focus on the graph | Top bar ▸ View | F11 |  |
| Show everything | Top bar ▸ View |  |  |
| Your graphs as its own window | Top bar ▸ View |  |  |
| Graph settings as its own window | Top bar ▸ View |  |  |
| Assistant as its own window | Top bar ▸ View |  |  |
| Put the panels back in place | Top bar ▸ View |  |  |
| Workspace: Your graphs | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Graph | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Graph settings | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Data | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Results | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Details | Top bar ▸ View ▸ Panels |  |  |
| Analysis: Analyses | Top bar ▸ View ▸ Panels |  |  |
| Analysis: Setup | Top bar ▸ View ▸ Panels |  |  |
| Analysis: Preview and results | Top bar ▸ View ▸ Panels |  |  |
| Analysis: Gallery | Top bar ▸ View ▸ Panels |  |  |
| Graph gallery: Graph types | Top bar ▸ View ▸ Panels |  |  |
| Graph gallery: Setup | Top bar ▸ View ▸ Panels |  |  |
| Graph gallery: Preview and results | Top bar ▸ View ▸ Panels |  |  |
| Graph gallery: Gallery | Top bar ▸ View ▸ Panels |  |  |
| Assistant beside the work | Top bar ▸ View ▸ Panels |  |  |
| Reset layout | Top bar ▸ View |  |  |
| Always show the ribbon | Top bar ▸ View ▸ Formatting ribbon |  |  |
| Show tabs only | Top bar ▸ View ▸ Formatting ribbon |  |  |
| Hide the ribbon (Ctrl+F1 shows it) | Top bar ▸ View ▸ Formatting ribbon |  |  |
| Side bar | Top bar ▸ View ▸ More | Ctrl+1 |  |
| Your graphs | Top bar ▸ View ▸ More | Ctrl+2 |  |
| Graph settings | Top bar ▸ View ▸ More | Ctrl+3 |  |
| Assistant | Top bar ▸ View ▸ More | Ctrl+4 |  |
| Focus on the graph | Top bar ▸ View ▸ More | F11 |  |
| Show everything | Top bar ▸ View ▸ More |  |  |
| Your graphs as its own window | Top bar ▸ View ▸ More |  |  |
| Graph settings as its own window | Top bar ▸ View ▸ More |  |  |
| Assistant as its own window | Top bar ▸ View ▸ More |  |  |
| Put the panels back in place | Top bar ▸ View ▸ More |  |  |
| Draw ticked graphs in Origin | Top bar ▸ Tools ▸ Draw | F5 |  |
| Draw all graphs in Origin | Top bar ▸ Tools ▸ Draw | Shift+F5 |  |
| Save this graph (PNG 600 dpi · TIFF · PDF · SVG) | Top bar ▸ Tools ▸ Draw | Ctrl+E |  |
| Your own graph… (columns, style, axes) | Top bar ▸ Tools ▸ Draw | Ctrl+Shift+D | Your own graph (columns, style, axes) |
| Peak labels you type… | Top bar ▸ Tools ▸ Draw | Ctrl+Shift+L | Peak labels you type |
| Label peaks automatically (positions) | Top bar ▸ Tools ▸ Draw | Ctrl+L |  |
| Figure from the ticked graphs (panels a, b …) | Top bar ▸ Tools ▸ Draw |  | Figure from the ticked graphs (panels a, b ) |
| Preview paper set (PDF) | Top bar ▸ Tools ▸ Draw |  |  |
| Make paper set | Top bar ▸ Tools ▸ Draw |  |  |
| Paper figures from a recipe… | Top bar ▸ Tools ▸ Draw |  | Paper figures from a recipe |
| All analyses… | Top bar ▸ Tools ▸ Analysis |  | All analyses |
| Graph gallery… | Top bar ▸ Tools ▸ Analysis |  | Graph gallery |
| TGA: mass loss in temperature intervals | Top bar ▸ Tools ▸ Analysis |  |  |
| Calorimetry (TAM III)… | Top bar ▸ Tools ▸ Analysis |  | Calorimetry (TAM III) |
| FTIR: band areas… | Top bar ▸ Tools ▸ Analysis |  | FTIR: band areas |
| Thermodynamic modelling… | Top bar ▸ Tools ▸ Analysis |  | Thermodynamic modelling |
| Find peaks | Top bar ▸ Tools ▸ Analysis |  |  |
| XRD Scan Generator… | Top bar ▸ Tools ▸ XRD tools |  | XRD Scan Generator |
| Peak correct / improve an XRD scan… | Top bar ▸ Tools ▸ XRD tools |  | Peak correct / improve an XRD scan |
| Phase library… | Top bar ▸ Tools ▸ XRD tools |  | Phase library |
| Check for updates… | Top bar ▸ Help |  | Check for updates |
| Install an update from a zip file… | Top bar ▸ Help |  | Install an update from a zip file |
| Undo the last update | Top bar ▸ Help |  |  |
| Where updates come from… | Top bar ▸ Help |  | Where updates come from |
| System Check | Top bar ▸ Help |  |  |
| Problem report… | Top bar ▸ Help |  | Problem report |
| Mouse actions and keyboard shortcuts | Top bar ▸ Help | F1 |  |
| About Origin Plot Studio | Top bar ▸ Help |  |  |
| Copy | Ribbon ▸ Home |  | Copy the picture of the graph (Ctrl+Shift+C) |
| Save picture | Ribbon ▸ Home |  | Save the picture |
| Reset look | Ribbon ▸ Home |  | Back to how the app draws this graph |
| A↑ | Ribbon ▸ Home |  | Bigger letters |
| A↓ | Ribbon ▸ Home |  | Smaller letters |
| B | Ribbon ▸ Home |  | Bold (Ctrl+B) |
| I | Ribbon ▸ Home |  | Italic (Ctrl+Shift+I) |
| x₂ | Ribbon ▸ Home |  | Subscript: the selected letters (Ctrl+=) |
| x² | Ribbon ▸ Home |  | Superscript: the selected letters (Ctrl+Shift++) |
| A | Ribbon ▸ Home |  | Text colour |
| Clear the format of this text | Ribbon ▸ Home |  | Clear the format of this text |
| ↘ | Ribbon ▸ Home |  | More: Font |
| Apply | Ribbon ▸ Home |  | Apply the typed title |
| Undo | Ribbon ▸ Home |  | Undo the last change of this graph's look (Ctrl+Z) |
| Redo | Ribbon ▸ Home |  | Redo (Ctrl+Y) |
| Edit on the graph | Ribbon ▸ Home |  | Click a text, a curve or the axes in the graph; double click a title to type it; right click for more |
| Sketch a design | Ribbon ▸ Insert |  | Draw how the figure should look (frames, the zoom, curves, titles, legend) - or trace a photo of a sketch - an |
| Add files | Ribbon ▸ Insert |  | Add data files (Ctrl+O) |
| Panel figure | Ribbon ▸ Insert |  | A figure for a paper: the ticked graphs as (a), (b) … |
| Draw freely | Ribbon ▸ Draw |  | Draw your design with a pen, your finger (touch screen) or the mouse |
| Zoom | Ribbon ▸ Draw |  | Drag a box to zoom (Z) |
| Pan | Ribbon ▸ Draw |  | Drag to move (P) |
| Select range | Ribbon ▸ Draw |  | Drag a 2θ / x range (S) |
| Reset axes | Ribbon ▸ Draw |  | The whole graph again (double click on it, Ctrl+R) |
| App look | Ribbon ▸ Design |  | How the app draws it |
| Black && white | Ribbon ▸ Design |  | Black text, axes and curves |
| Bold paper | Ribbon ▸ Design |  | Bold letters, heavier axes and curves |
| Light | Ribbon ▸ Design |  | Normal letters, fine axes and curves |
| Slides | Ribbon ▸ Design |  | Large letters for a presentation |
| Serif | Ribbon ▸ Design |  | Times New Roman everywhere |
| Navy | Ribbon ▸ Design |  | Dark blue axes and titles |
| Stack | Ribbon ▸ Layout |  | One above the other with an offset |
| Overlay | Ribbon ▸ Layout |  | On common axes |
| Panels | Ribbon ▸ Layout |  | One panel each |
| Decide for me | Ribbon ▸ Layout |  | XRD fits and patterns: the app decides |
| Panel figure | Ribbon ▸ Layout |  | A figure for a paper: the ticked graphs as (a), (b) … |
| Apply | Ribbon ▸ Axes |  | Use these ranges |
| Automatic | Ribbon ▸ Axes |  | The app's ranges again |
| Axis colour | Ribbon ▸ Axes |  | Colour of the axes, ticks included |
| Line colour | Ribbon ▸ Lines |  | Colour of this curve (or of all) |
| Automatic | Ribbon ▸ Lines |  | The app's colours and weights again |
| Add files… | Workspace (button) |  | Add data files (Ctrl+O); you can also drop them on the window |
| Tick all | Workspace (button) |  | Ctrl+A |
| Untick all | Workspace (button) |  | Ctrl+Shift+A |
| Stack | Workspace (button) |  | Your own group: the ticked graphs of one kind in one figure, stacked with an offset |
| Overlay | Workspace (button) |  | Your own group: the ticked graphs of one kind in one figure, on common axes |
| Ungroup | Workspace (button) |  | Remove the group you made that is ticked or on show |
| + Add data files | Workspace (button) |  |  |
| Apply | Workspace (button) |  |  |
| … | Workspace (button) |  | Choose the results folder |
| Export ▾ | Workspace (button) |  |  |
| Draw in Origin | Workspace (button) |  | Draw the ticked graphs in Origin (or the one on show): Origin does the final work |
| Zoom | Workspace (button) |  |  |
| Pan | Workspace (button) |  |  |
| Select range | Workspace (button) |  |  |
| Reset axes | Workspace (button) |  |  |
| (shortcut) | window | Ctrl+Return |  |
| (shortcut) | window | Ctrl+Z |  |
| (shortcut) | window | Ctrl+Y |  |
| (shortcut) | window | Ctrl+B |  |
| (shortcut) | window | Ctrl+Shift+I |  |
| (shortcut) | window | Ctrl+= |  |
| (shortcut) | window | Ctrl+Shift++ |  |
| (shortcut) | window | Ctrl+F1 |  |
| (shortcut) | window | Ctrl+O |  |
| (shortcut) | window | Esc |  |
| Graph types | Panel (figtypeBrowserDock) |  | movable, floatable, closable |
| Setup | Panel (figtypeSetupDock) |  | movable, floatable, closable |
| Gallery | Panel (figtypeGalleryDock) |  | movable, floatable, closable |
| Preview and results | Panel (figtypePreviewDock) |  | movable, floatable, closable |
| Analyses | Panel (analysisBrowserDock) |  | movable, floatable, closable |
| Setup | Panel (analysisSetupDock) |  | movable, floatable, closable |
| Gallery | Panel (analysisGalleryDock) |  | movable, floatable, closable |
| Preview and results | Panel (analysisPreviewDock) |  | movable, floatable, closable |
| Details | Panel (detailsDock) |  | movable, floatable, closable |
| Results | Panel (resultsDock) |  | movable, floatable, closable |
| Data | Panel (dataDock) |  | movable, floatable, closable |
| Your graphs | Panel (graphsDock) |  | movable, floatable, closable |
| Graph settings | Panel (settingsDock) |  | movable, floatable, closable |
| Graph | Panel (graphDock) |  | movable, floatable, closable |
| Assistant | Panel (assistantDock) |  | movable, floatable, closable |

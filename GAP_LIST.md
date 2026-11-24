# GAP_LIST – brief v2.1 against the app (version 5.50.0, branch `upgrade-v2`)

Status: **done** = works today and is tested · **partly** = some of it exists · **missing** = not there.
"File / feature" names the code that exists today or will carry the change.
The wording is neutral on purpose: the user's own reference figures are called the *private reference set*, and the house style is called *house_style_1*.

Counted from the pack: 104 templates (none has an `origin_template` / `.otpu` yet), 9 styles, 372 catalogue rows
(121 implemented · 17 tier 1 · 127 tier 2 · 107 tier 3).

---

## A. Priority 1 – §6.8 Multiple selection everywhere

| # | Requirement | Status | Where today / what is missing |
|---|---|---|---|
| 8.1a | Click / Ctrl / Shift / Ctrl+A, same in every list | **partly** | `workspace_qt.py` graph list ("Your graphs") uses `ExtendedSelection`. Gallery (`workspace_tools.py`, `QListWidget`) is single-select; the file list, sheets, columns, styles and panels lists are not multi-select |
| 8.1b | Checkboxes on every item, *Select all in this category*, *Clear selection* | **partly** | Ticks exist on the graph list (`ItemIsUserCheckable`, "Draw ticked"). They are missing in the gallery, styles, files, sheets/columns and curves |
| 8.1c | Visible count "n files · n templates · n styles selected" | **missing** | — |
| 8.2 | Applies to files, sheets, columns, template graphs, styles, workspace graphs, curves in a graph, panels | **partly** | Only workspace graphs (and curves through the Edit dialog, one at a time) |
| 8.3 | Preview grid files × templates × styles from real data; enlarge a tile; tick the ones to keep | **missing** | Needs a new compare-grid panel on the template × style × data engine (section C) |
| 8.4a | Batch: Open all in editor | **missing** | — |
| 8.4b | Batch: **Draw all in Origin like this** | **partly** | "Draw ticked / all in Origin" (`origin_plot_app.py` `run_items`, `workspace_menu.py`) works for workspace graphs. Nothing for template graphs (depends on §6.7) |
| 8.4c | Batch: Export all at journal size and dpi | **partly** | Publication files (PNG 600 dpi / TIFF / PDF / SVG, `smart_plots.publication_figure`) for the loaded graphs. Missing: export of the selection only, the size from a style preset, and EMF |
| 8.4d | Batch: apply the same style or edits to all | **partly** | The per-graph `fmt` (`workspace_ribbon.py`) can be copied by the sketch-pad design. There is no "apply to selection" and no style presets |
| 8.4e | Batch: data and results of all to one Excel workbook, one sheet per file | **partly** | "Save everything as one workbook…" (`workspace_menu.write_workbook`) covers all loaded graphs; missing the selection-only scope and the results sheets |
| 8.4f | Batch: remove selected | **partly** | Removing graphs exists; it is not undoable (see §4) |
| 8.5 | **Combine into one figure**: 1×2, 2×2, 2×3, stacked, custom; auto (a)(b) labels; shared axes; in-app **and** in Origin | **partly** | Panel figures / `Board` / `Combined` (`smart_plots.py`) and Origin multi-layer exist for workspace graphs, with automatic letters. Missing: a layout chooser (1×2…2×3, custom), template graphs as panels, the shared-axes option and the label format that follows the preset |
| 8.6 | Progress bar + cancel for large selections, no freezing | **partly** | Drawing progress and a Stop button exist for analysis jobs (`workspace_tools.py`, `StatusLabel`). They are missing for batch preview / export / Origin |
| 13.14 | Acceptance check 14 (3 files + 4 templates + 2 styles → 24 previews → keep 6 → 6 Origin graphs → 2×3 figure → export 6 files) | **missing** | Needs everything above |

## B. Priority 2 – §6.7 Template graph → my data in that shape → the same graph in Origin

| # | Requirement | Status | Where today / what is missing |
|---|---|---|---|
| 7.1 | Clicking or ticking a template redraws the selected files in that layout and style (live) | **partly** | The 26 workbook graph types (`gallery_graphs.py`) draw the user's workbook in one fixed style. The pack's 104 templates are not in the app yet |
| 7.2 | **Draw in Origin like this** (button, right-click, Ctrl+Shift+O): same layout, panels, insets, offsets, ranges, scales, reversals, shaded zones, fonts, colours, widths, markers, legend, panel labels; data in a worksheet laid out for that graph | **partly** | The LabTalk driver (`origin_plot_app.Driver`) does this for the app's own spec graphs: panels, insets, offsets, ranges, labels and fonts. Template graphs have no Origin path. FINDINGS decision 4 (plain sheet + `origin_hint`) is **not enough for v2.1** and is replaced: each template gets its own Origin script |
| 7.3 | Each template ships a `.otpu` plus a LabTalk/originpro apply script; `origin_template` in the JSON; a one-line "what differs" when Origin cannot match | **missing** | 0 of 104 templates have `origin_template`. `.otpu` files can only be made in Origin (Windows), which this container doesn't have. Plan: generate the **LabTalk script per template** here (testable with the dry-run mock). On the user's PC, a one-time "Build Origin templates" command runs each script in Origin and saves the `.otpu` (*Save Template As*) into the template folder |
| 7.4 | Several files at once (one graph per file, or one multi-panel graph); works for the user's own saved templates (*Save as my template* also creates the `.otpu`) | **missing** | Depends on 7.3 and §6.3 *Save as my template* (missing) |
| 7.5 | Each graph saved as `.opju` named `{sample}_{template}` in a chosen folder; export from Origin at the preset size and dpi | **partly** | `.opju` saving exists for the Origin path (`origin_plot_app.py`). The `{sample}_{template}` naming and the preset size/dpi export are missing |
| 13.13 | Acceptance check 13 (five reference sheets + raw TGA: in-app preview ≙ Origin graph, side by side) | **missing** | Origin isn't available here, so the visual part will be marked **not verified**. The scripts and worksheets will be unit-tested against the dry-run mock. The check runs only from the private reference set on the user's PC (those files are never committed) |

## C. §6.1–6.6 Gallery engine, catalogue, styles

| # | Requirement | Status | Where today / what is missing |
|---|---|---|---|
| 6.1 | Graph = Template × Style × Data; `opstudio.template/1`, `opstudio.style/1` contracts; any template in any style | **missing** | Each graph type today is a Python function with a fixed look. Plan: vendor the pack's reference renderer as `origin_plot_app/opstudio/` |
| 6.2a | Two-level tree (graph families / domain packs + My templates + private reference set) with counts; search; filters | **partly** | One-level category tree with 9 techniques (`workspace_tools.py`). No counts, search or filters |
| 6.2b | Thumbnail grid: name, use case, badge, ✓; hover = large preview + roles + Origin equivalent | **partly** | Icon grid of 45 thumbnails (`gallery/`). No badges, checkboxes or hover card |
| 6.2c | *Preview with my data* (live renders); compare view; Open / Create all / Send to Origin / Export all; apply to all files | **missing** | — |
| 6.2d | Recommender (top 3 by data kind / headers / units, 15 rules in the brief) | **partly** | Kind detection (`smart_plots.load_file`) and `suggest()` for XY tables. There is no ranking across templates |
| 6.3a | House style as default | **partly** | One house look in code. It becomes the style `house_style_1` (neutral name; the original stays private) |
| 6.3b | *Save as my template*; `.opst` export/import | **missing** | — |
| 6.3c | *Make template from a reference figure* (image → closest template and style) | **partly** | Sketch pad / photo tracing (`sketch_pad.py`) gives a layout from a picture. There is no matching against the template library |
| 6.3d | Add the newly attached figures as templates | **missing** | Only as anonymised templates; the real figures go to the private folder only |
| 6.4 | Column-to-role mapping panel, drag-drop, remembered per header pattern; panel order for multi-file | **partly** | Column choosers in the analysis setup (`workspace_tools.py`). No role panel and no memory |
| 6.5.1 | Global variant switches (log / reversed / break / top axis, inset zoom, error style, fill/hatch, markers, offset/normalise, single↔multi-panel, colour-blind palette, landscape) on every template | **partly** | Several exist in `fmt` / spec (ranges, log, reverse, inset zoom, offset, markers, landscape). Missing: axis break, a secondary top axis with transform, error band/caps choice, hatch, the single↔multi switch, and one shared switch set for all templates |
| 6.5.2 | 104 implemented templates ported and checked against previews | **missing** | Not in the app. 24 of them carry names or demo labels from the private reference set and need anonymising first (see E) |
| 6.5.3 | Tier 1 (17 rows) | **missing** | Parts of the calculations exist: DTG peaks / onset (`smart_plots.py`), calorimetry, XRD stacks. No kinetics (Kissinger/OFW/KAS/Friedman), Sankey, Pareto front, regression bands |
| 6.5.4 | Tier 2 (127 rows) | **missing** | Some tools exist in `analysis_tools.py` (44 tools incl. Tukey); no templates |
| 6.5.5 | Tier 3 (107 rows) | **missing** | — |
| 6.5.6 | Per new template: JSON, illustrative landscape preview, Origin path, calculations, known-answer test | **missing** | — |
| 6.5.7 | Coverage per catalogue section in TEST_REPORT | **missing** | — |
| 6.6 | Publisher presets (Elsevier, Nature, Springer/RILEM, RSC, ACS + house, slides, greyscale, Okabe–Ito); export warns below minimum size; panel label format per preset | **partly** | Journal sizes exist in "Size and look". There are no style files, no minimum-size warning and no label format per preset |

## D. Earlier stages (§3–§5, §7–§12)

| § | Requirement | Status | Where today / what is missing |
|---|---|---|---|
| 3 | File menu far left; Quick Access; tabs Home·Insert·Graph·Data·Analysis·Templates·Export·View·Help | **partly** | `workspace_shell.py` top bar has File/View/Tools/Help on the **right**. The ribbon (`workspace_ribbon.py`) has Home/Insert/Draw/Design/Layout/Axes/Lines with Save/Undo/Redo |
| 3 | Tooltips everywhere with shortcut + description + disabled reason; status bar echo | **partly** | Most buttons have tooltips; 7 have none (`tools/command_inventory.py`). None gives the disabled reason |
| 3 | Command search Ctrl+Q; right-click customise / labels / size | **missing** | — |
| 4 | New / Open / Recent / Save / Save As | **partly** | New project, Resume last session and session save/load exist (`workspace_menu.py`). Recent and Save As for sessions are missing |
| 4 | Clear Graph, Clear All Graphs, Remove selected/all files, soft delete + undo, summary prompt | **partly** | Removing exists. No undo and no summary |
| 4 | Start Afresh (keep settings & layout), Reset Layout, autosave every N min + crash recovery | **partly** | Start afresh (Ctrl+N) and an autosave on change with Resume exist (`workspace_qt.py`, `workspace_menu.autosave`). Timed autosave and crash recovery are missing |
| 5 | Dock panels for every section incl. Assistant and Settings; collapse; named layouts; per-section reset; safe recovery | **partly** | Workspace (6 docks), Analysis (4) and Templates (4) are docks (`workspace_shell.py`, `saveState`). Assistant and Settings are fixed pages. No collapse, named layouts or per-section reset |
| 7.1 | Mouse/key model (select objects, rubber band, pan, wheel zooms, Alt-range, drag objects, drop on canvas/thumbnail, nudge, copy/paste format, F2) | **partly** | Click-select text, double-click edit, right-click, drag labels, wheel zoom (`workspace_ribbon.py`, `workspace_actions.py`). Missing: object IDs for curves/axes/legend, rubber band, nudge, format painter, F2, drop on a thumbnail |
| 7.2 | Context menus for canvas, curve, axis, legend, text, zone, file, thumbnail, table column | **partly** | Canvas and graph-list menus exist. Curve, axis, legend, zone, thumbnail and column menus are missing |
| 7.3 | Insert menu (text, panel label, arrow, bracket, shaded region, reference line, inset, legend, table, image, scale bar, equation, chemical formula …) | **partly** | Ribbon Insert has text/arrow/inset through the sketch design. The rest is missing |
| 7.4 | One model, stable IDs, one undo step per edit, survives redraw/save/export | **partly** | `fmt` survives redraw/save/export/Origin. No stable IDs; undo covers formatting only |
| 8 | Import (drag-drop, folder, + button; instrument formats) | **partly** | Excel/CSV/TXT, HighScore, NETZSCH STA, TAM calorimetry, Origin projects. Missing: JCAMP-DX, electrochemistry, rheometer and modelling-software tables, image scale metadata, remembered manual mapping |
| 8 | Export Figure dialog (scope, PNG/TIFF-LZW/JPG/PDF/SVG/EPS/**EMF**, sizes from style, dpi, transparent, fonts, name pattern, batch); clipboard image + EMF | **partly** | Publication files exist. No dialog, EMF or clipboard EMF |
| 8 | Export Data (CSV/XLSX + derived + results + settings; Origin-ready sheet); Convert Files tool (units, sheet split/join, 2θ↔d) | **partly** | Convert files and one workbook exist (`workspace_menu.py`). Unit conversions are partial |
| 9 | Confirm-labels panel; "?" for unconfirmed labels, never exported; label memory; XRD labels only from files or confirmed memory | **partly** | XRD already labels only from the user's peak lists (`smart_plots.py`). There is no Confirm-labels panel, no "?" guard on export and no label memory per material/technique |
| 10 | TGA/DTG module (normalisations, blank, SG DTG, onset/endset, draggable zones, stepwise **and** tangent loss, CH/CaCO₃/Mg(OH)₂, bases, replicates, Excel with 5 sheets + chart) | **partly** | DTG, peaks, onset/endset and mass loss between fixed limits (step method) exist in `smart_plots.py`. Missing: draggable zones, the tangent method, CH/CaCO₃ and the 5-sheet export. `tga_core.py` from the pack passes its reference test |
| 11 | General toolbox (smoothing, baselines, peaks/deconvolution, fits with CI/PI, stats incl. PCA/Tukey/Bland–Altman/Weibull, FFT, isoconversional kinetics, Pareto, Sankey check) | **partly** | 44 tools in `analysis_tools.py`. Missing: kinetics, Bland–Altman, Weibull, LOWESS, ALS baseline, Herschel–Bulkley, CI/PI bands |
| 11 | Domain calculations (calorimetry bases, XRD amorphous by internal standard, clinker moduli LSF/SM/AM/Bogue, PSD RRSB, strength CoV, carbonation k, chloride erfc) | **partly** | Calorimetry and PSD d-values / RRSB exist. Missing: clinker moduli, the internal-standard formula as a tool, carbonation k and chloride fit |
| 12 | Visual tokens, empty start screen (Add files · Choose analysis · Browse templates), Assistant panel | **partly** | Tokens are applied (`theme.py`). The start screen differs. The Assistant panel exists but is a fixed page (see §5) |
| 13.1–12 | Acceptance checks 1–12 | **not run** | Run at the end; the checks that need Origin or Windows will be reported as not verifiable here |
| 14 | CHANGELOG, COMMAND_MAP, TEST_REPORT, screenshots, catalogue statuses, CLAUDE_CODE_HANDOFF | **missing** | FINDINGS.md and the command inventory exist |

## E. Publishing hygiene (new rules, before any code change)

| Item | Status | Note |
|---|---|---|
| `.gitignore`: `_upgrade_pack/` | **done** | — |
| `.gitignore`: `sample_data/`, `screenshots/`, `my_templates/`, the user's `*.xlsx` / `*.opju` | **missing** | Needs care: the app ships some generic `.xlsx` (synthetic examples, workbook templates, test inputs), so the rule must ignore all and whitelist those paths |
| Pre-commit banned-term check on staged files | **missing** | Plan: `tools/check_banned.py` plus a local git hook. The term list lives **outside** the repo (in the private folder), because the list itself names the user's work |
| Private folder loaded at start (`%APPDATA%\OriginPlotStudio\my_templates`) + local, uncommitted install script | **missing** | — |
| Anonymise the pack before shipping: 24 templates, the house style, `catalog.json`, the renderer's demo labels; regenerate the previews from neutral data | **missing** | Must be done before any template reaches the repository |
| Already-public content in the repository and its history | **found – needs the user's decision** | Reported separately in chat, not in this file |

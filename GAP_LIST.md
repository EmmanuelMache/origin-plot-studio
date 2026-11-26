# GAP_LIST – brief v2.1 against the app (version 5.58.0)

Status: **done** = works and is tested · **partly** = some of it exists · **missing** = not there.
Evidence for every "done" is in `TEST_REPORT.md`. Wording is neutral on purpose (no names of anyone's work).

## §6.8 Multiple selection everywhere

| Requirement | Status | Where |
|---|---|---|
| Click / Ctrl / Shift / Ctrl+A, tick boxes, Select all in category, Clear selection | **done** on the Templates page (files, columns, templates, styles); Workspace graph list as before | `workspace_templates.py` |
| Visible count "n files · n templates · n styles selected → n previews" | **done** | same |
| Applies to files, sheets, columns, templates, styles, workspace graphs, curves, panels | **partly**: sheets are chosen one at a time; curves inside a graph and panels are not multi-select | – |
| Preview grid files × templates × styles from real data; enlarge; keep | **done** | same |
| Batch: open all, Draw all in Origin, export all, apply style to all, one Excel workbook, remove | **done** (results sheets in the workbook: only the list of graphs and their columns) | same |
| Combine into one figure (1×2, 2×2, 2×3, stacked, custom; letters; shared axes; app and Origin) | **done** in the app; Origin: commands built and tested, **not verified** in Origin | `opstudio/api.combine`, `opstudio/origin.py` |
| Progress and cancel for large selections | **done** | same |

## §6.7 Template graph → the same graph in Origin

| Requirement | Status | Where |
|---|---|---|
| Ticking a template redraws the ticked files in that layout and style | **done** | Templates page |
| Draw in Origin like this (button, right-click, Ctrl+Shift+O): layout, panels, insets, ranges, scales, zones, fonts, colours, markers, legend, labels, worksheets | **done as commands**, tested with the driver's dry run; **not verified** in Origin | `opstudio/origin.py` |
| Each template has an Origin script named in its JSON (`origin_template`); one line per difference | **done** (`origin/<id>.ogs`, `DIFFERENCES.md`) | `tools/build_origin_scripts.py` |
| `.otpu` per template | **partly**: made on the user's computer by *Build Origin templates*; none shipped | – |
| Several files; own templates get a script too | **done** | – |
| Saved as `{sample}_{template}.opju`; export from Origin at preset size and dpi | **done as commands**; **not verified** in Origin | – |

## §6.1–6.6 Engine, catalogue, styles

| Requirement | Status |
|---|---|
| Template × style × data; JSON contracts | **done** |
| Family / domain tree with counts, search, filters | **done**: a tree by instrument / technique and by graph type with counts, search, source and status filters |
| Thumbnails with name, use, badge, tick; hover card | **done** (hover = tooltip with roles and Origin name) |
| Recommender | **done** (16 header rules + "can the file fill it") |
| House style default; private original style | **done** (neutral style shipped; the private one is loaded from the private folder when present) |
| Save as my template; `.opst` | **done** |
| Make a template from a reference picture | **missing** for the template library (the sketch pad of Workspace is unchanged) |
| Column-to-role mapping, remembered | **done** (order and on / off; no drag between named roles) |
| Global variant switches | **partly**: log, reversed, markers, normalise, offset, grid, hatch, top axis, limits. Missing: axis break as a switch, error style, single ↔ multi-panel |
| 104 templates ported and checked against previews | **done** (previews rebuilt from neutral data; compared by eye on a sample, not pixel by pixel) |
| Tier 1 | **partly**: 14 of 17 |
| Tier 2 / Tier 3 | **missing** (127 / 83 rows listed as coming) |
| Publisher presets; warning below minimum; panel label format | **done** |

## Earlier stages

| § | Requirement | Status |
|---|---|---|
| 3 | File far left, Quick Access, command search, tooltips | **done**. Ribbon tabs as in the brief (Home · Insert · Graph · Data · …), right-click customise and compact size: **missing** |
| 4 | Session basics with undo, save / save as / recent, autosave, recovery | **done** |
| 5 | Panels in every section | **partly**: Workspace, Analysis, Graph gallery, Templates. Fold / float / close buttons on every panel: done. Assistant and Settings as panels, named layouts: **missing** |
| 7 | Mouse / keys, right-click menus, Insert menu, object model | **partly** (as before the upgrade, plus menus on files, templates, previews and TGA zones) |
| 8 | Import, Export dialog, convert, save | **partly**: export dialog on the Templates page (no EMF); the rest as before |
| 9 | Confirm labels | **partly**: TGA zones done; FTIR and other bands missing |
| 10 | TGA / DTG module | **done** (blank correction and the user's own Excel template: missing) |
| 11 | Toolbox and domain calculations | **partly**: kinetics added; the rest as before |
| 12 | Visual system, start screen, Assistant | **partly** (unchanged) |
| 13 | Acceptance checks | see `TEST_REPORT.md` |
| 14 | Deliverables | **done**: CHANGELOG, COMMAND_MAP, TEST_REPORT, CLAUDE_CODE_HANDOFF, catalogue statuses; screenshots are made by `tools/screenshot_templates.py` and are not published |

## Composed figures (5.55.0)

| Requirement | Status | Where |
|---|---|---|
| A recipe for any workbook, without writing JSON | **done** (automatic; figure-plan sheet used when present) | `auto_recipe.py`, Tools ▸ Draw |
| Recipe figures in Origin | **done as commands** (dry run); **not verified** in Origin | `paper_figures.run(origin=…)` |
| Recipe editor (change a made recipe in the window) | **missing**: the recipe is a JSON file in your recipe folder | – |

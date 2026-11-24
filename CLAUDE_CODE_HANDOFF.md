# CLAUDE_CODE_HANDOFF.md – Origin Plot Studio

Read this file first. It says what exists in the code now, not what is intended.

## 1. Summary

* App version: **5.52.3** (branch `upgrade-v2`; `main` is the published branch the updater reads).
* Built and run on: Linux container, Python 3.12, PySide6 (offscreen), matplotlib, pandas, numpy, scipy, openpyxl.
  **Origin not available. Windows not available.**
* This round: publishing hygiene (no user data in the repository, private folder, privacy check before every commit);
  the template × style × data engine (118 templates, 9 styles); the Templates page with multiple selection, the preview
  grid and batch actions; "Draw in Origin like this"; command area and session basics; the TGA / DTG module; Tier 1 of
  the graph catalogue (14 of 17 rows).
* The repository's history was replaced by one clean commit at 5.51.0 (the owner asked for it). Do not restore old history.

## 2. What was changed (file by file)

| File / module | Change | Why (brief section) | Tests covering it |
|---|---|---|---|
| `origin_plot_app/opstudio/` (new package) | Template × style × data engine | §6.1 | `tests/test_opstudio.py` (45) |
| `opstudio/core.py` | Styles, registry, `render`, `save`; figures are plain `Figure` objects inside `rc_context` (nothing global changes); `target` = draw into a cell of a combined figure; `width` = draw at an export width | §6.1, §6.6, §6.8.5 | same |
| `opstudio/data.py` | `Table`, `read_tables`, `bundle(template, tables)`: fills a bundle shaped like the template's demo from the user's tables and returns the mapping; `NeedData` says what is missing | §6.4 | same |
| `opstudio/api.py` | `draw`, `export`, `min_size_warnings`, `recommend`, `combine`, variant `SWITCHES`, user templates, `.opst` | §6.2–6.6, §6.8 | same |
| `opstudio/origin.py` | `read_figure` (figure → layers), `send` (layers → the app's Origin driver), `draw_in_origin` (`{sample}_{template}.opju` + `.ogs`), `write_ogs` | §6.7 | `tests/test_opstudio.py` (17 Origin checks) |
| `opstudio/templates_materials.py`, `templates_general.py` | The pack's 104 draw functions with neutral illustrative data | §6.5.2 | every template draws; previews rebuilt |
| `opstudio/templates_tier1.py`, `kinetics.py` | 14 Tier-1 templates; OFW / KAS / Friedman / Kissinger | §6.5.3, §11 | known-answer checks in `tests/test_opstudio.py` |
| `opstudio/tga_core.py` | The pack's TGA calculations, unchanged | §10 | `tests/test_tga_core.py` |
| `opstudio/templates/*.json`, `styles/*.json`, `previews/*.png`, `origin/*.ogs`, `catalog.json`, `catalogue_all_graph_types.json` | Built by `tools/build_template_library.py` and `tools/build_origin_scripts.py`; styles carry `limits` | §6.5–6.7 | `tests/test_opstudio.py` |
| `origin_plot_app/workspace_templates.py` (new) | The Templates page: six dock panels, multi-select lists, preview grid, editor, export dialog, combine, batch Origin, workbook, my templates | §6.2, §6.8 | `tests/test_templates_page.py` (41) |
| `origin_plot_app/workspace_session.py` (new) | File far left, quick Save / Undo / Redo, command search, clear / start afresh with undo, save / recent, autosave timer, recovery flag, tooltips for buttons that had none, TGA menu entry | §3, §4 | `tests/test_session_basics.py` (32) |
| `origin_plot_app/workspace_tga.py` (new) | `TgaAnalysis` (no Qt) and the dialog: zones, both methods, confirm labels, label memory, Excel, Origin | §9, §10 | `tests/test_tga_module.py` (37) |
| `origin_plot_app/private_store.py` (new) | The user's private folder | publishing rules | used by the tests through `OPS_PRIVATE_DIR` |
| `origin_plot_app/workspace_qt.py` | Page 5 "Templates" is shown inside Graph gallery (`GALLERY_PAGES = (5, 2)`, a switch at the top of both pages; `NAV_ORDER` lists the five top-bar sections); installs `workspace_session`; clears the running flag on close | §3, §6 | window tests |
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
3. *(answered: the templates are inside Graph gallery since 5.52.2.)*
4. **EMF**: is Origin's own EMF export after "Draw in Origin like this" enough, or is an EMF writer in the app needed?
5. **Amorphous content formula** (brief §11): not implemented as a tool yet; the formula in the brief will be used as written unless you say otherwise.

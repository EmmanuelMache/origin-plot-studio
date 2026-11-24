# Contributing to Origin Plot Studio

Thank you for helping. Three kinds of contribution are most useful. Keep the app deterministic: nothing in it may let a model
read, change or generate the numbers of a data file, and nothing generated may be executed.

## Phase libraries
- A phase library is a CSV file in `origin_plot_app/phase_library/` (or in `%APPDATA%\OriginPlotApp\custom_plugins\` for your own).
- One row per phase: name, letter code, colour, and the reflections (2θ or d) used to label peaks. Copy `xrd_phase_library.csv` as a start.
- Give the source of the reflection positions (ICDD/COD number or paper) in a comment column.

## Figure recipes
- A recipe is a JSON file in `origin_plot_app/figure_recipes/` (or in the `custom_plugins` folders): `{"figures": [{"name": ..., "panels": [...]}]}`.
- Layout modes include `stacked_offset` (with `offset_mode`: `auto_percent` or `fixed_value`, `palette`, `shared_peak_guides`).
- Figures are landscape, one font family, no boxed legend; curves are labelled directly. A recipe with unreadable content is reported
  in the message log (a line starting with `!!`) and skipped; it never stops the app.

## Synthetic datasets
- Example data in `origin_plot_app/examples_synthetic/` must be invented or generated, never real measurements of unpublished work.
- Every example file must keep rendering exactly as before: run the comparison in `self_update.check` before sending a change.
- Your own data belongs in `examples_your_data/`, which is git-ignored.

## Tests
- `python tests/test_xrd_generator.py TEMPLATE.xrdml`, `python tests/test_calorimetry.py`, `python tests/test_assistant.py`.
- Do not put API keys, tokens or personal paths in any file, commit message or log.

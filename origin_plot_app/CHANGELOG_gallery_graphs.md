# Gallery graph types (G01–G24, C01, C02) – changelog

## 1. Audit before any change (version 5.23.3)

What the app could already do for each type of `GRAPH_CATALOGUE.md`, and where.

| ID | Type | Before | Where it was (function) |
|---|---|---|---|
| G01 | XRD_STACK | partial | `smart_plots.build_xrd` + stacking (`stack_style`), `paper_figures.draw_stacked` (`layout_mode: stacked_offset`); labels from the user's label sheet. Missing: dashed highlight box, zoom window with guide lines, several sheets as panels (a)(b) |
| G02 | XRD_PEAKS_INSET | partial | `build_xrd` with labels and the 2θ inset (`INSETS`). Missing: vertical labels with arrows from a Labels sheet, inset range from an Options sheet |
| G03 | RIETVELD_FIT | partial | `build_fit` (observed, calculated, difference, inset), `paper_figures.rietveld_two_panel`. Missing: χ² = (Rwp/Rexp)² written from Options |
| G04 | NMR_STACK | missing | – (the drawing spec can reverse x: `xrev`) |
| G05 | NMR_DECONV | missing | – |
| G06 | NMR_ANNOTATED | missing | – |
| G07 | TG_DTG | partial | `build_tga`: TG left, DTG right in one graph, natural sign, `analyze_tga_steps`. Missing: Labels sheet with arrows at DTG minima, Ranges sheet as range bars, several ages from one TG/DTG column-pair table |
| G08 | DTG_COMPARE | partial | DTG curves can be drawn as XY lines. Missing: overlay/offset mode with names at the right |
| G09 | XRD_DTG_PAIR | missing | – (`paper_figures` composes panels from a recipe only) |
| G10 | CALORIMETRY_PAIR | partial | `build_calorimetry`, `calorimetry.py` (C1/C2/C3, trapezoid ×3.6). Missing: inset of the first hour, heat flow and cumulative heat side by side from one template |
| G11 | DUAL_Y_LOG | missing | – (spec supports `ylog` and `y2`, not together from two sheets) |
| G12 | PHASE_EVOLUTION | missing | – (no split linear/log time axis) |
| G13 | PANEL_GRID_TIME | missing | – (`Board` combines separate graphs; no LONG layout, no shared legend) |
| G14 | METHOD_COMPARISON | missing | – |
| G15 | MASS_BALANCE | missing | – |
| G16 | VS_RATIO | partial | `build_xy` (lines, replicates with SD). Missing: SD columns as error bars, arrow after the x title |
| G17 | SCATTER_TREND | partial | XY symbols. Missing: point labels from a Label column, linear fit with equation and R² |
| G18 | GROUPED_BAR_ERR | partial | `build_chart` "Bars". Missing: grouped bars with SD error caps, hatch fills |
| G19 | BAR_LINE_COMBO | missing | – |
| G20 | PSD_CUMULATIVE | partial | `build_psd` (one table, D10/D50/D90). Missing: one panel per sheet |
| G21 | STACKED_AREA | partial | `build_thermo` "Phase assemblage (stacked areas)". Missing: names inside the areas, hatching of the anhydrous part, fixed colour per phase name |
| G22 | TERNARY_POINTS | missing | – |
| G23 | TERNARY_CONTOUR | partial | `build_chart` "Contour map" (x–y only). Missing: ternary frame, one panel per quantity, colour bars |
| G24 | REFINEMENT_INDICES | missing | – |
| C01 | HYDRATION_DEGREE | missing | ("Change against the first row" in `build_thermo` is a difference, not α) |
| C02 | ATOMIC_RATIOS | missing | – |

Decision: the existing kinds stay exactly as they are (their example files must give the same graphs). The gallery types are a new
module, `gallery_graphs.py`, that reads the template layouts of the catalogue (Instructions / data sheets / Labels / Options), recognises
the type, draws the publication figure with matplotlib in the app's house style, gives the Origin driver an equivalent graph where the
driver can draw it, and writes the templates. It reuses the app's style (`apply_style`, fonts, 1.5 pt lines), the calorimetry rule
(trapezoid × 3.6), the provenance sidecar and the results table.

## 2. After (version 5.24.0)

Every type is now **done**. The publication figure is drawn by `gallery_graphs.py`; Origin gets the equivalent graphs through the
app's Origin driver (`gallery_graphs.origin_specs` → `Driver.draw_spec`), and the log says in one line what Origin does not get.

| ID | Done by | Origin |
|---|---|---|
| G01 XRD_STACK | `draw_g01`, `_xrd_stack`, `_stack_offsets` (offset so patterns never touch, highlight box, zoom with guide lines, one panel per sheet) | stacked curves + labels; box, guide lines and end names in the publication files |
| G02 XRD_PEAKS_INSET | `draw_g02`, `_inset` (vertical labels with arrows, inset with bold numbers) | curve + labels + inset |
| G03 RIETVELD_FIT | `draw_g03` (difference computed if missing, χ² = (Rwp/Rexp)²) | observed, calculated, difference + inset; χ² text in the files |
| G04 NMR_STACK | `draw_g04` (one panel per sheet, ppm high → low, dotted guides, fanned labels) | one graph per sample, x reversed |
| G05 NMR_DECONV | `draw_g05` (rows = ages, full range | zoom, shared legend, Sum of fit computed if missing) | one graph per age (full range) |
| G06 NMR_ANNOTATED | `draw_g06` (coloured arrows, ppm values as typed, Q⁰…Q⁴ superscripts) | curve + labels, x reversed |
| G07 TG_DTG | `draw_g07` (ONE graph, TG left / DTG right, natural sign, same colour per age, arrows at DTG minima, range bars) | TG + DTG on the second y axis; arrows and range bars in the files |
| G08 DTG_COMPARE | `draw_g08` (overlay or offset with names at the right) | overlay |
| G09 XRD_DTG_PAIR | `draw_g09` (same colour per sample in both panels) | two graphs |
| G10 CALORIMETRY_PAIR | `draw_g10`, `cumulative` (inset of the first hour, trapezoid × 3.6, compared with the file's cumulative columns) | heat flow with inset + cumulative heat |
| G11 DUAL_Y_LOG | `draw_g11` | log left axis + right axis |
| G12 PHASE_EVOLUTION | `draw_g12`, `split_axes` (linear segment with t = 0, // marks, log segment, optional y break, SD error bars) | log time axis without t = 0 (said in the log) |
| G13 PANEL_GRID_TIME | `draw_long`, `to_long` (LONG layout; WIDE input converted and shown) | one graph per panel |
| G14 METHOD_COMPARISON | `draw_g14` (fixed style per method) | one graph per panel |
| G15 MASS_BALANCE | `draw_g15` (reference lines in the legend, annotations as typed) | one graph per panel with the reference lines |
| G16 VS_RATIO | `draw_g16` | lines with error bars |
| G17 SCATTER_TREND | `draw_g17` (linear fit only when asked; equation and R²) | points + fit line |
| G18 GROUPED_BAR_ERR | `draw_g18` (grouped bars, SD caps, hatch option) | grouped columns |
| G19 BAR_LINE_COMBO | `draw_g19` (Difference = NMR − QXRD if missing) | columns + line |
| G20 PSD_CUMULATIVE | `draw_g20` (one panel per sheet, D10/D50/D90 in the results) | one graph per sheet |
| G21 STACKED_AREA | `draw_g21` (fixed colour per phase name, anhydrous hatched, names inside, thin bands in the legend) | area plot |
| G22 TERNARY_POINTS | `draw_g22`, `tern_frame` (CAC bottom-left, PC bottom-right, sulphate top; normalised with a warning) | not in the driver: one line in the log |
| G23 TERNARY_CONTOUR | `draw_g23` (triangulated, 20 levels, colour bar per panel) | not in the driver: one line in the log |
| G24 REFINEMENT_INDICES | `draw_g24` (χ² per row, table in the results) | χ² vs time |
| C01 HYDRATION_DEGREE | `hydration_degree`, `draw_c01` (formula and t₀ row shown; asks when there is no t = 0 row) | one graph per phase |
| C02 ATOMIC_RATIOS | `atomic_ratios`, `draw_c02` (molar masses listed) | one graph per ratio |

In the app:
- **Recognition** (`smart_plots.load_figtype`): a workbook with an Options or Instructions sheet (or the type tag), or with a layout the
  older kinds could not draw, becomes one graph of its gallery type, named in the log. A plain measurement file keeps its old graphs;
  the gallery type that fits it is named in the log and offered under Suggestions (only types of the same measurement).
- **Graph type list and the Assistant**: the 26 types are in the graph-type list, so the AI's "kind" step can choose them; the fixed
  command `figtype_graph` understands e.g. "draw the phase evolution of this file" (G12) and "make a 2×2 grid of hydration degree,
  anhydrite vs gypsum" (G13). Neither can add labels or numbers: gallery graphs take labels only from the file.
- **Templates**: Import and convert › Make a gallery graph template… (`gallery_graphs.make_template`) writes Instructions, data
  sheet(s), Labels and Options from a raw file (TAM export → G10, asking the sample mass; HighScore-style CSV stack → G01; wide
  Rietveld table → G12 or LONG G13; TGA export → G07) and loads the template back.
- **Questions instead of assumptions**: no t = 0 row (C01) or a heat flow in W without a mass (G10 template) → the app asks.
- Graph gallery are never merged into "combined" figures; each is a complete figure.
- Tests: `tests/test_gallery_graphs.py` (34 checks on the templates in `tests/gallery_templates`).

Not done / left as a hook:
- Gallery eq. 3.15 (Rietveld wt % → g/100 g paste): not implemented, as asked; needs the user's exact formula.
- Origin: ternary diagrams (G22, G23), the split time axis (G12), shared legends and in-figure annotations are in the publication
  files only; the log says so for each graph. Not tested with OriginPro itself (no Windows/Origin here): the Origin commands were
  produced and checked in the app's dry run.

## 3. Version 5.25.0

- G10 is drawn as in the house figures. Panel (a) shows heat flow with an inset of the first hours; the inset defaults to 12 h when the run is 48 h or longer, or uses `inset_x_to_h`. The y scale is set by the main peak, not the wetting spike. Regime labels are placed at the peaks and set side by side when they are close. Panel (b) shows cumulative heat with a framed legend and regime brackets on the right, moved apart when they would overlap.
- New `draw_g10_bar`/`bar_q` figure: Q at a time (`bar_at_h`, or the end of the shortest run) per sample. It is given per unit alite when the Samples sheet gives alite fractions, with bold values above the bars and regime brackets over the groups. It is written with the G10 figure (`extra_figures`, `save_extra`) and by `smart_plots.export_publication`.
- Regimes, labels, alite fractions and colours come only from the Samples sheet, or from what you type in the calorimetry dialog.
- `calorimetry.run` also writes C4 (the G10 pair) and C5 (the bars, two or more samples) at 11.7 × 6.5 in and 300 dpi, the same as C1–C3, with `C4_C5_calorimetry_provenance.json`.

## 4. Version 5.26.0

- Calorimetry files in Your graphs, single or combined, are drawn as G10 in the publication files, the preview and the Origin graphs. A helper, `smart_plots.calo_style`, turns the processed numbers (`_calo`: time in h, heat flow in mW/g, cumulative heat in J/g) into a G10 book with `gallery_graphs.calo_book`.
  - Regimes and alite fractions come only from Analysis settings › Calorimetry › "Regimes and alite fractions" (`parse_calo_info`).
  - The bar chart of Q is written when there are two or more samples. Its time is the latest of "Report cumulative heat at (h)" that every run reaches, or the end of the shortest run.
- G10 drawing:
  - The inset uses the same y scale as the main panel (the hydration peaks, not the wetting spike).
  - Regime brackets stay at the true end values; only their names are spread apart, with a thin leader line.

# Graph operations audit

Made by `tools/audit_graph_operations.py` on 2026-11-25 (app 5.57.0). Every cell is the result of trying that control on that graph, drawn from
the template's own example or the workbook type's test workbook - it is not inferred from the number of passing tests.

* **works**: the graph has that component and the control changed it, and only it.
* **n/a**: the graph has no such component (no curve with points, a single panel, no inset, no fit ...). The control is not offered / is greyed out with the reason.
* **FAILS**: the graph has the component and the control did not do what it says.

'Origin commands' is the app's Origin driver in dry-run mode (it writes the LabTalk commands and worksheets). It is not a run in Origin.

## Summary

| Control | works | n/a | FAILS |
|---|---:|---:|---:|
| draws | 148 | 0 | 0 |
| markers | 118 | 30 | 0 |
| one panel only | 35 | 113 | 0 |
| zoom inset | 10 | 138 | 0 |
| difference row | 2 | 146 | 0 |
| Bragg rows | 2 | 146 | 0 |
| background | 0 | 148 | 0 |
| Origin commands | 148 | 0 | 0 |

122 Analysis templates and 26 workbook graph types. Catalogue rows marked "Coming" are not graphs yet and are not in this table.

## XRD & Rietveld

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| XRD pattern with phase labels (`xrd_single_labeled`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Stacked XRD patterns (offset) (`xrd_stacked_offset`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Stacked XRD + zoom panel (`xrd_stack_with_zoom`) | works | works | works | n/a | n/a | n/a | n/a | works |
| XRD panels sharing one x axis (`xrd_multi_panel_shared_x`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Rietveld fit: observed / calculated / difference / Bragg ticks (`rietveld_fit_diff_ticks`) | works | works | n/a | works | works | works | n/a | works |
| Rietveld fits as small multiples (2 x 3) (`rietveld_grid_2x3`) | works | works | works | works | works | works | n/a | works |
| Waterfall (pseudo-3D) for in-situ / temperature series (`xrd_waterfall_3d`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Contour / colour map (2θ vs time or temperature) (`xrd_heatmap_contour`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Peak-shift / diagnostic window (`xrd_peak_shift`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Williamson–Hall plot with linear fit (`williamson_hall`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Lattice parameter vs composition (Vegard-type) (`lattice_param_vs_x`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Secondary top axis (e.g. d-spacing over 2θ, K over °C) (`xrd_dspacing_top`) | works | works | n/a | works | n/a | n/a | n/a | works |
| Pattern(s) with reference stick rows per phase (`xrd_ref_ticks`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Integrated peak area or phase amount against time or temperature (`xrd_peak_area_vs_t`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Phase & chemical composition

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Phase assemblage – stacked bars (`qpa_stacked_bar_100`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Grouped bars with error bars (`qpa_grouped_bar`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Measured vs modelled, one panel per phase (`phase_vs_dosage_lines`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Parity plot (calculated vs measured) (`parity_plot`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Donut chart (single composition) (`donut_composition`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Oxide composition bars (XRF) (`xrf_oxide_bar`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Raw-meal moduli (LSF, SM, AM) with target bands (`raw_meal_moduli`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Ternary diagram (CaO–SiO2–Al2O3 or any 3 components) (`ternary_cas`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Radar chart (multi-criteria) (`radar_properties`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Phase evolution against age (stacked areas) (`qpa_vs_age_area`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Calculated against measured composition (parity) (`bogue_vs_qpa`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Burnability curve: free lime against burning temperature (`free_lime_vs_T`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Thermal analysis (TGA / DTG / DSC)

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| TG and DTG in one graph (DTG natural sign, right axis) (`tga_dtg_single`) | works | works | works | n/a | n/a | n/a | n/a | works |
| DTG of several samples with shaded decomposition zones (`tga_dtg_zones_multi`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| TG curves of several samples (mass %) (`tga_multi_sample_tg`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| TG–DTG panels stacked (one material per panel) (`tga_stacked_panels`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Mass loss per temperature window (stacked bars) (`tga_massloss_stacked_bar`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Portlandite and CaCO3 content from TGA (`ch_cc_content_bar`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Bound water / CH vs age (log time) (`bound_water_vs_age`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| DSC / DTA heat flow with exo/endo indicator (`dsc_heatflow`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| TG + evolved gas (MS / FTIR) panels (`tg_ms`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Tangent (step) method view for one decomposition step (`tangent_method_demo`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Conversion α vs T at several heating rates (`conversion_vs_T`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Kissinger plot (activation energy) (`kissinger_plot`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Activation energy vs conversion (isoconversional) (`ea_vs_alpha`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| High-temperature DTA/DSC with event bands (labels to confirm) (`dta_raw_meal`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Isoconversional lines (OFW / KAS) for α = 0.1 … 0.9 (`ofw_kas_plot`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Friedman plot: ln(dα/dt) vs 1/T at each conversion (`friedman_plot`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Isothermal calorimetry

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Heat flow with early-age inset (`calorimetry_heatflow_inset`) | works | works | n/a | works | n/a | n/a | n/a | works |
| Cumulative heat with regime brackets (`calorimetry_cumulative`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Heat flow (a) + cumulative heat (b) (`calorimetry_two_panel`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Bars with value labels and regime brackets (`normalised_heat_bar_regimes`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Heat flow vs cumulative heat (`heatflow_vs_cumheat`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Heat flow on a logarithmic time axis (`calorimetry_log_time`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Heat-flow curves against sulfate dosage (`sulfate_balance`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Degree of reaction against time (methods compared) (`hydration_degree`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Strength against cumulative heat (or degree of reaction) (`strength_vs_cumheat`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Reactivity test: heat against bound water (`r3_heat_vs_bw`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Heat flow with inset (a) + cumulative heat with group brackets (b) (`calorimetry_pair_inset_groups`) | works | works | works | works | n/a | n/a | n/a | works |

## Particle size, porosity & surface

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Particle size: differential + cumulative (log x) (`psd_diff_cum_2x2`) | works | works | works | n/a | n/a | n/a | n/a | works |
| d10 / d50 / d90 grouped bars (log y) (`psd_dvalues_bar`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| RRSB (Rosin–Rammler) linearised plot (`rrsb_plot`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| MIP: cumulative + log-differential intrusion (`mip_pore`) | works | works | works | n/a | n/a | n/a | n/a | works |
| N2 sorption isotherm (adsorption / desorption) (`bet_isotherm`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Particle size, two groups: differential + cumulative with d-value tables (2 × 2) (`psd_groups_2x2`) | works | works | works | n/a | n/a | n/a | n/a | works |

## Spectroscopy (FTIR / Raman / NMR)

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| FTIR stacked spectra with band lines (`ftir_stacked_bands`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Raman stacked spectra (`raman_stacked`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Deconvolution plot (e.g. 29Si MAS NMR, XPS, DTG) (`nmr_29si_deconv`) | works | works | works | n/a | n/a | n/a | n/a | works |

## Thermodynamic modelling

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Phase evolution vs temperature (Scheil / equilibrium), multi-panel (`phase_assemblage_vs_T_panels`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Stacked-area phase assemblage (GEMS-style) (`phase_assemblage_stacked_area`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Grouped hatched bars + measured markers (`grouped_hatched_bars_markers`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Liquid fraction vs temperature (`liquid_fraction_vs_T`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Cement & concrete engineering

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Compressive strength by age (grouped bars ± SD) (`strength_vs_age_bars`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Strength development (log age) (`strength_vs_age_lines_log`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Relative strength / activity index with threshold line (`strength_activity_index`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Setting time as floating bars (initial → final) (`setting_time_bar`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Workability (flow / slump) bars (`flow_slump_bar`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Shrinkage / expansion vs time (± band) (`shrinkage_vs_time`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Stress–strain curves (`stress_strain`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Strength vs w/c with Abrams-type fit (`abrams_wc_strength`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Carbonation depth vs √t with k coefficient (`carbonation_depth_sqrt_t`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Chloride profile with Fick's 2nd-law fit (`chloride_profile`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Single-quantity bars with SD and 'not detected' marking (`free_lime_bar`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |

## Microstructure & SEM-EDS

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| SEM-EDS atomic ratio plot (Al/Ca vs Si/Ca) (`eds_atomic_ratio`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| SEM / optical image panel grid with scale bars (`sem_panel_layout`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Point analyses in a ternary diagram with density shading (`eds_ternary_cloud`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Sustainability & CO2

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| CO2 per tonne clinker (stacked by source) (`co2_emissions_stacked`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Waterfall chart (step-wise reduction) (`waterfall_co2`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Pareto front (trade-off of two objectives, third as colour) (`pareto_front`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Sankey diagram (mass / energy flows) (`sankey_mass_energy`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Tornado diagram (sensitivity) (`sensitivity_tornado`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Intensity against performance (eco-efficiency) (`eco_efficiency`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |

## General scientific & statistics

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Scatter + linear fit with 95 % confidence band (`scatter_linear_fit`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Correlation matrix heatmap (`correlation_heatmap`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Box plot with individual points (`box_strip`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Double-Y graph (two quantities, one x) (`dual_y_axis`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Broken y axis (one dominant peak) (`broken_axis`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Contour response surface (two factors) (`contour_response_surface`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Violin + box + points (`violin`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Raincloud plot (half violin + box + rain) (`raincloud`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Ridgeline (joy) plot (`ridgeline`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Histogram + normal fit + KDE (`hist_kde`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Normal Q–Q plot with reference line (`qq`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Regression with 95 % confidence and prediction bands (`regression_bands`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Residual diagnostics (4 panels) (`residuals_4`) | works | works | works | n/a | n/a | n/a | n/a | works |
| PCA biplot (scores + loadings) with scree inset (`pca_biplot`) | works | works | n/a | works | n/a | n/a | n/a | works |
| Bland–Altman agreement plot (`bland_altman`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Flow diagram of a procedure (numbered stages, boxes and arrows) (`process_flow_steps`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |

## Basic 2D & layout

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Line with shaded SD / CI band (`error_band`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Colour-mapped line series (colour = parameter) (`colormap_line_series`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Bubble chart with colour map (4 variables) (`bubble_colormap`) | works | n/a | n/a | n/a | n/a | n/a | n/a | works |
| Lollipop / dumbbell chart (`lollipop`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Bars + line on a second y axis (`bar_line_combo`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Line plot (`scientific_line`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Physics & signal

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Arrhenius plot (ln k vs 1000/T) (`arrhenius_plot`) | works | works | n/a | works | n/a | n/a | n/a | works |
| Signal + amplitude spectrum (FFT) (`fft_spectrum`) | works | works | works | n/a | n/a | n/a | n/a | works |

## Rheology & mechanics

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Rheology flow curve with Herschel–Bulkley fit and viscosity (`rheo_flow_curve`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Amplitude sweep (G′, G″) with LVE limit and crossover (`rheo_amp_sweep`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Electrochemistry & energy

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| EIS Nyquist plot (equal axes) with frequency labels (`eis_nyquist`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Cyclic voltammograms at several scan rates (`cv_voltammogram`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Ragone plot (energy vs power, log-log) (`ragone_plot`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Life science & medicine

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Dose–response with 4-parameter logistic fit (EC50) (`dose_response_4pl`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Kaplan–Meier survival / time-to-failure curves (`kaplan_meier`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| ROC curve with AUC (`roc_curve`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Analytical chemistry

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Calibration curve with LOD/LOQ and residual panel (`calibration_lod`) | works | works | works | n/a | n/a | n/a | n/a | works |
| Chromatogram with integrated, labelled peaks (`chromatogram`) | works | works | n/a | n/a | n/a | n/a | n/a | works |

## Environment & geoscience

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| Time series with moving average and min–max band (`time_series_band`) | works | works | n/a | n/a | n/a | n/a | n/a | works |
| Depth profiles (depth downward, shared y) (`depth_profile`) | works | works | works | n/a | n/a | n/a | n/a | works |

## Workbook graph types

| Graph | draws | markers | one panel only | zoom inset | difference row | Bragg rows | background | Origin commands |
|---|---|---|---|---|---|---|---|---|
| HYDRATION_DEGREE (`C01`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| ATOMIC_RATIOS (`C02`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| XRD_STACK (`G01`) | works | works | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| XRD_PEAKS_INSET (`G02`) | works | works | n/a | works | n/a (own layout) | n/a (own layout) | n/a | works |
| RIETVELD_FIT (`G03`) | works | works | n/a | works | n/a (own layout) | n/a (own layout) | n/a | works |
| NMR_STACK (`G04`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| NMR_DECONV (`G05`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| NMR_ANNOTATED (`G06`) | works | works | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| TG_DTG (`G07`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| DTG_COMPARE (`G08`) | works | works | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| XRD_DTG_PAIR (`G09`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| CALORIMETRY_PAIR (`G10`) | works | works | works | works | n/a (own layout) | n/a (own layout) | n/a | works |
| DUAL_Y_LOG (`G11`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| PHASE_EVOLUTION (`G12`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| PANEL_GRID_TIME (`G13`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| METHOD_COMPARISON (`G14`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| MASS_BALANCE (`G15`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| VS_RATIO (`G16`) | works | works | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| SCATTER_TREND (`G17`) | works | works | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| GROUPED_BAR_ERR (`G18`) | works | n/a | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| BAR_LINE_COMBO (`G19`) | works | works | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| PSD_CUMULATIVE (`G20`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| STACKED_AREA (`G21`) | works | n/a | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| TERNARY_POINTS (`G22`) | works | works | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| TERNARY_CONTOUR (`G23`) | works | works | works | n/a | n/a (own layout) | n/a (own layout) | n/a | works |
| REFINEMENT_INDICES (`G24`) | works | works | n/a | n/a | n/a (own layout) | n/a (own layout) | n/a | works |

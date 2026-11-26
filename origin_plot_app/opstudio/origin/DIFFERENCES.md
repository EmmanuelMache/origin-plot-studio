# What Origin gets differently, per template

Written by `tools/build_origin_scripts.py`. An empty cell means: the same graph.

| Template | Difference in Origin |
|---|---|
| `xrd_single_labeled` |  |
| `xrd_stacked_offset` |  |
| `xrd_stack_with_zoom` |  |
| `xrd_multi_panel_shared_x` |  |
| `rietveld_fit_diff_ticks` |  |
| `rietveld_grid_2x3` |  |
| `xrd_waterfall_3d` |  |
| `xrd_heatmap_contour` | a colour map is sent as a picture of the app's figure (use Plot > Contour > Colour Fill in Origin on the worksheet that is sent)<br>fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `xrd_peak_shift` |  |
| `williamson_hall` |  |
| `lattice_param_vs_x` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `qpa_stacked_bar_100` | stacked or floating bars are sent as columns of their top values over a column of their base values (set Plot Details > Stack in Origin for a stacked look) |
| `qpa_grouped_bar` |  |
| `phase_vs_dosage_lines` |  |
| `parity_plot` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `donut_composition` |  |
| `xrf_oxide_bar` |  |
| `raw_meal_moduli` |  |
| `ternary_cas` |  |
| `radar_properties` | a polar panel is sent as a picture of the app's figure (Origin's own polar graph type is named in the template's Origin hint)<br>this graph type has no equal built here: its picture is placed on the Origin page |
| `tga_dtg_single` |  |
| `tga_dtg_zones_multi` |  |
| `tga_multi_sample_tg` |  |
| `tga_stacked_panels` |  |
| `tga_massloss_stacked_bar` | stacked or floating bars are sent as columns of their top values over a column of their base values (set Plot Details > Stack in Origin for a stacked look) |
| `ch_cc_content_bar` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `bound_water_vs_age` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `dsc_heatflow` |  |
| `tg_ms` |  |
| `tangent_method_demo` |  |
| `calorimetry_heatflow_inset` |  |
| `calorimetry_cumulative` |  |
| `calorimetry_two_panel` |  |
| `normalised_heat_bar_regimes` | bars with one colour per bar are sent in the colour of the first bar (Plot Details > Pattern > Fill > Increment) |
| `heatflow_vs_cumheat` |  |
| `psd_diff_cum_2x2` |  |
| `psd_dvalues_bar` |  |
| `rrsb_plot` |  |
| `mip_pore` |  |
| `bet_isotherm` |  |
| `ftir_stacked_bands` |  |
| `raman_stacked` |  |
| `nmr_29si_deconv` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `phase_assemblage_vs_T_panels` |  |
| `phase_assemblage_stacked_area` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `grouped_hatched_bars_markers` | hatched columns: where Origin shows them plain, set the pattern in Plot Details > Pattern > Fill |
| `liquid_fraction_vs_T` |  |
| `strength_vs_age_bars` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `strength_vs_age_lines_log` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `strength_activity_index` |  |
| `setting_time_bar` | horizontal bars are sent as columns over the category positions (turn the graph in Origin with Graph > Exchange X-Y Axes)<br>stacked or floating bars are sent as columns of their top values over a column of their base values (set Plot Details > Stack in Origin for a stacked look)<br>bars with one colour per bar are sent in the colour of the first bar (Plot Details > Pattern > Fill > Increment) |
| `flow_slump_bar` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `shrinkage_vs_time` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `stress_strain` |  |
| `abrams_wc_strength` |  |
| `carbonation_depth_sqrt_t` |  |
| `chloride_profile` |  |
| `free_lime_bar` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `eds_atomic_ratio` |  |
| `sem_panel_layout` | an image panel is sent as a picture (Origin: Insert > Image From File) |
| `co2_emissions_stacked` | stacked or floating bars are sent as columns of their top values over a column of their base values (set Plot Details > Stack in Origin for a stacked look) |
| `waterfall_co2` | stacked or floating bars are sent as columns of their top values over a column of their base values (set Plot Details > Stack in Origin for a stacked look) |
| `scatter_linear_fit` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `correlation_heatmap` | an image panel is sent as a picture (Origin: Insert > Image From File)<br>fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar)<br>a colour map is sent as a picture of the app's figure (use Plot > Contour > Colour Fill in Origin on the worksheet that is sent) |
| `box_strip` |  |
| `dual_y_axis` |  |
| `broken_axis` |  |
| `contour_response_surface` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar)<br>a colour map is sent as a picture of the app's figure (use Plot > Contour > Colour Fill in Origin on the worksheet that is sent) |
| `error_band` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `colormap_line_series` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar)<br>a colour map is sent as a picture of the app's figure (use Plot > Contour > Colour Fill in Origin on the worksheet that is sent) |
| `bubble_colormap` | points coloured by a value are sent in one colour (map the colour in Origin: Plot Details > Symbol > Colour > Map)<br>fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar)<br>a colour map is sent as a picture of the app's figure (use Plot > Contour > Colour Fill in Origin on the worksheet that is sent) |
| `lollipop` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `bar_line_combo` |  |
| `xrd_dspacing_top` | a second axis with its own scale (for example d-spacing on top) is not sent: add it in Origin (Axis dialog > Show the top axis, with a formula) |
| `violin` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `raincloud` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `ridgeline` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `hist_kde` |  |
| `qq` |  |
| `regression_bands` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `residuals_4` |  |
| `pca_biplot` |  |
| `bland_altman` |  |
| `conversion_vs_T` |  |
| `kissinger_plot` |  |
| `ea_vs_alpha` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `dta_raw_meal` |  |
| `arrhenius_plot` | a second axis with its own scale (for example d-spacing on top) is not sent: add it in Origin (Axis dialog > Show the top axis, with a formula) |
| `rheo_flow_curve` |  |
| `rheo_amp_sweep` |  |
| `eis_nyquist` |  |
| `cv_voltammogram` |  |
| `ragone_plot` |  |
| `dose_response_4pl` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `kaplan_meier` |  |
| `roc_curve` |  |
| `calibration_lod` |  |
| `chromatogram` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `fft_spectrum` |  |
| `time_series_band` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `depth_profile` |  |
| `pareto_front` | points coloured by a value are sent in one colour (map the colour in Origin: Plot Details > Symbol > Colour > Map)<br>fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar)<br>a colour map is sent as a picture of the app's figure (use Plot > Contour > Colour Fill in Origin on the worksheet that is sent) |
| `sankey_mass_energy` |  |
| `sensitivity_tornado` | horizontal bars are sent as columns over the category positions (turn the graph in Origin with Graph > Exchange X-Y Axes) |
| `scientific_line` |  |
| `ofw_kas_plot` |  |
| `friedman_plot` |  |
| `xrd_ref_ticks` |  |
| `xrd_peak_area_vs_t` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `calorimetry_log_time` |  |
| `sulfate_balance` |  |
| `hydration_degree` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `strength_vs_cumheat` |  |
| `r3_heat_vs_bw` |  |
| `qpa_vs_age_area` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `bogue_vs_qpa` | a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot) |
| `free_lime_vs_T` | fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar) |
| `eds_ternary_cloud` |  |
| `eco_efficiency` |  |
| `psd_groups_2x2` |  |
| `calorimetry_pair_inset_groups` |  |
| `process_flow_steps` |  |

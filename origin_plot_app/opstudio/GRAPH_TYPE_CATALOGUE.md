# Graph-type catalogue – all scientific graph templates (general + domain packs)

**Where this comes from.** Sections A–R come from the research report "Origin Plot Studio: Graph Template
Catalogue and Gap Analysis" (24 Nov 2026). It surveyed OriginLab's graph types and Graph Gallery, general chart
taxonomies, materials characterisation, thermal analysis, cement/concrete science, statistics and journal
figure rules. Sections S–X add general-science domains that the report did not cover (electrochemistry, life
science, analytical chemistry, physics/signal, environment/geoscience, chemical kinetics). Those sections come
from general practice and are marked *(added)*.

**The app is a general scientific graphing tool.** Cement/clinker is one domain pack among many. Every row
becomes one template JSON (`opstudio.template/1`). `catalogue_all_graph_types.json/.csv` holds the same
rows in machine-readable form. Each row has a status: `implemented` (preview exists in `previews/`) or a gap
tier (`tier1`, `tier2`, `tier3`).

**How to read the tables**
* **Roles:** X, Y, Yerr, Xerr, G = group/sample, L = label, Z = matrix/XYZ, A/B/C = ternary fractions,
  T = temperature, t = time, S = size. "n×Y" means several Y columns sharing one X.
* **Origin path:** "P>" means the Plot menu. Template file names are given only where OriginLab documents them.
* **Rel:** relevance for materials/cement work (H/M/L). In sections S–X, Gen marks a general-science type.
* ✔ means already in the library, with the existing id in brackets.

**Global variant switches (implement once, apply to every template – not separate templates):**
* axes: linear / log / reversed / axis break / secondary top axis
* inset (zoom of a region)
* error style: bars, caps or band
* fill and hatch
* markers on or off
* single or multi-panel
* landscape aspect
* colour-blind palette
* normalise / offset

## A. Basic 2D (line, scatter, error)
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| line_basic | Line; spline, step, dashed per group | X, n×Y | P>Basic 2D: Line | smoothing | H |
| scatter_basic | Scatter; open/filled symbols | X, Y, G | P>Basic 2D: Scatter | — | H |
| line_symbol | Line + symbol; sparse markers on dense data | X, n×Y | P>Basic 2D: Line & Symbol | — | H |
| scatter_yerr | Y error bars; caps, ± or one-sided | X, Y, Yerr | P>Basic 2D: Y Error | mean ± SD | H |
| scatter_xyerr | XY error bars | X, Y, Xerr, Yerr | P>Basic 2D: XY Error | — | M |
| error_band | Line with shaded SD/CI band, transparency | X, Y, Yerr | P>Basic 2D: Error Band | CI | H |
| scatter_central | Scatter with central (crossing) axes | X, Y | P>Basic 2D: Scatter Central | — | L |
| column_scatter | Column scatter (jittered dots per group) | G, Y | P>Basic 2D: Column Scatter | mean line | M |
| scatter_rug | Scatter + rug marks | X, Y | P>Basic 2D: Scatter + Rug | — | L |
| bubble | Bubble (size = 3rd variable) | X, Y, S | P>Basic 2D: Bubble | — | M |
| colormap_scatter | Colour-mapped scatter (colour = Z) | X, Y, Z | P>Basic 2D: Color Map | — | M |
| bubble_colormap | Bubble + colour map | X, Y, S, Z | P>Basic 2D: Bubble+Color Mapped | — | M |
| colormap_line_series | Colour-mapped line series (colour = parameter, e.g. age or T) | X, n×Y, param | P>Basic 2D: Colormapped Line Series | — | H |
| stacked_y_offset | Stacked lines by Y offset (auto/constant/individual; fill to next) | X, n×Y | P>Basic 2D: Stacked Lines by Y Offsets (OFFSETSTACKY.OTP) | normalise, offset | H ✔ (xrd_stacked_offset) |
| rowwise_series | Row-wise line series | rows | P>Basic 2D: Row-wise Line Series | — | L |
| lollipop | Lollipop (stem + dot); dumbbell variant | G, Y | P>Basic 2D: Lollipop | — | M |
| drop_line | Drop-line plot (vertical lines to axis, e.g. peak positions) | X, Y | Plot Details > Drop Lines | — | M |
| anomaly_line | Anomaly line/area (colour above/below a reference) | X, Y, ref | gallery feature | — | L |
| density_dots | Density dots / binned scatter (large n) | X, Y | P>Basic 2D: Density Dots | 2D binning | L |
| fill_between | Fill area between two curves (obs–calc, envelope) | X, Y1, Y2 | P>Bar,Pie,Area: Fill Area | — | H |
| function_plot | 2D function / parametric overlay (model curve) | f(x) | File>New>Function Plot | — | M |
| logx_logy | Log-log and semi-log variants | X, Y | Axis scale; Log-Log template | power-law fit | H |
| scatter_linear_fit | Scatter + linear fit, equation and R² | X, Y | Analysis>Fitting | LSQ | H ✔ (scatter_linear_fit) |

## B. Column, bar, pie, area
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| column | Column ± error | G, Y, Yerr | P>Bar,Pie,Area: Column | mean ± SD | H ✔ (flow_slump_bar) |
| column_label | Column + value labels | G, Y | …: Column + Label | — | H ✔ (normalised_heat_bar_regimes) |
| bar_h | Horizontal bar (long category names) | G, Y | …: Bar | — | M |
| grouped_column | Grouped column; significance brackets/letters | G1, G2, Y, Yerr | grouped column (index data) | ANOVA/Tukey letters | H ✔ (qpa_grouped_bar) |
| stacked_column | Stacked column (absolute) | G, n×Y | …: Stacked Column | sum | H ✔ (tga_massloss_stacked_bar) |
| stacked_bar | Stacked bar (horizontal) | G, n×Y | …: Stacked Bar | — | M |
| stack100_column | 100 % stacked column; connected-line variant | G, n×Y | …: 100% Stacked Column | normalise | H ✔ (qpa_stacked_bar_100) |
| stack100_bar | 100 % stacked bar | G, n×Y | …: 100% Stacked Bar | — | M |
| grouped_stacked | Grouped and stacked column | G1, G2, n×Y | subgroup + Stack tab | — | H |
| floating_column | Floating column (start–end, ranges) | G, Ylow, Yhigh | …: Floating Column | — | H ✔ (setting_time_bar) |
| floating_bar | Floating bar (Gantt-like ranges) | G, Xlow, Xhigh | …: Floating Bar | — | H |
| bridge_waterfall | Bridge / waterfall chart | step, ΔY | Bridge Plot | cumulative | H ✔ (waterfall_co2) |
| bar_hatched | Hatched / patterned bars (greyscale-safe) | G, Y | Pattern tab | — | H ✔ (grouped_hatched_bars_markers) |
| bar_line_combo | Bars + line or markers on 2nd Y | G, Y1, Y2 | Double-Y Column-Line Symbol | — | H |
| bar_table | Bars with stats table under the axis | G, Y | gallery feature | — | L |
| kite | Kite diagram | X, Y | …: Kite Diagram | — | L |
| spiral_bar | Spiral bar chart | G, Y | gallery | — | L |
| pie | Pie 2D/3D, exploded | L, Y | …: 2D/3D Color Pie | % | L |
| donut | Doughnut; with total | L, Y | …: Doughnut | % | M ✔ (donut_composition) |
| pie_of_pie | Pie of pie / bar of pie | L, Y | …: Pie of Pie / Bar of Pie | — | L |
| area | Area (fill to axis) | X, Y | …: Area | integral | M |
| stacked_area | Stacked area (cumulative; 100 % variant) | X, n×Y | …: Stacked Area | cumulative | H ✔ (phase_assemblage_stacked_area) |
| pyramid | Population / back-to-back pyramid | G, Yleft, Yright | gallery | — | L |

## C. Multi-panel and multi-axis
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| double_y | Double-Y (1-layer or 2-layer) | X, Y1, Y2 | P>Multi-Panel/Axis: Double-Y | — | H ✔ (dual_y_axis) |
| double_y_column | Double-Y column | G, Y1, Y2 | …: Double-Y Column | — | M |
| multi_y | 3–4 Y axes (offset spines) | X, Y1..Y4 | …: Multiple Y Axes | — | M |
| panel_v2 | Vertical 2-panel, shared X | X, Y1, Y2 | …: Vertical 2 Panel | — | H ✔ (xrd_multi_panel_shared_x) |
| panel_h2 | Horizontal 2-panel, shared Y | X, Y | …: Horizontal 2 Panel | — | H ✔ (calorimetry_two_panel) |
| panel_4 | 2×2 panel | 4 sets | …: 4 Panel | — | H ✔ (psd_diff_cum_2x2) |
| panel_9 | 3×3 panel | 9 sets | …: 9 Panel | — | M |
| stack_panels | Stack (n panels, zero gap, own Y) | X, n×Y | …: Stack | — | H ✔ (tga_stacked_panels) |
| trellis | Trellis / small multiples by factor | X, Y, G1, G2 | Trellis Plot | — | M ✔ (rietveld_grid_2x3) |
| inset | Inset (zoom or secondary data) | X, Y | Zoomed Inset / Merge | — | H ✔ (calorimetry_heatflow_inset) |
| zoom_plot | Overview + linked magnified panel | X, Y | Specialized: Zoom | — | M ✔ (xrd_stack_with_zoom) |
| broken_axis | Axis break (X or Y), several breaks | X, Y | Axis > Breaks | — | H ✔ (broken_axis) |
| top_x_secondary | Secondary top X (d vs 2θ, °C vs K, days vs √t) | X, Y | Axis > Top | transform | H |
| merge_graphs | Merged arbitrary layouts on one page | any | Graph>Merge Graph Windows | — | H |

## D. Statistical
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| box | Box (1.5 IQR, min–max, percentiles; notched) | G, Y | P>Statistical: Box | quartiles | H ✔ (box_strip) |
| box_grouped | Grouped box | G1, G2, Y | P>Statistical: Grouped Box | — | M |
| violin | Violin; with box, points, quartiles, sticks | G, Y | P>Statistical: Violin (Violin*.otpu) | KDE | M |
| violin_split | Split / half violin | G, Y, G2 | ViolinSplit.otpu, HalfViolin.otpu | KDE | M |
| raincloud | Raincloud (half violin + dots + box) | G, Y | File Exchange template fid 773 | KDE | M |
| histogram | Histogram (count/%, bin rules) | Y | P>Statistical: Histogram | binning | M |
| hist_kde | Histogram + normal/KDE curve | Y | P>Statistical: Histogram + Probabilities | fit dist. | M |
| hist_stacked | Stacked / multi-panel histograms | Y, G | P>Statistical: Stacked Histograms | — | L |
| ridgeline | Ridgeline / joy plot | G, Y | P>Statistical: Ridgeline | KDE | M |
| marginal | Marginal plot (scatter/contour + hist/box/violin) | X, Y, G | P>Statistical: Marginal (Marginal_Scatter.OTPU) | — | M |
| marginal_hist | Marginal histograms | X, Y | MARGINHIST.OTP | — | L |
| marginal_box | Marginal box charts | X, Y | P>Statistical: Marginal Box Charts | — | L |
| qq | Q–Q plot | Y | P>Statistical: Q-Q | quantiles | M |
| prob_plot | Probability plot (normal, Weibull) | Y | P>Statistical: Probability | Weibull modulus | M |
| cdf | Empirical / theoretical CDF | Y | P>Statistical: CDF | ECDF | M |
| dot_plot | Dot / means plot | G, Y | P>Statistical: Dot | — | L |
| interval_plot | Interval plot (mean ± CI) | G, Y | grouped interval | CI | M |
| scatter_matrix | Scatter matrix (pair plot) | n×Y | P>Statistical: Scatter Matrix | r | M |
| kde_2d | 2D kernel density | X, Y | P>Statistical: 2D Kernel Density | KDE | L |
| hexbin | Hexbin | X, Y | Hexbin Plot | — | L |
| bland_altman | Bland–Altman (difference vs mean, ±1.96 SD) | M1, M2 | Bland-Altman Plot | bias, LoA | M |
| before_after | Paired comparison | G, Y1, Y2 | P>Statistical: Paired Comparison | paired t | L |
| forest | Forest plot (effect ± CI) | L, est, lo, hi | Forest Plot | — | L |
| interaction | Interaction plot (DoE) | factors, Y | P>Statistical: Interaction (2025b) | means | M |
| main_effects | Main-effects plot (DoE) | factors, Y | P>Statistical: Main Effects (2025b) | means | M |
| pareto_chart | Pareto chart (bars + cumulative % line) | L, Y | Quality: Pareto | cumulative % | M |
| control_chart | Control chart (X̄-R) | t, Y | Quality: Control charts | limits | M |
| run_chart | Run chart | t, Y | P>Statistical: Run Chart (2025b) | median | L |
| symmetry | Symmetry plot | Y | P>Statistical: Symmetry (2025b) | — | L |
| regression_bands | Regression with 95 % confidence and prediction bands | X, Y | Fit report option | CI/PI | H |
| residuals_4 | Residual diagnostics (vs fitted, vs X, histogram, Q–Q) | fit | Fit report | residuals | H |
| parity | Parity (predicted vs measured, 1:1 ± %) | Ymeas, Ypred | scatter + line | RMSE, R² | H ✔ (parity_plot) |
| corr_heatmap | Correlation matrix heatmap (annotated r) | n×Y | Correlation Plot app | Pearson/Spearman | H ✔ (correlation_heatmap) |
| pca_biplot | PCA scores + loadings biplot; scree | n×Y, G | PCA tool | PCA | M |
| dendrogram | Hierarchical-cluster dendrogram | n×Y | Cluster analysis | HCA | L |
| heatmap_dendro | Heatmap with dendrogram (2025b) | matrix | P>Contour: Heatmap with Dendrogram | HCA | L |
| andrews | Andrews plot | n×Y | gallery | — | L |
| venn_upset | Venn / UpSet | sets | Venn app; P>Statistical: UpSet | — | L |
| taylor | Taylor diagram (model skill) | obs, models | Taylor Diagram app | SD, r, RMSE | L |

## E. Contour, heatmap, image
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| contour_fill | Contour colour fill (XYZ, matrix) | X, Y, Z | P>Contour: Contour - Color Fill | gridding | H ✔ (contour_response_surface) |
| contour_lines | B/W contour lines + labels | X, Y, Z | P>Contour: B/W Lines + Labels | — | M |
| contour_gray | Grey-scale map | X, Y, Z | P>Contour: Gray Scale Map | — | L |
| contour_catz | Contour with categorical Z (phase-field map) | X, Y, Zcat | P>Contour: Contour - Categorical Z | — | H |
| heatmap | Heatmap | X, Y, Z | P>Contour: Heatmap | — | M ✔ (xrd_heatmap_contour) |
| heatmap_labels | Heatmap with cell labels | X, Y, Z | P>Contour: Heatmap with Labels | — | M |
| heatmap_split | Split heatmap (two values per cell) | X, Y, Z1, Z2 | P>Contour: Split Heatmap | — | L |
| heatmap_grouping | Heatmap with grouping (2025b) | matrix, G | P>Contour | — | L |
| contour_profiles | Contour + linked X/Y profiles | Z | P>Contour: Contour Profiles | profiles | H |
| image_plot | Image plot (micrograph/map + colour bar) | image | Image Plot | — | M |
| image_profiles | Line profiles across images | matrix | P>Contour: Image Profiles | — | M |
| polar_contour | Polar contour | θ, r, Z | P>Contour: Polar Contour | — | L |
| contour_vector | Contour + gradient vectors / streamlines | Z | Specialized | gradient | L |
| polyline_profile | Polyline profile across a map | Z | Profile tools | — | L |

## F. Specialized: polar, ternary, vector and others
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| ternary | Ternary scatter/line | A, B, C | P>Specialized: Ternary | normalise | H ✔ (ternary_cas) |
| ternary_contour | Ternary contour (property over composition) | A, B, C, Z | P>Contour: Ternary Contour | gridding | H |
| ternary_vector | Ternary vector (composition shifts) | A, B, C, ΔA, ΔB | P>Specialized: Ternary Vector | — | M |
| right_ternary | Right-triangle ternary | A, B, C | P>Specialized: Right-Triangle Ternary | — | L |
| ternary_kde | Ternary kernel density (point clouds) | A, B, C | Polar/Ternary KDE | KDE | M |
| tetrahedral | Tetrahedral (quaternary) composition plot | A, B, C, D | 3D: Tetrahedral | — | M |
| ternary_3d | 3D ternary scatter / surface | A, B, C, Z | 3D Ternary | — | L |
| piper | Piper / trilinear (water chemistry) | ions | P>Specialized: Piper | meq % | M |
| durov | Durov diagram | ions | P>Specialized: Durov | — | L |
| stiff | Stiff diagram | ions | P>Specialized: Stiff | — | L |
| polar | Polar plot | θ, r | P>Specialized: Polar | — | L |
| radar | Radar / spider | criteria, G | P>Specialized: Radar | normalise | H ✔ (radar_properties) |
| radial_bar | Radial bar / Nightingale rose | G, Y | P>Specialized: Radial Bar | — | L |
| stacked_radial | Stacked radial | G, n×Y | P>Specialized: Stacked Radial | — | L |
| compass | Compass plot | θ, mag | P>Specialized: Compass | — | L |
| windrose | Wind rose | dir, speed | P>Specialized: Wind Rose | binning | L |
| smith | Smith chart | Re, Im | P>Specialized: Smith Chart (SMITHCHT.OTP) | normalise | L |
| vector_xyam | Vector X, Y, angle, magnitude | X, Y, A, M | P>Specialized: Vector XYAM | — | L |
| vector_xyxy | Vector X, Y, X, Y (displacement fields) | X1, Y1, X2, Y2 | P>Specialized: Vector XYXY | — | M |
| streamline | Streamline | U, V | P>Specialized: Streamline | — | L |
| polar_vector | Polar vector / quiver (2025b) | θ, r, vec | Specialized | — | L |
| bullet | Bullet chart (value vs target bands) | Y, target | P>Specialized: Bullet Chart | — | M |
| wafer_map | Wafer map | X, Y, Z | Specialized | — | L |
| stock | Stock (OHLC) | t, OHLC | Specialized | — | L |
| soil_class | Soil / rock classification diagrams | A, B, C | extended templates | — | L |
| chromaticity | CIE chromaticity diagram | x, y | Chromaticity app | — | L |
| volcano | Volcano plot | logFC, p | Volcano app | — | L |
| manhattan | Manhattan plot | pos, p | gallery | — | L |
| poincare | Poincaré plot | Yn, Yn+1 | gallery | — | L |

## G. Categorical, flow and hierarchy
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| sankey | Sankey (mass/energy flow) | source, target, value | P>Categorical: Sankey (Sankey.otpu) | balances | H |
| alluvial | Alluvial | ≥2 categorical | P>Categorical: Alluvial | — | M |
| parallel_coords | Parallel coordinates | n×Y, G | P>Categorical: Parallel Plot | normalise | M |
| parallel_sets | Parallel sets | cats | P>Categorical: Parallel Sets | — | L |
| chord | Chord diagram | matrix | P>Categorical: Chord | — | L |
| network | Network / correlation network | nodes, edges | P>Categorical: Network | r threshold | L |
| ribbon | Ribbon chart (rank changes) | t, G, Y | gallery | — | L |
| sunburst | Sunburst (hierarchical composition) | levels, Y | P>Categorical: Sunburst | — | M |
| treemap | Treemap (2025b) | levels, Y | P>Categorical: Treemap | — | L |
| circle_packing | Circular packing | levels, Y | P>Categorical | — | L |
| edge_bundling | Hierarchical edge bundling | hierarchy | P>Categorical | — | L |
| sankey_map | Sankey on a map | X, Y, L, src, tgt, w | P>Categorical: Sankey Map | — | L |
| bar_pie_map | Bar / pie / tile-grid map | geo, Y | Maps | — | L |
| macc | Marginal abatement cost curve (variable-width bars) | measure, cost, Δ | extended template | — | H |

## H. 3D
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| waterfall_2d | 2D waterfall (X and Y offsets) | X, n×Y | P>3D/2D Waterfall | — | H ✔ (xrd_waterfall_3d) |
| waterfall_3d | 3D waterfall; colour-mapped | X, n×Y, Z | P>3D: 3D Waterfall | — | H |
| surface_cmap | 3D colour-map surface (+ projection) | X, Y, Z | P>3D: Colormap Surface | — | M |
| surface_wire | Wire frame / constant-X/Y with base | Z | P>3D | — | L |
| surface_fit | Fitted response surface + points | X1, X2, Y | Surface fit | polynomial | M |
| scatter_3d | 3D scatter / trajectory (+ drop lines) | X, Y, Z | P>3D: Scatter | — | L |
| bar_3d | 3D bars / stacked | X, Y, Z | P>3D: Bars | — | L |
| ribbons_walls | 3D ribbons / walls | X, n×Y | P>3D: Ribbons/Walls | — | L |
| wall_profile | 3D wall profile | X, n×Y | gallery | — | L |
| hist_3d | 3D stacked histograms | Y, G | gallery | — | L |
| isosurface | Isosurface (tomography volume) | volume | Isosurface | — | L |
| function_3d | 3D function / parametric surface | f(x, y) | File>New>Function Plot | — | L |

## I. XRD and diffraction
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| xrd_single_labeled | Single pattern + phase markers | 2θ, I | Line + text | peak find | H ✔ (xrd_single_labeled) |
| xrd_stacked_offset | Offset stack; labels at right | 2θ, n×I | OFFSETSTACKY.OTP | normalise | H ✔ (xrd_stacked_offset) |
| xrd_stack_with_zoom | Stack + magnified window | 2θ, n×I | Zoom/inset | — | H ✔ (xrd_stack_with_zoom) |
| xrd_multi_panel_shared_x | Panels with own Y | 2θ, n×I | Stack | — | H ✔ (xrd_multi_panel_shared_x) |
| xrd_ref_ticks | Pattern(s) + reference stick rows per phase | 2θ, I, phase, 2θref | Drop-line / tick layer | d→2θ | H |
| xrd_dspacing_top | 2θ bottom, d-spacing or Q top axis | 2θ, I | Top axis transform | λ-dependent | M |
| rietveld_fit_diff_ticks | Obs/calc/diff/Bragg ticks, Rwp | 2θ, Yobs, Ycalc, Ydiff, ticks | Line+scatter + stack | — | H ✔ (rietveld_fit_diff_ticks) |
| rietveld_grid_2x3 | Grid of refinements | as above | 2×3 panels | — | H ✔ (rietveld_grid_2x3) |
| rietveld_log_sqrt | Rietveld on √I or log I | as above | Axis scale | — | M |
| xrd_waterfall_3d | Waterfall of in-situ series | 2θ, n×I, t | 3D Waterfall | — | H ✔ (xrd_waterfall_3d) |
| xrd_heatmap_contour | In-situ contour map | 2θ, t, I | Contour | — | H ✔ (xrd_heatmap_contour) |
| xrd_peak_area_vs_t | Integrated peak area / phase vs t or T | t, A, G | Line+symbol | peak integration | H |
| xrd_peak_shift | Peak position vs composition/T | x, 2θ | Line+symbol | peak fit | H ✔ (xrd_peak_shift) |
| williamson_hall | Size–strain plot | 4 sinθ, βcosθ | scatter + fit | FWHM | M ✔ (williamson_hall) |
| scherrer_bar | Crystallite size bars | G, D | column | Scherrer | L |
| lattice_param_vs_x | a, b, c, V vs composition/T | x, a…V, err | multi-panel | — | M ✔ (lattice_param_vs_x) |
| pole_figure | Pole figure | χ, φ, I | Polar contour | — | L |
| pdf_gr | Pair distribution function G(r) stacked | r, G(r) | stack | — | L |
| amorphous_hump | Pattern with fitted amorphous hump shaded | 2θ, I, Iam | fill area | profile fit | M |

## J. Spectroscopy (FTIR, Raman, NMR, XPS, XRF, UV–Vis)
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| ftir_stacked_bands | Stacked FTIR, reversed axis, band shading | ν, n×A/T | stack + reversed X | baseline | H ✔ (ftir_stacked_bands) |
| ftir_deconv | Band deconvolution (envelope + components + residual) | ν, A | Peak Analyzer | Gauss/Lorentz | M |
| ftir_2nd_derivative | 2nd-derivative spectra stacked | ν, d²A | stack | SG derivative | L |
| ftir_band_ratio | Band position / area ratio vs x | x, ratio | line+symbol | integration | M |
| raman_stacked | Stacked Raman | Δν, n×I | stack | baseline | M ✔ (raman_stacked) |
| raman_map | Raman phase map | X, Y, I | Image plot | MCR/PCA | L |
| nmr_29si_deconv | ²⁹Si Qn deconvolution, reversed ppm | ppm, I | Peak fit | MCL | H ✔ (nmr_29si_deconv) |
| nmr_27al_deconv | ²⁷Al Al(IV)/(V)/(VI) regions + fit | ppm, I | Peak fit | areas | M |
| nmr_qn_bar | Qn distribution stacked bar | G, Qn% | 100% stacked | MCL | M |
| xps_core_fit | XPS core level: background, components, envelope, residual | BE, cps | Peak fit | Shirley/Tougaard | M |
| xps_survey | XPS survey with labelled lines | BE, cps | line + labels | — | L |
| xrf_oxide_bar | Oxide bars (log for minors) | oxide, wt% | column | LOI closure | H ✔ (xrf_oxide_bar) |
| xrf_spectrum | Energy spectrum with element lines | keV, cps | line + drop lines | — | L |
| uvvis_tauc | UV–Vis / Tauc plot | E, (αhν)ⁿ | scatter + fit | band gap | L |

## K. Microscopy and microanalysis
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| sem_panel_layout | Image grid with scale bars, panel letters | images | Image + layout | — | H ✔ (sem_panel_layout) |
| eds_atomic_ratio | Al/Ca vs Si/Ca point cloud | Si/Ca, Al/Ca, G | scatter | ratios | H ✔ (eds_atomic_ratio) |
| eds_ratio_variants | S/Ca vs Al/Ca; Mg/Si vs Al/Si | ratios | scatter | — | H |
| eds_ternary_cloud | EDS points in a ternary, KDE-shaded, phase markers | A, B, C, G | Ternary + KDE | normalisation | H |
| eds_map_grid | Element map grid + BSE + segmented overlay | maps | Image grid | segmentation | H |
| bse_grey_histogram | Grey-level histogram with thresholds | grey, count | histogram | thresholding | M |
| clinker_microscopy_bar | Phase area % / crystal size distribution | G, % | stacked column | — | M |
| linescan | EDS/EPMA line scan across an interface | distance, n×wt% | multi-Y | — | M |

## L. Particle size, surface area and porosity
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| psd_diff_cum_2x2 | Differential + cumulative, log X | d, q3, Q3 | panels | — | H ✔ (psd_diff_cum_2x2) |
| psd_overlay_dual | Differential + cumulative in one log-X double-Y graph | d, q3, Q3 | Double-Y | — | H |
| psd_dvalues_bar | D10/D50/D90 bars | G, D | grouped column | interpolation | H ✔ (psd_dvalues_bar) |
| rrsb_plot | RRSB linearised | ln d, lnln(1/R) | scatter + fit | RRSB | H ✔ (rrsb_plot) |
| bet_isotherm | Adsorption–desorption isotherm | p/p0, V | line+symbol | — | M ✔ (bet_isotherm) |
| bet_linear | BET linear plot | p/p0, BET fn | scatter + fit | SBET | M |
| bjh_psd | BJH/DFT pore-size distribution + cumulative | D, dV/dlogD | Double-Y | BJH | M |
| t_plot | t-plot (micropores) | t, V | scatter + fit | micropore vol. | L |
| mip_pore | MIP cumulative + dV/dlogD | D, V | Double-Y, reversed log X | Washburn | H ✔ (mip_pore) |
| mip_hysteresis | Intrusion–extrusion loop | D, V | line | — | M |
| porosity_bar | Porosity fractions stacked by age | G, % | stacked column | — | M |
| nmr_relaxometry_t2 | ¹H NMR T2 distribution | T2, I | log X | ILT | M |

## M. Rheology, mechanics and other physical tests
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| rheo_flow_curve | Flow curve: stress (+ viscosity on 2nd Y) vs shear rate, up/down ramps, log-log | γ̇, τ, η | Double-Y, log | Bingham / Herschel–Bulkley | H |
| rheo_amp_sweep | Amplitude sweep G′, G″ vs strain, LVE limit, crossover | γ, G′, G″ | log-log | LVE | H |
| rheo_freq_sweep | Frequency sweep G′, G″, complex viscosity | ω, G′, G″ | log-log | — | M |
| rheo_time_sweep | Time sweep / structural build-up | t, G′ | line | slope | M |
| static_yield_bar | Static/dynamic yield stress bars | G, τ | grouped column | — | M |
| stress_strain | Stress–strain, modulus marked | ε, σ | line | E, peak | H ✔ (stress_strain) |
| load_cmod | Load–CMOD / deflection | δ, F | line | fracture energy | M |
| dma_temp | DMA E′, E″, tan δ vs T | T, E′, E″, tanδ | multi-Y | Tg | L |
| eis_nyquist | EIS Nyquist (equal aspect, circuit fit) | Z′, Z″ | scatter + fit | circuit fit | M |
| eis_bode | Bode: impedance modulus and phase vs f | f, Zmod, φ | Double-Y log | — | M |
| dilatometry | ΔL/L0 vs T + derivative | T, ΔL/L0 | Double-Y | derivative | M |
| hot_stage_micro | Hot-stage microscopy: height % vs T, silhouettes, characteristic T | T, h%, images | line + image row | thresholds | H |
| ultrasonic_pv | Ultrasonic pulse velocity vs age | t, v | line | — | M |

## N. Thermal analysis (TG, DTG, DSC, DTA, EGA, kinetics)
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| tga_dtg_single | TG + DTG (right Y, natural sign) | T, m%, dm/dT | Double-Y | derivative | H ✔ (tga_dtg_single) |
| tga_dtg_zones_multi | Multi-sample with shaded zones | T, n×m | Double-Y + fill | zone integration | H ✔ (tga_dtg_zones_multi) |
| tga_multi_sample_tg | TG overlay | T, n×m | line | — | H ✔ (tga_multi_sample_tg) |
| tga_stacked_panels | TG/DTG stacked panels | T, n× | Stack | — | H ✔ (tga_stacked_panels) |
| tga_massloss_stacked_bar | Mass loss per zone | G, Δm | stacked column | — | H ✔ (tga_massloss_stacked_bar) |
| ch_cc_content_bar | Derived contents from TG | G, % | column | stoichiometry | H ✔ (ch_cc_content_bar) |
| tangent_method_demo | Tangent construction | T, m | line | — | M ✔ (tangent_method_demo) |
| bound_water_vs_age | Bound water vs age | t, % | line | — | H ✔ (bound_water_vs_age) |
| dtg_deconv | DTG peak deconvolution | T, DTG | Peak fit | Gauss/asymmetric | M |
| tg_isothermal | Isothermal TG at several T | t, m, T | line | conversion α | H |
| dsc_heatflow | DSC heat flow (exo direction stated) | T, q | line | enthalpy | M ✔ (dsc_heatflow) |
| dsc_multi_rate | DSC/DTA at several heating rates | T, q, β | colour-mapped lines | Tp | H |
| dta_raw_meal | High-T DTA/DSC with event bands (labels confirmed) | T, ΔT, events | line + bands | onset, peak | H |
| tg_ms | TG + evolved gas | T, m, m/z | multi-Y / stack | — | H ✔ (tg_ms) |
| tg_ftir_gram | TG-FTIR Gram–Schmidt + evolved-gas map | T, ν, A | contour/waterfall | — | M |
| conversion_vs_T | α vs T at several β + dα/dT | T, α, β | colour-mapped lines | α | H |
| kissinger_plot | ln(β/Tp²) vs 1000/Tp, Ea | 1/Tp, ln(β/Tp²) | scatter + fit | Ea, A | H |
| ofw_kas_plot | Isoconversional lines (OFW/KAS) for α = 0.1…0.9 | 1/Tα, f(β), α | multi-fit | Eα | H |
| friedman_plot | ln(dα/dt) vs 1/Tα | as above | multi-fit | Eα | H |
| ea_vs_alpha | Eα vs α (± CI), methods compared | α, Eα, err | line + band | — | H |
| coats_redfern | Coats–Redfern for candidate models | 1/T, ln g | multi-fit | model R² | M |
| master_plot | Master plot vs theoretical models | α, z | lines | reaction model | M |

## O. Calorimetry and hydration
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| calorimetry_heatflow_inset | Heat flow + inset | t, q | line + inset | normalisation | H ✔ (calorimetry_heatflow_inset) |
| calorimetry_cumulative | Cumulative heat | t, Q | line | integration | H ✔ (calorimetry_cumulative) |
| calorimetry_two_panel | Heat flow + cumulative | t, q, Q | 2-panel | — | H ✔ (calorimetry_two_panel) |
| normalised_heat_bar_regimes | Heat bars with regimes | G, Q | column | — | H ✔ (normalised_heat_bar_regimes) |
| heatflow_vs_cumheat | Heat flow vs cumulative heat | Q, q | line | — | H ✔ (heatflow_vs_cumheat) |
| calorimetry_log_time | Heat flow on log time, stages annotated | t, q | log X | max slope | H |
| calorimetry_multi_T | Heat flow at several T + apparent Ea | t, q, T | colour-mapped + inset fit | Ea | M |
| r3_heat_vs_bw | Reactivity test: heat vs bound water | Q, BW, G | scatter + fit | — | H |
| sulfate_balance | Heat-flow overlays vs sulfate dosage | t, q, dosage | colour-mapped | peak timing | H |
| hydration_degree | Degree of reaction vs t (methods compared) | t, α, method | line + band | α = Q/Q∞ | H |
| chem_shrinkage | Chemical shrinkage vs t / vs heat | t, Δv | line | — | M |
| strength_vs_cumheat | Strength vs cumulative heat (or α) | Q, fc, G | scatter + fit | R² | H |

## P. Thermodynamic modelling and phase chemistry
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| phase_assemblage_stacked_area | Stacked phase assemblage vs x | x, n×V | stacked area | from GEMS etc. | H ✔ (phase_assemblage_stacked_area) |
| phase_assemblage_vs_T_panels | Phase content vs T, panels | T, n× | panels | — | H ✔ (phase_assemblage_vs_T_panels) |
| liquid_fraction_vs_T | Liquid fraction vs T | T, %L | line | — | H ✔ (liquid_fraction_vs_T) |
| scheil_vs_equilibrium | Scheil vs equilibrium solid fraction | T, fs, model | line | — | M |
| isopleth_phase_diagram | Isopleth / pseudo-binary with phase-field labels | x, T, fields | lines + text + categorical contour | — | H |
| ternary_phase_diagram | Ternary liquidus: primary fields, isotherms, sample points | A, B, C, isotherms | ternary + lines | — | H (extend ternary_cas) |
| predominance_diagram | Predominance / Ellingham diagram | T, ΔG/pO2 | lines + fills | — | M |
| phase_vs_dosage_lines | Phase content vs dosage | x, n×% | lines | — | H ✔ (phase_vs_dosage_lines) |
| qpa_vs_age_area | Phase evolution vs age | t, n×wt% | stacked area / lines | — | H |
| raw_meal_moduli | Moduli with target bands | G, LSF, SM, AM | column + bands | moduli | H ✔ (raw_meal_moduli) |
| bogue_vs_qpa | Bogue vs Rietveld (parity or bars) | phase, B, R | grouped / parity | Bogue | H |
| free_lime_vs_T | Burnability curve | T, fCaO, mix | line + symbol | — | H |
| free_lime_bar | Single-quantity bars with n.d. | G, % | column | — | H ✔ (free_lime_bar) |
| saturation_index | Saturation indices vs time | t, SI, phase | lines + zero line | — | M |

## Q. Engineering, durability and pore solution
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| strength_vs_age_bars | Strength by age ± SD | age, G, fc | grouped column | — | H ✔ (strength_vs_age_bars) |
| strength_vs_age_lines_log | Strength vs log age | t, fc | line | — | H ✔ (strength_vs_age_lines_log) |
| strength_activity_index | Relative strength with limit line | G, SAI | column + ref | ratio | H ✔ (strength_activity_index) |
| comp_vs_flex | Compressive and flexural, double-Y bars | G, fc, ff | Double-Y column | — | M |
| strength_vs_porosity | Strength vs porosity / gel-space ratio | φ, fc | scatter + fit | power law | M |
| strength_weibull | Strength distribution / Weibull | G, fc | box / prob | Weibull | L |
| abrams_wc_strength | Abrams curve | w/c, fc | scatter + fit | exponential | M ✔ (abrams_wc_strength) |
| setting_time_bar | Setting times (floating column) | G, ti, tf | floating column | — | H ✔ (setting_time_bar) |
| vicat_curve | Penetration vs time | t, depth | line | interpolation | M |
| flow_slump_bar | Flow / slump | G, mm | column | — | H ✔ (flow_slump_bar) |
| flow_retention | Spread loss vs time | t, mm | line | — | M |
| shrinkage_vs_time | Shrinkage vs time | t, ε | line | — | H ✔ (shrinkage_vs_time) |
| mass_loss_shrinkage | Shrinkage vs mass loss | Δm, ε | scatter | — | M |
| asr_expansion | Expansion vs time with limit lines (user-set) | t, % | line + ref | — | M |
| sulfate_expansion | Sulfate expansion vs time | t, % | line | — | M |
| carbonation_depth_sqrt_t | Depth vs √t, k | √t, d | scatter + fit | k | H ✔ (carbonation_depth_sqrt_t) |
| chloride_profile | Profile + erfc fit | x, Cl | scatter + fit | erfc | H ✔ (chloride_profile) |
| rcm_migration | Migration coefficient bars | G, D | column | — | M |
| resistivity_vs_age | Resistivity vs age, class bands | t, ρ | line + bands | — | M |
| sorptivity_sqrt_t | Absorption vs √t, two slopes | √t, i | scatter + 2 fits | slopes | M |
| water_absorption_bar | Absorption / porosity bars | G, % | column | — | L |
| freeze_thaw | Relative dynamic modulus vs cycles | N, RDM | line + ref | — | M |
| service_life | Probability of failure / reliability vs time | t, Pf/β | line + target | probabilistic | M |
| pore_solution_ions | Ion concentrations (log Y) + pH | t, n×c, pH | multi-Y log | — | M |
| leaching_cum | Cumulative leached amount vs √t | √t, mg/m² | scatter + fit | diffusion slope | M |
| temp_rise | Semi-adiabatic temperature rise / maturity | t, T | line | maturity | M |

## R. Sustainability and decision support
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| co2_emissions_stacked | Emissions by source stacked | G, n×kg | stacked column | — | H ✔ (co2_emissions_stacked) |
| waterfall_co2 | Reduction steps waterfall | step, Δ | bridge | — | H ✔ (waterfall_co2) |
| lca_multi_impact | Normalised multi-impact bars or radar | impact, G | grouped column / radar | normalisation | M |
| sankey_mass_energy | Mass/energy Sankey | src, tgt, val | Sankey | balance | H |
| eco_efficiency | Intensity (e.g. kg CO2 per unit performance) vs performance | perf, CI | scatter + iso-lines | ratio | H |
| pareto_front | Pareto front, 3rd metric as size/colour | X, Y, S, Z | bubble colormap + front | non-dominated sort | H |
| macc_sector | Abatement cost curve | lever, cost, t | MACC | — | M |
| radar_properties | Multi-criteria radar | criteria, G | Radar | normalise | H ✔ (radar_properties) |
| sensitivity_tornado | Tornado (sensitivity ±) | param, low, high | floating bar | — | M |

## S. Electrochemistry and energy *(added)*
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| cv_voltammogram | Cyclic voltammogram, several scan rates (colour-mapped) | E, i, rate | line, colour-mapped | peak currents, ΔEp | Gen |
| tafel_plot | Tafel plot (log current vs potential) with fitted slopes | E, log i | line + fits | Tafel slopes, i_corr | Gen |
| gcd_curves | Galvanostatic charge–discharge curves per cycle | t or Q, V, cycle | colour-mapped lines | capacity | Gen |
| capacity_retention | Capacity and coulombic efficiency vs cycle (double-Y) | N, Q, CE | Double-Y | retention % | Gen |
| ragone_plot | Ragone plot (energy vs power density, log-log) | P, E, G | log-log scatter | — | Gen |
| polarization_curve | Polarisation / I–V curve with power density on 2nd Y | i, V, P | Double-Y | max power | Gen |

## T. Life science and medicine *(added)*
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| dose_response_4pl | Dose–response, log dose, 4-parameter logistic fit | dose, resp, G | scatter + fit (log X) | EC50/IC50, Hill slope | Gen |
| kaplan_meier | Kaplan–Meier survival curves with censor ticks and at-risk table | t, event, G | step lines | log-rank | Gen |
| roc_curve | ROC curve with AUC and diagonal | FPR, TPR | line | AUC | Gen |
| michaelis_menten | Michaelis–Menten + Lineweaver–Burk inset | [S], v | scatter + fit | Km, Vmax | Gen |
| growth_curve | Growth curves (log OD vs t) with error band | t, OD, G | line + band, log Y | growth rate | Gen |
| gel_band_quant | Band intensity bars normalised to control | G, I | column + points | normalise | Gen |

## U. Analytical chemistry *(added)*
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| calibration_lod | Calibration curve with LOD/LOQ, residuals panel | conc, signal | scatter + fit + panel | slope, LOD, LOQ | Gen |
| chromatogram | Chromatogram with integrated peaks shaded and labelled | t, signal | line + fill | areas, Rt | Gen |
| mass_spectrum | Mass spectrum as sticks with m/z labels | m/z, I | drop lines | — | Gen |
| standard_addition | Standard-addition plot with x-intercept | added, signal | scatter + fit | unknown conc. | Gen |
| titration_curve | Titration curve + first derivative | V, pH | Double-Y | equivalence point | Gen |

## V. Physics, signal and engineering *(added)*
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| fft_spectrum | Signal + amplitude spectrum (FFT) panels | t, y | 2 panels, log Y | FFT | Gen |
| spectrogram | Time–frequency spectrogram | t, f, P | image/contour | STFT | Gen |
| arrhenius_plot | ln k vs 1000/T with Ea (general kinetics) | T, k | scatter + fit | Ea | Gen |
| hysteresis_loop | Hysteresis loop (M–H, P–E, load–unload) | X, Y, branch | line | loop area, coercivity | Gen |
| iv_curve | Current–voltage curve, linear and log panels | V, I | 2 panels | diode fit | Gen |
| bode_filter | Bode magnitude/phase of a system (control/filters) | f, dB, φ | 2 panels log X | cut-off | Gen |

## W. Environment and geoscience *(added)*
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| time_series_band | Long time series with moving average and min–max band | t, y | line + band | rolling mean | Gen |
| depth_profile | Depth profile (depth downward on reversed Y), several variables | value, depth | multi-panel, reversed Y | — | Gen |
| seasonal_boxplot | Monthly / seasonal box plots | month, y | box | — | Gen |
| climate_stripes | Warming stripes / anomaly heat strip | t, anomaly | image strip | anomaly | Gen |

## X. Chemical kinetics and general chemistry *(added)*
| id | Type and variants | Roles | Origin path | Calcs | Rel |
|---|---|---|---|---|---|
| conc_vs_time | Concentration of several species vs time with model curves | t, n×c | scatter + model lines | rate constants | Gen |
| eyring_plot | Eyring plot ln(k/T) vs 1/T | T, k | scatter + fit | ΔH‡, ΔS‡ | Gen |
| vant_hoff | van 't Hoff plot ln K vs 1/T | T, K | scatter + fit | ΔH, ΔS | Gen |
| speciation_plot | Speciation fractions vs pH | pH, n×fraction | stacked/overlaid lines | pKa | Gen |

## Gap tiers (from the research report; sections S–X added as Tier 2 general)
**Tier 1 – add first:**
* thermal kinetics pack: kissinger_plot, ofw_kas_plot, friedman_plot, ea_vs_alpha, conversion_vs_T
* dta_raw_meal, eds_ternary_cloud, isopleth_phase_diagram (+ fields and isotherms for the ternary), hot_stage_micro
* qpa_vs_age_area, bogue_vs_qpa, free_lime_vs_T, strength_vs_cumheat, r3_heat_vs_bw, hydration_degree
* calorimetry_log_time, sulfate_balance, xrd_ref_ticks, xrd_peak_area_vs_t
* regression_bands, residuals_4, rheo_flow_curve, rheo_amp_sweep
* sankey_mass_energy, pareto_front, eco_efficiency, eds_map_grid

**Tier 2:**
* porosity, spectroscopy fitting and remaining thermal/calorimetry types
* durability, pore solution, LCA, ternary/contour variants
* statistics: pca_biplot, interaction, main_effects, pareto_chart, bland_altman, qq, hist_kde, violin, raincloud, ridgeline
* layout helpers: bar_line_combo, top_x_secondary, error_band, multi_y, trellis
* general-science packs S–X

**Tier 3 (completeness):**
* smith, windrose, piper/durov/stiff, compass, stock, wafer_map, chord, network, treemap, sunburst
* pole_figure, raman_map, isosurface, bar_3d, andrews, venn_upset, manhattan, volcano and other low-relevance generic types

## Journal figure presets (research findings, verify before submission)
| Publisher | Widths | Text | Lines | Resolution | Notes |
|---|---|---|---|---|---|
| Elsevier (incl. CCR, CCC, CBM) | 90 single, 140 one-and-a-half, 190 double (30 min) mm | 7 pt, ≥ 6 pt sub/superscripts | — | 300 halftone / 500 combination / 1000 line art dpi | EPS/PDF vector, TIFF/JPEG |
| Nature (final artwork) | 89 single, 120–136 1.5-col, 183 double mm | 5–7 pt sans-serif | 0.25–1 pt | ≥ 300 dpi images | panel labels 8 pt bold lowercase **a, b, c**; vector graphs |
| Springer incl. *Materials and Structures* (RILEM) | 84 single, 174 double mm, ≤ 234 mm high | 8–12 pt Helvetica/Arial | ≥ 0.1 mm (0.3 pt) | 1200 line / 600 combination / 300 halftone dpi | patterns in addition to colour; scale bars instead of SEM info bars |
| RSC | 83 single, 171 double mm | 7 pt Arial/Helvetica | — | ≥ 600 dpi | TIFF preferred |
| ACS | 3.25 in single, up to 7 in double | ≥ 4.5 pt final | ≥ 0.5 pt | 300 colour / 600 combination / 1200 line art dpi | TIFF/EPS/PDF |
| Wiley (general) | 80–180 mm | legible | — | 300–600 dpi | — |

Colour-blind-safe default palette (Okabe–Ito): #000000, #E69F00, #56B4E9, #009E73, #F0E442, #0072B2, #D55E00, #CC79A7.
Use markers and hatching as well as colour.

**Selected sources (from the report):**
* OriginLab graphing guide: https://docs.originlab.com/user-guide/graphing/
* OriginLab specialized graphs: https://docs.originlab.com/origin-help/specialized-graphs/
* Stacked lines by Y offsets: https://www.originlab.com/doc/Origin-Help/StackLineYOffset-Graph
* Sankey diagram: https://docs.originlab.com/origin-help/sankey-diagram/
* Elsevier artwork sizing: https://www.elsevier.com/about/policies-and-standards/author/artwork-and-media-instructions/artwork-sizing
* Nature final submission: https://nature.com/nature/for-authors/final-submission
* Springer *Materials and Structures* guidelines: https://link.springer.com/journal/11527/submission-guidelines
* ACS author guidelines: https://researcher-resources.acs.org/publish/author_guidelines?coden=mamobx
* ICTAC kinetics recommendations (Vyazovkin et al. 2011): https://digital.csic.es/bitstream/10261/354012/3/ICTAC%20Kinetics%20COmmittee%20recommendations.pdf
* CemGEMS (Kulik et al. 2021): https://letters.rilem.net/index.php/rilem/article/view/140

# CHANGELOG – Origin Plot Studio upgrade v2

What changed for the user, newest first. Versions are those of the app (Help ▸ About).

## 5.54.4

* **Fixed: a multi-sheet workbook could draw the wrong sheet.** When a file has many sheets and none is called "Data", the sheet picked is now the one that actually fits the ticked template (tried against it directly), not just the sheet with the most numeric columns or the first sheet - which could be a text-only guide page.
* **Fixed: an instrument export with a leading row-number column ("No.", "#", "Index"…) could be drawn against that column instead of the real x / position column.** The row-number column is now skipped when picking x and the series columns, everywhere a file is read.
* **Fixed: a "decimal commas" instrument export (the comma is both the column separator and the decimal point) now keeps its real header text** instead of falling back to generic column names.
* **Fixed: a reference pattern file with an almost-empty text column (for example "ESD") was sometimes drawn as if it were a peak list too.** Only a table whose name column actually names more than one thing counts as a peak list now, so reference stick rows ("connect related things") come only from the real peak list file.
* Reading a photo in the Sketch pad now always reports a clear message (and logs the full error) instead of a cryptic crash when the image cannot be read.

## 5.54.3

* **Fixed: a failed command used to do nothing visible.** The app runs without a console window, so an error inside a button's command (for example "Draw my data like this") was swallowed by Qt and nothing was shown - it looked exactly like the command doing nothing. Every such error is now written to **error_log.txt** next to the app, shown in the status bar, and included in *Help ▸ Problem report*. **Help ▸ Open the error log…** opens it directly.

## 5.54.2

* **The phase library is built in again**: 19 phases with 1889 reflections (clinker phases, feldspars, micas, carbonates, quartz, gypsum and others). Every reference to samples was removed from it; the positions and intensities are unchanged. Nothing has to be installed by hand. Phase files in your private folder still come first.

## 5.54.1

* **House figures** is the second entry of the classes in *Analysis ▸ Graphs and templates*: one click shows the house figure layouts (stacked XRD with zoom, fit with tick rows, TG–DTG panels, calorimetry, particle size …). **My templates** is right below it. Nothing has to be installed for these: they come with the app, in the house style, which is the default.

## 5.54.0

* **One place for graphs: the gallery is inside Analysis.** The top bar has four sections: Workspace · Analysis · Assistant · Settings. *Graph gallery* is no longer a section of its own.
* **Analysis** has two views, with a switch at the top:
  * **Graphs and templates** (opens first): the picture gallery – tick your files and the pictures of the graphs you want, *Draw my data like this*, then Origin, export or combine;
  * **Calculations**: the analysis tools with their settings (XRD, TGA, calorimetry, composition and the 44 data-analysis tools).
* **The 26 workbook graph types** (G01–G24, C01, C02) are pictures in that gallery, in the class of their technique, and are drawn from your ticked workbooks like any other picture. The separate look-alike list page is gone. *+ Add template ▸ Workbook for a workbook graph type* writes such a workbook from a raw file.
* **Fixed: your loaded files were missing from the gallery.** Files added while the gallery was open did not appear in its Files list. They now appear at once, ticked.

## 5.53.0

### Panels
* **Every panel has a clear title strip** with three buttons: **▾ Fold** (only the title stays), **⧉ Float**, **✕ Close**. View ▸ Panels brings a closed panel back. (The close button had been hidden by the style of the window.)
* **Dragging a panel moves it.** Drag the title strip and drop the panel on another side, or on another panel to make tabs. Before, a panel turned into a separate window the moment it was dragged and could not be dropped anywhere. *View ▸ … as its own window* still makes a normal window with minimise and maximise.
* **View ▸ Side bar** shows the side bar again.

### Analysis and Graph gallery no longer repeat each other
* The list under *Graph gallery ▸ Workbook graph types* now holds only the 26 workbook graph types. The analyses that were listed there a second time (XRD drawing, FTIR, particle size, thermodynamic modelling) are in **Analysis**, once. The FTIR stacked / overlaid figures and *Stack / Overlay the ticked graphs* moved to Analysis (FTIR, and *Figures from several graphs*).

### Graph gallery
* **Draw my data like this** (the blue button): your ticked files are drawn in every ticked template picture. With no file ticked it ticks your files, or asks for them. Right-click a picture: *Draw my data like this (only this template)*.
* **+ Add template**: from a graph you made here, as a copy of a ticked template, or from a template file. It appears under *My templates* and is drawn like any other.
* Classes with short names: XRD · FTIR, Raman, NMR, XRF · Microscopy · Particle size and porosity · Rheology and mechanics · TGA, DTG, DSC, kinetics · Calorimetry · Thermodynamic modelling · Strength and durability · CO2 and sustainability · … and by graph type.
* **New figure layouts** (121 templates now):
  * particle size of two groups, 2 × 2: differential and cumulative per group, the legend above each row, d10 / d50 / d90 in a coloured table;
  * heat flow with inset (a) beside cumulative heat with group brackets (b) – the groups are yours;
  * TG–DTG panels: the total mass loss in each panel, your reference lines, your own notes with arrows (typed in the editor);
  * a flow diagram of a procedure from a table of steps (boxes and arrows; photographs are not drawn).
* **Zoom and inset can be switched off**: in the XRD fit the grey band goes with the inset; the stacked XRD has *show zoom*; a zoom window without data is left out instead of failing. The calorimetry insets have a switch too.

### Fixed
* Cumulative heat drawn from your own heat-flow files was in mW·h/g; it is now in J/g (× 3.6), as the axis says.
* Previews of some templates failed on computers with an older numpy.

## 5.52.3

* **Selecting is ticking.** A click on a template, a file or a style ticks it (✓ before the name and a blue frame); click again to untick, Shift+click ticks a range, Ctrl+A ticks all that are shown.
* **A ticked template is drawn at once**: from your ticked files, or as an illustrative example when no file is ticked. Your Workspace files are ticked the first time you open the gallery.
* **Templates in classes**: a tree *By instrument / technique* (XRD, spectroscopy, microscopy, particle size, rheology, thermal analysis, calorimetry, thermodynamic modelling, engineering, sustainability, electrochemistry, life science, analytical chemistry, physics, environment, kinetics) and *By graph type* (basic 2D, bars, multi-panel, statistics, contour, specialised, flow, 3D), each with "can be drawn now of in the catalogue".

## 5.52.2

* **One Graph gallery.** The templates are inside *Graph gallery* now; the separate *Templates* entry in the top bar is gone. A switch at the top of the gallery shows **Templates** or **Workbook graph types (26)**, and the gallery opens where you left it.

## 5.52.1

* The app finishes its own update: when a part of a new version is still missing after an update (the template library), the button **Finish the update (one click)** appears at the top by itself.

## 5.52.0

### New: Templates (graph = template × style × your data)
* A new view **Templates** (inside *Graph gallery* since 5.52.2), with six panels: Files, Columns, Templates, Styles, Previews, Variants.
* **Multiple selection everywhere**: click, Ctrl+click, Shift+click, Ctrl+A and a tick box on every row, in every list. *Select all in this category*, *Clear selection*, and a count such as "3 files · 4 templates · 2 styles selected → 24 previews".
* **Previews with my data**: every ticked combination files × templates × styles is drawn from your files. Double click a tile to enlarge and edit it. Tick the ones to keep.
* **118 graph templates** can be drawn (104 from the template library, 14 new from Tier 1 of the catalogue). The other graph types of the catalogue are listed as *coming*.
* **9 style presets**: house style, Elsevier, Nature, Springer/RILEM, RSC, ACS, slides, greyscale, colour-blind safe. The export warns when text or lines fall below the minimum of the chosen preset.
* **Recommender**: *Works with the ticked files* shows the templates your file can fill, best fit first (2θ → diffraction, temperature + mass → TGA, source / target / value → flows …). Nothing is labelled by it.
* **Columns**: choose the sheet, untick columns, change their order; remembered for files with the same headers.
* **Variants on every template**: log x / y, reversed axes, markers, normalise, offset, grid, hatched bars, second top axis (d-spacing or 1000/T), axis limits.
* **Batch actions on the kept previews**: Open all in editor · Draw all in Origin like this · Export all · data of all in one Excel workbook · apply one style to all · Combine into one figure · remove.
* **Combine into one figure**: 1×2, 2×2, 2×3, stacked, one row or your own grid, with panel letters in the format of the style; can be sent to Origin as one graph.
* **My templates**: *Save as my template* (kept in your private folder with a preview and an Origin script), export / import as one `.opst` file.

### New: Draw in Origin like this
* The graph you see is rebuilt in Origin: one layer per panel or inset at the same place on a page of the same size; the same axis ranges, scales and reversals; curves with their colour, width, dash and marker; bars; shaded zones; texts, panel labels and the legend; text sizes in points.
* Your data goes into worksheets laid out for that graph. Each graph is saved as `{sample}_{template}.opju`, with the complete LabTalk script (`.ogs`) beside it.
* Where Origin has no equal, the closest is used and one line says what differs (list per template: `origin_plot_app/opstudio/origin/DIFFERENCES.md`).
* *More ▸ Build Origin templates (.otpu)* stores Origin graph templates on a computer with Origin.

### New: TGA / DTG module (Tools ▸ TGA / DTG analysis)
* TG and DTG in one graph, DTG at its natural sign. DTG peaks with extrapolated onset and endset.
* Zones are suggested and shown as shaded bands. Drag their edges on the graph; add, split, merge, delete.
* Mass loss per zone by the stepwise **and** the tangent method, side by side. Ca(OH)₂, CaCO₃ and Mg(OH)₂ from zones you confirmed. Ignited or binder basis, bound water, replicate statistics.
* **Confirm labels**: every zone name is a suggestion with "?" until you confirm it. Unconfirmed names are never written on exported graphs or into Excel. Confirmed names are remembered per material.
* *Export results → Excel* (Data, Peaks, Zones, Summary, Chart), *Copy table*, *Draw in Origin like this*, *Save graph*.

### Command area and sessions
* **File** is the left-most command, followed by **Save, Undo, Redo** (one Undo / Redo for the whole app), then the sections.
* **Ctrl+Q** searches every command by name and runs it. (Exit: Alt+F4 or File ▸ Exit.)
* **File ▸ Clear / Start afresh**: Clear graph, Clear all graphs, Remove ticked graphs, Start afresh (keep settings and layout, or reset the layout too), Reset layout, Recover last session. Each asks with a one-line summary and can be undone with Ctrl+Z.
* **Save** (Ctrl+S) writes to the session file in use; **Save session as** (Ctrl+Shift+S); **Recent sessions**.
* The session is saved by itself every 5 minutes and when the app closes. After a crash the app offers to bring it back.
* Every button has a tooltip: name, shortcut, what it does, and what enables it when it is disabled.

### Graph catalogue
* Tier 1: isoconversional kinetics (OFW / KAS lines, Friedman) with known-answer tests, reference stick rows under a pattern, peak area against time, log-time calorimetry, heat-flow curves against dosage, degree of reaction, strength against heat, reactivity test, phase evolution against age, calculated against measured composition, burnability curve, ternary point cloud with density shading, eco-efficiency.

## 5.51.0

* **Your own work stays on your computer.** The app reads your phase files, styles, templates and defaults from your private folder (`%APPDATA%\OriginPlotStudio\my_templates`, or the folder named by `OPS_PRIVATE_DIR`). Nothing in it is published or sent anywhere, and the updater never touches it.
* The published app holds no data, names or results of any user. Examples and previews use neutral names. A small starter list of common minerals replaces the built-in phase library; your own phase files come first.
* The section with the 26 workbook graph types is now called **Graph gallery**. Sessions saved by older versions open as before.
* A privacy check runs before every commit of the project (`tools/check_banned.py`; the list of private terms is kept outside the repository).

## Not changed

Assistant (all providers, key storage, history, upload), HighScore reading, the Origin drawing of Workspace graphs, the 44 analysis tools, calorimetry, the XRD tools and old sessions work as before. The updater's own check gives the same Origin commands as 5.50.0 for all ten example files.

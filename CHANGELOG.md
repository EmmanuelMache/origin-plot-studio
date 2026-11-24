# CHANGELOG – Origin Plot Studio upgrade v2

What changed for the user, newest first. Versions are those of the app (Help ▸ About).

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

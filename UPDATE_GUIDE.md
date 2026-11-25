# Origin Plot Studio 5.56.0 — Project workbench update

The application now has the three-column Start Here design: **Projects → Inspect data → Choose a graph**. The existing Qt desktop application, scientific engines, original 121 templates, 26 workbook graph types, Assistant, exports and Origin integration are retained. A plain **Line plot** template has been added to Analysis, making 122 registered templates.

![Start Here](docs/start_here_preview.png)

## Install on Windows

1. Close Origin Plot Studio.
2. Extract this complete ZIP to a new folder.
3. Open `origin_plot_app/Setup.bat` to update the installed application. The existing installer preserves your settings and saved project list.
4. Launch Origin Plot Studio from its shortcut. To run the extracted copy, use `origin_plot_app/Run_Origin_Plot_App.bat`.

Python source is included. This is an updated application package with its existing installer, rather than a compiled standalone EXE.

## Start a project

- Select **New project**, enter a name, and add multiple files or drop supported files onto Start Here.
- Create folders, move files into them, rename folders/projects, and change their order with the project menu or Move up/down.
- Check projects, folders or files to open several inputs. The selection summary shows the scope. A highlighted file determines the data shown in Inspect data.
- **Open selected** loads the chosen sources with project labels. **Save** keeps data edits and graph settings. **Close** saves and closes that project.
- **Export project** creates a portable `.opsproject` containing input-file copies and saved state. **Open project** imports it, including on another computer.
- Removing an item from the project does not delete the original file. Removing a folder returns its files to the project root.

Normal saved projects retain references to their source files. Keep those files available; use the portable project export to include the source bytes. Missing files are identified in the project browser.

## Inspect data and choose graphs

The application recognises Unicode diffraction headers such as `2θ`. It distinguishes scientific measurement type from file extension and displays the evidence for detection. Numeric-only, angle-like scans require confirmation before specialised recommendations are offered.

Select the Excel sheet and map X/Y columns. **Data type** can confirm or correct the identification. Corrections are scoped to the selected sheet, so a mixed workbook can contain XRD and TGA data without sharing one forced type.

**Choose a graph uses the live Analysis catalogue.** It does not contain a separate hard-coded gallery. Available built-in and private templates are checked against the selected data. Recognised structured workbooks can recommend their installed workbook template. Unsupported or incomplete inputs are explained; for example, raw multi-column scans do not automatically count as observed/calculated fit data, and a d-spacing recommendation requires a confirmed wavelength.

Choose separate graphs for each file or a combined graph when the template and inputs support it. **Browse Analysis templates** carries the selected files and column mappings into Analysis. **Create graph** opens the output in Workspace.

The thumbnails illustrate template layouts; the central preview shows the selected file's actual data.

## Workbook

Workbook provides editable working copies, per-sheet selection, column order and inclusion, X/Y mapping, data type correction, file order, and data export. Original files are not overwritten by editing the table. Save the project to retain edits.

Two merge modes are available:

- **Append rows:** requires matching column names and records the source filename for each row.
- **Join columns:** requires finite, unique, identical X values in the same order. It does not silently interpolate or average data.

Merges create a separate derived dataset in the active project. Use the graph chooser or Analysis after preparing the data. Structured workbook figures also receive working-copy data while retaining their own recipes.

## Graph controls

For a created template graph, select **Edit this graph** in Workspace, or use the component editor on an Analysis preview. Set markers on measured data and fitted curves independently. Select the whole graph or an individual panel to control zoom and its range, residual rows, Bragg rows and available background curves.

For existing composed figures, use the per-panel controls or right-click the relevant panel. The original graph editor also includes **Edit each graph / panel independently** for previews such as the pattern-and-fit Sample page. Changes to one graph do not switch off the other graph's zoom.

Difference, Bragg, peak/stick and background controls cover the identifiable lower-plot components. The earlier phrase “painting plot” did not identify a specific component by name; no scientific component has been renamed to that phrase.

Hiding and removal preserve source measurements. Adding a component back requires its actual source data; the app does not invent phase reflections or fitted values. Batch application is an explicit option.

## Send to Origin

Review and edit the graph, then use **Send to Origin / Draw in Origin**. The existing figure-to-Origin driver transfers supported curves, markers, layers, axes and text, and reports its existing differences. Project save, figure export and Origin transfer remain separate operations.

Live Origin automation requires Windows and an installed compatible Origin/OriginPro. This environment did not contain that installation. Native Windows/PySide6 startup and COM automation still require local verification. Core, data, rendering and Origin command-generation checks are documented in `IMPLEMENTATION_AND_TESTS.md`.

The preview images use example data and were rendered from the application through a local Qt compatibility test runtime. That test adapter is not included in the application.

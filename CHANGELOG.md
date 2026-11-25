# CHANGELOG – Origin Plot Studio upgrade v2

What changed for the user, newest first. Versions are those of the app (Help ▸ About).

## 5.57.0

The project-workbench update merged into the app. The look and the new project features come from the update; how the app behaves is as it was at 5.56.0. `UPDATE_GUIDE.md` is the guide for the user.

* **"Start here" is now Projects → Inspect data → Choose a graph.** Projects have folders, can be saved, closed, reopened, exported as a portable `.opsproject` (with copies of the input files) and imported. Tick projects, folders or files; **Open selected** reads them and shows them in Workspace when they are read. The middle column shows the file you click, what it was recognised as and by which columns, its first rows and a plot of the X and Y you choose. The right column lists the templates of Analysis that fit it, with the reason, and **Create graph** opens the result in Workspace.
* **New: "Workbook"**, a section of its own in the top bar. Edit working copies of the data (the source files are never written), choose the sheet, order and switch columns, set X and Y and the data type, arrange the files, export the prepared data, and merge files into a new, separate dataset: *Append rows* needs the same columns, *Join columns* needs identical X values - nothing is interpolated.
* **New: "Edit this graph…"** for a graph made from a template: markers on measured and fitted curves separately, zoom inset and its range, difference row, Bragg rows, background - for the whole graph or one panel of it. A control is greyed out, with the reason, where the graph has no such component. Applying to all graphs of the project is a separate tick.
* **New: a plain "Line plot"** in Analysis (122 templates now), offered whenever the kind of data is not established.
* **A file is recognised from its contents.** `2θ`, `2Theta`, `2-theta`, `Two theta` and the usual export headers are all diffraction; a table with a calculated column is a pattern and fit; positions with widths, areas or h k l are a peak list and are not offered the scan templates; numbers alone are only *tentative* until you confirm. **Data type** lets you say what a file is, and every class of the template catalogue can be chosen there.
* **Fixed: a pattern-and-fit export was read by column position.** With a leading `No.` column the row number was drawn as 2θ and the curves were shifted by one column; a background column after the calculated one was drawn as the difference. The columns are now taken by their names (observed, calculated, difference, background); unnamed columns keep their order. A background the file names can be switched on in "Edit this graph…".
* **Fixed: the window stopped for seconds while several files were added.** Each file re-ranked all 122 templates, and each ranking rebuilt every template's example data and read every ticked file. Ten files: 3.6 s of stopped window before, about 0.5 s now; files are read in the background and a file is shown as soon as it is read.
* **Kept from before** (the update had dropped these; they are back): **View**, **Tools** and **Help** as buttons on the header (in the ••• menu on a narrow window); adding a file without creating a project; a column choice remembered for files with the same headers; the sheet that fits the ticked template picked by itself; an unreadable file listed, with the reason in words; a tooltip on every button. Every entry of the File, View, Tools and Help menus and every keyboard shortcut of 5.56.0 is still there. The "Assistant" entry of the top bar is now a button that shows and hides the Assistant panel.
* **Selecting in the project list is a click on the row** (click again to untick), as in the file lists of Analysis; the small box still works. The stray little box that was drawn beside the highlighted row is gone - the highlight is one bar.
* **Fixed in the update itself:** two header buttons that appeared as a block over the top-left corner; the Start here plot drawn at twice its size; text overlapping in the Projects column on a small screen; with files of several kinds ticked, only the plain plot was offered - the chooser now follows the file you are looking at and makes a graph for each ticked file the template fits.
* Not verified: Windows itself and a live Origin (everything ran with PySide6 on Linux without a screen; Origin as the driver's dry run). A workbook with dozens of sheets still takes about a minute to read, in the background.

## 5.56.0

* **"Start here" redesigned as three columns.** Left: **Your projects**, now with a search box that narrows the list as you type. Middle: **Inspect data** - click a file to see what kind of data the app thinks it is, its first rows as a table, and a quick plot of its first two numeric columns. Right: **Choose a graph** - the templates that fit the file as pictures, the best one first (★); click any of them, then **Create graph**.
* **New: you choose which graph is drawn from Start here.** Before, the button could only draw the single best-fitting template; now it draws the one you picked, from the file you are looking at.
* **New: "Change type".** If the app's guess of what the file is (diffraction, thermal analysis, calorimetry …) is wrong, pick the right kind from the list beside it; the graphs on the right re-sort to put that kind first. "Automatic" gives the app's own pick back.
* The file you add is shown at once (selected, with its preview). Delete / right-click still removes the highlighted file(s).
* Not in this version: choosing the plot preview's x and y columns yourself (it uses the first two numeric columns), and a separate "Workbook" tab (arranging a workbook's figures stays on the right-click menu of Your graphs).

## 5.55.7

* **New: "Arrange this workbook's figures…"** - right-click a graph read from a file that gives several (a workbook of composed figures, or several sheets each drawn as a picture), under Your graphs. Drag to reorder the figures of that file (or use Move up / Move down), and untick one to leave it out of "Draw ticked" and the paper set. The new order is kept in Your graphs, and "Draw all in Origin" / "Draw ticked" / the paper set all follow it, the same way dragging a row in Your graphs already did - this just gives a focused view of one workbook's own figures instead of the whole list.

## 5.55.6

* **Fixed: the Zoomed-part switch also did nothing on a Sample page** (the measured pattern with its assigned peaks, next to its fit - made by "Sample pages" / "Which peak list goes with which pattern"). Same root cause as 5.55.5's fix to the "several fits, one panel each" figure, closed here too: the pattern's own, already-built inset was used regardless of the switch. A typed 2θ range now also wins over the pattern's own zoomed part, where before it was silently ignored for this figure type.
* **New: Delete / right-click "Remove this file" on "Start here"'s file list.** It had no way to remove a file at all - only Analysis ▸ Graphs and templates ▸ Files did. Removing it here takes it out of the Files list and out of Workspace's Your graphs together, in one step; the file on the disk is never touched, and "Add data files…" brings it back.

## 5.55.5

* **"Start here" is now what you see when the app opens**, instead of Workspace. (Files given at launch, e.g. dropped on the shortcut, still go straight to Workspace to show them.)
* **New: "Your projects", under Start here.** A project is a name for a set of data files (CSV, TSV, Excel …) you come back to. Create one, add files to it, then open it - or several at once - to bring all of it into Workspace and Analysis together; each graph is tagged with the project it came from (shown on its row in Your graphs, and findable with the search box). Rename, delete, or see which of a project's files have moved or gone missing, from a right-click menu. Opening several projects at once used to silently drop all but the first (Workspace reads one batch of files at a time); they now open one after another, correctly.
* **Fixed: the Zoomed-part switch did nothing for a "several fits, one panel each" combined figure** (made by Ctrl+G / "Decide for me" / HighScore pairing on two or more fits). The drawing code read the figure's own frozen settings instead of the one your switch had just changed, so toggling it had no visible effect at all. Verified: switching it off now removes every panel's inset, switching it back on restores them.

## 5.55.4

* **Fixed: "Start here" could misname your data.** A Rietveld peak-list export with a column literally called "Source" (common in HighScore and similar software) was scored as a Sankey diagram (mass / energy flows), outranking the correct diffraction templates, because the recommender treated the single words "source", "target", "from" and "to" as enough on their own. It now needs "source" and "target" together (or "from" and "to" together) before it suggests a Sankey diagram.
* **New: a "Panel" bar for a figure of several panels** (Fig_C, Fig_D and similar composed figures with more than one Rietveld fit in one picture), beside Zoom / Pan / Select range. Pick a panel from it and change, for that panel alone: its zoomed part (on or off), its observed curve (dots, or a plain line - useful for a dense scan where dots look noisy), and its difference row (shown or left out). The other panels of the figure are not touched. Undo (Ctrl+Z) takes the change off again.

## 5.55.3

* **Fixed: selecting a graph in "Your graphs" and pressing Delete (or right-click › Remove) did nothing** when the row was a ★ combined figure (several files grouped on shared axes) instead of a plain single graph - the Delete key and "Remove ticked graphs" only recognised single graphs and panel figures, silently skipping combined ones. Delete (and the new right-click menu) now removes a highlighted single graph, ungroups a highlighted ◆ group of yours, or - for a ★ figure the app made on its own - says clearly that the Group list (or the graphs it is made of) is what to change instead, rather than doing nothing.
* **New: a right-click menu on "Your graphs"** ("Remove this graph(s) from the list") alongside the existing Delete key, for removing the highlighted row(s) without first ticking a box.
* **Fixed: "Draw in Origin" / "Draw all in Origin" asked where to put the {sample}_{template}.opju files every single time.** The folder is now remembered after the first time; Draw in Origin then goes straight to Origin without asking again, until you pick "Change the Origin output folder…" from More ▾.
* **Calculations ▸ XRD no longer repeats Analysis ▸ Graphs and templates.** The plain re-drawing entries that duplicated a picture already in the gallery (fits as panels, patterns/fits stacked or overlaid, the zoomed part on/off) are removed from Calculations; they stay available as gallery templates and, for the zoomed part, in the ribbon and Settings ▸ XRD. What is kept here is what the gallery cannot do: deciding for you across several fits, the Sample pages layout, and the HighScore file-pairing tools.

## 5.55.2 – hybrid: nothing of before is lost

* **The app decides for each workbook** (*Draw ▸ Workbooks of figures ▸ Let the app decide*, the default):
  * made for figures – **your saved recipe fits it, or it has a figure-plan sheet**: its figures first, then every sheet that no figure uses (sheets drawn inside a figure are not listed twice);
  * only label / tick / zoom sheets beside the data: the graphs of its sheets **exactly as before**, with the figures added after them;
  * any other file: exactly as before.
  Your own choice is kept in the settings: *Figures and all sheets*, *Figures only*, *Sheets only (as before 5.55)*.
* **Sessions:** a saved session always reads every graph of its files again, so sessions saved before 5.55 open with all their graphs (5.55.1 could lose them for a workbook of figures).
* **Your recipes:** a saved recipe that fits the workbook is always used first. The defaults of the recipe engine are those of before 5.55 (no gap between fit and difference, tick marks of 6 pt up to seven phases, alite on top, inset scaled as before, labels kept clear of every curve); the automatic recipes switch the new behaviour on themselves. What still changes in your recipes are fixes only: the exact pairing of tick rows, labels that were cut and are now shown (or listed in the report), titles and legends kept on the page, labels of a stack (a panel with names at the left) kept at their own pattern.
* **Templates draw exactly as before** for the same files (checked pixel by pixel): the new drawing of labels, coloured tick rows, Rwp and insets is used only when you tick a label, tick or Rwp table, and such tables are only set aside in templates that can draw them – elsewhere they are data, as before. The one deliberate change: in *Stacked XRD + zoom* the zoom panel keeps the offsets of the full panel (the traces used to sit at other heights).

## 5.55.1

* **Fixed: a workbook of figures gave the wrong graphs in the Workspace.** *Add data files* split such a workbook into one raw graph per sheet (model tables read as fits, tick lists as x–y graphs, zoom sheets as fits of their own …) and the composed figures were only reachable through *Tools ▸ Draw ▸ Paper figures from a recipe*. Now a workbook with a figure-plan sheet, or with label / tick / zoom sheets beside its data, comes in as **one graph per figure**: the whole figure is shown in the window, saved as PNG / PDF / SVG / TIFF, and built in Origin by *Draw in Origin*. A saved recipe for the workbook is used when there is one; otherwise it is made from the sheets. Figures of a workbook are never overlaid with each other.
* Fits are drawn over the refined range (where the reflection list has positions), not over the whole scan.
* Chemical formulas in titles and legends get subscripts (Na₂O, K₂O, C₃S, Ca₂Fe₂O₅); sample names such as S1 or P12 stay as they are.
* The workbook's own sentence on labels in brackets is written under a figure whose labels use brackets.
* Bar names that would run into each other are set smaller.

## 5.55.0

### Paper figures for any workbook
* **No recipe? The app makes one.** *Tools ▸ Draw ▸ Paper figures from a recipe…* offers to make the recipe from the workbook itself when no saved recipe fits. It reads what every sheet holds – diffraction or spectral patterns, fits (observed / calculated / difference), Bragg tick lists (pairs `<code> 2θ` + `<code> row`, or a long reflection list), peak-label lists, zoom windows, already-offset stacks, x–y series, category tables with SD columns, agreement indices (Rwp), colour keys written as `<name> <code> #RRGGBB`, and a figure-plan sheet if there is one (Figure / Sheets to use / X title / Y title / Layout / Extras, wildcards such as `*_Profile` included). The recipe is saved in your own recipe folder, never in the app's folder. Also as its own command: **Make a figure recipe from a workbook…** (new module `auto_recipe.py`).
* **Recipe figures in Origin.** *Paper figures from a recipe, also in Origin…* builds every figure in Origin as well (one `.opju` per figure, data in worksheets, labels as text objects); without Origin the LabTalk script is written beside each figure.

### Fixed (wrong or lost content)
* **Tick rows could show another phase's positions.** A row `<code> row` was paired with the first 2θ column whose name *started* with the code, so `B` took `B' 2θ` and `C` took `Cal 2θ` whenever those came first. Now only the exact code pairs; a row without its partner is reported. A code that is literally `X` is no longer swallowed by the column-name pattern.
* **Labels of an offset stack were pushed above the top trace.** Each label was kept clear of *every* curve of the panel. Now a label only keeps clear of its own curve (found by its Sample value or its peak height) and of other labels; the names of the stack no longer cover labels.
* **Labels above the y range disappeared silently.** The axis now grows to hold them; with a y range fixed in the recipe, the cut labels are listed in the report. A label at the edge of a panel is turned inwards.
* **Titles over the top row were cut off** (two-line titles in a 2 × 3 grid). The panels are moved in until everything is on the page; a legend in a free cell shrinks its text to fit.
* **Templates:** *Measured vs modelled* gave a series the style of another model where a column was missing (style by position → style by role, the same in every panel); *Phase evolution vs temperature* left out of the legend a phase that appears only in later panels; *Hatched bars* drew one table only and showed nothing for a bar of zero.

### Improved
* **Templates use the side tables you tick:** a label list, a tick list and an Rwp table ticked beside the data are matched to their data table by name and drawn (labels at their own peaks, coloured tick rows, `R_wp` in the title). A plain `Label, x, y` data table is still data.
* Rietveld templates: one block function for one fit and the 2 × 3 grid (fit, difference, tick rows, inset, Rwp, shared legend). Stack + zoom: the zoom panel keeps the offsets of the full panel.
* Recipes: error bars on bar panels (`"error"`), auto-stacked spectra with a reversed axis, `"sharey"` for panels of a row, `"collide_with"` for labels, `"rwp"` written upright, the tick block of a fit scales with the number of phases, a small gap between fit and difference.

## 5.54.7

* **New "Start here" tab, first in the top bar.** Add your data there; the app says what kind of file it looks like (from the columns, the same guess the ★ marks and "Use what the app recommends" use) and lists the best-fitting templates. Draw the best one at once, or go browse the full gallery yourself - either way, your data is also in Workspace to review and draw in Origin.
* **Fixed: the app could say what kind of file was added, but only after some other action triggered it.** Adding a file now shows "Looks like an XRD file" (or TGA, calorimetry, …) and the ★ best-fit marks the moment it is added, not only after a search or filter is touched.
* **Fixed: a template could fail with "needs an x column…" if a sheet had been chosen for a *different* template earlier.** A sheet you picked for one file is now only kept for a template it still fits; it is no longer silently reused for every other template of that file.
* **Fixed: a file added in Analysis ▸ Graphs and templates now also appears in Workspace** ("Your graphs"), so it can be reviewed there - zoom, pan - and drawn in Origin from either place.
* **Fixed: the app could fail to close properly** (and occasionally crash) if it was closed while a just-added file was still being read in the background.

## 5.54.6

* **Fixed: ticking, searching or filtering templates could stop hiding anything.** "Best fit first" reordering of the gallery (the ★ templates) now keeps each picture's shown / hidden state - a Qt quirk (taking a row out of the list and back in forgets it) meant the search box, the class tree and the file/source filters could silently stop working together whenever a file was ticked.
* **New: "Use what the app recommends"**, beside "Draw my data like this" in Analysis ▸ Graphs and templates. Tick your file(s) and press it: the app picks the best-fitting template for them by itself (the same ranking as the ★ marks) and draws it at once - for when you would rather not browse the gallery yourself.
* The best-fitting templates (★, moved to the top) now update as soon as a file is ticked, without first turning on "Works with the ticked files" (that box still only *hides* the rest - an opt-in choice).
* "House figures" in the Templates class tree is now grouped by instrument / technique (XRD, TGA / DTG / DSC, Calorimetry, Thermodynamic modelling …), like the rest of the tree, instead of one flat list of 20.

## 5.54.5

* **Visual polish pass**, after a review of the window against modern desktop conventions:
  * The header's two search fields ("Search commands…", "Find a graph") now show readable placeholder text on the dark bar - it used to be almost invisible.
  * Scroll bars and right-click / dropdown menus now follow the app's own flat style everywhere, instead of the operating system's own look.
  * Analysis ▸ Graphs and templates: the Files panel's "Add files…" button was being clipped at the panel's default width ("dd files…"); it is now the clear, full-width first action, with "Tick selected" / "Clear" below it.
  * Data and Results tables read more easily with faint alternating row shading.
  * A template picture now lifts slightly (a soft background tint) on hover, and the box you type into in the Assistant has a subtle drop shadow under it - a touch of depth, never blur or transparency, so nothing loses contrast.

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

# CHANGELOG – Origin Plot Studio upgrade v2

What changed for the user, newest first. Versions are those of the app (Help ▸ About).

## 5.59.3

* **New: every graph with labels on its peaks can be drawn with them or without - a "Peak labels" box.** The picture in the app, the exported files and the drawing in Origin all follow it. Curves, tick rows and data are not changed, and the peaks stay listed in Results.
  * **A figure of a workbook** (the row *Panel:* under Zoom / Pan): *Peak labels* for the panel you choose, or choose **All panels** and tick or untick it once for the whole figure. A fit panel that the workbook's figure plan drew *without* labels can now have them: the app takes the rows of its sample from the workbook's label sheet for the fits. Where the workbook has no label rows for a sample, the box is greyed out and says so - nothing is invented.
  * **All panels** also works for the other boxes of that row (zoomed part, observed as dots, difference row, phase tick rows): one click for every fit panel, one step to undo.
  * **Any other graph** (an XRD pattern, a thermal graph, a stacked figure …): a *Peak labels* box beside Zoom / Pan, shown when the graph has labels. Without them the page is laid out again, so no empty room is left above the curve. Each graph has its own switch; a stacked or combined figure follows its own, not that of its graphs.
  * **Analysis graphs**: *Edit this graph…* has **Show peak labels**, for the whole graph or one panel.
  * Right click on a panel of a workbook figure: *Peak labels: hide / show (this panel only)*.

## 5.59.2

* **New: the app can keep its evidence file up to date by itself.** *Help ▸ Learning* has a box *Save the evidence file by itself into a folder (to help improve the app)*. Tick it, choose your Google Drive folder once, and the app keeps one small file there (in a sub-folder *Origin Plot Studio evidence*), refreshed when it starts and closes. The file holds kinds of corrections and failures only - no names, folders or measurements. The app itself sends nothing; your Drive program copies the file. Off by default; untick to stop (this computer's file is removed); local-only mode pauses it.
* **A review every 14 days.** Those files are read every 14 days by a scheduled review, which fixes defects it can reproduce and publishes the fix when the whole test suite passes. You receive it with *Help ▸ Check for updates* as before. Changes to the update, security and privacy parts are never published that way.
* Fixed: *Evidence file for the developer…* said a file was written when problem records were switched off and nothing could be written. It now says what to tick.

## 5.59.1

* **New: "Draw my own graph…" in the Workbook**, for when the suggested graph is not the one you want. You choose X, Y and the type, and pick **any graph of Analysis that fits the table** - the ones that do not fit are shown in grey with the reason. The graph is drawn from the Workbook's columns and opens in Workspace.
* **It is added to learning.** With *Remember this for such data* ticked (it is, unless you untick it), the graph becomes your preferred one for such data and the columns you chose are remembered for files of that layout. The next such file is offered your columns, and the Workbook and Start here list your graph first, marked *Your saved preference*. Untick it and the graph is drawn without anything being remembered.
* **Help ▸ Learning ▸ How it works**: a one-page guide - what is remembered and when, what happens next time, how to switch off or forget something that is wrong, what the four switches do, and where it is kept.

## 5.59.0

Two things in one: the app now remembers what you confirm, and it is hardened for giving to other people.
If anything is wrong after this update, *Help ▸ Undo the last update* puts 5.58.6 back.

### The app remembers what you confirm

* **Remember this mapping.** When you correct a file's type or its X / Y columns on Start here (or in the Workbook), a small bar shows what would be confirmed - "Use XRD · X: … · Y: …" - with *Remember this mapping* and where it should apply. Confirm it, and the next file of the same layout is offered "Saved XRD mapping available" with the reason and Apply / Dismiss. It is checked against the new file before it is used; a file that does not fit is left alone. Opening, refreshing or cancelling records nothing.
* **Prefer this graph for such data**, **Save style…** in the graph editor (for one graph, one panel, or graphs of that kind of data - other graphs are not touched), and **Remember the last merge as a workflow…** in the Workbook.
* **Help ▸ Learning** lists everything remembered, with the before / after of each correction, and lets you edit, switch off, export, import and forget it. Lessons and learned file layouts of earlier versions are taken over once; the original files stay.
* What is remembered is a setting - structure, roles, units, switches - never your measurements, file names, folders or sample names. It is kept in your own data folder, on this computer. Sharing is off; nothing is uploaded.

### Security and privacy

* **Help ▸ Privacy and connections**: four levels for what may leave the computer - *Local-only*, *Minimal AI context*, *Approved metadata*, *Approved scientific content* - and a switch per connection. Local-only blocks the update check, the assistant, the web search, diagnostics and shared learning where the request would be sent, while files, graphs, projects, learning and Origin work as always.
* **The assistant sends only what the level permits**, also in its automatic reading steps: at *Minimal* your sample, graph and file names are replaced by stand-ins and no numbers or results are sent. The wording in the panel says what really happens.
* **Fixed: the update token could be sent to the wrong place** (any address containing a certain word). It now goes only to the exact host and route of the update repository, is dropped on a redirect elsewhere, and never appears on a command line.
* **Fixed: a remote AI address with plain http was accepted.** Remote services need https; a model on this computer is reached on an approved port only. A key is not reused for another service.
* **Fixed: keys could be written to disk as plain text** outside Windows. Keys are protected by Windows or the system keyring, or kept for the session only.
* **Updates can be verified.** A release signed by its publisher is checked before any of it is unpacked or run; an interrupted installation is finished or undone at the next start. In a build made for other people, unsigned updates and the "AI repair" of the program are not available. (Your own copy updates from the repository as before and says that such an update is not verified.)
* **Project import** has size, count and path limits, unpacks into a staging folder and leaves everything as it was when it fails; a project cannot carry keys, update settings or program paths. **Export** neutralises text cells that a spreadsheet would run as a formula; numbers are untouched.
* **Packages are pinned** with checksums and installed only by Setup. The tested set needs **Python 3.12 or newer**.
* **Problem report** is now safe to send: names, folders and keys are removed, and MANIFEST.txt says what is inside.

### For the developer

A 14-day improvement cycle (a daily gate, an evidence bundle, a Claude Code pull request, a separate signed release) and an optional shared-learning backend are in the repository as code and tests. **None of it is active**: see `docs/FORTNIGHTLY_CYCLE.md`, `docs/SHARED_LEARNING_SETUP.md` and `docs/LEARNING_SECURITY_COMPLETION_REPORT.md` for what was tested and what needs you.

## 5.58.6

XRD graphs are stacked in every case.

* **New: several peak lists are stacked too.** Until now only measured patterns were put into one stacked figure; peak lists of several samples stayed single graphs. With two or more peak lists (and no measured pattern of theirs in the list) the app now makes a ★ stacked figure and puts it first: one sample above the other on its own baseline, the sticks of each sample divided by its strongest peak, **one colour per mineral - the same in every sample** - with the minerals in the legend, the mineral names on the peaks, and the sample names at the right.
* **Stacked measured patterns: the mineral names stand upright on the peaks.** Whole names written side by side ran into each other and were joined to their peaks by long leader lines; they are written upright now, as in the graph of one sample. Letter codes (A, B, Q ...) are placed as before.
* When the measured patterns of the same samples are in the list, there is one stacked figure - the patterns, labelled from their peak lists - and the peak lists are not stacked a second time. *Keep them separate* in the Group list still gives single graphs only.

## 5.58.5

XRD: a peak list whose patterns are named by PDF number, with its pattern list.

* **New: the peaks are labelled with the mineral names, not the PDF numbers.** A peak list from a search-match names the pattern that explains a peak by its reference code (*Matched by*: `01-072-0156`). The names belong to those codes in the **pattern list** of the same analysis (*Ref. Code*, *Compound Name* / *Mineral Name*). Add both - as two files, as two sheets of one workbook, or one under the other in one CSV - and every matched peak carries the name of its mineral; a peak matched by two patterns carries both names. Before, all of them were drawn as one phase labelled "?".
* It works on the **peak list drawn by itself** (sticks coloured by mineral, names on the peaks and in the legend, peaks no pattern explains in grey without a label) and on the **measured pattern** of the same sample, which takes its labels from the peak list.
* The name is the one the file gives: the *Mineral Name* column when there is one, else the compound name. "syn" and "low" are left off (*Portlandite, syn* → Portlandite; *Quartz low* → Quartz), and a compound that is one mineral without doubt gets its mineral name (calcium hydroxide → Portlandite). The record of the graph lists which name stands for which number.
* The pattern list can be added later: the graphs that were waiting are drawn again. The names are remembered, so the next peak list with the same patterns gets them without its pattern list.
* Without any pattern list a code stays a code - the app does not guess a mineral from a number - and the record says which pattern list to add.

## 5.58.4

FTIR and TGA graphs drawn after two reference pictures, and the merge shown where you look:

* **Infrared spectra (Analysis ▸ *FTIR stacked spectra with labelled bands*, the first graph offered for infrared files)** are drawn as in the reference: the spectra one above the other in **one colour per sample**, the y scale shown (*Transmittance (%), offset per sample*), wavenumber from 400 up to 4000, and **every band of every spectrum marked on its curve (▼) and labelled below it** in the colour of the spectrum with its wavenumber and the usual assignment (`1409 ν₃ CO₃²⁻`, `957 Si–O (C-S-H)`, `3642 O–H (Ca(OH)₂)`; the CO₂ of the air is named as such). The legend with the sample names stands at the lower left. The names are the usual ones for those wavenumbers - possibilities to check; with more than four spectra they stand at the top spectrum only. A band near 665 cm⁻¹ got its name (Si–O).
* **DTG of several thermal runs (Analysis ▸ *DTG of several samples with shaded decomposition zones*, now the first graph offered for a series of TGA files)** is drawn as in the reference: the DTG curves of all samples in one graph, in % per minute, over the shaded zones **named inside the graph** in bold (C-S-H / AFt 30–200 °C, AFm ~150–250 °C, portlandite 400–550 °C, calcite 600–800 °C), x from 30 to 900 °C, a framed legend at the lower left (moved only if curves run through that corner), left and bottom axis only.
* **Fixed: that graph was wrong for files as the instrument writes them.** Time, mass and DSC of every file were each drawn as a "sample" and no zones were shaded. Each file is now one sample - its mass against its temperature - and the heating rate is read from the file's own time column.
* **Fixed: "the merge is not working".** The merge did write its workbook, but the Workbook then showed the sheet of the *first file* - exactly what was there before. It now opens the merged workbook on **All side by side**: every file with its own X and Y columns, named after the file. That sheet (and *Peaks of all files*) is a view to read and export; the sheet of each file is one choice away in the Sheet box, and the graphs are drawn from those.
* **Fixed: after a merge every sample was drawn twice in the combined figure** ("6 x TGA" for three files) - the sheets of the merged workbook were counted beside the files they were made from.

Both graphs go to Origin with their labels: the band labels as texts at their wavenumbers, the marks as symbols, the zones as shaded areas with their names. Not checked in a running Origin here.

## 5.58.3

Seen on a screenshot of the Workbook with a merged workbook of infrared spectra open:

* **Fixed: the peak columns looked empty.** The name of a peak was written in the row of that peak - ten names among 7,468 rows, none of them in sight. The peaks are now **listed from the first row down** in three columns at the right of the data: where the peak is (*Band at (cm⁻¹)* / *Peak at (°C)*), its label, and what it may be. A label you type in the table of peaks shows there at once.
* **Fixed: in a merged workbook the app's peak columns were taken for data** (ticked under Columns, and so carried to graphs). They are the app's own columns in every file now, also in workbooks merged or exported with an earlier version. A workbook merged from now on is kept clean: the sheet of each file holds its data (and DTG), the peaks of all files stand on a sheet of their own, *Peaks of all files*, and the last sheet has all files side by side.
* **Fixed: one infrared spectrum was offered only the plain line plot.** The infrared graph (spectrum with its band lines) needed two spectra. It draws one as well and is now suggested first.
* **Fixed: a repeat measurement was left out of its series.** `…-40-X` and `…-40-X-2` are built the same way but for the repeat number; the second was not counted in ("2 files" where there were three).
* **Fixed: a column header cut off** at the left ("Navenumber"): every column is as wide as its header needs.
* **New: sheets.** *Table ▾ ▸ Add a sheet…*, *Duplicate this sheet…*, *Remove this sheet* - in the working copy; the file on the disk keeps its sheets, and what you added or removed is remembered with the project.

## 5.58.2

* **The Workbook table works like a spreadsheet.** A **Table ▾** button (and the right-click menu) holds: *Copy* (Ctrl+C), *Cut* (Ctrl+X), *Paste* (Ctrl+V) - a block copied in Excel goes in from the selected cell, and rows and columns are added when it is larger -, *Insert a row above / below*, *Insert a column…*, *Rename this column…* (or double click its header), *Sort by this column*, *Fill down* (Ctrl+D), and *Add a calculated column…* with a formula that uses the letters of the columns as in Excel (`C/C.max()*100`, `(B-A)/2`, `log10(C)`). Each is one step of *Undo edit*; the graphs of the file follow; the file on the disk is never changed. It is not all of Excel: no cell formulas that recalculate, no formats, no charts - for those, *Export data…* and open the file in Excel.
* **Whatever is labelled on a graph can be read in the Workbook.** Thermal runs and infrared spectra have their Peaks sheet and peak columns (5.58.1); an XRD pattern now has the Peaks sheet too - the table of peaks its graph found and named (positions, d-spacings, phases), to read and export.
* **Send to PowerPoint / Word goes straight into the open program.** On Windows the graph is put on a new slide at the end of the presentation you have open, or at the cursor of the document you have open (a new one if none is open), as a picture - no file to open first. If PowerPoint or Word cannot be reached, the file is written and opened as before. *The direct way could only be tested here with stand-ins for the two programs.*
* **A figure of two graphs: each graph for itself.** *Select range* could only be dragged in the first graph, what was worked out from a selection (integration) always used the first graph, and *Reset axes* reset both. Now a range can be dragged in either graph and belongs to that graph (the line says "graph (b) of 2"), the calculation uses its curves, and *Reset axes* brings back the graph you last worked in - a second Reset brings back all.
* **Analysis: Delete on the list of files**, and *Remove* takes a file out of the app's lists even when its graphs are in Workspace (they leave it too; Undo there brings them back). With no file highlighted, the ticked ones are removed.

## 5.58.1

* **Fixed: Send to PowerPoint / Send to Word did nothing in an app that had been updated.** The two empty Office files the export fills were in a folder of their own, and the app's updater installs only the folders it knows - so an updated app did not have them, the export could not write, and the only sign was a line in the status bar. They are now inside a folder the updater installs; a failure is shown in a message box that says what is wrong; and the first time a file is written, a note says where it is (in case PowerPoint or Word does not come to the front). A test now checks that no data file of the program lies outside what the updater installs.
* **Analysis: the buttons work on what you see.** *Combine into one figure…*, *Open all in editor*, *Draw all in Origin like this* and *Export all…* were grey - and so seemed to do nothing - until previews had been ticked "keep" one by one. They now work on the kept previews or, with none (for Combine: fewer than two) kept, on all previews on show; Combine shows the combined figure at once, with *Draw in Origin like this* and *Export…* on it. With nothing to work on they say what is needed. New button **Edit data in Workbook** takes the ticked files there.
* **Delete and hide in the Workbook.** The table could only be typed in. Now: **Delete** empties the selected cells; with whole rows or whole columns selected (click their numbers or headers) it deletes them from the working copy. A right click on a cell, a row number or a column header offers the same, and *Hide: leave it out of the graphs*, *Leave out in all files*, *Undo edit*, *Redo edit*. Every such change is one step of **Undo edit**. Only the working copy changes; the file on the disk never does.
* **X and Y on the table itself, and the graph that follows.** Right click a column header: *Use as X*, *Use as Y*, *Move column left / right*. The headers show which column is `[X]` and which `[Y]`. Under the table the app says which graph it suggests for the data as chosen (for a file of a series: the graph of the whole series) and why; *Create this graph* draws it, *Other graphs…* shows all that fit.
* **The Workbook is filled from Start here.** Clicking *Workbook* in the top bar showed an empty page, or an old list, unless you came through *Edit and arrange in Workbook*: it now always lists the files ticked on Start here - or, with nothing ticked, the file highlighted there.
* **Delete on a file of the Workbook list** (or right click ▸ *Remove from the list*) takes the file off the list - several at once with Ctrl / Shift-click. **Delete on a column of the Columns list** leaves it out of the graphs.
* **What is not ticked on Start here is nowhere else in the app.** On leaving Start here, Analysis and the Workbook list only the ticked files, and the graphs of files that are listed there but not ticked leave Workspace (the status line says so; Ctrl+Z brings them back). Ticked files that are not read yet are read when you go to Workspace. Taking a file off the Workbook list unticks it on Start here. A file added on another page starts ticked.
* **Several graphs removed at once in Your graphs.** Ctrl / Shift-click and Delete already removed all highlighted graphs, but a right click dropped the highlight to one row first, so *Remove* took one graph: the highlight is kept now. The menu offers *Remove the N highlighted graphs*, *Remove the N ticked graphs* (**Shift+Delete**) and *Remove all N graphs of this file*. (The list also opened two menus one after the other; it has one.)
* **The names of peaks beside the numbers.** The working copy of a thermal run or an infrared spectrum has a column *Peak (may be)* / *Band (may be)*: empty, except in the row of each peak, where its label stands, and beside it a column *What it may be* with the meaning in full - so the names and what they stand for are in the table and in every export without opening anything. A **Peaks (n)…** button beside the Sheet list opens the table of peaks and goes back to the data. A label you type there is the one shown in the column.
* **Merging gives one Excel workbook.** *Merge selected files…* (Side by side) now writes an `.xlsx`: a sheet for every file with its own X and Y columns (and DTG and peak names), and a last sheet *All side by side* with every file's columns next to each other, each labelled with its file. Graphs are drawn from it file by file (and the figure of all of them); the side-by-side sheet is not drawn a second time. It wrote a CSV with only the side-by-side table before.
* **Thermal and infrared graphs, tidied for publication.**
  * The temperature axis ends on round values (0 - 1000 °C) instead of the first and last reading.
  * The dip of the DTG in the first degrees of a run - the balance settling - is no longer an event: no label with a slanted line at the left edge, no row in the results.
  * In a figure of several thermal runs the DTG panel has the same unit and curve as the graph of one run (% per minute when the file has a time column; it was % per °C there).
  * An infrared graph no longer labels the CO₂ doublet of the air (2280 - 2400 cm⁻¹) or noise at the very end of the measured range; the record of the graph says what was left out.
  Because these change how the app's own example files are drawn, the update window will say that this version draws some examples differently and ask before installing: that is these changes.

## 5.58.0

* **Samples that belong together are drawn together.** When the files you tick on Start here are the same kind of measurement and their names are built the same way - `10-900-AB`, `10-950-AB`, `20-900-AB`; `Ref_rep1`, `Ref_rep2`; `S1`, `S2` - the app takes them for one series: it chooses *Combine selected files in one graph* by itself, lists the graphs that show several samples first (the stacked one before the others), and says why ("the names share ... and differ in ..."). A ticked file of another kind is left out of it and named. Choosing *Separate graph for each file* is kept for those files.
* **A thermal run is looked at as mass against temperature.** A file exported as temperature, time, mass, DSC was shown as time against temperature, because that is the order of its columns. X and Y now follow what the columns are (also for DSC, calorimetry and infrared spectra) until you choose them yourself.
* **Workbook: the DTG curve is there by itself.** The working copy of a thermal run gets a column `DTG (%/°C)` (the calculation of the TGA page, 15 °C window), so it is in the table and in *Export data…*. It is listed under Columns as "worked out by the app" and is not used in graphs - they work out their own - unless you tick it.
* **Workbook: files of a series side by side, made by the app.** The last entry of *Selected files* is a table of all files of a series next to each other: for each its X column, its Y columns and its DTG curve, named `column [file]`. Every file keeps its own X values; nothing is interpolated. *Export data…* saves it as CSV or Excel.
* **Fixed: "Merge selected files…" seemed to do nothing.** With files that were in no project it asked for a name and then only wrote "Create or select a project" in the status line. It merges them now; the new dataset is selected in the list, named after the series, and listed in Your graphs and on Start here. A third way to merge, *Side by side*, is the first choice; a file merged that way is read back as one table per sample, so Workspace draws every sample of it (and the figure of all of them), not only the first.
* **Workbook: leave a column out in all files.** *Use these column choices for all files* applies the ticks of the columns on show to every file of the list that has columns of those names; right click on a column: *Leave out in all files* / *Use in all files*. A column left out is not carried to Workspace and does not count for the graphs that are offered and made. The files and their working copies keep it.
* **New: the peaks of a thermal run and the bands of an infrared spectrum, with what each may be.** Such a file has a last sheet in the Workbook, *Peaks — found by the app*: for a thermal run every step of mass loss (DTG peak, from - to, loss in %), for a spectrum every band (position, value), each with **May be** - the usual event or bond at that position, most likely first - the other possibilities, and a **Label** of your own, started with the short name and a question mark. The names are possibilities from where the peak lies (references of cement and mineral thermal analysis and infrared spectroscopy), not findings: check them. Tick *Draw these labels on the graph* and the TGA or FTIR graphs of that file write your labels beside the positions; clear a Label to leave a peak unnamed. Off, the graphs are exactly as before. *Export data…* as Excel writes the peaks on a second sheet. The results tables of TGA and FTIR graphs in Workspace have the same *May be* and *Other possibilities* columns.

## 5.57.2

* **Fixed: a figure of a workbook (and "Draw in Origin like this") drawn in Origin did not look like the figure in the app** - texts missing, the title as a jumble at the top of the page, columns covering each other, letters and lines far too small, no legend, an empty sixth panel. Seen on Origin 2018 and traced command by command:
  * *Texts were lost.* A text is made with `label -a x y`; where x or y was negative (the first column of a bar chart stands at -0.6) Origin read the number as an option, made a text out of the rest of the command and gave it no name, so the text and everything said about it afterwards was lost. Every text is now made at a position that is not negative and then moved to its place - the way the app's ordinary graphs have always done it.
  * *Axis titles were missing on every panel but the first.* A layer added to a page has no title objects of its own. The axis titles of every layer are now sent as texts, at the place they have in the figure.
  * *Letters and lines came out at a half or a third of their size.* Origin makes everything in a layer smaller in proportion to the layer's width. Every size sent to a layer (letters, numbers on the axes, line weights, symbols, the frame) is now multiplied by 62 / (the layer's width in % of the page), measured on your two figures, so it comes out at the size of the app's figure. This is also what brings the line weights and letter sizes of the app's figure into Origin.
  * *No legend, and an empty panel with axes from 0 to 1.* A cell of a figure that only carries the legend was sent as a layer. It makes no layer now; every legend entry is sent as a text with the key of its own curve (`\l(n)`), attached to the panel that holds those curves. The legend of a whole figure (under its panels) is sent the same way; columns are matched by colour and hatch, points by their symbol.
  * *Names of two lines showed the letter n* (a name written over "(0 %)" came out as "…n(0 %)"): a text of several lines is sent line by line.
  * *Columns in groups covered each other.* Origin makes a column 80 % as wide as the smallest step between the x values of its own data. Grouped columns now get the width they have in the figure.
  * *Points on columns were hidden behind them, and blue.* Columns are plotted first, points after them, in the colour of their fill.
  * *Origin's own tick steps* (5, 10, 15 where the figure has 20, 40, 60): the steps of the figure are sent.
  * The look of every axis is sent once more at the very end, because a layer that Origin fills the second way gets its standard axes back.
  Still to check on your computer: hatched columns (Origin shows them plain if it refuses the pattern command; the note says where to set it) and the frame around the panels after the first. If something is still off, the file `origin_commands_log.txt` beside the Origin project names every command Origin refused.
* **New: Export ▸ Send to PowerPoint, Send to Word.** The graph on show goes into a new presentation as a picture filling one slide, or into a new document as a 600 dpi picture at its printed size. With two or more graphs ticked, each gets its own slide or picture. The file is written to the results folder and opened; an earlier one is never written over. Also in the Save menu and on the right-click menu of the graph. Nothing has to be installed for it.
* **Fixed: Delete (and right-click ▸ Remove) on a ★ combined figure made by the app did nothing but show a message.** It now takes the figure off the list - its graphs stay - and it stays away when graphs are added or grouped again. Undo brings it back, a saved session remembers it, and choosing from the Group list makes the app's figures anew.
* **New: "Phase tick rows" on the Panel bar** of a figure with fit panels, beside *Zoomed part*, *Observed as dots* and *Difference row*: the rows of small marks under a fit (one row per phase, a mark at each of its reflections) on or off, for one panel. Greyed out, with the reason, for a panel that has none. Also on the right-click menu of the panel.

## 5.57.1

* **Fixed: figures of a workbook, and "Draw in Origin like this", came out empty in Origin** - the layers were there, at Origin's default 0-10 axes, with no curves, no titles and a long message log. For these figures the app imported the data of each curve and plotted it straight away; importing a workbook makes it Origin's active window, so the plot command and every axis, text and legend command after it went to the workbook and were refused. They are now sent in the order the app's ordinary graphs have always used: every workbook first, then the graph window, its layers, and then curves, axes and texts layer by layer - and Origin is asked afterwards how many curves each layer holds, with an empty one filled a second way. The 122 Origin scripts that come with the templates are written in that order too. (Checked by following which window is active through every command: 224 commands went to the wrong window before, none now. A run in Origin itself was not possible here.)
* **Fixed: the window stopped for seconds, again and again, with a workbook of figures.** Each of its figures re-read the whole workbook from the disk every time it was drawn - on opening, and at every change of a zoom, a panel option or a group (about 8 s each for a 3 MB, 50-sheet workbook). A workbook is now read once and kept until the file changes: and a figure is drawn once when it changes instead of twice, with its picture kept for the next click. Measured on a project of thirteen files with such a workbook, same computer, before and after: clicking one of its figures 5-6 s -> under half a second; switching one panel's zoom, or Undo, 10 s -> 1 s; opening Calculations 10 s -> at once; adding the files 68 s -> 30 s (in the background).
* **Fixed: clicking a large file in the project list stopped the window while it was read.** A large file is now read in the background; the page says "Reading this file…" and shows it when it is there.
* **Fixed: closing the app while files were still being read** made it wait up to half a minute and could end in a crash ("QThread: Destroyed while thread is still running"). Reading now stops at the next file, and a file in the middle of being read no longer holds the app open.
* **Fixed: a file added on Start here without a project could not be seen.** It went into a two-row list in the middle column, with nothing highlighted, while the Projects column stayed empty. Files that are in no project are now listed on the left like everything else, under "Files not in a project": ticked, the one on show highlighted, removable, and they can be dragged onto a project to join it.
* **Every graph of a fit or refinement: the observed curve is a solid line, the calculated curve is dashed over it** - two lines of different kinds, so both are seen where they lie on each other. This is now the look of the figures of a workbook (they had the observed curve as dots), of the app's own "Fit: observed, calculated, difference" view and its zoomed part, of several fits as panels or stacked and of Sample pages, of the Analysis templates "Rietveld fit" and "Rietveld grid", of the deconvolution template (observed and fit) and of the workbook graph type G03. The legend shows the two kinds, and Origin gets the calculated curve dashed as well. Dots for the measured points are still there when you want them: "Observed as dots" in the Panel bar (or the right-click menu of a panel) for a figure of a workbook, "Show markers on measured data" in *Edit this graph…* for a template graph - the calculated curve is then a solid line, as before.
* **New: "Add folder…"** on Start here, beside "Add files" (also File ▸ *Add a folder of data files…*, the right-click menu of the project list, and dropping a folder onto the page). Every data file in the folder comes in, its sub-folders too, under a folder of the same name with the sub-folders as folders inside it - so the project list shows the files the way they are on the disk. It goes into the project (or folder) you have selected; with no project selected, a project named after the folder is made for it. Hidden folders, Office lock files and files that are not data are left out; adding the same folder again makes nothing double; a folder with no data files says so. The files are only read and stay where they are.
* A folder dropped on the page used to come in as a flat list of its files; it now keeps its sub-folders.
* "New folder" (an empty folder of your own inside a project) is now "New empty folder…" in the ••• menu and the right-click menu, so that it is not mistaken for adding a folder from the disk.

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

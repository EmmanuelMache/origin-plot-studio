VERSION 5.52.3  -  CLICK TO TICK, PREVIEW AT ONCE, TEMPLATES IN CLASSES
  Graph gallery > Templates: a click on a template, a file or a style ticks it (a tick before the name and a blue frame);
  click again to untick; Shift+click ticks a range; Ctrl+A ticks all shown. A ticked template is drawn at once - from
  your ticked files, or as an example when no file is ticked. The tree beside the pictures classes the templates by
  instrument / technique and by graph type; the numbers are "can be drawn now" of "in the catalogue" (118 of 331).

VERSION 5.52.2  -  ONE GRAPH GALLERY
  The templates are inside Graph gallery (no separate Templates section in the top bar). A switch at the top of the
  gallery shows "Templates" or "Workbook graph types (26)"; Graph gallery opens where you left it.

VERSION 5.52.0  -  TEMPLATES (MULTIPLE SELECTION), THE SAME GRAPH IN ORIGIN, SESSION BASICS, TGA / DTG MODULE
  TEMPLATES (new section, between Graph gallery and Assistant)
    Graph = template x style x your data. Six panels you can move, float, close and reopen: Files, Columns, Templates,
    Styles, Previews, Variants.
    - Multiple selection, the same in every list: click = one, Ctrl+click = add / remove, Shift+click = a range,
      Ctrl+A = all; a tick box on every row; "Select all in this category", "Clear selection"; the count on top says
      e.g. "3 files · 4 templates · 2 styles selected -> 24 previews".
    - Previews: every ticked combination is drawn from YOUR files. Double click a tile to enlarge and edit it; tick the
      ones to keep. Drawing many previews shows a progress bar and can be cancelled.
    - Columns: the first ticked numeric column is x, the others are series; untick or drag to reorder. The choice is
      remembered for files with the same headers. Nothing is written to your files.
    - Templates: 118 graph types can be drawn; the other rows of the catalogue are listed as "coming". Search, field
      (graph families / domain packs), source, and "Works with the ticked files" (best fit first, top 3 marked).
    - Styles: house style, Elsevier, Nature, Springer/RILEM, RSC, ACS, slides, greyscale, colour-blind safe. Export
      warns when text or lines fall below the minimum of the chosen preset.
    - Batch actions on the kept previews: Open all in editor; Draw all in Origin like this (Ctrl+Shift+O); Export all
      (Ctrl+Shift+E: PNG, TIFF-LZW, PDF, SVG, EPS, JPG at single / 1.5 / double column or your own width); data of all
      in one Excel workbook (one sheet per file + the list of graphs); apply one style to all; Combine into one figure
      (Ctrl+Shift+G: 1x2, 2x2, 2x3, stacked, your own grid; panel letters in the format of the style).
    - Draw in Origin like this: the drawn figure is rebuilt in Origin - one layer per panel or inset at the same place on
      a page of the same size, the same ranges, scales and reversals, curves with colour, width, dash and marker, bars,
      shaded zones, texts, legend, sizes in points; your data in worksheets; saved as {sample}_{template}.opju with the
      complete LabTalk script (.ogs) beside it. What Origin cannot match is said in one line (opstudio/origin/DIFFERENCES.md).
      More > "Build Origin templates (.otpu)" stores the Origin graph templates on a computer with Origin.
    - My templates: Save as my template (JSON + preview + Origin script in your private folder), export / import .opst.
  COMMAND AREA AND SESSIONS
    - File is the left-most command, then Save, Undo, Redo (one Undo / Redo for the whole app), then the sections.
    - Ctrl+Q: command search - type a part of a command's name and press Enter. (Exit: Alt+F4 or File > Exit.)
    - File > Clear / Start afresh: Clear graph, Clear all graphs, Remove ticked graphs, Start afresh (keep settings and
      layout, or reset the layout), Reset layout, Recover last session. Each asks with a one-line summary and can be
      undone with Ctrl+Z. File > Save (Ctrl+S, to the session file in use), Save session as (Ctrl+Shift+S), Recent sessions.
    - The session is saved by itself every 5 minutes ("autosave_min" in the settings) and when the app closes; after a
      crash the app offers to bring it back.
    - Every button has a tooltip: name, shortcut, what it does, and what enables it when it is disabled.
  TGA / DTG MODULE (Tools > TGA / DTG analysis)
    TG and DTG in one graph (DTG at its natural sign), DTG peaks with extrapolated onset and endset, zones you can drag
    on the graph (add, split, merge, delete), mass loss per zone by the stepwise and the tangent method side by side,
    Ca(OH)2 / CaCO3 / Mg(OH)2 from zones YOU confirmed, ignited or binder basis, bound water, replicates.
    Zone names are suggestions with "?" until you confirm them; unconfirmed names are never exported. Confirmed names are
    remembered per material. Export results -> Excel (Data, Peaks, Zones, Summary, Chart), Copy table, Draw in Origin.

VERSION 5.51.0  -  YOUR PRIVATE FOLDER, NEUTRAL EXAMPLES, THE TEMPLATE ENGINE
  - Your private folder: %APPDATA%\OriginPlotStudio\my_templates (or the folder named by OPS_PRIVATE_DIR). The app reads from
    it at start: phase files (*.csv), your style presets (styles\*.json), your graph templates (templates\*.json) and your
    defaults (defaults.json). Nothing in it is published or sent anywhere, and the updater never touches it.
  - The published app holds no data, names or results of any user: examples and previews use neutral names
    (Sample A-F, Series 1-3, Additive (wt.%)). A small starter list of common minerals replaces the built-in phase
    library; your own phase files in the private folder come first.
  - The section with the 26 graph types is now called "Graph gallery". Sessions saved by older versions open as before.
  - New package opstudio: Graph = Template x Style x Data. 104 templates (opstudio.template/1), 9 style presets
    (opstudio.style/1: house style, Elsevier, Nature, Springer/RILEM, RSC, ACS, slides, greyscale, colour-blind safe),
    export at the journal widths of the style with a warning when text or lines fall below the preset's minimum.

VERSION 5.50.0  -  DRAG LABELS IN THE GRAPH
  Press on a peak label - or on the name of a curve in a stacked figure - and drag it to where you want it (with Zoom, Pan and Select
  range switched off). It stays there: in the graph, the publication files and Origin, and in a saved session; its pointer still goes
  to its peak. Ctrl+Z undoes it; right click › Put this label back, or Put all moved labels back. A click without dragging still
  chooses the label for font, size and colour. Labels inside the zoomed part, and the zoomed part itself (drag it as before), are
  not moved this way. No number of your data is changed.

VERSION 5.49.2  -  RIGHT CLICK ON A GRAPH TO EDIT IT
  Right click anywhere on the graph (or on it in Your graphs): ✎ Edit this graph… opens one window, as Plot Details in Origin:
    Titles   graph title, x and y axis titles (select letters and press x² or x₂), hide the title;
    Text     font, size, weight, italic and colour of the title, axis titles, axis numbers, labels or legend;
    Axes     x and y range, axis colour and weight;      Curves   the colour and weight of each curve (or all);
    Layout   legend, a ready-made look, and for XRD the zoomed part (on / off / range) and pattern or fit.
  Apply or OK is one step that Ctrl+Z undoes; Cancel changes nothing; 'Back to the app's look' undoes all your formatting.
  The menu also has Title…, x / y axis title…, Look, Legend, Axis range…, Undo, Redo straight away; on a text, a curve or the axes it
  still offers the quick changes for that part (bigger, bold, colour, thicker …).

VERSION 5.49.0  -  ALWAYS STACKED AND OVERLAID, THERMAL PAGES, A PHOTO OF A SKETCH
  Several files of one kind (TGA, DSC, calorimetry, FTIR, XRD, Raman, NMR, particle size): with 'Decide for me' (the default) the app
  makes both figures - stacked with an offset AND overlaid on common axes - and keeps every curve as its own graph as well.
  Thermal analysis files that hold TG and DSC together (NETZSCH .ngb-ds3 / .ngb-ss3, STA exports with mass and DSC columns):
    one page per sample        (a) TG with DTG (steps labelled), (b) DSC (peaks labelled), on the same temperature axis;
    a comparison of all samples (a) the TG (and DTG) curves overlaid, (b) the DSC curves overlaid.
  They are at the top of Your graphs (▣ Thermal_<sample>, ▣ Thermal_comparison), ready to edit, export or draw in Origin.
  Sketch a design › Read a photo of a sketch…: a photo or scan of a sketch on paper is read by fixed rules (no AI; nothing leaves your
  computer): the pen is told from the paper and its shading, a photo taken a little crooked is straightened, every frame (a drawn box
  or just two axes) becomes a graph, inside it a box is the zoomed part (a very small one in a corner, the legend), and the lines are
  curves - one above the other: stacked, crossing: overlaid. The shapes appear on the pad over the photo: move, add or delete them,
  type the titles (hand-writing is not read), then 'Lay out the ticked graphs like this'.

VERSION 5.48.2  -  A NEW ICON
  The icon in the colours of the window: a navy tile with a white spectrum, the blue axis and an orange dot (Origin). It is on the
  shortcuts, the taskbar, the window and the top bar. The start screen and Setup use the same colours. (The Desktop shortcut takes the
  new icon at once or after Windows refreshes its icon cache; running Setup.bat again makes it immediate.)

VERSION 5.48.1  -  START FIX, STOP BESIDE RUN, REPAIR WHEN THE APP CANNOT START
  5.48.0 did not start when the settings held an older entry called 'layout' (from an earlier version): the arrangement of the panels
  is now kept under its own name, and a damaged or older arrangement is simply not used - the app starts with the default one. The panel
  arrangement can never keep the app from starting.
  If the app ever cannot start, the message offers Repair: the newest version is downloaded from the app's GitHub page and installed over
  this one (the program is backed up first, in your home folder under "Origin Plot Studio program backups"; settings and sessions are
  kept), then the app starts again.
  Analysis and Graph gallery: ■ Stop sits beside Run (red, greyed while nothing runs). While a run is going, press it: the run ends at
  its next step, nothing of it comes to Your graphs, and the files it had written are removed again. The message under Run says so.
  The next run works as before.

VERSION 5.48.0  -  A NEW LAYOUT: ONE TOP BAR, PANELS EVERYWHERE, BROWSER / SETUP / PREVIEW, GALLERIES
  One top bar (navy): Origin Plot Studio, the sections Workspace · Analysis · Graph gallery · Assistant · Settings, Find a graph, and the
  menus File (the only File menu: new, open, save, add files, save and export, refresh, results folder …), View (panels, Reset layout,
  formatting ribbon), Tools (draw, analyses, XRD tools), Help, and Add files. The old menu bar and side bar are gone; their keyboard
  shortcuts work as before. The formatting ribbon (Home, Insert, Draw, Design, Layout, Axes, Lines) shows in Workspace only; on a small
  screen it starts folded to its tabs.
  Panels everywhere. Workspace: Your graphs, Graph, Data, Results, Details, Graph settings. Analysis: Analyses, Setup, Preview and
  results, Gallery. Graph gallery: Graph types, Gallery, Setup, Preview and results. Each panel: drag it by its header (beside, under, on
  top of another one as a tab, or out as a window of its own), resize it at its edges, close it (View › Panels brings it back). Closing a
  panel never loses files, settings or results. The arrangement is kept for the next start; View › Reset layout puts everything back.
  When the window changes size the graph (the preview, the gallery) takes the space; side panels keep the width you gave them.
  Workspace: the graph keeps its proportions and always fits; Data, Results and Details are tabs beside it (drag one out to see both).
  Export ▾ and the one orange action, Draw in Origin, sit above the graph. Graph settings fold in sections (kept). Long file names are
  shortened in the middle, the whole name and path on hover.
  Analysis and Graph gallery: the workflow above (Choose › Files › Inspect › Configure › Preview › Workspace › Export). A click on an
  entry - or a category, or a picture in the gallery - opens its setup at once. Setup shows the files it works on with their columns
  (Add files…, Choose in Workspace), the settings, the Run button and its message beside it (red: failed, amber: something to do first,
  green: done). Preview and results: your own data as the app draws it, its data table, the result of a run (Open in Workspace to edit
  and export it), the result tables; with no file yet, an illustration that says it is one. Your settings of an entry stay when you go
  to another one and come back. The gallery: a picture of each of the 26 gallery graph types (of the chosen category) and of each kind
  of analysis; a click opens it; the chosen one is marked.
  Colours: navy #17324D, blue #2563EB for the main action and selection, orange #B4532A only for Origin, teal #0F766E for previews,
  green / amber / red with words for done / attention / failed. The colours of your graphs are not touched.
  XRD: a fit file now opens as the measured pattern with its peak labels (and the zoomed part) - the basic graph. Beside Zoom / Pan:
  'Pattern with labels' or 'Fit: observed, calculated, difference'; for every fit: Settings › XRD › Fit files open as. Figures of
  several fits and the sample pages still use the whole fit.
  Checked at 1366×768, 1600×900, 1920×1080 and at 125 % and 150 % display scaling.

VERSION 5.47.0  -  THE RIBBON AS IN WORD, EDITING ON THE GRAPH, XRD MIDDLE PART AND ZOOM ON THE GRAPH
  The ribbon sits in the top bar (dark blue), where the name and version were (the version is in Help › About and in the tooltip of the
  name): 💾 ↶ ↷ (save, undo, redo), then the tabs File, Home, Insert, Draw, Design, Layout, Axes, Lines; the buttons of the top bar
  stay on the right. Each tab has groups of large and small buttons with the group's name underneath, as in Word:
    Home     Clipboard (Copy, Save picture, Reset look); Font (font, size, A↑ A↓, B, I, x₂, x², colour, clear; ↘ the whole font dialog);
             Text (what to change, type a title); Editing (Undo, Redo).
    Insert   Sketch a design, Add files, Panel figure.   Draw   Draw freely (pen, finger, mouse); Zoom, Pan, Select range, Reset axes.
    Design   Looks, as Word's Styles: App look, Black & white, Bold paper, Light, Slides, Serif, Navy; page orientation, title, legend.
    Layout   Stack, Overlay, Panels, Decide for me, Panel figure; the graph type.   Axes / Lines as before.
  ⌃ folds the ribbon to its tabs (a click on a tab opens it), Ctrl+F1 hides it; ⚙ › Customise the ribbon… chooses the groups shown.
  Editing on the graph itself
    Click a text, a curve or the axes: the ribbon opens on it (Home, Lines or Axes), with a thin frame round what you chose.
    Double click a title or an axis title: type it again (^{..} superscript, _{..} subscript). Double click elsewhere: reset the axes.
    Right click: for a text - edit, bigger, smaller, bold, italic, colour, back to the app's look; for a curve - colour, thicker,
    thinner; for the axes - colour, thicker, range; for XRD - zoomed part on / off.  Drag the zoomed part to where you want it.
  XRD, beside Zoom / Pan / Select range (shown for XRD graphs only; the zoom switch is not in the ribbon)
    Zoomed part  on / off, and its 2θ range (Enter).
    Middle part  of a fit, between the fit and the difference curve: Bragg tick rows; Peaks with labels (each reflection of the linked
                 peak list as a line of its calculated height, coloured by phase, the strong ones labelled B, C, CH …); both; nothing.
  Stack the graphs you select in Your graphs (click, Ctrl + click, Shift + click) - they do not have to be ticked: the stacked
  figure is drawn and shown at once; Draw in Origin does the final work.

VERSION 5.46.0  -  XRD ZOOM ON OR OFF; DRAW THE SKETCH WITH A PEN, A FINGER OR THE MOUSE
  The zoomed part (inset) of XRD graphs, on or off
    For every graph: Settings > XRD > Zoomed part (inset):
      Automatic on sample pages        fits and sample pages get the zoom the app chooses (as before)
      On every XRD pattern and fit     single patterns get it too (the 10° window with the most diffracted intensity)
      No inset                          no zoom anywhere
      or type a 2θ range, e.g. 27-37   that range on every graph whose axis holds it
    For one graph (or the ticked ones): ribbon Graph > Zoom: as in Settings / on / off, and a range (Enter);
      Analysis > XRD > Zoomed part (inset): on or off - for the ticked graphs. Undo with Ctrl+Z.
  Sketch a design: draw freely (✎ Draw freely, the tool the pad starts with)
    With a pen, your finger on a touch screen, or the mouse. The strokes are recognised by fixed rules: a big closed shape is a
    graph frame, a closed shape inside a frame is the zoomed part (a very small one, in a corner, is the legend), a line inside a frame
    is a curve. A pen's pressure sets the line width. ⌫ Erase removes what you touch; Ctrl+Z takes back the last stroke. Titles are
    still typed with T (handwriting is not read). The exact tools (▭ Graph, ◳ Zoom, ☰ Legend, 〰 Curve) stay.

VERSION 5.45.0  -  A RIBBON AT THE TOP (AS IN WORD) AND SKETCH A DESIGN
  The ribbon (above the graph): File, Home, Graph, Axes, Lines, Insert. It works on the graph on show; every change is kept with the
  graph (and in a saved session), drawn the same way in the preview, the publication files and Origin, and can be undone.
    File      New, Add files, Open, Save (session), Save picture as, Copy, Draw ticked / all in Origin, Results folder, Undo, Redo,
              Reset look (back to how the app draws it).
    Home      Text: Graph title, Axis titles (x or y), Axis numbers, Peak labels and other text, Legend - or click on the text in the graph.
              Type the title or an axis title (Enter); X² makes the selected letters superscript, X₂ subscript (written ^{..} and _{..},
              e.g. "S_{BET} (m^{2} g^{-1})"; shown as real superscript and subscript, also in Origin). Font, size (pt), B (Ctrl+B),
              I (Ctrl+Shift+I), text colour, Clear.
    Graph     Change the kind of graph, title shown or hidden, legend automatic / on / off; put the ticked graphs together (Stack,
              Overlay, Panels, Decide for me, Panel figure).
    Axes      x and y range (Enter; Automatic for the app's ranges), axis colour (ticks included) and weight.
    Lines     each curve (or all curves): colour and weight; Automatic for the app's.
    Insert    Sketch a design…
  Undo Ctrl+Z, Redo Ctrl+Y. No number of your data is changed by any of this.
  Sketch a design (Insert > Sketch a design…)
    Draw how the figure should look: a box for each graph (▭ Graph); a small box inside a graph for the zoomed part (◳ Zoom) or the
    legend (☰ Legend); the curves you expect (〰 Curve: one above the other = stacked, crossing = overlaid); text (T) above a box is its
    title, below it the x axis title, left of it the y axis title, inside it a note. Landscape or portrait page. A photo of a sketch on
    paper can be put behind the pad and traced. Right of the pad the app says what it reads, before anything is changed; then 'Lay out the
    ticked graphs like this':
      one box             the graph(s) with your titles, the zoom where you drew it (the range you type, or the busiest part of the
                          data), the legend in that corner, your notes;
      one box, 2+ curves  the ticked graphs stacked or overlaid in one figure;
      boxes one above the other, touching   panels sharing the x axis;   a grid of boxes   a panel figure (a), (b) … rows x columns.
    The sketch is read by fixed rules, never by an AI.

VERSION 5.44.0  -  HIGHSCORE FITS AND PEAK LISTS, BACKGROUND AT THE SCAN ENDS, SIZE AND LOOK, A MOVING BAR
  HighScore (and other Rietveld) exports, CSV or TXT
    The fit (No., Pos., Iobs, Icalc, Iback ...) and the peak list (Assignment, h k l, Height ...) of a sample are put together: by the
    sample name, or - when the names differ - because the listed peaks sit on the peaks of the pattern (the agreement is written in
    Details). A shifted second sample gets its own list, not the first one.
    The single fit: observed and calculated, the difference below, the peaks labelled from the peak list, and a zoomed part chosen by
    the app (the 10° window with the most diffracted intensity; type your own range under Settings > Inset, or 'No inset').
    One page per sample: (a) the pattern with its peaks labelled, (b) the fit with the difference and the zoom.
    A phase whose every reflection has a calculated height of 0 (e.g. alite with scale factor 0) is named in the record as not drawn.
  Analysis > XRD and Graph gallery > XRD: drawing first
    Decide for me (up to 4 fits one panel each with difference and zoom, more than 4 stacked; patterns stacked), Sample pages, Fits as
    panels, Fits without the fitted curve (stacked or overlaid), XRD patterns stacked / overlaid, Which peak list goes with which pattern
    (a table with the reason and the phases not drawn). The Scan Generator, Peak correct and the phase library are in the group after it,
    'XRD: correct and generate scans'.
  XRD Scan Generator: the template's background is no longer bent at the start and end of the scan
    The background was smoothed with the ends padded flat, so a background that falls steeply at low angle (or rises at the end) was
    cut off there, and 'Keep the template's background' copied that bend into every generated scan. It is now followed by a local fit
    in log counts on the background points only, one-sided at the ends; checked on falling, rising and steep low-angle backgrounds at
    1 300 to 6 500 points: within a few % at the first and last degree (it was up to 35-67 %).
  Graph settings > Size and look
    Orientation (landscape / portrait), Letters (80-150 %), Font weight (bold / normal), Text colour, Line colour (the curves the app draws
    black; coloured curves and labels keep their colours; or type #rrggbb). Used in the preview, the publication files and Origin. The
    Curve (pt) and Axis (pt) weights now also show in the preview.
  A moving bar at the bottom right while the app reads files, draws in Origin, saves or runs an entry of Analysis / Graph gallery; it
  fills up graph by graph ("3 of 10 graphs").
  Assistant: "graphs of PSD cements" (without "show me") shows the app's own pictures of that kind, also when an AI is linked (the AI
  answers after them). "Show in Workspace" under an example picture adds that graph to Your graphs, in the style of the picture, and opens it.

VERSION 5.43.0  -  XRD SCAN GENERATOR KEEPS THE TEMPLATE'S BACKGROUND
  Generation settings > Background
    Keep the template's background (default)   the generated scans have exactly the background of your template - its shape and its
                 level relative to the peaks - on their own 2θ points; only the counting (Poisson) noise is new.
    Small variations   the level ±15 % and a slight tilt, no added hump.
    Vary it      level, tilt and a random amorphous hump between 15 and 45° 2θ (what the generator always did before).
  The manifest of each run records it (bg_scale 1.000, hump 0 when kept). Peak correct never changes the background shape: it counts
  the whole measured scan longer or shorter.

VERSION 5.42.0  -  XRD SCAN GENERATOR: MOUSE SELECTION, RIGHT-CLICK MENUS, WHERE SCANS ARE SAVED
  Peak correct
    Left click on a peak of the graph: tick / untick it (the mode 'The ticked peaks to the heights I give' is chosen for you).
    Shift + drag: tick every peak in that 2θ range.
    Right click: tick / untick the peak, tick only this peak, set its target (counts), zoom to the peak, tick all / none / the peaks in
    view, reset the view, copy or save the picture.
    'Save corrected scans in' (Browse, Open): where 'Correct peaks' writes the corrected scans and their provenance files; empty = the
    output folder of the generator.
  Generated scans
    Left click on a curve: select that scan (drawn thicker, selected in the list).
    Right click: save this scan as…, open its folder, tick only this scan, untick it, use it in Origin Plot Studio, save the ticked
    scans to…, tick all / none, overlay the template, normalise, reset the view, copy or save the picture.
    Buttons: 'Save the ticked scans to…' (Ctrl+S) and 'Save the selected scan as…'.
  Lists (generated scans, corrected versions, Files): right click - save as / save a copy as, open the file, open its folder, copy the
  path, remove from the list (the file stays), save the ticked to a folder.
  Saving copies a scan byte for byte, with its provenance file when it has one; an existing name is never overwritten (_2, _3 ...).
  The generator itself (its settings, scans and corrections) is unchanged.

VERSION 5.41.0  -  PARTICLE SIZE AS IT IS USUALLY DRAWN; PICTURES IN THE ASSISTANT
  Particle size (PSD)
    Drawn the usual way: one graph, logarithmic size axis, the distribution (volume %) on the left axis, the cumulative passing (%) on
    the right axis, D10, D50 and D90 marked - in the preview, in Origin and in the publication files. Other styles: two panels
    (distribution above, cumulative below), cumulative only, distribution only - Settings > Particle size for all, or per graph in
    Analysis > Particle size (PSD) and Graph gallery > Particle size. Several PSDs overlaid: distributions above, cumulative below.
    Analysis > Particle size (PSD): D10, D50, D90, span and mode of all ticked PSDs in one table; RRSB (Rosin-Rammler-Sperling-
    Bennett) fit: x' and n with R², fitted between 5 and 95 % passing. CSV and provenance in the results folder\PSD.
    Note: the example PSD now comes out in the new style, so the update says that one example is drawn differently - that is this
    change; press 'Install this version'.
  The assistant shows pictures
    Pictures from Wikimedia Commons (free, no key) with title, author and licence; 'Use in chat' sends one to an AI that can see
    pictures (or 'Draw my data like this'), 'Source' opens its page, Google Images for more.
    'Show me graphs of particle size distribution' (XRD, TGA, FTIR, calorimetry, strength ...): how the app draws that kind - your
    own graphs, or an example file - every style, as pictures in the chat; then papers and pictures.
  Free search: misspellings of the usual science words are corrected ('partcile size ditricution'), words like 'show me graphs of'
  are left out of the search, and papers that share no real word with the question are not listed.

VERSION 5.40.0  -  ONE WINDOW; GRAPHS, TABLES AND PICTURES IN THE ASSISTANT
  One window
    Origin Plot Studio has one window. The earlier (classic) window is no longer offered: File > Classic window and the choice
    in Settings are gone, and every way of starting the app (shortcut, Origin_Plot_Studio.vbs, Run_Origin_Plot_App.bat, start.pyw,
    origin_plot_app.py) opens this window. PySide6, which the window is built with, is checked and installed with the other packages;
    if it is missing at the start it is installed then. If the window cannot start, a message says why and startup_error.txt holds
    the details. Your settings, sessions (Resume last session) and results stay as they are.
  The assistant shows everything in the chat
    Graphs     after each action that changes a graph (your own graph, gallery graph, group, labels, thermodynamic chart, graph type,
               FTIR reading ...) a picture of the graph as it is now; 'Show in Workspace' opens it, 'Open the picture' saves or zooms.
    Tables     the result table of an analysis (find peaks, TGA steps, FTIR band areas ...) as a table; tables the AI writes in its
               answer (Markdown) are drawn as tables.
    Pictures   your own pictures (+, paste, drop) as before, with 'Draw my data like this'.
    New actions for the AI: show_graph (a picture of a graph) and show_table (the first rows of a graph's data or results).
    Without any AI: type 'show graph 2', 'show data 2' or 'show results 2'.

VERSION 5.39.1  -  THE ASSISTANT TAB, ADJUSTABLE SECTIONS, NEW / REFRESH / UNTICK ALL
  Assistant tab   the chat itself, full size (the same conversation). Going to another section puts it back beside your work if it
                  was open there (Assistant button at the top, or Ctrl+K).
  Adjustable      drag the edge of the side bar to make it wider or narrower, or fold it away; the dividers between the panels are
                  wider and turn blue when the mouse is on them - drag them to resize Your graphs, the graph, Graph settings and the
                  assistant. Panel title bars (⠿) are dragged to move a panel to another side or out as its own window.
  Top bar         New (start afresh: an empty project; File > Resume last session brings the list back) and ↻ Refresh (draw every
                  graph again). Your graphs: Tick all and Untick all.

VERSION 5.39.0  -  THE NEW WINDOW IS THE MAIN WINDOW
  Starting the app (Desktop shortcut, Origin_Plot_Studio.vbs, Run_Origin_Plot_App.bat, start.pyw) opens the new window by itself.
  Files dropped on the shortcut open in it. If PySide6 is missing, or the window cannot start, the classic window opens instead
  and startup_error.txt says why. Settings > 'Window that opens when you start' still lets you choose the classic window.
  The classic window: File > Classic window (it opens with the files of Your graphs; its own File > Modern window comes back).
  Menu bar
    File       New project (Ctrl+N), Add data files (Ctrl+O), Open session (Ctrl+Shift+O), Resume last session (Ctrl+Shift+R; the list
               is saved by itself when you close the app or start a new project - the same file as the classic window), Save session
               (Ctrl+S), Import from an Origin project, Convert files to Excel, Save everything as one workbook, Workbook template,
               Make a gallery graph template, Refresh previews, Open results folder, Classic window, Exit (Ctrl+Q).
    Draw       Draw ticked / all in Origin (F5 / Shift+F5), Save this graph (Ctrl+E), Your own graph… (Ctrl+Shift+D: x column, y
               columns, style, layout, axis titles, log x, reversed x - or back to the automatic graph), Peak labels you type…
               (Ctrl+Shift+L: position and text; your own assignment, noted in the record), Label peaks automatically (Ctrl+L),
               Figure from the ticked graphs, Preview paper set, Make paper set, Paper figures from a recipe.
    Analysis   all analyses, gallery graphs, TGA mass loss, calorimetry, FTIR band areas, thermodynamic modelling, find peaks.
    XRD tools  XRD Scan Generator, Peak correct / improve a scan, Phase library… (the table of all phases; add phases from a file with
               Phase, Code, d, I; remove stored ones - built-in phases stay).
    View       the panels (Ctrl+1..4), focus on the graph (F11), show everything, panels as windows, put them back.
    Help       Check for updates (download, draw the examples with the new version, install when they are the same, restart),
               Install an update from a zip file, Undo the last update, Where updates come from, System Check, Problem report
               (messages, settings, list of graphs - no tables, no key), Mouse and keyboard (F1), About.
  At the start the window removes old program files, notes plugin and System Check problems in Details, and looks quietly for a new
  version: a button '↑ Update x available' appears at the top; nothing is installed without your click.
  The assistant without any AI also understands short commands, as the classic window did: 'plot TGA with DTG', 'stack all XRD
  files', 'analyse the TGA steps', 'draw G07', 'plot calorimetry, mass 0.5 g', 'generate XRD scans', 'system check'. Questions
  are searched on the web.

VERSION 5.38.0  -  PICTURES IN THE CHAT, ACADEMIC SEARCH WITH PREVIEW, MOVABLE PANELS, THE MODELLING PROGRAM
  Pictures in the chat (modern window)
    Add a picture with +, paste it (Ctrl+V: a screenshot, a figure copied from a PDF) or drop it on the chat: it is shown in the
    chat and sent with your next message to an AI that can see pictures (Claude, ChatGPT, Gemini; once, later only its name).
    Draw my data like this   under each picture: the AI looks at the figure and proposes how to draw YOUR ticked graph the same
                 way (kind of chart, stacked / overlaid / panels, log or reversed axes, peak labels) with the app's actions - only
                 the style is copied, never numbers from the picture; you confirm with Do it. Ask about it / Open.
    New assistant action 'own': draw one table your way (columns, style, axis titles, log / reversed axis, layout); refused with the
    real column names if a column does not exist.
  Web search, academic first
    Free web search lists papers from OpenAlex, Semantic Scholar, Crossref and arXiv (each paper once, the best of each source in
    turn); Wikipedia only when no paper is found. Cards show authors, year, journal, times cited, OPEN ACCESS and the source.
    Click a title: the paper opens in a preview inside the app with all authors, DOI and the whole abstract (fetched by its DOI when
    the list had only part of it); Open the paper, Free PDF, Copy the reference, Ask the assistant about it (title and abstract go
    with your next message). ↗ opens the page in the browser.
  Panels
    Your graphs and Graph settings are panels around the graph: drag a title bar to another side (left, right, top, bottom) or out
    as its own window - that window can be minimised and maximised. Panels ▾ > '… as its own window' does the same; 'Put the panels
    back in place' docks them again. The assistant works the same way.
  Thermodynamic modelling > Program and database used
    Choose the program (GEMS, CEMGEMS, GEMS3K, FactSage, Thermo-Calc, TC-Python, PHREEQC, HCh, Perple_X, OLI Studio, MTDATA,
    ChemApp / ChemSheet, or type another) and the database (CEMDATA18, FToxid, TCOX ...): "Calculated with ..." is written under the
    figure (preview, Origin, publication files), in the processing record and in the session; each program shows what of its
    output is read. The assistant can set it too, only as you say.

VERSION 5.37.0  -  MOUSE, RIGHT-CLICK MENUS, SAVE MENU AND SHORTCUTS (modern window)
  Right click   Your graphs: tick / tick only this one, sample name, graph type, Analyse (find peaks, smoothing, baseline,
                normalise, derivative, statistics), peak labels, thermodynamic chart, FTIR read as, group (stack, overlay, panels,
                ungroup), draw in Origin, save, copy the picture, open the file's folder, copy the path, remove from the list.
                The graph: reset axes, zoom, pan, select range, integrate, label peaks, find peaks, copy, save the view, save, draw.
                Data and Results tables: copy the selected cells or the whole table (paste into Excel or Origin), save as CSV / Excel.
                The chat: copy, copy all, save the chat, new chat.
  Mouse         double click a graph in the list ticks / unticks it; drag graphs to change their order (drawing and the paper set
                follow it); on the graph the wheel zooms around the pointer (Ctrl + wheel: x only) and a double click resets the
                axes; drop files from Explorer onto the window.
  Save ▾        this graph (PNG 600 dpi, TIFF, PDF, SVG), the view on screen as a picture (with your zoom), copy the view, the
                data table, the results table, the session, open a session, the chat, open the results folder.
  Shortcuts     Ctrl+O add files · Ctrl+S save session · Ctrl+Shift+O open session · Ctrl+E save this graph · Ctrl+Shift+E save
                the view · Ctrl+Shift+C copy the view · F5 draw ticked in Origin · Shift+F5 draw all · Ctrl+A / Ctrl+Shift+A tick /
                untick all · Space tick the graph on show · Delete remove from the list · Ctrl+F find a graph · Ctrl+R reset axes ·
                Z / P / S zoom, pan, select range (on the graph) · Ctrl+I integrate · Ctrl+L label peaks · Ctrl+G stack ·
                Ctrl+Shift+G overlay · Ctrl+K assistant · Ctrl+1..4 panels · F11 focus on the graph · Ctrl+Shift+1..5 sections ·
                Esc clear the range · F1 the list of all of these (also the ? button).
  Sessions saved in the modern window are the current window's format (File > Open session there opens them), with your ticks
  and your own groups kept for the modern window.

VERSION 5.36.0  -  THERMODYNAMIC MODELLING, FILES IN THE CHAT, A CLEARER CHAT, PANELS
  Thermodynamic modelling (both windows read these files; the modern window has its own section)
    Read as they are, nothing calculated: tables of phase amounts from GEMS (GEM-Selektor, CEMGEMS), FactSage (Equilib results
    exported to Excel or CSV), Thermo-Calc (NP(...), NPM(...), BPW(...) columns - now with clean phase names), HCh, PHREEQC selected
    output (.sel - new: the equilibrium phases against time or step, in mol) and any table with an ordered column (temperature,
    time, replacement level ...) and columns named like phases. They are drawn in Origin like every other graph.
    Analysis / Graph gallery > Thermodynamic modelling (modern window)
      Phase assemblage (stacked areas), Phase amounts (lines), Phase assemblage per composition (stacked bars), Change against the
      first row, Pore solution (logarithmic): for the ticked model tables.
      Saturation indices (si_ / SI columns), Solution composition (m_ / tot_ / molal / mmol/l columns), pH, pe and Eh: a new graph
      each, with its table (CSV) and provenance in the results folder\Modelling; PHREEQC's -99 'no value' is left out.
    The assistant can do the same (thermo_chart, thermo_extract), after you press Do it.
  The chat (modern window)
    +            add files: data files go to Your graphs (ticked); PDF, Word, Markdown and text documents are read and sent with your
                 next message to the AI you chose (shown above the box, ✕ removes one). Pictures are not sent. PDF needs the Python
                 package pypdf, Word python-docx (the app says so if they are missing).
    Easier to read   your messages on the right, the assistant's in a card, bold / lists / [1] references formatted; web results
                 as numbered cards (title, authors, year, journal, times cited, first words, PAPER / WIKIPEDIA) with Google and
                 Google Scholar buttons. Wikipedia's &quot; and similar signs are shown as text; a busy search service is no longer
                 shown as an error when the others answered.
  Panels ▾ (top bar of the modern window)
    Side bar (Ctrl+1), Your graphs (Ctrl+2), Graph settings (Ctrl+3), Assistant (Ctrl+4): show or minimise each; remembered for
    the next start. Focus on the graph (F11) leaves only the graph; Show everything brings all back.

VERSION 5.35.0  -  FTIR, YOUR OWN GROUPS, AUTOMATIC PEAK LABELS, BETTER WEB SEARCH
  Analysis > FTIR
    Read as absorbance / as transmittance / automatically   for the ticked spectra only: absorbance -> bands found and labelled at
                         the maxima, transmittance -> at the minima. Only how the graph is read changes; your numbers stay.
    Transmittance to absorbance, absorbance to transmittance, wavenumber to wavelength   new spectra come to Your graphs.
    Band areas in wavenumber regions   one region per line ("1200-850 Si-O"; change the starting list to your own); straight-line
                         baseline between the region's ends; transmittance is turned into absorbance first. Table + CSV +
                         provenance (results folder\FTIR).
  Analysis > Peak labels
    Label peaks automatically   the ticked graphs get their peaks labelled with their positions (how many, minimum prominence,
                         digits). Numbers only - never a guessed phase. The labels go to Origin and the publication files.
                         FTIR spectra label their bands themselves. Remove the automatic labels takes them off again.
  Graph gallery > FTIR    the ticked FTIR spectra stacked (offset) or overlaid; also "Stack / Overlay the ticked graphs" for any kind.
  Your graphs (Workspace)
    Group list           Decide for me, Stack them, Overlay them, One page per sample, Keep them separate (as in the current window).
    Stack / Overlay      your own group of the ticked graphs (one kind), shown with ◆ at the top; Ungroup removes it.
                         Mixing absorbance and transmittance spectra gives a note to convert one first.
  Settings > Peak labels  Label peaks automatically on XY graphs, and the most labels per graph (as in the current window).
  Assistant: web search
    No AI: free web search   papers from OpenAlex and Semantic Scholar (each paper once) and Wikipedia, plus links that open the
                         same search in Google and Google Scholar in your browser.
    With an AI that cannot search itself (Ollama, Kimi ...)   the AI first writes a precise search query, the app searches with it,
                         and the AI answers from the results.
    Google's own search inside the assistant   a free Gemini key from Google AI Studio: Gemini answers with Google Search.
    New assistant actions: group, labels_auto, labels_clear, ftir_read, ftir_areas (you confirm each).

VERSION 5.34.0  -  WEB SEARCH WITHOUT A KEY, FILES FROM EVERY PAGE
  Assistant (modern window)
    No AI: free web search   choose it in the AI list and type your question: the app searches scientific papers (OpenAlex)
                             and Wikipedia and lists what it found, with links. No key, no account, nothing to install.
                             Only your search words are sent.
    Local model (Ollama)     free and on your computer; with 'Search the web' ticked the app searches for it and the model
                             answers from the results, citing them [1], [2] ...
    Claude, ChatGPT, Gemini, OpenRouter   with a key they search the web themselves (as in 5.33.0).
    Ask in your browser      for a ChatGPT, Claude or Gemini account without an API key: your question (and the names of your
                             graphs) is copied and the website opens; press Ctrl+V there if it is not filled in. Answers there
                             cannot act on the app.
    + Add files              adds data files from the assistant.
  Every page: Add files… (or drop files anywhere on the window). Added files come to Your graphs ticked, so the tool on the page
  works on them straight away; the page says which graphs a Run works on. 'Go to Workspace' takes you to the graphs.
  Ticks now stay when files are added (before, adding files cleared them).

VERSION 5.33.0  -  MODERN WINDOW, STEPS 3 AND 4: ANALYSIS, GALLERY GRAPHS, ASSISTANT, SETTINGS
  Analysis        click an entry, set it, press Run. It works on the graphs ticked in Your graphs (or the one on show), with the
                  same code as the current window:
                    XRD            XRD Scan Generator, Peak correct / improve a scan (the scans you send back come to Your graphs),
                                   phase library folder.
                    TGA            mass loss in temperature intervals, with total and residue (table + CSV + provenance).
                    Calorimetry    one row per file: mass (required), label, regime, alite; exclusion window, reaction-start row,
                                   bar-chart time; then the workbook and figures C1-C5.
                    Phases         C01 hydration degree, C02 atomic ratios.
                    44 data tools  smoothing, baseline, normalise, calculus, peaks, fitting, transforms, curve arithmetic, FFT,
                                   statistics. A range selected on the graph fills From x / To x. New curves come to Your graphs;
                                   tables are shown and saved as CSV with a provenance file (results folder\Analysis).
  Graph gallery   draw the ticked workbook(s) as any of the 26 types (it asks for t0 or the sample mass when a type needs it),
                  or make a template in that layout from a raw file.
  Assistant       a panel beside your work (the Assistant button; drag its title bar to put it left, right or in its own window).
                    AI       Claude, ChatGPT, Gemini, Kimi, a free local model (Ollama), or any OpenAI-compatible service
                             (OpenRouter: hundreds of models with one key; Groq, xAI, Mistral ...). Keys are the ones saved in the
                             current window, or added in Settings; stored encrypted by Windows.
                    Model    every model your key can use, changeable at any time.
                    Search the web   Claude, ChatGPT, Gemini and OpenRouter look things up and list the pages they used.
                    Actions  look, show, tick, name samples, graph type, run analyses, TGA steps, gallery graphs, panel figures,
                             results folder, save, draw in Origin, paper set, XRD Scan Generator, remember a rule. It says what it
                             wants to do; nothing runs until you press Do it. It sees the list of graphs, not your tables.
  Settings        which window opens when you start the app (current or modern), the AI and its key, your instructions and what
                  it has learned, and the analysis and figure settings (XRD, TGA, FTIR, calorimetry, figures) with
                  "Apply to my graphs".
  The modern window keeps its own settings in settings_modern.json (started from the current window's), because each window
  writes its settings when it closes. The current window and its functions are unchanged; File > Modern window opens this one.

VERSION 5.32.0  -  MODERN WINDOW: EVERYTHING INSIDE ANALYSIS AND GALLERY GRAPHS
  The side bar of the modern window is now: Workspace, Analysis, Graph gallery, Assistant, Settings.
    Analysis        XRD (Scan Generator, Peak correct, generate scans, phase library), TGA (mass loss in intervals),
                    Calorimetry (TAM III workbook, figures C1-C5), Phases and composition (C01, C02), then the 44 data-analysis
                    tools by group (smoothing, baseline, peaks, fitting, statistics ...).
    Graph gallery   the 26 types grouped by technique: XRD, NMR, TGA, Calorimetry, Phases and composition, Particle size,
                    General plots.
  Each has a search box; clicking an entry tells what it does and where it is in the current window. Step 3 makes them run
  inside the modern window. The current window is unchanged.

VERSION 5.31.0  -  MODERN WINDOW, STEP 2 OF 4: DRAWING AND SAVING
  File > Modern window (steps 1-2 of 4). The right-hand card now draws and saves, through the same functions as this window
  (Draw ticked, publication files, Figure from ticked, Paper set), so the results are the same files in the same folders:
    Sample name      type it and press Apply: it is given to the ticked single graphs (or the one on show); the combined
                     figures are made again, as in this window.
    Size and look    journal, width in mm (or Automatic) and curve / axis line weights.
    Files            PNG and PDF from Origin, publication files (PNG 600 dpi, TIFF, PDF, SVG), keep Origin open, a new dated
                     folder per run, the results folder and the Origin project name.
    Draw ticked in Origin / Draw all in Origin   if Origin does not start, the publication files are still made.
    Save this graph  publication files of the graph on show (or a panel figure) in <results>\publication.
    Figure from the ticked graphs   a panel figure (a), (b) ... at the top of Your graphs; tick it and draw or save it.
    Paper set        main-text samples, Preview paper set (PDF, nothing drawn in Origin) and Make paper set.
    Stop after the current graph, and a Details tab with the full log.
  The settings chosen there are saved in settings.json, so this window uses them too.

VERSION 5.30.0  -  MODERN WINDOW, STEP 1 OF 4
  File > Modern window (step 1 of 4) opens the new window (Qt, the same toolkit as the XRD Scan Generator) with the graphs
  of Your graphs. It reads them with the same engine as this window.
  Now: side bar (Workspace; the other sections say which step brings them), Your graphs with ticks, combined figures and a
  search box, the live graph with Zoom, Pan, Select range (then Integrate: the same calculation as Analysis > Calculus > Area)
  and Reset axes, the Data and Results tabs, and the graph type. Add files with the button or Ctrl+O.
  Step 2: drawing in Origin, PNG/PDF/SVG, journal sizes, sample names. Step 3: Analysis, gallery graphs, calorimetry, XRD tools.
  Step 4: assistant and settings, then you choose which window opens. It closes when Origin Plot Studio closes.

VERSION 5.29.2  -  THE MODERN WINDOW (PREVIEW) IS REMOVED
  File > Modern window (preview), added in 5.29.0, is removed again. Its program files are deleted from the program folder the
  first time 5.29.2 starts (the update itself only adds and replaces files). The rest of the app is unchanged.
  If you installed the Python package pywebview for it, it is no longer needed: py -m pip uninstall pywebview  (optional).
  Its log and recovery copy were kept in %LOCALAPPDATA%\OriginPlotStudioPilot; you can delete that folder.

VERSION 5.28.0  -  MENUS BY PURPOSE, AND AN ANALYSIS MENU
  File        everything about files and the project: New project (start anew), Open / Resume / Save session,
              Import data files (Ctrl+I), Import from an Origin project, Convert files to Excel, Save everything as one
              workbook, Workbook template, Make a gallery graph template, Refresh previews, Open results folder, Exit.
  Analysis    data-analysis tools for the graphs you tick in Your graphs (or the one on show):
    Smoothing              Moving average, Savitzky-Golay, Gaussian, Median (remove spikes)
    Baseline               Straight line between the ends, Polynomial (iterative), Asymmetric least squares (ALS), SNIP (XRD, Raman)
    Normalise              To maximum = 1, To area = 1, Min-max to 0-1, z-score, Relative to the value at an x
    Calculus               First derivative, Second derivative, Cumulative integral, Area between two x values
    Peaks                  Find peaks, Find valleys (minima), Fit peaks (deconvolution)
    Curve fitting          Fit a model, Polynomial fit, Linear regression with confidence band
    Transform and convert  Crop to an x range, Resample to an even step, Scale and offset, log10 of y, XRD: 2θ to d-spacing, XRD: d-spacing to 2θ, XRD: 2θ to Q, FTIR: wavenumber to wavelength, FTIR: transmittance to absorbance, FTIR: absorbance to transmittance, Temperature: °C to K, Temperature: K to °C
    Curve arithmetic       Difference A - B, Ratio A / B, Sum, Mean ± SD of curves
    Frequency              FFT amplitude spectrum
    Statistics             Descriptive statistics, Correlation (Pearson, Spearman), t-test (two groups), ANOVA (several groups) + Tukey
              and the app's own analyses: TGA mass loss in temperature intervals, Calorimetry (TAM III) C1-C5,
              hydration degree (C01), atomic ratios (C02), Analysis settings.
              Every tool is a plain calculation (numpy / scipy); no AI touches your numbers. New curves are saved as CSV
              in the results folder under Analysis, with a _provenance.json (method, settings, input file and its
              SHA-256), and are added to Your graphs so you can draw them like any file. Result tables (peaks, fit
              parameters with standard errors and R², statistics) are saved as _results.csv and shown in a window.
  XRD tools   XRD Scan Generator (app) with the Peak correct tab, Peak correct / improve a scan, the built-in generator,
              Phase library.
  Draw        Draw ticked (F5) / all (Shift+F5), paper set, paper figures from a recipe, Stop (Esc).
  Help        as before.

VERSION 5.14.2  -  A CLEAR PLACE TO TYPE WITH A + FOR ANY FILE, THE AI CONVERTS FILES THE APP CANNOT READ, THE CHAT AND THE KEY STAY
  WHERE THE ASSISTANT IS
    Nowhere to put: it is part of the app. Tab 'Assistant' (second tab), or the button 'Assistant...' on 'My graphs'.
  THE TAB IS REARRANGED
    - The place to type is at the top in a coloured frame, with + on its left and Send on its right. Enter sends
      (Shift+Enter makes a new line). The conversation is below it. The cursor is in the box when you open the tab.
    - The examples are buttons under the box ('Recommend graphs', 'Label a peak' ...): a click puts the sentence in
      the box. The box for linking the AI is hidden once linked; the top line shows which AI, 'Change AI...' opens it.
  THE + BUTTON: ANY FILE
    + opens a file window for any kind of file. A file the app can read is added as always and the assistant
    recommends what to draw. A file the app cannot read (text around the table, a table written in rows, a title block
    in Excel, an unknown instrument export) is handed to the AI:
      1. the AI is shown the first 40 lines of the file, with row numbers;
      2. it answers with a reading recipe: where the table is, the separator, the decimal sign, what the columns are
         called and their units;
      3. the APP reads the numbers from your file with that recipe (the AI never types a number), writes a clean
         workbook in <your folder>\converted_tables, loads it and draws it. The workbook also opens in Origin.
    Pictures, PDF, Word and Origin project files are not tables: the app says so.
    The AI may only open files you typed, chose with + or loaded; never a file it thought of itself.
  IT LEARNS NEW FILE LAYOUTS
    After a conversion the app remembers the layout (learned_formats.json in %APPDATA%\OriginPlotApp). The next file of
    the same layout is read with the saved recipe at once, without the AI, also from 'Add files' on 'My graphs' and
    also when it is longer or shorter. The message box says when this happened. Delete the entry to make it forget.
  THE CHAT STAYS, WHICHEVER AI
    The conversation is saved and is there again when you open the app, and it continues when you switch to another AI
    in the list. 'New chat' starts a fresh one; the old one is kept as a text file ('Earlier chats...').
    The app cannot fetch the chats you had on the websites of ChatGPT, Claude or Kimi: a key gives no access to those.
  THE KEY IS STORED ENCRYPTED
    With 'Remember the key' ticked the key is encrypted by Windows itself (data protection tied to your Windows login)
    before it is written; only your Windows account on this computer can read it back. Keys saved as plain text by
    5.14.0 and 5.14.1 are encrypted at the next link. If Windows refuses, the key is not stored at all and the app
    says so. Each AI keeps its own key; choosing the AI in the list brings it back.
  PROBLEMS AND "UPDATING ITSELF"
    - Every problem (a line with !!) is kept. 'Explain the last problem' asks the AI what it means and what to do.
    - 'Problem report...' writes one zip in your folder (messages, settings, the first 30 lines of files that could
      not be read; no tables, no key) to send to whoever looks after the app.
    - The app does not rewrite its own program, and no AI is allowed to: untested changes to the code that draws
      your figures would be a risk. What it does update by itself is its knowledge: your rules, your phases, and the
      file layouts it has learned. A new version of the program still comes as a zip.
  NOT TESTED: the real AI services (no keys here), real Origin, and the Windows encryption call itself (it exists only
  on Windows; here it was replaced by a stand-in). Tested here: the real app window on a virtual screen with a
  stand-in AI (link, +, conversion of two files the app cannot read, reopening), 41 checks of the AI module, the
  layouts learned and re-used, and every earlier example file (same graphs as before).

VERSION 5.14.1  -  LINKING THE AI IS EASIER, AND KIMI IS IN THE LIST
  WHEN TO USE THE ASSISTANT
    You do not need it for normal work: Add files, look at the preview, Draw. That costs nothing and needs no AI.
    Use the Assistant when you want
      - several steps from one sentence ("add these files, call the sample Sample A (4 % additive), save in D:\Results, draw"),
      - a recommendation for a table ("what can I draw from this?"), also for a table the app does not recognise,
      - your own labels on peaks ("label 29.4 as A"),
      - the same rules every time ("from now on ...").
  LINKING, THE FIRST TIME (about a minute)
    1. Tab 'Assistant'. Choose your AI in the list: Claude, ChatGPT, Gemini, Kimi, a local model, or another service.
    2. Press 'Get a key...': the page of that AI opens in your browser. Create a key there and copy it.
    3. Come back and press 'Paste'. The app links by itself; the dot turns green and the model list is filled.
    If you already have a key: just press 'Paste'. For Claude and Gemini the app sees from the key whose it is.
  AFTER THAT
    - Nothing to do: when you open the tab 'Assistant' the app links by itself with the saved key.
    - Choosing another AI in the list brings its own saved key and model back and links at once. So you can keep keys
      for several AIs and switch with the list.
    - The line under the boxes always says what to do next for the AI you chose. The dot: grey = not linked,
      yellow = working, green = linked, red = it did not work (the reason is written in the chat).
  KIMI
    'Kimi (Moonshot AI)' is in the list (address https://api.moonshot.ai/v1, key page platform.kimi.ai). A Kimi key
    looks like an OpenAI key, so the app cannot tell them apart: choose Kimi in the list before you paste.
    A key in the Windows variable MOONSHOT_API_KEY is found by itself.
  A LOCAL MODEL
    Choose 'Local model on this computer (Ollama, free)': no key. 'Get the program...' opens its page; install it,
    download one model in it, press Connect. If the program is not running the app says so.
  Also: a Claude key is tried in both ways the Claude API takes a key.
  Tested in a real app window on a virtual screen here (paste -> linked, Kimi, switching, reopening the app), against a
  stand-in for the AI services. NOT tested with the real services (I have no keys) and NOT in real Origin.

VERSION 5.14.0  -  THE ASSISTANT: TYPE WHAT YOU WANT, AN AI OF YOUR CHOICE DOES THE STEPS IN THE APP
  New tab 'Assistant', next to 'My graphs'. Everything else works as before, also without any AI.
  THE FLOW
    1. Choose the AI: paste its key and press Connect. The app finds out from the key which AI it is and fills the list
       of models. (Claude, ChatGPT, Gemini; a local model with Ollama needs no key; any other service that speaks the
       OpenAI chat format: choose 'Other service' and type its address.)
    2. Press 'Add files and recommend...' (or type the file paths). The files are read as always; the assistant then
       says what it found and recommends what to draw.
    3. Type what you want in plain words, for example:
          call the sample Sample A (4 % additive) and draw the sample page
          label the peak at 29.4 as A and the one at 32.2 as B on graph 2
          write the workbook for Origin and save everything in D:\Results\figures
          draw graph 1 and 3
       The assistant answers in one or two lines; under its answer you see every step the app carried out and its result.
    4. The figures are drawn in Origin with their labels and saved, with the publication files and the record, in the
       folder you named.
  WHAT THE AI DOES AND DOES NOT DO
    - The AI only chooses steps the app already has: add files, sample name, graph type, graph suggestion, own graph
      (columns, style, axis titles), peak labels, settings, tick, figure of several graphs, save folder, workbook for
      Origin (one clean sheet per table plus samples, phases and peak labels; or the empty template), draw, remember.
      The app carries them out with the same code as the buttons. The AI never draws and cannot change your numbers.
    - Labels: the app refuses a label whose text you did not type in the chat and that is not in your own files.
      So the AI cannot put a phase on a peak by itself. Labels you typed are written in the processing record as yours.
    - Line weights below 1.5 pt are refused.
  YOUR INSTRUCTIONS AND WHAT IT LEARNS
    - 'My instructions...' opens a text file with your rules (sample names like "Sample A (4 % additive)", landscape, TG and DTG in
      one graph, no guessed phases ...). The assistant reads it before every answer. Change it as you like.
    - When you state a lasting rule ("from now on ...", "always ...", "never ...") or correct it, it saves one line in
      'What it has learned...'. That file is read in every later chat. Delete a line to make it forget.
      This is saved text, not a retrained model. Both files are in %APPDATA%\OriginPlotApp, outside the app folder,
      so they stay when you unzip a new version.
  THE KEY, THE COST, YOUR DATA
    - A key ("API key") comes from the website of the AI provider. It is usually billed by use and is separate from a
      chat subscription. With 'Keep the key on this computer' ticked it is saved as plain text in
      %APPDATA%\OriginPlotApp\assistant.json (not in the app folder). Untick it to type the key each time. A key in
      the Windows variable ANTHROPIC_API_KEY, OPENAI_API_KEY or GEMINI_API_KEY is found by itself.
    - Sent to the AI: your message, your instruction file, the list of graphs (file names, sample names, column names
      with smallest and largest value, positions of the strongest peaks, the labels on a graph). The tables of numbers
      are not sent. With a local model (Ollama) nothing leaves the computer; small local models follow the steps less
      reliably.
  NOT TESTED WITH A REAL AI SERVICE. I have no keys here. It was tested with a stand-in that answers in the format of
  each service (Claude, OpenAI-type, Gemini, Ollama): finding the AI from the key, the list of models, a whole chat
  (add the two S1 files, folder, workbook, draw; recommendation; labels; refused label; settings; a lasting rule;
  wrong key, limit reached, service down, an answer that is not in the agreed form). The first run with your own key is
  the real test: if Connect or Send shows a message you do not understand, send it to me. Also NOT tested in real Origin.

VERSION 5.13.6  -  NOTHING TO DO BY HAND FOR A FIT FILE AND ITS PEAK LIST
  Add the two files (together, or one after the other, in any order). The app then does all of this by itself:
  reads both, finds that they belong to the same sample, takes the phase labels from the peak list, and lists three graphs:
  the sample page ((a) pattern with assigned peaks, (b) fit; already ticked), the fit, and the peak list. Draw all sends
  them to Origin. No sample name has to be typed and no kind has to be chosen.
  LABELS THAT WERE STACKED. When two peaks are close together their labels are stacked, and the leader line of the upper
  label ran through the lower label. The lower label is now moved a little to the side, so that the line passes beside
  it; it stays next to its own peak and gets no line of its own. Same in the preview, the publication files and Origin.
  In the example files this changes 4 of 64 graphs.
  Checked as in 5.13.5, and with the two files added in either order in the app window. NOT tested in real Origin.

VERSION 5.13.5  -  HIGHSCORE CSV FILES AS THEY COME OUT OF HIGHSCORE (SWEDISH NUMBER FORMAT), AND FILES WITH DIFFERENT NAMES
  Made for the two files S1_RETVELT.CSV (observed, calculated, background) and S1_peak_lables.CSV (the reflections of the
  refinement with their phases). Version 5.13.4 could not open either of them.
  WHAT WAS WRONG WITH THE FILES
    - On a computer with Swedish number format HighScore writes the comma BOTH between the columns and as the decimal sign,
      without quotes:   1,6,0043,307,9961   means   1 | 6.0043 | 307.9961.  The header has 11 names, every row 20 pieces.
    - The degree sign and the angstrom sign are written in the Windows character set, not UTF-8.
  WHAT THE APP DOES NOW
    - It puts the numbers together again. Which columns are decimal numbers is decided for the whole file: a piece that
      begins with a zero ('0043') can only be decimals, a negative piece or a word can only begin a column, a column keeps
      its number of decimals. Heights with their uncertainty, 24(64) or 2,1(5), are read as 24 and 2.1. Phase names with a
      comma in them ('Quartz, syn') stay one name. The message box and processing_record.txt say that this was done and
      which columns are decimal numbers. Files with semicolons, tabs or decimal points are read as before.
    - Text files are read in UTF-8, UTF-16 or the Windows character set, whichever fits.
    - The wavelength is taken from the file when it has a 2theta column and a d-spacing column (here 1.5406 A, copper).
    - A peak list of a refinement lists every reflection twice, for K-alpha1 and K-alpha2. The K-alpha2 rows are found
      (from the d-spacing column, or from position and half height when there is none) and left out, so every reflection
      has one tick and one label. In S1_peak_lables.CSV that is 1298 of 2607 rows.
    - 'Quartz_alpha', 'Zinc_oxide' are written 'Quartz alpha', 'Zinc oxide'. Zinc oxide gets the label Z, oligoclase Olg.
  DIFFERENT NAMES
    - File names: words at the end that describe the content are not part of the sample name, also when mistyped:
      S1_RETVELT -> S1, S1_peak_lables -> S1 (Rietveld, refinement, profile, peaks, peak list, labels, pattern, scan,
      fit, calc, hkl, xrd ...). The two files then belong to the same sample: the pattern carries the phase labels of the
      peak list, and the sample page (a) pattern with assigned peaks, (b) fit is made.
    - When the names have nothing in common, a peak list without a pattern and a pattern without a peak list are still put
      together when the listed peaks sit on the peaks of that pattern (agreement of at least 0.6 of 1, and clearly better
      than any other pair). The message box says so with the agreement.
      If you typed different sample names for the two, they stay apart.
    - Column names: a peak list is also recognised when the phase column is called 'Matched by', 'Compound name' or 'Name'
      and the height column 'Intensity' or 'Counts'.
  Rwp on the graph is recomputed from the observed and calculated columns of the file (w = 1/Yobs, all points of the file).
  It can differ from the value HighScore shows when the refinement used another range or excluded regions.
  Checked with: the two files themselves (all 2607 rows of the peak list compared with a second, independent reading rule),
  the same data written with decimal points, semicolons, tabs, UTF-8, other column names and another column order, a
  stand-in for Origin, and every example file (same graphs as before). NOT tested in real Origin.

VERSION 5.13.4  -  THERMODYNAMIC MODELLING OF HYDRATED CEMENT PASTES (GEMS / CEMDATA AND THE LIKE)
  As in 5.13.3 the app does not calculate; it draws the result tables, saved as Excel, CSV or text.
  PHASE ASSEMBLAGE OF A HYDRATED PASTE. Recognised from the column names: C-S-H, portlandite, ettringite (AFt),
  monosulfate, monocarbonate, hemicarbonate (AFm), hydrotalcite, hydrogarnet, straetlingite, calcite, gypsum, brucite,
  M-S-H, unreacted clinker phases (alite, belite, aluminate, ferrite), unreacted additions (slag, fly ash, limestone,
  tailings ...), pore solution, also in GEMS spelling (CSHQ, C4AcH11, aq_gen).
    - against ANY ordered column, not only temperature: hydration time (logarithmic axis when the times span more than
      a factor of 100), degree of reaction, replacement level, water/binder ratio, temperature  ->  stacked areas;
    - one row per mix  ->  stacked bars.
  Stacking order for a paste: unreacted binder at the bottom, hydrates in the middle, pore solution on top. In a
  hydrated system "slag" is treated as a solid binder, not as a liquid. Each hydrate has its own fixed colour.
  The unit is taken from the brackets behind the phase names when all are the same, e.g. (cm3/100 g), (g/100 g).
  Suggestions also offer: phase amounts as lines, hydrates only, change against the first row.
  PORE SOLUTION. A table with at least three columns named after dissolved elements or ions (Na, K, Ca, Si, Al, S,
  SO4, OH, Mg, Fe, Cl), with or without a pH, is drawn with the concentrations on a LOGARITHMIC y axis and the pH in a
  panel of its own, against time, replacement level or per mix. Values of zero cannot be shown on a logarithmic axis and
  are reported. Suggestions also offer one linear panel per species.
  Both are also under Own graph > Curves drawn as.
  IN ORIGIN: the logarithmic y axis is set with layer.y.type=2. NOT tested in real Origin.
  Not included: reading GEMS project files, saturation indices, any calculation.
  Checked with made-up tables shaped like GEMS output: hydration against time, against replacement, per mix, and a
  pore solution. The clinker graphs of 5.13.3 and every example file give the same graphs as before.

VERSION 5.13.3  -  THERMODYNAMIC CALCULATIONS (PHASE AMOUNTS FROM FACTSAGE, GEMS, THERMO-CALC ...)
  The app does NOT calculate thermodynamics. It draws the tables such programs give, saved as Excel, CSV or text.
  RECOGNISED BY ITSELF: a table whose columns are named after phases (Liquid / Slag, C3S, C2S, C3A, C4AF, CaO, MgO,
  alite, belite, Ca3SiO5 ... also with a unit in front or behind: g-C3S, C3S (wt%)) and that has
    - a temperature column and many rows  ->  PHASE ASSEMBLAGE AGAINST TEMPERATURE (stacked areas), for an Equilib
      temperature series or a Scheil-Gulliver cooling calculation;
    - or one row per composition or run   ->  STACKED BARS, one bar per row (Reference, S1 ... S4; sensitivity runs).
  Under "Suggestions..." the same table can also be drawn as: phase amounts as lines; the liquid only (burnability);
  and "Change against the first row" (each run minus the base case, per phase) for a sensitivity study.
  The four kinds are also under Own graph > Curves drawn as.
  Colours: the same phase has the same colour in every graph (liquid orange, C3S blue, C2S green, C3A purple, C4AF
  brown, free lime grey, MgO teal). The liquid is put on top of the solids. Phase names are the column names of the
  file without their unit; they are not translated or interpreted.
  Results table: for a temperature table, per phase the temperatures between which it is present, its largest amount
  and where, and the amounts at the highest and lowest temperature (read from the rows of the file, not interpolated).
  For a table of runs, the amounts and their total per row; for the change graph, the differences.
  These graphs stand on their own: "Decide for me" does not overlay them with other tables.
  IN ORIGIN: areas go in as area plots and bars as column plots, each drawn over the one below it; the fill colour
  command is one I could not test, so in Origin the colours may come out as Origin's own. NOT tested in real Origin.
  Not included: reading FactSage's own result files (.res, .equi) or figures, phase diagrams, and any calculation.
  Checked with made-up tables shaped like an equilibrium series, a Scheil cooling run and a sensitivity study.

VERSION 5.13.2  -  SUGGESTED GRAPHS, UNLABELLED TABLES, BARS / HISTOGRAM / BOX PLOT / CONTOUR MAP
  SUGGESTIONS. Click a graph in the list and press "Suggestions..." (beside Graph type, and on the tab "Own graph").
  A window shows small pictures of the graphs that fit that table, the most likely first, each with one line saying
  why. Click one and it is drawn. What is offered depends on the table: for an ordered x column - all signals in one
  graph, one panel per signal, line, symbols, logarithmic x, bars; for columns that are variables measured together -
  contour map (when x and y repeat as on a grid), one column against another, box plot, histogram; for groups in a text
  column - bars with mean and standard deviation, box plot. A suggestion that cannot be drawn for the table is left out.
  TABLES WITHOUT COLUMN NAMES. The app now looks at the numbers and says what they look like: 2theta with sharp peaks
  (XRD), wavenumbers (FTIR), a temperature with a mass that only falls (TGA), size classes that grow by a constant
  factor (particle size). The graph is drawn as that type and marked as a GUESS in the note, in the processing record
  and in the suggestions, with the reason. If no rule fits, it stays a plain graph. Calorimetry and DSC are not guessed:
  a time or temperature column with a heat signal cannot be told apart from other data by its numbers.
  NEW KINDS OF GRAPH for any table (tab "Own graph" > Curves drawn as, or among the suggestions):
    Bars          one bar per x value or per group; rows with the same value are averaged, the line is +- 1 SD
    Histogram     how the values of one column are distributed (5 to 40 classes, Freedman-Diaconis rule)
    Box plot      quartiles, median, whiskers at 1.5 x the interquartile range, values outside as circles
    Contour map   a value z as colours over x and y, interpolated between the measured points
  Each writes its numbers into the results table. "Several signals" on the same tab chooses one graph or one panel per signal.
  A table with groups in a text column and numbers but no x axis (Mix, Strength) is now drawn as bars; before, it was
  mistaken for a table of peak labels and not drawn.
  EASIER TO ADD UNKNOWN DATA. On the tab "Own graph": "Add a file...", "Paste a table (copied in Excel)" - select the
  cells in Excel, Ctrl+C, press the button - and "Show suggestions...". A file that is one small table of 3 or 4 points
  is now drawn (5 rows were needed before).
  IN ORIGIN: bars go in as column plots and the names under the axis as text. The contour map is drawn by the app only
  (preview and publication files); Origin gets the measured points. None of this is tested in real Origin.
  Checked: every example file gives the same graphs as in 5.13.1.

VERSION 5.13.1  -  ORIGIN: THE "WINDOW PROPERTIES" BOX AND THE EMPTY ZOOM
  Seen in OriginPro 2018 on a sample page: Origin opened its Window Properties box (long name L5a.csv, short name L5a1,
  comments D4a / L5a) and the zoom of panel (a) had its labels but no curve.
  What happened: every curve goes into Origin as a small workbook made from a CSV file. The file of the zoom's pointer lines
  (L5a) was read into the workbook of the zoom's curve (D4a) instead of its own. Origin renamed that workbook L5a1; the app
  then asked Origin to name it L5a, which was taken, and Origin opened the box. The zoom curve was gone with its workbook.
  The app assumed the new workbook was the active window. That holds unless something else takes the focus: a click in
  Origin while it draws, or a second drawing running at the same time. Which of these it was on your PC I cannot tell.
  Reproduced here with a stand-in for Origin: the same box, the same names, the same empty zoom.
  Changed:
    - Each file is told which workbook it belongs to, and that workbook is made the active one in the same command.
    - The import no longer renames anything (and adds no sparklines, which is quicker). If your Origin does not know these
      import options the app notices that the workbook stayed empty and uses the earlier import for the rest of the run.
    - A window is only ever renamed when the name is free, so Origin has no reason to open the box.
    - After each workbook the app asks Origin whether it exists and has rows. A workbook that is missing when the finished
      graph is checked is made again and its curves are drawn again. origin_check.txt says how the data went in.
    - Window names of a run end in two letters taken from the clock (D2kq), so they cannot meet names of an earlier run.
    - Only one drawing at a time: a second one (the app open twice) is refused with a message instead of mixing its
      workbooks into the first.
    - The numbers of the hidden left axis of the zoom, which Origin 2018 still wrote in small print, are made invisible.
  Please do not click inside Origin while the app draws.
  NOT tested in real Origin. If the box comes again, send origin_check.txt and data_for_origin\origin_commands_log.txt
  from the results folder.

VERSION 5.13  -  CORRECTIONS AFTER AN AUDIT OF VERSION 5.11
  Each point was first reproduced, then corrected, then run again. Not tested: the windows on a real screen and real Origin.
  1  "Save everything as one workbook" / "Convert files to Excel" LOST A SAMPLE when two tables of one file had the same
     column names and length (two samples measured the same way): only the first was written. A table is now a duplicate
     only when its numbers are the same. Checked: import -> workbook -> import keeps every sample and its values.
  2  TGA: A MASS IN mg WAS TAKEN AS %. A mass column that says mg and starts between 90 and 110 was drawn as per cent.
     The unit written in the file now decides; the values are only looked at when the file gives no unit. The record
     states the original unit, the plotted unit and the reference mass. A column of mass LOSS is turned into remaining
     mass (in mg or g it needs Analysis settings > TGA > Initial sample mass).
  3  THE JOURNAL NOW REACHES THE ORIGIN GRAPH. Before, the journal only changed the app's own publication files. Now one
     size and letter size are worked out per figure and used for both: the Origin page gets the journal's printed size
     and its letters are scaled for the journal's letter size. Without a journal the Origin graph is drawn exactly as
     before. The log says which files Origin drew and which the app drew itself. NOT TESTED IN REAL ORIGIN.
  4  DSC IS A GRAPH TYPE OF ITS OWN (first version). Heat flow against temperature; heating, cooling and isothermal
     segments are found and kept in the order they were measured; the exothermic direction is read from the file
     (NETZSCH header, or "exo up" in the column name) and otherwise not assumed. For each event: onset, peak, endset,
     limits and area, integrated against TIME (J/g when the unit is W/g or mW/mg). These limits are SUGGESTIONS to
     review; there is no window yet to move them by hand. A simultaneous TG-DSC file (NETZSCH STA) gives two graphs
     of the same sample: TG-DTG and DSC. Checked with a made-up heat-cool-heat run: 100, 80 and 90 J/g came out as
     99.0, 79.0 and 88.9 J/g.
  5  CALORIMETRY: a start time between two data points was integrated from the point before it (1 W/g hourly, from
     1.5 h: 25,200 J/g instead of 23,400). The heat flow is now interpolated at the start. A cumulative-heat column of
     the file itself is kept and drawn beside the calculated one. The record states the time covered by the data.
  6  JOURNAL CHECK OF THE FINISHED FILES. With a journal chosen, the TIFF is made at the resolution the publisher asks
     for bitmap line art (Elsevier 1000, Springer and Taylor & Francis 1200, others 600 dpi) and every figure is then
     MEASURED: width, height, TIFF resolution, vector files, smallest letters, line weights, font. Result in the log and
     in publication/journal_check.txt, with PASS / FAIL and the publisher page the numbers come from. A FAIL is reported,
     not hidden: for example the peak labels of a sample page are about 6.5 pt, below Springer's 8 pt.
  7  WHAT WAS IMPORTED IS REMEMBERED. Each data file gets its full SHA-256 hash and a private copy when it is read. Every
     results folder gets a folder "inputs" with these copies and their hashes, so the folder with session.json can be
     opened on another computer. A file that changed on disk after import is reported; the record no longer describes
     other bytes than the graphs show. Open session uses the saved copy when the original has changed.
  8  TGA: NO Ca(OH)2 / CaCO3 UNLESS YOU SAY THE SAMPLE IS CEMENTITIOUS. New setting Analysis settings > TGA > Material.
     The default gives the measured mass-loss steps only; choose "Cementitious sample" to get the CH / CC suggestions
     back (the table then says they are suggestions). An impossible result (more than 100 % of the sample) is refused.
     Your own ranges with tags (400-500 CH) work as before.
  9  NETZSCH EXPORTS: gas flow, sensitivity and segment columns are kept (they were dropped), the whole header goes into
     the processing record, several data blocks are all read, and a block with other columns is reported, not skipped
     silently.
  10 PEAK LISTS: d-spacings were always calculated with the copper wavelength. They now use the wavelength of the file or
     of Analysis settings; when neither is given the record says that copper was ASSUMED. Phases stored from a Bragg
     table use the wavelength of the pattern they belong to.
  Not done from the audit, on purpose not claimed: a full project database, TA TRIOS JSON import, hand-editable DSC and TGA
  baselines, method profiles (ASTM), per-journal profiles beyond the publishers' general artwork rules.

VERSION 5.12
  THE APP REMEMBERS THE PHASES OF YOUR FILES. The app is for drawing, and drawing never needs the phase library.
  But every phase that comes with your files and is new to the library is now stored, and used later when you
  choose "Suggest phases from the library" for a pattern that has no labels of its own.
  What is stored (automatically, reported in the details and in the processing record of the graph):
    - a peak list with phase assignment and intensities (HighScore peak list, Bragg sheet with calculated heights):
      d-spacings and relative intensities of each new phase;
    - a Bragg table with positions only: the relative intensities are read from the measured pattern, at the
      peaks that no other phase shares. This is an estimate and the record says so;
    - your own peak labels, when the key names the phase (Yy = ye'elimite) and at least 3 peaks carry that label.
  A phase needs at least 3 lines to be stored. Built-in phases are never changed.
  Where: outside the app folder (Windows: %APPDATA%\OriginPlotApp\phase_library\stored_phases.csv), so the
  stored phases STAY when you unzip a new version of the app into a new folder.
  XRD tools > Phase library... (also a button under Analysis settings > XRD) shows every phase the app
  knows - label, name, number of lines, built in / stored / your file, when and from what it was stored - and lets you
    Add phase from file...        a table with d (A) or 2theta (Cu K-alpha1) and relative intensities, for example
                                  a reference card exported from HighScore. Name the file after the phase with
                                  its label in brackets: Portlandite (CH).csv. A reference card is better than a
                                  phase stored from a pattern, and replaces it.
    Remove stored phase           a phase you remove is not stored again by itself
    Open folder of stored phases  stored_phases.csv opens in Excel; copy the folder to take the phases to another PC
  "Store new phases from my files" can be switched off there and under Analysis settings > XRD.
  Phases learnt by an older version (learnt_phases.csv in the old app folder): add that file with "Add phase from file".
  A stored phase of the Bragg table of a sample is from now on also labelled on the fit of that sample, and the
  key of the graph gives its name.

VERSION 5.11
  NO PHASE LABELS UNLESS YOUR FILES GIVE THEM. Until now a pattern that came without any label information got
  the app's own phase suggestions (letters from the phase library) written on its peaks. A suggestion is not an
  identification, so this is no longer done by default. Analysis settings > XRD > Peak labels now offers:
    Only labels from my files (no guessing)   the default. Labels come from a label sheet, or from the peak list /
                                              Bragg table of the same sample (your own refinement). A pattern
                                              without these is drawn without phase labels and without a key.
    Suggest phases from the library (check them)   the earlier behaviour, now only when you choose it.
    2θ values, d-spacings (Å), No labels      as before; 2θ and d are measured values, not interpretations.
  The processing record of a pattern without labels says why it has none. A saved setting from an older version
  ("Phase codes (suggested)") is replaced by the new default.
  OLD EXCEL FILES (.xls) NOW OPEN. A .xls file (Excel 97-2003, for example from PowDLL) needs a reader that was
  not installed with the app. Run_Origin_Plot_App.bat now installs it (xlrd, python-calamine); the app tries, in
  this order: pandas, calamine, xlrd, installing the readers, and Excel itself. If all fail the message says what
  to do (open the file in Excel and save it as .xlsx).
  ONE PATTERN PER COLUMN. An XRD table with one 2θ column and several intensity columns (S1 (Y), S2 (Y), ...)
  now gives one graph per sample, named after the column, instead of only the first column. Columns that repeat
  another column exactly are left out and reported.
  Names such as "15-AB-S4" are kept whole (the leading number was cut off before).

VERSION 5.10
  FIXED: EXCEL FILES WRITTEN BY THE APP WERE BROKEN on computers with the newest pandas (3.1): "Convert files to
  Excel", "Save as one workbook", "Workbook template" and the tables of the paper set produced a 3 KB .xlsx that
  Excel cannot open. The cause was one call that pandas 3.1 no longer accepts; it is corrected and the whole app
  was run again with pandas 3.1.1.
  A workbook is now written under a temporary name and only gets its real name when it is complete, so a failed
  write can never leave a broken file behind.
  Files the app cannot read now say why, in plain words: a HighScore project (.HPF2) is a closed format - export
  the pattern from HighScore as .xrdml, .xy or ASCII; pictures, PDFs and other programs' project files hold no
  table of numbers - export the data as CSV, text or Excel.
  Delete the broken .xlsx files made by version 5.9 and convert again.

VERSION 5.9
  A MENU BAR WITH THE USUAL OPERATIONS.
  File
    New project (Ctrl+N)         empties the list for new work. Your data files and saved results are not touched.
    Open session... (Ctrl+O)     a session you saved, or session.json in the results folder of an earlier run
    Resume last session (Ctrl+R) brings back the list you had when you last drew, started a new project or closed
    Save session... (Ctrl+S)
    Open results folder, Close project, Exit (Ctrl+Q)
  Import and convert
    Add data files... (Ctrl+I)   Excel, CSV, text and instrument files (.xrdml, .brml, .ras, .uxd, .xy, NETZSCH ...)
    Import from an Origin project... (new)   opens an .opju / .opj in Origin, writes each workbook as CSV and adds
                                 them to the list. NOT TESTED in Origin; if it writes nothing, export the workbooks
                                 in Origin (File > Export > ASCII) and add those files.
    Open earlier results (session.json)...
    Convert files to Excel...    .xrdml, .brml, .ras, .uxd, .xy and text files become Excel workbooks next to the
                                 originals: named columns, a File_info sheet (source, instrument, wavelength).
                                 A converted XRD file keeps its wavelength when you add the workbook to the app.
    Save everything in the list as one workbook..., Workbook template...
  Run
    Draw ticked graphs (F5), Draw all graphs (Shift+F5), Preview paper set, Make paper set, Stop (Esc)
  Help
    Guide (F1), Show or hide details, About
  The app reads data. A picture of a graph from another program (PNG, JPG, PDF) cannot be turned into data.

VERSION 5.8
  JOURNAL TEMPLATES AND A PREVIEW OF THE PAPER SET (My graphs, step 3).
  Journal: choose the publisher of your journal. The figures of the paper set (and of every normal Draw) are then
  made at that publisher's column width, page depth and letter size, and an EPS file is written as well:
    Elsevier (Cem. Concr. Res., Constr. Build. Mater. ...)  90 / 140 / 190 mm; 7 pt text, nothing below 6 pt
    Springer (Materials and Structures ...)                 84 / 174 mm, not higher than 234 mm; lettering 8-12 pt
    Royal Society of Chemistry                              83 / 171 mm, not higher than 233 mm; 600 dpi
    Wiley                                                   80 to 180 mm; line art 600 dpi
    Nature journals                                         89 / 136 / 183 mm, not higher than 247 mm; 5-7 pt; lines 0.25-1 pt
    Taylor & Francis, MDPI                                  no width stated: your own sizes are used
  Combined figures, sample pages and graphs with an inset use the double-column width; a single graph uses
  1.5 columns where the publisher has that width, otherwise the double column. A width you type yourself under
  Look and saving wins. If your line weight is outside what the publisher asks for, the plan says so.
  The numbers are the ones on the publishers' own author pages (read November 2026). A journal's own guide for
  authors can differ: check it. PDF, EPS and SVG are vector files; PNG and TIFF are 600 dpi.
  "Preview paper set (PDF)": nothing is drawn in Origin. You get Paper_set\Paper_set_preview.pdf: page 1 lists every
  figure and table with its final size and what the journal asks for; then every figure at its true printed size
  on an A4 sheet, with its draft caption. Look at it, change names / journal / settings, preview again, and press
  "Make paper set" when it is right.

VERSION 5.7
  THE PAPER SET NOW COVERS EVERY KIND OF GRAPH, not only XRD fits. "Make paper set" looks at everything that is
  loaded and makes, for each kind:
    XRD fits        main text: stacked comparison, the sample pages you named, table of phase amounts and Rwp;
                    supplementary: the other sample pages and the stacked profile fits
    XRD scans       main text: the stacked scans (or the single scan); supplementary: each scan on its own
    FTIR            main text: the stacked spectra; table of bands; supplementary: each spectrum
    TG-DTG          main text: the samples overlaid (replicates averaged); table of mass-loss steps with
                    Ca(OH)2 / CaCO3 where assigned; supplementary: each TG-DTG graph
    Particle size   main text: the distributions overlaid; table; supplementary: each one
    Calorimetry     main text: the curves overlaid; table of peak and cumulative heat; supplementary: each one
    Own / XY data   main text: the comparison or the single graph; table of the values
  A kind with one sample puts that single graph into the main text. Figures and tables are numbered in this
  order (Figure 1 ..., Table 1 ...; Figure S1 ... in Supplementary). A results table with more than 40 rows
  goes to Supplementary as Table S. The peak table of an XRD scan is too long for a paper and stays with its graph.
  Paper_set_contents.txt lists every figure and table. Making the set again replaces the earlier figures and
  tables in that folder. All graphs use your settings (orientation, pointers, label size, colours, line weights).

VERSION 5.6
  PAPER SET: everything a paper needs from your XRD fits, with one button.
  On "My graphs", step 3: type the samples whose pages go into the main text (default: PC, Reference, S1)
  and press "Make paper set". In your results folder you get the folder Paper_set with:
    Main_text\
      Figure 1   stacked comparison of all refined samples (one tall page, so six panels stay readable)
      Figure 2-4 the sample pages you named: (a) pattern with assigned peaks, (b) fit, zoom, key to the letters
      Table_1_phase_amounts.xlsx (and .csv): phase amounts (wt%) of every refined sample, amorphous content, Rwp
    Supplementary\
      Figure S1 ... the sample pages of all other samples, and the stacked profile fits (raw materials)
    Paper_set_contents.txt: the list of what is what.
  Each folder has its own Origin project, the publication files (PNG, TIFF, PDF, SVG) and draft captions.
  The amounts in Table 1 are the ones in your files; Rwp is recomputed from the curves. Profile fits (raw
  materials) have no phase amounts and are not in the table. A name the app cannot find is reported.

VERSION 5.5
  THE KEY TO THE LETTERS IS NOW ON THE SAMPLE PAGES. It was missing there. Under the two graphs the page now says
  what each letter on it means (A = alite (C3S)   B = belite ...   R = rutile (int. std.)) and what brackets mean.
  With "Phase names on the peaks" only the codes that stayed letters are listed.
  WHERE THE LEGENDS ARE:
   - curves (Observed / Calculated / Difference): sample pages and stacked figures - the row above the graph;
     single fit graphs - the box in the top corner (with Rwp);
   - letters on the peaks: single graphs - the line "Labels: A = ..." under the title; stacked figures and
     sample pages - under the x axis;
   - every figure: a draft caption with the same key in publication\captions.txt and processing_record.txt.

VERSION 5.4
  ZOOMED INSET IN ORIGIN, the rest of it: the numbers on its axis are now bold and larger (0.85 x the label
  size, so 20 for labels of 24), and its axes and frame are drawn 3.8 pt heavy like its curves.
  New box: Look and saving > "Zoomed inset: axes and frame". The app's own preview and the 'publication' files
  show the zoom with bold numbers and a full-weight frame as well.

VERSION 5.3
  ZOOMED INSET IN ORIGIN: its curves are now sent with a line weight of 3.8 pt and its peak labels with font
  size 24 (your values). Origin draws a small inset layer finer than the main graph, so these larger numbers
  look right there. Both can be changed: Look and saving > "Zoomed inset: curves" and "Zoomed inset: label size".
  The app's own preview and the files in 'publication' are not affected.

  "SAVE AS ONE WORKBOOK..." NOW TAKES EVERY GRAPH, NOT ONLY FIT GRAPHS. Whatever you loaded (Excel, CSV, text,
  instrument files; XRD, FTIR, TGA, particle size, calorimetry, your own tables) is written into one clean
  workbook: a sheet "Graphs" that lists everything, the XRD fit sheets as before, and one sheet per other table
  with the column names (and units) in the first row. Add that workbook to the app and you get the same graphs.
  You do NOT have to convert anything before drawing: the app draws straight from the files you add.

VERSION 5.2
  BIGGER LABELS, CLEARER ZOOM (sample pages):
   - Peak labels on the sample pages are about 40 % larger (as large as in a single graph).
   - The zoomed inset is larger, its curves have the full line weight, its labels are as large as those of the
     main graph, and its axis numbers are larger.
   - Inside the zoom a label stays over its own peak. Peaks that stand out in the zoom are named (at least 5 % of
     its strongest peak); a tiny peak, or one cut off by the edge of the zoom, is left to the single graph.
   - Single graphs with many labels use 12-13 pt letters instead of 10-12 pt.
   - New setting "Peak label size" (Analysis settings > All graphs): Normal, Large (+25 %), Extra large (+50 %).
     Bigger letters need more room, so a crowded graph keeps fewer labels.

VERSION 5.1
  SETTINGS FOR EVERY KIND OF GRAPH. Analysis settings now starts with a block "All graphs". What used to be
  XRD-only holds for XRD, FTIR, TGA, particle size, calorimetry and your own graphs:
   - Page orientation (Landscape / Portrait).
   - Label pointers (thin lines / arrows).
   - Zoomed inset: type a range in the units of the x axis (27-37 for XRD, 800-1200 for FTIR, 400-500 for TGA).
     Every single graph whose data hold that range gets the inset; a graph that does not hold it is left alone.
     It also works on a reversed axis (FTIR). Not on a logarithmic axis (particle size).
   - Samples per figure: for figures with one panel per sample. Curves overlaid on common axes stay together.
  Phase names on the peaks, fit colours and the sample page layout stay under XRD: they only mean something there.

  OWN GRAPH (ANY DATA): a new tab. Any table of numbers can be drawn, also data the app does not recognise.
  Click its line on "My graphs", open the tab "Own graph (any data)", choose the X column and one or several
  Y columns, type the axis titles, tick logarithmic or reversed x if you want, choose line / symbols, and press
  "Draw it this way". "Back to automatic" undoes it. Sessions remember your own graphs.

VERSION 5.0
  ORIGIN DRAWING REBUILT. In Origin, version 4.9 drew graph (a) but left graph (b) empty, without axis numbers and
  without the inset. Every figure is now sent to Origin in the order the first version of this app used
  (which drew its three-layer graphs correctly): 1 all workbooks, 2 the graph window, 3 all its layers,
  4 curves, axes and texts layer by layer. Workbooks are plain (x, y1, y2 ...). Axis numbers are switched on
  for every layer. After each figure the app asks Origin how many curves every layer holds; an empty layer
  is filled a second way. The outcome is in origin_check.txt in your results folder and in the result line.
  IF A GRAPH IS STILL WRONG IN ORIGIN: send origin_check.txt and data_for_origin\origin_commands_log.txt.
  The files in the folder 'publication' are drawn by the app itself and always look like the preview.

  Zoomed inset: now ON for sample pages without typing anything ("Automatic on sample pages": the app takes
  the 10-degree region with the most diffracted intensity, 27-37 for your clinkers). "No inset" switches it off;
  a typed range such as 27-37 also puts the inset into the single graphs.
  On the first tab, under "Several files of the same kind": Page (Landscape / Portrait), Sample pages
  (side by side / one above the other) and Fit colours. A line below says what will be drawn.
  Fit colours: observed black, calculated red, difference blue (the default now, also for single fit graphs);
  the HighScore colours (red / blue) can still be chosen.
  NEW WORKBOOK BUTTONS (step 1):
   - "Workbook template...": an empty-to-fill Excel file in the format the app understands, with one made-up
     sample and a ReadMe sheet that explains every sheet and column. XRD_workbook_template.xlsx in this
     folder is the same file.
   - "Save as one workbook...": writes every fit graph loaded in the app (from any files: CSV, text, Excel)
     into one workbook in that format: Samples, Phases, Peak_Labels, Label_Key and one <Sample>_Profile sheet
     each. That is how XRD_ALL_SAMPLES_combined.xlsx is laid out. Load it back whenever you like.

VERSION 4.9
  SAMPLE PAGES: one page per sample with (a) the measured pattern with its assigned peaks and
  (b) the fit (observed black, calculated red, difference blue below), side by side on a landscape page.
   - "Several files of the same kind" = "Decide for me": the app makes the stacked comparison figures AND one
     sample page for every fit graph. They appear in the list as "Sample page: PC ..." - tick the ones you want.
   - "One page per sample (pattern + fit)": only the sample pages.
   - Analysis settings > XRD > "Sample page layout": Decide for me (side by side on a landscape page, one above
     the other on a portrait page), Side by side, or One above the other.
   - The zoomed inset, the label text (letters / phase names) and the pointers (lines / arrows) apply to the
     pages too.
   - Half a page holds fewer labels: side by side, (a) labels the peaks of at least 8 % of the strongest one,
     and a label that would need a long pointer is left out. The inset and the single graph keep every label.
     "One above the other" gives wider graphs and keeps more labels (5 %).
  Not tested in Origin itself: a page is one graph window with the two graphs as layers side by side.

VERSION 4.8
  Three new choices under Analysis settings > XRD (all off by default, so your graphs stay as they were):
   - Zoomed inset (2-theta range): type for example 27-37. Single XRD and fit graphs get a small zoomed graph
     in the top right corner, on its own intensity scale, with every peak of that range labelled.
     In fit graphs the phase amounts (wt%) then move to a column right of the graph, so the corner stays free.
   - Label text: "Phase names on the peaks" writes C3S, C2S, C3A, C4AF, Calcite ... upright on the peaks instead
     of the letters with a key. Names are long, so the main graph names the peaks of at least 5 % of the
     strongest one; the inset names every peak of its range. Stacked figures keep the letters.
   - Label pointers: "Arrows" draws a small arrow from a moved label to its peak instead of a thin line.
  For a figure like (a) pattern with assigned peaks + (b) refined pattern: draw the fit graph for (b); for (a)
  pick the same graph in the list and choose "XRD" under Graph type (observed pattern only).
  Not tested in Origin itself: the inset is a new small layer; send origin_commands_log.txt if it looks wrong.

VERSION 4.7
  New setting 'Samples per figure' (3 per figure is the default, best quality; also 2, 4 or All in one figure).
  Six clinker/PC samples then become two figures of three tall panels; raw materials stay one figure.
  Choose 'All in one figure' when you want everything in one page.

Origin plot app, version 4.6 (OriginPro 2018 and newer)
=======================================================

Start:  double-click Run_Origin_Plot_App.bat
        (or drag one or more data files onto Run_Origin_Plot_App.bat)

VERSION 4.6: PROFILE FITS NAMED AS SUCH
  - A Samples sheet may have a column "Calculated_curve" (or "Fit type"). When it says the
    curve is a profile fit / empirical / without crystal structure, the graph writes
    "Rwp (profile fit) = ..." and does not ask for phase amounts.
  - Landscape stacked figures label peaks from 5 % of the strongest peak (portrait: 10 %).
  - If graphs cannot be combined, the line now starts with !! so it is not overlooked.
  - examples_your_data\XRD_ALL_SAMPLES_combined.xlsx now holds your latest raw-material
    data (the profile fits and labels of your raw-material workbook).

VERSION 4.5: LANDSCAPE PAGES
  - Every figure is drawn on a landscape page, in Origin and in the publication files.
    Analysis settings > "Page orientation" chooses Landscape (default) or Portrait.
  - Stacked fit figures in landscape: each group of samples (the Group column of the
    Samples sheet) is one figure with up to six panels, e.g. clinkers + PC in one figure
    and the raw materials in another. Observed and calculated stay together in one panel
    with the difference curve under them. With more than three panels the panels are
    short: sample name and Rwp share one line and labels are smaller. Portrait gives the
    tall figure with roomier panels.
  - Single graphs, TG-DTG and overlays were already landscape and stay so in both settings.

VERSION 4.4: ONE STRICT PUBLICATION STYLE
  - Every drawing run now also saves, for every graph, files made by the app itself in the
    subfolder "publication": PNG and TIFF at 600 dpi, PDF and SVG (text stays text, fonts
    embedded). They do not depend on Origin: if Origin does not start, they are still made.
    captions.txt in the same folder holds the size and a draft caption of each figure.
  - Exact printed size: 140 mm wide for one graph, 175 mm for stacked or combined figures
    (never taller than 236 mm), or your own width (Look and saving > Width, e.g. 85 or 90).
  - One style everywhere: Arial (sans-serif); 8-9 pt axis text, 7-8 pt tick numbers, peak
    labels never below 5.5 pt; ticks pointing in on all four sides with minor ticks; no
    title inside the figure (it belongs in the caption); black text; true minus signs;
    superscripts and subscripts typeset (cm-1, CaCO3, Rwp).
  - Colours for several series: the Okabe-Ito set (readable for colour-blind readers and in
    print). Two samples in one figure never share a colour.
  - Phase legend: colour squares only when tick rows of those colours are drawn.
  - Line weights stay as you set them (1.5 pt curves and frame). At 140 mm this is heavier
    than most journals print; 1.0 for curves and 0.75-1.0 for the frame is the usual range.
    Change it under Look and saving if a journal asks.
  - Origin: superscripts/subscripts are sent in Origin's own notation. The Origin graphs
    follow the same layout, but only the app's own files were checked by eye.

VERSION 4.3: TG-DTG FROM INSTRUMENT FILES
  - NETZSCH text exports (lines starting with #, column line starting with ##) are read:
    temperature, time, mass %, DSC, DTG; sample name, start mass and heating rate come from
    the header. The same should work for other exports of this '#KEY: value' kind, but only
    the NETZSCH STA 449 file you sent was tested.
  - TG and DTG are ONE graph: mass (%) on the left axis, DTG on the right axis. DTG is drawn
    as it is (mass loss = negative, shown as dips), in %/min, from the instrument's own DTG
    column when the file has one. (When several TGA files are overlaid, TG and DTG are two
    stacked panels, because two axes cannot be read with several curves.) In Origin the
    right axis is a second layer on top of the first; this part has not been run in Origin.
  - Older text of this entry: mass (%) on top, DTG below, sample name, start mass and heating rate in
    the corner, every DTG peak labelled with its temperature and the mass lost in that step.
    Steps with a DTG peak at 400-570 C are marked CH (Ca(OH)2) and 570-900 C CC (CaCO3) as a
    suggestion; the amounts are in the _analysis.csv. Your own fixed ranges (Analysis
    settings) replace this.

VERSION 4.2: CLEAN STACKED FIGURES (default)
  - Stacked fit figures now draw as a clean publication figure: observed black, calculated red,
    difference blue under the pattern, sample name and Rwp top right, a short key below.
    Only your own checked labels from the label sheet are used, and only for peaks of at
    least 10 % of the strongest peak (plus bracketed phases without a resolved peak).
    Analysis settings > "Stacked fit figures" brings back the Detailed version (tick rows and
    wt% beside each panel). Single graphs still label every peak.

VERSION 4.1: STACKED FIGURES IN ORIGIN, TICK BOXES, EVERY PEAK LABELLED
  - Stacked figures in Origin: a text placed at a negative height (the amounts beside a
    panel, the phase key under the axis) was sent to Origin in a form it reads as an option.
    Those texts were lost and the curves after them were not drawn. Fixed.
  - Window names in Origin are now short and never cut (G1a, D2a ...). The first app used
    short names (SC4, SOPC) and its stacked figures drew; the newer app cut long names to 13
    characters and numbered them (DCombinedFit2), and exactly those panels stayed empty.
    The readable name is the window title; origin_commands_log.txt lists which is which.
  - The app now asks Origin after every curve whether it was really drawn. If not, it tries
    a second way (plotxy) and, if that fails too, says so in the result line ("CURVES WERE
    NOT DRAWN"). Every command and whether Origin accepted it is written to
    data_for_origin\origin_commands_log.txt in the results folder: send that file if a graph
    is still wrong.
  - Tick boxes in the list: click a line to tick it and see it; click again to untick.
    Shift+click ticks everything in between. "Tick all" / "Untick all" are above the list.
    "Draw N ticked" draws exactly the ticked graphs.
  - Every peak is labelled: "Peak labels (all, or a number)" is "all" by default. Labels from
    your label sheet are kept; every other measured peak that the peak list of the same
    sample explains gets its phase label too (phases giving at least 30 % of the calculated
    intensity at the peak, at most two). With many labels the letters get smaller. Small
    bumps that no reflection explains get no label (a label there would be a guess); their
    number is written in processing_record.txt and they are in the analysis table.
    Type a number (for example 15) to go back to the strongest peaks only.

VERSION 4.0: MADE PREDICTABLE (after the UI/UX review)
  Correctness
  - "Draw N ticked" and "Draw all N" (top right and in step 4) say exactly what will be
    drawn. Nothing is drawn by surprise.
  - Changed a setting? "Settings changed - applied when you draw" appears at the top. Drawing
    first applies the settings to all graphs, so the graphs and processing_record.txt always
    agree. "Apply to all my graphs" / "Refresh previews" apply them at once.
  - The selection follows the graphs, not the row numbers, when the list is regrouped.
  - Every run ends with the truth: "16 of 18 drawn · 2 FAILED: <names> · 3 notes to check",
    and says how many Origin commands were not accepted. Problems open the details by themselves.
  - Sessions also remember files that only hold names or phase amounts, and list every
    file that is missing when a session is opened.
  Responsiveness
  - Files are read and analysed in the background, with progress ("Analysing graph 4 of
    18") and a Cancel button; drawing in Origin shows "Drawing graph 3 of 12" and can be
    cancelled between graphs. Closing the window while it works asks first.
  - The launcher installs the Python packages only when one is missing (no upgrade on
    every start).
  - Dated result folders are named to the second.
  Interface
  - Zoom, pan, reset view and the coordinates under the mouse: toolbar under the preview.
  - Stacked figures are previewed in the proportions of the exported page.
  - With several lines selected, the preview shows the line you clicked.
  - Graph type and sample name are greyed out for combined figures (they belong to single
    graphs). "Remove" on a combined figure hides it; its single graphs stay.
  - The list has a scrollbar. The detailed log is folded away ("Show details").
  Not done yet (needs checking on a real Windows screen step by step): the graph-first
  layout with a collapsible settings panel, search/filter and separate sections in the
  list, dragging labels in the preview, scrollable settings pages and a draggable divider,
  a portable project package.

WHERE TO PRESS
  Add your files with "Add files..." (or click the empty list). Select the graphs you want
  (Ctrl+click for several) and press "Draw N selected", or press "Draw all N".

BRAGG TABLES WITH ONE COLUMN PER PHASE
  A sheet with column pairs such as "M3-C3S_2theta" / "M3-C3S_marker" (positions only, no
  intensities) is read as the Bragg positions of that sample. It gives the tick rows and
  limits the phase labels to the phases of your refinement (an internal standard, rutile
  or zincite, is added only if it has several peaks of its own). Because such a table
  lists every reflection, rows of phases in the library are thinned to the reflections
  with at least 1.5 % relative intensity; the processing record says how many were kept.

PHASE AMOUNTS (wt%)
  The app shows the amounts wherever it finds them: in the legend of each fit graph
  ("Calcite  85.8 wt%"), in the column next to each panel of the stacked figures
  ("A 56.1, B 20.7, ... Amorph. 15.0 wt%"), and in <graph>_quantification.csv.
  It reads them from a table in your files, in any of these forms:
    - long:  Sample | Phase | (Code) | wt%          one row per phase per sample
    - wide:  Phase | S3 | S2 | S1           one column per sample
    - one sample: Phase | wt%                        in the same workbook as that sample
  The table can be in the same workbook as the curves, or in a separate file that holds
  only the amounts (it is then used for all loaded graphs). Sample names are matched like
  the graph names (C1_Profile = C1, REAL Quartz = Quartz).
  phase_amounts_template.csv shows the long form; replace the EXAMPLE rows with yours.
  If no amounts are found for a sample, the log says so.
  Note: amounts come from a quantification (Rietveld). An empirical profile fit has none
  of its own; if you add amounts to a profile-fit graph, say in the caption where they
  come from.

NEW IN VERSION 3.2
  - No fixed sample list any more. The old "Rietveld project" tab (always the same nine
    example samples, read from a workbook inside the app) is gone. Every figure now comes
    from the files you load, so new data always gives new figures.
  - Names are suggested from your files: "REAL Quartz" -> Quartz, "C1_Profile" -> C1,
    or the display name of a Samples sheet ("Sample A (4 % additive)"). Type your own under
    "Sample name" if you want.
  - Information sheets are read, not drawn: a Samples/Statistics sheet (display name, Rwp,
    amorphous, Group), a Phases sheet (phase names, wt%, colours) and a label key.
  - Fit graphs in a HighScore look: observed red, calculated blue on top, phase legend
    with wt% and coloured squares, "Counts", "Position [°2θ] (Copper (Cu))".
  - A Group column (for example "Clinkers and PC" / "Raw materials") decides which
    samples are drawn together in combined figures.

NEW IN VERSION 3.1: MUCH SMARTER XRD (details in "XRD" further down)
  - HighScore exports are read correctly: observed and calculated intensity are paired in
    the same unit (counts with counts), background and ESD are used, Rwp is shown.
  - Peak lists (Pos, Height, Phase Assignment) are recognised and drawn as sticks, and are
    linked automatically to the pattern of the same sample: exact phase labels + Bragg
    tick rows from your own refinement.
  - Instrument files: .xrdml, .brml, .uxd, .ras (wavelength taken from the file), and
    .xy/.dat/.txt with or without headers.
  - Background (SNIP), noise from counting statistics, K-alpha2 shoulders never labelled.
  - Phase suggestions by a whole-pattern match against a library built from your own 9
    refinements (19 phases); you can add phases. Weakly supported phases get a "?".
  - Labels never overlap and sit on their peaks; stacked XRD figures keep phase labels.

NEW IN VERSION 3
  - Analysis settings tab: X-ray wavelength, TGA mass unit, FTIR signal type, fixed TGA
    ranges with Ca(OH)2 / CaCO3, cumulative heat at chosen ages.
  - Replicates: mean with SD band for curves, mean with error bars for tables such as strength.
  - Sample names: one colour per sample in every combined figure.
  - Figure for a paper: panels (a), (b) ... at an exact width in mm.
  - processing_record.txt: what was done to every graph, with a draft caption.
  - Sessions: save and reopen the whole list.
  - Combined figures now check units and say on the figure when curves were scaled.

TAB "My graphs"
  1. "Add files..."  - Excel (.xlsx/.xls), CSV, TXT or DAT. Add as many as you like.
     Every sheet is examined; the list shows each graph it can draw and what it thinks it is.
  2. Click a line in the list to see the preview on the right. The analysis table for
     that graph is printed in the log box.
  3. If it guessed the wrong kind of graph, pick the right one under "Graph type for the
     selected sheet".
  4. Select the graphs you want (Ctrl-click / Shift-click) and press "Draw selected in
     Origin", or "Draw all in Origin". Origin starts by itself; the project is saved under
     the name you gave, each graph is exported as PNG/PDF, and each analysis table is saved
     as <file>_<sheet>_analysis.csv in the output folder.

  What it recognises (from the column headers and units) and what it calculates
     XRD            2theta + intensity (see "XRD" below).
     XRD peak list  positions + heights (+ phase): drawn as sticks, one colour per phase.
     Fit            observed + calculated columns: pattern, Bragg tick rows (if a peak
                    list of the same sample is loaded), difference curve, Rwp.
     FTIR           wavenumber + absorbance or transmittance. Axis runs 4000 -> 400,
                    bands are labelled (maxima for absorbance, minima for transmittance).
     TGA            temperature (or time) + mass. Converts mass to %, calculates the DTG
                    curve, labels each DTG peak with its temperature and the mass loss of
                    that step, and lists the steps, total loss and residual mass.
     Particle size  size + volume % (or cumulative %). Log size axis, distribution and
                    cumulative curve, D10 / D50 / D90, span and mode.
     Calorimetry    time + heat flow. Labels the main peak; if the units are recognised
                    (time in s/min/h, heat flow in mW/g or W/g) adds cumulative heat in J/g.
     XY             anything else: all numeric columns against the first/X column.
                    Curves on very different scales get one panel each; few points are
                    drawn as line + symbol.
  Peak labels
     - Peak positions come from the data: a peak must stand out from the noise, and its
       position is refined between the measured points (tested: within 0.002 deg on a
       0.013 deg step pattern).
     - If the file has a label sheet (a text column + a position column, optionally a
       sample column), those labels are used instead and each is moved onto the real peak
       top next to it. A label with no clear peak there is reported in the log.
     - XRD phase labels: see "XRD" below.

XRD
  Files      HighScore csv/txt exports (profile with Icalc/Iback/ESD, or plain scan), peak
             lists, .xrdml (PANalytical), .brml and .uxd (Bruker), .ras (Rigaku), and two-
             column .xy/.dat/.txt files without headers. Binary .raw files: export them as
             .xy or .xrdml first.
  HighScore  A HighScore profile export has the same intensity in counts and in cps. The
             app always pairs columns of the same unit: Intensity [Counts] or Iobs [cts]
             with Icalc [cts] and Iback [cts]. Rwp is recomputed (w = 1/ESD^2, or 1/Yobs
             without ESD) and printed on the graph; it matches HighScore.
  Peaks      1. background by the SNIP algorithm (anything broader than about 2 deg, such
                as an amorphous hump, is background);
             2. noise from counting statistics (sqrt of the background);
             3. a peak needs signal/noise >= 5 and at least 1 % of the strongest peak;
                its position is refined between the measured points; FWHM is measured;
             4. a peak at the K-alpha2 position of a stronger peak, with about half its
                height, is marked as the K-alpha2 partner and never labelled.
             The curve drawn is always your measured data, never smoothed.
  Phases     a) Best: load the HighScore peak list of the same sample (the csv with
                Phase Assignment) together with the pattern. Same sample name = linked
                (C1.csv in two folders, or C1_profile + C1_peaks, or C1_Profile +
                C1_Bragg sheets). Labels then come from your refinement, and the graph
                gets one row of Bragg ticks per phase.
             b) Without these the pattern gets NO phase labels (since version 5.11).
                Only if you choose "Suggest phases from the library" under Peak labels
                does the app suggest phases: every library phase is turned into a
                calculated pattern (its lines broadened like your peaks, with K-alpha2),
                a small zero shift is scanned, and your pattern (minus background) is
                fitted with non-negative amounts of the phases. A phase is kept only if
                the fit gets clearly worse without it AND it has a peak of its own.
                A phase without a strong peak of its own is labelled with "?".
                In tests the main phases are found; minor phases and belite without a resolved peak
                (your "(B)") can be missed; feldspars can be confused with each other.
                Choose "Phases to look for" (clinker set, raw-material set or your own
                codes) - this removes most wrong suggestions.
             These suggestions are NOT an identification or a quantification. The table
             <graph>_phases.csv gives each phase's share of the fitted peak intensity
             (not wt%), its own peaks and a confidence.
  Library    xrd_phase_library.csv: d-spacings and relative intensities of 19 phases from
             your own HighScore refinements (alite, belite, alpha'H-C2S, C3A, C4AF, lime,
             periclase, gypsum, rutile, quartz, albite, microcline, K-feldspar, muscovite,
             biotite, cordierite, calcite, dolomite, zincite). Because it stores d-spacings
             it works for any X-ray tube. Add a phase (for example portlandite, ettringite)
             by putting its peak list (d or 2theta, I %) as "Portlandite (CH).csv" into the
             folder phase_library (export it from the reference card in HighScore), or
             with XRD tools > Phase library > Add phase from file. New phases of
             the files you load are stored by the app itself (see VERSION 5.12).
  Labels     Analysis settings > Peak labels: phase codes, 2theta values, d-spacings or
             none. The key (A = alite (C3S), ...) is printed above the graph. Labels sit
             above their peak; if there is no room they move up or a little sideways with
             a thin leader line.
  Stacking   Patterns with different X-ray tubes are never stacked together. Start file
             names with a number (1_Reference, 2_S1, ...) to set the order from the
             bottom up; the number is not shown.

SEVERAL FILES AT ONCE: STACK OR OVERLAY?
Add as many csv / txt / xlsx files as you like in one go. Graphs of the same kind
whose x ranges overlap are also drawn together in one figure. These combined
figures are at the top of the list, marked with a star. Every single graph stays
in the list too, so you choose what to draw.

With "Several files of the same kind" set to "Decide for me", the app follows the
usual convention for each measurement:
  XRD patterns          stacked with an offset, each scaled to its own maximum,
                        sample name above each trace. Overlaid patterns hide
                        each other's peaks.
  FTIR spectra          stacked with an offset, to compare band by band.
  Fits (obs + calc)     one panel per sample with its own difference curve.
  TGA                   overlaid on common axes (mass on top, DTG below), so the
                        mass losses can be read against each other.
  Particle size         overlaid on one log size axis (distribution + cumulative).
  Calorimetry           overlaid on one time axis (heat flow + cumulative heat).
  Other x-y data        overlaid, only if the axis names are the same.
Files are grouped only if they are the same kind and share at least half of
their x range. At most 8 curves are stacked or overlaid in one figure and at most
6 fit panels; more files are split over several figures.
You can overrule this: "Stack them", "Overlay them" or "Keep them separate".
The message box says what was combined and why. The analysis table of a combined
figure has a Sample column. Stacked figures carry no peak labels (they would
collide); the single graphs keep theirs. Stacked intensities are scaled per
sample, so compare positions and shapes there, not absolute heights.
Samples are drawn in the order of the list (file name order when added together).

TAB "Analysis settings"
  The app shows the choices it makes for you, and you can correct them here. Press
  "Apply to all my graphs" after a change.
  XRD   X-ray tube: Automatic (from .xrdml/.brml/.ras/.uxd files, else Cu Ka1), Cu, Co,
        Fe, Cr, Mo, Ag, or type a wavelength in A. Peak labels: phase codes / 2theta /
        d-spacing / none. Phases to look for: all, clinker set, raw-material set, or type
        your own codes after a colon (Mine: A B C F CH). Background: not drawn / drawn /
        subtracted.
  TGA   Mass column: Automatic / already in % / absolute, convert to % of the first point.
        Mass-loss ranges in deg C, for example   40-105, 105-400, 400-500 CH, 600-800 CC
        Empty = ranges are found from the DTG peaks. With ranges, the loss is the
        difference of the measured TG curve at the two limits (step method, no tangential
        correction), per mass at the start. CH after a range gives Ca(OH)2 = loss x
        74.09/18.02, CC gives CaCO3 = loss x 100.09/44.01. Every loss inside the range is
        counted, so these are upper estimates. Check the limits on your own DTG curve.
  FTIR  Signal: Automatic / Absorbance / Transmittance (labels at maxima or minima).
  Calorimetry   Cumulative heat at chosen ages in hours (for example 24, 48, 72, 168),
        and the time where the integration starts (0 = first data point; 0.75 leaves out
        the first 45 minutes). The heat flow is used as normalised in your file.
  Replicates    Overlaid replicate curves as "mean with SD band" or "every curve".

REPLICATES AND UNCERTAINTY
  Curves (TGA, particle size, calorimetry): graphs with the same sample name are
  replicates. File names that end in _rep1, _run2, _trial3, (2) ... get the same sample
  name by themselves; otherwise select the graphs, type a name in "Sample name" and press
  Apply. In the combined figure the line is the mean and the band is +/- 1 standard
  deviation. A table <name>_replicates_mean_SD.csv gives mean and SD of the results; for
  TGA this needs fixed ranges, so that every replicate has the same rows.
  In Origin the band is drawn as two thin lines (its upper and lower edge).
  Tables (strength and similar): a table with a text column (Mix), an x column with
  repeated values (Age) and a value column (Strength) is drawn as mean with +/- SD bars
  and the individual values as small symbols. The analysis table has n, mean, SD, 95 %
  confidence interval, the individual values and, if one series is called Reference or
  Control, the percentage of that reference. Try examples_synthetic\strength_replicates.csv.

SAMPLE NAMES AND COLOURS
  Each sample name gets one colour, used in every combined figure. Give the XRD, TGA
  and calorimetry files of one mix the same sample name to keep its colour everywhere.

FIGURE FOR A PAPER
  Select 1 to 9 graphs (Ctrl+click), set the width in mm (for example 85 for one column,
  175 for two) and press "Make panel figure". The figure appears at the top of the list.
  When drawn it is saved at exactly that width as PNG (600 dpi), PDF and SVG with editable
  text, with (a), (b) ... on the panels and no titles. Sentences that normally stand above
  a graph (for example what a calculated curve is, or that traces were scaled) go into the
  draft caption instead, so keep them in your caption.
  The app also asks Origin to merge the same graphs into one window (merge_graph). This
  has not been tried on a real Origin yet. If Origin refuses, use Graph > Merge Graph
  Windows; the saved figure files are complete either way.

PROCESSING RECORD AND SESSIONS
  Every run writes processing_record.txt (and .json) into the results folder. For each
  graph it lists the data file (size, date, checksum), the columns used, every choice and
  calculation, things to check, and a draft caption to edit. Your data files are never
  changed.
  session.json is saved with every run. "Save session..." and "Open session..." (top right)
  store and restore the file list, graph types, sample names, settings and panel figures.
  The data files must still be where they were, or next to the session file.

COMBINED FIGURES: CHECKS
  Files are only combined if their x units agree (hours with hours), and overlays only if
  the y units agree. Stacked and per-panel figures say on the figure that each trace was
  scaled. If files name their y axes differently, the log asks you to check.

FIT GRAPHS (observed + calculated)
  Look (Analysis settings > Fit graphs look like):
    HighScore look (pattern + difference curve)   Default. Observed red, calculated blue drawn
                                         on top (as in HighScore), legend box with the sample
                                         name, the curves, the phases (+ wt% if your file has
                                         them) and Rwp; the difference curve (Yobs - Ycalc)
                                         in its own panel underneath.
    HighScore look + Bragg tick rows     the same, plus one row of Bragg ticks per phase
                                         (when a peak list of the sample is loaded).
    HighScore look, pattern only         no difference curve (like HighScore's main view).
    Paper style                          calculated dark red underneath, observed black on
                                         top (so the red never hides the measurement), tick
                                         rows, difference in blue.
  STACKED FIT FIGURES (several samples, "one panel each"): a publication layout that
  combines GSAS-II and HighScore. One panel per sample, panels touching and sharing the 2θ
  axis (first sample at the bottom). In each panel: observed (red) and calculated (blue,
  on top) scaled to the maximum of that pattern; Bragg tick rows below the pattern, one
  colour per phase (from the peak list of each sample); the difference curve (teal) offset
  below the ticks; sample name and Rwp top right; phase labels on the strongest peaks.
  One legend row above the figure and a colour-coded phase key below the 2θ axis, no title
  or notes on the figure. In Origin the page is 7 inches wide and about 1.55 inches per
  sample high. Which samples go together comes from the Group column of your Samples sheet.
  The legend box goes to the top corner (left or right) where it covers no data; the
  y axis is raised just enough for it.
  Rwp is always recomputed from the observed and calculated columns of the file you
  loaded. If your file also writes an Rwp (for example a Statistics sheet), the log says
  when the two differ.
  Where names and wt% come from: an information sheet in the same file. A file that holds
  only information sheets (no curves) is used for the graphs of all loaded files. A sheet
  from another data file is never used, so two workbooks of the same samples (for example
  a Rietveld refinement and a profile fit) never mix their Rwp, wt% or Bragg ticks, and
  their fits are never combined into one figure.

WHY RWP CAN DIFFER BETWEEN TWO GRAPHS OF THE SAME SAMPLE
  It belongs to the calculated curve, not to the sample.
  Both use the same measured Yobs; only Ycalc differs. A profile fit (free peaks, no
  crystal structure) always reaches a lower Rwp and is not a Rietveld refinement. The app
  prints the "Calculated curve:" sentence from the workbook's Notes sheet above those graphs.

TAB "Look and saving"
  - Where results are saved: choose any folder (default: Documents\Origin plot results).
    The same folder can be chosen in step 3 of "My graphs". "Open results folder" at the
    bottom of the window opens it.
  - Optional dated subfolder per run, so nothing is overwritten.
  - Save as PNG and/or PDF. The Origin project (.opj) and analysis tables (.csv) are
    always saved. The project name is set in step 3 of "My graphs".
  - Line weights: curves and axes 1.5 pt, tick rows and leader lines 0.75 pt.
  Your choices are remembered for next time (settings.json next to the app).

FOLDER examples_your_data
  Your own workbooks (this folder is never published):
  They are NOT loaded automatically; add them with "Add files..." like any other data.

FOLDER examples_synthetic
  Made-up XRD, TGA (also three replicates), FTIR, particle-size, calorimetry and strength
  files (also with three specimens per age) to try the app with. They are not real
  measurements.

GOOD TO KNOW
  - Needs Windows, Origin/OriginPro 2018 or newer, and Python 3 (tick "Add python.exe to
    PATH" when installing). Keep all files of this folder together.
  - If Origin does not start: run Origin once as administrator, close it, try again.
  - "(Origin refused: ...)" in the log = a single command this Origin version did not
    accept; the run continues. Lines starting with "!!" are real errors.
  - The log is saved as last_run_log.txt. Send it back if a graph is wrong.

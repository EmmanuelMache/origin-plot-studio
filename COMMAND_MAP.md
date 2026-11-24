# COMMAND_MAP – where every command is

Part 1 lists the commands that moved or are new in the upgrade (old place → new place, shortcut, tooltip).
Part 2 is the full inventory of the running window, written by `tools/command_inventory.py`. **No command was removed.**

## Part 1 – moved and new

| Command | Old place | New place | Shortcut | Tooltip |
|---|---|---|---|---|
| File menu | top bar, right | **top bar, far left** | – | File: new, open, recent, save, import, export, convert, clear / start afresh, exit |
| Save | ribbon quick bar; File ▸ Save session… | top bar, beside File; File ▸ Save | Ctrl+S | Save the session to its file (asks where the first time). Disabled: nothing is loaded yet |
| Save session as | File ▸ Save session… (Ctrl+S) | File ▸ Save session as… | Ctrl+Shift+S | Save the session under a new name |
| Undo / Redo | ribbon (a graph's look only) | top bar, beside File (whole app); ribbon ▸ Home ▸ Editing | Ctrl+Z / Ctrl+Y | Undo the last thing done: a removal, a clearing, or a change of a graph's look |
| Search commands | – (new) | top bar, right | Ctrl+Q | Type a part of a command's name and press Enter |
| Exit | File ▸ Exit (Ctrl+Q) | File ▸ Exit | Alt+F4 | Ctrl+Q is the command search now |
| Recent sessions | – (new) | File ▸ Recent sessions | – | The last ten session files |
| Clear graph | Delete key; right-click ▸ Remove | File ▸ Clear / Start afresh ▸ Clear graph (also Delete) | Del | Remove the graph on show from the list (the file stays). Undo: Ctrl+Z |
| Clear all graphs | – (new) | File ▸ Clear / Start afresh | – | Remove every graph from the list; settings and layout stay. Undo: Ctrl+Z |
| Remove ticked graphs | – (new) | File ▸ Clear / Start afresh | – | Remove the ticked graphs from the list. Undo: Ctrl+Z |
| Start afresh | File ▸ New project | File ▸ Clear / Start afresh ▸ Start afresh… (New project stays) | Ctrl+N | An empty session: keep settings and layout, or reset the layout too |
| Reset layout | View ▸ Reset layout | View ▸ Reset layout; File ▸ Clear / Start afresh ▸ Reset layout | – | Put every panel back where it was at the first start |
| Recover last session | File ▸ Resume last session | File ▸ Clear / Start afresh ▸ Recover last session (Resume stays) | Ctrl+Shift+R | Bring back the session the app saved by itself |
| Templates | – (new) | **Graph gallery** ▸ switch at the top: Templates · Workbook graph types (26) | – | Graph = template × style × your data. One Graph gallery entry in the top bar |
| Preview | – (new) | Templates ▸ action bar | – | Draw every ticked combination of files, templates and styles from your data |
| Open all in editor | – (new) | Templates ▸ action bar | – | Open every kept graph in the editor |
| Draw all in Origin like this | – (new) | Templates ▸ action bar; right-click a preview | Ctrl+Shift+O (on Templates) | Send every kept graph to Origin as the same graph; each saved as {sample}_{template}.opju |
| Export all… | – (new) | Templates ▸ action bar; right-click a preview | Ctrl+Shift+E (on Templates) | Save every kept graph at the journal size and dpi of its style |
| Combine into one figure… | – (new) | Templates ▸ action bar | Ctrl+Shift+G (on Templates) | 1×2, 2×2, 2×3, stacked or your own grid, with panel letters |
| Data and results of all → one Excel workbook | – (new) | Templates ▸ More ▾ | – | One sheet per file and the list of graphs |
| Apply the first ticked style to all kept graphs | – (new) | Templates ▸ More ▾ | – | Every kept graph is redrawn in that style |
| Save as my template… | – (new) | Templates ▸ More ▾; right-click a preview; editor | – | Template + style + variants as your own template, in your private folder |
| Export / Import a template (.opst) | – (new) | Templates ▸ More ▾ | – | One file with the JSON, the preview and the Origin script |
| Build Origin templates (.otpu) | – (new) | Templates ▸ More ▾ | – | Needs Origin: stores each ticked template as an Origin graph template |
| FTIR spectra stacked / overlaid; Stack / Overlay the ticked graphs; XRD drawing, particle size and modelling entries | Graph gallery list (and Analysis) | **Analysis only** (FTIR; Figures from several graphs; XRD; Particle size; Thermodynamic modelling) | – | listed once |
| Panel: Fold / Float / Close | (close button hidden) | title strip of every panel: ▾ ⧉ ✕ | – | Fold away, float, close; View ▸ Panels reopens |
| Draw my data like this | – (new) | Graph gallery ▸ Templates, blue button; right-click a picture | – | Draw the ticked files in the ticked template pictures |
| + Add template | – (new) | Graph gallery ▸ Templates | – | From my graph, as a copy of a ticked template, from a .opst file |
| TGA / DTG analysis | Analysis ▸ TGA (mass loss in intervals stays) | Tools ▸ TGA / DTG analysis… | – | Zones, stepwise and tangent mass loss, Ca(OH)₂ / CaCO₃, Excel |
| Open a saved session | Ctrl+Shift+O everywhere | Ctrl+Shift+O everywhere except on Templates (there: Draw all in Origin) | Ctrl+Shift+O | File ▸ Open session… works in every section |

## Part 2 – full inventory (written by the app)

| Command | Location | Shortcut | Tooltip |
|---|---|---|---|
| Save | Top bar ▸ File | Ctrl+S | Save the session to the file in use (asks where the first time) |
| (no saved session yet) | Top bar ▸ File ▸ Recent sessions |  |  |
| Clear graph | Top bar ▸ File ▸ Clear / Start afresh |  | Remove the graph on show from the list (the file stays). Undo: Ctrl+Z |
| Clear all graphs | Top bar ▸ File ▸ Clear / Start afresh |  | Remove every graph from the list; settings and layout stay. Undo: Ctrl+Z |
| Remove ticked graphs | Top bar ▸ File ▸ Clear / Start afresh |  | Remove the ticked graphs from the list (their files stay on the disk). Undo: Ctrl+Z |
| Start afresh… | Top bar ▸ File ▸ Clear / Start afresh |  | An empty session: keep settings and layout, or reset the layout too. Undo: Ctrl+Z |
| Reset layout | Top bar ▸ File ▸ Clear / Start afresh |  | Put every panel back where it was at the first start |
| Recover last session | Top bar ▸ File ▸ Clear / Start afresh |  | Bring back the session that the app saved by itself (every few minutes and when it closes) |
| New project | Top bar ▸ File | Ctrl+N |  |
| Add data files… | Top bar ▸ File | Ctrl+O | Add data files	Ctrl+O |
| Open session… | Top bar ▸ File | Ctrl+Shift+O | Open session	Ctrl+Shift+O |
| Resume last session | Top bar ▸ File | Ctrl+Shift+R |  |
| Save session as… | Top bar ▸ File | Ctrl+Shift+S | Save the session under a new name |
| Import from an Origin project… | Top bar ▸ File |  | Import from an Origin project |
| Convert files to Excel… | Top bar ▸ File |  | Convert files to Excel |
| Save everything as one workbook… | Top bar ▸ File |  | Save everything as one workbook |
| Workbook template… | Top bar ▸ File |  | Workbook template |
| Make a gallery graph template… (G01–G24, C01, C02) | Top bar ▸ File |  | Make a gallery graph template (G01–G24, C01, C02) |
| Refresh previews | Top bar ▸ File |  |  |
| Open results folder | Top bar ▸ File |  |  |
| Exit | Top bar ▸ File |  |  |
| This graph: PNG 600 dpi · TIFF · PDF · SVG | Top bar ▸ File ▸ Save and export | Ctrl+E |  |
| The view on screen as a picture… | Top bar ▸ File ▸ Save and export | Ctrl+Shift+E | The view on screen as a picture	Ctrl+Shift+E |
| Copy the view to the clipboard | Top bar ▸ File ▸ Save and export | Ctrl+Shift+C |  |
| Data table as CSV or Excel… | Top bar ▸ File ▸ Save and export |  | Data table as CSV or Excel |
| Results table as CSV or Excel… | Top bar ▸ File ▸ Save and export |  | Results table as CSV or Excel |
| Session… | Top bar ▸ File ▸ Save and export | Ctrl+S | Session	Ctrl+S |
| Open a session… | Top bar ▸ File ▸ Save and export | Ctrl+Shift+O | Open a session	Ctrl+Shift+O |
| The chat as a text file… | Top bar ▸ File ▸ Save and export |  | The chat as a text file |
| Open the results folder | Top bar ▸ File ▸ Save and export |  |  |
| Side bar | Top bar ▸ View | Ctrl+1 |  |
| Your graphs | Top bar ▸ View | Ctrl+2 |  |
| Graph settings | Top bar ▸ View | Ctrl+3 |  |
| Assistant | Top bar ▸ View | Ctrl+4 |  |
| Focus on the graph | Top bar ▸ View | F11 |  |
| Show everything | Top bar ▸ View |  |  |
| Your graphs as its own window | Top bar ▸ View |  |  |
| Graph settings as its own window | Top bar ▸ View |  |  |
| Assistant as its own window | Top bar ▸ View |  |  |
| Put the panels back in place | Top bar ▸ View |  |  |
| Workspace: Your graphs | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Graph | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Graph settings | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Data | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Results | Top bar ▸ View ▸ Panels |  |  |
| Workspace: Details | Top bar ▸ View ▸ Panels |  |  |
| Analysis: Analyses | Top bar ▸ View ▸ Panels |  |  |
| Analysis: Setup | Top bar ▸ View ▸ Panels |  |  |
| Analysis: Preview and results | Top bar ▸ View ▸ Panels |  |  |
| Analysis: Gallery | Top bar ▸ View ▸ Panels |  |  |
| Graph gallery: Graph types | Top bar ▸ View ▸ Panels |  |  |
| Graph gallery: Setup | Top bar ▸ View ▸ Panels |  |  |
| Graph gallery: Preview and results | Top bar ▸ View ▸ Panels |  |  |
| Graph gallery: Gallery | Top bar ▸ View ▸ Panels |  |  |
| Templates: Files | Top bar ▸ View ▸ Panels |  |  |
| Templates: Columns | Top bar ▸ View ▸ Panels |  |  |
| Templates: Templates | Top bar ▸ View ▸ Panels |  |  |
| Templates: Styles | Top bar ▸ View ▸ Panels |  |  |
| Templates: Previews | Top bar ▸ View ▸ Panels |  |  |
| Templates: Variants | Top bar ▸ View ▸ Panels |  |  |
| Assistant beside the work | Top bar ▸ View ▸ Panels |  |  |
| Reset layout | Top bar ▸ View |  |  |
| Always show the ribbon | Top bar ▸ View ▸ Formatting ribbon |  |  |
| Show tabs only | Top bar ▸ View ▸ Formatting ribbon |  |  |
| Hide the ribbon (Ctrl+F1 shows it) | Top bar ▸ View ▸ Formatting ribbon |  |  |
| Side bar | Top bar ▸ View ▸ More | Ctrl+1 |  |
| Your graphs | Top bar ▸ View ▸ More | Ctrl+2 |  |
| Graph settings | Top bar ▸ View ▸ More | Ctrl+3 |  |
| Assistant | Top bar ▸ View ▸ More | Ctrl+4 |  |
| Focus on the graph | Top bar ▸ View ▸ More | F11 |  |
| Show everything | Top bar ▸ View ▸ More |  |  |
| Your graphs as its own window | Top bar ▸ View ▸ More |  |  |
| Graph settings as its own window | Top bar ▸ View ▸ More |  |  |
| Assistant as its own window | Top bar ▸ View ▸ More |  |  |
| Put the panels back in place | Top bar ▸ View ▸ More |  |  |
| TGA / DTG analysis: zones, mass loss, CH / CaCO₃, Excel… | Top bar ▸ Tools |  | TG + DTG in one graph, zones you can drag, stepwise and tangent mass loss side by side, Ca(OH)₂ / CaCO₃ from z |
| Draw ticked graphs in Origin | Top bar ▸ Tools ▸ Draw | F5 |  |
| Draw all graphs in Origin | Top bar ▸ Tools ▸ Draw | Shift+F5 |  |
| Save this graph (PNG 600 dpi · TIFF · PDF · SVG) | Top bar ▸ Tools ▸ Draw | Ctrl+E |  |
| Your own graph… (columns, style, axes) | Top bar ▸ Tools ▸ Draw | Ctrl+Shift+D | Your own graph (columns, style, axes) |
| Peak labels you type… | Top bar ▸ Tools ▸ Draw | Ctrl+Shift+L | Peak labels you type |
| Label peaks automatically (positions) | Top bar ▸ Tools ▸ Draw | Ctrl+L |  |
| Figure from the ticked graphs (panels a, b …) | Top bar ▸ Tools ▸ Draw |  | Figure from the ticked graphs (panels a, b ) |
| Preview paper set (PDF) | Top bar ▸ Tools ▸ Draw |  |  |
| Make paper set | Top bar ▸ Tools ▸ Draw |  |  |
| Paper figures from a recipe… | Top bar ▸ Tools ▸ Draw |  | Paper figures from a recipe |
| All analyses… | Top bar ▸ Tools ▸ Analysis |  | All analyses |
| Graph gallery… | Top bar ▸ Tools ▸ Analysis |  | Graph gallery |
| TGA: mass loss in temperature intervals | Top bar ▸ Tools ▸ Analysis |  |  |
| Calorimetry (TAM III)… | Top bar ▸ Tools ▸ Analysis |  | Calorimetry (TAM III) |
| FTIR: band areas… | Top bar ▸ Tools ▸ Analysis |  | FTIR: band areas |
| Thermodynamic modelling… | Top bar ▸ Tools ▸ Analysis |  | Thermodynamic modelling |
| Find peaks | Top bar ▸ Tools ▸ Analysis |  |  |
| XRD Scan Generator… | Top bar ▸ Tools ▸ XRD tools |  | XRD Scan Generator |
| Peak correct / improve an XRD scan… | Top bar ▸ Tools ▸ XRD tools |  | Peak correct / improve an XRD scan |
| Phase library… | Top bar ▸ Tools ▸ XRD tools |  | Phase library |
| Check for updates… | Top bar ▸ Help |  | Check for updates |
| Install an update from a zip file… | Top bar ▸ Help |  | Install an update from a zip file |
| Undo the last update | Top bar ▸ Help |  |  |
| Where updates come from… | Top bar ▸ Help |  | Where updates come from |
| System Check | Top bar ▸ Help |  |  |
| Problem report… | Top bar ▸ Help |  | Problem report |
| Mouse actions and keyboard shortcuts | Top bar ▸ Help | F1 |  |
| About Origin Plot Studio | Top bar ▸ Help |  |  |
| Copy | Ribbon ▸ Home |  | Copy the picture of the graph (Ctrl+Shift+C) |
| Save picture | Ribbon ▸ Home |  | Save the picture |
| Reset look | Ribbon ▸ Home |  | Back to how the app draws this graph |
| A↑ | Ribbon ▸ Home |  | Bigger letters |
| A↓ | Ribbon ▸ Home |  | Smaller letters |
| B | Ribbon ▸ Home |  | Bold (Ctrl+B) |
| I | Ribbon ▸ Home |  | Italic (Ctrl+Shift+I) |
| x₂ | Ribbon ▸ Home |  | Subscript: the selected letters (Ctrl+=) |
| x² | Ribbon ▸ Home |  | Superscript: the selected letters (Ctrl+Shift++) |
| A | Ribbon ▸ Home |  | Text colour |
| Clear the format of this text | Ribbon ▸ Home |  | Clear the format of this text |
| ↘ | Ribbon ▸ Home |  | More: Font |
| Apply | Ribbon ▸ Home |  | Apply the typed title |
| Undo | Ribbon ▸ Home |  | Undo the last change of this graph's look (Ctrl+Z) |
| Redo | Ribbon ▸ Home |  | Redo (Ctrl+Y) |
| Edit on the graph | Ribbon ▸ Home |  | Click a text, a curve or the axes in the graph; double click a title to type it; right click for more |
| Sketch a design | Ribbon ▸ Insert |  | Draw how the figure should look (frames, the zoom, curves, titles, legend) - or trace a photo of a sketch - an |
| Add files | Ribbon ▸ Insert |  | Add data files (Ctrl+O) |
| Panel figure | Ribbon ▸ Insert |  | A figure for a paper: the ticked graphs as (a), (b) … |
| Draw freely | Ribbon ▸ Draw |  | Draw your design with a pen, your finger (touch screen) or the mouse |
| Zoom | Ribbon ▸ Draw |  | Drag a box to zoom (Z) |
| Pan | Ribbon ▸ Draw |  | Drag to move (P) |
| Select range | Ribbon ▸ Draw |  | Drag a 2θ / x range (S) |
| Reset axes | Ribbon ▸ Draw |  | The whole graph again (double click on it, Ctrl+R) |
| App look | Ribbon ▸ Design |  | How the app draws it |
| Black && white | Ribbon ▸ Design |  | Black text, axes and curves |
| Bold paper | Ribbon ▸ Design |  | Bold letters, heavier axes and curves |
| Light | Ribbon ▸ Design |  | Normal letters, fine axes and curves |
| Slides | Ribbon ▸ Design |  | Large letters for a presentation |
| Serif | Ribbon ▸ Design |  | Times New Roman everywhere |
| Navy | Ribbon ▸ Design |  | Dark blue axes and titles |
| Stack | Ribbon ▸ Layout |  | One above the other with an offset |
| Overlay | Ribbon ▸ Layout |  | On common axes |
| Panels | Ribbon ▸ Layout |  | One panel each |
| Decide for me | Ribbon ▸ Layout |  | XRD fits and patterns: the app decides |
| Panel figure | Ribbon ▸ Layout |  | A figure for a paper: the ticked graphs as (a), (b) … |
| Apply | Ribbon ▸ Axes |  | Use these ranges |
| Automatic | Ribbon ▸ Axes |  | The app's ranges again |
| Axis colour | Ribbon ▸ Axes |  | Colour of the axes, ticks included |
| Line colour | Ribbon ▸ Lines |  | Colour of this curve (or of all) |
| Automatic | Ribbon ▸ Lines |  | The app's colours and weights again |
| Add files… | Workspace (button) |  | Add data files (Ctrl+O); you can also drop them on the window |
| Tick all | Workspace (button) |  | Ctrl+A |
| Untick all | Workspace (button) |  | Ctrl+Shift+A |
| Stack | Workspace (button) |  | Your own group: the ticked graphs of one kind in one figure, stacked with an offset |
| Overlay | Workspace (button) |  | Your own group: the ticked graphs of one kind in one figure, on common axes |
| Ungroup | Workspace (button) |  | Remove the group you made that is ticked or on show |
| + Add data files | Workspace (button) |  | Add data files (Ctrl+O) – Excel, CSV, text and instrument files; they are only read, never changed. You can al |
| Apply | Workspace (button) |  | Apply – Use the settings of this panel for the graph on show |
| … | Workspace (button) |  | Choose the results folder |
| Export ▾ | Workspace (button) |  | Export (Ctrl+E) – Save this graph as PNG 600 dpi, TIFF, PDF or SVG, or copy it as a picture. Disabled: no grap |
| Draw in Origin | Workspace (button) |  | Draw the ticked graphs in Origin (or the one on show): Origin does the final work |
| Zoom | Workspace (button) |  | Zoom (Z) – Drag a box on the graph to enlarge it; the wheel zooms around the cursor |
| Pan | Workspace (button) |  | Pan (P) – Drag the graph to move the view. Middle mouse button does the same in any mode |
| Select range | Workspace (button) |  | Select range (S) – Drag over an x range for integration, mass loss or a zoom panel. Esc clears it |
| Reset axes | Workspace (button) |  | Reset axes (Ctrl+R) – Back to the full range of the data |
| (shortcut) | window | Ctrl+F |  |
| (shortcut) | window | Ctrl+Return |  |
| (shortcut) | window | Ctrl+Z |  |
| (shortcut) | window | Ctrl+Y |  |
| (shortcut) | window | Ctrl+B |  |
| (shortcut) | window | Ctrl+Shift+I |  |
| (shortcut) | window | Ctrl+= |  |
| (shortcut) | window | Ctrl+Shift++ |  |
| (shortcut) | window | Ctrl+F1 |  |
| (shortcut) | window | Ctrl+O |  |
| (shortcut) | window | Esc |  |
| Files | Panel (templatesFilesDock) |  | movable, floatable, closable |
| Columns | Panel (templatesColumnsDock) |  | movable, floatable, closable |
| Templates | Panel (templatesGalleryDock) |  | movable, floatable, closable |
| Styles | Panel (templatesStylesDock) |  | movable, floatable, closable |
| Previews | Panel (templatesPreviewDock) |  | movable, floatable, closable |
| Variants | Panel (templatesVariantsDock) |  | movable, floatable, closable |
| Graph types | Panel (figtypeBrowserDock) |  | movable, floatable, closable |
| Setup | Panel (figtypeSetupDock) |  | movable, floatable, closable |
| Gallery | Panel (figtypeGalleryDock) |  | movable, floatable, closable |
| Preview and results | Panel (figtypePreviewDock) |  | movable, floatable, closable |
| Analyses | Panel (analysisBrowserDock) |  | movable, floatable, closable |
| Setup | Panel (analysisSetupDock) |  | movable, floatable, closable |
| Gallery | Panel (analysisGalleryDock) |  | movable, floatable, closable |
| Preview and results | Panel (analysisPreviewDock) |  | movable, floatable, closable |
| Details | Panel (detailsDock) |  | movable, floatable, closable |
| Results | Panel (resultsDock) |  | movable, floatable, closable |
| Data | Panel (dataDock) |  | movable, floatable, closable |
| Your graphs | Panel (graphsDock) |  | movable, floatable, closable |
| Graph settings | Panel (settingsDock) |  | movable, floatable, closable |
| Graph | Panel (graphDock) |  | movable, floatable, closable |
| Assistant | Panel (assistantDock) |  | movable, floatable, closable |

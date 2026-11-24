# XRD Scan Generator

A Windows desktop program that writes randomised XRD scans from one measured PANalytical `.xrdml` scan (the
*template*). It is meant for testing software and data pipelines: every scan has the template's peaks, with new
counting noise, background, sample displacement and peak widths, and optionally a mixture of phases from reference
peak lists. Generated scans are synthetic test data, not measurements.

## What it does

1. **Template**: drop an `.xrdml` file on the window or press *Browse for template…*. The program shows the file
   name, sample ID, angular range, number of points, maximum intensity and the peaks it found (green marks), with
   the fitted background. Zoom and pan with the toolbar above the graph.
2. **Generation settings**: number of scans, points per scan (min–max), maximum peak counts (min–max), an optional
   random seed and the output folder. Defaults are those of the script: 5 scans, 8000–10000 points, 8000–10000
   counts. Hover over any field for a short explanation.
3. **Phase mixtures and advanced options** (press *Show advanced options*): add reference peak lists (text/CSV with
   2θ and relative intensity per line), set each phase's weight, include or remove the template's own peaks, and
   set the peak intensity jitter, phase amount jitter, weak-line dropout and peak detection prominence.
4. **Generate**: a progress bar and status line follow the work, which runs in the background so the window stays
   responsive. *Cancel* stops between scans; scans already written are kept together with `manifest.csv`.

Results: the *Generated scans* tab overlays the scans you tick (optionally with the template, optionally normalised
to the same height), with zoom and pan. The *Files* tab lists every written file (double-click opens it) and has an
*Open output folder* button.

Output for every scan: `NAME-001.xrdml` (the template file with new data, the instrument's Windows line endings,
new time stamps in Europe/Stockholm time) and `NAME-001.csv` (`2theta_deg,intensity_counts`). Also
`manifest.csv` (seed, points, maximum, target maximum, peak counts per height band, zero shift, width scale,
background scale, amorphous hump and phase weights of every scan) and, if ticked, `preview.png` of the first four
scans.

Names: files are called after the template's sample ID (`<id>`, else `<name>`, else the file name), numbered
`-001`, `-002`, … — a template with sample ID `SAMPLE` gives `SAMPLE-001`, `SAMPLE-002`, …. The original `<name>`
stays in each file. Existing files are never overwritten: a second run into the same folder continues the
numbering and adds its lines to `manifest.csv`.

The same template, settings and seed always give byte-identical files.

## Install (once)

1. Install **Python 3.9 or newer** from <https://www.python.org/downloads/windows/>. In the installer, tick
   **"Add python.exe to PATH"**.
2. Double-click **`Install.bat`**. It installs the packages in `requirements.txt` (PySide6, numpy, scipy,
   matplotlib, and tzdata for the time zone on Windows).

## Start

Double-click **`Start XRD Scan Generator.bat`**. The window opens without a console window. If a package is
missing, a message says which one and how to install it.

From a command prompt in this folder you can also run `py run.pyw` or `py -m xrd_scan_generator`.

## Build a stand-alone program (.exe)

Double-click **`Build_EXE.bat`**, or in a command prompt in this folder:

```
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --clean xrd_scan_generator.spec
```

The program is then `dist\XRD Scan Generator\XRD Scan Generator.exe` (it opens without a console window). Copy the
whole `dist\XRD Scan Generator` folder to share it; the computer it runs on needs no Python.

## Command line

The engine keeps the options of `xrd_generator_v2.py`:

```
py -m xrd_scan_generator.engine TEMPLATE.xrdml --n 5 --seed 42 --out-dir scans --points 8000-10000 --counts 8000-10000 --phase template:0.7 --phase ref.csv:0.3 --preview
```

## Tests

```
py tests/test_engine.py
py tests/test_gui.py
```

`tests/make_fixture.py` writes the test template `tests/fixtures/SAMPLE.xrdml`, an invented scan (not a
measurement).

## Files

| File | What it is |
| --- | --- |
| `xrd_scan_generator/engine.py` | the scientific engine: template analysis, synthesis, noise, phases, writers; no user interface |
| `xrd_scan_generator/app.py` | the window (PySide6) |
| `run.pyw` | starts the window, checks the packages first |
| `Start XRD Scan Generator.bat`, `Install.bat`, `Build_EXE.bat` | double-click launchers |
| `xrd_scan_generator.spec` | PyInstaller build (windowed, one folder) |
| `requirements.txt` | packages |
| `tests/` | engine and window tests, test template |

# Origin Plot Studio 5.58.4

New in this version: the three-column Start here with projects, the Workbook section and a lighter header - see [the update guide](UPDATE_GUIDE.md); what was checked and what is not done is in [the implementation notes](IMPLEMENTATION_AND_TESTS.md) and [the validation results](VALIDATION_RESULTS.md).

# Origin Plot Studio

A Windows desktop app that reads measurement files (XRD patterns and fits, TGA, FTIR, calorimetry, particle
size, any table), recognises what they are, previews the graphs and draws them in OriginPro. It also composes
multi-panel figures for papers as PDF and PNG.

## Install

1. Download this repository (green **Code** button, **Download ZIP**) and unzip it.
2. Open the folder `origin_plot_app` and double-click `Setup.bat`.
3. Press **Install**, then **Finish**. A shortcut "Origin Plot Studio" is put on the Desktop.

Needs Windows and Python 3.9 or newer (Setup offers to install it). Drawing in Origin needs OriginPro.
More in `origin_plot_app/HOW_TO_INSTALL.txt`.

## Updates

An installed app updates itself from this repository: Help > "Check for updates and install".
It compares its version with `VERSION` in `origin_plot_app/smart_plots.py` on the main branch, redraws the
example files with the new version, installs it and offers a restart. A version that draws an example
differently is not installed without asking. Help > "Undo the last update or fix" puts the earlier version back.

## Not in this repository

Your settings, sessions, results, AI key and your own data files are never uploaded here.

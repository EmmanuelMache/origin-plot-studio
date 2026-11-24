"""Your private folder: things of your own work that are never part of the published app.

  Windows:  %APPDATA%\\OriginPlotStudio\\my_templates          (other systems: ~/.config/OriginPlotStudio/my_templates)
  or the folder named by the environment variable OPS_PRIVATE_DIR

What the app reads from it at start, when present:
  *.csv                 phase files (your own phase library; they come before the small built-in starter list)
  styles/*.json         your own style presets (opstudio.style/1); one with the same id replaces the built-in one
  templates/*.json      your own graph templates (with previews/<id>.png and origin/<id>.otpu beside them)
  reference_figures/    your reference figures and their data (never read by the app itself; kept for you)
  defaults.json         your defaults, e.g. {"default_style": "...", "paper_main": "..."}
Nothing in this folder is sent anywhere, and the updater never touches it."""
import json, os


def private_dir(make=False):
    d = os.environ.get("OPS_PRIVATE_DIR")
    if not d:
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
        d = os.path.join(base, "OriginPlotStudio", "my_templates")
    if make: os.makedirs(d, exist_ok=True)
    return d


def sub(name, make=False):
    d = os.path.join(private_dir(make), name)
    if make: os.makedirs(d, exist_ok=True)
    return d


def defaults():
    try:
        with open(os.path.join(private_dir(), "defaults.json"), encoding="utf-8") as f: d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception: return {}


def default(key, fallback=None):
    v = defaults().get(key)
    return fallback if v in (None, "") else v

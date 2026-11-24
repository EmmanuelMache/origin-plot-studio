"""
start.pyw - what the Desktop shortcut runs.

It shows a small "Starting" window at once, then loads the program. Loading the plotting libraries takes a few
seconds, and without this there was nothing to see in that time.
"""
import os, sys, time
os.environ["OPS_T0"] = repr(time.time())
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
try:
    import json, builtins
    try: _cfg = json.load(open(os.path.join(HERE, "settings.json"), encoding="utf-8"))
    except Exception: _cfg = {}
    if _cfg.get("dpi_aware", True) and os.environ.get("ORIGIN_PLOT_DPI", "").lower() not in ("off", "0", "no"):
        try:
            import ctypes
            try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception: ctypes.windll.user32.SetProcessDPIAware()
        except Exception: pass
    try:                                       # one taskbar button with the app's icon, from the first moment
        import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OriginPlotStudio.App")
    except Exception: pass
    import tkinter as tk
    s = tk.Tk(); s.overrideredirect(True); s.configure(bg="#D8E1EC")
    try: s.iconbitmap(default=os.path.join(HERE, "app.ico"))
    except Exception: pass
    k = max(1.0, s.winfo_fpixels("1i") / 96.0); w, h = int(430 * k), int(170 * k)
    s.geometry(f"{w}x{h}+{(s.winfo_screenwidth() - w) // 2}+{(s.winfo_screenheight() - h) // 3}")
    f = tk.Frame(s, bg="#FFFFFF"); f.pack(fill="both", expand=True, padx=1, pady=1)
    tk.Label(f, text="ORIGIN PLOT STUDIO", bg="#FFFFFF", fg="#17324D", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=int(26 * k), pady=(int(26 * k), 0))
    tk.Label(f, text="Starting…", bg="#FFFFFF", fg="#172B4D", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=int(26 * k))
    tk.Label(f, text="Loading the plotting libraries. This takes a few seconds.", bg="#FFFFFF", fg="#526277", font=("Segoe UI", 9)).pack(anchor="w", padx=int(26 * k), pady=(int(6 * k), 0))
    tk.Frame(f, bg="#2563EB", height=max(3, int(3 * k))).pack(side="bottom", fill="x")
    try: s.attributes("-topmost", True)
    except Exception: pass
    s.update(); builtins._ops_splash = s
    tk._default_root = None                    # the program's own window becomes the main one, not this little one
except Exception: pass
def _say(title, text, error=False):
    """A message without a console (the splash is a Tk window, so Tk can show it)."""
    try:
        import tkinter as _tk
        from tkinter import messagebox as _mb
        r = _tk.Tk(); r.withdraw()
        (_mb.showerror if error else _mb.showinfo)(title, text, parent=r); r.destroy()
    except Exception:
        pass


def _close_splash():
    try:
        _s = getattr(builtins, "_ops_splash", None)
        if _s is not None:
            _s.destroy(); builtins._ops_splash = None
    except Exception:
        pass


def _ensure_qt():
    """The window is built with PySide6 (Qt). If it is missing it is installed once, as the other packages are."""
    import importlib.util
    if importlib.util.find_spec("PySide6") is not None:
        return True
    import subprocess
    _close_splash()
    _say("Origin Plot Studio", "One more Python package is needed for the window (PySide6, about 200 MB). It is installed now; this takes a minute or two.\n\nPress OK to start.")
    exe = sys.executable
    if os.path.basename(exe).lower() == "pythonw.exe" and os.path.isfile(os.path.join(os.path.dirname(exe), "python.exe")):
        exe = os.path.join(os.path.dirname(exe), "python.exe")
    try:
        r = subprocess.run([exe, "-m", "pip", "install", "--quiet", "PySide6"], capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ok = r.returncode == 0
        why = (r.stderr or r.stdout or "")[-1200:]
    except Exception as e:
        ok, why = False, str(e)
    importlib.invalidate_caches()
    if not ok or importlib.util.find_spec("PySide6") is None:
        _say("Origin Plot Studio could not start", "PySide6 could not be installed:\n\n" + why + "\n\nInstall it yourself in a command window:  py -m pip install PySide6\nthen start the app again.", True)
        return False
    return True


def _ask_repair(tb):
    """The app did not start: offer to get the newest version (it may hold the fix), install it over this one (after a backup;
    settings and sessions are kept) and start again. True when it was repaired and started."""
    try:
        import tkinter as _tk
        from tkinter import messagebox as _mb
        r = _tk.Tk(); r.withdraw()
        yes = _mb.askyesno("Origin Plot Studio could not start",
                           "The app could not start (details in startup_error.txt).\n\n" + tb[-500:] +
                           "\n\nRepair now? The newest version is downloaded from the app's GitHub page and installed over this one "
                           "(the current program is backed up first; your settings and sessions are kept), then the app starts again.", parent=r)
        r.destroy()
        if not yes:
            return False
        import tempfile, subprocess
        import self_update as su
        info = su.find_update(su.DEFAULT_SOURCE, "0")            # the newest version, whatever is installed
        work = tempfile.mkdtemp(prefix="ops_repair_")
        trial = su.fetch_and_unpack(info, work)
        store = os.path.join(os.path.expanduser("~"), "Origin Plot Studio program backups")
        su.install(trial, HERE, store, "repair after a start error")
        subprocess.Popen([sys.executable, os.path.join(HERE, "start.pyw")] + _files, cwd=HERE)
        return True
    except Exception as e:
        _say("Origin Plot Studio: repair did not work", f"The repair did not work ({e}).\n\nGet the newest version as a zip from the app's GitHub page "
             "(Code > Download ZIP), unpack it and run Setup.bat in it: it updates the app and keeps your settings.", True)
        return False


# Origin Plot Studio has one window (workspace_qt.py). Files given on the command line (dropped on the shortcut) are opened in it.
_files = [a for a in sys.argv[1:] if not a.startswith("--")]
if not _ensure_qt():
    sys.exit(1)
_close_splash()
try:
    sys.argv = [os.path.join(HERE, "workspace_qt.py")] + _files
    import workspace_qt
    sys.exit(workspace_qt.main(_files))
except SystemExit:
    raise
except Exception:
    import traceback
    _tb = traceback.format_exc()
    try:
        open(os.path.join(HERE, "startup_error.txt"), "w", encoding="utf-8").write("Origin Plot Studio could not start.\n\n" + _tb)
    except Exception:
        pass
    if _ask_repair(_tb):
        sys.exit(0)
    _say("Origin Plot Studio could not start", "The app could not start. The details are in startup_error.txt, in the folder of the app "
         "(send that file to whoever looks after the app; Help > Problem report does the same once it runs).\n\n" + _tb[-900:], True)
    sys.exit(1)

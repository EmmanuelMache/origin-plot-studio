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


def _ask(title, text):
    """A yes / no question without a console. No window to ask in means no."""
    try:
        import tkinter as _tk
        from tkinter import messagebox as _mb
        r = _tk.Tk(); r.withdraw()
        yes = _mb.askyesno(title, text, parent=r); r.destroy()
        return bool(yes)
    except Exception:
        return False


def _ensure_qt():
    """The window is built with PySide6 (Qt). Starting the app installs nothing by itself. When the package is missing
    this says so and asks: with a yes, the tested set of requirements.lock is installed (exact versions, ready-made
    packages only, every file checked against its sha256 - the same command Setup uses); with a no, nothing is
    downloaded and the app does not start. It never installs 'the newest' of anything."""
    import importlib.util
    if importlib.util.find_spec("PySide6") is not None:
        return True
    import subprocess
    _close_splash()
    lock = os.path.join(HERE, "requirements.lock")
    if not os.path.isfile(lock):
        _say("Origin Plot Studio could not start", "The Python package for the window (PySide6) is not installed, and requirements.lock - the list of the tested "
             "package versions - is missing from the folder of the app.\n\nDownload the release again, unpack all of it and run Setup.bat.", True)
        return False
    if not _ask("Origin Plot Studio", "The Python packages this app needs are not all installed (PySide6, which draws the window, is missing).\n\n"
                "Nothing is installed without your yes.\n\nInstall the tested versions now? They are the ones listed in requirements.lock in the folder of the app; "
                "every downloaded file is checked against the sha256 in that list. Several hundred MB, a few minutes.\n\n"
                "No: nothing is installed. Run Setup.bat in the folder of the app when you want to install them."):
        return False
    exe = sys.executable
    if os.path.basename(exe).lower() == "pythonw.exe" and os.path.isfile(os.path.join(os.path.dirname(exe), "python.exe")):
        exe = os.path.join(os.path.dirname(exe), "python.exe")
    try:
        hashed = "--hash=sha256:" in open(lock, encoding="utf-8").read()
        cmd = [exe, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--only-binary", ":all:"] + (["--require-hashes"] if hashed else ["--no-deps"]) + ["-r", lock]
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ok = r.returncode == 0
        why = (r.stderr or r.stdout or "")[-1200:]
    except Exception as e:
        ok, why = False, str(e)
    importlib.invalidate_caches()
    if not ok or importlib.util.find_spec("PySide6") is None:
        _say("Origin Plot Studio could not start", "The packages could not be installed:\n\n" + why + "\n\nRun Setup.bat in the folder of the app: it shows each step "
             "and installs the same tested versions. Is the computer online?", True)
        return False
    return True


def _update_store():
    """Where the windows keep the backups of the program and the journal of an installation (the same folder they use:
    beside the app's own data, outside the program). Worked out here without importing the program."""
    v = os.environ.get("ORIGIN_PLOT_APP_HOME") or os.path.join(os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config"), "OriginPlotApp")
    return os.path.join(v, "program_backups")


def _recover_interrupted_install():
    """An installation that was cut off (power loss, a crash) is finished or undone BEFORE the program is imported -
    a half-installed program might not start at all. Only the updater itself is imported for this. Never stops a start."""
    try:
        if not os.path.isfile(os.path.join(_update_store(), "install_journal.json")): return
        import self_update as su
        su.recover(HERE, _update_store())
    except Exception:
        pass


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
        trial = su.fetch_and_unpack(info, work, allow_same=True)     # the same version again is what a repair asks for; a build for other people still needs the publisher's signature
        su.install(trial, HERE, _update_store(), "repair after a start error")
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
_recover_interrupted_install()
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

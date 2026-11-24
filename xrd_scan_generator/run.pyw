"""Starts XRD Scan Generator without a console window (pythonw). If a package is missing it says which, and how to install it."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def tell(text):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "XRD Scan Generator", 0x10)
    except Exception:
        try:
            import tkinter
            from tkinter import messagebox
            r = tkinter.Tk(); r.withdraw(); messagebox.showerror("XRD Scan Generator", text); r.destroy()
        except Exception:
            print(text, file=sys.stderr)


missing = []
for mod, pkg in (("PySide6", "PySide6"), ("numpy", "numpy"), ("scipy", "scipy"), ("matplotlib", "matplotlib")):
    try:
        __import__(mod)
    except ImportError:
        missing.append(pkg)
try:
    from zoneinfo import ZoneInfo
    ZoneInfo("Europe/Stockholm")
except Exception:
    missing.append("tzdata")
if sys.version_info < (3, 9):
    tell(f"XRD Scan Generator needs Python 3.9 or newer (this is {sys.version.split()[0]}).")
    sys.exit(1)
if missing:
    tell("These Python packages are missing: " + ", ".join(missing) + "\n\nInstall them by double-clicking Install.bat, "
         "or in a command prompt in this folder:\n\n    py -m pip install -r requirements.txt")
    sys.exit(1)

try:
    from xrd_scan_generator.app import main
    sys.exit(main())
except Exception:
    import traceback
    tell("XRD Scan Generator could not start:\n\n" + traceback.format_exc(limit=5))
    sys.exit(1)

# PyInstaller build of XRD Scan Generator: one folder, windowed (no console).  Build:  pyinstaller --noconfirm --clean xrd_scan_generator.spec
from PyInstaller.utils.hooks import collect_data_files

datas = [("xrd_scan_generator/icon.png", "xrd_scan_generator"), ("xrd_scan_generator/icon.ico", "xrd_scan_generator")]
datas += collect_data_files("tzdata")          # Europe/Stockholm time zone on Windows

a = Analysis(
    ["run.pyw"],
    pathex=["."],
    datas=datas,
    hiddenimports=["tzdata", "scipy.signal", "matplotlib.backends.backend_qtagg", "matplotlib.backends.backend_agg"],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="XRD Scan Generator",
    console=False,
    icon="xrd_scan_generator/icon.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, name="XRD Scan Generator")

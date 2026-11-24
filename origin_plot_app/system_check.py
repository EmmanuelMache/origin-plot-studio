"""Pre-flight / System Check. Never raises, never blocks: every line is a (name, status, detail) tuple, status in ok / warn / missing."""
import sys, os, importlib

def _mod(name):
    try:
        m = importlib.import_module(name); return "ok", getattr(m, "__version__", "")
    except Exception as e: return "missing", type(e).__name__

def origin_com():
    if os.name != "nt": return "warn", "not Windows: figures use the matplotlib fallback"
    try:
        import win32com.client; win32com.client.GetActiveObject("Origin.Application"); return "ok", "OriginPro is running"
    except Exception: pass
    try:
        import win32com.client; win32com.client.GetObject(Class="Origin.ApplicationSI"); return "ok", "OriginPro is installed"
    except Exception: return "warn", "OriginPro not found: figures use the matplotlib fallback"

def origin_available():
    return origin_com()[0] == "ok"

def run():
    rows = [("Python", "ok" if sys.version_info >= (3, 9) else "warn", sys.version.split()[0])]
    for n in ("numpy", "pandas", "scipy", "matplotlib", "openpyxl"): s, d = _mod(n); rows.append((n, s, d))
    for n in ("originpro", "win32com"): s, d = _mod(n); rows.append(({"win32com": "pywin32"}.get(n, n), "ok" if s == "ok" else "warn", d if s == "ok" else "optional, not installed"))
    s, d = origin_com(); rows.append(("OriginPro (COM)", s, d))
    try:                                                     # the XRD Scan Generator app (XRD tools > XRD Scan Generator (app))
        import importlib.util, os as _os
        here_ = _os.path.dirname(_os.path.abspath(__file__))
        f_ok = _os.path.isfile(_os.path.join(here_, "xrd_scan_generator_app.py")); q_ok = importlib.util.find_spec("PySide6") is not None
        rows.append(("XRD Scan Generator (app)", "ok" if f_ok and q_ok else "warn",
                     "ready" if f_ok and q_ok else ("PySide6 not installed: the app offers to install it when you open the generator" if f_ok else "xrd_scan_generator_app.py is missing: update the app")))
    except Exception as e: rows.append(("XRD Scan Generator (app)", "warn", type(e).__name__))
    try:
        import assistant_secrets as sec; rows.append(("Windows data protection (DPAPI)", "ok" if sec.dpapi_available() else "warn", "available" if sec.dpapi_available() else "not available here"))
        k = sec.status(); rows.append(("API key", {"set": "ok", "not set": "warn", "invalid": "missing"}[k], k))
    except Exception as e: rows.append(("API key", "warn", type(e).__name__))
    return rows

def text(rows=None):
    return "\n".join(f"{'✓' if s == 'ok' else '!' if s == 'warn' else '✗'}  {n}: {d}" for n, s, d in (rows or run()))

"""
net.py - secure connections that work on more computers, without ever switching the certificate check off.

Python on Windows trusts only the certificates Windows has already stored on that computer, and Windows fetches many
of them only when its own programs need them. On a fresh PC, or behind an antivirus or company network that inspects
secure connections, Python can then fail with CERTIFICATE_VERIFY_FAILED although every browser works.

So a connection is tried in this order, each one fully verified:
  1. Python, trusting Windows' certificates AND the standard public list (the 'certifi' package, or pip's own copy);
  2. Windows' own download tool curl.exe (part of Windows 10 and 11), which uses Windows' certificate handling,
     including certificates a company or an antivirus installed and the on-demand fetching;
  3. PowerShell's Invoke-WebRequest, for a Windows without curl.exe.
"""
import os, ssl, sys, shutil, subprocess, tempfile

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class HttpError(Exception):
    """The server answered, but with an error code (404 = not there, 403 = not allowed or too many requests ...)."""
    def __init__(self, code, url): super().__init__(f"HTTP Error {code}"); self.code = int(code); self.url = url

class CertificateProblem(Exception):
    """No way of connecting could verify the certificate of the server."""


def context():
    """What Python trusts: the certificates of this computer plus the standard public list when it is installed."""
    ctx = ssl.create_default_context()
    for mod in ("certifi", "pip._vendor.certifi"):
        try:
            import importlib
            ctx.load_verify_locations(importlib.import_module(mod).where()); break
        except Exception: continue
    return ctx

def is_certificate_error(e):
    t = (str(e) + " " + str(getattr(e, "reason", ""))).upper()
    return isinstance(e, ssl.SSLError) or isinstance(getattr(e, "reason", None), ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in t or "SSL:" in t

def _curl(url, headers, timeout):
    exe = shutil.which("curl.exe") or (shutil.which("curl") if os.name != "nt" else None)
    if not exe: return None
    fd, tmp = tempfile.mkstemp(prefix="ops_dl_"); os.close(fd)
    try:
        cmd = [exe, "-sS", "-L", "--max-time", str(int(timeout)), "-o", tmp, "-w", "%{http_code}"]
        for k, v in headers.items(): cmd += ["-H", f"{k}: {v}"]
        r = subprocess.run(cmd + [url], capture_output=True, text=True, creationflags=NOWIN, timeout=timeout + 30)
        code = (r.stdout or "").strip()[-3:]
        if r.returncode != 0: raise CertificateProblem((r.stderr or "curl failed").strip()[-300:]) if "certificate" in (r.stderr or "").lower() or "SEC_E" in (r.stderr or "") or "schannel" in (r.stderr or "").lower() else OSError((r.stderr or "curl failed").strip()[-300:])
        if code.isdigit() and int(code) >= 400: raise HttpError(code, url)
        with open(tmp, "rb") as f: return f.read()
    finally:
        try: os.remove(tmp)
        except Exception: pass

def _powershell(url, headers, timeout):
    if os.name != "nt" or not shutil.which("powershell"): return None
    fd, tmp = tempfile.mkstemp(prefix="ops_dl_"); os.close(fd)
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    hdr = "@{" + "; ".join(f"{q(k)}={q(v)}" for k, v in headers.items() if k.lower() != "user-agent") + "}"
    script = ("$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
              f"try {{ Invoke-WebRequest -UseBasicParsing -Uri {q(url)} -Headers {hdr} -UserAgent {q(headers.get('User-Agent', 'origin-plot-studio'))} -OutFile {q(tmp)} -TimeoutSec {int(timeout)}; 'OK' }} "
              "catch { if ($_.Exception.Response) { 'HTTP ' + [int]$_.Exception.Response.StatusCode } else { 'ERR ' + $_.Exception.Message } }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, creationflags=NOWIN, timeout=timeout + 60)
        out = (r.stdout or "").strip().splitlines()[-1:] or [""]
        if out[0].startswith("HTTP "): raise HttpError(out[0][5:8], url)
        if out[0] != "OK": raise OSError(out[0][4:300] or (r.stderr or "PowerShell could not download").strip()[-300:])
        with open(tmp, "rb") as f: return f.read()
    finally:
        try: os.remove(tmp)
        except Exception: pass

def fetch(url, headers=None, timeout=60):
    """The bytes at an https address. Raises HttpError (the server said no), CertificateProblem, or OSError (no connection)."""
    import urllib.request, urllib.error
    if not str(url).lower().startswith("https://"): raise ValueError("only https addresses are fetched")
    headers = dict(headers or {}); first = None
    try:
        op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context()))
        with op.open(urllib.request.Request(url, headers=headers), timeout=timeout) as r: return r.read()
    except urllib.error.HTTPError as e: raise HttpError(e.code, url)
    except Exception as e:
        if not is_certificate_error(e): raise
        first = e
    last = first
    for way in (_curl, _powershell):                         # Python could not verify the certificate: let Windows' own tools try
        try:
            b = way(url, headers, timeout)
            if b is not None: return b
        except HttpError: raise
        except Exception as e: last = e
    raise CertificateProblem(str(last)[:300])

WHY_CERTIFICATE = ("This computer could not verify the secure connection. That is usually an antivirus or a company or university network that inspects "
                   "secure connections, or a wrong date on the computer. Nothing is wrong with the app or with the place it connects to.")

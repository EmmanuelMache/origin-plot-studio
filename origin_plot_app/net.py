"""
net.py - secure connections that work on more computers, without ever switching the certificate check off.

Python on Windows trusts only the certificates Windows has already stored on that computer, and Windows fetches many
of them only when its own programs need them. On a fresh PC, or behind an antivirus or company network that inspects
secure connections, Python can then fail with CERTIFICATE_VERIFY_FAILED although every browser works.

So a connection is tried in this order, each one fully verified:
  1. Python, trusting Windows' certificates AND the standard public list (the 'certifi' package, or pip's own copy);
  2. Windows' own download tool curl.exe (part of Windows 10 and 11), which uses Windows' certificate handling,
     including certificates a company or an antivirus installed and the on-demand fetching;
  3. PowerShell (the .NET web request), for a Windows without curl.exe.

The same rules hold for all three ways (they are applied here, not left to the tool):
  - only https; an address with a user name or password in it is not used;
  - a redirect is never followed by the tool itself. Every hop comes back here and is checked again
    (outbound_policy.check_url): a hop to plain http is refused, and a hop that leaves the place the request was made
    for loses its credential headers (Authorization, cookies, API keys) for good;
  - a credential never appears on a command line: curl gets its address and headers on standard input (-K -),
    PowerShell gets them as JSON on standard input; the script text holds no value of yours;
  - error texts go through outbound_policy.redact before they are raised.
"""
import os, re, ssl, sys, json, shutil, subprocess, tempfile, urllib.parse

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MAX_REDIRECTS = 5
REDIRECT_CODES = (301, 302, 303, 307, 308)
CREDENTIAL_HEADERS = ("authorization", "proxy-authorization", "cookie", "x-api-key", "x-goog-api-key", "api-key", "private-token")
_CREDENTIAL_WORDS = ("auth", "token", "secret", "cookie", "password", "api-key", "apikey", "api_key")


class HttpError(Exception):
    """The server answered, but with an error code (404 = not there, 403 = not allowed or too many requests ...)."""
    def __init__(self, code, url): super().__init__(f"HTTP Error {code}"); self.code = int(code); self.url = _plain_url(url)

class CertificateProblem(Exception):
    """No way of connecting could verify the certificate of the server."""

class TooLarge(OSError):
    """The answer is larger than the caller accepts (max_bytes); the download was stopped."""


def _op():
    import outbound_policy
    return outbound_policy

def _clean(text):
    """A text that may be shown, logged or raised: no key, no token, no Authorization value."""
    try: return _op().redact(str(text))
    except Exception: return "(the details are withheld)"

def _plain_url(url):
    """The address without its query (a signed download link carries a credential there)."""
    try:
        p = urllib.parse.urlsplit(str(url)); host = p.hostname or ""
        return _clean(f"{p.scheme}://{host}{(':' + str(p.port)) if p.port else ''}{p.path}")
    except Exception: return ""

def is_credential_header(name):
    n = str(name).strip().lower()
    return n in CREDENTIAL_HEADERS or any(w in n for w in _CREDENTIAL_WORDS)

def without_credentials(headers):
    return {k: v for k, v in dict(headers or {}).items() if not is_credential_header(k)}

def _check_headers(headers):
    for k, v in headers.items():
        if not re.fullmatch(r"[A-Za-z0-9!#$%&'*+.^_`|~-]+", str(k)) or re.search(r"[\r\n\x00]", str(v)): raise ValueError("a request header is not valid (a line break or an invalid name); nothing was sent")


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


# ---------------------------------------------------------------------------------------------- one request, three ways
# Each way makes ONE request and never follows a redirect: it returns (status code, Location or "", the bytes), or None
# when that way does not exist on this computer. fetch() walks the hops.
def _opener():
    import urllib.request
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl): return None          # the hop is decided in _walk, not by urllib
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=context()), NoRedirect())

def _too_big(): return TooLarge("the download is larger than the app accepts; it was stopped")

def _urllib_once(url, headers, timeout, max_bytes=None):
    import urllib.request, urllib.error
    try:
        with _opener().open(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            b = r.read() if not max_bytes else r.read(int(max_bytes) + 1)
            if max_bytes and len(b) > max_bytes: raise _too_big()
            return int(getattr(r, "status", 200) or 200), "", b
    except urllib.error.HTTPError as e:
        loc = ""
        try: loc = (e.headers.get("Location") or "") if e.headers is not None else ""
        except Exception: pass
        try: e.close()
        except Exception: pass
        return int(e.code), loc, b""

def _curl_exe(): return shutil.which("curl.exe") or (shutil.which("curl") if os.name != "nt" else None)

def _cq(s):
    """A value inside double quotes of a curl config file."""
    return str(s).replace("\\", "\\\\").replace('"', '\\"')

def _curl_once(url, headers, timeout, max_bytes=None):
    exe = _curl_exe()
    if not exe: return None
    fd, tmp = tempfile.mkstemp(prefix="ops_dl_"); os.close(fd)
    try:
        # The address and the headers travel on standard input (-K -), never on the command line, where every program of this
        # computer could read them. -q: no .curlrc (it could switch redirects on or the certificate check off). No -L: curl
        # does not follow a redirect; %{redirect_url} says where it points and the hop is checked in _walk.
        cfg = "".join(f'header = "{_cq(k)}: {_cq(v)}"\n' for k, v in headers.items() if str(v) != "") + f'url = "{_cq(url)}"\n'
        cmd = [exe, "-q", "-sS", "-g", "--proto", "=https", "--max-redirs", "0", "--max-time", str(int(timeout)), "-o", tmp, "-w", "%{http_code} %{redirect_url}"]
        if max_bytes: cmd += ["--max-filesize", str(int(max_bytes))]
        r = subprocess.run(cmd + ["-K", "-"], input=cfg, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN, timeout=timeout + 30)
        err = _clean((r.stderr or "curl failed").strip()[-300:])
        if r.returncode == 63: raise _too_big()
        if r.returncode != 0: raise CertificateProblem(err) if ("certificate" in err.lower() or "SEC_E" in err or "schannel" in err.lower()) else OSError(err)
        out = (r.stdout or "").strip().split(" ", 1); code = out[0][-3:]
        if not code.isdigit(): raise OSError("curl gave no status code")
        if int(code) in REDIRECT_CODES: return int(code), (out[1].strip() if len(out) > 1 else ""), b""
        if int(code) >= 400: return int(code), "", b""
        if max_bytes and os.path.getsize(tmp) > max_bytes: raise _too_big()
        with open(tmp, "rb") as f: return int(code), "", f.read()
    finally:
        try: os.remove(tmp)
        except Exception: pass

# The script is constant: the address, the headers and the file name are read from standard input as JSON. AllowAutoRedirect
# is off, so a redirect comes back as its status code and Location. The certificate check of Windows stays on.
_PS_SCRIPT = ("$ErrorActionPreference='Stop'; try { "
              "[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12; "
              "$j = [Console]::In.ReadToEnd() | ConvertFrom-Json; "
              "$req = [System.Net.HttpWebRequest][System.Net.WebRequest]::Create([string]$j.url); $req.AllowAutoRedirect = $false; $req.Method = 'GET'; "
              "$req.Timeout = [int]$j.timeout * 1000; $req.ReadWriteTimeout = [int]$j.timeout * 1000; "
              "foreach ($h in $j.headers) { $n = [string]$h.name; $v = [string]$h.value; "
              "if ($n -ieq 'User-Agent') { $req.UserAgent = $v } elseif ($n -ieq 'Accept') { $req.Accept = $v } elseif ($n -ieq 'Referer') { $req.Referer = $v } "
              "elseif ($n -ieq 'Content-Type') { $req.ContentType = $v } else { $req.Headers.Add($n, $v) } }; "
              "$resp = $null; try { $resp = $req.GetResponse() } catch { $ex = $_.Exception; while ($ex -and -not ($ex -is [System.Net.WebException])) { $ex = $ex.InnerException }; "
              "if ($ex -and $ex.Response) { $resp = $ex.Response } else { throw } }; "
              "$code = [int]$resp.StatusCode; $loc = [string]$resp.Headers['Location']; "
              "if ($code -ge 200 -and $code -lt 300) { $in = $resp.GetResponseStream(); $out = [System.IO.File]::Create([string]$j.out); "
              "try { $in.CopyTo($out) } finally { $out.Close(); $in.Close() } }; $resp.Close(); 'STATUS ' + $code; 'LOCATION ' + $loc "
              "} catch { 'ERR ' + $_.Exception.Message }")

def _powershell_exe(): return shutil.which("powershell") if os.name == "nt" else None

def _powershell_once(url, headers, timeout, max_bytes=None):
    exe = _powershell_exe()
    if not exe: return None
    fd, tmp = tempfile.mkstemp(prefix="ops_dl_"); os.close(fd)
    try:
        job = json.dumps({"url": str(url), "out": tmp, "timeout": int(timeout), "headers": [{"name": str(k), "value": str(v)} for k, v in headers.items()]})     # ASCII JSON, on standard input
        r = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _PS_SCRIPT], input=job, capture_output=True, text=True,
                           creationflags=NOWIN, timeout=timeout + 60)
        lines = [l.strip() for l in (r.stdout or "").strip().splitlines() if l.strip()]
        st = next((l for l in lines if l.startswith("STATUS ")), ""); loc = next((l[9:].strip() for l in lines if l.startswith("LOCATION ")), "")
        if not st:
            err = _clean((next((l[4:] for l in lines if l.startswith("ERR ")), "") or (r.stderr or "PowerShell could not download").strip())[-300:])
            raise CertificateProblem(err) if ("certificate" in err.lower() or "trust relationship" in err.lower()) else OSError(err)
        code = int(re.sub(r"\D", "", st[7:]) or 0)
        if code in REDIRECT_CODES: return code, loc, b""
        if code >= 400 or code < 200: return code, "", b""
        if max_bytes and os.path.getsize(tmp) > max_bytes: raise _too_big()
        with open(tmp, "rb") as f: return code, "", f.read()
    finally:
        try: os.remove(tmp)
        except Exception: pass


# ---------------------------------------------------------------------------------------------- the hops
def _admit(url, channel):
    """The policy check right before a request is sent: every hop, every way."""
    op = _op()
    return op.require(channel, url) if channel else op.check_url(url)

def _walk(once, url, headers, timeout, channel=None, max_bytes=None, keep_credentials=None):
    """Make the request with one way and walk its redirects here. Returns the bytes, or None when that way does not exist.
    keep_credentials(address) -> bool can narrow further where the credential headers may go (the update token: only
    the routes of its own repository); leaving the first origin always drops them, and they never come back."""
    op = _op(); cur = str(url); h = dict(headers)
    for _hop in range(MAX_REDIRECTS + 1):
        _admit(cur, channel)
        if not op.same_origin(url, cur) or (keep_credentials is not None and not keep_credentials(cur)): h = without_credentials(h)
        got = once(cur, h, timeout, max_bytes)
        if got is None: return None
        code, loc, body = got
        if code in REDIRECT_CODES:
            if not loc: raise HttpError(code, cur)
            nxt = urllib.parse.urljoin(cur, str(loc).strip())
            try: op.check_url(nxt)                                    # https only: a hop down to plain http, or to an address with a password in it, ends here
            except op.Blocked as e: raise op.Blocked(f"the server sent the request on to an address the app does not use ({e}); it was not followed")
            cur = nxt; continue
        if code >= 400 or code < 200: raise HttpError(code, cur)
        return body
    raise OSError(f"too many redirects (more than {MAX_REDIRECTS}); the download was stopped")

def fetch(url, headers=None, timeout=60, *, channel=None, max_bytes=None, keep_credentials=None):
    """The bytes at an https address. Raises HttpError (the server said no), CertificateProblem, OSError (no connection),
    or outbound_policy.Blocked (the policy, or a redirect that is not followed).
    channel: one of outbound_policy.CHANNELS; then the level and the switch of that channel are checked at every hop
    (local-only mode stops the request here). Without it only the address rules are checked: the caller asks the policy."""
    if not str(url).lower().startswith("https://"): raise ValueError("only https addresses are fetched")
    headers = dict(headers or {}); _check_headers(headers); op = _op()
    _admit(url, channel)
    try:
        return _walk(_urllib_once, url, headers, timeout, channel, max_bytes, keep_credentials)
    except HttpError: raise
    except Exception as e:
        if not is_certificate_error(e): raise
        last = e
    for way in (_curl_once, _powershell_once):                # Python could not verify the certificate: let Windows' own tools try
        try:
            b = _walk(way, url, headers, timeout, channel, max_bytes, keep_credentials)
            if b is not None: return b
        except (HttpError, TooLarge, op.Blocked): raise       # an answer of the server, a size limit, or a refusal of the policy, is final
        except Exception as e: last = e
    raise CertificateProblem(_clean(last)[:300])

WHY_CERTIFICATE = ("This computer could not verify the secure connection. That is usually an antivirus or a company or university network that inspects "
                   "secure connections, or a wrong date on the computer. Nothing is wrong with the app or with the place it connects to.")

"""Where credentials may go, how requests leave, and where keys are kept (SEC-01, SEC-04, SEC-06, local-only mode).

Nothing here makes a real request: every way out (urllib, curl, PowerShell, the AI opener) is replaced by a recorder, the
addresses end in .invalid, and the credentials are dummies. A real socket connection would fail the run.
What this cannot show: the behaviour of the real curl.exe, of Windows PowerShell and of Windows data protection (DPAPI)
on a Windows computer - those are replaced by stand-ins here and still need a check on Windows.
Run:  python tests/test_security_net.py"""
import os, sys, ssl, json, base64, socket, tempfile, urllib.request, urllib.error, urllib.parse, email.message
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix="ops_secnet_"))
os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private"); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json")
os.environ["OPS_NO_OPEN"] = "1"; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["OPS_PROFILE"] = "owner"; os.environ["OPS_NO_KEYRING"] = "1"; os.environ.pop("OPS_LOCAL_ONLY", None)
os.environ["APPDATA"] = str(TMP / "appdata")
ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "origin_plot_app"; sys.path.insert(0, str(A))
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
def raised(fn, *types):
    try: fn()
    except BaseException as e: return e if (not types or isinstance(e, types)) else None
    return None

def _no_network(*a, **k): raise AssertionError("a test tried to open a real network connection")
socket.socket.connect = _no_network; socket.create_connection = _no_network

import outbound_policy as op, secure_store, net, self_update as su, assistant as ai, assistant_backends as ab, assistant_secrets as sec, assistant_actions as aa
op.reload()

TOKEN = "ghp_" + "dummyTOKEN123" * 3            # shaped like a GitHub token; not a real one
REPO = "owner-x/repo-y"
API = "https://api.github.com/repos/owner-x/repo-y"

# ================================================================ the stand-ins for the three ways out
WORLD = {}                                      # address -> ("ok", bytes) | ("to", code, location) | ("http", code)
SEEN = []                                       # every request any way made: {"way", "url", "headers" (lower-case names), "argv", "stdin", "env"}
FAIL = {"urllib": None, "curl": None}           # an exception / a stderr text to fail with

def answer(url): return WORLD.get(url, ("http", 404))

class FakeResp:
    def __init__(self, body): self.body = body; self.status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, n=-1): return self.body if n is None or n < 0 else self.body[:n]

class FakeOpener:
    def open(self, req, timeout=None):
        SEEN.append({"way": "urllib", "url": req.full_url, "headers": {k.lower(): v for k, v in req.header_items()}, "argv": [], "stdin": "", "env": None})
        if FAIL["urllib"] is not None: raise FAIL["urllib"]
        a = answer(req.full_url)
        if a[0] == "ok": return FakeResp(a[1])
        hd = email.message.Message()
        if a[0] == "to": hd["Location"] = a[2]
        raise urllib.error.HTTPError(req.full_url, a[1], "x", hd, None)

class Done:
    def __init__(self, out="", err="", code=0): self.stdout = out; self.stderr = err; self.returncode = code

def fake_run(cmd, input=None, **kw):
    """Stands in for subprocess.run: plays curl (config on standard input) or PowerShell (JSON on standard input)."""
    rec = {"argv": list(cmd), "stdin": input or "", "env": kw.get("env")}
    if cmd[0] == "curl-fake":
        cfg = input or ""; url = ""; headers = {}
        for line in cfg.splitlines():
            k, _, v = line.partition(" = "); v = v.strip()[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            if k == "url": url = v
            elif k == "header": n, _, hv = v.partition(": "); headers[n.lower()] = hv
        SEEN.append(dict(rec, way="curl", url=url, headers=headers))
        if FAIL["curl"] is not None: return Done("", FAIL["curl"], 60)
        a = answer(url); out = cmd[cmd.index("-o") + 1]
        if a[0] == "ok": open(out, "wb").write(a[1]); return Done("200 ")
        if a[0] == "to": return Done(f"{a[1]} {urllib.parse.urljoin(url, a[2])}")
        return Done(f"{a[1]} ")
    if cmd[0] == "powershell-fake":
        j = json.loads(input); url = j["url"]
        SEEN.append(dict(rec, way="powershell", url=url, headers={h["name"].lower(): h["value"] for h in j["headers"]}))
        a = answer(url)
        if a[0] == "ok": open(j["out"], "wb").write(a[1]); return Done("STATUS 200\nLOCATION \n")
        if a[0] == "to": return Done(f"STATUS {a[1]}\nLOCATION {a[2]}\n")
        return Done(f"STATUS {a[1]}\nLOCATION \n")
    raise AssertionError(f"an unexpected program was started: {cmd[0]}")

REAL = dict(opener=net._opener, run=net.subprocess.run, curl=net._curl_exe, ps=net._powershell_exe)
CERT = ssl.SSLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (stand-in)")
def use(way):
    """Make `way` the one that answers: Python itself, or - after Python 'cannot verify the certificate' - curl or PowerShell."""
    net._opener = lambda: FakeOpener(); net.subprocess.run = fake_run
    FAIL["urllib"] = None if way == "urllib" else CERT; FAIL["curl"] = None
    net._curl_exe = (lambda: "curl-fake") if way == "curl" else (lambda: None)
    net._powershell_exe = (lambda: "powershell-fake") if way == "powershell" else (lambda: None)
def sent_by(way): return [r for r in SEEN if r["way"] == way]
def leaked(secret, e=None):
    """Does the secret show anywhere it must not: a command line, an environment handed to a program, an error text?"""
    return any(secret in " ".join(map(str, r["argv"])) or secret in json.dumps(r["env"] or {}) for r in SEEN) or (e is not None and secret in (str(e) + repr(e)))

# ================================================================ SEC-01: the rule itself (parsed, exact)
su.TOKEN = TOKEN; su._REPO[0] = REPO
YES = [API, API + "/releases/latest", API + "/releases/assets/17", API + "/zipball/v9", "https://api.github.com:443/repos/OWNER-X/Repo-Y/contents/smart_plots.py"]
NO = {"look-alike host": "https://api.github.com.evil.invalid/repos/owner-x/repo-y/releases/latest",
      "host that only contains the word": "https://github.evil.invalid/owner-x/repo-y/x.zip",
      "the word only in the path": "https://files.invalid/github/api.github.com/repos/owner-x/repo-y/f.zip",
      "user name in the address": "https://someone:pw@api.github.com/repos/owner-x/repo-y/releases/latest",
      "the real host as a user name": "https://api.github.com@evil.invalid/repos/owner-x/repo-y",
      "another port": "https://api.github.com:8443/repos/owner-x/repo-y/releases/latest",
      "raw file host": "https://raw.githubusercontent.com/owner-x/repo-y/main/smart_plots.py",
      "codeload": "https://codeload.github.com/owner-x/repo-y/zip/refs/heads/main",
      "release storage host": "https://objects.githubusercontent.com/github-production-release-asset/1/abc",
      "github.com download link": "https://github.com/owner-x/repo-y/releases/download/v9/app.zip",
      "another repository": "https://api.github.com/repos/someone-else/repo-y/releases/latest",
      "a repository whose name only begins the same": "https://api.github.com/repos/owner-x/repo-y-copy/releases/latest",
      "another route of the API": "https://api.github.com/user",
      "a '..' step out of the repository": "https://api.github.com/repos/owner-x/repo-y/../../../user",
      "an encoded '..' step": "https://api.github.com/repos/owner-x/repo-y/%2e%2e/%2e%2e/user",
      "plain http": "http://api.github.com/repos/owner-x/repo-y/releases/latest"}
check("the update token is allowed on the routes of its own repository at https://api.github.com (port 443), whatever the letter case of the name", all(su.token_allowed(u) for u in YES), [u for u in YES if not su.token_allowed(u)])
check("... and nowhere else: look-alike host, the word in a path, user name, other port, raw / codeload / storage hosts, other repository, other route, '..', plain http",
      not any(su.token_allowed(u) for u in NO.values()), [k for k, u in NO.items() if su.token_allowed(u)])
su._REPO[0] = ""
check("without a configured repository (or with a name that is not owner/repository) the token is allowed nowhere", not su.token_allowed(API) and not su.token_allowed(API, "../..") and not su.token_allowed(API, "owner-x") and not su.token_allowed(API, "owner-x/repo-y/extra"))
su._REPO[0] = REPO
src = (A / "self_update.py").read_text(encoding="utf-8")
check("the substring rule is gone from the updater", '"github" in str(url)' not in src and "token_allowed" in src)

# ================================================================ SEC-01: every way out, the same rule
for way in ("urllib", "curl", "powershell"):
    use(way)
    # --- the intended request works and carries the token; the token is never on a command line
    WORLD.clear(); SEEN.clear(); WORLD[API + "/releases/latest"] = ("ok", b'{"tag_name": "v9"}')
    got = su._get(API + "/releases/latest")
    r = sent_by(way)
    check(f"[{way}] the intended API request works and carries the token", got == b'{"tag_name": "v9"}' and len(r) == 1 and r[0]["headers"].get("authorization") == "Bearer " + TOKEN, r[:1])
    check(f"[{way}] the token is not on a command line or in a program's environment" + ("" if way == "urllib" else " (it travels on standard input)"),
          not leaked(TOKEN) and (way == "urllib" or TOKEN in r[0]["stdin"]), [x["argv"] for x in r])
    if way != "urllib":
        argv = " ".join(r[0]["argv"])
        check(f"[{way}] the address is not on the command line either, and the tool is told not to follow redirects by itself",
              "api.github.com" not in argv and ("-L" not in r[0]["argv"] and "--location" not in r[0]["argv"] and "--max-redirs" in r[0]["argv"] if way == "curl" else "AllowAutoRedirect = $false" in argv), argv[:200])
    # --- addresses that must never get it
    bad = []
    for why, u in NO.items():
        SEEN.clear(); WORLD.clear(); WORLD[u] = ("ok", b"x")
        e = raised(lambda: su._get(u))
        if any("authorization" in x["headers"] for x in SEEN) or leaked(TOKEN, e) or any(TOKEN in x["stdin"] for x in SEEN): bad.append(why)
        if why in ("user name in the address", "the real host as a user name", "plain http") and SEEN: bad.append(why + " (a request was made)")
    check(f"[{way}] look-alike host, path substring, user-info, other port, storage hosts, other repository: none of them receives the token", bad == [], bad)
    # --- a redirect to the storage host: followed, without the token
    SEEN.clear(); WORLD.clear()
    WORLD[API + "/releases/assets/17"] = ("to", 302, "https://objects.githubusercontent.invalid/asset/17?X-Sig=abc")
    WORLD["https://objects.githubusercontent.invalid/asset/17?X-Sig=abc"] = ("ok", b"ZIPBYTES")
    got = su._get(API + "/releases/assets/17", accept="application/octet-stream")
    r = sent_by(way)
    check(f"[{way}] a redirect to another host is followed here, hop by hop: the first request has the token, the second has none",
          got == b"ZIPBYTES" and len(r) == 2 and "authorization" in r[0]["headers"] and "authorization" not in r[1]["headers"] and TOKEN not in r[1]["stdin"], [(x["url"], sorted(x["headers"])) for x in r])
    # --- there and back again: the token does not return
    SEEN.clear(); WORLD.clear()
    WORLD[API + "/a"] = ("to", 302, "https://elsewhere.invalid/b"); WORLD["https://elsewhere.invalid/b"] = ("to", 307, API + "/c"); WORLD[API + "/c"] = ("ok", b"back")
    got = su._get(API + "/a"); r = sent_by(way)
    check(f"[{way}] once a request has left the place it was made for, the token never comes back (also when a later hop returns)",
          got == b"back" and [("authorization" in x["headers"]) for x in r] == [True, False, False], [(x["url"], "authorization" in x["headers"]) for x in r])
    # --- same host, but a route the token is not for
    SEEN.clear(); WORLD.clear()
    WORLD[API + "/a"] = ("to", 302, "/repos/someone-else/other/zipball"); WORLD["https://api.github.com/repos/someone-else/other/zipball"] = ("ok", b"z")
    su._get(API + "/a"); r = sent_by(way)
    check(f"[{way}] a redirect on the same host to a route outside the repository loses the token too", len(r) == 2 and "authorization" in r[0]["headers"] and "authorization" not in r[1]["headers"])
    SEEN.clear(); WORLD.clear()
    WORLD[API + "/a"] = ("to", 301, API + "/b"); WORLD[API + "/b"] = ("ok", b"same")
    su._get(API + "/a"); r = sent_by(way)
    check(f"[{way}] a redirect inside the repository's own routes keeps it", len(r) == 2 and all("authorization" in x["headers"] for x in r))
    # --- https -> http, and a redirect to an address with a user name: refused, no request is made there
    for label, target in (("down to plain http", "http://api.github.com/repos/owner-x/repo-y/b"), ("to an address with a user name in it", "https://u:p@elsewhere.invalid/b")):
        SEEN.clear(); WORLD.clear(); WORLD[API + "/a"] = ("to", 302, target); WORLD[target] = ("ok", b"never")
        e = raised(lambda: su._get(API + "/a"))
        check(f"[{way}] a redirect {label} is refused before a request is made there", isinstance(e, su.UpdateError) and len(SEEN) == (1 if way == "urllib" else 2) and all(x["url"] != target for x in SEEN) and not leaked(TOKEN, e),
              (type(e).__name__, str(e)[:120], [x["url"] for x in SEEN]))
    # --- a loop of redirects ends
    SEEN.clear(); WORLD.clear(); WORLD[API + "/a"] = ("to", 302, API + "/b"); WORLD[API + "/b"] = ("to", 302, API + "/a")
    e = raised(lambda: su._get(API + "/a"))
    check(f"[{way}] a loop of redirects is stopped after {net.MAX_REDIRECTS} hops", e is not None and len(sent_by(way)) == net.MAX_REDIRECTS + 1, (type(e).__name__, len(sent_by(way))))
    # --- an answer of the server (404) is an HttpError, on every way
    SEEN.clear(); WORLD.clear()
    e = raised(lambda: su._get(API + "/missing"))
    check(f"[{way}] an error code of the server comes back as HttpError with its code; its text holds no address query and no token", isinstance(e, net.HttpError) and e.code == 404 and not leaked(TOKEN, e), repr(e))

# --- error texts
use("urllib"); SEEN.clear(); WORLD.clear()
FAIL["urllib"] = ssl.SSLError(f"[SSL: CERTIFICATE_VERIFY_FAILED] while sending Authorization: Bearer {TOKEN} and x-api-key: dummy-token-123")
e = raised(lambda: su._get(API + "/releases/latest"))
check("an error text that would repeat a header is cleaned before it is raised (no token, no 'dummy-token-123')", isinstance(e, net.CertificateProblem) and TOKEN not in str(e) and "dummy-token-123" not in str(e), str(e))
use("curl"); SEEN.clear(); WORLD.clear(); FAIL["curl"] = f"curl: (60) SSL certificate problem. Authorization: Bearer {TOKEN}"
e = raised(lambda: su._get(API + "/releases/latest"))
check("... also what curl prints when it fails", isinstance(e, net.CertificateProblem) and TOKEN not in str(e) and not leaked(TOKEN, e), str(e))
check("the plain-words explanation of a download problem holds no token", TOKEN not in su.explain(OSError(f"refused; token={TOKEN}")) and "dummy-token-123" not in su.explain(OSError("Authorization: Bearer dummy-token-123")))
use("urllib"); SEEN.clear(); WORLD.clear(); WORLD["https://files.invalid/a.txt"] = ("ok", b"plain")
check("net.fetch(url, headers, timeout) still works with its three positional arguments (the web search uses it)", net.fetch("https://files.invalid/a.txt", {"User-Agent": "t"}, 5) == b"plain")
check("net.fetch refuses anything but https, and a header with a line break", isinstance(raised(lambda: net.fetch("http://files.invalid/a.txt")), ValueError) and isinstance(raised(lambda: net.fetch("https://files.invalid/a.txt", {"X": "a\r\nAuthorization: x"})), ValueError) and len(SEEN) == 1)
SEEN.clear(); WORLD["https://files.invalid/r"] = ("to", 302, "https://other.invalid/r"); WORLD["https://other.invalid/r"] = ("ok", b"r")
net.fetch("https://files.invalid/r", {"Authorization": "Bearer dummy-token-123", "X-Api-Key": "dummy-token-123", "Cookie": "s=dummy-token-123", "User-Agent": "t"}, 5)
check("for every caller of net.fetch: Authorization, API-key and cookie headers are dropped when a redirect leaves the origin; harmless headers stay",
      len(SEEN) == 2 and set(SEEN[1]["headers"]) == {"user-agent"} and "authorization" in SEEN[0]["headers"], [sorted(x["headers"]) for x in SEEN])
ctx = net.context()
check("certificates are verified: the context requires a certificate and checks the host name", ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True)
mine = ("net.py", "self_update.py", "assistant.py", "assistant_backends.py", "assistant_secrets.py", "update_verify.py")
off = [f for f in mine if any(w in (A / f).read_text(encoding="utf-8") for w in ("CERT_NONE", "_create_unverified_context", "check_hostname = False", "--insecure", '"-k"', "SkipCertificateCheck", "ServerCertificateValidationCallback"))]
check("no way out switches the certificate check off", off == [], off)
use("curl"); SEEN.clear(); WORLD.clear(); WORLD[API] = ("ok", b"1"); su._get(API); argv = sent_by("curl")[-1]["argv"]
check("curl is started without a .curlrc (-q first), for https only, with its config on standard input, and never with -k", argv[1] == "-q" and argv[argv.index("--proto") + 1] == "=https" and argv[-2:] == ["-K", "-"] and "-k" not in argv and "--insecure" not in argv, argv)

# ================================================================ local-only mode and the switches: at the place the request is made
use("urllib"); SEEN.clear(); WORLD.clear(); WORLD[API + "/releases/latest"] = ("ok", b"{}")
op.set_level("local_only")
e1 = raised(lambda: su._get(API + "/releases/latest")); e2 = raised(lambda: su.find_update("github:" + REPO, "1.0")); e3 = raised(lambda: net.fetch(API, {}, 5, channel="update_check"))
e4 = raised(lambda: su.fetch_and_unpack({"zip": "https://files.invalid/new.zip"}, str(TMP / "work_lo")))
check("local-only mode: no update check and no update download leave the computer (refused before any way out is tried), with a plain message",
      isinstance(e1, su.UpdateError) and isinstance(e2, su.UpdateError) and isinstance(e3, op.Blocked) and isinstance(e4, su.UpdateError) and SEEN == [] and "Local-only" in str(e2), (str(e2)[:100], len(SEEN)))
op.set_level("minimal"); op.set_channel("update_check", False)
e = raised(lambda: su.find_update("github:" + REPO, "1.0"))
check("the update check switched off in Privacy: nothing is asked either", isinstance(e, su.UpdateError) and SEEN == [], str(e)[:100])
op.set_channel("update_check", True)

# ================================================================ SEC-04: the AI service
AISEEN = []; AIPLAN = {"answer": {"data": []}, "error": None}
class AIOpener:
    def __init__(self, local, origin): self.local = local; self.origin = origin
    def open(self, req, timeout=None):
        AISEEN.append({"url": req.full_url, "headers": {k.lower(): v for k, v in req.header_items()}, "local": self.local, "body": req.data})
        if AIPLAN["error"] is not None: raise AIPLAN["error"]
        return FakeResp(json.dumps(AIPLAN["answer"]).encode())
real_ai_opener = ai._opener
ai._opener = lambda local, origin: AIOpener(local, origin)
KEY = "dummy-key-123"
e = raised(lambda: ai._http("POST", "http://remote-ai.invalid/v1/chat/completions", {"Authorization": "Bearer " + KEY}, {"x": 1}))
check("a remote AI address with plain http is refused before anything is sent (the key and the text would travel unprotected)", isinstance(e, ai.AIError) and isinstance(e, PermissionError) and AISEEN == [] and "https" in str(e) and KEY not in str(e), str(e)[:120])
bad = [u for u in ("http://localhost.evil.invalid:11434/v1/models", "http://127.0.0.1.evil.invalid:11434/v1", "http://evil.invalid/localhost/v1", "http://10.0.0.5:11434/v1", "ftp://ai.invalid/v1", "https://u:p@ai.invalid/v1")
       if not isinstance(raised(lambda: ai._http("GET", u, {"Authorization": "Bearer " + KEY})), ai.AIError)]
check("a name that only contains 'localhost', another computer of the network, another scheme, an address with a password: all refused before transport", bad == [] and AISEEN == [], bad)
ok = []
for u in ("http://localhost:11434/v1/models", "http://127.0.0.1:11434/v1/models", "http://[::1]:11434/v1/models"):
    AISEEN.clear(); ai._http("GET", u, {}); ok.append(len(AISEEN) == 1 and AISEEN[0]["local"] is True)
check("a model on this computer is reached with plain http on the approved port: localhost, 127.0.0.1 and IPv6 ::1, decided from the parsed host", all(ok), ok)
AISEEN.clear(); e = raised(lambda: ai._http("GET", "http://127.0.0.1:9999/v1/models", {}))
check("... but not on a port that is not approved", isinstance(e, ai.AIError) and AISEEN == [] and "port" in str(e), str(e)[:120])
AISEEN.clear(); ai._http("POST", "https://ai-service.invalid/v1/chat/completions", {"Authorization": "Bearer " + KEY}, {"x": 1})
check("a remote https service is used, and is not treated as local", len(AISEEN) == 1 and AISEEN[0]["local"] is False and AISEEN[0]["headers"]["authorization"] == "Bearer " + KEY)
# the real opener: proxy bypass for this computer only, and the redirect rule
old_env = {k: os.environ.get(k) for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")}
os.environ["HTTP_PROXY"] = os.environ["http_proxy"] = "http://proxy.invalid:3128"; os.environ["HTTPS_PROXY"] = os.environ["https_proxy"] = "http://proxy.invalid:3128"
lo = real_ai_opener(True, "http://localhost:11434/v1"); re_ = real_ai_opener(False, "https://ai-service.invalid/v1")
for k, v in old_env.items():
    if v is None: os.environ.pop(k, None)
    else: os.environ[k] = v
proxied = lambda o: any(isinstance(h, urllib.request.ProxyHandler) and getattr(h, "proxies", None) for h in o.handlers)
check("a model on this computer is never reached through a proxy; a remote service uses the proxy of the system as before", not proxied(lo) and proxied(re_))
hs = next(h for h in re_.handlers if isinstance(h, urllib.request.HTTPSHandler))
check("the AI connection verifies certificates (host name and chain)", hs._context.verify_mode == ssl.CERT_REQUIRED and hs._context.check_hostname is True)
rh = next(h for h in re_.handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
rq = urllib.request.Request("https://ai-service.invalid/v1/models", headers={"Authorization": "Bearer " + KEY})
e1 = raised(lambda: rh.redirect_request(rq, None, 302, "Found", {}, "https://other-service.invalid/v1/models"))
e2 = raised(lambda: rh.redirect_request(rq, None, 302, "Found", {}, "http://ai-service.invalid/v1/models"))
e3 = raised(lambda: rh.redirect_request(rq, None, 302, "Found", {}, "https://ai-service.invalid:8443/v1/models"))
same = rh.redirect_request(rq, None, 302, "Found", {}, "https://ai-service.invalid/v2/models")
check("the AI opener does not follow a redirect to another host, to another port or down to plain http (the key would go there); the same service is fine",
      all(isinstance(x, ai.AIError) for x in (e1, e2, e3)) and KEY not in str(e1) + str(e2) and same is not None and same.full_url == "https://ai-service.invalid/v2/models", (str(e1)[:90], str(e2)[:90]))
# the key and the service it was entered for
OTHER = ai.PROVIDERS["other"]["name"]; K1 = "dummy-key-service-one-123"
c1 = ai.detect(K1, "https://svc-one.invalid/v1", OTHER, entered=True)
check("connecting says which host the requests really go to", c1["host"] == "svc-one.invalid" and c1["name"] == "svc-one.invalid" and ai.detect("", "https://u:pw@svc.invalid:8443/v1", OTHER)["host"] == "svc.invalid:8443" and "pw" not in ai.detect("", "https://u:pw@svc.invalid:8443/v1", OTHER)["name"])
AISEEN.clear(); ai.models(c1)
check("the key goes to the service it was entered for", len(AISEEN) == 1 and AISEEN[0]["headers"]["authorization"] == "Bearer " + K1 and AISEEN[0]["url"].startswith("https://svc-one.invalid/"))
AISEEN.clear(); c2 = ai.detect(K1, "https://svc-two.invalid/v1", OTHER)
e = raised(lambda: ai.models(c2)); e_chat = raised(lambda: ai.chat(c2, "m", "s", [{"role": "user", "content": "hello"}]))
check("after the address changed, the key of the old service is NOT sent to the new one: a plain message names both hosts, nothing is sent",
      isinstance(e, ai.AIError) and isinstance(e_chat, ai.AIError) and AISEEN == [] and "svc-one.invalid" in str(e) and "svc-two.invalid" in str(e) and K1 not in str(e), str(e)[:160])
H = TMP / "assistant_home"; H.mkdir()
ai.save_settings(str(H), {"keys": {"other": K1}, "addresses": {"other": "https://svc-one.invalid/v1"}})
ai._BOUND.clear()                                          # as after a restart: only what is on disk is known
c = ai.load_settings(str(H)); k = ai.reveal_key(c["keys"]["other"])
AISEEN.clear(); e = raised(lambda: ai.models(ai.detect(k, "https://svc-two.invalid/v1", OTHER)))
check("... also for a key read back from the settings: the service is remembered beside the key reference", k == K1 and c["keys"]["other"].get("origin") == "https://svc-one.invalid:443" and isinstance(e, ai.AIError) and AISEEN == [])
ai.save_settings(str(H), {"keys": {}, "addresses": {"other": "https://svc-two.invalid/v1"}})        # 'Remove the key'
AISEEN.clear(); ai.models(ai.detect(K1, "https://svc-two.invalid/v1", OTHER, entered=True))
check("after the saved key was removed and entered again for the new service, it is used there", len(AISEEN) == 1 and AISEEN[0]["url"].startswith("https://svc-two.invalid/"))
check("a host that only has a provider's name in it is not taken for that provider", ai.detect("", "https://anthropic.evil.invalid/v1", "")["provider"] == "other" and ai.detect("dummy-key-123", "https://api.anthropic.com", "")["provider"] == "anthropic"
      and ai.detect("", "http://localhost.evil.invalid:11434", "")["provider"] == "other" and ai.detect("", "http://localhost:11434/v1", "")["provider"] == "ollama")
# an error answer that repeats the key
AISEEN.clear(); body = json.dumps({"error": {"message": f"bad credentials: Authorization: Bearer {KEY} / sk-ant-" + "Z" * 30}}).encode()
class Err(urllib.error.HTTPError):
    def read(self): return body
AIPLAN["error"] = Err("https://ai-service.invalid/v1", 401, "x", email.message.Message(), None)
e = raised(lambda: ai._http("POST", "https://ai-service.invalid/v1/chat/completions", {"Authorization": "Bearer " + KEY}, {}))
check("an error answer of the service that repeats the key is cleaned before it becomes a message", isinstance(e, ai.AIError) and KEY not in str(e) and "Z" * 30 not in str(e) and "code 401" in str(e), str(e))
AIPLAN["error"] = None
# local-only and the AI switch, at the transport boundary
AISEEN.clear(); op.set_level("local_only")
e = raised(lambda: ai._http("POST", "https://ai-service.invalid/v1/chat/completions", {"Authorization": "Bearer " + KEY}, {"q": 1}))
e_loc = raised(lambda: ai._http("GET", "http://localhost:11434/v1/models", {}))
e_b = raised(lambda: ab._post("https://ai-service.invalid/v1", {}, {})); e_cli = raised(lambda: (setattr(ab, "cli_available", lambda program="claude": True), ab.cli("stack them", []))[1])
check("local-only mode: no AI request is sent, by the assistant or by the sentence backends (also not to a command-line AI program)", isinstance(e, ai.AIError) and isinstance(e, PermissionError) and isinstance(e_loc, ai.AIError)
      and isinstance(e_b, op.Blocked) and isinstance(e_cli, op.Blocked) and AISEEN == [] and "Local-only" in str(e), str(e)[:100])
op.set_level("minimal"); op.set_channel("ai", False)
e = raised(lambda: ai._http("POST", "https://ai-service.invalid/v1/chat/completions", {}, {}))
check("the AI switched off in Privacy: nothing is sent", isinstance(e, ai.AIError) and AISEEN == [])
op.set_channel("ai", True)
# the sentence backends
AISEEN.clear(); e = raised(lambda: ab._post("http://remote-ai.invalid/api/chat", {}, {"x-api-key": KEY}))
check("the sentence backends follow the same address rules (remote plain http refused before transport)", isinstance(e, op.Blocked) and AISEEN == [])
os.environ[sec.ENV] = "sk-ant-api03-" + "E" * 40
e = raised(lambda: ab.api_key("stack them", [], endpoint="https://other-service.invalid/v1/messages"))
okc, msg = ab.test_connection(endpoint="https://other-service.invalid/v1/messages")
check("the stored Claude key is never sent to another address than the Claude service", isinstance(e, aa.ActionError) and AISEEN == [] and okc is False and "E" * 40 not in msg, msg)
os.environ.pop(sec.ENV)

# ================================================================ SEC-06: where keys are kept
secure_store.forget_session()
check("this test system has no protected store (no keyring): a key is kept for the session only", secure_store.backend() in ("session", "dpapi"))
if os.name != "nt":
    check("protect_key never returns a plain-text form (None when it cannot be kept safely)", ai.protect_key("dummy-key-123") is None and ai.protect_key("") is None)
    check("... with a name it goes into the store for this session, and still nothing may be written", ai.protect_key("dummy-key-123", name="ai:test") is None and secure_store.get("ai:test") == "dummy-key-123")
src_ai = (A / "assistant.py").read_text(encoding="utf-8")
check("no code path writes {'plain': key} any more", 'return {"plain"' not in src_ai and '{"plain": key}' not in src_ai)
H2 = TMP / "home2"; H2.mkdir(); P2 = H2 / "assistant.json"
lost = ai.save_settings(str(H2), {"keys": {"anthropic": "sk-ant-" + "q" * 30, "openai": "dummy-key-123"}, "models": {"anthropic": "m"}, "addresses": {}})
txt = P2.read_text(encoding="utf-8"); d2 = json.loads(txt)
SESSION = secure_store.backend() == "session"
check("store unavailable: the settings file holds only a reference and the service, never the key; the caller is told the key lasts for this session",
      "q" * 30 not in txt and "dummy-key-123" not in txt and d2["keys"]["anthropic"] == {"store": "ai:anthropic", "origin": "https://api.anthropic.com:443"} and (sorted(lost) == ["anthropic", "openai"] or not SESSION), txt[:200].replace("\n", " "))
priv = "".join(p.read_text(encoding="utf-8", errors="replace") for p in (TMP / "private").rglob("*") if p.is_file()) if (TMP / "private").exists() else ""
check("... and no other file of the private folder holds it", "q" * 30 not in priv and "dummy-key-123" not in priv)
c = ai.load_settings(str(H2))
check("... it still works until the app closes", ai.reveal_key(c["keys"]["anthropic"]) == "sk-ant-" + "q" * 30 and ai.reveal_key(c["keys"]["openai"]) == "dummy-key-123")
secure_store.forget_session(); c = ai.load_settings(str(H2))
check("... and after a restart it is simply not there (asked for again), not read from a plain copy", not SESSION or (ai.reveal_key(c["keys"]["anthropic"]) == "" and ai.reveal_key(c["keys"]["openai"]) == ""))
# an old settings file with plain keys
P2.write_text(json.dumps({"keys": {"openai": {"plain": "dummy-plain-key-AAA"}, "gemini": "dummy-plain-key-BBB"}, "key": "sk-ant-" + "L" * 30, "models": {"openai": "m1"}}), encoding="utf-8")
ai.storage_notes(); c = ai.load_settings(str(H2)); txt = P2.read_text(encoding="utf-8"); notes = ai.storage_notes()
check("plain keys left by an older version are moved into the store when the settings are read, and removed from the file",
      all(s not in txt for s in ("dummy-plain-key-AAA", "dummy-plain-key-BBB", "L" * 30, '"plain"')) and '"key"' not in txt and ai.reveal_key(c["keys"]["openai"]) == "dummy-plain-key-AAA"
      and ai.reveal_key(c["keys"]["gemini"]) == "dummy-plain-key-BBB" and ai.reveal_key(c["keys"]["anthropic"]) == "sk-ant-" + "L" * 30 and c["models"] == {"openai": "m1"}, txt[:240].replace("\n", " "))
check("... and with no protected store the user is told plainly that the key lasts only until the app closes", len(notes) == 3 and (not SESSION or all("until the app closes" in n for n in notes)) and not any("dummy-plain" in n or "L" * 30 in n for n in notes), notes[:1])
# a protected store exists (a stand-in for the keyring of the system)
class FakeRing:
    __module__ = "standin.backend"
    data = {}
class FakeKeyring:
    @staticmethod
    def get_keyring(): return FakeRing()
    @staticmethod
    def set_password(service, name, value): FakeRing.data[(service, name)] = value
    @staticmethod
    def get_password(service, name): return FakeRing.data.get((service, name))
    @staticmethod
    def delete_password(service, name): FakeRing.data.pop((service, name), None)
if os.name != "nt":
    sys.modules["keyring"] = FakeKeyring; os.environ.pop("OPS_NO_KEYRING", None); secure_store.forget_session()
    check("(stand-in) a keyring is found", secure_store.backend() == "keyring")
    H3 = TMP / "home3"; H3.mkdir(); P3 = H3 / "assistant.json"
    lost = ai.save_settings(str(H3), {"keys": {"kimi": "dummy-key-kimi-123"}, "addresses": {}})
    txt = P3.read_text(encoding="utf-8"); secure_store.forget_session(); c = ai.load_settings(str(H3))
    check("store available: the key is in the keyring, the file holds a reference, nothing is reported lost, and it is there after a restart",
          lost == [] and "dummy-key-kimi-123" not in txt and FakeRing.data.get((secure_store.SERVICE, "ai:kimi")) == "dummy-key-kimi-123" and ai.reveal_key(c["keys"]["kimi"]) == "dummy-key-kimi-123")
    P3.write_text(json.dumps({"keys": {"openai": {"plain": "dummy-plain-key-CCC"}}}), encoding="utf-8"); ai.storage_notes()
    c = ai.load_settings(str(H3)); notes = ai.storage_notes(); secure_store.forget_session()
    check("store available: a plain key of an older version is moved into the keyring and removed from the file",
          "dummy-plain-key-CCC" not in P3.read_text(encoding="utf-8") and FakeRing.data.get((secure_store.SERVICE, "ai:openai")) == "dummy-plain-key-CCC" and ai.reveal_key(ai.load_settings(str(H3))["keys"]["openai"]) == "dummy-plain-key-CCC"
          and len(notes) == 1 and "protected store" in notes[0])
    ai.save_settings(str(H3), {"keys": {}})
    check("removing a key removes it from the store too", (secure_store.SERVICE, "ai:openai") not in FakeRing.data and secure_store.get("ai:openai") == "")
    where = sec.save("sk-ant-api03-" + "S" * 40)
    check("the sentence assistant's key uses the same store (no secrets file of its own)", where == "keyring" and sec.load() == "sk-ant-api03-" + "S" * 40 and not os.path.exists(sec.secrets_path()) and sec.status() == "set")
    sec.clear(); check("... and can be removed", sec.load() == "" and sec.status() == "not set")
    # the update token
    how = su.set_token("dummy-token-123")
    check("the GitHub update token is kept in the same store", how == "keyring" and FakeRing.data.get((secure_store.SERVICE, su.TOKEN_NAME)) == "dummy-token-123" and su.TOKEN == "dummy-token-123")
    su.set_token(""); check("... and forgotten when it is cleared", su.TOKEN == "" and (secure_store.SERVICE, su.TOKEN_NAME) not in FakeRing.data)
    r = su.load_token({"plain": "dummy-token-123"})
    check("a token an older version left in the settings file is moved into the store, and the caller is told to remove it from the file",
          r["drop_legacy"] is True and r["token"] is True and su.TOKEN == "dummy-token-123" and FakeRing.data.get((secure_store.SERVICE, su.TOKEN_NAME)) == "dummy-token-123" and "protected store" in r["note"] and "dummy-token-123" not in r["note"])
    su.set_token(""); sys.modules.pop("keyring", None); os.environ["OPS_NO_KEYRING"] = "1"; secure_store.forget_session()
r = su.load_token("dummy-token-123")
check("no protected store: the old token is still removed from the settings file and lives until the app closes", r["drop_legacy"] is True and su.TOKEN == "dummy-token-123" and (os.name == "nt" or "until the app closes" in r["note"]))
su.set_token("")
# the Qt window's own call site: the settings file loses the token
try:
    import workspace_menu as WM, workspace_qt as WQ
    Path(os.environ["OPS_SETTINGS_FILE"]).write_text(json.dumps({"update_token": {"plain": "dummy-token-123"}, "update_source": "off"}), encoding="utf-8")
    class Win:
        def __init__(self): self.cfg = json.loads(Path(os.environ["OPS_SETTINGS_FILE"]).read_text(encoding="utf-8")); self.logged = []
        def log(self, t): self.logged.append(t)
    wn = Win(); WM._upd_token(wn); left = Path(os.environ["OPS_SETTINGS_FILE"]).read_text(encoding="utf-8")
    check("the main window: the token is read from the store, and the copy in settings_modern.json is gone after the first start",
          "dummy-token-123" not in left and json.loads(left)["update_token"] == "" and wn.cfg["update_token"] == "" and (os.name == "nt" or su.TOKEN == "dummy-token-123") and wn.logged and "dummy-token-123" not in " ".join(wn.logged), left.replace("\n", " "))
    su.set_token("")
except ImportError as e:
    print(f"SKIP  the main window's token call site (PySide6 is not installed here: {e})")
# the encrypted form older versions wrote on Windows is still read (the Windows function itself is replaced by a stand-in here)
real_dpapi = ai._dpapi
ai._dpapi = lambda data, protect: bytes(b ^ 0x5A for b in data)
blob = {"dpapi": base64.b64encode(bytes(b ^ 0x5A for b in b"dummy-key-old-windows")).decode()}
check("(stand-in for Windows data protection) a key saved by an earlier version as {'dpapi': ...} is still read", ai.reveal_key(blob) == "dummy-key-old-windows" and su.load_token(blob)["token"] is True and su.TOKEN == "dummy-key-old-windows")
ai._dpapi = real_dpapi; su.set_token("")
check("redaction covers the keys of every provider and Authorization values, not only 'sk-'", all(s not in sec.redact(f"x {s} y") for s in ("sk-ant-" + "a" * 30, TOKEN, "AIza" + "b" * 30)) and "dummy-token-123" not in sec.redact("Authorization: Bearer dummy-token-123")
      and "sk-...****" in sec.redact("x sk-ant-api03-" + "A" * 40))
legacy_src = (A / "origin_plot_app.py").read_text(encoding="utf-8")
check("the earlier window no longer writes the update token into settings.json", '"update_token": cfg.get("update_token", "")' not in legacy_src and "su.set_token(" in legacy_src and 'cfg["update_token"] = ai.protect_key' not in legacy_src)

net._opener, net.subprocess.run, net._curl_exe, net._powershell_exe = REAL["opener"], REAL["run"], REAL["curl"], REAL["ps"]; ai._opener = real_ai_opener
print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

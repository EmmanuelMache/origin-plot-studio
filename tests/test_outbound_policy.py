"""The shared security foundations: the outbound-data policy (levels, channels, addresses, credential routing rule,
redaction, aliases, profile) and the credential store (never plain text on disk). No Qt, no network."""
import os, sys, json, tempfile
from pathlib import Path
PRIV = tempfile.mkdtemp(); os.environ["OPS_PRIVATE_DIR"] = PRIV; os.environ["OPS_NO_OPEN"] = "1"
os.environ.pop("OPS_PROFILE", None); os.environ.pop("OPS_LOCAL_ONLY", None); os.environ["OPS_NO_KEYRING"] = "1"
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app"))
import outbound_policy as P, secure_store as S
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
def blocked(fn, *a, **k):
    try: fn(*a, **k); return ""
    except P.Blocked as e: return str(e) or "blocked"

# ---- profile and defaults
check("the developer's own copy: profile 'owner', level 'minimal', diagnostics and shared learning OFF by default", P.profile() == "owner" and P.level() == "minimal" and not P.channel_on("diagnostics") and not P.channel_on("learning_sync") and P.allowed("ai") and P.allowed("update_check"))
os.environ["OPS_PROFILE"] = "friends"; P.reload()
check("a build for other people (profile 'friends') starts in local-only mode: nothing is sent until it is turned on", P.profile() == "friends" and P.level() == "local_only" and not any(P.allowed(c) for c in P.CHANNELS), P.level())
os.environ.pop("OPS_PROFILE"); P.reload()

# ---- local-only is enforced where a request is sent
P.set_level("local_only")
msgs = {c: blocked(P.require, c, "https://service.example.invalid/x") for c in P.CHANNELS}
check("local-only mode refuses EVERY channel at the point of sending (update check and download, AI, web search, diagnostics, shared learning), in plain words", all(m and "Local-only" in m for m in msgs.values()), msgs)
check("... and it is remembered in the private folder, not in the program or a project", json.load(open(os.path.join(PRIV, "outbound_policy.json")))["level"] == "local_only")
os.environ["OPS_LOCAL_ONLY"] = "1"; P.set_level("scientific"); P.reload()
check("OPS_LOCAL_ONLY=1 forces local-only whatever was saved", P.local_only()); os.environ.pop("OPS_LOCAL_ONLY"); P.reload()
P.set_level("minimal")
check("a channel that is switched off is refused although the level allows connections", bool(blocked(P.require, "diagnostics", "https://service.example.invalid/x")) and not blocked(P.require, "ai", "https://service.example.invalid/x"))
check("an unknown channel is refused (nothing is sent by default)", bool(blocked(P.require, "telemetry", "https://service.example.invalid/x")))
check("what was let through is recorded as channel and host only", P.audit()[-1] == {"channel": "ai", "host": "service.example.invalid"})

# ---- what each level lets an AI request carry
table = {lv: {k for k in P.KINDS if (P.set_level(lv) or True) and P.permits(k)} for lv in P.LEVELS}
check("levels: minimal = prompt + generic type information; metadata adds labels and structure; measurements, results, images, documents and paths need 'scientific'",
      table["local_only"] == set() and table["minimal"] == {"prompt", "generic"} and table["metadata"] == {"prompt", "generic", "labels", "structure"}
      and {"measurements", "results", "images", "documents", "paths"} <= table["scientific"] and not ({"measurements", "results", "images", "documents", "paths"} & table["metadata"]), table)
seen = []; P.on_change(seen.append); P.set_level("minimal"); P.set_level("minimal"); P.set_ai_destination("https://a.example.invalid"); P.set_ai_destination("https://b.example.invalid")
check("a change of level or of the AI destination is announced (queued history must be cleared), an unchanged value is not", seen == ["level", "ai_destination", "ai_destination"], seen)

# ---- addresses
check("https is accepted; plain http to another computer is refused before anything is sent", not blocked(P.check_url, "https://api.example.invalid/v1") and "https" in blocked(P.check_url, "http://api.example.invalid/v1"))
check("http to a model on THIS computer only when asked for, on an approved port, and only for a real loopback address (also IPv6)",
      not blocked(P.check_url, "http://localhost:11434/api", loopback_http=True) and not blocked(P.check_url, "http://127.0.0.1:11434/", loopback_http=True) and not blocked(P.check_url, "http://[::1]:11434/", loopback_http=True)
      and bool(blocked(P.check_url, "http://localhost:11434/api")) and bool(blocked(P.check_url, "http://127.0.0.1:9999/", loopback_http=True)))
check("a name that only CONTAINS 'localhost' or '127.0.0.1' is not this computer", all(blocked(P.check_url, u, loopback_http=True) for u in ("http://localhost.example.invalid:11434/", "http://127.0.0.1.example.invalid:11434/", "http://example.invalid/localhost", "http://notlocalhost:11434/"))
      and P.is_loopback("LOCALHOST.") and P.is_loopback("127.5.5.5") and not P.is_loopback("localhost.evil.invalid") and not P.is_loopback("10.0.0.1"))
check("an address with a user name or password, without a host, or with another scheme is refused", all(blocked(P.check_url, u) for u in ("https://user:pw@api.example.invalid/", "https://token@api.example.invalid/", "https:///path", "ftp://api.example.invalid/", "file:///etc/passwd", "api.example.invalid/v1")))
check("'the same place' means scheme, host and port", P.same_origin("https://API.example.invalid/a", "https://api.example.invalid:443/b") and not P.same_origin("https://api.example.invalid/a", "https://api.example.invalid:8443/a") and not P.same_origin("https://api.example.invalid/", "http://api.example.invalid/") and not P.same_origin("https://api.example.invalid/", "https://cdn.example.invalid/"))

# ---- the credential routing rule (SEC-01)
R = [("api.github.com", 443, ["/repos/owner/project"])]
yes = ["https://api.github.com/repos/owner/project/releases/latest", "https://api.github.com/repos/owner/project", "https://API.GITHUB.COM:443/repos/owner/project/contents/x.py"]
no = ["https://github.attacker.invalid/release.zip", "https://example.invalid/github/release.zip", "https://api.github.com.attacker.invalid/repos/owner/project/x", "https://xapi.github.com/repos/owner/project/x",
      "https://api.github.com:8443/repos/owner/project/x", "http://api.github.com/repos/owner/project/x", "https://u:p@api.github.com/repos/owner/project/x", "https://api.github.com/repos/owner/project-other/x",
      "https://api.github.com/repos/other/project/x", "https://raw.githubusercontent.com/owner/project/main/x.py", "https://objects.githubusercontent.com/repos/owner/project/x", "https://api.github.com/"]
check("a token goes only to the exact host, port and route it is for", all(P.token_allowed(u, R) for u in yes), [u for u in yes if not P.token_allowed(u, R)])
check("... never to a look-alike host, a word in the path, a sub-domain, another port, plain http, a user-info address, a neighbouring repository or a download host", not any(P.token_allowed(u, R) for u in no), [u for u in no if P.token_allowed(u, R)])

# ---- redaction
dummy = ["sk-ant-api03-DUMMYDUMMYDUMMY1234", "sk-proj-DUMMYDUMMYDUMMY1234", "sk-DUMMYDUMMYDUMMYDUMMY1234", "ghp_DUMMYDUMMYDUMMYDUMMYDUMMY12", "github_pat_DUMMYDUMMYDUMMYDUMMY_12", "AIzaDUMMYDUMMYDUMMYDUMMY123",
         "gsk_DUMMYDUMMYDUMMYDUMMY1234", "hf_DUMMYDUMMYDUMMYDUMMY1234", "sbp_DUMMYDUMMYDUMMYDUMMY1234", "eyJDUMMYDUMMY12.eyJDUMMYDUMMY34.DUMMYSIG56"]
text = "request failed: " + " | ".join(dummy) + ' | Authorization: Bearer plainDummyToken99 | x-api-key: "otherDummy77" | curl -H "api-key=thirdDummy55" | token=fourthDummy33&x=1'
red = P.redact(text)
check("credentials of every supported kind are taken out of a text (provider keys, GitHub tokens, JWTs, and whatever follows Authorization / api-key / token)", not any(d in red for d in dummy + ["plainDummyToken99", "otherDummy77", "thirdDummy55", "fourthDummy33"]) and "request failed" in red and "x=1" in red, red[:200])
check("... a private key block too; ordinary text and numbers stay", "PRIVATE KEY" not in P.redact("-----BEGIN PRIVATE KEY-----\nAAAA\nBBBB\n-----END PRIVATE KEY-----") and P.redact("2theta 29.41 intensity 2000, sample token ring") == "2theta 29.41 intensity 2000, sample token ring" and P.has_secret(dummy[3]) and not P.has_secret("plain words"))

# ---- aliases and paths
a = P.Aliases()
s1, s2, g1 = a.alias("sample", "ZQ-SENTINEL-SAMPLE-77"), a.alias("sample", "ZQ-OTHER-88"), a.alias("graph", "ZQ-SENTINEL-SAMPLE-77 pattern")
out = a.scrub("Graph ZQ-SENTINEL-SAMPLE-77 pattern compares ZQ-SENTINEL-SAMPLE-77 with ZQ-OTHER-88")
check("names that identify your work get stable stand-ins (the same name, the same alias), and a text is scrubbed of them", (s1, s2, g1) == ("Sample 1", "Sample 2", "Graph 1") and a.alias("sample", "ZQ-SENTINEL-SAMPLE-77") == "Sample 1" and "ZQ-" not in out and out == "Graph Graph 1 compares Sample 1 with Sample 2", out)
check("... and the answer can be shown with the real names again", a.restore("Make Sample 2 red in Graph 1") == "Make ZQ-OTHER-88 red in ZQ-SENTINEL-SAMPLE-77 pattern")
paths = "saved to C:\\Users\\tester\\secret_project_XK9\\run.csv and /home/tester/secret_project_XK9/out.png and \\\\server\\share\\x.xlsx done"
check("folder paths are replaced by '<folder>' (Windows drive, UNC and Unix home paths)", "secret_project_XK9" not in P.strip_paths(paths) and "tester" not in P.strip_paths(paths) and P.strip_paths(paths).count("<folder>") == 3 and P.strip_paths(paths).endswith("done"), P.strip_paths(paths))

check("... also a drive path written with forward slashes and a path under another root; units such as counts/s or °C/min are left alone", "secret" not in P.strip_paths("D:/work/secret_XK9/a.csv and /srv/lab/secret_XK9/b.csv") and P.strip_paths("5 °C/min, 12 counts/s, ratio 1/2/3, w/c 0.5") == "5 °C/min, 12 counts/s, ratio 1/2/3, w/c 0.5", P.strip_paths("D:/work/secret_XK9/a.csv and /srv/lab/secret_XK9/b.csv"))
b2 = P.Aliases(); b2.alias("sample", "Sample 2"); b2.alias("sample", "ZQ-REAL-9")
check("a real name that looks like a stand-in is not replaced twice (one pass)", b2.scrub("Sample 2 and ZQ-REAL-9") == "Sample 1 and Sample 2" and b2.restore("Sample 1 and Sample 2") == "Sample 2 and ZQ-REAL-9", b2.scrub("Sample 2 and ZQ-REAL-9"))
check("a route with steps back, doubled or encoded parts is no route a token was meant for; the path is compared without regard to case", not any(P.token_allowed(u, R) for u in ("https://api.github.com/repos/owner/project/../other/x", "https://api.github.com/repos/owner/project/%2e%2e/x", "https://api.github.com//repos/owner/project/x", "https://api.github.com/repos/owner/project/%252e/x"))
      and P.token_allowed("https://api.github.com/repos/Owner/Project/releases", R))
P.set_level("minimal"); was = P.loopback_ports()
check("a local model on another port must be approved first - then, and only for this computer, it is reached", bool(blocked(P.check_url, "http://127.0.0.1:8080/v1", loopback_http=True)) and P.approve_loopback_port(8080) and not blocked(P.check_url, "http://127.0.0.1:8080/v1", loopback_http=True)
      and bool(blocked(P.check_url, "http://203.0.113.9:8080/v1", loopback_http=True)) and P.approve_loopback_port(8080, on=False) and P.loopback_ports() == was and P.ai_destination() == "https://b.example.invalid")

# ---- the credential store
S.forget_session()
how = S.put("ai:demo", "dummy-key-123")
on_disk = "".join(open(os.path.join(b, f), errors="replace").read() for b, _d, fs in os.walk(PRIV) for f in fs)
check("without a protected store (this test system: no Windows protection, no keyring) a key is kept for the session only", S.backend() == "session" and how == "session" and S.get("ai:demo") == "dummy-key-123" and "never written to disk" in S.describe())
check("... and NEVER written to disk as plain text", "dummy-key-123" not in on_disk)
S.forget_session()
check("... so after a restart it is gone and is asked for again", S.get("ai:demo") == "" and not S.has("ai:demo"))
w, removable = S.migrate_plain("update:token", "legacy-plain-token-9")
on_disk = "".join(open(os.path.join(b, f), errors="replace").read() for b, _d, fs in os.walk(PRIV) for f in fs)
check("a key an older version kept as plain text is taken into the store; the caller may then delete the plain copy, and nothing plain is written", w == "session" and removable and S.get("update:token") == "legacy-plain-token-9" and "legacy-plain-token-9" not in on_disk)
S.delete("update:token"); check("a credential can be removed", S.get("update:token") == "" and S.put("x", "") == "")
class FakeRing:
    store = {}
    def set_password(self, svc, name, v): self.store[(svc, name)] = v
    def get_password(self, svc, name): return self.store.get((svc, name))
    def delete_password(self, svc, name): self.store.pop((svc, name), None)
ring = FakeRing(); S._keyring = lambda: ring; S.forget_session()
check("with a keyring of the system the key is kept there (not in a file) and read back after a restart", S.backend() == "keyring" and S.put("ai:demo", "dummy-key-456") == "keyring" and (S.forget_session() or S.get("ai:demo")) == "dummy-key-456"
      and ring.store == {("OriginPlotStudio", "ai:demo"): "dummy-key-456"} and not os.path.isfile(os.path.join(PRIV, "credentials.json")))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

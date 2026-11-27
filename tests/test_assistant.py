"""Tests of the assistant layer (no network except a local mock). Run: python tests/test_assistant.py"""
import sys, os, json, threading, http.server, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "origin_plot_app"))
import assistant_actions as aa, assistant_parser as ap, assistant_backends as ab, assistant_secrets as sec, system_check
ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print("PASS", name)
    else: fail += 1; print("FAIL", name)
def raises(f, *a, **k):
    try: f(*a, **k)
    except aa.ActionError: return True
    return False

a = ap.parse("plot TGA with DTG and annotate mass loss between 400 and 500 C")
check("tga command", a and a["action"] == "plot_tga" and a["params"]["intervals"] == [[400.0, 500.0]] and a["params"]["annotate"] and a["params"]["with_dtg"])
a = ap.parse("stack all XRD files with vertical offset"); check("stack command", a == {"action": "stack_xrd", "params": {}})
a = ap.parse("plot calorimetry, exclusion 45 min, mass 0.5 g"); check("calorimetry command", a == {"action": "plot_calorimetry", "params": {"mass_g": 0.5, "exclusion_min": 45.0}})
check("mg unit", ap.parse("calorimetry mass 500 mg")["params"]["mass_g"] == 0.5)
check("hours unit", ap.parse("calorimetry mass 1 g exclusion 1 h")["params"]["exclusion_min"] == 60.0)
a = ap.parse("generate 10 XRD scans from a template"); check("generate xrd command", a == {"action": "generate_xrd_scans", "params": {"n": 10}} and aa.validate(a)["params"]["n"] == 10)
check("generate 0 scans refused", raises(aa.validate, ap.parse("generate 0 xrd scans")))
act, msg = ap.run("make me a sandwich"); check("unknown gives help, no guess", act is None and "stack all XRD files" in msg)
check("calorimetry without mass refused", raises(aa.validate, ap.parse("plot calorimetry")))
check("zero mass refused", raises(aa.validate, {"action": "plot_calorimetry", "params": {"mass_g": 0}}))
check("negative mass refused", raises(aa.validate, {"action": "plot_calorimetry", "params": {"mass_g": -1}}))
check("unknown action rejected", raises(aa.validate, {"action": "run_python", "params": {"code": "import os"}}))
check("unknown parameter rejected", raises(aa.validate, {"action": "plot_tga", "params": {"code": "x"}}))
check("bad interval rejected", raises(aa.validate, {"action": "analyze_tga_steps", "params": {"intervals": [[500, 400]]}}))
check("fixed_value needs value", raises(aa.validate, {"action": "stack_xrd", "params": {"offset_mode": "fixed_value"}}))
check("defaults filled", aa.validate({"action": "plot_calorimetry", "params": {"mass_g": "0,5"}})["params"] == {"exclusion_min": 45.0, "mass_g": 0.5})

called = []; rec = []; H = {n: (lambda n=n, **p: called.append((n, p)) or "done") for n in aa.ACTIONS}
asked = []
r = aa.dispatch({"action": "stack_xrd", "params": {}}, H, lambda t: asked.append(t) or False, rec)
check("declined: nothing runs, nothing recorded", r is None and not called and not rec and asked[0].startswith("Run: stack_xrd") and asked[0].endswith("OK?"))
r = aa.dispatch({"action": "stack_xrd", "params": {}}, H, lambda t: True, rec)
check("confirmed: runs and is recorded", r == "done" and called == [("stack_xrd", {"offset_mode": "auto_percent"})] and rec[0]["action"] == "stack_xrd")
check("no handler -> refused", raises(aa.dispatch, {"action": "system_check", "params": {}}, {}, lambda t: True))

# provenance gets the confirmed actions
import paper_figures as pf
pf.CONFIRMED_ACTIONS[:] = rec; d = tempfile.mkdtemp()
p = pf.write_provenance(os.path.join(d, "f"), {"confirmed_assistant_actions": list(pf.CONFIRMED_ACTIONS)}, "v5.15.0")
check("confirmed action in provenance", json.load(open(p))["confirmed_assistant_actions"][0]["action"] == "stack_xrd")

# Ollama mock: valid JSON, invalid JSON, unknown action
class Mock(http.server.BaseHTTPRequestHandler):
    reply = ""; seen = []
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"])); Mock.seen.append(body.decode())
        out = json.dumps({"message": {"content": Mock.reply}}).encode(); self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), Mock); threading.Thread(target=srv.serve_forever, daemon=True).start()
# a model on this computer is reached with plain http only on a port approved in the privacy settings (outbound_policy): approve the
# mock's port, in a private folder made for this test (port 9 too: 'not running' must still be a refused connection, not a refusal of the policy)
os.environ["OPS_PRIVATE_DIR"] = tempfile.mkdtemp(); import outbound_policy
json.dump({"level": "minimal", "loopback_http_ports": [srv.server_port, 9]}, open(os.path.join(os.environ["OPS_PRIVATE_DIR"], "outbound_policy.json"), "w")); outbound_policy.reload()
cfg = {"ollama": {"address": f"http://127.0.0.1:{srv.server_port}", "model": "m"}}
Mock.reply = '{"action": "stack_xrd", "params": {"offset_mode": "fixed_value", "offset_value": 100}}'
act, _ = ab.interpret("stack them", ["a.xrdml", "b.xrdml"], "ollama", cfg)
check("ollama valid JSON used", act and act["params"]["offset_value"] == 100.0)
sent = Mock.seen[-1]; check("ollama sees only action list, file names, sentence", "a.xrdml" in sent and "stack them" in sent and "Intensity" not in sent)
Mock.reply = "sure! here you go"; act, note = ab.interpret("stack all XRD files with vertical offset", [], "ollama", cfg)
check("ollama invalid JSON falls back to parser", act and act["action"] == "stack_xrd")
Mock.reply = '{"action": "delete_everything", "params": {}}'; act, _ = ab.interpret("plot calorimetry mass 1 g", [], "ollama", cfg)
check("ollama unknown action falls back", act and act["action"] == "plot_calorimetry")
act, _ = ab.interpret("plot calorimetry mass 1 g", [], "ollama", {"ollama": {"address": "http://127.0.0.1:9", "model": "m"}})
check("ollama not running falls back", act and act["action"] == "plot_calorimetry")
act, msg = ab.interpret("hello", [], "parser"); check("no backend works", act is None and "Try, for example" in msg)
check("cli missing falls back", ab.interpret("stack all XRD files with vertical offset", [], "cli", {"cli": {"program": "nonexistent"}})[0]["action"] == "stack_xrd")

# keys
os.environ.pop(sec.ENV, None); os.environ["APPDATA"] = tempfile.mkdtemp()
check("key not set", sec.status() == "not set")
os.environ[sec.ENV] = "sk-ant-api03-" + "A" * 40; check("key set via env", sec.status() == "set")
check("badly shaped key invalid", sec.status("hello") == "invalid")
check("redaction", "AAAAAAAA" not in sec.redact("error with " + os.environ[sec.ENV]) and "sk-...****" in sec.redact("x sk-ant-api03-" + "A" * 40))
check("api backend without key", (os.environ.pop(sec.ENV), raises(ab.api_key, "x", []))[1])
check("test_connection without key", ab.test_connection()[0] is False)
check("system check never raises", len(system_check.run()) >= 8 and "Python" in system_check.text())
check("help lists every action", all(n in aa.action_list_text() for n in aa.ACTIONS))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

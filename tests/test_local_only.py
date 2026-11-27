"""Local-only mode for the Assistant and the free web search: nothing is contacted, and the app still plots and analyses.

The checks are made where a request would leave, not where a control is shown:
  - the panel (workspace_assistant) refuses before anything is built for a request,
  - the transports (assistant._http for the AI, web_free._get / net.fetch for the web search) refuse again,
  - under both sits a recorder on urllib and on the sockets: it must stay empty for the whole local-only part.
A made-up AI key is set (an environment variable, as a user may have one), so an automatic link WOULD be tried if the mode did not
stop it. Then the two channel switches (web search off / AI off) and the start of the app are checked the same way.
What this does not prove: other windows and features outside these files (the update check and the classic window have their own tests).

Run: python tests/test_local_only.py"""
import json, math, os, socket, sys, tempfile, time, urllib.parse, urllib.request
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix="ops_local_only_"))
os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private"); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json")
os.environ["OPS_NO_OPEN"] = "1"; os.environ["QT_QPA_PLATFORM"] = "offscreen"; os.environ.setdefault("MPLBACKEND", "Agg")
os.environ["ORIGIN_PLOT_APP_HOME"] = str(TMP / "store"); os.environ["OPS_ASSISTANT_SYNC"] = "1"; os.environ["OPS_PROFILE"] = "owner"
for v in ("OPS_LOCAL_ONLY", "OPENAI_API_KEY", "GEMINI_API_KEY", "MOONSHOT_API_KEY"): os.environ.pop(v, None)
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-000000000000-not-a-real-key"       # made up: with it the panel has an AI it could link to
ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "origin_plot_app"; sys.path.insert(0, str(A))

# ---------------------------------------------------------------- the recorders under every transport
NET, HTTP = [], []
def _no_connect(self, addr, *a_, **k_):
    NET.append(addr); raise OSError("this test contacts no service")
socket.socket.connect = _no_connect; socket.socket.connect_ex = _no_connect
def _no_create(addr, *a_, **k_):
    NET.append(addr); raise OSError("this test contacts no service")
socket.create_connection = _no_create
def _no_open(self, req, *a_, **k_):
    HTTP.append(getattr(req, "full_url", str(req))); raise OSError("this test contacts no service")
urllib.request.OpenerDirector.open = _no_open

from PySide6.QtWidgets import QApplication
import outbound_policy as OP
OP.set_level("local_only")                            # chosen BEFORE the window exists: the app starts in local-only mode
import workspace_qt as W
import workspace_assistant as WA
import assistant as ai
import smart_plots as sp
import web_free as WF
import net

ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info and not cond else ""))
app = QApplication.instance() or QApplication(sys.argv)
def wait(c, t=120):
    t0 = time.time()
    while not c() and time.time() - t0 < t: app.processEvents(); time.sleep(0.02)
    app.processEvents(); return c()
MODELS, CHATS = [], []
real_models, real_chat, real_chat_web = ai.models, ai.chat, ai.chat_web
def models_recorded(conn):
    MODELS.append(conn.get("base")); return ["test-model"]
ai.models = models_recorded                           # 'link to the AI' = ask it for its models: recorded, never sent
def chat_recorded(*a_, **k_):
    CHATS.append("chat"); return real_chat(*a_, **k_)
def chat_web_recorded(*a_, **k_):
    CHATS.append("chat_web"); return real_chat_web(*a_, **k_)
ai.chat, ai.chat_web = chat_recorded, chat_web_recorded       # the real functions run underneath: the real transport must refuse too
def quiet(): return not NET and not HTTP

# ---------------------------------------------------------------- made-up data
D = TMP / "data"; D.mkdir()
rows = ["2theta (deg),Intensity (counts)"]
for i in range(400):
    x = 10 + i * 0.1
    rows.append(f"{x:.2f},{271.828 + 31065.5962 * math.exp(-((x - 29.4) / 0.15) ** 2) + 9000 * math.exp(-((x - 32.2) / 0.15) ** 2):.4f}")
(D / "synthetic_pattern.csv").write_text("\n".join(rows), encoding="utf-8")
DOC = TMP / "notes.md"; DOC.write_text("made-up notes for the test", encoding="utf-8")

# ================================================================ the app starts in local-only mode
W.save_cfg({"assistant_open": True})                  # the assistant was open when the app was closed: it is shown at once
w = W.Workspace([str(D / "synthetic_pattern.csv")]); w.resize(1400, 900); w.show()
wait(lambda: w.thread is None and w.list.count() >= 1)
a = w.assistant; app.processEvents()
check("start in local-only mode with an AI key present and the assistant open: no link is tried, nothing is contacted",
      a.isVisible() and a.prov.currentData() == "anthropic" and a.conn is None and not MODELS and quiet(), (a.prov.currentData(), MODELS, NET, HTTP))
check("the panel says so: the state line, the line under the chat and the selector", "Local-only" in a.state.text() and "Nothing is sent" in a.note.text() and a.privacy.currentData() == "local_only", (a.state.text(), a.note.text()))

# ---------------------------------------------------------------- local work goes on
it = w.singles[0]
check("local-only: the file is read and recognised (an XRD pattern)", it.kind == "XRD" and len(w.items) == 1, it.kind)
from matplotlib.figure import Figure
fig = Figure(figsize=(6, 4)); sp.preview_figure(it.spec, fig=fig)
check("local-only: the graph is drawn (preview with the measured curve)", fig.axes and any(len(l_.get_xdata()) >= 300 for ax in fig.axes for l_ in ax.get_lines()), [len(ax.get_lines()) for ax in fig.axes])
w.list.setCurrentRow(0); app.processEvents()
check("local-only: the Workspace shows it", w.current() is it and w.canvas.isVisible())
look = w.do_action({"do": "look", "graph": 1})
check("local-only: the app's own look at the data works on this computer (ranges, results)", "31337.4" in look and "synthetic_pattern.csv" in look, look[:200])
OUT = TMP / "results"; w.outdir.setText(str(OUT)); w.dated.setChecked(False)
r = w.do_action({"do": "analysis", "tool": "Find peaks", "graphs": [1]})
check("local-only: an analysis runs and its files are written", r.startswith("done") and "29.4" in r and any(p.suffix == ".csv" for p in (OUT / "Analysis").glob("*")), r[:200])
check("... and none of that contacted anything", quiet(), (NET, HTTP))

# ---------------------------------------------------------------- the Assistant: blocked in the panel
CLAUDE = {"provider": "anthropic", "base": "https://api.anthropic.com", "key": os.environ["ANTHROPIC_API_KEY"], "name": "Claude (Anthropic)"}
r = a.send("What is in my graph?"); app.processEvents()
check("local-only, no link: a message to the AI is not sent, and the chat says plainly why", r == "blocked" and "Local-only mode is on" in a.view.toPlainText() and "Nothing was sent" in a.view.toPlainText() and not CHATS and quiet(), (r, CHATS))
a.conn = dict(CLAUDE); a.model.setEnabled(True); a.model.clear(); a.model.addItem("test-model")       # as if it had been linked before the mode was switched on
a.attach([str(DOC)])
r = a.send("What is in my graph?"); app.processEvents()
check("local-only, AI linked earlier: the message is not sent either (nothing is built, the stored conversation stays empty)", r == "blocked" and a.hist == [] and not CHATS and quiet(), (r, a.hist, CHATS))
check("... the attached document stays here and is marked as not sent", len(a.attached) == 1 and "NOT sent" in a.attbar.text(), a.attbar.text())
a.pending, a.more = [{"do": "look", "graph": 1}], True; a.run_pending(); app.processEvents()
check("local-only: a reading step still runs on this computer, but its result does not go back to an AI", "were not sent back" in a.view.toPlainText() and a.hist == [] and not CHATS and quiet())
u = a.ask_browser("ChatGPT", "explain my pattern")
check("local-only: 'Ask in browser' does not put the question into an address", u == "" and "was not opened" in a.view.toPlainText())
a.conn = None
a.reload(); app.processEvents()
check("local-only: 'link again' (a saved key, the provider chosen) asks no service for its models", not MODELS and a.conn is None and quiet(), MODELS)
r = a.send("show graph 1"); app.processEvents()
check("local-only: the app's own commands in the chat still work ('show graph 1')", r == "command" and "ops_chat_graph_" in a.view.toHtml())

# ---------------------------------------------------------------- the Assistant: blocked at the transport
for name, fn in (("assistant.chat", lambda: real_chat(dict(CLAUDE), "test-model", "system", [{"role": "user", "content": "hello"}])),
                 ("assistant.chat_web", lambda: real_chat_web(dict(CLAUDE), "test-model", "system", [{"role": "user", "content": "hello"}])),
                 ("assistant.models", lambda: real_models(dict(CLAUDE))),
                 ("assistant._http", lambda: ai._http("POST", "https://api.anthropic.com/v1/messages", {}, {"x": 1}))):
    try: fn(); r = "sent"
    except PermissionError as e: r = "refused: " + str(e)
    except Exception as e: r = f"other error: {type(e).__name__}: {e}"
    check(f"local-only: {name} refuses at the transport, before a connection is opened", r.startswith("refused") and "Local-only" in r and quiet(), (r, NET, HTTP))

# ---------------------------------------------------------------- the free web search: blocked in the panel and at the transport
a.prov.setCurrentIndex(a.prov.findData("none")); a.connect_ai()
r = a.send("what is alite hydration?"); app.processEvents()
check("local-only, free web search chosen: nothing is searched, and the chat says plainly why", r == "blocked" and a.view.toPlainText().count("Local-only mode is on") >= 2 and quiet(), r)
r = a.free_search("alite hydration")
check("local-only: free_search() itself refuses", r == "blocked" and quiet())
for name, fn in (("web_free.search", lambda: WF.search("alite hydration")), ("web_free.papers", lambda: WF.papers("alite")), ("web_free.papers_s2", lambda: WF.papers_s2("alite")),
                 ("web_free.papers_crossref", lambda: WF.papers_crossref("alite")), ("web_free.papers_arxiv", lambda: WF.papers_arxiv("alite")), ("web_free.pages", lambda: WF.pages("alite")),
                 ("web_free.pictures", lambda: WF.pictures("alite", 2, str(TMP))), ("web_free.details", lambda: WF.details({"kind": "paper", "doi": "10.1/abc", "abstract": ""})),
                 ("web_free._get", lambda: WF._get("https://api.openalex.org/works?search=alite")), ("web_free._get_json", lambda: WF._get_json("https://api.crossref.org/works?query=alite")),
                 ("net.fetch (channel web_search)", lambda: net.fetch("https://api.openalex.org/works?search=alite", WF.HEADERS, 5, channel="web_search"))):
    try: fn(); r = "sent"
    except OP.Blocked as e: r = "refused: " + str(e)
    except PermissionError as e: r = "refused: " + str(e)
    except Exception as e: r = f"other error: {type(e).__name__}: {e}"
    check(f"local-only: {name} refuses before a connection is opened", r.startswith("refused") and "Local-only" in r and quiet(), (r, NET, HTTP))
check("local-only: the policy let no request through (its list of admitted requests is empty)", OP.audit() == [], OP.audit()[:3])
check("the whole local-only part: no socket was opened, no HTTP request was made, no AI function was called", quiet() and not MODELS and not CHATS, (NET, HTTP, MODELS, CHATS))

# ================================================================ leaving local-only is your choice; then the two switches
PAY, WEB = [], []
def fake_http(method, url, headers=None, body=None, timeout=180, **kw):
    PAY.append({"url": url, "body": body, "json": json.dumps(body, ensure_ascii=False) if body is not None else ""})
    return {"content": [{"type": "text", "text": json.dumps({"say": "Hello.", "actions": [], "done": True})}], "stop_reason": "end_turn"}
def fake_fetch(url, headers=None, timeout=60, **kw):
    WEB.append(url)
    if "api.openalex.org/works" in url:
        return json.dumps({"results": [{"title": "Hydration of alite", "doi": "https://doi.org/10.1/abc", "publication_year": 2011, "primary_location": {"source": {"display_name": "J"}},
                                        "authorships": [], "abstract_inverted_index": {"Alite": [0], "hydration": [1]}}]}).encode()
    raise OSError("not reachable in the test")
ai._http = fake_http; net.fetch = fake_fetch
ai.chat, ai.chat_web = real_chat, real_chat_web
a.prov.setCurrentIndex(a.prov.findData("anthropic")); a.connect_ai(); app.processEvents()
check("still local-only: choosing the AI in the list links nothing", a.conn is None and not MODELS and "Local-only" in a.state.text())
i_ = a.privacy.findData("minimal"); a.privacy.setCurrentIndex(i_); a.privacy.activated.emit(i_)
wait(lambda: a.conn is not None, 20)
check("you choose 'Minimal' in the panel: now the AI you set up is linked (once), and the panel names its host",
      OP.level() == "minimal" and a.conn is not None and MODELS == ["https://api.anthropic.com"] and "api.anthropic.com" in a.state.text() and "api.anthropic.com" in a.note.text(), (MODELS, a.state.text()))
a.model.setCurrentText("test-model")
r = a.send("Hello there."); app.processEvents()
check("'Minimal': a message goes to the AI service (recorded, not sent)", r == "sent" and len(PAY) == 1 and "api.anthropic.com" in PAY[0]["url"], (r, len(PAY)))
# the web search switched off, the AI on
OP.set_channel("web_search", False); PAY.clear(); WEB.clear()
a.web.setChecked(True); r = a.send("How does alite hydrate?"); app.processEvents(); a.web.setChecked(False)
check("web search switched off: the AI still answers, without the web (no search tool in the request, nothing fetched), and the chat says so",
      r == "sent" and len(PAY) == 1 and "tools" not in PAY[0]["body"] and not WEB and "answers without the web" in a.view.toPlainText(), (r, len(PAY), WEB))
try: WF.search("alite hydration"); r = "sent"
except OP.Blocked as e: r = "refused: " + str(e)
check("web search switched off: web_free refuses with a plain reason", r.startswith("refused") and "switched off" in r and not WEB, r)
keep = a.conn; a.conn = None; a.prov.setCurrentIndex(a.prov.findData("none")); r = a.send("what is alite hydration?"); app.processEvents()
check("web search switched off: the free search in the chat is not started", r == "blocked" and not WEB and "switched off" in a.view.toPlainText(), r)
# the AI switched off, the web search on
OP.set_channel("web_search", True); OP.set_channel("ai", False); PAY.clear(); WEB.clear()
r = a.send("what is alite hydration?"); app.processEvents()
check("AI switched off, web search on: the free search works (recorded) and sends only the search words", r == "searching" and WEB and "alite+hydration" in WEB[0] and not PAY and "Hydration of alite" in a.view.toPlainText(), (r, WEB[:1]))
a.conn = keep; a.prov.setCurrentIndex(a.prov.findData("anthropic")); r = a.send("Hello again."); app.processEvents()
check("AI switched off: a message to the AI is not sent, and the chat says the AI is switched off", r == "blocked" and not PAY and "switched off" in a.view.toPlainText().split("Hydration of alite")[-1], r)
a.conn = None; n_models = len(MODELS); a.connect_ai(); app.processEvents()
check("AI switched off: no link is tried", a.conn is None and len(MODELS) == n_models and "switched off" in a.state.text(), a.state.text())
OP.set_channel("ai", True)

# ================================================================ the start of the app at a connected level
W.save_cfg({"assistant_open": False}); n_models = len(MODELS); PAY.clear(); WEB.clear()
w2 = W.Workspace([]); w2.resize(1200, 800); w2.show(); app.processEvents(); time.sleep(0.2); app.processEvents()
check("start at 'Minimal' with the assistant closed: the app links to no AI and searches nothing by itself", w2.assistant.conn is None and len(MODELS) == n_models and not PAY and not WEB, (MODELS, PAY, WEB))
w2.show_assistant(True); wait(lambda: w2.assistant.conn is not None, 20)
check("... the AI is linked when you open the assistant (once)", w2.assistant.conn is not None and len(MODELS) == n_models + 1, MODELS)
w2.show_assistant(False); w2.show_assistant(True); app.processEvents()
check("... and not again each time the panel is shown", len(MODELS) == n_models + 1, MODELS)
OP.set_level("local_only"); app.processEvents()
r = w2.assistant.send("Hello."); r1 = a.send("Hello.")
check("local-only switched on while the app runs: every open window stops sending at once", r == "blocked" and r1 == "blocked" and not PAY and w2.assistant.privacy.currentData() == "local_only" and a.privacy.currentData() == "local_only", (r, r1, len(PAY)))
check("no part of this test opened a network connection", quiet(), (NET, HTTP))
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

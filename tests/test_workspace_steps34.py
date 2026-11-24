"""The modern window, steps 3 and 4: Analysis and Graph gallery run their tools; the assistant panel; Settings. Without a screen.
Run: python tests/test_workspace_steps34.py [screenshot_prefix]"""
import json, math, os, re, sys, tempfile, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TMP = Path(tempfile.mkdtemp(prefix="ws_step34_"))
os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_NO_OPEN"] = "1"
os.environ["ORIGIN_PLOT_APP_HOME"] = str(TMP / "store")                  # the assistant's files go to TMP, not to the user's folder
for v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "MOONSHOT_API_KEY"): os.environ.pop(v, None)
ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "origin_plot_app"; sys.path.insert(0, str(A))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import workspace_qt as W
import assistant as ai
import smart_plots as sp
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
app = QApplication.instance() or QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(W.STYLE)
def wait(c, t=180):
    t0 = time.time()
    while not c() and time.time() - t0 < t: app.processEvents(); time.sleep(0.02)
    app.processEvents(); return c()
E = A / "examples_synthetic"
files = [str(E / f) for f in ("xrd_raw.csv", "TGA_Ref_28d_rep1.txt", "TGA_Ref_28d_rep2.txt", "tga.xlsx")]
w = W.Workspace(files); w.resize(1500, 920); w.show()
wait(lambda: w.thread is None and w.list.count() > 0)
OUT = TMP / "results"; w.outdir.setText(str(OUT)); w.dated.setChecked(False)
def idx(pred): return next(i for i, it in enumerate(w.items) if pred(it))
def tick_only(*rows):
    for i in range(w.list.count()): w.list.item(i).setCheckState(Qt.Checked if i in rows else Qt.Unchecked)
def job(): return wait(lambda: w.job_thread is None, 300)

# ---------------------------------------------------------------- step 3: Analysis
pa = w.pages.widget(1); pt = w.pages.widget(2)
check("side bar: Workspace, Analysis, Assistant, Settings", [b.text() for b in w.navgroup.buttons()] == ["Workspace", "Analysis", "Assistant", "Settings"])
i_x = idx(lambda it: "xrd_raw" in str(getattr(it, "path", ""))); tick_only(i_x); w.list.setCurrentRow(i_x); app.processEvents()
n0 = len(w.singles)
pa.tree.setCurrentItem(pa.find_entry("Savitzky-Golay")); app.processEvents()
check("a tool shows its settings form", set(pa.fields) == {"window", "order"} and pa.fields["window"].text() == "11", list(pa.fields))
pa.fields["window"].setText("15"); pa.buttons.itemAt(0).widget().click(); job(); wait(lambda: w.thread is None and len(w.singles) > n0)
af = sorted(p.name for p in (OUT / "Analysis").glob("*"))
check("Run: the smoothed curve is saved (CSV + provenance) and added to Your graphs, as in the current window",
      any(f.endswith("Savitzky-Golay.csv") for f in af) and any(f.endswith("_provenance.json") for f in af) and len(w.singles) == n0 + 1, af)
prov = json.load(open(next((OUT / "Analysis").glob("*Savitzky-Golay_provenance.json")), encoding="utf-8"))
check("the provenance holds the settings you set and the input file's hash", str(prov["settings"]["window"]) == "15" and len(prov["inputs"][0]["sha256"]) == 64, prov["settings"])
import analysis_tools as at, origin_plot_app as opa
i_x = idx(lambda it: isinstance(it, sp.Item) and "xrd_raw" in str(getattr(it, "path", "")))
c = w.tools.curves([w.items[i_x]])[0]
ref = at.run("Savitzky-Golay", [c], window=15)[0][1].curves[0][2]
import pandas as pd
got = pd.read_csv(next((OUT / "Analysis").glob("*Savitzky-Golay.csv")), encoding="utf-8-sig").iloc[:, 1].to_numpy()
check("the numbers are analysis_tools' own (same as Analysis > Smoothing in the current window)", len(ref) == len(got) and abs(ref - got).max() < 1e-9)
w.list.setCurrentRow(i_x); tick_only(i_x); app.processEvents()
pa.tree.setCurrentItem(pa.find_entry("Find peaks")); app.processEvents(); pa.buttons.itemAt(0).widget().click(); job()
check("Find peaks: the result table is shown on the page", not pa.restable.isHidden() and pa.resmodel.rowCount() >= 3 and "Done" in pa.msg.text(), (pa.resmodel.rowCount(), pa.msg.text()[:90]))
w.on_span(29.0, 29.8); pa.tree.setCurrentItem(pa.find_entry("Area between")); app.processEvents()
check("a range selected on the graph fills From x / To x", pa.fields["x_from"].text() == "29.0" and pa.fields["x_to"].text() == "29.8", (pa.fields["x_from"].text(), pa.fields["x_to"].text()))
w.clear_selection()
tick_only(); w.list.setCurrentRow(-1); pa.tree.setCurrentItem(pa.find_entry("Moving average")); app.processEvents(); r = w.tools.run_tool("Moving average", {}, pa, sync=True)
check("nothing ticked or shown: a plain message, nothing written", isinstance(r, tuple) and r[0] == "error" and "Tick" in pa.msg.text())
# TGA
pa.tree.setCurrentItem(pa.find_entry("Mass loss in temperature")); app.processEvents(); df = w.tools.tga_steps(pa)
check("TGA mass loss in intervals: table with total and residue, CSV saved", hasattr(df, "columns") and "residue" in set(df["from (°C)"].astype(str)) and (OUT / "TGA_steps" / "TGA_mass_loss_intervals.csv").exists(), None if not hasattr(df, "shape") else df.shape)
i_t = idx(lambda it: it.kind == "TGA" and str(getattr(it, "path", "")).endswith("rep1.txt"))
refr = sp.analyze_tga_steps(w.items[i_t], None, w.opt)["total_mass_loss_pct"]
check("the same numbers as smart_plots.analyze_tga_steps", any(abs(float(v) - refr) < 1e-9 for v in df["mass loss (%)"]), refr)
# Calorimetry
import openpyxl
cw = TMP / "CEM_ref.xlsx"; wb = openpyxl.Workbook(); ws_ = wb.active; ws_.append(["Time", "Heat flow", "Marker"]); ws_.append(["s", "W", None])
for i in range(12): ws_.append([i * 60 - 720, 2e-4 * math.exp(-i / 3), None])
for i in range(48 * 60):
    t = i * 60.0; h = t / 3600.0
    ws_.append([t, 0.5e-3 * (1.6 * math.exp(-((h - 9) / 4.0) ** 2) + 0.3 * math.exp(-h / 2.0) + 0.05), "Reaction start" if i == 0 else None])
wb.save(cw)
pa.tree.setCurrentItem(pa.find_entry("Calorimetry (TAM III)")); app.processEvents()
pa.calo_add(str(cw)); r = w.tools.calorimetry(pa, wait=True)
check("Calorimetry without a mass: nothing processed, it asks for the mass", isinstance(r, tuple) and "mass" in pa.msg.text(), pa.msg.text()[:80])
t = pa.calo_table; row = t.rowCount() - 1; t.item(row, 1).setText("0.5"); r = w.tools.calorimetry(pa, wait=True)
cf = sorted(p.name for p in (OUT / "Calorimetry").rglob("*"))
check("Calorimetry processed with calorimetry.run: total J/g shown, figures and workbook written", r and pa.resmodel.rowCount() == 1 and any(f.endswith(".png") for f in cf) and any(f.endswith(".xlsx") for f in cf), cf[:6])
# Graph gallery
TPL = ROOT / "tests" / "gallery_templates"
w.load_sync([str(TPL / "G07_TG_DTG.xlsx")])
i_g = idx(lambda it: "G07_TG_DTG" in str(getattr(it, "path", ""))); tick_only(i_g)
pt.tree.setCurrentItem(pt.find_entry("G07")); app.processEvents()
r = w.tools.figtype_draw("G07", pt)
it_g = next(it for it in w.singles if "G07_TG_DTG" in str(getattr(it, "path", "")))
check("Graph gallery: the ticked workbook drawn as G07 and shown", sp.figtype_id(it_g.kind) == "G07" and it_g.spec is not None and "G07" in pt.msg.text(), (it_g.kind, pt.msg.text()[:80]))
n1 = len(w.singles)
p = w.tools.figtype_template("G07", pt, raw=str(E / "tga.xlsx"), out=str(TMP / "tga_G07_template.xlsx"))
wait(lambda: w.thread is None and len(w.singles) > n1)
check("Make a template from a raw file: written with gallery_graphs.make_template and added to Your graphs", Path(str(p)).exists() and len(w.singles) > n1, p)
check("Graph gallery holds all 26 types", sum(pt.tree.topLevelItem(i).childCount() for i in range(pt.tree.topLevelItemCount())) >= 26)

# ---------------------------------------------------------------- step 4: Settings
ps = w.pages.widget(4)
w.set_fields["tga_ranges"].setText("50-200, 400-500"); n = w.apply_settings()
check("Apply: analysis settings saved and every graph redrawn with them", n == len(w.singles) and w.opt.get("tga_ranges") == "50-200, 400-500" and json.load(open(TMP / "settings_modern.json"))["tga_ranges"] == "50-200, 400-500", n)
check("settings.json of the current window is not touched", not (A / "settings.json").exists() or "start_window" not in json.load(open(A / "settings.json", encoding="utf-8")))
# the AI: a key is saved encrypted the way the current window saves it (here: no Windows, stored as plain in the test folder)
real_models, real_http, real_chat = ai.models, ai._http, ai.chat
ai.models = lambda conn: ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
w.ai_choice.setCurrentIndex(0); w.ai_key.setText("sk-ant-test-0000"); r = w.ai_save_key()
st = ai.load_settings(w.assistant.home)
check("Settings > AI: the key is recognised (Claude) and saved with the current window's code", r == "linked" and "anthropic" in (st.get("keys") or {}) and w.ai_key.text() == "", w.ai_msg.text())
wait(lambda: w.assistant.conn is not None, 20)
check("the assistant links by itself and lists every model of the key", w.assistant.conn and w.assistant.model.count() == 3 and w.assistant.web.isEnabled(), w.assistant.state.text())
w.assistant.model.setCurrentText("claude-sonnet-5-5"); w.assistant.save_model()
check("the model can be changed at any time and is remembered", ai.load_settings(w.assistant.home)["models"]["anthropic"] == "claude-sonnet-5-5")

# ---------------------------------------------------------------- step 4: the assistant panel
w.show_assistant(True); app.processEvents()
check("the assistant is a panel beside the work (dockable, floatable) and the top button shows it", w.dock.isVisible() and w.ai_btn.isChecked() and bool(w.dock.features() & w.dock.DockWidgetFeature.DockWidgetFloatable))
os.environ["OPS_ASSISTANT_SYNC"] = "1"
seen = {}
i_x = idx(lambda it: isinstance(it, sp.Item) and "xrd_raw" in str(getattr(it, "path", "")))
def fake_chat(conn, model, system, messages, timeout=180):
    seen["system"], seen["msgs"], seen["model"] = system, messages, model
    if "RESULTS" in messages[-1]["content"]:
        return json.dumps({"say": "Done: the peaks are in the table.", "actions": [], "done": True})
    return json.dumps({"say": "I will find the peaks of the XRD pattern.", "actions": [{"do": "analysis", "tool": "Find peaks", "graphs": [i_x + 1]}], "done": False})
ai.chat = fake_chat
w.assistant.input.setPlainText("find the peaks of the xrd pattern"); w.assistant.send(); app.processEvents()
st_ = json.loads(seen["msgs"][-1]["content"].split("STATE: ", 1)[1])
check("the AI gets the list of graphs (names, kinds, ticks), not the tables", st_["graphs"][i_x]["kind"] in ("XRD", "XY") and set(st_["graphs"][i_x]) <= {"n", "name", "kind", "file", "sample", "combined", "ticked"}, st_["graphs"][i_x])
check("the system prompt lists this window's actions, the 44 tools and the gallery types, and the user's instructions", "MODERN" not in seen["system"] and '"analysis"' in seen["system"] and "Savitzky-Golay" in seen["system"] and "G24" in seen["system"] and "THE USER'S OWN INSTRUCTIONS" in seen["system"])
check("the chosen model is used", seen["model"] == "claude-sonnet-5-5")
check("an action waits for you: Do it / Don't", w.assistant.card.isVisible() and "Find peaks" in w.assistant.cardtext.text())
pf_ = next((OUT / "Analysis").glob("*Find_peaks_provenance.json")); t0_ = pf_.stat().st_mtime_ns; time.sleep(0.05)
w.assistant.doit.click(); app.processEvents()
txt = w.assistant.view.toPlainText()
check("Do it runs the tool through the same code, sends the RESULTS back, and the AI finishes", pf_.stat().st_mtime_ns > t0_ and "Position" in txt and "Done: the peaks are in the table." in txt and "RESULTS" in seen["msgs"][-1]["content"], txt[-200:])
def fake_chat2(conn, model, system, messages, timeout=180):
    return json.dumps({"say": "Naming them.", "actions": [{"do": "sample", "graphs": [i_x + 1], "name": "Ref"}], "done": True})
ai.chat = fake_chat2; w.assistant.send("name the xrd Ref"); app.processEvents(); w.assistant.dont.click(); app.processEvents()
check("Don't: nothing is done", all(getattr(s, "sample", "") != "Ref" for s in w.singles) and "Not done." in w.assistant.view.toPlainText())
ai.chat = lambda *a_, **k_: json.dumps({"say": "x", "actions": [{"do": "delete_everything"}], "done": True})
w.assistant.send("do something else"); w.assistant.doit.click(); app.processEvents()
check("an action that is not in the list is refused", "is not an action of this window" in w.assistant.view.toPlainText())
# web search: the request carries the search tool, a pause is continued, and the pages are listed
calls = []
def fake_http(method, url, headers, body=None, timeout=180):
    calls.append((url, body))
    if len(calls) == 1:
        return {"content": [{"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {"query": "C3S hydration"}}], "stop_reason": "pause_turn"}
    return {"content": [{"type": "text", "text": json.dumps({"say": "Alite hydrates in stages; see the review.", "actions": [], "done": True}),
                         "citations": [{"type": "web_search_result_location", "url": "https://example.org/review", "title": "A review of alite hydration", "cited_text": "..."}]}],
            "stop_reason": "end_turn"}
ai._http = fake_http; ai.chat = real_chat
w.assistant.web.setChecked(True); w.assistant.send("how does alite hydrate?"); app.processEvents()
check("Search the web (Claude): the web search tool is sent, a paused search is continued", calls and calls[0][1]["tools"][0]["name"] == "web_search" and calls[0][1]["tools"][0]["type"] == "web_search_20260209" and len(calls) == 2 and calls[1][1]["messages"][-1]["role"] == "assistant", [c[1]["tools"][0]["type"] for c in calls])
check("the answer lists the pages it used, as links", "A review of alite hydration" in w.assistant.view.toPlainText() and "https://example.org/review" in w.assistant.view.toHtml())
# the other services
def one(conn, reply):
    ai._http = lambda m, u, h, b=None, timeout=180: (calls.append((u, b)) or reply)
    return ai.chat_web(conn, "m", "sys", [{"role": "user", "content": "q"}])
calls.clear(); t_, s_ = one({"provider": "openai", "base": "https://api.openai.com/v1", "key": "k", "name": "ChatGPT"},
             {"output": [{"type": "message", "content": [{"type": "output_text", "text": "ok", "annotations": [{"type": "url_citation", "url": "https://a.org", "title": "A"}]}]}]})
check("ChatGPT: Responses API with web_search, pages listed", calls[0][0].endswith("/responses") and calls[0][1]["tools"] == [{"type": "web_search"}] and s_ == [("A", "https://a.org")])
calls.clear(); t_, s_ = one({"provider": "gemini", "base": "https://generativelanguage.googleapis.com/v1beta", "key": "k", "name": "Gemini"},
             {"candidates": [{"content": {"parts": [{"text": "ok"}]}, "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://g.org", "title": "G"}}]}}]})
check("Gemini: Google Search grounding, pages listed", calls[0][1]["tools"] == [{"google_search": {}}] and s_ == [("G", "https://g.org")])
calls.clear(); t_, s_ = one({"provider": "other", "base": "https://openrouter.ai/api/v1", "key": "k", "name": "openrouter.ai"},
             {"choices": [{"message": {"content": "ok", "annotations": [{"type": "url_citation", "url_citation": {"url": "https://o.org", "title": "O"}}]}}]})
check("OpenRouter (any model): ':online', pages listed", calls[0][1]["model"] == "m:online" and s_ == [("O", "https://o.org")])
try: ai.chat_web({"provider": "ollama", "base": "http://localhost:11434/v1", "key": "", "name": "Ollama"}, "m", "s", []); r = "no error"
except ai.AIError as e: r = str(e)
check("a local model cannot search the web: a plain message, nothing sent", "cannot search the web" in r, r)
ai._http, ai.models = real_http, real_models

# ---------------------------------------------------------------- 5.34: web search without a key, files from every page
import web_free
FAKE = {"api.semanticscholar.org": {"data": [{"title": "Hydration of alite", "externalIds": {"DOI": "10.1/abc"}, "year": 2011},
          {"title": "Alite reactivity", "externalIds": {"DOI": "10.2/xyz"}, "year": 2019, "venue": "CCR", "authors": [{"name": "B. Author"}], "abstract": "Reactivity of alite"}]},
        "api.openalex.org": {"results": [{"title": "Hydration of alite", "doi": "https://doi.org/10.1/abc", "publication_year": 2011,
          "primary_location": {"source": {"display_name": "Cem. Concr. Res."}}, "authorships": [{"author": {"display_name": "A. Author"}}],
          "abstract_inverted_index": {"Alite": [0], "hydrates": [1], "fast": [2]}, "cited_by_count": 10}]},
        "api.crossref.org": {"message": {"items": [{"DOI": "10.3/crs", "title": ["Crossref paper on alite"], "author": [{"given": "Carl", "family": "Ross"}],
          "issued": {"date-parts": [[2020]]}, "container-title": ["J. Am. Ceram. Soc."], "is-referenced-by-count": 7, "type": "journal-article"}]}},
        "en.wikipedia.org": {"pages": [{"title": "Alite", "key": "Alite", "excerpt": "<span>Alite</span> is tricalcium silicate", "description": "mineral"}]}}
asked = []
def fake_json(url, timeout=25):
    asked.append(url)
    hit = next((FAKE[k] for k in sorted(FAKE, key=len, reverse=True) if k in url), None)      # the most specific address first
    if hit is None:
        raise web_free.SearchError(url.split("/")[2] + ": not reachable in the test")
    return hit
ARXIV_XML = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2101.00001</id><title>Alite dissolution by simulation</title>
<summary>We simulate alite dissolution.</summary><published>2021-01-01T00:00:00Z</published><author><name>D. Sim</name></author>
<link title="pdf" href="http://arxiv.org/pdf/2101.00001"/></entry></feed>"""
def fake_get(url, timeout=25):
    asked.append(url)
    if "arxiv" in url:
        return ARXIV_XML
    raise web_free.SearchError("not in the test")
web_free._get_json = fake_json; web_free._get = fake_get
res, probs = web_free.search("what is alite hydration?")
urls = [r["url"] for r in res]
check("free web search, academic first: OpenAlex, Semantic Scholar, Crossref, arXiv (each paper once); no Wikipedia when papers are found",
      all(r["kind"] == "paper" for r in res) and urls[0] == "https://doi.org/10.1/abc" and urls.count("https://doi.org/10.1/abc") == 1 and "https://doi.org/10.3/crs" in urls
      and "http://arxiv.org/abs/2101.00001" in urls and "https://doi.org/10.2/xyz" in urls and not any("wikipedia" in u for u in urls) and res[0]["text"].startswith("Alite hydrates fast"), urls)
ax_ = next(r for r in res if "arxiv" in r["url"])
check("each paper keeps authors, year, journal, abstract, free PDF and its source", ax_["oa_url"].endswith("2101.00001") and ax_["abstract"].startswith("We simulate") and ax_["source"] == "arXiv"
      and next(r for r in res if "crs" in r["url"])["authors"] == ["C. Ross"])
check("only the search words are sent", all("alite" in u.lower() and "STATE" not in u for u in asked), asked)
w.assistant.prov.setCurrentIndex(w.assistant.prov.findData("none")); w.assistant.connect_ai(); app.processEvents()
w.assistant.input.setPlainText("search the web for alite hydration"); w.assistant.send(); app.processEvents()
h = w.assistant.view.toHtml()
check("No AI: the question is searched for free and the papers are listed (preview, link), plus the same search in Google / Scholar", "Hydration of alite" in w.assistant.view.toPlainText() and "https://doi.org/10.1/abc" in h and "preview:" in h and "google.com/search?q=alite+hydration" in h and "scholar.google.com" in h, h[-600:])
seen2 = {}
def chat_plain(conn, model, system, messages, timeout=180):
    if system.startswith("You write web search queries"):
        return "tricalcium silicate hydration kinetics"
    seen2["msgs"] = messages; return json.dumps({"say": "Alite hydrates fast [1].", "actions": [], "done": True})
ai.chat = chat_plain
w.assistant.conn = {"provider": "ollama", "base": "http://localhost:11434/v1", "key": "", "name": "Local model (Ollama)"}
w.assistant.model.setEnabled(True); w.assistant.model.clear(); w.assistant.model.addItem("llama3.1")
w.assistant.web.setChecked(True); w.assistant.send("how does alite hydrate?"); app.processEvents()
check("a local model (no web of its own): the app searches and gives it the WEB RESULTS; the pages are listed",
      "WEB RESULTS" in seen2["msgs"][-1]["content"] and "Hydration of alite" in seen2["msgs"][-1]["content"] and "Alite hydrates fast [1]." in w.assistant.view.toPlainText()
      and "https://doi.org/10.1/abc" in w.assistant.view.toHtml())
check("the local model first writes a precise search query, and the app searches with it", any("tricalcium+silicate+hydration+kinetics" in a_ or "tricalcium%20silicate" in a_ for a_ in asked), asked[-3:])
u = w.assistant.ask_browser("ChatGPT", "explain the DTG peak at 450 °C")
check("Ask in your browser: the question goes to the site and to the clipboard", u.startswith("https://chatgpt.com/?q=explain") and QApplication.clipboard().text().startswith("explain the DTG peak"), u[:60])
ai.chat = real_chat
# files from every page come in ticked, and ticks stay
w.go(1); app.processEvents()
tick_only(); i_k = idx(lambda it: isinstance(it, sp.Item) and str(getattr(it, "path", "")).endswith("rep1.txt")); w.list.item(i_k).setCheckState(Qt.Checked)
n2 = len(w.singles); w.load([str(E / "ftir.xlsx")], tick=True); wait(lambda: w.thread is None and len(w.singles) > n2)
tk_ = [getattr(i, "path", "") for i in w.ticked()]
check("Add files on a tool page: the new file comes to Your graphs ticked; what was ticked stays ticked", any(str(p).endswith("ftir.xlsx") for p in tk_) and any(str(p).endswith("rep1.txt") for p in tk_), [os.path.basename(str(p)) for p in tk_])
check("the page says what a Run works on", "Works on 3 graph(s)" in pa.workson.text() and "FTIR" in pa.workson.text(), pa.workson.text())
check("the page lists the files it works on, with their columns", pa.inputs.rowCount() == 3 and all(pa.inputs.item(r, 2).text() for r in range(3)))
pa.steps[5].click(); app.processEvents()
check("Go to Workspace (step 6 of the workflow)", w.pages.currentIndex() == 0 and w.header_nav.button(0).isChecked())

# ---------------------------------------------------------------- 5.35: FTIR, automatic peak labels, your own groups
w.go(0); app.processEvents()
ftirs = [it for it in w.singles if it.kind == "FTIR"]
w._tick_only(ftirs); app.processEvents()
abs_ = next(it for it in ftirs if "Abs" in it.title)
w.tools.ftir_read("Transmittance", pa)
check("FTIR: read as transmittance for the ticked spectra (bands at the minima), noted on the graph", abs_.det.get("_ftir_signal") == "Transmittance" and any("transmittance" in str(r) and "your choice" in str(r) for r in abs_.record), abs_.record[-2:])
w.tools.ftir_read("Absorbance", pa)
check("FTIR: read as absorbance", abs_.det.get("_ftir_signal") == "Absorbance" and any("absorbance" in str(r) and "your choice" in str(r) for r in abs_.record))
w._tick_only([abs_])
df = w.tools.ftir_areas("1200-850 Si-O\n3700-3000", pa)
ca = w.tools.curves([abs_])[0]
ref = at.area_between(ca, x_from=850, x_to=1200, subtract_line=True).table.iloc[0]["Area"]
check("FTIR band areas: one row per region, the same numbers as Area between two x values (with the straight-line baseline)", len(df) == 2 and abs(df.iloc[0]["area (absorbance·cm-1)"] - ref) < 1e-9 and df.iloc[1]["region"] == "3700-3000" and (OUT / "FTIR" / "FTIR_band_areas.csv").exists(), df.to_dict("records"))
pa.tree.setCurrentItem(pa.find_entry("Band areas")); app.processEvents()
check("Analysis has an FTIR group (read as absorbance / transmittance, conversions, band areas)", sum(1 for i in range(pa.tree.topLevelItemCount()) if pa.tree.topLevelItem(i).text(0).startswith("FTIR")) == 1 and pa.find_entry("Read as transmittance") is not None and "regions" in pa.fields)
xi = next(it for it in w.singles if "xrd_raw" in str(getattr(it, "path", "")))
w._tick_only([xi]); r = w.tools.labels_auto({"n": 6, "prom": 5, "digits": 4}, pa)
nlab = sum(len(p.get("labels") or []) + len(p.get("code_labels") or []) for p in xi.spec["panels"])
check("Label peaks automatically: positions only, on the graph (and so in Origin and the files)", len(xi.det.get("_auto_labels") or []) == 6 and nlab >= 1 and all(re.fullmatch(r"[0-9.]+", t) for t in xi.det["_auto_labels"]), (xi.det.get("_auto_labels"), nlab, r[:120]))
w.tools.labels_clear(pa)
check("Remove the automatic labels: the graph is as before", "_auto_labels" not in xi.det and list(xi.given or []) == list(xi.det.get("_given_file", xi.given or [])))
tg_ = [it for it in w.singles if it.kind == "TGA" and str(getattr(it, "path", "")).endswith(".txt")]
w._tick_only(tg_); n_c = len(w.combined)
check("Stack ticked: your own group (◆) at the top", w.group_ticked("stack") == "grouped" and any(getattr(c, "mine", False) and c.how == "stack" for c in w.combined) and w.list.item(0).text().startswith("◆"), w.list.item(0).text())
w.groupmode.setCurrentText("Keep them separate"); w.regroup(); w.refresh_list()
check("Group list 'Keep them separate': no ★ combined figures, your ◆ group stays", all(getattr(c, "mine", False) for c in w.combined) and len(w.combined) == 1)
w.list.setCurrentRow(0); w._tick_only([]); check("Ungroup", w.ungroup() == "ungrouped" and not w.combined)
w.groupmode.setCurrentText("Decide for me"); w.regroup(); w.refresh_list()
check("the FTIR figures (stacked / overlaid) are in Analysis > FTIR, once (not repeated in the gallery)", pa.find_entry("FTIR spectra stacked") is not None and pt.find_entry("FTIR spectra stacked") is None)
r = w.tools.group("overlay", "FTIR", pt)
check("FTIR spectra overlaid from the Graph gallery page", r == "grouped" and any(getattr(c, "mine", False) and c.kind == "FTIR" and c.how == "overlay" for c in w.combined))
import re as _re

# ---------------------------------------------------------------- 5.36: thermodynamic modelling, files in the chat, a readable chat, panels
M = ROOT / "tests" / "modelling"
w.go(0); n3 = len(w.singles)
w.load_sync([str(M / f) for f in ("gems_hydration.csv", "equilib_table.csv", "thermocalc.csv", "phreeqc.sel", "gems_T.csv")])
mods = w.singles[n3:]
check("modelling tables read as thermodynamic results: GEMS (time, temperature), FactSage, Thermo-Calc, PHREEQC .sel", len(mods) == 5 and all(it.det.get("thermo") for it in mods), [(os.path.basename(str(it.path)), bool(it.det.get("thermo"))) for it in mods])
tc = next(it for it in mods if "thermocalc" in str(it.path)); ph_ = next(it for it in mods if str(it.path).endswith(".sel"))
check("Thermo-Calc NP(...) columns get clean phase names", {"LIQUID", "HALITE", "C3S"} <= {c["label"] for c in tc.spec["panels"][0]["curves"]})
check("PHREEQC: the equilibrium phases (not si_, m_, d_) against time, in mol", set(ph_.det["thermo"]["phases"]) == {"Calcite", "Portlandite"} and ph_.det["thermo"]["unit"] == "mol")
check("Thermodynamic modelling is in Analysis, once (not repeated in the gallery)", pa.find_entry("Phase assemblage (stacked areas)") is not None and pa.find_entry("Saturation indices") is not None and pt.find_entry("Saturation indices") is None)
fs = next(it for it in mods if "equilib_table" in str(it.path)); w._tick_only([fs])
w.tools.thermo_chart("Phase amounts (lines)", pa)
check("equilibrium table drawn as phase amounts (lines), ready for Origin", fs.custom["style"] == "Phase amounts (lines)" and all(c.get("kind", "line") != "area" for c in fs.spec["panels"][0]["curves"]) and len(fs.spec["panels"][0]["curves"]) == 5)
w.tools.thermo_chart("Phase assemblage (stacked areas)", pa)
check("... and back to stacked areas", any(c.get("kind") == "area" for c in fs.spec["panels"][0]["curves"]))
w._tick_only([ph_]); n4 = len(w.singles)
made = w.tools.thermo_extract("si", pa, sync=True)
si = pd.read_csv(made[0], encoding="utf-8-sig")
check("PHREEQC saturation indices as a new graph: si_ columns, -99 left out, provenance written", list(si.columns) == ["time", "Calcite (SI)", "Gypsum (SI)"] and len(w.singles) == n4 + 1 and os.path.exists(made[0][:-4] + "_provenance.json"), list(si.columns))
made2 = w.tools.thermo_extract("ph", pa, sync=True)
check("pH and pe as a new graph", list(pd.read_csv(made2[0], encoding="utf-8-sig").columns) == ["time", "pH", "pe"])
w._tick_only([fs]); r = w.tools.thermo_extract("si", pa, sync=True)
check("no SI columns: a plain message", isinstance(r, tuple) and "saturation" in r[1])
# files in the chat
doc = TMP / "notes.md"; doc.write_text("# Mix design\nThe paste has w/c 0.45 and 10 % filler.", encoding="utf-8")
n5 = len(w.singles)
from PySide6.QtGui import QImage as _QI
_im = _QI(40, 30, _QI.Format_RGB32); _im.fill(0); _im.save(str(TMP / "photo.png"))
dat, att = w.assistant.attach([str(doc), str(E / "strength.csv"), str(TMP / "photo.png")]); wait(lambda: w.thread is None and len(w.singles) > n5)
check("+ in the chat: a data file goes to Your graphs (ticked), a document is attached, a picture is shown", len(w.singles) > n5 and att == ["notes.md"] and not w.assistant.attbar.isHidden() and "<img" in w.assistant.view.toHtml() and len(w.assistant.pending_images) == 1)
w.assistant.pending_images = []; w.assistant.images = []
seen3 = {}
def chat_doc(conn, model, system, messages, timeout=180):
    seen3["m"] = messages[-1]["content"]; return json.dumps({"say": "The paste has **w/c 0.45**:\n- filler 10 %\n- see [1]", "actions": [], "done": True})
ai.chat = chat_doc; w.assistant.conn = {"provider": "anthropic", "base": "https://api.anthropic.com", "key": "k", "name": "Claude (Anthropic)"}
w.assistant.web.setChecked(False); w.assistant.send("what is the w/c?"); app.processEvents()
check("the attached document goes with the next message (once) and the chip clears", "ATTACHED DOCUMENT 'notes.md'" in seen3["m"] and "w/c 0.45" in seen3["m"] and not w.assistant.attached and w.assistant.attbar.isHidden())
hh = w.assistant.view.toHtml()
check("the chat is readable: bold, bullet lists and [n] references are formatted", "<li" in hh and "font-weight:" in hh and "[1]" in w.assistant.view.toPlainText())
ai.chat = real_chat
import workspace_assistant as WA
rh = WA.results_html([{"title": "A &amp; B", "url": "https://doi.org/1", "where": "X (2020) J", "text": "snippet", "kind": "paper", "cited": 5}], "alite")
check("web results as numbered cards: title opens the preview, ↗ the page, PAPER tag, cited count, Google and Scholar buttons", "PAPER" in rh and "cited 5" in rh and "scholar.google.com" in rh and "href='https://doi.org/1'" in rh and "href='preview:0'" in rh)
import web_free as WF
WF._get = lambda url, timeout=25: (_ for _ in ()).throw(WF.SearchError("export.arxiv.org: HTTP Error 429"))
WF._get_json = lambda url, timeout=25: {"pages": [{"title": "Calcium aluminoferrite", "key": "Calcium_aluminoferrite", "excerpt": "forms &quot;C-S-H&quot;"}]} if "wikipedia" in url else (_ for _ in ()).throw(WF.SearchError("api.semanticscholar.org: HTTP Error 429")) if "semantic" in url else {"results": []}
w.assistant.conn = None; w.assistant.free_search("aluminoferrite"); app.processEvents()
tx = w.assistant.view.toPlainText()
check("free search: HTML signs shown as text (no &quot;), a busy service (429) is not shown as an error", '"C-S-H"' in tx and "&quot;" not in tx and "429" not in tx.split("aluminoferrite")[-1], tx[-300:])

# ---------------------------------------------------------------- 5.38: paper preview, pictures, draw like this, program used, movable panels
from PySide6.QtCore import QUrl
WF._get_json = fake_json; WF._get = fake_get
FAKE["api.openalex.org/works/doi"] = {"abstract_inverted_index": {"Alite": list(range(0, 80, 2)), "hydration": list(range(1, 80, 2))}, "best_oa_location": {"pdf_url": "https://oa.example/p.pdf"}}
w.assistant.conn = None; w.assistant.free_search("alite hydration"); app.processEvents()
k_ = next(i for i, r in enumerate(w.assistant.papers) if "10.1/abc" in r["url"])
w.assistant.papers[k_]["abstract"] = "short"
pv = w.assistant.on_link(QUrl(f"preview:{k_}")); app.processEvents()
pt_ = pv.browser.toPlainText()
check("Preview: the paper in the app with the whole abstract (fetched by its DOI), DOI link and free PDF", "Hydration of alite" in pt_ and pt_.count("Alite hydration") >= 20 and "10.1/abc" in pt_ and pv.b_pdf.isEnabled(), pt_[:160])
check("Copy the reference", pv.copy_ref().startswith("A. Author (2011). Hydration of alite. Cem. Concr. Res.") and "https://doi.org/10.1/abc" in QApplication.clipboard().text())
pv.b_ask.click(); app.processEvents()
check("Ask the assistant about it: title and abstract go with the next message", any(n.startswith("paper: Hydration of alite") for n, _ in w.assistant.attached))
w.assistant.attached = []; w.assistant.show_attachments()
from PySide6.QtGui import QImage, QColor
img = QImage(320, 200, QImage.Format_RGB32); img.fill(QColor("white")); img.save(str(TMP / "figure.png"))
w.assistant.attach([str(TMP / "figure.png")])
hh = w.assistant.view.toHtml()
check("a picture is shown in the chat with 'Draw my data like this' and 'Ask about it'", "<img" in hh and "like:0" in hh and "ask:0" in hh and len(w.assistant.pending_images) == 1)
seen4 = []
def chat_pic(conn, model, system, messages, timeout=180):
    seen4.append(messages)
    return json.dumps({"say": "It is a stacked plot with symbols.", "actions": [], "done": True})
ai.chat = chat_pic; w.assistant.conn = {"provider": "anthropic", "base": "x", "key": "k", "name": "Claude"}
w.assistant.web.setChecked(False); w.assistant.send("what is this?")
last = seen4[-1][-1]["content"]
check("the picture goes to the AI with the message (as a picture, not as text)", isinstance(last, list) and last[0]["type"] == "image" and last[0]["mime"] == "image/png" and len(last[0]["data"]) > 100)
w.assistant.send("and now?")
check("... and only once: later messages carry only its name", all(isinstance(m["content"], str) for m in seen4[-1][:-1]))
import assistant as _ai
pa_ = _ai._parts("anthropic", last); po_ = _ai._parts("openai", last); pg_ = _ai._parts("gemini", last); pr_ = _ai._parts("openai", last, "responses")
check("pictures in the form each AI reads (Claude, ChatGPT chat and Responses, Gemini)", pa_[0]["source"]["type"] == "base64" and po_[0]["image_url"]["url"].startswith("data:image/png;base64,")
      and "inline_data" in pg_[0] and pr_[0]["type"] == "input_image")
w._tick_only([xi]); w.assistant.on_link(QUrl("like:0")); app.processEvents()
lk = seen4[-1][-1]["content"]
check("Draw my data like this: the picture and the ticked graph go to the AI, which may only copy the style", isinstance(lk, list) and "Draw MY data the same way" in lk[-1]["text"] and "Never copy numbers" in lk[-1]["text"])
w.assistant.conn = None; r_ = w.assistant.like_image(0)
check("without an AI that sees pictures: a plain message", r_ == "no ai")
ai.chat = real_chat
# own graph (what the AI proposes after looking at a picture)
cols = [str(c) for c in xi.det["nums"]]
r_ = w.do_action({"do": "own", "graph": w.items.index(xi) + 1, "style": "Symbols", "xtitle": "2θ (°)", "xrev": True})
check("'own': the graph drawn your way (symbols, axis title, reversed axis)", all(c.get("kind") == "scatter" for c in xi.spec["panels"][0]["curves"] if not str(c["label"]).startswith("_")) and xi.spec["xname"] == "2θ (°)" and xi.spec.get("xrev"), r_)
try: w.do_action({"do": "own", "graph": w.items.index(xi) + 1, "ys": ["no such column"]}); r_ = "no error"
except ValueError as e: r_ = str(e)
check("'own' with a column that does not exist: refused with the real column names", "no column" in r_, r_)
# the program used for a model
gm = next(it for it in mods if "gems_hydration" in str(it.path)); w._tick_only([gm])
pa.tree.setCurrentItem(pa.find_entry("Program and database used")); app.processEvents()
pa.fields["software"].setCurrentText("GEMS (GEM-Selektor)"); pa.fields["database"].setText("CEMDATA18"); pa.buttons.itemAt(0).widget().click(); app.processEvents()
check("Program and database: written under the figure, in the record and in the session", gm.spec.get("note", "").endswith("Calculated with GEMS (GEM-Selektor), CEMDATA18.") and any("GEMS" in r for r in gm.record)
      and next(g for g in sp.session_dump(w.singles, [], {})["graphs"] if "gems_hydration" in g["file"])["model"] == {"_software": "GEMS (GEM-Selektor)", "_database": "CEMDATA18"})
check("the list of programs: GEMS, CEMGEMS, FactSage, Thermo-Calc, PHREEQC, HCh, Perple_X, OLI, MTDATA, ChemApp",
      all(pa.fields["software"].findText(k, Qt.MatchContains) >= 0 for k in ("GEMS", "CEMGEMS", "FactSage", "Thermo-Calc", "PHREEQC", "HCh", "Perple_X", "OLI", "MTDATA", "ChemApp")))
# movable panels
w.go(0); w.panels_btn.menu(); w.panel_as_window(w.graphs_dock); app.processEvents()
check("a panel as its own window, with minimise and maximise", w.graphs_dock.isWindow() and bool(w.graphs_dock.windowFlags() & Qt.WindowMaximizeButtonHint) and w.graphs_dock.isVisible())
w.graphs_dock.showMaximized(); app.processEvents(); w.graphs_dock.showMinimized(); app.processEvents()
w.dock_back(); app.processEvents()
check("Put the panels back in place", not w.graphs_dock.isFloating() and not w.graphs_dock.isWindow() and w.graphs_dock.isVisible() and w.wsmain.dockWidgetArea(w.graphs_dock) == Qt.LeftDockWidgetArea)
w.wsmain.addDockWidget(Qt.BottomDockWidgetArea, w.settings_dock); app.processEvents()
check("panels can be moved to another side (Graph settings at the bottom)", w.wsmain.dockWidgetArea(w.settings_dock) == Qt.BottomDockWidgetArea)
w.dock_back()
# panels
w.panel_actions["graphs"].setChecked(False); w.panel_actions["nav"].setChecked(False); app.processEvents()
check("Panels: Your graphs and the side bar minimised, remembered for the next start", not w.graphs_card.isVisible() and not w.navw.isVisible() and set(json.load(open(TMP / "settings_modern.json"))["hidden_panels"]) == {"nav", "graphs"})
w.focus_graph(); app.processEvents()
check("Focus on the graph: only the graph is left", not w.settings_card.isVisible() and not w.dock.isVisible() and w.canvas.isVisible())
next(a_ for a_ in w.panels_btn.menu().actions() if a_.text() == "Show everything").trigger(); app.processEvents()
check("Show everything", w.graphs_card.isVisible() and w.navw.isVisible() and w.settings_card.isVisible())
w.show_assistant(True)
if len(sys.argv) > 1:
    w.assistant.web.setChecked(True); w.go(1); pa.tree.setCurrentItem(pa.find_entry("Find peaks")); app.processEvents(); time.sleep(0.3); app.processEvents()
    w.grab().save(sys.argv[1] + "_analysis.png"); w.go(4); app.processEvents(); time.sleep(0.2); app.processEvents(); w.grab().save(sys.argv[1] + "_settings.png")
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

"""Origin Plot Studio - modern window, step 4: the assistant panel.

A chat that stays beside your work (dock it left or right, or drag it out as its own window). Without any key it still searches the
web for free (web_free.py: papers from OpenAlex, Semantic Scholar, Crossref and arXiv; Wikipedia only as a fallback), and 'Ask in your browser' hands the question to the ChatGPT,
Claude or Gemini website you already use. With a key it uses the AI connection of the
current window (assistant.py: Claude, ChatGPT, Gemini, Kimi, a local model through Ollama, or any OpenAI-compatible service such as
OpenRouter, Groq, xAI or Mistral), with a model list you can change at any time, and an optional web search (Claude, ChatGPT, Gemini,
OpenRouter search themselves; for the others the app searches first and gives them the results) that says which pages it used.

What it may do is a fixed list of actions on this window (MODERN_ACTIONS). It proposes them; nothing runs until you press 'Do it'.
It never sees your full data tables and never changes your numbers: the app's own code does every calculation.
"""
from __future__ import annotations

import html
import json
import os
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTextBrowser, QVBoxLayout,
                               QWidget)

import assistant as ai
import smart_plots as sp

MODERN_ACTIONS = """
ACTIONS (the only things you can do in this window). "graph" and "graphs" are the numbers n of the list "graphs" in STATE.
  {"do": "look", "graph": n}                      more about one graph: file, kind, its columns with their ranges, its result table. Use it before you analyse or label.
  {"do": "show", "graph": n}                      show a graph in the preview (and a picture of it in the chat).
  {"do": "show_graph", "graph": n}                a picture of the graph in the chat (no change to anything).
  {"do": "show_table", "graph": n, "what": "data|results", "rows": 20}     the first rows of a graph's data or results table in the chat.
  You may also write small tables in "say" as Markdown (| a | b |) - only numbers you were given.
  {"do": "tick", "graphs": [n, ...]}              tick graphs ("all" or "none" also work).
  {"do": "sample", "graphs": [n, ...], "name": "Sample A (4 % additive)"}     give graphs a sample name (graphs with the same name are put together).
  {"do": "kind", "graph": n, "kind": "<one of KINDS>"}              say what kind of measurement a table is.
  {"do": "analysis", "tool": "<one of TOOLS>", "graphs": [n, ...], "settings": {"<key>": value}}     run a data-analysis tool; new curves come to the list, tables to RESULTS. Settings you leave out keep their defaults.
  {"do": "tga_steps", "graphs": [n, ...]}         TGA mass loss in temperature intervals (total and residue).
  {"do": "figtype", "type": "<G01..G24, C01, C02>", "graphs": [n, ...]}     draw workbooks as a gallery graph type.
  {"do": "figure", "graphs": [n, ...]}            one figure with panels (a), (b) ... from up to 9 graphs.
  {"do": "own", "graph": n, "x": "<column>", "ys": ["<column>", ...], "style": "<one of OWN_STYLES>", "xtitle": "", "ytitle": "", "xlog": false, "xrev": false, "layout": "<one of OWN_LAYOUTS>"}
        draw one table your way (columns from "look"). Leave out what should stay.
  {"do": "group", "graphs": [n, ...], "how": "stack|overlay"}     the graphs (one kind) in one figure, stacked with an offset or overlaid.
  {"do": "thermo_chart", "graphs": [n, ...], "style": "Phase assemblage (stacked areas)|Phase amounts (lines)|Phase assemblage (stacked bars)|Change against the first row|Pore solution (logarithmic)"}
        draw results of a thermodynamic model (GEMS, FactSage, Thermo-Calc, PHREEQC ...) the way the user wants.
  {"do": "psd_style", "graphs": [n, ...], "style": "<one of PSD_STYLES>"}     how particle size distributions are drawn.
  {"do": "psd_sizes", "graphs": [n, ...]}  /  {"do": "psd_rrsb", "graphs": [n, ...]}     D10/D50/D90/span/mode table, or the RRSB fit (x', n, R²).
  {"do": "thermo_software", "graphs": [n, ...], "software": "<one of SOFTWARE>", "database": "CEMDATA18"}     which program (and database) calculated the tables, ONLY as the user said; it is written on the figure.
  {"do": "thermo_extract", "graphs": [n, ...], "what": "si|solution|ph"}     saturation indices, solution composition or pH/pe/Eh of a model as a new graph.
  {"do": "labels_auto", "graphs": [n, ...], "n": 8, "prominence": 5}     label the peaks with their POSITIONS (numbers only). Never phase names.
  {"do": "labels_clear", "graphs": [n, ...]}      remove those automatic labels.
  {"do": "ftir_read", "graphs": [n, ...], "signal": "absorbance|transmittance|auto"}     how FTIR spectra are read (bands at maxima or minima).
  {"do": "ftir_areas", "graphs": [n, ...], "regions": [{"from": 1200, "to": 850, "name": "Si-O"}]}     FTIR band areas in wavenumber regions the USER gave.
  {"do": "folder", "path": "D:\\\\Paper2\\\\figures"}     where everything is saved.
  {"do": "save", "graph": n}                      publication files (PNG 600 dpi, TIFF, PDF, SVG) of one graph at the chosen journal size.
  {"do": "draw", "graphs": [n, ...]}              draw in Origin and save the files ("ticked" or "all" also work). Do this last.
  {"do": "paper_preview"}  /  {"do": "paper_set"}     preview (PDF) or make the paper set.
  {"do": "xrd_app", "graph": n}                   open the XRD Scan Generator with that scan (Peak correct is a tab there).
  {"do": "remember", "text": "..."}               save a lasting rule the user stated ("always ...", "from now on ...").

HOW YOU ANSWER
Answer with ONE JSON object and nothing else:  {"say": "<short message, plain words>", "actions": [<in order>], "done": true}
- "done": false means: carry out these actions, then show me the RESULTS and the new STATE, I have more to do. Use it after "look" and "analysis".
- The user confirms your actions before they run. Say in one line what they will do.
- When you searched the web, say what you found in "say" and name the sources in a few words; the app lists the links. Facts from the web
  are for explaining and planning; they never replace the user's data, labels or measured values.
"""


CHAT_CSS = """
td.you { background-color: #E7F0F8; color: #0B2E4A; padding: 8px 10px; }
td.ai { background-color: #FFFFFF; color: #172B4D; padding: 8px 10px; border: 1px solid #D8E1EC; }
td.app { color: #4D5B6B; padding: 4px 2px; font-size: 9pt; }
span.who { color: #A9542A; font-weight: 600; font-size: 8.5pt; }
td.num { color: #FFFFFF; background-color: #2563EB; font-weight: 600; font-size: 8.5pt; padding: 2px 6px; }
td.res { padding: 6px 8px; border-bottom: 1px solid #E5E9EE; }
a { color: #0B5FA5; text-decoration: none; }
span.meta { color: #5B6876; font-size: 8.5pt; }
span.tag { color: #8A4421; font-size: 8pt; font-weight: 600; }
span.snip { color: #2B3642; font-size: 9pt; }
code { background-color: #EEF1F4; }
table.dt { border: 1px solid #D8DEE5; margin: 4px 0; }
table.dt th { background-color: #EEF1F4; color: #172B4D; font-size: 8.5pt; font-weight: 600; padding: 3px 6px; }
table.dt td { font-size: 8.5pt; padding: 2px 6px; border-top: 1px solid #E5E9EE; }
p.cap { color: #4D5B6B; font-size: 8.5pt; margin: 2px 0; }
span.oa { color: #FFFFFF; background-color: #2E7D32; font-size: 7.5pt; font-weight: 600; }
a.small { font-size: 8.5pt; }
"""


def _md_table(rows):
    """| a | b | rows (Markdown) as an HTML table."""
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [c for c in cells if not all(set(x) <= set("-: ") for x in c)]          # the |---|---| line
    if not cells:
        return ""
    head, body = cells[0], cells[1:]
    return ("<table class='dt' cellspacing='0' cellpadding='3'><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr>"
            + "".join("<tr>" + "".join(f"<td>{html.escape(x)}</td>" for x in r) + "</tr>" for r in body) + "</table>")


def table_html(df, title="", max_rows=30):
    """A table of numbers for the chat (the first rows; the whole table is in the app and its CSV)."""
    if df is None or not len(df):
        return ""
    d = df.head(max_rows)
    fmt = lambda v: f"{v:.5g}" if isinstance(v, float) else html.escape(str(v))
    return ((f"<p class='cap'><b>{html.escape(title)}</b></p>" if title else "") + "<table class='dt' cellspacing='0' cellpadding='3'><tr>"
            + "".join(f"<th>{html.escape(str(c))}</th>" for c in d.columns) + "</tr>"
            + "".join("<tr>" + "".join(f"<td>{fmt(v)}</td>" for v in row) + "</tr>" for row in d.itertuples(index=False)) + "</table>"
            + (f"<p class='cap'>{len(df) - max_rows} more row(s): see the Results tab or the CSV.</p>" if len(df) > max_rows else ""))


def md(text):
    """A little Markdown for the chat: **bold**, `code`, lists, tables, [1] references, links. Everything else is shown as text."""
    import re as _re
    lines_ = str(text).split("\n")
    out_t, buf = [], []
    for line in lines_ + [""]:                                    # Markdown tables first, as blocks
        if line.strip().startswith("|") and line.strip().count("|") >= 2:
            buf.append(line)
            continue
        if buf:
            out_t.append("\x00TABLE" + str(len(out_t)) + "\x00")
            md.tables = getattr(md, "tables", {})
            md.tables[out_t[-1]] = _md_table(buf)
            buf = []
        out_t.append(line)
    text = "\n".join(out_t[:-1])
    out, inlist = [], None
    for line in str(text).split("\n"):
        if line.startswith("\x00TABLE"):
            if inlist:
                out.append(f"</{inlist}>")
                inlist = None
            out.append(md.tables.pop(line, ""))
            continue
        t = html.escape(line)
        t = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = _re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = _re.sub(r"(https?://[^\s<]+)", r"<a href='\1'>\1</a>", t)
        t = _re.sub(r"\[(\d{1,2})\]", r"<sup><b style='color:#2563EB'>[\1]</b></sup>", t)
        m = _re.match(r"^\s*(?:[-*•]|(\d+)[.)])\s+(.*)$", t)
        if m:
            tag = "ol" if m.group(1) else "ul"
            if inlist != tag:
                if inlist:
                    out.append(f"</{inlist}>")
                out.append(f"<{tag} style='margin-top:2px;margin-bottom:2px'>")
                inlist = tag
            out.append(f"<li>{m.group(2)}</li>")
            continue
        if inlist:
            out.append(f"</{inlist}>")
            inlist = None
        out.append(t + "<br>")
    if inlist:
        out.append(f"</{inlist}>")
    h = "".join(out)
    return h[:-4] if h.endswith("<br>") else h


def sources_html(sources):
    if not sources:
        return ""
    web = [(t, u) for t, u in sources if "google." not in u]
    goo = [(t, u) for t, u in sources if "google." in u]
    h = ""
    if web:
        h += "<br><span class='meta'>Sources</span><br>" + "<br>".join(
            f"<span class='meta'>[{i}]</span> <a href='{html.escape(u)}'>{html.escape(t)}</a>" for i, (t, u) in enumerate(web, 1))
    if goo:
        h += "<br>" + " &nbsp; ".join(f"<a href='{html.escape(u)}'>🔎 {html.escape(t.replace('Search the same in ', ''))}</a>" for t, u in goo)
    return h


def results_html(results, query=None, start=0):
    """Web results as numbered cards: the title opens the preview in the app (↗ opens the page), who/when/where, times cited,
    open access, the first words of the abstract, and the source."""
    rows = []
    for i, r in enumerate(results, 1):
        cited = f" · cited {r['cited']}×" if r.get("cited") else ""
        paper = r.get("kind") == "paper"
        tag = "PAPER" if paper else "WIKIPEDIA" if "wikipedia" in str(r.get("url", "")) else "PAGE"
        oa = " <span class='oa'>OPEN ACCESS</span>" if r.get("oa_url") else ""
        snip = html.escape(str(r.get("text") or "")[:260])
        rows.append(f"<tr><td class='num' valign='top' width='22'>{i}</td><td class='res'><a href='preview:{start + i - 1}'><b>{html.escape(r['title'])}</b></a>"
                    f" <a href='{html.escape(r['url'])}' title='open in the browser'>↗</a><br>"
                    f"<span class='tag'>{tag}</span>{oa} <span class='meta'>{html.escape(str(r.get('where') or ''))}{cited}"
                    f"{(' · ' + html.escape(r['source'])) if r.get('source') else ''}</span>"
                    + (f"<br><span class='snip'>{snip}</span>" if snip else "")
                    + (f"<br><a href='preview:{start + i - 1}' class='small'>Preview · abstract</a>" if paper else "") + "</td></tr>")
    h = "<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:4px'><tr><td width='22'></td><td></td></tr>" + "".join(rows) + "</table>"
    if query:
        import web_free
        h += "<p>" + " &nbsp; ".join(f"<a href='{html.escape(u)}'>🔎 {html.escape(t.replace('Search the same in ', ''))}</a>" for t, u in web_free.google_links(query)) + "</p>"
    return h


def read_document(path, limit=12000):
    """The text of a document for the AI (PDF, Word, Markdown, text). Returns (text, why-not)."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                try:
                    from PyPDF2 import PdfReader
                except ImportError:
                    return "", "reading PDF needs the Python package pypdf (py -m pip install pypdf)"
            r = PdfReader(path)
            t = "\n".join((pg.extract_text() or "") for pg in r.pages[:30])
        elif ext == ".docx":
            try:
                import docx
            except ImportError:
                return "", "reading Word needs the Python package python-docx (py -m pip install python-docx)"
            t = "\n".join(p.text for p in docx.Document(path).paragraphs)
        else:
            with open(path, encoding="utf-8", errors="replace") as fh:
                t = fh.read(limit + 1)
        if ext in (".html", ".htm"):
            import re as _re
            t = _re.sub(r"<[^>]+>", " ", t)
        t = " ".join(t.split()) if ext == ".pdf" else t
        if not t.strip():
            return "", "no text found (a scanned PDF has pictures, not text)"
        return (t[:limit] + (" …[shortened]" if len(t) > limit else "")), ""
    except Exception as e:
        return "", f"not read ({e})"


def system_prompt(lists, instructions, lessons):
    return ("You are the assistant inside the modern window of Origin Plot Studio (version " + sp.VERSION + "), a Windows program for materials-"
            "science data (XRD, TGA, FTIR, calorimetry, particle size, any table). It previews graphs, analyses them, draws them in OriginPro and "
            "saves publication files. The user types; you answer and propose the app's actions. The app does the work with its own code.\n"
            + ai.BUILT_IN_RULES + MODERN_ACTIONS
            + "\nKINDS: " + json.dumps(lists["KINDS"], ensure_ascii=False)
            + "\nTOOLS (name: settings with defaults): " + json.dumps(lists["TOOLS"], ensure_ascii=False)
            + "\nGALLERY TYPES: " + json.dumps(lists["GALLERY"], ensure_ascii=False)
            + "\nPSD_STYLES: " + json.dumps(sp.PSD_STYLES, ensure_ascii=False)
            + "\nSOFTWARE: " + json.dumps(__import__("workspace_tools").SOFTWARE, ensure_ascii=False)
            + "\nOWN_STYLES: " + json.dumps(sp.OWN_STYLES, ensure_ascii=False) + "\nOWN_LAYOUTS: " + json.dumps(sp.OWN_LAYOUTS, ensure_ascii=False)
            + "\nPICTURES: when the user sends a picture you may describe it and copy its STYLE (kind of chart, layout, axes, labels) to the "
              "user's data with the actions; never take numbers from a picture into the user's graphs."
            + "\n\nTHE USER'S OWN INSTRUCTIONS (follow them unless they conflict with the rules above):\n" + (instructions.strip() or "(none)")
            + "\n\nWHAT YOU HAVE LEARNED FROM THIS USER BEFORE:\n" + (lessons.strip() or "(nothing yet)") + "\n")


def lists():
    import analysis_tools as at
    tools = {lab: {s[0]: s[3] for s in t[2]} for lab, t in at.TOOLS.items()}
    try:
        import gallery_graphs as tg
        figtype = {k: v[1] for k, v in tg.TYPES.items()}
    except Exception:
        figtype = {}
    return {"KINDS": [k for k in sp.KINDS if not k.startswith("Gallery")], "TOOLS": tools, "GALLERY": figtype}


def web_free_wants(text):
    import web_free
    return web_free.wants_pictures(text)


class Bridge(QObject):
    answer = Signal(object)       # (text, sources) or an error string
    models = Signal(object, object)
    paper = Signal(object)        # the details of a paper for the preview


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff")


class PaperPreview(QWidget):
    """A paper inside the app: title, authors, year, journal, DOI, times cited, open access, the whole abstract; open it, open the
    free PDF, copy the reference, or ask the assistant about it."""

    def __init__(self, panel, r):
        super().__init__(panel.ws, Qt.Window)
        self.panel, self.r = panel, r
        self.setWindowTitle("Paper preview")
        self.resize(720, 620)
        v = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        v.addWidget(self.browser, 1)
        row = QHBoxLayout()
        self.b_open = QPushButton("Open the paper")
        self.b_pdf = QPushButton("Free PDF")
        self.b_cite = QPushButton("Copy the reference")
        self.b_ask = QPushButton("Ask the assistant about it", objectName="primary")
        for b in (self.b_open, self.b_pdf, self.b_cite):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.b_ask)
        v.addLayout(row)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        go = lambda u: (QDesktopServices.openUrl(QUrl(u)) if u and not os.environ.get("OPS_NO_OPEN") else None)
        self.b_open.clicked.connect(lambda: go(self.r.get("url")))
        self.b_pdf.clicked.connect(lambda: go(self.r.get("oa_url")))
        self.b_cite.clicked.connect(self.copy_ref)
        self.b_ask.clicked.connect(lambda: (self.panel.ask_paper(self.r), self.close()))
        self.fill(r)

    def set_text(self, t):
        self.note = t
        self.fill(self.r)

    def copy_ref(self):
        import web_free
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(web_free.citation(self.r))
        return web_free.citation(self.r)

    def fill(self, r):
        self.r = r
        au = r.get("authors") or []
        ab = r.get("abstract") or r.get("text") or ""
        note = getattr(self, "note", "")
        doi = r.get("doi")
        self.browser.setHtml(
            f"<h2 style='color:#172B4D'>{html.escape(r.get('title', ''))}</h2>"
            f"<p style='color:#4D5B6B'>{html.escape(', '.join(au[:25]) + (' et al.' if len(au) > 25 else '')) or html.escape(r.get('where', ''))}</p>"
            f"<p><b>{html.escape(str(r.get('venue') or r.get('where') or ''))}</b> {html.escape(str(r.get('year') or ''))}"
            + (f" · cited {r['cited']}×" if r.get("cited") else "") + (f" · <span style='color:#2E7D32'><b>open access</b></span>" if r.get("oa_url") else "")
            + (f"<br>DOI: <a href='https://doi.org/{html.escape(doi)}'>{html.escape(doi)}</a>" if doi else f"<br><a href='{html.escape(r.get('url', ''))}'>{html.escape(r.get('url', ''))}</a>")
            + (f" · found in {html.escape(r['source'])}" if r.get("source") else "") + "</p>"
            f"<h3>Abstract</h3><p style='line-height:140%'>{html.escape(ab) or 'No abstract is available from the free sources; open the paper.'}</p>"
            + (f"<p style='color:#4D5B6B'>{html.escape(note)}</p>" if note else ""))
        self.b_pdf.setEnabled(bool(r.get("oa_url")))


class AssistantPanel(QWidget):
    def __init__(self, ws):
        super().__init__()
        self.ws = ws
        self.home = ai.home(sp.store_dir(ws.opt))
        self.conn, self.hist, self.pending, self.rounds, self.busy = None, [], [], 0, False
        self.more, self.user_texts, self.keys, self.cfg = False, [], {}, {}
        self.papers, self.images, self.pending_images = [], [], []     # papers shown (for the preview), pictures in the chat, pictures for the next message
        self.bridge = Bridge()
        self.bridge.answer.connect(self._answered)
        self.bridge.models.connect(self._got_models)
        self.bridge.paper.connect(self._paper_ready)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)
        self.prov = QComboBox()
        self.prov.setToolTip("Your AI. Add or change one in Settings > AI for the assistant. 'Free web search' needs no key.")
        self.prov.activated.connect(lambda _i: self.connect_ai())
        v.addWidget(self.prov)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setToolTip("The model. Every model your key can use is listed; you can change it at any time, also in the middle of a chat.")
        self.model.activated.connect(lambda _i: self.save_model())
        v.addWidget(self.model)
        r2 = QHBoxLayout()
        self.web = QCheckBox("Search the web")
        self.web.setToolTip("Look things up online (papers, phase data, methods); the pages used are listed. Claude, ChatGPT, Gemini and "
                            "OpenRouter search themselves; for a local model, other AIs or no AI at all the app searches for free "
                            "(papers from OpenAlex, Semantic Scholar, Crossref, arXiv) - no key needed.")
        r2.addWidget(self.web)
        r2.addStretch(1)
        br = QPushButton("Ask in browser ▾")
        br.setToolTip("No key? Ask ChatGPT, Claude or Gemini on their website with your own account: the question (and the list of your "
                      "graphs) is copied and the site opens. It cannot act on the app from there.")
        from PySide6.QtWidgets import QMenu
        m = QMenu(br)
        for site in ("ChatGPT", "Claude", "Gemini"):
            m.addAction(site, lambda s_=site: self.ask_browser(s_))
        br.setMenu(m)
        r2.addWidget(br)
        new = QPushButton("New chat")
        new.clicked.connect(self.new_chat)
        r2.addWidget(new)
        v.addLayout(r2)
        self.state = QLabel("", objectName="soft")
        self.state.setWordWrap(True)
        v.addWidget(self.state)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        self.view.setOpenLinks(False)
        self.view.anchorClicked.connect(self.on_link)
        self.view.setAcceptDrops(False)
        self.view.setStyleSheet("QTextBrowser { border: 1px solid #D8DEE5; border-radius: 10px; background: #FBFCFD; padding: 6px; font-size: 10pt; }")
        self.view.document().setDefaultStyleSheet(CHAT_CSS)
        v.addWidget(self.view, 1)
        self.card = QFrame(objectName="card")
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(10, 8, 10, 8)
        self.cardtext = QLabel("", wordWrap=True)
        cl.addWidget(self.cardtext)
        cb = QHBoxLayout()
        self.doit = QPushButton("Do it", objectName="primary")
        self.doit.clicked.connect(self.run_pending)
        self.dont = QPushButton("Don't")
        self.dont.clicked.connect(self.drop_pending)
        cb.addStretch(1)
        cb.addWidget(self.dont)
        cb.addWidget(self.doit)
        cl.addLayout(cb)
        self.card.hide()
        v.addWidget(self.card)
        self.attached = []                                 # [(name, text)]: documents sent with the next message
        self.attbar = QLabel("", objectName="soft")
        self.attbar.setWordWrap(True)
        self.attbar.setTextFormat(Qt.RichText)
        self.attbar.linkActivated.connect(self.remove_attachment)
        self.attbar.hide()
        v.addWidget(self.attbar)
        box = QFrame(objectName="inbox")
        box.setStyleSheet("QFrame#inbox { border: 1px solid #C9D2DC; border-radius: 10px; background: #FFFFFF; } "
                          "QPlainTextEdit { border: none; background: transparent; } "
                          "QPushButton#plus { border: 1px solid #C9D2DC; border-radius: 17px; background: #F4F6F8; font-size: 16pt; font-weight: 600; "
                          "color: #2563EB; padding: 0px; min-width: 0px; } QPushButton#plus:hover { background: #EAF2FF; }")
        shadow = QGraphicsDropShadowEffect(box); shadow.setBlurRadius(18); shadow.setOffset(0, 3); shadow.setColor(QColor(23, 50, 77, 55))
        box.setGraphicsEffect(shadow)       # a soft lift under the box you type into (a plain child widget here, so it renders correctly - never on a floating/top-level window)
        bl = QHBoxLayout(box)
        bl.setContentsMargins(4, 4, 6, 4)
        from PySide6.QtWidgets import QToolButton
        plus = QToolButton()
        plus.setText("+")
        plus.setFixedSize(34, 34)
        plus.setStyleSheet("QToolButton { border: 1px solid #C9D2DC; border-radius: 17px; background: #F4F6F8; font-size: 16pt; font-weight: 600; "
                           "color: #2563EB; padding: 0px; } QToolButton:hover { background: #EAF2FF; }")
        plus.setToolTip("Add files: data files go to Your graphs (ticked); PDF, Word and text documents are read and sent with your next "
                        "message to the AI you chose.")
        plus.clicked.connect(lambda: self.attach())
        bl.addWidget(plus, 0, Qt.AlignBottom)
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("Ask, or tell it what to do with your graphs …  (Ctrl+Enter sends)")
        self.input.setFixedHeight(70)
        bl.addWidget(self.input, 1)
        self.send_btn = QPushButton("Send", objectName="primary")
        bl.addWidget(self.send_btn, 0, Qt.AlignBottom)
        self.send_btn.clicked.connect(lambda: self.send())
        v.addWidget(box)
        note = QLabel("It sees the list of your graphs, what you type and the documents you attach - not your data tables. You confirm every action.",
                      objectName="soft")
        note.setWordWrap(True)
        v.addWidget(note)
        QShortcut(QKeySequence("Ctrl+Return"), self.input, activated=lambda: self.send())
        for wdg in (self.input, self.view, self.view.viewport()):          # paste a picture; drop files or pictures on the chat
            wdg.installEventFilter(self)
            wdg.setAcceptDrops(True)
        self.say("app", "Hello. Without any key, choose **Free web search** above and type your question, or use **Ask in browser** with "
                 "your ChatGPT, Claude or Gemini account. With an AI key (Settings > AI for the assistant) or a free local model (Ollama) it "
                 "also works on your graphs. Press **+** to add data files or documents.")
        self.reload()

    # ------------------------------------------------------------------ the AI and its models
    def settings(self):
        return ai.load_settings(self.home)

    def saved(self):
        """{provider: key} for every AI with a saved key, plus the local model (no key) and keys in Windows variables."""
        c = self.settings()
        keys = {k: ai.reveal_key(v) for k, v in (c.get("keys") or {}).items()}
        keys = {k: v for k, v in keys.items() if v}
        for pr, p in ai.PROVIDERS.items():
            if p["env"] and os.environ.get(p["env"]) and pr not in keys:
                keys[pr] = os.environ[p["env"]].strip()
        keys.setdefault("ollama", "")
        return keys, c

    def reload(self):
        keys, c = self.saved()
        self.keys, self.cfg = keys, c
        self.prov.blockSignals(True)
        self.prov.clear()
        for pr in keys:
            if pr == "ollama":
                continue
            name = ai.PROVIDERS[pr]["name"] if pr != "other" else ((c.get("addresses") or {}).get("other") or "Other service")
            self.prov.addItem(name, pr)
        self.prov.addItem("Free web search (no AI, no key)", "none")
        self.prov.addItem(ai.PROVIDERS["ollama"]["name"], "ollama")
        want = ai.provider_of(c.get("choice") or "") or next((p for p in keys if p != "ollama"), "none")
        i = self.prov.findData(want)
        self.prov.setCurrentIndex(i if i >= 0 else 0)
        self.prov.blockSignals(False)
        self.connect_ai()

    def connect_ai(self):
        pr = self.prov.currentData()
        if pr is None:
            return
        if pr == "none":
            self.conn = None
            self.model.clear()
            self.model.setEnabled(False)
            self.model.hide()
            self.web.setEnabled(True)
            self.state.setText("Free web search, academic first: papers from OpenAlex, Semantic Scholar, Crossref and arXiv (Wikipedia only when no paper is found).")
            return
        self.model.setEnabled(True)
        self.model.show()
        try:
            conn = ai.detect(self.keys.get(pr, ""), (self.cfg.get("addresses") or {}).get(pr, ""), ai.PROVIDERS[pr]["name"])
        except ai.AIError as e:
            self.state.setText(str(e))
            return
        self.state.setText(f"Linking to {conn['name']} …")
        def work():
            try:
                self.bridge.models.emit(conn, ai.models(conn))
            except Exception as e:
                self.bridge.models.emit(conn, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _got_models(self, conn, ids):
        if isinstance(ids, str):
            self.conn = None
            self.state.setText(f"Not linked: {ids}  (choose 'No AI: free web search' to search without an AI)")
            return
        self.conn = conn
        self.model.clear()
        self.model.addItems(ids)
        want = (self.cfg.get("models") or {}).get(conn["provider"], "")
        self.model.setCurrentText(want if (want in ids or not ids) else (ids[0] if ids else ""))
        web = "searches the web itself" if ai.web_capable(conn) else "the app searches the web for it (free)"
        self.state.setText(f"Linked to {conn['name']} · {len(ids)} model(s) · {web}")

    def save_model(self):
        if not self.conn:
            return
        c = self.settings()
        keys = {k: ai.reveal_key(v) for k, v in (c.get("keys") or {}).items()}
        models = dict(c.get("models") or {})
        models[self.conn["provider"]] = self.model.currentText().strip()
        ai.save_settings(self.home, {**c, "keys": {k: v for k, v in keys.items() if v}, "models": models, "choice": ai.PROVIDERS[self.conn["provider"]]["name"]})

    # ------------------------------------------------------------------ the chat
    def say(self, who, text, sources=(), results=None, query=None):
        """One message: yours on the right, the assistant's and the app's on the left; web results as numbered cards."""
        body = md(str(text))
        if who == "you":
            h = (f"<table width='100%' cellspacing='0' cellpadding='0'><tr><td width='12%'></td><td class='you'>{body}</td></tr></table>")
        elif who == "ai":
            h = f"<table width='100%' cellspacing='0'><tr><td class='ai'><span class='who'>Assistant</span><br>{body}{sources_html(sources)}</td><td width='6%'></td></tr></table>"
        else:
            h = f"<table width='100%' cellspacing='0'><tr><td class='app'>{body}{sources_html(sources)}</td></tr></table>"
        if results is not None:
            h += results_html(results, query, len(self.papers))
            self.papers += list(results)
        self.view.append(h)
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    # ------------------------------------------------------------------ files in the chat (+)
    DOC_EXT = (".pdf", ".docx", ".md", ".rtf", ".json", ".log", ".html", ".htm")

    def attach(self, paths=None):
        """+ in the chat: data files go to Your graphs (ticked); documents are read and sent with the next message."""
        from PySide6.QtWidgets import QFileDialog
        if paths is None:
            paths, _ = QFileDialog.getOpenFileNames(self, "Add files to the chat", "", "All files (*.*);;Data files (*.xlsx *.xlsm *.xls *.csv *.txt *.dat "
                                                    "*.xy *.xrdml *.brml *.ras *.sel *.spa);;Documents (*.pdf *.docx *.md *.txt *.json)")
        data, docs, notes = [], [], []
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in self.DOC_EXT:
                docs.append(p)
            elif ext in IMAGE_EXT:
                self.add_image(p)
            else:
                data.append(p)
        if data:
            self.ws.load(data, tick=True)
            self.say("app", f"Added to Your graphs (ticked): {', '.join(os.path.basename(p) for p in data)}")
        for p in docs:
            t, why = read_document(p)
            if t:
                self.attached.append((os.path.basename(p), t))
            else:
                notes.append(f"{os.path.basename(p)}: {why}")
        if notes:
            self.say("app", "\n".join(notes))
        self.show_attachments()
        return data, [n for n, _ in self.attached]

    def show_attachments(self):
        if not self.attached and not self.pending_images:
            self.attbar.hide()
            return
        chips = " &nbsp; ".join([f"📎 {html.escape(n)} ({len(t) // 1000 + 1} k chars) <a href='{i}' style='color:#8B1E28;text-decoration:none'>✕</a>"
                                 for i, (n, t) in enumerate(self.attached)] +
                                [f"🖼 {html.escape(im['name'])} <a href='img{i}' style='color:#8B1E28;text-decoration:none'>✕</a>" for i, im in enumerate(self.pending_images)])
        self.attbar.setText("Sent with your next message: " + chips)
        self.attbar.show()

    def remove_attachment(self, i):
        try:
            if str(i).startswith("img"):
                self.pending_images.pop(int(str(i)[3:]))
            else:
                self.attached.pop(int(i))
        except Exception:
            pass
        self.show_attachments()

    # ------------------------------------------------------------------ pictures in the chat
    def add_image(self, path, name=None):
        """A picture (a graph from a paper, a photo): shown in the chat; it goes with your next message to an AI that can see pictures."""
        import base64
        ext = os.path.splitext(path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/png")
        data_path = path
        if ext in (".tif", ".tiff", ".bmp"):                          # the AI services read PNG, JPEG, GIF, WebP: converted to PNG
            from PySide6.QtGui import QImage
            import tempfile
            data_path = os.path.join(tempfile.gettempdir(), f"ops_chat_{len(self.images)}_{os.getpid()}.png")
            QImage(path).save(data_path, "PNG")
            mime = "image/png"
        with open(data_path, "rb") as fh:
            raw = fh.read()
        if len(raw) > 4_500_000:
            from PySide6.QtGui import QImage
            import tempfile
            data_path = os.path.join(tempfile.gettempdir(), f"ops_chat_{len(self.images)}_{os.getpid()}_small.jpg")
            QImage(path).scaledToWidth(1600).save(data_path, "JPG", 85)
            mime, raw = "image/jpeg", open(data_path, "rb").read()
        im = {"name": name or os.path.basename(path), "mime": mime, "data": base64.b64encode(raw).decode("ascii"), "path": data_path}
        self.images.append(im)
        self.pending_images.append(im)
        i = len(self.images) - 1
        from PySide6.QtCore import QUrl
        url = QUrl.fromLocalFile(os.path.abspath(data_path)).toString()
        self.view.append(f"<table width='100%' cellspacing='0'><tr><td width='12%'></td><td class='you'><img src='{url}' width='240'><br>"
                         f"<span class='meta'>🖼 {html.escape(im['name'])}</span><br><a href='like:{i}'><b>Draw my data like this</b></a> &nbsp; "
                         f"<a href='ask:{i}'>Ask about it</a> &nbsp; <a href='open:{i}'>Open</a></td></tr></table>")
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())
        self.show_attachments()
        return i

    def paste_image(self):
        """Ctrl+V in the message box with a picture on the clipboard (a screenshot, a figure copied from a PDF)."""
        from PySide6.QtWidgets import QApplication
        import tempfile, time as _t
        img = QApplication.clipboard().image()
        if img.isNull():
            return False
        p = os.path.join(tempfile.gettempdir(), f"ops_pasted_{int(_t.time() * 1000)}.png")
        img.save(p, "PNG")
        self.add_image(p, "pasted picture")
        return True

    def eventFilter(self, obj, e):
        from PySide6.QtCore import QEvent
        if obj is self.input and e.type() == QEvent.KeyPress and e.matches(QKeySequence.Paste):
            from PySide6.QtWidgets import QApplication
            if QApplication.clipboard().mimeData().hasImage() and self.paste_image():
                return True
        if e.type() in (QEvent.DragEnter, QEvent.DragMove) and e.mimeData().hasUrls():
            e.acceptProposedAction()
            return True
        if e.type() == QEvent.Drop and e.mimeData().hasUrls():
            self.attach([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
            e.acceptProposedAction()
            return True
        return super().eventFilter(obj, e)

    def like_image(self, i):
        """Draw my data like this picture: the AI looks at the picture and proposes the actions (chart, layout, axes, labels, grouping)."""
        im = self.images[int(i)]
        if self.conn is None:
            self.say("app", "Drawing your data like a picture needs an AI that can see pictures (Claude, ChatGPT or Gemini; Settings > AI for "
                     "the assistant). The free web search cannot read pictures.")
            return "no ai"
        if im not in self.pending_images:
            self.pending_images.append(im)
        ticked = [g for g in self.state_json()["graphs"] if g.get("ticked")]
        return self.send(f"Look at the picture '{im['name']}': it is a graph I like. Draw MY data the same way: the same kind of chart "
                         "(lines, symbols, bars, stacked areas ...), stacked or overlaid or in panels, axis direction and log axes, peak labels as "
                         "positions if it has labels. " + (f"Use my ticked graph(s) {[g['n'] for g in ticked]}. " if ticked else "Ask me which of my graphs to use. ")
                         + "Use 'look' first, then the actions (own, group, figure, labels_auto, thermo_chart ...). Never copy numbers from the picture: "
                         "only the style. Say in one line what you will change.")

    def ask_image(self, i):
        im = self.images[int(i)]
        if im not in self.pending_images:
            self.pending_images.append(im)
            self.show_attachments()
        self.input.setPlainText(f"What does the picture '{im['name']}' show? ")
        self.input.setFocus()

    def show_pictures(self, pics, query=None):
        """A gallery of pictures from Wikimedia Commons: thumbnail, title, author and licence; 'Use in chat' (an AI can then see it, or
        'Draw my data like this'), 'Source' opens its page."""
        import urllib.parse
        from PySide6.QtCore import QUrl
        start = len(getattr(self, "web_pics", []))
        self.web_pics = getattr(self, "web_pics", []) + list(pics)
        cells = []
        for k, p in enumerate(pics):
            i = start + k
            cells.append(f"<td valign='top' width='33%' style='padding:4px'><img src='{QUrl.fromLocalFile(p['path']).toString()}' width='190'><br>"
                         f"<span class='meta'><b>{html.escape(p['title'][:70])}</b><br>{html.escape(p.get('author') or '')} · {html.escape(p.get('licence') or '')}</span><br>"
                         f"<a href='pic:{i}'>Use in chat</a> &nbsp; <a href='{html.escape(p.get('page') or '')}'>Source</a></td>")
        rows = "".join("<tr>" + "".join(cells[j:j + 3]) + "</tr>" for j in range(0, len(cells), 3))
        more = (f"<p class='cap'>Pictures from Wikimedia Commons (free to use under the licence shown). More: <a href='https://www.google.com/search?tbm=isch&q="
                f"{urllib.parse.quote_plus(query)}'>Google Images</a></p>") if query else "<p class='cap'>Pictures from Wikimedia Commons (licence under each).</p>"
        self.view.append(f"<table width='100%' cellspacing='0'><tr><td class='ai'><span class='who'>Pictures</span><table width='100%'>{rows}</table>{more}</td></tr></table>")
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())
        return len(pics)

    # ------------------------------------------------------------------ links in the chat
    def on_link(self, url):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        u = url.toString()
        sch, _, arg = u.partition(":")
        if sch == "preview":
            return self.preview_paper(int(arg))
        if sch == "pic":
            p = self.web_pics[int(arg)]
            return self.add_image(p["path"], p["title"])
        if sch == "graph":
            return self.show_in_workspace(int(arg))
        if sch == "gopen":
            if not os.environ.get("OPS_NO_OPEN"):
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.graph_pics[int(arg)][0]))
            return "gopen"
        if sch == "like":
            return self.like_image(int(arg))
        if sch == "ask":
            return self.ask_image(int(arg))
        if sch == "open":
            if not os.environ.get("OPS_NO_OPEN"):
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.images[int(arg)]["path"]))
            return "open"
        if not os.environ.get("OPS_NO_OPEN"):
            QDesktopServices.openUrl(url)
        return "browser"

    def preview_paper(self, i):
        """The paper in the app: title, all authors, year, journal, DOI, times cited, open access, the whole abstract."""
        import web_free
        r = self.papers[i]
        dlg = PaperPreview(self, r)
        self.preview = dlg
        if r.get("kind") == "paper" and len(r.get("abstract") or "") < 200 and r.get("doi"):
            dlg.set_text("Fetching the whole abstract …")
            def work():
                try:
                    self.bridge.paper.emit(web_free.details(r))
                except Exception:
                    self.bridge.paper.emit(r)
            if os.environ.get("OPS_ASSISTANT_SYNC"):
                work()
            else:
                import threading as _th
                _th.Thread(target=work, daemon=True).start()
        if not os.environ.get("OPS_NO_OPEN"):
            dlg.show()
        return dlg

    def _paper_ready(self, r):
        if getattr(self, "preview", None) is not None:
            self.preview.note = "" if len(r.get("abstract") or "") >= 200 else "The free sources have only this part of the abstract: open the paper for the rest."
            self.preview.fill(r)

    def ask_paper(self, r):
        self.attached.append((f"paper: {r['title'][:60]}", f"{r['title']}\n{r.get('where')}\nDOI: {r.get('doi') or r.get('url')}\nABSTRACT: {r.get('abstract') or r.get('text')}"))
        self.show_attachments()
        self.input.setPlainText("What does this paper find, and how does it relate to my data? ")
        self.ws.show_assistant(True)
        self.input.setFocus()

    def new_chat(self):
        self.hist, self.pending, self.rounds = [], [], 0
        self.card.hide()
        self.view.clear()
        self.say("app", "New chat. Your instructions and what it learned stay.")

    def state_json(self):
        ws = self.ws
        names = sp.display_names(ws.singles) if ws.singles else []
        nm = {id(it): n for it, n in zip(ws.singles, names)}
        ticked = {id(i) for i in ws.ticked()}
        gl = []
        for n, it in enumerate(ws.items, 1):
            if isinstance(it, sp.Board):
                gl.append({"n": n, "name": it.name, "figure_of": len(it.members), "ticked": id(it) in ticked})
            else:
                gl.append({"n": n, "name": nm.get(id(it)) or it.title.strip()[:60], "kind": it.kind, "file": os.path.basename(str(getattr(it, "path", "") or "")),
                           "sample": getattr(it, "sample", "") or "", "combined": it in ws.combined, "ticked": id(it) in ticked})
        cur = ws.current()
        return {"graphs": gl, "shown": (ws.items.index(cur) + 1) if cur in ws.items else None, "folder": ws.outdir.text().strip() or "(the app's results folder)",
                "journal": ws.journal.currentText()}

    def send(self, text=None, auto=False):
        if self.busy:
            return "busy"
        text = (text if text is not None else self.input.toPlainText()).strip()
        if not text:
            return "empty"
        if self.conn is None:
            if not auto:
                self.input.clear()
                self.say("you", text)
            if self.show_examples(text):                     # 'show me graphs of ...': how the app draws it, then papers and pictures
                return self.free_search(text)
            done = self.fixed_command(text)
            if done:
                self.say("app", done)
                return "command"
            return self.free_search(text)
        model = self.model.currentText().strip()
        if not auto:
            self.input.clear()
            self.say("you", text)
            self.rounds = 0
            self.user_texts.append(text)
            try:
                self.show_examples(text)                      # 'graphs of PSD': the app's own pictures first, then the AI answers
            except Exception:
                pass
        docs = ""
        if self.attached and not auto:
            docs = "".join(f"\n\nATTACHED DOCUMENT '{n}' (text, may be shortened):\n{t}" for n, t in self.attached)
            self.say("app", "Sent with this message: " + ", ".join(n for n, _ in self.attached))
            self.attached = []
            self.show_attachments()
        body = text + docs + "\n\nSTATE: " + json.dumps(self.state_json(), ensure_ascii=False)
        if self.pending_images and not auto:                  # pictures go with this message to an AI that can see them
            content = [{"type": "image", "mime": im["mime"], "data": im["data"]} for im in self.pending_images] + [
                {"type": "text", "text": f"(picture{'s' if len(self.pending_images) > 1 else ''}: {', '.join(im['name'] for im in self.pending_images)})\n" + body}]
            self.pending_images = []
            self.show_attachments()
        else:
            content = body
        self.hist.append({"role": "user", "content": content})
        system = system_prompt(lists(), ai.read_text(ai.instructions_file(self.home)), ai.read_text(ai.lessons_file(self.home)))
        recent = self.hist[-16:]
        while recent and recent[0]["role"] != "user":
            recent = recent[1:]
        recent = [m if (k == len(recent) - 1 or isinstance(m["content"], str)) else          # a picture is sent once; later only its name
                  dict(m, content=" ".join(c.get("text", "[picture]") if c.get("type") != "image" else "[picture]" for c in m["content"]))
                  for k, m in enumerate(recent)]
        web = self.web.isChecked() and self.web.isEnabled()
        conn = self.conn
        app_search = web and not auto and not ai.web_capable(conn)        # the app searches; the AI answers from the results
        self.busy = True
        self.send_btn.setEnabled(False)
        self.state.setText("Searching the web and thinking …" if web else "Thinking …")
        def work():
            try:
                if app_search:
                    import web_free
                    try:                                       # the AI writes a precise search query first: better results than the raw question
                        q = ai.chat(conn, model, "You write web search queries for scientific questions. Answer with the query only: at most 12 "
                                    "words, the technical terms, no quotes, no explanation.", [{"role": "user", "content": text}], 60).strip().splitlines()[0][:200]
                        q = q.strip(' "\'') or web_free.search_words(text)
                    except Exception:
                        q = web_free.search_words(text)
                    res, probs = web_free.search(q)
                    msgs = [dict(m) for m in recent]
                    msgs[-1]["content"] += ("\n\nWEB RESULTS (found by the app; cite them as [1], [2] ... and say when they do not answer the question):\n"
                                            + (web_free.as_text(res) or "(nothing found" + (": " + "; ".join(probs) if probs else "") + ")"))
                    out = (ai.chat(conn, model, system, msgs), [(r["title"], r["url"]) for r in res] + web_free.google_links(q))
                elif web:
                    out = ai.chat_web(conn, model, system, recent)
                else:
                    out = (ai.chat(conn, model, system, recent), [])
                if web and isinstance(out, tuple) and web_free_wants(text):
                    import web_free
                    try:
                        pics, _pp = web_free.pictures(web_free.search_words(text), 6)
                    except Exception:
                        pics = []
                    out = (out[0], out[1], pics)
                self.bridge.answer.emit(out)
            except Exception as e:
                self.bridge.answer.emit(str(e))
        if os.environ.get("OPS_ASSISTANT_SYNC"):
            work()
        else:
            threading.Thread(target=work, daemon=True).start()
        return "sent"

    EXAMPLE_KINDS = [(r"particle size|psd|granulometr|grain size|sieve", "Particle size", "psd.xlsx"), (r"\bxrd\b|x-?ray diffr|diffractogram|diffraction", "XRD", "xrd_raw.csv"),
                     (r"\btga\b|\bdtg\b|thermogravimetr|mass loss", "TGA", "TGA_Ref_28d_rep1.txt"), (r"ftir|infrared|\bir spectr", "FTIR", "ftir.xlsx"),
                     (r"calorimetr|heat flow|heat of hydration", "Calorimetry", "calorimetry.csv"), (r"strength", "XY", "strength.csv")]

    def show_examples(self, text):
        """'show me graphs of particle size distribution': how the app draws that kind - your own graphs of that kind first, else the
        example files - as pictures in the chat, every style there is; plus Google Images for other people's figures."""
        import re as _re
        import urllib.parse
        wants_see = (_re.search(r"(?i)\b(show|see|view|display|examples?|look like|looks like|how (is|are) .* drawn)\b", text)
                     or _re.search(r"(?i)^\W*(graphs?|figures?|charts?|pictures?|images?)\s+(of|for)\b", text))      # 'graphs of PSD cements'
        noun = _re.search(r"(?i)\b(graphs?|plots?|figures?|pictures?|images?|photos?|examples?|charts?|drawn|look like|looks like)\b", text)
        if not (wants_see and noun):                          # 'plot TGA with DTG' is a command, 'show me graphs of TGA' a wish to see
            return False
        hit = next(((k, f) for rx, k, f in self.EXAMPLE_KINDS if _re.search("(?i)" + rx, text)), None)
        if hit is None:
            return False
        kind, fname = hit
        mine = [it for it in self.ws.singles if it.kind == kind][:3]
        its = mine
        if not its:
            try:
                its, _ = sp.load_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples_synthetic", fname))
                for it in its:
                    it.build(self.ws.opt)
                its = its[:1]
            except Exception:
                its = []
        if not its:
            return False
        self.say("app", f"How Origin Plot Studio draws **{kind.lower()}** " + ("(your own graphs):" if mine else "(an example file of the app; add your files to see them drawn the same way):"))
        for it in its:
            if kind == "Particle size":                       # every PSD style there is
                old = it.det.get("_psd_style")
                for st in sp.PSD_STYLES:
                    it.det["_psd_style"] = st
                    it.build(self.ws.opt, it.kind)
                    self.chat_graph(it, f"{it.title.strip()} - {st}", st)
                if old:
                    it.det["_psd_style"] = old
                else:
                    it.det.pop("_psd_style", None)
                it.build(self.ws.opt, it.kind)
            else:
                self.chat_graph(it)
        import web_free
        q = web_free.search_words(text)
        self.say("app", "Figures by others: these open in your browser.", [("Google Images: " + q, "https://www.google.com/search?tbm=isch&q=" + urllib.parse.quote_plus(q))]
                 + web_free.google_links(q))
        return True

    def fixed_command(self, text):
        """Without any AI: short commands the app understands itself (assistant_parser), e.g. 'plot TGA with DTG',
        'stack all XRD files', 'analyse the TGA steps', 'draw G07', 'plot calorimetry, mass 0.5 g', 'generate XRD scans', 'system check'."""
        import re as _re
        if not _re.match(r"(?i)^\s*(please\s+)?(plot|draw|stack|make|generate|create|analy[sz]e|run|check|show|open|process)\b", text):
            return None
        m_ = _re.match(r"(?i)^\s*(please\s+)?show\s+(me\s+)?(the\s+)?(graph|table|data|results)\s*(?:no\.?|number|#)?\s*(\d+)", text)
        if m_:
            n_ = int(m_.group(5))
            if not 1 <= n_ <= len(self.ws.items):
                return f"There is no graph {n_} (the list has {len(self.ws.items)})."
            it = self.ws.items[n_ - 1]
            if m_.group(4).lower() == "graph":
                self.chat_graph(it, f"{n_}. {it.title.strip()}")
                return f"Graph {n_}: {it.title.strip()[:70]}"
            self.chat_table(*self.ws.table_for_chat({"graph": n_, "what": "results" if m_.group(4).lower() == "results" else "data"}))
            return f"The {m_.group(4).lower()} of graph {n_}."
        import assistant_parser as ap
        a = ap.parse(text)
        if not a:
            return None
        ws, act, p = self.ws, a["action"], a["params"]
        kind = lambda k: [s_ for s_ in ws.singles if s_.kind == k]
        if act == "figtype_graph":
            r = ws.tools.figtype_draw(str(p.get("type")).upper(), ws.pages.widget(2))
            if isinstance(r, tuple):                          # nothing to draw it from: not a command after all - searched instead
                return None
        elif act == "system_check":
            r = ws.system_check()
        elif act == "generate_xrd_scans":
            r = ws.tools.xrd_app(False)
        elif act == "analyze_tga_steps":
            r = ws.tools.tga_steps(ws.pages.widget(1))
            if isinstance(r, tuple):
                return r[1]
            self.chat_table(r, "TGA mass loss in temperature intervals")
            r = "the table is above (and saved as CSV)."
        elif act == "plot_tga":
            its = kind("TGA")
            if not its:
                return "No TGA graph yet: add a TGA file first."
            ws._tick_only(its)
            ws.go(0)
            ws.list.setCurrentRow(ws.items.index(its[0]))
            r = f"{len(its)} TGA graph(s) ticked and shown (TG and DTG together). F5 draws them in Origin."
        elif act == "stack_xrd":
            its = kind("XRD")
            if len(its) < 2:
                return "Stacking needs two or more XRD patterns."
            ws._tick_only(its)
            ws.group_ticked("stack")
            r = f"{len(its)} XRD patterns stacked (your group ◆ at the top)."
        elif act == "plot_calorimetry":
            pg = ws.open_entry(1, "Calorimetry (TAM III)") and ws.pages.widget(1)
            if p.get("mass_g") and pg is not None and pg.calo_table is not None:
                for r_ in range(pg.calo_table.rowCount()):
                    pg.calo_table.item(r_, 1).setText(f"{p['mass_g']:g}")
            r = "Analysis > Calorimetry is open with your files" + (f" and the mass {p['mass_g']:g} g" if p.get("mass_g") else "") + ": press Process."
        else:
            r = "That figure is made from a workbook and a recipe: Draw > Paper figures from a recipe."
        return f"Done without an AI ({act.replace('_', ' ')}): {r}"

    def free_search(self, text):
        """No AI: the question is searched for free (academic papers first) and the results are listed."""
        import web_free
        self.busy = True
        self.send_btn.setEnabled(False)
        self.state.setText("Searching the web (free) …")
        def work():
            try:
                q = web_free.search_words(text)
                res, probs = web_free.search(q)
                pics = []
                try:
                    pics, pp = web_free.pictures(q, 6)
                except Exception as e:
                    pp = [str(e)]
                self.bridge.answer.emit(("__free__", res, probs, q, pics))
            except Exception as e:
                self.bridge.answer.emit(str(e))
        if os.environ.get("OPS_ASSISTANT_SYNC"):
            work()
        else:
            threading.Thread(target=work, daemon=True).start()
        return "searching"

    def ask_browser(self, site, text=None):
        """Your free ChatGPT / Claude / Gemini account in the browser: the question and the list of your graphs are copied, the site opens."""
        import urllib.parse
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QApplication
        q = (text if text is not None else self.input.toPlainText()).strip()
        names = [g["name"] + (f" ({g['kind']})" if g.get("kind") else "") for g in self.state_json()["graphs"]][:20]
        full = q + ("\n\n(My graphs in Origin Plot Studio: " + "; ".join(names) + ")" if names else "")
        QApplication.clipboard().setText(full)
        url = {"ChatGPT": "https://chatgpt.com/?q=" + urllib.parse.quote(full[:1800]), "Claude": "https://claude.ai/new?q=" + urllib.parse.quote(full[:1800]),
               "Gemini": "https://gemini.google.com/app"}[site]
        if not os.environ.get("OPS_NO_OPEN"):
            QDesktopServices.openUrl(QUrl(url))
        self.say("app", f"{site} opens in your browser with your question. If it is not filled in, click the box there and press Ctrl+V "
                 "(it is copied). Answers there cannot act on the app.")
        return url

    def _answered(self, out):
        self.busy = False
        self.send_btn.setEnabled(True)
        if isinstance(out, tuple) and out and out[0] == "__free__":
            _t, res, probs, q = out[:4]
            pics = out[4] if len(out) > 4 else []
            import web_free
            self.state.setText("Free web search, academic first: papers from OpenAlex, Semantic Scholar, Crossref and arXiv (Wikipedia only when no paper is found).")
            busy = [p_ for p_ in probs if "429" in p_]
            other = [p_ for p_ in probs if "429" not in p_]
            if pics:
                self.show_pictures(pics, q)
            if res:
                self.say("app", f"**{len(res)} results** for “{q}”", results=res, query=q)
                if other:
                    self.say("app", "Not reached this time: " + "; ".join(other))
            else:
                self.say("app", "Nothing found" + (" (the search services are busy - try again in a minute)" if busy else "")
                         + ("; " + "; ".join(other) if other else "") + ". Try other words, or the same search in Google:", web_free.google_links(q))
            return
        self.state.setText(f"Linked to {self.conn['name']} · model {self.model.currentText()}" if self.conn else "")
        if isinstance(out, str):
            self.say("app", out)
            return
        txt, src = out[0], out[1]
        if len(out) > 2 and out[2]:
            self.show_pictures(out[2], None)
        self.hist.append({"role": "assistant", "content": txt})
        r = ai.parse_reply(txt)
        if r["say"]:
            self.say("ai", r["say"], src)
        elif src:
            self.say("ai", "(sources)", src)
        self.pending, self.more = r["actions"], not r["done"]
        if self.pending:
            safe = {"look", "show", "show_graph", "show_table"}
            if all(a.get("do") in safe for a in self.pending):          # only reading: no need to ask
                self.run_pending()
                return
            self.cardtext.setText("<b>The assistant wants to:</b><br>" + "<br>".join("· " + html.escape(self.describe(a)) for a in self.pending))
            self.card.show()

    def describe(self, a):
        d = a.get("do")
        g = a.get("graphs", a.get("graph", ""))
        return {"analysis": f"run {a.get('tool')} on graph(s) {g}" + (f" with {a.get('settings')}" if a.get("settings") else ""),
                "draw": f"draw graph(s) {g} in Origin and save the files", "save": f"save the publication files of graph {g}",
                "sample": f"name graph(s) {g} '{a.get('name')}'", "kind": f"treat graph {g} as {a.get('kind')}", "tick": f"tick graph(s) {g}",
                "figtype": f"draw graph(s) {g} as gallery type {a.get('type')}", "figure": f"make one figure from graph(s) {g}",
                "folder": f"save into {a.get('path')}", "remember": f"remember: {a.get('text')}", "tga_steps": f"TGA mass loss of graph(s) {g}",
                "paper_preview": "make the paper-set preview (PDF)", "paper_set": "make the paper set (draws in Origin)",
                "xrd_app": f"open the XRD Scan Generator with graph {g}", "group": f"{a.get('how', 'overlay')} graph(s) {g} in one figure",
                "own": f"draw graph {g} as {a.get('style') or 'chosen'}" + (f", x = {a.get('x')}" if a.get("x") else "") + (f", y = {a.get('ys')}" if a.get("ys") else "")
                       + (", log x" if a.get("xlog") else "") + (", reversed x" if a.get("xrev") else ""),
                "thermo_software": f"note that table(s) {g} were calculated with {a.get('software')}" + (f" ({a.get('database')})" if a.get("database") else ""),
                "thermo_chart": f"draw model table(s) {g} as {a.get('style')}", "thermo_extract": f"make a {a.get('what')} graph from model table(s) {g}",
                "labels_auto": f"label the peaks of graph(s) {g} with their positions", "labels_clear": f"remove the automatic labels of graph(s) {g}",
                "ftir_read": f"read FTIR graph(s) {g} as {a.get('signal')}", "ftir_areas": f"measure FTIR band areas of graph(s) {g} in {a.get('regions')}"}.get(d, f"{d} {g}".strip())

    def drop_pending(self):
        self.pending = []
        self.card.hide()
        self.say("app", "Not done.")

    def show_in_workspace(self, i):
        """'Show in Workspace' under a graph in the chat: the graph is opened in Workspace. An example graph (not one of yours yet)
        is added to your graphs first, drawn in the style of the picture you clicked."""
        pic = self.graph_pics[i]
        it, style = pic[1], (pic[2] if len(pic) > 2 else None)
        ws = self.ws
        if not isinstance(it, sp.Board) and (style is not None or it not in ws.items):
            if it not in ws.singles:
                ws.singles.append(it)
            if style is not None:
                it.det["_psd_style"] = style
            try:
                it.build(ws.opt, it.kind)
            except Exception as e:
                self.say("app", f"The graph could not be opened in Workspace: {e}")
                return None
            ws.refresh_list()
        if it not in ws.items:
            self.say("app", "That graph is no longer in Workspace.")
            return None
        ws.go(0)
        ws.list.setCurrentRow(ws.items.index(it))
        self.say("app", f"Opened in Workspace: {it.title.strip()}" + (f" ({style})" if style else "") + ".")
        return "graph"

    # ------------------------------------------------------------------ graphs and tables in the chat
    def chat_graph(self, it, caption=None, style=None):
        """A picture of the graph, as the app draws it, in the chat (click: show it in Workspace)."""
        import tempfile
        from matplotlib.figure import Figure
        from PySide6.QtCore import QUrl
        if it is None or (getattr(it, "spec", None) is None and not isinstance(it, sp.Board)):
            return None
        fig = Figure(figsize=(6.4, 4.2), dpi=90)
        try:
            if isinstance(it, sp.Board):
                sp.board_figure(it, fig, 1.5, 1.5)
            else:
                sp.preview_figure(it.spec, fig=fig)
        except Exception as e:
            self.say("app", f"The graph could not be drawn here: {e}")
            return None
        n = len(self.images) + len(getattr(self, "graph_pics", []))
        p = os.path.join(tempfile.gettempdir(), f"ops_chat_graph_{os.getpid()}_{n}.png")
        fig.savefig(p, dpi=90, facecolor="white")
        self.graph_pics = getattr(self, "graph_pics", []) + [(p, it, style)]
        i = len(self.graph_pics) - 1
        cap = caption or it.title.strip()
        self.view.append(f"<table width='100%' cellspacing='0'><tr><td class='ai'><img src='{QUrl.fromLocalFile(p).toString()}' width='420'><br>"
                         f"<span class='meta'>📈 {html.escape(cap[:90])}</span> &nbsp; <a href='graph:{i}'>Show in Workspace</a> &nbsp; "
                         f"<a href='gopen:{i}'>Open the picture</a></td><td width='6%'></td></tr></table>")
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())
        return p

    def chat_table(self, df, title=""):
        h = table_html(df, title)
        if h:
            self.view.append(f"<table width='100%' cellspacing='0'><tr><td class='ai'>{h}</td><td width='6%'></td></tr></table>")
            self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())
        return bool(h)

    GRAPH_ACTIONS = ("own", "figtype", "group", "psd_style", "labels_auto", "labels_clear", "thermo_chart", "kind", "ftir_read", "show", "show_graph", "figure",
                     "thermo_software", "sample")
    TABLE_ACTIONS = ("analysis", "tga_steps", "ftir_areas", "psd_sizes", "psd_rrsb")

    def run_pending(self):
        self.card.hide()
        acts, self.pending = self.pending, []
        lines = []
        for a in acts:
            d = a.get("do")
            try:
                r = self.ws.do_action(a, self.user_texts)
                lines.append(f"{d}: {r}")
                if d in self.TABLE_ACTIONS:                          # the result table, as a table
                    df = self.ws.pages.widget(1).resmodel.df
                    if df is not None:
                        self.chat_table(df, f"{a.get('tool') or d.replace('_', ' ')}")
                if d == "show_table":
                    self.chat_table(*self.ws.table_for_chat(a))
                if d in self.GRAPH_ACTIONS or d == "thermo_extract":    # what the graph looks like now
                    self.chat_graph(self.ws.current())
            except Exception as e:
                lines.append(f"{d}: not done ({e})")
        shown = [l.split("\n")[0] if l.split(":")[0] in self.TABLE_ACTIONS else l          # the table itself is above; the AI gets all of it
                 for l in lines if not l.startswith(("look:", "show_graph:", "show_table:"))]
        if shown:
            self.say("app", "\n".join(l[:400] for l in shown))
        if self.more and self.rounds < 5:
            self.rounds += 1
            self.send("RESULTS:\n" + "\n".join(lines), auto=True)

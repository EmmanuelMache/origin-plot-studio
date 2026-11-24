"""Web search without any key or account, academic sources first.

Papers: OpenAlex, Semantic Scholar, Crossref and arXiv (all free and open). Each paper keeps its authors, year, journal, DOI, times
cited, its whole abstract (when the source has it) and a free PDF when one is known (open access). Encyclopaedia pages (Wikipedia)
only when no paper is found, or when you ask for them. Links open the same search in Google and Google Scholar in your browser.

Used by the assistant of the modern window: with no AI, the results are listed; with an AI that cannot search by itself the AI
answers from them. Only your search words are sent (no file, no data, no name). Nothing here needs a key.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

OPENALEX = "https://api.openalex.org/works"
S2 = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF = "https://api.crossref.org/works"
ARXIV = "https://export.arxiv.org/api/query"
WIKIPEDIA = "https://en.wikipedia.org/w/rest.php/v1/search/page"
COMMONS = "https://commons.wikimedia.org/w/api.php"
PICTURE_WORDS = re.compile(r"(?i)\b(pictures?|images?|photos?|photographs?|figures?|graphs?|plots?|charts?|diagrams?|micrographs?|sem|tem|microscop\w*|"
                           r"looks? like|show|drawn|schematic|illustrat\w*|crystal|mineral|structure)\b")
HEADERS = {"User-Agent": "OriginPlotStudio (scientific plotting app)", "Accept": "application/json"}


class SearchError(Exception):
    pass


def _get(url, timeout=25):
    import net                                        # trusts this computer's certificates, like the updater
    try:
        return net.fetch(url, HEADERS, timeout)
    except Exception as e:
        raise SearchError(f"{urllib.parse.urlparse(url).netloc}: {e}")


def _get_json(url, timeout=25):
    raw = _get(url, timeout)
    try:
        return json.loads(raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception as e:
        raise SearchError(f"{urllib.parse.urlparse(url).netloc}: not the expected answer ({e})")


def _clean(t):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", str(t or ""))).split())


def _abstract(inv):
    """OpenAlex keeps the abstract as {word: [positions]}: the whole text, in order."""
    if not isinstance(inv, dict):
        return ""
    pos = sorted((p, w) for w, ps in inv.items() for p in (ps or []))
    return html.unescape(" ".join(w for _, w in pos))


def _short(t, words=45):
    w = str(t or "").split()
    return " ".join(w[:words]) + (" …" if len(w) > words else "")


def _paper(title, url, authors, year, venue, abstract, cited, doi, oa, source):
    au = [a for a in authors if a]
    who = ", ".join(au[:3]) + (" et al." if len(au) > 3 else "")
    return {"title": _clean(title), "url": url, "where": f"{who} ({year or ''}) {venue or ''}".strip(), "text": _short(_clean(abstract)),
            "abstract": _clean(abstract), "authors": au, "year": year, "venue": venue or "", "cited": cited, "doi": doi or "",
            "oa_url": oa or "", "kind": "paper", "source": source}


def papers(query, n=5):
    """OpenAlex: articles, reviews, preprints, theses and chapters, most relevant first."""
    q = urllib.parse.urlencode({"search": query, "per-page": n, "filter": "type:article|review|preprint|book-chapter|dissertation",
                                "select": "title,doi,publication_year,primary_location,authorships,abstract_inverted_index,cited_by_count,open_access,best_oa_location"})
    j = _get_json(f"{OPENALEX}?{q}")
    out = []
    for w in j.get("results") or []:
        loc = w.get("primary_location") or {}
        doi = str(w.get("doi") or "").replace("https://doi.org/", "")
        url = w.get("doi") or loc.get("landing_page_url") or ""
        oa = (w.get("best_oa_location") or {}).get("pdf_url") or (w.get("open_access") or {}).get("oa_url") or ""
        if w.get("title") and url:
            out.append(_paper(w["title"], url, [a.get("author", {}).get("display_name", "") for a in (w.get("authorships") or [])], w.get("publication_year"),
                              (loc.get("source") or {}).get("display_name"), _abstract(w.get("abstract_inverted_index")), w.get("cited_by_count"), doi, oa, "OpenAlex"))
    return out


def papers_s2(query, n=4):
    q = urllib.parse.urlencode({"query": query, "limit": n, "fields": "title,url,year,abstract,venue,authors,citationCount,externalIds,openAccessPdf"})
    j = _get_json(f"{S2}?{q}")
    out = []
    for w in j.get("data") or []:
        doi = (w.get("externalIds") or {}).get("DOI") or ""
        url = f"https://doi.org/{doi}" if doi else w.get("url") or ""
        if w.get("title") and url:
            out.append(_paper(w["title"], url, [a.get("name", "") for a in (w.get("authors") or [])], w.get("year"), w.get("venue"), w.get("abstract"),
                              w.get("citationCount"), doi, (w.get("openAccessPdf") or {}).get("url"), "Semantic Scholar"))
    return out


def papers_crossref(query, n=4):
    q = urllib.parse.urlencode({"query": query, "rows": n, "select": "DOI,title,author,issued,container-title,is-referenced-by-count,abstract,type"})
    j = _get_json(f"{CROSSREF}?{q}")
    out = []
    for w in (j.get("message") or {}).get("items") or []:
        if w.get("type") not in (None, "journal-article", "proceedings-article", "book-chapter", "posted-content", "dissertation"):
            continue
        doi = w.get("DOI") or ""
        year = (((w.get("issued") or {}).get("date-parts") or [[None]])[0] or [None])[0]
        au = [f"{a.get('given', '')[:1]}. {a.get('family', '')}".strip(". ") for a in (w.get("author") or [])]
        if (w.get("title") or [""])[0] and doi:
            out.append(_paper(w["title"][0], f"https://doi.org/{doi}", au, year, (w.get("container-title") or [""])[0], w.get("abstract"),
                              w.get("is-referenced-by-count"), doi, "", "Crossref"))
    return out


def papers_arxiv(query, n=3):
    raw = _get(f"{ARXIV}?" + urllib.parse.urlencode({"search_query": f"all:{query}", "start": 0, "max_results": n}))
    try:
        root = ET.fromstring(raw if isinstance(raw, (bytes, bytearray)) else str(raw).encode("utf-8"))
    except ET.ParseError as e:
        raise SearchError(f"export.arxiv.org: not the expected answer ({e})")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in root.findall("a:entry", ns):
        url = (e.findtext("a:id", "", ns) or "").strip()
        pdf = next((l.get("href") for l in e.findall("a:link", ns) if l.get("title") == "pdf"), "")
        out.append(_paper(e.findtext("a:title", "", ns), url, [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)],
                          (e.findtext("a:published", "", ns) or "")[:4], "arXiv (preprint)", e.findtext("a:summary", "", ns), None, "", pdf, "arXiv"))
    return out


def pages(query, n=3):
    j = _get_json(f"{WIKIPEDIA}?" + urllib.parse.urlencode({"q": query, "limit": n}))
    out = []
    for p in j.get("pages") or []:
        key = p.get("key") or ""
        if not key:
            continue
        text = _clean(p.get("excerpt"))
        out.append({"title": _clean(p.get("title") or key), "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(key), "where": "Wikipedia",
                    "text": (p.get("description") or "") + (" - " if p.get("description") and text else "") + text, "kind": "page", "source": "Wikipedia",
                    "abstract": text})
    return out


def _key(r):
    d = str(r.get("doi") or "").lower()
    if d:
        return d
    u = str(r.get("url", "")).lower()
    return u.split("doi.org/")[-1] if "doi.org/" in u else re.sub(r"[^a-z0-9]", "", str(r.get("title", "")).lower())[:80]


def google_links(query):
    """The same search in Google and Google Scholar, opened in your browser (no key; Google's own results)."""
    q = urllib.parse.quote_plus(query)
    return [("Search the same in Google", f"https://www.google.com/search?q={q}"), ("Search the same in Google Scholar", f"https://scholar.google.com/scholar?q={q}")]


def search(query, n_papers=8, n_pages=3, include_pages=False):
    """Papers first (OpenAlex, Semantic Scholar, Crossref, arXiv; each paper once, the most relevant of each source first);
    Wikipedia only when no paper is found or include_pages. Returns (results, problems)."""
    query = re.sub(r"\s+", " ", str(query or "")).strip()[:300]
    if not query:
        return [], ["no search words"]
    lists, probs = [], []
    for fn, n in ((papers, 5), (papers_s2, 4), (papers_crossref, 4), (papers_arxiv, 3)):
        try:
            lists.append(fn(query, n))
        except SearchError as e:
            probs.append(str(e))
    res, seen = [], {}
    for k in range(max([len(l) for l in lists] or [0])):          # take turns: the best of each source, then the next ...
        for l in lists:
            if k < len(l):
                r = l[k]
                key = _key(r)
                if key in seen:                              # the same paper from two sources: keep it once, with what the other knew
                    old = seen[key]
                    for f in ("abstract", "oa_url", "cited", "venue"):
                        if not old.get(f) and r.get(f):
                            old[f] = r[f]
                    old["text"] = old["text"] or _short(old.get("abstract"))
                    continue
                seen[key] = r
                res.append(r)
    kws = keywords(query)
    res = [r for r in res if relevant(r, kws)][:n_papers]                # off-topic papers are left out
    if include_pages or not res:
        try:
            res += pages(query, n_pages)
        except SearchError as e:
            probs.append(str(e))
    return res, probs


def details(r):
    """Everything known about one paper for the preview; the whole abstract is fetched by its DOI when the list had none."""
    r = dict(r)
    if r.get("kind") == "paper" and r.get("doi") and len(r.get("abstract") or "") < 200:
        for fetch in (lambda d: _get_json(f"{OPENALEX}/doi:{urllib.parse.quote(d)}"), lambda d: _get_json(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(d)}?fields=abstract,openAccessPdf,citationCount,authors")):
            try:
                j = fetch(r["doi"])
            except SearchError:
                continue
            ab = _abstract(j.get("abstract_inverted_index")) or _clean(j.get("abstract"))
            if ab:
                r["abstract"] = ab
            r["oa_url"] = r.get("oa_url") or (j.get("best_oa_location") or {}).get("pdf_url") or (j.get("openAccessPdf") or {}).get("url") or ""
            if j.get("authorships"):
                r["authors"] = [a.get("author", {}).get("display_name", "") for a in j["authorships"]]
            if len(r.get("abstract") or "") >= 200:
                break
    return r


def wants_pictures(text):
    return bool(PICTURE_WORDS.search(str(text or "")))


def pictures(query, n=6, folder=None):
    """Pictures for the words from Wikimedia Commons (free, no key): photos, micrographs, diagrams and figures, each with its title,
    author, licence and page. The thumbnails are downloaded into `folder` so the chat can show them. Returns [dict], problems."""
    import os
    import tempfile
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": n * 2,
                                "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": 360})
    j = _get_json(f"{COMMONS}?{q}")
    pages_ = sorted(((j.get("query") or {}).get("pages") or {}).values(), key=lambda p: p.get("index", 0))
    folder = folder or tempfile.gettempdir()
    out, probs = [], []
    for p in pages_:
        ii = (p.get("imageinfo") or [{}])[0]
        mime, thumb = ii.get("mime", ""), ii.get("thumburl") or ""
        if not thumb or not mime.startswith("image/") or mime in ("image/vnd.djvu", "image/tiff") and not thumb.endswith((".png", ".jpg", ".jpeg")):
            continue
        md_ = ii.get("extmetadata") or {}
        val = lambda k: _clean((md_.get(k) or {}).get("value", ""))
        title = re.sub(r"^File:|\.(jpe?g|png|svg|gif|tiff?|webp)$", "", p.get("title", ""), flags=re.I).replace("_", " ")
        try:
            raw = _get(thumb)
            ext = ".png" if ".png" in thumb.lower() or thumb.lower().endswith(".svg.png") else ".jpg"
            path = os.path.join(folder, f"ops_web_pic_{abs(hash(thumb)) % 10**10}{ext}")
            with open(path, "wb") as fh:
                fh.write(raw if isinstance(raw, (bytes, bytearray)) else bytes(raw))
        except SearchError as e:
            probs.append(str(e))
            continue
        out.append({"title": title[:120], "path": path, "page": ii.get("descriptionurl") or "", "author": val("Artist")[:80],
                    "licence": val("LicenseShortName") or "see the page", "description": val("ImageDescription")[:200]})
        if len(out) >= n:
            break
    return out, probs


def citation(r):
    """A plain reference: Authors (year) Title. Journal. https://doi.org/..."""
    au = r.get("authors") or []
    who = ", ".join(au[:6]) + (", et al." if len(au) > 6 else "")
    return f"{who} ({r.get('year') or 'n.d.'}). {r.get('title')}. {r.get('venue') or ''}. {('https://doi.org/' + r['doi']) if r.get('doi') else r.get('url', '')}".replace(". .", ".")


def as_text(results):
    """The results as the AI reads them: numbered, with title, where, link and the abstract."""
    return "\n".join(f"[{i}] {r['title']} - {r['where']} - {r['url']}\n    {(r.get('abstract') or r.get('text') or '')[:700]}" for i, r in enumerate(results, 1))


FIXES = {"partcile": "particle", "particel": "particle", "paricle": "particle", "ditricution": "distribution", "distrubution": "distribution",
         "distribtion": "distribution", "distibution": "distribution", "hydation": "hydration", "hydratoin": "hydration", "calorimetery": "calorimetry",
         "calorimtry": "calorimetry", "thermogravimetic": "thermogravimetric", "difraction": "diffraction", "diffration": "diffraction",
         "cemnet": "cement", "cment": "cement", "clinkr": "clinker", "portlnd": "portland", "spectrum": "spectrum", "infared": "infrared",
         "rietvelt": "rietveld", "ettringte": "ettringite", "portlandit": "portlandite", "pozzolan": "pozzolan", "thermodyanmic": "thermodynamic",
         "thermodynamc": "thermodynamic", "modelling": "modelling", "analisis": "analysis", "anaysis": "analysis"}


def search_words(text):
    """The words worth searching for in what the user typed: drops 'please', 'show me graphs of', 'search the web for' ...,
    and corrects common misspellings of the science words."""
    t = re.sub(r"(?i)\b(please|can you|could you|search( the)? (web|internet)( for)?|look up|find( me)?|give me|show( me)?|tell me|what is|what are|"
               r"about|on the internet|online|papers? (on|about|of)|(some |a few )?(graphs?|plots?|figures?|pictures?|images?|photos?|examples?) (of|for|showing)|"
               r"how (are|is|do|does)|drawn|look like)\b", " ", str(text))
    t = re.sub(r"[?!.,;:]+", " ", t)
    words = [FIXES.get(w.lower(), w) for w in t.split()]
    return " ".join(words).strip() or str(text).strip()


STOP = set("the and for with from that this into over under of in on at to by an a is are was were be as or its their our your which what how why "
           "using use used between during after before effect effects study analysis new based".split())


def keywords(query):
    return {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2 and w not in STOP}


def relevant(r, kws):
    """A paper is kept when its title or abstract has at least one of the real words of the question (a search service sometimes
    returns papers that share none of them, e.g. only 'show' or 'me')."""
    if not kws:
        return True
    text = (str(r.get("title", "")) + " " + str(r.get("abstract") or r.get("text") or "")).lower()
    hits = sum(1 for k in kws if k in text)
    return hits >= 1

"""PDF numbers -> mineral names.

A peak list exported from a search-match program names the pattern that explains a peak by its reference code
('Matched by': 01-072-0156). The names belong to those codes in the PATTERN LIST of the same analysis (Ref. Code,
Compound Name, Mineral Name, Chemical Formula). This module reads such a pattern list, keeps code -> name, and
translates the codes of a peak list, so the peaks are labelled with the name of the mineral and never with a number.

Nothing is guessed: a code without a name in any pattern list you gave stays a code and is reported.
"""
import os, re, json

# 01-072-0156 (PDF-4/PDF-2), 98-002-7837 (ICSD), 96-900-0096 (COD); the old short form 5-586 is accepted in a code column
CODE_RE = re.compile(r"(?<![\d.\-])(\d{2}-\d{3}-\d{4})(?![\d\-])")
SHORT_RE = re.compile(r"^\s*(\d{1,2}-\d{3,4})\s*$")
NAMES = {}            # key -> {"code", "name", "compound", "formula", "source"}
_LOADED = [False]

# compound names that are one mineral without doubt (a pattern list without a mineral-name column)
COMPOUND_MINERAL = [(r"^calcium hydroxide$", "Portlandite"), (r"^magnesium hydroxide$", "Brucite"), (r"^magnesium oxide$", "Periclase"), (r"^calcium oxide$", "Lime"),
                    (r"^zinc oxide$", "Zincite"), (r"^sodium chloride$", "Halite"), (r"^potassium chloride$", "Sylvite"), (r"^calcium fluoride$", "Fluorite"),
                    (r"^calcium sulfate (di)?hydrate$", "Gypsum"), (r"^calcium magnesium carbonate$", "Dolomite"), (r"^aluminum oxide$|^aluminium oxide$", "Corundum")]


def key(code):
    """The same key for 00-005-0586, 005-0586 and 5-586."""
    parts = [int(p) for p in re.findall(r"\d+", str(code))]
    if len(parts) == 2: parts = [0] + parts
    return tuple(parts)


def codes_in(text):
    """The reference codes written in one cell ('01-072-0156; 01-085-0794')."""
    return list(dict.fromkeys(CODE_RE.findall(str(text))))


def looks_coded(values):
    """True for a column whose filled cells are reference codes (the 'Matched by' column of a peak list)."""
    vals = [str(v).strip() for v in values if v is not None and str(v).strip() and str(v).strip().lower() not in ("nan", "none", "-")]
    return bool(vals) and sum(1 for v in vals if codes_in(v)) >= 0.6 * len(vals)


def clean(name):
    """'Portlandite, syn' -> 'Portlandite'; 'Quartz low' -> 'Quartz'. The name as the file gives it otherwise."""
    s = re.sub(r"[_\s]+", " ", str(name)).strip()
    s = re.sub(r"(?i)\s*,?\s*\bsyn(thetic)?\b\.?", "", s).strip(" ,;")
    s = re.sub(r"(?i)\s*,?\s+low$", "", s).strip(" ,;")              # 'Quartz low' is quartz as it is at room temperature
    s = re.sub(r"\$-?", "", s)                                   # the markup of the database for Greek letters
    if s and (s.islower() or s.isupper()) and len(s) > 3: s = s[:1].upper() + s[1:].lower()
    return s


def mineral(compound):
    """The mineral of a compound name when there is only one ('Calcium Hydroxide' -> 'Portlandite'), else None."""
    s = re.sub(r"\s+", " ", str(compound)).strip().lower().replace("sulphate", "sulfate")
    for pat, m in COMPOUND_MINERAL:
        if re.search(pat, s): return m
    return None


def _norm(c):
    return re.sub(r"[^a-z0-9]", "", str(c).lower())


def table_names(df):
    """{code: {"name", "compound", "formula"}} when the table is a pattern list, else None. A pattern list has a column
    of reference codes and a column of names; it has no column of peak positions."""
    try:
        cols = list(df.columns); n = {c: _norm(c) for c in cols}
        if any(n[c].startswith(("pos", "2theta", "2th", "twotheta", "angle", "dspacing", "height", "fwhm")) for c in cols): return None      # a peak list ('Displ. [°2Th.]' of a pattern list is not a position column)
        code = next((c for c in cols if n[c] in ("refcode", "referencecode", "refcodes", "pdf", "pdfnumber", "pdfno", "pdfcode", "card", "cardnumber", "icddcode", "code", "patterncode", "reference")), None)
        if code is None: code = next((c for c in cols if n[c].startswith(("refcode", "referencecode", "pdfn", "pdfc"))), None)
        if code is None: return None
        mcol = next((c for c in cols if n[c].startswith("mineral")), None)
        ccol = next((c for c in cols if n[c].startswith(("compoundname", "compound", "phasename", "name", "phase", "commonname")) and c not in (code, mcol)), None)
        fcol = next((c for c in cols if n[c].startswith(("chemformula", "chemicalformula", "formula")) and c not in (code, mcol, ccol)), None)
        if mcol is None and ccol is None: return None
        out = {}
        for i in range(len(df)):
            raw = str(df[code].iloc[i]).strip(); found = codes_in(raw) or ([SHORT_RE.match(raw).group(1)] if SHORT_RE.match(raw) else [])
            if not found: continue
            val = lambda c: "" if c is None or df[c].iloc[i] is None or str(df[c].iloc[i]).strip().lower() in ("", "nan", "none", "-") else str(df[c].iloc[i]).strip()
            mn, cn, fm = clean(val(mcol)), clean(val(ccol)), val(fcol)
            name = mn or mineral(cn) or cn or re.sub(r"\s+", "", fm)
            if name: out[found[0]] = {"name": name, "compound": cn, "formula": fm, "from_compound": bool(not mn and mineral(cn))}
        return out if out and len(out) >= 0.6 * len(df) else None
    except Exception:
        return None


CODE_HEADS = ("refcode", "referencecode", "pdfnumber", "pdfno", "pdfcode", "icddcode", "patterncode", "cardnumber")
NAME_HEADS = ("compoundname", "mineralname", "phasename", "compound", "mineral")


def _cells(line):
    return [_norm(c) for c in re.split(r"[,;\t|]", line)]


def split_text(text):
    """A text file that holds a pattern list AND another table (the peak list), one under the other:
    [("data" | "patterns", text of that table), ...] in the order of the file, else None. The pattern list starts at
    the line with its column headers (Ref. Code ... Compound Name) and ends at an empty line or at the header line of
    the next table (a line with a position column)."""
    if len(text) > 3_000_000: return None
    low = text.lower()
    if "code" not in low or not any(k in low for k in ("compound", "mineral", "phase name")): return None
    lines = text.splitlines(); start = None
    for i, ln in enumerate(lines):
        c = _cells(ln)
        if any(x.startswith(CODE_HEADS) for x in c) and any(x.startswith(NAME_HEADS) for x in c): start = i; break
    if start is None: return None
    is_pos_head = lambda ln: any(x.startswith(("pos2", "pos", "2theta", "2th", "angle")) for x in _cells(ln)) and not re.search(r"\d\.\d", ln)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if not lines[j].strip() or is_pos_head(lines[j]): end = j; break
    def body(p_):                                     # without the title lines above a table ('Peak List') and the empty lines around it
        p_ = [l for l in p_ if l.strip()]
        while p_ and len([c for c in re.split(r"[,;\t|]", p_[0]) if c.strip()]) < 2: p_ = p_[1:]
        while p_ and len([c for c in re.split(r"[,;\t|]", p_[-1]) if c.strip()]) < 2: p_ = p_[:-1]
        return p_
    parts = [("data", body(lines[:start])), ("patterns", body(lines[start:end])), ("data", body(lines[end:]))]
    out = [(k, "\n".join(p_)) for k, p_ in parts if len(p_) >= 2]
    return out if len(out) >= 2 and any(k == "data" for k, _ in out) else None


def repair_text(text):
    """A pattern list written without quotes has rows with more cells than its header when a name holds the separator
    ('01-072-0156,62,Portlandite, syn,0.0,...'). Those rows were dropped on reading - and their patterns stayed
    numbers. The surplus cells are given back to the name column. Returns the text (unchanged when nothing is wrong)."""
    import csv, io
    if len(text) > 3_000_000: return text
    lines = text.splitlines(); start = None
    for i, ln in enumerate(lines):
        c = _cells(ln)
        if any(x.startswith(CODE_HEADS) for x in c) and any(x.startswith(NAME_HEADS) for x in c): start = i; break
    if start is None: return text
    sep = max(",;\t|", key=lambda ch: lines[start].count(ch)); head = next(csv.reader([lines[start]], delimiter=sep)); hn = [_norm(h) for h in head]
    k = next((j for j, h in enumerate(hn) if h.startswith(NAME_HEADS)), None)
    if k is None: return text
    out = list(lines); changed = False
    for j in range(start + 1, len(lines)):
        if not lines[j].strip(): break
        try: row = next(csv.reader([lines[j]], delimiter=sep))
        except Exception: continue
        extra = len(row) - len(head)
        if extra <= 0 or not codes_in(lines[j]): continue
        row = row[:k] + [(sep + " ").join(x.strip() for x in row[k:k + extra + 1])] + row[k + extra + 1:]
        buf = io.StringIO(); csv.writer(buf, delimiter=sep, lineterminator="").writerow(row); out[j] = buf.getvalue(); changed = True
    return "\n".join(out) if changed else text


def _file():
    try:
        import private_store
        return os.path.join(private_store.private_dir(make=True), "pdf_names.json")
    except Exception:
        return None


def _load():
    if _LOADED[0]: return
    _LOADED[0] = True
    try:
        f = _file()
        if f and os.path.isfile(f):
            for e in json.load(open(f, encoding="utf-8")):
                NAMES.setdefault(key(e["code"]), dict(e, source=e.get("source") or "remembered from an earlier pattern list"))
    except Exception: pass


def register(names, source=""):
    """Take the names of a pattern list in (they replace older ones of the same code) and remember them for later
    sessions - a peak list read without its pattern list then still gets its names. Returns the number of codes."""
    _load()
    for code, e in (names or {}).items():
        NAMES[key(code)] = dict(e, code=code, source=source)
    try:
        f = _file()
        if f: json.dump([{k: v for k, v in e.items() if k in ("code", "name", "compound", "formula")} for e in NAMES.values()], open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception: pass
    return len(names or {})


def name_of(code):
    """The name of a reference code, or None when no pattern list gave one."""
    _load(); e = NAMES.get(key(code))
    return e["name"] if e else None


def forget():
    """For tests: nothing known."""
    NAMES.clear(); _LOADED[0] = True

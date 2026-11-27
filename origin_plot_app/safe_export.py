"""safe_export.py - text that leaves the app in a spreadsheet file (CSV, TSV, XLSX) must stay text.

A spreadsheet program reads a cell that begins with  =  +  -  @  (or a tab / carriage return in front of one) as a
formula. A column name or a label that came out of somebody else's file could so become something that is calculated,
or that asks to start another program, when the exported file is opened. escape_cell() puts a single quote in front of
such TEXT, which every spreadsheet program then shows as plain text.

Numbers are never touched:
  * a real number (int, float, numpy number, date, None, NaN) is returned as it is, with its type;
  * a text that IS a number ("-1.5", "+3", "-2.5e-3", "-1,5") is returned as it is: it cannot call anything, and a
    quote in front of it would turn measured values into text;
  * a text of signs only ("-", "--", "+") is returned as it is: the usual way to write "no value".

    escape_cell(value)   one cell
    safe_frame(df)       a table: its text columns and its column names, the numeric columns and their dtype unchanged

Standard library + pandas (pandas is loaded only by safe_frame); importable without Qt.
"""
import re

FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
_NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?\s*%?$")
_SIGNS_ONLY_RE = re.compile(r"^[+\-\s]*$")


def is_number_text(text):
    """True when the text is nothing but a number (optionally with a sign, a decimal point or comma, an exponent, %)."""
    t = str(text).strip()
    if not t: return False
    if _NUMBER_RE.match(t): return True
    try: float(t); return True                      # also inf / nan with a sign
    except ValueError: return False


def needs_escape(value):
    """True when this cell is TEXT that a spreadsheet program would read as a formula."""
    if not isinstance(value, str) or not value: return False
    if not value.startswith(FORMULA_START): return False
    if _SIGNS_ONLY_RE.match(value): return False
    return not is_number_text(value)


def escape_cell(value):
    """The value as it may be written into a spreadsheet file: a text that would be read as a formula gets a single
    quote in front; everything else (numbers, numeric text, None, dates) is returned unchanged."""
    return "'" + value if needs_escape(value) else value


def _escape_label(label):
    if isinstance(label, tuple): return tuple(escape_cell(x) for x in label)
    return escape_cell(label)


def safe_frame(df):
    """A table for export: text cells and column names that would be read as formulas are neutralised (see
    escape_cell). Numeric columns are not looked at and keep their dtype; a text column keeps every cell that needs no
    change. The table given is not changed; when nothing needs a change it is returned as it is."""
    import pandas as pd
    if df is None or not hasattr(df, "columns"): return df
    out = None
    for i in range(df.shape[1]):
        s = df.iloc[:, i]
        if not (pd.api.types.is_object_dtype(s.dtype) or pd.api.types.is_string_dtype(s.dtype)): continue   # numbers, dates, booleans: untouched
        try: hit = s.map(needs_escape)
        except Exception: continue
        hit = hit.fillna(False).astype(bool)
        if not bool(hit.any()): continue
        new = s.astype(object).where(~hit, s.astype(object).map(escape_cell))
        try: new = new.astype(s.dtype)                                                                    # a 'str' column stays a 'str' column
        except Exception: pass
        if out is None: out = df.copy()
        out.isetitem(i, new)
    labels = list(df.columns); safe = [_escape_label(c) for c in labels]
    if any(a is not b and a != b for a, b in zip(safe, labels)):
        if out is None: out = df.copy()
        out.columns = pd.MultiIndex.from_tuples(safe, names=df.columns.names) if isinstance(df.columns, pd.MultiIndex) else pd.Index(safe, name=df.columns.name)
    return df if out is None else out

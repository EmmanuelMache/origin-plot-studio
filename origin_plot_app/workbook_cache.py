"""One parse of an Excel workbook, shared by every part of the app that needs its sheets.

A workbook of figures is read by the figure recipes, by each of its composed figures every time one is drawn again, by
the template gallery and by the project workbench. Each used to parse the whole file for itself: a 3 MB workbook with
50 sheets takes several seconds per parse, so opening it took a minute and every redraw of one of its figures stopped
the window. Here it is parsed once per version of the file (its time stamp and size) and handed out as copies."""
import os
import threading

KEEP = 4                              # workbooks kept; the oldest goes first
_BOOKS = {}                           # absolute path -> ((mtime_ns, size), {sheet: DataFrame})
_GUARD = threading.Lock()
_PARSING = {}                         # absolute path -> lock: a second caller waits for the parse in progress instead of parsing again


def _stamp(path):
    try:
        st = os.stat(path); return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def sheets(path):
    """{sheet: DataFrame}, exactly what pandas.read_excel(path, sheet_name=None) gives. Every caller gets its own
    copies of the frames: nothing a caller does to a sheet reaches the kept ones or another caller."""
    import pandas as pd
    key = os.path.abspath(str(path)); stamp = _stamp(key)
    if stamp is None: return pd.read_excel(path, sheet_name=None)          # not a file on the disk: read it as before, the error (if any) is pandas' own
    with _GUARD: lock = _PARSING.setdefault(key, threading.Lock())
    with lock:
        with _GUARD: hit = _BOOKS.get(key)
        if hit is None or hit[0] != stamp:
            book = pd.read_excel(path, sheet_name=None)
            with _GUARD:
                _BOOKS.pop(key, None); _BOOKS[key] = (stamp, book)
                while len(_BOOKS) > KEEP: _BOOKS.pop(next(iter(_BOOKS)))
        else:
            book = hit[1]
    return {name: frame.copy() for name, frame in book.items()}


def forget(path=None):
    """Drop the kept parse of one workbook, or of all (after the file was written by the app itself)."""
    with _GUARD:
        if path is None: _BOOKS.clear()
        else: _BOOKS.pop(os.path.abspath(str(path)), None)

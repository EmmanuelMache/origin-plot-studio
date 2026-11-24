"""The user's tables -> the data bundle a template draws.

The rule of the plain sheet: row 1 = headers, column 1 = x (or the category), every other column = one series.
Each template has an example bundle (its demo). `bundle()` fills a bundle of the same shape from the user's tables and
returns, beside it, the mapping (role -> where it came from) so that the app can show it and the user can change it.
Nothing is invented: decorations that are not in the file (zones, labels, reference lines, regimes) stay empty, and a
template that needs something the file does not have says what it needs (NeedData)."""
import re
import numpy as np
import pandas as pd


class NeedData(Exception):
    """The file cannot fill this template; the message says what the template needs."""


ERR_RE = re.compile(r"(^|[^a-z])(sd|std|stdev|err|error|se|sem|±|\+/-|unc|uncertainty)([^a-z]|$)", re.I)
CUM_RE = re.compile(r"cum|total|integral|passing", re.I)


class Table:
    """One sheet of one file: name, the frame, and what its columns are."""
    def __init__(self, name, df, order=None):
        self.name = str(name); df = df.dropna(how="all").dropna(axis=1, how="all"); self.df = df
        self.cols = [str(c) for c in df.columns]; df.columns = self.cols
        num = df.apply(pd.to_numeric, errors="coerce")
        self.numeric = [c for c in self.cols if num[c].notna().mean() >= 0.8 and num[c].notna().sum() >= 1]
        self.text = [c for c in self.cols if c not in self.numeric]
        self.num = num
        if order: self.reorder(order)

    def reorder(self, order):
        """order: the columns in the order the user wants them used (the first numeric one is x)."""
        keep = [c for c in order if c in self.cols]
        self.cols = keep + [c for c in self.cols if c not in keep]
        self.numeric = [c for c in self.cols if c in self.numeric]; self.text = [c for c in self.cols if c in self.text]

    def arr(self, c): return self.num[c].to_numpy(dtype=float)
    @property
    def x(self): return self.numeric[0] if self.numeric else None
    @property
    def ys(self):
        """The series columns: numeric, not x, not an error column."""
        return [c for c in self.numeric[1:] if not ERR_RE.search(c)]
    def err_of(self, c):
        i = self.cols.index(c)
        nxt = self.cols[i + 1] if i + 1 < len(self.cols) else None
        return nxt if nxt in self.numeric and ERR_RE.search(nxt) else None
    @property
    def cat(self): return self.text[0] if self.text else None


def short_name(header):
    """Only unit tails are trimmed from a header; nothing is invented."""
    h = str(header)
    for tail in (" (offset, counts)", " (counts)", " (wt.%)", " (wt%)", " (a.u.)"):
        if h.endswith(tail): h = h[: -len(tail)]
    return h


def _is_arr(v): return isinstance(v, np.ndarray)
def _nums(v): return isinstance(v, (list, tuple)) and len(v) > 0 and all(isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool) for x in v)
def _empty(v):
    if isinstance(v, bool): return False
    if isinstance(v, dict): return {}
    if isinstance(v, (list, tuple)): return []
    if isinstance(v, str): return ""
    return None

KEEP = ("wavelength", "window", "scale_um", "px_um")           # numbers of the method, not of the sample: the template's default
DECOR = ("zones", "regions", "refs", "labels", "key", "bands", "shade", "ref_lines", "events", "regimes", "break", "targets",
         "ticks", "peaks", "annotations", "rwp", "markers", "dvals", "note", "missing_text", "title", "name")


def _need(n, t, what):
    if len(t.numeric) < n: raise NeedData(f"needs {what} ({n} numeric columns); this table has {len(t.numeric)}")


def _series(tables, ex, mp, with_x=True):
    out = []; many = len(tables) > 1
    for t in tables:
        _need(2, t, "an x column and at least one series column")
        x = t.arr(t.x)
        for i, c in enumerate(t.ys):
            y = t.arr(c); ok = np.isfinite(x) & np.isfinite(y)
            s = {"name": (f"{t.name}: " if many and len(t.ys) > 1 else "") + (t.name if many and len(t.ys) == 1 else short_name(c)), "y": y[ok]}
            if with_x: s["x"] = x[ok]
            if "yerr" in ex:
                e = t.err_of(c); s["yerr"] = t.arr(e)[ok] if e else np.zeros(int(ok.sum()))
                mp.append((f"error of {c}", e or "none in the file (drawn without error bars)"))
            if "cum" in ex:
                xs, ys = s["y"] * 0 + x[ok], y[ok]
                s["cum"] = np.concatenate([[0.0], np.cumsum(0.5 * (ys[1:] + ys[:-1]) * np.diff(xs))]) if len(ys) > 1 else ys * 0
            if "param" in ex:
                m = re.search(r"-?\d+(?:\.\d+)?", c); s["param"] = float(m.group(0)) if m else float(i)
            out.append(s)
        mp.append((f"x ({t.name})", t.x)); mp.append((f"series ({t.name})", ", ".join(t.ys)))
    if not out: raise NeedData("needs at least one numeric series column beside x")
    if "cum" in ex: mp.append(("cumulative curve", "calculated: integral of each series over x (trapezoid rule)"))
    return out


def _rietveld(t, mp):
    _need(3, t, "x, observed and calculated")
    c = t.numeric; d = {"x": t.arr(c[0]), "obs": t.arr(c[1]), "calc": t.arr(c[2]), "name": t.name, "rwp": None, "ticks": {}, "x_label": c[0], "y_label": c[1]}
    d["diff"] = t.arr(c[3]) if len(c) > 3 else d["obs"] - d["calc"]
    mp += [("x", c[0]), ("observed", c[1]), ("calculated", c[2]), ("difference", c[3] if len(c) > 3 else "calculated: observed - calculated")]
    return d


def _category(t, ex, mp):
    if t.cat is None:
        if len(t.numeric) < 2: raise NeedData("needs a column of categories and at least one value column")
        cats = [f"{v:g}" for v in t.arr(t.numeric[0])]; vals = t.ys; mp.append(("categories", t.numeric[0]))
    else:
        cats = [str(v) for v in t.df[t.cat]]; vals = [c for c in t.numeric if not ERR_RE.search(c)]; mp.append(("categories", t.cat))
    if not vals: raise NeedData("needs at least one numeric value column")
    V = np.column_stack([t.arr(c) for c in vals]); mp.append(("groups", ", ".join(vals)))
    E = np.column_stack([t.arr(t.err_of(c)) if t.err_of(c) else np.zeros(len(cats)) for c in vals])
    return cats, [short_name(c) for c in vals], V, E


def bundle(template, tables, overrides=None):
    """(bundle, mapping). tables: list of Table. overrides: {key: value} set by the user (labels, zones ...)."""
    if not tables: raise NeedData("no data: tick a file first")
    ex = template.demo(); t = tables[0]; mp = []; d = {}
    keys = list(ex)
    k_set = set(keys)
    # ---- whole-shape rules
    if "items" in k_set:                                                    # grid of fits: one per table
        d["items"] = [_rietveld(x, mp) for x in tables]
    elif {"obs", "calc"} <= k_set:
        d.update(_rietveld(t, mp))
    elif {"obs", "fit", "components"} <= k_set:
        _need(3, t, "x, observed, fit, and one column per component"); c = t.numeric
        d.update(x=t.arr(c[0]), obs=t.arr(c[1]), fit=t.arr(c[2])); comps = []
        for n in c[3:]:
            y = t.arr(n); i = int(np.nanargmax(np.abs(y))) if np.isfinite(y).any() else 0; h = float(y[i]); half = np.where(np.abs(y) >= abs(h) / 2)[0]
            comps.append({"name": short_name(n), "c": float(d["x"][i]), "h": h, "w": float(abs(d["x"][half[-1]] - d["x"][half[0]])) if len(half) > 1 else 0.0, "y": y})
        d["components"] = comps; mp += [("x", c[0]), ("observed", c[1]), ("fit", c[2]), ("components", ", ".join(c[3:]) or "none")]
    elif "samples" in k_set:                                                # thermal: T + mass per sample
        ss = []
        for x in tables:
            _need(2, x, "temperature and mass"); T = x.arr(x.x)
            for c in ([x.ys[0]] if "ms" in k_set else x.ys):
                ss.append({"name": x.name if len(tables) > 1 and len(x.ys) == 1 else short_name(c) if len(x.ys) > 1 else x.name, "T": T, "mass": x.arr(c)})
            mp += [(f"temperature ({x.name})", x.x), (f"mass ({x.name})", ", ".join(x.ys[:1] if "ms" in k_set else x.ys))]
        d["samples"] = ss
        if "ms" in k_set: d["ms"] = [{"name": short_name(c), "y": t.arr(c)} for c in t.ys[1:]]; mp.append(("ion currents", ", ".join(t.ys[1:]) or "none"))
    elif "panels" in k_set:
        exs = ex["panels"][0]["series"][0]
        if len(tables) > 1: d["panels"] = [{"title": x.name, "series": _series([x], exs, mp)} for x in tables]
        else: d["panels"] = [{"title": "", "series": _series([t], exs, mp)}]
    elif "series" in k_set and isinstance(ex["series"], list) and ex["series"] and isinstance(ex["series"][0], dict):
        exs = ex["series"][0]
        if "x" in k_set and _is_arr(ex.get("x")):                         # stacked area: one x, series of y
            d["x"] = t.arr(t.x); d["series"] = [{"name": short_name(c), "y": t.arr(c)} for c in t.ys]; mp += [("x", t.x), ("series", ", ".join(t.ys))]
            if not d["series"]: raise NeedData("needs at least one series column beside x")
        elif "sticks" in k_set:                                            # pattern(s) from the tables of curves; reference positions from a table with a name column
            lists = [x for x in tables if x.cat is not None and x.numeric]; curves = [x for x in tables if x not in lists] or tables[:1]
            d["series"] = _series(curves, exs, mp); st_ = {}
            for x in lists:
                for nm_, v_ in zip(x.df[x.cat], x.arr(x.numeric[0])):
                    if np.isfinite(v_): st_.setdefault(str(nm_), []).append(float(v_))
                mp.append((f"reference positions ({x.name})", f"{x.cat} + {x.numeric[0]}"))
            d["sticks"] = st_
            if not lists: mp.append(("reference positions", "none in the ticked files (tick a peak list as well: a name column and a position column)"))
        else:
            d["series"] = _series(tables, exs, mp)
        if "series2" in k_set:
            if len(d["series"]) < 2: raise NeedData("needs two series columns (left and right axis)")
            d["series2"] = [d["series"].pop()]; mp.append(("right axis", d["series2"][0]["name"]))
        if "dvals" in k_set:
            dv = []
            for s in d["series"]:
                cum = s["cum"] / s["cum"][-1] * 100 if len(s["cum"]) and s["cum"][-1] else s["cum"]
                dv.append([float(np.interp(q, cum, s["x"])) for q in (10, 50, 90)])
            d["dvals"] = dv; mp.append(("d10 / d50 / d90", "calculated from the cumulative curve"))
    elif "categories" in k_set:
        cats, groups, V, E = _category(t, ex, mp); d["categories"] = cats
        if _is_arr(ex.get("values")) and ex["values"].ndim == 2 or isinstance(ex.get("values"), np.ndarray) and "groups" in k_set:
            d["groups"] = groups; d["values"] = V
            if "errors" in k_set: d["errors"] = E
        else:                                                               # one value per category (and a second one)
            d["values"] = V[:, 0]
            if "values2" in k_set:
                if V.shape[1] < 2: raise NeedData("needs two value columns")
                d["values2"] = V[:, 1]
            if "groups" in k_set: d["groups"] = groups
        if "names" in k_set: d["names"] = groups[:2][::-1] if "values2" in k_set else groups
        if "markers" in k_set and V.shape[1] > 1 and overrides and overrides.get("_markers_last"):
            d["markers"] = {"name": groups[-1], "values": V[:, -1]}; d["groups"] = groups[:-1]; d["values"] = V[:, :-1]
    elif "points" in k_set:
        e0 = ex["points"][0]
        if isinstance(e0, dict) and _is_arr(e0.get("x")):
            d["points"] = [{"name": s["name"], "x": s["x"], "y": s["y"]} for s in _series(tables, {}, mp)]
        elif isinstance(e0, dict) and {"a", "b", "c"} <= set(e0):
            _need(3, t, "three components"); c = t.numeric[:3]
            nm = [str(v) for v in t.df[t.cat]] if t.cat else [str(i + 1) for i in range(len(t.df))]
            d["points"] = [{"name": n, "a": a, "b": b, "c": cc} for n, a, b, cc in zip(nm, t.arr(c[0]), t.arr(c[1]), t.arr(c[2]))]
            d["apexes"] = [short_name(x) for x in c]; mp += [("components (apexes)", ", ".join(c)), ("point names", t.cat or "row numbers")]
        else:
            _need(2, t, "two numeric columns"); c = t.numeric[:2]; d["points"] = [[float(a), float(b)] for a, b in zip(t.arr(c[0]), t.arr(c[1]))]; mp.append(("points", ", ".join(c)))
    elif "groups" in k_set and isinstance(ex["groups"], list) and ex["groups"] and isinstance(ex["groups"][0], dict):
        e0 = ex["groups"][0]
        if "values" in e0:
            cs = t.numeric if t.cat is None else t.numeric
            if t.cat is not None and len(t.numeric) == 1:                   # long table: group | value
                g = t.df.groupby(t.cat, sort=False)[t.numeric[0]]; d["groups"] = [{"name": str(k), "values": pd.to_numeric(v, errors="coerce").dropna().to_numpy()} for k, v in g]
                mp += [("group", t.cat), ("values", t.numeric[0])]
            else:
                if not cs: raise NeedData("needs one numeric column per group")
                d["groups"] = [{"name": short_name(c), "values": t.arr(c)[np.isfinite(t.arr(c))]} for c in cs]; mp.append(("groups (one column each)", ", ".join(cs)))
        else:                                                               # survival: time, event (, group)
            _need(2, t, "time and event (1 = event, 0 = censored)"); tc, ec = t.numeric[:2]
            if t.cat: d["groups"] = [{"name": str(k), "t": pd.to_numeric(g[tc], errors="coerce").to_numpy(), "event": pd.to_numeric(g[ec], errors="coerce").to_numpy()} for k, g in t.df.groupby(t.cat, sort=False)]
            else: d["groups"] = [{"name": t.name, "t": t.arr(tc), "event": t.arr(ec)}]
            mp += [("time", tc), ("event", ec), ("group", t.cat or "none")]
    elif "matrix" in k_set:
        _need(2, t, "two or more numeric columns"); d["labels"] = [short_name(c) for c in t.numeric]; d["matrix"] = np.corrcoef(np.column_stack([t.arr(c) for c in t.numeric]), rowvar=False)
        mp.append(("variables", ", ".join(t.numeric))); mp.append(("matrix", "calculated: Pearson correlation of the columns"))
    elif "X" in k_set:
        _need(2, t, "two or more numeric columns"); M = np.column_stack([t.arr(c) for c in t.numeric]); ok = np.isfinite(M).all(axis=1)
        d["X"] = M[ok]; d["vars"] = [short_name(c) for c in t.numeric]; d["groups"] = [str(v) for v in t.df[t.cat][ok]] if t.cat else [""] * int(ok.sum())
        mp += [("variables", ", ".join(t.numeric)), ("group", t.cat or "none")]
    elif "z" in k_set and _is_arr(ex.get("z")) and ex["z"].ndim == 2:
        hx = pd.to_numeric(pd.Series(t.cols[1:]), errors="coerce")
        if hx.notna().all() and len(hx) >= 2:                               # first column = y, numeric headers = x
            d["x"] = hx.to_numpy(); d["y"] = t.arr(t.cols[0]); d["z"] = np.column_stack([t.arr(c) for c in t.cols[1:]]); mp += [("x", "the headers"), ("y", t.cols[0]), ("z", "the cells")]
        else:                                                               # x, then one column per pattern: y = column number
            _need(3, t, "x and two or more columns"); d["x"] = t.arr(t.x); d["z"] = np.vstack([t.arr(c) for c in t.ys]); d["y"] = np.arange(len(t.ys), dtype=float)
            mp += [("x", t.x), ("rows of the map", ", ".join(t.ys))]
    elif "steps" in k_set:
        if not t.cat or not t.numeric: raise NeedData("needs a column of step names and a column of values")
        d["steps"] = [(str(a), float(b)) for a, b in zip(t.df[t.cat], t.arr(t.numeric[0]))]; mp += [("step", t.cat), ("value", t.numeric[0])]
    elif "flows" in k_set:
        if len(t.text) < 2 or not t.numeric: raise NeedData("needs source, target and value columns")
        d["flows"] = [(str(a), str(b), float(v)) for a, b, v in zip(t.df[t.text[0]], t.df[t.text[1]], t.arr(t.numeric[0]))]; mp += [("source", t.text[0]), ("target", t.text[1]), ("value", t.numeric[0])]
    elif "params" in k_set:
        if not t.cat: raise NeedData("needs a column of parameter names, then low and high")
        _need(2, t, "low and high"); d["params"] = [str(v) for v in t.df[t.cat]]; d["low"] = t.arr(t.numeric[0]); d["high"] = t.arr(t.numeric[1])
        d["base"] = float(t.arr(t.numeric[2])[0]) if len(t.numeric) > 2 else float(np.nanmean((d["low"] + d["high"]) / 2)); mp += [("parameter", t.cat), ("low", t.numeric[0]), ("high", t.numeric[1])]
    elif "images" in k_set:
        raise NeedData("needs image files (TIFF or PNG), not a table")
    elif "curves" in k_set:
        _need(2, t, "temperature and one conversion column per heating rate"); T = t.arr(t.x); cs = []
        for i, c in enumerate(t.ys):
            m = re.search(r"\d+(?:\.\d+)?", c); cs.append({"beta": float(m.group(0)) if m else i + 1, "T": T, "alpha": t.arr(c)})
        d["curves"] = cs; mp += [("temperature", t.x), ("conversion per heating rate", ", ".join(t.ys))]
    else:                                                                   # arrays by position: the template's roles in order
        arrs = [k for k in keys if _is_arr(ex[k]) and ex[k].ndim == 1]
        lists = [k for k in keys if isinstance(ex[k], list) and ex[k] and isinstance(ex[k][0], dict) and any(_is_arr(v) for v in ex[k][0].values())]
        _need(len(arrs) + (1 if lists else 0), t, "the columns " + ", ".join(arrs + lists))
        for k, c in zip(arrs, t.numeric): d[k] = t.arr(c); mp.append((k, c))
        rest = t.numeric[len(arrs):]
        for k in lists:
            e0 = ex[k][0]; ak = [a for a, v in e0.items() if _is_arr(v)]
            items = []
            for c in [c for c in rest if not ERR_RE.search(c)]:
                it = {"name": short_name(c), ak[0]: t.arr(c)}
                for a in ak[1:]: e = t.err_of(c); it[a] = t.arr(e) if e else np.zeros(len(t.df))
                items.append(it)
            d[k] = items; mp.append((k, ", ".join(rest) or "none"))
    # ---- labels and decorations
    for k in keys:
        if k in d: continue
        v = ex[k]
        if k == "x_label": d[k] = (t.x or t.cat or "") if not d.get("categories") else (t.cat or "")
        elif k in ("y_label", "y2_label", "z_label", "s_label", "depth_label", "param_label", "unit"):
            ys = t.ys
            d[k] = (short_name(ys[0]) if len(ys) == 1 and k == "y_label" else t.numeric[2] if k in ("s_label", "z_label") and len(t.numeric) > 2 else "")
            if k == "depth_label": d[k] = t.x or ""
        elif k in KEEP: d[k] = v
        elif k == "names": d[k] = [short_name(c) for c in t.numeric[:2]]
        elif k == "apexes": d[k] = [short_name(c) for c in t.numeric[:3]]
        else: d[k] = _empty(v)
    for k, v in (overrides or {}).items():
        if not k.startswith("_"): d[k] = v
    ren = (overrides or {}).get("_renames") or {}
    if ren:                                  # names typed by the user for the graph; the file keeps its headers
        def nm(o):
            if isinstance(o, dict):
                for key in ("name", "title"):
                    if isinstance(o.get(key), str) and o[key] in ren: o[key] = ren[o[key]]
                for v_ in o.values(): nm(v_)
            elif isinstance(o, list):
                for i_, v_ in enumerate(o):
                    if isinstance(v_, str) and v_ in ren: o[i_] = ren[v_]
                    else: nm(v_)
        nm(d); mp.append(("names on the graph", "; ".join(f"{a_} shown as {b_}" for a_, b_ in ren.items())))
    return d, mp


def read_tables(path, sheet=None, max_rows=200000):
    """The sheets of a file as Table objects (a CSV / text file is one table). The file is only read."""
    import os
    low = path.lower(); name = os.path.splitext(os.path.basename(path))[0]; out = []
    if low.endswith((".xlsx", ".xlsm", ".xls")):
        book = pd.read_excel(path, sheet_name=None, nrows=max_rows)
        pick = [sheet] if sheet and sheet in book else ([s for s in book if s.strip().lower() == "data"] or list(book))
        for s in pick:
            df = book[s]
            if df.shape[1] >= 1 and len(df): out.append(Table(name if len(pick) == 1 else f"{name} [{s}]", df))
    else:
        df = None
        for kw in (dict(sep=None, engine="python"), dict(sep=r"\s+", engine="python"), dict(sep=";", decimal=",")):
            try:
                df = pd.read_csv(path, nrows=max_rows, comment="#", **kw)
                if df.shape[1] >= 2: break
            except Exception: df = None
        if df is None: raise NeedData("this file could not be read as a table")
        if all(re.fullmatch(r"-?[\d.,eE+-]+", str(c).strip()) for c in df.columns):       # no header row: the first row is data
            df = pd.concat([pd.DataFrame([df.columns], columns=df.columns), df], ignore_index=True); df.columns = ["x"] + [f"y{i}" for i in range(1, df.shape[1])]
        out.append(Table(name, df))
    return out

"""'Draw in Origin like this': the same graph that the app shows, built in Origin from the drawn figure.

The figure of a template (any template, any style, the user's data) is read back object by object and sent to Origin
through the app's Origin driver: one layer per panel or inset at the same place on a page of the same size, the same
axis ranges, scales and reversals, every curve with its colour, width, dash and marker, bars as columns, shaded zones,
texts, panel labels and the legend, with the text sizes of the style in points. The data of every layer goes into its
own worksheet (column A = x, the others y), laid out the way that layer needs it.

Where Origin has no equal, the closest is used and `differences` says so in one line each. Nothing is guessed: only
what is on the figure is sent.

The same list of commands can be written as a LabTalk script file (.ogs), and - on a computer with Origin - the graph
can be stored as an Origin graph template (.otpu) beside it."""
import os, re
import numpy as np
from matplotlib import colors as mcolors
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.container import BarContainer
from matplotlib.collections import PathCollection, PolyCollection, QuadMesh, LineCollection
from matplotlib.image import AxesImage

MARKERS = {"o": 2, "s": 1, "^": 3, "v": 4, "D": 5, "d": 5, "+": 6, "x": 7, "*": 8, "P": 6, "X": 7, "<": 3, ">": 3, "p": 5, "h": 2, ".": 2, "|": 10, "_": 9}   # Origin symbol shapes
DASHES = {"-": 0, "--": 1, ":": 2, "-.": 3}


def _rgb(c, alpha_bg=None):
    try: r, g, b, a = mcolors.to_rgba(c)
    except Exception: r, g, b, a = 0, 0, 0, 1
    if a < 1:                                           # Origin gets the colour as it looks on white
        r, g, b = (1 - a) + a * r, (1 - a) + a * g, (1 - a) + a * b
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def _otext(s):
    """matplotlib text -> Origin text: $_{2}$ and $^{-1}$ become subscripts and superscripts; plain text stays."""
    s = str(s)
    def math(m):
        t = m.group(1)
        t = re.sub(r"\^\{([^{}]*)\}", r"\\+(\1)", t); t = re.sub(r"_\{([^{}]*)\}", r"\\-(\1)", t)
        t = re.sub(r"\^(.)", r"\\+(\1)", t); t = re.sub(r"_(.)", r"\\-(\1)", t)
        t = t.replace(r"\theta", "θ").replace(r"\alpha", "α").replace(r"\beta", "β").replace(r"\mu", "µ").replace(r"\degree", "°").replace(r"\cdot", "·").replace(r"\,", " ")
        return re.sub(r"\\(mathrm|mathit|mathbf|text)\{([^{}]*)\}", r"\2", t)
    s = re.sub(r"\$([^$]*)\$", math, s)
    return s.replace('"', "'").replace("\n", " ")          # a text of several lines is sent line by line (_text): Origin wrote "\\n" as the letter n


def _marker_colour(ln):
    """The colour a symbol is seen in: its fill, or its edge when it is open."""
    fc = ln.get_markerfacecolor()
    if str(fc).lower() in ("none", "white", "w", "#ffffff"): fc = ln.get_markeredgecolor()
    try: return _rgb(fc)
    except Exception: return _rgb(ln.get_color())


def _open_marker(ln):
    return str(ln.get_markerfacecolor()).lower() in ("white", "w", "none", "#ffffff")


def _tick_step(axis, lo, hi, scale):
    """The distance between the numbered ticks of a linear axis (None when they are not evenly spaced)."""
    if scale != "linear": return None
    a, b = min(lo, hi), max(lo, hi); t = np.array([v for v in axis.get_majorticklocs() if a - 1e-9 * (b - a) <= v <= b + 1e-9 * (b - a)], dtype=float)
    if len(t) < 2: return None
    dv = np.diff(np.sort(t))
    return float(dv[0]) if dv[0] > 0 and np.allclose(dv, dv[0], rtol=1e-6, atol=0) else None


def _minor_count(axis, lo, hi):
    """Small ticks between two numbered ones."""
    a, b = min(lo, hi), max(lo, hi)
    try: mj = [v for v in axis.get_majorticklocs() if a <= v <= b]; mn = [v for v in axis.get_minorticklocs() if a <= v <= b]
    except Exception: return 0
    return int(round(len(mn) / max(1, len(mj) - 1))) if len(mj) > 1 and mn else 0


def _is_data(artist, ax):
    try: return artist.get_transform().contains_branch(ax.transData)
    except Exception: return True


def read_figure(fig):
    """The figure as plain data: {"page": (w_in, h_in), "layers": [...], "differences": [...]}.
    A layer: place (left, top, width, height in % of the page), x / y range, log, titles, sizes, curves, bars, zones, texts, legend."""
    fig.canvas.draw(); W, H = fig.get_size_inches(); layers = []; diff = []
    def note(s):
        if s not in diff: diff.append(s)
    twins = {}; axes = []; inv = fig.transFigure.inverted(); legends = []; loose = []
    def fpos(bb):                                                          # a box of the drawing in fractions of the page
        return Bbox(inv.transform(bb.get_points()))
    def legend_of(lg, host):
        """One legend as plain entries: where each stands on the page, its text and what its key looks like."""
        if lg is None or not lg.get_visible(): return
        hs = list(getattr(lg, "legend_handles", None) or getattr(lg, "legendHandles", None) or []); ent = []
        for k, t in enumerate(lg.get_texts()):
            if not t.get_text().strip(): continue
            tb = fpos(t.get_window_extent()); h = hs[k] if k < len(hs) else None; e = {"text": t.get_text(), "x": float(tb.x0), "y": float((tb.y0 + tb.y1) / 2), "pt": float(t.get_fontsize()), "kind": None, "colour": (0, 0, 0), "hatch": "", "marker": None}
            try:
                if h is not None: e["x"] = float(fpos(h.get_window_extent()).x0)
            except Exception: pass
            if isinstance(h, Line2D):
                has_line = h.get_linestyle() not in ("None", "none", "", " "); mk = h.get_marker(); has_mk = mk not in ("None", "none", "", " ", None)
                e["kind"] = "line" if has_line else "marker"; e["marker"] = MARKERS.get(mk, 2) if has_mk else None
                e["colour"] = _rgb(h.get_color()) if has_line else _marker_colour(h)
            elif h is not None and hasattr(h, "get_facecolor"):
                try: fc = h.get_facecolor(); fc = fc[0] if hasattr(fc, "__len__") and len(fc) and hasattr(fc[0], "__len__") else fc; e["colour"] = _rgb(fc)
                except Exception: pass
                e["kind"] = "patch"; e["hatch"] = (h.get_hatch() or "") if hasattr(h, "get_hatch") else ""
            ent.append(e)
        if ent: legends.append({"entries": ent, "host": host, "frame": bool(lg.get_frame_on())})
    def walk(a):
        if not a.get_visible(): return
        axes.append(a)
        for ch in getattr(a, "child_axes", []):
            if type(ch).__name__ == "SecondaryAxis": note("a second axis with its own scale (for example d-spacing on top) is not sent: add it in Origin (Axis dialog > Show the top axis, with a formula)")
            else: walk(ch)                                              # insets (zoom panels inside a graph) are layers of their own
    for ax in fig.axes: walk(ax)
    from matplotlib.transforms import Bbox
    for ax in axes:
        if getattr(ax, "name", "") in ("polar", "3d"):
            note(f"a {'polar' if ax.name == 'polar' else '3D'} panel is sent as a picture of the app's figure (Origin's own {ax.name} graph type is named in the template's Origin hint)"); continue
        if not ax.axison and not (ax.lines or ax.containers or ax.collections or ax.images or ax.patches):
            # a cell that only carries a legend or a note (its axes are switched off): no layer - Origin drew an empty one at 0-1 for it
            legend_of(ax.get_legend(), None)
            for t in ax.texts:
                if t.get_text().strip() and t.get_visible():
                    bb = fpos(t.get_window_extent()); loose.append({"text": t.get_text(), "x": float(bb.x0), "y": float(bb.y1), "pt": float(t.get_fontsize()), "bold": str(t.get_fontweight()) in ("bold", "700", "heavy")})
            continue
        p = Bbox(inv.transform(ax.get_window_extent().get_points())); x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()      # where the panel really is on the page (insets too)
        L = {"left": p.x0 * 100, "top": (1 - p.y1) * 100, "width": p.width * 100, "height": p.height * 100, "x": (x0, x1), "y": (y0, y1),
             "xlog": ax.get_xscale() == "log", "ylog": ax.get_yscale() == "log", "xlabel": ax.get_xlabel(), "ylabel": ax.get_ylabel(),
             "title": ax.get_title(loc="left") or ax.get_title(), "title_bold": True, "curves": [], "bars": [], "zones": [], "texts": [], "vlines": [], "legend": None,
             "xticklabels": any(t.get_visible() and t.get_text() for t in ax.get_xticklabels()), "yticklabels": any(t.get_visible() and t.get_text() for t in ax.get_yticklabels()),
             "tick_pt": (ax.get_xticklabels()[0].get_fontsize() if ax.get_xticklabels() else 8), "label_pt": ax.xaxis.label.get_fontsize(), "title_pt": ax.title.get_fontsize(),
             "axis_pt": ax.spines["left"].get_linewidth() if "left" in ax.spines else 0.8, "frame": all(ax.spines[s].get_visible() for s in ("top", "right") if s in ax.spines),
             "ticks_in": True, "right_axis": False, "cat_labels": None, "ylabel_color": _rgb(ax.yaxis.label.get_color()),
             "xinc": _tick_step(ax.xaxis, x0, x1, ax.get_xscale()), "yinc": _tick_step(ax.yaxis, y0, y1, ax.get_yscale()),
             "xminor": _minor_count(ax.xaxis, x0, x1), "yminor": _minor_count(ax.yaxis, y0, y1), "xlabel_at": None, "ylabel_at": None, "ylabel_rot": 90.0,
             "title_left": bool(ax.get_title(loc="left")), "title_bold": str(ax.title.get_fontweight()) in ("bold", "700", "heavy") or str(getattr(ax, "_left_title", ax.title).get_fontweight()) in ("bold", "700", "heavy")}
        try:                                                              # where the axis titles stand on the page: they are sent as texts at the same place
            if ax.get_xlabel().strip() and ax.xaxis.label.get_visible(): b_ = fpos(ax.xaxis.label.get_window_extent()); L["xlabel_at"] = (float((b_.x0 + b_.x1) / 2), float((b_.y0 + b_.y1) / 2))
            if ax.get_ylabel().strip() and ax.yaxis.label.get_visible(): b_ = fpos(ax.yaxis.label.get_window_extent()); L["ylabel_at"] = (float((b_.x0 + b_.x1) / 2), float((b_.y0 + b_.y1) / 2)); L["ylabel_rot"] = float(ax.yaxis.label.get_rotation())
        except Exception: pass
        key = (round(p.x0, 4), round(p.y0, 4), round(p.width, 4), round(p.height, 4))
        if key in twins: L["right_axis"] = True; L["linked_to"] = twins[key]
        else: twins[key] = len(layers) + 1
        tl = [t.get_text() for t in ax.get_xticklabels()]
        if tl and any(re.search(r"[A-Za-z]", t) for t in tl) and not L["xlog"]:
            L["cat_labels"] = (list(ax.get_xticks()), tl)
        for ln in ax.get_lines():
            x = np.asarray(ln.get_xdata(orig=False), dtype=float); y = np.asarray(ln.get_ydata(orig=False), dtype=float)
            if not ln.get_visible() or len(x) == 0: continue
            if not _is_data(ln, ax):
                if len(x) == 2 and ln.get_transform() == ax.transAxes: continue                 # break marks and such
                tr = ln.get_transform()
                try:                                                                              # axvline / axhline: blended transforms
                    if len(x) == 2 and x[0] == x[1] and tr.contains_branch_seperately(ax.transData)[0]: L["vlines"].append(("v", float(x[0]), _rgb(ln.get_color()), ln.get_linewidth(), ln.get_linestyle())); continue
                    if len(y) == 2 and y[0] == y[1] and tr.contains_branch_seperately(ax.transData)[1]: L["vlines"].append(("h", float(y[0]), _rgb(ln.get_color()), ln.get_linewidth(), ln.get_linestyle())); continue
                except Exception: pass
                continue
            ls = ln.get_linestyle(); mk = ln.get_marker(); has_line = ls not in ("None", "none", "", " "); has_mk = mk not in ("None", "none", "", " ", None)
            lab = ln.get_label(); lab = "" if str(lab).startswith("_") else str(lab)
            L["curves"].append({"x": x, "y": y, "colour": _rgb(ln.get_color()) if has_line else _marker_colour(ln), "width": float(ln.get_linewidth()), "dash": DASHES.get(ls, 0 if has_line else None),
                                "kind": "linesymbol" if has_line and has_mk else "line" if has_line else "scatter", "marker": MARKERS.get(mk, 2) if has_mk else None,
                                "msize": float(ln.get_markersize()), "open": _open_marker(ln) if has_mk else False, "label": lab})
        for c in ax.containers:
            if isinstance(c, BarContainer) and len(c.patches):
                r0 = c.patches[0]; horiz = getattr(c, "orientation", "vertical") == "horizontal"
                if horiz:
                    note("horizontal bars are sent as columns over the category positions (turn the graph in Origin with Graph > Exchange X-Y Axes)")
                    xs = [r.get_y() + r.get_height() / 2 for r in c.patches]; hs = [r.get_width() for r in c.patches]; bs = [r.get_x() for r in c.patches]; w = r0.get_height()
                else:
                    xs = [r.get_x() + r.get_width() / 2 for r in c.patches]; hs = [r.get_height() for r in c.patches]; bs = [r.get_y() for r in c.patches]; w = r0.get_width()
                if any(abs(b) > 1e-12 for b in bs): note("stacked or floating bars are sent as columns of their top values over a column of their base values (set Plot Details > Stack in Origin for a stacked look)")
                cols = {_rgb(r.get_facecolor()) for r in c.patches}
                if len(cols) > 1: note("bars with one colour per bar are sent in the colour of the first bar (Plot Details > Pattern > Fill > Increment)")
                lab = c.get_label(); lab = "" if str(lab).startswith("_") else str(lab)
                L["bars"].append({"x": np.array(xs, dtype=float), "y": np.array(hs, dtype=float) + np.array(bs, dtype=float), "base": np.array(bs, dtype=float), "colour": _rgb(r0.get_facecolor()),
                                  "hatch": r0.get_hatch() or "", "width": float(w), "label": lab})
        for pt in ax.patches:
            if isinstance(pt, Rectangle) and not any(pt in getattr(c, "patches", []) for c in ax.containers) and pt.get_visible():
                tr = pt.get_transform()
                try: bx, by = tr.contains_branch_seperately(ax.transData)
                except Exception: bx = by = False
                fc = pt.get_facecolor()
                if fc[3] == 0: continue
                if bx and not by: L["zones"].append({"x": (pt.get_x(), pt.get_x() + pt.get_width()), "y": None, "colour": _rgb(fc)})
                elif by and not bx: L["zones"].append({"x": None, "y": (pt.get_y(), pt.get_y() + pt.get_height()), "colour": _rgb(fc)})
                elif bx and by: L["zones"].append({"x": (pt.get_x(), pt.get_x() + pt.get_width()), "y": (pt.get_y(), pt.get_y() + pt.get_height()), "colour": _rgb(fc)})
        for col in ax.collections:
            if isinstance(col, PathCollection) and len(col.get_offsets()):
                off = np.asarray(col.get_offsets(), dtype=float); fc = col.get_facecolor(); c0 = _rgb(fc[0]) if len(fc) else (0, 0, 0)
                if len(fc) > 1 and len({tuple(np.round(f, 3)) for f in fc}) > 1: note("points coloured by a value are sent in one colour (map the colour in Origin: Plot Details > Symbol > Colour > Map)")
                sz = col.get_sizes(); lab = col.get_label(); lab = "" if str(lab).startswith("_") else str(lab)
                L["curves"].append({"x": off[:, 0], "y": off[:, 1], "colour": c0, "width": 0.5, "dash": None, "kind": "scatter", "marker": 2, "msize": float(np.sqrt(np.mean(sz))) if len(sz) else 4.0, "open": False, "label": lab})
            elif isinstance(col, PolyCollection) and not isinstance(col, QuadMesh):
                for path in col.get_paths()[:1]:
                    v = path.vertices
                    if len(v) >= 4 and _is_data(col, ax):
                        fc = col.get_facecolor(); n = len(v) // 2
                        L["curves"].append({"x": v[1:n, 0], "y": v[1:n, 1], "colour": _rgb(fc[0]) if len(fc) else (200, 200, 200), "width": 0.5, "dash": 0, "kind": "area", "marker": None, "msize": 0, "open": False, "label": ""})
                        note("a filled band is sent as an area under its upper edge (fill between two curves in Origin: Plot Details > Line > Fill Area Under Curve > Fill to next data plot)")
            elif isinstance(col, QuadMesh): note("a colour map is sent as a picture of the app's figure (use Plot > Contour > Colour Fill in Origin on the worksheet that is sent)")
            elif isinstance(col, LineCollection): note("fine line sets (for example error whiskers or tick rows) are not sent as objects; error bars: add the error column in Origin (Plot Details > Error Bar)")
        for im in ax.images:
            if isinstance(im, AxesImage): note("an image panel is sent as a picture (Origin: Insert > Image From File)")
        for t in ax.texts:
            s = t.get_text()
            if not s.strip() or not t.get_visible(): continue
            x, y = t.get_position(); tr = t.get_transform()
            if tr == ax.transAxes: x = x0 + x * (x1 - x0) if not L["xlog"] else 10 ** (np.log10(x0) + x * (np.log10(x1) - np.log10(x0))); y = y0 + y * (y1 - y0) if not L["ylog"] else 10 ** (np.log10(y0) + y * (np.log10(y1) - np.log10(y0)))
            elif not _is_data(t, ax):
                try:
                    bx, by = tr.contains_branch_seperately(ax.transData)
                    if not bx: x = x0 + x * (x1 - x0)
                    if not by: y = y0 + y * (y1 - y0)
                except Exception: continue
            L["texts"].append({"text": s, "x": float(x), "y": float(y), "pt": float(t.get_fontsize()), "colour": _rgb(t.get_color()), "bold": str(t.get_fontweight()) in ("bold", "700", "heavy"),
                               "rotate": float(t.get_rotation()), "ha": t.get_ha(), "va": t.get_va()})
        lg = ax.get_legend()
        if lg is not None and lg.get_visible():
            bb = lg.get_window_extent().transformed(ax.transAxes.inverted())
            L["legend"] = {"entries": [t.get_text() for t in lg.get_texts()], "x": float(bb.x0), "y": float(bb.y1), "pt": float(lg.get_texts()[0].get_fontsize()) if lg.get_texts() else 7.5, "frame": bool(lg.get_frame_on())}
            legend_of(lg, len(layers) + 1)
        layers.append(L)
    for lg in fig.legends: legend_of(lg, None)                           # a legend of the whole figure (under or beside its panels)
    ftexts = [{"text": t.get_text(), "x": t.get_position()[0], "y": t.get_position()[1], "pt": t.get_fontsize()} for t in fig.texts if t.get_text().strip() and "Illustrative" not in t.get_text()] + loose
    inv = fig.transFigure.inverted()
    for sf in getattr(fig, "subfigs", []):                               # a combined figure: the panel letter of every cell
        for t in list(sf.texts) + ([sf._suptitle] if getattr(sf, "_suptitle", None) is not None else []):
            if t.get_text().strip():
                bb = t.get_window_extent(); x, y = inv.transform((bb.x0, bb.y1)); ftexts.append({"text": t.get_text(), "x": float(x), "y": float(y), "pt": t.get_fontsize()})
    return {"page": (float(W), float(H)), "layers": layers, "differences": diff, "fig_texts": ftexts, "legends": legends}


REF_WIDTH = 62.0      # % of the page width: in a layer about this wide Origin draws letters, symbols and line weights at their stated size


def _scale(L):
    """Origin makes everything in a layer smaller in proportion to the layer's width ("scale elements with the layer frame"):
    in the two panels of a figure the letters came out at about two thirds of their size, in the six panels of another at
    about a third, and the lines as thin. Every size sent to a layer is therefore multiplied by this, so that it comes out
    at the size of the app's figure. Measured on Origin 2018 with its standard graph template."""
    return float(min(8.0, max(0.6, REF_WIDTH / max(float(L["width"]), 1.0))))


def send(driver, fig, name, picture_dir=None):
    """Build the figure in Origin through the app's driver (real Origin or the dry-run mock). Returns (graph window, differences).

    The commands are first written down and then sent in the driver's proven order - every workbook, then the graph
    window, then all its layers, then curves, axes and texts layer by layer - the order the app's ordinary graphs have
    always used (Driver.draw_spec). Importing a workbook makes it Origin's active window: when the curves were plotted
    straight after each import, the plot command and every axis command after it went to the workbook, Origin refused
    them, and the graph came out with empty layers at their default 0-10 axes."""
    d = driver; ordered = hasattr(d, "rec") and getattr(d, "rec", None) is None and hasattr(d, "make_book")
    if not ordered: return _build(d, fig, name)
    d.rec = {"books": [], "graph": [], "layers": [], "rest": []}; d.plan = {}; d.axplan = {}; d._ops_axes = []
    try: g, diff = _build(d, fig, name)
    finally: rec = d.rec; d.rec = None
    for bucket in ("books", "graph", "layers", "rest"):
        for cmd, soft in rec[bucket]:
            if isinstance(cmd, tuple): d.make_book(cmd[1])
            else: (d.soft if soft else d.ex)(cmd)
    if hasattr(d, "check"): d.check(g, name)          # Origin is asked how many curves each layer holds; an empty one is filled a second way
    for i, cmds in getattr(d, "_ops_axes", []):       # the look of every axis once more, last: filling a layer the second way gives it Origin's standard axes back
        d.soft(f"win -a {g};"); d.soft(f"page.active={i};")
        for cmd, _soft in cmds: d.soft(cmd)
    d._ops_axes = []
    return g, diff


def _axis_cmds(L, k):
    """The commands for the axes of one layer: ranges, scales, frame, tick steps, sizes. [(command, optional)]"""
    c = []; ex = lambda t: c.append((t, False)); soft = lambda t: c.append((t, True))
    (x0, x1), (y0, y1) = L["x"], L["y"]
    ex(f"layer.x.type={2 if L['xlog'] else 1};"); ex(f"layer.y.type={2 if L['ylog'] else 1};")
    ex(f"layer.x.from={x0:.8g}; layer.x.to={x1:.8g};"); ex(f"layer.y.from={y0:.8g}; layer.y.to={y1:.8g};")
    if L.get("xinc"): ex(f"layer.x.inc={L['xinc']:.6g};"); soft(f"layer.x.minor={int(L.get('xminor') or 0)};")      # the same numbered ticks as in the app (Origin chose its own: 5, 10, 15 where the figure has 20, 40, 60)
    if L.get("yinc"): ex(f"layer.y.inc={L['yinc']:.6g};"); soft(f"layer.y.minor={int(L.get('yminor') or 0)};")
    if L["right_axis"]:
        soft(f"layer.link={L['linked_to']};"); soft("layer.x.link=1;"); ex("layer.x.showAxes=0;"); ex("layer.y.showAxes=2;"); soft("layer.y.showLabels=0;"); soft("layer.y2.showLabels=1;"); soft("layer.y2.ticks=5;")
    else:
        ex(f"layer.x.showAxes={3 if L['frame'] else 1};"); ex(f"layer.y.showAxes={3 if L['frame'] else 1};")
        ex("layer.x.ticks=5;"); ex("layer.y.ticks=5;"); ex(f"layer.x2.ticks={5 if L['frame'] else 0};"); ex(f"layer.y2.ticks={5 if L['frame'] else 0};")
        ex("layer.x2.showLabels=0;"); ex("layer.y2.showLabels=0;")
        ex(f"layer.x.showLabels={1 if L['xticklabels'] and not L['cat_labels'] else 0};"); ex(f"layer.y.showLabels={1 if L['yticklabels'] else 0};")
    tp = max(4, int(round(L["tick_pt"] * k))); ex(f"layer.x.label.pt={tp}; layer.y.label.pt={tp};"); soft(f"layer.y2.label.pt={tp};")
    for a in ("x", "y", "x2", "y2"): soft(f"layer.{a}.thickness={max(0.5, L['axis_pt'] * k):.3g};")
    if L["cat_labels"]:                                                    # names under the columns: the numbers of the axis are hidden every way Origin 2018 needs
        soft("layer.x.label.color=color(255,255,255);"); soft("layer.x.label.pt=4;"); soft("layer.x.minor=0;")
    ex("label -r legend;")
    soft("xb.show=0;"); soft("yl.show=0;"); soft("yr.show=0;")          # the axis titles are sent as texts at their place in the figure (a layer added to a page has no title objects of its own)
    return c


def _build(driver, fig, name):
    R = read_figure(fig); d = driver; W, H = R["page"]; diff = list(R["differences"])
    g = d.graph(name, round(W, 3), round(H, 3))
    ex, soft = d.ex, d.soft
    if not R["layers"]:
        diff.append("this graph type has no equal built here: its picture is placed on the Origin page"); return g, diff
    def note(t):
        if t not in diff: diff.append(t)
    def place(L, fx, fy):
        """A point of the page (fractions, y upwards) in the axis units of a layer - outside its frame too."""
        ax_ = (fx * 100 - L["left"]) / L["width"]; ay = 1 - ((1 - fy) * 100 - L["top"]) / L["height"]; (x0, x1), (y0, y1) = L["x"], L["y"]
        x = 10 ** (np.log10(x0) + ax_ * (np.log10(x1) - np.log10(x0))) if L["xlog"] else x0 + ax_ * (x1 - x0)
        y = 10 ** (np.log10(y0) + ay * (np.log10(y1) - np.log10(y0))) if L["ylog"] else y0 + ay * (y1 - y0)
        return float(x), float(y)
    def riser(L):
        """up(y, inches): the y that lies so many inches higher on the page."""
        (y0, y1) = L["y"]; hin = max(1e-6, H * L["height"] / 100.0)
        if L["ylog"]: return lambda y, inch: float(10 ** (np.log10(y) + inch / hin * (np.log10(y1) - np.log10(y0)))) if y > 0 else y
        return lambda y, inch: float(y + inch / hin * (y1 - y0))
    def runner(L):
        (x0, x1) = L["x"]; win_ = max(1e-6, W * L["width"] / 100.0)
        if L["xlog"]: return lambda x, inch: float(10 ** (np.log10(x) + inch / win_ * (np.log10(x1) - np.log10(x0)))) if x > 0 else x
        return lambda x, inch: float(x + inch / win_ * (x1 - x0))
    for i, L in enumerate(R["layers"], 1):
        d.layer(g, i, L["left"], L["top"], L["width"], L["height"], new=i > 1)
    plots = {}                                                              # layer -> what was plotted in it, in Origin's order (for the keys of the legends)
    for i, L in enumerate(R["layers"], 1):
        ex(f"win -a {g};"); ex(f"page.active={i};")
        k = _scale(L); up = riser(L); n = 0; here = plots.setdefault(i, [])
        (x0, x1), (y0, y1) = L["x"], L["y"]
        for z in L["zones"]:                                                   # shaded zones first: they lie behind the curves
            zx = z["x"] or L["x"]; zy = z["y"] or L["y"]; lo, hi = min(zy), max(zy)
            b = d.book("B_zone", [np.array([min(zx), max(zx)]), np.array([hi, hi])]); ds = f"{b}_B"
            d.plot(g, i, ds, z["colour"], 0.2, 204); soft(f"set {ds} -pf 1;"); n += 1; here.append({"n": n, "kind": "patch", "colour": z["colour"], "label": "", "hatch": ""})
        for bset in L["bars"]:                                                 # columns before curves: points and lines of the figure lie on its columns
            bx = np.asarray(bset["x"], dtype=float); by = np.asarray(bset["y"], dtype=float)
            if len(bx) > 1 and not L["ylog"]:
                gap = float(np.min(np.diff(np.sort(bx))))
                if bset["width"] < 0.75 * gap:
                    # Origin makes a column 80 % as wide as the smallest step between the x values of its own data set. Columns
                    # that stand in groups (their own narrower width in the figure) get one more x value at that distance, with
                    # no height: the columns then have the width of the figure instead of covering each other.
                    bx = np.append(bx, float(np.max(bx)) + bset["width"] / 0.8); by = np.append(by, 0.0)
            b = d.book("D_bars", [bx, by]); ds = f"{b}_B"; d.plot(g, i, ds, bset["colour"], 0.5, 203)
            soft(f"set {ds} -w {max(125, int(round(0.5 * k * 500)))};")
            if bset["hatch"]:
                soft(f"set {ds} -pfv {1 + '/\\|-+x'.find(bset['hatch'][0]) % 6};"); note("hatched columns: where Origin shows them plain, set the pattern in Plot Details > Pattern > Fill")
            n += 1; here.append({"n": n, "kind": "patch", "colour": bset["colour"], "label": bset["label"], "hatch": bset["hatch"]})
        for c in L["curves"]:
            ok = np.isfinite(c["x"]) & np.isfinite(c["y"])
            if ok.sum() == 0: continue
            b = d.book("D_curve", [c["x"][ok], c["y"][ok]]); ds = f"{b}_B"; code = {"line": 200, "scatter": 201, "linesymbol": 202, "area": 204}[c["kind"]]
            d.plan.setdefault((g, i), []).append((ds, c["colour"], c["width"] * k, code))
            ex(f"layer -i{code} {ds};"); ex(f"set {ds} -c color({c['colour'][0]},{c['colour'][1]},{c['colour'][2]});")
            if c["kind"] in ("line", "linesymbol", "area"):
                ex(f"set {ds} -w {max(125, int(round(c['width'] * k * 500)))};")
                if c["dash"]: ex(f"set {ds} -d {c['dash']};")
            if c["marker"] is not None:
                ex(f"set {ds} -k {c['marker']};"); ex(f"set {ds} -z {max(3, int(round(c['msize'] * k * 1.1)))};")
                if c["open"]: soft(f"set {ds} -kf 1;")
            if c["kind"] == "area": soft(f"set {ds} -cf color({c['colour'][0]},{c['colour'][1]},{c['colour'][2]});")
            n += 1; here.append({"n": n, "kind": "patch" if c["kind"] == "area" else "marker" if c["kind"] == "scatter" else "line", "colour": c["colour"], "label": c["label"], "hatch": "", "symbol": c["marker"] is not None})
        # ---- axes: the same ranges, scales, reversals, tick steps and sizes
        d.axplan[(g, i)] = (x0, x1, y0, y1); cmds = _axis_cmds(L, k)
        for cmd, sf in cmds: (soft if sf else ex)(cmd)
        if hasattr(d, "_ops_axes"): d._ops_axes.append((i, cmds))
        lp = L["label_pt"]
        if L["xlabel"].strip() and L.get("xlabel_at"):
            tx, ty = place(L, *L["xlabel_at"]); _text(d, L["xlabel"], tx, ty, lp * k, (0, 0, 0), False, ha="center", va="center", up=up, pt_true=lp)
        if L["ylabel"].strip() and L.get("ylabel_at"):
            tx, ty = place(L, *L["ylabel_at"]); _text(d, L["ylabel"], tx, ty, lp * k, L["ylabel_color"], False, rotate=L.get("ylabel_rot", 90.0), ha="center", va="center", up=up, pt_true=lp)
        if L["cat_labels"]:
            for xv, t in zip(*L["cat_labels"]):
                if t.strip() and min(x0, x1) <= xv <= max(x0, x1): _text(d, t, xv, up(y0, -0.035 - 0.25 * L["tick_pt"] / 72.0), L["tick_pt"] * k, (0, 0, 0), False, ha="center", va="top", up=up, pt_true=L["tick_pt"])
        for kind, v, col, w, ls in L["vlines"]:                               # reference lines
            if kind == "v": b = d.book("L_ref", [np.array([v, v]), np.array([y0, y1])])
            else: b = d.book("L_ref", [np.array([x0, x1]), np.array([v, v])])
            ds = f"{b}_B"; ex(f"layer -i200 {ds};"); ex(f"set {ds} -c color({col[0]},{col[1]},{col[2]});"); ex(f"set {ds} -w {max(125, int(round(w * k * 500)))};"); n += 1
            if DASHES.get(ls): ex(f"set {ds} -d {DASHES[ls]};")
        if L["title"].strip():                                                 # panel label + title: above the top-left corner (or the middle) of the frame
            left = L.get("title_left", True); tx = x0 if left else place(L, (L["left"] + L["width"] / 2) / 100.0, 0.5)[0]
            _text(d, L["title"], tx, up(y1, 0.03), L["title_pt"] * k, (0, 0, 0), L.get("title_bold", True), ha="left" if left else "center", va="bottom", up=up, pt_true=L["title_pt"])
        for t in L["texts"]:
            _text(d, t["text"], t["x"], t["y"], t["pt"] * k, t["colour"], t["bold"], rotate=t["rotate"], ha=t["ha"] if t["ha"] in ("left", "center", "right") else "left",
                  va="top" if t["va"] == "top" else "bottom" if t["va"] in ("bottom", "baseline") else "center", up=up, pt_true=t["pt"])
        if hasattr(d, "checks") and getattr(d, "rec", None) is None: d.checks.append((name, i, n, d.count_plots(g, i), ""))   # written down first (send): counted after it is sent, by Driver.check
    def nearest(fx, fy):
        return min(range(len(R["layers"])), key=lambda j: abs((R["layers"][j]["left"] + R["layers"][j]["width"] / 2) / 100 - fx) + abs((1 - (R["layers"][j]["top"] + R["layers"][j]["height"] / 2) / 100) - fy)) + 1
    def key_in(i, e):
        """Which plot of layer i this legend entry stands for: by its name, else by what it looks like. None when it has none there."""
        here = plots.get(i, [])
        m = [q for q in here if q["label"] and q["label"] == e["text"]]
        if not m and e["kind"]:
            m = [q for q in here if q["kind"] == e["kind"] and tuple(q["colour"]) == tuple(e["colour"]) and (e["kind"] != "patch" or (q.get("hatch") or "")[:1] == (e.get("hatch") or "")[:1])]
            if not m and e["kind"] == "patch": m = [q for q in here if q["kind"] == "patch" and tuple(q["colour"]) == tuple(e["colour"])]
            if not m and e["kind"] == "marker": m = [q for q in here if q.get("symbol") and tuple(q["colour"]) == tuple(e["colour"])]
        return m[0]["n"] if m else None
    for lg in R.get("legends", []):                                           # every legend entry as a text with the key of its curve, at its place in the figure
        ent = lg["entries"]; host = lg["host"]
        if host is None:
            cx = float(np.mean([e["x"] for e in ent])); cy = float(np.mean([e["y"] for e in ent]))
            score = {i: sum(key_in(i, e) is not None for e in ent) for i in range(1, len(R["layers"]) + 1)}; best = max(score.values())
            cand = [i for i, v in score.items() if v == best]; near = nearest(cx, cy); host = near if near in cand else cand[0]
        L = R["layers"][host - 1]; k = _scale(L); up = riser(L); run = runner(L)
        ex(f"win -a {g};"); ex(f"page.active={host};")
        for e in ent:
            tx, ty = place(L, e["x"], e["y"]); kk = key_in(host, e); pt = e["pt"]
            if kk is not None:
                _text(d, e["text"], tx, ty, pt * k, (0, 0, 0), False, ha="left", va="center", up=up, pt_true=pt, lead=f"\\l({kk}) ")
            else:                                                             # no such curve in this layer: a mark in its colour, then the text
                mark = {"patch": "■", "marker": "◆", "line": "—"}.get(e["kind"] or "", "")
                if mark: _text(d, mark, tx, ty, pt * k * (1.0 if e["kind"] != "line" else 1.3), e["colour"], e["kind"] == "line", ha="left", va="center", up=up, pt_true=pt)
                _text(d, e["text"], run(tx, (1.9 * pt / 72.0) if mark else 0.0), ty, pt * k, (0, 0, 0), False, ha="left", va="center", up=up, pt_true=pt)
    for t in R["fig_texts"]:                                                   # texts of the page (panel letters of a combined figure, notes): attached to the nearest layer
        j = min(range(len(R["layers"])), key=lambda j: abs(R["layers"][j]["left"] / 100 - t["x"]) + abs((1 - R["layers"][j]["top"] / 100) - t["y"]))
        L = R["layers"][j]; x, y = place(L, t["x"], t["y"])
        ex(f"win -a {g};"); ex(f"page.active={j + 1};"); _text(d, t["text"], x, y, t["pt"] * _scale(L), (0, 0, 0), t.get("bold", True), ha="left", va="top", up=riser(L), pt_true=t["pt"])
    return g, diff


def _text(d, s, x, y, pt, colour, bold, rotate=0, ha="left", va="top", up=None, pt_true=None, lead=""):
    """One text at axis position (x, y) of the active layer, with the commands the app's graphs have always used.
    ha: which side of the text stands on x (left / center / right); va: top (hangs below y), bottom (sits on y), center.
    A text of several lines is sent as one text per line - Origin wrote the line break of a text as the letter n.
    The text is made at a position that is not negative and then moved: 'label -a' read a negative number as an option,
    made a text of the rest of the command and gave it no name, so every text left of zero was lost."""
    lines = [ln for ln in str(s).split("\n")]
    if len(lines) > 1 and not rotate and up is not None:
        step = 1.22 * float(pt_true or pt) / 72.0; n = len(lines)
        for j, ln in enumerate(lines):
            if not ln.strip(): continue
            off = -j if va == "top" else (n - 1 - j) if va == "bottom" else ((n - 1) / 2.0 - j)
            _text(d, ln, x, up(y, off * step), pt, colour, bold, rotate=rotate, ha=ha, va=va, lead=lead if j == 0 else "")
        return
    d.nlabel += 1; nm = "T%d" % d.nlabel; t = _otext(" ".join(ln.strip() for ln in lines))
    if bold: t = "\\b(" + t + ")"
    t = lead + t
    d.ex(f"label -a {max(x, 0.0):.6g} {max(y, 0.0):.6g} -n {nm} x;"); d.ex(f'{nm}.text$="{t}";'); d.ex(f"{nm}.fsize={max(4, int(round(pt)))};")
    d.ex(f"{nm}.color=color({colour[0]},{colour[1]},{colour[2]});"); d.ex(f"{nm}.attach=2;")
    if rotate: d.ex(f"{nm}.rotate={int(round(rotate))};")
    d.ex(f"{nm}.x={x:.6g}{'+' + nm + '.dx/2' if ha == 'left' else '-' + nm + '.dx/2' if ha == 'right' else ''};")
    d.ex(f"{nm}.y={y:.6g}{'-' + nm + '.dy/2' if va == 'top' else '+' + nm + '.dy/2' if va == 'bottom' else ''};")


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_")[:80] or "graph"


def project_name(sample, template):
    """{sample}_{template}.opju"""
    return f"{safe_name(sample)}_{safe_name(template)}.opju"


def draw_in_origin(make_driver, fig, sample, template, folder, keep_open=True, export_dpi=None, width_mm=None, save_otpu=None):
    """One Origin project per graph: {sample}_{template}.opju in `folder`. make_driver(folder) gives the app's driver
    (dry run or real). Returns {"project", "graph", "differences", "commands"}."""
    os.makedirs(folder, exist_ok=True); d = make_driver(folder)
    d.tmp = os.path.join(d.out, "data_for_origin", os.path.splitext(project_name(sample, template))[0]); os.makedirs(d.tmp, exist_ok=True)      # the worksheets of this graph, apart from those of the others
    g, diff = send(d, fig, f"{safe_name(sample)[:20]}_{safe_name(template)[:20]}")
    if any("picture" in x for x in diff):              # what Origin cannot build here: the app's own figure, beside the project and on the page
        from . import core
        pic = os.path.join(d.out, f"{safe_name(sample)}_{safe_name(template)}_app_figure.png"); core.save(fig, pic, dpi=300)
        d.soft(f'win -a {g}; insertImg2g fname:="{pic}";')
    if width_mm:                                       # export from Origin at the size and resolution of the preset
        d.soft(f'expGraph type:=tif path:="{d.out}" filename:="{safe_name(sample)}_{safe_name(template)}" tr.Unit:=2 tr.Width:={width_mm / 10:.3f} tr1.Resolution:={int(export_dpi or 600)} overwrite:=replace;')
    if save_otpu:
        d.soft(f'win -a {g}; template_saveas template:="{os.path.splitext(os.path.basename(save_otpu))[0]}" path:="{os.path.dirname(save_otpu)}";')
    pj = project_name(sample, template); d.save(keep_open, name=pj)
    cmds = list(getattr(d.org, "cmds", [])) or [t[8:] for t in getattr(d, "trace", []) if t[:8].strip() in ("ok", "FAILED", "refused")]
    try: write_ogs(cmds, os.path.join(d.out, os.path.splitext(pj)[0] + ".ogs"), f"{sample} drawn as {template}")
    except Exception: pass
    return {"project": os.path.join(d.out, pj), "graph": g, "differences": diff, "commands": cmds, "check": getattr(d, "check_text", "")}


def write_ogs(commands, path, title=""):
    """The commands of a graph as a LabTalk script file (Origin: run.section(file, Main))."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"// {title}\n// Written by Origin Plot Studio: the same commands the app sends to Origin.\n[Main]\n")
        for c in commands:
            if not str(c).startswith("SAVE "): f.write(str(c).rstrip() + ("\n" if str(c).rstrip().endswith(";") else ";\n"))
    return path

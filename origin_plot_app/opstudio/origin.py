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
    return s.replace('"', "'").replace("\n", "\\n")


def _is_data(artist, ax):
    try: return artist.get_transform().contains_branch(ax.transData)
    except Exception: return True


def read_figure(fig):
    """The figure as plain data: {"page": (w_in, h_in), "layers": [...], "differences": [...]}.
    A layer: place (left, top, width, height in % of the page), x / y range, log, titles, sizes, curves, bars, zones, texts, legend."""
    fig.canvas.draw(); W, H = fig.get_size_inches(); layers = []; diff = []
    def note(s):
        if s not in diff: diff.append(s)
    twins = {}; axes = []; inv = fig.transFigure.inverted()
    def walk(a):
        if not a.get_visible(): return
        axes.append(a)
        for ch in getattr(a, "child_axes", []):
            if type(ch).__name__ == "SecondaryAxis": note("a second axis with its own scale (for example d-spacing on top) is not sent: add it in Origin (Axis dialog > Show the top axis, with a formula)")
            else: walk(ch)                                              # insets (zoom panels inside a graph) are layers of their own
    for ax in fig.axes: walk(ax)
    for ax in axes:
        if getattr(ax, "name", "") in ("polar", "3d"):
            note(f"a {'polar' if ax.name == 'polar' else '3D'} panel is sent as a picture of the app's figure (Origin's own {ax.name} graph type is named in the template's Origin hint)"); continue
        from matplotlib.transforms import Bbox
        p = Bbox(inv.transform(ax.get_window_extent().get_points())); x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()      # where the panel really is on the page (insets too)
        L = {"left": p.x0 * 100, "top": (1 - p.y1) * 100, "width": p.width * 100, "height": p.height * 100, "x": (x0, x1), "y": (y0, y1),
             "xlog": ax.get_xscale() == "log", "ylog": ax.get_yscale() == "log", "xlabel": ax.get_xlabel(), "ylabel": ax.get_ylabel(),
             "title": ax.get_title(loc="left") or ax.get_title(), "title_bold": True, "curves": [], "bars": [], "zones": [], "texts": [], "vlines": [], "legend": None,
             "xticklabels": any(t.get_visible() and t.get_text() for t in ax.get_xticklabels()), "yticklabels": any(t.get_visible() and t.get_text() for t in ax.get_yticklabels()),
             "tick_pt": (ax.get_xticklabels()[0].get_fontsize() if ax.get_xticklabels() else 8), "label_pt": ax.xaxis.label.get_fontsize(), "title_pt": ax.title.get_fontsize(),
             "axis_pt": ax.spines["left"].get_linewidth() if "left" in ax.spines else 0.8, "frame": all(ax.spines[s].get_visible() for s in ("top", "right") if s in ax.spines),
             "ticks_in": True, "right_axis": False, "cat_labels": None, "ylabel_color": _rgb(ax.yaxis.label.get_color())}
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
            L["curves"].append({"x": x, "y": y, "colour": _rgb(ln.get_color()), "width": float(ln.get_linewidth()), "dash": DASHES.get(ls, 0 if has_line else None),
                                "kind": "linesymbol" if has_line and has_mk else "line" if has_line else "scatter", "marker": MARKERS.get(mk, 2) if has_mk else None,
                                "msize": float(ln.get_markersize()), "open": str(ln.get_markerfacecolor()).lower() in ("white", "w", "none", "#ffffff") if has_mk else False, "label": lab})
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
        layers.append(L)
    ftexts = [{"text": t.get_text(), "x": t.get_position()[0], "y": t.get_position()[1], "pt": t.get_fontsize()} for t in fig.texts if t.get_text().strip() and "Illustrative" not in t.get_text()]
    inv = fig.transFigure.inverted()
    for sf in getattr(fig, "subfigs", []):                               # a combined figure: the panel letter of every cell
        for t in list(sf.texts) + ([sf._suptitle] if getattr(sf, "_suptitle", None) is not None else []):
            if t.get_text().strip():
                bb = t.get_window_extent(); x, y = inv.transform((bb.x0, bb.y1)); ftexts.append({"text": t.get_text(), "x": float(x), "y": float(y), "pt": t.get_fontsize()})
    return {"page": (float(W), float(H)), "layers": layers, "differences": diff, "fig_texts": ftexts}


def send(driver, fig, name, picture_dir=None):
    """Build the figure in Origin through the app's driver (real Origin or the dry-run mock). Returns (graph window, differences)."""
    R = read_figure(fig); d = driver; W, H = R["page"]; diff = list(R["differences"])
    g = d.graph(name, round(W, 3), round(H, 3))
    ex, soft = d.ex, d.soft
    if not R["layers"]:
        diff.append("this graph type has no equal built here: its picture is placed on the Origin page"); return g, diff
    for i, L in enumerate(R["layers"], 1):
        d.layer(g, i, L["left"], L["top"], L["width"], L["height"], new=i > 1)
    for i, L in enumerate(R["layers"], 1):
        ex(f"win -a {g};"); ex(f"page.active={i};")
        n = 0; plotted = []
        for z in L["zones"]:                                                   # shaded zones first: they lie behind the curves
            zx = z["x"] or L["x"]; zy = z["y"] or L["y"]; lo, hi = min(zy), max(zy)
            b = d.book("B_zone", [np.array([min(zx), max(zx)]), np.array([hi, hi])]); ds = f"{b}_B"
            d.plot(g, i, ds, z["colour"], 0.2, 204); soft(f"set {ds} -pf 1;"); n += 1
        for c in L["curves"]:
            ok = np.isfinite(c["x"]) & np.isfinite(c["y"])
            if ok.sum() == 0: continue
            b = d.book("D_curve", [c["x"][ok], c["y"][ok]]); ds = f"{b}_B"; code = {"line": 200, "scatter": 201, "linesymbol": 202, "area": 204}[c["kind"]]
            d.plan.setdefault((g, i), []).append((ds, c["colour"], c["width"], code))
            ex(f"layer -i{code} {ds};"); ex(f"set {ds} -c color({c['colour'][0]},{c['colour'][1]},{c['colour'][2]});")
            if c["kind"] in ("line", "linesymbol", "area"):
                ex(f"set {ds} -w {int(round(c['width'] * 500))};")
                if c["dash"]: ex(f"set {ds} -d {c['dash']};")
            if c["marker"] is not None:
                ex(f"set {ds} -k {c['marker']};"); ex(f"set {ds} -z {max(2, int(round(c['msize'] * 1.6)))};")
                if c["open"]: soft(f"set {ds} -kf 1;")
            if c["kind"] == "area": soft(f"set {ds} -cf color({c['colour'][0]},{c['colour'][1]},{c['colour'][2]});")
            plotted.append((ds, c["label"])); n += 1
        for bset in L["bars"]:
            b = d.book("D_bars", [bset["x"], bset["y"]]); ds = f"{b}_B"; d.plot(g, i, ds, bset["colour"], 0.5, 203)
            if bset["hatch"]: soft(f"set {ds} -pfv {1 + '/\\|-+x'.find(bset['hatch'][0]) % 6};")
            if len(bset["x"]) > 1: soft(f"layer.bar.gap={max(0, min(90, int(round((1 - bset['width'] / max(1e-9, float(np.min(np.diff(np.sort(bset['x'])))))) * 100))))};")
            plotted.append((ds, bset["label"])); n += 1
        # ---- axes: the same ranges, scales and reversals
        (x0, x1), (y0, y1) = L["x"], L["y"]; d.axplan[(g, i)] = (x0, x1, y0, y1)
        ex(f"layer.x.type={2 if L['xlog'] else 1};"); ex(f"layer.y.type={2 if L['ylog'] else 1};")
        ex(f"layer.x.from={x0:.8g}; layer.x.to={x1:.8g};"); ex(f"layer.y.from={y0:.8g}; layer.y.to={y1:.8g};")
        if L["right_axis"]:
            soft(f"layer.link={L['linked_to']};"); soft("layer.x.link=1;"); ex("layer.x.showAxes=0;"); ex("layer.y.showAxes=2;"); soft("layer.y.showLabels=0;"); soft("layer.y2.showLabels=1;"); soft("layer.y2.ticks=5;")
        else:
            ex(f"layer.x.showAxes={3 if L['frame'] else 1};"); ex(f"layer.y.showAxes={3 if L['frame'] else 1};")
            ex("layer.x.ticks=5;"); ex("layer.y.ticks=5;"); ex(f"layer.x2.ticks={5 if L['frame'] else 0};"); ex(f"layer.y2.ticks={5 if L['frame'] else 0};")
            ex("layer.x2.showLabels=0;"); ex("layer.y2.showLabels=0;")
            ex(f"layer.x.showLabels={1 if L['xticklabels'] else 0};"); ex(f"layer.y.showLabels={1 if L['yticklabels'] else 0};")
        tp = int(round(L["tick_pt"])); ex(f"layer.x.label.pt={tp}; layer.y.label.pt={tp};"); soft(f"layer.y2.label.pt={tp};")
        for a in ("x", "y", "x2", "y2"): soft(f"layer.{a}.thickness={L['axis_pt']:g};")
        ex("label -r legend;")
        lp = int(round(L["label_pt"]))
        if L["xlabel"] and L["xticklabels"]: ex('xb.text$="%s";' % _otext(L["xlabel"])); ex(f"xb.fsize={lp};")
        else: soft("xb.show=0;")
        if L["ylabel"]:
            nm = "yr" if L["right_axis"] else "yl"
            (soft if L["right_axis"] else ex)('%s.text$="%s";' % (nm, _otext(L["ylabel"]))); (soft if L["right_axis"] else ex)(f"{nm}.fsize={lp};")
            c = L["ylabel_color"]
            if c != (0, 0, 0): soft(f"{nm}.color=color({c[0]},{c[1]},{c[2]});")
        else: soft("yl.show=0;")
        if L["cat_labels"]:
            diff.append("category names on the axis are sent as texts under the columns (in Origin, set the names column as X to get tick labels)") if "category names" not in " ".join(diff) else None
            for xv, s in zip(*L["cat_labels"]):
                if s.strip(): _text(d, s, xv, min(y0, y1), L["tick_pt"], (0, 0, 0), False, hang=True)
            soft("layer.x.showLabels=0;")
        for kind, v, col, w, ls in L["vlines"]:                               # reference lines
            if kind == "v": b = d.book("L_ref", [np.array([v, v]), np.array([y0, y1])])
            else: b = d.book("L_ref", [np.array([x0, x1]), np.array([v, v])])
            ds = f"{b}_B"; ex(f"layer -i200 {ds};"); ex(f"set {ds} -c color({col[0]},{col[1]},{col[2]});"); ex(f"set {ds} -w {int(round(w * 500))};")
            if DASHES.get(ls): ex(f"set {ds} -d {DASHES[ls]};")
        if L["title"].strip():                                                 # panel label + title: bold, above the top-left corner
            _text(d, L["title"], x0, y1, L["title_pt"], (0, 0, 0), True, centre=False, sit=True)
        for t in L["texts"]:
            _text(d, t["text"], t["x"], t["y"], t["pt"], t["colour"], t["bold"], rotate=t["rotate"], centre=t["ha"] == "center", hang=t["va"] == "top", sit=t["va"] in ("bottom", "baseline"))
        if L["legend"] and plotted:
            lg = L["legend"]; ent = [e for e in lg["entries"]]
            named = [(k + 1, lab) for k, (ds, lab) in enumerate(plotted) if lab]
            lines = [f"\\l({k}) {_otext(lab)}" for k, lab in named] or [_otext(e) for e in ent]
            xl = x0 + lg["x"] * (x1 - x0) if not L["xlog"] else 10 ** (np.log10(x0) + lg["x"] * (np.log10(x1) - np.log10(x0)))
            yl = y0 + lg["y"] * (y1 - y0) if not L["ylog"] else 10 ** (np.log10(y0) + lg["y"] * (np.log10(y1) - np.log10(y0)))
            ex("legend -r;"); ex('legend.text$="%s";' % "\\n".join(lines)); ex(f"legend.fsize={int(round(lg['pt']))};"); soft(f"legend.background={1 if lg['frame'] else 0};")
            ex(f"legend.x={xl:.6g}+legend.dx/2;"); ex(f"legend.y={yl:.6g}-legend.dy/2;")
        d.checks.append((name, i, n, d.count_plots(g, i), "")) if hasattr(d, "checks") else None
    for t in R["fig_texts"]:                                                   # texts of the page (panel letters of a combined figure): attached to the nearest layer
        k = min(range(len(R["layers"])), key=lambda j: abs(R["layers"][j]["left"] / 100 - t["x"]) + abs((1 - R["layers"][j]["top"] / 100) - t["y"]))
        L = R["layers"][k]; fx = (t["x"] * 100 - L["left"]) / L["width"]; fy = ((1 - t["y"]) * 100 - L["top"]) / L["height"]
        (x0, x1), (y0, y1) = L["x"], L["y"]
        x = 10 ** (np.log10(x0) + fx * (np.log10(x1) - np.log10(x0))) if L["xlog"] else x0 + fx * (x1 - x0)
        y = 10 ** (np.log10(y1) - fy * (np.log10(y1) - np.log10(y0))) if L["ylog"] else y1 - fy * (y1 - y0)
        ex(f"win -a {g};"); ex(f"page.active={k + 1};"); _text(d, t["text"], x, y, t["pt"], (0, 0, 0), t.get("bold", True), centre=False)
    return g, diff


def _text(d, s, x, y, pt, colour, bold, rotate=0, centre=True, hang=False, sit=False):
    d.nlabel += 1; nm = "T%d" % d.nlabel; t = _otext(s)
    if bold: t = "\\b(" + t + ")"
    d.ex(f"label -a {x:.6g} {y:.6g} -n {nm} x;"); d.ex(f'{nm}.text$="{t}";'); d.ex(f"{nm}.fsize={max(4, int(round(pt)))};")
    d.ex(f"{nm}.color=color({colour[0]},{colour[1]},{colour[2]});"); d.ex(f"{nm}.attach=2;")
    if rotate: d.ex(f"{nm}.rotate={int(round(rotate))};")
    if centre: d.ex(f"{nm}.x={x:.6g};"); d.ex(f"{nm}.y={y:.6g}{'-' if hang else '+'}{nm}.dy/2;")
    else: d.ex(f"{nm}.x={x:.6g}+{nm}.dx/2;"); d.ex(f"{nm}.y={y:.6g}{'+' if sit else '-'}{nm}.dy/2;")


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

"""Sketch a design: draw how your figure should look and the app lays your graphs out that way.

Tools: Graph (a box for each graph or panel), Zoom (a small box inside a graph: the zoomed part goes there), Curve (draw the curves you
expect: one above the other = stacked, crossing = overlaid), Text (above a box: its title, below: the x axis title, left: the y axis
title, inside: a note), Legend (a small box: the legend goes to that corner). A photo of a sketch on paper can be put behind the pad and
traced. The sketch is read by fixed rules (read_sketch) - shown on the right before anything is changed - never by an AI, and none of
your numbers is touched: the sketch only decides the layout, the titles and where things go."""
import math
import os

import smart_plots as sp

TOOLS = [("pen", "✎ Draw freely", "Draw with a pen, your finger (touch screen) or the mouse: a big closed shape = a graph box, a closed shape "
         "inside a box = the zoomed part (small, in a corner = the legend), a line inside a box = a curve"),
         ("select", "↖ Move", "Move or delete (Del) what you drew"), ("erase", "⌫ Erase", "Click (or touch) what you drew to remove it"),
         ("box", "▭ Graph", "A box for each graph or panel: drag a rectangle"),
         ("zoom", "◳ Zoom", "A small box inside a graph: the zoomed part goes there"), ("curve", "〰 Curve", "Draw the curves: one above the other = stacked, crossing = overlaid"),
         ("text", "T Text", "Click and type: above a box = its title, below = x axis title, left = y axis title, inside = a note"),
         ("legend", "☰ Legend", "A small box inside a graph: the legend goes to that corner")]


def _inside(pt, r, pad=0.0):
    x, y = pt; rx, ry, rw, rh = r
    return rx - pad <= x <= rx + rw + pad and ry - pad <= y <= ry + rh + pad


def _centre(r):
    return r[0] + r[2] / 2, r[1] + r[3] / 2


def classify_strokes(strokes, page=(1100, 700)):
    """Free-hand strokes (pen, finger or mouse) -> the parts of a sketch, by fixed rules:
    a closed stroke (it ends near where it began) that is not inside a graph box and is big enough = a graph box; a closed stroke inside a
    box = the zoomed part, or the legend when it is small (under 6 % of the box); an open stroke = a curve. Returns item dicts as read_sketch takes."""
    W, H = page; out = []; closed = []
    for pts in strokes:
        pts = [tuple(map(float, q)) for q in pts]
        if len(pts) < 3:
            continue
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys); diag = math.hypot(w, h) or 1.0
        tail = pts[int(len(pts) * 0.75):]
        is_closed = min(math.hypot(q[0] - pts[0][0], q[1] - pts[0][1]) for q in tail) < 0.2 * diag and w > 15 and h > 15
        if is_closed:
            closed.append((w * h, (x0, y0, w, h)))
        else:
            out.append({"type": "curve", "pts": pts})
    boxes = []
    for area, r in sorted(closed, key=lambda t: -t[0]):
        cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
        host = next((b for b in boxes if _inside((cx, cy), b)), None)
        if host is None:
            if r[2] >= 0.12 * W and r[3] >= 0.10 * H:
                boxes.append(r); out.append({"type": "box", "rect": r})
            continue
        frac = area / (host[2] * host[3])
        out.append({"type": "legend" if frac < 0.06 else "zoom", "rect": r})
    return out


def photo_to_items(path_or_array, page=None):
    """A photo (or scan) of a sketch on paper -> the parts of a sketch, by fixed rules (no AI, nothing leaves the computer):
    the pen strokes are told from the paper (Otsu threshold on a background-flattened picture); every frame - a drawn box, or just the
    two axes of a graph (an L) - becomes a graph box; inside a frame, a small closed shape is the zoomed part (a very small one in a
    corner, the legend) and a long line is a curve. Hand-written words are not read. Returns (items, page size) in pad coordinates."""
    import numpy as np
    from scipy import ndimage as ndi
    if isinstance(path_or_array, (str, bytes)) or hasattr(path_or_array, "__fspath__"):
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(path_or_array)).convert("L")
        a = np.asarray(im, float)
    else:
        a = np.asarray(path_or_array, float)
        if a.ndim == 3: a = a[..., :3].mean(axis=2)
    if a.ndim != 2 or 0 in a.shape:
        raise ValueError("this picture has no readable width and height (it may be empty, 1-pixel, or in a format that did not convert to a plain image)")
    H0, W0 = a.shape
    sc = 1100.0 / max(W0, H0)
    if sc < 1:
        zoom = (max(1, int(H0 * sc)), max(1, int(W0 * sc)))
        a = ndi.zoom(a, (zoom[0] / H0, zoom[1] / W0), order=1)
    H, W = a.shape
    bg = ndi.uniform_filter(ndi.grey_closing(a, size=(25, 25)), 25)          # the paper: shading and shadows taken out
    d = np.clip(bg - a, 0, None)
    hist, edges = np.histogram(d, bins=256)
    p_ = hist / max(1, hist.sum()); om = np.cumsum(p_); mu = np.cumsum(p_ * np.arange(256)); mt = mu[-1]
    sb = (mt * om - mu) ** 2 / np.maximum(om * (1 - om), 1e-12); t = edges[int(np.nanargmax(sb))]
    ink = d > max(t, 18.0)
    # a photo taken a little crooked: straightened first (the angle at which the drawn lines run best along rows and columns)
    small = ink[::3, ::3].astype(float)
    def score(ang):
        r_ = ndi.rotate(small, ang, reshape=False, order=0)
        return float((r_.sum(axis=0) ** 2).sum() + (r_.sum(axis=1) ** 2).sum())
    angs = np.arange(-8.0, 8.01, 0.5)
    best = max(angs, key=score)
    fine = np.arange(best - 0.5, best + 0.51, 0.125)
    best = float(max(fine, key=score))
    photo_to_items.angle = best if abs(best) >= 0.25 else 0.0          # the pad shows the photo straightened the same way
    if abs(best) >= 0.25:
        d = ndi.rotate(d, best, reshape=False, order=1, mode="constant", cval=0.0)
        ink = d > max(t, 18.0)
    ink = ndi.binary_closing(ink, iterations=2)
    lab, n = ndi.label(ndi.binary_dilation(ink, iterations=2))
    objs = ndi.find_objects(lab)
    PW, PH = (1100.0, 1100.0 * H / W) if W >= H else (1100.0 * W / H, 1100.0)
    fx, fy = PW / W, PH / H
    def sides(mask):
        """How much of each side of the bounding box is drawn (0-1): left, right, top, bottom."""
        hh, ww = mask.shape; b = max(2, int(0.06 * min(hh, ww)))
        return (mask[:, :b].any(axis=1).mean(), mask[:, -b:].any(axis=1).mean(), mask[:b, :].any(axis=0).mean(), mask[-b:, :].any(axis=0).mean())
    frames, rest = [], []
    for k, sl in enumerate(objs, 1):
        if sl is None: continue
        m = (lab[sl] == k) & ink[sl]; hh, ww = m.shape
        if hh < 0.08 * H and ww < 0.08 * W: rest.append((sl, m)); continue
        l_, r_, t_, b_ = sides(m)
        if (l_ > 0.7 and b_ > 0.7) and (hh > 0.12 * H and ww > 0.15 * W):      # a box, or two axes
            frames.append((sl, m, (l_, r_, t_, b_)))
        else:
            rest.append((sl, m))
    items = []
    inner = []
    for sl, m, sd in frames:
        y0, x0 = sl[0].start, sl[1].start; hh, ww = m.shape
        items.append({"type": "box", "rect": (x0 * fx, y0 * fy, ww * fx, hh * fy)})
    boxes = [it["rect"] for it in items]
    # boxes drawn inside a frame (zoom, legend): found by their straight sides, even where a curve runs through them
    def rects_in(mask):
        hh, ww = mask.shape; L = max(8, int(0.05 * hh))
        V = ndi.binary_opening(ndi.binary_dilation(mask, structure=np.ones((1, 7))), structure=np.ones((L, 1)))      # hand-drawn sides wobble
        lv, nv = ndi.label(ndi.binary_dilation(V, iterations=1))
        segs = [(s_[1].start, s_[1].stop, s_[0].start, s_[0].stop) for s_ in ndi.find_objects(lv) if s_ is not None]
        out = []
        for i in range(len(segs)):
            for j in range(len(segs)):
                a_, b_ = segs[i], segs[j]
                if b_[0] <= a_[1] + 6: continue
                top, bot = max(a_[2], b_[2]), min(a_[3], b_[3])
                if bot - top < 0.7 * max(a_[3] - a_[2], b_[3] - b_[2]): continue
                xa, xb = a_[0], b_[1]; t2, b2 = min(a_[2], b_[2]), max(a_[3], b_[3])
                band = max(6, int(0.03 * hh))                                 # the corners of a drawn box lie a little beyond its straight sides
                cov_t = mask[max(0, t2 - 2 * band):t2 + band, xa:xb].any(axis=0).mean()
                cov_b = mask[max(0, b2 - band):b2 + 2 * band, xa:xb].any(axis=0).mean()
                if cov_t > 0.75 and cov_b > 0.75:
                    out.append((xa, t2, xb, b2))
        keep = []
        for r_ in sorted(out, key=lambda q: (q[2] - q[0]) * (q[3] - q[1])):    # the smallest box between two sides
            if not any(k_[0] >= r_[0] - 4 and k_[2] <= r_[2] + 4 and k_[1] >= r_[1] - 4 and k_[3] <= r_[3] + 4 for k_ in keep):
                keep.append(r_)
        return keep
    def split_curves(m):
        """One line or several: in every column the pen marks are counted; with K marks in most columns there are K curves
        (sorted from top to bottom in each column - crossing curves then touch, which reads as 'overlaid')."""
        cols = np.where(m.any(axis=0))[0]
        runs = {}
        for c in cols:
            yy = np.where(m[:, c])[0]
            br = np.where(np.diff(yy) > 3)[0]
            runs[c] = [float(np.mean(g)) for g in np.split(yy, br + 1)]
        cnt = [len(v) for v in runs.values()]
        K = int(np.median(cnt)) if cnt else 1
        K = max(1, min(K, 8))
        curves = [[] for _ in range(K)]
        for c in cols[:: max(1, len(cols) // 160)]:
            v = sorted(runs[c])
            if len(v) == K:
                for i in range(K):
                    curves[i].append((c, v[i]))
        crossed = False
        if K >= 2:                                                             # curves that meet: fewer marks in a stretch between full ones
            full = [c for c in cols if len(runs[c]) >= K]
            if full:
                inside = [c for c in cols if full[0] < c < full[-1]]
                fewer = [c for c in inside if len(runs[c]) < K]
                crossed = len(fewer) >= 3
        split_curves.crossed = crossed
        return [cv for cv in curves if len(cv) >= 5]
    for sl, m, sd in frames:
        y0, x0 = sl[0].start, sl[1].start; hh, ww = m.shape
        b = max(5, int(0.03 * min(hh, ww)))                                # the frame lines (and only them) are taken away
        mm = ink[sl].copy(); mm[:, :b] = False; mm[-b:, :] = False              # everything drawn inside the frame, joined to it or not
        if sd[1] > 0.7: mm[:, -b:] = False
        if sd[2] > 0.7: mm[:b, :] = False
        host = (x0 * fx, y0 * fy, ww * fx, hh * fy)
        for xa, t2, xb, b2 in rects_in(mm):
            r = ((x0 + xa) * fx, (y0 + t2) * fy, (xb - xa) * fx, (b2 - t2) * fy)
            frac = (r[2] * r[3]) / (host[2] * host[3])
            if frac < 0.004 or frac > 0.6: continue
            items.append({"type": "legend" if frac < 0.06 else "zoom", "rect": r})
            pad_ = max(8, int(0.025 * hh))                                       # its sides taken away: the curves through it stay
            for xx in (xa, xb):
                mm[max(0, t2 - pad_):b2 + pad_, max(0, xx - pad_):xx + pad_] = False
            for yy_ in (t2, b2):
                mm[max(0, yy_ - pad_):yy_ + pad_, max(0, xa - pad_):xb + pad_] = False
            if frac < 0.06:
                mm[t2:b2, xa:xb] = False                                       # what is written inside a legend is not a curve
        lc, nc = ndi.label(ndi.binary_dilation(ndi.binary_dilation(mm, iterations=2), structure=np.ones((1, 7))))
        pieces, overlay = [], False
        for k3, s3 in enumerate(ndi.find_objects(lc), 1):
            if s3 is None: continue
            m3 = (lc[s3] == k3) & mm[s3]
            if m3.shape[1] < 0.04 * ww: continue                               # dots, letters
            cvs = split_curves(m3)
            overlay |= len(cvs) >= 2 and getattr(split_curves, "crossed", False)
            pieces += [[(s3[1].start + c, s3[0].start + y) for c, y in cv] for cv in cvs]
        pieces.sort(key=lambda q: q[0][0]); merged = []
        for pc in pieces:                                                      # a curve cut where it crossed a box side: one curve again
            tgt = next((m_ for m_ in merged if 0 <= pc[0][0] - m_[-1][0] < 0.08 * ww and abs(pc[0][1] - m_[-1][1]) < 0.06 * hh), None)
            if tgt is not None: tgt.extend(pc)
            else: merged.append(list(pc))
        for cv in merged:
            if cv[-1][0] - cv[0][0] < 0.25 * ww: continue                      # too short for a curve: a scrap
            ys_ = [y for _, y in cv]
            if max(ys_) - min(ys_) < 0.03 * hh and (min(ys_) < 0.1 * hh or max(ys_) > 0.9 * hh): continue      # a flat bit of the frame's own edge
            items.append({"type": "curve", "pts": [((x0 + c) * fx, (y0 + y) * fy) for c, y in cv]})
        if overlay:
            items.append({"type": "hint", "how": "overlay", "pos": (host[0] + host[2] / 2, host[1] + host[3] / 2)})
    # marks outside every frame (words, arrows) are not read
    return items, (PW, PH)


def read_sketch(items, page=(1100, 700)):
    """The design in a sketch. items: dicts {type: box|zoom|curve|text|legend, rect: (x, y, w, h) | pts: [(x, y) ...] | pos, text}, in pad
    coordinates (y downwards). Returns {graphs: [{rect, title, xtitle, ytitle, notes, inset_rect, legend_loc, curves, how}], layout,
    rows, cols, orientation, lines: [what was read, in words]}."""
    W, H = page
    boxes = [dict(rect=tuple(it["rect"]), title=None, xtitle=None, ytitle=None, notes=[], inset_rect=None, legend_loc=None, curves=[])
             for it in items if it.get("type") == "box" and it["rect"][2] > 8 and it["rect"][3] > 8]
    lines = []
    if not boxes:
        return dict(graphs=[], layout="none", rows=0, cols=0, orientation="Landscape" if W >= H else "Portrait",
                    lines=["Draw at least one Graph box (▭): one for each graph or panel."])
    # rows and columns: boxes whose centres are within half a box height share a row
    hs = sorted(b["rect"][3] for b in boxes); tol = hs[len(hs) // 2] / 2
    rows = []
    for b in sorted(boxes, key=lambda b: _centre(b["rect"])[1]):
        cy = _centre(b["rect"])[1]
        if rows and abs(_centre(rows[-1][0]["rect"])[1] - cy) <= tol:
            rows[-1].append(b)
        else:
            rows.append([b])
    for r in rows:
        r.sort(key=lambda b: b["rect"][0])
    ordered = [b for r in rows for b in r]
    ncol = max(len(r) for r in rows)

    def owner(pt, pad=0.0):
        hit = [b for b in ordered if _inside(pt, b["rect"], pad)]
        return min(hit, key=lambda b: b["rect"][2] * b["rect"][3]) if hit else None

    for it in items:
        t = it.get("type")
        if t in ("zoom", "legend"):
            r = tuple(it["rect"]); b = owner(_centre(r))
            if b is None:
                lines.append(f"A {t} box outside every graph box was left out.")
                continue
            bx, by, bw, bh = b["rect"]
            if t == "zoom":                                   # axes fractions, origin bottom left
                fx = max(0.0, min(0.95, (r[0] - bx) / bw)); fw = max(0.08, min(1 - fx, r[2] / bw))
                fy = max(0.0, min(0.95, 1 - (r[1] + r[3] - by) / bh)); fh = max(0.08, min(1 - fy, r[3] / bh))
                b["inset_rect"] = (round(fx, 3), round(fy, 3), round(fw, 3), round(fh, 3))
            else:
                cx, cy = _centre(r)
                b["legend_loc"] = ("upper " if cy < by + bh / 2 else "lower ") + ("left" if cx < bx + bw / 2 else "right")
        elif t == "curve":
            pts = [tuple(p) for p in it.get("pts") or []]
            if len(pts) < 2:
                continue
            votes = {}
            for p in pts:
                b = owner(p)
                if b is not None:
                    votes[id(b)] = votes.get(id(b), 0) + 1
            if votes:
                b = next(b for b in ordered if id(b) == max(votes, key=votes.get))
                b["curves"].append(pts)
        elif t == "text":
            txt = str(it.get("text") or "").strip()
            if not txt:
                continue
            p = tuple(it["pos"]); b = owner(p)
            if b is not None:
                bx, by, bw, bh = b["rect"]
                b["notes"].append((round((p[0] - bx) / bw, 3), round(1 - (p[1] - by) / bh, 3), txt))
                continue
            # nearest box: where the text is relative to it
            best = None
            for b in ordered:
                bx, by, bw, bh = b["rect"]
                dx = max(bx - p[0], 0, p[0] - (bx + bw)); dy = max(by - p[1], 0, p[1] - (by + bh)); d = math.hypot(dx, dy)
                if best is None or d < best[0]:
                    best = (d, b)
            b = best[1]; bx, by, bw, bh = b["rect"]
            if p[1] < by and bx - 0.1 * bw <= p[0] <= bx + 1.1 * bw:
                b["title"] = txt
            elif p[1] > by + bh:
                b["xtitle"] = txt
            elif p[0] < bx:
                b["ytitle"] = txt
            else:
                b["notes"].append((1.02, 1 - (p[1] - by) / bh, txt))
    hints = [it for it in items if it.get("type") == "hint"]
    # curves in one graph: one above the other (stacked) or crossing (overlaid)
    for b in ordered:
        if any(_inside(h["pos"], b["rect"]) and h.get("how") == "overlay" for h in hints) and len(b["curves"]) >= 2:
            b["how"] = "overlay"; continue
        cs = b["curves"]
        if len(cs) < 2:
            b["how"] = None
            continue
        lv = []
        for c in cs:
            ys = sorted(q[1] for q in c); lv.append((ys[len(ys) // 10], ys[-1 - len(ys) // 10], sum(ys) / len(ys)))
        lv.sort(key=lambda v: v[2])
        overlap = sum(max(0.0, lv[i][1] - lv[i + 1][0]) for i in range(len(lv) - 1)) / max(1e-9, sum(v[1] - v[0] for v in lv))
        b["how"] = "stack" if overlap < 0.35 else "overlay"
    n = len(ordered)
    if n == 1:
        layout = "single"
    elif ncol == 1:
        gaps = [rows[i + 1][0]["rect"][1] - (rows[i][0]["rect"][1] + rows[i][0]["rect"][3]) for i in range(len(rows) - 1)]
        layout = "panels" if all(g <= 0.12 * rows[0][0]["rect"][3] for g in gaps) else "figure"
    else:
        layout = "figure"
    orient = "Landscape" if W >= H else "Portrait"
    words = {"single": "one graph", "panels": f"{n} panels one above the other, touching (sharing the x axis)",
             "figure": f"a figure of {n} graphs, {len(rows)} row(s) x {ncol} column(s), labelled (a), (b) …"}
    lines.insert(0, f"Layout: {words[layout]}; {orient.lower()} page.")
    for k, b in enumerate(ordered):
        tag = f"Graph {k + 1}" if n > 1 else "The graph"
        bits = []
        if b["title"]: bits.append(f"title '{b['title']}'")
        if b["xtitle"]: bits.append(f"x axis '{b['xtitle']}'")
        if b["ytitle"]: bits.append(f"y axis '{b['ytitle']}'")
        if b["inset_rect"]: bits.append("a zoomed part " + ("top " if b["inset_rect"][1] > 0.4 else "bottom ") + ("right" if b["inset_rect"][0] > 0.35 else "left"))
        if b["legend_loc"]: bits.append(f"legend {b['legend_loc']}")
        if b.get("how"): bits.append(f"{len(b['curves'])} curves {'stacked (one above the other)' if b['how'] == 'stack' else 'overlaid (crossing)'}")
        if b["notes"]: bits.append(f"{len(b['notes'])} note(s)")
        lines.append(f"{tag}: " + (", ".join(bits) if bits else "as the app draws it"))
    return dict(graphs=ordered, layout=layout, rows=len(rows), cols=ncol, orientation=orient, lines=lines)


def fmt_from(g, zoom=None):
    """The format of one graph from its box of the sketch."""
    f = {}
    if g.get("title"): f["title"] = g["title"]
    if g.get("xtitle"): f["xtitle"] = g["xtitle"]
    if g.get("ytitle"): f["ytitle"] = g["ytitle"]
    if g.get("notes"): f["notes"] = [list(n) for n in g["notes"]]
    if g.get("inset_rect"):
        f["inset_rect"] = list(g["inset_rect"])
        if zoom: f["zoom"] = list(zoom)
    if g.get("legend_loc"): f["legend_loc"] = g["legend_loc"]; f["legend"] = "on"
    return f


def apply_design(w, design, zoom_text=""):
    """Lay the ticked graphs (or the one on show) out as sketched. Returns what was done, in words."""
    graphs = design.get("graphs") or []
    if not graphs:
        return "Nothing to apply: draw at least one Graph box."
    chosen = [i for i in w.ticked() if isinstance(i, sp.Item)] or ([w.current()] if isinstance(w.current(), sp.Item) else [])
    if not chosen:
        return "Tick the graphs to lay out (or show one) in Your graphs first."
    zoom = None
    if zoom_text.strip():
        import re
        m = re.findall(r"-?\d+(?:[.,]\d+)?", zoom_text)
        if len(m) >= 2:
            zoom = sorted(float(v.replace(",", ".")) for v in m[:2])
    out = []
    if design.get("orientation") and hasattr(w, "orient"):
        w.orient.setCurrentText(design["orientation"]); w.look_changed()

    def fmt_for(it, g):
        z = zoom
        if g.get("inset_rect") and not z:                     # the busiest part of the data, unless the graph already has its own zoom
            if not (it.spec and (it.spec["panels"][0].get("inset") or {}).get("xlim")):
                c = it.spec["panels"][0]["curves"][0] if it.spec and it.spec["panels"] and it.spec["panels"][0]["curves"] else None
                z = sp.auto_zoom(c["x"], c["y"]) if c is not None else None
        return fmt_from(g, z)

    layout = design["layout"]
    if layout == "single" and len(chosen) >= 2 and graphs[0].get("how"):
        how = graphs[0]["how"]; kinds = {i.kind for i in chosen}
        if len(kinds) > 1:
            return "Your sketch puts the curves in one graph, but the ticked graphs are of different kinds: tick graphs of one kind."
        w._tick_only(chosen); r = w.group_ticked(how)
        c = next((c for c in w.combined if getattr(c, "mine", False) and {id(m) for m in c.members} == {id(m) for m in chosen}), None)
        if c is not None:
            f = fmt_from(graphs[0])
            w.group_fmt = getattr(w, "group_fmt", {}); w.group_fmt[tuple(sp.key_of(m) for m in c.members)] = f
            c.fmt = f; c.build(); w.refresh_list(); w.list.setCurrentRow(w.items.index(c)); w.draw()
        out.append(f"{len(chosen)} graphs {'stacked' if how == 'stack' else 'overlaid'} in one figure ({r}).")
    elif layout == "single":
        for it in chosen:
            it.fmt = dict(getattr(it, "fmt", None) or {}, **fmt_for(it, graphs[0])); it.build(w.opt, it.kind)
        out.append(f"{len(chosen)} graph(s) laid out as your sketch.")
        w.refresh_list()
        if chosen[0] in w.items:
            w.list.setCurrentRow(w.items.index(chosen[0]))
        w.draw()
    else:
        for it, g in zip(chosen, graphs):
            it.fmt = dict(getattr(it, "fmt", None) or {}, **fmt_for(it, g)); it.build(w.opt, it.kind)
        if layout == "panels" and len({i.kind for i in chosen}) == 1 and len(chosen) >= 2:
            w._tick_only(chosen); w.group_ticked("panels")
            out.append(f"{len(chosen)} graphs as panels one above the other.")
        else:
            b = sp.Board([sp.key_of(c) for c in chosen[:len(graphs)]], design["cols"], 175.0, max([b.number for b in w.boards] + [0]) + 1)
            w.boards.append(b); w.refresh_list(); w.list.setCurrentRow(w.items.index(b)); w.draw()
            out.append(f"A panel figure: {b.title}.")
        if len(chosen) != len(graphs):
            out.append(f"Your sketch has {len(graphs)} graph box(es) and {len(chosen)} graph(s) are ticked: " + ("the first ones were used." if len(chosen) > len(graphs) else "the extra boxes stay empty."))
    w.set_status(" ".join(out))
    w.log("Design from your sketch: " + " | ".join(design.get("lines", [])) + " -> " + " ".join(out))
    return " ".join(out)


# ---------------------------------------------------------------------------------------------- the pad
def open_pad(w):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen, QPixmap
    from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QFileDialog, QGraphicsScene, QGraphicsView, QHBoxLayout, QInputDialog,
                                   QLabel, QLineEdit, QPushButton, QTextBrowser, QToolButton, QVBoxLayout)

    COL = {"box": QColor("#18222F"), "zoom": QColor("#A9542A"), "curve": QColor("#0072B2"), "legend": QColor("#2E7D32"), "text": QColor("#18222F")}

    class Pad(QGraphicsView):
        def __init__(self, dlg):
            self.sc = QGraphicsScene(0, 0, 1100, 700)
            super().__init__(self.sc)
            self.dlg = dlg; self.tool = "pen"; self.start = None; self.tmp = None; self.path = None; self.photo = None
            self.setRenderHints(self.renderHints()); self.setBackgroundBrush(QBrush(QColor("#FFFFFF")))
            self.page = self.sc.addRect(QRectF(0, 0, 1100, 700), QPen(QColor("#C9D1DA"), 1, Qt.DashLine))

        def set_size(self, W, H):
            """A page the shape of a photo (its shapes and the photo behind them then match)."""
            self.sc.setSceneRect(0, 0, W, H); self.page.setRect(QRectF(0, 0, W, H)); self.fitInView(self.page, Qt.KeepAspectRatio)

        def set_page(self, landscape):
            W, H = (1100, 700) if landscape else (700, 1000)
            self.sc.setSceneRect(0, 0, W, H); self.page.setRect(QRectF(0, 0, W, H)); self.fitInView(self.page, Qt.KeepAspectRatio)

        def resizeEvent(self, e):
            super().resizeEvent(e); self.fitInView(self.page, Qt.KeepAspectRatio)

        def tabletEvent(self, e):                       # a pen: its pressure sets the width; Qt then sends the strokes as mouse events
            self.pressure = max(0.1, float(e.pressure())); e.ignore()

        def mousePressEvent(self, e):
            p = self.mapToScene(e.position().toPoint())
            if self.tool == "select":
                return super().mousePressEvent(e)
            if self.tool == "erase":
                hit = [it for it in self.sc.items(p) if it.data(0)]
                if hit:
                    self.sc.removeItem(hit[0]); self.dlg.update_reading()
                return
            if self.tool == "pen":
                self.start = p; self.path = QPainterPath(p); self.pts = [(p.x(), p.y())]
                self.tmp = self.sc.addPath(self.path, QPen(QColor("#18222F"), 1.5 + 3.0 * getattr(self, "pressure", 0.5), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                return
            if self.tool == "text":
                t, ok = QInputDialog.getText(self, "Text", "Type it (X² as ^{2}, X₂ as _{2}):")
                if ok and t.strip():
                    it = self.sc.addText(t.strip(), QFont("Segoe UI", 14)); it.setPos(p); it.setDefaultTextColor(COL["text"])
                    it.setData(0, "text"); it.setFlag(it.GraphicsItemFlag.ItemIsMovable); it.setFlag(it.GraphicsItemFlag.ItemIsSelectable)
                    self.dlg.update_reading()
                return
            self.start = p
            if self.tool == "curve":
                self.path = QPainterPath(p); self.tmp = self.sc.addPath(self.path, QPen(COL["curve"], 3))
            else:
                pen = QPen(COL[self.tool], 2.5 if self.tool == "box" else 2, Qt.SolidLine if self.tool == "box" else Qt.DashLine)
                self.tmp = self.sc.addRect(QRectF(p, p), pen)

        def mouseMoveEvent(self, e):
            if self.tmp is None:
                return super().mouseMoveEvent(e)
            p = self.mapToScene(e.position().toPoint())
            if self.tool == "pen":
                self.path.lineTo(p); self.tmp.setPath(self.path); self.pts.append((p.x(), p.y()))
            elif self.tool == "curve":
                self.path.lineTo(p); self.tmp.setPath(self.path)
            else:
                self.tmp.setRect(QRectF(self.start, p).normalized())

        def mouseReleaseEvent(self, e):
            if self.tmp is None:
                super().mouseReleaseEvent(e); self.dlg.update_reading(); return
            it = self.tmp; self.tmp = None
            if self.tool == "pen":
                if len(self.pts) < 3:
                    self.sc.removeItem(it); return
                it.setData(0, "stroke"); it.setData(1, list(self.pts)); self.strokes_order = getattr(self, "strokes_order", []) + [it]
                it.setFlag(it.GraphicsItemFlag.ItemIsSelectable); self.dlg.update_reading(); return
            if self.tool == "curve":
                it.setData(0, "curve"); it.setData(1, [(self.path.elementAt(i).x, self.path.elementAt(i).y) for i in range(self.path.elementCount())])
            else:
                r = it.rect()
                if r.width() < 6 or r.height() < 6:
                    self.sc.removeItem(it); return
                it.setData(0, self.tool)
            it.setFlag(it.GraphicsItemFlag.ItemIsSelectable); it.setFlag(it.GraphicsItemFlag.ItemIsMovable)
            self.dlg.update_reading()

        def keyPressEvent(self, e):
            if e.key() == Qt.Key_Z and e.modifiers() & Qt.ControlModifier:          # take back the last thing drawn
                drawn = [it for it in self.sc.items() if it.data(0)]
                if drawn:
                    self.sc.removeItem(drawn[0]); self.dlg.update_reading()
                return
            if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                for it in self.sc.selectedItems():
                    self.sc.removeItem(it)
                self.dlg.update_reading()
            else:
                super().keyPressEvent(e)

        def items_data(self):
            out = []; strokes = []
            for it in self.sc.items():
                t = it.data(0)
                if t == "stroke":
                    off = it.pos(); strokes.append([(x + off.x(), y + off.y()) for x, y in (it.data(1) or [])]); continue
                if t in ("box", "zoom", "legend"):
                    r = it.mapRectToScene(it.rect()); out.append({"type": t, "rect": (r.x(), r.y(), r.width(), r.height())})
                elif t == "curve":
                    off = it.pos(); out.append({"type": "curve", "pts": [(x + off.x(), y + off.y()) for x, y in (it.data(1) or [])]})
                elif t == "text":
                    br = it.sceneBoundingRect(); out.append({"type": "text", "pos": (br.center().x(), br.center().y()), "text": it.toPlainText()})
            if strokes:
                r = self.sc.sceneRect(); out += classify_strokes(strokes, (r.width(), r.height()))
            return out

    class Dlg(QDialog):
        def __init__(self):
            super().__init__(w)
            self.setWindowTitle("Sketch a design - Origin Plot Studio"); self.resize(1250, 760)
            v = QVBoxLayout(self)
            v.addWidget(QLabel("Draw how the figure should look - with a pen, your finger on a touch screen, or the mouse (✎ Draw freely): a frame for "
                               "each graph, a small frame inside it for the zoomed part (a very small one in a corner for the legend), the curves you "
                               "expect. Or use the exact tools (▭ Graph, ◳ Zoom, ☰ Legend, 〰 Curve), and T for titles. Ctrl+Z takes back the last "
                               "stroke. A photo of your paper sketch can be put behind and traced.", wordWrap=True))
            h = QHBoxLayout(); v.addLayout(h, 1)
            bar = QVBoxLayout(); h.addLayout(bar)
            self.pad = Pad(self); grp = QButtonGroup(self)
            for key, lab, tip in TOOLS:
                b = QToolButton(); b.setText(lab); b.setToolTip(tip); b.setCheckable(True); b.setMinimumWidth(110)
                b.clicked.connect(lambda _c=False, k=key: setattr(self.pad, "tool", k)); grp.addButton(b); bar.addWidget(b)
                if key == "pen":
                    b.setChecked(True)
            self.page = QComboBox(); self.page.addItems(["Landscape page", "Portrait page"])
            self.page.activated.connect(lambda *_: (self.pad.set_page(self.page.currentIndex() == 0), self.update_reading()))
            bar.addWidget(self.page)
            ph = QPushButton("Photo to trace…"); ph.clicked.connect(self.photo); bar.addWidget(ph)
            rd = QPushButton("Read a photo of a sketch…", objectName="primary"); rd.setToolTip("A photo or scan of a sketch on paper: its frames, zoom, legend and curves become shapes on the pad (edit them, then lay out your graphs)")
            rd.clicked.connect(self.read_photo); bar.addWidget(rd)
            cl = QPushButton("Clear"); cl.clicked.connect(self.clear); bar.addWidget(cl)
            bar.addStretch(1)
            h.addWidget(self.pad, 3)
            right = QVBoxLayout(); h.addLayout(right, 1)
            right.addWidget(QLabel("<b>What the app reads from your sketch</b>"))
            self.read = QTextBrowser(); right.addWidget(self.read, 1)
            right.addWidget(QLabel("Zoomed range (optional, e.g. 27-37):"))
            self.zoom = QLineEdit(); self.zoom.setPlaceholderText("the app chooses the busiest part"); right.addWidget(self.zoom)
            ap = QPushButton("Lay out the ticked graphs like this", objectName="primary"); ap.clicked.connect(self.apply); right.addWidget(ap)
            self.msg = QLabel("", wordWrap=True); right.addWidget(self.msg)
            self.update_reading()

        def photo(self):
            p, _ = QFileDialog.getOpenFileName(self, "A photo of your sketch", "", "Pictures (*.png *.jpg *.jpeg *.bmp *.gif)")
            if p:
                self.set_photo(p)

        def set_photo(self, p):
            pm = QPixmap(p)
            if pm.isNull():
                self.msg.setText("That picture could not be read."); return False
            r = self.pad.page.rect(); pm = pm.scaled(int(r.width()), int(r.height()), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if self.pad.photo is not None:
                self.pad.sc.removeItem(self.pad.photo)
            self.pad.photo = self.pad.sc.addPixmap(pm); self.pad.photo.setOpacity(0.35); self.pad.photo.setZValue(-10)
            self.msg.setText("Trace your sketch with the tools: a Graph box over each graph, Zoom, Legend, Text, Curve.")
            return True

        def read_photo(self, path=None):
            """A photo of a sketch: what it shows becomes shapes on the pad (you can move, add or delete them), and is read at once."""
            if path is None:
                path, _ = QFileDialog.getOpenFileName(self, "A photo or scan of your sketch", "", "Pictures (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff)")
                if not path:
                    return None
            try:
                items, (PW, PH) = photo_to_items(path)
            except Exception as e:
                try:
                    import traceback, datetime, workspace_qt as _WQ
                    with open(_WQ.ERROR_LOG, "a", encoding="utf-8") as f:
                        f.write(f"\n--- {datetime.datetime.now().isoformat(timespec='seconds')}  reading a sketch photo: {path} ---\n{traceback.format_exc()}")
                except Exception: pass
                self.msg.setText(f"The photo could not be read: {e}  (the full error is in error_log.txt next to the app)"); return None
            self.page.setCurrentIndex(0 if PW >= PH else 1); self.pad.set_size(PW, PH)
            self.clear()
            ang = getattr(photo_to_items, "angle", 0.0)
            shown = path
            if ang:                                                            # behind the shapes: the photo straightened as it was read
                import tempfile
                from PIL import Image, ImageOps
                im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
                shown = os.path.join(tempfile.gettempdir(), "ops_sketch_straight.png")
                im.rotate(ang, resample=Image.BICUBIC, fillcolor=(235, 235, 235)).save(shown)
            self.set_photo(shown)
            pr = self.pad.page.rect(); kx, ky = pr.width() / PW, pr.height() / PH
            for it in items:
                if it["type"] in ("box", "zoom", "legend"):
                    x, y, w_, h_ = it["rect"]
                    g = self.pad.sc.addRect(QRectF(x * kx, y * ky, w_ * kx, h_ * ky), QPen(COL[it["type"]], 2.5, Qt.SolidLine if it["type"] == "box" else Qt.DashLine))
                    g.setData(0, it["type"])
                else:
                    pts = [(x * kx, y * ky) for x, y in it["pts"]]
                    path_ = QPainterPath(QPointF(*pts[0]))
                    for q in pts[1:]:
                        path_.lineTo(QPointF(*q))
                    g = self.pad.sc.addPath(path_, QPen(COL["curve"], 3)); g.setData(0, "curve"); g.setData(1, pts)
                g.setFlag(g.GraphicsItemFlag.ItemIsSelectable); g.setFlag(g.GraphicsItemFlag.ItemIsMovable)
            d = self.update_reading()
            n_b = sum(1 for it in items if it["type"] == "box")
            self.msg.setText(f"Read from the photo: {n_b} frame(s), " + f"{sum(1 for it in items if it['type'] == 'curve')} curve(s), "
                             + f"{sum(1 for it in items if it['type'] in ('zoom', 'legend'))} small box(es). Check the shapes (move, add, delete), type the titles with T, then lay out your graphs."
                             if n_b else "No frame found in the photo: draw one over it with ✎ or ▭ (the photo stays behind to trace).")
            return d

        def clear(self):
            for it in list(self.pad.sc.items()):
                if it.data(0):
                    self.pad.sc.removeItem(it)
            self.update_reading()

        def design(self):
            r = self.pad.sc.sceneRect()
            return read_sketch(self.pad.items_data(), (r.width(), r.height()))

        def update_reading(self):
            d = self.design()
            self.read.setHtml("<br>".join("• " + l for l in d["lines"]))
            return d

        def apply(self):
            m = apply_design(w, self.design(), self.zoom.text())
            self.msg.setText(m)
            return m

    d = Dlg()
    w.sketch_dlg = d
    d.show()
    return d

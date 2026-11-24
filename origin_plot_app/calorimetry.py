"""
calorimetry.py - isothermal calorimetry (TAM III and similar): from the instrument's Excel export to
normalised heat flow, cumulative heat, a workbook with live formulas, an Origin table and three figures.

The specification is docs/skills/iso-calorimetry-excel-processor/SKILL.md. Everything here is plain
arithmetic on the numbers of the file; no model of any kind reads or writes a data row.

ONE convention for units (the skill mentions two factors; this is the one used everywhere here):
    time (h)                  t_h   = (t - t_start) / 3600          (divisor 60 for minutes, 1 for hours)
    normalised heat flow      hf    = heat flow (W) * 1000 / mass (g)                              [mW/g]
    cumulative heat           Q_i   = Q_(i-1) + 0.5 * (hf_i + hf_(i-1)) * (t_h_i - t_h_(i-1)) * 3.6  [J/g]
because 1 mW h = 3.6 J.  A constant 1 mW/g held for 1 h gives exactly 3.6 J/g.

Rows before the end of the exclusion window are NaN in the Python data (the Excel sheet shows "Null",
as the skill asks). Cumulative heat is 0 at the first row after the window: heat released inside the
window (mixing, loading the ampoule) is not counted.
"""
import os, re, csv, math, json, shutil, hashlib, tempfile, datetime, subprocess

FACTOR = 3.6                       # J per mW h
DEFAULT_EXCLUSION_MIN = 45.0
ORIGIN_HEAD = ["Time", "Normalised Heatflow", "Cumulative Heatflow"]
ORIGIN_UNITS = ["h", "mW/g", "J/g"]
NEGATIVE_TOTAL = "Negative total: check for baseline drift"
BASELINE_NOTE = "Cumulative heat starts at 0 at the end of the exclusion window; heat released inside the window is not counted."

# one look for every figure of this module (and the one the composed paper figures use): landscape, one font, no chart junk
STYLE = {"size_in": (11.7, 6.5), "font": ["Arial", "Liberation Sans", "DejaVu Sans"], "axis_title": 13, "tick_label": 11, "label": 11, "axis_lw": 0.9, "curve_lw": 1.8, "dpi": 300}
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000", "#F0E442"]        # Okabe-Ito: safe for colour-blind readers
LINESTYLES = ["-", "--", "-.", ":", (0, (5, 1)), (0, (3, 1, 1, 1)), (0, (1, 1)), (0, (7, 2, 2, 2))]

TIME_HEAD = re.compile(r"^\s*(time|t|zeit)\b", re.I)
HEAT_HEAD = re.compile(r"(heat\s*flow|w[äa]rmefluss|^\s*hf\b)", re.I)
MARK_HEAD = re.compile(r"(marker|event|reaction\s*start)", re.I)
REACTION = re.compile(r"reaction\s*start", re.I)


class CalorimetryError(ValueError):
    """The run is refused: nothing is written."""


# ---------------------------------------------------------------------------------------------- reading
def _letter(col):
    from openpyxl.utils import get_column_letter
    return get_column_letter(col)

def _unit_in(text):
    m = re.search(r"[\(\[/]\s*(m?W/g|m?W|s|sec|min|h|hours?)\s*[\)\]]?\s*$", str(text or ""), re.I)
    return m.group(1) if m else ""

def _norm_unit(u):
    u = str(u or "").strip().replace("·", "").replace(" ", "")
    low = u.lower()
    if low in ("s", "sec", "second", "seconds"): return "s"
    if low in ("min", "minute", "minutes"): return "min"
    if low in ("h", "hr", "hour", "hours"): return "h"
    if low in ("w", "mw", "w/g", "mw/g"): return {"w": "W", "mw": "mW", "w/g": "W/g", "mw/g": "mW/g"}[low]
    return u

def _open(path, sheet=None):
    """The workbook as openpyxl sheets. A .csv is loaded into a workbook in memory, so one code path reads both."""
    import openpyxl
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(path); ws = wb[sheet] if sheet else wb.worksheets[0]; return wb, ws
    if ext in (".csv", ".txt"):
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Data"
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample = f.read(4096); f.seek(0)
            try: dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except Exception: dialect = csv.excel
            for row in csv.reader(f, dialect):
                out = []
                for c in row:
                    try: out.append(float(c.replace(",", ".")) if dialect.delimiter == ";" else float(c))
                    except ValueError: out.append(c if c != "" else None)
                ws.append(out)
        return wb, ws
    raise CalorimetryError(f"'{os.path.basename(path)}' is not an Excel workbook (.xlsx) or a .csv table")

def read(path, sheet=None):
    """Find the columns by their headers (never by assumed letters) and read the numbers.
    Returns a dict: sheet, header_row, first_data_row, last_data_row, columns {time, heat, marker: letter},
    units {time, heat}, reaction_row (or None), rows [(row number, time, heat flow)], sha256, path."""
    wb, ws = _open(path, sheet)
    found = None
    for hr in (1, 2, 3):
        cells = [(c, ws.cell(row=hr, column=c).value) for c in range(1, ws.max_column + 1)]
        tcol = next((c for c, v in cells if isinstance(v, str) and TIME_HEAD.search(v)), None)
        hcol = next((c for c, v in cells if isinstance(v, str) and HEAT_HEAD.search(v)), None)
        if tcol and hcol:
            mcol = next((c for c, v in cells if isinstance(v, str) and MARK_HEAD.search(v) and c not in (tcol, hcol)), None); found = (hr, tcol, hcol, mcol); break
    if not found:
        heads = [str(v) for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ()) if v is not None]
        raise CalorimetryError("I found no 'Time' and 'Heat flow' column headers in rows 1 to 3 of the sheet (row 1 holds: " + ", ".join(heads)[:160] + ")")
    hr, tcol, hcol, mcol = found
    below = ws.cell(row=hr + 1, column=tcol).value; unit_row = hr + 1 if isinstance(below, str) else None
    tu = _norm_unit(ws.cell(row=unit_row, column=tcol).value if unit_row else _unit_in(ws.cell(row=hr, column=tcol).value))
    hu = _norm_unit(ws.cell(row=unit_row, column=hcol).value if unit_row else _unit_in(ws.cell(row=hr, column=hcol).value))
    if tu not in ("s", "min", "h"): raise CalorimetryError(f"the unit of the time column {_letter(tcol)} is '{tu or 'not given'}'; I need s, min or h (in the row under the header, or in the header as 'Time (s)')")
    if hu not in ("W", "mW", "W/g", "mW/g"): raise CalorimetryError(f"the unit of the heat-flow column {_letter(hcol)} is '{hu or 'not given'}'; I need W, mW, W/g or mW/g")
    first = (unit_row or hr) + 1; rows = []; reaction = None
    for r in range(first, ws.max_row + 1):
        t, h = ws.cell(row=r, column=tcol).value, ws.cell(row=r, column=hcol).value
        if mcol and reaction is None and isinstance(ws.cell(row=r, column=mcol).value, str) and REACTION.search(ws.cell(row=r, column=mcol).value): reaction = r
        if isinstance(t, (int, float)) and not isinstance(t, bool) and isinstance(h, (int, float)) and not isinstance(h, bool) and math.isfinite(t) and math.isfinite(h): rows.append((r, float(t), float(h)))
    if len(rows) < 3: raise CalorimetryError("the sheet holds fewer than three rows with a time and a heat flow")
    with open(path, "rb") as f: sha = hashlib.sha256(f.read()).hexdigest()
    return {"path": os.path.abspath(path), "file": os.path.basename(path), "sha256": sha, "sheet": ws.title, "header_row": hr, "unit_row": unit_row, "first_data_row": rows[0][0], "last_data_row": rows[-1][0],
            "columns": {"time": _letter(tcol), "heat": _letter(hcol), "marker": _letter(mcol) if mcol else None}, "col_index": {"time": tcol, "heat": hcol, "marker": mcol},
            "units": {"time": tu, "heat": hu}, "reaction_row": reaction, "rows": rows, "max_column": ws.max_column}


# ---------------------------------------------------------------------------------------------- the calculation
def validate(parsed, mass_g, exclusion_min, reaction_row):
    """Refuse a run that cannot give right numbers. Returns (mass, exclusion, reaction row) as numbers."""
    try: mass = float(mass_g)
    except (TypeError, ValueError): raise CalorimetryError("the sample mass (g) is missing: enter it. It is on the run log of the calorimeter")
    if not math.isfinite(mass) or mass <= 0: raise CalorimetryError(f"the sample mass must be larger than 0 g (it is {mass_g}). Nothing was calculated")
    try: excl = float(exclusion_min)
    except (TypeError, ValueError): raise CalorimetryError("the exclusion window (min) is missing: enter it (the usual value is 45)")
    if not math.isfinite(excl) or excl < 0: raise CalorimetryError("the exclusion window must be 0 min or longer")
    rr = reaction_row if reaction_row not in (None, "") else parsed["reaction_row"]
    if rr in (None, ""): raise CalorimetryError("the file has no 'Reaction start' marker: enter the row of the sheet at which the reaction started")
    try: rr = int(rr)
    except (TypeError, ValueError): raise CalorimetryError("the reaction-start row must be a row number of the sheet")
    if rr not in {r for r, _, _ in parsed["rows"]}: raise CalorimetryError(f"row {rr} is not a data row of the sheet (data are in rows {parsed['first_data_row']} to {parsed['last_data_row']})")
    return mass, excl, rr

def integrate(t_h, hf):
    """Cumulative heat (J/g) by the trapezoid rule over rows that are not NaN; 0 at the first of them. NaN rows stay NaN."""
    out = []; prev = None; q = 0.0
    for t, h in zip(t_h, hf):
        if h != h: out.append(float("nan")); continue
        if prev is not None: q += 0.5 * (h + prev[1]) * (t - prev[0]) * FACTOR
        out.append(q); prev = (t, h)
    return out

def compute(parsed, mass_g, exclusion_min=DEFAULT_EXCLUSION_MIN, reaction_row=None, name=None):
    """Normalised heat flow (mW/g) and cumulative heat (J/g). Returns a dict with the numbers, the inputs used and warnings."""
    mass, excl, rr = validate(parsed, mass_g, exclusion_min, reaction_row)
    div = {"s": 3600.0, "min": 60.0, "h": 1.0}[parsed["units"]["time"]]; hu = parsed["units"]["heat"]
    scale = {"W": 1000.0 / mass, "mW": 1.0 / mass, "W/g": 1000.0, "mW/g": 1.0}[hu]
    t0 = next(t for r, t, _ in parsed["rows"] if r == rr); cutoff = excl / 60.0
    rows = [r for r, _, _ in parsed["rows"]]; t_h = [(t - t0) / div for _, t, _ in parsed["rows"]]
    hf = [(h * scale if th >= cutoff else float("nan")) for (_, _, h), th in zip(parsed["rows"], t_h)]
    q = integrate(t_h, hf); kept = [i for i, v in enumerate(hf) if v == v]; warn = []
    if not kept: warn.append(f"The exclusion window ({excl:g} min) is longer than the experiment ({max(t_h) * 60:.0f} min after the reaction start): no row is left and the cumulative heat is zero.")
    total = q[kept[-1]] if kept else 0.0
    if total < 0: warn.append(NEGATIVE_TOTAL)
    return {"name": name or os.path.splitext(parsed["file"])[0], "rows": rows, "time_h": t_h, "heat_flow_mWg": hf, "cumulative_Jg": q, "kept": kept, "excluded_rows": len(rows) - len(kept),
            "total_Jg": total, "total_kJkg": total, "mass_g": mass, "exclusion_min": excl, "cutoff_h": cutoff, "reaction_row": rr, "t_start": t0, "time_divisor": div, "heat_unit": hu,
            "mass_used": hu in ("W", "mW"), "factor": FACTOR, "warnings": warn, "duration_h": max(t_h)}


# ---------------------------------------------------------------------------------------------- the workbook
def write_workbook(parsed, res, out_path):
    """The source sheet plus helper cells, three formula columns, summary cells, two charts and the 'Origin Export' sheet.
    Every formula refers to the helper cells: changing the exclusion window or the mass in Excel changes all results."""
    from openpyxl.styles import Font, PatternFill
    from openpyxl.chart import ScatterChart, Reference, Series
    from openpyxl.comments import Comment
    wb, ws = _open(parsed["path"], parsed["sheet"] if os.path.splitext(parsed["path"])[1].lower() in (".xlsx", ".xlsm") else None)
    ci = parsed["col_index"]; L = _letter; hr = parsed["header_row"]; ur = parsed["unit_row"]; f0, f1 = parsed["first_data_row"], parsed["last_data_row"]; rr = res["reaction_row"]
    hcol = parsed["max_column"] + 2; pcol = hcol + 4; qcol, rcol = pcol + 1, pcol + 2            # helper cells two columns to the right, the three results after them
    blue, yellow, bold = Font(color="0000FF", bold=True), PatternFill("solid", fgColor="FFFF00"), Font(bold=True)
    def put(r, c, v, font=None, fill=None):
        cell = ws.cell(row=r, column=c, value=v)
        if font: cell.font = font
        if fill: cell.fill = fill
        return cell
    put(rr, hcol, "Exclusion window (min)", bold); put(rr, hcol + 1, res["exclusion_min"], blue, yellow); put(rr, hcol + 2, "Cutoff (h)", bold); put(rr, hcol + 3, f"={L(hcol + 1)}{rr}/60")
    put(rr + 1, hcol, "t_start (" + parsed["units"]["time"] + ")", bold); put(rr + 1, hcol + 1, f"={L(ci['time'])}{rr}")
    put(rr + 2, hcol, "Sample mass (g)", bold); put(rr + 2, hcol + 1, res["mass_g"], blue, yellow)
    excl_c, cut_c, t0_c, mass_c = f"${L(hcol + 1)}${rr}", f"${L(hcol + 3)}${rr}", f"${L(hcol + 1)}${rr + 1}", f"${L(hcol + 1)}${rr + 2}"
    put(hr, pcol, "Time (h)", bold); put(hr, qcol, "Normalised Heat flow (mW/g)", bold); put(hr, rcol, "Cumulative heat (J/g)", bold)
    if ur: put(ur, pcol, "h"); put(ur, qcol, "mW/g"); put(ur, rcol, "J/g")
    hu = parsed["units"]["heat"]; norm = {"W": f"*1000/{mass_c}", "mW": f"/{mass_c}", "W/g": "*1000", "mW/g": ""}[hu]
    ws.cell(row=hr, column=rcol).comment = Comment(f"Heat flow in mW/g, time in h: trapezoid increment x {FACTOR:g} gives J/g (1 mW h = 3.6 J). " + BASELINE_NOTE, "Origin Plot Studio")
    P, Q, R, T, H = L(pcol), L(qcol), L(rcol), L(ci["time"]), L(ci["heat"]); data_rows = [r for r in res["rows"]]
    for k, r in enumerate(data_rows):
        ws.cell(row=r, column=pcol, value=f"=({T}{r}-{t0_c})/{res['time_divisor']:g}")
        ws.cell(row=r, column=qcol, value=f'=IF({P}{r}<{cut_c},"Null",{H}{r}{norm})')
        if k == 0: ws.cell(row=r, column=rcol, value=f'=IF({Q}{r}="Null",0,0)')
        else:
            p = data_rows[k - 1]
            ws.cell(row=r, column=rcol, value=f'=IF({Q}{r}="Null",0,IF({Q}{p}="Null",0,({Q}{r}+{Q}{p})/2*({P}{r}-{P}{p})*{FACTOR:g}+{R}{p}))')
    put(rr + 4, hcol, "Total heat (J/g)", bold); put(rr + 4, hcol + 1, f"={R}{f1}"); tot_c = f"{L(hcol + 1)}{rr + 4}"
    put(rr + 5, hcol, "Total heat (kJ/kg)", bold); put(rr + 5, hcol + 1, f"={tot_c}")
    put(rr + 6, hcol, f'=IF({tot_c}<0,"{NEGATIVE_TOTAL}","")', Font(color="C00000", bold=True))
    put(rr + 7, hcol, BASELINE_NOTE, Font(italic=True, color="555555"))
    for c, w in ((hcol, 26), (hcol + 1, 12), (hcol + 2, 12), (hcol + 3, 12), (pcol, 12), (qcol, 30), (rcol, 22)): ws.column_dimensions[L(c)].width = w
    for k, (col, title, ytitle) in enumerate(((qcol, "Normalised heat flow vs. time", "Normalised heat flow (mW/g)"), (rcol, "Cumulative heat vs. time", "Cumulative heat (J/g)"))):
        ch = ScatterChart(); ch.style = 10; ch.title = title; ch.x_axis.title = "Time (h)"; ch.y_axis.title = ytitle; ch.height, ch.width = 9, 17; ch.legend = None
        s = Series(Reference(ws, min_col=col, min_row=f0, max_row=f1), Reference(ws, min_col=pcol, min_row=f0, max_row=f1), title=ytitle); s.smooth = True; s.marker.symbol = "none"; ch.series.append(s)
        ws.add_chart(ch, f"{L(rcol + 2)}{max(2, hr) + k * 20}")
    if "Origin Export" in wb.sheetnames: del wb["Origin Export"]                              # never keep stale rows of an earlier run
    we = wb.create_sheet("Origin Export"); we.append(ORIGIN_HEAD); we.append(ORIGIN_UNITS)
    for row in origin_rows(res): we.append(row)
    wb.save(out_path)
    return {"helper": {"exclusion_min": excl_c.replace("$", ""), "cutoff_h": cut_c.replace("$", ""), "t_start": t0_c.replace("$", ""), "mass_g": mass_c.replace("$", ""), "total_Jg": tot_c},
            "output_columns": {"time_h": P, "heat_flow_mWg": Q, "cumulative_Jg": R}, "pcol": pcol, "qcol": qcol, "rcol": rcol, "total_cell": tot_c}

def origin_rows(res):
    """The rows after the exclusion window as plain numbers: time (h), normalised heat flow (mW/g), cumulative heat (J/g)."""
    return [[res["time_h"][i], res["heat_flow_mWg"][i], res["cumulative_Jg"][i]] for i in res["kept"]]

def write_origin_csv(res, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(ORIGIN_HEAD); w.writerow(ORIGIN_UNITS)
        for row in origin_rows(res): w.writerow([repr(float(v)) for v in row])

def soffice():
    for exe in ("soffice", "libreoffice", "soffice.exe"):
        p = shutil.which(exe)
        if p: return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if os.path.isfile(p): return p
    return None

def recalc_check(xlsx, parsed, res, layout, rtol=1e-6):
    """Let LibreOffice calculate the formulas, read the values back and compare them with the Python numbers.
    Returns {"done": bool, "ok": bool, "compared": n, "mismatches": [...], "errors": [...], "note": str}."""
    import openpyxl
    exe = soffice()
    if not exe: return {"done": False, "ok": None, "compared": 0, "mismatches": [], "errors": [], "note": "LibreOffice is not installed: the formulas of the workbook were NOT recalculated and compared (the numbers of the Origin table come from the same arithmetic in Python)"}
    work = tempfile.mkdtemp(prefix="calo_recalc_")
    try:
        prof = os.path.join(work, "profile"); r = subprocess.run([exe, f"-env:UserInstallation=file://{prof.replace(os.sep, '/')}" if os.name != "nt" else f"-env:UserInstallation=file:///{prof.replace(os.sep, '/')}", "--headless", "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", work, xlsx],
                                                              capture_output=True, text=True, timeout=240, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = os.path.join(work, os.path.basename(xlsx))
        if not os.path.isfile(out): return {"done": False, "ok": None, "compared": 0, "mismatches": [], "errors": [], "note": "LibreOffice could not recalculate the workbook: " + (r.stderr or r.stdout or "no output")[-200:]}
        ws = openpyxl.load_workbook(out, data_only=True)[parsed["sheet"] if parsed["sheet"] in openpyxl.load_workbook(out, read_only=True).sheetnames else "Data"]
        bad, errs, n = [], [], 0
        for i, row in enumerate(res["rows"]):
            for col, py, nm in ((layout["pcol"], res["time_h"][i], "Time (h)"), (layout["qcol"], res["heat_flow_mWg"][i], "heat flow"), (layout["rcol"], res["cumulative_Jg"][i], "cumulative heat")):
                v = ws.cell(row=row, column=col).value
                if isinstance(v, str) and v.startswith("#"): errs.append(f"{_letter(col)}{row}: {v}"); continue
                if py != py:                                    # excluded row: the sheet shows "Null" (heat flow) and 0 (cumulative heat)
                    if not ((nm == "heat flow" and v == "Null") or (nm == "cumulative heat" and v in (0, 0.0))): bad.append(f"{_letter(col)}{row}: sheet {v!r}, expected an excluded row")
                    continue
                n += 1
                if not isinstance(v, (int, float)) or abs(v - py) > rtol * max(abs(py), 1e-12) + 1e-12: bad.append(f"{_letter(col)}{row}: sheet {v!r}, Python {py!r}")
        m = re.match(r"([A-Z]+)(\d+)", layout["total_cell"]); from openpyxl.utils import column_index_from_string
        tv = ws.cell(row=int(m.group(2)), column=column_index_from_string(m.group(1))).value
        if not isinstance(tv, (int, float)) or abs(tv - res["total_Jg"]) > rtol * max(abs(res["total_Jg"]), 1e-12) + 1e-12: bad.append(f"total heat: sheet {tv!r}, Python {res['total_Jg']!r}")
        return {"done": True, "ok": not bad and not errs, "compared": n, "mismatches": bad[:20], "errors": errs[:20], "note": f"LibreOffice recalculated the workbook: {n} values compared with Python at relative tolerance {rtol:g}"}
    finally: shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- figures
def _mpl():
    import matplotlib
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    rc = {"font.family": "sans-serif", "font.sans-serif": STYLE["font"], "pdf.fonttype": 42, "axes.unicode_minus": True, "mathtext.default": "regular"}
    return matplotlib, Figure, FigureCanvasAgg, rc

def _axes(ax):
    for s in ax.spines.values(): s.set_linewidth(STYLE["axis_lw"])
    ax.tick_params(direction="in", width=STYLE["axis_lw"], length=4, labelsize=STYLE["tick_label"]); ax.grid(False); ax.set_facecolor("white"); ax.margins(x=0)

def _end_labels(ax, items, fig):
    """A name at the right end of each curve, moved apart where two would touch."""
    fig.canvas.draw(); lo, hi = ax.get_ylim(); gap = 0.045 * (hi - lo); ys = sorted(((y, k) for k, (_, y, _, _) in enumerate(items))); placed = {}
    last = None
    for y, k in ys:
        y2 = y if last is None or y - last >= gap else last + gap; placed[k] = y2; last = y2
    for k, (x, y, text, colour) in enumerate(items):
        ax.annotate(text, xy=(x, y), xytext=(x + 0.012 * (ax.get_xlim()[1] - ax.get_xlim()[0]), placed[k]), color=colour, fontsize=STYLE["label"], va="center", ha="left", annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=colour, lw=0.5) if abs(placed[k] - y) > 1e-9 else None)

def _save(fig, rc, base):
    import matplotlib
    out = []
    with matplotlib.rc_context(rc):
        for ext in ("png", "pdf"): p = f"{base}.{ext}"; fig.savefig(p, dpi=STYLE["dpi"] if ext == "png" else None, facecolor="white"); out.append(p)
    return out

def figure_single(res, base):
    """C1: normalised heat flow (left axis) and cumulative heat (right axis) against time, in one landscape graph."""
    import numpy as np
    matplotlib, Figure, Canvas, rc = _mpl()
    with matplotlib.rc_context(rc):
        fig = Figure(figsize=STYLE["size_in"], facecolor="white"); Canvas(fig); ax = fig.add_axes([0.085, 0.13, 0.80, 0.80]); ax2 = ax.twinx()
        k = res["kept"]; t = np.array([res["time_h"][i] for i in k]); hf = np.array([res["heat_flow_mWg"][i] for i in k]); q = np.array([res["cumulative_Jg"][i] for i in k]); c1, c2 = PALETTE[0], PALETTE[1]
        ax.plot(t, hf, color=c1, lw=STYLE["curve_lw"], ls="-"); ax2.plot(t, q, color=c2, lw=STYLE["curve_lw"], ls="--")
        _axes(ax); _axes(ax2); ax.set_xlabel("Time (h)", fontsize=STYLE["axis_title"]); ax.set_ylabel("Normalised heat flow (mW/g)", fontsize=STYLE["axis_title"], color=c1); ax2.set_ylabel("Cumulative heat (J/g)", fontsize=STYLE["axis_title"], color=c2)
        ax.tick_params(axis="y", colors=c1); ax2.tick_params(axis="y", colors=c2); ax.spines["left"].set_color(c1); ax2.spines["right"].set_color(c2); ax2.spines["left"].set_visible(False); ax.spines["right"].set_visible(False)
        if len(t):
            ax.set_xlim(0 if t[0] >= 0 else t[0], t[-1]); ax.set_ylim(min(0, float(hf.min())), float(hf.max()) * 1.08 if hf.max() > 0 else 1); ax2.set_ylim(min(0, float(q.min())), float(q.max()) * 1.08 if q.max() > 0 else 1)
            ip = int(np.argmax(hf)); ax.annotate("Heat flow", xy=(t[ip], hf[ip]), xytext=(10, 4), textcoords="offset points", color=c1, fontsize=STYLE["label"], va="bottom", ha="left")
            iq = int(len(t) * 0.72); ax2.annotate("Cumulative heat", xy=(t[iq], q[iq]), xytext=(0, 9), textcoords="offset points", color=c2, fontsize=STYLE["label"], va="bottom", ha="center")
        fig.text(0.085, 0.045, f"{res['name']}   ·   {res['mass_g']:g} g   ·   exclusion window {res['exclusion_min']:g} min   ·   total {res['total_Jg']:.1f} J/g.  " + BASELINE_NOTE, fontsize=STYLE["label"] - 2, color="#444444", ha="left", va="bottom")
    return _save(fig, rc, base)

def figure_overlay(results, which, base):
    """C2 (which='cumulative') and C3 (which='heat_flow'): one line per sample on common axes, names at the line ends."""
    import numpy as np
    matplotlib, Figure, Canvas, rc = _mpl()
    key, ytitle = ("cumulative_Jg", "Cumulative heat (J/g)") if which == "cumulative" else ("heat_flow_mWg", "Normalised heat flow (mW/g)")
    with matplotlib.rc_context(rc):
        fig = Figure(figsize=STYLE["size_in"], facecolor="white"); Canvas(fig); ax = fig.add_axes([0.085, 0.13, 0.76, 0.80]); items = []; tmax = 0.0; ymax = 0.0; ymin = 0.0
        for n, res in enumerate(results):
            k = res["kept"]
            if not k: continue
            t = np.array([res["time_h"][i] for i in k]); y = np.array([res[key][i] for i in k]); col = PALETTE[n % len(PALETTE)]
            ax.plot(t, y, color=col, lw=STYLE["curve_lw"], ls=LINESTYLES[(n // len(PALETTE)) % len(LINESTYLES)]); items.append((t[-1], float(y[-1]), res["name"], col)); tmax = max(tmax, float(t[-1])); ymax = max(ymax, float(y.max())); ymin = min(ymin, float(y.min()))
        _axes(ax); ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False); ax.set_xlabel("Time (h)", fontsize=STYLE["axis_title"]); ax.set_ylabel(ytitle, fontsize=STYLE["axis_title"])
        if items: ax.set_xlim(0, tmax); ax.set_ylim(ymin, ymax * 1.06 if ymax > 0 else 1); _end_labels(ax, items, fig)
        excl = sorted({r["exclusion_min"] for r in results}); fig.text(0.085, 0.045, ("Exclusion window " + ", ".join(f"{e:g}" for e in excl) + " min.  " + BASELINE_NOTE) if which == "cumulative" else "Normalised to the sample mass.  Exclusion window " + ", ".join(f"{e:g}" for e in excl) + " min.", fontsize=STYLE["label"] - 2, color="#444444", ha="left", va="bottom")
    return _save(fig, rc, base)

def origin_spec(results, which):
    """The same graphs as figure specs of the app, for drawing in Origin when OriginPro is there (smart_plots layout)."""
    def curve(label, x, y, colour): return dict(label=label, x=list(x), y=list(y), colour=colour, style="line", width=None)
    def rgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    if which == "single":
        r = results[0]; k = r["kept"]; t = [r["time_h"][i] for i in k]
        p = dict(yname="Normalised heat flow (mW/g)", curves=[curve("Heat flow", t, [r["heat_flow_mWg"][i] for i in k], rgb(PALETTE[0]))], weight=1.0, labels=[], vlines=[], ylim=None, vertical=True, legend=False)
        p["y2"] = dict(curves=[curve("Cumulative heat", t, [r["cumulative_Jg"][i] for i in k], rgb(PALETTE[1]))], yname="Cumulative heat (J/g)", ylim=None, labels=[])
        return dict(title=r["name"], xname="Time (h)", panels=[p], no_title=True, page_in=STYLE["size_in"])
    key, yn = ("cumulative_Jg", "Cumulative heat (J/g)") if which == "cumulative" else ("heat_flow_mWg", "Normalised heat flow (mW/g)")
    cs = [curve(r["name"], [r["time_h"][i] for i in r["kept"]], [r[key][i] for i in r["kept"]], rgb(PALETTE[n % len(PALETTE)])) for n, r in enumerate(results) if r["kept"]]
    return dict(title=yn, xname="Time (h)", panels=[dict(yname=yn, curves=cs, weight=1.0, labels=[], vlines=[], ylim=None, vertical=True, legend=True)], no_title=True, page_in=STYLE["size_in"])


# ---------------------------------------------------------------------------------------------- one run
def run(inputs, out_dir, app_version="", log=None, origin_draw=None):
    """inputs: [{"path", "mass_g", "exclusion_min", "reaction_row" (optional), "name" (optional), "sheet" (optional)}, ...]
    Everything is checked first: if one input is refused, nothing at all is written.
    Returns {"samples": [...], "figures": [...], "warnings": [...], "files": [...]}.  origin_draw(spec, tag) draws a spec in Origin."""
    say = log or (lambda m: None)
    if not inputs: raise CalorimetryError("no calorimetry file was given")
    done = []
    for inp in inputs:                                         # 1. read and check everything
        parsed = read(inp["path"], inp.get("sheet")); res = compute(parsed, inp.get("mass_g"), inp.get("exclusion_min", DEFAULT_EXCLUSION_MIN), inp.get("reaction_row"), inp.get("name")); done.append((parsed, res))
    os.makedirs(out_dir, exist_ok=True); files, warns, samples, figs = [], [], [], []
    for parsed, res in done:                                    # 2. write
        stem = re.sub(r'[\\/:*?"<>|]+', "_", res["name"]); xlsx = os.path.join(out_dir, stem + "_calorimetry.xlsx"); layout = write_workbook(parsed, res, xlsx); csvp = os.path.join(out_dir, stem + "_origin_export.csv"); write_origin_csv(res, csvp)
        chk = recalc_check(xlsx, parsed, res, layout); say(f"{res['name']}: {chk['note']}")
        if chk["done"] and not chk["ok"]: raise CalorimetryError(f"{res['name']}: the workbook's formulas do not give the numbers calculated in Python: " + "; ".join((chk["errors"] + chk["mismatches"])[:4]))
        f1 = figure_single(res, os.path.join(out_dir, stem + "_C1_heat_flow_and_cumulative_heat")); figs += f1
        for w in res["warnings"]: warns.append(f"{res['name']}: {w}"); say("   note: " + w)
        prov = {"what": "isothermal calorimetry", "input_file": parsed["file"], "input_sha256": parsed["sha256"], "sheet": parsed["sheet"], "columns": parsed["columns"], "units_in_file": parsed["units"],
                "reaction_start_row": res["reaction_row"], "reaction_start_from": "marker in the file" if parsed["reaction_row"] == res["reaction_row"] else "entered by the user", "exclusion_window_min": res["exclusion_min"],
                "sample_mass_g": res["mass_g"], "sample_mass_used_in_normalisation": res["mass_used"], "factor_J_per_mWh": FACTOR, "cumulative_heat_baseline": BASELINE_NOTE, "rows_excluded": res["excluded_rows"], "rows_kept": len(res["kept"]),
                "total_heat_J_per_g": res["total_Jg"], "helper_cells": layout["helper"], "output_columns": layout["output_columns"], "excel_recalculation_check": {k: chk[k] for k in ("done", "ok", "compared", "note")}, "warnings": res["warnings"],
                "outputs": [os.path.basename(p) for p in [xlsx, csvp] + f1]}
        pp = write_provenance(os.path.join(out_dir, stem + "_calorimetry"), prov, app_version); files += [xlsx, csvp, pp] + f1
        samples.append({"name": res["name"], "total_Jg": res["total_Jg"], "excluded_rows": res["excluded_rows"], "workbook": xlsx, "origin_csv": csvp, "provenance": pp, "columns": parsed["columns"], "reaction_row": res["reaction_row"], "recalc": chk, "warnings": res["warnings"]})
        if origin_draw: origin_draw(origin_spec([res], "single"), stem + "_C1")
    results = [r for _, r in done]
    f2 = figure_overlay(results, "cumulative", os.path.join(out_dir, "C2_cumulative_heat_all_samples")); f3 = figure_overlay(results, "heat_flow", os.path.join(out_dir, "C3_heat_flow_all_samples")); figs += f2 + f3; files += f2 + f3
    try:                                                       # C4: heat flow (with the first hours as inset) beside cumulative heat; C5: Q at a time as bars
        f45 = figure_pair_and_bar(done, inputs, out_dir, app_version, say)
        figs += [f for f in f45 if f.endswith((".png", ".pdf"))]; files += f45
    except Exception as e:                                     # noqa: BLE001
        say(f"   the pair figure (C4) and the bar chart (C5) could not be drawn: {e}")
    for base, which in ((f2[0], "cumulative"), (f3[0], "heat_flow")):
        files.append(write_provenance(os.path.splitext(base)[0], {"what": "isothermal calorimetry, overlay of " + which.replace("_", " "), "inputs": [{"file": p["file"], "sha256": p["sha256"], "sample_mass_g": r["mass_g"], "exclusion_window_min": r["exclusion_min"], "reaction_start_row": r["reaction_row"]} for p, r in done], "factor_J_per_mWh": FACTOR, "cumulative_heat_baseline": BASELINE_NOTE}, app_version))
    if origin_draw:
        origin_draw(origin_spec(results, "cumulative"), "C2_cumulative_heat"); origin_draw(origin_spec(results, "heat_flow"), "C3_heat_flow")
    return {"samples": samples, "figures": figs, "warnings": warns, "files": files, "folder": out_dir}

def figure_pair_and_bar(done, inputs, out_dir, app_version="", say=None):
    """C4 (heat flow with an inset of the first hours, beside cumulative heat; regimes as labels and brackets) and C5 (Q at a time per
    sample, per unit alite when given), drawn by gallery_graphs from these results. Labels, regimes and alite fractions only from the inputs."""
    import numpy as np, pandas as pd
    import gallery_graphs as tg
    frames, rows = {}, []
    for (parsed, res), inp in zip(done, inputs):
        nm = str(inp.get("label") or res["name"])
        t = np.asarray(res["time_h"], float); hf = np.asarray(res["heat_flow_mWg"], float); q = np.asarray(res["cumulative_Jg"], float)
        q = np.where(np.isfinite(hf), q, np.nan)
        key = re.sub(r'[\\/:*?"<>|\[\]]+', "_", nm)[:31] or f"sample {len(frames) + 1}"
        frames[key] = pd.DataFrame({"Time (h)": t, f"Heat flow {key} (mW/g)": hf, f"Cumulative heat {key} (J/g)": q})
        rows.append({"Sample": key, "Label": nm, "Regime": inp.get("regime") or "", "Alite fraction": inp.get("alite") if inp.get("alite") else "", "Colour": inp.get("colour") or ""})
    frames["Samples"] = pd.DataFrame(rows)
    opts = {"exclusion_min": 0}
    if inputs and inputs[0].get("bar_at_h"):
        opts["bar_at_h"] = inputs[0]["bar_at_h"]
    book = tg.book_from_frames(frames, "calorimetry", opts)
    files, r = tg.save("G10", book, out_dir, base="C4_heat_flow_and_cumulative_heat_pair", dpi=300, extra_scale=1.0)
    if len(done) >= 2 and not any(f.endswith("_Q_bar.png") for f in files):
        files += tg.save_extra(tg.draw_g10_bar, book, out_dir, "C4_heat_flow_and_cumulative_heat_pair_Q_bar", ("png", "pdf"), r, dpi=300, scale=1.0)
    out = []
    for f in files:                                            # C5 name for the bar chart (one sample: no bar chart)
        if "_Q_bar" in f and len(done) < 2:
            os.remove(f); continue
        if "_Q_bar" in f:
            g = f.replace("C4_heat_flow_and_cumulative_heat_pair_Q_bar", "C5_cumulative_heat_at_time_bars")
            os.replace(f, g); out.append(g)
        else:
            out.append(f)
    facts = {"what": "isothermal calorimetry: C4 heat flow + cumulative heat pair, C5 Q at a time", "notes": r.notes,
             "samples": rows, "inputs": [{"file": p["file"], "sha256": p["sha256"], "sample_mass_g": rr["mass_g"], "exclusion_window_min": rr["exclusion_min"]} for p, rr in done],
             "factor_J_per_mWh": FACTOR, "cumulative_heat_baseline": BASELINE_NOTE}
    for k, v in r.tables.items():
        facts["table: " + k] = v.to_dict(orient="records")
    out.append(write_provenance(os.path.join(out_dir, "C4_C5_calorimetry"), facts, app_version))
    if say:
        say("   C4 pair figure and C5 bar chart drawn (labels, regimes and alite fractions only from what you entered)")
    return out


def write_provenance(base, facts, app_version=""):
    """<base>_provenance.json: what was read, with which settings, by which version. Never holds a key or a data row."""
    d = {"written": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "app": "Origin Plot Studio", "app_version": app_version}
    d.update(facts); p = base + "_provenance.json"
    with open(p, "w", encoding="utf-8") as f: json.dump(d, f, indent=1, ensure_ascii=False, default=str)
    return p

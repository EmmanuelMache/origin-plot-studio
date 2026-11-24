"""
Origin plot app (OriginPro 2018 and newer, Windows).

Tab "Smart plots":      add any Excel / CSV / TXT files. Every sheet is examined and recognised
        as XRD, observed + calculated fit, FTIR, TGA, particle size distribution, calorimetry
        or plain XY; the analysis that kind of graph needs is done (peak positions, DTG and
        mass-loss steps, D10/D50/D90, cumulative heat ...), a preview is shown, and the graphs
        you select are drawn in Origin. Analysis results are saved as CSV next to the figures.
Version 3.1: XRD reading, background, peaks, K-alpha2, phase library and search-match (xrd_smart.py).
Version 3 adds: analysis settings (wavelength, TGA mass unit and ranges, FTIR signal,
        calorimetry ages), replicates with mean ± SD, sample names with fixed colours, panel
        figures (a), (b) ... at an exact width, a processing record with draft captions, and
        sessions that can be saved and reopened.
Version 3.2: no fixed sample list any more - every figure comes from the files you load; names,
        Rwp, amorphous content and phase wt% are read from information sheets in your files;
        fit graphs in a HighScore look (observed red, calculated blue, phase legend with wt%).

Origin is started and driven automatically through its automation (COM) interface with
ordinary LabTalk commands.  Needs: pip install pywin32 pandas openpyxl numpy matplotlib

Run:   double-click Run_Origin_Plot_App.bat   (you can also drag data files onto it)
Test without Origin:  python origin_plot_app.py --dry-run <file> [<file> ...]
"""
import os, sys, re, csv, math, threading, traceback
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smart_plots as sp

NAVY = (0, 0, 139)
COLS = [a for a in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [a + b for a in "ABCD" for b in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
PALETTE = [(0, 0, 0), (255, 0, 0), (0, 0, 255), (0, 128, 0), (255, 0, 255), (255, 128, 0), (0, 139, 139), (128, 0, 128), (139, 69, 19), (128, 128, 0)]
PLOT_CODES = {"line": 200, "scatter": 201, "linesymbol": 202, "bar": 203, "area": 204}          # 203 = column plot, 204 = area plot

_SUP = {"\u207b": "-", "\u207a": "+", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3", "\u2070": "0", "\u2074": "4", "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9"}
def otext(t):
    """Superscript and subscript characters in Origin's own notation: cm\\+(-1), CaCO\\-(3); typed ^{..} and _{..} too."""
    t = re.sub(r"\^\{([^{}]*)\}", lambda m: "\\+(" + m.group(1) + ")", str(t)); t = re.sub(r"_\{([^{}]*)\}", lambda m: "\\-(" + m.group(1) + ")", t)
    t = re.sub("[" + "".join(_SUP) + "]+", lambda m: "\\+(" + "".join(_SUP[c] for c in m.group(0)) + ")", str(t))
    return re.sub("[\u2080-\u2089]+", lambda m: "\\-(" + "".join(str(ord(c) - 0x2080) for c in m.group(0)) + ")", t)

class Style:
    """Line weights in points. The user asked for curves and axes of at least 1.5."""
    def __init__(self, curve=1.5, axis=1.5, tick=0.75, zoom_curve=3.8, zoom_label=24, zoom_axis=3.8):
        self.curve, self.axis, self.tick = float(curve), float(axis), float(tick)
        self.zoom_curve, self.zoom_label, self.zoom_axis = float(zoom_curve), float(zoom_label), float(zoom_axis)      # Origin draws a small inset layer finer: its lines and letters are sent larger
    @property
    def obs(self): return self.curve * 4.0 / 3.0     # observed a little heavier so it shows behind the fit

def nice_range(lo, hi, pad=0.0):
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo: return lo - 1, hi + 1, 0.5
    span = hi - lo; lo, hi = lo - pad * span, hi + pad * span
    raw = (hi - lo) / 5.0; mag = 10 ** math.floor(math.log10(raw)); inc = min((1, 2, 2.5, 5, 10), key=lambda m: abs(m * mag - raw)) * mag
    return lo, hi, inc

def rgb(h):
    h = str(h).lstrip("#"); return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def short(prefix, s):
    return (prefix + re.sub(r"[^A-Za-z0-9]", "", str(s)))[:13]

# ============================================================================= Origin (COM + LabTalk)
class MockOrigin:
    def __init__(self): self.cmds = []; self.Visible = 0
    def Execute(self, c): self.cmds.append(c); return True
    def NewProject(self): return True
    def Save(self, p): self.cmds.append("SAVE " + p); return True
    def Exit(self): pass

class Busy(Exception):
    """Another drawing is still running in Origin."""

def draw_lock():
    """Only one drawing at a time may talk to Origin. The lock is held by the operating system, so it is released
    by itself when the drawing ends or the app is closed. Returns the open lock file (None where locking is not possible)."""
    try: import msvcrt, tempfile
    except Exception: return None
    try:
        f = open(os.path.join(tempfile.gettempdir(), "OriginPlotApp_drawing.lock"), "a+"); f.seek(0)
    except Exception: return None
    try: msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close(); raise Busy("Another drawing is still running in Origin (this app is open twice, or the last drawing has not finished). "
                              "Wait until it has finished - or answer the box Origin is showing - and draw again.")
    return f

class Driver:
    def __init__(self, outdir, log, style=None, dry=False, png=True, pdf=True, new_project=True):
        self.lock = None; self.files = {}; self.imp_tier = 0; self.book_notes = []; self.can_ask = None
        # window names of this run end in two letters taken from the clock, so they cannot meet the names of an earlier or a second run
        t_ = int(__import__("time").time() * 10); A_ = "bcfghjkmnpqrstvwxyz"; self.code = "a" if dry else A_[t_ % 19] + A_[(t_ // 19) % 19]
        self.out, self.log, self.png, self.pdf = os.path.abspath(outdir), log, png, pdf
        self.st = style or Style()
        self.tmp = os.path.join(self.out, "data_for_origin"); os.makedirs(self.tmp, exist_ok=True)
        if dry: self.org = MockOrigin()
        else:
            import pythoncom, win32com.client
            pythoncom.CoInitialize()
            self.lock = draw_lock()                              # Origin runs once per computer: two drawings at the same time would write into each other's workbooks
            self.org = win32com.client.Dispatch("Origin.ApplicationSI")
            try: self.org.Visible = 1
            except Exception: pass
            if new_project:
                try: self.org.NewProject()
                except Exception: pass
        self.rec = None; self.bucket = "rest"; self.plan = {}; self.axplan = {}; self.repaired = 0; self.checks = []; self.dry = dry; self.fs = 1.0; self.jk = 1.0; self.final = None; self.nlabel = 0; self.failed = 0; self.used_names = set(); self.graphs = {}; self.trace = []; self.count = 0; self.verify = not dry; self.missing = 0; self.checked = False

    def count_plots(self, g, idx):
        """Number of curves in one layer of a finished graph, asked from Origin. None when Origin cannot be asked."""
        if self.dry: return None
        try:
            self.org.Execute(f"win -a {g};"); self.org.Execute(f"page.active={idx};"); self.org.Execute("count=-1;"); self.org.Execute("layer -c;")
            n = int(round(float(self.org.LTVar("count")))); return n if n >= 0 else None
        except Exception: return None

    def ex(self, cmd):
        if self.rec is not None: self.rec[self.bucket].append((cmd, False)); return True      # a figure is first written down, then sent in the proven order
        try: ok = self.org.Execute(cmd)
        except Exception as e: ok = False; cmd = f"{cmd}  [{e}]"
        self.trace.append(("FAILED  " if ok is False else "ok      ") + cmd)
        if ok is False:
            self.failed += 1; self.log("   (Origin refused: " + cmd[:110] + ")")
        return ok

    def soft(self, cmd):
        """A command that only improves the look: a refusal is written to the command log but not counted as a failure."""
        if self.rec is not None: self.rec[self.bucket].append((cmd, True)); return
        try: ok = self.org.Execute(cmd)
        except Exception as e: ok = False; cmd = f"{cmd}  [{e}]"
        self.trace.append(("refused " if ok is False else "ok      ") + cmd + "   (optional)")

    def unique(self, name):
        """A short window name that is new in this run: a letter for what it is (G graph, D data, L leader lines, B band,
        E error bars), a running number and a closing letter, e.g. G3a, D17a. Names cut to Origin's 13-character limit and
        then numbered (DCombinedFit2) were not found again by Origin, so no name is ever cut or renumbered."""
        self.count += 1; new = f"{name[:1]}{self.count}{self.code}"; self.used_names.add(new.lower()); self.trace.append(f"        {new}  =  {name}"); return new

    def book(self, name, columns):
        """A workbook from a plain CSV file: column A is x, the others are y (Origin's own default), so no column settings are needed."""
        name = self.unique(name)
        n = max(len(c) for c in columns); arr = np.full((n, len(columns)), np.nan)
        for j, c in enumerate(columns): arr[:len(c), j] = c
        path = os.path.join(self.tmp, name + ".csv")
        pd.DataFrame(arr).to_csv(path, header=False, index=False, float_format="%.8g", na_rep="--")
        self.files[name] = path
        if self.rec is not None: self.rec["books"].append((("BOOK", name), False))        # made when the figure is sent, see make_book
        else: self.make_book(name)
        return name

    def ask(self, script):
        """Run a LabTalk line that puts a number into 'count' and read it back. None when Origin cannot be asked."""
        if self.dry: return None
        try: self.org.Execute("count=-9;"); self.org.Execute(script); v = float(self.org.LTVar("count")); return None if v == -9 else v
        except Exception: return None

    def book_state(self, name):
        """(is there a workbook window with this name, rows of data in it). (None, None) when Origin cannot be asked."""
        e = self.ask(f"count=exist({name});")
        if e is None: return None, None
        if int(round(e)) != 2: return False, 0
        r = self.ask(f"win -a {name}; count=wks.maxRows;")
        if r is None: r = self.ask(f"get {name}_A -e count;")          # the older way to ask for the number of rows
        return True, (None if r is None else int(round(r)))

    IMPORTS = [' options.Names.AutoNames:=0 options.Names.FNameToBk:=0 options.Names.FNameToSht:=0 options.Names.FNameToBkComm:=0 options.sparklines:=0 orng:=[{n}]1!',
               ' options.Names.AutoNames:=0 options.Names.FNameToBk:=0 options.Names.FNameToSht:=0 orng:=[{n}]1!', '']

    def run(self, cmd, note=""):
        try: ok = self.org.Execute(cmd)
        except Exception as e: ok = False; cmd = f"{cmd}  [{e}]"
        self.trace.append(("refused " if ok is False else "ok      ") + cmd + note); return ok

    def make_book(self, name, again=False):
        """One workbook of this figure from its CSV file. What went wrong before (Origin 2018): the import of one file landed in
        the workbook of the file before it, Origin named that workbook <name>1, and the command that renamed it back met a
        name that was taken - Origin then opened its Window Properties box and the curves of that workbook were lost.
        Now: the import is told which workbook it belongs to and not to rename anything; a window is only ever renamed when
        its name is free; and the workbook is checked (it exists, it has rows) before the next one is made."""
        path = self.files[name]
        if not (again and self.book_state(name)[0]): self.run(f"win -t data origin {name};")
        if self.dry:
            self.run(f'win -a {name}; impASC fname:="{path}"' + self.IMPORTS[0].format(n=name) + ";"); self.run(f"win -a {name};"); return True
        state = (None, None)
        if self.can_ask is None:                                # Origin that cannot be asked for numbers: nothing can be checked, so the earlier, proven import is used
            self.can_ask = self.ask("count=1;") is not None
            if not self.can_ask: self.imp_tier = len(self.IMPORTS) - 1
        for k in range(self.imp_tier, len(self.IMPORTS)):
            plain = not self.IMPORTS[k]
            self.run(f'win -a {name}; impASC fname:="{path}"' + self.IMPORTS[k].format(n=name) + ";", "" if plain else "   (import that names its workbook)")
            self.run(f"if(exist({name})!=2) {{win -r %H {name};}}", "   (only when the name is free)")       # Origin gave the window the name of the file with a number: take the name back
            state = self.book_state(name)
            if plain or state[0] is None or (state[0] and state[1] is not None and state[1] > 0): break   # filled (the plain import is the last way; rows that cannot be counted do not count as filled)
            if not plain: self.imp_tier = k + 1                  # this Origin does not know these import options: use the next way from now on
        self.run(f"win -a {name};")
        ok = state[0] is None or bool(state[0] and (state[1] is None or state[1] > 0))
        if not ok: self.book_notes.append(f"workbook {name}: " + ("not there after the import" if not state[0] else "empty after the import")); self.trace.append(f"FAILED  workbook {name} has no data ({path})")
        return ok

    def datasets(self, name, curves):
        """Workbook(s) for the curves of one panel; returns one dataset name per curve. Curves on the same x values share one
        workbook (x, y1, y2 ...); a curve with its own x values gets its own two-column workbook."""
        x0 = curves[0]["x"]
        if len(curves) <= 40 and all(len(c["x"]) == len(x0) and np.array_equal(c["x"], x0, equal_nan=True) for c in curves):
            B = self.book(name, [x0] + [c["y"] for c in curves]); return [f"{B}_{COLS[j + 1]}" for j in range(len(curves))]
        return [self.book(name, [c["x"], c["y"]]) + "_B" for c in curves]

    def graph(self, name, page_w_in=None, page_h_in=None, long=""):
        name = self.unique(name); keep = self.bucket; self.bucket = "graph"
        self.ex(f"win -t plot line {name};"); self.ex(f"win -a {name};")
        if page_w_in: self.ex(f"page.width={page_w_in}*page.resx; page.height={page_h_in}*page.resy;")
        self.bucket = keep; return name

    def layer(self, g, idx, left, top, width, height, new=True):
        keep = self.bucket; self.bucket = "layers"             # every layer of a figure is made before anything is drawn into it
        self.ex(f"win -a {g};")
        if new: self.ex("layer -n;")
        self.ex(f"page.active={idx};"); self.ex("layer.unit=1;")
        self.ex(f"layer.left={left:.3f}; layer.top={top:.3f}; layer.width={width:.3f}; layer.height={height:.3f};")
        self.bucket = keep

    def plot(self, g, idx, dataset, colour, width_pt, code=200):
        self.plan.setdefault((g, idx), []).append((dataset, colour, width_pt, code))
        self.ex(f"win -a {g};"); self.ex(f"page.active={idx};")
        self.ex(f"layer -i{code} {dataset};")
        self.style(dataset, colour, width_pt, code)

    def style(self, dataset, colour, width_pt, code=200):
        cc = sp.look_colour(getattr(sp, "LOOK", {}).get("curve_colour")) if hasattr(sp, "look_colour") else None
        if cc is not None and tuple(colour) == (0, 0, 0) and code == 200: colour = cc          # Size and look: the colour of black curves
        self.ex(f"set {dataset} -c color({colour[0]},{colour[1]},{colour[2]});")
        self.ex(f"set {dataset} -w {int(round(width_pt * 500))};")
        if code in (203, 204): self.soft(f"set {dataset} -cf color({colour[0]},{colour[1]},{colour[2]});"); self.soft(f"set {dataset} -c color(0,0,0);"); self.soft(f"set {dataset} -w 250;")      # columns and areas: filled with the colour, thin black outline
        if code != 200: self.ex(f"set {dataset} -z 6;")

    def axes(self, g, idx, y0, y1, yinc=None, x0=5, x1=80, xinc=10, xlabels=True, ylabels=True, yticks=True, xlog=False):
        self.axplan[(g, idx)] = (x0, x1, y0, y1)
        self.ex(f"win -a {g};"); self.ex(f"page.active={idx};")
        if xlog: self.ex("layer.x.type=2;")
        self.ex(f"layer.x.from={x0:.8g}; layer.x.to={x1:.8g};")
        if xinc and not xlog: self.ex(f"layer.x.inc={xinc:.6g};"); self.ex("layer.x.minor=4;")
        self.ex(f"layer.y.from={y0:.8g}; layer.y.to={y1:.8g};")
        if yinc: self.ex(f"layer.y.inc={yinc:.6g};")
        self.ex("layer.x.showAxes=3;"); self.ex("layer.y.showAxes=3;")
        self.ex("layer.x.ticks=5;"); self.ex("layer.x2.ticks=5;")
        self.ex("layer.y.ticks=%d;" % (5 if yticks else 0)); self.ex("layer.y2.ticks=%d;" % (5 if yticks else 0))
        self.ex("layer.x2.showLabels=0;"); self.ex("layer.y2.showLabels=0;")
        self.ex(f"layer.x.showLabels={1 if xlabels else 0};"); self.ex(f"layer.y.showLabels={1 if (ylabels and yticks) else 0};")      # numbers on the bottom and left axis: said explicitly for every layer
        self.ex(f"layer.x.label.pt={int(round(18 * self.fs * self.jk))};"); self.ex(f"layer.y.label.pt={int(round(18 * self.fs * self.jk))};")
        if not xlabels: self.soft("xb.show=0;")
        if not ylabels:
            self.soft("yl.show=0;")
            # Origin 2018 still wrote the numbers of a hidden left axis (seen small beside the zoom): there they are also made white and tiny
            self.soft("layer.y.label.color=color(255,255,255);"); self.soft("layer.y.label.pt=4;")
        self.ex("label -r legend;")
        ax_ = (getattr(self, "fmt", None) or {}).get("axis") or {}; ac_ = sp.look_colour(ax_.get("colour")) if isinstance(ax_.get("colour"), str) else None
        for a in ("x", "y", "x2", "y2"):
            self.soft(f"layer.{a}.thickness={float(ax_.get('width') or self.st.axis):g};")   # axis and frame line weight (yours, if you set one)
            if ac_: self.soft(f"layer.{a}.color=color({ac_[0]},{ac_[1]},{ac_[2]});")
        nm_ = self._role("numbers"); nc_ = sp.look_colour(nm_.get("colour")) if isinstance(nm_.get("colour"), str) else None
        if nm_.get("size"): self.ex(f"layer.x.label.pt={int(round(float(nm_['size']) * sp.ORIGIN_PT * 0.82 * self.jk))};"); self.ex(f"layer.y.label.pt={int(round(float(nm_['size']) * sp.ORIGIN_PT * 0.82 * self.jk))};")
        if nc_: self.soft(f"layer.x.label.color=color({nc_[0]},{nc_[1]},{nc_[2]});"); self.soft(f"layer.y.label.color=color({nc_[0]},{nc_[1]},{nc_[2]});")
        if nm_.get("bold"): self.soft("layer.x.label.bold=1;"); self.soft("layer.y.label.bold=1;")

    def _role(self, role):
        return ((getattr(self, "fmt", None) or {}).get("text") or {}).get(role) or {}

    def _styled(self, t, st):
        """Bold / italic of your format around Origin text."""
        if st.get("italic"): t = "\\i(" + t + ")"
        if st.get("bold"): t = "\\b(" + t + ")"
        return t

    def titles(self, x=None, y=None):
        st = self._role("axis_titles"); fz = (int(round(float(st["size"]) * sp.ORIGIN_PT * self.jk)) if st.get("size") else int(round(22 * self.fs * self.jk)))
        for nm, v in (("yl", y), ("xb", x)):
            if v is None: continue
            self.ex('%s.text$="%s";' % (nm, self._styled(otext(str(v).replace('"', "'")), st))); self.ex(f"{nm}.fsize={fz};")
            c_ = sp.look_colour(st.get("colour")) if isinstance(st.get("colour"), str) else None
            if c_: self.ex(f"{nm}.color=color({c_[0]},{c_[1]},{c_[2]});")
            if st.get("family"): self.soft(f"{nm}.font=font({st['family']});")

    def text(self, txt, x, y, size, colour=(0, 0, 0), bold=False, centre=True, rotate=0, hang=False, sit=False, raw=False):
        """Text at axis position (x, y). centre=True: centred on x, sitting on y (hang=True: hanging below y).
        centre=False: its top-left corner at (x, y)."""
        self.nlabel += 1; nm = "T%d" % self.nlabel; size = int(round(size * self.jk)) if raw else max(7 if self.jk >= 1 else 5, int(round(size * self.fs * self.jk)))
        t = otext(str(txt).replace('"', "'"))
        lk = getattr(sp, "LOOK", {}); bold = bold and str(lk.get("font_weight", "Bold")).startswith("Bold")      # Size and look: font weight, text colour, size
        tc = sp.look_colour(lk.get("text_colour")) if hasattr(sp, "look_colour") else None
        if tc is not None and tuple(colour) == (0, 0, 0): colour = tc
        st_ = self._role("labels")                                     # your format of the labels of this graph
        if st_.get("bold") is not None: bold = bool(st_["bold"])
        if st_.get("italic"): t = "\\i(" + t + ")"
        if isinstance(st_.get("colour"), str) and sp.look_colour(st_["colour"]): colour = sp.look_colour(st_["colour"])
        if st_.get("size"): size = int(round(float(st_["size"]) * sp.ORIGIN_PT * self.jk))
        size = max(5, int(round(size * float(lk.get("font_scale") or 1.0))))
        if bold: t = "\\b(" + t + ")"
        self.ex(f"label -a {max(x, 0.0):.6g} {max(y, 0.0):.6g} -n {nm} x;"); self.ex(f'{nm}.text$="{t}";'); self.ex(f"{nm}.fsize={size};")
        self.ex(f"{nm}.color=color({colour[0]},{colour[1]},{colour[2]});"); self.ex(f"{nm}.attach=2;")
        if rotate: self.ex(f"{nm}.rotate={rotate};")
        if centre: self.ex(f"{nm}.x={x:.6g};"); self.ex(f"{nm}.y={y:.6g}{'-' if hang else '+'}{nm}.dy/2;")
        else: self.ex(f"{nm}.x={x:.6g}+{nm}.dx/2;"); self.ex(f"{nm}.y={y:.6g}{'+' if sit else '-'}{nm}.dy/2;")

    def export(self, g, fname):
        self.ex(f"win -a {g};"); fname = re.sub(r'[\\/:*?"<>|]', "_", fname)
        for ok, ext in ((self.png, "png"), (self.pdf, "pdf")):
            if ok and self.ex(f'expGraph type:={ext} path:="{self.out}" filename:="{fname}" overwrite:=replace;') is False:
                self.ex(f'expGraph type:={ext} path:="{self.out}" filename:="{fname}";')

    def draw_spec(self, spec, tag, final=None):
        """One graph window for a figure. A page of several graphs ((a), (b) ...) is drawn into parts of the same page.
        final = (width in, height in, pt) of the chosen journal: the Origin page gets that printed size and the letters are
        scaled so the axis titles come out near that size. Without it the graph is drawn on the working page, as before."""
        self.final = final; self.jk = (float(final[2]) / 20.0) if final else 1.0          # working sizes are 18-22 pt: 20 pt stands for the journal's letter size
        self.rec = {"books": [], "graph": [], "layers": [], "rest": []}; self.plan = {}; self.axplan = {}
        try:
            G = self._compose(spec, tag)
        finally:
            rec = self.rec; self.rec = None
        for b in ("books", "graph", "layers", "rest"):         # 1 all workbooks, 2 the graph window, 3 all its layers, 4 curves, axes and texts layer by layer
            for cmd, soft in rec[b]:
                if isinstance(cmd, tuple): self.make_book(cmd[1])
                else: (self.soft if soft else self.ex)(cmd)
        self.check(G, tag)
        try: self.org.Execute('win -a %s; page.longname$="%s";' % (G, str(tag).replace('"', "'")[:80]))      # readable window title; not essential
        except Exception: pass
        self.fs = 1.0; self.jk = 1.0; self.final = None; self.graphs[tag] = G; self.export(G, tag)

    def check(self, G, tag):
        """Ask Origin how many curves each layer of the finished graph holds. A layer that stayed empty is filled a second way
        (plotxy with the layer named explicitly). The outcome goes to origin_check.txt and into the result line."""
        for (g, idx), lst in sorted(self.plan.items(), key=lambda kv: kv[0][1]):
            n = self.count_plots(g, idx)
            if n is None: self.checks.append((tag, idx, len(lst), None, "")); continue
            how = ""
            if n < len(lst):
                again = []                                       # workbooks of this layer that are missing or empty: made again from their files
                for bk in dict.fromkeys(ds.rsplit("_", 1)[0] for ds, _, _, _ in lst):
                    there, rows = self.book_state(bk)
                    if bk in self.files and (there is False or rows == 0): self.make_book(bk, again=True); again.append(bk)
                todo = lst if n == 0 else [l for l in lst if l[0].rsplit("_", 1)[0] in again]
                if again: self.log(f"   workbook(s) {', '.join(again)} of {tag} were missing in Origin and were made again")
            else: todo = []
            if todo:
                for ds, col, w, code in todo:
                    bk, cl = ds.rsplit("_", 1)
                    self.ex(f"plotxy iy:=[{bk}]1!(1,{COLS.index(cl) + 1}) plot:={code} ogl:=[{g}]{idx}!;"); self.style(ds, col, w, code)
                if (g, idx) in self.axplan:                      # plotxy may rescale the axes: the ranges of this layer are set again
                    x0, x1, y0, y1 = self.axplan[(g, idx)]; self.ex(f"win -a {g};"); self.ex(f"page.active={idx};")
                    self.ex(f"layer.x.from={x0:.8g}; layer.x.to={x1:.8g};"); self.ex(f"layer.y.from={y0:.8g}; layer.y.to={y1:.8g};"); self.soft("label -r legend;")
                n = self.count_plots(g, idx); how = "filled the second way (plotxy)" + (f"; workbook {', '.join(again)} made again" if again else ""); self.repaired += 1
                if n is not None and n < len(lst): self.missing += len(lst) - n; self.log(f"!! Origin holds {n} of the {len(lst)} curve(s) of layer {idx} in {tag} (two ways tried).")
            self.checks.append((tag, idx, len(lst), n, how))

    def _compose(self, spec, tag):
        self._page_fmt = spec.get("fmt") or {}
        G = self.graph(short("G", tag), *((self.final[0], self.final[1]) if self.final else (spec.get("page_in") or (None, None))), long=tag)
        if spec.get("cols"):
            n_ = len(spec["cols"]); nxt = 1
            for k_, sub in enumerate(spec["cols"]):
                cell = (k_ / n_, 0.0, 1.0 / n_, 1.0) if spec.get("layout") == "side" else (0.0, k_ / n_, 1.0, 1.0 / n_)
                nxt = self._draw_into(dict(sub, page_in=spec.get("page_in")), f"{tag}{chr(97 + k_)}", G, cell, nxt, chr(97 + k_))
        else: self._draw_into(spec, tag, G, (0.0, 0.0, 1.0, 1.0), 1, None)
        return G

    def _draw_into(self, spec, tag, G, cell, nxt, letter):
        cx_, cy_, cw_, chh = cell; self.fs = float(spec.get("font_scale", 1.0)); self.fmt = spec.get("fmt") or getattr(self, "_page_fmt", None) or {}
        mL = max(15.0 * cw_, 9.0) / cw_; mB = max(15.0 * chh, 11.0) / chh          # room for the axis numbers and titles, in % of this part of the page
        st = self.st; pans = spec["panels"]; xa, xb_ = spec["xlim"]; xlog = bool(spec.get("xlog")); rev = xa > xb_
        lo, hi = min(xa, xb_), max(xa, xb_)
        def xfrac(f):                      # data x at fraction f of the axis, left to right as drawn
            f = 1 - f if rev else f
            return 10 ** (math.log10(lo) + f * (math.log10(hi) - math.log10(lo))) if xlog else lo + f * (hi - lo)
        _, _, xinc = nice_range(lo, hi)
        foot = spec.get("footer") or spec.get("o_footer") or []; total = sum(p["weight"] for p in pans); own_key = bool(spec.get("o_footer")) and not spec.get("footer")
        top = 7.0 + (4.0 if spec.get("legend_row") else 0.0) - (3.0 if spec.get("no_title") and not spec.get("legend_row") else 0.0); 
        if letter: top = max(top, 11.0, 5.0 / chh)          # the same room above (a) and (b): letter and legend row
        avail = 100.0 - top - mB - 3.2 * (len(foot) or spec.get("footer_pad", 0)) / chh
        insets = []; Wp, Hp = spec.get("page_in") or (11.0, 8.5)
        def head(x1, y1, x2, y2, sx, sy):                   # arrow head at (x2, y2) as two short strokes, for a pointer coming from (x1, y1)
            dx, dy = (x2 - x1) * sx, (y2 - y1) * sy; L = math.hypot(dx, dy)
            if L < 1e-9: return [], []
            ux, uy = dx / L, dy / L; hl = min(0.10 * Wp / 11.0, 0.5 * L); ox, oy = [], []
            for sg in (1, -1):
                ca, sa = math.cos(math.radians(24)), sg * math.sin(math.radians(24)); bx_, by_ = -(ux * ca - uy * sa), -(ux * sa + uy * ca)
                ox += [x2 + hl * bx_ / sx, x2, np.nan]; oy += [y2 + hl * by_ / sy, y2, np.nan]
            return ox, oy
        for i, p in enumerate(pans):
            lw_ = (62 if any(p_.get("side") for p_ in pans) else 74 if any(p_.get("rows") for p_ in pans) else 78) - (mL - 15.0)
            idx = nxt; nxt += 1; h = avail * p["weight"] / total; self.layer(G, idx, 100 * cx_ + mL * cw_, 100 * cy_ + top * chh, lw_ * cw_, h * chh, new=(idx > 1)); top += h
            dsn = self.datasets(short("D", f"{tag}{idx}"), p["curves"])
            for j, c in enumerate(p["curves"]):
                col_, w_ = sp.fmt_curve(self.fmt, c["label"], c["colour"], st.tick if (p.get("thin") or c["width"] == "thin") else st.obs if c["width"] == "obs" else st.curve)
                self.plot(G, idx, dsn[j], col_, w_, PLOT_CODES.get(c["kind"], 200))
            for k_, (bx, blo, bhi, bcol) in enumerate(p.get("bands", [])):          # ± SD band: its two edges as thin lines
                Bb = self.book(short("B", f"{tag}{idx}{k_}"), [bx, blo, bhi])
                self.plot(G, idx, f"{Bb}_B", bcol, st.tick); self.plot(G, idx, f"{Bb}_C", bcol, st.tick)
            for k_, (sx, sy, scol) in enumerate(p.get("segs", [])):                  # error bars as line segments
                Sb = self.book(short("E", f"{tag}{idx}{k_}"), [sx, sy]); self.plot(G, idx, f"{Sb}_B", scol, st.tick)
            y0, y1 = p["ylim"]; ysp = y1 - y0; _, _, yinc = nice_range(y0, y1); last = i == len(pans) - 1
            if p.get("ylog"): yinc = None                        # logarithmic y axis: Origin chooses the decades
            self.axes(G, idx, y0, y1, yinc=yinc, x0=xa, x1=xb_, xinc=xinc, xlabels=last, yticks=p.get("yticks", True), xlog=xlog)
            if p.get("ylog"): self.ex("layer.y.type=2;"); self.ex(f"layer.y.from={y0:.6g}; layer.y.to={y1:.6g};")
            if spec.get("xcats") and last:                      # bars and boxes: names instead of numbers under the axis
                self.ex("layer.x.showLabels=0;"); self.soft("layer.x.label.color=color(255,255,255);"); self.soft("layer.x.label.pt=4;"); self.soft("layer.x.minor=0;"); self.soft("layer.x.ticks=0;"); self.soft("layer.x2.ticks=0;")
                for pos_, nm_ in spec["xcats"]: self.text(str(nm_), pos_, y0 - 0.02 * (y1 - y0), 15, centre=True, hang=True)
            self.titles(x=spec["xname"] if last else None, y=p["yname"] if p["yname"] else " ")
            seg_x, seg_y = [], []
            for pos, py, txt, lx, ly in p.get("placed", []):
                self.text(txt, lx, ly, p.get("lab_pt", 15), sp.NAVY, bold=True, rotate=90 if p["vertical"] else 0)
                if ly - py > 0.04 * ysp or (abs(lx - pos) > 1e-9 and not getattr(txt, "beside", False)):
                    seg_x += [pos, lx, np.nan]; seg_y += [py + 0.01 * ysp, ly - 0.005 * ysp, np.nan]
                    if spec.get("arrows") and not xlog:
                        hx, hy = head(lx, ly - 0.005 * ysp, pos, py + 0.01 * ysp, (lw_ * cw_ / 100.0 * Wp) / (xb_ - xa), (h * chh / 100.0 * Hp) / ysp); seg_x += hx; seg_y += hy
            if p.get("inset") and p["inset"].get("curves"): insets.append((p, top - h, h, lw_))
            for pos, py, txt, lx, ly in p.get("placed_below", []):
                self.text(txt, lx, ly, 15, sp.NAVY, bold=True, rotate=90, hang=True)
            for tx, ty, txt, col in p.get("texts", []): self.text(txt, tx, ty, 15, col, bold=True)
            ycr = 0.95; xcr = 0.985; pin_ = spec.get("page_in"); inline_ = bool(pin_) and (h * chh / 100.0 * pin_[1]) < 1.25 and len(p.get("corner_r", [])) <= 2      # short panel: name and Rwp on one line
            for it_ in p.get("corner_r", []):
                txt, b_ = it_[0], it_[1]; t_ = txt.replace("R_wp", "R\\-(wp)"); wf = (len(txt) * (0.0095 if b_ else 0.0075) + 0.015)
                if inline_: self.text(t_, xfrac(xcr - wf), y1 - 0.07 * ysp, 16 if b_ else 13, it_[2] if len(it_) > 2 else (0, 0, 0), bold=b_, centre=False); xcr -= wf + 0.012
                else: self.text(t_, xfrac(0.985 - wf), y1 - (1 - ycr) * ysp - 0.0 * ysp, 16 if b_ else 13, it_[2] if len(it_) > 2 else (0, 0, 0), bold=b_, centre=False); ycr -= 0.12 if b_ else 0.075
            for k_, txt in enumerate(p.get("corner", [])): self.text(txt.replace("R_wp", "R\\-(wp)"), xfrac(0.015), y1 - (0.04 + (0.055 if spec.get("cell") else 0.075) / spec.get("cell", (1.0, 1.0))[1] * k_) * ysp, 15, bold=(k_ == 0 and bool(spec.get("cell"))), centre=False)
            for yy, txt, col in p.get("rows", []): self.text(txt, xfrac(1.012), yy + 0.45, 13, col, centre=False)
            for k_, (txt, b_) in enumerate(p.get("side", [])):        # sample name, Rwp and wt% in a column right of the panel
                self.text(txt, xfrac(1.02), y1 - (0.05 * ysp) - k_ * (2.3 / max(h * chh, 1.0)) * ysp, 15 if b_ else 12, bold=b_, centre=False)
            bx = p.get("legendbox")
            if bx:                                                     # HighScore-style legend: sample name, curve key, coloured squares + phases, Rwp
                dy = bx.get("dy", 0.055) * ysp; yy = y1 - 0.02 * ysp; f0 = 0.012 if bx.get("side", "left") == "left" else 1 - bx.get("wfrac", 0.3) + 0.004
                fz = int(max(9, min(15, 15 * bx.get("dy", 0.055) / 0.052)))
                self.text(bx.get("title", ""), xfrac(f0), yy, fz + 2, bold=True, centre=False); yy -= dy * 1.15
                for k_, (col, txt) in enumerate(bx.get("keys", [])):
                    self.text(f"\\l({k_ + 1}) {txt}", xfrac(f0), yy, fz, centre=False); yy -= dy
                for col, txt in bx.get("entries", []):
                    if col is not None: self.text("\u25a0", xfrac(f0), yy, fz + 1, col, centre=False)
                    self.text(txt, xfrac(f0 + (0.028 if col is not None else 0.0)), yy, fz, centre=False); yy -= dy
                for txt in bx.get("lines", []): self.text(txt, xfrac(f0), yy, fz, centre=False); yy -= dy
            for xv, txt in p["vlines"]:
                seg_x += [xv, xv, np.nan]; seg_y += [y0, y1, np.nan]
                if txt: self.text(txt, xv, y0 + 0.45 * ysp, 13, sp.NAVY, rotate=90)
            if seg_x:
                Lb = self.book(short("L", f"{tag}{idx}"), [np.array(seg_x, float), np.array(seg_y, float)]); self.plot(G, idx, f"{Lb}_B", sp.NAVY, st.tick)
            vis = sp.visible(p)
            if p["legend"] and len(vis) > 1:
                for row, (j, c) in enumerate(vis): self.text(f"\\l({j + 1}) {c['label']}", xfrac(0.02 if (p.get("inset") or {}).get("curves") else 0.66), y1 - (0.02 + 0.075 * row) * ysp, 14, centre=False)
            y2 = p.get("y2")
            if y2:                                          # second y axis: its own layer on top of this one, right axis only
                j = nxt; nxt += 1; self.layer(G, j, 100 * cx_ + mL * cw_, 100 * cy_ + (top - h) * chh, lw_ * cw_, h * chh, new=True)
                ds2 = self.datasets(short("D", f"{tag}{j}"), y2["curves"])
                for q, c in enumerate(y2["curves"]): self.plot(G, j, ds2[q], c["colour"], st.curve)
                a0, a1 = y2["ylim"]; _, _, yinc2 = nice_range(a0, a1)
                self.ex(f"win -a {G};"); self.ex(f"page.active={j};")
                if xlog: self.ex("layer.x.type=2;")                 # the second layer on the same logarithmic x axis (e.g. particle size)
                self.ex(f"layer.x.from={xa:.8g}; layer.x.to={xb_:.8g};"); self.ex(f"layer.y.from={a0:.8g}; layer.y.to={a1:.8g};"); self.ex(f"layer.y.inc={yinc2:.6g};")
                self.ex("layer.x.showAxes=0;"); self.ex("layer.y.showAxes=2;"); self.ex("layer.y.ticks=5;"); self.ex("layer.y.showLabels=2;"); self.ex(f"layer.y.label.pt={int(round(18 * self.jk))};"); self.soft(f"layer.y.thickness={st.axis:g};")
                self.ex('yr.text$="%s";' % otext(str(y2["yname"]).replace('"', "'"))); self.ex(f"yr.fsize={int(round(22 * self.jk))};"); self.ex("label -r legend;")
                for pos, py, txt, lx, ly in y2.get("placed", []): self.text(txt, lx, ly, y2.get("lab_pt", 12), sp.NAVY, bold=True)
                self.ex(f"page.active={idx};"); self.ex("layer.y.showAxes=1;"); self.ex("layer.y2.ticks=0;")           # the frame's right side and its ticks come from the second layer
            if i == 0 and spec.get("legend_row"):          # one legend row above the figure
                k_ = {c["label"]: j + 1 for j, c in enumerate(p["curves"])}
                parts = [f"\\l({k_[l_]}) {l_}" if l_ in k_ else l_ for _, l_ in spec["legend_row"]]
                self.text(("     " if cw_ >= 1.0 else "  ").join(parts), xfrac(0.5 if cw_ >= 1.0 else 0.56), y1 + 0.03 * ysp, 14)
            if last and foot:                               # colour-coded phase key under the x axis title
                for kk, line in enumerate(foot):
                    fx = 0.0; yy_ = y0 - (9.0 + 3.2 * kk) / (h * chh) * ysp
                    if own_key: self.text("     ".join(t_ for _, t_ in line), xfrac(0.0), yy_, 15, (0, 0, 0), centre=False, raw=True); continue      # key of a sample page: one line of text, across the page
                    for col, txt in line:
                        self.text(txt, xfrac(fx), yy_, 12, col, centre=False); fx += (len(txt) + 3) * 0.0105
            if i == 0 and letter: self.text(f"({letter})", xfrac(0.0), y1 + 0.025 * ysp, 18, bold=True, centre=False, sit=True)      # above the frame, not on it
            if i == 0 and not spec.get("no_title"):
                import textwrap
                notes = textwrap.wrap(spec.get("note", ""), 95)
                self.text(spec["title"], xfrac(0.0), y1 + (0.09 + 0.05 * len(notes)) * ysp, 18, bold=True, centre=False)
                for k_, ln in enumerate(notes): self.text(ln, xfrac(0.0), y1 + (0.02 + 0.05 * (len(notes) - k_)) * ysp, 11, centre=False)
        for p, ptop, h, lw_ in insets:                      # zoomed insets: a small layer of its own in the top right corner of its panel
            ins = p["inset"]; fx, fy, fw, fh = ins["rect"]; j = nxt; nxt += 1
            self.layer(G, j, 100 * cx_ + (mL + fx * lw_) * cw_, 100 * cy_ + (ptop + (1 - fy - fh) * h) * chh, fw * lw_ * cw_, fh * h * chh, new=True)
            dsi = self.datasets(short("D", f"{tag}i{j}"), ins["curves"])
            for q, c in enumerate(ins["curves"]):
                col_, w_ = sp.fmt_curve(self.fmt, c["label"], c["colour"], st.zoom_curve)
                self.plot(G, j, dsi[q], col_, w_ if w_ == st.zoom_curve else w_ * st.zoom_curve / max(st.curve, 0.1), PLOT_CODES.get(c["kind"], 200))
            a_, b_ = ins.get("xdraw", ins["xlim"]); i0, i1 = ins["ylim"]; _, _, xi = nice_range(min(a_, b_), max(a_, b_)); _, _, yi = nice_range(i0, i1); isp = i1 - i0
            self.axes(G, j, i0, i1, yinc=yi, x0=a_, x1=b_, xinc=xi, xlabels=True, ylabels=False)
            self.soft(f"layer.x.label.pt={max(10 if self.jk >= 1 else 5, int(round(0.85 * st.zoom_label * self.jk)))};"); self.soft("layer.x.label.bold=1;")      # the numbers under the zoom: large and bold, like its labels
            for a in ("x", "y", "x2", "y2"): self.soft(f"layer.{a}.thickness={st.zoom_axis:g};")                                 # its frame: as heavy as its curves; self.soft("xb.show=0;"); self.soft("layer.x.minor=1;")
            sx_, sy_ = [], []
            for pos, py, txt, lx, ly in ins.get("placed", []):
                self.text(txt, lx, ly, st.zoom_label, sp.NAVY, bold=True, rotate=90 if ins["vertical"] else 0, raw=True)
                if ly - py > 0.04 * isp or (abs(lx - pos) > 1e-9 and not getattr(txt, "beside", False)):
                    sx_ += [pos, lx, np.nan]; sy_ += [py + 0.01 * isp, ly - 0.005 * isp, np.nan]
                    if spec.get("arrows"):
                        hx, hy = head(lx, ly - 0.005 * isp, pos, py + 0.01 * isp, (fw * lw_ * cw_ / 100.0 * Wp) / (b_ - a_), (fh * h * chh / 100.0 * Hp) / isp); sx_ += hx; sy_ += hy
            if sx_:
                Li = self.book(short("L", f"{tag}i{j}"), [np.array(sx_, float), np.array(sy_, float)]); self.plot(G, j, f"{Li}_B", sp.NAVY, st.tick * st.zoom_curve / max(st.curve, 0.1))
        return nxt

    def save(self, keep_open, name="Origin_figures.opj"):
        path = os.path.join(self.out, name)
        try: open(os.path.join(self.tmp, "origin_commands_log.txt"), "w", encoding="utf-8").write("\n".join(self.trace))      # every command sent to Origin and whether it was accepted
        except Exception: pass
        try:
            bad = [c for c in self.checks if c[3] is not None and c[3] < c[2]]; unk = [c for c in self.checks if c[3] is None]
            L = ["Check of the graphs in Origin: for every layer, the curves the app sent and the curves Origin holds.", ""]
            L += [f"{t}  layer {i}: sent {n}, in Origin {'not known (Origin could not be asked)' if k is None else k}{'  ' + h if h else ''}{'   <-- CURVES MISSING' if k is not None and k < n else ''}" for t, i, n, k, h in self.checks]
            if self.book_notes: L += ["", "Workbooks that could not be filled (their curves are missing):"] + ["   " + b_ for b_ in self.book_notes]
            L += ["", "How the data went into Origin: " + ["import that names its workbook, no renaming, no sparklines", "import that names its workbook, no renaming", "plain import, window renamed only when the name is free"][min(self.imp_tier, 2)]]
            open(os.path.join(self.out, "origin_check.txt"), "w", encoding="utf-8").write("\n".join(L))
            self.check_text = ("" if self.dry else f"Origin check: curves are missing in {len(bad)} layer(s), see origin_check.txt" if bad else "Origin check: Origin could not be asked how many curves it drew" if unk and len(unk) == len(self.checks) else "Origin check: every layer holds its curves" + (f" ({self.repaired} layer(s) had to be filled a second way)" if self.repaired else ""))
        except Exception: self.check_text = ""
        try: self.org.Save(path); self.log("Origin project saved: " + path)
        except Exception as e: self.log(f"Project not saved automatically ({e}). Use File > Save Project As in Origin.")
        if not keep_open:
            try: self.org.Exit()
            except Exception: pass
        self.unlock()

    def __del__(self): self.unlock()

    def unlock(self):
        try:
            if self.lock is not None: self.lock.close()
        except Exception: pass
        self.lock = None

# ============================================================================= jobs
def tag_of(it): return re.sub(r"[^A-Za-z0-9_-]", "_", getattr(it, "paper_name", None) or f"{it.file}_{it.name}")

def run_paper(singles, opt, main_names, outdir, log, **kw):
    """The figures and the tables of a paper in one go, for every kind of graph that is loaded. Main_text: the comparison
    figures, the XRD sample pages you named and the tables. Supplementary: the single graph of every other sample.
    Each folder gets its own Origin project."""
    ps = sp.paper_set(singles, opt, main_names); os.makedirs(outdir, exist_ok=True); project = kw.pop("project", "Paper"); stop = kw.get("stop")
    contents = "Main_text\n" + "\n".join(ps["lines_main"]) + "\n\nSupplementary\n" + ("\n".join(ps["lines_supp"]) or "  (nothing)")
    log("Paper set:\n" + contents + "\n" + "\n".join(sp.journal_lines(kw.get("journal"), getattr(kw.get("style"), "curve", 1.5))))
    if ps["missing"]: log("!! not found among the fit graphs: " + ", ".join(ps["missing"]) + " (check the names typed for the main text)")
    d1, d2 = os.path.join(outdir, "Main_text"), os.path.join(outdir, "Supplementary"); drv = drv2 = None
    for d_ in (d1, d2, os.path.join(d1, "publication"), os.path.join(d2, "publication")):      # figures and tables of an earlier paper set in this folder would mix with the new ones
        if os.path.isdir(d_):
            for f_ in os.listdir(d_):
                if re.match(r"^(Figure|Table)_S?\d+_", f_) and os.path.isfile(os.path.join(d_, f_)):
                    try: os.remove(os.path.join(d_, f_))
                    except Exception: pass
    try:
        if ps["supp"]: drv2 = run_items(ps["supp"], d2, log, project=project + "_supplementary", **kw)      # first, so Origin ends with the main-text figures open
        if stop and stop(): return drv2
        drv = run_items(ps["main"], d1, log, project=project + "_main_text", **kw)
    finally:
        for it in ps["main"] + ps["supp"]: it.__dict__.pop("paper_name", None)          # the graphs in your list keep their own names
    for t in ps["tables"]:
        try:
            d_ = d1 if t["where"] == "main" else d2; os.makedirs(d_, exist_ok=True)
            sp.write_table(t["table"], os.path.join(d_, t["file"] + ".xlsx"), t["note"], t["title"]); log(f"{t['title']}  saved: {os.path.basename(d_)}\\{t['file']}.xlsx (and .csv)")
        except Exception: log(f"!! {t['file']} could not be written:\n" + traceback.format_exc())
    try: open(os.path.join(outdir, "Paper_set_contents.txt"), "w", encoding="utf-8").write("Paper set made by Origin plot app " + sp.VERSION + "\n\n" + contents + "\n\nDraft captions: publication\\captions.txt in each folder. Edit them before use.\n")
    except Exception: pass
    if drv is not None and getattr(drv, "result", None):
        r2 = getattr(drv2, "result", None) or {}; nt = sum(1 for t in ps["tables"] if t["where"] == "main")
        t_ = f"Paper set: {ps['n_main']} main-text figures and {nt} table(s), {ps['n_supp']} supplementary figures · main text: " + drv.result.get("text", "")
        if r2.get("text"): t_ += " · supplementary: " + r2["text"].split(" · publication")[0]
        if ps["missing"]: t_ += " · NOT FOUND: " + ", ".join(ps["missing"])
        drv.result["text"] = t_; drv.result["failed"] = list(drv.result.get("failed") or []) + list(r2.get("failed") or [])
    return drv

def _confirmed():
    try:
        import paper_figures as pf_; return list(pf_.CONFIRMED_ACTIONS)
    except Exception: return []

def save_analysis(label, curves, st_, folder, src, stop=None):
    """Analysis > <tool> on the curves, written to `folder`: new curves as CSV, result tables as CSV, a provenance JSON each.
    Returns (files, tables, notes), ("error", message), or ("stopped", message) when stop() said so (nothing is left behind then).
    Used by both windows."""
    import analysis_tools as at_, json as _json, hashlib, datetime as _dt
    grp = at_.TOOLS[label][0]
    stopped = lambda: bool(stop and stop())
    if stopped(): return ("stopped", "stopped before it began")
    try: res_ = at_.run(label, curves, **st_)
    except at_.AnalysisError as e_: return ("error", str(e_))
    if stopped(): return ("stopped", "stopped: nothing was written")
    files_, tables_ = [], []
    written_ = []                                       # every file of this run, removed again if you press Stop
    safe = lambda t_: re.sub(r"[^A-Za-z0-9_.-]+", "_", t_).strip("_")[:90]
    for c_, r_ in res_:
        if stopped():
            for f in list(files_) + written_:
                try: os.remove(f)
                except OSError: pass
            return ("stopped", "stopped: the files of this run were removed")
        stem = safe(f"{c_.name if c_ is not None else 'curves'}_{label}")
        prov = {"what": f"Analysis > {grp} > {label}", "method": r_.note, "settings": st_, "app_version": sp.VERSION,
                "made": _dt.datetime.now().isoformat(timespec="seconds"), "inputs": []}
        for cc_ in ([c_] if c_ is not None else curves):
            pth = src.get(cc_.name, "")
            try: sha = hashlib.sha256(open(pth, "rb").read()).hexdigest() if pth and os.path.isfile(pth) else ""
            except Exception: sha = ""
            prov["inputs"].append({"curve": cc_.name, "file": os.path.basename(pth), "sha256": sha, "x": cc_.xname, "y": cc_.yname, "points": int(len(cc_.x))})
        if r_.curves:
            groups_ = []
            for nm_, x_, y_ in r_.curves:                  # curves on the same x go into one table
                g_ = next((g for g in groups_ if len(g[0]) == len(x_) and np.allclose(g[0], x_)), None)
                if g_ is None: groups_.append([np.asarray(x_, float), [(nm_, np.asarray(y_, float))]])
                else: g_[1].append((nm_, np.asarray(y_, float)))
            for k_, (x_, cols_) in enumerate(groups_):
                df_ = pd.DataFrame({r_.xname or "x": x_, **{n_: v_ for n_, v_ in cols_}})
                f_ = os.path.join(folder, stem + (f"_{k_ + 1}" if len(groups_) > 1 else "") + ".csv")
                i_ = 2
                while os.path.exists(f_): f_ = os.path.join(folder, stem + f"_{i_}.csv"); i_ += 1
                df_.to_csv(f_, index=False, encoding="utf-8-sig"); files_.append(f_)
                prov.setdefault("outputs", []).append(os.path.basename(f_))
        if r_.table is not None and len(r_.table):
            f_ = os.path.join(folder, stem + "_results.csv"); r_.table.to_csv(f_, index=False, encoding="utf-8-sig"); written_.append(f_)
            tables_.append((f"{label}: {c_.name if c_ is not None else ', '.join(cc.name for cc in curves)}", r_.table))
            prov.setdefault("outputs", []).append(os.path.basename(f_))
        with open(os.path.join(folder, stem + "_provenance.json"), "w", encoding="utf-8") as fh: _json.dump(prov, fh, indent=1, default=str)
        written_.append(os.path.join(folder, stem + "_provenance.json"))
    if stopped():
        for f in list(files_) + written_:
            try: os.remove(f)
            except OSError: pass
        return ("stopped", "stopped: the files of this run were removed")
    return files_, tables_, [r_.note for _, r_ in res_][:1]


def run_items(items, outdir, log, style=None, dry=False, png=True, pdf=True, keep_open=True, project="Smart_plots", settings=None, session=None, stop=None, progress=None, pub=True, pub_width=None, journal=None):
    """Draw already-built smart-plot items in Origin; save analysis tables, panel figures, the processing record and the session."""
    import json
    os.makedirs(outdir, exist_ok=True)
    if not items: log("Nothing selected."); return None
    no_origin = ""
    try: drv = Driver(outdir, log, style, dry, png, pdf)
    except Busy as e:                                   # a second drawing would write into the workbooks of the first one
        log("!! " + str(e)); r_ = type("NotDrawn", (), {})(); r_.result = dict(text="Nothing was drawn: another drawing is still running in Origin", failed=["Origin is busy"], refused=0, drawn=0, notes=0, cancelled=False, total=len(items)); r_.out = os.path.abspath(outdir); return r_
    except Exception as e:                              # Origin is not installed or did not start: the app's own publication files are still made
        no_origin = str(e); log(f"!! Origin could not be started ({e}). I still make the publication files of every graph myself.")
        drv = Driver(outdir, log, style, True, png, pdf)
    st = drv.st; outputs = {}; pubdir = os.path.join(drv.out, "publication")
    if pub:
        try: os.remove(os.path.join(pubdir, "captions.txt"))
        except Exception: pass
    plain = [it for it in items if not isinstance(it, sp.Board)]; boards = [it for it in items if isinstance(it, sp.Board)]
    for b in boards:                                   # the panels of a figure are needed in Origin too
        plain += [m for m in b.members if not any(m is p for p in plain)]
    failed, notes, drawn, cancelled = [], 0, 0, False; jchecks = []; jfail = [0]
    for k_, it in enumerate(plain):
        if stop and stop(): cancelled = True; log("Cancelled: the remaining graphs were not drawn."); break
        if progress: progress(k_ + 1, len(plain) + len(boards), it.title.strip())
        tag = tag_of(it); files = [tag + e for e, on in ((".png", png), (".pdf", pdf)) if on]
        try:
            log(f"{it.title}")
            ja, jcol = sp.journal_args(it, journal) if pub else ({}, "")          # ONE resolved size and letter size for this figure: used by Origin and by the app's own files
            if ja and pub_width: ja["width_mm"] = pub_width                         # a width you typed yourself wins
            final = sp.final_size(it, ja.get("width_mm"), ja.get("max_h_mm"), ja.get("fs")) if ja else None
            if it.spec.get("figtype"):                                              # gallery graph types: the equivalent graphs, and one line on what Origin does not get
                for suf_, s_ in it.spec.get("origin_specs") or []: drv.draw_spec(s_, tag + ("_" + re.sub(r"[^A-Za-z0-9_-]+", "_", suf_) if suf_ else ""), None)
                log(f"   Origin: {len(it.spec.get('origin_specs') or [])} graph(s)" + (f"; {it.spec['origin_note']}" if it.spec.get("origin_note") else ""))
                final = None
            else: drv.draw_spec(it.spec, tag, final)
            if final: log(f"   Origin graph (drawn by Origin): page {final[0] * 25.4:.0f} x {final[1] * 25.4:.0f} mm, letters scaled for about {final[2]:g} pt, as asked by {str(journal).split(' (')[0]}")
            if it.results is not None:
                it.results.to_csv(os.path.join(drv.out, tag + "_analysis.csv"), index=False); files.append(tag + "_analysis.csv"); log("   analysis saved: " + tag + "_analysis.csv")
            for k_, tb in (getattr(it, "extra", None) or {}).items():
                if tb is not None and len(tb): tb.to_csv(os.path.join(drv.out, f"{tag}_{k_}.csv"), index=False); files.append(f"{tag}_{k_}.csv"); log(f"   {k_} saved: {tag}_{k_}.csv")
            if getattr(it, "summary", None) is not None:
                it.summary.to_csv(os.path.join(drv.out, tag + "_replicates_mean_SD.csv"), index=False); files.append(tag + "_replicates_mean_SD.csv"); log("   mean and SD of the replicates saved: " + tag + "_replicates_mean_SD.csv")
            for w in it.warnings: log("   note: " + w)
            if pub:
                try:
                    if pub_width: ja["width_mm"] = pub_width                # a width you typed yourself wins
                    fl, size = sp.export_publication(it, pubdir, ja.pop("width_mm", None), st.curve, st.axis, name=tag, **ja); files += ["publication/" + f_ for f_ in fl if not f_.startswith("(")]
                    log(f"   publication files (drawn by the app itself, not by Origin), {size[0]:.0f} x {size[1]:.0f} mm: publication/{tag} (.png at 600 dpi, .tif at {ja.get('dpi', 600)} dpi, .pdf, .svg" + (", .eps)" if ja.get("eps") else ")"))
                    cl_, bad_ = sp.check_publication(re.sub(r"[^A-Za-z0-9_-]+", "_", tag).strip("_"), journal)
                    if cl_:
                        jchecks.append((tag, cl_, bad_)); log(f"   journal check of these files: {len([c_ for c_ in cl_ if c_.startswith('PASS')])} passed, {bad_} failed" + ("" if not bad_ else ":\n" + "\n".join("      " + c_ for c_ in cl_ if c_.startswith("FAIL"))))
                        jfail[0] += bad_
                except Exception: log("!! the publication files of this graph could not be made:\n" + traceback.format_exc())
            try: files.append(os.path.basename(sp.write_figure_provenance(os.path.join(drv.out, tag), it, settings if isinstance(settings, dict) else None, _confirmed())))
            except Exception: log("!! the provenance file of this graph could not be written:\n" + traceback.format_exc())
            outputs[id(it)] = files; drawn += 1; notes += len(it.warnings)
        except Exception: failed.append(it.title.strip()); log(f"!! {it.title} failed:\n{traceback.format_exc()}")
    for b in boards:
        if cancelled or (stop and stop()): cancelled = True; break
        try:
            b.build(); drawn += 1; outputs[id(b)] = sp.export_board(b, drv.out, st.curve, st.axis, png, pdf); w, h = b.size_in()
            try: outputs[id(b)] = list(outputs[id(b)]) + [os.path.basename(sp.write_figure_provenance(os.path.join(drv.out, b.name), b, settings if isinstance(settings, dict) else None, _confirmed()))]
            except Exception: log("!! the provenance file of this figure could not be written:\n" + traceback.format_exc())
            log(f"{b.title}\n   saved at exactly {b.width_mm:g} x {h * 25.4:.0f} mm: " + ", ".join(outputs[id(b)]))
            gs = [drv.graphs.get(tag_of(m)) for m in b.members]
            if len(gs) > 1 and all(gs):
                log("   Trying to merge the same panels into one graph in Origin as well. If Origin refuses, use Graph > Merge Graph Windows; the files above are complete either way.")
                r, c = b.grid; drv.ex(f"merge_graph option:=specified graphs:=({','.join(gs)}) row:={r} col:={c};")
        except Exception: drawn -= 1; failed.append(b.title.strip()); log(f"!! {b.title} failed:\n{traceback.format_exc()}")
    try:
        for l_ in sp.save_inputs(plain, drv.out): log("   " + l_)
        log("The data files of these graphs, as imported, are copied into the folder 'inputs' (with their SHA-256 hashes): the results folder is complete on its own.")
    except Exception: log("!! The data files could not be copied into 'inputs':\n" + traceback.format_exc())
    try:
        log("What was done to every graph is written in: " + sp.write_record(plain + boards, drv.out, settings, outputs))
        if session is not None:
            json.dump(session, open(os.path.join(drv.out, "session.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str); log("This session is saved as session.json (Open session… brings it back).")
    except Exception: log("!! The processing record could not be written:\n" + traceback.format_exc())
    try:
        jf_ = sp.write_journal_check(pubdir, journal, jchecks) if jchecks else None
        if jf_: log("Journal check of the publication files: " + jf_)
    except Exception: log("!! The journal check could not be written:\n" + traceback.format_exc())
    drv.save(keep_open, project + ".opj")
    drv.result = dict(drawn=drawn, failed=failed, notes=notes, refused=drv.failed, cancelled=cancelled, total=len(plain) + len(boards))
    msg = f"{drawn} of {len(plain) + len(boards)} drawn"
    if failed: msg += f" · {len(failed)} FAILED: " + "; ".join(failed)
    if cancelled: msg += " · cancelled before the end"
    if notes: msg += f" · {notes} notes to check (lines starting with 'note:')"
    if no_origin: msg += " · ORIGIN DID NOT START: only the app's own publication files were made"
    elif pub: msg += " · publication files are in the folder 'publication'"
    if jchecks: msg += f" · journal check: {jfail[0]} FAILED check(s), see publication/journal_check.txt" if jfail[0] else " · journal check: all checks passed"
    if drv.missing: msg += f" · {drv.missing} CURVES WERE NOT DRAWN by Origin (lines starting with !!)"
    if getattr(drv, "check_text", ""): msg += " · " + drv.check_text
    if drv.failed: msg += f" · {drv.failed} Origin commands were not accepted (lines in brackets above): look at those graphs in Origin"
    drv.result["text"] = msg; log("Result: " + msg + f"\nFiles are in: {drv.out}"); return drv

def import_origin_project(path, outdir, log):
    """Open an Origin project (.opju, .opj) in Origin and write every workbook as a CSV file the app can read (column names
    in the first row, units in the second). Returns the CSV files. New: these Origin commands could not be tested."""
    import pythoncom, win32com.client
    pythoncom.CoInitialize(); org = win32com.client.Dispatch("Origin.ApplicationSI")
    try: org.Visible = 1
    except Exception: pass
    os.makedirs(outdir, exist_ok=True); ok = False
    try: ok = bool(org.Load(path))
    except Exception: ok = False
    if not ok:
        try: ok = bool(org.Execute('doc -o "%s";' % path))
        except Exception: ok = False
    if not ok: raise RuntimeError("Origin could not open this project file")
    cmd = 'doc -e W { expASC type:=csv path:="%s\\%%H.csv" shortname:=0 longname:=1 units:=1; };' % outdir
    try: org.Execute(cmd)
    except Exception as e: log(f"   (Origin refused the export command: {e})")
    files = sorted(os.path.join(outdir, f) for f in os.listdir(outdir) if f.lower().endswith(".csv"))
    log(f"Origin project {os.path.basename(path)}: {len(files)} workbook(s) written as CSV into {outdir}\n   command sent: {cmd}")
    if not files: raise RuntimeError("Origin opened the project but wrote no files. This import is new and could not be tested. In Origin use File > Export > ASCII for each workbook, then add those files here with Add files")
    return files

# ============================================================================= window
# The look of the window comes from theme.py (colours, type, radii, spacing). These names are kept for the code below.
import theme as ui_theme
_T = ui_theme.THEME
BG, CARD, INK, SOFT, ACCENT, ACCENT_DARK, LINE = _T["canvas"], _T["card"], _T["text"], _T["meta"], _T["accent"], _T["accent_hover"], _T["border"]
FIELD_LINE, BTN, BTN_HOT, PLACEHOLDER_INK, SELECT = _T["border_strong"], _T["card"], _T["subtle"], _T["muted"], _T["select"]

def default_results_folder():
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(docs if os.path.isdir(docs) else os.path.expanduser("~"), "Origin plot results")

REMOVED_FILES = {                                         # the modern window (5.29.0-5.29.1) was removed in 5.29.2: the updater adds and replaces files but never
    "modern_window.py": "Origin Plot Studio - modern window",          # deletes them, so its leftover program files are removed here, once. A file
    "modern_ui_assets.py": "GENERATED by tools/build_modern_assets.py", # is removed only when it holds the line that marks it as that program's own.
    "ops_science.py": "Verified repository integration, with deliberately narrow pilot import rules",
    "ops_state.py": "def atomic_json(path: Path, value: dict)",
    "ops_jobs.py": "Cooperative cancellation acknowledged before publication",
    "ops_exports.py": "class FigureSpec:",
    "ops_origin.py": "Only the owning STA thread touches COM"}

HOOKS = {}            # handles for the tests

def gui():
    import json, datetime
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext
    here = os.path.dirname(os.path.abspath(__file__)); logfile = os.path.join(here, "last_run_log.txt"); cfgfile = os.path.join(here, "settings.json")
    try: cfg = json.load(open(cfgfile, encoding="utf-8"))
    except Exception: cfg = {}
    # Sharp drawing on high-resolution screens. Switch off with "dpi_aware": false in settings.json (or ORIGIN_PLOT_DPI=off) if the window comes out the wrong size.
    if cfg.get("dpi_aware", True) and os.environ.get("ORIGIN_PLOT_DPI", "").lower() not in ("off", "0", "no"): ui_theme.enable_dpi_awareness()
    try:                                             # its own button in the taskbar, with the icon of the app instead of Python's
        import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OriginPlotStudio.App")
    except Exception: pass
    root = tk.Tk(); root.title("Origin Plot Studio / Scientific Workbench")
    # The icon of the app on the window, the taskbar and every dialog (otherwise Tk shows its own feather).
    # Two ways, because one of them can fail on some Windows and Tk versions: the .ico file, and a picture.
    try: root.iconbitmap(default=os.path.join(here, "app.ico"))
    except Exception: pass
    try: _icon = tk.PhotoImage(master=root, file=os.path.join(here, "app.png")); root.iconphoto(True, _icon); root._app_icon = _icon
    except Exception: pass
    try: root.withdraw()                              # built out of sight, shown when everything is in place
    except Exception: pass
    try: ui_ = float(os.environ.get("ORIGIN_PLOT_UI_SCALE") or cfg.get("ui_scale") or 0) or None
    except Exception: ui_ = None
    th = ui_theme.install(root, ui_); px = th.px; UI = th.ui; st_ = th.style; FF = th.family
    try:                                             # fit the window to the screen, so the buttons are never cut off
        sw, sh = int(root.winfo_screenwidth()), int(root.winfo_screenheight()); root.geometry(f"{min(px(1440), sw - 40)}x{min(px(940), sh - 90)}+10+10"); root.minsize(min(px(1200), sw - 40), min(px(780), sh - 90))
        if sh < px(1000): root.state("zoomed")
    except Exception: root.geometry("1360x900")
    font, bold, small, big = th.f_body, th.f_bold, th.f_meta, th.f_title
    SP1, SP2, SP3, SP4, SP5 = px(4), px(8), px(12), px(16), px(24)            # one spacing scale for the whole window
    GAP, PAD = px(_T["gap"]), px(_T["pad_card"])
    # Previews: sharp, but never more than 1.5 times the pixels per side, or every redraw gets slow. On Windows matplotlib
    # already multiplies by the display scaling itself, so there the number must not be multiplied a second time.
    PREVIEW_DPI = int(100 * min(UI, 1.5) / (UI if sys.platform == "win32" else 1.0))

    def SText(master=None, **kw):
        """A text box with the thin scroll bar of the theme. Like tkinter's ScrolledText: pack / grid act on its frame."""
        fr = tk.Frame(master, bg=kw.get("bg", CARD)); vbar = ttk.Scrollbar(fr, orient="vertical"); vbar.pack(side="right", fill="y")
        t_ = tk.Text(fr, **kw); t_.pack(side="left", fill="both", expand=True); t_.configure(yscrollcommand=vbar.set); vbar.configure(command=t_.yview); t_.frame = fr; t_.vbar = vbar
        for m_ in ("pack", "pack_forget", "pack_configure", "grid", "grid_forget", "grid_remove", "grid_configure", "place", "place_forget"): setattr(t_, m_, getattr(fr, m_))
        return t_

    # ---------------- the speed recorder: whenever the window does not answer for more than a second, what it was doing is written to slow_log.txt
    class Slow:
        def __init__(self):
            self.beat = _clock(); self.doing = ""; self.path = None; self.lines = []; self.main = __import__("threading").get_ident(); self.t_start = float(os.environ.get("OPS_T0") or 0) or _clock()
        def file(self):
            if self.path is None:
                try: d_ = os.path.dirname(os.path.abspath(sp.store_dir())); os.makedirs(d_, exist_ok=True); self.path = os.path.join(d_, "slow_log.txt")
                except Exception: self.path = os.path.join(here, "slow_log.txt")
                try:
                    if os.path.isfile(self.path) and os.path.getsize(self.path) > 300000: os.remove(self.path)
                except Exception: pass
            return self.path
        def write(self, text):
            try:
                with open(self.file(), "a", encoding="utf-8") as f_: f_.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S  ") + text + "\n")
            except Exception: pass
        def step(self, what):
            outer_ = self
            class _S:
                def __enter__(s_): s_.t = _clock(); s_.was = outer_.doing; outer_.doing = what
                def __exit__(s_, *a):
                    d_ = _clock() - s_.t; outer_.doing = s_.was
                    if d_ > 0.5: outer_.write(f"{d_:5.1f} s  {what}")
            return _S()
        def tick(self):
            self.beat = _clock()
            try: root.after(200, self.tick)
            except Exception: pass
        def watch(self):
            told = False; stack = ""
            while True:
                _sleep(0.25); lag = _clock() - self.beat
                if lag > 1.0 and not told:
                    told = True
                    try:
                        fr = sys._current_frames().get(self.main); stack = "".join(traceback.format_stack(fr)[-9:]) if fr else ""
                        stack = "\n".join("        " + l_.replace(here, "").strip().replace("\n", "  |  ")[:230] for l_ in stack.strip().split("\n  File"))
                    except Exception: stack = ""
                elif told and lag < 0.6:
                    told = False; self.write(f"THE WINDOW DID NOT ANSWER for about {_clock() - self.hung_since:4.1f} s" + (f" while {self.doing}" if self.doing else "") + ". It was here:\n" + stack)
                if not told: self.hung_since = self.beat
        def begin(self):
            self.hung_since = self.beat
            try:
                import platform, matplotlib
                self.write(f"--- started. version {sp.VERSION}, Python {platform.python_version()}, Tk {root.tk.call('info', 'patchlevel')}, matplotlib {matplotlib.__version__}, {platform.platform()}, "
                           f"screen {root.winfo_screenwidth()}x{root.winfo_screenheight()}, scaling {UI:.2f}, rounded pictures {th.rounded}, started with a console {sys.stdout is not None and getattr(sys.stdout, 'name', '') == '<stdout>'}")
            except Exception: pass
            self.tick(); __import__("threading").Thread(target=self.watch, daemon=True).start()
    import time as _t_; _clock = _t_.time; _sleep = _t_.sleep; slow = Slow()

    # ---------------- helpers for the layout
    scrollers = []
    def scrolling(parent, bg=CARD):
        """A part of the window that gets a scroll bar when it is taller than the window, so no control is ever cut off.
        Returns (the frame to place, the frame to fill). A widget packed with expand inside it still takes spare height."""
        outer = ttk.Frame(parent); outer.columnconfigure(0, weight=1); outer.columnconfigure(1, minsize=px(14)); outer.rowconfigure(0, weight=1)
        cv = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0, yscrollincrement=px(24)); cv.grid(row=0, column=0, sticky="nsew")
        vs = ttk.Scrollbar(outer, orient="vertical", command=cv.yview); cv.configure(yscrollcommand=vs.set)
        inner = ttk.Frame(cv); win_ = cv.create_window(0, 0, window=inner, anchor="nw")
        strut = tk.Frame(inner, width=1, height=1, bg=bg); strut.pack(side="left", fill="y")       # as tall as the view: content that is shorter still fills it
        def fit(event=None):
            try:
                have = cv.winfo_height()
                if int(strut.cget("height")) != have: strut.configure(height=have)
                need = max(inner.winfo_reqheight(), have)
                cv.itemconfigure(win_, width=cv.winfo_width()); cv.configure(scrollregion=(0, 0, cv.winfo_width(), need))
                if need > have + 1 and not vs.winfo_ismapped(): vs.grid(row=0, column=1, sticky="ns", padx=(SP1, 0))
                elif need <= have + 1 and vs.winfo_ismapped(): vs.grid_remove(); cv.yview_moveto(0)
            except Exception: pass
        inner.bind("<Configure>", fit); cv.bind("<Configure>", fit); scrollers.append((outer, cv, vs)); outer.canvas = cv
        outer.refit = lambda: (root.after_idle(fit), root.after(120, fit))      # call after adding or removing content while the window keeps its size
        return outer, inner
    def on_wheel(event):
        """The mouse wheel scrolls the part under the pointer; lists and text boxes keep their own scrolling."""
        try:
            w_ = root.winfo_containing(event.x_root, event.y_root)
            if w_ is None or (w_.winfo_class() in ("Listbox", "Text", "TCombobox", "ComboboxListbox") and not getattr(w_, "pass_wheel", False)): return
            while w_ is not None:
                for outer, cv, vs in scrollers:
                    if w_ is outer:
                        if vs.winfo_ismapped(): cv.yview_scroll(-3 if (getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0) else 3, "units")
                        return
                w_ = w_.master
        except Exception: pass
    for ev_ in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        try: root.bind_all(ev_, on_wheel, add="+")
        except Exception: pass
    def autowrap(label, host, used=0, most=900, least=220):
        """A hint wraps at the width it really has (never wider than a comfortable line), instead of at a fixed number that only fits one window size."""
        most, least = px(most), px(least)
        def fit(event):
            try:
                w_ = int(max(least, min(most, event.width - used)))
                if abs(int(str(label.cget("wraplength")) or 0) - w_) > 6: label.configure(wraplength=w_)
            except Exception: pass
        host.bind("<Configure>", fit, add="+"); label.configure(justify="left"); return label
    def form(parent, label_w=132):
        """A form whose labels share one column and whose fields share both edges."""
        label_w = px(label_w)
        f = ttk.Frame(parent); f.columnconfigure(0, minsize=label_w); f.columnconfigure(1, weight=1); f.rows = 0
        def row(text, make, extra=None, hint=None):
            r = f.rows; f.rows += 1 + bool(hint)
            ttk.Label(f, text=text, wraplength=label_w - SP2, justify="left", foreground=_T["text2"]).grid(row=r, column=0, sticky="w", pady=SP1, padx=(0, SP2))
            w_ = make(f); w_.grid(row=r, column=1, sticky="we", pady=SP1, columnspan=1 if extra else 2); x_ = None
            if extra: x_ = extra(f); x_.grid(row=r, column=2, sticky="e", padx=(SP2, 0), pady=SP1)
            if hint: autowrap(ttk.Label(f, text=hint, style="Soft.TLabel"), f, used=label_w, most=520).grid(row=r + 1, column=1, columnspan=2, sticky="w", pady=(0, SP1))
            return w_, x_
        f.row = row; return f
    def step(parent, number, title, hint=None, first=False, fold=None):
        """The heading of one step: number, title and one line of help. With fold=<name>, the step folds away (remembered for next time)."""
        h = ttk.Frame(parent); h.pack(fill="x", pady=(0 if first else SP4 + SP1, 0)); body = ttk.Frame(parent)
        ttk.Label(h, text=str(number), style="StepNo.TLabel", width=2).pack(side="left")
        if fold is None:
            ttk.Label(h, text=title, style="Step.TLabel").pack(side="left")
            if hint: autowrap(ttk.Label(parent, text=hint, style="Soft.TLabel"), parent, most=560).pack(anchor="w", pady=(2, SP2))
            body.pack(fill="x"); return body
        opened = [bool(cfg.get(fold, False))]; folds[fold] = opened; hl = autowrap(ttk.Label(parent, text=hint or "", style="Soft.TLabel"), parent, most=560)
        def toggle(to=None):
            opened[0] = (not opened[0]) if to is None else bool(to); btn.config(text=("▾  " if opened[0] else "▸  ") + title)
            if opened[0]: hl.pack(anchor="w", pady=(2, SP2), after=h); body.pack(fill="x", after=hl)
            else: hl.pack_forget(); body.pack_forget()
            for o_, c_, v_ in scrollers:
                try: o_.refit()
                except Exception: pass
        btn = ttk.Button(h, style="Section.TButton", command=toggle, takefocus=True, cursor="hand2"); btn.pack(side="left", fill="x", expand=True); toggle(opened[0]); return body
    folds = {}
    def rule(parent): return tk.Frame(parent, bg=LINE, height=1)             # a 1 px divider in the border colour
    def kicker(parent, text, **kw): return ttk.Label(parent, text=text.upper(), style="Kicker.TLabel", **kw)
    def listbox(parent, **kw):
        """A list inside a rounded field. Returns (the frame to place, the list)."""
        fr = ttk.Frame(parent, style="Field.TFrame", padding=px(2))
        opt = dict(exportselection=False, bg=CARD, fg=INK, font=font, relief="flat", borderwidth=0, highlightthickness=0, selectbackground=SELECT, selectforeground=INK, activestyle="none"); opt.update(kw)
        lb_ = tk.Listbox(fr, **opt); sb_ = ttk.Scrollbar(fr, orient="vertical", command=lb_.yview); lb_.configure(yscrollcommand=sb_.set)
        sb_.pack(side="right", fill="y", pady=px(4), padx=(0, px(2))); lb_.pack(side="left", fill="both", expand=True, padx=(px(6), 0), pady=px(4)); return fr, lb_

    # ---------------- the window: header, the views, the bar with the view switcher
    frm = ttk.Frame(root, style="Canvas.TFrame", padding=px(_T["margin"])); frm.pack(fill="both", expand=True)
    head = ttk.Frame(frm, style="Canvas.TFrame"); head.grid(row=0, column=0, sticky="we", pady=(0, GAP))
    act = {}; hb = ttk.Frame(head, style="Canvas.TFrame"); hb.pack(side="right", anchor="center")
    dirtytxt = tk.StringVar(value="")
    ttk.Label(hb, textvariable=dirtytxt, style="Canvas.Soft.TLabel", foreground=_T["warn_text"]).pack(side="left", padx=(0, SP3))
    updpilltxt = tk.StringVar(value=""); updpill = ttk.Label(hb, textvariable=updpilltxt, style="Canvas.Warn.Pill.TLabel", cursor="hand2"); updpill.bind("<Button-1>", lambda e: act["update"]())      # shown when a newer version is waiting; a click installs it
    aipilltxt = tk.StringVar(value="●  AI not connected")
    aipill = ttk.Label(hb, textvariable=aipilltxt, style="Canvas.Idle.Pill.TLabel", cursor="hand2"); aipill.pack(side="left", padx=(0, SP3))        # the real state of the link to the AI; a click opens the Assistant
    ttk.Button(hb, text="Save session", style="Canvas.TButton", command=lambda: act["save"]()).pack(side="left", padx=(0, SP2))
    topbtn = [ttk.Button(hb, text="Draw ticked", style="Canvas.Accent.TButton", command=lambda: act["draw_sel"]())]; topbtn[0].pack(side="left")
    ttk.Label(head, text="SCIENTIFIC WORKBENCH", style="Canvas.Kicker.TLabel").pack(anchor="w")
    ttk.Label(head, text="Data, preview, assistant — together", style="Canvas.Title.TLabel").pack(anchor="w", pady=(px(2), 0))
    nb = ttk.Notebook(frm, style="Hidden.TNotebook"); nb.grid(row=1, column=0, sticky="nsew")
    t6 = ttk.Frame(nb, style="Canvas.TFrame"); t2 = ttk.Frame(nb, style="Canvas.TFrame")
    t5 = ttk.Frame(nb, style="Card.TFrame", padding=PAD); t4 = ttk.Frame(nb, style="Card.TFrame", padding=PAD); t3 = ttk.Frame(nb, style="Card.TFrame", padding=PAD)
    VIEWS = [(t6, "Focused Copilot"), (t2, "Scientific Workbench"), (t5, "Own graph"), (t4, "Analysis settings"), (t3, "Look and saving")]
    for t_, n_ in VIEWS: nb.add(t_, text=n_)

    # ---------------- variables (remembered between runs)
    out = tk.StringVar(value=cfg.get("out") or default_results_folder()); proj = tk.StringVar(value=cfg.get("project", "My_graphs"))
    dated = tk.BooleanVar(value=cfg.get("dated", False)); png = tk.BooleanVar(value=cfg.get("png", True)); pdf = tk.BooleanVar(value=cfg.get("pdf", True))
    pubv = tk.BooleanVar(value=cfg.get("pub", True)); pubw = tk.StringVar(value=str(cfg.get("pub_width", "Automatic")))
    keep = tk.BooleanVar(value=cfg.get("keep", True)); cw = tk.StringVar(value=str(cfg.get("curve", "1.5"))); aw = tk.StringVar(value=str(cfg.get("axis", "1.5"))); tw = tk.StringVar(value=str(cfg.get("tick", "0.75"))); zw = tk.StringVar(value=str(cfg.get("zoom_curve", "3.8"))); za = tk.StringVar(value=str(cfg.get("zoom_axis", "3.8"))); zl = tk.StringVar(value=str(cfg.get("zoom_label", "24")))
    mode = tk.StringVar(value=cfg.get("mode", sp.MODES[0])); kind = tk.StringVar(value="Automatic"); maxlab = tk.StringVar(value=str(cfg.get("peak_labels", "all"))); labxy = tk.BooleanVar(value=cfg.get("labxy", False)); useref = tk.BooleanVar(value=False)
    tube = tk.StringVar(value=cfg.get("wavelength", list(sp.TUBES)[0]) if cfg.get("wavelength") in sp.TUBES or re.search(r"\d", str(cfg.get("wavelength", ""))) else list(sp.TUBES)[0]); tgam = tk.StringVar(value=cfg.get("tga_mass", sp.TGA_MASS[0])); tgar = tk.StringVar(value=cfg.get("tga_ranges", ""))
    ftirs = tk.StringVar(value=cfg.get("ftir_signal", sp.FTIR_SIGNAL[0])); caloa = tk.StringVar(value=cfg.get("calo_ages", "")); calof = tk.StringVar(value=str(cfg.get("calo_from", "0"))); caloi = tk.StringVar(value=cfg.get("calo_info", "")); caloe = tk.StringVar(value=str(cfg.get("calo_excl", "45")))
    repl = tk.StringVar(value=cfg.get("replicates", sp.REPLICATES[0])); sample = tk.StringVar(value=""); fw = tk.StringVar(value=str(cfg.get("fig_width", "175"))); fcols = tk.StringVar(value=cfg.get("fig_cols", "Automatic"))
    ori = tk.StringVar(value=cfg.get("orientation", sp.ORIENTATIONS[0]) if cfg.get("orientation") in sp.ORIENTATIONS else sp.ORIENTATIONS[0])
    insv = tk.StringVar(value=str(cfg.get("inset") or sp.INSETS[0])); fcol = tk.StringVar(value=cfg.get("fit_colours", sp.FIT_COLOURS[0]) if cfg.get("fit_colours") in sp.FIT_COLOURS else sp.FIT_COLOURS[0]); ltxt = tk.StringVar(value=cfg.get("label_text", sp.LABEL_TEXT[0]) if cfg.get("label_text") in sp.LABEL_TEXT else sp.LABEL_TEXT[0])
    ptr = tk.StringVar(value=cfg.get("pointers", sp.POINTERS[0]) if cfg.get("pointers") in sp.POINTERS else sp.POINTERS[0])
    jour = tk.StringVar(value=cfg.get("journal") if cfg.get("journal") in sp.JOURNALS else list(sp.JOURNALS)[0])
    pmain = tk.StringVar(value=str(cfg.get("paper_main") or sp.PAPER_MAIN))
    lsz = tk.StringVar(value=cfg.get("label_size", sp.LABEL_SIZES[0]) if cfg.get("label_size") in sp.LABEL_SIZES else sp.LABEL_SIZES[0])
    play = tk.StringVar(value=cfg.get("page_layout", sp.PAGE_LAYOUTS[0]) if cfg.get("page_layout") in sp.PAGE_LAYOUTS else sp.PAGE_LAYOUTS[0])
    pf = tk.StringVar(value=cfg.get("per_fig", sp.PER_FIG[0]) if cfg.get("per_fig") in sp.PER_FIG else sp.PER_FIG[0])
    stk = tk.StringVar(value=cfg.get("stack_style", sp.STACK_STYLES[0]) if cfg.get("stack_style") in sp.STACK_STYLES else sp.STACK_STYLES[0])
    fst = tk.StringVar(value=cfg.get("fit_style", sp.FIT_STYLES[0]) if cfg.get("fit_style") in sp.FIT_STYLES else sp.FIT_STYLES[0])
    xph = tk.StringVar(value=cfg.get("xrd_phases", sp.XRD_PHASES[0])); xlab = tk.StringVar(value=cfg.get("xrd_labels") if cfg.get("xrd_labels") in sp.XRD_LABELS else sp.XRD_LABELS[0]); xbg = tk.StringVar(value=cfg.get("xrd_background", sp.XRD_BG[0]))
    xstore = tk.BooleanVar(value=bool(cfg.get("xrd_store", True)))
    tgamat = tk.StringVar(value=cfg.get("tga_material") if cfg.get("tga_material") in sp.TGA_MATERIAL else sp.TGA_MATERIAL[0]); tgam0 = tk.StringVar(value=str(cfg.get("tga_m0", "")))
    tgac = tk.StringVar(value=cfg.get("tga_curves") if cfg.get("tga_curves") in sp.TGA_CURVES else sp.TGA_CURVES[0])
    analysis = {"tga_curves": tgac, "tga_material": tgamat, "tga_m0": tgam0, "xrd_store": xstore, "fit_style": fst, "xrd_phases": xph, "xrd_labels": xlab, "xrd_background": xbg, "wavelength": tube, "tga_mass": tgam, "tga_ranges": tgar, "ftir_signal": ftirs, "calo_ages": caloa, "calo_from": calof, "calo_info": caloi, "calo_excl": caloe, "replicates": repl, "stack_style": stk, "orientation": ori, "per_fig": pf, "inset": insv, "label_text": ltxt, "pointers": ptr, "page_layout": play, "fit_colours": fcol, "label_size": lsz}
    status = tk.StringVar(value="Ready when you are.")

    def remember():
        try:
            c_ = {"out": out.get(), "project": proj.get(), "dated": dated.get(), "png": png.get(), "pdf": pdf.get(), "keep": keep.get(), "fig_width": fw.get(), "fig_cols": fcols.get(),
                  "curve": cw.get(), "axis": aw.get(), "tick": tw.get(), "zoom_curve": zw.get(), "zoom_label": zl.get(), "zoom_axis": za.get(), **({"update_source": cfg["update_source"]} if "update_source" in cfg else {}), "update_token": cfg.get("update_token", ""), "layout": lay["name"], "layout_splits": lay["splits"], "dpi_aware": cfg.get("dpi_aware", True), "ui_scale": cfg.get("ui_scale", 0), "paper_open": bool(folds["paper_open"][0]) if "paper_open" in folds else False, "paper_main": pmain.get(), "journal": jour.get(), "pub": pubv.get(), "pub_width": pubw.get(), "peak_labels": maxlab.get(), "labxy": labxy.get(), "mode": mode.get()}
            c_.update({k: v.get() for k, v in analysis.items()}); json.dump(c_, open(cfgfile, "w", encoding="utf-8"), indent=1)
        except Exception: pass
    def choose_folder():
        v = filedialog.askdirectory(title="Where should your results be saved?", initialdir=out.get() if os.path.isdir(out.get()) else os.path.expanduser("~"))
        if v: out.set(os.path.normpath(v)); remember()
    def open_folder(path=None):
        p = path or out.get()
        try:
            os.makedirs(p, exist_ok=True); os.startfile(p)
        except Exception as e: log(f"I could not open the folder ({e}). It is here: {p}")
    def run_folder():
        p = out.get().strip() or default_results_folder()
        return os.path.join(p, datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")) if dated.get() else p
    def project_name(): return re.sub(r'[\\/:*?"<>|]', "_", proj.get().strip()) or "My_graphs"
    def style():
        def num(v, d):
            try: return max(0.1, float(str(v.get()).replace(",", ".")))
            except Exception: return d
        return Style(num(cw, 1.5), num(aw, 1.5), num(tw, 0.75), num(zw, 3.8), num(zl, 24), num(za, 3.8))

    # ---------------- bottom: what is happening
    foot = ttk.Frame(frm, style="Canvas.TFrame"); foot.grid(row=2, column=0, sticky="nsew", pady=(GAP, 0))
    sbar = ttk.Frame(foot, style="Canvas.TFrame"); sbar.pack(fill="x"); sbar.columnconfigure(0, weight=1)
    sleft = ttk.Frame(sbar, style="Canvas.TFrame", height=px(36)); sleft.grid(row=0, column=0, sticky="we"); sleft.pack_propagate(False); sright = ttk.Frame(sbar, style="Canvas.TFrame"); sright.grid(row=0, column=2, sticky="e")
    prog = ttk.Progressbar(sleft, mode="indeterminate", length=px(120))
    cancel = [False]; cancelbtn = ttk.Button(sleft, text="Cancel", style="Canvas.TButton", command=lambda: (cancel.__setitem__(0, True), status.set("Cancelling after the current graph …")))
    statlab = ttk.Label(sleft, textvariable=status, style="Canvas.Status.TLabel"); statlab.pack(side="left")              # one line; the full text is also in the details
    def working(on):
        """The progress bar and Cancel are only there while something is running: an idle bar looked like a stuck one."""
        try:
            if on: prog.pack(side="left", padx=(0, SP2), before=statlab); cancelbtn.pack(side="left", padx=(0, SP3), before=statlab); cancelbtn.config(state="normal"); prog.start(12)
            else: prog.stop(); prog.pack_forget(); cancelbtn.pack_forget()
        except Exception: pass
    # the view switcher: the dark pill in the middle of the bar. Ctrl+1 … Ctrl+5 do the same.
    switch = ttk.Frame(sbar, style="Switch.TFrame", padding=px(5)); switch.grid(row=0, column=1, padx=GAP); segs = []
    def view(k):
        try: nb.select(VIEWS[k][0])
        except Exception: pass
    def view_shown(event=None):
        try: now = str(nb.select())
        except Exception: return
        try:                                                 # draw the preview of this view now, if the graph changed while it was out of sight
            for which, tab in (("full", t2), ("live", t6)):
                if stale[which] is not None and now == str(tab):
                    it_ = next((i_ for i_ in items if sp.key_of(i_) == stale[which]), None); stale[which] = None
                    if it_ is not None: root.after(40, lambda it_=it_, f_=(show if which == "full" else assistant_show): f_(it_))       # the view first, then its graph
            if now == str(t6) and cards_stale[0]: cards_stale[0] = False; root.after(10, lambda: act["cards"]())
        except Exception: pass
        for k_, b_ in enumerate(segs):
            try: b_.config(style="SegOn.TButton" if str(VIEWS[k_][0]) == now else "Seg.TButton")
            except Exception: pass
    for k_, (t_, n_) in enumerate(VIEWS):
        segs.append(ttk.Button(switch, text=f"{k_ + 1} \u00B7 {n_}", style="Seg.TButton", cursor="hand2", takefocus=False, command=lambda k_=k_: view(k_))); segs[-1].pack(side="left", padx=(0 if not k_ else px(2), 0))
        root.bind(f"<Control-Key-{k_ + 1}>", lambda e, k_=k_: view(k_))
    nb.bind("<<NotebookTabChanged>>", view_shown, add="+"); view_shown()
    try: aipill.bind("<Button-1>", lambda e: view(0))
    except Exception: pass
    ttk.Button(sright, text="Open results folder", style="Canvas.TButton", command=lambda: open_folder(last_folder[0])).pack(side="right")
    details = [False]; detbtn = ttk.Button(sright, text="Show details", style="Canvas.TButton", command=lambda: show_details(not details[0])); detbtn.pack(side="right", padx=SP2)
    logcard = ttk.Frame(foot, style="Card.TFrame", padding=px(10))
    logbox = SText(logcard, height=7, bg=CARD, fg=INK, font=("Consolas", -px(12)), relief="flat", borderwidth=0, padx=SP2, pady=SP1, highlightthickness=0); logbox.pack(fill="both", expand=True)
    def show_details(on):
        """The detailed log (analysis tables, how files were combined, notes) is folded away until you want it."""
        details[0] = bool(on)
        try:
            if on: logcard.pack(fill="x", pady=(SP3, 0)); detbtn.config(text="Hide details")              # a fixed strip of 7 lines: it no longer takes a fifth of the window
            else: logcard.pack_forget(); detbtn.config(text="Show details"); frm.rowconfigure(2, weight=0)
        except Exception: pass
    frm.rowconfigure(1, weight=4); frm.rowconfigure(2, weight=0); frm.columnconfigure(0, weight=1)
    last_folder = [None]

    problems = []; nograph = []
    def log(m):
        root.after(0, lambda: (logbox.insert("end", str(m) + "\n"), logbox.see("end")))
        if "!!" in str(m):
            problems.append((datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), str(m)[:3000]))
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(sp.store_dir())), "problems.txt"), "a", encoding="utf-8") as f: f.write(f"--- {problems[-1][0]}  (version {sp.VERSION})\n{problems[-1][1]}\n")
            except Exception: pass
        if "!!" in str(m) and not details[0]: root.after(0, lambda: show_details(True))        # problems are never hidden
        try:
            with open(logfile, "a", encoding="utf-8") as f: f.write(str(m) + "\n")
        except Exception: pass
    buttons = list(topbtn); busy = [False]
    def background(work, done, what):
        """Run slow work (reading and analysing files) away from the window, so the window never freezes."""
        if busy[0]: status.set("One moment please, I am still working on the previous step."); return
        busy[0] = True; cancel[0] = False
        for b in buttons: b.config(state="disabled")
        working(True); status.set(what)
        def run():
            t_ = _clock()
            try: res = work()
            except sp.Cancelled: res = None; log("Cancelled.")
            except Exception: res = None; log("!! Something went wrong:\n" + traceback.format_exc())
            if _clock() - t_ > 2: slow.write(f"{_clock() - t_:5.1f} s  in the background (the window stays usable): {what}")
            def fin():
                busy[0] = False; working(False)
                for b in buttons: b.config(state="normal")
                with slow.step(f"showing the result of: {what}"):
                    try: done(res)
                    except Exception: log("!! Something went wrong:\n" + traceback.format_exc())
            root.after(0, fin)
        threading.Thread(target=run, daemon=True).start()
    def start(job, what, folder):
        if busy[0]: status.set("One moment please, I am still working on the previous step."); return
        remember(); last_folder[0] = folder; busy[0] = True; cancel[0] = False
        try: open(logfile, "w").close()
        except Exception: pass
        for b in buttons: b.config(state="disabled")
        working(True); status.set(what + " Origin will open by itself; please leave it alone until I am finished.")
        try: topbtn[0].config(text="Drawing\u2026")
        except Exception: pass
        def work():
            try:
                drv = job(); r_ = getattr(drv, "result", None) or {}
                msg = (r_.get("text") or "Finished") + ".  Folder: " + folder
                if r_.get("failed") or r_.get("refused"): root.after(0, lambda: show_details(True))
            except Exception: log("!! Something went wrong:\n" + traceback.format_exc()); msg = "That did not work. Press Show details to see why."
            def done():
                busy[0] = False; working(False); status.set(msg)
                try: update_buttons()
                except Exception: pass
                for b in buttons: b.config(state="normal")
            root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    # ---------------- tab: my graphs
    items = []; singles = []; boards = []
    # Left card: the four steps, top to bottom, with the Draw buttons fixed under them. Right card: the large preview. The gap can be dragged.
    workspace = ttk.PanedWindow(t2, orient="horizontal"); workspace.grid(row=0, column=0, sticky="nsew")
    leftcol = ttk.Frame(workspace, style="Card.TFrame", padding=PAD, width=px(560)); leftcol.pack_propagate(False)
    right = ttk.Frame(workspace, style="Card.TFrame", padding=PAD)
    workspace.add(leftcol, weight=0); workspace.add(right, weight=1)
    t2.columnconfigure(0, weight=1); t2.rowconfigure(0, weight=1)
    kicker(leftcol, "Data & plot settings").pack(anchor="w", pady=(0, SP2))
    b2 = ttk.Frame(leftcol, padding=(0, SP3, 0, 0)); b2.pack(side="bottom", fill="x")               # always in view, whatever the height of the window
    rule(leftcol).pack(side="bottom", fill="x")
    lscroll, left = scrolling(leftcol); lscroll.pack(fill="both", expand=True); left.configure(padding=(0, 0, SP2, SP3))
    # 1 --- the data
    s1 = step(left, 1, "Add your data", "Excel, CSV or text files. Every sheet is checked for you.", first=True)
    bar = ttk.Frame(s1); bar.pack(fill="x")
    tickbar = ttk.Frame(left); tickbar.pack(fill="x", pady=(SP3, SP1))
    lf, lb = listbox(left, selectmode="extended", width=20, height=5); lf.pack(fill="both", expand=True)
    # 2 --- how each graph is drawn: one form, labels in one column, fields with common edges
    s2 = step(left, 2, "Check the graph", "Click a line in the list to preview it. Change the type if I guessed wrong.")
    f2 = form(s2); f2.pack(fill="x")
    kbox, _ = f2.row("Graph type", lambda f: ttk.Combobox(f, textvariable=kind, values=sp.KINDS, width=12, state="readonly"), lambda f: ttk.Button(f, text="Suggestions…", command=lambda: act["suggest"]()))
    sent, sapply = f2.row("Sample name", lambda f: ttk.Entry(f, textvariable=sample, width=12), lambda f: ttk.Button(f, text="Apply", command=lambda: act["sample"]()),
                          hint="Graphs with the same sample name are replicates and share one colour.")
    def peak_row(f):
        r = ttk.Frame(f); ttk.Entry(r, textvariable=maxlab, width=6).pack(side="left"); ttk.Label(r, text="all, or a number", style="Soft.TLabel").pack(side="left", padx=(SP2, 0)); return r
    f2.row("Peak labels", peak_row)
    f2.row("", lambda f: ttk.Checkbutton(f, text="Label peaks on XY graphs", variable=labxy))
    mbox, _ = f2.row("Several files of the same kind", lambda f: ttk.Combobox(f, textvariable=mode, values=sp.MODES, width=12, state="readonly"))
    obox, _ = f2.row("Page", lambda f: ttk.Combobox(f, textvariable=ori, values=sp.ORIENTATIONS, width=12, state="readonly"))               # how the pages will look: said here, before drawing
    pbox, _ = f2.row("Sample pages", lambda f: ttk.Combobox(f, textvariable=play, values=sp.PAGE_LAYOUTS, width=12, state="readonly"))
    cbox, _ = f2.row("Fit colours", lambda f: ttk.Combobox(f, textvariable=fcol, values=sp.FIT_COLOURS, width=12, state="readonly"))
    looktxt = tk.StringVar(value=""); autowrap(ttk.Label(s2, textvariable=looktxt, style="Soft.TLabel"), s2, most=560).pack(anchor="w", pady=(SP1, 0))
    # 3 --- optional, so it is folded away until wanted
    s3 = step(left, 3, "Figure for a paper (optional)", "Tick graphs, then make one figure with panels (a), (b) … or the whole set of figures a paper needs.", fold="paper_open")
    f3 = form(s3); f3.pack(fill="x")
    f3.row("Width (mm)", lambda f: ttk.Entry(f, textvariable=fw, width=6))
    f3.row("Columns", lambda f: ttk.Combobox(f, textvariable=fcols, values=["Automatic", "1", "2", "3"], width=10, state="readonly"), lambda f: ttk.Button(f, text="Make panel figure", command=lambda: act["board"]()))
    rule(s3).pack(fill="x", pady=SP3)               # everything a paper needs, in one go
    f3b = form(s3); f3b.pack(fill="x")
    f3b.row("Paper set, main text", lambda f: ttk.Entry(f, textvariable=pmain, width=12), hint="The XRD sample pages that go in the main text.")
    f3b.row("Journal", lambda f: ttk.Combobox(f, textvariable=jour, values=list(sp.JOURNALS), width=12, state="readonly"))
    o9 = ttk.Frame(s3); o9.pack(fill="x", pady=(SP2, SP1))
    ttk.Button(o9, text="Preview paper set (PDF)", command=lambda: act["paper_preview"]()).pack(side="left", padx=(0, SP2)); pbtn = ttk.Button(o9, text="Make paper set", command=lambda: act["paper"]()); pbtn.pack(side="left")
    autowrap(ttk.Label(s3, text="Comparison figures and tables go to Main_text, single graphs to Supplementary, sized for the journal. Preview shows every figure at its printed size first.", style="Soft.TLabel"), s3, most=560).pack(anchor="w")
    # 4 --- where it goes
    s4 = step(left, 4, "Save and draw", "Your figures, the Origin project and the analysis tables go here.")
    f4 = form(s4); f4.pack(fill="x")
    f4.row("Folder", lambda f: ttk.Entry(f, textvariable=out, width=12), lambda f: ttk.Button(f, text="Choose…", command=choose_folder))
    f4.row("Project name", lambda f: ttk.Entry(f, textvariable=proj, width=12))

    canvas = fig = toolbar = None
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        kicker(right, "Full preview").pack(anchor="w"); ttk.Label(right, text="Zoom, pan and check the graph before it is drawn in Origin", style="Step.TLabel").pack(anchor="w", pady=(px(2), SP3))
        pframe = ttk.Frame(right, style="Preview.TFrame", padding=px(6)); pframe.pack(fill="both", expand=True)
        pcard = tk.Frame(pframe, bg="white"); pcard.pack(fill="both", expand=True)
        fig = Figure(figsize=(7.2, 5.2), dpi=PREVIEW_DPI, facecolor="white"); canvas = FigureCanvasTkAgg(fig, master=pcard); toolbar = None
        try:                                           # zoom, pan, reset view and the coordinates under the mouse
            from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
            toolbar = NavigationToolbar2Tk(canvas, pcard, pack_toolbar=False); toolbar.update(); toolbar.pack(side="bottom", fill="x")
            try:                                       # the grey band of the toolbar did not belong to this window
                toolbar.config(background="white")
                for c_ in toolbar.winfo_children(): c_.config(background="white")
            except Exception: pass
            tk.Frame(pcard, bg=LINE, height=1).pack(side="bottom", fill="x")
        except Exception: toolbar = None
        canvas.get_tk_widget().pack(fill="both", expand=True)
        fig.text(0.5, 0.5, "Your graph will appear here\nas soon as you add a file.", ha="center", va="center", color=SOFT, fontsize=12); canvas.draw()
    except Exception as e:
        ttk.Label(right, text="The preview needs the matplotlib package, which could not be loaded:\n%s\nYou can still draw in Origin." % e, style="Soft.TLabel").pack(padx=20, pady=20)

    def options():
        try: n = max(1, int(float(maxlab.get()))); allx = False
        except Exception: n = 15; allx = True                # "all" (or empty): every XRD peak gets its label
        o = {"max_labels": n, "xrd_max": None if allx else n, "stack_labels": None if allx else n, "label_peaks": labxy.get(), "app_dir": here}
        o.update({k: v.get() for k, v in analysis.items()}); return o
    def settings_now():
        s_ = style(); d_ = {k: v.get() for k, v in analysis.items()}
        d_.update({"several files of the same kind": mode.get(), "most peak labels": maxlab.get(), "label peaks on XY graphs": labxy.get(), 
                   "curve weight (pt)": s_.curve, "axis weight (pt)": s_.axis, "tick and leader weight (pt)": s_.tick, "zoomed inset in Origin: curve weight (pt)": s_.zoom_curve, "zoomed inset in Origin: label size (pt)": s_.zoom_label, "zoomed inset in Origin: axis weight (pt)": s_.zoom_axis}); return d_
    selkeys = []; hidden = set(); dirty = [False]; botbtn = []; addbtn = []; shown = [None]; lastrow = [None]
    TICK, NOTICK = " \u2611  ", " \u2610  "               # a ticked box = this graph will be drawn
    def cur(): return [i for i in lb.curselection() if i < len(items)]
    def update_buttons():
        n, N = len(cur()), len(items)
        for b, txt in ((topbtn[0], f"Draw {n} ticked" if n else "Draw ticked"),):
            try: b.config(text=txt)
            except Exception: pass
        for b, txt in zip(botbtn, (f"Draw {n} ticked in Origin" if n else "Draw ticked in Origin", f"Draw all {N}" if N else "Draw all")):
            try: b.config(text=txt)
            except Exception: pass
    def mark_dirty(*a):
        if singles and not dirty[0]: dirty[0] = True; dirtytxt.set("Settings changed – applied when you draw")
    def clean(): dirty[0] = False; dirtytxt.set("")
    def regroup(say=True, opt=None, md=None):
        opt = opt or options(); md = md or mode.get()
        sp.apply_info(singles, opt)
        links = sp.link_xrd(singles, opt)
        if say and links: log("XRD peak lists linked to patterns of the same sample:\n" + "\n".join(links))
        comb, lines = sp.make_groups(singles, md, opt); comb = [c for c in comb if sp.key_of(c) not in hidden]; pool = comb + singles
        for b in list(boards):
            if not b.resolve(pool): boards.remove(b); log(f"{b.name} was removed, because its graphs are no longer in the list.")
            else: b.build()
        items[:] = boards + pool
        if say and lines: log("How I combined your files:\n" + "\n".join(lines))
    def refresh():
        for m_ in sp.store_news(): log("Phase library: " + m_)           # phases of your files that were new to the library
        try: top_ = lb.yview()[0]
        except Exception: top_ = None
        lb.delete(0, "end")                             # the ticks follow the graphs, not the row numbers
        if not items: lb.insert("end", "   Click here, or press “Add files…”, to add your data files")
        for it in items: lb.insert("end", (TICK if sp.key_of(it) in selkeys else NOTICK) + it.title)
        for i, it in enumerate(items):
            if sp.key_of(it) in selkeys: lb.selection_set(i)
            if sp.key_of(it) == shown[0]:                 # the graph in the preview: a darker line
                try: lb.itemconfig(i, background="#F6D5BF", selectbackground="#F6D5BF")
                except Exception: pass
        if top_ is not None:
            try: lb.yview_moveto(top_)
            except Exception: pass
        update_buttons()
        try:
            if "assistant_refresh_context" in locals(): assistant_refresh_context()
        except Exception: pass
    def shown_item(): return next((it for it in items if sp.key_of(it) == shown[0]), None)
    def show(it):
        if canvas is None or (it.spec is None and not isinstance(it, sp.Board)): return
        try:
            s_ = style()
            if isinstance(it, sp.Board): sp.board_figure(it, fig, s_.curve, s_.axis)
            else: sp.preview_figure(it.spec, fig, s_.curve, s_.axis, keep_aspect=True)
            canvas.draw()
            if toolbar is not None: toolbar.update()          # a new graph: forget the old zoom
        except Exception: log("!! I could not draw the preview:\n" + traceback.format_exc())
    def build(it, k=None, opt=None):
        try: it.build(opt or options(), k); return True
        except Exception as e: log(f"!! {it.title}: {e}"); return False
    # ------------------------------------------------------------------ low (or high) peak intensities in an .xrdml file: ask, in big letters
    ask_answer = [None]                     # tests set this to True / False instead of clicking
    def ask_correct(rows, where="added"):
        """rows: [(path, 'low' | 'high', highest count)]. Shows the question in big letters. Returns True (correct them) or False."""
        if ask_answer[0] is not None: return ask_answer[0]
        import xrd_generator as xg
        low = all(r_[1] == "low" for r_ in rows); high = all(r_[1] == "high" for r_ in rows)
        word = "low" if low else "high" if high else "outside the usual range"
        d_ = tk.Toplevel(root); d_.title("Peak intensities")
        try: d_.transient(root); d_.configure(bg=CARD); d_.resizable(False, False)
        except Exception: pass
        f_ = tk.Frame(d_, bg=CARD, padx=px(28), pady=px(22)); f_.pack(fill="both", expand=True)
        big = FF                                           # the app's own font family
        ic = tk.Canvas(f_, width=px(44), height=px(44), bg=CARD, highlightthickness=0); ic.pack(anchor="w", pady=(0, px(6)))       # drawn, so it shows with every font
        ic.create_oval(px(2), px(2), px(42), px(42), fill="#F59E0B", outline=""); ic.create_text(px(22), px(23), text="!", fill="white", font=(big, -px(26), "bold"))
        tk.Label(f_, text=f"The intensities of your peaks are {word}", font=(big, 22, "bold"), fg=INK, bg=CARD, justify="left", wraplength=px(640)).pack(anchor="w")
        lo_, hi_ = xg.USUAL_COUNTS
        for p_, k_, m_ in rows[:8]:
            tk.Label(f_, text=f"{os.path.basename(p_)}:  highest peak {m_:,.0f} counts", font=(big, 13), fg=INK, bg=CARD, justify="left").pack(anchor="w", pady=(px(6), 0))
        if len(rows) > 8: tk.Label(f_, text=f"… and {len(rows) - 8} more file(s)", font=(big, 12), fg=SOFT, bg=CARD).pack(anchor="w")
        tk.Label(f_, text=f"The usual range is {lo_:,.0f}–{hi_:,.0f} counts.", font=(big, 13), fg=SOFT, bg=CARD).pack(anchor="w", pady=(px(4), 0))
        tk.Label(f_, text="Would you like to correct them?", font=(big, 20, "bold"), fg=ACCENT, bg=CARD).pack(anchor="w", pady=(px(16), px(4)))
        tk.Label(f_, text=f"Correcting works like counting longer: your measured counts are kept and the counts of the extra counting time are added as new "
                          f"Poisson counts, so the noise is that of a longer measurement, not your noise multiplied. The highest peak comes out near "
                          f"{xg.CORRECT_TARGET:,.0f} counts. (A scan that is too high is thinned the way a shorter measurement would be.) The corrected scan is "
                          "saved as a new file, <name>_corrected.xrdml, with a note of what was done, and used instead; your original file is not changed.",
                 font=(big, 11), fg=SOFT, bg=CARD, justify="left", wraplength=px(640)).pack(anchor="w")
        res = [False]; again = tk.BooleanVar(value=True)
        bf = tk.Frame(f_, bg=CARD); bf.pack(fill="x", pady=(px(18), 0))
        def answer(v): res[0] = v; d_.destroy()
        yb = ttk.Button(bf, text="Yes, correct them", style="Accent.TButton", command=lambda: answer(True)); yb.pack(side="left")
        ttk.Button(bf, text="No, keep them as they are", command=lambda: answer(False)).pack(side="left", padx=px(10))
        ttk.Checkbutton(f_, text="Ask me every time I add a scan like this", variable=again).pack(anchor="w", pady=(px(12), 0))
        d_.bind("<Return>", lambda e: answer(True)); d_.bind("<Escape>", lambda e: answer(False)); d_.protocol("WM_DELETE_WINDOW", lambda: answer(False))
        try:
            d_.update_idletasks(); x_ = root.winfo_rootx() + (root.winfo_width() - d_.winfo_width()) // 2; y_ = root.winfo_rooty() + (root.winfo_height() - d_.winfo_height()) // 3
            d_.geometry(f"+{max(0, x_)}+{max(0, y_)}"); d_.grab_set(); yb.focus_set()
        except Exception: pass
        root.wait_window(d_)
        if not again.get():
            cfg["ask_xrd_intensity"] = False
            try:
                c_ = json.load(open(cfgfile, encoding="utf-8")) if os.path.isfile(cfgfile) else {}; c_["ask_xrd_intensity"] = False; json.dump(c_, open(cfgfile, "w", encoding="utf-8"), indent=1)
            except Exception: pass
        return res[0]
    def correct_files(rows):
        """Correct the files of rows; returns {original: corrected}. A folder that cannot be written falls back to the results folder."""
        import xrd_generator as xg
        done_ = {}
        for p_, k_, m_ in rows:
            try:
                try: newp, fac, how = xg.correct_intensity(p_)
                except OSError: newp, fac, how = xg.correct_intensity(p_, out_dir=os.path.join(out.get().strip() or default_results_folder(), "Corrected_XRD"))
                done_[p_] = newp; log(f"Corrected peak intensities: {os.path.basename(p_)} (highest {m_:,.0f} counts), counting time \u00d7 {fac:.3g}: {how} \u2192 {newp}  (the original file is unchanged; what was done: {os.path.splitext(os.path.basename(newp))[0]}_provenance.json)")
            except Exception as e: log(f"!! {os.path.basename(p_)} could not be corrected: {e}")
        return done_
    def check_intensities(paths):
        """After files were added: the .xrdml scans whose highest peak is outside the usual range, the question, and the correction."""
        if cfg.get("ask_xrd_intensity", True) is False: return
        import xrd_generator as xg
        rows = []
        for p_ in paths:
            if not str(p_).lower().endswith(".xrdml") or str(p_).lower().endswith("_corrected.xrdml") or "_corrected_" in os.path.basename(str(p_)).lower(): continue
            try:
                k_, m_ = xg.intensity_check(p_)
                if k_ != "ok": rows.append((p_, k_, m_))
            except Exception: pass
        if not rows or not ask_correct(rows): return
        if xg.SCIPY_MISSING and any(r_[1] == "low" for r_ in rows):
            if messagebox.askyesno("Peak intensities", "Correcting low intensities needs the Python package SciPy, which is not installed.\n\nInstall it now? (one-time download of about 40 MB)", parent=root):
                scipy_install(lambda: check_intensities(paths))
            return
        pick_queue[:] = [r_[0] for r_ in rows]; pick_next()            # each scan opens in the generator: make candidates, choose one, go on
    pick_queue = []
    def improve_scan(path=None):
        """Better versions of any .xrdml scan, whatever its counts: the scan under the mouse / the selected one in Your graphs, or a file you choose."""
        if not path:
            sel_ = [items[i] for i in cur()]
            path = next((getattr(it, "path", "") for it in sel_ if str(getattr(it, "path", "")).lower().endswith(".xrdml")), None)
        if not path:
            path = filedialog.askopenfilename(parent=root, title="The XRD scan to improve", filetypes=[("PANalytical XRD scan", "*.xrdml"), ("All files", "*.*")])
        if not path: return "No scan chosen."
        if not str(path).lower().endswith(".xrdml"):
            messagebox.showerror("Improve an XRD scan", "Choose a PANalytical .xrdml scan.", parent=root); return "not an .xrdml scan"
        pick_queue[:] = [path]; pick_next(); return f"Better versions of {os.path.basename(path)}: compare them and choose one."
    act["improve_scan"] = improve_scan
    def pick_next():
        """Open the generator for the next scan that waits for a better version (Yes in the peak-intensity question)."""
        if not pick_queue: return
        p_ = pick_queue.pop(0)
        def chosen(path_):
            singles[:] = [s_ for s_ in singles if getattr(s_, "path", None) != p_]          # the chosen scan takes the place of the original
            regroup(False); refresh(); add_files([path_])
            log(f"Peak intensities: {os.path.basename(p_)} replaced in Your graphs by your choice {os.path.basename(path_)} (the original file is unchanged)")
            status.set(f"{os.path.basename(path_)} chosen and added; the original {os.path.basename(p_)} is unchanged.")
            root.after(300, pick_next)
        w_ = on_xrd_generator(n_scans=3, template=p_, pick_for=p_, on_chosen=chosen)
        if w_ is None: root.after(300, pick_next)
    def add_files(paths):
        paths = list(paths)
        if not paths: return
        opt, md = options(), mode.get()
        def work():
            fresh = []
            for k, p in enumerate(paths):
                root.after(0, lambda p=p, k=k: status.set(f"Reading {os.path.basename(p)} (file {k + 1} of {len(paths)}) …"))
                try:
                    new, lines = sp.load_file(p); log("I looked at " + os.path.basename(p) + ":\n" + "\n".join(lines)); fresh += new
                    if not new and p not in nograph and p not in sp._INFO_ONLY: nograph.append(p)
                    elif new and p in nograph: nograph.remove(p)
                except Exception: log(f"!! I could not read {p}:\n" + traceback.format_exc())
            def prog_(i, m, nm):
                if cancel[0]: raise sp.Cancelled()
                root.after(0, lambda: status.set(f"Analysing graph {i} of {m}: {nm} …"))
            try: n, errs = sp.prepare(singles, fresh, opt, prog_)
            except sp.Cancelled: n, errs = 0, []; log("Cancelled: the graphs analysed so far are in the list.")
            for e in errs: log("!!" + e)
            root.after(0, lambda: status.set("Putting graphs of the same kind together …")); regroup(True, opt, md); return n
        def done(n):
            refresh()
            if n:
                lb.selection_clear(0, "end"); lb.selection_set(0); on_select()
                nc = len(items) - len(singles) - len(boards); status.set(f"I found {n} graph(s)" + (f" and made {nc} combined figure(s), marked with a star" if nc else "") + ". Click any line to preview it.")
            else: status.set("I did not find a table I can draw in that file. The assistant can convert it: view 'Focused Copilot', press + and choose the file.")
            if any(str(p_).lower().endswith(".xrdml") for p_ in paths): root.after(50, lambda: check_intensities(paths))
            if any(isinstance(i_, sp.Item) and i_.det.get("_need") for i_ in singles): root.after(80, lambda: ask_figtype_needs([i_ for i_ in singles if isinstance(i_, sp.Item) and i_.det.get("_need")]))
        background(work, done, "Reading your files …")
    def on_list_click(event=None, span=False):
        """One click on a line ticks or unticks its box and shows that graph. Shift+click ticks everything in between."""
        if not items and not busy[0]: on_add(); return "break"
        if not items or busy[0]: return "break"
        try:
            i = int(lb.nearest(event.y)); bb = lb.bbox(i)
            if bb and event.y > bb[1] + bb[3]: return "break"          # below the last line
        except Exception: return None
        if not 0 <= i < len(items): return "break"
        k = sp.key_of(items[i])
        if span and lastrow[0] is not None:
            for j in range(min(i, lastrow[0]), max(i, lastrow[0]) + 1):
                if j < len(items) and sp.key_of(items[j]) not in selkeys: selkeys.append(sp.key_of(items[j]))
        elif k in selkeys: selkeys.remove(k)
        else: selkeys.append(k)
        with slow.step("a click in the list"):
            lastrow[0] = i; shown[0] = k; refresh(); present(items[i])
        return "break"
    def on_tick_all(on=True):
        selkeys[:] = [sp.key_of(it) for it in items] if on else []; refresh()
        status.set(f"All {len(items)} graphs are ticked." if on and items else "No graph is ticked. Click a line to tick it.")
    def on_add(): add_files(filedialog.askopenfilenames(title="Choose your data files", filetypes=[("Data files", "*.xlsx *.xlsm *.xls *.csv *.txt *.dat *.xy *.xye *.asc *.xrdml *.brml *.uxd *.ras *.spa *.ngb-ds3 *.ngb-ss3"), ("All files", "*.*")]) or [])
    def on_paste():
        """A table copied in Excel (or any table as text) becomes a data file of its own and is added like a file."""
        try: txt = root.clipboard_get()
        except Exception: txt = ""
        rows_ = [l_ for l_ in str(txt).splitlines() if l_.strip()]
        if len(rows_) < 2 or not any(ch_.isdigit() for ch_ in txt): status.set("The clipboard holds no table. Select the cells in Excel, press Ctrl+C, then press this button."); return
        import tempfile, time as _t
        d_ = os.path.join(tempfile.gettempdir(), "OriginPlotApp_pasted"); os.makedirs(d_, exist_ok=True); f_ = os.path.join(d_, "Pasted_table_" + _t.strftime("%Y%m%d_%H%M%S") + ".csv")
        tab_ = any("\t" in l_ for l_ in rows_)                   # cells copied in Excel are separated by tabs; they are written as a proper CSV file so that spaces and commas inside a cell do no harm
        with open(f_, "w", encoding="utf-8-sig", newline="") as h_:
            if tab_: csv.writer(h_).writerows([c_.strip() for c_ in l_.split("\t")] for l_ in rows_)
            else: h_.write("\n".join(rows_) + "\n")
        log(f"Pasted table saved as {f_} ({len(rows_)} rows) and added."); add_files([f_])
    def on_suggest():
        """Small pictures of the graphs that fit the table in the preview; a click draws that one."""
        it = shown_item() or (items[cur()[0]] if cur() else None)
        if not isinstance(it, sp.Item): status.set("Click a single graph (a line without a star) in the list first; suggestions are made for one table at a time."); return
        opt_ = options()
        def work():
            out_ = []
            for s_ in sp.suggest(it, opt_):
                try: out_.append((s_, sp.suggestion_png(it, s_, opt_)))
                except Exception as e: log(f"   suggestion '{s_['title']}' cannot be drawn for this table: {str(e)[:140]}")
            return out_
        def done(out_):
            if not out_: status.set("No suggestion could be drawn for this table."); return
            import base64
            win = tk.Toplevel(root)
            try: win.title("Suggested graphs for " + it.title.strip()[:80]); win.geometry("1250x740"); win.transient(root); win.configure(bg=CARD)
            except Exception: pass
            ttk.Label(win, text="Suggested graphs", style="Step.TLabel").pack(anchor="w", padx=14, pady=(12, 0))
            ttk.Label(win, text="Click the graph you want. The most likely one is first. A type marked (guessed) was worked out from the numbers because the table has no column names: check it. "
                                "You can change everything afterwards on the view 'Own graph'.", style="Soft.TLabel", wraplength=px(1130), justify="left").pack(anchor="w", padx=14, pady=(2, 8))
            grid_ = ttk.Frame(win); grid_.pack(fill="both", expand=True, padx=10); keep_ = []
            def use(s_):
                it.custom = dict(s_["custom"])
                if build(it, s_["kind"]):
                    regroup(); shown[0] = sp.key_of(it); refresh(); show(it); kind.set(it.kind); fill_own(it); status.set(f"Drawn as: {s_['title']}. Change details on the view 'Own graph', or open Suggestions again.")
                try: win.destroy()
                except Exception: pass
            for k_, (s_, png_) in enumerate(out_):
                c_ = ttk.Frame(grid_, padding=6); c_.grid(row=k_ // 4, column=k_ % 4, sticky="n", padx=4, pady=4)
                try: ph_ = tk.PhotoImage(data=base64.b64encode(png_)); keep_.append(ph_); tk.Button(c_, image=ph_, relief="flat", bd=1, cursor="hand2", bg="white", command=lambda s_=s_: use(s_)).pack()
                except Exception: pass
                ttk.Button(c_, text=("★ " if k_ == 0 else "") + s_["title"][:38], command=lambda s_=s_: use(s_)).pack(fill="x", pady=(4, 0))
                ttk.Label(c_, text=s_["why"], style="Soft.TLabel", wraplength=px(265), justify="left").pack(anchor="w")
            win._pictures = keep_                                # the pictures must stay referenced or Tk drops them
            ttk.Button(win, text="Close", command=lambda: win.destroy()).pack(anchor="e", padx=14, pady=10)
        background(work, done, "Looking for graphs that fit this table …")
    act["paste"] = on_paste; act["suggest"] = on_suggest; act["add"] = on_add
    def on_remove():
        gone = [items[i] for i in cur()]
        for g in gone:
            if isinstance(g, sp.Combined): hidden.add(sp.key_of(g))        # a combined figure is hidden; its single graphs stay
        if any(isinstance(g, sp.Combined) for g in gone): status.set("Combined figure hidden. Choosing “Several files of the same kind” again, or Clear list, brings it back.")
        del selkeys[:]
        singles[:] = [s_ for s_ in singles if not any(s_ is g for g in gone)]; boards[:] = [b for b in boards if not any(b is g for g in gone)]
        lb.selection_clear(0, "end"); regroup(False); refresh()
    def on_clear():
        del singles[:]; del items[:]; del boards[:]; del selkeys[:]; hidden.clear(); clean(); sp._INFO_ONLY.clear(); lb.selection_clear(0, "end"); refresh()
    def on_mode(event=None):
        hidden.clear(); del selkeys[:]; lb.selection_clear(0, "end"); regroup(); refresh(); remember()
        if items: lb.selection_set(0); on_select()
    def on_select(event=None):
        sel = cur(); selkeys[:] = [sp.key_of(items[i]) for i in sel]; update_buttons()
        if not sel: refresh(); return
        try: a_ = int(lb.index("active"))                 # preview the line that was clicked, also when several are ticked
        except Exception: a_ = -1
        it = items[a_ if a_ in sel else sel[0]]; shown[0] = sp.key_of(it); refresh(); present(it)
    stale = {"full": None, "live": None}                 # a preview that is out of sight is drawn when its view is opened
    cards_stale = [False]
    def on_view(v): return str(nb.select()) == str(v)
    soon = {"full": None, "live": None, "job": None}
    def draw_soon(which, it):
        """Draw a preview right after the click has been shown. Several quick clicks draw only the last graph."""
        soon[which] = it
        if soon["job"] is None: soon["job"] = root.after(20, draw_now)
    def draw_now():
        soon["job"] = None
        for which in ("full", "live"):
            it = soon[which]; soon[which] = None
            if it is None: continue
            with slow.step(f"drawing the preview of {str(getattr(it, 'title', ''))[:60]}"):
                try: (show if which == "full" else assistant_show)(it)
                except NameError: pass                       # the window is still being built
    def present(it):
        kind.set(it.kind); fill_own(it)
        if on_view(t2) or not on_view(t6): draw_soon("full", it); stale["full"] = None
        else: stale["full"] = sp.key_of(it)
        if on_view(t6): draw_soon("live", it); stale["live"] = None
        else: stale["live"] = sp.key_of(it)
        single = isinstance(it, sp.Item)                  # type and sample name only exist for single graphs
        for w_, st_on in ((kbox, "readonly"), (sent, "normal"), (sapply, "normal")):
            try: w_.config(state=st_on if single else "disabled")
            except Exception: pass
        sample.set(sp.display_names([it])[0] if isinstance(it, sp.Item) else "")
        if isinstance(it, sp.Board): log(it.title + "\n   draft caption: " + sp.caption(it)); return
        if isinstance(it, sp.Combined): log(it.title + "\n   why: " + it.why)
        if it.results is not None: log(it.title + "\n" + it.results.to_string(index=False))
        for w in it.warnings: log("   note: " + w)
    def fill_own(it):
        """The view 'Own graph' shows the columns of the graph in the preview."""
        single = isinstance(it, sp.Item); cols = [str(c) for c in it.det["nums"]] if single else []; cu = (getattr(it, "custom", None) or {}) if single else {}
        owng.set((it.title if single else "Click a single graph (a line without a star) on the view 'Scientific Workbench' first.")[:110])
        try: oxb["values"] = cols
        except Exception: pass
        d_ = it.det if single else {}; x0_ = str(cu.get("x") or d_.get("x") or d_.get("x_temp") or (cols[0] if cols else ""))
        ox.set(x0_); oxt.set(cu.get("xtitle", "")); oyt.set(cu.get("ytitle", "")); olog.set(bool(cu.get("xlog"))); orev.set(bool(cu.get("xrev"))); osty.set(cu.get("style") or sp.OWN_STYLES[0]); olay.set(cu.get("layout") or sp.OWN_LAYOUTS[0])
        ys_ = [str(c) for c in (cu.get("ys") or d_.get("ys") or [])]; owncols[:] = cols
        try:
            oyl.delete(0, "end")
            for c in cols: oyl.insert("end", c)
            for i_, c in enumerate(cols):
                if c in ys_: oyl.selection_set(i_)
        except Exception: pass
    def on_own(clear=False):
        it = shown_item()
        if not isinstance(it, sp.Item): status.set("Click a single graph (a line without a star) on the view 'Scientific Workbench' first."); return
        if clear: it.custom = {}; ok = build(it, it.det["kind"])
        else:
            try: ys_ = [owncols[i_] for i_ in oyl.curselection() if i_ < len(owncols)]
            except Exception: ys_ = []
            ys_ = [c for c in ys_ if c != ox.get()]
            it.custom = {"x": ox.get(), "ys": ys_, "xtitle": oxt.get().strip(), "ytitle": oyt.get().strip(), "xlog": bool(olog.get()), "xrev": bool(orev.get()), "style": osty.get(), "layout": olay.get()}
            ok = build(it, "XY")
        if ok:
            regroup(); shown[0] = sp.key_of(it); refresh(); show(it); kind.set(it.kind)
            status.set("Back to the automatic graph." if clear else "Your own graph is in the preview on the view 'Scientific Workbench'.")
    def on_kind(event=None):
        sel = cur(); it = shown_item() or (items[sel[0]] if sel else None)      # the graph in the preview
        if it is None: return
        if not isinstance(it, sp.Item): log("To change the type, click the single graph (without a star) and change it there."); kind.set(it.kind); return
        if build(it, kind.get()):
            regroup(); shown[0] = sp.key_of(it); refresh(); show(it)
    def on_rebuild(then=None):
        if not singles: remember(); clean(); return
        opt, md = options(), mode.get()
        def work():
            for k, it in enumerate(list(singles)):
                if cancel[0]: raise sp.Cancelled()
                root.after(0, lambda k=k, it=it: status.set(f"Analysing graph {k + 1} of {len(singles)}: {it.name} …")); build(it, it.kind, opt)
            regroup(False, opt, md); return True
        def done(ok):
            refresh(); remember()
            if ok: clean(); status.set("All graphs are up to date.")
            if ok and then: then()
            elif ok: on_select()
        background(work, done, "Applying your settings to all graphs …")
    def on_sample():
        chosen = [items[i] for i in cur() if isinstance(items[i], sp.Item)] or [it for it in [shown_item()] if isinstance(it, sp.Item)]
        if not chosen: status.set("Tick one or more single graphs (without a star) first, then type the sample name."); return
        for it in chosen: it.sample = sample.get().strip()
        lb.selection_clear(0, "end"); regroup(); refresh(); lb.selection_set(items.index(chosen[0])); on_select()
        status.set(f"{len(chosen)} graph(s) now belong to the sample '{sample.get().strip()}'.")
    def on_board():
        chosen = [items[i] for i in cur() if not isinstance(items[i], sp.Board)][:9]
        if not chosen: status.set("Tick the graphs for the figure first (click their lines)."); return
        try: w_ = min(400.0, max(40.0, float(fw.get().replace(",", "."))))
        except Exception: w_ = 175.0
        b = sp.Board([sp.key_of(c) for c in chosen], int(fcols.get()) if fcols.get().isdigit() else 0, w_, max([b.number for b in boards] + [0]) + 1)
        boards.append(b); regroup(False); refresh(); lb.selection_clear(0, "end"); lb.selection_set(items.index(b)); on_select(); remember()
        status.set(f"{b.name} is at the top of the list. Draw it to save it at exactly {w_:g} mm wide.")
    def look_now(*a):
        o_ = ori.get(); c_ = fcol.get().split(" (")[0]; i_ = insv.get().strip() or sp.INSETS[0]
        try: looktxt.set(f"Will be drawn: {o_.lower()} pages · fit graphs {c_.lower()} · peak labels navy · inset: {i_.lower()}")
        except Exception: pass
    def on_look(event=None):
        look_now(); remember(); on_rebuild()
    def on_workbook(template=False):
        v = filedialog.asksaveasfilename(title="Workbook template" if template else "Save the loaded fit graphs as one workbook", defaultextension=".xlsx",
                                         initialfile="XRD_workbook_template.xlsx" if template else project_name() + "_XRD_workbook.xlsx", filetypes=[("Excel workbook", "*.xlsx")])
        if not v: return
        try:
            lines = sp.write_workbook([] if template else singles, v, template=template); log("\n".join(lines)); status.set(lines[0])
        except Exception: log("!! I could not write the workbook:\n" + traceback.format_exc())
    act["own"] = on_own; act["own_clear"] = lambda: on_own(True)
    act["workbook"] = on_workbook; act["template"] = lambda: on_workbook(True)
    def on_save_session():
        v = filedialog.asksaveasfilename(title="Save this session", defaultextension=".json", initialfile=project_name() + "_session.json", filetypes=[("Session", "*.json")])
        if not v: return
        try:
            d_ = sp.session_dump(singles, boards, settings_now()); d_["raw_settings"] = {k: v_.get() for k, v_ in analysis.items()}; d_["raw_settings"].update(mode=mode.get(), maxlab=maxlab.get(), labxy=labxy.get())
            json.dump(d_, open(v, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str); status.set("Session saved: " + v)
        except Exception: log("!! I could not save the session:\n" + traceback.format_exc())
    def on_open_session(v=None):
        v = v or filedialog.askopenfilename(title="Open a saved session, or session.json in the results folder of an earlier run", filetypes=[("Session", "*.json"), ("All files", "*.*")])
        if not v: return
        # A session is a small text file written by this app. Anything else (an Excel workbook, an Origin project, a data file)
        # is said in plain words, without an error report; a data file is simply added to the list.
        d_ = None
        try:
            with open(v, "rb") as f_: blob = f_.read()
            if not blob.startswith((b"PK", b"\xd0\xcf\x11\xe0", b"CPYA")):
                for enc_ in ("utf-8-sig", "utf-16", "cp1252"):                    # also a session that another program saved again in its own encoding
                    try: d_ = json.loads(blob.decode(enc_)); break
                    except Exception: d_ = None
        except Exception as e_: status.set(f"I could not read that file ({e_})."); return
        if not isinstance(d_, dict) or not ("graphs" in d_ or "files" in d_ or "raw_settings" in d_):
            nm_ = os.path.basename(v)
            if os.path.splitext(v)[1].lower() in (".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".dat", ".xy", ".xye", ".asc", ".xrdml", ".brml", ".uxd", ".ras", ".spa", ".ngb-ds3", ".ngb-ss3"):
                status.set(f"{nm_} is a data file, not a saved session, so I am adding it to the list."); log(f"{nm_} is a data file, not a saved session: added with 'Add files'."); add_files([v]); return
            status.set(f"{nm_} is not a session saved by this app. Choose a file ending in _session.json, or session.json in a results folder."); log(f"Not a session file: {v}"); return
        try:
            raw = d_.get("raw_settings", {})
            for k, var in list(analysis.items()) + [("mode", mode), ("maxlab", maxlab), ("labxy", labxy)]:
                if k in raw: var.set(raw[k])
            opt, md = options(), mode.get()
            def work():
                new_s, new_b, lines = sp.session_load(d_, opt, os.path.dirname(v)); singles[:] = new_s; boards[:] = new_b
                regroup(True, opt, md); log("Session opened: " + v + ("\n" + "\n".join(lines) if lines else ""))
            def done(_):
                lb.selection_clear(0, "end"); refresh()
                if items: lb.selection_set(0); on_select()
                status.set(f"Session opened: {len(singles)} graph(s) are back.")
            background(work, done, "Opening the session and reading its files …")
        except Exception: log("!! I could not open that session:\n" + traceback.format_exc())
    act.update(sample=on_sample, board=on_board, save=on_save_session, open=on_open_session)
    act["draw_sel"] = lambda: draw("selected"); act["draw_all"] = lambda: draw("all")
    def pub_w():
        try: return min(400.0, max(50.0, float(str(pubw.get()).replace(",", "."))))
        except Exception: return None                     # "Automatic"
    def draw(which):
        if not items: status.set("Add a file first."); return
        if which == "selected" and not cur(): status.set("No graph is ticked. Click the lines of the graphs you want (a tick appears), or press Draw all."); return
        if dirty[0]:                                      # settings changed: apply them first, so graphs and record agree
            keys = [sp.key_of(items[i]) for i in cur()]
            def again():
                lb.selection_clear(0, "end")
                for i, it in enumerate(items):
                    if sp.key_of(it) in keys: lb.selection_set(i)
                selkeys[:] = keys; update_buttons(); draw(which)
            on_rebuild(again); return
        chosen = [items[i] for i in cur()] if which == "selected" else list(items)
        folder = run_folder(); autosave()
        set_, ses_ = settings_now(), sp.session_dump(singles, boards, settings_now()); ses_["raw_settings"] = {k: v_.get() for k, v_ in analysis.items()}; ses_["raw_settings"].update(mode=mode.get(), maxlab=maxlab.get(), labxy=labxy.get())
        start(lambda: run_items(chosen, folder, log, style(), png=png.get(), pdf=pdf.get(), keep_open=keep.get(), project=project_name(), settings=set_, session=ses_, stop=lambda: cancel[0], pub=pubv.get(), pub_width=pub_w(), journal=jour.get(),
                                  progress=lambda i, m, nm: root.after(0, lambda: status.set(f"Drawing graph {i} of {m} in Origin: {nm}"))), f"Drawing {len(chosen)} graph(s).", folder)
    def on_paper():
        if not singles: status.set("Add your data first."); return
        if dirty[0]: on_rebuild(on_paper); return        # settings changed: apply them first
        folder = os.path.join(run_folder(), "Paper_set"); opt_ = options(); set_ = settings_now(); set_["paper set, sample pages in the main text"] = pmain.get(); set_["journal template"] = jour.get()
        start(lambda: run_paper(list(singles), opt_, pmain.get(), folder, log, style=style(), png=png.get(), pdf=pdf.get(), keep_open=keep.get(), project=project_name(), settings=set_, stop=lambda: cancel[0], pub=True, pub_width=pub_w(), journal=jour.get(),
                                progress=lambda i, m, nm: root.after(0, lambda: status.set(f"Paper set: drawing graph {i} of {m} in Origin: {nm}"))), "Making the paper set.", folder)
    act["paper"] = on_paper
    def on_paper_preview():
        if not singles: status.set("Add your data first."); return
        if dirty[0]: on_rebuild(on_paper_preview); return
        path = os.path.join(run_folder(), "Paper_set", "Paper_set_preview.pdf"); opt_ = options(); s_ = style(); remember()
        def work(): return sp.paper_preview(list(singles), opt_, pmain.get(), jour.get(), path, s_.curve, s_.axis)
        def done(plan):
            if not plan: return
            log("Paper set preview (nothing was drawn in Origin):\n" + "\n".join(plan) + "\nPreview file: " + path); status.set("Preview written: " + path); show_details(True)
            try: os.startfile(path)
            except Exception: pass
        background(work, done, "Making the preview of the paper set …")
    act["paper_preview"] = on_paper_preview
    lb.bind("<Button-1>", on_list_click); lb.bind("<Control-Button-1>", on_list_click); lb.bind("<Shift-Button-1>", lambda e: on_list_click(e, True))
    for ev_ in ("<B1-Motion>", "<Double-Button-1>", "<Triple-Button-1>", "<Shift-B1-Motion>", "<Control-B1-Motion>"): lb.bind(ev_, lambda e: "break")      # dragging must not change the ticks
    refresh()
    lbmenu = tk.Menu(root, tearoff=0, font=font)
    lbmenu.add_command(label="Improve this XRD scan (choose a better version)\u2026", command=lambda: improve_scan(lbmenu.path_))
    def on_list_right(e):
        i = lb.nearest(e.y)
        if 0 <= i < len(items) and str(getattr(items[i], "path", "")).lower().endswith(".xrdml"):
            lbmenu.path_ = items[i].path; lbmenu.tk_popup(e.x_root, e.y_root)
    lb.bind("<Button-3>", on_list_right)
    lb.bind("<<ListboxSelect>>", on_select); kbox.bind("<<ComboboxSelected>>", on_kind); mbox.bind("<<ComboboxSelected>>", on_mode)
    for w_ in (obox, pbox, cbox): w_.bind("<<ComboboxSelected>>", on_look)
    look_now()
    buttons.append(ttk.Button(bar, text="Add files…", command=on_add)); buttons[-1].pack(side="left"); addbtn.append(buttons[-1])
    ttk.Button(bar, text="Remove ticked", command=on_remove).pack(side="left", padx=SP2); ttk.Button(bar, text="Clear list", command=on_clear).pack(side="left")
    mm = tk.Menu(root, tearoff=0, font=font)              # the things you need now and then: out of the way, one click away
    more = ttk.Button(bar, text="More  \u25BE", command=lambda: mm.tk_popup(more.winfo_rootx(), more.winfo_rooty() + more.winfo_height() + 2)); more.pack(side="right")
    mm.add_command(label="XRD Scan Generator (app)\u2026", command=lambda: act["xrd_app"]()); mm.add_command(label="Refresh previews", command=on_rebuild); mm.add_separator()
    mm.add_command(label="Save as one workbook…", command=lambda: act["workbook"]()); mm.add_command(label="Workbook template…", command=lambda: act["template"]()); mm.add_separator()
    mm.add_command(label="Open session…", command=lambda: act["open"]()); mm.add_command(label="Open the Assistant (Focused Copilot)", command=lambda: nb.select(t6))
    ttk.Label(tickbar, text="\u2611 = will be drawn. Click a line to tick it and see it.", style="Soft.TLabel").pack(side="left")
    ttk.Button(tickbar, text="Untick all", style="Small.TButton", command=lambda: on_tick_all(False)).pack(side="right"); ttk.Button(tickbar, text="Tick all", style="Small.TButton", command=lambda: on_tick_all(True)).pack(side="right", padx=SP1)
    buttons.append(ttk.Button(b2, text="Draw ticked in Origin", style="Accent.TButton", command=lambda: draw("selected"))); buttons[-1].pack(side="left"); botbtn.append(buttons[-1])
    buttons.append(ttk.Button(b2, text="Draw all", command=lambda: draw("all"))); buttons[-1].pack(side="left", padx=SP2); botbtn.append(buttons[-1])
    HOOKS.update(add_files=add_files, notebook=nb, open_session=on_open_session, status=status)

    # ---------------- tab: analysis settings
    kicker(t4, "Analysis settings").pack(anchor="w"); ttk.Label(t4, text="How your data are read and analysed", style="Step.TLabel").pack(anchor="w", pady=(px(2), 0))
    ttk.Label(t4, text="I show my choices here so you can correct them. Every choice is also written into processing_record.txt next to your figures.", style="Soft.TLabel").pack(anchor="w", pady=(2, SP3))
    a_foot = ttk.Frame(t4, padding=(0, SP3, 0, 0)); a_foot.pack(side="bottom", fill="x")                 # the button that applies the settings stays in view
    rule(t4).pack(side="bottom", fill="x")
    a_scroll, t4b = scrolling(t4); a_scroll.pack(fill="both", expand=True); t4b.configure(padding=(0, 0, SP3, SP3))
    LABEL_COL, FIELD_COL = px(230), px(400)            # the same two columns in every box, so labels, fields and hints line up down the whole page
    def setting_row(parent, label, widget, hint):
        r = ttk.Frame(parent); r.pack(fill="x", pady=SP1); r.columnconfigure(0, minsize=LABEL_COL); r.columnconfigure(1, minsize=FIELD_COL); r.columnconfigure(2, weight=1)
        ttk.Label(r, text=label).grid(row=0, column=0, sticky="nw", pady=(5, 0)); w_ = widget(r)
        try: wide = int(w_.cget("width")) >= 24
        except Exception: wide = False
        w_.grid(row=0, column=1, sticky="new" if wide else "nw")                  # long fields share both edges; short ones (a number, a short choice) keep their size
        autowrap(ttk.Label(r, text=hint, style="Soft.TLabel"), r, used=LABEL_COL + FIELD_COL + SP4, most=640).grid(row=0, column=2, sticky="nw", padx=(SP4, 0), pady=(5, 0)); r.field = w_; return r
    owng = tk.StringVar(value="Click a single graph on the view 'Scientific Workbench' first."); ox = tk.StringVar(value=""); oxt = tk.StringVar(value=""); oyt = tk.StringVar(value="")
    olog = tk.BooleanVar(value=False); orev = tk.BooleanVar(value=False); osty = tk.StringVar(value=sp.OWN_STYLES[0]); olay = tk.StringVar(value=sp.OWN_LAYOUTS[0]); owncols = []
    kicker(t5, "Own graph").pack(anchor="w"); ttk.Label(t5, text="Draw any table of numbers your way", style="Step.TLabel").pack(anchor="w", pady=(px(2), 0))
    autowrap(ttk.Label(t5, text="Any table of numbers can be drawn, also data I do not recognise. Click its line on the view 'Scientific Workbench', then say here what goes on the axes. "
                                "Page orientation, pointers, the zoomed inset and the line weights apply to it like to every other graph.", style="Soft.TLabel"), t5, most=760).pack(anchor="w", pady=(2, SP3))
    w0 = ttk.Frame(t5); w0.pack(fill="x", pady=(0, SP4))
    ttk.Button(w0, text="Add a file…", command=lambda: act["add"]()).pack(side="left")
    ttk.Button(w0, text="Paste a table (copied in Excel)", command=lambda: act["paste"]()).pack(side="left", padx=SP2)
    ttk.Button(w0, text="Show suggestions…", command=lambda: act["suggest"]()).pack(side="left")
    kicker(t5, "Columns and axes").pack(anchor="w", pady=(0, SP2)); wcard = ttk.Frame(t5); wcard.pack(anchor="w")
    ttk.Label(wcard, textvariable=owng, style="Note.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, SP3))
    wcard.columnconfigure(0, minsize=px(150)); wcard.columnconfigure(1, minsize=px(380))
    def own_row(r, label, widget, hint=None, top=False):
        ttk.Label(wcard, text=label).grid(row=r, column=0, sticky="nw" if top else "w", pady=SP1); widget.grid(row=r, column=1, sticky="we", pady=SP1)
        if hint: ttk.Label(wcard, text=hint, style="Soft.TLabel", wraplength=px(340), justify="left").grid(row=r, column=2, sticky="nw" if top else "w", padx=(SP4, 0), pady=SP1)
    oxb = ttk.Combobox(wcard, textvariable=ox, values=[], state="readonly"); own_row(1, "X column", oxb)
    oyf, oyl = listbox(wcard, selectmode="extended", height=8)
    own_row(2, "Y columns", oyf, "Click one; Ctrl+click or Shift+click for several (each becomes a curve). Nothing chosen = all other columns.", top=True)
    own_row(3, "X axis title", ttk.Entry(wcard, textvariable=oxt), "Empty = the column name.")
    own_row(4, "Y axis title", ttk.Entry(wcard, textvariable=oyt))
    w5 = ttk.Frame(wcard); ttk.Checkbutton(w5, text="Logarithmic", variable=olog).pack(side="left"); ttk.Checkbutton(w5, text="Reversed (high values left)", variable=orev).pack(side="left", padx=SP4)
    own_row(5, "X axis", w5)
    own_row(6, "Curves drawn as", ttk.Combobox(wcard, textvariable=osty, values=sp.OWN_STYLES, state="readonly"), "Bars, histogram, box plot and contour map are also here.")
    own_row(7, "Several signals", ttk.Combobox(wcard, textvariable=olay, values=sp.OWN_LAYOUTS, state="readonly"), "One graph, or one panel per signal with its own y scale.")
    w7 = ttk.Frame(wcard); w7.grid(row=8, column=1, columnspan=2, sticky="w", pady=(SP4, 0))
    ttk.Button(w7, text="Draw it this way", style="Accent.TButton", command=lambda: act["own"]()).pack(side="left"); ttk.Button(w7, text="Back to automatic", command=lambda: act["own_clear"]()).pack(side="left", padx=SP2)
    a0 = ttk.LabelFrame(t4b, text="All graphs", padding=SP3); a0.pack(fill="x", pady=(0, SP4))
    a1 = ttk.LabelFrame(t4b, text="XRD", padding=SP3); a1.pack(fill="x", pady=(0, SP4))
    setting_row(a1, "X-ray tube (wavelength)", lambda r: ttk.Combobox(r, textvariable=tube, values=list(sp.TUBES), width=34), "Automatic reads it from .xrdml/.brml/.ras/.uxd files; or type a wavelength in Å")
    setting_row(a0, "Page orientation", lambda r: ttk.Combobox(r, textvariable=ori, values=sp.ORIENTATIONS, width=14, state="readonly"), "Landscape: wide pages (default). Portrait: tall pages. For every graph")
    setting_row(a0, "Samples per figure", lambda r: ttk.Combobox(r, textvariable=pf, values=sp.PER_FIG, width=28, state="readonly"), "for figures with one panel per sample. Fewer = taller panels. Curves overlaid on common axes always stay together")
    setting_row(a1, "Sample page layout", lambda r: ttk.Combobox(r, textvariable=play, values=sp.PAGE_LAYOUTS, width=20, state="readonly"), "pattern (a) and fit (b) of one sample on one page. Decide for me: side by side on a landscape page, one above the other on a portrait page")
    setting_row(a1, "Stacked fit figures", lambda r: ttk.Combobox(r, textvariable=stk, values=sp.STACK_STYLES, width=46, state="readonly"), "Clean: black / red / blue, main peaks only. Detailed: tick rows and wt% beside each panel")
    setting_row(a1, "Fit graphs look like", lambda r: ttk.Combobox(r, textvariable=fst, values=sp.FIT_STYLES, width=46, state="readonly"), "HighScore: observed red, calculated blue, phase legend with wt%")
    setting_row(a1, "Peak labels", lambda r: ttk.Combobox(r, textvariable=xlab, values=sp.XRD_LABELS, width=34, state="readonly"), "Only from my files: a label sheet or the peak list of the same sample; nothing is guessed. Suggest: the app's own phase search with the phase library, to be checked against your identification. From my files needs a label sheet or a peak list of the same sample")
    setting_row(a1, "Label text", lambda r: ttk.Combobox(r, textvariable=ltxt, values=sp.LABEL_TEXT, width=46, state="readonly"), "names are written upright on single graphs; stacked figures keep the letters")
    setting_row(a0, "Peak label size", lambda r: ttk.Combobox(r, textvariable=lsz, values=sp.LABEL_SIZES, width=14, state="readonly"), "Large = 25 % bigger, Extra large = 50 % bigger. Bigger letters need more room, so a crowded graph keeps fewer labels")
    setting_row(a0, "Label pointers", lambda r: ttk.Combobox(r, textvariable=ptr, values=sp.POINTERS, width=14, state="readonly"), "what joins a label to its peak when the label had to move")
    setting_row(a0, "Zoomed inset (x range)", lambda r: ttk.Combobox(r, textvariable=insv, values=sp.INSETS + ["27-37"], width=26), "Automatic: on XRD sample pages. Or type a range in the units of the x axis (27-37, 800-1200, 400-500): every single graph whose data hold that range gets it")
    setting_row(a1, "Colours of fit graphs", lambda r: ttk.Combobox(r, textvariable=fcol, values=sp.FIT_COLOURS, width=46, state="readonly"), "observed / calculated / difference")
    setting_row(a1, "Phases to look for", lambda r: ttk.Combobox(r, textvariable=xph, values=sp.XRD_PHASES, width=46), "pick a set or type codes after a colon, e.g.  Mine: A B C F CH AFt")
    setting_row(a1, "Background", lambda r: ttk.Combobox(r, textvariable=xbg, values=sp.XRD_BG, width=34, state="readonly"), "it is always removed before peaks are found")
    xr2 = ttk.Frame(a1); xr2.pack(fill="x", pady=(SP2, 0)); xr2.columnconfigure(0, minsize=LABEL_COL)
    ttk.Label(xr2, text="Phase library").grid(row=0, column=0, sticky="nw", pady=(5, 0))
    xr = ttk.Frame(xr2); xr.grid(row=0, column=1, sticky="w")
    ttk.Button(xr, text="Phase library…", command=lambda: act["library"]()).pack(side="left")
    ttk.Checkbutton(xr, text="Store new phases from my files for future suggestions", variable=xstore).pack(side="left", padx=SP4)
    autowrap(ttk.Label(xr2, text="19 phases from your own HighScore refinements, plus every phase the app stores from your files (peak lists, Bragg tables, your peak labels) "
                       "and the phases you add yourself. Stored phases are used when you choose 'Suggest phases from the library'. They are kept outside the app folder, so they stay when you install a new version.",
              style="Soft.TLabel"), xr2, used=LABEL_COL, most=760).grid(row=1, column=1, sticky="w", pady=(SP1, 0))
    a2 = ttk.LabelFrame(t4b, text="TGA", padding=SP3); a2.pack(fill="x", pady=(0, SP4))
    setting_row(a2, "Mass column is", lambda r: ttk.Combobox(r, textvariable=tgam, values=sp.TGA_MASS, width=46, state="readonly"), "Automatic = the unit written in the file decides (mg, g, %); the values are only looked at when the file gives no unit")
    setting_row(a2, "Curves", lambda r: ttk.Combobox(r, textvariable=tgac, values=sp.TGA_CURVES, width=46, state="readonly"), "TG on the left axis and DTG on the right axis in one graph, or only one of them. The steps and DTG peaks are in the results table either way")
    setting_row(a2, "Material", lambda r: ttk.Combobox(r, textvariable=tgamat, values=sp.TGA_MATERIAL, width=46, state="readonly"), "chemistry is only proposed for a material you declare; a temperature alone does not identify a phase")
    setting_row(a2, "Initial sample mass", lambda r: ttk.Entry(r, textvariable=tgam0, width=12), "only for a column of mass LOSS in mg or g: the mass at the start, in the same unit")
    r_ = setting_row(a2, "Mass-loss ranges (°C)", lambda r: ttk.Entry(r, textvariable=tgar, width=48), "empty = found from the DTG peaks")
    ttk.Button(r_, text="Cement example", style="Small.TButton", command=lambda: tgar.set(sp.CEMENT_TGA)).grid(row=1, column=1, sticky="w", pady=(SP1, 0))
    r2_ = ttk.Frame(a2); r2_.pack(fill="x"); r2_.columnconfigure(0, minsize=LABEL_COL)
    autowrap(ttk.Label(r2_, text="Write ranges like  40-105, 105-400, 400-500 CH, 600-800 CC .  CH after a range gives Ca(OH)2, CC gives CaCO3 (step method, per start mass; check the limits on your DTG curve).", style="Soft.TLabel"), r2_, used=LABEL_COL, most=760).grid(row=0, column=1, sticky="w")
    a3 = ttk.LabelFrame(t4b, text="FTIR", padding=SP3); a3.pack(fill="x", pady=(0, SP4))
    setting_row(a3, "Signal is", lambda r: ttk.Combobox(r, textvariable=ftirs, values=sp.FTIR_SIGNAL, width=24, state="readonly"), "decides whether bands are labelled at maxima or minima")
    a4 = ttk.LabelFrame(t4b, text="Calorimetry", padding=SP3); a4.pack(fill="x", pady=(0, SP4))
    setting_row(a4, "Report cumulative heat at (h)", lambda r: ttk.Entry(r, textvariable=caloa, width=27), "for example  24, 48, 72, 168")
    setting_row(a4, "Exclusion window (min)", lambda r: ttk.Entry(r, textvariable=caloe, width=8), "as in the calorimetry skill: the heat flow is left out for this long after the Reaction start marker (or the first point): not drawn, not integrated. Default 45")
    setting_row(a4, "Regimes and alite fractions", lambda r: ttk.Entry(r, textvariable=caloi, width=48), "optional, e.g.  Reference: I, 0.62; Sample A: II, 0.55  (sample name as in Your graphs: regime, alite fraction). Drawn only as you type it: regime labels at the peaks, brackets, and the bar chart per unit alite")
    a5 = ttk.LabelFrame(t4b, text="Replicates", padding=SP3); a5.pack(fill="x", pady=(0, SP4))
    setting_row(a5, "Overlaid replicate curves", lambda r: ttk.Combobox(r, textvariable=repl, values=sp.REPLICATES, width=24, state="readonly"), "replicates = graphs with the same sample name (endings like _rep1, _run2 are recognised)")
    ttk.Button(a_foot, text="Apply to all my graphs", style="Accent.TButton", command=on_rebuild).pack(side="left")
    ttk.Label(a_foot, text="Reads the settings again and refreshes every preview.", style="Soft.TLabel").pack(side="left", padx=SP3)

    # ---------------- tab: look and saving
    kicker(t3, "Look and saving").pack(anchor="w"); ttk.Label(t3, text="Where results go, file formats and line weights", style="Step.TLabel").pack(anchor="w", pady=(px(2), SP3))
    t3s, t3in = scrolling(t3); t3s.pack(fill="both", expand=True)
    t3b = ttk.Frame(t3in); t3b.pack(anchor="nw")                       # a readable column, not stretched across a wide screen
    sv_ = ttk.LabelFrame(t3b, text="Where results are saved", padding=SP4); sv_.pack(fill="x")
    r0 = ttk.Frame(sv_); r0.pack(fill="x")
    ttk.Entry(r0, textvariable=out, width=70).pack(side="left", fill="x", expand=True); ttk.Button(r0, text="Choose folder…", command=choose_folder).pack(side="left", padx=SP2)
    ttk.Button(r0, text="Open", command=lambda: open_folder()).pack(side="left")
    ttk.Checkbutton(sv_, text="Put each run in its own dated subfolder (for example 2026-11-16_0915), so nothing is overwritten", variable=dated).pack(anchor="w", pady=(SP3, 0))
    ttk.Checkbutton(sv_, text="Leave Origin open when finished, so I can keep editing", variable=keep).pack(anchor="w", pady=(SP2, 0))
    fm_ = ttk.LabelFrame(t3b, text="File formats", padding=SP4); fm_.pack(fill="x", pady=(SP4, 0))
    r1 = ttk.Frame(fm_); r1.pack(fill="x")
    ttk.Label(r1, text="Save as").pack(side="left"); ttk.Checkbutton(r1, text="PNG picture", variable=png).pack(side="left", padx=(SP3, SP2)); ttk.Checkbutton(r1, text="PDF (vector)", variable=pdf).pack(side="left", padx=SP2)
    ttk.Label(fm_, text="The Origin project (.opj) and the analysis tables (.csv) are always saved.", style="Soft.TLabel").pack(anchor="w", pady=(2, 0))
    rp_ = ttk.Frame(fm_); rp_.pack(anchor="w", pady=(SP3, 0))
    ttk.Checkbutton(rp_, text="Also make publication files myself (PNG and TIFF 600 dpi, PDF, SVG; Arial; exact width)", variable=pubv).pack(side="left")
    ttk.Label(rp_, text="Width (mm)").pack(side="left", padx=(SP4, SP2)); ttk.Entry(rp_, textvariable=pubw, width=10).pack(side="left")
    ttk.Label(fm_, text="Automatic width: 140 mm for one graph, 175 mm for stacked or combined figures. Letters are 8-9 pt at that size; type 85 or 90 for a single column.", style="Soft.TLabel", wraplength=px(820), justify="left").pack(anchor="w", pady=(2, 0))
    lk = ttk.LabelFrame(t3b, text="Line weights (points) and the zoomed inset", padding=SP4); lk.pack(fill="x", pady=(SP4, SP3))
    lk.columnconfigure(0, minsize=LABEL_COL)
    for k_, (lab_, var, hint) in enumerate((("Curves", cw, "Data and fitted lines."), ("Axes and frame", aw, "The box around each graph."), ("Tick rows and leader lines", tw, "Bragg ticks, lines from peak to label."),
                            ("Zoomed inset: curves", zw, "In Origin. Origin draws a small inset finer, so 3.8 here looks like the main curves."),
                            ("Zoomed inset: axes and frame", za, "In Origin: the box around the zoom, as heavy as its curves."),
                            ("Zoomed inset: label size", zl, "In Origin: font size of the peak labels inside the zoom (24 or 25); the numbers on its axis are bold and a little smaller."))):
        ttk.Label(lk, text=lab_).grid(row=k_, column=0, sticky="w", pady=SP1); ttk.Entry(lk, textvariable=var, width=7).grid(row=k_, column=1, sticky="w", pady=SP1)
        ttk.Label(lk, text=hint, style="Soft.TLabel", wraplength=px(560), justify="left").grid(row=k_, column=2, sticky="w", padx=(SP4, 0), pady=SP1)
    ttk.Label(t3b, text="Your choices on this page are remembered for next time.", style="Soft.TLabel").pack(anchor="w")

    lastses = os.path.join(here, "last_session.json")
    def autosave():
        """What is in the list right now, so 'Resume last session' can bring it back."""
        if not singles: return
        try:
            d_ = sp.session_dump(singles, boards, settings_now()); d_["raw_settings"] = {k: v_.get() for k, v_ in analysis.items()}; d_["raw_settings"].update(mode=mode.get(), maxlab=maxlab.get(), labxy=labxy.get())
            json.dump(d_, open(lastses, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
        except Exception: pass
    def ask(title, text):
        try:
            from tkinter import messagebox
            return bool(messagebox.askyesno(title, text))
        except Exception: return True
    def on_new():
        if busy[0]: status.set("One moment please, I am still working. Press Stop first."); return
        if singles and not ask("New project", "Start a new, empty project?\nThe list of graphs is cleared. Your data files and the results already saved are not touched.\n(File > Resume last session brings this list back.)"): return
        autosave(); on_clear(); shown[0] = None
        try:
            fig.clear(); fig.text(0.5, 0.5, "Your graph will appear here\nas soon as you add a file.", ha="center", va="center", color=SOFT, fontsize=12); canvas.draw()
        except Exception: pass
        status.set("New project. Add your data files.")
    def on_resume():
        if not os.path.exists(lastses): status.set("There is no earlier session to resume yet. It is saved when you draw, start a new project or close the app."); return
        on_open_session(lastses)
    def on_stop():
        if busy[0]: cancel[0] = True; status.set("Stopping after the current graph …")
        else: status.set("Nothing is running.")
    def on_library():
        """The phases the app knows: built in, stored from your files, added by you."""
        win = tk.Toplevel(root)
        try: win.title("Phase library"); win.geometry("1040x600"); win.transient(root)
        except Exception: pass
        try: win.configure(bg=CARD)
        except Exception: pass
        ttk.Label(win, text="Phase library", style="Step.TLabel").pack(anchor="w", padx=14, pady=(12, 0))
        ttk.Label(win, text="These phases are used only when you choose 'Suggest phases from the library' (Analysis settings > XRD > Peak labels). The drawing itself never needs them. "
                            "A phase that comes with your files and is new to the library is stored here by itself. Add a phase yourself from a table with d (Å) or 2θ (Cu Kα1) and relative "
                            "intensities, for example a reference card exported from HighScore; name the file after the phase with its label in brackets: Portlandite (CH).csv",
                  style="Soft.TLabel", wraplength=px(1000), justify="left").pack(anchor="w", padx=14, pady=(2, 8))
        fr_ = ttk.Frame(win); fr_.pack(fill="both", expand=True, padx=14)
        lbx = tk.Listbox(fr_, font=("Consolas", 10), selectmode="extended", activestyle="none", exportselection=False); sb_ = ttk.Scrollbar(fr_, orient="vertical", command=lbx.yview)
        lbx.configure(yscrollcommand=sb_.set); lbx.pack(side="left", fill="both", expand=True); sb_.pack(side="right", fill="y")
        rows_ = []; info_ = tk.StringVar(value="")
        def fill(msg=""):
            rows_[:] = sp.library_table(options()); lbx.delete(0, "end")
            lbx.insert("end", f"{'Label':<7}{'Phase':<34}{'Lines':>6}  {'Kind':<10}{'Stored on':<12}Where it comes from")
            for r_ in rows_: lbx.insert("end", f"{r_['Code'][:6]:<7}{r_['Phase'][:32]:<34}{r_['Lines']:>6}  {r_['Kind']:<10}{r_['Added'][:10]:<12}{r_['Origin'][:120]}")
            n_ = {k_: sum(1 for r_ in rows_ if r_["Kind"] == k_) for k_ in ("built in", "stored", "your file")}
            info_.set((msg + "   " if msg else "") + f"{len(rows_)} phases: {n_['built in']} built in, {n_['stored']} stored, {n_['your file']} from your own csv files. Stored phases are kept in {sp.store_dir(options())}")
        def changed(lines):
            for l_ in lines: log("Phase library: " + l_)
            sp.store_news(); mark_dirty()
        def add():
            ps_ = filedialog.askopenfilenames(title="Choose the table(s) of the phase(s) to add", filetypes=[("Tables", "*.csv *.txt *.dat *.xlsx *.xls"), ("All files", "*.*")]) or []
            if not ps_: return
            lines_ = []; n_ = 0
            for p_ in ps_:
                try: done_, msgs_ = sp.add_phase_file(p_, options()); n_ += len(done_); lines_ += msgs_
                except Exception: lines_.append(f"!! {os.path.basename(p_)} could not be added:\n" + traceback.format_exc())
            changed(lines_); fill(f"{n_} phase(s) stored." + (" See the details for what was not stored." if any(l_.startswith(("not stored", "!!")) or "no column" in l_ or "could not" in l_ for l_ in lines_) else ""))
        def remove():
            sel_ = [rows_[i_ - 1] for i_ in lbx.curselection() if 1 <= i_ <= len(rows_)]
            if not sel_: info_.set("Click a stored phase in the list first."); return
            mine_ = [r_["Code"] for r_ in sel_ if r_["Removable"]]
            if not mine_: info_.set("Only stored phases can be removed here. Built-in phases stay; a phase from your own csv file goes when you delete that file from the folder."); return
            if not ask("Remove stored phases", "Remove from your stored phases: " + ", ".join(mine_) + " ?\nYour data files are not touched."): return
            gone_ = sp.remove_stored(mine_, options()); changed(["removed from the stored phases: " + ", ".join(gone_)]); fill(f"{len(gone_)} phase(s) removed.")
        def folder():
            d_ = sp.store_dir(options())
            try: os.makedirs(d_, exist_ok=True)
            except Exception: pass
            open_folder(d_)
        bb_ = ttk.Frame(win); bb_.pack(fill="x", padx=14, pady=10)
        ttk.Button(bb_, text="Add phase from file…", style="Accent.TButton", command=add).pack(side="left")
        ttk.Button(bb_, text="Remove stored phase", command=remove).pack(side="left", padx=8)
        ttk.Button(bb_, text="Open folder of stored phases", command=folder).pack(side="left")
        ttk.Checkbutton(bb_, text="Store new phases from my files", variable=xstore).pack(side="left", padx=16)
        ttk.Button(bb_, text="Close", command=lambda: win.destroy()).pack(side="right")
        ttk.Label(win, textvariable=info_, style="Soft.TLabel", wraplength=px(1000), justify="left").pack(anchor="w", padx=14, pady=(0, 12))
        fill()
    act["library"] = on_library
    def on_convert():
        ps_ = filedialog.askopenfilenames(title="Choose the files to convert to Excel", filetypes=[("Instrument and data files", "*.xrdml *.brml *.uxd *.ras *.spa *.ngb-ds3 *.ngb-ss3 *.xy *.xye *.asc *.dat *.txt *.csv"), ("All files", "*.*")]) or []
        if not ps_: return
        keep_ = [s_.path for s_ in singles]
        def work(): return sp.convert_to_excel(list(ps_), None, keep_)
        def done(res):
            if not res: return
            outs_, lines_ = res; log(f"Converted to Excel ({len(outs_)} of {len(ps_)} files; each workbook is next to its file):\n" + "\n".join(lines_)); show_details(True)
            bad_ = len(ps_) - len(outs_)
            status.set((f"{len(outs_)} file(s) converted to Excel, next to the original files." if outs_ else "Nothing could be converted.") + (f" {bad_} file(s) could NOT be converted: the reason is in the details below." if bad_ else ""))
        background(work, done, "Converting to Excel …")
    def on_import_origin():
        v = filedialog.askopenfilename(title="Choose an Origin project", filetypes=[("Origin project", "*.opju *.opj"), ("All files", "*.*")])
        if not v: return
        import datetime as _dt
        dest = os.path.join(run_folder(), "imported_from_origin", re.sub(r"[^A-Za-z0-9_-]+", "_", os.path.splitext(os.path.basename(v))[0]) + _dt.datetime.now().strftime("_%H%M%S"))
        def work(): return import_origin_project(v, dest, log)
        def done(files_):
            if not files_: show_details(True); status.set("The Origin project could not be imported. See the details."); return
            add_files(files_)
        background(work, done, "Opening the Origin project and reading its workbooks …")
    def paper_figures_run(workbook, recipe, only=None, then=None):
        """Figures for a paper, composed by a recipe from the sheets of a workbook (paper_figures.py): PDF and PNG at 600 dpi.
        `recipe` is the name of a recipe in figure_recipes, a .json file, or the recipe itself. Returns at once; `then(result)` runs when it is finished."""
        import paper_figures as pf
        rec = recipe if isinstance(recipe, dict) else pf.load_recipe(recipe); folder = os.path.join(run_folder(), "Paper_figures"); last_folder[0] = folder
        def work(): return pf.run(workbook, rec, folder, only=only, log=log, stop=lambda: cancel[0])
        def done(res):
            if res is None: status.set("The paper figures were not made. Press Show details to see why."); return
            for n_ in res["notes"]: log("   note: " + n_)
            status.set(res["text"] + ".  Folder: " + folder)
            if res["notes"]: show_details(True)
            if then: then(res)
        background(work, done, f"Drawing the paper figures from {os.path.basename(workbook)} \u2026")
    def on_paper_figures():
        import paper_figures as pf
        wb = filedialog.askopenfilename(title="The workbook with the data of the figures", filetypes=[("Excel workbook", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")])
        if not wb: return
        names = list(pf.recipes()); guess = pf.recipe_for(wb)
        if guess is None:
            rp = filedialog.askopenfilename(title="The recipe for these figures (.json)", initialdir=pf.RECIPE_DIR if os.path.isdir(pf.RECIPE_DIR) else here, filetypes=[("Figure recipe", "*.json")])
            if not rp: return
            guess = rp
        try: paper_figures_run(wb, guess)
        except Exception as e: status.set(f"I could not start the paper figures: {e}"); log("!! Paper figures:\n" + traceback.format_exc())
    # ---------------- new versions and AI repairs (self_update.py): nothing is installed without your click, and every install can be undone
    def upd_store(): return os.path.join(os.path.dirname(os.path.abspath(sp.store_dir())), "program_backups")
    def upd_restart(text):
        from tkinter import messagebox
        if messagebox.askyesno("Installed", text + "\n\nRestart the app now to use it?\n(Help > 'Undo the last update or fix' brings the earlier program back.)"): restart_app()
    def upd_offer(title, head, lines, trial, why, only=None):
        """The result of the check, and the one button that installs. Without a passed check there is no install button."""
        import self_update as su
        win = tk.Toplevel(root); win.title(title); win.configure(bg=CARD); win.transient(root)
        try: win.geometry(f"{px(900)}x{px(600)}")
        except Exception: pass
        ttk.Label(win, text=title, style="Step.TLabel").pack(anchor="w", padx=PAD, pady=(PAD, 2))
        ttk.Label(win, text=head, style="Soft.TLabel", wraplength=px(840), justify="left").pack(anchor="w", padx=PAD)
        bb = ttk.Frame(win); bb.pack(side="bottom", fill="x", padx=PAD, pady=PAD)
        box = SText(win, height=10, wrap="none", bg=_T["subtle"], fg=INK, font=("Consolas", -px(12)), relief="flat", borderwidth=0, padx=SP2, pady=SP2, highlightthickness=1, highlightbackground=LINE); box.pack(fill="both", expand=True, padx=PAD, pady=(SP3, 0))
        box.insert("1.0", "\n".join(lines)); box.config(state="disabled")
        def go():
            try: b_, ch_ = su.install(trial, here, upd_store(), why, only=only); log(f"Installed ({why}): {', '.join(ch_) or 'no file differed'}. Backup: {b_}"); win.destroy(); upd_restart(f"{why}: {len(ch_)} file(s) changed.")
            except Exception as e: log("!! The install did not work. If some files were already copied, Help > 'Undo the last update or fix' puts the earlier program back:\n" + traceback.format_exc()); status.set(f"The install did not work: {e}")
        ttk.Button(bb, text="Close", command=win.destroy).pack(side="right")
        if trial: ttk.Button(bb, text="Install this fix" if only else "Install this version", style="Accent.TButton", command=go).pack(side="right", padx=SP2)
        else: ttk.Label(bb, text="Not offered for install: the check did not pass.", foreground=_T["bad_text"]).pack(side="left")
    def on_update_source():
        from tkinter import simpledialog, messagebox
        v = simpledialog.askstring("Where new versions come from", "New versions come from the app's own repository. You only change this if someone gave you another place:\n"
                                   "a folder with zips, a link to a .zip or latest.json, or github:owner/repository.\nOnly use a place you trust. Type  off  to switch update checks off; leave empty for the app's own repository.", initialvalue=update_source() or "off", parent=root)
        if v is None: return None
        cfg["update_source"] = v.strip()
        if v.strip().lower().startswith("github:"):
            t_ = simpledialog.askstring("Private repository?", "Only if the repository is PRIVATE: paste a read-only access token of GitHub here.\nFor a public repository leave this empty.", show="\u2022", parent=root)
            if t_ is not None:
                try: cfg["update_token"] = ai.protect_key(t_.strip()) if t_.strip() else ""
                except Exception: cfg["update_token"] = ""
        remember(); status.set("Updates come from: " + (v.strip() or "nowhere (switched off)")); return v.strip()
    def update_source():
        """Where new versions come from: the app's own repository, unless you set another place (empty = switched off)."""
        import self_update as su
        raw = str(cfg.get("update_source") or "").strip()        # nothing set (also by an older version) = the app's own repository
        v = su.normalize_source(raw)
        if raw and not v:                                    # something was typed that is no place for updates: use the app's own repository, and say so once
            log(f"The place for updates in the settings ('{raw[:80]}') is not one I can use; I use the app's own repository instead."); cfg["update_source"] = ""; v = ""
        elif v and v != raw and v != "off": cfg["update_source"] = v      # a pasted web address becomes github:owner/repository
        return "" if v == "off" else (v or su.DEFAULT_SOURCE)
    def restart_app():
        try:
            import subprocess
            st_ = os.path.join(here, "start.pyw"); exe_ = sys.executable; pw_ = os.path.join(os.path.dirname(exe_), "pythonw.exe")
            subprocess.Popen([pw_ if os.path.isfile(pw_) else exe_, st_ if os.path.isfile(st_) else os.path.join(here, "origin_plot_app.py")], cwd=here, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            root.after(200, on_close)
        except Exception as e: status.set(f"I could not restart by myself ({e}). Close the app and start it again.")
    def on_update_zip():
        """Update from a zip you downloaded yourself."""
        z = filedialog.askopenfilename(title="The zip of the new version (as you downloaded it)", initialdir=os.path.join(os.path.expanduser("~"), "Downloads"), filetypes=[("Zip", "*.zip"), ("All files", "*.*")])
        if z: on_update(source=z)
    upd_win = [None]; upd_known = [None]
    def update_waiting(info):
        """A newer version is there: a badge in the header, and one question. 'Update now' does everything; 'Later' leaves the badge."""
        v_ = str(info.get("version") or "").strip()
        try: updpilltxt.set(f"\u2191  Update {v_} available" if v_ else "\u2191  Update available"); updpill.pack(side="left", padx=(0, SP3), before=aipill)
        except Exception: pass
        status.set(f"Version {v_} is available. Click 'Update {v_} available' at the top to install it." if v_ else "A new version is available.")
        if busy[0] or abusy[0] or upd_win[0] is not None: return
        win = tk.Toplevel(root); win.title("Update available"); win.configure(bg=CARD); win.transient(root); win.resizable(False, False)
        W_, H_ = px(460), px(230)
        try: win.geometry(f"{W_}x{H_}+{root.winfo_rootx() + (root.winfo_width() - W_) // 2}+{root.winfo_rooty() + (root.winfo_height() - H_) // 3}")
        except Exception: pass
        f_ = ttk.Frame(win, padding=PAD); f_.pack(fill="both", expand=True)
        kicker(f_, "Update available").pack(anchor="w")
        ttk.Label(f_, text=f"Version {v_} is ready" if v_ else "A new version is ready", style="Title.TLabel").pack(anchor="w", pady=(px(2), SP1))
        note_ = str(info.get("notes") or "").split("\n")[0][:150]
        ttk.Label(f_, text=f"You have version {sp.VERSION}." + (f"\nNew: {note_}" if note_ else "") + "\nIt takes under a minute. Your settings and files stay as they are.", style="Soft.TLabel", wraplength=W_ - 2 * PAD, justify="left").pack(anchor="w")
        bb = ttk.Frame(f_); bb.pack(side="bottom", fill="x")
        ttk.Button(bb, text="Later", command=win.destroy).pack(side="right")
        ttk.Button(bb, text="Update now", style="Accent.TButton", command=lambda: (win.destroy(), on_update())).pack(side="right", padx=(0, SP2))
        try: win.bind("<Return>", lambda e: (win.destroy(), on_update())); win.bind("<Escape>", lambda e: win.destroy()); win.lift(); win.focus_force()
        except Exception: pass
    def on_update(quiet=False, source=None):
        """One click: look for a new version, download it, redraw the example files with it, install it, offer to restart.
        A version that draws an example differently is not installed by itself: you see what differs and decide."""
        import self_update as su, queue as _queue, shutil
        src = str(source or update_source()).strip()
        try: su.TOKEN = (ai.reveal_key(cfg.get("update_token", "")) or "") if cfg.get("update_token") else ""
        except Exception: su.TOKEN = ""
        if quiet:                                            # at the start: only look, and show the badge in the header
            if not src: return
            def look():
                try: r_ = su.find_update(src, sp.VERSION)
                except Exception: return
                if r_: upd_known[0] = r_; root.after(0, lambda: update_waiting(r_))
            threading.Thread(target=look, daemon=True).start(); return
        if busy[0]: status.set("One moment please: let the current step finish, then check for updates again."); return
        if upd_win[0] is not None:
            try: upd_win[0].lift(); upd_win[0].focus_force(); return
            except Exception: upd_win[0] = None
        if not src: status.set("Update checks are switched off. Help > 'Where updates come from…' switches them on."); return
        win = tk.Toplevel(root); upd_win[0] = win; win.title("Update"); win.configure(bg=CARD); win.transient(root); win.resizable(False, False)
        W_, H_ = px(560), px(330)
        try: win.geometry(f"{W_}x{H_}+{root.winfo_rootx() + (root.winfo_width() - W_) // 2}+{root.winfo_rooty() + (root.winfo_height() - H_) // 3}")
        except Exception: pass
        f_ = ttk.Frame(win, padding=PAD); f_.pack(fill="both", expand=True)
        kicker(f_, "Update").pack(anchor="w")
        head = tk.StringVar(value="Looking for a new version…"); ttk.Label(f_, textvariable=head, style="Title.TLabel", wraplength=W_ - 2 * PAD, justify="left").pack(anchor="w", pady=(px(2), SP1))
        sub = tk.StringVar(value=f"You have version {sp.VERSION}."); ttk.Label(f_, textvariable=sub, style="Soft.TLabel", wraplength=W_ - 2 * PAD, justify="left").pack(anchor="w")
        bar = ttk.Progressbar(f_, mode="determinate", maximum=100); bar.pack(fill="x", pady=(SP4, SP2))
        line = tk.StringVar(value=""); ttk.Label(f_, textvariable=line, style="Muted.TLabel", wraplength=W_ - 2 * PAD, justify="left").pack(anchor="w")
        bb = ttk.Frame(f_); bb.pack(side="bottom", fill="x")
        b_main = ttk.Button(bb, text="Restart now", style="Accent.TButton"); b_side = ttk.Button(bb, text="Cancel")
        b_side.pack(side="right")
        q = _queue.Queue(); st = {"stop": False, "open": True, "trial": None}
        work = os.path.join(upd_store(), "_trial")
        def close():
            st["stop"] = True; st["open"] = False; upd_win[0] = None
            try: win.destroy()
            except Exception: pass
        b_side.configure(command=close); win.protocol("WM_DELETE_WINDOW", close)
        def worker():
            try:
                info = upd_known[0] if (upd_known[0] and not source) else su.find_update(src, sp.VERSION)
                if not info: q.put(("none",)); return
                v_ = info.get("version") or "new"; q.put(("found", v_, 12)); shutil.rmtree(work, ignore_errors=True)
                trial = su.fetch_and_unpack(info, work); v_ = su.version_of(trial) or v_
                if not su.newer(v_, sp.VERSION): q.put(("none",)); return
                q.put(("checking", v_, 30))
                c_ = su.check(trial, here, quick=True, stop=lambda: st["stop"], log=lambda m: q.put(("line", m)), progress=lambda fr: q.put(("bar", 30 + 60 * fr)))
                if st["stop"]: return
                q.put(("checked", trial, c_, v_, str(info.get("notes") or "").split("\n")[0][:140]))
            except su.UpdateError as e: q.put(("fail", str(e)[:480])); log("Update: " + str(e))
            except Exception as e: q.put(("fail", su.explain(e)[:480])); log("Update: " + traceback.format_exc())
        def do_install(trial, v_, forced=False):
            try:
                b_, ch_ = su.install(trial, here, upd_store(), f"update {sp.VERSION} to {v_}"); log(f"Updated {sp.VERSION} to {v_}: {len(ch_)} file(s) changed. Backup: {b_}")
                bar.configure(value=100); head.set(f"Version {v_} is installed"); sub.set("Restart the app to use it. Help > 'Undo the last update or fix' brings the earlier version back."); line.set(f"{len(ch_)} file(s) changed.")
                b_main.configure(text="Restart now", command=lambda: (close(), restart_app())); b_main.pack(side="right", padx=(0, SP2)); b_side.configure(text="Later")
                try: updpill.pack_forget()
                except Exception: pass
                upd_known[0] = None; status.set(f"Version {v_} is installed. It is used after a restart.")
            except Exception as e:
                head.set("The update could not be installed"); sub.set(str(e)[:200]); line.set("Nothing you had was lost. Help > 'Undo the last update or fix' puts the earlier program back if files were already copied."); log("!! Update install:\n" + traceback.format_exc())
        def pump():
            if not st["open"]: return
            try:
                while True:
                    m = q.get_nowait()
                    if m[0] == "none": bar.configure(value=100); head.set("You are up to date"); sub.set(f"Version {sp.VERSION} is the newest."); line.set(""); b_side.configure(text="Close")
                    elif m[0] == "found": bar.configure(value=m[2]); head.set(f"Downloading version {m[1]}…"); sub.set(f"You have version {sp.VERSION}.")
                    elif m[0] == "checking": bar.configure(value=m[2]); head.set(f"Checking version {m[1]}…"); sub.set("The example files are redrawn with the new version and compared with today's result.")
                    elif m[0] == "line": line.set(m[1])
                    elif m[0] == "bar": bar.configure(value=m[1])
                    elif m[0] == "fail":
                        bar.configure(value=0); head.set("The update did not work"); sub.set(m[1]); line.set("Nothing was changed."); b_side.configure(text="Close")
                        if src.lower().startswith("github:"):          # the way round: the zip in the browser, then 'Install an update from a zip file'
                            def by_browser():
                                import webbrowser
                                webbrowser.open("https://github.com/" + src.split(":", 1)[1] + "/archive/HEAD.zip"); line.set("The zip is downloading in your browser. Then: Help > 'Install an update from a zip file\u2026' and choose it in Downloads.")
                            ttk.Button(bb, text="Get the zip in the browser", command=by_browser).pack(side="left")
                        b_main.configure(text="Try again", command=lambda: (close(), on_update(source=source))); b_main.pack(side="right", padx=(0, SP2))
                    elif m[0] == "checked":
                        _, trial, c_, v_, note_ = m
                        if c_["ok"]:
                            line.set(f"All {c_['same']} example files are drawn exactly as before." + (f"  New: {note_}" if note_ else "")); head.set(f"Installing version {v_}…"); bar.configure(value=95)
                            win.after(150, lambda: do_install(trial, v_))
                        else:                                # drawings differ: never installed by itself
                            head.set(f"Version {v_} draws some examples differently"); sub.set("The check is finished. A new version can change drawings on purpose: press the button to see what differs, then 'Install this version'."); bar.configure(value=100); line.set(f"{len(c_['different'])} of {c_['covered']} example files differ.")
                            b_main.configure(text="Show what differs and install…", command=lambda: (close(), upd_offer("New version " + v_, f"Version {v_}. {len(c_['different'])} example(s) come out different from now.", c_["lines"], trial, f"update {sp.VERSION} to {v_}")))
                            b_main.pack(side="right", padx=(0, SP2)); b_side.configure(text="Do not install")
            except _queue.Empty: pass
            win.after(90, pump)
        bar.configure(value=4); threading.Thread(target=worker, daemon=True).start(); pump()
    def on_undo_update():
        import self_update as su
        from tkinter import messagebox
        bs = su.backups(upd_store())
        if not bs: status.set("There is no earlier version to go back to."); return
        if not messagebox.askyesno("Undo", f"Put back the program as it was before the last update or fix?\n({os.path.basename(bs[-1])})"): return
        try: t_ = su.undo(here, upd_store()); log("Undo: " + t_); upd_restart("Undone: " + t_ + ".")
        except Exception as e: status.set(f"Undo did not work: {e}"); log("!! Undo:\n" + traceback.format_exc())
    def on_ai_repair():
        """Ask the linked AI for a fix of the last problem, try it on a copy, and offer it only when every example still draws the same."""
        import self_update as su
        from tkinter import messagebox
        if not problems: status.set("There is no problem to repair: nothing has gone wrong in this session."); return
        if aconn[0] is None or not aimodel.get().strip(): status.set("Link an AI first (Focused Copilot > Change AI\u2026); the repair is written by that AI."); return
        prob = problems[-1][1]
        try: msg, files = su.repair_message(prob, here)
        except su.UpdateError as e: status.set(str(e)); return
        if not messagebox.askyesno("Repair with AI", f"This sends the error message and parts of the program code ({', '.join(files)}; about {len(msg) // 1000 + 1} thousand characters, no data of yours) to {aconn[0]['name']}.\n\n"
                                   "Its fix is tried on a copy of the program. It is offered to you only if the copy still draws every example file exactly as now. "
                                   "That check cannot cover a new kind of file, and it does not cover the composed paper figures.\n\nSend it?"): return
        conn, model = aconn[0], aimodel.get().strip(); work = os.path.join(upd_store(), "_repair")
        def work_():
            reply = ai.chat(conn, model, su.REPAIR_SYSTEM, [{"role": "user", "content": msg}]); expl, edits = su.parse_edits(reply)
            if not edits: return {"expl": expl or "The AI saw no safe fix.", "trial": None, "lines": ["The AI proposed no change."], "files": []}
            try: trial, touched = su.make_trial(here, edits, work)
            except su.UpdateError as e: return {"expl": expl, "trial": None, "lines": ["The proposed fix was refused before any test:", str(e)], "files": []}
            c_ = su.check(trial, here, log=lambda m: root.after(0, lambda: status.set(m)), stop=lambda: cancel[0])
            return {"expl": expl, "trial": trial if c_["ok"] else None, "lines": c_["lines"] + ["", "THE CHANGE:", su.diff_text(here, trial, touched)], "files": touched, "check": c_}
        def done(r_):
            if not r_: status.set("The repair could not be made. Press Show details to see why."); return
            ok = bool(r_["trial"]); c_ = r_.get("check") or {}
            head = (f"{r_['expl']}\n\nThe trial copy compiles and draws all {c_.get('same', 0)} example files exactly as now. The check cannot prove the fix for a file type the examples do not hold." if ok else
                    f"{r_['expl']}\n\nThis fix is NOT offered: " + ("it changed how examples are drawn, or did not run." if c_ else "it could not be tried."))
            upd_offer("AI repair of the last problem", head, r_["lines"], r_["trial"], "AI repair: " + (r_["expl"][:80] or "last problem"), only=r_["files"] or None); status.set("The repair is checked." if ok else "The repair did not pass the check; nothing was changed.")
        background(work_, done, "Asking the AI for a repair and testing it on a copy \u2026")
    def on_readme():
        try: os.startfile(os.path.join(here, "README.txt"))
        except Exception as e: log(f"The guide is the file README.txt in {here} ({e})")
    def on_about():
        t_ = f"Origin plot app {sp.VERSION}\nReads your data files, recognises the kind of measurement, shows a preview and draws the graphs in Origin.\nYour data files are only read, never changed."
        try:
            from tkinter import messagebox
            messagebox.showinfo("About", t_)
        except Exception: log(t_)
    try:                                                 # the menu bar: the usual places for the usual things
        mb = tk.Menu(root); mf = tk.Menu(mb, tearoff=0); ma = tk.Menu(mb, tearoff=0); mx = tk.Menu(mb, tearoff=0); mr = tk.Menu(mb, tearoff=0); mh = tk.Menu(mb, tearoff=0)
        mi = mf                                                   # (older name: the import entries now live in File)
        # File: everything about files and the project
        mf.add_command(label="Modern window\u2026", command=lambda: act["modern_window"]())
        mf.add_separator()
        mf.add_command(label="New project (start anew)", accelerator="Ctrl+N", command=on_new)
        mf.add_command(label="Open session…", accelerator="Ctrl+O", command=on_open_session)
        mf.add_command(label="Resume last session", accelerator="Ctrl+R", command=on_resume)
        mf.add_command(label="Save session…", accelerator="Ctrl+S", command=lambda: act["save"]())
        mf.add_separator()
        mf.add_command(label="Import data files…", accelerator="Ctrl+I", command=lambda: on_add())
        mf.add_command(label="Import from an Origin project…", command=on_import_origin)
        mf.add_command(label="Convert files to Excel… (.xrdml, .brml, .ras, .uxd, text)", command=on_convert)
        mf.add_separator()
        mf.add_command(label="Save everything in the list as one workbook…", command=lambda: act["workbook"]())
        mf.add_command(label="Workbook template…", command=lambda: act["template"]())
        mf.add_command(label="Make a gallery graph template\u2026 (G01\u2013G24, C01, C02)", command=lambda: act["figtype_template"]())
        mf.add_separator()
        mf.add_command(label="Refresh previews", command=on_rebuild)
        mf.add_command(label="Open results folder", command=lambda: open_folder())
        mf.add_command(label="Close project", command=on_new)
        mf.add_separator()
        mf.add_command(label="Exit", accelerator="Ctrl+Q", command=lambda: on_close())
        # Analysis: the data-analysis tools (analysis_tools.py) and the app's own analyses
        import analysis_tools as at_m
        for g_ in at_m.GROUPS:
            sub_ = tk.Menu(ma, tearoff=0)
            for lab_, (gg_, _f, _s, d_, _h) in at_m.TOOLS.items():
                if gg_ == g_: sub_.add_command(label=f"{lab_}\u2026" if _s else lab_, command=lambda l_=lab_: act["analysis"](l_))
            ma.add_cascade(label=g_, menu=sub_)
        ma.add_separator()
        def _tga_steps():
            try: say("app", str(CMD["analyze_tga_steps"]()))
            except Exception as e_: messagebox.showerror("TGA mass loss", str(e_), parent=root)
        ma.add_command(label="TGA: mass loss in temperature intervals", command=_tga_steps)
        ma.add_command(label="Calorimetry (TAM III): workbook, figures C1\u2013C5\u2026", command=lambda: act["calorimetry"]())
        ma.add_command(label="Hydration degree from phase amounts (C01)", command=lambda: log(figtype_apply("C01")))
        ma.add_command(label="Atomic ratios (C02)", command=lambda: log(figtype_apply("C02")))
        ma.add_separator()
        ma.add_command(label="Analysis settings (TGA, calorimetry, XRD …)", command=lambda: nb.select(t4))
        # XRD tools
        mx.add_command(label="XRD Scan Generator (app)\u2026  generate scans, Peak correct", command=lambda: act["xrd_app"]())
        mx.add_command(label="Peak correct / improve an XRD scan\u2026 (any counts)", command=lambda: act["improve_scan"]())
        mx.add_command(label="Generate XRD scans (built-in window)\u2026", command=lambda: act["xrd_generator"]())
        mx.add_separator(); mx.add_command(label="Phase library… (stored phases for suggestions)", command=on_library)
        # Draw
        mr.add_command(label="Draw ticked graphs", accelerator="F5", command=lambda: act["draw_sel"]())
        mr.add_command(label="Draw all graphs", accelerator="Shift+F5", command=lambda: act["draw_all"]())
        mr.add_separator()
        mr.add_command(label="Preview paper set (PDF)", command=lambda: act["paper_preview"]())
        mr.add_command(label="Make paper set", command=lambda: act["paper"]())
        mr.add_command(label="Paper figures from a recipe\u2026 (composed figures, PDF + PNG 600 dpi)", command=on_paper_figures)
        mr.add_separator()
        mr.add_command(label="Stop", accelerator="Esc", command=on_stop)
        mh.add_command(label="System Check\u2026", command=lambda: act["system_check"]())
        mh.add_command(label="Assistant settings (API key, local model)\u2026", command=lambda: act["assistant_settings"]())
        mh.add_command(label="Guide (README)", accelerator="F1", command=on_readme)
        mh.add_command(label="Show or hide details", command=lambda: show_details(not details[0]))
        mh.add_separator()
        mh.add_command(label="Install an update from a zip file\u2026", command=on_update_zip)
        mh.add_command(label="Speed report\u2026 (what was slow, to send to whoever looks after the app)", command=lambda: (slow.write("--- speed report opened"), open_folder(os.path.dirname(slow.file()))))
        mh.add_command(label="Check for updates and install", command=lambda: on_update())
        mh.add_command(label="Where updates come from\u2026", command=on_update_source)
        mh.add_command(label="Repair the last problem with AI\u2026 (tested on a copy first)", command=lambda: on_ai_repair())
        mh.add_command(label="Undo the last update or fix", command=on_undo_update)
        mh.add_separator()
        mh.add_command(label="About", command=on_about)
        mb.add_cascade(label="File", menu=mf); mb.add_cascade(label="Analysis", menu=ma); mb.add_cascade(label="XRD tools", menu=mx); mb.add_cascade(label="Draw", menu=mr); mb.add_cascade(label="Help", menu=mh)
        HOOKS["menus"] = {"File": mf, "Analysis": ma, "XRD tools": mx, "Draw": mr, "Help": mh}
        root.config(menu=mb)
        for key_, f_ in (("<Control-n>", on_new), ("<Control-o>", lambda: on_open_session()), ("<Control-r>", on_resume), ("<Control-s>", lambda: act["save"]()), ("<Control-q>", lambda: on_close()), ("<Control-i>", lambda: on_add()),
                         ("<F5>", lambda: act["draw_sel"]()), ("<Shift-F5>", lambda: act["draw_all"]()), ("<Escape>", on_stop), ("<F1>", on_readme)):
            root.bind(key_, lambda e, f_=f_: f_())
    except Exception: pass
    # ---------------- the assistant: an AI of your choice turns typed instructions into the app's own actions
    import time as _time
    import assistant as ai
    ahome = ai.home(sp.store_dir()); acfg = ai.load_settings(ahome)
    akeys = {k_: ai.reveal_key(v_) for k_, v_ in (acfg.get("keys") or {}).items()}; akeys = {k_: v_ for k_, v_ in akeys.items() if v_}; amodels = dict(acfg.get("models") or {}); aaddrs = dict(acfg.get("addresses") or {})
    if acfg.get("key") and ai.whose_key(acfg["key"]): akeys.setdefault(ai.whose_key(acfg["key"]), acfg["key"])          # settings of version 5.14.0
    aiprov = tk.StringVar(value=acfg.get("choice") if acfg.get("choice") in ai.CHOICES else ai.CHOICES[0]); p0_ = ai.provider_of(aiprov.get())
    aikey = tk.StringVar(value=akeys.get(p0_, "") if p0_ else next(iter(akeys.values()), "")); aiaddr = tk.StringVar(value=aaddrs.get(p0_, "") if p0_ else "")
    aimodel = tk.StringVar(value=amodels.get(p0_, "") if p0_ else ""); aikeep = tk.BooleanVar(value=bool(acfg.get("keep_key", True)))
    aistat = tk.StringVar(value="Not linked yet."); aiguide = tk.StringVar(value=ai.GUIDES.get(p0_, ai.GUIDES[None]))
    aconn = [None]; ahist = []; asaid = []; achat = []; abusy = [False]; aquiet = [False]; apending = [None]; atried = set(); awarned = [False]
    # --- Focused Copilot: the data and the live preview (left card, about a third) and the assistant (right card)
    SUB = _T["subtle"]
    for k_ in ("ok", "warn", "bad", "idle"): th.pill("Soft." + k_.capitalize() + ".Pill.TLabel", k_, SUB)
    # Three panels: the list of graphs, the live preview, the assistant. They are placed by the chosen arrangement, and the
    # gaps between them can be dragged. The arrangement and the sizes are remembered.
    acontext = ttk.Frame(t6, style="Card.TFrame", padding=PAD); acontext.pack_propagate(False)       # the list of graphs
    aprev = ttk.Frame(t6, style="Card.TFrame", padding=PAD); aprev.pack_propagate(False)             # the live preview
    amain = ttk.Frame(t6, style="Card.TFrame", padding=PAD); amain.pack_propagate(False)             # the assistant
    LAYOUTS = {"side": "Graphs and preview left, assistant right", "below": "Graphs and preview on top, assistant below", "three": "Graphs, preview and assistant side by side", "swap": "Assistant left, graphs and preview right"}
    SPLITS0 = {"side": [0.34, 0.50], "below": [0.52, 0.42], "three": [0.24, 0.58], "swap": [0.62, 0.50]}
    lay = {"name": cfg.get("layout") if cfg.get("layout") in LAYOUTS else "side", "splits": {k_: list(v_) for k_, v_ in SPLITS0.items()}, "job": None}
    try:
        for k_, v_ in (cfg.get("layout_splits") or {}).items():
            if k_ in SPLITS0 and len(v_) == 2: lay["splits"][k_] = [min(0.85, max(0.15, float(v_[0]))), min(0.85, max(0.15, float(v_[1])))]
    except Exception: pass
    sash_a = tk.Frame(t6, bg=BG); sash_b = tk.Frame(t6, bg=BG)
    def layout_now(event=None):
        lay["job"] = None
        try:
            W_, H_ = t6.winfo_width(), t6.winfo_height()
            if W_ < 50 or H_ < 50: return
            a_, b_ = lay["splits"][lay["name"]]; g = GAP; nm = lay["name"]
            def put(w, x, y, wd, ht): w.place(x=int(x), y=int(y), width=max(40, int(wd)), height=max(40, int(ht)))
            if nm in ("side", "swap"):                       # two columns; the column with the graphs is split in two rows
                xa = int(W_ * a_); col_x, col_w, chat_x, chat_w = (0, xa - g // 2, xa + g // 2, W_ - xa - g // 2) if nm == "side" else (xa + g // 2, W_ - xa - g // 2, 0, xa - g // 2)
                yb = int(H_ * b_)
                put(acontext, col_x, 0, col_w, yb - g // 2); put(aprev, col_x, yb + g // 2, col_w, H_ - yb - g // 2); put(amain, chat_x, 0, chat_w, H_)
                sash_a.place(x=xa - g // 2, y=0, width=g, height=H_); sash_a.configure(cursor="sb_h_double_arrow"); sash_b.place(x=col_x, y=yb - g // 2, width=col_w, height=g); sash_b.configure(cursor="sb_v_double_arrow")
            elif nm == "below":                              # graphs and preview side by side on top, the assistant under them
                ya = int(H_ * a_); xb = int(W_ * b_)
                put(acontext, 0, 0, xb - g // 2, ya - g // 2); put(aprev, xb + g // 2, 0, W_ - xb - g // 2, ya - g // 2); put(amain, 0, ya + g // 2, W_, H_ - ya - g // 2)
                sash_a.place(x=0, y=ya - g // 2, width=W_, height=g); sash_a.configure(cursor="sb_v_double_arrow"); sash_b.place(x=xb - g // 2, y=0, width=g, height=ya - g // 2); sash_b.configure(cursor="sb_h_double_arrow")
            else:                                            # three columns
                a_, b_ = min(a_, b_ - 0.12), max(b_, a_ + 0.12); xa, xb = int(W_ * a_), int(W_ * b_)
                put(acontext, 0, 0, xa - g // 2, H_); put(aprev, xa + g // 2, 0, xb - xa - g, H_); put(amain, xb + g // 2, 0, W_ - xb - g // 2, H_)
                sash_a.place(x=xa - g // 2, y=0, width=g, height=H_); sash_b.place(x=xb - g // 2, y=0, width=g, height=H_)
                for s_ in (sash_a, sash_b): s_.configure(cursor="sb_h_double_arrow")
        except Exception: pass
    def layout_soon(event=None):
        if lay["job"] is None: lay["job"] = root.after(25, layout_now)
    def sash_drag(which, event):
        """Dragging a gap between two panels changes their share of the room."""
        try:
            nm = lay["name"]; W_, H_ = max(1, t6.winfo_width()), max(1, t6.winfo_height()); x_ = (event.x_root - t6.winfo_rootx()) / W_; y_ = (event.y_root - t6.winfo_rooty()) / H_
            horiz = (which == 0 and nm != "below") or (which == 1 and nm in ("below", "three")); v_ = min(0.85, max(0.15, x_ if horiz else y_)); sp_ = lay["splits"][nm]
            if nm == "three": v_ = min(v_, sp_[1] - 0.12) if which == 0 else max(v_, sp_[0] + 0.12)
            sp_[which] = round(v_, 3); layout_soon()
        except Exception: pass
    for k_, s_ in enumerate((sash_a, sash_b)):
        s_.bind("<B1-Motion>", lambda e, k_=k_: sash_drag(k_, e)); s_.bind("<ButtonRelease-1>", lambda e: remember())
        s_.bind("<Enter>", lambda e, s_=s_: s_.configure(bg=_T["border_strong"])); s_.bind("<Leave>", lambda e, s_=s_: s_.configure(bg=BG))
    def set_layout(name=None, reset=False):
        if reset: lay["splits"][lay["name"]] = list(SPLITS0[lay["name"]])
        elif name in LAYOUTS: lay["name"] = name
        layvar.set(lay["name"]); layout_now(); remember(); status.set("Arrangement: " + LAYOUTS[lay["name"]] + ". Drag the gaps between the panels to resize them.")
    layvar = tk.StringVar(value=lay["name"]); laymenu = tk.Menu(root, tearoff=0, font=font)
    for k_, lab_ in LAYOUTS.items(): laymenu.add_radiobutton(label=lab_, variable=layvar, value=k_, command=lambda k_=k_: set_layout(k_))
    laymenu.add_separator(); laymenu.add_command(label="Reset the sizes of this arrangement", command=lambda: set_layout(reset=True))
    laybtn = ttk.Button(hb, text="Arrange  ▾", style="Canvas.TButton", command=lambda: (nb.select(t6), laymenu.tk_popup(laybtn.winfo_rootx(), laybtn.winfo_rooty() + laybtn.winfo_height() + 2))); laybtn.pack(side="left", padx=(0, SP2), before=aipill)
    t6.bind("<Configure>", layout_soon, add="+"); act["layout"] = set_layout
    root.bind("<Control-l>", lambda e: set_layout(list(LAYOUTS)[(list(LAYOUTS).index(lay["name"]) + 1) % len(LAYOUTS)]))
    # --- panel 1: the graphs
    hdl = ttk.Frame(acontext); hdl.pack(fill="x")
    buttons.append(ttk.Button(hdl, text="+  Add files", style="Small.TButton", command=lambda: act["add"]())); buttons[-1].pack(side="right", anchor="n")
    kicker(hdl, "Data").pack(anchor="w"); ttk.Label(hdl, text="Your graphs", style="Step.TLabel").pack(anchor="w", pady=(px(2), 0))
    acontext_file = tk.StringVar(value="No graph selected yet")
    assistant_action = tk.StringVar(value="Add a file to get started.")
    hintbox = ttk.Frame(acontext, height=px(34)); hintbox.pack(side="bottom", fill="x", pady=(SP2, 0)); hintbox.pack_propagate(False)
    autowrap(ttk.Label(hintbox, textvariable=assistant_action, style="Muted.TLabel"), acontext, used=2 * PAD, most=520, least=160).pack(anchor="nw")
    cards_out, cards_in = scrolling(acontext); cards_out.pack(fill="both", expand=True, pady=(SP3, 0))
    # --- panel 2: the live preview, as large as its panel
    hdp = ttk.Frame(aprev); hdp.pack(fill="x")
    kicker(hdp, "Live preview").pack(anchor="w"); ttk.Label(hdp, textvariable=acontext_file, style="Step.TLabel").pack(anchor="w", pady=(px(2), 0))
    doors = ttk.Frame(aprev); doors.pack(side="bottom", fill="x", pady=(SP1, 0))
    for k_, (lab_, t_) in enumerate((("Plot settings", t2), ("Data & phases", t4), ("Look & saving", t3))):
        ttk.Button(doors, text=lab_, style="Ghost.TButton", cursor="hand2", command=lambda t_=t_: nb.select(t_)).pack(side="left", padx=(0, px(2)))
    ttk.Button(aprev, text="Open full preview", command=lambda: nb.select(t2)).pack(side="bottom", fill="x", pady=(SP3, 0))
    pbox = ttk.Frame(aprev, style="Preview.TFrame", padding=px(8)); pbox.pack(fill="both", expand=True, pady=(SP3, 0))
    assistant_preview_host = tk.Frame(pbox, bg="white"); assistant_preview_host.pack(fill="both", expand=True); assistant_preview_host.pack_propagate(False)
    assistant_fig = assistant_canvas = None
    try:
        from matplotlib.figure import Figure as AssistantFigure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as AssistantCanvas
        assistant_fig = AssistantFigure(figsize=(3.3, 2.4), dpi=int(PREVIEW_DPI * 0.9), facecolor="white")
        assistant_canvas = AssistantCanvas(assistant_fig, master=assistant_preview_host); assistant_canvas.get_tk_widget().configure(bg="white", highlightthickness=0); assistant_canvas.get_tk_widget().pack(fill="both", expand=True)
        assistant_fig.text(0.5, 0.5, "Click a graph in the list\nto see it here", ha="center", va="center", color=_T["muted"], fontsize=10); assistant_canvas.draw()
    except Exception:
        ttk.Label(assistant_preview_host, text="Preview appears here after you select a graph.", style="Soft.TLabel", background="white", wraplength=px(230), justify="center").pack(expand=True)
    live = {"key": None, "job": None, "size": (0, 0)}
    def live_resized(event=None):
        """The panel got another size: the graph in it is laid out again for that size, once the dragging has stopped."""
        try:
            sz = (assistant_preview_host.winfo_width(), assistant_preview_host.winfo_height())
            if abs(sz[0] - live["size"][0]) < 6 and abs(sz[1] - live["size"][1]) < 6: return
            live["size"] = sz
            if live["job"] is not None: root.after_cancel(live["job"])
            def again():
                live["job"] = None; it_ = next((i_ for i_ in items if sp.key_of(i_) == live["key"]), None)
                if it_ is not None and on_view(t6): assistant_show(it_)
            live["job"] = root.after(220, again)
        except Exception: pass
    assistant_preview_host.bind("<Configure>", live_resized, add="+")
    # --- the assistant card: who is linked, the conversation, what was done, the place to type
    hd = ttk.Frame(amain); hd.pack(fill="x")
    amenu = tk.Menu(root, tearoff=0, font=font)
    amore = ttk.Button(hd, text="More  \u25BE", style="Small.TButton", command=lambda: amenu.tk_popup(amore.winfo_rootx(), amore.winfo_rooty() + amore.winfo_height() + 2)); amore.pack(side="right", anchor="n")
    amenu.add_command(label="New chat", command=lambda: act["ai_new"]()); amenu.add_command(label="Earlier chats…", command=lambda: act["ai_file"]("chats")); amenu.add_separator()
    amenu.add_command(label="My instructions…", command=lambda: act["ai_file"]("instructions")); amenu.add_command(label="What it has learned…", command=lambda: act["ai_file"]("lessons")); amenu.add_separator()
    amenu.add_command(label="Choose the results folder…", command=choose_folder); amenu.add_command(label="Problem report…", command=lambda: act["ai_report"]())
    achange = ttk.Button(hd, text="Change AI…", style="Small.TButton", command=lambda: act["ai_linkbox"]()); achange.pack(side="right", anchor="n", padx=(0, SP2))
    hdr = ttk.Frame(hd); hdr.pack(side="right", anchor="n", padx=(SP3, SP3), pady=(px(4), 0))
    ttk.Label(hdr, textvariable=aistat, style="Muted.TLabel").pack(side="right"); ttk.Label(hdr, text=" · ", style="Muted.TLabel").pack(side="right"); ttk.Label(hdr, textvariable=aimodel, style="Muted.TLabel").pack(side="right")
    kicker(hd, "Assistant").pack(anchor="w"); ttk.Label(hd, text="Work on the selected graph", style="Step.TLabel").pack(anchor="w", pady=(px(2), 0))
    q1 = ttk.Frame(amain, style="Soft.TFrame", padding=px(14))
    def q1row(**kw): return ttk.Frame(q1, style="Subtle.TFrame", **kw)
    def q1lab(parent, text): return ttk.Label(parent, text=text, background=SUB, foreground=_T["text2"])
    kicker(q1, "Connect an AI provider", background=SUB).pack(anchor="w", pady=(0, SP2))
    # three short rows instead of one long one: nothing is pushed off the edge in a narrow window
    r1 = q1row(); r1.pack(fill="x", pady=2)
    q1lab(r1, "1  Choose the AI").pack(side="left"); aibox = ttk.Combobox(r1, textvariable=aiprov, values=ai.CHOICES, width=36, state="readonly"); aibox.pack(side="left", padx=(SP2, SP4))
    q1lab(r1, "Model").pack(side="left"); aimbox = ttk.Combobox(r1, textvariable=aimodel, values=[], width=24); aimbox.pack(side="left", padx=(SP2, 0))
    r2 = q1row(); r2.pack(fill="x", pady=(SP2, 2))
    keyrow = ttk.Frame(r2, style="Subtle.TFrame"); keyrow.pack(side="left")
    q1lab(keyrow, "2  Key").pack(side="left"); ttk.Entry(keyrow, textvariable=aikey, width=24, show="•").pack(side="left", padx=(SP2, SP2))
    ttk.Button(keyrow, text="Paste", command=lambda: act["ai_paste"]()).pack(side="left", padx=(0, SP2))
    agetbtn = ttk.Button(r2, text="Get a key…", command=lambda: act["ai_getkey"]()); agetbtn.pack(side="left")
    abtn = ttk.Button(r2, text="Connect", style="Accent.TButton", command=lambda: act["ai_connect"]()); abtn.pack(side="left", padx=(SP2, SP4))
    addrrow = ttk.Frame(r2, style="Subtle.TFrame"); q1lab(addrrow, "Address").pack(side="left"); ttk.Entry(addrrow, textvariable=aiaddr, width=28).pack(side="left", padx=(SP2, 0))
    st_.configure("Soft.TCheckbutton", background=SUB); st_.map("Soft.TCheckbutton", background=[("active", SUB)])
    ttk.Checkbutton(q1, text="Remember the key on this computer (encrypted by Windows)", variable=aikeep, style="Soft.TCheckbutton").pack(anchor="w", pady=(SP2, 0))
    autowrap(ttk.Label(q1, textvariable=aiguide, style="Soft.TLabel", background=SUB), q1, used=px(28), most=900).pack(anchor="w", pady=(SP2, 0))
    # the place to type, at the bottom of the card
    typ = ttk.Frame(amain)
    tin = ttk.Frame(typ, style="Field.TFrame", padding=(px(6), px(5)))
    aplus = ttk.Button(tin, text="+  Attach", style="Ghost.TButton", cursor="hand2", command=lambda: act["ai_plus"]()); aplus.pack(side="left", anchor="n", pady=px(2))
    ainput = tk.Text(tin, height=2, width=10, wrap="word", bg=CARD, fg=INK, insertbackground=INK, font=font, relief="flat", borderwidth=0, highlightthickness=0, padx=SP2, pady=px(5), undo=True, selectbackground=SELECT, selectforeground=INK); ainput.pack(side="left", fill="both", expand=True)
    asend = ttk.Button(typ, text="Send ↗", style="Accent.TButton", cursor="hand2", command=lambda: act["ai_send"]()); asend.pack(side="right", fill="y", padx=(SP2, 0)); tin.pack(side="left", fill="both", expand=True)
    AHINT = "Enter sends · Shift+Enter makes a new line · Attach adds any file"; aatt = tk.StringVar(value=AHINT)
    ex = ttk.Frame(amain)
    ttk.Label(ex, text="Try:", style="Muted.TLabel").pack(side="left", padx=(0, SP2))
    for lab_, txt_ in (("Recommend graphs", "What can I draw from the loaded files? Recommend one graph for each."), ("Convert a file…", None),
                       ("Label a peak", "On graph 1 label the peak at 29.4 as A."), ("Workbook for Origin", "Write the workbook for Origin."), ("Draw and save", "Draw the ticked graphs and save everything in "),
                       ("Explain last problem", "Explain the last problem in plain words and tell me what to do.")):
        ttk.Button(ex, text=lab_, style="Small.TButton", command=(lambda txt_=txt_: act["ai_example"](txt_)) if txt_ else (lambda: act["ai_plus"]())).pack(side="left", padx=(0, SP1))
    # the action queue: every step the assistant carried out for your last request, and whether it was done
    queue = ttk.Frame(amain, style="Soft.TFrame", padding=(px(14), px(10)))
    qh = ttk.Frame(queue, style="Subtle.TFrame"); qh.pack(fill="x")
    kicker(qh, "Action queue", background=SUB).pack(side="left"); qbadge = ttk.Label(qh, text="empty", style="Soft.Idle.Pill.TLabel"); qbadge.pack(side="right")
    qbody = ttk.Frame(queue, style="Subtle.TFrame"); qbody.pack(fill="x", pady=(SP1, 0)); qsteps = []
    def queue_show():
        try:
            for w_ in qbody.winfo_children(): w_.destroy()
            ok_n = sum(1 for o_, _ in qsteps if o_); bad_n = len(qsteps) - ok_n
            if abusy[0]: qbadge.config(text="working…", style="Soft.Warn.Pill.TLabel")
            elif bad_n: qbadge.config(text=f"{bad_n} not done", style="Soft.Bad.Pill.TLabel")
            elif ok_n: qbadge.config(text=f"{ok_n} done", style="Soft.Ok.Pill.TLabel")
            else: qbadge.config(text="empty", style="Soft.Idle.Pill.TLabel")
            if not qsteps: ttk.Label(qbody, text="The steps the assistant carries out for you appear here, each with its result.", style="Muted.TLabel", background=SUB).pack(anchor="w"); return
            if len(qsteps) > 4: ttk.Label(qbody, text=f"… {len(qsteps) - 4} earlier step(s) are in the conversation above", style="Muted.TLabel", background=SUB).pack(anchor="w")
            for o_, t_ in qsteps[-4:]:
                r_ = ttk.Frame(qbody, style="Subtle.TFrame"); r_.pack(fill="x", pady=(px(3), 0))
                ic_ = th.icon(o_)
                if ic_ is not None: ttk.Label(r_, image=ic_, background=SUB).pack(side="left", anchor="n", pady=(px(1), 0))
                else: ttk.Label(r_, text="\u2713" if o_ else "\u2715", background=SUB, foreground=_T["ok_text"] if o_ else _T["bad_text"]).pack(side="left", anchor="n")
                ttk.Label(r_, text=re.sub(r"\s+", " ", t_)[:150], style="Soft.TLabel", background=SUB, foreground=_T["text2"]).pack(side="left", padx=(SP2, 0))
        except Exception: pass
    def did(text, ok=True):
        """One step of the assistant: written into the conversation and into the action queue."""
        qsteps.append((bool(ok), str(text))); say("app", text); root.after(0, queue_show)
    queue_show()
    # the conversation: one bubble per message, in a part that scrolls
    chat_out, chat_in = scrolling(amain); chat_in.configure(padding=(0, 0, SP2, 0)); chat_notes = []; chat_bubbles = []
    def chat_gap(): return max(px(72), chat_in.winfo_width() - px(860))
    def chat_measure(event=None):
        """A bubble never gets wider than a comfortable line; yours are set in from the left, the assistant's from the right."""
        try:
            g_ = chat_gap(); w_ = max(px(220), min(px(780), chat_in.winfo_width() - px(40)))
            for b_, you_ in chat_bubbles:
                if b_.winfo_exists(): b_.pack_configure(padx=(g_, 0) if you_ else (0, g_))
            for l_ in chat_notes:
                if l_.winfo_exists(): l_.configure(wraplength=w_)
        except Exception: pass
    chat_w = [0, None]
    def chat_resized(event=None):
        """Dragging the window edge sends many size changes: the bubbles are set again once, shortly after the last one, and only when the width changed."""
        try:
            w_ = chat_in.winfo_width()
            if abs(w_ - chat_w[0]) < 4: return
            chat_w[0] = w_
            if chat_w[1] is not None: root.after_cancel(chat_w[1])
            chat_w[1] = root.after(140, lambda: (chat_w.__setitem__(1, None), chat_measure()))
        except Exception: pass
    chat_in.bind("<Configure>", chat_resized, add="+")
    def chat_insert(box, text, rich):
        """What the AI writes with **bold** and '- ' list marks is shown as bold and as a list, not as stars and dashes."""
        if not rich: box.insert("end", text); return
        for k_, ln in enumerate(str(text).split("\n")):
            if k_: box.insert("end", "\n")
            m_ = re.match(r"\s*(?:[-*•]|\d+[.)])\s+(?=\S)", ln); tags = ("bullet",) if m_ else ()
            if m_: ln = ("•  " if not m_.group(0).strip()[0].isdigit() else m_.group(0).strip() + "  ") + ln[m_.end():]
            for j_, part in enumerate(re.split(r"\*\*(.+?)\*\*", ln)):
                if part: box.insert("end", part, tags + (("bold",) if j_ % 2 else ()))
    def bubble(who, text):
        if who in ("app", "hint"):
            l_ = ttk.Label(chat_in, text=("•  " if who == "app" else "") + text, style="Soft.TLabel", justify="left", wraplength=max(px(220), min(px(780), chat_in.winfo_width() - px(40))) if chat_in.winfo_width() > 50 else px(520))
            l_.pack(anchor="w", padx=(px(14) if who == "app" else 0, 0), pady=(0, px(6) if who == "app" else px(12))); chat_notes.append(l_); chat_out.refit(); return
        kids_ = chat_in.winfo_children()
        if len(kids_) > 60:                                  # a long chat keeps its newest messages as bubbles; the older ones stay in the chat file
            for w_ in kids_[:len(kids_) - 50]:
                try: w_.destroy()
                except Exception: pass
            chat_bubbles[:] = [(b__, y__) for b__, y__ in chat_bubbles if b__.winfo_exists()]; chat_notes[:] = [l__ for l__ in chat_notes if l__.winfo_exists()]
        you_ = who == "you"; fill_ = _T["you_bg"] if you_ else _T["ai_bg"]; g_ = chat_gap() if chat_in.winfo_width() > 50 else px(72)
        b_ = ttk.Frame(chat_in, style="BubbleYou.TFrame" if you_ else "BubbleAI.TFrame", padding=(px(14), px(11))); b_.pack(fill="x", padx=(g_, 0) if you_ else (0, g_), pady=(px(6), px(8))); chat_bubbles.append((b_, you_))
        kicker(b_, "You" if you_ else "Assistant", background=fill_, foreground=_T["meta"]).pack(anchor="w")
        x_ = tk.Text(b_, height=1, width=10, wrap="word", bg=fill_, fg=INK, font=font, relief="flat", borderwidth=0, highlightthickness=0, padx=0, pady=0, spacing2=px(3), cursor="arrow", selectbackground=SELECT, selectforeground=INK, takefocus=False)
        x_.tag_configure("bold", font=bold); x_.tag_configure("bullet", lmargin1=SP2, lmargin2=SP2 + px(16), spacing1=px(3)); x_.pass_wheel = True
        chat_insert(x_, text, not you_)
        try:                                                 # about the right height at once, so the conversation does not jump while it is measured
            per_ = max(20, int((chat_in.winfo_width() - g_ - px(40)) / max(1, px(6.6)))) if chat_in.winfo_width() > 50 else 90
            x_.config(height=max(1, sum(-(-max(1, len(l_)) // per_) for l_ in text.split("\n"))))
        except Exception: pass
        x_.config(state="disabled"); x_.pack(fill="x", pady=(px(4), 0))
        def fit(event=None, x_=x_):
            """The bubble is exactly as tall as its text."""
            try:
                n_ = max(1, -(-int(x_.tk.call(x_._w, "count", "-update", "-ypixels", "1.0", "end")) // max(1, th.linespace)))
                if int(x_.cget("height")) != n_: x_.config(height=n_); chat_out.refit()
            except Exception: pass
        x_.bind("<Configure>", fit, add="+"); chat_out.refit()
    def chat_clear():
        for w_ in chat_in.winfo_children():
            try: w_.destroy()
            except Exception: pass
        chat_notes.clear(); chat_bubbles.clear(); qsteps.clear(); queue_show(); chat_out.refit()
    def chat_end():
        try: chat_out.canvas.update_idletasks(); chat_out.canvas.configure(scrollregion=(0, 0, chat_out.canvas.winfo_width(), max(chat_in.winfo_reqheight(), chat_out.canvas.winfo_height()))); chat_out.canvas.yview_moveto(1.0)
        except Exception: pass
    aprivacy = autowrap(ttk.Label(amain, text="Privacy: the assistant receives your message, instructions, graph summaries and only the first lines of a file you ask it to convert—not full data tables. "
                                  "The key is stored encrypted by Windows and is never sent anywhere but to the AI you chose.", style="Muted.TLabel"), amain, used=2 * PAD, most=900)
    # order on the card, from the bottom up: privacy, hint, the place to type, the examples, the action queue; the conversation takes the rest
    aprivacy.pack(side="bottom", anchor="w", pady=(px(2), 0)); ttk.Label(amain, textvariable=aatt, style="Muted.TLabel").pack(side="bottom", anchor="w", pady=(SP1, 0))
    typ.pack(side="bottom", fill="x", pady=(SP2, 0)); ex.pack(side="bottom", fill="x", pady=(SP3, 0)); queue.pack(side="bottom", fill="x", pady=(SP3, 0))
    rule(amain).pack(side="bottom", fill="x", pady=(SP2, 0)); chat_out.pack(fill="both", expand=True, pady=(SP4, 0))
    PLACEHOLDER = "Ask about this graph\u2026  for example: what can I draw from my files?"; aph = [False]
    def ai_placeholder(on):
        try:
            if on and not ainput.get("1.0", "end").strip(): ainput.insert("1.0", PLACEHOLDER); ainput.config(fg=PLACEHOLDER_INK); aph[0] = True
            elif not on and aph[0]: ainput.delete("1.0", "end"); ainput.config(fg=INK); aph[0] = False
        except Exception: pass
    def ai_text():
        try: return "" if aph[0] else (ainput.get("1.0", "end") or "").strip()
        except Exception: return ""
    def ai_example(txt_):
        ai_placeholder(False)
        try: ainput.delete("1.0", "end"); ainput.insert("1.0", txt_); ainput.focus_set(); ainput.mark_set("insert", "end")
        except Exception: pass
    def ai_linkbox(show=None):
        """The box for linking is only in the way once the AI is linked: it is shown when needed, or with 'Change AI…'."""
        try:
            vis = bool(q1.winfo_ismapped()); want = (not vis) if show is None else bool(show)
            if want and not vis: q1.pack(fill="x", pady=(SP3, 0), after=hd)
            elif not want and vis: q1.pack_forget()
            achange.config(text="Hide" if want else "Change AI…")
        except Exception: pass
    def say(who, text, keep=True):
        achat.append((who, str(text)))
        if who == "you": qsteps.clear()                      # a new request: the queue starts again
        def put():
            try:
                bubble(who, str(text).strip())
                if who == "you": queue_show()
                root.after(120, chat_end)
            except Exception: pass
        root.after(0, put)
    def on_ui(fn):
        """Run fn in the window's own thread and wait for its result (the assistant thinks in a second thread)."""
        ev = threading.Event(); box = {}
        def run():
            try: box["v"] = fn()
            except Exception as e: box["e"] = e
            finally: ev.set()
        root.after(0, run); ev.wait(1800)
        if "e" in box: raise box["e"]
        return box.get("v")
    def idle(limit=3600):
        """Wait until reading, analysing or drawing has finished."""
        t0 = _time.time()
        while _time.time() - t0 < limit:
            while busy[0] and _time.time() - t0 < limit: _time.sleep(0.1)
            on_ui(lambda: None)                              # let the window finish what it was doing
            if not busy[0]: break
    AISET = dict(analysis); AISET.update({"several_files": mode, "max_peak_labels": maxlab, "curve_weight_pt": cw, "axis_weight_pt": aw, "project_name": proj, "dated_subfolder": dated,
                                          "publication_files": pubv, "journal": jour})
    AIALLOWED = {"tga_curves": sp.TGA_CURVES, "tga_material": sp.TGA_MATERIAL, "fit_style": sp.FIT_STYLES, "xrd_labels": sp.XRD_LABELS, "xrd_background": sp.XRD_BG, "tga_mass": sp.TGA_MASS, "ftir_signal": sp.FTIR_SIGNAL,
                 "replicates": sp.REPLICATES, "stack_style": sp.STACK_STYLES, "orientation": sp.ORIENTATIONS, "per_fig": sp.PER_FIG, "label_text": sp.LABEL_TEXT, "pointers": sp.POINTERS,
                 "page_layout": sp.PAGE_LAYOUTS, "fit_colours": sp.FIT_COLOURS, "label_size": sp.LABEL_SIZES, "several_files": sp.MODES, "journal": list(sp.JOURNALS),
                 "xrd_store": [True, False], "dated_subfolder": [True, False], "publication_files": [True, False]}
    AINOTE = {"wavelength": list(sp.TUBES) + ["or a number in Å"], "inset": sp.INSETS + ["or an x range such as 27-37"], "xrd_phases": sp.XRD_PHASES, "max_peak_labels": ["all", "or a number"],
              "curve_weight_pt": ["a number, 1.5 or more"], "axis_weight_pt": ["a number, 1.5 or more"], "tga_ranges": ["text such as 400-500 CH, 600-800 CC"], "calo_ages": ["hours, such as 24, 72, 168"]}
    def ai_state():
        gl = []
        for n_, it in enumerate(items[:80], 1):
            g = {"n": n_, "name": sp.display_names([it])[0] if isinstance(it, sp.Item) else it.title.strip()[:90],
                 "type": "figure of several graphs" if isinstance(it, sp.Board) else "combined figure" if isinstance(it, sp.Combined) else "single graph", "kind": str(getattr(it, "kind", "")), "ticked": sp.key_of(it) in selkeys}
            if isinstance(it, sp.Item):
                g["file"] = os.path.basename(it.path); g["table"] = str(it.name)
                if it.sample: g["sample_name_typed"] = it.sample
                nl = sum(len(p.get("labels") or []) for p in (it.spec or {}).get("panels", []))
                if nl: g["labels"] = nl
                if it.warnings: g["note"] = str(it.warnings[0])[:160]
            gl.append(g)
        st_ = {"save_folder": out.get(), "graphs": gl, "graphs_in_list": len(items), "settings": {k: (v.get() if isinstance(v.get(), bool) else str(v.get())) for k, v in AISET.items()}}
        try:
            import paper_figures as pf_
            st_["figure_recipes"] = {k_: [f_.get("name") for f_ in pf_.load_recipe(k_).get("figures", [])] for k_ in pf_.recipes()}
            wbs_ = list(dict.fromkeys([it.path for it in singles if str(it.path).lower().endswith((".xlsx", ".xlsm", ".xls"))] + [p_ for p_ in apicked if str(p_).lower().endswith((".xlsx", ".xlsm", ".xls"))]))
            if wbs_: st_["workbooks"] = [{"path": w_, "recipe_that_fits": pf_.recipe_for(w_)} for w_ in wbs_[:6]]
        except Exception: pass
        if nograph: st_["files_that_gave_no_graph"] = list(nograph[-6:])
        if problems: st_["last_problem"] = {"when": problems[-1][0], "text": problems[-1][1][-900:]}
        return st_
    def ai_look(it):
        r = {"title": it.title.strip()[:120]}
        if not isinstance(it, sp.Item):
            r["made_of"] = [sp.display_names([m_])[0] + f" [{m_.kind}]" for m_ in getattr(it, "members", [])][:20]; r["why"] = str(getattr(it, "why", ""))[:300]; return r
        d = it.det; nums = d["nums"]; cols = []; sig = lambda v: float(f"{v:.5g}")
        for c in list(nums)[:40]:
            v = np.asarray(pd.to_numeric(pd.Series(np.asarray(nums[c])), errors="coerce"), float); f_ = v[np.isfinite(v)]
            cols.append({"column": str(c), "rows": int(len(f_)), "min": sig(f_.min()) if len(f_) else None, "max": sig(f_.max()) if len(f_) else None})
        r.update(kind=it.kind, columns=cols)
        try: r["text_columns"] = [str(c) for c in d["_df"].columns if c not in nums][:12]
        except Exception: pass
        if getattr(it, "custom", None): r["drawn_your_way"] = dict(it.custom)
        pans = (it.spec or {}).get("panels") or []
        if pans:
            p0 = pans[0]; r["x_axis"] = str((it.spec or {}).get("xname", "")); r["curves"] = [str(c.get("name") or "") for c in p0["curves"]][:12]
            if p0.get("labels"): r["labels_on_graph"] = [{"x": sig(float(l[0])), "text": str(l[1])} for l in p0["labels"]][:40]
            try:
                c0 = p0["curves"][0]; xx = np.asarray(c0["x"], float); yy = np.asarray(c0["y"], float); m_ = np.isfinite(xx) & np.isfinite(yy)
                if m_.sum() > 30 and c0.get("kind", "line") == "line": r["strongest_peaks"] = [{"x": sig(float(p["pos"])), "height": sig(float(p["height"]))} for p in sp.find_peaks(xx[m_], yy[m_], max_n=12)]
            except Exception: pass
        pl = d.get("_peaklist")
        if pl is not None and len(pl): r["phases_in_your_peak_list"] = sorted({f"{a_} = {b_}" for a_, b_ in zip(pl["Code"], pl["Phase"])})[:30]
        try: r["suggestions"] = [f"{k_ + 1}: {s_['title']} ({s_['why'][:110]})" for k_, s_ in enumerate(sp.suggest(it, options()))][:10]
        except Exception: pass
        if it.warnings: r["notes"] = [str(w)[:200] for w in it.warnings[:3]]
        return r
    def ai_pick(a, snap, many=False):
        v = a.get("graphs", a.get("graph")) if many else a.get("graph", a.get("graphs"))
        if isinstance(v, str) and not v.strip().lstrip("-").isdigit():
            w_ = v.strip().lower()
            if w_ == "all": return list(snap)
            if w_ in ("ticked", "selected"): return [it for it in snap if sp.key_of(it) in selkeys]
            if w_ == "none": return []
            raise ValueError(f"'{v}' is not a graph number")
        got = []
        for n_ in (v if isinstance(v, (list, tuple)) else [v]):
            try: i_ = int(n_)
            except Exception: raise ValueError("the number of the graph is missing")
            if not 1 <= i_ <= len(snap): raise ValueError(f"there is no graph {i_} in the list (it has {len(snap)})")
            if snap[i_ - 1] not in items: raise ValueError(f"graph {i_} is no longer in the list; read the new STATE")
            got.append(snap[i_ - 1])
        if not got and not many: raise ValueError("the number of the graph is missing")
        return got if many else got[0]
    def single(it):
        if not isinstance(it, sp.Item): raise ValueError("this is a combined figure; give the number of a single graph")
        return it
    def after_build(it):
        regroup(False); shown[0] = sp.key_of(it); refresh(); show(it); kind.set(it.kind); fill_own(it)
    def tick_these(chosen):
        keys = [sp.key_of(c) for c in chosen]; lb.selection_clear(0, "end")
        for i_, it in enumerate(items):
            if sp.key_of(it) in keys: lb.selection_set(i_)
        selkeys[:] = [sp.key_of(items[i_]) for i_ in cur()]; refresh()
    def match(val, allowed):
        if allowed is None: return val
        if isinstance(allowed[0], bool): return str(val).strip().lower() in ("true", "yes", "on", "1")
        t = str(val).strip().lower(); hit = [a_ for a_ in allowed if a_.lower() == t] or [a_ for a_ in allowed if a_.lower().startswith(t)] or [a_ for a_ in allowed if t and t in a_.lower()]
        if len(hit) != 1: raise ValueError(f"'{val}' is not one of: " + " | ".join(allowed))
        return hit[0]
    apicked = set()
    def your_file(p):
        """May the assistant open this file? Only a file you typed, chose in a file window, or loaded: never one it thought of itself."""
        nrm = lambda t: str(t).lower().replace("\\", "/"); ap = nrm(os.path.abspath(p)); typed = nrm(" \n ".join(said_all()))
        if ap in {nrm(os.path.abspath(q)) for q in list(apicked) + list(nograph) + [it.path for it in singles]}: return True
        whole = lambda t_: bool(t_) and re.search(r"(?<![\w/.-])" + re.escape(t_) + r"/?(?![\w/.-])", typed) is not None       # typed as a whole path or name
        if whole(ap) or whole(nrm(p)) or whole(nrm(os.path.basename(p))): return True
        d_ = os.path.dirname(ap)
        while len(d_) > 3:                                  # a folder you typed: the files in it
            if whole(d_): return True
            n_ = os.path.dirname(d_)
            if n_ == d_: break
            d_ = n_
        return False
    def said_all(): return list(asaid)
    def ai_do(a, snap, said):
        """Carry out one action of the assistant. Returns a short line with the result. Runs in the assistant's thread; everything that touches the window goes through on_ui."""
        do = str(a.get("do", "")).strip().lower()
        if do == "look": return json.dumps(on_ui(lambda: ai_look(ai_pick(a, snap))), ensure_ascii=False)[:6000]
        if do == "add_files":
            n0 = len(singles)
            if a.get("ask"): on_ui(on_add); idle(); return f"{len(singles) - n0} new graph(s); {len(singles)} table(s) loaded now"
            paths = []
            for p in (a.get("paths") or []):
                p = os.path.expandvars(os.path.expanduser(str(p).strip().strip('"')))
                if os.path.isdir(p): paths += sorted(os.path.join(p, f_) for f_ in os.listdir(p) if f_.lower().endswith((".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".dat", ".xy", ".xye", ".asc", ".xrdml", ".brml", ".raw", ".ras", ".uxd")) and not f_.startswith("~$"))
                elif os.path.isfile(p): paths.append(p)
                else: return f"file not found: {p}. Ask the user for the full path, or use \"ask\": true to open the file chooser"
            if not paths: return "no file was named"
            if not all(your_file(p) for p in paths): raise ValueError("I only open files the user named or chose. Ask the user for the file, or use \"ask\": true")
            on_ui(lambda: add_files(paths)); idle(); return f"{len(singles) - n0} new graph(s) from {len(paths)} file(s)"
        if do in ("read_file", "convert"):
            p = os.path.expandvars(os.path.expanduser(str(a.get("path", "")).strip().strip('"')))
            if not os.path.isfile(p): return f"file not found: {p}"
            if not your_file(p): raise ValueError("I only open files the user named or chose. Ask the user which file they mean")
            if do == "read_file": return sp.peek_file(p)[:7000]
            n0 = len(singles); outdir = os.path.join(out.get().strip() or default_results_folder(), "converted_tables")
            outp, df_, lines = sp.convert_by_recipe(p, a, outdir); log("\n".join(lines)); apicked.add(outp)
            on_ui(lambda: add_files([outp])); idle(); new = [it for it in singles[n0:]]
            if not new: return lines[0] + ". But the app still finds no graph in the converted table: " + lines[1].strip() + ". Check the recipe (rows, delimiter, decimal sign, transpose)"
            k_ = a.get("kind")
            if k_:
                def f():
                    kk = match(k_, [k for k in sp.KINDS])
                    for it in new:
                        if it.kind != kk and build(it, kk): after_build(it)
                try: on_ui(f)
                except Exception as e: lines.append(f"  (it could not be drawn as {k_}: {e})")
            learned = False
            try: learned = sp.learn_format(p, a)
            except Exception: pass
            if p in nograph: nograph.remove(p)
            return (lines[0] + " · " + lines[1].strip() + " · the app made: " + ", ".join(f"{sp.display_names([it])[0]} [{it.kind}]" for it in new[:6])
                    + (" · this layout is remembered: the next file like it is read without the AI" if learned else ""))
        if do == "sample":
            name = str(a.get("name", "")).strip()
            def f():
                ch = [single(it) for it in ai_pick(a, snap, True)]
                for it in ch: it.sample = name
                regroup(False); refresh(); return f"{len(ch)} graph(s) now belong to the sample '{name}'"
            return on_ui(f)
        if do == "kind":
            def f():
                it = single(ai_pick(a, snap)); k_ = match(a.get("kind"), [k for k in sp.KINDS])
                if not build(it, k_): raise ValueError("this table cannot be drawn as " + k_)
                after_build(it); return f"drawn as {it.kind}"
            return on_ui(f)
        if do == "suggestion":
            def f():
                it = single(ai_pick(a, snap)); sg = sp.suggest(it, options()); k_ = int(a.get("choose", 1))
                if not 1 <= k_ <= len(sg): raise ValueError(f"there are {len(sg)} suggestions for this table")
                it.custom = dict(sg[k_ - 1]["custom"])
                if not build(it, sg[k_ - 1]["kind"]): raise ValueError("this suggestion cannot be drawn for this table")
                after_build(it); return "drawn as: " + sg[k_ - 1]["title"]
            return on_ui(f)
        if do == "own":
            def f():
                it = single(ai_pick(a, snap)); cols = {str(c).lower(): str(c) for c in it.det["nums"]}; cu = dict(getattr(it, "custom", None) or {})
                def col(v):
                    if str(v).lower() not in cols: raise ValueError(f"there is no column '{v}'. Columns: " + ", ".join(cols.values()))
                    return cols[str(v).lower()]
                if a.get("x") is not None: cu["x"] = col(a["x"])
                if a.get("ys") is not None: cu["ys"] = [col(v) for v in (a["ys"] if isinstance(a["ys"], list) else [a["ys"]])]
                if a.get("style") is not None: cu["style"] = match(a["style"], sp.OWN_STYLES)
                if a.get("layout") is not None: cu["layout"] = match(a["layout"], sp.OWN_LAYOUTS)
                for k_ in ("xtitle", "ytitle"):
                    if a.get(k_) is not None: cu[k_] = str(a[k_]).strip()
                for k_ in ("xlog", "xrev"):
                    if a.get(k_) is not None: cu[k_] = bool(a[k_])
                it.custom = cu
                if not build(it, "XY"): raise ValueError("this table cannot be drawn that way")
                after_build(it); return "drawn your way: " + ", ".join(f"{k_}={v_}" for k_, v_ in cu.items() if v_ not in ("", False, None))
            return on_ui(f)
        if do == "labels":
            def f():
                it = single(ai_pick(a, snap)); new = []; pl = it.det.get("_peaklist")
                known = {str(t_[1]).strip().lower() for t_ in (it.given or [])} | {str(k_).lower() for k_ in (it.det.get("_idmap") or {})}
                if pl is not None and len(pl): known |= {str(v_).strip().lower() for v_ in list(pl["Code"]) + list(pl["Phase"])}
                for L in (a.get("labels") or []):
                    try: x_ = float(str(L.get("x")).replace(",", "."))
                    except Exception: raise ValueError("every label needs a position x (a number)")
                    t_ = str(L.get("text", "")).strip()
                    if not t_: raise ValueError("every label needs a text")
                    if not (ai.typed_by_user(t_, said) or t_.lower() in known):
                        raise ValueError(f"the label '{t_}' is not in what the user typed and not in their files. I do not put a label on a peak that the user did not give. Ask the user which label they want")
                    new.append((x_, t_, None))
                if "_given_file" not in it.det: it.det["_given_file"] = list(it.given or [])
                it.given = sorted((([] if a.get("replace") else list(it.given or [])) + new), key=lambda t_: t_[0])
                typed = [t_ for t_ in it.given if t_ not in it.det["_given_file"]]; it.det["_typed_labels"] = [f"{t_[1]} at {t_[0]:g}" for t_ in typed]
                if not build(it, it.kind): raise ValueError("the graph could not be drawn with these labels")
                after_build(it); on_g = sum(len(p.get("labels") or []) for p in it.spec["panels"])
                return f"{len(new)} label(s) set; the graph now shows {on_g} label(s)" + ("" if on_g >= len(it.given) else f" ({len(it.given) - on_g} did not sit on a peak or had no room; see the notes of the graph)")
            return on_ui(f)
        if do == "setting":
            nm = str(a.get("name", "")).strip().lower()
            if nm not in AISET: raise ValueError(f"there is no setting '{nm}'")
            val = match(a.get("value"), AIALLOWED.get(nm))
            if nm in ("curve_weight_pt", "axis_weight_pt"):
                val = float(str(val).replace(",", "."))
                if val < 1.5: raise ValueError("line weights stay at 1.5 pt or more")
                val = f"{val:g}"
            on_ui(lambda: (AISET[nm].set(val), remember()))
            if nm in analysis or nm in ("several_files", "max_peak_labels"): on_ui(on_rebuild); idle()
            return f"{nm} = {val}"
        if do == "tick": return on_ui(lambda: (tick_these(ai_pick(a, snap, True)), f"{len(selkeys)} graph(s) ticked")[1])
        if do == "figure":
            def f():
                tick_these([c for c in ai_pick(a, snap, True)][:9]); n0 = len(boards); on_board(); return "the figure is at the top of the list" if len(boards) > n0 else "the figure could not be made"
            return on_ui(f)
        if do == "folder":
            if a.get("ask"): on_ui(choose_folder); return "save folder: " + out.get()
            p = os.path.normpath(os.path.expandvars(os.path.expanduser(str(a.get("path", "")).strip().strip('"'))))
            if not p or p == ".": raise ValueError("no folder was named")
            os.makedirs(p, exist_ok=True); on_ui(lambda: (out.set(p), remember())); return "everything will be saved in " + p
        if do == "workbook":
            if not singles and not a.get("template"): return "nothing is loaded, so there is nothing to write"
            p = os.path.join(out.get().strip() or default_results_folder(), "XRD_workbook_template.xlsx" if a.get("template") else project_name() + "_graph_data.xlsx"); os.makedirs(os.path.dirname(p), exist_ok=True)
            lines = on_ui(lambda: sp.write_workbook([] if a.get("template") else singles, p, template=bool(a.get("template")))); log("\n".join(lines)); return lines[0] + (" · " + lines[1].strip() if len(lines) > 1 else "")
        if do == "draw":
            ch = ai_pick(a, snap, True) if a.get("graphs", a.get("graph")) is not None else [it for it in snap if sp.key_of(it) in selkeys]
            if not ch: return "no graph is ticked; say which graphs to draw"
            on_ui(lambda: (tick_these(ch), draw("selected"))); idle()
            return f"{len(ch)} graph(s) sent to Origin. " + str(status.get())
        if do == "paper_figures":
            import paper_figures as pf_
            wb = str(a.get("workbook") or "").strip()
            if not wb:
                c_ = list(dict.fromkeys([it.path for it in singles if str(it.path).lower().endswith((".xlsx", ".xlsm", ".xls"))] + [p_ for p_ in apicked if str(p_).lower().endswith((".xlsx", ".xlsm", ".xls"))]))
                fit_ = [w_ for w_ in c_ if pf_.recipe_for(w_)]; wb = (fit_ or c_ or [""])[0] if (len(fit_) == 1 or len(c_) == 1) else ""
                if not wb: return "NOT DONE: say which workbook (full path), or load it first; I do not guess a file"
            if not os.path.isfile(wb): return f"NOT DONE: there is no file {wb}"
            if not your_file(wb): return "NOT DONE: I only open a workbook the user typed, chose or loaded"
            if isinstance(a.get("spec"), dict): rec = {"figures": [a["spec"]]} if "panels" in a["spec"] else a["spec"]
            else:
                nm_ = a.get("recipe") or pf_.recipe_for(wb)
                if not nm_: return "NOT DONE: no recipe fits this workbook. Recipes: " + (", ".join(pf_.recipes()) or "none") + '. Or send the figure as "spec".'
                rec = pf_.load_recipe(nm_)
            box_ = [None]; on_ui(lambda: paper_figures_run(wb, rec, only=a.get("only") or None, then=lambda r_: box_.__setitem__(0, r_))); idle()
            r_ = box_[0]
            if not r_: return "NOT DONE: the figures were not made; see the details"
            return (r_["text"] + ". Saved in " + r_["folder"] + " as PDF and PNG (600 dpi): " + ", ".join(os.path.basename(f_) for f_ in r_["files"] if f_.endswith(".pdf")) + (". NOTES: " + " | ".join(r_["notes"][:8]) if r_["notes"] else ""))[:1800]
        if do == "show":
            def f():
                it = ai_pick(a, snap); shown[0] = sp.key_of(it); refresh(); present(it); return "in the preview: " + it.title.strip()[:80]
            return on_ui(f)
        if do == "remember":
            t_ = ai.learn(ahome, a.get("text")); return ("saved as a lasting rule: " + t_) if t_ else "this rule was already saved"
        raise ValueError(f"I do not know the action '{do}'")
    def ai_label():
        c = aconn[0]
        return f"{c['name']} \u00B7 Connected" if c else "Not linked yet."
    def ai_dot(state):
        """The pill in the header says what the link to the AI really is: connected, working, not connected, failed."""
        try:
            aipilltxt.set("\u25CF  " + {"on": "AI connected", "off": "AI not connected", "busy": "AI working\u2026", "bad": "AI not connected"}[state])
            aipill.config(style="Canvas." + {"on": "Ok", "off": "Idle", "busy": "Warn", "bad": "Bad"}[state] + ".Pill.TLabel")
        except Exception: pass
    def ai_save():
        c = aconn[0]
        if c:
            pr = c["provider"]
            if aimodel.get().strip(): amodels[pr] = aimodel.get().strip()
            if aiaddr.get().strip(): aaddrs[pr] = aiaddr.get().strip()
            if aikeep.get() and c.get("key") and not (ai.PROVIDERS[pr]["env"] and os.environ.get(ai.PROVIDERS[pr]["env"], "").strip() == c["key"]): akeys[pr] = c["key"]
        lost = ai.save_settings(ahome, {"choice": aiprov.get(), "keep_key": bool(aikeep.get()), "keys": dict(akeys) if aikeep.get() else {}, "models": amodels, "addresses": aaddrs})
        if lost and not awarned[0]: awarned[0] = True; say("app", "Windows could not store the key safely on this computer, so it is not stored: it works until you close the app, then paste it again.")
    def ai_layout():
        """Show only what the chosen AI needs: no key box for a local model, the address only where it is needed."""
        pr = ai.provider_of(aiprov.get()); aiguide.set(ai.GUIDES.get(pr, ai.GUIDES[None]))
        try:
            agetbtn.config(text="Get the program…" if pr == "ollama" else "Get a key…", state="disabled" if pr == "other" else "normal")
            if pr == "ollama": keyrow.pack_forget()
            elif not keyrow.winfo_ismapped(): keyrow.pack(side="left", before=agetbtn)
            if pr in ("ollama", "other") or aiaddr.get().strip(): addrrow.pack(side="left")
            else: addrrow.pack_forget()
        except Exception: pass
    def ai_busy_ui(on):
        """Keep the prompt controls in sync with the assistant worker thread."""
        state = "disabled" if on else "normal"
        try:
            asend.config(state=state, text="Working\u2026" if on else "Send \u2197"); queue_show()
            aplus.config(state=state)
            for child in ex.winfo_children():
                if isinstance(child, ttk.Button): child.config(state=state)
        except Exception: pass
    def card_text(it):
        """Name and one line of facts for the card of a graph: kind, what is plotted, how many points."""
        try:
            if isinstance(it, sp.Board): return it.title.strip(), f"Panel figure \u00B7 {len(it.members)} graph(s) \u00B7 {it.width_mm:g} mm wide"
            if isinstance(it, sp.Combined): return it.title.strip(), f"{it.kind} \u00B7 combined figure \u00B7 {len(it.members)} graph(s)"
            d_ = it.det; nm_ = os.path.basename(it.path) or it.file; shown_ = sp.display_names([it])[0]
            if it.name and it.name not in (it.file, "Sheet1"): nm_ += "  \u00B7  " + str(it.name)
            parts = [str(it.kind)]; x_ = d_.get("x") or d_.get("x_temp"); ys_ = [str(y_) for y_ in (d_.get("ys") or ([d_["mass"]] if d_.get("mass") else []))]
            if x_ and ys_: parts.append(f"{str(x_)[:22]} vs {ys_[0][:22]}" + (f" +{len(ys_) - 1}" if len(ys_) > 1 else ""))
            try: parts.append(f"{len(d_['_df']):,} points")
            except Exception: pass
            if shown_ and shown_ != it.file: parts.append("sample " + str(shown_)[:24])
            return nm_, " \u00B7 ".join(parts)
        except Exception: return str(getattr(it, "title", "Graph")).strip(), str(getattr(it, "kind", ""))
    def card_pick(k):
        """A click on a card: that graph goes into the live preview and becomes what the assistant works on."""
        if busy[0]: return
        it = next((i_ for i_ in items if sp.key_of(i_) == k), None)
        if it is None: return
        with slow.step("a click on a card"):
            shown[0] = k; refresh(); present(it)
    def card_tick(k):
        """A click on the badge: the graph is ticked (drawn by 'Draw ticked') or not."""
        if busy[0]: return "break"
        if k in selkeys: selkeys.remove(k)
        else: selkeys.append(k)
        refresh(); return "break"
    cards = {"keys": None, "w": {}}; act["cards"] = lambda: assistant_refresh_context()
    def assistant_refresh_context():
        """The cards of the loaded graphs in the Focused Copilot view follow the list: which is ticked, which is in the preview.
        The cards are made once; a click only changes a badge and a frame. They are made again only when graphs come or go."""
        try:
            if not on_view(t6): cards_stale[0] = True; return          # out of sight: the cards are brought up to date when the view is opened
            sig = [(sp.key_of(it), card_text(it)) for it in items[:80]]
            if sig != cards["keys"]:
                cards["keys"] = sig; cards["w"] = {}
                for w_ in cards_in.winfo_children(): w_.destroy()
                if not items:
                    dz = ttk.Frame(cards_in, style="Drop.TFrame", padding=(PAD, px(26)), cursor="hand2"); dz.pack(fill="both", expand=True)
                    parts_ = [ttk.Label(dz, text="+", font=(FF, -px(26)), foreground=_T["muted"], background=SUB), ttk.Label(dz, text="Add XRD, TGA, FTIR or CSV / XLSX files", style="Name.TLabel", background=SUB),
                              ttk.Label(dz, text="Click here to browse. Every sheet is checked and recognised for you. You can also drag files onto Run_Origin_Plot_App.bat.", style="Soft.TLabel", background=SUB, justify="center", wraplength=max(px(180), cards_in.winfo_width() - 2 * PAD - px(20)) if cards_in.winfo_width() > 50 else px(240))]
                    ttk.Frame(dz, style="Subtle.TFrame").pack(expand=True)
                    for l_ in parts_: l_.pack(pady=(0, SP1))
                    ttk.Frame(dz, style="Subtle.TFrame").pack(expand=True)
                    for w_ in [dz] + parts_: w_.bind("<Button-1>", lambda e: act["add"]())
                else:
                    for it, (k, (nm_, meta_)) in zip(items[:80], sig):
                        c_ = ttk.Frame(cards_in, style="Sub.TFrame", padding=px(12), cursor="hand2"); c_.pack(fill="x", pady=(0, SP2))
                        top_ = ttk.Frame(c_); top_.pack(fill="x")
                        bd_ = ttk.Label(top_, text="Not selected", style="Idle.Pill.TLabel", cursor="hand2"); bd_.pack(side="right", anchor="n", padx=(SP2, 0))
                        n_ = ttk.Label(top_, text=("\u2605 " if isinstance(it, sp.Board) else "") + nm_[:60], style="Name.TLabel", width=4); n_.pack(side="left", fill="x", expand=True)        # the name gives way, so the badge is never pushed out of the card
                        m_ = ttk.Label(c_, text=meta_[:110], style="Soft.TLabel"); m_.pack(anchor="w", pady=(px(4), 0))
                        for w_ in (c_, top_, n_, m_): w_.bind("<Button-1>", lambda e, k=k: card_pick(k))
                        bd_.bind("<Button-1>", lambda e, k=k: card_tick(k)); cards["w"][k] = (c_, bd_, [None, None])
                    if len(items) > 80: ttk.Label(cards_in, text=f"\u2026 and {len(items) - 80} more in the Scientific Workbench view", style="Muted.TLabel").pack(anchor="w")
                cards_out.refit()
            for k, (c_, bd_, was) in cards["w"].items():
                now_ = [k == shown[0], k in selkeys]
                if now_[0] != was[0]: c_.configure(style="SubSel.TFrame" if now_[0] else "Sub.TFrame")
                if now_[1] != was[1]: bd_.configure(text="Ready" if now_[1] else "Not selected", style="Ok.Pill.TLabel" if now_[1] else "Idle.Pill.TLabel")
                was[:] = now_
            selected = shown_item(); n_t = len([1 for it in items if sp.key_of(it) in selkeys])
            if selected is not None: assistant_action.set(f"{n_t} of {len(items)} ticked for drawing. Click a card to preview it, its badge to tick or untick it.")
            elif items: assistant_action.set("Click a card to preview it; click its badge to tick it for drawing.")
            else: assistant_action.set("Add a file to get started.")
        except Exception: log("!! I could not update the list of graphs:\n" + traceback.format_exc())
    def assistant_show(it):
        """Render the current graph in the Assistant rail when a preview is available."""
        try:
            acontext_file.set(it.title.strip()[:70] or "Selected graph"); live["key"] = sp.key_of(it)
            if assistant_canvas is None or assistant_fig is None or (it.spec is None and not isinstance(it, sp.Board)): return
            s_ = style(); assistant_fig.clear()
            if isinstance(it, sp.Board): sp.board_figure(it, assistant_fig, s_.curve, s_.axis)
            else: sp.preview_figure(it.spec, assistant_fig, s_.curve, s_.axis, keep_aspect=True)
            try:                                             # a small picture: pull the axes in until titles and axis labels are inside it (measured without drawing)
                from matplotlib.transforms import Bbox
                assistant_fig.draw_without_rendering(); W_, H_ = assistant_fig.get_size_inches(); bb = assistant_fig.get_tightbbox(assistant_fig.canvas.get_renderer()); m_ = 0.06
                if bb.x0 < m_ or bb.y0 < m_ or bb.x1 > W_ - m_ or bb.y1 > H_ - m_:
                    k_ = min((W_ - 2 * m_) / max(bb.width, 0.1), (H_ - 2 * m_) / max(bb.height, 0.1), 1.0) * 0.97
                    ox_, oy_ = (W_ - bb.width * k_) / 2, (H_ - bb.height * k_) / 2
                    for ax_ in assistant_fig.axes:
                        p_ = ax_.get_position(); x0, y0, x1, y1 = p_.x0 * W_, p_.y0 * H_, p_.x1 * W_, p_.y1 * H_
                        ax_.set_position(Bbox([[((x0 - bb.x0) * k_ + ox_) / W_, ((y0 - bb.y0) * k_ + oy_) / H_], [((x1 - bb.x0) * k_ + ox_) / W_, ((y1 - bb.y0) * k_ + oy_) / H_]]))
            except Exception: pass
            assistant_canvas.draw_idle()
        except Exception: log("!! I could not update the Assistant preview:\n" + traceback.format_exc())
    def ai_choice(event=None):
        """Another AI was chosen in the list: its saved key and model come back, and the link is made at once when there is a key."""
        pr = ai.provider_of(aiprov.get()); aconn[0] = None; ai_dot("off"); aistat.set("Not linked yet.")
        aquiet[0] = True
        try:
            aikey.set((akeys.get(pr, "") or (os.environ.get(ai.PROVIDERS[pr]["env"], "") if ai.PROVIDERS[pr]["env"] else "")) if pr else aikey.get())
            aiaddr.set(aaddrs.get(pr, "") if pr else ""); aimodel.set(amodels.get(pr, "") if pr else "")
            try: aimbox["values"] = []
            except Exception: pass
        finally: aquiet[0] = False
        ai_layout()
        if pr == "ollama" or (pr and pr != "other" and aikey.get().strip()) or (pr == "other" and aiaddr.get().strip() and aikey.get().strip()): ai_connect()
    def ai_key_typed(*a):
        """A key was pasted or typed: link by itself a moment later, so nothing else has to be pressed."""
        if aquiet[0]: return
        if apending[0] is not None:
            try: root.after_cancel(apending[0])
            except Exception: pass
            apending[0] = None
        k_ = aikey.get().strip()
        if len(k_) < 20 or (aconn[0] and aconn[0].get("key") == k_): return
        def go():
            apending[0] = None
            if aikey.get().strip() == k_ and not abusy[0] and (ai.provider_of(aiprov.get()) != "other" or aiaddr.get().strip()): ai_connect()
        apending[0] = root.after(900, go)
    def ai_paste():
        try: k_ = str(root.clipboard_get()).strip()
        except Exception: k_ = ""
        if not k_ or len(k_) > 400 or " " in k_ or "\n" in k_: aistat.set("There is no key in the clipboard. Copy the key on the page of your AI first, then press Paste."); return
        aikey.set(k_)
    def ai_getkey():
        pr = ai.provider_of(aiprov.get())
        if pr is None: aistat.set("Choose your AI in the list first; then this button opens its page."); return
        url = ai.PROVIDERS[pr]["keypage"]
        if not url: return
        try:
            import webbrowser; webbrowser.open(url); aistat.set("The page is open in your browser. Copy the key there, come back and press Paste." if pr != "ollama" else "The page is open in your browser. Install the program, download a model, then press Connect.")
        except Exception: aistat.set("Open this page in your browser: " + url)
    def ai_connect(then=None):
        if abusy[0]: return
        try: conn = ai.detect(aikey.get(), aiaddr.get(), aiprov.get())
        except ai.AIError as e: aistat.set(str(e)); ai_dot("bad"); return
        abusy[0] = True; ai_busy_ui(True); aistat.set(f"Linking to {conn['name']} …"); ai_dot("busy"); atried.add((conn["provider"], conn["key"]))
        def work():
            try: ids = ai.models(conn); err = None
            except ai.AIError as e: ids = []; err = str(e)
            except Exception as e: ids = []; err = f"That did not work: {e}"
            def fin():
                abusy[0] = False; ai_busy_ui(False)
                if err: aconn[0] = None; aistat.set("Not linked."); ai_dot("bad"); say("app", err); ai_linkbox(True); return
                aconn[0] = conn; ai_linkbox(False)
                try: aimbox["values"] = ids
                except Exception: pass
                want = aimodel.get().strip() or amodels.get(conn["provider"], "")
                aimodel.set(want if (want in ids or not ids) else ids[0])
                aistat.set(ai_label()); ai_dot("on"); ai_save()
                if not aimodel.get().strip(): say("app", "This service gave no list of models. Type the name of the model in the box 'Model'.")
                elif not then and not any(w_ == "app" and t_.startswith("Linked to " + conn["name"]) for w_, t_ in achat): say("app", f"Linked to {conn['name']}, model {aimodel.get().strip()}. Type what you want in the box above, or press + to add files.")
                if then: then()
            root.after(0, fin)
        threading.Thread(target=work, daemon=True).start()
    def ai_tab(event=None):
        """The tab is opened and a key is saved: link by itself (once), so you can type straight away."""
        try:
            if str(nb.select()) != str(t6): return
        except Exception: return
        try: root.after(50, ainput.focus_set)
        except Exception: pass
        if aconn[0] is not None or abusy[0]: return
        pr = ai.provider_of(aiprov.get()); k_ = aikey.get().strip()
        if (k_ or (pr == "ollama" and "ollama" in amodels)) and (pr, k_) not in atried and (ai.whose_key(k_) if pr is None else pr) is not None:
            atried.add((pr, k_)); ai_connect()
    from tkinter import messagebox
    # ------------------------------------------------------------------ fixed commands (no model needed): assistant_parser -> assistant_actions
    def cmd_folder():
        p = os.path.join(run_folder(), "Assistant_figures"); os.makedirs(p, exist_ok=True); last_folder[0] = p; return p
    def cmd_items(kind): return [it for it in items if isinstance(it, sp.Item) and it.kind == kind]
    def cmd_hashes(its):
        import hashlib
        out_ = []
        for it in its:
            try:
                with open(it.path, "rb") as f_: out_.append({"file": os.path.basename(it.path), "sha256": hashlib.sha256(f_.read()).hexdigest()})
            except OSError: pass
        return out_
    def cmd_recipe():
        try: return {"learned_formats": os.path.join(here, "learned_formats.json"), "present": os.path.isfile(os.path.join(here, "learned_formats.json"))}
        except Exception: return {}
    def cmd_tga(with_dtg=True, intervals=None, annotate=False):
        import paper_figures as pf_
        its = cmd_items("TGA")
        if not its: raise ValueError("no TGA table is loaded: add a TGA file first")
        folder = cmd_folder(); lines = []; o = options()
        o["tga_curves"] = sp.TGA_CURVES[0] if with_dtg else sp.TGA_CURVES[1]
        for it in its:
            r = sp.analyze_tga_steps(it, intervals, o) if (intervals or annotate) else None
            if r is None: it.build(o, "TGA")
            base = os.path.join(folder, re.sub(r'[\\/:*?"<>|]+', "_", it.file + "_TGA"))
            facts = {"what": "TGA graph, TG left axis" + (", DTG right axis (natural sign)" if with_dtg else ""), "inputs": cmd_hashes([it]), "active_recipe": cmd_recipe(), "temperature_intervals": (r or {}).get("intervals") or [], "tga_curves": o["tga_curves"], "peak_labels": [{"x": float(x_), "text": t_} for x_, t_, _y in ((it.spec["panels"][0].get("y2") or {}).get("labels") or it.spec["panels"][0].get("labels") or [])]}
            pf_.save_spec_figure(it.spec, base, facts=facts, app_version=sp.PROVENANCE_VERSION)
            if r: lines.append(f"{it.file}: " + "; ".join(f"{i['from']:g}–{i['to']:g} °C: {i['mass_loss_pct']:.2f} %" for i in r["intervals"]) + f"; total {r['total_mass_loss_pct']:.2f} %")
            else: lines.append(f"{it.file}: drawn")
        return "TGA figure(s) saved in " + folder + "\n" + "\n".join(lines)
    def cmd_analyze_tga(intervals=None):
        its = cmd_items("TGA")
        if not its: raise ValueError("no TGA table is loaded: add a TGA file first")
        o = options(); folder = cmd_folder(); lines = []
        for it in its:
            r = sp.analyze_tga_steps(it, intervals, o)
            import paper_figures as pf_
            pf_.write_provenance(os.path.join(folder, re.sub(r'[\\/:*?"<>|]+', "_", it.file + "_TGA_steps")), {"what": "TGA mass loss in temperature intervals", "inputs": cmd_hashes([it]), "temperature_intervals": r["intervals"], "total_mass_loss_pct": r["total_mass_loss_pct"], "residual_mass_pct": r["residual_mass_pct"], "confirmed_assistant_actions": list(pf_.CONFIRMED_ACTIONS)}, sp.PROVENANCE_VERSION)
            lines.append(f"{it.file}: " + "; ".join(f"{i['from']:g}–{i['to']:g} °C: {i['mass_loss_pct']:.2f} %" for i in r["intervals"]) + f"; total {r['total_mass_loss_pct']:.2f} %, residue {r['residual_mass_pct']:.2f} %")
        return "\n".join(lines)
    def cmd_stack(offset_mode="auto_percent", offset_value=None, palette=None):
        import paper_figures as pf_
        its = cmd_items("XRD")
        if not its: raise ValueError("no XRD pattern is loaded: add the XRD files first")
        traces = []
        for it in its:
            if it.spec is None: it.build(options())
            c = next((c_ for p_ in it.spec["panels"] for c_ in p_["curves"] if c_.get("kind", "line") == "line"), None)
            if c is not None: traces.append((sp.display_names([it])[0], c["x"], c["y"]))
        if not traces: raise ValueError("the loaded XRD tables gave no curve to stack")
        base = os.path.join(cmd_folder(), "XRD_stacked"); files = pf_.stacked_figure(traces, base, offset_mode, offset_value, None, (), facts={"inputs": cmd_hashes(its), "active_recipe": cmd_recipe()}, app_version=sp.PROVENANCE_VERSION)
        return f"{len(traces)} patterns stacked: {files[0]}"
    def cmd_calorimetry(mass_g=None, exclusion_min=45.0, path=None, reaction_row=None, inputs=None, bar_at_h=None):
        """One file (mass_g, path) or several (inputs: dicts with path, mass_g, label, regime, alite). Several files also give C2/C3
        overlays, the C4 pair (heat flow with the first hours as inset, beside cumulative heat) and the C5 bar chart."""
        import calorimetry as cal
        if not inputs:
            if not path:
                path = filedialog.askopenfilename(title="The calorimetry (TAM) Excel file", filetypes=[("Excel workbook", "*.xlsx *.xlsm"), ("All files", "*.*")])
                if not path: return "No file chosen."
            inputs = [{"path": path, "mass_g": mass_g, "exclusion_min": exclusion_min, "reaction_row": reaction_row}]
        inputs = [dict(i_, exclusion_min=i_.get("exclusion_min", exclusion_min)) for i_ in inputs]
        if bar_at_h: inputs[0]["bar_at_h"] = bar_at_h
        folder = cmd_folder()
        def work(): return cal.run(inputs, folder, sp.PROVENANCE_VERSION, log)
        def done(res):
            if res is None: status.set("The calorimetry files were not processed. Press Show details to see why."); return
            tot = "; ".join(f"{s_.get('name', '')}: {s_['total_Jg']:.2f} J/g" for s_ in res["samples"])
            msg = f"Calorimetry processed ({tot}). Files in {folder}" + (("\n" + "\n".join(res["warnings"])) if res["warnings"] else "")
            say("app", msg); status.set(msg.splitlines()[0])
        background(work, done, "Processing the calorimetry file(s) …"); return "started"
    # ------------------------------------------------------------------ gallery graph types (gallery_graphs.py): answers the app needs, templates, assistant step
    figtype_answer = [None]                  # tests set this instead of typing into the question
    def ask_figtype_needs(its):
        """A gallery graph that waits for an answer (which row is t0, the sample mass): ask it; nothing is assumed."""
        from tkinter import simpledialog
        for it in its:
            nd = it.det.get("_need") if isinstance(it, sp.Item) else None
            if not nd: continue
            key, q = nd
            if key == "calo_mass":                                 # a TAM export in W: the sample mass, as the calorimetry skill asks
                v = figtype_answer[0] if figtype_answer[0] is not None else simpledialog.askfloat("Calorimetry: sample mass", q, parent=root, minvalue=1e-6)
                if not v: log(f"   {it.title.strip()}: no sample mass given; the heat flow stays in the file's unit and no cumulative heat is calculated"); continue
                it.det["calo_mass"] = float(v)
                if build(it, it.kind): log(f"   {it.title.strip()}: sample mass {float(v):g} g (your answer)"); after_build(it)
                continue
            if figtype_answer[0] is not None: v = figtype_answer[0]
            elif key == "t0_row": v = simpledialog.askinteger("Gallery graph", q + "\n\nRow number of t0 (1 = first data row):", parent=root, minvalue=1)
            else: v = simpledialog.askfloat("Gallery graph", q, parent=root, minvalue=0.0)
            if v is None: log(f"   {it.title.strip()}: no answer given; the graph waits ({q})"); continue
            it.det["_figtype_book"][1].options[key] = (int(v) - 1) if key == "t0_row" else float(v)
            if build(it, it.kind): log(f"   {it.title.strip()}: {key} = {v} (your answer)"); after_build(it)
    def figtype_apply(tid):
        """Draw the ticked graphs (or the shown one) as gallery graph type tid. Returns a short line for the log or the chat."""
        kind_ = next((k for k in sp.KINDS if sp.figtype_id(k) == tid), None)
        if not kind_: raise ValueError(f"unknown gallery graph type {tid}")
        pool = [items[i] for i in cur()] or [i for i in singles if sp.key_of(i) == shown[0]] or list(singles)
        done_, fail_ = [], []
        for it in pool:
            if not isinstance(it, sp.Item) or not str(it.path).lower().endswith((".xlsx", ".xlsm", ".csv")): continue
            if build(it, kind_): done_.append(it); after_build(it)
            else: fail_.append(it.title.strip())
        if not done_: raise ValueError(f"no loaded workbook could be drawn as {tid} {sp.TG.TYPES[tid][0]}" + (": " + "; ".join(fail_) if fail_ else " (add a workbook in that layout, or make one with File > Make a gallery graph template)"))
        ask_figtype_needs(done_)
        return f"{len(done_)} graph(s) drawn as {tid} {sp.TG.TYPES[tid][0]}: " + ", ".join(i.title.strip()[:40] for i in done_[:4])
    def on_figtype_template(tid=None, src=None):
        """Make a gallery graph template from a raw file (or from a template), then load it back."""
        import gallery_graphs as tg
        win = tk.Toplevel(root)
        try: win.title("Make a gallery graph template"); win.transient(root); win.configure(bg=CARD)
        except Exception: pass
        fr = ttk.Frame(win, padding=px(14)); fr.pack(fill="both", expand=True)
        ttk.Label(fr, text="Make a gallery graph template", style="Step.TLabel").pack(anchor="w")
        autowrap(ttk.Label(fr, text="The app writes your raw file into the layout of the chosen graph type: an Instructions sheet, the data sheet(s), a Labels sheet "
                                    "(only the labels you type are drawn) and an Options sheet with the defaults. The template is then loaded so you see the graph.", style="Soft.TLabel"), fr, most=560).pack(anchor="w", pady=(2, SP2))
        fv = tk.StringVar(value=src or ""); tv = tk.StringVar()
        names = [f"{k}  {v[0]}  -  {v[1]}" for k, v in tg.TYPES.items()]
        def pick():
            p_ = filedialog.askopenfilename(parent=win, title="The raw file", filetypes=[("Data files", "*.xlsx *.xlsm *.csv *.txt *.xrdml *.xy *.dat *.spa *.ngb-ds3"), ("All files", "*.*")])
            if p_: fv.set(p_); guess()
        def guess():
            try:
                b_ = tg.read_book(fv.get()); g_, why_ = tg.recognise(b_)
                if g_ and not tv.get(): tv.set(names[tg.ORDER.index(g_)]); hint.set(f"The file looks like {g_}: {why_}")
            except Exception: pass
        r1 = ttk.Frame(fr); r1.pack(fill="x", pady=SP1); ttk.Label(r1, text="Raw file").pack(side="left"); ttk.Entry(r1, textvariable=fv, width=48).pack(side="left", padx=SP1, fill="x", expand=True); ttk.Button(r1, text="Browse…", command=pick).pack(side="left")
        r2 = ttk.Frame(fr); r2.pack(fill="x", pady=SP1); ttk.Label(r2, text="Graph type").pack(side="left"); cb_ = ttk.Combobox(r2, textvariable=tv, values=names, state="readonly", width=70); cb_.pack(side="left", padx=SP1)
        hint = tk.StringVar(value=""); ttk.Label(fr, textvariable=hint, style="Soft.TLabel").pack(anchor="w")
        if tid: tv.set(names[tg.ORDER.index(tid)])
        elif src: guess()
        def go():
            if not fv.get() or not tv.get(): messagebox.showerror("Template", "Choose the raw file and the graph type.", parent=win); return
            t_ = tv.get().split()[0]; base_ = os.path.splitext(os.path.basename(fv.get()))[0]
            out_ = filedialog.asksaveasfilename(parent=win, title="Save the template as", initialdir=os.path.dirname(fv.get()), initialfile=f"{base_}_{tg.TYPES[t_][0]}_template.xlsx", defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")])
            if not out_: return
            mass = None
            for _ in range(2):
                try: path_, notes_ = tg.make_template(t_, fv.get(), out_, mass_g=mass); break
                except tg.NeedInput as e:
                    from tkinter import simpledialog
                    mass = figtype_answer[0] if figtype_answer[0] is not None else simpledialog.askfloat("Template", str(e), parent=win, minvalue=0.000001)
                    if not mass: return
                except Exception as e: messagebox.showerror("Template", str(e), parent=win); return
            else: return
            log(f"Gallery template {t_} written: {path_}" + ("".join("\n   " + n_ for n_ in notes_)))
            win.destroy(); add_files([path_]); status.set(f"Template {t_} written and loaded: {os.path.basename(path_)}")
        ttk.Button(fr, text="Write the template and load it", style="Accent.TButton", command=go).pack(anchor="e", pady=(SP2, 0))
        win.figtype = dict(file=fv, type=tv, go=go, guess=guess)
        return win
    act["figtype_template"] = lambda: on_figtype_template()
    # ------------------------------------------------------------------ XRD scan generator (XRD tools > Generate XRD scans)
    xgen_win = [None]
    def scipy_install(then, packages=("scipy", "tzdata"), what="SciPy", module=None):
        """Install SciPy (or PySide6 for the XRD Scan Generator window) once, in the background, then call then()."""
        import subprocess, importlib, importlib.util
        exe = sys.executable
        if os.path.basename(exe).lower() == "pythonw.exe" and os.path.isfile(os.path.join(os.path.dirname(exe), "python.exe")): exe = os.path.join(os.path.dirname(exe), "python.exe")
        def work():
            r = subprocess.run([exe, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-warn-script-location", *packages], capture_output=True, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0: raise RuntimeError((r.stderr or r.stdout or "pip failed")[-1500:])
            importlib.invalidate_caches()
            if what != "SciPy": return importlib.util.find_spec(module or packages[0]) is None      # the module name when it differs from the package name
            import xrd_generator as xg_; importlib.reload(xg_); return xg_.SCIPY_MISSING
        def done(res):
            if res is None or res: messagebox.showerror(what, f"{what} could not be installed. Press Show details to see why, or install it yourself:\n\n    py -m pip install {' '.join(packages)}", parent=root); return
            status.set(f"{what} is installed."); then()
        background(work, done, f"Installing {what} for the XRD generator (one-time download) …")
    xgen_procs = []                                          # XRD Scan Generator windows opened from here: closed when Origin Plot Studio closes
    def close_xgen():
        for p_ in list(xgen_procs):
            try:
                if p_.poll() is None: p_.terminate()
            except Exception: pass
        xgen_procs.clear()
    HOOKS["close_xgen"] = close_xgen
    xgen_qt = [os.environ.get("OPA_XGEN_TK") != "1"]        # the XRD Scan Generator window (PySide6); tests and computers without PySide6 use the built-in one
    def qt_generator(template=None, better=False, on_chosen=None):
        """Open the XRD Scan Generator window (the stand-alone app, xrd_scan_generator_app.py) as its own program. The scans you tick there
        and send back with 'Use the ticked scans in Origin Plot Studio' come to on_chosen(paths). True when the window was opened (or is
        being installed); False: use the built-in window."""
        import importlib.util, subprocess, tempfile, json
        if not xgen_qt[0] or not os.path.isfile(os.path.join(here, "xrd_scan_generator_app.py")): return False
        if importlib.util.find_spec("PySide6") is None:
            if messagebox.askyesno("XRD Scan Generator", "The XRD Scan Generator window needs the Python package PySide6, which is not installed on this computer.\n\n"
                                   "Install it now? (one-time download of about 200 MB)\n\nNo: use the simpler generator built into Origin Plot Studio.", parent=root):
                scipy_install(lambda: qt_generator(template, better, on_chosen), ("PySide6",), "PySide6"); return True
            messagebox.showinfo("XRD Scan Generator", "PySide6 was not installed, so the simpler generator built into Origin Plot Studio opens instead.\n\n"
                                "You can install it later from XRD tools > XRD Scan Generator (app), or yourself:  py -m pip install PySide6", parent=root)
            return False
        exe = sys.executable
        if os.name == "nt" and os.path.basename(exe).lower() == "python.exe" and os.path.isfile(os.path.join(os.path.dirname(exe), "pythonw.exe")): exe = os.path.join(os.path.dirname(exe), "pythonw.exe")
        fd_, rf = tempfile.mkstemp(suffix=".json", prefix="xrdgen_"); os.close(fd_); os.remove(rf)
        errf = rf[:-5] + "_errors.txt"
        args = [exe, os.path.join(here, "xrd_scan_generator_app.py")] + ([template] if template else []) + ["--return", rf, "--parent", str(os.getpid())] + (["--better"] if better else [])
        try:
            with open(errf, "w", encoding="utf-8") as ef: proc = subprocess.Popen(args, cwd=here, stdout=ef, stderr=ef)
        except Exception as e: log(f"!! XRD Scan Generator could not be started: {e}"); return False
        log("XRD Scan Generator opened" + (f" with {os.path.basename(template)}" if template else "") + (" (better versions of this scan offered)" if better else ""))
        status.set("The XRD Scan Generator is open: tick the scan(s) you like there and press 'Use the ticked scans in Origin Plot Studio'.")
        HOOKS["xgen_proc"] = proc; xgen_procs.append(proc)
        def poll():
            if proc.poll() is None: root.after(400, poll); return
            chosen = []
            try: chosen = [p_ for p_ in json.load(open(rf, encoding="utf-8")).get("chosen", []) if os.path.isfile(p_)]
            except Exception: pass
            err = ""
            try: err = open(errf, encoding="utf-8", errors="replace").read()
            except Exception: pass
            for f_ in (rf, errf):
                try: os.remove(f_)
                except Exception: pass
            if proc.returncode not in (0, None) and not chosen and "Traceback" in err:
                log("!! XRD Scan Generator stopped with an error:\n" + err[-2500:]); status.set("The XRD Scan Generator stopped with an error: press Show details."); return
            if not chosen: status.set("The XRD Scan Generator was closed without sending scans back."); log("   XRD Scan Generator closed: no scan sent back"); return
            log(f"   XRD Scan Generator: {len(chosen)} scan(s) sent back: " + ", ".join(os.path.basename(p_) for p_ in chosen))
            if on_chosen: on_chosen(chosen)
        root.after(400, poll); return True
    # ------------------------------------------------------------------ File > Modern window (step 1 of 4): workspace_qt.py, a Qt window over the same engine
    def modern_window():
        """Open the modern window with the graphs of Your graphs. Its own program (like the XRD Scan Generator), closed with this app."""
        import importlib.util, subprocess, json as _json, tempfile as _tf, time as _time
        if not os.path.isfile(os.path.join(here, "workspace_qt.py")):
            messagebox.showerror("Modern window", "workspace_qt.py is missing from the program folder: update the app (Help > Check for updates).", parent=root); return "missing"
        if importlib.util.find_spec("PySide6") is None:
            if messagebox.askyesno("Modern window", "The modern window uses the Python package PySide6 (Qt), the same as the XRD Scan Generator, and it is not installed.\n\n"
                                   "Install it now? (one-time download of about 200 MB)", parent=root):
                scipy_install(modern_window, ("PySide6",), "PySide6")
            return "installing"
        exe = sys.executable
        if os.name == "nt" and os.path.basename(exe).lower() == "python.exe" and os.path.isfile(os.path.join(os.path.dirname(exe), "pythonw.exe")): exe = os.path.join(os.path.dirname(exe), "pythonw.exe")
        tmp = _tf.gettempdir(); tag = f"{os.getpid()}_{int(_time.time())}"
        listf, errf, readyf = (os.path.join(tmp, f"modern_window_{tag}{e}") for e in (".json", ".txt", ".ready"))
        paths = list(dict.fromkeys(os.path.abspath(getattr(i, "path", "")) for i in singles if getattr(i, "path", "") and os.path.isfile(getattr(i, "path", ""))))
        with open(listf, "w", encoding="utf-8") as fh: _json.dump(paths, fh)
        args = [exe, os.path.join(here, "workspace_qt.py"), "--files", listf, "--parent", str(os.getpid()), "--ready-file", readyf]
        try:
            with open(errf, "w", encoding="utf-8") as ef: proc = subprocess.Popen(args, cwd=here, stdout=ef, stderr=ef)
        except Exception as e:
            log(f"!! Modern window could not be started: {e}"); messagebox.showerror("Modern window", f"The modern window could not be started:\n\n{e}", parent=root); return "failed"
        xgen_procs.append(proc); HOOKS["modern_proc"] = proc; HOOKS["modern_ready"] = False
        log(f"Modern window opening with {len(paths)} file(s) of Your graphs. Your graphs here are not changed.")
        status.set("Opening the modern window …")
        box = tk.Toplevel(root); box.title("Modern window"); box.transient(root); box.resizable(False, False)
        fr_ = ttk.Frame(box, padding=PAD); fr_.pack(fill="both", expand=True)
        boxv = tk.StringVar(value="Opening the modern window …\n\nThe first start can take up to half a minute.")
        ttk.Label(fr_, textvariable=boxv, wraplength=px(420), justify="left").pack(anchor="w")
        ttk.Button(fr_, text="Hide this message", command=box.destroy).pack(anchor="e", pady=(SP3, 0))
        HOOKS["modern_box"] = box; t0 = _time.time()
        def tail():
            try: return open(errf, encoding="utf-8", errors="replace").read()
            except Exception: return ""
        def poll():
            if os.path.exists(readyf):
                if box.winfo_exists(): box.destroy()
                status.set("The modern window is open."); log("   Modern window: open"); HOOKS["modern_ready"] = True
                try: os.remove(readyf)
                except OSError: pass
                root.after(1500, watch_end); return
            if proc.poll() is not None:
                if box.winfo_exists(): box.destroy()
                err = tail(); last = "\n".join(err.strip().splitlines()[-6:])
                log("!! The modern window ended before it opened" + (f":\n{err[-2500:]}" if err.strip() else " (no message)"))
                status.set("The modern window did not open: see the message.")
                messagebox.showerror("Modern window", "The modern window could not open." + (f"\n\n{last}" if last else "") + "\n\nPress Show details for the whole message.", parent=root)
                return
            if box.winfo_exists() and _time.time() - t0 > 45: boxv.set("The modern window is still starting. If no window has appeared, look in the taskbar.")
            root.after(500, poll)
        def watch_end():
            if proc.poll() is None: root.after(2000, watch_end); return
            err = tail()
            if proc.returncode not in (0, None) and "Traceback" in err: log("!! The modern window stopped with an error:\n" + err[-2500:]); status.set("The modern window stopped with an error: press Show details.")
            else: log("   Modern window closed")
            try:
                if root.state() == "iconic": root.deiconify()            # it was opened at start instead of this window: show this one again
            except Exception: pass
        root.after(500, poll); return "opening"
    def modern_window_safe():
        try: return modern_window()
        except Exception as e:
            log("!! Modern window:\n" + traceback.format_exc()); messagebox.showerror("Modern window", f"The modern window could not be opened:\n\n{e}", parent=root); return "failed"
    act["modern_window"] = modern_window_safe
    def on_xrd_generator(n_scans=None, template=None, pick_for=None, on_chosen=None):
        """The XRD scan generator. pick_for: a scan whose intensities are to be corrected: the window makes candidates (generated scans and the
        counting-longer correction), you compare them in the overlay and choose one; on_chosen(path) then continues with it."""
        import xrd_generator as xg
        if xg.SCIPY_MISSING:
            if messagebox.askyesno("XRD scan generator", "The XRD generator needs the Python package SciPy, which is not installed on this computer.\n\nInstall it now? (one-time download of about 40 MB)", parent=root):
                scipy_install(lambda: on_xrd_generator(n_scans, template))
            return
        if qt_generator(template or pick_for, better=bool(pick_for),
                        on_chosen=(lambda ps: (on_chosen(ps[0]), add_files(ps[1:]) if ps[1:] else None)) if (pick_for and on_chosen) else (lambda ps: add_files(ps))):
            return "qt"                                                  # the XRD Scan Generator window (the stand-alone app) is open
        if xgen_win[0] is not None and pick_for:
            try: xgen_win[0].xgen["close"]()
            except Exception: xgen_win[0] = None
            if xgen_win[0] is not None: return None
        if xgen_win[0] is not None:
            try:
                xgen_win[0].deiconify(); xgen_win[0].lift()
                if n_scans: xgen_win[0].set_n(n_scans)
                return
            except Exception: xgen_win[0] = None
        import threading as _th, queue as _q
        from matplotlib.figure import Figure as _Fig
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as _Canvas, NavigationToolbar2Tk as _Bar
        win = tk.Toplevel(root); xgen_win[0] = win
        try: win.title("Generate XRD scans from a template"); win.geometry(f"{px(1240)}x{px(780)}"); win.transient(root); win.configure(bg=CARD)
        except Exception: pass
        st = {"tpl": None, "worker": None, "stop": None, "q": _q.Queue(), "scans": [], "files": [], "phases": [("template", 1.0)], "user_counts": False, "user_out": False, "pick": pick_for}
        if pick_for:
            try: win.title(f"Choose a better scan for {os.path.basename(pick_for)}")
            except Exception: pass
        top = ttk.Frame(win, padding=(px(14), px(10))); top.pack(fill="both", expand=True)
        ttk.Label(top, text=(f"Choose a better scan for {os.path.basename(pick_for)}" if pick_for else "Generate XRD scans from a template"), style="Step.TLabel").pack(anchor="w")
        if pick_for:
            autowrap(ttk.Label(top, text="Make a few better versions of this scan, compare them in the graph (normalised, with your scan behind them), choose the one you "
                                         "like and go on with it. Each version is your scan counted longer: your measured counts are kept and the counts of the extra "
                                         "counting time are added as Poisson counts, so the 2θ grid, the points and every real peak stay yours. Your original file is not changed.",
                               style="Soft.TLabel", foreground=ACCENT), top, most=1180).pack(anchor="w")
        if not pick_for: autowrap(ttk.Label(top, text="Randomised scans with the template's peaks: new counting noise, background, sample displacement and peak widths; optionally a mixture of phases. "
                                     "The scans are saved as .xrdml and .csv with manifest.csv, and are added to Your graphs so you can go on from there. Generated scans are test data, not measurements.",
                           style="Soft.TLabel"), top, most=1180).pack(anchor="w", pady=(2, SP2))
        pane = ttk.Panedwindow(top, orient="horizontal"); pane.pack(fill="both", expand=True)
        lo_, left = scrolling(pane); right = ttk.Frame(pane); pane.add(lo_, weight=0); pane.add(right, weight=1)
        try: lo_.configure(width=px(500))
        except Exception: pass
        # ---- 1 template
        b1 = step(left, 1, "Template scan", "A measured .xrdml scan. Its peaks, peak widths and background are used.", first=True)
        tr = ttk.Frame(b1); tr.pack(fill="x")
        ttk.Button(tr, text="Choose an .xrdml file…", command=lambda: pick_template()).pack(side="left")
        loaded = [it.path for it in items if isinstance(it, sp.Item) and str(getattr(it, "path", "")).lower().endswith(".xrdml")]
        loaded = list(dict.fromkeys(loaded)); usev = tk.StringVar(value="")
        if loaded:
            cb = ttk.Combobox(tr, textvariable=usev, values=[os.path.basename(p_) for p_ in loaded], state="readonly", width=26); cb.pack(side="left", padx=(SP2, 0))
            usev.set("or use a loaded file ▾"); cb.bind("<<ComboboxSelected>>", lambda e: set_template(loaded[cb.current()]))
        infov = tk.StringVar(value="No template chosen yet."); autowrap(ttk.Label(b1, textvariable=infov), b1, most=440).pack(anchor="w", pady=(SP2, 0))
        smartv = tk.StringVar(value=""); smart = autowrap(ttk.Label(b1, textvariable=smartv, style="Soft.TLabel"), b1, most=440); smart.pack(anchor="w", pady=(SP1, 0))
        sb_ = ttk.Frame(b1); sb_.pack(anchor="w", pady=(SP1, 0))
        use_det = ttk.Button(sb_, text="Use the detected range", command=lambda: apply_counts(True)); use_def = ttk.Button(sb_, text="Use 8,000–10,000", command=lambda: apply_counts(False))
        # ---- 2 settings
        b2 = step(left, 2, "Generation settings", "Each scan gets random points and a random maximum inside these ranges.")
        f2 = form(b2, 150); d = xg.DEFAULTS
        V = {k: tk.StringVar(value=str(v)) for k, v in (("n", n_scans or d["n"]), ("p_lo", d["points"][0]), ("p_hi", d["points"][1]), ("c_lo", int(d["counts"][0])), ("c_hi", int(d["counts"][1])), ("seed", ""), ("out", ""))}
        def pair(a, b, unit):
            def mk(p):
                fr = ttk.Frame(p); ttk.Entry(fr, textvariable=V[a], width=9).pack(side="left"); ttk.Label(fr, text=" to ").pack(side="left"); ttk.Entry(fr, textvariable=V[b], width=9).pack(side="left"); ttk.Label(fr, text=" " + unit, style="Soft.TLabel").pack(side="left"); return fr
            return mk
        f2.row("Number of scans", lambda p: ttk.Entry(p, textvariable=V["n"], width=9))
        f2.row("Points per scan", pair("p_lo", "p_hi", "points"))
        f2.row("Maximum counts", pair("c_lo", "c_hi", "counts"), hint="The highest point of each scan, after Poisson noise, always lies in this range.")
        f2.row("Random seed", lambda p: ttk.Entry(p, textvariable=V["seed"], width=12), hint="Empty: different every time. A number: the same files every time.")
        f2.row("Output folder", lambda p: ttk.Entry(p, textvariable=V["out"]), extra=lambda p: ttk.Button(p, text="Browse…", command=lambda: pick_out()), hint="Existing files are never overwritten: the numbering continues.")
        prevv = tk.BooleanVar(value=False); addv = tk.BooleanVar(value=not pick_for); corrv = tk.BooleanVar(value=False)        # pick mode: also fully simulated scans
        f2.pack(fill="x")
        ttk.Checkbutton(b2, text="Also save preview.png of the first 4 scans", variable=prevv).pack(anchor="w")
        ttk.Checkbutton(b2, text="Add the new scans to Your graphs (up to 50)", variable=addv).pack(anchor="w")
        V["c_lo"].trace_add("write", lambda *a: st.__setitem__("user_counts", True)); V["c_hi"].trace_add("write", lambda *a: st.__setitem__("user_counts", True))
        V["out"].trace_add("write", lambda *a: st.__setitem__("user_out", True))
        # ---- 3 phases and advanced
        b3 = step(left, 3, "Phase mixtures and advanced options", "Reference peak lists: a text or CSV file with 2θ and relative intensity on each line.", fold="xgen_adv")
        plf, plb = listbox(b3, height=5); plf.pack(fill="x")
        wv = tk.StringVar(value="1.0")
        pr = ttk.Frame(b3); pr.pack(fill="x", pady=(SP1, 0))
        ttk.Button(pr, text="Add reference…", command=lambda: add_ref()).pack(side="left")
        ttk.Button(pr, text="Add template peaks", command=lambda: add_tpl()).pack(side="left", padx=SP1)
        ttk.Button(pr, text="Remove", command=lambda: rm_phase()).pack(side="left")
        wr = ttk.Frame(b3); wr.pack(fill="x", pady=(SP1, 0)); ttk.Label(wr, text="Weight of the selected phase").pack(side="left"); ttk.Entry(wr, textvariable=wv, width=8).pack(side="left", padx=SP1); ttk.Button(wr, text="Set", command=lambda: set_w()).pack(side="left")
        f3 = form(b3, 210); A = {k: tk.StringVar(value=str(d[k])) for k in ("intensity_jitter", "phase_jitter", "dropout", "prominence")}
        f3.row("Peak intensity jitter (σ)", lambda p: ttk.Entry(p, textvariable=A["intensity_jitter"], width=8), hint="0 keeps the relative peak strengths of the template.")
        f3.row("Phase amount jitter (σ)", lambda p: ttk.Entry(p, textvariable=A["phase_jitter"], width=8))
        f3.row("Weak-line dropout (fraction)", lambda p: ttk.Entry(p, textvariable=A["dropout"], width=8), hint="0 keeps every peak.")
        f3.row("Peak detection prominence (× noise σ)", lambda p: ttk.Entry(p, textvariable=A["prominence"], width=8), hint="Peaks must also exceed 3σ of the local noise.")
        f3.pack(fill="x", pady=(SP2, 0))
        # ---- 4 run
        b4 = step(left, 4, "Generate")
        rr = ttk.Frame(b4); rr.pack(fill="x")
        gob = ttk.Button(rr, text="Generate scans", style="Accent.TButton", command=lambda: go()); gob.pack(side="left")
        canb = ttk.Button(rr, text="Cancel", command=lambda: cancel(), state="disabled"); canb.pack(side="left", padx=SP2)
        openb = ttk.Button(rr, text="Open output folder", command=lambda: open_folder(V["out"].get().strip())); openb.pack(side="left")
        bar = ttk.Progressbar(b4, mode="determinate", maximum=1); bar.pack(fill="x", pady=(SP2, SP1))
        msgv = tk.StringVar(value="Choose a template to begin."); autowrap(ttk.Label(b4, textvariable=msgv), b4, most=440).pack(anchor="w")
        useb = None
        if pick_for:                                                     # choose one candidate and go on with it
            b5 = step(left, 5, "Choose the scan you like", "Tick one scan in the overlay list under the graph (compare them with the template), then go on with it.")
            ttk.Checkbutton(b5, text="Also add fully simulated scans (re-drawn from the detected peaks: new data, not your measurement)", variable=corrv).pack(anchor="w")
            useb = ttk.Button(b5, text="Use the selected scan and continue", style="Accent.TButton", command=lambda: use_selected(), state="disabled"); useb.pack(anchor="w", pady=(SP2, 0))
        # ---- right: graph with zoom / pan, list of scans for the overlay
        rt = ttk.Frame(right); rt.pack(fill="both", expand=True, padx=(SP2, 0))
        fig = _Fig(figsize=(7.4, 4.6), dpi=PREVIEW_DPI, facecolor="white"); cv = _Canvas(fig, master=rt)
        tb = _Bar(cv, rt, pack_toolbar=False); tb.update(); tb.pack(side="top", fill="x"); cv.get_tk_widget().pack(side="top", fill="both", expand=True)
        ax = fig.add_subplot(111)
        lr = ttk.Frame(rt); lr.pack(fill="x", pady=(SP1, 0))
        ttk.Label(lr, text="Overlay:").pack(side="left")
        slf, slb = listbox(lr, height=4, selectmode="extended"); slf.pack(side="left", fill="x", expand=True, padx=SP1)
        tplv = tk.BooleanVar(value=True); normv = tk.BooleanVar(value=bool(pick_for))
        oc = ttk.Frame(lr); oc.pack(side="left")
        ttk.Checkbutton(oc, text="with the template", variable=tplv, command=lambda: draw_scans()).pack(anchor="w")
        ttk.Checkbutton(oc, text="normalised", variable=normv, command=lambda: draw_scans()).pack(anchor="w")
        useb2 = None
        if pick_for:
            useb2 = ttk.Button(oc, text="Use the selected one", style="Accent.TButton", command=lambda: use_selected(), state="disabled"); useb2.pack(anchor="w", pady=(SP1, 0))
        slb.bind("<<ListboxSelect>>", lambda e: draw_scans())
        PAL = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000"]
        def plain(a):
            a.clear(); a.set_axis_on()
            for s_ in ("top", "right"): a.spines[s_].set_visible(False)
            a.set_xlabel("2θ (°)"); a.set_ylabel("Intensity (counts)"); tb.update()
        def labels_at_end(a, rows):
            lo, hi = a.get_ylim(); gap = (hi - lo) * 0.045; last = None
            for text, y, col in sorted(rows, key=lambda r: r[1]):
                y2 = y if last is None else max(y, last + gap); last = y2
                a.annotate(text, xy=(1.0, y2), xycoords=("axes fraction", "data"), xytext=(4, 0), textcoords="offset points", color=col, fontsize=8, va="center", annotation_clip=False)
        def empty(text):
            ax.clear(); ax.set_axis_off(); ax.text(0.5, 0.5, text, ha="center", va="center", color="#6B7280", transform=ax.transAxes); cv.draw_idle()
        empty("Choose a template to see it here")
        def draw_template():
            t = st["tpl"]; plain(ax)
            ax.plot(t.x, t.y, lw=0.6, color="#1E3A8A"); ax.plot(t.x, t.bg, lw=0.9, color="#F97316", ls="--")
            ax.plot(t.peaks[:, 0], t.peaks[:, 1] + np.interp(t.peaks[:, 0], t.x, t.bg), ls="none", marker="v", ms=4, color="#10B981")
            ax.set_xlim(t.x[0], t.x[-1]); ax.set_ylim(bottom=0); ax.set_title(f"{t.sample}: {len(t.peaks)} peaks used (green), background (orange)", fontsize=9, loc="left")
            labels_at_end(ax, [("background", float(t.bg[-1]), "#F97316")])
            fig.tight_layout(rect=(0, 0, 0.9, 1)); cv.draw_idle()
        def draw_scans():
            sel = [st["scans"][i] for i in slb.curselection() if i < len(st["scans"])]
            if not sel and st["scans"]: sel = st["scans"][:3]
            t = st["tpl"]
            if not sel:
                if t is not None: draw_template()
                return
            plain(ax); norm = normv.get(); rows = []
            if tplv.get() and t is not None:
                yt = t.y / (t.y.max() if norm else 1); ax.plot(t.x, yt, lw=1.1, color="#9CA3AF", alpha=0.8); rows.append(("template", float(np.median(yt[-80:])), "#6B7280"))
            for k_, sc in enumerate(sel[:10]):
                y = sc.counts / (sc.counts.max() if norm else 1); c = PAL[k_ % len(PAL)]; ax.plot(sc.x, y, lw=0.6, color=c); rows.append((sc.sid, float(np.median(y[-80:])), c))
            if norm: ax.set_ylabel("Intensity (normalised)")
            ax.set_xlim(min(s_.x[0] for s_ in sel), max(s_.x[-1] for s_ in sel)); ax.set_ylim(bottom=0); labels_at_end(ax, rows)
            fig.tight_layout(rect=(0, 0, 0.86, 1)); cv.draw_idle()
        # ---- actions
        def show_phases():
            plb.delete(0, "end")
            for name, w in st["phases"]: plb.insert("end", f"{'Template peaks' if name == 'template' else os.path.basename(name)}    weight {w:g}")
        show_phases()
        def add_ref():
            ps_ = filedialog.askopenfilenames(parent=win, title="Reference peak lists (2θ, intensity)", filetypes=[("Peak lists", "*.csv *.txt *.dat *.xy"), ("All files", "*.*")]) or []
            for p_ in ps_:
                try: xg.load_phase(p_)
                except xg.XrdError as e: messagebox.showerror("Reference peak list", str(e), parent=win); continue
                st["phases"].append((p_, 1.0))
            show_phases()
        def add_tpl():
            if not any(n_ == "template" for n_, _ in st["phases"]): st["phases"].insert(0, ("template", 1.0)); show_phases()
        def rm_phase():
            for i in sorted(plb.curselection(), reverse=True): del st["phases"][i]
            show_phases()
        def set_w():
            try: w = float(wv.get().replace(",", ".")); assert w > 0
            except Exception: messagebox.showerror("Weight", "The weight must be a number above 0.", parent=win); return
            for i in plb.curselection(): st["phases"][i] = (st["phases"][i][0], w)
            show_phases()
        def pick_template():
            p_ = filedialog.askopenfilename(parent=win, title="Template scan", filetypes=[("XRDML scans", "*.xrdml"), ("All files", "*.*")])
            if p_: set_template(p_)
        def pick_out():
            p_ = filedialog.askdirectory(parent=win, title="Output folder", initialdir=V["out"].get() or None)
            if p_: V["out"].set(p_)
        def apply_counts(detected):
            t = st["tpl"]
            lo, hi = (xg.suggest_counts(t.y.max())[:2] if detected and t is not None else xg.DEFAULTS["counts"])
            V["c_lo"].set(f"{lo:.0f}"); V["c_hi"].set(f"{hi:.0f}"); st["user_counts"] = False
        def set_template(p_):
            if st["worker"] is not None: return
            msgv.set(f"Reading {os.path.basename(p_)} …"); win.update_idletasks()
            try: prom = float(A["prominence"].get().replace(",", "."))
            except ValueError: prom = 1.0
            try: t = xg.load_template(p_, prom)
            except xg.XrdError as e: msgv.set("This file cannot be used as a template."); messagebox.showerror("Template", str(e), parent=win); return
            k_chk = "low" if t.y.max() < xg.USUAL_COUNTS[0] else "high" if t.y.max() > xg.USUAL_COUNTS[1] else "ok"
            if k_chk != "ok" and not st.get("pick") and not str(p_).lower().endswith("_corrected.xrdml") and ask_correct([(p_, k_chk, float(t.y.max()))], "template"):
                msgv.set("Correcting the template (fitting the peaks; a few seconds) \u2026"); gob.configure(state="disabled")
                def fixed_done(fixed):
                    gob.configure(state="normal")
                    if fixed: set_template(fixed[p_])
                    else: msgv.set("The template could not be corrected: see Show details in the main window.")
                background(lambda: correct_files([(p_, k_chk, float(t.y.max()))]), fixed_done, "Correcting the template's peak intensities \u2026"); return
            st["tpl"] = t; s_ = t.summary(); b = s_["bands"]
            infov.set(f"{s_['file']}\nSample ID: {s_['sample_id']}" + (f"   (name: {s_['name']})" if s_["name"] and s_["name"] != s_["sample_id"] else "") +
                      f"\n2θ {s_['range'][0]:.3f}–{s_['range'][1]:.3f}°,  {s_['points']:,} points,  maximum {s_['max_counts']:,.0f} counts"
                      f"\n{s_['peaks']} peaks above 3σ noise (tops below 5000: {b[0]}, 5000–8000: {b[1]}, above 8000: {b[2]})")
            lo, hi, why = xg.suggest_counts(s_["max_counts"]); smartv.set("Detected counts: " + why)
            V["c_lo"].set(f"{lo:.0f}"); V["c_hi"].set(f"{hi:.0f}"); st["user_counts"] = False                 # smart: the range follows the template's own counts
            use_det.pack(side="left"); use_def.pack(side="left", padx=SP1)
            if not st["user_out"] or not V["out"].get().strip():
                V["out"].set(os.path.join(out.get().strip() or default_results_folder(), "Generated_XRD", xg.safe_stem(t.sample))); st["user_out"] = False
            draw_template(); msgv.set(f"Template ready. Files will be called {xg.safe_stem(t.sample)}-001, -002, …")
            for o_, c_, v_ in scrollers:
                try: o_.refit()
                except Exception: pass
        def settings_():
            def num(v, cast, name):
                try: return cast(float(str(V[v].get()).replace(",", "").strip()) if cast is int else float(str(V[v].get()).replace(",", "").strip()))
                except ValueError: raise xg.XrdError(f"{name} must be a number.")
            seed_t = V["seed"].get().strip()
            try: seed = int(seed_t) if seed_t else None
            except ValueError: raise xg.XrdError("Random seed must be a whole number (or empty).")
            adv = {}
            for k in A:
                try: adv[k] = float(A[k].get().replace(",", "."))
                except ValueError: raise xg.XrdError(f"{k.replace('_', ' ').capitalize()} must be a number.")
            return xg.Settings(template=st["tpl"].path, out_dir=V["out"].get().strip(), n=num("n", int, "Number of scans"), points=(num("p_lo", int, "Points"), num("p_hi", int, "Points")),
                               counts=(num("c_lo", float, "Counts"), num("c_hi", float, "Counts")), seed=seed, phases=list(st["phases"]), preview=bool(prevv.get()), **adv)
        def go():
            if st["worker"] is not None: return
            if st["tpl"] is None: messagebox.showerror("XRD generator", "Choose a template .xrdml file first.", parent=win); return
            try:
                s_ = settings_(); errs = xg.check_settings(s_)
                if errs: raise xg.XrdError("\n".join("• " + e_ for e_ in errs))
                xg.check_output_folder(s_.out_dir)
            except xg.XrdError as e: messagebox.showerror("Check the settings", str(e), parent=win); return
            st["scans"] = []; st["files"] = []; slb.delete(0, "end"); bar.configure(maximum=s_.n, value=0); stop = _th.Event(); st["stop"] = stop
            gob.configure(state="disabled"); canb.configure(state="normal"); msgv.set(f"Generating {s_.n} scan(s) …"); q = st["q"]
            def work():
                try:
                    if not st.get("pick"):
                        r_ = xg.generate(s_, st["tpl"], progress=lambda d_, n_, sc: q.put(("scan", d_, n_, sc)), cancelled=stop.is_set, log=lambda m: q.put(("log", m)))
                        q.put(("done", r_)); return
                    import types as _ty                               # better versions of YOUR scan: counted longer, each its own target and random draw
                    os.makedirs(s_.out_dir, exist_ok=True); scans_, files_ = [], []
                    def one(i_, n_, r):
                        cp_ = r[0]; _t, cx_, cy_, _s, _n = xg.load_xrdml(cp_)
                        sc = _ty.SimpleNamespace(sid=os.path.splitext(os.path.basename(cp_))[0] + f" (counted {r[1]:.3g}\u00d7 longer)" if r[1] >= 1 else os.path.splitext(os.path.basename(cp_))[0] + " (shorter count)", x=cx_, counts=np.asarray(cy_), files=[cp_], meta={})
                        scans_.append(sc); files_.append(cp_); q.put(("scan", i_, n_ + (s_.n if corrv.get() else 0), sc))
                    xg.improve_candidates(st["pick"], s_.n, counts=s_.counts, out_dir=s_.out_dir, progress=one, cancelled=stop.is_set)
                    if corrv.get() and not stop.is_set():                # optional: fully simulated scans, on the scan's own number of points
                        import dataclasses as _dc
                        npts = len(st["tpl"].y); s2 = _dc.replace(s_, points=(npts, npts))
                        r2 = xg.generate(s2, st["tpl"], progress=lambda d_, n_, sc: q.put(("scan", len(scans_) + d_, len(scans_) + n_, sc)), cancelled=stop.is_set, log=lambda m: q.put(("log", m)))
                        scans_ += list(r2.scans)
                        files_ += list(r2.files)
                    q.put(("done", _ty.SimpleNamespace(scans=scans_, files=files_, out_dir=s_.out_dir, cancelled=stop.is_set(), preview=None)))
                except xg.XrdError as e: q.put(("error", str(e)))
                except Exception: q.put(("error", "An unexpected error stopped the generation:\n\n" + traceback.format_exc(limit=4)))
            st["worker"] = _th.Thread(target=work, daemon=True); st["worker"].start(); win.after(80, poll)
        def poll():
            q = st["q"]; drawn = False
            try:
                while True:
                    m = q.get_nowait()
                    if m[0] == "scan":
                        _, d_, n_, sc = m; st["scans"].append(sc); slb.insert("end", f"{sc.sid}   max {int(sc.counts.max()):,}"); bar.configure(value=d_)
                        msgv.set(f"Scan {d_} of {n_} saved: {sc.sid} (max {int(sc.counts.max()):,} counts)")
                        if d_ <= 3 and not drawn: draw_scans(); drawn = True
                    elif m[0] == "log": log("   XRD generator: " + m[1])
                    elif m[0] in ("done", "error"): finish(m); return
            except _q.Empty: pass
            win.after(120, poll)
        def finish(m):
            st["worker"] = None; gob.configure(state="normal"); canb.configure(state="disabled")
            if m[0] == "error":
                msgv.set("Generation stopped: see the message."); log("!! XRD generator: " + m[1])
                messagebox.showerror("Generation stopped", m[1] + ("\n\nScans saved before the error are kept." if st["scans"] else ""), parent=win); return
            r = m[1]; n_ = len(r.scans); st["files"] = r.files
            msgv.set((f"Cancelled: {n_} scan(s) were saved in {r.out_dir} and kept." if r.cancelled else f"Done: {n_} scan(s) saved in {r.out_dir}" + (" with preview.png." if r.preview else ".")))
            log(f"XRD generator: {n_} scan(s) from {st['tpl'].filename} saved in {r.out_dir} (.xrdml, .csv, manifest.csv{', preview.png' if r.preview else ''})")
            draw_scans(); last_folder[0] = r.out_dir
            if useb is not None and st["scans"]:
                useb.configure(state="normal"); useb2.configure(state="normal"); slb.selection_clear(0, "end"); slb.selection_set(0, "end"); draw_scans()
                msgv.set(msgv.get() + "  Choose one in the list under the graph and press 'Use the selected scan and continue'.")
            if addv.get() and r.scans:
                paths = [sc.files[0] for sc in r.scans][:50]
                add_files(paths); msgv.set(msgv.get() + f"  {len(paths)} added to Your graphs: go on there (draw, label peaks, stack).")
        def cancel():
            if st["stop"] is not None and st["worker"] is not None: st["stop"].set(); canb.configure(state="disabled"); msgv.set("Cancelling after the current scan …")
        def close():
            if st["worker"] is not None:
                if not messagebox.askyesno("XRD generator", "Scans are still being generated. Stop after the current scan and close?", parent=win): return
                st["stop"].set()
            xgen_win[0] = None; win.destroy()
        win.protocol("WM_DELETE_WINDOW", close)
        def use_selected():
            sel = list(slb.curselection())
            if not sel: messagebox.showerror("Choose a scan", "Tick one scan in the list under the graph first.", parent=win); return
            sc = st["scans"][sel[0]]; path_ = sc.files[0]
            xgen_win[0] = None
            try: win.destroy()
            except Exception: pass
            if on_chosen: on_chosen(path_)
        win.set_n = lambda n_: V["n"].set(str(int(n_)))
        win.xgen = dict(use_selected=use_selected, corrv=corrv, set_template=set_template, go=go, cancel=cancel, state=st, V=V, A=A, add_ref=add_ref, add_tpl=add_tpl, rm_phase=rm_phase, apply_counts=apply_counts, smart=smartv, msg=msgv, info=infov, ax=ax, slb=slb, plb=plb, close=close, addv=addv, prevv=prevv)
        if template: set_template(template)
        if pick_for and st["tpl"] is not None:
            mx_ = float(st["tpl"].y.max()); lo_, hi_ = xg.improve_counts(mx_)
            V["c_lo"].set(f"{lo_:.0f}"); V["c_hi"].set(f"{hi_:.0f}"); st["user_counts"] = False
            V["p_lo"].set(str(len(st["tpl"].y))); V["p_hi"].set(str(len(st["tpl"].y)))
            if xg.USUAL_COUNTS[0] <= mx_ <= xg.USUAL_COUNTS[1]:
                smartv.set(f"This scan's highest peak is {mx_:,.0f} counts, already in the usual range; the better versions are counted 2\u20133\u00d7 longer ({lo_:,.0f}\u2013{hi_:,.0f} counts: less noise). Change the range if you want.")
            else:
                smartv.set(f"This scan's highest peak is {mx_:,.0f} counts; the better versions are made in the usual range {lo_:,.0f}\u2013{hi_:,.0f} counts (change it if you want).")
            gob.configure(text="Make better versions")
            msgv.set(f"{os.path.basename(pick_for)}: highest peak {mx_:,.0f} counts. Press Make better versions, compare them and choose one.")
        return win
    act["xrd_generator"] = lambda: on_xrd_generator()
    def xrd_app():
        """XRD tools > XRD Scan Generator (app): the stand-alone XRD Scan Generator window, with the scan ticked in Your graphs
        (if any) as its template; the scans you send back come to Your graphs."""
        import xrd_generator as xg
        if xg.SCIPY_MISSING:
            if messagebox.askyesno("XRD Scan Generator", "The XRD Scan Generator needs the Python package SciPy, which is not installed.\n\nInstall it now? (one-time download of about 40 MB)", parent=root):
                scipy_install(xrd_app)
            return
        tpl = next((getattr(items[i], "path", "") for i in cur() if str(getattr(items[i], "path", "")).lower().endswith(".xrdml")), None)
        xgen_qt[0] = True
        if not qt_generator(tpl, better=bool(tpl), on_chosen=lambda ps: add_files(ps)):
            if not os.path.isfile(os.path.join(here, "xrd_scan_generator_app.py")): messagebox.showerror("XRD Scan Generator", "xrd_scan_generator_app.py is missing from the program folder: update the app (Help > Check for updates).", parent=root)
    act["xrd_app"] = xrd_app
    # ------------------------------------------------------------------ Analysis menu (analysis_tools.py: deterministic calculations on your curves)
    analysis_answers = [None]                 # tests: the settings instead of the dialog
    HOOKS["analysis_answers"] = analysis_answers; HOOKS["graph_list"] = lb
    def analysis_curves(its):
        """The curves of the chosen graphs: [Curve(name, x, y, xname, yname)] from each graph's first panel (helpers left out)."""
        import analysis_tools as at_
        out_ = []
        for it in its:
            if getattr(it, "spec", None) is None:
                try: build(it, it.kind)
                except Exception: pass
            spc = getattr(it, "spec", None) or {}
            pans = spc.get("panels") or []
            if not pans: continue
            p0 = pans[0]; cs = [c_ for c_ in p0.get("curves", []) if not str(c_.get("label", "")).startswith("_") and len(c_.get("x", [])) > 2]
            nm0 = sp.display_names([it])[0] if isinstance(it, sp.Item) else getattr(it, "name", "graph")
            for c_ in cs:
                nm = nm0 if len(cs) == 1 else f"{nm0} {c_.get('label', '')}".strip()
                yname = p0.get("yname") or str(c_.get("label", "y"))
                out_.append(at_.Curve(nm, np.asarray(c_["x"], float), np.asarray(c_["y"], float), str(spc.get("xname") or "x"), str(yname)))
        return out_
    def analysis_ask(label, spec, desc):
        """The tool's settings in a small window; None = cancelled."""
        if analysis_answers[0] is not None: return dict(analysis_answers[0])
        if not spec: return {}
        w = tk.Toplevel(root); w.title(label); w.transient(root); w.configure(bg=CARD); fr = ttk.Frame(w, padding=PAD); fr.pack(fill="both", expand=True)
        ttk.Label(fr, text=label, style="Step.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(fr, text=desc, style="Soft.TLabel", wraplength=px(420)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, SP2))
        vs = {}; box = {"ok": None}
        for r_, s_ in enumerate(spec, start=2):
            k_, lab_, typ_, dflt = s_[0], s_[1], s_[2], s_[3]
            ttk.Label(fr, text=lab_).grid(row=r_, column=0, sticky="w", pady=2, padx=(0, SP2))
            if typ_ is bool:
                vs[k_] = tk.BooleanVar(value=bool(dflt)); ttk.Checkbutton(fr, variable=vs[k_]).grid(row=r_, column=1, sticky="w")
            elif len(s_) > 4:
                vs[k_] = tk.StringVar(value=str(dflt)); ttk.Combobox(fr, textvariable=vs[k_], values=s_[4], state="readonly", width=44).grid(row=r_, column=1, sticky="we")
            else:
                vs[k_] = tk.StringVar(value=f"{dflt:g}" if isinstance(dflt, float) else str(dflt)); ttk.Entry(fr, textvariable=vs[k_], width=14).grid(row=r_, column=1, sticky="w")
        def done_(okk):
            box["ok"] = {k_: v_.get() for k_, v_ in vs.items()} if okk else None; w.destroy()
        bf = ttk.Frame(fr); bf.grid(row=len(spec) + 2, column=0, columnspan=2, sticky="e", pady=(SP3, 0))
        ttk.Button(bf, text="Cancel", command=lambda: done_(False)).pack(side="right")
        ttk.Button(bf, text="Run", style="Accent.TButton", command=lambda: done_(True)).pack(side="right", padx=SP2)
        w.bind("<Return>", lambda e: done_(True)); w.bind("<Escape>", lambda e: done_(False)); w.grab_set(); root.wait_window(w)
        return box["ok"]
    def analysis_show(title, tables):
        """The result tables in a window (and in the log)."""
        if analysis_answers[0] is not None or not tables: return
        w = tk.Toplevel(root); w.title(title); w.transient(root); w.configure(bg=CARD)
        try: w.geometry(f"{px(980)}x{px(420)}")
        except Exception: pass
        txt = SText(w, wrap="none", bg=_T["subtle"], fg=INK, font=("Consolas", -px(12)), relief="flat", borderwidth=0, padx=SP2, pady=SP2)
        txt.pack(fill="both", expand=True, padx=PAD, pady=PAD)
        txt.insert("1.0", "\n\n".join(f"{n_}\n{t_.to_string(index=False, float_format=lambda v: f'{v:.6g}')}" for n_, t_ in tables)); txt.config(state="disabled")
        ttk.Button(w, text="Close", command=w.destroy).pack(side="right", padx=PAD, pady=(0, PAD))
    def run_analysis(label):
        """Analysis > <tool>: on the ticked graphs (or the one on show). New curves are saved as CSV (+ provenance) in the results folder,
        under Analysis, and added to Your graphs; result tables are saved as CSV and shown."""
        import analysis_tools as at_, json as _json, hashlib, datetime as _dt
        grp, fn, spec, desc, how = at_.TOOLS[label]
        pool = [items[i] for i in cur()] or [i for i in singles if sp.key_of(i) == shown[0]]
        curves = analysis_curves(pool)
        if not curves:
            messagebox.showerror("Analysis", "Tick the graph(s) to analyse in Your graphs first (or click one to show it).", parent=root); return "no graph"
        st_ = analysis_ask(label, spec, desc)
        if st_ is None: return "cancelled"
        folder = os.path.join(run_folder(), "Analysis"); os.makedirs(folder, exist_ok=True)
        src = {c_.name: getattr(it_, "path", "") for it_ in pool for c_ in analysis_curves([it_])}
        def work(): return save_analysis(label, curves, st_, folder, src)
        def done(r):
            if r is None: status.set(f"{label}: not done. Press Show details to see why."); return
            if r[0] == "error":
                log(f"Analysis > {label}: not done: {r[1]}"); status.set(f"{label}: not done: {r[1]}")
                messagebox.showerror(label, r[1], parent=root); return
            files_, tables_, note_ = r
            log(f"Analysis > {grp} > {label} on {len(curves)} curve(s): {note_[0] if note_ else ''}")
            for n_, t_ in tables_: log(f"   {n_}\n" + t_.to_string(index=False, float_format=lambda v: f"{v:.6g}"))
            if files_: add_files(files_)
            status.set(f"{label}: done" + (f"; {len(files_)} new graph(s) added to Your graphs" if files_ else "") + (f"; {len(tables_)} result table(s)" if tables_ else "") + f". Files in {folder}")
            analysis_show(f"{label}: results", tables_)
            HOOKS["analysis_last"] = {"files": files_, "tables": tables_, "folder": folder}
        background(work, done, f"{label} …"); return "started"
    act["analysis"] = run_analysis
    def on_calorimetry_dialog():
        """One row per calorimetry file: mass (required), label, regime and alite fraction (optional, only what you type is used)."""
        import calorimetry as cal
        w = tk.Toplevel(root); w.title("Calorimetry (TAM III)"); w.transient(root); fr = ttk.Frame(w, padding=14); fr.pack(fill="both", expand=True)
        ttk.Label(fr, text="Add one row per sample. The mass is required; the label, regime (e.g. I, II, III) and alite fraction (e.g. 0.62) are optional "
                  "and appear on the figures only as you type them. With two or more files you also get the heat flow / cumulative heat pair (C4) "
                  "and the bar chart of the heat at a time (C5).", wraplength=720, foreground="#444444").grid(row=0, column=0, columnspan=7, sticky="w", pady=(0, 8))
        heads = ("Excel file", "", "Mass (g)", "Label", "Regime", "Alite fraction", "")
        for c_, h_ in enumerate(heads): ttk.Label(fr, text=h_, font=("Segoe UI", 9, "bold")).grid(row=1, column=c_, sticky="w", padx=3)
        rows = []; box = ttk.Frame(fr); box.grid(row=2, column=0, columnspan=7, sticky="we")
        def add_row(path_=""):
            r_ = {k: tk.StringVar() for k in ("file", "mass", "label", "regime", "alite")}; r_["file"].set(path_)
            if path_: r_["label"].set(os.path.splitext(os.path.basename(path_))[0])
            i = len(rows); ws = []
            ws.append(ttk.Entry(box, textvariable=r_["file"], width=34))
            ws.append(ttk.Button(box, text="Browse…", command=lambda: r_["file"].set(filedialog.askopenfilename(parent=w, filetypes=[("Excel workbook", "*.xlsx *.xlsm")]) or r_["file"].get())))
            for k, wd in (("mass", 8), ("label", 16), ("regime", 7), ("alite", 8)): ws.append(ttk.Entry(box, textvariable=r_[k], width=wd))
            def rm():
                for x_ in ws: x_.destroy()
                rows.remove(r_)
            ws.append(ttk.Button(box, text="\u2715", width=3, command=rm))
            for c_, x_ in enumerate(ws): x_.grid(row=i, column=c_, padx=3, pady=2, sticky="w")
            rows.append(r_); return r_
        def add_files_():
            for p_ in filedialog.askopenfilenames(parent=w, title="Calorimetry (TAM) Excel files", filetypes=[("Excel workbook", "*.xlsx *.xlsm")]) or ():
                empty = next((r_ for r_ in rows if not r_["file"].get()), None)
                if empty: empty["file"].set(p_); empty["label"].set(empty["label"].get() or os.path.splitext(os.path.basename(p_))[0])
                else: add_row(p_)
        add_row()
        bf = ttk.Frame(fr); bf.grid(row=3, column=0, columnspan=7, sticky="w", pady=6)
        ttk.Button(bf, text="Add files…", command=add_files_).pack(side="left", padx=(0, 6)); ttk.Button(bf, text="Add an empty row", command=lambda: add_row()).pack(side="left")
        g = {"excl": tk.StringVar(value=str(cal.DEFAULT_EXCLUSION_MIN)), "row": tk.StringVar(), "bar": tk.StringVar()}
        for i, (lab, k) in enumerate((("Exclusion window (min), all files", "excl"), ("Reaction-start row (empty = detect automatically)", "row"), ("Bar chart: heat at time (h) (empty = end of the shortest run)", "bar"))):
            ttk.Label(fr, text=lab).grid(row=4 + i, column=0, columnspan=2, sticky="w", pady=3); ttk.Entry(fr, textvariable=g[k], width=10).grid(row=4 + i, column=2, sticky="w", pady=3)
        def num(x_, what):
            x_ = x_.strip().replace(",", ".")
            if not x_: return None
            try: return float(x_)
            except ValueError: raise ValueError(f"{what} must be a number (you typed \u201c{x_}\u201d)")
        def go():
            ins = []
            try:
                ex = num(g["excl"].get(), "The exclusion window"); rr = num(g["row"].get(), "The reaction-start row"); bar = num(g["bar"].get(), "The bar-chart time")
                for r_ in rows:
                    if not r_["file"].get().strip(): continue
                    m = num(r_["mass"].get(), "The sample mass")
                    if not m or m <= 0: raise ValueError(f"Enter the sample mass in grams (above zero) for {os.path.basename(r_['file'].get())}. Nothing is processed without it.")
                    al = num(r_["alite"].get(), "The alite fraction")
                    if al is not None and al > 1: al = al / 100.0          # typed as a percentage
                    ins.append({"path": r_["file"].get().strip(), "mass_g": m, "exclusion_min": cal.DEFAULT_EXCLUSION_MIN if ex is None else ex, "reaction_row": int(rr) if rr else None,
                                "label": r_["label"].get().strip(), "name": r_["label"].get().strip() or None, "regime": r_["regime"].get().strip(), "alite": al})
            except ValueError as e: messagebox.showerror("Calorimetry", str(e), parent=w); return
            if not ins: messagebox.showerror("Calorimetry", "Choose at least one Excel file.", parent=w); return
            w.destroy(); cmd_calorimetry(inputs=ins, bar_at_h=bar)
        ttk.Button(fr, text="Process", command=go).grid(row=7, column=5, columnspan=2, sticky="e", pady=(10, 0))
        w.calo = {"rows": rows, "add_row": add_row, "go": go, "g": g}
        return w
    def on_assistant_settings():
        import assistant_secrets as sec, assistant_backends as ab_, system_check as sc_
        w = tk.Toplevel(root); w.title("Assistant settings"); w.transient(root); fr = ttk.Frame(w, padding=14); fr.pack(fill="both", expand=True)
        ttk.Label(fr, text="Fixed commands work without any of this. A key or a model is optional.", wraplength=420).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        key = tk.StringVar(); st = tk.StringVar(value="Key status: " + sec.status()); show = tk.BooleanVar(value=False)
        ttk.Label(fr, text="API key (ANTHROPIC_API_KEY)").grid(row=1, column=0, sticky="w")
        e = ttk.Entry(fr, textvariable=key, show="\u2022", width=36); e.grid(row=1, column=1, padx=6)
        ttk.Checkbutton(fr, text="Show", variable=show, command=lambda: e.config(show="" if show.get() else "\u2022")).grid(row=1, column=2)
        ttk.Label(fr, textvariable=st).grid(row=2, column=0, columnspan=3, sticky="w", pady=4)
        def save():
            if key.get().strip():
                where = sec.save(key.get()); key.set(""); st.set("Key status: " + sec.status() + (" (stored encrypted)" if where else " (could not be stored safely: kept for this session only)"))
                if not where: os.environ[sec.ENV] = e.get() or os.environ.get(sec.ENV, "")
        def test():
            ok_, m_ = ab_.test_connection(key=key.get().strip() or None); st.set(("\u2713 " if ok_ else "\u2717 ") + m_)
        def clear(): sec.clear(); st.set("Key status: " + sec.status())
        bf = ttk.Frame(fr); bf.grid(row=3, column=0, columnspan=3, sticky="w", pady=6)
        for t_, c_ in (("Save key", save), ("Test connection", test), ("Remove stored key", clear)): ttk.Button(bf, text=t_, command=c_).pack(side="left", padx=(0, 6))
        ttk.Label(fr, text=ab_.CLI_NOTE, wraplength=420, foreground="#555555").grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(fr, text="The key is never written to the repository, the logs, the figures or their provenance files.", wraplength=420, foreground="#555555").grid(row=5, column=0, columnspan=3, sticky="w")
    def cmd_system_check():
        import system_check; t_ = system_check.text(); say("app", t_); return t_
    def cmd_rietveld(amounts_file=None):
        raise ValueError("The two-panel Rietveld figure needs an observed/calculated pattern file and tick positions: use Draw › Paper figures from a recipe, or the function paper_figures.rietveld_two_panel")
    act["calorimetry"] = on_calorimetry_dialog; act["xrd_gen"] = on_xrd_generator; act["system_check"] = lambda: cmd_system_check(); act["assistant_settings"] = lambda: on_assistant_settings()
    CMD = {"figtype_graph": lambda type=None: figtype_apply(str(type)), "generate_xrd_scans": lambda n=None: (on_xrd_generator(n_scans=n), "The XRD generator is open: choose the template there.")[1], "plot_tga": cmd_tga, "analyze_tga_steps": cmd_analyze_tga, "stack_xrd": cmd_stack, "plot_calorimetry": cmd_calorimetry, "system_check": cmd_system_check, "rietveld_two_panel": cmd_rietveld}
    def cmd_try(t):
        """True when the sentence was a fixed command (handled here: confirmed, run, reported); False when it needs a model."""
        import assistant_parser as ap_, assistant_actions as aa_, paper_figures as pf_
        a = ap_.parse(t)
        if a is None: return False
        try: a = aa_.validate(a)
        except aa_.ActionError as e: say("you", t); say("app", f"I understood the request, but: {e}"); return True
        say("you", t)
        try:
            res = aa_.dispatch(a, CMD, lambda q: messagebox.askokcancel("Confirm", q, parent=root), pf_.CONFIRMED_ACTIONS)
        except Exception as e: say("app", f"NOT DONE: {e}"); log("!! Command:\n" + traceback.format_exc()); return True
        say("app", "Cancelled, nothing was run." if res is None else str(res)); return True
    def ai_send(text=None):
        t = (text if text is not None else ai_text()).strip()
        if not t: aatt.set("Type what you want in the box above, then press Enter."); return
        if abusy[0] or busy[0]: aistat.set("One moment please, I am still working on the previous step."); return
        if text is None:
            try: ainput.delete("1.0", "end")
            except Exception: pass
        if cmd_try(t): return
        if aconn[0] is None:
            import assistant_parser as ap_; say("you", t); say("app", ap_.HELP + "\n\nFor other requests, connect an AI above (optional)."); return
        model = aimodel.get().strip(); conn = aconn[0]
        if not model: aistat.set("Choose a model in the list 'Model' first (or type its name)."); return
        try:
            if text is None: ainput.delete("1.0", "end")
        except Exception: pass
        if anote[0]: t = t + "\n" + anote[0]; anote[0] = ""
        aatt.set(AHINT)
        say("you", t); asaid.append(t); abusy[0] = True; ai_busy_ui(True); aistat.set("Thinking …"); ai_dot("busy"); ai_save()
        def work():
            n_hist = len(ahist)
            try:
                lists = {"KINDS": [k for k in sp.KINDS if k != "Automatic"], "OWN_STYLES": sp.OWN_STYLES, "OWN_LAYOUTS": sp.OWN_LAYOUTS, "SETTINGS": {k: AIALLOWED.get(k) or AINOTE.get(k) for k in AISET}}
                system = ai.system_prompt(sp.VERSION, ai.read_text(ai.instructions_file(ahome)), ai.read_text(ai.lessons_file(ahome)), lists)
                msg = "STATE:\n" + json.dumps(on_ui(ai_state), ensure_ascii=False) + "\n\nUSER:\n" + t
                for round_ in range(ai.MAX_ROUNDS):
                    ahist.append({"role": "user", "content": msg}); recent = ahist[-13:]
                    while recent and recent[0]["role"] != "user": recent = recent[1:]
                    root.after(0, lambda: aistat.set("Thinking …")); reply = ai.chat(conn, model, system, recent)
                    ahist.append({"role": "assistant", "content": reply}); n_hist = len(ahist); r = ai.parse_reply(reply)
                    if r["say"]: say("ai", r["say"])
                    if not r["actions"]: break
                    snap = on_ui(lambda: list(items)); results = []; failed = False
                    for k_, a in enumerate(r["actions"][:25], 1):
                        root.after(0, lambda a=a: aistat.set(f"Doing: {a.get('do')} …"))
                        try: res = str(ai_do(a, snap, asaid)); ok = True
                        except Exception as e: res = f"NOT DONE: {e}"; ok = False; failed = True
                        results.append(f"{k_}. {a.get('do')}: {res}")
                        if not ok or a.get("do") not in ("look", "read_file"): did(f"{a.get('do')}: {res[:400]}", ok and not res.startswith("NOT DONE"))
                        elif a.get("do") == "look": did("looked at graph " + str(a.get("graph", "")))
                        else: did("looked into " + os.path.basename(str(a.get("path", ""))) + " (its first lines were sent to the AI)")
                        if not ok: break                     # later steps may depend on this one
                    if r["done"] and not failed: break
                    msg = "RESULTS:\n" + "\n".join(results) + "\n\nSTATE:\n" + json.dumps(on_ui(ai_state), ensure_ascii=False) + ("\n\nA step was not done. Tell the user in plain words what happened, and continue only if it makes sense." if failed else "")
                else: say("app", f"I stopped after {ai.MAX_ROUNDS} rounds. Say 'continue' if there is more to do.")
            except ai.AIError as e: del ahist[n_hist:]; say("app", str(e))
            except Exception: del ahist[n_hist:]; say("app", "Something went wrong; the details are in the message box of the view 'Scientific Workbench'."); log("!! Assistant:\n" + traceback.format_exc())
            finally:
                abusy[0] = False; root.after(0, lambda: (ai_busy_ui(False), aistat.set(ai_label()), ai_dot("on" if aconn[0] else "off"))); ai_keep_chat()
        threading.Thread(target=work, daemon=True).start()
    anote = [""]
    NOT_TABLES = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".zip", ".opj", ".opju")
    def ai_plus():
        """The + of the typing box: any file. The app reads it as always; a file it cannot read is handed to the AI to convert."""
        if abusy[0] or busy[0]: aatt.set("One moment please, I am still working on the previous step."); return
        paths = list(filedialog.askopenfilenames(title="Choose any files", filetypes=[("All files", "*.*")]))
        if not paths: return
        odd = [p for p in paths if p.lower().endswith(NOT_TABLES)]; paths = [p for p in paths if p not in odd]
        for p in odd: say("app", f"{os.path.basename(p)} is a document, picture or project file. This app draws from tables of numbers: export the table as CSV or Excel and add that.")
        if not paths: return
        apicked.update(paths); n0 = len(singles); add_files(paths); aatt.set("Reading " + ", ".join(os.path.basename(p) for p in paths) + " …")
        def work():
            idle(); new = singles[n0:]; bad = [p for p in paths if p in nograph]
            got = ", ".join(dict.fromkeys(os.path.basename(it.path) for it in new))
            note = ("Files just added: " + (f"{got} ({len(new)} graph(s))" if new else "none gave a graph") + (". These gave no graph: " + ", ".join(bad) if bad else "") + ".")
            def fin():
                typed = ai_text()
                if typed: anote[0] = "[" + note + "]"; aatt.set("Attached: " + ", ".join(os.path.basename(p) for p in paths) + ". Now press Enter to send what you typed."); return
                if aconn[0] is None and not aikey.get().strip() and ai.provider_of(aiprov.get()) != "ollama":
                    aatt.set(note + " Link an AI (Change AI…) to get a recommendation" + (" and to convert the files that gave no graph." if bad else ".")); return
                aatt.set(AHINT); ai_send(note + (" Read the files that gave no graph and convert them into tables the app can draw." if bad else "") + " Tell me in a few lines what you found and recommend what to draw.")
            root.after(0, fin)
        threading.Thread(target=work, daemon=True).start()
    def ai_keep_chat():
        """The conversation stays: it is there again when you open the app, whichever AI is linked."""
        try:
            with open(os.path.join(ahome, "assistant_chat.json"), "w", encoding="utf-8") as f: json.dump({"chat": [list(c) for c in achat if c[0] != "hint"][-400:], "hist": ahist[-12:], "said": asaid[-80:]}, f, ensure_ascii=False)
        except Exception: pass
    def ai_report():
        """One file with everything needed to find the cause of a problem (no data tables, no key)."""
        import zipfile, platform
        try:
            folder = out.get().strip() or default_results_folder(); os.makedirs(folder, exist_ok=True)
            p = os.path.join(folder, "OriginPlotApp_problem_report_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ".zip")
            about = [f"Origin plot app {sp.VERSION}", f"Python {sys.version.split()[0]} on {platform.platform()}", f"pandas {pd.__version__}, numpy {np.__version__}", "", "Loaded graphs:"]
            about += [f"  {it.title.strip()}" for it in items[:200]] + ["", "Files that gave no graph:"] + [f"  {os.path.basename(q)}" for q in nograph] + ["", "Problems of this session:"] + [f"--- {w_}\n{t_}" for w_, t_ in problems]
            with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("about.txt", "\n".join(about))
                for nm_, src in (("last_run_log.txt", logfile), ("settings.json", cfgfile), ("problems_all.txt", os.path.join(ahome, "problems.txt")), ("learned_formats.json", os.path.join(ahome, "learned_formats.json")), ("assistant_lessons.txt", os.path.join(ahome, "assistant_lessons.txt"))):
                    if os.path.exists(src): z.write(src, nm_)
                for q in nograph[-5:]:                       # the first lines of the files that could not be read: usually enough to see why
                    try: z.writestr("first_lines_of_" + os.path.basename(q) + ".txt", sp.peek_file(q, 30))
                    except Exception: pass
            say("app", f"Problem report written: {p}. It holds the messages, the settings and the first 30 lines of files that could not be read; no tables, no key. Send this file to whoever looks after the app."); status.set("Problem report: " + p)
        except Exception as e: say("app", f"I could not write the report: {e}")
    def ai_file(which):
        if which == "chats": p = os.path.join(ahome, "assistant_chats"); os.makedirs(p, exist_ok=True)
        else: p = ai.instructions_file(ahome) if which == "instructions" else ai.lessons_file(ahome)
        try: os.startfile(p)
        except Exception: say("app", "The file is here: " + p)
    def ai_new():
        old = [c for c in achat if c[0] != "hint"]
        if old:                                              # the old conversation is kept as a text file
            try:
                d_ = os.path.join(ahome, "assistant_chats"); os.makedirs(d_, exist_ok=True)
                with open(os.path.join(d_, "chat_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".txt"), "w", encoding="utf-8") as f:
                    f.write("\n".join({"you": "You: ", "ai": "Assistant: ", "app": "   - "}.get(w_, "") + t_ + ("" if w_ == "app" else "\n") for w_, t_ in old))
            except Exception: pass
        ahist.clear(); asaid.clear(); achat.clear()
        chat_clear()
        say("app", "New chat. The earlier one is kept under 'Earlier chats…'. Your instructions and what I learned stay."); ai_keep_chat()
    act["ai_connect"] = ai_connect; act["ai_send"] = ai_send; act["ai_plus"] = ai_plus; act["ai_paste"] = ai_paste; act["ai_getkey"] = ai_getkey; act["ai_report"] = ai_report; act["ai_example"] = ai_example; act["ai_linkbox"] = ai_linkbox
    try:
        aibox.bind("<<ComboboxSelected>>", ai_choice); aikey.trace_add("write", ai_key_typed); nb.bind("<<NotebookTabChanged>>", ai_tab, add="+")
    except Exception: pass
    ai_layout()
    act["ai_file"] = ai_file; act["ai_new"] = ai_new
    try:
        ainput.bind("<Return>", lambda e: (ai_send(), "break")[1]); ainput.bind("<Control-Return>", lambda e: (ai_send(), "break")[1]); ainput.bind("<Shift-Return>", lambda e: None)
        ainput.bind("<FocusIn>", lambda e: (ai_placeholder(False), tin.configure(style="FieldFocus.TFrame"))); ainput.bind("<FocusOut>", lambda e: (ai_placeholder(True), tin.configure(style="Field.TFrame")))
    except Exception: pass
    ai_placeholder(True)
    try:                                                     # the conversation of last time
        with open(os.path.join(ahome, "assistant_chat.json"), "r", encoding="utf-8") as f: old_ = json.load(f)
        if old_.get("chat"):
            say("hint", "Your earlier conversation (it continues; 'New chat' starts a fresh one):")
            SHOWN_ = 30                                          # the last messages are built as bubbles; all of them stay in the chat file and in the AI's memory of the chat
            if len(old_["chat"]) > SHOWN_: say("hint", f"({len(old_['chat']) - SHOWN_} earlier messages of this chat are not shown, to keep the window quick. They are still part of the chat.)", keep=False)
            achat.extend((w_, str(t_)) for w_, t_ in old_["chat"][-400:-SHOWN_] if w_ in ("you", "ai", "app"))
            for w_, t_ in old_["chat"][-SHOWN_:]:
                if w_ in ("you", "ai", "app"): say(w_, t_)
            ahist[:] = [m_ for m_ in (old_.get("hist") or []) if isinstance(m_, dict) and m_.get("role") in ("user", "assistant")]; asaid[:] = [str(x_) for x_ in (old_.get("said") or [])]
    except Exception: pass
    ai_linkbox(not (aikey.get().strip() or amodels))
    if not achat:
        say("hint", "Hi. I can recommend graphs, rename samples, label peaks you specify, convert difficult files, prepare an Origin workbook, and draw the selected results. Start by attaching a file or typing a request below.")
    assistant_refresh_context()
    def remove_old_files():
        gone = []
        for f_, mark_ in REMOVED_FILES.items():
            p_ = os.path.join(here, f_)
            try:
                if os.path.isfile(p_):
                    with open(p_, encoding="utf-8", errors="replace") as fh_: head_ = fh_.read(4000)
                    if mark_ in head_: os.remove(p_); gone.append(f_)
            except Exception as e: log(f"   could not remove the old file {f_}: {e}")
        if gone: log("Removed the program files of the former modern window: " + ", ".join(gone))
        return gone
    HOOKS["remove_old_files"] = remove_old_files
    def startup_checks():
        """Plugin folders and the System Check, once, after the window is up. Problems are written to the message log; nothing here can stop the app."""
        try: remove_old_files()
        except Exception: pass
        try:
            import paper_figures as pf_
            for p_ in pf_.load_plugins()["problems"]: log("!! plugin file not used: " + p_)
        except Exception as e: log("!! plugin folders could not be read: " + type(e).__name__)
        try:
            import system_check as sc_
            for n_, s_, d_ in sc_.run():
                if s_ != "ok": log(f"   System Check: {n_}: {d_}")
        except Exception: pass
    def preload_generator():
        """Import SciPy and the XRD generator in the background once the window is up, so opening the generator is instant."""
        def work():
            try: import xrd_generator  # noqa: F401
            except Exception: pass
        try: threading.Thread(target=work, daemon=True).start()
        except Exception: pass
    try: root.after(4000, preload_generator)
    except Exception: pass
    try: root.after(1200, startup_checks)
    except Exception: pass
    def modern_at_start():
        """Settings > 'Window that opens at start' in the modern window: open it, and keep this window in the taskbar."""
        try:
            with open(os.path.join(here, "settings_modern.json"), encoding="utf-8") as fh: want = json.load(fh).get("start_window") == "modern"
        except Exception: want = False
        if not want or os.environ.get("OPS_CLASSIC"): return          # opened as the classic window from the modern one
        import importlib.util
        if importlib.util.find_spec("PySide6") is None: return
        if act["modern_window"]() == "opening":
            try: root.iconify()
            except Exception: pass
    try: root.after(1500, modern_at_start)
    except Exception: pass
    HOOKS.update(show=show, figtype_answer=figtype_answer, figtype_apply=figtype_apply, figtype_template=on_figtype_template, singles=singles, act=act, ask_answer=ask_answer, check_intensities=check_intensities, xrd_generator=on_xrd_generator, items=items, cmd=CMD, cmd_try=cmd_try, assistant_settings=on_assistant_settings, out_var=out, say=say, did=did, ai_do=ai_do, ai_said=asaid, paper_figures=paper_figures_run, ai_plus=ai_plus, ai_report=ai_report, ai_new=ai_new, ai_nograph=nograph, ai_input=ainput, ai_att=aatt, ai_choice=ai_choice, ai_paste=ai_paste, ai_tab=ai_tab, ai_conn=aconn, ai_stat=aistat, ai_send=ai_send, ai_connect=ai_connect, ai_chat=achat, ai_vars={"key": aikey, "address": aiaddr, "choice": aiprov, "model": aimodel}, ai_busy=abusy, ai_home=ahome, ai_hist=ahist)
    def on_close():
        autosave()
        if busy[0]:
            try:
                from tkinter import messagebox
                if not messagebox.askokcancel("Still working", "I am still working (reading files or drawing in Origin).\nClose anyway? Graphs not finished yet will be missing."): return
            except Exception: pass
        try: HOOKS.get("close_xgen", lambda: None)()        # the XRD Scan Generator window(s) opened from here close too
        except Exception: pass
        try: root.withdraw()                              # gone from the screen at once
        except Exception: pass
        try: remember()
        except Exception: pass
        def last_resort():                                 # if something still holds the program after 3 seconds (a hanging link to the AI or to Origin), end it
            _time.sleep(3); os._exit(0)
        try: threading.Thread(target=last_resort, daemon=True).start()
        except Exception: pass
        root.destroy()
    for v_ in list(analysis.values()) + [maxlab, labxy]:        # any changed setting marks the graphs as not up to date
        try: v_.trace_add("write", mark_dirty)
        except Exception: pass
    try: root.protocol("WM_DELETE_WINDOW", on_close)
    except Exception: pass
    try: root.after(4000, lambda: on_update(quiet=True))                 # only tells you that a new version is there; it installs nothing
    except Exception: pass
    act["update"] = lambda: on_update()
    HOOKS.update(layout=set_layout, live_fig=assistant_fig, slow=slow, update_zip=on_update, update=on_update, update_known=upd_known, update_waiting=update_waiting, update_source=update_source, ai_repair=on_ai_repair, undo_update=on_undo_update, log_problem=log)
    try: root.update_idletasks(); root.deiconify()
    except Exception: pass
    def taskbar_icon():
        """The app's icon on the taskbar button, in the size Windows asks for, and for the button when it is pinned.
        Tk sets the icon of the window; the taskbar takes its own from Windows, so it is given there directly."""
        if sys.platform != "win32": return
        ico = os.path.join(here, "app.ico")
        try:
            import ctypes
            from ctypes import wintypes
            u = ctypes.windll.user32; u.GetParent.restype = wintypes.HWND; u.GetParent.argtypes = [wintypes.HWND]
            hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
            u.LoadImageW.restype = wintypes.HANDLE; u.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            u.SendMessageW.restype = ctypes.c_ssize_t; u.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            keep = []
            for which, metric in ((1, 11), (0, 49)):         # the large icon (taskbar, Alt+Tab) and the small one (title bar)
                n_ = int(u.GetSystemMetrics(metric)) or (32 if which else 16)
                h_ = u.LoadImageW(None, ico, 1, n_, n_, 0x0010)
                if h_: u.SendMessageW(hwnd, 0x0080, which, h_); keep.append(h_)
            root._icon_handles = keep
        except Exception: hwnd = None
        try:                                             # pinned to the taskbar: the pin keeps the app's icon and starts the app, not bare Python
            if hwnd:
                import pythoncom
                from win32com.propsys import propsys, pscon
                st_ = propsys.SHGetPropertyStoreForWindow(hwnd, propsys.IID_IPropertyStore)
                pw_ = os.path.join(os.path.dirname(sys.executable), "pythonw.exe"); pw_ = pw_ if os.path.isfile(pw_) else sys.executable
                for key_, val_ in ((pscon.PKEY_AppUserModel_ID, "OriginPlotStudio.App"), (pscon.PKEY_AppUserModel_RelaunchCommand, f'"{pw_}" "{os.path.join(here, "start.pyw")}"'),
                                   (pscon.PKEY_AppUserModel_RelaunchDisplayNameResource, "Origin Plot Studio"), (pscon.PKEY_AppUserModel_RelaunchIconResource, ico + ",0")):
                    st_.SetValue(key_, propsys.PROPVARIANTType(val_, pythoncom.VT_LPWSTR))
                st_.Commit()
        except Exception: pass
    try: root.after(300, taskbar_icon)
    except Exception: pass
    try:                                                 # the little "Starting" window of start.pyw has done its job
        import builtins
        sp_ = getattr(builtins, "_ops_splash", None)
        if sp_ is not None: builtins._ops_splash = None; root.after(150, sp_.destroy)
    except Exception: pass
    slow.write(f"{_clock() - slow.t_start:5.1f} s  from the double-click to the window being on the screen"); slow.begin()
    dropped = [os.path.abspath(a) for a in sys.argv[1:] if os.path.exists(a)]      # files dragged onto the .bat
    if dropped: add_files(dropped)
    root.mainloop()

if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        a = [v for v in sys.argv[1:] if not v.startswith("--")]; here = os.path.dirname(os.path.abspath(a[0])); cmds = []
        if True:
            items = []
            for f in a:
                new, lines = sp.load_file(f); print(os.path.basename(f) + ":\n" + "\n".join(lines)); items += [it.build({"app_dir": os.path.dirname(os.path.abspath(__file__))}) for it in new]
            opt_ = {"app_dir": os.path.dirname(os.path.abspath(__file__))}; sp.apply_info(items, opt_); print("\n".join(sp.link_xrd(items, opt_)))
            comb, lines = sp.make_groups(items, "Decide for me", opt_); print("How the files were combined:\n" + "\n".join(lines)); items = comb + items
            if "--board" in sys.argv:
                b = sp.Board([sp.key_of(i) for i in items[:4]]); b.resolve(items); items = [b.build()] + items
            drv = run_items(items, os.path.join(here, "dry_out"), print, dry=True, settings={"dry run": True}, session=sp.session_dump([i for i in items if isinstance(i, sp.Item)], [i for i in items if isinstance(i, sp.Board)], {})); cmds = drv.org.cmds if drv else []
        open(os.path.join(here, "dry_commands.txt"), "w", encoding="utf-8").write("\n".join(cmds)); print("LabTalk commands generated:", len(cmds))
    else:
        # Started without a console window (pythonw): nothing can be printed, so a start that fails is written to
        # startup_error.txt next to the program and shown in a message, instead of the app simply not appearing.
        _here = os.path.dirname(os.path.abspath(__file__))
        if sys.stdout is None or sys.stderr is None:
            try: _out = open(os.path.join(_here, "console_output.txt"), "w", encoding="utf-8", buffering=1); sys.stdout = sys.stdout or _out; sys.stderr = sys.stderr or _out
            except Exception: pass
        try:                                  # since 5.40.0 the app has one window (workspace_qt.py, started by start.pyw); gui() is the earlier one
            import runpy as _rp
            _rp.run_path(os.path.join(_here, "start.pyw"), run_name="__main__")
        except SystemExit: raise
        except Exception:
            _tb = traceback.format_exc()
            try: open(os.path.join(_here, "startup_error.txt"), "w", encoding="utf-8").write(_tb)
            except Exception: pass
            try:
                import tkinter as _tk
                from tkinter import messagebox as _mb
                _r = _tk.Tk(); _r.withdraw(); _mb.showerror("Origin Plot Studio could not start", "The app could not start. The details are in startup_error.txt, in the folder of the app.\n\n" + _tb[-900:]); _r.destroy()
            except Exception: pass
            raise

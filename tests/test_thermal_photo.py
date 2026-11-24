"""Several files of one kind: always stacked AND overlaid, and every curve on its own. Thermal analysis files with TG and DSC
together (NETZSCH .ngb-ds3, STA exports): a page per sample - (a) TG with DTG, (b) DSC - and a comparison of all samples.
A photo of a sketch on paper: read into frames, zoom, legend and curves, and used to lay out graphs."""
import os, sys, tempfile, shutil
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
os.environ["OPS_SETTINGS_FILE"] = str(Path(tempfile.mkdtemp()) / "settings_modern.json")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "tests"))
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info else ""))
import numpy as np, pandas as pd
from PIL import Image
import smart_plots as sp, sketch_pad as SK, make_sketch_photo as mp
D = Path(tempfile.mkdtemp())
T = np.linspace(30, 1000, 600); files = []
for k, nm in enumerate(["RunA", "RunB", "RunC"]):                       # three STA runs: mass and DSC against temperature in one file
    m = 100 - 8 / (1 + np.exp(-(T - 110) / 15)) - 5 / (1 + np.exp(-(T - 480) / 12)) - (4 + k) / (1 + np.exp(-(T - 760) / 20))
    dsc = 20 * np.exp(-0.5 * ((T - 115) / 30) ** 2) + 10 * np.exp(-0.5 * ((T - 490) / 15) ** 2) - 0.01 * T
    f = D / f"{nm}.csv"; pd.DataFrame({"Temp./°C": T, "Mass/%": m, "DSC/(mW/mg)": dsc}).to_csv(f, index=False, encoding="utf-8-sig"); files.append(str(f))
from PySide6.QtWidgets import QApplication
from matplotlib.figure import Figure
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W
w = W.Workspace([]); w.show(); app.processEvents()
w.load_sync(files); app.processEvents()
check("every curve on its own: a TGA and a DSC graph of each file", sorted(i.kind for i in w.singles) == ["DSC"] * 3 + ["TGA"] * 3)
hows = sorted((c.kind, c.how) for c in w.combined)
check("several files of one kind: stacked AND overlaid, always (TGA and DSC)", hows == [("DSC", "overlay"), ("DSC", "stack"), ("TGA", "overlay"), ("TGA", "stack")], hows)
pages = [b for b in w.boards if getattr(b, "auto", "") == "sample"]; comp = [b for b in w.boards if getattr(b, "auto", "") == "compare"]
check("TG and DSC in one file: a page per sample, (a) TG with DTG, (b) DSC", len(pages) == 3 and all([m.kind for m in b.members] == ["TGA", "DSC"] for b in pages), [b.name for b in pages])
check("... and a comparison of all samples: (a) the TG curves, (b) the DSC curves", len(comp) == 1 and [m.kind for m in comp[0].members] == ["TGA", "DSC"] and all(m.how == "overlay" for m in comp[0].members))
for b in pages[:1] + comp:
    fig = Figure(); sp.board_figure(b, fig, 1.5, 1.5)
    check(f"'{b.name}' is drawn ({len(fig.axes)} axes)", len(fig.axes) >= 2)
check("all of them are in Your graphs", all(b in w.items for b in pages + comp) and all(c in w.items for c in w.combined))
w.load_sync([files[0]]); app.processEvents()
check("reading a file again makes no second set of pages", len([b for b in w.boards if getattr(b, "auto", "")]) <= 5)
w.close()
# calorimetry: several files, both ways too
cal = ROOT / "origin_plot_app" / "examples_synthetic" / "calorimetry.csv"
c2 = D / "calorimetry_B.csv"; shutil.copy(cal, c2)
its = sp.load_file(str(cal))[0] + sp.load_file(str(c2))[0]
pool = []; sp.prepare(pool, its, {}); g, _ = sp.make_groups(pool, "Decide for me", {})
ch = sorted(x.how for x in g if x.kind == "Calorimetry")
check("calorimetry, several files: two figures of them (both ways)", len(ch) == 2 and "stack" in ch, ch)
# a photo of a sketch
cases = ((mp.framed, "single", 3, "stack", True), (mp.axes_only, "single", 2, "overlay", False), (mp.two_frames, "figure", 2, None, False))
for fn, lay, nc, how, zl in cases:
    for rot in (0, 3):
        p = fn(str(D / f"{fn.__name__}.jpg"))
        if rot: Image.open(p).rotate(rot, fillcolor=(215, 215, 215)).save(p)
        items, page = SK.photo_to_items(p); d = SK.read_sketch(items, page)
        got = (d["layout"], sum(1 for i in items if i["type"] == "curve"), d["graphs"][0].get("how") if d["graphs"] else None,
               any(i["type"] == "zoom" for i in items) and any(i["type"] == "legend" for i in items))
        check(f"photo '{fn.__name__}'{' taken 3° crooked' if rot else ''}: {lay}, {nc} curves" + (f", {how}" if how else "") + (", zoom and legend" if zl else ""),
              got[0] == lay and got[1] == nc and (how is None or got[2] == how) and (got[3] or not zl), got)
blank = D / "blank.jpg"; Image.new("RGB", (800, 600), (220, 220, 220)).save(blank)
check("a photo without a sketch: nothing is made up", SK.photo_to_items(str(blank))[0] == [])
# in the window: the pad reads the photo, shows the shapes (to edit), and lays out the ticked graphs
w = W.Workspace([]); w.show(); app.processEvents()
w.load_sync(files[:1]); app.processEvents()
dlg = w.ribbon.sketch(); app.processEvents()
dz = dlg.read_photo(mp.framed(str(D / "f.jpg")))
shapes = sorted(i.data(0) for i in dlg.pad.sc.items() if i.data(0))
check("the pad reads the photo into shapes you can edit (frame, zoom, legend, curves) and says what it read", shapes == ["box", "curve", "curve", "curve", "legend", "zoom"]
      and "Read from the photo" in dlg.msg.text() and dlg.pad.photo is not None, shapes)
w._tick_only([w.singles[0]]); w.list.setCurrentRow(w.items.index(w.singles[0]))
m_ = dlg.apply(); app.processEvents()
check("... and the graph is laid out from it (the zoom where the photo has it)", "laid out" in m_ and w.singles[0].fmt.get("inset_rect") and w.singles[0].fmt["inset_rect"][0] > 0.5, (m_, w.singles[0].fmt.get("inset_rect")))
dlg.close(); w.close()
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)

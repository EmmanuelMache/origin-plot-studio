"""Checks of origin_plot_app/calorimetry.py (Part 2.9).  Run:  python tests/test_calorimetry.py [output folder]"""
import os, sys, csv, math, json, shutil, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "origin_plot_app"))
import calorimetry as cal


def synthetic(path, mass=0.5, hours=48, step_s=60, lead_rows=12, peak=3.2, shift=0.0, unit_row=True, t_unit="s", hf_unit="W"):
    """A TAM-like export: Time (s), Heat flow (W), Marker, with a 'Reaction start' marker after some rows of baseline."""
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Raw data"
    if unit_row: ws.append(["Time", "Heat flow", "Marker"]); ws.append([t_unit, hf_unit, None])
    else: ws.append([f"Time ({t_unit})", f"Heat flow ({hf_unit})", "Marker"])
    n = int(hours * 3600 / step_s)
    for i in range(-lead_rows, n + 1):
        t_s = 600 + (i + lead_rows) * step_s; th = i * step_s / 3600.0
        if th < 0: mwg = 0.02
        else: mwg = 25 * math.exp(-th / 0.12) + peak * math.exp(-((th - 9.5 - shift) / 4.2) ** 2) + 0.55 * math.exp(-th / 30) + 0.05
        t = {"s": t_s, "min": t_s / 60, "h": t_s / 3600}[t_unit]; hf = {"W": mwg * mass / 1000, "mW": mwg * mass, "W/g": mwg / 1000, "mW/g": mwg}[hf_unit]
        ws.append([t, hf, "Reaction start" if i == 0 else None])
    wb.save(path); return path


def check(keep=None):
    res = []; ok = lambda name, cond, detail="": res.append((name, bool(cond), str(detail)))
    work = keep or tempfile.mkdtemp(prefix="calo_"); os.makedirs(work, exist_ok=True)
    # 1. unit test: constant 1 mW/g for 1 h gives exactly 3.6 J/g
    q = cal.integrate([0.0, 0.25, 0.5, 1.0], [1.0, 1.0, 1.0, 1.0]); ok("1  constant 1 mW/g for 1 h gives 3.6 J/g", abs(q[-1] - 3.6) < 1e-12 and q[0] == 0.0, q[-1])
    q = cal.integrate([0.0, 0.5, 1.0, 2.0], [float("nan"), float("nan"), 1.0, 1.0]); ok("   excluded rows are NaN and the sum starts at 0 after them", q[0] != q[0] and q[2] == 0.0 and abs(q[3] - 3.6) < 1e-12, q)
    # 2. the full pipeline on synthetic files, with the Excel recalculation compared with Python
    a = synthetic(os.path.join(work, "CEM_ref.xlsx"), mass=0.5); b = synthetic(os.path.join(work, "CEM_15pct_SCM.xlsx"), mass=0.48, peak=2.5, shift=1.5, unit_row=False); c = synthetic(os.path.join(work, "CEM_30pct_SCM.xlsx"), mass=0.51, peak=1.9, shift=3.0, t_unit="h", hf_unit="mW")
    out = os.path.join(work, "out"); shutil.rmtree(out, ignore_errors=True); logs = []
    r = cal.run([{"path": a, "mass_g": 0.5, "exclusion_min": 45}, {"path": b, "mass_g": 0.48, "exclusion_min": 45}, {"path": c, "mass_g": 0.51, "exclusion_min": 45}], out, "test", logs.append)
    ok("2  the pipeline runs on three synthetic files", len(r["samples"]) == 3, [f"{s['name']}: {s['total_Jg']:.1f} J/g" for s in r["samples"]])
    rc = [s["recalc"] for s in r["samples"]]
    if all(x["done"] for x in rc): ok("   Excel recalculation (LibreOffice) matches Python at 1e-6", all(x["ok"] for x in rc), [x["compared"] for x in rc])
    else: ok("   Excel recalculation SKIPPED: LibreOffice is not installed (WARNING, not a failure)", True, rc[0]["note"])
    p = cal.read(a); ok("   columns found by their headers", p["columns"] == {"time": "A", "heat": "B", "marker": "C"} and p["reaction_row"] == 15, f"{p['columns']} reaction row {p['reaction_row']}")
    ra = cal.compute(p, 0.5, 45); k = ra["kept"]; expect_tot = ra["total_Jg"]
    ok("   the mass is used: half the mass doubles the result", abs(cal.compute(p, 0.25, 45)["total_Jg"] / expect_tot - 2) < 1e-9)
    import openpyxl
    wb = openpyxl.load_workbook(r["samples"][0]["workbook"]); ws = wb["Raw data"]
    forms = [c_.value for row in ws.iter_rows() for c_ in row if isinstance(c_.value, str) and c_.value.startswith("=")]
    ok("   the workbook holds live formulas that refer to the helper cells", len(forms) > 3 * len(p["rows"]) and any("$" in f for f in forms), f"{len(forms)} formulas")
    ok("   two charts on the sheet", len(ws._charts) == 2, len(ws._charts))
    ok("   no hard-coded mass in the formulas", not any("/0.5" in f for f in forms))
    # 3. refusal: mass 0 (and missing, negative) must refuse and write nothing
    refused = []
    for m in (0, None, "", -1, "abc"):
        o3 = os.path.join(work, "refused"); shutil.rmtree(o3, ignore_errors=True)
        try: cal.run([{"path": a, "mass_g": m, "exclusion_min": 45}], o3, "test"); refused.append((m, "RAN"))
        except cal.CalorimetryError as e: refused.append((m, "refused" if not os.path.exists(o3) else "refused BUT WROTE FILES"))
    ok("3  mass 0, missing, negative or not a number is refused and nothing is written", all(v == "refused" for _, v in refused), refused)
    o3 = os.path.join(work, "refused2"); shutil.rmtree(o3, ignore_errors=True)
    try: cal.run([{"path": a, "mass_g": 0.5}, {"path": b, "mass_g": 0}], o3, "test"); two = "RAN"
    except cal.CalorimetryError: two = "refused" if not os.path.exists(o3) else "WROTE"
    ok("   one bad sample among several: nothing at all is written", two == "refused", two)
    # 4. exclusion: the number of excluded rows is the expected one
    lead = 12; step = 60; expected = lead + int(45 * 60 / step)          # rows before the reaction start + rows inside 45 min (the row at exactly 45 min is kept)
    ok("4  excluded rows for a 45 min window", ra["excluded_rows"] == expected, f"{ra['excluded_rows']} (expected {expected})")
    ok("   and for 0 min and 90 min", cal.compute(p, 0.5, 0)["excluded_rows"] == lead and cal.compute(p, 0.5, 90)["excluded_rows"] == lead + 90, (cal.compute(p, 0.5, 0)["excluded_rows"], cal.compute(p, 0.5, 90)["excluded_rows"]))
    ok("   the first kept row has time 0.75 h and cumulative heat 0", abs(ra["time_h"][k[0]] - 0.75) < 1e-9 and ra["cumulative_Jg"][k[0]] == 0.0)
    long = cal.compute(p, 0.5, 60 * 60); ok("   a window longer than the experiment warns and gives zero", long["total_Jg"] == 0 and any("longer than the experiment" in w for w in long["warnings"]))
    # 5. Origin export: header rows exactly, numbers only, excluded rows left out
    we = wb["Origin Export"]; rows = list(we.iter_rows(values_only=True))
    ok("5  Origin Export rows 1 and 2 are exact", list(rows[0]) == ["Time", "Normalised Heatflow", "Cumulative Heatflow"] and list(rows[1]) == ["h", "mW/g", "J/g"], rows[:2])
    ok("   numbers only, no formulas, excluded rows left out", len(rows) - 2 == len(k) and all(isinstance(v, (int, float)) for rw in rows[2:] for v in rw), f"{len(rows) - 2} rows")
    ok("   no merged cells, colours or borders", not we.merged_cells.ranges and all(c_.fill.fgColor.rgb in ("00000000", None) and c_.border.left.style is None for rw in we.iter_rows(max_row=6) for c_ in rw))
    with open(r["samples"][0]["origin_csv"], newline="") as f: cr = list(csv.reader(f))
    ok("   the CSV has the same two header rows and the same numbers", cr[0] == cal.ORIGIN_HEAD and cr[1] == cal.ORIGIN_UNITS and len(cr) - 2 == len(k) and abs(float(cr[-1][2]) - expect_tot) < 1e-9)
    r2 = cal.run([{"path": r["samples"][0]["workbook"], "mass_g": 0.5, "exclusion_min": 60, "name": "rerun"}], os.path.join(work, "out2"), "test")
    n2 = len(list(openpyxl.load_workbook(r2["samples"][0]["workbook"])["Origin Export"].iter_rows())) - 2
    ok("   a second run on a processed workbook recreates the sheet (no stale rows)", n2 == len(cal.compute(p, 0.5, 60)["kept"]), n2)
    # other rules of the task
    pv = json.load(open(r["samples"][0]["provenance"])); ok("   provenance: hash, columns, reaction row, window, mass, factor", len(pv["input_sha256"]) == 64 and pv["columns"]["time"] == "A" and pv["reaction_start_row"] == 15 and pv["exclusion_window_min"] == 45 and pv["sample_mass_g"] == 0.5 and pv["factor_J_per_mWh"] == 3.6)
    nomark = os.path.join(work, "no_marker.xlsx"); wbn = openpyxl.load_workbook(a)
    for i in range(3, 40): wbn.active.cell(row=i, column=3).value = None
    wbn.save(nomark)
    try: cal.compute(cal.read(nomark), 0.5, 45); nm = "ran"
    except cal.CalorimetryError as e: nm = "refused"
    ok("   no marker and no row given: refused; with a row given: runs", nm == "refused" and cal.compute(cal.read(nomark), 0.5, 45, reaction_row=15)["reaction_row"] == 15)
    wg = cal.compute(cal.read(synthetic(os.path.join(work, "wg.xlsx"), hf_unit="W/g")), 0.5, 45); ok("   heat flow already in W/g: the mass is not divided again", abs(wg["total_Jg"] - expect_tot) / expect_tot < 1e-9 and not wg["mass_used"])
    neg = openpyxl.Workbook(); wn = neg.active; wn.append(["Time", "Heat flow", "Marker"]); wn.append(["s", "W", None]); [wn.append([i * 60, -1e-5, "Reaction start" if i == 0 else None]) for i in range(200)]; neg.save(os.path.join(work, "neg.xlsx"))
    ok("   a negative total is flagged", cal.NEGATIVE_TOTAL in cal.compute(cal.read(os.path.join(work, "neg.xlsx")), 0.5, 45)["warnings"])
    figs = [f for f in r["figures"] if f.endswith(".png")]; ok("   figures C1 (per sample), C2, C3, C4 (pair) and C5 (bars) written", len(figs) == 7 and any("C4_" in f for f in figs) and any("C5_" in f for f in figs), [os.path.basename(f) for f in figs])
    from PIL import Image
    sz = {Image.open(f).size for f in figs}; ok("   all figures are landscape 11.7 x 6.5 in", sz == {(3510, 1950)}, sz)
    if not keep: shutil.rmtree(work, ignore_errors=True)
    return res


if __name__ == "__main__":
    res = check(sys.argv[1] if len(sys.argv) > 1 else None)
    for name, good, detail in res: print(("PASS  " if good else "FAIL  ") + name + (f"   [{detail[:150]}]" if detail else ""))
    sys.exit(0 if all(g for _, g, _ in res) else 1)

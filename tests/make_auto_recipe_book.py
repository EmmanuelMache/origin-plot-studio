"""A neutral workbook for the automatic recipe: no figure plan, several kinds of sheets. Synthetic numbers only.

    python tests/make_auto_recipe_book.py out.xlsx [--plan]
"""
import sys
import numpy as np
import pandas as pd


def peaks(x, centres, heights, w=0.12):
    y = np.zeros_like(x)
    for c, h in zip(centres, heights): y += h * np.exp(-0.5 * ((x - c) / w) ** 2)
    return y


def book(plan=False):
    r = np.random.default_rng(7); sh = {}
    # 1. a fit with a long reflection list and a label list (Sample A)
    x = np.round(np.arange(10, 60, 0.02), 3)
    pos = {"X": [20.0, 28.5, 33.1, 47.2], "Xa": [24.4, 31.0, 44.8], "Y": [26.6, 40.3]}
    calc = 80 + peaks(x, sum(pos.values(), []), [900, 400, 1200, 300, 500, 250, 350, 700, 200])
    obs = calc + r.normal(0, 8, x.size)
    sh["SampleA_Profile"] = pd.DataFrame({"2theta_deg": x, "Yobs_counts": obs, "Ycalc_counts": calc, "Ydiff_counts": obs - calc})
    sh["SampleA_Bragg"] = pd.DataFrame([{"Phase": k, "2theta_deg": p, "h": 1, "k": 0, "l": 0} for k, ps in pos.items() for p in ps])
    sh["Samples"] = pd.DataFrame({"Sample": ["SampleA"], "Rwp (%)": [8.21]})
    lab = []
    for k, ps in pos.items():
        for p in ps: lab.append({"Sample": "SampleA", "Label": k, "2θ (°)": p, "Peak top (counts)": float(calc[np.argmin(abs(x - p))]),
                                  "Label height (counts)": float(calc[np.argmin(abs(x - p))]) + 40, "Stagger level": 0,
                                  "Colour (hex)": {"X": "#0072B2", "Xa": "#D55E00", "Y": "#009E73"}[k]})
    sh["Labels_SampleA"] = pd.DataFrame(lab)
    # 2. FTIR spectra of four samples, one sheet, not offset
    wn = np.arange(4000, 399, -2.0)
    sp = {"Wavenumber (cm-1)": wn}
    for i, n in enumerate(["Sample A", "Sample B", "Sample C", "Sample D"]):
        sp[f"{n} absorbance"] = 0.05 + peaks(wn, [3400, 1640, 1080, 960 - 10 * i, 450], [0.3, 0.15, 0.8 - 0.1 * i, 0.4, 0.5], w=40) + r.normal(0, 0.004, wn.size)
    sh["FTIR"] = pd.DataFrame(sp)
    # 3. heat flow of three samples (x-y, many rows): one family of two sheets
    t = np.linspace(0, 72, 400)
    for nm, k in (("Calorimetry_20C", 1.0), ("Calorimetry_40C", 1.8)):
        sh[nm] = pd.DataFrame({"Time (h)": t, **{f"Sample {s} heat flow (mW/g)": 3 * np.exp(-((t * k - 10 - 2 * i) / 5) ** 2) + 0.3 * np.exp(-t / 2) for i, s in enumerate("ABC")}})
    # 4. strength with SD columns (category table)
    sh["Strength"] = pd.DataFrame({"Mix": ["Sample A", "Sample B", "Sample C"], "2 d (MPa)": [20, 15, 12], "2 d SD": [1.1, 0.9, 1.0],
                                   "28 d (MPa)": [52, 47, 40], "28 d SD": [2.0, 1.7, 2.2]})
    # 5. measured vs two models (x-y, few points), two panels
    xx = np.array([0, 5, 10, 15])
    sh["Model_Phase1"] = pd.DataFrame({"Additive (wt.%)": xx, "Measured (wt.%)": [50, 44, 37, 30], "Model 1 (wt.%)": [55, 47, 40, 31], "Model 2 (wt.%)": [52, 45, 39, 33]})
    sh["Model_Phase2"] = pd.DataFrame({"Additive (wt.%)": xx, "Measured (wt.%)": [10, 13, 17, 22], "Model 2 (wt.%)": [9, 12, 18, 24]})
    sh["Key"] = pd.DataFrame({"Label_code": ["X", "Xa", "Y"], "Meaning": ["Phase X", "Phase X, second form", "Phase Y"]})
    if plan:
        sh["Graphs"] = pd.DataFrame([
            {"Figure": "Fig 1", "Content": "Fit", "Layout": "one panel", "Sheets to use": "SampleA_Profile; SampleA_Bragg; Labels_SampleA", "X title": "2θ (°)", "Y title": "Intensity (counts)", "Extras": ""},
            {"Figure": "Fig 2", "Content": "Models", "Layout": "2 panels", "Sheets to use": "Model_Phase1, Model_Phase2", "X title": "Additive (wt.%)", "Y title": "Content (wt.%)", "Extras": "y 0 to 60"}])
    return sh


if __name__ == "__main__":
    out = sys.argv[1]
    with pd.ExcelWriter(out) as w:
        for k, v in book("--plan" in sys.argv).items(): v.to_excel(w, sheet_name=k, index=False)
    print(out)

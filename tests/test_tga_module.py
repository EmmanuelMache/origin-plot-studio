"""The TGA / DTG module of the app (acceptance check 9) and the label policy for zones (check 10)."""
import os, sys, tempfile, json
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["OPS_NO_OPEN"] = "1"
TMP = Path(tempfile.mkdtemp()); os.environ["OPS_SETTINGS_FILE"] = str(TMP / "settings_modern.json"); os.environ["OPS_PRIVATE_DIR"] = str(TMP / "private")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "origin_plot_app")); sys.path.insert(0, str(ROOT / "tests"))
import numpy as np, pandas as pd
N = [0, 0]
def check(name, cond, info=""):
    N[0 if cond else 1] += 1; print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
from test_tga_core import synthetic
import workspace_tga as TG
from opstudio import origin as O
T, m = synthetic(); a = TG.TgaAnalysis(T, m, "SYN")
check("three DTG peaks found near 120, 460 and 720 °C", len(a.peaks) == 3 and abs(sorted(p["T_peak"] for p in a.peaks)[1] - 460) < 3, [round(p["T_peak"]) for p in a.peaks])
pk = min(a.peaks, key=lambda p: abs(p["T_peak"] - 460)); check("onset and endset bracket the 460 °C peak", 430 < pk["onset"] < 460 < pk["endset"] < 490, (round(pk["onset"], 1), round(pk["endset"], 1)))
check("zones are suggested, every name is a suggestion with '?' until confirmed", len(a.zones) == 3 and all(not z["confirmed"] and a.label_of(z).endswith("?") for z in a.zones), [a.label_of(z) for z in a.zones])
check("no content is calculated for a zone that is not confirmed", not any(r.get("content_name") for r in a.rows()))
check("an unconfirmed name is never written in an export (final) label", all(a.label_of(z, final=True) == "" for z in a.zones))
fig = a.figure(); texts = [t.get_text() for t in fig.axes[0].texts]; check("the preview shows the suggestions with '?'", len(texts) == 3 and all(t.endswith("?") for t in texts), texts)
fin = a.figure(final=True); check("the exported graph leaves unconfirmed names out", [t.get_text() for t in fin.axes[0].texts] == [])
# the user sets the zones as in the reference test and confirms the names
i_ch = min(range(3), key=lambda i: abs(a.zones[i]["T_peak"] - 460)); i_cc = min(range(3), key=lambda i: abs(a.zones[i]["T_peak"] - 720))
a.set_edge(i_ch, 0, 400); a.set_edge(i_ch, 1, 530); a.set_edge(i_cc, 0, 620); a.set_edge(i_cc, 1, 820); a.settings["ignited_T"] = 1000
a.confirm(i_ch); a.confirm(i_cc); rows = a.rows(); ch = rows[i_ch]["content"]; cc = rows[i_cc]["content"]
check("check 9: Ca(OH)₂ within 0.5 wt.% of 12.3 (tangent method)", rows[i_ch]["content_name"] == "Ca(OH)2" and abs(ch - 12.34) < 0.5, round(ch, 2))
check("check 9: CaCO₃ within 0.5 wt.% of 4.5 (tangent method)", rows[i_cc]["content_name"] == "CaCO3" and abs(cc - 4.55) < 0.5, round(cc, 2))
check("stepwise and tangent losses are side by side; the stepwise one includes the background", rows[i_ch]["dm_stepwise"] > rows[i_ch]["dm_tangent"] and abs(rows[i_ch]["dm_tangent"] - 3.0) < 0.08, (round(rows[i_ch]["dm_stepwise"], 3), round(rows[i_ch]["dm_tangent"], 3)))
check("contents on the ignited basis are given when an ignition temperature is set", rows[i_ch]["content_ignited_basis"] > ch)
s = a.summary(); check("summary: total loss, residual mass, bound water, the contents", abs(s["total_loss (%)"] - (a.mass[0] - a.mass[-1])) < 1e-6 and abs(a.mass[0] - 100) < 1e-9 and "bound water (%)" in s and "Ca(OH)2 (wt.%)" in s, list(s))
out = str(TMP / "res.xlsx"); a.export_excel(out)
from openpyxl import load_workbook
wb = load_workbook(out); zs = [[c.value for c in r] for r in wb["Zones"].iter_rows(min_row=2)]
check("check 9: the Excel export opens with five sheets and the chart", wb.sheetnames == ["Data", "Peaks", "Zones", "Summary", "Chart"] and len(wb["Chart"]._charts) == 1, wb.sheetnames)
check("Excel: confirmed zones carry their name, the unconfirmed one has none", sorted(bool(z[0]) for z in zs) == [False, True, True], [z[0] for z in zs])
ch_ = wb["Chart"]._charts[0]; check("Excel chart: TG and DTG on two axes, DTG not reversed", len(ch_._charts) == 2 and ch_._charts[1].y_axis.scaling.orientation in (None, "minMax"))
summ = {r[0].value: r[1].value for r in wb["Summary"].iter_rows() if r[0].value}; check("Excel summary writes the settings and the formulas out", "DTG" in summ and "Formulas" in summ and "mass loss used" in summ, list(summ)[:6])
d = pd.read_excel(out, sheet_name="Data"); check("Excel data: temperature, mass and DTG at its natural sign (negative where mass is lost)", d.shape[1] == 3 and d.iloc[:, 2].min() < 0 and abs(d.iloc[:, 2].min()) > abs(d.iloc[:, 2].max()))
txt = a.table_text(); check("Copy table: tab-separated, one row per zone", len(txt.splitlines()) == 4 and txt.count("\t") >= 33)
R = O.read_figure(a.figure(final=True)); right = [L for L in R["layers"] if L["right_axis"]]
check("TG + DTG in one graph for Origin: DTG on the right axis, natural sign", len(R["layers"]) == 2 and len(right) == 1 and right[0]["y"][0] < right[0]["y"][1] and len(R["layers"][0]["zones"]) == 3)
# zones: add, split, merge, delete
n0 = len(a.zones); a.add_zone(250, 300); check("add a zone", len(a.zones) == n0 + 1)
i = next(k for k, z in enumerate(a.zones) if z["T"] == [250.0, 300.0]); a.split(i, 275); check("split a zone", len(a.zones) == n0 + 2)
a.merge(i); check("merge two zones (the name must be confirmed again)", len(a.zones) == n0 + 1 and not a.zones[i]["confirmed"]); a.delete_zone(i); check("delete a zone", len(a.zones) == n0)
# other mass references and units
b = TG.TgaAnalysis(T + 273.15, m * 0.2, "mg run", {"temperature_unit": "K", "normalise": "ignited", "T_ref": 1000.0, "heating_rate": 10.0, "dtg_unit": "% min⁻¹"})
check("K → °C, mg → % of the ignited mass, DTG in % per minute", abs(b.T[0] - 30) < 1e-6 and abs(b.mass[-1] - 100) < 1e-6 and b.dtg_shown()[1].startswith("DTG (% min") and abs(b.dtg_shown()[0].min() / b.dtg.min() - 10) < 1e-9)
check("the original arrays are not changed", m[0] == synthetic()[1][0] and len(a.mass_raw) == len(m))
st = TG.replicate_stats([TG.TgaAnalysis(T, m, "r1"), TG.TgaAnalysis(T, m + np.random.default_rng(1).normal(0, 0.01, len(m)), "r2"), TG.TgaAnalysis(T, m * 1.0, "r3")])
check("replicates: mean, SD and CoV of the summary values", any(r["quantity"] == "total_loss (%)" and r["n"] == 3 and r["SD"] >= 0 for r in st))
# ---- the window
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
app = QApplication.instance() or QApplication(sys.argv)
import workspace_qt as W
w = W.Workspace([]); w.show(); app.processEvents()
f = TMP / "run.csv"; pd.DataFrame({"Temperature (°C)": T, "Mass (%)": m}).to_csv(f, index=False)
check("the module is in the Tools menu and in the command search", w.tga_action.text().startswith("TGA / DTG analysis") and any("TGA / DTG analysis" in k for k in w.commands()))
dlg = w.tga_analysis(str(f)); app.processEvents()
check("check 10: the Confirm labels table is there the moment the graph is drawn, one row per zone, nothing confirmed", dlg is not None and dlg.table.rowCount() == 3 and all(dlg.table.item(i, 0).checkState() == Qt.Unchecked and dlg.table.item(i, 1).text().endswith("?") for i in range(3)))
check("each row shows the suggestion, other candidates, the confidence and the source", "Other candidates" in dlg.table.item(1, 1).toolTip() and dlg.table.item(1, 12).text() in ("low", "medium") and "literature" in dlg.table.item(1, 12).toolTip())
dlg.table.item(1, 0).setCheckState(Qt.Checked); app.processEvents()
check("ticking Confirm makes the name the user's: the phase and its content appear", dlg.a.zones[1]["confirmed"] and dlg.table.item(1, 10).text().startswith("Ca(OH)2"), dlg.table.item(1, 10).text())
dlg.table.item(2, 1).setText("My carbonate"); app.processEvents(); check("a name typed by the user replaces the suggestion", dlg.a.zones[2]["name"] == "My carbonate" and dlg.a.zones[2]["confirmed"])
dlg.table.item(1, 3).setText("400"); dlg.table.item(1, 4).setText("530"); app.processEvents(); check("typing a temperature moves a zone edge", dlg.a.zones[1]["T"] == [400.0, 530.0])
class Ev:                                               # dragging an edge on the graph
    def __init__(s, x): s.button = 1; s.xdata = x; s.inaxes = dlg.a.ax
dlg._press(Ev(530.0)); dlg._move(Ev(540.0)); dlg._release(Ev(540.0)); check("dragging a zone edge on the graph moves it", abs(dlg.a.zones[1]["T"][1] - 540) < 1e-6, dlg.a.zones[1]["T"])
x = dlg.export(str(TMP / "dlg.xlsx")); check("Export results → Excel from the window", load_workbook(x).sheetnames == ["Data", "Peaks", "Zones", "Summary", "Chart"])
g = dlg.save_graph(str(TMP / "g.png")); check("Save graph writes the picture", os.path.getsize(g) > 5000)
dlg.force_dry = True; r = dlg.origin(str(TMP / "o")); check("Draw in Origin like this: saved as {sample}_tga_dtg.opju", r["project"].endswith("run_tga_dtg.opju") and len(r["commands"]) > 40)
dlg.material.setText("test paste"); dlg._material(); TG.remember_labels("test paste", dlg.a)
c = TG.TgaAnalysis(T, m, "next"); n = TG.offer_remembered("test paste", c)
check("confirmed names are remembered per material and offered first - still as suggestions", n >= 2 and any(z["suggested"] == "My carbonate" for z in c.zones) and not any(z["confirmed"] for z in c.zones), [z["suggested"] for z in c.zones])
dlg.close(); w.close()
print(f"\n{N[0]} passed, {N[1]} failed"); sys.exit(1 if N[1] else 0)

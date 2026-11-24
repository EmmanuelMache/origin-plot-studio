"""Known-answer tests for tga_core (run: python -m pytest test_tga_core.py  or  python test_tga_core.py)."""
import os, tempfile
import numpy as np
import sys; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'origin_plot_app'))
from opstudio import tga_core as tc


def synthetic(ch_water=3.0, co2=2.0):
    T = np.linspace(30, 1000, 2911)
    m = 100 - 6 / (1 + np.exp(-(T - 120) / 18)) - ch_water / (1 + np.exp(-(T - 460) / 9)) - co2 / (1 + np.exp(-(T - 720) / 14))
    m -= 0.002 * (T - 30)  # slow background (C-S-H continues to lose water)
    return T, m


def test_tangent_recovers_step():
    T, m = synthetic()
    r = tc.tangent_step(T, m, 400, 530)
    assert abs(r["dm"] - 3.0) < 0.08, r["dm"]          # tangent removes background
    assert tc.stepwise_loss(T, m, 400, 530) > r["dm"]   # stepwise includes background


def test_peaks_and_onset():
    T, m = synthetic(); d = tc.dtg(T, m)["dtg_per_C"]
    pk = tc.find_dtg_peaks(T, d)
    Tp = sorted(p["T_peak"] for p in pk)
    assert len(Tp) == 3 and abs(Tp[1] - 460) < 3 and abs(Tp[2] - 720) < 3, Tp
    oe = tc.onset_endset(T, m, d, 460)
    assert 430 < oe["onset"] < 460 < oe["endset"] < 490, oe


def test_quantify_and_export():
    T, m = synthetic(); d = tc.dtg(T, m)["dtg_per_C"]
    zones = [{"name": "Portlandite", "T": [400, 530], "species": "CH"}, {"name": "Calcite", "T": [620, 820], "species": "CaCO3"}]
    rows, summ = tc.quantify(T, m, zones, ignited_T=1000)
    ch = rows[0]["content"]; cc = rows[1]["content"]
    assert abs(ch - 3.0 * 74.093 / 18.015) < 0.4, ch
    assert abs(cc - 2.0 * 100.087 / 44.009) < 0.4, cc
    sz = tc.suggest_zones(T, d)
    assert all(z["needs_confirmation"] for z in sz)
    out = os.path.join(tempfile.mkdtemp(), "tga_test.xlsx")
    tc.export_excel(out, "SYN", T, m, d, tc.find_dtg_peaks(T, d), rows, summ, {"dtg_window_C": 15})
    from openpyxl import load_workbook
    wb = load_workbook(out); assert set(["Data", "Peaks", "Zones", "Summary", "Chart"]) <= set(wb.sheetnames)
    return ch, cc, sz


if __name__ == "__main__":
    test_tangent_recovers_step(); test_peaks_and_onset(); ch, cc, sz = test_quantify_and_export()
    print(f"OK  CH={ch:.2f} wt.% (expected 12.34)  CaCO3={cc:.2f} wt.% (expected 4.55)")
    for z in sz:
        print(f"  zone {z['T'][0]:.0f}-{z['T'][1]:.0f} °C  peak {z['T_peak']:.0f} °C  suggested: {z['suggested']} [{z['confidence']}] -> ASK USER")

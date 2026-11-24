"""Synthetic HighScore exports, written the way HighScore Plus writes them with a comma as the decimal sign and as the separator:
a fit (No., Pos., Iobs, Icalc, Iback ...) and a peak list (Assignment, h k l, Height ...). The numbers are invented."""
import numpy as np

PHASES = [("COD9014308_Aluminate_C3A_orthorhombic_Na_bearing", [(33.2, 3000), (47.6, 700), (59.3, 500)]),
          ("COD9012789_Belite_beta_larnite", [(32.1, 1800), (32.6, 1500), (41.2, 600), (62.5, 300)]),
          ("COD9015662_Portlandite", [(18.0, 900), (34.1, 1100), (47.1, 500), (50.8, 450)]),
          ("COD9004141_Rutile", [(27.45, 2200), (36.1, 900), (54.3, 800)]),
          ("COD1540704_Alite_M3_average_cell", [(29.4, 0.0), (51.7, 0.0)])]      # a phase with a calculated height of 0 (scale factor 0)


def _c(v, nd=4):
    return f"{v:.{nd}f}".replace(".", ",")


def pattern(seed=0, shift=0.0, scale=1.0, lo=5.0, hi=70.0, step=0.013):
    rng = np.random.default_rng(seed)
    x = np.arange(lo, hi, step)
    bg = 900 * np.exp(-(x - lo) / 8) + 400
    calc = bg.copy()
    for _, refl in PHASES:
        for p, h in refl:
            calc += scale * h * np.exp(-0.5 * ((x - p - shift) / 0.07) ** 2)
    obs = rng.poisson(calc).astype(float)
    return x, obs, calc, bg


def write_fit(path, seed=0, shift=0.0, scale=1.0):
    x, obs, calc, bg = pattern(seed, shift, scale)
    with open(path, "w", encoding="latin-1", newline="\r\n") as f:
        f.write("No.,Pos. [\xb02Th.],Iobs [cts],Icalc [cts],Iback [cts],Icalc [cps],Iback [cps],CT [s],ESD,D spacings\n")
        for i, (a, o, c, b) in enumerate(zip(x, obs, calc, bg), 1):
            d = 1.5406 / (2 * np.sin(np.radians(a / 2)))
            f.write(f"{i},{_c(a)},{_c(o)},{_c(c)},{_c(b)},{_c(c / 954.72)},{_c(b / 954.72)},{_c(954.72)}, ,{_c(d)}\n")
    return path


def write_peaklist(path, shift=0.0, scale=1.0):
    rows = []
    for name, refl in PHASES:
        for p, h in refl:
            rows.append((p + shift, name, h * scale))
    rows.sort()
    with open(path, "w", encoding="latin-1", newline="\r\n") as f:
        f.write("No.,Pos. [\xb02Th.],FWHM Left [\xb02Th.],Area calc.,Assignment,h,k,l,Multiplicity,Backgr.[cts],d-spacing [\xc5],Height [cts],"
                "Matched by,Shape Left,Source,Status,Crystallite Size only [\xc5],Micro Strain only [%]\n")
        for i, (p, name, h) in enumerate(rows, 1):
            d = 1.5406 / (2 * np.sin(np.radians(p / 2)))
            f.write(f"{i},{_c(p)},{_c(0.165)},{_c(h * 0.18, 2)},{name},1,1,0,4,{_c(500.0, 2)},{_c(d, 5)},{int(round(h))}(50), ,{_c(0.6, 3)},"
                    f"Rietveld refinement,Included,{_c(400.0, 6)},{_c(0.05, 6)}\n")
    return path

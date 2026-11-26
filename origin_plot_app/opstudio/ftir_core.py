"""
ftir_core.py - what an infrared band may be, from where it lies.

Nothing here assigns a band with certainty. `suggest(position)` returns the usual assignments for a wavenumber, the
most central first; the app writes them as possibilities ("may be") and draws a name only when the user asks for the
labels. Ranges overlap (a band near 875 cm-1 is the carbonate out-of-plane bend in most cements, but aluminate and
silicate bands lie close by), they shift with composition and crystallinity, and a weak band can be noise.
"""
from __future__ import annotations

# (name, short label for a graph, [from, to] in cm-1, where it is usually seen)
REFERENCE_BANDS = [
    {"name": "O-H stretch of kaolinite / brucite (free hydroxyl)", "short": "O–H (kaolinite / brucite)", "range": [3680, 3705], "applies_to": "clays, MgO-rich binders"},
    {"name": "O-H stretch of portlandite Ca(OH)2", "short": "O–H (Ca(OH)₂)", "range": [3635, 3650], "applies_to": "hydrated cement, slaked lime"},
    {"name": "O-H stretch of clay minerals (inner hydroxyl)", "short": "O–H (clay)", "range": [3610, 3630], "applies_to": "kaolinite, illite, smectite"},
    {"name": "O-H stretch of water (bound and adsorbed H2O; C-S-H, ettringite, gypsum)", "short": "O–H (H₂O)", "range": [3100, 3600], "applies_to": "hydrates, moist samples"},
    {"name": "C-H stretch (organic matter, admixtures, grinding aids)", "short": "C–H", "range": [2840, 2980], "applies_to": "organics"},
    {"name": "Carbonate combination band (calcite, v1 + v3)", "short": "CO₃²⁻ (comb.)", "range": [2500, 2530], "applies_to": "calcite-rich samples"},
    {"name": "CO2 of the air in the beam path (not the sample)", "short": "CO₂ (air)", "range": [2300, 2390], "applies_to": "any spectrum without a good background"},
    {"name": "Carbonate combination band (calcite, v1 + v4)", "short": "CO₃²⁻ (comb.)", "range": [1785, 1805], "applies_to": "calcite-rich samples"},
    {"name": "H-O-H bending of water (hydrates; doublet near 1620 and 1685 in gypsum)", "short": "H–O–H", "range": [1600, 1700], "applies_to": "hydrates, moist samples"},
    {"name": "Carbonate v3 asymmetric stretch (calcite near 1420-1430; vaterite, aragonite higher)", "short": "ν₃ CO₃²⁻", "range": [1390, 1500], "applies_to": "carbonate rocks, carbonated paste"},
    {"name": "Sulfate v3 stretch (ettringite near 1110, gypsum 1110-1140, AFm)", "short": "ν₃ SO₄²⁻", "range": [1095, 1160], "applies_to": "cement, hydrates, gypsum"},
    {"name": "Si-O stretch of quartz", "short": "Si–O (quartz)", "range": [1070, 1095], "applies_to": "sand, tailings, fly ash"},
    {"name": "Si-O-Si / Si-O-Al stretch (clays, glass of slag and fly ash, alkali-activated gel)", "short": "Si–O–T", "range": [1000, 1060], "applies_to": "clays, SCMs, geopolymers"},
    {"name": "Si-O stretch of C-S-H (Q2 chains)", "short": "Si–O (C-S-H)", "range": [940, 1000], "applies_to": "hydrated cement"},
    {"name": "Si-O stretch of alite / belite (unhydrated clinker); Al-OH bend of kaolinite near 912", "short": "Si–O (clinker)", "range": [900, 940], "applies_to": "clinker, cement, clays"},
    {"name": "Carbonate v2 out-of-plane bend (calcite near 875)", "short": "ν₂ CO₃²⁻", "range": [865, 882], "applies_to": "carbonate rocks, carbonated paste"},
    {"name": "Carbonate v2 of aragonite / Al-OH of ettringite", "short": "ν₂ CO₃²⁻ (aragonite) / Al–OH", "range": [845, 862], "applies_to": "aragonite, ettringite"},
    {"name": "Si-O of quartz (doublet near 798 and 779)", "short": "Si–O (quartz)", "range": [772, 802], "applies_to": "sand, tailings, fly ash"},
    {"name": "Carbonate v4 of vaterite", "short": "ν₄ CO₃²⁻ (vaterite)", "range": [738, 750], "applies_to": "carbonated paste"},
    {"name": "Carbonate v4 in-plane bend (calcite near 712; aragonite 700 and 713)", "short": "ν₄ CO₃²⁻", "range": [698, 716], "applies_to": "carbonate rocks, carbonated paste"},
    {"name": "Sulfate v4 bend (gypsum near 669 and 602; ettringite near 620)", "short": "ν₄ SO₄²⁻", "range": [595, 675], "applies_to": "gypsum, hydrates"},
    {"name": "Si-O bend of alite / belite (near 520)", "short": "δ Si–O (clinker)", "range": [505, 535], "applies_to": "clinker, cement"},
    {"name": "Si-O-Si bend (silicates, C-S-H, quartz)", "short": "δ Si–O–Si", "range": [430, 480], "applies_to": "silicates"},
]
SOURCE_NOTE = ("Usual band positions from the infrared literature of cements, hydrates and common minerals; ranges overlap and "
               "shift with composition and crystallinity - confirm every assignment for your sample.")


def suggest(position):
    """The reference bands whose range holds this wavenumber, the one it lies most centrally in first."""
    p = float(position); c = [b for b in REFERENCE_BANDS if b["range"][0] <= p <= b["range"][1]]
    c.sort(key=lambda b: abs(p - (b["range"][0] + b["range"][1]) / 2.0) / ((b["range"][1] - b["range"][0]) / 2.0))
    return c

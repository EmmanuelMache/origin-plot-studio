"""signatures.py - what makes two files "the same format": a canonical STRUCTURAL signature, versioned.

A signature is built only from things that legitimately identify an export format: the container (csv, xlsx ...), the
delimiter and decimal sign, whether there is a header row, the normalised column headers with their declared units,
the column layout (order and count) and a permitted instrument descriptor. Never from measured rows, file names,
paths, sheet names or sample names.

Two signatures exist side by side:

    structural_signature(...)   "s2:<hex>"   LOCAL. Uses the normalised header words of the file. A hash does not make a
                                             private header anonymous, so this one never leaves the computer.
    shareable_signature(...)    "p2:<hex>"   Built ONLY from the sanitised projection: every header replaced by a
                                             recognised structural role ('two_theta', 'intensity' ... or 'unknown') and
                                             every unit by a known unit (or 'other'). This is what a shared record carries.

Versions: SIGNATURE_VERSION = 2 is this algorithm. Entries of the earlier smart_plots.layout_signature() are imported
as version 1 (LEGACY_SIGNATURE_VERSION) and stay labelled 1: an old signature is never relabelled as a new one.

Normalisation keeps scientific meaning: '2θ', '2Theta' and '2theta' are one header, 'theta' is another; a unit written
in the header ('Temperature (°C)') is kept as the unit of that column, not thrown away.

Standard library only. describe_table() accepts an opstudio.data.Table but does not import pandas itself.
"""
import hashlib, json, re, unicodedata

SIGNATURE_VERSION = 2
LEGACY_SIGNATURE_VERSION = 1
MAX_COLUMNS = 512

# ------------------------------------------------------------------------------------------------ headers
_UNIT_TAIL = re.compile(r"^(?P<name>.*?)[\s_]*[\(\[\{](?P<unit>[^\(\)\[\]\{\}]{0,24})[\)\]\}]\s*$")
_UNIT_SLASH = re.compile(r"^(?P<name>[^/]{1,60}?)\s+/\s+(?P<unit>[^/\s][^\s]{0,15})\s*$")


def _fold(text):
    t = str(text if text is not None else "").strip()
    t = (t.replace("θ", "theta").replace("ϑ", "theta").replace("Θ", "theta").replace("µ", "u").replace("μ", "u")
         .replace("λ", "lambda").replace("Å", "angstrom").replace("å", "angstrom").replace("Ω", "ohm").replace("−", "-"))
    return unicodedata.normalize("NFKC", t)


def norm_header(text):
    """The header as a comparison word: lower case, Greek theta/mu spelled out, everything that is not a letter or a
    digit removed. Digits stay ('2theta' is not 'theta'). At most 64 characters."""
    t = _fold(text).lower().replace("°", "deg")
    return re.sub(r"[^a-z0-9]+", "", t)[:64]


def split_header(text):
    """('header word', 'canonical unit') of a column header. The unit is read from a bracket at the end
    ('Mass (%)', '2θ [°]') or after ' / ' ('Intensity / a.u.'); '' when the header declares none this table knows."""
    raw = _fold(text)
    m = _UNIT_TAIL.match(raw) or _UNIT_SLASH.match(raw)
    if m and m.group("name").strip():
        u = norm_unit(m.group("unit"))
        if unit_known(u): return norm_header(m.group("name")), u          # a bracket that is not a known unit stays part of the header word
    return norm_header(raw), ""


# ------------------------------------------------------------------------------------------------ units
_UNIT_EXACT = {"MPa": "MPa", "mPa": "mPa", "mPa.s": "mPa_s", "mPa·s": "mPa_s", "mPas": "mPa_s", "MW": "MW", "mW": "mW", "A": "A", "K": "K",
               "mV": "mV", "V": "V", "W": "W", "N": "N", "J": "J", "g": "g", "m": "m", "s": "s", "h": "h", "d": "d", "Pa": "Pa", "M": "mol_per_L"}
_UNIT_ALIASES = {
    "degree": ("deg", "degree", "degrees", "deg2theta", "2thetadeg", "degtwotheta", "deg2th", "2theta", "deg2thet"),
    "radian": ("rad", "radian", "radians"),
    "angstrom": ("angstrom", "angstroms", "ang"), "nm": ("nm",), "um": ("um", "micron", "microns", "micrometer", "micrometre"),
    "mm": ("mm",), "cm": ("cm",),
    "per_angstrom": ("angstrom-1", "1/angstrom", "angstrom^-1"), "per_nm": ("nm-1", "1/nm", "nm^-1"),
    "per_cm": ("cm-1", "1/cm", "cm^-1", "wavenumber", "wavenumbers"),
    "count": ("count", "counts", "cts", "ct"),
    "count_per_second": ("cps", "counts/s", "cts/s", "count/s", "counts/sec", "c/s"),
    "arbitrary": ("a.u.", "a.u", "au", "arb.u.", "arb.u", "arb.units", "arb.unit", "arbitraryunits", "arb", "arb."),
    "percent": ("%", "percent", "pct"),
    "weight_percent": ("wt%", "wt.%", "mass%", "weight%", "wtpercent", "m%", "wt-%", "mass-%"),
    "volume_percent": ("vol%", "vol.%", "volume%", "vol-%"), "mol_percent": ("mol%", "mol.%", "mol-%"),
    "degC": ("degc", "celsius", "degcelsius"), "K": ("kelvin",),
    "s": ("sec", "second", "seconds"), "min": ("min", "minute", "minutes"), "h": ("hr", "hrs", "hour", "hours"), "d": ("day", "days"),
    "ug": ("ug",), "mg": ("mg",), "kg": ("kg",),
    "uW": ("uw",), "mW_per_g": ("mw/g",), "W_per_g": ("w/g",), "uV": ("uv",), "uV_per_mg": ("uv/mg",), "mW_per_mg": ("mw/mg",),
    "J_per_g": ("j/g",), "kJ_per_mol": ("kj/mol",), "kJ_per_kg": ("kj/kg",),
    "GPa": ("gpa",), "kPa": ("kpa",), "N_per_mm2": ("n/mm2", "n/mm^2"), "kN": ("kn",),
    "Pa_s": ("pa.s", "pas", "pa*s"), "per_s": ("1/s", "s-1", "s^-1"),
    "mA": ("ma",), "uA": ("ua",), "ohm": ("ohm", "ohms"), "Hz": ("hz",), "kHz": ("khz",),
    "ppm": ("ppm",), "percent_per_degC": ("%/degc",), "percent_per_min": ("%/min",), "mg_per_min": ("mg/min",),
    "mL_per_g": ("ml/g", "cm3/g", "cm^3/g"), "m2_per_g": ("m2/g", "m^2/g"), "g_per_cm3": ("g/cm3", "g/cm^3"), "kg_per_m3": ("kg/m3", "kg/m^3"),
    "mol_per_L": ("mol/l",), "mmol_per_L": ("mmol/l",), "mg_per_L": ("mg/l",),
}
_UNIT_LOOKUP = {a: u for u, al in _UNIT_ALIASES.items() for a in al}
_DIMENSION = {
    "degree": "angle", "radian": "angle", "angstrom": "length", "nm": "length", "um": "length", "mm": "length", "cm": "length", "m": "length",
    "per_angstrom": "inverse_length", "per_nm": "inverse_length", "per_cm": "inverse_length",
    "count": "count", "count_per_second": "count_rate", "arbitrary": "arbitrary",
    "percent": "fraction", "weight_percent": "fraction", "volume_percent": "fraction", "mol_percent": "fraction", "ppm": "fraction",
    "degC": "temperature", "K": "temperature", "s": "time", "min": "time", "h": "time", "d": "time",
    "ug": "mass", "mg": "mass", "g": "mass", "kg": "mass",
    "uW": "power", "mW": "power", "W": "power", "MW": "power", "mW_per_g": "specific_power", "W_per_g": "specific_power", "mW_per_mg": "specific_power",
    "uV": "voltage", "mV": "voltage", "V": "voltage", "uV_per_mg": "specific_voltage",
    "J": "energy", "J_per_g": "specific_energy", "kJ_per_kg": "specific_energy", "kJ_per_mol": "molar_energy",
    "Pa": "pressure", "kPa": "pressure", "MPa": "pressure", "GPa": "pressure", "N_per_mm2": "pressure", "mPa": "pressure",
    "N": "force", "kN": "force", "Pa_s": "viscosity", "mPa_s": "viscosity", "per_s": "rate",
    "A": "current", "mA": "current", "uA": "current", "ohm": "resistance", "Hz": "frequency", "kHz": "frequency",
    "percent_per_degC": "fraction_rate_T", "percent_per_min": "fraction_rate_t", "mg_per_min": "mass_rate",
    "mL_per_g": "specific_volume", "m2_per_g": "specific_area", "g_per_cm3": "density", "kg_per_m3": "density",
    "mol_per_L": "concentration", "mmol_per_L": "concentration", "mg_per_L": "mass_concentration",
}
KNOWN_UNITS = frozenset(_DIMENSION)


def norm_unit(text):
    """The canonical unit of a unit text ('°' -> 'degree', 'cts' -> 'count', '°C' -> 'degC', 'a.u.' -> 'arbitrary').
    An already canonical unit is returned as it is. A unit this table does not know is kept as a short harmless word
    (letters, digits and / % ^ . * - only, 16 characters) so that it still distinguishes two formats locally; such a
    word is never shared (see KNOWN_UNITS). '' when nothing is declared."""
    if text is None: return ""
    raw = _fold(text).strip()
    if not raw: return ""
    if raw in KNOWN_UNITS: return raw
    if raw in _UNIT_EXACT: return _UNIT_EXACT[raw]
    t = raw.lower().replace("°", "deg").replace("·", ".").replace("⁻¹", "-1").replace("²", "2").replace("³", "3")
    t = re.sub(r"\s+", "", t)
    if t in ("deg", "degrees", "degree"): return "degree"
    if t in ("degc", "c") and ("°" in raw or "deg" in raw.lower()): return "degC"
    if t in _UNIT_LOOKUP: return _UNIT_LOOKUP[t]
    for canonical in KNOWN_UNITS:
        if t == canonical.lower(): return canonical
    return re.sub(r"[^a-z0-9/%^.*\-]", "", t)[:16]


def unit_known(unit): return unit in KNOWN_UNITS
def unit_dimension(unit): return _DIMENSION.get(unit, "")


def units_conflict(a, b):
    """True when both units are declared and are not the same unit. 'degree' against 'radian', or 'degC' against 'K', is
    a conflict as well: a saved mapping is applied without converting anything, so a different unit of the same quantity
    must not pass silently. An undeclared unit ('') conflicts with nothing - and proves nothing."""
    return bool(a) and bool(b) and a != b


# ------------------------------------------------------------------------------------------------ structural roles
# Ordered: the first pattern that matches the normalised header names the structural role of the column.
_ROLE_PATTERNS = (
    ("two_theta", r"2theta|twotheta|2th(?![a-z])|2thet"),
    ("d_spacing", r"dspacing|dspace|dvalue|dhkl|^d$|^dangstrom$"),
    ("theta", r"theta"),
    ("q", r"^q$|^qvector|scatteringvector|^qangstrom|^qnm"),
    ("calculated", r"calc|fitted|^yfit|^fit$|simulated|modelled"),
    ("difference", r"diff|residual|obscalc"),
    ("background", r"bkg|bgr|background"),
    ("raman_shift", r"ramanshift"),
    ("wavenumber", r"wavenumber|wavenum|cm1$"),
    ("chemical_shift", r"chemicalshift"),
    ("absorbance", r"absorbance|^abs$"),
    ("transmittance", r"transmittance|transmission"),
    ("temperature", r"temperature|^temp|celsius|degc$"),
    ("dtg", r"^dtg|derivativemass|derivativeweight|dmdt"),
    ("heat_flow", r"heatflow|heatflux|thermalpower|^dsc|^power"),
    ("heat", r"^heat|cumulativeheat|totalheat"),
    ("time", r"^time|time$|elapsed|^hours?$|^minutes?$|^seconds?$|^age"),
    ("mass", r"mass|weight|^tg$|^tgpercent"),
    ("pore_diameter", r"porediameter|poresize|poreradius"),
    ("particle_size", r"particlesize|diameter|^size|micron"),
    ("cumulative", r"cumulative|passing|undersize"),
    ("volume_fraction", r"volume|differential"),
    ("shear_rate", r"shearrate"), ("shear_stress", r"shearstress"), ("viscosity", r"viscosity"),
    ("impedance_real", r"zreal|^zre|zprime$"), ("impedance_imag", r"zimag|^zim|zdoubleprime"),
    ("frequency", r"frequency|^freq"),
    ("potential", r"potential|voltage"), ("current", r"current"),
    ("strength", r"strength|compressive|flexural"), ("stress", r"stress"), ("strain", r"strain"), ("load", r"^load|force"),
    ("pressure", r"pressure|^pp0"),
    ("intensity", r"intensity|counts?$|^counts?|cps|^iobs|^yobs|observed|^int$|height|signal"),
    ("error", r"^sd$|^std|stdev|error$|^err|uncertainty|^esd"),
    ("index", r"^no$|^nr$|^index$|^row$|^id$"),
)
_ROLE_RE = tuple((role, re.compile(p)) for role, p in _ROLE_PATTERNS)
KNOWN_ROLES = tuple(r for r, _ in _ROLE_PATTERNS) + ("unknown", "other")


def classify_header(token):
    """The recognised structural role of a normalised header ('2theta' -> 'two_theta', 'intensitycps' -> 'intensity'),
    or 'unknown'. This is a reading of the header WORD only; it is not evidence about the measurement."""
    word = str(token or "").strip().lower()
    if word in KNOWN_ROLES: return "unknown" if word == "other" else word          # already a role word (a sanitised projection): it stays what it is
    t = norm_header(token)
    if not t: return "unknown"
    for role, rx in _ROLE_RE:
        if rx.search(t): return role
    return "unknown"


# ------------------------------------------------------------------------------------------------ signatures
def _digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()[:32]


def canonical(container, delimiter, decimal, has_header, headers, units, instrument=""):
    """The canonical description a version-2 structural signature is the digest of (a plain dict)."""
    headers = [norm_header(h) for h in list(headers or [])[:MAX_COLUMNS]]
    units = [norm_unit(u) for u in list(units or [])[:MAX_COLUMNS]]
    units += [""] * (len(headers) - len(units))
    return {"v": SIGNATURE_VERSION, "container": str(container or "other"), "delimiter": str(delimiter or ""), "decimal": str(decimal or "."),
            "header": bool(has_header), "columns": [[h, u] for h, u in zip(headers, units)], "instrument": str(instrument or "")}


def structural_signature(container, delimiter, decimal, has_header, headers, units, instrument=""):
    """'s2:<hex>' - LOCAL signature of an export format (version 2). Same container, separators, header words, units and
    column order give the same signature; the measured values play no part."""
    return "s2:" + _digest(canonical(container, delimiter, decimal, has_header, headers, units, instrument))


def shareable_columns(headers, units):
    """[[role, unit]] per column: the recognised structural role of each header and its known unit ('other' for a unit
    this table does not know, '' for none). No header text survives this projection."""
    headers = list(headers or [])[:MAX_COLUMNS]; units = list(units or [])[:MAX_COLUMNS]; units += [""] * (len(headers) - len(units))
    out = []
    for h, u in zip(headers, units):
        u = norm_unit(u)
        out.append([classify_header(h), u if unit_known(u) else ("other" if u else "")])
    return out


def shareable_signature(container, delimiter, decimal, has_header, headers, units):
    """'p2:<hex>' - the signature a SHARED record carries. Computed from the sanitised projection only (roles and known
    units, see shareable_columns), never from header text, rows or names. The instrument descriptor is left out."""
    return "p2:" + _digest({"v": SIGNATURE_VERSION, "container": str(container or "other"), "delimiter": str(delimiter or ""), "decimal": str(decimal or "."),
                            "header": bool(has_header), "columns": shareable_columns(headers, units)})


def signature_version_of(signature):
    """2 for 's2:'/'p2:' signatures of this module, 1 for anything else (a legacy layout_signature() string)."""
    return SIGNATURE_VERSION if str(signature or "").startswith(("s2:", "p2:")) else LEGACY_SIGNATURE_VERSION


def is_shareable_signature(signature): return bool(re.match(r"^p2:[0-9a-f]{32}$", str(signature or "")))


# ------------------------------------------------------------------------------------------------ helper for the app
def describe_table(table, *, container="other", delimiter="", decimal=".", encoding="", header_row=0, **more):
    """A raw context dict (for models.Context.build) from an opstudio.data.Table: the column headers, the units their
    headers declare, and per column whether usable numeric values exist. The values themselves are not read into the
    result. `more` passes through the other allowlisted context fields (data_family, file_id, sheet_id ...)."""
    cols = [str(c) for c in getattr(table, "cols", [])][:MAX_COLUMNS]
    numeric = set(str(c) for c in getattr(table, "numeric", []))
    raw = {"container": container, "delimiter": delimiter, "decimal": decimal, "encoding": encoding, "header_row": header_row,
           "headers": cols, "numeric_ok": [c in numeric for c in cols]}
    raw.update(more)
    return raw

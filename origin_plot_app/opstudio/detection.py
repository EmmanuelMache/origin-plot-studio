"""Shared conservative scientific detection and Analysis-template compatibility."""
from dataclasses import dataclass, asdict
import re
import unicodedata
import numpy as np

KINDS = ['Unknown', 'XRD', 'FTIR', 'Raman', 'NMR', 'TGA', 'DSC', 'Calorimetry',
         'Particle size', 'Porosity and surface', 'Thermodynamic modelling', 'Composition', 'Microstructure and SEM-EDS',
         'Cement and concrete', 'Strength', 'Rheology', 'Electrochemistry', 'Sustainability and CO2', 'Analytical chemistry',
         'Physics and signal', 'Life science', 'Environment and geoscience', 'Flow network', 'Category table', 'General XY']

# Kinds that stand for one whole class of the Analysis catalogue: choosing one shows that class's installed templates
# (each still checked against the real columns). The class names are the catalogue's own, so a template added to a
# class is offered without a change here.
CATEGORY_KINDS = {
    'Thermodynamic modelling': 'Thermodynamic modelling', 'Microstructure and SEM-EDS': 'Microstructure & SEM-EDS',
    'Cement and concrete': 'Cement & concrete engineering', 'Sustainability and CO2': 'Sustainability & CO2',
    'Analytical chemistry': 'Analytical chemistry', 'Physics and signal': 'Physics & signal',
    'Life science': 'Life science & medicine', 'Environment and geoscience': 'Environment & geoscience',
}

_FIT_ROLES = (('obs', r'^(?:y|i|int|intensity)?(?:obs|observed|meas|measured|exp|experimental)'),
              ('calc', r'^(?:y|i|int|intensity)?(?:calc|calculated|fit|fitted|model|modelled|sim|simulated)'),
              ('diff', r'^(?:y|i|int|intensity)?(?:diff|difference|residual|obscalc|delta)'),
              ('back', r'^(?:y|i|int|intensity)?(?:back|bkg|bgr|background)'))


def fit_columns(table):
    """The observed / calculated / difference / background columns of a pattern-and-fit table, by their names:
    {'obs': col, 'calc': col, ...} with only the roles that are named. Nothing is guessed from the column order."""
    out = {}
    for c in table.ys:
        n = normalise(c)
        for role, pat in _FIT_ROLES:
            if role not in out and re.match(pat, n): out[role] = c; break
    return out


def xrd_form(table):
    """What kind of diffraction table this is, from its column names: 'fit' (a calculated curve beside the observed
    one), 'peak list' (positions with widths, areas or hkl - not a measured scan) or 'scan'."""
    names = [normalise(c) for c in table.cols]
    if fit_columns(table).get('calc'): return 'fit'
    hkl = {'h', 'k', 'l'} <= set(names)
    if hkl or any(k in n for n in names for k in ('fwhm', 'breadth', 'peakarea', 'areacalc', 'areaobs', 'crystallitesize', 'microstrain', 'relint')): return 'peak list'
    return 'scan'


def normalise(value):
    text = str(value).lower().replace('θ', 'theta').replace('ϑ', 'theta').replace('µ', 'u').replace('μ', 'u')
    text = unicodedata.normalize('NFKC', text).replace('−', '-')
    return re.sub(r'[^a-z0-9]+', '', text)


@dataclass(frozen=True)
class Detection:
    kind: str
    confidence: str
    evidence: tuple
    confirmed: bool = False
    form: str = ''                 # for XRD: 'scan', 'fit' or 'peak list' (xrd_form) - read from the columns, also when you chose the type yourself

    @property
    def needs_confirmation(self):
        return self.kind == 'Unknown' or self.confidence == 'tentative'

    def to_dict(self):
        return asdict(self)


def detect(table, override=None):
    cols = list(table.numeric)
    names = {c: normalise(c) for c in cols}
    def find(*keys):
        return next((c for c in cols if any(k in names[c] for k in keys)), None)
    if override and override != 'Automatic':
        return Detection(override, 'confirmed', ('Measurement type selected by you',), True, xrd_form(table) if override == 'XRD' else '')
    all_names = [normalise(c) for c in table.cols]
    if 'source' in all_names and 'target' in all_names and cols:
        return Detection('Flow network', 'high', ('Source, target and numeric flow values detected',))
    if len(cols) >= 1 and table.text and len(cols) < 2:
        return Detection('Category table', 'generic', ('Category labels and numeric values detected',))
    if len(cols) < 2:
        return Detection('Unknown', 'tentative', ('At least two numeric columns are needed for a curve',))
    angle = find('2theta', 'twotheta', '2th', 'position2theta')
    signal = find('intensity', 'counts', 'count', 'cps', 'iobs', 'yobs', 'observed', 'height', 'relint')
    if angle:
        ev = [f'Angle column: {angle}']; form = xrd_form(table)
        if form == 'peak list':
            return Detection('XRD', 'high', tuple(ev + ['Peak list: positions with widths, areas or hkl (not a measured scan)']), False, form)
        if form == 'fit':
            f = fit_columns(table)
            return Detection('XRD', 'high', tuple(ev + [f"Calculated curve: {f['calc']}" + (f"; observed: {f['obs']}" if f.get('obs') else '')]), False, form)
        if signal:
            ev.append(f'Intensity column: {signal}')
            return Detection('XRD', 'high', tuple(ev), False, form)
        return Detection('XRD', 'tentative', tuple(ev + ['Confirm that the remaining values are diffraction intensities']), False, form)
    if find('chemicalshift'):
        return Detection('NMR', 'high', ('Chemical-shift column detected',))
    pore = find('porediameter', 'poresize', 'poreradius', 'intrusion', 'dvdlogd')
    if pore or find('relativepressure', 'pp0', 'adsorbed', 'quantityadsorbed'):
        return Detection('Porosity and surface', 'high', (f'Pore-size or intrusion column: {pore}' if pore else 'Relative-pressure or adsorbed-amount column detected',))
    if find('ramanshift'):
        return Detection('Raman', 'high', ('Raman shift column detected',))
    wn = find('wavenumber', 'cm1')
    if wn:
        return Detection('FTIR', 'high' if find('absorbance', 'transmittance', 'transmission') else 'tentative',
                         (f'Wavenumber column: {wn}', 'Confirm FTIR versus Raman if the signal is not labelled'))
    temperature = find('temperature', 'temp', 'celsius', 'degc')
    time = find('time', 'hours', 'minutes', 'seconds', 'elapsed')
    mass = find('mass', 'weight', 'tgpercent')
    heat = find('heatflow', 'heatflux', 'thermalpower', 'normalizedheatflow', 'dsc', 'power')
    if mass and (temperature or time):
        return Detection('TGA', 'high', (f'Mass column: {mass}', f'Coordinate: {temperature or time}'))
    if temperature and not heat:
        amounts = [c for c in cols if c != temperature and re.search(r'(wt|masspercent|masspct|weightpercent|molpercent|fraction)$|^(wt|mass|mol)(percent|pct|fraction)', re.sub(r'\d+$', '', names[c]))]
        if len(amounts) >= 2:
            return Detection('Thermodynamic modelling', 'tentative', (f'Temperature column: {temperature}', f'{len(amounts)} columns of amounts (e.g. {amounts[0]}): phase amounts against temperature',
                                                                      'Confirm whether these are modelled (thermodynamic) or measured amounts'))
    if heat and temperature:
        a = table.arr(temperature); a = a[np.isfinite(a)]
        if len(a) > 2 and np.ptp(a) > 15:
            return Detection('DSC', 'high', ('Heat signal and changing temperature programme',))
    if heat and time:
        return Detection('Calorimetry', 'high', ('Time and heat-flow columns detected',))
    if find('particlesize', 'diameter', 'micron', 'sizeum'):
        return Detection('Particle size', 'high', ('Particle-size or diameter column detected',))
    if find('shearrate', 'shearstress', 'viscosity'):
        return Detection('Rheology', 'high', ('Shear or viscosity column detected',))
    if find('impedance', 'zreal', 'zimag', 'zre', 'zim') or (find('potential', 'voltage') and find('current')):
        return Detection('Electrochemistry', 'high', ('Electrical measurement columns detected',))
    if find('strength', 'compressive', 'flexural', 'mpa'):
        return Detection('Strength', 'high', ('Strength or stress units detected',))
    x = table.arr(table.x); y = table.arr(table.ys[0]) if table.ys else np.array([])
    xx = x[np.isfinite(x)]
    if len(xx) >= 100 and len(y) and np.nanmin(y) >= 0:
        d = np.diff(xx)
        if (1 <= xx.min() < xx.max() <= 170 and np.ptp(xx) >= 8 and np.all(d > 0)
                and np.median(d) <= .2 and np.std(d) < .1 * np.mean(d)):
            return Detection('XRD', 'tentative', ('Fine, regularly spaced angular-like range and nonnegative signal',
                                                'Numeric shape alone does not confirm XRD'))
    return Detection('General XY', 'generic', ('Numeric X and Y columns; measurement type not established',))


def preferred_xy(table):
    """(x column, y column) this kind of measurement is drawn by, from the column names - None when the file's own first
    two numeric columns already are those, or when the names do not say. A thermal run exported as temperature, time,
    mass, DSC is a mass curve against temperature: not the time against the temperature, which the column order alone gave."""
    cols = list(table.numeric)
    if len(cols) < 3: return None
    names = {c: normalise(c) for c in cols}
    def find(*keys, skip=()):
        return next((c for c in cols if c not in skip and any(k in names[c] for k in keys)), None)
    d = detect(table, getattr(table, 'measurement_type', None))
    if d.needs_confirmation: return None
    x = y = None
    if d.kind == 'TGA':
        x = find('temperature', 'temp', 'celsius', 'degc') or find('time', 'hours', 'minutes', 'seconds', 'elapsed'); y = find('mass', 'weight', 'tgpercent', skip=(x,))
    elif d.kind == 'DSC':
        x = find('temperature', 'temp', 'celsius', 'degc'); y = find('heatflow', 'heatflux', 'dsc', 'thermalpower', 'power', skip=(x,))
    elif d.kind == 'Calorimetry':
        x = find('time', 'hours', 'minutes', 'seconds', 'elapsed'); y = find('normalizedheatflow', 'heatflow', 'heatflux', 'thermalpower', 'power', skip=(x,))
    elif d.kind in ('FTIR', 'Raman'):
        x = find('wavenumber', 'cm1', 'ramanshift'); y = find('absorbance', 'transmittance', 'transmission', 'intensity', 'counts', skip=(x,))
    if not x or not y or x == y: return None
    if table.x == x and table.ys and table.ys[0] == y: return None
    return x, y


FAMILIES = {
 'NMR': ('nmr',), 'Porosity and surface': ('mip', 'bet'),
 **{k: (v,) for k, v in CATEGORY_KINDS.items()},
 'Flow network': ('sankey', 'flowchart', 'network'),
 'Composition': ('composition', 'qpa', 'ternary', 'oxide'),
 'XRD': ('xrd', 'rietveld', 'diffraction'), 'FTIR': ('ftir', 'spectroscopy'),
 'Raman': ('raman', 'spectroscopy'), 'TGA': ('tga', 'tg_', 'dtg', 'bound_water', 'ch_cc'),
 'DSC': ('dsc', 'dta', 'thermal'), 'Calorimetry': ('calorimetry', 'heatflow', 'hydration_degree'),
 'Particle size': ('psd', 'particle', 'rrsb'), 'Rheology': ('rheo', 'bingham', 'herschel'),
 'Electrochemistry': ('eis', 'cv_', 'tafel'), 'Strength': ('strength', 'abrams', 'stress'),
}


def family_matches(template, kind):
    if template.id == 'scientific_line': return True
    tid = template.id.lower()
    if kind == 'XRD': return 'XRD' in template.category or any(k in tid for k in ('xrd','rietveld'))
    if kind in CATEGORY_KINDS: return template.category == CATEGORY_KINDS[kind]
    exact = {
        'NMR': ('nmr',), 'Porosity and surface': ('mip', 'bet_'),
        'FTIR': ('ftir',), 'Raman': ('raman',), 'TGA': ('tga','tg_','dtg','tangent_method'),
        'DSC': ('dsc','dta'), 'Calorimetry': ('calorimetry','heatflow','hydration_degree'),
        'Particle size': ('psd','particle','rrsb'), 'Rheology': ('rheo','bingham','herschel'),
        'Electrochemistry': ('eis','cv_','tafel'), 'Strength': ('strength','abrams','stress'),
        'Flow network': ('sankey','flowchart','network'), 'Composition': ('composition','qpa','ternary','oxide'),
    }
    return any(k in tid for k in exact[kind]) if kind in exact else True


def compatibility(template, tables, detection=None, overrides=None):
    """Validate real inputs; numerical shape alone does not identify a measurement."""
    from . import data
    if not tables:
        return False, 'Select a data file first'
    if detection and detection.kind in FAMILIES and template.id != 'scientific_line':
        if not family_matches(template, detection.kind):
            return False, f'Outside the detected {detection.kind} family; browse Analysis to choose manually'
    try:
        data.bundle(template, tables, overrides)
    except Exception as e:
        return False, str(e)
    tid = template.id
    if detection and detection.kind in ('General XY', 'Category table'):
        allowed = ('Basic 2D & layout', 'General scientific & statistics')
        if template.category not in allowed:
            return False, 'Measurement type is unspecified; confirm it to see specialised templates'
    series_count = sum(len(t.ys) for t in tables)
    one_ok = ('ftir_stacked_bands', 'raman_stacked')       # a single spectrum with its band lines is a figure as well: these draw one curve as well as several
    if tid not in one_ok and any(word in tid for word in ('stack', 'multi_panel', 'waterfall', 'heatmap_contour', 'rietveld_grid', 'pair_')) and series_count < 2:
        return False, 'Select at least two scans or series'
    header = ' '.join(normalise(c) for t in tables for c in t.cols)
    if tid == 'tangent_method_demo' and not (overrides or {}).get('window'):
        return False, 'Requires a user-confirmed onset/endset temperature window'
    multi_scan = any(word in tid for word in ('stack', 'multi_panel', 'waterfall', 'heatmap_contour'))
    if template.data_kind == 'rietveld':
        if not all(fit_columns(t).get('calc') or any(k in ' '.join(normalise(c) for c in t.cols) for k in ('ycalc','icalc','calculated','fitted','yfit')) for t in tables):
            return False, 'Requires an explicitly identified calculated or fitted intensity column'
    elif 'XRD' in template.category:
        forms = [xrd_form(t) for t in tables]
        if 'peak list' in forms and tid not in ('williamson_hall', 'lattice_param_vs_x'):
            return False, 'This is a peak list (positions, widths, areas), not a measured scan; use a plain plot or a peak-width analysis'
        if 'fit' in forms and multi_scan:
            return False, 'These columns are the observed, calculated and difference curves of one fit, not separate scans; use a pattern-and-fit template'
    if tid in ('xrd_waterfall_3d','xrd_heatmap_contour'):
        if not any(k in header for k in ('temperature','time','degc','minutes','hours')):
            return False, 'Requires time or temperature metadata for the scans'
    if tid == 'xrd_dspacing_top' and not all(getattr(t, 'wavelength_confirmed', False) for t in tables):
        return False, 'Requires a confirmed X-ray wavelength; configure this template in Analysis'
    if tid.startswith('abrams') and not any(k in header for k in ('watercement','wcratio','wc','waterbinder')):
        return False, 'Requires water/cement or water/binder ratios'
    if tid.startswith('eis') and not any(k in header for k in ('impedance','zre','zim')):
        return False, 'Requires real and imaginary impedance columns'
    if tid.startswith(('cv_','tafel')) and not any(k in header for k in ('potential','voltage')):
        return False, 'Requires potential and current measurements'

    if detection and detection.kind == 'TGA':
        if tid in ('bound_water_vs_age','ch_cc_content_bar','tga_massloss_stacked_bar'):
            return False, 'Requires quantified sample results, not an unprocessed temperature/mass scan'
        if tid in ('conversion_vs_T','ofw_kas_plot','friedman_plot','kissinger_plot','ea_vs_alpha'):
            return False, 'Requires heating-rate or conversion analysis inputs'
        if tid == 'tg_ms' and not any(k in header for k in ('ioncurrent','mz','masscharge')):
            return False, 'Requires mass-spectrometer ion-current columns'

    if tid.startswith('williamson') and not ('fwhm' in header or 'breadth' in header):
        return False, 'Requires peak positions and peak widths (FWHM or integral breadth)'
    if tid.startswith('lattice_param') and not ('lattice' in header or 'parameter' in header):
        return False, 'Requires lattice parameters and composition values'
    if ('phase_vs' in tid or 'peak_area' in tid or 'qpa_' in tid) and detection and detection.kind == 'XRD':
        if not any(k in header for k in ('phaseamount', 'wtpercent', 'weightfraction', 'peakarea', 'phasefraction')):
            return False, 'Requires quantified phase amounts or integrated peak areas'
    if detection and detection.kind in FAMILIES and template.id != 'scientific_line':
        if not family_matches(template, detection.kind):
            return False, f'Outside the detected {detection.kind} family; browse Analysis to choose manually'
    return True, '; '.join(detection.evidence[:2]) if detection else 'Required inputs are available'

"""Shared conservative scientific detection and Analysis-template compatibility."""
from dataclasses import dataclass, asdict
import re
import unicodedata
import numpy as np

KINDS = ['Unknown', 'XRD', 'FTIR', 'Raman', 'TGA', 'DSC', 'Calorimetry',
         'Particle size', 'Rheology', 'Electrochemistry', 'Strength', 'Composition', 'Flow network', 'Category table', 'General XY']


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
        return Detection(override, 'confirmed', ('Measurement type selected by you',), True)
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
        ev = [f'Angle column: {angle}']
        if signal:
            ev.append(f'Intensity column: {signal}')
            return Detection('XRD', 'high', tuple(ev))
        return Detection('XRD', 'tentative', tuple(ev + ['Confirm that the remaining values are diffraction intensities']))
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


FAMILIES = {
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
    exact = {
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
    if any(word in tid for word in ('stack', 'multi_panel', 'waterfall', 'heatmap_contour', 'rietveld_grid', 'pair_')) and series_count < 2:
        return False, 'Select at least two scans or series'
    header = ' '.join(normalise(c) for t in tables for c in t.cols)
    if tid == 'tangent_method_demo' and not (overrides or {}).get('window'):
        return False, 'Requires a user-confirmed onset/endset temperature window'
    if template.data_kind == 'rietveld':
        if not any(k in header for k in ('ycalc','icalc','calculated','fitted','yfit')):
            return False, 'Requires an explicitly identified calculated or fitted intensity column'
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

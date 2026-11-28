"""Per-panel scientific components shared by preview, export and Origin transfer."""
import numpy as np
from . import core


def render_rietveld(tid, bundle, style, params, switches, target=None):
    from .templates_materials import _riet_block
    items = bundle.get('items') or [bundle]
    ncols = min(max(1, int(params.get('ncols', 3 if len(items) > 1 else 1))), len(items))
    nrows = (len(items) + ncols - 1) // ncols
    fig = core.make_fig(core.fig_size(style, 'double', max(1.2, ncols * 1.1 / nrows)))
    cells = fig.add_gridspec(nrows, ncols, hspace=.32, wspace=.25)
    for i, item in enumerate(items):
        opt = dict(switches); opt.update((switches.get('panel_options') or {}).get(str(i), {}))
        p = dict(params); p.update(_component_options=opt)
        if 'inset' in opt: p['inset'] = bool(opt['inset'])
        if opt.get('zoom'): p['zoom'] = list(opt['zoom'])
        _riet_block(fig, cells[i//ncols, i%ncols], item, style, p, i,
                    small=len(items)>1, show_labels=True)
    return fig


def apply(fig, switches):
    """Optional components for any template. Tagging survives display and export."""
    roots = [a for a in fig.axes if not getattr(a, '_ops_auxiliary', False)]
    for i, ax in enumerate(roots):
        panel = getattr(ax, '_ops_panel', i)
        opt = dict(switches); opt.update((switches.get('panel_options') or {}).get(str(panel), {}))
        for child in list(ax.child_axes):
            if 'inset' in opt: child.set_visible(bool(opt['inset']))
        if 'peak_labels' in opt:                                   # the labels on the peaks (bands), with their marks and leaders: shown or not; the curves stay
            from . import side_tables as SD
            SD.show_labels(fig, ax, bool(opt['peak_labels']))
        markers = opt.get('markers')
        if markers is not None:
            for line in ax.lines:
                if len(line.get_xdata()) <= 2 or line.get_marker() in ('|', '_'): continue
                label = str(line.get_label()).lower()
                value = opt.get('observed_markers', markers) if any(k in label for k in ('observed','yobs','iobs')) else opt.get('fitted_markers', markers) if any(k in label for k in ('calculated','fitted','ycalc','fit')) else markers
                line.set_marker('o' if value else 'None')
                if not value and line.get_linestyle() in ('None', 'none', ''): line.set_linestyle('-')
        for line in ax.lines:
            label = str(line.get_label()).lower()
            if any(k in label for k in ('background', 'baseline')) and 'show_background' in opt:
                line.set_visible(bool(opt['show_background']))
    return fig

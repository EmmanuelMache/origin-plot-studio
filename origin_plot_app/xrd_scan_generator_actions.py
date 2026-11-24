"""XRD Scan Generator - selecting with the mouse, right-click menus, and choosing where scans are saved.

Added to the window of xrd_scan_generator_app.py (install(window)); the generator's own functions are unchanged.

  Peak correct graph   left click on a peak: tick / untick it (the mode 'The ticked peaks to the heights I give' is chosen);
                       Shift + drag: tick every peak in that 2θ range; right click: tick / untick, tick only this peak, set its target,
                       tick all / none / the peaks in view, zoom to the peak, reset the view, save or copy the picture.
  Generated scans      left click on a curve: select that scan (drawn thicker, selected in the list); right click: save this scan as…,
                       open its folder, tick only this scan, untick it, use it in Origin Plot Studio, tick all / none, overlay the
                       template, normalise, reset the view, save or copy the picture.
  Lists                right click on the generated scans, the corrected versions or the files: save as…, save the ticked to a folder…,
                       open the file, open its folder, copy the path, remove from the list (the file stays).
  Where to save        Peak correct has its own 'Save corrected scans in' folder (Browse, Open; empty = the output folder);
                       'Save the ticked scans to…' and 'Save this scan as…' copy a scan and its provenance file wherever you want.
Nothing here changes a number: copies are byte for byte, ticks and targets go into the generator's own table.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QPushButton)


def _noopen():
    return bool(os.environ.get("OPS_NO_OPEN"))


def _open(p):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    if not _noopen():
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))


def _prov(f):
    return Path(f).with_name(Path(f).stem + "_provenance.json")


def install(w):
    """Add the mouse actions, menus and save places to a MainWindow of the XRD Scan Generator."""
    import types
    for name, fn in METHODS.items():
        setattr(w, name, types.MethodType(fn, w))
    w.sel_sid = None
    w._shift_x0 = None
    # Peak correct: where the corrected scans go
    row = QHBoxLayout()
    row.addWidget(QLabel("Save corrected scans in"))
    w.pc_out = QLineEdit()
    w.pc_out.setPlaceholderText("the output folder (left)")
    w.pc_out.setToolTip("Where 'Correct peaks' writes the corrected scans and their provenance files. Empty: the output folder of the generator.")
    row.addWidget(w.pc_out, 1)
    b = QPushButton("Browse…")
    b.clicked.connect(w.pc_browse_out)
    row.addWidget(b)
    o = QPushButton("Open")
    o.clicked.connect(lambda: _open(w.pc_out_dir()))
    row.addWidget(o)
    lay = w.pc_go.parentWidget().layout()
    _insert_before(lay, w.pc_go, row)
    hint = QLabel("Mouse: click a peak on the graph to tick it, Shift + drag to tick a range, right click for more.", objectName="key")
    hint.setWordWrap(True)
    _insert_before(lay, w.pc_go, hint)
    # Generated scans: save buttons
    for btn_text, fn, tip in (("Save the ticked scans to…", w.save_ticked_to, "Copy the ticked scans (and their provenance files) into a folder you choose"),
                              ("Save the selected scan as…", lambda: w.save_scan_as(w.selected_scan()), "Copy the scan you clicked (or the first ticked one) to a file you name")):
        bb = QPushButton(btn_text)
        bb.setToolTip(tip)
        bb.clicked.connect(fn)
        _side_layout(w).addWidget(bb)
    # mouse on the graphs
    w.pc_plot.canvas.mpl_connect("button_press_event", w._pc_press)
    w.pc_plot.canvas.mpl_connect("button_release_event", w._pc_release)
    w.gen_plot.canvas.mpl_connect("button_press_event", w._gen_press)
    # right-click menus on the lists
    for lst, kind in ((w.scan_list, "scans"), (w.pc_list, "pc"), (w.file_list, "files")):
        lst.setContextMenuPolicy(Qt.CustomContextMenu)
        lst.customContextMenuRequested.connect(lambda pos, l=lst, k=kind: w.menu_list(l, k, pos))
    w.scan_list.currentRowChanged.connect(lambda r: w._select_row(r))
    QShortcut(QKeySequence("Ctrl+S"), w, activated=w.save_ticked_to)
    # the generator's Peak correct writes where you chose
    orig = w.peak_correct

    def peak_correct_here():
        if w.pc_out.text().strip():
            keep = w.out.text()
            w.out.blockSignals(True)
            w.out.setText(w.pc_out.text().strip())
            try:
                return orig()
            finally:
                w.out.setText(keep)
                w.out.blockSignals(False)
        return orig()
    w.peak_correct = peak_correct_here
    try:
        w.pc_go.clicked.disconnect()
    except Exception:
        pass
    w.pc_go.clicked.connect(w.peak_correct)
    return w


def _insert_before(layout, widget, item):
    i = layout.indexOf(widget)
    if hasattr(item, "count"):
        layout.insertLayout(max(i, 0), item)
    else:
        layout.insertWidget(max(i, 0), item)


def _side_layout(w):
    """The column under the list of generated scans (Tick all / Tick none / Use ...)."""
    return w.scan_list.parentWidget().layout().itemAt(0).layout()


# ---------------------------------------------------------------------------------------------- where to save
def pc_out_dir(self):
    return self.pc_out.text().strip() or self.out.text().strip() or (str(Path(self.template.path).parent / "scans") if self.template else str(Path.home()))


def pc_browse_out(self):
    p = QFileDialog.getExistingDirectory(self, "Save corrected scans in", self.pc_out_dir())
    if p:
        self.pc_out.setText(p)
    return p


def _copy(self, files, dest_dir, rename=None):
    """Copy scans (and their provenance files) byte for byte; an existing name gets _2, _3 ..."""
    done = []
    os.makedirs(dest_dir, exist_ok=True)
    for f in files:
        for src in (Path(f), _prov(f)):
            if not src.exists():
                continue
            name = (rename + src.suffix if src == Path(f) else Path(rename).stem + "_provenance.json") if rename else src.name
            target = Path(dest_dir) / name
            k = 2
            while target.exists() and target.resolve() != src.resolve():
                target = Path(dest_dir) / f"{Path(name).stem}_{k}{Path(name).suffix}"
                k += 1
            if target.resolve() != src.resolve():
                shutil.copy2(src, target)
            done.append(str(target))
    return done


def save_ticked_to(self, dest=None, scans=None):
    scans = scans if scans is not None else self.ticked()
    if not scans:
        self.error("Tick a scan", "Tick the scan(s) to save in the list under 'Generated scans' first.")
        return []
    if dest is None:
        dest = QFileDialog.getExistingDirectory(self, "Save the ticked scans to", self.out.text().strip() or str(Path.home()))
        if not dest:
            return []
    done = self._copy([sc.files[0] for sc in scans if getattr(sc, "files", None)], dest)
    self.logline(f"Saved {len(scans)} scan(s) to {dest}: " + ", ".join(Path(f).name for f in done))
    self.set_status(f"{len(scans)} scan(s) saved to {dest} (with their provenance files).")
    return done


def save_scan_as(self, sc, path=None):
    if sc is None or not getattr(sc, "files", None):
        self.error("Choose a scan", "Click a scan on the graph or in the list (or tick one) first.")
        return None
    src = Path(sc.files[0])
    if path is None:
        path, _ = QFileDialog.getSaveFileName(self, "Save this scan as", str(Path(self.out.text().strip() or src.parent) / src.name), "XRDML scan (*.xrdml)")
        if not path:
            return None
    p = Path(path)
    done = self._copy([str(src)], str(p.parent), rename=p.stem)
    self.logline(f"Saved {src.name} as {done[0] if done else p}")
    self.set_status(f"Saved as {done[0] if done else p} (with its provenance file).")
    return done


def selected_scan(self):
    by = {sc.sid: sc for sc in self.scans}
    if self.sel_sid in by:
        return by[self.sel_sid]
    t = self.ticked()
    return t[0] if t else None


# ---------------------------------------------------------------------------------------------- the Peak correct graph
def _pc_nearest(self, x):
    if not self.pc_peaks or x is None:
        return None
    r = min(range(len(self.pc_peaks)), key=lambda i: abs(self.pc_peaks[i]["pos"] - x))
    lo, hi = self.pc_plot.ax.get_xlim()
    return r if abs(self.pc_peaks[r]["pos"] - x) <= max(0.25, 0.012 * abs(hi - lo)) else None


def _pc_set(self, rows, on=True, only=False):
    tb = self.pc_table
    tb.blockSignals(True)
    for r in range(tb.rowCount()):
        if only and r not in rows:
            tb.item(r, 0).setCheckState(Qt.Unchecked)
    for r in rows:
        tb.item(r, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)
    tb.blockSignals(False)
    if rows and not self.pc_mode_sel.isChecked():
        self.pc_mode_sel.setChecked(True)                 # ticking peaks by hand means: these peaks to their targets
    self._pc_update()
    self._pc_plot()


def _pc_press(self, e):
    if self.pc_plot.toolbar.mode or e.inaxes is None:
        return
    if e.button == 3:
        return self.menu_pc(e)
    if e.button == 1 and e.key == "shift":
        self._shift_x0 = e.xdata
        return None
    if e.button == 1 and not self.pc_scans:
        r = self._pc_nearest(e.xdata)
        if r is not None:
            on = self.pc_table.item(r, 0).checkState() != Qt.Checked
            self._pc_set([r], on)
            self.set_status(f"Peak at {self.pc_peaks[r]['pos']:.3f}° {'ticked' if on else 'unticked'} (target {self.pc_table.item(r, 3).text()} counts).")
            return r
    return None


def _pc_release(self, e):
    if self._shift_x0 is None or e.xdata is None:
        self._shift_x0 = None
        return None
    a, b = sorted((self._shift_x0, e.xdata))
    self._shift_x0 = None
    rows = [r for r, d in enumerate(self.pc_peaks) if a <= d["pos"] <= b]
    if rows:
        self._pc_set(rows, True)
        self.set_status(f"{len(rows)} peak(s) between {a:.2f}° and {b:.2f}° ticked.")
    return rows


def pc_target(self, r, value=None):
    if value is None:
        cur = self.pc_table.item(r, 3).text().replace(",", "")
        value, ok = QInputDialog.getDouble(self, "Target", f"Counts wanted at the top of the peak at {self.pc_peaks[r]['pos']:.3f}°:", float(cur or 0), 1, 1e9, 0)
        if not ok:
            return None
    self.pc_table.item(r, 3).setText(f"{value:.0f}")
    self._pc_set([r], True)
    return value


def menu_pc(self, e):
    m = QMenu(self)
    r = self._pc_nearest(e.xdata) if not self.pc_scans else None
    if r is not None:
        d = self.pc_peaks[r]
        on = self.pc_table.item(r, 0).checkState() == Qt.Checked
        m.addAction(f"{'Untick' if on else 'Tick'} the peak at {d['pos']:.3f}° ({d['top']:,.0f} counts)", lambda: self._pc_set([r], not on))
        m.addAction("Tick only this peak", lambda: self._pc_set([r], True, only=True))
        m.addAction("Set its target…", lambda: self.pc_target(r))
        m.addAction("Zoom to this peak", lambda: self._zoom(self.pc_plot, d["pos"] - 1.0, d["pos"] + 1.0))
        m.addSeparator()
    if self.pc_peaks:
        m.addAction("Tick all peaks", lambda: self._pc_set(list(range(len(self.pc_peaks))), True))
        m.addAction("Untick all peaks", lambda: self._pc_set(list(range(len(self.pc_peaks))), False))
        lo, hi = self.pc_plot.ax.get_xlim()
        m.addAction("Tick the peaks in view", lambda: self._pc_set([i for i, d_ in enumerate(self.pc_peaks) if lo <= d_["pos"] <= hi], True))
        m.addSeparator()
    self._view_items(m, self.pc_plot)
    self.last_menu = m
    if not _noopen():
        m.exec(self.pc_plot.canvas.mapToGlobal(self.pc_plot.canvas.mapFromGlobal(self.cursor().pos())))
    return m


# ---------------------------------------------------------------------------------------------- the generated scans graph
def _gen_nearest(self, x, y):
    chosen = [self.scans[i] for i in range(min(self.scan_list.count(), len(self.scans))) if self.scan_list.item(i).checkState() == Qt.Checked]
    if not chosen or x is None or y is None:
        return None
    import numpy as np
    norm = self.norm.isChecked()
    def dist(sc):
        yy = float(np.interp(x, sc.x, sc.counts / (sc.counts.max() if norm else 1)))
        return abs(yy - y)
    return min(chosen, key=dist)


def _gen_press(self, e):
    if self.gen_plot.toolbar.mode or e.inaxes is None:
        return None
    sc = self._gen_nearest(e.xdata, e.ydata)
    if e.button == 1 and sc is not None:
        self.select_scan(sc)
        return sc
    if e.button == 3:
        return self.menu_gen(sc)
    return None


def select_scan(self, sc):
    """The clicked scan: drawn thicker and selected in the list (Save the selected scan as… uses it)."""
    self.sel_sid = sc.sid
    i = self.scans.index(sc)
    self.scan_list.blockSignals(True)
    self.scan_list.setCurrentRow(i)
    self.scan_list.blockSignals(False)
    self.plot_scans()
    self._highlight()
    self.set_status(f"Selected: {sc.sid}  ({Path(sc.files[0]).name if getattr(sc, 'files', None) else ''}). Right click for Save as…")
    return sc


def _highlight(self):
    """Thicken the selected scan's curve (curves are drawn in the order of the ticked scans)."""
    chosen = [self.scans[i] for i in range(min(self.scan_list.count(), len(self.scans))) if self.scan_list.item(i).checkState() == Qt.Checked]
    lines = self.gen_plot.ax.get_lines()
    off = 1 if (self.show_tpl.isChecked() and self.template is not None) else 0
    for k, sc in enumerate(chosen):
        if k + off < len(lines):
            lines[k + off].set_linewidth(1.8 if sc.sid == self.sel_sid else 0.6)
            lines[k + off].set_alpha(1.0 if (self.sel_sid is None or sc.sid == self.sel_sid) else 0.55)
    self.gen_plot.canvas.draw_idle()


def _select_row(self, r):
    if 0 <= r < len(self.scans):
        self.sel_sid = self.scans[r].sid
        self._highlight()


def menu_gen(self, sc):
    m = QMenu(self)
    if sc is not None:
        m.addAction(f"Save {sc.sid} as…", lambda: self.save_scan_as(sc))
        if getattr(sc, "files", None):
            m.addAction("Open its folder", lambda: _open(Path(sc.files[0]).parent))
        m.addAction("Tick only this scan", lambda: self._tick_only(sc))
        m.addAction("Untick this scan", lambda: self._tick_scan(sc, False))
        if self.return_file:
            m.addAction("Use this scan in Origin Plot Studio", lambda: (self._tick_only(sc), self.use_ticked()))
        m.addSeparator()
    m.addAction("Save the ticked scans to…", self.save_ticked_to)
    m.addAction("Tick all", lambda: self._tick_all(True))
    m.addAction("Tick none", lambda: self._tick_all(False))
    a = m.addAction("Overlay the template", lambda: self.show_tpl.setChecked(not self.show_tpl.isChecked()))
    a.setCheckable(True)
    a.setChecked(self.show_tpl.isChecked())
    a = m.addAction("Normalise to maximum = 1", lambda: self.norm.setChecked(not self.norm.isChecked()))
    a.setCheckable(True)
    a.setChecked(self.norm.isChecked())
    m.addSeparator()
    self._view_items(m, self.gen_plot)
    self.last_menu = m
    if not _noopen():
        m.exec(self.cursor().pos())
    return m


def _tick_scan(self, sc, on):
    i = self.scans.index(sc)
    self.scan_list.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)


def _tick_only(self, sc):
    self.scan_list.blockSignals(True)
    for i in range(self.scan_list.count()):
        self.scan_list.item(i).setCheckState(Qt.Checked if self.scans[i] is sc else Qt.Unchecked)
    self.scan_list.blockSignals(False)
    self.sel_sid = sc.sid
    self.plot_scans()
    self._highlight()


# ---------------------------------------------------------------------------------------------- shared
def _zoom(self, panel, a, b):
    panel.ax.set_xlim(a, b)
    panel.canvas.draw_idle()


def _view_items(self, m, panel):
    m.addAction("Reset the view", lambda: panel.toolbar.home())
    m.addAction("Copy the picture", lambda: QApplication.clipboard().setPixmap(panel.canvas.grab()))
    m.addAction("Save the picture…", lambda: self.save_picture(panel))


def save_picture(self, panel, path=None):
    if path is None:
        path, _ = QFileDialog.getSaveFileName(self, "Save the picture", str(Path(self.out.text().strip() or Path.home()) / "xrd_view.png"), "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not path:
            return None
    panel.fig.savefig(path, dpi=300, bbox_inches="tight")
    self.set_status(f"Picture saved: {path}")
    return path


def menu_list(self, lst, kind, pos):
    """Right click on the generated scans, the corrected versions or the files."""
    it = lst.itemAt(pos)
    m = QMenu(self)
    files = []
    if it is not None:
        row = lst.row(it)
        if kind == "files":
            files = [it.data(Qt.UserRole)]
        else:
            src = self.scans if kind == "scans" else self.pc_scans
            sc = src[row] if row < len(src) else None
            files = list(getattr(sc, "files", []) or [])[:1] if sc is not None else []
            if sc is not None:
                m.addAction("Save as…", lambda: self.save_scan_as(sc))
                if kind == "scans":
                    m.addAction("Tick only this scan", lambda: self._tick_only(sc))
        if files:
            f = files[0]
            if kind == "files":
                m.addAction("Save a copy as…", lambda: self._save_file_as(f))
            m.addAction("Open the file", lambda: _open(f))
            m.addAction("Open its folder", lambda: _open(Path(f).parent))
            m.addAction("Copy the path", lambda: QApplication.clipboard().setText(str(f)))
        m.addAction("Remove from the list (the file stays)", lambda: self._remove_row(lst, kind, lst.row(it)))
        m.addSeparator()
    if kind == "scans":
        m.addAction("Save the ticked scans to…", self.save_ticked_to)
        m.addAction("Tick all", lambda: self._tick_all(True))
        m.addAction("Tick none", lambda: self._tick_all(False))
    elif kind == "pc":
        ticked = [self.pc_scans[i] for i in range(min(lst.count(), len(self.pc_scans))) if lst.item(i).checkState() == Qt.Checked]
        m.addAction("Save the ticked corrected scans to…", lambda: self.save_ticked_to(scans=ticked))
    self.last_menu = m
    if not _noopen():
        m.exec(lst.mapToGlobal(pos))
    return m


def _save_file_as(self, f, path=None):
    if path is None:
        path, _ = QFileDialog.getSaveFileName(self, "Save a copy as", str(Path(self.out.text().strip() or Path(f).parent) / Path(f).name))
        if not path:
            return None
    shutil.copy2(f, path)
    self.set_status(f"Copy saved: {path}")
    return path


def _remove_row(self, lst, kind, row):
    if row < 0:
        return
    if kind == "scans" and row < len(self.scans):
        self.scans.pop(row)
    elif kind == "pc" and row < len(self.pc_scans):
        self.pc_scans.pop(row)
    lst.takeItem(row)
    if kind == "scans":
        self.plot_scans()
    elif kind == "pc":
        self._pc_plot()


METHODS = {f.__name__: f for f in (pc_out_dir, pc_browse_out, _copy, save_ticked_to, save_scan_as, selected_scan, _pc_nearest, _pc_set, _pc_press, _pc_release,
                                   pc_target, menu_pc, _gen_nearest, _gen_press, select_scan, _highlight, _select_row, menu_gen, _tick_scan, _tick_only, _zoom,
                                   _view_items, save_picture, menu_list, _save_file_as, _remove_row)}

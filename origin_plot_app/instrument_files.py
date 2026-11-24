"""
instrument_files.py - binary instrument files the app reads directly.

  .spa        Thermo Scientific OMNIC spectrum (FTIR): one spectrum, x from the header, y as stored.
  .ngb-*      NETZSCH Proteus measurement (.ngb-ds3 DSC, .ngb-ss3 STA, ...): time, sample temperature, DSC signal and,
              when the instrument has a balance, the mass. The file is a zip of binary tables.

Neither format is documented by its maker. The layouts used here were worked out from real files, so every reader checks
what it finds and says plainly when a file does not look as expected, instead of returning numbers it is not sure of.

What is NOT done here, and why:
  - NETZSCH: the DSC signal is the raw thermocouple voltage (microvolt). Proteus turns it into mW/mg with a sensitivity
    calibration file that is not inside the measurement, so no heat flow in mW/mg and no enthalpy in J/g come out of it.
  - NETZSCH: when the file holds a correction (baseline) run measured on the same time grid, it is subtracted from the
    sample run, as Proteus does for "sample + correction". The result names this in its header (REMARK).
"""
import os, re, io, struct, zipfile, tempfile

SPA_Y = {11: "Reflectance (%)", 12: "Log(1/R)", 15: "Single beam", 16: "Transmittance (%)", 17: "Absorbance", 20: "Kubelka-Munk", 22: "Detector signal (V)", 26: "Photoacoustic", 31: "Raman intensity"}
SPA_X = {1: "Wavenumber (cm-1)", 2: "Data point", 3: "Wavelength (nm)", 4: "Wavelength (um)", 32: "Raman shift (cm-1)"}


class NotReadable(ValueError):
    pass


# ---------------------------------------------------------------------------------------------- Thermo OMNIC .spa
def read_spa(path):
    """One OMNIC spectrum -> ({"title", "x_name", "y_name", "scans", "history"}, x array, y array)."""
    import numpy as np
    b = open(path, "rb").read()
    if not b.startswith(b"Spectral Data File") or len(b) < 400: raise NotReadable("this .spa file does not start like an OMNIC spectrum")
    title = b[30:285].split(b"\x00")[0].decode("latin1", "replace").strip(); n = struct.unpack("<H", b[294:296])[0]
    head = data = None; hist = ""
    for i in range(min(n, 200)):
        p = 304 + 16 * i
        if p + 10 > len(b): break
        key = b[p]; off, size = struct.unpack("<II", b[p + 2:p + 10])
        if off + size > len(b): continue
        if key == 2 and head is None: head = off
        elif key == 3 and data is None: data = (off, size)
        elif key == 27 and not hist: hist = b[off:off + size].split(b"\x00")[0].decode("latin1", "replace")
    if head is None or data is None: raise NotReadable("the .spa file has no spectrum block I can read (it may be a spectral group or a map; export it from OMNIC as .csv)")
    nx = struct.unpack("<I", b[head + 4:head + 8])[0]; xu, yu = b[head + 8], b[head + 12]; x0, x1 = struct.unpack("<ff", b[head + 16:head + 24]); scans = struct.unpack("<I", b[head + 36:head + 40])[0]
    y = np.frombuffer(b[data[0]:data[0] + data[1]], dtype="<f4").astype(float)
    if nx < 2 or y.size != nx: raise NotReadable(f"the .spa header says {nx} points but the spectrum block holds {y.size}")
    if not (np.isfinite(x0) and np.isfinite(x1)) or x0 == x1 or not np.isfinite(y).all(): raise NotReadable("the .spa file holds values that are not numbers")
    x = np.linspace(float(x0), float(x1), nx)
    return {"title": title, "x_name": SPA_X.get(xu, f"X (unit code {xu})"), "y_name": SPA_Y.get(yu, f"Intensity (unit code {yu})"), "scans": int(scans) if scans < 100000 else None, "history": hist}, x, y

def spa_tables(path):
    """For the app: [(name, table with the column names in its first row)]."""
    import pandas as pd
    m, x, y = read_spa(path)
    df = pd.DataFrame([[m["x_name"], m["y_name"]]] + [[float(a), float(b_)] for a, b_ in zip(x, y)])
    return [(m["title"] or os.path.splitext(os.path.basename(path))[0], df)], m


# ---------------------------------------------------------------------------------------------- NETZSCH .ngb-*
_SEP = b"\x00\x00\x01\x00\x00\x00\x0c\x00\x17\xfc\xff\xff\x1a\x80\x01\x01\x80\x02\x00\x00"       # between two tables of a stream
_FIELD = re.compile(rb"\x17\xfc\xff\xff(.)\x80\x01", re.S)                                         # a field: its type byte, then the value
_NP = {5: "<f8", 4: "<f4", 3: "<i4"}

def _streams(path):
    try: z = zipfile.ZipFile(path)
    except Exception: raise NotReadable("this NETZSCH file is not the zip container I expect (files of Proteus 6 and newer are)")
    out = {}
    for n in z.namelist():
        m = re.match(r"(?i)streams/stream_(\d+)\.table$", n)
        if m: out[int(m.group(1))] = z.read(n)
    if not out or not any(v[2:17] == b"Netzsch TA file" for v in out.values()): raise NotReadable("this file holds no NETZSCH measurement streams")
    return out

def _arrays(stream):
    """The data columns of a stream, in the order they are stored: a column is a table that carries a type byte, 'a0 01', a count and the values."""
    import numpy as np
    cols = []
    for t in stream.split(_SEP):
        if len(t) < 100 or t[83:85] != b"\xa0\x01" or t[82] not in _NP: continue
        n = struct.unpack("<I", t[85:89])[0]; dt = np.dtype(_NP[t[82]])
        if n < 2 or 89 + n * dt.itemsize > len(t): continue
        cols.append(np.frombuffer(t[89:89 + n * dt.itemsize], dtype=dt).astype(float))
    return cols

def _fields(table):
    out = []
    for m in _FIELD.finditer(table):
        ty = m.group(1)[0]; e = m.end()
        try:
            if ty == 0x1f:
                if table[e:e + 3] == b"\xff\xfe\xff": n = table[e + 3]; out.append(table[e + 4:e + 4 + 2 * n].decode("utf-16-le", "replace"))
                else: n = struct.unpack("<I", table[e:e + 4])[0]; out.append(table[e + 4:e + 4 + min(n, 400)].split(b"\x00")[0].decode("latin1", "replace"))
            elif ty == 5: out.append(struct.unpack("<d", table[e:e + 8])[0])
            elif ty == 4: out.append(struct.unpack("<f", table[e:e + 4])[0])
            elif ty == 3: out.append(struct.unpack("<i", table[e:e + 4])[0])
        except Exception: pass
    return out

def _meta(stream1):
    """Sample name and mass, reference, instrument, crucible, correction file: from the tables of the first stream."""
    m = {"texts": []}
    for t in stream1.split(_SEP):
        f = _fields(t); tid = t[1:3]
        if tid == b"\xfb\x2a" and "sample" not in m:                 # the sample: name, name, remark, ..., mass in mg
            s = [x for x in f if isinstance(x, str) and x.strip()]; d = [x for x in f if isinstance(x, float) and 0 < x < 1e5]
            if s: m["sample"] = s[0].strip()
            if d: m["mass_mg"] = float(d[0])
        elif tid == b"\xfc\x2a" and "reference" not in m:
            s = [x for x in f if isinstance(x, str) and x.strip()]
            if s: m["reference"] = s[0].strip()
        m["texts"] += [x.strip() for x in f if isinstance(x, str) and x.strip()]
    tx = m["texts"]
    m["instrument"] = next((x for x in tx if re.match(r"(?i)NETZSCH\s+\S", x)), None)
    m["correction_file"] = next((os.path.basename(x.replace("\\", "/")) for x in tx if re.search(r"(?i)\.ngb-b\w\d$", x)), None)
    m["crucible"] = next((x for x in tx if re.search(r"(?i)\bpan\b|crucible", x)), None)
    return m

def read_ngb(path):
    """A NETZSCH measurement -> dict(meta, time_min, temp_C, dsc_uV, mass_change_mg or None, corrected: bool, notes: [..]).
    The DSC signal and the mass change have the correction run subtracted when the file holds one on the same time grid."""
    import numpy as np
    st = _streams(path)
    if 2 not in st: raise NotReadable("the NETZSCH file has no measurement stream (stream 2)")
    cols = _arrays(st[2])
    if len(cols) < 3: raise NotReadable("I found no data columns in the NETZSCH file (its layout differs from the files this reader was made from)")
    def is_time(a): return a.size > 10 and abs(a[0]) < 1e-6 and bool(np.all(np.diff(a) > 0))
    starts = [i for i, a in enumerate(cols) if is_time(a)]
    if not starts: raise NotReadable("I found no time column in the NETZSCH file")
    blocks = [cols[a:b] for a, b in zip(starts, starts[1:] + [len(cols)])]
    def parts(blk):
        t = blk[0]; rest = [a for a in blk[1:] if a.size == t.size]
        if len(rest) < 2: raise NotReadable("a run in the NETZSCH file has fewer than three columns of the same length")
        temp, dsc = rest[0], rest[1]
        tail = [a for a in rest[2:] if np.ptp(a) > 1e-6 and not np.allclose(a, np.round(a))]          # the gas flows are whole numbers: they are not the balance
        return t, temp, dsc, (tail[-1] if tail else None)
    t, temp, dsc, tg = parts(blocks[0]); notes = []; meta = _meta(st.get(1, b"")); corrected = False
    if not (-300 < float(np.nanmin(temp)) and float(np.nanmax(temp)) < 2500 and np.ptp(temp) > 5): raise NotReadable("the second column of the NETZSCH file does not look like a temperature in degrees C")
    if len(blocks) == 2:
        t2, temp2, dsc2, tg2 = parts(blocks[1])
        if t2.size == t.size and np.allclose(t2, t, atol=1e-6) and float(np.max(np.abs(temp2 - temp))) < 25:
            dsc = dsc - dsc2; corrected = True
            if tg is not None and tg2 is not None: tg = tg - tg2
            notes.append("the correction run stored in the file" + (f" ({meta['correction_file']})" if meta.get("correction_file") else "") + " was subtracted from the sample run (DSC" + (" and mass" if tg is not None else "") + ")")
        else: notes.append("the file holds a second run that is not on the same time and temperature grid as the first: only the first run is read, uncorrected")
    elif len(blocks) > 2: notes.append(f"the file holds {len(blocks)} runs or segments: only the first is read, uncorrected")
    notes.append("the DSC signal is the uncalibrated voltage in microvolt (Proteus applies a sensitivity file to get mW/mg): peak positions are right, areas are not enthalpies")
    return {"meta": meta, "time_min": t, "temp_C": temp, "dsc_uV": dsc, "mass_change_mg": tg, "corrected": corrected, "notes": notes}

def ngb_export_text(path):
    """The measurement written like a NETZSCH text export (#KEY: lines, then ##columns), which the app already reads."""
    import numpy as np
    r = read_ngb(path); m = r["meta"]; t, T, d, tg = r["time_min"], r["temp_C"], r["dsc_uV"], r["mass_change_mg"]; m0 = m.get("mass_mg")
    k = max(2, t.size // 20); rate = abs(float(np.polyfit(t[k:-k], T[k:-k], 1)[0])) if t.size > 3 * k else None
    stem = os.path.splitext(os.path.basename(path))[0]; name = m.get("sample") or stem
    head = [("EXPORTTYPE", "DATA ALL"), ("FILE", os.path.basename(path)), ("FORMAT", "NETZSCH5"), ("IDENTITY", name), ("DECIMAL", "POINT"), ("SEPARATOR", "COMMA"), ("MTYPE", "DSC-TG" if tg is not None else "DSC"),
            ("INSTRUMENT", m.get("instrument") or "NETZSCH"), ("CORR. FILE", m.get("correction_file") or ""), ("SAMPLE", name), ("SAMPLE MASS /mg", f"{m0:.4f}" if m0 else ""), ("REFERENCE", m.get("reference") or ""),
            ("TYPE OF CRUCIBLE", m.get("crucible") or ""), ("RANGE", f"{T[0]:.0f}°C/{rate:.1f}(K/min)/{T[-1]:.0f}°C" if rate else ""), ("SEGMENT", "S1/1"),
            ("REMARK", "read from the binary file by Origin Plot Studio; " + "; ".join(r["notes"]))]
    cols = ["Temp./°C", "Time/min"]; data = [T, t]
    if tg is not None and m0: cols.append("Mass/%"); data.append(100.0 + 100.0 * tg / m0)
    elif tg is not None: cols.append("Mass change/mg"); data.append(tg)
    cols.append("DSC/uV"); data.append(d)
    out = io.StringIO(); [out.write(f"#{a}:,{str(b_).replace(',', ';')}\n") for a, b_ in head]; out.write("\n##" + ",".join(cols) + "\n")
    for row in zip(*data): out.write(",".join(f"{v:.6g}" for v in row) + "\n")
    return out.getvalue(), r

def ngb_as_text_file(path):
    """Write the export text into a temporary file and return its path (the caller reads and removes it)."""
    text, r = ngb_export_text(path)
    fd, tmp = tempfile.mkstemp(prefix="ngb_", suffix=".csv"); os.close(fd)
    with open(tmp, "w", encoding="utf-8") as f: f.write(text)
    return tmp, r

def is_ngb(path): return bool(re.search(r"(?i)\.ngb-[a-z]{1,2}\d$", path))

EXTENSIONS = (".spa", ".ngb-ds3", ".ngb-ss3", ".ngb-dss", ".ngb-ds2", ".ngb-ss2")

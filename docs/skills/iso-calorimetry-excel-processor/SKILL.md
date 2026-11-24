---
name: iso-calorimetry-excel-processor
description: >
  Process isothermal microcalorimetry exports (e.g. TAM III) in Excel. Use this skill whenever
  the user mentions calorimetry data in Excel, heat flow analysis, cumulative heat calculations,
  isothermal calorimetry processing, TAM III exports, or wants to add Time (h), normalised heat
  flow (mW/g), or cumulative heat (J/g) columns to a calorimetry spreadsheet. Also triggers for:
  "process my calorimetry file", "add heat flow columns", "calculate cumulative heat",
  "calorimetry chart", "reaction-start row", "exclusion window", "sample mass", "mW/g", "J/g",
  "export to Origin", "Origin export sheet", "OriginPro import", or any reference to TAM,
  isothermal calorimetry, or heat flow in Excel context. All outputs reference named helper cells
  (exclusion window, sample mass) so changing either updates all results and charts automatically.
---

# Isothermal Microcalorimetry Excel Processor

Adds live-formula columns and charts to a TAM III (or equivalent) isothermal calorimetry export
already open in Excel. All calculations reference two editable helper cells, so changing
reaction-start or exclusion window updates everything automatically.

---

## Step 0 — Read the xlsx skill first

Before writing any Python or openpyxl code, always read `/mnt/skills/public/xlsx/SKILL.md`
to follow correct formula, formatting, and recalculation conventions.

---

## Step 1 — Read the header/unit rows; do NOT assume column letters

The export format varies between instruments and software versions. Always inspect the
actual file first:

```python
import openpyxl
wb = openpyxl.load_workbook(path)
ws = wb.active

# Print first 3 rows to find header, unit, and first-data rows
for row in ws.iter_rows(min_row=1, max_row=3, values_only=True):
    print(row)
```

Map these quantities by scanning column headers (row 1 or row 2):

| Quantity | Expected header text | Unit row value |
|---|---|---|
| Time | "Time", "t", "Zeit" | "s" |
| Heat flow (W) | "Heat flow", "Wärmefluss", "HF" | "W" (not "W/g") |
| Time markers | "Marker", "Event", "Reaction start" | — |

**Report the exact column letters found before proceeding. Do NOT guess.**

---

## Step 2 — Ask two questions; wait for answers

After reporting the column mapping, ask the user:

> **Q1 – Reaction-start row:** I found "Reaction start" at row `<N>` (time = `<t>` s).
> Use that row, or would you like to override?
>
> **Q2 – Exclusion window:** How many minutes after reaction start should be excluded
> from the heat flow signal? Default is **45 min**.
>
> **Q3 – Sample mass (g):** What is the mass of the sample (binder/paste) in grams?
> This is used to normalise heat flow to mW/g and cumulative heat to J/g for the
> output columns and Origin export. (Check your TAM III run log or method sheet.)

**Do NOT proceed until the user answers all three questions.** Do not guess or use defaults silently.

---

## Step 3 — Write helper cells

Place labelled helper cells in an empty area (e.g. two columns right of the last
data column, starting at the reaction-start row):

| Cell | Label | Formula / value | Formatting |
|---|---|---|---|
| Helper col, reaction-start row | "Exclusion window (min)" | user-supplied integer | **Blue text, yellow fill** (editable input) |
| Helper col + 1, same row | "Cutoff (h)" | `=<minutes_cell>/60` | Black formula |
| Helper col, row+1 | "t_start (s)" | link to the Time cell at reaction-start row | Black formula |
| Helper col, row+2 | "Sample mass (g)" | user-supplied mass in grams | **Blue text, yellow fill** (editable input) |

Name conventions (use these in all downstream formulas):
- `cutoff_cell` → the "Cutoff (h)" cell address (e.g. `$M$10`)
- `t_start_cell` → the "t_start (s)" cell address (e.g. `$N$10`)
- `mass_cell` → the "Sample mass (g)" cell address (e.g. `$M$12`)

---

## Step 4 — Add three output columns

Insert headers in the **row directly above the reaction-start row** in four empty adjacent
columns (immediately after the existing data, or in a dedicated output area):

| Column | Header | Unit | Formula (fill down to last data row) |
|---|---|---|---|
| Col P | `Time (h)` | h | `=(t_col_row - {t_start_cell}) / 3600` |
| Col Q | `Normalised Heat flow (mW/g)` | mW/g | `=IF({time_h_cell} < {cutoff_cell}, "Null", {heatflow_col_row} * 1000 / {mass_cell})` |
| Col R | `Cumulative heat (J/g)` | J/g | see trapezoidal formula below |

**Unit note:** The raw TAM III signal is in W. Multiplying by 1000 converts to mW;
dividing by `mass_cell` normalises per gram. The trapezoidal integral of mW/g over
hours gives mW·h/g; multiplying by 3600 converts to J/g. Apply this ×3600 factor
inside the cumulative formula (see below).

### Trapezoidal cumulative heat formula (result in J/g)

For the **first valid row** (first row where Time (h) ≥ cutoff):
```
=IF(Q<row>="Null", 0, 0)
```

For **all subsequent rows**:
```
=IF(Q<row>="Null", 0,
   IF(Q<prev>="Null", 0,
      (Q<row> + Q<prev>) / 2 * (P<row> - P<prev>) * 3600 + R<prev>))
```

The `* 3600` converts the mW/g × h increment to J/g (since 1 W·h = 3600 J,
and mW/g × h × (1 W / 1000 mW) × 3600 s/h = 3.6 J/g per mW·h/g — but because
the signal is already in mW/g and time in h, the net factor is ×3.6; however
to keep the formula readable and exact, apply `* 3600 / 1000` = `* 3.6` or
express as `* 3600` where Q is in W/g not mW/g).

**Recommended approach — keep Q in W/g internally, display as mW/g:**

Alternatively, keep Col Q as `W/g` (dividing by mass only, no ×1000), then the
trapezoidal factor is simply `* 3600` to get J/g, and format the column display
as `0.000` with a cell note saying "×1000 for mW/g display". Either approach is
acceptable — but be consistent: if Q is in mW/g, the cumulative factor is `* 3.6`;
if Q is in W/g, the factor is `* 3600`. **Document which you used in a cell comment.**

This avoids `#VALUE!` at the boundary where the previous gated cell is still "Null".
Cumulative heat starts at 0 on the first valid (non-excluded) data point.

---

## Step 5 — Summary cells

Below (or beside) the helper cells, add:

| Label | Formula |
|---|---|
| `Total heat (J/g)` | `=<last R cell>` |
| `Total heat (kJ/kg)` | `=<total_Jg_cell>` *(same numeric value — 1 J/g = 1 kJ/kg, useful label for publication)* |

If `Total heat (J/g)` is negative, add a warning label cell:
`"⚠ Negative total — check for baseline drift"`.

---

## Step 6 — Draw two XY scatter charts

Use openpyxl's charting API. Both charts:
- X axis: Time (h) column (Col P)
- Smooth line series
- Placed to the right of the data

### Chart 1 — Normalised heat flow vs. time
- Y: Normalised heat flow (mW/g) column (Col Q)
- Axis titles: "Time (h)" / "Normalised heat flow (mW/g)"
- Series name: "Normalised heat flow (mW/g)"

### Chart 2 — Cumulative heat vs. time
- Y: Cumulative heat (J/g) column (Col R)
- Axis titles: "Time (h)" / "Cumulative heat (J/g)"
- Series name: "Cumulative heat (J/g)"

```python
from openpyxl.chart import ScatterChart, Reference, Series

chart = ScatterChart()
chart.style = 10
chart.title = "Normalised heat flow vs. time"
chart.x_axis.title = "Time (h)"
chart.y_axis.title = "Normalised heat flow (mW/g)"

xvalues = Reference(ws, min_col=p_col, min_row=header_row, max_row=last_row)
yvalues = Reference(ws, min_col=q_col, min_row=header_row, max_row=last_row)
series = Series(yvalues, xvalues, title="Normalised heat flow (mW/g)")
series.smooth = True
chart.series.append(series)

ws.add_chart(chart, anchor_cell)  # e.g. "T10"
```

Repeat for cumulative heat chart (J/g) anchored two rows below the first.

---

## Step 7 — Create "Origin Export" sheet

After all calculations are complete on the main sheet, create a new sheet named
**`Origin Export`** containing clean, values-only columns ready for paste-import into
OriginPro.

### Sheet structure

Row 1 — **Long name** (Origin layer 1): column headers
Row 2 — **Units** (Origin layer 2): unit strings
Row 3 onwards — numeric data values (no formulas, no "Null" strings)

| Column A | Column B | Column C |
|---|---|---|
| `Time` | `Normalised Heatflow` | `Cumulative Heatflow` |
| `h` | `mW/g` | `J/g` |
| numeric… | numeric… | numeric… |

**These are the exact Long name and Units strings Origin expects for these quantities.**
Do not alter the spelling or capitalisation.

### Rules for the export sheet

- **Values only, no formulas.** Copy the computed columns from the main sheet and
  paste as values. "Null" string rows (excluded window) are **omitted entirely** —
  only rows where Heat flow is a real number are written.
- **No headers beyond row 2.** Origin reads Long name from row 1 and Units from row 2
  automatically when you use File → Import → Excel (XLS, XLSX) with the "Sparklines /
  Column designation" option, or when pasting with headers.
- **No merged cells, no colours, no borders.** Plain numeric table only.
- **Time starts at 0.** The first exported row is the first post-exclusion data point,
  so Time (h) = 0 in that row (or the small positive offset from the trapezoid start —
  do not re-zero; just copy the Time (h) values as-is).

### Python implementation

```python
# After recalculating, read back computed values from main sheet
from openpyxl import load_workbook

wb = load_workbook('output.xlsx', data_only=True)
ws_main = wb.active

# Collect rows where Normalised heat flow is a real number (not "Null", not None)
export_rows = []
for row_idx in range(first_data_row, last_data_row + 1):
    t_h    = ws_main.cell(row=row_idx, column=p_col).value
    hf_mwg = ws_main.cell(row=row_idx, column=q_col).value
    cum_jg = ws_main.cell(row=row_idx, column=r_col).value
    if isinstance(hf_mwg, (int, float)):  # skip "Null" string rows
        export_rows.append((t_h, hf_mwg, cum_jg))

# Write Origin Export sheet — exact Long name / Units rows Origin expects
ws_exp = wb.create_sheet("Origin Export")
ws_exp.append(["Time", "Normalised Heatflow", "Cumulative Heatflow"])  # row 1 — Long name
ws_exp.append(["h", "mW/g", "J/g"])                                     # row 2 — Units
for row in export_rows:
    ws_exp.append(list(row))

wb.save('output.xlsx')
```

> **Note:** Load with `data_only=True` to read calculated values, not formula strings.
> Only do this read-back **after** `recalc.py` has run — otherwise cells will be `None`.

### Origin import instructions (tell the user)

After delivering the file, include this note:

> **To import into OriginPro:**
> 1. In the Origin Export sheet, select columns A–C from row 1 downward.
> 2. Copy (Ctrl+C).
> 3. In OriginPro, click the first empty column header in your workbook → Paste.
> 4. Right-click the column headers → **Set As** → **Long Name** for row 1, **Units** for row 2.
>    (Or: use **File → Import → Excel** and set "Number of rows for Long Name = 1,
>    Units = 1" in the import wizard.)
> 5. Column B will be labelled "Normalised Heatflow / mW/g" and Column C
>    "Cumulative Heatflow / J/g" — exactly as needed for publication-ready axis labels.
> 6. Plot as XY Scatter: X = Time (h), Y = Normalised Heatflow (mW/g) for the rate curve;
>    second graph Y = Cumulative Heatflow (J/g) for the energy curve.
>
> Alternatively, save the sheet as a separate `.csv`:
> — Switch to "Origin Export" sheet → File → Save As → CSV.
> In Origin, File → Import → Single ASCII, set header rows = 2.

---

## Step 8 — Recalculate and verify

Always run formula recalculation after saving:

```bash
python /mnt/skills/public/xlsx/scripts/recalc.py output.xlsx 60
```

Check the JSON output for any `#VALUE!`, `#REF!`, or `#DIV/0!` errors and fix before
returning the file.

Visually verify both charts render (capture screenshot if possible) and confirm in your
reply:
- The reaction-start row used
- The exact column letters mapped for Time (s), Heat flow (W), and Markers
- The cutoff cell address and exclusion window applied

---

## Key constraints

- **Zero hardcoded values** — every formula references the helper cells
- **No `#VALUE!` at the Null/valid boundary** — use nested IF as shown above
- **Negative total warning** — always check and flag
- **Blue text + yellow fill** on the minutes input cell (industry convention for editable inputs)
- **Do NOT assume column order** — always read headers first
- **Do NOT proceed past Step 2** without user confirmation of reaction-start row and exclusion window

---

## Edge cases

| Situation | Handling |
|---|---|
| No "Reaction start" marker found | Ask user to specify the row manually |
| Heat flow column in W/g not W | Note this — then skip the `/mass_cell` division (already normalised); still multiply by 1000 for mW/g |
| Multiple sheets in workbook | Process the active/first sheet; ask user if different sheet needed |
| Exclusion window > total experiment duration | Warn — cumulative heat will be zero |
| Time column in hours, not seconds | Detect from unit row; adjust `/3600` divisor accordingly |
| Sample mass not provided / zero | Warn and refuse to proceed — division by zero would corrupt all normalised values |
| Origin Export sheet already exists | Delete and recreate it (stale data must not accumulate) |
| Cumulative heat values are all None after recalc | `data_only=True` read before `recalc.py` ran — always recalc first |

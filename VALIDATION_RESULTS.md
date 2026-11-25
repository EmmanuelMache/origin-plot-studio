# Validation results — Origin Plot Studio 5.56.0

Date: 25 November 2026.

Python compilation and syntax checks passed for the application and tests.

| Suite | Result | Environment |
|---|---:|---|
| Workbench core | 35 passed | Python / Agg |
| Desktop workflow | 15 passed | Qt compatibility runtime |
| Template engine and Origin driver | 63 passed | Python / Agg; Origin dry run |
| Composed figures | 37 passed | Python / Agg |
| Analysis tools | 17 passed | Python / SciPy |
| HighScore / XRD workflows | 27 passed | Qt compatibility runtime |
| Workbook gallery | 34 passed | Python / Agg |

**Total: 228 checks passed across these seven suites.** Some individual checks exercise multiple tools or templates. The template suite includes the original templates and the added Line plot (122 registered templates), and checks their Origin command generation. The analysis suite exercises all 44 registered analysis tools. The workbook gallery covers the 26 workbook graph types.

Desktop workflow tests cover opening multiple files, graph independence, Workbook data edits without source modification, project save/close/reopen, portable project import/export, imported-project ownership, per-panel fit controls, ordinary session restoration, resize behaviour and independent sheet mappings.

The Qt checks used the available local compatibility runtime, not native Windows/PySide6. No live Origin installation or Windows COM automation was available. Those platform checks remain necessary on the target computer. Full details and commands are in `IMPLEMENTATION_AND_TESTS.md`.

Example-data screenshots are included in `docs/`. No user project settings, private credentials, local test adapter or generated test sessions are included in the application archive.

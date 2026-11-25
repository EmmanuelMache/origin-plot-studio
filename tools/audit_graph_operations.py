"""Audit of the per-graph controls over every installed graph type.

For each of the installed Analysis templates and each of the workbook graph types, the graph is drawn (the template's
own example, or the type's test workbook) and every per-graph control is tried on it. A control is recorded as

    works   the graph has that component and the control changed it (and only it)
    n/a     the graph has no such component: the control is not offered for it (nothing to switch)
    FAILS   the graph has the component and the control did not do what it says

Nothing is inferred: each cell is the result of doing it. Writes docs/GRAPH_OPERATIONS_AUDIT.md.
Run:  python tools/audit_graph_operations.py        (QT_QPA_PLATFORM=offscreen where there is no screen)"""
import os, sys, glob, tempfile, warnings, datetime
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ.setdefault("MPLBACKEND", "Agg"); os.environ["OPS_NO_OPEN"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "origin_plot_app")); warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from opstudio import api, core, origin as O
from opstudio.graph_components import apply, render_rietveld

OPS = ["draws", "markers", "one panel only", "zoom inset", "difference row", "Bragg rows", "background", "Origin commands"]


def data_lines(ax):
    return [l for l in ax.lines if len(l.get_xdata()) > 2 and l.get_marker() not in ("|", "_") and l.get_visible()]


def mains(fig):
    return [a for a in fig.axes if not getattr(a, "_ops_auxiliary", False) and a not in [c for b in fig.axes for c in b.child_axes]]


def has_marker(l): return l.get_marker() not in ("None", "none", "", None, " ")


def try_markers(make):
    fig = make(); lines = [l for a in mains(fig) for l in data_lines(a)]
    if not lines: plt.close(fig); return "n/a"
    apply(fig, {"markers": True}); on = all(has_marker(l) for l in lines)
    apply(fig, {"markers": False}); off = not any(has_marker(l) for l in lines) and all(l.get_linestyle() not in ("None", "none", "") for l in lines)
    plt.close(fig); return "works" if on and off else "FAILS"


def try_one_panel(make):
    fig = make(); panels = {}
    for i, a in enumerate(mains(fig)):
        if data_lines(a): panels.setdefault(getattr(a, "_ops_panel", i), []).extend(data_lines(a))
    if len(panels) < 2: plt.close(fig); return "n/a"
    first, *rest = sorted(panels)
    apply(fig, {"markers": False, "panel_options": {str(first): {"markers": True}}})
    ok = all(has_marker(l) for l in panels[first]) and not any(has_marker(l) for k in rest for l in panels[k])
    plt.close(fig); return "works" if ok else "FAILS"


def try_inset(make):
    fig = make(); kids = [c for a in fig.axes for c in a.child_axes]
    if not kids: plt.close(fig); return "n/a"
    apply(fig, {"inset": False}); off = not any(c.get_visible() for c in kids)
    apply(fig, {"inset": True}); on = all(c.get_visible() for c in kids)
    plt.close(fig); return "works" if on and off else "FAILS"


def try_background(make):
    fig = make(); lines = [l for a in fig.axes for l in a.lines if any(k in str(l.get_label()).lower() for k in ("background", "baseline"))]
    if not lines: plt.close(fig); return "n/a"
    apply(fig, {"show_background": False}); off = not any(l.get_visible() for l in lines)
    apply(fig, {"show_background": True}); on = all(l.get_visible() for l in lines)
    plt.close(fig); return "works" if on and off else "FAILS"


def try_fit_rows(tid, template, style):
    """Difference and Bragg rows of the pattern-and-fit templates: off removes the row (and only it), per panel too."""
    if template.data_kind != "rietveld": return "n/a", "n/a"
    def roles(sw):
        fig = render_rietveld(tid, template.demo(), style, dict(template.params), sw); r = [(getattr(a, "_ops_panel", 0), getattr(a, "_ops_role", "")) for a in fig.axes]; plt.close(fig); return r
    base = roles({}); n = len({p for p, _ in base})
    def result(role, key):
        if not any(r == role for _, r in base): return "n/a"
        off = roles({key: False}); other = "bragg" if role == "difference" else "difference"
        ok = not any(r == role for _, r in off) and sum(r == other for _, r in off) == sum(r == other for _, r in base) and sum(r == "main" for _, r in off) == n
        if ok and n > 1:                                               # one panel only: the others keep theirs
            one = roles({"panel_options": {"0": {key: False}}}); ok = sum(r == role for _, r in one) == n - 1 and not any(p == 0 and r == role for p, r in one)
        return "works" if ok else "FAILS"
    return result("difference", "show_difference"), result("bragg", "show_bragg")


def try_origin(make, name, folder):
    import origin_plot_app as opa
    fig = make()
    try: O.send(opa.Driver(folder, lambda m: None, dry=True), fig, name); return "works"
    except Exception as e: return "FAILS (" + type(e).__name__ + ")"
    finally: plt.close(fig)


def audit_templates(folder):
    rows = []; style = core.load_style(api.DEFAULT_STYLE)
    for row in api.all_templates():
        tid = row["id"]; t = api.resolve(tid)[0]; make = lambda tid=tid: api.demo_figure(tid)
        try: plt.close(make()); r = {"draws": "works"}
        except Exception as e: rows.append((t.category, tid, row["name"], {k: ("FAILS (" + type(e).__name__ + ")" if k == "draws" else "not tried") for k in OPS})); continue
        r["markers"] = try_markers(make); r["one panel only"] = try_one_panel(make); r["zoom inset"] = try_inset(make); r["background"] = try_background(make)
        r["difference row"], r["Bragg rows"] = try_fit_rows(tid, t, style)
        if t.data_kind == "rietveld":                                 # the zoom of a fit is a parameter of the drawing: on / off and one panel only
            def kids(sw): fig = render_rietveld(tid, t.demo(), style, dict(t.params, zoom=[28, 36]), sw); k = sorted(getattr(c, "_ops_panel", 0) for a in fig.axes for c in a.child_axes if getattr(c, "_ops_role", "") == "inset"); plt.close(fig); return k
            on, off, one = kids({"inset": True}), kids({"inset": False}), kids({"inset": True, "panel_options": {"0": {"inset": False}}})
            r["zoom inset"] = "works" if on and not off and one == [p for p in on if p != 0] else "FAILS"
        r["Origin commands"] = try_origin(make, tid, folder)
        rows.append((t.category, tid, row["name"], r))
    return rows


def audit_workbook_types(folder):
    import gallery_graphs as TG
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "tests", "gallery_templates", "*.xlsx"))):
        tid = os.path.basename(path).split("_")[0]
        def make(path=path, tid=tid): return TG.figure(tid, TG.read_book(path))[0]
        try: plt.close(make()); r = {"draws": "works"}
        except Exception as e: rows.append(("Workbook graph types", tid, TG.TYPES.get(tid, [tid])[0] if isinstance(TG.TYPES.get(tid), (list, tuple)) else tid, {k: ("FAILS (" + type(e).__name__ + ")" if k == "draws" else "not tried") for k in OPS})); continue
        r["markers"] = try_markers(make); r["one panel only"] = try_one_panel(make); r["zoom inset"] = try_inset(make); r["background"] = try_background(make)
        r["difference row"] = r["Bragg rows"] = "n/a (own layout)"       # these figures keep their own recipe: their rows are part of the type
        r["Origin commands"] = try_origin(make, tid, folder)
        name = TG.TYPES.get(tid); name = name.get("name") if isinstance(name, dict) else (name[0] if isinstance(name, (list, tuple)) else str(name or tid))
        rows.append(("Workbook graph types", tid, name, r))
    return rows


def main():
    folder = tempfile.mkdtemp(prefix="ops-audit-")
    rows = audit_templates(folder) + audit_workbook_types(folder)
    counts = {op: {} for op in OPS}
    for _c, _i, _n, r in rows:
        for op in OPS: k = r[op].split(" ")[0]; counts[op][k] = counts[op].get(k, 0) + 1
    out = ["# Graph operations audit", "",
           f"Made by `tools/audit_graph_operations.py` on {datetime.date.today().isoformat()} (app {__import__('smart_plots').VERSION}). Every cell is the result of trying that control on that graph, drawn from",
           "the template's own example or the workbook type's test workbook - it is not inferred from the number of passing tests.", "",
           "* **works**: the graph has that component and the control changed it, and only it.",
           "* **n/a**: the graph has no such component (no curve with points, a single panel, no inset, no fit ...). The control is not offered / is greyed out with the reason.",
           "* **FAILS**: the graph has the component and the control did not do what it says.", "",
           "'Origin commands' is the app's Origin driver in dry-run mode (it writes the LabTalk commands and worksheets). It is not a run in Origin.", "",
           "## Summary", "", "| Control | works | n/a | FAILS |", "|---|---:|---:|---:|"]
    for op in OPS: out.append(f"| {op} | {counts[op].get('works', 0)} | {counts[op].get('n/a', 0)} | {counts[op].get('FAILS', 0) + counts[op].get('not', 0)} |")
    out += ["", f"{sum(1 for r in rows if r[0] != 'Workbook graph types')} Analysis templates and {sum(1 for r in rows if r[0] == 'Workbook graph types')} workbook graph types. Catalogue rows marked \"Coming\" are not graphs yet and are not in this table.", ""]
    for cat in dict.fromkeys(r[0] for r in rows):
        out += [f"## {cat}", "", "| Graph | " + " | ".join(OPS) + " |", "|---|" + "---|" * len(OPS)]
        for c, tid, name, r in rows:
            if c == cat: out.append(f"| {name} (`{tid}`) | " + " | ".join(r[op] for op in OPS) + " |")
        out.append("")
    path = os.path.join(ROOT, "docs", "GRAPH_OPERATIONS_AUDIT.md"); os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(out))
    fails = [(tid, op, r[op]) for _c, tid, _n, r in rows for op in OPS if r[op].startswith(("FAILS", "not"))]
    print(f"{len(rows)} graph types audited -> {path}"); print("summary:", {op: counts[op] for op in OPS})
    for f in fails: print("FAILS", f)
    return 1 if fails else 0


if __name__ == "__main__":
    code = main(); sys.stdout.flush(); os._exit(code)

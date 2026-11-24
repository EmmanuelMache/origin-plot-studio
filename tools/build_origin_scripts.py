"""Write the Origin script of every template (origin_plot_app/opstudio/origin/<id>.ogs) from its illustrative figure,
through the app's Origin driver in dry-run mode, and the list of what Origin gets differently (origin/DIFFERENCES.md).
The script shows the layout commands of the template; when you draw your own data, the app writes the complete script
(with your worksheets) beside the .opju.   Run:  python tools/build_origin_scripts.py"""
import os, re, sys, tempfile, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "origin_plot_app"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); warnings.filterwarnings("ignore")
import opstudio
from opstudio import api, origin as O
import origin_plot_app as opa


def main():
    out = os.path.join(ROOT, "origin_plot_app", "opstudio", "origin"); os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp(); rows = []; fails = []
    for tid in opstudio.REGISTRY:
        try:
            r = O.draw_in_origin(lambda f: opa.Driver(f, lambda m: None, dry=True), api.demo_figure(tid), "demo", tid, os.path.join(tmp, tid))
            cmds = [re.sub(re.escape(os.path.join(tmp, tid)) + r"[\\/]?", "<data folder>/", c) for c in r["commands"]]
            O.write_ogs(cmds, os.path.join(out, tid + ".ogs"), f"Template {tid}: layout commands (illustrative data)")
            rows.append((tid, r["differences"]))
        except Exception as e: fails.append((tid, repr(e)))
    with open(os.path.join(out, "DIFFERENCES.md"), "w", encoding="utf-8") as f:
        f.write("# What Origin gets differently, per template\n\nWritten by `tools/build_origin_scripts.py`. An empty cell means: the same graph.\n\n| Template | Difference in Origin |\n|---|---|\n")
        for tid, d in rows: f.write(f"| `{tid}` | {'<br>'.join(d)} |\n")
    same = sum(1 for _, d in rows if not d)
    print(f"{len(rows)} scripts written ({same} templates without any difference), {len(fails)} failed: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

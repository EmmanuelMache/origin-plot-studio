"""Rebuild the template library of the app from its draw functions and illustrative data:
origin_plot_app/opstudio/templates/*.json, previews/*.png (landscape, marked 'Illustrative example'), catalog.json.
Run:  python tools/build_template_library.py"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "origin_plot_app"))
import opstudio
from opstudio import core, api

LIB = os.path.join(ROOT, "origin_plot_app", "opstudio")


def main():
    for d in ("templates", "previews"): os.makedirs(os.path.join(LIB, d), exist_ok=True)
    cat, fails = [], []
    for tid, t in opstudio.REGISTRY.items():
        try:
            fig = api.demo_figure(tid); core.save(fig, os.path.join(LIB, "previews", tid + ".png"), dpi=110)
            j = core.template_json(t); o = os.path.join(LIB, "origin", tid + ".ogs")
            j["origin_template"] = {"script": f"origin/{tid}.ogs" if os.path.isfile(o) else "", "otpu": f"origin/{tid}.otpu"}
            json.dump(j, open(os.path.join(LIB, "templates", tid + ".json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str); cat.append(j)
        except Exception as e:
            fails.append((tid, repr(e)))
    json.dump(cat, open(os.path.join(LIB, "catalog.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(f"{len(cat)} templates built, {len(fails)} failed: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

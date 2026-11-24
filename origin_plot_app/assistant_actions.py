"""The fixed list of things the assistant may ask the app to do, and the dispatcher that runs them.

Every action maps to a function the app already has. The dispatcher rejects any action that is not in ACTIONS, checks the
parameters against the schema, asks the user to confirm ("Run: <action>, <params>. OK?"), and then calls the handler.
Nothing here executes text that a model produced: no Python, no LabTalk, no shell. No data rows pass through this module.
"""
import json
import re

class ActionError(ValueError): pass

# name -> {"help": ..., "params": {name: (type, required, default)}}   types: "float", "int", "bool", "str", "intervals", "strlist"
ACTIONS = {
    "plot_tga": {"help": "Draw TG (left axis) and DTG (right axis) in one graph; optionally mark the mass loss between temperatures.",
                 "params": {"with_dtg": ("bool", False, True), "intervals": ("intervals", False, None), "annotate": ("bool", False, False)}},
    "analyze_tga_steps": {"help": "Mass loss in temperature intervals of the loaded TGA table (default 50-200, 400-500, 600-800 °C).",
                          "params": {"intervals": ("intervals", False, None)}},
    "stack_xrd": {"help": "Stack all loaded XRD patterns in one graph with a vertical offset.",
                  "params": {"offset_mode": ("str", False, "auto_percent"), "offset_value": ("float", False, None), "palette": ("str", False, None)}},
    "plot_calorimetry": {"help": "Process isothermal calorimetry and draw heat flow with cumulative heat.",
                         "params": {"exclusion_min": ("float", False, 45.0), "mass_g": ("float", True, None)}},
    "rietveld_two_panel": {"help": "Rietveld fit (observed, calculated, difference, phase ticks) with a phase-amount bar chart.",
                           "params": {"amounts_file": ("str", False, None)}},
    "figtype_graph": {"help": "Draw the ticked (or shown) workbook as one of the gallery graph types G01-G24 or calculations C01-C02 (labels only from the file).",
                     "params": {"type": ("str", True, None)}},
    "generate_xrd_scans": {"help": "Open the XRD scan generator (randomised scans from an .xrdml template), optionally with the number of scans.",
                           "params": {"n": ("int", False, None)}},
    "system_check": {"help": "Show the System Check (Python, packages, OriginPro, Windows data protection).", "params": {}},
}
OFFSET_MODES = ("auto_percent", "fixed_value")

EXAMPLES = ["plot TGA with DTG and annotate mass loss between 400 and 500 C",
            "stack all XRD files with vertical offset",
            "plot calorimetry, exclusion 45 min, mass 0.5 g",
            "generate 10 XRD scans from a template",
            "draw the phase evolution of this file",
            "make a 2x2 grid of hydration degree, anhydrite vs gypsum"]

def action_list_text():
    """The list a model is shown: names, parameters, one line each. Never data."""
    return "\n".join(f"- {n}({', '.join(f'{p}: {t[0]}' + ('' if t[1] else '?') for p, t in a['params'].items())}): {a['help']}" for n, a in ACTIONS.items())

def _coerce(kind, v, name):
    try:
        if kind == "float":
            f = float(str(v).replace(",", "."))
            if f != f or f in (float("inf"), float("-inf")): raise ValueError
            return f
        if kind == "int": return int(v)
        if kind == "bool":
            if isinstance(v, bool): return v
            if str(v).strip().lower() in ("true", "yes", "1"): return True
            if str(v).strip().lower() in ("false", "no", "0"): return False
            raise ValueError
        if kind == "str": return str(v)
        if kind == "intervals":
            out = [[float(a), float(b)] for a, b in v]
            if any(b <= a for a, b in out): raise ValueError
            return out
    except (TypeError, ValueError): pass
    raise ActionError(f"parameter '{name}' has an unusable value: {str(v)[:60]!r}")

def validate(act):
    """{"action", "params"} -> a clean copy, or ActionError. Unknown actions and unknown parameters are refused."""
    if not isinstance(act, dict) or "action" not in act: raise ActionError("an action needs the field 'action'")
    name = act["action"]
    if not isinstance(name, str) or name not in ACTIONS: raise ActionError(f"unknown action: {str(name)[:40]!r}")
    given = act.get("params") or {}
    if not isinstance(given, dict): raise ActionError("'params' must be an object")
    spec = ACTIONS[name]["params"]; extra = [k for k in given if k not in spec]
    if extra: raise ActionError(f"unknown parameter(s) for {name}: {', '.join(map(str, extra))}")
    out = {}
    for p, (kind, req, dflt) in spec.items():
        if p in given and given[p] is not None: out[p] = _coerce(kind, given[p], p)
        elif req: raise ActionError(f"{name} needs '{p}'")
        elif dflt is not None: out[p] = dflt
    if name == "plot_calorimetry" and out["mass_g"] <= 0: raise ActionError("sample mass must be above zero")
    if name == "plot_calorimetry" and out["exclusion_min"] < 0: raise ActionError("the exclusion window cannot be negative")
    if name == "figtype_graph":
        t_ = str(out["type"]).strip().upper()[:3]
        if not re.match(r"^[GC]\d\d$", t_) or not (t_.startswith("G") and 1 <= int(t_[1:]) <= 24 or t_ in ("C01", "C02")): raise ActionError("type must be one of G01-G24, C01, C02")
        out["type"] = t_
    if name == "generate_xrd_scans" and "n" in out and not (1 <= out["n"] <= 10000): raise ActionError("the number of scans must be 1 to 10000")
    if name == "stack_xrd":
        if out.get("offset_mode") not in OFFSET_MODES: raise ActionError("offset_mode must be auto_percent or fixed_value")
        if out["offset_mode"] == "fixed_value" and "offset_value" not in out: raise ActionError("fixed_value needs offset_value")
    return {"action": name, "params": out}

def describe(act):
    return f"Run: {act['action']}, {json.dumps(act['params'], ensure_ascii=False)}. OK?"

def dispatch(act, handlers, confirm, record=None):
    """Validate, confirm, run. handlers: {action name: function(**params)}; confirm: function(text) -> bool; record: list that receives the
    confirmed action (it ends up in the provenance file of the figures). Returns the handler's result, or None when the user said no."""
    a = validate(act)
    if a["action"] not in handlers: raise ActionError(f"this app has no handler for {a['action']}")
    if not confirm(describe(a)): return None
    if record is not None: record.append({"action": a["action"], "params": a["params"]})
    return handlers[a["action"]](**a["params"])

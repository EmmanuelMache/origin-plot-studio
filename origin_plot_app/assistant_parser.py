"""The default assistant backend: keywords and patterns, no network, no model. A sentence either matches an action or it does not;
an unknown sentence gets the help message with examples, never a guess."""
import re
from assistant_actions import EXAMPLES, ActionError

HELP = "I did not understand that. I can only do a fixed list of things. Try, for example:\n" + "\n".join("  • " + e for e in EXAMPLES)
_NUM = r"(-?\d+(?:[.,]\d+)?)"

def _f(s): return float(s.replace(",", "."))

GALLERY_WORDS = [            # (pattern, type): the first that matches wins; only words that name a gallery graph type
    (r"\b(?:g|c)(\d\d)\b", None),
    (r"\b(grid|small multiples|\d\s*[x×]\s*\d|panels? (?:per|for each))\b", "G13"),
    (r"\bmethod comparison|compare (?:the )?methods\b", "G14"),
    (r"\bmass balance|oxide budget\b", "G15"),
    (r"\bphase evolution|phase contents? (?:over|vs|against) time|split (?:time )?axis\b", "G12"),
    (r"\b(?:degree of hydration|hydration degree)\b", "C01"),
    (r"\batomic ratios?\b", "C02"),
    (r"\bternary contour|contour maps? (?:over|on) (?:the )?(?:ternary|triangle)\b", "G23"),
    (r"\bternary\b", "G22"),
    (r"\bnmr\b.*\bdeconvol|deconvolution\b", "G05"),
    (r"\bnmr\b.*\bannotat|annotated (?:29si|nmr|spectrum)\b", "G06"),
    (r"\bnmr\b", "G04"),
    (r"\b(?:refinement indices|rwp|chi2|χ2|chi square)\b", "G24"),
    (r"\b(?:stacked areas?|phase assemblage)\b", "G21"),
    (r"\b(?:psd|particle size)\b", "G20"),
    (r"\bbars? (?:with|and) (?:a )?line\b", "G19"),
    (r"\bgrouped bars?|bars? with error\b", "G18"),
    (r"\b(?:scatter|labelled points)\b.*\btrend|trend ?line\b", "G17"),
    (r"\b(?:against|vs\.?|versus) (?:the )?(?:w/b|water/binder|mix) ?ratio\b", "G16"),
    (r"\b(?:concentrations?|ions?)\b.*\b(?:log|heat flow)\b", "G11"),
    (r"\b(?:calorimetry pair|heat flow (?:with|and) (?:an )?inset|heat flow and cumulative heat)\b", "G10"),
    (r"\bxrd and dtg|xrd (?:with|beside) (?:the )?dtg\b", "G09"),
    (r"\b(?:compare (?:the )?dtg|dtg compar\w*|overlay (?:the )?dtg)\b", "G08"),
    (r"\bxrd (?:stack )?with (?:a )?(?:highlight|zoom)|highlight box\b", "G01"),
    (r"\b(?:peak labels? and (?:an )?inset|xrd (?:with|and) (?:an )?inset)\b", "G02"),
    (r"\brietveld fit\b", "G03"),
]


def figtype_type(t):
    """The gallery graph type a sentence names, or None. Never guessed from data, only from the words."""
    for pat, tid in GALLERY_WORDS:
        m = re.search(pat, t)
        if not m:
            continue
        if tid is None:
            k = re.search(r"\b([gc])(\d\d)\b", t)
            n = int(k.group(2))
            if (k.group(1) == "g" and 1 <= n <= 24) or (k.group(1) == "c" and n in (1, 2)):
                return f"{k.group(1).upper()}{n:02d}"
            continue
        return tid
    return None


def parse(text):
    """Sentence -> {"action", "params"}, or None when nothing matches."""
    t = " ".join(str(text or "").lower().split())
    if not t: return None
    th = figtype_type(t)
    if th:
        return {"action": "figtype_graph", "params": {"type": th}}
    if re.search(r"\b(system check|check (my )?system|pre-?flight)\b", t): return {"action": "system_check", "params": {}}
    if re.search(r"\b(generat\w*|simulat\w*|synthetic|make|create)\b.*\b(xrd|xrdml|diffraction)\b.*\b(scans?|patterns?|files?)\b", t) or re.search(r"\bxrd (scan )?generator\b", t):
        m = re.search(r"\b(\d+)\s*(?:new\s+)?(?:synthetic\s+|random\w*\s+)?(?:xrd|xrdml|scans?|patterns?)", t)
        return {"action": "generate_xrd_scans", "params": {"n": int(m.group(1))} if m else {}}
    if re.search(r"\b(calorimetr\w*|heat ?flow|tam)\b", t):
        m = re.search(r"mass\s*(?:of|=|:)?\s*" + _NUM + r"\s*(mg|g)?\b", t) or re.search(_NUM + r"\s*(mg|g)\b\s*(?:sample|mass)?", t)
        e = re.search(r"exclu\w*\s*(?:window)?\s*(?:of|=|:)?\s*" + _NUM + r"\s*(min|h|hr|hour)?", t)
        p = {}
        if m:
            v = _f(m.group(1)); p["mass_g"] = v / 1000.0 if (m.group(2) or "g") == "mg" else v
        if e:
            v = _f(e.group(1)); p["exclusion_min"] = v * 60.0 if (e.group(2) or "min").startswith("h") else v
        return {"action": "plot_calorimetry", "params": p}
    if re.search(r"\b(tga|dtg|thermogravimetr\w*|mass loss)\b", t):
        ivs = [[_f(a), _f(b)] for a, b in re.findall(r"(?:between|from)\s*" + _NUM + r"\s*(?:and|to|-|–)\s*" + _NUM, t)]
        ivs += [[_f(a), _f(b)] for a, b in re.findall(_NUM + r"\s*(?:-|–)\s*" + _NUM + r"\s*(?:°|deg)?\s*c\b", t)]
        steps_only = re.search(r"\b(analy[sz]e|steps|intervals|table)\b", t) and not re.search(r"\b(plot|draw|graph|show)\b", t)
        if steps_only: return {"action": "analyze_tga_steps", "params": {"intervals": ivs} if ivs else {}}
        p = {"with_dtg": not re.search(r"\b(tg only|without dtg|no dtg|only tg)\b", t)}
        if ivs: p["intervals"] = ivs
        if re.search(r"\b(annotate|mark|label)\b", t) or ivs: p["annotate"] = True
        return {"action": "plot_tga", "params": p}
    if re.search(r"\b(rietveld|phase amounts?|refinement)\b", t): return {"action": "rietveld_two_panel", "params": {}}
    if re.search(r"\b(xrd|diffractogram|patterns?)\b", t) and re.search(r"\b(stack\w*|offset|waterfall)\b", t):
        p = {}
        m = re.search(r"offset\s*(?:of|=|:)?\s*" + _NUM + r"\s*(%)?", t)
        if m and m.group(2): p["offset_mode"] = "auto_percent"; p["offset_value"] = _f(m.group(1))
        elif m: p["offset_mode"] = "fixed_value"; p["offset_value"] = _f(m.group(1))
        return {"action": "stack_xrd", "params": p}
    return None

def run(text):
    """Parse and return (action or None, message). The message is the help text when nothing matched."""
    a = parse(text)
    return (a, "") if a else (None, HELP)

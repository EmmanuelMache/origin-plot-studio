"""privacy.py - what may be kept, and the stricter rule for what may be shared.

Two filters, both ALLOWLISTS (a field that is not named here does not pass; there is no list of "bad" fields to forget):

    local_snapshot(raw, context)   what an event / a memory on THIS computer may contain: data family, column roles
                                   (as positions in the context), declared units, reading rules, template id, the closed
                                   style vocabulary, supported workflow steps. Never rows or cell values, frames, paths,
                                   file names, sample names, graph titles, notes, fitted parameters, credentials - and
                                   no numerical axis limits unless the caller asks for them (include_limits=True).

    shareable(memory)              the projection that may leave the computer after consent and preview: header words
                                   are replaced by recognised structural roles ('x:two_theta', 'y:intensity'); a column
                                   the recipe uses whose header is not recognised makes the contribution needs_review
                                   (withheld until the user names the role); units outside the known table become
                                   'other'; ids, limits, local signatures and instrument words outside a small known
                                   list are left out; anything outbound_policy.has_secret() hits is refused.

Standard library only.
"""
import copy, re

from . import models as M
from . import signatures as sg


MAX_SHARE_BYTES = 32768          # what the shared service accepts for one record (it checks again; this is the client's own limit)
MAX_SHARE_ITEMS = 256            # ... and for one list inside it


def _has_secret(text): return M._has_secret(text)


def _version(text):
    """An app version as it may be shared ('5.58.6', '5.58.6-rc1'), or ''."""
    t = str(text or "").strip()
    return t if re.match(r"^[0-9]{1,4}(\.[0-9]{1,4}){1,3}([.+-][A-Za-z0-9.]{1,16})?$", t) else ""


def _longest_list(obj):
    if isinstance(obj, (list, tuple)): return max([len(obj)] + [_longest_list(v) for v in obj])
    if isinstance(obj, dict): return max([0] + [_longest_list(v) for v in obj.values()])
    return 0


def _strip_paths(text):
    try:
        import outbound_policy
        return outbound_policy.strip_paths(text)
    except Exception:
        return re.sub(r"(?:[A-Za-z]:\\|\\\\|/(?:home|Users|mnt|media|Volumes|root|tmp|var)/)[^\s\"'<>|]*", "<folder>", str(text))


# ------------------------------------------------------------------------------------------------ local snapshot
def _ref_index(v, context):
    """A column reference of the caller (position, header text, or {'i'/'h': ...}) as a position in the context, or None."""
    n = context.column_count if context is not None else M.MAX_COLUMNS
    if isinstance(v, dict): v = v.get("i") if isinstance(v.get("i"), int) and not isinstance(v.get("i"), bool) else v.get("h")
    if isinstance(v, bool) or v is None: return None
    if isinstance(v, int): return v if 0 <= v < n else None
    if isinstance(v, str) and context is not None:
        tok = sg.split_header(v)[0]
        hits = [i for i, h in enumerate(context.headers) if h and h == tok]
        return hits[0] if len(hits) == 1 else None
    return None


def local_snapshot(raw, context=None, *, include_limits=False):
    """The allowlisted copy of a before/after description. Keys read from `raw` (everything else is ignored):

        data_family        'XRD' / 'xrd' ...                  -> storage word
        confirmed          bool: the user confirmed the type
        roles              {'x': col, 'y': [cols], 'yerr': [cols], 'label': col, 'obs'/'calc'/'diff'/'background': col}
                           a col is a position (int) or the header text of a column of `context`
        x_index, y_indices the same as roles.x / roles.y (positions)
        units              list per column, or {position or header: unit}
        read               {'delimiter', 'decimal', 'encoding', 'header_row', 'skip_rows', 'sheet_index'}
        template_id, template_version
        style              the closed style vocabulary of models.STYLE (unknown keys dropped)
        target             {'scope': 'graph'|'panel'|'family', 'panel_index': n}
        workflow           {'steps': [{'op': ..., 'params': {...}}]}  (or 'steps' directly); dropped as a whole when a
                           step is not a supported operation
    Numerical axis limits inside a style are removed unless include_limits=True. The result contains positions, words
    from closed vocabularies, booleans and bounded numbers of presentation settings - never a measured value."""
    raw = raw if isinstance(raw, dict) else {}
    ctx = context if isinstance(context, M.Context) or context is None else M.Context.build(context)
    out = {}
    if "data_family" in raw: out["data_family"] = M.family_token(raw.get("data_family"))
    if isinstance(raw.get("confirmed"), bool): out["confirmed"] = raw["confirmed"]
    src = dict(raw["roles"]) if isinstance(raw.get("roles"), dict) else {}
    if "x_index" in raw: src.setdefault("x", raw["x_index"])
    if "y_indices" in raw: src.setdefault("y", raw["y_indices"])
    roles = {}
    for name in M.ROLE_NAMES:
        if name not in src: continue
        v = src[name]
        if name in ("y", "yerr"):
            seq = v if isinstance(v, (list, tuple)) else [v]
            idx = []
            for x in list(seq)[:64]:
                i = _ref_index(x, ctx)
                if i is not None and i not in idx: idx.append(i)
            if idx: roles[name] = idx
        else:
            i = _ref_index(v, ctx)
            if i is not None: roles[name] = i
    if roles: out["roles"] = roles
    u = raw.get("units")
    if isinstance(u, (list, tuple)):
        n = ctx.column_count if ctx is not None else len(u)
        units = [sg.norm_unit(x) if isinstance(x, str) else "" for x in list(u)[:M.MAX_COLUMNS]]
        out["units"] = (units + [""] * n)[:max(n, 0) or len(units)]
    elif isinstance(u, dict) and ctx is not None:
        units = list(ctx.units)
        for k, x in list(u.items())[:M.MAX_COLUMNS]:
            i = _ref_index(int(k) if isinstance(k, str) and k.isdigit() else k, ctx)
            if i is not None and isinstance(x, str) and i < len(units): units[i] = sg.norm_unit(x)
        out["units"] = units
    if isinstance(raw.get("read"), dict):
        r = dict(raw["read"])
        if isinstance(r.get("delimiter"), str): r["delimiter"] = M._DELIMITER_NAMES.get(r["delimiter"].strip().lower(), r["delimiter"])
        try:
            r = M._READ(r, False, "read")
            if r: out["read"] = r
        except M.RecipeError: pass
    for key, rx in (("template_id", r"^[a-z0-9_]{1,64}$"), ("template_version", r"^[A-Za-z0-9_.\-]{1,32}$")):
        v = raw.get(key)
        if isinstance(v, str) and re.match(rx, v): out[key] = v
    if isinstance(raw.get("style"), dict):
        try:
            st = M.STYLE(raw["style"], False, "style")
            if not include_limits: st = M.strip_limits(st)
            st = {k: v for k, v in st.items() if v not in ({}, [])}
            if st:
                out["style"] = st
                if include_limits and M.has_limits(st): out["include_limits"] = True
        except M.RecipeError: pass
    if isinstance(raw.get("target"), dict):
        try: out["target"] = M.TARGET(raw["target"], False, "target")
        except M.RecipeError: pass
    wf = raw.get("workflow") if isinstance(raw.get("workflow"), dict) else ({"steps": raw["steps"]} if isinstance(raw.get("steps"), (list, tuple)) else None)
    if wf is not None:
        try:
            steps = M.Arr(M._step, 1, 32)(wf.get("steps") or [], True, "steps")          # all steps supported, or no workflow at all
            M.assert_inert(steps)
            out["workflow"] = {"steps": steps}
        except M.RecipeError: pass
    return out


def diff(before, after):
    """Field-level difference of two snapshots: {field: {'before': ..., 'after': ...}} for every field that differs.
    Fields: data_family, confirmed, roles.<name>, units, read.<key>, template_id, style, target, workflow."""
    before = before or {}; after = after or {}; out = {}
    def put(name, b, a):
        if b != a: out[name] = {"before": copy.deepcopy(b), "after": copy.deepcopy(a)}
    for k in ("data_family", "confirmed", "units", "template_id", "style", "target", "workflow", "include_limits"): put(k, before.get(k), after.get(k))
    for sect in ("roles", "read"):
        b = before.get(sect) or {}; a = after.get(sect) or {}
        for k in sorted(set(b) | set(a)): put(f"{sect}.{k}", b.get(k), a.get(k))
    return out


# ------------------------------------------------------------------------------------------------ shareable projections
def _role_axes(roles):
    """{position: role name} from snapshot roles ({'x': 0, 'y': [1, 2]}) or recipe roles ({'x': {'i': 0}, ...})."""
    axes = {}
    for name, v in (roles or {}).items():
        for r in (v if isinstance(v, list) else [v]):
            i = r.get("i") if isinstance(r, dict) else r
            if isinstance(i, int) and not isinstance(i, bool): axes.setdefault(i, name)
    return axes


def shareable_context(context, roles=None, role_overrides=None):
    """(projection, needs_review) of a stored context dict: container, separators, whether there is a header row, the
    column count and per column a structural role and a known unit. No header word survives. needs_review is True when
    a column the recipe USES has a header that is not a recognised role (and no override names it)."""
    c = context or {}; axes = _role_axes(roles); over = {int(k): str(v) for k, v in (role_overrides or {}).items() if str(v) in sg.KNOWN_ROLES and str(v) != "unknown"}
    heads = list(c.get("headers") or []); units = list(c.get("units") or []); n = int(c.get("column_count") or len(heads)); cols = []; review = False
    for i in range(min(n, M.MAX_COLUMNS)):
        role = over.get(i) or sg.classify_header(heads[i] if i < len(heads) else "")
        u = sg.norm_unit(units[i]) if i < len(units) else ""
        u = u if sg.unit_known(u) else ("other" if u else "")
        axis = axes.get(i, "-")
        if axis != "-" and role == "unknown": review = True
        cols.append({"role": f"{axis}:{role if (axis != '-' or role != 'unknown') else 'other'}", "unit": u})
    proj = {"container": c.get("container") if c.get("container") in M.CONTAINERS else "other",
            "delimiter": c.get("delimiter") if c.get("delimiter") in M.DELIMITERS else "", "decimal": c.get("decimal") if c.get("decimal") in M.DECIMALS else ".",
            "header": bool(int(c.get("header_row") or 0) >= 0 and any(heads)), "column_count": len(cols), "columns": cols}
    return proj, review


def shareable_snapshot(snapshot, context, role_overrides=None):
    """(projection, needs_review) of a local before/after snapshot for evidence and previews: the data family, the roles
    as structural role words, known units of the used columns, the template id, the style without limits, the workflow."""
    s = snapshot or {}; c = context or {}; heads = list(c.get("headers") or []); out = {}; review = False
    over = {int(k): str(v) for k, v in (role_overrides or {}).items()}
    def word(i):
        nonlocal review
        r = over.get(i) or sg.classify_header(heads[i] if isinstance(i, int) and 0 <= i < len(heads) else "")
        if r == "unknown": review = True
        return r
    if "data_family" in s: out["data_family"] = M.family_token(s["data_family"])
    if isinstance(s.get("confirmed"), bool): out["confirmed"] = s["confirmed"]
    if s.get("roles"):
        out["roles"] = {k: ([word(i) for i in v] if isinstance(v, list) else word(v)) for k, v in s["roles"].items() if k in M.ROLE_NAMES}
        units = list(s.get("units") or c.get("units") or [])
        used = sorted(_role_axes(s["roles"]))
        out["units"] = [(units[i] if i < len(units) and sg.unit_known(units[i]) else ("other" if i < len(units) and units[i] else "")) for i in used]
    if s.get("read"): out["read"] = {k: v for k, v in s["read"].items() if k in ("delimiter", "decimal", "header_row", "skip_rows")}
    if s.get("template_id"): out["template_id"] = s["template_id"]
    if s.get("style"): out["style"] = M.strip_limits(s["style"])
    if s.get("target"): out["target"] = {"scope": s["target"].get("scope")}
    if s.get("workflow"): out["workflow"] = copy.deepcopy(s["workflow"])
    return out, review


def _shared_ref(ref, heads, over):
    i = ref.get("i") if isinstance(ref, dict) else None
    role = ref.get("role") if isinstance(ref, dict) else None
    if not role or role == "unknown":
        role = over.get(i) or sg.classify_header(heads[i] if isinstance(i, int) and 0 <= i < len(heads) else (ref.get("h", "") if isinstance(ref, dict) else ""))
    out = {"role": role}
    if isinstance(i, int): out["i"] = i
    return out


def shareable(memory, role_overrides=None):
    """The projection of a memory (a dict as LearningService.memory_detail() returns it) that may be shared.

    Returns {'ok': bool, 'needs_review': bool, 'reasons': [plain words], 'payload': dict or None}.
      ok            the payload may be offered to the user for preview and consent
      needs_review  a used column has a header that is not a recognised structural role: the contribution is WITHHELD
                    until the user names the role (role_overrides={position: role}); nothing is guessed
      payload       the exact record that would be sent: schema, kind, data_family, signature ('p2:' - computed from
                    this projection), signature_version, schema_version, revision, app_version, structure, recipe,
                    template_id/version, validation flags. It contains no header text, id, path, name, note or limit.
    A payload is refused when it trips outbound_policy.has_secret() or does not pass models.validate_recipe()."""
    m = memory or {}; reasons = []; kind = m.get("kind")
    over = {int(k): str(v) for k, v in (role_overrides or {}).items() if str(v) in sg.KNOWN_ROLES and str(v) != "unknown"}
    def no(text): return {"ok": False, "needs_review": False, "reasons": reasons + [text], "payload": None}
    if kind not in M.KINDS: return no("unknown kind of memory")
    if kind in M.LEGACY_KINDS: return no("entries imported from earlier versions are not shared")
    if m.get("visibility", "personal") != "personal": return no("a record received from others is not shared again")
    if m.get("origin") != "user": return no("only knowledge you confirmed yourself can be shared")
    val = m.get("validation") or {}
    if not val.get("user_confirmed") or not val.get("structural_checks_passed"): return no("the memory is not validated and confirmed")
    recipe = copy.deepcopy(m.get("recipe") or {}); ctx = m.get("context") or {}; heads = list(ctx.get("headers") or [])
    if kind == "graph_style":
        if (recipe.get("target") or {}).get("scope") != "family": return no("a style saved for one graph or panel belongs to that graph; save it for the data family to share it")
        if M.has_limits(recipe.get("style") or {}): reasons.append("numerical axis limits were left out")
        recipe["style"] = M.strip_limits(recipe.get("style") or {}); recipe.pop("include_limits", None); recipe["target"] = {"scope": "family"}
    roles = None
    if kind == "import_mapping":
        roles = recipe.get("roles") or {}
        recipe["roles"] = {k: ([_shared_ref(r, heads, over) for r in v] if isinstance(v, list) else _shared_ref(v, heads, over)) for k, v in roles.items()}
        recipe["units"] = [(u if sg.unit_known(u) else ("other" if u else "")) for u in (recipe.get("units") or [])]
        if "read" in recipe: recipe["read"] = {k: v for k, v in recipe["read"].items() if k in ("delimiter", "decimal", "header_row", "skip_rows", "container")}
    elif kind == "unit_mapping":
        recipe["units"] = [{"col": _shared_ref(e.get("col") or {}, heads, over), "unit": e.get("unit") if sg.unit_known(e.get("unit")) else "other"} for e in (recipe.get("units") or [])]
        roles = {"y": [e.get("col") or {} for e in ((m.get("recipe") or {}).get("units") or [])]}
    elif kind == "classification":
        if recipe.get("instrument") not in M.KNOWN_INSTRUMENTS: recipe.pop("instrument", None)
    structure, review = shareable_context(ctx, roles, over)
    if review: reasons.append("a column this recipe uses has a header that is not a recognised role; name its role before sharing")
    try: recipe = M.validate_recipe(kind, recipe)
    except M.RecipeError as e: return no(f"the recipe does not pass validation ({e.code})")
    sig = sg.shareable_signature(structure["container"], structure["delimiter"], structure["decimal"], structure["header"],
                                 [c["role"].split(":", 1)[1] for c in structure["columns"]], [c["unit"] for c in structure["columns"]]) \
        if kind in ("import_mapping", "classification", "unit_mapping") or (m.get("scope") == "personal_format") else ""
    payload = {"schema": M.CONTRIBUTION_SCHEMA, "kind": kind, "data_family": M.family_token(m.get("data_family")), "signature": sig,
               "signature_version": sg.SIGNATURE_VERSION, "schema_version": M.SCHEMA_VERSION, "revision": int(m.get("revision") or 1),
               "app_version": _version(m.get("app_version")),
               "structure": structure if sig else None, "recipe": recipe,
               "template_id": m.get("template_id") or "", "template_version": m.get("template_version") or "",
               "validation": {"structural_checks_passed": bool(val.get("structural_checks_passed")), "preview_rendered": bool(val.get("preview_rendered")),
                              "user_confirmed": bool(val.get("user_confirmed"))}}
    if len(M.canonical_json(payload).encode("utf-8")) > MAX_SHARE_BYTES or _longest_list(payload) > MAX_SHARE_ITEMS:
        return no(f"the record is too large to share (more than {MAX_SHARE_ITEMS} columns or {MAX_SHARE_BYTES // 1024} kB)")
    found = scan_private(payload)
    if "credential" in found: return no("the record contains something that looks like a credential")
    if "path" in found: return no("the record contains something that looks like a folder path")
    return {"ok": not review, "needs_review": review, "reasons": reasons, "payload": payload}


def shared_signature_of(context_stored):
    """The 'p2:' signature of a stored context (what a downloaded record of the same structure carries)."""
    c = context_stored or {}
    heads = list(c.get("headers") or []); n = int(c.get("column_count") or len(heads))
    return sg.shareable_signature(c.get("container"), c.get("delimiter"), c.get("decimal"), int(c.get("header_row") or 0) >= 0 and any(heads),
                                  heads if heads else [""] * n, c.get("units") or [])


# ------------------------------------------------------------------------------------------------ diagnostics text
ERROR_CLASSES = ("parser_error", "encoding_error", "delimiter_error", "missing_columns", "no_numeric_data", "unit_conflict", "template_unfit",
                 "missing_prerequisite", "io_error", "timeout", "origin_error", "out_of_memory", "unknown")
_ERR_WORDS = (("encoding_error", r"unicode|codec|encoding|decode"), ("delimiter_error", r"delimiter|separator|tokeniz"),
              ("missing_columns", r"column|header|keyerror|no such role|missing role"), ("no_numeric_data", r"numeric|not a number|could not convert|nan|empty"),
              ("unit_conflict", r"unit"), ("template_unfit", r"unfit|template|needdata|cannot be drawn"), ("missing_prerequisite", r"requires|prerequisite|wavelength|not installed"),
              ("timeout", r"timeout|timed out"), ("origin_error", r"origin|labtalk|com error"), ("out_of_memory", r"memoryerror|out of memory"),
              ("io_error", r"permission|file|ioerror|oserror|not found|access"), ("parser_error", r"pars|syntax|format|read"))


def classify_error(error):
    """One word from ERROR_CLASSES for an exception or an error text. The text itself is never kept: an error message
    can contain a path, a sample name or a header."""
    t = (type(error).__name__ + " " + str(error)) if isinstance(error, BaseException) else str(error or "")
    t = t.lower()
    for word, rx in _ERR_WORDS:
        if re.search(rx, t): return word
    return "unknown"


def safe_error_class(value):
    """What may be stored as the class of a failure: a word of ERROR_CLASSES, or the bare class name of an exception
    ('ValueError', 'NeedData'). Free text is reduced to a word of ERROR_CLASSES."""
    if isinstance(value, BaseException): name = type(value).__name__
    else: name = str(value or "").strip()
    if name in ERROR_CLASSES: return name
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,48}(Error|Exception|Warning)$", name) or name in ("NeedData", "Unfit", "Blocked", "Timeout", "KeyboardInterrupt"):
        if not _has_secret(name): return name
    return classify_error(value)


def _strings(obj):
    if isinstance(obj, str): yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k); yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj: yield from _strings(v)


def scan_private(obj):
    """Problems found in a JSON value that is about to be written to an export or sent: 'credential', 'path'. [] = clean.
    Every string (keys too) is looked at on its own."""
    out = []
    for t in _strings(obj):
        if "credential" not in out and _has_secret(t): out.append("credential")
        if "path" not in out and _strip_paths(t) != t: out.append("path")
    return out

"""models.py - the typed, validated shapes of the learning system: vocabularies, the Context of an operation, the
results the service returns, and the versioned schema every reusable recipe must pass.

Everything here is declarative. A recipe is CONFIGURATION (which column is x, which unit, which template, which line
style, which supported workbook step) - never code. validate_recipe() rejects unknown keys, values outside their range,
oversized documents, and any text that looks like Python, SQL, a shell command, LabTalk or an instruction to an AI.

Standard library only; importable without Qt, pandas or Origin.
"""
import copy, hashlib, json, math, re, time, uuid
from dataclasses import dataclass, field, asdict

from . import signatures as sg

SCHEMA_VERSION = 1                     # of memories / recipes / exports
EXPORT_SCHEMA = "opstudio.learning/1"
CONTRIBUTION_SCHEMA = "opstudio.contribution/1"
EVIDENCE_SCHEMA = "opstudio.evidence/1"

# ------------------------------------------------------------------------------------------------ vocabularies
ORIGINS = ("user", "system", "memory", "migration")          # who caused an action; only 'user' can confirm a correction

EVENT_TYPES = ("classification_corrected", "column_mapping_corrected", "unit_mapping_confirmed", "template_preference_saved",
               "graph_style_saved", "workflow_saved", "suggestion_accepted", "suggestion_rejected", "memory_disabled", "memory_enabled",
               "memory_edited", "memory_forgotten", "import_failed", "analysis_failed", "legacy_imported")
FAILURE_EVENTS = ("import_failed", "analysis_failed")

KINDS = ("import_mapping", "classification", "unit_mapping", "template_preference", "graph_style", "workflow", "legacy_lesson", "legacy_format")
LEGACY_KINDS = ("legacy_lesson", "legacy_format")
EVENT_KIND = {"classification_corrected": "classification", "column_mapping_corrected": "import_mapping", "unit_mapping_confirmed": "unit_mapping",
              "template_preference_saved": "template_preference", "graph_style_saved": "graph_style", "workflow_saved": "workflow"}
EVENT_GROUP = {"classification_corrected": "mapping", "column_mapping_corrected": "mapping", "unit_mapping_confirmed": "mapping",
               "template_preference_saved": "template", "graph_style_saved": "style", "workflow_saved": "workflow"}


class Outcome:
    """The explicit outcome strings every service call returns. Compare with these, never with message texts."""
    SAVED = "saved"                                    # committed (only ever reported after the commit succeeded)
    ALREADY_SAVED = "already_saved"                    # the same operation was recorded before: nothing was added
    VALIDATION_FAILED = "validation_failed"            # the technical checks did not pass (or validate() was not called)
    STALE = "stale_candidate"                          # the file, sheet, source revision or mapping changed; or unknown/superseded
    NOT_REMEMBERED = "applied_without_remembering"     # confirmed with Remember off (or there was nothing to learn)
    STORAGE_UNAVAILABLE = "storage_unavailable"        # the database could not be written: the user's work is NOT affected
    DISABLED = "disabled"                              # the relevant preference (or the memory itself) is switched off
    NOT_FOUND = "not_found"
    NOT_PERMITTED = "not_permitted"                    # e.g. origin is not 'user', consent missing, a shared record


OUTCOMES = (Outcome.SAVED, Outcome.ALREADY_SAVED, Outcome.VALIDATION_FAILED, Outcome.STALE, Outcome.NOT_REMEMBERED,
            Outcome.STORAGE_UNAVAILABLE, Outcome.DISABLED, Outcome.NOT_FOUND, Outcome.NOT_PERMITTED)

SCOPES = ("personal_format", "personal_instrument", "personal_family", "personal_project")     # where a personal memory applies
SCOPE_ALIASES = {"personal": "personal_format", "format": "personal_format", "this_export_format": "personal_format",
                 "instrument": "personal_instrument", "family": "personal_family", "data_family": "personal_family", "project": "personal_project"}
VISIBILITIES = ("personal", "lab", "community")
SHARE_SCOPES = ("lab", "community")
STATUSES = ("personal", "pending", "approved", "rejected", "revoked")
TARGET_SCOPES = ("graph", "panel", "family")                 # what a saved style is declared for
FEEDBACK_OUTCOMES = ("accepted", "rejected")
FEEDBACK_REASONS = ("", "wrong_columns", "wrong_type", "wrong_units", "wrong_template", "not_wanted", "other")
GRADES = ("exact", "compatible", "weak")                     # a match GRADE. It is not a probability and not a confidence.

# The data families of the installed detection (opstudio.detection.KINDS), as storage words. tests check they stay in step.
FAMILY_KINDS = {
    "unknown": "Unknown", "xrd": "XRD", "ftir": "FTIR", "raman": "Raman", "nmr": "NMR", "tga": "TGA", "dsc": "DSC", "calorimetry": "Calorimetry",
    "particle_size": "Particle size", "porosity_and_surface": "Porosity and surface", "thermodynamic_modelling": "Thermodynamic modelling",
    "composition": "Composition", "microstructure_and_sem_eds": "Microstructure and SEM-EDS", "cement_and_concrete": "Cement and concrete",
    "strength": "Strength", "rheology": "Rheology", "electrochemistry": "Electrochemistry", "sustainability_and_co2": "Sustainability and CO2",
    "analytical_chemistry": "Analytical chemistry", "physics_and_signal": "Physics and signal", "life_science": "Life science",
    "environment_and_geoscience": "Environment and geoscience", "flow_network": "Flow network", "category_table": "Category table", "general_xy": "General XY"}
FAMILIES = tuple(FAMILY_KINDS)

CONTAINERS = ("csv", "tsv", "txt", "dat", "xy", "xye", "asc", "xlsx", "xlsm", "xls", "ods", "json", "xrdml", "jdx", "spa", "other")
DELIMITERS = ("", ",", ";", "\t", " ", "|")
_DELIMITER_NAMES = {"comma": ",", "semicolon": ";", "tab": "\t", "space": " ", "pipe": "|", "auto": "", "none": "", "whitespace": " "}
DECIMALS = (".", ",")
# Descriptors of an export FORMAT that may be shared. Anything else stays a local word (and is left out of shared records).
KNOWN_INSTRUMENTS = ("generic", "xy", "xye", "xrdml", "brml", "raw", "ras", "udf", "cif", "spa", "jdx", "dpt", "csv_export", "txt_export", "xlsx_export")

MAX_RECIPE_BYTES = 16384
MAX_DEPTH = 8
MAX_COLUMNS = sg.MAX_COLUMNS

# Hard prerequisites of a data family: which structural roles / unit dimensions an X or a Y column may have. These are
# TECHNICAL exclusions ("a temperature column is not a diffraction angle"), not proof that a classification is right.
FAMILY_RULES = {
    "xrd": {"x": ({"two_theta", "theta", "d_spacing", "q"}, {"angle", "length", "inverse_length"}),
            "y": ({"intensity", "calculated", "difference", "background"}, {"count", "count_rate", "arbitrary", "fraction"})},
    "tga": {"x": ({"temperature", "time"}, {"temperature", "time"}), "y": ({"mass", "dtg"}, {"mass", "fraction", "fraction_rate_T", "fraction_rate_t", "mass_rate"})},
    "dsc": {"x": ({"temperature", "time"}, {"temperature", "time"}), "y": ({"heat_flow", "heat"}, {"power", "specific_power", "voltage", "specific_voltage"})},
    "calorimetry": {"x": ({"time"}, {"time"}), "y": ({"heat_flow", "heat"}, {"power", "specific_power", "energy", "specific_energy"})},
    "ftir": {"x": ({"wavenumber"}, {"inverse_length", "length"}), "y": ({"absorbance", "transmittance", "intensity"}, {"arbitrary", "fraction"})},
    "raman": {"x": ({"raman_shift", "wavenumber"}, {"inverse_length"}), "y": ({"intensity"}, {"count", "count_rate", "arbitrary"})},
    "particle_size": {"x": ({"particle_size"}, {"length"}), "y": ({"volume_fraction", "cumulative"}, {"fraction"})},
}


def family_token(kind):
    """The storage word of a data family: 'XRD' -> 'xrd', 'Particle size' -> 'particle_size'. Unknown names -> 'unknown'."""
    t = re.sub(r"[^a-z0-9]+", "_", str(kind or "").strip().lower()).strip("_")
    return t if t in FAMILY_KINDS else "unknown"


def family_kind(token):
    """The detection name of a storage word: 'xrd' -> 'XRD' (what opstudio.detection.detect(..., override=) takes)."""
    return FAMILY_KINDS.get(str(token or ""), "Unknown")


def normalise_scope(scope):
    s = str(scope or "personal_format").strip().lower()
    s = SCOPE_ALIASES.get(s, s)
    return s if s in SCOPES else None


def new_id(): return str(uuid.uuid4())


def is_uuid(value):
    try: return str(uuid.UUID(str(value))) == str(value).lower()
    except Exception: return False


def now_iso(clock=None):
    """UTC time as text, from clock() (seconds since 1970) or the system clock."""
    t = float(clock()) if clock else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + "Z"


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(obj, n=32):
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()[:n]


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,79}$")


def opaque_id(value):
    """A stable internal id as it may be kept: an id that already is a plain word (letters, digits, _ . : -) stays;
    anything else (a path, a file name, a label with spaces) is replaced by a digest, so no such text reaches storage.
    Callers should pass real internal ids; this is the safety net, not the design."""
    v = str(value or "").strip()
    if not v: return ""
    if _SAFE_ID.match(v) and not re.search(r"\.[A-Za-z0-9]{1,5}$", v): return v          # 'scan_01.csv' looks like a file name: digest it
    return "h:" + hashlib.sha256(v.encode("utf-8", "replace")).hexdigest()[:24]


# ------------------------------------------------------------------------------------------------ context
@dataclass(frozen=True)
class Context:
    """The allowlisted description of what an operation works on. Build it with Context.build(raw) - never by hand.

    Structure (persisted with an event / a memory):
        container, delimiter, decimal, encoding, header_row (-1 = no header row), column_count,
        headers (normalised words), units (canonical, '' = not declared), data_family, instrument,
        template_id, template_version, signature + signature_version, share_signature
    Identity of the operation (used for stale-preview checks; kept only as opaque ids, never as paths or names):
        project_id, file_id, sheet_id, dataset_id, graph_id, panel_id, panel_index, source_revision
    Evidence for validation (NEVER persisted):
        numeric_ok   per column: True = usable numeric values exist, False = none, None = not checked
        legacy_signature   smart_plots.layout_signature(path) when the caller has it (to match migrated formats)
    """
    container: str = "other"
    delimiter: str = ""
    decimal: str = "."
    encoding: str = ""
    header_row: int = 0
    column_count: int = 0
    headers: tuple = ()
    units: tuple = ()
    numeric_ok: tuple = ()
    data_family: str = "unknown"
    instrument: str = ""
    template_id: str = ""
    template_version: str = ""
    project_id: str = ""
    file_id: str = ""
    sheet_id: str = ""
    dataset_id: str = ""
    graph_id: str = ""
    panel_id: str = ""
    panel_index: int = -1
    source_revision: str = ""
    legacy_signature: str = ""
    signature: str = ""
    signature_version: int = sg.SIGNATURE_VERSION
    share_signature: str = ""

    # the only keys build() reads; everything else in a raw dict (path, file name, sample, title, rows ...) is ignored
    ALLOWED = ("container", "delimiter", "decimal", "encoding", "header_row", "column_count", "headers", "units", "numeric_ok", "data_family",
               "instrument", "template_id", "template_version", "project_id", "file_id", "sheet_id", "dataset_id", "graph_id", "panel_id",
               "panel_index", "source_revision", "legacy_signature")

    @classmethod
    def build(cls, raw=None, **more):
        """Context from a plain dict (or keyword arguments): every field is read from the allowlist, normalised and
        bounded; unknown keys are dropped. `headers` are the column headers as the file shows them (a unit in a bracket
        becomes the unit of that column); `units` may declare units explicitly and wins over the header where given."""
        if isinstance(raw, Context) and not more: return raw
        d = dict(raw.stored()) if isinstance(raw, Context) else dict(raw or {})
        if isinstance(raw, Context):
            for k in ("project_id", "file_id", "sheet_id", "dataset_id", "graph_id", "panel_id", "panel_index", "source_revision", "legacy_signature", "numeric_ok"): d[k] = getattr(raw, k)
        d.update(more)
        container = str(d.get("container") or "other").strip().lower().lstrip(".")
        if container not in CONTAINERS: container = "other"
        delim = d.get("delimiter"); delim = "" if delim is None else str(delim)
        delim = _DELIMITER_NAMES.get(delim.strip().lower(), delim) if delim.strip() else ("\t" if "\t" in delim else (" " if delim else ""))
        if delim not in DELIMITERS: delim = ""
        decimal = str(d.get("decimal") or ".").strip(); decimal = decimal if decimal in DECIMALS else "."
        enc = str(d.get("encoding") or "").strip().lower(); enc = enc if re.match(r"^[a-z0-9_\-]{1,24}$", enc) else ""
        header_row = _int(d.get("header_row"), 0, -1, 100000)
        raw_headers = list(d.get("headers") or [])[:MAX_COLUMNS]
        heads, units = [], []
        for h in raw_headers:
            t, u = sg.split_header(h); heads.append(t); units.append(u)
        declared = d.get("units")
        if isinstance(declared, (list, tuple)):
            for i, u in enumerate(list(declared)[:MAX_COLUMNS]):
                u = sg.norm_unit(u)
                if i < len(units):
                    if u: units[i] = u
                else: units.append(u)
        n = _int(d.get("column_count"), len(heads), 0, MAX_COLUMNS)
        if heads: n = len(heads)
        units = (units + [""] * n)[:max(n, len(heads))]
        nok = d.get("numeric_ok"); numeric = []
        if isinstance(nok, (list, tuple)):
            numeric = [(bool(v) if isinstance(v, (bool, int)) and v is not None else None) for v in list(nok)[:MAX_COLUMNS]]
        numeric = (numeric + [None] * n)[:n]
        inst = re.sub(r"\s+", "_", str(d.get("instrument") or "").strip().lower()); inst = inst if re.match(r"^[a-z0-9][a-z0-9_.\-]{0,39}$", inst) else ""
        tid = str(d.get("template_id") or "").strip(); tid = tid if re.match(r"^[a-z0-9_]{1,64}$", tid) else ""
        tver = str(d.get("template_version") or "").strip(); tver = tver if re.match(r"^[A-Za-z0-9_.\-]{1,32}$", tver) else ""
        legacy = str(d.get("legacy_signature") or "")[:1200]
        has_header = header_row >= 0 and any(heads)
        sig = sg.structural_signature(container, delim, decimal, has_header, heads if heads else [""] * n, units, inst)
        share = sg.shareable_signature(container, delim, decimal, has_header, heads if heads else [""] * n, units)
        return cls(container=container, delimiter=delim, decimal=decimal, encoding=enc, header_row=header_row, column_count=n, headers=tuple(heads),
                   units=tuple(units), numeric_ok=tuple(numeric), data_family=family_token(d.get("data_family")), instrument=inst,
                   template_id=tid, template_version=tver, project_id=opaque_id(d.get("project_id")), file_id=opaque_id(d.get("file_id")),
                   sheet_id=opaque_id(d.get("sheet_id")), dataset_id=opaque_id(d.get("dataset_id")), graph_id=opaque_id(d.get("graph_id")),
                   panel_id=opaque_id(d.get("panel_id")), panel_index=_int(d.get("panel_index"), -1, -1, 63),
                   source_revision=opaque_id(d.get("source_revision")), legacy_signature=legacy, signature=sig,
                   signature_version=sg.SIGNATURE_VERSION, share_signature=share)

    @property
    def has_header(self): return self.header_row >= 0 and any(self.headers)

    def stored(self):
        """The part that may be persisted with an event or a memory (structure only: no ids, no numeric evidence)."""
        return {"container": self.container, "delimiter": self.delimiter, "decimal": self.decimal, "encoding": self.encoding,
                "header_row": self.header_row, "column_count": self.column_count, "headers": list(self.headers), "units": list(self.units),
                "data_family": self.data_family, "instrument": self.instrument, "template_id": self.template_id,
                "template_version": self.template_version, "signature": self.signature, "signature_version": self.signature_version,
                "share_signature": self.share_signature}

    def fingerprint(self):
        """What 'the same displayed thing' means: the ids of project, file, sheet, dataset, graph and panel, the source
        revision and the structure. A confirmation token is bound to it; any change makes the token stale."""
        return digest([self.project_id, self.file_id, self.sheet_id, self.dataset_id, self.graph_id, self.panel_id, self.source_revision, self.signature])

    def target_id(self, group="mapping"):
        """The stable id of what an event of this group is about (the dataset for a mapping, the graph/panel for a style)."""
        if group == "style": parts = (self.graph_id, self.panel_id)
        elif group == "mapping": parts = (self.file_id, self.sheet_id, self.dataset_id)
        else: parts = (self.file_id, self.sheet_id, self.dataset_id, self.graph_id)
        key = "/".join(p for p in parts if p) or self.signature
        return (group + ":" + key)[:200]


def _int(v, default, lo, hi):
    try:
        if isinstance(v, bool) or v is None: return default
        i = int(v)
        return i if lo <= i <= hi else default
    except Exception: return default


# ------------------------------------------------------------------------------------------------ results
def _copy(v): return copy.deepcopy(v)


@dataclass(frozen=True)
class Candidate:
    """A staged change (process memory only). learnable=False means confirm() will refuse to learn from it; reason says
    why: 'origin_not_user', 'no_change', 'nothing_allowed' (nothing of the change is an allowlisted field)."""
    id: str
    operation_id: str
    origin: str
    event_type: str
    kind: str
    target_id: str
    learnable: bool
    reason: str = ""
    changes: dict = field(default_factory=dict)          # field -> {"before": ..., "after": ...}
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    fingerprint: str = ""

    def to_dict(self): return _copy(asdict(self))


@dataclass(frozen=True)
class ValidationResult:
    """ok = every technical check passed AND the candidate still refers to what is displayed. token is the confirmation
    token to hand to confirm() ('' unless ok). Technical checks are not scientific proof: checks['user_confirmed'] is
    always False here and only becomes True in the stored record once the user confirms."""
    ok: bool
    stale: bool = False
    token: str = ""
    checks: dict = field(default_factory=dict)
    problems: tuple = ()                                  # stable words, e.g. 'x_column_missing', 'units_conflict'
    messages: tuple = ()                                  # the same in plain words

    def to_dict(self): return _copy(asdict(self))


@dataclass(frozen=True)
class RecordResult:
    """The result of confirm() and of the save_* wrappers.
    applied = the caller may treat the user's change as confirmed and keep it applied (True also when it could not be
    remembered). saved is True only for outcome 'saved' / 'already_saved'."""
    outcome: str
    applied: bool = False
    message: str = ""
    memory_id: str = ""
    revision: int = 0
    event_id: str = ""
    candidate_id: str = ""
    effect: str = ""                                      # 'created' | 'revised' | 'confirmed' | ''  (what happened to the memory)
    problems: tuple = ()

    @property
    def saved(self): return self.outcome in (Outcome.SAVED, Outcome.ALREADY_SAVED)

    def to_dict(self): return _copy(asdict(self))


@dataclass(frozen=True)
class ActionResult:
    """The result of the management calls (feedback, disable, enable, edit, forget, undo, export, import, settings)."""
    outcome: str
    message: str = ""
    memory_id: str = ""
    revision: int = 0
    detail: dict = field(default_factory=dict)

    @property
    def ok(self): return self.outcome in (Outcome.SAVED, Outcome.ALREADY_SAVED)

    def to_dict(self): return _copy(asdict(self))


@dataclass(frozen=True)
class Suggestion:
    """A saved memory that fits the current context.

    grade        'exact' | 'compatible' | 'weak' - a match GRADE (which structural test passed). NOT a probability.
    weak         True for grade 'weak': show it, never apply it without the user.
    conflict     True when another equally valid suggestion says something different: show both, pick neither.
    auto_apply_ok  True only for an exact, validated, personal, user-confirmed, unconflicted match AND the auto-apply
                 preference on. Even then apply_suggestion() revalidates the current file.
    explanation  why it matches, in plain words.
    recipe       a copy of the declarative recipe; resolved = its column roles as indices of the CURRENT context.
    """
    id: str
    memory_id: str
    revision: int
    kind: str
    grade: str
    explanation: str
    weak: bool = False
    conflict: bool = False
    conflicts_with: tuple = ()
    auto_apply_ok: bool = False
    data_family: str = ""
    scope: str = ""
    visibility: str = "personal"
    origin: str = "user"
    template_id: str = ""
    needs_revalidation: bool = False
    user_confirmed: bool = False
    recipe: dict = field(default_factory=dict)
    resolved: dict = field(default_factory=dict)
    notes: tuple = ()

    def to_dict(self): return _copy(asdict(self))


@dataclass(frozen=True)
class ApplyResult:
    """apply_suggestion(): applied=True means the recipe passed revalidation against the current context and the caller
    may now use `recipe` / `resolved`. The service never touches the user's data itself."""
    outcome: str
    applied: bool = False
    message: str = ""
    memory_id: str = ""
    revision: int = 0
    kind: str = ""
    recipe: dict = field(default_factory=dict)
    resolved: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)
    problems: tuple = ()

    def to_dict(self): return _copy(asdict(self))


# ------------------------------------------------------------------------------------------------ inert text
class RecipeError(ValueError):
    """A recipe (or a part of one) is not acceptable. code is a stable word; path says where."""
    def __init__(self, code, path="", detail=""):
        super().__init__(f"{code} at {path or 'recipe'}" + (f": {detail}" if detail else "")); self.code = code; self.path = path


_CODE_RE = re.compile(
    r"(?is)("
    r"\b(select|insert|update|delete|drop|alter|create|truncate|union)\b\s[^;]*\b(from|into|table|set|select|database|where)\b"   # SQL
    r"|;\s*--|/\*|\bor\s+1\s*=\s*1\b"
    r"|\b(rm|del|curl|wget|powershell|cmd|bash|sudo|chmod|chown|mkfs|shutdown|reg|schtasks|certutil)(\.exe)?\s+[-/\w]"             # shell
    r"|\$\(|\$\{|`|&&|\|\||\|\s*(sh|bash|cmd|powershell|python)\b|>\s*/"
    r"|\bimport\s+(os|sys|subprocess|shutil|socket|ctypes|importlib|builtins|pickle)\b|\bfrom\s+\w+\s+import\b|__\w+__"            # Python
    r"|\b(eval|exec|compile|system|popen|getattr|setattr|globals|locals)\s*\(|\bsubprocess\b|\bos\.\w+|\blambda\s*[\w, ]*:"
    r"|<\s*script|javascript:|\bon(load|error|click)\s*="
    r"|\brun\.section\b|\b(doc|win|type|run|sec|plotxy|worksheet|wks|page|layer|system)\s*[.\-]\s*[a-z]+\s*[=(]|\b(doc|win|type|run)\s+-[a-z]"  # LabTalk
    r"|%\([^)]*\)|\bdlgfile\b"
    r"|[a-z][a-z0-9+.\-]{1,10}://|\\\\[^\\]|\.\./|\.\.\\"                                                                          # addresses, traversal
    r")")
_INJECTION_RE = re.compile(
    r"(?i)(ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)|disregard\s+(all\s+|the\s+)?(previous|above|prior|instructions)"
    r"|system\s+prompt|you\s+are\s+now|as\s+an\s+ai|new\s+instructions|override\s+(your|the|all)\s+(rules|instructions|permissions)"
    r"|developer\s+message|jailbreak|<\s*/?\s*(system|assistant|user|tool)\s*>|\bapprove\s+this\s+(contribution|recipe)\b|grant\s+(me\s+)?(access|permission))")


def looks_like_code(text):
    """True when a text looks like SQL, a shell command, Python, script markup, LabTalk, an address or a path traversal."""
    return bool(_CODE_RE.search(str(text)))


def looks_like_injection(text):
    """True when a text reads like an instruction to an AI or a reviewer ('ignore previous instructions ...')."""
    return bool(_INJECTION_RE.search(str(text)))


def _has_secret(text):
    try:
        import outbound_policy
        return outbound_policy.has_secret(text)
    except Exception:
        return bool(re.search(r"sk-[A-Za-z0-9_\-]{16,}|eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.|gh[pousr]_[A-Za-z0-9]{20,}|sb[ps]_[A-Za-z0-9_\-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY", str(text)))


def assert_inert(obj, path="recipe", *, code_check=True, depth=0):
    """Walk a JSON value: every string (keys too) must be free of credentials, instructions to an AI and - unless
    code_check is off - anything that looks like code. Raises RecipeError."""
    if depth > MAX_DEPTH: raise RecipeError("too_deep", path)
    if isinstance(obj, str):
        if len(obj) > 2000: raise RecipeError("text_too_long", path)
        if _has_secret(obj): raise RecipeError("contains_credential", path)
        if looks_like_injection(obj): raise RecipeError("instruction_like_text", path)
        if code_check and looks_like_code(obj): raise RecipeError("code_like_text", path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str): raise RecipeError("bad_key", path)
            assert_inert(k, path + "." + k[:20], code_check=code_check, depth=depth + 1); assert_inert(v, path + "." + k[:20], code_check=code_check, depth=depth + 1)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj): assert_inert(v, f"{path}[{i}]", code_check=code_check, depth=depth + 1)
    elif isinstance(obj, float):
        if not math.isfinite(obj): raise RecipeError("not_finite", path)
    elif not (obj is None or isinstance(obj, (bool, int))):
        raise RecipeError("bad_type", path, type(obj).__name__)


# ------------------------------------------------------------------------------------------------ schema machinery
# A validator is f(value, strict, path) -> cleaned value, or raises RecipeError.
# strict=True  (recipes, imports, downloads): an unknown key or a bad value is an error.
# strict=False (privacy.local_snapshot): an unknown key or a bad value is silently dropped - an allowlist projection.
def Bool():
    def f(v, strict, path):
        if isinstance(v, bool): return v
        raise RecipeError("not_a_boolean", path)
    return f


def Int(lo, hi):
    def f(v, strict, path):
        if isinstance(v, bool) or not isinstance(v, int): raise RecipeError("not_an_integer", path)
        if not lo <= v <= hi: raise RecipeError("out_of_range", path, f"{lo}..{hi}")
        return v
    return f


def Num(lo, hi):
    def f(v, strict, path):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)): raise RecipeError("not_a_number", path)
        if not lo <= float(v) <= hi: raise RecipeError("out_of_range", path, f"{lo}..{hi}")
        return v
    return f


def Enum(*values):
    allowed = set(values)
    def f(v, strict, path):
        if isinstance(v, str) and v in allowed: return v
        raise RecipeError("not_allowed", path)
    return f


def Tok(pattern, maxlen=64):
    rx = re.compile(pattern)
    def f(v, strict, path):
        if not isinstance(v, str) or len(v) > maxlen or not rx.match(v): raise RecipeError("bad_word", path)
        return v
    return f


def Arr(item, lo=0, hi=64):
    def f(v, strict, path):
        if not isinstance(v, (list, tuple)): raise RecipeError("not_a_list", path)
        if len(v) > hi: raise RecipeError("too_many_items", path, str(hi))
        out = []
        for i, x in enumerate(v):
            try: out.append(item(x, strict, f"{path}[{i}]"))
            except RecipeError:
                if strict: raise
        if len(out) < lo: raise RecipeError("too_few_items", path, str(lo))
        return out
    return f


def Obj(fields, required=(), any_of=()):
    def f(v, strict, path):
        if not isinstance(v, dict): raise RecipeError("not_an_object", path)
        out = {}
        for k, x in v.items():
            if k not in fields:
                if strict: raise RecipeError("unknown_key", f"{path}.{str(k)[:24]}")
                continue
            try: out[k] = fields[k](x, strict, f"{path}.{k}")
            except RecipeError:
                if strict: raise
        for k in required:
            if k not in out: raise RecipeError("missing_key", f"{path}.{k}")
        if any_of and not any(k in out for k in any_of): raise RecipeError("missing_key", path, "one of " + ", ".join(any_of))
        return out
    return f


_HEX = Tok(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$", 9)
_FAMILY = Enum(*FAMILIES)
_UNIT = Tok(r"^[A-Za-z0-9/%^.*_\-]{0,24}$", 24)
_TEMPLATE_ID = Tok(r"^[a-z0-9_]{1,64}$", 64)
_TEMPLATE_VERSION = Tok(r"^[A-Za-z0-9_.\-]{0,32}$", 32)
_ROLE = Enum(*sg.KNOWN_ROLES)
# A column reference: by normalised header word ('h'), by structural role ('role', shared records), with its position ('i').
# A position alone is only honoured for an exactly matching layout.
COLREF = Obj({"h": Tok(r"^[a-z0-9]{1,64}$", 64), "role": _ROLE, "i": Int(0, MAX_COLUMNS - 1)}, any_of=("h", "role", "i"))
ROLE_NAMES = ("x", "y", "yerr", "xerr", "label", "obs", "calc", "diff", "background", "group", "z")
_ROLES = Obj({"x": COLREF, "y": Arr(COLREF, 1, 64), "yerr": Arr(COLREF, 0, 64), "xerr": COLREF, "label": COLREF, "obs": COLREF, "calc": COLREF, "diff": COLREF,
              "background": COLREF, "group": COLREF, "z": COLREF})
_READ = Obj({"delimiter": Enum(*DELIMITERS), "decimal": Enum(*DECIMALS), "encoding": Tok(r"^[a-z0-9_\-]{0,24}$", 24), "header_row": Int(-1, 100000),
             "skip_rows": Int(0, 100000), "sheet_index": Int(0, 500), "container": Enum(*CONTAINERS)})

_AXIS = Obj({"log": Bool(), "reverse": Bool(), "grid": Bool(), "minor_ticks": Bool(), "ticks": Enum("in", "out", "both", "none"),
             "label_mode": Enum("auto", "name", "name_unit", "none"), "side": Enum("bottom", "top", "left", "right"),
             "min": Num(-1e12, 1e12), "max": Num(-1e12, 1e12)})                          # min / max only with include_limits
STYLE = Obj({
    "style_id": Tok(r"^[a-z0-9_]{1,64}$", 64),
    "line": Obj({"visible": Bool(), "width": Num(0, 20), "style": Enum("solid", "dash", "dot", "dashdot", "none")}),
    "marker": Obj({"visible": Bool(), "shape": Enum("circle", "square", "triangle", "diamond", "cross", "plus", "star", "none"), "size": Num(0, 40),
                   "every": Int(1, 100000), "filled": Bool()}),
    "colors": Obj({"palette": Arr(_HEX, 0, 24), "line": _HEX, "marker": _HEX, "fill": _HEX, "background": _HEX, "by": Enum("series", "panel", "single")}),
    "axis": Obj({"x": _AXIS, "y": _AXIS, "y2": _AXIS, "top_axis": Enum("none", "d-spacing", "1000/T")}),
    "legend": Obj({"visible": Bool(), "position": Enum("best", "inside_top_right", "inside_top_left", "inside_bottom_right", "inside_bottom_left", "outside_right", "below", "above"),
                   "frame": Bool(), "columns": Int(1, 8)}),
    "panels": Obj({"rows": Int(1, 12), "cols": Int(1, 12), "share_x": Bool(), "share_y": Bool(), "labels": Bool(), "arrangement": Enum("grid", "stacked", "side_by_side", "inset")}),
    # each graph component is its own switch: remembering one never implies another
    "components": Obj({"zoom": Bool(), "inset": Bool(), "markers": Bool(), "observed": Bool(), "fitted": Bool(), "difference": Bool(),
                       "background": Bool(), "bragg_ticks": Bool(), "labels": Bool(), "legend": Bool()}),
    "font": Obj({"size": Num(4, 48), "family": Enum("sans-serif", "serif", "monospace")}),
    # the variant switches of opstudio.api.SWITCHES that are presentation only ('normalise' changes the drawn numbers and
    # is deliberately NOT a style: it can only be an explicit workflow step)
    "switches": Obj({"logx": Bool(), "logy": Bool(), "revx": Bool(), "revy": Bool(), "markers": Bool(), "grid": Bool(), "legend_off": Bool(), "hatch": Bool(),
                     "top_axis": Enum("none", "d-spacing", "1000/T"), "offset": Num(0, 10),
                     "xmin": Num(-1e12, 1e12), "xmax": Num(-1e12, 1e12), "ymin": Num(-1e12, 1e12), "ymax": Num(-1e12, 1e12)}),
})
LIMIT_KEYS = ("min", "max", "xmin", "xmax", "ymin", "ymax")
TARGET = Obj({"scope": Enum(*TARGET_SCOPES), "panel_index": Int(-1, 63)}, required=("scope",))

# The closed vocabulary of workflow steps: operation -> its parameters. A step outside this table cannot be stored.
STEP_OPS = {
    "select_source": {"role": Enum("data", "reference", "background", "calibration"), "sheet_index": Int(0, 500)},
    "append_rows": {"match": Enum("headers", "position"), "require_same_units": Bool()},
    "join_columns": {"on_role": Enum("x", "label"), "require_equal_x": Bool(), "tolerance": Num(0, 1e6)},
    "arrange_sheets": {"order_by": Enum("name", "created", "source_order")},
    "select_columns": {"roles": Arr(Enum(*ROLE_NAMES), 1, 16)},
    "drop_columns": {"roles": Arr(Enum(*ROLE_NAMES), 1, 16)},
    "sort_rows": {"by_role": Enum("x", "label"), "ascending": Bool()},
    "convert_units": {"role": Enum(*ROLE_NAMES), "from": _UNIT, "to": _UNIT},
    "derivative": {"order": Int(1, 2), "window": Num(0, 1e4)},
    "normalise": {"mode": Enum("max", "area", "first_point")},
    "subtract_background": {"method": Enum("linear", "polynomial", "snip", "measured_blank"), "order": Int(0, 12)},
    "smooth": {"method": Enum("moving_average", "savitzky_golay"), "window": Int(3, 501), "order": Int(0, 6)},
    "draw_template": {"template_id": _TEMPLATE_ID},
    "export": {"format": Enum("png", "pdf", "svg", "tiff", "opju", "xlsx", "pptx", "docx")},
}
# steps that change the numbers that are analysed: always explicit, never implied by a style or a mapping
PROCESSING_OPS = ("convert_units", "derivative", "normalise", "subtract_background", "smooth")


def _step(v, strict, path):
    if not isinstance(v, dict): raise RecipeError("not_an_object", path)
    op = v.get("op")
    if not isinstance(op, str) or op not in STEP_OPS: raise RecipeError("unsupported_operation", path + ".op")
    extra = set(v) - {"op", "params"}
    if extra and strict: raise RecipeError("unknown_key", f"{path}.{sorted(map(str, extra))[0][:24]}")
    params = Obj(STEP_OPS[op])(v.get("params") or {}, strict, path + ".params")
    return {"op": op, "params": params}


_LEGACY_SCALAR = (bool, int, float, str)


def _legacy_recipe(v, strict, path):
    """A recipe of the earlier learned_formats.json, kept as it was: a flat dict of scalars, and 'columns' as a list of
    small dicts. It is never executed by this package and never shared."""
    if not isinstance(v, dict): raise RecipeError("not_an_object", path)
    if len(v) > 40: raise RecipeError("too_many_items", path)
    def scalar(x, p):
        if x is None or isinstance(x, bool) or isinstance(x, int): return x
        if isinstance(x, float):
            if not math.isfinite(x): raise RecipeError("not_finite", p)
            return x
        if isinstance(x, str):
            if len(x) > 200: raise RecipeError("text_too_long", p)
            return x
        raise RecipeError("bad_type", p)
    out = {}
    for k, x in v.items():
        if not isinstance(k, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,39}$", k):
            if strict: raise RecipeError("bad_key", path)
            continue
        if isinstance(x, (list, tuple)):
            if len(x) > 128: raise RecipeError("too_many_items", f"{path}.{k}")
            items = []
            for i, y in enumerate(x):
                if isinstance(y, dict):
                    if len(y) > 12: raise RecipeError("too_many_items", f"{path}.{k}[{i}]")
                    items.append({str(a)[:40]: scalar(b, f"{path}.{k}[{i}]") for a, b in y.items()})
                else: items.append(scalar(y, f"{path}.{k}[{i}]"))
            out[k] = items
        elif isinstance(x, dict):
            raise RecipeError("bad_type", f"{path}.{k}")
        else: out[k] = scalar(x, f"{path}.{k}")
    return out


def _lesson_text(v, strict, path):
    if not isinstance(v, str) or not v.strip() or len(v) > 300: raise RecipeError("bad_text", path)
    return re.sub(r"\s+", " ", v).strip()


def _legacy_signature(v, strict, path):
    if not isinstance(v, str) or not v or len(v) > 1200 or any(ord(c) < 32 for c in v): raise RecipeError("bad_text", path)
    return v


RECIPES = {
    "import_mapping": Obj({"data_family": _FAMILY, "roles": _ROLES, "units": Arr(_UNIT, 0, MAX_COLUMNS), "read": _READ}, required=("data_family", "roles")),
    "classification": Obj({"data_family": _FAMILY, "instrument": Tok(r"^[a-z0-9][a-z0-9_.\-]{0,39}$", 40)}, required=("data_family",)),
    "unit_mapping": Obj({"units": Arr(Obj({"col": COLREF, "unit": _UNIT}, required=("col", "unit")), 1, MAX_COLUMNS), "data_family": _FAMILY}, required=("units",)),
    "template_preference": Obj({"template_id": _TEMPLATE_ID, "template_version": _TEMPLATE_VERSION, "data_family": _FAMILY}, required=("template_id", "data_family")),
    "graph_style": Obj({"style": STYLE, "target": TARGET, "template_id": _TEMPLATE_ID, "data_family": _FAMILY, "include_limits": Bool()}, required=("style", "target")),
    "workflow": Obj({"steps": Arr(_step, 1, 32), "requires": Obj({"data_family": _FAMILY, "roles": Arr(_ROLE, 0, 16)}), "template_id": _TEMPLATE_ID,
                     "data_family": _FAMILY}, required=("steps",)),
    "legacy_lesson": Obj({"text": _lesson_text}, required=("text",)),
    "legacy_format": Obj({"legacy_signature": _legacy_signature, "recipe": _legacy_recipe}, required=("legacy_signature", "recipe")),
}


def strip_limits(style):
    """A copy of a style without numerical axis limits (one sample's range is not a preference for a data family)."""
    s = _copy(style) if isinstance(style, dict) else {}
    for ax in (s.get("axis") or {}).values():
        if isinstance(ax, dict):
            for k in LIMIT_KEYS: ax.pop(k, None)
    for k in LIMIT_KEYS: (s.get("switches") or {}).pop(k, None)
    return s


def has_limits(style):
    return _copy(style) != strip_limits(style)


def validate_recipe(kind, recipe, *, untrusted=True):
    """The cleaned recipe, or RecipeError. Checks, in this order: the kind is known; the document is a JSON object of at
    most MAX_RECIPE_BYTES and MAX_DEPTH levels; no text in it is a credential, an instruction to an AI or code-like;
    every key is known and every value is of the declared type and range; a style without include_limits carries no
    axis limits; a workflow uses only supported operations.

    untrusted=False is used ONLY for the user's own legacy files during migration: their free text ('legacy_lesson'
    text, a legacy layout signature) is kept as the user wrote it. Everything else is always checked in full."""
    if kind not in RECIPES: raise RecipeError("unknown_kind", "kind")
    if not isinstance(recipe, dict): raise RecipeError("not_an_object", "recipe")
    try: size = len(json.dumps(recipe, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as e: raise RecipeError("not_json", "recipe", type(e).__name__)
    if size > MAX_RECIPE_BYTES: raise RecipeError("too_large", "recipe", f"{size} > {MAX_RECIPE_BYTES} bytes")
    if kind == "legacy_format":
        assert_inert({k: v for k, v in recipe.items() if k != "legacy_signature"}, code_check=untrusted)
        if untrusted: assert_inert(str(recipe.get("legacy_signature", "")), "recipe.legacy_signature", code_check=False)
        elif _has_secret(str(recipe.get("legacy_signature", ""))): raise RecipeError("contains_credential", "recipe.legacy_signature")
    elif kind == "legacy_lesson" and not untrusted:
        if _has_secret(str(recipe.get("text", ""))): raise RecipeError("contains_credential", "recipe.text")
    else:
        assert_inert(recipe)
    clean = RECIPES[kind](recipe, True, "recipe")
    if kind == "graph_style":
        if not clean["style"]: raise RecipeError("empty", "recipe.style")
        if has_limits(clean["style"]) and not clean.get("include_limits"): raise RecipeError("limits_not_included", "recipe.style")
    if kind == "import_mapping":
        refs = [clean["roles"].get("x")] + list(clean["roles"].get("y") or [])
        if not clean["roles"].get("x") or not clean["roles"].get("y"): raise RecipeError("missing_key", "recipe.roles")
        keys = [canonical_json({k: r[k] for k in ("h", "role", "i") if k in r}) for r in refs if r]
        if len(set(keys)) != len(keys): raise RecipeError("roles_not_distinct", "recipe.roles")
    return clean

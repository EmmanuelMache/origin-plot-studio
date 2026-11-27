"""migrate.py - bring the knowledge of earlier versions into the learning database, once, without touching the originals.

Two legacy stores exist:

    assistant_lessons.txt    (assistant.learn)         one rule per line, 'YYYY-MM-DD: text'; lines starting with '#'
                                                       are comments
    learned_formats.json     (smart_plots.learn_format) {layout signature: {'recipe': {...}, 'learned_from': <file
                                                       name>, 'on': 'YYYY-MM-DD'}}

Both live in the app's data folder beside the phase store ($ORIGIN_PLOT_APP_HOME, else %APPDATA%/OriginPlotApp -
legacy_home()); older copies may also lie in the program folder.

What migration does:
  * every entry becomes a memory with origin 'migration' and provenance {source file, original signature, original
    date, validation 'unknown'} - it is NOT presented as validated or user-confirmed knowledge of this version
  * a legacy layout signature keeps signature_version 1; it is never relabelled as a version-2 signature
  * the name of the file a format was learned from ('learned_from') is NOT copied: a file name is not kept
  * idempotent: each imported entry leaves a marker; running again adds nothing, and an entry the user has forgotten
    here is not imported again
  * the original files are only READ. They are never changed, moved or deleted - the old code paths
    (assistant.learn, smart_plots.apply_learned) keep working from them. If anything fails, the transaction of that
    file is rolled back, the failure is reported, and the originals are as they were.
"""
import hashlib, json, os, re

from . import models as M, signatures as sg
from .service import dedup_key
from .store import StorageUnavailable

LESSONS_FILE = "assistant_lessons.txt"
FORMATS_FILE = "learned_formats.json"
MAX_FILE_BYTES = 4 * 1024 * 1024


def legacy_home():
    """The data folder of earlier versions (where assistant.home() / smart_plots._home() put the two files)."""
    v = os.environ.get("ORIGIN_PLOT_APP_HOME")
    if not v: v = os.path.join(os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config"), "OriginPlotApp")
    return v


def _key(*parts): return hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8", "replace")).hexdigest()[:32]


def read_lessons(path):
    """[(date or '', text)] of a lessons file - the same reading as assistant.learn: comment lines and empty lines
    are skipped, a leading 'YYYY-MM-DD: ' is the date."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f: text = f.read(MAX_FILE_BYTES)
    for line in text.splitlines():
        t = line.strip()
        if not t or t.startswith("#"): continue
        m = re.match(r"^(\d{4}-\d{2}-\d{2}):\s*(.*)$", t)
        date, body = (m.group(1), m.group(2)) if m else ("", t)
        body = re.sub(r"\s+", " ", body).strip().strip("-• ")[:300]
        if body: out.append((date, body))
    return out


def _lesson_memory(service, date, text):
    recipe = M.validate_recipe("legacy_lesson", {"text": text}, untrusted=False)
    return {"kind": "legacy_lesson", "signature": "", "signature_version": sg.LEGACY_SIGNATURE_VERSION, "data_family": "unknown", "scope": "personal_family",
            "origin": "migration", "recipe": recipe, "context": {}, "constraints": {},
            "validation": {"structural_checks_passed": None, "preview_rendered": None, "user_confirmed": None, "status": "unknown"},
            "provenance": {"origin": "migration", "source_file": LESSONS_FILE, "original_date": date, "validation": "unknown", "app_version": service.app_version},
            "dedup_key": dedup_key("legacy_lesson", "", "", "", "", "", recipe)}


def _format_memory(service, signature, entry):
    raw = dict(entry.get("recipe") or {}) if isinstance(entry, dict) and isinstance(entry.get("recipe"), dict) else {}
    raw.pop("sample", None); raw.pop("path", None)                           # belong to one file, not to the layout (as learn_format already says)
    recipe = M.validate_recipe("legacy_format", {"legacy_signature": str(signature), "recipe": raw}, untrusted=False)
    date = str(entry.get("on") or "") if isinstance(entry, dict) else ""
    date = date if re.match(r"^\d{4}-\d{2}-\d{2}$", date) else ""
    return {"kind": "legacy_format", "signature": str(signature), "signature_version": sg.LEGACY_SIGNATURE_VERSION, "data_family": "unknown", "scope": "personal_format",
            "origin": "migration", "recipe": recipe, "context": {}, "constraints": {"signature_version": sg.LEGACY_SIGNATURE_VERSION},
            "validation": {"structural_checks_passed": None, "preview_rendered": None, "user_confirmed": None, "status": "unknown"},
            "provenance": {"origin": "migration", "source_file": FORMATS_FILE, "original_signature": str(signature), "original_signature_version": sg.LEGACY_SIGNATURE_VERSION,
                           "original_date": date, "had_source_file_name": bool(isinstance(entry, dict) and entry.get("learned_from")), "validation": "unknown",
                           "app_version": service.app_version},
            "dedup_key": dedup_key("legacy_format", "", "", str(signature), "", "", recipe)}


def migrate_legacy(service, app_dir, private_dir=None, *, extra_dirs=(), include_home=True):
    """Import assistant_lessons.txt and learned_formats.json from app_dir, private_dir, extra_dirs and (include_home)
    the legacy data folder. Returns
        {'lessons_imported', 'formats_imported', 'skipped_existing', 'rejected', 'errors': [...], 'sources': [...],
         'originals_untouched': True}
    'errors' are short words with the file's base name (never a path or content); 'sources' are base names of the files
    that were read. Safe to call at every start: a second run imports nothing."""
    out = {"lessons_imported": 0, "formats_imported": 0, "skipped_existing": 0, "rejected": 0, "errors": [], "sources": [], "originals_untouched": True}
    dirs = []
    for d in [app_dir, private_dir, *list(extra_dirs or ()), legacy_home() if include_home else None]:
        if d and os.path.isdir(d):
            r = os.path.realpath(d)
            if r not in dirs: dirs.append(r)
    for d in dirs:
        p = os.path.join(d, LESSONS_FILE)
        if os.path.isfile(p):
            try:
                entries = []
                for date, text in read_lessons(p):
                    try: entries.append((_key("lesson", text.lower()), _lesson_memory(service, date, text)))
                    except M.RecipeError: out["rejected"] += 1
                done, skipped = service.store.import_legacy("assistant_lessons", entries)
                out["lessons_imported"] += done; out["skipped_existing"] += skipped; out["sources"].append(LESSONS_FILE)
            except StorageUnavailable: out["errors"].append(f"{LESSONS_FILE}: storage_unavailable")
            except (OSError, ValueError) as e: out["errors"].append(f"{LESSONS_FILE}: {type(e).__name__}")
        p = os.path.join(d, FORMATS_FILE)
        if os.path.isfile(p):
            try:
                if os.path.getsize(p) > MAX_FILE_BYTES: raise ValueError("too large")
                with open(p, encoding="utf-8") as f: data = json.load(f)
                if not isinstance(data, dict): raise ValueError("not a table of formats")
                entries = []
                for sig, entry in data.items():
                    try:
                        mem = _format_memory(service, sig, entry)
                        entries.append((_key("format", sig, M.canonical_json(mem["recipe"]["recipe"])), mem))
                    except M.RecipeError: out["rejected"] += 1
                done, skipped = service.store.import_legacy("learned_formats", entries)
                out["formats_imported"] += done; out["skipped_existing"] += skipped; out["sources"].append(FORMATS_FILE)
            except StorageUnavailable: out["errors"].append(f"{FORMATS_FILE}: storage_unavailable")
            except (OSError, ValueError) as e: out["errors"].append(f"{FORMATS_FILE}: {type(e).__name__}")
    return out

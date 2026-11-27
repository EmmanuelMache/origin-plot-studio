"""opstudio.learning - the app remembers what the user CONFIRMED, on this computer, and offers it again where it fits.

    from opstudio.learning import LearningService, Context, Outcome
    svc = LearningService()                                    # <private folder>/learning/learning.sqlite3
    op = svc.new_operation_id()
    cand = svc.stage_change(context, before, after, origin="user", operation_id=op)
    check = svc.validate(cand, context, rendered=True)         # after the preview of the change finished
    result = svc.confirm(cand.id, remember=True, scope="personal_format", confirmation_token=check.token)
    ...
    for s in svc.find_suggestions(context_of_the_next_file): ...
    applied = svc.apply_suggestion(s.id, context_of_the_next_file, operation_id=svc.new_operation_id())

Modules: models (vocabularies, Context, results, recipe schema), privacy (allowlisted snapshots, shareable projection),
signatures (versioned structural signatures), store (SQLite), service (LearningService), matcher (explainable
matching, template ranking), migrate (legacy lessons / learned formats), sync (adapter protocol, contribution flow,
background worker, in-memory test doubles), supabase_adapter (REST adapter - not validated against a live service),
evidence (sanitised evidence export).

REAL: the local SQLite learning (everything in service / store / matcher / privacy / migrate / evidence).
MOCK: sync.FakeServer and sync.FakeAdapter (tests only). NOT YET VALIDATED LIVE: supabase_adapter.

The package lives under opstudio/ because the installed updater copies that folder; the database, tokens and memories
live in the user's private folder and are never part of the program or a release.
No Qt, no Origin, no network at import; no embeddings anywhere.
"""
from . import models, privacy, signatures, store, matcher                                    # noqa: F401
from .models import (Context, Candidate, ValidationResult, RecordResult, ActionResult, Suggestion, ApplyResult, Outcome, OUTCOMES, ORIGINS, EVENT_TYPES,    # noqa: F401
                     KINDS, SCOPES, VISIBILITIES, TARGET_SCOPES, FAMILIES, GRADES, RecipeError, validate_recipe, family_token, family_kind, SCHEMA_VERSION)
from .signatures import SIGNATURE_VERSION, LEGACY_SIGNATURE_VERSION                         # noqa: F401
from .store import StorageUnavailable, default_dir, default_path                            # noqa: F401
from .service import LearningService, SETTING_DEFAULTS                                      # noqa: F401
from .migrate import migrate_legacy                                                         # noqa: F401

_default = None


def default_service():
    """The one LearningService of the running app (created on first use, at the default database path)."""
    global _default
    if _default is None: _default = LearningService()
    return _default


# The app calls learning.service(). (The name also is that of the submodule service.py; `from opstudio.learning.service
# import LearningService` keeps working - only the attribute `learning.service` is this function.)
service = default_service


def context_from_table(table, **fields):
    """A Context for an opstudio.data.Table: headers, the units their headers declare and - per column - whether usable
    numbers exist. Pass the rest as keyword arguments: container, delimiter, decimal, encoding, header_row,
    data_family, instrument, template_id, and the stable ids project_id / file_id / sheet_id / dataset_id / graph_id /
    panel_id plus source_revision. Do not pass paths or names as ids: use the app's internal ids."""
    return Context.build(signatures.describe_table(table, **fields))

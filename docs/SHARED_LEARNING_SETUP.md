# Shared learning – owner setup

**Status: not deployed, off by default.** No backend project exists for this app. The desktop adapter has never
talked to a live server. Personal learning works without any of this, without an account and without internet.

What exists and how far it was tested:

| Part | Where | Tested how |
| --- | --- | --- |
| Contribution flow in the app: preview → your consent → outbox → retries → withdrawal → tombstones; background worker | `origin_plot_app/opstudio/learning/sync.py` | `python3 tests/test_learning_sync.py`, against an **in-memory test server** that only simulates the server rules |
| Supabase adapter (REST, sign-in, refresh) | `origin_plot_app/opstudio/learning/supabase_adapter.py` | the same test file, with a **fake HTTP transport** that records requests; its real transport was never executed |
| Tables, triggers and row-level security | `backend/supabase/migrations/0001_learning.sql` | `backend/supabase/tests/rls_tests.sql` run on a throw-away plain PostgreSQL 16 with stand-ins for the Supabase roles; **not** on a Supabase project |

So: the client logic and the SQL rules are tested separately; the two have never been run together, and the HTTP
answers of the real API layer are unconfirmed. Shared learning must stay off until the steps below pass.

## What is shared, and what never is

A contribution is the **shareable projection** of one remembered item: the kind of data, a structural signature made
from recognised roles and units, and the declarative settings. It never contains file names, folders, sample names,
graph titles, notes, measured values or keys. A header the app cannot map to a known role keeps the contribution
back for your review. The user sees the exact payload before submitting (Settings → Learning → *Preview
contribution…*). A contribution starts as `pending`; only a reviewer can approve it; popularity never approves.

Scopes: personal (this computer only), lab (members of one lab), community (every signed-in user, after review).

## Owner steps

1. Create a Supabase project (or a managed Postgres with the same roles). Keep the **secret / service-role key**
   out of the desktop, the repository and chat: it bypasses every access rule.
2. Apply `backend/supabase/migrations/0001_learning.sql` (SQL editor or `supabase db push`).
3. Create two ordinary users and one reviewer; insert a lab, the memberships and the reviewer row as the owner
   (`backend/supabase/README.md` has the statements).
4. Run `backend/supabase/tests/rls_tests.sql` against the project. Every check must pass.
5. **Call the API as an ordinary user** (not only the SQL): a user cannot read another user's pending row, cannot
   set `status` to `approved`, cannot read another lab's rows; a reviewer can approve only in their scope; a replayed
   submission does not duplicate; a revoked row leaves a tombstone. Record the HTTP answers – the adapter expects
   `403`, `409` and `429` as described in the backend README.
6. On each participating computer put **only** the project URL and the publishable (anon) key into
   `<private folder>/learning/remote.json` (`backend/supabase/config.example.json`). The app refuses a key that looks
   like a service-role or secret key. The user's sign-in tokens are kept in the protected credential store.
7. In the app: Settings → Privacy and connections → switch on *Shared learning*; Settings → Learning → *Allow
   shared contributions*. Submit one sanitized recipe from account A, approve it as the reviewer, and check that
   account B receives it and an account outside the lab does not.

Until step 5 has passed with two ordinary users and a reviewer, treat every statement about sharing as untested.

## Turning it off again

Switch off *Allow shared contributions*: nothing new is uploaded; queued contributions can be cancelled and sent
ones withdrawn (a tombstone removes them from other clients at their next sync). A copy that someone already
exported, or a computer that never goes online again, cannot be reached. Local-only mode blocks the sync at the
transport in any case.

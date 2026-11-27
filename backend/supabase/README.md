# backend/supabase: the optional shared-learning backend

**Status: NOT DEPLOYED.** This folder holds SQL and a test script. No Supabase project exists for this app, nothing
here has been applied to one, and the desktop adapter (`origin_plot_app/opstudio/learning/supabase_adapter.py`) has
never talked to a live server. The app works fully without any of this: shared learning is off by default.

What was actually run: the migration and the test script on a throw-away **plain PostgreSQL 16** database on the
development machine, with small stand-ins for the things Supabase provides (the roles `anon`, `authenticated`,
`service_role`, the schema `auth` with `auth.users` and `auth.uid()`). Result: 96 checks passed, 0 failed. That
shows the tables, triggers and row-level security behave as described under PostgreSQL. It does not show how the
Supabase API layer (PostgREST, GoTrue) answers: the HTTP status codes named below are what the SQL asks for, to be
confirmed on a real project (step 5).

| File | What it is |
| --- | --- |
| `migrations/0001_learning.sql` | Tables, constraints, triggers, row-level security. One transaction. |
| `tests/rls_tests.sql` | The access rules tested as ordinary users. Everything is rolled back at the end. |
| `config.example.json` | What `remote.json` on a user's computer looks like. Placeholders only. |

## The model in one page

- `labs`, `lab_members(role: member | reviewer)`, `community_reviewers`: written by the owner only (SQL editor),
  never by the app. A user can read their own memberships.
- `contributions`: a row belongs to the signed-in user who sent it and starts as `pending`, whatever the request
  says. Scope `lab` (with a `lab_id` the user is a member of) or `community`.
  - The owner may withdraw it (`status = 'revoked'`) and may send a **new revision**: a higher `revision` replaces
    the content and puts the row back to `pending`, so changed content is never shown as approved. The same revision
    again changes nothing (a retry). A lower one is refused as a conflict. A revoked id stays revoked.
  - A reviewer of that lab, or a community reviewer for community rows, sets `approved` or `rejected` (and may revoke
    an approved row). Never their own contribution. The server writes `reviewed_by` and `reviewed_at`.
  - Reading: your own rows; approved rows of your lab; approved community rows; reviewers also the pending rows of
    their scope. Nobody reads another lab's rows.
- `contribution_feedback`: one row per user, contribution and operation (`unique`), on an approved contribution the
  user can read and that is not their own. It changes no status and grants no access. No update.
- `tombstones(contribution_id, version, deleted_at)`: written by a trigger when a contribution is revoked or deleted.
  Readable by the owner, by the members of the lab (lab scope) and by every signed-in user (community scope).
  `version` comes from a sequence; clients ask for `version > last seen`.
- `evidence`: a user writes and reads their own diagnostic exports. Nobody else reads them through the API.
- Limits: payloads are JSON objects (contributions up to 32 kB, evidence up to 256 kB), at most 12 levels deep, texts
  up to 2000 characters, no key named `python`, `sql`, `shell`, `labtalk`, `script`, `exec`, `eval` or `macro`;
  `kind` and `data_family` are lower-case words; per user and hour at most 30 new contributions or revisions, 120
  feedback rows, 30 evidence rows.
- Two tables in the schema `private` (not reachable through the API) hold the rate-limit log and, for each
  tombstone, who may read it. That second table is why `tombstones` can keep exactly the three columns the app reads.

Things the SQL does on purpose that differ from the app's in-memory test double (`sync.py`, `FakeRemote`):
a user's feedback on their **own** contribution is refused (the app treats the refusal as final and goes on), and a
revoked contribution cannot come back under the same id.

What the SQL asks the API layer to answer (to be confirmed on a live project): a refused access `403`, a duplicate
id of another user `409`, an older revision `409`, the rate limit `429` with a `Retry-After` header. The last two
are raised as SQLSTATE `PGRST` with a JSON message, the form PostgREST documents for custom HTTP answers; on plain
PostgreSQL they are ordinary exceptions whose message contains `revision_conflict` or `rate_limit_exceeded`.

Known limits: there is no shared count of feedback (each user sees their own rows only), so feedback cannot yet
influence a ranking for others; when a new revision of an approved contribution waits for review, clients that
already downloaded the earlier approved revision keep it until the new one is approved or the contribution is revoked;
`tombstones.version` numbers are handed out before commit, so a client should re-read a small overlap now and then.

## Keys: what goes where

- **Desktop** (`<learning folder>/remote.json`): the project URL and the **publishable** key (`sb_publishable_...`;
  older projects call it the `anon` key). Nothing else. With this key and a user's sign-in, a request runs as the role
  `authenticated` and can do exactly what the policies allow.
- **Never in the desktop, never in this repository, never in a workflow of the coding agent**: the secret key
  (`sb_secret_...`, older: `service_role`) and the database password. They bypass row-level security. The app refuses
  to start shared learning with such a key.
- This description of the key types follows Supabase's documentation as known when this was written; the page
  (https://supabase.com/docs/guides/getting-started/api-keys) could not be opened from the development session, so
  check the names against it when you create the project.

## Owner steps

1. **Create the project** at supabase.com (free tier is enough to try). Note the project URL and the publishable key
   (Project Settings > API keys). Keep the secret key and the database password in your password manager only.
2. **Sign-in settings** (Authentication): e-mail and password; switch off open sign-up if only invited people should
   get an account, and invite the users yourself.
3. **Apply the migration.** SQL editor > paste `migrations/0001_learning.sql` > Run. Or with the connection string
   from Project Settings > Database:

       psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/supabase/migrations/0001_learning.sql

   It is one transaction: it applies whole or not at all. It expects a project without tables of these names.
4. **Create two ordinary users and a reviewer** (Authentication > Users > Add user), then a lab and the roles, in the
   SQL editor (replace the placeholders with the users' ids from the Users page):

       insert into public.labs (id, name) values (gen_random_uuid(), 'YOUR LAB NAME') returning id;
       insert into public.lab_members (lab_id, user_id, role) values
         ('LAB-ID', 'USER-A-ID', 'member'), ('LAB-ID', 'USER-B-ID', 'member'), ('LAB-ID', 'REVIEWER-ID', 'reviewer');
       -- only if someone should approve community contributions:
       insert into public.community_reviewers (user_id) values ('REVIEWER-ID');

   A reviewer cannot approve their own contributions. In a lab with one reviewer, approve the reviewer's own rows
   yourself in the SQL editor (`update public.contributions set status = 'approved' where id = '...'`).
5. **Run the tests against the project** (as the database owner, from your own machine; they roll everything back):

       psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v user_a=USER-A-ID -v user_b=USER-B-ID -v reviewer=REVIEWER-ID \
            -f backend/supabase/tests/rls_tests.sql

   Expected last line: `96 passed, 0 failed`, exit code 0. The script makes its own two test labs and removes them
   again. Then test the API itself as an ordinary user, which the SQL script cannot do: sign in with the app as user
   A, submit one contribution, try to read it as user B (must not appear), approve it as the reviewer, read it as
   user B (appears), withdraw it as A (disappears for B after the next sync). Gate C of the security review asks for
   exactly this with two ordinary users and a reviewer.
6. **Configure a desktop**: copy `config.example.json` to `<learning folder>/remote.json`, put in the project URL and
   the publishable key, and sign in from the app's Privacy page. Sharing stays off until the user switches it on.

To try the SQL without Supabase (what was done here):

    createdb ops_rls_test
    psql -v ON_ERROR_STOP=1 -d ops_rls_test -f backend/supabase/tests/rls_tests.sql
    dropdb ops_rls_test

On a database without a schema `auth` the script first creates the stand-ins and applies the migration itself.
(The roles `anon`, `authenticated` and `service_role` stay in the PostgreSQL cluster afterwards; drop them by hand.)

## Evidence for the fortnightly cycle

The coding job never reads this database. If users upload diagnostics to `evidence`, the maintainer exports the rows
on their own machine with trusted credentials, reviews them, and puts the files into the private evidence source of
the cycle (docs/FORTNIGHTLY_CYCLE.md). Until such an export exists, users can send the file the app writes
("export evidence") by any private route.

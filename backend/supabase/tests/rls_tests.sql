-- Row-level security tests for migrations/0001_learning.sql.
--
-- They act as ordinary signed-in users (role 'authenticated' with the user's id in request.jwt.claims, which is what
-- Supabase sets for a request made with the publishable key and a user session) and check what the SERVER allows.
-- Everything happens in one transaction that is rolled back at the end: nothing stays in the database.
--
-- Plain PostgreSQL (a throw-away local database, no Supabase): the script first makes stand-ins for the Supabase
-- roles and the auth schema, applies the migration, and uses three made-up users:
--     psql -v ON_ERROR_STOP=1 -d ops_rls_test -f backend/supabase/tests/rls_tests.sql
-- A Supabase project (migration already applied; run as the postgres role, never from the desktop):
--     psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v user_a=<uuid> -v user_b=<uuid> -v reviewer=<uuid> -f backend/supabase/tests/rls_tests.sql
--   user_a, user_b: two ordinary users; reviewer: the user who reviews for the first lab. All three must exist in auth.users.
--
-- Output: one line per check, 'PASS  name' or 'FAIL  name   [info]', then 'N passed, M failed'.
-- psql ends with a non-zero exit code when a check fails or the script cannot run.
\set ON_ERROR_STOP on
\set QUIET on
\pset tuples_only on
\pset format unaligned
\pset pager off

\if :{?user_a}
\else
  \set user_a 00000000-0000-4000-8000-00000000000a
\endif
\if :{?user_b}
\else
  \set user_b 00000000-0000-4000-8000-00000000000b
\endif
\if :{?reviewer}
\else
  \set reviewer 00000000-0000-4000-8000-00000000000c
\endif

select not exists (select 1 from pg_namespace where nspname = 'auth') as plain_postgres \gset
\if :plain_postgres
  \echo 'plain PostgreSQL: making stand-ins for the Supabase roles and the auth schema, then applying the migration'
  do $$ begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
    if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin bypassrls; end if;
  end $$;
  create schema auth;
  create table auth.users (id uuid primary key);
  create function auth.uid() returns uuid language sql stable as
    $$ select (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')::uuid $$;
  create function auth.role() returns text language sql stable as
    $$ select nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role' $$;
  grant usage on schema auth to anon, authenticated, service_role;
  grant usage on schema public to anon, authenticated, service_role;
\endif

select to_regclass('public.contributions') is null as no_tables \gset
\if :no_tables
  \if :plain_postgres
    \ir ../migrations/0001_learning.sql
  \else
    do $$ begin raise exception 'The tables are not there: apply backend/supabase/migrations/0001_learning.sql first.'; end $$;
  \endif
\endif

begin;

select set_config('rls_test.a', :'user_a', true), set_config('rls_test.b', :'user_b', true), set_config('rls_test.r', :'reviewer', true) \gset ignored_
\if :plain_postgres
  insert into auth.users (id) values (:'user_a'), (:'user_b'), (:'reviewer') on conflict do nothing;
\endif
do $$ begin
  if (select count(*) from auth.users where id in (current_setting('rls_test.a')::uuid, current_setting('rls_test.b')::uuid, current_setting('rls_test.r')::uuid)) <> 3 then
    raise exception 'user_a, user_b and reviewer must be three different existing users (pass -v user_a=... -v user_b=... -v reviewer=...)';
  end if;
end $$;

-- ------------------------------------------------------------------------------------------ helpers of the test
create schema rls_test;
create table rls_test.results (n serial primary key, ok boolean not null, name text not null, info text not null default '');
create function rls_test.a() returns uuid language sql stable as $$ select current_setting('rls_test.a')::uuid $$;
create function rls_test.b() returns uuid language sql stable as $$ select current_setting('rls_test.b')::uuid $$;
create function rls_test.r() returns uuid language sql stable as $$ select current_setting('rls_test.r')::uuid $$;
create function rls_test.ok(cond boolean, name text, info text default '') returns void language sql security definer as
  $$ insert into rls_test.results (ok, name, info) values (coalesce(cond, false), name, coalesce(info, '')) $$;
-- become a signed-in user / an anonymous visitor / the administrator again
create function rls_test.as_user(u uuid) returns void language plpgsql as $$ begin
  perform set_config('role', 'none', true);
  perform set_config('request.jwt.claims', json_build_object('sub', u, 'role', 'authenticated')::text, true);
  perform set_config('role', 'authenticated', true);
end $$;
create function rls_test.as_anon() returns void language plpgsql as $$ begin
  perform set_config('role', 'none', true);
  perform set_config('request.jwt.claims', json_build_object('role', 'anon')::text, true);
  perform set_config('role', 'anon', true);
end $$;
create function rls_test.as_admin() returns void language plpgsql as $$ begin
  perform set_config('role', 'none', true); perform set_config('request.jwt.claims', '', true);
end $$;
-- how many rows a query returns, how many rows a statement changes, and whether a statement is refused
create function rls_test.n(q text) returns bigint language plpgsql as $$ declare c bigint; begin execute 'select count(*) from (' || q || ') q' into c; return c; end $$;
create function rls_test.changed(q text) returns bigint language plpgsql as $$ declare c bigint; begin execute q; get diagnostics c = row_count; return c; end $$;
create function rls_test.refused(q text, want text default null) returns text language plpgsql as $$
begin
  execute q;
  return 'NOT REFUSED';
exception when others then
  if want is null or sqlstate = want or sqlerrm like want then return 'refused'; end if;
  return 'refused, but with ' || sqlstate || ': ' || sqlerrm;
end $$;
grant usage on schema rls_test to anon, authenticated;
grant execute on all functions in schema rls_test to anon, authenticated;

-- ------------------------------------------------------------------------------------------ the scene
-- two labs; A is a member of lab 1, B of lab 2, R reviews for lab 1. Made by the administrator, as in real use.
insert into public.labs (id, name) values ('11111111-1111-4111-8111-111111111111', 'test lab one'), ('22222222-2222-4222-8222-222222222222', 'test lab two');
insert into public.lab_members (lab_id, user_id, role) values
  ('11111111-1111-4111-8111-111111111111', rls_test.a(), 'member'),
  ('22222222-2222-4222-8222-222222222222', rls_test.b(), 'member'),
  ('11111111-1111-4111-8111-111111111111', rls_test.r(), 'reviewer');
delete from public.community_reviewers where user_id in (rls_test.a(), rls_test.b(), rls_test.r());

-- c1: A, lab 1   c2: A, community   c3: B, lab 2   c4: B, community   c5: A, lab 1 (second)   c6: R, lab 1
create function rls_test.ins(id text, scope text, lab text, extra_cols text default '', extra_vals text default '') returns text language sql as $$
  select format('insert into public.contributions (id, scope, lab_id, kind, data_family, signature, signature_version, schema_version, revision, app_version, payload%s) '
                'values (%L, %L, %s, ''format_mapping'', ''xrd'', ''sig1:test'', 1, 1, 1, ''5.58.6'', ''{"roles": {"x": "two_theta", "y": "intensity"}}''%s)',
                extra_cols, 'cccccccc-cccc-4ccc-8ccc-00000000000' || id, scope, coalesce(quote_literal(lab), 'null'), extra_vals) $$;
grant execute on function rls_test.ins(text, text, text, text, text) to authenticated, anon;
-- the upsert the desktop sends (POST ...?on_conflict=id with Prefer: resolution=merge-duplicates): content columns and its own owner_id
create function rls_test.upsert(id text, scope text, lab text, revision int, payload text) returns text language sql as $$
  select format('insert into public.contributions (id, lab_id, scope, kind, data_family, signature, signature_version, schema_version, revision, app_version, payload, owner_id) '
                'values (%L, %s, %L, ''format_mapping'', ''xrd'', ''sig1:test'', 1, 1, %s, ''5.58.6'', %L, auth.uid()) '
                'on conflict (id) do update set id = excluded.id, lab_id = excluded.lab_id, scope = excluded.scope, kind = excluded.kind, data_family = excluded.data_family, '
                'signature = excluded.signature, signature_version = excluded.signature_version, schema_version = excluded.schema_version, revision = excluded.revision, '
                'app_version = excluded.app_version, payload = excluded.payload, owner_id = excluded.owner_id',
                'cccccccc-cccc-4ccc-8ccc-00000000000' || id, coalesce(quote_literal(lab), 'null'), scope, revision, payload) $$;
grant execute on function rls_test.upsert(text, text, text, int, text) to authenticated, anon;

-- ------------------------------------------------------------------------------------------ 1. inserting
do $$ declare c1 uuid := 'cccccccc-cccc-4ccc-8ccc-000000000001'; x record; begin
  perform rls_test.as_user(rls_test.a());
  -- the request claims to be approved and reviewed already
  perform rls_test.changed(rls_test.ins('1', 'lab', '11111111-1111-4111-8111-111111111111', ', status, reviewed_by, reviewed_at', format(', ''approved'', %L, now()', rls_test.a())));
  execute 'select status, owner_id, reviewed_by, reviewed_at from public.contributions where id = $1' into x using c1;
  perform rls_test.ok(x.status = 'pending' and x.reviewed_by is null and x.reviewed_at is null and x.owner_id = rls_test.a(),
                      'a user cannot approve their own contribution on insert: status approved in the request is stored as pending, with no reviewer', x::text);
  perform rls_test.changed(rls_test.ins('2', 'community', null));
  perform rls_test.changed(rls_test.ins('5', 'lab', '11111111-1111-4111-8111-111111111111'));
  perform rls_test.ok(rls_test.refused(rls_test.ins('7', 'community', null, ', owner_id', format(', %L', rls_test.b())), '42501') = 'refused', 'a user cannot insert a contribution in another user''s name');
  perform rls_test.ok(rls_test.refused(rls_test.ins('7', 'lab', '22222222-2222-4222-8222-222222222222'), '42501') = 'refused', 'a user cannot send a contribution to a lab they are not a member of');
  perform rls_test.ok(rls_test.refused(rls_test.ins('7', 'community', '11111111-1111-4111-8111-111111111111'), '23514') = 'refused', 'a community contribution cannot carry a lab, and a lab contribution needs one');
  perform rls_test.as_user(rls_test.b());
  perform rls_test.changed(rls_test.ins('3', 'lab', '22222222-2222-4222-8222-222222222222'));
  perform rls_test.changed(rls_test.ins('4', 'community', null));
  perform rls_test.as_user(rls_test.r());
  perform rls_test.changed(rls_test.ins('6', 'lab', '11111111-1111-4111-8111-111111111111'));
  perform rls_test.as_anon();
  perform rls_test.ok(rls_test.refused(rls_test.ins('8', 'community', null), '42501') = 'refused' and rls_test.refused('select 1 from public.contributions', '42501') = 'refused'
                      and rls_test.refused('select 1 from public.tombstones', '42501') = 'refused', 'someone who is not signed in can neither insert nor read');
  perform rls_test.as_admin();
end $$;

-- ------------------------------------------------------------------------------------------ 2. reading pending rows
do $$ begin
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions') = 3 and rls_test.n('select 1 from public.contributions where owner_id <> auth.uid()') = 0,
                      'user A sees their own three rows and nothing else', rls_test.n('select 1 from public.contributions')::text);
  perform rls_test.ok(rls_test.n('select 1 from public.contributions where id = ''cccccccc-cccc-4ccc-8ccc-000000000004''') = 0, 'user A cannot read user B''s pending community row');
  perform rls_test.ok(rls_test.n('select 1 from public.contributions where id = ''cccccccc-cccc-4ccc-8ccc-000000000003''') = 0, 'user A (lab 1) cannot read user B''s pending row of lab 2');
  perform rls_test.ok(rls_test.n('select 1 from public.contributions where id = ''cccccccc-cccc-4ccc-8ccc-000000000006''') = 0, 'user A cannot read another member''s pending row of the same lab');
  perform rls_test.as_user(rls_test.b());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions where owner_id <> auth.uid()') = 0 and rls_test.n('select 1 from public.contributions') = 2, 'user B sees only their own two rows');
  perform rls_test.as_admin();
end $$;

-- ------------------------------------------------------------------------------------------ 3. the owner's updates
do $$ declare c1 text := 'where id = ''cccccccc-cccc-4ccc-8ccc-000000000001'''; begin
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.refused('update public.contributions set status = ''approved'' ' || c1, '42501') = 'refused', 'a user cannot approve their own contribution by updating it');
  perform rls_test.ok(rls_test.refused(format('update public.contributions set status = ''approved'', reviewed_by = %L, reviewed_at = now() ', rls_test.r()) || c1, '42501') = 'refused',
                      '... also not by naming a real reviewer in the request');
  perform rls_test.ok(rls_test.refused(format('update public.contributions set reviewed_by = %L ', rls_test.a()) || c1, '42501') = 'refused', 'a user cannot write the review fields');
  perform rls_test.ok(rls_test.refused(format('update public.contributions set owner_id = %L ', rls_test.b()) || c1, '42501') = 'refused', 'a user cannot give a contribution to another owner');
  perform rls_test.ok(rls_test.refused('update public.contributions set scope = ''community'', lab_id = null ' || c1, '42501') = 'refused', 'a user cannot move a lab contribution to the community scope');
  perform rls_test.ok(rls_test.refused('update public.contributions set status = ''rejected'' ' || c1, '42501') = 'refused', 'a user cannot set their contribution to rejected either');
  perform rls_test.ok(rls_test.changed('update public.contributions set payload = ''{"roles": {"x": "two_theta"}}'', revision = 2 ' || c1) = 1
                      and rls_test.n('select 1 from public.contributions ' || c1 || ' and status = ''pending'' and revision = 2 and payload = ''{"roles": {"x": "two_theta"}}''') = 1,
                      'the owner can send a new revision of a pending contribution; it stays pending');
  perform rls_test.as_user(rls_test.b());
  perform rls_test.ok(rls_test.changed('update public.contributions set payload = ''{"x": 1}'' ' || c1) = 0 and rls_test.changed('delete from public.contributions ' || c1) = 0,
                      'another user can neither change nor delete it');
  perform rls_test.as_admin();
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || c1 || ' and status = ''pending'' and reviewed_by is null and revision = 2') = 1, '... and after all these attempts the row is still pending and unreviewed');
end $$;

-- ------------------------------------------------------------------------------------------ 4. the reviewer of lab 1
do $$ declare w text := 'where id = ''cccccccc-cccc-4ccc-8ccc-00000000000'; x record; begin
  perform rls_test.as_user(rls_test.r());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '1''') = 1 and rls_test.n('select 1 from public.contributions ' || w || '5''') = 1, 'the reviewer of lab 1 can read the pending rows of lab 1');
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '3''') = 0, 'the reviewer of lab 1 cannot read rows of lab 2');
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '2''') = 0 and rls_test.n('select 1 from public.contributions ' || w || '4''') = 0, 'the reviewer of lab 1 cannot read pending community rows');
  perform rls_test.ok(rls_test.refused('update public.contributions set status = ''approved'', payload = ''{"changed": true}'' ' || w || '5''', '42501') = 'refused', 'a reviewer cannot change the content while approving');
  perform rls_test.ok(rls_test.changed('update public.contributions set status = ''approved'' ' || w || '1''') = 1, 'the reviewer of lab 1 can approve a pending row of lab 1');
  execute 'select status, reviewed_by, reviewed_at from public.contributions ' || w || '1''' into x;
  perform rls_test.ok(x.status = 'approved' and x.reviewed_by = rls_test.r() and x.reviewed_at is not null, '... the server records who reviewed it and when', x::text);
  perform rls_test.ok(rls_test.changed('update public.contributions set status = ''approved'' ' || w || '3''') = 0, 'the reviewer of lab 1 cannot approve a row of lab 2');
  perform rls_test.ok(rls_test.changed('update public.contributions set status = ''approved'' ' || w || '2''') = 0 and rls_test.changed('update public.contributions set status = ''approved'' ' || w || '4''') = 0,
                      'the reviewer of lab 1 cannot approve community rows');
  perform rls_test.ok(rls_test.refused('update public.contributions set status = ''approved'' ' || w || '6''', '42501') = 'refused', 'a reviewer cannot approve their own contribution');
  perform rls_test.ok(rls_test.refused('update public.contributions set status = ''pending'' ' || w || '1''', '42501') = 'refused', 'a reviewer cannot move an approved row back to pending');
  perform rls_test.as_admin();
  perform rls_test.ok(rls_test.n('select 1 from public.contributions where status = ''approved''') = 1, '... exactly one row is approved now', rls_test.n('select 1 from public.contributions where status = ''approved''')::text);
end $$;

-- ------------------------------------------------------------------------------------------ 5. approved lab rows and lab borders
do $$ declare w text := 'where id = ''cccccccc-cccc-4ccc-8ccc-00000000000'; begin
  update public.contributions set status = 'approved' where id = 'cccccccc-cccc-4ccc-8ccc-000000000003';        -- the administrator approves B's row of lab 2
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '3''') = 0, 'a member of lab 1 cannot read an approved row of lab 2');
  perform rls_test.ok(rls_test.n('select 1 from public.labs') = 1 and rls_test.n('select 1 from public.lab_members') = 1, 'a member sees their own lab and their own membership, not the other lab or other members');
  perform rls_test.as_user(rls_test.b());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '1''') = 0, 'a member of lab 2 cannot read an approved row of lab 1');
  perform rls_test.ok(rls_test.refused(format('insert into public.lab_members (lab_id, user_id, role) values (''11111111-1111-4111-8111-111111111111'', %L, ''reviewer'')', rls_test.b()), '42501') = 'refused'
                      and rls_test.refused(format('insert into public.community_reviewers (user_id) values (%L)', rls_test.b()), '42501') = 'refused'
                      and rls_test.refused('update public.lab_members set role = ''reviewer''', '42501') = 'refused', 'a user cannot make themselves a member or a reviewer');
  perform rls_test.as_admin();
  insert into public.lab_members (lab_id, user_id, role) values ('11111111-1111-4111-8111-111111111111', rls_test.b(), 'member');   -- B joins lab 1 as an ordinary member
  perform rls_test.as_user(rls_test.b());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '1''') = 1 and rls_test.n('select 1 from public.contributions ' || w || '5''') = 0,
                      'a member of the lab reads its approved rows, and still not its pending ones');
  perform rls_test.ok(rls_test.changed('update public.contributions set status = ''approved'' ' || w || '5''') = 0, '... and an ordinary member cannot approve');
  perform rls_test.as_admin();
  delete from public.lab_members where lab_id = '11111111-1111-4111-8111-111111111111' and user_id = rls_test.b();
end $$;

-- ------------------------------------------------------------------------------------------ 6. the community scope
do $$ declare w text := 'where id = ''cccccccc-cccc-4ccc-8ccc-00000000000'; begin
  insert into public.community_reviewers (user_id) values (rls_test.b());                                  -- the administrator makes B a community reviewer
  perform rls_test.as_user(rls_test.b());
  perform rls_test.ok(rls_test.changed('update public.contributions set status = ''approved'' ' || w || '2''') = 1, 'a community reviewer can approve a community row');
  perform rls_test.ok(rls_test.refused('update public.contributions set status = ''approved'' ' || w || '4''', '42501') = 'refused', '... but not their own');
  perform rls_test.ok(rls_test.changed('update public.contributions set status = ''approved'' ' || w || '5''') = 0, '... and not a lab row');
  perform rls_test.as_user(rls_test.r());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '2''') = 1 and rls_test.n('select 1 from public.contributions ' || w || '4''') = 0,
                      'every signed-in user reads an approved community row, and not a pending one');
  perform rls_test.as_user(rls_test.a());
  perform rls_test.changed('update public.contributions set payload = ''{"changed": true}'' ' || w || '2''');
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '2'' and status = ''approved'' and payload = ''{"roles": {"x": "two_theta", "y": "intensity"}}''') = 1,
                      'the owner cannot change an approved contribution behind the reviewer''s back: without a new revision nothing changes');
  perform rls_test.as_admin();
end $$;

-- ------------------------------------------------------------------------------------------ 7. a request sent twice
do $$ declare before bigint; begin
  select count(*) into before from public.contributions;
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.refused(rls_test.ins('1', 'lab', '11111111-1111-4111-8111-111111111111'), '23505') = 'refused', 'the same contribution id sent again is refused as a duplicate');
  perform rls_test.ok(rls_test.changed(rls_test.ins('1', 'lab', '11111111-1111-4111-8111-111111111111') || ' on conflict (id) do nothing') = 0, '... or ignored when the client asks to ignore duplicates');
  perform rls_test.as_user(rls_test.b());
  perform rls_test.ok(rls_test.changed(rls_test.ins('1', 'community', null) || ' on conflict (id) do nothing') = 0
                      and rls_test.refused(rls_test.ins('1', 'community', null) || ' on conflict (id) do update set payload = excluded.payload') = 'refused', '... another user cannot take over the id either');
  perform rls_test.as_admin();
  perform rls_test.ok((select count(*) from public.contributions) = before and (select status = 'approved' and owner_id = rls_test.a() and revision = 2 from public.contributions where id = 'cccccccc-cccc-4ccc-8ccc-000000000001'),
                      '... no second row was made and the first one is unchanged');
end $$;

-- ------------------------------------------------------------------------------------------ 7b. the upsert the desktop sends
do $$ declare w text := 'where id = ''cccccccc-cccc-4ccc-8ccc-00000000000'; body text := '{"roles": {"x": "two_theta", "y": "intensity"}}'; stamp timestamptz; x record; logged bigint; begin
  select updated_at into stamp from public.contributions where id = 'cccccccc-cccc-4ccc-8ccc-000000000002';
  select count(*) into logged from private.rate_log where user_id = rls_test.a();
  perform rls_test.as_user(rls_test.a());
  perform rls_test.changed(rls_test.upsert('2', 'community', null, 1, body));
  perform rls_test.changed(rls_test.upsert('2', 'community', null, 1, '{"changed": "same revision"}'));
  perform rls_test.as_admin();
  select status, payload::text as payload, updated_at, reviewed_by from public.contributions where id = 'cccccccc-cccc-4ccc-8ccc-000000000002' into x;
  perform rls_test.ok(x.status = 'approved' and x.payload = body::jsonb::text and x.updated_at = stamp and x.reviewed_by = rls_test.b()
                      and (select count(*) from private.rate_log where user_id = rls_test.a()) = logged,
                      'the same revision sent again (a retry) changes nothing, not even on an approved row, and does not count against the rate limit', x::text);
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.refused(rls_test.upsert('1', 'lab', '11111111-1111-4111-8111-111111111111', 1, body), '%revision_conflict%') = 'refused',
                      'an older revision than the stored one is answered with a conflict', rls_test.refused(rls_test.upsert('1', 'lab', '11111111-1111-4111-8111-111111111111', 1, body), '%revision_conflict%'));
  perform rls_test.ok(rls_test.refused(rls_test.upsert('1', 'community', null, 3, body), '42501') = 'refused', 'a new revision cannot move the contribution to another scope');
  -- a row of its own for the new-revision case: c9, A's, community; B (community reviewer) approves it
  perform rls_test.changed(rls_test.upsert('9', 'community', null, 1, body));
  perform rls_test.as_user(rls_test.b());
  perform rls_test.changed('update public.contributions set status = ''approved'' ' || w || '9''');
  perform rls_test.as_user(rls_test.r());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '9'' and status = ''approved''') = 1, '(the new row is approved and every user can read it)');
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.changed(rls_test.upsert('9', 'community', null, 2, '{"roles": {"x": "wavenumber"}}')) = 1, 'the owner can send a new revision of an approved contribution');
  perform rls_test.as_admin();
  select status, revision, reviewed_by, reviewed_at, payload::text as payload from public.contributions where id = 'cccccccc-cccc-4ccc-8ccc-000000000009' into x;
  perform rls_test.ok(x.status = 'pending' and x.revision = 2 and x.reviewed_by is null and x.reviewed_at is null and x.payload = '{"roles": {"x": "wavenumber"}}',
                      '... it goes back to pending and loses its review: changed content is never shown as approved', x::text);
  perform rls_test.as_user(rls_test.r());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '9''') = 0, '... and other users no longer read it until it is approved again');
  perform rls_test.as_user(rls_test.b());
  perform rls_test.ok(rls_test.refused(rls_test.upsert('9', 'community', null, 3, body), '42501') = 'refused', 'another user cannot send a revision of it, not even a reviewer');
  perform rls_test.as_admin();
end $$;

-- ------------------------------------------------------------------------------------------ 8. feedback
do $$ declare fb text := 'insert into public.contribution_feedback (contribution_id, operation_id, outcome%s) values (''cccccccc-cccc-4ccc-8ccc-00000000000%s'', %L, %L%s)'; begin
  perform rls_test.as_user(rls_test.r());
  perform rls_test.ok(rls_test.changed(format(fb, '', '2', 'op-1', 'accepted', '')) = 1, 'a user can give feedback on an approved contribution they can read');
  perform rls_test.ok(rls_test.refused(format(fb, '', '2', 'op-1', 'accepted', ''), '23505') = 'refused' and rls_test.changed(format(fb, '', '2', 'op-1', 'rejected', '') || ' on conflict do nothing') = 0
                      and rls_test.n('select 1 from public.contribution_feedback') = 1, 'the same user, contribution and operation counts once: a retry is not a second vote');
  perform rls_test.ok(rls_test.changed(format(fb, '', '2', 'op-2', 'rejected', '')) = 1, 'another operation is another row');
  perform rls_test.ok(rls_test.refused(format(fb, ', user_id', '2', 'op-3', 'accepted', format(', %L', rls_test.b())), '42501') = 'refused', 'feedback cannot be given in another user''s name');
  perform rls_test.ok(rls_test.refused(format(fb, '', '4', 'op-4', 'accepted', ''), '42501') = 'refused', 'no feedback on a contribution the user cannot read (pending, another owner)');
  perform rls_test.ok(rls_test.refused(format(fb, '', '3', 'op-5', 'accepted', ''), '42501') = 'refused', 'no feedback on an approved row of another lab: feedback grants no access');
  perform rls_test.ok(rls_test.refused('update public.contribution_feedback set outcome = ''accepted''', '42501') = 'refused', 'feedback cannot be rewritten afterwards');
  perform rls_test.ok(rls_test.refused(format(fb, '', '2', 'op-6', 'approved', ''), '23514') = 'refused', 'the outcome is accepted or rejected, nothing else');
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.refused(format(fb, '', '2', 'op-7', 'accepted', ''), '42501') = 'refused', 'the owner cannot vote for their own contribution');
  perform rls_test.ok(rls_test.n('select 1 from public.contribution_feedback') = 0, 'a user sees their own feedback rows only');
  perform rls_test.as_admin();
  perform rls_test.ok((select status = 'approved' from public.contributions where id = 'cccccccc-cccc-4ccc-8ccc-000000000002')
                      and (select status = 'pending' from public.contributions where id = 'cccccccc-cccc-4ccc-8ccc-000000000004'), 'feedback changed no status');
end $$;

-- ------------------------------------------------------------------------------------------ 9. revoking, deleting, tombstones
do $$ declare w text := 'where id = ''cccccccc-cccc-4ccc-8ccc-00000000000'; t text := 'select 1 from public.tombstones where contribution_id = ''cccccccc-cccc-4ccc-8ccc-00000000000'; begin
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.n('select 1 from public.tombstones') = 0, 'there is no tombstone before anything was revoked');
  perform rls_test.ok(rls_test.changed('update public.contributions set status = ''revoked'' ' || w || '1''') = 1 and rls_test.n(t || '1''') = 1, 'the owner revokes an approved contribution: a tombstone is written');
  perform rls_test.ok(rls_test.changed('delete from public.contributions ' || w || '5''') = 1 and rls_test.n(t || '5''') = 1, 'the owner deletes a pending contribution: a tombstone is written');
  perform rls_test.ok(rls_test.changed('update public.contributions set status = ''revoked'' ' || w || '2''') = 1 and rls_test.n(t || '2''') = 1, 'the owner revokes a community contribution: a tombstone is written');
  perform rls_test.ok(rls_test.refused('update public.contributions set status = ''pending'' ' || w || '1''', '42501') = 'refused'
                      and rls_test.refused(rls_test.upsert('1', 'lab', '11111111-1111-4111-8111-111111111111', 7, '{"again": true}'), '42501') = 'refused', 'a revoked contribution cannot be brought back by its owner, not even as a new revision');
  perform rls_test.ok(rls_test.changed('update public.contributions set status = ''revoked'' ' || w || '1''') = 1 and rls_test.n('select 1 from public.tombstones') = 3, 'revoking it a second time (a retry) is accepted and makes no second tombstone');
  perform rls_test.ok(rls_test.refused('insert into public.tombstones (contribution_id) values (gen_random_uuid())', '42501') = 'refused'
                      and rls_test.refused('delete from public.tombstones', '42501') = 'refused', 'a user can neither write nor remove tombstones');
  perform rls_test.as_user(rls_test.r());
  perform rls_test.ok(rls_test.n(t || '1''') = 1 and rls_test.n(t || '5''') = 1 and rls_test.n(t || '2''') = 1, 'a member of lab 1 reads the tombstones of lab 1 and of the community');
  perform rls_test.as_user(rls_test.b());
  perform rls_test.ok(rls_test.n(t || '1''') = 0 and rls_test.n(t || '5''') = 0 and rls_test.n(t || '2''') = 1, 'a member of lab 2 reads the community tombstone and not those of lab 1');
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '2''') = 1, '(B is a community reviewer in this scene and therefore still sees the revoked row)');
  perform rls_test.as_user(rls_test.r());
  perform rls_test.ok(rls_test.n('select 1 from public.contributions ' || w || '2''') = 0, 'an ordinary user no longer reads a revoked community row');
  perform rls_test.as_admin();
  perform rls_test.ok((select count(*) = 3 and count(distinct version) = 3 and min(version) > 0 from public.tombstones), 'each tombstone has a version number of its own', (select string_agg(version::text, ',') from public.tombstones));
  delete from public.contributions where id = 'cccccccc-cccc-4ccc-8ccc-000000000001';
  perform rls_test.ok((select count(*) from public.tombstones) = 3, 'deleting a row that was already revoked makes no second tombstone');
end $$;

-- ------------------------------------------------------------------------------------------ 10. shape and size of what is stored
do $$ declare base text := 'insert into public.contributions (scope, kind, data_family, signature, signature_version, schema_version, app_version, payload) values (''community'', %L, %L, %L, 1, %s, %L, %L::jsonb)'; begin
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.refused(format(base, 'format_mapping', 'xrd', 'sig1:t', '1', '5.58.6', '[1, 2, 3]'), '23514') = 'refused', 'a payload that is not a JSON object is refused');
  perform rls_test.ok(rls_test.refused(format(base, 'format_mapping', 'xrd', 'sig1:t', '1', '5.58.6', (select json_object_agg('k' || g, (select array_agg(md5((g * 1000 + i)::text)) from generate_series(1, 250) i)) from generate_series(1, 6) g)::text), '23514') = 'refused',
                      'a payload that is too large is refused');
  perform rls_test.ok(rls_test.refused(format(base, 'format_mapping', 'xrd', 'sig1:t', '1', '5.58.6', repeat('{"a":', 14) || '1' || repeat('}', 14)), '23514') = 'refused', 'a payload nested too deep is refused');
  perform rls_test.ok(rls_test.refused(format(base, 'format_mapping', 'xrd', 'sig1:t', '1', '5.58.6', '{"steps": [{"python": "import os"}]}'), '23514') = 'refused'
                      and rls_test.refused(format(base, 'format_mapping', 'xrd', 'sig1:t', '1', '5.58.6', '{"LabTalk": "run.section()"}'), '23514') = 'refused', 'a payload with a key that names code (python, labtalk ...) is refused');
  perform rls_test.ok(rls_test.refused(format(base, 'format_mapping', 'xrd', 'sig1:t', '1', '5.58.6', json_build_object('note', repeat('x', 2001))::text), '23514') = 'refused', 'a payload with an over-long text is refused');
  perform rls_test.ok(rls_test.refused(format(base, 'Format Mapping!', 'xrd', 'sig1:t', '1', '5.58.6', '{}'), '23514') = 'refused' and rls_test.refused(format(base, 'format_mapping', 'XRD data', 'sig1:t', '1', '5.58.6', '{}'), '23514') = 'refused',
                      'kind and data family must have their fixed form');
  perform rls_test.ok(rls_test.refused(format(base, 'format_mapping', 'xrd', 'C:\Users\x\scan.xrdml', '1', '5.58.6', '{}'), '23514') = 'refused' and rls_test.refused(format(base, 'format_mapping', 'xrd', repeat('s', 200), '1', '5.58.6', '{}'), '23514') = 'refused',
                      'a signature that looks like a path, or is too long, is refused');
  perform rls_test.ok(rls_test.refused(format(base, 'format_mapping', 'xrd', 'sig1:t', '0', '5.58.6', '{}'), '23514') = 'refused' and rls_test.refused(format(base, 'format_mapping', 'xrd', 'sig1:t', '1001', '5.58.6', '{}'), '23514') = 'refused'
                      and rls_test.refused(format(base, 'format_mapping', 'xrd', 'sig1:t', '1', 'latest', '{}'), '23514') = 'refused', 'schema version and app version outside their range or form are refused');
  perform rls_test.ok(rls_test.changed(format(base, 'graph_style', 'general_xy', '', '1', '', '{"schema": "x", "recipe": {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": 1}}}}}}}}}')) = 1,
                      'what the desktop really sends is accepted: no format signature, eight levels of nesting');
  perform rls_test.as_admin();
end $$;

-- ------------------------------------------------------------------------------------------ 11. evidence
do $$ begin
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.changed('insert into public.evidence (payload) values (''{"schema": "opstudio.evidence/1", "items": []}'')') = 1 and rls_test.n('select 1 from public.evidence') = 1, 'a user can send evidence and read their own');
  perform rls_test.ok(rls_test.refused(format('insert into public.evidence (owner_id, payload) values (%L, ''{}'')', rls_test.b()), '42501') = 'refused' and rls_test.refused('update public.evidence set payload = ''{}''', '42501') = 'refused',
                      'evidence cannot be sent in another user''s name, nor rewritten');
  perform rls_test.as_user(rls_test.b());
  perform rls_test.ok(rls_test.n('select 1 from public.evidence') = 0, 'another user cannot read it, not even a reviewer');
  perform rls_test.as_admin();
end $$;

-- ------------------------------------------------------------------------------------------ 12. the rate limit
do $$ declare done int := 0; msg text := ''; already int; begin
  select count(*) into already from private.rate_log where user_id = rls_test.b() and action = 'contributions';
  perform rls_test.as_user(rls_test.b());
  begin
    for i in 1..40 loop
      execute 'insert into public.contributions (scope, kind, data_family, signature, signature_version, schema_version, app_version, payload) values (''community'', ''format_mapping'', ''xrd'', ''sig1:rate'', 1, 1, ''5.58.6'', ''{}'')';
      done := done + 1;
    end loop;
  exception when others then msg := sqlerrm; done := -1;
  end;
  perform rls_test.ok(done = -1 and msg like '%rate_limit_exceeded%' and msg like '%per hour%', 'a user who inserts 40 contributions in a row is stopped by the rate limit, and the whole burst is undone', msg);
  done := 0;
  for i in 1..40 loop
    begin
      execute 'insert into public.contributions (scope, kind, data_family, signature, signature_version, schema_version, app_version, payload) values (''community'', ''format_mapping'', ''xrd'', ''sig1:rate'', 1, 1, ''5.58.6'', ''{}'')';
      done := done + 1;
    exception when others then exit;
    end;
  end loop;
  perform rls_test.ok(done + already = 30, 'one by one, exactly 30 new rows per hour get through (counting the earlier ones of this user)', format('%s now + %s earlier', done, already));
  perform rls_test.ok(rls_test.changed('delete from public.contributions where signature = ''sig1:rate''') = done
                      and rls_test.refused('insert into public.contributions (scope, kind, data_family, signature, signature_version, schema_version, app_version, payload) values (''community'', ''format_mapping'', ''xrd'', ''sig1:rate'', 1, 1, ''5.58.6'', ''{}'')', '%rate_limit_exceeded%') = 'refused',
                      'deleting rows does not give the quota back');
  perform rls_test.ok(rls_test.refused('select 1 from private.rate_log', '42501') = 'refused' and rls_test.refused('select 1 from private.tombstone_scope', '42501') = 'refused', 'the internal tables are closed to users');
  perform rls_test.as_user(rls_test.a());
  perform rls_test.ok(rls_test.changed('insert into public.contributions (scope, kind, data_family, signature, signature_version, schema_version, app_version, payload) values (''community'', ''format_mapping'', ''xrd'', ''sig1:other'', 1, 1, ''5.58.6'', ''{}'')') = 1,
                      'the limit is per user: another user is not held back');
  perform rls_test.as_admin();
end $$;

-- ------------------------------------------------------------------------------------------ every table has row-level security
select rls_test.ok(count(*) filter (where not c.relrowsecurity) = 0 and count(*) = 9, 'row-level security is enabled on every table of the migration',
                   coalesce(string_agg(c.relname, ', ') filter (where not c.relrowsecurity), '') || ' / ' || count(*)::text)
  from pg_class c join pg_namespace s on s.oid = c.relnamespace
  where c.relkind = 'r' and ((s.nspname = 'public' and c.relname in ('labs', 'lab_members', 'community_reviewers', 'contributions', 'contribution_feedback', 'tombstones', 'evidence'))
                             or (s.nspname = 'private' and c.relname in ('tombstone_scope', 'rate_log'))) \gset ignored_
select rls_test.ok(not has_table_privilege('anon', 'public.contributions', 'select') and not has_table_privilege('anon', 'public.evidence', 'insert')
                   and not has_table_privilege('authenticated', 'public.lab_members', 'insert') and not has_table_privilege('authenticated', 'public.tombstones', 'insert')
                   and not has_table_privilege('authenticated', 'public.contribution_feedback', 'update'), 'the table privileges are as narrow as the policies expect') \gset ignored_

-- ------------------------------------------------------------------------------------------ the result
select (case when ok then 'PASS  ' else 'FAIL  ' end) || name || (case when info <> '' and not ok then '   [' || info || ']' else '' end) from rls_test.results order by n;
select format(E'\n%s passed, %s failed', count(*) filter (where ok), count(*) filter (where not ok)) from rls_test.results;
select (count(*) filter (where not ok) > 0 or count(*) = 0) as any_failed from rls_test.results \gset
rollback;
\if :any_failed
  do $$ begin raise exception 'the row-level security tests did not all pass'; end $$;
\endif

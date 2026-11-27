-- Origin Plot Studio: optional shared-learning backend (Supabase / Postgres 15+).
-- NOT DEPLOYED ANYWHERE by this repository. The owner applies it to a project of their own (see ../README.md).
--
-- What the desktop gets: the project URL and the publishable (anon) key, plus the signed-in user's own session.
-- With those it can do exactly what the row-level security below allows. No secret / service_role key is ever
-- needed by the desktop, and none may be put into it.
--
-- Rules enforced here, on the server, and not by hiding buttons in the app:
--   * a contribution starts as 'pending' and belongs to the user who sent it; the request cannot say otherwise
--   * the owner may withdraw (revoke) it at any time, and send a NEW REVISION of it: a higher revision number replaces
--     the content and puts the row back to 'pending' (it must be reviewed again); the same revision sent again changes
--     nothing (a retry); a lower one is answered with a conflict. The owner can never approve it, give it to someone
--     else, or move it to another scope or lab. A revoked id stays revoked.
--   * a reviewer of that lab (lab scope) or a community reviewer (community scope) approves or rejects it,
--     and never one of their own
--   * approved lab rows are read by members of that lab, approved community rows by every signed-in user,
--     pending rows by their owner and the reviewers of their scope; nobody reads another lab's rows
--   * feedback: one row per user, contribution and operation; it changes no status and grants no access
--   * revoking or deleting a contribution leaves a tombstone, so that copies in other clients can be removed
--   * payloads are JSON objects of limited size, depth and shape; text columns have fixed forms
--   * a user can send only so many new rows or new revisions per hour (retries of the same record do not count)
--
-- Roles: 'authenticated' is the signed-in user (subject to everything below); 'anon' (not signed in) gets nothing.
-- Roles that bypass row-level security (postgres, service_role) are the trusted side: the SQL editor of the owner
-- and trusted infrastructure. They are how labs, members and reviewers are administered.

begin;

create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;          -- for the helper functions used by policies and checks; its tables stay closed

-- ---------------------------------------------------------------------------------------------- tables
create table public.labs (
  id          uuid primary key default gen_random_uuid(),
  name        text not null check (char_length(name) between 1 and 80),
  created_at  timestamptz not null default now()
);

create table public.lab_members (
  lab_id   uuid not null references public.labs (id) on delete cascade,
  user_id  uuid not null references auth.users (id) on delete cascade,
  role     text not null default 'member' check (role in ('member', 'reviewer')),
  primary key (lab_id, user_id)
);
create index lab_members_user_idx on public.lab_members (user_id);

create table public.community_reviewers (
  user_id  uuid primary key references auth.users (id) on delete cascade
);

-- A JSON value of limited depth, width and text length, whose keys do not name executable content.
create function private.learning_json_ok(v jsonb, depth int default 0, max_items int default 256) returns boolean
language plpgsql immutable set search_path = '' as $$
declare k text; c jsonb;
begin
  if v is null then return false; end if;
  if depth > 12 then return false; end if;
  case jsonb_typeof(v)
    when 'object' then
      if (select count(*) from jsonb_object_keys(v)) > 64 then return false; end if;
      for k, c in select * from jsonb_each(v) loop
        if char_length(k) not between 1 and 64 or k ~ '[[:cntrl:]]' then return false; end if;
        if lower(k) in ('python', 'sql', 'shell', 'labtalk', 'script', 'exec', 'eval', 'macro') then return false; end if;
        if not private.learning_json_ok(c, depth + 1, max_items) then return false; end if;
      end loop;
    when 'array' then
      if jsonb_array_length(v) > max_items then return false; end if;
      for c in select * from jsonb_array_elements(v) loop
        if not private.learning_json_ok(c, depth + 1, max_items) then return false; end if;
      end loop;
    when 'string' then
      if char_length(v #>> '{}') > 2000 then return false; end if;
    else null;
  end case;
  return true;
end $$;

create table public.contributions (
  id                 uuid primary key default gen_random_uuid(),       -- the client sends its own stable id, so a retry is the same row
  owner_id           uuid not null default auth.uid() references auth.users (id) on delete cascade,
  lab_id             uuid null references public.labs (id) on delete cascade,
  scope              text not null check (scope in ('lab', 'community')),
  status             text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'revoked')),
  kind               text not null check (kind ~ '^[a-z][a-z0-9_]{0,31}$'),
  data_family        text not null check (data_family ~ '^[a-z][a-z0-9_]{0,31}$'),
  signature          text not null default '' check (signature ~ '^([A-Za-z0-9][A-Za-z0-9_.:+=|,-]{0,159})?$'),   -- '' = no format signature
  signature_version  int  not null check (signature_version between 0 and 100000),
  schema_version     int  not null check (schema_version between 1 and 1000),
  revision           int  not null default 1 check (revision between 1 and 100000),
  app_version        text not null default '' check (app_version ~ '^([0-9]{1,4}(\.[0-9]{1,4}){1,3}([.+-][A-Za-z0-9.]{1,16})?)?$'),
  payload            jsonb not null,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  reviewed_by        uuid null references auth.users (id) on delete set null,
  reviewed_at        timestamptz null,
  constraint contributions_scope_lab check ((scope = 'lab') = (lab_id is not null)),
  constraint contributions_payload_object check (jsonb_typeof(payload) = 'object'),
  constraint contributions_payload_size check (pg_column_size(payload) <= 32768 and octet_length(payload::text) <= 32768),
  constraint contributions_payload_shape check (private.learning_json_ok(payload))
);
create index contributions_read_idx on public.contributions (status, scope, lab_id, updated_at);
create index contributions_owner_idx on public.contributions (owner_id);

create table public.contribution_feedback (
  id               uuid primary key default gen_random_uuid(),
  contribution_id  uuid not null references public.contributions (id) on delete cascade,
  user_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  operation_id     text not null check (operation_id ~ '^[A-Za-z0-9_.:-]{1,96}$'),
  outcome          text not null check (outcome in ('accepted', 'rejected')),
  created_at       timestamptz not null default now(),
  unique (contribution_id, user_id, operation_id)
);

create sequence public.tombstones_version_seq as bigint;
create table public.tombstones (
  contribution_id  uuid primary key,                                   -- no foreign key: the row it names may be gone
  version          bigint not null unique default nextval('public.tombstones_version_seq'),
  deleted_at       timestamptz not null default now()
);
alter sequence public.tombstones_version_seq owned by public.tombstones.version;

create table public.evidence (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  payload     jsonb not null,
  created_at  timestamptz not null default now(),
  constraint evidence_payload_object check (jsonb_typeof(payload) = 'object'),
  constraint evidence_payload_size check (pg_column_size(payload) <= 262144 and octet_length(payload::text) <= 262144),
  constraint evidence_payload_shape check (private.learning_json_ok(payload, 0, 2000))
);
create index evidence_owner_idx on public.evidence (owner_id, created_at);

-- Not part of the API (schema private is not exposed): who could read a contribution when its tombstone was written,
-- and the log the rate limit counts in.
create table private.tombstone_scope (
  contribution_id  uuid primary key,
  owner_id         uuid,
  scope            text not null,
  lab_id           uuid
);
create table private.rate_log (
  user_id  uuid not null,
  action   text not null,
  at       timestamptz not null default now()
);
create index rate_log_idx on private.rate_log (user_id, action, at);

-- ---------------------------------------------------------------------------------------------- helpers
-- SECURITY DEFINER with an empty search_path: they answer one yes/no question about the caller and nothing else.
create function private.is_lab_member(p_lab uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.lab_members m where m.lab_id = p_lab and m.user_id = (select auth.uid()))
$$;

create function private.is_lab_reviewer(p_lab uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.lab_members m where m.lab_id = p_lab and m.user_id = (select auth.uid()) and m.role = 'reviewer')
$$;

create function private.is_community_reviewer() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.community_reviewers r where r.user_id = (select auth.uid()))
$$;

create function private.can_review(p_scope text, p_lab uuid) returns boolean
language sql stable set search_path = '' as $$
  select case p_scope when 'lab' then private.is_lab_reviewer(p_lab) when 'community' then private.is_community_reviewer() else false end
$$;

create function private.can_read_tombstone(p_id uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from private.tombstone_scope s
                 where s.contribution_id = p_id
                   and (s.owner_id = (select auth.uid()) or s.scope = 'community'
                        or (s.scope = 'lab' and exists (select 1 from public.lab_members m where m.lab_id = s.lab_id and m.user_id = (select auth.uid())))))
$$;

-- The roles that row-level security does not apply to: superusers, roles with BYPASSRLS (service_role) and the owner
-- of the tables (postgres). That is the trusted side. 'authenticated' and 'anon' are none of these.
create function private.is_trusted() returns boolean
language sql stable set search_path = '' as $$
  select coalesce((select r.rolsuper or r.rolbypassrls from pg_catalog.pg_roles r where r.rolname = current_user), false)
      or coalesce((select pg_catalog.pg_has_role(current_user, c.relowner, 'MEMBER') from pg_catalog.pg_class c
                   where c.oid = 'public.contributions'::pg_catalog.regclass), false)
$$;

-- ---------------------------------------------------------------------------------------------- triggers
-- What a request may set and change. Runs before the policies are checked, for every role that is not trusted.
create function private.contributions_guard() returns trigger
language plpgsql set search_path = '' as $$
declare me uuid := auth.uid(); content_changed boolean;
begin
  if private.is_trusted() then
    if tg_op = 'UPDATE' then new.updated_at := now(); end if;
    return new;
  end if;
  if me is null then raise exception 'not signed in' using errcode = '42501'; end if;

  if tg_op = 'INSERT' then
    if new.owner_id is not null and new.owner_id <> me then
      raise exception 'a contribution can only be sent in your own name' using errcode = '42501';
    end if;
    new.owner_id := me;
    new.status := 'pending';            -- whatever the request said
    new.reviewed_by := null;
    new.reviewed_at := null;
    new.created_at := now();
    new.updated_at := now();
    return new;
  end if;

  -- UPDATE
  if new.id <> old.id or new.owner_id <> old.owner_id or new.scope <> old.scope or new.lab_id is distinct from old.lab_id or new.created_at <> old.created_at then
    raise exception 'id, owner, scope, lab and creation time of a contribution cannot be changed' using errcode = '42501';
  end if;
  content_changed := (new.kind, new.data_family, new.signature, new.signature_version, new.schema_version, new.revision, new.app_version, new.payload)
                     is distinct from (old.kind, old.data_family, old.signature, old.signature_version, old.schema_version, old.revision, old.app_version, old.payload);

  if old.owner_id = me then
    -- the owner: withdraw, or send a new revision (which must be reviewed again); never a review
    if new.reviewed_by is distinct from old.reviewed_by or new.reviewed_at is distinct from old.reviewed_at then
      raise exception 'review fields are set by the server' using errcode = '42501';
    end if;
    if new.status is distinct from old.status then
      if new.status = 'revoked' and not content_changed then null;                         -- withdraw: the one status an owner may ask for
      else raise exception 'the owner of a contribution cannot make this change (status % to %)', old.status, new.status using errcode = '42501';
      end if;
    elsif old.status = 'revoked' then
      if content_changed then raise exception 'a revoked contribution stays revoked; send the new record under a new id' using errcode = '42501'; end if;
      return old;
    elsif new.revision < old.revision then
      raise sqlstate 'PGRST' using
        message = json_build_object('code', 'revision_conflict', 'message', format('revision_conflict: the stored revision is %s', old.revision),
                                    'details', old.revision::text, 'hint', 'the stored record is newer')::text,
        detail = json_build_object('status', 409, 'headers', json_build_object())::text;
    elsif new.revision = old.revision then
      return old;                                                                          -- the same revision again: a retry, nothing changes
    else
      perform private.rate_hit('contributions', 30);                                       -- a new revision: counted, and reviewed again
      new.status := 'pending'; new.reviewed_by := null; new.reviewed_at := null;
    end if;
  elsif private.can_review(old.scope, old.lab_id) then
    -- a reviewer of this scope, and not the owner: the status only
    if content_changed then raise exception 'a reviewer changes the status only' using errcode = '42501'; end if;
    if old.status = 'pending' and new.status in ('approved', 'rejected') then
      new.reviewed_by := me; new.reviewed_at := now();
    elsif old.status = 'approved' and new.status = 'revoked' then
      new.reviewed_by := me; new.reviewed_at := now();
    elsif new.status = old.status then
      new.reviewed_by := old.reviewed_by; new.reviewed_at := old.reviewed_at;
    else raise exception 'a reviewer cannot make this change (status % to %)', old.status, new.status using errcode = '42501';
    end if;
  else
    raise exception 'not allowed' using errcode = '42501';
  end if;
  new.updated_at := now();
  return new;
end $$;

create trigger t10_guard before insert or update on public.contributions
  for each row execute function private.contributions_guard();

-- Feedback and evidence: always in the caller's own name.
create function private.own_row_guard() returns trigger
language plpgsql set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if private.is_trusted() then return new; end if;
  if me is null then raise exception 'not signed in' using errcode = '42501'; end if;
  if tg_table_name = 'contribution_feedback' then
    if new.user_id is not null and new.user_id <> me then raise exception 'feedback can only be given in your own name' using errcode = '42501'; end if;
    new.user_id := me;
  else
    if new.owner_id is not null and new.owner_id <> me then raise exception 'evidence can only be sent in your own name' using errcode = '42501'; end if;
    new.owner_id := me;
  end if;
  new.created_at := now();
  return new;
end $$;

create trigger t10_guard before insert on public.contribution_feedback for each row execute function private.own_row_guard();
create trigger t10_guard before insert on public.evidence for each row execute function private.own_row_guard();

-- So many new rows (or new revisions) per user and hour. Counted in a log of its own, so deleting rows does not give
-- the quota back, and counted only for a row that was really inserted: a retry that the unique key ignores is free.
-- A refusal is raised in the form PostgREST turns into HTTP 429 with a Retry-After header (SQLSTATE 'PGRST'); the
-- message contains 'rate_limit_exceeded'.
create function private.rate_hit(p_action text, p_limit int) returns void
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); n int; oldest timestamptz; wait_s int;
begin
  if me is null then return; end if;                                   -- the trusted side has no user id
  delete from private.rate_log where user_id = me and at < now() - interval '1 day';
  select count(*), min(at) into n, oldest from private.rate_log where user_id = me and action = p_action and at > now() - interval '1 hour';
  if n >= p_limit then
    wait_s := greatest(1, ceil(extract(epoch from (oldest + interval '1 hour' - now())))::int);
    raise sqlstate 'PGRST' using
      message = json_build_object('code', 'rate_limit_exceeded', 'message', format('rate_limit_exceeded: at most %s %s per hour', p_limit, p_action),
                                  'details', null, 'hint', 'try again later')::text,
      detail = json_build_object('status', 429, 'headers', json_build_object('Retry-After', wait_s::text))::text;
  end if;
  insert into private.rate_log (user_id, action) values (me, p_action);
end $$;

create function private.rate_limit() returns trigger
language plpgsql set search_path = '' as $$
begin
  perform private.rate_hit(tg_argv[0], tg_argv[1]::int);
  return null;
end $$;

create trigger t20_rate after insert on public.contributions for each row execute function private.rate_limit('contributions', '30');
create trigger t20_rate after insert on public.contribution_feedback for each row execute function private.rate_limit('feedback', '120');
create trigger t20_rate after insert on public.evidence for each row execute function private.rate_limit('evidence', '30');

-- A tombstone when a contribution is revoked or deleted (also when its owner's account is deleted).
create function private.write_tombstone() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into private.tombstone_scope (contribution_id, owner_id, scope, lab_id)
    values (old.id, old.owner_id, old.scope, old.lab_id) on conflict (contribution_id) do nothing;
  insert into public.tombstones (contribution_id) values (old.id) on conflict (contribution_id) do nothing;
  return null;
end $$;

create trigger t90_tombstone_revoke after update of status on public.contributions
  for each row when (new.status = 'revoked' and old.status is distinct from 'revoked') execute function private.write_tombstone();
create trigger t90_tombstone_delete after delete on public.contributions
  for each row execute function private.write_tombstone();

-- Functions: closed to everyone, then opened one by one. (Trigger functions need no grant: a trigger runs them.)
revoke all on all functions in schema private from public;
grant execute on function private.learning_json_ok(jsonb, int, int), private.is_lab_member(uuid), private.is_lab_reviewer(uuid),
                          private.is_community_reviewer(), private.can_review(text, uuid), private.can_read_tombstone(uuid),
                          private.is_trusted(), private.rate_hit(text, int) to authenticated;
grant usage on schema private to service_role;
grant execute on all functions in schema private to service_role;

-- ---------------------------------------------------------------------------------------------- row-level security
alter table public.labs                  enable row level security;
alter table public.lab_members           enable row level security;
alter table public.community_reviewers   enable row level security;
alter table public.contributions         enable row level security;
alter table public.contribution_feedback enable row level security;
alter table public.tombstones            enable row level security;
alter table public.evidence              enable row level security;
alter table private.tombstone_scope      enable row level security;     -- no policy: closed to everyone but the definer functions
alter table private.rate_log             enable row level security;

-- Privileges first: nothing for anon, and for authenticated only what a policy below then narrows.
revoke all on public.labs, public.lab_members, public.community_reviewers, public.contributions, public.contribution_feedback,
              public.tombstones, public.evidence from public, anon, authenticated;
revoke all on sequence public.tombstones_version_seq from public, anon, authenticated;
revoke all on private.tombstone_scope, private.rate_log from public, anon, authenticated;
grant select                         on public.labs, public.lab_members, public.community_reviewers, public.tombstones to authenticated;
grant select, insert, delete on public.contributions to authenticated;
-- UPDATE column by column: the review fields and the timestamps can be written by the server's trigger only
grant update (id, owner_id, lab_id, scope, status, kind, data_family, signature, signature_version, schema_version, revision, app_version, payload)
  on public.contributions to authenticated;
grant select, insert, delete         on public.contribution_feedback, public.evidence to authenticated;
grant all on public.labs, public.lab_members, public.community_reviewers, public.contributions, public.contribution_feedback,
             public.tombstones, public.evidence to service_role;          -- the trusted side; this key never leaves trusted machines

-- labs, members, reviewers: read what concerns you; written by the trusted side only (no policy for writing)
create policy labs_read on public.labs for select to authenticated
  using (private.is_lab_member(id));
create policy lab_members_read_own on public.lab_members for select to authenticated
  using (user_id = (select auth.uid()));
create policy community_reviewers_read_own on public.community_reviewers for select to authenticated
  using (user_id = (select auth.uid()));

-- contributions
create policy contributions_read on public.contributions for select to authenticated
  using (owner_id = (select auth.uid())
         or (status = 'approved' and scope = 'community')
         or (status = 'approved' and scope = 'lab' and private.is_lab_member(lab_id))
         or private.can_review(scope, lab_id));

create policy contributions_insert on public.contributions for insert to authenticated
  with check (owner_id = (select auth.uid())
              and status = 'pending' and reviewed_by is null and reviewed_at is null
              and (scope = 'community' or (scope = 'lab' and private.is_lab_member(lab_id))));

create policy contributions_update on public.contributions for update to authenticated
  using (owner_id = (select auth.uid()) or private.can_review(scope, lab_id))
  with check ((owner_id = (select auth.uid())                 -- the owner leaves a row pending or revoked, or untouched after someone else's review
               and (status in ('pending', 'revoked') or (reviewed_by is not null and reviewed_by <> (select auth.uid()))))
              or (owner_id <> (select auth.uid()) and private.can_review(scope, lab_id)));

create policy contributions_delete on public.contributions for delete to authenticated
  using (owner_id = (select auth.uid()));

-- feedback: on an approved contribution you can read and that is not your own; your own rows only; no update
create policy feedback_read_own on public.contribution_feedback for select to authenticated
  using (user_id = (select auth.uid()));
create policy feedback_insert on public.contribution_feedback for insert to authenticated
  with check (user_id = (select auth.uid())
              and exists (select 1 from public.contributions c
                          where c.id = contribution_id and c.status = 'approved' and c.owner_id <> (select auth.uid())));
create policy feedback_delete_own on public.contribution_feedback for delete to authenticated
  using (user_id = (select auth.uid()));

-- tombstones: for those who could read the contribution
create policy tombstones_read on public.tombstones for select to authenticated
  using (private.can_read_tombstone(contribution_id));

-- evidence: write and read your own; the maintainer exports it with trusted credentials, outside the desktop
create policy evidence_read_own on public.evidence for select to authenticated
  using (owner_id = (select auth.uid()));
create policy evidence_insert_own on public.evidence for insert to authenticated
  with check (owner_id = (select auth.uid()));
create policy evidence_delete_own on public.evidence for delete to authenticated
  using (owner_id = (select auth.uid()));

commit;

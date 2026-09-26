-- Core schema: profiles, reward rules, scan events and points, app settings,
-- and the leaderboard.
--
-- Row-level security is on for every table. What a client may not do
-- directly (create a profile, record points, rank everyone) goes through a
-- trigger or a security-definer function that checks the caller itself.
-- Points follow backend/SPECIFICATION.md 5.3: the detector, the recycling
-- policy and the reward stay separate, points come only from a confirmed scan
-- event with an eligible policy result, and each scan event earns at most once.

-- Internal helpers live outside the API schema, so PostgREST can't call them.
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to anon, authenticated, service_role;

-- Keeps updated_at current on every update.
create function private.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Profiles
-- ---------------------------------------------------------------------------

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null
    check (char_length(display_name) between 1 and 40),
  -- Derived from display_name by a trigger; clients never set it.
  avatar_initials text not null default ''
    check (char_length(avatar_initials) <= 2),
  -- Avatar gradient, as 0xRRGGBB integers from the app's palette.
  avatar_top integer not null default 3450978
    check (avatar_top between 0 and 16777215),
  avatar_bottom integer not null default 1864770
    check (avatar_bottom between 0 and 16777215),
  role text not null default 'user' check (role in ('user', 'admin')),
  banned_at timestamptz,
  terms_accepted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.profiles is
  'One row per auth user: public name and avatar, role, ban and terms state.';

-- "Truong Son" -> "TS", "Recycler 4821" -> "R".
create function private.initials_for(name text)
returns text
language sql
immutable
set search_path = ''
as $$
  select upper(
    coalesce(left(words[1], 1), '')
    || case when words[2] ~ '^[[:alpha:]]' then left(words[2], 1) else '' end
  )
  from (select regexp_split_to_array(btrim(name), '\s+') as words) as split;
$$;

create function private.prepare_profile()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.display_name := regexp_replace(btrim(new.display_name), '\s+', ' ', 'g');
  new.avatar_initials := private.initials_for(new.display_name);
  return new;
end;
$$;

create trigger prepare_profile
  before insert or update of display_name on public.profiles
  for each row execute function private.prepare_profile();

create trigger touch_updated_at
  before update on public.profiles
  for each row execute function private.touch_updated_at();

-- Every new auth user (guests included) gets a profile with a friendly
-- generated name, e.g. "Recycler 4821", and one of the app's avatar gradients.
-- Names from the sign-in provider are ignored on purpose: nothing personal is
-- shown until the user picks a name.
create function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  palette constant integer[][] := array[
    [3450978, 1864770], [10189531, 7229368], [14721594, 11890194],
    [4174782, 949382], [6003672, 4091824], [14711451, 11553390],
    [8364891, 5601082], [14256991, 11033140]
  ];
  pick integer := 1 + floor(random() * 8)::integer;
begin
  insert into public.profiles (id, display_name, avatar_top, avatar_bottom)
  values (
    new.id,
    'Recycler ' || (1000 + floor(random() * 9000)::integer)::text,
    palette[pick][1],
    palette[pick][2]
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_user();

-- True when the caller is a signed-in (not guest), unbanned admin. Guests can
-- never act as admins, even if their profile says so.
create function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) = false
    and exists (
      select 1 from public.profiles
      where id = auth.uid() and role = 'admin' and banned_at is null
    );
$$;

revoke execute on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

alter table public.profiles enable row level security;

-- Names and avatars are public to everyone using the app.
create policy "Profiles are visible to signed-in users"
  on public.profiles for select
  to authenticated
  using (true);

-- Users edit only their own name, and only while not banned. Column grants
-- below stop them from touching role, ban or terms fields.
create policy "Users update their own profile"
  on public.profiles for update
  to authenticated
  using (id = (select auth.uid()) and banned_at is null)
  with check (id = (select auth.uid()));

revoke all on table public.profiles from anon, authenticated;
grant select on table public.profiles to authenticated;
grant update (display_name) on table public.profiles to authenticated;

-- ---------------------------------------------------------------------------
-- App settings (a single row)
-- ---------------------------------------------------------------------------

create table public.app_settings (
  id boolean primary key default true check (id),
  -- Show the app's built-in sample people, posts and map spots.
  show_samples boolean not null default true,
  -- Most points one user can earn per Vietnam calendar day.
  daily_point_cap integer not null default 200
    check (daily_point_cap between 0 and 100000),
  -- Distinct reports that hide a post or reply until an admin reviews it.
  report_threshold integer not null default 3
    check (report_threshold between 1 and 1000),
  updated_at timestamptz not null default now(),
  updated_by uuid references auth.users (id) on delete set null
);

comment on table public.app_settings is
  'Server settings the admin page edits. Exactly one row.';

insert into public.app_settings default values;

create function private.stamp_settings()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  new.updated_by := auth.uid();
  return new;
end;
$$;

create trigger stamp_settings
  before update on public.app_settings
  for each row execute function private.stamp_settings();

alter table public.app_settings enable row level security;

create policy "Anyone can read the settings"
  on public.app_settings for select
  to anon, authenticated
  using (true);

create policy "Admins change the settings"
  on public.app_settings for update
  to authenticated
  using ((select public.is_admin()))
  with check ((select public.is_admin()));

revoke all on table public.app_settings from anon, authenticated;
grant select on table public.app_settings to anon, authenticated;
grant update (show_samples, daily_point_cap, report_threshold)
  on table public.app_settings to authenticated;

-- ---------------------------------------------------------------------------
-- Reward rules (versioned) and scan events
-- ---------------------------------------------------------------------------

-- Point values per canonical label under a recycling-policy version. A label
-- whose group depends on the user's answer (what the cup is made of, whether
-- the cardboard is clean) has one row per answer (choice_id) and no '' row.
create table public.reward_rules (
  policy_version text not null check (char_length(policy_version) between 1 and 40),
  label text not null check (label ~ '^[a-z_]{1,40}$'),
  choice_id text not null default '' check (choice_id ~ '^[a-z_]{0,40}$'),
  disposal_group text not null
    check (disposal_group in ('recyclable', 'food_waste', 'other', 'hazardous')),
  points integer not null check (points >= 0),
  eligible boolean not null,
  created_at timestamptz not null default now(),
  primary key (policy_version, label, choice_id)
);

comment on table public.reward_rules is
  'Versioned point values per canonical label and confirmation answer.';

-- Today's values, matching RecyclingPolicy in the app (policy hanoi-2026.1):
-- 20 points for a recyclable result, 10 for other waste.
insert into public.reward_rules (policy_version, label, choice_id, disposal_group, points, eligible) values
  ('hanoi-2026.1', 'plastic_bottle', '', 'recyclable', 20, true),
  ('hanoi-2026.1', 'glass_container', '', 'recyclable', 20, true),
  ('hanoi-2026.1', 'metal_can', '', 'recyclable', 20, true),
  ('hanoi-2026.1', 'cardboard', 'clean', 'recyclable', 20, true),
  ('hanoi-2026.1', 'cardboard', 'soiled', 'other', 10, true),
  ('hanoi-2026.1', 'plastic_bag', '', 'other', 10, true),
  ('hanoi-2026.1', 'disposable_cup', 'paper', 'recyclable', 20, true),
  ('hanoi-2026.1', 'disposable_cup', 'plastic', 'recyclable', 20, true),
  ('hanoi-2026.1', 'disposable_cup', 'foam', 'other', 10, true),
  ('hanoi-2026.1', 'styrofoam', '', 'other', 10, true);

alter table public.reward_rules enable row level security;

create policy "Anyone can read the reward rules"
  on public.reward_rules for select
  to anon, authenticated
  using (true);

revoke all on table public.reward_rules from anon, authenticated;
grant select on table public.reward_rules to anon, authenticated;

-- One row per scan event the app reports. The id is the app's scan event UUID,
-- so the same event can never be recorded (or rewarded) twice.
create table public.scan_events (
  id uuid primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  label text not null check (label ~ '^[a-z_]{1,40}$'),
  choice_id text check (choice_id ~ '^[a-z_]{1,40}$'),
  policy_version text not null check (char_length(policy_version) between 1 and 40),
  confirmed boolean not null,
  disposal_group text
    check (disposal_group in ('recyclable', 'food_waste', 'other', 'hazardous')),
  points_awarded integer not null default 0 check (points_awarded >= 0),
  -- 'already_awarded' is only ever a response, never a stored state.
  reward_state text not null
    check (reward_state in ('eligible', 'ineligible', 'confirmation_required')),
  reason_code text not null,
  scanned_at timestamptz not null,
  -- The Vietnam calendar day of the scan, for the daily cap and leaderboards.
  scanned_on date generated always as ((scanned_at at time zone 'Asia/Ho_Chi_Minh')::date) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.scan_events is
  'Scan events and the points each earned. Written only by award_scan().';

create index scan_events_user_day_idx on public.scan_events (user_id, scanned_on);
create index scan_events_day_idx on public.scan_events (scanned_on) where points_awarded > 0;

create trigger touch_updated_at
  before update on public.scan_events
  for each row execute function private.touch_updated_at();

alter table public.scan_events enable row level security;

create policy "Users read their own scan events"
  on public.scan_events for select
  to authenticated
  using (user_id = (select auth.uid()));

revoke all on table public.scan_events from anon, authenticated;
grant select on table public.scan_events to authenticated;

-- Records a scan event and awards its points, the only way points are added.
-- Returns the reward output of SPECIFICATION.md 5.3 as JSON:
--   {"state": "eligible" | "ineligible" | "already_awarded" | "confirmation_required",
--    "points": 20, "reason_code": "sorted_recyclable", "scan_event_id": "..."}
-- p_choice_id is the user's answer for labels that need one ("clean", "paper").
-- p_scanned_at is when the scan happened on the phone (it may sync later); it
-- is clamped to the last 7 days. The daily cap counts Vietnam calendar days.
-- A call for an event that was waiting for confirmation evaluates it again;
-- any other repeat returns the stored result without awarding anything.
create function public.award_scan(
  p_scan_event_id uuid,
  p_label text,
  p_policy_version text,
  p_confirmed boolean,
  p_choice_id text default null,
  p_scanned_at timestamptz default null
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_existing public.scan_events;
  v_rule public.reward_rules;
  v_choice text := nullif(btrim(coalesce(p_choice_id, '')), '');
  v_label text := btrim(coalesce(p_label, ''));
  v_scanned_at timestamptz :=
    least(greatest(coalesce(p_scanned_at, now()), now() - interval '7 days'), now());
  v_state text;
  v_reason text;
  v_points integer := 0;
  v_group text;
  v_cap integer;
  v_day_total integer;
begin
  if v_uid is null then
    raise exception 'Sign in to record scans' using errcode = '42501';
  end if;
  if p_scan_event_id is null or v_label = '' or p_policy_version is null or p_confirmed is null then
    raise exception 'A scan needs an id, a label, a policy version and a confirmation flag'
      using errcode = '22023';
  end if;
  if v_label !~ '^[a-z_]{1,40}$' or (v_choice is not null and v_choice !~ '^[a-z_]{1,40}$') then
    raise exception 'Unknown label format' using errcode = '22023';
  end if;

  -- One award at a time per user, so parallel calls can't beat the daily cap.
  perform 1 from public.profiles where id = v_uid for update;
  if not found then
    raise exception 'No profile for this user' using errcode = '42501';
  end if;

  select * into v_existing from public.scan_events where id = p_scan_event_id;
  if found then
    if v_existing.user_id <> v_uid then
      return jsonb_build_object('state', 'ineligible', 'points', 0,
        'reason_code', 'scan_event_taken', 'scan_event_id', p_scan_event_id);
    elsif v_existing.reward_state = 'eligible' then
      return jsonb_build_object('state', 'already_awarded', 'points', v_existing.points_awarded,
        'reason_code', 'already_awarded', 'scan_event_id', p_scan_event_id);
    elsif v_existing.reward_state = 'ineligible' then
      return jsonb_build_object('state', 'ineligible', 'points', 0,
        'reason_code', v_existing.reason_code, 'scan_event_id', p_scan_event_id);
    end if;
    -- Still waiting for confirmation: evaluate this call below.
  end if;

  if not p_confirmed then
    v_state := 'confirmation_required';
    v_reason := 'not_confirmed';
  else
    select * into v_rule from public.reward_rules r
    where r.policy_version = p_policy_version and r.label = v_label
      and r.choice_id = coalesce(v_choice, '');
    if not found and v_choice is not null then
      -- An answer for a label that doesn't need one.
      select * into v_rule from public.reward_rules r
      where r.policy_version = p_policy_version and r.label = v_label and r.choice_id = '';
    end if;

    if v_rule.label is null then
      if exists (select 1 from public.reward_rules r
                 where r.policy_version = p_policy_version and r.label = v_label) then
        v_state := 'confirmation_required';
        v_reason := 'confirmation_required';
      elsif not exists (select 1 from public.reward_rules r
                        where r.policy_version = p_policy_version) then
        v_state := 'ineligible';
        v_reason := 'unsupported_policy';
      else
        v_state := 'ineligible';
        v_reason := 'unsupported_label';
      end if;
    elsif not v_rule.eligible or v_rule.points = 0 then
      v_state := 'ineligible';
      v_reason := 'no_reward_for_group';
      v_group := v_rule.disposal_group;
    else
      v_group := v_rule.disposal_group;
      select s.daily_point_cap into v_cap from public.app_settings s;
      select coalesce(sum(e.points_awarded), 0) into v_day_total
      from public.scan_events e
      where e.user_id = v_uid
        and e.scanned_on = (v_scanned_at at time zone 'Asia/Ho_Chi_Minh')::date;
      if v_day_total + v_rule.points > coalesce(v_cap, 200) then
        v_state := 'ineligible';
        v_reason := 'daily_cap_reached';
      else
        v_state := 'eligible';
        v_reason := 'sorted_' || v_rule.disposal_group;
        v_points := v_rule.points;
      end if;
    end if;
  end if;

  insert into public.scan_events as e (
    id, user_id, label, choice_id, policy_version, confirmed, disposal_group,
    points_awarded, reward_state, reason_code, scanned_at
  ) values (
    p_scan_event_id, v_uid, v_label, v_choice, p_policy_version, p_confirmed, v_group,
    v_points, v_state, v_reason, v_scanned_at
  )
  on conflict (id) do update set
    label = excluded.label,
    choice_id = excluded.choice_id,
    policy_version = excluded.policy_version,
    confirmed = excluded.confirmed,
    disposal_group = excluded.disposal_group,
    points_awarded = excluded.points_awarded,
    reward_state = excluded.reward_state,
    reason_code = excluded.reason_code,
    scanned_at = excluded.scanned_at
  where e.user_id = v_uid and e.reward_state = 'confirmation_required';

  return jsonb_build_object('state', v_state, 'points', v_points,
    'reason_code', v_reason, 'scan_event_id', p_scan_event_id);
end;
$$;

revoke execute on function public.award_scan(uuid, text, text, boolean, text, timestamptz) from public, anon;
grant execute on function public.award_scan(uuid, text, text, boolean, text, timestamptz) to authenticated;

-- ---------------------------------------------------------------------------
-- Leaderboard
-- ---------------------------------------------------------------------------

-- The top p_limit recyclers by points for p_period ('month': this Vietnam
-- calendar month, 'all': all time), highest first, then the caller's own row
-- if it isn't among them. Banned users are left out. Ties share a rank.
create function public.leaderboard(p_period text default 'month', p_limit integer default 10)
returns table (
  rank bigint,
  user_id uuid,
  display_name text,
  avatar_initials text,
  avatar_top integer,
  avatar_bottom integer,
  points bigint,
  is_me boolean
)
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_since date;
  v_limit integer := least(greatest(coalesce(p_limit, 10), 1), 100);
begin
  if v_uid is null then
    raise exception 'Sign in to see the leaderboard' using errcode = '42501';
  end if;
  if p_period = 'month' then
    v_since := date_trunc('month', now() at time zone 'Asia/Ho_Chi_Minh')::date;
  elsif p_period = 'all' then
    v_since := '-infinity'::date;
  else
    raise exception 'Period must be month or all' using errcode = '22023';
  end if;

  return query
  with totals as (
    select e.user_id, sum(e.points_awarded)::bigint as points
    from public.scan_events e
    where e.points_awarded > 0 and e.scanned_on >= v_since
    group by e.user_id
  ),
  ranked as (
    select rank() over (order by t.points desc) as rank,
      p.id, p.display_name, p.avatar_initials, p.avatar_top, p.avatar_bottom, t.points
    from totals t
    join public.profiles p on p.id = t.user_id
    where p.banned_at is null
  ),
  top as (
    select * from ranked r order by r.rank, r.display_name, r.id limit v_limit
  ),
  me as (
    select 1 + (select count(*) from ranked r where r.points > coalesce(t.points, 0)) as rank,
      p.id, p.display_name, p.avatar_initials, p.avatar_top, p.avatar_bottom,
      coalesce(t.points, 0)::bigint as points
    from public.profiles p
    left join totals t on t.user_id = p.id
    where p.id = v_uid and p.banned_at is null
      and not exists (select 1 from top where top.id = v_uid)
  )
  select x.rank, x.id, x.display_name, x.avatar_initials, x.avatar_top, x.avatar_bottom,
    x.points, x.id = v_uid
  from (
    select top.*, 0 as part from top
    union all
    select me.*, 1 as part from me
  ) x
  order by x.part, x.rank, x.display_name, x.id;
end;
$$;

revoke execute on function public.leaderboard(text, integer) from public, anon;
grant execute on function public.leaderboard(text, integer) to authenticated;

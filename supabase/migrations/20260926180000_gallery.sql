-- Community Gallery: posts, replies, likes, saves, photos, and moderation
-- (reports, blocks, auto-hide, a word filter, bans and community terms).
--
-- What each user may see and do is enforced here with row-level security:
--   * posts and replies show unless removed, hidden (except to their author),
--     written by a banned user, or written by someone the viewer blocked;
--   * only users who accepted the community terms and aren't banned can post
--     or reply, and banned users can't like;
--   * likes, saves, reports and blocks are private to the user who made them;
--   * counts are kept by the database, never sent by the app.

-- ---------------------------------------------------------------------------
-- Blocks
-- ---------------------------------------------------------------------------

create table public.blocks (
  blocker_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  blocked_id uuid not null references public.profiles (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blocker_id, blocked_id),
  check (blocker_id <> blocked_id)
);

create index blocks_blocked_idx on public.blocks (blocked_id);

alter table public.blocks enable row level security;

create policy "Users see their own blocks"
  on public.blocks for select to authenticated
  using (blocker_id = (select auth.uid()));
create policy "Users block others"
  on public.blocks for insert to authenticated
  with check (blocker_id = (select auth.uid()));
create policy "Users unblock"
  on public.blocks for delete to authenticated
  using (blocker_id = (select auth.uid()));

revoke all on table public.blocks from anon, authenticated;
grant select, delete on table public.blocks to authenticated;
grant insert (blocked_id) on table public.blocks to authenticated;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

-- The caller may post, reply and like: accepted the terms and isn't banned.
create function private.can_contribute()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and banned_at is null and terms_accepted_at is not null
  );
$$;

-- The user exists and isn't banned (their content may show).
create function private.is_active_user(p_user uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.profiles where id = p_user and banned_at is null);
$$;

-- The caller blocked this user.
create function private.blocked_by_me(p_user uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.blocks where blocker_id = auth.uid() and blocked_id = p_user
  );
$$;

grant execute on function private.can_contribute() to authenticated;
grant execute on function private.is_active_user(uuid) to authenticated;
grant execute on function private.blocked_by_me(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- Word filter (a basic English and Vietnamese list; add rows to extend it)
-- ---------------------------------------------------------------------------

create table private.blocked_words (
  word text primary key check (word = lower(word) and word !~ '[^[:alpha:] ]')
);

-- Vietnamese words keep their diacritics on purpose: without them, "lồn"
-- would become "lon", which is also a drink can.
insert into private.blocked_words (word) values
  ('fuck'), ('fucking'), ('motherfucker'), ('shit'), ('bitch'), ('cunt'), ('dick'),
  ('pussy'), ('asshole'), ('bastard'), ('slut'), ('whore'), ('nigger'), ('faggot'),
  ('retard'),
  ('địt'), ('đụ'), ('lồn'), ('cặc'), ('buồi'), ('đéo'), ('đĩ'), ('cứt'), ('đcm'),
  ('đmm'), ('vcl'), ('vkl'), ('clm'), ('đm');

-- True when the text contains a blocked word as a whole word, any case.
create function private.has_blocked_word(p_text text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(p_text, '') <> '' and exists (
    select 1 from private.blocked_words w
    where lower(p_text) ~ ('(^|[^[:alnum:]])' || w.word || '($|[^[:alnum:]])')
  );
$$;

-- Rejects posts, replies and names with blocked words. The app shows a
-- friendly message for the 'content_not_allowed' error.
create function private.check_words()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_text text;
begin
  -- One statement per table: NEW only has that table's columns.
  if tg_table_name = 'posts' then
    v_text := coalesce(new.title, '') || ' ' || coalesce(new.body, '');
  elsif tg_table_name = 'replies' then
    v_text := new.body;
  else
    v_text := new.display_name;
  end if;
  if private.has_blocked_word(v_text) then
    raise exception 'content_not_allowed' using errcode = 'P0001', hint = 'word_filter';
  end if;
  return new;
end;
$$;

create trigger check_words
  before insert or update of display_name on public.profiles
  for each row execute function private.check_words();

-- ---------------------------------------------------------------------------
-- Community terms
-- ---------------------------------------------------------------------------

-- Records that the caller accepted the community terms (App Store
-- guideline 1.2). Needed once before the first post or reply.
create function public.accept_terms()
returns timestamptz
language sql
security definer
set search_path = ''
as $$
  update public.profiles
  set terms_accepted_at = coalesce(terms_accepted_at, now())
  where id = auth.uid()
  returning terms_accepted_at;
$$;

revoke execute on function public.accept_terms() from public, anon;
grant execute on function public.accept_terms() to authenticated;

-- ---------------------------------------------------------------------------
-- Posts and replies
-- ---------------------------------------------------------------------------

create table public.posts (
  id uuid primary key default gen_random_uuid(),
  author_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  title text check (char_length(title) between 1 and 60),
  body text not null default '' check (char_length(body) <= 2000),
  material text check (material in ('plastic', 'paper', 'glass', 'metal')),
  -- A photo in the post-images bucket, always inside the author's folder.
  image_path text check (image_path ~ '^[0-9a-f-]{36}/[A-Za-z0-9._-]{1,100}$'),
  like_count integer not null default 0 check (like_count >= 0),
  reply_count integer not null default 0 check (reply_count >= 0),
  save_count integer not null default 0 check (save_count >= 0),
  -- Hidden by reports or an admin until reviewed; the author still sees it.
  hidden_at timestamptz,
  -- Removed by an admin; nobody but admins sees it any more.
  removed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (btrim(body) <> '' or image_path is not null or removed_at is not null),
  check (image_path is null or split_part(image_path, '/', 1) = author_id::text)
);

create index posts_feed_idx on public.posts (created_at desc) where removed_at is null;
create index posts_author_idx on public.posts (author_id);

create trigger touch_updated_at
  before update on public.posts
  for each row execute function private.touch_updated_at();
create trigger check_words
  before insert or update of title, body on public.posts
  for each row execute function private.check_words();

create table public.replies (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.posts (id) on delete cascade,
  author_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  body text not null default '' check (char_length(body) <= 1000),
  image_path text check (image_path ~ '^[0-9a-f-]{36}/[A-Za-z0-9._-]{1,100}$'),
  hidden_at timestamptz,
  removed_at timestamptz,
  created_at timestamptz not null default now(),
  check (btrim(body) <> '' or image_path is not null or removed_at is not null),
  check (image_path is null or split_part(image_path, '/', 1) = author_id::text)
);

create index replies_post_idx on public.replies (post_id, created_at);
create index replies_author_idx on public.replies (author_id);

create trigger check_words
  before insert or update of body on public.replies
  for each row execute function private.check_words();

alter table public.posts enable row level security;
alter table public.replies enable row level security;

create policy "Visible posts"
  on public.posts for select to authenticated
  using (
    (removed_at is null
     and (hidden_at is null or author_id = (select auth.uid()))
     and private.is_active_user(author_id)
     and not private.blocked_by_me(author_id))
    or (select public.is_admin())
  );
create policy "Members post"
  on public.posts for insert to authenticated
  with check (author_id = (select auth.uid()) and (select private.can_contribute()));
create policy "Authors and admins delete posts"
  on public.posts for delete to authenticated
  using (author_id = (select auth.uid()) or (select public.is_admin()));

-- A reply shows when its post shows (the subquery applies the posts policy).
create policy "Visible replies"
  on public.replies for select to authenticated
  using (
    (removed_at is null
     and (hidden_at is null or author_id = (select auth.uid()))
     and private.is_active_user(author_id)
     and not private.blocked_by_me(author_id)
     and exists (select 1 from public.posts p where p.id = post_id))
    or (select public.is_admin())
  );
create policy "Members reply to visible posts"
  on public.replies for insert to authenticated
  with check (
    author_id = (select auth.uid())
    and (select private.can_contribute())
    and exists (select 1 from public.posts p where p.id = post_id and p.hidden_at is null)
  );
create policy "Authors and admins delete replies"
  on public.replies for delete to authenticated
  using (author_id = (select auth.uid()) or (select public.is_admin()));

revoke all on table public.posts from anon, authenticated;
grant select, delete on table public.posts to authenticated;
grant insert (title, body, material, image_path) on table public.posts to authenticated;

revoke all on table public.replies from anon, authenticated;
grant select, delete on table public.replies to authenticated;
grant insert (post_id, body, image_path) on table public.replies to authenticated;

-- ---------------------------------------------------------------------------
-- Likes and saves (private rows; counts kept on the post)
-- ---------------------------------------------------------------------------

create table public.likes (
  post_id uuid not null references public.posts (id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);

create table public.saves (
  post_id uuid not null references public.posts (id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);

create index likes_user_idx on public.likes (user_id);
create index saves_user_idx on public.saves (user_id);

alter table public.likes enable row level security;
alter table public.saves enable row level security;

create policy "Users see their own likes"
  on public.likes for select to authenticated
  using (user_id = (select auth.uid()));
-- Liking needs no terms (only posting and replying do), but banned users can't.
create policy "Users like visible posts"
  on public.likes for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and (select private.is_active_user((select auth.uid())))
    and exists (select 1 from public.posts p where p.id = post_id)
  );
create policy "Users unlike"
  on public.likes for delete to authenticated
  using (user_id = (select auth.uid()));

create policy "Users see their own saves"
  on public.saves for select to authenticated
  using (user_id = (select auth.uid()));
create policy "Users save visible posts"
  on public.saves for insert to authenticated
  with check (user_id = (select auth.uid()) and exists (select 1 from public.posts p where p.id = post_id));
create policy "Users unsave"
  on public.saves for delete to authenticated
  using (user_id = (select auth.uid()));

revoke all on table public.likes from anon, authenticated;
grant select, delete on table public.likes to authenticated;
grant insert (post_id) on table public.likes to authenticated;

revoke all on table public.saves from anon, authenticated;
grant select, delete on table public.saves to authenticated;
grant insert (post_id) on table public.saves to authenticated;

-- Keeps like_count, save_count and reply_count on posts.
create function private.count_on_post()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_post uuid := case when tg_op = 'INSERT' then new.post_id else old.post_id end;
  v_step integer := case when tg_op = 'INSERT' then 1 else -1 end;
begin
  if tg_table_name = 'likes' then
    update public.posts set like_count = greatest(like_count + v_step, 0) where id = v_post;
  elsif tg_table_name = 'saves' then
    update public.posts set save_count = greatest(save_count + v_step, 0) where id = v_post;
  else
    update public.posts set reply_count = greatest(reply_count + v_step, 0) where id = v_post;
  end if;
  return null;
end;
$$;

create trigger count_on_post after insert or delete on public.likes
  for each row execute function private.count_on_post();
create trigger count_on_post after insert or delete on public.saves
  for each row execute function private.count_on_post();
create trigger count_on_post after insert or delete on public.replies
  for each row execute function private.count_on_post();

-- ---------------------------------------------------------------------------
-- Reports and auto-hide
-- ---------------------------------------------------------------------------

create table public.reports (
  id uuid primary key default gen_random_uuid(),
  reporter_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  post_id uuid references public.posts (id) on delete cascade,
  reply_id uuid references public.replies (id) on delete cascade,
  reported_user_id uuid references public.profiles (id) on delete cascade,
  reason text check (char_length(reason) <= 300),
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by uuid references public.profiles (id) on delete set null,
  check (num_nonnulls(post_id, reply_id, reported_user_id) = 1)
);

-- One report per person per target, so the threshold counts distinct people.
create unique index reports_post_once on public.reports (reporter_id, post_id) where post_id is not null;
create unique index reports_reply_once on public.reports (reporter_id, reply_id) where reply_id is not null;
create unique index reports_user_once on public.reports (reporter_id, reported_user_id)
  where reported_user_id is not null;
create index reports_open_idx on public.reports (created_at) where resolved_at is null;

alter table public.reports enable row level security;

create policy "Users see their own reports"
  on public.reports for select to authenticated
  using (reporter_id = (select auth.uid()) or (select public.is_admin()));
create policy "Users report"
  on public.reports for insert to authenticated
  with check (reporter_id = (select auth.uid()));

revoke all on table public.reports from anon, authenticated;
grant select on table public.reports to authenticated;
grant insert (post_id, reply_id, reported_user_id, reason) on table public.reports to authenticated;

-- Hides a post or reply once enough different people reported it and an
-- admin hasn't reviewed those reports yet.
create function private.hide_reported()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_threshold integer;
begin
  select report_threshold into v_threshold from public.app_settings;
  v_threshold := coalesce(v_threshold, 3);
  if new.post_id is not null
     and (select count(*) from public.reports r
          where r.post_id = new.post_id and r.resolved_at is null) >= v_threshold then
    update public.posts set hidden_at = coalesce(hidden_at, now()) where id = new.post_id;
  elsif new.reply_id is not null
     and (select count(*) from public.reports r
          where r.reply_id = new.reply_id and r.resolved_at is null) >= v_threshold then
    update public.replies set hidden_at = coalesce(hidden_at, now()) where id = new.reply_id;
  end if;
  return null;
end;
$$;

create trigger hide_reported after insert on public.reports
  for each row execute function private.hide_reported();

-- ---------------------------------------------------------------------------
-- Admin moderation (the admin page calls these; each checks is_admin())
-- ---------------------------------------------------------------------------

create function private.require_admin()
returns void
language plpgsql
stable
set search_path = ''
as $$
begin
  if not public.is_admin() then
    raise exception 'Admins only' using errcode = '42501';
  end if;
end;
$$;

grant execute on function private.require_admin() to authenticated;

-- Hides ('hide'), restores ('restore') or removes ('remove') a post or reply
-- (p_kind 'post' or 'reply'). Restoring and removing close its open reports.
-- Returns the photo path of removed content, so the admin page can delete the
-- file through the Storage API.
create function public.admin_moderate(p_kind text, p_id uuid, p_action text)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_image text;
begin
  perform private.require_admin();
  if p_kind not in ('post', 'reply') or p_action not in ('hide', 'restore', 'remove') then
    raise exception 'Unknown kind or action' using errcode = '22023';
  end if;

  if p_kind = 'post' then
    select image_path into v_image from public.posts where id = p_id;
    if not found then raise exception 'No such post' using errcode = 'P0002'; end if;
    update public.posts set
      hidden_at = case p_action when 'hide' then coalesce(hidden_at, now())
                                when 'restore' then null else hidden_at end,
      removed_at = case p_action when 'remove' then coalesce(removed_at, now())
                                 when 'restore' then null else removed_at end,
      image_path = case p_action when 'remove' then null else image_path end
    where id = p_id;
  else
    select image_path into v_image from public.replies where id = p_id;
    if not found then raise exception 'No such reply' using errcode = 'P0002'; end if;
    update public.replies set
      hidden_at = case p_action when 'hide' then coalesce(hidden_at, now())
                                when 'restore' then null else hidden_at end,
      removed_at = case p_action when 'remove' then coalesce(removed_at, now())
                                 when 'restore' then null else removed_at end,
      image_path = case p_action when 'remove' then null else image_path end
    where id = p_id;
  end if;

  if p_action in ('restore', 'remove') then
    update public.reports set resolved_at = now(), resolved_by = auth.uid()
    where resolved_at is null
      and ((p_kind = 'post' and post_id = p_id) or (p_kind = 'reply' and reply_id = p_id));
  end if;
  return case when p_action = 'remove' then v_image end;
end;
$$;

-- Bans or unbans a user. Banned users can't post, reply or like, their
-- content stops showing, and they leave the leaderboard.
create function public.admin_set_banned(p_user uuid, p_banned boolean)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform private.require_admin();
  if p_user = auth.uid() then
    raise exception 'Admins can''t ban themselves' using errcode = '22023';
  end if;
  update public.profiles
  set banned_at = case when p_banned then coalesce(banned_at, now()) end
  where id = p_user;
  if not found then raise exception 'No such user' using errcode = 'P0002'; end if;
  if not p_banned then
    return;
  end if;
  update public.reports set resolved_at = now(), resolved_by = auth.uid()
  where resolved_at is null and reported_user_id = p_user;
end;
$$;

-- Closes the open reports on a target without changing it ("looks fine").
create function public.admin_dismiss_reports(p_kind text, p_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform private.require_admin();
  update public.reports set resolved_at = now(), resolved_by = auth.uid()
  where resolved_at is null
    and ((p_kind = 'post' and post_id = p_id)
      or (p_kind = 'reply' and reply_id = p_id)
      or (p_kind = 'user' and reported_user_id = p_id));
end;
$$;

-- The open reports, one row per reported post, reply or user, most reported
-- first, with enough of the target to judge it.
create function public.admin_report_queue()
returns table (
  kind text,
  target_id uuid,
  reports bigint,
  last_reported_at timestamptz,
  reasons text[],
  author_id uuid,
  author_name text,
  author_banned boolean,
  title text,
  body text,
  image_path text,
  hidden boolean,
  removed boolean
)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  perform private.require_admin();
  return query
  with open_reports as (
    select
      case when r.post_id is not null then 'post'
           when r.reply_id is not null then 'reply' else 'user' end as kind,
      coalesce(r.post_id, r.reply_id, r.reported_user_id) as target_id,
      r.reason, r.created_at
    from public.reports r
    where r.resolved_at is null
  ),
  grouped as (
    select o.kind, o.target_id, count(*) as reports, max(o.created_at) as last_reported_at,
      array_remove(array_agg(o.reason order by o.created_at desc), null) as reasons
    from open_reports o
    group by o.kind, o.target_id
  )
  select g.kind, g.target_id, g.reports, g.last_reported_at, g.reasons,
    coalesce(p.author_id, rp.author_id, g.target_id),
    pr.display_name, pr.banned_at is not null,
    p.title, coalesce(p.body, rp.body),
    coalesce(p.image_path, rp.image_path),
    coalesce(p.hidden_at, rp.hidden_at) is not null,
    coalesce(p.removed_at, rp.removed_at) is not null
  from grouped g
  left join public.posts p on g.kind = 'post' and p.id = g.target_id
  left join public.replies rp on g.kind = 'reply' and rp.id = g.target_id
  left join public.profiles pr on pr.id = coalesce(p.author_id, rp.author_id, g.target_id)
  order by g.reports desc, g.last_reported_at desc;
end;
$$;

revoke execute on function public.admin_moderate(text, uuid, text) from public, anon;
revoke execute on function public.admin_set_banned(uuid, boolean) from public, anon;
revoke execute on function public.admin_dismiss_reports(text, uuid) from public, anon;
revoke execute on function public.admin_report_queue() from public, anon;
grant execute on function public.admin_moderate(text, uuid, text) to authenticated;
grant execute on function public.admin_set_banned(uuid, boolean) to authenticated;
grant execute on function public.admin_dismiss_reports(text, uuid) to authenticated;
grant execute on function public.admin_report_queue() to authenticated;

-- ---------------------------------------------------------------------------
-- Photos: the post-images bucket
-- ---------------------------------------------------------------------------

-- Public reads (photos show without signed URLs); images only, 5 MB each.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('post-images', 'post-images', true, 5242880,
        array['image/jpeg', 'image/png', 'image/heic', 'image/webp'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Users upload only into their own "<user id>/" folder, and only while they
-- may post.
create policy "Members upload their own post images"
  on storage.objects for insert to authenticated
  with check (
    bucket_id = 'post-images'
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and (select private.can_contribute())
  );
create policy "Signed-in users read post images"
  on storage.objects for select to authenticated
  using (bucket_id = 'post-images');
create policy "Owners and admins delete post images"
  on storage.objects for delete to authenticated
  using (
    bucket_id = 'post-images'
    and ((storage.foldername(name))[1] = (select auth.uid())::text or (select public.is_admin()))
  );

-- Deleting a post removes its photos, including other people's reply photos,
-- so its author may delete those too (before the post itself goes).
create policy "Post authors delete reply images on their posts"
  on storage.objects for delete to authenticated
  using (
    bucket_id = 'post-images'
    and exists (
      select 1 from public.replies r
      join public.posts p on p.id = r.post_id
      where r.image_path = name and p.author_id = (select auth.uid())
    )
  );

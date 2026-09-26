-- Push notifications: the phones' APNs tokens, and an outbox that triggers
-- fill (a reply or like on your post, an admin announcement) and the
-- send-push Edge Function drains. Weekly goal and streak reminders are local
-- notifications scheduled by the app; they never touch the server.

create table public.device_tokens (
  token text primary key check (token ~ '^[0-9a-f]{32,200}$'),
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  -- APNs environment the token belongs to: development builds use the sandbox.
  environment text not null default 'production' check (environment in ('sandbox', 'production')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index device_tokens_user_idx on public.device_tokens (user_id);

create trigger touch_updated_at
  before update on public.device_tokens
  for each row execute function private.touch_updated_at();

alter table public.device_tokens enable row level security;

create policy "Users see their own device tokens"
  on public.device_tokens for select to authenticated
  using (user_id = (select auth.uid()));
create policy "Users register their own device tokens"
  on public.device_tokens for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy "Users update their own device tokens"
  on public.device_tokens for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));
create policy "Users remove their own device tokens"
  on public.device_tokens for delete to authenticated
  using (user_id = (select auth.uid()));

revoke all on table public.device_tokens from anon, authenticated;
grant select, delete on table public.device_tokens to authenticated;
grant insert (token, environment) on table public.device_tokens to authenticated;
grant update (environment) on table public.device_tokens to authenticated;

-- Registers this phone's token for the caller. A token that belonged to
-- another account on the same phone moves to the caller.
create function public.register_device(p_token text, p_environment text default 'production')
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'Sign in first' using errcode = '42501';
  end if;
  insert into public.device_tokens (token, user_id, environment)
  values (lower(p_token), auth.uid(), coalesce(p_environment, 'production'))
  on conflict (token) do update
    set user_id = excluded.user_id, environment = excluded.environment, updated_at = now();
end;
$$;

revoke execute on function public.register_device(text, text) from public, anon;
grant execute on function public.register_device(text, text) to authenticated;

-- ---------------------------------------------------------------------------
-- Outbox (no client access: only the service role reads or changes it)
-- ---------------------------------------------------------------------------

create table public.notification_outbox (
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('reply', 'like', 'announcement')),
  -- Null sends to everyone (announcements).
  recipient_id uuid references public.profiles (id) on delete cascade,
  title text not null,
  body text not null,
  post_id uuid references public.posts (id) on delete cascade,
  created_at timestamptz not null default now(),
  sent_at timestamptz,
  attempts integer not null default 0,
  last_error text
);

create index notification_outbox_pending_idx on public.notification_outbox (id) where sent_at is null;

alter table public.notification_outbox enable row level security;
revoke all on table public.notification_outbox from anon, authenticated;

-- True when the recipient blocked the actor (then nothing is sent).
create function private.blocks_actor(p_recipient uuid, p_actor uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.blocks where blocker_id = p_recipient and blocked_id = p_actor);
$$;

create function private.notify_reply()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_author uuid;
  v_name text;
begin
  select author_id into v_author from public.posts where id = new.post_id;
  if v_author is null or v_author = new.author_id or private.blocks_actor(v_author, new.author_id) then
    return null;
  end if;
  select display_name into v_name from public.profiles where id = new.author_id;
  insert into public.notification_outbox (kind, recipient_id, title, body, post_id)
  values ('reply', v_author, 'New reply',
          coalesce(v_name, 'Someone') || ': ' || left(coalesce(nullif(btrim(new.body), ''), '📷'), 120),
          new.post_id);
  return null;
end;
$$;

-- One pending like notification per post at a time, so a popular post
-- doesn't buzz its author for every like.
create function private.notify_like()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_author uuid;
  v_name text;
begin
  select author_id into v_author from public.posts where id = new.post_id;
  if v_author is null or v_author = new.user_id or private.blocks_actor(v_author, new.user_id) then
    return null;
  end if;
  if exists (select 1 from public.notification_outbox o
             where o.kind = 'like' and o.post_id = new.post_id and o.sent_at is null) then
    return null;
  end if;
  select display_name into v_name from public.profiles where id = new.user_id;
  insert into public.notification_outbox (kind, recipient_id, title, body, post_id)
  values ('like', v_author, 'New like', coalesce(v_name, 'Someone') || ' liked your post', new.post_id);
  return null;
end;
$$;

create function private.notify_announcement()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.notification_outbox (kind, recipient_id, title, body)
  values ('announcement', null, new.title, new.body);
  return null;
end;
$$;

create trigger notify_reply after insert on public.replies
  for each row execute function private.notify_reply();
create trigger notify_like after insert on public.likes
  for each row execute function private.notify_like();
create trigger notify_announcement after insert on public.announcements
  for each row execute function private.notify_announcement();

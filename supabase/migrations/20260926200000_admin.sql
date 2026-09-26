-- Admin page support: announcements (written by admins, pushed to everyone
-- once notifications exist) and the page's simple counts.

create table public.announcements (
  id uuid primary key default gen_random_uuid(),
  title text not null check (char_length(btrim(title)) between 1 and 80),
  body text not null check (char_length(btrim(body)) between 1 and 300),
  created_by uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now()
);

create index announcements_recent_idx on public.announcements (created_at desc);

alter table public.announcements enable row level security;

create policy "Everyone signed in reads announcements"
  on public.announcements for select to authenticated
  using (true);
create policy "Admins announce"
  on public.announcements for insert to authenticated
  with check ((select public.is_admin()));

revoke all on table public.announcements from anon, authenticated;
grant select on table public.announcements to authenticated;
grant insert (title, body) on table public.announcements to authenticated;

-- Numbers for the admin page's overview. Admins only.
create function public.admin_counts()
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_today date := (now() at time zone 'Asia/Ho_Chi_Minh')::date;
begin
  perform private.require_admin();
  return jsonb_build_object(
    'users', (select count(*) from public.profiles),
    'guests', (select count(*) from auth.users where is_anonymous),
    'banned', (select count(*) from public.profiles where banned_at is not null),
    'scans_today', (select count(*) from public.scan_events where scanned_on = v_today),
    'points_today', (select coalesce(sum(points_awarded), 0) from public.scan_events where scanned_on = v_today),
    'scans_total', (select count(*) from public.scan_events),
    'posts', (select count(*) from public.posts where removed_at is null),
    'hidden_posts', (select count(*) from public.posts where hidden_at is not null and removed_at is null),
    'replies', (select count(*) from public.replies where removed_at is null),
    'open_reports', (select count(*) from public.reports where resolved_at is null)
  );
end;
$$;

revoke execute on function public.admin_counts() from public, anon;
grant execute on function public.admin_counts() to authenticated;

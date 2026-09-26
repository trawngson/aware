-- Community totals for Home's "Your Impact" card: how many people have
-- earned points, and how many recycled items of each canonical label were
-- counted (the app turns those into a weight with its typical item masses).
-- Banned users are left out, like on the leaderboard.
create function public.community_stats()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with counted as (
    select e.user_id, e.label, e.disposal_group
    from public.scan_events e
    join public.profiles p on p.id = e.user_id
    where e.points_awarded > 0 and p.banned_at is null
  )
  select jsonb_build_object(
    'recyclers', (select count(distinct c.user_id) from counted c),
    'recycled_by_label', coalesce(
      (select jsonb_object_agg(t.label, t.items)
       from (select c.label, count(*) as items from counted c
             where c.disposal_group = 'recyclable' group by c.label) t),
      '{}'::jsonb)
  );
$$;

revoke execute on function public.community_stats() from public, anon;
grant execute on function public.community_stats() to authenticated;

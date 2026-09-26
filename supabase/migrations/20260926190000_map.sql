-- Recycling map: posts may carry a location, always stored rounded to a
-- 0.005° grid (about 500 m), so nobody's exact position is ever saved. The
-- database rounds, so no client can skip it.

alter table public.posts
  add column latitude numeric(8, 3) check (latitude between -90 and 90),
  add column longitude numeric(9, 3) check (longitude between -180 and 180),
  add constraint posts_location_pair check ((latitude is null) = (longitude is null));

create index posts_location_idx on public.posts (latitude, longitude)
  where latitude is not null and removed_at is null;

create function private.round_location()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.latitude is not null then
    new.latitude := round(new.latitude / 0.005) * 0.005;
  end if;
  if new.longitude is not null then
    new.longitude := round(new.longitude / 0.005) * 0.005;
  end if;
  return new;
end;
$$;

create trigger round_location
  before insert or update of latitude, longitude on public.posts
  for each row execute function private.round_location();

grant insert (latitude, longitude) on table public.posts to authenticated;

-- Posts with a location inside a map region, newest first, optionally one
-- material. Runs with the caller's rights, so the posts' row-level security
-- (hidden, removed, banned and blocked authors) applies as everywhere else.
create function public.map_posts(
  p_min_latitude double precision,
  p_min_longitude double precision,
  p_max_latitude double precision,
  p_max_longitude double precision,
  p_material text default null,
  p_limit integer default 200
)
returns table (
  id uuid,
  title text,
  body text,
  material text,
  image_path text,
  latitude double precision,
  longitude double precision,
  created_at timestamptz,
  author_id uuid,
  author_name text,
  author_initials text,
  author_top integer,
  author_bottom integer
)
language sql
stable
security invoker
set search_path = ''
as $$
  select p.id, p.title, p.body, p.material, p.image_path,
    p.latitude::double precision, p.longitude::double precision, p.created_at,
    a.id, a.display_name, a.avatar_initials, a.avatar_top, a.avatar_bottom
  from public.posts p
  join public.profiles a on a.id = p.author_id
  where p.latitude between p_min_latitude and p_max_latitude
    and p.longitude between p_min_longitude and p_max_longitude
    and (p_material is null or p.material = p_material)
  order by p.created_at desc
  limit least(greatest(coalesce(p_limit, 200), 1), 500);
$$;

-- How many visible posts with a location are within p_radius_meters of a
-- point, optionally one material. Distances use an equirectangular
-- approximation, which is accurate to well under a percent at these ranges.
create function public.nearby_count(
  p_latitude double precision,
  p_longitude double precision,
  p_radius_meters double precision default 2000,
  p_material text default null
)
returns integer
language sql
stable
security invoker
set search_path = ''
as $$
  select count(*)::integer
  from public.posts p
  where p.latitude is not null
    and (p_material is null or p.material = p_material)
    and 6371000 * sqrt(
          power(radians(p.latitude::double precision - p_latitude), 2)
          + power(radians(p.longitude::double precision - p_longitude)
                  * cos(radians((p.latitude::double precision + p_latitude) / 2)), 2)
        ) <= least(greatest(coalesce(p_radius_meters, 2000), 0), 50000);
$$;

revoke execute on function public.map_posts(double precision, double precision, double precision, double precision, text, integer) from public, anon;
revoke execute on function public.nearby_count(double precision, double precision, double precision, text) from public, anon;
grant execute on function public.map_posts(double precision, double precision, double precision, double precision, text, integer) to authenticated;
grant execute on function public.nearby_count(double precision, double precision, double precision, text) to authenticated;

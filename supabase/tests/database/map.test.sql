-- Map: locations are rounded by the database to a 0.005° grid, and the map
-- functions only return posts the caller may see.
begin;
\ir _helpers.psql
select plan(13);

select tests.create_user('ana@example.com') as ana \gset
select tests.create_user('binh@example.com') as binh \gset
update public.profiles set terms_accepted_at = now();

select tests.act_as(:'ana');
insert into public.posts (body, material, latitude, longitude)
values ('Lamp by the lake', 'plastic', 21.02874, 105.85244);
select id as lamp from public.posts where body = 'Lamp by the lake' \gset
select is((select latitude::text || ',' || longitude::text from public.posts where id = :'lamp'),
  '21.030,105.850', 'exact positions are rounded to the 0.005° grid');
select throws_ok($$insert into public.posts (body, latitude) values ('half', 21.0)$$, '23514', null,
  'a location needs both coordinates');
select throws_ok($$insert into public.posts (body, latitude, longitude) values ('bad', 95, 105)$$, '23514', null,
  'coordinates must be on Earth');
select throws_ok(format($$update public.posts set latitude = 21.1 where id = '%s'$$, :'lamp'), '42501', null,
  'nobody moves a post afterwards');
insert into public.posts (body, material, latitude, longitude) values ('Far away', 'paper', 21.12, 105.85);
insert into public.posts (body) values ('No location');

select tests.act_as(:'binh');
select is((select count(*)::int from public.map_posts(21.0, 105.8, 21.06, 105.9)), 1,
  'posts inside the region, and only ones with a location');
select is((select author_name from public.map_posts(21.0, 105.8, 21.06, 105.9)),
  (select display_name from public.profiles where id = :'ana'), 'with their author');
select is((select count(*)::int from public.map_posts(21.0, 105.8, 21.06, 105.9, 'paper')), 0,
  'filtered by material');
select is((select count(*)::int from public.map_posts(20.0, 105.0, 22.0, 106.0)), 2, 'a bigger region has both');
select is(public.nearby_count(21.0287, 105.8524), 1, 'one post within 2 km of Hoan Kiem Lake');
select is(public.nearby_count(21.0287, 105.8524, 20000), 2, 'both within 20 km');
select is(public.nearby_count(21.0287, 105.8524, 2000, 'paper'), 0, 'nearby counts can be filtered too');

insert into public.blocks (blocked_id) values (:'ana');
select is(public.nearby_count(21.0287, 105.8524, 20000), 0, 'blocked authors don''t count');

select tests.act_as_anon();
select throws_ok($$select public.nearby_count(21.0, 105.8)$$, '42501', null, 'the anon key alone gets nothing');

select * from finish();
rollback;

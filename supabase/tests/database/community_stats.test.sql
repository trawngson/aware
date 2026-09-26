-- community_stats(): people with points and recycled items per label.
begin;
\ir _helpers.psql
select plan(5);

delete from public.scan_events;
select tests.create_user('a@example.com') as a \gset
select tests.create_user('b@example.com') as b \gset
select tests.create_user('c@example.com') as c \gset

insert into public.scan_events (id, user_id, label, policy_version, confirmed, disposal_group,
                                points_awarded, reward_state, reason_code, scanned_at)
values
  (gen_random_uuid(), :'a', 'metal_can', 'hanoi-2026.1', true, 'recyclable', 20, 'eligible', 'sorted_recyclable', now()),
  (gen_random_uuid(), :'a', 'metal_can', 'hanoi-2026.1', true, 'recyclable', 20, 'eligible', 'sorted_recyclable', now()),
  (gen_random_uuid(), :'b', 'plastic_bag', 'hanoi-2026.1', true, 'other', 10, 'eligible', 'sorted_other', now()),
  (gen_random_uuid(), :'b', 'glass_container', 'hanoi-2026.1', true, 'recyclable', 0, 'ineligible', 'daily_cap_reached', now()),
  (gen_random_uuid(), :'c', 'plastic_bottle', 'hanoi-2026.1', true, 'recyclable', 20, 'eligible', 'sorted_recyclable', now());
update public.profiles set banned_at = now() where id = :'c';

select tests.act_as_anon();
select throws_ok($$select public.community_stats()$$, '42501', null, 'the anon key alone gets no stats');

select tests.act_as(:'a');
select is((public.community_stats() ->> 'recyclers')::int, 2, 'people with points, banned users left out');
select is(public.community_stats() -> 'recycled_by_label', '{"metal_can": 2}'::jsonb,
  'only recycled items that earned points, by label');

select tests.act_as_owner();
delete from public.scan_events;
select tests.act_as(:'a');
select is((public.community_stats() ->> 'recyclers')::int, 0, 'an empty community has no recyclers');
select is(public.community_stats() -> 'recycled_by_label', '{}'::jsonb, 'and no items');

select * from finish();
rollback;

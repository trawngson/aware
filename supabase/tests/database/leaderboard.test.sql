-- Leaderboard: this Vietnam month and all time, top N plus the caller's own
-- row, banned users left out.
begin;
\ir _helpers.psql
select plan(13);

-- Start from an empty board (rolled back at the end).
delete from public.scan_events;

select tests.create_user('an@example.com') as an \gset
select tests.create_user('binh@example.com') as binh \gset
select tests.create_user('chi@example.com') as chi \gset
select tests.create_user('dung@example.com') as dung \gset
select tests.create_user(null, true) as guest \gset

-- Scores: An 60 this month; Binh 40 this month + 100 two months ago;
-- Chi 20 this month but banned; Dung 20 this month; the guest has none.
insert into public.scan_events (id, user_id, label, policy_version, confirmed, disposal_group,
                                points_awarded, reward_state, reason_code, scanned_at)
select gen_random_uuid(), u, 'metal_can', 'hanoi-2026.1', true, 'recyclable', p, 'eligible',
       'sorted_recyclable', t
from (values
  (:'an'::uuid, 20, now()), (:'an'::uuid, 20, now()), (:'an'::uuid, 20, now()),
  (:'binh'::uuid, 20, now()), (:'binh'::uuid, 20, now()),
  (:'binh'::uuid, 100, date_trunc('month', now() at time zone 'Asia/Ho_Chi_Minh') at time zone 'Asia/Ho_Chi_Minh' - interval '40 days'),
  (:'chi'::uuid, 20, now()),
  (:'dung'::uuid, 20, now())
) as s (u, p, t);
update public.profiles set display_name = 'An' where id = :'an';
update public.profiles set display_name = 'Binh' where id = :'binh';
update public.profiles set display_name = 'Dung' where id = :'dung';
update public.profiles set banned_at = now() where id = :'chi';

select tests.act_as_anon();
select throws_ok($$select * from public.leaderboard()$$, '42501', null, 'the anon key alone gets no leaderboard');

select tests.act_as(:'guest', true);
select results_eq(
  $$select rank, display_name, points from public.leaderboard('month', 10) where not is_me$$,
  $$values (1::bigint, 'An'::text, 60::bigint), (2, 'Binh', 40), (3, 'Dung', 20)$$,
  'this month: highest first, banned users left out');
select results_eq(
  $$select rank, display_name, points from public.leaderboard('all', 10) where not is_me$$,
  $$values (1::bigint, 'Binh'::text, 140::bigint), (2, 'An', 60), (3, 'Dung', 20)$$,
  'all time counts earlier months');
select results_eq(
  $$select rank, points, is_me from public.leaderboard('month', 10) where user_id = auth.uid()$$,
  $$values (4::bigint, 0::bigint, true)$$,
  'a caller with no points comes after everyone with points');
select is((select count(*)::int from public.leaderboard('month', 2)), 3,
  'top 2 plus the caller''s own row');
select is((select count(*)::int from public.leaderboard('month', 2) where is_me), 1,
  'the caller''s row is marked');

select tests.act_as(:'an');
select is((select count(*)::int from public.leaderboard('month', 2)), 2,
  'no extra row when the caller is already in the top N');
select is((select is_me from public.leaderboard('month', 2) where rank = 1), true,
  'the caller is marked inside the top N');

select tests.act_as(:'dung');
select results_eq(
  $$select rank, points from public.leaderboard('month', 1) where is_me$$,
  $$values (3::bigint, 20::bigint)$$,
  'the caller''s own rank outside the top N');

select tests.act_as(:'chi');
select is((select count(*)::int from public.leaderboard('month', 10) where is_me), 0,
  'banned callers don''t appear, not even to themselves');

-- Ties share a rank
select tests.act_as_owner();
insert into public.scan_events (id, user_id, label, policy_version, confirmed, disposal_group,
                                points_awarded, reward_state, reason_code, scanned_at)
values (gen_random_uuid(), :'dung', 'metal_can', 'hanoi-2026.1', true, 'recyclable', 20, 'eligible', 'sorted_recyclable', now());
select tests.act_as(:'guest', true);
select results_eq(
  $$select rank, display_name from public.leaderboard('month', 10) where not is_me$$,
  $$values (1::bigint, 'An'::text), (2, 'Binh'), (2, 'Dung')$$,
  'equal points share a rank');

select throws_ok($$select * from public.leaderboard('week')$$, '22023', null, 'only month and all are periods');
select is((select count(*)::int from public.leaderboard('month', 1000) where not is_me), 3,
  'a huge limit is capped and still works');

select * from finish();
rollback;

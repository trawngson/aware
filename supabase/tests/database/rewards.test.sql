-- Points: award_scan() is the only way to earn them, it follows the reward
-- rules, awards each scan event at most once, needs the user's confirmation
-- and caps points per Vietnam day (backend/SPECIFICATION.md 5.3).
begin;
\ir _helpers.psql
select plan(37);

select tests.create_user(null, true) as guest \gset
select tests.create_user('bao@example.com') as bao \gset

-- Reward rules are public, versioned and seeded with today's values
select tests.act_as_anon();
select is((select points from public.reward_rules
           where policy_version = 'hanoi-2026.1' and label = 'plastic_bottle' and choice_id = ''),
  20, 'a plastic bottle is worth 20 points under hanoi-2026.1');
select is((select count(*)::int from public.reward_rules where policy_version = 'hanoi-2026.1'),
  10, 'every label and answer has a rule');
select throws_ok($$select public.award_scan(gen_random_uuid(), 'plastic_bottle', 'hanoi-2026.1', true)$$,
  '42501', null, 'the anon key alone can''t record scans');

select tests.act_as(:'guest', true);
select throws_ok($$insert into public.reward_rules values ('x', 'plastic_bottle', '', 'recyclable', 999, true)$$,
  '42501', null, 'users can''t add reward rules');

-- Eligible, then already awarded
select '11111111-1111-4111-8111-111111111111' as bottle \gset
select is(public.award_scan(:'bottle', 'plastic_bottle', 'hanoi-2026.1', true),
  jsonb_build_object('state', 'eligible', 'points', 20, 'reason_code', 'sorted_recyclable',
                     'scan_event_id', :'bottle'),
  'a confirmed recyclable scan earns 20 points');
select is(public.award_scan(:'bottle', 'plastic_bottle', 'hanoi-2026.1', true),
  jsonb_build_object('state', 'already_awarded', 'points', 20, 'reason_code', 'already_awarded',
                     'scan_event_id', :'bottle'),
  'the same scan event never earns twice');
select is(public.award_scan(:'bottle', 'metal_can', 'hanoi-2026.1', true) ->> 'state', 'already_awarded',
  'changing the label doesn''t earn again');
select is((select sum(points_awarded)::int from public.scan_events where user_id = :'guest'), 20,
  'only one award was stored');

-- Other waste
select is(public.award_scan(gen_random_uuid(), 'plastic_bag', 'hanoi-2026.1', true) - 'scan_event_id',
  '{"state": "eligible", "points": 10, "reason_code": "sorted_other"}'::jsonb,
  'other waste earns 10 points, as in the app');

-- Confirmation
select '22222222-2222-4222-8222-222222222222' as cup \gset
select is(public.award_scan(:'cup', 'disposable_cup', 'hanoi-2026.1', true) ->> 'state',
  'confirmation_required', 'a cup needs the user''s answer first');
select is(public.award_scan(:'cup', 'disposable_cup', 'hanoi-2026.1', true, 'glass') ->> 'state',
  'confirmation_required', 'an unknown answer still needs one');
select is(public.award_scan(:'cup', 'disposable_cup', 'hanoi-2026.1', true, 'paper') - 'scan_event_id',
  '{"state": "eligible", "points": 20, "reason_code": "sorted_recyclable"}'::jsonb,
  'after the answer the same scan event earns its points');
select is((select choice_id || '/' || reward_state from public.scan_events where id = :'cup'),
  'paper/eligible', 'the answer is stored with the event');
select is(public.award_scan(gen_random_uuid(), 'cardboard', 'hanoi-2026.1', true, 'soiled') ->> 'points',
  '10', 'soiled cardboard is other waste');

select '33333333-3333-4333-8333-333333333333' as unconfirmed \gset
select is(public.award_scan(:'unconfirmed', 'metal_can', 'hanoi-2026.1', false) - 'scan_event_id',
  '{"state": "confirmation_required", "points": 0, "reason_code": "not_confirmed"}'::jsonb,
  'no points before the user confirms');
select is(public.award_scan(:'unconfirmed', 'metal_can', 'hanoi-2026.1', true) ->> 'state', 'eligible',
  'the user can confirm the same event later');
select is(public.award_scan(gen_random_uuid(), 'metal_can', 'hanoi-2026.1', true, 'clean') ->> 'state',
  'eligible', 'an answer for a label that needs none is ignored');

-- Ineligible
select is(public.award_scan(gen_random_uuid(), 'uncertain', 'hanoi-2026.1', true) - 'scan_event_id',
  '{"state": "ineligible", "points": 0, "reason_code": "unsupported_label"}'::jsonb,
  'labels outside the ontology earn nothing');
select is(public.award_scan(gen_random_uuid(), 'plastic_bottle', 'hanoi-1999.0', true) ->> 'reason_code',
  'unsupported_policy', 'unknown policy versions earn nothing');
select throws_ok($$select public.award_scan(gen_random_uuid(), 'Plastic Bottle', 'hanoi-2026.1', true)$$,
  '22023', null, 'labels are matched exactly, not loosely');

-- Stored events are private and read-only
select is((select count(*)::int from public.scan_events), 8, 'users see their own scan events');
select throws_ok($$update public.scan_events set points_awarded = 1000$$, '42501', null,
  'users can''t change their points');
select throws_ok(
  $$insert into public.scan_events (id, user_id, label, policy_version, confirmed, reward_state, reason_code, scanned_at)
    values (gen_random_uuid(), auth.uid(), 'metal_can', 'hanoi-2026.1', true, 'eligible', 'x', now())$$,
  '42501', null, 'users can''t write scan events directly');
select throws_ok($$delete from public.scan_events$$, '42501', null, 'users can''t delete scan events');

select tests.act_as(:'bao');
select is((select count(*)::int from public.scan_events), 0, 'users can''t see other people''s scan events');
select is(public.award_scan(:'bottle', 'plastic_bottle', 'hanoi-2026.1', true) - 'scan_event_id',
  '{"state": "ineligible", "points": 0, "reason_code": "scan_event_taken"}'::jsonb,
  'another user''s scan event id earns nothing');

-- Scan time is clamped to the last 7 days
select tests.act_as(:'guest', true);
select '44444444-4444-4444-8444-444444444444' as old_scan \gset
select '55555555-5555-4555-8555-555555555555' as future_scan \gset
select public.award_scan(:'old_scan', 'metal_can', 'hanoi-2026.1', true, null, now() - interval '30 days');
select public.award_scan(:'future_scan', 'metal_can', 'hanoi-2026.1', true, null, now() + interval '3 days');
select ok((select scanned_at between now() - interval '7 days 1 minute' and now() - interval '6 days 23 hours'
           from public.scan_events where id = :'old_scan'),
  'a scan dated 30 days ago counts as 7 days ago');
select ok((select scanned_at <= now() from public.scan_events where id = :'future_scan'),
  'a scan dated in the future counts as now');

-- Daily cap, by Vietnam day
select tests.act_as_owner();
select is((select daily_point_cap from public.app_settings), 200, 'the default cap is 200 points a day');
update public.app_settings set daily_point_cap = 50;
select tests.create_user('cap@example.com') as capped \gset
select tests.act_as(:'capped');
select is(public.award_scan(gen_random_uuid(), 'metal_can', 'hanoi-2026.1', true) ->> 'points', '20', 'first scan: 20');
select is(public.award_scan(gen_random_uuid(), 'metal_can', 'hanoi-2026.1', true) ->> 'points', '20', 'second scan: 40');
select is(public.award_scan(gen_random_uuid(), 'metal_can', 'hanoi-2026.1', true) - 'scan_event_id',
  '{"state": "ineligible", "points": 0, "reason_code": "daily_cap_reached"}'::jsonb,
  'a third would pass the cap of 50, so it earns nothing');
select is(public.award_scan(gen_random_uuid(), 'plastic_bag', 'hanoi-2026.1', true) ->> 'points', '10',
  'a smaller award that fits under the cap still counts');
select is(public.award_scan(gen_random_uuid(), 'metal_can', 'hanoi-2026.1', true, null, now() - interval '2 days') ->> 'state',
  'eligible', 'another day has its own cap');
select is((select sum(points_awarded)::int from public.scan_events), 70, 'capped total');
-- 23:30 in Vietnam on one day and 00:30 the next are different days, even
-- though both are the same UTC day.
select is(
  (select (timestamptz '2026-09-25 16:30:00+00' at time zone 'Asia/Ho_Chi_Minh')::date
        <> (timestamptz '2026-09-25 17:30:00+00' at time zone 'Asia/Ho_Chi_Minh')::date),
  true, 'days are counted in Vietnam time');
select is(
  (select scanned_on from public.scan_events order by scanned_at desc limit 1),
  (now() at time zone 'Asia/Ho_Chi_Minh')::date, 'stored events carry their Vietnam day');

select * from finish();
rollback;

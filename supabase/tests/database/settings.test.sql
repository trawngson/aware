-- App settings: anyone can read the single row; only a signed-in admin can
-- change it. Guests can never act as admins.
begin;
\ir _helpers.psql
select plan(13);

select tests.create_user(null, true) as guest \gset
select tests.create_user('admin@example.com') as admin \gset
select tests.make_admin(:'admin');

select tests.act_as_anon();
select is((select show_samples from public.app_settings), true, 'anyone can read show_samples; samples start on');
select is((select report_threshold from public.app_settings), 3, 'three reports hide content by default');

select tests.act_as(:'guest', true);
update public.app_settings set show_samples = false;
select is((select show_samples from public.app_settings), true, 'users can''t change the settings');
select throws_ok($$update public.app_settings set updated_by = null$$, '42501', null,
  'users can''t forge who changed the settings');
select throws_ok($$insert into public.app_settings (id) values (true)$$, '42501', null,
  'there is no second settings row');
select throws_ok($$delete from public.app_settings$$, '42501', null, 'the settings row can''t be deleted');

-- A guest whose profile somehow says admin is still not an admin
select tests.act_as_owner();
select tests.make_admin(:'guest');
select tests.act_as(:'guest', true);
select is(public.is_admin(), false, 'guests are never admins');
update public.app_settings set show_samples = false;
select is((select show_samples from public.app_settings), true, 'a guest with the admin role still can''t change settings');

select tests.act_as(:'admin');
select is(public.is_admin(), true, 'a signed-in admin is an admin');
update public.app_settings set show_samples = false, daily_point_cap = 150;
select is((select show_samples::text || '/' || daily_point_cap from public.app_settings), 'false/150',
  'admins change the settings');
select is((select updated_by from public.app_settings), :'admin'::uuid, 'the change records who made it');
select throws_ok($$update public.app_settings set daily_point_cap = -1$$, '23514', null,
  'the cap can''t go below zero');

select tests.act_as_owner();
update public.profiles set banned_at = now() where id = :'admin';
select tests.act_as(:'admin');
select is(public.is_admin(), false, 'a banned admin loses admin rights');

select * from finish();
rollback;

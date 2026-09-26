-- Profiles: created on sign-up with a friendly name, readable by everyone
-- signed in, and editable only by their owner, and only the name.
begin;
\ir _helpers.psql
select plan(19);

select tests.create_user('ana@example.com') as ana \gset
select tests.create_user(null, true) as guest \gset

-- The sign-up trigger
select is((select count(*)::int from public.profiles where id in (:'ana', :'guest')), 2,
  'every new user, guests included, gets a profile');
select matches((select display_name from public.profiles where id = :'guest'), '^Recycler [0-9]{4}$',
  'guests get a generated "Recycler 1234" name');
select is((select avatar_initials from public.profiles where id = :'guest'), 'R',
  'generated names get one initial');
select is((select role from public.profiles where id = :'guest'), 'user',
  'new users are not admins');
select ok((select avatar_top between 0 and 16777215 and avatar_top <> avatar_bottom
           from public.profiles where id = :'guest'),
  'new users get an avatar gradient');

-- Reading
select tests.act_as(:'guest', true);
select is((select count(*)::int from public.profiles where id in (:'ana', :'guest')), 2,
  'signed-in users can see other people''s names');

-- Editing their own name
select lives_ok(
  format($$update public.profiles set display_name = '  Truong   Son ' where id = %L$$, :'guest'),
  'users can rename themselves');
select tests.act_as_owner();
select is((select display_name || '/' || avatar_initials from public.profiles where id = :'guest'),
  'Truong Son/TS', 'names are trimmed and initials follow the name');

-- Not someone else's
select tests.act_as(:'guest', true);
update public.profiles set display_name = 'Hacked' where id = :'ana';
select tests.act_as_owner();
select isnt((select display_name from public.profiles where id = :'ana'), 'Hacked',
  'users can''t rename someone else');

-- Not the protected columns
select tests.act_as(:'guest', true);
select throws_ok(
  format($$update public.profiles set role = 'admin' where id = %L$$, :'guest'),
  '42501', null, 'users can''t make themselves admins');
select throws_ok(
  format($$update public.profiles set banned_at = null where id = %L$$, :'guest'),
  '42501', null, 'users can''t lift a ban');
select throws_ok(
  format($$update public.profiles set avatar_initials = 'XX' where id = %L$$, :'guest'),
  '42501', null, 'initials come from the name only');
select throws_ok(
  format($$insert into public.profiles (id, display_name) values (%L, 'Extra')$$, gen_random_uuid()),
  '42501', null, 'users can''t create profiles');
select throws_ok(
  format($$delete from public.profiles where id = %L$$, :'ana'),
  '42501', null, 'users can''t delete profiles');
select throws_ok(
  $$update public.profiles set display_name = '' $$,
  '23514', null, 'empty names are rejected');

-- Banned users keep their profile but can't rename themselves
select tests.act_as_owner();
update public.profiles set banned_at = now() where id = :'ana';
select tests.act_as(:'ana');
update public.profiles set display_name = 'New name' where id = :'ana';
select tests.act_as_owner();
select isnt((select display_name from public.profiles where id = :'ana'), 'New name',
  'banned users can''t rename themselves');

-- No session, no profiles
select tests.act_as_anon();
select throws_ok($$select count(*) from public.profiles$$, '42501', null,
  'the anon key alone can''t list profiles');

-- Deleting the auth user removes the profile
select tests.act_as_owner();
delete from auth.users where id = :'ana';
select is((select count(*)::int from public.profiles where id = :'ana'), 0,
  'deleting the account removes the profile');

-- Admin check
select tests.act_as(:'guest', true);
select is(public.is_admin(), false, 'a guest is not an admin');

select * from finish();
rollback;

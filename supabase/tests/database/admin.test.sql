-- Admin support: announcements and counts are for signed-in admins only.
begin;
\ir _helpers.psql
select plan(9);

select tests.create_user('admin@example.com') as admin \gset
select tests.create_user('user@example.com') as member \gset
select tests.create_user(null, true) as guest \gset
select tests.make_admin(:'admin');

select tests.act_as(:'member');
select throws_ok($$insert into public.announcements (title, body) values ('Hi', 'Free bags')$$, '42501', null,
  'users can''t announce');
select throws_ok($$select public.admin_counts()$$, '42501', null, 'users can''t see the admin counts');

select tests.act_as_owner();
select tests.make_admin(:'guest');
select tests.act_as(:'guest', true);
select throws_ok($$insert into public.announcements (title, body) values ('Hi', 'Free bags')$$, '42501', null,
  'guests can''t announce, even with the admin role');

select tests.act_as(:'admin');
select lives_ok($$insert into public.announcements (title, body) values ('Recycling day', 'Bring your cans on Sunday!')$$,
  'admins announce');
select is((select created_by from public.announcements where title = 'Recycling day'), :'admin'::uuid,
  'the announcement records its admin');
select throws_ok($$insert into public.announcements (title, body) values ('  ', 'x')$$, '23514', null,
  'an announcement needs a title');
select ok((public.admin_counts() ->> 'users')::int >= 3, 'the counts include every user');
select ok((public.admin_counts() ->> 'guests')::int >= 1, 'and the guests among them');

select tests.act_as(:'member');
select is((select count(*)::int from public.announcements where title = 'Recycling day'), 1,
  'everyone signed in can read announcements');

select * from finish();
rollback;

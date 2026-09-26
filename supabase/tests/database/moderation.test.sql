-- Moderation: blocks, reports and auto-hide, bans, and the admin tools.
begin;
\ir _helpers.psql
select plan(32);

select tests.create_user('ana@example.com') as ana \gset
select tests.create_user('binh@example.com') as binh \gset
select tests.create_user('chi@example.com') as chi \gset
select tests.create_user('dung@example.com') as dung \gset
select tests.create_user('admin@example.com') as admin \gset
select tests.create_user(null, true) as guest \gset
select tests.make_admin(:'admin');
update public.profiles set terms_accepted_at = now();

select tests.act_as(:'ana');
insert into public.posts (body) values ('Ana''s egg carton turtle');
select id as post from public.posts where body = 'Ana''s egg carton turtle' \gset
select tests.act_as(:'binh');
insert into public.replies (post_id, body) values (:'post', 'Binh says hi');
select id as reply from public.replies where body = 'Binh says hi' \gset

-- Blocks
select tests.act_as(:'chi');
insert into public.blocks (blocked_id) values (:'ana');
select is((select count(*)::int from public.posts where id = :'post'), 0, 'the blocker no longer sees the blocked user''s posts');
select is((select count(*)::int from public.replies where id = :'reply'), 0, 'nor replies under them');
select tests.act_as(:'binh');
select is((select count(*)::int from public.posts where id = :'post'), 1, 'other people still see them');
select is((select count(*)::int from public.blocks), 0, 'blocks are private');
select tests.act_as(:'chi');
select throws_ok(format($$insert into public.blocks (blocked_id) values ('%s')$$, :'chi'), '23514', null,
  'nobody blocks themselves');
delete from public.blocks where blocked_id = :'ana';
select is((select count(*)::int from public.posts where id = :'post'), 1, 'unblocking shows them again');

-- Reports and auto-hide after 3 different people
select tests.act_as(:'binh');
insert into public.reports (post_id, reason) values (:'post', 'spam');
select throws_ok(format($$insert into public.reports (post_id) values ('%s')$$, :'post'), '23505', null,
  'one report per person per post');
select tests.act_as(:'chi');
insert into public.reports (post_id) values (:'post');
select tests.act_as(:'dung');
select is((select count(*)::int from public.reports), 0, 'reports are private');
select is((select count(*)::int from public.posts where id = :'post'), 1, 'two reports don''t hide a post');
insert into public.reports (post_id) values (:'post');
select is((select count(*)::int from public.posts where id = :'post'), 0, 'the third report hides it');
select tests.act_as(:'ana');
select is((select count(*)::int from public.posts where id = :'post'), 1, 'its author still sees it');
select throws_ok(format($$insert into public.replies (post_id, body) values ('%s', 'hello?')$$, :'post'),
  '42501', null, 'nobody replies to a hidden post');

-- The threshold is a setting
select tests.act_as_owner();
update public.app_settings set report_threshold = 1;
select tests.act_as(:'dung');
insert into public.reports (reply_id) values (:'reply');
select tests.act_as(:'chi');
select is((select count(*)::int from public.replies where id = :'reply'), 0, 'with a threshold of 1 one report hides a reply');
select tests.act_as_owner();
update public.app_settings set report_threshold = 3;

-- Users can be reported too, without anything being hidden
select tests.act_as(:'chi');
select lives_ok(format($$insert into public.reports (reported_user_id, reason) values ('%s', 'rude')$$, :'binh'),
  'users can be reported');
select throws_ok(format($$insert into public.reports (post_id, reply_id) values ('%s', '%s')$$, :'post', :'reply'),
  '23514', null, 'a report is about exactly one thing');

-- Admin tools are for signed-in admins only
select throws_ok($$select * from public.admin_report_queue()$$, '42501', null, 'users can''t open the report queue');
select throws_ok(format($$select public.admin_moderate('post', '%s', 'restore')$$, :'post'), '42501', null,
  'users can''t moderate');
select throws_ok(format($$select public.admin_set_banned('%s', true)$$, :'binh'), '42501', null, 'users can''t ban');
select tests.act_as_owner();
select tests.make_admin(:'guest');
select tests.act_as(:'guest', true);
select throws_ok($$select * from public.admin_report_queue()$$, '42501', null, 'guests can''t act as admins');

select tests.act_as(:'admin');
select is((select count(*)::int from public.reports), 5, 'admins see every report');
select results_eq(
  $$select kind, reports from public.admin_report_queue() order by kind$$,
  $$values ('post'::text, 3::bigint), ('reply', 1), ('user', 1)$$,
  'the queue groups open reports by what was reported');
select is((select count(*)::int from public.posts where id = :'post'), 1, 'admins see hidden posts');
select is(public.admin_moderate('post', :'post', 'restore'), null, 'restoring returns no photo to delete');
select tests.act_as(:'chi');
select is((select count(*)::int from public.posts where id = :'post'), 1, 'a restored post shows again');
select tests.act_as(:'admin');
select is((select count(*)::int from public.admin_report_queue() where kind = 'post'), 0,
  'restoring closes its reports');

-- Removing
select tests.act_as(:'ana');
insert into public.posts (image_path) values (:'ana' || '/lamp.jpg');
select id as photo_post from public.posts where image_path = :'ana' || '/lamp.jpg' \gset
select tests.act_as(:'admin');
select is(public.admin_moderate('post', :'photo_post', 'remove'), :'ana' || '/lamp.jpg',
  'removing returns the photo to delete from storage');
select tests.act_as(:'ana');
select is((select count(*)::int from public.posts where id = :'photo_post'), 0, 'removed posts are gone, even for their author');

-- Bans
select tests.act_as(:'admin');
select public.admin_set_banned(:'binh', true);
select throws_ok(format($$select public.admin_set_banned('%s', true)$$, :'admin'), '22023', null,
  'admins can''t ban themselves');
select tests.act_as(:'binh');
select throws_ok($$insert into public.posts (body) values ('I''m back')$$, '42501', null, 'banned users can''t post');
select throws_ok(format($$insert into public.likes (post_id) values ('%s')$$, :'post'), '42501', null,
  'banned users can''t like');
select tests.act_as(:'chi');
select is((select count(*)::int from public.replies where author_id = :'binh'), 0, 'banned users'' content stops showing');
select tests.act_as(:'admin');
select public.admin_set_banned(:'binh', false);
select is((select banned_at from public.profiles where id = :'binh'), null, 'admins can lift a ban');

select * from finish();
rollback;

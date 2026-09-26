-- Notifications: device tokens are private, and the outbox gets a message for
-- replies and likes on your posts (not your own, not from people you blocked)
-- and for announcements. Only the service role can read the outbox.
begin;
\ir _helpers.psql
select plan(14);

select tests.create_user('ana@example.com') as ana \gset
select tests.create_user('binh@example.com') as binh \gset
select tests.create_user('chi@example.com') as chi \gset
select tests.create_user('admin@example.com') as admin \gset
select tests.make_admin(:'admin');
update public.profiles set terms_accepted_at = now();
update public.profiles set display_name = 'Binh' where id = :'binh';

-- Device tokens
select tests.act_as(:'ana');
select lives_ok($$select public.register_device(repeat('ab', 32), 'sandbox')$$, 'users register their phone');
select is((select count(*)::int from public.device_tokens), 1, 'and see their own token');
select throws_ok(format($$insert into public.device_tokens (token, user_id) values ('%s', '%s')$$, repeat('cd', 32), :'binh'),
  '42501', null, 'nobody registers a token for someone else');
select throws_ok($$select public.register_device('not a token')$$, '23514', null, 'tokens are hex');
select tests.act_as(:'binh');
select is((select count(*)::int from public.device_tokens), 0, 'tokens are private');
select public.register_device(repeat('ab', 32), 'sandbox');
select tests.act_as_owner();
select is((select user_id from public.device_tokens), :'binh'::uuid, 'a phone that signs in to another account moves to it');

-- Outbox
select tests.act_as(:'ana');
insert into public.posts (body) values ('Ana''s lamp');
select id as post from public.posts where body = 'Ana''s lamp' \gset
insert into public.replies (post_id, body) values (:'post', 'Thanks all!');
select tests.act_as(:'binh');
insert into public.replies (post_id, body) values (:'post', 'So cool');
insert into public.likes (post_id) values (:'post');
select tests.act_as(:'chi');
insert into public.likes (post_id) values (:'post');
select throws_ok($$select count(*) from public.notification_outbox$$, '42501', null, 'users can''t read the outbox');

select tests.act_as_owner();
select results_eq(
  $$select kind, recipient_id, title, body from public.notification_outbox order by id$$,
  format($$values ('reply'::text, '%s'::uuid, 'New reply'::text, 'Binh: So cool'::text),
                  ('like', '%s'::uuid, 'New like', 'Binh liked your post')$$, :'ana', :'ana'),
  'a reply and one like notification; no notice for your own reply or for every like');

update public.notification_outbox set sent_at = now();
select tests.act_as(:'chi');
delete from public.likes where post_id = :'post';
insert into public.likes (post_id) values (:'post');
select tests.act_as_owner();
select is((select count(*)::int from public.notification_outbox where sent_at is null and kind = 'like'), 1,
  'after the last one went out, a new like notifies again');

-- Blocked people don't reach you
select tests.act_as(:'ana');
insert into public.blocks (blocked_id) values (:'chi');
select tests.act_as(:'chi');
insert into public.replies (post_id, body) values (:'post', 'hello?');
select tests.act_as_owner();
select is((select count(*)::int from public.notification_outbox where body like '%hello?%'), 0,
  'replies from blocked people send nothing');

-- Photo-only replies
select tests.act_as(:'binh');
insert into public.replies (post_id, image_path) values (:'post', :'binh' || '/p.jpg');
select tests.act_as_owner();
select is((select body from public.notification_outbox order by id desc limit 1), 'Binh: 📷',
  'a photo reply says so');

-- Announcements go to everyone
select tests.act_as(:'admin');
insert into public.announcements (title, body) values ('Recycling day', 'Sunday at the lake');
select tests.act_as_owner();
select results_eq(
  $$select kind, recipient_id is null, title, body from public.notification_outbox where kind = 'announcement'$$,
  $$values ('announcement'::text, true, 'Recycling day'::text, 'Sunday at the lake'::text)$$,
  'an announcement is one message for everyone');

-- Deleting an account removes its tokens and messages
delete from auth.users where id = :'ana';
select is((select count(*)::int from public.notification_outbox where recipient_id = :'ana'), 0,
  'messages for a deleted account go with it');
delete from auth.users where id = :'binh';
select is((select count(*)::int from public.device_tokens), 0, 'and so do its tokens');

select * from finish();
rollback;

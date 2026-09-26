-- Gallery: posting needs the community terms, counts come from the database,
-- likes and saves are private, and users only change their own content.
begin;
\ir _helpers.psql
select plan(34);

select tests.create_user('ana@example.com') as ana \gset
select tests.create_user(null, true) as guest \gset

-- Terms come first
select tests.act_as(:'guest', true);
select throws_ok($$insert into public.posts (body) values ('My first bottle lamp')$$,
  '42501', null, 'no posting before accepting the community terms');
select isnt(public.accept_terms(), null, 'accepting the terms is recorded');
select tests.act_as_owner();
select isnt((select terms_accepted_at from public.profiles where id = :'guest'), null, 'the profile shows the terms were accepted');

-- Posting
select tests.act_as(:'guest', true);
select lives_ok($$insert into public.posts (title, body, material) values ('Bottle lamp', 'Made from 3 bottles', 'plastic')$$,
  'a guest who accepted the terms can post');
select is((select author_id from public.posts where title = 'Bottle lamp'), :'guest'::uuid,
  'the author is always the caller');
select throws_ok($$insert into public.posts (body) values ('   ')$$, '23514', null, 'a post needs text or a photo');
select throws_ok($$insert into public.posts (body, material) values ('x', 'wood')$$, '23514', null,
  'the material is one of the four tags');
select throws_ok(format($$insert into public.posts (body, image_path) values ('x', '%s/a.jpg')$$, :'ana'),
  '23514', null, 'a post can only use a photo from the author''s own folder');
select lives_ok(format($$insert into public.posts (image_path) values ('%s/photo-1.jpg')$$, :'guest'),
  'a post can be just a photo');
select throws_ok($$insert into public.posts (body, like_count) values ('x', 999)$$, '42501', null,
  'the app can''t set counts');
select throws_ok(format($$insert into public.posts (body, author_id) values ('x', '%s')$$, :'ana'),
  '42501', null, 'the app can''t post as someone else');
select throws_ok($$update public.posts set body = 'edited'$$, '42501', null, 'posts can''t be edited');

select id as lamp from public.posts where title = 'Bottle lamp' \gset

-- Everyone signed in sees it
select tests.act_as(:'ana');
select is((select count(*)::int from public.posts where id = :'lamp'), 1, 'other users see the post');

-- Likes: counted by the database, private, once per person
select lives_ok(format($$insert into public.likes (post_id) values ('%s')$$, :'lamp'),
  'liking needs no terms');
select throws_ok(format($$insert into public.likes (post_id) values ('%s')$$, :'lamp'), '23505', null,
  'one like per person');
select tests.act_as(:'guest', true);
insert into public.likes (post_id) values (:'lamp');
select is((select like_count from public.posts where id = :'lamp'), 2, 'the like count follows the likes');
select is((select count(*)::int from public.likes), 1, 'users only see their own likes');
delete from public.likes where post_id = :'lamp';
select is((select like_count from public.posts where id = :'lamp'), 1, 'unliking lowers the count');

-- Saves: private too
insert into public.saves (post_id) values (:'lamp');
select is((select save_count from public.posts where id = :'lamp'), 1, 'the save count follows the saves');
select tests.act_as(:'ana');
select is((select count(*)::int from public.saves), 0, 'users can''t see other people''s saves');
select throws_ok(format($$insert into public.saves (post_id, user_id) values ('%s', '%s')$$, :'lamp', :'guest'),
  '42501', null, 'users can''t save for someone else');

-- Replies
select throws_ok(format($$insert into public.replies (post_id, body) values ('%s', 'Love it')$$, :'lamp'),
  '42501', null, 'replying needs the terms too');
select public.accept_terms();
select lives_ok(format($$insert into public.replies (post_id, body) values ('%s', 'Love it')$$, :'lamp'),
  'members reply');
select is((select reply_count from public.posts where id = :'lamp'), 1, 'the reply count follows the replies');
select is((select count(*)::int from public.replies where post_id = :'lamp'), 1, 'replies are visible');

-- Only the author (or an admin) deletes
delete from public.posts where id = :'lamp';
select is((select count(*)::int from public.posts where id = :'lamp'), 1, 'users can''t delete someone else''s post');
select tests.act_as(:'guest', true);
delete from public.replies where post_id = :'lamp';
select is((select count(*)::int from public.replies where post_id = :'lamp'), 1, 'or someone else''s reply');

-- Word filter
select throws_ok($$insert into public.posts (body) values ('What the FUCK is this')$$, 'P0001', 'content_not_allowed',
  'English swear words are refused, in any case');
select throws_ok($$insert into public.posts (body) values ('đồ lồn')$$, 'P0001', 'content_not_allowed',
  'Vietnamese swear words are refused');
select lives_ok($$insert into public.posts (body) values ('Gom lon nước ngọt để bán ve chai')$$,
  '"lon" (a can) is not the swear word with diacritics');
select lives_ok($$insert into public.posts (body) values ('Reading Dickens by a lamp made of shiitake boxes')$$,
  'only whole words are matched');
select throws_ok(format($$update public.profiles set display_name = 'Big Shit' where id = '%s'$$, :'guest'),
  'P0001', 'content_not_allowed', 'names are filtered too');

-- Deleting a post takes its replies, likes and saves with it
select lives_ok(format($$delete from public.posts where id = '%s'$$, :'lamp'), 'authors delete their own posts');
select tests.act_as_owner();
select is((select count(*)::int from public.replies where post_id = :'lamp')
          + (select count(*)::int from public.likes where post_id = :'lamp')
          + (select count(*)::int from public.saves where post_id = :'lamp'), 0,
  'its replies, likes and saves go with it');

select * from finish();
rollback;

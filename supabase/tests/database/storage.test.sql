-- Photos: the post-images bucket takes images up to 5 MB, and users upload
-- only into their own folder, only while they may post.
begin;
\ir _helpers.psql
select plan(7);

select is((select file_size_limit from storage.buckets where id = 'post-images'), 5242880::bigint,
  'photos are limited to 5 MB');
select is((select allowed_mime_types from storage.buckets where id = 'post-images'),
  array['image/jpeg', 'image/png', 'image/heic', 'image/webp'], 'only images are accepted');

select tests.create_user('ana@example.com') as ana \gset
select tests.create_user('binh@example.com') as binh \gset
update public.profiles set terms_accepted_at = now() where id = :'ana';

select tests.act_as(:'ana');
select lives_ok(format($$insert into storage.objects (bucket_id, name, owner_id) values ('post-images', '%s/a.jpg', '%s')$$, :'ana', :'ana'),
  'users upload into their own folder');
select throws_ok(format($$insert into storage.objects (bucket_id, name, owner_id) values ('post-images', '%s/b.jpg', '%s')$$, :'binh', :'ana'),
  '42501', null, 'but not into someone else''s');
select throws_ok(format($$insert into storage.objects (bucket_id, name, owner_id) values ('other', '%s/c.jpg', '%s')$$, :'ana', :'ana'),
  '42501', null, 'or into another bucket');

select tests.act_as(:'binh');
select throws_ok(format($$insert into storage.objects (bucket_id, name, owner_id) values ('post-images', '%s/d.jpg', '%s')$$, :'binh', :'binh'),
  '42501', null, 'uploading needs the community terms');

select tests.act_as_owner();
update public.profiles set terms_accepted_at = now(), banned_at = now() where id = :'binh';
select tests.act_as(:'binh');
select throws_ok(format($$insert into storage.objects (bucket_id, name, owner_id) values ('post-images', '%s/e.jpg', '%s')$$, :'binh', :'binh'),
  '42501', null, 'banned users can''t upload');

select * from finish();
rollback;

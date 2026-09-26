-- Guards for every table, present and future: row-level security is on, and
-- the anon key alone can never write anything.
begin;
select plan(3);

select is_empty(
  $$select c.relname::text from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind in ('r', 'p') and not c.relrowsecurity$$,
  'every table in public has row-level security on');

select is_empty(
  $$select table_name::text || ' ' || privilege_type from information_schema.role_table_grants
    where table_schema = 'public' and grantee = 'anon'
      and privilege_type in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')$$,
  'the anon role has no write grants on any table');

select is_empty(
  $$select p.proname::text from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.prosecdef
      and not coalesce(array_to_string(p.proconfig, ',') like '%search_path=%', false)$$,
  'every security-definer function pins its search_path');

select * from finish();
rollback;

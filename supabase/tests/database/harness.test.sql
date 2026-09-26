-- Proves the test harness works: the stack started, migrations applied, and
-- pgTAP runs. Real schema and row-level security tests sit next to this file.
begin;
select plan(3);

select has_schema('public');
select has_schema('auth');
select has_schema('storage');

select * from finish();
rollback;

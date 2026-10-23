-- Business conflicts must not trigger PostgREST serialization retries.
-- Preserve the applied migration and existing function grants.
do $$
declare fn record; definition text; found_count integer:=0;
begin
 for fn in select p.oid from pg_catalog.pg_proc p join pg_catalog.pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname in ('append_security_score','guard_managed_portfolio_write','apply_portfolio_event') loop
  found_count:=found_count+1;
  definition:=pg_catalog.pg_get_functiondef(fn.oid);
  definition:=replace(definition,'errcode=''40001''','errcode=''PT409''');
  execute definition;
 end loop;
 if found_count<>3 then raise exception 'Expected exactly three score-tracking functions'; end if;
end $$;

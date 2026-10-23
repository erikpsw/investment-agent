-- User-private observations and atomic portfolio lifecycle management.
alter table public.user_portfolios add column if not exists revision bigint not null default 0;

create table if not exists public.user_security_score_snapshots (
 id uuid primary key default gen_random_uuid(), user_id text not null,
 market text not null check(market in ('CN','HK','US')), ticker text not null,
 mode text not null check(mode in ('balanced','conservative','aggressive')),
 config_fingerprint text not null, quote_as_of timestamptz not null,
 payload jsonb not null, created_at timestamptz not null default now(),
 unique(user_id,market,ticker,mode,config_fingerprint,quote_as_of)
);
create index if not exists score_history_owner on public.user_security_score_snapshots(user_id,market,ticker,quote_as_of desc,id desc);
create table if not exists public.user_position_events (
 id uuid primary key default gen_random_uuid(), user_id text not null, request_id uuid not null,
 request_payload jsonb not null, response_payload jsonb not null, created_at timestamptz not null default now(),
 unique(user_id,request_id)
);
create table if not exists public.user_position_management (
 user_id text not null, market text not null, ticker text not null, episode_id uuid not null default gen_random_uuid(),
 entry_snapshot jsonb, protection jsonb, closed_at timestamptz,
 primary key(user_id,market,ticker)
);
create table if not exists public.user_portfolio_risk_settings (
 user_id text primary key, settings jsonb not null, updated_at timestamptz not null default now()
);
alter table public.user_security_score_snapshots enable row level security;
alter table public.user_position_events enable row level security;
alter table public.user_position_management enable row level security;
alter table public.user_portfolio_risk_settings enable row level security;
revoke all on public.user_security_score_snapshots,public.user_position_events,public.user_position_management,public.user_portfolio_risk_settings from public,anon,authenticated;
grant select,insert,update,delete on public.user_security_score_snapshots,public.user_position_events,public.user_position_management,public.user_portfolio_risk_settings to service_role;

create or replace function public.append_security_score(p_owner text,p_snapshot jsonb) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare latest public.user_security_score_snapshots; saved public.user_security_score_snapshots; stamp timestamptz;
begin
 if coalesce(length(trim(p_owner)),0)=0 or coalesce(p_snapshot->>'market','') not in ('CN','HK','US') or
    coalesce(p_snapshot->>'mode','') not in ('balanced','conservative','aggressive') or
    coalesce(p_snapshot->>'ticker','')='' or coalesce(p_snapshot->>'config_fingerprint','')='' then
   raise exception 'invalid snapshot identity' using errcode='22023'; end if;
 stamp := (p_snapshot->>'quote_as_of')::timestamptz;
 if stamp is null or stamp>now()+interval '2 minutes' then raise exception 'invalid quote time' using errcode='22023'; end if;
 perform pg_advisory_xact_lock(hashtextextended(p_owner||':'||(p_snapshot->>'market')||':'||(p_snapshot->>'ticker')||':'||(p_snapshot->>'mode')||':'||(p_snapshot->>'config_fingerprint'),0));
 select * into latest from public.user_security_score_snapshots where user_id=p_owner and market=p_snapshot->>'market'
  and ticker=p_snapshot->>'ticker' and mode=p_snapshot->>'mode' and config_fingerprint=p_snapshot->>'config_fingerprint'
  order by quote_as_of desc limit 1;
 if latest.id is not null and latest.quote_as_of>=stamp then
  if latest.quote_as_of=stamp and (latest.payload - array['id','observed_at','request_id'])<>(p_snapshot - array['id','observed_at','request_id']) then
   raise exception 'same quote input conflict' using errcode='40001'; end if;
  return jsonb_build_object('saved',true,'inserted',false,'snapshot',latest.payload||jsonb_build_object('id',latest.id));
 end if;
 insert into public.user_security_score_snapshots(user_id,market,ticker,mode,config_fingerprint,quote_as_of,payload)
 values(p_owner,p_snapshot->>'market',p_snapshot->>'ticker',p_snapshot->>'mode',p_snapshot->>'config_fingerprint',stamp,p_snapshot - 'id') returning * into saved;
 return jsonb_build_object('saved',true,'inserted',true,'snapshot',saved.payload||jsonb_build_object('id',saved.id));
end $$;

create or replace function public.security_score_history(p_owner text,p_market text,p_ticker text,p_cursor uuid default null,p_limit int default 200,p_days int default 30) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare output jsonb; next_id uuid; cursor_time timestamptz; zone text;
begin
 if coalesce(length(trim(p_owner)),0)=0 or p_market not in ('CN','HK','US') or p_limit not between 1 and 200 or p_days not in (30,90) then
  raise exception 'invalid history query' using errcode='22023'; end if;
 zone:=case p_market when 'CN' then 'Asia/Shanghai' when 'HK' then 'Asia/Hong_Kong' else 'America/New_York' end;
 if p_cursor is not null then
  select quote_as_of into cursor_time from public.user_security_score_snapshots where id=p_cursor and user_id=p_owner and market=p_market and ticker=p_ticker;
  if cursor_time is null then raise exception 'invalid cursor' using errcode='22023'; end if;
 end if;
 with days as (select distinct timezone(zone,quote_as_of)::date d from public.user_security_score_snapshots
  where user_id=p_owner and market=p_market and ticker=p_ticker order by d desc limit p_days),
 selected as (select s.* from public.user_security_score_snapshots s where user_id=p_owner and market=p_market and ticker=p_ticker
  and timezone(zone,quote_as_of)::date in (select d from days)
  and (p_cursor is null or (quote_as_of,id)<(cursor_time,p_cursor)) order by quote_as_of desc,id desc limit p_limit+1),
 page as (select * from selected order by quote_as_of desc,id desc limit p_limit)
 select coalesce((select jsonb_agg(payload||jsonb_build_object('id',id) order by quote_as_of desc,id desc) from page),'[]'::jsonb),
  case when (select count(*) from selected)>p_limit then (select id from page order by quote_as_of asc,id asc limit 1) end into output,next_id;
 return jsonb_build_object('items',output,'next_cursor',next_id);
end $$;

create or replace function public.portfolio_management_state(p_owner text) returns jsonb
language sql security invoker set search_path='' as $$
 select jsonb_build_object('revision',coalesce((select revision from public.user_portfolios where user_id=p_owner),0),
  'positions',coalesce((select positions from public.user_portfolios where user_id=p_owner),'[]'::jsonb),
  'management',coalesce((select jsonb_object_agg(market||':'||ticker,to_jsonb(m)-'user_id') from public.user_position_management m where user_id=p_owner and closed_at is null),'{}'::jsonb),
  'settings',coalesce((select settings from public.user_portfolio_risk_settings where user_id=p_owner),'{}'::jsonb));
$$;

create or replace function public.save_portfolio_risk_settings(p_owner text,p_settings jsonb) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare k text; v numeric;
begin
 if coalesce(length(trim(p_owner)),0)=0 or jsonb_typeof(p_settings)<>'object' then raise exception 'invalid settings' using errcode='22023'; end if;
 for k in select jsonb_object_keys(p_settings) loop
  if k='mode' then
   if p_settings->>k not in ('balanced','conservative','aggressive') then raise exception 'invalid mode' using errcode='22023'; end if;
  elsif k in ('risk_budget_percent','position_cap_percent','total_risk_percent','one_way_cost') then
   if coalesce(p_settings->>k,'') !~ '^[0-9]+(\.[0-9]+)?$' then raise exception 'invalid numeric setting' using errcode='22023'; end if;
   v:=(p_settings->>k)::numeric;
   if (k='risk_budget_percent' and (v<0.1 or v>2)) or (k='position_cap_percent' and (v<1 or v>30)) or
      (k='total_risk_percent' and (v<0.1 or v>10)) or (k='one_way_cost' and (v<0 or v>0.05)) then
    raise exception 'out of bounds setting' using errcode='22023'; end if;
  else raise exception 'unknown risk setting' using errcode='22023'; end if;
 end loop;
 insert into public.user_portfolio_risk_settings(user_id,settings) values(p_owner,p_settings)
 on conflict(user_id) do update set settings=excluded.settings,updated_at=now();
 return p_settings;
end $$;

create or replace function public.guard_managed_portfolio_write() returns trigger language plpgsql security invoker set search_path='' as $$
begin
 if old.revision>0 and coalesce(current_setting('app.portfolio_rpc',true),'')<>'on' then
  raise exception 'managed portfolio requires revision-aware transaction' using errcode='40001'; end if;
 return new;
end $$;
drop trigger if exists guard_managed_portfolio_write on public.user_portfolios;
create trigger guard_managed_portfolio_write before update on public.user_portfolios for each row execute function public.guard_managed_portfolio_write();

-- Normalize legacy identifiers before matching managed positions; ambiguous duplicates fail closed.
create or replace function public.normalize_score_positions(p_positions jsonb) returns jsonb
language plpgsql immutable security invoker set search_path='' as $$
declare row jsonb; result jsonb:='[]'; market text; ticker text; currency text; code text; identities text[]:='{}'; identity text;
begin
 if coalesce(jsonb_typeof(p_positions),'')<>'array' then raise exception 'invalid positions' using errcode='22023'; end if;
 for row in select value from jsonb_array_elements(p_positions) loop
  market:=upper(coalesce(row->>'market','')); ticker:=trim(coalesce(row->>'ticker',''));
  if market='CASH' or upper(ticker) like 'CASH_%' then
   currency:=coalesce(row->>'currency',substring(upper(ticker) from 6)); market:='CASH'; ticker:='CASH_'||currency;
   if currency not in ('USD','HKD','CNY') then raise exception 'invalid currency' using errcode='22023'; end if;
  else
   currency:=case market when 'CN' then 'CNY' when 'HK' then 'HKD' when 'US' then 'USD' end;
   if currency is null or coalesce(row->>'currency',currency)<>currency then raise exception 'security currency mismatch' using errcode='22023'; end if;
   if market='CN' then
    ticker:=lower(ticker);
    if ticker ~ '^[0-9]{6}$' then ticker:=(case when left(ticker,1)='6' then 'sh' when left(ticker,1) in ('4','8','9') then 'bj' else 'sz' end)||ticker; end if;
    if ticker !~ '^(sh|sz|bj)[0-9]{6}$' then raise exception 'invalid CN ticker' using errcode='22023'; end if;
   elsif market='HK' then
    code:=regexp_replace(regexp_replace(lower(ticker),'^hk',''),'[.]hk$','');
    if code !~ '^[0-9]{4,5}$' then raise exception 'invalid HK ticker' using errcode='22023'; end if;
    ticker:='hk'||lpad(code,5,'0');
   else
    ticker:=upper(ticker);
    if ticker !~ '^[A-Z][A-Z0-9.-]{0,14}$' then raise exception 'invalid US ticker' using errcode='22023'; end if;
   end if;
  end if;
  identity:=market||':'||ticker;
  if identity=any(identities) then raise exception 'duplicate canonical security' using errcode='22023'; end if;
  identities:=array_append(identities,identity);
  if coalesce(row->>'quantity','') !~ '^[0-9]+([.][0-9]+)?$' or coalesce(row->>'avg_cost','0') !~ '^[0-9]+([.][0-9]+)?$' then raise exception 'invalid position number' using errcode='22023'; end if;
  result:=result||jsonb_build_array(row||jsonb_build_object('market',market,'ticker',ticker,'currency',currency));
 end loop;
 return result;
end $$;
revoke all on function public.normalize_score_positions(jsonb) from public,anon,authenticated;
grant execute on function public.normalize_score_positions(jsonb) to service_role;

create or replace function public.apply_portfolio_event(p_owner text,p_request_id uuid,p_expected_revision bigint,p_event jsonb) returns jsonb
language plpgsql security invoker set search_path='' as $$
<<apply_portfolio_event>>
declare doc public.user_portfolios; previous public.user_position_events; managed public.user_position_management;
 action text:=p_event->>'action'; market text:=p_event->>'market'; ticker text:=p_event->>'instrument_id'; currency text;
 positions jsonb; item jsonb; cash_item jsonb; snapshot jsonb; plan jsonb; result jsonb; old_plan jsonb;
 quantity numeric; price numeric; fee numeric; old_q numeric:=0; old_cost numeric:=0; cash numeric:=0; balance numeric;
 episode uuid; executed timestamptz; old_snapshot jsonb;
begin
 if coalesce(length(trim(p_owner)),0)=0 or p_request_id is null then raise exception 'missing owner/request' using errcode='22023'; end if;
 insert into public.user_portfolios(user_id,positions) values(p_owner,'[]') on conflict(user_id) do nothing;
 select * into doc from public.user_portfolios where user_id=p_owner for update;
 select * into previous from public.user_position_events where user_id=p_owner and request_id=p_request_id;
 if previous.id is not null then
  if previous.request_payload<>p_event then raise exception 'request key conflict' using errcode='40001'; end if;
  return previous.response_payload; end if;
 if p_expected_revision is null or doc.revision<>p_expected_revision then raise exception 'revision conflict' using errcode='40001'; end if;
 positions:=public.normalize_score_positions(doc.positions);
 if action in ('buy','sell','protection','adopt') then
  if coalesce(market,'') not in ('CN','HK','US') or coalesce(ticker,'')='' then raise exception 'invalid security' using errcode='22023'; end if;
  currency:=case market when 'CN' then 'CNY' when 'HK' then 'HKD' else 'USD' end;
  select value into item from jsonb_array_elements(positions) where value->>'ticker'=ticker and value->>'market'=market limit 1;
  old_q:=coalesce((item->>'quantity')::numeric,0); old_cost:=coalesce((item->>'avg_cost')::numeric,0);
  select * into managed from public.user_position_management where user_id=p_owner and user_position_management.market=apply_portfolio_event.market and user_position_management.ticker=apply_portfolio_event.ticker;
  if action='adopt' then
   if old_q<=0 then raise exception 'no existing position to track' using errcode='22023'; end if;
   if managed.episode_id is null or managed.closed_at is not null then
    insert into public.user_position_management(user_id,market,ticker,entry_snapshot) values(p_owner,market,ticker,null)
     on conflict on constraint user_position_management_pkey do update set episode_id=gen_random_uuid(),entry_snapshot=null,protection=null,closed_at=null;
   end if;
  elsif action='protection' then
   if old_q<=0 or managed.closed_at is not null or managed.episode_id is null or managed.episode_id::text<>p_event->>'episode_id' then raise exception 'episode mismatch' using errcode='22023'; end if;
   plan:=p_event->'plan';
   select payload into snapshot from public.user_security_score_snapshots where id=(plan->>'snapshot_id')::uuid and user_id=p_owner
    and user_security_score_snapshots.market=apply_portfolio_event.market and user_security_score_snapshots.ticker=apply_portfolio_event.ticker;
   if snapshot is null or coalesce(plan->>'config_fingerprint','')<>snapshot->>'config_fingerprint' or coalesce(plan->>'currency','')<>currency or coalesce(plan->>'price_basis','')<>'raw' or
    coalesce(plan->>'reference_price','') !~ '^[0-9]+(\.[0-9]+)?$' or coalesce(plan->>'quote_as_of','')='' or
    coalesce(plan->>'stop_loss','') !~ '^[0-9]+(\.[0-9]+)?$' or (plan->>'stop_loss')::numeric<=0 or
    (plan->>'stop_loss')::numeric>=(snapshot->>'price')::numeric or (plan->>'reference_price')::numeric<>(snapshot->>'price')::numeric or
    plan->>'quote_as_of'<>snapshot->>'quote_as_of' then raise exception 'invalid protection reference' using errcode='22023'; end if;
   if (snapshot->>'quote_as_of')::timestamptz<now()-interval '4 days' or
    snapshot->>'mode'<>coalesce((select settings->>'mode' from public.user_portfolio_risk_settings where user_id=p_owner),'balanced') or exists(select 1 from public.user_security_score_snapshots
    where user_id=p_owner and user_security_score_snapshots.market=apply_portfolio_event.market and user_security_score_snapshots.ticker=apply_portfolio_event.ticker
    and mode=snapshot->>'mode' and (quote_as_of>(snapshot->>'quote_as_of')::timestamptz or
     (quote_as_of=(snapshot->>'quote_as_of')::timestamptz and config_fingerprint<>snapshot->>'config_fingerprint'))) then
    raise exception 'stale protection reference' using errcode='40001'; end if;
   old_plan:=managed.protection;
   if old_plan is not null and ((old_plan->>'stop_loss')::numeric>(plan->>'stop_loss')::numeric or old_plan->>'price_basis'<>plan->>'price_basis'
    or abs((plan->>'reference_price')::numeric/(old_plan->>'reference_price')::numeric-1)>0.2) then
     raise exception 'protection cannot loosen or cross scales' using errcode='22023'; end if;
   update public.user_position_management set protection=plan||jsonb_build_object('confirmed_at',now(),'episode_id',managed.episode_id)
    where user_id=p_owner and user_position_management.market=apply_portfolio_event.market and user_position_management.ticker=apply_portfolio_event.ticker;
  else
   if coalesce(p_event->>'quantity','') !~ '^[0-9]+(\.[0-9]+)?$' or coalesce(p_event->>'price','') !~ '^[0-9]+(\.[0-9]+)?$' or
      coalesce(p_event->>'fee','0') !~ '^[0-9]+(\.[0-9]+)?$' then raise exception 'invalid trade number' using errcode='22023'; end if;
   quantity:=(p_event->>'quantity')::numeric; price:=(p_event->>'price')::numeric; fee:=coalesce((p_event->>'fee')::numeric,0);
   if quantity<=0 or price<=0 then raise exception 'nonpositive trade' using errcode='22023'; end if;
   executed:=coalesce((p_event->>'executed_at')::timestamptz,now());
   if executed>now()+interval '2 minutes' then raise exception 'future trade' using errcode='22023'; end if;
   if p_event->>'score_snapshot_id' is not null then
    select payload||jsonb_build_object('id',id) into snapshot from public.user_security_score_snapshots where id=(p_event->>'score_snapshot_id')::uuid
     and user_id=p_owner and user_security_score_snapshots.market=apply_portfolio_event.market and user_security_score_snapshots.ticker=apply_portfolio_event.ticker
     and quote_as_of<=executed and quote_as_of>=executed-interval '15 minutes'
     and created_at<=executed and coalesce((payload->>'observed_at')::timestamptz,created_at)<=executed;
    if snapshot is null then raise exception 'invalid entry score association' using errcode='22023'; end if;
   end if;
   select value into cash_item from jsonb_array_elements(positions) where value->>'ticker'='CASH_'||currency limit 1;
   cash:=coalesce((cash_item->>'quantity')::numeric,0);
   if action='buy' then
    balance:=cash-quantity*price-fee;
    if balance<0 then raise exception 'insufficient cash' using errcode='22023'; end if;
    item:=coalesce(item,jsonb_build_object('ticker',ticker,'market',market,'currency',currency,'name',coalesce(p_event->>'name',''),'notes',''))||
     jsonb_build_object('quantity',old_q+quantity,'avg_cost',(old_q*old_cost+quantity*price)/(old_q+quantity));
    if managed.episode_id is null or managed.closed_at is not null then
     episode:=gen_random_uuid();
     insert into public.user_position_management(user_id,market,ticker,episode_id,entry_snapshot,protection,closed_at)
      values(p_owner,market,ticker,episode,case when old_q=0 then snapshot end,null,null)
     on conflict on constraint user_position_management_pkey do update set episode_id=excluded.episode_id,entry_snapshot=excluded.entry_snapshot,protection=null,closed_at=null;
    end if;
   else
    if old_q<quantity then raise exception 'insufficient quantity' using errcode='22023'; end if;
    balance:=cash+quantity*price-fee;
    if balance<0 then raise exception 'insufficient cash for fee' using errcode='22023'; end if;
    item:=item||jsonb_build_object('quantity',old_q-quantity);
    if old_q=quantity then update public.user_position_management set closed_at=now() where user_id=p_owner and user_position_management.market=apply_portfolio_event.market and user_position_management.ticker=apply_portfolio_event.ticker; end if;
   end if;
   select coalesce(jsonb_agg(value),'[]'::jsonb) into positions from jsonb_array_elements(positions)
    where not (value->>'ticker'=ticker and value->>'market'=market) and value->>'ticker'<>'CASH_'||currency;
   if (item->>'quantity')::numeric>0 then positions:=positions||jsonb_build_array(item); end if;
   positions:=positions||jsonb_build_array(coalesce(cash_item,jsonb_build_object('ticker','CASH_'||currency,'market','CASH','currency',currency,'avg_cost',1))||jsonb_build_object('quantity',balance));
  end if;
 elsif action='replace_positions' then
  snapshot:=public.normalize_score_positions(p_event->'positions');
  for managed in select * from public.user_position_management where user_id=p_owner and closed_at is null loop
   select value into item from jsonb_array_elements(positions) where value->>'market'=managed.market and value->>'ticker'=managed.ticker limit 1;
   select value into cash_item from jsonb_array_elements(snapshot) where value->>'market'=managed.market and value->>'ticker'=managed.ticker limit 1;
   if cash_item is null or coalesce(cash_item->>'currency','')<>coalesce(item->>'currency','') or (cash_item->>'quantity')::numeric is distinct from (item->>'quantity')::numeric or (cash_item->>'avg_cost')::numeric is distinct from (item->>'avg_cost')::numeric then
    raise exception 'tracked positions require buy/sell events' using errcode='22023'; end if;
  end loop;
  positions:=snapshot;
 elsif action in ('set_cash','adjust_cash') then
  currency:=p_event->>'currency';
  if coalesce(currency,'') not in ('CNY','USD','HKD') or coalesce(p_event->>'amount','') !~ '^-?[0-9]+(\.[0-9]+)?$' then raise exception 'invalid cash event' using errcode='22023'; end if;
  select value into cash_item from jsonb_array_elements(positions) where value->>'ticker'='CASH_'||currency limit 1;
  balance:=(p_event->>'amount')::numeric+case when action='adjust_cash' then coalesce((cash_item->>'quantity')::numeric,0) else 0 end;
  if balance<0 then raise exception 'negative cash' using errcode='22023'; end if;
  select coalesce(jsonb_agg(value),'[]'::jsonb) into positions from jsonb_array_elements(positions) where value->>'ticker'<>'CASH_'||currency;
  positions:=positions||jsonb_build_array(coalesce(cash_item,jsonb_build_object('ticker','CASH_'||currency,'market','CASH','currency',currency,'avg_cost',1))||jsonb_build_object('quantity',balance));
 else raise exception 'unsupported managed event' using errcode='22023'; end if;
 perform set_config('app.portfolio_rpc','on',true);
 update public.user_portfolios set positions=apply_portfolio_event.positions,revision=revision+1,updated_at=now() where user_id=p_owner;
 result:=public.portfolio_management_state(p_owner);
 insert into public.user_position_events(user_id,request_id,request_payload,response_payload) values(p_owner,p_request_id,p_event,result);
 return result;
end $$;

revoke all on function public.append_security_score(text,jsonb),public.security_score_history(text,text,text,uuid,int,int),public.portfolio_management_state(text),public.save_portfolio_risk_settings(text,jsonb),public.apply_portfolio_event(text,uuid,bigint,jsonb),public.guard_managed_portfolio_write() from public,anon,authenticated;
grant execute on function public.append_security_score(text,jsonb),public.security_score_history(text,text,text,uuid,int,int),public.portfolio_management_state(text),public.save_portfolio_risk_settings(text,jsonb),public.apply_portfolio_event(text,uuid,bigint,jsonb),public.guard_managed_portfolio_write() to service_role;

create or replace function public.portfolio_latest_scores(p_owner text,p_mode text) returns jsonb
language sql security invoker set search_path='' as $$
 select coalesce(jsonb_object_agg(market||':'||ticker,payload||jsonb_build_object('id',id)),'{}'::jsonb)
 from (select distinct on (market,ticker) * from public.user_security_score_snapshots
  where user_id=p_owner and mode=p_mode order by market,ticker,quote_as_of desc,id desc) latest;
$$;
revoke all on function public.portfolio_latest_scores(text,text) from public,anon,authenticated;
grant execute on function public.portfolio_latest_scores(text,text) to service_role;

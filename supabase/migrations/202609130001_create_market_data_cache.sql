create table if not exists public.market_data_cache (
  cache_key text primary key,
  market text not null,
  ticker text not null,
  kind text not null,
  payload jsonb not null,
  fetched_at timestamptz not null default now(),
  constraint market_data_cache_key_not_blank check (length(btrim(cache_key)) > 0)
);

create index if not exists market_data_cache_market_ticker_idx
on public.market_data_cache (market, ticker);

alter table public.market_data_cache enable row level security;
revoke all on table public.market_data_cache from anon, authenticated;
grant all on table public.market_data_cache to service_role;

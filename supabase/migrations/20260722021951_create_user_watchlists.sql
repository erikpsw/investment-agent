create table if not exists public.user_watchlists (
  user_id text primary key,
  groups jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  constraint user_watchlists_user_id_not_blank check (length(btrim(user_id)) > 0),
  constraint user_watchlists_groups_is_array check (jsonb_typeof(groups) = 'array')
);

create or replace function public.set_user_watchlists_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_user_watchlists_updated_at on public.user_watchlists;
create trigger set_user_watchlists_updated_at
before update on public.user_watchlists
for each row execute function public.set_user_watchlists_updated_at();

alter table public.user_watchlists enable row level security;

revoke all on table public.user_watchlists from anon, authenticated;
revoke all on function public.set_user_watchlists_updated_at() from public, anon, authenticated;
grant all on table public.user_watchlists to service_role;

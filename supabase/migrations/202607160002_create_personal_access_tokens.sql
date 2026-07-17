create table if not exists public.user_personal_access_tokens (
  id uuid primary key,
  user_id text not null,
  name text not null,
  token_prefix text not null,
  token_hash text not null unique,
  scopes text[] not null default array['portfolio:read']::text[],
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  last_used_at timestamptz,
  revoked_at timestamptz,
  constraint user_personal_access_tokens_user_id_not_blank check (length(btrim(user_id)) > 0),
  constraint user_personal_access_tokens_name_not_blank check (length(btrim(name)) > 0),
  constraint user_personal_access_tokens_name_length check (length(name) <= 80),
  constraint user_personal_access_tokens_prefix_not_blank check (length(btrim(token_prefix)) > 0),
  constraint user_personal_access_tokens_hash_not_blank check (length(btrim(token_hash)) = 64),
  constraint user_personal_access_tokens_expiry check (expires_at > created_at)
);

create index if not exists user_personal_access_tokens_user_id_idx
  on public.user_personal_access_tokens (user_id, created_at desc);

alter table public.user_personal_access_tokens enable row level security;

revoke all on table public.user_personal_access_tokens from anon, authenticated;
grant all on table public.user_personal_access_tokens to service_role;

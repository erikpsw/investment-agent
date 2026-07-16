# PAT, Hot Markets, and A-Share ETF Design

## Goal

Deliver three independently verifiable capabilities:

1. Replace long-lived Auth0 access-token usage with revocable 90-day Personal Access Tokens (PATs) for remote MCP access.
2. Replace the dashboard's fixed stock cards with dynamic A-share, Hong Kong, and U.S. hot-stock rankings.
3. Allow A-share ETFs in search and portfolios, and show a daily-updated A-share hot-ETF sector list.

The implementation order is PAT, hot-stock dashboard, then A-share ETFs. Each stage must remain usable if a later stage is delayed.

## Personal Access Tokens

### Security Model

A PAT has the format `eai_pat_<random-secret>`. The server returns the complete token exactly once at creation. Supabase stores only a SHA-256 hash, a short display prefix, and metadata; neither the browser nor the database can retrieve the original secret later.

PATs expire 90 days after creation and can be revoked immediately. The initial scope is read-only: `portfolio:read` permits MCP portfolio details and AI portfolio analysis, but not portfolio writes or PAT management. Only an interactive Auth0 session can create, list, or revoke PATs. A PAT cannot mint another PAT.

The table `public.user_personal_access_tokens` contains:

- `id uuid primary key`
- `user_id text not null`
- `name text not null`
- `token_prefix text not null`
- `token_hash text unique not null`
- `scopes text[] not null default '{portfolio:read}'`
- `created_at timestamptz not null`
- `expires_at timestamptz not null`
- `last_used_at timestamptz null`
- `revoked_at timestamptz null`

RLS remains enabled with no browser-role policies. The service-role backend always filters management operations by the verified Auth0 `sub`.

### Authentication Flow

FastAPI becomes the authoritative bearer-token validator. Tokens beginning with `eai_pat_` are hashed and looked up in Supabase; all other bearer tokens follow the existing Auth0 validation path. Validation rejects missing, expired, revoked, or incorrectly scoped PATs with HTTP 401 or 403 as appropriate and updates `last_used_at` without blocking the request if that metadata update fails.

The Next.js MCP adapter asks FastAPI to validate the presented bearer token and receives only the authenticated subject, scopes, and optional expiry. It then forwards the original token to the existing protected portfolio endpoint, preserving the current double-validation boundary. PAT validation logic is not duplicated in TypeScript.

Auth0-protected management endpoints are:

- `GET /api/portfolio/tokens`: list token metadata, never token hashes or secrets.
- `POST /api/portfolio/tokens`: create a named 90-day token and return the secret once.
- `DELETE /api/portfolio/tokens/{id}`: revoke a token owned by the current user.
- `GET /api/auth/verify`: validate Auth0 or PAT credentials for the MCP adapter.

The portfolio page replaces the temporary Auth0-token copy workflow with a PAT manager. It explains the 90-day expiry, displays active/revoked/expired state and last-use time, provides create and revoke actions, and displays a newly created secret in a one-time copy panel.

## Hot-Stock Dashboard

### Ranking

The dashboard exposes separate A-share, Hong Kong, and U.S. sections with six stocks per market. Users can switch between `综合热度`, `成交额`, and `涨幅` ranking modes.

The default composite score uses percentile ranks within each market universe:

- 45% trading amount
- 25% absolute price movement, capped to limit one-day outliers
- 20% turnover rate where the source provides it
- 10% volume ratio where the source provides it

When turnover rate or volume ratio is unavailable, its weight is redistributed proportionally across available factors. Candidates with no valid price or amount, suspended securities, ST/delisting names, and the bottom liquidity decile are excluded. The API returns the score inputs so the ranking is explainable and testable.

### Data and Refresh

A market-specific scanner normalizes provider data into one `HotStock` contract. A shares reuse the complete Eastmoney snapshot and add trading amount to the persisted fields. Hong Kong data uses the existing Hong Kong quote providers, and U.S. data uses the existing Yahoo provider. Provider details remain behind scanner interfaces so a failed source can be replaced without changing the API or page.

`GET /api/market/hot-stocks?market=CN|HK|US&mode=hot|amount|gainers&limit=6` returns ranked items, `generated_at`, `source`, and `stale`.

During an open market session, the backend may refresh an in-memory ranking at most once every 10 minutes. The scheduled GitHub Actions job persists one complete valid snapshot after each relevant market day. If live refresh fails, the endpoint serves the last valid persisted snapshot with `stale: true`; it does not silently replace dynamic rankings with hard-coded cards.

The homepage uses one query per market, keeps each market's loading/error state independent, displays data time and stale status, and links every card to the existing stock-detail route.

## A-Share ETFs and Hot Sectors

### Portfolio Support

Search results gain an `instrument_type` value of `stock` or `etf`. A-share ETF ticker normalization accepts Shanghai ETF prefixes such as `510`, `511`, `512`, `513`, `515`, `516`, `518`, `560`, `561`, `562`, `563`, `588`, and Shenzhen ETF prefixes such as `159`. Search results remain selectable through the existing portfolio autocomplete, and an ETF position uses the same quantity, average cost, native currency, quote enrichment, CNY valuation, profit/loss, and AI analysis flow as a stock position.

Validation is capability-based rather than a hard-coded stock-only prefix check: if search resolves the instrument and the quote provider returns a valid market price, the portfolio accepts it. This avoids blocking newly issued ETF prefixes.

### Hot ETF Sectors

The first release covers A-share ETFs only. The scanner collects exchange-traded funds, maps each fund to a normalized theme using provider category metadata with a name-based fallback, and excludes money-market, bond, commodity, QDII, leveraged, inverse, and cross-border products from the sector-equity ranking.

Each theme is represented by its most liquid eligible ETF. Theme heat is calculated from:

- 40% trading amount percentile
- 30% daily return percentile
- 20% turnover or volume-ratio percentile
- 10% five-day momentum percentile when history is available

`GET /api/etfs/hot-sectors?limit=10` returns theme, representative ETF, price, daily return, amount, five-day return, heat score, data time, source, and stale status. The investment portfolio page shows this list beside the add-position workflow with an `加入投资组合` action that pre-fills the standard position editor; it never invents quantity or average cost.

ETF rankings are regenerated by the existing weekday snapshot workflow after the A-share close at 15:15 China Standard Time. During trading hours, displayed prices may refresh every 10 minutes, while the daily theme ranking remains stable until the next successful snapshot. A failed update keeps the previous snapshot and marks it stale.

## Error Handling and Observability

- PAT secrets and hashes never appear in logs, API list responses, MCP output, or analytics events.
- PAT creation fails atomically if the database write fails; the UI must not display an unpersisted secret.
- Market endpoints report source, generation time, and stale state.
- A failed market does not prevent the other two dashboard sections from rendering.
- Snapshot jobs validate minimum row counts and required fields before replacing a previous snapshot.
- API failures use concise user-facing Chinese messages and retain the last successfully rendered data where possible.

## Testing and Acceptance

Backend tests cover PAT creation, one-time secret response, hash-only persistence, 90-day expiry, revocation, ownership isolation, scope enforcement, Auth0 fallback, and MCP validation. A real MCP smoke test must retrieve the authenticated user's portfolio with a PAT and fail after that PAT is revoked.

Ranking tests use fixed fixtures to prove filtering, score order, missing-factor redistribution, ranking modes, stale fallback, ETF theme grouping, and representative-ETF selection. API tests verify response contracts for all three markets and A-share ETF sectors.

Frontend tests cover PAT one-time display and revoke state, independent market loading/error states, ranking-mode switching, ETF autocomplete selection, and hot-ETF prefill. The production build must pass, and browser verification must confirm the portfolio PAT flow, three dashboard market sections, ETF price and profit/loss display after save, and hot-ETF prefill.

The feature is accepted when:

1. A signed-in user can create a 90-day PAT, use it with `/mcp`, revoke it, and observe subsequent MCP authentication fail.
2. The homepage displays dynamic, timestamped A-share, Hong Kong, and U.S. hot-stock lists without fixed stock constants.
3. An A-share ETF can be found, selected, saved, priced, and included in CNY portfolio totals and AI analysis.
4. The portfolio page displays a timestamped A-share hot-ETF sector list updated by the weekday snapshot workflow.

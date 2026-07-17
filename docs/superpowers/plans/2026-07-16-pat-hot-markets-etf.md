# PAT, Hot Markets, and A-Share ETF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add revocable 90-day PAT authentication for MCP, dynamic A/HK/US hot-stock dashboard data, and A-share ETF portfolio discovery with daily hot-sector rankings.

**Architecture:** FastAPI remains the identity and portfolio authorization boundary, with a hash-only Supabase PAT store and a verification endpoint used by the Next.js MCP adapter. Market scanners normalize provider snapshots behind stable API contracts; the dashboard and portfolio page consume those contracts independently and preserve stale snapshots when providers fail.

**Tech Stack:** FastAPI, Pydantic, Supabase PostgREST, Python `unittest`, Next.js 16, React 19, TanStack Query, TypeScript node tests, GitHub Actions, Eastmoney/Tencent/Yahoo market data.

## Global Constraints

- PAT secrets use `eai_pat_` plus at least 32 random bytes, are returned once, and are stored only as SHA-256 hashes.
- PAT lifetime is exactly 90 days and initial scope is exactly `portfolio:read`.
- PATs cannot write portfolios or create, list, or revoke PATs.
- Auth0 `sub` remains the only user ownership key; requests never accept `user_id`.
- A/HK/US dashboard sections fail independently and expose source, generation time, and stale state.
- Hot-stock composite weights are amount 45%, absolute movement 25%, turnover 20%, and volume ratio 10%, redistributed when factors are missing.
- A-share ETF hot-sector weights are amount 40%, daily return 30%, turnover or volume ratio 20%, and five-day momentum 10%.
- A-share hot-ETF ranking updates after the weekday close at 15:15 China Standard Time; intraday prices may refresh every 10 minutes.
- Do not stage or commit implementation files automatically because the current worktree contains required pre-existing changes.

---

### Task 1: PAT Store and Database Schema

**Files:**
- Create: `tests/test_pat_store.py`
- Create: `data/pat_store.py`
- Create: `supabase/migrations/202607160002_create_personal_access_tokens.sql`

**Interfaces:**
- Produces: `PersonalAccessTokenStore.create(user_id, name) -> CreatedPersonalAccessToken`, `list(user_id) -> list[PersonalAccessTokenRecord]`, `revoke(user_id, token_id) -> bool`, and `authenticate(secret) -> PersonalAccessTokenIdentity | None`.
- Produces: `eai_pat_<urlsafe secret>` and stores `sha256(secret).hexdigest()` only.

- [ ] **Step 1: Write failing store tests**

Cover exact 90-day expiry, one-time secret return, hash-only persisted rows, ownership-filtered list/revoke, expired/revoked rejection, and non-blocking `last_used_at` updates using an in-memory fake table client.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests.test_pat_store -v`

Expected: FAIL because `investment.data.pat_store` does not exist.

- [ ] **Step 3: Implement the minimal PAT domain and Supabase store**

Use `secrets.token_urlsafe(32)`, `hashlib.sha256`, timezone-aware UTC datetimes, constant-time hash comparison where applicable, and server-side user filters on every management operation. Map storage failures to a dedicated `PersonalAccessTokenStorageError`.

- [ ] **Step 4: Add the migration**

Create `public.user_personal_access_tokens` with the design fields, checks for nonblank owner/name/prefix/hash, `expires_at > created_at`, RLS enabled, browser grants revoked, service-role grant, and indexes on `user_id` and `token_hash`.

- [ ] **Step 5: Run focused tests and SQL checks**

Run: `python -m unittest tests.test_pat_store -v`

Expected: all PAT store tests PASS. Run `git diff --check -- data/pat_store.py tests/test_pat_store.py supabase/migrations/202607160002_create_personal_access_tokens.sql` and expect no output.

### Task 2: Dual Auth0/PAT API Authentication

**Files:**
- Create: `tests/test_pat_auth.py`
- Create: `api/routes/tokens.py`
- Modify: `api/auth.py`
- Modify: `api/index.py`
- Modify: `api/routes/portfolio.py`

**Interfaces:**
- Produces: `AuthenticatedUser(sub, email, auth_type, scopes)`.
- Produces: `get_current_user`, `get_auth0_user`, and `require_scope("portfolio:read")` dependencies.
- Produces: `GET /api/auth/verify`, `GET|POST|DELETE /api/portfolio/tokens` contracts from the design.

- [ ] **Step 1: Write failing route/auth tests**

Assert PAT read and analysis succeed, PAT portfolio PUT returns 403, PAT management returns 403, Auth0 management succeeds, token list excludes hash/secret, revoke is owner-scoped, and `/api/auth/verify` returns only subject/scopes/expiry.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_pat_auth -v`

Expected: FAIL because PAT-aware authentication and token routes are absent.

- [ ] **Step 3: Implement dual-token authentication**

Dispatch bearer values beginning with `eai_pat_` to the PAT store and all others to `Auth0TokenVerifier`. Keep `get_auth0_user` strict for management routes and use scope dependencies on PAT-readable portfolio routes. Return 401 for invalid/expired/revoked credentials and 403 for valid credentials lacking capability.

- [ ] **Step 4: Add management and verification routes**

Create Pydantic request/response models, trim token names, cap names at 80 characters, register the router in `api/index.py`, and ensure secrets only appear in the successful create response.

- [ ] **Step 5: Verify backend auth regression suite**

Run: `python -m unittest tests.test_pat_store tests.test_pat_auth tests.test_auth0_verifier tests.test_portfolio_auth tests.test_portfolio_store -v`

Expected: all tests PASS.

### Task 3: MCP PAT Support and Portfolio PAT Manager

**Files:**
- Modify: `web/tests/mcp-route.test.ts`
- Modify: `web/src/app/mcp/route.ts`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/app/portfolio/page.tsx`

**Interfaces:**
- MCP consumes `GET /api/auth/verify` with the caller bearer token.
- Frontend consumes `listPersonalAccessTokens`, `createPersonalAccessToken(name)`, and `revokePersonalAccessToken(id)`.

- [ ] **Step 1: Write failing MCP verification tests**

Add a test where FastAPI verification accepts an `eai_pat_` token and MCP tool discovery/call succeeds, plus invalid and revoked verification responses that leave MCP unauthorized.

- [ ] **Step 2: Run MCP tests and verify RED**

Run: `npm run test:mcp` from `web`.

Expected: the new PAT scenario FAILS because MCP only calls `verifyAuth0AccessToken`.

- [ ] **Step 3: Route MCP validation through FastAPI**

Replace direct Auth0-only verification in the MCP route with a no-store bearer request to `/api/auth/verify`, map its response to MCP `AuthInfo`, and continue forwarding the original token to portfolio endpoints.

- [ ] **Step 4: Add PAT API client and UI**

Add typed token metadata/create responses. Replace the temporary Auth0-token copy card with a name input, create action, one-time copy panel, active/expired/revoked list, expiry and last-used timestamps, and revoke action. Do not persist the returned secret in local storage or React Query cache.

- [ ] **Step 5: Verify MCP and frontend compilation**

Run from `web`: `npm run test:mcp`, `npm run lint`, and `npm run build`.

Expected: each exits 0.

### Task 4: Explainable Three-Market Hot-Stock API

**Files:**
- Create: `tests/test_hot_stocks.py`
- Create: `data/hot_stocks.py`
- Create: `api/routes/hot_stocks.py`
- Modify: `api/index.py`
- Modify: `data/market_scanner.py`
- Modify: `scripts/update_market_snapshot.mjs`
- Modify: `.github/workflows/market-snapshot.yml`

**Interfaces:**
- Produces: `rank_hot_stocks(rows, mode, limit) -> list[dict]` and `get_hot_stocks(market, mode, limit) -> HotStockSnapshot`.
- Produces: `GET /api/market/hot-stocks?market=CN|HK|US&mode=hot|amount|gainers&limit=6`.

- [ ] **Step 1: Write failing pure ranking tests**

Use fixtures to assert liquidity filtering, ST/suspended exclusion, percentile score order, capped movement, missing-factor redistribution, amount/gainers modes, limit bounds, and independent stale snapshot fallback.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_hot_stocks -v`

Expected: FAIL because the ranking module and endpoint do not exist.

- [ ] **Step 3: Implement normalized ranking and providers**

Add a `HotStockSnapshot` contract and market provider functions. Reuse the complete CN snapshot, existing HK provider, and existing Yahoo provider; cache live results for 600 seconds and read the last valid market snapshot on provider failure. Include raw factor values and normalized score components in each item.

- [ ] **Step 4: Persist required snapshot fields**

Add `amount` to CN Python and JavaScript snapshot normalization. Extend the snapshot script and workflow outputs for HK and US hot lists only after validating nonempty rows and required fields; preserve prior files on invalid responses.

- [ ] **Step 5: Register and verify API**

Validate market/mode enums and `1 <= limit <= 20`, register the router, and run `python -m unittest tests.test_hot_stocks -v` plus the full backend suite.

Expected: all tests PASS.

### Task 5: Three-Market Dashboard UI

**Files:**
- Create: `web/src/components/hot-stock-section.tsx`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/app/page.tsx`

**Interfaces:**
- Consumes: `api.getHotStocks(market, mode, 6)`.
- Produces: independent CN/HK/US sections and `hot|amount|gainers` mode control.

- [ ] **Step 1: Add a failing render/data-contract test where practical**

Extract market labels, mode values, and stale/fresh display logic into exported pure helpers and test that each market retains independent state and timestamp/source labels.

- [ ] **Step 2: Remove fixed cards and implement the sections**

Delete `HOT_STOCKS`, add typed API responses, render six ranked items per market, show score inputs, timestamp/source/stale badge, and preserve stock-detail links. One market error renders a retry action only in that section.

- [ ] **Step 3: Verify frontend quality**

Run from `web`: `npm run lint` and `npm run build`.

Expected: each exits 0 and the build includes `/` without TypeScript errors.

### Task 6: A-Share ETF Discovery and Portfolio Compatibility

**Files:**
- Create: `tests/test_etf_discovery.py`
- Modify: `data/stock_search.py`
- Modify: `data/stock_fetcher.py`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/app/portfolio/page.tsx`

**Interfaces:**
- Search results produce `instrument_type: "stock" | "etf"`.
- Existing quote and portfolio position contracts accept resolved `sh|sz` ETF tickers without a stock-only prefix gate.

- [ ] **Step 1: Write failing ETF search and quote tests**

Cover representative Shanghai and Shenzhen ETFs, capability-based acceptance of a valid new prefix, `instrument_type`, ticker normalization, and a saved ETF receiving current price and CNY profit/loss enrichment.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_etf_discovery -v`

Expected: at least ETF search/type assertions FAIL.

- [ ] **Step 3: Implement ETF discovery and quote compatibility**

Extend exchange data/search normalization to include ETFs and type metadata. Keep portfolio payload backward compatible when `instrument_type` is absent. Remove only stock-prefix validation that blocks a successfully resolved and priced ETF.

- [ ] **Step 4: Update portfolio autocomplete**

Display an ETF badge in results, preserve the selected ticker/name/market, and use the existing position editor for quantity and average cost. Do not add ETF-specific valuation math.

- [ ] **Step 5: Verify focused and regression tests**

Run the ETF tests, portfolio tests, frontend lint, and frontend build.

Expected: all commands exit 0.

### Task 7: Daily A-Share Hot-ETF Sectors

**Files:**
- Create: `tests/test_hot_etfs.py`
- Create: `data/etf_scanner.py`
- Create: `api/routes/etfs.py`
- Create: `web/src/components/hot-etf-sectors.tsx`
- Modify: `api/index.py`
- Modify: `scripts/update_market_snapshot.mjs`
- Modify: `.github/workflows/market-snapshot.yml`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/app/portfolio/page.tsx`

**Interfaces:**
- Produces: `rank_hot_etf_sectors(rows, limit) -> list[dict]`.
- Produces: `GET /api/etfs/hot-sectors?limit=10` and snapshot `storage/market/hot-etfs.json`.
- UI produces an add action that pre-fills, but does not save, a standard portfolio position.

- [ ] **Step 1: Write failing ETF ranking tests**

Use fixed fixtures to prove exclusions, theme mapping, percentile weights, five-day-momentum fallback, one representative ETF per theme, most-liquid representative selection, and stale snapshot fallback.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_hot_etfs -v`

Expected: FAIL because the ETF scanner does not exist.

- [ ] **Step 3: Implement scanner, API, and scheduled snapshot**

Normalize eligible A-share equity ETFs, map provider categories then deterministic name fallbacks, rank themes, validate snapshot rows before write, and extend the weekday 07:15 UTC workflow to persist `hot-etfs.json` after the A-share close.

- [ ] **Step 4: Implement portfolio-page hot ETF panel**

Display ten themes with representative ETF, heat, return, amount, data time, and stale state. `Add to portfolio` opens/prefills the existing editor with ticker/name/market only.

- [ ] **Step 5: Verify focused functionality**

Run ETF scanner tests, all backend tests, frontend lint, and frontend build.

Expected: all commands exit 0.

### Task 8: End-to-End Verification and Documentation

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Documents: PAT lifecycle, MCP bearer setup, snapshot schedule, provider/fallback behavior, and API examples without secrets.

- [ ] **Step 1: Run complete automated verification**

Run: `python -m unittest discover -s tests -v`, `python -m compileall api data`, and from `web`: `npm run test:auth`, `npm run test:mcp`, `npm run lint`, `npm run build`.

Expected: every command exits 0 with no test failures or compilation errors.

- [ ] **Step 2: Apply production database migration**

Apply `202607160002_create_personal_access_tokens.sql` to the configured Supabase project, inspect table grants/RLS, and verify no `anon` or `authenticated` policy grants access.

- [ ] **Step 3: Deploy and run production smoke tests**

Create a PAT from the signed-in portfolio page, call MCP `get_portfolio_details`, revoke the PAT, and verify the same MCP bearer is rejected. Verify the homepage has timestamped CN/HK/US hot sections and the portfolio page can prefill, save, price, and analyze an A-share ETF.

- [ ] **Step 4: Inspect final scope**

Run `git diff --check` and `git status --short`; review every changed file against this plan and report any uncommitted pre-existing changes separately from feature changes.

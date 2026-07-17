# Auth0 Cloud Portfolio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Auth0 login and user-scoped Supabase persistence to the existing portfolio workflow.

**Architecture:** Next.js owns the Auth0 encrypted session and supplies an Auth0 API access token to the browser. FastAPI validates that token, derives the user solely from `sub`, and uses a server-only Supabase client to persist one JSON portfolio document per user.

**Tech Stack:** Next.js 16, React 19, `@auth0/nextjs-auth0`, `mcp-handler`, MCP Streamable HTTP, FastAPI, PyJWT RS256/JWKS validation, Supabase PostgREST, Python `unittest`/FastAPI TestClient.

## Global Constraints

- Never accept `user_id` from a portfolio request.
- Never expose `SUPABASE_SERVICE_KEY` to browser code or `NEXT_PUBLIC_*` variables.
- Require issuer, audience, signature, and expiry validation for Auth0 tokens.
- Keep the existing portfolio endpoint paths and position payload shape.
- Use Auth0 `sub` as the exact database owner key.

---

### Task 1: Authenticated Portfolio API Contract

**Files:**
- Create: `tests/test_portfolio_auth.py`
- Create: `api/auth.py`
- Modify: `api/routes/portfolio.py`
- Modify: `requirements.txt`
- Modify: `requirements-vercel.txt`

**Interfaces:**
- Produces: `AuthenticatedUser(sub: str, email: str | None)` and `get_current_user(request) -> AuthenticatedUser`.
- Consumes: `Authorization: Bearer <JWT>` and `AUTH0_DOMAIN`/`AUTH0_AUDIENCE`.

- [x] Write tests asserting missing tokens return 401 and an injected authenticated identity reaches all portfolio handlers.
- [x] Run `python -m unittest tests.test_portfolio_auth -v` and confirm the unauthenticated contract fails before implementation.
- [x] Implement cached JWKS RS256 validation and FastAPI dependency injection.
- [x] Protect all three portfolio endpoints and pass `current_user.sub` to the service.
- [x] Run the focused tests and confirm they pass.

### Task 2: User-Scoped Supabase Store

**Files:**
- Create: `tests/test_portfolio_store.py`
- Create: `data/portfolio_store.py`
- Modify: `data/portfolio.py`

**Interfaces:**
- Produces: `PortfolioStore.load(user_id) -> PortfolioDocument` and `PortfolioStore.save(user_id, positions) -> PortfolioDocument`.
- Consumes: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and table `user_portfolios`.

- [x] Write tests with an in-memory fake proving two Auth0 subjects cannot observe or overwrite each other's positions.
- [x] Run `python -m unittest tests.test_portfolio_store -v` and verify failure because the store interface is absent.
- [x] Implement Supabase load/upsert with service-key configuration validation and normalized response handling.
- [x] Refactor `PortfolioService.get_positions`, `save_positions`, and `analyze` to require `user_id` and load through the store.
- [x] Run both backend test modules and confirm user isolation and existing valuation behavior pass.

### Task 3: Supabase Schema

**Files:**
- Create: `supabase/migrations/202607160001_create_user_portfolios.sql`

**Interfaces:**
- Produces: `public.user_portfolios(user_id text primary key, positions jsonb, updated_at timestamptz)`.
- Consumes: server-side service-role access only.

- [x] Write SQL that creates the table, update timestamp trigger, enables RLS, and revokes browser roles.
- [x] Apply the migration to the Supabase project matched by `SUPABASE_URL`.
- [x] Query table metadata and run Supabase security advisors to verify RLS and grants.

### Task 4: Next.js Auth0 Session

**Files:**
- Create: `web/src/lib/auth0.ts`
- Create: `web/src/proxy.ts`
- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Modify: `web/src/app/layout.tsx`
- Modify: `web/src/components/sidebar.tsx`

**Interfaces:**
- Produces: Auth0 routes `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/profile`, `/auth/access-token` and visible session controls.
- Consumes: Auth0 environment variables listed in the design.

- [x] Install pinned `@auth0/nextjs-auth0` and inspect its current exported types.
- [x] Configure `Auth0Client` with explicit audience/scope and route paths.
- [x] Add the Next.js 16 proxy entry and SDK provider required by the installed version.
- [x] Add sidebar login/logout and current-user display without exposing tokens.
- [x] Run `npm run lint` and `npm run build`; fix all errors introduced by this task.

### Task 5: Authenticated Browser API Calls

**Files:**
- Create: `web/src/lib/auth-token.ts`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/app/portfolio/page.tsx`

**Interfaces:**
- Produces: automatic Bearer injection for protected portfolio requests.
- Consumes: SDK `/auth/access-token` response `{ token: string, expires_at: number }` and 401 responses.

- [x] Add a token helper that obtains the session-backed access token and represents signed-out state explicitly.
- [x] Mark portfolio API methods as authenticated and attach the token without changing public market-data calls.
- [x] Render a login action when portfolio loading receives 401; preserve the current editor for authenticated users.
- [x] Run lint, TypeScript build, and browser verification against the signed-out state.

### Task 6: Authenticated Remote MCP

**Files:**
- Create: `web/src/app/mcp/route.ts`
- Create: `web/src/app/.well-known/oauth-protected-resource/route.ts`
- Create: `web/src/lib/auth0-token.ts`
- Modify: `web/package.json`
- Modify: `web/package-lock.json`

**Interfaces:**
- Produces: authenticated Streamable HTTP MCP endpoint `/mcp` and tool `get_portfolio_details(include_analysis?: boolean)`.
- Consumes: Auth0 RS256 access token and the protected FastAPI portfolio endpoints.

- [x] Add a token verifier shared by MCP authorization that validates issuer, audience, signature, and expiry.
- [x] Add a failing route test or protocol smoke script proving `/mcp` rejects missing authorization.
- [x] Implement `get_portfolio_details` without a `user_id` input and forward the caller token to FastAPI.
- [x] Publish OAuth Protected Resource Metadata pointing at the configured Auth0 issuer.
- [x] Run an MCP initialize/tools-list/tools-call smoke test and confirm the returned schema has no user identifier.

### Task 7: Configuration And End-To-End Verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Documents: Auth0 callback/logout/web-origin values and required Vercel variables.

- [x] Document local and production environment keys without copying secrets.
- [x] Run all focused backend tests, Python compilation, frontend lint, and production build.
- [x] Start both services and verify `/portfolio` presents login while signed out and protected API returns 401 without a token.
- [ ] With configured Auth0 credentials, verify login callback, cloud save, reload persistence, and logout.

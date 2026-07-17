# Auth0 Cloud Portfolio Design

## Goal

Require deployed users to sign in with Auth0 and persist each user's investment portfolio in Supabase so portfolios survive serverless deployments and remain isolated between users.

## Authentication

The Next.js application uses `@auth0/nextjs-auth0` with the same route model as `E:/programming/fin-agent`: `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/profile`, and `/auth/access-token`. By default it reuses that application's `openid profile email` access token and validates it through Auth0 `/userinfo`. When `AUTH0_AUDIENCE` is configured, FastAPI and MCP instead validate the RS256 JWT locally.

The browser never sends a user ID. It obtains an access token from the Auth0 SDK's session-backed `/auth/access-token` endpoint and sends it as `Authorization: Bearer <token>` to protected FastAPI endpoints. FastAPI validates RS256 signature, issuer, audience, and expiry against the tenant JWKS. The validated JWT `sub` claim is the only portfolio owner identifier.

## Cloud Storage

Supabase stores one atomic portfolio document per Auth0 subject in `public.user_portfolios`:

- `user_id text primary key`
- `positions jsonb not null default '[]'::jsonb`
- `updated_at timestamptz not null default now()`

The table is not exposed to browser clients. RLS is enabled with no `anon` or `authenticated` policies, and access is revoked from those roles. FastAPI uses `SUPABASE_SERVICE_KEY` server-side and always filters reads and writes by the verified Auth0 `sub`.

## API

The existing endpoints remain stable:

- `GET /api/portfolio/positions`
- `PUT /api/portfolio/positions`
- `POST /api/portfolio/analyze`

All three require a valid Auth0 access token. Missing or invalid tokens return 401. Missing cloud configuration returns 503 without leaking credentials. The response no longer exposes a server filesystem path; it returns `storage: "supabase"` and the persisted timestamp.

There is no ordinary endpoint that accepts an arbitrary `user_id`. This prevents insecure direct-object access. A future administrator API must be separate, role-gated, and audited.

## Frontend

Next.js middleware/proxy mounts the Auth0 routes. The application shell exposes login/logout state. The portfolio page requires a session: signed-out users see a login action, while signed-in users load and save their own cloud portfolio. The API client obtains and attaches an access token automatically and redirects to login when authentication is absent.

## Remote MCP

Next.js exposes a Streamable HTTP MCP endpoint at `/mcp`. The endpoint requires the same Auth0 Bearer token through the MCP authorization wrapper and publishes OAuth Protected Resource Metadata at `/.well-known/oauth-protected-resource`.

The MCP server provides `get_portfolio_details`. It accepts no user identifier. The tool forwards the authenticated connection token to FastAPI and returns the caller's saved positions enriched with current price, cost, market value, floating profit/loss, profit/loss percentage, position weight, and portfolio totals. An optional `include_analysis` flag invokes the existing portfolio analysis workflow for news, technical signals, and AI position-management commentary.

The MCP layer and FastAPI both validate the token. This deliberate double validation keeps the MCP adapter from becoming a trusted identity proxy and preserves FastAPI as the authoritative portfolio access boundary.

## Local And Deployment Configuration

Required Next.js variables: `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_SECRET`, `APP_BASE_URL`, and `AUTH0_SCOPE`. `AUTH0_AUDIENCE` is optional.

Required FastAPI variables: `AUTH0_DOMAIN`, `SUPABASE_URL`, and `SUPABASE_SERVICE_KEY`. `AUTH0_AUDIENCE` is optional.

There is no implicit unauthenticated production fallback. Tests inject fake identity and storage implementations instead of using live credentials.

## Verification

Automated backend tests prove 401 handling, JWT identity propagation, per-user read/write isolation, and analysis loading the authenticated user's positions. Frontend lint/type checks prove Auth0 integration compiles. Browser verification covers login redirect and the signed-out portfolio state; a full signed-in smoke test requires valid Auth0 callback URLs and deployment environment values.

MCP verification covers unauthenticated rejection, tool discovery, authenticated `get_portfolio_details`, and confirmation that a caller cannot supply or override a user ID.

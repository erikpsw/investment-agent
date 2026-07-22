# Multi-Currency Cash and Cloud Watchlists Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CNY/HKD/USD cash positions, grouped cloud-synced watchlists, shared 5/20/60/250-day research metrics, and read-only structured MCP access.

**Architecture:** Keep portfolio positions in `user_portfolios` and store ordered watchlist documents separately in `user_watchlists`, both keyed by the authenticated Auth0 subject. A shared Python research snapshot service enriches portfolio and watchlist securities; the Next.js MCP route forwards authenticated requests and never generates opinions.

**Tech Stack:** Python 3, FastAPI, Pydantic, pandas, Supabase, Next.js 16, React 19, TypeScript, MCP SDK, Node test runner, lightweight-charts.

## Global Constraints

- Cash identifiers are exactly `CASH_CNY`, `CASH_HKD`, and `CASH_USD`; legacy `CASH` becomes `CASH_CNY`.
- Retain only the first cash row for each currency in request order.
- A ticker is unique inside one watchlist group but may occur in multiple groups.
- Trend windows are exactly 5, 20, 60, and 250 trading sessions.
- Default MCP responses omit OHLCV history; `include_history=true` returns at most 250 ascending daily bars.
- MCP returns structured data and recent news only; it must not call an LLM or return `agent_view` or recommendations.
- Existing OAuth and PAT scopes remain `portfolio:read` and `portfolio:write`.

---

### Task 1: Shared Security Research Snapshot

**Files:**
- Create: `data/research_snapshot.py`
- Create: `tests/test_research_snapshot.py`

**Interfaces:**
- Produces: `ResearchSnapshotService(fetcher=None, news_provider=None)`.
- Produces: `ResearchSnapshotService.snapshot(ticker: str, name: str, market: str, include_history: bool = False) -> dict[str, Any]`.
- Produces: `ResearchSnapshotService.enrich(items: list[dict[str, Any]], include_history: bool = False) -> list[dict[str, Any]]` preserving input order.

- [ ] **Step 1: Write metric-contract tests**

Create deterministic OHLCV data and assert exact keys and period behavior:

```python
def test_snapshot_returns_structured_metrics_without_history_by_default():
    service = make_service(closes=list(range(100, 361)))
    result = service.snapshot("sh600000", "浦发银行", "CN")
    assert result["returns"]["5d"] == pytest.approx((360 / 355 - 1) * 100)
    assert result["moving_averages"]["ma20"] == pytest.approx(sum(range(341, 361)) / 20)
    assert result["history"] is None
    assert "volatility_20d" in result["technical"]
    assert "rsi14" in result["technical"]
    assert "max_drawdown_250d" in result["technical"]

def test_snapshot_requires_n_plus_one_closes_for_n_day_return():
    service = make_service(closes=list(range(1, 21)))
    result = service.snapshot("AAPL", "Apple", "US")
    assert result["returns"]["20d"] is None

def test_snapshot_optionally_returns_at_most_250_ascending_bars():
    result = make_service(closes=list(range(1, 301))).snapshot(
        "AAPL", "Apple", "US", include_history=True
    )
    assert len(result["history"]) == 250
    assert result["history"][0]["time"] < result["history"][-1]["time"]
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_research_snapshot.py -q`

Expected: collection fails because `investment.data.research_snapshot` does not exist.

- [ ] **Step 3: Implement deterministic metrics and partial-failure handling**

Implement the service with these stable result sections:

```python
{
    "quote": {"price": ..., "currency": ..., "day_change_percent": ..., "volume": ...},
    "returns": {"5d": ..., "20d": ..., "60d": ..., "250d": ...},
    "moving_averages": {"ma5": ..., "ma20": ..., "ma60": ..., "ma250": ...},
    "technical": {
        "volatility_20d": ..., "volatility_60d": ..., "rsi14": ...,
        "volume_ratio_20d": ..., "high_250d": ..., "low_250d": ...,
        "max_drawdown_250d": ..., "distance_to_high_250d": ...,
    },
    "recent_news": [...],
    "history": [...] if include_history else None,
    "errors": [],
}
```

Use valid numeric rows only, annualize return standard deviation with `sqrt(252)`, and compute drawdown from cumulative running peaks. Catch quote, history, and news failures independently and append concise source-prefixed errors.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_research_snapshot.py -q`

Expected: all snapshot tests pass.

- [ ] **Step 5: Commit**

```bash
git add data/research_snapshot.py tests/test_research_snapshot.py
git commit -m "feat: add shared security research snapshots"
```

### Task 2: Multi-Currency Cash Normalization and Portfolio Enrichment

**Files:**
- Modify: `data/portfolio.py`
- Modify: `api/routes/portfolio.py`
- Modify: `tests/test_portfolio_store.py`
- Modify: `tests/test_portfolio_auth.py`

**Interfaces:**
- Consumes: `ResearchSnapshotService.enrich(...)` from Task 1.
- Changes: `PortfolioService.get_positions(user_id, include_history=False)`.
- Preserves: `PortfolioService.analyze(user_id)` for explicit web analysis only.

- [ ] **Step 1: Add failing cash and history tests**

```python
def test_three_cash_currencies_are_unique_and_converted_to_cny():
    saved = service.save_positions("auth0|alice", [
        {"ticker": "CASH", "market": "CASH", "quantity": 100},
        {"ticker": "CASH_CNY", "market": "CASH", "currency": "CNY", "quantity": 999},
        {"ticker": "CASH_HKD", "market": "CASH", "currency": "HKD", "quantity": 200},
        {"ticker": "CASH_USD", "market": "CASH", "currency": "USD", "quantity": 300},
    ])
    cash = {item["ticker"]: item for item in saved["positions"]}
    assert cash["CASH_CNY"]["quantity"] == 100
    assert cash["CASH_HKD"]["market_value"] == 180
    assert cash["CASH_USD"]["market_value"] == 2100

def test_portfolio_history_is_opt_in():
    result = service.get_positions("auth0|alice", include_history=True)
    assert result["positions"][0]["research"]["history"]
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_portfolio_store.py tests/test_portfolio_auth.py -q`

Expected: cash identifiers are collapsed to `CASH` and `include_history` is unsupported.

- [ ] **Step 3: Implement currency-specific cash and shared research**

Normalize cash by identifier and explicit currency, migrate legacy `CASH` to CNY, preserve first occurrence, and enrich only non-cash positions under a `research` property. Add `include_history: bool = Query(False)` to `GET /portfolio/positions` and pass it to the service.

- [ ] **Step 4: Verify GREEN and portfolio regression tests**

Run: `python -m pytest tests/test_portfolio_store.py tests/test_portfolio_auth.py tests/test_pat_auth.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add data/portfolio.py api/routes/portfolio.py tests/test_portfolio_store.py tests/test_portfolio_auth.py
git commit -m "feat: support multicurrency cash positions"
```

### Task 3: Watchlist Cloud Store and Domain Service

**Files:**
- Create: `supabase/migrations/202607220001_create_user_watchlists.sql`
- Create: `data/watchlist_store.py`
- Create: `data/watchlists.py`
- Create: `tests/test_watchlist_store.py`
- Create: `tests/test_watchlists.py`

**Interfaces:**
- Produces: `WatchlistDocument(groups, updated_at, storage)`.
- Produces: `InMemoryWatchlistStore`, `SupabaseWatchlistStore`, and `get_watchlist_store()`.
- Produces: `WatchlistService.get_watchlists(user_id, group_id=None, include_history=False)`.
- Produces: `WatchlistService.save_watchlists(user_id, groups)`.

- [ ] **Step 1: Write failing isolation and normalization tests**

```python
def test_same_group_deduplicates_but_cross_group_duplicate_is_preserved():
    saved = service.save_watchlists("auth0|alice", [
        {"id": "core", "name": "Core", "items": [item("AAPL"), item("aapl")]},
        {"id": "tech", "name": "Tech", "items": [item("AAPL")]},
    ])
    assert [len(group["items"]) for group in saved["groups"]] == [1, 1]

def test_users_have_independent_watchlist_documents():
    store.save("auth0|alice", [{"id": "a", "name": "A", "items": []}])
    store.save("auth0|bob", [{"id": "b", "name": "B", "items": []}])
    assert store.load("auth0|alice").groups[0]["id"] == "a"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_watchlist_store.py tests/test_watchlists.py -q`

Expected: modules do not exist.

- [ ] **Step 3: Add migration, stores, normalization, and enrichment**

Migration requirements:

```sql
create table if not exists public.user_watchlists (
  user_id text primary key,
  groups jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.user_watchlists enable row level security;
```

Follow `portfolio_store.py` for service-role reads and upserts. Normalize group IDs/names, preserve order, normalize market/ticker/name/notes, deduplicate case-insensitive tickers inside each group, then enrich items with `ResearchSnapshotService`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_watchlist_store.py tests/test_watchlists.py -q`

Expected: all watchlist domain tests pass.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/202607220001_create_user_watchlists.sql data/watchlist_store.py data/watchlists.py tests/test_watchlist_store.py tests/test_watchlists.py
git commit -m "feat: add cloud watchlist storage"
```

### Task 4: Authenticated Watchlist API

**Files:**
- Create: `api/routes/watchlists.py`
- Modify: `api/main.py`
- Modify: `api/index.py`
- Create: `tests/test_watchlist_auth.py`

**Interfaces:**
- Consumes: `WatchlistService` from Task 3.
- Produces: `GET /api/watchlists?group_id=&include_history=`.
- Produces: `PUT /api/watchlists` with strict `{groups: [...]}` body.

- [ ] **Step 1: Write failing API tests**

Assert missing tokens return 401, authenticated calls pass only `current_user.sub`, `group_id` and `include_history` are forwarded, unknown groups become 404, storage failures become 503, and client-supplied `user_id` returns 422.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_watchlist_auth.py -q`

Expected: route module does not exist.

- [ ] **Step 3: Implement and mount the router**

Use `require_scope("portfolio:read")` for GET and `require_scope("portfolio:write")` for PUT. Mount the router in both FastAPI entrypoints so local and Vercel deployments expose identical contracts.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_watchlist_auth.py tests/test_portfolio_auth.py tests/test_pat_auth.py -q`

Expected: all auth tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/routes/watchlists.py api/main.py api/index.py tests/test_watchlist_auth.py
git commit -m "feat: expose authenticated watchlist API"
```

### Task 5: Structured Portfolio and Watchlist MCP Tools

**Files:**
- Create: `web/src/lib/mcp-user-data-tools.ts`
- Modify: `web/src/app/mcp/route.ts`
- Modify: `web/tests/mcp-route.test.ts`

**Interfaces:**
- Produces: `registerUserDataTools(server, tokenProvider)`.
- Produces MCP tools `get_portfolio_details({include_history})` and `get_watchlists({group_id, include_history})`.
- Removes generated-analysis access from MCP while retaining the web-only analysis endpoint.

- [ ] **Step 1: Change MCP tests first**

Assert tool schemas contain `include_history`, omit `include_analysis` and `user_id`, forward the bearer token, call only GET endpoints, filter with `group_id`, and return structured results without `agent_view`.

```typescript
const portfolio = await client.callTool({
  name: "get_portfolio_details",
  arguments: { include_history: true },
});
assert.equal(apiRequests[0].url, "https://portfolio.test/api/portfolio/positions?include_history=true");
assert.equal("agent_view" in (portfolio.structuredContent as object), false);

await client.callTool({
  name: "get_watchlists",
  arguments: { group_id: "core", include_history: false },
});
assert.equal(apiRequests[1].url, "https://portfolio.test/api/watchlists?group_id=core&include_history=false");
```

- [ ] **Step 2: Verify RED**

Run: `npm run test:mcp --prefix web`

Expected: old schema still exposes `include_analysis` and `get_watchlists` is absent.

- [ ] **Step 3: Implement one reusable authenticated JSON tool adapter**

Move portfolio tool registration out of the route, register both read-only tools, URL-encode `group_id`, and return MCP errors for non-2xx responses. Do not import an AI SDK or call `/api/portfolio/analyze`.

- [ ] **Step 4: Verify GREEN**

Run: `npm run test:mcp --prefix web`

Expected: MCP tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/mcp-user-data-tools.ts web/src/app/mcp/route.ts web/tests/mcp-route.test.ts
git commit -m "feat: expose structured watchlist data through MCP"
```

### Task 6: Watchlist UI, Cash Controls, and Trend Details

**Files:**
- Create: `web/src/app/watchlist/page.tsx`
- Create: `web/src/components/security-research-details.tsx`
- Create: `web/src/components/watchlist-group-card.tsx`
- Modify: `web/src/app/portfolio/page.tsx`
- Modify: `web/src/components/sidebar.tsx`
- Modify: `web/src/lib/api.ts`
- Modify: `web/tests/auth-route.test.ts`
- Modify: `web/tests/ui-support.test.ts`

**Interfaces:**
- Consumes authenticated `/api/watchlists` and `/api/portfolio/positions` responses.
- Produces reusable `SecurityResearchDetails` with 5/20/60/250-day tabs.
- Produces explicit-save grouped watchlist editing.

- [ ] **Step 1: Add failing static UI contract tests**

Assert the sidebar links `/watchlist`, the page uses authenticated load/save methods, group cards support add/rename/reorder/delete, mobile and desktop layouts exist, cash controls contain all three currency IDs, and both pages render `SecurityResearchDetails` for securities.

- [ ] **Step 2: Verify RED**

Run: `npm run test:auth --prefix web && npm run test:ui-support --prefix web`

Expected: watchlist page/components and currency controls are absent.

- [ ] **Step 3: Add API types and methods**

Add `SecurityResearch`, `WatchlistItem`, `WatchlistGroup`, and `WatchlistResult` interfaces. Add:

```typescript
getWatchlists(groupId?: string, includeHistory = false)
saveWatchlists(groups: WatchlistGroup[])
```

Both methods must use the existing authenticated fetch path.

- [ ] **Step 4: Implement cash selector and trend details**

Replace the generic cash button with CNY/HKD/USD choices, disable currencies already present, and display native balance, FX rate, CNY value, and weight. Render period-return chips by default and lazily expose charts/metrics in `SecurityResearchDetails`; cash does not render this component.

- [ ] **Step 5: Implement grouped watchlist page**

Use stable client-generated UUID group IDs, existing symbol search behavior, explicit Save, same-group duplicate checks, cross-group duplicates, delete confirmation, stacked mobile cards, and desktop group tables. Preserve unsaved edits when a save fails.

- [ ] **Step 6: Verify UI tests and TypeScript build**

Run: `npm run test:auth --prefix web`

Run: `npm run test:ui-support --prefix web`

Run: `npm run build --prefix web`

Expected: tests and production build pass.

- [ ] **Step 7: Commit**

```bash
git add web/src/app/watchlist/page.tsx web/src/components/security-research-details.tsx web/src/components/watchlist-group-card.tsx web/src/app/portfolio/page.tsx web/src/components/sidebar.tsx web/src/lib/api.ts web/tests/auth-route.test.ts web/tests/ui-support.test.ts
git commit -m "feat: add grouped cloud watchlists"
```

### Task 7: Full Verification and Deployment Readiness

**Files:**
- Modify only files required by failures found in this task.

**Interfaces:**
- Verifies all contracts produced by Tasks 1-6.

- [ ] **Step 1: Run the full Python suite**

Run: `python -m pytest -q`

Expected: all tests pass with no new warnings caused by this feature.

- [ ] **Step 2: Run all web tests and build**

Run: `npm run test:mcp --prefix web`

Run: `npm run test:auth --prefix web`

Run: `npm run test:market-index --prefix web`

Run: `npm run test:ui-support --prefix web`

Run: `npm run build --prefix web`

Expected: every command exits 0.

- [ ] **Step 3: Review the final diff for contract violations**

Run: `git diff --check`

Run: `rg -n "include_analysis|agent_view" web/src/app/mcp web/src/lib/mcp-*.ts`

Expected: no whitespace errors; MCP code contains neither deprecated analysis parameter nor generated analysis output.

- [ ] **Step 4: Confirm migration order and environment requirements**

Verify `202607220001_create_user_watchlists.sql` follows existing migrations and that production has `SUPABASE_URL` plus `SUPABASE_SERVICE_KEY` or `SUPABASE_SERVICE_ROLE_KEY`.

If a verification command fails, return to the task that owns the failing contract, add a focused regression test there, fix it, rerun that task's focused commands, and repeat this full verification task. A clean verification run creates no additional commit.

# Multi-Currency Cash and Cloud Watchlists Design

## Scope

This change extends the authenticated investment workspace in two related areas:

1. Portfolio cash positions support one CNY, one HKD, and one USD balance.
2. A new grouped watchlist module is stored per user in Supabase and exposed to MCP as read-only structured research data.

Portfolio and watchlist securities share one research snapshot service so prices, trend periods, technical metrics, and news use the same definitions. MCP returns data rather than generated investment opinions.

## Product Requirements

### Multi-Currency Cash

- The portfolio add-cash control offers CNY, HKD, and USD.
- Each currency can occur at most once in a user's portfolio.
- Cash uses stable identifiers `CASH_CNY`, `CASH_HKD`, and `CASH_USD`.
- Quantity is the native-currency balance and average cost is fixed at 1.
- Cash has no price profit/loss. Its native balance is converted to CNY with the same FX provider already used by the portfolio service.
- Cash contributes to total market value, portfolio weight, cash allocation, and the user-triggered portfolio analysis.
- Cash rows show currency, native balance, CNY exchange rate, CNY market value, and portfolio weight. They do not show meaningless security trend metrics.

### Grouped Watchlists

- Add a dedicated `/watchlist` page and sidebar entry. The existing `/watchlist/monitor` route remains the real-time monitoring page.
- Users can create, rename, reorder, and delete groups.
- Users can search for and add securities with the existing symbol search experience.
- A watchlist item stores ticker, name, market, and notes.
- A ticker is unique within a group but may appear in multiple groups.
- Deleting a non-empty group requires confirmation and deletes its contained items.
- Changes are edited locally and persisted through an explicit Save action. Loading another authenticated device reads the same cloud document.
- Mobile uses stacked group and security cards with full-width controls. Desktop uses compact tables inside group cards.

## Storage Design

### Portfolio Compatibility

The existing `user_portfolios.positions` JSON document remains the source of truth. Legacy cash rows with ticker `CASH` are normalized to `CASH_CNY`. New writes use currency-specific cash identifiers. Server-side normalization rejects duplicate cash currencies by retaining the first normalized row for each currency in request order.

### Watchlist Document

Create a `user_watchlists` table with one row per Auth0 subject:

| Column | Type | Purpose |
| --- | --- | --- |
| `user_id` | text primary key | Auth0 `sub` and user isolation key |
| `groups` | jsonb | Ordered groups and ordered items |
| `updated_at` | timestamptz | Last successful save time |

The JSON document shape is:

```json
[
  {
    "id": "stable-uuid",
    "name": "Core Watchlist",
    "items": [
      {
        "ticker": "hk00700",
        "name": "Tencent Holdings",
        "market": "HK",
        "notes": "Track AI and gaming catalysts"
      }
    ]
  }
]
```

The API service normalizes identifiers and text, validates supported markets, removes duplicate tickers within each group, and preserves cross-group duplicates. The Supabase service role remains server-only. Browser and MCP callers never receive it.

## Shared Research Snapshot

Create a reusable service that enriches a security without depending on portfolio ownership or watchlist storage. Both modules call it in bounded parallel batches.

The default snapshot includes:

- Current price, native currency, daily change percentage, and volume.
- Returns for 5, 20, 60, and 250 trading-day windows.
- MA5, MA20, MA60, and MA250.
- Annualized volatility for 20 and 60 trading days.
- RSI14 and current-volume-to-20-day-average ratio.
- Window high, low, maximum drawdown, and distance from the 250-day high.
- Recent news title, publication time, source, URL, and source-provided summary.
- Per-source errors so one quote, history, or news failure does not fail the whole document.

An N-day return compares the latest close with the close N trading sessions earlier and is `null` unless at least N+1 valid closes exist. Volatility is the annualized standard deviation of daily returns. Maximum drawdown and high/low metrics use the selected lookback window, capped at 250 sessions.

When history is requested, the result additionally contains at most 250 daily OHLCV records in ascending date order. Missing lookback data produces `null` metrics rather than fabricated values.

The UI offers 5-day, 20-day, 60-day, and 250-day chart tabs. List rows show the four period returns; charts and detailed metrics are placed in an expandable section to keep desktop tables and mobile cards usable.

Cash entries bypass security research enrichment.

## HTTP API

### Watchlists

- `GET /api/watchlists?group_id=<optional>&include_history=false`
  - Requires `portfolio:read`.
  - Returns all groups or one matching group, enriched items, storage type, and update timestamp.
  - An unknown `group_id` returns HTTP 404.
- `PUT /api/watchlists`
  - Requires `portfolio:write`.
  - Replaces the authenticated user's normalized watchlist document.
- A storage outage returns HTTP 503.
- Invalid group/item payloads return HTTP 422.
- A failed security enrichment remains HTTP 200 with errors attached to that item.

### Portfolio

Existing portfolio endpoints remain stable. Position responses gain the shared trend and metric summary for securities. Full OHLCV history is returned only when explicitly requested, preventing oversized default responses.

## MCP Contract

MCP remains authenticated by OAuth or a Personal Access Token. Existing `portfolio:read` credentials can read both portfolio and watchlists without being reissued.

### `get_portfolio_details`

- Replace `include_analysis` with `include_history`, defaulting to `false`.
- Return positions, cash balances, CNY totals, FX rates, weights, structured market metrics, recent news, and optional OHLCV history.
- Do not invoke an LLM or return `agent_view`, recommendations, or template portfolio judgments.

### `get_watchlists`

- Parameters:
  - `group_id`: optional stable group ID. Omit it to return all groups.
  - `include_history`: optional boolean, default `false`.
- Return ordered groups and enriched security data.
- An unknown `group_id` returns an MCP tool error with a concise message.
- The tool is read-only. MCP cannot create, rename, reorder, or delete groups or items.

The web application's explicit "AI Portfolio Analysis" action remains available. It is separate from both MCP tools and only runs when requested by the signed-in user.

## Error Handling and Concurrency

- Authentication and scope checks happen before storage or market-data calls.
- Stores wrap Supabase failures in domain-specific storage errors that API routes translate to HTTP 503.
- Market calls use a bounded thread pool and preserve input ordering.
- One failed symbol does not prevent other symbols from loading.
- Save buttons remain disabled during writes, and failed writes keep the user's unsaved local edits.
- Empty groups are valid.
- Duplicate cash currencies and duplicate same-group tickers are normalized server-side, not only prevented by UI controls.

## Testing

### Python

- CNY, HKD, and USD cash normalization, valuation, uniqueness, weights, and legacy `CASH` migration.
- Watchlist normalization, same-group deduplication, cross-group duplication, ordering, and user isolation.
- Supabase watchlist reads, writes, and storage failure translation.
- Research metrics for complete, partial, and missing history.
- Portfolio and watchlist API authentication and scope enforcement.

### Web and MCP

- Currency-specific add-cash controls and duplicate prevention.
- Group create, rename, reorder, delete confirmation, item search, and save behavior.
- Mobile card and desktop table layouts.
- `get_portfolio_details` returns structured data without generated analysis.
- `get_watchlists` filters by group, forwards bearer credentials, handles unknown groups, and includes history only when requested.

### End-to-End Verification

- Save cash and grouped watchlists under one user and confirm they load on a second session.
- Confirm another user cannot read or overwrite those documents.
- Connect with OAuth and PAT, inspect both MCP tools, and verify no mechanical AI analysis appears.
- Run the full Python and web test suites before deployment.

## Migration and Rollout

1. Apply the `user_watchlists` table migration before deploying API code.
2. Deploy backward-compatible cash normalization and watchlist endpoints.
3. Deploy the watchlist UI and MCP schema update.
4. Verify cloud persistence and both MCP authentication methods in production.

The portfolio JSON requires no destructive migration. Existing generic cash becomes CNY cash on read and is persisted in the new form on the next save.

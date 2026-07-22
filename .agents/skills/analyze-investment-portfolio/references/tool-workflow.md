# Tool Workflow

## Source Order

Run independent reads in parallel when possible. Use read-only calls only.

### Cloud-only boundary

Discover and call the Portfolio Management MCP directly. It is the only permitted source for holdings, balances, cost basis, portfolio P/L, account performance, and pending portfolio changes. Do not inspect the current workspace, local portfolio files, exported statements, cached reports, browser storage, on-disk databases, IBKR account endpoints, ErikAI, or another broker connector for portfolio state. Local scripts are allowed only as clients for the remote Huatai and Guangfa APIs; do not use their local caches as evidence. When Portfolio Management MCP returns no holdings or balances, report the analysis as `blocked` without producing holding-level conclusions or recommendations.

### Portfolio Management MCP

Portfolio Management tools may be lazy-loaded. Find them by semantic description and use these current read-only capabilities:

| Semantic operation | Required data |
|---|---|
| portfolio details | holdings, quantity, cost/current price, native/reporting value, P/L, weight, FX, timestamp, errors |
| broad-market snapshot | major indexes, change, market labels, timestamp, and any returned volume/breadth/session metadata |
| stock quote and price history | current quote plus OHLCV bars for technical state and entry conditions |
| sector ranking | composite score, performance, breadth, turnover, leading stocks, timestamp/source metadata |
| sector history and constituents | sector 5/20/60-day trend plus formula-ranked members and history-quality metadata |
| formula stock ranking | market/mode-specific scores, components, risks, and source metadata |

Retry one transient read failure. These tools are research inputs; do not create, edit, or delete holdings, orders, plans, or instructions during analysis.

#### Current semantic tool map

Resolve these by description on every run because generated identifiers may change:

| Semantic operation | Description to match | Call notes |
|---|---|---|
| portfolio details | “authenticated user's portfolio” | call with `include_analysis: true` for a full review; preserve raw errors and timestamp |
| broad-market snapshot | `get_market_overview` or descriptions mentioning major-market index levels | call once, then select every market represented by holdings and proposed opportunities |
| stock quote | `get_stock_quote` or descriptions mentioning current quote | use for held names and shortlisted candidates when portfolio/ranking prices are stale or timestamps differ |
| price history | `get_price_history` or descriptions mentioning OHLCV history | default to daily 3-month data; expand only when the thesis requires it |
| sector ranking | “market sectors ranked by composite score” | request enough rows to cover leadership and laggards; preserve returned scoring fields |
| sector history | `get_sector_history` or descriptions mentioning sector trend history | call for shortlisted sector codes returned by sector ranking, normally 120 days |
| sector constituents | `get_sector_constituents` or descriptions mentioning formula-ranked sector members | call for confirmed leading sectors using the user's risk mode; preserve history enrichment count |
| formula stock ranking | “formula-based stock ranking” | run once per relevant held market; default `balanced`, or match an explicit user risk style |

Call portfolio details, broad-market snapshot, and sector ranking in parallel. After portfolio details identifies held markets, call formula ranking for each relevant market; CN and US may be called in parallel. For the strongest credible sectors, call sector history and sector constituents in parallel, then call stock quote and price history only for the resulting shortlist. Use `all` only for a global screen, not as a substitute for market-specific comparisons. Record parameters, tool errors, data timestamp, session state, and source metadata from every response.

If a newly connected or stale MCP deployment does not yet expose one of these research tools, obtain equivalent market evidence from an official exchange/data source or the available live market-data/web finance capability. Use Huatai `marketInsight` only as interpretation, not as the sole quote source. This fallback does not violate the portfolio source boundary because it supplies market evidence, never holdings, balances, cost basis, P/L, or performance. Label delayed, previous-close, cached, or incomplete breadth/turnover data explicitly.

#### Broad-market interpretation

- Cover each market materially represented by holdings or qualified opportunities. For CN holdings, normally include Shanghai, Shenzhen/CSI or ChiNext as relevant; for US holdings, include broad, technology, and volatility/risk-appetite proxies when available.
- Report index level/change, trading-session state, data timestamp, turnover or volume versus a recent baseline, and market breadth. Never combine values from different sessions without disclosure.
- Classify the regime as risk-on, neutral/rotational, or risk-off only when price direction agrees with at least one confirmation input such as breadth, turnover/volume, volatility, or credit/currency behavior.
- Separate index strength from median-stock strength. A cap-weighted index rally with weak breadth is narrow leadership, not a broad risk-on signal.
- Use the market regime to adjust entry aggressiveness: broad confirmation permits normal staged sizing; narrow or extended markets require smaller first tranches or pullback confirmation; risk-off conditions normally produce watchlist status unless the setup is explicitly defensive.

#### Sector-trend interpretation

- Use performance for direction, breadth for participation, turnover for confirmation, and leading stocks for concentration/leadership quality.
- Prefer a sector with aligned performance, breadth, and turnover over one driven by a single leader.
- Map each holding to the closest returned sector only when the mapping is supported; label inferred mappings.
- Do not extrapolate a short ranking window into a long-term forecast. Confirm material conclusions with current market news and, where available, industry fundamentals.
- If composite scores are saturated or tied, do not use rank/score to distinguish sectors; compare raw performance, breadth, turnover, coverage size, and leader concentration instead, and disclose the saturation.

#### Formula-screen interpretation

- Preserve `market`, `mode`, `limit`, timestamp, total score, components, risks, and source metadata.
- Compare held names and candidates only within the same market/mode run.
- A missing holding is not automatically a sell; state whether it fell below the limit or was ineligible.
- Shortlist candidates only after checking liquidity, valuation, fundamentals, news/event risk, sector concentration, and incremental portfolio correlation.
- Reject candidates that merely duplicate an existing sector/style exposure or whose risk flags conflict with the user's risk limit.
- Never convert rank order directly into position sizes. Anchor any suggested size to combined portfolio NAV and risk bands.
- Treat a screen as degraded when `fallback` is true, `generated_at` is missing, required price/trend fields are null, history enrichment is zero when the formula claims history inputs, or scores/components are materially tied. A degraded screen may produce a watchlist only, never a buy/trim recommendation.
- If `cached` is true, state it and verify the cache timestamp before using time-sensitive fields. If no timestamp is supplied, treat recency as unknown.

#### Sector-led opportunity construction

Generate new-position opportunities only after establishing the broad-market and sector regimes:

1. Select sectors whose direction is supported by performance, breadth, turnover, and leadership quality. Reject score-only leadership when composite scores are tied or saturated.
2. Confirm each selected sector with `get_sector_history`, then use `get_sector_constituents` to generate sector-native candidates. Intersect them with the market-wide formula ranking when possible. Verify business membership; do not infer it from the ticker name alone.
3. Prefer candidates with adequate liquidity, non-degraded ranking inputs, acceptable valuation/fundamentals, no unresolved material adverse event, and lower incremental correlation than an existing holding with similar exposure.
4. Use `get_stock_quote` plus `get_price_history` to check current price against trend, support/resistance, recent range, volume, and upcoming earnings or regulatory events. Distinguish a breakout entry from a pullback entry; do not recommend chasing an extended one-day move.
5. Express size as a percentage of combined portfolio NAV and respect market lot sizes. Use staged entries, normally an initial tranche followed by confirmation, while keeping single-name, sector, style, currency, and speculative-risk bands intact.
6. Give an observable invalidation condition. Include both thesis invalidation, such as sector breadth deterioration or adverse fundamentals, and price-risk invalidation, such as a closing support break.

Classify each result:

- `qualified entry`: sector, instrument, data quality, and portfolio-fit checks pass; provide a conditional entry plan.
- `watchlist`: direction is promising but price, valuation, event risk, or confirmation is inadequate.
- `rejected`: candidate conflicts with portfolio limits, lacks liquidity, fails fundamentals/news checks, or only appears because of degraded ranking data.
- `no qualified entry`: no candidate passes all gates. This is a valid outcome and must not be replaced with a forced recommendation.

For every qualified entry preserve the sector-ranking and formula-ranking timestamps and report: sector thesis, ticker/name, why this candidate rather than the sector leader or an ETF, entry trigger/zone, initial and maximum target weight, add condition, invalidation/stop condition, catalyst, and principal risks. Do not calculate share quantity when cash/NAV availability is missing; provide portfolio-percentage sizing and label cash feasibility unverified.

#### Reconciliation conventions

- If Portfolio Management returns an account-level/base-currency roll-up plus native-currency rows, never add the roll-up to its component rows.
- Use native-currency rows for exposure and the explicit account/portfolio total for NAV/cash reconciliation.
- Reconcile small differences between positions, currency balances, and account financials as timing/rounding only after checking their timestamps.
- If portfolio details omits cash, leverage, realized P/L, performance history, or pending orders, mark those fields unavailable. Do not infer zero and do not fill them from IBKR.

#### Conditional instrument analytics

IBKR is not a portfolio-state source. After holdings are identified exclusively by Portfolio Management MCP, IBKR instrument tools may be used only when they materially improve instrument-level research:

| Need | Tool sequence |
|---|---|
| current quote, spread, volume, volatility | resolve the Portfolio Management ticker via contract search -> price snapshot |
| technical trend/support/resistance | resolve the Portfolio Management ticker via contract search -> price history; if the call fails, use an official/exchange market source and disclose the gap |
| business model, products, geography, competitors | resolve the Portfolio Management ticker via contract search -> company connections with company/link information |
| themes and ranked peers | resolve the Portfolio Management ticker via contract search -> company themes |
| resolve another instrument | contract search; use the exact symbol/security-type match and returned identifier |
| option risk or hedge analysis | contract search -> option parameters -> option data; request price snapshots only for selected contracts |
| futures exposure | contract search -> futures term structure -> selected-contract snapshot/history |

Never call IBKR positions, account financials, currency balances, performance, NAV allocation, live orders, saved instructions, or trades during portfolio analysis. Watchlist mutation, instruction creation/deletion, combo construction, and feedback submission are also outside read-only portfolio analysis. Never call them without a separate explicit user request and any confirmation required by the tool.

### Huatai

**REQUIRED SUB-SKILL:** Read and use `financial-analysis`.

Use `diagnosisStock` for holding diagnosis and `marketInsight` for portfolio/industry/news comparison. Include ticker, quantity, cost, and the other holdings in the query so concentration and correlations are visible.

Windows direct-call pattern:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
if (-not $env:HT_APIKEY) {
  $env:HT_APIKEY=[Environment]::GetEnvironmentVariable('HT_APIKEY','User')
}
python financial_analysis.py diagnosisStock --query "<完整问题>"
```

Use direct networking by default. Do not inject a proxy unless the user requests it or direct connectivity is proven unavailable.

### Guangfa

**REQUIRED SUB-SKILLS:** Read the relevant `gf_stock_f10` and `gf_stock_valuation` skills.

For each material A-share, call F10. Compare related A-shares in one valuation call and one financial-indicator call.

`indicatorCompare` requires at least two same-market-type stocks. Select a genuinely comparable peer, disclose that it is a research comparator rather than a holding, and never add it to portfolio weights.

```powershell
if (-not $env:GF_SKILLS_APIKEY) {
  $env:GF_SKILLS_APIKEY=[Environment]::GetEnvironmentVariable('GF_SKILLS_APIKEY','User')
}
python gf_stock_f10.py f10Basic --code 601066 --market SH
python gf_stock_valuation.py valuationCompare --stock_codes SH601066,SH600906
python gf_stock_valuation.py indicatorCompare --report_type 12 --stock_codes SH601066,SH600906 --year 2025
```

Do not print keys. If Process scope is empty but User scope exists, load it only into the child process and recommend restarting Codex for future inheritance.

On macOS/Linux, if the Python client reports `CERTIFICATE_VERIFY_FAILED`, retry safely with the CA bundle returned by `python -m certifi`, for example `SSL_CERT_FILE="$(python -m certifi)" python ...`. Never use an unverified SSL context or otherwise disable certificate verification.

## Web News

Browse because prices, filings, earnings, management, regulation, and news are time-sensitive. Search material holdings and sector-level catalysts.

Evidence priority:

1. Regulator, exchange, SEC/EDGAR, statutory filing.
2. Company investor relations or official announcement.
3. Established financial media.
4. Aggregators and social sources only as leads.

Record event date separately from publication date. Cite every current factual claim near the claim. Label company projections and press releases as management claims, not independently verified outcomes.

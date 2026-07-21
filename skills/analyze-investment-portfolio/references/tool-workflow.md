# Tool Workflow

## Source Order

Run independent reads in parallel when possible. Use read-only calls only.

### Cloud-only boundary

Discover and call configured cloud connectors directly. Do not inspect the current workspace, local portfolio files, exported statements, cached reports, browser storage, or on-disk databases for holdings. Local scripts are allowed only as clients for the remote Huatai and Guangfa APIs; do not use their local caches as evidence. When no cloud connector returns portfolio data, report the analysis as `blocked` without producing holding-level conclusions or recommendations.

### ErikAI

Call `mcp__erik_ai__get_portfolio_details` with `include_analysis: true`. Capture positions, quantities, average costs, current prices, common-currency values, P/L, weights, FX rates, technical indicators, news, timestamps, and errors.

If authentication fails, report it and continue. Do not ask for or use manual holdings as a fallback.

### Interactive Brokers

IBKR tools may be lazy-loaded or have generated identifiers. Find tools by their semantic descriptions rather than hardcoding hashes. Retrieve:

| Semantic operation | Required data |
|---|---|
| account positions | quantity, price, value, cost, daily and unrealized P/L |
| account balances | NAV, cash, buying power, margin, leverage |
| cash/market value by currency | settled cash, FX rate, currency exposure |
| performance all periods | 1D, 7D, MTD, 1M, YTD, 1Y TWR/MWR |
| NAV allocation `ALL` | asset, sector, region, country, instrument |
| live orders | pending portfolio changes |
| trades | use when historical loss or turnover requires diagnosis |

Retry one transient read failure. Do not create, edit, or delete orders/instructions during analysis.

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

```powershell
if (-not $env:GF_SKILLS_APIKEY) {
  $env:GF_SKILLS_APIKEY=[Environment]::GetEnvironmentVariable('GF_SKILLS_APIKEY','User')
}
python gf_stock_f10.py f10Basic --code 601066 --market SH
python gf_stock_valuation.py valuationCompare --stock_codes SH601066,SH600906
python gf_stock_valuation.py indicatorCompare --report_type 12 --stock_codes SH601066,SH600906 --year 2025
```

Do not print keys. If Process scope is empty but User scope exists, load it only into the child process and recommend restarting Codex for future inheritance.

## Web News

Browse because prices, filings, earnings, management, regulation, and news are time-sensitive. Search material holdings and sector-level catalysts.

Evidence priority:

1. Regulator, exchange, SEC/EDGAR, statutory filing.
2. Company investor relations or official announcement.
3. Established financial media.
4. Aggregators and social sources only as leads.

Record event date separately from publication date. Cite every current factual claim near the claim. Label company projections and press releases as management claims, not independently verified outcomes.

# Investment Analysis Agent

This project can use two local skill providers for A-share analysis:

- Huatai Securities skills under `skills/financial-analysis` and `skills/query-indicator`
- GF Securities skills under `skills/gf_stock_f10` and `skills/gf_stock_valuation`

The API keys are expected from environment variables and should not be committed:

- `HT_APIKEY`
- `GF_SKILLS_APIKEY`

## Installed Skills In This Project

Huatai skills copied into `skills/`:

- `financial-analysis`: stock diagnosis and market insight
- `query-indicator`: quote, valuation, financial indicator lookup
- `a-share-paper-trading`: A-share paper trading tools
- `select-stock`: conditional stock screening
- `watchlist-management`: watchlist tools

GF Securities skills copied into `skills/`:

- `gf_stock_f10`: stock F10 basic company profile
- `gf_stock_valuation`: stock valuation and financial indicator comparison
- `gf_fund_detail`: fund detail lookup
- `gf_lhb_list`: Dragon Tiger List stock list
- `gf_etf_rank`: ETF ranking
- `gf_etf_search`: ETF multi-factor search
- `gf_etf_super_fund`: ETF super-fund flow abnormality

## Stock Analysis Workflow

Use this workflow for a single A-share stock.

### 1. Identify Code And Market

Normalize the stock to the provider formats:

- Huatai: natural language query is acceptable, for example `中信建投 601066`
- GF F10: pure code plus market, for example `--code 601066 --market SH`
- GF valuation: exchange-prefixed code, for example `SH601066`

### 2. Huatai Diagnosis

Run Huatai `financial-analysis` for a narrative diagnosis:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:HT_APIKEY=[Environment]::GetEnvironmentVariable('HT_APIKEY','User')
python .\skills\financial-analysis\financial_analysis.py diagnosisStock --query "分析中信建投 601066"
```

Use this output for:

- business mix
- performance trend
- market position
- funds flow
- technical signals
- qualitative summary

### 3. Huatai Quote And Indicator Check

Run Huatai `query-indicator` for current quote, valuation, and key financial values:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:HT_APIKEY=[Environment]::GetEnvironmentVariable('HT_APIKEY','User')
python .\skills\query-indicator\query_indicator.py queryIndicator --query "中信建投 601066 最新股价 PE PB 市值 2025年营收净利润 2026一季报"
```

Use this output to cross-check:

- latest price
- intraday move
- market cap
- PE TTM
- PB
- latest annual and quarterly revenue/profit

### 4. GF F10 Basic Profile

Run GF `gf_stock_f10` for static company profile:

```powershell
$env:GF_SKILLS_APIKEY=[Environment]::GetEnvironmentVariable('GF_SKILLS_APIKEY','User')
python .\skills\gf_stock_f10\gf_stock_f10.py f10Basic --code 601066 --market SH
```

Use this output for:

- company full name
- board
- listing date
- business scope
- industry

### 5. GF Valuation Peer Comparison

Run GF `gf_stock_valuation` to compare with peers:

```powershell
$env:GF_SKILLS_APIKEY=[Environment]::GetEnvironmentVariable('GF_SKILLS_APIKEY','User')
python .\skills\gf_stock_valuation\gf_stock_valuation.py valuationCompare --stock_codes SH601066,SH600030,SH601688,SH601995
```

Suggested peer set for securities firms:

- `SH601066`: 中信建投
- `SH600030`: 中信证券
- `SH601688`: 华泰证券
- `SH601995`: 中金公司

Use this output for:

- total market cap
- PE TTM
- PB
- industry average PE/PB
- historical valuation percentile

### 6. GF Financial Indicator Comparison

Run GF 2026 Q1 comparison:

```powershell
$env:GF_SKILLS_APIKEY=[Environment]::GetEnvironmentVariable('GF_SKILLS_APIKEY','User')
python .\skills\gf_stock_valuation\gf_stock_valuation.py indicatorCompare --report_type 1 --stock_codes SH601066,SH600030 --year 2026
```

Run GF 2025 annual comparison:

```powershell
$env:GF_SKILLS_APIKEY=[Environment]::GetEnvironmentVariable('GF_SKILLS_APIKEY','User')
python .\skills\gf_stock_valuation\gf_stock_valuation.py indicatorCompare --report_type 12 --stock_codes SH601066,SH600030 --year 2025
```

Use these outputs for:

- ROE
- net profit margin
- operating income growth
- net profit growth
- equity-to-asset ratio
- liability-to-asset ratio
- operating cash flow quality

## Synthesis Template

Use this structure for the final answer:

1. Quote and valuation snapshot
2. Huatai view: business, earnings trend, funds flow, technical signals
3. GF view: F10 profile, valuation percentile, peer comparison, financial metrics
4. Cross-provider agreement and differences
5. Investment judgment: strengths, risks, watch points

## Example: 中信建投 601066

### Huatai Findings

Huatai diagnosis shows 中信建投 is a national comprehensive securities firm with investment banking, wealth management, trading and institutional services, and asset management businesses.

2025 performance:

- Revenue: `233.22` billion yuan
- Attributable net profit: about `94.39` billion yuan
- Revenue growth: `22.41%`
- Net profit growth: about `30.68%`

2026 Q1 performance:

- Revenue: `76.96` billion yuan
- Attributable net profit: about `36.67` billion yuan
- Revenue growth: `62.26%`
- Net profit growth: about `99.03%`

Huatai market data on 2026-06-29:

- Latest price: about `29.29` yuan
- Intraday change: about `-3.17%`
- Main net inflow: about `-2.30` billion yuan
- Turnover rate: about `1.34%`

Interpretation: earnings momentum is strong, but short-term funds flow is negative after recent gains.

### GF Findings

GF F10:

- Company: 中信建投证券股份有限公司
- Board: 主板
- Listing date: `2018-06-20`
- Industry: 金融业
- Business scope: securities business, FX business, investment consulting, fund custody, public fund sales, futures IB service, precious metal sales

GF valuation on 2026-06-26:

- Market cap: `2346.40` billion yuan
- PE TTM: `20.83`
- PB: `2.72`
- PE historical percentile: `21.40%`
- PB historical percentile: `41.77%`

Peer comparison:

- 中信建投: PE `20.83`, PB `2.72`
- 中信证券: PE `12.18`, PB `1.44`
- 华泰证券: PE `10.50`, PB `1.03`
- 中金公司: PE `15.16`, PB `1.67`

GF 2026 Q1 comparison with 中信证券:

- 中信建投 net profit margin: `47.69%`
- 中信建投 net profit growth: `98.76%`
- 中信建投 operating income growth: `56.45%`
- 中信建投 ROE: `2.89%`
- 中信证券 net profit growth: `54.68%`
- 中信证券 operating income growth: `30.37%`
- 中信证券 ROE: `3.05%`

Interpretation: 中信建投 has stronger short-term growth acceleration, but its valuation premium over larger peers is also clear.

## Final Judgment Framework

For 中信建投, the combined Huatai and GF workflow points to:

- Strength: strong 2025 recovery and very strong 2026 Q1 earnings acceleration
- Strength: clear brokerage/investment banking/institutional business exposure to capital market recovery
- Risk: securities firms remain cyclical and sensitive to market turnover, IPO/refinancing pace, and proprietary trading conditions
- Risk: valuation is higher than 中信证券、华泰证券、中金公司 on PE and PB
- Short-term signal: Huatai funds flow was negative on 2026-06-29, so near-term momentum needs confirmation
- Key follow-up: daily market turnover, IPO pipeline, proprietary trading performance, 2026 H1 earnings continuity

Practical conclusion: 中信建投 is a high-beta securities stock with strong earnings acceleration. It is more attractive if the capital market recovery continues, but the valuation premium means the stock needs sustained earnings delivery to justify further upside.

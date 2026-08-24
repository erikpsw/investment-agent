---
name: analyze-investment-portfolio
description: Use when a user asks to diagnose, deeply analyze, review, rebalance, or explicitly modify a cloud-connected investment portfolio obtained from the Portfolio Management MCP, review current broad-market conditions, or identify sector-led new-position opportunities, including A-shares or US stocks, index/market-breadth analysis, sector trends, formula-based quantitative stock screening, conditional entry plans, position buys/sells, and cash adjustments.
---

# Analyze Investment Portfolio

## Overview

Build one evidence-backed view of every cloud-connected account before recommending action. Use cloud account data only, reconcile conflicting cloud sources, include cash, and label any incomplete account explicitly.

## Cloud-Only Source Boundary

- Use the authenticated Portfolio Management MCP as the sole source for holdings, balances, cost basis, portfolio P/L, and account performance.
- Do not use IBKR, ErikAI, or another broker connector to fetch or fill gaps in positions or account data. IBKR tools may be used only for instrument-level research after the Portfolio Management MCP has identified the holding.
- Do not search for, read, infer from, or cite workspace files, local portfolio stores, exported statements, cached reports, browser storage, databases on disk, or prior local analysis.
- Local client scripts may call remote Huatai or Guangfa APIs, but their local files and caches are not portfolio evidence.
- If some cloud accounts succeed, continue with them and label the result `partial`. If no cloud account returns holdings or balances, label the result `blocked` and stop before portfolio diagnosis or recommendations.
- Do not ask the user to paste holdings as a fallback. State which cloud connection or authorization is missing and how it could change the conclusion.

## Required Workflow

1. Read [tool-workflow.md](references/tool-workflow.md), discover the Portfolio Management MCP tools, then fetch portfolio details, broad-market snapshot, sector ranking, sector histories/constituents, formula stock ranking, and shortlisted stock quotes/history with maximum safe parallelism.
2. Treat Portfolio Management MCP output as authoritative for holdings, balances, cost basis, P/L, account performance, and pending portfolio changes. Never call IBKR position, balance, performance, order, instruction, or trade tools for portfolio state.
3. Use the Huatai `financial-analysis` skill for diagnosis/market insight. Use Guangfa F10 and valuation skills for A-share company facts, PE/PB, historical percentiles, and financial comparisons.
4. Browse current news for every material holding. Prefer regulatory filings, exchange announcements, and company investor relations; use reputable media for context.
5. Read [analysis-contract.md](references/analysis-contract.md), normalize currencies and combine accounts without double counting.
6. Diagnose portfolio-level risk before judging individual stocks: cash, leverage, concentration, industry correlation, currency, drawdown, realized loss, and unrealized loss.
7. Establish the broad-market regime before interpreting sectors: major indexes, price direction, turnover/volume, breadth, volatility/risk appetite, and cross-market context relevant to the holdings. Then use sector ranking to identify leadership and formula ranking to compare held names with candidates.
8. Build new-position opportunities from confirmed sector leadership, not from an isolated stock rank. For each candidate, verify sector membership, score drivers, fundamentals, valuation, liquidity, technical entry state, current news, incremental portfolio correlation, and event risk. Give an entry trigger, staged sizing, invalidation condition, and maximum risk; otherwise label it watchlist-only.
9. Treat rankings as research signals, not holdings or trade instructions. Reconcile them with fundamentals, valuation, liquidity, news, and portfolio fit before producing condition-based recommendations. Never place orders or create IBKR instructions unless the user explicitly asks.
10. When the user explicitly asks to change the Portfolio Management portfolio record, follow **Explicit Portfolio Mutations** below. Analysis and recommendations alone never authorize a mutation.

## Explicit Portfolio Mutations

Portfolio record changes are allowed only when the user explicitly requests them. They update the cloud portfolio ledger; they do not place a broker order.

1. Before adding or buying an instrument, call `search_portfolio_instruments` with the user's name/code and optional market. Never invent or normalize an identifier yourself.
2. Present or select an unambiguous search result, then pass its returned `instrument_id` to `update_portfolio`. If multiple materially different matches remain, ask the user which one they mean.
3. Use `buy` with `instrument_id`, positive `quantity`, and positive execution `price`. The tool deducts `quantity × price` from the matching CNY/HKD/USD cash balance and recalculates weighted average cost as `(old quantity × old average cost + bought quantity × price) / new quantity`. Insufficient cash is an error.
4. Use `sell` with the existing `instrument_id`, positive `quantity`, and positive execution `price`. The tool adds gross proceeds to the matching currency cash balance. A partial sale recalculates diluted average cost as `(old quantity × old average cost - sold quantity × price) / remaining quantity`; this value may be negative. A full sale removes the position.
5. Use `set_cash` to replace one CNY/HKD/USD cash balance with an exact non-negative amount. Use `adjust_cash` to apply a signed increment; the resulting balance cannot be negative.
6. The mutation uses the same authenticated MCP token as portfolio reads; do not request a new token or change scopes.
7. After every successful mutation, call `get_portfolio_details` and verify the changed quantity, average cost, matching cash balance, currency, and timestamp. Report that the calculation excludes commissions, taxes, FX conversion, settlement delay, and broker execution unless the user supplied and explicitly requested those adjustments.

## Completeness Gate

Attempt every relevant Portfolio Management MCP read endpoint. If a source fails:

- Retry one transient connector/network failure.
- On Windows, check User-scoped `HT_APIKEY` and `GF_SKILLS_APIKEY` without printing values.
- On macOS/Linux, if a Huatai/Guangfa Python client fails with `CERTIFICATE_VERIFY_FAILED`, retry with `SSL_CERT_FILE=$(python -m certifi)` when available. Never disable TLS verification.
- Continue with verified sources and label the result `partial`; never call it a complete portfolio.
- Never fall back to local files, caches, exports, or manually pasted holdings.
- State the missing source and how it could change the conclusion.

## Output Contract

Return sections in this order:

1. Verdict and top three risks.
2. Combined account table with value, common-currency weight, P/L, and data timestamp.
3. Account health: cash, margin, performance, realized versus unrealized loss.
4. Holding diagnosis with fundamentals, valuation, technical state, and news catalysts/risks.
5. Current market conditions: relevant major indexes, direction, turnover/volume, breadth, volatility/risk appetite, cross-market context, and timestamp.
6. Sector regime and quantitative screen: leadership, breadth, held-name alignment, candidate shortlist, score drivers, and disqualifying risks.
7. Sector-led new-position opportunities: thesis, sector evidence, candidate fit, entry zone or observable trigger, staged target size, invalidation/stop condition, catalyst, and principal risks. State `no qualified entry` when evidence is insufficient.
8. Existing-position action plan ordered by urgency, using observable price/position conditions and suggested risk limits.
9. Data gaps, conflicting source conventions, and source links.

Separate facts, inferences, and recommendations. Explain why advice from a provider is accepted or rejected. Cost basis is not support; do not recommend waiting merely to break even.

## Example

User: "深度分析 Portfolio Management 里的全部持仓，用华泰、广发和最新新闻给操作建议。"

Fetch portfolio details, current broad-market conditions, sector and formula rankings; cross-check A-share valuations, browse material news, calculate combined weights, interpret sectors within the market regime, identify candidates inside confirmed leading sectors, validate their portfolio fit, then give conditional new-entry and existing-position plans.

## Common Mistakes

- Treating share count as portfolio weight.
- Omitting cash or double counting the same position.
- Treating TWR drawdown as current unrealized P/L.
- Fetching positions, balances, performance, orders, instructions, or trades from IBKR instead of Portfolio Management MCP.
- Treating a sector or formula ranking as a position, a complete market forecast, or an automatic buy list.
- Calling one index move a market regime without checking volume/turnover, breadth, and the timestamp/session state.
- Recommending a high-ranked stock that is not demonstrably aligned with a confirmed leading sector.
- Giving a new-position idea without an entry trigger, staged size, invalidation condition, or incremental concentration check.
- Comparing ranking scores across different market/mode runs without preserving parameters and timestamps.
- Copying a provider's recommendation without reconciling cost, concentration, or data date.
- Using industrial-company leverage heuristics for brokers.
- Giving precise targets from one technical source or uncited current news.
- Treating a local portfolio file or cached report as a fallback when cloud access fails.
- Adding a position with a guessed ticker instead of a returned `instrument_id`.
- Changing a portfolio during analysis without an explicit mutation request.
- Forgetting the automatic same-currency cash deduction/addition or applying the conventional unchanged-cost sell rule instead of this portfolio's diluted-cost formula.

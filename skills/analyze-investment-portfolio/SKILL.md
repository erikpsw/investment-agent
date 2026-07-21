---
name: analyze-investment-portfolio
description: Use when a user asks to diagnose, deeply analyze, review, or rebalance a cloud-connected investment portfolio spread across ErikAI, Interactive Brokers, A-shares, or US stocks, especially when current holdings, cash, performance, valuation, and recent news must be reconciled without using local portfolio files or caches.
---

# Analyze Investment Portfolio

## Overview

Build one evidence-backed view of every cloud-connected account before recommending action. Use cloud account data only, reconcile conflicting cloud sources, include cash, and label any incomplete account explicitly.

## Cloud-Only Source Boundary

- Use authenticated cloud account connectors and current remote APIs as portfolio evidence.
- Do not search for, read, infer from, or cite workspace files, local portfolio stores, exported statements, cached reports, browser storage, databases on disk, or prior local analysis.
- Local client scripts may call remote Huatai or Guangfa APIs, but their local files and caches are not portfolio evidence.
- If some cloud accounts succeed, continue with them and label the result `partial`. If no cloud account returns holdings or balances, label the result `blocked` and stop before portfolio diagnosis or recommendations.
- Do not ask the user to paste holdings as a fallback. State which cloud connection or authorization is missing and how it could change the conclusion.

## Required Workflow

1. Read [tool-workflow.md](references/tool-workflow.md), then fetch all available accounts in parallel.
2. Use ErikAI for its authenticated portfolio and IBKR for positions, balances, currency exposure, allocation, orders, and multi-period performance.
3. Use the Huatai `financial-analysis` skill for diagnosis/market insight. Use Guangfa F10 and valuation skills for A-share company facts, PE/PB, historical percentiles, and financial comparisons.
4. Browse current news for every material holding. Prefer regulatory filings, exchange announcements, and company investor relations; use reputable media for context.
5. Read [analysis-contract.md](references/analysis-contract.md), normalize currencies and combine accounts without double counting.
6. Diagnose portfolio-level risk before judging individual stocks: cash, leverage, concentration, industry correlation, currency, drawdown, realized loss, and unrealized loss.
7. Produce condition-based recommendations. Never place orders or create IBKR instructions unless the user explicitly asks.

## Completeness Gate

Attempt every configured cloud source. If a source fails:

- Retry one transient connector/network failure.
- On Windows, check User-scoped `HT_APIKEY` and `GF_SKILLS_APIKEY` without printing values.
- Continue with verified sources and label the result `partial`; never call it a complete portfolio.
- Never fall back to local files, caches, exports, or manually pasted holdings.
- State the missing source and how it could change the conclusion.

## Output Contract

Return sections in this order:

1. Verdict and top three risks.
2. Combined account table with value, common-currency weight, P/L, and data timestamp.
3. Account health: cash, margin, performance, realized versus unrealized loss.
4. Holding diagnosis with fundamentals, valuation, technical state, and news catalysts/risks.
5. Action plan ordered by urgency, using observable price/position conditions and suggested risk limits.
6. Data gaps, conflicting source conventions, and source links.

Separate facts, inferences, and recommendations. Explain why advice from a provider is accepted or rejected. Cost basis is not support; do not recommend waiting merely to break even.

## Example

User: "深度分析我的全部持仓，包括 ErikAI 和 IBKR，用华泰、广发和最新新闻给操作建议。"

Fetch both accounts, include IBKR cash, cross-check A-share valuations, browse material news, calculate combined weights, then give a prioritized conditional plan.

## Common Mistakes

- Treating share count as portfolio weight.
- Omitting cash or double counting the same position.
- Treating TWR drawdown as current unrealized P/L.
- Copying a provider's recommendation without reconciling cost, concentration, or data date.
- Using industrial-company leverage heuristics for brokers.
- Giving precise targets from one technical source or uncited current news.
- Treating a local portfolio file or cached report as a fallback when cloud access fails.

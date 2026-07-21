# Analysis Contract

## Normalize and Reconcile

Use only assets returned by authenticated cloud account connectors. Never supplement them from local files or caches. Choose one reporting currency, normally the user's currency or ErikAI's valuation currency. State the FX rate and timestamp. For every asset calculate:

- market value in native and reporting currency;
- weight = asset value / combined NAV including cash;
- invested weight = asset value / total invested assets excluding cash;
- unrealized P/L and return from cost basis;
- contribution to total unrealized P/L.

Detect likely duplicates by ticker, market, quantity, and account source. Keep accounts separate when ownership is uncertain; do not silently deduplicate.

Use the freshest source for price. Explain close versus intraday and one-day date differences. Compare valuation sources directionally when dates or methodologies differ.

## Diagnose in This Order

1. Account safety: cash, settled cash, leverage, initial/maintenance margin, excess liquidity, pending orders.
2. Historical behavior: TWR/MWR, peak-to-current drawdown, realized loss, commissions, turnover.
3. Structure: single-name, industry, region, currency, style, and speculative exposure.
4. Holdings: business quality, growth, valuation, technical state, catalysts, and tail risks.

Do not infer historical trading loss from current holdings. If IBKR TWR is deeply negative but current unrealized P/L is small, inspect trades or state that closed positions likely dominate.

For financial companies, interpret balance-sheet leverage using sector-specific context. A broker's high liabilities are not directly comparable with an industrial company's debt burden.

## Recommendation Rules

Give a baseline plan plus observable alternatives:

- `If price reclaims resistance with confirming volume/time -> hold or reassess.`
- `If rebound fails near resistance -> trim concentration.`
- `If support breaks on a closing basis -> reduce risk.`

Use at least two independent inputs for a price condition, such as moving averages plus recent support/resistance. Treat provider-generated support levels as estimates.

Anchor sizing to combined NAV, not share count. Respect market lot sizes. Prefer staged changes when a position is concentrated. State target risk bands such as single-name, same-industry, cash, and speculative exposure; explain that these are portfolio controls, not universal rules.

Never recommend averaging down solely because a position is below cost. Never describe loss reduction as "locking profit." Do not promise outcomes or present a forecast as fact.

## News Interpretation

For each material event, answer:

- What changed versus prior expectations?
- Is it recurring operating performance, cyclicality, accounting, financing, or publicity?
- Was the event already priced in?
- Does price/volume confirm or reject the headline?
- What future filing or date can falsify the thesis?

## Quality Gate

Before responding, verify:

- all available cloud accounts and cash are included;
- no local portfolio file, cache, export, browser storage, or on-disk database was used;
- weights sum approximately to 100%;
- timestamps and currencies are visible;
- current P/L is separated from account performance;
- provider disagreements are explained;
- current claims have source links;
- advice is conditional, prioritized, and no trade was placed.

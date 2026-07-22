# Analysis Contract

## Normalize and Reconcile

Use only assets returned by the authenticated Portfolio Management MCP. Never supplement holdings, balances, cost basis, P/L, or performance from IBKR, ErikAI, another broker connector, local files, or caches. Choose one reporting currency, normally the user's currency or Portfolio Management's valuation currency. State the FX rate and timestamp. For every asset calculate:

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
5. Broad-market regime: major indexes, direction, session state, turnover/volume, breadth, volatility/risk appetite, and cross-market confirmation.
6. Sector regime: direction, breadth, turnover confirmation, and leadership concentration.
7. Quantitative candidates: score components, risk flags, portfolio fit, and incremental correlation.
8. New-position opportunities: market and sector confirmation, candidate verification, entry state, staged sizing, and thesis/price invalidation.

Do not infer historical trading loss from current holdings. If Portfolio Management performance is deeply negative but current unrealized P/L is small, inspect Portfolio Management activity/history or state that closed positions or cash flows may dominate. Do not call IBKR trades to fill the gap.

Sector and formula rankings are research evidence, not portfolio-state evidence. They cannot alter holdings, cost basis, weights, or P/L. Preserve their parameters and timestamps, and distinguish returned facts from inferred sector mappings and recommendations.

For financial companies, interpret balance-sheet leverage using sector-specific context. A broker's high liabilities are not directly comparable with an industrial company's debt burden.

## Recommendation Rules

Give a baseline plan plus observable alternatives:

- `If price reclaims resistance with confirming volume/time -> hold or reassess.`
- `If rebound fails near resistance -> trim concentration.`
- `If support breaks on a closing basis -> reduce risk.`

Use at least two independent inputs for a price condition, such as moving averages plus recent support/resistance. Treat provider-generated support levels as estimates.

Anchor sizing to combined NAV, not share count. Respect market lot sizes. Prefer staged changes when a position is concentrated. State target risk bands such as single-name, same-industry, cash, and speculative exposure; explain that these are portfolio controls, not universal rules.

Never recommend averaging down solely because a position is below cost. Never describe loss reduction as "locking profit." Do not promise outcomes or present a forecast as fact.

## New-Position Opportunity Rules

Start with the broad market, then the sector, then select the instrument. A formula rank alone is insufficient. Require all of the following for a `qualified entry`:

- broad-market conditions are compatible with the proposed entry aggressiveness, using index direction plus breadth, turnover/volume, or risk appetite;
- sector trend confirmed by more than the composite score, using performance plus breadth and turnover or leadership quality;
- candidate belongs materially to that sector and has non-degraded current ranking inputs;
- liquidity, fundamentals, valuation, current news, and event calendar have been checked;
- the entry improves or deliberately changes portfolio exposure without violating concentration, sector, style, currency, or speculative-risk limits;
- an observable entry trigger and invalidation condition can be stated.

Offer at most three qualified opportunities and rank them by risk-adjusted portfolio fit, not raw formula score. For each opportunity provide:

- sector thesis and evidence timestamp;
- candidate thesis and why it is preferred over alternatives, including an ETF when single-name risk is unnecessary;
- pullback or breakout entry condition based on at least two technical inputs;
- initial tranche and maximum target weight as percentages of combined NAV;
- add condition, price-risk invalidation, thesis invalidation, catalyst, and main risks;
- feasibility caveat when available cash, lot size, or FX funding is unknown.

Do not force a recommendation. Downgrade to `watchlist` when the sector move is extended, price confirmation is missing, valuation/event risk is excessive, or source quality is incomplete. A degraded formula screen can never produce a `qualified entry`.

## News Interpretation

For each material event, answer:

- What changed versus prior expectations?
- Is it recurring operating performance, cyclicality, accounting, financing, or publicity?
- Was the event already priced in?
- Does price/volume confirm or reject the headline?
- What future filing or date can falsify the thesis?

## Quality Gate

Before responding, verify:

- all accounts and cash returned by Portfolio Management MCP are included;
- no IBKR, ErikAI, or other broker account endpoint was used for portfolio state;
- no local portfolio file, cache, export, browser storage, or on-disk database was used;
- weights sum approximately to 100%;
- timestamps and currencies are visible;
- broad-market claims include session state and reconcile index direction with breadth and turnover/volume or explicitly state missing confirmation;
- current P/L is separated from account performance;
- sector claims reconcile performance, breadth, turnover, and leadership rather than relying on rank alone;
- quant candidates retain market/mode/limit parameters and pass fundamental, liquidity, news, and portfolio-fit checks;
- every qualified new-position opportunity originates from a confirmed leading sector and includes entry, staged sizing, invalidation, catalyst, and risk;
- no opportunity is marked qualified when formula history, timestamp, price fields, or other critical inputs are degraded;
- ranking quality is downgraded for fallback/cache without timestamp, missing fields, zero history enrichment, tied components, or saturated scores;
- rankings were not treated as holdings, automatic trades, or position-sizing instructions;
- provider disagreements are explained;
- current claims have source links;
- advice is conditional, prioritized, and no trade was placed.

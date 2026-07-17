# Index Overview and Mobile Portfolio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add A/HK/US index overview cards with dedicated history pages and make portfolio editing usable on phones while removing the hot ETF panel.

**Architecture:** `StockFetcher` will aggregate Tencent A-share indices and Yahoo global indices into one stable schema with per-symbol failure isolation. The Next.js dashboard will link those results to a focused index page that reuses the history API and candlestick chart. Portfolio data and desktop editing remain unchanged; a responsive card editor becomes the mobile rendering of the same state.

**Tech Stack:** Python 3.12, FastAPI/Pydantic, unittest, Next.js 16 App Router, React 19, TypeScript, TanStack Query, Tailwind CSS, lightweight-charts, Node test runner.

## Global Constraints

- Keep ETF search and backend ETF discovery intact; only remove the hot ETF panel from the portfolio page.
- Use `md` as the mobile/desktop breakpoint.
- Use the nine index mappings and five periods defined in the approved design.
- Isolate quote failures per index and preserve all successful results.
- Do not change portfolio storage, PAT/MCP authorization, or Auth0 behavior.

---

### Task 1: Aggregate Nine Market Indices

**Files:**
- Create: `tests/test_market_overview.py`
- Modify: `data/stock_fetcher.py`
- Modify: `api/schemas.py`

**Interfaces:**
- Consumes: `TencentClient.get_index(code, name)` and `YFinanceClient.get_quote(ticker)`.
- Produces: `StockFetcher.get_market_overview() -> {"indices": list[dict], "timestamp": str}` where every item includes `code`, `name`, `market`, `history_ticker`, `price`, `change`, and `change_percent`.

- [ ] **Step 1: Write the failing aggregation tests**

```python
def test_market_overview_contains_all_configured_indices():
    fetcher = make_fetcher()
    result = fetcher.get_market_overview()
    assert [(item["name"], item["market"], item["history_ticker"]) for item in result["indices"]] == EXPECTED_INDICES

def test_market_overview_skips_only_the_failed_index():
    fetcher = make_fetcher(failed_yahoo="^HSTECH")
    result = fetcher.get_market_overview()
    assert "恒生科技指数" not in [item["name"] for item in result["indices"]]
    assert len(result["indices"]) == 8
```

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m pytest tests/test_market_overview.py -q`

Expected: FAIL because the current method returns only Tencent's existing A-share overview and omits `market` and `history_ticker`.

- [ ] **Step 3: Implement fixed mappings and isolated aggregation**

```python
A_SHARE_INDICES = (
    ("sh000001", "上证指数", "000001.SS"),
    ("sz399001", "深证成指", "399001.SZ"),
    ("sz399006", "创业板指", "399006.SZ"),
    ("sh000300", "沪深300", "000300.SS"),
)
GLOBAL_INDICES = (
    ("^HSI", "恒生指数", "HK"),
    ("^HSTECH", "恒生科技指数", "HK"),
    ("^GSPC", "标普500", "US"),
    ("^IXIC", "纳斯达克综合", "US"),
    ("^DJI", "道琼斯工业指数", "US"),
)

def get_market_overview(self):
    indices = []
    for code, name, history_ticker in A_SHARE_INDICES:
        try:
            quote = self.tencent.get_index(code, name)
            if quote.get("price") is not None:
                indices.append({**quote, "market": "CN", "history_ticker": history_ticker})
        except Exception:
            continue
    for ticker, name, market in GLOBAL_INDICES:
        try:
            quote = self.yfinance.get_quote(ticker)
            if quote.get("price") is not None and not quote.get("error"):
                indices.append({
                    "code": ticker, "name": name, "market": market,
                    "history_ticker": ticker, "price": quote.get("price"),
                    "change": quote.get("change"),
                    "change_percent": quote.get("change_percent"),
                })
        except Exception:
            continue
    return {"indices": indices, "timestamp": datetime.now().isoformat()}
```

Extend `MarketIndex` with required `market: str` and `history_ticker: str` fields.

- [ ] **Step 4: Run focused and full backend tests**

Run: `python -m pytest tests/test_market_overview.py -q`

Expected: PASS.

Run: `python -m pytest tests -q`

Expected: all backend tests PASS.

### Task 2: Make Market Cards Link to Index Details

**Files:**
- Create: `web/src/lib/market-index.ts`
- Create: `web/tests/market-index.test.ts`
- Modify: `web/package.json`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/components/market-overview.tsx`

**Interfaces:**
- Consumes: `MarketIndex.history_ticker` from Task 1.
- Produces: `marketIndexHref(index: MarketIndex): string` and `MARKET_INDEXES` metadata used by the dashboard and detail page.

- [ ] **Step 1: Write failing URL and metadata tests**

```typescript
test("encodes caret-prefixed Yahoo index tickers", () => {
  assert.equal(marketIndexHref({ history_ticker: "^IXIC" } as MarketIndex), "/market/index/%5EIXIC");
});

test("defines all supported periods", () => {
  assert.deepEqual(INDEX_PERIODS.map((item) => item.value), ["5d", "1mo", "3mo", "6mo", "1y"]);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `npx tsx --test tests/market-index.test.ts`

Expected: FAIL because `market-index.ts` does not exist.

- [ ] **Step 3: Implement metadata, types, and links**

```typescript
export const INDEX_PERIODS = [
  { value: "5d", label: "5日" },
  { value: "1mo", label: "1月" },
  { value: "3mo", label: "3月" },
  { value: "6mo", label: "6月" },
  { value: "1y", label: "1年" },
] as const;

export function marketIndexHref(index: Pick<MarketIndex, "history_ticker">) {
  return `/market/index/${encodeURIComponent(index.history_ticker)}`;
}
```

Add `market` and `history_ticker` to the frontend `MarketIndex` interface. Render each market card inside a Next `Link`, add a market badge, keyboard focus styles, and a responsive `sm:grid-cols-2 lg:grid-cols-3` grid.

- [ ] **Step 4: Run the frontend unit test**

Run: `npx tsx --test tests/market-index.test.ts`

Expected: PASS.

### Task 3: Add the Dedicated Index History Page

**Files:**
- Create: `web/src/app/market/index/[ticker]/page.tsx`
- Modify: `web/src/lib/market-index.ts`

**Interfaces:**
- Consumes: decoded route ticker, `INDEX_PERIODS`, `api.getMarketOverview()`, and `CandlestickChart`.
- Produces: `/market/index/[ticker]` with quote header and period-controlled chart.

- [ ] **Step 1: Extend the metadata test for lookup behavior**

```typescript
test("looks up a supported index by history ticker", () => {
  assert.equal(findMarketIndex("^HSI")?.name, "恒生指数");
  assert.equal(findMarketIndex("UNKNOWN"), undefined);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `npx tsx --test tests/market-index.test.ts`

Expected: FAIL because `findMarketIndex` does not exist.

- [ ] **Step 3: Add metadata lookup and the client detail page**

```tsx
const [period, setPeriod] = useState<IndexPeriod>("1mo");
const ticker = decodeURIComponent(useParams<{ ticker: string }>().ticker);
const metadata = findMarketIndex(ticker);

return (
  <main className="flex-1 space-y-6 p-4 sm:p-6">
    <Link href="/">返回市场概览</Link>
    <Card>
      <CardHeader>{metadata?.name ?? ticker}</CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">{INDEX_PERIODS.map(renderPeriodButton)}</div>
        <CandlestickChart ticker={ticker} period={period} interval="1d" />
      </CardContent>
    </Card>
  </main>
);
```

Read the matching live quote from `useMarketOverview`; show an explicit unavailable state when the quote or chart data cannot be loaded.

- [ ] **Step 4: Run metadata tests and build type checking**

Run: `npx tsx --test tests/market-index.test.ts && npm run build`

Expected: test PASS and Next.js build exit code 0 with the dynamic index route listed.

### Task 4: Replace the Mobile Portfolio Table with Cards

**Files:**
- Modify: `web/src/app/portfolio/page.tsx`
- Modify: `web/tests/auth-route.test.ts`

**Interfaces:**
- Consumes: existing `positions`, `updatePosition`, `PositionSearchInput`, formatters, and delete handler.
- Produces: mobile-only position cards and desktop-only existing table using the same state.

- [ ] **Step 1: Add failing structural regression tests**

```typescript
test("portfolio renders mobile cards and desktop table without the hot ETF panel", async () => {
  const source = await readPortfolioSource();
  assert.doesNotMatch(source, /HotEtfSectors/);
  assert.match(source, /data-testid="mobile-position-card"/);
  assert.match(source, /className="hidden[^\"]*md:block/);
  assert.match(source, /className="[^\"]*md:hidden/);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `npm run test:auth`

Expected: FAIL because the hot ETF panel remains and no mobile cards exist.

- [ ] **Step 3: Remove only the portfolio hot ETF presentation**

Delete the `HotEtfSectors` and `HotEtfSectorItem` imports, `addEtfPosition`, and `<HotEtfSectors onAdd={addEtfPosition} />`. Do not remove API methods, scanner code, or ETF search support.

- [ ] **Step 4: Make the search input viewport-safe**

```typescript
const viewportPadding = 12;
const width = Math.min(Math.max(rect.width, 300), window.innerWidth - viewportPadding * 2);
const left = Math.min(Math.max(rect.left, viewportPadding), window.innerWidth - width - viewportPadding);
setDropdownStyle({ left, top: rect.bottom + 6, width });
```

Change the wrapper to `relative w-full min-w-0`.

- [ ] **Step 5: Add the mobile card editor and preserve the desktop table**

```tsx
function MobilePositionCard({
  position,
  index,
  onUpdate,
  onRemove,
}: {
  position: PortfolioPosition;
  index: number;
  onUpdate: (index: number, patch: Partial<PortfolioPosition>) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <Card data-testid="mobile-position-card">
      <CardContent className="space-y-4 pt-6">
        <PositionSearchInput
          value={position.ticker}
          onInput={(value) => {
            const market = marketFor(value);
            onUpdate(index, { ticker: value, market, currency: currencyForMarket(market) });
          }}
          onSelect={(result) => onUpdate(index, {
            ticker: result.code,
            name: result.name,
            market: result.market,
            currency: currencyForMarket(result.market),
          })}
        />
        <Input
          value={position.name || ""}
          onChange={(event) => onUpdate(index, { name: event.target.value })}
          placeholder="名称"
        />
        <div className="grid grid-cols-2 gap-3">
          <Input value={position.market || ""} onChange={(event) => onUpdate(index, { market: event.target.value.toUpperCase() })} placeholder="市场" />
          <Input value={position.currency || "CNY"} onChange={(event) => onUpdate(index, { currency: event.target.value.toUpperCase() })} placeholder="币种" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1 text-xs text-muted-foreground">数量<Input type="number" value={position.quantity} onChange={(event) => onUpdate(index, { quantity: Number(event.target.value) })} /></label>
          <label className="space-y-1 text-xs text-muted-foreground">买入均价<Input type="number" value={position.avg_cost} onChange={(event) => onUpdate(index, { avg_cost: Number(event.target.value) })} /></label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Metric label={`现价 (${position.currency || "CNY"})`} value={formatNumber(position.current_price)} />
          <Metric label="市值 (人民币)" value={`¥${formatNumber(position.market_value)}`} />
          <Metric label="浮盈亏 (人民币)" value={`¥${formatNumber(position.pnl)}`} className={pnlClass(position.pnl)} />
          <Metric label="盈亏比例" value={formatPct(position.pnl_percent)} className={pnlClass(position.pnl_percent)} />
        </div>
        <Input value={position.notes || ""} onChange={(event) => onUpdate(index, { notes: event.target.value })} placeholder="策略/原因" />
        <Button variant="outline" className="w-full" onClick={() => onRemove(index)}><Trash2 className="mr-2 h-4 w-4" />删除持仓</Button>
      </CardContent>
    </Card>
  );
}

<div className="space-y-4 md:hidden">
  {positions.map((position, index) => (
    <MobilePositionCard key={index} position={position} index={index} onUpdate={updatePosition} onRemove={(itemIndex) => setPositions((current) => current.filter((_, currentIndex) => currentIndex !== itemIndex))} />
  ))}
</div>
```

Wrap the current complete `Table` element in `<div className="hidden overflow-x-auto md:block">`; its `TableHeader` and `TableBody` remain byte-for-byte unchanged.

- [ ] **Step 6: Run regression tests**

Run: `npm run test:auth`

Expected: PASS.

### Task 5: Full Verification and Production Smoke Test

**Files:**
- No production code changes expected.

**Interfaces:**
- Consumes: all deliverables from Tasks 1-4.
- Produces: verification evidence for backend, frontend, desktop, and mobile behavior.

- [ ] **Step 1: Run all automated checks**

Run: `python -m pytest tests -q`

Expected: all backend tests PASS.

Run: `npm run test:auth && npm run test:mcp && npx tsx --test tests/market-index.test.ts && npm run lint && npm run build`

Expected: all tests PASS, lint has zero errors, and build exits 0.

- [ ] **Step 2: Run live API smoke checks**

Run: `curl -sS http://127.0.0.1:8000/api/market/overview`

Expected: JSON contains available CN/HK/US indices with `market` and `history_ticker`.

Run: `curl -sS "http://127.0.0.1:8000/api/history/%5EIXIC?period=1mo&interval=1d"`

Expected: JSON contains `bars` or a controlled empty response, never a server crash.

- [ ] **Step 3: Verify responsive UI in the browser**

At desktop width, verify the portfolio table and clickable index cards. At a phone viewport, verify the table is hidden, each holding is a card, all editable fields fit, and the search dropdown stays inside the viewport. Open one CN, one HK, and one US index detail route and switch all five periods.

- [ ] **Step 4: Review the final diff**

Run: `git diff --check` and `git diff --stat`.

Expected: no whitespace errors and no unrelated file churn.

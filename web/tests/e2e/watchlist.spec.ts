import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/financials/**", route => route.fulfill({ json: {} }));
  await page.route("**/api/financial-history/**", route => route.fulfill({ json: { data: [] } }));
  await page.route("**/api/news/**", route => route.fulfill({ json: { news: [] } }));
  await page.route("**/api/foreign/**", route => route.fulfill({ json: { filings: [] } }));
  await page.route("**/api/disclosure/**", route => route.fulfill({ json: { documents: [] } }));
});

test("selected group quotes refresh automatically and manually without bulk research", async ({ page }) => {
  await page.route("**/auth/profile", route => route.fulfill({ json: { sub: "test|quotes", name: "Test" } }));
  await page.route("**/auth/access-token*", route => route.fulfill({ json: { token: "test" } }));
  let calls = 0;
  await page.route("**/api/watchlists**", route => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("include_quotes") === "true") calls++;
    expect(url.searchParams.get("include_history")).toBe("false");
    const group = { id: "refresh", name: "美股", items: [{ ticker: "VICR", market: "US", name: "Vicor", research: { quote: { price: 100 + calls } } }], children: [] };
    return route.fulfill({ json: { result: { groups: [group] } } });
  });
  await page.clock.install();
  await page.goto("/watchlist");
  await expect.poll(() => calls).toBe(1);
  await expect(page.getByRole("button", { name: "刷新本组报价" })).toBeEnabled();
  await page.clock.fastForward(61_000);
  await expect.poll(() => calls).toBe(2);
  await expect(page.getByRole("button", { name: "刷新本组报价" })).toBeEnabled();
  await page.getByRole("button", { name: "刷新本组报价" }).click();
  await expect.poll(() => calls).toBe(3);
});

test("watchlist opens details, refreshes automatically and stops on close", async ({ page }) => {
  let detailCalls = 0;
  let notesCalls = 0;
  const research = { quote: { price: 100, currency: "USD" }, returns: {}, moving_averages: {}, technical: {}, history: [{ time: "2026-09-29", close: 99 }, { time: "2026-09-30", close: 100 }], errors: [] };
  const group = { id: "test-core", name: "美股测试", parent_id: null, children: [], items: [{ ticker: "AAPL", market: "US", name: "苹果", notes: "", research }] };
  await page.route("**/auth/profile", route => route.fulfill({ json: { sub: "test|watchlist", name: "Test" } }));
  await page.route("**/auth/access-token*", route => route.fulfill({ json: { token: "local-test-token" } }));
  await page.route("**/api/watchlists**", async route => {
    const request = route.request();
    if (request.url().endsWith("/items/AAPL/research")) {
      detailCalls++;
      return route.fulfill({ json: { status: "ok", result: { ...research, quote: { price: 100 + detailCalls, currency: "USD" } } } });
    }
    if (request.method() === "PATCH") { notesCalls++; return route.fulfill({ json: { status: "ok", result: {} } }); }
    if (request.url().endsWith("/watchlists/research")) return route.fulfill({ json: { status: "ok", result: { items: group.items } } });
    return route.fulfill({ json: { status: "ok", result: { groups: [group], storage: "test" } } });
  });
  await page.clock.install();
  await page.goto("/watchlist");
  await expect(page.getByRole("heading", { name: "自选股", exact: true })).toBeVisible();
  await page.getByText("管理分组与添加股票", { exact: true }).click();
  await page.getByPlaceholder("备注").fill("测试备注");
  expect(notesCalls).toBe(0);
  await page.getByRole("button", { name: "AAPL 走势与关键数据", exact: true }).filter({ visible: true }).click();
  await expect.poll(() => detailCalls).toBe(1);
  await expect(page.getByRole("dialog")).toContainText("101");
  await expect(page.getByRole("button", { name: /20日/ })).toBeVisible();
  await page.clock.fastForward(61_000);
  await expect.poll(() => detailCalls).toBe(2);
  await expect(page.getByRole("dialog")).toContainText("102");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.clock.fastForward(61_000);
  expect(detailCalls).toBe(2);
});


test("mobile stock list stays above long groups and group search is usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const groups = Array.from({ length: 60 }, (_, index) => ({ id: `group-${index}`, name: `A股-行业${index}`, parent_id: null, children: [], items: [{ ticker: `TEST${index}`, name: `股票${index}`, market: "CN", notes: "", research: { quote: { price: 10, day_change_percent: 1 } } }] }));
  await page.route("**/auth/profile", route => route.fulfill({ json: { sub: "test|mobile", name: "Mobile" } }));
  await page.route("**/auth/access-token*", route => route.fulfill({ json: { token: "test-mobile" } }));
  let bulkRequests = 0;
  await page.route("**/api/watchlists**", route => {
    if (route.request().url().includes("/items/")) return route.fulfill({ json: { status: "ok", result: { quote: { price: 10 }, history: [], returns: {}, errors: [] } } });
    if (route.request().url().endsWith("/research")) bulkRequests++;
    const groupId = new URL(route.request().url()).searchParams.get("group_id");
    return route.fulfill({ json: { status: "ok", result: { groups: groupId ? groups.filter(group => group.id === groupId) : groups } } });
  });
  await page.goto("/watchlist");
  const stock = page.getByRole("button", { name: "TEST0 走势与关键数据", exact: true }).filter({ visible: true });
  await expect(stock).toBeVisible();
  expect((await stock.boundingBox())!.y).toBeLessThan(650);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  expect(bulkRequests).toBe(0);
  await page.getByRole("button", { name: "切换自选分组" }).click();
  await page.getByRole("textbox", { name: "搜索分组" }).fill("行业59");
  await page.getByRole("button", { name: "A股-行业59 1 只" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const selectedStock = page.getByRole("button", { name: "TEST59 走势与关键数据", exact: true }).filter({ visible: true });
  await expect(selectedStock).toBeVisible();
  await selectedStock.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect((await page.getByRole("dialog").boundingBox())!.width).toBeGreaterThan(380);
  await page.getByRole("button", { name: "返回列表" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
});

for (const security of [{ ticker: "VICR", market: "US", reportPath: "/api/foreign/us/filings/VICR", documents: { filings: [{ description: "2025 Annual Report", type: "10-K", date: "2026-02-01", url: "https://www.sec.gov/report.html" }] } }, { ticker: "hk00700", market: "HK", reportPath: "/api/foreign/hk/announcements/hk00700", documents: { filings: [{ description: "2025 Annual Report", date: "2026-02-01", url: "https://www.hkexnews.hk/report.html" }] } }, { ticker: "sh600519", market: "CN", reportPath: "/api/disclosure/sh600519", documents: { documents: [{ title: "2025 Annual Report", date: "2026-02-01", url: "https://www.cninfo.com.cn/report.html" }] } }]) {
  test(`mobile watchlist financials and news: ${security.market}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    let reports = 0; let news = 0;
    await page.route("**/auth/profile", route => route.fulfill({ json: { sub: "test|financial", name: "Test" } }));
    await page.route("**/auth/access-token*", route => route.fulfill({ json: { token: "test" } }));
    const research = { quote: { price: 100 }, history: [{ time: "2026-01-01", close: 100 }], errors: [] };
    const group = { id: "financial", name: "测试", items: [{ ...security, name: "测试公司", notes: "", research }], children: [] };
    await page.route("**/api/watchlists**", route => route.fulfill({ json: { status: "ok", result: route.request().url().includes("/items/") ? research : { groups: [group] } } }));
    await page.route(`**${security.reportPath}*`, route => { reports++; return route.fulfill({ json: security.documents }); });
    await page.route("**/api/financial-history/**", route => route.fulfill({ json: { data: [{ period: "2025", revenue: 123, net_profit: null, total_assets: 456, operating_cash_flow: 78 }], updated_at: "2026-01-01" } }));
    await page.route("**/api/news/**", route => { news++; return route.fulfill({ json: { news: [{ title: "测试新闻", source: "测试来源", published: "2026-01-01", link: "https://example.com/news" }] } }); });
    await page.goto("/watchlist");
    await page.getByRole("button", { name: `${security.ticker} 走势与关键数据`, exact: true }).filter({ visible: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("2025 Annual Report")).toBeVisible();
    await expect(dialog.getByText("营业收入", { exact: true })).toBeVisible();
    await expect.poll(() => reports).toBe(1);
    await expect.poll(() => news).toBe(1);
    await expect(dialog.getByRole("link", { name: "测试新闻" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}

test("long chart ranges fetch history beyond one year", async ({ page }) => {
  const periods: string[] = [];
  await page.route("**/api/quote/**", route => route.fulfill({ json: { ticker: "VICR", name: "Vicor", price: 10, market: "US" } }));
  await page.route("**/api/financials/**", route => route.fulfill({ json: {} }));
  await page.route("**/api/history/**", route => { periods.push(new URL(route.request().url()).searchParams.get("period")!); return route.fulfill({ json: { bars: Array.from({ length: 100 }, (_, i) => ({ time: new Date(Date.UTC(2015, 0, i + 1)).toISOString().slice(0, 10), open: 10, high: 12, low: 9, close: 11, volume: 10 })) } }); });
  await page.route("**/api/financial-history/**", route => route.fulfill({ json: { data: [] } }));
  await page.route("**/api/news/**", route => route.fulfill({ json: { news: [] } }));
  await page.route("**/api/foreign/**", route => route.fulfill({ json: { filings: [] } }));
  await page.goto("/stock/VICR");
  await expect(page.getByRole("heading", { name: "Vicor", exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "5年", exact: true }).click();
  await expect.poll(() => periods.includes("10y")).toBe(true);
  await page.getByRole("tab", { name: "全部", exact: true }).click();
  await expect.poll(() => periods.includes("max")).toBe(true);
  await expect(page.getByText(/数据范围：2015/)).toBeVisible();
  await expect(page.getByText("暂无与该标的明确相关的新闻。")).toBeVisible();
});


test("stock valuation uses TTM financials instead of mislabelled quote EPS and exposes Yahoo", async ({ page }) => {
  await page.route("**/api/quote/VICR", route => route.fulfill({ json: { ticker: "VICR", name: "Vicor", price: 288.94, pe_ratio: 3.03, market: "US", source: "Sina" } }));
  await page.route("**/api/financials/VICR", route => route.fulfill({ json: { ticker: "VICR", pe_ratio: 92.60898, eps: 3.12, pe_source: "Yahoo Finance", pe_basis: "TTM" } }));
  await page.route("**/api/history/**", route => route.fulfill({ json: { bars: [] } }));
  await page.goto("/stock/VICR");
  const row = page.getByText("市盈率 (PE · TTM)").locator("..");
  await expect(row).toContainText("92.61");
  await expect(page.getByText("每股收益 (EPS)").locator("..")).toContainText("3.12");
  await expect(page.getByText("估值来源：Yahoo Finance · 行情来源：Sina", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Yahoo Finance ↗", exact: true })).toHaveAttribute("href", "https://finance.yahoo.com/quote/VICR/");
});

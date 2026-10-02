import { test, expect, type Page } from "@playwright/test";

async function setup(page: Page, failAdds = 0, failGroups = 0, signedIn = true) {
  const calls = { quote: 0, history: 0, news: 0, reports: 0, added: [] as Array<{ url: string; body: unknown }> };
  await page.route("**/auth/profile", route => signedIn ? route.fulfill({ json: { sub: "test|actions", name: "Test" } }) : route.fulfill({ status: 401, json: {} }));
  await page.route("**/auth/access-token*", route => route.fulfill({ json: { token: "test" } }));
  await page.route("**/api/**", route => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith("/api/quote/")) { calls.quote++; return route.fulfill({ json: { ticker: "KLIC", name: "Kulicke", market: "US", price: 95, prev_close: 95, change: 0, change_percent: 0, amount: 120000000, market_cap: 5000000000, timestamp: "2026-10-01T12:00:00Z" } }); }
    if (url.pathname.startsWith("/api/history/")) { calls.history++; return route.fulfill({ json: { bars: [{ time: "2026-09-28", open: 93, high: 95, low: 92, close: 94, volume: 100 }, { time: "2026-09-29", open: 94, high: 96, low: 93, close: 95, volume: 110 }] } }); }
    if (url.pathname === "/api/watchlists") {
      if (failGroups-- > 0) return route.fulfill({ status: 503, json: { detail: "分组暂时不可用" } });
      return route.fulfill({ json: { result: { groups: [{ id: "tech", name: "科技", items: [], children: [{ id: "semis", name: "半导体", items: [], children: [] }] }, { id: "existing", name: "已有分组", items: [{ ticker: "KLIC", market: "US" }], children: [] }] } } });
    }
    if (route.request().method() === "POST") {
      if (failAdds-- > 0) return route.fulfill({ status: 503, json: { detail: "添加暂时失败" } });
      calls.added.push({ url: url.pathname, body: route.request().postDataJSON() });
      return route.fulfill({ json: { status: "ok", result: {} } });
    }
    if (url.pathname.startsWith("/api/financial-history/")) return route.fulfill({ json: { data: [{ period: "2025", revenue: 100, net_profit: 10, total_assets: 500, operating_cash_flow: 50 }] } });
    if (url.pathname.startsWith("/api/foreign/")) { calls.reports++; return route.fulfill({ json: { filings: [{ description: "Annual Report", type: "10-K", date: "2025-11-20", url: "https://www.sec.gov/test.html" }] } }); }
    if (url.pathname.startsWith("/api/news/")) calls.news++;
    return route.fulfill({ json: { news: [], documents: [], pe_ratio: 43.41, eps: 2.19, pe_basis: "TTM" } });
  });
  await page.goto("/stock/KLIC");
  return calls;
}

test("add action selects nested group, blocks duplicate, and saves with visible feedback", async ({ page }) => {
  const calls = await setup(page);
  await page.getByRole("button", { name: "添加到自选", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: "确认添加" })).toBeDisabled();
  await dialog.getByLabel("自选分组").selectOption("existing");
  await expect(dialog).toContainText("该股票已在此分组中");
  await expect(dialog.getByRole("button", { name: "确认添加" })).toBeDisabled();
  await dialog.getByLabel("自选分组").selectOption("semis");
  await dialog.getByRole("button", { name: "确认添加" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "已添加 Kulicke" })).toContainText("半导体");
  expect(calls.added).toEqual([{ url: "/api/watchlists/groups/semis/items", body: { ticker: "KLIC", name: "Kulicke", market: "US", notes: "" } }]);
});

test("failed group load and failed add are retryable", async ({ page }) => {
  const calls = await setup(page, 1, 1);
  await page.getByRole("button", { name: "选择分组添加到自选" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("分组加载失败");
  await dialog.getByRole("button", { name: "重试" }).click();
  await dialog.getByLabel("自选分组").selectOption("semis");
  await dialog.getByRole("button", { name: "确认添加" }).click();
  await expect(dialog.getByRole("alert")).toContainText("添加暂时失败");
  await dialog.getByRole("button", { name: "确认添加" }).click();
  await expect(dialog).not.toBeVisible();
  expect(calls.added.length).toBe(1);
});

test("stock refresh, copy link, financial report placement and compact chart work", async ({ page, context }) => {
  await page.setViewportSize({ width: 1413, height: 871 });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const calls = await setup(page);
  await expect(page.getByTestId("financial-history-section")).toContainText("财报原文");
  await expect(page.getByTestId("financial-history-section")).toContainText("Annual Report");
  await expect(page.getByTestId("financial-history-section").getByRole("link", { name: "打开原文" })).toHaveAttribute("href", "https://www.sec.gov/test.html");
  const reportBefore = calls.reports;
  await page.getByRole("button", { name: "季报", exact: true }).click();
  await expect.poll(() => calls.reports).toBeGreaterThan(reportBefore);
  const newsBefore = calls.news;
  await page.getByRole("button", { name: "刷新新闻", exact: true }).click();
  await expect.poll(() => calls.news).toBeGreaterThan(newsBefore);
  await expect(page.getByText("49.74万亿")).toHaveCount(0);
  await expect(page.getByText("50.00亿", { exact: true })).toBeVisible();
  const plot = page.getByTestId("candlestick-plot");
  expect((await plot.boundingBox())!.height).toBeLessThanOrEqual(300);
  await page.getByRole("tab", { name: "5年", exact: true }).click();
  await expect.poll(() => calls.history).toBeGreaterThan(1);
  const quoteBefore = calls.quote; const historyBefore = calls.history;
  await page.getByRole("button", { name: "刷新个股数据" }).click();
  await expect.poll(() => calls.quote).toBeGreaterThan(quoteBefore);
  await expect.poll(() => calls.history).toBeGreaterThan(historyBefore);
  await page.getByRole("button", { name: "复制个股链接" }).click();
  await expect(page.getByRole("status").filter({ hasText: "个股链接已复制" })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("/stock/KLIC");
  await page.getByRole("button", { name: /搜索股票/ }).click();
  await expect(page.getByPlaceholder("输入股票名称或代码，如：茅台、苹果、AAPL...")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 600 });
  await expect.poll(async () => (await plot.boundingBox())!.height).toBeLessThanOrEqual(220);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("empty watchlist offers create-group navigation and cannot submit", async ({ page }) => {
  const calls = await setup(page);
  await page.route("**/api/watchlists?*", route => route.fulfill({ json: { result: { groups: [] } } }));
  await page.getByRole("button", { name: "添加到自选", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("link", { name: "前往自选股创建分组" })).toHaveAttribute("href", "/watchlist");
  await expect(dialog.getByRole("button", { name: "确认添加" })).toBeDisabled();
  await dialog.getByRole("button", { name: "取消" }).click();
  expect(calls.added.length).toBe(0);
});

for (const security of [{ ticker: "sh600519", market: "CN" }, { ticker: "hk00700", market: "HK" }]) {
  test(`add stock sends correct ticker and market: ${security.market}`, async ({ page }) => {
    const calls = await setup(page);
    await page.route(`**/api/quote/${security.ticker}`, route => route.fulfill({ json: { ...security, name: "市场测试", price: 100 } }));
    await page.goto(`/stock/${security.ticker}`);
    await page.getByRole("button", { name: "添加到自选", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("自选分组").selectOption("semis");
    await dialog.getByRole("button", { name: "确认添加" }).click();
    await expect(dialog).not.toBeVisible();
    expect(calls.added[0].body).toMatchObject(security);
  });
}

test("signed out add action leads to login with a return path", async ({ page }) => {
  await setup(page, 0, 0, false);
  await expect(page.getByRole("link", { name: "登录后添加到自选" }).first()).toHaveAttribute("href", "/auth/login?returnTo=%2Fstock%2FKLIC");
});

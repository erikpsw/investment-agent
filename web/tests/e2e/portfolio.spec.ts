import { test, expect } from "@playwright/test";

test("mobile portfolio loads valuation only, protects edits and saves without analysis", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/auth/profile", route => route.fulfill({ json: { sub: "test|portfolio", name: "Test" } }));
  await page.route("**/auth/access-token*", route => route.fulfill({ json: { token: "test" } }));
  await page.route("**/api/portfolio/tokens", route => route.fulfill({ json: { result: { tokens: [] } } }));
  let positions = [{ ticker: "VICR", name: "Vicor", market: "US", currency: "USD", quantity: 2, avg_cost: 100, current_price: 120, market_value: 1680, pnl: 280, pnl_percent: 20, notes: "" }];
  let analyses = 0;
  let loads = 0;
  await page.route("**/api/portfolio/analyze", route => { analyses++; return route.fulfill({ json: { result: { positions: [] } } }); });
  await page.route("**/api/portfolio/positions**", route => {
    if (route.request().method() === "PUT") positions = route.request().postDataJSON().positions;
    else {
      loads++;
      const url = new URL(route.request().url());
      expect(url.searchParams.get("include_history")).toBe("false");
      expect(url.searchParams.get("include_research")).toBe("false");
    }
    return route.fulfill({ json: { result: { positions, storage: "test" } } });
  });
  await page.goto("/portfolio");
  await expect(page.getByRole("status")).toContainText("估值已更新");
  await expect(page.getByRole("link", { name: "查看走势、财报与新闻" })).toHaveAttribute("href", "/stock/VICR");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  const card = page.getByTestId("mobile-position-card");
  await card.getByRole("spinbutton").first().fill("3");
  await expect(page.getByRole("status")).toContainText("未保存");
  await expect(page.getByRole("button", { name: "刷新估值" })).toBeDisabled();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByText("持仓已保存，估值已更新")).toBeVisible();
  expect(positions[0].quantity).toBe(3);
  expect(analyses).toBe(0);
  expect(loads).toBe(1);
});

test("failed portfolio load cannot overwrite saved holdings", async ({ page }) => {
  await page.route("**/auth/profile", route => route.fulfill({ json: { sub: "test|failure", name: "Test" } }));
  await page.route("**/auth/access-token*", route => route.fulfill({ json: { token: "test" } }));
  await page.route("**/api/portfolio/tokens", route => route.fulfill({ json: { result: { tokens: [] } } }));
  await page.route("**/api/portfolio/positions**", route => route.fulfill({ status: 503, json: { detail: "Storage unavailable" } }));
  await page.goto("/portfolio");
  await expect(page.getByRole("alert").filter({ hasText: "Storage unavailable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "保存", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "添加", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "刷新估值" })).toBeEnabled();
});

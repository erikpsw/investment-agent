import { test, expect } from "@playwright/test";

test("sidebar hides brand when collapsed and remembers preference across reload and navigation", async ({ page }) => {
  await page.route("**/auth/profile", route => route.fulfill({ json: { sub: "test|sidebar", name: "Test" } }));
  await page.route("**/api/**", route => route.fulfill({ json: route.request().url().includes("hot-stocks")
    ? { result: { items: [{ ticker: "TEST", name: "热门测试", price: 100, amount: 1000, heat_score: 80, today_change_percent: 2 }], source: "test" } }
    : { indices: [], results: [] } }));
  await page.goto("/dashboard");
  const sidebar = page.locator("aside").getByTestId("sidebar");
  await expect(sidebar).toHaveAttribute("data-collapsed", "false");
  await sidebar.getByRole("button", { name: "收起侧边栏" }).click();
  await expect(sidebar.getByRole("link", { name: "Investment Agent" })).toHaveCount(0);
  await expect(sidebar.locator('a[href="/"]')).toHaveCount(0);
  await page.reload();
  await expect(sidebar).toHaveAttribute("data-collapsed", "true");
  await sidebar.getByRole("link", { name: "行情搜索", exact: true }).click();
  await expect(sidebar).toHaveAttribute("data-collapsed", "true");
  await sidebar.getByRole("button", { name: "展开侧边栏" }).click();
  await page.reload();
  await expect(sidebar).toHaveAttribute("data-collapsed", "false");
  await expect(sidebar.getByRole("link", { name: "Investment Agent" })).toBeVisible();
  await sidebar.getByRole("button", { name: "收起侧边栏" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Toggle menu" }).click();
  const mobileSidebar = page.getByRole("dialog").getByTestId("sidebar");
  await expect(mobileSidebar).toHaveAttribute("data-collapsed", "false");
  await expect(mobileSidebar.getByRole("link", { name: "Investment Agent" })).toBeVisible();
});

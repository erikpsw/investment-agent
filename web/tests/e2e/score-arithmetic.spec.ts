import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test, expect } from "@playwright/test";
import { chooseSelect, MARKET_OPTION_LABELS } from "./select-support";

for (const ticker of ["sh600519", "hk00700", "AAPL"]) {
  test(`${ticker} formula ranking rejects inconsistent factor arithmetic and refresh restores it`, async ({ page }) => {
    const source = JSON.parse(readFileSync(resolve(process.cwd(), `tests/fixtures/formula-score/${ticker}-balanced.json`), "utf8")).result.item;
    let repaired = false;
    await page.route("**/auth/profile", route => route.fulfill({ json: null }));
    await page.route("**/api/ai-screener/tuning", route => route.fulfill({ json: { result: { status: "not_run", applied: false } } }));
    await page.route("**/api/formula-ranking/backtest*", route => route.fulfill({ json: { result: { status: "not_run", applied: false } } }));
    await page.route("**/api/formula-ranking/holdout*", route => route.fulfill({ json: { result: { status: "not_run", applied: false } } }));
    await page.route("**/api/formula-ranking?**", route => {
      const market = new URL(route.request().url()).searchParams.get("market");
      const item = structuredClone(source); if (!repaired) item.formula_score += 1;
      return route.fulfill({ json: { result: { market, mode: "balanced", items: market === source.market ? [item] : [], total: market === source.market ? 1 : 0 } } });
    });
    await page.goto("/stock-picker");
    if (source.market !== "CN") await page.getByRole("main").getByRole("button", { name: source.market === "HK" ? "港股" : "美股", exact: true }).click();
    await expect(page.getByText("公式排名数据异常，请重试", { exact: true })).toBeVisible({ timeout: 2000 });
    await expect(page.getByRole("link", { name: source.name || ticker, exact: true })).toHaveCount(0);
    repaired = true;
    await page.getByRole("button", { name: "刷新", exact: true }).click();
    await expect(page.getByRole("link", { name: source.name || ticker, exact: true })).toHaveAttribute("href", `/stock/${ticker}?mode=balanced`);
    await expect(page.getByText("公式排名数据异常，请重试", { exact: true })).toHaveCount(0);
  });
  test(`${ticker} inconsistent total is hidden and retry restores archived factor score`, async ({ page }) => {
    const source = JSON.parse(readFileSync(resolve(process.cwd(), `tests/fixtures/formula-score/${ticker}-balanced.json`), "utf8"));
    let repaired = false;
    await page.route("**/auth/profile", route => route.fulfill({ json: null }));
    await page.route("**/api/**", route => {
      const path = new URL(route.request().url()).pathname;
      if (path === `/api/formula-ranking/stock/${ticker}`) {
        const payload = structuredClone(source);
        if (!repaired) payload.result.item.formula_score += 1;
        return route.fulfill({ json: payload });
      }
      if (path.startsWith("/api/quote/")) return route.fulfill({ json: { ticker, price: 100 } });
      return route.fulfill({ json: { bars: [], data: [], news: [], documents: [], filings: [] } });
    });
    await page.goto(`/stock/${ticker}`);
    await expect(page.getByRole("button", { name: "重试评分", exact: true })).toBeVisible();
    await expect(page.getByText(/\/ 100$/, { exact: false })).toHaveCount(0);
    await expect(page.getByText(/^止盈止损参考/)).toHaveCount(0);
    repaired = true;
    await page.getByRole("button", { name: "重试评分", exact: true }).click();
    await expect(page.getByText(`${source.result.item.formula_score.toFixed(1)} / 100`, { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "重试评分", exact: true })).toHaveCount(0);
  });
  test(`${ticker} AI candidate uses the same arithmetic rejection and original-job recovery`, async ({ page }) => {
    const source = JSON.parse(readFileSync(resolve(process.cwd(), `tests/fixtures/formula-score/${ticker}-balanced.json`), "utf8")).result.item;
    let repaired = false, jobId = "";
    const completed = () => {
      const item = structuredClone(source); item.match_reasons = ["原候选"];
      if (!repaired) item.contributions["5日动量"] += 1;
      return { id: jobId, status: "completed", request: { market: source.market, query: "PE小于20" }, response: { result: { market: source.market, plan: { mode: "balanced", summary: "恢复核验候选", filters: [], unsupported: [] }, items: [item] } } };
    };
    await page.route("**/auth/profile", route => route.fulfill({ json: null }));
    await page.route("**/api/formula-ranking**", route => route.fulfill({ json: { result: { status: "not_run", applied: false, items: [], total: 0 } } }));
    await page.route("**/api/ai-screener/tuning", route => route.fulfill({ json: { result: { status: "not_run", applied: false } } }));
    await page.route("**/api/ai-screener/jobs", route => {
      jobId = route.request().postDataJSON().submission_id;
      return route.fulfill({ status: 202, json: { job: completed() } });
    });
    await page.route("**/api/ai-screener/jobs/*", route => route.fulfill({ json: { job: completed() } }));
    await page.goto("/stock-picker");
    await chooseSelect(page, "条件选股市场", MARKET_OPTION_LABELS[source.market as keyof typeof MARKET_OPTION_LABELS]);
    await page.getByLabel("你想找什么样的股票？").fill("PE小于20");
    await page.getByRole("button", { name: "AI 筛选", exact: true }).click();
    await expect(page.getByText("筛选候选数据异常，请刷新查询原任务", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: new RegExp(ticker) })).toHaveCount(0);
    expect(await page.evaluate(() => sessionStorage.getItem("ai-screen-active-job"))).toBe(jobId);
    repaired = true;
    await page.reload();
    await expect(page.getByText("恢复核验候选", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: new RegExp(ticker) })).toHaveAttribute("href", `/stock/${ticker}?mode=balanced`);
    expect(await page.evaluate(() => sessionStorage.getItem("ai-screen-active-job"))).toBeNull();
  });
}

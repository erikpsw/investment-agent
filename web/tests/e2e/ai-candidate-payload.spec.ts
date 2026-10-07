import { test, expect } from "@playwright/test";
import { chooseSelect, MARKET_OPTION_LABELS } from "./select-support";

for (const [ticker, market] of [["sh600519", "CN"], ["hk00700", "HK"], ["BRK.B", "US"]]) {
  for (const defect of ["score", "ticker", "market", "reasons", "duplicate"]) {
    test(`${market} rejects ${defect} candidate payload and recovers original job`, async ({ page }) => {
      let repaired = false, id = "", submissions = 0;
      const errors: string[] = [];
      page.on("pageerror", e => errors.push(e.message));
      await page.route("**/auth/profile", r => r.fulfill({ json: null }));
      await page.route("**/api/formula-ranking**", r => r.fulfill({ json: { result: { items: [], total: 0, market: "CN", mode: "balanced" } } }));
      await page.route("**/api/ai-screener/tuning", r => r.fulfill({ json: { result: { status: "not_run", applied: false } } }));
      function result() {
        const item: Record<string, unknown> = { ticker, market, name: "待核验候选", formula_score: 68, recommendation: "观察", match_reasons: ["符合已验证条件"], risks: [] };
        if (!repaired) {
          if (defect === "score") item.formula_score = "68";
          if (defect === "ticker") item.ticker = market === "US" ? "hk00700" : "AAPL";
          if (defect === "market") item.market = market === "US" ? "HK" : "US";
          if (defect === "reasons") item.match_reasons = "错误类型理由";
        }
        return { market, plan: { mode: "balanced", summary: "原任务恢复完成", filters: [], unsupported: [] }, items: !repaired && defect === "duplicate" ? [item, item] : [item] };
      }
      await page.route("**/api/ai-screener/jobs", r => {
        const request = r.request().postDataJSON(); id = request.submission_id; submissions++;
        return r.fulfill({ status: 202, json: { job: { id, status: "completed", request, response: { result: result() } } } });
      });
      await page.route("**/api/ai-screener/jobs/*", r => {
        expect(new URL(r.request().url()).pathname).toBe(`/api/ai-screener/jobs/${id}`);
        return r.fulfill({ json: { job: { id, status: "completed", request: { market, query: "PE小于20" }, response: { result: result() } } } });
      });
      await page.goto("/stock-picker");
      await chooseSelect(page, "条件选股市场", MARKET_OPTION_LABELS[market as keyof typeof MARKET_OPTION_LABELS]);
      await page.getByLabel("你想找什么样的股票？").fill("PE小于20");
      await page.getByRole("button", { name: "AI 筛选", exact: true }).click();
      await expect(page.getByText("筛选候选数据异常，请刷新查询原任务", { exact: true })).toBeVisible();
      await expect(page.getByRole("link", { name: /待核验候选/ })).toHaveCount(0);
      expect(await page.evaluate(() => sessionStorage.getItem("ai-screen-active-job"))).toBe(id);
      repaired = true;
      await page.reload();
      await expect(page.getByRole("link", { name: /待核验候选/ })).toHaveAttribute("href", `/stock/${ticker}?mode=balanced`);
      await expect(page.getByText("公式分 68.0", { exact: true })).toBeVisible();
      expect(submissions).toBe(1);
      expect(errors).toEqual([]);
    });
  }
}

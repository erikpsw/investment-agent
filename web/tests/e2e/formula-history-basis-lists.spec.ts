import { test, expect } from "@playwright/test";
import { chooseSelect, MARKET_OPTION_LABELS } from "./select-support";

for (const [market, ticker, currency] of [["CN", "sh600519", "CNY"], ["HK", "hk00700", "HKD"], ["US", "AAPL", "USD"]]) {
  for (const location of ["AI", "ranking"]) {
    test(`${market} ${location} candidate retains its history basis`, async ({ page }) => {
      await page.route("**/auth/profile", r => r.fulfill({ json: null }));
      const source=market==="US"?"Yahoo":"Tencent", trendBasis=market==="US"?"adjusted":market==="HK"?"qfq":"raw";
      const protectionBasis=market==="US"?"latest_raw_close_reference":trendBasis;
      const trendLabel=market==="US"?"Yahoo · 调整价":market==="HK"?"腾讯 · 前复权":"腾讯 · 原始价";
      const protectionLabel=market==="US"?"Yahoo · 调整价换算至最近原始价":trendLabel;
      const item = { ticker, market, name: "口径核验候选", formula_score: 68, recommendation: "观察", match_reasons: [], risks: [],
        history_price_metadata: { version: "history-price-metadata-v1", trend: { source, price_basis: trendBasis, status: "reported" },
          protection: { source, price_basis: protectionBasis, status: "reported", bar_count: 21 } }, risk_plan: { status: "not_available" } };
      await page.route("**/api/**", r => {
        const u = new URL(r.request().url());
        if (u.pathname === "/api/ai-screener/jobs") {
          const request = r.request().postDataJSON();
          return r.fulfill({ status: 202, json: { job: { id: request.submission_id, status: "completed", request, response: { result: {
            market, currency, plan: { mode: "conservative", summary: "价格口径候选", filters: [], unsupported: [] }, items: [item],
          } } } } });
        }
        if (u.pathname === "/api/formula-ranking") {
          const selected = u.searchParams.get("market"), available = location === "ranking" && selected === market;
          return r.fulfill({ json: { result: { market: selected, mode: "balanced", items: available ? [item] : [], total: available ? 1 : 0, formula: "口径核验" } } });
        }
        return r.fulfill({ json: { result: { status: "not_run", applied: false }, bars: [], data: [] } });
      });
      const initialRanking = page.waitForResponse(r => new URL(r.url()).pathname === "/api/formula-ranking");
      await page.goto("/stock-picker");
      await initialRanking;
      if (location === "AI") {
        await chooseSelect(page, "条件选股市场", MARKET_OPTION_LABELS[market as keyof typeof MARKET_OPTION_LABELS]);
        await page.getByRole("button", { name: "低估值大盘", exact: true }).click();
      } else if (market !== "CN") {
        // The first market button belongs to historical research; use the ranking control.
        await page.getByRole("button", { name: market === "HK" ? "港股" : "美股", exact: true }).last().click();
      }
      await expect(page.getByText(`保护日K：${protectionLabel}（最近21条）`, { exact: true })).toBeVisible();
      await expect(page.getByText(`动量日K：${trendLabel}`, { exact: true })).toBeVisible();
    });
  }
}

import { test, expect } from "@playwright/test";

for (const [ticker, market] of [["sh600519", "CN"], ["hk00700", "HK"], ["AAPL", "US"]]) {
  for (const mode of ["conservative", "aggressive"]) {
    test(`${market} AI screening links retain ${mode} scoring and protection`, async ({ page }) => {
      await page.route("**/auth/profile", r => r.fulfill({ json: null }));
      await page.route("**/api/**", r => {
        const path = new URL(r.request().url()).pathname;
        const item = { ticker, market, name: "AI模式候选", formula_score: 58, recommendation: "观察", contributions: {}, weights: {}, match_reasons: [], risks: [], risk_plan: { status: "ok", currency: market === "CN" ? "CNY" : market === "HK" ? "HKD" : "USD", reference_price: 100, stop_loss: 90, take_profit_1: 115, take_profit_2: 125, atr14: 4, trailing_distance: 10, position_cap_percent: 10, risk_budget_percent: .5, stop_distance_percent: 10 } };
        if (path === "/api/ai-screener/jobs") {
          const request = r.request().postDataJSON();
          return r.fulfill({ status: 202, json: { job: { id: request.submission_id, status: "completed", request, response: { status: "ok", result: { market, plan: { mode, summary: "AI模式核验", filters: [], unsupported: [] }, items: [item] } } } } });
        }
        if (path.startsWith("/api/formula-ranking/stock/")) {
          const requestedMode = new URL(r.request().url()).searchParams.get("mode");
          return r.fulfill({ json: { result: { status: "ok", mode: requestedMode, item: { ...item, formula_score: requestedMode === mode ? 58 : 99, risk_plan: { ...item.risk_plan, stop_loss: requestedMode === mode ? 90 : 92 } } } } });
        }
        if (path.startsWith("/api/quote/")) return r.fulfill({ json: { ticker, price: 100 } });
        return r.fulfill({ json: { result: { status: "not_run", applied: false }, bars: [], data: [], news: [], documents: [], filings: [] } });
      });
      await page.goto("/stock-picker");
      await page.getByLabel("条件选股市场").selectOption(market);
      await page.getByRole("button", { name: mode === "conservative" ? "低估值大盘" : "放量温和上涨", exact: true }).click();
      const link = page.getByRole("link", { name: new RegExp(`AI模式候选.*${ticker}`) });
      await expect(link).toHaveAttribute("href", `/stock/${ticker}?mode=${mode}`);
      await link.click();
      await expect(page.getByRole("button", { name: `评分模式：${mode === "conservative" ? "稳健" : "进取"}`, exact: true })).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByText("58.0 / 100", { exact: true })).toBeVisible();
      await page.getByText(/^止盈止损参考 ·/).click();
      await expect(page.getByText("止损 90.00（距离 10.00%）", { exact: true })).toBeVisible();
    });
  }
}

for (const ticker of ["sh600519", "hk00700", "AAPL"]) {
  for (const responseMode of ["balanced", undefined]) {
    test(`${ticker} rejects ${responseMode ?? "missing"} response identity for conservative scoring`, async ({ page }) => {
      await page.route("**/auth/profile", r => r.fulfill({ json: null }));
      let retry = false;
      await page.route("**/api/**", r => {
        const path = new URL(r.request().url()).pathname;
        if (path.startsWith("/api/formula-ranking/stock/")) return r.fulfill({ json: { result: { status: "ok", mode: retry ? "conservative" : responseMode, item: { ticker, market: ticker === "AAPL" ? "US" : ticker === "hk00700" ? "HK" : "CN", formula_score: retry ? 58 : 99, recommendation: "观察", contributions: {}, weights: {}, risk_plan: { status: "not_available" } } } } });
        if (path.startsWith("/api/quote/")) return r.fulfill({ json: { ticker, price: 100 } });
        return r.fulfill({ json: { bars: [], data: [], news: [], documents: [], filings: [] } });
      });
      await page.goto(`/stock/${ticker}?mode=conservative`);
      await expect(page.getByText("量化评分暂不可用，未填充默认分数。", { exact: true })).toBeVisible();
      await expect(page.getByText("99.0 / 100", { exact: true })).toHaveCount(0);
      retry = true;
      await page.getByRole("button", { name: "重试评分", exact: true }).click();
      await expect(page.getByText("58.0 / 100", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "评分模式：稳健", exact: true })).toHaveAttribute("aria-pressed", "true");
    });
  }
}

for (const [ticker, market] of [["sh600519", "CN"], ["hk00700", "HK"], ["AAPL", "US"]]) {
  test(`${market} detail mode switches remain in copied links and after refresh`, async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", { value: { writeText: async (value: string) => {
        (window as Window & { copiedStockLink?: string }).copiedStockLink = value;
      } } });
    });
    await page.route("**/auth/profile", r => r.fulfill({ json: null }));
    await page.route("**/api/**", r => {
      const u = new URL(r.request().url());
      if (u.pathname.startsWith("/api/formula-ranking/stock/")) {
        const mode = u.searchParams.get("mode")!;
        return r.fulfill({ json: { result: { status: "ok", mode, item: { ticker, market, formula_score: mode === "conservative" ? 58 : mode === "aggressive" ? 72 : 68, recommendation: "观察", weights: {}, contributions: {}, risk_plan: { status: "not_available" } } } } });
      }
      if (u.pathname.startsWith("/api/quote/")) return r.fulfill({ json: { ticker, market, name: ticker, price: 100 } });
      return r.fulfill({ json: { bars: [], data: [], news: [], documents: [], filings: [] } });
    });
    await page.goto(`/stock/${ticker}?ref=picker#score`);
    await expect(page.getByText("68.0 / 100", { exact: true })).toBeVisible();
    for (const [mode, label, score] of [["conservative", "稳健", "58.0"], ["aggressive", "进取", "72.0"], ["balanced", "均衡", "68.0"]]) {
      const button = page.getByRole("button", { name: `评分模式：${label}`, exact: true });
      await button.click();
      await expect.poll(() => new URL(page.url()).searchParams.get("mode")).toBe(mode);
      await expect(button).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByText(`${score} / 100`, { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "复制个股链接", exact: true }).click();
      const copied = await page.evaluate(() => (window as Window & { copiedStockLink?: string }).copiedStockLink!);
      const url = new URL(copied);
      expect(url.searchParams.get("mode")).toBe(mode);
      expect(url.searchParams.get("ref")).toBe("picker");
      expect(url.hash).toBe("#score");
      await page.reload();
      await expect(button).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByText(`${score} / 100`, { exact: true })).toBeVisible();
    }
  });
}

for (const [ticker, market, label] of [["sh600519", "CN", "A股"], ["hk00700", "HK", "港股"], ["AAPL", "US", "美股"]]) {
  for (const mode of ["conservative", "aggressive"]) {
    test(`${market} ranking detail navigation preserves ${mode} scoring and protection`, async ({ page }) => {
      await page.route("**/auth/profile", r => r.fulfill({ json: null }));
      const detailModes: string[] = [];
      await page.route("**/api/**", r => {
        const u = new URL(r.request().url());
        const requestedMode = u.searchParams.get("mode") || "balanced";
        const item = { ticker, market, name: "模式核验股票", formula_score: requestedMode === "balanced" ? 68 : 58, recommendation: "观察", weights: {}, contributions: {}, risk_plan: { status: "ok", currency: market === "CN" ? "CNY" : market === "HK" ? "HKD" : "USD", reference_price: 100, stop_loss: requestedMode === "balanced" ? 92 : 90, take_profit_1: 115, take_profit_2: 125, atr14: 4, trailing_distance: 10, position_cap_percent: 10, risk_budget_percent: .5, stop_distance_percent: requestedMode === "balanced" ? 8 : 10 } };
        if (u.pathname === "/api/formula-ranking") return r.fulfill({ json: { result: { market, mode: requestedMode, items: [item], total: 1 } } });
        if (u.pathname.startsWith("/api/formula-ranking/stock/")) {
          detailModes.push(requestedMode);
          return r.fulfill({ json: { result: { status: "ok", mode: requestedMode, item } } });
        }
        if (u.pathname.startsWith("/api/quote/")) return r.fulfill({ json: { ticker, market, name: ticker, price: 100 } });
        return r.fulfill({ json: { result: { status: "not_run", items: [] }, bars: [], data: [], news: [], documents: [], filings: [] } });
      });
      await page.goto("/stock-picker");
      if (market !== "CN") await page.getByRole("main").getByRole("button", { name: label, exact: true }).click();
      await page.getByRole("button", { name: mode === "conservative" ? "稳健" : "进攻", exact: true }).click();
      const link = page.getByRole("link", { name: "模式核验股票", exact: true });
      await expect(link).toHaveAttribute("href", `/stock/${ticker}?mode=${mode}`);
      await link.click();
      await expect(page.getByRole("button", { name: `评分模式：${mode === "conservative" ? "稳健" : "进取"}`, exact: true })).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByText("58.0 / 100", { exact: true })).toBeVisible();
      // React development remounts can abort/reissue the same request.
      // Every observed request must carry the selected mode, including aborted ones.
      expect([...new Set(detailModes)]).toEqual([mode]);
      await page.getByText(`止盈止损参考 · ${market === "CN" ? "CNY" : market === "HK" ? "HKD" : "USD"}`, { exact: true }).click();
      await expect(page.getByText("止损 90.00（距离 10.00%）", { exact: true })).toBeVisible();
      await page.reload();
      await expect(page.getByRole("button", { name: `评分模式：${mode === "conservative" ? "稳健" : "进取"}`, exact: true })).toHaveAttribute("aria-pressed", "true");
    });
  }
}

for (const [ticker, market, currency] of [["sh600519", "CN", "CNY"], ["hk00700", "HK", "HKD"], ["AAPL", "US", "USD"]]) {
  test(`${market} tiny analytical prices remain distinct and fund a consistent share scenario`, async ({ page }) => {
    await page.route("**/auth/profile", r => r.fulfill({ json: null }));
    await page.route("**/api/**", r => {
      const path = new URL(r.request().url()).pathname;
      if (path.startsWith("/api/formula-ranking/stock/")) return r.fulfill({ json: { result: { status: "ok", mode: "balanced", item: {
        ticker, market, formula_score: 60, recommendation: "观察", data_coverage: 1, weights: {}, contributions: {},
        risk_plan: { status: "ok", currency, reference_price: .005, stop_loss: .0046, take_profit_1: .0056, take_profit_2: .006,
          atr14: .0002, trailing_distance: .0004, support20: .0049, resistance20: .0051, position_cap_percent: 12.5, risk_budget_percent: 1, stop_distance_percent: 8 }
      } } } });
      if (path.startsWith("/api/quote/")) return r.fulfill({ json: { ticker, market, name: ticker, price: .005 } });
      return r.fulfill({ json: { bars: [], data: [], news: [], documents: [], filings: [] } });
    });
    await page.goto(`/stock/${ticker}`);
    await page.getByText(`止盈止损参考 · ${currency}`, { exact: true }).click();
    await expect(page.getByText("参考价 0.005 · ATR14 0.0002", { exact: true })).toBeVisible();
    await expect(page.getByText("止损 0.0046（距离 8.00%）", { exact: true })).toBeVisible();
    await expect(page.getByText("目标一 0.0056 · 目标二 0.006", { exact: true })).toBeVisible();
    await page.getByRole("spinbutton", { name: `组合资金（${currency}）`, exact: true }).fill("1000");
    await page.getByRole("checkbox", { name: "计算股数与费用情景", exact: true }).check();
    await page.getByRole("spinbutton", { name: "买入股数步长（股）", exact: true }).fill("1");
    // Binary subtraction puts 25,000 shares just above the exact risk budget;
    // the calculator conservatively rounds down rather than adding tolerance.
    await expect(page.getByText("情景股数上限 24,999 股", { exact: true })).toBeVisible();
    await expect(page.getByText(`买入资金含费用 125.00 ${currency}`, { exact: true })).toBeVisible();
    await expect(page.getByText(`止损价差加买卖费用 10.00 ${currency}`, { exact: true })).toBeVisible();
  });
}

for (const [ticker, market] of [["sh600519", "CN"], ["hk00700", "HK"], ["AAPL", "US"]]) {
  test(`${market} stock detail displays shared quant score and switches mode`, async ({ page }) => {
    await page.route("**/auth/profile", r => r.fulfill({ json: null }));
    await page.route("**/api/**", r => {
      const url = new URL(r.request().url());
      if (url.pathname.startsWith("/api/formula-ranking/stock/")) {
        const mode = url.searchParams.get("mode");
        return r.fulfill({ json: { result: { status: "ok", mode, source: "测试行情", quote_as_of: "2026-10-02", scope: "单只股票共享公式评估", item: {
          ticker, market, formula_version: "formula-v2", formula_score: mode === "conservative" ? 58 : 68, recommendation: "观察", data_coverage: .8,
          history_as_of: "2026-09-30", weights: { "5日动量": .2 }, contributions: { "5日动量": 15 }, components: { "风险惩罚": 2 }, missing_fields: ["volume_ratio"], risks: ["部分指标缺失"], risk_plan: { status: "ok", currency: market === "CN" ? "CNY" : market === "HK" ? "HKD" : "USD", reference_price: 100, stop_loss: 92, take_profit_1: 112, take_profit_2: 120, atr14: 4, support20: 98, resistance20: 102, position_cap_percent: 12.5, risk_budget_percent: 1, stop_distance_percent: 8, trailing_distance: 8 }
        } } } });
      }
      if (url.pathname.startsWith("/api/quote/")) return r.fulfill({ json: { ticker, market, name: ticker, price: 100, timestamp: "2026-10-02" } });
      return r.fulfill({ json: { bars: [], data: [], news: [], documents: [], filings: [] } });
    });
    await page.goto(`/stock/${ticker}`);
    await expect(page.getByRole("heading", { name: "量化评分", exact: true })).toBeVisible();
    await expect(page.getByText("68.0 / 100", { exact: true })).toBeVisible();
    await expect(page.getByText("加权因子完整度 80%", { exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "15.0 分", exact: true })).toBeVisible();
    await expect(page.getByText("缺失指标：量比", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "评分模式：稳健", exact: true }).click();
    await expect(page.getByText("58.0 / 100", { exact: true })).toBeVisible();
    await expect(page.getByText("68.0 / 100", { exact: true })).toHaveCount(0);
    const currency = market === "CN" ? "CNY" : market === "HK" ? "HKD" : "USD";
    await page.getByText(`止盈止损参考 · ${currency}`, { exact: true }).click();
    await expect(page.getByText("止损 92.00（距离 8.00%）", { exact: true })).toBeVisible();
    await page.getByRole("spinbutton", { name: `组合资金（${currency}）`, exact: true }).fill("1000");
    await expect(page.getByText(`参考持仓金额上限 125.00 ${currency}`, { exact: true })).toBeVisible();
    await page.getByRole("checkbox", { name: "计算股数与费用情景", exact: true }).check();
    await expect(page.getByText("请填入股数步长，未默认套用整手规则。", { exact: true })).toBeVisible();
    await page.getByRole("spinbutton", { name: "买入股数步长（股）", exact: true }).fill("1");
    await page.getByRole("spinbutton", { name: `每笔最低费用（${currency}）`, exact: true }).fill("5");
    await expect(page.getByText("当前资金、风险预算与费用不足以满足一个股数步长。", { exact: true })).toBeVisible();
    await page.getByRole("spinbutton", { name: `组合资金（${currency}）`, exact: true }).fill("100000");
    await page.getByRole("spinbutton", { name: "单边比例费用（%）", exact: true }).fill("0.15");
    await expect(page.getByText("情景股数上限 120 股", { exact: true })).toBeVisible();
    await expect(page.getByText(`止损价差加买卖费用 994.56 ${currency}`, { exact: true })).toBeVisible();
    await page.getByRole("checkbox", { name: "计算股数与费用情景", exact: true }).uncheck();
    await expect(page.getByText(/情景股数上限/)).toHaveCount(0);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole("heading", { name: "量化评分", exact: true })).toBeVisible();
  });
}


test("stock score failure and unsupported securities do not display invented scores", async ({ page }) => {
  await page.route("**/auth/profile", r => r.fulfill({ json: null }));
  let fail = true;
  await page.route("**/api/**", r => {
    const path = new URL(r.request().url()).pathname;
    if (path.startsWith("/api/formula-ranking/stock/")) {
      if (fail) { fail = false; return r.fulfill({ status: 503, json: { detail: "价格不可用" } }); }
      return r.fulfill({ json: { result: { status: "not_supported", message: "此证券不是已核验的普通股票" } } });
    }
    if (path.startsWith("/api/quote/")) return r.fulfill({ json: { ticker: "SPY", market: "US", price: 100 } });
    return r.fulfill({ json: { bars: [], data: [], news: [], documents: [], filings: [] } });
  });
  await page.goto("/stock/SPY");
  await expect(page.getByText("量化评分暂不可用，未填充默认分数。", { exact: true })).toBeVisible();
  await expect(page.getByText(/\/ 100/)).toHaveCount(0);
  await page.getByRole("button", { name: "重试评分", exact: true }).click();
  await expect(page.getByText("此证券不是已核验的普通股票", { exact: true })).toBeVisible();
  await expect(page.getByText(/\/ 100/)).toHaveCount(0);
});


for (const pe of [20, null]) {
  test(`detail metrics and score agree on financial valuation ${pe}`, async ({ page }) => {
    await page.route("**/auth/profile", r => r.fulfill({ json: null }));
    await page.route("**/api/**", r => {
      const path = new URL(r.request().url()).pathname;
      if (path.startsWith("/api/formula-ranking/stock/")) return r.fulfill({ json: { result: { status: "ok", mode: "balanced", financials_status: "available", valuation: { pe_ratio: pe, pb_ratio: 3, pe_basis: "TTM", pe_source: "Financial", pb_source: "PB provider" }, item: { ticker: "AAPL", market: "US", formula_score: 60, recommendation: "观察", pe_ratio: pe, pb_ratio: 3, contributions: {}, weights: {}, risk_plan: { status: "not_available" } } } } });
      if (path.startsWith("/api/quote/")) return r.fulfill({ json: { ticker: "AAPL", market: "US", price: 100, pe_ratio: 40, source: "Quote" } });
      if (path.startsWith("/api/financials/")) return r.fulfill({ json: { ticker: "AAPL", pe_ratio: pe, pb_ratio: 3, pe_basis: "TTM", pe_source: "Financial", pb_source: "PB provider" } });
      return r.fulfill({ json: { bars: [], data: [], news: [], filings: [], documents: [] } });
    });
    await page.goto("/stock/AAPL");
    await expect(page.getByText(`评分估值：PE ${pe === null ? "—" : "20.00"}（TTM） · PB 3.00`, { exact: false })).toBeVisible();
    await expect(page.getByText("市盈率 (PE · TTM)", { exact: true }).locator("..")).toContainText(pe === null ? "--" : "20.00");
    await expect(page.getByText("市净率 (PB)", { exact: true }).locator("..")).toContainText("3.00");
    await expect(page.getByText(/PE来源 Financial · PB来源 PB provider/)).toBeVisible();
  });
}

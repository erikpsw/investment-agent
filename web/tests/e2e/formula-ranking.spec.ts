import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test, expect } from "@playwright/test";
import { chooseSelect } from "./select-support";

for (const scenario of [
  { market: "CN", mode: "balanced", prefix: "cn-mode", reversal: true },
  { market: "HK", mode: "aggressive", prefix: "hk-mode", reversal: true },
  { market: "US", mode: "balanced", prefix: "us-mode", reversal: false },
  { market: "CN", mode: "balanced", prefix: "cn-reference-mode", reversal: true },
]) {
  test(`${scenario.prefix} ${scenario.mode} cost stress shows archived exposure and loss sensitivity`, async ({ page }) => {
    const report = JSON.parse(readFileSync(resolve(process.cwd(), `../storage/stock_picker/research/${scenario.prefix}-${scenario.mode}.json`), "utf8"));
    await page.route("**/auth/profile", r => r.fulfill({ json: null }));
    await page.route("**/api/formula-ranking?**", r => r.fulfill({ json: { result: { items: [], total: 0 } } }));
    await page.route("**/api/formula-ranking/backtest*", r => r.fulfill({ json: { result: report } }));
    await page.route("**/api/ai-screener/tuning", r => r.fulfill({ json: { result: { status: "not_run" } } }));
    await page.goto("/stock-picker");
    if (scenario.market !== "CN") await page.getByRole("main").getByRole("button", { name: scenario.market === "HK" ? "港股" : "美股", exact: true }).click();
    if (scenario.mode !== "balanced") await page.getByRole("button", { name: "进攻", exact: true }).click();
    const region = page.getByRole("region", { name: "交易成本压力测试", exact: true });
    await expect(region.getByRole("columnheader", { name: "平均股票仓位", exact: true })).toBeVisible();
    for (const stress of report.cost_stress) {
      const row = region.getByRole("row").filter({ has: page.getByRole("cell", { name: `${(stress.one_way_cost * 100).toFixed(2)}%`, exact: true }) });
      await expect(row.getByRole("cell", { name: `${(stress.net_return * 100).toFixed(2)}%`, exact: true })).toBeVisible();
      await expect(row.getByRole("cell", { name: `${(stress.average_exposure * 100).toFixed(1)}%`, exact: true })).toBeVisible();
      await expect(row.getByRole("cell", { name: "滚动调优止盈止损", exact: true })).toBeVisible();
      await expect(row.getByRole("cell", { name: "0 / 0", exact: true })).toHaveCount(2);
    }
    await expect(region.getByText("较高费用下，同一训练选定策略由正收益转为亏损，当前结果对交易成本敏感。", { exact: true })).toHaveCount(scenario.reversal ? 1 : 0);
  });
}

test("cost stress keeps cash, missing inputs and legacy unknown counts explicit", async ({ page }) => {
  const metric = { net_return: .1, max_drawdown: .02, sharpe_zero_rate: 1, days: 80, equity_curve: [] };
  await page.route("**/auth/profile", r => r.fulfill({ json: null }));
  await page.route("**/api/formula-ranking?**", r => r.fulfill({ json: { result: { items: [], total: 0 } } }));
  await page.route("**/api/ai-screener/tuning", r => r.fulfill({ json: { result: { status: "not_run" } } }));
  await page.route("**/api/formula-ranking/backtest*", r => r.fulfill({ json: { result: { status: "research_only", applied: false, cost_stress: [
    { ...metric, one_way_cost: .003, strategy: "risk_tuned", net_return: 0, average_exposure: 0, risk_unverifiable_days: 2, risk_missing_entries: 3, missing_quote_days: 1, stale_quote_days: 0 },
    { ...metric, one_way_cost: .005, strategy: "candidate" },
  ], out_of_sample: { baseline: metric, candidate: metric, benchmark: metric, risk_tuned: metric } } } }));
  await page.goto("/stock-picker");
  const region = page.getByRole("region", { name: "交易成本压力测试", exact: true });
  await expect(region.getByText("部分成本情景没有股票持仓，零收益不能视为策略有效。", { exact: true })).toBeVisible();
  await expect(region.getByText("部分成本情景存在报价或保护数据缺口，收益与回撤不能视为完整路径验证。", { exact: true })).toBeVisible();
  const legacy = region.getByRole("row").filter({ has: page.getByRole("cell", { name: "0.50%", exact: true }) });
  await expect(legacy.getByRole("cell", { name: "滚动调优", exact: true })).toBeVisible();
  await expect(legacy.getByRole("cell", { name: "— / —", exact: true })).toHaveCount(2);
});

test('completed-day volume research shows coverage and does not claim missing data are valid', async ({page}) => {
  await page.route('**/auth/profile',r=>r.fulfill({json:null}));
  await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  await page.route('**/api/formula-ranking?**',r=>r.fulfill({json:{result:{items:[],total:0,market:'HK',mode:'balanced'}}}));
  await page.route('**/api/formula-ranking/backtest*',r=>{
    const p=new URL(r.request().url()).searchParams;
    const us=p.get('market')==='US';
    return r.fulfill({json:{result:p.get('volume_reference')==='true' ? {status:'research_only',applied:false,volume_reference_coverage:{status:us?'available':'not_available',available:us?5:0,observations:10,status_counts:us?{share_scale_changed:5}:{unverified_share_scale:10},basis:'完成日成交量 / 前5日平均'}} : {status:'not_run',applied:false}}});
  });
  await page.goto('/stock-picker');
  await page.getByRole('main').getByRole('button',{name:'港股',exact:true}).click();
  await page.getByRole('checkbox',{name:'加入完成日量能研究',exact:true}).check();
  await expect(page.getByText('完成日量能覆盖：0.0%（0/10）',{exact:true})).toBeVisible();
  await expect(page.getByText(/调整比例未验证 10/)).toBeVisible();
  await expect(page.getByText(/此样本缺少可验证的完成日量能/)).toBeVisible();
  await page.getByRole('checkbox',{name:'加入完成日量能研究',exact:true}).uncheck();
  await expect(page.getByText(/完成日量能覆盖/)).toHaveCount(0);
  await page.getByRole('main').getByRole('button',{name:'美股',exact:true}).click();
  await page.getByRole('checkbox',{name:'加入完成日量能研究',exact:true}).check();
  await expect(page.getByText('完成日量能覆盖：50.0%（5/10）',{exact:true})).toBeVisible();
  await expect(page.getByText(/此样本缺少可验证的完成日量能/)).toHaveCount(0);
});

test("combined rankings retain snapshot warnings and allow separate market validation", async ({ page }) => {
  await page.route("**/auth/profile", route => route.fulfill({ json: null }));
  await page.route("**/api/ai-screener/tuning", route => route.fulfill({ json: { result: { status: "not_run", applied: false } } }));
  const backtestMarkets: string[] = [];
  await page.route("**/api/formula-ranking/backtest*", route => {
    backtestMarkets.push(new URL(route.request().url()).searchParams.get("market")!);
    return route.fulfill({ json: { result: { status: "not_run", applied: false } } });
  });
  await page.route("**/api/formula-ranking?**", route => route.fulfill({ json: { result: { items: [], total: 0, market: "all", mode: "balanced", formula: "test", snapshot_only: true, market_sources: [{ market: "HK", generated_at: "2026-09-29", source: "saved" }] } } }));
  await page.goto("/stock-picker");
  await page.getByRole("main").getByRole("button", { name: "全部", exact: true }).click();
  await expect(page.getByText("当前使用保存的市场快照，请核对数据时间；不代表实时价格。", { exact: true })).toBeVisible();
  await chooseSelect(page, "历史验证市场", "港股");
  await expect(page.getByText("HK 公式历史验证", { exact: true })).toBeVisible();
  await chooseSelect(page, "历史验证市场", "美股");
  await expect(page.getByText("US 公式历史验证", { exact: true })).toBeVisible();
  await expect.poll(() => backtestMarkets).toEqual(expect.arrayContaining(["CN", "HK", "US"]));
});

test("formula rankings show coverage, contributions, scope and rolling validation", async ({ page }) => {
  await page.route("**/auth/profile", route => route.fulfill({ json: null }));
  await page.route("**/api/ai-screener/tuning", route => route.fulfill({ json: { result: { status: "not_run", applied: false } } }));
  const metrics = { missing_quote_days: 10, stale_quote_days: 3, max_quote_age_calendar_days: 14, average_exposure: .5, net_return: .1, max_drawdown: .05, sharpe_zero_rate: 1, days: 80, equity_curve: [{ date: "2025-01-01", equity: 1 }, { date: "2025-02-01", equity: 1.1 }] };
  await page.route("**/api/formula-ranking/backtest*", route => route.fulfill({ json: { result: { status: "research_only", applied: false, formula_version: "formula-v2", available_count: 58, requested_count: 60, folds: [{ train_start: "2024-01-01", train_end: "2024-12-31", test_start: "2025-01-01", test_end: "2025-04-01", candidate_weights: { "5日动量": .2, "20日趋势": .25, "60日趋势": .15, "今日动量": .1, "量比": .1, "换手率": .08, "估值": .05, "市值质量": .07 }, weight_selection_status: "retained_default_due_to_quotes", risk_selection_status: "retained_default_due_to_quotes" }], cost_stress: [{ ...metrics, one_way_cost: .003, strategy: "risk_tuned" }], quality_failures: [{ ticker: "hk00148", reason: "invalid OHLC" }], out_of_sample: { baseline: metrics, candidate: metrics, benchmark: metrics, protected: { ...metrics, net_return: .02 }, risk_tuned: { ...metrics, net_return: .03 }, capped_control: { ...metrics, net_return: .04 } }, limitations: ["历史估值缺失"] } } }));
  await page.route("**/api/formula-ranking?**", route => {
    const query = new URL(route.request().url()).searchParams;
    const mode = query.get("mode"); const market = query.get("market") || "CN";
    return route.fulfill({ json: { result: { market, mode, formula_version: "formula-v2", formula: "均衡公式", scope: "主板候选池，非全市场最终排名", candidate_count: 120, total: 120, scanned_count: 3046, source: "测试快照", items: [{ ticker: market === "US" ? "AAPL" : market === "HK" ? "hk00700" : "sh600001", name: `${mode}候选`, formula_score: 70, recommendation: "观察", data_coverage: .8, history_as_of: "2026-09-28", contributions: { "5日动量": 15 }, weights: { "5日动量": .2 }, components: { "风险惩罚": 2 }, missing_fields: ["pe_ratio"], risks: ["部分指标缺失"], risk_plan: { status: "ok", currency: market === "US" ? "USD" : market === "HK" ? "HKD" : "CNY", reference_price: 100, stop_loss: 92, take_profit_1: 112, take_profit_2: 120, atr14: 4, support20: 98, resistance20: 102, stop_distance_percent: 8, position_cap_percent: 12.5, risk_budget_percent: 1, trailing_distance: 8, basis: [], limitations: ["跳空可能使实际损失超过预算"] } }] } } });
  });
  await page.goto("/stock-picker");
  await expect(page.getByText("因子完整度 80%", { exact: true })).toBeVisible();
  await page.getByText("止盈止损参考 · CNY", { exact: true }).click();
  await page.getByRole("spinbutton", { name: "组合资金（CNY）", exact: true }).fill("1000");
  await expect(page.getByText("参考持仓金额上限 125.00 CNY", { exact: true })).toBeVisible();
  await expect(page.getByText(/非全市场最终排名/)).toBeVisible();
  await page.getByText("评分依据", { exact: true }).click();
  await expect(page.getByText("5日动量：15.0分 · 权重 20%", { exact: true })).toBeVisible();
  await expect(page.getByText("日K截至 2026-09-28", { exact: true })).toBeVisible();
  await expect(page.getByRole("table").first().getByRole("cell", { name: "10.00%", exact: true })).toHaveCount(3);
  await expect(page.getByRole("table").first().getByRole("cell", { name: "滚动调优止盈止损", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "共享限仓规则对照", exact: true })).toBeVisible();
  await expect(page.getByText("交易成本压力测试（沿用训练选定参数）", { exact: true })).toBeVisible();
  await expect(page.getByRole("table").first().getByRole("columnheader", { name: "平均股票仓位", exact: true })).toBeVisible();
  await expect(page.getByRole("table").first().getByRole("columnheader", { name: "缺报价／陈旧报价日", exact: true })).toBeVisible();
  await expect(page.getByText("训练选参完整性：1 个窗口沿用默认权重，1 个窗口沿用默认保护参数。训练数据不足或没有实际买入的候选时，不声称选出了更优参数。", { exact: true })).toBeVisible();
  await expect(page.getByText("部分持仓缺少当日报价，净值沿用最后报价估算；回撤可能被低估，不能将这些结果视为完整可成交价格验证。", { exact: true })).toBeVisible();
  await expect(page.getByText("数据质量检查排除 1 只样本：hk00148。", { exact: true })).toBeVisible();
  await page.getByText("查看滚动窗口、权重和实验限制", { exact: true }).click();
  await expect(page.getByText(/因子权重：.*今日动量 10%.*量比 10%.*换手率 8%/)).toBeVisible();
  await expect(page.getByText(/NaN%/)).toHaveCount(0);
  await page.getByRole("button", { name: "稳健", exact: true }).click();
  await expect(page.getByRole("link", { name: "conservative候选", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "balanced候选", exact: true })).toHaveCount(0);
  await page.getByRole("main").getByRole("button", { name: "美股", exact: true }).click();
  await expect(page.getByText("US 公式历史验证", { exact: true })).toBeVisible();
  await page.getByText("止盈止损参考 · USD", { exact: true }).click();
  await expect(page.getByText("止损 92.00（距离 8.00%）", { exact: true })).toBeVisible();
  await page.getByRole("spinbutton", { name: "组合资金（USD）", exact: true }).fill("100000");
  await expect(page.getByText("参考持仓金额上限 12,500.00 USD", { exact: true })).toBeVisible();
  await expect(page.getByText("按止损价估算损失 1,000.00 USD", { exact: true })).toBeVisible();
  await page.getByRole("spinbutton", { name: "组合资金（USD）", exact: true }).fill("-1");
  await expect(page.getByText("请输入大于0的有限资金金额。", { exact: true })).toBeVisible();
  await expect(page.getByText("跳空可能使实际损失超过预算", { exact: true })).toBeVisible();
  await page.getByRole("main").getByRole("button", { name: "港股", exact: true }).click();
  await expect(page.getByText("HK 公式历史验证", { exact: true })).toBeVisible();
  await expect(page.getByText("止盈止损参考 · HKD", { exact: true })).toBeVisible();
  await page.getByText("止盈止损参考 · HKD", { exact: true }).click();
  await expect(page.getByRole("spinbutton", { name: "组合资金（HKD）", exact: true })).toHaveValue("");
  await page.getByRole("spinbutton", { name: "组合资金（HKD）", exact: true }).fill("10000");
  await expect(page.getByText("按止损价估算损失 100.00 HKD", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "公式与 AI 选股", exact: true })).toBeVisible();
});

test("catalog validation reports data shortage separately from snapshot research", async ({ page }) => {
  await page.route("**/auth/profile", route => route.fulfill({ json: null }));
  await page.route("**/api/ai-screener/tuning", route => route.fulfill({ json: { result: { status: "not_run", applied: false } } }));
  await page.route("**/api/formula-ranking?**", route => route.fulfill({ json: { result: { items: [], total: 0, mode: "balanced", market: "CN", formula: "均衡", source: "快照" } } }));
  await page.route("**/api/formula-ranking/backtest*", route => {
    const catalog = new URL(route.request().url()).searchParams.get("universe") === "catalog";
    return route.fulfill({ json: { result: catalog ? { status: "insufficient_data", applied: false, message: "证券目录抽样历史不足，不能生成验证结果", available_count: 4, requested_count: 60, quality_failures: [{ ticker: "BAD", reason: "OHLC" }], selection_method: "当前证券目录等距抽样" } : { status: "not_run", applied: false, message: "尚未运行候选样本" } } });
  });
  await page.goto("/stock-picker");
  await expect(page.getByText("尚未运行候选样本", { exact: true })).toBeVisible();
  await chooseSelect(page, "历史样本来源", "证券目录较广抽样");
  await expect(page.getByText("证券目录抽样历史不足，不能生成验证结果", { exact: true })).toBeVisible();
  await expect(page.getByText(/有效样本 4\/60；异常数据排除 1 只/)).toBeVisible();
  await chooseSelect(page, "历史样本来源", "行情候选样本");
  await expect(page.getByText("尚未运行候选样本", { exact: true })).toBeVisible();
});

test("US historical valuation toggle requests the SEC report and shows coverage", async ({ page }) => {
  await page.route("**/auth/profile", route => route.fulfill({ json: null }));
  await page.route("**/api/ai-screener/tuning", route => route.fulfill({ json: { result: { status: "not_run", applied: false } } }));
  await page.route("**/api/formula-ranking?**", route => route.fulfill({ json: { result: { items: [], total: 0, mode: "balanced", market: "US", formula: "均衡", source: "快照" } } }));
  await page.route("**/api/formula-ranking/backtest*", route => {
    const params = new URL(route.request().url()).searchParams;
    const sec = params.get("fundamentals") === "sec-pit";
    const volume = params.get("volume_reference") === "true";
    return route.fulfill({ json: { result: sec ? { status: "research_only", applied: false, message: "SEC估值研究", fundamental_mode: "sec-pit", ...(volume ? { volume_reference_coverage: { status: "available", available: 50, observations: 100, status_counts: { share_scale_changed: 50 }, basis: "完成日量能参考" } } : {}), available_count: 20, requested_count: 20, fundamental_coverage: { observations: 100, pe_observations: 60, pb_observations: 40, cap_observations: 70, missing_ledgers: ["ADR"], basis: "使用未复权股价估算，缺失不回填", availability: "提交日期次日可用" } } : { status: "not_run", applied: false, message: "仅价格因子研究" } } });
  });
  await page.goto("/stock-picker");
  await page.getByRole("main").getByRole("button", { name: "美股", exact: true }).click();
  await page.getByRole("checkbox", { name: "加入SEC披露日期估值", exact: true }).check();
  await expect(page.getByText("SEC估值研究", { exact: true })).toBeVisible();
  await expect(page.getByText("可评分历史日K覆盖：PE 60.0% / PB 40.0% / 市值 70.0%", { exact: true })).toBeVisible();
  await expect(page.getByText("使用未复权股价估算，缺失不回填", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "加入完成日量能研究", exact: true }).check();
  await expect(page.getByText("完成日量能覆盖：50.0%（50/100）", { exact: true })).toBeVisible();
  await expect(page.getByText("可评分历史日K覆盖：PE 60.0% / PB 40.0% / 市值 70.0%", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "加入完成日量能研究", exact: true }).uncheck();
  await expect(page.getByText(/完成日量能覆盖/)).toHaveCount(0);
  await page.getByRole("checkbox", { name: "加入SEC披露日期估值", exact: true }).uncheck();
  await expect(page.getByText("仅价格因子研究", { exact: true })).toBeVisible();
  await expect(page.getByText(/可评分历史日K覆盖/)).toHaveCount(0);
  await page.getByRole("main").getByRole("button", { name: "A股", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "加入SEC披露日期估值", exact: true })).toHaveCount(0);
});

test("CN alternate history keeps unverified vendor references explicit", async ({ page }) => {
  await page.route("**/auth/profile", route => route.fulfill({ json: null }));
  await page.route("**/api/ai-screener/tuning", route => route.fulfill({ json: { result: { status: "not_run", applied: false } } }));
  await page.route("**/api/formula-ranking?**", route => route.fulfill({ json: { result: { items: [], total: 0, mode: "balanced", market: "CN", formula: "均衡", source: "快照" } } }));
  await page.route("**/api/formula-ranking/backtest*", route => {
    const params = new URL(route.request().url()).searchParams;
    const message = params.get("history_source") !== "baostock" ? "原行情归档" : params.get("fundamentals") === "cn-reference" ? "接口参考研究，未应用参数" : "BaoStock价格研究";
    return route.fulfill({ json: { result: { status: "not_run", applied: false, message } } });
  });
  await page.goto("/stock-picker");
  await chooseSelect(page, "A股历史行情来源", "BaoStock 扩充历史");
  await expect(page.getByText("BaoStock价格研究", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "加入历史接口估值参考", exact: true }).check();
  await expect(page.getByText("接口参考研究，未应用参数", { exact: true })).toBeVisible();
  await expect(page.getByText("加入接口历史PE／PB／换手率参考（财务修订时间未验证）", { exact: true })).toBeVisible();
  await chooseSelect(page, "A股历史行情来源", "现有行情归档");
  await expect(page.getByText("原行情归档", { exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "加入历史接口估值参考", exact: true })).toHaveCount(0);
});


test("window weights distinguish volume references and tolerate legacy fields", async ({ page }) => {
  await page.route("**/auth/profile", r => r.fulfill({ json: null }));
  await page.route("**/api/ai-screener/tuning", r => r.fulfill({ json: { result: { status: "not_run", applied: false } } }));
  await page.route("**/api/formula-ranking?**", r => r.fulfill({ json: { result: { items: [], total: 0, market: "CN", mode: "balanced" } } }));
  const metrics = { net_return: 0, max_drawdown: 0, sharpe_zero_rate: 0, equity_curve: [] };
  await page.route("**/api/formula-ranking/backtest*", r => r.fulfill({ json: { result: {
    status: "research_only", applied: false,
    volume_reference_coverage: { available: 1, observations: 2, status_counts: {}, basis: "完成日成交量参考" },
    folds: [
      { train_start: "2024-01-01", train_end: "2024-12-31", test_start: "2025-01-01", test_end: "2025-04-01", candidate_weights: { "5日动量": .2, "量比": .1, "换手率": null } },
      { train_start: "2024-04-01", train_end: "2025-03-31", test_start: "2025-04-02", test_end: "2025-07-01", candidate_weights: { "5日动量": .2 } }
    ], out_of_sample: { baseline: metrics, candidate: metrics, benchmark: metrics }
  } } }));
  await page.goto("/stock-picker");
  await page.getByText("查看滚动窗口、权重和实验限制", { exact: true }).click();
  await expect(page.getByText(/因子权重：5日动量 20% \/ 完成日量能参考 10% \/ 换手率 未记录/)).toBeVisible();
  await expect(page.getByText(/NaN%|undefined%/)).toHaveCount(0);
});


test("volume weight tuning requests a separate report and clears hidden selection", async ({ page }) => {
  await page.route("**/auth/profile", r => r.fulfill({ json: null }));
  await page.route("**/api/ai-screener/tuning", r => r.fulfill({ json: { result: { status: "not_run", applied: false } } }));
  await page.route("**/api/formula-ranking?**", r => r.fulfill({ json: { result: { items: [], total: 0, market: "CN", mode: "balanced" } } }));
  const requests: URLSearchParams[] = [];
  await page.route("**/api/formula-ranking/backtest*", r => {
    const params = new URL(r.request().url()).searchParams;
    requests.push(params);
    const tuned = params.get("tune_volume_weight") === "true";
    if (tuned && params.get("history_source") === "baostock") return r.fulfill({ json: { result: {
      status: "research_only", applied: false, volume_weight_tuning: { enabled: true, weights: [0, .05, .1, .2], policy: "仅训练窗口选择；不自动应用" }
    } } });
    return r.fulfill({ json: { result: { status: tuned ? "not_run" : "research_only", applied: false,
      message: tuned ? "尚未归档该组合的量能权重调优报告" : "固定量能权重报告"
    } } });
  });
  await page.goto("/stock-picker");
  await expect(page.getByRole("checkbox", { name: "训练期调优量能权重", exact: true })).toHaveCount(0);
  await page.getByRole("checkbox", { name: "加入完成日量能研究", exact: true }).check();
  await page.getByRole("checkbox", { name: "训练期调优量能权重", exact: true }).check();
  await expect(page.getByText("尚未归档该组合的量能权重调优报告", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "加入完成日量能研究", exact: true }).uncheck();
  await expect(page.getByText("固定量能权重报告", { exact: true })).toBeVisible();
  await expect.poll(() => requests.at(-1)?.get("tune_volume_weight")).toBe("false");
  await page.getByRole("checkbox", { name: "加入完成日量能研究", exact: true }).check();
  await expect(page.getByRole("checkbox", { name: "训练期调优量能权重", exact: true })).not.toBeChecked();
  await chooseSelect(page, "A股历史行情来源", "BaoStock 扩充历史");
  await page.getByRole("checkbox", { name: "训练期调优量能权重", exact: true }).check();
  await expect(page.getByText("量能权重调优实验：0%／5%／10%／20%。仅训练窗口选择；不自动应用", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "训练期调优量能权重", exact: true }).uncheck();
  await expect(page.getByText(/量能权重调优实验：/)).toHaveCount(0);
});


test("HK paired archive renders actual volume and risk research without leaking source to US", async ({ page }) => {
  await page.route("**/auth/profile", r => r.fulfill({ json: null }));
  await page.route("**/api/ai-screener/tuning", r => r.fulfill({ json: { result: { status: "not_run", applied: false } } }));
  await page.route("**/api/formula-ranking?**", r => r.fulfill({ json: { result: { items: [], total: 0, market: "HK", mode: "balanced" } } }));
  const requests: URLSearchParams[] = [];
  await page.route("**/api/formula-ranking/backtest*", r => {
    const params = new URL(r.request().url()).searchParams; requests.push(params);
    if (params.get("history_source") !== "yahoo-hk") return r.fulfill({ json: { result: { status: "not_run", applied: false, message: "原行情归档" } } });
    const suffix = params.get("tune_volume_weight") === "true" ? "-volume-tuned" : params.get("volume_reference") === "true" ? "-volume" : "";
    const report = JSON.parse(readFileSync(resolve(process.cwd(), `../storage/stock_picker/formula-backtest-hk-yahoo-hk${suffix}.json`), "utf-8"));
    return r.fulfill({ json: { result: report } });
  });
  await page.goto("/stock-picker");
  await page.getByRole("main").getByRole("button", { name: "港股", exact: true }).click();
  await chooseSelect(page, "港股历史行情来源", "Yahoo 原价与复权价配对归档");
  await expect(page.getByText(/独立Yahoo归档，不能将与原归档的收益差异全部归因于量能/)).toBeVisible();
  await page.getByRole("checkbox", { name: "加入完成日量能研究", exact: true }).check();
  await expect(page.getByText("完成日量能覆盖：32.2%（2879/8949）", { exact: true })).toBeVisible();
  await expect(page.getByRole("table").first().getByRole("cell", { name: "滚动调优止盈止损", exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "训练期调优量能权重", exact: true }).check();
  await expect(page.getByText(/量能权重调优实验：0%／5%／10%／20%/)).toBeVisible();
  await expect(page.getByRole("cell", { name: "4.36%", exact: true })).toBeVisible();
  await page.getByRole("main").getByRole("button", { name: "美股", exact: true }).click();
  await expect(page.getByLabel("港股历史行情来源", { exact: true })).toHaveCount(0);
  await expect.poll(() => requests.at(-1)?.get("history_source")).toBe("default");
  await expect(page.getByText(/完成日量能覆盖/)).toHaveCount(0);
});


for (const scenario of [
  { market: "CN", button: "A股", file: "formula-backtest-baostock-volume-tuned-execution.json", capital: "100,000 CNY", lot: "买入按 100 股步长向下取整" },
  { market: "HK", button: "港股", file: "formula-backtest-hk-yahoo-hk-volume-tuned-execution.json", capital: "100,000 HKD", lot: "未加入整手门槛，允许小数股" },
  { market: "US", button: "美股", file: "formula-backtest-us-catalog-pit-volume-tuned-execution.json", capital: "10,000 USD", lot: "买入按 1 股步长向下取整" },
]) {
  test(`${scenario.market} execution scenario shows actual assumptions and clears old report`, async ({ page }) => {
    await page.route("**/auth/profile", r => r.fulfill({ json: null }));
    await page.route("**/api/ai-screener/tuning", r => r.fulfill({ json: { result: { status: "not_run", applied: false } } }));
    await page.route("**/api/formula-ranking?**", r => r.fulfill({ json: { result: { items: [], total: 0, market: scenario.market, mode: "balanced" } } }));
    const requests: URLSearchParams[] = [];
    await page.route("**/api/formula-ranking/backtest*", r => {
      const params = new URL(r.request().url()).searchParams; requests.push(params);
      if (params.get("execution_scenario") !== "true" || params.get("market") !== scenario.market) return r.fulfill({ json: { result: { status: "not_run", applied: false, message: "未开启资金情景" } } });
      const report = JSON.parse(readFileSync(resolve(process.cwd(), `../storage/stock_picker/${scenario.file}`), "utf-8"));
      return r.fulfill({ json: { result: report } });
    });
    await page.goto("/stock-picker");
    if (scenario.market !== "CN") await page.getByRole("main").getByRole("button", { name: scenario.button, exact: true }).click();
    await page.getByRole("checkbox", { name: "加入资金成交情景", exact: true }).check();
    await expect(page.getByText(new RegExp(`固定资金情景：${scenario.capital}`))).toBeVisible();
    await expect(page.getByText(new RegExp(scenario.lot))).toBeVisible();
    await expect(page.getByText("止损预算已计入买卖费用。", { exact: true })).toBeVisible();
    await expect.poll(() => requests.at(-1)?.get("execution_scenario")).toBe("true");
    await page.getByRole("checkbox", { name: "加入资金成交情景", exact: true }).uncheck();
    await expect(page.getByText(/固定资金情景：/)).toHaveCount(0);
    await expect.poll(() => requests.at(-1)?.get("execution_scenario")).toBe("false");
  });
}


test("HK lot references show zero coverage without inventing backtest gains", async ({ page }) => {
  await page.route("**/auth/profile", r => r.fulfill({ json: null }));
  await page.route("**/api/ai-screener/tuning", r => r.fulfill({ json: { result: { status: "not_run", applied: false } } }));
  await page.route("**/api/formula-ranking?**", r => r.fulfill({ json: { result: { items: [], total: 0, mode: "balanced", market: "HK" } } }));
  const requests: URLSearchParams[] = [];
  await page.route("**/api/formula-ranking/backtest*", r => {
    const params = new URL(r.request().url()).searchParams; requests.push(params);
    if (params.get("lot_reference") !== "true") return r.fulfill({ json: { result: { status: "not_run", applied: false, message: "普通资金情景" } } });
    const report = JSON.parse(readFileSync(resolve(process.cwd(), "../storage/stock_picker/formula-backtest-hk-yahoo-hk-volume-tuned-execution-lot-reference.json"), "utf-8"));
    return r.fulfill({ json: { result: report } });
  });
  await page.goto("/stock-picker");
  await page.getByRole("main").getByRole("button", { name: "港股", exact: true }).click();
  await page.getByRole("checkbox", { name: "加入资金成交情景", exact: true }).check();
  await page.getByRole("checkbox", { name: "加入公告每手参考", exact: true }).check();
  await expect(page.getByText(/公告每手参考覆盖 0\/8931 个证券报价日/)).toBeVisible();
  await expect(page.getByText(/冻结样本没有已披露且生效的每手参考记录/)).toBeVisible();
  await expect(page.getByRole("table").first().getByRole("cell", { name: "滚动调优止盈止损", exact: true })).toHaveCount(0);
  await expect(page.getByText(/未加入整手门槛，允许小数股/)).toHaveCount(0);
  await page.getByRole("main").getByRole("button", { name: "美股", exact: true }).click();
  await expect.poll(() => requests.at(-1)?.get("lot_reference")).toBe("false");
  await expect(page.getByRole("checkbox", { name: "加入公告每手参考", exact: true })).toHaveCount(0);
  await expect(page.getByText(/公告每手参考覆盖/)).toHaveCount(0);
  await page.getByRole("checkbox", { name: "加入资金成交情景", exact: true }).uncheck();
  await page.getByRole("main").getByRole("button", { name: "港股", exact: true }).click();
  await page.getByRole("checkbox", { name: "加入资金成交情景", exact: true }).check();
  await expect(page.getByRole("checkbox", { name: "加入公告每手参考", exact: true })).not.toBeChecked();
});


test('risk research shows its training data boundary and flags legacy reports', async ({page}) => {
  const report = JSON.parse(readFileSync(resolve(process.cwd(),'../storage/stock_picker/research/hk-risk-boundary-after.json'),'utf8'));
  const legacy = {...report};
  delete legacy.risk_availability_as_of;
  delete legacy.risk_availability_policy;
  await page.route('**/auth/profile',r=>r.fulfill({json:null}));
  await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  await page.route('**/api/formula-ranking?**',r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
  await page.route('**/api/formula-ranking/backtest*',r=>r.fulfill({json:{result:new URL(r.request().url()).searchParams.get('volume_reference')==='true'?report:legacy}}));
  await page.goto('/stock-picker');
  await expect(page.getByText('旧版风控回测未记录训练期数据边界，请以重新验证的报告为准。',{exact:true})).toBeVisible();
  await page.getByRole('checkbox',{name:'加入完成日量能研究',exact:true}).check();
  await expect(page.getByText(`风控数据检查截至 ${report.risk_availability_as_of}，在首次验证之前固定。`,{exact:true})).toBeVisible();
  await expect(page.getByText(/旧版风控回测未记录/)).toHaveCount(0);
});


test('risk data gaps distinguish unavailable plans from unknown held intraday triggers', async ({page}) => {
  const report=JSON.parse(readFileSync(resolve(process.cwd(),'../storage/stock_picker/research/hk-risk-observability-after.json'),'utf8'));
  report.out_of_sample.risk_tuned.risk_unverifiable_days=2;
  report.out_of_sample.risk_tuned.risk_missing_entries=3;
  report.out_of_sample.risk_tuned.risk_evaluation_status='incomplete_intraday_data';
  await page.route('**/auth/profile',r=>r.fulfill({json:null}));
  await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  await page.route('**/api/formula-ranking?**',r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
  await page.route('**/api/formula-ranking/backtest*',r=>r.fulfill({json:{result:report}}));
  await page.goto('/stock-picker');
  const row=page.getByRole('row').filter({has:page.getByRole('cell',{name:'滚动调优止盈止损',exact:true})});
  await expect(row.getByRole('cell',{name:'2 / 3',exact:true})).toBeVisible();
  await expect(page.getByText(/存在无法核验的保护判断或入场计划/)).toBeVisible();
  await expect(page.getByRole('table').first().getByRole('columnheader',{name:'保护判断缺失日／入场计划缺失次',exact:true})).toBeVisible();
  await expect(page.getByText(/无法更新次日移动保护的日期/)).toBeVisible();
  await expect(page.getByText('此报告尚未复核A股当日不可卖出期间的次日移动保护更新，请以重建版本为准。',{exact:true})).toBeVisible();
});


test('prospective protocol stays separate from retrospective backtest in all markets',async({page})=>{
  await page.route('**/auth/profile',r=>r.fulfill({json:null}));
  await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  await page.route('**/api/formula-ranking?**',r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
  await page.route('**/api/formula-ranking/backtest*',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  await page.route('**/api/formula-ranking/holdout*',r=>{
    const market=new URL(r.request().url()).searchParams.get('market')!;
    const protocol=JSON.parse(readFileSync(resolve(process.cwd(),`../storage/stock_picker/holdout/protocol-${market.toLowerCase()}.json`),'utf8'));
    return r.fulfill({json:{result:{...protocol,status:'awaiting_evaluation',engine_storage:'archived',requested_count:protocol.requested_universe.length,training_available_count:protocol.training_available_universe.length}}});
  });
  await page.goto('/stock-picker');
  for(const [market,label,count] of [['CN','A股',60],['US','美股',60],['HK','港股',20]]){
    if(market!=='CN')await page.getByRole('main').getByRole('button',{name:label as string,exact:true}).click();
    await expect(page.getByText(`固定请求样本 ${count} 只；未来评估不得更换或缩小样本。`,{exact:true})).toBeVisible();
    await expect(page.getByText('截止日期 2026-10-03；仅评估之后的首个 80 交易日。',{exact:true})).toBeVisible();
    await expect(page.getByText('参数已冻结，未来验证尚未完成。',{exact:true})).toBeVisible();
    await expect(page.getByText('后续验证使用已归档的冻结版本，不随当前选股迭代改变。',{exact:true})).toBeVisible();
  }
});

test('rebuilt trailing protection report displays corrected CN result without the legacy warning', async ({page}) => {
  const report=JSON.parse(readFileSync(resolve(process.cwd(),'../storage/stock_picker/research/cn-trailing-update-after.json'),'utf8'));
  await page.route('**/auth/profile',r=>r.fulfill({json:null}));
  await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  await page.route('**/api/formula-ranking?**',r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
  await page.route('**/api/formula-ranking/backtest*',r=>r.fulfill({json:{result:report}}));
  await page.goto('/stock-picker');
  const row=page.getByRole('row').filter({has:page.getByRole('cell',{name:'滚动调优止盈止损',exact:true})});
  await expect(row.getByRole('cell',{name:'2.01%',exact:true})).toBeVisible();
  await expect(page.getByText('此报告尚未复核A股当日不可卖出期间的次日移动保护更新，请以重建版本为准。',{exact:true})).toHaveCount(0);
  await expect(page.getByText(/收盘后已知高价仍用于更新次日保护/)).toBeVisible();
});

for (const market of ['CN','HK','US']) {
  test(`${market} ranking mode loads its own archived weights and protection budget`, async ({page}) => {
    const requests: string[]=[];
    await page.route('**/auth/profile',r=>r.fulfill({json:null}));
    await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
    await page.route('**/api/formula-ranking?**',r=>r.fulfill({json:{result:{items:[],total:0,market,mode:new URL(r.request().url()).searchParams.get('mode')}}}));
    await page.route('**/api/formula-ranking/backtest*',async r=>{
      const query=new URL(r.request().url()).searchParams;
      const mode=query.get('mode')||'balanced';
      const report=JSON.parse(readFileSync(resolve(process.cwd(),`../storage/stock_picker/research/${query.get('market')!.toLowerCase()}-mode-${mode}.json`),'utf8'));
      requests.push(mode);
      if(mode==='conservative') await new Promise(resolve=>setTimeout(resolve,500));
      return r.fulfill({json:{result:report}});
    });
    await page.goto('/stock-picker');
    if (market!=='CN') await page.getByRole('main').getByRole('button',{name:market==='HK'?'港股':'美股',exact:true}).click();
    await expect(page.getByText('实时评分模式：均衡。历史报告按相同模式独立加载。',{exact:true})).toBeVisible();
    await expect(page.getByText(/研究原权重：5日动量 20%/)).toBeVisible();
    await page.getByRole('button',{name:'稳健',exact:true}).click();
    await expect(page.getByText(/研究原权重：5日动量 20%/)).toHaveCount(0);
    await expect(page.getByText('实时评分模式：稳健。历史报告按相同模式独立加载。',{exact:true})).toBeVisible();
    await expect(page.getByText(/研究原权重：5日动量 10%/)).toBeVisible();
    await expect(page.getByText('模式保护预算：组合风险 0.5% · 单股上限 10% · 默认 2.5 × ATR。',{exact:true})).toBeVisible();
    expect(requests).toContain('conservative');
    if(market!=='US') await expect(page.getByText(/验证窗口平均股票仓位为0/)).toBeVisible();
    await page.getByRole('button',{name:'进攻',exact:true}).click();
    await expect(page.getByText(/研究原权重：5日动量 25%/)).toBeVisible();
    await expect(page.getByText('模式保护预算：组合风险 1% · 单股上限 20% · 默认 1.5 × ATR。',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'均衡',exact:true}).click();
    await expect(page.getByText(/研究原权重：5日动量 20%/)).toBeVisible();
    await expect(page.getByText(/当前模式的未来留出协议尚未创建/)).toHaveCount(0);
  });
}

test('default protection counts include unavailable training plans as well as missing quotes',async({page})=>{
  const report=JSON.parse(readFileSync(resolve(process.cwd(),'../storage/stock_picker/research/cn-trailing-update-after.json'),'utf8'));
  report.folds=report.folds.slice(0,2);
  report.folds[0].risk_selection_status='retained_default_due_to_quotes';
  report.folds[1].risk_selection_status='retained_default_due_to_risk_inputs';
  await page.route('**/auth/profile',r=>r.fulfill({json:null}));
  await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  await page.route('**/api/formula-ranking?**',r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
  await page.route('**/api/formula-ranking/backtest*',r=>r.fulfill({json:{result:report}}));
  await page.goto('/stock-picker');
  await expect(page.getByText('训练选参完整性：0 个窗口沿用默认权重，2 个窗口沿用默认保护参数。训练数据不足或没有实际买入的候选时，不声称选出了更优参数。',{exact:true})).toBeVisible();
});

for (const mode of ['balanced','conservative','aggressive']) {
  test(`CN ${mode} reference experiment has actual positions and remains distinct from price research`,async({page})=>{
    await page.route('**/auth/profile',r=>r.fulfill({json:null}));
    await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
    await page.route('**/api/formula-ranking?**',r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode}}}));
    await page.route('**/api/formula-ranking/backtest*',r=>{
      const p=new URL(r.request().url()).searchParams;
      const m=p.get('mode')||'balanced';
      if(p.get('history_source')!=='baostock'||p.get('volume_reference')!=='true'||p.get('tune_volume_weight')!=='true'||p.get('execution_scenario')!=='true') return r.fulfill({json:{result:{status:'not_run',applied:false}}});
      const kind=p.get('fundamentals')==='cn-reference'?'cn-reference-mode':'cn-mode';
      const report=JSON.parse(readFileSync(resolve(process.cwd(),`../storage/stock_picker/research/${kind}-${m}.json`),'utf8'));
      return r.fulfill({json:{result:report}});
    });
    await page.goto('/stock-picker');
    if(mode!=='balanced') await page.getByRole('button',{name:mode==='conservative'?'稳健':'进攻',exact:true}).click();
    await chooseSelect(page, 'A股历史行情来源', 'BaoStock 扩充历史');
    await page.getByRole('checkbox',{name:'加入完成日量能研究',exact:true}).check();
    await page.getByRole('checkbox',{name:'训练期调优量能权重',exact:true}).check();
    await page.getByRole('checkbox',{name:'加入资金成交情景',exact:true}).check();
    if(mode==='conservative') await expect(page.getByText(/验证窗口平均股票仓位为0/)).toBeVisible();
    await page.getByRole('checkbox',{name:'加入历史接口估值参考',exact:true}).check();
    const row=page.getByRole('row').filter({has:page.getByRole('cell',{name:'滚动调优止盈止损',exact:true})});
    await expect(row.getByRole('cell',{name:mode==='balanced'?'3.71%':mode==='conservative'?'0.43%':'4.97%',exact:true})).toBeVisible();
    await expect(page.getByText('接口历史估值参考研究：财务修订时间未验证，结果不能用于证明严格时点策略有效。',{exact:true})).toBeVisible();
    await expect(page.getByText(/验证窗口平均股票仓位为0/)).toHaveCount(0);
    await page.getByRole('checkbox',{name:'加入历史接口估值参考',exact:true}).uncheck();
    await expect(page.getByText(/接口历史估值参考研究：/)).toHaveCount(0);
    if(mode==='conservative') await expect(page.getByText(/验证窗口平均股票仓位为0/)).toBeVisible();
  });
}

for (const market of ['CN','HK','US']) {
  test(`${market} completed experiment shortcut selects the archived source and execution combination`,async({page})=>{
    await page.route('**/auth/profile',r=>r.fulfill({json:null}));
    await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
    await page.route('**/api/formula-ranking?**',r=>r.fulfill({json:{result:{items:[],total:0,market,mode:'balanced'}}}));
    const requests: URLSearchParams[]=[];
    await page.route('**/api/formula-ranking/backtest*',r=>{
      const p=new URL(r.request().url()).searchParams; requests.push(p);
      if(p.get('volume_reference')!=='true'||p.get('tune_volume_weight')!=='true'||p.get('execution_scenario')!=='true') return r.fulfill({json:{result:{status:'not_run',applied:false}}});
      const prefix=p.get('fundamentals')==='cn-reference'?'cn-reference-mode':`${p.get('market')!.toLowerCase()}-mode`;
      const report=JSON.parse(readFileSync(resolve(process.cwd(),`../storage/stock_picker/research/${prefix}-${p.get('mode')}.json`),'utf8'));
      return r.fulfill({json:{result:report}});
    });
    await page.goto('/stock-picker');
    if(market!=='CN') await page.getByRole('main').getByRole('button',{name:market==='HK'?'港股':'美股',exact:true}).click();
    await page.getByRole('button',{name:'加载已完成基础实验',exact:true}).click();
    await expect(page.getByText(/研究原权重：5日动量 20%/)).toBeVisible();
    const p=requests.at(-1)!;
    expect(p.get('market')).toBe(market);
    expect(p.get('history_source')).toBe(market==='CN'?'baostock':market==='HK'?'yahoo-hk':'default');
    expect(p.get('universe')).toBe(market==='US'?'catalog':'snapshot');
    expect(p.get('fundamentals')).toBe(market==='US'?'sec-pit':'price');
    expect(p.get('lot_reference')).toBe('false');
    await expect(page.getByRole('checkbox',{name:'加入资金成交情景',exact:true})).toBeChecked();
    if(market==='CN'){
      await page.getByRole('button',{name:'加载已完成估值参考实验',exact:true}).click();
      await expect(page.getByText('接口历史估值参考研究：财务修订时间未验证，结果不能用于证明严格时点策略有效。',{exact:true})).toBeVisible();
      expect(requests.at(-1)!.get('fundamentals')).toBe('cn-reference');
      await page.getByRole('button',{name:'加载已完成基础实验',exact:true}).click();
      await expect(page.getByText(/接口历史估值参考研究：/)).toHaveCount(0);
    }
  });
}

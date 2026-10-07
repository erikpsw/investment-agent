import { test, expect, type Route } from "@playwright/test";
import { chooseSelect, MARKET_OPTION_LABELS } from "./select-support";

const screenReply = (route: Route, payload: Parameters<Route["fulfill"]>[0]) => route.fulfill({ ...payload, json: {job: {id: route.request().postDataJSON().submission_id, status: "completed", response: payload?.json}} });

test('foreign natural-language screening carries market and native currency', async ({page}) => {
  await page.route('**/auth/profile',r=>r.fulfill({json:null}));
  await page.route('**/api/ai-screener/tuning',r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  await page.route('**/api/formula-ranking**',r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
  await page.route('**/api/ai-screener/jobs',r=>{
    const request=r.request().postDataJSON();
    expect(request.market).toBe('HK');
    return screenReply(r,{json:{result:{market:'HK',currency:'HKD',plan:{summary:'港股条件',filters:[{field:'market_cap',op:'gte',value:10000000000}],unsupported:[]},items:[],matched_count:0,scanned_count:87,filter_coverage:{market_cap:{available:0,total:87}},scope:'港股股票候选快照'}}});
  });
  await page.goto('/stock-picker');
  await chooseSelect(page, '条件选股市场', '港股 · HKD');
  await page.getByRole('button',{name:'低估值大盘',exact:true}).click();
  await expect(page.getByText('总市值（HKD） ≥ 10,000,000,000',{exact:true})).toBeVisible();
  await expect(page.getByText('条件指标覆盖：总市值（HKD） 0/87。缺失指标不参与匹配。',{exact:true})).toBeVisible();
  await expect(page.getByText(/当前候选快照缺少部分条件指标/)).toBeVisible();
});

test("screening explains conditions, links to research and handles unsupported requirements", async ({ page }) => {
  await page.route("**/auth/profile", route => route.fulfill({ json: null }));
  await page.route("**/api/formula-ranking?**", route => route.fulfill({ json: { result: { market: "CN", mode: "balanced", items: [], formula: "测试公式", total: 0, source: "测试" } } }));
  await page.route("**/api/ai-screener/tuning", route => route.fulfill({ json: { result: { status: "not_run", applied: false, message: "尚未运行历史验证" } } }));
  await page.route("**/api/ai-screener/jobs", route => {
    const request = route.request().postDataJSON();
    return screenReply(route,{ json: request.preset ? { status: "ok", result: { market: "CN", plan: { mode: "conservative", summary: "低估值", filters: [{ field: "pe_ratio", op: "lte", value: 20 }], unsupported: [] }, scanned_count: 3000, matched_count: 1, source: "测试行情", generated_at: "2026-10-01", items: [{ ticker: "sh600519", market: "CN", name: "贵州茅台", recommendation: "观察", formula_score: 70, match_reasons: ["市盈率 18 ≤ 20"], risks: [] }] } } : { status: "needs_revision", result: { plan: { summary: "高ROE", filters: [], unsupported: ["ROE数据不可用"] }, items: [], message: "请修改条件" } } });
  });
  await page.goto("/stock-picker");
  await page.getByRole("button", { name: "低估值大盘", exact: true }).click();
  await expect(page.getByText("符合全部条件 1 只", { exact: false })).toBeVisible();
  await expect(page.getByText("市盈率 18 ≤ 20", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /贵州茅台/ })).toHaveAttribute("href", "/stock/sh600519?mode=conservative");
  await page.getByLabel("你想找什么样的股票？").fill("ROE大于20%");
  await page.getByRole("button", { name: "AI 筛选", exact: true }).click();
  await expect(page.getByText(/未执行筛选：ROE数据不可用/)).toBeVisible();
  await expect(page.getByRole("link", { name: /贵州茅台/ })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel("你想找什么样的股票？")).toBeVisible();
});

for (const [market, currency, ticker] of [['CN','CNY','sh600519'],['HK','HKD','hk00700'],['US','USD','AAPL']]) {
  test(`historical screening exposes coverage and protective prices in ${market}`, async ({page}) => {
    await page.route('**/auth/profile', r=>r.fulfill({json:null}));
    await page.route('**/api/ai-screener/tuning', r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
    await page.route('**/api/formula-ranking**', r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
    await page.route('**/api/ai-screener/jobs', r=>screenReply(r,{json:{result:{market,currency,plan:{mode:'balanced',summary:'历史条件',filters:[{field:'change_20d',op:'gt',value:0}],unsupported:[]},items:[{ticker,market,name:'历史候选',recommendation:'观察',formula_score:70,match_reasons:['20日涨幅 8 > 0'],risks:[],risk_plan:{status:'ok',currency,reference_price:100,atr14:4,trailing_distance:8,stop_loss:92,take_profit_1:112,take_profit_2:120,history_as_of:'2026-09-25',position_cap_percent:20,stop_distance_percent:8,risk_budget_percent:1}}],scanned_count:125,matched_count:2,history_requested_count:125,history_enriched_count:124,history_failed_count:1,risk_plan_available_count:2}}}));
    await page.goto('/stock-picker');
    await chooseSelect(page, '条件选股市场', MARKET_OPTION_LABELS[market as keyof typeof MARKET_OPTION_LABELS]);
    await page.getByLabel('你想找什么样的股票？').fill('20日涨幅大于0%');
    await page.getByRole('button',{name:'AI 筛选',exact:true}).click();
    await expect(page.getByText('20日涨幅（%） > 0',{exact:true})).toBeVisible();
    await expect(page.getByText(/历史因子完整覆盖 124\/125 只/)).toBeVisible();
    await page.getByText(`止盈止损参考 · ${currency}`,{exact:true}).click();
    await expect(page.getByText('止损 92.00（距离 8.00%）',{exact:true})).toBeVisible();
    await expect(page.getByRole('link',{name:/历史候选/})).toHaveAttribute('href',`/stock/${ticker}?mode=balanced`);
  });
}


test('long-running screening resumes after reload and waiting can be stopped', async ({page}) => {
  await page.route('**/auth/profile', r=>r.fulfill({json:null}));
  await page.route('**/api/formula-ranking**', r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
  await page.route('**/api/ai-screener/tuning', r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  let submits = 0;
  let completed = false;
  let id = '';
  const request = {market:'US',query:'20日涨幅大于0%'};
  await page.route('**/api/ai-screener/jobs', r=>{submits++; id=r.request().postDataJSON().submission_id; return r.fulfill({status:202,json:{job:{id,status:'running',request}}});});
  await page.route('**/api/ai-screener/jobs/*', r=>r.fulfill({json:{job:{id,status:completed?'completed':'running',request,response:completed?{result:{plan:{summary:'任务完成',filters:[],unsupported:[]},items:[],scanned_count:99,matched_count:0}}:null}}}));
  await page.goto('/stock-picker');
  await chooseSelect(page, '条件选股市场', '美股 · USD');
  await page.getByLabel('你想找什么样的股票？').fill(request.query);
  await page.getByRole('button',{name:'AI 筛选',exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>sessionStorage.getItem('ai-screen-active-job'))).toBe(id);
  await page.reload();
  await expect(page.getByRole('button',{name:'停止等待',exact:true})).toBeVisible();
  await expect(page.getByLabel('你想找什么样的股票？')).toHaveValue(request.query);
  completed = true;
  await expect(page.getByText('任务完成',{exact:true})).toBeVisible();
  expect(submits).toBe(1);
  completed = false;
  await page.getByRole('button',{name:'AI 筛选',exact:true}).click();
  await expect(page.getByRole('button',{name:'停止等待',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'停止等待',exact:true}).click();
  await expect(page.getByText(/已停止页面等待/)).toBeVisible();
  await expect(page.getByLabel('你想找什么样的股票？')).toBeEnabled();
  expect(await page.evaluate(()=>sessionStorage.getItem('ai-screen-active-job'))).toBeNull();
});


test('a lost submission response is recovered without submitting twice', async ({page}) => {
  await page.route('**/auth/profile', r=>r.fulfill({json:null}));
  await page.route('**/api/formula-ranking**', r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
  await page.route('**/api/ai-screener/tuning', r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  let submissions = 0;
  let id = '';
  await page.route('**/api/ai-screener/jobs', r=>{submissions++; id=r.request().postDataJSON().submission_id; return r.abort('failed');});
  await page.route('**/api/ai-screener/jobs/*', r=>r.fulfill({json:{job:{id,status:'completed',request:{market:'CN',query:'PE小于20'},response:{result:{plan:{summary:'已恢复结果',filters:[],unsupported:[]},items:[]}}}}}));
  await page.goto('/stock-picker');
  await page.getByLabel('你想找什么样的股票？').fill('PE小于20');
  await page.getByRole('button',{name:'AI 筛选',exact:true}).click();
  await expect.poll(()=>submissions).toBe(1);
  await expect(page.getByRole('button',{name:'AI 筛选',exact:true})).toBeEnabled();
  expect(await page.evaluate(()=>sessionStorage.getItem('ai-screen-active-job'))).toBe(id);
  await page.reload();
  await expect(page.getByText('已恢复结果',{exact:true})).toBeVisible();
  expect(submissions).toBe(1);
});

test('interrupted and busy jobs show actionable errors without partial rankings', async ({page}) => {
  await page.route('**/auth/profile', r=>r.fulfill({json:null}));
  await page.route('**/api/formula-ranking**', r=>r.fulfill({json:{result:{items:[],total:0,market:'CN',mode:'balanced'}}}));
  await page.route('**/api/ai-screener/tuning', r=>r.fulfill({json:{result:{status:'not_run',applied:false}}}));
  let busy = false;
  await page.route('**/api/ai-screener/jobs', r=>r.fulfill(busy?{status:429,json:{detail:'筛选任务繁忙，请稍后重试。'}}:{status:202,json:{job:{id:r.request().postDataJSON().submission_id,status:'interrupted',message:'筛选服务已中断，请重新提交；没有生成完整结果。'}}}));
  await page.goto('/stock-picker');
  await page.getByLabel('你想找什么样的股票？').fill('PE小于20');
  await page.getByRole('button',{name:'AI 筛选',exact:true}).click();
  await expect(page.getByText(/筛选服务已中断/)).toBeVisible();
  expect(await page.evaluate(()=>sessionStorage.getItem('ai-screen-active-job'))).toBeNull();
  busy=true;
  await page.getByRole('button',{name:'AI 筛选',exact:true}).click();
  await expect(page.getByText('筛选任务繁忙，请稍后重试。',{exact:true})).toBeVisible();
  await expect(page.getByLabel('你想找什么样的股票？')).toBeEnabled();
});

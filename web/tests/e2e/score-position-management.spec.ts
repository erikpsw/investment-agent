import {test,expect} from '@playwright/test';

const stamp=new Date().toISOString();
const snapshot={id:'00000000-0000-0000-0000-000000000001',market:'US',ticker:'AAPL',mode:'balanced',formula_version:'v2',config_fingerprint:'a',formula_score:75,price:100,data_coverage:1,quote_as_of:stamp,quality_status:'ok'};
const entry={...snapshot,formula_score:65};
const candidate={status:'candidate',snapshot_id:snapshot.id,config_fingerprint:'a',quote_as_of:stamp,currency:'USD',price_basis:'raw',reference_price:100,stop_loss:95,take_profit_1:110,take_profit_2:115};
const management={episode_id:'00000000-0000-0000-0000-000000000002',entry_snapshot:entry,protection:null};

test.beforeEach(async({page})=>{
  await page.route('**/auth/profile',r=>r.fulfill({json:{sub:'test|score',name:'Test'}}));
  await page.route('**/auth/access-token*',r=>r.fulfill({json:{token:'test'}}));
  await page.route('**/api/portfolio/tokens',r=>r.fulfill({json:{result:{tokens:[]}}}));
  await page.route('**/api/securities/**/score-history?*',r=>r.fulfill({json:{result:{items:[snapshot,{...entry,id:'old',quote_as_of:new Date(Date.now()-86400000).toISOString()}],next_cursor:null}}}));
});

test('watchlist detects scores and opens observed history on mobile',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.route('**/api/watchlists**',r=>r.fulfill({json:{result:{groups:[{id:'us',name:'美股',items:[{ticker:'AAPL',market:'US',name:'Apple'}],children:[]}]}}}));
  await page.route('**/api/watchlists/detection',r=>{
    const body=r.request().postDataJSON();expect(body.securities).toEqual([{market:'US',ticker:'AAPL'}]);
    return r.fulfill({json:{result:{items:[{market:'US',ticker:'AAPL',status:'ok',saved:true,inserted:true,snapshot,change:{previous_delta:5,entry_delta:null,quality_changed:false,reasons:[{factor:'趋势',delta:5}]}}],mode:'balanced'}}});
  });
  await page.goto('/watchlist');
  await page.getByRole('button',{name:'检测评分',exact:true}).click();
  await expect(page.getByText('75.00分')).toBeVisible();
  await expect(page.getByText(/较上次 \+5.00/)).toBeVisible();
  await page.getByText('评分历史与变化趋势',{exact:true}).click();
  await expect(page.getByRole('img',{name:/AAPL已保存评分曲线/})).toBeVisible();
  await page.getByRole('button',{name:'最近90交易观察日'}).click();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'test-results/score-watchlist-mobile.png',fullPage:true});
});

test('portfolio confirms protection explicitly and sends idempotent accounting metadata',async({page})=>{
  const positions=[{ticker:'AAPL',market:'US',currency:'USD',name:'Apple',quantity:10,avg_cost:80,current_price:100,market_value:7000,pnl:1400,pnl_percent:25}];
  await page.route('**/api/portfolio/positions?*',r=>r.fulfill({json:{result:{positions,revision:2,storage:'test'}}}));
  const overview={items:[{key:'US:AAPL',market:'US',ticker:'AAPL',currency:'USD',quantity:10,price:100,planned_risk_native:null,additional_quantity:null,quantity_reason:'止损尚未确认',current_weight_percent:20,position_cap_percent:20,management,detection:{...snapshot,change:{entry_delta:10,previous_delta:null}},protection_candidate:candidate,signal:{status:'observe',reason:'继续观察'}}],revision:2,account_value_base:35000,planned_risk_base:null,remaining_risk_base:null,unknown_risk_count:1,cash:{USD:1000},settings:{mode:'balanced',risk_budget_percent:1,position_cap_percent:20,total_risk_percent:5,one_way_cost:.0015},limitations:['计划风险不是保证最大亏损']};
  await page.route('**/api/portfolio/risk-overview',r=>r.fulfill({json:{result:overview}}));
  let confirms=0;
  await page.route('**/api/portfolio/positions/US/AAPL/protection',r=>{const body=r.request().postDataJSON();expect(body.expected_revision).toBe(2);expect(body.plan.stop_loss).toBe(95);confirms++;return r.fulfill({json:{result:{}}});});
  await page.route('**/api/portfolio/transactions',r=>{const body=r.request().postDataJSON();expect(body.request_id).toMatch(/^[0-9a-f-]{36}$/);expect(body.expected_revision).toBe(2);expect(body.executed_at).toBeTruthy();return r.fulfill({json:{result:{revision:3}}});});
  await page.goto('/portfolio');
  await expect(page.getByText('本轮买入评分',{exact:true})).toBeVisible();
  expect(confirms).toBe(0);
  await page.getByRole('button',{name:'确认候选保护计划',exact:true}).click();
  await expect.poll(()=>confirms).toBe(1);
  await page.getByText('买卖与现金记账',{exact:true}).click();
  await page.getByLabel('记账证券代码',{exact:true}).fill('AAPL');
  await page.getByLabel('记账数量',{exact:true}).fill('1');
  await page.getByLabel('记账成交价',{exact:true}).fill('100');
  await page.getByRole('button',{name:'确认记账',exact:true}).click();
  await expect(page.getByText('操作已保存，持仓和管理数据已重新读取')).toBeVisible();
  await page.screenshot({path:'test-results/score-portfolio.png',fullPage:true});
});


test('mode change cancels old detection and does not remain busy',async({page})=>{
  await page.route('**/api/watchlists**',r=>r.fulfill({json:{result:{groups:[{id:'us',name:'美股',items:[{market:'US',ticker:'AAPL'}],children:[]}]}}}));
  let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  let first=true;
  await page.route('**/api/watchlists/detection',async r=>{
    if(first){first=false;await gate;await r.fulfill({json:{result:{items:[{market:'US',ticker:'AAPL',status:'ok',snapshot:{...snapshot,formula_score:99}}]}}}).catch(()=>{});}
    else await r.fulfill({json:{result:{items:[{market:'US',ticker:'AAPL',status:'ok',snapshot:{...snapshot,mode:'conservative',formula_score:60}}]}}});
  });
  await page.goto('/watchlist');
  await page.getByRole('button',{name:'检测评分',exact:true}).click();
  await expect(page.getByRole('button',{name:'停止本轮'})).toBeVisible();
  await page.getByLabel('评分模式',{exact:true}).selectOption('conservative');
  await expect(page.getByRole('button',{name:'检测评分',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'检测评分',exact:true}).click();
  await expect(page.getByText('60.00分')).toBeVisible();
  release();
  await expect(page.getByText('99.00分')).toHaveCount(0);
});


test('automatic detection pauses while page is hidden and refreshes on visibility',async({page})=>{
  await page.clock.install();
  await page.route('**/api/watchlists**',r=>r.fulfill({json:{result:{groups:[{id:'us',name:'美股',items:[{market:'US',ticker:'AAPL'}],children:[]}]}}}));
  let detections=0;
  await page.route('**/api/watchlists/detection',r=>{detections++;return r.fulfill({json:{result:{items:[{market:'US',ticker:'AAPL',status:'ok',snapshot}]}}});});
  await page.goto('/watchlist');
  await page.getByRole('checkbox',{name:'页面可见时每60秒检测'}).check();
  await page.clock.fastForward(60001);
  await expect.poll(()=>detections).toBe(1);
  await expect(page.getByRole('button',{name:'检测评分',exact:true})).toBeEnabled();
  await page.evaluate(()=>Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'}));
  await page.clock.fastForward(180000);
  expect(detections).toBe(1);
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});document.dispatchEvent(new Event('visibilitychange'));});
  await expect.poll(()=>detections).toBe(2);
});

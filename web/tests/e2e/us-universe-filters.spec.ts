import { test, expect } from '@playwright/test';
import { chooseSelect } from './select-support';

test('US filters use USD units, apply on the backend and reveal full coverage', async ({ page }) => {
  let requested: URL | undefined;
  await page.route('**/auth/profile', route => route.fulfill({ json: null }));
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/formula-ranking') {
      requested = url;
      return route.fulfill({ json: { result: {
        market: url.searchParams.get('market'), mode: 'balanced', items: [], total: 0,
        universe_count: 6000, quote_coverage_count: 5800, quote_missing_count: 200,
        filtered_count: 0, scoring_limit: 120, candidate_count: 0, source: 'US test snapshot',
      } } });
    }
    return route.fulfill({ json: { result: { status: 'not_run', items: [], applied: false } } });
  });
  await page.goto('/stock-picker');
  await page.getByRole('main').getByRole('button', { name: '美股', exact: true }).click();
  await expect(page.getByText('目录股票', { exact: true })).toBeVisible();
  await expect(page.getByText('6000', { exact: true })).toBeVisible();
  await page.getByLabel('评分数量', { exact: true }).selectOption('0');
  await page.getByLabel('最低市值（亿美元）').fill('50');
  await page.getByLabel('最低股价（美元）').fill('10');
  await page.getByLabel('最低成交额（百万美元）').fill('20');
  await chooseSelect(page, '上市交易所', 'NYSE');
  await page.getByRole('button', { name: '应用筛选', exact: true }).click();
  await expect.poll(() => requested?.searchParams.get('min_market_cap')).toBe('5000000000');
  expect(requested?.searchParams.get('min_amount')).toBe('20000000');
  expect(requested?.searchParams.get('exchange')).toBe('NYSE');
  expect(requested?.searchParams.get('scoring_limit')).toBe('0');
  await expect(page.getByText(/没有股票符合当前条件/)).toBeVisible();
  await page.getByLabel('最高市值（亿美元）').fill('1');
  await page.getByRole('button', { name: '应用筛选', exact: true }).click();
  await expect(page.getByText('最低市值不能大于最高市值', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '取消条件', exact: true }).click();
  await expect.poll(() => requested?.searchParams.get('min_market_cap')).toBe('0');
});


test('automatic refresh repeats requests and can be switched off', async ({ page }) => {
  let requests = 0;
  await page.clock.install();
  await page.route('**/auth/profile', route => route.fulfill({ json: null }));
  await page.route('**/api/**', route => {
    if (new URL(route.request().url()).pathname === '/api/formula-ranking') requests++;
    return route.fulfill({ json: { result: { market: 'CN', mode: 'balanced', items: [], total: 0 } } });
  });
  await page.goto('/stock-picker');
  await expect(page.getByLabel('自动刷新', { exact: true })).toBeVisible();
  await expect.poll(() => requests).toBeGreaterThan(0);
  await expect(page.getByRole('button', { name: '刷新', exact: true })).toBeEnabled();
  const initial = requests;
  await page.getByLabel('自动刷新', { exact: true }).selectOption('60');
  await page.clock.fastForward(60000);
  await expect.poll(() => requests).toBeGreaterThan(initial);
  await page.getByLabel('自动刷新', { exact: true }).selectOption('0');
  const stopped = requests;
  await page.clock.fastForward(120000);
  expect(requests).toBe(stopped);
});


test('research is collapsed until requested and cache update requires login', async ({ page }) => {
  let researchRequests = 0;
  await page.route('**/auth/profile', route => route.fulfill({ json: null }));
  await page.route('**/auth/access-token', route => route.fulfill({ status: 401, json: { error: 'not_authenticated' } }));
  await page.route('**/api/**', route => {
    if (route.request().url().includes('backtest')) researchRequests++;
    return route.fulfill({ json: { result: { status: 'not_run', market: 'CN', mode: 'balanced', items: [], total: 0, applied: false } } });
  });
  await page.goto('/stock-picker');
  await expect(page.getByRole('heading', { name: '选股', exact: true })).toBeVisible();
  expect(researchRequests).toBe(0);
  await page.getByRole('button', { name: '更新行情与评分缓存', exact: true }).click();
  await expect(page.getByText('请先登录后更新行情缓存', { exact: true })).toBeVisible();
  await page.getByText('研究与验证（回测、冻结参数、资金情景）', { exact: true }).click();
  await expect.poll(() => researchRequests).toBeGreaterThan(0);
});

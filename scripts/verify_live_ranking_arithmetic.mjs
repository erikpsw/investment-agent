// Actual public rankings and rendered rows; no intercepted requests.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const require = createRequire(new URL('../web/package.json', import.meta.url));
require('tsx/cjs');
const { validScoreItem } = require('./src/lib/formula-score-validation.ts');
const { chromium, expect } = require('@playwright/test');
const [folder, origin = 'https://www.erikai.top'] = process.argv.slice(2);
assert.ok(folder);
const output = resolve(folder); await mkdir(output);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const records = [];
try {
  const page = await browser.newPage();
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  for (const [market, label] of [['CN', 'A股'], ['HK', '港股'], ['US', '美股']]) {
    const fetched = page.waitForResponse(response => {
      const u = new URL(response.url());
      return u.pathname === '/api/formula-ranking' && u.searchParams.get('market') === market && u.searchParams.get('mode') === 'balanced';
    }, { timeout: 180000 });
    if (market === 'CN') await page.goto(`${origin}/stock-picker`, { waitUntil: 'domcontentloaded', timeout: 90000 });
    else await page.getByRole('main').getByRole('button', { name: label, exact: true }).click();
    const response = await fetched;
    const payload = await response.json();
    await writeFile(resolve(output, `${market}.json`), JSON.stringify(payload, null, 2), { flag: 'wx' });
    assert.equal(response.status(), 200); assert.equal(payload.result.market, market);
    const items = payload.result.items;
    assert.ok(Array.isArray(items) && items.length > 0);
    assert.ok(items.every(validScoreItem), 'Actual ranking arithmetic must be internally consistent');
    for (const item of items) {
      const link = page.locator(`a[href="/stock/${encodeURIComponent(item.ticker)}?mode=balanced"]`);
      await expect(link).toBeVisible();
    }
    await expect(page.getByText('公式排名数据异常，请重试', { exact: true })).toHaveCount(0);
    assert.deepEqual(errors, []);
    await page.screenshot({ path: resolve(output, `${market}.png`), fullPage: true });
    records.push({ market, count: items.length, arithmetic_valid: true, rendered: true, http_status: response.status() });
    console.log(JSON.stringify(records.at(-1)));
  }
  await writeFile(resolve(output, 'manifest.json'), JSON.stringify({ origin, mocked_requests: false, records }, null, 2), { flag: 'wx' });
} finally { await browser.close(); }

// Actual deployed responses and rendered stock detail scores; no intercepted requests.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const require = createRequire(new URL('../web/package.json', import.meta.url));
const { chromium, expect } = require('@playwright/test');
const [outputPath, origin = 'https://www.erikai.top', selected] = process.argv.slice(2);
const tickers = selected ? selected.split(',') : ['sh600519', 'hk00700', 'AAPL', 'BF.A', 'BRK.B'];
assert.ok(tickers.every(ticker => /^[A-Za-z][A-Za-z0-9.-]{0,14}$/.test(ticker)));
assert.ok(outputPath, 'An unused evidence directory is required');
const output = resolve(outputPath);
await mkdir(output); // Fail rather than overwrite prior acceptance evidence.
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const results = [];
try {
  for (const ticker of tickers) {
    for (const [mode, label] of [['balanced', '均衡'], ['conservative', '稳健'], ['aggressive', '进取']]) {
      const context = await browser.newContext();
      try {
        const page = await context.newPage();
        const fetched = page.waitForResponse(response => {
          const url = new URL(response.url());
          return url.pathname === `/api/formula-ranking/stock/${ticker}` && url.searchParams.get('mode') === mode;
        }, { timeout: 90000 });
        const navigation = await page.goto(`${origin}/stock/${ticker}?mode=${mode}`, { waitUntil: 'domcontentloaded', timeout: 90000 });
        assert.equal(navigation.status(), 200);
        const response = await fetched;
        const payload = await response.json();
        await writeFile(resolve(output, `${ticker}-${mode}.json`), JSON.stringify(payload, null, 2), { flag: 'wx' });
        assert.equal(response.status(), 200);
        assert.equal(payload.result.status, 'ok');
        assert.equal(payload.result.mode, mode);
        assert.equal(payload.result.item.ticker, ticker);
        const item = payload.result.item;
        await expect(page.getByRole('button', { name: `评分模式：${label}`, exact: true })).toHaveAttribute('aria-pressed', 'true');
        await expect(page.getByText(`${item.formula_score.toFixed(1)} / 100`, { exact: true })).toBeVisible();
        if (item.risk_plan.status === 'ok') {
          await page.getByText(/^止盈止损参考 ·/).click();
          const stop = page.getByText(/^止损 [0-9.e+-]+（距离/).first();
          await expect(stop).toBeVisible();
          const displayed = Number((await stop.textContent()).match(/^止损 ([0-9.e+-]+)/)[1]);
          assert.ok(Math.abs(displayed - item.risk_plan.stop_loss) <= 0.005, 'Rendered stop must match the analytical level within cent rounding');
        }
        await page.screenshot({ path: resolve(output, `${ticker}-${mode}.png`), fullPage: true });
        results.push({ ticker, mode, score_rendered: true, score: item.formula_score, risk_status: item.risk_plan.status });
        console.log(JSON.stringify(results.at(-1)));
      } finally { await context.close(); }
    }
  }
  await writeFile(resolve(output, 'manifest.json'), JSON.stringify({ origin, mocked_requests: false, results }, null, 2), { flag: 'wx' });
} finally { await browser.close(); }

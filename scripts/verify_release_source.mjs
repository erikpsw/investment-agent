// Fail the production build when its checkout cannot ship quant scoring.
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const read = path => readFileSync(resolve(root, path), 'utf8');
const route = read('api/routes/formula_ranking.py');
assert.ok(route.includes('@router.get("/formula-ranking/stock/{ticker}")'), 'Missing stock scoring endpoint');
assert.ok(route.includes('from investment.data.cn_live_scanner import scan_cn_market'), 'Missing CN snapshot recovery');
assert.ok(route.includes('from investment.data.foreign_live_scanner import scan_foreign_market'), 'Missing HK/US snapshot recovery');
assert.match(read('web/src/app/stock/[ticker]/page.tsx'), /<StockFormulaScore\b/, 'Missing stock detail scoring panel');
assert.match(read('web/src/app/stock-picker/page.tsx'), /<USUniverseFilterPanel\b/, 'Missing US universe filter panel');
assert.ok(read('data/foreign_live_scanner.py').includes('return read_us_snapshot()'), 'US scanner reverted to active-only candidates');
for (const path of ['data/formula_scoring.py', 'data/formula_risk.py', 'data/screener_snapshot_store.py',
  'api/market_snapshots/cn-sina.json', 'api/market_snapshots/hot-hk.json', 'api/market_snapshots/us-universe.json',
  'data/us_universe.py', 'scripts/update_us_universe.py',
  'api/research_reports/manifest.json', 'storage/market/instrument-catalog.json']) {
  assert.ok(existsSync(resolve(root, path)), `Missing release input: ${path}`);
}
const us = JSON.parse(read('api/market_snapshots/us-universe.json'));
assert.equal(us.version, 'us-universe-v1');
assert.ok(us.directory.length >= 3000 && us.rows.length >= us.directory.length * .7, 'Incomplete US release snapshot');
console.log('Quant scoring endpoints, detail integration and release inputs are present.');

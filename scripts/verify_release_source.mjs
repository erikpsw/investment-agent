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
for (const path of ['data/formula_scoring.py', 'data/formula_risk.py', 'data/screener_snapshot_store.py',
  'api/market_snapshots/cn-sina.json', 'api/market_snapshots/hot-hk.json',
  'api/research_reports/manifest.json', 'storage/market/instrument-catalog.json']) {
  assert.ok(existsSync(resolve(root, path)), `Missing release input: ${path}`);
}
console.log('Quant scoring endpoints, detail integration and release inputs are present.');

import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { PGlite } from '../storage/score-tracking-sql-test/node_modules/@electric-sql/pglite/dist/index.js';

const db = new PGlite();
process.on('uncaughtException', e => { console.error(e.message, e.code, e.where || ''); process.exit(1); });
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
await db.exec(await readFile(new URL('../supabase/migrations/202607160001_create_user_portfolios.sql', import.meta.url), 'utf8'));
await db.exec(await readFile(new URL('../supabase/migrations/202610220001_score_tracking.sql', import.meta.url), 'utf8'));
await db.exec(await readFile(new URL('../supabase/migrations/20261022142807_score_tracking_http_conflicts.sql', import.meta.url), 'utf8'));
let checks = 0;
async function query(sql, args = []) { return (await db.query(sql, args)).rows; }
async function rpc(name, args) { return (await query(`select public.${name}(${args.map((_, i) => `$${i + 1}`).join(',')}) as result`, args))[0].result; }
async function rejects(fn, code) { await assert.rejects(fn, e => e.code === code); checks++; }
await db.exec('set role service_role');
const quoteTime = new Date(Date.now() - 60000).toISOString();
const snapshot = { market:'US', ticker:'AAPL', mode:'balanced', config_fingerprint:'a', formula_version:'v2',
  quote_as_of:quoteTime, formula_score:75, data_coverage:1, price:100, contributions:{trend:75} };
const saved = await rpc('append_security_score', ['alice', snapshot]);
assert.equal(saved.inserted, true); checks++;
assert.equal((await rpc('append_security_score', ['alice', snapshot])).snapshot.id, saved.snapshot.id); checks++;
await rejects(() => rpc('append_security_score', ['alice', {...snapshot, formula_score:90}]), 'PT409');
assert.equal((await rpc('security_score_history', ['bob','US','AAPL',null,200,30])).items.length, 0); checks++;
const cash = await rpc('apply_portfolio_event', ['alice',randomUUID(),0,{action:'set_cash',currency:'USD',amount:1000}]);
assert.equal(cash.revision,1); checks++;
const request = randomUUID();
const buyEvent = { action:'buy',market:'US',instrument_id:'AAPL',quantity:2,price:100,fee:1,
  executed_at:new Date().toISOString(),score_snapshot_id:saved.snapshot.id };
const bought = await rpc('apply_portfolio_event', ['alice',request,1,buyEvent]);
assert.equal(bought.positions.find(p => p.ticker==='CASH_USD').quantity,799); checks++;
assert.equal(bought.management['US:AAPL'].entry_snapshot.formula_score,75); checks++;
assert.equal((await rpc('apply_portfolio_event', ['alice',request,1,buyEvent])).revision,2); checks++;
await rejects(() => rpc('apply_portfolio_event', ['alice',request,2,{...buyEvent,quantity:3}]), 'PT409');
await rejects(() => rpc('apply_portfolio_event', ['alice',randomUUID(),1,buyEvent]), 'PT409');
await rejects(() => rpc('apply_portfolio_event', ['alice',randomUUID(),2,{...buyEvent,quantity:10000}]), '22023');
assert.equal((await rpc('portfolio_management_state',['alice'])).revision,2); checks++;
await rejects(() => rpc('apply_portfolio_event', ['bob',randomUUID(),0,{...buyEvent}]), '22023');
await rejects(() => rpc('apply_portfolio_event',['alice',randomUUID(),2,{...buyEvent,executed_at:new Date(Date.now()-30000).toISOString()}]), '22023');
await rejects(() => rpc('apply_portfolio_event',['alice',randomUUID(),2,{action:'replace_positions',positions:bought.positions.map(p=>p.market==='US'?{...p,currency:'CNY'}:p)}]), '22023');
const episode = bought.management['US:AAPL'].episode_id;
const plan = { snapshot_id:saved.snapshot.id,config_fingerprint:'a',quote_as_of:quoteTime,
  currency:'USD',price_basis:'raw',reference_price:100,stop_loss:95,take_profit_1:110 };
const protectedState = await rpc('apply_portfolio_event',['alice',randomUUID(),2,{action:'protection',market:'US',instrument_id:'AAPL',episode_id:episode,plan}]);
assert.equal(protectedState.management['US:AAPL'].protection.stop_loss,95); checks++;
await rejects(() => rpc('apply_portfolio_event',['alice',randomUUID(),3,{action:'protection',market:'US',instrument_id:'AAPL',episode_id:episode,plan:{...plan,stop_loss:90}}]), '22023');
await rejects(() => query("update public.user_portfolios set positions='[]' where user_id='alice'"), 'PT409');
const added=await rpc('apply_portfolio_event',['alice',randomUUID(),3,{action:'buy',market:'US',instrument_id:'AAPL',quantity:1,price:100}]);
assert.equal(added.management['US:AAPL'].episode_id,episode); checks++;
assert.equal(added.management['US:AAPL'].entry_snapshot.id,saved.snapshot.id); checks++;
const partial=await rpc('apply_portfolio_event',['alice',randomUUID(),4,{action:'sell',market:'US',instrument_id:'AAPL',quantity:1,price:100}]);
assert.equal(partial.management['US:AAPL'].episode_id,episode); checks++;
assert.equal(partial.management['US:AAPL'].entry_snapshot.id,saved.snapshot.id); checks++;
const sold = await rpc('apply_portfolio_event',['alice',randomUUID(),5,{action:'sell',market:'US',instrument_id:'AAPL',quantity:2,price:100}]);
assert.equal(sold.management['US:AAPL'],undefined); checks++;
const reentered = await rpc('apply_portfolio_event',['alice',randomUUID(),6,{action:'buy',market:'US',instrument_id:'AAPL',quantity:1,price:100}]);
assert.notEqual(reentered.management['US:AAPL'].episode_id,episode); checks++;
assert.equal(reentered.management['US:AAPL'].entry_snapshot,null); checks++;
await rejects(() => rpc('save_portfolio_risk_settings',['alice',{risk_budget_percent:999}]), '22023');
const normalized = await rpc('normalize_score_positions', [[{market:'CN',ticker:'600000',quantity:100,avg_cost:10},{market:'HK',ticker:'0017.HK',quantity:100,avg_cost:10}]]);
assert.equal(normalized[0].ticker,'sh600000'); assert.equal(normalized[1].ticker,'hk00017'); checks++;
await rejects(()=>rpc('normalize_score_positions',[[{market:'CN',ticker:'600000',quantity:1},{market:'CN',ticker:'sh600000',quantity:1}]]),'22023');
const legacy=await rpc('apply_portfolio_event',['legacy',randomUUID(),0,{action:'replace_positions',positions:[{market:'CN',ticker:'600000',quantity:100,avg_cost:10}]}]);
const adopted=await rpc('apply_portfolio_event',['legacy',randomUUID(),legacy.revision,{action:'adopt',market:'CN',instrument_id:'sh600000'}]);
assert.equal(adopted.management['CN:sh600000'].entry_snapshot,null); checks++;
for (const role of ['anon','authenticated']) {
  await db.exec(`reset role; set role ${role}`);
  await rejects(() => query('select * from public.user_security_score_snapshots'), '42501');
  await rejects(() => rpc('portfolio_management_state',['alice']), '42501');
}
await db.close();
console.log(`${checks} real PostgreSQL transaction/isolation/permission checks passed (PGlite; no remote migration).`);

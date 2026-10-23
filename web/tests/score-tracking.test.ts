import test from 'node:test';
import assert from 'node:assert/strict';
import { comparableScores, scoreDelta, requestIsCurrent, securitiesFrom, scoreKey, entrySnapshotAt } from '../src/lib/score-tracking';

const score = { market:'US',ticker:'AAPL',mode:'balanced',formula_version:'v2',config_fingerprint:'a',formula_score:70 };
test('scores only compare across identical identities and configurations', () => {
  assert.equal(scoreDelta({...score,formula_score:75},score),5);
  assert.equal(comparableScores(score,{...score,mode:'aggressive'}),false);
  assert.equal(scoreDelta(score,{...score,formula_version:'v3'}),null);
  assert.equal(scoreDelta(score,{...score,formula_score:null}),null);
});
test('a changed user or request generation rejects an old response', () => {
  assert.equal(requestIsCurrent({generation:2,user:'alice'},{generation:1,user:'alice'}),false);
  assert.equal(requestIsCurrent({generation:2,user:'bob'},{generation:2,user:'alice'}),false);
  assert.equal(requestIsCurrent({generation:2,user:'alice'},{generation:2,user:'alice'}),true);
});

test('canonical securities match provider responses across CN/HK and deduplicate',()=>{
  assert.equal(scoreKey({market:'CN',ticker:'600000'}),'CN:sh600000');
  assert.equal(scoreKey({market:'HK',ticker:'0017.HK'}),'HK:hk00017');
  assert.equal(securitiesFrom([{market:'CN',ticker:'600000'},{market:'CN',ticker:'sh600000'}]).length,1);
});
test('backfilled buy cannot borrow later-observed score; earlier applicable record is selected',()=>{
  const row={...score,id:'late',quote_as_of:'2026-10-20T10:00:00Z',observed_at:'2026-10-20T10:10:00Z'};
  assert.equal(entrySnapshotAt([row],'balanced','2026-10-20T10:05:00Z'),undefined);
  assert.equal(entrySnapshotAt([row,{...row,id:'early',observed_at:'2026-10-20T10:01:00Z'}],'balanced','2026-10-20T10:05:00Z')?.id,'early');
});

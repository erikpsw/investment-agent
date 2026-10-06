import { test } from "node:test";
import assert from "node:assert/strict";
import { securityIdentity, validScoreItem } from "../src/lib/formula-score-validation";
import { validScreenCandidates } from "../src/lib/screen-candidate-validation";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const archivedScore = () => JSON.parse(readFileSync(resolve(process.cwd(), "tests/fixtures/formula-score/AAPL-balanced.json"), "utf8")).result.item;
test("complete factor arithmetic rejects altered scores, contributions, weights and coverage", () => {
  const source = archivedScore();
  assert.equal(validScoreItem(source), true);
  for (const mutate of [
    (value: any) => value.formula_score += 1,
    (value: any) => value.contributions["5日动量"] += 1,
    (value: any) => value.weights["5日动量"] += .01,
    (value: any) => delete value.contributions["20日趋势"],
    (value: any) => delete value.components["风险惩罚"],
    (value: any) => value.components["风险惩罚"] = -1,
    (value: any) => value.data_coverage = source.data_coverage > .1 ? source.data_coverage - .1 : .9,
    (value: any) => value.components["5日动量"] = 101,
  ]) {
    const value = structuredClone(source); mutate(value);
    assert.equal(validScoreItem(value), false);
    assert.equal(validScreenCandidates({ market: "US", items: [{ ...value, match_reasons: ["符合条件"] }] }, "US"), false);
  }
});
test("actual three-market three-mode scores preserve engine rounding and missing factors", () => {
  for (const ticker of ["sh600519", "hk00700", "AAPL"]) for (const mode of ["balanced", "conservative", "aggressive"]) {
    const value = JSON.parse(readFileSync(resolve(process.cwd(), `tests/fixtures/formula-score/${ticker}-${mode}.json`), "utf8")).result.item;
    const before = JSON.stringify(value);
    assert.equal(validScoreItem(value), true, `${ticker}/${mode}`);
    assert.equal(JSON.stringify(value), before);
  }
});
test("loss-making PE remains available and a penalty can clamp the total to zero", () => {
  const value = archivedScore();
  const fields = ["change_5d", "change_20d", "change_60d", "today_change_percent", "volume_ratio", "turnover_rate", "pe_ratio", "pb_ratio", "market_cap"];
  for (const field of fields) value[field] = null;
  value.pe_ratio = -10;
  value.missing_fields = fields.filter(field => field !== "pe_ratio");
  for (const name of Object.keys(value.weights)) { value.components[name] = 0; value.contributions[name] = 0; }
  value.components["估值"] = 13; value.contributions["估值"] = .65;
  value.components["风险惩罚"] = 8; value.formula_score = 0; value.data_coverage = .0325;
  assert.equal(validScoreItem(value), true);
  assert.equal(validScoreItem({ ...value, formula_score: .1 }), false);
  assert.equal(validScoreItem({ ...value, change_5d: "0" }), false);
  assert.equal(validScoreItem({ ...value, missing_fields: [...value.missing_fields, "pe_ratio"] }), false);
});
test("separately rounded components and weighted contributions retain both error bounds", () => {
  const value = archivedScore();
  // Unrounded component 83.33366: component rounds to 83.3337, while
  // its 15% contribution 12.500049 rounds to 12.5000 independently.
  value.components["60日趋势"] = 83.3337;
  value.contributions["60日趋势"] = 12.5;
  const sum = Object.values(value.contributions).reduce((total: number, v) => total + (v as number), 0);
  value.formula_score = Math.round(Math.max(0, Math.min(100, sum - value.components["风险惩罚"])) * 10) / 10;
  assert.equal(validScoreItem(value), true);
  value.contributions["60日趋势"] += .001;
  assert.equal(validScoreItem(value), false);
});

test("detail aliases identify canonical securities without changing share classes", () => {
  for (const [input, ticker, market] of [["600519", "sh600519", "CN"], ["000001", "sz000001", "CN"], ["920001", "bj920001", "CN"],
    ["HK0700", "hk00700", "HK"], ["0700.HK", "hk00700", "HK"], ["brk.b", "BRK.B", "US"], ["BRK.A", "BRK.A", "US"]]) {
    assert.deepEqual(securityIdentity(input), [ticker, market]);
  }
  for (const input of ["", "../AAPL", "AAPL?mode=aggressive", "100000000000000000"]) assert.equal(securityIdentity(input), undefined);
  // This spelling follows the API's US symbol grammar, never the HK alias rule.
  assert.deepEqual(securityIdentity("hk700"), ["HK700", "US"]);
  assert.equal(validScreenCandidates({ market: "HK", items: [{ ...item, ticker: "hk700", market: "HK" }] }), false);
});

const item = { ticker: "BRK.B", market: "US", formula_score: 68, recommendation: "观察", data_coverage: .8, weights: { momentum: .2 }, contributions: { momentum: 15 }, match_reasons: ["符合条件"], risks: [] };
test("score validation preserves valid missing factors and rejects misleading fields", () => {
  assert.equal(validScoreItem(item), true);
  assert.equal(validScoreItem({ formula_score: 0, recommendation: "数据不足" }), true);
  for (const patch of [{ formula_score: "68" }, { formula_score: -1 }, { formula_score: NaN }, { formula_score: 101 }, { recommendation: {} },
    { weights: { momentum: .2, value: Infinity } }, { contributions: [] }, { risks: "风险" }, { data_coverage: 2 }]) {
    assert.equal(validScoreItem({ ...item, ...patch }), false);
  }
});

test("candidate lists must match the requested market and canonical identities", () => {
  for (const [market, ticker, currency] of [["CN", "sh600519", "CNY"], ["HK", "hk00700", "HKD"], ["US", "BRK.B", "USD"]]) {
    const result = { market, currency, items: [{ ...item, ticker, market }] };
    const before = JSON.stringify(result);
    assert.equal(validScreenCandidates(result, market), true);
    assert.equal(validScreenCandidates(result, market === "US" ? "CN" : "US"), false);
    assert.equal(validScreenCandidates({ ...result, currency: "EUR" }, market), false);
    assert.equal(validScreenCandidates({ ...result, items: [{ ...item, ticker, market: "UNKNOWN" }] }, market), false);
    assert.equal(JSON.stringify(result), before);
  }
  assert.equal(validScreenCandidates({ market: "CN", items: [{ ...item, ticker: "600519", market: "CN" }] }), false);
});

test("duplicate and malformed candidates cannot be partially accepted", () => {
  for (const items of [[item, item], [item, null], [item, { ...item, ticker: "BRK.A", match_reasons: "原因" }], [{ ...item, name: {} }], Array(51).fill(item)]) {
    assert.equal(validScreenCandidates({ market: "US", items }), false);
  }
  assert.equal(validScreenCandidates({ items: [] }), true);
  assert.equal(validScreenCandidates(null), false);
  assert.equal(validScreenCandidates({ market: "constructor", items: [item] }), false);
});

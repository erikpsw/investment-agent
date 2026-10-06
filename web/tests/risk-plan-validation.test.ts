import { test } from "node:test";
import assert from "node:assert/strict";
import { validRiskPlan } from "../src/lib/risk-plan-validation";

const plan = { status: "ok", currency: "CNY", reference_price: 100, stop_loss: 92, take_profit_1: 112, take_profit_2: 120,
  atr14: 4, trailing_distance: 8, stop_distance_percent: 8, position_cap_percent: 12.5, risk_budget_percent: 1 };

test("valid plans bind to each market currency and retain tiny-price precision", () => {
  for (const [market, currency] of [["CN", "CNY"], ["HK", "HKD"], ["US", "USD"]]) {
    assert.equal(validRiskPlan({ ...plan, currency }, market), true);
    assert.equal(validRiskPlan({ ...plan, currency, reference_price: .005, stop_loss: .0046, take_profit_1: .0056, take_profit_2: .006, atr14: .0002, trailing_distance: .0004 }, market), true);
  }
});

test("unordered, missing, nonfinite and coerced prices do not form a valid plan", () => {
  for (const patch of [{ stop_loss: 100 }, { stop_loss: 0 }, { take_profit_1: 100 }, { take_profit_2: 112 }, { reference_price: "100" },
    { atr14: NaN }, { trailing_distance: Infinity }, { take_profit_2: undefined }]) assert.equal(validRiskPlan({ ...plan, ...patch }, "CN"), false);
});

test("budgets and displayed stop distance must describe the same valid scenario", () => {
  for (const patch of [{ risk_budget_percent: 0 }, { risk_budget_percent: 101 }, { position_cap_percent: -1 }, { position_cap_percent: undefined },
    { stop_distance_percent: 10 }, { stop_distance_percent: "8" }]) assert.equal(validRiskPlan({ ...plan, ...patch }, "CN"), false);
});

test("wrong currencies and malformed explanation lists are rejected without mutation", () => {
  const before = JSON.stringify(plan);
  assert.equal(validRiskPlan(plan, "US"), false);
  assert.equal(validRiskPlan({ ...plan, currency: "EUR" }, "CN"), false);
  assert.equal(validRiskPlan(plan, "UNKNOWN"), false);
  assert.equal(validRiskPlan({ ...plan, basis: "ATR" }, "CN"), false);
  assert.equal(validRiskPlan({ ...plan, limitations: [42] }, "CN"), false);
  assert.equal(validRiskPlan({ ...plan, basis: ["ATR"], limitations: ["跳空风险"] }, "CN"), true);
  assert.equal(JSON.stringify(plan), before);
});

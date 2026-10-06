import assert from 'node:assert/strict';
import test from 'node:test';
import { riskOrderAmounts, riskTargetAmounts } from '../src/lib/risk-scenario';
import { enumerateOrder, targetOracle } from '../../scripts/risk_scenario_oracle.mjs';

test('independent exhaustive orders agree across 300 deterministic price, step and cost scenarios', () => {
  let seed = 10705;
  const pick = <T,>(values: T[]): T => { seed = (seed * 1664525 + 1013904223) >>> 0; return values[seed % values.length]; };
  for (let i = 0; i < 300; i++) {
    const price = pick([.25, 1.5, 26.67, 100, 1258.62]);
    const stop = price * pick([.5, .9, .999999]);
    const input = { capital: pick([100, 1000, 10000]), step: pick([1, 10, 100, 500]),
      ratePercent: pick([0, .15, 1]), minimumFee: pick([0, 5, 20]), slippagePercent: pick([0, .1, 1]) };
    const plan = { reference_price: price, stop_loss: stop, position_cap_percent: 20, risk_budget_percent: 1 };
    const expected = enumerateOrder(plan, input);
    const actual = riskOrderAmounts(input.capital, 20, 1, price, stop, input.step, input.ratePercent, input.minimumFee, input.slippagePercent);
    assert.ok(actual);
    assert.equal(actual.quantity, expected.quantity, `scenario ${i}`);
    if (actual.quantity) {
      assert.ok(Math.abs(actual.cashRequired - expected.cashRequired) < 1e-8);
      assert.ok(Math.abs(actual.totalStopLossAmount - expected.totalStopLossAmount) < 1e-8);
      const target = price * 1.2;
      const actualTarget = riskTargetAmounts(actual, target, input.ratePercent, input.minimumFee, input.slippagePercent)!;
      const expectedTarget = targetOracle(expected, target, input);
      assert.ok(Math.abs(actualTarget.netProfitAmount - expectedTarget.netProfit) < 1e-8);
      assert.ok(Math.abs(actualTarget.rewardRiskRatio - expectedTarget.rewardRisk) < 1e-8);
    }
  }
});

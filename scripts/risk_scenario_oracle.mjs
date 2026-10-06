// Independent exhaustive reference for bounded acceptance scenarios, not a trading engine.
import assert from 'node:assert/strict';

export function enumerateOrder(plan, input) {
  const { capital, step, ratePercent, minimumFee, slippagePercent } = input;
  const entryPrice = plan.reference_price * (1 + slippagePercent / 100);
  const stopPrice = plan.stop_loss * (1 - slippagePercent / 100);
  const cashBudget = capital * plan.position_cap_percent / 100;
  const riskBudget = capital * plan.risk_budget_percent / 100;
  const limit = Math.floor(cashBudget / entryPrice / step);
  assert.ok(Number.isSafeInteger(limit) && limit >= 0 && limit <= 100000, 'Enumeration scope exceeded');
  let result = { quantity: 0, cashRequired: 0, totalStopLossAmount: 0,
    entryFee: 0, exitFee: 0, entryPrice, stopPrice };
  for (let lots = 1; lots <= limit; lots++) {
    const quantity = lots * step;
    const entryFee = Math.max(quantity * entryPrice * ratePercent / 100, minimumFee);
    const exitFee = Math.max(quantity * stopPrice * ratePercent / 100, minimumFee);
    const cashRequired = quantity * entryPrice + entryFee;
    const totalStopLossAmount = quantity * (entryPrice - stopPrice) + entryFee + exitFee;
    if (cashRequired <= cashBudget && totalStopLossAmount <= riskBudget) {
      result = { quantity, cashRequired, totalStopLossAmount, entryFee, exitFee, entryPrice, stopPrice };
    }
  }
  return result;
}

export function targetOracle(order, target, input) {
  assert.ok(order.quantity > 0);
  const proceeds = order.quantity * target * (1 - input.slippagePercent / 100);
  const fee = Math.max(proceeds * input.ratePercent / 100, input.minimumFee);
  const netProfit = proceeds - fee - order.cashRequired;
  return { netProfit, rewardRisk: netProfit / order.totalStopLossAmount };
}

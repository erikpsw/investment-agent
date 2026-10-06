import assert from "node:assert/strict";
import test from "node:test";
import { riskAmounts, riskOrderAmounts, riskTargetAmounts } from "../src/lib/risk-scenario";

test("amounts respect both position cap and portfolio risk budget", () => {
  assert.deepEqual(riskAmounts(100000, 12.5, 8, 1), { positionAmount: 12500, stopLossAmount: 1000 });
  assert.deepEqual(riskAmounts(100000, 20, 8, 1), { positionAmount: 12500, stopLossAmount: 1000 });
  assert.deepEqual(riskAmounts(100000, 10, 8, 1), { positionAmount: 10000, stopLossAmount: 800 });
});

test("order quantities include both fees inside the stop risk budget", () => {
  const result = riskOrderAmounts(100000, 12.5, 1, 100, 92, 1, .15, 5);
  assert.ok(result);
  assert.equal(result.quantity, 120);
  assert.equal(result.totalStopLossAmount, 994.56);
  assert.ok(result.cashRequired <= 12500);
  assert.ok(result.totalStopLossAmount <= 1000);
  assert.equal(riskOrderAmounts(1000, 12.5, 1, 100, 92, 1, 0, 5)?.quantity, 0);
});

test("rounded order is feasible and one additional step breaches a budget", () => {
  for (const capital of [1000, 10000, 100000]) for (const step of [1, 100, 500]) for (const percent of [0, .15, 1]) {
    const result = riskOrderAmounts(capital, 20, 1, 100, 92, step, percent, 5);
    assert.ok(result);
    assert.equal(result.quantity % step, 0);
    assert.ok(result.cashRequired <= capital * .20);
    assert.ok(result.totalStopLossAmount <= capital * .01);
    const quantity = result.quantity + step;
    const buyFee = Math.max(quantity * 100 * percent / 100, 5);
    const sellFee = Math.max(quantity * 92 * percent / 100, 5);
    assert.ok(quantity * 100 + buyFee > capital * .20 || quantity * 8 + buyFee + sellFee > capital * .01);
  }
});

test("invalid price, fees or step cannot produce an order suggestion", () => {
  for (const args of [
    [1000, 20, 1, 0, 92, 1, 0, 0],
    [1000, 20, 1, 100, 101, 1, 0, 0],
    [1000, 20, 1, 100, 92, 1.5, 0, 0],
    [1000, 20, 1, 100, 92, 1, NaN, 0],
    [1000, 20, 1, 100, 92, 1, 0, -1],
    [1000, 20, 1, 1e-20, 1e-21, 1, 0, 0],
  ]) assert.equal(riskOrderAmounts(...args as [number, number, number, number, number, number, number, number]), null);
});

test("invalid or unbounded inputs never produce amount suggestions", () => {
  for (const capital of [0, -1, NaN, Infinity]) assert.equal(riskAmounts(capital, 10, 8, 1), null);
  for (const cap of [-1, 0, 101, Infinity]) assert.equal(riskAmounts(100000, cap, 8, 1), null);
  assert.equal(riskAmounts(100000, 10, 0, 1), null);
  assert.equal(riskAmounts(100000, 10, 101, 1), null);
  assert.equal(riskAmounts(100000, 10, 8, Infinity), null);
  assert.equal(riskAmounts(Number.MAX_VALUE, 10, 8, 1), null);
});

test("two-sided slippage and execution-price fees stay inside both budgets", () => {
  const result = riskOrderAmounts(100000, 20, 1, 100, 92, 1, .15, 5, 1);
  assert.ok(result);
  assert.equal(result.entryPrice, 101);
  assert.equal(result.stopExecutionPrice, 91.08);
  assert.ok(result.quantity < riskOrderAmounts(100000, 20, 1, 100, 92, 1, .15, 5)!.quantity);
  assert.ok(result.cashRequired <= 20000 && result.totalStopLossAmount <= 1000);
  assert.ok(Math.abs(result.slippageAmount - result.quantity * 1.92) < 1e-9);
  assert.equal(result.entryFee, Math.max(result.quantity * 101 * .0015, 5));
  assert.equal(result.exitFee, Math.max(result.quantity * 91.08 * .0015, 5));
});

test("slippage orders are maximal whole steps under capital and stop-loss budgets", () => {
  for (const step of [1, 100, 500]) for (const slippage of [0, .1, 1, 5]) {
    const result = riskOrderAmounts(100000, 20, 1, 100, 92, step, .15, 20, slippage);
    assert.ok(result);
    assert.equal(result.quantity % step, 0);
    assert.ok(result.cashRequired <= 20000 && result.totalStopLossAmount <= 1000);
    const next = result.quantity + step;
    const entryFee = Math.max(next * result.entryPrice * .0015, 20);
    const exitFee = Math.max(next * result.stopExecutionPrice * .0015, 20);
    assert.ok(next * result.entryPrice + entryFee > 20000
      || next * (result.entryPrice - result.stopExecutionPrice) + entryFee + exitFee > 1000);
  }
});

test("invalid slippage or overflowed execution prices cannot produce quantities", () => {
  for (const slippage of [-1, 100, NaN, Infinity])
    assert.equal(riskOrderAmounts(100000, 20, 1, 100, 92, 1, .15, 5, slippage), null);
  assert.equal(riskOrderAmounts(100000, 20, 1, Number.MAX_VALUE, Number.MAX_VALUE / 2, 1, 0, 0, 99), null);
});

test("target profits deduct entry and exit fees and both adverse slippage sides", () => {
  const order = riskOrderAmounts(100000, 12.5, 1, 100, 92, 1, .15, 5, 1)!;
  const first = riskTargetAmounts(order, 112, .15, 5, 1)!;
  const second = riskTargetAmounts(order, 120, .15, 5, 1)!;
  assert.equal(first.executionPrice, 110.88);
  assert.ok(Math.abs(first.netProfitAmount - 927.53146) < 1e-8);
  assert.ok(Math.abs(second.netProfitAmount - 1694.6191) < 1e-8);
  assert.equal(first.rewardRiskRatio, first.netProfitAmount / order.totalStopLossAmount);
  assert.equal(first.netReturnPercent, first.netProfitAmount / order.cashRequired * 100);
  assert.equal(first.exitFee, 97 * 110.88 * .0015);
  assert.ok(first.breakEvenTargetPrice! > 100);
  assert.ok(Math.abs(riskTargetAmounts(order, first.breakEvenTargetPrice!, .15, 5, 1)!.netProfitAmount) < 1e-8);
});

test("minimum fees can erase positive gross target profit and break-even uses the binding fee", () => {
  const order = riskOrderAmounts(100000, 12.5, 1, 100, 92, 1, 0, 50)!;
  const target = riskTargetAmounts(order, 100.1, 0, 50)!;
  assert.ok(target.netProfitAmount < 0 && target.rewardRiskRatio < 0);
  assert.equal(target.exitFee, 50);
  assert.ok(Math.abs(riskTargetAmounts(order, target.breakEvenTargetPrice!, 0, 50)!.netProfitAmount) < 1e-8);
});

test("zero fees reproduce price differences and a 100 percent sale fee has no finite break-even", () => {
  const order = riskOrderAmounts(100000, 20, 1, 100, 92, 1, 0, 0)!;
  const zero = riskTargetAmounts(order, 112, 0, 0)!;
  assert.equal(zero.netProfitAmount, order.quantity * 12);
  assert.equal(zero.rewardRiskRatio, 1.5);
  assert.equal(zero.breakEvenTargetPrice, 100);
  const impossible = riskTargetAmounts(order, 112, 100, 0)!;
  assert.equal(impossible.netProfitAmount, -order.cashRequired);
  assert.equal(impossible.breakEvenTargetPrice, null);
});

test("invalid target inputs and zero-share orders do not invent profits", () => {
  const order = riskOrderAmounts(100000, 20, 1, 100, 92, 1, .15, 5)!;
  for (const target of [0, -1, NaN, Infinity]) assert.equal(riskTargetAmounts(order, target, .15, 5), null);
  assert.equal(riskTargetAmounts({ ...order, quantity: 0 }, 112, .15, 5), null);
  assert.equal(riskTargetAmounts(order, 112, .15, 5, 100), null);
  assert.equal(riskTargetAmounts(order, 112, -1, 5), null);
  assert.equal(riskTargetAmounts(order, Number.MAX_VALUE, 100, 5), null);
});

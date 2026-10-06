export function riskAmounts(capital: number, capPercent: number, distancePercent: number, riskPercent: number) {
  if (![capital, capPercent, distancePercent, riskPercent].every(Number.isFinite)
    || capital <= 0 || capital > Number.MAX_SAFE_INTEGER
    || capPercent <= 0 || capPercent > 100 || distancePercent <= 0 || distancePercent > 100
    || riskPercent <= 0 || riskPercent > 100) return null;
  const allowedPercent = Math.min(capPercent, riskPercent / distancePercent * 100);
  const positionAmount = capital * (allowedPercent / 100);
  const stopLossAmount = positionAmount * (distancePercent / 100);
  return { positionAmount, stopLossAmount };
}

export function riskOrderAmounts(capital: number, capPercent: number, riskPercent: number, price: number, stop: number, step: number, feePercent: number, minimumFee: number, slippagePercent = 0) {
  if (![price, stop, step, feePercent, minimumFee, slippagePercent].every(Number.isFinite)
    || price <= 0 || stop <= 0 || stop >= price
    || !Number.isSafeInteger(step) || step <= 0
    || feePercent < 0 || feePercent > 100 || minimumFee < 0 || slippagePercent < 0 || slippagePercent >= 100
    || !riskAmounts(capital, capPercent, (price - stop) / price * 100, riskPercent)) return null;
  const positionBudget = capital * capPercent / 100;
  const riskBudget = capital * riskPercent / 100;
  const rate = feePercent / 100;
  const entryPrice = price * (1 + slippagePercent / 100);
  const stopExecutionPrice = stop * (1 - slippagePercent / 100);
  if (![entryPrice, stopExecutionPrice].every(Number.isFinite) || stopExecutionPrice <= 0) return null;
  const maxLots = Math.floor(positionBudget / entryPrice / step);
  if (!Number.isSafeInteger(maxLots) || !Number.isSafeInteger(maxLots * step)) return null;
  const amounts = (lots: number) => {
    const quantity = lots * step;
    const positionAmount = quantity * entryPrice;
    const entryFee = quantity ? Math.max(positionAmount * rate, minimumFee) : 0;
    const exitFee = quantity ? Math.max(quantity * stopExecutionPrice * rate, minimumFee) : 0;
    const totalStopLossAmount = quantity * (entryPrice - stopExecutionPrice) + entryFee + exitFee;
    const slippageAmount = quantity * ((entryPrice - price) + (stop - stopExecutionPrice));
    const cashRequired = positionAmount + entryFee;
    return { quantity, positionAmount, entryFee, exitFee, totalStopLossAmount, cashRequired, entryPrice, stopExecutionPrice, slippageAmount };
  };
  let low = 0, high = maxLots;
  while (low < high) {
    const mid = low + Math.ceil((high - low) / 2);
    const value = amounts(mid);
    if (value.cashRequired <= positionBudget && value.totalStopLossAmount <= riskBudget) low = mid;
    else high = mid - 1;
  }
  return amounts(low);
}

export function riskTargetAmounts(order: NonNullable<ReturnType<typeof riskOrderAmounts>>, target: number, feePercent: number, minimumFee: number, slippagePercent = 0) {
  if (![target, feePercent, minimumFee, slippagePercent, order.cashRequired, order.totalStopLossAmount].every(Number.isFinite)
    || target <= 0 || !Number.isSafeInteger(order.quantity) || order.quantity <= 0
    || order.cashRequired <= 0 || order.totalStopLossAmount <= 0
    || feePercent < 0 || feePercent > 100 || minimumFee < 0 || slippagePercent < 0 || slippagePercent >= 100) return null;
  const rate = feePercent / 100;
  const executionPrice = target * (1 - slippagePercent / 100);
  const grossProceeds = order.quantity * executionPrice;
  const exitFee = Math.max(grossProceeds * rate, minimumFee);
  const netProceeds = grossProceeds - exitFee;
  const netProfitAmount = netProceeds - order.cashRequired;
  const rewardRiskRatio = netProfitAmount / order.totalStopLossAmount;
  const netReturnPercent = netProfitAmount / order.cashRequired * 100;
  if (![executionPrice, grossProceeds, exitFee, netProceeds, netProfitAmount, rewardRiskRatio, netReturnPercent].every(Number.isFinite)
    || executionPrice <= 0) return null;
  // Both fee branches must leave enough proceeds to recover entry cash.
  const breakEven = rate < 1 ? Math.max(order.cashRequired + minimumFee, order.cashRequired / (1 - rate))
    / order.quantity / (1 - slippagePercent / 100) : NaN;
  const breakEvenTargetPrice = Number.isFinite(breakEven) && breakEven > 0 ? breakEven : null;
  return { executionPrice, exitFee, netProceeds, netProfitAmount, rewardRiskRatio, netReturnPercent, breakEvenTargetPrice };
}

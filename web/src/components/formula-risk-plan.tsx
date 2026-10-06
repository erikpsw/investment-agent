"use client";

import { useId, useState } from "react";
import type { FormulaRankingItem } from "@/lib/api";
import { riskAmounts, riskOrderAmounts, riskTargetAmounts } from "@/lib/risk-scenario";
import { formatRiskPrice } from "@/lib/risk-price";
import { validRiskPlan } from "@/lib/risk-plan-validation";
import { historyPriceLabels } from "@/lib/history-price-labels";

const display = (value?: number) => value != null && Number.isFinite(value) ? value.toFixed(2) : "--";
const money = (value: number) => value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function FormulaRiskPlan({ plan, market, historyMetadata }: { plan: FormulaRankingItem["risk_plan"]; market?: string; historyMetadata?: unknown }) {
  const [capital, setCapital] = useState("");
  const [includeOrder, setIncludeOrder] = useState(false);
  const [step, setStep] = useState("");
  const [feePercent, setFeePercent] = useState("0");
  const [minimumFee, setMinimumFee] = useState("0");
  const [slippagePercent, setSlippagePercent] = useState("0");
  const inputId = useId();
  const labels = historyPriceLabels(historyMetadata);
  const metadata = <div role="group" aria-label="日K价格口径" className="space-y-1 text-xs text-muted-foreground">{labels.provided
    ? <><p>动量日K：{labels.trend}</p><p>保护日K：{labels.protection}</p></> : <p>日K价格口径未提供</p>}</div>;
  if (plan?.status !== "ok") return <>{metadata}<p className="mt-1 text-xs text-muted-foreground">价格参考不可用：{typeof plan?.reason === "string" && plan.reason ? plan.reason : "需要完整OHLC历史"}</p></>;
  if (labels.mixed) return <>{metadata}<p className="mt-1 text-xs text-muted-foreground">价格参考不可用：日K价格口径不一致，暂停保护方案。</p></>;
  if (!validRiskPlan(plan, market)) return <>{metadata}<p className="mt-1 text-xs text-muted-foreground">价格参考不可用：保护方案数据无效，请重新加载评分。</p></>;
  const amounts = riskAmounts(Number(capital), plan.position_cap_percent ?? NaN, plan.stop_distance_percent ?? NaN, plan.risk_budget_percent ?? NaN);
  const validCapital = Number.isFinite(Number(capital)) && Number(capital) > 0 && Number(capital) <= Number.MAX_SAFE_INTEGER;
  const currency = plan.currency;
  const gap = Math.min(...[
    (plan.reference_price ?? NaN) - (plan.stop_loss ?? NaN),
    (plan.take_profit_1 ?? NaN) - (plan.reference_price ?? NaN),
    (plan.take_profit_2 ?? NaN) - (plan.take_profit_1 ?? NaN),
    plan.atr14 ?? NaN, plan.trailing_distance ?? NaN,
  ].filter(value => Number.isFinite(value) && value > 0));
  const price = (value?: number) => formatRiskPrice(value, gap);
  const order = includeOrder && step !== "" ? riskOrderAmounts(Number(capital), plan.position_cap_percent ?? NaN, plan.risk_budget_percent ?? NaN,
    plan.reference_price ?? NaN, plan.stop_loss ?? NaN, Number(step), feePercent === "" ? NaN : Number(feePercent), minimumFee === "" ? NaN : Number(minimumFee), slippagePercent === "" ? NaN : Number(slippagePercent)) : null;
  const targets = order && order.quantity > 0 ? [plan.take_profit_1, plan.take_profit_2].map(target =>
    riskTargetAmounts(order, target ?? NaN, Number(feePercent), Number(minimumFee), Number(slippagePercent))) : [];
  return <>{metadata}<details className="mt-2 text-xs">
    <summary className="cursor-pointer text-primary">止盈止损参考 · {currency}</summary>
    <div className="mt-2 space-y-1">
      <p>参考价 {price(plan.reference_price)} · ATR14 {price(plan.atr14)}</p>
      <p>保护价日K截至 {plan.history_as_of || "日期未提供"}</p>
      {plan.quote_as_of && <p>报价时点 {plan.quote_as_of}</p>}
      {plan.history_timing_status === "ok" && <p>日K与报价相差 {plan.history_lag_calendar_days} 个自然日</p>}
      {plan.history_timing_status !== "ok" && <p className="text-muted-foreground">报价与日K的时间差尚未核验。</p>}
      <p>止损 {price(plan.stop_loss)}（距离 {display(plan.stop_distance_percent)}%）</p>
      <p>目标一 {price(plan.take_profit_1)} · 目标二 {price(plan.take_profit_2)}</p>
      <p>支撑 {price(plan.support20)} · 阻力 {price(plan.resistance20)}</p>
      {plan.resistance_before_target && <p>阻力在第一目标之前，需先确认突破。</p>}
      <p>组合风险预算 {plan.risk_budget_percent}% · 示例仓位上限 {display(plan.position_cap_percent)}%</p>
      <p>移动保护距离 {price(plan.trailing_distance)}</p>
      <p className="text-muted-foreground">价格为分析参考，未按交易所最小报价单位取整。</p>
      <div className="my-2 rounded-md border p-2 space-y-2">
        <label htmlFor={inputId} className="block">组合资金（{currency}）</label>
        <input id={inputId} type="number" inputMode="decimal" min="0" step="any" value={capital}
          onChange={event => setCapital(event.target.value)} placeholder="输入同币种资金，查看情景"
          className="w-full rounded border bg-background px-2 py-1" aria-invalid={capital !== "" && !validCapital} />
        {capital !== "" && !validCapital && <p role="alert">请输入大于0的有限资金金额。</p>}
        {amounts && <div aria-live="polite">
          <p>参考持仓金额上限 {money(amounts.positionAmount)} {currency}</p>
          <p>按止损价估算损失 {money(amounts.stopLossAmount)} {currency}</p>
        </div>}
        <label className="flex items-center gap-2"><input type="checkbox" checked={includeOrder} onChange={event => setIncludeOrder(event.target.checked)} />计算股数与费用情景</label>
        {includeOrder && <div className="space-y-2 rounded border p-2">
          <label htmlFor={`${inputId}-step`} className="block">买入股数步长（股）</label>
          <input id={`${inputId}-step`} type="number" min="1" step="1" value={step} onChange={event => setStep(event.target.value)} placeholder="填入该证券的步长" className="w-full rounded border bg-background px-2 py-1" />
          <label htmlFor={`${inputId}-rate`} className="block">单边比例费用（%）</label>
          <input id={`${inputId}-rate`} type="number" min="0" max="100" step="any" value={feePercent} onChange={event => setFeePercent(event.target.value)} className="w-full rounded border bg-background px-2 py-1" />
          <label htmlFor={`${inputId}-minimum`} className="block">每笔最低费用（{currency}）</label>
          <input id={`${inputId}-minimum`} type="number" min="0" step="any" value={minimumFee} onChange={event => setMinimumFee(event.target.value)} className="w-full rounded border bg-background px-2 py-1" />
          <label htmlFor={`${inputId}-slippage`} className="block">单边不利滑点（%）</label>
          <input id={`${inputId}-slippage`} type="number" min="0" max="99.99" step="any" value={slippagePercent} onChange={event => setSlippagePercent(event.target.value)} className="w-full rounded border bg-background px-2 py-1" />
          {step === "" && <p>请填入股数步长，未默认套用整手规则。</p>}
          {validCapital && step !== "" && !order && <p role="alert">请核对有效价格、正整数步长、非负费用及0至小于100%的滑点。</p>}
          {order && <div aria-live="polite" className="space-y-1">
            {order.quantity > 0 ? <><p>情景股数上限 {order.quantity.toLocaleString()} 股</p><p>{Number(slippagePercent) > 0 ? "买入资金含费用与滑点" : "买入资金含费用"} {money(order.cashRequired)} {currency}</p><p>{Number(slippagePercent) > 0 ? "止损价差、滑点与买卖费用" : "止损价差加买卖费用"} {money(order.totalStopLossAmount)} {currency}</p><p>费用假设：买入 {money(order.entryFee)} · 止损卖出 {money(order.exitFee)} {currency}</p>{Number(slippagePercent) > 0 && <><p>滑点情景价格：买入 {price(order.entryPrice)} · 止损卖出 {price(order.stopExecutionPrice)}</p><p>两侧滑点增加损失 {money(order.slippageAmount)} {currency}</p></>}</> : <p>当前资金、风险预算与费用不足以满足一个股数步长。</p>}
          </div>}
          {!!targets.length && <div aria-live="polite" className="space-y-1">
            {targets.map((target, i) => target && <div key={i}><p>目标{i === 0 ? "一" : "二"}情景净收益 {money(target.netProfitAmount)} {currency} · 净盈亏比 {display(target.rewardRiskRatio)}R</p><p className="text-muted-foreground">情景卖出价 {price(target.executionPrice)} · 卖出费用 {money(target.exitFee)} {currency} · 净资金收益率 {display(target.netReturnPercent)}%</p></div>)}
            {targets[0]?.breakEvenTargetPrice != null && <p>含费用与滑点的保本目标价 {price(targets[0].breakEvenTargetPrice)}</p>}
            {targets.some(target => target && target.netProfitAmount <= 0) && <p className="text-amber-700">目标价的涨幅不足以覆盖当前费用与滑点，情景净收益不为正。</p>}
            {targets.some(target => !target) && <p>部分目标收益无法计算，请核对目标价及情景输入。</p>}
            <p className="text-muted-foreground">净收益扣除买入与卖出费用、两侧滑点，净盈亏比以同一股数的含成本止损损失为分母。目标一、目标二分别假设一次卖出全部情景股数，收益不相加。</p>
          </div>}
          <p className="text-muted-foreground">股数同时满足含买入费用的仓位上限与含买卖费用、两侧滑点的止损预算。买入价上浮、卖出价下浮所填滑点比例，费用按情景成交金额与最低费用取较大值；未模拟额外税费、公司行动或成交可用性。</p>
        </div>}
        <p className="text-muted-foreground">资金按所示币种输入，不作汇率换算。上方参考持仓金额未扣费用或取整；股数情景按填写的步长和费用计算。跳空时损失可能更大。</p>
      </div>
      {plan.basis?.map(text => <p key={text}>{text}</p>)}
      {plan.limitations?.map(text => <p key={text} className="text-muted-foreground">{text}</p>)}
    </div>
  </details></>;
}

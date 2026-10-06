"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ReviewedHkFactorsPanel } from "@/components/reviewed-hk-factors-panel";
import { CenteredRiskGridPanel } from "@/components/centered-risk-grid-panel";
import { RiskBudgetResearchPanel } from "@/components/risk-budget-research-panel";

type Metrics = { net_return: number; max_drawdown: number; days: number; average_exposure?: number; risk_unverifiable_days?: number; risk_missing_entries?: number; missing_quote_days?: number };
type Stress = Metrics & { one_way_cost: number };
type JointReport = { status: string; message?: string; applied?: boolean; market?: string; formula_mode?: string; optimization_method?: string; source_scoring_input_fingerprint?: string; fundamental_mode?: string; available_count?: number; folds?: Array<{ train_start: string; train_end: string; test_start: string; test_end: string; candidate_weights: Record<string, number>; candidate_risk_parameters: { atr_multiple: number; target_r: number } | null; selection_status: string; training_trials: unknown[] }>; out_of_sample?: { joint_risk_tuned: Metrics }; cost_stress?: Stress[]; sequential_comparison?: { out_of_sample: Metrics; cost_stress: Stress[] } };
const percent = (value?: number) => typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "—";

export function FormulaJointPanel({ market, mode, sourceFingerprint }: { market: "CN" | "HK" | "US"; mode: "balanced" | "conservative" | "aggressive"; sourceFingerprint: string }) {
  const [open, setOpen] = useState(false);
  const { data, isPending, isError, refetch } = useQuery<JointReport>({
    queryKey: ["formula-joint", market, mode, sourceFingerprint], enabled: open, retry: false, staleTime: 60000,
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ market, mode, source_fingerprint: sourceFingerprint });
      const response = await fetch(`/api/formula-ranking/joint-backtest?${params}`, { signal });
      if (!response.ok) throw new Error("联合对照不可用");
      const result: JointReport = (await response.json()).result;
      if (!result || !["research_only", "not_run"].includes(result.status)) throw new Error("报告不完整");
      if (result.status === "research_only" && (result.market !== market || result.formula_mode !== mode || result.source_scoring_input_fingerprint !== sourceFingerprint || result.optimization_method !== "joint-protected-grid-v1" || result.applied !== false || !result.out_of_sample?.joint_risk_tuned || !result.sequential_comparison?.out_of_sample)) throw new Error("报告来源不匹配");
      return result;
    },
  });
  const joint = !isError ? data?.out_of_sample?.joint_risk_tuned : undefined;
  const sequential = !isError ? data?.sequential_comparison : undefined;
  const rows = joint && sequential ? [
    { method: "两步选择", cost: .0015, value: sequential.out_of_sample },
    { method: "联合选择", cost: .0015, value: joint },
    ...(data?.cost_stress || []).flatMap(stress => {
      const original = sequential.cost_stress.find(row => row.one_way_cost === stress.one_way_cost);
      return [...(original ? [{ method: "两步选择", cost: stress.one_way_cost, value: original }] : []), { method: "联合选择", cost: stress.one_way_cost, value: stress }];
    }),
  ] : [];
  return <div className="space-y-3">
    {market === "HK" && <ReviewedHkFactorsPanel key={`${mode}:${sourceFingerprint}`} mode={mode} sourceFingerprint={sourceFingerprint} />}
    <Button size="sm" variant="outline" onClick={() => setOpen(!open)}>{open ? "关闭联合对照" : "比较联合调优实验"}</Button>
    {open && <section aria-label="联合调优对照" className="space-y-3 rounded-lg border p-3 text-sm">
      <p className="font-medium">因子权重与止盈止损联合调优对照</p>
      {isPending && <p role="status">正在加载联合对照…</p>}
      {isError && <div className="space-y-2"><p role="status">联合调优对照暂不可用，未展示其他样本的结果。</p><Button size="sm" variant="outline" onClick={() => void refetch()}>重试联合对照</Button></div>}
      {!isError && data?.status === "not_run" && <p role="status">{data.message}</p>}
      {!!rows.length && <>
        <p className="text-xs text-muted-foreground">同一冻结样本 {data?.available_count} 只、{data?.folds?.length} 个滚动窗口。两步选择先选权重，再选保护参数；联合选择以训练保护策略净收益减0.5倍最大回撤比较权重与ATR／R组合。</p>
        <p className="text-amber-700">联合搜索扩大了比较数量，历史结果没有一致改善，参数未应用到实时选股。</p>
        {data?.fundamental_mode === "cn-reference" && <p className="text-amber-700">A股接口历史估值的财务修订时间未验证，此对照不是严格时点财务验证。</p>}
        <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b"><th className="p-2">单边费用与滑点</th><th className="p-2">选参方式</th><th className="p-2">验证净收益</th><th className="p-2">最大回撤</th><th className="p-2">平均股票仓位</th><th className="p-2">保护缺失日／入场缺失次</th></tr></thead><tbody>{rows.map(row => <tr key={`${row.method}:${row.cost}`} className="border-b"><td className="p-2">{percent(row.cost)}</td><td className="p-2">{row.method}</td><td className="p-2 tabular-nums">{percent(row.value.net_return)}</td><td className="p-2 tabular-nums">{percent(row.value.max_drawdown)}</td><td className="p-2 tabular-nums">{percent(row.value.average_exposure)}</td><td className="p-2">{row.value.risk_unverifiable_days ?? "—"} / {row.value.risk_missing_entries ?? "—"}</td></tr>)}</tbody></table></div>
        {rows.some(row => row.value.average_exposure === 0) && <p className="text-amber-700">部分情景没有股票持仓，零收益不能视为策略有效。</p>}
        {rows.some(row => (row.value.missing_quote_days ?? 0) > 0 || (row.value.risk_unverifiable_days ?? 0) > 0 || (row.value.risk_missing_entries ?? 0) > 0) && <p className="text-amber-700">部分对照路径存在报价或保护缺口，不能据此认定参数有效。</p>}
        <p className="text-xs text-muted-foreground">已查看的历史验证不属于新的未来留出证据；样本和公司行动限制沿用原实验。各窗口资金重置，费用会改变可买股数与持仓路径，不能视为等仓位效果。</p>
        <details><summary className="cursor-pointer">查看联合训练窗口与参数</summary><div className="mt-2 space-y-2">{data?.folds?.map(fold => <p key={fold.test_start}>训练 {fold.train_start}—{fold.train_end}；验证 {fold.test_start}—{fold.test_end}；比较 {fold.training_trials.length} 个组合。{fold.selection_status.startsWith("retained_default_") ? "没有活跃且完整的合格组合，沿用默认参数。" : "训练选定组合："}{fold.candidate_risk_parameters && `${fold.candidate_risk_parameters.atr_multiple} × ATR，${fold.candidate_risk_parameters.target_r}R；`}{Object.entries(fold.candidate_weights).map(([name, weight]) => `${name} ${(weight * 100).toFixed(0)}%`).join(" / ")}</p>)}</div></details>
        <CenteredRiskGridPanel key={`${market}:${mode}:${sourceFingerprint}`} market={market} mode={mode} sourceFingerprint={sourceFingerprint} />
        <RiskBudgetResearchPanel key={`budget:${market}:${mode}:${sourceFingerprint}`} market={market} mode={mode} sourceFingerprint={sourceFingerprint} />
      </>}
    </section>}
  </div>;
}

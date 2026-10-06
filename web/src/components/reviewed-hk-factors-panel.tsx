"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";

type Metrics = { net_return: number; max_drawdown: number; days: number; average_exposure: number };
type Stress = Metrics & { one_way_cost: number };
type Arm = { metrics: Metrics; cost_stress: Stress[] };
type Summary = {
  status: "research_only" | "not_run"; message?: string; applied?: boolean;
  market?: string; formula_mode?: string; source_scoring_input_fingerprint?: string;
  universe_count: number; fold_count: number; train_days: number; test_days: number;
  pb_available: boolean; initial_capital_hkd: number; minimum_fee_hkd: number; entry_lot_size: null;
  grid_pairs_per_fold: number; net_return_difference: number;
  issuers: { ticker: string; name: string; train_counts: number[]; test_counts: number[] }[];
  control: Arm; reviewed: Arm;
};
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const percent = (value: number) => `${(value * 100).toFixed(2)}%`;
function validMetrics(value: Metrics) {
  return value && finite(value.net_return) && finite(value.max_drawdown) && value.max_drawdown >= 0
    && value.days === 320 && finite(value.average_exposure) && value.average_exposure >= 0 && value.average_exposure <= 1;
}
function validArm(value: Arm) {
  return value && validMetrics(value.metrics) && Array.isArray(value.cost_stress) && value.cost_stress.length === 2
    && value.cost_stress.every((row, index) => row.one_way_cost === [.003, .005][index] && validMetrics(row));
}
function validSummary(value: Summary, mode: string, fingerprint: string) {
  return value.market === "HK" && value.formula_mode === mode && value.source_scoring_input_fingerprint === fingerprint
    && value.applied === false && value.universe_count === 18 && value.fold_count === 4
    && value.train_days === 240 && value.test_days === 80 && value.pb_available === false && value.entry_lot_size === null
    && finite(value.initial_capital_hkd) && value.initial_capital_hkd > 0 && finite(value.minimum_fee_hkd) && value.minimum_fee_hkd >= 0
    && value.grid_pairs_per_fold === (mode === "conservative" ? 80 : 96)
    && Array.isArray(value.issuers) && value.issuers.length === 2
    && value.issuers.every((issuer, index) => issuer.ticker === ["hk00001", "hk00388"][index] && typeof issuer.name === "string"
      && [issuer.train_counts, issuer.test_counts].every((counts, kind) => Array.isArray(counts) && counts.length === 4
        && counts.every(count => Number.isInteger(count) && count >= 0 && count <= (kind === 0 ? 240 : 80))))
    && validArm(value.control) && validArm(value.reviewed) && finite(value.net_return_difference)
    && Math.abs(value.net_return_difference - (value.reviewed.metrics.net_return - value.control.metrics.net_return)) < 1e-12;
}

export function ReviewedHkFactorsPanel({ mode, sourceFingerprint }: { mode: "balanced" | "conservative" | "aggressive"; sourceFingerprint: string }) {
  const [open, setOpen] = useState(false);
  const { data, isPending, isError, refetch } = useQuery<Summary>({
    queryKey: ["reviewed-hk-factors", mode, sourceFingerprint], enabled: open, retry: false, staleTime: 60000,
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ market: "HK", mode, source_fingerprint: sourceFingerprint });
      const response = await fetch(`/api/formula-ranking/reviewed-hk-backtest?${params}`, { signal });
      if (!response.ok) throw new Error("财务因子实验不可用");
      const result: Summary = (await response.json()).result;
      if (!result || !["research_only", "not_run"].includes(result.status)
        || (result.status === "research_only" && !validSummary(result, mode, sourceFingerprint))) throw new Error("财务因子实验来源不匹配");
      return result;
    },
  });
  const report = !isError && data?.status === "research_only" ? data : undefined;
  const rows = report ? [0.0015, .003, .005].flatMap((cost, index) => [
    { method: "同范围搜索对照", cost, metrics: index === 0 ? report.control.metrics : report.control.cost_stress[index - 1] },
    { method: "加入财务因子", cost, metrics: index === 0 ? report.reviewed.metrics : report.reviewed.cost_stress[index - 1] },
  ]) : [];
  return <div className="space-y-3">
    <Button size="sm" variant="outline" onClick={() => setOpen(!open)}>{open ? "关闭港股财务因子实验" : "查看港股财务因子实验"}</Button>
    {open && <section aria-label="港股财务因子实验" className="space-y-3 rounded-lg border p-3 text-sm">
      <p className="font-medium">经公告核验的 PE 与市值因子对照</p>
      {isPending && <p role="status">正在加载财务因子实验…</p>}
      {isError && <div className="space-y-2"><p role="status">财务因子实验暂不可用，请重试。</p><Button size="sm" variant="outline" onClick={() => void refetch()}>重试财务因子实验</Button></div>}
      {!isError && data?.status === "not_run" && <p role="status">{data.message || "当前样本尚未归档港股财务因子对照。"}</p>}
      {report && <>
        <p>财务因子覆盖 {report.issuers.length} / {report.universe_count} 只股票，PB 数据仍缺失。</p>
        <p className="text-xs text-muted-foreground">两组使用同一冻结样本和搜索范围，每个窗口比较 {report.grid_pairs_per_fold} 个组合；{report.fold_count} 个滚动窗口各训练 {report.train_days} 日、验证 {report.test_days} 日。加入财务因子的组仅对已核验公司使用当时可获得的 PE 与市值。</p>
        <p className="text-amber-700">历史结果未支持推广新参数，尚未应用到实时选股。</p>
        <div className="overflow-x-auto"><table aria-label="财务因子收益对照" className="w-full text-left text-xs">
          <thead><tr className="border-b">{["单边费用与滑点", "实验组", "验证净收益", "最大回撤", "平均股票仓位"].map(title => <th className="p-2" key={title}>{title}</th>)}</tr></thead>
          <tbody>{rows.map(row => <tr className="border-b" key={`${row.method}:${row.cost}`}><td className="p-2">{percent(row.cost)}</td><td className="p-2">{row.method}</td><td className="p-2 tabular-nums">{percent(row.metrics.net_return)}</td><td className="p-2 tabular-nums">{percent(row.metrics.max_drawdown)}</td><td className="p-2 tabular-nums">{percent(row.metrics.average_exposure)}</td></tr>)}</tbody>
        </table></div>
        <div className="overflow-x-auto"><table aria-label="财务因子样本覆盖" className="w-full text-left text-xs"><thead><tr className="border-b"><th className="p-2">公司</th><th className="p-2">各窗口训练覆盖 / 240 日</th><th className="p-2">各窗口验证覆盖 / 80 日</th></tr></thead><tbody>{report.issuers.map(issuer => <tr className="border-b" key={issuer.ticker}><td className="p-2">{issuer.name}（{issuer.ticker}）</td><td className="p-2">{issuer.train_counts.join(" / ")}</td><td className="p-2">{issuer.test_counts.join(" / ")}</td></tr>)}</tbody></table></div>
        <p className="text-xs text-muted-foreground">各窗口初始资金 {report.initial_capital_hkd.toLocaleString("zh-CN")} HKD、最低费用 {report.minimum_fee_hkd} HKD。历史每手股数未验证，采用可分割股数计算；窗口资金重置。当前样本与公司行动覆盖有限，已查看的历史验证不能作为新的未来留出证据。</p>
      </>}
    </section>}
  </div>;
}

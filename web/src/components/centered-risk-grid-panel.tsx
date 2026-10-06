"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";

type Metrics = { net_return: number; max_drawdown: number; days: number; average_exposure: number };
type Arm = { metrics: Metrics; cost_stress: (Metrics & { one_way_cost: number })[]; inactive_folds: number };
type Report = {
  status: string; message?: string; applied?: boolean; market?: string; formula_mode?: string;
  source_scoring_input_fingerprint?: string; universe_count: number; fold_count: number;
  train_days: number; test_days: number; original_risk_pairs: number; expanded_risk_pairs: number;
  fundamental_mode: string; net_return_difference: number; control: Arm; expanded: Arm;
};
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const percent = (value: number) => `${(value * 100).toFixed(2)}%`;
function validArm(arm: Arm, folds: number) {
  const metrics = (v: Metrics) => v && finite(v.net_return) && finite(v.max_drawdown) && v.max_drawdown >= 0
    && v.days === folds * 80 && finite(v.average_exposure) && v.average_exposure >= 0 && v.average_exposure <= 1;
  return arm && metrics(arm.metrics) && Number.isInteger(arm.inactive_folds) && arm.inactive_folds >= 0 && arm.inactive_folds <= folds
    && Array.isArray(arm.cost_stress) && arm.cost_stress.length === 2
    && arm.cost_stress.every((v, i) => v && v.one_way_cost === [.003, .005][i] && metrics(v));
}
function validReport(r: Report, market: "CN" | "HK" | "US", mode: string, fingerprint: string) {
  const expected = { CN: { count: 56, folds: 7, fundamentals: "cn-reference" }, HK: { count: 18, folds: 4, fundamentals: "price" }, US: { count: 57, folds: 5, fundamentals: "sec-pit" } }[market];
  return r.market === market && r.formula_mode === mode && r.source_scoring_input_fingerprint === fingerprint
    && r.applied === false && r.universe_count === expected.count && r.fold_count === expected.folds && r.fundamental_mode === expected.fundamentals
    && r.train_days === 240 && r.test_days === 80 && r.original_risk_pairs === 4 && r.expanded_risk_pairs === 9
    && validArm(r.control, expected.folds) && validArm(r.expanded, expected.folds) && finite(r.net_return_difference)
    && Math.abs(r.net_return_difference - (r.expanded.metrics.net_return - r.control.metrics.net_return)) < 1e-12;
}

export function CenteredRiskGridPanel({ market, mode, sourceFingerprint }: { market: "CN" | "HK" | "US"; mode: "balanced" | "conservative" | "aggressive"; sourceFingerprint: string }) {
  const [open, setOpen] = useState(false);
  const { data, isPending, isError, refetch } = useQuery<Report>({
    queryKey: ["centered-risk-grid", market, mode, sourceFingerprint], enabled: open, retry: false, staleTime: 60000,
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ market, mode, source_fingerprint: sourceFingerprint });
      const response = await fetch(`/api/formula-ranking/centered-risk-backtest?${params}`, { signal });
      if (!response.ok) throw new Error("扩展风控网格不可用");
      const r: Report = (await response.json()).result;
      if (!r || !["research_only", "not_run"].includes(r.status)
        || (r.message !== undefined && typeof r.message !== "string")
        || (r.status === "research_only" && !validReport(r, market, mode, sourceFingerprint))) throw new Error("实验来源不匹配");
      return r;
    },
  });
  const report = !isError && data?.status === "research_only" ? data : undefined;
  const rows = report ? [.0015, .003, .005].flatMap((cost, i) => [
    { method: "原四组", cost, arm: report.control, metrics: i === 0 ? report.control.metrics : report.control.cost_stress[i - 1] },
    { method: "扩展九组", cost, arm: report.expanded, metrics: i === 0 ? report.expanded.metrics : report.expanded.cost_stress[i - 1] },
  ]) : [];
  return <div className="space-y-3">
    <Button size="sm" variant="outline" onClick={() => setOpen(!open)}>{open ? "关闭扩展风控网格" : "比较扩展风控网格"}</Button>
    {open && <section aria-label="扩展风控网格对照" className="space-y-3 rounded-lg border p-3 text-sm">
      {isPending && <p role="status">正在加载扩展风控网格…</p>}
      {isError && <><p role="status">扩展风控网格暂不可用，请重试。</p><Button size="sm" variant="outline" onClick={() => void refetch()}>重试扩展风控网格</Button></>}
      {!isError && data?.status === "not_run" && <p role="status">{data.message || "当前样本尚未归档扩展风控网格实验"}</p>}
      {report && <>
        <p className="font-medium">止盈止损网格扩展对照</p>
        <p>同一冻结样本 {report.universe_count} 只、{report.fold_count} 个滚动窗口，各训练 240 日、验证 80 日。ATR 倍数与止盈 R 倍数均从 1.5、2、2.5 中选择，扩展为九组；因子权重搜索范围相同。</p>
        <p className="text-amber-700">历史实验未呈现一致改善，参数尚未应用到实时选股。</p>
        {report.fundamental_mode === "cn-reference" && <p className="text-amber-700">A股历史财务修订时间未验证，此实验不是严格时点财务验证。</p>}
        <div className="overflow-x-auto"><table aria-label="风控网格收益对照" className="w-full text-left text-xs">
          <thead><tr>{["单边费用与滑点", "实验组", "验证净收益", "最大回撤", "平均股票仓位", "无活跃候选窗口"].map(t => <th className="p-2" key={t}>{t}</th>)}</tr></thead>
          <tbody>{rows.map(row => <tr className="border-b" key={`${row.method}:${row.cost}`}><td className="p-2">{percent(row.cost)}</td><td className="p-2">{row.method}</td><td className="p-2">{percent(row.metrics.net_return)}</td><td className="p-2">{percent(row.metrics.max_drawdown)}</td><td className="p-2">{percent(row.metrics.average_exposure)}</td><td className="p-2">{row.arm.inactive_folds} / {report.fold_count}</td></tr>)}</tbody>
        </table></div>
        {(report.control.inactive_folds > 0 || report.expanded.inactive_folds > 0) && <p className="text-amber-700">存在无活跃候选窗口，现金零收益不能视为策略有效。</p>}
        <p className="text-xs text-muted-foreground">收益为各验证窗口累计结果，非年化收益。压力情景沿用训练选定参数；费用会改变可买股数和持仓路径。扩大搜索增加了选择偏差，已查看的历史不构成未来留出证据；窗口资金重置，样本与公司行动覆盖限制沿用原实验。</p>
      </>}
    </section>}
  </div>;
}

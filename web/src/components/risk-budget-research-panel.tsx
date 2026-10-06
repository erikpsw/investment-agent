"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";

type Metrics = { net_return: number; max_drawdown: number; days: number; average_exposure: number };
type Arm = { metrics: Metrics; cost_stress: (Metrics & { one_way_cost: number })[] };
type Fold = { train_start: string; train_end: string; test_start: string; test_end: string; risk_budget_percent: number; budget_selection_status: string };
type Report = { status: string; message?: string; applied?: boolean; market: string; formula_mode: string;
  source_scoring_input_fingerprint: string; optimization_method: string; fundamental_mode: string;
  universe_count: number; fold_count: number; train_days: number; test_days: number; default_risk_budget_percent: number;
  risk_budget_grid: number[]; folds: Fold[]; control: Arm; budget_tuned: Arm };
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const percent = (v: number) => `${(v * 100).toFixed(2)}%`;
const canonicalDate = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)
  && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;
function validArm(a: Arm, folds: number) {
  const metrics = (v: Metrics) => v && finite(v.net_return) && finite(v.max_drawdown) && v.max_drawdown >= 0
    && v.days === folds * 80 && finite(v.average_exposure) && v.average_exposure >= 0 && v.average_exposure <= 1;
  return a && metrics(a.metrics) && Array.isArray(a.cost_stress) && a.cost_stress.length === 2
    && a.cost_stress.every((v, i) => v && v.one_way_cost === [.003, .005][i] && metrics(v));
}
function validReport(r: Report, market: "CN" | "HK" | "US", mode: string, fingerprint: string) {
  const expected = { CN: { count: 56, folds: 7, fundamentals: "cn-reference" }, HK: { count: 18, folds: 4, fundamentals: "price" }, US: { count: 57, folds: 5, fundamentals: "sec-pit" } }[market];
  const grid = mode === "conservative" ? [.5, .25, 1] : [1, .5, 1.5];
  return r.applied === false && r.market === market && r.formula_mode === mode && r.source_scoring_input_fingerprint === fingerprint
    && r.optimization_method === "centered-then-budget-v1" && r.fundamental_mode === expected.fundamentals
    && r.universe_count === expected.count && r.fold_count === expected.folds && r.train_days === 240 && r.test_days === 80
    && r.default_risk_budget_percent === grid[0] && Array.isArray(r.risk_budget_grid) && r.risk_budget_grid.length === 3
    && r.risk_budget_grid.every((v, i) => v === grid[i]) && Array.isArray(r.folds) && r.folds.length === expected.folds
    && r.folds.every((f, i) => f && [f.train_start, f.train_end, f.test_start, f.test_end].every(canonicalDate)
      && f.train_start < f.train_end && f.train_end < f.test_start && f.test_start < f.test_end
      && (i === 0 || r.folds[i - 1].test_end < f.test_start) && grid.includes(f.risk_budget_percent)
      && ["selected_from_complete_budget_candidates", "retained_default_due_to_inactive_candidates", "retained_default_due_to_incomplete_paths"].includes(f.budget_selection_status)
      && (!f.budget_selection_status.startsWith("retained_default_") || f.risk_budget_percent === grid[0]))
    && validArm(r.control, expected.folds) && validArm(r.budget_tuned, expected.folds);
}

export function RiskBudgetResearchPanel({ market, mode, sourceFingerprint }: { market: "CN" | "HK" | "US"; mode: "balanced" | "conservative" | "aggressive"; sourceFingerprint: string }) {
  const [open, setOpen] = useState(false);
  const { data, isPending, isError, refetch } = useQuery<Report>({
    queryKey: ["risk-budget-research", market, mode, sourceFingerprint], enabled: open, retry: false, staleTime: 60000,
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ market, mode, source_fingerprint: sourceFingerprint });
      const response = await fetch(`/api/formula-ranking/risk-budget-backtest?${params}`, { signal });
      if (!response.ok) throw new Error("风险预算实验不可用");
      const r: Report = (await response.json()).result;
      if (!r || !["research_only", "not_run"].includes(r.status) || (r.message !== undefined && typeof r.message !== "string")
        || (r.status === "research_only" && !validReport(r, market, mode, sourceFingerprint))) throw new Error("实验来源不匹配");
      return r;
    },
  });
  const report = !isError && data?.status === "research_only" ? data : undefined;
  const rows = report ? [.0015, .003, .005].flatMap((cost, i) => [
    { method: "模式默认预算", cost, metrics: i === 0 ? report.control.metrics : report.control.cost_stress[i - 1] },
    { method: "训练预算调优", cost, metrics: i === 0 ? report.budget_tuned.metrics : report.budget_tuned.cost_stress[i - 1] },
  ]) : [];
  return <div className="space-y-3">
    <Button size="sm" variant="outline" onClick={() => setOpen(!open)}>{open ? "关闭风险预算实验" : "比较风险预算实验"}</Button>
    {open && <section aria-label="风险预算实验" className="space-y-3 rounded-lg border p-3 text-sm">
      {isPending && <p role="status">正在加载风险预算实验…</p>}
      {isError && <><p role="status">风险预算实验暂不可用，请重试。</p><Button size="sm" variant="outline" onClick={() => void refetch()}>重试风险预算实验</Button></>}
      {!isError && data?.status === "not_run" && <p role="status">{data.message || "当前样本尚未归档风险预算实验"}</p>}
      {report && <>
        <p className="font-medium">固定模式预算与训练期预算调优对照</p>
        <p>样本 {report.universe_count} 只、{report.fold_count} 个窗口，每窗训练 240 日、验证 80 日。默认预算 {report.default_risk_budget_percent}%；训练候选 {report.risk_budget_grid.map(v => `${v}%`).join(" / ")}。保留此前训练选出的权重、ATR 和止盈倍数，再在训练期选择预算；这不是全部参数的联合最优解。</p>
        <p className="text-amber-700">历史预算调优没有一致改善，实时预算保持原值。</p>
        {report.budget_tuned.metrics.max_drawdown > report.control.metrics.max_drawdown && <p className="text-amber-700">本实验预算调优后的最大回撤更大，收益变化需要结合仓位变化理解。</p>}
        {report.fundamental_mode === "cn-reference" && <p className="text-amber-700">A股历史财务修订时间未验证，此实验不是严格时点财务验证。</p>}
        <div className="overflow-x-auto"><table aria-label="风险预算收益对照" className="w-full text-left text-xs"><thead><tr>{["单边费用与滑点", "实验组", "验证净收益", "最大回撤", "平均股票仓位"].map(t => <th className="p-2" key={t}>{t}</th>)}</tr></thead>
          <tbody>{rows.map(row => <tr className="border-b" key={`${row.method}:${row.cost}`}><td className="p-2">{percent(row.cost)}</td><td className="p-2">{row.method}</td><td className="p-2">{percent(row.metrics.net_return)}</td><td className="p-2">{percent(row.metrics.max_drawdown)}</td><td className="p-2">{percent(row.metrics.average_exposure)}</td></tr>)}</tbody>
        </table></div>
        {report.folds.some(f => f.budget_selection_status === "retained_default_due_to_inactive_candidates") && <p className="text-amber-700">存在无活跃候选窗口，现金零收益不能视为策略有效。</p>}
        <details><summary className="cursor-pointer">查看各训练窗口选择的预算</summary><div className="mt-2 space-y-2">{report.folds.map(f => <div key={f.test_start}><p>验证 {f.test_start}—{f.test_end}；训练预算 {f.risk_budget_percent}%。</p><p className="text-xs text-muted-foreground">训练 {f.train_start}—{f.train_end}。{f.budget_selection_status.startsWith("retained_default_") ? "没有活跃且完整的合格候选，沿用模式默认预算。" : "按训练净收益减0.5倍最大回撤选择，同分优先默认预算。"}</p></div>)}</div></details>
        <p className="text-xs text-muted-foreground">累计验证收益非年化，各窗口资金重置；费用压力沿用训练选择。预算改变股数、现金和费用路径，不能视为等暴露归因。样本与公司行动覆盖有限，已查看历史不构成未来留出证据。</p>
      </>}
    </section>}
  </div>;
}

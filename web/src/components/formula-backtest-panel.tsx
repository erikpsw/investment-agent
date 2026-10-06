"use client";
import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { FormulaHoldoutPanel } from "@/components/formula-holdout-panel";
import { FormulaJointPanel } from "@/components/formula-joint-panel";
import { UsCoverResearchPanel } from "@/components/us-cover-research-panel";
import { validateBacktestReport } from "@/lib/backtest-validation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type VolumeCoverage = { status: string; available: number; observations: number; basis: string; status_counts: Record<string, number> };
const volumeReasons: Record<string, string> = { invalid_volume: "成交量缺失或异常", unverified_share_scale: "调整比例未验证", share_scale_changed: "调整比例变化（含舍入差异）", source_changed: "行情来源变化", quote_gap: "报价间隔超过7日", invalid_dates: "日期异常", invalid_ratio: "成交量倍数异常", insufficient_history: "历史不足" };

type Metrics = { risk_unverifiable_days?: number | null; risk_missing_entries?: number | null; risk_evaluation_status?: string; missing_quote_days?: number; stale_quote_days?: number; max_quote_age_calendar_days?: number; average_exposure?: number; net_return: number; max_drawdown: number; sharpe_zero_rate: number; days: number; equity_curve: { date: string; equity: number }[] };
type Report = { scoring_input_fingerprint?: string; formula_mode?: "balanced" | "conservative" | "aggressive"; mode_risk_defaults?: { risk_budget_percent: number; position_cap_percent: number; atr_multiple: number }; parameter_grid?: Record<string, number>[]; risk_protection_policy_version?: string; risk_availability_as_of?: string; risk_availability_policy?: string; risk_availability_training_universe?: string[]; execution_lot_coverage?: { available: number; observations: number; basis: string }; execution_risk_costs_included?: boolean; execution_scenario?: { market: "CN" | "HK" | "US"; initial_capital: number; minimum_fee: number; entry_lot_size: number | null; lot_ledger?: Record<string, unknown> }; volume_weight_tuning?: { enabled: boolean; weights: number[]; policy: string }; volume_reference_coverage?: VolumeCoverage; selection_quality_policy?: string; fundamental_coverage?: { observations: number; pe_observations: number; pb_observations: number; cap_observations: number; missing_ledgers: string[]; basis: string; availability: string }; fundamental_mode?: string; download_failures?: Array<{ ticker: string }>; cost_stress?: Array<Metrics & { one_way_cost: number; strategy: string }>; quality_failures?: Array<{ ticker: string; reason: string }>; status: string; applied: boolean; message?: string; formula_version?: string; formula_scope?: string; source?: string; available_count?: number; requested_count?: number; selection_method?: string; generated_at?: string; limitations?: string[]; folds?: { weight_selection_status?: string; risk_selection_status?: string; train_start: string; train_end: string; test_start: string; test_end: string; candidate_risk_parameters?: { atr_multiple: number; target_r: number }; candidate_weights: Record<string, number> }[]; out_of_sample?: Record<"candidate" | "baseline" | "benchmark", Metrics> & { protected?: Metrics; risk_tuned?: Metrics; capped_control?: Metrics } };
const names = { baseline: "原权重", candidate: "滚动调优", benchmark: "样本等权", protected: "止盈止损＋限仓", risk_tuned: "滚动调优止盈止损", capped_control: "共享限仓规则对照" };

export function FormulaBacktestPanel({ market: rankingMarket = "CN", rankingMode = "balanced" }: { market?: "CN" | "HK" | "US" | "all"; rankingMode?: "balanced" | "conservative" | "aggressive" }) {
  const [validationMarket, setValidationMarket] = useState<"CN" | "HK" | "US">("CN");
  const market = rankingMarket === "all" ? validationMarket : rankingMarket;
  const [historySource, setHistorySource] = useState<"default" | "baostock">("default");
  const [hkHistorySource, setHKHistorySource] = useState<"default" | "yahoo-hk">("default");
  const [includeCNReference, setIncludeCNReference] = useState(false);
  const [includeFundamentals, setIncludeFundamentals] = useState(false);
  const [includeVolume, setIncludeVolume] = useState(false);
  const [tuneVolumeWeight, setTuneVolumeWeight] = useState(false);
  const [includeExecution, setIncludeExecution] = useState(false);
  const [includeLotReference, setIncludeLotReference] = useState(false);
  const [universe, setUniverse] = useState<"snapshot" | "catalog">("snapshot");
  const [storedReport, setReport] = useState<{ key: string; value: Report } | null>(null);
  const requestKey = JSON.stringify([market, rankingMode, universe, includeFundamentals, historySource, includeCNReference, includeVolume, tuneVolumeWeight, hkHistorySource, includeExecution, includeLotReference]);
  const report = storedReport?.key === requestKey ? storedReport.value : null;
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);
  const loadCompletedExperiment = (reference = false) => {
    setUniverse(market === "US" ? "catalog" : "snapshot");
    setHistorySource(market === "CN" ? "baostock" : "default");
    setHKHistorySource(market === "HK" ? "yahoo-hk" : "default");
    setIncludeFundamentals(market === "US");
    setIncludeCNReference(market === "CN" && reference);
    setIncludeVolume(true);
    setTuneVolumeWeight(true);
    setIncludeExecution(true);
    setIncludeLotReference(false);
  };
  useEffect(() => {
    const controller = new AbortController();
    setReport(null); setError("");
    const params = new URLSearchParams({ market, mode: rankingMode, universe, execution_scenario: String(includeExecution), lot_reference: String(market === "HK" && includeExecution && includeLotReference), volume_reference: String(includeVolume), tune_volume_weight: String(includeVolume && tuneVolumeWeight), history_source: market === "CN" ? historySource : market === "HK" ? hkHistorySource : "default", fundamentals: market === "US" && includeFundamentals ? "sec-pit" : market === "CN" && historySource === "baostock" && includeCNReference ? "cn-reference" : "price" });
    void fetch(`/api/formula-ranking/backtest?${params}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("历史验证报告加载失败");
      const payload = await response.json();
      const validated = validateBacktestReport(payload.result, rankingMode) as Report;
      if (!controller.signal.aborted) setReport({ key: requestKey, value: validated });
    }).catch(() => { if (!controller.signal.aborted) setError("历史验证报告暂不可用"); });
    return () => controller.abort();
  }, [requestKey, market, rankingMode, universe, includeFundamentals, historySource, includeCNReference, includeVolume, tuneVolumeWeight, hkHistorySource, includeExecution, includeLotReference, retryCount]);
  const modeName = { balanced: "均衡", conservative: "稳健", aggressive: "进攻" }[rankingMode];
  const results = report?.out_of_sample;
  const lookup = new Map(results?.candidate.equity_curve.map(row => [row.date, row.equity]));
  const benchmark = new Map(results?.benchmark.equity_curve.map(row => [row.date, row.equity]));
  const protectedLookup = new Map(results?.protected?.equity_curve.map(row => [row.date, row.equity]));
  const riskLookup = new Map(results?.risk_tuned?.equity_curve.map(row => [row.date, row.equity]));
  const capLookup = new Map(results?.capped_control?.equity_curve.map(row => [row.date, row.equity]));
  const curve = results?.baseline.equity_curve.map(row => ({ date: row.date, baseline: row.equity, candidate: lookup.get(row.date), benchmark: benchmark.get(row.date), protected: protectedLookup.get(row.date), risk_tuned: riskLookup.get(row.date), capped_control: capLookup.get(row.date) })) || [];
  const resultKeys: Array<keyof typeof names> = ["baseline", "candidate", "benchmark"];
  if (results?.protected) resultKeys.push("protected");
  if (results?.risk_tuned) resultKeys.push("risk_tuned");
  if (results?.capped_control) resultKeys.push("capped_control");
  const defaultWeights = report?.folds?.filter(fold => fold.weight_selection_status?.startsWith("retained_default_")).length ?? 0;
  const defaultRisk = report?.folds?.filter(fold => fold.risk_selection_status?.startsWith("retained_default_")).length ?? 0;
  const costReversal = report?.cost_stress?.some(row => {
    const base = row.strategy === "risk_tuned" ? results?.risk_tuned : row.strategy === "candidate" ? results?.candidate : undefined;
    return base && base.days === row.days && base.net_return > 0 && row.net_return < 0;
  });
  return <Card><CardHeader><CardTitle>{market} 公式历史验证</CardTitle><CardDescription>用同一评分引擎做滚动验证，展示成本后的收益、逐日回撤和参数选择过程。</CardDescription></CardHeader><CardContent className="space-y-4"><p className="text-sm">实时评分模式：{modeName}。历史报告按相同模式独立加载。</p>{rankingMode !== "balanced" && <p className="text-xs text-muted-foreground">下方冻结协议属于原均衡研究模型，当前模式的未来留出协议尚未创建。</p>}<FormulaHoldoutPanel market={market} />
    {rankingMarket === "all" && <div className="space-y-2"><label className="flex items-center gap-2 text-sm">历史验证市场<select aria-label="历史验证市场" value={validationMarket} onChange={event => setValidationMarket(event.target.value as "CN" | "HK" | "US")} className="rounded-md border bg-background px-3 py-2"><option value="CN">A股</option><option value="HK">港股</option><option value="US">美股</option></select></label><p className="text-xs text-muted-foreground">三个市场的样本、币种与验证期间不同，分别展示报告。</p></div>}
    <div className="flex flex-wrap gap-2"><button type="button" onClick={() => loadCompletedExperiment()} className="rounded-md border px-3 py-2 text-sm hover:bg-muted">加载已完成基础实验</button>{market === "CN" && <button type="button" onClick={() => loadCompletedExperiment(true)} className="rounded-md border px-3 py-2 text-sm hover:bg-muted">加载已完成估值参考实验</button>}</div>
    <label className="flex items-center gap-2 text-sm">历史样本来源<select aria-label="历史样本来源" value={universe} onChange={event => setUniverse(event.target.value as "snapshot" | "catalog")} className="rounded-md border bg-background px-3 py-2"><option value="snapshot">行情候选样本</option><option value="catalog">证券目录较广抽样</option></select></label>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label="加入资金成交情景" checked={includeExecution} onChange={event => { setIncludeExecution(event.target.checked); if (!event.target.checked) setIncludeLotReference(false); }} />加入资金规模与最低费用情景</label>
    {market === "HK" && includeExecution && <label className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label="加入公告每手参考" checked={includeLotReference} onChange={event => setIncludeLotReference(event.target.checked)} />按公告短区间核验每手股数（未覆盖日期不买入）</label>}
    {report?.execution_lot_coverage && <div className="rounded-lg border p-3 text-sm"><p>公告每手参考覆盖 {report.execution_lot_coverage.available}/{report.execution_lot_coverage.observations} 个证券报价日</p><p className="text-xs text-muted-foreground">{report.execution_lot_coverage.basis}；覆盖为0时不计算优化收益，缺失日期拒绝买入，不回退小数股。</p></div>}
    {includeExecution && <p className="text-xs text-muted-foreground">资金与费用为研究假设。已归档A股BaoStock行情样本、美股SEC目录样本、港股Yahoo行情样本的量能权重调优组合；其他组合显示未验证。</p>}
    {report?.execution_scenario && <div className="space-y-1 rounded-lg border p-3 text-sm"><p>固定资金情景：{report.execution_scenario.initial_capital.toLocaleString()} {report.execution_scenario.market === "CN" ? "CNY" : report.execution_scenario.market === "HK" ? "HKD" : "USD"}；每笔最低费用 {report.execution_scenario.minimum_fee}。</p><p>{report.execution_scenario.lot_ledger ? "逐证券按披露与生效日期查询每手参考，未覆盖日期拒绝买入。" : report.execution_scenario.entry_lot_size == null ? "未加入整手门槛，允许小数股；尚缺逐证券历史每手股数。" : `买入按 ${report.execution_scenario.entry_lot_size} 股步长向下取整，原价缺失则不买入。`}</p>{report.execution_risk_costs_included && <p>止损预算已计入买卖费用。</p>}<p className="text-xs text-muted-foreground">仅约束入场股数，各窗口资金固定；拼接曲线不是连续实盘账户，尚未完整回放公司行动与碎股卖出。</p></div>}
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label="加入完成日量能研究" checked={includeVolume} onChange={event => { setIncludeVolume(event.target.checked); if (!event.target.checked) setTuneVolumeWeight(false); }} />加入完成日成交量倍数研究（不等同于盘中量比）</label>
    {includeVolume && <p className="text-xs text-muted-foreground">已归档A股BaoStock行情候选、美股和港股行情候选的量能研究；A股历史估值参考、美股SEC估值也可与量能组合，其他尚无报告的组合显示未验证。</p>}
    {includeVolume && <div className="space-y-2 rounded-lg border p-3"><label className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label="训练期调优量能权重" checked={tuneVolumeWeight} onChange={event => setTuneVolumeWeight(event.target.checked)} />训练期比较量能权重（以报告实际网格为准）</label><p className="text-xs text-muted-foreground">已归档三种模式的A股BaoStock、美股SEC目录及港股Yahoo配对归档资金情景。量能权重与20日趋势互相调整；训练期选择，后续窗口验证，尚无一致改善，不应用到实时选股。</p></div>}
    {report?.volume_weight_tuning?.enabled && <p className="rounded-lg border p-3 text-sm">量能权重调优实验：{report.volume_weight_tuning.weights.map(weight => `${(weight * 100).toFixed(0)}%`).join("／")}。{report.volume_weight_tuning.policy}</p>}
    {market === "CN" && <label className="flex items-center gap-2 text-sm">行情来源<select aria-label="A股历史行情来源" value={historySource} onChange={event => setHistorySource(event.target.value as "default" | "baostock")} className="rounded-md border bg-background px-3 py-2"><option value="default">现有行情归档</option><option value="baostock">BaoStock 扩充历史</option></select></label>}
    {market === "HK" && <label className="flex items-center gap-2 text-sm">行情来源<select aria-label="港股历史行情来源" value={hkHistorySource} onChange={event => setHKHistorySource(event.target.value as "default" | "yahoo-hk")} className="rounded-md border bg-background px-3 py-2"><option value="default">原行情归档</option><option value="yahoo-hk">Yahoo 原价与复权价配对归档</option></select></label>}
    {market === "HK" && hkHistorySource === "yahoo-hk" && <p className="rounded-lg border p-3 text-xs text-muted-foreground">独立Yahoo归档，不能将与原归档的收益差异全部归因于量能。有效样本和报价日历可能不同；仅部分日K具备稳定调整比例，缺失指标贡献0。</p>}
    {market === "CN" && historySource === "baostock" && <label className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label="加入历史接口估值参考" checked={includeCNReference} onChange={event => setIncludeCNReference(event.target.checked)} />加入接口历史PE／PB／换手率参考（财务修订时间未验证）</label>}
    {report?.fundamental_mode === "cn-reference" && <p className="rounded-lg border p-3 text-sm text-amber-700">接口历史估值参考研究：财务修订时间未验证，结果不能用于证明严格时点策略有效。</p>}
    {market === "US" && <label className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label="加入SEC披露日期估值" checked={includeFundamentals} onChange={event => setIncludeFundamentals(event.target.checked)} />加入按披露日期重建的估值／市值估算</label>}
    {report?.fundamental_coverage && <div className="rounded-lg border p-3 text-xs text-muted-foreground"><p>可评分历史日K覆盖：{(["pe", "pb", "cap"] as const).map((key, index) => `${["PE", "PB", "市值"][index]} ${((report.fundamental_coverage![`${key}_observations`] / Math.max(1, report.fundamental_coverage!.observations)) * 100).toFixed(1)}%`).join(" / ")}</p><p className="mt-1">{report.fundamental_coverage.basis}</p><p className="mt-1">{report.fundamental_coverage.availability}；缺少受支持财务记录 {report.fundamental_coverage.missing_ledgers.length} 只，缺失指标贡献0。</p></div>}
    {report && !results && <p className="text-xs text-muted-foreground">有效样本 {report.available_count ?? 0}/{report.requested_count ?? 0}；异常数据排除 {report.quality_failures?.length ?? 0} 只；历史获取失败 {report.download_failures?.length ?? 0} 只。{report.selection_method}</p>}
    {error && <div><p role="status">{error}</p><button type="button" onClick={() => setRetryCount(value => value + 1)} className="rounded-md border px-3 py-2 text-sm hover:bg-muted">重试历史验证</button></div>}{!report && !error && <p className="text-sm text-muted-foreground">正在加载历史验证…</p>}{report?.message && <p className="text-sm">{report.message}</p>}
    {report?.volume_reference_coverage && <div className="space-y-1 rounded-lg border p-3 text-xs text-muted-foreground"><p>完成日量能覆盖：{(report.volume_reference_coverage.available / Math.max(1, report.volume_reference_coverage.observations) * 100).toFixed(1)}%（{report.volume_reference_coverage.available}/{report.volume_reference_coverage.observations}）</p><p>{report.volume_reference_coverage.basis}</p><p>{Object.entries(report.volume_reference_coverage.status_counts).filter(([key, count]) => key !== "ok" && count > 0).map(([key, count]) => `${volumeReasons[key] || "其他不可用记录"} ${count}`).join("；")}</p>{report.volume_reference_coverage.available === 0 && <p className="text-amber-700">此样本缺少可验证的完成日量能，当前实验未补入该因子，不能声称完成量能验证。</p>}</div>}
    {report && results && <><p className="text-sm">{report.formula_version} · {report.source} · {report.available_count}/{report.requested_count} 只样本 · {report.folds?.length} 个滚动窗口 · {report.applied ? "已应用参数" : "研究结果，未修改生产参数"}</p><p className="text-xs text-muted-foreground">{report.selection_method}<br />{report.formula_scope}<br />每20交易日调仓，次日开盘成交假设，单边费用与滑点合计0.15%。</p>
      {report.mode_risk_defaults && <p className="text-xs text-muted-foreground">模式保护预算：组合风险 {report.mode_risk_defaults.risk_budget_percent}% · 单股上限 {report.mode_risk_defaults.position_cap_percent}% · 默认 {report.mode_risk_defaults.atr_multiple} × ATR。</p>}
      {results.candidate.average_exposure === 0 && <p className="rounded-md border p-3 text-sm text-amber-700">验证窗口平均股票仓位为0，结果反映现金路径；不能据此认定模式有效。</p>}
      <p className="text-xs text-muted-foreground">研究原权重：{report.parameter_grid?.[0] ? Object.entries(report.parameter_grid[0]).map(([factor, weight]) => `${factor === "量比" && report.volume_reference_coverage ? "完成日量能参考" : factor} ${typeof weight === "number" && Number.isFinite(weight) ? `${(weight * 100).toFixed(0)}%` : "未记录"}`).join(" / ") : "报告未记录完整原权重，请查看各窗口参数"}。</p>
      {!!report.folds?.some(fold => fold.weight_selection_status || fold.risk_selection_status) && <p className="rounded-md border p-3 text-sm">训练选参完整性：{defaultWeights} 个窗口沿用默认权重，{defaultRisk} 个窗口沿用默认保护参数。训练数据不足或没有实际买入的候选时，不声称选出了更优参数。</p>}
      {report.selection_quality_policy && <p className="text-xs text-muted-foreground">{report.selection_quality_policy}</p>}
      {resultKeys.some(key => (results[key]?.missing_quote_days ?? 0) > 0) && <p className="rounded-md border p-3 text-sm text-amber-700">部分持仓缺少当日报价，净值沿用最后报价估算；回撤可能被低估，不能将这些结果视为完整可成交价格验证。</p>}
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="p-2">方案</th><th className="p-2">验证净收益</th><th className="p-2">最大回撤</th><th className="p-2">夏普（无风险=0）</th><th className="p-2">平均股票仓位</th><th className="p-2">缺报价／陈旧报价日</th><th className="p-2">保护判断缺失日／入场计划缺失次</th></tr></thead><tbody>{resultKeys.map(key => { const value = results[key]; return value ? <tr key={key} className="border-b"><td className="p-2">{names[key]}</td><td className="p-2 tabular-nums">{(value.net_return * 100).toFixed(2)}%</td><td className="p-2 tabular-nums">{(value.max_drawdown * 100).toFixed(2)}%</td><td className="p-2 tabular-nums">{value.sharpe_zero_rate.toFixed(2)}</td><td className="p-2 tabular-nums">{value.average_exposure == null ? "—" : `${(value.average_exposure * 100).toFixed(1)}%`}</td><td className="p-2 tabular-nums">{value.missing_quote_days ?? "—"} / {value.stale_quote_days ?? "—"}</td><td className="p-2 tabular-nums">{value.risk_unverifiable_days ?? "—"} / {value.risk_missing_entries ?? "—"}</td></tr> : null; })}</tbody></table></div>
      {Object.values(results).some(value => (value?.risk_unverifiable_days ?? 0) > 0 || (value?.risk_missing_entries ?? 0) > 0) && <p className="rounded-lg border p-3 text-xs text-amber-700">存在无法核验的保护判断或入场计划；相关收益来自不完整风控路径，不能据此认定参数有效。</p>}
      <p className="text-xs text-muted-foreground">保护判断缺失日：缺少持仓报价、无法确认当日触发或无法更新次日移动保护的日期。A股当日买入不能卖出，收盘后已知高价仍用于更新次日保护；旧报告可能未统计这类更新缺口。入场计划缺失次：无法生成保护计划而放弃买入的次数。限仓对照未启用止盈止损；“—”表示不适用或旧报告未统计，不代表0。</p>
      <p className="text-xs text-muted-foreground">缺报价日指持仓缺少当日报价的估值日；陈旧报价日指其中末次报价已超过7个自然日。统计为天数，不是成交失败次数；“—”表示旧报告未统计。</p>
      {!!report.quality_failures?.length && <p className="text-xs text-muted-foreground">数据质量检查排除 {report.quality_failures.length} 只样本：{report.quality_failures.map(row => row.ticker).join("、")}。</p>}
      {!!report.cost_stress?.length && <div role="region" aria-label="交易成本压力测试" className="space-y-2 rounded-lg border p-3 text-sm">
        <p>交易成本压力测试（沿用训练选定参数）</p>
        <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b"><th className="p-2">单边费用与滑点</th><th className="p-2">方案</th><th className="p-2">验证净收益</th><th className="p-2">最大回撤</th><th className="p-2">平均股票仓位</th><th className="p-2">缺报价／陈旧报价日</th><th className="p-2">保护判断缺失日／入场计划缺失次</th></tr></thead><tbody>{report.cost_stress.map(row => <tr key={`${row.strategy}:${row.one_way_cost}`} className="border-b"><td className="p-2">{(row.one_way_cost * 100).toFixed(2)}%</td><td className="p-2">{row.strategy === "risk_tuned" ? names.risk_tuned : row.strategy === "candidate" ? names.candidate : "未记录"}</td><td className="p-2 tabular-nums">{(row.net_return * 100).toFixed(2)}%</td><td className="p-2 tabular-nums">{(row.max_drawdown * 100).toFixed(2)}%</td><td className="p-2 tabular-nums">{row.average_exposure == null ? "—" : `${(row.average_exposure * 100).toFixed(1)}%`}</td><td className="p-2">{row.missing_quote_days ?? "—"} / {row.stale_quote_days ?? "—"}</td><td className="p-2">{row.risk_unverifiable_days ?? "—"} / {row.risk_missing_entries ?? "—"}</td></tr>)}</tbody></table></div>
        {costReversal && <p className="text-amber-700">较高费用下，同一训练选定策略由正收益转为亏损，当前结果对交易成本敏感。</p>}
        {report.cost_stress.some(row => row.average_exposure === 0) && <p className="text-amber-700">部分成本情景没有股票持仓，零收益不能视为策略有效。</p>}
        {report.cost_stress.some(row => (row.missing_quote_days ?? 0) > 0 || (row.risk_unverifiable_days ?? 0) > 0 || (row.risk_missing_entries ?? 0) > 0) && <p className="text-amber-700">部分成本情景存在报价或保护数据缺口，收益与回撤不能视为完整路径验证。</p>}
        <p className="text-xs text-muted-foreground">提高费用也会改变可买股数与持仓路径，不能视为等仓位扣费比较；“—”表示报告未记录，不代表0。</p>
      </div>}
      {report?.risk_availability_as_of && <div className="rounded-lg border p-3 text-xs text-muted-foreground"><p>风控数据检查截至 {report.risk_availability_as_of}，在首次验证之前固定。</p><p>{report.risk_availability_policy}</p><p>训练期可参与的证券 {report.risk_availability_training_universe?.length ?? "未记录"} 只；后续上市股票按实际历史长度进入候选。</p></div>}
    {results.protected && !report?.risk_availability_as_of && <p className="rounded-lg border p-3 text-xs text-amber-700">旧版风控回测未记录训练期数据边界，请以重新验证的报告为准。</p>}
    {results.protected && report?.risk_protection_policy_version !== "next-session-trailing-v2" && <p className="rounded-lg border p-3 text-xs text-amber-700">此报告尚未复核A股当日不可卖出期间的次日移动保护更新，请以重建版本为准。</p>}
    {results.protected && <p className="text-xs text-muted-foreground">止盈止损对照同时限制仓位、保留现金，不能将回撤下降全部归因于止损，也不是等仓位收益比较。</p>}
      <div className="h-64 w-full min-w-0" aria-label="滚动验证净值曲线"><ResponsiveContainer width="100%" height={256} minWidth={0} initialDimension={{ width: 600, height: 256 }}><LineChart data={curve}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" minTickGap={70} tick={{ fontSize: 10 }} /><YAxis domain={["auto", "auto"]} width={45} tick={{ fontSize: 10 }} /><Tooltip /><Legend /><Line dataKey="baseline" name={names.baseline} stroke="#2563eb" dot={false} /><Line dataKey="candidate" name={names.candidate} stroke="#7c3aed" dot={false} /><Line dataKey="benchmark" name={names.benchmark} stroke="#64748b" dot={false} />{results.protected && <Line dataKey="protected" name={names.protected} stroke="#059669" dot={false} />}{results.risk_tuned && <Line dataKey="risk_tuned" name={names.risk_tuned} stroke="#d97706" dot={false} />}{results.capped_control && <Line dataKey="capped_control" name={names.capped_control} stroke="#db2777" dot={false} />}</LineChart></ResponsiveContainer></div>
      <details className="rounded-lg border p-3 text-sm"><summary className="cursor-pointer">查看滚动窗口、权重和实验限制</summary><div className="mt-3 space-y-3">{report.folds?.map(fold => <p key={fold.test_start}>训练 {fold.train_start}—{fold.train_end}；验证 {fold.test_start}—{fold.test_end}。因子权重：{Object.entries(fold.candidate_weights).map(([key, weight]) => `${key === "量比" && report.volume_reference_coverage ? "完成日量能参考" : key} ${typeof weight === "number" && Number.isFinite(weight) ? `${(weight * 100).toFixed(0)}%` : "未记录"}`).join(" / ")}。{fold.candidate_risk_parameters && `训练选定：${fold.candidate_risk_parameters.atr_multiple} × ATR 止损，${fold.candidate_risk_parameters.target_r}R 止盈；仅用于后续窗口验证。`}</p>)}{report.limitations?.map(text => <p key={text} className="text-xs text-muted-foreground">{text}</p>)}</div></details>
    </>}
    {report?.scoring_input_fingerprint && results && <FormulaJointPanel key={requestKey} market={market} mode={rankingMode} sourceFingerprint={report.scoring_input_fingerprint} />}
    {market === "US" && <UsCoverResearchPanel />}
  </CardContent></Card>;
}

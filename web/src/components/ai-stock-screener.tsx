"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AddToWatchlistButton } from "@/components/add-to-watchlist-button";
import { FormulaRiskPlan } from "@/components/formula-risk-plan";
import type { FormulaRankingItem } from "@/lib/api";
import { validScreenCandidates } from "@/lib/screen-candidate-validation";

const jobStorageKey = "ai-screen-active-job";
type ScreenJob = { id: string; status: "running" | "completed" | "failed" | "interrupted"; request?: { market: "CN" | "HK" | "US"; query: string }; response?: { result: Result }; message?: string };
type Preset = "value" | "momentum" | "liquid";
type Tuning = { status: string; message?: string; applied: boolean; sample_start?: string; sample_end?: string; train_end?: string; validation_start?: string; round_trip_cost?: number; candidate_weights?: Record<string, number>; baseline_validation?: { net_return: number; max_drawdown: number; periods: number }; candidate_validation?: { net_return: number; max_drawdown: number; periods: number }; limitations?: string[] };
type Result = {
  market?: "CN" | "HK" | "US"; currency?: string;
  plan: { mode: "balanced" | "conservative" | "aggressive"; summary: string; filters: { field: string; op: string; value: number }[]; unsupported: string[] };
  items: (FormulaRankingItem & { match_reasons: string[] })[];
  matched_count?: number; scanned_count?: number; generated_at?: string; source?: string;
  universe_count?: number; quote_missing_count?: number; snapshot_matched_count?: number; history_deferred_count?: number;
  history_requested_count?: number; history_enriched_count?: number; history_failed_count?: number; risk_plan_available_count?: number;
  scope?: string; ranking_note?: string; message?: string;
  filter_coverage?: Record<string, { available: number; total: number }>;
};
const labels: Record<string, string> = { pe_ratio: "市盈率", pb_ratio: "市净率", market_cap: "总市值（元）", amount: "成交额（元）", volume_ratio: "量比", turnover_rate: "换手率（%）", today_change_percent: "今日涨幅（%）", change_5d: "5日涨幅（%）", change_20d: "20日涨幅（%）", change_60d: "60日涨幅（%）" };
const operators: Record<string, string> = { gt: ">", gte: "≥", lt: "<", lte: "≤" };
const presets: { id: Preset; label: string; query: string }[] = [
  { id: "value", label: "低估值大盘", query: "市盈率大于0且不超过20，市净率大于0且不超过3，市值至少100亿元" },
  { id: "momentum", label: "放量温和上涨", query: "量比至少1.5，今日涨幅大于0且不超过5%" },
  { id: "liquid", label: "成交活跃", query: "成交额至少5亿元，总市值至少200亿元" },
];

export function AIStockScreener() {
  const [market, setMarket] = useState<"CN" | "HK" | "US">("CN");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const active = useRef(false);
  const waiting = useRef<AbortController | null>(null);
  const [tuning, setTuning] = useState<Tuning | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/ai-screener/tuning", { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("报告不可用");
      const payload = await response.json(); setTuning(payload.result);
    }).catch(() => { if (!controller.signal.aborted) setTuning({ status: "unavailable", applied: false, message: "历史验证报告暂不可用，当前使用原始参数。" }); });
    return () => controller.abort();
  }, []);
  const watchJob = async (first: ScreenJob, controller: AbortController, expectedId: string, requestedMarket?: string) => {
    let job = first;
    while (!controller.signal.aborted) {
      if (!job || job.id !== expectedId) throw new Error("筛选任务标识与请求不一致，请刷新查询原任务");
      if (job.request) { setMarket(job.request.market); setQuery(job.request.query); }
      if (job.status === "completed") {
        if (!job.response?.result || !Array.isArray(job.response.result.items)) throw new Error("筛选结果格式异常，请重新提交");
        if (job.response.result.items.length > 0 && !["balanced", "conservative", "aggressive"].includes(job.response.result.plan?.mode)) {
          throw new Error("筛选结果评分模式异常，请重新提交");
        }
        if (!validScreenCandidates(job.response.result, requestedMarket || job.request?.market)) {
          throw new Error("筛选候选数据异常，请刷新查询原任务");
        }
        sessionStorage.removeItem(jobStorageKey);
        setResult(job.response.result);
        return;
      }
      if (job.status !== "running") {
        sessionStorage.removeItem(jobStorageKey);
        throw new Error(job.message || "筛选未完成，请重新提交");
      }
      await new Promise<void>((resolve, reject) => {
        const aborted = () => { clearTimeout(timer); reject(new DOMException("停止等待", "AbortError")); };
        const timer = setTimeout(() => { controller.signal.removeEventListener("abort", aborted); resolve(); }, 1500);
        controller.signal.addEventListener("abort", aborted, { once: true });
      });
      const response = await fetch(`/api/ai-screener/jobs/${expectedId}`, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]), cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) {
        if (response.status === 404) sessionStorage.removeItem(jobStorageKey);
        throw new Error(payload.detail || "状态查询失败，刷新页面可继续查询已有任务");
      }
      job = payload.job;
    }
  };
  useEffect(() => {
    const id = sessionStorage.getItem(jobStorageKey);
    if (!id) return;
    const controller = new AbortController();
    waiting.current = controller; active.current = true; setBusy(true);
    void fetch(`/api/ai-screener/jobs/${id}`, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]), cache: "no-store" }).then(async response => {
      const payload = await response.json();
      if (!response.ok) { if (response.status === 404) sessionStorage.removeItem(jobStorageKey); throw new Error(payload.detail || "无法恢复筛选任务"); }
      await watchJob(payload.job, controller, id);
    }).catch(error => { if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "无法恢复筛选任务"); })
      .finally(() => { if (waiting.current === controller) { waiting.current = null; active.current = false; setBusy(false); } });
    return () => controller.abort();
    // Restore the single outstanding task when this component mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => () => waiting.current?.abort(), []);
  const run = async (preset?: typeof presets[number]) => {
    if (active.current) return;
    active.current = true;
    const controller = new AbortController(); waiting.current = controller;
    const text = preset ? preset.query.replaceAll("亿元", market === "HK" ? "亿港元" : market === "US" ? "亿美元" : "亿元") : query.trim();
    if (preset) setQuery(text);
    setBusy(true); setResult(null); setMessage("");
    try {
      const bytes = crypto.getRandomValues(new Uint8Array(32));
      const submissionId = btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
      sessionStorage.setItem(jobStorageKey, submissionId);
      const response = await fetch("/api/ai-screener/jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ submission_id: submissionId, query: text, market, preset: preset?.id, limit: 20 }), signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) });
      const payload = await response.json();
      if (!response.ok) {
        // Server/proxy failures can happen after the worker accepted this ID.
        // Keep it for GET recovery rather than replacing it with a new task.
        const uncertain = response.status >= 500 || response.status === 408;
        if (!uncertain) sessionStorage.removeItem(jobStorageKey);
        const detail = typeof payload.detail === "string" ? payload.detail : "筛选失败，请检查条件后重试";
        throw new Error(uncertain ? `${detail} 刷新页面可继续查询原任务。` : detail);
      }
      if (controller.signal.aborted) return;
      await watchJob(payload.job, controller, submissionId, market);
    } catch (error) { if (!controller.signal.aborted) setMessage(error instanceof Error && error.name === "TimeoutError" ? "请求超时；已提交的任务可刷新页面继续查询" : error instanceof Error ? error.message : "筛选失败"); }
    finally { if (waiting.current === controller) { waiting.current = null; active.current = false; setBusy(false); } }
  };
  const stopWaiting = () => {
    waiting.current?.abort(); waiting.current = null; active.current = false; setBusy(false);
    sessionStorage.removeItem(jobStorageKey);
    setMessage("已停止页面等待；后台任务仍会完成。可以重新填写条件，繁忙时请稍后再提交。");
  };
  return <Card>
    <CardHeader><CardTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5" />一句话选股</CardTitle><CardDescription>AI 识别条件，行情数据验证。支持A股、港股、美股；金额使用所选市场本币，不作汇率换算。策略模板无需 AI 服务即可使用。</CardDescription></CardHeader>
    <CardContent className="space-y-4">
      <form className="space-y-3" onSubmit={event => { event.preventDefault(); void run(); }}>
        <label className="flex items-center gap-2 text-sm">条件选股市场<select aria-label="条件选股市场" value={market} disabled={busy} onChange={event => {setMarket(event.target.value as "CN" | "HK" | "US");setResult(null);setMessage("");}} className="rounded-md border bg-background px-3 py-2"><option value="CN">A股 · CNY</option><option value="HK">港股 · HKD</option><option value="US">美股 · USD</option></select></label>
        <label htmlFor="screen-intent" className="text-sm font-medium">你想找什么样的股票？</label>
        <Textarea id="screen-intent" maxLength={600} rows={3} value={query} disabled={busy} onChange={event => setQuery(event.target.value)} placeholder="例如：找市盈率0到20倍、市值超过100亿元的A股" />
        <div className="flex flex-wrap items-center gap-2"><Button type="submit" disabled={busy || query.trim().length < 2}>{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}{busy ? "正在识别条件并筛选…" : "AI 筛选"}</Button>{busy && <Button type="button" variant="outline" onClick={stopWaiting}>停止等待</Button>}{presets.map(preset => <Button key={preset.id} type="button" variant="outline" disabled={busy} onClick={() => void run(preset)}>{preset.label}</Button>)}</div>
      </form>
      {busy && <p role="status" className="text-xs text-muted-foreground">正在核验条件并补齐候选日 K；历史数据不足时会显示缺失，不会补造因子。</p>}
      {message && <p role="status" className="text-sm">{message}</p>}
      {tuning && <details className="rounded-lg border p-4 text-sm"><summary className="cursor-pointer font-medium">历史参数验证 · {tuning.applied ? "已应用" : "保留原始参数"}</summary><div className="mt-3 space-y-2">{tuning.message && <p>{tuning.message}</p>}{tuning.candidate_validation && tuning.baseline_validation && <><p>固定12只A股样本 · {tuning.sample_start} 至 {tuning.sample_end} · 调优数据截至 {tuning.train_end}，验证从 {tuning.validation_start} 开始。</p><p>20交易日调仓，选前三名，每轮成本 {((tuning.round_trip_cost || 0) * 100).toFixed(2)}%。</p><p>训练期候选权重：{Object.entries(tuning.candidate_weights || {}).map(([key, value]) => `${key} ${(value * 100).toFixed(0)}%`).join(" / ")}</p><p>验证期 {tuning.candidate_validation.periods} 轮：原权重净收益 {(tuning.baseline_validation.net_return * 100).toFixed(2)}%，候选权重 {(tuning.candidate_validation.net_return * 100).toFixed(2)}%；最大回撤分别为 {(tuning.baseline_validation.max_drawdown * 100).toFixed(2)}% / {(tuning.candidate_validation.max_drawdown * 100).toFixed(2)}%。</p><p>本实验使用价格动量排序，与下方多因子公式口径不同，候选参数未用于当前排名。</p></>}{tuning.limitations?.map(text => <p key={text} className="text-xs text-muted-foreground">{text}</p>)}</div></details>}
      {result && <div className="space-y-4" aria-live="polite">
        <div className="rounded-lg border bg-muted/30 p-4"><p className="font-medium">{result.plan.summary}</p><div className="mt-2 flex flex-wrap gap-2">{result.plan.filters.map((condition, index) => <span key={index} className="rounded-md border bg-background px-2 py-1 text-xs">{labels[condition.field]?.replace('（元）', `（${result.currency || ({CN:'CNY',HK:'HKD',US:'USD'}[market])}）`)} {operators[condition.op]} {condition.value.toLocaleString("zh-CN")}</span>)}</div>
        {result.plan.unsupported.length > 0 && <p className="mt-3 text-sm text-amber-700">未执行筛选：{result.plan.unsupported.join("；")}。请移除这些条件后重新筛选。</p>}</div>
        {result.message && <p className="text-sm">{result.message}</p>}
        {result.filter_coverage && <p className="text-xs text-muted-foreground">条件指标覆盖：{Object.entries(result.filter_coverage).map(([field, counts]) => `${labels[field]?.replace('（元）', `（${result.currency}）`) || field} ${counts.available}/${counts.total}`).join(" · ")}。缺失指标不参与匹配。</p>}
        {result.universe_count != null && <p className="text-sm">目录 {result.universe_count} 只 · 缺少有效行情 {result.quote_missing_count} 只 · 快照条件匹配 {result.snapshot_matched_count} 只 · 未进行本轮历史评分 {result.history_deferred_count} 只</p>}
        {result.scanned_count != null && <><p className="text-sm">扫描 {result.scanned_count} 只 · {result.market === "US" ? "本轮评分候选中符合全部条件" : "符合全部条件"} {result.matched_count} 只 · 展示前 {result.items.length} 只</p><p className="text-xs text-muted-foreground">{result.source} · 数据时间 {result.generated_at || "未知"}<br />{result.scope}<br />{result.ranking_note}</p></>}
        {result.history_requested_count != null && <p className="text-xs text-muted-foreground">历史因子完整覆盖 {result.history_enriched_count}/{result.history_requested_count} 只 · 缺失或未通过时间校验 {result.history_failed_count} 只 · 全部匹配候选中价格参考可用 {result.risk_plan_available_count} 只。完整覆盖指 5/20/60 日涨幅均可验证，价格参考另需完整 OHLC。</p>}
        {result.scanned_count != null && result.items.length === 0 && <p className="rounded-lg border p-4 text-sm">{Object.values(result.filter_coverage || {}).some(counts => counts.total > 0 && counts.available === 0) ? "当前候选快照缺少部分条件指标，无法验证全部要求。请使用有数据覆盖的条件，或等待行情指标补全。" : "没有符合全部条件的股票。可调整阈值后重新筛选；缺失指标不会视为满足条件。"}</p>}
        <div className="grid gap-3 lg:grid-cols-2">{result.items.map(item => <article key={item.ticker} className="space-y-3 rounded-lg border p-4"><div className="flex items-center justify-between gap-2"><Link href={`/stock/${encodeURIComponent(item.ticker)}?mode=${result.plan.mode}`} className="font-semibold hover:underline">{item.name || item.ticker} <span className="text-xs font-normal text-muted-foreground">{item.ticker}</span></Link><span className="text-sm">公式分 {item.formula_score.toFixed(1)}</span></div><ul className="space-y-1 text-xs text-muted-foreground">{item.match_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>{!!item.risks?.length && <p className="text-xs text-amber-700">风险：{item.risks.join("；")}</p>}<FormulaRiskPlan key={`${item.ticker}:${result.generated_at}`} plan={item.risk_plan} market={item.market || result.market || market} historyMetadata={item.history_price_metadata} /><AddToWatchlistButton ticker={item.ticker} name={item.name} market={item.market || result.market || market} onResult={setMessage} /></article>)}</div>
        <p className="text-xs text-muted-foreground">条件匹配用于缩小研究范围，不代表未来收益或买入建议。</p>
      </div>}
    </CardContent>
  </Card>;
}

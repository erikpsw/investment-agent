"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Header } from "@/components/header";

type EventRow = {
  code: string; date: string; stage: string; score: number; score_max: number;
  eligible: boolean; state_risks: string[]; quality_flags: string[];
  components: Record<string, { points: number | null; max: number; status: string }>;
  preview: { mapping_status: string; native_open?: number; native_stop?: number; executable_from?: string };
  entry_risk?: { gap_atr: number; stop_distance_atr: number; reasons: string[] };
};
type Report = {
  version: string; report_date: string; stocks: number; native_rows: number;
  factor_records: number; events: EventRow[]; limitations: string[]; universe: string[];
};
const stageNames: Record<string, string> = { pullback: "缩量回撤", observe: "介入观察", confirmed: "突破确认" };
const componentNames: Record<string, string> = { weekly_trend: "周线趋势", volume_price: "量价结构", daily_entry: "日线介入", sector: "板块加持", momentum: "动量", liquidity: "流动性" };

export default function StrategyPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState(false);
  const [symbol, setSymbol] = useState("all");
  const [selected, setSelected] = useState<EventRow | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/strategy/weekly-v1.2.json", { signal: controller.signal }).then(r => {
      if (!r.ok) throw new Error("report_unavailable");
      return r.json();
    }).then((r: Report) => {
      setReport(r); setSelected(r.events.find(e => e.stage === "confirmed") ?? r.events[0]);
    }).catch(e => { if (e.name !== "AbortError") setError(true); });
    return () => controller.abort();
  }, []);
  return <><Header /><main className="mx-auto w-full max-w-7xl space-y-6 p-4 lg:p-8">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-sm text-muted-foreground">周线趋势 · 缩量洗盘 · 日线确认</p><h1 className="text-3xl font-bold">策略评分 v1.2</h1><p className="mt-2 text-sm text-muted-foreground">历史研究报告 · 2026-10-25 发布 · 自动交易关闭</p></div>
      <a className="rounded-lg border px-4 py-2 text-sm" href="/strategy/weekly-v1.2.json" download>下载诊断数据</a>
    </div>
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-5 text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
      <h2 className="font-semibold">收益回测待验证</h2><p className="mt-2 text-sm leading-6">当前版本完成了指标、形态和价格风险诊断，尚未完成大盘、板块与动态仓位的组合收益回测。此前 527.88% 属于另一套动量研究，不能视为本策略收益。评分表示规则匹配程度，不是上涨概率。</p>
    </div>
    {error && <p role="alert">报告加载失败，请刷新重试。</p>}
    {!report && !error && <p role="status">正在加载已核验的历史报告…</p>}
    {report && <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[
        ["样本股票", `${report.stocks} 只`], ["原始日线", report.native_rows.toLocaleString()],
        ["历史候选信号", `${report.events.length} 个`], ["完整策略可执行", "0 个"],
      ].map(([label, value]) => <div key={label} className="rounded-xl border p-5"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold">{value}</p></div>)}</div>
      <section className="rounded-xl border p-5"><h2 className="text-lg font-semibold">评分与介入流程</h2>
        <p className="mt-3 text-sm leading-7">周线趋势 25 + 量价结构 25 + 日线介入 20 + 板块 15 + 动量 10 + 流动性 5 = 100 分。当前缺少历史板块评分，显示已获分 / 可评 85 分，不折算到 100 分。VW-MACD、布林带、CCI、一目均衡表作为特征；PE/PB 不作为追逐题材行情的核心评分。</p>
        <p className="mt-3 text-sm leading-7">周线趋势 → 放量上涨 → 缩量回撤且支撑有效 → 日线十字星进入观察 → 放量突破确认 → 下一交易日检查价格风险。观察点不等于买点。开盘绝对跳空超过 0.5 ATR，或入场到止损超过 2.5 ATR，跳过。通过价格检查后仍需大盘、板块、账户风险预算及交易可执行性全部通过。</p>
        <p className="mt-3 text-sm leading-7">撤出框架：有效跌破冻结支撑时退出；板块或大盘走弱时降低仓位预算。动态减仓、分批止盈和 ATR 跟踪止损仍需联合回测，不将这些待验证规则计入已有收益。</p>
      </section>
      <section className="rounded-xl border p-5"><h2 className="text-lg font-semibold">历史信号：32 次回撤 → 4 次观察 → 1 次确认</h2>
        <p className="mt-2 text-sm text-muted-foreground">以下是各日期当时的归档评分，不是当前买入建议。覆盖 28 只股票，其中部分没有候选信号。</p>
        <label className="mt-4 block text-sm">股票筛选 <select aria-label="股票筛选" value={symbol} onChange={e => setSymbol(e.target.value)} className="ml-2 rounded border bg-background p-2"><option value="all">全部样本</option>{report.universe.map(code => <option key={code}>{code}</option>)}</select></label>
        <div className="mt-4 max-h-96 overflow-auto"><table className="w-full min-w-[600px] text-left text-sm"><thead className="sticky top-0 bg-background"><tr>{["股票", "信号日期", "阶段", "评分 / 可评", "次日价格映射", "详情"].map(h => <th key={h} className="border-b p-3">{h}</th>)}</tr></thead><tbody>
          {report.events.filter(e => symbol === "all" || e.code === symbol).map(e => <tr key={`${e.code}-${e.stage}-${e.date}`} className="border-b"><td className="p-3">{e.code}</td><td>{e.date}</td><td>{stageNames[e.stage]}</td><td>{e.score.toFixed(2)} / {e.score_max}</td><td>{e.preview.mapping_status === "compatible" ? "映射可用 · 仍需风控" : "拒绝 / 数据不足"}</td><td><button className="rounded border px-3 py-1" onClick={() => setSelected(e)}>查看</button></td></tr>)}
        </tbody></table>{!report.events.some(e => symbol === "all" || e.code === symbol) && <p className="p-4 text-sm">该样本没有产生候选信号。</p>}</div>
      </section>
      {selected && <section className="rounded-xl border p-5" aria-live="polite"><h2 className="text-lg font-semibold">{selected.code} · {selected.date} · {stageNames[selected.stage]}</h2>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">{Object.entries(selected.components).map(([key, c]) => <div key={key} className="rounded-lg bg-muted p-3"><p className="text-sm">{componentNames[key] ?? key}</p><p className="mt-1 font-semibold">{c.points == null ? "缺少数据" : c.points.toFixed(2)} / {c.max}</p></div>)}</div>
        <p className="mt-4 text-sm">完整策略资格：未通过。市场 M、历史板块 B 与实际交易风控不完整；次日原始开盘 {selected.preview.native_open?.toFixed(2) ?? "未知"}，参考支撑 {selected.preview.native_stop?.toFixed(2) ?? "未知"}。价格映射成功不等于允许成交。</p>
        {selected.entry_risk && <div className="mt-4 rounded-lg border border-red-300 p-4"><p className="font-semibold">山煤国际：形态确认，但价格风险拒绝介入</p><p className="mt-2 text-sm leading-7">2019-07-23 观察，07-24 放量确认；07-25 开盘 6.71 元。确认收盘 6.49 元，ATR 0.2981 元，支撑 5.93 元。跳空 {selected.entry_risk.gap_atr.toFixed(3)} ATR ＞ 0.5；止损距离 {selected.entry_risk.stop_distance_atr.toFixed(3)} ATR ＞ 2.5。评分较高仍跳过，不放宽阈值追买。</p></div>}
        {selected.state_risks.length > 0 && <p className="mt-3 text-sm text-amber-700">结构风险标记：{selected.state_risks.join("、")}</p>}
      </section>}
      <section className="rounded-xl border p-5"><h2 className="text-lg font-semibold">K 线决策点：唯一突破确认案例</h2><p className="mb-4 mt-2 text-sm text-muted-foreground">山煤国际历史案例，图上标注观察与确认；未产生订单或收益。</p><Image src="/strategy/weekly-v1.2-confirmed.png" alt="山煤国际历史K线、成交量、观察及突破确认决策点，缺少市场和板块评分，不构成订单" width={1800} height={1100} unoptimized className="h-auto w-full rounded-lg" /></section>
      <section className="rounded-xl border p-5"><h2 className="font-semibold">本次验证的边界</h2><ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-muted-foreground">{report.limitations.map(t => <li key={t}>{t}</li>)}</ul><p className="mt-4 text-xs text-muted-foreground">版本：{report.version} · 复权因子记录 {report.factor_records} 条 · 原始研究文件 SHA256 包含在下载报告中。</p></section>
    </>}
  </main></>;
}

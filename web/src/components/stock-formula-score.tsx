"use client";

import { useQuery } from "@tanstack/react-query";
import type { FormulaRankingItem } from "@/lib/api";
import { securityIdentity, validScoreItem } from "@/lib/formula-score-validation";
import { FormulaRiskPlan } from "@/components/formula-risk-plan";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Mode = "balanced" | "conservative" | "aggressive";
type Detail = { mode?: Mode; valuation?: { pe_ratio?: number | null; pb_ratio?: number | null; pe_source?: string | null; pb_source?: string | null; pe_basis?: string | null }; financials_status?: string; status: string; message?: string; item?: FormulaRankingItem; source?: string; quote_as_of?: string | null; quote_time_status?: string | null; provider_timestamp_raw?: string | null; fetched_at?: string | null; scope?: string };
const modes: Array<[Mode, string]> = [["balanced", "均衡"], ["conservative", "稳健"], ["aggressive", "进取"]];
const fields: Record<string, string> = { change_5d: "5日动量", change_20d: "20日趋势", change_60d: "60日趋势", today_change_percent: "今日动量", volume_ratio: "量比", turnover_rate: "换手率", pe_ratio: "PE", pb_ratio: "PB", market_cap: "市值" };
const fixed = (value: number | null | undefined, decimals = 1) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(decimals) : "—";

export function StockFormulaScore({ ticker, mode, onModeChange }: { ticker: string; mode: Mode; onModeChange: (mode: Mode) => void }) {
  const { data, isPending, isError, refetch } = useQuery<Detail>({
    queryKey: ["formula-score", ticker, mode], staleTime: 60000, retry: false,
    queryFn: async ({ signal }) => {
      const response = await fetch(`/api/formula-ranking/stock/${encodeURIComponent(ticker)}?mode=${mode}`, { signal });
      if (!response.ok) throw new Error("量化评分暂不可用");
      const payload = await response.json();
      if (!payload.result) throw new Error("量化评分暂不可用");
      if (payload.result.status === "ok" && payload.result.mode !== mode) {
        throw new Error("量化评分模式与请求不匹配");
      }
      if (payload.result.status === "ok") {
        const identity = securityIdentity(ticker);
        if (!identity || payload.result.item?.ticker !== identity[0] || payload.result.item?.market !== identity[1]) {
          throw new Error("量化评分证券与请求不匹配");
        }
        if (!validScoreItem(payload.result.item)) throw new Error("量化评分数据格式无效");
      }
      return payload.result;
    },
  });
  const item = !isError && data?.status === "ok" ? data.item : undefined;
  const providerTime = data?.quote_time_status === "provider" && typeof data.quote_as_of === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(data.quote_as_of) && Number.isFinite(Date.parse(data.quote_as_of)) ? data.quote_as_of : undefined;
  return <Card className="min-w-0"><CardHeader><CardTitle role="heading" aria-level={2}>量化评分</CardTitle><CardDescription>与公式选股共用评分和风控引擎，按当前可用数据评估这只股票。</CardDescription></CardHeader><CardContent className="space-y-4">
    <div className="flex flex-wrap gap-2">{modes.map(([value, label]) => <Button key={value} size="sm" variant={mode === value ? "default" : "outline"} aria-label={`评分模式：${label}`} aria-pressed={mode === value} onClick={() => onModeChange(value)}>{label}</Button>)}</div>
    {isPending && <p role="status" className="text-sm text-muted-foreground">正在计算量化评分…</p>}
    {isError && <div className="flex flex-wrap items-center gap-3"><p role="status" className="text-sm">量化评分暂不可用，未填充默认分数。</p><Button size="sm" variant="outline" onClick={() => void refetch()}>重试评分</Button></div>}
    {data && data.status !== "ok" && <p role="status" className="text-sm text-muted-foreground">{data.message || "此证券暂不支持股票公式评分"}</p>}
    {item && <>
      <div className="flex flex-wrap items-center gap-4"><p className="text-3xl font-semibold tabular-nums">{fixed(item.formula_score)} / 100</p><div className="text-sm"><p>{item.recommendation}</p><p className="text-muted-foreground">加权因子完整度 {fixed(item.data_coverage == null ? undefined : item.data_coverage * 100, 0)}%</p></div></div>
      <div role="group" aria-label="评分数据时间" className="space-y-1 text-xs text-muted-foreground">
        <p>{item.formula_version} · 行情来源 {data?.source || "未提供"} · 报价时间 {providerTime || "未提供"} · 日K截至 {item.history_as_of || "未提供"}</p>
        <p>{providerTime ? "供应商已提供带时区的报价时间；日K对齐状态见保护价参考。" : data?.quote_time_status === "unverified_timezone" ? "报价时区尚未核验；评分与保护价的时间对齐未确认。" : "报价时间尚未核验；评分与保护价的时间对齐未确认。"}</p>
        {data?.quote_time_status === "unverified_timezone" && data.provider_timestamp_raw && <p>原始时间 {data.provider_timestamp_raw}（时区未确认）</p>}
        {data?.fetched_at && <p>查询时间 {data.fetched_at}</p>}
      </div>
      {data?.valuation && <p className="text-xs text-muted-foreground">评分估值：PE {fixed(data.valuation.pe_ratio, 2)}{data.valuation.pe_basis ? `（${data.valuation.pe_basis}）` : ""} · PB {fixed(data.valuation.pb_ratio, 2)}<br />PE来源 {data.valuation.pe_source || "未提供"} · PB来源 {data.valuation.pb_source || "未提供"}</p>}
      {data?.financials_status === "unavailable" && <p className="text-xs text-muted-foreground">财务估值暂不可用，本次仅使用可用行情指标；缺失项未补分。</p>}
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="p-2">因子</th><th className="p-2">权重</th><th className="p-2">得分贡献</th></tr></thead><tbody>{Object.entries(item.contributions || {}).map(([name, contribution]) => <tr className="border-b" key={name}><td className="p-2">{name}</td><td className="p-2">{fixed(item.weights?.[name] == null ? undefined : item.weights[name] * 100, 0)}%</td><td className="p-2 tabular-nums">{fixed(contribution)} 分</td></tr>)}</tbody></table></div>
      <p className="text-sm">风险惩罚 {fixed(item.components?.["风险惩罚"])} 分；缺失因子贡献0，不重分配权重。</p>
      {!!item.missing_fields?.length && <p className="text-xs text-muted-foreground">缺失指标：{item.missing_fields.map(field => fields[field] || field).join("、")}</p>}
      {!!item.risks?.length && <p className="text-xs text-muted-foreground">{item.risks.join("；")}</p>}
      <FormulaRiskPlan key={`${ticker}:${mode}`} plan={item.risk_plan} market={item.market} historyMetadata={item.history_price_metadata} />
      <p className="text-xs text-muted-foreground">{data?.scope}；量化分数不是预期收益或买卖指令。</p>
    </>}
  </CardContent></Card>;
}

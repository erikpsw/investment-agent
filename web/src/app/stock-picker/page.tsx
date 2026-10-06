"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Calculator, Loader2, RefreshCw, Target } from "lucide-react";
import { AIStockScreener } from "@/components/ai-stock-screener";
import { FormulaBacktestPanel } from "@/components/formula-backtest-panel";
import { FormulaRiskPlan } from "@/components/formula-risk-plan";
import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, type FormulaRankingItem, type FormulaRankingResult } from "@/lib/api";
import { validScoreItem } from "@/lib/formula-score-validation";
import { cn } from "@/lib/utils";

type Market = "CN" | "US" | "HK" | "all";
type Mode = "balanced" | "conservative" | "aggressive";
type SortKey = "formula_score" | "change_5d" | "change_20d" | "change_60d" | "today_change_percent";

const markets: Array<{ value: Market; label: string }> = [
  { value: "CN", label: "A股" },
  { value: "US", label: "美股" },
  { value: "HK", label: "港股" },
  { value: "all", label: "全部" },
];

const modes: Array<{ value: Mode; label: string }> = [
  { value: "balanced", label: "均衡" },
  { value: "conservative", label: "稳健" },
  { value: "aggressive", label: "进攻" },
];

const sorts: Array<{ value: SortKey; label: string }> = [
  { value: "formula_score", label: "综合分" },
  { value: "change_5d", label: "5日" },
  { value: "change_20d", label: "20日" },
  { value: "change_60d", label: "60日" },
  { value: "today_change_percent", label: "今日" },
];

function percent(value?: number | null) {
  if (value == null) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function number(value?: number | null, digits = 2) {
  if (value == null) return "--";
  return value.toFixed(digits);
}

function PercentValue({ value }: { value?: number | null }) {
  return (
    <span
      className={cn(
        "font-medium tabular-nums",
        value != null && value > 0 && "text-green-600",
        value != null && value < 0 && "text-red-600"
      )}
    >
      {percent(value)}
    </span>
  );
}

function scoreTone(score: number) {
  if (score >= 78) return "text-green-600";
  if (score >= 65) return "text-amber-600";
  return "text-muted-foreground";
}

function recommendationVariant(value: string) {
  if (value.includes("优先")) return "default";
  if (value.includes("观察")) return "secondary";
  return "outline";
}

function formatTime(value?: string | null) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function topRisk(item: FormulaRankingItem) {
  if (item.risks?.length) return item.risks[0];
  return item.action || "--";
}

export default function StockPickerPage() {
  const [market, setMarket] = useState<Market>("CN");
  const [mode, setMode] = useState<Mode>("balanced");
  const [sortKey, setSortKey] = useState<SortKey>("formula_score");
  const [data, setData] = useState<FormulaRankingResult | null>(null);
  const [loading, setLoading] = useState(true);

  const [message, setMessage] = useState("");

  const requestId = useRef(0);
  const load = async () => {
    const id = ++requestId.current;
    setLoading(true);
    setData(null);
    setMessage("");
    try {
      const response = await api.getFormulaRanking(market, 20, mode);
      if (id !== requestId.current) return;
      if (!response.result || !Array.isArray(response.result.items) || !response.result.items.every(validScoreItem)) {
        throw new Error("公式排名数据异常，请重试");
      }
      setData(response.result);
      setMessage("");

    } catch (error) {
      if (id !== requestId.current) return;
      setMessage(error instanceof Error ? error.message : "加载公式排名失败");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    return () => { requestId.current++; };
  }, [market, mode]);

  const topItems = useMemo(
    () =>
      [...(data?.items || [])].sort(
        (left, right) => (right[sortKey] ?? Number.NEGATIVE_INFINITY) - (left[sortKey] ?? Number.NEGATIVE_INFINITY)
      ),
    [data, sortKey]
  );
  const priorityCount = useMemo(
    () => topItems.filter((item) => item.recommendation.includes("优先")).length,
    [topItems]
  );

  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col gap-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">公式与 AI 选股</h1>
            <p className="text-muted-foreground">
              用行情、趋势、量价和估值因子初筛，查看每项贡献与历史验证。
            </p>
          </div>
          <Button variant="outline" onClick={load} disabled={loading}>
            {loading ? <Loader2 data-icon="inline-start" className="animate-spin" /> : <RefreshCw data-icon="inline-start" />}
            刷新
          </Button>
        </div>

        <AIStockScreener />
        <FormulaBacktestPanel market={market} rankingMode={mode} />



        <div className="flex flex-wrap gap-3">
          <div className="flex rounded-md border p-1">
            {markets.map((item) => (
              <Button
                key={item.value}
                type="button"
                size="sm"
                variant={market === item.value ? "secondary" : "ghost"}
                onClick={() => setMarket(item.value)}
              >
                {item.label}
              </Button>
            ))}
          </div>
          <div className="flex flex-wrap rounded-md border p-1">
            {sorts.map((item) => (
              <Button
                key={item.value}
                type="button"
                size="sm"
                variant={sortKey === item.value ? "secondary" : "ghost"}
                onClick={() => setSortKey(item.value)}
              >
                {item.label}（本页）
              </Button>
            ))}
          </div>
          <div className="flex rounded-md border p-1">
            {modes.map((item) => (
              <Button
                key={item.value}
                type="button"
                size="sm"
                variant={mode === item.value ? "secondary" : "ghost"}
                onClick={() => setMode(item.value)}
              >
                {item.label}
              </Button>
            ))}
          </div>
        </div>

        {message && <div className="rounded-lg border px-4 py-3 text-sm">{message}</div>}

        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader>
              <CardDescription>本轮扫描</CardDescription>
              <CardTitle className="text-2xl">{data?.scanned_count ?? data?.total ?? "--"}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>优先关注</CardDescription>
              <CardTitle className="text-2xl">{priorityCount}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>行情时间</CardDescription>
              <CardTitle className="text-sm">{formatTime(data?.generated_at)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>数据来源</CardDescription>
              <CardTitle className="text-sm">{data?.source || "--"}</CardTitle>
            </CardHeader>
          </Card>
        </div>

        {data?.fallback && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            全市场行情暂时不可用，当前显示历史候选缓存。
            {data.fallback_reason ? ` 原因：${data.fallback_reason}` : ""}
          </div>
        )}
        {data?.snapshot_only && <p className="rounded-lg border px-4 py-3 text-sm text-amber-700">当前使用保存的市场快照，请核对数据时间；不代表实时价格。</p>}
        {!!data?.market_sources?.length && <div className="rounded-lg border p-3 text-xs text-muted-foreground">{data.market_sources.map(source => <p key={source.market}>{source.market} · {formatTime(source.generated_at)} · {source.source}</p>)}</div>}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calculator />公式口径
            </CardTitle>
            <CardDescription>{data?.formula || "正在加载公式口径"}</CardDescription>
            {data?.scope && <p className="text-xs text-muted-foreground">{data.scope} · 候选 {data.candidate_count ?? data.total} 只 · {data.formula_version}</p>}
          </CardHeader>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target />公式候选排名
            </CardTitle>
            <CardDescription>点击股票名称进入个股行情、K 线和财务数据。</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-14">排名</TableHead>
                  <TableHead>股票</TableHead>
                  <TableHead>主题</TableHead>
                  <TableHead>公式分</TableHead>
                  <TableHead>建议</TableHead>
                  <TableHead>5日</TableHead>
                  <TableHead>20日</TableHead>
                  <TableHead>60日</TableHead>
                  <TableHead>今日</TableHead>
                  <TableHead>量比</TableHead>
                  <TableHead>换手</TableHead>
                  <TableHead>PE/PB</TableHead>
                  <TableHead className="min-w-48">风险/动作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading && !topItems.length ? (
                  <TableRow>
                    <TableCell colSpan={13} className="h-24 text-center text-muted-foreground">
                      <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" />
                      正在计算排名
                    </TableCell>
                  </TableRow>
                ) : topItems.length ? (
                  topItems.map((item, index) => (
                    <TableRow key={`${item.market}-${item.ticker}`}>
                      <TableCell className="font-medium tabular-nums">{index + 1}</TableCell>
                      <TableCell>
                        <Link href={`/stock/${encodeURIComponent(item.ticker)}?mode=${mode}`} className="font-medium hover:underline">
                          {item.name || item.ticker}
                        </Link>
                        <div className="text-xs text-muted-foreground">{item.ticker}</div>
                        {item.data_coverage != null && <div className="mt-1 text-xs text-muted-foreground">因子完整度 {(item.data_coverage * 100).toFixed(0)}%</div>}
                        {item.history_as_of && <div className="text-xs text-muted-foreground">日K截至 {item.history_as_of}</div>}
                        {!!item.contributions && <details className="mt-2 text-xs"><summary className="cursor-pointer text-primary">评分依据</summary><div className="mt-1 space-y-1">{Object.entries(item.contributions).map(([name, contribution]) => <p key={name}>{name}：{contribution.toFixed(1)}分 · 权重 {((item.weights?.[name] || 0) * 100).toFixed(0)}%</p>)}<p>风险扣分：{item.components?.["风险惩罚"] ?? 0}</p>{!!item.missing_fields?.length && <p>缺失 {item.missing_fields.length} 项指标，未补默认分。</p>}</div></details>}
                      </TableCell>
                      <TableCell>
                        <div className="max-w-32 truncate">{item.theme || "--"}</div>
                      </TableCell>
                      <TableCell>
                        <span className={cn("text-lg font-semibold tabular-nums", scoreTone(item.formula_score))}>
                          {item.formula_score.toFixed(1)}
                        </span>
                        {item.original_score != null && (
                          <div className="text-xs text-muted-foreground">原始 {item.original_score.toFixed(0)}</div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={recommendationVariant(item.recommendation)}>
                          {item.recommendation}
                        </Badge>
                      </TableCell>
                      <TableCell><PercentValue value={item.change_5d} /></TableCell>
                      <TableCell><PercentValue value={item.change_20d} /></TableCell>
                      <TableCell><PercentValue value={item.change_60d} /></TableCell>
                      <TableCell><PercentValue value={item.today_change_percent} /></TableCell>
                      <TableCell>{number(item.volume_ratio)}</TableCell>
                      <TableCell>{percent(item.turnover_rate)}</TableCell>
                      <TableCell>
                        <div className="tabular-nums">{number(item.pe_ratio, 1)}</div>
                        <div className="text-xs text-muted-foreground">PB {number(item.pb_ratio, 1)}</div>
                      </TableCell>
                      <TableCell className="max-w-64">
                        <div className="line-clamp-2 text-sm text-muted-foreground">{topRisk(item)}</div>
                        <FormulaRiskPlan key={`${item.ticker}-${item.risk_plan?.currency}`} plan={item.risk_plan} market={item.market || market} historyMetadata={item.history_price_metadata} />
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={13} className="h-24 text-center text-muted-foreground">
                      暂无可排名标的
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </main>
    </>
  );
}

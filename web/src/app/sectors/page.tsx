"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, ArrowDownUp, Calculator, Loader2, RefreshCw, Target } from "lucide-react";
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, type FormulaRankingItem, type SectorConstituentsResult, type SectorHistoryResult, type SectorItem } from "@/lib/api";
import { cn } from "@/lib/utils";

type SortKey = "score" | "change_percent" | "change_60d" | "turnover_rate" | "breadth";
type Mode = "balanced" | "conservative" | "aggressive";
type StockSortKey = "formula_score" | "today_change_percent" | "change_5d" | "change_20d" | "change_60d";

const sortOptions: Array<{ value: SortKey; label: string }> = [
  { value: "score", label: "强度" },
  { value: "change_percent", label: "今日涨幅" },
  { value: "change_60d", label: "60日涨幅" },
  { value: "turnover_rate", label: "换手率" },
  { value: "breadth", label: "上涨广度" },
];

const modes: Array<{ value: Mode; label: string }> = [
  { value: "balanced", label: "均衡" },
  { value: "conservative", label: "稳健" },
  { value: "aggressive", label: "进攻" },
];

const stockSortOptions: Array<{ value: StockSortKey; label: string }> = [
  { value: "formula_score", label: "综合分" },
  { value: "today_change_percent", label: "今日" },
  { value: "change_5d", label: "5日" },
  { value: "change_20d", label: "20日" },
  { value: "change_60d", label: "60日" },
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

function topRisk(item: FormulaRankingItem) {
  if (item.risks?.length) return item.risks[0];
  return item.action || "--";
}

export default function SectorsPage() {
  const [data, setData] = useState<{ sectors: SectorItem[]; coverage_count: number; source: string; generated_at?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [selected, setSelected] = useState<SectorItem | null>(null);
  const [history, setHistory] = useState<SectorHistoryResult | null>(null);
  const [constituents, setConstituents] = useState<SectorConstituentsResult | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [constituentsLoading, setConstituentsLoading] = useState(false);
  const [mode, setMode] = useState<Mode>("balanced");
  const [stockSortKey, setStockSortKey] = useState<StockSortKey>("formula_score");
  const [mounted, setMounted] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.getSectors();
      setData(response.result);
      setMessage("");
      setSelected((current) => current || response.result.sectors[0] || null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加载板块失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setMounted(true);
    void load();
  }, []);

  useEffect(() => {
    if (!selected) return;
    setHistoryLoading(true);
    api
      .getSectorHistory(selected.code)
      .then((response) => setHistory(response.result))
      .catch((error) => setMessage(error instanceof Error ? error.message : "加载板块走势失败"))
      .finally(() => setHistoryLoading(false));
  }, [selected]);

  useEffect(() => {
    if (!selected) return;
    setConstituentsLoading(true);
    setConstituents(null);
    api
      .getSectorConstituents(selected.code, 120, mode)
      .then((response) => setConstituents(response.result))
      .catch((error) => setMessage(error instanceof Error ? error.message : "加载成分股评分失败"))
      .finally(() => setConstituentsLoading(false));
  }, [selected, mode]);

  const sectors = useMemo(
    () =>
      [...(data?.sectors || [])].sort(
        (left, right) => (right[sortKey] ?? Number.NEGATIVE_INFINITY) - (left[sortKey] ?? Number.NEGATIVE_INFINITY)
      ),
    [data, sortKey]
  );

  const chartData = useMemo(() => {
    const first = history?.bars.find((bar) => typeof bar.close === "number")?.close;
    if (!first) return [];
    return history?.bars.map((bar) => ({
      date: bar.date.slice(5),
      trend: typeof bar.close === "number" ? Number(((bar.close / first - 1) * 100).toFixed(2)) : null,
    })) || [];
  }, [history]);

  const rankedStocks = useMemo(
    () =>
      [...(constituents?.items || [])].sort(
        (left, right) => (right[stockSortKey] ?? Number.NEGATIVE_INFINITY) - (left[stockSortKey] ?? Number.NEGATIVE_INFINITY)
      ),
    [constituents, stockSortKey]
  );

  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col gap-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">板块分析</h1>
            <p className="text-muted-foreground">完整沪深板块强弱、市场广度、领涨股票与历史走势。</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={load} disabled={loading}>
              {loading ? <Loader2 data-icon="inline-start" className="animate-spin" /> : <RefreshCw data-icon="inline-start" />}
              刷新
            </Button>
            <Link href="/stock-picker" className={buttonVariants()}>
              <Target data-icon="inline-start" />公式选股
            </Link>
          </div>
        </div>

        {message && <div className="rounded-lg border px-4 py-3 text-sm">{message}</div>}

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardDescription>完整板块数量</CardDescription>
              <CardTitle className="text-2xl">{data?.coverage_count ?? "--"}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>当前最强板块</CardDescription>
              <CardTitle className="text-lg">{sectors[0]?.name || "--"}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>数据口径</CardDescription>
              <CardTitle className="text-sm">{data?.source || "--"}</CardTitle>
            </CardHeader>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Activity />{selected?.name || "板块"}走势</CardTitle>
            <CardDescription>点击下方任意板块切换曲线，收益均按当前区间首日归一化。</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-4 flex flex-wrap gap-2">
              <Badge variant="outline">5日 {percent(history?.change_5d)}</Badge>
              <Badge variant="outline">20日 {percent(history?.change_20d)}</Badge>
              <Badge variant="outline">60日 {percent(history?.change_60d)}</Badge>
            </div>
            <div className="h-72">
              {historyLoading ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />加载走势
                </div>
              ) : mounted ? (
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="date" minTickGap={24} tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={(value) => `${value}%`} width={56} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(value) => [`${Number(value).toFixed(2)}%`, "区间涨幅"]} />
                    <Line type="monotone" dataKey="trend" stroke="#2563eb" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2"><Calculator />{selected?.name || "板块"}成分股评分</CardTitle>
                <CardDescription>只保留沪深主板股票，按公式选股模型在当前板块内重新排序。</CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <div className="flex rounded-md border p-1">
                  {modes.map((item) => (
                    <Button
                      key={item.value}
                      size="sm"
                      variant={mode === item.value ? "secondary" : "ghost"}
                      onClick={() => setMode(item.value)}
                    >
                      {item.label}
                    </Button>
                  ))}
                </div>
                <div className="flex flex-wrap rounded-md border p-1">
                  {stockSortOptions.map((item) => (
                    <Button
                      key={item.value}
                      size="sm"
                      variant={stockSortKey === item.value ? "secondary" : "ghost"}
                      onClick={() => setStockSortKey(item.value)}
                    >
                      {item.label}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <div className="mb-3 flex flex-wrap gap-2 text-sm text-muted-foreground">
              <Badge variant="outline">成分股 {rankedStocks.length}/{constituents?.total ?? "--"}</Badge>
              <Badge variant="outline">补算走势 {constituents?.history_enriched_count ?? 0}</Badge>
              <Badge variant="outline">{constituents?.source || "东方财富板块成分股"}</Badge>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-14">排名</TableHead>
                  <TableHead>股票</TableHead>
                  <TableHead>公式分</TableHead>
                  <TableHead>建议</TableHead>
                  <TableHead>今日</TableHead>
                  <TableHead>5日</TableHead>
                  <TableHead>20日</TableHead>
                  <TableHead>60日</TableHead>
                  <TableHead>量比</TableHead>
                  <TableHead>换手</TableHead>
                  <TableHead>PE/PB</TableHead>
                  <TableHead className="min-w-48">风险/动作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {constituentsLoading ? (
                  <TableRow>
                    <TableCell colSpan={12} className="h-24 text-center text-muted-foreground">
                      <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" />
                      正在计算板块内排名
                    </TableCell>
                  </TableRow>
                ) : rankedStocks.length ? (
                  rankedStocks.map((item, index) => (
                    <TableRow key={`${item.market}-${item.ticker}`}>
                      <TableCell className="font-medium tabular-nums">{index + 1}</TableCell>
                      <TableCell>
                        <Link href={`/stock/${item.ticker}`} className="font-medium hover:underline">
                          {item.name || item.ticker}
                        </Link>
                        <div className="text-xs text-muted-foreground">{item.ticker}</div>
                      </TableCell>
                      <TableCell>
                        <span className={cn("text-lg font-semibold tabular-nums", scoreTone(item.formula_score))}>
                          {item.formula_score.toFixed(1)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={recommendationVariant(item.recommendation)}>
                          {item.recommendation}
                        </Badge>
                      </TableCell>
                      <TableCell><PercentValue value={item.today_change_percent} /></TableCell>
                      <TableCell><PercentValue value={item.change_5d} /></TableCell>
                      <TableCell><PercentValue value={item.change_20d} /></TableCell>
                      <TableCell><PercentValue value={item.change_60d} /></TableCell>
                      <TableCell>{number(item.volume_ratio)}</TableCell>
                      <TableCell>{percent(item.turnover_rate)}</TableCell>
                      <TableCell>
                        <div className="tabular-nums">{number(item.pe_ratio, 1)}</div>
                        <div className="text-xs text-muted-foreground">PB {number(item.pb_ratio, 1)}</div>
                      </TableCell>
                      <TableCell className="max-w-64">
                        <div className="line-clamp-2 text-sm text-muted-foreground">{topRisk(item)}</div>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={12} className="h-24 text-center text-muted-foreground">
                      当前板块没有符合沪深主板代码规则的成分股
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2"><ArrowDownUp />板块排序</CardTitle>
                <CardDescription>强度综合今日涨幅、上涨家数占比和换手率。</CardDescription>
              </div>
              <div className="flex flex-wrap rounded-md border p-1">
                {sortOptions.map((option) => (
                  <Button
                    key={option.value}
                    size="sm"
                    variant={sortKey === option.value ? "secondary" : "ghost"}
                    onClick={() => setSortKey(option.value)}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>排名</TableHead>
                  <TableHead>板块</TableHead>
                  <TableHead>强度</TableHead>
                  <TableHead>今日</TableHead>
                  <TableHead>60日</TableHead>
                  <TableHead>换手</TableHead>
                  <TableHead>上涨/下跌</TableHead>
                  <TableHead>上涨广度</TableHead>
                  <TableHead>领涨股票</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sectors.map((sector, index) => (
                  <TableRow
                    key={sector.code}
                    className={cn("cursor-pointer", selected?.code === sector.code && "bg-muted/60")}
                    onClick={() => setSelected(sector)}
                  >
                    <TableCell>{index + 1}</TableCell>
                    <TableCell className="font-medium">{sector.name}</TableCell>
                    <TableCell>{sector.score?.toFixed(1) ?? "--"}</TableCell>
                    <TableCell><PercentValue value={sector.change_percent} /></TableCell>
                    <TableCell><PercentValue value={sector.change_60d} /></TableCell>
                    <TableCell>{percent(sector.turnover_rate)}</TableCell>
                    <TableCell>{sector.up_count ?? 0}/{sector.down_count ?? 0}</TableCell>
                    <TableCell>{percent(sector.breadth)}</TableCell>
                    <TableCell>
                      {sector.leader?.ticker ? (
                        <Link
                          href={`/stock/${sector.leader.ticker}`}
                          className="hover:underline"
                          onClick={(event) => event.stopPropagation()}
                        >
                          {sector.leader.name || sector.leader.ticker}
                          <span className="ml-2 text-xs text-muted-foreground">
                            {percent(sector.leader.today_change_percent)}
                          </span>
                        </Link>
                      ) : "--"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </main>
    </>
  );
}

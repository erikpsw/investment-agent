"use client";

import { useId, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Flame,
  Gauge,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  Area,
  AreaChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useMarketSentiment } from "@/hooks/use-market";
import { api, type MarketSentimentItem } from "@/lib/api";
import {
  formatSentimentDelta,
  gaugeArcAngle,
  getRegimeMeta,
  resonanceBadgeMeta,
} from "@/lib/sentiment";
import { cn, formatNumber, formatPercent } from "@/lib/utils";

function SentimentGauge({
  score,
  label,
  regime,
}: {
  score: number;
  label: string;
  regime: string;
}) {
  const gradId = useId();
  const meta = getRegimeMeta(regime);
  const angleDeg = gaugeArcAngle(score);

  return (
    <div className="flex flex-col items-center">
      <svg
        viewBox="0 0 200 118"
        className="w-full max-w-[210px] overflow-visible"
        role="img"
        aria-label={`市场情绪温度 ${score.toFixed(1)} 分，状态 ${label}`}
      >
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#0ea5e9" />
            <stop offset="28%" stopColor="#14b8a6" />
            <stop offset="50%" stopColor="#f59e0b" />
            <stop offset="75%" stopColor="#f97316" />
            <stop offset="100%" stopColor="#ef4444" />
          </linearGradient>
        </defs>

        {/* Background track */}
        <path
          d="M 22 100 A 78 78 0 0 1 178 100"
          fill="none"
          stroke="currentColor"
          strokeWidth="13"
          strokeLinecap="round"
          className="text-muted/60"
        />
        {/* Temperature gradient arc */}
        <path
          d="M 22 100 A 78 78 0 0 1 178 100"
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth="13"
          strokeLinecap="round"
          opacity={0.92}
        />

        {/* Tick labels */}
        <text
          x="16"
          y="115"
          fontSize="10"
          fill="currentColor"
          className="text-muted-foreground"
        >
          0 冰点
        </text>
        <text
          x="94"
          y="14"
          fontSize="10"
          textAnchor="middle"
          fill="currentColor"
          className="text-muted-foreground"
        >
          50
        </text>
        <text
          x="184"
          y="115"
          fontSize="10"
          textAnchor="end"
          fill="currentColor"
          className="text-muted-foreground"
        >
          100 过热
        </text>

        {/* Needle rotated around (100, 100) */}
        <g transform={`translate(100, 100) rotate(${angleDeg})`}>
          <line
            x1="0"
            y1="6"
            x2="0"
            y2="-63"
            stroke={meta.accentHex}
            strokeWidth="3"
            strokeLinecap="round"
          />
          <circle cx="0" cy="0" r="6" fill={meta.accentHex} />
          <circle cx="0" cy="0" r="2.5" className="fill-background" />
        </g>
      </svg>

      <div className="-mt-1 flex items-baseline gap-2">
        <span className="text-3xl font-bold tracking-tight tabular-nums">
          {score.toFixed(1)}
        </span>
        <Badge variant="outline" className={cn("font-medium", meta.badgeClass)}>
          {label}
        </Badge>
      </div>
    </div>
  );
}

function MarketSentimentCard({ item }: { item: MarketSentimentItem }) {
  const [open, setOpen] = useState(false);
  const sparkId = useId();
  const meta = getRegimeMeta(item.regime);
  const resMeta = resonanceBadgeMeta(item.resonance.signal);

  const chg = item.benchmark.change_percent;
  const isUp = (chg ?? 0) > 0;
  const isDown = (chg ?? 0) < 0;

  return (
    <Card
      data-testid={`sentiment-card-${item.market}`}
      className={cn("flex flex-col justify-between transition-colors", meta.ringClass)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{item.market}</Badge>
              <CardTitle className="text-base font-semibold">
                {item.name}情绪温度
              </CardTitle>
              {item.stale && (
                <Badge variant="outline" className="text-[11px]">
                  快照
                </Badge>
              )}
            </div>
            <CardDescription className="mt-1 flex items-center gap-2 text-xs">
              <span>{item.benchmark.name}</span>
              <span className="font-medium text-foreground tabular-nums">
                {item.benchmark.price != null
                  ? formatNumber(item.benchmark.price, 2)
                  : "--"}
              </span>
              {chg != null && (
                <span
                  className={cn(
                    "inline-flex items-center gap-0.5 tabular-nums",
                    isUp
                      ? "text-green-600 dark:text-green-400"
                      : isDown
                        ? "text-red-600 dark:text-red-400"
                        : "text-muted-foreground",
                  )}
                >
                  {isUp ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : isDown ? (
                    <TrendingDown className="h-3 w-3" />
                  ) : null}
                  {formatPercent(chg)}
                </span>
              )}
            </CardDescription>
          </div>

          <div className="text-right text-[11px] text-muted-foreground tabular-nums">
            {item.smoothed_score != null && (
              <div>5日平滑 {item.smoothed_score.toFixed(1)}</div>
            )}
            <div>
              日 {formatSentimentDelta(item.delta_1d)} · 周{" "}
              {formatSentimentDelta(item.delta_1w)}
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <SentimentGauge score={item.score} label={item.label} regime={item.regime} />

        {/* Resonance Alert */}
        <div
          data-testid={`sentiment-resonance-${item.market}`}
          className={cn("rounded-lg border p-2.5 text-xs", resMeta.containerClass)}
        >
          <div className="flex items-center justify-between gap-2 font-medium">
            <span className="flex items-center gap-1.5">
              {resMeta.tone === "right_turn" ? (
                <TrendingUp className="h-3.5 w-3.5 shrink-0" />
              ) : resMeta.tone === "bottom" ? (
                <Sparkles className="h-3.5 w-3.5 shrink-0" />
              ) : resMeta.tone === "top" ? (
                <Flame className="h-3.5 w-3.5 shrink-0" />
              ) : (
                <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
              )}
              {item.resonance.label}
            </span>
          </div>
          {item.resonance.triggers.length > 0 && (
            <ul className="mt-1.5 space-y-1 pl-4 text-[11px] opacity-90 list-disc">
              {item.resonance.triggers.map((trigger, idx) => (
                <li key={idx}>{trigger}</li>
              ))}
            </ul>
          )}
        </div>

        {/* Position Guidance */}
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="text-muted-foreground">参考权益仓位区间</span>
            <span className="font-semibold text-foreground tabular-nums">
              {item.position_range}
            </span>
          </div>
          <div className="relative mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn("absolute top-0 h-full rounded-full transition-all", meta.barClass)}
              style={{
                left: `${item.position_min}%`,
                width: `${Math.max(8, item.position_max - item.position_min)}%`,
              }}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{item.action}</p>
          {item.trend_filter && (
            <div className="mt-2 flex items-center gap-1.5">
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] font-normal",
                  item.trend_filter.above_ma200
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                    : "border-amber-500/35 bg-amber-500/10 text-amber-700 dark:text-amber-300",
                )}
              >
                {item.trend_filter.label}
              </Badge>
            </div>
          )}
        </div>

        {/* 60-day sentiment history sparkline */}
        {item.history.length > 1 && (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span>近 60 日情绪走势</span>
              <span>虚线：20 恐慌底 / 80 过热顶</span>
            </div>
            <div className="h-24 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={item.history}
                  margin={{ top: 6, right: 4, left: 4, bottom: 2 }}
                >
                  <defs>
                    <linearGradient id={sparkId} x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor={meta.accentHex}
                        stopOpacity={0.35}
                      />
                      <stop
                        offset="95%"
                        stopColor={meta.accentHex}
                        stopOpacity={0.02}
                      />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" hide />
                  <YAxis domain={[0, 100]} hide />
                  <ReferenceLine
                    y={20}
                    stroke="#0ea5e9"
                    strokeDasharray="3 3"
                    strokeOpacity={0.65}
                  />
                  <ReferenceLine
                    y={80}
                    stroke="#ef4444"
                    strokeDasharray="3 3"
                    strokeOpacity={0.65}
                  />
                  <Tooltip
                    formatter={(val) => [
                      `${Number(val).toFixed(1)} 分`,
                      "情绪温度",
                    ]}
                    labelFormatter={(label) => `日期：${String(label)}`}
                    contentStyle={{
                      fontSize: "12px",
                      borderRadius: "8px",
                      padding: "6px 10px",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke={meta.accentHex}
                    strokeWidth={2}
                    fill={`url(#${sparkId})`}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Expandable Factor Breakdown */}
        <Collapsible open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-full justify-between text-xs text-muted-foreground hover:text-foreground"
            >
              <span>展开量化因子明细 ({item.factors.length} 项)</span>
              {open ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-2.5 border-t pt-3">
            {item.factors.map((factor) => (
              <div key={factor.key} className="space-y-1 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">
                    {factor.name}
                    <span className="ml-1 text-[11px] font-normal text-muted-foreground">
                      ({Math.round(factor.weight * 100)}%)
                    </span>
                  </span>
                  <span className="font-semibold tabular-nums">
                    {factor.value}{" "}
                    <span className="text-[11px] font-normal text-muted-foreground">
                      · {factor.score.toFixed(0)}分
                    </span>
                  </span>
                </div>
                <Progress value={factor.score} className="gap-1" />
                <p className="text-[11px] text-muted-foreground">{factor.detail}</p>
              </div>
            ))}

            {item.sub_metrics.length > 0 && (
              <div className="rounded-md bg-muted/40 p-2.5">
                <p className="mb-2 text-[11px] font-medium text-muted-foreground">
                  CNN 官方 7 大子指标拆解
                </p>
                <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                  {item.sub_metrics.map((sub) => (
                    <div
                      key={sub.key}
                      className="flex items-center justify-between rounded bg-background/80 px-2 py-1"
                    >
                      <span className="truncate">{sub.name}</span>
                      <span className="ml-1 shrink-0 font-medium tabular-nums">
                        {sub.score.toFixed(0)} ({sub.rating})
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-1 text-[10px] text-muted-foreground">
              <span>{item.source}</span>
              <span>口径截至 {item.as_of ?? "--"}</span>
            </div>
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
}

export function MarketSentimentPanel() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, isFetching, refetch } = useMarketSentiment();
  const [manualRefreshing, setManualRefreshing] = useState(false);

  const handleForceRefresh = async () => {
    setManualRefreshing(true);
    try {
      const fresh = await api.getMarketSentiment(true);
      queryClient.setQueryData(["market-sentiment"], fresh);
    } catch {
      await refetch();
    } finally {
      setManualRefreshing(false);
    }
  };

  if (isLoading) {
    return (
      <Card data-testid="market-sentiment-skeleton">
        <CardHeader className="pb-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {[1, 2, 3].map((idx) => (
            <Skeleton key={idx} className="h-80 rounded-xl" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (isError || !data?.result?.markets?.length) {
    return (
      <Card data-testid="market-sentiment-error">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Gauge className="h-5 w-5 text-primary" />
            大盘情绪与仓位风向标
          </CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
          <span className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            大盘情绪指标暂时不可用
          </span>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            重试
          </Button>
        </CardContent>
      </Card>
    );
  }

  const result = data.result;
  const spinning = isFetching || manualRefreshing;

  return (
    <Card data-testid="market-sentiment">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Gauge className="h-5 w-5 text-primary" />
              <CardTitle className="text-lg">大盘情绪与仓位风向标</CardTitle>
              {result.stale && <Badge variant="outline">部分使用历史快照</Badge>}
            </div>
            <CardDescription className="mt-1">
              量化追踪 A 股 / 港股 / 美股市场温度（0 极度恐慌 → 100 极度贪婪）与多因子底部共振提示，辅助动态仓位管理
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>
              更新于{" "}
              {result.generated_at
                ? new Date(result.generated_at).toLocaleString("zh-CN")
                : "--"}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="刷新大盘情绪"
              onClick={handleForceRefresh}
              disabled={spinning}
            >
              <RefreshCw className={cn("h-4 w-4", spinning && "animate-spin")} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {result.markets.map((item) => (
            <MarketSentimentCard key={item.market} item={item} />
          ))}
        </div>
        <p className="text-center text-xs text-muted-foreground">
          情绪分值与参考仓位区间基于估值分位、隐含/实现波动率、资金流及市场宽度量化合成，仅作仓位纪律参考，不构成投资建议。
        </p>
      </CardContent>
    </Card>
  );
}

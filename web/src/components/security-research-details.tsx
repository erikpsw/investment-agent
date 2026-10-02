"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CandlestickChart } from "@/components/charts/candlestick-chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SecurityResearch } from "@/lib/api";

const PERIODS = [5, 10, 20, 60, 250] as const;

function number(value?: number | null, digits = 2) {
  return value == null || Number.isNaN(value) ? "--" : value.toFixed(digits);
}

function percent(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function changeClass(value?: number | null) {
  if ((value || 0) > 0) return "text-green-600";
  if ((value || 0) < 0) return "text-red-600";
  return "text-muted-foreground";
}

export function SecurityResearchDetails({
  research,
  defaultExpanded = false,
  showNews = true,
  ticker,
}: {
  research?: SecurityResearch | null;
  defaultExpanded?: boolean;
  showNews?: boolean;
  ticker?: string;
}) {
  const [longPeriod, setLongPeriod] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>(20);
  const history = useMemo(
    () => (research?.history || []).slice(-(period + 1)),
    [period, research?.history],
  );

  if (!research) {
    return <div className="text-xs text-muted-foreground">暂无走势数据</div>;
  }

  return (
    <details open={expanded} onToggle={event => setExpanded(event.currentTarget.open)} className="w-full min-w-0 max-w-full overflow-hidden rounded-lg border bg-background p-3">
      <summary className="cursor-pointer text-sm font-medium">
        走势与关键数据
      </summary>
      <div className="mt-3 min-w-0 max-w-full space-y-4 overflow-hidden">
        <div className="flex flex-wrap gap-2">
          {PERIODS.map((days) => {
            const value =
              research.returns?.[
                `${days}d` as keyof NonNullable<SecurityResearch["returns"]>
              ];
            return (
              <Button
                key={days}
                type="button"
                size="sm"
                className="min-h-11"
                variant={period === days ? "default" : "outline"}
                onClick={() => { setLongPeriod(null); setPeriod(days); }}
              >
                {days}日{" "}
                <span className={changeClass(value)}>{percent(value)}</span>
              </Button>
            );
          })}
        </div>

        {ticker && <div className="flex flex-wrap gap-2">{[["5y", "5年"], ["10y", "10年"], ["max", "全部历史"]].map(([value, label]) => <Button key={value} className="min-h-11" variant={longPeriod === value ? "default" : "outline"} onClick={() => setLongPeriod(value)}>{label}</Button>)}</div>}
        {ticker && longPeriod ? <CandlestickChart ticker={ticker} period={longPeriod} height={320} /> : <div className="h-56 w-full min-w-0 rounded-md bg-muted/20 p-2">
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                <XAxis dataKey="time" hide />
                <YAxis
                  domain={["auto", "auto"]}
                  width={52}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip formatter={(value) => number(Number(value))} />
                <Line
                  dataKey="close"
                  type="monotone"
                  stroke="var(--color-primary)"
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              暂无可绘制的日线数据
            </div>
          )}
        </div>}

        <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
          <Metric label="MA5" value={number(research.moving_averages?.ma5)} />
          <Metric label="MA10" value={number(research.moving_averages?.ma10)} />
          <Metric label="MA20" value={number(research.moving_averages?.ma20)} />
          <Metric label="MA60" value={number(research.moving_averages?.ma60)} />
          <Metric
            label="MA250"
            value={number(research.moving_averages?.ma250)}
          />
          <Metric
            label="20日波动率"
            value={percent(research.technical?.volatility_20d)}
          />
          <Metric
            label="60日波动率"
            value={percent(research.technical?.volatility_60d)}
          />
          <Metric label="RSI14" value={number(research.technical?.rsi14)} />
          <Metric
            label="量比(20日)"
            value={number(research.technical?.volume_ratio_20d)}
          />
          <Metric
            label="250日最高"
            value={number(research.technical?.high_250d)}
          />
          <Metric
            label="250日最低"
            value={number(research.technical?.low_250d)}
          />
          <Metric
            label="最大回撤"
            value={percent(research.technical?.max_drawdown_250d)}
          />
          <Metric
            label="距250日高点"
            value={percent(research.technical?.distance_to_high_250d)}
          />
        </div>

        {showNews && research.recent_news && research.recent_news.length > 0 && (
          <div className="min-w-0 max-w-full space-y-2 overflow-hidden">
            <div className="text-sm font-medium">最近新闻</div>
            {research.recent_news.slice(0, 5).map((article, index) => (
              <a
                key={`${article.link || article.title}-${index}`}
                href={article.link || "#"}
                target="_blank"
                rel="noreferrer"
                className="block min-w-0 max-w-full overflow-hidden rounded-md border p-2 text-sm hover:bg-muted/50"
              >
                <div className="break-words font-medium [overflow-wrap:anywhere]">
                  {article.title || "--"}
                </div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  {article.source && (
                    <Badge variant="outline">{article.source}</Badge>
                  )}
                  {article.published && <span>{article.published}</span>}
                </div>
                {article.summary && (
                  <p className="mt-1 line-clamp-2 break-words text-muted-foreground [overflow-wrap:anywhere]">
                    {article.summary}
                  </p>
                )}
              </a>
            ))}
          </div>
        )}

        {research.errors && research.errors.length > 0 && (
          <div className="rounded-md bg-amber-500/10 p-2 text-xs text-amber-700">
            数据问题：{research.errors.join("；")}
          </div>
        )}
      </div>
    </details>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/40 p-2">
      <div className="text-muted-foreground">{label}</div>
      <div className="mt-1 font-medium tabular-nums">{value}</div>
    </div>
  );
}

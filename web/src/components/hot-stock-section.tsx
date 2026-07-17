"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Flame, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type HotStockMarket, type HotStockMode } from "@/lib/api";


const MARKET_LABELS: Record<HotStockMarket, string> = {
  CN: "A 股",
  HK: "港股",
  US: "美股",
};

function formatAmount(value: number) {
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return value.toFixed(0);
}

export function HotStockSection({
  market,
  mode,
}: {
  market: HotStockMarket;
  mode: HotStockMode;
}) {
  const query = useQuery({
    queryKey: ["hot-stocks", market, mode],
    queryFn: () => api.getHotStocks(market, mode, 6),
    staleTime: 10 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
  });

  if (query.isLoading) {
    return (
      <Card>
        <CardHeader><Skeleton className="h-6 w-32" /></CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, index) => <Skeleton key={index} className="h-28" />)}
        </CardContent>
      </Card>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Card>
        <CardHeader><CardTitle>{MARKET_LABELS[market]}热门股票</CardTitle></CardHeader>
        <CardContent className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
          <span className="flex items-center gap-2"><AlertCircle className="h-4 w-4" />该市场热门数据暂时不可用</span>
          <Button variant="outline" size="sm" onClick={() => query.refetch()}><RefreshCw className="mr-2 h-4 w-4" />重试</Button>
        </CardContent>
      </Card>
    );
  }

  const result = query.data.result;
  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2"><Flame className="h-5 w-5 text-orange-500" />{MARKET_LABELS[market]}热门股票</CardTitle>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {result.stale && <Badge variant="outline">历史快照</Badge>}
            <span>{result.generated_at ? new Date(result.generated_at).toLocaleString("zh-CN") : "--"}</span>
          </div>
        </div>
        <div className="text-xs text-muted-foreground">{result.source}</div>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {result.items.map((item, index) => {
          const positive = item.today_change_percent > 0;
          const negative = item.today_change_percent < 0;
          return (
            <Link
              key={item.ticker}
              href={`/stock/${encodeURIComponent(item.ticker)}`}
              className="rounded-lg border p-3 transition-colors hover:border-primary hover:bg-muted/30"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-medium"><span className="mr-2 text-muted-foreground">{index + 1}</span>{item.name}</div>
                  <div className="text-xs text-muted-foreground">{item.ticker}</div>
                </div>
                <Badge variant="secondary">热度 {item.heat_score.toFixed(0)}</Badge>
              </div>
              <div className="mt-3 flex items-end justify-between gap-2">
                <div className="text-lg font-semibold tabular-nums">{item.price.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}</div>
                <div className={`text-sm font-medium tabular-nums ${positive ? "text-green-600" : negative ? "text-red-600" : ""}`}>
                  {positive ? "+" : ""}{item.today_change_percent.toFixed(2)}%
                </div>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">成交额 {formatAmount(item.amount)}</div>
            </Link>
          );
        })}
      </CardContent>
    </Card>
  );
}

"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Minus, TrendingDown, TrendingUp } from "lucide-react";

import { CandlestickChart } from "@/components/charts/candlestick-chart";
import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMarketOverview } from "@/hooks/use-market";
import { cn, formatNumber, formatPercent } from "@/lib/utils";
import { findMarketIndex, INDEX_PERIODS, type IndexPeriod } from "@/lib/market-index";


export default function MarketIndexPage() {
  const params = useParams<{ ticker: string }>();
  const ticker = useMemo(() => decodeURIComponent(params.ticker), [params.ticker]);
  const metadata = findMarketIndex(ticker);
  const [period, setPeriod] = useState<IndexPeriod>("1mo");
  const { data, isLoading, error } = useMarketOverview();
  const quote = data?.indices.find((index) => index.history_ticker === ticker);
  const changePercent = quote?.change_percent;
  const TrendIcon = (changePercent ?? 0) > 0
    ? TrendingUp
    : (changePercent ?? 0) < 0
      ? TrendingDown
      : Minus;
  const trendClass = (changePercent ?? 0) > 0
    ? "text-green-600 dark:text-green-400"
    : (changePercent ?? 0) < 0
      ? "text-red-600 dark:text-red-400"
      : "text-muted-foreground";

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 space-y-6 p-4 sm:p-6">
        <Button variant="ghost" nativeButton={false} render={<Link href="/" />}>
          <ArrowLeft className="mr-2 h-4 w-4" />返回市场概览
        </Button>

        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle>{metadata?.name || quote?.name || ticker}</CardTitle>
                  <Badge variant="outline">{metadata?.market || quote?.market || "--"}</Badge>
                </div>
                <CardDescription>{ticker}</CardDescription>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold tabular-nums">
                  {quote?.price != null ? formatNumber(quote.price, 2) : isLoading ? "加载中..." : "--"}
                </div>
                <div className={cn("mt-1 flex items-center justify-end gap-1 text-sm", trendClass)}>
                  <TrendIcon className="h-4 w-4" />
                  <span>{quote?.change != null ? formatNumber(quote.change, 2) : "--"}</span>
                  <span>{changePercent != null ? formatPercent(changePercent) : "--"}</span>
                </div>
              </div>
            </div>
            {error && <CardDescription>实时指数行情暂不可用，仍可查看历史走势。</CardDescription>}
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {INDEX_PERIODS.map((item) => (
                <Button
                  key={item.value}
                  size="sm"
                  variant={period === item.value ? "default" : "outline"}
                  onClick={() => setPeriod(item.value)}
                >
                  {item.label}
                </Button>
              ))}
            </div>
            <CandlestickChart ticker={ticker} period={period} interval="1d" height={460} />
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

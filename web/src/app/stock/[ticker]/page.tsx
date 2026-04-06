"use client";

import { useState } from "react";
import { use } from "react";
import { ArrowLeft, RefreshCw, Star, Share2, Bot } from "lucide-react";
import Link from "next/link";
import { Header } from "@/components/header";
import { StockSearch } from "@/components/stock-search";
import { CandlestickChart } from "@/components/charts/candlestick-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuote } from "@/hooks/use-quote";
import { useFinancials } from "@/hooks/use-market";
import { cn, formatNumber, formatPercent, formatLargeNumber } from "@/lib/utils";

interface PageProps {
  params: Promise<{ ticker: string }>;
}

export default function StockDetailPage({ params }: PageProps) {
  const { ticker } = use(params);
  const decodedTicker = decodeURIComponent(ticker);
  const [searchOpen, setSearchOpen] = useState(false);
  const [period, setPeriod] = useState("1mo");

  const { data: quote, isLoading: quoteLoading, refetch } = useQuote(decodedTicker);
  const { data: financials, isLoading: financialsLoading } = useFinancials(decodedTicker);

  const isPositive = (quote?.change_percent ?? 0) > 0;
  const isNegative = (quote?.change_percent ?? 0) < 0;
  const trendColor = isPositive
    ? "text-green-600 dark:text-green-400"
    : isNegative
    ? "text-red-600 dark:text-red-400"
    : "text-muted-foreground";

  return (
    <>
      <Header onSearchClick={() => setSearchOpen(true)} />
      <StockSearch open={searchOpen} onOpenChange={setSearchOpen} />

      <div className="flex-1 p-6 space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>

          {quoteLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-4 w-20" />
            </div>
          ) : (
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold">
                  {quote?.name || decodedTicker}
                </h1>
                <Badge variant="outline">
                  {quote?.market === "CN"
                    ? "A股"
                    : quote?.market === "HK"
                    ? "港股"
                    : "美股"}
                </Badge>
              </div>
              <p className="text-muted-foreground">{decodedTicker}</p>
            </div>
          )}

          <div className="ml-auto flex items-center gap-2">
            <Button variant="outline" size="icon">
              <Star className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon">
              <Share2 className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle>实时行情</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {quote?.timestamp
                      ? new Date(quote.timestamp).toLocaleString("zh-CN")
                      : ""}
                  </p>
                </div>
              </CardHeader>
              <CardContent>
                {quoteLoading ? (
                  <div className="space-y-4">
                    <Skeleton className="h-12 w-32" />
                    <Skeleton className="h-6 w-24" />
                  </div>
                ) : (
                  <div className="flex items-end gap-8">
                    <div>
                      <p className="text-4xl font-bold tabular-nums">
                        {quote?.price ? formatNumber(quote.price, 2) : "--"}
                      </p>
                      <div className={cn("flex items-center gap-2 text-lg mt-1", trendColor)}>
                        <span className="font-medium">
                          {quote?.change ? formatNumber(quote.change, 2) : "--"}
                        </span>
                        <span>
                          ({quote?.change_percent ? formatPercent(quote.change_percent) : "--"})
                        </span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                      <div>
                        <span className="text-muted-foreground">开盘: </span>
                        <span className="font-medium">
                          {quote?.open ? formatNumber(quote.open, 2) : "--"}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">昨收: </span>
                        <span className="font-medium">
                          {quote?.prev_close ? formatNumber(quote.prev_close, 2) : "--"}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">最高: </span>
                        <span className="font-medium text-green-600">
                          {quote?.high ? formatNumber(quote.high, 2) : "--"}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">最低: </span>
                        <span className="font-medium text-red-600">
                          {quote?.low ? formatNumber(quote.low, 2) : "--"}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">成交量: </span>
                        <span className="font-medium">
                          {quote?.volume ? formatLargeNumber(quote.volume) : "--"}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">成交额: </span>
                        <span className="font-medium">
                          {quote?.amount ? formatLargeNumber(quote.amount * 10000) : "--"}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle>K线图</CardTitle>
                  <Tabs value={period} onValueChange={setPeriod}>
                    <TabsList className="h-8">
                      <TabsTrigger value="5d" className="text-xs px-2">5日</TabsTrigger>
                      <TabsTrigger value="1mo" className="text-xs px-2">1月</TabsTrigger>
                      <TabsTrigger value="3mo" className="text-xs px-2">3月</TabsTrigger>
                      <TabsTrigger value="6mo" className="text-xs px-2">6月</TabsTrigger>
                      <TabsTrigger value="1y" className="text-xs px-2">1年</TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>
              </CardHeader>
              <CardContent>
                <CandlestickChart ticker={decodedTicker} period={period} />
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>关键指标</CardTitle>
              </CardHeader>
              <CardContent>
                {financialsLoading ? (
                  <div className="space-y-3">
                    {[1, 2, 3, 4].map((i) => (
                      <div key={i} className="flex justify-between">
                        <Skeleton className="h-4 w-16" />
                        <Skeleton className="h-4 w-12" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <MetricRow label="市盈率 (PE)" value={quote?.pe_ratio || financials?.pe_ratio} />
                    <MetricRow label="市净率 (PB)" value={financials?.pb_ratio} />
                    <MetricRow label="净资产收益率 (ROE)" value={financials?.roe} percent />
                    <MetricRow label="毛利率" value={financials?.gross_margin} percent />
                    <MetricRow label="净利率" value={financials?.profit_margin} percent />
                    <MetricRow label="资产负债率" value={financials?.debt_ratio} percent />
                    <MetricRow
                      label="市值"
                      value={quote?.market_cap}
                      format={(v) => formatLargeNumber(v * 1e8)}
                    />
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>快捷操作</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Link href={`/stock/${encodeURIComponent(decodedTicker)}/analysis`}>
                  <Button className="w-full">
                    <Bot className="h-4 w-4 mr-2" />
                    AI 深度分析
                  </Button>
                </Link>
                <Button className="w-full" variant="outline">
                  添加到自选
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </>
  );
}

function MetricRow({
  label,
  value,
  percent,
  format,
}: {
  label: string;
  value?: number | null;
  percent?: boolean;
  format?: (v: number) => string;
}) {
  const displayValue = value == null
    ? "--"
    : format
    ? format(value)
    : percent
    ? `${formatNumber(value * 100, 2)}%`
    : formatNumber(value, 2);

  return (
    <div className="flex justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{displayValue}</span>
    </div>
  );
}


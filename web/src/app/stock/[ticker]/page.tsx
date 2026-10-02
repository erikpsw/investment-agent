"use client";

import { useState } from "react";
import { use } from "react";
import { ArrowLeft, RefreshCw, Share2, Bot } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { SecurityFundamentals } from "@/components/security-fundamentals";
import { AddToWatchlistButton } from "@/components/add-to-watchlist-button";
import { yahooQuoteUrl } from "@/lib/financial-reports";
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
  const [period, setPeriod] = useState("1y");
  const [message, setMessage] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const queryClient = useQueryClient();

  const { data: quote, isLoading: quoteLoading, refetch } = useQuote(decodedTicker);
  const { data: financials, isLoading: financialsLoading } = useFinancials(decodedTicker);
  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setMessage("个股链接已复制");
    } catch { setMessage("复制失败，请复制地址栏中的个股链接。"); }
  };
  const refresh = async () => {
    setRefreshing(true);
    setMessage("");
    try {
      await Promise.all([
        refetch({ throwOnError: true }),
        ...["history", "financials", "financial-history", "security-news", "security-reports"].map(key => queryClient.invalidateQueries({ queryKey: [key, decodedTicker] })),
      ]);
      setMessage("已完成数据刷新，暂缺数据会在对应区域显示。");
    } catch { setMessage("行情刷新失败，请重试。"); }
    finally { setRefreshing(false); }
  };

  const valuation = financials && (financials.pe_ratio != null || financials.pe_basis === "TTM") ? financials : quote;
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

      <div className="flex-1 p-3 sm:p-6 space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/dashboard">
            <Button variant="ghost" size="icon" aria-label="返回仪表盘">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>

          {quoteLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-4 w-20" />
            </div>
          ) : (
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-3">
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
              <a className="inline-flex min-h-11 items-center text-sm text-primary underline" href={yahooQuoteUrl(decodedTicker, quote?.market)} target="_blank" rel="noreferrer">Yahoo Finance ↗</a>
            </div>
          )}

          <div className="ml-auto flex items-center gap-2">
            <AddToWatchlistButton compact ticker={decodedTicker} name={quote?.name || ""} market={quote?.market} onResult={setMessage} />
            <Button variant="outline" size="icon" className="min-h-11 min-w-11" aria-label="复制个股链接" onClick={() => void share()}>
              <Share2 className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" className="min-h-11 min-w-11" aria-label="刷新个股数据" disabled={refreshing} onClick={() => void refresh()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>
        {message && <p role="status" className="rounded-md border p-3 text-sm">{message}</p>}

        <div className="grid min-w-0 gap-4 lg:grid-cols-3 sm:gap-6">
          <div className="min-w-0 lg:col-span-2 space-y-4 sm:space-y-6">
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
                  <div className="flex flex-wrap items-end gap-4 sm:gap-8">
                    <div>
                      <p className="text-4xl font-bold tabular-nums">
                        {quote?.price ? formatNumber(quote.price, 2) : "--"}
                      </p>
                      <div className={cn("flex items-center gap-2 text-lg mt-1", trendColor)}>
                        <span className="font-medium">
                          {quote?.change != null ? formatNumber(quote.change, 2) : "--"}
                        </span>
                        <span>
                          ({quote?.change_percent != null ? formatPercent(quote.change_percent) : "--"})
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
                          {quote?.amount != null ? formatLargeNumber(quote.amount) : "--"}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card data-testid="stock-chart-card" className="min-w-0">
              <CardHeader className="pb-2">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <CardTitle>K线图</CardTitle>
                  <Tabs value={period} onValueChange={setPeriod}>
                    <TabsList className="h-auto max-w-full flex-wrap">
                      <TabsTrigger value="5d" className="min-h-11 text-xs px-2">5日</TabsTrigger>
                      <TabsTrigger value="1mo" className="min-h-11 text-xs px-2">1月</TabsTrigger>
                      <TabsTrigger value="3mo" className="min-h-11 text-xs px-2">3月</TabsTrigger>
                      <TabsTrigger value="6mo" className="min-h-11 text-xs px-2">6月</TabsTrigger>
                      <TabsTrigger value="1y" className="min-h-11 text-xs px-2">1年</TabsTrigger>
                      <TabsTrigger value="5y" className="min-h-11 text-xs px-2">5年</TabsTrigger>
                      <TabsTrigger value="10y" className="min-h-11 text-xs px-2">10年</TabsTrigger>
                      <TabsTrigger value="max" className="min-h-11 text-xs px-2">全部</TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>
              </CardHeader>
              <CardContent className="min-w-0 px-3 sm:px-6">
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
                    <MetricRow label={`市盈率 (PE${valuation?.pe_basis ? ` · ${valuation.pe_basis}` : ""})`} value={valuation?.pe_ratio} />
                    <MetricRow label="每股收益 (EPS)" value={valuation?.eps} />
                    <p className="text-xs text-muted-foreground">估值来源：{valuation?.pe_source || "未提供"} · 行情来源：{quote?.source || "未提供"}</p>
                    <MetricRow label="市净率 (PB)" value={financials?.pb_ratio} />
                    <MetricRow label="净资产收益率 (ROE)" value={financials?.roe} percent />
                    <MetricRow label="毛利率" value={financials?.gross_margin} percent />
                    <MetricRow label="净利率" value={financials?.profit_margin} percent />
                    <MetricRow label="资产负债率" value={financials?.debt_ratio} percent />
                    <MetricRow
                      label="市值"
                      value={quote?.market_cap}
                      format={(v) => formatLargeNumber(v)}
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
                <Button className="w-full" disabled>
                  <Bot className="h-4 w-4 mr-2" />
                  AI 深度分析暂不可用
                </Button>
                <AddToWatchlistButton ticker={decodedTicker} name={quote?.name || ""} market={quote?.market} onResult={setMessage} />
              </CardContent>
            </Card>
          </div>
        </div>
        <SecurityFundamentals key={decodedTicker} ticker={decodedTicker} market={quote?.market} name={quote?.name || ""} />
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

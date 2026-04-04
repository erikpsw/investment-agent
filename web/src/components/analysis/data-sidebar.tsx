"use client";

import { useState, useEffect, useCallback } from "react";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  DollarSign,
  BarChart3,
  Building2,
  Newspaper,
  RefreshCw,
  ExternalLink,
  Clock,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn, formatNumber, formatPercent, formatLargeNumber } from "@/lib/utils";

interface NewsItem {
  title: string;
  link: string;
  source: string;
  published?: string;
  published_date?: string;
  summary?: string;
  thumbnail?: string;
}

interface Quote {
  ticker: string;
  name: string;
  price: number;
  change: number;
  change_percent: number;
  open?: number;
  high?: number;
  low?: number;
  prev_close?: number;
  volume?: number;
  amount?: number;
  market_cap?: number;
  pe_ratio?: number;
  market?: string;
  timestamp?: string;
}

interface Financials {
  pe_ratio?: number;
  pb_ratio?: number;
  roe?: number;
  gross_margin?: number;
  profit_margin?: number;
  debt_ratio?: number;
}

interface DataSidebarProps {
  ticker: string;
  quote?: Quote;
  quoteLoading: boolean;
  financials?: Financials;
  financialsLoading: boolean;
}

export function DataSidebar({
  ticker,
  quote,
  quoteLoading,
  financials,
  financialsLoading,
}: DataSidebarProps) {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);

  const fetchNews = useCallback(async () => {
    if (!ticker) return;
    setNewsLoading(true);
    try {
      const market = ticker.startsWith("sh") || ticker.startsWith("sz") 
        ? "CN" 
        : ticker.includes(".HK") 
        ? "HK" 
        : "US";
      const stockName = quote?.name || "";
      const params = new URLSearchParams({
        stock_name: stockName,
        market,
        limit: "5",
      });
      const res = await fetch(`http://localhost:8000/api/news/${ticker}?${params}`);
      if (res.ok) {
        const data = await res.json();
        setNews(data.news || []);
      }
    } catch (e) {
      console.error("Failed to fetch news:", e);
    } finally {
      setNewsLoading(false);
    }
  }, [ticker, quote?.name]);

  useEffect(() => {
    fetchNews();
  }, [fetchNews]);

  const isPositive = (quote?.change_percent ?? 0) > 0;
  const isNegative = (quote?.change_percent ?? 0) < 0;

  const TrendIcon = isPositive
    ? TrendingUp
    : isNegative
    ? TrendingDown
    : Minus;

  const trendColor = isPositive
    ? "text-green-600 dark:text-green-400"
    : isNegative
    ? "text-red-600 dark:text-red-400"
    : "text-muted-foreground";

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-4">
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <DollarSign className="h-4 w-4" />
                实时行情
              </CardTitle>
              {quote?.timestamp && (
                <span className="text-xs text-muted-foreground">
                  {new Date(quote.timestamp).toLocaleTimeString("zh-CN")}
                </span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {quoteLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-8 w-24" />
                <Skeleton className="h-4 w-16" />
              </div>
            ) : quote ? (
              <div className="space-y-3">
                <div>
                  <p className="text-2xl font-bold tabular-nums">
                    {formatNumber(quote.price, 2)}
                  </p>
                  <div className={cn("flex items-center gap-1 text-sm", trendColor)}>
                    <TrendIcon className="h-4 w-4" />
                    <span>{formatNumber(quote.change, 2)}</span>
                    <span>({formatPercent(quote.change_percent)})</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">开盘</span>
                      <span>{quote.open ? formatNumber(quote.open, 2) : "--"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">最高</span>
                      <span className="text-green-600">
                        {quote.high ? formatNumber(quote.high, 2) : "--"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">最低</span>
                      <span className="text-red-600">
                        {quote.low ? formatNumber(quote.low, 2) : "--"}
                      </span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">昨收</span>
                      <span>{quote.prev_close ? formatNumber(quote.prev_close, 2) : "--"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">成交量</span>
                      <span>{quote.volume ? formatLargeNumber(quote.volume) : "--"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">成交额</span>
                      <span>
                        {quote.amount ? formatLargeNumber(quote.amount * 10000) : "--"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">暂无数据</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              关键指标
            </CardTitle>
          </CardHeader>
          <CardContent>
            {financialsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex justify-between">
                    <Skeleton className="h-3 w-12" />
                    <Skeleton className="h-3 w-8" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-2 text-xs">
                <MetricRow
                  label="市盈率 (PE)"
                  value={quote?.pe_ratio || financials?.pe_ratio}
                />
                <MetricRow label="市净率 (PB)" value={financials?.pb_ratio} />
                <MetricRow label="ROE" value={financials?.roe} percent />
                <MetricRow label="毛利率" value={financials?.gross_margin} percent />
                <MetricRow label="净利率" value={financials?.profit_margin} percent />
                <MetricRow label="资产负债率" value={financials?.debt_ratio} percent />
                {quote?.market_cap && (
                  <MetricRow
                    label="市值"
                    value={quote.market_cap}
                    format={(v) => formatLargeNumber(v * 1e8)}
                  />
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              公司信息
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">代码</span>
                <span className="font-mono">{ticker}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">名称</span>
                <span>{quote?.name || "--"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">市场</span>
                <Badge variant="outline" className="text-xs h-5">
                  {quote?.market === "CN"
                    ? "A股"
                    : quote?.market === "HK"
                    ? "港股"
                    : quote?.market === "US"
                    ? "美股"
                    : "--"}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <Newspaper className="h-4 w-4" />
                相关资讯
              </CardTitle>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={fetchNews}
                disabled={newsLoading}
              >
                <RefreshCw className={cn("h-3 w-3", newsLoading && "animate-spin")} />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {newsLoading && news.length === 0 ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : news.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">
                暂无相关资讯
              </p>
            ) : (
              <div className="space-y-3">
                {news.map((item, i) => (
                  <a
                    key={i}
                    href={item.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block group"
                  >
                    <div className="text-xs space-y-1">
                      <p className="font-medium line-clamp-2 group-hover:text-primary transition-colors">
                        {item.title}
                      </p>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        {item.source && (
                          <span className="truncate max-w-[80px]">{item.source}</span>
                        )}
                        {item.published_date && (
                          <span className="flex items-center gap-0.5 shrink-0">
                            <Clock className="h-3 w-3" />
                            {formatRelativeTime(item.published_date)}
                          </span>
                        )}
                        <ExternalLink className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </ScrollArea>
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
  const displayValue =
    value == null
      ? "--"
      : format
      ? format(value)
      : percent
      ? `${formatNumber(value * 100, 2)}%`
      : formatNumber(value, 2);

  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{displayValue}</span>
    </div>
  );
}

function formatRelativeTime(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "刚刚";
    if (diffMins < 60) return `${diffMins}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;
    if (diffDays < 7) return `${diffDays}天前`;
    return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

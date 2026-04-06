"use client";

import Link from "next/link";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { StockQuote } from "@/lib/api";
import { cn, formatNumber, formatPercent } from "@/lib/utils";

interface StockCardProps {
  quote: StockQuote;
  showDetails?: boolean;
}

export function StockCard({ quote, showDetails = false }: StockCardProps) {
  const isPositive = (quote.change_percent ?? 0) > 0;
  const isNegative = (quote.change_percent ?? 0) < 0;
  const isZero = !isPositive && !isNegative;

  const TrendIcon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;
  const trendColor = isPositive
    ? "text-green-600 dark:text-green-400"
    : isNegative
    ? "text-red-600 dark:text-red-400"
    : "text-muted-foreground";

  const bgColor = isPositive
    ? "bg-green-50 dark:bg-green-950/20"
    : isNegative
    ? "bg-red-50 dark:bg-red-950/20"
    : "";

  return (
    <Link href={`/stock/${encodeURIComponent(quote.ticker)}`}>
      <Card
        data-testid="stock-card"
        className={cn(
          "transition-all hover:shadow-md hover:border-primary/50 cursor-pointer",
          bgColor
        )}
      >
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-semibold">
              {quote.name || quote.ticker}
            </CardTitle>
            <Badge variant="outline" className="text-xs">
              {quote.market === "CN" ? "A股" : quote.market === "HK" ? "港股" : "美股"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">{quote.ticker}</p>
        </CardHeader>
        <CardContent>
          <div className="flex items-end justify-between">
            <div>
              <p className="text-2xl font-bold tabular-nums">
                {quote.price ? formatNumber(quote.price, 2) : "--"}
              </p>
              <div className={cn("flex items-center gap-1 text-sm", trendColor)}>
                <TrendIcon className="h-4 w-4" />
                <span className="font-medium">
                  {quote.change ? formatNumber(quote.change, 2) : "--"}
                </span>
                <span>
                  ({quote.change_percent ? formatPercent(quote.change_percent) : "--"})
                </span>
              </div>
            </div>
            {showDetails && (
              <div className="text-right text-sm text-muted-foreground">
                <p>成交量: {quote.volume ? formatNumber(quote.volume / 10000, 1) + "万" : "--"}</p>
                <p>PE: {quote.pe_ratio ? formatNumber(quote.pe_ratio, 2) : "--"}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export function StockCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-5 w-12" />
        </div>
        <Skeleton className="h-4 w-16 mt-1" />
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between">
          <div>
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-4 w-24 mt-2" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

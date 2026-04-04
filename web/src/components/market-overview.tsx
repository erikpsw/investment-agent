"use client";

import { TrendingUp, TrendingDown, Minus, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useMarketOverview } from "@/hooks/use-market";
import { cn, formatNumber, formatPercent } from "@/lib/utils";

export function MarketOverview() {
  const { data, isLoading, refetch, isFetching } = useMarketOverview();

  if (isLoading) {
    return <MarketOverviewSkeleton />;
  }

  const indices = data?.indices || [];

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">市场概览</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw
              className={cn("h-4 w-4", isFetching && "animate-spin")}
            />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {indices.map((index) => {
            const isPositive = (index.change_percent ?? 0) > 0;
            const isNegative = (index.change_percent ?? 0) < 0;
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
              <div
                key={index.code}
                className="flex flex-col gap-1 p-3 rounded-lg bg-secondary/50"
              >
                <p className="text-sm font-medium text-muted-foreground">
                  {index.name}
                </p>
                <p className="text-lg font-bold tabular-nums">
                  {index.price ? formatNumber(index.price, 2) : "--"}
                </p>
                <div className={cn("flex items-center gap-1 text-sm", trendColor)}>
                  <TrendIcon className="h-3 w-3" />
                  <span>
                    {index.change_percent
                      ? formatPercent(index.change_percent)
                      : "--"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function MarketOverviewSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">市场概览</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex flex-col gap-1 p-3 rounded-lg bg-secondary/50">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-6 w-20" />
              <Skeleton className="h-4 w-12" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

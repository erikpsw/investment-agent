"use client";

import { useQuery } from "@tanstack/react-query";
import { Flame, Loader2, Plus, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type HotEtfSectorItem } from "@/lib/api";


function formatAmount(value: number) {
  if (value >= 1e8) return `${(value / 1e8).toFixed(1)}亿`;
  if (value >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return value.toFixed(0);
}

export function HotEtfSectors({ onAdd }: { onAdd: (item: HotEtfSectorItem) => void }) {
  const query = useQuery({
    queryKey: ["hot-etf-sectors"],
    queryFn: () => api.getHotEtfSectors(10),
    staleTime: 10 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2"><Flame className="h-5 w-5 text-orange-500" />A 股热门 ETF 板块</CardTitle>
            <CardDescription>每日收盘后更新板块排名，盘中价格最多每 10 分钟刷新。</CardDescription>
          </div>
          {query.data && (
            <div className="text-right text-xs text-muted-foreground">
              <div>{query.data.result.stale && <Badge variant="outline">历史快照</Badge>}</div>
              <div className="mt-1">{query.data.result.generated_at ? new Date(query.data.result.generated_at).toLocaleString("zh-CN") : "--"}</div>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <div className="flex items-center justify-center py-10 text-sm text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin" />加载 ETF 热门板块</div>
        ) : query.isError || !query.data ? (
          <div className="flex items-center justify-between rounded-lg border p-4 text-sm text-muted-foreground">
            <span>A 股 ETF 热门数据暂时不可用</span>
            <Button variant="outline" size="sm" onClick={() => query.refetch()}><RefreshCw className="mr-2 h-4 w-4" />重试</Button>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            {query.data.result.items.map((item) => (
              <div key={item.theme} className="rounded-lg border p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium">{item.theme}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{item.name} · {item.ticker}</div>
                  </div>
                  <Badge variant="secondary">{item.heat_score.toFixed(0)}</Badge>
                </div>
                <div className="mt-3 flex justify-between text-sm">
                  <span>{item.price.toFixed(3)}</span>
                  <span className={item.today_change_percent >= 0 ? "text-green-600" : "text-red-600"}>
                    {item.today_change_percent > 0 ? "+" : ""}{item.today_change_percent.toFixed(2)}%
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">成交额 {formatAmount(item.amount)}</div>
                <Button className="mt-3 w-full" variant="outline" size="sm" onClick={() => onAdd(item)}>
                  <Plus className="mr-2 h-4 w-4" />加入投资组合
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

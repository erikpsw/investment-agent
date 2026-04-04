"use client";

import { useState } from "react";
import { Search, TrendingUp, Sparkles } from "lucide-react";
import { Header } from "@/components/header";
import { StockSearch } from "@/components/stock-search";
import { MarketOverview } from "@/components/market-overview";
import { StockCard, StockCardSkeleton } from "@/components/stock-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useQuote } from "@/hooks/use-quote";

const HOT_STOCKS = [
  { ticker: "sh600519", name: "贵州茅台" },
  { ticker: "sh601318", name: "中国平安" },
  { ticker: "sz000858", name: "五粮液" },
  { ticker: "hk00700", name: "腾讯控股" },
  { ticker: "AAPL", name: "苹果" },
  { ticker: "MSFT", name: "微软" },
];

export default function DashboardPage() {
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <>
      <Header onSearchClick={() => setSearchOpen(true)} />
      <StockSearch open={searchOpen} onOpenChange={setSearchOpen} />

      <div className="flex-1 p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">投资仪表盘</h1>
            <p className="text-muted-foreground">
              实时追踪 A股、港股、美股行情
            </p>
          </div>
          <Button onClick={() => setSearchOpen(true)}>
            <Search className="mr-2 h-4 w-4" />
            搜索股票
          </Button>
        </div>

        <MarketOverview />

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-primary" />
                  <CardTitle>热门股票</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2">
                  {HOT_STOCKS.map((stock) => (
                    <HotStockCard key={stock.ticker} ticker={stock.ticker} />
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-primary" />
                  <CardTitle>快速搜索</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  支持中文名称、拼音、股票代码搜索
                </p>
                <div className="flex flex-wrap gap-2">
                  {["茅台", "腾讯", "苹果", "特斯拉", "阿里", "工商银行"].map(
                    (keyword) => (
                      <Badge
                        key={keyword}
                        variant="secondary"
                        className="cursor-pointer hover:bg-secondary/80"
                        onClick={() => setSearchOpen(true)}
                      >
                        {keyword}
                      </Badge>
                    )
                  )}
                </div>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setSearchOpen(true)}
                >
                  <Search className="mr-2 h-4 w-4" />
                  打开搜索 (⌘K)
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">数据来源</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground space-y-2">
                <p>A股: 新浪财经 + 腾讯财经</p>
                <p>港股: 腾讯财经</p>
                <p>美股: Yahoo Finance</p>
                <p className="text-xs pt-2">
                  数据仅供参考，不构成投资建议
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </>
  );
}

function HotStockCard({ ticker }: { ticker: string }) {
  const { data: quote, isLoading } = useQuote(ticker);

  if (isLoading || !quote) {
    return <StockCardSkeleton />;
  }

  return <StockCard quote={quote} showDetails />;
}

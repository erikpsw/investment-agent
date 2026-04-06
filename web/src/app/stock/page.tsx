"use client";

import { useState } from "react";
import { Header } from "@/components/header";
import { StockSearch } from "@/components/stock-search";
import { StockCard, StockCardSkeleton } from "@/components/stock-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useQuote } from "@/hooks/use-quote";
import { LineChart, TrendingUp, TrendingDown } from "lucide-react";

const STOCK_LISTS = {
  cn: [
    { ticker: "sh600519", name: "贵州茅台" },
    { ticker: "sh601318", name: "中国平安" },
    { ticker: "sz000858", name: "五粮液" },
    { ticker: "sh600036", name: "招商银行" },
    { ticker: "sz000333", name: "美的集团" },
    { ticker: "sh601888", name: "中国中免" },
  ],
  hk: [
    { ticker: "hk00700", name: "腾讯控股" },
    { ticker: "hk09988", name: "阿里巴巴-SW" },
    { ticker: "hk03690", name: "美团-W" },
    { ticker: "hk09618", name: "京东集团-SW" },
    { ticker: "hk01810", name: "小米集团-W" },
    { ticker: "hk00941", name: "中国移动" },
  ],
  us: [
    { ticker: "AAPL", name: "苹果" },
    { ticker: "MSFT", name: "微软" },
    { ticker: "GOOGL", name: "谷歌" },
    { ticker: "AMZN", name: "亚马逊" },
    { ticker: "NVDA", name: "英伟达" },
    { ticker: "TSLA", name: "特斯拉" },
  ],
};

export default function StockListPage() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [market, setMarket] = useState<"cn" | "hk" | "us">("cn");

  const stocks = STOCK_LISTS[market];

  return (
    <>
      <Header onSearchClick={() => setSearchOpen(true)} />
      <StockSearch open={searchOpen} onOpenChange={setSearchOpen} />

      <div className="flex-1 p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <LineChart className="h-8 w-8" />
              个股分析
            </h1>
            <p className="text-muted-foreground">
              选择股票查看详细分析和 AI 投资建议
            </p>
          </div>
          <Tabs value={market} onValueChange={(v) => setMarket(v as typeof market)}>
            <TabsList>
              <TabsTrigger value="cn">🇨🇳 A股</TabsTrigger>
              <TabsTrigger value="hk">🇭🇰 港股</TabsTrigger>
              <TabsTrigger value="us">🇺🇸 美股</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-green-600" />
                <CardTitle>热门股票</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                {stocks.slice(0, 4).map((stock) => (
                  <StockCardWrapper key={stock.ticker} ticker={stock.ticker} />
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <TrendingDown className="h-5 w-5 text-red-600" />
                <CardTitle>更多股票</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                {stocks.slice(4).map((stock) => (
                  <StockCardWrapper key={stock.ticker} ticker={stock.ticker} />
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>使用说明</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>1. 点击任意股票卡片进入详情页</p>
            <p>2. 在详情页可以查看实时行情、K线图、关键财务指标</p>
            <p>3. 点击「AI 深度分析」获取 AI 生成的投资建议</p>
            <p className="text-xs mt-4">
              * 所有分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function StockCardWrapper({ ticker }: { ticker: string }) {
  const { data: quote, isLoading } = useQuote(ticker);

  if (isLoading || !quote) {
    return <StockCardSkeleton />;
  }

  return <StockCard quote={quote} showDetails />;
}

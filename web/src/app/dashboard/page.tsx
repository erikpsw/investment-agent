"use client";

import { useState } from "react";
import { Search, TrendingUp } from "lucide-react";

import { Header } from "@/components/header";
import { HotStockSection } from "@/components/hot-stock-section";
import { MarketOverview } from "@/components/market-overview";
import { StockSearch } from "@/components/stock-search";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { HotStockMode } from "@/lib/api";


const MODES: Array<{ value: HotStockMode; label: string }> = [
  { value: "hot", label: "综合热度" },
  { value: "amount", label: "成交额" },
  { value: "gainers", label: "涨幅" },
];

export default function DashboardPage() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [mode, setMode] = useState<HotStockMode>("hot");

  return (
    <>
      <Header onSearchClick={() => setSearchOpen(true)} />
      <StockSearch open={searchOpen} onOpenChange={setSearchOpen} />

      <main className="flex-1 space-y-6 p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">投资仪表盘</h1>
            <p className="text-muted-foreground">动态追踪 A 股、港股和美股的市场热点</p>
          </div>
          <Button onClick={() => setSearchOpen(true)}><Search className="mr-2 h-4 w-4" />搜索股票或 ETF</Button>
        </div>

        <MarketOverview />

        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <div className="flex items-center gap-2 font-medium"><TrendingUp className="h-5 w-5 text-primary" />热门股票排行</div>
            <div className="flex flex-wrap gap-2">
              {MODES.map((item) => (
                <Button
                  key={item.value}
                  size="sm"
                  variant={mode === item.value ? "default" : "outline"}
                  onClick={() => setMode(item.value)}
                >
                  {item.label}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        <HotStockSection market="CN" mode={mode} />
        <HotStockSection market="HK" mode={mode} />
        <HotStockSection market="US" mode={mode} />

        <p className="text-center text-xs text-muted-foreground">热度来自成交额、涨跌幅、换手率和量比的综合评分，仅供参考，不构成投资建议。</p>
      </main>
    </>
  );
}

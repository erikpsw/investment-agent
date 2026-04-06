"use client";

import { useState } from "react";
import { Search, TrendingUp, Building2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/header";
import { StockSearch } from "@/components/stock-search";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSearch } from "@/hooks/use-search";
import { useDebounce } from "@/hooks/use-debounce";

const POPULAR_STOCKS = [
  { name: "贵州茅台", code: "sh600519", market: "CN" },
  { name: "中国平安", code: "sh601318", market: "CN" },
  { name: "腾讯控股", code: "hk00700", market: "HK" },
  { name: "苹果", code: "AAPL", market: "US" },
  { name: "微软", code: "MSFT", market: "US" },
  { name: "阿里巴巴", code: "BABA", market: "US" },
];

export default function SearchPage() {
  const router = useRouter();
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [market, setMarket] = useState("all");
  const debouncedQuery = useDebounce(query, 300);

  const { data, isLoading } = useSearch(debouncedQuery, {
    market,
    limit: 20,
    enabled: debouncedQuery.length >= 1,
  });

  const handleSelect = (code: string) => {
    router.push(`/stock/${encodeURIComponent(code)}`);
  };

  const marketBadge = (m: string) => {
    const variants: Record<string, { label: string; className: string }> = {
      CN: { label: "A股", className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" },
      HK: { label: "港股", className: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200" },
      US: { label: "美股", className: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" },
    };
    const v = variants[m] || { label: m, className: "" };
    return <Badge variant="outline" className={v.className}>{v.label}</Badge>;
  };

  return (
    <>
      <Header onSearchClick={() => setSearchOpen(true)} />
      <StockSearch open={searchOpen} onOpenChange={setSearchOpen} />

      <div className="flex-1 p-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">行情搜索</h1>
          <p className="text-muted-foreground">
            搜索 A股、港股、美股，支持名称、代码、拼音
          </p>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>搜索股票</CardTitle>
              <Tabs value={market} onValueChange={setMarket}>
                <TabsList className="h-8">
                  <TabsTrigger value="all" className="text-xs px-3">全部</TabsTrigger>
                  <TabsTrigger value="cn" className="text-xs px-3">A股</TabsTrigger>
                  <TabsTrigger value="hk" className="text-xs px-3">港股</TabsTrigger>
                  <TabsTrigger value="us" className="text-xs px-3">美股</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="输入股票名称或代码，如：茅台、苹果、AAPL..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {query.length === 0 ? (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">热门股票</p>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {POPULAR_STOCKS.map((stock) => (
                    <Button
                      key={stock.code}
                      variant="outline"
                      className="justify-start h-auto py-3"
                      onClick={() => handleSelect(stock.code)}
                    >
                      <div className="flex items-center gap-3 w-full">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
                          {stock.market === "CN" ? (
                            <TrendingUp className="h-4 w-4 text-red-600" />
                          ) : (
                            <Building2 className="h-4 w-4 text-primary" />
                          )}
                        </div>
                        <div className="flex-1 text-left">
                          <p className="font-medium">{stock.name}</p>
                          <p className="text-xs text-muted-foreground">{stock.code}</p>
                        </div>
                        {marketBadge(stock.market)}
                      </div>
                    </Button>
                  ))}
                </div>
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            ) : data?.results.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                未找到匹配的股票
              </div>
            ) : (
              <div className="grid gap-2">
                {data?.results.map((result) => (
                  <Button
                    key={result.code}
                    variant="ghost"
                    className="justify-start h-auto py-3 px-4"
                    onClick={() => handleSelect(result.code)}
                  >
                    <div className="flex items-center gap-3 w-full">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary">
                        {result.market === "CN" ? (
                          <TrendingUp className="h-5 w-5 text-red-600" />
                        ) : (
                          <Building2 className="h-5 w-5 text-primary" />
                        )}
                      </div>
                      <div className="flex-1 text-left">
                        <p className="font-medium">{result.name}</p>
                        <p className="text-sm text-muted-foreground">{result.code}</p>
                      </div>
                      {marketBadge(result.market)}
                    </div>
                  </Button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

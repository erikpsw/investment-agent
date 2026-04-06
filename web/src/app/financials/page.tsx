"use client";

import { useState } from "react";
import { FileText, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/header";
import { StockSearch } from "@/components/stock-search";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSearch } from "@/hooks/use-search";
import { useFinancials, useFinancialHistory } from "@/hooks/use-market";
import { useDebounce } from "@/hooks/use-debounce";
import { formatNumber } from "@/lib/utils";
import { RevenueChart, ProfitabilityChart, FinancialSummaryTable } from "@/components/charts/financial-chart";

const FEATURED_STOCKS = [
  { ticker: "sh600519", name: "贵州茅台" },
  { ticker: "sh601318", name: "中国平安" },
  { ticker: "hk00700", name: "腾讯控股" },
  { ticker: "AAPL", name: "苹果" },
];

type ReportType = "annual" | "q1" | "q2" | "q3" | "all";

export default function FinancialsPage() {
  const router = useRouter();
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedTicker, setSelectedTicker] = useState("sh600519");
  const [reportType, setReportType] = useState<ReportType>("annual");
  const debouncedQuery = useDebounce(query, 300);

  const { data: searchResults } = useSearch(debouncedQuery, {
    limit: 5,
    enabled: debouncedQuery.length >= 1,
  });

  const { data: financials, isLoading: financialsLoading } = useFinancials(selectedTicker);
  const { data: historyData, isLoading: historyLoading } = useFinancialHistory(
    selectedTicker,
    reportType
  );

  const handleSelectStock = (ticker: string) => {
    setSelectedTicker(ticker);
    setQuery("");
  };

  return (
    <>
      <Header onSearchClick={() => setSearchOpen(true)} />
      <StockSearch open={searchOpen} onOpenChange={setSearchOpen} />

      <div className="flex-1 p-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <FileText className="h-8 w-8" />
            财报数据
          </h1>
          <p className="text-muted-foreground">
            查看上市公司关键财务指标
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">选择股票</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="搜索股票..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>

                {query.length > 0 && searchResults?.results && (
                  <div className="space-y-1">
                    {searchResults.results.map((result) => (
                      <Button
                        key={result.code}
                        variant="ghost"
                        className="w-full justify-start"
                        onClick={() => handleSelectStock(result.code)}
                      >
                        <span className="truncate">{result.name}</span>
                        <span className="ml-auto text-xs text-muted-foreground">{result.code}</span>
                      </Button>
                    ))}
                  </div>
                )}

                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground mb-2">快速选择</p>
                  {FEATURED_STOCKS.map((stock) => (
                    <Button
                      key={stock.ticker}
                      variant={selectedTicker === stock.ticker ? "secondary" : "ghost"}
                      className="w-full justify-start"
                      onClick={() => handleSelectStock(stock.ticker)}
                    >
                      {stock.name}
                      <span className="ml-auto text-xs text-muted-foreground">{stock.ticker}</span>
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-2 space-y-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>{financials?.name || selectedTicker}</CardTitle>
                    <CardDescription>{selectedTicker}</CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Tabs value={reportType} onValueChange={(v) => setReportType(v as ReportType)}>
                      <TabsList className="h-8">
                        <TabsTrigger value="annual" className="text-xs px-2">年报</TabsTrigger>
                        <TabsTrigger value="q1" className="text-xs px-2">Q1</TabsTrigger>
                        <TabsTrigger value="q2" className="text-xs px-2">H1</TabsTrigger>
                        <TabsTrigger value="q3" className="text-xs px-2">Q3</TabsTrigger>
                      </TabsList>
                    </Tabs>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => router.push(`/stock/${selectedTicker}`)}
                    >
                      详情
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {financialsLoading ? (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                      <div key={i} className="p-4 rounded-lg bg-secondary/50">
                        <Skeleton className="h-4 w-20 mb-2" />
                        <Skeleton className="h-6 w-16" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <MetricCard
                      label="市盈率 (PE)"
                      value={financials?.pe_ratio}
                      format={(v) => formatNumber(v, 2)}
                    />
                    <MetricCard
                      label="市净率 (PB)"
                      value={financials?.pb_ratio}
                      format={(v) => formatNumber(v, 2)}
                    />
                    <MetricCard
                      label="净资产收益率 (ROE)"
                      value={financials?.roe}
                      format={(v) => `${formatNumber(v * 100, 2)}%`}
                    />
                    <MetricCard
                      label="毛利率"
                      value={financials?.gross_margin}
                      format={(v) => `${formatNumber(v * 100, 2)}%`}
                    />
                    <MetricCard
                      label="净利率"
                      value={financials?.profit_margin}
                      format={(v) => `${formatNumber(v * 100, 2)}%`}
                    />
                    <MetricCard
                      label="资产负债率"
                      value={financials?.debt_ratio}
                      format={(v) => `${formatNumber(v * 100, 2)}%`}
                    />
                  </div>
                )}
              </CardContent>
            </Card>

            <RevenueChart 
              data={historyData?.data || []} 
              isLoading={historyLoading} 
            />

            <ProfitabilityChart 
              data={historyData?.data || []} 
              isLoading={historyLoading} 
            />

            <FinancialSummaryTable 
              data={historyData?.data || []} 
              isLoading={historyLoading} 
            />
          </div>
        </div>
      </div>
    </>
  );
}

function MetricCard({
  label,
  value,
  format,
}: {
  label: string;
  value?: number | null;
  format: (v: number) => string;
}) {
  return (
    <div className="p-4 rounded-lg bg-secondary/50">
      <p className="text-sm text-muted-foreground mb-1">{label}</p>
      <p className="text-xl font-bold">
        {value != null ? format(value) : "--"}
      </p>
    </div>
  );
}

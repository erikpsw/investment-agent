"use client";

import { useEffect, useState, useMemo } from "react";
import {
  TrendingUp,
  TrendingDown,
  Loader2,
  AlertCircle,
  RefreshCw,
  BarChart3,
  Sparkles,
  CheckCircle2,
  XCircle,
  MinusCircle,
  AlertTriangle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn, formatLargeNumber } from "@/lib/utils";

interface FinancialHistoryItem {
  period: string;
  revenue: number | null;
  net_profit: number | null;
  gross_profit: number | null;
  operating_profit: number | null;
  total_assets: number | null;
  total_liabilities: number | null;
  net_assets: number | null;
  operating_cash_flow: number | null;
  eps: number | null;
  roe: number | null;
  gross_margin: number | null;
  net_margin: number | null;
}

interface AIAnalysisResult {
  ticker: string;
  report_period: string;
  report_type: string;
  analysis_date: string;
  summary: string;
  revenue?: { value?: string; yoy_change?: string; trend?: string };
  profit?: { net_profit?: string; yoy_change?: string; margin?: string; trend?: string };
  cash_flow?: { operating?: string; assessment?: string };
  highlights: Array<{
    metric: string;
    value: string;
    change?: string;
    assessment: string;
    comment?: string;
  }>;
  risks: Array<{
    category: string;
    description: string;
    severity: string;
  }>;
  outlook?: string;
  recommendation?: string;
  confidence: number;
  error?: string;
}

interface FinancialChartsProps {
  ticker: string;
  stockName?: string;
}

type ReportFilter = "quarterly" | "annual" | "all";

export function FinancialCharts({ ticker, stockName }: FinancialChartsProps) {
  const [data, setData] = useState<FinancialHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeChart, setActiveChart] = useState("revenue");
  const [reportFilter, setReportFilter] = useState<ReportFilter>("quarterly");
  
  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysisResult | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, [ticker]);

  const fetchData = async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const url = `/api/financial-history/${encodeURIComponent(ticker)}${refresh ? "?refresh=true" : ""}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("获取数据失败");
      const json = await res.json();
      setData(json.data || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "获取数据失败");
    } finally {
      setLoading(false);
    }
  };

  const fetchAIAnalysis = async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      const res = await fetch(`/api/report-analysis/${encodeURIComponent(ticker)}`);
      if (res.ok) {
        const json = await res.json();
        setAiAnalysis(json);
        return;
      }
      
      const analyzeRes = await fetch(`/api/report-analysis/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, report_type: "年报" }),
      });
      
      if (!analyzeRes.ok) throw new Error("AI分析失败");
      const json = await analyzeRes.json();
      setAiAnalysis(json);
    } catch (e) {
      setAiError(e instanceof Error ? e.message : "AI分析失败");
    } finally {
      setAiLoading(false);
    }
  };

  const chartData = useMemo(() => {
    if (!data.length) return [];
    
    // 先筛选季度报告数据
    let filteredData = data.filter((item) => {
      const match = item.period.match(/(\d{4})-(\d{2})-(\d{2})/);
      if (!match) return false;
      const month = parseInt(match[2]);
      const day = parseInt(match[3]);
      return (
        (month === 3 && day === 31) ||
        (month === 6 && day === 30) ||
        (month === 9 && day === 30) ||
        (month === 12 && day === 31)
      );
    });
    
    if (reportFilter === "annual") {
      // 只保留年报 (12-31)
      filteredData = filteredData.filter((item) => {
        const match = item.period.match(/(\d{4})-(\d{2})-(\d{2})/);
        if (!match) return false;
        const month = parseInt(match[2]);
        return month === 12;
      });
    }
    
    // 季度模式显示12期（3年），年报模式显示10期，全部显示最近16期
    const limit = reportFilter === "quarterly" ? 12 : reportFilter === "annual" ? 10 : 16;
    const slicedData = filteredData.slice(-limit);
    
    // 计算单季度数据（累计数据 -> 单季度数据）
    return slicedData.map((item, idx) => {
      const match = item.period.match(/(\d{4})-(\d{2})-(\d{2})/);
      let shortPeriod = item.period;
      let reportType = "";
      let quarter = 0;
      let year = "";
      
      if (match) {
        year = match[1];
        const yearShort = year.slice(2);
        const month = parseInt(match[2]);
        const day = parseInt(match[3]);
        
        if (month === 12 && day === 31) {
          shortPeriod = `${yearShort}Q4`;
          reportType = "q4";
          quarter = 4;
        } else if (month === 9 && day === 30) {
          shortPeriod = `${yearShort}Q3`;
          reportType = "q3";
          quarter = 3;
        } else if (month === 6 && day === 30) {
          shortPeriod = `${yearShort}Q2`;
          reportType = "q2";
          quarter = 2;
        } else if (month === 3 && day === 31) {
          shortPeriod = `${yearShort}Q1`;
          reportType = "q1";
          quarter = 1;
        } else {
          shortPeriod = `${yearShort}/${month.toString().padStart(2, "0")}`;
          reportType = "other";
        }
      }
      
      // 计算单季度收入和利润
      // Q1 是单季度，Q2/Q3/Q4 需要减去上一季度累计
      let singleRevenue = item.revenue;
      let singleNetProfit = item.net_profit;
      let singleGrossProfit = item.gross_profit;
      let singleOperatingProfit = item.operating_profit;
      
      if (quarter > 1 && reportFilter === "quarterly") {
        // 找到同年上一季度的数据
        const prevQuarterMonth = quarter === 2 ? 3 : quarter === 3 ? 6 : quarter === 4 ? 9 : 0;
        const prevPeriod = `${year}-${prevQuarterMonth.toString().padStart(2, "0")}-${prevQuarterMonth === 6 ? "30" : prevQuarterMonth === 9 ? "30" : "31"}`;
        const prevData = filteredData.find((d) => d.period === prevPeriod);
        
        if (prevData) {
          singleRevenue = item.revenue != null && prevData.revenue != null 
            ? item.revenue - prevData.revenue 
            : item.revenue;
          singleNetProfit = item.net_profit != null && prevData.net_profit != null 
            ? item.net_profit - prevData.net_profit 
            : item.net_profit;
          singleGrossProfit = item.gross_profit != null && prevData.gross_profit != null 
            ? item.gross_profit - prevData.gross_profit 
            : item.gross_profit;
          singleOperatingProfit = item.operating_profit != null && prevData.operating_profit != null 
            ? item.operating_profit - prevData.operating_profit 
            : item.operating_profit;
        }
      }
      
      // 单季度利润率计算
      // 优先使用单季度收入和利润计算，否则使用原始利润率
      let singleGrossMargin = item.gross_margin;
      let singleNetMargin = item.net_margin;
      
      // 如果有单季度收入和利润，重新计算利润率
      if (singleRevenue && singleRevenue > 0) {
        if (singleGrossProfit != null) {
          singleGrossMargin = singleGrossProfit / singleRevenue;
        }
        if (singleNetProfit != null) {
          singleNetMargin = singleNetProfit / singleRevenue;
        }
      }
      
      return {
        ...item,
        shortPeriod,
        reportType,
        // 保留原始累计数据
        cumRevenue: item.revenue,
        cumNetProfit: item.net_profit,
        // 单季度数据用于图表
        revenue: singleRevenue,
        net_profit: singleNetProfit,
        gross_profit: singleGrossProfit,
        operating_profit: singleOperatingProfit,
        gross_margin: singleGrossMargin,
        net_margin: singleNetMargin,
      };
    });
  }, [data, reportFilter]);

  const getMaxValue = (key: keyof FinancialHistoryItem) => {
    const values = chartData
      .map((d) => d[key])
      .filter((v): v is number => v !== null);
    return Math.max(...values, 1);
  };

  const latestData = data.length > 0 ? data[data.length - 1] : null;
  const prevData = data.length > 1 ? data[data.length - 2] : null;

  const getChange = (current: number | null, previous: number | null) => {
    if (current == null || previous == null || previous === 0) return null;
    return ((current - previous) / Math.abs(previous)) * 100;
  };

  if (loading && data.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">加载财务数据...</p>
        </div>
      </div>
    );
  }

  if (error && data.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-3" />
          <p className="text-sm text-destructive mb-3">{error}</p>
          <Button variant="outline" size="sm" onClick={() => fetchData()}>
            重试
          </Button>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p>暂无财务数据</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="p-4 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              财务趋势
            </h2>
            <p className="text-sm text-muted-foreground">
              {stockName || ticker} · {reportFilter === "quarterly" ? "近3年季度" : reportFilter === "annual" ? "年报" : "全部"}数据
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Tabs value={reportFilter} onValueChange={(v) => setReportFilter(v as ReportFilter)}>
              <TabsList className="h-8">
                <TabsTrigger value="quarterly" className="text-xs px-2">季度(3年)</TabsTrigger>
                <TabsTrigger value="annual" className="text-xs px-2">年报</TabsTrigger>
                <TabsTrigger value="all" className="text-xs px-2">全部</TabsTrigger>
              </TabsList>
            </Tabs>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchData(true)}
              disabled={loading}
            >
              <RefreshCw className={cn("h-4 w-4 mr-1", loading && "animate-spin")} />
              刷新
            </Button>
          </div>
        </div>

        {/* Key Metrics Cards */}
        <div className="grid grid-cols-4 gap-3">
          <MetricCard
            label="营业收入"
            value={latestData?.revenue}
            change={getChange(latestData?.revenue, prevData?.revenue)}
            format={(v) => formatLargeNumber(v)}
          />
          <MetricCard
            label="净利润"
            value={latestData?.net_profit}
            change={getChange(latestData?.net_profit, prevData?.net_profit)}
            format={(v) => formatLargeNumber(v)}
          />
          <MetricCard
            label="毛利率"
            value={latestData?.gross_margin}
            change={getChange(latestData?.gross_margin, prevData?.gross_margin)}
            format={(v) => `${(v * 100).toFixed(1)}%`}
            isPercent
          />
          <MetricCard
            label="ROE"
            value={latestData?.roe}
            change={getChange(latestData?.roe, prevData?.roe)}
            format={(v) => `${(v * 100).toFixed(1)}%`}
            isPercent
          />
        </div>

        {/* Charts */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">趋势图表</CardTitle>
              <Tabs value={activeChart} onValueChange={setActiveChart}>
                <TabsList className="h-8">
                  <TabsTrigger value="revenue" className="text-xs px-3">营收</TabsTrigger>
                  <TabsTrigger value="profit" className="text-xs px-3">利润</TabsTrigger>
                  <TabsTrigger value="margin" className="text-xs px-3">利润率</TabsTrigger>
                  <TabsTrigger value="assets" className="text-xs px-3">资产</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              {activeChart === "revenue" && (
                <BarChartSimple
                  data={chartData}
                  dataKey="revenue"
                  label="营业收入"
                  color="#3b82f6"
                  formatValue={(v) => formatLargeNumber(v)}
                />
              )}
              {activeChart === "profit" && (
                <BarChartSimple
                  data={chartData}
                  dataKey="net_profit"
                  label="净利润"
                  color="#22c55e"
                  formatValue={(v) => formatLargeNumber(v)}
                  showNegative
                />
              )}
              {activeChart === "margin" && (
                <LineChartSimple
                  data={chartData}
                  lines={[
                    { key: "gross_margin", label: "毛利率", color: "#3b82f6" },
                    { key: "net_margin", label: "净利率", color: "#22c55e" },
                  ]}
                  formatValue={(v) => `${(v * 100).toFixed(1)}%`}
                />
              )}
              {activeChart === "assets" && (
                <BarChartSimple
                  data={chartData}
                  dataKey="total_assets"
                  label="总资产"
                  color="#8b5cf6"
                  formatValue={(v) => formatLargeNumber(v)}
                />
              )}
            </div>
          </CardContent>
        </Card>

        {/* Data Table */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              历史数据
              {reportFilter === "quarterly" && (
                <span className="text-xs font-normal text-muted-foreground ml-2">
                  (单季度数据)
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-2 font-medium">报告期</th>
                    <th className="text-right py-2 px-2 font-medium">营收</th>
                    <th className="text-right py-2 px-2 font-medium">净利润</th>
                    <th className="text-right py-2 px-2 font-medium">毛利率</th>
                    <th className="text-right py-2 px-2 font-medium">净利率</th>
                    <th className="text-right py-2 px-2 font-medium">ROE</th>
                    <th className="text-right py-2 px-2 font-medium">EPS</th>
                  </tr>
                </thead>
                <tbody>
                  {chartData.slice().reverse().map((item, i) => (
                    <tr key={i} className="border-b last:border-0 hover:bg-muted/50">
                      <td className="py-2 px-2">{item.shortPeriod}</td>
                      <td className="text-right py-2 px-2">
                        {item.revenue != null ? formatLargeNumber(item.revenue) : "--"}
                      </td>
                      <td className={cn(
                        "text-right py-2 px-2",
                        item.net_profit != null && item.net_profit < 0 && "text-red-500"
                      )}>
                        {item.net_profit != null ? formatLargeNumber(item.net_profit) : "--"}
                      </td>
                      <td className="text-right py-2 px-2">
                        {item.gross_margin != null ? `${(item.gross_margin * 100).toFixed(1)}%` : "--"}
                      </td>
                      <td className={cn(
                        "text-right py-2 px-2",
                        item.net_margin != null && item.net_margin < 0 && "text-red-500"
                      )}>
                        {item.net_margin != null ? `${(item.net_margin * 100).toFixed(1)}%` : "--"}
                      </td>
                      <td className={cn(
                        "text-right py-2 px-2",
                        item.roe != null && item.roe < 0 && "text-red-500"
                      )}>
                        {item.roe != null ? `${(item.roe * 100).toFixed(1)}%` : "--"}
                      </td>
                      <td className="text-right py-2 px-2">
                        {item.eps != null ? item.eps.toFixed(2) : "--"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* AI Analysis Section */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-amber-500" />
                AI 财报分析
              </CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchAIAnalysis}
                disabled={aiLoading}
              >
                {aiLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    分析中...
                  </>
                ) : aiAnalysis ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-1" />
                    重新分析
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4 mr-1" />
                    开始分析
                  </>
                )}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {aiError && (
              <div className="flex items-center gap-2 text-sm text-destructive mb-4">
                <AlertCircle className="h-4 w-4" />
                {aiError}
              </div>
            )}
            
            {aiLoading && !aiAnalysis && (
              <div className="flex items-center justify-center py-8">
                <div className="text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-amber-500 mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">AI 正在分析财报数据...</p>
                  <p className="text-xs text-muted-foreground mt-1">首次分析可能需要 30-60 秒</p>
                </div>
              </div>
            )}

            {!aiAnalysis && !aiLoading && (
              <div className="text-center py-8 text-muted-foreground">
                <Sparkles className="h-12 w-12 mx-auto mb-3 opacity-30" />
                <p className="text-sm">点击"开始分析"让 AI 提取关键财务数据</p>
              </div>
            )}

            {aiAnalysis && (
              <div className="space-y-4">
                {/* Summary */}
                <div className="p-3 bg-muted/50 rounded-lg">
                  <p className="text-sm font-medium">{aiAnalysis.summary}</p>
                  {aiAnalysis.recommendation && (
                    <Badge 
                      variant={
                        aiAnalysis.recommendation.includes("买入") ? "default" :
                        aiAnalysis.recommendation.includes("卖出") ? "destructive" : 
                        "secondary"
                      }
                      className="mt-2"
                    >
                      {aiAnalysis.recommendation}
                    </Badge>
                  )}
                </div>

                {/* Revenue & Profit */}
                <div className="grid grid-cols-2 gap-3">
                  {aiAnalysis.revenue && (
                    <div className="p-3 border rounded-lg">
                      <p className="text-xs text-muted-foreground mb-1">营业收入</p>
                      <p className="font-semibold">{aiAnalysis.revenue.value || "--"}</p>
                      {aiAnalysis.revenue.yoy_change && (
                        <p className={cn(
                          "text-xs",
                          aiAnalysis.revenue.yoy_change.includes("+") ? "text-green-500" : 
                          aiAnalysis.revenue.yoy_change.includes("-") ? "text-red-500" : ""
                        )}>
                          {aiAnalysis.revenue.yoy_change}
                        </p>
                      )}
                    </div>
                  )}
                  {aiAnalysis.profit && (
                    <div className="p-3 border rounded-lg">
                      <p className="text-xs text-muted-foreground mb-1">净利润</p>
                      <p className="font-semibold">{aiAnalysis.profit.net_profit || "--"}</p>
                      {aiAnalysis.profit.yoy_change && (
                        <p className={cn(
                          "text-xs",
                          aiAnalysis.profit.yoy_change.includes("+") ? "text-green-500" : 
                          aiAnalysis.profit.yoy_change.includes("-") ? "text-red-500" : ""
                        )}>
                          {aiAnalysis.profit.yoy_change}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {/* Highlights */}
                {aiAnalysis.highlights && aiAnalysis.highlights.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">财务亮点</p>
                    <div className="space-y-2">
                      {aiAnalysis.highlights.map((h, i) => (
                        <div key={i} className="flex items-start gap-2 p-2 border rounded">
                          {h.assessment === "positive" ? (
                            <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                          ) : h.assessment === "negative" ? (
                            <XCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                          ) : (
                            <MinusCircle className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{h.metric}</span>
                              <span className="text-sm">{h.value}</span>
                              {h.change && (
                                <span className={cn(
                                  "text-xs",
                                  h.change.includes("+") ? "text-green-500" : 
                                  h.change.includes("-") ? "text-red-500" : ""
                                )}>
                                  {h.change}
                                </span>
                              )}
                            </div>
                            {h.comment && (
                              <p className="text-xs text-muted-foreground">{h.comment}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Risks */}
                {aiAnalysis.risks && aiAnalysis.risks.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">风险提示</p>
                    <div className="space-y-2">
                      {aiAnalysis.risks.map((r, i) => (
                        <div key={i} className="flex items-start gap-2 p-2 border rounded border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-950/20">
                          <AlertTriangle className={cn(
                            "h-4 w-4 mt-0.5 flex-shrink-0",
                            r.severity === "high" ? "text-red-500" :
                            r.severity === "medium" ? "text-amber-500" : "text-muted-foreground"
                          )} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{r.category}</span>
                              <Badge variant="outline" className="text-[10px] px-1 py-0">
                                {r.severity === "high" ? "高风险" : r.severity === "medium" ? "中风险" : "低风险"}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">{r.description}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Outlook */}
                {aiAnalysis.outlook && (
                  <div className="p-3 border rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">业绩展望</p>
                    <p className="text-sm">{aiAnalysis.outlook}</p>
                  </div>
                )}

                {/* Confidence */}
                <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
                  <span>分析时间: {aiAnalysis.analysis_date?.split("T")[0] || "--"}</span>
                  <span>置信度: {((aiAnalysis.confidence || 0) * 100).toFixed(0)}%</span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  change,
  format,
  isPercent,
}: {
  label: string;
  value: number | null | undefined;
  change: number | null;
  format: (v: number) => string;
  isPercent?: boolean;
}) {
  const isPositive = change != null && change > 0;
  const isNegative = change != null && change < 0;

  return (
    <Card>
      <CardContent className="p-3">
        <p className="text-xs text-muted-foreground mb-1">{label}</p>
        <p className={cn(
          "text-lg font-semibold",
          value != null && value < 0 && "text-red-500"
        )}>
          {value != null ? format(value) : "--"}
        </p>
        {change != null && (
          <div className={cn(
            "flex items-center gap-1 text-xs mt-1",
            isPositive && "text-green-500",
            isNegative && "text-red-500"
          )}>
            {isPositive ? (
              <TrendingUp className="h-3 w-3" />
            ) : isNegative ? (
              <TrendingDown className="h-3 w-3" />
            ) : null}
            <span>{change > 0 ? "+" : ""}{change.toFixed(1)}%</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function BarChartSimple({
  data,
  dataKey,
  label,
  color,
  formatValue,
  showNegative,
}: {
  data: any[];
  dataKey: string;
  label: string;
  color: string;
  formatValue: (v: number) => string;
  showNegative?: boolean;
}) {
  const values = data.map((d) => d[dataKey]).filter((v): v is number => v !== null);
  if (values.length === 0) {
    return <div className="h-full flex items-center justify-center text-muted-foreground text-sm">暂无数据</div>;
  }
  
  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);
  
  // 简单直接的 Y 轴计算
  // Y 轴从最小值的 60% 开始，到最大值的 110%
  let yMin: number;
  let yMax: number;
  
  if (dataMin < 0) {
    const dataRange = dataMax - dataMin;
    const padding = dataRange * 0.1;
    yMin = dataMin - padding;
    yMax = dataMax + padding;
  } else if (dataMin === dataMax) {
    yMin = dataMin * 0.5;
    yMax = dataMax * 1.2;
  } else {
    // 从最小值的 60% 开始，确保最小柱子有一定高度
    yMin = dataMin * 0.6;
    yMax = dataMax * 1.08;
  }
  
  const yRange = yMax - yMin || 1;
  
  // Generate Y-axis ticks (4-5 ticks)
  const tickCount = 4;
  const yTicks = Array.from({ length: tickCount + 1 }, (_, i) => 
    yMin + (yRange * i) / tickCount
  );

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 flex min-h-0">
        {/* Y-axis labels */}
        <div className="w-16 flex flex-col justify-between text-[10px] text-muted-foreground pr-2 shrink-0">
          {yTicks.slice().reverse().map((tick, i) => (
            <span key={i} className="text-right">{formatValue(tick)}</span>
          ))}
        </div>
        {/* Bars */}
        <div className="flex-1 h-full flex items-end gap-1 border-l border-b relative">
          {/* Grid lines */}
          {yTicks.slice(1, -1).map((_, i) => (
            <div
              key={i}
              className="absolute w-full border-t border-dashed border-muted-foreground/20"
              style={{ bottom: `${((i + 1) / tickCount) * 100}%` }}
            />
          ))}
          {data.map((item, i) => {
            const val = item[dataKey];
            if (val == null) return <div key={i} className="flex-1 h-full" />;
            
            const height = ((val - yMin) / yRange) * 100;
            const isNegative = val < 0;
            
            return (
              <div
                key={i}
                className="flex-1 h-full flex flex-col items-center justify-end group relative"
              >
                <div
                  className={cn(
                    "w-full max-w-8 rounded-t transition-all",
                    isNegative ? "bg-red-500/80" : "bg-primary/80",
                    "hover:opacity-80"
                  )}
                  style={{
                    height: `${Math.max(height, 2)}%`,
                    backgroundColor: isNegative ? "#ef4444" : color,
                  }}
                />
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-popover border rounded px-2 py-1 text-xs shadow-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                  {formatValue(val)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="flex gap-1 mt-2 pt-2 ml-16">
        {data.map((item, i) => (
          <div key={i} className="flex-1 text-center">
            <span className="text-[10px] text-muted-foreground">{item.shortPeriod}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LineChartSimple({
  data,
  lines,
  formatValue,
}: {
  data: any[];
  lines: { key: string; label: string; color: string }[];
  formatValue: (v: number) => string;
}) {
  const allValues = lines.flatMap((line) =>
    data.map((d) => d[line.key]).filter((v): v is number => v !== null)
  );
  if (allValues.length === 0) {
    return <div className="h-full flex items-center justify-center text-muted-foreground text-sm">暂无数据</div>;
  }
  
  const dataMin = Math.min(...allValues);
  const dataMax = Math.max(...allValues);
  
  // 简单直接的 Y 轴计算
  let minVal: number;
  let maxVal: number;
  
  if (dataMin < 0) {
    const dataRange = dataMax - dataMin;
    const padding = dataRange * 0.1;
    minVal = dataMin - padding;
    maxVal = dataMax + padding;
  } else if (dataMin === dataMax || dataMax - dataMin < 0.001) {
    minVal = dataMin * 0.9;
    maxVal = dataMax * 1.1;
  } else {
    // 从最小值的 60% 开始
    minVal = dataMin * 0.6;
    maxVal = dataMax * 1.08;
  }
  
  const range = maxVal - minVal || 0.01;
  
  // Generate Y-axis ticks
  const tickCount = 4;
  const yTicks = Array.from({ length: tickCount + 1 }, (_, i) => 
    minVal + (range * i) / tickCount
  );

  const getY = (val: number | null) => {
    if (val == null) return null;
    return 100 - ((val - minVal) / range) * 100;
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex gap-4 mb-2">
        {lines.map((line) => (
          <div key={line.key} className="flex items-center gap-1.5 text-xs">
            <div className="w-3 h-0.5 rounded" style={{ backgroundColor: line.color }} />
            <span className="text-muted-foreground">{line.label}</span>
          </div>
        ))}
      </div>
      <div className="flex-1 flex">
        {/* Y-axis labels */}
        <div className="w-12 flex flex-col justify-between text-[10px] text-muted-foreground pr-2">
          {yTicks.slice().reverse().map((tick, i) => (
            <span key={i} className="text-right">{formatValue(tick)}</span>
          ))}
        </div>
        {/* Chart area */}
        <div className="flex-1 relative border-l border-b">
          {/* Grid lines */}
          {yTicks.slice(1, -1).map((_, i) => (
            <div
              key={i}
              className="absolute w-full border-t border-dashed border-muted-foreground/20"
              style={{ bottom: `${((i + 1) / tickCount) * 100}%` }}
            />
          ))}
          <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            {lines.map((line) => {
              const points = data
                .map((d, i) => {
                  const y = getY(d[line.key]);
                  if (y == null) return null;
                  const x = data.length > 1 ? (i / (data.length - 1)) * 100 : 50;
                  return `${x},${y}`;
                })
                .filter(Boolean);

              return (
                <polyline
                  key={line.key}
                  points={points.join(" ")}
                  fill="none"
                  stroke={line.color}
                  strokeWidth="2"
                  vectorEffect="non-scaling-stroke"
                />
              );
            })}
          </svg>
        </div>
      </div>
      <div className="flex gap-1 mt-2 pt-2 ml-12">
        {data.map((item, i) => (
          <div key={i} className="flex-1 text-center">
            <span className="text-[10px] text-muted-foreground">{item.shortPeriod}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

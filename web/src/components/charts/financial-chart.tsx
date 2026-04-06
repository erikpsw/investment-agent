"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
  Area,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { FinancialHistoryItem } from "@/lib/api";

interface FinancialChartProps {
  data: FinancialHistoryItem[];
  isLoading?: boolean;
}

function formatLargeNumber(value: number | null): string {
  if (value === null) return "-";
  const absValue = Math.abs(value);
  if (absValue >= 1e8) {
    return `${(value / 1e8).toFixed(2)}亿`;
  } else if (absValue >= 1e4) {
    return `${(value / 1e4).toFixed(2)}万`;
  }
  return value.toFixed(2);
}

function formatPercent(value: number | null): string {
  if (value === null) return "-";
  return `${(value * 100).toFixed(2)}%`;
}

function formatPeriod(period: string): string {
  const match = period.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return period;
  const [, year, month] = match;
  if (month === "12") return `${year}年报`;
  if (month === "03") return `${year}Q1`;
  if (month === "06") return `${year}H1`;
  if (month === "09") return `${year}Q3`;
  return period;
}

export function RevenueChart({ data, isLoading }: FinancialChartProps) {
  const chartData = useMemo(() => {
    // 按日期排序（升序）并计算同比
    const sorted = [...data].sort((a, b) => a.period.localeCompare(b.period));
    
    return sorted.map((item, idx) => {
      // 计算同比：当前 vs 上年同期
      let revenueYoy = null;
      let profitYoy = null;
      
      if (idx >= 4 && sorted[idx - 4]) {
        const prevYear = sorted[idx - 4];
        if (prevYear.revenue && item.revenue) {
          revenueYoy = ((item.revenue - prevYear.revenue) / Math.abs(prevYear.revenue)) * 100;
        }
        if (prevYear.net_profit && item.net_profit) {
          profitYoy = ((item.net_profit - prevYear.net_profit) / Math.abs(prevYear.net_profit)) * 100;
        }
      }
      
      return {
        period: formatPeriod(item.period),
        revenue: item.revenue ? item.revenue / 1e8 : null,
        netProfit: item.net_profit ? item.net_profit / 1e8 : null,
        revenueYoy,
        profitYoy,
      };
    });
  }, [data]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">营收与净利润趋势</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis 
              dataKey="period" 
              tick={{ fontSize: 12 }} 
              className="text-muted-foreground"
            />
            <YAxis 
              yAxisId="left"
              tick={{ fontSize: 12 }}
              tickFormatter={(v) => `${v}亿`}
              className="text-muted-foreground"
            />
            <YAxis 
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 12 }}
              tickFormatter={(v) => `${v}%`}
              className="text-muted-foreground"
            />
            <Tooltip
              contentStyle={{ 
                backgroundColor: "hsl(var(--card))", 
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
              }}
              formatter={(value: number, name: string) => {
                if (name === "营业收入" || name === "净利润") {
                  return [`${value?.toFixed(2)}亿`, name];
                }
                return [`${value?.toFixed(2)}%`, name];
              }}
            />
            <Legend />
            <Bar 
              yAxisId="left"
              dataKey="revenue" 
              name="营业收入" 
              fill="hsl(var(--primary))" 
              radius={[4, 4, 0, 0]}
            />
            <Bar 
              yAxisId="left"
              dataKey="netProfit" 
              name="净利润" 
              fill="hsl(142 76% 36%)"
              radius={[4, 4, 0, 0]}
            />
            <Line 
              yAxisId="right"
              type="monotone" 
              dataKey="revenueYoy" 
              name="营收同比" 
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={{ r: 4 }}
              strokeDasharray="5 5"
            />
          </ComposedChart>
        </ResponsiveContainer>
        <p className="text-xs text-muted-foreground text-center mt-2">
          单位：亿元 | 同比增长率：%
        </p>
      </CardContent>
    </Card>
  );
}

export function ProfitabilityChart({ data, isLoading }: FinancialChartProps) {
  const chartData = useMemo(() => {
    const sorted = [...data].sort((a, b) => a.period.localeCompare(b.period));
    
    return sorted.map((item) => ({
      period: formatPeriod(item.period),
      grossMargin: item.gross_margin ? item.gross_margin * 100 : null,
      profitMargin: (item.net_margin ?? item.profit_margin) 
        ? (item.net_margin ?? item.profit_margin)! * 100 
        : null,
      roe: item.roe ? item.roe * 100 : null,
    }));
  }, [data]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">盈利能力指标</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis 
              dataKey="period" 
              tick={{ fontSize: 12 }} 
              className="text-muted-foreground"
            />
            <YAxis 
              tick={{ fontSize: 12 }}
              tickFormatter={(v) => `${v}%`}
              domain={[0, 'auto']}
              className="text-muted-foreground"
            />
            <Tooltip
              contentStyle={{ 
                backgroundColor: "hsl(var(--card))", 
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
              }}
              formatter={(value: number) => [`${value?.toFixed(2)}%`, ""]}
            />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="grossMargin" 
              name="毛利率" 
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={{ r: 4 }}
            />
            <Line 
              type="monotone" 
              dataKey="profitMargin" 
              name="净利率" 
              stroke="hsl(142 76% 36%)"
              strokeWidth={2}
              dot={{ r: 4 }}
            />
            <Line 
              type="monotone" 
              dataKey="roe" 
              name="ROE" 
              stroke="hsl(38 92% 50%)"
              strokeWidth={2}
              dot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
        <p className="text-xs text-muted-foreground text-center mt-2">
          毛利率 = (营收-成本)/营收 | 净利率 = 净利润/营收 | ROE = 净利润/净资产
        </p>
      </CardContent>
    </Card>
  );
}

export function FinancialSummaryTable({ data, isLoading }: FinancialChartProps) {
  // 计算同比数据
  const tableData = useMemo(() => {
    const sorted = [...data].sort((a, b) => a.period.localeCompare(b.period));
    
    return sorted.map((item, idx) => {
      let revenueYoy = null;
      let profitYoy = null;
      
      if (idx >= 4 && sorted[idx - 4]) {
        const prevYear = sorted[idx - 4];
        if (prevYear.revenue && item.revenue) {
          revenueYoy = (item.revenue - prevYear.revenue) / Math.abs(prevYear.revenue);
        }
        if (prevYear.net_profit && item.net_profit) {
          profitYoy = (item.net_profit - prevYear.net_profit) / Math.abs(prevYear.net_profit);
        }
      }
      
      return {
        ...item,
        revenue_yoy: revenueYoy,
        net_profit_yoy: profitYoy,
        profit_margin: item.net_margin ?? item.profit_margin,
      };
    }).reverse(); // 最新的在前
  }, [data]);
  
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-48 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">财务数据明细</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 px-3 font-medium text-muted-foreground">报告期</th>
                <th className="text-right py-2 px-3 font-medium text-muted-foreground">营收</th>
                <th className="text-right py-2 px-3 font-medium text-muted-foreground">同比</th>
                <th className="text-right py-2 px-3 font-medium text-muted-foreground">净利润</th>
                <th className="text-right py-2 px-3 font-medium text-muted-foreground">同比</th>
                <th className="text-right py-2 px-3 font-medium text-muted-foreground">毛利率</th>
                <th className="text-right py-2 px-3 font-medium text-muted-foreground">净利率</th>
              </tr>
            </thead>
            <tbody>
              {tableData.map((item, idx) => (
                <tr key={idx} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="py-2 px-3">{formatPeriod(item.period)}</td>
                  <td className="text-right py-2 px-3">{formatLargeNumber(item.revenue)}</td>
                  <td className={`text-right py-2 px-3 ${
                    item.revenue_yoy && item.revenue_yoy > 0 
                      ? "text-green-600" 
                      : item.revenue_yoy && item.revenue_yoy < 0 
                      ? "text-red-600" 
                      : ""
                  }`}>
                    {formatPercent(item.revenue_yoy)}
                  </td>
                  <td className="text-right py-2 px-3">{formatLargeNumber(item.net_profit)}</td>
                  <td className={`text-right py-2 px-3 ${
                    item.net_profit_yoy && item.net_profit_yoy > 0 
                      ? "text-green-600" 
                      : item.net_profit_yoy && item.net_profit_yoy < 0 
                      ? "text-red-600" 
                      : ""
                  }`}>
                    {formatPercent(item.net_profit_yoy)}
                  </td>
                  <td className="text-right py-2 px-3">{formatPercent(item.gross_margin)}</td>
                  <td className="text-right py-2 px-3">{formatPercent(item.profit_margin)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

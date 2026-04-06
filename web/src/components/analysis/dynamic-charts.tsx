"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { cn, formatLargeNumber } from "@/lib/utils";

export interface ChartConfig {
  type: "line" | "bar" | "area" | "pie" | "composed";
  title: string;
  description?: string;
  data: Record<string, unknown>[];
  metrics: {
    key: string;
    name: string;
    color?: string;
    type?: "line" | "bar" | "area";
  }[];
  xAxisKey?: string;
  unit?: string;
}

interface DynamicChartsProps {
  charts: ChartConfig[];
  className?: string;
}

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
];

const DEFAULT_COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
];

function getColor(index: number, customColor?: string): string {
  if (customColor) return customColor;
  return DEFAULT_COLORS[index % DEFAULT_COLORS.length];
}

function formatValue(value: unknown, unit?: string): string {
  if (typeof value !== "number") return String(value);
  
  const formatted = formatLargeNumber(value);
  return unit ? `${formatted}${unit}` : formatted;
}

function SingleChart({ config }: { config: ChartConfig }) {
  const { type, title, description, data, metrics, xAxisKey = "period", unit } = config;

  const renderChart = () => {
    switch (type) {
      case "line":
        return (
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis 
                dataKey={xAxisKey} 
                tick={{ fontSize: 12 }}
                className="text-muted-foreground"
              />
              <YAxis 
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => formatValue(v, unit)}
                className="text-muted-foreground"
              />
              <Tooltip 
                formatter={(value: number) => formatValue(value, unit)}
                contentStyle={{
                  backgroundColor: "hsl(var(--background))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Legend />
              {metrics.map((metric, i) => (
                <Line
                  key={metric.key}
                  type="monotone"
                  dataKey={metric.key}
                  name={metric.name}
                  stroke={getColor(i, metric.color)}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );

      case "bar":
        return (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis 
                dataKey={xAxisKey} 
                tick={{ fontSize: 12 }}
                className="text-muted-foreground"
              />
              <YAxis 
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => formatValue(v, unit)}
                className="text-muted-foreground"
              />
              <Tooltip 
                formatter={(value: number) => formatValue(value, unit)}
                contentStyle={{
                  backgroundColor: "hsl(var(--background))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Legend />
              {metrics.map((metric, i) => (
                <Bar
                  key={metric.key}
                  dataKey={metric.key}
                  name={metric.name}
                  fill={getColor(i, metric.color)}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );

      case "area":
        return (
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis 
                dataKey={xAxisKey} 
                tick={{ fontSize: 12 }}
                className="text-muted-foreground"
              />
              <YAxis 
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => formatValue(v, unit)}
                className="text-muted-foreground"
              />
              <Tooltip 
                formatter={(value: number) => formatValue(value, unit)}
                contentStyle={{
                  backgroundColor: "hsl(var(--background))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Legend />
              {metrics.map((metric, i) => (
                <Area
                  key={metric.key}
                  type="monotone"
                  dataKey={metric.key}
                  name={metric.name}
                  stroke={getColor(i, metric.color)}
                  fill={getColor(i, metric.color)}
                  fillOpacity={0.3}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );

      case "pie":
        return (
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                dataKey={metrics[0]?.key || "value"}
                nameKey="name"
              >
                {data.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={getColor(index)} />
                ))}
              </Pie>
              <Tooltip 
                formatter={(value: number) => formatValue(value, unit)}
                contentStyle={{
                  backgroundColor: "hsl(var(--background))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        );

      case "composed":
        return (
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis 
                dataKey={xAxisKey} 
                tick={{ fontSize: 12 }}
                className="text-muted-foreground"
              />
              <YAxis 
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => formatValue(v, unit)}
                className="text-muted-foreground"
              />
              <Tooltip 
                formatter={(value: number) => formatValue(value, unit)}
                contentStyle={{
                  backgroundColor: "hsl(var(--background))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Legend />
              {metrics.map((metric, i) => {
                const chartType = metric.type || "bar";
                if (chartType === "line") {
                  return (
                    <Line
                      key={metric.key}
                      type="monotone"
                      dataKey={metric.key}
                      name={metric.name}
                      stroke={getColor(i, metric.color)}
                      strokeWidth={2}
                    />
                  );
                } else if (chartType === "area") {
                  return (
                    <Area
                      key={metric.key}
                      type="monotone"
                      dataKey={metric.key}
                      name={metric.name}
                      stroke={getColor(i, metric.color)}
                      fill={getColor(i, metric.color)}
                      fillOpacity={0.3}
                    />
                  );
                }
                return (
                  <Bar
                    key={metric.key}
                    dataKey={metric.key}
                    name={metric.name}
                    fill={getColor(i, metric.color)}
                    radius={[4, 4, 0, 0]}
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        );

      default:
        return null;
    }
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        {description && (
          <CardDescription className="text-xs">{description}</CardDescription>
        )}
      </CardHeader>
      <CardContent>{renderChart()}</CardContent>
    </Card>
  );
}

export function DynamicCharts({ charts, className }: DynamicChartsProps) {
  if (!charts || charts.length === 0) {
    return null;
  }

  return (
    <div className={cn("grid gap-4", className)}>
      {charts.length === 1 ? (
        <SingleChart config={charts[0]} />
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {charts.map((chart, index) => (
            <SingleChart key={index} config={chart} />
          ))}
        </div>
      )}
    </div>
  );
}

export function generateChartsFromFinancials(
  data: Record<string, unknown>[]
): ChartConfig[] {
  if (!data || data.length === 0) return [];

  const charts: ChartConfig[] = [];
  const sample = data[0];

  if ("revenue" in sample && "net_profit" in sample) {
    charts.push({
      type: "composed",
      title: "营收与利润趋势",
      description: "营业收入与净利润的变化趋势",
      data: data as Record<string, unknown>[],
      metrics: [
        { key: "revenue", name: "营业收入", type: "bar" },
        { key: "net_profit", name: "净利润", type: "line" },
      ],
      xAxisKey: "period",
      unit: "亿",
    });
  }

  if ("gross_margin" in sample || "net_margin" in sample || "roe" in sample) {
    const metrics = [];
    if ("gross_margin" in sample) metrics.push({ key: "gross_margin", name: "毛利率" });
    if ("net_margin" in sample) metrics.push({ key: "net_margin", name: "净利率" });
    if ("roe" in sample) metrics.push({ key: "roe", name: "ROE" });
    
    if (metrics.length > 0) {
      charts.push({
        type: "line",
        title: "盈利能力指标",
        description: "利润率与ROE变化趋势",
        data: data as Record<string, unknown>[],
        metrics,
        xAxisKey: "period",
        unit: "%",
      });
    }
  }

  return charts;
}

"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  PieChart,
  BarChart3,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Lightbulb,
  Target,
} from "lucide-react";

interface KeyFinancials {
  revenue?: string;
  net_profit?: string;
  gross_margin?: string;
  net_margin?: string;
  roe?: string;
  eps?: string;
}

interface RevenueBreakdown {
  segment: string;
  revenue: string;
  ratio: string;
  growth: string;
  dimension?: string;
}

interface Risk {
  type: string;
  description: string;
  level: "high" | "medium" | "low";
}

interface ReportData {
  key_financials?: KeyFinancials;
  revenue_breakdown?: RevenueBreakdown[];
  business_highlights?: string[];
  risks?: Risk[];
  outlook?: string;
}

interface ReportVisualizationProps {
  data: ReportData;
  reportTitle?: string;
}

const COLORS = [
  "bg-blue-500",
  "bg-green-500",
  "bg-yellow-500",
  "bg-purple-500",
  "bg-pink-500",
  "bg-indigo-500",
  "bg-orange-500",
  "bg-teal-500",
];

function parsePercentage(str: string): number {
  const match = str.match(/([\d.]+)/);
  return match ? parseFloat(match[1]) : 0;
}

function formatMetricValue(value?: string): string {
  if (!value || value === "{}" || value === "[]") return "";
  if (value.includes("元/股")) return value;
  const match = value.match(/^([\d,]+(?:\.\d+)?)元(?:人民币)?(.*)$/);
  if (!match) return value;
  const amount = Number(match[1].replaceAll(",", ""));
  if (!Number.isFinite(amount)) return value;
  if (Math.abs(amount) >= 100_000_000) {
    return `${(amount / 100_000_000).toFixed(2)}亿元${match[2]}`;
  }
  return `${(amount / 10_000).toFixed(2)}万元${match[2]}`;
}

function breakdownDimension(item: RevenueBreakdown): string {
  if (item.dimension) return item.dimension;
  return /内销|出口|境内|境外|国内|海外/.test(item.segment) ? "地区构成" : "业务构成";
}

function PieChartSimple({ data }: { data: RevenueBreakdown[] }) {
  const total = data.reduce((sum, item) => {
    const ratio = parsePercentage(item.ratio);
    return sum + ratio;
  }, 0);

  return (
    <div className="flex items-center gap-6">
      <div className="relative size-40 shrink-0">
        <svg viewBox="0 0 100 100" className="size-full -rotate-90">
          {data.map((item, index) => {
            const ratio = parsePercentage(item.ratio);
            const percentage = total > 0 ? (ratio / total) * 100 : 0;
            const angle = (percentage / 100) * 360;
            const startAngle = data
              .slice(0, index)
              .reduce((sum, prior) => sum + ((parsePercentage(prior.ratio) / (total || 1)) * 360), 0);

            const x1 = 50 + 45 * Math.cos((startAngle * Math.PI) / 180);
            const y1 = 50 + 45 * Math.sin((startAngle * Math.PI) / 180);
            const x2 = 50 + 45 * Math.cos(((startAngle + angle) * Math.PI) / 180);
            const y2 = 50 + 45 * Math.sin(((startAngle + angle) * Math.PI) / 180);

            const largeArc = angle > 180 ? 1 : 0;

            const colorClasses = [
              "#3b82f6",
              "#22c55e",
              "#eab308",
              "#a855f7",
              "#ec4899",
              "#6366f1",
              "#f97316",
              "#14b8a6",
            ];

            return (
              <path
                key={index}
                d={`M 50 50 L ${x1} ${y1} A 45 45 0 ${largeArc} 1 ${x2} ${y2} Z`}
                fill={colorClasses[index % colorClasses.length]}
                className="hover:opacity-80 transition-opacity cursor-pointer"
              />
            );
          })}
        </svg>
      </div>
      <div className="flex flex-1 flex-col gap-2">
        {data.map((item, index) => (
          <div key={index} className="flex items-center gap-2 text-sm">
            <div className={`size-3 rounded-full ${COLORS[index % COLORS.length]}`} />
            <span className="flex-1 truncate">{item.segment}</span>
            <span className="font-mono text-muted-foreground">{item.ratio}</span>
            {item.growth && (
              <Badge
                variant={item.growth.includes("-") ? "destructive" : "secondary"}
                className="text-xs"
              >
                {item.growth}
              </Badge>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
}) {
  const isPositive = value.includes("+") || (value.includes("%") && !value.includes("-"));
  const isNegative = value.includes("-");

  const displayValue = formatMetricValue(value);
  if (!displayValue) return null;

  return (
    <div className="flex flex-col gap-2 rounded-lg bg-muted/50 p-4">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-4 w-4" />
        <span className="text-sm">{label}</span>
      </div>
      <p
        className={`text-lg font-bold ${
          isNegative ? "text-red-500" : isPositive ? "text-green-500" : ""
        }`}
      >
        {displayValue}
      </p>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const config = {
    high: { color: "bg-red-500/20 text-red-600 border-red-500/30", label: "高" },
    medium: { color: "bg-yellow-500/20 text-yellow-600 border-yellow-500/30", label: "中" },
    low: { color: "bg-green-500/20 text-green-600 border-green-500/30", label: "低" },
  };
  const c = config[level as keyof typeof config] || config.medium;
  return (
    <span className={`px-2 py-0.5 rounded text-xs border ${c.color}`}>
      {c.label}风险
    </span>
  );
}

export function ReportVisualization({ data }: ReportVisualizationProps) {
  if (!data || Object.keys(data).length === 0) {
    return null;
  }

  const { key_financials, revenue_breakdown, business_highlights, risks, outlook } = data;
  const financials = key_financials
    ? Object.fromEntries(
        Object.entries(key_financials).map(([key, value]) => [key, formatMetricValue(value)])
      ) as KeyFinancials
    : undefined;
  const breakdownGroups = (revenue_breakdown || []).reduce<Record<string, RevenueBreakdown[]>>(
    (groups, item) => {
      const dimension = breakdownDimension(item);
      groups[dimension] = [...(groups[dimension] || []), item];
      return groups;
    },
    {}
  );

  const hasData =
    (financials && Object.values(financials).some(Boolean)) ||
    (revenue_breakdown && revenue_breakdown.length > 0) ||
    (business_highlights && business_highlights.length > 0) ||
    (risks && risks.length > 0) ||
    outlook;

  if (!hasData) {
    return null;
  }

  return (
    <div className="space-y-4">
      {/* 关键财务指标 */}
      {financials && Object.values(financials).some(Boolean) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              关键财务指标
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {financials.revenue && (
                <MetricCard label="营业收入" value={financials.revenue} icon={TrendingUp} />
              )}
              {financials.net_profit && (
                <MetricCard label="净利润" value={financials.net_profit} icon={TrendingUp} />
              )}
              {financials.gross_margin && (
                <MetricCard label="毛利率" value={financials.gross_margin} icon={Target} />
              )}
              {financials.net_margin && (
                <MetricCard label="净利率" value={financials.net_margin} icon={Target} />
              )}
              {financials.roe && (
                <MetricCard label="ROE" value={financials.roe} icon={TrendingUp} />
              )}
              {financials.eps && (
                <MetricCard label="每股收益" value={financials.eps} icon={Target} />
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 收入构成 */}
      {revenue_breakdown && revenue_breakdown.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <PieChart className="h-4 w-4" />
              收入构成分析
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 lg:grid-cols-2">
              {Object.entries(breakdownGroups).map(([dimension, items]) => (
                <section key={dimension} className="flex flex-col gap-3">
                  <div>
                    <h3 className="text-sm font-medium">{dimension}</h3>
                    <p className="text-xs text-muted-foreground">同一统计口径内的占比合计约为 100%</p>
                  </div>
                  <PieChartSimple data={items} />
                </section>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 业务亮点 */}
      {business_highlights && business_highlights.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Lightbulb className="h-4 w-4" />
              业务亮点
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {business_highlights.map((highlight, index) => (
                <li key={index} className="flex items-start gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                  <span className="text-sm">{highlight}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* 风险因素 */}
      {risks && risks.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              风险因素
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {risks.map((risk, index) => (
                <div
                  key={index}
                  className="flex items-start gap-3 p-3 bg-muted/50 rounded-lg"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">{risk.type}</span>
                      <RiskBadge level={risk.level} />
                    </div>
                    <p className="text-sm text-muted-foreground">{risk.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 发展展望 */}
      {outlook && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Target className="h-4 w-4" />
              发展展望
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground leading-relaxed">{outlook}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import {
  FileText,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  PieChart,
  BarChart3,
  Lightbulb,
  Target,
  X,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface RevenueBreakdown {
  segment: string;
  revenue: string;
  ratio: string;
  growth: string;
}

interface Risk {
  type: string;
  description: string;
  level: "high" | "medium" | "low";
}

interface ReportAnalysis {
  ticker: string;
  stock_name: string;
  report_title: string;
  summary: string;
  key_financials: {
    revenue?: string;
    net_profit?: string;
    gross_margin?: string;
    net_margin?: string;
    roe?: string;
    eps?: string;
  };
  business_highlights: string[];
  revenue_breakdown: RevenueBreakdown[];
  risks: Risk[];
  outlook?: string;
  investment_opinion?: string;
  confidence?: number;
  analysis_date?: string;
  text_length?: number;
  sections_found?: string[];
}

interface ReportDeepAnalysisProps {
  open: boolean;
  onClose: () => void;
  ticker: string;
  stockName: string;
  reportTitle: string;
  pdfUrl: string;
}

export function ReportDeepAnalysis({
  open,
  onClose,
  ticker,
  stockName,
  reportTitle,
  pdfUrl,
}: ReportDeepAnalysisProps) {
  const [analysis, setAnalysis] = useState<ReportAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runAnalysis = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://localhost:8000/api/pdf-analysis/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker,
          stock_name: stockName,
          pdf_url: pdfUrl,
          report_title: reportTitle,
        }),
      });

      if (!res.ok) {
        throw new Error("分析失败");
      }

      const data = await res.json();
      setAnalysis(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "分析失败");
    } finally {
      setLoading(false);
    }
  };

  const getOpinionColor = (opinion?: string) => {
    if (!opinion) return "secondary";
    if (opinion.includes("买入")) return "default";
    if (opinion.includes("持有")) return "secondary";
    if (opinion.includes("观望")) return "outline";
    return "destructive";
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case "high": return "destructive";
      case "medium": return "secondary";
      case "low": return "outline";
      default: return "secondary";
    }
  };

  // Simple pie chart component
  const PieChartSimple = ({ data }: { data: RevenueBreakdown[] }) => {
    const colors = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899"];
    const total = data.reduce((sum, item) => {
      const val = parseFloat(item.ratio?.replace("%", "") || "0");
      return sum + val;
    }, 0);

    let cumulativeAngle = 0;

    return (
      <div className="flex items-center gap-6">
        <svg width="160" height="160" viewBox="0 0 160 160">
          {data.map((item, i) => {
            const ratio = parseFloat(item.ratio?.replace("%", "") || "0") / (total || 100);
            const angle = ratio * 360;
            const startAngle = cumulativeAngle;
            cumulativeAngle += angle;

            const startRad = (startAngle - 90) * Math.PI / 180;
            const endRad = (startAngle + angle - 90) * Math.PI / 180;
            const largeArc = angle > 180 ? 1 : 0;

            const x1 = 80 + 70 * Math.cos(startRad);
            const y1 = 80 + 70 * Math.sin(startRad);
            const x2 = 80 + 70 * Math.cos(endRad);
            const y2 = 80 + 70 * Math.sin(endRad);

            if (angle < 1) return null;

            return (
              <path
                key={i}
                d={`M 80 80 L ${x1} ${y1} A 70 70 0 ${largeArc} 1 ${x2} ${y2} Z`}
                fill={colors[i % colors.length]}
                stroke="white"
                strokeWidth="2"
              />
            );
          })}
        </svg>
        <div className="space-y-1.5">
          {data.map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <div
                className="w-3 h-3 rounded-sm shrink-0"
                style={{ backgroundColor: colors[i % colors.length] }}
              />
              <span className="truncate max-w-[120px]">{item.segment}</span>
              <span className="text-muted-foreground ml-auto">{item.ratio}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // Revenue breakdown bar chart
  const RevenueBarChart = ({ data }: { data: RevenueBreakdown[] }) => {
    const maxRatio = Math.max(
      ...data.map((d) => parseFloat(d.ratio?.replace("%", "") || "0")),
      1
    );

    return (
      <div className="space-y-3">
        {data.map((item, i) => {
          const ratio = parseFloat(item.ratio?.replace("%", "") || "0");
          const growth = item.growth || "";
          const isPositive = growth.includes("+") || (!growth.includes("-") && parseFloat(growth) > 0);

          return (
            <div key={i} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium truncate max-w-[200px]">{item.segment}</span>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">{item.revenue}</span>
                  {growth && (
                    <span className={cn(
                      "text-xs",
                      isPositive ? "text-green-600" : "text-red-600"
                    )}>
                      {growth}
                    </span>
                  )}
                </div>
              </div>
              <div className="h-6 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary/80 rounded-full flex items-center justify-end pr-2"
                  style={{ width: `${(ratio / maxRatio) * 100}%` }}
                >
                  <span className="text-xs text-primary-foreground font-medium">
                    {item.ratio}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] p-0">
        <DialogHeader className="p-4 pb-2 border-b">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              财报深度分析
            </DialogTitle>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            {stockName} · {reportTitle}
          </p>
        </DialogHeader>

        <ScrollArea className="h-[calc(90vh-100px)]">
          <div className="p-4 space-y-4">
            {!analysis && !loading && (
              <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <BarChart3 className="h-16 w-16 text-muted-foreground/50" />
                <div className="text-center">
                  <h3 className="font-medium">准备分析财报</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    AI 将解析 PDF 财报，提取关键数据并生成可视化分析
                  </p>
                </div>
                <Button onClick={runAnalysis} className="mt-4">
                  <Lightbulb className="h-4 w-4 mr-2" />
                  开始深度分析
                </Button>
              </div>
            )}

            {loading && (
              <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <Loader2 className="h-12 w-12 animate-spin text-primary" />
                <div className="text-center">
                  <h3 className="font-medium">正在分析财报...</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    下载 PDF、提取文本、AI 分析中，请稍候
                  </p>
                </div>
              </div>
            )}

            {error && (
              <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <AlertTriangle className="h-12 w-12 text-destructive" />
                <div className="text-center">
                  <h3 className="font-medium text-destructive">分析失败</h3>
                  <p className="text-sm text-muted-foreground mt-1">{error}</p>
                </div>
                <Button onClick={runAnalysis} variant="outline">
                  重试
                </Button>
              </div>
            )}

            {analysis && (
              <div className="space-y-4">
                {/* Summary & Opinion */}
                <Card>
                  <CardContent className="pt-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <h3 className="font-semibold text-lg mb-2">分析摘要</h3>
                        <p className="text-muted-foreground">{analysis.summary}</p>
                      </div>
                      {analysis.investment_opinion && (
                        <Badge variant={getOpinionColor(analysis.investment_opinion)} className="shrink-0">
                          {analysis.investment_opinion}
                        </Badge>
                      )}
                    </div>
                    {analysis.confidence && (
                      <div className="mt-4 flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">置信度</span>
                        <Progress value={analysis.confidence * 100} className="flex-1 h-2" />
                        <span className="text-sm font-medium">{(analysis.confidence * 100).toFixed(0)}%</span>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Key Financials */}
                {analysis.key_financials && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Target className="h-4 w-4" />
                        核心财务数据
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                        {Object.entries(analysis.key_financials).map(([key, value]) => {
                          if (!value) return null;
                          const labels: Record<string, string> = {
                            revenue: "营业收入",
                            net_profit: "净利润",
                            gross_margin: "毛利率",
                            net_margin: "净利率",
                            roe: "ROE",
                            eps: "每股收益",
                          };
                          return (
                            <div key={key} className="p-3 bg-muted/50 rounded-lg">
                              <div className="text-sm text-muted-foreground">{labels[key] || key}</div>
                              <div className="font-semibold mt-1">{value}</div>
                            </div>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Revenue Breakdown */}
                {analysis.revenue_breakdown && analysis.revenue_breakdown.length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <PieChart className="h-4 w-4" />
                        收入结构分析
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid md:grid-cols-2 gap-6">
                        <div>
                          <h4 className="text-sm font-medium mb-3">收入占比</h4>
                          <PieChartSimple data={analysis.revenue_breakdown} />
                        </div>
                        <div>
                          <h4 className="text-sm font-medium mb-3">各业务板块</h4>
                          <RevenueBarChart data={analysis.revenue_breakdown} />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Business Highlights */}
                {analysis.business_highlights && analysis.business_highlights.length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                        业务亮点
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2">
                        {analysis.business_highlights.map((highlight, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <TrendingUp className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
                            <span className="text-sm">{highlight}</span>
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}

                {/* Risks */}
                {analysis.risks && analysis.risks.length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-amber-500" />
                        风险因素
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {analysis.risks.map((risk, i) => (
                          <div key={i} className="flex items-start gap-3 p-3 bg-muted/30 rounded-lg">
                            <Badge variant={getRiskColor(risk.level)} className="shrink-0">
                              {risk.level === "high" ? "高" : risk.level === "medium" ? "中" : "低"}
                            </Badge>
                            <div>
                              <div className="font-medium text-sm">{risk.type}</div>
                              <div className="text-sm text-muted-foreground mt-0.5">
                                {risk.description}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Outlook */}
                {analysis.outlook && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <TrendingUp className="h-4 w-4" />
                        业绩展望
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground">{analysis.outlook}</p>
                    </CardContent>
                  </Card>
                )}

                {/* Meta Info */}
                <div className="text-xs text-muted-foreground flex items-center gap-4 pt-2 border-t">
                  <span>分析时间: {analysis.analysis_date?.split("T")[0]}</span>
                  <span>文档长度: {(analysis.text_length || 0).toLocaleString()} 字符</span>
                  <span>识别章节: {analysis.sections_found?.length || 0} 个</span>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

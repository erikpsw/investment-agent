"use client";

import { use, useRef, useEffect, useState } from "react";
import {
  ArrowLeft,
  Play,
  RotateCcw,
  Bot,
  Activity,
  PanelRightClose,
  PanelRight,
  PanelLeftClose,
  PanelLeft,
  FileText,
  Sparkles,
  Download,
  ExternalLink,
  Calendar,
  Loader2,
  AlertCircle,
  TrendingUp,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { Header } from "@/components/header";
import { StockSearch } from "@/components/stock-search";
import { InlineSteps } from "@/components/analysis/inline-steps";
import { DataSidebar } from "@/components/analysis/data-sidebar";
import { MarkdownContent } from "@/components/markdown-content";
import { FinancialCharts } from "@/components/analysis/financial-charts";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAnalysisStream } from "@/hooks/use-analysis-stream";
import { useQuote } from "@/hooks/use-quote";
import { useFinancials } from "@/hooks/use-market";
import { cn } from "@/lib/utils";

interface PageProps {
  params: Promise<{ ticker: string }>;
}

interface Report {
  stock_code: string;
  stock_name?: string;
  title: string;
  time?: string;
  url?: string;
  announcement_url?: string;
}

const REPORT_TYPES = [
  { value: "年报", label: "年报", icon: "📊" },
  { value: "半年报", label: "半年报", icon: "📈" },
  { value: "一季报", label: "Q1", icon: "1️⃣" },
  { value: "三季报", label: "Q3", icon: "3️⃣" },
];

export default function AnalysisPage({ params }: PageProps) {
  const { ticker } = use(params);
  const decodedTicker = decodeURIComponent(ticker);
  const [searchOpen, setSearchOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState("analysis");
  const [reportsListOpen, setReportsListOpen] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: quote, isLoading: quoteLoading } = useQuote(decodedTicker);
  const { data: financials, isLoading: financialsLoading } = useFinancials(decodedTicker);

  const {
    events,
    steps,
    finalResult,
    isRunning,
    error,
    startAnalysis,
    reset,
  } = useAnalysisStream();

  // Reports state
  const [reportType, setReportType] = useState("年报");
  const [reports, setReports] = useState<Report[]>([]);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState<string | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [steps, finalResult]);

  useEffect(() => {
    if (activeTab === "reports") {
      fetchReports();
    }
  }, [activeTab, reportType, decodedTicker]);

  const fetchReports = async () => {
    setReportsLoading(true);
    setReportsError(null);
    try {
      const res = await fetch(
        `http://localhost:8000/api/reports/${encodeURIComponent(decodedTicker)}?report_type=${encodeURIComponent(reportType)}&years=5`
      );
      if (!res.ok) throw new Error("获取财报列表失败");
      const data = await res.json();
      setReports(data.reports || []);
    } catch (e) {
      setReportsError(e instanceof Error ? e.message : "获取财报列表失败");
      setReports([]);
    } finally {
      setReportsLoading(false);
    }
  };

  const handleStartAnalysis = () => {
    startAnalysis(decodedTicker, `深度分析 ${quote?.name || decodedTicker}`);
  };

  return (
    <>
      <Header onSearchClick={() => setSearchOpen(true)} />
      <StockSearch open={searchOpen} onOpenChange={setSearchOpen} />

      <div className="flex-1 flex flex-col h-[calc(100vh-64px)]">
        <div className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 p-4">
          <div className="flex items-center gap-4">
            <Link href={`/stock/${encodeURIComponent(decodedTicker)}`}>
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-5 w-5" />
              </Button>
            </Link>

            <div className="flex items-center gap-3">
              <Bot className="h-6 w-6 text-primary" />
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-bold">AI 深度分析</h1>
                  <Badge variant="outline">{quote?.name || decodedTicker}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  LangGraph 多维度投资分析 · 财务可视化
                </p>
              </div>
            </div>

            <div className="ml-auto flex items-center gap-2">
              {activeTab === "analysis" && (
                <>
                  {!isRunning && !finalResult && (
                    <Button onClick={handleStartAnalysis}>
                      <Play className="h-4 w-4 mr-2" />
                      开始分析
                    </Button>
                  )}
                  {(finalResult || error) && (
                    <Button variant="outline" onClick={reset}>
                      <RotateCcw className="h-4 w-4 mr-2" />
                      重新分析
                    </Button>
                  )}
                  {isRunning && (
                    <Badge variant="secondary" className="animate-pulse">
                      <Activity className="h-3 w-3 mr-1" />
                      分析中...
                    </Badge>
                  )}
                </>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                title={sidebarOpen ? "隐藏数据面板" : "显示数据面板"}
              >
                {sidebarOpen ? (
                  <PanelRightClose className="h-5 w-5" />
                ) : (
                  <PanelRight className="h-5 w-5" />
                )}
              </Button>
            </div>
          </div>
        </div>

        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="flex-1 flex flex-col min-h-0"
        >
          <div className="border-b px-6 py-2 shrink-0">
            <TabsList>
              <TabsTrigger value="analysis" className="gap-2">
                <Sparkles className="h-4 w-4" />
                智能分析
              </TabsTrigger>
              <TabsTrigger value="reports" className="gap-2">
                <FileText className="h-4 w-4" />
                财报数据
              </TabsTrigger>
            </TabsList>
          </div>

          <div className="flex-1 flex overflow-hidden">
            <TabsContent value="analysis" className="flex-1 m-0 min-h-0 flex flex-col">
              <ScrollArea className="flex-1" ref={scrollRef}>
                <div className="max-w-4xl mx-auto p-6 space-y-4">
                  {!isRunning && !finalResult && events.length === 0 && (
                    <Card className="border-dashed">
                      <CardContent className="flex flex-col items-center justify-center py-12">
                        <Bot className="h-12 w-12 text-muted-foreground mb-4" />
                        <h3 className="text-lg font-semibold mb-2">准备就绪</h3>
                        <p className="text-muted-foreground text-center max-w-md mb-4">
                          点击"开始分析"按钮，AI 将对 {quote?.name || decodedTicker}{" "}
                          进行多维度深度分析，包括技术面、基本面、市场情绪和风险评估。
                        </p>
                        <Button onClick={handleStartAnalysis}>
                          <Play className="h-4 w-4 mr-2" />
                          开始分析
                        </Button>
                      </CardContent>
                    </Card>
                  )}

                  {(isRunning || steps.length > 0) && (
                    <InlineSteps steps={steps} events={events} isRunning={isRunning} />
                  )}

                  {error && (
                    <Card className="border-destructive">
                      <CardHeader>
                        <CardTitle className="text-destructive">分析出错</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-destructive">{error}</p>
                        <Button variant="outline" className="mt-4" onClick={reset}>
                          重试
                        </Button>
                      </CardContent>
                    </Card>
                  )}

                  {finalResult && (
                    <>
                      <Card>
                        <CardHeader>
                          <div className="flex items-center justify-between">
                            <CardTitle>综合投资建议</CardTitle>
                            {finalResult.output?.confidence && (
                              <Badge variant="secondary">
                                置信度: {Math.round(finalResult.output.confidence * 100)}%
                              </Badge>
                            )}
                          </div>
                        </CardHeader>
                        <CardContent>
                          <MarkdownContent
                            content={finalResult.output?.recommendation || "暂无建议"}
                          />
                        </CardContent>
                      </Card>

                      {finalResult.output?.technical_analysis && (
                        <Card>
                          <CardHeader>
                            <CardTitle>技术面分析</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <MarkdownContent content={finalResult.output.technical_analysis} />
                          </CardContent>
                        </Card>
                      )}

                      {finalResult.output?.fundamental_analysis && (
                        <Card>
                          <CardHeader>
                            <CardTitle>基本面分析</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <MarkdownContent content={finalResult.output.fundamental_analysis} />
                          </CardContent>
                        </Card>
                      )}

                      {finalResult.output?.risk_assessment && (
                        <Card>
                          <CardHeader>
                            <CardTitle>风险评估</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <MarkdownContent content={finalResult.output.risk_assessment} />
                          </CardContent>
                        </Card>
                      )}
                    </>
                  )}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="reports" className="flex-1 m-0 min-h-0 overflow-hidden">
              <div className="h-full flex overflow-hidden">
                {/* Reports List */}
                <div
                  className={cn(
                    "border-r flex flex-col shrink-0 transition-all duration-300",
                    reportsListOpen ? "w-72" : "w-0"
                  )}
                >
                  {reportsListOpen && (
                    <>
                      <div className="p-3 border-b shrink-0">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex flex-wrap gap-1 flex-1">
                            {REPORT_TYPES.map((type) => (
                              <Button
                                key={type.value}
                                variant={reportType === type.value ? "default" : "outline"}
                                size="sm"
                                onClick={() => setReportType(type.value)}
                                className="gap-1 text-xs h-7"
                              >
                                <span>{type.icon}</span>
                                {type.label}
                              </Button>
                            ))}
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 shrink-0"
                            onClick={() => setReportsListOpen(false)}
                            title="隐藏财报列表"
                          >
                            <PanelLeftClose className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>

                  <ScrollArea className="flex-1">
                    <div className="p-2 space-y-1.5">
                      {reportsLoading ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                      ) : reportsError ? (
                        <div className="text-center py-8">
                          <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
                          <p className="text-xs text-destructive">{reportsError}</p>
                        </div>
                      ) : reports.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                          <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p className="text-xs">暂无{reportType}数据</p>
                        </div>
                      ) : (
                        reports.map((report, i) => (
                          <div
                            key={i}
                            className="p-2.5 rounded-lg border hover:border-primary/50 hover:bg-accent/50 transition-colors"
                          >
                            <div className="flex items-center gap-1.5 mb-1">
                              <Badge variant="outline" className="text-[10px] h-5">
                                <Calendar className="h-2.5 w-2.5 mr-0.5" />
                                {report.time?.split(" ")[0]}
                              </Badge>
                            </div>
                            <p className="text-xs font-medium leading-tight mb-1.5 line-clamp-2">
                              {report.title}
                            </p>
                            <div className="flex gap-1">
                              {report.url && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 text-[10px] px-2"
                                  onClick={() => window.open(report.url, "_blank")}
                                >
                                  <Download className="h-3 w-3 mr-0.5" />
                                  PDF
                                </Button>
                              )}
                              {report.announcement_url && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 text-[10px] px-2"
                                  onClick={() => window.open(report.announcement_url, "_blank")}
                                >
                                  <ExternalLink className="h-3 w-3 mr-0.5" />
                                  详情
                                </Button>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </ScrollArea>
                    </>
                  )}
                </div>

                {/* Toggle button when sidebar is closed */}
                {!reportsListOpen && (
                  <div className="border-r p-2 flex flex-col items-center shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => setReportsListOpen(true)}
                      title="显示财报列表"
                    >
                      <PanelLeft className="h-4 w-4" />
                    </Button>
                  </div>
                )}

                {/* Financial Charts */}
                <div className="flex-1 min-h-0 overflow-hidden">
                  <FinancialCharts ticker={decodedTicker} stockName={quote?.name} />
                </div>
              </div>
            </TabsContent>

            <div
              className={cn(
                "border-l transition-all duration-300 overflow-hidden shrink-0",
                sidebarOpen ? "w-80" : "w-0"
              )}
            >
              {sidebarOpen && (
                <DataSidebar
                  ticker={decodedTicker}
                  quote={quote}
                  quoteLoading={quoteLoading}
                  financials={financials}
                  financialsLoading={financialsLoading}
                />
              )}
            </div>
          </div>
        </Tabs>
      </div>
    </>
  );
}

"use client";

import { useState, useEffect, useRef } from "react";
import {
  FileText,
  Download,
  ExternalLink,
  Loader2,
  AlertCircle,
  Bot,
  Send,
  Calendar,
  TrendingUp,
  Sparkles,
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MarkdownContent } from "@/components/markdown-content";
import { cn } from "@/lib/utils";

interface Report {
  stock_code: string;
  stock_name?: string;
  title: string;
  time?: string;
  url?: string;
  announcement_url?: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ReportsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ticker: string;
  stockName?: string;
}

const REPORT_TYPES = [
  { value: "年报", label: "年报", icon: "📊" },
  { value: "半年报", label: "半年报", icon: "📈" },
  { value: "一季报", label: "Q1", icon: "1️⃣" },
  { value: "三季报", label: "Q3", icon: "3️⃣" },
];

const QUICK_PROMPTS = [
  "分析这份财报的营收和利润趋势",
  "总结主要财务指标和风险点",
  "对比去年同期的变化",
  "分析现金流状况",
];

export function ReportsDialog({
  open,
  onOpenChange,
  ticker,
  stockName,
}: ReportsDialogProps) {
  const [reportType, setReportType] = useState("年报");
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [activeTab, setActiveTab] = useState("reports");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && ticker) {
      fetchReports();
    }
  }, [open, ticker, reportType]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `http://localhost:8000/api/reports/${encodeURIComponent(ticker)}?report_type=${encodeURIComponent(reportType)}&years=2`
      );
      if (!res.ok) throw new Error("获取财报列表失败");
      const data = await res.json();
      setReports(data.reports || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "获取财报列表失败");
      setReports([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (prompt: string) => {
    if (!prompt.trim() || analyzing) return;

    const userMessage: Message = { role: "user", content: prompt };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setAnalyzing(true);

    try {
      const context = selectedReport
        ? `分析财报: ${selectedReport.title} (${selectedReport.time})`
        : `分析 ${stockName || ticker} 的财务状况`;

      const res = await fetch("http://localhost:8000/api/analysis/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: prompt,
          context: JSON.stringify({
            ticker,
            name: stockName,
            report: selectedReport,
            query_context: context,
          }),
        }),
      });

      if (!res.ok) throw new Error("分析失败");
      const data = await res.json();
      
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply || data.response || "暂无分析结果" },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "分析失败，请稍后重试" },
      ]);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSelectReport = (report: Report) => {
    setSelectedReport(report);
    setActiveTab("analysis");
    setMessages([]);
  };

  const getYearFromTitle = (title: string) => {
    const match = title.match(/(\d{4})年/);
    return match ? match[1] : "";
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[85vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b shrink-0">
          <DialogTitle className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <FileText className="h-5 w-5 text-primary" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span>财报中心</span>
                {stockName && (
                  <Badge variant="secondary" className="font-normal">
                    {stockName}
                  </Badge>
                )}
              </div>
              <p className="text-sm font-normal text-muted-foreground">
                查看财报 · AI 智能分析
              </p>
            </div>
          </DialogTitle>
        </DialogHeader>

        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="flex-1 flex flex-col min-h-0"
        >
          <div className="px-6 py-2 border-b shrink-0">
            <TabsList className="grid w-full max-w-md grid-cols-2">
              <TabsTrigger value="reports" className="gap-2">
                <FileText className="h-4 w-4" />
                财报列表
              </TabsTrigger>
              <TabsTrigger value="analysis" className="gap-2">
                <Sparkles className="h-4 w-4" />
                AI 分析
                {selectedReport && (
                  <Badge variant="secondary" className="ml-1 text-xs">
                    {getYearFromTitle(selectedReport.title)}
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="reports" className="flex-1 m-0 min-h-0">
            <div className="h-full flex flex-col">
              <div className="px-6 py-3 border-b shrink-0">
                <div className="flex gap-2">
                  {REPORT_TYPES.map((type) => (
                    <Button
                      key={type.value}
                      variant={reportType === type.value ? "default" : "outline"}
                      size="sm"
                      onClick={() => setReportType(type.value)}
                      className="gap-1.5"
                    >
                      <span>{type.icon}</span>
                      {type.label}
                    </Button>
                  ))}
                </div>
              </div>

              <ScrollArea className="flex-1">
                <div className="p-6">
                  {loading ? (
                    <div className="flex flex-col items-center justify-center py-12">
                      <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
                      <p className="text-sm text-muted-foreground">加载中...</p>
                    </div>
                  ) : error ? (
                    <div className="flex flex-col items-center justify-center py-12">
                      <AlertCircle className="h-10 w-10 text-destructive mb-3" />
                      <p className="text-destructive mb-3">{error}</p>
                      <Button variant="outline" size="sm" onClick={fetchReports}>
                        重试
                      </Button>
                    </div>
                  ) : reports.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                      <FileText className="h-10 w-10 mb-3 opacity-50" />
                      <p>暂无{reportType}数据</p>
                    </div>
                  ) : (
                    <div className="grid gap-3">
                      {reports.map((report, index) => (
                        <div
                          key={index}
                          className={cn(
                            "group relative rounded-xl border p-4 transition-all hover:shadow-md cursor-pointer",
                            selectedReport?.title === report.title
                              ? "border-primary bg-primary/5 shadow-sm"
                              : "hover:border-primary/50 hover:bg-accent/50"
                          )}
                          onClick={() => handleSelectReport(report)}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <Badge variant="outline" className="shrink-0">
                                  <Calendar className="h-3 w-3 mr-1" />
                                  {report.time?.split(" ")[0] || "未知"}
                                </Badge>
                                {selectedReport?.title === report.title && (
                                  <Badge className="bg-primary/20 text-primary border-0">
                                    已选择
                                  </Badge>
                                )}
                              </div>
                              <h4 className="font-medium text-sm leading-tight">
                                {report.title}
                              </h4>
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              {report.url && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    window.open(report.url, "_blank");
                                  }}
                                  title="下载 PDF"
                                >
                                  <Download className="h-4 w-4" />
                                </Button>
                              )}
                              {report.announcement_url && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    window.open(report.announcement_url, "_blank");
                                  }}
                                  title="查看详情"
                                >
                                  <ExternalLink className="h-4 w-4" />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                className="gap-1 text-primary"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSelectReport(report);
                                }}
                              >
                                <Sparkles className="h-3.5 w-3.5" />
                                分析
                              </Button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
          </TabsContent>

          <TabsContent value="analysis" className="flex-1 m-0 min-h-0">
            <div className="h-full flex flex-col">
              {selectedReport ? (
                <>
                  <div className="px-6 py-3 border-b shrink-0 bg-muted/30">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
                          <TrendingUp className="h-4 w-4 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-sm">{selectedReport.title}</p>
                          <p className="text-xs text-muted-foreground">
                            {selectedReport.time}
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => setSelectedReport(null)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  <ScrollArea className="flex-1">
                    <div className="p-6 space-y-4">
                      {messages.length === 0 ? (
                        <div className="space-y-4">
                          <div className="text-center py-6">
                            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-3">
                              <Bot className="h-6 w-6 text-primary" />
                            </div>
                            <h3 className="font-medium mb-1">AI 财报分析</h3>
                            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                              选择下方问题或输入自定义问题，AI 将基于财报内容为您分析
                            </p>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            {QUICK_PROMPTS.map((prompt, i) => (
                              <Button
                                key={i}
                                variant="outline"
                                className="h-auto py-3 px-4 text-left justify-start text-sm font-normal"
                                onClick={() => handleAnalyze(prompt)}
                                disabled={analyzing}
                              >
                                {prompt}
                              </Button>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {messages.map((msg, i) => (
                            <div
                              key={i}
                              className={cn(
                                "flex gap-3",
                                msg.role === "user" ? "justify-end" : "justify-start"
                              )}
                            >
                              {msg.role === "assistant" && (
                                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                                  <Bot className="h-4 w-4 text-primary" />
                                </div>
                              )}
                              <div
                                className={cn(
                                  "rounded-2xl px-4 py-3 max-w-[85%]",
                                  msg.role === "user"
                                    ? "bg-primary text-primary-foreground"
                                    : "bg-muted"
                                )}
                              >
                                {msg.role === "assistant" ? (
                                  <MarkdownContent content={msg.content} />
                                ) : (
                                  <p className="text-sm">{msg.content}</p>
                                )}
                              </div>
                            </div>
                          ))}
                          {analyzing && (
                            <div className="flex gap-3">
                              <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                                <Bot className="h-4 w-4 text-primary" />
                              </div>
                              <div className="bg-muted rounded-2xl px-4 py-3">
                                <Loader2 className="h-4 w-4 animate-spin" />
                              </div>
                            </div>
                          )}
                          <div ref={messagesEndRef} />
                        </div>
                      )}
                    </div>
                  </ScrollArea>

                  <div className="px-6 py-4 border-t shrink-0 bg-background">
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        handleAnalyze(input);
                      }}
                      className="flex gap-2"
                    >
                      <Input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="输入问题，分析财报..."
                        disabled={analyzing}
                        className="flex-1"
                      />
                      <Button type="submit" disabled={analyzing || !input.trim()}>
                        <Send className="h-4 w-4" />
                      </Button>
                    </form>
                  </div>
                </>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-6">
                  <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center mb-4">
                    <FileText className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <h3 className="font-medium mb-1">请先选择财报</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    从财报列表中选择一份财报进行 AI 分析
                  </p>
                  <Button variant="outline" onClick={() => setActiveTab("reports")}>
                    查看财报列表
                  </Button>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

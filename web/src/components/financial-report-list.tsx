"use client";

import { useMemo, useState } from "react";
import { AlertCircle, ExternalLink, FileText, Loader2, RefreshCw } from "lucide-react";

import { PdfViewerDialog } from "@/components/pdf-viewer-dialog";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DisclosureItem } from "@/lib/api";
import { securityMarket, isPdfUrl, safeReportUrl } from "@/lib/financial-reports";

type ReportCategory = "annual" | "interim" | "quarterly" | "all";

const CATEGORIES: Array<{ value: ReportCategory; label: string }> = [
  { value: "annual", label: "年报" },
  { value: "interim", label: "中报" },
  { value: "quarterly", label: "季报" },
  { value: "all", label: "全部" },
];

export function FinancialReportList({ ticker, market }: { ticker: string; market?: string }) {
  const [category, setCategory] = useState<ReportCategory>("annual");
  const [selection, setSelection] = useState<{ key: string; report: DisclosureItem } | null>(null);
  const resolvedMarket = securityMarket(ticker, market);
  const disclosure = useQuery({ queryKey: ["security-reports", ticker, resolvedMarket, category], queryFn: async () => { const started = performance.now(); const result = await api.getSecurityReports(ticker, resolvedMarket, category); return { ...result, elapsedMs: performance.now() - started }; }, staleTime: 300000, refetchInterval: 300000, retry: false });
  const selectionKey = `${ticker}:${category}`;
  const selectedReport = selection?.key === selectionKey ? selection.report : null;

  const documents = useMemo(
    () => (disclosure.data?.documents || []).filter((item) => safeReportUrl(item.url)),
    [disclosure.data?.documents],
  );

  return (
    <>
      <Card>
        <CardHeader className="gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2"><FileText className="h-5 w-5" />财报原文</CardTitle>
            <CardDescription>{resolvedMarket === "CN" ? "巨潮资讯" : resolvedMarket === "HK" ? "披露易" : "SEC EDGAR"} · 财报原文与披露日期，支持 PDF 预览或打开原文。</CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
              {CATEGORIES.map((item) => (
                <Button
                  key={item.value}
                  type="button"
                  size="sm"
                  className="min-h-11"
                  variant={category === item.value ? "default" : "outline"}
                  onClick={() => setCategory(item.value)}
                >
                  {item.label}
                </Button>
              ))}
            </div>
        </CardHeader>
        <CardContent>
          {disclosure.data && <p className="mb-3 text-xs text-muted-foreground">本次加载 {(disclosure.data.elapsedMs / 1000).toFixed(2)} 秒</p>}
          {disclosure.isLoading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />正在获取财报列表...
            </div>
          ) : disclosure.isError ? (
            <div className="flex flex-col items-center gap-3 rounded-lg border border-destructive/30 p-6 text-center">
              <AlertCircle className="h-6 w-6 text-destructive" />
              <div className="text-sm">财报列表加载失败，请稍后重试。</div>
              <Button type="button" variant="outline" size="sm" onClick={() => disclosure.refetch()}>
                <RefreshCw />重试
              </Button>
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
              暂无符合条件的财报。
            </div>
          ) : (
            <div className="divide-y rounded-lg border">
              {documents.map((report) => {
                const url = safeReportUrl(report.url)!;
                const pdf = isPdfUrl(url);
                return (
                  <div key={`${report.date}-${report.title}-${url}`} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <Badge variant={pdf ? "secondary" : "outline"}>{pdf ? "PDF" : "网页"}</Badge>
                        {report.source && <span className="text-xs text-muted-foreground">{report.source}</span>}
                        {report.size && <span className="text-xs text-muted-foreground">{report.size}</span>}
                      </div>
                      <div className="font-medium leading-6">{report.title}</div>
                      <div className="text-xs text-muted-foreground">{report.date}</div>
                    </div>
                    {pdf ? (
                      <Button type="button" variant="outline" onClick={() => setSelection({ key: selectionKey, report })}>
                        查看 PDF
                      </Button>
                    ) : (
                      <a href={url} target="_blank" rel="noreferrer" className={buttonVariants({ variant: "outline" })}>
                        打开原文<ExternalLink />
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <PdfViewerDialog report={selectedReport} onOpenChange={(nextOpen) => !nextOpen && setSelection(null)} />
    </>
  );
}

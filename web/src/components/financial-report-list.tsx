"use client";

import { useMemo, useState } from "react";
import { AlertCircle, ExternalLink, FileText, Loader2, RefreshCw } from "lucide-react";

import { PdfViewerDialog } from "@/components/pdf-viewer-dialog";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDisclosure } from "@/hooks/use-market";
import type { DisclosureItem } from "@/lib/api";
import { isAStockTicker, isPdfUrl, safeReportUrl } from "@/lib/financial-reports";

type ReportCategory = "annual" | "interim" | "quarterly" | "all";

const CATEGORIES: Array<{ value: ReportCategory; label: string }> = [
  { value: "annual", label: "年报" },
  { value: "interim", label: "中报" },
  { value: "quarterly", label: "季报" },
  { value: "all", label: "全部" },
];

export function FinancialReportList({ ticker }: { ticker: string }) {
  const [category, setCategory] = useState<ReportCategory>("annual");
  const [selection, setSelection] = useState<{ key: string; report: DisclosureItem } | null>(null);
  const supported = isAStockTicker(ticker);
  const disclosure = useDisclosure(ticker, category, supported);
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
            <CardDescription>来自巨潮资讯的 A 股财报，支持站内 PDF 预览和原文打开。</CardDescription>
          </div>
          {supported && (
            <div className="flex flex-wrap gap-2">
              {CATEGORIES.map((item) => (
                <Button
                  key={item.value}
                  type="button"
                  size="sm"
                  variant={category === item.value ? "default" : "outline"}
                  onClick={() => setCategory(item.value)}
                >
                  {item.label}
                </Button>
              ))}
            </div>
          )}
        </CardHeader>
        <CardContent>
          {!supported ? (
            <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
              财报 PDF 首版仅支持 A 股。当前股票仍可查看上方财务指标。
            </div>
          ) : disclosure.isLoading ? (
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

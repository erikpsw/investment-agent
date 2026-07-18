"use client";

import { ExternalLink, FileText } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { DisclosureItem } from "@/lib/api";
import { safeReportUrl } from "@/lib/financial-reports";

interface PdfViewerDialogProps {
  report: DisclosureItem | null;
  onOpenChange: (open: boolean) => void;
}

export function PdfViewerDialog({ report, onOpenChange }: PdfViewerDialogProps) {
  const url = report ? safeReportUrl(report.url) : null;

  return (
    <Dialog open={Boolean(report && url)} onOpenChange={onOpenChange}>
      <DialogContent className="h-[92vh] max-w-[96vw] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-[min(96vw,1200px)]">
        <DialogHeader className="border-b p-4 pr-12">
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-4 w-4" />{report?.title || "财报 PDF"}
          </DialogTitle>
          <DialogDescription>{report?.date || ""}</DialogDescription>
        </DialogHeader>

        {url && (
          <iframe
            src={url}
            title="财报 PDF"
            className="h-full min-h-0 w-full border-0 bg-white"
          />
        )}

        <DialogFooter className="m-0 rounded-none px-4 py-3 sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">
            如果来源网站禁止站内预览，请使用新窗口打开。移动端将使用系统 PDF 阅读器。
          </p>
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              新窗口打开<ExternalLink />
            </a>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

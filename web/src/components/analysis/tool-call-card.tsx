"use client";

import { useState } from "react";
import { Wrench, ChevronDown, ChevronRight, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface ToolCallCardProps {
  tool: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
}

const TOOL_LABELS: Record<string, string> = {
  get_quote: "获取实时行情",
  get_history: "获取历史数据",
  get_key_metrics: "获取财务指标",
  search_reports: "搜索财报",
  analyze: "AI 分析",
};

export function ToolCallCard({ tool, input, output }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);
  const hasOutput = output != null;
  const hasError = output && "error" in output;

  return (
    <div
      className={cn(
        "rounded-md border text-xs overflow-hidden",
        hasError ? "border-destructive/50" : "border-border"
      )}
    >
      <button
        className="w-full flex items-center gap-2 p-2 hover:bg-accent/50 transition-colors text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <Wrench className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
        <span className="font-mono flex-1 truncate">
          {TOOL_LABELS[tool] || tool}
        </span>
        {hasOutput && (
          hasError ? (
            <X className="h-3.5 w-3.5 text-destructive flex-shrink-0" />
          ) : (
            <Check className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
          )
        )}
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="border-t px-2 py-1.5 space-y-2 bg-muted/30">
          {input && (
            <div>
              <p className="text-muted-foreground mb-1">输入:</p>
              <pre className="bg-background p-1.5 rounded overflow-x-auto font-mono">
                {JSON.stringify(input, null, 2)}
              </pre>
            </div>
          )}
          {output && (
            <div>
              <p className="text-muted-foreground mb-1">输出:</p>
              <pre
                className={cn(
                  "p-1.5 rounded overflow-x-auto font-mono",
                  hasError ? "bg-destructive/10" : "bg-background"
                )}
              >
                {JSON.stringify(output, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

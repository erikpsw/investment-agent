"use client";

import { useMemo } from "react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  Wrench,
  Brain,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AnalysisEvent, StepStatus } from "@/hooks/use-analysis-stream";
import { ToolCallCard } from "./tool-call-card";
import { ThinkingBlock } from "./thinking-block";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useState } from "react";

interface StepTimelineProps {
  steps: StepStatus[];
  events: AnalysisEvent[];
}

const NODE_LABELS: Record<string, string> = {
  fetch_data: "获取行情数据",
  fetch_history: "获取历史K线",
  fetch_financials: "获取财务指标",
  technical: "技术面分析",
  fundamental: "基本面分析",
  sentiment: "市场情绪分析",
  risk: "风险评估",
  synthesize: "生成投资建议",
};

const NODE_ICONS: Record<string, React.ReactNode> = {
  fetch_data: "📊",
  fetch_history: "📈",
  fetch_financials: "💰",
  technical: "📉",
  fundamental: "🏢",
  sentiment: "💭",
  risk: "⚠️",
  synthesize: "🎯",
};

export function StepTimeline({ steps, events }: StepTimelineProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

  const toggleStep = (node: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(node)) {
        next.delete(node);
      } else {
        next.add(node);
      }
      return next;
    });
  };

  const eventsByNode = useMemo(() => {
    const map: Record<string, AnalysisEvent[]> = {};
    events.forEach((e) => {
      const node = e.node || "unknown";
      if (!map[node]) map[node] = [];
      map[node].push(e);
    });
    return map;
  }, [events]);

  if (steps.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Circle className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">等待分析开始...</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {steps.map((step, index) => {
        const nodeEvents = eventsByNode[step.node] || [];
        const toolCalls = nodeEvents.filter((e) => e.event === "tool_call");
        const toolResults = nodeEvents.filter((e) => e.event === "tool_result");
        const thinkings = nodeEvents.filter((e) => e.event === "thinking");
        const errors = nodeEvents.filter((e) => e.event === "error");
        const hasDetails = toolCalls.length > 0 || thinkings.length > 0 || errors.length > 0;
        const isExpanded = expandedSteps.has(step.node);

        return (
          <Collapsible
            key={step.node}
            open={isExpanded}
            onOpenChange={() => hasDetails && toggleStep(step.node)}
          >
            <div
              className={cn(
                "rounded-lg border transition-colors",
                step.status === "running" && "border-primary bg-primary/5",
                step.status === "completed" && "border-green-500/50 bg-green-500/5",
                step.status === "error" && "border-destructive bg-destructive/5",
                step.status === "pending" && "border-muted bg-muted/30"
              )}
            >
              <CollapsibleTrigger asChild disabled={!hasDetails}>
                <button
                  className={cn(
                    "w-full flex items-start gap-3 p-3 text-left",
                    hasDetails && "cursor-pointer hover:bg-accent/50"
                  )}
                >
                  <div className="flex-shrink-0 mt-0.5">
                    <StepIcon status={step.status} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{NODE_ICONS[step.node] || "🔹"}</span>
                      <span className="font-medium text-sm">
                        {NODE_LABELS[step.node] || step.node}
                      </span>
                    </div>

                    {step.duration_ms != null && (
                      <p className="text-xs text-muted-foreground mt-1">
                        耗时: {(step.duration_ms / 1000).toFixed(2)}s
                      </p>
                    )}

                    {toolCalls.length > 0 && (
                      <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                        <Wrench className="h-3 w-3" />
                        <span>{toolCalls.length} 个工具调用</span>
                      </div>
                    )}

                    {thinkings.length > 0 && (
                      <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                        <Brain className="h-3 w-3" />
                        <span>{thinkings.length} 条思考</span>
                      </div>
                    )}
                  </div>

                  {hasDetails && (
                    <div className="flex-shrink-0 text-muted-foreground">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </div>
                  )}
                </button>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <div className="px-3 pb-3 pt-0 space-y-2 border-t">
                  {thinkings.map((t, i) => (
                    <ThinkingBlock key={i} content={t.content || ""} />
                  ))}

                  {toolCalls.map((tc, i) => {
                    const result = toolResults.find((r) => r.tool === tc.tool);
                    return (
                      <ToolCallCard
                        key={i}
                        tool={tc.tool || "unknown"}
                        input={tc.input}
                        output={result?.output}
                      />
                    );
                  })}

                  {errors.map((e, i) => (
                    <div
                      key={i}
                      className="text-xs text-destructive bg-destructive/10 p-2 rounded"
                    >
                      {e.content}
                    </div>
                  ))}
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        );
      })}
    </div>
  );
}

function StepIcon({ status }: { status: StepStatus["status"] }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    case "running":
      return <Loader2 className="h-5 w-5 text-primary animate-spin" />;
    case "error":
      return <AlertCircle className="h-5 w-5 text-destructive" />;
    default:
      return <Circle className="h-5 w-5 text-muted-foreground/50" />;
  }
}

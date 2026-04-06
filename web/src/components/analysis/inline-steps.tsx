"use client";

import { useMemo, useState } from "react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Wrench,
  Brain,
  Bot,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AnalysisEvent, StepStatus } from "@/hooks/use-analysis-stream";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface InlineStepsProps {
  steps: StepStatus[];
  events: AnalysisEvent[];
  isRunning: boolean;
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

const NODE_ICONS: Record<string, string> = {
  fetch_data: "📊",
  fetch_history: "📈",
  fetch_financials: "💰",
  technical: "📉",
  fundamental: "🏢",
  sentiment: "💭",
  risk: "⚠️",
  synthesize: "🎯",
};

export function InlineSteps({ steps, events, isRunning }: InlineStepsProps) {
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

  const completedCount = steps.filter((s) => s.status === "completed").length;
  const totalSteps = 8;

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">LangGraph 分析引擎</span>
              {isRunning ? (
                <Badge variant="secondary" className="animate-pulse">
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  执行中
                </Badge>
              ) : completedCount === totalSteps ? (
                <Badge variant="default" className="bg-green-500">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  完成
                </Badge>
              ) : null}
            </div>
            <p className="text-sm text-muted-foreground">
              {isRunning
                ? `正在执行分析流程... (${completedCount}/${totalSteps})`
                : completedCount === totalSteps
                ? `分析完成，共执行 ${totalSteps} 个步骤`
                : "等待开始分析"}
            </p>
          </div>
        </div>

        <div className="space-y-2 ml-12">
          {steps.map((step) => {
            const nodeEvents = eventsByNode[step.node] || [];
            const toolCalls = nodeEvents.filter((e) => e.event === "tool_call");
            const thinkings = nodeEvents.filter((e) => e.event === "thinking");
            const errors = nodeEvents.filter((e) => e.event === "error");
            const hasDetails = toolCalls.length > 0 || thinkings.length > 0 || errors.length > 0;
            const isExpanded = expandedSteps.has(step.node);

            return (
              <div
                key={step.node}
                className={cn(
                  "rounded-lg border p-3 transition-colors",
                  step.status === "running" && "border-primary bg-primary/5",
                  step.status === "completed" && "border-green-500/30 bg-green-500/5",
                  step.status === "error" && "border-destructive bg-destructive/5",
                  step.status === "pending" && "border-muted bg-muted/30"
                )}
              >
                <div
                  className={cn(
                    "flex items-center gap-3",
                    hasDetails && "cursor-pointer"
                  )}
                  onClick={() => hasDetails && toggleStep(step.node)}
                >
                  <StepIcon status={step.status} />
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-base">{NODE_ICONS[step.node] || "🔹"}</span>
                      <span className="font-medium text-sm">
                        {NODE_LABELS[step.node] || step.node}
                      </span>
                      {step.duration_ms != null && (
                        <span className="text-xs text-muted-foreground">
                          {(step.duration_ms / 1000).toFixed(2)}s
                        </span>
                      )}
                    </div>
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
                </div>

                {/* 正在执行时显示流式内容 */}
                {step.status === "running" && step.streamingContent && (
                  <div className="mt-3 pt-3 border-t">
                    <div className="text-sm text-muted-foreground whitespace-pre-wrap max-h-48 overflow-y-auto">
                      {step.streamingContent}
                      <span className="animate-pulse">▊</span>
                    </div>
                  </div>
                )}

                {isExpanded && hasDetails && (
                  <div className="mt-3 pt-3 border-t space-y-2">
                    {thinkings.map((t, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 text-xs text-muted-foreground"
                      >
                        <Brain className="h-3.5 w-3.5 text-primary flex-shrink-0 mt-0.5" />
                        <span className="italic">{t.content}</span>
                      </div>
                    ))}

                    {toolCalls.map((tc, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 text-xs"
                      >
                        <Wrench className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0 mt-0.5" />
                        <div>
                          <span className="font-mono text-muted-foreground">
                            {tc.tool}
                          </span>
                          {tc.input && (
                            <span className="text-muted-foreground ml-1">
                              ({JSON.stringify(tc.input)})
                            </span>
                          )}
                        </div>
                      </div>
                    ))}

                    {errors.map((e, i) => (
                      <div
                        key={i}
                        className="text-xs text-destructive bg-destructive/10 p-2 rounded"
                      >
                        {e.content}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {isRunning && steps.length < totalSteps && (
            <div className="flex items-center gap-3 p-3 rounded-lg border border-dashed text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">等待更多步骤...</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function StepIcon({ status }: { status: StepStatus["status"] }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />;
    case "running":
      return <Loader2 className="h-5 w-5 text-primary animate-spin flex-shrink-0" />;
    case "error":
      return <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0" />;
    default:
      return <Circle className="h-5 w-5 text-muted-foreground/50 flex-shrink-0" />;
  }
}

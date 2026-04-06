"use client";

import { useState, useCallback, useRef } from "react";

export type EventType =
  | "node_start"
  | "node_end"
  | "tool_call"
  | "tool_result"
  | "thinking"
  | "streaming"
  | "error"
  | "final";

export interface AnalysisEvent {
  event: EventType;
  timestamp: string;
  node?: string;
  tool?: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  content?: string;
  duration_ms?: number;
}

export interface StepStatus {
  node: string;
  status: "pending" | "running" | "completed" | "error";
  start_time?: string;
  end_time?: string;
  duration_ms?: number;
  output?: Record<string, unknown>;
  streamingContent?: string;
}

interface UseAnalysisStreamReturn {
  events: AnalysisEvent[];
  steps: StepStatus[];
  finalResult: AnalysisEvent | null;
  isRunning: boolean;
  error: string | null;
  streamingContent: Record<string, string>;
  startAnalysis: (ticker: string, query?: string) => void;
  startReportAnalysis: (ticker: string, reportTitle?: string, reportPeriod?: string, pdfUrl?: string) => void;
  reset: () => void;
}

// 直接使用后端地址，因为 Next.js rewrites 不能正确处理 SSE 流
const API_BASE = typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  : "";

export function useAnalysisStream(): UseAnalysisStreamReturn {
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [steps, setSteps] = useState<StepStatus[]>([]);
  const [finalResult, setFinalResult] = useState<AnalysisEvent | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState<Record<string, string>>({});
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setEvents([]);
    setSteps([]);
    setFinalResult(null);
    setIsRunning(false);
    setError(null);
    setStreamingContent({});
  }, []);

  const processEvent = useCallback((event: AnalysisEvent) => {
    setEvents((prev) => [...prev, event]);

    switch (event.event) {
      case "node_start":
        if (event.node) {
          setSteps((prev) => {
            const existing = prev.find((s) => s.node === event.node);
            if (existing) {
              return prev.map((s) =>
                s.node === event.node
                  ? { ...s, status: "running", start_time: event.timestamp, streamingContent: "" }
                  : s
              );
            }
            return [
              ...prev,
              {
                node: event.node,
                status: "running",
                start_time: event.timestamp,
                streamingContent: "",
              },
            ];
          });
          // 清空该节点的流式内容
          setStreamingContent((prev) => ({ ...prev, [event.node!]: "" }));
        }
        break;

      case "streaming":
        // 处理流式内容
        if (event.node && event.content) {
          setStreamingContent((prev) => ({
            ...prev,
            [event.node!]: (prev[event.node!] || "") + event.content,
          }));
          // 同时更新步骤中的流式内容
          setSteps((prev) =>
            prev.map((s) =>
              s.node === event.node
                ? { ...s, streamingContent: (s.streamingContent || "") + event.content }
                : s
            )
          );
        }
        break;

      case "node_end":
        if (event.node) {
          setSteps((prev) =>
            prev.map((s) =>
              s.node === event.node
                ? {
                    ...s,
                    status: "completed",
                    end_time: event.timestamp,
                    duration_ms: event.duration_ms,
                    output: event.output,
                  }
                : s
            )
          );
        }
        break;

      case "error":
        if (event.node) {
          setSteps((prev) =>
            prev.map((s) =>
              s.node === event.node ? { ...s, status: "error" } : s
            )
          );
        }
        if (event.content) {
          setError(event.content);
        }
        break;

      case "final":
        setFinalResult(event);
        setIsRunning(false);
        break;
    }
  }, []);

  const startAnalysis = useCallback(
    async (ticker: string, query?: string) => {
      reset();
      setIsRunning(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(`${API_BASE}/api/analysis/start`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ ticker, query: query || "" }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        if (!response.body) {
          throw new Error("No response body");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            setIsRunning(false);
            break;
          }

          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                processEvent(data as AnalysisEvent);
              } catch (e) {
                console.error("Failed to parse SSE data:", line, e);
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          return;
        }
        setError((err as Error).message);
        setIsRunning(false);
      }
    },
    [reset, processEvent]
  );

  const startReportAnalysis = useCallback(
    async (ticker: string, reportTitle?: string, reportPeriod?: string, pdfUrl?: string) => {
      reset();
      setIsRunning(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(`${API_BASE}/api/analysis/report`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            ticker,
            report_title: reportTitle || "",
            report_period: reportPeriod || "",
            pdf_url: pdfUrl || "",
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        if (!response.body) {
          throw new Error("No response body");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            setIsRunning(false);
            break;
          }

          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                processEvent(data as AnalysisEvent);
              } catch (e) {
                console.error("Failed to parse SSE data:", line, e);
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          return;
        }
        setError((err as Error).message);
        setIsRunning(false);
      }
    },
    [reset, processEvent]
  );

  return {
    events,
    steps,
    finalResult,
    isRunning,
    error,
    streamingContent,
    startAnalysis,
    startReportAnalysis,
    reset,
  };
}

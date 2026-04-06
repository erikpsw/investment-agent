"use client";

import * as React from "react";
import {
  Bot,
  Send,
  Loader2,
  Sparkles,
  MessageSquare,
  TrendingUp,
  PieChart,
  AlertTriangle,
  DollarSign,
  Building2,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";

interface AnalysisContext {
  ticker: string;
  reportTitle?: string;
  reportPeriod?: string;
  analysis?: string;
  keyMetrics?: Record<string, unknown>;
}

interface InlineChatProps {
  context: AnalysisContext;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

const QUICK_PROMPTS = [
  {
    icon: TrendingUp,
    label: "业绩解读",
    prompt: "请详细解读这份财报的业绩亮点和不足之处，包括营收、利润、现金流等关键指标的变化",
  },
  {
    icon: PieChart,
    label: "收入结构",
    prompt: "请分析公司的收入结构和各业务板块表现，哪些业务是增长引擎，哪些面临压力",
  },
  {
    icon: AlertTriangle,
    label: "风险分析",
    prompt: "请指出这份财报中需要关注的风险点和潜在隐患",
  },
  {
    icon: DollarSign,
    label: "盈利能力",
    prompt: "请分析公司的盈利能力，包括毛利率、净利率、ROE等指标的变化趋势",
  },
  {
    icon: Building2,
    label: "竞争优势",
    prompt: "基于财报数据，分析公司的核心竞争优势和护城河",
  },
  {
    icon: FileText,
    label: "估值分析",
    prompt: "基于财报数据和当前股价，请给出估值分析和投资建议",
  },
];

export function InlineChat({ context }: InlineChatProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const [input, setInput] = React.useState("");
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [streamingContent, setStreamingContent] = React.useState("");

  React.useEffect(() => {
    if (scrollRef.current) {
      const viewport = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, [messages, streamingContent]);

  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: content.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setStreamingContent("");

    try {
      const response = await fetch("/api/analysis/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          ticker: context.ticker,
          report_title: context.reportTitle || "",
          analysis_summary: context.analysis || "",
          key_metrics: context.keyMetrics || {},
        }),
      });

      if (!response.ok) {
        throw new Error("请求失败");
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("无法读取响应");

      const decoder = new TextDecoder();
      let accumulatedContent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.text) {
                accumulatedContent += data.text;
                setStreamingContent(accumulatedContent);
              } else if (data.done) {
                // 流结束，添加完整消息
                const assistantMessage: Message = {
                  id: (Date.now() + 1).toString(),
                  role: "assistant",
                  content: accumulatedContent,
                };
                setMessages((prev) => [...prev, assistantMessage]);
                setStreamingContent("");
              } else if (data.error) {
                throw new Error(data.error);
              }
            } catch {
              // 忽略解析错误
            }
          }
        }
      }

      // 如果流结束但没有收到 done 信号
      if (accumulatedContent && !messages.find(m => m.content === accumulatedContent)) {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: accumulatedContent,
        };
        setMessages((prev) => [...prev, assistantMessage]);
        setStreamingContent("");
      }
    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `抱歉，发生错误：${error instanceof Error ? error.message : "未知错误"}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input?.trim() || isLoading) return;
    const message = input;
    setInput("");
    await sendMessage(message);
  };

  const handleQuickPrompt = async (prompt: string) => {
    if (isLoading) return;
    await sendMessage(prompt);
  };

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <Bot className="h-5 w-5 text-primary" />
        <span className="text-base font-medium">追问 AI 分析师</span>
        {context.reportTitle && (
          <span className="text-sm text-muted-foreground">
            · {context.reportTitle}
          </span>
        )}
      </div>

      {messages.length === 0 && !streamingContent ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Sparkles className="h-4 w-4" />
            <span className="text-sm">基于财报内容的智能问答，点击快捷问题或自由提问</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {QUICK_PROMPTS.map((item) => (
              <Button
                key={item.label}
                variant="outline"
                size="sm"
                className="justify-start h-auto py-3 px-4 text-sm hover:bg-primary/5"
                onClick={() => handleQuickPrompt(item.prompt)}
                disabled={isLoading}
              >
                <item.icon className="h-4 w-4 mr-2 text-primary" />
                {item.label}
              </Button>
            ))}
          </div>
        </div>
      ) : (
        <ScrollArea className="h-[450px] mb-4 pr-3" ref={scrollRef}>
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "flex gap-3",
                  message.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                {message.role === "assistant" && (
                  <div className="shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center mt-0.5">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[85%] rounded-xl px-4 py-3",
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  )}
                >
                  {message.role === "assistant" ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                      <ReactMarkdown>
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap text-sm">{message.content}</p>
                  )}
                </div>
              </div>
            ))}
            {streamingContent && (
              <div className="flex gap-3">
                <div className="shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center mt-0.5">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="max-w-[85%] rounded-xl px-4 py-3 bg-muted">
                  <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                    <ReactMarkdown>
                      {streamingContent}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            )}
            {isLoading && !streamingContent && (
              <div className="flex gap-3">
                <div className="shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-muted rounded-xl px-4 py-3">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      )}

      <form onSubmit={onSubmit} className="flex gap-3 mt-2">
        <Textarea
          placeholder="输入您的问题，AI 将从财报中搜索相关内容回答..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="min-h-[50px] max-h-[120px] resize-none text-sm"
          rows={2}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit(e);
            }
          }}
        />
        <Button
          type="submit"
          size="icon"
          disabled={isLoading || !input?.trim()}
          className="shrink-0 h-[50px] w-[50px]"
        >
          {isLoading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Send className="h-5 w-5" />
          )}
        </Button>
      </form>
    </div>
  );
}

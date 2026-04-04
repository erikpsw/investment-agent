"use client";

import * as React from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import {
  Bot,
  Send,
  Sparkles,
  Loader2,
  TrendingUp,
  BarChart3,
  AlertTriangle,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface StockContext {
  ticker: string;
  name: string | null;
  price: number | null;
  changePercent: number | null;
  peRatio: number | null;
  marketCap: number | null;
}

interface AIAnalysisDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  stockContext?: StockContext;
}

const QUICK_PROMPTS = [
  {
    icon: TrendingUp,
    label: "技术分析",
    prompt: "请对这只股票进行技术分析，分析当前价格趋势和支撑阻力位",
  },
  {
    icon: BarChart3,
    label: "财务分析",
    prompt: "请分析这家公司的财务状况，包括盈利能力、成长性和估值水平",
  },
  {
    icon: AlertTriangle,
    label: "风险评估",
    prompt: "请评估投资这只股票的主要风险因素",
  },
];

export function AIAnalysisDialog({
  open,
  onOpenChange,
  stockContext,
}: AIAnalysisDialogProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const [input, setInput] = React.useState("");
  
  const transport = React.useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/chat",
        body: { stockContext },
      }),
    [stockContext]
  );

  const { messages, sendMessage, status } = useChat({ transport });

  const isLoading = status === "streaming" || status === "submitted";

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleQuickPrompt = (prompt: string) => {
    setInput(prompt);
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input?.trim() || isLoading) return;
    const message = input;
    setInput("");
    await sendMessage({ text: message });
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg flex flex-col p-0">
        <SheetHeader className="px-6 py-4 border-b">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Bot className="h-5 w-5 text-primary" />
              </div>
              <div>
                <SheetTitle className="text-left">AI 分析助手</SheetTitle>
                <SheetDescription className="text-left">
                  {stockContext?.name || "股票"} 智能分析
                </SheetDescription>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onOpenChange(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </SheetHeader>

        {stockContext && (
          <div className="px-6 py-3 border-b bg-muted/30">
            <div className="flex items-center gap-4 text-sm">
              <span className="font-medium">{stockContext.name}</span>
              <Badge variant="outline">{stockContext.ticker}</Badge>
              {stockContext.price && (
                <span className="tabular-nums">{stockContext.price.toFixed(2)}</span>
              )}
              {stockContext.changePercent !== null && (
                <span
                  className={cn(
                    "tabular-nums",
                    stockContext.changePercent >= 0
                      ? "text-green-600"
                      : "text-red-600"
                  )}
                >
                  {stockContext.changePercent >= 0 ? "+" : ""}
                  {stockContext.changePercent.toFixed(2)}%
                </span>
              )}
            </div>
          </div>
        )}

        <ScrollArea ref={scrollRef} className="flex-1 px-6">
          <div className="py-4 space-y-4">
            {messages.length === 0 ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Sparkles className="h-4 w-4" />
                  <span className="text-sm">快速开始</span>
                </div>
                <div className="grid gap-2">
                  {QUICK_PROMPTS.map((item, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      className="justify-start h-auto py-3 px-4"
                      onClick={() => handleQuickPrompt(item.prompt)}
                    >
                      <item.icon className="h-4 w-4 mr-3 text-muted-foreground" />
                      <span>{item.label}</span>
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground text-center pt-4">
                  AI 分析仅供参考，不构成投资建议
                </p>
              </div>
            ) : (
              messages.map((message) => {
                const textContent = message.parts
                  ?.filter((part): part is { type: "text"; text: string } => part.type === "text")
                  .map((part) => part.text)
                  .join("") || "";
                
                return (
                  <div
                    key={message.id}
                    className={cn(
                      "flex gap-3",
                      message.role === "user" ? "justify-end" : "justify-start"
                    )}
                  >
                    {message.role === "assistant" && (
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                        <Bot className="h-4 w-4 text-primary" />
                      </div>
                    )}
                    <div
                      className={cn(
                        "rounded-lg px-4 py-3 max-w-[85%] text-sm",
                        message.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted"
                      )}
                    >
                      <div className="whitespace-pre-wrap">{textContent}</div>
                    </div>
                  </div>
                );
              })
            )}
            {isLoading && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-muted rounded-lg px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin" />
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="p-4 border-t">
          <form onSubmit={onSubmit} className="flex gap-2">
            <Textarea
              placeholder="输入您的问题..."
              value={input}
              onChange={handleInputChange}
              className="min-h-[60px] max-h-[120px] resize-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSubmit(e);
                }
              }}
            />
            <Button type="submit" size="icon" disabled={isLoading || !input?.trim()}>
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
        </div>
      </SheetContent>
    </Sheet>
  );
}

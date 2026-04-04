"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface AnalysisChatProps {
  context?: Record<string, unknown>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const QUICK_PROMPTS = [
  "为什么给出这个评级?",
  "主要风险是什么?",
  "适合长期持有吗?",
  "和同行业比如何?",
];

export function AnalysisChat({ context }: AnalysisChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: content.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/analysis/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: content,
          context,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const data = await response.json();

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.reply || "抱歉，无法生成回复。",
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `出错了: ${(error as Error).message}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="flex flex-col h-full max-h-[400px]">
      <div className="flex items-center gap-2 mb-3">
        <Bot className="h-4 w-4 text-primary" />
        <span className="text-sm font-medium">追问 AI 分析师</span>
      </div>

      {messages.length === 0 ? (
        <div className="mb-3">
          <p className="text-xs text-muted-foreground mb-2">快捷问题:</p>
          <div className="flex flex-wrap gap-2">
            {QUICK_PROMPTS.map((prompt) => (
              <Button
                key={prompt}
                variant="outline"
                size="sm"
                className="text-xs h-7"
                onClick={() => sendMessage(prompt)}
                disabled={isLoading}
              >
                {prompt}
              </Button>
            ))}
          </div>
        </div>
      ) : (
        <ScrollArea className="flex-1 mb-3 pr-4" ref={scrollRef}>
          <div className="space-y-3">
            {messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "flex gap-2",
                  message.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                {message.role === "assistant" && (
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
                    <Bot className="h-3.5 w-3.5 text-primary" />
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[80%] rounded-lg px-3 py-2 text-sm",
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  )}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
                {message.role === "user" && (
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary flex items-center justify-center">
                    <User className="h-3.5 w-3.5 text-primary-foreground" />
                  </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-2">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="h-3.5 w-3.5 text-primary" />
                </div>
                <div className="bg-muted rounded-lg px-3 py-2">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入问题..."
          disabled={isLoading}
          className="flex-1"
        />
        <Button type="submit" size="icon" disabled={!input.trim() || isLoading}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

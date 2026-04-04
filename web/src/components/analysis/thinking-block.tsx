"use client";

import { Brain } from "lucide-react";
import { cn } from "@/lib/utils";

interface ThinkingBlockProps {
  content: string;
  className?: string;
}

export function ThinkingBlock({ content, className }: ThinkingBlockProps) {
  if (!content) return null;

  return (
    <div
      className={cn(
        "flex items-start gap-2 p-2 rounded-md bg-primary/5 border border-primary/20 text-xs",
        className
      )}
    >
      <Brain className="h-3.5 w-3.5 text-primary flex-shrink-0 mt-0.5" />
      <p className="text-muted-foreground italic">{content}</p>
    </div>
  );
}

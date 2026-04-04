"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  return (
    <div
      className={cn(
        "prose prose-sm dark:prose-invert max-w-none",
        "prose-headings:font-semibold prose-headings:text-foreground",
        "prose-h1:text-xl prose-h2:text-lg prose-h3:text-base",
        "prose-p:text-muted-foreground prose-p:leading-relaxed",
        "prose-strong:text-foreground prose-strong:font-semibold",
        "prose-ul:text-muted-foreground prose-ol:text-muted-foreground",
        "prose-li:marker:text-muted-foreground",
        "prose-blockquote:border-l-primary prose-blockquote:text-muted-foreground",
        "prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs",
        "prose-pre:bg-muted prose-pre:text-foreground",
        "prose-table:text-sm",
        "prose-th:text-left prose-th:font-semibold prose-th:p-2 prose-th:border-b",
        "prose-td:p-2 prose-td:border-b",
        "prose-hr:border-border",
        className
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
        h1: ({ children }) => (
          <h1 className="text-xl font-bold mt-6 mb-3 text-foreground">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-lg font-semibold mt-5 mb-2 text-foreground">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-base font-semibold mt-4 mb-2 text-foreground">{children}</h3>
        ),
        p: ({ children }) => (
          <p className="my-2 leading-relaxed">{children}</p>
        ),
        ul: ({ children }) => (
          <ul className="my-2 ml-4 list-disc space-y-1">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="my-2 ml-4 list-decimal space-y-1">{children}</ol>
        ),
        li: ({ children }) => (
          <li className="leading-relaxed">{children}</li>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-4 border-primary pl-4 my-3 italic text-muted-foreground">
            {children}
          </blockquote>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold text-foreground">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic">{children}</em>
        ),
        code: ({ className, children, ...props }) => {
          const isInline = !className;
          if (isInline) {
            return (
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">
                {children}
              </code>
            );
          }
          return (
            <code className={cn("block", className)} {...props}>
              {children}
            </code>
          );
        },
        pre: ({ children }) => (
          <pre className="bg-muted p-4 rounded-lg overflow-x-auto my-3 text-sm">
            {children}
          </pre>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto my-4">
            <table className="w-full border-collapse text-sm">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="text-left font-semibold p-2 border-b border-border bg-muted/50">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="p-2 border-b border-border">{children}</td>
        ),
        hr: () => <hr className="my-6 border-border" />,
        a: ({ href, children }) => (
          <a
            href={href}
            className="text-primary hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            {children}
          </a>
        ),
      }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

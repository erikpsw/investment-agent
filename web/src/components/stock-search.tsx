"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Search, TrendingUp, Building2, Loader2 } from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { useSearch } from "@/hooks/use-search";
import { useDebounce } from "@/hooks/use-debounce";

interface StockSearchProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function StockSearch({ open, onOpenChange }: StockSearchProps) {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const debouncedQuery = useDebounce(query, 300);

  const { data, isLoading } = useSearch(debouncedQuery, {
    limit: 10,
    enabled: debouncedQuery.length >= 1,
  });

  const handleSelect = (code: string) => {
    onOpenChange(false);
    setQuery("");
    router.push(`/stock/${encodeURIComponent(code)}`);
  };

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, onOpenChange]);

  const marketBadge = (market: string) => {
    const variants: Record<string, { label: string; className: string }> = {
      CN: { label: "A股", className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" },
      HK: { label: "港股", className: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200" },
      US: { label: "美股", className: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" },
    };
    const v = variants[market] || { label: market, className: "" };
    return <Badge variant="outline" className={v.className}>{v.label}</Badge>;
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} shouldFilter={false}>
      <CommandInput
        placeholder="输入股票名称或代码，如：茅台、苹果、AAPL..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        {isLoading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : query.length === 0 ? (
          <CommandEmpty>
            <div className="flex flex-col items-center gap-2 py-6">
              <Search className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                输入公司名称或股票代码开始搜索
              </p>
              <div className="flex gap-2 mt-2">
                <Badge variant="secondary">茅台</Badge>
                <Badge variant="secondary">苹果</Badge>
                <Badge variant="secondary">腾讯</Badge>
                <Badge variant="secondary">AAPL</Badge>
              </div>
            </div>
          </CommandEmpty>
        ) : data?.results.length === 0 ? (
          <CommandEmpty>未找到匹配的股票</CommandEmpty>
        ) : (
          <CommandGroup heading="搜索结果">
            {data?.results.map((result) => (
              <CommandItem
                key={result.code}
                value={result.code}
                onSelect={() => handleSelect(result.code)}
                className="flex items-center gap-3 py-3"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary">
                  {result.market === "CN" ? (
                    <TrendingUp className="h-5 w-5 text-red-600" />
                  ) : (
                    <Building2 className="h-5 w-5 text-primary" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{result.name}</span>
                    {marketBadge(result.market)}
                  </div>
                  <p className="text-sm text-muted-foreground">{result.code}</p>
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}

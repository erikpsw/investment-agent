"use client";

import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Search, Trash2 } from "lucide-react";

import { SecurityResearchDetails } from "@/components/security-research-details";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDebounce } from "@/hooks/use-debounce";
import { api, type SearchResult, type WatchlistGroup, type WatchlistItem } from "@/lib/api";


function pct(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}


function price(value?: number | null) {
  return value == null || Number.isNaN(value) ? "--" : value.toLocaleString("zh-CN", { maximumFractionDigits: 3 });
}


function SearchToAdd({ onSelect }: { onSelect: (result: SearchResult) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const debounced = useDebounce(query, 250);

  useEffect(() => {
    let cancelled = false;
    if (!debounced.trim()) return;
    Promise.resolve()
      .then(() => {
        if (!cancelled) setLoading(true);
        return api.search(debounced.trim(), "all", 8);
      })
      .then((response) => {
        if (!cancelled) setResults(response.results);
      })
      .catch(() => {
        if (!cancelled) setResults([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
      <Input
        className="pl-9"
        value={query}
        placeholder="搜索代码或名称并添加"
        onChange={(event) => setQuery(event.target.value)}
      />
      {(loading || results.length > 0) && debounced.trim() && (
        <div className="absolute z-40 mt-1 max-h-72 w-full overflow-y-auto rounded-md border bg-popover p-1 shadow-lg">
          {loading && <div className="px-3 py-2 text-sm text-muted-foreground">搜索中...</div>}
          {!loading && results.map((result) => (
            <button
              key={`${result.market}-${result.code}`}
              type="button"
              className="flex w-full items-center justify-between rounded px-3 py-2 text-left text-sm hover:bg-muted"
              onClick={() => {
                onSelect(result);
                setQuery("");
                setResults([]);
              }}
            >
              <span><strong>{result.name || result.code}</strong><span className="ml-2 text-muted-foreground">{result.code}</span></span>
              <Badge variant="outline">{result.market}</Badge>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}


export function WatchlistGroupCard({
  group,
  mobile,
  canMoveUp,
  canMoveDown,
  onRename,
  onMove,
  onDelete,
  onAdd,
  onUpdateItem,
  onDeleteItem,
}: {
  group: WatchlistGroup;
  mobile: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onRename: (name: string) => void;
  onMove: (direction: -1 | 1) => void;
  onDelete: () => void;
  onAdd: (result: SearchResult) => void;
  onUpdateItem: (index: number, patch: Partial<WatchlistItem>) => void;
  onDeleteItem: (index: number) => void;
}) {
  return (
    <Card className="overflow-visible">
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            aria-label="分组名称"
            className="min-w-48 flex-1 text-base font-semibold"
            value={group.name}
            onChange={(event) => onRename(event.target.value)}
          />
          <Button type="button" size="icon" variant="outline" disabled={!canMoveUp} onClick={() => onMove(-1)} aria-label="上移分组">
            <ArrowUp />
          </Button>
          <Button type="button" size="icon" variant="outline" disabled={!canMoveDown} onClick={() => onMove(1)} aria-label="下移分组">
            <ArrowDown />
          </Button>
          <Button type="button" size="icon" variant="outline" onClick={onDelete} aria-label="删除分组">
            <Trash2 />
          </Button>
        </div>
        <SearchToAdd onSelect={onAdd} />
      </CardHeader>
      <CardContent>
        {group.items.length === 0 ? (
          <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">该分组暂无自选股</div>
        ) : mobile ? (
          <div className="space-y-3">
            {group.items.map((item, index) => (
              <div key={`${item.ticker}-${index}`} className="space-y-3 rounded-lg border p-3">
                <SecurityHeader item={item} onDelete={() => onDeleteItem(index)} />
                <Input value={item.notes} placeholder="备注" onChange={(event) => onUpdateItem(index, { notes: event.target.value })} />
                <PeriodReturns item={item} />
                <SecurityResearchDetails research={item.research} />
              </div>
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>代码 / 名称</TableHead>
                  <TableHead>市场</TableHead>
                  <TableHead>现价</TableHead>
                  <TableHead>5 / 20 / 60 / 250日</TableHead>
                  <TableHead>备注</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {group.items.map((item, index) => (
                  <TableRow key={`${item.ticker}-${index}`}>
                    <TableCell className="min-w-44"><div className="font-medium">{item.ticker}</div><div className="text-xs text-muted-foreground">{item.name}</div></TableCell>
                    <TableCell><Badge variant="outline">{item.market}</Badge></TableCell>
                    <TableCell>{price(item.research?.quote?.price)} {item.research?.quote?.currency}</TableCell>
                    <TableCell className="min-w-56"><PeriodReturns item={item} /></TableCell>
                    <TableCell className="min-w-56"><Input value={item.notes} placeholder="备注" onChange={(event) => onUpdateItem(index, { notes: event.target.value })} /></TableCell>
                    <TableCell><Button type="button" size="icon" variant="ghost" onClick={() => onDeleteItem(index)}><Trash2 /></Button></TableCell>
                  </TableRow>
                ))}
                {group.items.map((item, index) => (
                  <TableRow key={`${item.ticker}-${index}-research`}>
                    <TableCell colSpan={6}><SecurityResearchDetails research={item.research} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}


function SecurityHeader({ item, onDelete }: { item: WatchlistItem; onDelete: () => void }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div><div className="font-semibold">{item.name || item.ticker}</div><div className="text-sm text-muted-foreground">{item.ticker} · {item.market}</div></div>
      <div className="flex items-center gap-2"><span className="tabular-nums">{price(item.research?.quote?.price)}</span><Button type="button" size="icon" variant="ghost" onClick={onDelete}><Trash2 /></Button></div>
    </div>
  );
}


function PeriodReturns({ item }: { item: WatchlistItem }) {
  return (
    <div className="flex flex-wrap gap-1 text-xs">
      {([5, 20, 60, 250] as const).map((days) => {
        const value = item.research?.returns?.[`${days}d`];
        return <Badge key={days} variant="secondary">{days}日 {pct(value)}</Badge>;
      })}
    </div>
  );
}

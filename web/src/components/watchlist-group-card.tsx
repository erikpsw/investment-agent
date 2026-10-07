"use client";

import { useEffect, useState } from "react";
import { BarChart3, FolderPlus, Search, Trash2 } from "lucide-react";
import dynamic from "next/dynamic";
const SecurityFundamentals = dynamic(() => import("@/components/security-fundamentals").then(module => module.SecurityFundamentals));
const SecurityResearchDetails = dynamic(() => import("@/components/security-research-details").then(module => module.SecurityResearchDetails), { loading: () => <p role="status">正在加载走势图…</p> });
import { yahooQuoteUrl } from "@/lib/financial-reports";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDebounce } from "@/hooks/use-debounce";
import {
  api,
  type SearchResult,
  type SecurityResearch,
  type WatchlistGroup,
  type WatchlistItem,
} from "@/lib/api";

function price(value?: number | null) {
  return value == null || Number.isNaN(value)
    ? "--"
    : value.toLocaleString("zh-CN", { maximumFractionDigits: 3 });
}
function number(value?: number | null, digits = 2) {
  return value == null || Number.isNaN(value) ? "--" : value.toFixed(digits);
}
function percent(value?: number | null) {
  return value == null || Number.isNaN(value)
    ? "--"
    : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}
function changeClass(value?: number | null) {
  if ((value || 0) > 0) return "text-green-600";
  if ((value || 0) < 0) return "text-red-600";
  return "text-muted-foreground";
}
function PercentValue({ value }: { value?: number | null }) {
  return (
    <span className={`font-medium tabular-nums ${changeClass(value)}`}>
      {percent(value)}
    </span>
  );
}
type WatchlistSortKey = "ticker" | "market" | "price" | "volume" | "day" | "5d" | "10d" | "20d" | "60d";
const ROOT_GROUP_VALUE = "__root__";

function researchKey(item: Pick<WatchlistItem, "market" | "ticker">) {
  return `${item.market.toUpperCase()}:${item.ticker.toUpperCase()}`;
}

function SearchToAdd({
  onSelect,
}: {
  onSelect: (result: SearchResult) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const debounced = useDebounce(query, 250);
  useEffect(() => {
    let cancelled = false;
    if (!debounced.trim()) return;
    void api
      .search(debounced.trim(), "all", 8)
      .then((response) => {
        if (!cancelled) setResults(response.results);
      })
      .catch(() => {
        if (!cancelled) setResults([]);
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
      {query.trim() && results.length > 0 && (
        <div className="absolute z-40 mt-1 max-h-72 w-full overflow-y-auto rounded-md border bg-popover p-1 shadow-lg">
          {results.map((result) => (
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
              <span>
                <strong>{result.name || result.code}</strong>
                <span className="ml-2 text-muted-foreground">
                  {result.code}
                </span>
              </span>
              <Badge variant="outline">{result.market}</Badge>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function WatchlistGroupCard({
  group: rawGroup,
  groups,
  researchByTicker,
  onReload,
  onAddChild,
}: {
  group: WatchlistGroup;
  groups: WatchlistGroup[];
  researchByTicker: Record<string, SecurityResearch>;
  onReload: () => Promise<void>;
  onAddChild: (parentId: string) => void;
}) {
  const [stockQuery, setStockQuery] = useState("");
  const group = {
    ...rawGroup,
    items: rawGroup.items.map((item) => ({
      ...item,
      research: researchByTicker[researchKey(item)] || item.research,
    })),
  };
  const [sort, setSort] = useState<{ key: WatchlistSortKey; descending: boolean }>({ key: "ticker", descending: false });
  const sortValue = (item: WatchlistItem): string | number | null | undefined => {
    if (sort.key === "ticker" || sort.key === "market") return item[sort.key];
    if (sort.key === "price" || sort.key === "volume") return item.research?.quote?.[sort.key];
    if (sort.key === "day") return item.research?.quote?.day_change_percent;
    return item.research?.returns?.[sort.key];
  };
  const sortedItems = group.items.filter(item => `${item.name} ${item.ticker}`.toLowerCase().includes(stockQuery.trim().toLowerCase())).sort((a, b) => {
    const first = sortValue(a), second = sortValue(b);
    if (first == null) return second == null ? 0 : 1;
    if (second == null) return -1;
    const compared = typeof first === "number" && typeof second === "number" ? first - second : String(first).localeCompare(String(second), "zh-CN");
    return sort.descending ? -compared : compared;
  });
  const sortHeader = (label: string, key: WatchlistSortKey) => <TableHead aria-sort={sort.key === key ? sort.descending ? "descending" : "ascending" : "none"}><button type="button" onClick={() => setSort(current => ({ key, descending: current.key === key ? !current.descending : key !== "ticker" && key !== "market" }))} aria-label={`按${label}排序`}>{label}{sort.key === key ? sort.descending ? " ↓" : " ↑" : ""}</button></TableHead>;
  const [activeItem, setActiveItem] = useState<WatchlistItem | null>(null);
  const [actionError, setActionError] = useState("");
  const call = async (action: () => Promise<unknown>) => {
    try { await action(); await onReload(); setActionError(""); }
    catch (error) { setActionError(error instanceof Error ? error.message : "操作失败，请重试"); }
  };
  const [detailMs, setDetailMs] = useState<number | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string>("");
  const [detailResearch, setDetailResearch] = useState<SecurityResearch | null>(null);
  const [detailError, setDetailError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const activeTicker = activeItem?.ticker;
  useEffect(() => {
    if (!activeTicker) return;
    let cancelled = false;
    let running = false;
    setDetailResearch(null);
    setDetailMs(null);
    setUpdatedAt("");
    setDetailError("");
    const refresh = async () => {
      if (running || document.hidden) return;
      running = true;
      const started = performance.now();
      setRefreshing(true);
      try {
        const response = await api.getWatchlistItemResearch(group.id, activeTicker);
        if (!cancelled) { setDetailResearch(response.result); setDetailError(""); setDetailMs(Math.round(performance.now() - started)); setUpdatedAt(new Date().toLocaleTimeString("zh-CN")); }
      } catch (error) {
        if (!cancelled) setDetailError(error instanceof Error ? error.message : "更新失败，请稍后重试");
      } finally {
        running = false;
        if (!cancelled) setRefreshing(false);
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60_000);
    const onVisible = () => { if (!document.hidden) void refresh(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => { cancelled = true; window.clearInterval(timer); document.removeEventListener("visibilitychange", onVisible); };
  }, [activeTicker, group.id]);
  const activeResearch = detailResearch || (activeItem
    ? researchByTicker[researchKey(activeItem)] || activeItem.research
    : null);
  const pending =
    !activeResearch?.history && !(activeResearch?.errors || []).length;
  return (
    <Card className="min-w-0 overflow-visible">
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between"><span className="font-semibold">{group.name}</span><span className="text-xs text-muted-foreground">{group.items.length} 只自选</span></div>
        <details className="rounded-lg border px-3 py-2">
          <summary className="min-h-9 cursor-pointer text-sm text-muted-foreground">管理分组与添加股票</summary>
          <div className="mt-3 space-y-3">
        <div className="flex items-center gap-2">
          <Input
            key={group.id}
            aria-label="分组名称"
            className="min-w-0 flex-1 text-base font-semibold"
            defaultValue={group.name}
            onBlur={(event) => {
              const name = event.currentTarget.value.trim();
              if (name && name !== group.name)
                void call(() => api.updateWatchlistGroup(group.id, { name }));
            }}
          />
          <Button
            type="button"
            size="icon"
            variant="outline"
            onClick={() => onAddChild(group.id)}
            aria-label="新建子分组"
          >
            <FolderPlus />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="outline"
            onClick={() => {
              if (window.confirm(`删除“${group.name}”及其所有子分组和股票？`))
                void call(() => api.deleteWatchlistGroup(group.id));
            }}
            aria-label="删除分组"
          >
            <Trash2 />
          </Button>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          移动到
          <Select
            value={group.parent_id || ROOT_GROUP_VALUE}
            onValueChange={(value) =>
              void call(() =>
                api.updateWatchlistGroup(group.id, {
                  parent_id: value === ROOT_GROUP_VALUE ? null : (value as string),
                }),
              )
            }
            items={{
              [ROOT_GROUP_VALUE]: "根分组",
              ...Object.fromEntries(
                groups
                  .filter((candidate) => candidate.id !== group.id)
                  .map((candidate) => [candidate.id, candidate.name]),
              ),
            }}
          >
            <SelectTrigger aria-label="移动分组" className="h-9 min-w-0 flex-1">
              <SelectValue placeholder="根分组" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ROOT_GROUP_VALUE}>根分组</SelectItem>
              {groups
                .filter((candidate) => candidate.id !== group.id)
                .map((candidate) => (
                  <SelectItem key={candidate.id} value={candidate.id}>
                    {candidate.name}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
        <SearchToAdd
          onSelect={(result) =>
            void call(() =>
              api.addWatchlistItem(group.id, {
                ticker: result.code,
                name: result.name,
                market: result.market,
                notes: "",
              }),
            )
          }
        />
          </div>
        </details>
      </CardHeader>
      <CardContent>
        {actionError && <p role="alert" className="mb-3 text-sm text-destructive">{actionError}</p>}
        <div className="mb-3 flex gap-2">
          <Input aria-label="搜索本组股票" placeholder="搜索本组股票" value={stockQuery} onChange={event => setStockQuery(event.target.value)} className="h-11 min-w-0 flex-1 text-base" />
          <Select
            value={`${sort.key}:${sort.descending ? "desc" : "asc"}`}
            onValueChange={(value) => {
              const [key, direction] = (value as string).split(":");
              setSort({ key: key as WatchlistSortKey, descending: direction === "desc" });
            }}
            items={{
              "ticker:asc": "代码顺序",
              "day:desc": "涨幅优先",
              "day:asc": "跌幅优先",
              "price:desc": "价格优先",
            }}
          >
            <SelectTrigger aria-label="股票排序" className="h-11 w-32 shrink-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ticker:asc">代码顺序</SelectItem>
              <SelectItem value="day:desc">涨幅优先</SelectItem>
              <SelectItem value="day:asc">跌幅优先</SelectItem>
              <SelectItem value="price:desc">价格优先</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {group.items.length === 0 ? (
          <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
            该分组暂无自选股
          </div>
        ) : (
          <div>
          <div className="space-y-2 lg:hidden" data-testid="mobile-watchlist-stocks">
            {sortedItems.map(item => <button key={`${item.market}:${item.ticker}`} type="button" className="flex min-h-24 w-full items-center justify-between gap-3 rounded-xl border p-4 text-left active:bg-muted" aria-label={`${item.ticker} 走势与关键数据`} onClick={() => setActiveItem(item)}>
              <span className="min-w-0 flex-1"><span className="block truncate text-base font-semibold">{item.name || item.ticker}</span><span className="mt-1 block text-xs text-muted-foreground">{item.ticker} · {item.market}</span>{item.notes && <span className="mt-1 block truncate text-xs text-muted-foreground">{item.notes}</span>}</span>
              <span className="shrink-0 text-right"><span className="block text-lg font-semibold tabular-nums">{price(item.research?.quote?.price)}</span><span className="mt-1 block"><PercentValue value={item.research?.quote?.day_change_percent} /></span></span>
            </button>)}
          </div>
          <div className="hidden overflow-x-auto lg:block">
            <Table className="w-full min-w-[1120px] text-sm">
              <TableHeader>
                <TableRow>
                  {sortHeader("代码 / 名称", "ticker")}
                  {sortHeader("市场", "market")}
                  {sortHeader("现价", "price")}
                  {sortHeader("今日", "day")}
                  {sortHeader("5日", "5d")}
                  {sortHeader("10日", "10d")}
                  {sortHeader("20日", "20d")}
                  {sortHeader("60日", "60d")}
                  {sortHeader("成交量", "volume")}
                  <TableHead>报价时间</TableHead>
                  <TableHead>换手</TableHead>
                  <TableHead>量比</TableHead>
                  <TableHead className="min-w-40">备注</TableHead>
                  <TableHead className="w-28 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedItems.map((item) => {
                  const research = item.research;
                  return (
                    <TableRow
                      key={`${item.market}:${item.ticker}`}
                      tabIndex={0}
                      aria-label={`${item.name || item.ticker} 详情`}
                      onKeyDown={(event) => {
                        if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) {
                          event.preventDefault(); setActiveItem(item);
                        }
                      }}
                      className="cursor-pointer"
                      onClick={() => setActiveItem(item)}
                    >
                      <TableCell>
                        <div className="font-medium">{item.ticker}</div>
                        <div className="text-xs text-muted-foreground">
                          {item.name}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{item.market}</Badge>
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {price(research?.quote?.price)}{" "}
                        {research?.quote?.currency}
                      </TableCell>
                      <TableCell>
                        <PercentValue
                          value={research?.quote?.day_change_percent}
                        />
                      </TableCell>
                      <TableCell>
                        <PercentValue value={research?.returns?.["5d"]} />
                      </TableCell>
                      <TableCell>
                        <PercentValue value={research?.returns?.["10d"]} />
                      </TableCell>
                      <TableCell>
                        <PercentValue value={research?.returns?.["20d"]} />
                      </TableCell>
                      <TableCell>
                        <PercentValue value={research?.returns?.["60d"]} />
                      </TableCell>
                      <TableCell>{price(research?.quote?.volume)}</TableCell>
                      <TableCell>{research?.quote?.fetched_at ? new Date(research.quote.fetched_at).toLocaleTimeString("zh-CN") : "--"}</TableCell>
                      <TableCell className="tabular-nums">
                        {percent(research?.quote?.turnover_rate)}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {number(research?.technical?.volume_ratio_20d)}
                      </TableCell>
                      <TableCell onClick={(event) => event.stopPropagation()}>
                        <Input
                          key={`${group.id}:${item.ticker}:${item.notes}`}
                          defaultValue={item.notes}
                          placeholder="备注"
                          onBlur={(event) => {
                            const notes = event.target.value;
                            if (notes !== item.notes)
                              void call(() => api.updateWatchlistItem(group.id, item.ticker, { notes }));
                          }}
                        />
                      </TableCell>
                      <TableCell
                        className="text-right"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => setActiveItem(item)}
                          aria-label={`${item.ticker} 走势与关键数据`}
                        >
                          <BarChart3 className="mr-1" />
                          详情
                        </Button>
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          onClick={() => {
                            if (
                              window.confirm(
                                `从“${group.name}”移除 ${item.ticker}？`,
                              )
                            )
                              void call(() =>
                                api.deleteWatchlistItem(group.id, item.ticker),
                              );
                          }}
                          aria-label={`删除 ${item.ticker}`}
                        >
                          <Trash2 />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          </div>
        )}
      </CardContent>
      <Sheet
        open={Boolean(activeItem)}
        onOpenChange={(open) => {
          if (!open) setActiveItem(null);
        }}
      >
        <SheetContent
          side="right"
          showCloseButton={false}
          className="[&>button]:size-11 data-[side=right]:w-full data-[side=right]:sm:w-[min(96vw,48rem)] data-[side=right]:sm:max-w-none overflow-y-auto pb-[env(safe-area-inset-bottom)]"
        >
          <SheetHeader>
            <Button type="button" variant="outline" className="mb-2 h-11 w-fit" onClick={() => setActiveItem(null)}>返回列表</Button>
            {activeItem && <a className="inline-flex min-h-11 items-center text-sm text-primary underline" href={yahooQuoteUrl(activeItem.ticker, activeItem.market)} target="_blank" rel="noreferrer">Yahoo Finance ↗</a>}
            <SheetTitle>
              {activeItem?.name || activeItem?.ticker} · {activeItem?.ticker}
            </SheetTitle>
            <div className="text-sm text-muted-foreground">
              现价 {price(activeResearch?.quote?.price)}{" "}
              {activeResearch?.quote?.currency}
            </div>
          </SheetHeader>
          <div className="p-4">
            {updatedAt && <p className="mb-2 text-xs text-muted-foreground">更新于 {updatedAt} · 本次 {((detailMs || 0) / 1000).toFixed(2)} 秒 · 每分钟自动更新</p>}
            {refreshing && <p role="status" className="mb-2 text-sm text-muted-foreground">正在自动更新</p>}
            {detailError && <p role="alert" className="mb-2 text-sm text-destructive">{detailError}</p>}
            {pending && !detailError ? (
              <div className="space-y-3" role="status">
                <div className="h-6 w-32 animate-pulse rounded bg-muted" />
                <div className="h-56 animate-pulse rounded-md bg-muted" />
                <div className="text-sm text-muted-foreground">
                  数据正在准备
                </div>
              </div>
            ) : (
              <>
                {activeItem && <details className="mb-4 rounded-lg border p-3"><summary className="min-h-9 cursor-pointer">备注与管理</summary><div className="mt-2 space-y-3"><Input key={`${activeItem.ticker}:${activeItem.notes}`} defaultValue={activeItem.notes} aria-label="股票备注" placeholder="添加备注" className="h-11 text-base" onBlur={event => { const notes = event.target.value; if (notes !== activeItem.notes) { setActiveItem(current => current ? { ...current, notes } : null); void call(() => api.updateWatchlistItem(group.id, activeItem.ticker, { notes })); } }} /><Button variant="outline" className="h-11 w-full" onClick={() => { if (window.confirm(`从“${group.name}”移除 ${activeItem.ticker}？`)) { void call(() => api.deleteWatchlistItem(group.id, activeItem.ticker)); setActiveItem(null); } }}>移出自选</Button></div></details>}
                <SecurityResearchDetails key={activeItem?.ticker} ticker={activeItem?.ticker} research={activeResearch} showNews={false} defaultExpanded />
              </>
            )}
            {activeItem && <SecurityFundamentals key={activeItem.ticker} ticker={activeItem.ticker} market={activeItem.market} name={activeItem.name} />}
          </div>
        </SheetContent>
      </Sheet>
    </Card>
  );

}

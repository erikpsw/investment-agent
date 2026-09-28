"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowDownUp, ArrowUp, BarChart3, FolderPlus, Search, Trash2 } from "lucide-react";
import { SecurityResearchDetails } from "@/components/security-research-details";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDebounce } from "@/hooks/use-debounce";
import { useSearch } from "@/hooks/use-search";
import { api, type SearchResult, type WatchlistGroup, type WatchlistItem } from "@/lib/api";

function price(value?: number | null) { return value == null || Number.isNaN(value) ? "--" : value.toLocaleString("zh-CN", { maximumFractionDigits: 3 }); }
function percent(value?: number | null) { return value == null || Number.isNaN(value) ? "--" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`; }
function volume(value?: number | null) { return value == null || Number.isNaN(value) ? "--" : value.toLocaleString("zh-CN", { maximumFractionDigits: 0 }); }
function quoteTime(value?: string | null) { if (!value) return "--"; const date = new Date(value); return Number.isNaN(date.getTime()) ? "--" : date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }); }

type SortKey = "ticker" | "market" | "price" | "day" | "fiveDay" | "volume";
type SortState = { key: SortKey; direction: "asc" | "desc" };

function ChangeValue({ value }: { value?: number | null }) {
  return <span className={value == null ? "text-muted-foreground" : value > 0 ? "text-emerald-600 dark:text-emerald-400" : value < 0 ? "text-red-600 dark:text-red-400" : "text-muted-foreground"}>{percent(value)}</span>;
}

function SortHeader({ label, sortKey, sort, onSort, className }: { label: string; sortKey: SortKey; sort: SortState; onSort: (key: SortKey) => void; className?: string }) {
  const active = sort.key === sortKey;
  const Icon = active ? sort.direction === "asc" ? ArrowUp : ArrowDown : ArrowDownUp;
  return <TableHead aria-sort={active ? sort.direction === "asc" ? "ascending" : "descending" : "none"} className={className}><Button type="button" variant="ghost" size="sm" className="-ml-2 h-8 px-2 font-medium" onClick={() => onSort(sortKey)}>{label}<Icon className="ml-1 h-3.5 w-3.5" /></Button></TableHead>;
}

function NotesEditor({ item, onSave }: { item: WatchlistItem; onSave: (notes: string) => Promise<void> }) {
  const [notes, setNotes] = useState(item.notes);
  const [savedNotes, setSavedNotes] = useState(item.notes);
  const [error, setError] = useState("");
  const save = async () => {
    if (notes === savedNotes) return;
    try { await onSave(notes); setSavedNotes(notes); setError(""); }
    catch { setError("保存失败，请重试"); }
  };
  return <div><Input aria-label={`${item.ticker} 备注`} value={notes} placeholder="备注" onChange={(event) => setNotes(event.target.value)} onBlur={() => void save()} />{error && <span role="alert" className="text-xs text-destructive">{error}</span>}</div>;
}

function SearchToAdd({ onSelect }: { onSelect: (result: SearchResult) => void }) {
  const [query, setQuery] = useState("");
  const debounced = useDebounce(query.trim(), 250);
  const search = useSearch(debounced, { limit: 8 });
  const results = search.data?.results || [];
  const waiting = query.trim() !== debounced || search.isPending || search.isFetching;
  return <div className="relative">
    <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
    <Input className="pl-9" value={query} placeholder="搜索代码或名称并添加" onChange={(event) => setQuery(event.target.value)} />
    {query.trim() && <div className="absolute z-40 mt-1 max-h-72 w-full overflow-y-auto rounded-md border bg-popover p-1 shadow-lg" role="listbox" aria-label="股票搜索结果">
      {waiting ? <p className="p-2 text-sm text-muted-foreground">搜索中…</p> : search.isError ? <p role="alert" className="p-2 text-sm text-destructive">搜索失败，请稍后重试</p> : results.length === 0 ? <p className="p-2 text-sm text-muted-foreground">没有匹配的股票，请检查完整代码</p> : results.map((result) => <button key={`${result.market}-${result.code}`} type="button" role="option" aria-selected={false} className="flex w-full items-center justify-between rounded px-3 py-2 text-left text-sm hover:bg-muted" onClick={() => { onSelect(result); setQuery(""); }}><span><strong>{result.name || result.code}</strong><span className="ml-2 text-muted-foreground">{result.code}</span></span><Badge variant="outline">{result.market}</Badge></button>)}
    </div>}
  </div>;
}

function ResearchButton({ item, groupId }: { item: WatchlistItem; groupId: string }) {
  const [research, setResearch] = useState(item.research);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const load = () => {
    setLoading(true);
    setError("");
    void api.getWatchlistItemResearch(groupId, item.ticker)
      .then((response) => setResearch(response.result))
      .catch((reason) => setError(reason instanceof Error ? reason.message : "加载研究资料失败"))
      .finally(() => setLoading(false));
  };
  return <Sheet onOpenChange={(open) => { if (open) load(); }}>
    <SheetTrigger render={<Button type="button" size="sm" variant="outline" aria-label={`${item.ticker} 走势与关键数据`} />}><BarChart3 className="mr-1" />走势与数据</SheetTrigger>
    <SheetContent side="right" className="w-[min(92vw,36rem)] overflow-y-auto"><SheetHeader><SheetTitle>{item.name || item.ticker} · {item.ticker}</SheetTitle></SheetHeader><div className="p-4">{loading ? <p>加载中…</p> : error ? <p role="alert" className="text-destructive">{error}</p> : <SecurityResearchDetails research={research} />}</div></SheetContent>
  </Sheet>;
}

export function WatchlistGroupCard({ group, groups, onReload, onAddChild }: { group: WatchlistGroup; groups: WatchlistGroup[]; onReload: () => Promise<void>; onAddChild: (parentId: string) => void }) {
  const [sort, setSort] = useState<SortState>({ key: "ticker", direction: "asc" });
  const sortedItems = useMemo(() => [...group.items].sort((left, right) => {
    const value = (item: WatchlistItem) => {
      const quote = item.research?.quote;
      switch (sort.key) {
        case "ticker": return item.ticker.toLocaleLowerCase();
        case "market": return item.market.toLocaleLowerCase();
        case "price": return quote?.price;
        case "day": return quote?.day_change_percent;
        case "fiveDay": return quote?.five_day_change_percent;
        case "volume": return quote?.volume;
      }
    };
    const a = value(left); const b = value(right);
    if (a == null) return b == null ? 0 : 1;
    if (b == null) return -1;
    const compared = typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b), "zh-CN");
    return sort.direction === "asc" ? compared : -compared;
  }), [group.items, sort]);
  const toggleSort = (key: SortKey) => setSort((current) => ({ key, direction: current.key === key ? current.direction === "asc" ? "desc" : "asc" : key === "ticker" || key === "market" ? "asc" : "desc" }));
  const call = async (action: () => Promise<unknown>) => { await action(); await onReload(); };
  return <Card className="overflow-visible"><CardHeader className="space-y-3"><div className="flex items-center gap-2"><Input key={group.id} aria-label="分组名称" className="min-w-0 flex-1 text-base font-semibold" defaultValue={group.name} onBlur={(event) => { const name = event.currentTarget.value.trim(); if (name && name !== group.name) void call(() => api.updateWatchlistGroup(group.id, { name })); }} /><Button type="button" size="icon" variant="outline" onClick={() => onAddChild(group.id)} aria-label="新建子分组"><FolderPlus /></Button><Button type="button" size="icon" variant="outline" onClick={() => { if (window.confirm(`删除“${group.name}”及其所有子分组和股票？`)) void call(() => api.deleteWatchlistGroup(group.id)); }} aria-label="删除分组"><Trash2 /></Button></div><label className="flex items-center gap-2 text-sm text-muted-foreground">移动到<select aria-label="移动分组" className="h-9 min-w-0 flex-1 rounded-md border bg-background px-2 text-foreground" value={group.parent_id || ""} onChange={(event) => void call(() => api.updateWatchlistGroup(group.id, { parent_id: event.target.value || null }))}><option value="">根分组</option>{groups.filter((candidate) => candidate.id !== group.id).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name}</option>)}</select></label><SearchToAdd onSelect={(result) => void call(() => api.addWatchlistItem(group.id, { ticker: result.code, name: result.name, market: result.market, notes: "" }))} /></CardHeader><CardContent>{group.items.length === 0 ? <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">该分组暂无自选股</div> : <div className="overflow-x-auto"><Table className="w-full min-w-[1120px] text-xs sm:text-sm"><TableHeader><TableRow><SortHeader label="代码 / 名称" sortKey="ticker" sort={sort} onSort={toggleSort} /><SortHeader label="市场" sortKey="market" sort={sort} onSort={toggleSort} /><SortHeader label="现价" sortKey="price" sort={sort} onSort={toggleSort} /><SortHeader label="当日涨跌" sortKey="day" sort={sort} onSort={toggleSort} /><SortHeader label="5 日涨跌" sortKey="fiveDay" sort={sort} onSort={toggleSort} /><SortHeader label="成交量" sortKey="volume" sort={sort} onSort={toggleSort} /><TableHead>报价时间</TableHead><TableHead>备注</TableHead><TableHead className="w-36 text-right">操作</TableHead></TableRow></TableHeader><TableBody>{sortedItems.map((item) => { const quote = item.research?.quote; return <TableRow key={item.ticker}><TableCell><div className="font-medium">{item.ticker}</div><div className="text-xs text-muted-foreground">{item.name}</div></TableCell><TableCell><Badge variant="outline">{item.market}</Badge></TableCell><TableCell>{price(quote?.price)} {quote?.currency}</TableCell><TableCell><ChangeValue value={quote?.day_change_percent} /></TableCell><TableCell title={quote?.five_day_asof ? `截至 ${quote.five_day_asof}` : undefined}><ChangeValue value={quote?.five_day_change_percent} /></TableCell><TableCell>{volume(quote?.volume)}</TableCell><TableCell title={quote?.fetched_at || undefined}>{quoteTime(quote?.fetched_at)}</TableCell><TableCell><NotesEditor key={`${group.id}:${item.ticker}`} item={item} onSave={async (notes) => { await api.updateWatchlistItem(group.id, item.ticker, { notes }); }} /></TableCell><TableCell className="text-right"><ResearchButton item={item} groupId={group.id} /><Button type="button" size="icon" variant="ghost" onClick={() => { if (window.confirm(`从“${group.name}”移除 ${item.ticker}？`)) void call(() => api.deleteWatchlistItem(group.id, item.ticker)); }} aria-label={`删除 ${item.ticker}`}><Trash2 /></Button></TableCell></TableRow>; })}</TableBody></Table></div>}</CardContent></Card>;
}

"use client";

import { useUser } from "@auth0/nextjs-auth0";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FolderPlus,
  Loader2,
  Plus,
  RefreshCw,
} from "lucide-react";

import { Header } from "@/components/header";
import { WatchlistGroupCard } from "@/components/watchlist-group-card";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  api,
  type SecurityResearch,
  type WatchlistGroup,
  type WatchlistItem,
} from "@/lib/api";

type SidebarNode = {
  id: string;
  name: string;
  group?: WatchlistGroup;
  children: SidebarNode[];
  depth?: number;
};
const MARKET_ROOTS = ["A股", "港股", "美股", "其他"] as const;
const WATCHLIST_TREE_CACHE_TTL_MS = 12 * 60 * 60 * 1000;

type WatchlistTreeCache = {
  cachedAt: number;
  groups: WatchlistGroup[];
};

function treeCacheKey(userSub: string) {
  return `watchlist:tree:${userSub}`;
}

function readTreeCache(userSub: string): WatchlistGroup[] | null {
  try {
    const key = treeCacheKey(userSub);
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const cached = JSON.parse(raw) as WatchlistTreeCache;
    if (
      !Array.isArray(cached.groups) ||
      typeof cached.cachedAt !== "number" ||
      Date.now() - cached.cachedAt > WATCHLIST_TREE_CACHE_TTL_MS
    ) {
      window.localStorage.removeItem(key);
      return null;
    }
    return cached.groups;
  } catch {
    return null;
  }
}

function writeTreeCache(userSub: string, groups: WatchlistGroup[]) {
  try {
    window.localStorage.setItem(
      treeCacheKey(userSub),
      JSON.stringify({
        cachedAt: Date.now(),
        groups,
      } satisfies WatchlistTreeCache),
    );
  } catch {
    // Local storage can be unavailable in privacy-restricted browsing contexts.
  }
}

function flatten(
  groups: WatchlistGroup[],
  depth = 0,
): Array<WatchlistGroup & { depth: number }> {
  return groups.flatMap((group) => [
    { ...group, depth },
    ...flatten(group.children || [], depth + 1),
  ]);
}
function groupMarket(group: WatchlistGroup): (typeof MARKET_ROOTS)[number] {
  if (group.name.startsWith("A股") || group.name.includes("ETF")) return "A股";
  if (group.name.startsWith("港股")) return "港股";
  if (group.name.startsWith("美股")) return "美股";
  const market =
    group.items[0]?.market || group.children?.[0]?.items?.[0]?.market;
  return market === "CN"
    ? "A股"
    : market === "HK"
      ? "港股"
      : market === "US"
        ? "美股"
        : "其他";
}
function groupNode(group: WatchlistGroup): SidebarNode {
  return {
    id: group.id,
    name: group.name,
    group,
    children: (group.children || []).map(groupNode),
  };
}
function marketTree(groups: WatchlistGroup[]): SidebarNode[] {
  const byMarket = new Map(
    MARKET_ROOTS.map((market) => [market, [] as SidebarNode[]]),
  );
  groups.forEach((group) =>
    byMarket.get(groupMarket(group))?.push(groupNode(group)),
  );
  return MARKET_ROOTS.flatMap((market) => {
    const children = byMarket.get(market) || [];
    return children.length
      ? [{ id: `market:${market}`, name: market, children }]
      : [];
  });
}
function flattenVisible(
  nodes: SidebarNode[],
  expanded: Set<string>,
  depth = 0,
): Array<SidebarNode & { depth: number }> {
  return nodes.flatMap((node) => [
    { ...node, depth },
    ...(expanded.has(node.id)
      ? flattenVisible(node.children, expanded, depth + 1)
      : []),
  ]);
}
function researchKey(item: Pick<WatchlistItem, "market" | "ticker">) {
  return `${item.market.toUpperCase()}:${item.ticker.toUpperCase()}`;
}

export default function WatchlistPage() {
  const { user, isLoading: authLoading } = useUser();
  const [groups, setGroups] = useState<WatchlistGroup[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [researchByTicker, setResearchByTicker] = useState<
    Record<string, SecurityResearch>
  >({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [groupQuery, setGroupQuery] = useState("");
  const [marketFilter, setMarketFilter] = useState<string>("全部");
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteMs, setQuoteMs] = useState<number | null>(null);
  const [treeMs, setTreeMs] = useState<number | null>(null);
  const [treeLoading, setTreeLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const applyGroups = useCallback((nextGroups: WatchlistGroup[]) => {
    const nodes = flatten(nextGroups);
    const tree = marketTree(nextGroups);
    setGroups(nextGroups);
    const ids = nodes.map((group) => group.id);
    setExpanded(current => current.size ? current : new Set(tree.slice(0, 1).map(node => node.id)));
    setSelectedId((current) =>
      ids.includes(current) ? current : ids[0] || "",
    );
  }, []);
  const load = useCallback(async (refreshQuotes = false) => {
    const started = performance.now();
    const response = await api.getWatchlists(undefined, false, false);
    setTreeMs(Math.round(performance.now() - started));
    setTreeLoading(false);
    if (refreshQuotes) setRevision(value => value + 1);
    const nextGroups = response.result.groups;
    applyGroups(nextGroups);
    if (user?.sub) writeTreeCache(user.sub, nextGroups);
  }, [applyGroups, user?.sub]);
  useEffect(() => {
    if (!authLoading && user) {
      const cachedGroups = readTreeCache(user.sub);
      if (cachedGroups) {
        applyGroups(cachedGroups);
        try {
          const lastGroup = window.localStorage.getItem(`watchlist:selected:${user.sub}`);
          if (lastGroup && flatten(cachedGroups).some(group => group.id === lastGroup)) setSelectedId(lastGroup);
        } catch { /* Local preferences are optional. */ }
      }
      void load().catch((error) =>
        { setTreeLoading(false); setMessage(error instanceof Error ? error.message : "加载自选股失败"); },
      );
    }
  }, [applyGroups, authLoading, load, user]);
  const nodes = useMemo(() => flatten(groups), [groups]);
  const tree = useMemo(() => marketTree(groups), [groups]);
  const visibleNodes = useMemo(
    () => flattenVisible(tree, expanded),
    [tree, expanded],
  );
  const selected = nodes.find((group) => group.id === selectedId);
  useEffect(() => {
    if (!selectedId || !user) return;
    let cancelled = false;
    let running = false;
    const refresh = async () => {
      if (cancelled || running || document.hidden) return;
      running = true;
      const started = performance.now();
      setQuoteLoading(true);
      try {
        const response = await api.getWatchlists(selectedId, false, true);
        if (cancelled) return;
        setResearchByTicker(current => ({ ...current, ...Object.fromEntries(
          (response.result.groups[0]?.items || []).map(item => [researchKey(item), item.research || {}]),
        ) }));
        setQuoteMs(Math.round(performance.now() - started));
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "更新报价失败");
      } finally {
        running = false;
        if (!cancelled) setQuoteLoading(false);
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60_000);
    const onVisible = () => { if (!document.hidden) void refresh(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [selectedId, revision, user]);
  const filteredGroups = nodes.filter(group =>
    (marketFilter === "全部" || groupMarket(group) === marketFilter) && group.name.toLowerCase().includes(groupQuery.trim().toLowerCase()),
  );
  const chooseGroup = (id: string) => {
    setSelectedId(id); setPickerOpen(false);
    if (user?.sub) { try { window.localStorage.setItem(`watchlist:selected:${user.sub}`, id); } catch { /* Optional preference. */ } }
  };
  const addGroup = async (parentId?: string) => {
    setBusy(true);
    try {
      const id = crypto.randomUUID();
      await api.createWatchlistGroup({
        id,
        name: parentId ? "新子分组" : "新分组",
        parent_id: parentId || null,
      });
      await load(true);
      setSelectedId(id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建分组失败");
    } finally {
      setBusy(false);
    }
  };
  const toggle = (id: string) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  if (authLoading)
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex flex-1 items-center justify-center">
          <Loader2 className="animate-spin" />
        </main>
      </div>
    );
  if (!user)
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex flex-1 items-center justify-center p-6">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>登录后管理自选股</CardTitle>
              <CardDescription>
                分组和自选股会按账户保存到云端。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                className="w-full"
                render={
                  <Link
                    href="/auth/login?returnTo=/watchlist"
                    prefetch={false}
                  />
                }
              >
                登录 / 注册
              </Button>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 p-4 sm:p-6">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">自选股</h1>
            <p className="text-muted-foreground">
              按市场与自定义层级组织关注标的。
            </p>
          </div>
          <Button onClick={() => void addGroup()} disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 animate-spin" />
            ) : (
              <Plus className="mr-2" />
            )}
            新建分组
          </Button>
        </div>
        {message && (
          <div className="mb-4 rounded-lg border px-4 py-3 text-sm">
            {message}
          </div>
        )}
        <div className="sticky top-0 z-20 mb-3 flex items-center gap-2 rounded-xl border bg-background/95 p-2 backdrop-blur lg:hidden">
          <Button variant="outline" className="h-12 min-w-0 flex-1 justify-between" onClick={() => setPickerOpen(true)} aria-label="切换自选分组">
            <span className="truncate">{selected?.name || "选择分组"}</span><ChevronDown className="ml-2 shrink-0" />
          </Button>
          <span className="shrink-0 px-2 text-xs text-muted-foreground">{selected?.items.length || 0} 只</span>
        </div>
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground" role="status">
          <Button variant="outline" className="min-h-11" onClick={() => setRevision(value => value + 1)} disabled={quoteLoading || !selectedId} aria-label="刷新本组报价"><RefreshCw className="mr-1 h-4 w-4" />刷新</Button>
          <span>{quoteLoading ? "正在更新报价，列表可先浏览" : quoteMs !== null ? `报价已更新 · ${(quoteMs / 1000).toFixed(2)} 秒` : treeLoading ? "正在同步分组" : "选择分组查看报价"}</span>
          {treeMs !== null && <span>分组同步 {(treeMs / 1000).toFixed(2)} 秒</span>}
        </div>
        <Sheet open={pickerOpen} onOpenChange={setPickerOpen}>
          <SheetContent side="bottom" className="[&>button]:size-11 max-h-[85dvh] rounded-t-2xl pb-[max(1rem,env(safe-area-inset-bottom))]">
            <SheetHeader><SheetTitle>选择分组</SheetTitle></SheetHeader>
            <div className="space-y-3 px-4">
              <Input aria-label="搜索分组" placeholder="搜索行业或分组" value={groupQuery} onChange={event => setGroupQuery(event.target.value)} className="h-12 text-base" />
              <div className="flex gap-1" aria-label="按市场筛选分组">{["全部", ...MARKET_ROOTS].map(market => <button key={market} type="button" aria-pressed={marketFilter === market} className={`min-h-11 flex-1 rounded-lg text-sm ${marketFilter === market ? "bg-primary text-primary-foreground" : "bg-muted"}`} onClick={() => setMarketFilter(market)}>{market}</button>)}</div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-4" aria-label="分组列表">
              {filteredGroups.map(group => <button key={group.id} type="button" aria-current={group.id === selectedId ? "true" : undefined} className={`mb-1 flex min-h-12 w-full items-center justify-between rounded-lg px-3 text-left ${group.id === selectedId ? "bg-primary/10 font-medium text-primary" : "hover:bg-muted"}`} onClick={() => chooseGroup(group.id)}><span className="min-w-0 truncate">{group.name}</span><span className="ml-3 shrink-0 text-xs text-muted-foreground">{group.items.length} 只</span></button>)}
              {!filteredGroups.length && <p className="py-8 text-center text-muted-foreground">没有匹配的分组</p>}
            </div>
          </SheetContent>
        </Sheet>
        <div className="grid min-w-0 gap-4 lg:grid-cols-[14rem_minmax(0,1fr)]">
          <Card className="hidden h-fit max-h-[calc(100dvh-10rem)] overflow-y-auto lg:block">
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-base">分组</CardTitle>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => void addGroup()}
                aria-label="新建根分组"
              >
                <FolderPlus />
              </Button>
            </CardHeader>
            <CardContent
              className="space-y-1"
              role="tree"
              aria-label="自选分组"
            >
              {visibleNodes.map((node) => {
                const hasChildren = node.children.length > 0;
                const open = expanded.has(node.id);
                const selectedNode = node.group?.id === selectedId;
                return (
                  <div
                    key={node.id}
                    role="treeitem"
                    aria-selected={selectedNode}
                    aria-level={(node.depth || 0) + 1}
                    aria-expanded={hasChildren ? open : undefined}
                    style={{ paddingLeft: `${node.depth * 16 + 8}px` }}
                    className={`flex w-full items-center gap-1 rounded-md py-1 pr-2 text-left text-sm ${selectedNode ? "bg-muted font-medium" : ""}`}
                  >
                    {hasChildren ? (
                      <button
                        type="button"
                        aria-label={`切换 ${node.name}`}
                        className="rounded p-0.5 hover:bg-background"
                        onClick={() => toggle(node.id)}
                      >
                        {open ? (
                          <ChevronDown className="size-4" />
                        ) : (
                          <ChevronRight className="size-4" />
                        )}
                      </button>
                    ) : (
                      <span className="size-5" />
                    )}
                    <button
                      type="button"
                      className="min-w-0 flex-1 rounded-md py-1 text-left hover:bg-muted"
                      onClick={() =>
                        node.group
                          ? chooseGroup(node.group.id)
                          : toggle(node.id)
                      }
                    >
                      {node.name}
                    </button>
                  </div>
                );
              })}
            </CardContent>
          </Card>
          <section className="min-w-0">
            {selected ? (
              <WatchlistGroupCard
                group={selected}
                groups={nodes}
                researchByTicker={researchByTicker}
                onReload={() => load(true)}
                onAddChild={(parentId) => void addGroup(parentId)}
              />
            ) : (
              <Card>
                <CardContent className="p-8 text-center text-muted-foreground">
                  新建分组后即可开始管理自选股。
                </CardContent>
              </Card>
            )}
          </section>
        </div>
      </main>
    </div>
  );

}

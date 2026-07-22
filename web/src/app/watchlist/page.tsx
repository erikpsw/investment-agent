"use client";

import { useUser } from "@auth0/nextjs-auth0";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Plus, Save } from "lucide-react";

import { Header } from "@/components/header";
import { WatchlistGroupCard } from "@/components/watchlist-group-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type SearchResult, type WatchlistGroup, type WatchlistItem } from "@/lib/api";


export default function WatchlistPage() {
  const { user, isLoading: authLoading } = useUser();
  const [groups, setGroups] = useState<WatchlistGroup[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    const response = await api.getWatchlists(undefined, true);
    setGroups(response.result.groups);
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    setBusy(true);
    void load()
      .catch((error) => setMessage(error instanceof Error ? error.message : "加载自选股失败"))
      .finally(() => setBusy(false));
  }, [authLoading, load, user]);

  const addGroup = () => {
    setGroups((current) => [
      ...current,
      { id: crypto.randomUUID(), name: `自选分组 ${current.length + 1}`, items: [] },
    ]);
  };

  const updateGroup = (index: number, patch: Partial<WatchlistGroup>) => {
    setGroups((current) => current.map((group, currentIndex) => currentIndex === index ? { ...group, ...patch } : group));
  };

  const moveGroup = (index: number, direction: -1 | 1) => {
    setGroups((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const deleteGroup = (index: number) => {
    const group = groups[index];
    if (group.items.length && !window.confirm(`分组“${group.name}”包含 ${group.items.length} 只股票，确认删除？`)) return;
    setGroups((current) => current.filter((_, currentIndex) => currentIndex !== index));
  };

  const addItem = (groupIndex: number, result: SearchResult) => {
    const group = groups[groupIndex];
    if (!group) return;
    if (group.items.some((item) => item.ticker.toLowerCase() === result.code.toLowerCase())) {
      setMessage(`${result.code} 已在“${group.name}”中`);
      return;
    }
    setGroups((current) => current.map((currentGroup, index) => {
      if (index !== groupIndex) return currentGroup;
      return {
        ...currentGroup,
        items: [...currentGroup.items, { ticker: result.code, name: result.name, market: result.market, notes: "" }],
      };
    }));
  };

  const updateItem = (groupIndex: number, itemIndex: number, patch: Partial<WatchlistItem>) => {
    setGroups((current) => current.map((group, index) => index === groupIndex ? {
      ...group,
      items: group.items.map((item, currentItemIndex) => currentItemIndex === itemIndex ? { ...item, ...patch } : item),
    } : group));
  };

  const deleteItem = (groupIndex: number, itemIndex: number) => {
    setGroups((current) => current.map((group, index) => index === groupIndex ? {
      ...group,
      items: group.items.filter((_, currentItemIndex) => currentItemIndex !== itemIndex),
    } : group));
  };

  const save = async () => {
    setBusy(true);
    try {
      await api.saveWatchlists(groups);
      await load();
      setMessage("自选股已保存并同步到云端");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存自选股失败");
    } finally {
      setBusy(false);
    }
  };

  if (authLoading) return <Loading />;
  if (!user) {
    return (
      <div className="flex min-h-screen flex-col"><Header /><main className="flex flex-1 items-center justify-center p-6"><Card className="w-full max-w-md"><CardHeader><CardTitle>登录后管理自选股</CardTitle><CardDescription>分组和自选股会按账户保存到云端。</CardDescription></CardHeader><CardContent><Button className="w-full" render={<Link href="/auth/login?returnTo=/watchlist" prefetch={false} />}>登录 / 注册</Button></CardContent></Card></main></div>
    );
  }

  const groupProps = (group: WatchlistGroup, index: number) => ({
    group,
    canMoveUp: index > 0,
    canMoveDown: index < groups.length - 1,
    onRename: (name: string) => updateGroup(index, { name }),
    onMove: (direction: -1 | 1) => moveGroup(index, direction),
    onDelete: () => deleteGroup(index),
    onAdd: (result: SearchResult) => addItem(index, result),
    onUpdateItem: (itemIndex: number, patch: Partial<WatchlistItem>) => updateItem(index, itemIndex, patch),
    onDeleteItem: (itemIndex: number) => deleteItem(index, itemIndex),
  });

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 space-y-6 p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><h1 className="text-3xl font-bold tracking-tight">自选股</h1><p className="text-muted-foreground">按分组维护关注标的，查看多周期走势与关键数据。</p></div>
          <div className="flex gap-2"><Button variant="outline" onClick={addGroup} disabled={busy}><Plus className="mr-2" />新建分组</Button><Button onClick={save} disabled={busy}>{busy ? <Loader2 className="mr-2 animate-spin" /> : <Save className="mr-2" />}保存</Button></div>
        </div>
        {message && <div className="rounded-lg border px-4 py-3 text-sm">{message}</div>}
        {groups.length === 0 && <Card><CardContent className="p-8 text-center text-muted-foreground">暂无分组，点击“新建分组”开始添加自选股。</CardContent></Card>}
        <div data-testid="mobile-watchlist-groups" className="space-y-4 md:hidden">
          {groups.map((group, index) => <WatchlistGroupCard key={group.id} {...groupProps(group, index)} mobile />)}
        </div>
        <div data-testid="desktop-watchlist-groups" className="hidden space-y-4 md:block">
          {groups.map((group, index) => <WatchlistGroupCard key={group.id} {...groupProps(group, index)} mobile={false} />)}
        </div>
      </main>
    </div>
  );
}


function Loading() {
  return <div className="flex min-h-screen flex-col"><Header /><main className="flex flex-1 items-center justify-center"><Loader2 className="animate-spin" /></main></div>;
}

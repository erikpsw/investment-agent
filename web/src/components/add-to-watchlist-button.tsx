"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { useUser } from "@auth0/nextjs-auth0";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Star } from "lucide-react";
import { api, type WatchlistGroup } from "@/lib/api";
import { securityMarket } from "@/lib/financial-reports";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

function flattenGroups(groups: WatchlistGroup[], path = ""): Array<{ group: WatchlistGroup; label: string }> {
  return groups.flatMap(group => {
    const label = path ? `${path} / ${group.name}` : group.name;
    return [{ group, label }, ...flattenGroups(group.children || [], label)];
  });
}

export function AddToWatchlistButton({ ticker, name = "", market, compact = false, onResult }: {
  ticker: string; name?: string; market?: string | null; compact?: boolean; onResult: (message: string) => void;
}) {
  const { user, isLoading } = useUser();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const selectId = useId();
  const resolvedMarket = securityMarket(ticker, market);
  const groups = useQuery({ queryKey: ["watchlist-groups", user?.sub], queryFn: () => api.getWatchlists(undefined, false, false), enabled: open && !!user, staleTime: 30000, retry: false });
  const choices = flattenGroups(groups.data?.result.groups || []);
  const selected = choices.find(item => item.group.id === groupId)?.group;
  const exists = selected?.items.some(item => item.ticker.toUpperCase() === ticker.toUpperCase() && item.market === resolvedMarket);
  const buttonClass = compact ? "min-h-11 min-w-11" : "min-h-11 w-full";

  if (!user && !isLoading) return <Button variant="outline" className={buttonClass} aria-label="登录后添加到自选" render={<Link href={`/auth/login?returnTo=${encodeURIComponent(`/stock/${ticker}`)}`} prefetch={false} />}>{compact ? <Star className="h-4 w-4" /> : "登录后添加到自选"}</Button>;

  const add = async () => {
    if (!selected || exists || saving) return;
    setSaving(true);
    setError("");
    try {
      await api.addWatchlistItem(selected.id, { ticker, name, market: resolvedMarket, notes: "" });
      await queryClient.invalidateQueries({ queryKey: ["watchlist-groups", user?.sub] });
      setOpen(false);
      onResult(`已添加 ${name || ticker} 到「${selected.name}」`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "添加失败，请重试");
    } finally { setSaving(false); }
  };

  return <>
    <Button variant="outline" className={buttonClass} disabled={isLoading} aria-label={compact ? "选择分组添加到自选" : undefined} onClick={() => { setError(""); setGroupId(""); setOpen(true); }}>{compact ? <Star className="h-4 w-4" /> : "添加到自选"}</Button>
    <Dialog open={open} onOpenChange={next => { if (!saving) setOpen(next); }}>
      <DialogContent>
        <DialogHeader><DialogTitle>添加到自选</DialogTitle><DialogDescription>{name || ticker} · {ticker}，请选择保存分组。</DialogDescription></DialogHeader>
        {groups.isLoading ? <p role="status">正在加载分组…</p> : groups.isError ? <div role="alert">分组加载失败。<Button variant="outline" onClick={() => groups.refetch()}>重试</Button></div> : choices.length === 0 ? <p>暂无分组，<Link className="underline" href="/watchlist">前往自选股创建分组</Link>。</p> : <label htmlFor={selectId} className="space-y-2 text-sm"><span className="block">自选分组</span><select id={selectId} value={groupId} disabled={saving} onChange={event => { setGroupId(event.target.value); setError(""); }} className="min-h-11 w-full rounded-md border bg-background px-3"><option value="">请选择分组</option>{choices.map(({group, label}) => <option key={group.id} value={group.id}>{label}</option>)}</select></label>}
        {exists && <p role="status">该股票已在此分组中，请选择其他分组。</p>}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2"><Button variant="outline" className="min-h-11" disabled={saving} onClick={() => setOpen(false)}>取消</Button><Button className="min-h-11" disabled={!selected || exists || saving || groups.isError} onClick={() => void add()}>{saving ? "正在添加…" : "确认添加"}</Button></div>
      </DialogContent>
    </Dialog>
  </>;
}

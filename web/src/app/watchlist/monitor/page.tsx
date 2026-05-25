"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Loader2, Play, RefreshCw, Save, Square } from "lucide-react";
import { Header } from "@/components/header";
import { MarkdownContent } from "@/components/markdown-content";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, type MonitorDecision, type MonitorEvent, type MonitorStatus } from "@/lib/api";

function displayTime(value?: string | number) {
  if (!value) return "--";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

function eventTitle(event: MonitorEvent) {
  return event.title || event.summary?.slice(0, 70) || "未命名事件";
}

type ParsedDecision = {
  summary?: string;
  reviewed_event_ids?: string[];
  important_events?: Array<Record<string, unknown>>;
  ignored_reason?: unknown;
};

function parseDecision(value?: string): ParsedDecision | null {
  if (!value) return null;
  const text = value.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
  try {
    const parsed = JSON.parse(text) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as ParsedDecision : null;
  } catch {
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start < 0 || end <= start) return null;
    try {
      return JSON.parse(text.slice(start, end + 1)) as ParsedDecision;
    } catch {
      return null;
    }
  }
}

function textValue(value: unknown) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function DecisionView({ decision }: { decision: ParsedDecision }) {
  const important = Array.isArray(decision.important_events) ? decision.important_events : [];
  const reviewed = Array.isArray(decision.reviewed_event_ids) ? decision.reviewed_event_ids : [];
  const ignored = decision.ignored_reason && typeof decision.ignored_reason === "object" && !Array.isArray(decision.ignored_reason)
    ? Object.entries(decision.ignored_reason as Record<string, unknown>)
    : [];

  return (
    <div className="flex flex-col gap-4">
      {decision.summary && <p className="rounded-lg border bg-muted/30 p-3 text-sm leading-6">{decision.summary}</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg bg-muted p-3">
          <p className="text-xs text-muted-foreground">已审阅事件</p>
          <p className="mt-1 text-2xl font-semibold">{reviewed.length}</p>
        </div>
        <div className="rounded-lg bg-muted p-3">
          <p className="text-xs text-muted-foreground">重要事件</p>
          <p className="mt-1 text-2xl font-semibold">{important.length}</p>
        </div>
      </div>
      {important.map((event, index) => (
        <article key={`${textValue(event.event_id)}-${index}`} className="rounded-lg border p-3">
          <h3 className="text-sm font-medium leading-6">{textValue(event.title_cn || event.title || event.event_id || `事件 ${index + 1}`)}</h3>
          {(event.content_summary || event.reason) && <p className="mt-1 text-sm leading-6 text-muted-foreground">内容概述：{textValue(event.content_summary || event.reason)}</p>}
          {(event.sector_impact || event.action || event.action_taken) && <p className="mt-1 text-sm leading-6 text-muted-foreground">关注板块影响：{textValue(event.sector_impact || event.action || event.action_taken)}</p>}
        </article>
      ))}
      {important.length === 0 && <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">本轮没有标记为需要即时处理的重要事件。</p>}
      {ignored.length > 0 && (
        <div className="rounded-lg border p-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">未提醒原因</p>
          <div className="flex flex-col gap-2">
            {ignored.map(([id, reason]) => (
              <p key={id} className="text-sm leading-6"><span className="font-medium">{id}</span>：<span className="text-muted-foreground">{textValue(reason)}</span></p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function MonitorPage() {
  const [status, setStatus] = useState<MonitorStatus | null>(null);
  const [events, setEvents] = useState<MonitorEvent[]>([]);
  const [logs, setLogs] = useState<Array<Record<string, unknown>>>([]);
  const [decisions, setDecisions] = useState<MonitorDecision[]>([]);
  const [profile, setProfile] = useState("");
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [profileDirty, setProfileDirty] = useState(false);
  const [intervalSeconds, setIntervalSeconds] = useState("60");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const latestDecision = decisions[decisions.length - 1];
  const parsedDecision = useMemo(() => parseDecision(latestDecision?.analysis), [latestDecision?.analysis]);

  const loadRuntime = useCallback(async () => {
    const [statusResponse, eventResponse, logResponse, decisionResponse] = await Promise.all([
      api.getMonitorStatus(),
      api.getMonitorEvents(80),
      api.getMonitorLogs(80),
      api.getMonitorDecisions(20),
    ]);
    setStatus(statusResponse.result);
    setEvents(eventResponse.result);
    setLogs(logResponse.result);
    setDecisions(decisionResponse.result);
    setIntervalSeconds(String(statusResponse.result.interval_seconds || 60));
  }, []);

  useEffect(() => {
    void loadRuntime().catch((error) => setMessage(error instanceof Error ? error.message : "加载盯盘状态失败"));
    void api.getUserProfile().then((response) => {
      setProfile(response.result.content);
      setProfileLoaded(true);
    }).catch((error) => setMessage(error instanceof Error ? error.message : "加载用户偏好失败"));
    const timer = window.setInterval(() => void loadRuntime(), 15000);
    return () => window.clearInterval(timer);
  }, [loadRuntime]);

  const start = async () => {
    setBusy(true);
    try {
      const response = await api.startMonitor({
        interval_seconds: Number(intervalSeconds) || 60,
        dry_run: false,
        channels: ["flashes", "macro", "tech"],
      });
      setStatus(response.result);
      setMessage("盯盘已启动");
      await loadRuntime();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "启动失败");
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      const response = await api.stopMonitor();
      setStatus(response.result);
      setMessage("盯盘已停止");
      await loadRuntime();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "停止失败");
    } finally {
      setBusy(false);
    }
  };

  const refresh = async () => {
    setBusy(true);
    try {
      const response = await api.refreshMonitorEvents({ dry_run: false, limit: 30, channels: ["flashes", "macro", "tech"] });
      setMessage(`刷新完成，新增 ${response.result.added} 条事件`);
      await loadRuntime();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "刷新失败");
    } finally {
      setBusy(false);
    }
  };

  const saveProfile = async () => {
    setBusy(true);
    try {
      await api.updateUserProfile(profile);
      setProfileDirty(false);
      setMessage("USER.md 已保存");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col gap-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">实时盯盘</h1>
            <p className="text-muted-foreground">MacroStream 事件流、运行日志和投资偏好控制台。</p>
          </div>
          <Badge variant={status?.running ? "default" : "secondary"}>
            {status?.running ? "运行中" : "已停止"}
          </Badge>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Activity />监控控制</CardTitle>
            <CardDescription>事件按本地缓存去重；启动后按间隔自动刷新。</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-2">
              <label className="text-sm text-muted-foreground" htmlFor="interval">轮询间隔（秒）</label>
              <Input id="interval" className="w-36" type="number" min={20} value={intervalSeconds} onChange={(event) => setIntervalSeconds(event.target.value)} />
            </div>
            <Button onClick={start} disabled={busy || status?.running}>
              {busy ? <Loader2 data-icon="inline-start" className="animate-spin" /> : <Play data-icon="inline-start" />}
              启动盯盘
            </Button>
            <Button variant="outline" onClick={stop} disabled={busy || !status?.running}>
              <Square data-icon="inline-start" />停止
            </Button>
            <Button variant="outline" onClick={refresh} disabled={busy}>
              <RefreshCw data-icon="inline-start" />立即刷新
            </Button>
            <div className="text-sm text-muted-foreground">
              已缓存 {status?.event_count ?? 0} 条事件 / {status?.decision_count ?? decisions.length} 轮决策
            </div>
          </CardContent>
        </Card>

        {message && <div className="rounded-lg border px-4 py-3 text-sm">{message}</div>}

        <Card>
          <CardHeader>
            <CardTitle>Agent 最新决策原因</CardTitle>
            <CardDescription>展示 Agent 本轮筛选重要事件、决定提醒或忽略的依据。</CardDescription>
          </CardHeader>
          <CardContent>
            {latestDecision?.analysis ? (
              <div className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">{displayTime(latestDecision.finished_at || latestDecision.started_at)}</Badge>
                  <span>新增事件 {latestDecision.new_events ?? 0}</span>
                  <span>工具调用 {latestDecision.tool_trace?.length ?? 0}</span>
                  <span>提醒 {latestDecision.alerts?.length ?? 0}</span>
                </div>
                {parsedDecision ? <DecisionView decision={parsedDecision} /> : <MarkdownContent content={latestDecision.analysis} />}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">暂无决策记录。点击“立即刷新”或启动盯盘后会生成并显示判断原因。</p>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(340px,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle>事件流</CardTitle>
              <CardDescription>最近拉取到的快讯和文章，按时间倒序展示。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {events.length === 0 && <p className="text-sm text-muted-foreground">暂无事件，点击“立即刷新”获取最新内容。</p>}
              {events.map((event, index) => (
                <article key={event.id || index} className="rounded-lg border p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="outline">{event.channel || event.type || "event"}</Badge>
                    <span>{displayTime(event.published_at_iso || event.published_at)}</span>
                    {event.source_url && <a className="underline" target="_blank" rel="noreferrer" href={event.source_url}>原文</a>}
                  </div>
                  <h2 className="text-sm font-medium leading-6">{eventTitle(event)}</h2>
                  {event.summary && event.title && <p className="mt-1 line-clamp-3 text-sm leading-6 text-muted-foreground">{event.summary}</p>}
                </article>
              ))}
            </CardContent>
          </Card>

          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader>
                <CardTitle>USER.md</CardTitle>
                <CardDescription>Agent 用于判断关注方向和提醒阈值的偏好文件。</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Textarea
                  disabled={!profileLoaded}
                  value={profile}
                  onChange={(event) => { setProfile(event.target.value); setProfileDirty(true); }}
                  className="min-h-72 font-mono text-xs"
                />
                <Button onClick={saveProfile} disabled={busy || !profileDirty}>
                  <Save data-icon="inline-start" />保存偏好
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>运行日志</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {logs.slice(0, 12).map((log, index) => (
                  <div key={index} className="rounded-md bg-muted p-2 text-xs">
                    <span className="text-muted-foreground">{displayTime(String(log.timestamp || ""))}</span>
                    <span className="ml-2">{String(log.message || "")}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </>
  );
}

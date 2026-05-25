"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ExternalLink, Loader2, RefreshCw, Sparkles, Target, Trash2 } from "lucide-react";
import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, type StockPickItem, type StockPickerResult } from "@/lib/api";
import { cn } from "@/lib/utils";

const MARKETS = [
  { key: "CN", label: "A股" },
  { key: "US", label: "美股" },
];

function formatTime(value?: string) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatPct(value?: number | null) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(2)}%`;
}

function asList(value?: string[]) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function PickCard({ item, muted = false }: { item: StockPickItem; muted?: boolean }) {
  const reasons = asList(item.reasons);
  const risks = asList(item.risks);
  const news = Array.isArray(item.recent_news) ? item.recent_news.filter((article) => article?.title) : [];
  const score = Number(item.score ?? 0);
  return (
    <div className={cn("rounded-lg border p-4", muted && "bg-muted/20")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link href={`/stock/${encodeURIComponent(item.ticker)}`} className="text-lg font-semibold hover:underline">
              {item.ticker}
            </Link>
            <span className="text-sm text-muted-foreground">{item.name}</span>
            {item.market && <Badge variant="outline">{item.market}</Badge>}
            {item.theme && <Badge variant="secondary">{item.theme}</Badge>}
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.why_now || "等待更多确认信号。"}</p>
        </div>
        <div className="w-24 text-right">
          <div className="text-xs text-muted-foreground">评分</div>
          <div className={cn("text-2xl font-semibold", score >= 75 ? "text-green-600" : score >= 62 ? "text-amber-600" : "")}>
            {item.score ?? "--"}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-sm md:grid-cols-4">
        <Metric label="5日" value={formatPct(item.change_5d)} />
        <Metric label="20日" value={formatPct(item.change_20d)} />
        <Metric label="距20日高点" value={formatPct(item.distance_to_high_20d)} />
        <Metric label="20日波动" value={formatPct(item.volatility_20d)} />
      </div>

      <div className="mt-4 grid gap-3 text-sm md:grid-cols-3">
        <InfoBlock label="公司业务" value={item.company_description || `${item.name || item.ticker}：${item.theme || "业务信息待补充"}。`} />
        <InfoBlock label="基本面" value={item.fundamental_summary || "基本面摘要暂不可用，需查看最新财报确认。"} />
        <InfoBlock label="当前逻辑" value={reasons.slice(0, 3).join("；") || "等待板块、成交量和价格确认。"} />
      </div>

      {news.length > 0 && (
        <div className="mt-3 rounded-md bg-muted/30 p-3">
          <div className="mb-2 text-xs text-muted-foreground">近期新闻/催化</div>
          <div className="space-y-2">
            {news.slice(0, 3).map((article, index) => {
              const content = (
                <>
                  <span className="font-medium">{article.title}</span>
                  {article.source && <span className="ml-2 text-muted-foreground">{article.source}</span>}
                  {article.summary && <div className="mt-1 line-clamp-2 text-muted-foreground">{article.summary}</div>}
                </>
              );
              return article.link ? (
                <a
                  key={`${article.title}-${index}`}
                  href={article.link}
                  target="_blank"
                  rel="noreferrer"
                  className="block text-sm leading-6 hover:underline"
                >
                  {content}
                </a>
              ) : (
                <div key={`${article.title}-${index}`} className="text-sm leading-6">
                  {content}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="mt-3 grid gap-3 text-sm md:grid-cols-3">
        <InfoBlock label="动作" value={item.action || "--"} />
        <InfoBlock label="买入计划" value={item.entry_plan || "--"} />
        <InfoBlock label="失效/止损" value={item.stop_loss || "--"} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {item.position_hint && <span className="rounded bg-muted px-2 py-1 text-muted-foreground">{item.position_hint}</span>}
        {reasons.slice(0, 4).map((reason, index) => (
          <span key={`${reason}-${index}`} className="rounded bg-green-500/10 px-2 py-1 text-green-700 dark:text-green-300">
            {reason}
          </span>
        ))}
        {risks.slice(0, 4).map((risk, index) => (
          <span key={`${risk}-${index}`} className="rounded bg-amber-500/10 px-2 py-1 text-amber-700 dark:text-amber-300">
            风险：{risk}
          </span>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/40 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 font-medium tabular-nums">{value}</div>
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/40 p-3">
      <div className="mb-1 text-xs text-muted-foreground">{label}</div>
      <div className="leading-6">{value}</div>
    </div>
  );
}

function ResultView({ result }: { result: StockPickerResult }) {
  const recommendations = result.recommendations || [];
  const watchOnly = result.watch_only || [];
  const avoid = result.avoid || [];
  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-[1fr_140px_140px]">
        <div className="rounded-lg border bg-muted/20 p-4">
          <div className="mb-1 text-xs text-muted-foreground">AI 综合结论</div>
          <p className="text-sm leading-6">{result.summary || "暂无结论。"}</p>
        </div>
        <div className="rounded-lg bg-muted/50 p-4">
          <div className="text-xs text-muted-foreground">重点候选</div>
          <div className="mt-1 text-2xl font-semibold">{recommendations.length}</div>
        </div>
        <div className="rounded-lg bg-muted/50 p-4">
          <div className="text-xs text-muted-foreground">生成时间</div>
          <div className="mt-2 text-sm">{formatTime(result.generated_at)}</div>
        </div>
      </div>

      {result.market_view && (
        <div className="grid gap-3 md:grid-cols-2">
          {Object.entries(result.market_view).map(([market, view]) => (
            <div key={market} className="rounded-lg border p-4">
              <div className="mb-1 text-xs font-medium text-muted-foreground">{market}</div>
              <p className="text-sm leading-6">{view}</p>
            </div>
          ))}
        </div>
      )}

      <section className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Target className="h-4 w-4" />
          重点候选
        </div>
        {recommendations.length ? (
          recommendations.map((item) => <PickCard key={`${item.market}-${item.ticker}`} item={item} />)
        ) : (
          <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">本轮没有符合“低追高风险 + 确定性”条件的候选。</div>
        )}
      </section>

      {watchOnly.length > 0 && (
        <section className="space-y-3">
          <div className="text-sm font-medium">只观察</div>
          {watchOnly.slice(0, 6).map((item) => <PickCard key={`watch-${item.market}-${item.ticker}`} item={item} muted />)}
        </section>
      )}

      {avoid.length > 0 && (
        <section className="rounded-lg border p-4">
          <div className="mb-3 text-sm font-medium">回避追高/暂不碰</div>
          <div className="flex flex-wrap gap-2">
            {avoid.slice(0, 10).map((item) => (
              <Badge key={`avoid-${item.market}-${item.ticker}`} variant="secondary">
                {item.name || item.ticker} · {item.action}
              </Badge>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default function StockPickerPage() {
  const [markets, setMarkets] = useState(["CN", "US"]);
  const [limit, setLimit] = useState("15");
  const [notes, setNotes] = useState("偏谨慎，选有潜力、不追高、风险低、确定性大的标的");
  const [results, setResults] = useState<StockPickerResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const latest = results[results.length - 1];

  const load = useCallback(async () => {
    try {
      const res = await api.getStockPickerResults(20);
      setResults(res.result || []);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加载选股记录失败");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleMarket = (market: string) => {
    setMarkets((current) => {
      if (current.includes(market)) {
        const next = current.filter((item) => item !== market);
        return next.length ? next : current;
      }
      return [...current, market];
    });
  };

  const run = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const res = await api.analyzeStockPicker({
        markets,
        limit: Number(limit) || 8,
        notes,
      });
      setResults((current) => [...current, res.result]);
      setMessage("选股完成");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "选股失败");
    } finally {
      setLoading(false);
    }
  };

  const clear = async () => {
    setClearing(true);
    setMessage(null);
    try {
      const res = await api.clearStockPickerResults();
      setResults([]);
      setMessage(`已清空 ${res.result.removed} 条选股记录`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "清空失败");
    } finally {
      setClearing(false);
    }
  };

  const history = useMemo(() => [...results].reverse().slice(1, 8), [results]);

  return (
    <>
      <Header />
      <main className="flex-1 space-y-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">AI选股</h1>
            <p className="text-muted-foreground">整合板块/主题、盯盘事件、行情走势，优先筛选不追高、风险低、确定性更高的潜力标的。</p>
          </div>
          <Button onClick={run} disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            运行选股
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>策略配置</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 lg:grid-cols-[220px_180px_1fr_auto]">
              <div>
                <div className="mb-2 text-sm text-muted-foreground">市场</div>
                <div className="flex gap-2">
                  {MARKETS.map((item) => (
                    <Button
                      key={item.key}
                      type="button"
                      variant={markets.includes(item.key) ? "default" : "outline"}
                      onClick={() => toggleMarket(item.key)}
                    >
                      {item.label}
                    </Button>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 text-sm text-muted-foreground">候选数量</div>
                <Input value={limit} onChange={(event) => setLimit(event.target.value)} type="number" min={3} max={20} />
              </div>
              <div>
                <div className="mb-2 text-sm text-muted-foreground">偏好备注</div>
                <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} className="min-h-20" />
              </div>
              <div className="flex items-end gap-2">
                <Button variant="outline" onClick={load}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  刷新
                </Button>
                <Button variant="outline" onClick={clear} disabled={clearing || results.length === 0}>
                  {clearing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
                  清空
                </Button>
              </div>
            </div>
            {message && <div className="mt-3 rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">{message}</div>}
          </CardContent>
        </Card>

        {latest ? (
          <ResultView result={latest} />
        ) : (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              暂无选股结果。运行一次后会在这里展示候选、买入计划、止损和风险。
            </CardContent>
          </Card>
        )}

        {history.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>历史记录</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {history.map((item, index) => (
                <div key={`${item.generated_at}-${index}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
                  <div>
                    <div className="text-sm font-medium">{formatTime(item.generated_at)}</div>
                    <div className="text-sm text-muted-foreground">{item.summary || "暂无摘要"}</div>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    候选 {item.recommendations?.length || 0}
                    <ExternalLink className="h-3 w-3" />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </main>
    </>
  );
}

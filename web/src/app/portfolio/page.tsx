"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ChevronDown, Loader2, Plus, RefreshCw, Save, Search, Trash2 } from "lucide-react";
import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useDebounce } from "@/hooks/use-debounce";
import { api, type PortfolioAnalysisItem, type PortfolioAnalysisResult, type PortfolioPosition, type SearchResult } from "@/lib/api";

function formatNumber(value?: number | null, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function formatPct(value?: number | null) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(2)}%`;
}

function marketFor(ticker: string) {
  const value = ticker.trim().toLowerCase();
  if (value.startsWith("hk") || value.endsWith(".hk") || (/^\d{5}$/.test(value) && value.startsWith("0"))) return "HK";
  if (value.startsWith("sh") || value.startsWith("sz") || /^\d{6}$/.test(value)) return "CN";
  return "US";
}

function emptyPosition(): PortfolioPosition {
  return { ticker: "", name: "", market: "", quantity: 0, avg_cost: 0, notes: "" };
}

function cashPosition(): PortfolioPosition {
  return { ticker: "CASH", name: "现金", market: "CASH", quantity: 0, avg_cost: 1, notes: "" };
}

function PositionSearchInput({
  value,
  onInput,
  onSelect,
}: {
  value: string;
  onInput: (value: string) => void;
  onSelect: (result: SearchResult) => void;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [typingActive, setTypingActive] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [dropdownStyle, setDropdownStyle] = useState({ left: 0, top: 0, width: 320 });
  const debouncedQuery = useDebounce(value, 250);

  const syncDropdownPosition = useCallback(() => {
    const rect = wrapperRef.current?.getBoundingClientRect();
    if (!rect) return;
    setDropdownStyle({
      left: rect.left,
      top: rect.bottom + 6,
      width: Math.max(rect.width, 360),
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!typingActive || !debouncedQuery.trim()) return;
    api.search(debouncedQuery.trim(), "all", 8)
      .then((response) => {
        if (!cancelled) {
          setResults(response.results);
          syncDropdownPosition();
          setOpen(response.results.length > 0);
        }
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
  }, [debouncedQuery, syncDropdownPosition, typingActive]);

  useEffect(() => {
    if (!open) return;
    window.addEventListener("resize", syncDropdownPosition);
    window.addEventListener("scroll", syncDropdownPosition, true);
    return () => {
      window.removeEventListener("resize", syncDropdownPosition);
      window.removeEventListener("scroll", syncDropdownPosition, true);
    };
  }, [open, syncDropdownPosition]);

  return (
    <div ref={wrapperRef} className="relative min-w-72">
      <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        className="pl-8"
        value={value}
        placeholder="输入名称或代码"
        onBlur={() => window.setTimeout(() => {
          setOpen(false);
          setTypingActive(false);
        }, 150)}
        onChange={(event) => {
          const next = event.target.value;
          setTypingActive(true);
          if (!next.trim()) setResults([]);
          if (next.trim()) setLoading(true);
          syncDropdownPosition();
          setOpen(Boolean(next.trim()));
          onInput(next);
        }}
        onFocus={syncDropdownPosition}
      />
      {open && (
        <div
          className="fixed z-[1000] max-h-96 overflow-y-auto rounded-md border bg-popover p-1 shadow-xl"
          style={{ left: dropdownStyle.left, top: dropdownStyle.top, width: dropdownStyle.width }}
        >
          {loading && <div className="px-3 py-2 text-sm text-muted-foreground">搜索中...</div>}
          {!loading && results.map((result) => (
            <button
              key={result.code}
              type="button"
              className="flex w-full items-center justify-between gap-2 rounded px-3 py-2 text-left text-sm hover:bg-muted"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                setOpen(false);
                setTypingActive(false);
                onSelect(result);
              }}
            >
              <span className="min-w-0">
                <span className="block truncate font-medium">{result.name || result.code}</span>
                <span className="text-xs text-muted-foreground">{result.code}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="rounded-lg bg-muted/40 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`mt-1 font-medium tabular-nums ${className}`}>{value}</div>
    </div>
  );
}

function pnlClass(value?: number | null) {
  if ((value || 0) > 0) return "text-green-600";
  if ((value || 0) < 0) return "text-red-600";
  return "";
}

function PositionAnalysis({ item }: { item: PortfolioAnalysisItem }) {
  const news = item.recent_news || [];
  const itemPnlClass = pnlClass(item.pnl);
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex flex-wrap items-center gap-2">
              <Link href={`/stock/${encodeURIComponent(item.ticker)}`} className="hover:underline">
                {item.ticker}
              </Link>
              {item.name && <span className="text-sm font-normal text-muted-foreground">{item.name}</span>}
              {item.market && <Badge variant="outline">{item.market}</Badge>}
            </CardTitle>
            <CardDescription>{item.technical?.summary || "技术面数据不足"}</CardDescription>
          </div>
          <div className="text-right">
            <div className="text-xs text-muted-foreground">仓位权重</div>
            <div className="text-xl font-semibold">{formatPct(item.weight)}</div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-5">
          <Metric label="数量" value={formatNumber(item.quantity, 0)} />
          <Metric label="买入均价" value={formatNumber(item.avg_cost)} />
          <Metric label="当前价" value={formatNumber(item.current_price)} />
          <Metric label="市值" value={formatNumber(item.market_value)} />
          <Metric label="浮盈亏" value={`${formatNumber(item.pnl)} / ${formatPct(item.pnl_percent)}`} className={itemPnlClass} />
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          <Metric label="当日涨跌" value={formatPct(item.day_change_percent)} />
          <Metric label="5日涨跌" value={formatPct(item.technical?.change_5d)} />
          <Metric label="20日涨跌" value={formatPct(item.technical?.change_20d)} />
          <Metric label="RSI14" value={formatNumber(item.technical?.rsi14)} />
        </div>

        {news.length > 0 && (
          <div className="rounded-lg border p-3">
            <div className="mb-2 text-sm font-medium">相关新闻</div>
            <div className="space-y-2">
              {news.slice(0, 4).map((article, index) => (
                <a
                  key={`${article.title}-${index}`}
                  href={article.link || "#"}
                  target="_blank"
                  rel="noreferrer"
                  className="block text-sm leading-6 hover:underline"
                >
                  <span className="font-medium">{article.title || "--"}</span>
                  {article.source && <span className="ml-2 text-muted-foreground">{article.source}</span>}
                  {article.summary && <div className="line-clamp-2 text-muted-foreground">{article.summary}</div>}
                </a>
              ))}
            </div>
          </div>
        )}

        {item.errors && item.errors.length > 0 && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700">
            数据问题：{item.errors.join("；")}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function PortfolioPage() {
  const [positions, setPositions] = useState<PortfolioPosition[]>([]);
  const [analysis, setAnalysis] = useState<PortfolioAnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const totals = useMemo(() => analysis ? [
    { label: "总成本", value: formatNumber(analysis.total_cost) },
    { label: "当前市值", value: formatNumber(analysis.total_market_value) },
    { label: "浮动盈亏", value: `${formatNumber(analysis.total_pnl)} / ${formatPct(analysis.total_pnl_percent)}` },
  ] : [], [analysis]);

  const loadPositions = useCallback(async () => {
    const response = await api.getPortfolioPositions();
    setPositions(response.result.positions.length ? response.result.positions : [emptyPosition()]);
  }, []);

  useEffect(() => {
    void loadPositions().catch((error) => setMessage(error instanceof Error ? error.message : "加载持仓失败"));
  }, [loadPositions]);

  const updatePosition = (index: number, patch: Partial<PortfolioPosition>) => {
    setPositions((current) => current.map((item, itemIndex) => {
      if (itemIndex !== index) return item;
      const next = { ...item, ...patch };
      if (patch.ticker && !next.market) next.market = marketFor(patch.ticker);
      return next;
    }));
  };

  const savePositionsOnly = async () => {
    const clean = positions.filter((item) => item.ticker.trim());
    const response = await api.savePortfolioPositions(clean);
    const savedPositions = response.result.positions.length ? response.result.positions : [emptyPosition()];
    setPositions(savedPositions);
    return savedPositions;
  };

  const refreshPortfolioAnalysis = async () => {
    const response = await api.analyzePortfolio();
    setAnalysis(response.result);
    if (response.result.positions.length) {
      setPositions(response.result.positions);
    }
    return response.result;
  };

  const save = async () => {
    setBusy(true);
    try {
      await savePositionsOnly();
      await refreshPortfolioAnalysis();
      setMessage("持仓已保存，估值已更新");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const analyze = async () => {
    setBusy(true);
    try {
      await savePositionsOnly();
      await refreshPortfolioAnalysis();
      setMessage("分析完成");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "分析失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 space-y-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">投资组合</h1>
            <p className="text-muted-foreground">维护自选/持仓，结合新闻、价格和技术面生成仓位管理建议。</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setPositions((current) => [...current, emptyPosition()])} disabled={busy}>
              <Plus className="mr-2 h-4 w-4" /> 添加
            </Button>
            <Button variant="outline" onClick={() => setPositions((current) => [...current, cashPosition()])} disabled={busy}>
              <Plus className="mr-2 h-4 w-4" /> 现金
            </Button>
            <Button variant="outline" onClick={save} disabled={busy}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} 保存
            </Button>
            <Button onClick={analyze} disabled={busy}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />} 分析组合
            </Button>
          </div>
        </div>

        {message && <div className="rounded-lg border px-4 py-3 text-sm">{message}</div>}

        <Card className="overflow-visible">
          <CardHeader>
            <CardTitle>持仓清单</CardTitle>
            <CardDescription>输入名称或代码后选择候选项，系统会自动填入代码和名称；再填写数量与买入均价。</CardDescription>
          </CardHeader>
          <CardContent className="overflow-visible">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>代码/名称</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>数量</TableHead>
                  <TableHead>买入均价</TableHead>
                  <TableHead>现价</TableHead>
                  <TableHead>市值</TableHead>
                  <TableHead>浮盈亏</TableHead>
                  <TableHead>盈亏比例</TableHead>
                  <TableHead>备注</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {positions.map((position, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <PositionSearchInput
                        value={position.ticker}
                        onInput={(value) => updatePosition(index, { ticker: value, market: marketFor(value) })}
                        onSelect={(result) => updatePosition(index, { ticker: result.code, name: result.name, market: result.market })}
                      />
                    </TableCell>
                    <TableCell><Input value={position.name || ""} onChange={(event) => updatePosition(index, { name: event.target.value })} placeholder="自动填入，可修改" /></TableCell>
                    <TableCell><Input type="number" value={position.quantity} onChange={(event) => updatePosition(index, { quantity: Number(event.target.value) })} /></TableCell>
                    <TableCell><Input type="number" value={position.avg_cost} onChange={(event) => updatePosition(index, { avg_cost: Number(event.target.value) })} /></TableCell>
                    <TableCell className="tabular-nums">{formatNumber(position.current_price)}</TableCell>
                    <TableCell className="tabular-nums">{formatNumber(position.market_value)}</TableCell>
                    <TableCell className={`tabular-nums ${pnlClass(position.pnl)}`}>{formatNumber(position.pnl)}</TableCell>
                    <TableCell className={`tabular-nums ${pnlClass(position.pnl_percent)}`}>{formatPct(position.pnl_percent)}</TableCell>
                    <TableCell><Input value={position.notes || ""} onChange={(event) => updatePosition(index, { notes: event.target.value })} placeholder="策略/原因" /></TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" onClick={() => setPositions((current) => current.filter((_, itemIndex) => itemIndex !== index))}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {analysis && (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              {totals.map((item) => <Metric key={item.label} label={item.label} value={item.value} />)}
            </div>
            <Card>
              <CardHeader>
                <CardTitle>Agent 仓位管理观点</CardTitle>
                <CardDescription>基于持仓、新闻、价格和技术分析生成。</CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea className="min-h-48 text-sm leading-6" value={analysis.agent_view || analysis.summary} readOnly />
              </CardContent>
            </Card>
            <div className="space-y-4">
              {analysis.positions.map((item) => <PositionAnalysis key={item.ticker} item={item} />)}
            </div>
          </>
        )}

        <Card>
          <Collapsible defaultOpen={false}>
            <CardHeader>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="h-auto w-full justify-between px-0 text-left">
                  <div>
                    <CardTitle>远程 MCP 接入</CardTitle>
                    <CardDescription>默认收起，点击展开配置远程 MCP 接入。</CardDescription>
                  </div>
                  <ChevronDown className="h-4 w-4" />
                </Button>
              </CollapsibleTrigger>
            </CardHeader>
            <CollapsibleContent>
              <CardContent className="pt-0 text-sm text-muted-foreground">
                远程 MCP 接入界面已放在页面最下方。
              </CardContent>
            </CollapsibleContent>
          </Collapsible>
        </Card>
      </main>
    </div>
  );
}

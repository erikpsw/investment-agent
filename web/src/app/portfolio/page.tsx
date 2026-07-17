"use client";

import { useUser } from "@auth0/nextjs-auth0";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ChevronDown, Copy, KeyRound, Loader2, Plus, RefreshCw, Save, Search, Trash2 } from "lucide-react";
import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useDebounce } from "@/hooks/use-debounce";
import { api, type CreatedPersonalAccessToken, type PersonalAccessToken, type PortfolioAnalysisItem, type PortfolioAnalysisResult, type PortfolioPosition, type SearchResult } from "@/lib/api";

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

function currencyForMarket(market?: string) {
  return ({ CN: "CNY", HK: "HKD", US: "USD", CASH: "CNY" } as Record<string, string>)[market || ""] || "CNY";
}

function emptyPosition(): PortfolioPosition {
  return { ticker: "", name: "", market: "", currency: "CNY", quantity: 0, avg_cost: 0, notes: "" };
}

function cashPosition(): PortfolioPosition {
  return { ticker: "CASH", name: "现金", market: "CASH", currency: "CNY", quantity: 0, avg_cost: 1, notes: "" };
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
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [dropdownStyle, setDropdownStyle] = useState({ left: 0, top: 0, width: 320 });
  const debouncedQuery = useDebounce(query, 250);

  const syncDropdownPosition = useCallback(() => {
    const rect = wrapperRef.current?.getBoundingClientRect();
    if (!rect) return;
    const viewportPadding = 12;
    const width = Math.min(
      Math.max(rect.width, 300),
      window.innerWidth - viewportPadding * 2,
    );
    const left = Math.min(
      Math.max(rect.left, viewportPadding),
      window.innerWidth - width - viewportPadding,
    );
    setDropdownStyle({
      left,
      top: rect.bottom + 6,
      width,
    });
  }, []);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    let cancelled = false;
    if (!debouncedQuery.trim() || !open) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    api.search(debouncedQuery.trim(), "all", 8)
      .then((response) => {
        if (!cancelled) {
          setResults(response.results);
          syncDropdownPosition();
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
  }, [debouncedQuery, open, syncDropdownPosition]);

  useEffect(() => {
    if (!open) return;
    syncDropdownPosition();
    window.addEventListener("resize", syncDropdownPosition);
    window.addEventListener("scroll", syncDropdownPosition, true);
    return () => {
      window.removeEventListener("resize", syncDropdownPosition);
      window.removeEventListener("scroll", syncDropdownPosition, true);
    };
  }, [open, syncDropdownPosition]);

  return (
    <div ref={wrapperRef} className="relative w-full min-w-0">
      <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        className="pl-8"
        value={query}
        placeholder="输入名称或代码"
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onChange={(event) => {
          const next = event.target.value;
          setQuery(next);
          syncDropdownPosition();
          setOpen(Boolean(next.trim()));
          onInput(next);
        }}
      />
      {open && (loading || results.length > 0) && (
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
                setQuery(result.code);
                setOpen(false);
                onSelect(result);
              }}
            >
              <span className="min-w-0">
                <span className="block truncate font-medium">{result.name || result.code}</span>
                <span className="text-xs text-muted-foreground">{result.code}</span>
              </span>
              {result.instrument_type === "etf" && <Badge variant="secondary">ETF</Badge>}
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

function MobilePositionCard({
  position,
  index,
  onUpdate,
  onRemove,
}: {
  position: PortfolioPosition;
  index: number;
  onUpdate: (index: number, patch: Partial<PortfolioPosition>) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <Card data-testid="mobile-position-card">
      <CardContent className="space-y-4 pt-6">
        <PositionSearchInput
          value={position.ticker}
          onInput={(value) => {
            const market = marketFor(value);
            onUpdate(index, {
              ticker: value,
              market,
              currency: currencyForMarket(market),
            });
          }}
          onSelect={(result) => onUpdate(index, {
            ticker: result.code,
            name: result.name,
            market: result.market,
            currency: currencyForMarket(result.market),
          })}
        />

        <Input
          value={position.name || ""}
          onChange={(event) => onUpdate(index, { name: event.target.value })}
          placeholder="名称（选择标的后自动填入）"
        />

        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1 text-xs text-muted-foreground">
            数量
            <Input
              type="number"
              inputMode="decimal"
              value={position.quantity}
              onChange={(event) => onUpdate(index, { quantity: Number(event.target.value) })}
            />
          </label>
          <label className="space-y-1 text-xs text-muted-foreground">
            买入均价
            <Input
              type="number"
              inputMode="decimal"
              value={position.avg_cost}
              onChange={(event) => onUpdate(index, { avg_cost: Number(event.target.value) })}
            />
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Metric label={`现价 (${position.currency || "CNY"})`} value={formatNumber(position.current_price)} />
          <Metric label="市值 (人民币)" value={`¥${formatNumber(position.market_value)}`} />
          <Metric label="浮盈亏 (人民币)" value={`¥${formatNumber(position.pnl)}`} className={pnlClass(position.pnl)} />
          <Metric label="盈亏比例" value={formatPct(position.pnl_percent)} className={pnlClass(position.pnl_percent)} />
        </div>

        <Input
          value={position.notes || ""}
          onChange={(event) => onUpdate(index, { notes: event.target.value })}
          placeholder="策略/原因"
        />
        <Button variant="outline" className="w-full" onClick={() => onRemove(index)}>
          <Trash2 className="mr-2 h-4 w-4" />删除持仓
        </Button>
      </CardContent>
    </Card>
  );
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
          <Metric label={`买入均价 (${item.currency || "CNY"})`} value={formatNumber(item.avg_cost)} />
          <Metric label={`当前价 (${item.currency || "CNY"})`} value={formatNumber(item.current_price)} />
          <Metric label="市值 (人民币)" value={`¥${formatNumber(item.market_value)}`} />
          <Metric label="浮盈亏 (人民币)" value={`¥${formatNumber(item.pnl)} / ${formatPct(item.pnl_percent)}`} className={itemPnlClass} />
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
  const { user, isLoading: authLoading } = useUser();
  const [positions, setPositions] = useState<PortfolioPosition[]>([]);
  const [analysis, setAnalysis] = useState<PortfolioAnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [personalTokens, setPersonalTokens] = useState<PersonalAccessToken[]>([]);
  const [newTokenName, setNewTokenName] = useState("Codex MCP");
  const [createdToken, setCreatedToken] = useState<CreatedPersonalAccessToken | null>(null);
  const [tokenLoading, setTokenLoading] = useState(false);
  const [mcpOpen, setMcpOpen] = useState(false);
  const activePersonalTokens = useMemo(
    () => personalTokens.filter((token) => !token.revoked_at),
    [personalTokens],
  );

  const totals = useMemo(() => analysis ? [
    { label: "总成本 (人民币)", value: `¥${formatNumber(analysis.total_cost)}` },
    { label: "当前市值 (人民币)", value: `¥${formatNumber(analysis.total_market_value)}` },
    { label: "浮动盈亏 (人民币)", value: `¥${formatNumber(analysis.total_pnl)} / ${formatPct(analysis.total_pnl_percent)}` },
  ] : [], [analysis]);

  const loadPositions = useCallback(async () => {
    const response = await api.getPortfolioPositions();
    setPositions(response.result.positions.length ? response.result.positions : [emptyPosition()]);
  }, []);

  const loadPersonalTokens = useCallback(async () => {
    const response = await api.listPersonalAccessTokens();
    setPersonalTokens(response.result.tokens);
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    void Promise.all([loadPositions(), loadPersonalTokens()]).catch((error) =>
      setMessage(error instanceof Error ? error.message : "加载投资组合失败")
    );
  }, [authLoading, loadPersonalTokens, loadPositions, user]);

  const updatePosition = (index: number, patch: Partial<PortfolioPosition>) => {
    setPositions((current) => current.map((item, itemIndex) => {
      if (itemIndex !== index) return item;
      const next = { ...item, ...patch };
      if (patch.ticker && !next.market) next.market = marketFor(patch.ticker);
      if (patch.market) next.currency = currencyForMarket(patch.market);
      return next;
    }));
  };

  const createMcpToken = async () => {
    if (!newTokenName.trim()) return;
    setTokenLoading(true);
    try {
      const response = await api.createPersonalAccessToken(newTokenName.trim());
      setCreatedToken(response.result);
      await loadPersonalTokens();
      setMessage("Personal Access Token 已创建，请立即复制并妥善保存");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建 Token 失败");
    } finally {
      setTokenLoading(false);
    }
  };

  const copyMcpToken = async () => {
    if (!createdToken) return;
    await navigator.clipboard.writeText(createdToken.token);
    setMessage("Token 已复制");
  };

  const revokeMcpToken = async (id: string) => {
    setTokenLoading(true);
    try {
      await api.revokePersonalAccessToken(id);
      if (createdToken?.id === id) setCreatedToken(null);
      await loadPersonalTokens();
      setMessage("Token 已撤销");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "撤销 Token 失败");
    } finally {
      setTokenLoading(false);
    }
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

  if (authLoading) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex flex-1 items-center justify-center p-6">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </main>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex flex-1 items-center justify-center p-6">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>登录后管理投资组合</CardTitle>
              <CardDescription>持仓将按账户保存到云端，并在不同设备间同步。</CardDescription>
            </CardHeader>
            <CardContent>
              <Button className="w-full" render={<Link href="/auth/login?returnTo=/portfolio" prefetch={false} />}>登录 / 注册</Button>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

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
            <div className="space-y-4 md:hidden">
              {positions.map((position, index) => (
                <MobilePositionCard
                  key={index}
                  position={position}
                  index={index}
                  onUpdate={updatePosition}
                  onRemove={(itemIndex) => setPositions((current) => current.filter((_, currentIndex) => currentIndex !== itemIndex))}
                />
              ))}
            </div>

            <div className="hidden overflow-x-auto md:block">
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
                        onInput={(value) => { const market = marketFor(value); updatePosition(index, { ticker: value, market, currency: currencyForMarket(market) }); }}
                        onSelect={(result) => updatePosition(index, { ticker: result.code, name: result.name, market: result.market, currency: currencyForMarket(result.market) })}
                      />
                    </TableCell>
                    <TableCell><Input value={position.name || ""} onChange={(event) => updatePosition(index, { name: event.target.value })} placeholder="自动填入，可修改" /></TableCell>
                    <TableCell><Input type="number" value={position.quantity} onChange={(event) => updatePosition(index, { quantity: Number(event.target.value) })} /></TableCell>
                    <TableCell><Input type="number" value={position.avg_cost} onChange={(event) => updatePosition(index, { avg_cost: Number(event.target.value) })} /></TableCell>
                    <TableCell className="tabular-nums">{formatNumber(position.current_price)} {position.currency}</TableCell>
                    <TableCell className="tabular-nums">¥{formatNumber(position.market_value)}</TableCell>
                    <TableCell className={`tabular-nums ${pnlClass(position.pnl)}`}>¥{formatNumber(position.pnl)}</TableCell>
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
            </div>
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
          <Collapsible open={mcpOpen} onOpenChange={setMcpOpen}>
            <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
              <div>
                <CardTitle className="flex items-center gap-2"><KeyRound className="h-5 w-5" />远程 MCP 接入</CardTitle>
                <CardDescription>创建可随时撤销的 90 天 Personal Access Token。Token 仅能读取和分析你的投资组合。</CardDescription>
              </div>
              <CollapsibleTrigger asChild>
                <Button type="button" variant="ghost" size="sm">
                  {mcpOpen ? "收起" : "展开"}
                  <ChevronDown className={`ml-1 h-4 w-4 transition-transform ${mcpOpen ? "rotate-180" : ""}`} />
                </Button>
              </CollapsibleTrigger>
            </CardHeader>
            <CollapsibleContent>
              <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-[180px_1fr]">
                  <div className="text-sm text-muted-foreground">Streamable HTTP 地址</div>
                  <code className="break-all rounded bg-muted px-3 py-2 text-sm">https://invest.erikai.top/mcp</code>
                  <div className="text-sm text-muted-foreground">创建 Token</div>
                  <div className="space-y-2">
                    <div className="flex flex-wrap gap-2">
                      <Input
                        value={newTokenName}
                        onChange={(event) => setNewTokenName(event.target.value)}
                        maxLength={80}
                        placeholder="例如：Codex MCP"
                        className="max-w-sm"
                      />
                      <Button variant="outline" onClick={createMcpToken} disabled={tokenLoading || !newTokenName.trim()}>
                        {tokenLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}创建 90 天 Token
                      </Button>
                    </div>
                  </div>
                </div>
                {createdToken && (
                  <div className="space-y-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4">
                    <div className="font-medium">完整 Token 仅显示这一次</div>
                    <Textarea value={createdToken.token} readOnly className="min-h-24 font-mono text-xs" />
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" onClick={copyMcpToken}>
                        <Copy className="mr-2 h-4 w-4" />复制 Token
                      </Button>
                      <Button variant="ghost" onClick={() => setCreatedToken(null)}>我已保存，关闭</Button>
                    </div>
                  </div>
                )}
                <div className="space-y-2">
                  <div className="text-sm font-medium">已创建的 Token</div>
                  {activePersonalTokens.length === 0 ? (
                    <div className="rounded-lg border p-3 text-sm text-muted-foreground">还没有有效的 Personal Access Token</div>
                  ) : activePersonalTokens.map((token) => {
                    const expired = new Date(token.expires_at).getTime() <= Date.now();
                    const state = expired ? "已过期" : "有效";
                    return (
                      <div key={token.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 text-sm">
                        <div>
                          <div className="flex items-center gap-2 font-medium">
                            {token.name}
                            <Badge variant={state === "有效" ? "secondary" : "outline"}>{state}</Badge>
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {token.token_prefix}... · 到期 {new Date(token.expires_at).toLocaleString("zh-CN")}
                            {token.last_used_at ? ` · 最近使用 ${new Date(token.last_used_at).toLocaleString("zh-CN")}` : " · 尚未使用"}
                          </div>
                        </div>
                        {!expired && (
                          <Button variant="outline" size="sm" onClick={() => revokeMcpToken(token.id)} disabled={tokenLoading}>
                            <Trash2 className="mr-2 h-4 w-4" />撤销
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="rounded-lg border bg-muted/40 p-4 text-sm leading-6">
                  <div className="font-medium">Codex 配置</div>
                  <code className="mt-2 block break-all">设置环境变量 ERIK_AI_ACCESS_TOKEN 为上面的 Token</code>
                  <code className="block break-all">codex mcp add erik_ai --url https://invest.erikai.top/mcp --bearer-token-env-var ERIK_AI_ACCESS_TOKEN</code>
                  <div className="mt-2 text-muted-foreground">Token 90 天后自动过期，也可以在此立即撤销。请勿把 Token 提交到 Git 或发送给他人。</div>
                </div>
              </CardContent>
            </CollapsibleContent>
          </Collapsible>
        </Card>
      </main>
    </div>
  );
}

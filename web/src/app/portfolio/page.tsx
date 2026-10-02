"use client";

import { useUser } from "@auth0/nextjs-auth0";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Loader2, Plus, RefreshCw, Save, Search, Trash2 } from "lucide-react";
import { Header } from "@/components/header";
import { McpAccessPanel } from "@/components/mcp-access-panel";
import { SecurityResearchDetails } from "@/components/security-research-details";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useDebounce } from "@/hooks/use-debounce";
import { securityMarket } from "@/lib/financial-reports";
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
  return securityMarket(ticker);
}

function currencyForMarket(market?: string) {
  return ({ CN: "CNY", HK: "HKD", US: "USD", CASH: "CNY" } as Record<string, string>)[market || ""] || "CNY";
}

function emptyPosition(): PortfolioPosition {
  return { ticker: "", name: "", market: "", currency: "CNY", quantity: 0, avg_cost: 0, notes: "" };
}

const CASH_OPTIONS = [
  { currency: "CNY", ticker: "CASH_CNY", name: "人民币现金" },
  { currency: "HKD", ticker: "CASH_HKD", name: "港币现金" },
  { currency: "USD", ticker: "CASH_USD", name: "美元现金" },
] as const;

function isCashPosition(position: PortfolioPosition) {
  return position.market === "CASH" || position.ticker.toUpperCase().startsWith("CASH_");
}

function cashPosition(currency: "CNY" | "HKD" | "USD"): PortfolioPosition {
  const option = CASH_OPTIONS.find((item) => item.currency === currency) || CASH_OPTIONS[0];
  return { ticker: option.ticker, name: option.name, market: "CASH", currency, quantity: 0, avg_cost: 1, notes: "" };
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
  const isCash = isCashPosition(position);
  return (
    <Card data-testid="mobile-position-card">
      <CardContent className="space-y-4 pt-6">
        {isCash ? (
          <div><div className="font-semibold">{position.name}</div><div className="text-sm text-muted-foreground">{position.ticker} · {position.currency}</div></div>
        ) : <PositionSearchInput
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
        />}

        {!isCash && <Input
          value={position.name || ""}
          onChange={(event) => onUpdate(index, { name: event.target.value })}
          placeholder="名称（选择标的后自动填入）"
        />}

        <div className={`grid gap-3 ${isCash ? "grid-cols-1" : "grid-cols-2"}`}>
          <label className="space-y-1 text-xs text-muted-foreground">
            {isCash ? `现金余额 (${position.currency})` : "数量"}
            <Input
              type="number"
              inputMode="decimal"
              value={position.quantity}
              onChange={(event) => onUpdate(index, { quantity: Number(event.target.value) })}
            />
          </label>
          {!isCash && <label className="space-y-1 text-xs text-muted-foreground">
            买入均价
            <Input
              type="number"
              inputMode="decimal"
              value={position.avg_cost}
              onChange={(event) => onUpdate(index, { avg_cost: Number(event.target.value) })}
            />
          </label>}
        </div>

        {isCash ? <div className="grid grid-cols-2 gap-3">
          <Metric label={`余额 (${position.currency})`} value={formatNumber(position.market_value_native ?? position.quantity)} />
          <Metric label="兑人民币汇率" value={formatNumber(position.fx_rate_to_cny, 4)} />
          <Metric label="人民币市值" value={`¥${formatNumber(position.market_value)}`} />
          <Metric label="组合占比" value={formatPct(position.weight)} />
        </div> : <div className="grid grid-cols-2 gap-3">
          <Metric label={`现价 (${position.currency || "CNY"})`} value={formatNumber(position.current_price)} />
          <Metric label="市值 (人民币)" value={`¥${formatNumber(position.market_value)}`} />
          <Metric label="浮盈亏 (人民币)" value={`¥${formatNumber(position.pnl)}`} className={pnlClass(position.pnl)} />
          <Metric label="盈亏比例" value={formatPct(position.pnl_percent)} className={pnlClass(position.pnl_percent)} />
        </div>}

        {!isCash && position.ticker && <Link href={`/stock/${encodeURIComponent(position.ticker)}`} className="flex min-h-11 items-center justify-center rounded-md border text-sm font-medium">查看走势、财报与新闻</Link>}
        {!isCash && position.research && <SecurityResearchDetails research={position.research} ticker={position.ticker} />}

        <Input
          value={position.notes || ""}
          onChange={(event) => onUpdate(index, { notes: event.target.value })}
          placeholder="策略/原因"
        />
        <Button variant="outline" className="min-h-11 w-full" onClick={() => onRemove(index)}>
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
  const [loadingPositions, setLoadingPositions] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [loadMs, setLoadMs] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [personalTokens, setPersonalTokens] = useState<PersonalAccessToken[]>([]);
  const [newTokenName, setNewTokenName] = useState("Codex MCP");
  const [createdToken, setCreatedToken] = useState<CreatedPersonalAccessToken | null>(null);
  const [tokenLoading, setTokenLoading] = useState(false);
  const activePersonalTokens = useMemo(
    () => personalTokens.filter((token) => !token.revoked_at),
    [personalTokens],
  );
  const cashCurrenciesInUse = useMemo(
    () => new Set(positions.filter(isCashPosition).map((position) => position.currency || "CNY")),
    [positions],
  );

  const totals = useMemo(() => analysis ? [
    { label: "总成本 (人民币)", value: `¥${formatNumber(analysis.total_cost)}` },
    { label: "当前市值 (人民币)", value: `¥${formatNumber(analysis.total_market_value)}` },
    { label: "浮动盈亏 (人民币)", value: `¥${formatNumber(analysis.total_pnl)} / ${formatPct(analysis.total_pnl_percent)}` },
  ] : [], [analysis]);

  const loadPositions = useCallback(async () => {
    setLoadingPositions(true);
    setLoadError("");
    const started = performance.now();
    try {
      const response = await api.getPortfolioPositions(false, false);
      setPositions(response.result.positions);
      setDirty(false);
      setLoadMs(performance.now() - started);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "加载投资组合失败");
    } finally {
      setLoadingPositions(false);
    }
  }, []);

  const loadPersonalTokens = useCallback(async () => {
    const response = await api.listPersonalAccessTokens();
    setPersonalTokens(response.result.tokens);
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    void loadPositions();
    void loadPersonalTokens().catch(() => setMessage("MCP 接入设置暂时无法加载，可在设置页重试。"));
  }, [authLoading, loadPersonalTokens, loadPositions, user]);

  const updatePosition = (index: number, patch: Partial<PortfolioPosition>) => {
    setDirty(true);
    setAnalysis(null);
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
    setDirty(false);
    setAnalysis(null);
    return savedPositions;
  };

  const refreshPortfolioAnalysis = async () => {
    const response = await api.analyzePortfolio();
    setAnalysis(response.result);
    return response.result;
  };

  const save = async () => {
    setBusy(true);
    try {
      await savePositionsOnly();
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
      await loadPositions();
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
      <main className="min-w-0 flex-1 space-y-4 p-3 sm:space-y-6 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">投资组合</h1>
            <p className="text-muted-foreground">维护自选/持仓，结合新闻、价格和技术面生成仓位管理建议。</p>
          </div>
          <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:flex-wrap [&>button]:min-h-11">
            <Button variant="outline" onClick={() => { setPositions((current) => [...current, emptyPosition()]); setDirty(true); setAnalysis(null); }} disabled={busy || loadingPositions || !!loadError}>
              <Plus className="mr-2 h-4 w-4" /> 添加
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger disabled={busy || loadingPositions || !!loadError} className="inline-flex min-h-11 items-center justify-center rounded-md border px-3 text-sm font-medium hover:bg-muted">
                <Plus className="mr-2 h-4 w-4" />现金
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                {CASH_OPTIONS.map((option) => (
                  <DropdownMenuItem
                    key={option.currency}
                    disabled={busy || cashCurrenciesInUse.has(option.currency)}
                    onClick={() => { setPositions((current) => [...current, cashPosition(option.currency)]); setDirty(true); setAnalysis(null); }}
                  >
                    {option.name}{cashCurrenciesInUse.has(option.currency) ? "（已添加）" : ""}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="outline" onClick={save} disabled={busy || loadingPositions || !!loadError || !dirty}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} 保存
            </Button>
            <Button onClick={analyze} disabled={busy || loadingPositions || !!loadError || !positions.some(item => item.ticker.trim())}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />} 分析组合
            </Button>
          </div>
        </div>

        {message && <div className="rounded-lg border px-4 py-3 text-sm">{message}</div>}
        <div role="status" className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
          <span>{loadingPositions ? "正在加载持仓估值…" : loadError ? "持仓加载失败" : dirty ? "有未保存的修改 · 估值将在保存后更新" : loadMs !== null ? `估值已更新 · ${(loadMs / 1000).toFixed(2)} 秒` : ""}</span>
          <Button className="min-h-11" variant="outline" onClick={() => { setAnalysis(null); void loadPositions(); }} disabled={busy || loadingPositions || dirty}><RefreshCw className="mr-2 h-4 w-4" />刷新估值</Button>
        </div>
        {loadError && <div role="alert" className="rounded-lg border p-3 text-sm">{loadError}，请点击刷新估值重试。</div>}

        <Card className="overflow-visible">
          <CardHeader>
            <CardTitle>持仓清单</CardTitle>
            <CardDescription>输入名称或代码后选择候选项，系统会自动填入代码和名称；再填写数量与买入均价。</CardDescription>
          </CardHeader>
          <CardContent className="overflow-visible">
            <fieldset disabled={busy || loadingPositions || !!loadError} className="min-w-0">
            {!loadingPositions && !loadError && positions.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">暂无持仓，点击添加股票或现金开始记录。</p>}
            <div className="space-y-4 md:hidden">
              {positions.map((position, index) => (
                <MobilePositionCard
                  key={index}
                  position={position}
                  index={index}
                  onUpdate={updatePosition}
                  onRemove={(itemIndex) => { setPositions((current) => current.filter((_, currentIndex) => currentIndex !== itemIndex)); setDirty(true); setAnalysis(null); }}
                />
              ))}
            </div>

            <div className="hidden overflow-x-auto md:block">
              <Table className="min-w-[1120px] table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-52">代码/名称</TableHead>
                  <TableHead className="w-40">名称</TableHead>
                  <TableHead className="w-28">数量</TableHead>
                  <TableHead className="w-32">买入均价</TableHead>
                  <TableHead className="w-32">现价</TableHead>
                  <TableHead className="w-32">市值</TableHead>
                  <TableHead className="w-32">浮盈亏</TableHead>
                  <TableHead className="w-28">盈亏比例</TableHead>
                  <TableHead className="w-48">备注</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {positions.map((position, index) => {
                  const cash = isCashPosition(position);
                  return (
                  <Fragment key={`${position.ticker}-${index}`}>
                  <TableRow>
                    <TableCell>
                      {cash ? (
                        <div><div className="font-medium">{position.name}</div><div className="text-xs text-muted-foreground">{position.ticker}</div></div>
                      ) : <PositionSearchInput
                        value={position.ticker}
                        onInput={(value) => { const market = marketFor(value); updatePosition(index, { ticker: value, market, currency: currencyForMarket(market) }); }}
                        onSelect={(result) => updatePosition(index, { ticker: result.code, name: result.name, market: result.market, currency: currencyForMarket(result.market) })}
                      />}
                      {!cash && position.ticker && <Link href={`/stock/${encodeURIComponent(position.ticker)}`} className="mt-1 flex min-h-11 items-center text-sm text-primary hover:underline">走势 / 财报 / 新闻</Link>}
                    </TableCell>
                    <TableCell>{cash ? position.currency : <Input value={position.name || ""} onChange={(event) => updatePosition(index, { name: event.target.value })} placeholder="自动填入，可修改" />}</TableCell>
                    <TableCell><Input type="number" value={position.quantity} onChange={(event) => updatePosition(index, { quantity: Number(event.target.value) })} /></TableCell>
                    <TableCell>{cash ? "--" : <Input type="number" value={position.avg_cost} onChange={(event) => updatePosition(index, { avg_cost: Number(event.target.value) })} />}</TableCell>
                    <TableCell className="tabular-nums">{cash ? `汇率 ${formatNumber(position.fx_rate_to_cny, 4)}` : `${formatNumber(position.current_price)} ${position.currency}`}</TableCell>
                    <TableCell className="tabular-nums">¥{formatNumber(position.market_value)}</TableCell>
                    <TableCell className={`tabular-nums ${pnlClass(position.pnl)}`}>{cash ? "--" : `¥${formatNumber(position.pnl)}`}</TableCell>
                    <TableCell className={`tabular-nums ${pnlClass(position.pnl_percent)}`}>{cash ? "--" : formatPct(position.pnl_percent)}</TableCell>
                    <TableCell><Input value={position.notes || ""} onChange={(event) => updatePosition(index, { notes: event.target.value })} placeholder="策略/原因" /></TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" aria-label={`删除 ${position.ticker || "空持仓"}`} onClick={() => { setPositions((current) => current.filter((_, itemIndex) => itemIndex !== index)); setDirty(true); setAnalysis(null); }}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                  {!cash && (
                    <TableRow data-testid="portfolio-research-row" className="border-b bg-muted/10">
                      <TableCell colSpan={10} className="max-w-0 p-3">
                        <div className="min-w-0 max-w-full overflow-hidden">
                          <SecurityResearchDetails research={position.research} />
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                  </Fragment>
                  );
                })}
              </TableBody>
              </Table>
            </div>
            </fieldset>
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

        <McpAccessPanel
          tokens={activePersonalTokens}
          createdToken={createdToken}
          newTokenName={newTokenName}
          tokenLoading={tokenLoading}
          onNewTokenNameChange={setNewTokenName}
          onCreateToken={createMcpToken}
          onCopyToken={copyMcpToken}
          onCloseCreatedToken={() => setCreatedToken(null)}
          onRevokeToken={revokeMcpToken}
        />
      </main>
    </div>
  );
}

"use client";

import { useFinancials } from "@/hooks/use-market";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { securityMarket, safeReportUrl, yahooQuoteUrl } from "@/lib/financial-reports";
import { FinancialReportList } from "@/components/financial-report-list";
import { Button } from "@/components/ui/button";

async function timed<T extends object>(request: () => Promise<T>): Promise<T & { elapsedMs: number }> {
  const started = performance.now();
  const result = await request();
  return { ...result, elapsedMs: performance.now() - started };
}

export function SecurityFundamentals({ ticker, market, name = "" }: { ticker: string; market?: string | null; name?: string }) {
  const resolvedMarket = securityMarket(ticker, market);
  const isFund = /ETF|基金/i.test(name) || (resolvedMarket === "CN" && /^(sh)?5\d{5}$|^(sz)?1[568]\d{4}$/i.test(ticker));
  const metrics = useFinancials(ticker, !isFund);
  const financial = useQuery({ queryKey: ["financial-history", ticker], queryFn: () => timed(() => api.getFinancialHistory(ticker)), enabled: !isFund, refetchInterval: 300000, staleTime: 300000, retry: false });
  const news = useQuery({ queryKey: ["security-news", ticker, resolvedMarket, name], queryFn: () => timed(() => api.getSecurityNews(ticker, resolvedMarket, name)),  staleTime: 60000, refetchInterval: 60000, retry: false });
  const amount = (value: number | null) => value == null ? "—" : new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2, notation: "compact" }).format(value);
  return <section className="mt-4 min-w-0 space-y-4" aria-label="财报与新闻">
    <a className="inline-flex min-h-11 items-center text-sm text-primary underline" href={yahooQuoteUrl(ticker, resolvedMarket)} target="_blank" rel="noreferrer">在 Yahoo Finance 核对行情与估值 ↗</a>
    <div className="grid min-w-0 items-start gap-4 lg:grid-cols-2">
      <div className="rounded-lg border p-3 space-y-3">
        <h3 className="font-medium">财务与估值</h3>
        {!isFund && <div className="rounded border p-3"><dl className="grid grid-cols-2 gap-3 text-sm"><div><dt className="text-muted-foreground">PE {metrics.data?.pe_basis || ""}</dt><dd>{metrics.data?.pe_ratio == null ? "—" : metrics.data.pe_ratio.toFixed(2)}</dd></div><div><dt className="text-muted-foreground">每股收益 EPS</dt><dd>{metrics.data?.eps == null ? "—" : metrics.data.eps.toFixed(2)}</dd></div></dl><p className="mt-2 text-xs text-muted-foreground">估值来源：{metrics.data?.pe_source || "未提供"}{metrics.isLoading ? " · 正在更新…" : metrics.isError ? " · 暂时无法获取" : ""}</p></div>}
        <div aria-label="财务历史" data-testid="financial-history-section" className="min-w-0 space-y-3">
        <h4 className="font-medium">财务历史</h4>
        <p className="text-xs text-muted-foreground">报告期与数据源返回的原始金额口径；不同市场币种不可直接比较。{financial.data?.updated_at && ` 数据更新：${financial.data.updated_at}`}</p>
        {isFund && <p className="text-sm text-muted-foreground">ETF / 基金不适用上市公司的营收、利润指标；可查看基金披露原文。</p>}
        {isFund ? null : financial.isLoading ? <p role="status">正在获取财务数据…</p> : financial.isError ? <div role="alert">财务数据加载失败。<Button variant="outline" onClick={() => financial.refetch()}>重试</Button></div> : !financial.data?.data?.length ? <p>数据源暂未提供财务历史。</p> : <div className="space-y-3">{financial.data.data.slice().sort((a, b) => b.period.localeCompare(a.period)).slice(0, 2).map(row => <div key={row.period} className="rounded border p-3"><h4 className="font-medium mb-2">{row.period}</h4><dl className="grid grid-cols-2 gap-3 text-sm">{([["营业收入", row.revenue], ["净利润", row.net_profit], ["总资产", row.total_assets], ["经营现金流", row.operating_cash_flow]] as const).map(([label, value]) => <div key={label}><dt className="text-muted-foreground">{label}</dt><dd>{amount(value)}</dd></div>)}</dl></div>)}</div>}
        {financial.data && <p className="text-xs text-muted-foreground">本次加载 {(financial.data.elapsedMs / 1000).toFixed(2)} 秒</p>}
        <FinancialReportList ticker={ticker} market={resolvedMarket} />
        </div>
      </div>
      <div className="rounded-lg border p-3 space-y-3">
      <div className="flex justify-between items-center"><h3 className="font-medium">相关新闻</h3><Button className="h-11" variant="outline" disabled={news.isFetching} onClick={() => news.refetch()}>刷新新闻</Button></div>
      {news.isLoading ? <p role="status">正在获取新闻…</p> : news.isError ? <p role="alert">新闻加载失败，请点击刷新重试。</p> : !news.data?.news.length ? <p>暂无与该标的明确相关的新闻。</p> : news.data.news.slice(0, 5).map((item, index) => <article className="border-t pt-3" key={`${item.link}:${index}`}><a href={safeReportUrl(item.link) || undefined} target="_blank" rel="noreferrer" className="block py-2 font-medium underline-offset-4 hover:underline">{item.title}</a><p className="text-xs text-muted-foreground">{item.matched_entity && `关联：${item.matched_entity} · `}{item.source} · {item.published_date || item.published || "日期未提供"}</p>{item.summary && <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">{item.summary}</p>}</article>)}
      {news.dataUpdatedAt > 0 && <p className="text-xs text-muted-foreground">获取于 {new Date(news.dataUpdatedAt).toLocaleTimeString("zh-CN")} · 本次 {((news.data?.elapsedMs || 0) / 1000).toFixed(2)} 秒 · 每分钟更新</p>}
    </div>
    </div>
  </section>;
}

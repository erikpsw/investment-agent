"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { FormulaRankingResult, USUniverseFilters } from "@/lib/api";

const defaults = { minCap: "10", maxCap: "", minPrice: "5", maxPrice: "", minAmount: "1", exchange: "" };
const fields = [
  ["minCap", "最低市值（亿美元）"], ["maxCap", "最高市值（亿美元）"],
  ["minPrice", "最低股价（美元）"], ["maxPrice", "最高股价（美元）"],
  ["minAmount", "最低成交额（百万美元）"],
] as const;
const exchangeOptions = [
  { value: "", label: "全部交易所" },
  { value: "NASDAQ", label: "NASDAQ" },
  { value: "NYSE", label: "NYSE" },
  { value: "AMEX", label: "NYSE American" },
  { value: "NYSE_ARCA", label: "NYSE Arca" },
  { value: "CBOE", label: "Cboe" },
  { value: "IEX", label: "IEX" },
] as const;
const exchanges = Object.fromEntries(exchangeOptions.map(option => [option.value, option.label]));

export function USUniverseFilterPanel({ onApply, loading, data, filters }: {
  onApply: (filters: USUniverseFilters) => void; loading: boolean; data: FormulaRankingResult | null; filters: USUniverseFilters;
}) {
  const [draft, setDraft] = useState(() => ({
    minCap: filters.min_market_cap ? String(filters.min_market_cap/1e8) : "",
    maxCap: filters.max_market_cap ? String(filters.max_market_cap/1e8) : "",
    minPrice: filters.min_price ? String(filters.min_price) : "",
    maxPrice: filters.max_price ? String(filters.max_price) : "",
    minAmount: filters.min_amount ? String(filters.min_amount/1e6) : "", exchange: filters.exchange || "",
  }));
  const [error, setError] = useState("");
  function apply() {
    const minCap = Number(draft.minCap), minPrice = Number(draft.minPrice), minAmount = Number(draft.minAmount);
    const maxCap = draft.maxCap === "" ? undefined : Number(draft.maxCap);
    const maxPrice = draft.maxPrice === "" ? undefined : Number(draft.maxPrice);
    if ([minCap, minPrice, minAmount, maxCap, maxPrice].some(value => value !== undefined && (!Number.isFinite(value) || value < 0))) {
      setError("请输入有效的非负数值"); return;
    }
    if (maxCap !== undefined && minCap > maxCap) { setError("最低市值不能大于最高市值"); return; }
    if (maxPrice !== undefined && minPrice > maxPrice) { setError("最低股价不能大于最高股价"); return; }
    if (maxCap === 0 || maxPrice === 0) { setError("最高条件须大于零，留空表示不限"); return; }
    setError("");
    onApply({ min_market_cap: minCap*1e8, max_market_cap: maxCap === undefined ? undefined : maxCap*1e8,
      min_price: minPrice, max_price: maxPrice, min_amount: minAmount*1e6, exchange: draft.exchange || undefined });
  }
  return <Card>
    <CardHeader>
      <CardTitle>美股全目录筛选</CardTitle>
      <CardDescription>普通股与股票 ADR，不含 ETF、优先股、权证、测试证券及 OTC。金额均为美元，条件同时满足；留空或最低值为 0 表示不限。</CardDescription>
    </CardHeader>
    <CardContent className="space-y-4">
      <form onSubmit={event => { event.preventDefault(); apply(); }} noValidate className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {fields.map(([key, label]) => <label key={key} htmlFor={`us-${key}`} className="space-y-1 text-sm">
            <span>{label}</span>
            <Input id={`us-${key}`} type="number" min="0" step="any" value={draft[key]} placeholder="不限"
              onChange={event => setDraft({ ...draft, [key]: event.target.value })} />
          </label>)}
          <div className="space-y-1 text-sm"><span>上市交易所</span>
            <Select value={draft.exchange || null} onValueChange={value => setDraft({ ...draft, exchange: (value as string) || "" })} items={exchanges}>
              <SelectTrigger aria-label="上市交易所" className="h-9 w-full"><SelectValue placeholder="全部交易所" /></SelectTrigger>
              <SelectContent>
                {exchangeOptions.map(option => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={loading}>应用筛选</Button>
          <Button type="button" variant="outline" disabled={loading} onClick={() => {
            setDraft({ minCap: "", maxCap: "", minPrice: "", maxPrice: "", minAmount: "", exchange: "" }); setError("");
            onApply({ min_market_cap: 0, min_price: 0, min_amount: 0 });
          }}>取消条件</Button>
          <Button type="button" variant="ghost" disabled={loading} onClick={() => {
            setDraft(defaults); setError(""); onApply({ min_market_cap: 1e9, min_price: 5, min_amount: 1e6 });
          }}>恢复默认</Button>
        </div>
      </form>
      {data?.universe_count !== undefined && <div className="grid grid-cols-2 gap-3 rounded-lg bg-muted/40 p-3 text-sm sm:grid-cols-4">
        {[["目录股票", data.universe_count], ["行情覆盖", data.quote_coverage_count], ["条件匹配", data.filtered_count], ["本轮评分", data.candidate_count]].map(([label, count]) => <div key={String(label)}><p className="text-muted-foreground">{label}</p><p className="text-xl font-semibold tabular-nums">{count ?? "--"}</p></div>)}
      </div>}
      <p className="text-xs text-muted-foreground">{data?.quote_missing_count !== undefined ? `目录中 ${data.quote_missing_count} 只缺少有效行情，未参与筛选。` : ""}按成交额选择匹配结果前 {data?.scoring_limit ?? 120} 只补算历史评分，不是全目录评分排名。行情为定时保存的延迟快照，请核对数据时间。</p>
      {data?.filtered_count === 0 && <p className="rounded-lg border p-3 text-sm">没有股票符合当前条件。可放宽筛选范围；缺失指标不会视为满足条件。</p>}
    </CardContent>
  </Card>;
}

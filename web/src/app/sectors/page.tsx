"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Layers3, Loader2, RefreshCw, Target } from "lucide-react";
import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, type SectorItem } from "@/lib/api";
import { cn } from "@/lib/utils";

function percent(value?: number | null) {
  if (value == null) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function PercentValue({ value }: { value?: number | null }) {
  return (
    <span className={cn("font-medium tabular-nums", value != null && value > 0 && "text-green-600", value != null && value < 0 && "text-red-600")}>
      {percent(value)}
    </span>
  );
}

export default function SectorsPage() {
  const [data, setData] = useState<{ sectors: SectorItem[]; coverage_count: number; source: string; generated_at?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.getSectors();
      setData(response.result);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加载板块失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const sectors = data?.sectors || [];
  const active = sectors.filter((sector) => sector.score != null);

  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col gap-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">板块分析</h1>
            <p className="text-muted-foreground">普通沪深主板候选的主题强弱、领涨标的和选股入口。</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={load} disabled={loading}>
              {loading ? <Loader2 data-icon="inline-start" className="animate-spin" /> : <RefreshCw data-icon="inline-start" />}
              刷新
            </Button>
            <Link href="/stock-picker" className={buttonVariants()}>
              <Target data-icon="inline-start" />进入 AI 选股
            </Link>
          </div>
        </div>

        {message && <div className="rounded-lg border px-4 py-3 text-sm">{message}</div>}

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardDescription>覆盖主板股票</CardDescription>
              <CardTitle className="text-2xl">{data?.coverage_count ?? "--"}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>已计算主题</CardDescription>
              <CardTitle className="text-2xl">{active.length}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>数据口径</CardDescription>
              <CardTitle className="text-sm">{data?.source || "--"}</CardTitle>
            </CardHeader>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Layers3 />主题强弱排行</CardTitle>
            <CardDescription>涨幅为当前最近一轮 AI 筛选中，同主题已评分标的的平均表现；点击股票进入个股页。</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>主题</TableHead>
                  <TableHead>覆盖</TableHead>
                  <TableHead>评分</TableHead>
                  <TableHead>5日</TableHead>
                  <TableHead>20日</TableHead>
                  <TableHead>领先标的</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sectors.map((sector) => (
                  <TableRow key={sector.code}>
                    <TableCell className="font-medium">{sector.name}</TableCell>
                    <TableCell>{sector.scored_count}/{sector.candidate_count}</TableCell>
                    <TableCell>{sector.score ?? "--"}</TableCell>
                    <TableCell><PercentValue value={sector.change_5d} /></TableCell>
                    <TableCell><PercentValue value={sector.change_20d} /></TableCell>
                    <TableCell>
                      {sector.leader?.ticker ? (
                        <Link href={`/stock/${sector.leader.ticker}`} className="hover:underline">
                          {sector.leader.name || sector.leader.ticker}
                          {sector.leader.score != null && <Badge className="ml-2" variant="secondary">{sector.leader.score}</Badge>}
                        </Link>
                      ) : "--"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </main>
    </>
  );
}

"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { validateUsCoverSummary } from "@/lib/us-cover-summary";

const percent = (value: number) => `${(value * 100).toFixed(2)}%`;
const labels = { balanced: "均衡", conservative: "稳健", aggressive: "进攻" };

export function UsCoverResearchPanel() {
  const [open, setOpen] = useState(false);
  const query = useQuery({ queryKey: ["us-cover-research-v1"], enabled: open, retry: false, staleTime: 60000,
    queryFn: async ({ signal }) => {
      const response = await fetch("/api/formula-ranking/us-cover-research", { signal });
      if (!response.ok) throw new Error("研究暂不可用");
      return validateUsCoverSummary((await response.json()).result);
    } });
  const data = query.isError ? undefined : query.data;
  return <div className="space-y-3">
    <Button size="sm" variant="outline" onClick={() => setOpen(!open)}>{open ? "关闭美股补充研究" : "查看美股数据补充研究"}</Button>
    {open && <section aria-label="美股数据补充研究" className="space-y-3 rounded-lg border p-3 text-sm">
      <p className="font-medium">美股股本与市值补充研究 · 参数未应用</p>
      {query.isPending && <p role="status">正在加载补充研究…</p>}
      {query.isError && <div><p role="status">研究报告暂不可用。</p><Button size="sm" variant="outline" onClick={() => void query.refetch()}>重试补充研究</Button></div>}
      {data && <>
        <p>固定样本 {data.available_count} 只股票，{data.fold_count} 个滚动窗口；验证期 {data.test_start} 至 {data.test_end}。</p>
        <p className="text-xs text-muted-foreground">原请求60只，3只历史数据缺失、1只基金排除。训练240日／验证80日；股类与主体历史映射仍不完整，不代表全美股覆盖。</p>
        <p>本轮补充 BG、CARR、IOSP、MNRO 的普通股市值；保留上一轮 DAKT 参考。优先股、债券与权利不计入普通股股数，PE／PB口径保持原状态。</p>
        <div className="overflow-x-auto"><table className="w-full text-left text-xs"><caption className="text-left text-muted-foreground">因子可用观测：股票×调仓日，共 {data.coverage.denominator} 个</caption><thead><tr><th className="p-2">因子</th><th className="p-2">补充前</th><th className="p-2">补充后</th></tr></thead><tbody>{([ ["市值",data.coverage.market_cap], ["PE",data.coverage.pe_ratio], ["PB",data.coverage.pb_ratio] ] as const).map(([label,count]) => <tr key={label} className="border-t"><td className="p-2">{label}</td><td className="p-2">{count.before} / {data.coverage.denominator}（{percent(count.before/data.coverage.denominator)}）</td><td className="p-2">{count.after} / {data.coverage.denominator}（{percent(count.after/data.coverage.denominator)}）</td></tr>)}</tbody></table></div>
        <div className="overflow-x-auto"><table className="w-full text-left text-xs"><caption className="text-left text-muted-foreground">风控策略验证净收益 · 基础单边成本0.15%</caption><thead><tr><th className="p-2">模式</th><th className="p-2">补充前研究</th><th className="p-2">补充后研究</th><th className="p-2">成本0.30%</th><th className="p-2">成本0.50%</th></tr></thead><tbody>{data.modes.map(row => <tr key={row.mode} className="border-t"><td className="p-2">{labels[row.mode]}</td><td className="p-2">{percent(row.before.net_return)}</td><td className="p-2">{percent(row.after.net_return)}</td>{row.cost_stress.map(cost => <td key={cost.one_way_cost} className="p-2">{percent(cost.net_return)}</td>)}</tr>)}</tbody></table></div>
        <p className="text-amber-700">均衡模式亏损减少，稳健和进攻模式略差，成本压力下仍亏损。研究参数未应用到实时选股。</p>
        <p className="text-xs text-muted-foreground">每窗口初始资金10,000 USD、最低费用1 USD、整数股。数据补充与重新选参同时改变持仓；验证数据曾被查看，尚无独立未来验证，公司行动和交易执行覆盖仍有限。</p>
      </>}
    </section>}
  </div>;
}

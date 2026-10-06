"use client";
import { useEffect, useState } from "react";

type Protocol = { engine_storage?: string; status: string; cutoff?: string; minimum_sessions?: number; requested_count?: number; training_available_count?: number; training_cutoff?: string; candidate_weights?: Record<string, number>; risk_parameters?: {atr_multiple: number; target_r: number}; message?: string; complete_quote_and_risk_data?: boolean; test_start?: string; test_end?: string; limitations?: string[] };

export function FormulaHoldoutPanel({ market }: {market: "CN" | "HK" | "US"}) {
  const [state,setState]=useState<{market:string;result:Protocol}|null>(null);
  useEffect(()=>{
    const controller=new AbortController();
    void fetch(`/api/formula-ranking/holdout?market=${market}`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)]),cache:"no-store"}).then(async response=>{
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"协议不可用");
      if(!controller.signal.aborted)setState({market,result:payload.result});
    }).catch(()=>{if(!controller.signal.aborted)setState({market,result:{status:"unavailable",message:"后续验证协议暂不可用，未展示验证收益。"}});});
    return ()=>controller.abort();
  },[market]);
  const p=state?.market===market?state.result:null;
  return <div className="space-y-2 rounded-lg border p-3 text-xs text-muted-foreground">
    <p className="font-medium text-foreground">后续留出验证 · 固定参数</p>
    {!p&&<p>正在读取当前市场验证协议…</p>}
    {p?.message&&<p>{p.message}</p>}
    {p?.cutoff&&<>
      <p>固定请求样本 {p.requested_count} 只；未来评估不得更换或缩小样本。</p>
      <p>截止日期 {p.cutoff}；仅评估之后的首个 {p.minimum_sessions} 交易日。</p>
      {p.engine_storage==="archived"&&<p>后续验证使用已归档的冻结版本，不随当前选股迭代改变。</p>}
      <p>原回测有效样本 {p.training_available_count} 只；选参训练截至 {p.training_cutoff}。</p>
      {p.status==="awaiting_evaluation"&&<p>参数已冻结，未来验证尚未完成。</p>}
      {p.status==="insufficient_data"&&<p>样本、预热或未来交易日不足，未计算收益。</p>}
      {p.status==="prospective_research"&&<p>固定参数评估区间 {p.test_start} 至 {p.test_end}；{p.complete_quote_and_risk_data?"报价与保护判断数据检查通过":"报价或保护判断仍有缺口"}。未自动应用参数。</p>}
      <details><summary className="cursor-pointer">冻结参数与验证限制</summary><div className="mt-2 space-y-1"><p>{Object.entries(p.candidate_weights||{}).map(([name,value])=>`${name} ${(value*100).toFixed(0)}%`).join(" / ")}</p>{p.risk_parameters&&<p>固定止损 {p.risk_parameters.atr_multiple} × ATR，目标 {p.risk_parameters.target_r}R；后续不按收益重选。</p>}{p.limitations?.map(text=><p key={text}>{text}</p>)}</div></details>
    </>}
  </div>;
}

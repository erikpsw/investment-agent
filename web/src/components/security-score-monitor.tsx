"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { scoreKey, type DetectionItem, type ScoreHistory, type ScoreMode, type ScoreSnapshot, type SecurityIdentity } from "@/lib/score-tracking";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const value=(n:number|null|undefined)=>n==null?"未记录":n.toFixed(2);
const difference=(n:number|null|undefined)=>n==null?"—":`${n>0?"+":""}${n.toFixed(2)}`;

function ScoreHistoryView({security,mode}:{security:SecurityIdentity;mode:ScoreMode}) {
  const [data,setData]=useState<ScoreHistory>({items:[],next_cursor:null});
  const [days,setDays]=useState<30|90>(30);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const generation=useRef(0);
  useEffect(()=>()=>{generation.current++;},[]);
  async function load(range:30|90,cursor?:string) {
    const id=++generation.current;setBusy(true);setError("");
    try {
      const response=await api.getScoreHistory(security,range,cursor);
      if(id!==generation.current)return;
      setData(current=>({items:cursor?[...current.items,...response.result.items]:response.result.items,next_cursor:response.result.next_cursor}));
      setDays(range);
    } catch(e) {if(id===generation.current)setError(e instanceof Error?e.message:"历史记录暂不可用");}
    finally{if(id===generation.current)setBusy(false);}
  }
  const ordered=[...data.items].filter(row=>row.mode===mode&&typeof row.formula_score==="number").sort((a,b)=>(a.quote_as_of||"").localeCompare(b.quote_as_of||""));
  const segments:ScoreSnapshot[][]=[];
  for(const row of ordered) {
    const previous=segments.at(-1)?.at(-1);
    if(!previous||previous.formula_version!==row.formula_version||previous.config_fingerprint!==row.config_fingerprint)segments.push([]);
    segments.at(-1)!.push(row);
  }
  const points=new Map(ordered.map((row,index)=>[row,`${20+index/Math.max(ordered.length-1,1)*560},${130-(row.formula_score||0)*1.1}`]));
  return <details className="mt-3 rounded-md border p-3" onToggle={event=>{if(event.currentTarget.open&&!data.items.length&&!busy)void load(days);}}>
    <summary className="cursor-pointer text-sm font-medium">评分历史与变化趋势</summary>
    <div className="mt-3 flex gap-2">{([30,90] as const).map(range=><Button key={range} size="sm" variant={days===range?"default":"outline"} disabled={busy} onClick={()=>void load(range)}>最近{range}交易观察日</Button>)}</div>
    {error&&<p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
    {busy&&<p className="mt-2 text-sm">正在读取已保存记录…</p>}
    {!busy&&!ordered.length&&<p className="mt-2 text-sm text-muted-foreground">尚未形成该模式的评分历史；不回填过去评分。</p>}
    {ordered.length>0&&<svg role="img" aria-label={`${security.ticker}已保存评分曲线，跨版本断开`} viewBox="0 0 600 150" className="mt-2 w-full max-w-2xl text-primary">
      <line x1="20" y1="130" x2="580" y2="130" stroke="currentColor" opacity=".25"/>
      {segments.map((segment,index)=><polyline key={index} points={segment.map(row=>points.get(row)).join(" ")} fill="none" stroke="currentColor" strokeWidth="2"/>)}
      {ordered.map((row,index)=>{const [x,y]=points.get(row)!.split(",");return <circle key={row.id||index} cx={x} cy={y} r="3" fill="currentColor"><title>{row.quote_as_of} · {value(row.formula_score)}</title></circle>;})}
    </svg>}
    <p className="mt-2 text-xs text-muted-foreground">仅含实际保存的观察记录；盘中记录不代表收盘评分，不同模式、版本与配置不直接连接。</p>
    <div className="mt-2 max-h-48 overflow-auto text-xs">{data.items.filter(row=>row.mode===mode).map((row,index)=><div key={row.id||index} className="flex flex-wrap justify-between gap-2 border-b py-2"><span>{row.quote_as_of?new Date(row.quote_as_of).toLocaleString():"时间待核验"}</span><span>{value(row.formula_score)}分 · {row.formula_version} · 覆盖{Math.round((row.data_coverage||0)*100)}%</span></div>)}</div>
    {data.next_cursor&&<Button className="mt-2" size="sm" variant="outline" disabled={busy} onClick={()=>void load(days,data.next_cursor!)}>加载更多记录</Button>}
  </details>;
}

export function SecurityScoreMonitor({securities,userSub,disabled=false,onDetected,fixedMode}:{securities:SecurityIdentity[];userSub:string;disabled?:boolean;onDetected?:()=>void;fixedMode?:ScoreMode}) {
  const [localMode,setMode]=useState<ScoreMode>("balanced");
  const mode=fixedMode??localMode;
  const [automatic,setAutomatic]=useState(false);
  const [rows,setRows]=useState<DetectionItem[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [progress,setProgress]=useState(0);
  const controller=useRef<AbortController|null>(null);
  const generation=useRef(0);
  const running=useRef(false);
  const detected=useRef(onDetected);
  useEffect(()=>{detected.current=onDetected;},[onDetected]);
  const encoded=JSON.stringify(securities);
  const run=useCallback(async()=>{
    if(running.current||disabled||!userSub)return;
    const inputs=JSON.parse(encoded) as SecurityIdentity[];
    if(!inputs.length)return;
    running.current=true;setBusy(true);setError("");setProgress(0);
    const id=++generation.current;const abort=new AbortController();controller.current=abort;
    try {
      // Four securities per request keeps a refresh bounded on lightweight deployments.
      for(let offset=0;offset<inputs.length;offset+=4) {
        const response=await api.detectScores(inputs.slice(offset,offset+4),mode,crypto.randomUUID(),abort.signal);
        if(id!==generation.current)return;
        setRows(current=>{
          const mapped=new Map(current.map(item=>[scoreKey(item),item]));
          for(const item of response.result.items)mapped.set(scoreKey(item),item);
          return [...mapped.values()];
        });
        setProgress(Math.min(offset+4,inputs.length));
      }
      detected.current?.();
    }catch(e){if(!abort.signal.aborted&&id===generation.current)setError(e instanceof Error?e.message:"评分检测失败");}
    finally{if(id===generation.current){running.current=false;setBusy(false);}}
  },[encoded,mode,userSub,disabled]);
  useEffect(()=>{
    const visible=()=>{if(document.visibilityState==="visible"){if(automatic&&!disabled)void run();}else{generation.current++;controller.current?.abort();running.current=false;setBusy(false);}};
    const timer=automatic&&!disabled?window.setInterval(visible,60_000):undefined;document.addEventListener("visibilitychange",visible);
    return()=>{window.clearInterval(timer);document.removeEventListener("visibilitychange",visible);};
  },[automatic,disabled,run]);
  const invalidate=useCallback(()=>{generation.current++;controller.current?.abort();running.current=false;},[]);
  useEffect(()=>{setBusy(false);setRows([]);return invalidate;},[encoded,mode,userSub,invalidate]);
  function cancel(){generation.current++;controller.current?.abort();running.current=false;setBusy(false);}
  const wanted=new Set(securities.map(scoreKey));
  return <Card>
    <CardHeader><CardTitle className="text-lg">自选与持仓评分检测</CardTitle></CardHeader>
    <CardContent className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <select disabled={Boolean(fixedMode)} aria-label="评分模式" className="min-h-10 rounded border bg-background px-2" value={mode} onChange={e=>{cancel();setRows([]);setMode(e.target.value as ScoreMode);}}>
          <option value="balanced">均衡</option><option value="conservative">保守</option><option value="aggressive">积极</option>
        </select>
        <Button disabled={disabled||busy||!securities.length} onClick={()=>void run()}>{busy?`检测中 ${progress}/${securities.length}`:"检测评分"}</Button>
        {busy&&<Button variant="outline" onClick={cancel}>停止本轮</Button>}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={automatic} disabled={disabled} onChange={e=>setAutomatic(e.target.checked)}/>页面可见时每60秒检测</label>
      </div>
      <p className="text-xs text-muted-foreground">当前买入机会评分沿用共享公式；评分提高不等于加仓。页面关闭后停止检测，休市/旧报价不会制造新趋势。</p>
      {disabled&&<p className="text-sm">请先保存或取消持仓修改，再进行检测和管理。</p>}
      {error&&<p role="alert" className="text-sm text-destructive">{error}</p>}
      {!rows.length&&!busy&&<p className="text-sm text-muted-foreground">点击检测，开始积累真实评分记录。</p>}
      <div className="grid gap-3 xl:grid-cols-2">{rows.filter(row=>wanted.has(scoreKey(row))).map(row=><section key={scoreKey(row)} className="min-w-0 rounded-lg border p-3">
        <div className="flex flex-wrap justify-between gap-2"><strong>{row.market} · {row.ticker}</strong><span>{row.snapshot?`${value(row.snapshot.formula_score)}分`:"待核验"}</span></div>
        {row.message&&<p className="mt-1 text-sm text-destructive">{row.message}</p>}
        {row.snapshot&&<><p className="mt-1 text-sm">较上次 {difference(row.change?.previous_delta)} · 覆盖 {Math.round((row.snapshot.data_coverage||0)*100)}% · {row.saved?row.inserted?"已保存":"报价未更新":"未保存"}</p>
          <p className="break-words text-xs text-muted-foreground">报价：{row.snapshot.quote_as_of?new Date(row.snapshot.quote_as_of).toLocaleString():"未核验"}</p>
          {row.change?.quality_changed&&<p className="text-xs text-amber-700">数据覆盖变化，本次分差不能只解释为走势变化。</p>}
          {!!row.change?.reasons?.length&&<p className="mt-1 text-xs">{row.change.reasons.slice(0,3).map(r=>`${r.factor} ${difference(r.delta)}`).join("；")}</p>}
          <p className="mt-1 text-xs">5个观察日评分变化 {difference(row.change?.trend_5d?.delta)} · 20个观察日 {difference(row.change?.trend_20d?.delta)}（非连续观察时不代表固定日历周期；不足时留空）</p>
        </>}
        <ScoreHistoryView key={`${scoreKey(row)}:${mode}`} security={{market:row.market as SecurityIdentity['market'],ticker:row.ticker}} mode={mode}/>
      </section>)}</div>
    </CardContent>
  </Card>;
}

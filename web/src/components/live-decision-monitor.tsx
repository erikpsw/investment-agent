"use client";
import {useEffect,useState} from "react";
type Quote={price:number;quote_as_of:string;fetched_at:string;fresh:boolean};
export function LiveDecisionMonitor({ticker}:{ticker:string}){
 const [quote,setQuote]=useState<Quote|null>(null),[error,setError]=useState(''),[entry,setEntry]=useState(''),[today,setToday]=useState(true);
 const supported=/^(sh(?:60|68)|sz(?:00|30))\d{4}$/.test(ticker);
 useEffect(()=>{if(!supported)return;const controller=new AbortController();let busy=false;
  async function load(){if(busy)return;busy=true;try{const r=await fetch(`/api/strategy/live-quote/${ticker}`,{signal:controller.signal,cache:'no-store'});if(!r.ok)throw Error('行情暂不可用');setQuote(await r.json());setError('');}catch(e){if(e instanceof Error&&e.name!=='AbortError'){setError('本次刷新失败，不据旧价触发实时建议');setQuote(null);}}finally{busy=false;}}
  void load();const timer=setInterval(load,30000);return()=>{controller.abort();clearInterval(timer);};
 },[ticker,supported]);
 if(!supported)return <p className="rounded-lg border p-4 text-sm">此板块已从当前推荐范围排除；下方仅保留原研究池的历史回放。</p>;
 const filled=Number(entry),stop=filled>0?filled*.88:null;
 const triggered=Boolean(quote?.fresh&&stop&&quote.price<=stop&&!today);
 return <section className="space-y-3 rounded-xl border p-4"><h2 className="font-semibold">行情与退出监测 · 原始报价</h2><p className="text-sm text-muted-foreground">每30秒轮询；原始行情时间与请求时间分别显示，不把休市收盘价称为实时成交。不会将原始价叠到后复权历史图上。</p>
 {error&&<p role="alert" className="text-sm text-red-600">{error}</p>}{quote?<div className="grid gap-3 sm:grid-cols-3"><div><p className="text-2xl font-semibold">{quote.price.toFixed(2)}</p><p className="text-sm">{quote.fresh?'有效时段最新报价':'最近报价，非有效盘中实时'}</p></div><p className="text-xs">行情时间<br/>{quote.quote_as_of}</p><p className="text-xs">请求时间<br/>{quote.fetched_at}</p></div>:!error&&<p className="text-sm">正在请求行情…</p>}
 <div className="flex flex-wrap items-center gap-4"><label className="text-sm">你的原始入场成交价 <input aria-label="实时监测入场价" type="number" min="0" className="ml-2 w-32 rounded border bg-background p-2" value={entry} onChange={e=>setEntry(e.target.value)}/></label><label className="text-sm"><input type="checkbox" checked={today} onChange={e=>setToday(e.target.checked)}/> 当日买入（T+1）</label></div>
 {stop&&<p className={`rounded-lg p-3 text-sm ${triggered?'bg-red-50 text-red-800':'bg-muted'}`}>参考12%止损：{stop.toFixed(3)}。{today?'当日买入受T+1约束。':!quote?.fresh?'当前没有新鲜行情，不触发实时退出建议。':triggered?'已触及止损监测线；请检查实际可成交能力，跳空不保证止损价成交。':'当前报价尚未触及止损监测线。'}</p>}
 </section>;
}

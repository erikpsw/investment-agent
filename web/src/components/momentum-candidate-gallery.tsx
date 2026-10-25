"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
type Candidate={ticker:string;name:string;rank:number;momentum_pct:number};
type Plot={bars:[string,number,number,number,number,number][];trades:{entry_date:string;exit_date:string}[]};
function CandidateCard({row,scope,allow}:{row:Candidate;scope:string;allow:boolean}){
 const [plot,setPlot]=useState<Plot|null>(null),[error,setError]=useState(false);
 useEffect(()=>{const controller=new AbortController();fetch(`/strategy/momentum/${row.ticker}.json.gz`,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error();const bytes=new Uint8Array(await r.arrayBuffer());const text=bytes[0]===31&&bytes[1]===139?await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text():new TextDecoder().decode(bytes);setPlot(JSON.parse(text));}).catch(e=>{if(e.name!=='AbortError')setError(true);});return()=>controller.abort();},[row.ticker]);
 const bars=plot?.bars.slice(-60)??[],low=Math.min(...bars.map(b=>b[3])),high=Math.max(...bars.map(b=>b[2])),span=high-low||1;
 const y=(n:number)=>10+(high-n)/span*115;const x=(i:number)=>8+i*344/Math.max(1,bars.length-1);
 const buys=new Set(plot?.trades.map(t=>t.entry_date));const sells=new Set(plot?.trades.map(t=>t.exit_date));
 return <Link href={`/strategy/stock/${row.ticker}?scope=${scope}`} className="space-y-3 rounded-xl border p-4 hover:border-primary"><h3 className="font-semibold">{row.rank}. {row.name} <span className="text-xs text-muted-foreground">{row.ticker}</span></h3><p className="text-sm">12周动量 {row.momentum_pct.toFixed(2)}% · {row.rank<=20?'优先候选':'补位备用'}</p><div className="h-40 rounded-lg bg-muted/30">
 {plot?<svg role="img" aria-label={`${row.name}历史后复权K线与原策略回测买卖点`} viewBox="0 0 360 150" className="h-full w-full"><title>后复权研究价格，不能直接下单</title>{bars.map((b,i)=>{const color=b[4]>=b[1]?'#ef4444':'#10b981';return <g key={b[0]}><line x1={x(i)} x2={x(i)} y1={y(b[2])} y2={y(b[3])} stroke={color}/><rect x={x(i)-1.5} y={Math.min(y(b[1]),y(b[4]))} width="3" height={Math.max(1,Math.abs(y(b[1])-y(b[4])))} fill={color}/>{buys.has(b[0])&&<text x={x(i)-3} y={Math.min(137,y(b[3])+12)} fontSize="10" fill="#2563eb">买</text>}{sells.has(b[0])&&<text x={x(i)-3} y={Math.max(10,y(b[2])-3)} fontSize="10" fill="#f97316">卖</text>}</g>;})}<text x="8" y="147" fontSize="9" fill="#8993a4">历史图截至 {bars.at(-1)?.[0]}</text></svg>:<p className="p-5 text-sm">{error?'图表暂不可用，可点击重试':'加载历史图…'}</p>}
 </div><p className="text-xs leading-5 text-muted-foreground">{allow?'大盘门槛通过，仍需周度入场时点、空位、现金和成交约束核验。':'大盘或数据门槛未通过，当前不是新增买点。'}{plot&&`原793只回测记录${plot.trades.length}笔。`}点击查看入场、止损与到期卖出依据。</p></Link>;
}
export function MomentumCandidateGallery({rows,scope,allow}:{rows:Candidate[];scope:string;allow:boolean}){return <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{rows.map(row=><CandidateCard key={`${scope}-${row.ticker}`} row={row} scope={scope} allow={allow}/>)}</div>;}

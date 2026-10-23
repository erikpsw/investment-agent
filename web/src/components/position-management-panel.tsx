"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { type PortfolioRiskOverview, type PositionManagement, type RiskSettings, type SecurityIdentity, securitiesFrom, entrySnapshotAt } from "@/lib/score-tracking";
import { SecurityScoreMonitor } from "@/components/security-score-monitor";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const n=(value:number|null|undefined,digits=2)=>value==null?"待核验":value.toLocaleString("zh-CN",{maximumFractionDigits:digits});
const security=(row:PositionManagement):SecurityIdentity=>({market:row.market as SecurityIdentity['market'],ticker:row.ticker});

function PositionCard({row,revision,mutate,disabled}:{row:PositionManagement;revision:number;mutate:(work:()=>Promise<unknown>)=>Promise<void>;disabled:boolean}) {
  const [portion,setPortion]=useState(33);
  const effective=row.protection_comparable===false?null:row.management.protection;
  const candidate=row.protection_candidate;
  const lot=row.market==='CN'?100:row.market==='US'?1:effective?.lot_size;
  const trim=lot&&row.quantity!=null?Math.floor(row.quantity*portion/100/lot)*lot:null;
  return <section className="min-w-0 space-y-2 rounded-lg border p-3">
    <div className="flex flex-wrap justify-between gap-2"><strong>{row.market} · {row.ticker}</strong><span className="text-sm">{row.signal.reason}</span></div>
    <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
      <div><dt className="text-muted-foreground">本轮买入评分</dt><dd>{row.management.entry_snapshot?.formula_score??"未记录"}</dd></div>
      <div><dt className="text-muted-foreground">当前评分</dt><dd>{row.detection.formula_score??"待检测"}</dd></div>
      <div><dt className="text-muted-foreground">相比买入评分</dt><dd>{n(row.detection.change?.entry_delta)}{row.detection.change?.entry_status==='incomparable'?'（版本/模式不可比）':''}</dd></div>
      <div><dt className="text-muted-foreground">当前仓位 / 上限</dt><dd>{n(row.current_weight_percent)}% / {n(row.position_cap_percent)}%</dd></div>
      <div><dt className="text-muted-foreground">计划风险（{row.currency}）</dt><dd>{n(row.planned_risk_native)}</dd></div>
      <div><dt className="text-muted-foreground">参考可追加数量</dt><dd>{n(row.additional_quantity,4)}</dd></div>
      <div><dt className="text-muted-foreground">已确认止损</dt><dd>{n(effective?.stop_loss)}</dd></div>
      <div><dt className="text-muted-foreground">候选止损</dt><dd>{n(candidate.stop_loss)}</dd></div>
      <div><dt className="text-muted-foreground">第一 / 第二止盈情景</dt><dd>{n(effective?.take_profit_1??candidate.take_profit_1)} / {n(effective?.take_profit_2??candidate.take_profit_2)}</dd></div>
    </dl>
    <p className="text-xs text-muted-foreground">{row.quantity_reason}</p>
    {row.detection.quote_as_of&&<p className="text-xs text-muted-foreground">评分报价：{new Date(row.detection.quote_as_of).toLocaleString()}</p>}
    {!row.management.episode_id?<Button size="sm" disabled={disabled} onClick={()=>void mutate(()=>api.adoptPosition(security(row),revision,crypto.randomUUID()))}>开始跟踪现有持仓</Button>:
      candidate.status==='candidate'&&candidate.snapshot_id?<Button size="sm" disabled={disabled} onClick={()=>void mutate(()=>api.confirmProtection(security(row),row.management.episode_id!,revision,candidate))}>确认候选保护计划</Button>:
      <p className="text-xs text-amber-700">{candidate.reason||"请先完成有效评分检测，再核对保护情景。"}</p>}
    {!row.management.entry_snapshot&&<p className="text-xs text-muted-foreground">未保存实际买入时评分，启用跟踪不会补造历史分数。</p>}
    <div className="flex flex-wrap items-center gap-2 text-sm"><label>止盈减持比例 <input aria-label={`${row.ticker}止盈减持比例`} type="number" min="1" max="100" value={portion} className="w-16 rounded border bg-background p-1" onChange={e=>setPortion(Math.min(100,Math.max(1,Number(e.target.value)||1)))}/>%</label><span>对应 {trim==null?"每手资料待核验":`${n(trim,4)} 股`}</span></div>
    <p className="text-xs text-muted-foreground">候选计划不会自动覆盖已确认保护；减持为情景计算。{row.market==='CN'?'A股新增仓位受T+1、停牌及涨跌停约束。':''}</p>
  </section>;
}

export function PositionManagementPanel({positions,userSub,disabled=false,onChanged}:{positions:{ticker:string;market?:string}[];userSub:string;disabled?:boolean;onChanged:()=>Promise<void>}) {
  const [data,setData]=useState<PortfolioRiskOverview|null>(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [settings,setSettings]=useState<RiskSettings>({mode:'balanced',risk_budget_percent:1,position_cap_percent:20,one_way_cost:.0015});
  const [trade,setTrade]=useState({action:'buy',market:'US',ticker:'',quantity:'',price:'',fee:'0',executed:'',associate:false,currency:'USD',amount:''});
  const request=useRef<{signature:string;id:string;executed:string}|null>(null);
  const generation=useRef(0);
  const load=useCallback(async()=>{
    const id=++generation.current;
    try{
      const response=await api.getPortfolioRisk();if(id!==generation.current)return;
      setData(response.result);setSettings(current=>({...current,...response.result.settings}));setError("");
    }catch(e){if(id===generation.current)setError(e instanceof Error?e.message:"仓位管理暂不可用");}
  },[]);
  const positionSignature=JSON.stringify(positions);
  const invalidate=useCallback(()=>{generation.current++;},[]);
  useEffect(()=>{setData(null);void load();return invalidate;},[load,positionSignature,disabled,invalidate]);
  async function mutate(work:()=>Promise<unknown>){
    if(disabled||busy)return;setBusy(true);setMessage("");
    try{await work();setMessage("操作已保存，持仓和管理数据已重新读取");await onChanged();await load();}
    catch(e){setError(e instanceof Error?e.message:"操作失败，请刷新核对后重试");}
    finally{setBusy(false);}
  }
  async function submitTrade(){
    if(!data)return;
    const signature=JSON.stringify(trade);
    if(request.current?.signature!==signature)request.current={signature,id:crypto.randomUUID(),executed:trade.executed?new Date(trade.executed).toISOString():new Date().toISOString()};
    const pending=request.current;
    await mutate(async()=>{
      let snapshotId:string|undefined;
      if(trade.associate&&trade.action==='buy'){
        try{
          const history=await api.getScoreHistory({market:trade.market as SecurityIdentity['market'],ticker:trade.ticker});
          const latest=entrySnapshotAt(history.result.items,settings.mode,pending.executed);
          snapshotId=latest?.id;
        }catch{/* A missing score must not discard an otherwise valid accounting event. */}
      }
      const event=trade.action==='set_cash'?{action:'set_cash' as const,currency:trade.currency,amount:Number(trade.amount)}:
        {action:trade.action as 'buy'|'sell',market:trade.market,instrument_id:trade.ticker,quantity:Number(trade.quantity),price:Number(trade.price),fee:Number(trade.fee),executed_at:pending.executed,score_snapshot_id:snapshotId};
      await api.recordPositionEvent({...event,request_id:pending.id,expected_revision:data.revision});
      request.current=null;
    });
  }
  return <div className="space-y-4">
    <SecurityScoreMonitor key={userSub} userSub={userSub} fixedMode={data?.settings.mode??"balanced"} securities={securitiesFrom(positions)} disabled={disabled||busy} onDetected={()=>void load()}/>
    <Card><CardHeader><CardTitle className="text-lg">仓位预算与止盈止损</CardTitle></CardHeader><CardContent className="space-y-4">
      <div className="flex flex-wrap items-center gap-3"><Button variant="outline" disabled={busy} onClick={()=>void load()}>刷新管理数据</Button><span className="text-xs text-muted-foreground">已确认计划与候选更新分开保存；风险优先于评分。</span></div>
      {error&&<p role="alert" className="text-sm text-destructive">{error}</p>}
      {message&&<p className="text-sm">{message}</p>}
      {data&&<>
        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><div><dt>账户资产（CNY）</dt><dd>{n(data.account_value_base)}</dd></div><div><dt>计划价格风险（CNY）</dt><dd>{n(data.planned_risk_base)}</dd></div><div><dt>剩余组合预算（CNY）</dt><dd>{n(data.remaining_risk_base)}</dd></div><div><dt>风险待核验持仓</dt><dd>{data.unknown_risk_count}只</dd></div></dl>
        <form className="flex flex-wrap items-end gap-3 rounded border p-3" onSubmit={e=>{e.preventDefault();void mutate(()=>api.saveRiskSettings(settings));}}>
          <label className="text-sm">模式<select aria-label="仓位风险模式" className="mt-1 block min-h-10 rounded border bg-background px-2" value={settings.mode} onChange={e=>setSettings({...settings,mode:e.target.value as RiskSettings['mode']})}><option value="balanced">均衡</option><option value="conservative">保守</option><option value="aggressive">积极</option></select></label>
          {([{key:'risk_budget_percent',label:'单笔风险%',min:.1,max:2},{key:'position_cap_percent',label:'单股仓位上限%',min:1,max:30},{key:'total_risk_percent',label:'组合总风险上限%',min:.1,max:10}] as const).map(field=><label key={field.key} className="text-sm">{field.label}<Input aria-label={field.label} className="mt-1 w-32" type="number" min={field.min} max={field.max} step="0.1" value={settings[field.key]??''} onChange={e=>setSettings({...settings,[field.key]:e.target.value===''?undefined:Number(e.target.value)})}/></label>)}
          <Button disabled={disabled||busy} type="submit">保存风险设置</Button>
        </form>
        <div className="grid gap-3 xl:grid-cols-2">{data.items.map(row=><PositionCard key={row.key} row={row} revision={data.revision} mutate={mutate} disabled={disabled||busy}/>)}</div>
        {!data.items.length&&<p className="text-sm text-muted-foreground">暂无持仓，可先登记本币现金，再记录买入。</p>}
        <details className="rounded border p-3"><summary className="cursor-pointer text-sm font-medium">买卖与现金记账</summary>
          <form className="mt-3 grid gap-3 sm:grid-cols-2" onSubmit={e=>{e.preventDefault();void submitTrade();}}>
            <label className="text-sm">记账类型<select aria-label="记账类型" className="mt-1 block min-h-10 rounded border bg-background px-2" value={trade.action} onChange={e=>setTrade({...trade,action:e.target.value})}><option value="buy">买入</option><option value="sell">卖出</option><option value="set_cash">设置本币现金余额</option></select></label>
            {trade.action==='set_cash'?<><label className="text-sm">现金币种<select aria-label="现金币种" value={trade.currency} className="mt-1 block min-h-10 rounded border bg-background px-2" onChange={e=>setTrade({...trade,currency:e.target.value})}><option>CNY</option><option>USD</option><option>HKD</option></select></label><label className="text-sm">余额<Input aria-label="记账现金余额" type="number" min="0" step="any" required value={trade.amount} onChange={e=>setTrade({...trade,amount:e.target.value})}/></label></>:
              <><label className="text-sm">市场<select aria-label="记账市场" className="mt-1 block min-h-10 rounded border bg-background px-2" value={trade.market} onChange={e=>setTrade({...trade,market:e.target.value})}><option value="CN">A股</option><option value="HK">港股</option><option value="US">美股</option></select></label>
              <label className="text-sm">证券代码<Input aria-label="记账证券代码" required value={trade.ticker} onChange={e=>setTrade({...trade,ticker:e.target.value})}/></label>
              <label className="text-sm">数量<Input aria-label="记账数量" type="number" min="0.00000001" step="any" required value={trade.quantity} onChange={e=>setTrade({...trade,quantity:e.target.value})}/></label>
              <label className="text-sm">成交价（本币）<Input aria-label="记账成交价" type="number" min="0.00000001" step="any" required value={trade.price} onChange={e=>setTrade({...trade,price:e.target.value})}/></label>
              <label className="text-sm">实际费用（本币）<Input aria-label="记账费用" type="number" min="0" step="any" value={trade.fee} onChange={e=>setTrade({...trade,fee:e.target.value})}/></label>
              <label className="text-sm">成交时间（留空为现在）<Input aria-label="记账成交时间" type="datetime-local" value={trade.executed} onChange={e=>setTrade({...trade,executed:e.target.value})}/></label>
              {trade.action==='buy'&&<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={trade.associate} onChange={e=>setTrade({...trade,associate:e.target.checked})}/>关联成交前15分钟内实际保存的同模式评分</label>}</>}
            <Button type="submit" disabled={disabled||busy}>确认记账</Button>
            <p className="text-xs text-muted-foreground sm:col-span-2">仅记录你确认的交易，不向券商下单。补录时没有适用记录则标记买入评分未记录；同一请求重试不会重复扣款。</p>
          </form>
        </details>
        <p className="text-xs text-muted-foreground">{data.limitations.join("；")}</p>
      </>}
    </CardContent></Card>
  </div>;
}

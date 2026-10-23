export type ScoreMode = "balanced" | "conservative" | "aggressive";
export type SecurityIdentity = {market:"CN"|"HK"|"US";ticker:string};
export interface ScoreSnapshot {
  id?:string;market:string;ticker:string;mode:string;formula_version:string;config_fingerprint:string;
  formula_score:number|null;quote_as_of?:string;observed_at?:string;data_coverage?:number;missing_fields?:string[];
  price?:number;quality_status?:string;contributions?:Record<string,number>;risk_plan?:ProtectionPlan;
}
export interface ProtectionPlan {
  status?:string;reason?:string;currency?:string;price_basis?:string;reference_price?:number;stop_loss?:number;
  take_profit_1?:number;take_profit_2?:number;quote_as_of?:string;snapshot_id?:string;config_fingerprint?:string;
  episode_id?:string;confirmed_at?:string;lot_size?:number;
}
export interface ScoreChange {
  previous_delta:number|null;entry_delta:number|null;quality_changed?:boolean;entry_status?:string;
  reasons?:{factor:string;delta:number}[];trend_5d?:{status:string;delta:number|null;observed_sessions:number};
  trend_20d?:{status:string;delta:number|null;observed_sessions:number};
}
export interface DetectionItem {market:string;ticker:string;status:string;snapshot?:ScoreSnapshot;change?:ScoreChange;message?:string;saved?:boolean;inserted?:boolean}
export interface ScoreHistory {items:ScoreSnapshot[];next_cursor:string|null}
export interface RiskSettings {mode:ScoreMode;risk_budget_percent:number;position_cap_percent:number;total_risk_percent?:number;one_way_cost:number}
export interface PositionManagement {
  key:string;market:string;ticker:string;currency:string;quantity:number|null;price:number|null;
  planned_risk_native:number|null;additional_quantity:number|null;quantity_reason:string;current_weight_percent:number|null;
  position_cap_percent:number|null;protection_comparable?:boolean;management:{episode_id?:string;entry_snapshot?:ScoreSnapshot|null;protection?:ProtectionPlan|null};
  detection:ScoreSnapshot & {change?:ScoreChange};protection_candidate:ProtectionPlan;signal:{status:string;reason:string};
}
export interface PortfolioRiskOverview {
  items:PositionManagement[];revision:number;account_value_base:number|null;planned_risk_base:number|null;
  remaining_risk_base:number|null;unknown_risk_count:number;cash:Record<string,number>;settings:Partial<RiskSettings>;limitations:string[];
}
type Comparable = Pick<ScoreSnapshot,'market'|'ticker'|'mode'|'formula_version'|'config_fingerprint'> & {formula_score?:number|null};
export function comparableScores(a:Comparable,b:Comparable) {
  return (['market','ticker','mode','formula_version','config_fingerprint'] as const).every(k=>Boolean(a[k])&&a[k]===b[k]);
}
export function scoreDelta(a:Comparable,b:Comparable) {
  return comparableScores(a,b)&&typeof a.formula_score==='number'&&Number.isFinite(a.formula_score)&&typeof b.formula_score==='number'&&Number.isFinite(b.formula_score)
    ? Math.round((a.formula_score-b.formula_score)*10000)/10000:null;
}
export function requestIsCurrent(current:{generation:number;user:string},response:{generation:number;user:string}) {
  return current.generation===response.generation&&current.user===response.user;
}
export function canonicalTicker(market:string,ticker:string) {
  let code=ticker.trim();
  if(market==='CN'){code=code.toLowerCase();if(/^\d{6}$/.test(code))code=(code.startsWith('6')?'sh':/^[489]/.test(code)?'bj':'sz')+code;}
  else if(market==='HK'){code=code.toLowerCase().replace(/^hk/,'').replace(/\.hk$/,'');if(/^\d{4,5}$/.test(code))code='hk'+code.padStart(5,'0');}
  else code=code.toUpperCase();
  return code;
}
export const scoreKey = (item:{market:string;ticker:string})=>`${item.market}:${canonicalTicker(item.market,item.ticker)}`;
export function entrySnapshotAt(rows:ScoreSnapshot[],mode:string,executed:string) {
  const time=Date.parse(executed);
  return rows.filter(row=>row.mode===mode&&row.quote_as_of&&row.observed_at&&
    Date.parse(row.quote_as_of)<=time&&time-Date.parse(row.quote_as_of)<=900_000&&Date.parse(row.observed_at)<=time)
    .sort((a,b)=>Date.parse(b.quote_as_of!)-Date.parse(a.quote_as_of!))[0];
}
export function securitiesFrom(rows:{market?:string;ticker:string}[]):SecurityIdentity[] {
  const map=new Map<string,SecurityIdentity>();
  for(const row of rows) if(['CN','HK','US'].includes(row.market||'')) {
    const item={market:row.market as SecurityIdentity['market'],ticker:canonicalTicker(row.market!,row.ticker)};map.set(scoreKey(item),item);
  }
  return [...map.values()];
}

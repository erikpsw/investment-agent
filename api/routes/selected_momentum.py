"""Selected policy snapshot and explicit-input, non-executing scenarios."""
import json
from typing import Literal
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo
import re
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from investment.data.selected_momentum import entry_size, holding_action
from investment.data.live_decision_quote import parse_quote

router=APIRouter()
REPORT=Path(__file__).resolve().parents[1]/'research_reports/momentum-selected.json'


@router.get('/strategy/live-quote/{ticker}')
def live_quote(ticker:str):
    if not re.fullmatch(r'(?:sh(?:60|68)\d{4}|sz(?:00|30)\d{4})',ticker):raise HTTPException(422,'不支持的A股代码')
    try:
        response=requests.get('https://qt.gtimg.cn/q='+ticker,timeout=8,verify=True)
        response.raise_for_status();response.encoding='gb18030'
        return parse_quote(response.text,ticker)
    except Exception as exc:raise HTTPException(503,'未取得可验证的原始行情，请稍后重试') from exc


@router.get('/strategy/momentum-selected')
def selected_policy(scope:Literal['mainboard','reference793']='reference793',ticker:str|None=None):
    path=REPORT if scope=='reference793' else REPORT.with_name('momentum-mainboard.json')
    if not path.exists():raise HTTPException(503,'主板数据尚未通过完整性校验')
    report=json.loads(path.read_text(encoding='utf-8'))
    report['scope']=scope
    ranking=report.pop('_rankings',report['candidates'])
    report['selected_rank']=next((r for r in ranking if r['ticker']==ticker),None) if ticker else None
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date()
    market_age=(today-date.fromisoformat(report['market']['as_of'])).days
    signal_age=(today-date.fromisoformat(report['signal_as_of'])).days
    fresh=0<=market_age<=3 and 0<=signal_age<=7
    report['snapshot_fresh']=fresh
    report['allow_new_by_snapshot']=bool(fresh and report['market']['allow_open'])
    report['freshness_note']='按日历天保守检查；过期时禁止据此开新仓，节假日也不放宽。'
    return report


class SizeRequest(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
    equity:float=Field(gt=0,le=1e12)
    cash:float=Field(ge=0,le=1e12)
    native_price:float=Field(gt=0,le=1e7)


@router.post('/strategy/momentum-selected/size')
def size_scenario(request:SizeRequest):
    if request.cash>request.equity:raise HTTPException(422,'现金不能大于所填策略权益')
    return entry_size(request.equity,request.cash,request.native_price)


class HoldingRequest(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
    entry_price:float=Field(gt=0)
    native_price:float|None=None
    quote_verified:bool=False
    elapsed_sessions:int|None=Field(default=None,ge=0)
    entered_today:bool=False


@router.post('/strategy/momentum-selected/holding-check')
def check_holding(request:HoldingRequest):
    return holding_action(**request.model_dump())

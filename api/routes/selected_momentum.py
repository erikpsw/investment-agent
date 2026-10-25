"""Selected policy snapshot and explicit-input, non-executing scenarios."""
import json
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from investment.data.selected_momentum import entry_size, holding_action

router=APIRouter()
REPORT=Path(__file__).resolve().parents[1]/'research_reports/momentum-selected.json'


@router.get('/strategy/momentum-selected')
def selected_policy():
    report=json.loads(REPORT.read_text(encoding='utf-8'))
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

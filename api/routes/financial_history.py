"""财务历史数据 API - 用于可视化"""
import json
import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import asyncio
import akshare as ak
import pandas as pd
from datetime import datetime

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=2)

CACHE_DIR = Path(__file__).parent.parent.parent / "storage" / "financial_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class FinancialHistoryItem(BaseModel):
    period: str
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_profit: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    net_assets: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    eps: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None


class FinancialHistoryResponse(BaseModel):
    ticker: str
    name: Optional[str] = None
    data: List[FinancialHistoryItem]
    updated_at: Optional[str] = None


def _get_cache_path(ticker: str) -> Path:
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    return CACHE_DIR / f"{code}_financial_history.json"


def _load_cache(ticker: str) -> Optional[dict]:
    cache_path = _get_cache_path(ticker)
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                updated = data.get("updated_at", "")
                if updated:
                    updated_date = datetime.fromisoformat(updated)
                    if (datetime.now() - updated_date).days < 1:
                        return data
        except Exception:
            pass
    return None


def _save_cache(ticker: str, data: dict):
    cache_path = _get_cache_path(ticker)
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _fetch_financial_history(ticker: str) -> dict:
    """获取财务历史数据"""
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    
    result = {
        "ticker": ticker,
        "name": None,
        "data": [],
        "updated_at": datetime.now().isoformat(),
    }
    
    try:
        df = ak.stock_financial_abstract_ths(symbol=code)
        if df is None or df.empty:
            return result
        
        df = df.sort_values("报告期", ascending=True)
        
        def parse_value(val):
            if val is None or pd.isna(val) or val == "False" or val == False:
                return None
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                val_str = val.strip()
                multiplier = 1
                if "亿" in val_str:
                    multiplier = 100000000
                    val_str = val_str.replace("亿", "")
                elif "万" in val_str:
                    multiplier = 10000
                    val_str = val_str.replace("万", "")
                val_str = val_str.replace(",", "").replace("%", "").strip()
                try:
                    return float(val_str) * multiplier
                except:
                    return None
            return None
        
        def parse_percent(val):
            v = parse_value(val)
            if v is not None:
                if v > 1 or v < -1:
                    return v / 100
            return v
        
        for _, row in df.iterrows():
            period = str(row.get("报告期", ""))
            if not period:
                continue
                
            item = {
                "period": period,
                "revenue": parse_value(row.get("营业总收入")),
                "net_profit": parse_value(row.get("净利润")),
                "gross_profit": parse_value(row.get("毛利润")),
                "operating_profit": parse_value(row.get("营业利润")),
                "total_assets": parse_value(row.get("总资产")),
                "total_liabilities": parse_value(row.get("总负债")),
                "net_assets": parse_value(row.get("净资产")),
                "operating_cash_flow": parse_value(row.get("经营活动产生的现金流量净额")),
                "eps": parse_value(row.get("基本每股收益")),
                "roe": parse_percent(row.get("净资产收益率")),
                "gross_margin": parse_percent(row.get("销售毛利率")),
                "net_margin": parse_percent(row.get("销售净利率")),
            }
            result["data"].append(item)
        
        try:
            info_df = ak.stock_individual_info_em(symbol=code)
            for _, r in info_df.iterrows():
                if r["item"] == "股票简称":
                    result["name"] = r["value"]
                    break
        except:
            pass
            
    except Exception as e:
        print(f"Error fetching financial history for {ticker}: {e}")
    
    return result


@router.get("/financial-history/{ticker}", response_model=FinancialHistoryResponse)
async def get_financial_history(ticker: str, refresh: bool = False):
    """获取财务历史数据，用于图表可视化"""
    if not refresh:
        cached = _load_cache(ticker)
        if cached:
            return FinancialHistoryResponse(**cached)
    
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(executor, _fetch_financial_history, ticker)
        _save_cache(ticker, data)
        return FinancialHistoryResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/financial-history/{ticker}/income")
async def get_income_history(ticker: str):
    """获取利润表历史数据"""
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    
    loop = asyncio.get_event_loop()
    
    def fetch():
        try:
            df = ak.stock_profit_sheet_by_report_em(symbol=code)
            if df is None or df.empty:
                return {"data": []}
            
            df = df.head(20)
            records = df.to_dict(orient="records")
            return {"data": records}
        except Exception as e:
            return {"error": str(e)}
    
    result = await loop.run_in_executor(executor, fetch)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/financial-history/{ticker}/balance")
async def get_balance_history(ticker: str):
    """获取资产负债表历史数据"""
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    
    loop = asyncio.get_event_loop()
    
    def fetch():
        try:
            df = ak.stock_balance_sheet_by_report_em(symbol=code)
            if df is None or df.empty:
                return {"data": []}
            
            df = df.head(20)
            records = df.to_dict(orient="records")
            return {"data": records}
        except Exception as e:
            return {"error": str(e)}
    
    result = await loop.run_in_executor(executor, fetch)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

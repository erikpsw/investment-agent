"""财务历史数据 API - 用于可视化"""
import json
import os
import time
import traceback
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import asyncio
import akshare as ak
import pandas as pd
from datetime import datetime

# 美股数据客户端
try:
    from investment.data import YFinanceClient
    _yfinance_client = YFinanceClient()
except ImportError:
    _yfinance_client = None
    print("[Warning] YFinanceClient not available, US stock financial history will be limited")

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


def _load_cache(ticker: str, max_age_days: int = 1) -> Optional[dict]:
    cache_path = _get_cache_path(ticker)
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                updated = data.get("updated_at", "")
                if updated:
                    updated_date = datetime.fromisoformat(updated)
                    # 美股使用更长的缓存时间（7天），因为 yfinance 容易被限流
                    if _is_us_stock(ticker):
                        max_age_days = 7
                    if (datetime.now() - updated_date).days < max_age_days:
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


def _is_hk_stock(ticker: str) -> bool:
    """判断是否为港股"""
    return ticker.lower().startswith("hk") or ticker.endswith(".HK")


def _is_us_stock(ticker: str) -> bool:
    """判断是否为美股"""
    ticker_upper = ticker.upper()
    if ticker_upper.startswith(("SH", "SZ", "HK")):
        return False
    if ticker.replace(".", "").isdigit():
        return False
    return True


def _fetch_hk_financial_history(ticker: str) -> dict:
    """获取港股财务历史数据"""
    code = ticker.lower().replace("hk", "").replace(".hk", "").zfill(5)
    
    result = {
        "ticker": ticker,
        "name": None,
        "data": [],
        "updated_at": datetime.now().isoformat(),
    }
    
    try:
        # 使用港股财务分析指标
        df = ak.stock_financial_hk_analysis_indicator_em(symbol=code)
        if df is None or df.empty:
            return result
        
        # 只取最近8期（约2年）
        df = df.head(8)
        
        # 获取公司名称
        try:
            result["name"] = df.iloc[0].get("SECURITY_NAME_ABBR", "")
        except:
            pass
        
        def safe_float(val):
            if val is None or pd.isna(val):
                return None
            try:
                return float(val)
            except:
                return None
        
        for _, row in df.iterrows():
            report_date = row.get("REPORT_DATE", "")
            if hasattr(report_date, "strftime"):
                report_date = report_date.strftime("%Y-%m-%d")
            else:
                report_date = str(report_date)[:10]
            
            item = {
                "period": report_date,
                "revenue": safe_float(row.get("OPERATE_INCOME")),
                "net_profit": safe_float(row.get("HOLDER_PROFIT")),
                "gross_profit": safe_float(row.get("GROSS_PROFIT")),
                "operating_profit": None,
                "total_assets": None,
                "total_liabilities": None,
                "net_assets": None,
                "operating_cash_flow": None,
                "eps": safe_float(row.get("BASIC_EPS")),
                "roe": safe_float(row.get("ROE_AVG")),
                "gross_margin": safe_float(row.get("GROSS_PROFIT_RATIO")),
                "net_margin": safe_float(row.get("NET_PROFIT_RATIO")),
            }
            
            # 转换百分比 (数据是百分比数值如 56.21，需要转成 0.5621)
            for key in ["roe", "gross_margin", "net_margin"]:
                if item[key] is not None and abs(item[key]) > 1:
                    item[key] = item[key] / 100
            
            result["data"].append(item)
        
        # 按日期排序
        result["data"].sort(key=lambda x: x["period"])
        
    except Exception as e:
        print(f"Error fetching HK financial history for {ticker}: {e}")
    
    return result


def _fetch_us_financial_history(ticker: str) -> dict:
    """获取美股财务历史数据，使用 yfinance 直接获取"""
    import yfinance as yf
    
    result = {
        "ticker": ticker,
        "name": None,
        "data": [],
        "updated_at": datetime.now().isoformat(),
    }
    
    def safe_get(df, col, *keys):
        """安全获取 DataFrame 中的值"""
        if df is None:
            return None
        for key in keys:
            if key in df.index:
                try:
                    val = df.loc[key, col]
                    if pd.notna(val):
                        return float(val)
                except:
                    pass
        return None
    
    try:
        print(f"[US Financial] Fetching data for {ticker}")
        stock = yf.Ticker(ticker.upper())
        
        # 获取基本信息
        try:
            info = stock.info
            result["name"] = info.get("shortName") or info.get("longName") or ticker
        except:
            result["name"] = ticker
        print(f"[US Financial] Got name: {result['name']}")
        
        # 等待一下以避免限流
        time.sleep(0.5)
        
        # 获取财务报表（直接使用 yfinance，绕过缓存）
        income_df = None
        balance_df = None
        
        try:
            income_df = stock.quarterly_financials
            balance_df = stock.quarterly_balance_sheet
            print(f"[US Financial] Got quarterly data")
        except Exception as e:
            print(f"[US Financial] Failed to get quarterly data: {e}")
        
        # 如果季度数据为空，使用年度数据
        if income_df is None or (hasattr(income_df, 'empty') and income_df.empty):
            try:
                income_df = stock.financials
                balance_df = stock.balance_sheet
                print(f"[US Financial] Using annual data instead")
            except Exception as e:
                print(f"[US Financial] Failed to get annual data: {e}")
        
        if income_df is None or (hasattr(income_df, 'empty') and income_df.empty):
            print(f"[US Financial] No income statement data")
            return result
        
        print(f"[US Financial] Income data shape: {income_df.shape}, columns: {list(income_df.columns)[:4]}")
        
        # 遍历最近的财务期间
        for col in income_df.columns[:8]:
            period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
            
            revenue = safe_get(income_df, col, "Total Revenue", "Revenue")
            net_profit = safe_get(income_df, col, "Net Income", "Net Income Common Stockholders")
            gross_profit = safe_get(income_df, col, "Gross Profit")
            operating_profit = safe_get(income_df, col, "Operating Income", "EBIT")
            total_assets = safe_get(balance_df, col, "Total Assets") if balance_df is not None else None
            total_liab = safe_get(balance_df, col, "Total Liabilities Net Minority Interest", "Total Liabilities") if balance_df is not None else None
            net_assets = safe_get(balance_df, col, "Total Stockholder Equity", "Stockholders Equity") if balance_df is not None else None
            
            gross_margin = (gross_profit / revenue) if revenue and gross_profit else None
            net_margin = (net_profit / revenue) if revenue and net_profit else None
            roe = (net_profit / net_assets) if net_profit and net_assets else None
            
            item = {
                "period": period,
                "revenue": revenue,
                "net_profit": net_profit,
                "gross_profit": gross_profit,
                "operating_profit": operating_profit,
                "total_assets": total_assets,
                "total_liabilities": total_liab,
                "net_assets": net_assets,
                "operating_cash_flow": None,
                "eps": None,
                "roe": roe,
                "gross_margin": gross_margin,
                "net_margin": net_margin,
            }
            result["data"].append(item)
        
        # 按日期排序（从早到晚）
        result["data"].sort(key=lambda x: x["period"])
        
    except Exception as e:
        print(f"[US Financial] Error fetching data for {ticker}: {e}")
        traceback.print_exc()
        
        # 如果获取财务数据失败，尝试使用 info 数据作为单期数据
        if not result["data"]:
            try:
                print(f"[US Financial] Trying info fallback for {ticker}")
                stock = yf.Ticker(ticker.upper())
                info = stock.info
                if info:
                    today = datetime.now().strftime("%Y-%m-%d")
                    item = {
                        "period": today,
                        "revenue": info.get("totalRevenue"),
                        "net_profit": info.get("netIncomeToCommon"),
                        "gross_profit": info.get("grossProfits"),
                        "operating_profit": info.get("operatingIncome"),
                        "total_assets": info.get("totalAssets"),
                        "total_liabilities": info.get("totalDebt"),
                        "net_assets": info.get("totalStockholderEquity"),
                        "operating_cash_flow": info.get("operatingCashflow"),
                        "eps": info.get("trailingEps"),
                        "roe": info.get("returnOnEquity"),
                        "gross_margin": info.get("grossMargins"),
                        "net_margin": info.get("profitMargins"),
                    }
                    # 只有当有实际数据时才添加
                    if item["revenue"] or item["net_profit"]:
                        result["data"].append(item)
                        print(f"[US Financial] Added info as fallback data")
            except Exception as e2:
                print(f"[US Financial] Info fallback failed: {e2}")
    
    print(f"[US Financial] Final result: name={result['name']}, data_count={len(result['data'])}")
    return result


def _fetch_financial_history(ticker: str) -> dict:
    """获取财务历史数据"""
    # 根据市场类型分发
    if _is_hk_stock(ticker):
        return _fetch_hk_financial_history(ticker)
    elif _is_us_stock(ticker):
        return _fetch_us_financial_history(ticker)
    
    # A股处理
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
        
        df = df.sort_values("报告期", ascending=False)
        df = df.head(8)  # 只取最近8期（约2年）
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
            
            df = df.head(8)  # 只取最近8期（约2年）
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
            
            df = df.head(8)  # 只取最近8期（约2年）
            records = df.to_dict(orient="records")
            return {"data": records}
        except Exception as e:
            return {"error": str(e)}
    
    result = await loop.run_in_executor(executor, fetch)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

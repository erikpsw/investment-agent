"""Domestic futures quote and daily-history endpoints."""

import asyncio

from fastapi import APIRouter, HTTPException, Query

from investment.data.futures_client import FuturesClient

router = APIRouter()
client = FuturesClient()


@router.get("/futures/search")
async def search_futures(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=50)):
    results = await asyncio.to_thread(client.search, q, limit)
    return {"query": q, "total": len(results), "results": results}


@router.get("/futures/quote/{ticker}")
async def get_futures_quote(ticker: str):
    try:
        quote = await asyncio.to_thread(client.get_quote, ticker)
        if "error" in quote:
            raise HTTPException(status_code=404, detail=quote["error"])
        return quote
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"期货行情数据源不可用: {exc}") from exc


@router.get("/futures/history/{ticker}")
async def get_futures_history(ticker: str, period: str = Query("3mo", pattern="^(1d|5d|1mo|3mo|6mo|1y)$")):
    try:
        frame = await asyncio.to_thread(client.get_history, ticker, period)
        if frame.empty:
            raise HTTPException(status_code=404, detail="未找到期货历史行情")
        bars = [
            {
                "time": index.strftime("%Y-%m-%d"),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0)),
                "open_interest": float(row.get("hold", 0)),
            }
            for index, row in frame.iterrows()
        ]
        return {"ticker": ticker.upper(), "period": period, "interval": "1d", "bars": bars}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"期货历史数据源不可用: {exc}") from exc

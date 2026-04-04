"""
Historical Data API Routes
"""
from fastapi import APIRouter, HTTPException, Query

from investment.data import StockFetcher
from investment.api.schemas import HistoryResponse, HistoryBar

router = APIRouter()
fetcher = StockFetcher()


@router.get("/history/{ticker}", response_model=HistoryResponse)
async def get_history(
    ticker: str,
    period: str = Query("1mo", description="Period: 1d, 5d, 1mo, 3mo, 6mo, 1y"),
    interval: str = Query("1d", description="Interval: 1m, 5m, 15m, 60m, 1d, 1wk"),
):
    """Get historical price data for a stock"""
    try:
        df = fetcher.get_history(ticker, period=period, interval=interval)
        
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="No historical data available")
        
        bars = []
        for idx, row in df.iterrows():
            time_str = str(idx)
            if hasattr(idx, 'strftime'):
                time_str = idx.strftime("%Y-%m-%d")
            
            bars.append(HistoryBar(
                time=time_str,
                open=float(row.get("open", 0)),
                high=float(row.get("high", 0)),
                low=float(row.get("low", 0)),
                close=float(row.get("close", 0)),
                volume=float(row.get("volume", 0)),
            ))
        
        return HistoryResponse(
            ticker=ticker,
            period=period,
            interval=interval,
            bars=bars,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            
            # Handle both lowercase and capitalized column names
            open_val = row.get("Open") or row.get("open") or 0
            high_val = row.get("High") or row.get("high") or 0
            low_val = row.get("Low") or row.get("low") or 0
            close_val = row.get("Close") or row.get("close") or 0
            volume_val = row.get("Volume") or row.get("volume") or 0
            
            bars.append(HistoryBar(
                time=time_str,
                open=float(open_val),
                high=float(high_val),
                low=float(low_val),
                close=float(close_val),
                volume=float(volume_val),
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

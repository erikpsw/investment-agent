"""
Stock Quotes API Routes
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime

from investment.data import StockFetcher
from investment.api.schemas import StockQuote, MarketOverview, MarketIndex

router = APIRouter()
fetcher = StockFetcher()


@router.get("/quote/{ticker}", response_model=StockQuote)
async def get_quote(ticker: str):
    """Get real-time quote for a stock"""
    try:
        quote = fetcher.get_quote(ticker)
        
        if "error" in quote:
            raise HTTPException(status_code=404, detail=quote["error"])
        
        return StockQuote(
            ticker=quote.get("ticker", ticker),
            name=quote.get("name"),
            price=quote.get("price"),
            prev_close=quote.get("prev_close"),
            open=quote.get("open"),
            high=quote.get("high"),
            low=quote.get("low"),
            volume=quote.get("volume"),
            amount=quote.get("amount"),
            change=quote.get("change"),
            change_percent=quote.get("change_percent"),
            pe_ratio=quote.get("pe_ratio"),
            market_cap=quote.get("market_cap"),
            timestamp=quote.get("timestamp", datetime.now().isoformat()),
            market=_detect_market(ticker),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quote/by-name/{name}", response_model=StockQuote)
async def get_quote_by_name(name: str):
    """Get quote by company name (supports Chinese names)"""
    try:
        quote = fetcher.get_quote_by_name(name)
        
        if "error" in quote:
            raise HTTPException(status_code=404, detail=quote["error"])
        
        resolved = quote.get("_resolved", {})
        ticker = resolved.get("code", name)
        
        return StockQuote(
            ticker=ticker,
            name=quote.get("name") or resolved.get("name"),
            price=quote.get("price"),
            prev_close=quote.get("prev_close"),
            open=quote.get("open"),
            high=quote.get("high"),
            low=quote.get("low"),
            volume=quote.get("volume"),
            amount=quote.get("amount"),
            change=quote.get("change"),
            change_percent=quote.get("change_percent"),
            pe_ratio=quote.get("pe_ratio"),
            market_cap=quote.get("market_cap"),
            timestamp=quote.get("timestamp", datetime.now().isoformat()),
            market=resolved.get("market", _detect_market(ticker)),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/overview", response_model=MarketOverview)
async def get_market_overview():
    """Get market indices overview"""
    try:
        overview = fetcher.get_market_overview()
        indices = overview.get("indices", [])
        
        return MarketOverview(
            indices=[
                MarketIndex(
                    code=idx.get("code", ""),
                    name=idx.get("name", ""),
                    price=idx.get("price"),
                    change=idx.get("change"),
                    change_percent=idx.get("change_percent"),
                )
                for idx in indices
            ],
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _detect_market(ticker: str) -> str:
    """Detect market from ticker"""
    ticker_lower = ticker.lower()
    if ticker_lower.startswith(("sh", "sz")):
        return "CN"
    elif ticker_lower.startswith("hk"):
        return "HK"
    elif ticker_lower.isdigit():
        return "CN"
    else:
        return "US"

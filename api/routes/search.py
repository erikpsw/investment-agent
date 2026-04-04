"""
Stock Search API Routes
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Query

from investment.data import StockFetcher
from investment.api.schemas import SearchResponse, SearchResult

router = APIRouter()
fetcher = StockFetcher()
executor = ThreadPoolExecutor(max_workers=4)


@router.get("/search", response_model=SearchResponse)
async def search_stocks(
    q: str = Query(..., min_length=1, description="Search query (name or code)"),
    market: str = Query("all", description="Market filter: all, cn, hk, us"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """Search stocks by name or code"""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        executor, lambda: fetcher.search(q, market=market, limit=limit)
    )
    
    return SearchResponse(
        results=[
            SearchResult(
                code=r.get("code", ""),
                name=r.get("name", ""),
                market=r.get("market", ""),
                display=r.get("display", ""),
                exchange=r.get("exchange"),
            )
            for r in results
        ],
        query=q,
        total=len(results),
    )


@router.get("/resolve")
async def resolve_stock(q: str = Query(..., min_length=1)):
    """Resolve user input to stock ticker"""
    loop = asyncio.get_event_loop()
    resolved = await loop.run_in_executor(executor, lambda: fetcher.resolve_input(q))
    return resolved

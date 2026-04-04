"""
Stock Search API Routes
优先使用 Supabase 搜索（更快），如果未配置则使用本地搜索
"""
import asyncio
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Query

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from investment.data import StockFetcher
from investment.api.schemas import SearchResponse, SearchResult

router = APIRouter()
fetcher = StockFetcher()
executor = ThreadPoolExecutor(max_workers=4)

# 检查是否配置了 Supabase
_use_supabase = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))
_supabase_searcher = None

if _use_supabase:
    try:
        from investment.data.supabase_search import get_supabase_searcher
        _supabase_searcher = get_supabase_searcher()
        print("[Search] Using Supabase for stock search (faster)")
    except Exception as e:
        print(f"[Search] Failed to initialize Supabase searcher: {e}")
        _use_supabase = False
else:
    print("[Search] Supabase not configured, using local search")


@router.get("/search", response_model=SearchResponse)
async def search_stocks(
    q: str = Query(..., min_length=1, description="Search query (name or code)"),
    market: str = Query("all", description="Market filter: all, cn, hk, us"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """Search stocks by name or code
    
    优先使用 Supabase PostgreSQL 搜索（如果配置了），否则使用本地 pandas 搜索
    """
    loop = asyncio.get_event_loop()
    
    if _supabase_searcher:
        # 使用 Supabase 搜索（更快）
        results = await loop.run_in_executor(
            executor, lambda: _supabase_searcher.search(q, market=market, limit=limit)
        )
    else:
        # 使用本地搜索
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
    
    if _supabase_searcher:
        resolved = await loop.run_in_executor(
            executor, lambda: _supabase_searcher.resolve(q)
        )
    else:
        resolved = await loop.run_in_executor(
            executor, lambda: fetcher.resolve_input(q)
        )
    
    return resolved

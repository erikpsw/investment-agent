"""
Lightweight FastAPI entrypoint for Vercel.

This intentionally mounts only the routes that are suitable for Vercel Python
Functions. Heavy PDF/RAG/Playwright/long-running agent routes remain available
through the local/full backend entrypoint in api/main.py.
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

if os.getenv("SUPABASE_KEY") and not os.getenv("SUPABASE_ANON_KEY"):
    os.environ["SUPABASE_ANON_KEY"] = os.environ["SUPABASE_KEY"]

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from investment.api.routes import (
    disclosure,
    etfs,
    financial_history,
    financials,
    foreign_reports,
    futures,
    formula_ranking,
    history,
    hot_stocks,
    news,
    portfolio,
    quotes,
    search,
    sectors,
    tokens,
    watchlists,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"):
        print("[Startup] Using Supabase for search")
    else:
        print("[Startup] Supabase is not configured; local CSV search fallback is enabled")
    yield


app = FastAPI(
    title="Investment Agent API (Vercel Lite)",
    description="Lightweight market data API for Vercel deployment",
    version="1.0.0",
    lifespan=lifespan,
)

frontend_origin = os.getenv("FRONTEND_ORIGIN")
allow_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if frontend_origin:
    allow_origins.append(frontend_origin.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(quotes.router, prefix="/api", tags=["quotes"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(history.router, prefix="/api", tags=["history"])
app.include_router(futures.router, prefix="/api", tags=["futures"])
app.include_router(hot_stocks.router, prefix="/api", tags=["hot-stocks"])
app.include_router(financials.router, prefix="/api", tags=["financials"])
app.include_router(financial_history.router, prefix="/api", tags=["financial-history"])
app.include_router(news.router, prefix="/api", tags=["news"])
app.include_router(portfolio.router, prefix="/api", tags=["portfolio"])
app.include_router(tokens.router, prefix="/api", tags=["tokens"])
app.include_router(watchlists.router, prefix="/api", tags=["watchlists"])
app.include_router(sectors.router, prefix="/api", tags=["sectors"])
app.include_router(formula_ranking.router, prefix="/api", tags=["formula-ranking"])
from investment.api.routes import ai_screener
app.include_router(ai_screener.router, prefix="/api", tags=["ai-screener"])
app.include_router(disclosure.router, prefix="/api", tags=["disclosure"])
app.include_router(etfs.router, prefix="/api", tags=["etfs"])

# Listing disclosures is lightweight; keep document download routes local.
foreign_disclosures = APIRouter()
foreign_disclosures.add_api_route("/us/filings/{ticker}", foreign_reports.get_us_filings, methods=["GET"], response_model=foreign_reports.FilingsResponse)
foreign_disclosures.add_api_route("/hk/announcements/{ticker}", foreign_reports.get_hk_announcements, methods=["GET"], response_model=foreign_reports.FilingsResponse)
app.include_router(foreign_disclosures, prefix="/api/foreign", tags=["foreign-reports"])


@app.get("/")
async def root():
    return {"message": "Investment Agent API", "mode": "vercel-lite", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok", "mode": "vercel-lite"}

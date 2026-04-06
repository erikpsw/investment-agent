"""
Investment Agent FastAPI Backend
"""
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 加载 .env 文件（在其他导入之前）
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[Startup] Loaded .env from {env_path}")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from investment.api.routes import quotes, search, history, financials, analysis, reports, financial_history, report_analysis, pdf_analysis, news, foreign_reports, disclosure


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload search data on startup"""
    # 检查是否使用 Supabase（如果配置了就不用预加载本地数据）
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"):
        print("[Startup] Using Supabase for search, skipping local preload")
    else:
        print("Preloading stock search data...")
        from investment.data.stock_search import get_stock_search
        searcher = get_stock_search()
        searcher._load_data()
        print(f"Loaded {len(searcher._stocks) if searcher._stocks is not None else 0} stocks")
    yield


app = FastAPI(
    title="Investment Agent API",
    description="A股/港股/美股行情数据 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(quotes.router, prefix="/api", tags=["quotes"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(history.router, prefix="/api", tags=["history"])
app.include_router(financials.router, prefix="/api", tags=["financials"])
app.include_router(analysis.router, prefix="/api", tags=["analysis"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
app.include_router(financial_history.router, prefix="/api", tags=["financial-history"])
app.include_router(report_analysis.router, prefix="/api", tags=["report-analysis"])
app.include_router(pdf_analysis.router, prefix="/api", tags=["pdf-analysis"])
app.include_router(news.router, prefix="/api", tags=["news"])
app.include_router(foreign_reports.router, prefix="/api/foreign", tags=["foreign-reports"])
app.include_router(disclosure.router, prefix="/api", tags=["disclosure"])


@app.get("/")
async def root():
    return {"message": "Investment Agent API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}

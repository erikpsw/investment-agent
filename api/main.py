"""
Investment Agent FastAPI Backend
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from investment.api.routes import quotes, search, history, financials, analysis, reports, financial_history, report_analysis, pdf_analysis
from investment.data.stock_search import get_stock_search


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload search data on startup"""
    print("Preloading stock search data...")
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


@app.get("/")
async def root():
    return {"message": "Investment Agent API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}

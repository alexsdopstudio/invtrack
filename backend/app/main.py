from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import scheduler
from .analysis.report import analysis_enabled
from .config import get_settings
from .routers import alerts, analysis, ideas, ingest, scores, screener, tickers, watchlist

DISCLAIMER = (
    "InvTrack is a personal research aid, not financial advice. It never issues "
    "buy/sell recommendations. Congressional trading disclosures are legally "
    "delayed by up to 45 days (STOCK Act) and all signals are lagging; verify "
    "important signals against the official sources (efdsearch.senate.gov, "
    "disclosures-clerk.house.gov, sec.gov) before acting on them."
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="InvTrack", description=DISCLAIMER, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(watchlist.router)
app.include_router(alerts.router)
app.include_router(ideas.router)
app.include_router(screener.router)
app.include_router(analysis.router)
app.include_router(tickers.router)
app.include_router(scores.router)
app.include_router(ingest.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "disclaimer": DISCLAIMER,
        "ai_analysis_enabled": analysis_enabled(),
        "auto_refresh_enabled": get_settings().auto_refresh_enabled,
        "next_auto_refresh": scheduler.next_run_time(),
    }

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    DimTicker,
    FactCongressTrade,
    FactFundamentals,
    FactInsiderTrade,
    FactPrice,
    WatchlistItem,
)
from ..queries import latest_score_for, price_stats, score_history
from ..risk import risk_flags
from ..schemas import (
    CongressTradeOut,
    FundamentalsOut,
    InsiderTradeOut,
    PricePoint,
    PriceStats,
    RiskFlag,
    ScoreHistoryEntry,
    ScoreOut,
    TickerDetail,
    TickerSearchResult,
)

router = APIRouter(prefix="/api/tickers", tags=["tickers"])


@router.get("/search", response_model=list[TickerSearchResult])
def search(q: str = Query(min_length=1, max_length=64), db: Session = Depends(get_db)):
    term = q.strip().upper()
    exact_first = case((DimTicker.ticker == term, 0), else_=1)
    stmt = (
        select(DimTicker, WatchlistItem.id.is_not(None).label("on_watchlist"))
        .outerjoin(WatchlistItem, WatchlistItem.ticker == DimTicker.ticker)
        .where(
            DimTicker.ticker.like(f"{term}%")
            | func.upper(DimTicker.name).like(f"%{term}%")
        )
        .order_by(exact_first, func.length(DimTicker.ticker), DimTicker.ticker)
        .limit(20)
    )
    return [
        TickerSearchResult(
            ticker=t.ticker, name=t.name, cik=t.cik, on_watchlist=bool(on_wl)
        )
        for t, on_wl in db.execute(stmt)
    ]


def _get_ticker(db: Session, ticker: str) -> DimTicker:
    dim = db.get(DimTicker, ticker.strip().upper())
    if dim is None:
        raise HTTPException(404, f"unknown ticker {ticker}")
    return dim


@router.get("/{ticker}", response_model=TickerDetail)
def detail(ticker: str, db: Session = Depends(get_db)):
    dim = _get_ticker(db, ticker)
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.ticker == dim.ticker))
    fundamentals = db.scalar(
        select(FactFundamentals)
        .where(FactFundamentals.ticker == dim.ticker)
        .order_by(FactFundamentals.as_of.desc())
        .limit(1)
    )
    score = latest_score_for(db, dim.ticker)
    return TickerDetail(
        ticker=dim.ticker,
        name=dim.name,
        sector=dim.sector,
        cik=dim.cik,
        on_watchlist=item is not None,
        notes=item.notes if item else None,
        fundamentals=fundamentals,
        score=ScoreOut(
            ticker=dim.ticker,
            total=score.total if score else None,
            computed_at=score.computed_at if score else None,
            components=score.components if score else None,
        ),
    )


@router.get("/{ticker}/congress-trades", response_model=list[CongressTradeOut])
def congress_trades(ticker: str, limit: int = 100, db: Session = Depends(get_db)):
    dim = _get_ticker(db, ticker)
    return db.scalars(
        select(FactCongressTrade)
        .where(FactCongressTrade.ticker == dim.ticker)
        .order_by(FactCongressTrade.transaction_date.desc())
        .limit(limit)
    ).all()


@router.get("/{ticker}/insider-trades", response_model=list[InsiderTradeOut])
def insider_trades(ticker: str, limit: int = 100, db: Session = Depends(get_db)):
    dim = _get_ticker(db, ticker)
    return db.scalars(
        select(FactInsiderTrade)
        .where(FactInsiderTrade.ticker == dim.ticker)
        .order_by(FactInsiderTrade.transaction_date.desc())
        .limit(limit)
    ).all()


@router.get("/{ticker}/stats", response_model=PriceStats)
def stats(ticker: str, db: Session = Depends(get_db)):
    dim = _get_ticker(db, ticker)
    result = price_stats(db, dim.ticker)
    if result is None:
        raise HTTPException(
            404, f"not enough price history for {dim.ticker} — ingest prices first"
        )
    return result


@router.get("/{ticker}/score-history", response_model=list[ScoreHistoryEntry])
def get_score_history(ticker: str, days: int = 120, db: Session = Depends(get_db)):
    dim = _get_ticker(db, ticker)
    return score_history(db, dim.ticker, days=days)


@router.get("/{ticker}/risks", response_model=list[RiskFlag])
def get_risks(ticker: str, db: Session = Depends(get_db)):
    dim = _get_ticker(db, ticker)
    return risk_flags(db, dim.ticker)


@router.get("/{ticker}/prices", response_model=list[PricePoint])
def prices(ticker: str, days: int = 365, db: Session = Depends(get_db)):
    dim = _get_ticker(db, ticker)
    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(FactPrice.date, FactPrice.close)
        .where(FactPrice.ticker == dim.ticker, FactPrice.date >= since)
        .order_by(FactPrice.date)
    )
    return [PricePoint(date=d, close=c) for d, c in rows]

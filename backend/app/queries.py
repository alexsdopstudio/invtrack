"""CTE-based read-model queries for the dashboard and detail views."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    DimTicker,
    FactCongressTrade,
    FactInsiderTrade,
    FactPrice,
    Score,
    WatchlistItem,
)

SPARKLINE_DAYS = 90


def latest_score_cte():
    ranked = select(
        Score,
        func.row_number()
        .over(partition_by=Score.ticker, order_by=Score.computed_at.desc())
        .label("rn"),
    ).cte("ranked_scores")
    return ranked


def dashboard_rows(db: Session) -> list[dict]:
    ranked_scores = latest_score_cte()

    last_congress = (
        select(
            FactCongressTrade.ticker,
            func.max(FactCongressTrade.transaction_date).label("last_date"),
        )
        .group_by(FactCongressTrade.ticker)
        .cte("last_congress")
    )
    last_insider = (
        select(
            FactInsiderTrade.ticker,
            func.max(FactInsiderTrade.transaction_date).label("last_date"),
        )
        .group_by(FactInsiderTrade.ticker)
        .cte("last_insider")
    )
    last_price = (
        select(
            FactPrice.ticker,
            func.max(FactPrice.date).label("last_date"),
        )
        .group_by(FactPrice.ticker)
        .cte("last_price")
    )

    stmt = (
        select(
            WatchlistItem.ticker,
            WatchlistItem.notes,
            DimTicker.name,
            DimTicker.sector,
            ranked_scores.c.total,
            ranked_scores.c.computed_at,
            ranked_scores.c.components,
            last_congress.c.last_date.label("last_congress_activity"),
            last_insider.c.last_date.label("last_insider_activity"),
            FactPrice.close.label("last_close"),
        )
        .join(DimTicker, DimTicker.ticker == WatchlistItem.ticker)
        .outerjoin(
            ranked_scores,
            (ranked_scores.c.ticker == WatchlistItem.ticker) & (ranked_scores.c.rn == 1),
        )
        .outerjoin(last_congress, last_congress.c.ticker == WatchlistItem.ticker)
        .outerjoin(last_insider, last_insider.c.ticker == WatchlistItem.ticker)
        .outerjoin(last_price, last_price.c.ticker == WatchlistItem.ticker)
        .outerjoin(
            FactPrice,
            (FactPrice.ticker == last_price.c.ticker)
            & (FactPrice.date == last_price.c.last_date),
        )
        .order_by(ranked_scores.c.total.desc().nulls_last(), WatchlistItem.ticker)
    )
    rows = [dict(r._mapping) for r in db.execute(stmt)]

    sparklines = _sparklines(db, [r["ticker"] for r in rows])
    for r in rows:
        r["sparkline"] = sparklines.get(r["ticker"], [])
        r["score"] = r.pop("total")
        r["score_computed_at"] = r.pop("computed_at")
    return rows


def _sparklines(db: Session, tickers: list[str]) -> dict[str, list[float]]:
    if not tickers:
        return {}
    since = date.today() - timedelta(days=SPARKLINE_DAYS)
    stmt = (
        select(FactPrice.ticker, FactPrice.date, FactPrice.close)
        .where(FactPrice.ticker.in_(tickers), FactPrice.date >= since)
        .order_by(FactPrice.ticker, FactPrice.date)
    )
    out: dict[str, list[float]] = {}
    for ticker, _d, close in db.execute(stmt):
        if close is not None:
            out.setdefault(ticker, []).append(round(close, 2))
    return out


def latest_score_for(db: Session, ticker: str) -> Score | None:
    return db.scalar(
        select(Score)
        .where(Score.ticker == ticker)
        .order_by(Score.computed_at.desc())
        .limit(1)
    )

"""yfinance daily OHLCV -> fact_price (1 year of history per watchlist
ticker), idempotent on (ticker, date)."""

import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FactPrice
from . import targets

logger = logging.getLogger(__name__)


def upsert_prices(db: Session, ticker: str, rows: list[dict[str, Any]]) -> int:
    existing = set(
        db.scalars(select(FactPrice.date).where(FactPrice.ticker == ticker))
    )
    count = 0
    for row in rows:
        if row["date"] in existing:
            continue
        db.add(FactPrice(ticker=ticker, **row))
        count += 1
    db.commit()
    return count


def _history_rows(history) -> list[dict[str, Any]]:
    rows = []
    for idx, r in history.iterrows():
        d = idx.date() if hasattr(idx, "date") else idx
        if not isinstance(d, date):
            continue
        rows.append(
            {
                "date": d,
                "open": float(r["Open"]),
                "high": float(r["High"]),
                "low": float(r["Low"]),
                "close": float(r["Close"]),
                "volume": float(r["Volume"]),
            }
        )
    return rows


def ingest(db: Session) -> int:
    import yfinance as yf

    from ..config import get_scoring_config

    # Benchmark closes are needed for excess-return comparisons (track record,
    # politician leaderboard); it is not scored or shown as a holding.
    benchmark = get_scoring_config()["benchmark_ticker"]
    tickers = [*targets.target_tickers(db), benchmark]
    count = 0
    errors = []
    for ticker in tickers:
        try:
            history = yf.Ticker(ticker).history(period="1y", auto_adjust=True)
            count += upsert_prices(db, ticker, _history_rows(history))
        except Exception as exc:  # noqa: BLE001 - per-ticker isolation
            logger.warning("prices failed for %s: %s", ticker, exc)
            errors.append(f"{ticker}: {exc}")
    if errors and count == 0 and tickers:
        raise RuntimeError("; ".join(errors))
    return count

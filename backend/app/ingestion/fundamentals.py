"""yfinance fundamentals snapshot -> fact_fundamentals (one row per ticker per
day). yfinance is unofficial and can break or rate-limit, so each ticker is
isolated: a failure is recorded and the rest continue."""

import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DimTicker, FactFundamentals, utcnow
from . import targets

logger = logging.getLogger(__name__)

# yfinance reports debtToEquity as a percentage (e.g. 154.3 for 1.543x).
_RAW_KEYS = [
    "revenueGrowth",
    "grossMargins",
    "operatingMargins",
    "debtToEquity",
    "trailingPE",
    "forwardPE",
    "marketCap",
    "currentRatio",
    "totalCash",
    "heldPercentInsiders",
    "sector",
    "exchange",
    "shortName",
]


def snapshot_from_info(
    info: dict[str, Any], quarterly_ocf: float | None = None
) -> dict[str, Any]:
    d2e = info.get("debtToEquity")
    return {
        "revenue_growth_yoy": info.get("revenueGrowth"),
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "debt_to_equity": (d2e / 100.0) if isinstance(d2e, (int, float)) else None,
        "pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "market_cap": info.get("marketCap"),
        "current_ratio": info.get("currentRatio"),
        "total_cash": info.get("totalCash"),
        "quarterly_operating_cashflow": quarterly_ocf,
        "insider_ownership_pct": info.get("heldPercentInsiders"),
        "raw": {k: info.get(k) for k in _RAW_KEYS if k in info},
    }


def latest_quarterly_ocf(quarterly_cashflow) -> float | None:
    """Most recent quarter's Operating Cash Flow from a yfinance
    quarterly_cashflow DataFrame (rows = line items, columns = quarters,
    newest first). Negative = cash burn."""
    try:
        if quarterly_cashflow is None or quarterly_cashflow.empty:
            return None
        for label in ("Operating Cash Flow", "Total Cash From Operating Activities"):
            if label in quarterly_cashflow.index:
                series = quarterly_cashflow.loc[label].dropna()
                if len(series) > 0:
                    return float(series.iloc[0])
    except Exception:  # noqa: BLE001 - unofficial source, shapes drift
        return None
    return None


def upsert_snapshot(db: Session, ticker: str, snapshot: dict[str, Any], as_of: date) -> int:
    existing = db.scalar(
        select(FactFundamentals).where(
            FactFundamentals.ticker == ticker, FactFundamentals.as_of == as_of
        )
    )
    if existing is not None:
        for key, value in snapshot.items():
            setattr(existing, key, value)
        existing.ingested_at = utcnow()
        db.commit()
        return 0
    db.add(FactFundamentals(ticker=ticker, as_of=as_of, **snapshot))
    db.commit()
    return 1


def ingest(db: Session) -> int:
    import yfinance as yf

    # Watchlist plus the top congressional-discovery candidates, so Radar
    # tickers get comparable scores.
    tickers = targets.target_tickers(db)
    count = 0
    errors = []
    for ticker in tickers:
        try:
            yft = yf.Ticker(ticker)
            info = yft.info or {}
            snapshot = snapshot_from_info(info, latest_quarterly_ocf(yft.quarterly_cashflow))
            count += upsert_snapshot(db, ticker, snapshot, date.today())
            sector = info.get("sector")
            if sector:
                dim = db.get(DimTicker, ticker)
                if dim is not None and not dim.sector:
                    dim.sector = sector
                    db.commit()
        except Exception as exc:  # noqa: BLE001 - per-ticker isolation
            logger.warning("fundamentals failed for %s: %s", ticker, exc)
            errors.append(f"{ticker}: {exc}")
    if errors and count == 0 and tickers:
        raise RuntimeError("; ".join(errors))
    return count

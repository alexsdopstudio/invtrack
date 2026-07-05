"""Aggressive-growth quantitative screener.

Evaluates each target ticker (watchlist + discovery) against the criteria in
scoring.yaml's `screener:` section. A criterion with missing data reports
status "unknown" — never a silent pass or fail. The LLM is never involved in
these numbers; everything comes from structured sources."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_scoring_config
from .ingestion import targets
from .models import DimTicker, FactFundamentals, FactPrice

VOLUME_WINDOW_DAYS = 90

CRITERIA_ORDER = [
    "market_cap",
    "avg_daily_volume",
    "revenue_growth_yoy",
    "gross_margin",
    "current_ratio",
    "cash_runway_quarters",
    "insider_ownership",
]


def cash_runway_quarters(total_cash: float | None, quarterly_ocf: float | None) -> float | None:
    """Quarters of survival at the current burn rate. Positive operating cash
    flow means no burn — effectively infinite runway."""
    if total_cash is None or quarterly_ocf is None:
        return None
    if quarterly_ocf >= 0:
        return float("inf")
    return total_cash / abs(quarterly_ocf)


def _criterion(value: float | None, *, min_: float | None = None, max_: float | None = None) -> dict[str, Any]:
    threshold: dict[str, float] = {}
    if min_ is not None:
        threshold["min"] = min_
    if max_ is not None:
        threshold["max"] = max_
    if value is None:
        return {"value": None, "threshold": threshold, "status": "unknown"}
    ok = (min_ is None or value >= min_) and (max_ is None or value <= max_)
    display = value if value != float("inf") else None
    return {
        "value": display,
        "threshold": threshold,
        "status": "pass" if ok else "fail",
    }


def _avg_daily_volume(db: Session, ticker: str) -> float | None:
    since = date.today() - timedelta(days=VOLUME_WINDOW_DAYS)
    result = db.scalar(
        select(func.avg(FactPrice.volume)).where(
            FactPrice.ticker == ticker,
            FactPrice.date >= since,
            FactPrice.volume.is_not(None),
        )
    )
    return float(result) if result is not None else None


def evaluate(db: Session, ticker: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = (config or get_scoring_config())["screener"]
    snapshot = db.scalar(
        select(FactFundamentals)
        .where(FactFundamentals.ticker == ticker)
        .order_by(FactFundamentals.as_of.desc())
        .limit(1)
    )

    def snap(attr: str) -> float | None:
        value = getattr(snapshot, attr) if snapshot is not None else None
        return float(value) if value is not None else None

    criteria = {
        "market_cap": _criterion(
            snap("market_cap"), min_=cfg["market_cap"]["min"], max_=cfg["market_cap"]["max"]
        ),
        "avg_daily_volume": _criterion(
            _avg_daily_volume(db, ticker), min_=cfg["avg_daily_volume"]["min"]
        ),
        "revenue_growth_yoy": _criterion(
            snap("revenue_growth_yoy"), min_=cfg["revenue_growth_yoy"]["min"]
        ),
        "gross_margin": _criterion(snap("gross_margin"), min_=cfg["gross_margin"]["min"]),
        "current_ratio": _criterion(snap("current_ratio"), min_=cfg["current_ratio"]["min"]),
        "cash_runway_quarters": _criterion(
            cash_runway_quarters(snap("total_cash"), snap("quarterly_operating_cashflow")),
            min_=cfg["cash_runway_quarters"]["min"],
        ),
        "insider_ownership": _criterion(
            snap("insider_ownership_pct"), min_=cfg["insider_ownership"]["min"]
        ),
    }

    statuses = [criteria[name]["status"] for name in CRITERIA_ORDER]
    return {
        "ticker": ticker,
        "criteria": criteria,
        "passed": statuses.count("pass"),
        "failed": statuses.count("fail"),
        "unknown": statuses.count("unknown"),
        "data_as_of": snapshot.as_of if snapshot is not None else None,
    }


def screen_all(db: Session, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config = config or get_scoring_config()
    rows = [evaluate(db, ticker, config) for ticker in targets.target_tickers(db)]
    names = {
        t.ticker: (t.name, t.sector)
        for t in db.scalars(
            select(DimTicker).where(DimTicker.ticker.in_([r["ticker"] for r in rows]))
        )
    }
    for row in rows:
        name, sector = names.get(row["ticker"], (None, None))
        row["name"] = name
        row["sector"] = sector
    # most passes first; among equals, fewest unknowns (better data coverage)
    rows.sort(key=lambda r: (-r["passed"], r["unknown"], r["ticker"]))
    return rows

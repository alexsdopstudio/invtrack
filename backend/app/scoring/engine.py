"""Composite score engine.

Combines the sub-scores with weights from scoring.yaml. When a component has
no data its weight is renormalized across the components that do — a missing
source never silently drags the score to zero, and the breakdown records the
component as "missing" so the score is always explainable.
"""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_scoring_config
from ..models import Score, WatchlistItem
from . import congress, fundamentals, insider

COMPONENTS = {
    "fundamentals": fundamentals.compute,
    "congress": congress.compute,
    "insider": insider.compute,
}


def compute_breakdown(
    db: Session, ticker: str, config: dict[str, Any] | None = None, today: date | None = None
) -> tuple[float | None, dict[str, Any]]:
    """Returns (total 0-100 or None if no data at all, per-component breakdown)."""
    config = config or get_scoring_config()
    today = today or date.today()
    weights = config["weights"]

    results: dict[str, dict[str, Any] | None] = {
        name: fn(db, ticker, config, today) for name, fn in COMPONENTS.items()
    }
    available = {name: r for name, r in results.items() if r is not None}
    weight_sum = sum(weights[name] for name in available)

    breakdown: dict[str, Any] = {}
    total = 0.0
    for name in COMPONENTS:
        result = results[name]
        if result is None or weight_sum == 0:
            breakdown[name] = {
                "status": "missing",
                "weight": weights[name],
                "normalized_weight": 0.0,
                "contribution": 0.0,
            }
            continue
        normalized = weights[name] / weight_sum
        contribution = normalized * result["score"]
        total += contribution
        breakdown[name] = {
            "status": "ok",
            "score": round(result["score"], 2),
            "weight": weights[name],
            "normalized_weight": round(normalized, 4),
            "contribution": round(contribution, 2),
            "source": result["source"],
            "data_as_of": result["data_as_of"],
            "inputs": result["inputs"],
        }

    if not available:
        return None, breakdown
    return round(total, 2), breakdown


def compute_and_store(db: Session, tickers: list[str] | None = None) -> list[Score]:
    if tickers is None:
        tickers = list(db.scalars(select(WatchlistItem.ticker)))
    stored = []
    for ticker in tickers:
        total, breakdown = compute_breakdown(db, ticker)
        if total is None:
            continue
        score = Score(ticker=ticker, total=total, components=breakdown)
        db.add(score)
        stored.append(score)
    db.commit()
    return stored

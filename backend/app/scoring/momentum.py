"""Momentum/trend sub-score (0-100, 50 = neutral).

Where is the price relative to its own 50- and 200-day moving averages?
Trend confirmation, not prediction: a blend of percent distances from the
MAs, squashed with tanh. Requires a minimum price history; otherwise the
component reports missing and the engine renormalizes the other weights.
"""

import math
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FactPrice


def compute(db: Session, ticker: str, config: dict[str, Any], today: date) -> dict[str, Any] | None:
    cfg = config["momentum"]
    rows = db.execute(
        select(FactPrice.date, FactPrice.close)
        .where(
            FactPrice.ticker == ticker,
            FactPrice.close.is_not(None),
            FactPrice.date <= today,
        )
        .order_by(FactPrice.date.desc())
        .limit(cfg["ma_long"])
    ).all()
    closes = [r.close for r in rows]  # newest first
    if len(closes) < cfg["min_closes"]:
        return None

    close = closes[0]
    ma_short = sum(closes[: cfg["ma_short"]]) / min(len(closes), cfg["ma_short"])
    d_short = (close - ma_short) / ma_short

    ma_long = None
    d_long = None
    if len(closes) >= cfg["ma_long"]:
        ma_long = sum(closes) / len(closes)
        d_long = (close - ma_long) / ma_long
        blend = cfg["short_weight"] * d_short + cfg["long_weight"] * d_long
    else:
        # not enough history for the long MA: score on the short MA alone
        blend = d_short

    score = 50.0 + 50.0 * math.tanh(blend / cfg["distance_scale"])
    return {
        "score": max(0.0, min(100.0, score)),
        "source": "daily closes (yfinance)",
        "data_as_of": rows[0].date.isoformat(),
        "inputs": {
            "close": round(close, 2),
            f"ma_{cfg['ma_short']}": round(ma_short, 2),
            f"ma_{cfg['ma_long']}": round(ma_long, 2) if ma_long is not None else None,
            "pct_vs_short_ma": round(d_short * 100, 2),
            "pct_vs_long_ma": round(d_long * 100, 2) if d_long is not None else None,
            "closes_used": len(closes),
            "note": "trend confirmation, not prediction",
        },
    }

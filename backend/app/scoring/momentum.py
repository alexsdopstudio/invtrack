"""Momentum/trend sub-score (0-100, 50 = neutral).

Two ingredients: (1) where the price sits relative to its own 50/200-day
moving averages, and (2) relative strength — did the stock beat the benchmark
over the last ~quarter? A stock up 5% while the market is up 20% is lagging,
not leading; the MA distance alone can't see that. Both are squashed with
tanh and blended (rs_weight). Requires a minimum price history; missing
benchmark history just drops the RS term (recorded in inputs), never fails
the component.
"""

import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FactPrice


def _window_return(
    db: Session, ticker: str, window_days: int, today: date
) -> float | None:
    """Close-to-close return over the last window_days calendar days."""
    since = today - timedelta(days=window_days)
    rows = db.execute(
        select(FactPrice.date, FactPrice.close)
        .where(
            FactPrice.ticker == ticker,
            FactPrice.close.is_not(None),
            FactPrice.date >= since,
            FactPrice.date <= today,
        )
        .order_by(FactPrice.date)
    ).all()
    if len(rows) < 2 or rows[0].close <= 0:
        return None
    # require coverage of most of the window, not just a few recent closes
    if (rows[-1].date - rows[0].date).days < window_days * 0.6:
        return None
    return rows[-1].close / rows[0].close - 1.0


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

    ma_score = 50.0 + 50.0 * math.tanh(blend / cfg["distance_scale"])

    # Relative strength vs the benchmark: beat-the-market, not just went-up.
    rs_weight = cfg.get("rs_weight", 0.0)
    benchmark = config.get("benchmark_ticker")
    excess = None
    if rs_weight > 0 and benchmark and ticker != benchmark:
        window = cfg.get("rs_window_days", 90)
        stock_r = _window_return(db, ticker, window, today)
        bench_r = _window_return(db, benchmark, window, today)
        if stock_r is not None and bench_r is not None:
            excess = stock_r - bench_r

    if excess is not None:
        rs_score = 50.0 + 50.0 * math.tanh(excess / cfg.get("rs_scale", 0.15))
        score = (1.0 - rs_weight) * ma_score + rs_weight * rs_score
    else:
        score = ma_score  # no benchmark history: MA-only, weight not wasted

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
            "excess_vs_benchmark_pct": round(excess * 100, 2) if excess is not None else None,
            "benchmark": benchmark if excess is not None else None,
            "note": "trend confirmation, not prediction",
        },
    }

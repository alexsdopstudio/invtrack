from datetime import date, timedelta

import pytest

from app.config import get_scoring_config
from app.models import FactPrice
from app.scoring import momentum
from app.scoring.engine import compute_breakdown

TODAY = date(2026, 7, 1)


def _prices(db, ticker, closes):
    """closes given oldest-first."""
    for i, close in enumerate(closes):
        db.add(
            FactPrice(
                ticker=ticker,
                date=TODAY - timedelta(days=len(closes) - i),
                open=close, high=close, low=close, close=close, volume=1e6,
            )
        )
    db.commit()


def test_uptrend_scores_above_neutral(db):
    _prices(db, "NVDA", [100 + i * 0.5 for i in range(220)])  # steady rise
    result = momentum.compute(db, "NVDA", get_scoring_config(), TODAY)
    assert result["score"] > 60
    assert result["inputs"]["pct_vs_short_ma"] > 0
    assert result["inputs"]["pct_vs_long_ma"] > 0


def test_downtrend_scores_below_neutral(db):
    _prices(db, "NVDA", [200 - i * 0.5 for i in range(220)])
    result = momentum.compute(db, "NVDA", get_scoring_config(), TODAY)
    assert result["score"] < 40


def test_insufficient_history_is_missing(db):
    _prices(db, "NVDA", [100.0] * 30)  # below min_closes
    assert momentum.compute(db, "NVDA", get_scoring_config(), TODAY) is None


def test_short_history_uses_short_ma_only(db):
    _prices(db, "NVDA", [100 + i for i in range(80)])  # >=60 but <200 closes
    result = momentum.compute(db, "NVDA", get_scoring_config(), TODAY)
    assert result is not None
    assert result["inputs"]["pct_vs_long_ma"] is None


def test_engine_renormalizes_with_momentum(db):
    _prices(db, "NVDA", [100 + i * 0.5 for i in range(220)])
    total, breakdown = compute_breakdown(db, "NVDA", get_scoring_config(), TODAY)
    assert set(breakdown) == {"fundamentals", "congress", "insider", "momentum"}
    assert breakdown["momentum"]["status"] == "ok"
    # momentum is the only component with data -> its weight renormalizes to 1
    assert breakdown["momentum"]["normalized_weight"] == 1.0
    assert total == pytest.approx(breakdown["momentum"]["score"], abs=0.05)

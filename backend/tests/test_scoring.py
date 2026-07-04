from datetime import date, timedelta

import pytest

from app.config import get_scoring_config
from app.models import (
    FactCongressTrade,
    FactFundamentals,
    FactInsiderTrade,
)
from app.scoring import congress, fundamentals, insider
from app.scoring.engine import compute_breakdown

TODAY = date(2026, 7, 1)


@pytest.fixture
def config():
    return get_scoring_config()


def add_congress_trade(db, member, tx_type, days_ago, low=50001, high=100000, ticker="NVDA"):
    db.add(
        FactCongressTrade(
            chamber="senate",
            member=member,
            ticker=ticker,
            transaction_date=TODAY - timedelta(days=days_ago + 20),
            disclosure_date=TODAY - timedelta(days=days_ago),
            tx_type=tx_type,
            amount_low=low,
            amount_high=high,
        )
    )
    db.commit()


def test_congress_score_missing_without_data(db, config):
    assert congress.compute(db, "NVDA", config, TODAY) is None


def test_congress_buys_score_above_neutral(db, config):
    add_congress_trade(db, "Sen. A", "buy", 10)
    result = congress.compute(db, "NVDA", config, TODAY)
    assert result["score"] > 50
    assert result["inputs"]["buys"] == 1
    assert result["inputs"]["cluster"] is None


def test_congress_cluster_bonus(db, config):
    for i, member in enumerate(["Sen. A", "Sen. B", "Sen. C"]):
        add_congress_trade(db, member, "buy", 5 + i)
    with_cluster = congress.compute(db, "NVDA", config, TODAY)
    assert with_cluster["inputs"]["cluster"]["direction"] == "buy"
    assert len(with_cluster["inputs"]["cluster"]["members"]) == 3


def test_congress_sells_score_below_neutral(db, config):
    add_congress_trade(db, "Sen. A", "sell", 10)
    result = congress.compute(db, "NVDA", config, TODAY)
    assert result["score"] < 50


def test_congress_old_trades_out_of_window(db, config):
    add_congress_trade(db, "Sen. A", "buy", config["congress"]["lookback_days"] + 30)
    assert congress.compute(db, "NVDA", config, TODAY) is None


def add_insider_trade(db, acc, name, code, days_ago, value, ticker="NVDA"):
    db.add(
        FactInsiderTrade(
            accession_no=acc,
            row_index=0,
            ticker=ticker,
            insider_name=name,
            transaction_date=TODAY - timedelta(days=days_ago),
            code=code,
            shares=1,
            price=value,
            value=value,
        )
    )
    db.commit()


def test_insider_buys_beat_equal_sells(db, config):
    # equal dollars, same recency: the sell discount should leave a net-positive score
    add_insider_trade(db, "a-1", "Alice", "P", 10, 500_000)
    add_insider_trade(db, "a-2", "Bob", "S", 10, 500_000)
    result = insider.compute(db, "NVDA", config, TODAY)
    assert result["score"] > 50


def test_insider_cluster_bonus(db, config):
    add_insider_trade(db, "a-1", "Alice", "P", 5, 200_000)
    add_insider_trade(db, "a-2", "Bob", "P", 8, 150_000)
    result = insider.compute(db, "NVDA", config, TODAY)
    assert result["inputs"]["cluster"]["direction"] == "buy"


def add_fundamentals(db, ticker="NVDA", **kwargs):
    db.add(FactFundamentals(ticker=ticker, as_of=TODAY, **kwargs))
    db.commit()


def test_fundamentals_bands(db, config):
    add_fundamentals(
        db,
        revenue_growth_yoy=0.62,  # excellent (>= 0.20)
        operating_margin=0.58,    # excellent
        debt_to_equity=0.22,      # excellent (<= 0.5)
        pe=45.0,                  # poor (> 40)
    )
    result = fundamentals.compute(db, "NVDA", config, TODAY)
    metrics = result["inputs"]["metrics"]
    assert metrics["revenue_growth_yoy"]["band"] == "excellent"
    assert metrics["pe"]["band"] == "poor"
    assert result["score"] == pytest.approx((90 + 90 + 90 + 20) / 4)


def test_fundamentals_skips_missing_metrics(db, config):
    add_fundamentals(db, revenue_growth_yoy=0.15)  # good; everything else None
    result = fundamentals.compute(db, "NVDA", config, TODAY)
    assert result["score"] == 70
    assert result["inputs"]["metrics_used"] == 1


def test_composite_renormalizes_missing_components(db, config):
    # only fundamentals data exists -> its normalized weight must be 1.0
    add_fundamentals(db, revenue_growth_yoy=0.15)
    total, breakdown = compute_breakdown(db, "NVDA", config, TODAY)
    assert total == pytest.approx(70)
    assert breakdown["fundamentals"]["normalized_weight"] == 1.0
    assert breakdown["congress"]["status"] == "missing"
    assert breakdown["insider"]["status"] == "missing"
    assert breakdown["congress"]["contribution"] == 0.0


def test_composite_no_data_returns_none(db, config):
    total, breakdown = compute_breakdown(db, "NVDA", config, TODAY)
    assert total is None
    assert all(c["status"] == "missing" for c in breakdown.values())


def test_composite_weights_sum(db, config):
    add_fundamentals(db, revenue_growth_yoy=0.15, operating_margin=0.20)
    add_congress_trade(db, "Sen. A", "buy", 10)
    add_insider_trade(db, "a-1", "Alice", "P", 10, 500_000)
    total, breakdown = compute_breakdown(db, "NVDA", config, TODAY)
    norm_sum = sum(c["normalized_weight"] for c in breakdown.values())
    assert norm_sum == pytest.approx(1.0, abs=1e-3)
    contribution_sum = sum(c["contribution"] for c in breakdown.values())
    assert total == pytest.approx(contribution_sum, abs=0.05)
    assert 0 <= total <= 100

from datetime import date, timedelta

from app.config import get_scoring_config
from app.models import FactFundamentals, FactPrice, WatchlistItem
from app.screener import cash_runway_quarters, evaluate, screen_all

TODAY = date.today()


def add_fundamentals(db, ticker="PLTR", **kwargs):
    db.add(FactFundamentals(ticker=ticker, as_of=TODAY, **kwargs))
    db.commit()


def add_volume(db, ticker, volume, days=30):
    for i in range(days):
        d = TODAY - timedelta(days=i + 1)
        db.add(
            FactPrice(ticker=ticker, date=d, open=1, high=1, low=1, close=1, volume=volume)
        )
    db.commit()


def test_cash_runway_math():
    assert cash_runway_quarters(1_000_000, -250_000) == 4.0
    assert cash_runway_quarters(1_000_000, 50_000) == float("inf")  # cash generative
    assert cash_runway_quarters(None, -250_000) is None
    assert cash_runway_quarters(1_000_000, None) is None


def test_evaluate_pass_fail_unknown(db):
    db.add(WatchlistItem(ticker="PLTR"))
    db.commit()
    add_fundamentals(
        db,
        market_cap=1.5e9,             # pass: within $50M-$2B
        revenue_growth_yoy=0.30,      # pass: >= 25%
        gross_margin=0.45,            # fail: < 60%
        current_ratio=5.0,            # pass
        total_cash=3.0e9,
        quarterly_operating_cashflow=-5.0e7,  # 60 quarters runway -> pass
        insider_ownership_pct=None,   # unknown
    )
    add_volume(db, "PLTR", 500_000)   # pass

    result = evaluate(db, "PLTR", get_scoring_config())
    c = result["criteria"]
    assert c["market_cap"]["status"] == "pass"
    assert c["avg_daily_volume"]["status"] == "pass"
    assert c["revenue_growth_yoy"]["status"] == "pass"
    assert c["gross_margin"]["status"] == "fail"
    assert c["current_ratio"]["status"] == "pass"
    assert c["cash_runway_quarters"]["status"] == "pass"
    assert c["insider_ownership"]["status"] == "unknown"
    assert (result["passed"], result["failed"], result["unknown"]) == (5, 1, 1)


def test_evaluate_megacap_fails_size(db):
    db.add(WatchlistItem(ticker="AAPL"))
    db.commit()
    add_fundamentals(db, ticker="AAPL", market_cap=3.2e12)
    result = evaluate(db, "AAPL", get_scoring_config())
    assert result["criteria"]["market_cap"]["status"] == "fail"


def test_evaluate_no_data_is_all_unknown(db):
    db.add(WatchlistItem(ticker="XYZ"))
    db.commit()
    result = evaluate(db, "XYZ", get_scoring_config())
    assert result["passed"] == 0
    assert result["failed"] == 0
    assert result["unknown"] == 7


def test_screen_all_ranked_by_passes(db):
    for t in ("AAPL", "PLTR"):
        db.add(WatchlistItem(ticker=t))
    db.commit()
    add_fundamentals(db, ticker="AAPL", market_cap=3.2e12, gross_margin=0.46)
    add_fundamentals(
        db,
        ticker="PLTR",
        market_cap=1.5e9,
        revenue_growth_yoy=0.30,
        gross_margin=0.80,
        current_ratio=5.0,
        total_cash=3.0e9,
        quarterly_operating_cashflow=1.0e7,
        insider_ownership_pct=0.13,
    )
    rows = screen_all(db, get_scoring_config())
    assert [r["ticker"] for r in rows] == ["PLTR", "AAPL"]
    assert rows[0]["passed"] > rows[1]["passed"]

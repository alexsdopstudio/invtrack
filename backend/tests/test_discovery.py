from datetime import date, timedelta

from app.ingestion.targets import discovered_tickers, target_tickers
from app.models import FactCongressTrade, FactPrice, WatchlistItem
from app.queries import idea_rows, price_stats

TODAY = date.today()


def add_trade(db, ticker, tx_type, days_ago, low=50001, high=100000, member="Sen. A"):
    db.add(
        FactCongressTrade(
            chamber="senate",
            member=member,
            ticker=ticker,
            transaction_date=TODAY - timedelta(days=days_ago + 10),
            disclosure_date=TODAY - timedelta(days=days_ago),
            tx_type=tx_type,
            amount_low=low,
            amount_high=high,
        )
    )
    db.commit()


def test_discovered_tickers_ranked_by_net_buying_excluding_watchlist(db):
    db.add(WatchlistItem(ticker="NVDA"))
    db.commit()
    add_trade(db, "NVDA", "buy", 5, 500001, 1000000)  # watchlisted -> excluded
    add_trade(db, "PLTR", "buy", 5, 100001, 250000, member="Sen. A")
    add_trade(db, "PLTR", "buy", 8, 100001, 250000, member="Sen. B")
    add_trade(db, "AVGO", "buy", 5, 1001, 15000)
    add_trade(db, "XOM", "sell", 5, 500001, 1000000)  # net seller ranks last
    add_trade(db, "OLD", "buy", 200, 500001, 1000000)  # outside 90d window

    result = discovered_tickers(db)
    assert result == ["PLTR", "AVGO", "XOM"]
    assert target_tickers(db) == ["NVDA", "PLTR", "AVGO", "XOM"]


def test_idea_rows_shape_and_ordering(db):
    db.add(WatchlistItem(ticker="NVDA"))
    db.commit()
    add_trade(db, "NVDA", "buy", 5)  # excluded: on watchlist
    add_trade(db, "PLTR", "buy", 5, member="Sen. A")
    add_trade(db, "PLTR", "buy", 8, member="Sen. B")
    add_trade(db, "PLTR", "sell", 12, 1001, 15000, member="Sen. C")

    rows = idea_rows(db)
    assert len(rows) == 1
    idea = rows[0]
    assert idea["ticker"] == "PLTR"
    assert idea["buys"] == 2
    assert idea["sells"] == 1
    assert idea["buyers"] == 2  # distinct buying members
    assert idea["last_activity"] == TODAY - timedelta(days=5)
    assert idea["net_dollars"] > 0
    assert idea["score"] is None  # no score computed yet
    assert idea["sparkline"] == []


def _add_prices(db, ticker, closes):
    for i, close in enumerate(closes):
        db.add(
            FactPrice(
                ticker=ticker,
                date=TODAY - timedelta(days=len(closes) - i),
                open=close,
                high=close * 1.02,
                low=close * 0.98,
                close=close,
                volume=1e6,
            )
        )
    db.commit()


def test_price_stats_math(db):
    # 10% total growth over ~100 days, small daily wiggle
    closes = [100.0 * (1.001**i) for i in range(100)]
    _add_prices(db, "NVDA", closes)
    stats = price_stats(db, "NVDA")
    assert stats is not None
    assert stats["data_points"] == 100
    assert stats["cagr_1y"] > 0.3  # 0.1%/day compounds to >30%/yr calendar-scaled
    assert stats["annual_vol"] < 0.05  # near-deterministic series
    assert stats["max_drawdown"] == 0.0  # monotonically increasing
    assert stats["atr_14"] is not None
    assert stats["last_close"] == closes[-1]


def test_price_stats_requires_enough_history(db):
    _add_prices(db, "NVDA", [100.0] * 30)
    assert price_stats(db, "NVDA") is None


def test_price_stats_drawdown(db):
    closes = [100.0] * 40 + [50.0] * 30  # 50% crash
    _add_prices(db, "NVDA", closes)
    stats = price_stats(db, "NVDA")
    assert stats["max_drawdown"] == -0.5

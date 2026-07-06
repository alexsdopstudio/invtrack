from datetime import date, datetime, time, timedelta, timezone

from app.alerts import detect_alerts, mark_all_seen
from app.models import (
    Alert,
    FactCongressTrade,
    FactInsiderTrade,
    Score,
    WatchlistItem,
)

TODAY = date.today()


def _watch(db, ticker="NVDA"):
    db.add(WatchlistItem(ticker=ticker))
    db.commit()


def _congress_trade(db, ticker="NVDA", days_ago=2):
    db.add(
        FactCongressTrade(
            chamber="senate",
            member="Sen. A",
            ticker=ticker,
            transaction_date=TODAY - timedelta(days=days_ago + 10),
            disclosure_date=TODAY - timedelta(days=days_ago),
            tx_type="buy",
            amount_low=15001,
            amount_high=50000,
        )
    )
    db.commit()


def test_congress_alert_created_and_idempotent(db):
    _watch(db)
    _congress_trade(db)
    created = detect_alerts(db, TODAY)
    assert len(created) == 1
    assert created[0].kind == "congress_trade"
    assert "Sen. A" in created[0].title
    # re-running detection creates nothing new
    assert detect_alerts(db, TODAY) == []


def test_no_alert_for_non_watchlist_ticker(db):
    _watch(db, "MSFT")
    _congress_trade(db, ticker="NVDA")
    assert detect_alerts(db, TODAY) == []


def test_old_disclosures_do_not_alert(db):
    _watch(db)
    _congress_trade(db, days_ago=30)  # outside the 7-day alert window
    assert detect_alerts(db, TODAY) == []


def test_insider_alert(db):
    _watch(db)
    db.add(
        FactInsiderTrade(
            accession_no="a-1",
            row_index=0,
            ticker="NVDA",
            insider_name="Chen Example",
            transaction_date=TODAY - timedelta(days=1),
            code="P",
            shares=1000,
            price=100.0,
            value=100000.0,
        )
    )
    db.commit()
    created = detect_alerts(db, TODAY)
    assert len(created) == 1
    assert created[0].kind == "insider_trade"
    assert "bought" in created[0].title


def _score(db, ticker, total, days_ago):
    db.add(
        Score(
            ticker=ticker,
            total=total,
            components={},
            computed_at=datetime.combine(
                TODAY - timedelta(days=days_ago), time(hour=8), tzinfo=timezone.utc
            ),
        )
    )
    db.commit()


def test_score_cross_up_alert(db):
    _watch(db)
    _score(db, "NVDA", 55.0, 1)
    _score(db, "NVDA", 63.0, 0)
    created = detect_alerts(db, TODAY)
    assert len(created) == 1
    assert created[0].kind == "score_cross"
    assert created[0].payload["direction"] == "up"


def test_score_cross_down_alert(db):
    _watch(db)
    _score(db, "NVDA", 45.0, 1)
    _score(db, "NVDA", 38.0, 0)
    created = detect_alerts(db, TODAY)
    assert created[0].payload["direction"] == "down"


def test_no_cross_no_alert(db):
    _watch(db)
    _score(db, "NVDA", 50.0, 1)
    _score(db, "NVDA", 55.0, 0)  # moved, but no band crossed
    assert detect_alerts(db, TODAY) == []


def test_mark_all_seen(db):
    _watch(db)
    _congress_trade(db)
    detect_alerts(db, TODAY)
    assert mark_all_seen(db) == 1
    assert db.query(Alert).filter_by(seen=False).count() == 0

from datetime import date, timedelta
from pathlib import Path

from app.ingestion.insider import upsert_insider_trades
from app.ingestion.insider_marketwide import keep_open_market_buys, parse_daily_index
from app.ingestion.targets import insider_cluster_tickers, target_tickers
from app.models import WatchlistItem
from app.queries import insider_idea_rows

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date.today()


def test_parse_daily_index_keeps_only_form4():
    entries = parse_daily_index((FIXTURES / "form_idx_sample.idx").read_text())
    assert [e["form"] for e in entries] == ["4", "4", "4/A"]
    assert entries[0]["cik_int"] == 1535527
    assert entries[0]["accession_no"] == "0001535527-26-000456"
    assert entries[1]["company"] == "SMITH JOHN Q"


def test_keep_open_market_buys_filters_code_and_size():
    rows = [
        {"code": "P", "value": 50000.0},
        {"code": "P", "value": 5000.0},   # too small
        {"code": "S", "value": 900000.0}, # sale
        {"code": "P", "value": None},     # unpriced
        {"code": "A", "value": 80000.0},  # award, not open-market
    ]
    kept = keep_open_market_buys(rows, min_value=25000.0)
    assert kept == [{"code": "P", "value": 50000.0}]


def _buy(acc, ticker, name, days_ago, value=50000.0):
    return {
        "accession_no": acc, "row_index": 0, "ticker": ticker,
        "insider_name": name, "transaction_date": TODAY - timedelta(days=days_ago),
        "code": "P", "shares": 100.0, "price": value / 100.0, "value": value,
    }


def test_cluster_discovery_needs_multiple_buyers(db):
    upsert_insider_trades(db, [
        _buy("a-1", "CLST", "Alice", 10),
        _buy("a-2", "CLST", "Bob", 5, value=80000.0),
        _buy("a-3", "SOLO", "Carol", 5),                # one buyer: no cluster
        _buy("a-4", "OLD", "Dan", 45), _buy("a-5", "OLD", "Erin", 44),  # too old
    ])
    assert insider_cluster_tickers(db) == ["CLST"]
    assert "CLST" in target_tickers(db)


def test_cluster_excludes_watchlist_and_ranks_by_dollars(db):
    db.add(WatchlistItem(ticker="OWNED"))
    db.commit()
    upsert_insider_trades(db, [
        _buy("b-1", "OWNED", "Alice", 5), _buy("b-2", "OWNED", "Bob", 4),
        _buy("b-3", "BIG", "Carol", 5, value=900000.0), _buy("b-4", "BIG", "Dan", 4, value=900000.0),
        _buy("b-5", "SMALL", "Erin", 5), _buy("b-6", "SMALL", "Frank", 4),
    ])
    assert insider_cluster_tickers(db) == ["BIG", "SMALL"]
    rows = insider_idea_rows(db)
    assert [r["ticker"] for r in rows] == ["BIG", "SMALL"]
    assert rows[0]["buyers"] == 2
    assert rows[0]["total_value"] == 1800000.0


def test_idempotent_upsert_from_scan(db):
    rows = [_buy("c-1", "CLST", "Alice", 5)]
    assert upsert_insider_trades(db, rows) == 1
    assert upsert_insider_trades(db, rows) == 0  # same accession/row: no dupes

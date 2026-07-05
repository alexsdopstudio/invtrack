import json
from datetime import date
from pathlib import Path

import pytest

from app.ingestion import congress
from app.ingestion.congress import parse_stock_watcher_rows, upsert_trades
from app.models import FactCongressTrade, WatchlistItem

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_parse_senate_rows():
    rows = parse_stock_watcher_rows(load("senate_sample.json"), "senate")
    # the "--" ticker row is dropped
    assert len(rows) == 2
    buy = rows[0]
    assert buy["ticker"] == "NVDA"
    assert buy["member"] == "Jane Doe"
    assert buy["tx_type"] == "buy"
    assert buy["transaction_date"] == date(2026, 1, 9)
    assert buy["disclosure_date"] == date(2026, 2, 10)
    assert buy["amount_low"] == 50001
    assert buy["amount_high"] == 100000
    sell = rows[1]
    assert sell["tx_type"] == "sell"
    assert sell["chamber"] == "senate"
    # raw payload preserved for provenance
    assert buy["raw"]["ptr_link"].startswith("https://efdsearch.senate.gov")


def test_parse_house_rows_skips_unparseable():
    rows = parse_stock_watcher_rows(load("house_sample.json"), "house")
    # third row has an unparseable transaction_date
    assert len(rows) == 2
    assert rows[0]["ticker"] == "MSFT"
    assert rows[0]["tx_type"] == "buy"
    assert rows[0]["transaction_date"] == date(2026, 1, 12)
    assert rows[1]["tx_type"] == "sell"
    assert rows[1]["amount_low"] == 100001


def test_upsert_is_idempotent(db):
    rows = parse_stock_watcher_rows(load("senate_sample.json"), "senate")
    assert upsert_trades(db, rows) == 2
    assert upsert_trades(db, rows) == 0


def _watch(db, ticker):
    db.add(WatchlistItem(ticker=ticker))
    db.commit()


def _fail(client):
    raise RuntimeError("403 Forbidden")


def test_ingest_survives_one_chamber_failing(db, monkeypatch):
    _watch(db, "MSFT")
    monkeypatch.setattr(congress, "fetch_senate_rows", _fail)
    monkeypatch.setattr(
        congress,
        "fetch_house_rows",
        lambda client: parse_stock_watcher_rows(load("house_sample.json"), "house"),
    )
    # both house fixture trades land (storage is market-wide for discovery)
    assert congress.ingest(db) == 2
    assert db.query(FactCongressTrade).count() == 2


def test_ingest_raises_when_all_chambers_fail(db, monkeypatch):
    _watch(db, "MSFT")
    monkeypatch.setattr(congress, "fetch_senate_rows", _fail)
    monkeypatch.setattr(congress, "fetch_house_rows", _fail)
    with pytest.raises(RuntimeError, match="all congressional sources failed"):
        congress.ingest(db)

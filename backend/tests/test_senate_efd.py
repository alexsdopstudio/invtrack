import json
from datetime import date
from pathlib import Path

from app.ingestion.congress import parse_stock_watcher_rows
from app.ingestion.senate_efd import parse_ptr_html, parse_search_rows

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_search_rows_keeps_electronic_ptrs_only():
    payload = json.loads((FIXTURES / "efd_search_sample.json").read_text())
    reports = parse_search_rows(payload)
    # the paper filing (scanned image, unparseable) is skipped
    assert len(reports) == 2
    first = reports[0]
    assert first["member"] == "Jane Doe"
    assert first["link"].startswith("https://efdsearch.senate.gov/search/view/ptr/abcd1234")
    assert first["date_received"] == "06/25/2026"


def test_parse_ptr_html_extracts_transactions():
    html = (FIXTURES / "efd_ptr_sample.html").read_text()
    rows = parse_ptr_html(html, "Jane Doe", "06/25/2026")
    assert len(rows) == 3
    buy = rows[0]
    assert buy["senator"] == "Jane Doe"
    assert buy["ticker"] == "NVDA"
    assert buy["type"] == "Purchase"
    assert buy["amount"] == "$15,001 - $50,000"
    assert buy["transaction_date"] == "06/15/2026"
    assert buy["disclosure_date"] == "06/25/2026"
    assert buy["owner"] == "Spouse"


def test_ptr_rows_feed_the_shared_normalizer():
    html = (FIXTURES / "efd_ptr_sample.html").read_text()
    raw = parse_ptr_html(html, "Jane Doe", "06/25/2026")
    normalized = parse_stock_watcher_rows(raw, "senate")
    # the "--" non-ticker row is dropped by the normalizer
    assert len(normalized) == 2
    buy, sell = normalized
    assert buy["chamber"] == "senate"
    assert buy["member"] == "Jane Doe"
    assert buy["tx_type"] == "buy"
    assert buy["transaction_date"] == date(2026, 6, 15)
    assert buy["disclosure_date"] == date(2026, 6, 25)
    assert buy["amount_low"] == 15001
    assert buy["amount_high"] == 50000
    assert sell["ticker"] == "UNH"
    assert sell["tx_type"] == "sell"


def test_parse_ptr_html_ignores_unrelated_tables():
    html = "<table><thead><tr><th>Name</th><th>Office</th></tr></thead><tbody><tr><td>x</td><td>y</td></tr></tbody></table>"
    assert parse_ptr_html(html, "Jane Doe", "06/25/2026") == []

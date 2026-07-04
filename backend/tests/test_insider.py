from datetime import date
from pathlib import Path

from app.ingestion.insider import (
    doc_candidates,
    list_xml_docs,
    parse_form4_xml,
    recent_form4_filings,
    upsert_insider_trades,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_form4_xml():
    xml_text = (FIXTURES / "form4_sample.xml").read_text()
    rows = parse_form4_xml(xml_text, "0001234567-26-000001")
    assert len(rows) == 2
    buy, sell = rows
    assert buy["ticker"] == "NVDA"
    assert buy["cik"] == "0001045810"
    assert buy["insider_name"] == "DOE JANE"
    assert buy["insider_title"] == "Executive Vice President"
    assert buy["is_officer"] is True
    assert buy["is_director"] is False
    assert buy["code"] == "P"
    assert buy["transaction_date"] == date(2026, 1, 14)
    assert buy["shares"] == 5000
    assert buy["price"] == 131.25
    assert buy["value"] == 5000 * 131.25
    assert sell["code"] == "S"
    assert sell["row_index"] == 1


def test_recent_form4_filings_filters_by_form_and_date():
    submissions = {
        "filings": {
            "recent": {
                "form": ["4", "10-K", "4", "4/A"],
                "filingDate": ["2026-06-20", "2026-06-01", "2025-01-01", "2026-06-25"],
                "accessionNumber": ["a-1", "a-2", "a-3", "a-4"],
                "primaryDocument": ["f4.xml", "tenk.htm", "old.xml", "f4a.xml"],
            }
        }
    }
    filings = recent_form4_filings(submissions, since=date(2026, 1, 1))
    assert [f["accession_no"] for f in filings] == ["a-1", "a-4"]


def test_doc_candidates_strips_xsl_rendering_prefix():
    # EDGAR's primaryDocument often points at the XSL-rendered HTML view;
    # the raw XML is the basename at the accession root.
    assert doc_candidates("xslF345X05/wk-form4_123.xml") == [
        "wk-form4_123.xml",
        "xslF345X05/wk-form4_123.xml",
    ]
    assert doc_candidates("form4.xml") == ["form4.xml"]


def test_list_xml_docs_skips_xsl_renderings():
    index_payload = {
        "directory": {
            "item": [
                {"name": "0001234567-26-000001-index.htm"},
                {"name": "xslF345X05/wk-form4_123.xml"},
                {"name": "wk-form4_123.xml"},
                {"name": "form4.pdf"},
            ]
        }
    }
    assert list_xml_docs(index_payload) == ["wk-form4_123.xml"]


def test_upsert_insider_is_idempotent(db):
    xml_text = (FIXTURES / "form4_sample.xml").read_text()
    rows = parse_form4_xml(xml_text, "0001234567-26-000001")
    assert upsert_insider_trades(db, rows) == 2
    assert upsert_insider_trades(db, rows) == 0

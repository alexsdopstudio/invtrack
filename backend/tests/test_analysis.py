from pathlib import Path

from app.analysis.edgar_sections import extract_sections, latest_10k_filing
from app.analysis.report import SYSTEM_PROMPT, build_user_prompt

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_sections_from_10k_html():
    html = (FIXTURES / "tenk_sample.html").read_text()
    sections = extract_sections(html)
    assert set(sections) == {"item_1", "item_1a", "item_7"}
    # real section content wins over the table-of-contents entries
    assert "widget-optimization software" in sections["item_1"]
    assert "24% of total revenue" in sections["item_1"]
    assert "patent infringement lawsuit" in sections["item_1a"]
    assert "elongated sales cycles" in sections["item_7"]
    # neighboring items are not bled into the extracted sections
    assert "headquarters facility" not in sections["item_1a"]
    assert "accompanying notes" not in sections["item_7"]


def test_latest_10k_filing_picks_most_recent():
    submissions = {
        "filings": {
            "recent": {
                "form": ["4", "10-K", "10-Q", "10-K"],
                "filingDate": ["2026-06-20", "2026-02-10", "2026-05-01", "2025-02-11"],
                "accessionNumber": ["a-1", "a-2", "a-3", "a-4"],
                "primaryDocument": ["f4.xml", "tenk-2026.htm", "tenq.htm", "tenk-2025.htm"],
            }
        }
    }
    filing = latest_10k_filing(submissions)
    assert filing["accession_no"] == "a-2"  # first (most recent) 10-K in the index
    assert filing["primary_doc"] == "tenk-2026.htm"


def test_latest_10k_filing_none_when_absent():
    assert latest_10k_filing({"filings": {"recent": {"form": ["4"], "filingDate": ["2026-01-01"], "accessionNumber": ["a"], "primaryDocument": ["d"]}}}) is None


def test_prompt_construction():
    sections = {"item_1a": "Risk text about the largest customer."}
    prompt = build_user_prompt("PLTR", "Palantir Technologies Inc.", sections)
    assert "Palantir Technologies Inc." in prompt
    assert "ticker PLTR" in prompt
    assert '<section name="Risk factors">' in prompt
    assert "Risk text about the largest customer." in prompt
    # the persona forbids the model from computing metrics
    assert "Do NOT compute financial ratios" in SYSTEM_PROMPT
    assert "## Red flags" in SYSTEM_PROMPT

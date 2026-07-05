"""Fetch and extract the analysis-relevant sections of a company's latest
10-K from SEC EDGAR (free, official).

Instead of a RAG pipeline, we pull only the sections that matter for
qualitative analysis — Item 1 (Business), Item 1A (Risk Factors), Item 7
(MD&A) — and cap each to a byte budget so a single Claude call stays cheap.
Filing HTML varies by filer; extraction is heading-based and defensive.
"""

import re
from datetime import date, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ..ingestion import http
from ..ingestion.insider import ARCHIVES_URL, SUBMISSIONS_URL

SECTIONS = {
    "item_1": "Business overview",
    "item_1a": "Risk factors",
    "item_7": "Management's discussion & analysis",
}

# Per-section character budget (~150k chars total ≈ 40-50k tokens).
SECTION_CHAR_BUDGET = {"item_1": 40000, "item_1a": 60000, "item_7": 50000}

_ITEM_HEADING_RE = re.compile(
    r"^\s*item\s+(1a|1b|1c|1|2|3|4|5|6|7a|7|8|9a|9b|9)[\s.:—-]",
    re.IGNORECASE,
)


def latest_10k_filing(submissions: dict[str, Any]) -> dict[str, str] | None:
    """Most recent 10-K accession + primary doc from a data.sec.gov
    submissions payload."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    for i, form in enumerate(forms):
        if form == "10-K":
            return {
                "accession_no": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
                "filing_date": recent["filingDate"][i],
            }
    return None


def extract_sections(html: str) -> dict[str, str]:
    """Split a 10-K document into items by scanning heading-like lines.

    Works on the flattened text: EDGAR filings wrap headings in wildly varying
    markup, but the visible text reliably starts item sections with
    "Item 1.", "Item 1A.", etc. The first occurrences are usually the table of
    contents; we keep the occurrence with the most content following it.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.split("\n")]

    # Mark every line that looks like an item heading.
    marks: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = _ITEM_HEADING_RE.match(line)
        if m and len(line) < 120:  # headings are short; prose lines are not
            marks.append((i, m.group(1).lower()))

    # Section content = text between a heading and the next heading.
    spans: dict[str, list[str]] = {}
    for idx, (line_no, item) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        content = "\n".join(ln for ln in lines[line_no:end] if ln)
        key = f"item_{item}"
        # keep the longest span per item (skips table-of-contents entries)
        if key not in spans or len(content) > len(spans[key][0]):
            spans[key] = [content]

    out: dict[str, str] = {}
    for key in SECTIONS:
        if key in spans:
            budget = SECTION_CHAR_BUDGET[key]
            content = spans[key][0]
            out[key] = content[:budget]
    return out


def fetch_latest_10k_sections(
    client: httpx.Client, cik: str
) -> tuple[dict[str, str], dict[str, Any]] | None:
    """Returns (sections, meta) for the ticker's latest 10-K, or None if no
    10-K exists in the recent filings index."""
    submissions = http.sec_get(client, SUBMISSIONS_URL.format(cik=cik)).json()
    filing = latest_10k_filing(submissions)
    if filing is None:
        return None
    accession_nodash = filing["accession_no"].replace("-", "")
    doc = filing["primary_doc"].rpartition("/")[2]
    url = ARCHIVES_URL.format(cik_int=int(cik), accession_nodash=accession_nodash, doc=doc)
    html = http.sec_get(client, url).text
    sections = extract_sections(html)
    meta = {
        "accession_no": filing["accession_no"],
        "filing_date": filing["filing_date"],
        "source_url": url,
        "sections": {
            key: {"label": SECTIONS[key], "chars": len(content)}
            for key, content in sections.items()
        },
        "fetched_at": datetime.combine(date.today(), datetime.min.time()).isoformat(),
    }
    return sections, meta

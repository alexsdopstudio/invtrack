"""SEC EDGAR Form 4 (corporate insider trades) -> fact_insider_trade.

Official and free: filed within 2 business days of the trade. For each
watchlist ticker we resolve its CIK (dim_ticker), pull the company's recent
submissions index from data.sec.gov, and parse the Form 4 XML documents.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DimTicker, FactInsiderTrade, WatchlistItem
from . import http

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{doc}"

LOOKBACK_DAYS = 180
MAX_FILINGS_PER_CIK = 40


def recent_form4_filings(
    submissions: dict[str, Any], since: date, limit: int = MAX_FILINGS_PER_CIK
) -> list[dict[str, str]]:
    """Extract recent Form 4 accession numbers + primary docs from a
    data.sec.gov submissions payload."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    out = []
    for i, form in enumerate(forms):
        if form not in ("4", "4/A"):
            continue
        filing_date = recent["filingDate"][i]
        if datetime.strptime(filing_date, "%Y-%m-%d").date() < since:
            continue
        out.append(
            {
                "accession_no": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
                "filing_date": filing_date,
            }
        )
        if len(out) >= limit:
            break
    return out


def doc_candidates(primary_doc: str) -> list[str]:
    """EDGAR's primaryDocument for a Form 4 often points at the XSL-rendered
    HTML view (e.g. 'xslF345X05/wk-form4.xml'), which is not parseable XML.
    The raw ownership XML is the same filename at the accession root, so try
    the basename first."""
    base = primary_doc.rpartition("/")[2]
    return [base] if base == primary_doc else [base, primary_doc]


def list_xml_docs(index_payload: dict[str, Any]) -> list[str]:
    """Fallback: raw .xml documents from an accession's index.json listing."""
    items = index_payload.get("directory", {}).get("item", [])
    return [
        i["name"]
        for i in items
        if i.get("name", "").endswith(".xml") and not i["name"].startswith("xsl")
    ]


def _fetch_form4_rows(
    client: httpx.Client, cik_int: int, accession_nodash: str, filing: dict[str, str]
) -> list[dict[str, Any]]:
    def url_for(doc: str) -> str:
        return ARCHIVES_URL.format(cik_int=cik_int, accession_nodash=accession_nodash, doc=doc)

    candidates = doc_candidates(filing["primary_doc"])
    last_error: Exception | None = None
    for doc in candidates:
        try:
            xml_text = http.sec_get(client, url_for(doc)).text
            return parse_form4_xml(xml_text, filing["accession_no"])
        except (ET.ParseError, httpx.HTTPError) as exc:
            last_error = exc
    # Last resort: scan the accession's file listing for the raw XML doc.
    index_payload = http.sec_get(client, url_for("index.json")).json()
    for doc in list_xml_docs(index_payload):
        if doc in candidates:
            continue
        try:
            xml_text = http.sec_get(client, url_for(doc)).text
            return parse_form4_xml(xml_text, filing["accession_no"])
        except (ET.ParseError, httpx.HTTPError) as exc:
            last_error = exc
    raise RuntimeError(
        f"no parseable Form 4 XML found for {filing['accession_no']}: {last_error}"
    )


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    # Form 4 wraps most leaf fields in a <value> element.
    value = el.find("value")
    target = value if value is not None else el
    return target.text.strip() if target.text else None


def _float(el: ET.Element | None) -> float | None:
    text = _text(el)
    try:
        return float(text) if text is not None else None
    except ValueError:
        return None


def parse_form4_xml(xml_text: str, accession_no: str) -> list[dict[str, Any]]:
    """Parse the non-derivative transactions out of a Form 4 ownership
    document. Returns one row per transaction."""
    root = ET.fromstring(xml_text)
    ticker = _text(root.find("./issuer/issuerTradingSymbol"))
    issuer_cik = _text(root.find("./issuer/issuerCik"))
    owner = root.find("./reportingOwner")
    name = _text(owner.find("./reportingOwnerId/rptOwnerName")) if owner is not None else None
    rel = owner.find("./reportingOwnerRelationship") if owner is not None else None
    is_officer = _text(rel.find("isOfficer")) in ("1", "true") if rel is not None else None
    is_director = _text(rel.find("isDirector")) in ("1", "true") if rel is not None else None
    title = _text(rel.find("officerTitle")) if rel is not None else None

    rows = []
    for idx, tx in enumerate(root.findall("./nonDerivativeTable/nonDerivativeTransaction")):
        tx_date_text = _text(tx.find("./transactionDate"))
        code = _text(tx.find("./transactionCoding/transactionCode"))
        if not tx_date_text or not code:
            continue
        shares = _float(tx.find("./transactionAmounts/transactionShares"))
        price = _float(tx.find("./transactionAmounts/transactionPricePerShare"))
        rows.append(
            {
                "accession_no": accession_no,
                "row_index": idx,
                "cik": issuer_cik.zfill(10) if issuer_cik else None,
                "ticker": (ticker or "").upper(),
                "insider_name": name,
                "insider_title": title,
                "is_officer": is_officer,
                "is_director": is_director,
                "transaction_date": datetime.strptime(tx_date_text, "%Y-%m-%d").date(),
                "code": code,
                "shares": shares,
                "price": price,
                "value": (shares * price) if shares is not None and price is not None else None,
                "raw": {
                    "accession_no": accession_no,
                    "acquired_disposed": _text(
                        tx.find("./transactionAmounts/transactionAcquiredDisposedCode")
                    ),
                    "security_title": _text(tx.find("./securityTitle")),
                },
            }
        )
    return rows


def upsert_insider_trades(db: Session, rows: list[dict[str, Any]]) -> int:
    existing = {
        (r.accession_no, r.row_index)
        for r in db.scalars(select(FactInsiderTrade))
    }
    count = 0
    for row in rows:
        key = (row["accession_no"], row["row_index"])
        if key in existing:
            continue
        existing.add(key)
        db.add(FactInsiderTrade(**row))
        count += 1
    db.commit()
    return count


def ingest(db: Session) -> int:
    since = date.today() - timedelta(days=LOOKBACK_DAYS)
    tickers = db.scalars(
        select(DimTicker).join(WatchlistItem, WatchlistItem.ticker == DimTicker.ticker)
    ).all()
    count = 0
    errors = []
    any_success = False
    with http.client() as client:
        for t in tickers:
            if not t.cik:
                continue
            try:
                submissions = http.sec_get(
                    client, SUBMISSIONS_URL.format(cik=t.cik)
                ).json()
                filings = recent_form4_filings(submissions, since)
            except Exception as exc:  # noqa: BLE001 - per-ticker isolation
                logger.warning("insider submissions failed for %s: %s", t.ticker, exc)
                errors.append(f"{t.ticker}: {exc}")
                continue
            for filing in filings:
                accession_nodash = filing["accession_no"].replace("-", "")
                try:
                    rows = _fetch_form4_rows(client, int(t.cik), accession_nodash, filing)
                except Exception as exc:  # noqa: BLE001 - per-filing isolation
                    logger.warning(
                        "insider filing %s failed for %s: %s",
                        filing["accession_no"], t.ticker, exc,
                    )
                    errors.append(f"{t.ticker}/{filing['accession_no']}: {exc}")
                    continue
                # Form 4s are filed under the issuer's CIK, so the symbol
                # should match; keep it as a guard anyway.
                rows = [r for r in rows if r["ticker"] == t.ticker]
                count += upsert_insider_trades(db, rows)
                any_success = True
    if errors and not any_success:
        raise RuntimeError("; ".join(errors[:5]))
    return count

"""Market-wide SEC Form 4 scan -> fact_insider_trade.

Discovery source: instead of fetching Form 4s only for tickers we already
know, walk EDGAR's official daily index of *all* filings and keep the
open-market purchases (code P) above a minimum size. That is what makes
insider cluster-buy discovery possible — finding stocks where several
insiders just bought, before the user has ever heard of them.

Cost: ~2 requests per Form 4 filing (accession index + ownership XML) at the
shared ~2 req/s government throttle — a full trading day (~2k filings) takes
~30 minutes, which is fine for the daily scheduler. Everything is idempotent
on (accession_no, row_index) and failure-isolated per filing.
"""

import logging
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from . import http
from .insider import list_xml_docs, parse_form4_xml, upsert_insider_trades

logger = logging.getLogger(__name__)

DAILY_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/form.{ymd}.idx"
)
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{doc}"

SOURCE = "sec_edgar_scan"


def parse_daily_index(text: str) -> list[dict[str, Any]]:
    """Form 4 entries out of an EDGAR form.idx daily index. The file is a
    header block followed by rows of: form type, company name (may contain
    spaces), CIK, date filed, file name — so anchor on the first and last
    tokens rather than column positions."""
    out = []
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) < 5 or tokens[0] not in ("4", "4/A"):
            continue
        file_name = tokens[-1]
        if not file_name.startswith("edgar/data/"):
            continue
        parts = file_name.split("/")
        accession = parts[-1].removesuffix(".txt")
        try:
            cik_int = int(parts[2])
        except ValueError:
            continue
        out.append(
            {
                "form": tokens[0],
                "company": " ".join(tokens[1:-3]),
                "cik_int": cik_int,
                "accession_no": accession,
            }
        )
    return out


def keep_open_market_buys(
    rows: list[dict[str, Any]], min_value: float
) -> list[dict[str, Any]]:
    """Only open-market purchases (code P) of at least min_value dollars —
    the strong insider signal; everything else is noise at market scale."""
    return [
        r
        for r in rows
        if r["code"] == "P" and r["value"] is not None and r["value"] >= min_value
    ]


def _business_days_back(today: date, n: int) -> list[date]:
    days, d = [], today - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days


def _fetch_filing_rows(
    client: httpx.Client, cik_int: int, accession_no: str
) -> list[dict[str, Any]]:
    accession_nodash = accession_no.replace("-", "")

    def url_for(doc: str) -> str:
        return ARCHIVES_URL.format(
            cik_int=cik_int, accession_nodash=accession_nodash, doc=doc
        )

    index_payload = http.sec_get(client, url_for("index.json")).json()
    last_error: Exception | None = None
    for doc in list_xml_docs(index_payload):
        try:
            xml_text = http.sec_get(client, url_for(doc)).text
            return parse_form4_xml(xml_text, accession_no)
        except Exception as exc:  # noqa: BLE001 - try the next candidate doc
            last_error = exc
    raise RuntimeError(f"no parseable Form 4 XML in {accession_no}: {last_error}")


def ingest(db: Session) -> int:
    settings = get_settings()
    if not settings.insider_scan_enabled:
        logger.info("insider market-wide scan disabled (INSIDER_SCAN_ENABLED)")
        return 0

    count = 0
    errors: list[str] = []
    any_success = False
    with http.client() as client:
        for day in _business_days_back(date.today(), settings.insider_scan_days):
            url = DAILY_INDEX_URL.format(
                year=day.year,
                quarter=(day.month - 1) // 3 + 1,
                ymd=day.strftime("%Y%m%d"),
            )
            try:
                index_text = http.sec_get(client, url).text
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:  # market holiday
                    continue
                errors.append(f"{day}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001 - per-day isolation
                errors.append(f"{day}: {exc}")
                continue
            for entry in parse_daily_index(index_text):
                try:
                    rows = _fetch_filing_rows(
                        client, entry["cik_int"], entry["accession_no"]
                    )
                except Exception as exc:  # noqa: BLE001 - per-filing isolation
                    logger.warning(
                        "scan filing %s failed: %s", entry["accession_no"], exc
                    )
                    errors.append(f"{entry['accession_no']}: {exc}")
                    continue
                buys = keep_open_market_buys(rows, settings.insider_scan_min_buy)
                for row in buys:
                    row["source"] = SOURCE
                count += upsert_insider_trades(db, buys)
                any_success = True
    if errors and not any_success:
        raise RuntimeError("; ".join(errors[:5]))
    return count

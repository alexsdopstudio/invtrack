"""SEC company_tickers.json -> dim_ticker (official, free, no key).

Provides the ticker<->CIK<->name mapping used by ticker search and by the
EDGAR Form 4 ingestion."""

from typing import Any

from sqlalchemy.orm import Session

from ..models import DimTicker, utcnow
from . import http

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def parse_company_tickers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for entry in payload.values():
        ticker = (entry.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        rows.append(
            {
                "ticker": ticker,
                "name": entry.get("title"),
                "cik": str(entry.get("cik_str", "")).zfill(10) or None,
            }
        )
    return rows


def upsert_tickers(db: Session, rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        existing = db.get(DimTicker, row["ticker"])
        if existing is None:
            db.add(DimTicker(**row))
            count += 1
        else:
            existing.name = row["name"] or existing.name
            existing.cik = row["cik"] or existing.cik
            existing.updated_at = utcnow()
    db.commit()
    return count


def ingest(db: Session) -> int:
    with http.client() as client:
        payload = http.sec_get(client, COMPANY_TICKERS_URL).json()
    return upsert_tickers(db, parse_company_tickers(payload))

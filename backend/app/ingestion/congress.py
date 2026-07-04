"""Senate/House Stock Watcher aggregate JSON -> fact_congress_trade.

These community-maintained datasets parse the official STOCK Act disclosures
(efdsearch.senate.gov / disclosures-clerk.house.gov) into structured JSON.
Disclosures are legally delayed up to 45 days, so this is a lagging signal.
Only trades for tickers currently on the watchlist are stored.
"""

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FactCongressTrade, WatchlistItem
from . import http

SENATE_URL = (
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com"
    "/aggregate/all_transactions.json"
)
HOUSE_URL = (
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com"
    "/data/all_transactions.json"
)

_AMOUNT_RE = re.compile(r"\$?([\d,]+)")


def _parse_amount_range(amount: str | None) -> tuple[float | None, float | None]:
    if not amount:
        return None, None
    numbers = [float(m.replace(",", "")) for m in _AMOUNT_RE.findall(amount)]
    if not numbers:
        return None, None
    low = numbers[0]
    high = numbers[1] if len(numbers) > 1 else None
    return low, high


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _normalize_tx_type(value: str | None) -> str | None:
    if not value:
        return None
    v = value.lower()
    if "purchase" in v:
        return "buy"
    if "sale" in v:
        return "sell"
    if "exchange" in v:
        return "exchange"
    return None


def parse_stock_watcher_rows(
    rows: list[dict[str, Any]], chamber: str
) -> list[dict[str, Any]]:
    """Normalize Senate ('senator' field) / House ('representative' field)
    Stock Watcher rows into fact_congress_trade columns."""
    parsed = []
    for row in rows:
        ticker = (row.get("ticker") or "").strip().upper()
        if not ticker or ticker in {"--", "N/A", "NONE"}:
            continue
        tx_type = _normalize_tx_type(row.get("type"))
        tx_date = _parse_date(row.get("transaction_date"))
        if tx_type is None or tx_date is None:
            continue
        member = row.get("senator") or row.get("representative") or "unknown"
        low, high = _parse_amount_range(row.get("amount"))
        parsed.append(
            {
                "chamber": chamber,
                "member": member.strip(),
                "ticker": ticker,
                "transaction_date": tx_date,
                "disclosure_date": _parse_date(row.get("disclosure_date")),
                "tx_type": tx_type,
                "amount_low": low,
                "amount_high": high,
                "raw": row,
                "source": f"{chamber}_stock_watcher",
            }
        )
    return parsed


def upsert_trades(db: Session, rows: list[dict[str, Any]]) -> int:
    existing = {
        (r.chamber, r.member, r.ticker, r.transaction_date, r.tx_type, r.amount_low)
        for r in db.scalars(select(FactCongressTrade))
    }
    count = 0
    for row in rows:
        key = (
            row["chamber"],
            row["member"],
            row["ticker"],
            row["transaction_date"],
            row["tx_type"],
            row["amount_low"],
        )
        if key in existing:
            continue
        existing.add(key)
        db.add(FactCongressTrade(**row))
        count += 1
    db.commit()
    return count


def ingest(db: Session) -> int:
    watchlist = set(db.scalars(select(WatchlistItem.ticker)))
    if not watchlist:
        return 0
    count = 0
    with http.client() as client:
        for chamber, url in (("senate", SENATE_URL), ("house", HOUSE_URL)):
            payload = client.get(url).raise_for_status().json()
            rows = parse_stock_watcher_rows(payload, chamber)
            rows = [r for r in rows if r["ticker"] in watchlist]
            count += upsert_trades(db, rows)
    return count

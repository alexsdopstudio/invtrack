"""Senate/House Stock Watcher aggregate JSON -> fact_congress_trade.

These community-maintained datasets parse the official STOCK Act disclosures
(efdsearch.senate.gov / disclosures-clerk.house.gov) into structured JSON.
Disclosures are legally delayed up to 45 days, so this is a lagging signal.
Only trades for tickers currently on the watchlist are stored.
"""

import logging
import re
from datetime import date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import FactCongressTrade, WatchlistItem
from . import http

logger = logging.getLogger(__name__)

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


def fetch_chamber_rows(client: httpx.Client, chamber: str, url: str) -> list[dict[str, Any]]:
    payload = client.get(url).raise_for_status().json()
    return parse_stock_watcher_rows(payload, chamber)


def ingest(db: Session) -> int:
    watchlist = set(db.scalars(select(WatchlistItem.ticker)))
    if not watchlist:
        return 0
    settings = get_settings()
    sources = (("senate", settings.senate_data_url), ("house", settings.house_data_url))
    count = 0
    errors = []
    any_success = False
    with http.client() as client:
        # Each chamber is isolated: these community datasets go stale or
        # disappear independently, and one dying must not block the other.
        for chamber, url in sources:
            try:
                rows = fetch_chamber_rows(client, chamber, url)
                count += upsert_trades(db, [r for r in rows if r["ticker"] in watchlist])
                any_success = True
            except Exception as exc:  # noqa: BLE001 - per-chamber isolation
                logger.warning("congress ingest failed for %s (%s): %s", chamber, url, exc)
                errors.append(f"{chamber}: {exc}")
    if errors and not any_success:
        raise RuntimeError(
            "all congressional sources failed — the community Stock Watcher datasets "
            "may be unavailable; override SENATE_DATA_URL / HOUSE_DATA_URL in .env "
            f"if they have moved. ({'; '.join(errors)})"
        )
    return count

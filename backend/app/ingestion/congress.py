"""Congressional trades -> fact_congress_trade.

Senate: official efdsearch.senate.gov PTRs (see senate_efd.py) — the
community Stock Watcher dataset is defunct (verified July 2026).
House: Stock Watcher-shaped aggregate JSON, URL overridable via
HOUSE_DATA_URL (the original bucket is also defunct; official House PTRs are
PDFs and need a dedicated parser — roadmap).

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
from . import http, senate_efd

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


def fetch_senate_rows(client: httpx.Client) -> list[dict[str, Any]]:
    return parse_stock_watcher_rows(senate_efd.fetch_rows(client), "senate")


def fetch_house_rows(client: httpx.Client) -> list[dict[str, Any]]:
    return fetch_chamber_rows(client, "house", get_settings().house_data_url)


def ingest(db: Session) -> int:
    watchlist = set(db.scalars(select(WatchlistItem.ticker)))
    if not watchlist:
        return 0
    sources = (("senate", fetch_senate_rows), ("house", fetch_house_rows))
    count = 0
    errors = []
    any_success = False
    with http.client() as client:
        # Chambers are isolated: sources fail independently, and one dying
        # must not block the other.
        for chamber, fetch in sources:
            try:
                rows = fetch(client)
                count += upsert_trades(db, [r for r in rows if r["ticker"] in watchlist])
                any_success = True
            except Exception as exc:  # noqa: BLE001 - per-chamber isolation
                logger.warning("congress ingest failed for %s: %s", chamber, exc)
                errors.append(f"{chamber}: {exc}")
    if errors and not any_success:
        raise RuntimeError(
            "all congressional sources failed — senate reads the official "
            "efdsearch.senate.gov; house needs HOUSE_DATA_URL pointed at a live "
            f"Stock Watcher-shaped dataset. ({'; '.join(errors)})"
        )
    return count

"""One-off backfills for columns added after data was already ingested.

backfill_10b51: rows ingested before the 10b5-1 plan flag was parsed have
is_10b5_1 = NULL. The stored raw payload doesn't include the flag, so this
re-fetches each filing's ownership XML from EDGAR (throttled, per-filing
isolated) and updates the rows in place. Run once on a machine with network
access; already-flagged rows are never touched.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ingestion import http
from .ingestion.insider_marketwide import _fetch_filing_rows
from .models import FactInsiderTrade

logger = logging.getLogger(__name__)


def backfill_10b51(db: Session) -> tuple[int, int]:
    """Returns (rows updated, filings failed)."""
    pending = db.scalars(
        select(FactInsiderTrade).where(FactInsiderTrade.is_10b5_1.is_(None))
    ).all()
    by_accession: dict[str, list[FactInsiderTrade]] = {}
    for t in pending:
        by_accession.setdefault(t.accession_no, []).append(t)

    updated = failed = 0
    with http.client() as client:
        for accession, trades in by_accession.items():
            cik = next((t.cik for t in trades if t.cik), None)
            if cik is None:
                failed += 1
                continue
            try:
                rows = _fetch_filing_rows(client, int(cik), accession)
            except Exception as exc:  # noqa: BLE001 - per-filing isolation
                logger.warning("backfill fetch failed for %s: %s", accession, exc)
                failed += 1
                continue
            flags = {r["row_index"]: r.get("is_10b5_1") for r in rows}
            for t in trades:
                if flags.get(t.row_index) is not None:
                    t.is_10b5_1 = flags[t.row_index]
                    updated += 1
            db.commit()
    return updated, failed

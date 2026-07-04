"""Job wrapper: every ingestion source runs inside run_job(), which records an
ingestion_run audit row and isolates failures so one broken source never
blocks the others (free/unofficial sources go down or change format)."""

import logging
import traceback
from collections.abc import Callable

from sqlalchemy.orm import Session

from ..models import IngestionRun, utcnow

logger = logging.getLogger(__name__)


def run_job(db: Session, source: str, fn: Callable[[Session], int]) -> IngestionRun:
    run = IngestionRun(source=source, status="running")
    db.add(run)
    db.commit()
    try:
        run.rows_upserted = fn(db)
        run.status = "ok"
        db.commit()
    except Exception as exc:  # noqa: BLE001 - isolation is the point
        db.rollback()
        logger.exception("ingestion job %s failed", source)
        run.status = "error"
        run.error = f"{exc}\n{traceback.format_exc(limit=5)}"
        db.commit()
    finally:
        run.finished_at = utcnow()
        db.commit()
    return run


def run_sources(db: Session, sources: list[str]) -> list[IngestionRun]:
    # Imported lazily so a broken optional dependency (e.g. yfinance) only
    # affects its own source.
    from . import congress, fundamentals, insider, prices, tickers

    jobs: dict[str, Callable[[Session], int]] = {
        "tickers": tickers.ingest,
        "congress": congress.ingest,
        "insider": insider.ingest,
        "fundamentals": fundamentals.ingest,
        "prices": prices.ingest,
    }
    runs = []
    for source in sources:
        if source not in jobs:
            raise ValueError(f"unknown ingestion source: {source}")
        runs.append(run_job(db, source, jobs[source]))
    return runs


ALL_SOURCES = ["tickers", "congress", "insider", "fundamentals", "prices"]

"""Daily auto-refresh: ingest all sources, rescore, detect alerts — the same
pipeline as POST /api/ingest/all, on a schedule. Nobody should have to click
'Refresh' to find out a senator traded their stock."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .alerts import detect_alerts
from .config import get_settings
from .db import SessionLocal
from .ingestion.runner import ALL_SOURCES, run_sources
from .scoring import engine

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def refresh_job() -> None:
    logger.info("auto-refresh: starting scheduled ingestion")
    with SessionLocal() as db:
        runs = run_sources(db, ALL_SOURCES)
        engine.compute_and_store(db)
        created = detect_alerts(db)
    summary = ", ".join(f"{r.source}:{r.status}" for r in runs)
    logger.info("auto-refresh done (%s); %d new alerts", summary, len(created))


def start() -> BackgroundScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.auto_refresh_enabled:
        logger.info("auto-refresh disabled (AUTO_REFRESH_ENABLED=false)")
        return None
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        refresh_job,
        CronTrigger(hour=settings.auto_refresh_hour, minute=0),
        id="daily_refresh",
        coalesce=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("auto-refresh scheduled daily at %02d:00", settings.auto_refresh_hour)
    return _scheduler


def next_run_time() -> str | None:
    if _scheduler is None:
        return None
    job = _scheduler.get_job("daily_refresh")
    return job.next_run_time.isoformat() if job and job.next_run_time else None


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

"""Alert engine: turns new signals into an in-app feed (and an optional
webhook push). Detection is idempotent — every alert carries a dedupe_key
derived from the triggering event's natural key, so re-running detection
after every ingest creates nothing twice."""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Alert, FactCongressTrade, FactInsiderTrade, Score, WatchlistItem

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 7  # only alert on events ingested/disclosed recently
SCORE_BULLISH = 60.0
SCORE_BEARISH = 40.0


def _fmt_amount(low: float | None, high: float | None) -> str:
    if low is None:
        return "undisclosed amount"
    if high is not None:
        return f"${low:,.0f}–${high:,.0f}"
    return f"${low:,.0f}+"


def _add(db: Session, existing: set[str], alerts: list[Alert], **kwargs: Any) -> None:
    if kwargs["dedupe_key"] in existing:
        return
    existing.add(kwargs["dedupe_key"])
    alert = Alert(**kwargs)
    db.add(alert)
    alerts.append(alert)


def detect_alerts(db: Session, today: date | None = None) -> list[Alert]:
    """Scan recent data for alert-worthy events on watchlist tickers.
    Returns only newly created alerts."""
    today = today or date.today()
    watchlist = set(db.scalars(select(WatchlistItem.ticker)))
    if not watchlist:
        return []
    existing = set(db.scalars(select(Alert.dedupe_key)))
    created: list[Alert] = []
    window_start = today - timedelta(days=LOOKBACK_DAYS)

    # New congressional trades (disclosure recency, since trades lag by law)
    congress = db.scalars(
        select(FactCongressTrade).where(
            FactCongressTrade.ticker.in_(watchlist),
            FactCongressTrade.tx_type.in_(["buy", "sell"]),
        )
    )
    for t in congress:
        signal_date = t.disclosure_date or t.transaction_date
        if signal_date < window_start:
            continue
        key = f"congress:{t.chamber}:{t.member}:{t.ticker}:{t.transaction_date}:{t.tx_type}:{t.amount_low}"
        verb = "bought" if t.tx_type == "buy" else "sold"
        _add(
            db, existing, created,
            ticker=t.ticker,
            kind="congress_trade",
            title=f"{t.member} {verb} {t.ticker}",
            body=(
                f"{t.member} ({t.chamber}) {verb} {_fmt_amount(t.amount_low, t.amount_high)} "
                f"of {t.ticker} on {t.transaction_date} (disclosed {t.disclosure_date or 'n/a'})."
            ),
            dedupe_key=key,
            payload={"member": t.member, "tx_type": t.tx_type, "transaction_date": str(t.transaction_date)},
        )

    # New insider trades (open-market buys/sells)
    insiders = db.scalars(
        select(FactInsiderTrade).where(
            FactInsiderTrade.ticker.in_(watchlist),
            FactInsiderTrade.code.in_(["P", "S"]),
            FactInsiderTrade.transaction_date >= window_start,
        )
    )
    for t in insiders:
        verb = "bought" if t.code == "P" else "sold"
        value = f"${t.value:,.0f} of " if t.value else ""
        _add(
            db, existing, created,
            ticker=t.ticker,
            kind="insider_trade",
            title=f"Insider {verb} {t.ticker}",
            body=(
                f"{t.insider_name or 'An insider'}"
                f"{f' ({t.insider_title})' if t.insider_title else ''} {verb} "
                f"{value}{t.ticker} on {t.transaction_date} (SEC Form 4)."
            ),
            dedupe_key=f"insider:{t.accession_no}:{t.row_index}",
            payload={"insider": t.insider_name, "code": t.code, "value": t.value},
        )

    # Score threshold crossings (latest vs previous score)
    for ticker in watchlist:
        latest_two = db.scalars(
            select(Score)
            .where(Score.ticker == ticker)
            .order_by(Score.computed_at.desc())
            .limit(2)
        ).all()
        if len(latest_two) < 2:
            continue
        latest, previous = latest_two[0], latest_two[1]
        direction = None
        if previous.total < SCORE_BULLISH <= latest.total:
            direction, label = "up", f"crossed above {SCORE_BULLISH:.0f} (leaning bullish)"
        elif previous.total > SCORE_BEARISH >= latest.total:
            direction, label = "down", f"crossed below {SCORE_BEARISH:.0f} (leaning bearish)"
        if direction is None:
            continue
        _add(
            db, existing, created,
            ticker=ticker,
            kind="score_cross",
            title=f"{ticker} score {label.split(' (')[0]}",
            body=(
                f"{ticker}'s composite score moved {previous.total:.0f} → {latest.total:.0f} "
                f"and {label}. Open the ticker for the component breakdown."
            ),
            dedupe_key=f"score:{ticker}:{direction}:{today}",
            payload={"from": previous.total, "to": latest.total, "direction": direction},
        )

    db.commit()
    if created:
        _push_webhook(created)
    return created


def _push_webhook(alerts: list[Alert]) -> None:
    """Optional push: JSON superset so Slack ('text'), Discord ('content'),
    ntfy and generic receivers all work. Failures never break the pipeline."""
    url = get_settings().alert_webhook_url
    if not url:
        return
    try:
        with httpx.Client(timeout=10.0) as client:
            for alert in alerts:
                message = f"{alert.title} — {alert.body}"
                client.post(
                    url,
                    json={
                        "title": alert.title,
                        "body": alert.body,
                        "text": message,
                        "content": message,
                        "ticker": alert.ticker,
                        "kind": alert.kind,
                    },
                )
    except Exception as exc:  # noqa: BLE001 - alerts must never break ingestion
        logger.warning("alert webhook delivery failed: %s", exc)


def mark_all_seen(db: Session) -> int:
    alerts = db.scalars(select(Alert).where(Alert.seen.is_(False))).all()
    for alert in alerts:
        alert.seen = True
    db.commit()
    return len(alerts)


def seed_demo_alert_time(days_ago: int) -> datetime:
    """Helper for the demo seed: a timezone-aware timestamp in the past."""
    return datetime.combine(
        date.today() - timedelta(days=days_ago), time(hour=14), tzinfo=timezone.utc
    )

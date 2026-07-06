"""Which tickers do we enrich and score?

The watchlist is the user's own list. Discovery targets are (a) tickers with
the strongest recent congressional net buying and (b) tickers where several
insiders just bought on the open market (found by the market-wide Form 4
scan) — they power the dashboard's Radar sections, and we fetch fundamentals/
prices/insider data for them too so their scores are comparable. An optional
universe file (UNIVERSE_FILE) widens the screener beyond discovery."""

import logging
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import FactCongressTrade, FactInsiderTrade, WatchlistItem

logger = logging.getLogger(__name__)

DISCOVERY_LIMIT = 25
DISCOVERY_WINDOW_DAYS = 90
INSIDER_CLUSTER_LIMIT = 15
INSIDER_CLUSTER_WINDOW_DAYS = 30
INSIDER_CLUSTER_MIN_BUYERS = 2


def _signed_midpoint():
    mid = (
        FactCongressTrade.amount_low
        + func.coalesce(FactCongressTrade.amount_high, FactCongressTrade.amount_low)
    ) / 2.0
    return func.coalesce(
        case(
            (FactCongressTrade.tx_type == "buy", mid),
            (FactCongressTrade.tx_type == "sell", -mid),
            else_=0.0,
        ),
        0.0,
    )


def activity_date():
    return func.coalesce(
        FactCongressTrade.disclosure_date, FactCongressTrade.transaction_date
    )


def discovered_tickers(db: Session, limit: int = DISCOVERY_LIMIT) -> list[str]:
    since = date.today() - timedelta(days=DISCOVERY_WINDOW_DAYS)
    stmt = (
        select(FactCongressTrade.ticker)
        .where(
            activity_date() >= since,
            FactCongressTrade.ticker.not_in(select(WatchlistItem.ticker)),
        )
        .group_by(FactCongressTrade.ticker)
        .order_by(func.sum(_signed_midpoint()).desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def insider_cluster_tickers(
    db: Session, limit: int = INSIDER_CLUSTER_LIMIT
) -> list[str]:
    """Tickers where >= INSIDER_CLUSTER_MIN_BUYERS distinct insiders bought on
    the open market recently, ranked by total buy dollars — the market-wide
    scan's discovery output."""
    since = date.today() - timedelta(days=INSIDER_CLUSTER_WINDOW_DAYS)
    t = FactInsiderTrade
    stmt = (
        select(t.ticker)
        .where(
            t.code == "P",
            t.transaction_date >= since,
            t.ticker != "",
            t.ticker.not_in(select(WatchlistItem.ticker)),
        )
        .group_by(t.ticker)
        .having(func.count(func.distinct(t.insider_name)) >= INSIDER_CLUSTER_MIN_BUYERS)
        .order_by(func.sum(func.coalesce(t.value, 0.0)).desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def universe_tickers() -> list[str]:
    """Optional user-provided universe file: one ticker per line, # comments.
    Missing/unreadable file logs a warning and contributes nothing."""
    settings = get_settings()
    if not settings.universe_file:
        return []
    try:
        lines = Path(settings.universe_file).read_text().splitlines()
    except OSError as exc:
        logger.warning("universe file %s unreadable: %s", settings.universe_file, exc)
        return []
    tickers = []
    for line in lines:
        t = line.split("#")[0].strip().upper()
        if t:
            tickers.append(t)
    return tickers[: settings.universe_limit]


def target_tickers(db: Session) -> list[str]:
    """Watchlist first, then discovery candidates (congress + insider
    clusters), then the optional universe file (deduplicated)."""
    watch = list(db.scalars(select(WatchlistItem.ticker)))
    return list(
        dict.fromkeys(
            [
                *watch,
                *discovered_tickers(db),
                *insider_cluster_tickers(db),
                *universe_tickers(),
            ]
        )
    )

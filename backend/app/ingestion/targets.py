"""Which tickers do we enrich and score?

The watchlist is the user's own list. Discovery targets are tickers with the
strongest recent congressional net buying that are NOT on the watchlist —
they power the dashboard's Radar section, and we fetch fundamentals/prices/
insider data for them too so their scores are comparable."""

from datetime import date, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models import FactCongressTrade, WatchlistItem

DISCOVERY_LIMIT = 25
DISCOVERY_WINDOW_DAYS = 90


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


def target_tickers(db: Session) -> list[str]:
    """Watchlist first, then top discovery candidates (deduplicated)."""
    watch = list(db.scalars(select(WatchlistItem.ticker)))
    return list(dict.fromkeys([*watch, *discovered_tickers(db)]))

"""CTE-based read-model queries for the dashboard, Radar and detail views."""

import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .ingestion.targets import (
    DISCOVERY_WINDOW_DAYS,
    INSIDER_CLUSTER_MIN_BUYERS,
    INSIDER_CLUSTER_WINDOW_DAYS,
    activity_date,
)
from .models import (
    DimTicker,
    FactCongressTrade,
    FactInsiderTrade,
    FactPrice,
    Score,
    WatchlistItem,
)

SPARKLINE_DAYS = 90


def latest_score_cte():
    ranked = select(
        Score,
        func.row_number()
        .over(partition_by=Score.ticker, order_by=Score.computed_at.desc())
        .label("rn"),
    ).cte("ranked_scores")
    return ranked


def dashboard_rows(db: Session) -> list[dict]:
    ranked_scores = latest_score_cte()

    last_congress = (
        select(
            FactCongressTrade.ticker,
            func.max(FactCongressTrade.transaction_date).label("last_date"),
        )
        .group_by(FactCongressTrade.ticker)
        .cte("last_congress")
    )
    last_insider = (
        select(
            FactInsiderTrade.ticker,
            func.max(FactInsiderTrade.transaction_date).label("last_date"),
        )
        .group_by(FactInsiderTrade.ticker)
        .cte("last_insider")
    )
    last_price = (
        select(
            FactPrice.ticker,
            func.max(FactPrice.date).label("last_date"),
        )
        .group_by(FactPrice.ticker)
        .cte("last_price")
    )

    stmt = (
        select(
            WatchlistItem.ticker,
            WatchlistItem.notes,
            DimTicker.name,
            DimTicker.sector,
            ranked_scores.c.total,
            ranked_scores.c.computed_at,
            ranked_scores.c.components,
            last_congress.c.last_date.label("last_congress_activity"),
            last_insider.c.last_date.label("last_insider_activity"),
            FactPrice.close.label("last_close"),
        )
        .join(DimTicker, DimTicker.ticker == WatchlistItem.ticker)
        .outerjoin(
            ranked_scores,
            (ranked_scores.c.ticker == WatchlistItem.ticker) & (ranked_scores.c.rn == 1),
        )
        .outerjoin(last_congress, last_congress.c.ticker == WatchlistItem.ticker)
        .outerjoin(last_insider, last_insider.c.ticker == WatchlistItem.ticker)
        .outerjoin(last_price, last_price.c.ticker == WatchlistItem.ticker)
        .outerjoin(
            FactPrice,
            (FactPrice.ticker == last_price.c.ticker)
            & (FactPrice.date == last_price.c.last_date),
        )
        .order_by(ranked_scores.c.total.desc().nulls_last(), WatchlistItem.ticker)
    )
    rows = [dict(r._mapping) for r in db.execute(stmt)]

    from .risk import risk_flags  # local import to avoid a module cycle

    sparklines = _sparklines(db, [r["ticker"] for r in rows])
    for r in rows:
        r["sparkline"] = sparklines.get(r["ticker"], [])
        r["score"] = r.pop("total")
        r["score_computed_at"] = r.pop("computed_at")
        r["risk_count"] = len(risk_flags(db, r["ticker"]))
    return rows


def _sparklines(db: Session, tickers: list[str]) -> dict[str, list[float]]:
    if not tickers:
        return {}
    since = date.today() - timedelta(days=SPARKLINE_DAYS)
    stmt = (
        select(FactPrice.ticker, FactPrice.date, FactPrice.close)
        .where(FactPrice.ticker.in_(tickers), FactPrice.date >= since)
        .order_by(FactPrice.ticker, FactPrice.date)
    )
    out: dict[str, list[float]] = {}
    for ticker, _d, close in db.execute(stmt):
        if close is not None:
            out.setdefault(ticker, []).append(round(close, 2))
    return out


def idea_rows(db: Session, limit: int = 20) -> list[dict]:
    """Radar: non-watchlist tickers with recent congressional activity, ranked
    by score (when available) then by net congressional buying."""
    since = date.today() - timedelta(days=DISCOVERY_WINDOW_DAYS)
    t = FactCongressTrade
    mid = (t.amount_low + func.coalesce(t.amount_high, t.amount_low)) / 2.0
    signed = func.coalesce(
        case((t.tx_type == "buy", mid), (t.tx_type == "sell", -mid), else_=0.0), 0.0
    )
    congress_agg = (
        select(
            t.ticker,
            func.sum(case((t.tx_type == "buy", 1), else_=0)).label("buys"),
            func.sum(case((t.tx_type == "sell", 1), else_=0)).label("sells"),
            func.count(
                func.distinct(case((t.tx_type == "buy", t.member), else_=None))
            ).label("buyers"),
            func.max(activity_date()).label("last_activity"),
            func.sum(signed).label("net_dollars"),
        )
        .where(
            activity_date() >= since,
            t.ticker.not_in(select(WatchlistItem.ticker)),
        )
        .group_by(t.ticker)
        .cte("congress_activity")
    )
    ranked_scores = latest_score_cte()
    last_price = (
        select(FactPrice.ticker, func.max(FactPrice.date).label("last_date"))
        .group_by(FactPrice.ticker)
        .cte("idea_last_price")
    )

    stmt = (
        select(
            congress_agg.c.ticker,
            congress_agg.c.buys,
            congress_agg.c.sells,
            congress_agg.c.buyers,
            congress_agg.c.last_activity,
            congress_agg.c.net_dollars,
            DimTicker.name,
            DimTicker.sector,
            ranked_scores.c.total.label("score"),
            ranked_scores.c.components,
            FactPrice.close.label("last_close"),
        )
        .outerjoin(DimTicker, DimTicker.ticker == congress_agg.c.ticker)
        .outerjoin(
            ranked_scores,
            (ranked_scores.c.ticker == congress_agg.c.ticker) & (ranked_scores.c.rn == 1),
        )
        .outerjoin(last_price, last_price.c.ticker == congress_agg.c.ticker)
        .outerjoin(
            FactPrice,
            (FactPrice.ticker == last_price.c.ticker)
            & (FactPrice.date == last_price.c.last_date),
        )
        .order_by(
            ranked_scores.c.total.desc().nulls_last(),
            congress_agg.c.net_dollars.desc(),
        )
        .limit(limit)
    )
    rows = [dict(r._mapping) for r in db.execute(stmt)]
    sparklines = _sparklines(db, [r["ticker"] for r in rows])
    for r in rows:
        r["sparkline"] = sparklines.get(r["ticker"], [])
        r["net_dollars"] = round(r["net_dollars"] or 0.0, 2)
    return rows


def insider_idea_rows(db: Session, limit: int = 20) -> list[dict]:
    """Insider Radar: non-watchlist tickers where several distinct insiders
    bought on the open market recently (market-wide Form 4 scan), ranked by
    score (when available) then by total buy dollars."""
    since = date.today() - timedelta(days=INSIDER_CLUSTER_WINDOW_DAYS)
    t = FactInsiderTrade
    clusters = (
        select(
            t.ticker,
            func.count(func.distinct(t.insider_name)).label("buyers"),
            func.count(t.id).label("buys"),
            func.sum(func.coalesce(t.value, 0.0)).label("total_value"),
            func.max(t.transaction_date).label("last_activity"),
        )
        .where(
            t.code == "P",
            t.transaction_date >= since,
            t.ticker != "",
            t.ticker.not_in(select(WatchlistItem.ticker)),
        )
        .group_by(t.ticker)
        .having(func.count(func.distinct(t.insider_name)) >= INSIDER_CLUSTER_MIN_BUYERS)
        .cte("insider_clusters")
    )
    ranked_scores = latest_score_cte()
    last_price = (
        select(FactPrice.ticker, func.max(FactPrice.date).label("last_date"))
        .group_by(FactPrice.ticker)
        .cte("cluster_last_price")
    )

    stmt = (
        select(
            clusters.c.ticker,
            clusters.c.buyers,
            clusters.c.buys,
            clusters.c.total_value,
            clusters.c.last_activity,
            DimTicker.name,
            DimTicker.sector,
            ranked_scores.c.total.label("score"),
            ranked_scores.c.components,
            FactPrice.close.label("last_close"),
        )
        .outerjoin(DimTicker, DimTicker.ticker == clusters.c.ticker)
        .outerjoin(
            ranked_scores,
            (ranked_scores.c.ticker == clusters.c.ticker) & (ranked_scores.c.rn == 1),
        )
        .outerjoin(last_price, last_price.c.ticker == clusters.c.ticker)
        .outerjoin(
            FactPrice,
            (FactPrice.ticker == last_price.c.ticker)
            & (FactPrice.date == last_price.c.last_date),
        )
        .order_by(
            ranked_scores.c.total.desc().nulls_last(),
            clusters.c.total_value.desc(),
        )
        .limit(limit)
    )
    rows = [dict(r._mapping) for r in db.execute(stmt)]
    sparklines = _sparklines(db, [r["ticker"] for r in rows])
    for r in rows:
        r["sparkline"] = sparklines.get(r["ticker"], [])
        r["total_value"] = round(r["total_value"] or 0.0, 2)
    return rows


TRADING_DAYS_PER_YEAR = 252
MIN_STATS_POINTS = 60


def price_stats(db: Session, ticker: str) -> dict[str, Any] | None:
    """Historical stats for the returns calculator: 1y CAGR, annualized
    volatility, worst drawdown, ATR(14). Purely descriptive of the ingested
    price history — never a forecast."""
    rows = db.execute(
        select(FactPrice.date, FactPrice.high, FactPrice.low, FactPrice.close)
        .where(FactPrice.ticker == ticker, FactPrice.close.is_not(None))
        .order_by(FactPrice.date)
    ).all()
    if len(rows) < MIN_STATS_POINTS:
        return None

    closes = [r.close for r in rows]
    span_days = max((rows[-1].date - rows[0].date).days, 1)
    cagr = (closes[-1] / closes[0]) ** (365.0 / span_days) - 1.0

    log_returns = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0]
    mean = sum(log_returns) / len(log_returns)
    variance = sum((x - mean) ** 2 for x in log_returns) / max(len(log_returns) - 1, 1)
    annual_vol = math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR)

    peak = closes[0]
    max_drawdown = 0.0
    for c in closes:
        peak = max(peak, c)
        max_drawdown = min(max_drawdown, c / peak - 1.0)

    trs = []
    for prev, r in zip(rows, rows[1:]):
        if r.high is None or r.low is None or prev.close is None:
            continue
        trs.append(max(r.high - r.low, abs(r.high - prev.close), abs(r.low - prev.close)))
    atr_14 = sum(trs[-14:]) / min(len(trs), 14) if trs else None

    return {
        "ticker": ticker,
        "cagr_1y": round(cagr, 4),
        "annual_vol": round(annual_vol, 4),
        "max_drawdown": round(max_drawdown, 4),
        "atr_14": round(atr_14, 4) if atr_14 is not None else None,
        "last_close": closes[-1],
        "data_points": len(closes),
        "first_date": rows[0].date,
        "last_date": rows[-1].date,
    }


def score_history(db: Session, ticker: str, days: int = 120) -> list[dict[str, Any]]:
    """Daily score series (last computation per day) with per-component
    contribution deltas vs the previous day — answers 'why did my score
    change' server-side."""
    since = date.today() - timedelta(days=days)
    scores = db.scalars(
        select(Score)
        .where(Score.ticker == ticker, Score.computed_at >= since)
        .order_by(Score.computed_at.asc())
    ).all()

    by_day: dict[date, Score] = {}
    for s in scores:
        by_day[s.computed_at.date()] = s  # ascending order -> last per day wins

    entries: list[dict[str, Any]] = []
    previous: Score | None = None
    for day in sorted(by_day):
        s = by_day[day]
        contributions = {
            name: comp.get("contribution", 0.0)
            for name, comp in (s.components or {}).items()
        }
        deltas: dict[str, float] | None = None
        total_delta: float | None = None
        if previous is not None:
            prev_contributions = {
                name: comp.get("contribution", 0.0)
                for name, comp in (previous.components or {}).items()
            }
            deltas = {
                name: round(contributions.get(name, 0.0) - prev_contributions.get(name, 0.0), 2)
                for name in set(contributions) | set(prev_contributions)
            }
            total_delta = round(s.total - previous.total, 2)
        entries.append(
            {
                "date": day,
                "total": s.total,
                "contributions": {k: round(v, 2) for k, v in contributions.items()},
                "deltas": deltas,
                "total_delta": total_delta,
            }
        )
        previous = s
    return entries


def latest_score_for(db: Session, ticker: str) -> Score | None:
    return db.scalar(
        select(Score)
        .where(Score.ticker == ticker)
        .order_by(Score.computed_at.desc())
        .limit(1)
    )

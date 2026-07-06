"""Congressional trading sub-score (0-100, 50 = neutral).

Net recency-decayed dollar flow of watchlisted-member trades, squashed with
tanh, plus a cluster bonus when several members trade the same direction in a
short window. Decay uses disclosure_date because STOCK Act disclosures lag the
trade by up to 45 days — this signal is explicitly lagging.
"""

import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FactCongressTrade


def _midpoint(low: float | None, high: float | None) -> float:
    if low is None:
        return 0.0
    return (low + high) / 2.0 if high is not None else low


def compute(db: Session, ticker: str, config: dict[str, Any], today: date) -> dict[str, Any] | None:
    cfg = config["congress"]
    lookback_start = today - timedelta(days=cfg["lookback_days"])
    trades = db.scalars(
        select(FactCongressTrade).where(
            FactCongressTrade.ticker == ticker,
            FactCongressTrade.tx_type.in_(["buy", "sell"]),
        )
    ).all()
    trades = [
        t for t in trades
        if (t.disclosure_date or t.transaction_date) >= lookback_start
        and (t.disclosure_date or t.transaction_date) <= today
    ]
    if not trades:
        return None

    # Skill weighting: scale each member's dollars by their own historical
    # track record (see trackrecord.member_weights). {} when disabled or when
    # too few members have measurable history — everyone then counts as 1.0.
    from ..trackrecord import member_weights  # local import: avoid module cycle

    weights = member_weights(db, config, today)

    half_life = cfg["decay_half_life_days"]
    net = 0.0
    buys = sells = 0
    weights_used: dict[str, float] = {}
    for t in trades:
        signal_date = t.disclosure_date or t.transaction_date
        age = (today - signal_date).days
        decay = 0.5 ** (age / half_life)
        sign = 1.0 if t.tx_type == "buy" else -1.0
        member_weight = weights.get(t.member, 1.0)
        weights_used[t.member] = member_weight
        net += sign * _midpoint(t.amount_low, t.amount_high) * decay * member_weight
        buys += t.tx_type == "buy"
        sells += t.tx_type == "sell"

    score = 50.0 + 50.0 * math.tanh(net / cfg["dollar_scale"])

    cluster_start = today - timedelta(days=cfg["cluster_window_days"])
    recent = [t for t in trades if (t.disclosure_date or t.transaction_date) >= cluster_start]
    buy_members = {t.member for t in recent if t.tx_type == "buy"}
    sell_members = {t.member for t in recent if t.tx_type == "sell"}
    cluster = None
    if len(buy_members) >= cfg["cluster_min_members"]:
        score += cfg["cluster_bonus"]
        cluster = {"direction": "buy", "members": sorted(buy_members)}
    elif len(sell_members) >= cfg["cluster_min_members"]:
        score -= cfg["cluster_bonus"]
        cluster = {"direction": "sell", "members": sorted(sell_members)}

    latest = max(t.disclosure_date or t.transaction_date for t in trades)
    return {
        "score": max(0.0, min(100.0, score)),
        "source": "official STOCK Act disclosures (efdsearch.senate.gov / house dataset)",
        "data_as_of": latest.isoformat(),
        "inputs": {
            "trades_in_window": len(trades),
            "buys": buys,
            "sells": sells,
            "net_decayed_dollars": round(net, 2),
            "lookback_days": cfg["lookback_days"],
            "cluster": cluster,
            "member_weights": weights_used,
            "note": "lagging signal: disclosures are legally delayed up to 45 days",
        },
    }

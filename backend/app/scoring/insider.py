"""Corporate insider (SEC Form 4) sub-score (0-100, 50 = neutral).

Open-market buys (code P) minus discounted sells (code S) over the lookback,
dollar-weighted with recency decay. Selling is discounted because insiders
sell for many non-signal reasons (taxes, diversification, 10b5-1 plans);
open-market buying is the strong signal. A cluster bonus applies when several
distinct insiders buy within a short window.
"""

import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FactInsiderTrade


def compute(db: Session, ticker: str, config: dict[str, Any], today: date) -> dict[str, Any] | None:
    cfg = config["insider"]
    lookback_start = today - timedelta(days=cfg["lookback_days"])
    trades = db.scalars(
        select(FactInsiderTrade).where(
            FactInsiderTrade.ticker == ticker,
            FactInsiderTrade.code.in_(["P", "S"]),
            FactInsiderTrade.transaction_date >= lookback_start,
            FactInsiderTrade.transaction_date <= today,
        )
    ).all()
    trades = [t for t in trades if t.value]
    if not trades:
        return None

    half_life = cfg["decay_half_life_days"]
    officer_weight = cfg.get("officer_weight", 1.0)
    director_weight = cfg.get("director_weight", 1.0)
    plan_sale_discount = cfg.get("plan_sale_discount", 0.0)
    net = 0.0
    buy_dollars = sell_dollars = 0.0
    plan_sales_muted = 0
    for t in trades:
        decay = 0.5 ** ((today - t.transaction_date).days / half_life)
        if t.code == "P":
            # A CFO buying with their own money is a stronger signal than a
            # board member's token purchase.
            role_weight = (
                officer_weight if t.is_officer
                else director_weight if t.is_director
                else 1.0
            )
            net += t.value * decay * role_weight
            buy_dollars += t.value
        else:
            # Pre-scheduled (10b5-1 plan) sales carry no timing signal.
            discount = plan_sale_discount if t.is_10b5_1 else cfg["sell_discount"]
            plan_sales_muted += bool(t.is_10b5_1)
            net -= discount * t.value * decay
            sell_dollars += t.value

    score = 50.0 + 50.0 * math.tanh(net / cfg["dollar_scale"])

    cluster_start = today - timedelta(days=cfg["cluster_window_days"])
    buyers = {
        t.insider_name
        for t in trades
        if t.code == "P" and t.transaction_date >= cluster_start
    }
    cluster = None
    if len(buyers) >= cfg["cluster_min_insiders"]:
        score += cfg["cluster_bonus"]
        cluster = {"direction": "buy", "insiders": sorted(b for b in buyers if b)}

    latest = max(t.transaction_date for t in trades)
    return {
        "score": max(0.0, min(100.0, score)),
        "source": "SEC EDGAR Form 4",
        "data_as_of": latest.isoformat(),
        "inputs": {
            "trades_in_window": len(trades),
            "buy_dollars": round(buy_dollars, 2),
            "sell_dollars": round(sell_dollars, 2),
            "sell_discount": cfg["sell_discount"],
            "officer_weight": officer_weight,
            "plan_sales_muted": plan_sales_muted,
            "net_decayed_dollars": round(net, 2),
            "lookback_days": cfg["lookback_days"],
            "cluster": cluster,
        },
    }

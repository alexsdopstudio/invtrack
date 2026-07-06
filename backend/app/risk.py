"""Risk flags: red-flag conditions computed on read from already-ingested
data. A bullish score can coexist with real warning signs — these make them
impossible to miss. Severity: 'warning' (worth knowing) or 'serious' (should
change how much you trust the bullish case)."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import FactCongressTrade, FactInsiderTrade, FactFundamentals, FactPrice
from .screener import cash_runway_quarters

WINDOW_DAYS = 90


def _flag(flag_id: str, severity: str, label: str, detail: str) -> dict[str, str]:
    return {"id": flag_id, "severity": severity, "label": label, "detail": detail}


def risk_flags(db: Session, ticker: str, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    window_start = today - timedelta(days=WINDOW_DAYS)
    flags: list[dict[str, Any]] = []

    # Insider selling cluster: >=2 distinct insiders net selling in the window
    insider_trades = db.scalars(
        select(FactInsiderTrade).where(
            FactInsiderTrade.ticker == ticker,
            FactInsiderTrade.code.in_(["P", "S"]),
            FactInsiderTrade.transaction_date >= window_start,
        )
    ).all()
    sellers = {t.insider_name for t in insider_trades if t.code == "S" and t.insider_name}
    sell_dollars = sum(t.value or 0 for t in insider_trades if t.code == "S")
    buy_dollars = sum(t.value or 0 for t in insider_trades if t.code == "P")
    if len(sellers) >= 2 and sell_dollars > buy_dollars:
        flags.append(_flag(
            "insider_selling_cluster", "serious",
            "Insider selling cluster",
            f"{len(sellers)} insiders sold a net ${sell_dollars - buy_dollars:,.0f} "
            f"in the last {WINDOW_DAYS} days (Form 4).",
        ))

    # Congressional net selling in the window
    congress = db.scalars(
        select(FactCongressTrade).where(
            FactCongressTrade.ticker == ticker,
            FactCongressTrade.tx_type.in_(["buy", "sell"]),
        )
    ).all()
    net = 0.0
    for t in congress:
        signal_date = t.disclosure_date or t.transaction_date
        if signal_date < window_start or signal_date > today:
            continue
        mid = (t.amount_low or 0) + ((t.amount_high or t.amount_low or 0) - (t.amount_low or 0)) / 2
        net += mid if t.tx_type == "buy" else -mid
    if net < 0:
        flags.append(_flag(
            "congress_net_selling", "warning",
            "Congress net selling",
            f"Members of Congress disclosed roughly ${abs(net):,.0f} more sells than buys "
            f"in the last {WINDOW_DAYS} days (lagging data).",
        ))

    # Price trend: below 200-day MA / deep drawdown from 52-week high
    closes = [
        r.close
        for r in db.execute(
            select(FactPrice.date, FactPrice.close)
            .where(FactPrice.ticker == ticker, FactPrice.close.is_not(None))
            .order_by(FactPrice.date.desc())
            .limit(260)
        ).all()
    ]
    if len(closes) >= 200:
        ma200 = sum(closes[:200]) / 200
        if closes[0] < ma200:
            flags.append(_flag(
                "below_200dma", "warning",
                "Below 200-day average",
                f"Last close ${closes[0]:,.2f} is {(1 - closes[0] / ma200) * 100:.0f}% below "
                "the 200-day moving average — the long-term trend is down.",
            ))
    if closes:
        high = max(closes)
        drawdown = 1 - closes[0] / high
        if drawdown > 0.30:
            flags.append(_flag(
                "deep_drawdown", "serious",
                "Deep drawdown",
                f"Price is {drawdown * 100:.0f}% below its 52-week high of ${high:,.2f}.",
            ))

    # Cash burn: negative operating cash flow with short runway
    snapshot = db.scalar(
        select(FactFundamentals)
        .where(FactFundamentals.ticker == ticker)
        .order_by(FactFundamentals.as_of.desc())
        .limit(1)
    )
    # Earnings within two weeks: a scheduled binary event that can invalidate
    # any research done today.
    if (
        snapshot is not None
        and snapshot.next_earnings_date is not None
        and today <= snapshot.next_earnings_date <= today + timedelta(days=14)
    ):
        flags.append(_flag(
            "earnings_soon", "warning",
            "Earnings soon",
            f"Next earnings report is scheduled for {snapshot.next_earnings_date} — "
            "expect a sharp move either way; research done today may be stale next week.",
        ))

    if snapshot is not None:
        runway = cash_runway_quarters(
            float(snapshot.total_cash) if snapshot.total_cash is not None else None,
            float(snapshot.quarterly_operating_cashflow)
            if snapshot.quarterly_operating_cashflow is not None
            else None,
        )
        if runway is not None and runway != float("inf") and runway < 4:
            flags.append(_flag(
                "short_cash_runway", "serious",
                "Short cash runway",
                f"At the current burn rate the company has ~{runway:.1f} quarters of cash "
                "left — dilution or debt risk.",
            ))

    return flags

"""Track record: did the score (and the people we follow) actually work?

Joins stored historical scores and congressional buys with what prices did
afterwards, measured as excess return over the benchmark (scoring.yaml
``benchmark_ticker``). Everything here is descriptive of recorded history —
small samples, survivorship of whatever we happened to ingest — and the API
labels it that way. Never a forecast.
"""

import bisect
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_scoring_config
from .models import FactCongressTrade, FactPrice, Score

# A return is only measured when a close exists within this many days of the
# wanted date (weekends/holidays); otherwise the sample is skipped, not zeroed.
DATE_TOLERANCE_DAYS = 7

BANDS = (
    ("bearish", None, 40.0),
    ("neutral", 40.0, 60.0),
    ("bullish", 60.0, None),
)


class PriceBook:
    """Sorted closes per ticker with nearest-forward lookup."""

    def __init__(self, db: Session, tickers: set[str]):
        self._dates: dict[str, list[date]] = defaultdict(list)
        self._closes: dict[str, list[float]] = defaultdict(list)
        if not tickers:
            return
        rows = db.execute(
            select(FactPrice.ticker, FactPrice.date, FactPrice.close)
            .where(FactPrice.ticker.in_(tickers), FactPrice.close.is_not(None))
            .order_by(FactPrice.ticker, FactPrice.date)
        )
        for ticker, d, close in rows:
            self._dates[ticker].append(d)
            self._closes[ticker].append(close)

    def close_on_or_after(self, ticker: str, wanted: date) -> tuple[date, float] | None:
        dates = self._dates.get(ticker)
        if not dates:
            return None
        i = bisect.bisect_left(dates, wanted)
        if i >= len(dates):
            return None
        if (dates[i] - wanted).days > DATE_TOLERANCE_DAYS:
            return None
        return dates[i], self._closes[ticker][i]

    def forward_return(
        self, ticker: str, start: date, horizon_days: int, today: date
    ) -> float | None:
        """Return over [start, start+horizon], None when either end is
        unpriceable or the window hasn't finished yet."""
        end_wanted = start + timedelta(days=horizon_days)
        if end_wanted > today:
            return None
        entry = self.close_on_or_after(ticker, start)
        exit_ = self.close_on_or_after(ticker, end_wanted)
        if entry is None or exit_ is None or entry[1] <= 0:
            return None
        return exit_[1] / entry[1] - 1.0

    def has(self, ticker: str) -> bool:
        return bool(self._dates.get(ticker))


def _daily_scores(db: Session) -> dict[str, dict[date, Score]]:
    """Last stored score per ticker per day (ascending insert order wins)."""
    out: dict[str, dict[date, Score]] = defaultdict(dict)
    for s in db.scalars(select(Score).order_by(Score.computed_at.asc())):
        out[s.ticker][s.computed_at.date()] = s
    return out


def forward_returns(db: Session, today: date | None = None) -> list[dict[str, Any]]:
    """One row per (ticker, score day) with excess returns per horizon,
    for every horizon that has fully elapsed and is priceable."""
    config = get_scoring_config()
    today = today or date.today()
    benchmark = config["benchmark_ticker"]
    horizons = config["track_record"]["horizons_days"]

    scores = _daily_scores(db)
    scores.pop(benchmark, None)
    book = PriceBook(db, set(scores) | {benchmark})

    rows: list[dict[str, Any]] = []
    for ticker, by_day in scores.items():
        if not book.has(ticker):
            continue
        for day, s in sorted(by_day.items()):
            row: dict[str, Any] = {
                "ticker": ticker,
                "date": day,
                "total": s.total,
                "components": {
                    name: comp.get("score")
                    for name, comp in (s.components or {}).items()
                    if comp.get("status") == "ok"
                },
            }
            measured = False
            for h in horizons:
                r = book.forward_return(ticker, day, h, today)
                b = book.forward_return(benchmark, day, h, today)
                excess = r - b if r is not None and b is not None else None
                row[f"return_{h}d"] = r
                row[f"excess_{h}d"] = excess
                measured = measured or excess is not None
            if measured:
                rows.append(row)
    return rows


def _band_of(total: float) -> str:
    for name, lo, hi in BANDS:
        if (lo is None or total >= lo) and (hi is None or total < hi):
            return name
    return "neutral"


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def summary(db: Session, today: date | None = None) -> dict[str, Any]:
    config = get_scoring_config()
    today = today or date.today()
    cfg = config["track_record"]
    horizons = cfg["horizons_days"]
    rows = forward_returns(db, today)

    bands: list[dict[str, Any]] = []
    for name, _lo, _hi in BANDS:
        band_rows = [r for r in rows if _band_of(r["total"]) == name]
        entry: dict[str, Any] = {"band": name, "horizons": {}}
        for h in horizons:
            excesses = [r[f"excess_{h}d"] for r in band_rows if r[f"excess_{h}d"] is not None]
            entry["horizons"][str(h)] = {
                "n": len(excesses),
                "mean_excess": _mean(excesses),
                "hit_rate": round(sum(e > 0 for e in excesses) / len(excesses), 4)
                if excesses
                else None,
            }
        bands.append(entry)

    # Per-component read: within samples where the component scored, does a
    # high component score precede better excess returns than a low one?
    horizon = max(horizons)
    key = f"excess_{horizon}d"
    component_names = sorted({name for r in rows for name in r["components"]})
    components: list[dict[str, Any]] = []
    for name in component_names:
        samples = sorted(
            (
                (r["components"][name], r[key])
                for r in rows
                if name in r["components"] and r[key] is not None
            ),
            key=lambda pair: pair[0],
        )
        third = len(samples) // 3
        if third == 0:
            components.append(
                {"component": name, "n": len(samples), "horizon_days": horizon,
                 "bottom_mean_excess": None, "top_mean_excess": None, "spread": None}
            )
            continue
        bottom = _mean([e for _v, e in samples[:third]])
        top = _mean([e for _v, e in samples[-third:]])
        components.append(
            {
                "component": name,
                "n": len(samples),
                "horizon_days": horizon,
                "bottom_mean_excess": bottom,
                "top_mean_excess": top,
                "spread": round(top - bottom, 4) if top is not None and bottom is not None else None,
            }
        )

    n_samples = sum(1 for r in rows if any(r[f"excess_{h}d"] is not None for h in horizons))
    return {
        "benchmark": config["benchmark_ticker"],
        "as_of": today.isoformat(),
        "samples": n_samples,
        "insufficient_data": n_samples < cfg["min_samples"],
        "min_samples": cfg["min_samples"],
        "bands": bands,
        "components": components,
        "note": (
            "Excess return vs the benchmark after each stored score, over the "
            "tickers this instance happened to track. Small, unaudited sample — "
            "evidence for tuning the score, not a promise about the future."
        ),
    }


def politician_stats(db: Session, today: date | None = None) -> list[dict[str, Any]]:
    """Per-member record: what happened in the `horizon_days` after each of
    their disclosed buys, vs the benchmark. Only buys on tickers with ingested
    prices are measurable — coverage is reported, not hidden."""
    config = get_scoring_config()
    today = today or date.today()
    benchmark = config["benchmark_ticker"]
    horizon = config["congress"]["member_weighting"]["horizon_days"]

    trades = db.scalars(
        select(FactCongressTrade).where(FactCongressTrade.tx_type.in_(["buy", "sell"]))
    ).all()
    book = PriceBook(db, {t.ticker for t in trades} | {benchmark})

    by_member: dict[tuple[str, str], dict[str, Any]] = {}
    for t in trades:
        entry = by_member.setdefault(
            (t.chamber, t.member),
            {
                "chamber": t.chamber,
                "member": t.member,
                "trades": 0,
                "buys": 0,
                "sells": 0,
                "tickers": set(),
                "excesses": [],
                "last_activity": None,
            },
        )
        entry["trades"] += 1
        entry["buys"] += t.tx_type == "buy"
        entry["sells"] += t.tx_type == "sell"
        entry["tickers"].add(t.ticker)
        signal_date = t.disclosure_date or t.transaction_date
        if entry["last_activity"] is None or signal_date > entry["last_activity"]:
            entry["last_activity"] = signal_date
        if t.tx_type == "buy":
            r = book.forward_return(t.ticker, signal_date, horizon, today)
            b = book.forward_return(benchmark, signal_date, horizon, today)
            if r is not None and b is not None:
                entry["excesses"].append(r - b)

    weights = member_weights(db, config, today)
    out = []
    for entry in by_member.values():
        excesses = entry.pop("excesses")
        entry["tickers"] = len(entry["tickers"])
        entry["measured_buys"] = len(excesses)
        entry["horizon_days"] = horizon
        entry["mean_excess"] = _mean(excesses)
        entry["hit_rate"] = (
            round(sum(e > 0 for e in excesses) / len(excesses), 4) if excesses else None
        )
        entry["weight"] = weights.get(entry["member"], 1.0)
        out.append(entry)
    out.sort(key=lambda e: (e["mean_excess"] is None, -(e["mean_excess"] or 0.0)))
    return out


def member_weights(
    db: Session, config: dict[str, Any] | None = None, today: date | None = None
) -> dict[str, float]:
    """Skill weights for the congress score: members ranked by their own mean
    excess return after disclosed buys, mapped linearly onto
    [min_weight, max_weight] by rank. Members with fewer than ``min_trades``
    measurable buys get 1.0 — missing history is never a penalty."""
    config = config or get_scoring_config()
    cfg = config["congress"].get("member_weighting") or {}
    if not cfg.get("enabled"):
        return {}
    today = today or date.today()
    benchmark = config["benchmark_ticker"]
    horizon = cfg["horizon_days"]

    buys = db.scalars(
        select(FactCongressTrade).where(FactCongressTrade.tx_type == "buy")
    ).all()
    book = PriceBook(db, {t.ticker for t in buys} | {benchmark})

    excesses: dict[str, list[float]] = defaultdict(list)
    for t in buys:
        signal_date = t.disclosure_date or t.transaction_date
        r = book.forward_return(t.ticker, signal_date, horizon, today)
        b = book.forward_return(benchmark, signal_date, horizon, today)
        if r is not None and b is not None:
            excesses[t.member].append(r - b)

    qualified = {
        member: sum(vals) / len(vals)
        for member, vals in excesses.items()
        if len(vals) >= cfg["min_trades"]
    }
    if len(qualified) < 2:
        return {}  # can't rank one member against nothing

    lo, hi = cfg["min_weight"], cfg["max_weight"]
    ranked = sorted(qualified, key=qualified.get)
    step = (hi - lo) / (len(ranked) - 1)
    return {member: round(lo + i * step, 4) for i, member in enumerate(ranked)}

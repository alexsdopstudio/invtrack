"""Fundamentals sub-score (0-100).

Each available metric from the latest snapshot maps into a band score
(excellent=90, good=70, weak=40, below=20) using thresholds from scoring.yaml;
the sub-score is the average of available metrics. Missing metrics are
skipped, never counted as zero.

Trend adjustment: a company whose margin just inflected up is not the same as
one whose margin is collapsing, even at the same level — when an older
snapshot exists (config fundamentals.trend), improving/deteriorating metrics
get a band-score bonus/penalty, recorded per metric.
"""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FactFundamentals

BAND_SCORES = {"excellent": 90.0, "good": 70.0, "weak": 40.0, "poor": 20.0}

# metric -> (snapshot attribute, higher_is_better)
METRICS = {
    "revenue_growth_yoy": ("revenue_growth_yoy", True),
    "operating_margin": ("operating_margin", True),
    "debt_to_equity": ("debt_to_equity", False),
    "pe": ("pe", False),
}


def band_metric(value: float, thresholds: dict[str, float], higher_is_better: bool) -> str:
    if higher_is_better:
        if value >= thresholds["excellent"]:
            return "excellent"
        if value >= thresholds["good"]:
            return "good"
        if value >= thresholds["weak"]:
            return "weak"
        return "poor"
    if value <= thresholds["excellent"]:
        return "excellent"
    if value <= thresholds["good"]:
        return "good"
    if value <= thresholds["weak"]:
        return "weak"
    return "poor"


def compute(db: Session, ticker: str, config: dict[str, Any], today: date) -> dict[str, Any] | None:
    snapshot = db.scalar(
        select(FactFundamentals)
        .where(FactFundamentals.ticker == ticker)
        .order_by(FactFundamentals.as_of.desc())
        .limit(1)
    )
    if snapshot is None:
        return None

    cfg = config["fundamentals"]
    trend_cfg = cfg.get("trend") or {}
    previous = None
    if trend_cfg:
        previous = db.scalar(
            select(FactFundamentals)
            .where(
                FactFundamentals.ticker == ticker,
                FactFundamentals.as_of
                <= snapshot.as_of - timedelta(days=trend_cfg["min_days_apart"]),
            )
            .order_by(FactFundamentals.as_of.desc())
            .limit(1)
        )

    metric_results: dict[str, Any] = {}
    scores: list[float] = []
    for metric, (attr, higher_is_better) in METRICS.items():
        value = getattr(snapshot, attr)
        if value is None or metric not in cfg:
            metric_results[metric] = {"value": value, "band": None, "score": None}
            continue
        band = band_metric(float(value), cfg[metric], higher_is_better)
        score = BAND_SCORES[band]

        trend = None
        if previous is not None and metric in trend_cfg.get("metrics", []):
            old = getattr(previous, attr)
            if old is not None:
                delta = float(value) - float(old)
                adjustment = 0.0
                if abs(delta) >= trend_cfg["min_delta"]:
                    direction = 1.0 if delta > 0 else -1.0
                    if not higher_is_better:
                        direction = -direction
                    adjustment = direction * trend_cfg["bonus"]
                    score = max(0.0, min(100.0, score + adjustment))
                trend = {
                    "delta": round(delta, 4),
                    "vs_as_of": previous.as_of.isoformat(),
                    "adjustment": adjustment,
                }

        metric_results[metric] = {
            "value": round(float(value), 4),
            "band": band,
            "score": score,
            **({"trend": trend} if trend is not None else {}),
        }
        scores.append(score)

    if not scores:
        return None
    return {
        "score": sum(scores) / len(scores),
        "source": snapshot.source,
        "data_as_of": snapshot.as_of.isoformat(),
        "inputs": {"metrics": metric_results, "metrics_used": len(scores)},
    }

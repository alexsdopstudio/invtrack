"""Fundamentals sub-score (0-100).

Each available metric from the latest snapshot maps into a band score
(excellent=90, good=70, weak=40, below=20) using thresholds from scoring.yaml;
the sub-score is the average of available metrics. Missing metrics are
skipped, never counted as zero.
"""

from datetime import date
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
    metric_results: dict[str, Any] = {}
    scores: list[float] = []
    for metric, (attr, higher_is_better) in METRICS.items():
        value = getattr(snapshot, attr)
        if value is None or metric not in cfg:
            metric_results[metric] = {"value": value, "band": None, "score": None}
            continue
        band = band_metric(float(value), cfg[metric], higher_is_better)
        metric_results[metric] = {
            "value": round(float(value), 4),
            "band": band,
            "score": BAND_SCORES[band],
        }
        scores.append(BAND_SCORES[band])

    if not scores:
        return None
    return {
        "score": sum(scores) / len(scores),
        "source": snapshot.source,
        "data_as_of": snapshot.as_of.isoformat(),
        "inputs": {"metrics": metric_results, "metrics_used": len(scores)},
    }

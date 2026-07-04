import pytest

from app.ingestion.fundamentals import snapshot_from_info


def test_snapshot_from_info_scales_debt_to_equity():
    info = {
        "revenueGrowth": 0.15,
        "grossMargins": 0.69,
        "operatingMargins": 0.44,
        "debtToEquity": 35.2,  # yfinance reports a percentage
        "trailingPE": 34.0,
        "forwardPE": 30.0,
        "marketCap": 3_100_000_000_000,
        "sector": "Technology",
    }
    snap = snapshot_from_info(info)
    assert snap["debt_to_equity"] == pytest.approx(0.352)
    assert snap["revenue_growth_yoy"] == 0.15
    assert snap["pe"] == 34.0
    assert snap["raw"]["sector"] == "Technology"


def test_snapshot_handles_missing_fields():
    snap = snapshot_from_info({})
    assert snap["revenue_growth_yoy"] is None
    assert snap["debt_to_equity"] is None
    assert snap["market_cap"] is None

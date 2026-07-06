from datetime import date, datetime, time, timedelta, timezone

from app.config import get_scoring_config
from app.models import FactCongressTrade, FactPrice, Score
from app.trackrecord import forward_returns, member_weights, politician_stats, summary

TODAY = date.today()


def _seed_prices(db, ticker, daily_growth, days=300, start=100.0):
    """Weekday closes from `days` ago to yesterday, compounding daily_growth."""
    p = start
    for days_ago in range(days, 0, -1):
        d = TODAY - timedelta(days=days_ago)
        if d.weekday() >= 5:
            continue
        p *= 1 + daily_growth
        db.add(FactPrice(ticker=ticker, date=d, close=round(p, 4)))
    db.commit()


def _seed_score(db, ticker, total, days_ago, components=None):
    db.add(
        Score(
            ticker=ticker,
            total=total,
            components=components
            or {"momentum": {"status": "ok", "score": total, "contribution": total}},
            computed_at=datetime.combine(
                TODAY - timedelta(days=days_ago), time(hour=8), tzinfo=timezone.utc
            ),
        )
    )
    db.commit()


def _seed_buy(db, member, ticker, disclosed_days_ago, amount=50000.0):
    db.add(
        FactCongressTrade(
            chamber="senate", member=member, ticker=ticker,
            transaction_date=TODAY - timedelta(days=disclosed_days_ago + 20),
            disclosure_date=TODAY - timedelta(days=disclosed_days_ago),
            tx_type="buy", amount_low=amount, amount_high=amount,
        )
    )
    db.commit()


def test_forward_returns_measure_excess_vs_benchmark(db):
    _seed_prices(db, "SPY", 0.0)          # flat benchmark
    _seed_prices(db, "UP", 0.002)         # riser
    _seed_score(db, "UP", 75.0, days_ago=120)
    rows = forward_returns(db, TODAY)
    assert len(rows) == 1
    row = rows[0]
    assert row["excess_30d"] > 0
    assert row["excess_90d"] > row["excess_30d"]  # keeps compounding


def test_unelapsed_horizon_and_missing_prices_are_skipped_not_zeroed(db):
    _seed_prices(db, "SPY", 0.0)
    _seed_prices(db, "UP", 0.002)
    _seed_score(db, "UP", 75.0, days_ago=40)      # 30d elapsed, 90d not
    _seed_score(db, "NOPRICES", 80.0, days_ago=120)
    rows = forward_returns(db, TODAY)
    assert [r["ticker"] for r in rows] == ["UP"]
    assert rows[0]["excess_30d"] is not None
    assert rows[0]["excess_90d"] is None


def test_summary_bands_and_insufficient_data(db):
    _seed_prices(db, "SPY", 0.0)
    _seed_prices(db, "UP", 0.002)
    _seed_prices(db, "DOWN", -0.002)
    for i in range(5):
        _seed_score(db, "UP", 80.0, days_ago=120 + i * 5)    # bullish, outperforms
        _seed_score(db, "DOWN", 20.0, days_ago=120 + i * 5)  # bearish, underperforms
    s = summary(db, TODAY)
    assert s["benchmark"] == "SPY"
    bands = {b["band"]: b for b in s["bands"]}
    assert bands["bullish"]["horizons"]["90"]["mean_excess"] > 0
    assert bands["bullish"]["horizons"]["90"]["hit_rate"] == 1.0
    assert bands["bearish"]["horizons"]["90"]["mean_excess"] < 0
    assert s["samples"] == 10
    assert s["insufficient_data"] is (s["samples"] < s["min_samples"])
    # per-component: momentum top third should beat bottom third
    comp = {c["component"]: c for c in s["components"]}
    assert comp["momentum"]["spread"] > 0


def test_summary_reports_insufficient_when_empty(db):
    s = summary(db, TODAY)
    assert s["insufficient_data"] is True
    assert s["samples"] == 0
    assert all(
        h["mean_excess"] is None for b in s["bands"] for h in b["horizons"].values()
    )


def test_politician_stats_ranks_by_track_record(db):
    _seed_prices(db, "SPY", 0.0005)
    _seed_prices(db, "WIN", 0.003)
    _seed_prices(db, "LOSE", -0.003)
    for days_ago in (200, 150):
        _seed_buy(db, "Sen. Sharp", "WIN", days_ago)
        _seed_buy(db, "Sen. Blunt", "LOSE", days_ago)
    _seed_buy(db, "Sen. Fresh", "WIN", 10)  # too recent to measure

    stats = {s["member"]: s for s in politician_stats(db, TODAY)}
    assert stats["Sen. Sharp"]["mean_excess"] > 0
    assert stats["Sen. Sharp"]["hit_rate"] == 1.0
    assert stats["Sen. Blunt"]["mean_excess"] < 0
    assert stats["Sen. Fresh"]["measured_buys"] == 0
    assert stats["Sen. Fresh"]["mean_excess"] is None
    # ranked best first, unmeasurable last
    ordered = [s["member"] for s in politician_stats(db, TODAY)]
    assert ordered.index("Sen. Sharp") < ordered.index("Sen. Blunt")
    assert ordered[-1] == "Sen. Fresh"


def test_member_weights_spread_and_defaults(db):
    _seed_prices(db, "SPY", 0.0005)
    _seed_prices(db, "WIN", 0.003)
    _seed_prices(db, "LOSE", -0.003)
    for days_ago in (200, 150):
        _seed_buy(db, "Sen. Sharp", "WIN", days_ago)
        _seed_buy(db, "Sen. Blunt", "LOSE", days_ago)
    _seed_buy(db, "Sen. Fresh", "WIN", 10)

    config = get_scoring_config()
    weights = member_weights(db, config, TODAY)
    wcfg = config["congress"]["member_weighting"]
    assert weights["Sen. Sharp"] == wcfg["max_weight"]
    assert weights["Sen. Blunt"] == wcfg["min_weight"]
    assert "Sen. Fresh" not in weights  # not enough history -> defaults to 1.0 downstream


def test_congress_score_uses_skill_weights(db):
    import copy

    from app.scoring import congress

    _seed_prices(db, "SPY", 0.0005)
    _seed_prices(db, "WIN", 0.003)
    _seed_prices(db, "LOSE", -0.003)
    for days_ago in (200, 150):
        _seed_buy(db, "Sen. Sharp", "WIN", days_ago)
        _seed_buy(db, "Sen. Blunt", "LOSE", days_ago)
    # current-window trade by the proven member on a fresh ticker
    _seed_buy(db, "Sen. Sharp", "TGT", 5, amount=100000.0)

    config = copy.deepcopy(get_scoring_config())
    weighted = congress.compute(db, "TGT", config, TODAY)
    config["congress"]["member_weighting"]["enabled"] = False
    unweighted = congress.compute(db, "TGT", config, TODAY)

    assert weighted["inputs"]["member_weights"]["Sen. Sharp"] == 1.5
    assert unweighted["inputs"]["member_weights"]["Sen. Sharp"] == 1.0
    assert weighted["score"] > unweighted["score"]


def test_member_weights_need_two_qualified_members(db):
    _seed_prices(db, "SPY", 0.0005)
    _seed_prices(db, "WIN", 0.003)
    for days_ago in (200, 150):
        _seed_buy(db, "Sen. Solo", "WIN", days_ago)
    assert member_weights(db, get_scoring_config(), TODAY) == {}

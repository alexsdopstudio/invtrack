"""Batch: signal-quality upgrades — 10b5-1 exclusion, officer weighting,
relative-strength momentum, fundamentals trend, earnings-soon flag, risk
alerts."""

import copy
from datetime import date, timedelta

from app.alerts import detect_alerts
from app.config import get_scoring_config
from app.ingestion.insider import parse_form4_xml
from app.models import FactFundamentals, FactInsiderTrade, FactPrice, WatchlistItem
from app.risk import risk_flags
from app.scoring import fundamentals as f_scoring
from app.scoring import insider as i_scoring
from app.scoring import momentum as m_scoring

TODAY = date.today()


def _insider_trade(db, acc, code, value, *, officer=False, director=False, plan=None, ticker="TGT"):
    db.add(
        FactInsiderTrade(
            accession_no=acc, row_index=0, ticker=ticker, insider_name=acc,
            is_officer=officer, is_director=director, is_10b5_1=plan,
            transaction_date=TODAY - timedelta(days=10),
            code=code, shares=1.0, price=value, value=value,
        )
    )
    db.commit()


def _prices(db, ticker, daily_growth, days=300, start=100.0):
    p = start
    for days_ago in range(days, 0, -1):
        d = TODAY - timedelta(days=days_ago)
        if d.weekday() >= 5:
            continue
        p *= 1 + daily_growth
        db.add(FactPrice(ticker=ticker, date=d, close=round(p, 4)))
    db.commit()


def test_plan_sales_are_excluded_from_insider_score(db):
    config = get_scoring_config()
    _insider_trade(db, "plan-sale", "S", 500000.0, plan=True)
    with_plan = i_scoring.compute(db, "TGT", config, TODAY)
    assert with_plan["score"] == 50.0  # fully muted -> neutral
    assert with_plan["inputs"]["plan_sales_muted"] == 1

    _insider_trade(db, "open-sale", "S", 500000.0, plan=False, ticker="TGT2")
    open_sale = i_scoring.compute(db, "TGT2", config, TODAY)
    assert open_sale["score"] < 50.0  # unflagged sale still counts


def test_officer_buys_outweigh_unaffiliated_buys(db):
    config = get_scoring_config()
    _insider_trade(db, "cfo-buy", "P", 300000.0, officer=True, ticker="OFF")
    _insider_trade(db, "anon-buy", "P", 300000.0, ticker="ANON")
    officer = i_scoring.compute(db, "OFF", config, TODAY)
    anon = i_scoring.compute(db, "ANON", config, TODAY)
    assert officer["score"] > anon["score"]
    assert officer["inputs"]["officer_weight"] == config["insider"]["officer_weight"]


def test_momentum_relative_strength_separates_leaders_from_laggards(db):
    config = get_scoring_config()
    _prices(db, "SPY", 0.0015)
    _prices(db, "LEAD", 0.003)   # beats the market
    _prices(db, "LAG", 0.0005)   # rises, but lags it
    lead = m_scoring.compute(db, "LEAD", config, TODAY)
    lag = m_scoring.compute(db, "LAG", config, TODAY)
    assert lead["inputs"]["excess_vs_benchmark_pct"] > 0
    assert lag["inputs"]["excess_vs_benchmark_pct"] < 0
    assert lead["score"] > lag["score"]


def test_momentum_falls_back_to_ma_only_without_benchmark(db):
    config = get_scoring_config()
    _prices(db, "SOLO", 0.002)  # no SPY prices at all
    result = m_scoring.compute(db, "SOLO", config, TODAY)
    assert result is not None
    assert result["inputs"]["excess_vs_benchmark_pct"] is None
    no_rs = copy.deepcopy(config)
    no_rs["momentum"]["rs_weight"] = 0.0
    assert result["score"] == m_scoring.compute(db, "SOLO", no_rs, TODAY)["score"]


def _snapshot(db, ticker, as_of, **metrics):
    db.add(FactFundamentals(ticker=ticker, as_of=as_of, **metrics))
    db.commit()


def test_fundamentals_trend_rewards_improvement_and_punishes_decay(db):
    config = get_scoring_config()
    _snapshot(db, "IMPR", TODAY - timedelta(days=90), operating_margin=0.16)
    _snapshot(db, "IMPR", TODAY, operating_margin=0.20)
    _snapshot(db, "DECAY", TODAY - timedelta(days=90), operating_margin=0.24)
    _snapshot(db, "DECAY", TODAY, operating_margin=0.20)
    _snapshot(db, "FLAT", TODAY, operating_margin=0.20)  # no history: no adjustment

    impr = f_scoring.compute(db, "IMPR", config, TODAY)["score"]
    decay = f_scoring.compute(db, "DECAY", config, TODAY)["score"]
    flat = f_scoring.compute(db, "FLAT", config, TODAY)["score"]
    assert impr > flat > decay
    trend = f_scoring.compute(db, "IMPR", config, TODAY)["inputs"]["metrics"][
        "operating_margin"
    ]["trend"]
    assert trend["adjustment"] == config["fundamentals"]["trend"]["bonus"]


def test_earnings_soon_flag_only_inside_window(db):
    _snapshot(db, "SOON", TODAY, next_earnings_date=TODAY + timedelta(days=7))
    _snapshot(db, "LATER", TODAY, next_earnings_date=TODAY + timedelta(days=40))
    assert any(f["id"] == "earnings_soon" for f in risk_flags(db, "SOON", TODAY))
    assert not any(f["id"] == "earnings_soon" for f in risk_flags(db, "LATER", TODAY))


def test_serious_risk_flags_create_deduped_alerts(db):
    db.add(WatchlistItem(ticker="BURN"))
    db.commit()
    _snapshot(db, "BURN", TODAY, total_cash=1.0e8, quarterly_operating_cashflow=-5.0e7)
    first = detect_alerts(db, TODAY)
    assert any(a.kind == "risk_flag" and a.ticker == "BURN" for a in first)
    assert detect_alerts(db, TODAY) == []  # idempotent


def test_parse_form4_reads_10b5_1_checkbox():
    xml = """<ownershipDocument>
      <aff10b5One>1</aff10b5One>
      <issuer><issuerCik>123</issuerCik><issuerTradingSymbol>tgt</issuerTradingSymbol></issuer>
      <reportingOwner>
        <reportingOwnerId><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
        <reportingOwnerRelationship><isOfficer>1</isOfficer></reportingOwnerRelationship>
      </reportingOwner>
      <nonDerivativeTable><nonDerivativeTransaction>
        <transactionDate><value>2026-06-30</value></transactionDate>
        <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
        <transactionAmounts>
          <transactionShares><value>100</value></transactionShares>
          <transactionPricePerShare><value>50</value></transactionPricePerShare>
        </transactionAmounts>
      </nonDerivativeTransaction></nonDerivativeTable>
    </ownershipDocument>"""
    rows = parse_form4_xml(xml, "acc-1")
    assert rows[0]["is_10b5_1"] is True
    # older form without the checkbox -> unknown (None), never assumed False
    from pathlib import Path

    fixture = (Path(__file__).parent / "fixtures" / "form4_sample.xml").read_text()
    assert all(r["is_10b5_1"] is None for r in parse_form4_xml(fixture, "acc-2"))

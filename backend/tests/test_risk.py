from datetime import date, timedelta

from app.models import FactFundamentals, FactInsiderTrade, FactPrice
from app.risk import risk_flags

TODAY = date.today()


def _flag_ids(flags):
    return {f["id"] for f in flags}


def test_clean_ticker_has_no_flags(db):
    assert risk_flags(db, "NVDA", TODAY) == []


def test_insider_selling_cluster(db):
    for i, name in enumerate(["Alice", "Bob"]):
        db.add(
            FactInsiderTrade(
                accession_no=f"a-{i}", row_index=0, ticker="NVDA",
                insider_name=name,
                transaction_date=TODAY - timedelta(days=5 + i),
                code="S", shares=1000, price=100.0, value=100000.0,
            )
        )
    db.commit()
    flags = risk_flags(db, "NVDA", TODAY)
    assert "insider_selling_cluster" in _flag_ids(flags)
    assert all(f["severity"] in ("warning", "serious") for f in flags)


def test_downtrend_and_drawdown_flags(db):
    closes = [200 - i * 0.5 for i in range(260)]  # long steady decline, ~65% drawdown
    for i, close in enumerate(closes):
        db.add(
            FactPrice(
                ticker="NVDA",
                date=TODAY - timedelta(days=len(closes) - i),
                open=close, high=close, low=close, close=close, volume=1e6,
            )
        )
    db.commit()
    ids = _flag_ids(risk_flags(db, "NVDA", TODAY))
    assert "below_200dma" in ids
    assert "deep_drawdown" in ids


def test_short_cash_runway_flag(db):
    db.add(
        FactFundamentals(
            ticker="NVDA", as_of=TODAY,
            total_cash=1.0e8, quarterly_operating_cashflow=-5.0e7,  # 2 quarters
        )
    )
    db.commit()
    ids = _flag_ids(risk_flags(db, "NVDA", TODAY))
    assert "short_cash_runway" in ids


def test_cash_generative_company_not_flagged(db):
    db.add(
        FactFundamentals(
            ticker="NVDA", as_of=TODAY,
            total_cash=1.0e8, quarterly_operating_cashflow=5.0e7,
        )
    )
    db.commit()
    assert "short_cash_runway" not in _flag_ids(risk_flags(db, "NVDA", TODAY))

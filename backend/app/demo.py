"""Demo seed: populates the database with realistic sample data (routed
through the real parsers/upserts where possible) so the app can be exercised
end-to-end without network access. Dates are generated relative to today so
scoring windows always have data. Clearly synthetic — for demo/dev only."""

import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from .ingestion.congress import parse_stock_watcher_rows, upsert_trades
from .ingestion.fundamentals import upsert_snapshot
from .ingestion.insider import upsert_insider_trades
from .ingestion.prices import upsert_prices
from .ingestion.tickers import upsert_tickers
from .models import WatchlistItem
from .scoring import engine

DEMO_TICKERS = {
    "AAPL": ("Apple Inc.", "0000320193", "Technology"),
    "MSFT": ("Microsoft Corporation", "0000789019", "Technology"),
    "NVDA": ("NVIDIA Corporation", "0001045810", "Technology"),
    "UNH": ("UnitedHealth Group Incorporated", "0000731766", "Healthcare"),
}

# Not on the watchlist: they surface in the Radar (discovery) section.
DISCOVERY_TICKERS = {
    "PLTR": ("Palantir Technologies Inc.", "0001321655", "Technology"),
    "AVGO": ("Broadcom Inc.", "0001730168", "Technology"),
}


def _d(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).strftime("%m/%d/%Y")


def _senate_row(senator, ticker, tx_type, amount, tx_days_ago, disclosure_days_ago):
    return {
        "senator": senator,
        "ticker": ticker,
        "type": tx_type,
        "amount": amount,
        "transaction_date": _d(tx_days_ago),
        "disclosure_date": _d(disclosure_days_ago),
        "asset_description": f"{ticker} common stock",
        "demo": True,
    }


def _house_row(rep, ticker, tx_type, amount, tx_days_ago, disclosure_days_ago):
    return {
        "representative": rep,
        "ticker": ticker,
        "type": tx_type,
        "amount": amount,
        "transaction_date": (date.today() - timedelta(days=tx_days_ago)).strftime("%Y-%m-%d"),
        "disclosure_date": _d(disclosure_days_ago),
        "asset_description": f"{ticker} common stock",
        "demo": True,
    }


def seed_demo(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}

    all_dims = {**DEMO_TICKERS, **DISCOVERY_TICKERS}
    counts["tickers"] = upsert_tickers(
        db,
        [
            {"ticker": t, "name": name, "cik": cik}
            for t, (name, cik, _sector) in all_dims.items()
        ],
    )
    for ticker, (_name, _cik, sector) in all_dims.items():
        from .models import DimTicker

        dim = db.get(DimTicker, ticker)
        if dim is not None:
            dim.sector = sector
    for ticker in DEMO_TICKERS:
        if not db.query(WatchlistItem).filter_by(ticker=ticker).first():
            db.add(WatchlistItem(ticker=ticker, notes="demo seed"))
    db.commit()
    counts["watchlist"] = len(DEMO_TICKERS)

    senate = [
        _senate_row("Sen. Alpha Example", "NVDA", "Purchase", "$50,001 - $100,000", 40, 12),
        _senate_row("Sen. Beta Example", "NVDA", "Purchase", "$15,001 - $50,000", 35, 9),
        _senate_row("Sen. Gamma Example", "NVDA", "Purchase", "$100,001 - $250,000", 30, 6),
        _senate_row("Sen. Alpha Example", "AAPL", "Purchase", "$15,001 - $50,000", 55, 20),
        _senate_row("Sen. Delta Example", "UNH", "Sale (Full)", "$250,001 - $500,000", 45, 14),
        # Radar (discovery) material: not on the demo watchlist
        _senate_row("Sen. Alpha Example", "PLTR", "Purchase", "$100,001 - $250,000", 22, 8),
        _senate_row("Sen. Beta Example", "PLTR", "Purchase", "$50,001 - $100,000", 18, 6),
        _senate_row("Sen. Gamma Example", "PLTR", "Purchase", "$15,001 - $50,000", 14, 3),
        _senate_row("Sen. Delta Example", "AVGO", "Purchase", "$50,001 - $100,000", 26, 11),
    ]
    house = [
        _house_row("Rep. Epsilon Example", "NVDA", "purchase", "$1,001 - $15,000", 25, 5),
        _house_row("Rep. Zeta Example", "MSFT", "purchase", "$15,001 - $50,000", 50, 18),
        _house_row("Rep. Eta Example", "UNH", "sale_partial", "$50,001 - $100,000", 38, 10),
        _house_row("Rep. Theta Example", "UNH", "sale_full", "$15,001 - $50,000", 28, 7),
        _house_row("Rep. Iota Example", "UNH", "sale_partial", "$100,001 - $250,000", 20, 4),
    ]
    counts["congress"] = upsert_trades(
        db,
        parse_stock_watcher_rows(senate, "senate") + parse_stock_watcher_rows(house, "house"),
    )

    def insider(acc, ticker, cik, name, title, officer, days_ago, code, shares, price):
        return {
            "accession_no": acc,
            "row_index": 0,
            "cik": cik,
            "ticker": ticker,
            "insider_name": name,
            "insider_title": title,
            "is_officer": officer,
            "is_director": not officer,
            "transaction_date": date.today() - timedelta(days=days_ago),
            "code": code,
            "shares": shares,
            "price": price,
            "value": shares * price,
            "raw": {"demo": True},
        }

    counts["insider"] = upsert_insider_trades(
        db,
        [
            insider("0000000000-25-000001", "NVDA", "0001045810", "Chen Example", "EVP", True, 15, "P", 5000, 130.0),
            insider("0000000000-25-000002", "NVDA", "0001045810", "Rivera Example", None, False, 12, "P", 2000, 132.5),
            insider("0000000000-25-000003", "AAPL", "0000320193", "Kim Example", "CFO", True, 30, "S", 10000, 210.0),
            insider("0000000000-25-000004", "MSFT", "0000789019", "Osei Example", "VP Eng", True, 22, "P", 1500, 420.0),
            insider("0000000000-25-000005", "UNH", "0000731766", "Novak Example", "CEO", True, 18, "S", 8000, 480.0),
            insider("0000000000-25-000006", "UNH", "0000731766", "Patel Example", None, False, 10, "S", 3000, 465.0),
        ],
    )

    fundamentals = {
        "AAPL": {"revenue_growth_yoy": 0.06, "gross_margin": 0.46, "operating_margin": 0.31,
                 "debt_to_equity": 1.45, "pe": 32.0, "forward_pe": 28.0, "market_cap": 3.2e12,
                 "current_ratio": 0.95, "total_cash": 6.5e10,
                 "quarterly_operating_cashflow": 2.9e10, "insider_ownership_pct": 0.001},
        "MSFT": {"revenue_growth_yoy": 0.15, "gross_margin": 0.69, "operating_margin": 0.44,
                 "debt_to_equity": 0.35, "pe": 34.0, "forward_pe": 30.0, "market_cap": 3.1e12,
                 "current_ratio": 1.3, "total_cash": 8.0e10,
                 "quarterly_operating_cashflow": 3.4e10, "insider_ownership_pct": 0.0005},
        "NVDA": {"revenue_growth_yoy": 0.62, "gross_margin": 0.75, "operating_margin": 0.58,
                 "debt_to_equity": 0.22, "pe": 45.0, "forward_pe": 33.0, "market_cap": 3.0e12,
                 "current_ratio": 4.1, "total_cash": 3.8e10,
                 "quarterly_operating_cashflow": 1.5e10, "insider_ownership_pct": 0.04},
        "UNH": {"revenue_growth_yoy": 0.07, "gross_margin": 0.24, "operating_margin": 0.08,
                 "debt_to_equity": 0.85, "pe": 12.0, "forward_pe": 11.0, "market_cap": 4.5e11,
                 "current_ratio": 0.9, "total_cash": 2.5e10,
                 "quarterly_operating_cashflow": 8.0e9},  # insider ownership: unknown
        # discovery ticker sized to pass most screener criteria (demo of the
        # aggressive-growth profile: small, fast-growing, high-margin, solvent)
        "PLTR": {"revenue_growth_yoy": 0.30, "gross_margin": 0.80, "operating_margin": 0.16,
                 "debt_to_equity": 0.10, "pe": 60.0, "forward_pe": 48.0, "market_cap": 1.5e9,
                 "current_ratio": 5.9, "total_cash": 3.0e9,
                 "quarterly_operating_cashflow": -5.0e7, "insider_ownership_pct": 0.13},
        # AVGO stays congress-only on purpose (missing-data paths in Radar + screener)
    }
    counts["fundamentals"] = sum(
        upsert_snapshot(db, t, {**snap, "raw": {"demo": True}}, date.today())
        for t, snap in fundamentals.items()
    )

    rng = random.Random(42)
    start_prices = {"AAPL": 195.0, "MSFT": 410.0, "NVDA": 105.0, "UNH": 520.0, "PLTR": 24.0}
    drift = {"AAPL": 0.0004, "MSFT": 0.0006, "NVDA": 0.0018, "UNH": -0.0012, "PLTR": 0.0022}
    counts["prices"] = 0
    for ticker, price in start_prices.items():
        rows = []
        p = price
        for days_ago in range(365, 0, -1):
            d = date.today() - timedelta(days=days_ago)
            if d.weekday() >= 5:
                continue
            p *= 1 + drift[ticker] + rng.gauss(0, 0.015)
            rows.append(
                {
                    "date": d,
                    "open": round(p * (1 + rng.gauss(0, 0.003)), 2),
                    "high": round(p * 1.01, 2),
                    "low": round(p * 0.99, 2),
                    "close": round(p, 2),
                    "volume": float(rng.randint(20_000_000, 90_000_000)),
                }
            )
        counts["prices"] += upsert_prices(db, ticker, rows)

    counts["scores"] = len(engine.compute_and_store(db))
    return counts

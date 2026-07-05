from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# JSONB on Postgres/Supabase, plain JSON elsewhere (SQLite dev/tests).
JsonCol = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DimTicker(Base):
    __tablename__ = "dim_ticker"

    ticker: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    cik: Mapped[str | None] = mapped_column(String(10), index=True)
    exchange: Mapped[str | None] = mapped_column(String(32))
    sector: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    watchlist_item: Mapped["WatchlistItem | None"] = relationship(back_populates="ticker_ref")


class WatchlistItem(Base):
    __tablename__ = "watchlist_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(ForeignKey("dim_ticker.ticker"), unique=True)
    notes: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticker_ref: Mapped[DimTicker] = relationship(back_populates="watchlist_item")


class FactCongressTrade(Base):
    __tablename__ = "fact_congress_trade"
    __table_args__ = (
        UniqueConstraint(
            "chamber", "member", "ticker", "transaction_date", "tx_type", "amount_low",
            name="uq_congress_trade_natural",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chamber: Mapped[str] = mapped_column(String(8))  # senate | house
    member: Mapped[str] = mapped_column(String(128))
    ticker: Mapped[str] = mapped_column(String(12), index=True)
    transaction_date: Mapped[date] = mapped_column(Date)
    disclosure_date: Mapped[date | None] = mapped_column(Date)
    tx_type: Mapped[str] = mapped_column(String(16))  # buy | sell | exchange
    amount_low: Mapped[float | None] = mapped_column(Float)
    amount_high: Mapped[float | None] = mapped_column(Float)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JsonCol)
    source: Mapped[str] = mapped_column(String(32), default="stock_watcher")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FactInsiderTrade(Base):
    __tablename__ = "fact_insider_trade"
    __table_args__ = (
        UniqueConstraint("accession_no", "row_index", name="uq_insider_trade_accession_row"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    accession_no: Mapped[str] = mapped_column(String(32))
    row_index: Mapped[int] = mapped_column(Integer, default=0)
    cik: Mapped[str | None] = mapped_column(String(10), index=True)
    ticker: Mapped[str] = mapped_column(String(12), index=True)
    insider_name: Mapped[str | None] = mapped_column(String(128))
    insider_title: Mapped[str | None] = mapped_column(String(128))
    is_officer: Mapped[bool | None] = mapped_column(default=None)
    is_director: Mapped[bool | None] = mapped_column(default=None)
    transaction_date: Mapped[date] = mapped_column(Date)
    code: Mapped[str] = mapped_column(String(4))  # Form 4 transaction code: P, S, A, ...
    shares: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)
    value: Mapped[float | None] = mapped_column(Float)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JsonCol)
    source: Mapped[str] = mapped_column(String(32), default="sec_edgar")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FactPrice(Base):
    __tablename__ = "fact_price"

    ticker: Mapped[str] = mapped_column(String(12), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="yfinance")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FactFundamentals(Base):
    __tablename__ = "fact_fundamentals"
    __table_args__ = (UniqueConstraint("ticker", "as_of", name="uq_fundamentals_ticker_asof"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(12), index=True)
    as_of: Mapped[date] = mapped_column(Date)
    revenue_growth_yoy: Mapped[float | None] = mapped_column(Float)
    gross_margin: Mapped[float | None] = mapped_column(Float)
    operating_margin: Mapped[float | None] = mapped_column(Float)
    debt_to_equity: Mapped[float | None] = mapped_column(Float)
    pe: Mapped[float | None] = mapped_column(Float)
    forward_pe: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    # Screener inputs
    current_ratio: Mapped[float | None] = mapped_column(Float)
    total_cash: Mapped[float | None] = mapped_column(Float)
    quarterly_operating_cashflow: Mapped[float | None] = mapped_column(Float)
    insider_ownership_pct: Mapped[float | None] = mapped_column(Float)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JsonCol)
    source: Mapped[str] = mapped_column(String(32), default="yfinance")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiReport(Base):
    __tablename__ = "ai_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(12), index=True)
    accession_no: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    report_md: Mapped[str] = mapped_column(Text)
    # provenance: which 10-K sections were analyzed and how much of each
    sections_meta: Mapped[dict[str, Any] | None] = mapped_column(JsonCol)


class Score(Base):
    __tablename__ = "score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(12), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    total: Mapped[float] = mapped_column(Float)
    # Per-component breakdown: value, weight, contribution, inputs, source,
    # data timestamps — the "why this score" provenance record.
    components: Mapped[dict[str, Any]] = mapped_column(JsonCol)


class IngestionRun(Base):
    __tablename__ = "ingestion_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | ok | error
    rows_upserted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

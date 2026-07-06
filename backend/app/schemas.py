from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TickerSearchResult(BaseModel):
    ticker: str
    name: str | None
    cik: str | None
    on_watchlist: bool = False


class WatchlistCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    notes: str | None = None


class WatchlistUpdate(BaseModel):
    notes: str | None = None


class WatchlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    notes: str | None
    added_at: datetime


class CongressTradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chamber: str
    member: str
    ticker: str
    transaction_date: date
    disclosure_date: date | None
    tx_type: str
    amount_low: float | None
    amount_high: float | None
    source: str
    ingested_at: datetime


class InsiderTradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    accession_no: str
    ticker: str
    insider_name: str | None
    insider_title: str | None
    is_officer: bool | None
    is_director: bool | None
    transaction_date: date
    code: str
    shares: float | None
    price: float | None
    value: float | None
    source: str
    ingested_at: datetime


class PricePoint(BaseModel):
    date: date
    close: float | None


class FundamentalsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    as_of: date
    revenue_growth_yoy: float | None
    gross_margin: float | None
    operating_margin: float | None
    debt_to_equity: float | None
    pe: float | None
    forward_pe: float | None
    market_cap: float | None
    source: str
    ingested_at: datetime


class ScoreOut(BaseModel):
    ticker: str
    total: float | None
    computed_at: datetime | None
    components: dict[str, Any] | None


class DashboardRow(BaseModel):
    ticker: str
    name: str | None
    sector: str | None
    notes: str | None
    score: float | None
    score_computed_at: datetime | None
    components: dict[str, Any] | None
    last_close: float | None
    last_congress_activity: date | None
    last_insider_activity: date | None
    sparkline: list[float]
    risk_count: int = 0


class TickerDetail(BaseModel):
    ticker: str
    name: str | None
    sector: str | None
    cik: str | None
    on_watchlist: bool
    notes: str | None
    fundamentals: FundamentalsOut | None
    score: ScoreOut | None


class IdeaRow(BaseModel):
    ticker: str
    name: str | None
    sector: str | None
    score: float | None
    components: dict[str, Any] | None
    buys: int
    sells: int
    buyers: int
    last_activity: date | None
    net_dollars: float
    last_close: float | None
    sparkline: list[float]


class PriceStats(BaseModel):
    ticker: str
    cagr_1y: float
    annual_vol: float
    max_drawdown: float
    atr_14: float | None
    last_close: float
    data_points: int
    first_date: date
    last_date: date


class ScreenerCriterion(BaseModel):
    value: float | None
    threshold: dict[str, float]
    status: str  # pass | fail | unknown


class ScreenerRow(BaseModel):
    ticker: str
    name: str | None
    sector: str | None
    criteria: dict[str, ScreenerCriterion]
    passed: int
    failed: int
    unknown: int
    data_as_of: date | None


class AiReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    ticker: str
    accession_no: str
    model: str
    created_at: datetime
    report_md: str
    sections_meta: dict[str, Any] | None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    ticker: str
    kind: str
    title: str
    body: str
    seen: bool


class RiskFlag(BaseModel):
    id: str
    severity: str  # warning | serious
    label: str
    detail: str


class ScoreHistoryEntry(BaseModel):
    date: date
    total: float
    contributions: dict[str, float]
    deltas: dict[str, float] | None
    total_delta: float | None


class IngestionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    rows_upserted: int
    error: str | None


class IngestRequest(BaseModel):
    sources: list[str] | None = None

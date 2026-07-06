export interface DashboardRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  notes: string | null;
  score: number | null;
  score_computed_at: string | null;
  components: Record<string, ScoreComponent> | null;
  last_close: number | null;
  last_congress_activity: string | null;
  last_insider_activity: string | null;
  sparkline: number[];
  risk_count: number;
}

export interface ScoreComponent {
  status: "ok" | "missing";
  score?: number;
  weight: number;
  normalized_weight: number;
  contribution: number;
  source?: string;
  data_as_of?: string;
  inputs?: Record<string, unknown>;
}

export interface ScoreOut {
  ticker: string;
  total: number | null;
  computed_at: string | null;
  components: Record<string, ScoreComponent> | null;
}

export interface TickerSearchResult {
  ticker: string;
  name: string | null;
  cik: string | null;
  on_watchlist: boolean;
}

export interface Fundamentals {
  ticker: string;
  as_of: string;
  revenue_growth_yoy: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  debt_to_equity: number | null;
  pe: number | null;
  forward_pe: number | null;
  market_cap: number | null;
  next_earnings_date: string | null;
  source: string;
}

export interface TickerDetail {
  ticker: string;
  name: string | null;
  sector: string | null;
  cik: string | null;
  on_watchlist: boolean;
  notes: string | null;
  fundamentals: Fundamentals | null;
  score: ScoreOut | null;
}

export interface CongressTrade {
  chamber: string;
  member: string;
  ticker: string;
  transaction_date: string;
  disclosure_date: string | null;
  tx_type: string;
  amount_low: number | null;
  amount_high: number | null;
  source: string;
}

export interface InsiderTrade {
  accession_no: string;
  ticker: string;
  insider_name: string | null;
  insider_title: string | null;
  is_officer: boolean | null;
  is_director: boolean | null;
  transaction_date: string;
  code: string;
  shares: number | null;
  price: number | null;
  value: number | null;
  source: string;
}

export interface PricePoint {
  date: string;
  close: number | null;
}

export interface IdeaRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  score: number | null;
  components: Record<string, ScoreComponent> | null;
  buys: number;
  sells: number;
  buyers: number;
  last_activity: string | null;
  net_dollars: number;
  last_close: number | null;
  sparkline: number[];
}

export interface PriceStats {
  ticker: string;
  cagr_1y: number;
  annual_vol: number;
  max_drawdown: number;
  atr_14: number | null;
  last_close: number;
  data_points: number;
  first_date: string;
  last_date: string;
}

export interface ScreenerCriterion {
  value: number | null;
  threshold: Record<string, number>;
  status: "pass" | "fail" | "unknown";
}

export interface ScreenerRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  criteria: Record<string, ScreenerCriterion>;
  passed: number;
  failed: number;
  unknown: number;
  data_as_of: string | null;
}

export interface AiReport {
  ticker: string;
  accession_no: string;
  model: string;
  created_at: string;
  report_md: string;
  sections_meta: Record<string, unknown> | null;
}

export interface Health {
  status: string;
  disclaimer: string;
  ai_analysis_enabled: boolean;
  auto_refresh_enabled: boolean;
  next_auto_refresh: string | null;
}

export interface AlertItem {
  id: number;
  created_at: string;
  ticker: string;
  kind: "congress_trade" | "insider_trade" | "score_cross" | "risk_flag";
  title: string;
  body: string;
  seen: boolean;
}

export interface RiskFlag {
  id: string;
  severity: "warning" | "serious";
  label: string;
  detail: string;
}

export interface ScoreHistoryEntry {
  date: string;
  total: number;
  contributions: Record<string, number>;
  deltas: Record<string, number> | null;
  total_delta: number | null;
}

export interface IngestionRun {
  id: number;
  source: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  rows_upserted: number;
  error: string | null;
}

export interface TrackRecordHorizon {
  n: number;
  mean_excess: number | null;
  hit_rate: number | null;
}

export interface TrackRecordBand {
  band: "bearish" | "neutral" | "bullish";
  horizons: Record<string, TrackRecordHorizon>;
}

export interface TrackRecordComponent {
  component: string;
  n: number;
  horizon_days: number;
  bottom_mean_excess: number | null;
  top_mean_excess: number | null;
  spread: number | null;
}

export interface TrackRecordSummary {
  benchmark: string;
  as_of: string;
  samples: number;
  insufficient_data: boolean;
  min_samples: number;
  bands: TrackRecordBand[];
  components: TrackRecordComponent[];
  note: string;
}

export interface PoliticianRow {
  chamber: "senate" | "house";
  member: string;
  trades: number;
  buys: number;
  sells: number;
  tickers: number;
  measured_buys: number;
  horizon_days: number;
  mean_excess: number | null;
  hit_rate: number | null;
  weight: number;
  last_activity: string | null;
}

export interface InsiderIdeaRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  score: number | null;
  components: Record<string, unknown> | null;
  buyers: number;
  buys: number;
  total_value: number;
  last_activity: string | null;
  last_close: number | null;
  sparkline: number[];
}

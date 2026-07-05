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

export interface IngestionRun {
  id: number;
  source: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  rows_upserted: number;
  error: string | null;
}

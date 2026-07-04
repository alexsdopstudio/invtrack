import type {
  CongressTrade,
  DashboardRow,
  IngestionRun,
  InsiderTrade,
  PricePoint,
  ScoreOut,
  TickerDetail,
  TickerSearchResult,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  scores: () => request<DashboardRow[]>("/api/scores"),
  scoreBreakdown: (ticker: string) => request<ScoreOut>(`/api/scores/${ticker}`),
  searchTickers: (q: string) =>
    request<TickerSearchResult[]>(`/api/tickers/search?q=${encodeURIComponent(q)}`),
  tickerDetail: (ticker: string) => request<TickerDetail>(`/api/tickers/${ticker}`),
  congressTrades: (ticker: string) =>
    request<CongressTrade[]>(`/api/tickers/${ticker}/congress-trades`),
  insiderTrades: (ticker: string) =>
    request<InsiderTrade[]>(`/api/tickers/${ticker}/insider-trades`),
  prices: (ticker: string, days = 365) =>
    request<PricePoint[]>(`/api/tickers/${ticker}/prices?days=${days}`),
  addToWatchlist: (ticker: string) =>
    request("/api/watchlist", { method: "POST", body: JSON.stringify({ ticker }) }),
  removeFromWatchlist: (ticker: string) =>
    request(`/api/watchlist/${ticker}`, { method: "DELETE" }),
  ingest: (source: string) =>
    request<IngestionRun[]>(`/api/ingest/${source}`, { method: "POST" }),
  ingestRuns: () => request<IngestionRun[]>("/api/ingest/runs"),
};

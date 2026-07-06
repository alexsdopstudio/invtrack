import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import AlertsPanel from "../components/AlertsPanel";
import ComponentBars from "../components/ComponentBars";
import HowToRead from "../components/HowToRead";
import InsiderRadarTable from "../components/InsiderRadarTable";
import RadarTable from "../components/RadarTable";
import ScoreBadge from "../components/ScoreBadge";
import Sparkline from "../components/Sparkline";
import TickerSearch from "../components/TickerSearch";

function fmtDate(d: string | null) {
  return d ?? "—";
}

export default function Dashboard() {
  const queryClient = useQueryClient();
  const { data: rows, isLoading, error } = useQuery({ queryKey: ["scores"], queryFn: api.scores });

  const refresh = useMutation({
    mutationFn: () => api.ingest("all"),
    onSettled: () => queryClient.invalidateQueries(),
  });

  const { data: runs } = useQuery({
    queryKey: ["ingest-runs"],
    queryFn: api.ingestRuns,
    refetchInterval: refresh.isPending ? 3000 : false,
  });
  const lastRun = runs?.[0];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-end gap-3">
          <TickerSearch />
          <button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="rounded-md border border-hairline bg-surface px-3 py-1.5 text-sm hover:border-baseline disabled:opacity-50"
            title="Fetch fresh congressional disclosures, insider filings, fundamentals and prices, then rescore"
          >
            {refresh.isPending ? "Refreshing…" : "Refresh data"}
          </button>
        </div>
        <HowToRead />
        {lastRun && (
          <p className="text-xs text-muted">
            Last ingestion: {lastRun.source} · {lastRun.status} · {new Date(lastRun.started_at).toLocaleString()}
            {lastRun.status === "error" && " — see /api/ingest/runs for details"}
          </p>
        )}
      </div>

      <AlertsPanel />

      <RadarTable />

      <InsiderRadarTable />

      <section className="flex flex-col gap-2">
        <div>
          <h1 className="text-xl font-semibold">Your watchlist</h1>
          <p className="text-sm text-ink-2">
            Stocks you track in depth — full signal breakdown, insider filings, fundamentals and
            the returns calculator on each ticker page.
          </p>
        </div>

      {isLoading && <p className="text-sm text-ink-2">Loading…</p>}
      {error && <p className="text-sm text-ink-2">Failed to load scores: {String(error)}</p>}

      {rows && rows.length === 0 && (
        <div className="rounded-lg border border-hairline bg-surface p-6 text-sm text-ink-2">
          Your watchlist is empty. Add a stock from the Radar above (“+ Watch”) or search any
          ticker in the box at the top.
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-hairline bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs text-muted">
                <th className="px-3 py-2 font-medium">Stock</th>
                <th className="px-3 py-2 font-medium" title="Composite score, 0–100 · 50 = neutral. Higher = more bullish signals.">
                  Score
                </th>
                <th className="px-3 py-2 font-medium" title="The three signals behind the score, each 0–100. Hover a bar for its value.">
                  Why — signal mix
                </th>
                <th className="px-3 py-2 font-medium">90d price</th>
                <th className="px-3 py-2 text-right font-medium" title="Red-flag conditions detected in the data — open the ticker for details">
                  Risks
                </th>
                <th className="px-3 py-2 text-right font-medium">Last close</th>
                <th className="px-3 py-2 text-right font-medium" title="Most recent congressional trade of this stock">
                  Last congress trade
                </th>
                <th className="px-3 py-2 text-right font-medium" title="Most recent insider (executive/director) trade">
                  Last insider trade
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.ticker} className="border-b border-hairline last:border-b-0">
                  <td className="px-3 py-2">
                    <Link to={`/ticker/${r.ticker}`} className="font-semibold hover:underline">
                      {r.ticker}
                    </Link>
                    <div className="max-w-48 truncate text-xs text-ink-2">{r.name}</div>
                  </td>
                  <td className="px-3 py-2">
                    <ScoreBadge score={r.score} />
                  </td>
                  <td className="px-3 py-2">
                    <ComponentBars components={r.components} />
                  </td>
                  <td className="px-3 py-2">
                    <Sparkline values={r.sparkline} />
                  </td>
                  <td className="px-3 py-2 text-right">
                    {r.risk_count > 0 ? (
                      <Link
                        to={`/ticker/${r.ticker}`}
                        className="tnum text-sm hover:underline"
                        title={`${r.risk_count} risk flag${r.risk_count > 1 ? "s" : ""} — click for details`}
                      >
                        ⚠️ {r.risk_count}
                      </Link>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tnum">
                    {r.last_close != null ? `$${r.last_close.toFixed(2)}` : "—"}
                  </td>
                  <td className="px-3 py-2 text-right tnum text-ink-2">{fmtDate(r.last_congress_activity)}</td>
                  <td className="px-3 py-2 text-right tnum text-ink-2">{fmtDate(r.last_insider_activity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </section>
    </div>
  );
}

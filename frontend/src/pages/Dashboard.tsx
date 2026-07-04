import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import ComponentBars from "../components/ComponentBars";
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
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Watchlist</h1>
        <div className="flex items-center gap-3">
          <TickerSearch />
          <button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="rounded-md border border-hairline bg-surface px-3 py-1.5 text-sm hover:border-baseline disabled:opacity-50"
          >
            {refresh.isPending ? "Refreshing…" : "Refresh data"}
          </button>
        </div>
      </div>

      {lastRun && (
        <p className="text-xs text-muted">
          Last ingestion: {lastRun.source} · {lastRun.status} · {new Date(lastRun.started_at).toLocaleString()}
          {lastRun.status === "error" && " — see /api/ingest/runs for details"}
        </p>
      )}

      {isLoading && <p className="text-sm text-ink-2">Loading…</p>}
      {error && <p className="text-sm text-ink-2">Failed to load scores: {String(error)}</p>}

      {rows && rows.length === 0 && (
        <div className="rounded-lg border border-hairline bg-surface p-6 text-sm text-ink-2">
          Your watchlist is empty. Search a ticker above and click “+ watch”, then hit
          “Refresh data” to pull congressional trades, insider filings, fundamentals and prices.
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-hairline bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs text-muted">
                <th className="px-3 py-2 font-medium">Ticker</th>
                <th className="px-3 py-2 font-medium">Score</th>
                <th className="px-3 py-2 font-medium">Signal components (0–100)</th>
                <th className="px-3 py-2 font-medium">90d price</th>
                <th className="px-3 py-2 text-right font-medium">Last close</th>
                <th className="px-3 py-2 text-right font-medium">Last congress</th>
                <th className="px-3 py-2 text-right font-medium">Last insider</th>
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
    </div>
  );
}

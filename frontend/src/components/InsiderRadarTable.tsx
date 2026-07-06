import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import ScoreBadge from "./ScoreBadge";
import Sparkline from "./Sparkline";

function fmtDollars(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v.toFixed(0)}`;
}

// Insider Radar: stocks where several insiders just bought with their own
// money, found by the market-wide SEC Form 4 scan — discovery of names the
// user has never searched for.
export default function InsiderRadarTable() {
  const queryClient = useQueryClient();
  const { data: ideas, isLoading } = useQuery({
    queryKey: ["insider-ideas"],
    queryFn: api.insiderIdeas,
  });

  const watch = useMutation({
    mutationFn: (ticker: string) => api.addToWatchlist(ticker),
    onSettled: () => queryClient.invalidateQueries(),
  });

  return (
    <section className="flex flex-col gap-2">
      <div>
        <h1 className="text-xl font-semibold">Radar — insiders are buying</h1>
        <p className="text-sm text-ink-2">
          Stocks where two or more executives or directors bought on the open market within 30
          days, found by scanning every SEC Form 4 filed — historically the strongest free insider
          signal. Ranked by score, then by dollars bought. A research starting point, not advice.
        </p>
      </div>

      {isLoading && <p className="text-sm text-ink-2">Loading…</p>}

      {ideas && ideas.length === 0 && (
        <div className="rounded-lg border border-hairline bg-surface p-6 text-sm text-ink-2">
          No insider buying clusters found yet. The market-wide Form 4 scan runs with the daily
          refresh (or <span className="font-medium text-ink">“Refresh data”</span>) and takes a
          while — clusters appear here as soon as several insiders of the same company have been
          buying.
        </div>
      )}

      {ideas && ideas.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-hairline bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs text-muted">
                <th className="px-3 py-2 font-medium">Stock</th>
                <th className="px-3 py-2 font-medium" title="0–100, 50 = neutral. Shown once fundamentals/prices have been fetched for the ticker.">
                  Score
                </th>
                <th className="px-3 py-2 font-medium" title="Open-market insider purchases (Form 4 code P) in the last 30 days">
                  Insider buying (30d)
                </th>
                <th className="px-3 py-2 font-medium">90d price</th>
                <th className="px-3 py-2 text-right font-medium">Last close</th>
                <th className="px-3 py-2 text-right font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {ideas.map((idea) => (
                <tr key={idea.ticker} className="border-b border-hairline last:border-b-0">
                  <td className="px-3 py-2">
                    <Link to={`/ticker/${idea.ticker}`} className="font-semibold hover:underline">
                      {idea.ticker}
                    </Link>
                    <div className="max-w-48 truncate text-xs text-ink-2">{idea.name ?? "—"}</div>
                  </td>
                  <td className="px-3 py-2">
                    <ScoreBadge score={idea.score} />
                  </td>
                  <td className="px-3 py-2">
                    <span className="tnum">
                      {idea.buyers} insider{idea.buyers === 1 ? "" : "s"} · {fmtDollars(idea.total_value)}
                    </span>
                    <div className="text-xs text-muted">last buy {idea.last_activity ?? "—"}</div>
                  </td>
                  <td className="px-3 py-2">
                    <Sparkline values={idea.sparkline} />
                  </td>
                  <td className="px-3 py-2 text-right tnum">
                    {idea.last_close != null ? `$${idea.last_close.toFixed(2)}` : "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => watch.mutate(idea.ticker)}
                      disabled={watch.isPending}
                      className="rounded-md border border-hairline bg-surface px-2 py-1 text-xs hover:border-baseline disabled:opacity-50"
                      title="Add to your watchlist to track it in depth"
                    >
                      + Watch
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

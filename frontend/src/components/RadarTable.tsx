import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import ScoreBadge from "./ScoreBadge";
import Sparkline from "./Sparkline";

// Radar: stocks surfaced automatically from official congressional
// disclosures — the discovery answer to "which stocks deserve a look?".
export default function RadarTable() {
  const queryClient = useQueryClient();
  const { data: ideas, isLoading } = useQuery({ queryKey: ["ideas"], queryFn: api.ideas });

  const watch = useMutation({
    mutationFn: (ticker: string) => api.addToWatchlist(ticker),
    onSettled: () => queryClient.invalidateQueries(),
  });

  return (
    <section className="flex flex-col gap-2">
      <div>
        <h1 className="text-xl font-semibold">Radar — stocks Congress is buying</h1>
        <p className="text-sm text-ink-2">
          Found automatically from official STOCK Act disclosures over the last 90 days — no
          searching needed. Ranked by score, then by net dollars bought. Disclosures lag up to 45
          days; this is a research starting point, not advice.
        </p>
      </div>

      {isLoading && <p className="text-sm text-ink-2">Loading…</p>}

      {ideas && ideas.length === 0 && (
        <div className="rounded-lg border border-hairline bg-surface p-6 text-sm text-ink-2">
          Nothing on the radar yet. Hit <span className="font-medium text-ink">“Refresh data”</span>{" "}
          to scan recent congressional disclosures — stocks that members of Congress have been
          buying will appear here automatically.
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
                <th className="px-3 py-2 font-medium" title="Congressional trades disclosed in the last 90 days">
                  Congress activity (90d)
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
                      {idea.buys} buy{idea.buys === 1 ? "" : "s"}
                      {idea.buyers > 1 && ` · ${idea.buyers} members`}
                      {idea.sells > 0 && ` · ${idea.sells} sell${idea.sells === 1 ? "" : "s"}`}
                    </span>
                    <div className="text-xs text-muted">last disclosed {idea.last_activity ?? "—"}</div>
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

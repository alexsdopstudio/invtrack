import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import CriterionChip from "../components/CriterionChip";

export default function ScreenerPage() {
  const queryClient = useQueryClient();
  const { data: rows, isLoading } = useQuery({ queryKey: ["screener"], queryFn: api.screener });
  const watch = useMutation({
    mutationFn: (ticker: string) => api.addToWatchlist(ticker),
    onSettled: () => queryClient.invalidateQueries(),
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">Screener — aggressive growth filter</h1>
        <p className="max-w-3xl text-sm text-ink-2">
          Every tracked and Radar stock is checked against seven criteria for small, fast-growing,
          high-margin companies that can fund themselves and whose management owns a real stake:
          market cap $50M–$2B, daily volume ≥150k shares, revenue growth ≥25%, gross margin ≥60%,
          current ratio ≥1.5, cash runway ≥4 quarters, insider ownership ≥10%. Thresholds live in{" "}
          <code className="text-xs">backend/scoring.yaml</code>.
        </p>
        <p className="mt-1 max-w-3xl text-xs text-muted">
          Note: candidates sourced from congressional trading are mostly mega-caps, so the size
          criterion will often fail — that is the filter doing its job, not a bug. “?” means the
          data hasn’t been ingested yet (hit Refresh on the dashboard). A high pass count is a
          research shortlist, not advice.
        </p>
      </div>

      {isLoading && <p className="text-sm text-ink-2">Loading…</p>}

      {rows && rows.length === 0 && (
        <div className="rounded-lg border border-hairline bg-surface p-6 text-sm text-ink-2">
          Nothing to screen yet — add stocks to your watchlist or run “Refresh data” on the
          dashboard so the Radar finds candidates.
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-hairline bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs text-muted">
                <th className="px-3 py-2 font-medium">Stock</th>
                <th className="px-3 py-2 font-medium" title="Criteria passed out of 7">
                  Score
                </th>
                <th className="px-3 py-2 font-medium">Criteria</th>
                <th className="px-3 py-2 text-right font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.ticker} className="border-b border-hairline align-top last:border-b-0">
                  <td className="px-3 py-2.5">
                    <Link to={`/ticker/${row.ticker}`} className="font-semibold hover:underline">
                      {row.ticker}
                    </Link>
                    <div className="max-w-44 truncate text-xs text-ink-2">{row.name ?? "—"}</div>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="tnum text-base font-semibold">{row.passed}</span>
                    <span className="text-xs text-muted">/7</span>
                    {row.unknown > 0 && (
                      <div className="text-[11px] text-muted">{row.unknown} unknown</div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex max-w-2xl flex-wrap gap-1">
                      {Object.entries(row.criteria).map(([name, criterion]) => (
                        <CriterionChip key={name} name={name} criterion={criterion} />
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <button
                      onClick={() => watch.mutate(row.ticker)}
                      disabled={watch.isPending}
                      className="rounded-md border border-hairline bg-surface px-2 py-1 text-xs hover:border-baseline disabled:opacity-50"
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
    </div>
  );
}

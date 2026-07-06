import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

const KIND_META: Record<string, { icon: string; label: string }> = {
  congress_trade: { icon: "🏛", label: "Congress" },
  insider_trade: { icon: "👤", label: "Insider" },
  score_cross: { icon: "⚡", label: "Score" },
};

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "yesterday" : `${days}d ago`;
}

// The retention loop: what happened on your watchlist since you last looked.
export default function AlertsPanel() {
  const queryClient = useQueryClient();
  const { data: alerts } = useQuery({ queryKey: ["alerts"], queryFn: () => api.alerts() });
  const markSeen = useMutation({
    mutationFn: api.markAlertsSeen,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  if (!alerts || alerts.length === 0) return null;
  const unseen = alerts.filter((a) => !a.seen).length;

  return (
    <details className="rounded-lg border border-hairline bg-surface" open={unseen > 0}>
      <summary className="flex cursor-pointer select-none items-center gap-2 px-4 py-3 text-sm font-semibold">
        Activity
        {unseen > 0 && (
          <span className="rounded-full border border-hairline px-1.5 text-xs tnum text-ink-2">
            {unseen} new
          </span>
        )}
        {unseen > 0 && (
          <button
            onClick={(e) => {
              e.preventDefault();
              markSeen.mutate();
            }}
            className="ml-auto rounded border border-hairline px-2 py-0.5 text-xs font-normal text-ink-2 hover:border-baseline"
          >
            Mark all read
          </button>
        )}
      </summary>
      <ul className="max-h-72 overflow-y-auto border-t border-hairline">
        {alerts.slice(0, 30).map((alert) => {
          const meta = KIND_META[alert.kind] ?? { icon: "•", label: alert.kind };
          return (
            <li
              key={alert.id}
              className={`flex items-baseline gap-2 border-b border-hairline px-4 py-2 text-sm last:border-b-0 ${alert.seen ? "opacity-70" : ""}`}
            >
              <span aria-hidden className="shrink-0">{meta.icon}</span>
              <div className="min-w-0">
                <span className="font-medium">
                  <Link to={`/ticker/${alert.ticker}`} className="hover:underline">
                    {alert.ticker}
                  </Link>{" "}
                  — {alert.title}
                </span>
                <p className="truncate text-xs text-ink-2" title={alert.body}>
                  {alert.body}
                </p>
              </div>
              <span className="ml-auto shrink-0 text-xs text-muted">{relativeTime(alert.created_at)}</span>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

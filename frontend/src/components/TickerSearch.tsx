import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export default function TickerSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: results } = useQuery({
    queryKey: ["ticker-search", q],
    queryFn: () => api.searchTickers(q),
    enabled: q.trim().length >= 1,
  });

  const add = async (ticker: string) => {
    await api.addToWatchlist(ticker);
    queryClient.invalidateQueries({ queryKey: ["scores"] });
    setQ("");
    setOpen(false);
  };

  return (
    <div className="relative w-72">
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Search ticker or company…"
        aria-label="Search tickers"
        className="w-full rounded-md border border-hairline bg-surface px-3 py-1.5 text-sm outline-none placeholder:text-muted focus:border-baseline"
      />
      {open && q.trim() && results && results.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-72 w-full overflow-auto rounded-md border border-hairline bg-surface shadow-lg">
          {results.map((r) => (
            <li key={r.ticker} className="flex items-center gap-2 border-b border-hairline px-3 py-1.5 text-sm last:border-b-0">
              <button
                className="flex-1 truncate text-left hover:underline"
                onMouseDown={() => navigate(`/ticker/${r.ticker}`)}
              >
                <span className="font-semibold">{r.ticker}</span>{" "}
                <span className="text-ink-2">{r.name ?? ""}</span>
              </button>
              {r.on_watchlist ? (
                <span className="text-xs text-muted">on watchlist</span>
              ) : (
                <button
                  className="rounded border border-hairline px-1.5 py-0.5 text-xs text-ink-2 hover:border-baseline"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    add(r.ticker);
                  }}
                >
                  + watch
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

import { useState } from "react";
import type { PriceStats } from "../api/types";

function money(v: number): string {
  return v.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

// "Given a budget and a timeframe, what could this become?" — three scenarios
// extrapolated from the stock's own ingested price history (lognormal
// compounding of last-year CAGR ± volatility). Explicitly NOT a forecast:
// the point is to make the range of outcomes and the downside tangible.
export default function ReturnsCalculator({
  stats,
  bench,
}: {
  stats: PriceStats | null;
  bench?: PriceStats | null;
}) {
  const [budget, setBudget] = useState(1000);
  const [years, setYears] = useState(3);

  if (!stats) {
    return (
      <p className="text-sm text-muted">
        Needs at least ~3 months of price history — hit “Refresh data” on the dashboard first.
      </p>
    );
  }

  const mu = Math.log(1 + stats.cagr_1y);
  const sigma = stats.annual_vol;
  const base = budget * Math.exp(mu * years);
  const low = budget * Math.exp(mu * years - sigma * Math.sqrt(years));
  const high = budget * Math.exp(mu * years + sigma * Math.sqrt(years));
  const drawdownValue = budget * (1 + stats.max_drawdown);

  const scenarios: { label: string; sub: string; value: number; color: string }[] = [
    { label: "Pessimistic", sub: "past year repeated, minus one volatility band", value: low, color: "var(--div-neg)" },
    { label: "Base", sub: `past year’s trend (${(stats.cagr_1y * 100).toFixed(1)}%/yr) repeated`, value: base, color: "var(--baseline)" },
    { label: "Optimistic", sub: "past year repeated, plus one volatility band", value: high, color: "var(--div-pos)" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-6">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs text-muted">Budget</span>
          <div className="flex items-center gap-1">
            <span className="text-ink-2">$</span>
            <input
              type="number"
              min={1}
              step={100}
              value={budget}
              onChange={(e) => setBudget(Math.max(1, Number(e.target.value) || 0))}
              className="w-32 rounded-md border border-hairline bg-surface px-2 py-1.5 tnum outline-none focus:border-baseline"
            />
          </div>
        </label>
        <label className="flex min-w-48 flex-1 flex-col gap-1 text-sm sm:max-w-xs">
          <span className="text-xs text-muted">
            Timeframe: <span className="font-medium text-ink tnum">{years} year{years > 1 ? "s" : ""}</span>
          </span>
          <input
            type="range"
            min={1}
            max={10}
            step={1}
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            className="accent-[var(--series-1)]"
          />
        </label>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {scenarios.map((s) => (
          <div key={s.label} className="rounded-md border border-hairline p-3">
            <div className="flex items-center gap-1.5 text-xs text-muted">
              <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.label}
            </div>
            <div className="mt-0.5 text-xl font-semibold tnum">{money(s.value)}</div>
            <div className="mt-0.5 text-xs text-ink-2">{s.sub}</div>
          </div>
        ))}
      </div>

      {bench && (
        <div className="rounded-md border border-hairline p-3 text-sm text-ink-2">
          <span className="font-medium text-ink">Market check:</span> the same{" "}
          <span className="tnum">{money(budget)}</span> in the whole market ({bench.ticker}, past
          year’s {(bench.cagr_1y * 100).toFixed(1)}%/yr repeated) would be{" "}
          <span className="tnum font-medium text-ink">
            {money(budget * Math.exp(Math.log(1 + bench.cagr_1y) * years))}
          </span>
          {stats.cagr_1y < bench.cagr_1y ? (
            <>
              {" "}
              — over the past year this stock <span className="font-medium text-ink">lagged the
              market</span>, with more volatility. Any single-stock bet needs a reason to beat that
              boring alternative.
            </>
          ) : (
            <>
              {" "}
              — this stock beat it over the past year, but with{" "}
              {(stats.annual_vol / Math.max(bench.annual_vol, 0.01)).toFixed(1)}× the volatility.
              Past outperformance is the least reliable thing markets offer.
            </>
          )}
        </div>
      )}

      <div className="rounded-md border border-hairline p-3 text-sm text-ink-2">
        <span className="font-medium text-ink">Stomach check:</span> at the worst point of the last
        12 months this stock was down {(stats.max_drawdown * 100).toFixed(0)}% from its peak — your{" "}
        <span className="tnum">{money(budget)}</span> could have been worth{" "}
        <span className="tnum font-medium text-ink">{money(drawdownValue)}</span> on the way. Only
        invest what you can watch drop that far without selling in panic.
      </div>

      <p className="text-xs text-muted">
        Based purely on this stock’s last {stats.data_points} trading days (through {stats.last_date}
        ): {(stats.cagr_1y * 100).toFixed(1)}%/yr trend, {(stats.annual_vol * 100).toFixed(0)}%
        annualized volatility. This is an <span className="font-medium">illustration of historical
        volatility, not a forecast</span> — extrapolating past returns is exactly the mistake this
        panel exists to make visible. Not financial advice.
      </p>
    </div>
  );
}

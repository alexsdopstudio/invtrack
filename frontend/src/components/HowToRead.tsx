import { COMPONENT_META } from "./ComponentBars";

const EXPLANATIONS: Record<string, { weight: string; text: string }> = {
  fundamentals: {
    weight: "35%",
    text: "Business quality: revenue growth, margins, debt, valuation (from company financials).",
  },
  congress: {
    weight: "30%",
    text: "Are members of Congress buying or selling this stock? From official STOCK Act disclosures — published up to 45 days after the trade, so always lagging.",
  },
  insider: {
    weight: "20%",
    text: "Are the company's own executives and directors buying with their own money? From SEC Form 4 filings.",
  },
  momentum: {
    weight: "15%",
    text: "Is the price above its own 50/200-day averages? Trend confirmation, not prediction.",
  },
};

// The "what does 72 mean" fix: a plain-language legend for the score,
// always available at the top of the dashboard.
export default function HowToRead() {
  return (
    <details className="rounded-lg border border-hairline bg-surface open:pb-4" open>
      <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold">
        How to read this page
      </summary>
      <div className="flex flex-col gap-3 px-4 text-sm text-ink-2">
        <p>
          Every stock gets a <span className="font-semibold text-ink">score from 0 to 100</span>,
          where <span className="font-semibold text-ink">50 means neutral</span> — no signal either
          way. Above ~60 several signals lean bullish{" "}
          <span aria-hidden className="mx-0.5 inline-block h-2 w-2 rounded-full align-baseline" style={{ background: "var(--div-pos)" }} />
          ; below ~40 they lean bearish{" "}
          <span aria-hidden className="mx-0.5 inline-block h-2 w-2 rounded-full align-baseline" style={{ background: "var(--div-neg)" }} />
          . The score blends four independent signals:
        </p>
        <ul className="flex flex-col gap-1.5">
          {COMPONENT_META.map(([key, label, color]) => (
            <li key={key} className="flex items-baseline gap-2">
              <span aria-hidden className="h-2.5 w-2.5 shrink-0 translate-y-px rounded-full" style={{ background: color }} />
              <span>
                <span className="font-medium text-ink">
                  {label} ({EXPLANATIONS[key].weight})
                </span>{" "}
                — {EXPLANATIONS[key].text}
              </span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted">
          If a signal has no data for a stock, the others take over its weight — open a ticker to
          see exactly what went into its score. A high score is a{" "}
          <span className="font-medium text-ink-2">shortlist for your own research</span>, never a
          recommendation to buy.
        </p>
      </div>
    </details>
  );
}

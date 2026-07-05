import type { ScreenerCriterion } from "../api/types";

// Status colors are reserved for state (pass/fail) and always paired with a
// symbol + label, never color alone.
const STATUS = {
  pass: { symbol: "✓", color: "var(--delta-good)" },
  fail: { symbol: "✗", color: "var(--div-neg)" },
  unknown: { symbol: "?", color: "var(--muted)" },
} as const;

export const CRITERION_LABELS: Record<string, { label: string; fmt: (v: number) => string }> = {
  market_cap: { label: "Size $50M–$2B", fmt: (v) => (v >= 1e12 ? `$${(v / 1e12).toFixed(1)}T` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${(v / 1e6).toFixed(0)}M`) },
  avg_daily_volume: { label: "Volume ≥150k/d", fmt: (v) => `${Math.round(v / 1000)}k/d` },
  revenue_growth_yoy: { label: "Growth ≥25%", fmt: (v) => `${(v * 100).toFixed(0)}%` },
  gross_margin: { label: "Gross margin ≥60%", fmt: (v) => `${(v * 100).toFixed(0)}%` },
  current_ratio: { label: "Current ratio ≥1.5", fmt: (v) => v.toFixed(1) },
  cash_runway_quarters: { label: "Runway ≥4qtr", fmt: (v) => `${v.toFixed(0)}qtr` },
  insider_ownership: { label: "Insiders ≥10%", fmt: (v) => `${(v * 100).toFixed(1)}%` },
};

export default function CriterionChip({ name, criterion }: { name: string; criterion: ScreenerCriterion }) {
  const meta = CRITERION_LABELS[name] ?? { label: name, fmt: (v: number) => String(v) };
  const s = STATUS[criterion.status];
  const valueText =
    criterion.status === "unknown"
      ? "no data"
      : criterion.value == null
        ? "cash-generative" // infinite runway is reported as null value + pass
        : meta.fmt(criterion.value);
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md border border-hairline px-1.5 py-0.5 text-[11px] leading-4"
      title={`${meta.label} — ${criterion.status}: ${valueText}`}
    >
      <span aria-hidden style={{ color: s.color }} className="font-bold">
        {s.symbol}
      </span>
      <span className="text-ink-2">{meta.label}</span>
      <span className="tnum text-muted">{valueText}</span>
    </span>
  );
}

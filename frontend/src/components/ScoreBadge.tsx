// 0-100 composite score. Polarity around the 50 neutral midpoint uses the
// diverging pair (blue bullish / red bearish / gray neutral) as a small mark;
// the number itself stays in ink per the "text wears text tokens" rule.

export function scoreLabel(score: number | null): string {
  if (score == null) return "no data yet";
  if (score >= 60) return "leaning bullish";
  if (score <= 40) return "leaning bearish";
  return "neutral / mixed";
}

export default function ScoreBadge({
  score,
  size = "md",
  showLabel = false,
}: {
  score: number | null;
  size?: "md" | "lg";
  showLabel?: boolean;
}) {
  const color =
    score == null
      ? "var(--muted)"
      : score >= 60
        ? "var(--div-pos)"
        : score <= 40
          ? "var(--div-neg)"
          : "var(--baseline)";
  const cls =
    size === "lg"
      ? "gap-2.5 rounded-lg px-3 py-1.5 text-2xl"
      : "gap-2 rounded-md px-2 py-0.5 text-sm";
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`inline-flex items-center border border-hairline bg-surface font-semibold tnum ${cls}`}
        title={`Composite signal score: ${score == null ? "no data" : `${score.toFixed(0)} / 100`} — 50 is neutral, higher means more bullish signals. Open the ticker for the full breakdown.`}
      >
        <span
          aria-hidden
          className={size === "lg" ? "h-3 w-3 rounded-full" : "h-2 w-2 rounded-full"}
          style={{ background: color }}
        />
        {score == null ? "—" : score.toFixed(0)}
      </span>
      {showLabel && (
        <span className={size === "lg" ? "text-sm text-ink-2" : "text-xs text-ink-2"}>
          {scoreLabel(score)}
          <span className="text-muted"> · 50 = neutral</span>
        </span>
      )}
    </span>
  );
}

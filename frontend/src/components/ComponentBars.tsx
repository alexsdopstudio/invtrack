import type { ScoreComponent } from "../api/types";

// Fixed categorical slot order — never cycled, color follows the component.
export const COMPONENT_META: [key: string, label: string, cssVar: string][] = [
  ["fundamentals", "Fundamentals", "var(--series-1)"],
  ["congress", "Congress", "var(--series-2)"],
  ["insider", "Insider", "var(--series-3)"],
  ["momentum", "Momentum", "var(--series-4)"],
];

// Compact per-component sub-score bars (0-100 scale) with adjacent text
// labels — the relief for light-mode series colors below 3:1 contrast.
export default function ComponentBars({
  components,
  showValues = false,
}: {
  components: Record<string, ScoreComponent> | null;
  showValues?: boolean;
}) {
  if (!components) return <span className="text-xs text-muted">no score yet</span>;
  return (
    <div className="flex min-w-36 flex-col gap-1">
      {COMPONENT_META.map(([key, label, color]) => {
        const c = components[key];
        const missing = !c || c.status !== "ok" || c.score == null;
        return (
          <div key={key} className="flex items-center gap-2" title={`${label}: ${missing ? "no data" : `${c!.score!.toFixed(0)} / 100`}`}>
            <span className="w-20 shrink-0 text-[11px] leading-3 text-ink-2">{label}</span>
            <span className="relative h-1.5 w-full overflow-hidden rounded-sm bg-grid">
              {!missing && (
                <span
                  className="absolute inset-y-0 left-0 rounded-sm"
                  style={{ width: `${c!.score}%`, background: color }}
                />
              )}
            </span>
            {showValues && (
              <span className="w-8 shrink-0 text-right text-[11px] tnum text-ink-2">
                {missing ? "—" : c!.score!.toFixed(0)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

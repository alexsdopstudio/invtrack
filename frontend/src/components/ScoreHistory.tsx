import { useQuery } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { COMPONENT_META } from "./ComponentBars";

const W = 720;
const H = 180;
const PAD = { top: 10, right: 12, bottom: 22, left: 34 };

// Score over time with the 40/60 polarity guides, plus a plain-language
// "what changed" list — the audit's "why did my score change" fix.
export default function ScoreHistory({ ticker }: { ticker: string }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const { data } = useQuery({
    queryKey: ["score-history", ticker],
    queryFn: () => api.scoreHistory(ticker),
  });

  const changes = useMemo(() => {
    if (!data) return [];
    const labels = Object.fromEntries(COMPONENT_META.map(([k, label]) => [k, label]));
    return [...data]
      .reverse()
      .filter((e) => e.total_delta != null && Math.abs(e.total_delta) >= 1)
      .slice(0, 4)
      .map((e) => {
        const parts = Object.entries(e.deltas ?? {})
          .filter(([, v]) => Math.abs(v) >= 0.5)
          .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
          .map(([k, v]) => `${labels[k] ?? k} ${v > 0 ? "+" : ""}${v.toFixed(1)}`);
        return { ...e, parts };
      });
  }, [data]);

  if (!data || data.length < 2) {
    return (
      <p className="text-sm text-muted">
        Not enough score history yet — the daily auto-refresh builds this timeline over time.
      </p>
    );
  }

  const x = (i: number) => PAD.left + (i / (data.length - 1)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - v / 100) * (H - PAD.top - PAD.bottom);
  const path = data.map((e, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(e.total).toFixed(1)}`).join("");

  const onMove = (e: React.MouseEvent) => {
    const rect = svgRef.current!.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - PAD.left) / (W - PAD.left - PAD.right)) * (data.length - 1));
    setHover(Math.max(0, Math.min(data.length - 1, i)));
  };
  const h = hover != null ? data[hover] : null;

  return (
    <div className="flex flex-col gap-3">
      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          role="img"
          aria-label="Composite score over time"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          {[0, 50, 100].map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth="1" />
              <text x={PAD.left - 6} y={y(t) + 3.5} textAnchor="end" fontSize="10" fill="var(--muted)">
                {t}
              </text>
            </g>
          ))}
          {/* polarity guides: above 60 leans bullish, below 40 bearish */}
          <line x1={PAD.left} x2={W - PAD.right} y1={y(60)} y2={y(60)} stroke="var(--div-pos)" strokeWidth="1" strokeDasharray="4 4" opacity="0.5" />
          <line x1={PAD.left} x2={W - PAD.right} y1={y(40)} y2={y(40)} stroke="var(--div-neg)" strokeWidth="1" strokeDasharray="4 4" opacity="0.5" />
          <text x={W - PAD.right} y={y(60) - 3} textAnchor="end" fontSize="9" fill="var(--muted)">60 bullish</text>
          <text x={W - PAD.right} y={y(40) + 10} textAnchor="end" fontSize="9" fill="var(--muted)">40 bearish</text>
          {[0, Math.floor(data.length / 2), data.length - 1].map((i) => (
            <text key={i} x={x(i)} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--muted)">
              {data[i].date}
            </text>
          ))}
          <path d={path} fill="none" stroke="var(--series-1)" strokeWidth="2" strokeLinejoin="round" />
          {h && hover != null && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--baseline)" strokeWidth="1" />
              <circle cx={x(hover)} cy={y(h.total)} r="4" fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth="2" />
            </g>
          )}
        </svg>
        {h && hover != null && (
          <div
            className="pointer-events-none absolute top-1 rounded-md border border-hairline bg-surface px-2 py-1 text-xs shadow-sm"
            style={{ left: `calc(${((x(hover) / W) * 100).toFixed(1)}% ${x(hover) > W / 2 ? "- 110px" : "+ 12px"})` }}
          >
            <div className="text-muted">{h.date}</div>
            <div className="font-semibold tnum">
              {h.total.toFixed(1)}
              {h.total_delta != null && (
                <span className="ml-1 font-normal text-ink-2">
                  ({h.total_delta > 0 ? "+" : ""}
                  {h.total_delta.toFixed(1)})
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {changes.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-muted">Recent changes</h3>
          <ul className="mt-1 flex flex-col gap-0.5 text-sm text-ink-2">
            {changes.map((c) => (
              <li key={c.date}>
                <span className="tnum text-muted">{c.date}:</span>{" "}
                <span className="tnum font-medium text-ink">
                  {(c.total - (c.total_delta ?? 0)).toFixed(0)} → {c.total.toFixed(0)}
                </span>
                {c.parts.length > 0 && <span> · {c.parts.join(", ")}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

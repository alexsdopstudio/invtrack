import { useMemo, useRef, useState } from "react";
import type { PricePoint } from "../api/types";

const W = 720;
const H = 220;
const PAD = { top: 10, right: 12, bottom: 22, left: 48 };

// Single-series price line (no legend needed — the title names it) with the
// default hover layer: crosshair + nearest-point tooltip + ringed marker.
export default function PriceChart({ points }: { points: PricePoint[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const data = useMemo(() => points.filter((p) => p.close != null) as { date: string; close: number }[], [points]);
  if (data.length < 2) return <p className="text-sm text-muted">No price history ingested yet.</p>;

  const closes = data.map((d) => d.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;
  const x = (i: number) => PAD.left + (i / (data.length - 1)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - (v - min) / span) * (H - PAD.top - PAD.bottom);
  const path = data.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.close).toFixed(1)}`).join("");

  const yTicks = [min, min + span / 2, max];
  const xTickIdx = [0, Math.floor(data.length / 2), data.length - 1];

  const onMove = (e: React.MouseEvent) => {
    const rect = svgRef.current!.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - PAD.left) / (W - PAD.left - PAD.right)) * (data.length - 1));
    setHover(Math.max(0, Math.min(data.length - 1, i)));
  };

  const h = hover != null ? data[hover] : null;

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Daily closing price"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth="1" />
            <text x={PAD.left - 6} y={y(t) + 3.5} textAnchor="end" fontSize="10" fill="var(--muted)">
              ${t.toFixed(0)}
            </text>
          </g>
        ))}
        {xTickIdx.map((i) => (
          <text key={i} x={x(i)} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--muted)">
            {data[i].date}
          </text>
        ))}
        <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom} stroke="var(--baseline)" strokeWidth="1" />
        <path d={path} fill="none" stroke="var(--series-1)" strokeWidth="2" strokeLinejoin="round" />
        {h && hover != null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--baseline)" strokeWidth="1" />
            <circle cx={x(hover)} cy={y(h.close)} r="4" fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth="2" />
          </g>
        )}
      </svg>
      {h && hover != null && (
        <div
          className="pointer-events-none absolute top-1 rounded-md border border-hairline bg-surface px-2 py-1 text-xs shadow-sm"
          style={{ left: `calc(${((x(hover) / W) * 100).toFixed(1)}% ${x(hover) > W / 2 ? "- 110px" : "+ 12px"})` }}
        >
          <div className="text-muted">{h.date}</div>
          <div className="font-semibold tnum">${h.close.toFixed(2)}</div>
        </div>
      )}
    </div>
  );
}

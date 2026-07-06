import type { Fundamentals } from "../api/types";

function fmtPct(v: number | null) {
  return v == null ? "—" : `${(v * 100).toFixed(1)}%`;
}
function fmtNum(v: number | null, digits = 1) {
  return v == null ? "—" : v.toFixed(digits);
}
function fmtCap(v: number | null) {
  if (v == null) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  return `$${(v / 1e6).toFixed(0)}M`;
}

export default function FundamentalsPanel({ f }: { f: Fundamentals | null }) {
  if (!f) return <p className="text-sm text-muted">No fundamentals ingested yet.</p>;
  const tiles: [string, string][] = [
    ["Revenue growth (YoY)", fmtPct(f.revenue_growth_yoy)],
    ["Gross margin", fmtPct(f.gross_margin)],
    ["Operating margin", fmtPct(f.operating_margin)],
    ["Debt / equity", fmtNum(f.debt_to_equity, 2)],
    ["P/E (trailing)", fmtNum(f.pe)],
    ["P/E (forward)", fmtNum(f.forward_pe)],
    ["Market cap", fmtCap(f.market_cap)],
    ["Next earnings", f.next_earnings_date ?? "—"],
  ];
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {tiles.map(([label, value]) => (
          <div key={label} className="rounded-md border border-hairline p-3">
            <div className="text-xs text-muted">{label}</div>
            <div className="mt-0.5 text-lg font-semibold">{value}</div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">
        source: {f.source} · as of {f.as_of}
      </p>
    </div>
  );
}

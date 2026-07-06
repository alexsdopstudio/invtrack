import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { COMPONENT_META } from "../components/ComponentBars";

function pct(v: number | null, signed = true): string {
  if (v === null) return "—";
  const s = (v * 100).toFixed(1);
  return `${signed && v > 0 ? "+" : ""}${s}%`;
}

function excessColor(v: number | null): string | undefined {
  if (v === null) return undefined;
  return v >= 0 ? "var(--div-pos)" : "var(--div-neg)";
}

const BAND_LABELS: Record<string, string> = {
  bullish: "Bullish scores (>60)",
  neutral: "Neutral scores (40–60)",
  bearish: "Bearish scores (<40)",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-hairline bg-surface p-4">
      <h2 className="mb-1 text-sm font-semibold text-ink-2">{title}</h2>
      {children}
    </section>
  );
}

export default function TrackRecordPage() {
  const { data: tr } = useQuery({ queryKey: ["track-record"], queryFn: api.trackRecord });
  const { data: pols } = useQuery({ queryKey: ["politicians"], queryFn: api.politicians });

  const componentLabel = (key: string) =>
    COMPONENT_META.find(([k]) => k === key)?.[1] ?? key;
  const componentColor = (key: string) => COMPONENT_META.find(([k]) => k === key)?.[2];

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Does the score work?</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">
          Every stored score is compared with what the price actually did afterwards, measured as{" "}
          <span className="font-medium text-ink">excess return over {tr?.benchmark ?? "the benchmark"}</span>{" "}
          (beating the market, not just going up). This is the tool grading its own homework on the
          tickers it happened to track — a small, lagging sample for tuning{" "}
          <code className="text-xs">scoring.yaml</code>, never a promise about the future.
        </p>
      </div>

      {tr?.insufficient_data && (
        <p className="rounded-lg border border-hairline bg-surface px-4 py-3 text-sm text-ink-2">
          Not enough history yet: {tr.samples} measurable samples of at least {tr.min_samples}.
          Scores need 30–90 days to elapse before they can be judged — keep the daily refresh
          running and this page fills in by itself.
        </p>
      )}

      <Section title="What happened after each score band">
        <p className="mb-3 text-xs text-muted">
          If the score carries signal, bullish rows should show positive excess returns and bearish
          rows negative — with samples (n) big enough to mean anything.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs text-muted">
                <th className="py-2 pr-4 font-medium">Score band</th>
                <th className="py-2 pr-4 font-medium">Horizon</th>
                <th className="py-2 pr-4 font-medium">Samples</th>
                <th className="py-2 pr-4 font-medium">Avg excess return</th>
                <th className="py-2 font-medium">Beat the market</th>
              </tr>
            </thead>
            <tbody>
              {(tr?.bands ?? []).flatMap((band) =>
                Object.entries(band.horizons).map(([h, stats], i) => (
                  <tr key={`${band.band}-${h}`} className="border-b border-hairline last:border-0">
                    <td className="py-2 pr-4 font-medium text-ink">
                      {i === 0 ? BAND_LABELS[band.band] ?? band.band : ""}
                    </td>
                    <td className="py-2 pr-4 text-ink-2">{h} days</td>
                    <td className="py-2 pr-4 tnum text-ink-2">{stats.n}</td>
                    <td className="py-2 pr-4 tnum font-medium" style={{ color: excessColor(stats.mean_excess) }}>
                      {pct(stats.mean_excess)}
                    </td>
                    <td className="py-2 tnum text-ink-2">{pct(stats.hit_rate, false)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Which components carry the signal">
        <p className="mb-3 text-xs text-muted">
          Within measured samples: average excess return ({tr?.components[0]?.horizon_days ?? 90}d)
          when a component scored in its top third vs its bottom third. A positive spread means the
          component pointed the right way; near zero means it added noise. Use this to retune the
          weights in scoring.yaml.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs text-muted">
                <th className="py-2 pr-4 font-medium">Component</th>
                <th className="py-2 pr-4 font-medium">Samples</th>
                <th className="py-2 pr-4 font-medium">Low scores led to</th>
                <th className="py-2 pr-4 font-medium">High scores led to</th>
                <th className="py-2 font-medium">Spread</th>
              </tr>
            </thead>
            <tbody>
              {(tr?.components ?? []).map((c) => (
                <tr key={c.component} className="border-b border-hairline last:border-0">
                  <td className="py-2 pr-4">
                    <span className="flex items-center gap-2 font-medium text-ink">
                      <span
                        aria-hidden
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ background: componentColor(c.component) }}
                      />
                      {componentLabel(c.component)}
                    </span>
                  </td>
                  <td className="py-2 pr-4 tnum text-ink-2">{c.n}</td>
                  <td className="py-2 pr-4 tnum" style={{ color: excessColor(c.bottom_mean_excess) }}>
                    {pct(c.bottom_mean_excess)}
                  </td>
                  <td className="py-2 pr-4 tnum" style={{ color: excessColor(c.top_mean_excess) }}>
                    {pct(c.top_mean_excess)}
                  </td>
                  <td className="py-2 tnum font-medium" style={{ color: excessColor(c.spread) }}>
                    {pct(c.spread)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Politician leaderboard — whose trades were worth following">
        <p className="mb-3 text-xs text-muted">
          Excess return vs the benchmark in the {pols?.[0]?.horizon_days ?? 90} days after each
          member's disclosed buys (only tickers with ingested prices are measurable). Members with a
          proven record get more weight in the congress score — the Weight column shows exactly how
          much.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs text-muted">
                <th className="py-2 pr-4 font-medium">Member</th>
                <th className="py-2 pr-4 font-medium">Chamber</th>
                <th className="py-2 pr-4 font-medium">Buys / Sells</th>
                <th className="py-2 pr-4 font-medium">Measured buys</th>
                <th className="py-2 pr-4 font-medium">Avg excess</th>
                <th className="py-2 pr-4 font-medium">Beat market</th>
                <th className="py-2 font-medium">Weight in score</th>
              </tr>
            </thead>
            <tbody>
              {(pols ?? []).map((p) => (
                <tr key={`${p.chamber}-${p.member}`} className="border-b border-hairline last:border-0">
                  <td className="py-2 pr-4 font-medium text-ink">{p.member}</td>
                  <td className="py-2 pr-4 text-ink-2 capitalize">{p.chamber}</td>
                  <td className="py-2 pr-4 tnum text-ink-2">
                    {p.buys} / {p.sells}
                  </td>
                  <td className="py-2 pr-4 tnum text-ink-2">{p.measured_buys}</td>
                  <td className="py-2 pr-4 tnum font-medium" style={{ color: excessColor(p.mean_excess) }}>
                    {pct(p.mean_excess)}
                  </td>
                  <td className="py-2 pr-4 tnum text-ink-2">{pct(p.hit_rate, false)}</td>
                  <td className="py-2 tnum text-ink-2">×{p.weight.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(pols ?? []).length === 0 && (
          <p className="text-sm text-muted">No congressional trades ingested yet.</p>
        )}
      </Section>

      <p className="text-xs text-muted">
        {tr?.note} Wondering about a specific stock? Open its page from the{" "}
        <Link to="/" className="underline">
          dashboard
        </Link>{" "}
        to see its own score timeline.
      </p>
    </div>
  );
}

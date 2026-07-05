import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import FundamentalsPanel from "../components/FundamentalsPanel";
import PriceChart from "../components/PriceChart";
import ReturnsCalculator from "../components/ReturnsCalculator";
import ScoreBadge from "../components/ScoreBadge";
import ScoreBreakdown from "../components/ScoreBreakdown";
import { CongressTradesTable, InsiderTradesTable } from "../components/TradesTables";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-hairline bg-surface p-4">
      <h2 className="mb-3 text-sm font-semibold text-ink-2">{title}</h2>
      {children}
    </section>
  );
}

export default function TickerDetailPage() {
  const { ticker = "" } = useParams();
  const queryClient = useQueryClient();

  const { data: detail, error } = useQuery({
    queryKey: ["ticker", ticker],
    queryFn: () => api.tickerDetail(ticker),
  });
  const { data: congress } = useQuery({
    queryKey: ["congress", ticker],
    queryFn: () => api.congressTrades(ticker),
  });
  const { data: insider } = useQuery({
    queryKey: ["insider", ticker],
    queryFn: () => api.insiderTrades(ticker),
  });
  const { data: prices } = useQuery({
    queryKey: ["prices", ticker],
    queryFn: () => api.prices(ticker),
  });
  const { data: stats } = useQuery({
    queryKey: ["stats", ticker],
    queryFn: () => api.stats(ticker),
    retry: false, // 404 just means not enough price history yet
  });

  const toggleWatch = useMutation({
    mutationFn: () =>
      detail?.on_watchlist ? api.removeFromWatchlist(ticker) : api.addToWatchlist(ticker),
    onSettled: () => queryClient.invalidateQueries(),
  });

  if (error) return <p className="text-sm text-ink-2">Could not load {ticker}: {String(error)}</p>;
  if (!detail) return <p className="text-sm text-ink-2">Loading…</p>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/" className="text-sm text-ink-2 hover:underline">
          ← watchlist
        </Link>
        <h1 className="text-2xl font-semibold">{detail.ticker}</h1>
        <span className="text-ink-2">{detail.name}</span>
        {detail.sector && (
          <span className="rounded border border-hairline px-1.5 py-0.5 text-xs text-ink-2">{detail.sector}</span>
        )}
        <ScoreBadge score={detail.score?.total ?? null} size="lg" showLabel />
        <button
          onClick={() => toggleWatch.mutate()}
          disabled={toggleWatch.isPending}
          className="ml-auto rounded-md border border-hairline bg-surface px-3 py-1.5 text-sm hover:border-baseline disabled:opacity-50"
        >
          {detail.on_watchlist ? "Remove from watchlist" : "Add to watchlist"}
        </button>
      </div>
      {detail.score?.computed_at && (
        <p className="text-xs text-muted">
          Composite score computed {new Date(detail.score.computed_at).toLocaleString()} — weights are
          configurable in backend/scoring.yaml.
        </p>
      )}

      <Section title="Why this score — component breakdown with provenance">
        {detail.score ? <ScoreBreakdown score={detail.score} /> : <p className="text-sm text-muted">No score yet.</p>}
      </Section>

      <Section title="Returns calculator — what could a given budget become?">
        <ReturnsCalculator stats={stats ?? null} />
      </Section>

      <Section title="Price — daily close, last 12 months">
        <PriceChart points={prices ?? []} />
      </Section>

      <Section title="Fundamentals">
        <FundamentalsPanel f={detail.fundamentals} />
      </Section>

      <Section title="Congressional trades (STOCK Act disclosures — lagged up to 45 days)">
        <CongressTradesTable trades={congress ?? []} />
      </Section>

      <Section title="Insider trades (SEC Form 4)">
        <InsiderTradesTable trades={insider ?? []} />
      </Section>
    </div>
  );
}

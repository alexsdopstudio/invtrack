import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import AiReportView from "./AiReportView";

// Opt-in Claude analysis of the ticker's latest 10-K. Disabled (with setup
// hint) when the backend has no ANTHROPIC_API_KEY configured.
export default function AnalyzeFiling({ ticker }: { ticker: string }) {
  const queryClient = useQueryClient();
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: api.health });
  const { data: report } = useQuery({
    queryKey: ["ai-report", ticker],
    queryFn: () => api.aiReport(ticker),
    retry: false, // 404 = no report yet
  });

  const analyze = useMutation({
    mutationFn: () => api.analyze(ticker),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-report", ticker] }),
  });

  const enabled = health?.ai_analysis_enabled ?? false;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={() => analyze.mutate()}
          disabled={!enabled || analyze.isPending}
          className="rounded-md border border-hairline bg-surface px-3 py-1.5 text-sm hover:border-baseline disabled:cursor-not-allowed disabled:opacity-50"
          title={
            enabled
              ? "Fetches Item 1 / 1A / 7 of the latest 10-K from SEC EDGAR and has Claude write a forensic-style review. Uses your API key; costs roughly $0.25–0.50 per new filing."
              : "Disabled — set ANTHROPIC_API_KEY in .env (backend) to enable AI filing analysis."
          }
        >
          {analyze.isPending
            ? "Analyzing 10-K… (can take a couple of minutes)"
            : report
              ? "Re-check latest 10-K"
              : "Analyze latest 10-K"}
        </button>
        {!enabled && (
          <span className="text-xs text-muted">
            Optional feature — needs a Claude API key in the backend .env (the rest of InvTrack
            stays free).
          </span>
        )}
        {analyze.isError && (
          <span className="text-xs" style={{ color: "var(--div-neg)" }}>
            {String((analyze.error as Error).message)}
          </span>
        )}
      </div>
      {report && <AiReportView report={report} />}
    </div>
  );
}

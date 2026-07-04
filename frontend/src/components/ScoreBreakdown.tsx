import type { ScoreOut } from "../api/types";
import { COMPONENT_META } from "./ComponentBars";

function InputsSummary({ inputs }: { inputs: Record<string, unknown> }) {
  const entries = Object.entries(inputs).filter(([k, v]) => v != null && k !== "metrics" && typeof v !== "object");
  const cluster = inputs.cluster as { direction?: string; members?: string[]; insiders?: string[] } | null;
  const metrics = inputs.metrics as Record<string, { value: number | null; band: string | null }> | undefined;
  return (
    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-ink-2">
      {entries.map(([k, v]) => (
        <span key={k}>
          <span className="text-muted">{k.replaceAll("_", " ")}:</span>{" "}
          <span className="tnum">{typeof v === "number" ? v.toLocaleString() : String(v)}</span>
        </span>
      ))}
      {cluster && (
        <span>
          <span className="text-muted">cluster:</span> {cluster.direction} ×{" "}
          {(cluster.members ?? cluster.insiders ?? []).length}
        </span>
      )}
      {metrics &&
        Object.entries(metrics).map(([m, r]) => (
          <span key={m}>
            <span className="text-muted">{m.replaceAll("_", " ")}:</span>{" "}
            <span className="tnum">{r.value ?? "—"}</span>
            {r.band && <span className="text-muted"> ({r.band})</span>}
          </span>
        ))}
    </div>
  );
}

// The "why this score" view: every component's sub-score, weight,
// contribution, source and data timestamp — never a number without provenance.
export default function ScoreBreakdown({ score }: { score: ScoreOut }) {
  if (!score.components) return <p className="text-sm text-muted">No score computed yet — ingest data first.</p>;
  return (
    <div className="flex flex-col gap-3">
      {COMPONENT_META.map(([key, label, color]) => {
        const c = score.components![key];
        if (!c) return null;
        const missing = c.status !== "ok";
        return (
          <div key={key} className="rounded-md border border-hairline p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
              <span className="font-medium">{label}</span>
              {missing ? (
                <span className="text-xs text-muted">no data in window — weight renormalized to other components</span>
              ) : (
                <>
                  <span className="tnum text-sm">{c.score!.toFixed(1)} / 100</span>
                  <span className="text-xs text-muted">
                    weight {c.weight} → {(c.normalized_weight * 100).toFixed(0)}% · contributes{" "}
                    <span className="tnum">{c.contribution.toFixed(1)}</span> pts
                  </span>
                  <span className="ml-auto text-xs text-muted">
                    {c.source} · data as of {c.data_as_of}
                  </span>
                </>
              )}
            </div>
            {!missing && (
              <>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-sm bg-grid">
                  <div className="h-full rounded-sm" style={{ width: `${c.score}%`, background: color }} />
                </div>
                {c.inputs && <InputsSummary inputs={c.inputs} />}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

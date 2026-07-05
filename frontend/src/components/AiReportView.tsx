import type { AiReport } from "../api/types";

// Minimal renderer for the report's markdown (## sections, paragraphs,
// - bullets, **bold**) — keeps the bundle free of a full markdown dependency.
function renderInline(text: string) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part));
}

function Markdown({ md }: { md: string }) {
  const blocks = md.split(/\n{2,}/);
  return (
    <div className="flex flex-col gap-2 text-sm leading-relaxed">
      {blocks.map((block, i) => {
        const trimmed = block.trim();
        if (!trimmed) return null;
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={i} className="mt-2 text-sm font-semibold text-ink">
              {trimmed.slice(3)}
            </h3>
          );
        }
        const lines = trimmed.split("\n");
        if (lines.every((l) => /^\s*[-*•]\s/.test(l))) {
          return (
            <ul key={i} className="ml-4 flex list-disc flex-col gap-1 text-ink-2">
              {lines.map((l, j) => (
                <li key={j}>{renderInline(l.replace(/^\s*[-*•]\s/, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="text-ink-2">
            {renderInline(trimmed)}
          </p>
        );
      })}
    </div>
  );
}

export default function AiReportView({ report }: { report: AiReport }) {
  return (
    <div className="flex flex-col gap-3">
      <Markdown md={report.report_md} />
      <p className="border-t border-hairline pt-2 text-xs text-muted">
        AI-generated analysis ({report.model}) of 10-K accession {report.accession_no}, created{" "}
        {new Date(report.created_at).toLocaleString()}. It can be wrong — verify against the{" "}
        original filing on sec.gov before acting on it. Not financial advice.
      </p>
    </div>
  );
}

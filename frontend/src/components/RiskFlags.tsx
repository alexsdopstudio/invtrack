import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

// Status colors are reserved for state and never carry meaning alone —
// each flag pairs color with an icon and a text label.
const SEVERITY = {
  serious: { color: "var(--div-neg)", icon: "⛔", label: "serious" },
  warning: { color: "#fab219", icon: "⚠️", label: "warning" },
} as const;

export default function RiskFlags({ ticker }: { ticker: string }) {
  const { data: flags } = useQuery({
    queryKey: ["risks", ticker],
    queryFn: () => api.risks(ticker),
  });

  if (!flags) return null;
  if (flags.length === 0) {
    return (
      <p className="text-sm text-ink-2">
        No red flags detected in the ingested data. (Absence of flags is not an all-clear —
        only these specific conditions are checked.)
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {flags.map((flag) => {
        const s = SEVERITY[flag.severity as keyof typeof SEVERITY] ?? SEVERITY.warning;
        return (
          <li key={flag.id} className="flex items-baseline gap-2 rounded-md border border-hairline p-3">
            <span aria-hidden>{s.icon}</span>
            <div>
              <span className="text-sm font-medium">{flag.label}</span>
              <span className="ml-2 text-xs uppercase tracking-wide" style={{ color: s.color }}>
                {s.label}
              </span>
              <p className="text-sm text-ink-2">{flag.detail}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

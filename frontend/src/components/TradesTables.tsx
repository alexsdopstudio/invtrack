import type { CongressTrade, InsiderTrade } from "../api/types";

function amount(low: number | null, high: number | null) {
  if (low == null) return "—";
  const f = (v: number) => `$${v.toLocaleString()}`;
  return high != null ? `${f(low)} – ${f(high)}` : `${f(low)}+`;
}

const txTypeLabel: Record<string, string> = { buy: "Buy", sell: "Sell", exchange: "Exchange" };
const codeLabel: Record<string, string> = { P: "Buy (open market)", S: "Sell", A: "Award/grant", M: "Option exercise", G: "Gift", F: "Tax withholding" };

export function CongressTradesTable({ trades }: { trades: CongressTrade[] }) {
  if (trades.length === 0)
    return <p className="text-sm text-muted">No congressional trades ingested for this ticker (disclosures lag up to 45 days).</p>;
  return (
    <div className="overflow-x-auto rounded-md border border-hairline">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-hairline text-left text-xs text-muted">
            <th className="px-3 py-1.5 font-medium">Member</th>
            <th className="px-3 py-1.5 font-medium">Chamber</th>
            <th className="px-3 py-1.5 font-medium">Type</th>
            <th className="px-3 py-1.5 text-right font-medium">Amount range</th>
            <th className="px-3 py-1.5 text-right font-medium">Traded</th>
            <th className="px-3 py-1.5 text-right font-medium">Disclosed</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={i} className="border-b border-hairline last:border-b-0">
              <td className="px-3 py-1.5">{t.member}</td>
              <td className="px-3 py-1.5 text-ink-2">{t.chamber}</td>
              <td className="px-3 py-1.5">{txTypeLabel[t.tx_type] ?? t.tx_type}</td>
              <td className="px-3 py-1.5 text-right tnum">{amount(t.amount_low, t.amount_high)}</td>
              <td className="px-3 py-1.5 text-right tnum text-ink-2">{t.transaction_date}</td>
              <td className="px-3 py-1.5 text-right tnum text-ink-2">{t.disclosure_date ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function InsiderTradesTable({ trades }: { trades: InsiderTrade[] }) {
  if (trades.length === 0) return <p className="text-sm text-muted">No Form 4 insider trades ingested for this ticker.</p>;
  return (
    <div className="overflow-x-auto rounded-md border border-hairline">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-hairline text-left text-xs text-muted">
            <th className="px-3 py-1.5 font-medium">Insider</th>
            <th className="px-3 py-1.5 font-medium">Role</th>
            <th className="px-3 py-1.5 font-medium">Transaction</th>
            <th className="px-3 py-1.5 text-right font-medium">Shares</th>
            <th className="px-3 py-1.5 text-right font-medium">Price</th>
            <th className="px-3 py-1.5 text-right font-medium">Value</th>
            <th className="px-3 py-1.5 text-right font-medium">Date</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={`${t.accession_no}-${i}`} className="border-b border-hairline last:border-b-0">
              <td className="px-3 py-1.5">{t.insider_name ?? "—"}</td>
              <td className="px-3 py-1.5 text-ink-2">
                {t.insider_title ?? (t.is_director ? "Director" : t.is_officer ? "Officer" : "—")}
              </td>
              <td className="px-3 py-1.5">{codeLabel[t.code] ?? `Code ${t.code}`}</td>
              <td className="px-3 py-1.5 text-right tnum">{t.shares?.toLocaleString() ?? "—"}</td>
              <td className="px-3 py-1.5 text-right tnum">{t.price != null ? `$${t.price.toFixed(2)}` : "—"}</td>
              <td className="px-3 py-1.5 text-right tnum">{t.value != null ? `$${Math.round(t.value).toLocaleString()}` : "—"}</td>
              <td className="px-3 py-1.5 text-right tnum text-ink-2">{t.transaction_date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

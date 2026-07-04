export default function DisclaimerBanner() {
  return (
    <div className="border-b border-hairline bg-surface">
      <p className="mx-auto max-w-6xl px-4 py-2 text-xs leading-relaxed text-ink-2">
        <span className="font-semibold text-ink">Personal research only — not financial advice.</span>{" "}
        InvTrack never issues buy/sell recommendations. Congressional trading disclosures are
        legally delayed by up to 45 days (STOCK Act), so those signals are always lagging. Verify
        anything important against the official sources (efdsearch.senate.gov,
        disclosures-clerk.house.gov, sec.gov) before acting on it.
      </p>
    </div>
  );
}

import type { Histogram } from "@/lib/aggregates.gen";
import { formatCount, formatStat } from "@/lib/format";

/**
 * SummaryStats → one quiet strip under a distribution. n_students always rides
 * along (a median without its n is not citable next to the Bergmann table).
 */
export function StatCallout({
  summary,
  nTotal,
  unit,
  floorN,
}: {
  summary: Histogram["summary"];
  nTotal: Histogram["n_total"];
  unit: string;
  floorN: number;
}) {
  const total =
    nTotal.status === "ok" ? `${formatCount(nTotal.value)} ${unit}` : `${unit} total suppressed`;
  if (!summary) {
    return <p className="mt-2 text-xs tabular-nums text-ink-2">{total}</p>;
  }
  if (summary.status === "suppressed") {
    return (
      <p className="mt-2 text-xs tabular-nums text-ink-2">
        {total} · summary suppressed (&lt; {floorN} students)
      </p>
    );
  }
  const parts = [
    `n = ${formatCount(summary.n_students)} students`,
    total,
    `median ${formatStat(summary.median)}`,
    `IQR ${formatStat(summary.p25)}–${formatStat(summary.p75)}`,
  ];
  if (summary.mean != null) {
    parts.push(
      `mean ${formatStat(summary.mean)}${summary.sd != null ? ` (SD ${formatStat(summary.sd)})` : ""}`,
    );
  }
  return <p className="mt-2 text-xs tabular-nums text-ink-2">{parts.join(" · ")}</p>;
}

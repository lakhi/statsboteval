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
  // A per-student distribution counts students in its bins, so n_total and n_students are
  // the same people counted twice ("n = 132 students · 132 students"). Drop the total there.
  const totalRepeatsN =
    unit === "students" && nTotal.status === "ok" && nTotal.value === summary.n_students;
  const before = [
    `n = ${formatCount(summary.n_students)} students`,
    ...(totalRepeatsN ? [] : [total]),
    `median ${formatStat(summary.median)}`,
  ];
  const after =
    summary.mean != null
      ? [`mean ${formatStat(summary.mean)}${summary.sd != null ? ` (SD ${formatStat(summary.sd)})` : ""}`]
      : [];
  return (
    <p className="mt-2 text-xs tabular-nums text-ink-2">
      {before.join(" · ")}
      {" · "}
      {/* "IQR" is methods vocabulary on a page written for educators reading as
          administrators. The plain reading leads; the term stays available on hover
          so a number here can still be matched to the thesis text. */}
      <span title="Interquartile range (IQR): the 25th to 75th percentile.">
        middle 50% {formatStat(summary.p25)}–{formatStat(summary.p75)}
      </span>
      {after.length > 0 ? ` · ${after.join(" · ")}` : null}
    </p>
  );
}

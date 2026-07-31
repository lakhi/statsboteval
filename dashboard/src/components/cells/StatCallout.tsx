import type { Histogram } from "@/lib/aggregates.gen";
import { formatCount, formatStat, unitLabel } from "@/lib/format";

/**
 * SummaryStats → one quiet strip under a distribution.
 *
 * 1.7.0 (D-55) fixes two things a PhD reader would have flagged:
 *
 * 1. **`n` is the number of observations behind the median**, not the floor's
 *    contributing-student count. Those coincide on a per-student distribution and do NOT
 *    on a per-session one: "Messages per conversation" summarises 414 conversations while
 *    132 students stand behind the floor, and printing `n = 132 students` first bound the
 *    reader's `n` to the wrong number. The student count still rides along in parentheses
 *    — it is the privacy basis, and a median without it is not citable next to the
 *    Bergmann table — but it no longer wears the name `n`.
 * 2. **The measured quantity is named.** `median 2` says nothing on its own; the card
 *    title was the only thing binding it to conversations, several lines away.
 */
export function StatCallout({
  summary,
  nTotal,
  unit,
  floorN,
  measure,
}: {
  summary: Histogram["summary"];
  nTotal: Histogram["n_total"];
  unit: string;
  floorN: number;
  /** Singular noun for the measured quantity, e.g. "conversation" — names the median. */
  measure?: string;
}) {
  // Contract vocabulary in, educator vocabulary out. The document's unit for a session
  // histogram is "sessions", but every visible label on the tab — card titles, measure
  // names, the chat-fragmentation footnote — says "conversation". The one strip built to
  // remove an ambiguity must not introduce a second one by leaking the internal word.
  const shown = unitLabel(unit);
  const total =
    nTotal.status === "ok" ? `${formatCount(nTotal.value)} ${shown}` : `${shown} total suppressed`;
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
  // On a per-student distribution the observations ARE the students, so naming the student
  // count twice ("n = 132 students, from 132 students") is noise; there, n stands alone.
  const perStudent = unit === "students";
  const n =
    nTotal.status === "ok"
      ? perStudent
        ? `n = ${formatCount(nTotal.value)} students`
        : `n = ${formatCount(nTotal.value)} ${shown} (${formatCount(summary.n_students)} students)`
      : `n = ${formatCount(summary.n_students)} students`;
  const median = measure
    ? `median ${formatStat(summary.median)} ${measure}${summary.median === 1 ? "" : "s"}`
    : `median ${formatStat(summary.median)}`;
  const after =
    summary.mean != null
      ? `mean ${formatStat(summary.mean)}${summary.sd != null ? ` (SD ${formatStat(summary.sd)})` : ""}`
      : null;
  return (
    <p className="mt-2 text-xs tabular-nums text-ink-2">
      {n}
      {" · "}
      {/* "IQR" is methods vocabulary on a page written for educators reading as
          administrators. The plain reading leads; the term stays available on hover
          so a number here can still be matched to the thesis text. The quantile
          definition is named too — it is why an integer-valued measure can report a
          median of 1.5. */}
      <span title="Quantiles are R type 2 (averaging at discontinuities), so a whole-number measure can report a half.">
        {median}
      </span>
      {" · "}
      <span title="Interquartile range (IQR): the 25th to 75th percentile.">
        middle 50% {formatStat(summary.p25)}–{formatStat(summary.p75)}
      </span>
      {after ? ` · ${after}` : null}
    </p>
  );
}

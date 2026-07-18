// Categorical distribution → horizontal bars, sorted by count. Pure CSS on
// purpose (D-27's reasoning): the suppressed-cell rendering is the hard part,
// and a bespoke row beats a chart-lib bar for it. The suppression grammar
// matches the rest of the dashboard — a suppressed category shows the gray
// baseline mark and "< N students", never a stub bar (which would read as
// "small", exactly the lie to avoid); an explicit zero shows "0" with no bar.

import type { TopicDistribution } from "@/lib/aggregates.gen";
import { formatCount } from "@/lib/format";

type Row = { label: string; value: number | null; suppressed: boolean };

/** ok(>0) by count desc, then suppressed (unknown but nonzero-ish), then explicit zeros. */
function sortedRows(distribution: TopicDistribution): Row[] {
  const rows: Row[] = distribution.items.map((item) => ({
    label: item.label,
    value: item.cell.status === "ok" ? item.cell.value : null,
    suppressed: item.cell.status === "suppressed",
  }));
  return rows.sort((a, b) => {
    const rank = (r: Row) => (r.value !== null && r.value > 0 ? 0 : r.suppressed ? 1 : 2);
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    if (a.value !== null && b.value !== null && a.value !== b.value) return b.value - a.value;
    return a.label.localeCompare(b.label);
  });
}

export function CategoryBars({
  distribution,
  floorN,
}: {
  distribution: TopicDistribution;
  floorN: number;
}) {
  const rows = sortedRows(distribution);
  const max = Math.max(1, ...rows.map((r) => r.value ?? 0));
  return (
    <ul className="space-y-1.5">
      {rows.map((row) => (
        <li key={row.label} className="grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-2 text-sm">
          <span className="truncate text-ink-2" title={row.label}>
            {row.label}
          </span>
          <span className="relative h-3 rounded-sm bg-paper" aria-hidden>
            {row.suppressed ? (
              <span className="absolute inset-y-1 left-0 w-2 rounded-sm bg-suppressed" />
            ) : row.value ? (
              <span
                className="absolute inset-y-0 left-0 rounded-sm bg-accent"
                style={{ width: `${Math.max(2, (row.value / max) * 100)}%` }}
              />
            ) : null}
          </span>
          <span className="min-w-[4.5rem] text-right tabular-nums">
            {row.suppressed ? (
              <span className="text-ink-3">&lt; {floorN} students</span>
            ) : (
              <span className={row.value ? "text-ink" : "text-ink-3"}>{formatCount(row.value ?? 0)}</span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function categoryTableRows(distribution: TopicDistribution): (string | number)[][] {
  return sortedRows(distribution).map((row) => [
    row.label,
    row.suppressed ? "suppressed" : formatCount(row.value ?? 0),
  ]);
}

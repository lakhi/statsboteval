// Categorical distribution → stacked label-over-bar rows, sorted by count.
// Pure CSS on purpose (D-27's reasoning): the suppressed-cell rendering is the
// hard part, and a bespoke row beats a chart-lib bar for it. The label gets its
// own full-width line so names are never truncated; the bar shows the share of
// the view's messages inside the fill (or beside it when the fill is too
// short). The suppression grammar matches the rest of the dashboard — a
// suppressed category shows the gray baseline mark and "< N students", never a
// stub bar (which would read as "small", exactly the lie to avoid); an explicit
// zero shows "0" with no bar. Only the top `maxRows` render; the data table
// keeps every row.

import type { ReactNode } from "react";
import type { TopicDistribution } from "@/lib/aggregates.gen";
import { formatCount } from "@/lib/format";
import { TopicRowTip } from "./TopicRowTip";

export type CategoryRow = {
  label: string;
  value: number | null;
  suppressed: boolean;
  description?: string;
};

/** ok(>0) by count desc, then suppressed (unknown but nonzero-ish), then explicit zeros. */
function sortedRows(distribution: TopicDistribution): CategoryRow[] {
  const rows: CategoryRow[] = distribution.items.map((item) => ({
    label: item.label,
    value: item.cell.status === "ok" ? item.cell.value : null,
    suppressed: item.cell.status === "suppressed",
    description: item.description ?? undefined,
  }));
  return rows.sort((a, b) => {
    const rank = (r: CategoryRow) => (r.value !== null && r.value > 0 ? 0 : r.suppressed ? 1 : 2);
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    if (a.value !== null && b.value !== null && a.value !== b.value) return b.value - a.value;
    return a.label.localeCompare(b.label);
  });
}

/** Share of the view's messages; null when the total is suppressed or zero. */
function share(row: CategoryRow, distribution: TopicDistribution): string | null {
  if (row.value === null || distribution.n_total.status !== "ok" || distribution.n_total.value === 0) {
    return null;
  }
  const pct = (row.value / distribution.n_total.value) * 100;
  if (pct === 0) return null;
  return pct < 1 ? "<1%" : `${Math.round(pct)}%`;
}

export function CategoryBars({
  distribution,
  floorN,
  maxRows = 7,
  rowTip,
}: {
  distribution: TopicDistribution;
  floorN: number;
  maxRows?: number;
  /** Hover/focus explanation of how a row's number was arrived at. */
  rowTip?: (row: CategoryRow) => ReactNode;
}) {
  const rows = sortedRows(distribution);
  const shown = rows.slice(0, maxRows);
  const hidden = rows.length - shown.length;
  const max = Math.max(1, ...rows.map((r) => r.value ?? 0));
  return (
    <ul className="space-y-2">
      {shown.map((row) => {
        const fillPct = row.value ? Math.max(2, (row.value / max) * 100) : 0;
        const pct = share(row, distribution);
        const content = (
          <>
            <span className="block text-sm leading-snug text-ink-2">{row.label}</span>
            <span className="mt-0.5 flex items-center gap-2">
              <span className="relative h-3.5 min-w-0 flex-1 rounded-sm bg-paper" aria-hidden>
                {row.suppressed ? (
                  <span className="absolute inset-y-1 left-0 w-2 rounded-sm bg-suppressed" />
                ) : row.value ? (
                  <>
                    <span
                      className="absolute inset-y-0 left-0 rounded-sm bg-accent"
                      style={{ width: `${fillPct}%` }}
                    />
                    {pct ? (
                      fillPct >= 18 ? (
                        <span
                          className="absolute inset-y-0 left-0 flex items-center justify-end pr-1.5 text-[10px] font-medium text-white"
                          style={{ width: `${fillPct}%` }}
                        >
                          {pct}
                        </span>
                      ) : (
                        <span
                          className="absolute inset-y-0 flex items-center text-[10px] font-medium text-ink-3"
                          style={{ left: `calc(${fillPct}% + 6px)` }}
                        >
                          {pct}
                        </span>
                      )
                    ) : null}
                  </>
                ) : null}
              </span>
              <span className="min-w-[4.5rem] text-right text-sm tabular-nums">
                {row.suppressed ? (
                  <span className="text-ink-3">&lt; {floorN} students</span>
                ) : (
                  <span className={row.value ? "text-ink" : "text-ink-3"}>{formatCount(row.value ?? 0)}</span>
                )}
              </span>
            </span>
          </>
        );
        return (
          <li key={row.label}>
            {rowTip ? <TopicRowTip tip={rowTip(row)}>{content}</TopicRowTip> : content}
          </li>
        );
      })}
      {hidden > 0 ? (
        <li className="pt-0.5 text-xs text-ink-3">
          + {hidden} more — every entry is in the data table below.
        </li>
      ) : null}
    </ul>
  );
}

export function categoryTableRows(distribution: TopicDistribution): (string | number)[][] {
  return sortedRows(distribution).map((row) => [
    row.label,
    row.suppressed ? "suppressed" : formatCount(row.value ?? 0),
    row.suppressed ? "—" : (share(row, distribution) ?? "—"),
  ]);
}

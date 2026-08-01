import type { ReactNode } from "react";
import type { OkCell, SuppressedCell } from "@/lib/aggregates.gen";
import { formatCount } from "@/lib/format";

/** A cell that may also be missing: absent from an older file, or null in a newer one
 *  that declares the field but has nothing to publish. Both render as "not published". */
type CountCell = OkCell | SuppressedCell | null;

/**
 * CountCell → stat tile. The three honest states, visually distinct:
 * a number (ok), an em-dash + "suppressed" caption (1..N−1 students),
 * and "not published" (absent cell).
 */
export function KpiTile({
  label,
  cell,
  floorN,
  note,
  tip,
}: {
  label: string;
  cell: CountCell | undefined;
  floorN: number;
  /** Definition the number would otherwise be ambiguous without, e.g. what a message is.
   *  A node rather than a string since D-58: the caveat belongs in the cell, and a caveat
   *  can carry a link or an InfoTip. */
  note?: ReactNode;
  /** Caveat marker beside the label, for what qualifies the number rather than defines it. */
  tip?: ReactNode;
}) {
  return (
    // `relative` is load-bearing, not styling: an InfoTip inside this tile anchors its
    // popover to the tile so it can never run off the side of a narrow viewport.
    <div className="relative rounded-lg border border-edge bg-card px-4 py-3">
      <div className="text-xs text-ink-2">
        {label}
        {tip}
      </div>
      {cell == null ? (
        <>
          <div className="mt-0.5 text-2xl font-semibold text-ink-3">·</div>
          <div className="text-[11px] text-ink-3">not published</div>
        </>
      ) : cell.status === "suppressed" ? (
        <>
          <div className="mt-0.5 text-2xl font-semibold text-suppressed">—</div>
          <div className="text-[11px] text-ink-3">suppressed (&lt; {floorN} students)</div>
        </>
      ) : (
        <div className="mt-0.5 text-3xl font-semibold text-ink">{formatCount(cell.value)}</div>
      )}
      {note ? <div className="mt-1 text-[11px] leading-snug text-ink-3">{note}</div> : null}
    </div>
  );
}

/**
 * Two counts that only mean something as a pair — new vs returning, signed up vs
 * actually used. Deliberately not one number plus a delta: the pair is published as
 * two floored cells, and a difference computed here could leak a sub-floor count.
 */
export function KpiPairTile({
  label,
  rows,
  floorN,
  note,
  tip,
}: {
  label: string;
  rows: { caption: string; cell: CountCell | undefined }[];
  floorN: number;
  /** What the pair means, rendered inside the tile (D-58). */
  note?: ReactNode;
  /** Caveat marker beside the label. */
  tip?: ReactNode;
}) {
  return (
    // `relative` is load-bearing, not styling: an InfoTip inside this tile anchors its
    // popover to the tile so it can never run off the side of a narrow viewport.
    <div className="relative rounded-lg border border-edge bg-card px-4 py-3">
      <div className="text-xs text-ink-2">
        {label}
        {tip}
      </div>
      <div className="mt-1 space-y-0.5">
        {rows.map((row) => (
          <div key={row.caption} className="flex items-baseline gap-2">
            {row.cell == null ? (
              <span className="text-xl font-semibold text-ink-3">·</span>
            ) : row.cell.status === "suppressed" ? (
              <span
                className="text-xl font-semibold text-suppressed"
                title={`suppressed (< ${floorN} students)`}
              >
                —
              </span>
            ) : (
              <span className="text-xl font-semibold tabular-nums text-ink">
                {formatCount(row.cell.value)}
              </span>
            )}
            <span className="text-[11px] leading-snug text-ink-2">{row.caption}</span>
          </div>
        ))}
      </div>
      {note ? <div className="mt-1.5 text-[11px] leading-snug text-ink-3">{note}</div> : null}
    </div>
  );
}

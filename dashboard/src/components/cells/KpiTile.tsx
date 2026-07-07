import type { OkCell, SuppressedCell } from "@/lib/aggregates.gen";
import { formatCount } from "@/lib/format";

type CountCell = OkCell | SuppressedCell;

/**
 * CountCell → stat tile. The three honest states, visually distinct:
 * a number (ok), an em-dash + "suppressed" caption (1..N−1 students),
 * and "not published" (absent cell).
 */
export function KpiTile({
  label,
  cell,
  floorN,
}: {
  label: string;
  cell: CountCell | undefined;
  floorN: number;
}) {
  return (
    <div className="rounded-lg border border-edge bg-card px-4 py-3">
      <div className="text-xs text-ink-2">{label}</div>
      {cell === undefined ? (
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
    </div>
  );
}

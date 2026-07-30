// DaypartTotals → horizontal bars, one per six-hour block (D-54).
//
// Horizontal because the labels ("Afternoon 12–18") are long and a vertical axis
// would either truncate or rotate them. One measure, so one hue — the accent —
// never a per-bar color: the blocks are an ordered sequence, not four identities.
// Equal-width blocks are what makes bar length directly comparable; the
// daypart_definition footnote says so on the card.

import type { Daypart, DaypartTotals } from "@/lib/aggregates.gen";
import { formatCount } from "@/lib/format";

type Cell = DaypartTotals["by_daypart"][string];

const hours = (part: Daypart): string =>
  `${String(part.from_hour).padStart(2, "0")}–${String(part.to_hour).padStart(2, "0")}`;

function Bar({ cell, max, floorN, label }: { cell: Cell; max: number; floorN: number; label: string }) {
  if (cell.status === "suppressed") {
    return (
      <div className="flex items-center gap-2">
        <div
          className="suppressed-stipple h-4 w-8 rounded-[3px]"
          title={`${label}: suppressed (< ${floorN} students)`}
        />
        <span className="text-[11px] text-suppressed">withheld</span>
      </div>
    );
  }
  // A measured zero still gets a tick of ink: an empty row reads as "no data",
  // and ok(0) means the opposite — we looked, and nobody wrote.
  const pct = cell.value === 0 ? 0 : Math.max(1.5, (cell.value / max) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-4 min-w-[2px] flex-1 rounded-[3px] bg-paper">
        <div
          className="h-4 rounded-[3px] bg-accent"
          style={{ width: `${pct}%` }}
          title={`${label}: ${formatCount(cell.value)} messages`}
        />
      </div>
      <span className="w-12 shrink-0 text-right text-xs tabular-nums text-ink">
        {formatCount(cell.value)}
      </span>
    </div>
  );
}

export function DaypartBars({
  totals,
  dayparts,
  floorN,
}: {
  totals: DaypartTotals;
  dayparts: Daypart[];
  floorN: number;
}) {
  const cells = dayparts.map((p) => totals.by_daypart[p.id]).filter(Boolean);
  const max = Math.max(1, ...cells.map((c) => (c.status === "ok" ? c.value : 0)));
  const span = (cell: Cell) =>
    cell.status === "ok" ? formatCount(cell.value) : <span className="text-suppressed">—</span>;
  return (
    <div>
      <div
        className="space-y-2"
        role="img"
        aria-label={`Messages by six-hour block of the day; striped bars are suppressed under the privacy floor (fewer than ${floorN} students).`}
      >
        {dayparts.map((part) => {
          const cell = totals.by_daypart[part.id];
          if (!cell) return null;
          const label = `${part.label} ${hours(part)}`;
          return (
            <div key={part.id} className="grid grid-cols-[7.5rem_1fr] items-center gap-2">
              <div className="text-xs text-ink-2">
                {part.label} <span className="text-ink-3 tabular-nums">{hours(part)}</span>
              </div>
              <Bar cell={cell} max={max} floorN={floorN} label={label} />
            </div>
          );
        })}
      </div>
      {/* Weekend/weekday: published as two independently floored cells, never as one
          number and a remainder — subtracting across them would recover a withheld side. */}
      <div className="mt-3 flex gap-6 border-t border-hairline pt-2 text-xs text-ink-2">
        <span>
          Mon–Fri <span className="font-semibold tabular-nums text-ink">{span(totals.weekday)}</span>
        </span>
        <span>
          Sat–Sun <span className="font-semibold tabular-nums text-ink">{span(totals.weekend)}</span>
        </span>
      </div>
    </div>
  );
}

export function daypartTableRows(totals: DaypartTotals, dayparts: Daypart[]): (string | number)[][] {
  const value = (cell: Cell | undefined) =>
    cell == null ? "" : cell.status === "ok" ? cell.value : "suppressed";
  return [
    ...dayparts.map((p) => [`${p.label} (${hours(p)})`, value(totals.by_daypart[p.id])]),
    ["Mon–Fri", value(totals.weekday)],
    ["Sat–Sun", value(totals.weekend)],
  ];
}

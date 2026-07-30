// DaypartGrid → weekday × daypart activity grid, plain CSS grid (no chart lib
// needed for 28 fixed cells). Sequential single-hue ramp (Vienna blue,
// light→dark); zero is a measured near-surface tint; suppressed is the 45° gray
// stipple — texture, not color, so the privacy state survives grayscale and CVD.
//
// This was a 7 × 24 grid until D-54. 168 cells was too fine for this corpus and
// the floor ate it: 29 of 139 non-empty cells suppressed all-time, 52 of 84 in
// 2025W. At 7 × 4 that is 2 of 28 and 3 of 21 — and the weekday × daypart
// interaction the grid exists to show survives intact (chi-square 160 on 18 df
// over the published axis; Saturday night runs 3.8× the margins' prediction).
// The full-resolution grid is still published as `activity_heatmap`; nothing
// renders it.

import type { Daypart, DaypartGrid } from "@/lib/aggregates.gen";
import { formatCount } from "@/lib/format";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const RAMP = ["#dbe9f4", "#b9d5ea", "#8ebcdc", "#5c9cc7", "#2d78ad", "#0f5a8f"];
const ZERO = "#f1f4f6";

const hours = (part: Daypart): string =>
  `${String(part.from_hour).padStart(2, "0")}–${String(part.to_hour).padStart(2, "0")}`;

export function ActivityHeatmap({
  grid,
  dayparts,
  floorN,
}: {
  grid: DaypartGrid;
  dayparts: Daypart[];
  floorN: number;
}) {
  const byKey = new Map(grid.cells.map((c) => [`${c.dow}-${c.daypart}`, c.cell]));
  const max = Math.max(1, ...grid.cells.map((c) => (c.cell.status === "ok" ? c.cell.value : 0)));
  return (
    <div>
      <div
        className="grid gap-[3px]"
        style={{ gridTemplateColumns: `2.6rem repeat(${dayparts.length}, minmax(0, 1fr))` }}
        role="img"
        aria-label={`Activity by weekday and six-hour block; darker means more messages; striped cells are suppressed under the privacy floor (fewer than ${floorN} students).`}
      >
        <div />
        {dayparts.map((part) => (
          <div key={part.id} className="pb-1 text-center text-[11px] leading-tight text-ink-2">
            {part.label}
            <div className="text-[9px] tabular-nums text-ink-3">{hours(part)}</div>
          </div>
        ))}
        {DOW.map((day, d) => (
          <div key={day} className="contents">
            <div className="self-center pr-1 text-right text-[10px] leading-4 text-ink-3">{day}</div>
            {dayparts.map((part) => {
              const cell = byKey.get(`${d + 1}-${part.id}`);
              const title = `${day} ${part.label} ${hours(part)} — `;
              if (!cell) return <div key={part.id} className="h-7 rounded-[3px] bg-paper" />;
              if (cell.status === "suppressed") {
                return (
                  <div
                    key={part.id}
                    className="suppressed-stipple h-7 rounded-[3px]"
                    title={`${title}suppressed (< ${floorN} students)`}
                  />
                );
              }
              const step =
                cell.value === 0
                  ? -1
                  : Math.min(RAMP.length - 1, Math.floor((cell.value / max) * RAMP.length));
              return (
                <div
                  key={part.id}
                  className="h-7 rounded-[3px]"
                  style={{ background: step < 0 ? ZERO : RAMP[step] }}
                  title={`${title}${formatCount(cell.value)} messages`}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-2">
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-3 rounded-[2px]" style={{ background: ZERO }} /> 0
        </span>
        <span className="inline-flex items-center gap-1">
          low
          {RAMP.map((c) => (
            <span key={c} className="h-3 w-3 rounded-[2px]" style={{ background: c }} />
          ))}
          high
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="suppressed-stipple h-3 w-3 rounded-[2px]" /> suppressed
        </span>
      </div>
    </div>
  );
}

export function heatmapTableRows(grid: DaypartGrid, dayparts: Daypart[]): (string | number)[][] {
  const byKey = new Map(grid.cells.map((c) => [`${c.dow}-${c.daypart}`, c.cell]));
  return DOW.map((day, d) => [
    day,
    ...dayparts.map((part) => {
      const cell = byKey.get(`${d + 1}-${part.id}`);
      if (!cell) return "";
      return cell.status === "ok" ? cell.value : "suppr.";
    }),
  ]);
}

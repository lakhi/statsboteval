// HeatmapGrid → day × hour activity grid, plain CSS grid (no chart lib needed
// for 168 fixed cells). Sequential single-hue ramp (Vienna blue, light→dark);
// zero is a measured near-surface tint; suppressed is the 45° gray stipple —
// texture, not color, so the privacy state survives grayscale and CVD.

import type { HeatmapGrid } from "@/lib/aggregates.gen";
import { formatCount } from "@/lib/format";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const RAMP = ["#dbe9f4", "#b9d5ea", "#8ebcdc", "#5c9cc7", "#2d78ad", "#0f5a8f"];
const ZERO = "#f1f4f6";

export function ActivityHeatmap({ grid, floorN }: { grid: HeatmapGrid; floorN: number }) {
  const byKey = new Map(grid.cells.map((c) => [`${c.dow}-${c.hour}`, c.cell]));
  const max = Math.max(
    1,
    ...grid.cells.map((c) => (c.cell.status === "ok" ? c.cell.value : 0)),
  );
  return (
    <div>
      <div
        className="grid gap-[2px]"
        style={{ gridTemplateColumns: "2.2rem repeat(24, minmax(0, 1fr))" }}
        role="img"
        aria-label={`Activity by weekday and hour; darker means more messages; striped cells are suppressed under the privacy floor (fewer than ${floorN} students).`}
      >
        {DOW.map((day, d) => (
          <div key={day} className="contents">
            <div className="pr-1 text-right text-[10px] leading-4 text-ink-3">{day}</div>
            {Array.from({ length: 24 }, (_, hour) => {
              const cell = byKey.get(`${d + 1}-${hour}`);
              const title = `${day} ${String(hour).padStart(2, "0")}:00 — `;
              if (!cell) return <div key={hour} className="h-4 rounded-[2px] bg-paper" />;
              if (cell.status === "suppressed") {
                return (
                  <div
                    key={hour}
                    className="suppressed-stipple h-4 rounded-[2px]"
                    title={`${title}suppressed (< ${floorN} students)`}
                  />
                );
              }
              const step = cell.value === 0 ? -1 : Math.min(
                RAMP.length - 1,
                Math.floor((cell.value / max) * RAMP.length),
              );
              return (
                <div
                  key={hour}
                  className="h-4 rounded-[2px]"
                  style={{ background: step < 0 ? ZERO : RAMP[step] }}
                  title={`${title}${formatCount(cell.value)} messages`}
                />
              );
            })}
          </div>
        ))}
        <div />
        {Array.from({ length: 24 }, (_, hour) => (
          <div key={hour} className="pt-0.5 text-center text-[9px] text-ink-3">
            {hour % 3 === 0 ? hour : ""}
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

export function heatmapTableRows(grid: HeatmapGrid): (string | number)[][] {
  const byKey = new Map(grid.cells.map((c) => [`${c.dow}-${c.hour}`, c.cell]));
  return DOW.map((day, d) => [
    day,
    ...Array.from({ length: 24 }, (_, hour) => {
      const cell = byKey.get(`${d + 1}-${hour}`);
      if (!cell) return "";
      return cell.status === "ok" ? cell.value : "suppr.";
    }),
  ]);
}

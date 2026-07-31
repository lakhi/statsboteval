"use client";

// WeeklySeries → trend line(s). Contract invariant 2 is the whole job:
// ok renders as a point, ok:0 as a true zero, suppressed as a gap — plus, in
// single-series mode, a gray baseline mark so the gap is visibly "withheld"
// rather than missing. Series are pre-sliced to the selected window upstream.

import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { WeeklyEntry } from "@/lib/aggregates.gen";
import {
  formatCount,
  SHORT_AXIS_POINTS,
  weekMonthAnchor,
  weekRangeLabel,
  weekStartLabel,
} from "@/lib/format";

export type TrendSeries = {
  id: string;
  label: string;
  color: string;
  entries: WeeklyEntry[];
};

type Row = { week: string; [key: string]: string | number | null | boolean };

function buildRows(series: TrendSeries[]): Row[] {
  const rows = new Map<string, Row>();
  for (const s of series) {
    for (const { week, cell } of s.entries) {
      const row = rows.get(week) ?? { week };
      row[s.id] = cell.status === "ok" ? cell.value : null;
      row[`${s.id}__suppressed`] = cell.status === "suppressed";
      rows.set(week, row);
    }
  }
  return [...rows.values()];
}

function TrendTooltip({
  active,
  label,
  payload,
  series,
  floorN,
}: {
  active?: boolean;
  label?: string;
  payload?: ReadonlyArray<{ payload: Row }>;
  series: TrendSeries[];
  floorN: number;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded border border-edge bg-card px-2.5 py-1.5 text-xs shadow-sm">
      {/* The axis is deliberately approximate now, so the tooltip is exact. */}
      <div className="font-medium text-ink">{label ? weekRangeLabel(label) : ""}</div>
      {series.map((s) => (
        <div key={s.id} className="mt-0.5 flex items-center gap-1.5 tabular-nums text-ink-2">
          {series.length > 1 ? (
            <span className="h-2 w-2 rounded-full" style={{ background: s.color }} aria-hidden />
          ) : null}
          {series.length > 1 ? <span>{s.label}:</span> : null}
          {row[`${s.id}__suppressed`] ? (
            <span className="text-ink-3">suppressed (&lt; {floorN} students)</span>
          ) : (
            <span className="text-ink">{formatCount((row[s.id] as number) ?? 0)}</span>
          )}
        </div>
      ))}
    </div>
  );
}

export function TrendChart({
  series,
  floorN,
  height = 200,
}: {
  series: TrendSeries[];
  floorN: number;
  height?: number;
}) {
  const rows = buildRows(series);
  const single = series.length === 1;
  if (single) {
    for (const row of rows) {
      row.__mark = row[`${series[0].id}__suppressed`] ? 0 : null;
    }
  }
  // A line needs two points to be visible, so a one-week window (D-56) draws nothing at
  // all unless the vertices are marked. On a single-series chart dots are already on for
  // the suppression marks; this is what covers the multi-series charts, where they are
  // off by choice and a lone week would otherwise render as an empty panel.
  const dotted = single || rows.length === 1;
  // Month anchors on a long axis, Monday dates on a short one: a 4-week window can
  // contain no month boundary at all, and an axis with no labels is worse than one
  // with four. Anchors need the previous week, so this is indexed, not per-value.
  const weeks = rows.map((r) => r.week as string);
  const shortAxis = weeks.length < SHORT_AXIS_POINTS;
  const tickFor = new Map(
    weeks.map((week, i) => [week, shortAxis ? weekStartLabel(week) : weekMonthAnchor(week, weeks[i - 1])]),
  );
  return (
    <div>
      {!single && (
        <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
          {series.map((s) => (
            <span key={s.id} className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: s.color }} aria-hidden />
              {s.label}
            </span>
          ))}
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
          <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
          <XAxis
            dataKey="week"
            tick={{ fontSize: 11, fill: "var(--color-ink-3)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--color-baseline)" }}
            tickFormatter={(week: string) => tickFor.get(week) ?? ""}
            // 0: the formatter already decides which weeks carry a label, and letting
            // recharts thin them again would drop month anchors at random.
            minTickGap={0}
            interval={0}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: "var(--color-ink-3)" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<TrendTooltip series={series} floorN={floorN} />} />
          {series.map((s) => (
            <Line
              key={s.id}
              dataKey={s.id}
              stroke={s.color}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              connectNulls={false}
              dot={
                dotted
                  ? { r: 4, fill: s.color, stroke: "var(--color-card)", strokeWidth: 2 }
                  : false
              }
              activeDot={{ r: 5, stroke: "var(--color-card)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
          {single && (
            <Scatter dataKey="__mark" fill="var(--color-suppressed)" isAnimationActive={false} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Table twin rows for one or more weekly series ("suppressed" spelled out).
 *  Keeps the machine-readable week id and adds the dates the axis no longer shows —
 *  the table is the precision twin of the figure. */
export function trendTableRows(series: TrendSeries[]): (string | number)[][] {
  const rows = buildRows(series);
  return rows.map((row) => [
    `${row.week as string} (${weekRangeLabel(row.week as string).split(" · ")[1]})`,
    ...series.map((s) =>
      row[`${s.id}__suppressed`] ? "suppressed" : formatCount((row[s.id] as number) ?? 0),
    ),
  ]);
}

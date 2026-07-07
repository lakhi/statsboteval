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
import { formatCount, weekShort } from "@/lib/format";

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
      <div className="font-medium text-ink">{label}</div>
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
            tickFormatter={weekShort}
            minTickGap={28}
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
                single
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

/** Table twin rows for one or more weekly series ("suppressed" spelled out). */
export function trendTableRows(series: TrendSeries[]): (string | number)[][] {
  const rows = buildRows(series);
  return rows.map((row) => [
    row.week as string,
    ...series.map((s) =>
      row[`${s.id}__suppressed`] ? "suppressed" : formatCount((row[s.id] as number) ?? 0),
    ),
  ]);
}

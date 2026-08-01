"use client";

// WeeklySeries → trend line(s). Contract invariant 2 is the whole job: ok renders as a
// point, ok:0 as a true zero, suppressed as neither.
//
// Until D-60 a suppressed week was drawn as a hole in the line. It read as damage rather
// than as a statement, and on a corpus this size a semester could break into four stubs.
// A suppressed week is now **bridged by a dashed segment**: the eye follows one line, and
// the dashes say the span between those two points was not measured. Nothing new is
// disclosed by this — the bridge is a straight interpolation between two cells that were
// already published, so it carries no information about the withheld week. What it buys
// is a legible curve; what it costs is the risk a reader takes the bridge for data, which
// is exactly what the dash pattern is there to deny.
//
// The mechanism is two <Line>s on one dataKey: a dashed one with connectNulls (the whole
// path, bridges included) under a solid one with connectNulls={false}. The solid line
// covers the real segments exactly, so dashes surface only across a gap. Per-segment
// stroke styling has no API in recharts; this is the way to get it.
//
// Single-series charts additionally keep the gray baseline mark under each suppressed
// week (D-60 keeps it, owner's call): the dashed bridge says "not measured here", the
// mark says which week, and neither reads as zero. Multi-series charts have no marks —
// with four languages a lone baseline dot could not say *which* series was withheld,
// which is precisely the ambiguity the dashed bridge resolves by sitting on the line
// that owns it. Series are pre-sliced to the selected window upstream.

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

/** Is there a hole with published weeks on both sides? Leading and trailing suppression
 *  has nothing to bridge *to*, so a series that only opens or closes short gets no dashed
 *  twin — one line is cheaper than two, and two coincident strokes fringe on subpixel
 *  boundaries wherever they are not needed. Shared with SemesterOverlay: one rule, so the
 *  two line charts cannot drift into disagreeing about what counts as a gap. */
export function needsBridge(rows: ReadonlyArray<Record<string, unknown>>, id: string): boolean {
  let seen = false;
  let gapAfterValue = false;
  for (const row of rows) {
    if (row[id] == null) {
      if (seen) gapAfterValue = true;
    } else {
      if (gapAfterValue) return true;
      seen = true;
    }
  }
  return false;
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
          {/* The bridges, under every solid line so a neighbouring series' real data always
              wins the overlap. No dots, no activeDot, no tooltip entry: this stroke is not
              a datum, it is the absence of one, drawn so the curve stays readable. */}
          {series.map((s) =>
            needsBridge(rows, s.id) ? (
              <Line
                key={`${s.id}__bridge`}
                dataKey={s.id}
                stroke={s.color}
                strokeWidth={2}
                strokeDasharray="3 4"
                strokeLinecap="round"
                connectNulls
                dot={false}
                activeDot={false}
                legendType="none"
                isAnimationActive={false}
              />
            ) : null,
          )}
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

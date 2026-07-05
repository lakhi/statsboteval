"use client";

// Provisional thin-slice chart (D-28): its one contract-bound job is rendering the
// three cell states distinctly — ok as a point, zero as a true 0 point, suppressed
// as a gap with a gray baseline marker, never as 0 (contract invariant 2).

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

type Point = {
  week: string;
  value: number | null;
  suppressedMark: number | null;
  suppressed: boolean;
};

function toPoints(entries: WeeklyEntry[]): Point[] {
  return entries.map(({ week, cell }) =>
    cell.status === "ok"
      ? { week, value: cell.value, suppressedMark: null, suppressed: false }
      : { week, value: null, suppressedMark: 0, suppressed: true },
  );
}

function TrendTooltip({
  active,
  payload,
  floorN,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload: Point }>;
  floorN: number;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs shadow-sm">
      <div className="font-medium">{point.week}</div>
      {point.suppressed ? (
        <div className="text-zinc-500">suppressed (&lt; {floorN} students)</div>
      ) : (
        <div>{point.value}</div>
      )}
    </div>
  );
}

export function WeeklyTrend({
  title,
  entries,
  floorN,
  footnotes = [],
}: {
  title: string;
  entries: WeeklyEntry[];
  floorN: number;
  footnotes?: string[];
}) {
  const points = toPoints(entries);
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <h2 className="mb-2 text-sm font-semibold text-zinc-700">{title}</h2>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
          <XAxis dataKey="week" tick={{ fontSize: 11 }} tickFormatter={(week: string) => week.slice(5)} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip content={<TrendTooltip floorN={floorN} />} />
          <Line
            dataKey="value"
            stroke="#2563eb"
            strokeWidth={2}
            connectNulls={false}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
          <Scatter dataKey="suppressedMark" fill="#9ca3af" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-zinc-500">
        Gray markers on the baseline: weeks suppressed under the privacy floor (&lt; {floorN} students) —
        not zeros.
      </p>
      {footnotes.map((text) => (
        <p key={text} className="mt-1 text-xs italic text-zinc-500">
          {text}
        </p>
      ))}
    </section>
  );
}

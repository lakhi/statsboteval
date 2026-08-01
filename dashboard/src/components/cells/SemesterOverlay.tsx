"use client";

// SemesterProfile[] → one line per semester on a shared teaching-week axis (D-54).
//
// The chart the window picker cannot serve: its whole job is comparing windows, so
// TimingTab renders it under all_time only. Week 1 is each semester's first ISO week
// (Thursday rule), which is what makes the curves comparable at all — the pipeline
// indexes on the semester's full membership, not on the weeks that happen to hold data,
// so a semester whose opening weeks are off-axis still starts where it really started.
//
// Categorical hues in the fixed dashboard order (accent, green, amber) — the same three
// the Language tab uses, assigned by chronological position so a new semester appends a
// color rather than repainting the others. Validated for CVD separation against the card
// surface; the contrast WARN on the two lighter hues is met by the legend and data table.
//
// Suppressed weeks are bridged by a dashed segment rather than left as holes (D-60) — see
// TrendChart's header for why, and for the two-<Line> mechanism. It matters more here than
// anywhere: the whole card is a comparison of curve *shapes*, and a semester broken into
// fragments cannot be compared to one that is not.

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SemesterProfile } from "@/lib/aggregates.gen";
import { formatCount } from "@/lib/format";
import { needsBridge } from "./TrendChart";

const SERIES_COLORS = ["var(--color-accent)", "var(--color-series-en)", "var(--color-series-other)"];

type Row = { week: number; [key: string]: number | null };

function buildRows(profiles: SemesterProfile[]): Row[] {
  const rows = new Map<number, Row>();
  for (const profile of profiles) {
    for (const point of profile.points) {
      const row = rows.get(point.semester_week) ?? { week: point.semester_week };
      row[profile.window_id] = point.messages.status === "ok" ? point.messages.value : null;
      rows.set(point.semester_week, row);
    }
  }
  return [...rows.values()].sort((a, b) => a.week - b.week);
}

function OverlayTooltip({
  active,
  label,
  payload,
  profiles,
}: {
  active?: boolean;
  label?: number;
  payload?: ReadonlyArray<{ payload: Row }>;
  profiles: SemesterProfile[];
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded border border-edge bg-card px-2.5 py-1.5 text-xs shadow-sm">
      <div className="font-medium text-ink">Teaching week {label}</div>
      {profiles.map((profile, i) => {
        const point = profile.points.find((p) => p.semester_week === label);
        if (!point) return null;
        return (
          <div key={profile.window_id} className="mt-0.5 flex items-center gap-1.5 tabular-nums text-ink-2">
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }}
              aria-hidden
            />
            <span>{point.week}:</span>
            {row[profile.window_id] == null ? (
              <span className="text-ink-3">suppressed</span>
            ) : (
              <span className="text-ink">{formatCount(row[profile.window_id] as number)}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function SemesterOverlay({
  profiles,
  height = 210,
}: {
  profiles: SemesterProfile[];
  height?: number;
}) {
  const rows = buildRows(profiles);
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
        {profiles.map((profile, i) => (
          <span key={profile.window_id} className="inline-flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }}
              aria-hidden
            />
            {profile.label}
          </span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 16, left: -14 }}>
          <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
          <XAxis
            dataKey="week"
            tick={{ fontSize: 11, fill: "var(--color-ink-3)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--color-baseline)" }}
            label={{
              value: "Week of semester",
              position: "insideBottom",
              offset: -8,
              style: { fontSize: 11, fill: "var(--color-ink-3)" },
            }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: "var(--color-ink-3)" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<OverlayTooltip profiles={profiles} />} />
          {profiles.map((profile, i) =>
            needsBridge(rows, profile.window_id) ? (
              <Line
                key={`${profile.window_id}__bridge`}
                dataKey={profile.window_id}
                stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
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
          {profiles.map((profile, i) => (
            <Line
              key={profile.window_id}
              dataKey={profile.window_id}
              stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              connectNulls={false}
              dot={false}
              activeDot={{ r: 5, stroke: "var(--color-card)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function semesterTableRows(profiles: SemesterProfile[]): (string | number)[][] {
  return buildRows(profiles).map((row) => [
    row.week,
    ...profiles.map((p) => {
      const point = p.points.find((pt) => pt.semester_week === row.week);
      if (!point) return "";
      return point.messages.status === "ok" ? point.messages.value : "suppressed";
    }),
  ]);
}

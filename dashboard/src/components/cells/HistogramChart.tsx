"use client";

// Histogram → distribution bars. A suppressed bin has no value, so it gets no
// bar at all — the same gray baseline mark as the trend charts stands in for
// it (a stub bar would be read as "small", which is exactly the lie to avoid).

import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Histogram } from "@/lib/aggregates.gen";
import { binLabel, formatCount } from "@/lib/format";
import { StatCallout } from "./StatCallout";

type Row = { label: string; value: number | null; __mark: number | null; suppressed: boolean };

function HistTooltip({
  active,
  payload,
  unit,
  floorN,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload: Row }>;
  unit: string;
  floorN: number;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded border border-edge bg-card px-2.5 py-1.5 text-xs shadow-sm">
      <div className="font-medium text-ink">{row.label}</div>
      {row.suppressed ? (
        <div className="text-ink-3">suppressed (&lt; {floorN} students)</div>
      ) : (
        <div className="tabular-nums text-ink-2">
          {formatCount(row.value ?? 0)} {unit}
        </div>
      )}
    </div>
  );
}

/** A lighter tint of the accent, never gray: gray is reserved for suppression. */
const MUTED_BAR = "color-mix(in srgb, var(--color-accent) 38%, var(--color-card))";

export function HistogramChart({
  histogram,
  floorN,
  height = 190,
  mutedBins,
  measure,
}: {
  histogram: Histogram;
  floorN: number;
  height?: number;
  /** Bin indices drawn in the lighter tint — used to separate a qualitatively
   *  different first bin ("tried it once") from the rest without inventing a
   *  second data series. */
  mutedBins?: readonly number[];
  /** Singular noun the summary strip uses to name its median (D-55). */
  measure?: string;
}) {
  const rows: Row[] = histogram.bins.map((bin) => ({
    label: binLabel(bin),
    value: bin.cell.status === "ok" ? bin.cell.value : null,
    __mark: bin.cell.status === "suppressed" ? 0 : null,
    suppressed: bin.cell.status === "suppressed",
  }));
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
          <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "var(--color-ink-3)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--color-baseline)" }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: "var(--color-ink-3)" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ fill: "color-mix(in srgb, var(--color-accent) 6%, transparent)" }}
            content={<HistTooltip unit={histogram.unit} floorN={floorN} />}
          />
          <Bar
            dataKey="value"
            fill="var(--color-accent)"
            maxBarSize={24}
            radius={[4, 4, 0, 0]}
            isAnimationActive={false}
          >
            {mutedBins
              ? rows.map((row, i) => (
                  <Cell key={row.label} fill={mutedBins.includes(i) ? MUTED_BAR : "var(--color-accent)"} />
                ))
              : null}
          </Bar>
          <Scatter dataKey="__mark" fill="var(--color-suppressed)" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <StatCallout
        summary={histogram.summary}
        nTotal={histogram.n_total}
        unit={histogram.unit}
        floorN={floorN}
        measure={measure}
      />
    </div>
  );
}

export function histogramTableRows(histogram: Histogram): (string | number)[][] {
  return histogram.bins.map((bin) => [
    binLabel(bin),
    bin.cell.status === "ok" ? formatCount(bin.cell.value) : "suppressed",
  ]);
}

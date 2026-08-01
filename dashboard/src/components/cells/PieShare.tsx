"use client";

// Part-to-whole donut + a figure-carrying legend (D-59).
//
// Two callers, one component: Adoption's active users by program level and
// Language's message mix. Both are a small closed set of categories that partition a
// published total, which is the only case a pie is the right form at all.
//
// Three rules, none of them cosmetic:
//
//  1. **All-or-nothing.** `slices` must be complete and published. A donut drawn over a
//     partial set silently asserts the missing category is zero — the exact claim the
//     privacy floor exists not to make — so the caller checks for suppression and renders
//     its table alone instead. `PieShare` cannot make that call itself: only the caller
//     knows what the whole was meant to be.
//  2. **The legend carries the numbers.** Two of the four hues sit below 3:1 against this
//     surface (validated: #1baf7a 2.74, #eda100 2.11), which obliges visible labels or a
//     table. The legend IS that relief, which is what lets Language collapse its table
//     into the standard disclosure. It also answers the pie's real weakness — angles
//     cannot compare 50% against 44% — by putting both numbers in text.
//  3. **Text wears ink tokens, never the series color.** The swatch carries identity; the
//     label and value stay readable.
//
// A measured zero keeps its legend row (`0`, `0%`) and contributes no arc: absence of ink
// is the honest rendering of "nobody", and dropping the row would read as "not measured".

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatCount } from "@/lib/format";

export type PieSlice = {
  key: string;
  label: string;
  value: number;
  color: string;
};

function SliceTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload: PieSlice }>;
  total: number;
}) {
  const slice = active ? payload?.[0]?.payload : undefined;
  if (!slice) return null;
  return (
    <div className="rounded border border-edge bg-card px-2 py-1 text-xs shadow-sm">
      <span className="font-medium text-ink">{slice.label}</span>
      <span className="text-ink-2">
        {" "}
        — {formatCount(slice.value)}
        {total > 0 ? ` (${Math.round((slice.value / total) * 100)}%)` : ""}
      </span>
    </div>
  );
}

export function PieShare({
  slices,
  total,
  centerLabel,
  ariaLabel,
  valueLabel,
}: {
  slices: PieSlice[];
  /** The denominator the shares are read against — the caller names it, because
   *  "share of the window" and "share of the levels shown" are different claims. */
  total: number;
  /** Sits in the hole: the total, in words the card's title does not already say. */
  centerLabel: string;
  ariaLabel: string;
  /** Column header for the legend's counts, e.g. "Students" or "Messages". */
  valueLabel: string;
}) {
  const drawn = slices.filter((s) => s.value > 0);
  const share = (value: number) => (total > 0 ? `${Math.round((value / total) * 100)}%` : "—");
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
      <div className="relative h-[168px] w-[168px] shrink-0" role="img" aria-label={ariaLabel}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={drawn}
              dataKey="value"
              nameKey="label"
              innerRadius="58%"
              outerRadius="92%"
              startAngle={90}
              endAngle={-270}
              // 2px of surface between segments: the spacer that keeps two adjacent
              // fills from reading as one, required whether or not the hues differ.
              stroke="var(--color-card)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {drawn.map((slice) => (
                <Cell key={slice.key} fill={slice.color} />
              ))}
            </Pie>
            <Tooltip content={<SliceTooltip total={total} />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-xl leading-none text-ink tabular-nums">
            {formatCount(total)}
          </span>
          <span className="mt-1 max-w-[6.5rem] text-center text-[10px] leading-tight text-ink-3">
            {centerLabel}
          </span>
        </div>
      </div>
      <table className="w-full text-xs tabular-nums">
        <thead>
          <tr className="border-b border-hairline text-left text-ink-2">
            <th className="py-1 font-medium">Group</th>
            <th className="py-1 text-right font-medium">{valueLabel}</th>
            <th className="py-1 text-right font-medium">Share</th>
          </tr>
        </thead>
        <tbody>
          {slices.map((slice) => (
            <tr key={slice.key} className="border-b border-hairline last:border-0">
              <td className="flex items-center gap-2 py-1.5 text-ink">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: slice.color }}
                  aria-hidden
                />
                {slice.label}
              </td>
              <td className="py-1.5 text-right text-ink">{formatCount(slice.value)}</td>
              <td className="py-1.5 text-right text-ink-2">{share(slice.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
//
// D-60 puts each share **inside its arc** as well, for the slices with room. The legend is
// still the accessible channel and still carries every row; the in-arc number is the one a
// reader takes without moving their eyes, which is what a part-to-whole figure is for. Two
// constraints make it a per-slice decision rather than a switch:
//
//  * **Room.** Below ~8% the arc is shorter than the text and the label collides with its
//    neighbours. Those slices say their share in the legend and nowhere else — better a
//    number in one place than a smear in two.
//  * **Ink.** White is not readable on all four hues: measured against white, the green is
//    2.9:1 and the amber 2.2:1, while near-black ink gives 6.0:1 and 7.8:1 on the same two.
//    The readable ink is a property of the hue, so it comes from `inkOn` (one table, in
//    `lib/palette.ts`) rather than a `fill="white"` at the draw site. Getting this wrong is
//    invisible on the dark hues and unreadable on the light ones — the failure that
//    survives review because three of four slices still look fine.

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatCount } from "@/lib/format";
import { inkOn } from "@/lib/palette";

/** Below this share of the ring, the arc is narrower than "12%" — legend only. */
const LABEL_MIN_SHARE = 0.08;

export type PieSlice = {
  key: string;
  label: string;
  value: number;
  color: string;
  /** Override for the in-arc share's text color. Omit it: `inkOn(color)` is right for
   *  every fill in the dashboard palette, and a caller that overrides it is asserting a
   *  contrast ratio nobody measured. */
  ink?: string;
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
  // The in-arc share is computed from `total`, never from recharts' own `percent`: that one
  // is the slice over the sum of the *drawn* slices, and the moment those two denominators
  // disagree the ring would print one number and its own legend another.
  const arcLabel = (props: {
    cx?: number;
    cy?: number;
    midAngle?: number;
    innerRadius?: number;
    outerRadius?: number;
    index?: number;
  }) => {
    const { cx = 0, cy = 0, midAngle = 0, innerRadius = 0, outerRadius = 0, index = 0 } = props;
    const slice = drawn[index];
    if (!slice || total <= 0 || slice.value / total < LABEL_MIN_SHARE) return null;
    const radius = (innerRadius + outerRadius) / 2;
    const radians = (-midAngle * Math.PI) / 180;
    return (
      <text
        x={cx + radius * Math.cos(radians)}
        y={cy + radius * Math.sin(radians)}
        fill={slice.ink ?? inkOn(slice.color)}
        fontSize={11}
        fontWeight={600}
        textAnchor="middle"
        dominantBaseline="central"
        // The legend row says the same thing in a readable order; a screen reader
        // meeting this twice would hear "83% 83%".
        aria-hidden
      >
        {share(slice.value)}
      </text>
    );
  };
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
              label={arcLabel}
              // Leader lines are for labels outside the ring; ours sit in the band.
              labelLine={false}
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

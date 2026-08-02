// A 100%-stacked column per group, with one legend under all of them (D-62).
//
// Two callers, one component: Language's language mix per program level, and Adoption's
// level mix per measure. Both are the same claim — a small closed set of categories
// partitioning a published total, compared across several groups — which is the case a
// stacked column answers better than anything else, because every category sits at the
// same height in every column and the eye reads across.
//
// Pure CSS rather than recharts, for `CategoryBars`' reason (D-27): the suppressed-cell
// rendering is the hard part, and a bespoke mark beats a chart-lib segment at it. Nothing
// here needs a scale, an axis or a hook, so it stays a server component too.
//
// Four rules, none cosmetic:
//
//  1. **The column is drawn against the group's published total, never against the sum of
//     its own segments.** Rescaling to the segments that survived the privacy floor makes
//     them total 100%, which asserts the withheld one is zero — the exact claim the floor
//     exists not to make. What is missing shows up as unfilled column, which is the one
//     thing a stacked column can say and a ring cannot: `PieShare` has to refuse to draw
//     at all, because a ring has no shape for "and this much is unaccounted for".
//  2. **A remainder over a suppressed cell is striped, not blank.** Same grammar as every
//     other withheld mark here (`suppressed-stipple`, `DaypartBars`): gray, textured, and
//     never mistakable for a measured zero. The caller's `suppressionKey` on the card says
//     "withheld, not zero" in words.
//  3. **A measured zero draws nothing and keeps its legend row.** Absence of ink is the
//     honest rendering of "nobody"; dropping the legend row would read as "not measured".
//  4. **Text wears `inkOn(fill)`, never a hard-coded white.** Two of the four fills in this
//     palette flip which ink is readable on them (see `lib/palette.ts`) — white on the
//     amber is 2.2:1. Getting it wrong is invisible on the dark fills and unreadable on
//     the light ones, which is how it would survive review.
//
// Whether a column may be drawn at all is the **caller's** call, exactly as with
// `PieShare`: only the caller knows what the whole was meant to be. A caller that cannot
// name an honest denominator passes `total: null` and the column renders as unavailable
// rather than as a shape.

import { formatCount } from "@/lib/format";
import { inkOn } from "@/lib/palette";

/** Column height. Sized so the smallest share worth labelling still clears MIN_LABEL_PX:
 *  6% — Language's Undetermined in most windows — is 14.4px here. */
const COLUMN_H = 240;
// Wide enough that three of them do not float in the middle of a full-width card (the
// "mostly void" problem D-61 fixed for the donut), narrow enough that a column still reads
// as a column rather than a block.
const COLUMN_W = 104;
/** Below this, an 11px label does not fit in the segment; the legend, the hover title and
 *  the data table carry that share instead. Better a number in three places than a smear. */
const MIN_LABEL_PX = 14;
/** Rounding slack: a remainder under this is arithmetic, not a withheld category. */
const REMAINDER_EPSILON = 0.005;

export type StackSeries = { key: string; label: string; color: string };
/** One category's cell in one group. `value: null` + `suppressed` is withheld; `value:
 *  null` alone is "this group does not publish this category at all". */
export type StackCell = { value: number | null; suppressed: boolean };
export type StackGroup = {
  key: string;
  label: string;
  /** The denominator this column is drawn against, or null when the caller cannot name an
   *  honest one — see the header. The card's note says which total it is. */
  total: number | null;
  cells: Record<string, StackCell | undefined>;
  /** Micro-caption for a column with **no denominator**. The two other undrawable states
   *  name themselves — see `caption` below. */
  unavailable?: string;
  /** Plural unit for this column's hover titles, where the groups measure different things
   *  (Adoption: active users vs messages). One noun for the whole figure is right only
   *  where every column counts the same thing, as Language's do. */
  valueNoun?: string;
};

function Column({
  group,
  series,
  valueNoun,
}: {
  group: StackGroup;
  series: StackSeries[];
  valueNoun: string;
}) {
  const total = group.total;
  const withheld = series.some((s) => group.cells[s.key]?.suppressed);
  // Zero-value categories are filtered out of the drawing (rule 3) but stay in the legend.
  const drawn =
    total !== null && total > 0
      ? series.flatMap((s) => {
          const value = group.cells[s.key]?.value;
          if (value == null || value <= 0) return [];
          return [{ ...s, value, share: Math.min(1, value / total) }];
        })
      : [];
  const filled = drawn.reduce((sum, d) => sum + d.share, 0);
  const remainder = Math.max(0, 1 - filled);
  const pct = (share: number) => `${Math.round(share * 100)}%`;
  const noun = group.valueNoun ?? valueNoun;
  // Three different claims about the data, and the floor's whole doctrine is that they must
  // never be confused: no denominator to draw against, a denominator every category was
  // withheld from, and a denominator every category measured zero against. One caption for
  // all three said "no total" over a fully striped Language column whose own card promised
  // the stripes meant "withheld" — and would have said "withheld" over a measured zero,
  // which is rule 3 inverted.
  const caption = total === null ? (group.unavailable ?? "·") : withheld ? "withheld" : "0";

  return (
    <div className="flex flex-col items-center">
      <div
        className="relative overflow-hidden rounded-[4px] bg-paper"
        style={{ height: COLUMN_H, width: COLUMN_W }}
      >
        {drawn.length === 0 ? (
          <div
            className={`flex h-full items-center justify-center ${
              withheld ? "suppressed-stipple" : ""
            }`}
          >
            <span className={`text-[11px] ${caption === "0" ? "text-ink-3" : "text-suppressed"}`}>
              {caption}
            </span>
          </div>
        ) : (
          // column-reverse so the first series anchors to the baseline, where a stacked
          // column is actually comparable across groups. `flexShrink: 0` keeps the explicit
          // heights exact; the separator is a border rather than a flex `gap` for the same
          // reason — a gap would add to the column's height and push the total past 100%.
          <div className="absolute inset-0 flex flex-col-reverse">
            {drawn.map((d, i) => {
              const px = d.share * COLUMN_H;
              return (
                <div
                  key={d.key}
                  className="flex items-center justify-center"
                  style={{
                    height: `${d.share * 100}%`,
                    flexShrink: 0,
                    background: d.color,
                    boxSizing: "border-box",
                    borderBottom: i > 0 ? "2px solid var(--color-card)" : undefined,
                  }}
                  title={`${group.label} · ${d.label}: ${[formatCount(d.value), noun]
                    .filter(Boolean)
                    .join(" ")} (${pct(d.share)})`}
                >
                  {px >= MIN_LABEL_PX ? (
                    <span
                      className="text-[11px] font-semibold tabular-nums"
                      style={{ color: inkOn(d.color) }}
                      // The legend names the category and the data table carries every
                      // share as text; a screen reader meeting this too would hear "83%"
                      // with nothing attached to it.
                      aria-hidden
                    >
                      {pct(d.share)}
                    </span>
                  ) : null}
                </div>
              );
            })}
            {withheld && remainder > REMAINDER_EPSILON ? (
              // Grows into whatever the drawn segments left, so the arithmetic cannot
              // drift: this band IS the unpublished part of the total, drawn to scale.
              <div
                className="suppressed-stipple"
                style={{
                  flex: "1 1 auto",
                  boxSizing: "border-box",
                  borderBottom: "2px solid var(--color-card)",
                }}
                title={`${group.label}: ${pct(remainder)} withheld under the privacy floor`}
              />
            ) : null}
          </div>
        )}
      </div>
      <div className="mt-2 text-center text-xs text-ink-2">{group.label}</div>
    </div>
  );
}

export function StackedShareBars({
  groups,
  series,
  ariaLabel,
  valueNoun,
  footer,
}: {
  groups: StackGroup[];
  /** Drawing order, bottom of the column upward, and legend order left to right. Fixed by
   *  the caller's constant list — a hue belongs to a category, never to its rank. */
  series: StackSeries[];
  ariaLabel: string;
  /** Plural noun for the hover titles, e.g. "messages" or "active users". */
  valueNoun: string;
  /** A strip under the legend for a measure that is not part of any column — Adoption's
   *  reach, which is a ratio against an outside denominator rather than a share of these. */
  footer?: React.ReactNode;
}) {
  if (groups.length === 0) return null;
  return (
    <div>
      <div
        className="flex flex-wrap items-end justify-center gap-x-8 gap-y-4"
        role="img"
        aria-label={ariaLabel}
      >
        {groups.map((group) => (
          <Column key={group.key} group={group} series={series} valueNoun={valueNoun} />
        ))}
      </div>
      {/* One legend for every column (>= 2 series always carries one), under the figure
          rather than beside it: it belongs to all the columns equally, and a legend to one
          side reads as belonging to the column it touches. Swatch carries identity, text
          stays in ink tokens. */}
      <ul className="mt-4 flex flex-wrap justify-center gap-x-5 gap-y-1.5">
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5 text-xs text-ink-2">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: s.color }}
              aria-hidden
            />
            {s.label}
          </li>
        ))}
      </ul>
      {footer}
    </div>
  );
}

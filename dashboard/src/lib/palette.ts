// Readable ink per series fill (D-60).
//
// The dashboard draws from one four-slot categorical palette — accent blue, green, amber,
// neutral gray — declared in `globals.css` and reached for by name in three places (LANGS,
// LEVEL_COLORS, the semester overlay), plus the sequential daypart ramp below. Anything
// that prints text *on top of* one of those fills needs to know which of the two inks
// survives there, and that is a property of the hue, not of the caller.
//
// Measured against this palette (WCAG 2.1 contrast ratio, text on fill):
//
//   fill                   white   near-black ink
//   #0063a6 accent          6.4      1.9
//   #1baf7a series-en       2.9      6.0
//   #eda100 series-other    2.2      7.8
//   #6e6c66 neutral         5.0      3.4
//
// So the choice flips twice across four slots — which is exactly why it cannot be a single
// hard-coded `fill="white"` at the draw site. Unknown fills fall back to the surface color:
// most fills that reach here are the dark accent, and a light-on-unknown miss degrades to
// a faint label rather than an invisible one.

/**
 * Sequential ramp for the dayparts, in clock order (D-60).
 *
 * Not the categorical palette, on purpose. `DaypartBars` has always insisted the blocks
 * are "an ordered sequence, not four identities", which is why the bars take a single hue;
 * a ring has to fill four arcs, and four unrelated hues would assert exactly the identity
 * the bars refuse. A ramp keeps the sequence readable — the ring reads as a clock face,
 * lightest at 00–06 and deepest at 18–24.
 *
 * The one thing it must not do is imply magnitude, and it does not: the arc angle carries
 * the count, and in every window we have the darkest block is not the largest. The steps
 * are ~1.6x apart in luminance, which separates them under CVD as well as by hue, and each
 * has a passing ink in the table below — the two light steps take near-black, the two dark
 * ones take the surface color.
 *
 * Indexed by the daypart's position in the published registry, which is ordered by
 * from_hour. The registry is pinned at four equal blocks (see CLAUDE.md — the equality is
 * load-bearing); a longer one would wrap rather than crash, and would look wrong enough
 * to be caught.
 */
export const DAYPART_RAMP = ["#cfe1ef", "#8fbadb", "var(--color-accent)", "#073d63"];

const INK_ON: Record<string, string> = {
  "var(--color-accent)": "var(--color-card)",
  "var(--color-series-en)": "var(--color-ink)",
  "var(--color-series-other)": "var(--color-ink)",
  "#6e6c66": "var(--color-card)",
  "#cfe1ef": "var(--color-ink)",
  "#8fbadb": "var(--color-ink)",
  "#073d63": "var(--color-card)",
};

/** The readable text color to print on top of `fill`. */
export const inkOn = (fill: string): string => INK_ON[fill] ?? "var(--color-card)";

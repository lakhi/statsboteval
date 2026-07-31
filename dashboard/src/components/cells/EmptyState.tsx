/**
 * The two honest kinds of "nothing here" (contract invariant 5): a section the
 * pipeline has not published yet, and a window a section has no rollup for.
 * Never conflated with suppression or zero.
 */
export function SectionPending({ what }: { what: string }) {
  return (
    <div className="rounded-lg border border-edge bg-card px-6 py-10 text-center">
      <p className="font-display text-lg italic text-ink-2">Not in this data release yet.</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-ink-3">
        {what} will appear here once the weekly pipeline publishes it — the view lights up on its
        own, no dashboard change needed.
      </p>
    </div>
  );
}

/**
 * The third honest "nothing here" (1.7.0, D-55): the window has data and the section is
 * published, but this program level did not use StatsBot in it — a measured absence, not a
 * gap in the data and not suppression, so it says so in those words rather than borrowing
 * either other state.
 */
export function LevelGap({ levelLabel, windowLabel }: { levelLabel: string; windowLabel: string }) {
  return (
    <div className="rounded-lg border border-edge bg-card px-6 py-8 text-center">
      <p className="text-sm text-ink-2">
        No <span className="font-medium text-ink">{levelLabel.toLowerCase()}</span> activity in{" "}
        <span className="text-ink">{windowLabel}</span>.
      </p>
      <p className="mx-auto mt-1.5 max-w-md text-xs text-ink-3">
        Nobody at this program level sent a message in this period. Widen the window, or
        switch to All users to see who did.
      </p>
    </div>
  );
}

/**
 * The fourth (1.8.0, D-56): the figure exists and is correct, but the selected window makes
 * the question it answers vacuous — weeks active in a one-week window is 1 for everyone
 * whatever the data says. Distinct from every state above it, and worth its own words: the
 * number is not missing, not withheld and not zero, it is defined away.
 */
export function MeasureUndefined({ what, why }: { what: string; why: string }) {
  return (
    <div className="rounded-lg border border-edge bg-card px-6 py-8 text-center">
      <p className="text-sm text-ink-2">{what}</p>
      <p className="mx-auto mt-1.5 max-w-md text-xs text-ink-3">{why}</p>
    </div>
  );
}

export function WindowGap({ what, windowLabel }: { what: string; windowLabel: string }) {
  return (
    <div className="rounded-lg border border-edge bg-card px-6 py-8 text-center">
      <p className="text-sm text-ink-3">
        No {what} rollup is published for <span className="text-ink-2">{windowLabel}</span>.
      </p>
    </div>
  );
}

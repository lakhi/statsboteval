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

export function WindowGap({ what, windowLabel }: { what: string; windowLabel: string }) {
  return (
    <div className="rounded-lg border border-edge bg-card px-6 py-8 text-center">
      <p className="text-sm text-ink-3">
        No {what} rollup is published for <span className="text-ink-2">{windowLabel}</span>.
      </p>
    </div>
  );
}

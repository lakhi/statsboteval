import type { Aggregates, Finding, TrendsWindow } from "@/lib/aggregates.gen";
import { weekShort } from "@/lib/format";
import { ALL } from "@/lib/levels";
import { isInProgress, type AnyWindow } from "@/lib/windows";
import { SectionPending, WindowGap } from "../cells/EmptyState";
import { FindingCard, windowLabel } from "../cells/FindingCard";
import { TopicRowTip } from "../cells/TopicRowTip";
import { PanelIntro, type TabProps } from "./shared";

export type TrendsTabProps = TabProps & {
  /** Switch the dashboard to a finding's source tab. Safe as a prop: Dashboard.tsx is
   *  the "use client" entry point, so this never crosses the server/client boundary. */
  onJumpToTab: (tabId: string) => void;
};

/**
 * "How is usage changing over time?" — the sixth tab (D-49).
 *
 * Findings are chosen in the pipeline, never here: contract invariant 4 forbids the
 * client re-aggregating, and the per-student data the tests need exists only locally.
 * This component's whole job is to render the array in the order it arrives.
 *
 * The three "nothing to show" states are deliberately distinct: "no earlier period",
 * "nothing was testable" and "tested and flat" are different claims, and collapsing
 * them would have the tab assert a comparison that never ran.
 */
export function TrendsTab({ doc, win, level, onJumpToTab }: TrendsTabProps) {
  const intro = (
    <PanelIntro
      question="How is usage changing over time?"
      deck="Only measures that changed enough to stand out from normal variation are listed — anything that stayed stable is left out."
    />
  );

  // Findings are selected in the pipeline over the whole cohort, so this tab has no
  // per-level shape to render (D-55). Saying so beats quietly showing cohort-wide
  // comparisons under a bachelor filter. The tab is hidden from the strip anyway; this
  // only matters to whoever opens ?tab=trends.
  if (level !== ALL) {
    return (
      <div>
        {intro}
        <div className="rounded-lg border border-edge bg-card px-6 py-8 text-center text-sm text-ink-2">
          Trends compares whole periods across every program level at once, so it does not
          follow the program-level filter. Switch to <span className="font-medium">All users</span>{" "}
          to read it.
        </div>
      </div>
    );
  }

  const section = doc.sections.trends;
  if (!section) {
    // A 1.2.0 document under a 1.3.0 dashboard. Deployment is safe in both directions.
    return (
      <div>
        {intro}
        <SectionPending what="Trends (the trends section)" />
      </div>
    );
  }

  const entry: TrendsWindow | undefined = section.per_window[win.id];
  if (!entry) {
    return (
      <div>
        {intro}
        <WindowGap what="trends" windowLabel={win.label} />
      </div>
    );
  }

  return (
    <div>
      {intro}
      <TrendsBody doc={doc} win={win} entry={entry} onJumpToTab={onJumpToTab} />
    </div>
  );
}

function TrendsBody({
  doc,
  win,
  entry,
  onJumpToTab,
}: {
  doc: Aggregates;
  win: AnyWindow;
  entry: TrendsWindow;
  onJumpToTab: (tabId: string) => void;
}) {
  const findings: Finding[] = entry.findings ?? [];

  if (!entry.baseline) {
    return (
      <Notice
        headline="No earlier period to compare."
        body={`${win.label} is the earliest period in this data, so there is nothing before it to measure against. Comparisons appear from the next period onward.`}
      />
    );
  }

  if (entry.insufficient_data) {
    return (
      <Notice
        headline="Too little activity in this period to compare."
        body="Not enough students were active for any measure to be compared reliably. This window may fall in a semester break, the Christmas closure, or an exam period."
      />
    );
  }

  if (findings.length === 0) {
    return (
      <div>
        <BaselineLine doc={doc} win={win} baseline={entry.baseline} />
        <Notice
          headline="No meaningful shifts in this period."
          body="Every measure was compared against the previous period and none moved far enough to stand out from normal variation."
        />
      </div>
    );
  }

  return (
    <div>
      <BaselineLine doc={doc} win={win} baseline={entry.baseline} />
      {/* The heading counts what is actually shown. A fixed "Top 5" over three cards
          would read as two missing cards rather than as three qualifying ones. */}
      <div className="mb-3 mt-5">
        <TopicRowTip
          tip={
            <>
              These are the changes most likely to inform a teaching or tooling decision,
              chosen from among those large and consistent enough to stand out from normal
              variation. Ordering is by how much a change could matter, not by how large it
              is — a small shift in what students ask about outranks a big shift in when
              they log in. At most five are shown, and at most three from any one tab.
            </>
          }
        >
          <h3 className="inline-block text-sm font-semibold text-ink">
            Top {findings.length} {findings.length === 1 ? "trend" : "trends"}
            <span className="ml-1.5 text-xs font-normal text-ink-3">
              — how these were chosen
            </span>
          </h3>
        </TopicRowTip>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {findings.map((finding) => (
          <FindingCard key={finding.id} doc={doc} finding={finding} onJumpToTab={onJumpToTab} />
        ))}
      </div>
    </div>
  );
}

/** What the selected window is being measured against — the tab's whole premise. */
function BaselineLine({
  doc,
  win,
  baseline,
}: {
  doc: Aggregates;
  win: AnyWindow;
  baseline: NonNullable<TrendsWindow["baseline"]>;
}) {
  let text: string;
  if (baseline.kind === "trajectory") {
    text = "Each measure shown across every semester.";
  } else if (baseline.kind === "weeks") {
    text = `Compared with the preceding 4 weeks (${weekShort(baseline.from)}–${weekShort(baseline.through)}).`;
  } else {
    text = `Compared with ${windowLabel(doc, baseline.window_id)}.`;
  }
  return (
    <p className="text-sm text-ink-2">
      {text}
      {isInProgress(win) ? (
        <span className="text-ink-3">
          {" "}
          This period is still in progress — volume measures are compared per covered week.
        </span>
      ) : null}
    </p>
  );
}

function Notice({ headline, body }: { headline: string; body: string }) {
  return (
    <div className="rounded-lg border border-edge bg-card px-6 py-8 text-center">
      <p className="font-display text-lg italic text-ink-2">{headline}</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-ink-3">{body}</p>
    </div>
  );
}

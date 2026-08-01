import type { ReactNode } from "react";
import type { Histogram } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { formatCount, formatStat, unitLabel } from "@/lib/format";
import { ALL, sliceByLevel } from "@/lib/levels";
import { isSingleWeek } from "@/lib/windows";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { LevelGap, MeasureUndefined, SectionPending, WindowGap } from "../cells/EmptyState";
import { HistogramChart, histogramTableRows } from "../cells/HistogramChart";
import { ProgramLevelCard, type LevelColumn } from "../cells/ProgramLevelCard";
import {
  levelsIn,
  PanelIntro,
  showsLevelCard,
  STATUS_LABELS,
  UnscopedNote,
  type TabProps,
} from "./shared";

/** One exchange, stated wherever a message count is plotted (D-50 wording). */
const MESSAGE_CAPTION = "1 msg = 1 user message + 1 StatsBot reply.";

function HistogramCard({
  doc,
  title,
  histogram,
  xLabel,
  note,
  lead,
  mutedBins,
  measure,
}: {
  doc: TabProps["doc"];
  title: string;
  histogram: Histogram;
  xLabel: string;
  note?: ReactNode;
  /** A one-line reading of the figure, above the plot. */
  lead?: ReactNode;
  mutedBins?: readonly number[];
  measure?: string;
}) {
  const footnotes = resolveFootnotes(doc, [histogram.footnote_ids]);
  const suppressed = histogram.bins.some((b) => b.cell.status === "suppressed");
  return (
    <ChartCard
      title={title}
      markers={symbolsFor(footnotes, histogram.footnote_ids)}
      footnotes={footnotes}
      note={note}
      suppressionKey={suppressed ? "Gray baseline marks are suppressed bins" : null}
      floorN={doc.privacy_floor_n}
      table={
        <DataTable
          caption={title}
          head={[xLabel, unitLabel(histogram.unit)]}
          rows={histogramTableRows(histogram)}
        />
      }
    >
      {lead}
      <HistogramChart
        histogram={histogram}
        floorN={doc.privacy_floor_n}
        mutedBins={mutedBins}
        measure={measure}
      />
    </ChartCard>
  );
}

/**
 * "Tried it once" vs "came back", stated in words above the weeks-active plot.
 *
 * Display math only: one published cell divided by another (contract invariant 4,
 * the same licence the language shares run on). Deliberately never states the
 * complement — that would be a subtraction across bins, which is how a suppressed
 * bin's value gets recovered. Renders nothing unless both cells it needs are published.
 */
function triedOnceShare(histogram: Histogram): number | null {
  const firstBin = histogram.bins[0]?.cell;
  const total = histogram.n_total;
  if (!firstBin || firstBin.status !== "ok" || total.status !== "ok" || total.value === 0) {
    return null;
  }
  return Math.round((firstBin.value / total.value) * 100);
}

function TriedVsAdopted({ histogram }: { histogram: Histogram }) {
  const share = triedOnceShare(histogram);
  const firstBin = histogram.bins[0]?.cell;
  const total = histogram.n_total;
  if (share === null || firstBin?.status !== "ok" || total.status !== "ok") return null;
  return (
    <p className="mb-3 text-sm leading-snug text-ink-2">
      <span className="font-semibold text-ink">
        {formatCount(firstBin.value)} of {formatCount(total.value)} students ({share}%)
      </span>{" "}
      wrote in only one week — they tried StatsBot rather than adopting it.
    </p>
  );
}

/** The median of a published summary, or null for every state that is not a number. */
const medianOf = (histogram: Histogram | undefined): string | null =>
  histogram?.summary?.status === "ok" ? formatStat(histogram.summary.median) : null;

export function EngagementTab({ doc, win, level }: TabProps) {
  const sessions = doc.sections.sessions;
  const perStudent = doc.sections.per_student;
  const intro = (
    <PanelIntro
      question="How deeply do students engage?"
      deck="Breadth per student and depth per conversation for the selected window: how often students come back, how long conversations run, and how much each student writes. Per student counts only the students active in this window."
    />
  );
  if (!sessions && !perStudent) {
    return (
      <div>
        {intro}
        <SectionPending what="Engagement (the sessions and per-student sections)" />
      </div>
    );
  }

  const sessionRoll = sessions?.per_window[win.id];
  const studentRoll = perStudent?.per_window[win.id];
  const sessionScoped = sessionRoll
    ? sliceByLevel(sessionRoll, sessionRoll.by_status, level)
    : undefined;
  const studentScoped = studentRoll
    ? sliceByLevel(studentRoll, studentRoll.by_status, level)
    : undefined;
  // Unscoped = the sections publish no split at all (a pre-1.7.0 document, or no roster).
  // Distinct from null, which is this level genuinely absent from a split that exists.
  const unscoped =
    level !== ALL &&
    (sessionScoped?.scoped === false || studentScoped?.scoped === false);

  // A level absent from both sections is an empty page, so say that once rather than
  // repeating five identical cards.
  if (level !== ALL && sessionScoped === null && studentScoped === null) {
    return (
      <div>
        {intro}
        <LevelGap levelLabel={STATUS_LABELS[level] ?? level} windowLabel={win.label} />
      </div>
    );
  }

  /** Absence is a first-class state (invariant 5): a section may not be published at
   *  all, may have no rollup for this window, or may not cover this program level. */
  const card = <T, U>(
    section: unknown,
    roll: U | undefined,
    scoped: { data: T | U; scoped: boolean } | null | undefined,
    what: string,
    sectionName: string,
    render: (roll: T | U) => ReactNode,
  ): ReactNode => {
    if (!section) return <SectionPending what={`${what} (the ${sectionName} section)`} />;
    if (!roll) return <WindowGap what={what} windowLabel={win.label} />;
    if (scoped === null || scoped === undefined) {
      return <LevelGap levelLabel={STATUS_LABELS[level] ?? level} windowLabel={win.label} />;
    }
    return render(scoped.data);
  };

  const levels = levelsIn(studentRoll?.by_status ?? sessionRoll?.by_status);
  const statusFootnotes = resolveFootnotes(doc, [["status_rule", "status_multi"]]);
  const levelColumns: LevelColumn[] = [
    { header: "Level", align: "left", cell: () => null },
    {
      header: "Students",
      cell: (l) => {
        const total = studentRoll?.by_status?.[l]?.sessions_per_student.n_total;
        return total?.status === "ok" ? formatCount(total.value) : null;
      },
    },
    {
      header: "Median conv.",
      cell: (l) => medianOf(studentRoll?.by_status?.[l]?.sessions_per_student),
    },
    {
      header: "Median msgs",
      cell: (l) => medianOf(studentRoll?.by_status?.[l]?.messages_per_student),
    },
    {
      header: "Median length (min)",
      cell: (l) => medianOf(sessionRoll?.by_status?.[l]?.session_duration_minutes),
    },
    // Same measure as the withheld card below, so it goes with it: in a one-week window
    // "tried once" is 100% at every level by definition, and a column of 100%s reads as a
    // finding.
    ...(isSingleWeek(win)
      ? []
      : [
          {
            // First bin over n_total, never the complement — the same rule TriedVsAdopted
            // follows, because a complement across bins can recover a suppressed bin.
            header: "Tried once",
            cell: (l: string) => {
              const hist = studentRoll?.by_status?.[l]?.weeks_active_per_student;
              const share = hist ? triedOnceShare(hist) : null;
              return share === null ? null : `${share}%`;
            },
          },
        ]),
  ];

  // Order is editorial (D-59, revising D-53): breadth over the term leads, because it
  // carries the tab's actual finding — most students wrote in a single week and did not
  // come back, which `TriedVsAdopted` states in words above the plot. D-53 opened with
  // conversations-per-student and put weeks-active third, on the reasoning that the two
  // "how much" distributions were the headline; a reader scanning the tab meets the
  // answer to "how deeply do they engage?" three cards later than they should. Then the
  // two headline distributions, volume per student, and the Bergmann-comparable turn
  // count last.
  return (
    <div>
      {intro}
      {unscoped ? (
        <UnscopedNote>
          This data release does not break Engagement down by program level, so the figures
          below cover every level. Republishing with a current pipeline fills them in.
        </UnscopedNote>
      ) : null}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {/* Withheld in a one-week window (D-56), where every active student is active in
            exactly one week by definition and the histogram is 100% in the first bin
            whatever happened. Withheld here rather than omitted from the document: the
            figure is correct, it is the *question* that is empty at this width, and an
            absent block would say "not in this data release yet" — blaming the publish
            for a property of the window. */}
        {isSingleWeek(win)
          ? card(perStudent, studentRoll, studentScoped, "weeks active per student", "per-student", () => (
              <MeasureUndefined
                what="Weeks active needs more than one week."
                why="This window covers a single week, so every active student is active in exactly one week by definition. Widen the window to see how many came back."
              />
            ))
          : card(perStudent, studentRoll, studentScoped, "weeks active per student", "per-student", (roll) => (
              <HistogramCard
                doc={doc}
                title="Weeks active per student"
                xLabel="Weeks"
                histogram={roll.weeks_active_per_student}
                measure="week"
                lead={<TriedVsAdopted histogram={roll.weeks_active_per_student} />}
                mutedBins={[0]}
                // Only claim a lighter bar when one is actually drawn: in a window where the
                // single-week bin falls under the floor there is a suppression mark instead.
                note={
                  roll.weeks_active_per_student.bins[0]?.cell.status === "ok"
                    ? "The lighter bar is the single-week group; every bar to its right is a student who came back in a later week."
                    : undefined
                }
              />
            ))}

        {card(perStudent, studentRoll, studentScoped, "conversations per student", "per-student", (roll) => (
          <HistogramCard
            doc={doc}
            title="Conversations per student"
            xLabel="Conversations"
            histogram={roll.sessions_per_student}
            measure="conversation"
          />
        ))}

        {card(sessions, sessionRoll, sessionScoped, "conversation length", "sessions", (roll) => (
          <HistogramCard
            doc={doc}
            title="Conversation length (minutes)"
            xLabel="Minutes"
            histogram={roll.session_duration_minutes}
            measure="minute"
          />
        ))}

        {card(perStudent, studentRoll, studentScoped, "messages per student", "per-student", (roll) => (
          <HistogramCard
            doc={doc}
            title="Messages per student"
            xLabel="Messages"
            histogram={roll.messages_per_student}
            measure="message"
            note={MESSAGE_CAPTION}
          />
        ))}

        {card(sessions, sessionRoll, sessionScoped, "messages per conversation", "sessions", (roll) => (
          <HistogramCard
            doc={doc}
            title="Messages per conversation"
            xLabel="Messages"
            histogram={roll.messages_per_session}
            measure="message"
            note={MESSAGE_CAPTION}
          />
        ))}

        {showsLevelCard(level) && levels.length > 0 ? (
          <ProgramLevelCard
            title="By program level"
            tableCaption={`Engagement measures by program level, ${win.label}`}
            levels={levels}
            columns={levelColumns}
            floorN={doc.privacy_floor_n}
            markers={symbolsFor(statusFootnotes, ["status_rule"])}
            footnotes={statusFootnotes}
            note={
              <>
                Medians, not totals: these compare how the levels behave rather than how
                many of each there are. <span className="font-medium">Tried once</span> is the
                share of that level&rsquo;s students who wrote in a single week only.
              </>
            }
          />
        ) : null}
      </div>
    </div>
  );
}

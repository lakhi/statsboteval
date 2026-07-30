import type { ReactNode } from "react";
import type { Histogram, PerStudentWindow, SessionsWindow } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { SectionPending, WindowGap } from "../cells/EmptyState";
import { HistogramChart, histogramTableRows } from "../cells/HistogramChart";
import { PanelIntro, type TabProps } from "./shared";

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
}: TabProps & {
  title: string;
  histogram: Histogram;
  xLabel: string;
  note?: ReactNode;
  /** A one-line reading of the figure, above the plot. */
  lead?: ReactNode;
  mutedBins?: readonly number[];
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
          head={[xLabel, histogram.unit]}
          rows={histogramTableRows(histogram)}
        />
      }
    >
      {lead}
      <HistogramChart histogram={histogram} floorN={doc.privacy_floor_n} mutedBins={mutedBins} />
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
function TriedVsAdopted({ histogram }: { histogram: Histogram }) {
  const firstBin = histogram.bins[0]?.cell;
  const total = histogram.n_total;
  if (!firstBin || firstBin.status !== "ok" || total.status !== "ok" || total.value === 0) {
    return null;
  }
  const share = Math.round((firstBin.value / total.value) * 100);
  return (
    <p className="mb-3 text-sm leading-snug text-ink-2">
      <span className="font-semibold text-ink">
        {formatCount(firstBin.value)} of {formatCount(total.value)} students ({share}%)
      </span>{" "}
      wrote in only one week — they tried StatsBot rather than adopting it.
    </p>
  );
}

export function EngagementTab({ doc, win }: TabProps) {
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

  /** Absence is a first-class state (invariant 5): a section may not be published at
   *  all, or may have no rollup for this window. Neither is ever drawn as a zero. */
  const perStudentCard = (what: string, render: (roll: PerStudentWindow) => ReactNode): ReactNode => {
    if (!perStudent) return <SectionPending what={`${what} (the per-student section)`} />;
    if (!studentRoll) return <WindowGap what={what} windowLabel={win.label} />;
    return render(studentRoll);
  };
  const sessionCard = (what: string, render: (roll: SessionsWindow) => ReactNode): ReactNode => {
    if (!sessions) return <SectionPending what={`${what} (the sessions section)`} />;
    if (!sessionRoll) return <WindowGap what={what} windowLabel={win.label} />;
    return render(sessionRoll);
  };

  // Order is editorial (D-53): the two headline measures first — how often a student
  // came back, and how long a conversation ran — then breadth over the term, then
  // volume per student, then the Bergmann-comparable turn count last.
  return (
    <div>
      {intro}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {perStudentCard("conversations per student", (roll) => (
          <HistogramCard
            doc={doc}
            win={win}
            title="Conversations per student"
            xLabel="Conversations"
            histogram={roll.sessions_per_student}
          />
        ))}

        {sessionCard("conversation length", (roll) => (
          <HistogramCard
            doc={doc}
            win={win}
            title="Conversation length (minutes)"
            xLabel="Minutes"
            histogram={roll.session_duration_minutes}
          />
        ))}

        {perStudentCard("weeks active per student", (roll) => (
          <HistogramCard
            doc={doc}
            win={win}
            title="Weeks active per student"
            xLabel="Weeks"
            histogram={roll.weeks_active_per_student}
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

        {perStudentCard("messages per student", (roll) => (
          <HistogramCard
            doc={doc}
            win={win}
            title="Messages per student"
            xLabel="Messages"
            histogram={roll.messages_per_student}
            note={MESSAGE_CAPTION}
          />
        ))}

        {sessionCard("messages per conversation", (roll) => (
          <HistogramCard
            doc={doc}
            win={win}
            title="Messages per conversation"
            xLabel="Messages"
            histogram={roll.messages_per_session}
            note={MESSAGE_CAPTION}
          />
        ))}
      </div>
    </div>
  );
}

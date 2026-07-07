import type { Histogram } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { SectionPending, WindowGap } from "../cells/EmptyState";
import { HistogramChart, histogramTableRows } from "../cells/HistogramChart";
import { PanelIntro, type TabProps } from "./shared";

function HistogramCard({
  doc,
  title,
  histogram,
  xLabel,
}: TabProps & { title: string; histogram: Histogram; xLabel: string }) {
  const footnotes = resolveFootnotes(doc, [histogram.footnote_ids]);
  const suppressed = histogram.bins.some((b) => b.cell.status === "suppressed");
  return (
    <ChartCard
      title={title}
      markers={symbolsFor(footnotes, histogram.footnote_ids)}
      footnotes={footnotes}
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
      <HistogramChart histogram={histogram} floorN={doc.privacy_floor_n} />
    </ChartCard>
  );
}

export function EngagementTab({ doc, win }: TabProps) {
  const sessions = doc.sections.sessions;
  const tokens = doc.sections.tokens;
  const intro = (
    <PanelIntro
      question="How deeply do students engage?"
      deck="Depth proxies for the selected window: how long sessions run, how many turns they take, and how long StatsBot's replies are."
    />
  );
  if (!sessions && !tokens) {
    return (
      <div>
        {intro}
        <SectionPending what="Engagement (the sessions and tokens sections)" />
      </div>
    );
  }
  const sessionRoll = sessions?.per_window[win.id];
  const tokenRoll = tokens?.per_window[win.id];
  return (
    <div>
      {intro}
      <div className="grid gap-4 lg:grid-cols-2">
        {!sessions ? (
          <SectionPending what="Session distributions (the sessions section)" />
        ) : sessionRoll ? (
          <>
            <HistogramCard
              doc={doc}
              win={win}
              title="Messages per session"
              xLabel="Messages"
              histogram={sessionRoll.messages_per_session}
            />
            <HistogramCard
              doc={doc}
              win={win}
              title="Session duration (minutes)"
              xLabel="Minutes"
              histogram={sessionRoll.session_duration_minutes}
            />
          </>
        ) : (
          <WindowGap what="session-distribution" windowLabel={win.label} />
        )}

        {!tokens ? (
          <SectionPending what="Reply length (the tokens section)" />
        ) : tokenRoll ? (
          <HistogramCard
            doc={doc}
            win={win}
            title="Reply length (completion tokens per message)"
            xLabel="Tokens"
            histogram={tokenRoll.completion_tokens_per_message}
          />
        ) : (
          <WindowGap what="reply-length" windowLabel={win.label} />
        )}
      </div>
    </div>
  );
}

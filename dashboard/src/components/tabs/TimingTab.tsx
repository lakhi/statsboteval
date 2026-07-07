import type { WeeklySeries } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { sliceToWindow } from "@/lib/windows";
import { ActivityHeatmap, heatmapTableRows } from "../cells/ActivityHeatmap";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { SectionPending, WindowGap } from "../cells/EmptyState";
import { TrendChart, trendTableRows } from "../cells/TrendChart";
import { hasSuppressed, PanelIntro, type TabProps } from "./shared";

function TrendCard({
  doc,
  win,
  title,
  weekly,
  valueLabel,
}: TabProps & { title: string; weekly: WeeklySeries; valueLabel: string }) {
  const entries = sliceToWindow(weekly.series, win);
  const footnotes = resolveFootnotes(doc, [weekly.footnote_ids]);
  return (
    <ChartCard
      title={title}
      markers={symbolsFor(footnotes, weekly.footnote_ids)}
      footnotes={footnotes}
      suppressionKey={hasSuppressed(entries) ? "Gray baseline marks are suppressed weeks" : null}
      floorN={doc.privacy_floor_n}
      table={
        <DataTable
          caption={title}
          head={["Week", valueLabel]}
          rows={trendTableRows([{ id: "v", label: valueLabel, color: "", entries }])}
        />
      }
    >
      <TrendChart
        series={[{ id: "v", label: valueLabel, color: "var(--color-accent)", entries }]}
        floorN={doc.privacy_floor_n}
      />
    </ChartCard>
  );
}

export function TimingTab({ doc, win }: TabProps) {
  const intro = (
    <PanelIntro
      question="When do students use StatsBot?"
      deck="Weekly rhythm across the selected window, and the day-by-hour pattern of activity (Vienna local time)."
    />
  );
  const section = doc.sections.temporal_usage;
  if (!section) {
    return (
      <div>
        {intro}
        <SectionPending what="Timing (the temporal-usage section)" />
      </div>
    );
  }
  const heatmap = section.per_window[win.id]?.activity_heatmap;
  const heatmapFootnotes = heatmap ? resolveFootnotes(doc, [heatmap.footnote_ids]) : [];
  return (
    <div>
      {intro}
      <div className="grid gap-4 lg:grid-cols-2">
        <TrendCard doc={doc} win={win} title="Messages per week" weekly={section.weekly.messages} valueLabel="Messages" />
        <TrendCard doc={doc} win={win} title="Sessions per week" weekly={section.weekly.sessions} valueLabel="Sessions" />
        <TrendCard
          doc={doc}
          win={win}
          title="Active students per week"
          weekly={section.weekly.active_students}
          valueLabel="Active students"
        />
        {heatmap ? (
          <ChartCard
            title="Activity by weekday and hour"
            markers={symbolsFor(heatmapFootnotes, heatmap.footnote_ids)}
            footnotes={heatmapFootnotes}
            suppressionKey={
              heatmap.cells.some((c) => c.cell.status === "suppressed")
                ? "Striped cells are suppressed"
                : null
            }
            floorN={doc.privacy_floor_n}
            table={
              <DataTable
                caption="Messages by weekday and hour"
                head={["", ...Array.from({ length: 24 }, (_, h) => String(h))]}
                rows={heatmapTableRows(heatmap)}
              />
            }
          >
            <ActivityHeatmap grid={heatmap} floorN={doc.privacy_floor_n} />
          </ChartCard>
        ) : (
          <WindowGap what="activity-heatmap" windowLabel={win.label} />
        )}
      </div>
    </div>
  );
}

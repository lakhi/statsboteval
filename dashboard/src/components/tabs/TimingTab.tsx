import type { ReactNode } from "react";
import type { WeeklySeries } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { sliceToWindow } from "@/lib/windows";
import { ActivityHeatmap, heatmapTableRows } from "../cells/ActivityHeatmap";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { DaypartBars, daypartTableRows } from "../cells/DaypartBars";
import { SectionPending, WindowGap } from "../cells/EmptyState";
import { SemesterOverlay, semesterTableRows } from "../cells/SemesterOverlay";
import { TrendChart, trendTableRows } from "../cells/TrendChart";
import { hasSuppressed, PanelIntro, type TabProps } from "./shared";

function TrendCard({
  doc,
  win,
  title,
  weekly,
  valueLabel,
  note,
}: TabProps & { title: string; weekly: WeeklySeries; valueLabel: string; note?: ReactNode }) {
  const entries = sliceToWindow(weekly.series, win);
  const footnotes = resolveFootnotes(doc, [weekly.footnote_ids]);
  return (
    <ChartCard
      title={title}
      markers={symbolsFor(footnotes, weekly.footnote_ids)}
      footnotes={footnotes}
      suppressionKey={hasSuppressed(entries) ? "Gray baseline marks are suppressed weeks" : null}
      note={note}
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
      deck="Time of day and weekly rhythm across the selected window, in Vienna local time."
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
  const dayparts = doc.dayparts ?? [];
  const rollup = section.per_window[win.id];
  const heatmap = rollup?.daypart_heatmap;
  const totals = rollup?.daypart_totals;
  const heatmapFootnotes = heatmap ? resolveFootnotes(doc, [heatmap.footnote_ids]) : [];
  const totalsFootnotes = totals ? resolveFootnotes(doc, [totals.footnote_ids]) : [];

  // The overlay compares whole semesters, so it cannot honour the window picker.
  // Rendering it only under all_time keeps the picker's meaning exact: pick a
  // semester and everything on screen is that semester. Deliberately not a
  // WindowGap — that says "not available for this window", which would frame a
  // design decision as missing data.
  const profiles = win.kind === "all_time" ? (section.semester_profiles ?? []) : [];
  const profileFootnotes = profiles.length ? resolveFootnotes(doc, [profiles[0].footnote_ids]) : [];

  return (
    <div>
      {intro}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {totals && dayparts.length > 0 ? (
          <ChartCard
            title="When during the day"
            markers={symbolsFor(totalsFootnotes, totals.footnote_ids)}
            footnotes={totalsFootnotes}
            suppressionKey={
              Object.values(totals.by_daypart).some((c) => c.status === "suppressed") ||
              totals.weekend.status === "suppressed" ||
              totals.weekday.status === "suppressed"
                ? "Striped bars are suppressed"
                : null
            }
            floorN={doc.privacy_floor_n}
            table={
              <DataTable
                caption="Messages by time of day"
                head={["Block", "Messages"]}
                rows={daypartTableRows(totals, dayparts)}
              />
            }
          >
            <DaypartBars totals={totals} dayparts={dayparts} floorN={doc.privacy_floor_n} />
          </ChartCard>
        ) : (
          <WindowGap what="time-of-day" windowLabel={win.label} />
        )}

        {heatmap && dayparts.length > 0 ? (
          <ChartCard
            title="Activity by weekday and time of day"
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
                caption="Messages by weekday and time of day"
                head={["", ...dayparts.map((p) => p.label)]}
                rows={heatmapTableRows(heatmap, dayparts)}
              />
            }
          >
            <ActivityHeatmap grid={heatmap} dayparts={dayparts} floorN={doc.privacy_floor_n} />
          </ChartCard>
        ) : (
          <WindowGap what="activity-heatmap" windowLabel={win.label} />
        )}

        <TrendCard
          doc={doc}
          win={win}
          title="Messages per week"
          weekly={section.weekly.messages}
          valueLabel="Messages"
          note="1 msg = 1 student message + 1 LLM response."
        />
        <TrendCard
          doc={doc}
          win={win}
          title="Sessions per week"
          weekly={section.weekly.sessions}
          valueLabel="Sessions"
        />
        <TrendCard
          doc={doc}
          win={win}
          title="Active students per week"
          weekly={section.weekly.active_students}
          valueLabel="Active students"
          note={
            <>
              A student counts in any week they sent at least one message. The same student
              is counted again in every week they were active, so the line does not add up to
              a student total — Adoption&rsquo;s <em>Active users</em> is the deduplicated count
              for the whole window.
            </>
          }
        />

        {profiles.length > 0 ? (
          <ChartCard
            title="Semester rhythm compared"
            markers={symbolsFor(profileFootnotes, profiles[0].footnote_ids)}
            footnotes={profileFootnotes}
            suppressionKey={
              profiles.some((p) => p.points.some((pt) => pt.messages.status === "suppressed"))
                ? "Gaps in a line are suppressed weeks"
                : null
            }
            floorN={doc.privacy_floor_n}
            table={
              <DataTable
                caption="Messages by week of semester"
                head={["Week of semester", ...profiles.map((p) => p.label)]}
                rows={semesterTableRows(profiles)}
              />
            }
          >
            <SemesterOverlay profiles={profiles} />
          </ChartCard>
        ) : null}
      </div>
    </div>
  );
}

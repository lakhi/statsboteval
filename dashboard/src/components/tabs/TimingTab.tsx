import type { ReactNode } from "react";
import type {
  TemporalUsageByStatus,
  TemporalUsageWeekly,
  WeeklySeries,
} from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { sliceToWindow } from "@/lib/windows";
import { ActivityHeatmap, heatmapTableRows } from "../cells/ActivityHeatmap";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { DaypartBars, daypartTableRows } from "../cells/DaypartBars";
import { ALL, sliceByLevel } from "@/lib/levels";
import { LevelGap, SectionPending, WindowGap } from "../cells/EmptyState";
import { SemesterOverlay, semesterTableRows } from "../cells/SemesterOverlay";
import { TrendChart, trendTableRows } from "../cells/TrendChart";
import { ProgramLevelCard, type LevelColumn } from "../cells/ProgramLevelCard";
import {
  hasSuppressed,
  levelsIn,
  PanelIntro,
  showsLevelCard,
  STATUS_LABELS,
  UnscopedNote,
  valueOf,
  type TabProps,
} from "./shared";

function TrendCard({
  doc,
  win,
  title,
  weekly,
  valueLabel,
  note,
}: Omit<TabProps, "level"> & {
  title: string;
  weekly: WeeklySeries;
  valueLabel: string;
  note?: ReactNode;
}) {
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

export function TimingTab({ doc, win, level }: TabProps) {
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
  const byStatus = rollup?.by_status as Record<string, TemporalUsageByStatus> | undefined;
  const scoped = rollup ? sliceByLevel(rollup, byStatus, level) : undefined;
  // Weekly series live at document level and are sliced client-side, so the level filter
  // reaches them only through their own published copies (1.7.0). Without this the tab
  // would narrow the dayparts and leave the trend lines cohort-wide.
  const weeklySlice = sliceByLevel(
    section.weekly,
    section.weekly_by_status as Record<string, TemporalUsageWeekly> | undefined,
    level,
  );

  // null means the split IS published and this level is simply absent from it — a measured
  // absence. A section with no split at all comes back unscoped instead, and says so below.
  if (weeklySlice === null || (rollup && scoped === null)) {
    return (
      <div>
        {intro}
        <LevelGap levelLabel={STATUS_LABELS[level] ?? level} windowLabel={win.label} />
      </div>
    );
  }

  const weekly = weeklySlice.data;
  const unscoped = level !== ALL && (!weeklySlice.scoped || scoped?.scoped === false);
  const heatmap = scoped?.data.daypart_heatmap;
  const totals = scoped?.data.daypart_totals;
  const heatmapFootnotes = heatmap ? resolveFootnotes(doc, [heatmap.footnote_ids]) : [];
  const totalsFootnotes = totals ? resolveFootnotes(doc, [totals.footnote_ids]) : [];

  // The overlay compares whole semesters, so it cannot honour the window picker — and for
  // the same reason it does not honour the level filter either (D-55): its scope is
  // "every semester, everyone". Rendering it only under all_time + All users keeps both
  // pickers' meaning exact. Deliberately not a WindowGap or a LevelGap — those say "not
  // available", which would frame a design decision as missing data.
  const profiles =
    win.kind === "all_time" && level === ALL ? (section.semester_profiles ?? []) : [];
  // D-55 binds every tab to honour the filter or say why it cannot. The overlay is
  // cohort-wide by construction, so under a single level it must say so rather than
  // silently disappear and read as a broken chart.
  const overlayHidden = win.kind === "all_time" && level !== ALL && section.semester_profiles?.length;
  const profileFootnotes = profiles.length ? resolveFootnotes(doc, [profiles[0].footnote_ids]) : [];

  const levels = levelsIn(byStatus);
  // Within-level shares: the levels differ in size by an order of magnitude (66 bachelor
  // against 8 staff in 2026S), so a share-of-window denominator would flatten the small
  // groups into noise and hide the very difference the card exists to show.
  //
  // The denominator is the level's own PUBLISHED message total, never a sum of the four
  // daypart cells. Summing them breaks twice: one suppressed block makes the sum unusable
  // and blanks the whole row (discarding three publishable numbers), and normalising to
  // the surviving blocks would make them total 100% — asserting the suppressed block is
  // zero, which is worse than saying nothing. Dayparts partition messages exactly, so the
  // published total IS the right denominator: the published blocks show their true shares,
  // the row visibly falls short of 100%, and the gap is where the suppressed block went.
  const levelMessages = (levelKey: string): number | null =>
    valueOf(doc.sections.usage_context?.per_window[win.id]?.by_status?.[levelKey]?.messages);
  const daypartShare = (levelKey: string, part: string): string | null => {
    const value = valueOf(byStatus?.[levelKey]?.daypart_totals?.by_daypart[part]);
    const total = levelMessages(levelKey);
    return value === null || total === null || total === 0
      ? null
      : `${Math.round((value / total) * 100)}%`;
  };
  const statusFootnotes = resolveFootnotes(doc, [["status_rule", "status_multi"]]);
  const levelColumns: LevelColumn[] = [
    { header: "Level", align: "left", cell: () => null },
    ...dayparts.map((part) => ({
      header: part.label,
      cell: (l: string) => daypartShare(l, part.id),
    })),
    {
      header: "Weekend",
      cell: (l: string) => {
        const weekend = valueOf(byStatus?.[l]?.daypart_totals?.weekend);
        const total = levelMessages(l);
        return weekend === null || total === null || total === 0
          ? null
          : `${Math.round((weekend / total) * 100)}%`;
      },
    },
  ];

  return (
    <div>
      {intro}
      {unscoped ? (
        <UnscopedNote>
          This data release does not break Timing down by program level, so the figures below
          cover every level. Republishing with a current pipeline fills them in.
        </UnscopedNote>
      ) : null}
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
          weekly={weekly.messages}
          valueLabel="Messages"
          note="1 msg = 1 student message + 1 LLM response."
        />
        <TrendCard
          doc={doc}
          win={win}
          title="Sessions per week"
          weekly={weekly.sessions}
          valueLabel="Sessions"
        />
        <TrendCard
          doc={doc}
          win={win}
          title="Active students per week"
          weekly={weekly.active_students}
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

        {overlayHidden ? (
          <div className="rounded-lg border border-edge bg-card px-6 py-8 text-center">
            <p className="text-sm text-ink-2">
              <span className="font-medium text-ink">Semester rhythm compared</span> puts whole
              semesters side by side across every program level at once.
            </p>
            <p className="mx-auto mt-1.5 max-w-md text-xs text-ink-3">
              That is its scope, so it does not follow the program-level filter — switch to All
              users to read it.
            </p>
          </div>
        ) : null}

        {showsLevelCard(level) && levels.length > 0 && dayparts.length > 0 ? (
          <ProgramLevelCard
            title="By program level"
            tableCaption={`Time-of-day profile by program level, ${win.label}`}
            levels={levels}
            columns={levelColumns}
            floorN={doc.privacy_floor_n}
            markers={symbolsFor(statusFootnotes, ["status_rule"])}
            footnotes={statusFootnotes}
            note={
              <>
                Each row is a share of that level&rsquo;s own published message total, not of
                the window, so levels of very different size stay comparable. A row need not
                total 100%: a block whose count is suppressed is left out rather than folded
                into the rest.
              </>
            }
          />
        ) : null}
      </div>
    </div>
  );
}

import type { OkCell, SuppressedCell } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import { sliceToWindow } from "@/lib/windows";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { SectionPending, WindowGap } from "../cells/EmptyState";
import { KpiTile } from "../cells/KpiTile";
import { TrendChart, trendTableRows } from "../cells/TrendChart";
import { hasSuppressed, PanelIntro, type TabProps } from "./shared";

function ClassStat({
  label,
  cell,
  floorN,
}: {
  label: string;
  cell: OkCell | SuppressedCell;
  floorN: number;
}) {
  return (
    <div>
      {cell.status === "ok" ? (
        <div className="text-2xl font-semibold text-ink">{formatCount(cell.value)}</div>
      ) : (
        <div className="text-2xl font-semibold text-suppressed" title={`suppressed (< ${floorN} students)`}>
          —
        </div>
      )}
      <div className="mt-0.5 text-xs text-ink-2">{label}</div>
    </div>
  );
}

export function AdoptionTab({ doc, win }: TabProps) {
  const intro = (
    <PanelIntro
      question="Who uses StatsBot, and how much?"
      deck="Adoption for the selected window: cohort totals, new registrations, and the Bergmann-comparable user classes."
    />
  );
  const section = doc.sections.usage_context;
  if (!section) {
    return (
      <div>
        {intro}
        <SectionPending what="Adoption (the usage-context section)" />
      </div>
    );
  }

  const roll = section.per_window[win.id];
  const regs = section.weekly.registrations;
  const regEntries = sliceToWindow(regs.series, win);
  const regFootnotes = resolveFootnotes(doc, [regs.footnote_ids]);
  const classFootnotes = roll ? resolveFootnotes(doc, [roll.user_classes.footnote_ids]) : [];

  return (
    <div>
      {intro}
      <div className="space-y-4">
        {roll ? (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiTile label="Active students" cell={roll.totals.active_students} floorN={doc.privacy_floor_n} />
            <KpiTile label="Messages" cell={roll.totals.messages} floorN={doc.privacy_floor_n} />
            <KpiTile label="Sessions" cell={roll.totals.sessions} floorN={doc.privacy_floor_n} />
            <KpiTile label="New registrations" cell={roll.totals.new_registrations} floorN={doc.privacy_floor_n} />
          </div>
        ) : (
          <WindowGap what="adoption totals" windowLabel={win.label} />
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard
            title="New registrations per week"
            markers={symbolsFor(regFootnotes, regs.footnote_ids)}
            footnotes={regFootnotes}
            suppressionKey={
              hasSuppressed(regEntries) ? "Gray baseline marks are suppressed weeks" : null
            }
            floorN={doc.privacy_floor_n}
            table={
              <DataTable
                caption="New registrations per week"
                head={["Week", "Registrations"]}
                rows={trendTableRows([
                  { id: "reg", label: "Registrations", color: "", entries: regEntries },
                ])}
              />
            }
          >
            <TrendChart
              series={[
                {
                  id: "reg",
                  label: "Registrations",
                  color: "var(--color-accent)",
                  entries: regEntries,
                },
              ]}
              floorN={doc.privacy_floor_n}
            />
          </ChartCard>

          {roll ? (
            <ChartCard
              title="User classes"
              markers={symbolsFor(classFootnotes, roll.user_classes.footnote_ids)}
              footnotes={classFootnotes}
              floorN={doc.privacy_floor_n}
            >
              <div className="flex h-full flex-wrap items-center gap-x-12 gap-y-6 py-4">
                <ClassStat label="one-time" cell={roll.user_classes.one_time} floorN={doc.privacy_floor_n} />
                <ClassStat label="monthly" cell={roll.user_classes.monthly} floorN={doc.privacy_floor_n} />
                <ClassStat label="sporadic" cell={roll.user_classes.sporadic} floorN={doc.privacy_floor_n} />
              </div>
            </ChartCard>
          ) : (
            <WindowGap what="user-class" windowLabel={win.label} />
          )}
        </div>
      </div>
    </div>
  );
}

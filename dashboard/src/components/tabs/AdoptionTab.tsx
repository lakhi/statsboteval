import type { OkCell, SuppressedCell, UsageContextByStatus } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import { sliceToWindow } from "@/lib/windows";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { SectionPending, WindowGap } from "../cells/EmptyState";
import { KpiPairTile, KpiTile } from "../cells/KpiTile";
import { TrendChart, trendTableRows } from "../cells/TrendChart";
import {
  hasSuppressed,
  PanelIntro,
  STATUS_LABELS,
  STATUS_ORDER,
  type TabProps,
} from "./shared";

function ClassStat({
  label,
  cell,
  floorN,
  sub,
}: {
  label: string;
  cell: OkCell | SuppressedCell | null | undefined;
  floorN: number;
  /** Marks a count that is a subset of another, so nobody adds it to the row. */
  sub?: boolean;
}) {
  return (
    <div>
      {cell == null ? (
        <div className="text-2xl font-semibold text-ink-3">·</div>
      ) : cell.status === "ok" ? (
        <div className={`text-2xl font-semibold ${sub ? "text-ink-2" : "text-ink"}`}>
          {formatCount(cell.value)}
        </div>
      ) : (
        <div className="text-2xl font-semibold text-suppressed" title={`suppressed (< ${floorN} students)`}>
          —
        </div>
      )}
      <div className="mt-0.5 text-xs text-ink-2">{label}</div>
    </div>
  );
}

/** One program level: the two counts an educator compares across levels. */
function StatusRow({
  label,
  entry,
  floorN,
}: {
  label: string;
  entry: UsageContextByStatus;
  floorN: number;
}) {
  const cell = (c: OkCell | SuppressedCell) =>
    c.status === "ok" ? (
      formatCount(c.value)
    ) : (
      <span className="text-suppressed" title={`suppressed (< ${floorN} students)`}>
        —
      </span>
    );
  return (
    <tr className="border-t border-hairline">
      <th scope="row" className="py-1.5 pr-3 text-left font-normal text-ink-2">
        {label}
      </th>
      <td className="py-1.5 pr-3 text-right font-semibold tabular-nums text-ink">
        {cell(entry.active_students)}
      </td>
      <td className="py-1.5 text-right font-semibold tabular-nums text-ink">{cell(entry.messages)}</td>
    </tr>
  );
}

export function AdoptionTab({ doc, win }: TabProps) {
  const intro = (
    <PanelIntro
      question="Who uses StatsBot, and how much?"
      deck="Adoption for the selected window: cohort totals, new signups, program levels, and the Bergmann-comparable user classes."
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
  const totalsFootnotes = roll ? resolveFootnotes(doc, [roll.totals.footnote_ids]) : [];
  const byStatus = roll?.by_status;
  const statusKeys = byStatus ? STATUS_ORDER.filter((key) => key in byStatus) : [];
  const statusFootnotes = byStatus
    ? resolveFootnotes(doc, [byStatus[statusKeys[0]]?.footnote_ids])
    : [];

  return (
    <div>
      {intro}
      <div className="space-y-4">
        {roll ? (
          <div>
            <div className="grid grid-cols-2 items-start gap-3 lg:grid-cols-4">
              {/* Retention sits under the total it decomposes, not beside it: the pair is
                  a breakdown of Active users, and reading it as a fifth headline number
                  would double-count the same people. */}
              <div className="space-y-3">
                <KpiTile label="Active users" cell={roll.totals.active_students} floorN={doc.privacy_floor_n} />
                <KpiPairTile
                  label="Of those"
                  markers={symbolsFor(totalsFootnotes, ["retention_definition"])}
                  floorN={doc.privacy_floor_n}
                  rows={[
                    { caption: "new", cell: roll.totals.new_users },
                    { caption: "returning", cell: roll.totals.returning_users },
                  ]}
                />
              </div>
              <KpiTile
                label="Messages"
                cell={roll.totals.messages}
                floorN={doc.privacy_floor_n}
                note="1 msg = 1 user + 1 LLM response"
              />
              <KpiTile label="Sessions" cell={roll.totals.sessions} floorN={doc.privacy_floor_n} />
              <KpiPairTile
                label="New signups"
                markers={symbolsFor(totalsFootnotes, ["signup_activation"])}
                floorN={doc.privacy_floor_n}
                rows={[
                  { caption: "signed up", cell: roll.totals.new_registrations },
                  { caption: "sent at least 1 msg", cell: roll.totals.new_registrations_active },
                ]}
              />
            </div>
            {totalsFootnotes.length > 0 ? (
              <p className="mt-2 text-xs leading-relaxed text-ink-2">
                <span className="font-display italic">Note.</span>{" "}
                {totalsFootnotes.map((f) => (
                  <span key={f.id}>
                    <sup className="text-accent-deep">{f.symbol}</sup> {f.text}{" "}
                  </span>
                ))}
              </p>
            ) : null}
          </div>
        ) : (
          <WindowGap what="adoption totals" windowLabel={win.label} />
        )}

        {/* items-start: the right column now stacks two cards, and stretching the chart
            card to match left a tall empty gutter under the plot. */}
        <div className="grid items-start gap-4 lg:grid-cols-2">
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
            <div className="space-y-4">
              <ChartCard
                title="User classes"
                markers={symbolsFor(classFootnotes, roll.user_classes.footnote_ids)}
                footnotes={classFootnotes}
                floorN={doc.privacy_floor_n}
              >
                <div className="flex flex-wrap items-center gap-x-10 gap-y-5 py-2">
                  <ClassStat label="one-time" cell={roll.user_classes.one_time} floorN={doc.privacy_floor_n} />
                  <ClassStat label="monthly" cell={roll.user_classes.monthly} floorN={doc.privacy_floor_n} />
                  <ClassStat label="sporadic" cell={roll.user_classes.sporadic} floorN={doc.privacy_floor_n} />
                  {/* Dimmed and last: a subset of monthly, so it must not read as a fourth
                      column of the partition. */}
                  <ClassStat
                    label="frequent (of monthly)"
                    cell={roll.user_classes.frequent}
                    floorN={doc.privacy_floor_n}
                    sub
                  />
                </div>
              </ChartCard>

              {byStatus && statusKeys.length > 0 ? (
                <ChartCard
                  title="By program level"
                  markers={symbolsFor(statusFootnotes, byStatus[statusKeys[0]]?.footnote_ids)}
                  footnotes={statusFootnotes}
                  floorN={doc.privacy_floor_n}
                >
                  <table className="w-full border-collapse text-xs">
                    <caption className="sr-only">
                      Active users and messages by program level, {win.label}
                    </caption>
                    <thead>
                      <tr className="text-ink-2">
                        <th scope="col" className="pb-1 text-left font-normal">
                          Level
                        </th>
                        <th scope="col" className="pb-1 pr-3 text-right font-normal">
                          Active users
                        </th>
                        <th scope="col" className="pb-1 text-right font-normal">
                          Messages
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {statusKeys.map((key) => (
                        <StatusRow
                          key={key}
                          label={STATUS_LABELS[key]}
                          entry={byStatus[key]}
                          floorN={doc.privacy_floor_n}
                        />
                      ))}
                    </tbody>
                  </table>
                </ChartCard>
              ) : null}
            </div>
          ) : (
            <WindowGap what="user-class" windowLabel={win.label} />
          )}
        </div>
      </div>
    </div>
  );
}

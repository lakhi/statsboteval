import type {
  OkCell,
  SuppressedCell,
  UsageContextByStatus,
  UserClasses,
} from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import { ALL, enrolledFor, reachPercent, sharePercent } from "@/lib/levels";
import { ChartCard } from "../cells/ChartCard";
import { LevelGap, SectionPending, WindowGap } from "../cells/EmptyState";
import { KpiPairTile, KpiTile } from "../cells/KpiTile";
import { ProgramLevelCard, type LevelColumn } from "../cells/ProgramLevelCard";
import {
  cellText,
  levelsIn,
  PanelIntro,
  showsLevelCard,
  STATUS_LABELS,
  UnscopedNote,
  valueOf,
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

function UserClassRow({ classes, floorN }: { classes: UserClasses; floorN: number }) {
  return (
    <div className="flex flex-wrap items-center gap-x-10 gap-y-5 py-2">
      <ClassStat label="one-time" cell={classes.one_time} floorN={floorN} />
      <ClassStat label="monthly" cell={classes.monthly} floorN={floorN} />
      <ClassStat label="sporadic" cell={classes.sporadic} floorN={floorN} />
      {/* Dimmed and last: a subset of monthly, so it must not read as a fourth
          column of the partition. */}
      <ClassStat label="frequent (of monthly)" cell={classes.frequent} floorN={floorN} sub />
    </div>
  );
}

export function AdoptionTab({ doc, win, level }: TabProps) {
  const intro = (
    <PanelIntro
      question="Who uses StatsBot, and how much?"
      deck="Adoption for the selected window: cohort totals, how many came back, and the Bergmann-comparable user classes."
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
  // The generated types carry an index signature, so a level slice read straight off the
  // map widens to `unknown`. Naming the type once here is what keeps every member access
  // below typed.
  const byStatus = roll?.by_status as Record<string, UsageContextByStatus> | undefined;
  const levels = levelsIn(byStatus);
  // A document with no split at all (pre-1.4.0, or no roster) cannot answer by level, so
  // the cohort-wide rollup is shown and said to be cohort-wide. Only a level missing from
  // a split that IS published is a measured absence.
  const unscoped = level !== ALL && (byStatus === undefined || Object.keys(byStatus).length === 0);
  const slice = level === ALL || unscoped ? undefined : byStatus?.[level];

  if (!roll) {
    return (
      <div>
        {intro}
        <WindowGap what="adoption totals" windowLabel={win.label} />
      </div>
    );
  }
  if (level !== ALL && !unscoped && !slice) {
    return (
      <div>
        {intro}
        <LevelGap levelLabel={STATUS_LABELS[level] ?? level} windowLabel={win.label} />
      </div>
    );
  }

  // The cohort-wide rollup nests its measures under `totals`; a level slice publishes the
  // same measures at its own top level. Normalising to one shape here keeps every tile
  // below from carrying its own `level === ALL ?` branch — ten branches would be ten
  // places for the two paths to drift, and drift there reads as a rendering bug rather
  // than a data one.
  const totals = slice
    ? {
        active_students: slice.active_students,
        messages: slice.messages,
        sessions: slice.sessions,
        new_users: slice.new_users,
        returning_users: slice.returning_users,
      }
    : roll.totals;
  const userClasses = slice ? slice.user_classes : roll.user_classes;
  const totalsFootnotes = resolveFootnotes(doc, [
    roll.totals.footnote_ids,
    byStatus?.[levels[0]]?.footnote_ids,
  ]);
  const classFootnotes = resolveFootnotes(doc, [roll.user_classes.footnote_ids]);
  const statusFootnotes = resolveFootnotes(doc, [["status_rule", "status_multi"]]);

  // Reach: active students over the enrolled cohort. Not a floored cell on either side —
  // the numerator is published and the denominator is an institutional headcount — so it
  // renders only when both actually exist, and only for a single level (BA + MA enrolled
  // is not a denominator for a numerator that includes staff).
  const enrolled = enrolledFor(doc, win, level);
  const activeValue = valueOf(totals.active_students);
  const reach =
    enrolled !== null && activeValue !== null ? reachPercent(activeValue, enrolled) : null;
  const enrollmentFootnotes = resolveFootnotes(doc, [["enrollment_source", "enrollment_scope"]]);

  const windowActive = valueOf(roll.totals.active_students);
  const windowMessages = valueOf(roll.totals.messages);
  const levelColumns: LevelColumn[] = [
    { header: "Level", align: "left", cell: () => null },
    {
      header: "Active users",
      cell: (l) => cellText(byStatus?.[l]?.active_students, doc.privacy_floor_n),
    },
    {
      header: "% of window",
      cell: (l) => {
        const v = valueOf(byStatus?.[l]?.active_students);
        return v === null ? null : (sharePercent(v, windowActive) ?? null);
      },
    },
    {
      header: "Messages",
      cell: (l) => cellText(byStatus?.[l]?.messages, doc.privacy_floor_n),
    },
    {
      header: "% of window",
      cell: (l) => {
        const v = valueOf(byStatus?.[l]?.messages);
        return v === null ? null : (sharePercent(v, windowMessages) ?? null);
      },
    },
    {
      // Reach only exists for the two enrolled levels; staff and unknown render a dot.
      header: "Reach",
      cell: (l) => {
        const active = valueOf(byStatus?.[l]?.active_students);
        const cohort = enrolledFor(doc, win, l);
        return active !== null && cohort !== null ? reachPercent(active, cohort) : null;
      },
    },
  ];
  const enrollmentEntry = doc.enrollment?.per_window?.[win.id];

  return (
    <div>
      {intro}
      {unscoped ? (
        <UnscopedNote>
          This data release does not break Adoption down by program level, so the figures
          below cover every level. Republishing with a current pipeline fills them in.
        </UnscopedNote>
      ) : null}
      <div className="space-y-4">
        <div>
          <div className="grid grid-cols-2 items-start gap-3 lg:grid-cols-4">
            {/* Retention sits under the total it decomposes, not beside it: the pair is
                a breakdown of Active users, and reading it as a fifth headline number
                would double-count the same people. */}
            <div className="space-y-3">
              <KpiTile
                label="Active users"
                cell={totals.active_students}
                floorN={doc.privacy_floor_n}
                note={
                  reach && enrolled !== null
                    ? `${reach} of ${formatCount(enrolled)} enrolled ${
                        (STATUS_LABELS[level] ?? level).toLowerCase()
                      } students`
                    : undefined
                }
              />
              <KpiPairTile
                label="Of those"
                markers={symbolsFor(totalsFootnotes, ["retention_definition"])}
                floorN={doc.privacy_floor_n}
                rows={[
                  { caption: "new", cell: totals.new_users },
                  { caption: "returning", cell: totals.returning_users },
                ]}
              />
            </div>
            <KpiTile
              label="Messages"
              cell={totals.messages}
              floorN={doc.privacy_floor_n}
              note="1 msg = 1 user + 1 LLM response"
            />
            <KpiTile label="Sessions" cell={totals.sessions} floorN={doc.privacy_floor_n} />
            {/* New signups is cohort-wide by construction: a registration has no session,
                so the usage-time rule cannot resolve its program level (D-55). Rather than
                show an unscoped number under a level filter, the tile steps aside — the
                same treatment the semester overlay gets on Timing. */}
            {level === ALL ? (
              <KpiPairTile
                label="New signups"
                markers={symbolsFor(totalsFootnotes, ["signup_activation"])}
                floorN={doc.privacy_floor_n}
                rows={[
                  { caption: "signed up", cell: roll.totals.new_registrations },
                  { caption: "sent at least 1 msg", cell: roll.totals.new_registrations_active },
                ]}
              />
            ) : (
              <div className="rounded-lg border border-dashed border-edge px-4 py-3 text-xs leading-relaxed text-ink-3">
                <span className="font-medium text-ink-2">New signups</span> counts accounts
                created in this window. A signup has no conversation behind it, so it cannot
                be attributed to a program level — switch to All users to see it.
              </div>
            )}
          </div>
          {totalsFootnotes.length > 0 ? (
            <p className="mt-2 text-xs leading-relaxed text-ink-2">
              <span className="font-display italic">Note.</span>{" "}
              {totalsFootnotes.map((f) => (
                <span key={f.id}>
                  <sup className="text-accent-deep">{f.symbol}</sup> {f.text}{" "}
                </span>
              ))}
              {reach ? (
                <span>
                  {enrollmentFootnotes.map((f) => (
                    <span key={f.id}>{f.text} </span>
                  ))}
                </span>
              ) : null}
            </p>
          ) : null}
        </div>

        <div className="grid items-start gap-4 lg:grid-cols-2">
          {userClasses ? (
            <ChartCard
              title="User classes"
              markers={symbolsFor(classFootnotes, roll.user_classes.footnote_ids)}
              footnotes={classFootnotes}
              floorN={doc.privacy_floor_n}
            >
              <UserClassRow classes={userClasses} floorN={doc.privacy_floor_n} />
            </ChartCard>
          ) : null}

          {showsLevelCard(level) && levels.length > 0 ? (
            <ProgramLevelCard
              title="By program level"
              tableCaption={`Active users, messages and reach by program level, ${win.label}`}
              levels={levels}
              columns={levelColumns}
              floorN={doc.privacy_floor_n}
              markers={symbolsFor(statusFootnotes, ["status_rule", "status_multi"])}
              footnotes={statusFootnotes}
              note={
                <>
                  <span className="font-medium">% of window</span> is the level&rsquo;s share of
                  this window&rsquo;s total.{" "}
                  {enrollmentEntry ? (
                    <>
                      <span className="font-medium">Reach</span> is its active users over its
                      enrolled cohort ({formatCount(enrollmentEntry.bachelor)} bachelor,{" "}
                      {formatCount(enrollmentEntry.master)} master).{" "}
                      {enrollmentFootnotes.map((f) => f.text).join(" ")}
                    </>
                  ) : (
                    <>
                      <span className="font-medium">Reach</span> needs an enrolled-cohort total,
                      which is published for semester windows only.
                    </>
                  )}
                </>
              }
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

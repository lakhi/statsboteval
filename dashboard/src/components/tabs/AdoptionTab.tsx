import type {
  OkCell,
  SuppressedCell,
  UsageContextByStatus,
  UserClasses,
} from "@/lib/aggregates.gen";
import { footnoteText, footnoteTexts, resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import {
  ALL,
  enrolledFor,
  enrollmentFor,
  LEVEL_COLORS,
  reachFootnoteIds,
  reachPercent,
  sharePercent,
} from "@/lib/levels";
import { ChartCard } from "../cells/ChartCard";
import { LevelGap, SectionPending, WindowGap } from "../cells/EmptyState";
import { InfoTip } from "../cells/InfoTip";
import { KpiPairTile, KpiTile } from "../cells/KpiTile";
import { NoteText } from "../cells/NoteText";
import { PieShare } from "../cells/PieShare";
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
      deck="Adoption for the selected window: cohort totals, how many came back, and frequency-based user classes."
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
        new_registrations: slice.new_registrations,
        new_registrations_active: slice.new_registrations_active,
      }
    : roll.totals;
  const userClasses = slice ? slice.user_classes : roll.user_classes;
  const classFootnotes = resolveFootnotes(doc, [roll.user_classes.footnote_ids]);
  const statusFootnotes = resolveFootnotes(doc, [["status_rule", "status_multi"]]);

  // D-58: the totals block has no shared Note paragraph any more, so there is nothing for
  // an APA symbol to point at — each caveat is rendered inside the cell it explains. Two
  // conditions gate a text: the *document* must carry the id (`footnoteText` → null
  // otherwise, for the bundle-before-blob deploy gap) and *this window* must reference it.
  // The second is what keeps `retention_all_time` off the semester windows: the pipeline
  // decides where the caveat applies, because it is the side that knows the window kind.
  const totalsIds = new Set(roll.totals.footnote_ids ?? []);
  const windowNote = (id: string) => (totalsIds.has(id) ? footnoteText(doc, id) : null);
  const retentionNote = windowNote("retention_definition");
  const retentionAllTimeNote = windowNote("retention_all_time");
  const signupNote = windowNote("signup_activation");
  const sessionsNote = windowNote("chat_fragmentation");
  // D-59 takes the `status_rule` tip off Active users, one day after D-58 put it there.
  // Three statements of the same roster rule fit on one screen under a level filter, and
  // the tile's own second line already carries a tip. The rule stays on the
  // By-program-level card, where the levels are the subject rather than the scope.
  //
  // 1.9.0: the signup pair is published per level (D-59), so the tile follows the filter
  // like every other number on this tab. `signup_level_rule` says what "per level" means
  // for a number that has no conversation behind it, and it arrives on the slice.
  const sliceIds = new Set(slice?.footnote_ids ?? []);
  const signupLevelNote = sliceIds.has("signup_level_rule")
    ? footnoteText(doc, "signup_level_rule")
    : null;

  // Reach: active students over the enrolled cohort. Not a floored cell on either side —
  // the numerator is published and the denominator is an institutional headcount — so it
  // renders only when both actually exist, and only for a single level (BA + MA enrolled
  // is not a denominator for a numerator that includes staff).
  const enrolled = enrolledFor(doc, win, level);
  const activeValue = valueOf(totals.active_students);
  const reach =
    enrolled !== null && activeValue !== null ? reachPercent(activeValue, enrolled) : null;
  const enrollmentNotes = footnoteTexts(doc, reachFootnoteIds(win));

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
  const enrollmentEntry = enrollmentFor(doc, win);

  // The donut under the level table (D-59). Denominator is the sum of the published
  // levels, NOT the window total: a BA→MA transitioner is counted under both levels
  // (`status_multi`), so the levels can add up past the window by a few, and a pie drawn
  // against the window total would over-fill. Drawn against their own sum it is exact,
  // and the card says which sum it is.
  //
  // Suppression is all-or-nothing: one withheld level and there is no donut, because a
  // ring over the survivors would show them as the whole cohort. The table above keeps
  // every publishable number visible either way, so nothing is lost but the picture.
  const levelSlices = levels.map((l) => ({
    key: l,
    label: STATUS_LABELS[l] ?? l,
    value: valueOf(byStatus?.[l]?.active_students),
    color: LEVEL_COLORS[l] ?? LEVEL_COLORS.unknown,
  }));
  const levelDonut = levelSlices.every((s) => s.value !== null)
    ? (levelSlices as { key: string; label: string; value: number; color: string }[])
    : null;
  const donutTotal = levelDonut?.reduce((sum, s) => sum + s.value, 0) ?? 0;

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
        {/* First block on the tab, above the totals it decomposes (D-59, owner's call).
            It renders under All users only, so under a level filter the KPI row leads the
            page instead — the layout differs by filter, on purpose. */}
        {showsLevelCard(level) && levels.length > 0 ? (
          <ProgramLevelCard
            title="By program level"
            tableCaption={`Active users, messages and reach by program level, ${win.label}`}
            levels={levels}
            columns={levelColumns}
            floorN={doc.privacy_floor_n}
            markers={symbolsFor(statusFootnotes, ["status_rule", "status_multi"])}
            footnotes={statusFootnotes}
            // The card's own figure is already an accessible <table> with a caption, so
            // the collapsible twin was these numbers a third time (D-59). The only card
            // on the dashboard where that is true.
            showTable={false}
            footer={
              levelDonut ? (
                <PieShare
                  slices={levelDonut}
                  total={donutTotal}
                  centerLabel="active users across the levels shown"
                  valueLabel="Active users"
                  ariaLabel={`Active users by program level, ${win.label}: ${levelDonut
                    .map((s) => `${s.label} ${formatCount(s.value)}`)
                    .join(", ")}.`}
                />
              ) : null
            }
            note={
              <>
                <span className="font-medium">% of window</span> is the level&rsquo;s share of
                this window&rsquo;s total.{" "}
                {enrollmentEntry ? (
                  <>
                    <span className="font-medium">Reach</span> is its active users over its
                    enrolled cohort ({formatCount(enrollmentEntry.bachelor)} bachelor,{" "}
                    {formatCount(enrollmentEntry.master)} master).{" "}
                    {enrollmentNotes.map((text, i) => (
                      <span key={i}>
                        <NoteText text={text} />{" "}
                      </span>
                    ))}
                  </>
                ) : (
                  <>
                    <span className="font-medium">Reach</span> needs an enrolled-cohort total.{" "}
                    {win.kind === "all_time"
                      ? "All time spans several semesters of cohort turnover, so no single headcount is its denominator."
                      : "None is published for this semester yet."}
                  </>
                )}{" "}
                {levelDonut
                  ? "The ring reads the Active users column against the levels shown, which is a hair more than the window total wherever a student changed level inside it."
                  : "One level's count is withheld here, so the ring is left out rather than drawn over the rest."}
              </>
            }
          />
        ) : null}

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
                  reach && enrolled !== null ? (
                    <>
                      {reach} of {formatCount(enrolled)} enrolled{" "}
                      {(STATUS_LABELS[level] ?? level).toLowerCase()} students
                      {/* The denominator's provenance and scope, not its definition:
                          three sentences that would bury the percentage they qualify. */}
                      {enrollmentNotes.length > 0 ? (
                        <InfoTip label="Where the enrolled total comes from">
                          {enrollmentNotes.map((text, i) => (
                            <span key={i} className={i > 0 ? "mt-2 block" : "block"}>
                              <NoteText text={text} />
                            </span>
                          ))}
                        </InfoTip>
                      ) : null}
                    </>
                  ) : undefined
                }
              />
              <KpiPairTile
                label="Of those"
                floorN={doc.privacy_floor_n}
                rows={[
                  { caption: "new", cell: totals.new_users },
                  { caption: "returning", cell: totals.returning_users },
                ]}
                note={
                  retentionNote || retentionAllTimeNote ? (
                    <>
                      {retentionNote ? <NoteText text={retentionNote} /> : null}
                      {/* All-time only, and published that way: on every other window
                          this line is simply absent from the document (D-58). */}
                      {retentionAllTimeNote ? (
                        <span className="mt-1.5 block">
                          <NoteText text={retentionAllTimeNote} />
                        </span>
                      ) : null}
                    </>
                  ) : undefined
                }
              />
            </div>
            <KpiTile
              label="Messages"
              cell={totals.messages}
              floorN={doc.privacy_floor_n}
              note="1 msg = 1 user + 1 LLM response"
            />
            <KpiTile
              label="Sessions"
              cell={totals.sessions}
              floorN={doc.privacy_floor_n}
              note={
                <>
                  1 session = one chat started
                  {sessionsNote ? (
                    <InfoTip label="How session counts should be read">
                      <NoteText text={sessionsNote} />
                    </InfoTip>
                  ) : null}
                </>
              }
            />
            {/* Follows the filter since 1.9.0 (D-59). A pre-1.9.0 document has no signup
                cells on its slices, so under a level filter the pair is simply absent —
                `KpiPairTile` renders the dot for a missing cell, and the tile does not
                claim a zero it was never told. */}
            <KpiPairTile
              label="New signups"
              floorN={doc.privacy_floor_n}
              rows={[
                { caption: "signed up", cell: totals.new_registrations },
                { caption: "sent at least 1 msg", cell: totals.new_registrations_active },
              ]}
              note={
                signupNote || signupLevelNote ? (
                  <>
                    {signupNote ? <NoteText text={signupNote} /> : null}
                    {/* Only under a single level: the rule it states is what "bachelor
                        signups" means, and under All users no level is claimed. */}
                    {signupLevelNote ? (
                      <InfoTip label="How a signup's program level is decided">
                        <NoteText text={signupLevelNote} />
                      </InfoTip>
                    ) : null}
                  </>
                ) : undefined
              }
            />
          </div>
          {/* No Note paragraph here since D-58: 92 words under four unrelated numbers is
              a paragraph nobody reads, and the reader who wants one of the four explained
              had to find their sentence inside the other three. Each caveat now renders in
              its own cell. The two cards keep theirs — one paragraph serving one figure
              is exactly what an APA table note is for. */}
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
        </div>
      </div>
    </div>
  );
}

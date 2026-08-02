import type { OkCell, SuppressedCell, UsageContextByStatus } from "@/lib/aggregates.gen";
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
import { LevelGap, SectionPending, WindowGap } from "../cells/EmptyState";
import { InfoTip } from "../cells/InfoTip";
import { KpiPairTile, KpiTile } from "../cells/KpiTile";
import { NoteText } from "../cells/NoteText";
import { ProgramLevelCard, type LevelColumn } from "../cells/ProgramLevelCard";
import { StackedShareBars } from "../cells/StackedShareBars";
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

export function AdoptionTab({ doc, win, level }: TabProps) {
  const intro = (
    <PanelIntro
      question="Who uses StatsBot, and how much?"
      deck="Adoption for the selected window: cohort totals, how the levels compare, and how many came back."
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

  // Data-table text for a count cell: the number, "suppressed", or nothing measured.
  const countText = (cell: OkCell | SuppressedCell | null | undefined) =>
    cell == null ? "·" : cell.status === "suppressed" ? "suppressed" : formatCount(cell.value);

  const windowActive = valueOf(roll.totals.active_students);
  const windowMessages = valueOf(roll.totals.messages);
  const levelColumns: LevelColumn[] = [
    { header: "Level", align: "left", cell: () => null },
    {
      header: "Active users",
      cell: (l) => cellText(byStatus?.[l]?.active_students, doc.privacy_floor_n),
      // The disclosure is this card's only text channel since D-62; `textOf`'s bare em
      // dash for a rich cell would be the sole rendering of a withheld number, with no
      // key anywhere to say it is not a zero.
      text: (l) => countText(byStatus?.[l]?.active_students),
    },
    {
      // Named for its numerator, not just its denominator (D-62). Two bare "% of window"
      // columns were legible beside the counts they followed in the visible table; in the
      // data table — which is this card's only text channel now — they are two
      // identically-labelled columns and the reader has no way to tell which is which.
      header: "% of window (users)",
      cell: (l) => {
        const v = valueOf(byStatus?.[l]?.active_students);
        return v === null ? null : (sharePercent(v, windowActive) ?? null);
      },
    },
    {
      header: "Messages",
      cell: (l) => cellText(byStatus?.[l]?.messages, doc.privacy_floor_n),
      text: (l) => countText(byStatus?.[l]?.messages),
    },
    {
      header: "% of window (messages)",
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

  // The card's figure since D-62: one 100%-stacked column per measure, split by level.
  // Two columns rather than the D-59 donut's one, because the interesting sentence on this
  // card is the *difference* between the two compositions — bachelor is 50% of the active
  // users and 52% of the messages — and a ring can only ever show one of them. (A single
  // stacked column would also be a one-bar bar chart, which is a stat tile wearing a
  // costume.)
  //
  // Denominator is the sum of the published levels, NOT the window total: a BA→MA
  // transitioner is counted under both levels (`status_multi`), so the levels can add up
  // past the window by a few and a column drawn against the window total would overfill.
  //
  // All-or-nothing per column, for `PieShare`'s rule 1: one withheld level and the
  // survivors would fill the column, asserting the withheld one is zero. `messages` cannot
  // reach that state anyway — `_joint_partition_floor` withholds it on every level once it
  // is withheld on one — but `active_students` is exempt from that joint floor, so it can,
  // and this is the branch that keeps it honest.
  const levelSeries = levels.map((l) => ({
    key: l,
    label: STATUS_LABELS[l] ?? l,
    color: LEVEL_COLORS[l] ?? LEVEL_COLORS.unknown,
  }));
  const anyLevelSuppressed = (["active_students", "messages"] as const).some((measure) =>
    levels.some((l) => byStatus?.[l]?.[measure]?.status === "suppressed"),
  );
  const measureGroup = (measure: "active_students" | "messages", label: string) => {
    const cells = Object.fromEntries(
      levels.map((l) => {
        const cell = byStatus?.[l]?.[measure];
        return [l, { value: valueOf(cell), suppressed: cell?.status === "suppressed" }];
      }),
    );
    const values = levels.map((l) => cells[l].value);
    const total = values.every((v) => v !== null)
      ? (values as number[]).reduce((sum, v) => sum + v, 0)
      : null;
    return {
      key: measure,
      label,
      total,
      cells,
      unavailable: "withheld",
      // Per column, because the two columns count different things. One noun for the whole
      // figure produced "Active users · Bachelor: 66 of the levels shown (50%)".
      valueNoun: measure === "messages" ? "messages" : "active users",
    };
  };

  // Reach rides under the columns rather than inside one: it is a ratio against an outside
  // denominator (the enrolled cohort), not a share of anything on this card, so it has no
  // column to belong to — and under All users this card is the only place it appears at
  // all. Same strip idiom as Timing's weekday/weekend pair, for the same reason.
  const reachRows = levels.flatMap((l) => {
    const active = valueOf(byStatus?.[l]?.active_students);
    const cohort = enrolledFor(doc, win, l);
    return active !== null && cohort !== null
      ? [{ key: l, label: STATUS_LABELS[l] ?? l, pct: reachPercent(active, cohort) }]
      : [];
  });

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
            // Columns where they can be drawn, the shared table where they cannot — the
            // same fallback Timing's daypart ring keeps, for the same reason. A withheld
            // level makes the sum of the published levels the wrong denominator for BOTH
            // columns, so the figure would go blank and the levels that ARE published would
            // survive only inside a collapsed disclosure. That is the window a reader most
            // needs the numbers in. `showTable={false}` then applies to the fallback, where
            // D-59's argument still holds exactly: the card's figure IS an accessible table.
            showTable={false}
            figure={
              anyLevelSuppressed ? undefined : (
              <StackedShareBars
                groups={[
                  measureGroup("active_students", "Active users"),
                  measureGroup("messages", "Messages"),
                ]}
                series={levelSeries}
                valueNoun="students"
                ariaLabel={`Active users and messages by program level, ${win.label}. Each column is split into the levels shown; every count and share is in the data table below.`}
                footer={
                  reachRows.length > 0 ? (
                    <div className="mt-4 flex flex-wrap justify-center gap-x-6 gap-y-1 border-t border-hairline pt-2 text-xs text-ink-2">
                      <span className="text-ink-3">Reach</span>
                      {reachRows.map((row) => (
                        <span key={row.key}>
                          {row.label}{" "}
                          <span className="font-semibold tabular-nums text-ink">{row.pct}</span>
                        </span>
                      ))}
                    </div>
                  ) : null
                }
              />
              )
            }
            note={
              <>
                {anyLevelSuppressed
                  ? "One level's count is withheld here, so the sum of the published levels is not this window's whole and the figures are shown as a table rather than as columns drawn over the rest. "
                  : "Each column is drawn against the levels shown, which is a hair more than the window total wherever a student changed level inside it. Counts, and each level's share of the window total, are in the data table below. "}
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
                )}
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

        {/* The User classes card was here until D-62 (one-time / monthly / sporadic /
            frequent). Taken off the page, not out of the pipeline: `user_classes` is still
            aggregated, still published, still governed by the `frequent ⊂ monthly`
            invariant, and the schema does not move — what happens to the measure itself is
            a separate decision. Restoring the card is a revert of this commit, not a
            re-aggregation. */}
      </div>
    </div>
  );
}

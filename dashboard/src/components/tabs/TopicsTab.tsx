"use client";

import { type ReactNode } from "react";
import type { Aggregates, TopicDistribution, TopicGroup, TopicsWindowEntry } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor, type ResolvedFootnote } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import { ALL, sliceByLevel } from "@/lib/levels";
import { CategoryBars, categoryTableRows, type CategoryRow } from "../cells/CategoryBars";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { LevelGap, SectionPending, WindowGap } from "../cells/EmptyState";
import { NoteText } from "../cells/NoteText";
import { ProgramLevelCard, type LevelColumn } from "../cells/ProgramLevelCard";
import {
  levelsIn,
  PanelIntro,
  showsLevelCard,
  STATUS_LABELS,
  UnscopedNote,
  valueOf,
  type TabProps,
} from "./shared";

type CardDef = {
  key: keyof TopicGroup & string;
  title: string;
  deck: string;
  /** Singular/plural for tooltip prose, e.g. "theme"/"themes". */
  noun: [string, string];
};

// Order is an editorial decision. Emergent themes still lead — the data-driven answer to
// the tab's question — but the deductive codebook moves from last to second (D-60,
// reversing 2026-07-19): the grid is two columns, so position 2 is the top-right card, and
// the pair a reader meets first is now "what came out of the chats" beside "what a
// published study looked for". That contrast is the tab's argument; the two fixed-list
// cards below it are supporting detail, and demoting them costs nothing because neither is
// a finding on its own.
const CARDS: CardDef[] = [
  {
    key: "emergent_themes",
    title: "Emergent themes",
    deck: "Data-driven themes from the chats themselves (reviewed set).",
    noun: ["theme", "themes"],
  },
  {
    key: "deductive",
    // "Bergmann-style" was doing the attribution work twice, in the title and again in the
    // deck (D-60). The citation now sits in the title, where a reader meets it once — and
    // since D-62 the *purpose* sits only in the deck, for the same reason: D-60 moved the
    // citation up but left "for cross-study validation" in both lines.
    title: "Deductive Categories (from Bergmann et al. 2026)",
    deck: "The 13 predefined codebook categories, included for cross-study validation.",
    noun: ["category", "categories"],
  },
  {
    key: "method_themes",
    title: "Statistical methods",
    deck: "Explicitly named methods (fixed list).",
    noun: ["method", "methods"],
  },
  {
    key: "software_themes",
    title: "Analysis software",
    deck: "Explicitly named software (fixed list).",
    noun: ["software", "software"],
  },
];

/** How this row's number was arrived at — definition (when published) + provenance. */
function rowTip(
  card: CardDef,
  row: CategoryRow,
  ctx: {
    scope: string;
    classifier: string | undefined;
    themeSet: string | null | undefined;
    floorN: number;
  },
): ReactNode {
  const definition =
    row.description ??
    (card.key === "deductive"
      ? "Defined in the Bergmann et al. codebook (public Stage-2 manuscript)."
      : card.key === "emergent_themes"
        ? null
        : `An explicitly named ${card.noun[0]} from the frozen Bergmann et al. list.`);
  const classifier = ctx.classifier ?? "configured classifier";
  const via =
    card.key === "emergent_themes" && ctx.themeSet
      ? `${classifier}, against the reviewed theme set ${ctx.themeSet}`
      : classifier;
  const provenance = row.suppressed
    ? `Fewer than ${ctx.floorN} students in ${ctx.scope} wrote messages the automated classifier ` +
      `(${via}) flagged with this ${card.noun[0]}, so the count is withheld — not zero.`
    : row.value
      ? `${formatCount(row.value)} messages in ${ctx.scope} were flagged with this ${card.noun[0]} ` +
        `by the automated classifier (${via}). A message can carry several ${card.noun[1]}, so counts overlap.`
      : `No messages in ${ctx.scope} were flagged with this ${card.noun[0]} by the automated classifier (${via}).`;
  return (
    <>
      <p className="font-medium text-ink">{row.label}</p>
      {definition ? <p className="mt-1">{definition}</p> : null}
      <p className={definition ? "mt-1.5 border-t border-hairline pt-1.5 text-ink-3" : "mt-1"}>{provenance}</p>
    </>
  );
}

function TopicCard({
  card,
  distribution,
  floorN,
  tabFootnotes,
  note,
  tip,
  suppressionKey = true,
}: {
  card: CardDef;
  distribution: TopicDistribution;
  floorN: number;
  /** Resolved once at tab level; texts render in the tab footer, not per card. */
  tabFootnotes: ResolvedFootnote[];
  note?: ReactNode;
  tip: (row: CategoryRow) => ReactNode;
  /** Off on the two fixed-list cards (D-59), where the note carries provenance instead
   *  and the tick's meaning is still one hover away on its own row (`rowTip` says
   *  "withheld — not zero") and spelled out in the data table. */
  suppressionKey?: boolean;
}) {
  const anySuppressed = distribution.items.some((item) => item.cell.status === "suppressed");
  const nTotal = distribution.n_total;
  return (
    <ChartCard
      title={card.title}
      markers={symbolsFor(tabFootnotes, distribution.footnote_ids)}
      suppressionKey={
        anySuppressed && suppressionKey
          ? "A gray tick instead of a bar is a suppressed category"
          : null
      }
      note={note}
      floorN={floorN}
      table={
        <DataTable
          caption={card.title}
          head={["Label", "Messages", "Share"]}
          rows={categoryTableRows(distribution)}
        />
      }
    >
      <p className="mb-3 text-xs text-ink-3">
        {card.deck}{" "}
        <span className="tabular-nums">
          {nTotal.status === "ok"
            ? `${formatCount(nTotal.value)} messages in this view.`
            : `Message total suppressed (< ${floorN} students).`}
        </span>
      </p>
      <CategoryBars distribution={distribution} floorN={floorN} rowTip={tip} />
    </ChartCard>
  );
}

/**
 * How every number on this tab was produced (D-59), collapsed by default.
 *
 * Every card here is a count of classifier decisions, and until now the only card that
 * said so was the emergent one. Collapsed rather than always-on because it is method,
 * not caveat: nothing here changes how a number should be read, which is the line D-58
 * drew between a visible note and a revealed one.
 *
 * The classifier version is read from the document, and **nothing else about the
 * classifier is stated here** — no model, no seed, no batch size. Those are properties of
 * a *version*, and this block cannot know which one the blob declares: `--classification-
 * version` also accepts `statsboteval-v1` (batch size 50, the documented rollback path)
 * and `bergmann-v1` (Bergmann's own imported labels, a different model run by different
 * people). Interpolating today's settings beside a version string the document owns is
 * how the page ends up confidently describing a run that never happened. Every sentence
 * below is true of any version this dashboard can be pointed at; the version-specific
 * facts live in `docs/decisions.md` (D-41, D-45), which is where a reader who needs the
 * batch size is going anyway.
 */
function ClassifierMethod({ doc }: { doc: Aggregates }) {
  const classifier = doc.label_versions.classification;
  if (!classifier) return null;
  return (
    <details className="mb-6 max-w-2xl text-xs leading-relaxed text-ink-2">
      <summary className="cursor-pointer select-none text-ink-3 hover:text-ink-2">
        How these labels were produced
      </summary>
      <p className="mt-2">
        Every label on this tab is an automated classification (
        <span className="font-mono text-[11px]">{classifier}</span>), not a hand count. Each
        message is judged on its own text — the student&rsquo;s message, not StatsBot&rsquo;s
        reply — and may carry several labels or none. The deductive categories and the
        method and software lists come from Bergmann et al.&rsquo;s published materials; the
        emergent themes were generated from these chats and frozen after review.
      </p>
    </details>
  );
}

/**
 * Where a fixed list came from, on the two cards that show one (D-59).
 *
 * A distinct claim from the `label_provenance` footnote, which names the classifier and
 * says nothing about the list: these 21 methods and 9 tools are Bergmann et al.'s
 * published Stage-2 theme tables, and only the *assignment* is ours. Without this the
 * cards read as our taxonomy, which would misattribute the comparison the whole
 * cross-study validation rests on.
 */
const FIXED_LIST_NOTE =
  "Frozen list from Bergmann et al.'s published materials; labels assigned by our " +
  "classifier where the message names the method explicitly.";

/** The generate→review→freeze story behind the emergent set (D-33/D-43). */
function emergentMethodNote(doc: Aggregates): ReactNode {
  const themeSet = doc.sections.topics?.theme_set_version;
  return (
    <>
      Themes were generated from the chats in a two-stage pass — candidate codes per message,
      synthesized into a draft theme list — then reviewed and frozen as the versioned set{" "}
      {themeSet ? <span className="font-mono text-[11px]">{themeSet}</span> : "behind this card"};
      every message was classified against that frozen set.
    </>
  );
}

export function TopicsTab({ doc, win, level }: TabProps) {
  const intro = (
    <PanelIntro
      question="What do students ask about?"
      deck="Topic distributions over the chat corpus — the question this project exists to answer. Classified locally on the pseudonymized corpus; only privacy-floored counts are published."
    />
  );

  const section = doc.sections.topics;
  const entry: TopicsWindowEntry | undefined = section?.per_window[win.id];
  const levels = levelsIn(entry?.by_status);

  if (!section) {
    return (
      <div>
        {intro}
        <SectionPending what="Topics (the classification pipeline's topics section)" />
      </div>
    );
  }
  if (!entry) {
    return (
      <div>
        {intro}
        <WindowGap what="topics" windowLabel={win.label} />
      </div>
    );
  }

  // The in-panel segmented control that used to live here moved into the header bar as
  // the global filter (D-55). Absence is now a real state: a level with no messages in
  // this window has no group at all, and falling back to the cohort-wide one would show
  // everyone's topics under a bachelor filter.
  const groupSlice = sliceByLevel(entry, entry.by_status, level);
  if (groupSlice === null) {
    return (
      <div>
        {intro}
        <LevelGap levelLabel={STATUS_LABELS[level] ?? level} windowLabel={win.label} />
      </div>
    );
  }
  const group: TopicGroup = groupSlice.data;
  const unscoped = level !== ALL && !groupSlice.scoped;

  // One symbol table for the whole tab: every card's registry footnotes resolve
  // here (identical across cards), render once in the tab footer, and the card
  // titles keep their †/‡ markers pointing at it.
  const tabFootnotes = resolveFootnotes(
    doc,
    CARDS.map((card) => (group[card.key] as TopicDistribution | null | undefined)?.footnote_ids),
  );
  const tipCtx = {
    scope: level === ALL ? win.label : `${win.label} (${STATUS_LABELS[level]} group)`,
    classifier: doc.label_versions.classification,
    themeSet: section.theme_set_version,
    floorN: doc.privacy_floor_n,
  };

  // Themes x levels, each cell that theme's share of its OWN level's messages (D-55).
  // The one comparison the filter genuinely cannot substitute for: flipping between four
  // levels to compare fifteen themes is past what anyone holds in working memory, which
  // is exactly when a facet beats a filter. Within-level denominators because the levels
  // differ in size — a share-of-window column would rank every theme by cohort size.
  const emergentByLevel = (l: string): TopicDistribution | null | undefined =>
    (entry.by_status?.[l] as TopicGroup | undefined)?.emergent_themes;
  const themeLabels = (emergentByLevel(levels[0])?.items ?? []).map((item) => item.label);
  const themeStatusFootnotes = resolveFootnotes(doc, [
    ["status_rule", "status_multi", "multi_label"],
  ]);
  const themeColumns: LevelColumn[] = [
    { header: "Level", align: "left", cell: () => null },
    ...themeLabels.map((label) => ({
      header: label,
      cell: (l: string) => {
        const distribution = emergentByLevel(l);
        const item = distribution?.items.find((i) => i.label === label);
        const value = valueOf(item?.cell);
        const total = valueOf(distribution?.n_total);
        return value === null || total === null || total === 0
          ? null
          : `${Math.round((value / total) * 100)}%`;
      },
    })),
  ];

  return (
    <div>
      {intro}
      <ClassifierMethod doc={doc} />
      {unscoped ? (
        <UnscopedNote>
          This data release does not break Topics down by program level, so the
          distributions below cover every level. Republishing with a current pipeline fills
          them in.
        </UnscopedNote>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        {CARDS.map((card) => {
          const distribution = group[card.key] as TopicDistribution | null | undefined;
          if (card.key === "emergent_themes" && !distribution) {
            return (
              <section key={card.key} className="rounded-lg border border-edge bg-card p-5">
                <h3 className="text-sm font-semibold text-ink">{card.title}</h3>
                <p className="mt-3 font-display text-sm italic text-ink-2">
                  Not in this data release yet.
                </p>
                <p className="mt-1.5 text-xs leading-relaxed text-ink-3">
                  Emergent themes are generated from the chats, reviewed by the operator, and
                  frozen as a versioned set before they can appear here — the view lights up on
                  its own once that set is published.
                </p>
              </section>
            );
          }
          if (!distribution) return null;
          // The two cards whose list is Bergmann's rather than ours (D-59).
          const fixedList = card.key === "method_themes" || card.key === "software_themes";
          return (
            <TopicCard
              key={card.key}
              card={card}
              distribution={distribution}
              floorN={doc.privacy_floor_n}
              tabFootnotes={tabFootnotes}
              note={
                card.key === "emergent_themes"
                  ? emergentMethodNote(doc)
                  : fixedList
                    ? FIXED_LIST_NOTE
                    : undefined
              }
              suppressionKey={!fixedList}
              tip={(row) => rowTip(card, row, tipCtx)}
            />
          );
        })}
      </div>
      {showsLevelCard(level) && levels.length > 0 && themeLabels.length > 0 ? (
        <div className="mt-4 overflow-x-auto">
          <ProgramLevelCard
            title="Emergent themes by program level"
            tableCaption={`Share of each level's messages carrying each emergent theme, ${win.label}`}
            levels={levels}
            columns={themeColumns}
            floorN={doc.privacy_floor_n}
            markers={symbolsFor(themeStatusFootnotes, ["status_rule", "multi_label"])}
            footnotes={themeStatusFootnotes}
            note={
              <>
                Each cell is the theme&rsquo;s share of that level&rsquo;s own messages, so
                levels of different size are directly comparable. A message can carry several
                themes, so a row does not add up to 100%; a suppressed cell is left blank
                rather than shown as zero.
              </>
            }
          />
        </div>
      ) : null}
      {tabFootnotes.length > 0 ? (
        <p className="mt-8 border-t border-hairline pt-3 text-xs leading-relaxed text-ink-2">
          <span className="font-display italic">Notes (all cards).</span>{" "}
          {tabFootnotes.map((f) => (
            <span key={f.id}>
              <sup className="text-accent-deep">{f.symbol}</sup> <NoteText text={f.text} />{" "}
            </span>
          ))}
        </p>
      ) : null}
    </div>
  );
}

"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import type { Aggregates, TopicDistribution, TopicGroup, TopicsWindowEntry } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor, type ResolvedFootnote } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import { CategoryBars, categoryTableRows, type CategoryRow } from "../cells/CategoryBars";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { SectionPending, WindowGap } from "../cells/EmptyState";
import { PanelIntro, type TabProps } from "./shared";

// Closed key set from the contract (D-39); "unknown" appears only when published.
const STATUS_ORDER = ["bachelor", "master", "staff", "unknown"] as const;
const STATUS_LABELS: Record<string, string> = {
  bachelor: "Bachelor",
  master: "Master",
  staff: "Staff",
  unknown: "Unknown",
};

type CardDef = {
  key: keyof TopicGroup & string;
  title: string;
  deck: string;
  /** Singular/plural for tooltip prose, e.g. "theme"/"themes". */
  noun: [string, string];
};

// Order is an editorial decision (2026-07-19): emergent themes lead — the
// data-driven answer to the tab's question — and the deductive codebook moves
// last, kept for cross-study validation.
const CARDS: CardDef[] = [
  {
    key: "emergent_themes",
    title: "Emergent themes",
    deck: "Data-driven themes from the chats themselves (reviewed set).",
    noun: ["theme", "themes"],
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
  {
    key: "deductive",
    title: "Bergmann-style Deductive Categories (for validation)",
    deck: "The 13 predefined Bergmann et al. codebook categories, kept for cross-study validation.",
    noun: ["category", "categories"],
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
}: {
  card: CardDef;
  distribution: TopicDistribution;
  floorN: number;
  /** Resolved once at tab level; texts render in the tab footer, not per card. */
  tabFootnotes: ResolvedFootnote[];
  note?: ReactNode;
  tip: (row: CategoryRow) => ReactNode;
}) {
  const anySuppressed = distribution.items.some((item) => item.cell.status === "suppressed");
  const nTotal = distribution.n_total;
  return (
    <ChartCard
      title={card.title}
      markers={symbolsFor(tabFootnotes, distribution.footnote_ids)}
      suppressionKey={anySuppressed ? "A gray tick instead of a bar is a suppressed category" : null}
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

/** The generate→review→freeze story behind the emergent set (D-33/D-43). */
function emergentMethodNote(doc: Aggregates): ReactNode {
  const themeSet = doc.sections.topics?.theme_set_version;
  return (
    <>
      Themes were generated from the chats in a two-stage pass — candidate codes per message,
      synthesized into a draft theme list — then reviewed by the project team and frozen as the
      versioned set{" "}
      {themeSet ? <span className="font-mono text-[11px]">{themeSet}</span> : "behind this card"};
      every message was classified against that frozen set.
    </>
  );
}

export function TopicsTab({ doc, win }: TabProps) {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<string>(() => searchParams.get("status") ?? "all");

  const intro = (
    <PanelIntro
      question="What do students ask about?"
      deck="Topic distributions over the chat corpus — the question this project exists to answer. Classified locally on the pseudonymized corpus; only privacy-floored counts are published."
    />
  );

  const section = doc.sections.topics;
  const entry: TopicsWindowEntry | undefined = section?.per_window[win.id];
  const available = entry?.by_status
    ? STATUS_ORDER.filter((key) => entry.by_status && key in entry.by_status)
    : [];
  const selected = status !== "all" && available.includes(status as (typeof STATUS_ORDER)[number]) ? status : "all";

  // Shareable state, same mechanism as the tab/window params (replaceState).
  useEffect(() => {
    const params = new URLSearchParams(globalThis.location.search);
    if (selected === "all") params.delete("status");
    else params.set("status", selected);
    globalThis.history.replaceState(null, "", `?${params.toString()}`);
  }, [selected]);

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

  const group: TopicGroup = selected === "all" ? entry : (entry.by_status?.[selected] ?? entry);

  // One symbol table for the whole tab: every card's registry footnotes resolve
  // here (identical across cards), render once in the tab footer, and the card
  // titles keep their †/‡ markers pointing at it.
  const tabFootnotes = resolveFootnotes(
    doc,
    CARDS.map((card) => (group[card.key] as TopicDistribution | null | undefined)?.footnote_ids),
  );
  const tipCtx = {
    scope: selected === "all" ? win.label : `${win.label} (${STATUS_LABELS[selected]} group)`,
    classifier: doc.label_versions.classification,
    themeSet: section.theme_set_version,
    floorN: doc.privacy_floor_n,
  };

  return (
    <div>
      {intro}
      {available.length > 0 ? (
        <div
          role="group"
          aria-label="Program level"
          className="mb-5 inline-flex overflow-hidden rounded-md border border-edge bg-card text-sm"
        >
          {["all", ...available].map((key) => (
            <button
              key={key}
              type="button"
              aria-pressed={selected === key}
              onClick={() => setStatus(key)}
              className={`px-3 py-1.5 transition-colors ${
                selected === key ? "bg-accent text-white" : "text-ink-2 hover:bg-paper"
              }`}
            >
              {key === "all" ? "All students" : STATUS_LABELS[key]}
            </button>
          ))}
        </div>
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
          return (
            <TopicCard
              key={card.key}
              card={card}
              distribution={distribution}
              floorN={doc.privacy_floor_n}
              tabFootnotes={tabFootnotes}
              note={card.key === "emergent_themes" ? emergentMethodNote(doc) : undefined}
              tip={(row) => rowTip(card, row, tipCtx)}
            />
          );
        })}
      </div>
      {tabFootnotes.length > 0 ? (
        <p className="mt-8 border-t border-hairline pt-3 text-xs leading-relaxed text-ink-2">
          <span className="font-display italic">Notes (all cards).</span>{" "}
          {tabFootnotes.map((f) => (
            <span key={f.id}>
              <sup className="text-accent-deep">{f.symbol}</sup> {f.text}{" "}
            </span>
          ))}
        </p>
      ) : null}
    </div>
  );
}

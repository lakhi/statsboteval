"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { TopicDistribution, TopicGroup, TopicsWindowEntry } from "@/lib/aggregates.gen";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import { CategoryBars, categoryTableRows } from "../cells/CategoryBars";
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

const CARDS: { key: keyof TopicGroup; title: string; deck: string }[] = [
  {
    key: "deductive",
    title: "Curriculum categories",
    deck: "The 13 predefined Bergmann et al. codebook categories.",
  },
  { key: "method_themes", title: "Statistical methods", deck: "Explicitly named methods (fixed list)." },
  { key: "software_themes", title: "Analysis software", deck: "Explicitly named software (fixed list)." },
  {
    key: "emergent_themes",
    title: "Emergent themes",
    deck: "Data-driven themes from the chats themselves (reviewed set).",
  },
];

function TopicCard({
  title,
  deck,
  distribution,
  floorN,
  doc,
}: {
  title: string;
  deck: string;
  distribution: TopicDistribution;
  floorN: number;
  doc: TabProps["doc"];
}) {
  const footnotes = resolveFootnotes(doc, [distribution.footnote_ids]);
  const anySuppressed = distribution.items.some((item) => item.cell.status === "suppressed");
  const nTotal = distribution.n_total;
  return (
    <ChartCard
      title={title}
      markers={symbolsFor(footnotes, distribution.footnote_ids)}
      footnotes={footnotes}
      suppressionKey={anySuppressed ? "A gray tick instead of a bar is a suppressed category" : null}
      floorN={floorN}
      table={<DataTable caption={title} head={["Label", "Messages"]} rows={categoryTableRows(distribution)} />}
    >
      <p className="mb-3 text-xs text-ink-3">
        {deck}{" "}
        <span className="tabular-nums">
          {nTotal.status === "ok"
            ? `${formatCount(nTotal.value)} messages in this view.`
            : `Message total suppressed (< ${floorN} students).`}
        </span>
      </p>
      <CategoryBars distribution={distribution} floorN={floorN} />
    </ChartCard>
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
        {CARDS.map(({ key, title, deck }) => {
          const distribution = group[key] as TopicDistribution | null | undefined;
          if (key === "emergent_themes" && !distribution) {
            return (
              <section key={key} className="rounded-lg border border-edge bg-card p-5">
                <h3 className="text-sm font-semibold text-ink">{title}</h3>
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
              key={key}
              title={title}
              deck={deck}
              distribution={distribution}
              floorN={doc.privacy_floor_n}
              doc={doc}
            />
          );
        })}
      </div>
    </div>
  );
}

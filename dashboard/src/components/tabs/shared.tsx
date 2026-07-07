import type { Aggregates, WeeklyEntry } from "@/lib/aggregates.gen";
import type { AnyWindow } from "@/lib/windows";

export type TabProps = { doc: Aggregates; win: AnyWindow };

/** Each panel opens with its educator question — the tab's reason to exist. */
export function PanelIntro({ question, deck }: { question: string; deck: string }) {
  return (
    <div className="mb-6">
      <h2 className="font-display text-[1.65rem] leading-snug text-ink">{question}</h2>
      <p className="mt-1.5 max-w-2xl text-sm text-ink-2">{deck}</p>
    </div>
  );
}

export const hasSuppressed = (entries: WeeklyEntry[]): boolean =>
  entries.some((e) => e.cell.status === "suppressed");

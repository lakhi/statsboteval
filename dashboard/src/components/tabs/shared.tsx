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

// Closed key set from the contract (D-39); "unknown" appears only when published.
// Shared by every tab that renders a by_status split, so Topics and Adoption can never
// order or spell the program levels differently.
export const STATUS_ORDER = ["bachelor", "master", "staff", "unknown"] as const;
export const STATUS_LABELS: Record<string, string> = {
  bachelor: "Bachelor",
  master: "Master",
  staff: "Staff",
  unknown: "Unknown",
};

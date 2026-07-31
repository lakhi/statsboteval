import type { Aggregates, OkCell, SuppressedCell, WeeklyEntry } from "@/lib/aggregates.gen";
import { ALL, LEVEL_LABELS, LEVEL_ORDER, type Level } from "@/lib/levels";
import type { AnyWindow } from "@/lib/windows";

export type TabProps = { doc: Aggregates; win: AnyWindow; level: Level };

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

// Closed key set from the contract (D-39); "unknown" appears only when published. These
// are re-exports, not a second copy: `lib/levels.ts` owns the order and the spellings, and
// two lists of the same closed key set is precisely the drift the shared constant exists
// to prevent. The STATUS_* names are kept because the contract field is `by_status`.
export const STATUS_ORDER = LEVEL_ORDER;
export const STATUS_LABELS = LEVEL_LABELS;

/**
 * Said in words wherever a figure cannot follow the program-level filter (D-55's binding
 * condition). Three situations reach it: a section that publishes no split at all (an old
 * document, or no roster), a measure that has no level to resolve (New signups), and a
 * card whose scope is deliberately cohort-wide (the semester overlay, Trends). Silence
 * would leave the reader believing they are looking at one level when they are not.
 */
export function UnscopedNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-4 rounded-md border border-dashed border-edge bg-paper/50 px-3 py-2 text-xs leading-relaxed text-ink-2">
      {children}
    </p>
  );
}

/** The comparison cards exist to answer "and how do the levels differ?" — a question the
 *  filter has already answered once a single level is selected (D-55). */
export const showsLevelCard = (level: Level): boolean => level === ALL;

/** Levels published for one window, in display order. */
export function levelsIn(byStatus: object | null | undefined): string[] {
  const keys = new Set(Object.keys(byStatus ?? {}));
  return STATUS_ORDER.filter((key) => keys.has(key));
}

type Cell = OkCell | SuppressedCell | null | undefined;

/** The published value, or null for every state that is not a number. */
export const valueOf = (cell: Cell): number | null =>
  cell != null && cell.status === "ok" ? cell.value : null;

/** A cell rendered inside a comparison table: number, suppression mark, or nothing. */
export function cellText(cell: Cell, floorN: number) {
  if (cell == null) return null;
  if (cell.status === "suppressed") {
    return (
      <span className="font-normal text-suppressed" title={`suppressed (< ${floorN} students)`}>
        —
      </span>
    );
  }
  return cell.value.toLocaleString("en");
}

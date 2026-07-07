import type { Aggregates, WeeklyEntry, Windows } from "./aggregates.gen";

export type AnyWindow = Windows[number];

// "YYYY-Www" sorts lexicographically (zero-padded, year first), so plain
// string comparison is correct week ordering throughout.

/** Default filter value: the semester with the latest coverage — the running
 *  semester mid-term, the just-ended one during breaks. Falls back to all_time. */
export function defaultWindowId(windows: Windows): string {
  const semesters = windows
    .filter((w) => w.kind === "semester")
    .sort((a, b) => (a.coverage.through < b.coverage.through ? 1 : -1));
  return semesters[0]?.id ?? windows.find((w) => w.kind === "all_time")?.id ?? windows[0]?.id ?? "";
}

export function findWindow(windows: Windows, id: string | null): AnyWindow | undefined {
  return windows.find((w) => w.id === id);
}

/** A semester whose published coverage stops short of its final member week is
 *  still accumulating data. (Contract §6.1 — no client-side date math needed.) */
export function isInProgress(win: AnyWindow): boolean {
  if (win.kind === "all_time") return false;
  return win.weeks.length > 0 && win.coverage.through < win.weeks[win.weeks.length - 1];
}

/** Display selection, not re-aggregation (invariant 4): weekly series are
 *  published over the full range; a window filter just narrows what is shown. */
export function sliceToWindow(series: WeeklyEntry[], win: AnyWindow): WeeklyEntry[] {
  return series.filter((e) => e.week >= win.coverage.from && e.week <= win.coverage.through);
}

/** Picker groups, in display order: semesters (newest first), trailing, all-time. */
export function groupedWindows(doc: Aggregates): { label: string; windows: AnyWindow[] }[] {
  const semesters = doc.windows
    .filter((w) => w.kind === "semester")
    .sort((a, b) => (a.coverage.through < b.coverage.through ? 1 : -1));
  const trailing = doc.windows.filter((w) => w.kind === "trailing");
  const allTime = doc.windows.filter((w) => w.kind === "all_time");
  return [
    { label: "Semesters", windows: semesters },
    { label: "Recent", windows: trailing },
    { label: "Everything", windows: allTime },
  ].filter((g) => g.windows.length > 0);
}

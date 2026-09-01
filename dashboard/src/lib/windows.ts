import type { Aggregates, WeeklyEntry, Windows } from "./aggregates.gen";

export type AnyWindow = Windows[number];

// "YYYY-Www" sorts lexicographically (zero-padded, year first), so plain
// string comparison is correct week ordering throughout.

/** Default filter value: all_time, the widest view. Falls back to the semester
 *  with the latest coverage if no all_time window is published. */
export function defaultWindowId(windows: Windows): string {
  const semesters = windows
    .filter((w) => w.kind === "semester")
    .sort((a, b) => (a.coverage.through < b.coverage.through ? 1 : -1));
  return windows.find((w) => w.kind === "all_time")?.id ?? semesters[0]?.id ?? windows[0]?.id ?? "";
}

export function findWindow(windows: Windows, id: string | null): AnyWindow | undefined {
  return windows.find((w) => w.id === id);
}

/** A semester whose published coverage stops short of its final member week is
 *  still accumulating data. (Contract §6.1 — no client-side date math needed.)
 *
 *  Only semesters can be in progress: a slice's weeks *are* its coverage, so it is always
 *  complete by construction, and its own label ("Last available week") is true either way.
 *  The marker therefore lands on the semester option and nowhere else. */
export function isInProgress(win: AnyWindow): boolean {
  if (win.kind !== "semester") return false;
  return win.weeks.length > 0 && win.coverage.through < win.weeks[win.weeks.length - 1];
}

/** Display selection, not re-aggregation (invariant 4): weekly series are
 *  published over the full range; a window filter just narrows what is shown. */
export function sliceToWindow(series: WeeklyEntry[], win: AnyWindow): WeeklyEntry[] {
  return series.filter((e) => e.week >= win.coverage.from && e.week <= win.coverage.through);
}

/** Does this window hold exactly one ISO week of data? Some measures are defined away by
 *  that — weeks active per student is 1 for everyone, whatever the data says.
 *
 *  Read off `coverage`, never `weeks`: a semester's `weeks` is its full Thursday-rule
 *  membership (17–18 entries from the day it opens), so the first week of a new term is a
 *  semester with one covered week — the same single week its `.last1` slice holds, and the
 *  default landing state at that moment. Asking `weeks.length` there answers "how long is
 *  the term" when the question was "how much data is in this window". Coverage is clipped
 *  to covered weeks for every kind and the axis is dense, so its endpoints are exact. */
export function isSingleWeek(win: AnyWindow): boolean {
  return win.coverage.from === win.coverage.through;
}

/** Is this window a slice of a semester (D-56)? Narrows the union for `parent_window_id`. */
export function parentWindowId(win: AnyWindow): string | null {
  return win.kind === "semester_slice" ? win.parent_window_id : null;
}

/**
 * Picker groups, in display order: semesters (newest first), the anchor semester's slices,
 * then all-time.
 *
 * Three fixed groups, not one per semester (D-57). Only the anchor is sliced, so nesting
 * would produce two headings holding a single option each and repeat the same three words
 * under the third. Slices are filtered by `kind` rather than by parent: whichever semester
 * they belong to, they are "Recent", and their own labels name it ("Previous 4 weeks ·
 * SS 2026"). Registry order is display order within a group — the pipeline emits the wider
 * slice first, and that is its statement to make, not ours to re-sort.
 */
export function groupedWindows(doc: Aggregates): { label: string; windows: AnyWindow[] }[] {
  const semesters = doc.windows
    .filter((w) => w.kind === "semester")
    .sort((a, b) => (a.coverage.through < b.coverage.through ? 1 : -1));
  const recent = doc.windows.filter((w) => w.kind === "semester_slice");
  const allTime = doc.windows.filter((w) => w.kind === "all_time");
  return [
    { label: "Semesters", windows: semesters },
    { label: "Recent", windows: recent },
    { label: "Everything", windows: allTime },
  ].filter((g) => g.windows.length > 0);
}

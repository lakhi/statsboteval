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
 *  still accumulating data. (Contract §6.1 — no client-side date math needed.)
 *
 *  Only semesters can be in progress: a slice's weeks *are* its coverage, so it is always
 *  complete by construction. The state it reports lives in its label instead — "Latest"
 *  while its semester runs, "Final" once that semester has ended. */
export function isInProgress(win: AnyWindow): boolean {
  if (win.kind !== "semester") return false;
  return win.weeks.length > 0 && win.coverage.through < win.weeks[win.weeks.length - 1];
}

/** Display selection, not re-aggregation (invariant 4): weekly series are
 *  published over the full range; a window filter just narrows what is shown. */
export function sliceToWindow(series: WeeklyEntry[], win: AnyWindow): WeeklyEntry[] {
  return series.filter((e) => e.week >= win.coverage.from && e.week <= win.coverage.through);
}

/** What the picker shows inside a group, where the heading already names the semester.
 *  Falls back to the self-contained `label`: `short_label` is optional on the pre-1.8.0
 *  window kinds so the previously published document keeps parsing (contract §6.1). */
export function optionLabel(win: AnyWindow): string {
  // Narrowed on `kind` rather than `"short_label" in win`: every generated window
  // interface carries an index signature, so the `in` check widens the result to unknown.
  return win.kind === "trailing" ? win.label : (win.short_label ?? win.label);
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

/** The semester a window belongs to: itself, its parent, or none for all_time. */
export function semesterOf(doc: Aggregates, win: AnyWindow): AnyWindow | undefined {
  if (win.kind === "semester") return win;
  const parent = parentWindowId(win);
  return parent ? doc.windows.find((w) => w.id === parent) : undefined;
}

/**
 * Picker groups, in display order: one group per semester (newest first) holding the whole
 * semester and its slices, then all-time.
 *
 * Grouping follows `parent_window_id` rather than parsing ids — the link is published
 * exactly so the client never has to infer it. Within a group, registry order is display
 * order (whole semester, then the wider slice, then the narrower), which is the pipeline's
 * statement and not something to re-sort here.
 */
export function groupedWindows(doc: Aggregates): { label: string; windows: AnyWindow[] }[] {
  const semesters = doc.windows
    .filter((w) => w.kind === "semester")
    .sort((a, b) => (a.coverage.through < b.coverage.through ? 1 : -1));
  const groups = semesters.map((semester) => ({
    label: semester.label + (isInProgress(semester) ? " (in progress)" : ""),
    windows: [semester, ...doc.windows.filter((w) => parentWindowId(w) === semester.id)],
  }));
  const allTime = doc.windows.filter((w) => w.kind === "all_time");
  return [...groups, { label: "Everything", windows: allTime }].filter((g) => g.windows.length > 0);
}

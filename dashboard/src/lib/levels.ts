import type { Aggregates } from "./aggregates.gen";
import { parentWindowId, type AnyWindow } from "./windows";

/**
 * The program-level filter (D-55). `"all"` is not a published key — it means "read the
 * cohort-wide shape beside by_status", which is why it never appears in a document.
 */
export type Level = string;
export const ALL: Level = "all";

// Closed key set from the contract (§8), in display order. Bachelor leads and All users
// trails, both deliberate: the bachelor cohort is the dashboard's primary audience, and a
// filter whose widest option sits last reads as "narrow → wide" rather than as a default
// someone forgot to change.
//
// This is THE list. `shared.tsx` re-exports it under its older STATUS_* names rather than
// keeping a second copy — two spellings of a closed key set is exactly the drift the
// single ordering constant was introduced to prevent.
export const LEVEL_ORDER = ["bachelor", "master", "staff", "unknown"] as const;
export const LEVEL_LABELS: Record<string, string> = {
  bachelor: "Bachelor",
  master: "Master",
  staff: "Staff",
  unknown: "Unknown",
  [ALL]: "All users",
};

/** Sentence fragment for the header line, e.g. "bachelor students". */
export const LEVEL_PHRASE: Record<string, string> = {
  bachelor: "bachelor students",
  master: "master students",
  staff: "staff",
  unknown: "students whose program level is unknown",
};

/**
 * Every level the document publishes anywhere — deliberately not "levels available in the
 * selected window".
 *
 * A picker that reshuffles when the window changes is a picker whose selection can vanish
 * under the reader: a single-week slice can easily hold master activity and nothing else, so a
 * window-scoped list would drop Bachelor, silently re-resolve the default, and show
 * master numbers under a filter the reader last set to bachelor. Offering the stable set
 * and rendering an honest gap for an empty combination keeps the control's meaning fixed.
 */
export function availableLevels(doc: Aggregates): string[] {
  const found = new Set<string>();
  const collect = (map: object | null | undefined) => {
    for (const key of Object.keys(map ?? {})) found.add(key);
  };
  const s = doc.sections;
  collect(s.temporal_usage?.weekly_by_status);
  for (const w of Object.values(s.temporal_usage?.per_window ?? {})) collect(w.by_status);
  for (const w of Object.values(s.usage_context?.per_window ?? {})) collect(w.by_status);
  for (const w of Object.values(s.sessions?.per_window ?? {})) collect(w.by_status);
  for (const w of Object.values(s.per_student?.per_window ?? {})) collect(w.by_status);
  for (const w of Object.values(s.language?.per_window ?? {})) collect(w.by_status);
  for (const w of Object.values(s.topics?.per_window ?? {})) collect(w.by_status);
  return LEVEL_ORDER.filter((key) => found.has(key));
}

/** Bachelor by default (D-55), falling back to the widest view when no roster exists. */
export function defaultLevel(available: string[]): Level {
  return available.includes("bachelor") ? "bachelor" : ALL;
}

export function resolveLevel(available: string[], candidate: string | null): Level {
  if (candidate === ALL) return ALL;
  if (candidate && available.includes(candidate)) return candidate;
  return defaultLevel(available);
}

/**
 * Pick the level's slice of a published `by_status` map, or the cohort-wide shape.
 *
 * Returning `undefined` (rather than falling back to the cohort-wide value) for a level
 * with no slice is the whole point: a tab that silently showed everyone's numbers under a
 * bachelor filter would be the exact failure the global control has to avoid.
 */
export type LevelSlice<T> = {
  data: T;
  /** False when the section cannot answer by level and the cohort-wide shape is shown. */
  scoped: boolean;
};

export function sliceByLevel<A, B>(
  cohortWide: A,
  byStatus: Record<string, B> | null | undefined,
  level: Level,
): LevelSlice<A | B> | null {
  if (level === ALL) return { data: cohortWide, scoped: true };
  // Absence has two causes and they mean opposite things. A section that publishes no
  // `by_status` AT ALL cannot answer the question — a pre-1.7.0 document (the blob live
  // right now, and what a rollback restores) or a corpus with no roster imported. Reading
  // that as "nobody at this level wrote anything" would have three tabs assert a measured
  // absence that was never measured. Only a level missing from a split that IS published
  // is a real, measured zero.
  if (byStatus == null || Object.keys(byStatus).length === 0) {
    return { data: cohortWide, scoped: false };
  }
  const slice = byStatus[level];
  return slice === undefined ? null : { data: slice, scoped: true };
}

/**
 * Enrolled cohort size for this window and level, when one is published.
 *
 * `enrollment.per_window` is keyed by semester only, and stays that way (D-55): one
 * institutional headcount per term, never copied under a second id. A semester slice lies
 * entirely inside one term, so the denominator it needs is its parent's — which is what
 * `parent_window_id` is for. Reach then means the share of that term's cohort active
 * during those weeks, which the `reach_window_scope` footnote states wherever it appears.
 *
 * all_time still gets nothing: it spans three semesters of cohort turnover, so no headcount
 * is the right denominator.
 */
export function enrollmentFor(doc: Aggregates, win: AnyWindow) {
  const parent = parentWindowId(win);
  return doc.enrollment?.per_window?.[win.id] ?? (parent ? doc.enrollment?.per_window?.[parent] : undefined);
}

export function enrolledFor(doc: Aggregates, win: AnyWindow, level: Level): number | null {
  if (level !== "bachelor" && level !== "master") return null;
  const entry = enrollmentFor(doc, win);
  return entry ? entry[level] : null;
}

/** Reach's denominator is the parent term's cohort in a slice, so the scope caveat rides
 *  along there and only there — on a whole semester it would state the obvious. */
export function reachFootnoteIds(win: AnyWindow): string[] {
  const base = ["enrollment_source", "enrollment_scope"];
  return win.kind === "semester_slice" ? ["reach_window_scope", ...base] : base;
}

/** Reach = active students ÷ enrolled cohort, as a rounded percentage string. */
export function reachPercent(active: number, enrolled: number): string {
  return `${((active / enrolled) * 100).toFixed(1)}%`;
}

/** Share of a published total, for the composition columns. Null when either side is unusable. */
export function sharePercent(part: number, total: number | null): string | null {
  if (total === null || total <= 0) return null;
  return `${Math.round((part / total) * 100)}%`;
}

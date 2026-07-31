import type { HistogramBin } from "./aggregates.gen";
import type { AnyWindow } from "./windows";

export const formatCount = (n: number): string => n.toLocaleString("en");

/** "2026-W27" → "W27" (axis ticks; the year is carried by context/tooltip). */
export const weekShort = (week: string): string => week.slice(5);

// --- Dates -----------------------------------------------------------------
// Intl cannot express the dashboard's date format. Every English locale that
// renders a 3-letter month reorders it month-first ("Sep 29, 25" — en-US, en-CA,
// en); every day-first English locale spells September "Sept" ("29 Sept 25" —
// en-GB, en-IE, en-AU). Day-first + 3-letter month is not an English CLDR
// pattern, so the month names live here — which also makes the output identical
// across browsers instead of dependent on the viewer's ICU data.
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

const MS_PER_DAY = 86_400_000;

/** ISO 8601 week id → that week's Monday. Mirrors `week_monday` in
 *  pipeline/statsboteval_pipeline/contract.py — keep the two in step.
 *  All arithmetic is UTC: local-time construction would shift the result a day
 *  in either direction depending on the viewer's offset and DST. */
export function isoWeekMonday(week: string): Date {
  const year = Number(week.slice(0, 4));
  const weekNumber = Number(week.slice(6));
  // ISO 8601: week 1 is the week containing Jan 4, weeks start on Monday.
  const jan4 = Date.UTC(year, 0, 4);
  const jan4Weekday = new Date(jan4).getUTCDay() || 7; // Sunday 0 → 7
  const week1Monday = jan4 - (jan4Weekday - 1) * MS_PER_DAY;
  return new Date(week1Monday + (weekNumber - 1) * 7 * MS_PER_DAY);
}

/** ISO 8601 week id → that week's Sunday (the week's last day). */
export const isoWeekSunday = (week: string): Date =>
  new Date(isoWeekMonday(week).getTime() + 6 * MS_PER_DAY);

// --- Week axis labels (D-54) ------------------------------------------------
// "W10" told an educator nothing. The replacement is a hierarchical axis — the
// month named once at its boundary, the weeks between it positional — which is
// what every serious time-series axis does (ggplot date_breaks, Plot's tick
// reduction, financial charts). The rejected alternative was "Mar-W1" on every
// tick: 9 of the 24 months in 2025-26 hold five ISO weeks (April 2026 and May
// 2025 among them), the Monday and Thursday rules disagree on boundary weeks,
// "Mar-W1" repeats unqualified across years on the 74-week all_time axis, and
// doubling the label width makes recharts drop MORE ticks than it does today.

/** The month owning a week: the one containing its Thursday. Same rule as
 *  windows.py:_semester_of, so a week never belongs to one month here and a
 *  different semester there. */
const weekThursday = (week: string): Date =>
  new Date(isoWeekMonday(week).getTime() + 3 * MS_PER_DAY);

/**
 * Month anchor for a dense axis: the month name at each month boundary, "" in
 * between. January also carries the year, which is what disambiguates the two
 * "Mar"s on the all_time axis; so does the very first tick (prev === undefined).
 */
export function weekMonthAnchor(week: string, prev?: string): string {
  const thursday = weekThursday(week);
  const month = thursday.getUTCMonth();
  if (prev !== undefined && weekThursday(prev).getUTCMonth() === month) return "";
  const label = MONTHS[month];
  const showYear = month === 0 || prev === undefined;
  return showYear ? `${label} ${String(thursday.getUTCFullYear()).slice(2)}` : label;
}

/** "02 Mar" — the week's Monday. Every tick self-describing, for short axes
 *  where month anchors could produce no labels at all (a 4-week window need
 *  not contain a month boundary). */
export const weekStartLabel = (week: string): string => formatDay(isoWeekMonday(week)).slice(0, 6);

/** "W23 · 01–07 Jun 2026" — tooltips and table rows, where there is room to be
 *  exact and the axis itself has been made approximate. */
export function weekRangeLabel(week: string): string {
  const monday = isoWeekMonday(week);
  const sunday = isoWeekSunday(week);
  const day = (d: Date) => String(d.getUTCDate()).padStart(2, "0");
  const span =
    monday.getUTCMonth() === sunday.getUTCMonth()
      ? `${day(monday)}–${day(sunday)} ${MONTHS[sunday.getUTCMonth()]}`
      : `${day(monday)} ${MONTHS[monday.getUTCMonth()]} – ${day(sunday)} ${MONTHS[sunday.getUTCMonth()]}`;
  return `W${week.slice(6)} · ${span} ${sunday.getUTCFullYear()}`;
}

/** Below this many points, month anchors risk labelling nothing, so every tick
 *  gets its Monday date instead. trailing_4 (4 points) is the case in hand. */
export const SHORT_AXIS_POINTS = 8;

/** "02 Mar 26"; `longYear` gives "02 Mar 2026". Reads UTC fields — pair it with
 *  a Date built in UTC (isoWeekMonday) or with viennaDate below. */
export function formatDay(d: Date, { longYear = false }: { longYear?: boolean } = {}): string {
  const day = String(d.getUTCDate()).padStart(2, "0");
  const year = longYear ? d.getUTCFullYear() : String(d.getUTCFullYear()).slice(2);
  return `${day} ${MONTHS[d.getUTCMonth()]} ${year}`;
}

/** The selected window's span as calendar dates: Monday of its first covered
 *  week → Sunday of its last. `coverage` is the only date source every window
 *  kind has (all_time and trailing publish no start_date/end_date), and the
 *  pipeline has already clipped it to the published axis — so an in-progress
 *  window's end date can never run past the data. */
export const formatWindowRange = (win: AnyWindow): string =>
  `${formatDay(isoWeekMonday(win.coverage.from))} – ${formatDay(isoWeekSunday(win.coverage.through))}`;

/** Publish instant → "28 Jul 2026", read in the document's own timezone.
 *  The document buckets everything Vienna-local and `data_through_date` is a
 *  Vienna-local Sunday, so a late-evening operator run must not print the UTC
 *  day. formatToParts (rather than a formatted string) keeps this
 *  locale-independent; the parts are re-formatted through MONTHS above. */
export function formatGeneratedDate(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(new Date(iso));
  const field = (type: Intl.DateTimeFormatPartTypes): number =>
    Number(parts.find((p) => p.type === type)?.value);
  // Re-anchored in UTC purely so formatDay reads back the same calendar day.
  return formatDay(new Date(Date.UTC(field("year"), field("month") - 1, field("day"))), {
    longYear: true,
  });
}

/** Inclusive-integer bin label: [1,1]→"1", [2,3]→"2–3", [8,null]→"8+". */
export function binLabel({ lo, hi }: Pick<HistogramBin, "lo" | "hi">): string {
  if (hi === null) return `${formatCount(lo)}+`;
  if (hi === lo) return formatCount(lo);
  return `${formatCount(lo)}–${formatCount(hi)}`;
}

/**
 * Contract unit -> the word the page uses for it.
 *
 * `Histogram.unit` is internal vocabulary ("sessions", from the corpus's session key).
 * Everything a reader sees calls the same object a conversation, so the mapping happens
 * once here, at the render boundary, rather than by renaming the contract field.
 */
const UNIT_LABELS: Record<string, string> = { sessions: "conversations" };
export const unitLabel = (unit: string): string => UNIT_LABELS[unit] ?? unit;

export function formatStat(n: number): string {
  return Number.isInteger(n) ? formatCount(n) : n.toLocaleString("en", { maximumFractionDigits: 1 });
}

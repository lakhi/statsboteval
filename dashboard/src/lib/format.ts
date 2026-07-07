import type { HistogramBin } from "./aggregates.gen";

export const formatCount = (n: number): string => n.toLocaleString("en");

/** "2026-W27" → "W27" (axis ticks; the year is carried by context/tooltip). */
export const weekShort = (week: string): string => week.slice(5);

/** Inclusive-integer bin label: [1,1]→"1", [2,3]→"2–3", [8,null]→"8+". */
export function binLabel({ lo, hi }: Pick<HistogramBin, "lo" | "hi">): string {
  if (hi === null) return `${formatCount(lo)}+`;
  if (hi === lo) return formatCount(lo);
  return `${formatCount(lo)}–${formatCount(hi)}`;
}

export function formatStat(n: number): string {
  return Number.isInteger(n) ? formatCount(n) : n.toLocaleString("en", { maximumFractionDigits: 1 });
}

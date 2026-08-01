import type { ReactNode } from "react";
import type { ResolvedFootnote } from "@/lib/footnotes";
import { NoteText } from "./NoteText";

/**
 * Card shell shared by every metric. The foot renders APA-style table notes:
 * the registry footnotes (†, ‡, …) plus the standard suppression key when the
 * plotted data contains suppressed cells — caveats live with the figure, as on
 * a journal table.
 */
export function ChartCard({
  title,
  markers,
  footnotes = [],
  suppressionKey,
  note,
  floorN,
  children,
  footer,
  table,
}: {
  title: string;
  /** Footnote symbols attached to this card's title, e.g. "†‡". */
  markers?: string;
  footnotes?: ResolvedFootnote[];
  /** What a suppressed mark looks like in this figure, if any are shown. */
  suppressionKey?: string | null;
  /** Card-specific prose appended to the Note (e.g. a method explanation). */
  note?: ReactNode;
  floorN: number;
  children: ReactNode;
  /** A second figure, below the Note — a rendering of the same numbers rather than
   *  new ones (D-59: Adoption's level donut under its level table). Below the note
   *  and not above it because the note qualifies the figures, and a reader who has
   *  reached the second one has already read past it. */
  footer?: ReactNode;
  table?: ReactNode;
}) {
  const hasNotes = footnotes.length > 0 || suppressionKey || note;
  return (
    <section className="rounded-lg border border-edge bg-card p-5">
      <h3 className="text-sm font-semibold text-ink">
        {title}
        {markers ? <sup className="ml-0.5 font-normal text-accent-deep">{markers}</sup> : null}
      </h3>
      <div className="mt-3">{children}</div>
      {hasNotes ? (
        <p className="mt-3 border-t border-hairline pt-2 text-xs leading-relaxed text-ink-2">
          <span className="font-display italic">Note.</span>{" "}
          {suppressionKey ? (
            <span>
              {suppressionKey} (&lt; {floorN} students — withheld, not zero).{" "}
            </span>
          ) : null}
          {footnotes.map((f) => (
            <span key={f.id}>
              {/* Through NoteText so a citation URL in a published note is clickable.
                  This is the only *card* renderer; TopicsTab's tab-level "Notes (all
                  cards)" paragraph is the other place footnote text reaches the page and
                  goes through NoteText too. Any third one must. */}
              <sup className="text-accent-deep">{f.symbol}</sup> <NoteText text={f.text} />{" "}
            </span>
          ))}
          {note ? <span>{note}</span> : null}
        </p>
      ) : null}
      {footer ? <div className="mt-4">{footer}</div> : null}
      {table}
    </section>
  );
}

/** Collapsible WCAG-clean twin of the figure: every plotted value as text. */
export function DataTable({
  head,
  rows,
  caption,
}: {
  head: string[];
  rows: (string | number)[][];
  caption: string;
}) {
  return (
    <details className="mt-2 text-xs">
      <summary className="cursor-pointer select-none text-ink-3 hover:text-ink-2">
        Data table
      </summary>
      <div className="mt-2 max-h-64 overflow-auto rounded border border-hairline">
        <table className="w-full border-collapse text-left tabular-nums">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="border-b border-hairline bg-paper text-ink-2">
              {head.map((h) => (
                <th key={h} className="px-2 py-1 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-hairline last:border-0">
                {row.map((cell, j) => (
                  <td key={j} className={`px-2 py-1 ${j === 0 ? "text-ink-2" : "text-ink"}`}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

import type { ReactNode } from "react";
import type { ResolvedFootnote } from "@/lib/footnotes";
import { LEVEL_LABELS } from "@/lib/levels";
import { ChartCard, DataTable } from "./ChartCard";

/**
 * The one comparison table every tab shows under "All users" (D-55).
 *
 * Shared rather than five hand-built tables: level order and spelling already live in one
 * place (`LEVEL_ORDER`/`LEVEL_LABELS`) precisely so two tabs cannot disagree about them,
 * and a table shape repeated five times would reintroduce that drift one column at a time.
 * Each tab supplies only its columns and the cells behind them.
 *
 * Percentages are always a division of two published cells — the arithmetic invariant 4
 * allows — and each card names its own denominator in the column header, because
 * "share of the window" and "share of this level" are different claims and a bare "%"
 * cannot tell them apart.
 *
 * Since D-62 the *figure* is swappable: two cards draw stacked columns instead of the
 * inline table. What stays shared is everything a second hand-built card would drift on —
 * level order, level spelling, the note, the footnote symbols, and the data table built
 * from these same `columns`. A card with a `figure` therefore always keeps its disclosure:
 * that table is then the only place the numbers exist as text.
 */

export type LevelColumn = {
  header: ReactNode;
  /** Right-aligned by default; the level name column opts out. */
  align?: "left" | "right";
  /** Rendered per level; return null for "nothing publishable here". */
  cell: (level: string) => ReactNode;
  /** Data-table text, where the rendered cell is not a plain string. Without it a rich
   *  cell falls back to an em dash — fine beside a visible table that already showed the
   *  mark, wrong on a `figure` card where the disclosure is the only text channel. */
  text?: (level: string) => string;
};

export function ProgramLevelCard({
  title,
  levels,
  columns,
  markers,
  footnotes = [],
  suppressionKey,
  note,
  floorN,
  tableCaption,
  figure,
  footer,
  showTable = true,
}: {
  title: string;
  levels: string[];
  columns: LevelColumn[];
  markers?: string;
  footnotes?: ResolvedFootnote[];
  /** What a withheld cell looks like in `figure`, if any are shown (D-62). Meaningless
   *  for the inline table, whose suppression mark carries its own title. */
  suppressionKey?: string | null;
  note?: ReactNode;
  floorN: number;
  tableCaption: string;
  /** Draw this instead of the inline table (D-62). The `columns` are still required —
   *  they build the data table, which a figure card always shows. */
  figure?: ReactNode;
  /** A second reading of these same numbers, below the Note (D-59). */
  footer?: ReactNode;
  /** Opt out of the collapsible data table. Only honest where the card's own figure
   *  already IS an accessible `<table>` with a caption, so it is ignored under `figure`
   *  and the disclosure stays on by default everywhere else. */
  showTable?: boolean;
}) {
  if (levels.length === 0) return null;
  return (
    <ChartCard
      title={title}
      markers={markers}
      footnotes={footnotes}
      suppressionKey={figure ? suppressionKey : null}
      note={note}
      floorN={floorN}
      footer={footer}
      table={
        showTable || figure ? (
          <DataTable
            caption={tableCaption}
            head={columns.map((c, i) => (i === 0 ? "Level" : String(c.header)))}
            rows={levels.map((level) => [
              LEVEL_LABELS[level] ?? level,
              ...columns.slice(1).map((c) => c.text?.(level) ?? textOf(c.cell(level))),
            ])}
          />
        ) : null
      }
    >
      {figure ?? <LevelTable levels={levels} columns={columns} tableCaption={tableCaption} />}
    </ChartCard>
  );
}

function LevelTable({
  levels,
  columns,
  tableCaption,
}: {
  levels: string[];
  columns: LevelColumn[];
  tableCaption: string;
}) {
  return (
    <table className="w-full border-collapse text-xs">
      <caption className="sr-only">{tableCaption}</caption>
      <thead>
        <tr className="text-ink-2">
          {columns.map((column, i) => (
            <th
              key={i}
              scope="col"
              className={`pb-1 font-normal ${i === 0 ? "text-left" : "pl-3 text-right"}`}
            >
              {column.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {levels.map((level) => (
          <tr key={level} className="border-t border-hairline">
            <th scope="row" className="py-1.5 pr-3 text-left font-normal text-ink-2">
              {LEVEL_LABELS[level] ?? level}
            </th>
            {columns.slice(1).map((column, i) => (
              <td key={i} className="py-1.5 pl-3 text-right font-semibold tabular-nums text-ink">
                {column.cell(level) ?? <span className="font-normal text-ink-3">·</span>}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Best-effort text for the WCAG data table; rich cells fall back to an em dash. */
function textOf(node: ReactNode): string {
  if (node === null || node === undefined) return "·";
  if (typeof node === "string" || typeof node === "number") return String(node);
  return "—";
}

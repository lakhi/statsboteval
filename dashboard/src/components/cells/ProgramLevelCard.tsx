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
 */

export type LevelColumn = {
  header: ReactNode;
  /** Right-aligned by default; the level name column opts out. */
  align?: "left" | "right";
  /** Rendered per level; return null for "nothing publishable here". */
  cell: (level: string) => ReactNode;
};

export function ProgramLevelCard({
  title,
  levels,
  columns,
  markers,
  footnotes = [],
  note,
  floorN,
  tableCaption,
}: {
  title: string;
  levels: string[];
  columns: LevelColumn[];
  markers?: string;
  footnotes?: ResolvedFootnote[];
  note?: ReactNode;
  floorN: number;
  tableCaption: string;
}) {
  if (levels.length === 0) return null;
  return (
    <ChartCard
      title={title}
      markers={markers}
      footnotes={footnotes}
      note={note}
      floorN={floorN}
      table={
        <DataTable
          caption={tableCaption}
          head={columns.map((c, i) => (i === 0 ? "Level" : String(c.header)))}
          rows={levels.map((level) => [
            LEVEL_LABELS[level] ?? level,
            ...columns.slice(1).map((c) => textOf(c.cell(level))),
          ])}
        />
      }
    >
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
    </ChartCard>
  );
}

/** Best-effort text for the WCAG data table; rich cells fall back to an em dash. */
function textOf(node: ReactNode): string {
  if (node === null || node === undefined) return "·";
  if (typeof node === "string" || typeof node === "number") return String(node);
  return "—";
}

import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import { sliceToWindow } from "@/lib/windows";
import { ALL, sliceByLevel } from "@/lib/levels";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { LevelGap, SectionPending, WindowGap } from "../cells/EmptyState";
import { PieShare } from "../cells/PieShare";
import { ProgramLevelCard, type LevelColumn } from "../cells/ProgramLevelCard";
import { TrendChart, trendTableRows, type TrendSeries } from "../cells/TrendChart";
import {
  hasSuppressed,
  levelsIn,
  PanelIntro,
  showsLevelCard,
  STATUS_LABELS,
  UnscopedNote,
  valueOf,
  type TabProps,
} from "./shared";

// Fixed key set in contract v1. "Undetermined" wears a neutral gray on purpose —
// it means "no signal", not an identity worth a hue. Aqua and yellow sit below 3:1 on
// this surface (2.74 and 2.11 measured), so this palette ships under an obligation:
// visible labels or a table. Since D-59 collapsed the totals table into the standard
// disclosure, the relief channel is the donut's figure-carrying legend — label, count
// and share per language, always visible. Whatever replaces that legend has to carry
// the same, or the table comes back out of the disclosure.
const LANGS = [
  { key: "de", label: "German", color: "var(--color-accent)" },
  { key: "en", label: "English", color: "var(--color-series-en)" },
  { key: "other", label: "Other", color: "var(--color-series-other)" },
  { key: "undetermined", label: "Undetermined", color: "#6e6c66" },
] as const;

/**
 * The Totals figures whenever the donut cannot be drawn — a withheld language, or no
 * published denominator for the Share column.
 *
 * The pre-D-59 table, kept for exactly these cases: languages partition messages, so a
 * ring over the published ones would show them as the whole corpus, and a ring with no
 * denominator has nothing to put in the legend's share column. A short table says the
 * true thing in both — here is what we can publish, and here is what is missing.
 */
function TotalsTable({
  rows,
  denomValue,
  floorN,
}: {
  /** The same slice list the donut would have used; `value: null` is the withheld one. */
  rows: { key: string; label: string; color: string; value: number | null }[];
  denomValue: number | null;
  floorN: number;
}) {
  return (
    <table className="w-full text-sm tabular-nums">
      <thead>
        <tr className="border-b border-hairline text-left text-xs text-ink-2">
          <th className="py-1.5 font-medium">Language</th>
          <th className="py-1.5 text-right font-medium">Messages</th>
          <th className="py-1.5 text-right font-medium">Share</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key} className="border-b border-hairline last:border-0">
            <td className="flex items-center gap-2 py-2 text-ink">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: row.color }}
                aria-hidden
              />
              {row.label}
            </td>
            {row.value !== null ? (
              <>
                <td className="py-2 text-right text-ink">{formatCount(row.value)}</td>
                <td className="py-2 text-right text-ink-2">
                  {denomValue ? `${Math.round((row.value / denomValue) * 100)}%` : "—"}
                </td>
              </>
            ) : (
              <td colSpan={2} className="py-2 text-right text-ink-3">
                suppressed (&lt; {floorN} students)
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function LanguageTab({ doc, win, level }: TabProps) {
  const intro = (
    <PanelIntro
      question="In which language do they chat?"
      deck="Message language over time and for the selected window, detected locally per message."
    />
  );
  const section = doc.sections.language;
  if (!section) {
    return (
      <div>
        {intro}
        <SectionPending what="Language (the language section)" />
      </div>
    );
  }

  // Per-level weekly copies (1.7.0): the chart is this tab's main figure, so leaving it
  // cohort-wide under a level filter would scope the totals table and nothing else.
  const weeklySlice = sliceByLevel(section.weekly, section.weekly_by_status, level);
  const perWindow = section.per_window[win.id];
  const totalsSlice = perWindow
    ? sliceByLevel(perWindow.totals, perWindow.by_status, level)
    : undefined;

  // Either side coming back null means the split is published and this level is absent
  // from it — a measured absence, and the same LevelGap every sibling tab shows. The old
  // condition required BOTH to be missing, which let the real trailing_4 x bachelor case
  // fall through to a flat-zero chart beside a mislabeled WindowGap.
  if (weeklySlice === null || totalsSlice === null) {
    return (
      <div>
        {intro}
        <LevelGap levelLabel={STATUS_LABELS[level] ?? level} windowLabel={win.label} />
      </div>
    );
  }
  const unscoped =
    level !== ALL && (!weeklySlice.scoped || totalsSlice?.scoped === false);

  const weekly = weeklySlice.data.messages_by_language;
  const series: TrendSeries[] = LANGS.map((lang) => ({
    id: lang.key,
    label: lang.label,
    color: lang.color,
    entries: sliceToWindow(weekly[lang.key].series, win),
  }));
  const footnotes = resolveFootnotes(doc, [weekly.footnote_ids]);
  const anySuppressed = series.some((s) => hasSuppressed(s.entries));

  const totals = totalsSlice?.data;
  // Share = language total ÷ the same window's published messages total —
  // division of two published cells, the one client-side arithmetic the
  // contract allows (invariant 4). Under a level filter both sides are that level's,
  // so the percentages keep meaning "of the messages on screen".
  const usageWindow = doc.sections.usage_context?.per_window[win.id];
  const denominator =
    level === ALL ? usageWindow?.totals.messages : usageWindow?.by_status?.[level]?.messages;
  const denomValue = denominator?.status === "ok" && denominator.value > 0 ? denominator.value : null;

  // The donut (D-59). All four languages or none: they partition the window's messages,
  // so a ring missing a withheld one would read as the whole. A measured zero keeps its
  // legend row and draws no arc — `Other` is 0 in most windows, and that IS the finding.
  const langSlices = totals
    ? LANGS.map((lang) => ({
        key: lang.key,
        label: lang.label,
        value: valueOf(totals[lang.key]),
        color: lang.color,
      }))
    : [];
  //
  // Two conditions, not one. Every language published, AND a published denominator to
  // read them against: the donut's legend is the card's share channel, so a ring without
  // a denominator would have to either print no shares (a legend that has lost its second
  // column) or invent one by summing the four cells — which is the client-side arithmetic
  // invariant 4 forbids, and which would contradict the card's own "counts are shown
  // without shares" line and the em dashes in its data table. No denominator, no ring:
  // the table below says the true thing on its own.
  const donut =
    totals && denomValue !== null && langSlices.every((s) => s.value !== null)
      ? (langSlices as { key: string; label: string; value: number; color: string }[])
      : null;

  const byStatus = perWindow?.by_status;
  const levels = levelsIn(byStatus);
  const langStatusFootnotes = resolveFootnotes(doc, [
    ["status_rule", "status_multi", "language_heuristic"],
  ]);
  // Within-level shares, the same denominator rule Timing's card uses: German's share of
  // bachelor messages is comparable across levels in a way German's share of all messages
  // is not, because the levels differ in size.
  const levelColumns: LevelColumn[] = [
    { header: "Level", align: "left", cell: () => null },
    ...LANGS.map((lang) => ({
      header: lang.label,
      cell: (l: string) => {
        // The level's published message total, never a sum of the four language cells:
        // one suppressed language would blank the whole row, and normalising to the
        // survivors would make them total 100% — asserting the suppressed language is
        // zero. Languages partition messages exactly, so the published total is the
        // honest denominator and a short row shows where the suppressed one went.
        const value = valueOf(byStatus?.[l]?.[lang.key]);
        const total = valueOf(
          doc.sections.usage_context?.per_window[win.id]?.by_status?.[l]?.messages,
        );
        return value === null || total === null || total === 0
          ? null
          : `${Math.round((value / total) * 100)}%`;
      },
    })),
  ];

  return (
    <div>
      {intro}
      {unscoped ? (
        <UnscopedNote>
          This data release does not break Language down by program level, so the figures
          below cover every level. Republishing with a current pipeline fills them in.
        </UnscopedNote>
      ) : null}
      {/* Order (D-59): the level comparison leads under All users, then Totals, then the
          weekly chart. Under a single level the level card is absent, so Totals leads —
          which is the same reading order one card shorter. */}
      <div className="grid gap-4 lg:grid-cols-5">
        {showsLevelCard(level) && levels.length > 0 ? (
          <div className="lg:col-span-5">
            <ProgramLevelCard
              title="By program level"
              tableCaption={`Language mix by program level, ${win.label}`}
              levels={levels}
              columns={levelColumns}
              floorN={doc.privacy_floor_n}
              markers={symbolsFor(langStatusFootnotes, ["status_rule", "language_heuristic"])}
              footnotes={langStatusFootnotes}
              note={
                <>
                  Each row is a share of that level&rsquo;s own published message total, so
                  levels of very different size stay comparable. A suppressed language is
                  left out of its row rather than folded into the others, so a row need not
                  total 100%.
                </>
              }
            />
          </div>
        ) : null}

        <div className="lg:col-span-2">
          {totals ? (
            <ChartCard
              title={`Totals — ${win.label}`}
              floorN={doc.privacy_floor_n}
              table={
                <DataTable
                  caption={`Messages by language, ${win.label}`}
                  head={["Language", "Messages", "Share"]}
                  rows={LANGS.map((lang) => {
                    const cell = totals[lang.key];
                    if (cell.status !== "ok") return [lang.label, "suppressed", "—"];
                    return [
                      lang.label,
                      formatCount(cell.value),
                      denomValue ? `${Math.round((cell.value / denomValue) * 100)}%` : "—",
                    ];
                  })}
                />
              }
            >
              {donut ? (
                <PieShare
                  slices={donut}
                  total={denomValue ?? 0}
                  centerLabel={`messages in ${win.label}`}
                  valueLabel="Messages"
                  ariaLabel={`Messages by language, ${win.label}: ${donut
                    .map((s) => `${s.label} ${formatCount(s.value)}`)
                    .join(", ")}.`}
                />
              ) : (
                // No ring: either a language is withheld (a ring over the rest would show
                // them as the whole corpus) or this window has no published denominator to
                // read shares against. The pre-donut table says both cases correctly.
                <TotalsTable
                  rows={langSlices}
                  denomValue={denomValue}
                  floorN={doc.privacy_floor_n}
                />
              )}
              {!denomValue ? (
                <p className="mt-2 text-xs text-ink-3">
                  Shares need this window&apos;s published messages total (Adoption section) — not
                  available here, so counts are shown without shares.
                </p>
              ) : null}
            </ChartCard>
          ) : (
            <WindowGap what="language-totals" windowLabel={win.label} />
          )}
        </div>

        <div className="lg:col-span-3">
          <ChartCard
            title="Messages by language per week"
            markers={symbolsFor(footnotes, weekly.footnote_ids)}
            footnotes={footnotes}
            suppressionKey={anySuppressed ? "Gaps in a line are suppressed weeks" : null}
            floorN={doc.privacy_floor_n}
            table={
              <DataTable
                caption="Messages by language per week"
                head={["Week", ...LANGS.map((l) => l.label)]}
                rows={trendTableRows(series)}
              />
            }
          >
            <TrendChart series={series} floorN={doc.privacy_floor_n} height={240} />
          </ChartCard>
        </div>

      </div>
    </div>
  );
}

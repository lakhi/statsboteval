import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { formatCount } from "@/lib/format";
import { sliceToWindow } from "@/lib/windows";
import { ChartCard, DataTable } from "../cells/ChartCard";
import { SectionPending, WindowGap } from "../cells/EmptyState";
import { TrendChart, trendTableRows, type TrendSeries } from "../cells/TrendChart";
import { hasSuppressed, PanelIntro, type TabProps } from "./shared";

// Fixed key set in contract v1. "Undetermined" wears a neutral gray on purpose —
// it means "no signal", not an identity worth a hue. Aqua and yellow sit below
// 3:1 on this surface; the always-visible totals table is the relief channel.
const LANGS = [
  { key: "de", label: "German", color: "var(--color-accent)" },
  { key: "en", label: "English", color: "var(--color-series-en)" },
  { key: "other", label: "Other", color: "var(--color-series-other)" },
  { key: "undetermined", label: "Undetermined", color: "#6e6c66" },
] as const;

export function LanguageTab({ doc, win }: TabProps) {
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

  const weekly = section.weekly.messages_by_language;
  const series: TrendSeries[] = LANGS.map((lang) => ({
    id: lang.key,
    label: lang.label,
    color: lang.color,
    entries: sliceToWindow(weekly[lang.key].series, win),
  }));
  const footnotes = resolveFootnotes(doc, [weekly.footnote_ids]);
  const anySuppressed = series.some((s) => hasSuppressed(s.entries));

  const totals = section.per_window[win.id]?.totals;
  // Share = language total ÷ the same window's published messages total —
  // division of two published cells, the one client-side arithmetic the
  // contract allows (invariant 4).
  const denominator = doc.sections.usage_context?.per_window[win.id]?.totals.messages;
  const denomValue = denominator?.status === "ok" && denominator.value > 0 ? denominator.value : null;

  return (
    <div>
      {intro}
      <div className="grid gap-4 lg:grid-cols-5">
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
        <div className="lg:col-span-2">
          {totals ? (
            <ChartCard title={`Totals — ${win.label}`} floorN={doc.privacy_floor_n}>
              <table className="w-full text-sm tabular-nums">
                <thead>
                  <tr className="border-b border-hairline text-left text-xs text-ink-2">
                    <th className="py-1.5 font-medium">Language</th>
                    <th className="py-1.5 text-right font-medium">Messages</th>
                    <th className="py-1.5 text-right font-medium">Share</th>
                  </tr>
                </thead>
                <tbody>
                  {LANGS.map((lang) => {
                    const cell = totals[lang.key];
                    return (
                      <tr key={lang.key} className="border-b border-hairline last:border-0">
                        <td className="flex items-center gap-2 py-2 text-ink">
                          <span
                            className="h-2.5 w-2.5 rounded-full"
                            style={{ background: lang.color }}
                            aria-hidden
                          />
                          {lang.label}
                        </td>
                        {cell.status === "ok" ? (
                          <>
                            <td className="py-2 text-right text-ink">{formatCount(cell.value)}</td>
                            <td className="py-2 text-right text-ink-2">
                              {denomValue ? `${Math.round((cell.value / denomValue) * 100)}%` : "—"}
                            </td>
                          </>
                        ) : (
                          <td colSpan={2} className="py-2 text-right text-ink-3">
                            suppressed (&lt; {doc.privacy_floor_n} students)
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
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
      </div>
    </div>
  );
}

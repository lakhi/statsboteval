import type { Aggregates, Finding, TrajectoryPoint } from "@/lib/aggregates.gen";
import { formatStat } from "@/lib/format";
import { resolveFootnotes, symbolsFor } from "@/lib/footnotes";
import { ChartCard, DataTable } from "./ChartCard";
import { TopicRowTip } from "./TopicRowTip";

const TAB_LABELS: Record<Finding["tab"], string> = {
  topics: "Topics",
  adoption: "Adoption",
  engagement: "Engagement",
  timing: "Timing",
  language: "Language",
};

const EVIDENCE_LABELS: Record<Finding["evidence"], string> = {
  robust: "Strong evidence",
  indicative: "Suggestive",
};

/** Signed value in the finding's own unit — pp for shares, minutes, per week, … */
function formatDelta(finding: Finding): string {
  const size = formatStat(Math.abs(finding.delta));
  const unit = finding.kind === "share" ? "pp" : finding.unit;
  return `${finding.delta < 0 ? "−" : "+"}${size} ${unit}`;
}

const decimals = (n: number): number => (Number.isInteger(n) ? 0 : 1);

/**
 * Both sides of a before → after pair at the same precision.
 *
 * formatStat alone drops the decimal on whole numbers, which renders one measure two
 * ways in the same sentence ("16 → 23.1") and reads as a change of precision rather
 * than a change of value.
 */
function formatPair(a: number, b: number): [string, string] {
  const places = Math.max(decimals(a), decimals(b));
  const fmt = (n: number) => n.toLocaleString("en", { minimumFractionDigits: places, maximumFractionDigits: places });
  return [fmt(a), fmt(b)];
}

/**
 * One pipeline-selected finding (contract §7.6).
 *
 * Reads as a stat tile — measure, before → after, delta, optional sparkline — because
 * that is what it is. Two deliberate departures from the usual stat-tile treatment:
 *
 *  - **The delta is not colored by valence.** The standard tile tints the delta by
 *    direction × whether up is good, but almost nothing here has a good direction:
 *    a rising German share is not better or worse than a falling one, and painting it
 *    green or red would editorialize a measurement. Direction is carried by an arrow
 *    and the sign, which say what happened without saying how to feel about it.
 *  - **No suppression key.** Findings have no suppressed state — sub-floor candidates
 *    are dropped in the pipeline and never reach the document.
 */
export function FindingCard({
  doc,
  finding,
  onJumpToTab,
}: {
  doc: Aggregates;
  finding: Finding;
  onJumpToTab: (tabId: string) => void;
}) {
  // Symbols are assigned per card in first-use order, matching every other card.
  const footnotes = resolveFootnotes(doc, [finding.footnote_ids]);
  const rising = finding.delta >= 0;
  const trajectory = finding.trajectory ?? null;
  const [before, after] = formatPair(finding.baseline.value, finding.current.value);

  return (
    <ChartCard
      title={finding.title}
      markers={symbolsFor(footnotes, finding.footnote_ids)}
      footnotes={footnotes}
      floorN={doc.privacy_floor_n}
      table={
        trajectory ? (
          <DataTable
            head={["Period", finding.measure, "Students"]}
            rows={trajectory.map((p) => [
              windowLabel(doc, p.window_id),
              `${formatStat(p.value)} ${finding.unit}`,
              p.n_students,
            ])}
            caption={`${finding.measure} for each semester`}
          />
        ) : undefined
      }
    >
      <p className="text-sm text-ink-2">{finding.measure}</p>

      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-sm text-ink-3">
          {before}
          <span className="mx-1.5 text-ink-3" aria-hidden="true">
            →
          </span>
        </span>
        {/* Proportional figures: this is a standalone headline value, not a column. */}
        <span className="font-display text-2xl text-ink">{after}</span>
        <span className="text-sm text-ink-2">{finding.unit}</span>
        <span className="rounded-full bg-paper px-2 py-0.5 text-xs font-medium text-ink-2">
          <span aria-hidden="true">{rising ? "↑" : "↓"}</span> {formatDelta(finding)}
        </span>
      </div>

      {trajectory ? <Trajectory points={trajectory} doc={doc} unit={finding.unit} /> : null}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <button
          type="button"
          onClick={() => onJumpToTab(finding.tab)}
          className="rounded-full border border-edge px-2.5 py-0.5 text-xs font-medium text-ink-2 transition-colors hover:border-baseline hover:text-ink"
        >
          {TAB_LABELS[finding.tab]} →
        </button>
        <TopicRowTip
          tip={
            <>
              <span className="font-medium text-ink">{EVIDENCE_LABELS[finding.evidence]}.</span>{" "}
              {finding.evidence === "robust"
                ? "This difference still stands out after accounting for how many measures were checked at once."
                : "This difference stands out on its own, but not once the number of measures checked at once is accounted for — read it as a lead, not a result."}{" "}
              Method: {finding.method}.
            </>
          }
        >
          <span className="text-xs text-ink-3">
            <span
              aria-hidden="true"
              className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle ${
                finding.evidence === "robust" ? "bg-accent" : "bg-baseline"
              }`}
            />
            {EVIDENCE_LABELS[finding.evidence]}
          </span>
        </TopicRowTip>
      </div>
    </ChartCard>
  );
}

const SPARK_WIDTH = 220;
const SPARK_HEIGHT = 44;
const SPARK_PAD = 10;

/**
 * Per-semester slope for all_time findings. Hand-rolled SVG rather than a chart
 * library: two to four points, no axes, and one of these renders per card — the
 * primitives-on-demand rule (D-28).
 *
 * Single series, so no legend: the card title already names what is plotted. Earlier
 * points sit in the de-emphasis gray with the latest in the accent, and only the first
 * and last carry a label — labelling every point is what makes sparklines unreadable.
 * Every value stays available in the Data table below.
 */
function Trajectory({
  points,
  doc,
  unit,
}: {
  points: TrajectoryPoint[];
  doc: Aggregates;
  unit: string;
}) {
  const values = points.map((p) => p.value);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1; // a flat trajectory draws a flat line, not a divide-by-zero
  const x = (i: number) =>
    points.length === 1
      ? SPARK_WIDTH / 2
      : SPARK_PAD + (i * (SPARK_WIDTH - 2 * SPARK_PAD)) / (points.length - 1);
  const y = (v: number) =>
    SPARK_HEIGHT - SPARK_PAD - ((v - lo) / span) * (SPARK_HEIGHT - 2 * SPARK_PAD);

  const label = `${points.map((p) => `${windowLabel(doc, p.window_id)} ${formatStat(p.value)} ${unit}`).join(", ")}`;

  return (
    <div className="mt-3 flex items-center gap-3">
      <svg
        width={SPARK_WIDTH}
        height={SPARK_HEIGHT}
        viewBox={`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`}
        role="img"
        aria-label={label}
        className="shrink-0 overflow-visible"
      >
        <polyline
          points={points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ")}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {points.map((p, i) => (
          <circle
            key={p.window_id}
            cx={x(i)}
            cy={y(p.value)}
            r={4}
            fill={i === points.length - 1 ? "var(--color-accent)" : "var(--color-ink-3)"}
            // 2px ring in the surface color so a dot stays legible where it meets the line.
            stroke="var(--color-card)"
            strokeWidth={2}
          />
        ))}
      </svg>
      {/* Text wears text tokens, never the series color. */}
      <div className="min-w-0 text-xs leading-snug text-ink-3">
        <div>
          {windowLabel(doc, points[0].window_id)} · {formatStat(points[0].value)}
        </div>
        <div className="text-ink-2">
          {windowLabel(doc, points[points.length - 1].window_id)} ·{" "}
          {formatStat(points[points.length - 1].value)}
        </div>
      </div>
    </div>
  );
}

/** Registry label for a window id — the pipeline guarantees the id resolves. */
export function windowLabel(doc: Aggregates, id: string): string {
  return doc.windows.find((w) => w.id === id)?.label ?? id;
}

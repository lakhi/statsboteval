// DaypartTotals → a part-to-whole ring, or horizontal bars where a ring would lie (D-54,
// D-60). `DaypartFigure` picks; the two renderings below are what it picks between.
//
// The ring is the primary form since D-60. Dayparts partition the window's messages
// exactly — `aggregate.py` bins each message into one block — so the four counts and the
// published messages total are a whole and its parts, which is the one thing a ring says
// better than anything else. It is drawn against that published total, never against a
// client-side sum of the four cells (invariant 4), and it uses the sequential ramp rather
// than four categorical hues, for the reason the bars give below.
//
// The bars remain, unchanged, as the fallback — and they are not a lesser rendering, they
// are the correct one whenever a ring would assert something untrue:
//
//  * **A suppressed block.** All-or-nothing, as on every other ring here: a ring over the
//    surviving three would show them as the whole day. The bars can say "withheld" in
//    place of one bar and keep the other three readable, which a ring cannot.
//  * **No published messages total for this window and level.** Without a denominator
//    there are no shares to print, and summing the blocks to invent one is exactly the
//    re-aggregation invariant 4 forbids.
//
// Bars are horizontal because the labels ("Afternoon 12–18") are long and a vertical axis
// would either truncate or rotate them. One measure, so one hue — the accent — never a
// per-bar color: the blocks are an ordered sequence, not four identities. The ring honours
// the same claim with a light-to-dark ramp in clock order (see `DAYPART_RAMP`), which is
// the sequence rendered as color instead of as position. Equal-width blocks are what makes
// bar length directly comparable; the daypart_definition footnote says so on the card.

import type { Daypart, DaypartTotals } from "@/lib/aggregates.gen";
import { formatCount } from "@/lib/format";
import { DAYPART_RAMP } from "@/lib/palette";
import { PieShare } from "./PieShare";

type Cell = DaypartTotals["by_daypart"][string];

const hours = (part: Daypart): string =>
  `${String(part.from_hour).padStart(2, "0")}–${String(part.to_hour).padStart(2, "0")}`;

function Bar({ cell, max, floorN, label }: { cell: Cell; max: number; floorN: number; label: string }) {
  if (cell.status === "suppressed") {
    return (
      <div className="flex items-center gap-2">
        <div
          className="suppressed-stipple h-4 w-8 rounded-[3px]"
          title={`${label}: suppressed (< ${floorN} students)`}
        />
        <span className="text-[11px] text-suppressed">withheld</span>
      </div>
    );
  }
  // A measured zero still gets a tick of ink: an empty row reads as "no data",
  // and ok(0) means the opposite — we looked, and nobody wrote.
  const pct = cell.value === 0 ? 0 : Math.max(1.5, (cell.value / max) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-4 min-w-[2px] flex-1 rounded-[3px] bg-paper">
        <div
          className="h-4 rounded-[3px] bg-accent"
          style={{ width: `${pct}%` }}
          title={`${label}: ${formatCount(cell.value)} messages`}
        />
      </div>
      <span className="w-12 shrink-0 text-right text-xs tabular-nums text-ink">
        {formatCount(cell.value)}
      </span>
    </div>
  );
}

/** Weekend/weekday: published as two independently floored cells, never as one number and
 *  a remainder — subtracting across them would recover a withheld side. A second partition
 *  of the same messages, so it rides under either figure rather than inside one. */
function SpanStrip({ totals }: { totals: DaypartTotals }) {
  const span = (cell: Cell) =>
    cell.status === "ok" ? formatCount(cell.value) : <span className="text-suppressed">—</span>;
  return (
    <div className="mt-3 flex gap-6 border-t border-hairline pt-2 text-xs text-ink-2">
      <span>
        Mon–Fri <span className="font-semibold tabular-nums text-ink">{span(totals.weekday)}</span>
      </span>
      <span>
        Sat–Sun <span className="font-semibold tabular-nums text-ink">{span(totals.weekend)}</span>
      </span>
    </div>
  );
}

/**
 * The card's figure: ring where the numbers support one, bars where they do not.
 *
 * The choice lives here rather than in TimingTab so the two preconditions travel with the
 * renderings they gate. `windowMessages` is the window-and-level's published messages
 * total, or null when none is published — see the header for why each blocks the ring.
 */
export function DaypartFigure({
  totals,
  dayparts,
  floorN,
  windowMessages,
  windowLabel,
}: {
  totals: DaypartTotals;
  dayparts: Daypart[];
  floorN: number;
  windowMessages: number | null;
  windowLabel: string;
}) {
  const cells = dayparts.map((part) => totals.by_daypart[part.id]);
  const ringable =
    dayparts.length > 0 &&
    windowMessages !== null &&
    windowMessages > 0 &&
    cells.every((cell) => cell != null && cell.status === "ok");
  if (!ringable) {
    return <DaypartBars totals={totals} dayparts={dayparts} floorN={floorN} />;
  }
  const slices = dayparts.map((part, i) => ({
    key: part.id,
    label: `${part.label} ${hours(part)}`,
    value: (totals.by_daypart[part.id] as { status: "ok"; value: number }).value,
    color: DAYPART_RAMP[i % DAYPART_RAMP.length],
  }));
  return (
    <div>
      <PieShare
        slices={slices}
        total={windowMessages}
        centerLabel={`messages in ${windowLabel}`}
        valueLabel="Messages"
        ariaLabel={`Messages by six-hour block of the day, ${windowLabel}: ${slices
          .map((s) => `${s.label} ${formatCount(s.value)}`)
          .join(", ")}.`}
      />
      <SpanStrip totals={totals} />
    </div>
  );
}

export function DaypartBars({
  totals,
  dayparts,
  floorN,
}: {
  totals: DaypartTotals;
  dayparts: Daypart[];
  floorN: number;
}) {
  const cells = dayparts.map((p) => totals.by_daypart[p.id]).filter(Boolean);
  const max = Math.max(1, ...cells.map((c) => (c.status === "ok" ? c.value : 0)));
  return (
    <div>
      <div
        className="space-y-2"
        role="img"
        aria-label={`Messages by six-hour block of the day; striped bars are suppressed under the privacy floor (fewer than ${floorN} students).`}
      >
        {dayparts.map((part) => {
          const cell = totals.by_daypart[part.id];
          if (!cell) return null;
          const label = `${part.label} ${hours(part)}`;
          return (
            <div key={part.id} className="grid grid-cols-[7.5rem_1fr] items-center gap-2">
              <div className="text-xs text-ink-2">
                {part.label} <span className="text-ink-3 tabular-nums">{hours(part)}</span>
              </div>
              <Bar cell={cell} max={max} floorN={floorN} label={label} />
            </div>
          );
        })}
      </div>
      <SpanStrip totals={totals} />
    </div>
  );
}

export function daypartTableRows(totals: DaypartTotals, dayparts: Daypart[]): (string | number)[][] {
  const value = (cell: Cell | undefined) =>
    cell == null ? "" : cell.status === "ok" ? cell.value : "suppressed";
  return [
    ...dayparts.map((p) => [`${p.label} (${hours(p)})`, value(totals.by_daypart[p.id])]),
    ["Mon–Fri", value(totals.weekday)],
    ["Sat–Sun", value(totals.weekend)],
  ];
}

// Inline caveat marker: provenance and scope on demand, beside the number it governs.
// Hand-rolled and CSS-only, like TopicRowTip, per D-28's primitives-on-demand rule. That
// one wraps a whole row and reveals on hover of the row; this one is an inline marker, so
// it is kept separate rather than generalised — two different anchors, two components.
//
// `group-focus-within` rather than `group-focus-visible` is the load-bearing difference
// (D-58): a tap on a touch device focuses the button but does not satisfy :focus-visible,
// so the focus-visible spelling would leave the caveat unreachable on a phone entirely.
//
// **The tip is anchored to the cell, not to the marker**, so the marker span deliberately
// does NOT create a positioning context — the nearest `relative` ancestor is the KPI tile,
// and the popover spans that tile's width under its bottom edge. A marker-anchored,
// fixed-width popover reads fine at 1152 px and runs off the right of a phone, which is a
// horizontal page scroll rather than a cosmetic nit. Any future host of an InfoTip must
// therefore be `relative`.
//
// Known and accepted: two tips in one cell share that anchor, so focusing one and then
// hovering the other stacks both popovers in the same place. The Active-users tile is the
// only cell with two (the roster rule on its label, the enrolled denominator on its reach
// line) and the combination takes a deliberate keyboard-then-mouse sequence to produce.
// Restructuring the anchor to avoid it would cost the viewport safety above.

import { useId, type ReactNode } from "react";

export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  return (
    <span className="group inline-block">
      <button
        type="button"
        aria-label={label}
        aria-describedby={id}
        // Nothing happens on click; the button exists to be focusable and announced.
        //
        // 24×24 with the glyph centred, not an 11 px glyph with preflight's zero padding:
        // WCAG 2.2 §2.5.8 sets 24×24 as the minimum target, and touch is the exact case
        // `focus-within` was chosen for — solving reachability and then shipping an 11 px
        // target would undo it. The negative margins keep the *optical* position and stop
        // a 24 px inline-flex box from opening up the line it sits in (vertical margins do
        // apply to an atomic inline-level box, unlike a plain inline one).
        className="-my-2 -mx-0.5 inline-flex h-6 w-6 cursor-help items-center justify-center rounded align-middle text-[11px] leading-none text-accent-deep/70 outline-none transition-colors hover:text-accent focus-visible:ring-2 focus-visible:ring-accent/40"
      >
        ⓘ
      </button>
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none invisible absolute inset-x-2 top-full z-20 mt-1 rounded-md border border-edge bg-card p-3 text-left text-[11px] font-normal leading-relaxed text-ink-2 opacity-0 shadow-lg transition-opacity duration-150 delay-150 group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100"
      >
        {children}
      </span>
    </span>
  );
}

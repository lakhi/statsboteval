// Hover/focus tooltip for topic rows: how this number was arrived at. CSS-only
// show/hide (group-hover + group-focus-visible) with a small delay so scanning
// the list doesn't flash tips; hand-rolled rather than a tooltip library per
// D-28's primitives-on-demand rule. The row is focusable so keyboard users get
// the same explanation; `aria-describedby` ties the tip to the row.

import { useId, type ReactNode } from "react";

export function TopicRowTip({ tip, children }: { tip: ReactNode; children: ReactNode }) {
  const id = useId();
  return (
    <div
      tabIndex={0}
      aria-describedby={id}
      className="group relative -mx-1.5 rounded-md px-1.5 py-0.5 outline-none transition-colors hover:bg-paper/60 focus-visible:ring-2 focus-visible:ring-accent/40"
    >
      {children}
      <div
        id={id}
        role="tooltip"
        className="pointer-events-none invisible absolute left-0 top-full z-20 mt-1.5 w-80 max-w-[calc(100vw-3rem)] rounded-md border border-edge bg-card p-3 text-xs leading-relaxed text-ink-2 opacity-0 shadow-lg transition-opacity duration-150 delay-200 group-hover:visible group-hover:opacity-100 group-focus-visible:visible group-focus-visible:opacity-100"
      >
        {tip}
      </div>
    </div>
  );
}

"use client";

// The date filter is a *window picker*: its options are exactly the pipeline's
// published windows registry (contract §6.1) — never a free date range, which
// invariant 4 (no client re-aggregation) rules out by design. A native <select>
// in a pill: keyboard/screen-reader behavior for free, styled to match.

import type { Aggregates } from "@/lib/aggregates.gen";
import { groupedWindows, isInProgress } from "@/lib/windows";

export function WindowPicker({
  doc,
  value,
  onChange,
}: {
  doc: Aggregates;
  value: string;
  onChange: (id: string) => void;
}) {
  const groups = groupedWindows(doc);
  return (
    <label className="relative inline-flex items-center">
      <span className="sr-only">Data window (applies to every tab)</span>
      <svg
        className="pointer-events-none absolute left-3.5 h-4 w-4 text-ink-2"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        aria-hidden
      >
        <rect x="1.5" y="2.5" width="13" height="12" rx="1.5" />
        <path d="M1.5 6h13M5 1v3M11 1v3" />
      </svg>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="cursor-pointer appearance-none rounded-full border border-edge bg-card py-2 pl-10 pr-9 text-sm font-medium text-ink shadow-sm transition-colors hover:border-baseline"
      >
        {groups.map((group) => (
          <optgroup key={group.label} label={group.label}>
            {/* The published `label` verbatim: the group headings are fixed and generic
                ("Recent"), so each option has to name itself — "Previous 4 weeks · SS
                2026". "(in progress)" rides on the semester option only; a slice is
                complete by construction, whatever state its term is in. */}
            {group.windows.map((w) => (
              <option key={w.id} value={w.id}>
                {w.label}
                {isInProgress(w) ? " (in progress)" : ""}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      <svg
        className="pointer-events-none absolute right-3.5 h-3.5 w-3.5 text-ink-2"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        aria-hidden
      >
        <path d="M4 6.5 8 10.5 12 6.5" />
      </svg>
    </label>
  );
}

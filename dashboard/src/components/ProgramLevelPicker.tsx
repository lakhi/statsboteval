"use client";

// The program-level filter (D-55). It sits in the header bar beside the window picker
// rather than inside a panel, because it scopes every tab — the same reasoning that put
// the window picker there. A segmented control rather than a <select>: four options with
// a non-obvious default, where the active value has to stay readable at a glance.

import { ALL, LEVEL_LABELS, type Level } from "@/lib/levels";

export function ProgramLevelPicker({
  levels,
  value,
  onChange,
}: {
  /** Published levels in display order; "All users" is appended here, never by the caller. */
  levels: string[];
  value: Level;
  onChange: (level: Level) => void;
}) {
  if (levels.length === 0) return null;
  return (
    <div
      role="group"
      aria-label="Program level (applies to every tab)"
      className="inline-flex overflow-hidden rounded-full border border-edge bg-card text-sm shadow-sm"
    >
      {[...levels, ALL].map((key) => {
        const selected = key === value;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(key)}
            className={`cursor-pointer px-3.5 py-2 font-medium transition-colors ${
              selected ? "bg-accent text-white" : "text-ink-2 hover:bg-paper hover:text-ink"
            }`}
          >
            {LEVEL_LABELS[key] ?? key}
          </button>
        );
      })}
    </div>
  );
}

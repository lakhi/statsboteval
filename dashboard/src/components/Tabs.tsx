"use client";

import { useRef } from "react";

export type TabDef = { id: string; label: string };

/** WAI-ARIA tabs, automatic activation: arrows move focus and select. */
export function Tabs({
  tabs,
  active,
  onSelect,
}: {
  tabs: TabDef[];
  active: string;
  onSelect: (id: string) => void;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const onKeyDown = (e: React.KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === active);
    let next: number | null = null;
    if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    if (next === null) return;
    e.preventDefault();
    const id = tabs[next].id;
    onSelect(id);
    refs.current[id]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label="Educator questions"
      className="flex overflow-x-auto border-b border-hairline"
    >
      {tabs.map((t) => {
        const selected = t.id === active;
        return (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el;
            }}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={selected}
            aria-controls={`panel-${t.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onSelect(t.id)}
            onKeyDown={onKeyDown}
            className={`whitespace-nowrap border-b-2 px-4 py-2.5 text-sm transition-colors ${
              selected
                ? "border-accent font-semibold text-ink"
                : "border-transparent font-medium text-ink-2 hover:border-baseline hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

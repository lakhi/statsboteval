import type { Aggregates } from "./aggregates.gen";

// APA-style table-note symbols, assigned per card in first-use order — the
// contract's footnote registry rendered in the notation psychology educators
// already read daily.
const SYMBOLS = ["†", "‡", "§", "¶", "#"]; // † ‡ § ¶ #

export type ResolvedFootnote = { id: string; symbol: string; text: string };

/** Resolve footnote ids (deduplicated, order kept) against the registry. */
export function resolveFootnotes(
  doc: Aggregates,
  ids: (string[] | null | undefined)[],
): ResolvedFootnote[] {
  const seen = new Set<string>();
  const resolved: ResolvedFootnote[] = [];
  for (const id of ids.flatMap((list) => list ?? [])) {
    if (seen.has(id)) continue;
    seen.add(id);
    resolved.push({
      id,
      symbol: SYMBOLS[resolved.length % SYMBOLS.length],
      text: doc.footnotes[id]?.text ?? id,
    });
  }
  return resolved;
}

export function symbolsFor(resolved: ResolvedFootnote[], ids?: string[] | null): string {
  return (ids ?? [])
    .map((id) => resolved.find((f) => f.id === id)?.symbol ?? "")
    .join("");
}

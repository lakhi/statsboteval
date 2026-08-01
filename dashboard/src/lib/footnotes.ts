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

/**
 * One footnote's published text, or null when this document does not carry that id.
 *
 * Null rather than `resolveFootnotes`'s id-as-text fallback, and the difference is not
 * cosmetic (D-58). A caveat rendered inside its own cell is prose with no symbol beside
 * it, so a missing id would print the literal string `retention_all_time` where a
 * sentence belongs — and that is a certainty, not a risk: the bundle deploys before the
 * blob, so every newly minted id spends the gap absent from the document the new code is
 * reading. The fallback stays where it belongs, in the paragraph renderers, where an
 * unresolved id reads as the diagnostic it is.
 */
export function footnoteText(doc: Aggregates, id: string): string | null {
  return doc.footnotes[id]?.text ?? null;
}

/** The texts for several ids, skipping any this document does not carry. */
export function footnoteTexts(doc: Aggregates, ids: string[]): string[] {
  return ids.map((id) => footnoteText(doc, id)).filter((text): text is string => text !== null);
}

export function symbolsFor(resolved: ResolvedFootnote[], ids?: string[] | null): string {
  return (ids ?? [])
    .map((id) => resolved.find((f) => f.id === id)?.symbol ?? "")
    .join("");
}

import type { Aggregates } from "./aggregates.gen";

// Same-origin by default (the API serves this bundle, D-26); override for `next dev`
// against a locally running API: NEXT_PUBLIC_API_BASE=http://localhost:8000 pnpm dev
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function fetchAggregates(): Promise<Aggregates> {
  // Design-review mode: NEXT_PUBLIC_DATA_SOURCE=fixture pnpm dev serves the
  // committed synthetic fixture with no API running. The env var is inlined at
  // build time, so production bundles never include this branch or the fixture.
  if (process.env.NEXT_PUBLIC_DATA_SOURCE === "fixture") {
    const fixture = await import("../../dev-fixtures/aggregates.fixture.json");
    return fixture.default as unknown as Aggregates;
  }
  const response = await fetch(`${API_BASE}/api/v1/aggregates`);
  if (!response.ok) {
    throw new Error(`aggregates request failed: ${response.status}`);
  }
  return response.json();
}

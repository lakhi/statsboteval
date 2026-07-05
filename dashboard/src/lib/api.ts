import type { Aggregates } from "./aggregates.gen";

// Same-origin by default (the API serves this bundle, D-26); override for `next dev`
// against a locally running API: NEXT_PUBLIC_API_BASE=http://localhost:8000 pnpm dev
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function fetchAggregates(): Promise<Aggregates> {
  const response = await fetch(`${API_BASE}/api/v1/aggregates`);
  if (!response.ok) {
    throw new Error(`aggregates request failed: ${response.status}`);
  }
  return response.json();
}

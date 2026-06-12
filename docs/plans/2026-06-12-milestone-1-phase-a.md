# Milestone 1 / Phase A — implementation plan (walking skeleton)

**Status: approved 2026-06-12, not yet started.** Produced by the decision-review session
that re-validated D-01…D-15 and recorded D-16…D-20 (`docs/decisions.md`). Part 0 (repo &
docs amendments, Bergmann history rewrite) was executed in that session; Parts 1–4 below
are the work remaining. Review key decisions once more before starting implementation.

## Context

Milestone 1 = the educator-facing dashboard. Per D-07 it is phased: **Phase A** (this plan)
is the descriptive dashboard with no LLM classification; **Phase B** (separate plan, gated
on the Leonardo handover) adds the classification pipeline. Build order is the **walking
skeleton** (D-19): define the aggregates contract, push one synthetic metric end-to-end to
a deployed Azure dashboard early, then widen metric by metric. Real data enters only at the
gated go-live (Part 4); everything before that runs on clearly-labeled synthetic fixtures.

Key facts the plan relies on:
- Direct MySQL access to the production StatsBot DB exists → scripted extract with
  **in-flight pseudonymization** (D-20); identifiers never persisted locally.
- Local corpus = **DuckDB**, one file on the FileVault-encrypted disk (D-17).
- Aggregates blob is **private**; the FastAPI tier is the auth boundary (D-18).
- Binding ethics constraints in `docs/ethics/data-handling.md` (privacy floor N=5 working
  value; no chat text cloud-side, ever).

## Part 1 — Contract & scaffold

**Repo layout** (monorepo, D-02):

```
pipeline/    Python (tooling matched to health-research-agent-api: ruff/mypy/pytest)
  statsboteval_pipeline/{extract,pseudonymize,corpus,aggregate,publish,cli}.py
  migrations/00X_*.sql        # plain numbered DuckDB migrations
  tests/                      # + synthetic fixture generator, clearly labeled synthetic
api/         FastAPI (pattern: ~/Developer/uni-studAsst-projects/ai_agents_ws/api-apps/health-research-agent-api)
dashboard/   Angular SPA (English, D-13)
schema/      aggregates.schema.json — THE contract between pipeline and api/dashboard
```

**Aggregates contract** (`schema/aggregates.schema.json`): one versioned JSON document per
publish. Top level: `schema_version`, `generated_at`, `data_through`, `label_version`,
`privacy_floor_n`, then one section per dashboard view. Cells carry student counts
internally pre-suppression; the published file contains only surviving cells. Source of
truth: pydantic models in `pipeline`, JSON Schema exported as the repo artifact; the API
validates on read; Angular interfaces are written against it.

**Synthetic fixture generator:** fake `students`/`history` rows with realistic shapes
(sessions via shared (`student_id`, `started`), DE/EN text snippets, token counts). Drives
all tests and the skeleton deploy.

## Part 2 — Thin slice, end-to-end, deployed

One metric (weekly message count + weekly active students, floored) through every layer:

1. **Mini-pipeline:** synthetic rows → DuckDB file → aggregate + privacy floor →
   `aggregates_v0.json` → upload to Azure Blob (versioned name + `latest` pointer). Blob
   private; API reads via connection string (D-18).
2. **API:** `GET /api/v1/aggregates` (serves latest, validates against schema, caches) +
   `GET /healthz`. `.env.local`/`.env.azure` switching per the reference pattern.
3. **Dashboard:** single Angular page rendering the metric (chart lib chosen at
   implementation — ngx-charts or ECharts; keep it swappable).
4. **Deploy** both to Azure per the health-research-agent-api pattern → demo URL exists
   from the first week, showing synthetic data clearly labeled as such.

## Part 3 — Widen to the Phase A metric set

Each metric lands as: schema section + aggregation SQL + tests + dashboard view.

- **Temporal usage:** messages/sessions/active students per ISO week; hour-of-day ×
  day-of-week heatmap (server `created_at`, not client `started`).
- **Usage context:** registrations, active vs one-time vs returning users (Bergmann
  comparator), totals.
- **Sessions:** messages-per-session and duration distributions (binned, floored).
- **Tokens:** `completion_tokens` distributions; `prompt_tokens` only as session-context
  growth (see its caveat in `docs/source-data-dictionary.md`) or omitted.
- **Language (pulled forward from Phase B):** local detection (lingua-py) on `sent`,
  stored as label version `lang-heuristic-v1` in the labels table — exercises the D-07
  label-versioning design early; Phase B LLM labels can supersede.

**Validation:** once real data is in, reproduce the Bergmann reference descriptives
(one-time-user %, language shares, token medians) on their date range — divergences
documented (sessionization definitions differ, D-08). Reference values are in the
local-only `docs/bergmann-framework.md` (D-16).

## Part 4 — Real-data go-live (gated, after the skeleton works)

- **Gates** (see `docs/open-questions.md`): recon queries run (matnr/lv, volumes → update
  the data dictionary); pepper generated + custody settled with Daniel; N=5 confirmed;
  Daniel's nod on the architecture. Until all pass, the deployed dashboard shows synthetic
  data, clearly labeled.
- **Extract:** read-only MySQL user if obtainable; incremental by `history.id` watermark;
  in-flight HMAC with normalized `uid`; only pseudonymized rows written to DuckDB on the
  encrypted volume; backups = file copy on the same medium.
- **Erasure runbook:** documented procedure + CLI command (recompute HMAC → DELETE →
  re-aggregate → republish → log completion date).
- **Cadence:** one CLI entry point (`statsboteval run-weekly`) doing
  extract → ingest → aggregate → publish.

## Verification

- **Unit (pytest):** HMAC determinism + uid normalization; privacy floor (cells <N never
  survive — property-based test); aggregation correctness on fixtures with hand-computed
  answers; schema round-trip (pipeline output validates; API rejects invalid).
- **Publish guard:** automated pre-publish assertion — no cell below N, no fields outside
  the schema (structurally excludes chat text cloud-side).
- **E2E (synthetic):** fixture → pipeline → Azurite (local blob emulator) → API → dashboard
  renders; then the same against real Azure on the demo URL.
- **Real-data check (local only):** Bergmann descriptives reproduction.

## Out of scope (separate plans)

Phase B classification (Leonardo handover), dashboard auth (D-12 revisit), milestone 2 ML.

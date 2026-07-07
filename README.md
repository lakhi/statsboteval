# StatsBotEval

An automated evaluation framework for student–GenAI interactions — master's thesis project
(MEi:CogSci, University of Vienna). StatsBotEval analyzes chat data from **StatsBot**, a
GPT-based statistics chatbot used by psychology students at the University of Vienna since
March 2025, and surfaces aggregated, non-identifying insights to educators through a dashboard.

**Status:** Milestone 1, Phase A Part 2 complete — the thin slice runs end-to-end, and the
dashboard carries the full Phase A information architecture: five educator-question tabs
with a global semester/window filter (D-32), on synthetic data, clearly bannered. Hosting
is migrating from the interim App Service F1 to Container Apps (D-31); the demo URL will be
recorded here once migrated (ops notes in `infra/README.md`).

## Layout

- `docs/` — research context (abstract), ethics constraints, source data dictionary,
  decision log, open questions, implementation plans (`docs/plans/`)
- `pipeline/` — local batch pipeline: DuckDB corpus, synthetic fixtures, aggregation +
  privacy floor, publish guard, blob publishing (`python -m statsboteval_pipeline.cli`)
- `schema/` — the aggregates contract as a generated, drift-checked JSON Schema artifact
- `api/` — FastAPI aggregates service (reads the blob, serves the dashboard bundle)
- `dashboard/` — Next.js static-export educator dashboard (types generated from the schema)
- `infra/` — az-CLI provisioning/release scripts + ops README
- `scripts/e2e_local.sh` — full local end-to-end check (Azurite → pipeline → API → bundle)
- `CLAUDE.md` — working instructions for AI-assisted development

(The Bergmann et al. classification-framework reference is kept local-only until the
underlying study is published — see decision D-16 in `docs/decisions.md`.)

## Data

See `docs/ethics/data-handling.md` for the binding constraints.

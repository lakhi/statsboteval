# StatsBotEval

An automated evaluation framework for student–GenAI interactions — master's thesis project
(MEi:CogSci, University of Vienna). StatsBotEval analyzes chat data from **StatsBot**, a
GPT-based statistics chatbot used by psychology students at the University of Vienna since
March 2025, and surfaces aggregated, non-identifying insights to educators through a dashboard.

**Status:** Milestone 1 — **live on real data** since 2026-07-17 (D-37). The weekly
pipeline extracts from the production DB (read-only, in-flight pseudonymization),
aggregates the full Phase A metric set under the N=3 privacy floor, and publishes to the
dashboard: five educator-question tabs with a global semester/window filter (D-32) at
**https://statsboteval.azurewebsites.net** — only floored, non-identifying aggregates
exist cloud-side. The Topics tab awaits Phase B (classification). Hosting stays on the
interim App Service F1 for now (Container Apps migration deferred, D-31; ops notes in
`infra/README.md`).

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

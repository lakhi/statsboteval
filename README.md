# StatsBotEval

An automated evaluation framework for student–GenAI interactions — master's thesis project
(MEi:CogSci, University of Vienna). StatsBotEval analyzes chat data from **StatsBot**, a
GPT-based statistics chatbot used by psychology students at the University of Vienna since
March 2025, and surfaces aggregated, non-identifying insights to educators through a dashboard.

**Status:** Milestone 1 — **live on real data** since 2026-07-17 (D-37), with Phase B
classification complete and published. The weekly pipeline extracts from the production DB
(read-only, in-flight pseudonymization), classifies each message with an LLM against a
versioned codebook, aggregates under the N=3 privacy floor, and publishes to the dashboard:
five educator-question tabs plus **Topics**, with a global semester/window filter (D-32).
A **Trends** tab (pipeline-selected period comparisons, D-49) is built and tested but not
yet published. Only floored, non-identifying aggregates exist
cloud-side; no chat text ever leaves the local machine except transiently to the consented
EU classification endpoint.

Corpus scale: 550 students / 4,419 messages / 15 frozen emergent themes. Published labels
are **`statsboteval-v2`** since 2026-07-28 (D-45), scoring average MCC **.823** against the
300 human-consensus messages of the reference study (previous version: .714). Label versions
coexist in the corpus, so the superseded one remains available as a comparison baseline and
rollback path.

The weekly run is **not yet scheduled** — each publish is a manual operator run
(`docs/plans/2026-07-27-weekly-run-automation.md`). Hosting stays on the interim App Service
F1 for now (Container Apps migration deferred, D-31; ops notes in `infra/README.md`).

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

(The Bergmann et al. classification framework underpins the deductive codebook. Their
Stage-2 manuscript, coded dataset and theme lists are public — OSF `v8ydk` and Zenodo
`10.5281/zenodo.20827020` (D-22) — but our derived codebook materials stay local-only and
git-ignored pending formal PCI RR recommendation; see D-16/D-22 in `docs/decisions.md`.)

## Data

See `docs/ethics/data-handling.md` for the binding constraints.

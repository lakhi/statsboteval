# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**StatsBotEval** — an automated evaluation framework for student–GenAI interactions; Akshay
Lakhi's master's thesis project (MEi:CogSci, University of Vienna). It analyzes chat data
produced by **StatsBot** (separate repo: `~/Developer/uni-studAsst-projects/statsbot`, a
Laravel + Angular GPT chat client in production since March 2025) and presents aggregated
insights to educators.

Three milestones: (1) educator-facing dashboard, (2) exploratory ML analysis (GBDT + SHAP vs
course performance), (3) master's thesis. See `docs/research-context.md`.

**Current status: planning stage, milestone 1 plan approved.** No application code exists
yet. The M1 Phase A plan lives at `docs/plans/2026-06-12-milestone-1-phase-a.md` (walking
skeleton, synthetic fixtures first). Nothing in `docs/open-questions.md` blocks Phase A
development; the items there gate real-data go-live (Daniel), thesis interpretation
(Wolfgang), and Phase B (Leonardo handover).

## Binding constraints — read before any data-touching work

From the informed-consent addendum (`docs/ethics/informed-consent-addendum.pdf`, summarized in
`docs/ethics/data-handling.md`):

1. **No student data ever enters this repo or any cloud database.** Pseudonymized chat
   histories live on a password-protected LOCAL storage medium only (until end of 2027).
2. The cloud (Azure) side receives **only aggregated, non-identifying outputs** that have
   passed the privacy floor (aggregate cells covering fewer than N≈5 students are suppressed
   at aggregation time, locally).
3. Sending chat text to Azure OpenAI for classification is consistent with consented practice
   (EU data centers); storing it in the cloud is not.
4. Data lifecycle deadlines (deletion window until end of July 2027, anonymize-and-publish to
   OSF afterwards) are documented in `docs/ethics/data-handling.md`.

## Planned architecture (agreed 2026-06-10, amended 2026-06-12, see docs/decisions.md)

```
LOCAL (password-protected machine)                 AZURE (dashboard public by URL)
weekly Python batch pipeline:                      Blob: versioned aggregates file (private)
  extract (direct MySQL, in-flight                 FastAPI aggregates API (reads blob;
  pseudonymize HMAC(uid, pepper))                    future auth boundary)
  → DuckDB corpus (one file, encrypted             Angular SPA dashboard (English)
  disk) → classify (Bergmann prompts,              — no chat text exists cloud-side
  versioned labels) → aggregate +
  privacy floor → publish to Blob
```

- Deployment pattern follows `~/Developer/uni-studAsst-projects/ai_agents_ws/api-apps/health-research-agent-api`
  (FastAPI, Docker, `.env.local`/`.env.azure` switching, ruff/mypy/pytest).
- Classification labels are versioned (`bergmann-v1` imported, `statsboteval-v1` from our
  pipeline); the dashboard reads one configured version.
- A "conversation" = one `started` session, keyed by (`student_id`, `started`) (StatsBot's
  app-native grouping; see `docs/source-data-dictionary.md` for `started` semantics and
  other source-schema gotchas).

## Conventions

- Source-of-truth docs live in `docs/`; update `docs/decisions.md` (ADR-style) when a
  significant choice is made or reversed.
- The StatsBot source schema is documented in `docs/source-data-dictionary.md`; if the
  StatsBot repo's schema changes, update that file in the same change.
- Never weaken `.gitignore` data exclusions. Test fixtures must be synthetic and clearly
  labeled as such.

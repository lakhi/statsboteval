# StatsBotEval

An automated evaluation framework for student–GenAI interactions — master's thesis project
(MEi:CogSci, University of Vienna). StatsBotEval analyzes chat data from **StatsBot**, a
GPT-based statistics chatbot used by psychology students at the University of Vienna since
March 2025, and surfaces aggregated, non-identifying insights to educators through a dashboard.

**Status:** planning / documentation stage — no application code yet.

## Layout

- `docs/` — research context (abstract), ethics constraints, source data dictionary,
  decision log, open questions, implementation plans (`docs/plans/`)
- `CLAUDE.md` — working instructions for AI-assisted development

(The Bergmann et al. classification-framework reference is kept local-only until the
underlying study is published — see decision D-16 in `docs/decisions.md`.)

## Data

This repository contains **no student data and never will**.
See `docs/ethics/data-handling.md` for the binding constraints.

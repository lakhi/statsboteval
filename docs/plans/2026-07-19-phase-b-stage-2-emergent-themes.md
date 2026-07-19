# Phase B Stage 2 — emergent themes (Tasks 12 + 20b execution plan)

**Date:** 2026-07-19 · **Status:** complete (D-43)
**Parent plan:** `2026-07-06-phase-b-classification-pipeline.md` (Task 12 spec, Task 20b
operator run) · **Decisions:** D-33 (reviewed emergent pass), D-38 (staging), D-41
(model + settings), D-42 (Stage 1 live)

## Goal

Fill the Topics tab's fourth card: run our own two-stage inductive pass over the real
corpus, freeze the operator-reviewed list as `statsboteval-themes-v1`, assign, and
republish. Everything downstream of the labels already exists and is live — the
contract (`emergent_themes` + `theme_set_version`, schema 1.1.0), the aggregator
(`_TOPIC_DOMAINS` includes `emergent_theme`, floored, by_status), the dashboard card
(currently rendering its designed absent state), and the synthetic E2E path
(`run-synthetic --with-labels` seeds `emergent_theme` rows under
`SYNTHETIC_THEME_SET_VERSION`). This plan builds only the generation machinery and the
operator run.

## Context deltas since the Task 12 spec was written (2026-07-07)

- Migration numbering confirmed: `004_student_status.sql` shipped (Task 21), so the
  theme tables take **005** as the spec anticipated.
- The classify stack grew Stage-1 hardening that generation and assignment inherit for
  free: strict Markdown-table parsing with corrective-retry + reasoning-effort ladder,
  numbered theme labels (model returns digits; label strings never round-trip),
  120 s request timeout, per-batch commit + heartbeat, idempotent anti-join resume.
- D-41 pins the model + settings: `statsboteval-5-mini` deployment (DZS, Sweden
  Central), `gpt-5-mini@2025-08-07`, base reasoning effort `low`. The emergent
  assignment writes into the **same `statsboteval-v1` label version** (one version =
  one model + settings; assignment satisfies this).
- `erase.py` deletes from a fixed table list that does not yet include
  `theme_candidates` — Task 17 flagged this exact follow-up for Stage 2.

## Design decisions folded in (operator can veto at review)

1. **Codes and themes are English**, whatever the message language (~half the corpus is
   German). The dashboard is English and the frozen Bergmann lists are English; a mixed
   list would fragment counts across translations.
2. **Theme-set selection is configured, not inferred:** `CLASSIFIER_THEME_SET_VERSION`
   (default `statsboteval-themes-v1`) mirrors `CLASSIFIER_LABEL_VERSION`. `run-weekly`
   chains `assign-themes` and passes `theme_set_version` to `build_aggregates` only
   when the configured set exists **and is reviewed**; otherwise both are skipped and
   the publish stays Stage-1-shaped (still valid 1.1.0).
3. **Review file is a Markdown table** (`| theme | description |`) written to
   `pipeline/data/theme-draft-<set_version>.md` (git-ignored). The operator edits it in
   place — merge, rename, cut, never quote chat text — then `freeze-themes` loads it and
   stamps `reviewed_at`. **This review is the privacy control (D-33):** the draft is
   derived from real chat text and nothing from it may reach the repo or the cloud
   until the operator has approved every label.
4. **Synthesis targets ~12–20 themes** (guidance in the prompt, not a hard limit) — the
   card is a distribution, not a taxonomy; the operator adjusts granularity at review.
5. **Assignment provenance** records both lineages:
   `<model_tag>#<set_version>` (e.g. `gpt-5-mini@2025-08-07#statsboteval-themes-v1`).

## Tasks

### S2-1: Migration 005 + erasure coverage

**Files:** `pipeline/migrations/005_theme_sets.sql`,
`pipeline/statsboteval_pipeline/erase.py`, `pipeline/tests/test_erase.py` (extend).

- `theme_candidates` (`history_id BIGINT, run_id TEXT, code TEXT`,
  PK all three) — run-scoped raw candidate codes, **local forever, never published**.
- `theme_sets` (`set_version TEXT, code TEXT, description TEXT, created_at TIMESTAMP,
  reviewed_at TIMESTAMP NULL`, PK (`set_version`, `code`)) — usable only once
  `reviewed_at` is stamped.
- `erase-student` gains the `theme_candidates` delete (keyed via messages → pseudonym);
  test proves a candidate row for the erased student disappears.
- [x] Failing tests → implement → suite green.
- [x] Commit: `Add theme_sets migration and cover theme_candidates in erasure`

### S2-2: Stage 1 — candidate-code generation (`generate.py`)

**Files:** `pipeline/statsboteval_pipeline/classify/generate.py`,
`prompts.py` (+ `build_candidate_prompt`), `parse.py` (+ `parse_candidates`),
`pipeline/tests/classify/test_generate.py`.

- Per ≤50-message batch (reuse the runner's batching/transaction/heartbeat pattern):
  prompt for 1–3 short candidate codes per message — instructed **generic wording,
  ≤5 words, English, no verbatim quotes, no names/identifiers**, `none` allowed for
  content-free messages.
- Strict Markdown-table parse (`| Message | Codes |`); deviations rejected and retried
  with parser feedback up the effort ladder — same discipline as Task 7/9; codes
  normalized (lowercased, whitespace-collapsed) before storage.
- Idempotent per (`history_id`, `run_id`): anti-join on `theme_candidates`, resumable
  after kills.
- [x] Failing tests (stub client): candidates written idempotently; malformed output
      rejected then recovered via corrective retry; normalization applied; `none` rows
      write nothing.
- [x] Commit: `Add stage-1 emergent candidate-code generation`

### S2-3: Stage 2 — synthesis to a reviewable draft (`synthesize.py`)

**Files:** `pipeline/statsboteval_pipeline/classify/synthesize.py`,
`pipeline/tests/classify/test_synthesize.py`.

- Input: the **distinct candidate-code list with frequencies** for a `run_id` — codes
  only, **no chat text is re-sent** (asserted in tests against the built prompt).
- One LLM call consolidates into a draft theme list (~12–20, label + one-line
  description); strict table parse; write the draft review file
  (`pipeline/data/theme-draft-<set_version>.md`) — never into `theme_sets` directly.
- [x] Failing tests: prompt contains codes only; draft file round-trips through the
      freeze loader; malformed synthesis output rejected.
- [x] Commit: `Add stage-2 theme synthesis to a reviewable draft file`

### S2-4: CLI wiring + weekly chaining

**Files:** `pipeline/statsboteval_pipeline/cli.py`, `classify/config.py`
(+ `classifier_theme_set_version`), `classify/step.py` (+ assignment entry point),
`pipeline/tests/test_cli.py` (extend), `.env.example`, `scripts/e2e_local.sh` (already
asserts emergent items via fixtures — verify unchanged),
`docs/runbooks/classification.md` (extend).

- Subcommands: `generate-themes` (S2-2 + S2-3, `--run-id` defaulting to the configured
  set version) · `freeze-themes` (reads the reviewed draft file → `theme_sets`, stamps
  `reviewed_at`; refuses an empty or duplicate-label file) · `assign-themes` (Task 6's
  `build_theme_prompt` + Task 9's runner with the frozen list, `domain='emergent_theme'`,
  provenance per decision 5; **raises if the set is missing or unreviewed**).
- `run-weekly`: after `classify`, chain `assign-themes` when the configured set is
  reviewed; pass `theme_set_version` into `build_aggregates` under the same condition;
  `--skip-classify` skips both.
- Runbook: generation → **operator review (the D-33 privacy control, spelled out)** →
  freeze → assign → republish; theme-set regeneration note (v2 = new set version, new
  review; per-semester cadence per D-38).
- [x] Failing tests: unreviewed set → `assign-themes` raises; `freeze-themes` stamps
      and is idempotent-safe; `run-weekly` chains assignment only with a reviewed set;
      aggregates carry `theme_set_version` iff assignment ran.
- [x] Commit: `Wire emergent-theme CLI and weekly chaining`

### S2-5 (operator, real data): Task 20b — generate, review, freeze, assign, republish

- [x] `generate-themes` over the real corpus (~4.4k messages ≈ 90 Stage-1 calls +
      1 synthesis call; minutes of wall time at Stage-1's observed pace).
- [x] **Akshay reviews the draft list** — short, generic, non-identifying labels only.
- [x] `freeze-themes` → `statsboteval-themes-v1` · `assign-themes` (~90 calls).
- [x] Re-aggregate → publish guard → republish → redeploy check: `emergent_themes` +
      `theme_set_version` live on the Topics tab.
- [x] Record D-43 in `docs/decisions.md` (set version, size, model, date); tick
      Tasks 12/20b in the parent plan; mark Phase B complete.

## Out of scope

Bergmann's set-conditioned inductive passes (unchanged from parent plan); milestone 2
(GBDT + SHAP) and milestone 3 (thesis) — planned next month; any dashboard change (the
card and its absent state already shipped in Task 15).

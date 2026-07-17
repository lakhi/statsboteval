# Go-live first — real-data dashboard on the Phase A metric set (implementation plan)

**Goal:** take the deployed dashboard from synthetic to **real production data** on the
five-tab Phase A information architecture (D-32), *without* waiting for classification.
The pipeline widens from the thin slice (one `temporal_usage` weekly series, one all-time
window) to the full Phase A section set — `temporal_usage` (+heatmap), `usage_context`,
`sessions`, `tokens`, `language` — plus the semester/trailing windows registry, all
privacy-floored, published with `data_provenance: "production"` (which retires the
synthetic banner by itself). The Topics tab keeps rendering its designed "not in this
data release yet" state (contract invariant 5) until Phase B resumes.

**Status: drafted 2026-07-17 (D-35/D-36), in progress.** Supersedes the *sequencing* of
the Phase B plan (2026-07-06), not its content: Phase B Tasks 5–16 and 18–19
(classification, themes, topics) resume after go-live; Tasks 4 and 17 are pulled into
this plan verbatim (shared infrastructure / publish precondition); Task 3 is **skipped as
satisfied** (D-35 — the 2026-07-17 row-level verification against the public Bergmann
dataset, recorded in `bergmann-framework.md`).

## Context

- Contract v1.0.0 already models every Phase A section and window kind
  (`pipeline/statsboteval_pipeline/contract.py`); the dashboard already renders them all
  (built against the schema-validated fixture). **No schema or dashboard changes are
  expected** — this plan is aggregation, labels-table plumbing, and operator steps.
- The corpus is real, current (extracted through 2026-07-14: 550 students / 4,419
  messages), and validated field-for-field against the published Bergmann window.
- Go-live preconditions per D-33/D-34, restated for this plan: gates closed (D-34),
  recon done, extract proven (D-35), **erasure runbook in place (Task GL6)**, publish
  guard green.
- Data-locality rules unchanged: only floored aggregates leave the machine; language
  detection runs **locally** (lingua-py) — no chat text goes anywhere.

## Global constraints

- TDD per task: failing tests (synthetic fixtures only — CI never sees real data) →
  implement → full suite green (`ruff`, `mypy`, `pytest`) → commit.
- Work from `pipeline/` unless noted; commit after each task.
- Aggregation reads the corpus read-only; all floor decisions happen at aggregation
  time on **distinct-student counts** per cell/bin (floor N=3, D-34).

### Task GL1: Windows registry (semesters, trailing_4, all_time)

**Files:** `pipeline/statsboteval_pipeline/windows.py`, `pipeline/tests/test_windows.py`.

**Produces:** `build_windows(axis) -> list[Window]` (axis = the dense complete-week
axis the aggregator already computes; `axis_start` is applied upstream in GL4 as an
event filter before the axis exists) implementing contract
§6.1: a week belongs to the semester containing its **Thursday**; SS = Mar 1–Jun 30,
WS = Oct 1–Jan 31 (label style: `Summer semester 2025`, `Winter semester 2025/26`, ids
`2025S`/`2025W`); Feb and Jul–Sep weeks are break weeks (all_time/trailing only);
`trailing_4` = last 4 complete weeks, recomputed each publish; semester `weeks` = full
membership, `coverage` = clipped to the data range.

- [ ] Failing tests: hand-computed semester assignment across year/semester boundaries
      (incl. the Thursday rule on New-Year weeks); trailing_4 contents; coverage
      clipping when a semester is partially covered by data.
- [ ] Implement; full suite green.
- [ ] Commit: `Add windows registry (semesters, trailing, all-time)`

### Task GL2: Versioned labels table (corpus migration 003) — Phase B Task 4, verbatim

Schema and helpers exactly as specified in the Phase B plan (labels keyed by
`(history_id, label_version, domain, code)`; `write_labels` upsert / `read_labels` /
`label_versions_present`). Needed now because `lang-heuristic-v1` labels live here;
Phase B's LLM labels land in the same table later with no further migration.

- [ ] Failing tests: migration applies on an existing 001+002 corpus; round-trip;
      versions coexist; upsert idempotent.
- [ ] Implement; full suite green.
- [ ] Commit: `Add versioned labels table to the corpus`

### Task GL3: Local language detection (`lang-heuristic-v1`)

**Files:** `pipeline/statsboteval_pipeline/language.py`, CLI subcommand
`detect-language`, `pipeline/tests/test_language.py`; `lingua-language-detector`
dependency.

**Produces:** a local pass over `messages.sent` writing labels
(`domain='language'`, codes `de`/`en`/`other`/`undetermined`, value 1) as version
`lang-heuristic-v1`. Detector configured with a broad language set so `other` is
reachable; low-confidence or very short inputs → `undetermined` (mirrors the registered
`language_heuristic` footnote). Idempotent: skips messages already labeled with this
version; `label_versions` metadata key `language: lang-heuristic-v1` flows into the
aggregates document.

- [ ] Failing tests (synthetic strings): clear German → `de`, clear English → `en`, a
      third language → `other`, gibberish/short → `undetermined`; idempotent re-run;
      labels written under the right version/domain.
- [ ] Implement; full suite green.
- [ ] Commit: `Add local language detection as lang-heuristic-v1 labels`

### Task GL4: Widen aggregation to the full Phase A section set

**Files:** `pipeline/statsboteval_pipeline/aggregate.py` (extend),
`pipeline/tests/test_aggregate.py` (extend).

**Produces:** `build_aggregates` emitting, per contract v1.0.0, with every `per_window`
keyed by the GL1 registry:

- `temporal_usage`: existing weekly series + per-window **hour×day heatmap** (168 dense
  cells, Vienna local time, distinct-student floor per cell).
- `usage_context`: weekly `registrations` (from `students.registered_at`); per-window
  `totals` (active students, messages, sessions, new registrations) and `user_classes`
  (one-time / monthly / sporadic) using the **pinned Bergmann operationalizations**
  (`bergmann-framework.md` "Exact operationalizations": one-time = span < 3 calendar
  days AND ≤ 24 h; monthly(=occasional) = all gaps < 30 days AND span ≥ 30; sporadic =
  the rest), computed within each window's coverage.
- `sessions`: per-window `messages_per_session` and `session_duration_minutes`
  histograms (duration = last−first `created_at` in the session; single-message
  sessions = 0 min, footnoted); fixed bin edges chosen once from the contract's fixture
  precedent; per-bin distinct-student floor.
- `tokens`: per-window `completion_tokens_per_message` histogram (contract deliberately
  omits `prompt_tokens` — its context-growth caveat is documented in the data
  dictionary).
- `language`: weekly `messages_by_language` (de/en/other/undetermined) and per-window
  totals, joined from `lang-heuristic-v1` labels; messages lacking a label count as
  `undetermined`.
- Axis start: aggregation takes an `axis_start` config (see open question 1 — pilot
  traffic before 2025-03 may be excluded from publish; the corpus itself keeps
  everything).

- [ ] Failing tests: hand-seeded synthetic corpus with hand-computed expected values
      per section; floor behavior per cell/bin/heatmap; window-key completeness
      (every `per_window` key in the registry); schema round-trip of the full document.
- [ ] Implement; full suite green; regenerate `schema/aggregates.schema.json` drift
      check (no changes expected — assert that).
- [ ] Commit: `Widen aggregation to the full Phase A section set`

### Task GL5: `run-weekly` CLI + provenance switch

**Files:** `pipeline/statsboteval_pipeline/cli.py` (extend), `pipeline/tests/test_cli.py`.

**Produces:** `run-weekly --corpus … [--out …] [--upload]` chaining
extract → detect-language → aggregate (`provenance="production"`) → publish guard →
write/upload. `--out` without `--upload` supports the operator-review step in GL7.
`run-synthetic` keeps its current behavior (fixtures, `provenance="synthetic"`).

- [ ] Failing tests (stubbed source/publisher): stage order, guard failure blocks
      upload, provenance set correctly.
- [ ] Implement; full suite green.
- [ ] Commit: `Add run-weekly pipeline entry point`

### Task GL6: Erasure runbook + CLI — Phase B Task 17, verbatim (publish precondition)

Exactly as specified in the Phase B plan: `erase-student --uid …` → recompute HMAC →
delete across `students`/`messages`/`labels` → re-aggregate → republish (guarded) →
git-ignored local log; runbook `docs/runbooks/erasure.md` (flow, Daniel as erasure
contact, pepper dependency per D-34).

- [ ] Failing tests (synthetic corpus, fake publisher): exact-row deletion,
      re-aggregation reflects removal, unknown uid = warned no-op, log appended.
- [ ] Implement; full suite green.
- [ ] Commit: `Add student erasure procedure (recompute, delete, re-aggregate, republish)`

### Task GL7 (operator, real data): first real publish

- [ ] Fresh `extract` run (VPN) to be current; `detect-language` over the corpus.
- [ ] `run-weekly --out` locally; **operator reviews the JSON** (spot-check counts,
      suppression, window labels; confirm no unexpected fields — guard enforces
      structurally, review confirms semantically).
- [ ] `run-weekly --upload` to the production blob; verify the deployed dashboard
      serves real data, synthetic banner gone, all five tabs correct, Topics shows its
      designed empty state.
- [ ] Update `README.md` status + demo URL note; record the go-live date in
      `docs/decisions.md`; close the corresponding `docs/open-questions.md` items.
- [ ] Commit: `Record first real-data publish`

## Verification summary

- CI: full synthetic-fixture suite (`ruff`, `mypy`, `pytest`), schema drift check.
- `scripts/e2e_local.sh` still green (synthetic path untouched).
- Real-data verification is GL7's operator review + the already-recorded extract
  validation (D-35); no ongoing Bergmann comparison (it was a one-time ETL check).

## Out of scope (→ resumes after go-live)

- Everything classification-shaped: Phase B Tasks 5–16, 18–19 (Azure OpenAI client,
  codebook, runner, bergmann-v1 import, MCC harness, emergent themes, `topics`
  section/schema 1.1.0, Topics tab, provisioning, validation run).
- Container Apps migration (D-31) — hosting stays on the interim App Service F1.
- `trailing_1` window, program-level (BA/MA) splits in published aggregates.

## Open questions (owner) — resolved 2026-07-17

1. **Axis start / pilot traffic:** ~~open~~ **Decided (owner):**
   `axis_start = 2025-03-01` (production launch). Jul 2024–Feb 2025 rows (developer
   testing, 1–2 users/month, sub-floor anyway) stay in the corpus but out of published
   aggregates.
2. **Publish flow:** ~~open~~ **Decided (owner):** local JSON review in GL7, then
   publish straight to the existing public blob/demo URL — no staging blob.

## Related decisions

D-07 (phasing), D-24/D-34 (floor N=3, gates), D-28/D-29 (thin slice, deploy),
D-32 (tab IA), D-33 (Phase B re-scope), **D-35 (extract validated, Task 3 skipped),
D-36 (go-live-first re-sequencing)** — see `docs/decisions.md`.

# Phase B — classification pipeline (implementation plan)

**Goal:** add automated message classification to StatsBotEval. The local weekly pipeline
gains a `classify` stage that codes each message against the Bergmann deductive scheme (13
binary categories) and assigns methods/software themes, stores versioned labels in the
DuckDB corpus, aggregates them into a new privacy-floored `topics` section of the aggregates
contract, and renders a dashboard topics view. A validation harness measures our classifier
(`statsboteval-v1`) against the team's published labels (`bergmann-v1`) on the public
1,400-message dataset. Chat text is sent only to Azure OpenAI EU (Data Zone Standard) for
transient classification; only floored aggregates ever leave the local machine.

**Status: drafted 2026-07-06, not started.** Phase A Part 2 shipped 2026-07-06; Parts 3–4
remain and follow this plan (sequencing decision below). Prerequisite decisions confirmed
2026-07-06 (see `docs/decisions.md` D-30): scope = deductive 13 + methods/software theme
assignment; classifier pinned to **gpt-5-mini** (escalate to gpt-5.1 only on a weak
category); consolidated multi-label prompt; validate on the public 1,400 messages (no
go-live gate); topics enters the existing contract as an additive **schema 1.1.0** minor
bump under the unchanged `v1/` blob prefix.

## Context & sequencing

Milestone 1 is phased (D-07): Phase A = descriptive dashboard (Parts 1–2 done, 3–4 remain),
**Phase B = this classification pipeline**. Per the 2026-07-06 re-scope, Phase B is built
**before** Phase A Parts 3–4: it is the thesis core, it is fully unblocked, and it de-risks
the largest technical unknown (the LLM classifier) early.

**Two-phase build, matching Part 4's local-vs-cloud split:**

- **Buildable now, no gate** — every task below is developed and tested against **synthetic
  fixtures** plus, for validation, the **public** Bergmann dataset (raw 1,400 messages on
  Zenodo + coded `full_dataset.csv` on OSF, both open access since 2026-06-30). No
  production corpus and no Azure OpenAI live call is required for CI: the Azure client is
  faked in tests. The validation *run* uses public data only, so it needs no consent gate.
- **Gated with Part 4** — running `statsboteval-v1` classification over the **real**
  production corpus and **publishing** real `topics` aggregates. Local classification of
  real chat text via Azure OpenAI EU is consented practice (D-24 sequencing note; the
  architecture-sign-off go-live gate explicitly names this Azure OpenAI path), but the
  floored topic aggregates only go cloud-side once the three go-live gates close
  (`docs/open-questions.md`).

**Data-locality rules (binding, unchanged):** the Bergmann prompt texts, frozen theme
lists, and the public validation dataset are **git-ignored local files** (D-16; owner
reaffirmed 2026-07-06 — they go public only when the team's paper is formally recommended).
No real data — public or not — enters git; all committed fixtures are synthetic and
`SYNTHETIC`-labeled. Labels live only in the local corpus; the `topics` schema carries
**counts, never message text** (contract invariant 6, enforced by the publish guard).

## Architecture (decisions D-07, D-16, D-22, D-24, D-25, D-30)

```
LOCAL weekly pipeline (extends the existing package)          AZURE (unchanged shape)
  extract → corpus (DuckDB)                                   Blob: v1/ aggregates + latest
  classify  ← NEW: statsboteval_pipeline/classify/            FastAPI serves them verbatim
    codebook.py   13 deductive blocks + method/software         + the dashboard bundle
                  theme lists, loaded from git-ignored          (topics view added)
                  BERGMANN_PROMPTS_DIR (synthetic in tests)
    prompts.py    consolidated multi-label prompt build
    client.py     Azure OpenAI (openai.AzureOpenAI),          Chat text → Azure OpenAI EU
                  Data Zone Standard, gpt-5-mini, seed +      (Data Zone Standard, transient,
                  reasoning_effort, 429 backoff               consented) — never persisted
    parse.py      strict Markdown-table → label matrix         cloud-side
    runner.py     batch 50/call, idempotent by
                  (history_id, label_version), resumable
  labels.py       versioned labels table (migration 002)
  import_bergmann.py  bergmann-v1 ← public full_dataset.csv
  validate.py     per-category MCC vs bergmann-v1 (300
                  human-consensus rows = ground truth)
  aggregate.py    += topics section (floored, per window)     schema 1.1.0 (additive; v1/
  contract.py     += TopicsSection, label_versions.classification   prefix unchanged)
```

**Tech stack additions (pipeline):** `openai>=1.40` (AzureOpenAI client), `azure-identity`
(token auth alternative to API key; already used in `api/`). MCC computed by hand (no
scikit-learn). CSV read via existing DuckDB `read_csv_auto`. Same ruff/mypy/pytest config.
Azure OpenAI settings via `pydantic-settings` from a git-ignored `.env`
(`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT=gpt-5-mini`, `AZURE_OPENAI_API_VERSION`,
`CLASSIFIER_LABEL_VERSION=statsboteval-v1`, `BERGMANN_PROMPTS_DIR`, `BERGMANN_DATASET_DIR`).

## Global constraints

- **No real or public research data in git.** Prompts, theme lists, and the validation
  dataset load from git-ignored paths; tests construct **synthetic** codebooks and message
  batches. A `.env.example` documents the paths; `.gitignore` data exclusions are untouched.
- **The classifier is faked in CI.** Unit tests inject a stub transport returning canned
  Markdown tables; no test makes a network call. One live smoke test is `skipif`-guarded on
  `AZURE_OPENAI_ENDPOINT`, mirroring the Azurite pattern in `test_publish.py`.
- **Determinism is best-effort and recorded, not assumed.** gpt-5-mini is a reasoning model;
  it may ignore `temperature`/`top_p`. We pin `reasoning_effort` and `seed` where supported
  and record the exact model + version in `label_versions.classification` and the validation
  report. Bergmann's `temperature=top_p=0` is documented as their setting, not reproduced.
- **Labels are versioned and coexist (D-07).** `bergmann-v1` (imported) and `statsboteval-v1`
  (produced) live side by side in one table; aggregation reads the one configured version;
  the dashboard shows it via `label_versions.classification`.
- **Floor semantics carry over unchanged.** Every `topics` cell is built through the same
  `floored_count()` path; the floor tests **distinct contributing students**, never the
  category count. A binary category and a theme are both "count of messages where present",
  floored on the students behind them.
- **Contract evolution is additive only.** `topics` and the `label_versions.classification`
  key are new optional fields → **minor bump to schema 1.1.0**, same `v1/` blob prefix. A
  1.0.0 document still validates; a 1.0.0 reader ignores `topics` (invariant 5). No breaking
  change, no `v2/`.
- Work from `pipeline/`; commit after every task; plain imperative messages; keep ruff +
  mypy green from the first task.

---

### Task 1: Versioned labels table (corpus migration 002)

**Files:** `pipeline/migrations/002_labels.sql`,
`pipeline/statsboteval_pipeline/labels.py`, `pipeline/tests/test_labels.py`.

**Produces:** a tidy labels table and typed read/write helpers.

```sql
CREATE TABLE labels (
  history_id    BIGINT  NOT NULL,   -- FK-in-spirit to messages.history_id
  label_version TEXT    NOT NULL,   -- 'bergmann-v1' | 'statsboteval-v1'
  domain        TEXT    NOT NULL,   -- 'deductive' | 'method_theme' | 'software_theme'
  code          TEXT    NOT NULL,   -- category name or theme label
  value         INTEGER NOT NULL,   -- deductive: 0/1; themes: 1 (present) only
  provenance    TEXT    NOT NULL,   -- 'human_consensus' | 'gpt5' | 'gpt-5-mini@2025-08-07'
  PRIMARY KEY (history_id, label_version, domain, code)
);
```

- `write_labels(con, rows)` — bulk upsert; `read_labels(con, label_version)` →
  typed rows; `label_versions_present(con)` → set. Deductive rows store explicit 0/1 (MCC
  needs true negatives); theme rows store only assignments (value=1).
- [ ] Failing tests: migration 002 applies on an existing 001 corpus; write/read round-trip;
      `bergmann-v1` and `statsboteval-v1` rows coexist without collision; provenance
      preserved; re-writing the same key is idempotent (upsert, not duplicate).
- [ ] Implement; full suite green.
- [ ] Commit: `Add versioned labels table to the corpus`

### Task 2: Codebook + theme-list loading (git-ignored, synthetic in tests)

**Files:** `pipeline/statsboteval_pipeline/classify/__init__.py`,
`classify/codebook.py`, `pipeline/tests/classify/test_codebook.py`;
modify `.env.example`, `.gitignore` (ensure `BERGMANN_PROMPTS_DIR` contents excluded if
placed inside the tree).

**Produces:** `load_codebook(dir: Path) -> Codebook` — parses the 13 deductive blocks (the
shared wrapper + per-category Brief/Full/when-1/when-0/example) and the frozen method (21)
and software (9) theme lists from the local Bergmann materials. A `synthetic_codebook()`
factory builds a tiny well-formed codebook for tests (no real definitions).

- [ ] Failing tests (synthetic codebook only): all 13 categories present with required
      fields; method/software theme lists non-empty; a malformed block raises; loader is
      pure (no network, no import-time file read).
- [ ] Implement; full suite green.
- [ ] Commit: `Add classification codebook and theme-list loading`

### Task 3: Consolidated multi-label prompt builder

**Files:** `pipeline/statsboteval_pipeline/classify/prompts.py`,
`pipeline/tests/classify/test_prompts.py`.

**Produces:**
- `build_deductive_prompt(codebook, batch) -> str` — one prompt covering **all 13
  categories** over a batch of ≤50 messages, requesting a Markdown table with a chat-number
  column + 13 binary columns (the consolidated design; departs from Bergmann's
  one-category-per-prompt — D-30, noted as a validation caveat). Static codebook first
  (cache-friendly), messages last.
- `build_theme_prompt(codebook, batch, target) -> str` for `target in {method, software}` —
  assigns each message to zero-or-more themes from the frozen list.
- Category/theme→column grouping is a parameter, so a fragile category can later be split
  into its own call without code change.
- [ ] Failing tests: deterministic render (same inputs → identical string); all 13 category
      headers appear; message numbering is 1..n; a >50 batch raises; theme prompt embeds the
      frozen list.
- [ ] Implement; full suite green.
- [ ] Commit: `Add consolidated multi-label and theme prompt builders`

### Task 4: Strict response parsing

**Files:** `pipeline/statsboteval_pipeline/classify/parse.py`,
`pipeline/tests/classify/test_parse.py`.

**Produces:** `parse_deductive(text, categories, n) -> LabelMatrix` and
`parse_themes(text, n) -> list[set[str]]` — parse the model's Markdown table into a
per-message label structure. **Strict:** exactly `n` rows, expected columns, values in
{0,1} for deductive; unknown themes (not in the frozen list) rejected; raises
`ClassifierParseError` with the offending row on any deviation (a silent mis-parse would
corrupt labels). Tolerant only of benign whitespace/pipe-padding.

- [ ] Failing tests: a canned good table parses to the expected matrix; missing row, extra
      column, non-binary value, and an out-of-list theme each raise; ragged whitespace still
      parses; row order independence (keyed by chat number, not position).
- [ ] Implement; full suite green.
- [ ] Commit: `Add strict classifier response parsing`

### Task 5: Azure OpenAI client (deterministic settings, retry; faked in tests)

**Files:** `pipeline/statsboteval_pipeline/classify/client.py`,
`pipeline/statsboteval_pipeline/classify/config.py`,
`pipeline/tests/classify/test_client.py`; modify `pipeline/pyproject.toml`
(add `openai>=1.40`, `azure-identity`).

**Produces:**
- `ClassifierClient` wrapping `openai.AzureOpenAI` — one `complete(prompt) -> str` method.
  Auth: `AZURE_OPENAI_API_KEY` if set, else `DefaultAzureCredential` bearer token. Pins
  `model=$AZURE_OPENAI_DEPLOYMENT` (gpt-5-mini), `reasoning_effort="minimal"`, `seed`, and a
  fixed `api-version`. Retries 429/5xx with capped exponential backoff.
- Settings via `pydantic-settings` (`config.py`); a `.env.example` documenting Data Zone
  Standard endpoint + deployment.
- [ ] Failing tests (no network): client builds from settings; a stub transport returns a
      canned completion; a 429-then-200 stub exercises one retry then succeeds; missing
      endpoint raises a clear config error.
- [ ] Implement; full suite green.
- [ ] Commit: `Add Azure OpenAI classifier client with retry and deterministic settings`

### Task 6: Classification runner (statsboteval-v1 producer, idempotent, resumable)

**Files:** `pipeline/statsboteval_pipeline/classify/runner.py`,
`pipeline/tests/classify/test_runner.py`.

**Produces:** `classify_corpus(con, client, codebook, *, label_version, model_tag) -> int`
— select messages lacking `label_version` labels, batch 50, run the deductive pass then the
method + software theme passes, parse, `write_labels`. Idempotent by
`(history_id, label_version)` — re-running labels only new messages; a mid-run failure
leaves already-written batches intact (resumable). Returns the count newly labeled.

- [ ] Failing tests (stub client returning deterministic canned tables): a full run over a
      synthetic corpus writes deductive + theme rows for every message with the right
      provenance tag; a second run writes zero (idempotent); a client raising mid-run leaves
      prior batches persisted and re-run completes the rest.
- [ ] Implement; full suite green.
- [ ] Commit: `Add batch classification runner (statsboteval-v1 producer)`

### Task 7: bergmann-v1 importer (from the public Stage-2 dataset)

**Files:** `pipeline/statsboteval_pipeline/import_bergmann.py`,
`pipeline/tests/test_import_bergmann.py`.

**Produces:** `import_bergmann_v1(con, csv_path) -> int` — read `full_dataset.csv`
(git-ignored local path) via DuckDB; map `id → history_id`; write the 13 deductive
categories (0/1) and method/software theme codings as `label_version="bergmann-v1"`, with
`provenance` from the `group` column (`human_consensus` for the 300-row `Master_sample`,
else `gpt5`). Verify a sample of `sent`/timestamps against the corpus when the corpus holds
those rows; on a standalone public-data import (no production corpus), skip the join check
and log it.

- [ ] Failing tests: import a **synthetic** CSV constructed in the test → labels table has
      `bergmann-v1` rows with correct provenance split; a row whose `id` collides across
      versions does not overwrite `statsboteval-v1`; malformed CSV (missing category column)
      raises.
- [ ] Implement; full suite green.
- [ ] Commit: `Add bergmann-v1 label importer from the public Stage-2 dataset`

### Task 8: Validation harness (per-category MCC vs bergmann-v1)

**Files:** `pipeline/statsboteval_pipeline/validate.py`,
`pipeline/tests/test_validate.py`.

**Produces:** `validate_against_bergmann(con) -> ValidationReport` — join
`statsboteval-v1` and `bergmann-v1` on `history_id` over the **300 human-consensus rows**;
per deductive category compute MCC (by hand: `(tp*tn − fp*fn)/sqrt(...)`, guarding the
zero-variance denominator → NA, as Bergmann's Multiple Choice was). Themes are produced but
**not** MCC-scored (Bergmann validated themes by expert similarity rating, not MCC) — the
report notes this. The report records the classifier model/version and the two-way
conflation caveat (model **and** consolidated-prompt differences from their pipeline).

- [ ] Failing tests: hand-computed MCC on a tiny synthetic labelled pair matches; only
      human-consensus rows enter the score; an all-zero category yields NA, not a crash;
      report carries model tag + caveat text.
- [ ] Implement; full suite green.
- [ ] Commit: `Add classifier validation harness (per-category MCC vs bergmann-v1)`

### Task 9: Contract extension — topics section (schema 1.1.0)

**Files:** `pipeline/statsboteval_pipeline/contract.py`,
`pipeline/tests/test_contract_topics.py`, `pipeline/tests/test_contract_root.py` (extend);
regenerate `schema/aggregates.schema.json` via `export_schema`; regenerate
`dashboard/src/lib/aggregates.gen.ts`; update `docs/aggregates-contract.md` (§8 → normative).

**Produces:**
- A **categorical-distribution** shape (not the numeric `Histogram` — categories aren't
  numeric ranges): `TopicDistribution = { items: {label: str; cell: CountCell}[];
  n_total: CountCell; footnote_ids?: [...] }`. Cells are **multi-label** counts (a message
  may be several categories/themes) — they do **not** sum to `n_total`; a footnote states so.
- `TopicsSection` = `per_window: dict[str, { deductive: TopicDistribution;
  method_themes: TopicDistribution; software_themes: TopicDistribution }]`, added optional to
  `Sections`. `label_versions` gains a documented optional `classification` domain key.
  `SCHEMA_VERSION` → `"1.1.0"`. New footnote `label_provenance` in §6.2.
- [ ] Failing tests: a topics document round-trips and validates; the committed 1.0.0
      synthetic fixture still validates against the 1.1.0 schema (additive proof); schema
      export drift-check passes; `label_versions.classification` optional; per_window keys
      validated against the windows registry (existing cross-doc validator covers topics).
- [ ] Implement; regenerate artifacts; full suite green (including `test_schema_export`).
- [ ] Commit: `Extend aggregates contract with topics section (schema 1.1.0)`

### Task 10: Topics aggregation (labels → contract, floored)

**Files:** `pipeline/statsboteval_pipeline/aggregate.py`,
`pipeline/tests/test_aggregate_topics.py`.

**Produces:** extend `build_aggregates` to emit `sections.topics` for the configured
`label_version` when labels exist: per window, per category/theme, a `floored_count` over
the count of messages where present, with the floor on **distinct students** behind that
category/theme; `n_total` = floored message count in the window; sets
`label_versions.classification`; attaches `label_provenance` footnote. Absent labels →
`topics` omitted (still a valid 1.1.0 document).

- [ ] Failing tests: hand-seeded corpus + labels → exact topics distributions with a
      category suppressed for sub-floor students; `n_total` floored independently;
      `label_versions.classification` reflects the configured version; no labels → no topics
      section, document still valid.
- [ ] Implement; full suite green.
- [ ] Commit: `Aggregate classification labels into the topics section`

### Task 11: Dashboard topics view

**Files:** `dashboard/src/components/TopicsDistribution.tsx` (name indicative),
`dashboard/src/app/page.tsx` (add the view); regenerate types if not already.

**Behavior (contract-driven, suppression-aware):** render the deductive category prevalences
and the method/software theme distributions for the selected window as floored bars;
suppressed categories show the "< N students" treatment (never as 0), reusing the Part 2
suppression convention; the multi-label footnote and `label_provenance` (with the active
`label_versions.classification`) render beneath. Absent topics section → the view hides
cleanly.

- [ ] Build against the local stack (Azurite + CLI publish incl. synthetic labels + uvicorn);
      verify suppressed/zero/ok distinct and the provenance footnote shows.
- [ ] `pnpm build` exports clean.
- [ ] Commit: `Add dashboard topics view (classification distributions)`

### Task 12: CLI wiring + synthetic label fixtures + operator runbook

**Files:** `pipeline/statsboteval_pipeline/cli.py` (add subcommands),
`pipeline/statsboteval_pipeline/fixtures.py` (synthetic labels for E2E),
`scripts/e2e_local.sh` (extend), `docs/runbooks/classification.md`.

**Produces:**
- CLI subcommands: `classify` (run `statsboteval-v1` over a corpus via the live client),
  `import-bergmann --csv PATH`, `validate` (print the MCC report). `run-synthetic` gains a
  `--with-labels` flag that seeds deterministic synthetic labels so the E2E slice and demo
  show a populated topics view without any API call.
- Operator runbook: the weekly order (extract → classify → aggregate → publish); the
  one-off `import-bergmann` + `validate` on the public dataset; the explicit note that
  classifying the **real** corpus and publishing real topics is **go-live-gated** (Part 4).
- [ ] Failing tests: `run-synthetic --with-labels` produces a document whose `topics`
      validates and whose `data_provenance == "synthetic"`; `validate` on a seeded
      two-version corpus prints a well-formed report.
- [ ] Extend `e2e_local.sh` to assert a dense `topics` section end-to-end; run it.
- [ ] Commit: `Wire classification CLI, synthetic labels, and operator runbook`

### Task 13 (operator, uses public data — not CI): validation run & model decision

Not a code task; a recorded operator step once Tasks 1–12 land.

- [ ] Import `bergmann-v1` from the local copy of the public `full_dataset.csv`; run
      `statsboteval-v1` (gpt-5-mini) over the public 1,400 messages; run `validate`.
- [ ] Record per-category MCCs in the **local** validation report (git-ignored, per D-16).
      If any category falls well below the Bergmann reference, decide per D-30's escalation:
      bump that category (or the whole run) to **gpt-5.1**, and/or split the fragile
      category into its own prompt call (config change, no rewrite). Re-run, re-record.
- [ ] Note the chosen production model + version in `docs/decisions.md` (amend D-30) and in
      `label_versions.classification` for real publishes.

---

## Verification summary

Unit (pytest, no network): labels round-trip + version coexistence; codebook parse; prompt
determinism; strict response parse (accept/reject); client build + retry (stub transport);
runner idempotence + resume (stub client); bergmann import provenance split; hand-computed
MCC; topics contract round-trip + 1.0.0-still-valid + schema-export drift; hand-seeded
topics aggregation with suppression. Integration/E2E: `e2e_local.sh` asserts a dense topics
section through Azurite → API → dashboard; one `skipif`-guarded live Azure OpenAI smoke test.
Operator (public data, out of CI): the Task 13 validation run. Throughout: ruff + mypy green
in `pipeline/`; `pnpm build` exports clean.

## Out of scope (→ later plans)

Complex inductive theme sets (non-statistical interaction, capability request, declarative
statement — the generate→assign passes; D-30 scoped Phase B to deductive + methods/software
only); the missing Declarative Statement production prompt and production repetition protocol
(open Bergmann items — interim manuscript Table-1 wording; `docs/open-questions.md`); Azure
OpenAI **Batch** SKU cost optimization (sync calls suffice at this corpus size); per-course
(`lv`) / program-level (`Status`) topic segmentation (contract §13, blocked on sources);
real-corpus classification + real topics publish (Part 4 go-live gates); Phase A Parts 3–4
metric widening (follow this plan); returning the Bergmann materials to the public repo
(gated on the team's formal publication, D-16).

## Related decisions

D-07 (label versioning) · D-16 (Bergmann materials local) · D-22 (public Stage-2 canon) ·
D-24 (privacy floor N=3) · D-25 (aggregates contract v1) · D-30 (this plan's inputs:
gpt-5-mini, consolidated prompt, public validation, schema 1.1.0).

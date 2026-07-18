# Phase B — classification pipeline (implementation plan)

**Goal:** add automated message classification to StatsBotEval; with the first real-data
publish already live (D-37), the finish line is now the **`topics` section live on the
dashboard's first tab**. The local weekly pipeline gains an `extract` stage (direct
MySQL, in-flight pseudonymization) and a `classify` stage that codes each message against
the Bergmann deductive scheme (13 binary categories), assigns the frozen methods/software
themes, and — new in the 2026-07-07 re-scope — runs our own **two-stage inductive pass**
(generate candidate codes → synthesize themes → operator review → freeze as
`statsboteval-themes-v1` → assign). Versioned labels live in the DuckDB corpus; a
privacy-floored `topics` section enters the aggregates contract (schema 1.1.0); the
redesigned dashboard's Topics tab (D-32) renders it. A validation harness measures our
classifier (`statsboteval-v1`) against the team's published labels (`bergmann-v1`) on the
public 1,400-message dataset. Chat text is sent only to Azure OpenAI EU (Data Zone
Standard) for transient classification; only floored aggregates ever leave the local
machine.

**Status: drafted 2026-07-06 (D-30); re-scoped in place 2026-07-07 (D-33/D-34); Tasks
1–2 done; re-sequenced 2026-07-17 (D-35/D-36): Task 3 skipped as satisfied (extract
validated row-level against the public dataset), Tasks 4 and 17 pulled into
`docs/plans/2026-07-17-go-live-first.md` (go-live first), Tasks 5–16/18–20 resume after
that plan's real-data publish; resumed 2026-07-18 (D-38) in two stages — Stage 1
(deductive + frozen themes → first topics publish), Stage 2 (emergent themes →
republish) — and `run-weekly` gains classification. See "Resumption deltas".** The re-scope: production DB access is in hand (Uni Wien VPN), so the extract
moves from "gated with Part 4" into this plan; emergent-theme generation joins the scope
(the frozen-list-only compromise was rejected — the Topics tab promises emergent themes);
the dashboard task is retargeted at the D-32 tab architecture; the three go-live gates are
**closed** (D-34: pepper custody scheme, floor N=3, architecture sign-off), so this plan
ends with the demo dashboard showing real aggregates.

## Context & sequencing

Milestone 1 is phased (D-07): Phase A = descriptive dashboard (Parts 1–2 done, 3–4
remain), **Phase B = this classification pipeline**. Per the 2026-07-06 re-scope, Phase B
runs **before** Phase A Parts 3–4: it is the thesis core, fully unblocked, and de-risks
the largest technical unknown (the LLM classifier) early.

**What "gated" means after D-34:** the three go-live *decisions* are recorded; what
remains before the first real publish is **operational**, and all of it is inside this
plan — recon done (Task 1), extract proven by the Bergmann-descriptives check (Task 3),
erasure runbook in place (Task 17), publish guard green. Local classification of real
chat text via Azure OpenAI EU was already consented practice (D-24 sequencing note;
sign-off now recorded in D-34).

**Dependency shape:** Tasks 1–3 need the VPN + DB credentials and touch real data
(local-only); Tasks 4–16 are pure code, developed and CI-tested against **synthetic
fixtures** plus, for validation, the **public** Bergmann dataset (Zenodo raw 1,400 +
OSF `full_dataset.csv`). The two tracks can proceed in parallel; Tasks 19–20 are operator
runs that need both tracks landed.

**Data-locality rules (binding, unchanged + one addition):** the Bergmann prompt texts,
frozen theme lists, and the public validation dataset are **git-ignored local files**
(D-16). No real data — public or not — enters git; all committed fixtures are synthetic
and `SYNTHETIC`-labeled. Labels live only in the local corpus; the `topics` schema
carries **counts, never message text** (contract invariant 6, enforced by the publish
guard). **New (D-33):** the synthesized emergent-theme list is *derived from real chat
text* — it is git-ignored local like the Bergmann materials, and its labels may appear in
a published aggregate **only after operator review** confirms they are short, generic,
and non-identifying (the generation prompt instructs this; the review is a named runbook
step).

## Resumption deltas (2026-07-18, D-38)

Go-live (D-36/D-37) landed between this plan's drafting and its resumption; the deltas
below re-shape the tail of the plan. Two are owner decisions taken 2026-07-18:

- **The finish line moved.** The "first real-data publish" this plan originally ended
  with is live (D-37, Phase A sections). Phase B now ends with `topics` live on the
  dashboard's first tab — in two stages.
- **Staged topics publish (owner).** Stage 1 = deductive (13) + frozen method/software
  themes, validated on public data (Task 19), aggregated and published with
  `emergent_themes` omitted — a state Tasks 13–15 already design as valid and rendered
  (invariant 5). Stage 2 = the emergent pass (Task 12) + review + assignment +
  republish. Rationale: the generate→review→freeze loop is the slowest, most
  operator-bound piece; tab #1 shouldn't wait on it. Task 20 splits into 20a/20b.
- **Classification joins the weekly cadence (owner).** GL5's `run-weekly` (which this
  plan predates) is extended in Task 16 to chain `classify` (+ `assign-themes` once a
  reviewed theme set exists) with a `--skip-classify` escape hatch. The Task 9 runner's
  idempotency by `(history_id, label_version)` makes the weekly increment safe and
  cents-cheap; without this, weekly publishes would serve stale topics next to fresh
  Phase A sections.
- **`axis_start` interplay (D-37):** classification runs corpus-wide (idempotent; the
  sub-floor pilot rows cost pennies) — published topics respect `axis_start`/window
  coverage automatically at aggregation time. No design change.
- **Theme-set drift:** `statsboteval-themes-v1` freezes at Stage 2; new semesters will
  eventually outgrow it. Regeneration (v2) is a per-semester operator-review question —
  out of Phase B scope, noted in the Task 16 runbook.
- **Task 18 re-verifies the model catalog** (Data Zone Standard, Sweden Central) at
  provisioning time — D-30's availability check ages, and that catalog demonstrably
  shifts.
- **Per-status topics ship in Stage 1 (owner, 2026-07-18, D-39):** the program-level
  dimension (Task 21) gets schema support in Task 13 (`by_status`), aggregation in
  Task 14, and a dashboard control in Task 15; Task 21 plus a real `import-status`
  run must precede 20a. The roster CSV is produced in the roster-derivation session
  (the validated list semantics live there; this repo only imports) and stays
  **uid-keyed** (single-hasher invariant, survives pepper rotation, human-checkable).

**Execution order:** 5 → 6 → 7 → 8 → 9 → 10 → 11 → 19 (with 18 provisioned any time
before it) → 13 → 14 → 15 → 16 → 21 (independent — any time before here) → **20a
(Stage 1 publish)** → 12 → **20b (Stage 2 republish)**.

## Architecture (decisions D-07, D-16, D-20, D-22, D-24, D-25, D-30, D-32, D-33, D-34)

```
LOCAL weekly pipeline (extends the existing package)          AZURE (unchanged shape)
  extract.py   ← NEW: direct MySQL over Uni Wien VPN,         Blob: v1/ aggregates + latest
               incremental by history.id watermark,           FastAPI serves them verbatim
               in-flight HMAC(normalize(uid), pepper),          + the dashboard bundle
               pepper-fingerprint interlock, SELECT-only        (Topics tab goes live)
  → corpus (DuckDB, one file, encrypted volume)
  classify/    ← NEW package
    codebook.py    13 deductive blocks + frozen method (21)
                   / software (9) lists, loaded from
                   git-ignored BERGMANN_PROMPTS_DIR           Chat text → Azure OpenAI EU
    prompts.py     consolidated multi-label + theme-          (Data Zone Standard, transient,
                   assignment prompt builders                 consented) — never persisted
    generate.py    inductive stage 1: candidate codes          cloud-side
    synthesize.py  inductive stage 2: codes → draft themes
                   → operator review → freeze as
                   statsboteval-themes-v1 (migration 003)
    client.py      openai.AzureOpenAI, gpt-5-mini, seed +
                   reasoning_effort, 429 backoff
    parse.py       strict Markdown-table → label matrix
    runner.py      batch 50/call, idempotent by
                   (history_id, label_version), resumable
  labels.py        versioned labels table (migration 002)
  import_bergmann.py  bergmann-v1 ← public full_dataset.csv
  validate.py      per-category MCC vs bergmann-v1 (300
                   human-consensus rows = ground truth)
  erase.py         ← NEW: erasure procedure backend
  aggregate.py     += topics section (floored, per window)    schema 1.1.0 (additive; v1/
  contract.py      += TopicsSection (incl. emergent_themes),    prefix unchanged)
                   label_versions.classification
```

**Tech stack additions (pipeline):** `openai>=1.40` (AzureOpenAI client), `azure-identity`
(token-auth alternative; already used in `api/`), `pymysql` (pure-Python MySQL driver —
trivially stubbed in tests; chosen over the DuckDB MySQL extension so the HMAC + interlock
logic stays in testable Python). MCC computed by hand (no scikit-learn). CSV read via
existing DuckDB `read_csv_auto`. Same ruff/mypy/pytest config. Settings via
`pydantic-settings` from the git-ignored `pipeline/.env`: `STATSBOT_DB_HOST/PORT/NAME/
USER/PASSWORD`, `PSEUDONYM_PEPPER`, `AZURE_OPENAI_ENDPOINT`,
`AZURE_OPENAI_DEPLOYMENT=gpt-5-mini`, `AZURE_OPENAI_API_VERSION`,
`CLASSIFIER_LABEL_VERSION=statsboteval-v1`, `BERGMANN_PROMPTS_DIR`,
`BERGMANN_DATASET_DIR`. `.env.example` documents all of them.

## Global constraints

- **No real or public research data in git.** Prompts, theme lists (frozen *and*
  generated), and the validation dataset load from git-ignored paths; tests construct
  **synthetic** codebooks, message batches, and candidate-code sets. `.gitignore` data
  exclusions are untouched.
- **CI never touches real data or the network.** The MySQL connection and the Azure
  OpenAI transport are both stubbed in unit tests; one live smoke test each is
  `skipif`-guarded (on `STATSBOT_DB_HOST` / `AZURE_OPENAI_ENDPOINT`), mirroring the
  Azurite pattern in `test_publish.py`.
- **Determinism is best-effort and recorded, not assumed.** gpt-5-mini is a reasoning
  model; it may ignore `temperature`/`top_p`. We pin `reasoning_effort` and `seed` where
  supported and record the exact model + version in `label_versions.classification` and
  the validation report. Bergmann's `temperature=top_p=0` is documented as their setting,
  not reproduced.
- **Labels are versioned and coexist (D-07).** `bergmann-v1` (imported) and
  `statsboteval-v1` (produced) live side by side in one table; aggregation reads the one
  configured version. Emergent themes additionally carry their theme-set version
  (`statsboteval-themes-v1`).
- **Floor semantics carry over unchanged.** Every `topics` cell is built through the same
  `floored_count()` path; the floor tests **distinct contributing students** (N=3, D-34),
  never the category count. A binary category and a theme are both "count of messages
  where present", floored on the students behind them.
- **Contract evolution is additive only.** `topics` and the
  `label_versions.classification` key are new optional fields → **minor bump to schema
  1.1.0**, same `v1/` blob prefix. A 1.0.0 document still validates; a 1.0.0 reader
  ignores `topics` (invariant 5). No breaking change, no `v2/`.
- Work from `pipeline/` (Task 15 from `dashboard/`, Task 18 from `infra/`); commit after
  every task; plain imperative messages; keep ruff + mypy green from the first task.

---

### Task 1 (operator + doc, needs VPN + DB creds): recon queries & data dictionary update

**Files:** `docs/source-data-dictionary.md`, `docs/open-questions.md` (check items off);
no production code.

Run the four self-serve recon queries from `docs/open-questions.md` over the production
connection (read-only session — **the DB is live; we never write**, owner directive
2026-07-07, now CLAUDE.md binding constraint 5):

- [x] `matnr`/`lv` population — **columns don't exist in prod**; `import` roster table
      (Moodle export) holds `Matrikelnummer`↔`uid` instead; prod adds a `registered` flag.
- [x] Current volumes: 550 students / 443 messaging / 4,412 messages / 1,871 sessions
      (2024-07 → live). **Cost estimate: single-digit euros per full gpt-5-mini run**
      (~3–4 M input tokens over all five passes), ≈ €10 with full gpt-5.1 escalation —
      D-30's "tens of euros" was conservative; Batch SKU stays out of scope.
- [x] Program-level `Status` source: **not in the DB** (roster `Gruppen` ≡ "MethodsHub");
      stays with the Daniel item; roster non-membership weakly proxies "Other" only.
- [x] `created_at` timezone: Laravel writes UTC strings into a Europe/Vienna session —
      **read with the server-default session tz and treat as UTC** (empirics + rule in
      `source-data-dictionary.md`); corpus "UTC assumed" holds, no Phase A fix needed.
- [x] Folded into `source-data-dictionary.md` (incl. new `import` table + timezone
      sections); recon items checked off in `open-questions.md`.
- [x] Commit: `Record production-DB recon results in the data dictionary`

**Done 2026-07-07.**

### Task 2: Extract stage (MySQL → pseudonymized corpus, pepper interlock)

**Files:** `pipeline/statsboteval_pipeline/extract.py`,
`pipeline/statsboteval_pipeline/config.py` (extend), `pipeline/tests/test_extract.py`,
`.env.example`; `pipeline/pyproject.toml` (+`pymysql`).

**Produces:** `extract_new_rows(con, source, settings) -> int` — pull `students` +
`history` rows above the stored `history.id` watermark over a session opened with
`init_command="SET SESSION TRANSACTION READ ONLY"` (the live-DB read-only rule, CLAUDE.md
constraint 5 — server-enforced, not just discipline) and the **server-default session
timezone** (never `time_zone='+00:00'` — see the data dictionary's timezone rule;
`created_at` then reads as true UTC); compute `pseudonym = HMAC_SHA256(normalize(uid),
pepper)` in flight (trim + lowercase per the data dictionary — pseudonyms silently fork
otherwise); write **only** pseudonymized columns into the migration-001 corpus tables (no
`uid`, no names; the `import` roster table is never selected). Direct identifiers never
touch disk. **Pepper interlock:** at first ingest the corpus stores
`sha256(pepper)`; every later run verifies it and refuses to proceed on mismatch (a
wrong/rotated pepper fails loudly instead of silently splitting every student in two).
Watermark makes reruns incremental and idempotent.

- [x] Failing tests (stubbed connection object; no network): HMAC determinism + uid
      normalization (mixed case/whitespace collapse to one pseudonym); only schema-001
      columns are written; watermark resume skips already-ingested ids; fingerprint
      mismatch raises before any write; empty delta is a no-op; NULL registration time
      skipped; NULL message timestamp fails loudly.
- [x] One `skipif(STATSBOT_DB_* unset)` live smoke: connect read-only, count rows.
- [x] Implement; generate the real pepper (D-34: `secrets.token_hex(32)` → `pipeline/.env`;
      password-manager backup = owner step); full suite green (75 passed).
- [x] Commit: `Add MySQL extract with in-flight pseudonymization and pepper interlock`

**Done 2026-07-07.** Deviations: the pepper interlock needed corpus storage, so
`002_extract_meta.sql` (key/value `meta` table) ships here — labels/theme_sets
migrations renumber to 003/004; the `extract` CLI subcommand is pulled forward from
Task 16 so Task 3 can run. First real extract executed the same day: 550 students /
4,412 messages / 1,871 sessions into `pipeline/data/corpus.duckdb` (git-ignored),
matching recon exactly; rerun ingests 0; corpus `created_at` verified as true UTC.

### Task 3 (operator, real data local-only): ETL correctness check — Bergmann descriptives

**Skipped 2026-07-17 as satisfied (D-35)** — the row-level validation against the public
dataset (1,400/1,400 field matches; all reference descriptives reproduce) delivered the
substance; the module is not built unless a future re-extract raises doubt.

**Files:** `pipeline/statsboteval_pipeline/check_descriptives.py`, CLI subcommand
`check-descriptives`, `pipeline/tests/test_check_descriptives.py` (synthetic).

**Produces:** a report comparing our corpus, filtered to Bergmann's exact window
(2025-03-15 → 2025-06-30; bachelor cohort exists only from 2025-05-16), against the
published reference descriptives (`bergmann-framework.md` table): message/user counts,
one-time-user %, messages-per-chat means, token medians. One-time ETL correctness check
— **the gate on trusting the extract before spending money classifying** (pulled forward
from Phase A Part 3). Program-level splits only if Task 1 found a `Status` source.

- [ ] Failing tests: hand-seeded synthetic corpus reproduces hand-computed descriptives;
      window filter respects the bachelor onboarding date.
- [ ] Operator: run against the real corpus; record the comparison in a **local**
      (git-ignored) report; investigate any gross mismatch before proceeding.
- [ ] Commit: `Add Bergmann descriptives check for extract validation`

### Task 4: Versioned labels table (corpus migration 003)

**Files:** `pipeline/migrations/003_labels.sql`,
`pipeline/statsboteval_pipeline/labels.py`, `pipeline/tests/test_labels.py`.

**Produces:** a tidy labels table and typed read/write helpers.

```sql
CREATE TABLE labels (
  history_id    BIGINT  NOT NULL,   -- FK-in-spirit to messages.history_id
  label_version TEXT    NOT NULL,   -- 'bergmann-v1' | 'statsboteval-v1'
  domain        TEXT    NOT NULL,   -- 'deductive' | 'method_theme' | 'software_theme'
                                    --   | 'emergent_theme'
  code          TEXT    NOT NULL,   -- category name or theme label
  value         INTEGER NOT NULL,   -- deductive: 0/1; themes: 1 (present) only
  provenance    TEXT    NOT NULL,   -- 'human_consensus' | 'gpt5' | 'gpt-5-mini@2025-08-07'
  PRIMARY KEY (history_id, label_version, domain, code)
);
```

- `write_labels(con, rows)` — bulk upsert; `read_labels(con, label_version)` → typed rows;
  `label_versions_present(con)` → set. Deductive rows store explicit 0/1 (MCC needs true
  negatives); theme rows store only assignments (value=1).
- [x] Failing tests: migration 003 applies on an existing 001+002 corpus; write/read
      round-trip; `bergmann-v1` and `statsboteval-v1` rows coexist without collision;
      provenance preserved; re-writing the same key is idempotent (upsert, not duplicate).
- [x] Implement; full suite green.
- [x] Commit: `Add versioned labels table to the corpus`

**Done 2026-07-17 via the go-live plan (GL2, commit `d37ed46`)** — pulled forward because
`lang-heuristic-v1` labels live in the same table; the `domain` enum already includes
`language`.

### Task 5: Codebook + frozen theme-list loading (git-ignored, synthetic in tests)

**Files:** `pipeline/statsboteval_pipeline/classify/__init__.py`,
`classify/codebook.py`, `pipeline/tests/classify/test_codebook.py`; modify
`.env.example`, `.gitignore` (ensure `BERGMANN_PROMPTS_DIR` contents excluded if placed
inside the tree).

**Produces:** `load_codebook(dir: Path) -> Codebook` — parses the 13 deductive blocks
(the shared wrapper + per-category Brief/Full/when-1/when-0/example) and the frozen
method (21) and software (9) theme lists from the local Bergmann materials. A
`synthetic_codebook()` factory builds a tiny well-formed codebook for tests (no real
definitions).

- [ ] Failing tests (synthetic codebook only): all 13 categories present with required
      fields; method/software theme lists non-empty; a malformed block raises; loader is
      pure (no network, no import-time file read).
- [ ] Implement; full suite green.
- [ ] Commit: `Add classification codebook and theme-list loading`

### Task 6: Consolidated multi-label + theme-assignment prompt builders

**Files:** `pipeline/statsboteval_pipeline/classify/prompts.py`,
`pipeline/tests/classify/test_prompts.py`.

**Produces:**
- `build_deductive_prompt(codebook, batch) -> str` — one prompt covering **all 13
  categories** over a batch of ≤50 messages, requesting a Markdown table with a
  chat-number column + 13 binary columns (the consolidated design; departs from
  Bergmann's one-category-per-prompt — D-30, noted as a validation caveat). Static
  codebook first (cache-friendly), messages last.
- `build_theme_prompt(themes, batch, domain) -> str` — assigns each message to
  zero-or-more themes from a **given list** (frozen method/software lists here; the
  generated `statsboteval-themes-v1` list in Task 12 — same builder, no special case).
- Category/theme→column grouping is a parameter, so a fragile category can later be split
  into its own call without code change.
- [ ] Failing tests: deterministic render (same inputs → identical string); all 13
      category headers appear; message numbering is 1..n; a >50 batch raises; theme
      prompt embeds the given list verbatim.
- [ ] Implement; full suite green.
- [ ] Commit: `Add consolidated multi-label and theme prompt builders`

### Task 7: Strict response parsing

**Files:** `pipeline/statsboteval_pipeline/classify/parse.py`,
`pipeline/tests/classify/test_parse.py`.

**Produces:** `parse_deductive(text, categories, n) -> LabelMatrix` and
`parse_themes(text, allowed, n) -> list[set[str]]` — parse the model's Markdown table
into a per-message label structure. **Strict:** exactly `n` rows, expected columns,
values in {0,1} for deductive; themes outside the allowed list rejected; raises
`ClassifierParseError` with the offending row on any deviation (a silent mis-parse would
corrupt labels). Tolerant only of benign whitespace/pipe-padding.

- [ ] Failing tests: a canned good table parses to the expected matrix; missing row,
      extra column, non-binary value, and an out-of-list theme each raise; ragged
      whitespace still parses; row order independence (keyed by chat number, not
      position).
- [ ] Implement; full suite green.
- [ ] Commit: `Add strict classifier response parsing`

### Task 8: Azure OpenAI client (deterministic settings, retry; faked in tests)

**Files:** `pipeline/statsboteval_pipeline/classify/client.py`,
`pipeline/statsboteval_pipeline/classify/config.py`,
`pipeline/tests/classify/test_client.py`; modify `pipeline/pyproject.toml`
(add `openai>=1.40`, `azure-identity`).

**Produces:**
- `ClassifierClient` wrapping `openai.AzureOpenAI` — one `complete(prompt) -> str`
  method. Auth: `AZURE_OPENAI_API_KEY` if set, else `DefaultAzureCredential` bearer token
  (key-first matters: the operator lacks `roleAssignments/write` in MOPS — see Task 18).
  Pins `model=$AZURE_OPENAI_DEPLOYMENT` (gpt-5-mini), `reasoning_effort="minimal"`,
  `seed`, and a fixed `api-version`. Retries 429/5xx with capped exponential backoff.
- Settings via `pydantic-settings` (`config.py`); `.env.example` documents the Data Zone
  Standard endpoint + deployment.
- [ ] Failing tests (no network): client builds from settings; a stub transport returns a
      canned completion; a 429-then-200 stub exercises one retry then succeeds; missing
      endpoint raises a clear config error.
- [ ] Implement; full suite green.
- [ ] Commit: `Add Azure OpenAI classifier client with retry and deterministic settings`

### Task 9: Classification runner (statsboteval-v1 producer, idempotent, resumable)

**Files:** `pipeline/statsboteval_pipeline/classify/runner.py`,
`pipeline/tests/classify/test_runner.py`.

**Produces:** `classify_corpus(con, client, codebook, *, label_version, model_tag) -> int`
— select messages lacking `label_version` labels, batch 50, run the deductive pass then
the method + software theme passes, parse, `write_labels`. Idempotent by
`(history_id, label_version)` — re-running labels only new messages; a mid-run failure
leaves already-written batches intact (resumable). Returns the count newly labeled.
(The emergent-theme assignment pass plugs in here in Task 12 — same batching, different
domain.)

- [ ] Failing tests (stub client returning deterministic canned tables): a full run over
      a synthetic corpus writes deductive + theme rows for every message with the right
      provenance tag; a second run writes zero (idempotent); a client raising mid-run
      leaves prior batches persisted and re-run completes the rest.
- [ ] Implement; full suite green.
- [ ] Commit: `Add batch classification runner (statsboteval-v1 producer)`

### Task 10: bergmann-v1 importer (from the public Stage-2 dataset)

**Files:** `pipeline/statsboteval_pipeline/import_bergmann.py`,
`pipeline/tests/test_import_bergmann.py`.

**Produces:** `import_bergmann_v1(con, csv_path) -> int` — read `full_dataset.csv`
(git-ignored local path) via DuckDB; map `id → history_id`; write the 13 deductive
categories (0/1) as `label_version="bergmann-v1"`, with `provenance` from the `group`
column (`human_consensus` for the 300-row `Master_sample`, else `gpt5`).
*Implementation deviation (2026-07-18): the public `full_dataset.csv` carries no
method/software theme codings, so the import is deductive-only — themes are not
MCC-validated anyway (Bergmann validated them by expert similarity); a theme import
from another Stage-2 file can be added later if a comparison is ever wanted.* With the real corpus present (Task 2), the join check —
verify a sample of `sent`/timestamps against corpus rows — **runs for real** rather than
being skipped-and-logged.

- [ ] Failing tests: import a **synthetic** CSV constructed in the test → labels table
      has `bergmann-v1` rows with correct provenance split; a row whose `id` collides
      across versions does not overwrite `statsboteval-v1`; malformed CSV (missing
      category column) raises.
- [ ] Implement; full suite green.
- [ ] Commit: `Add bergmann-v1 label importer from the public Stage-2 dataset`

### Task 11: Validation harness (per-category MCC vs bergmann-v1)

**Files:** `pipeline/statsboteval_pipeline/validate.py`,
`pipeline/tests/test_validate.py`.

**Produces:** `validate_against_bergmann(con) -> ValidationReport` — join
`statsboteval-v1` and `bergmann-v1` on `history_id` over the **300 human-consensus
rows**; per deductive category compute MCC (by hand: `(tp*tn − fp*fn)/sqrt(...)`,
guarding the zero-variance denominator → NA, as Bergmann's Multiple Choice was). Frozen
themes are produced but **not** MCC-scored (Bergmann validated themes by expert
similarity rating, not MCC); emergent themes have no Bergmann counterpart at all — the
report notes both. The report records the classifier model/version and the two-way
conflation caveat (model **and** consolidated-prompt differences from their pipeline).

- [ ] Failing tests: hand-computed MCC on a tiny synthetic labelled pair matches; only
      human-consensus rows enter the score; an all-zero category yields NA, not a crash;
      report carries model tag + caveat text.
- [ ] Implement; full suite green.
- [ ] Commit: `Add classifier validation harness (per-category MCC vs bergmann-v1)`

### Task 12: Emergent-theme generation (two-stage, reviewed, versioned) — NEW (D-33) — Stage 2 (D-38): after the first topics publish

**Files:** `pipeline/migrations/004_theme_sets.sql`,
`pipeline/statsboteval_pipeline/classify/generate.py`,
`pipeline/statsboteval_pipeline/classify/synthesize.py`,
`pipeline/tests/classify/test_generate.py`, `test_synthesize.py`.

**Produces** our reproduction of Bergmann's two-stage inductive method, corpus-wide:

- **Migration 004:** `theme_candidates` (run-scoped candidate codes per message:
  `history_id, run_id, code`) and `theme_sets` (`set_version, code, description,
  created_at, reviewed_at NULLABLE`) — a theme set is usable only once `reviewed_at` is
  stamped.
- **Stage 1 — `generate.py`:** per ≤50-message batch, prompt for short candidate codes
  per message (instructed: generic wording, ≤5 words, **no verbatim quotes, no names**);
  strict parse (same discipline as Task 7); accumulate into `theme_candidates`.
  Idempotent per (history_id, run_id).
- **Stage 2 — `synthesize.py`:** consolidate the **distinct candidate-code list** (codes
  only — no chat text re-sent) into a draft theme list via one LLM call; write the draft
  to a git-ignored review file. Operator edits/approves; a `freeze-themes` CLI step (Task
  16) loads the reviewed file into `theme_sets` as **`statsboteval-themes-v1`** and
  stamps `reviewed_at`. **The review is the privacy control** for theme labels entering
  published aggregates (D-33).
- **Assignment:** reuse Task 6's `build_theme_prompt` + Task 9's runner with the frozen
  generated list, writing `domain='emergent_theme'`; provenance carries model tag +
  theme-set version.
- [ ] Failing tests (stub client, synthetic data): generation writes candidates
      idempotently; parse rejects malformed candidate output; synthesis input contains
      codes only (no message text — asserted); an unreviewed theme set cannot be used for
      assignment (raises); assignment against a reviewed synthetic set writes
      `emergent_theme` rows.
- [ ] Implement; full suite green.
- [ ] Commit: `Add two-stage emergent-theme generation with reviewed, versioned theme sets`

### Task 13: Contract extension — topics section (schema 1.1.0)

**Files:** `pipeline/statsboteval_pipeline/contract.py`,
`pipeline/tests/test_contract_topics.py`, `pipeline/tests/test_contract_root.py`
(extend); regenerate `schema/aggregates.schema.json` via `export_schema`; regenerate
`dashboard/src/lib/aggregates.gen.ts`; update `docs/aggregates-contract.md`
(§8 → normative).

**Produces:**
- A **categorical-distribution** shape (not the numeric `Histogram` — categories aren't
  numeric ranges): `TopicDistribution = { items: {label: str; cell: CountCell}[];
  n_total: CountCell; footnote_ids?: [...] }`. Cells are **multi-label** counts (a
  message may be several categories/themes) — they do **not** sum to `n_total`; a
  footnote states so.
- `TopicsSection` = `per_window: dict[str, TopicGroup]` where `TopicGroup` =
  `{ deductive: TopicDistribution; method_themes: TopicDistribution;
  software_themes: TopicDistribution; emergent_themes?: TopicDistribution }`, plus
  optional `theme_set_version: str` (documents which reviewed set produced
  `emergent_themes`), added optional to `Sections`. `label_versions` gains a documented
  optional `classification` domain key. `SCHEMA_VERSION` → `"1.1.0"`. New footnote
  `label_provenance` in §6.2.
- **Per-status split (D-39):** each `per_window` entry additionally carries optional
  `by_status: dict[str, TopicGroup]` (keys `bachelor` | `master` | `staff` |
  `unknown`; `unknown` present only when non-empty). Every cell is floored
  independently — the floor, not the schema, is the small-group defense. New footnote
  `status_rule` in §6.2 (roster provenance; usage-time resolution at session level).
- [ ] Failing tests: a topics document round-trips and validates; the committed 1.0.0
      synthetic fixture still validates against the 1.1.0 schema (additive proof); schema
      export drift-check passes; `label_versions.classification` and `theme_set_version`
      optional; per_window keys validated against the windows registry (existing
      cross-doc validator covers topics); `by_status` optional, reuses the `TopicGroup`
      shape, rejects unknown status keys, `unknown` allowed.
- [ ] Implement; regenerate artifacts; full suite green (including `test_schema_export`).
- [ ] Commit: `Extend aggregates contract with topics section (schema 1.1.0)`

### Task 14: Topics aggregation (labels → contract, floored)

**Files:** `pipeline/statsboteval_pipeline/aggregate.py`,
`pipeline/tests/test_aggregate_topics.py`.

**Produces:** extend `build_aggregates` to emit `sections.topics` for the configured
`label_version` when labels exist: per window, per category/theme (all four
distributions), a `floored_count` over the count of messages where present, with the
floor on **distinct students** behind that category/theme; `n_total` = floored message
count in the window; sets `label_versions.classification` and `theme_set_version`;
attaches `label_provenance` + multi-label footnotes. Absent labels → `topics` omitted
(still a valid 1.1.0 document); absent emergent labels → `emergent_themes` omitted from
the window entry.

**Per-status (D-39):** when `student_status` rows exist, also emit `by_status` per
window: sessions resolve via Task 21's `status_at` (usage-time rule at session level;
messages inherit their session's status), each status group runs the identical floored
distribution build, students without a status row group under `unknown` (emitted only
when non-empty), and the `status_rule` footnote attaches. No status rows → `by_status`
omitted; document still valid.

- [ ] Failing tests: hand-seeded corpus + labels → exact topics distributions with a
      category suppressed for sub-floor students; `n_total` floored independently;
      version keys reflect configuration; no labels → no topics section, document still
      valid; a transitioner's messages split bachelor/master by session date across the
      boundary; a sub-floor status group suppresses per cell; no status rows →
      `by_status` omitted.
- [ ] Implement; full suite green.
- [ ] Commit: `Aggregate classification labels into the topics section`

### Task 15: Dashboard Topics tab (retargeted at the D-32 architecture)

**Files:** `dashboard/src/components/tabs/TopicsTab.tsx` (replace the teaser),
`dashboard/src/components/cells/CategoryBars.tsx` (new cell primitive),
`dashboard/dev-fixtures/generate.mjs` (+ topics section), `dashboard/src/lib/footnotes.ts`
(+ new registry entries); regenerate `aggregates.gen.ts` if not already (Task 13).

**Behavior (contract-driven, suppression-aware, per the D-32 conventions):**
- New **`CategoryBars`** cell primitive: horizontal categorical bars sorted by count,
  rendering all four cell states distinctly — ok / ok:0 (explicit zero bar) / suppressed
  (gray baseline mark, "< N students", never 0) / absent (EmptyState) — consistent with
  the established suppression grammar.
- `TopicsTab` replaces the teaser with four cards under the **global window picker**
  (`per_window` key lookup, no client re-aggregation): deductive category prevalences,
  method themes, software themes, **emergent themes**. Each card: APA-style †/‡ registry
  footnotes (multi-label caveat; `label_provenance` showing
  `label_versions.classification` + `theme_set_version`), collapsible data-table twin,
  ChartCard chrome.
- A publish without `topics` (or without `emergent_themes`) renders the explicit
  "not in this data release yet" state (invariant 5) — the teaser copy retires.
- **Status segmented control (D-39):** `All students | Bachelor | Master | Staff`
  (`Unknown` appears only when the group is present in the data) above the four cards;
  selection switches every card to the chosen `by_status` group — a key lookup, never
  client re-aggregation, same rule as the window picker; syncs to a URL query param
  (shareable, D-32 convention). Absent `by_status` hides the control entirely. The
  `status_rule` footnote renders on each card while a status group is selected.
- `dev-fixtures/generate.mjs` emits a synthetic `topics` section across all windows and
  all cell states — including a `by_status` split with one sub-floor group — so FE work
  runs on `NEXT_PUBLIC_DATA_SOURCE=fixture` with no pipeline.
- [ ] Build against the fixture, then the local stack (Azurite + CLI publish incl.
      synthetic labels + uvicorn); verify suppressed/zero/ok/absent distinct and the
      provenance footnote shows.
- [ ] `pnpm build` exports clean.
- [ ] Commit: `Render the Topics tab from the topics section (categorical cell primitive)`

### Task 16: CLI wiring + synthetic label fixtures + operator runbook

**Files:** `pipeline/statsboteval_pipeline/cli.py` (add subcommands),
`pipeline/statsboteval_pipeline/fixtures.py` (synthetic labels for E2E),
`scripts/e2e_local.sh` (extend), `docs/runbooks/classification.md`.

**Produces:**
- CLI subcommands: `extract` · `check-descriptives` · `classify` (deductive + frozen
  themes) · `generate-themes` (stage 1+2 → draft for review) · `freeze-themes` (reviewed
  file → `theme_sets`, stamps `reviewed_at`) · `assign-themes` (emergent assignment) ·
  `import-bergmann --csv PATH` · `validate`. `run-synthetic` gains `--with-labels`
  seeding deterministic synthetic labels (all four domains) so the E2E slice and demo
  show a populated Topics tab without any API call.
- **`run-weekly` chains classification (D-38):** after `detect-language`, run `classify`
  (deductive + frozen themes) and — once a reviewed theme set exists — `assign-themes`,
  before aggregation; `--skip-classify` mirrors `--skip-extract` for offline runs.
  Task 9's idempotency keeps the weekly increment safe and cents-cheap.
- Operator runbook: the full order (extract → classify → generate/review/freeze → assign
  → aggregate → publish); the one-off `import-bergmann` + `validate` on the public
  dataset; the theme-review step spelled out as the privacy control (D-33); the
  theme-set regeneration (v2) note (per-semester operator review, D-38).
- [ ] Failing tests: `run-synthetic --with-labels` produces a document whose `topics`
      (incl. `emergent_themes`) validates and whose `data_provenance == "synthetic"`;
      `validate` on a seeded two-version corpus prints a well-formed report;
      `run-weekly` stage order includes classify (stub client), `--skip-classify`
      bypasses it, guard behavior unchanged.
- [ ] Extend `e2e_local.sh` to assert a dense `topics` section end-to-end; run it.
- [ ] Commit: `Wire classification CLI, synthetic labels, and operator runbook`

### Task 17: Erasure runbook + CLI — NEW (pulled from Part 4; publish precondition)

**Files:** `pipeline/statsboteval_pipeline/erase.py`, CLI subcommand `erase-student`,
`pipeline/tests/test_erase.py`, `docs/runbooks/erasure.md`.

**Produces:** the end-to-end erasure procedure the consent addendum requires, executable
before any real aggregate is public: `erase-student --uid <uid>` → normalize + recompute
`HMAC(uid, pepper)` → delete the student's rows from `students`, `messages`, `labels`,
`theme_candidates` → re-aggregate → republish (guarded) → append the completion date to a
local (git-ignored) erasure log. The runbook documents the flow, Daniel's role as erasure
*contact*, and the pepper dependency (D-34: no pepper, no erasure — hence the backup).

- [x] Failing tests (synthetic corpus, fake publisher): erasure removes exactly the
      target student's rows across all tables; re-aggregation output no longer reflects
      them; unknown uid is a clean no-op with a warning; log line appended.
- [x] Implement; full suite green.
- [x] Commit: `Add student erasure procedure (recompute, delete, re-aggregate, republish)`

**Done 2026-07-17 via the go-live plan (GL6, commit `dca9858`)** — a go-live publish
precondition. Note for Stage 2: erasure must also cover `theme_candidates` once
migration 004 exists (the spec above already lists it).

### Task 18 (operator + infra): Azure OpenAI provisioning (Sweden Central, DZS, gpt-5-mini)

**Files:** `infra/scripts/` (provisioning script alongside the existing az-CLI scripts),
`.env.example`.

- [ ] Verify gpt-5-mini **Data Zone Standard** deployability in MOPS / Sweden Central
      (`az cognitiveservices model list`) — closes D-30's open confirmation.
- [ ] Provision the Azure OpenAI resource in the shared **`Lehrprojekt`** RG (operator
      has no RG-create rights — D-31 finding) + the gpt-5-mini deployment with the DZS
      SKU; script it like the existing `infra/scripts` so it's reproducible.
- [ ] Auth: API key into `pipeline/.env` (operator lacks `roleAssignments/write`, so
      managed-identity/RBAC is out for now — same constraint D-31 recorded for blob).
- [ ] Live smoke test (the Task 8 `skipif` test) passes against the deployment.
- [ ] Commit: `Add Azure OpenAI provisioning script (Data Zone Standard, gpt-5-mini)`

### Task 19 (operator, public data — not CI): validation run & model decision

Not a code task; a recorded operator step once Tasks 4–12 and 18 land.

- [ ] Import `bergmann-v1` from the local copy of the public `full_dataset.csv`; run
      `statsboteval-v1` (gpt-5-mini) over the public 1,400 messages; run `validate`.
- [ ] Record per-category MCCs in the **local** validation report (git-ignored, per
      D-16). If any category falls well below the Bergmann reference, decide per D-30's
      escalation: bump that category (or the whole run) to **gpt-5.1**, and/or split the
      fragile category into its own prompt call (config change, no rewrite). Re-run,
      re-record.
- [ ] Note the chosen production model + version in `docs/decisions.md` (amend D-30) and
      in `label_versions.classification` for real publishes.

### Task 20a (operator, real data): Stage 1 — real-corpus run & first topics publish

**Preconditions (all in-plan):** Task 19 model decision recorded; Task 21 landed and
`import-status` run with the roster CSV (so `by_status` populates in this publish);
publish guard green (the former recon/extract/erasure preconditions closed via D-35
and GL6).

- [ ] Fresh extract; `import-status` with the roster-session CSV; `classify` (deductive
      + frozen method/software themes) over the corpus with the Task-19 model — via
      `run-weekly` with classification enabled or stepwise.
- [ ] Aggregate (floor N=3, D-34) → publish guard → publish to Blob. `topics` goes live
      on tab #1 with three distributions; the `emergent_themes` card renders its
      designed absent state (invariant 5).
- [ ] Record in `docs/decisions.md` (date, model, corpus snapshot size); update `README`
      demo notes if needed.

### Task 20b (operator, real data): Stage 2 — emergent themes & republish

- [ ] `generate-themes` over the real corpus → **operator reviews the draft theme list**
      (short, generic, non-identifying — the D-33 control) → `freeze-themes` as
      `statsboteval-themes-v1` → `assign-themes`.
- [ ] Re-aggregate → publish guard → republish; `emergent_themes` and
      `theme_set_version` appear on the Topics tab.
- [ ] Record completion in `docs/decisions.md` (theme-set version).

### Task 21: Student-status dimension (migration 005, `import-status`) — NEW (D-39)

**Files:** `pipeline/migrations/005_student_status.sql`,
`pipeline/statsboteval_pipeline/status.py`, CLI subcommand `import-status`,
`pipeline/tests/test_status.py`; `erase.py` (extend); runbook note.

**Produces:** the program-level dimension (consent confirmed 2026-07-18, D-39;
independent of Tasks 5–12 — can land any time, must precede any per-status aggregation):

```sql
CREATE TABLE student_status (
  pseudonym         TEXT PRIMARY KEY,
  status            TEXT NOT NULL,   -- 'bachelor' | 'master' | 'staff'
  ma_start_semester TEXT,            -- NULL unless BA→MA transitioner ('2025W', ...)
  provenance        TEXT NOT NULL    -- source list, e.g. 'roster-mar25' | 'doktorat'
);
```

- `import-status [--csv PATH]`: read the roster-derived CSV
  (`uid,status,ma_start_semester,source`, one row per student) from
  `STUDENT_STATUS_CSV` in the git-ignored `pipeline/.env` (the file lives **outside the
  repo tree**, beside its source Excels — custody rules in
  `docs/ethics/data-handling.md` §program-level), normalize + HMAC the uid **in
  flight** (identical discipline to `extract.py` — identifiers never enter the repo
  tree or the corpus), upsert. Report corpus pseudonyms lacking a status row (drift
  indicator — the roster derivation is a snapshot; refresh + re-import each semester,
  runbook note).
- `status_at(row, session_started)` resolution helper implementing the **usage-time
  rule at session level** (owner, 2026-07-17): `master` iff `ma_start_semester` is set
  and the session's `started` falls on/after that semester's calendar start (S → Mar 1,
  W → Oct 1); else the stored `status`; no row → `unknown`. A session never straddles
  two statuses.
- `erase-student` extends to delete from `student_status`; the erasure runbook gains
  the operator step of also removing the student's row from the roster CSV (else the
  next re-import restores it — `docs/ethics/data-handling.md` §program-level).
- [ ] Failing tests (synthetic): HMAC/normalization parity with extract; transitioner
      resolution across the boundary incl. break-month sessions (Aug before an Oct
      transition → still bachelor); upsert idempotence; missing-row → `unknown` +
      reported; erasure covers the table.
- [ ] Implement; full suite green.
- [ ] Commit: `Add student-status dimension with usage-time resolution`

The CSV itself is produced in the roster-derivation session (owner call 2026-07-18:
the validated list semantics and overlap analysis live there — re-deriving here from a
summary risks divergence from the 180/182-validated labeling; exporting there is
trivial). It stays **uid-keyed** (D-39): only this repo's two blessed code paths ever
map uid→pseudonym, the file survives pepper rotation, and rows stay spot-checkable
against the rosters; custody = the records directory **outside the repo tree**, beside
the roster Excels, verified against the primary ethics documents (EK 01548 + consent
addendum — `docs/ethics/data-handling.md` §program-level).

---

## Verification summary

Unit (pytest, no network, no real data): HMAC determinism + normalization + pepper
interlock; descriptives on a hand-seeded corpus; labels round-trip + version coexistence;
codebook parse; prompt determinism; strict response parse (accept/reject);
client build + retry (stub transport); runner idempotence + resume (stub client);
candidate generation idempotence + synthesis-input hygiene (codes only) + review-gate
enforcement; bergmann import provenance split; hand-computed MCC; topics contract
round-trip + 1.0.0-still-valid + schema-export drift; hand-seeded topics aggregation with
suppression; erasure completeness. Integration/E2E: `e2e_local.sh` asserts a dense topics
section through Azurite → API → dashboard; `skipif`-guarded live smokes for MySQL and
Azure OpenAI. Operator: Task 3 descriptives check (real, local), Task 19 validation run
(public), Task 20 reviewed publish (real). Throughout: ruff + mypy green in `pipeline/`;
`pnpm build` exports clean.

## Out of scope (→ later plans)

Replicating Bergmann's *set-conditioned* complex inductive passes (non-statistical
interaction / capability request / declarative statement as separate theme sets — our
emergent pass is corpus-wide and our own; D-33); the missing Declarative Statement
production prompt and production repetition protocol (open Bergmann items;
`docs/open-questions.md`); Azure OpenAI **Batch** SKU cost optimization (sync calls
suffice at this corpus size — revisit if Task 1's volume says otherwise); per-course
(`lv`) topic segmentation (no source — Task 1 recon); extending the per-status split
beyond topics (e.g. the Language tab's de/en mix by program level — Bergmann's 75.7%
vs 46.1% suggests it's worth a later iteration);
theme-set regeneration (`statsboteval-themes-v2`) as new semesters accrue (per-semester
operator review, D-38); returning the Bergmann materials to the public repo (gated on
the team's formal publication, D-16). The `run-weekly` wrapper and Phase A Parts 3–4
widening, listed here originally, were delivered by the go-live plan (D-36/D-37).

## Related decisions

D-07 (label versioning) · D-16 (Bergmann materials local) · D-20 (direct-MySQL extract) ·
D-22 (public Stage-2 canon) · D-24 (privacy floor working value) · D-25 (aggregates
contract v1) · D-30 (classifier model, consolidated prompt, public validation, schema
1.1.0) · D-32 (dashboard tab IA the Topics tab lands in) · D-33 (this re-scope: real
data end-to-end, emergent themes, extract pulled forward) · D-34 (gates closed: pepper
custody, N=3, architecture sign-off).

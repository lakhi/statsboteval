# Runbook: topic classification (Phase B, D-38/D-39)

Operator guide for the classification layer. All commands run from `pipeline/`
on the local machine holding the corpus; chat text leaves it only transiently to
the consented Azure OpenAI EU Data Zone Standard deployment (D-30/D-34) and is
never persisted cloud-side.

## Prerequisites (once)

- `.env` filled in per `.env.example`: MySQL source, `PSEUDONYM_PEPPER`,
  `AZURE_OPENAI_*`, `BERGMANN_PROMPTS_DIR`, `STUDENT_STATUS_CSV`.
- `BERGMANN_PROMPTS_DIR` points at the git-ignored materials directory holding
  `wrapper.txt`, `categories.md` (all 13 categories), `method_themes.txt`,
  `software_themes.txt` (frozen Stage-1 theme lists from the public Stage-2 data).
- `STUDENT_STATUS_CSV` points at the roster-derived `uid,status,ma_start_semester,source`
  file OUTSIDE the repo tree (docs/ethics/data-handling.md, program-level section).
  uids are HMAC'd in flight at import; plaintext uids never enter the corpus.

## Weekly run

`run-weekly` chains everything (D-38): extract → detect-language → classify →
aggregate → guard → write/upload. Classification is idempotent per
(`history_id`, label version) — already-labeled messages are skipped, so the
weekly incremental cost is only the new messages.

```sh
.venv/bin/python -m statsboteval_pipeline.cli run-weekly \
  --corpus data/corpus.duckdb --out data/aggregates.json   # review, then add --upload
```

- `--skip-classify` publishes without the classification pass (no Azure OpenAI
  needed — e.g. quota outage). Topics stay at their previous published state
  only if you also skip upload; an upload without labels for new messages
  undercounts the current week until the next full run.
- `--skip-extract` publishes the corpus as-is (no VPN).

Refresh the status table whenever the roster derivation is re-run (start of
each semester, or after an erasure):

```sh
.venv/bin/python -m statsboteval_pipeline.cli import-status --corpus data/corpus.duckdb
```

Unmatched corpus students aggregate as `unknown`; the importer prints a drift
report so you notice when the roster needs a refresh.

## One-off: bergmann-v1 import + validation (Task 19 gate)

Before trusting `statsboteval-v1` on real data, import Bergmann's public
Stage-2 coded dataset and compare per-category MCC on the 300 human-consensus
messages:

```sh
.venv/bin/python -m statsboteval_pipeline.cli import-bergmann \
  --corpus data/corpus.duckdb --csv /path/to/full_dataset.csv   # git-ignored local copy
.venv/bin/python -m statsboteval_pipeline.cli validate --corpus data/corpus.duckdb
```

Label versions coexist (D-07), so `--label-version` scores whichever one you ask
for against the same 300 consensus messages — run it once per version to compare
them directly. The report names the version it scored and prints the average MCC
(the mean over scoreable categories; NA categories are excluded, not counted as
zero — that is how the .71/.82 figures in D-42/D-45 are derived).

```sh
.venv/bin/python -m statsboteval_pipeline.cli validate \
  --corpus data/corpus.duckdb --label-version statsboteval-v2
```

The importer refuses to write if the (`history_id`, `started`) join fingerprint
mismatches — that protects against classifying against the wrong corpus. The
validation report is advisory: the model decision (keep gpt-5-mini vs escalate)
is recorded in `docs/decisions.md` when made, and `CLASSIFIER_MODEL_TAG`
in `.env` must match the deployment that produced the published labels.

Note: the public `full_dataset.csv` carries the 13 deductive categories only;
Bergmann's theme codings are not in the public release, so validation covers
the deductive pass (documented plan deviation, Task 10).

## Stage 2: emergent themes (D-33/D-38)

One-off per theme-set version (then `run-weekly` maintains assignments):

```sh
.venv/bin/python -m statsboteval_pipeline.cli generate-themes --corpus data/corpus.duckdb
# -> REVIEW data/theme-draft-<set_version>.md by hand (see below), then:
.venv/bin/python -m statsboteval_pipeline.cli freeze-themes \
  --corpus data/corpus.duckdb --draft data/theme-draft-<set_version>.md
.venv/bin/python -m statsboteval_pipeline.cli assign-themes --corpus data/corpus.duckdb
```

`generate-themes` runs both inductive stages: per-message candidate codes into
the local-only `theme_candidates` table (idempotent/resumable like `classify`),
then one synthesis call — over the distinct code list only, no chat text — that
writes the draft file. The **review of that draft is a privacy control**, not
polish: every label derives from real chat text, so check each one for
identifying content (names, unique incidents, quoted phrasing) and edit the
table freely before freezing. `assign-themes` (and the `run-weekly` chaining)
refuses any set without a `reviewed_at` stamp, and `freeze-themes` refuses to
overwrite an existing version.

Once a reviewed set matching `CLASSIFIER_THEME_SET_VERSION` exists, `run-weekly`
chains `assign-themes` after `classify` and stamps `theme_set_version` into the
published document. Regenerating themes later (new data, prompt change) mints a
NEW `theme_set_version` with its own review — published versions are immutable;
the dashboard reads one configured version.

## Full re-classification (a new label version)

Minting a new label version means re-classifying the whole corpus, which is a
multi-hour unattended run rather than a weekly incremental. Three things have bitten
this project on such runs (an overnight sleep stall, two network drops, a stopped
parent shell), so launch it detached, on AC power, under `caffeinate`:

```sh
nohup caffeinate -dims .venv/bin/python -u -m statsboteval_pipeline.cli classify \
  --corpus data/corpus.duckdb >> data/classify-<version>-<date>.log 2>&1 &
disown
```

- **AC power is required, not advisory.** `caffeinate` only inhibits system sleep
  when plugged in; on battery the machine still cycles into Maintenance Sleep.
- **`nohup` + `disown`** detach the run from the launching shell so it survives the
  terminal (or agent session) going away. `-u` keeps the heartbeat unbuffered.
- **Budget by batches × 3, not by batches.** `classify_corpus` piggybacks the
  method- and software-theme passes onto every deductive batch (`THEME_PASSES`),
  so one batch is three API calls. At `CLASSIFIER_BATCH_SIZE=10` the 4,419-message
  corpus is 442 batches ≈ 1,326 calls ≈ 35-40 s per batch ≈ **4-5 h**. Emergent
  `assign-themes` is a separate single-call-per-batch pass on top.
- **Nothing else may touch the corpus while it runs.** DuckDB is single-writer: a
  DBeaver connection (or a second CLI command) either blocks the run from starting
  or is itself refused, and no read-only connection gets in either. Keep GUI clients
  pointed away from `corpus.duckdb` until the pass exits.
- **Interruption is safe.** Each batch commits in its own transaction and the
  resume is an anti-join against `labels`, so re-running the same command continues
  from the last committed batch. On resume the heartbeat denominator shrinks (it is
  the count of *remaining* work, e.g. `10/3749` rather than `10/4419`) — that is
  correct, not a sign of lost data. Verify it equals total minus already-labeled.
- **Keep the previous version.** Do not delete the old label version until the new
  one is validated and published; it is both the comparison baseline and the
  rollback path, and `erase-student` clears every version for a student anyway.

## When the Azure deployment changes

Model upgrades/redeployments (Task 18 catalog drift) require: re-verify the
deployment is EU Data Zone Standard, update `AZURE_OPENAI_DEPLOYMENT` /
`CLASSIFIER_MODEL_TAG`, and mint a new label version if the model changed —
never mix models within one label version.

The same rule covers **inference settings, not just the model** (D-41): a change to
`CLASSIFIER_REASONING_EFFORT`, `CLASSIFIER_BATCH_SIZE`, or the codebook materials
means a new `CLASSIFIER_LABEL_VERSION` and a full re-classify. Batch size counts
because it changes how many decisions one call is asked for, which measurably moves
accuracy (D-45) — it is an inference parameter here, not a throughput knob.

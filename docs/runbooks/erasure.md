# Runbook: student erasure

The informed-consent addendum grants every participant erasure on request (see
`docs/ethics/data-handling.md`). This runbook is the executable procedure; it is a
**go-live precondition** (D-33/D-34): no real aggregate is public unless this works.

## Roles

- **Erasure contact: Daniel.** Requests arrive via him (he can map a requesting
  student to their StatsBot uid). The operator (Akshay) executes.
- The uid travels person-to-person for the erasure only; it is never stored by this
  project — the corpus knows only `HMAC(normalized uid, pepper)`.

## Preconditions

- The corpus pepper (`PSEUDONYM_PEPPER` in `pipeline/.env`). **No pepper, no erasure**
  (D-34): the pseudonym cannot be recomputed without it, which is why the pepper has a
  password-manager backup. The CLI refuses to run on a pepper mismatch or a corpus
  without a stored fingerprint — a wrong pepper would otherwise "succeed" while
  deleting nothing.
- No VPN or production-DB access is needed; erasure touches only the local corpus and
  the published blob.

## Procedure

From `pipeline/`:

```sh
.venv/bin/python -m statsboteval_pipeline.cli erase-student \
  --corpus data/corpus.duckdb --uid <uid-from-daniel> --upload
```

What it does, in order:

1. Verifies the pepper fingerprint against the corpus (`meta` table).
2. Recomputes `HMAC(normalize(uid), pepper)` and deletes that pseudonym's rows from
   `labels`, `messages`, `student_status`, and `students` (in that order — labels
   reference messages).
3. Prints per-table deletion counts. An unknown uid is a warned no-op (check the uid
   with Daniel; a typo must not look like a completed erasure).
4. Re-aggregates and re-runs the publish guard; `--upload` overwrites `v1/latest.json`
   so the dashboard stops reflecting the student immediately.
5. Appends a completion line (UTC date, truncated pseudonym, per-table counts — never
   the uid) to the git-ignored local log `pipeline/data/erasure.log`.

## Afterwards

- **Delete the student's row from the roster CSV** (`STUDENT_STATUS_CSV`, outside the
  repo beside the roster Excels) — otherwise the next `import-status` re-import
  restores their status row (D-39; `docs/ethics/data-handling.md`, program-level
  section). Do the same in any roster re-derivation.
- Reply to Daniel with the completion date (the log line is the record).
- Note: previously published **immutable** versioned blobs under `v1/` may still
  contain the student's contribution inside floored aggregate counts — no individual
  data, but delete blobs older than the erasure if the request demands it
  (Azure portal or `az storage blob delete`).
- The extract watermark is unaffected; future extracts will re-ingest the student's
  rows **only if they still exist in the source DB** — confirm with Daniel that the
  source-side erasure (StatsBot's own obligation) happened first, or the next
  `run-weekly` resurrects the data locally.

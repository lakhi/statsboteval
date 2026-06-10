# Decision log

ADR-style, newest at the bottom. Record significant choices and reversals here.

## 2026-06-10 — founding session (planning round with Claude Code)

**D-01 · Separate repo.** StatsBotEval lives in its own repo, not inside the StatsBot repo.
The projects share *data, not code* — the only coupling is the shape of two MySQL tables,
documented in `source-data-dictionary.md`. Drivers: different publication destinies (thesis
code public/citable vs production university app), different people (co-authors don't need
prod-app access), different lifecycles (active thesis development vs maintenance mode),
tooling cleanliness, GDPR hygiene (clonable without the prod app). Accepted costs: extra
clone; manual data-dictionary sync on schema changes.

**D-02 · Repo scope = whole framework.** Milestone 1 (dashboard) and milestone 2 (ML
analysis) share this repo and the local data layer. Repo named `statsboteval`, matching the
abstract/thesis brand.

**D-03 · Weekly batch, not real time.** The abstract's "real time" is reinterpreted as a
weekly refresh — educators check week over week; bounded classification cost; no live
connection to defend.

**D-04 · Local corpus / cloud aggregates split.** Forced by the consent addendum
("password-protected local storage medium"): the pseudonymized corpus stays local; Azure
receives only privacy-floored aggregates. Supersedes the earlier in-session idea of an Azure
Postgres research DB. See `ethics/data-handling.md`.

**D-05 · Pseudonyms = HMAC(uid, secret pepper).** Stable across runs without a stored mapping
table; erasure = recompute + delete. Pepper custody to be fixed (open question).

**D-06 · Local corpus DB = Postgres in Docker.** Mirrors the health-research-agent-api
pattern (compose, lazy init); real SQL for aggregation; volume on the protected disk.

**D-07 · Versioned classification labels.** Import the team's labels as `bergmann-v1`; our
automated pipeline writes `statsboteval-v1`. Dashboard reads one configured version; overlap
doubles as a validation set. Classification is in milestone 1, phased: Phase A descriptive
dashboard first, Phase B classification pipeline.

**D-08 · Conversation = `started` session.** StatsBot's app-native grouping (one "new chat"
click). Derived sessionization can be added later for comparability with the Bergmann study's
student+time reconstruction.

**D-09 · Privacy floor from day one.** Every published aggregate suppresses cells covering
fewer than N students (working N = 5; confirm against ethics protocol) — applied locally at
aggregation time, making the public cloud side structurally non-identifying.

**D-10 · Publish path = file to Azure Blob.** The pipeline uploads one versioned aggregates
file; the API reads it. No cloud database; "refresh" = a new file version; history retained.

**D-11 · Stack = Angular SPA + FastAPI on Azure.** Follows the health-research-agent-api
deployment pattern (FastAPI, Docker, env switching). Matches existing skills (Angular daily in
StatsBot; FastAPI/Azure in health-research-agent-api) and produces a thesis-grade artifact.

**D-12 · No auth in the feedback phase.** Dashboard is public by URL to ease feedback —
acceptable because only privacy-floored aggregates exist cloud-side. Revisit before wide
circulation; auth designed to be added later.

**D-13 · Dashboard UI in English.** German can be added via Angular i18n if educators ask.

**D-14 · Docs in repo.** Abstract as Markdown + canonical PDF; consent addendum PDF + extracted
constraints; source data dictionary; Bergmann framework reference; this log; open questions.
The ZID presentation (3.9 MB ODP) is linked, not committed. No data files, ever.

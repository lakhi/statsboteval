# Part 2 Thin-Slice Implementation Plan (walking skeleton, end-to-end, deployed)

**Goal:** Part 2 of the Phase A plan (`2026-06-12-milestone-1-phase-a.md`): one synthetic
metric set — weekly **messages**, **sessions**, **active students** — through every layer:
synthetic fixtures → DuckDB corpus → aggregation + privacy floor → publish guard → Azure
Blob (§9 protocol) → FastAPI → Next.js dashboard, **deployed to Azure** with a public demo
URL showing clearly-labeled synthetic data.

**Architecture (decisions D-17, D-18, D-23, D-26, D-27):**

```
pipeline/  (extends the existing package)          api/            dashboard/
  corpus.py      DuckDB open + migrations            FastAPI:        Next.js 15, TS,
  fixtures.py    synthetic students/history          /healthz        Tailwind, Recharts,
  aggregate.py   weekly counts + floor →             /api/v1/        output:'export';
                 Aggregates doc (contract.py)          aggregates    types generated from
  publish.py     guard + blob upload (§9)            + serves the    schema/aggregates
  cli.py         run-synthetic entry                 dashboard         .schema.json
                                                     bundle (D-26)
infra/     Bicep + az-CLI scripts (D-26): RG statsboteval-rg (Sweden Central),
           ACR, Storage (private container `aggregates`), Container Apps env + one app
```

**Tech stack:** existing `pipeline/` package + `duckdb`, `azure-storage-blob`,
`hypothesis` (dev); `api/` = FastAPI + uvicorn + `jsonschema` + `pydantic-settings` +
`azure-storage-blob` (own package, own venv, same ruff/mypy/pytest config as pipeline);
`dashboard/` = Next.js 15 + TypeScript + Tailwind + Recharts + `json-schema-to-typescript`
(pnpm, mirroring agent-ui); Azurite (npm) for local blob emulation — no Docker daemon
needed locally except for the image-build task.

## Global constraints

- **No real student data anywhere in Part 2.** Every fixture is generated, seeded, and
  self-labels (`data_provenance: "synthetic"`, pseudonyms `syn-NNNN`, message text
  prefixed `SYNTHETIC`). The `.gitignore` data exclusions are untouched; the DuckDB corpus
  file lives outside git (`*.db` is already ignored) and is disposable/regenerable.
- **Cells are constructed only via `floored_count()`** (aggregate.py). No other code path
  may build an `OkCell`/`SuppressedCell` from corpus numbers — this plus the property test
  is the thin slice's floor guarantee; the independent evidence-recomputing publish guard
  arrives with Part 3 (noted in Out of scope).
- The blob is **private** (D-18); connection strings live in `.env` files (git-ignored)
  and Container App secrets, never in code or Bicep param files committed with values.
- Contract invariants bind: complete ISO weeks only (invariant 3, bucketing in
  `Europe/Vienna`); dense weekly series; suppressed ≠ zero ≠ absent — the dashboard
  renders each distinctly (D-27 wrapper).
- Amounts of new config: `first_week` and `data_through_week` are **derived from the
  corpus + clock**, never hardcoded. Synthetic `created_at` is UTC (prod timezone is a
  recon question in `open-questions.md`).
- Work from each component's own directory (`pipeline/`, `api/`, `dashboard/`); commit
  after every task, plain imperative messages.
- When building dashboard UI, load the `frontend-design` and `dataviz` skills first
  (session-level instruction, not a code artifact).

---

### Task 1: DuckDB corpus module

**Files:** `pipeline/migrations/001_corpus_init.sql`,
`pipeline/statsboteval_pipeline/corpus.py`, `pipeline/tests/test_corpus.py`;
modify `pipeline/pyproject.toml` (add `duckdb>=1.0`).

**Produces:** `open_corpus(path: Path) -> duckdb.DuckDBPyConnection` — opens/creates the
file and applies pending numbered migrations (tracked in a `_migrations` table);
`MIGRATIONS_DIR` constant.

Schema (pseudonym-keyed; mirrors what aggregation needs from
`docs/source-data-dictionary.md` — the corpus never holds direct identifiers):

```sql
CREATE TABLE students (
  pseudonym     TEXT PRIMARY KEY,       -- HMAC output in prod; syn-NNNN in fixtures
  registered_at TIMESTAMP NOT NULL
);
CREATE TABLE messages (
  history_id        BIGINT PRIMARY KEY, -- source history.id
  pseudonym         TEXT NOT NULL,
  session_started   BIGINT NOT NULL,    -- client epoch ms; (pseudonym, session_started) = session (D-08)
  created_at        TIMESTAMP NOT NULL, -- server clock (UTC assumed); THE temporal axis
  sent              TEXT NOT NULL,
  received          TEXT NOT NULL,
  prompt_tokens     INTEGER NOT NULL,
  completion_tokens INTEGER NOT NULL
);
```

- [ ] Failing tests: fresh corpus has both tables + `_migrations` row for 001; reopening
      applies nothing twice; a second migration file 002 (created in tmp by the test)
      applies in order.
- [ ] Implement; run `pytest tests/test_corpus.py`, then full suite.
- [ ] Commit: `Add DuckDB corpus with plain numbered migrations`

### Task 2: Synthetic fixture generator

**Files:** `pipeline/statsboteval_pipeline/fixtures.py`,
`pipeline/tests/test_fixtures.py`.

**Produces:** `seed_synthetic(con, *, weeks: int = 8, seed: int = 42) -> None` —
deterministic (seeded `random.Random`), ~30 students, messages over the last `weeks`
complete ISO weeks. **Shape requirements (tested):** ≥1 week with zero messages (published
0); ≥1 week where exactly 1–2 students are active (exercises suppression at N=3); sessions
= 1–10 messages sharing a `session_started`; DE/EN text snippets all prefixed
`"SYNTHETIC"`; plausible token counts. Registration dates spread so registrations-per-week
will also exercise the floor in Part 3.

- [ ] Failing tests: determinism (same seed → identical row sets); the shape requirements
      above asserted by querying the seeded corpus.
- [ ] Implement; full suite green.
- [ ] Commit: `Add deterministic synthetic corpus fixture generator`

### Task 3: Aggregation + privacy floor → Aggregates document

**Files:** `pipeline/statsboteval_pipeline/aggregate.py`,
`pipeline/tests/test_aggregate.py`, `pipeline/tests/test_floor_property.py`;
modify `pipeline/pyproject.toml` (dev: add `hypothesis`).

**Produces:**
- `floored_count(value: int, n_students: int, floor_n: int) -> OkCell | SuppressedCell` —
  ok iff `n_students == 0 or n_students >= floor_n` (contract invariant 1: the test is on
  students, never magnitude).
- `build_aggregates(con, *, floor_n: int, now: datetime, provenance: Literal[...],
  pipeline_version: str) -> Aggregates`:
  - Rows out of SQL (tiny volumes), ISO-week bucketing in Python via the tested contract
    helpers after UTC→`Europe/Vienna` conversion (`zoneinfo`) — calendar knowledge stays
    in Python, matching the contract's semester principle.
  - `data_through_week` = last ISO week fully elapsed before `now` (Vienna) that is ≤ the
    latest data week; `first_week` = week of earliest message. Weeks with no rows → 0 from
    0 students → published `ok(0)`.
  - Document: metadata per contract §4 (`label_versions={}` — no labels in the slice);
    `windows=[all_time]` with coverage `[first_week, data_through_week]`;
    `footnotes={chat_fragmentation}` (referenced by the sessions series);
    `sections.temporal_usage` = weekly `messages`/`sessions`/`active_students`,
    `per_window={}` (heatmap is a Part 3 scoping question). All construction through
    `contract.py` models — the root validator is the first guard.
- [ ] Failing tests — hand-computed corpus (inserted directly, not via fixtures.py):
      e.g. W1: 3 students / 5 msgs / 4 sessions → all ok; W2: 2 students / 100 msgs →
      all three cells suppressed; W3: empty → ok(0); assert exact dumped cells, density,
      metadata fields, and that `dump_doc(build_aggregates(...))` validates against
      `schema/aggregates.schema.json`.
- [ ] Property test (hypothesis): for all `(value ≥ 0, n_students ≥ 0, floor_n ≥ 1)`:
      suppressed ⟺ `1 <= n_students < floor_n`; an ok cell never exists for a sub-floor
      positive student count (contract §11 property).
- [ ] Implement; full suite green.
- [ ] Commit: `Add weekly aggregation with privacy floor building the contract document`

### Task 4: Publish guard, blob upload, CLI

**Files:** `pipeline/statsboteval_pipeline/publish.py`,
`pipeline/statsboteval_pipeline/cli.py`, `pipeline/tests/test_publish.py`;
modify `pipeline/pyproject.toml` (add `azure-storage-blob>=12.19`).

**Produces:**
- `guard(doc: Aggregates) -> dict` — re-validates: model round-trip, `jsonschema` against
  the **committed** schema artifact, and a dump-walk asserting no `suppressed` cell
  carries any key besides `status` (belt over the model's braces). Returns the canonical
  dumped dict. Raises `PublishGuardError` otherwise.
- `publish(doc, *, connection_string, container="aggregates") -> tuple[str, str]` — §9
  protocol exactly: (1) upload immutable
  `v1/aggregates_{data_through_week}_{generated_at:%Y%m%dT%H%M%SZ}.json` (fail if exists),
  (2) overwrite `v1/latest.json` with identical bytes. Creates the container if missing
  (Azurite/dev convenience; harmless in prod).
- CLI (`argparse`, no new dep): `python -m statsboteval_pipeline.cli run-synthetic
  --corpus PATH --weeks 8 --seed 42 [--out FILE] [--upload]` → seed → build → guard →
  write file and/or upload using `$AZURE_STORAGE_CONNECTION_STRING`.
- [ ] Failing tests: guard passes the Task 3 document and rejects a hand-broken dict
      (suppressed cell with a value injected post-dump); publish against **Azurite**
      (`pytest` fixture launches `npx azurite --inMemoryPersistence` on a free port,
      `skipif` azurite unavailable): both blobs exist, byte-identical, immutable name
      collision raises; CLI `--out` writes a file whose content passes `jsonschema`.
- [ ] Implement; full suite green (`ruff` + `mypy` too — keep them green from here on).
- [ ] Commit: `Add publish guard, §9 blob publish, and run-synthetic CLI`

### Task 5: FastAPI service

**Files:** `api/pyproject.toml`, `api/app/{__init__,main,config,blob_source}.py`,
`api/tests/{test_healthz,test_aggregates}.py`, `api/tests/fixtures/aggregates_synthetic.json`
(generated by the Task 4 CLI, committed — synthetic by construction), `api/.env.example`.

**Produces:**
- `GET /healthz` → `{"status": "ok"}`.
- `GET /api/v1/aggregates` → the `v1/latest.json` document **verbatim** (contract §1):
  read via connection string, validated with `jsonschema` against
  `schema/aggregates.schema.json` on every refresh (tripwire), cached in-memory with TTL
  (`CACHE_TTL_SECONDS`, default 300). Blob missing → 503; validation failure → 500 with a
  logged reason (never serve an invalid document).
- Settings via `pydantic-settings` from `.env` (`AZURE_STORAGE_CONNECTION_STRING`,
  `AGGREGATES_CONTAINER=aggregates`, `CACHE_TTL_SECONDS`, `DASHBOARD_DIST` — Task 8);
  `.env.example` documents local (Azurite `UseDevelopmentStorage=true`) and Azure modes
  (repo `.gitignore` already blocks real `.env*`).
- Same pyproject conventions as `pipeline/` (ruff 120, mypy, pytest; own `uv venv`).
  Schema path resolves `../schema/…` in dev, `/app/schema/…` in the image (env-overridable
  `SCHEMA_PATH`).
- [ ] Failing tests (httpx TestClient, blob source faked via dependency override): healthz;
      happy path serves the fixture verbatim; cache honored within TTL (fake source call
      count); invalid doc → 500; missing blob → 503.
- [ ] Implement; `api/` suite + ruff + mypy green.
- [ ] Commit: `Add FastAPI aggregates service (blob read, schema tripwire, TTL cache)`

### Task 6: Dashboard scaffold + generated types

**Files:** `dashboard/` via `pnpm create next-app` (TS, Tailwind, app router, src dir);
`next.config.ts` with `output: 'export'`; `package.json` script
`gen:types` (json-schema-to-typescript: `../schema/aggregates.schema.json` →
`src/lib/aggregates.gen.ts`, committed); `src/lib/api.ts` (fetch wrapper;
`NEXT_PUBLIC_API_BASE`, default `""` = same origin per D-26).

- [ ] Scaffold; set static export; verify `pnpm build` emits `out/index.html`.
- [ ] Generate types; spot-check `Aggregates`/`CountCell` shapes match the contract
      (discriminated `status`, `from` property on coverage).
- [ ] Commit: `Scaffold Next.js dashboard (static export) with schema-generated types`

### Task 7: Dashboard thin-slice page

**Files:** `dashboard/src/app/page.tsx`,
`dashboard/src/components/{SyntheticBanner,WeeklyTrendChart,SuppressedLegend}.tsx` (names
indicative). **Load `frontend-design` + `dataviz` skills before writing UI code.**

**Behavior (contract-driven, D-27):**
- Client-side fetch of `/api/v1/aggregates`; loading/error states.
- Prominent banner whenever `data_provenance !== "production"`.
- Three weekly trend charts (messages, sessions, active students) via one Recharts
  wrapper: **ok(0) renders as a true 0 point; suppressed renders as a line gap with a
  distinct marker and a "suppressed (< N students)" tooltip using `privacy_floor_n` from
  metadata** — never as 0, never interpolated over silently. Footnote text (sessions →
  `chat_fragmentation`) rendered from the registry beneath the chart.
- Header shows `data_through_date` and window coverage (display math only, invariant 4).
- [ ] Build against the local stack (Azurite + CLI publish + uvicorn,
      `NEXT_PUBLIC_API_BASE=http://localhost:8000 pnpm dev`); verify all three cell states
      visibly distinct (the Task 2 fixture guarantees all three occur).
- [ ] `pnpm build` still exports clean.
- [ ] Commit: `Add thin-slice dashboard page (weekly trends, suppression-aware rendering)`

### Task 8: Single image — API serves the bundle (D-26)

**Files:** `Dockerfile` (repo root, multi-stage: node/pnpm builds `dashboard/out` →
python:3.12-slim installs `api/`, copies `schema/` and the bundle), `.dockerignore`;
modify `api/app/main.py` (mount `StaticFiles(html=True)` at `/` **after** API routes,
only when `DASHBOARD_DIST` exists — dev API runs without it).

- [ ] API test: with a dist dir configured, `/` serves index.html and `/api/v1/*` +
      `/healthz` still win.
- [ ] `docker build` + `docker run` with Azurite connection string
      (`host.docker.internal`): healthz, aggregates, and the dashboard page all answer.
- [ ] Commit: `Serve dashboard bundle from the API container (single image, D-26)`

### Task 9: Local E2E script

**Files:** `scripts/e2e_local.sh` (repo root `scripts/`).

- [ ] Script: start Azurite (in-memory) → `run-synthetic --upload` → start uvicorn →
      poll `/healthz` → assert `/api/v1/aggregates` returns `data_provenance ==
      "synthetic"` and a dense `temporal_usage` → clean shutdown, non-zero exit on any
      failure. Print the manual step (`pnpm dev` against it) for eyeballing the page.
- [ ] Run it; commit: `Add local end-to-end script (Azurite → pipeline → API)`

### Task 10: Azure infrastructure (Bicep + scripts, D-26)

**Files:** `infra/main.bicep` (+ `main.bicepparam`), `infra/scripts/{01_create_rg.sh,
02_deploy_infra.sh,03_release.sh,04_publish_synthetic.sh}`, `infra/README.md`.

**Resources** (RG `statsboteval-rg`, Sweden Central; names parameterized, globally-unique
ones suffixed): Storage account (Standard_LRS, public access disabled, container
`aggregates`), ACR (Basic), Container Apps environment, Container App (0.25 vCPU/0.5 Gi,
external ingress → 8000, min replicas 0, connection string as secret →
`AZURE_STORAGE_CONNECTION_STRING`). Scripts follow the reference `deployment-plan.md`
flow: create RG → deploy Bicep → `az acr login` + build `--platform linux/amd64` + push +
`az containerapp update` → publish synthetic doc using
`az storage account show-connection-string`.

- [ ] `az bicep build` lints clean; `az deployment group what-if` reviewed before create.
- [ ] Commit: `Add Azure infra (Bicep) and deploy scripts`

### Task 11: Deploy, verify, record

- [ ] Run scripts 01→04. Verify from outside: `curl https://<fqdn>/healthz`;
      `curl https://<fqdn>/api/v1/aggregates | jq .data_provenance` → `"synthetic"`;
      dashboard renders in a browser with the synthetic banner and all three cell states.
- [ ] Record the demo URL + operational notes (release = `03_release.sh`; republish =
      `04_publish_synthetic.sh`) in `infra/README.md`; link from the root README.
- [ ] Update the Phase A plan doc: mark Part 2 done with the demo URL.
- [ ] Commit: `Deploy thin slice to Azure; record demo URL`

---

## Verification summary

Unit: corpus migrations, fixture determinism + shapes, hand-computed aggregation, floor
property test (hypothesis), guard accept/reject, API contract behaviors. Integration:
Azurite publish round-trip; Docker image smoke. E2E: `scripts/e2e_local.sh` locally, then
Task 11's external checks against the live URL. Throughout: `ruff` + `mypy` green in both
Python packages; `pnpm build` exports clean.

## Out of scope (→ later plans)

Part 3 metric widening (histograms, user classes, language, registrations view; heatmap
**pending the educator-value scoping question** in `open-questions.md`); the
evidence-recomputing publish guard (independent distinct-student recount per cell —
arrives with Part 3's aggregation layer); real extract/pseudonymization and go-live gates
(Part 4); auth (D-12); GitHub Actions CI (deferred per D-26); custom domain; Phase B
classification (planning starts after Part 2 per the 2026-07-05 re-scope).

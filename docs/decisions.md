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

**D-15 · Repo is public on GitHub.** Published at https://github.com/lakhi/statsboteval for
thesis reproducibility. The committed PDFs are public-facing documents already (the abstract
is a conference submission; the consent addendum is shown to every student at registration).
The no-data-in-git rule (D-14, `ethics/data-handling.md`) is what makes public visibility safe.

## 2026-06-12 — decision review session (full D-01…D-15 re-validation with Claude Code)

All founding decisions were re-examined with rationale. Twelve stand unchanged; the entries
below record the changes, plus two new facts that reshaped the plan: direct MySQL access to
the production DB exists, and milestone 1 build order was chosen.

**D-16 · Bergmann framework reference is local-only until their study is published.**
(Amends D-14/D-15.) `docs/bergmann-framework.md` distills the team's work-in-progress study
document and contains unpublished results (validation MCCs, rater scores, descriptives,
theme counts) — publishing them in a public repo before the team's paper was an oversight.
Removed from git history (`git filter-repo`, force-pushed 2026-06-12; repo had no forks),
kept locally, excluded via `.gitignore`. Restore to the repo after their publication.

**D-17 · Local corpus DB = DuckDB.** (Supersedes D-06.) The workload is single-writer,
weekly-batch, scan-and-aggregate — embedded OLAP territory, not client–server OLTP. DuckDB
makes the corpus one file on the FileVault-encrypted disk (the cleanest reading of the
consent's "password-protected local storage medium"), removes the Docker-daemon dependency
from every local run, and hands query results zero-copy to pandas for milestone 2. Plain
numbered `.sql` migrations replace alembic. D-06's "pattern reuse" rationale actually
belongs to the cloud deployment (FastAPI/Docker/Azure), which is unaffected — cloud-side
StatsBotEval has no database at all (D-10).

**D-18 · API-tier rationale corrected; aggregates blob is private.** (Amends D-11/D-10.)
The strongest reason for the FastAPI tier is not skill match but that it is the future
**auth boundary** (D-12 plans auth later; a static-SPA-reads-blob design would need the API
retrofitted then anyway) and the stable contract while the blob format evolves. Accordingly
the blob is kept private with the API reading via connection string — more restrictive than
D-10's public-by-URL allowance; only the dashboard URL is public.

**D-19 · Milestone 1 build order = walking skeleton.** Chosen over pipeline-first and
dashboard-first: define the aggregates contract, push one synthetic metric end-to-end
through pipeline → blob → API → SPA deployed on Azure early, then widen metric by metric.
Retires deployment/integration risk first and produces a demo URL for team feedback from
the start. Plan: `docs/plans/2026-06-12-milestone-1-phase-a.md`.

**D-20 · Weekly extract = scripted direct-MySQL pull with in-flight pseudonymization.**
(Refines D-03/D-05; resolves the export-capability open question.) A direct MySQL
connection to the production DB exists, so the extract is scripted: incremental by
`history.id` watermark, HMAC applied in-flight — raw identifiers flow from MySQL through
memory into the pseudonym and are never persisted locally. The corpus is therefore fully
reproducible from the source DB until the mid-2027 export deadline, which also lowers the
stakes on pepper rotation (worst case: re-ingest).

## 2026-06-19 — Bergmann materials review

**D-21 · Bergmann source-of-truth hierarchy.** (Refines D-16.) The team's work-in-progress
results manuscript is the canonical source for every Bergmann-derived fact in this repo; the
OSF Stage-1 registered-report PDFs are an earlier, superseded artifact (they predate the final
model, sample, and production-codebook decisions) and must not be relied on for those details.
The reconciliation, the verbatim coding prompts, and the canonical-source pointer all live in
the git-ignored local docs `bergmann-framework.md` and `bergmann-prompts.md` (kept local per
D-16). Two open handover items remain (message join key; bachelor/master mapping source); the
exact prompts and OSF review are now closed (`open-questions.md`).

## 2026-07-02 — Bergmann Stage-2 release review

**D-22 · Bergmann canon = the public Stage-2 OSF/Zenodo release.** (Supersedes D-21's
working-doc canon.) On 2026-06-30 the team published the PCI RR **Stage 2 Full Manuscript
(final)** and a complete "Stage 2 - R Code and Data" folder (coded dataset, final theme
lists, production inductive prompts, analysis scripts) at https://osf.io/v8ydk/, plus the
raw 1,400 chat messages on Zenodo (https://doi.org/10.5281/zenodo.20827020, open access).
The working Google Doc — the draft of this manuscript — is retired as a source. All local
Bergmann docs were re-reconciled against the release; corrections of record: 182 users (not
192), study window 2025-03-15→2025-06-30, bachelor onboarding 2025-05-16, delivered labels
are 300 human-consensus + 1,100 GPT-5 rows. The former handover items (coded dataset, join
key = `history.id`, theme lists) resolved themselves via the public release; the remaining
Bergmann asks are narrower (`open-questions.md`). **Flag for next decision review:** D-16
keeps `bergmann-framework.md` local "until their study is published" — the results are now
public on OSF/Zenodo but the paper awaits formal PCI RR recommendation; decide whether the
doc returns to the public repo now or after recommendation.

## 2026-07-02/03 — decision review session (full D-01…D-22 re-validation with Claude Code)

All decisions re-examined with rationale ahead of Phase A implementation. The architecture
stands; the one change is the dashboard frontend (below). Micro-decisions confirmed along
the way: published time bucket = ISO week (Mon–Sun), daily granularity stays internal;
conversation-count views carry a footnote that the credit UI nudges chat fragmentation
(D-08); corpus label tables will record per-row provenance (`human_consensus` vs `gpt5`)
for the `bergmann-v1` import; classifier policy is quality-first on the consented Azure
OpenAI EU platform (`open-questions.md`).

**D-16 flag resolved: `bergmann-framework.md` stays local.** Reviewed against the public
Stage-2 release: restoring the doc to the public repo gains nothing concrete (no Phase A
dependency), so it remains local-only until the team's paper is formally
recommended/published — D-16's original wording already covers this; no amendment needed.

**D-23 · Dashboard frontend = Next.js (static export), mirroring agent-ui.** (Amends D-11;
touches D-13.) D-11's frontend rationale ("Angular daily") is stale — development is now
agent-driven rather than hand-fluent, which changes the optimization target. What survives
of D-11 is pattern reuse, and for the frontend that now points at
`~/Developer/uni-studAsst-projects/ai_agents_ws/agent-ui` (Next.js 15 + React + Tailwind +
Radix, a working deployed example) exactly as health-research-agent-api anchors the API
tier. Drivers: agentic-coding fluency (React's training-data density, post-hooks idiom
stability vs Angular's recent API churn, single-file component locality), the owned
reference implementation, and the richer React charting ecosystem. Static export
(`output: 'export'`) keeps the deployment shape a plain static bundle — no Node server.
Backend (FastAPI), deploy pattern, and the D-18 auth boundary are unchanged; D-13
(English-only) unchanged, future German via next-intl instead of Angular i18n. Accepted
cost: framework split vs StatsBot's Angular — fine because the repos share data, not code
(D-01).

## 2026-07-05 — aggregates-contract design session (D-19 gate, with Claude Code)

**D-24 · Working privacy floor lowered to N = 3.** (Amends D-09's working value; the rule
and its local application point are unchanged.) Project-owner call during the
aggregates-contract brainstorm: at the current cohort scale (~182 users in the Bergmann
window), N = 5 suppresses a large share of fine-grained cells — the hour×weekday heatmap
especially. k = 3 is the recognized lower bound in statistical-disclosure-control practice
(k = 5 the conservative default). The published file declares `privacy_floor_n` in its
metadata, so no reader hardcodes the value: if the ethics confirmation (go-live gate,
`open-questions.md`, unchanged) later forces 5, that is a pipeline config change plus
republish, not a schema change. Slightly widens the accepted repeated-releases residual
risk (`ethics/data-handling.md`), same reasoning applies.

Sequencing note (recorded in the Phase A plan): local real-data ingest and validation are
pulled forward — the go-live gates bind the first cloud publish, not local development.
The public demo switches from synthetic to real aggregates as soon as the three gates
(pepper custody, floor confirmation, architecture nod) close; synthetic fixtures remain
the permanent basis for tests/CI, and every published file self-labels via a
`data_provenance` metadata field. Gate ownership clarified in the same session: all three
go-live gates (pepper custody, floor N, architecture sign-off) are project-owner decisions
checked against the governing documents and recorded with a date; Daniel is the erasure
contact per the consent addendum, not the gate decision-maker.

**D-25 · Aggregates contract v1 locked.** (Closes the D-19 contract gate; honors the
2026-07-02/03 pinned inputs.) Full spec: `docs/aggregates-contract.md`. Key choices:
explicit tagged cells (`ok`/`suppressed` discriminated union; suppressed cells carry no
value field — sub-floor numbers structurally cannot leak); the floor always tests distinct
contributing students, never value magnitude; complete ISO weeks only; the client never
re-aggregates — every displayed (metric × window) is its own pre-aggregated floored cell,
so the viewable windows are part of the contract (one registry: semesters by the
Thursday-membership rule, `all_time`, `trailing_4`); footnotes as a referenced registry;
`label_versions` as a domain→version map (pluralizes the pinned `label_version`; D-07's
one-active-version-per-domain made structural); metadata additions `timezone` and
`data_provenance`; blob protocol = immutable versioned blobs + atomically overwritten
full-copy `latest.json` under a major-version prefix (`v1/`); additive-only evolution
within a major. Phase B extends the same file (new `topics` section +
`label_versions.classification`).

## 2026-07-05 — Part 2 thin-slice planning session (with Claude Code)

**D-26 · Deployment shape: one Container App; the API serves the dashboard.** The Next.js
static-export bundle (D-23) is baked into the FastAPI Docker image and served by the same
process (`/api/v1/*` + static files). Grounds: same origin (no CORS), a single deploy
path, and the API remains the sole future auth boundary (D-18) covering data and UI
together when D-12 revisits auth. Accepted cost: dashboard-only changes rebuild the image
(script-driven, minutes). Azure setup: new dedicated resource group in **Sweden Central**
(EU residency; matches the operator's existing infra region), ACR + Container Apps
environment + one storage account (private `aggregates` container) provisioned via Bicep
and az-CLI scripts following health-research-agent-api's deployment-plan pattern. CI/CD
(GitHub Actions) deliberately deferred until the deployment shape is stable.

**D-27 · Chart library = Recharts behind a thin wrapper.** Chosen over ECharts at the
implementation point the Phase A plan reserved. Grounds: everything certain in the Phase A
metric set is trend lines + histogram bars at trivial data sizes; the contract's
suppressed-cell rendering (distinct marker, "< N students", never drawn as 0) is a custom
React component, which declarative Recharts makes natural; a native heatmap type is no
longer a requirement because the hour×weekday heatmap's educator value is an open scoping
question (`open-questions.md`) and, if built, a 7×24 CSS-grid component beats a chart-lib
heatmap for bespoke suppressed-cell styling anyway. The thin wrapper keeps the library
swappable.

Phase B re-scoped in the same session: the Leonardo handover is no longer a gate —
building the classification pipeline is on us (see the reframed section in
`open-questions.md`); Part 2 implementation is followed by Phase B planning, not blocked
on external input.

**D-28 · Reference patterns audited, not cloned (amends D-26's machinery; D-23/D-27
stand).** Owner directive: health-research-agent-api and agent-ui anchor *what works*,
not *what we copy*. API hosting: Azure **Container Apps survives the audit** (scale-to-
zero fits a weekly-updated, low-traffic dashboard; compute sits inside the free grant;
cold starts are seconds) against App Service B1 (always warm but ~€13/mo) and F1 (free
but Python apps unload on idle and cold-start slowly — bad first impression on an
educator's demo link). The reference *machinery* is dropped: no Bicep (three resources;
az-CLI scripts are the reproducible record), no hand-managed ACR pushes or local Docker
builds (`az containerapp up --source` builds the image in the cloud), no GitHub Actions
(already deferred). Storage auth: **managed identity + RBAC** cloud-side (no secret in
the deployed app); connection strings exist only for local Azurite and ad-hoc in the
operator's publish script via `az`. Running cost ≈ ACR Basic ~€5/mo + storage cents.
Dashboard: scaffold on **latest stable create-next-app defaults** (App Router, React 19,
Tailwind v4, TS) rather than agent-ui's module list; no Radix/shadcn preinstalled —
primitives added on demand. The exact chart catalog is deliberately deferred until the
E2E slice is live (owner call, `open-questions.md`); thin-slice visuals are provisional
plumbing that must only prove the ok/zero/suppressed rendering distinction.

**D-29 · Interim thin-slice hosting = App Service Linux F1 (zip deploy); Container Apps
deferred until the provider is registered.** D-26/D-28's Container Apps deploy turned out
to require a one-time, subscription-scope provider registration (`Microsoft.App/register/
action`) that the operator's RG-scoped Contributor role on MOPS cannot perform — confirmed
via both CLI and portal (the portal renders the create wizard but ARM denies at submit).
Registration was requested from the subscription admin (2026-07-06, expected ~a day).
Rather than wait or pay for B1 (~€13/mo), the thin slice ships on the free tier: the same
tree the Dockerfile builds (`app/` + `schema/` + `static/` + generated `requirements.txt`)
is zip-deployed with Oryx building server-side; the blob connection string lives in an app
setting (encrypted at rest — managed-identity RBAC also needs rights the operator lacks).
This *reverses D-28's on-merits rejection of F1 under changed constraints*, accepting its
weaknesses knowingly: idle unload with slow cold starts, and a daily CPU quota that a
single crash-looping deploy can exhaust (both were hit on first deploy; root cause was
wwwroot-absolute paths — Oryx runs the app from a random `/tmp` extraction, so
`SCHEMA_PATH`/`DASHBOARD_DIST` are relative). Acceptable while the URL's audience is the
operator; migrate to Container Apps (script preserved at commit `2fd5f1e`, ~15 min) once
registration lands and before the link is shared with the team. Demo URL:
<https://statsboteval.azurewebsites.net>.

## 2026-07-06 — Phase B planning session (with Claude Code)

**D-30 · Phase B classification pipeline inputs fixed.** Plan:
`docs/plans/2026-07-06-phase-b-classification-pipeline.md`. Owner decisions taken this
session:
- **Scope:** the 13 Bergmann deductive binary categories **plus** methods (21) and software
  (9) theme *assignment* against the frozen public lists. The complex inductive sets
  (non-statistical interaction, capability request, declarative statement) are deferred.
- **Classifier model:** pin **gpt-5-mini** (2025-08-07) on Azure OpenAI **Data Zone
  Standard**, Sweden Central (GDPR EU residency; owner verifies deployability in the
  portal). Escalate a category — or the whole run — to **gpt-5.1** only if validation
  exposes a weak category. Ranking rationale: this is short-text binary/theme
  classification where mini-tier reasoning models already saturate quality, and absolute
  cost is tens of euros at our corpus size, so value dominates; `gpt-chat-latest`
  (unversioned) and `model-router` (nondeterministic) are disqualified for reproducibility;
  gpt-5.2/5.3/5.4-mini and the `-chat` variants are **not** offered in Data Zone Standard in
  Sweden Central (verified via `az cognitiveservices model list`) so they fail the residency
  requirement. Replicating Bergmann's exact classifier is explicitly **not** a goal (owner).
- **Prompt design:** **consolidated multi-label** prompt (all 13 categories in one call per
  batch), departing from Bergmann's one-category-per-prompt. ~13× fewer calls; the
  category→call grouping is config so a fragile category can be split out later without a
  rewrite. Recorded as a validation caveat (a per-category MCC gap now conflates model
  **and** prompt-structure differences from their pipeline).
- **Validation:** run `statsboteval-v1` on the **public** 1,400-message dataset (Zenodo raw
  + OSF `full_dataset.csv`) and compute per-category MCC against `bergmann-v1`, using the
  300 human-consensus rows as ground truth. This needs **no production corpus and no
  go-live gate** — pure public data. Themes are produced but not MCC-scored (Bergmann
  validated themes by expert similarity, not MCC).
- **Contract:** `topics` enters the existing aggregates file **additively** — a new
  categorical-distribution shape (multi-label counts, not the numeric `Histogram`) plus a
  `label_versions.classification` key → **minor bump to schema 1.1.0** under the unchanged
  `v1/` blob prefix (honors contract §8/§10). 1.0.0 documents stay valid; 1.0.0 readers
  ignore `topics`.
- **Sequencing:** Phase B is built **before** Phase A Parts 3–4 (thesis core, fully
  unblocked, de-risks the classifier). Code + validation are developed on synthetic
  fixtures + public data (no gate); running classification over the real corpus and
  publishing real topics is gated with Part 4.
- **Bergmann materials stay local (reaffirms D-16):** prompt texts, frozen theme lists, the
  validation dataset, and the validation report are git-ignored until the team's paper is
  formally recommended/published.

**D-31 · Migrate the thin slice from App Service F1 to Container Apps (supersedes D-29's
interim).** The subscription admin registered `Microsoft.App` in MOPS (confirmed
2026-07-06: `az provider show -n Microsoft.App` → `Registered`), removing D-29's blocker.
Owner directive: migrate to Container Apps and delete the F1 app/plan, restoring the
D-26/D-28 target shape (scale-to-zero within the free grant, seconds-not-unload cold starts,
no crash-loop CPU quota) before the demo link is shared with the team. **Two constraints the
preserved `2fd5f1e` script does not yet reflect, found during migration prep:** (1) resources
live in the shared **`Lehrprojekt`** RG (operator has no RG-create rights — HEAD `config.sh`),
not the `statsboteval-rg` the old script names; (2) D-29 also recorded that the operator
lacks `Microsoft.Authorization/roleAssignments/write`, so the managed-identity + RBAC blob
read in the old script may still fail — if so, Container Apps keeps the **connection-string
secret** app-setting approach (Container App secret) rather than managed identity, pending a
separate grant. Migration execution was **blocked this session by an Azure CLI identity
mismatch** (`az account show` = operator `lakhia92@`, but ARM calls presented a stale token
for `akshay.lakhi@` with no role on the RG); it proceeds once the operator re-authenticates.
Demo URL will change from `*.azurewebsites.net` to `*.<region>.azurecontainerapps.io`.

## 2026-07-07 — Dashboard redesign session (with Claude Code)

**D-32 · Dashboard redesigned: educator-question tab IA, registry-driven window filter,
"academic instrument" design tokens.** (Commit `017c137`; supersedes the thin-slice
single-page layout, D-28's provisional chart included.)
- **Tab per educator question**, ordered by owner priority: **Topics** (Phase B teaser
  panel until `sections.topics` ships) · **Adoption** (`usage_context`) · **Engagement**
  (`sessions` + `tokens` merged — both are depth proxies answering one question; a
  deliberate deviation from the contract's one-section-per-view sketch) · **Timing**
  (`temporal_usage`) · **Language** (`language`). Panels open with the question set as a
  display headline; sections absent from a publish render an explicit "not in this data
  release yet" state (invariant 5), so views light up as the pipeline widens with no
  dashboard change. Tab + window selection sync to URL query params (shareable views).
- **The date filter is a window picker, not a date-range control.** Options are the
  published windows registry verbatim (semesters newest-first, trailing, all-time);
  default = the semester with the latest `coverage.through`, falling back to `all_time`;
  "(in progress)" derives from coverage vs. membership, no client date math. Free ranges
  are excluded by contract invariant 4: `per_window` metrics are key lookups, weekly
  series are sliced client-side to window coverage (display selection, never
  re-aggregation). Placed above the tab row, right-aligned — visibly scoping every tab.
- **Design tokens** (light-only v1): STIX Two Text for display headlines only (numbers
  and chart text stay in IBM Plex Sans; Plex Mono for identifiers); Vienna blue
  `#0063a6` as UI accent and data slot 1, `#1baf7a`/`#eda100` as the further language
  series (categorical palette validated for CVD/contrast; the sub-3:1 slots are relieved
  by legend + the always-visible language totals table). A unified **suppression
  grammar**: gray baseline marks (trends, histograms), 45° gray stipple (heatmap), "—"
  (tiles) — suppressed ≠ zero ≠ absent everywhere. Registry footnotes render as
  APA-style †/‡ table notes on each card; every chart carries a collapsible data-table
  twin (accessibility + citability).
- **Dev fixture**: `dashboard/dev-fixtures/` holds a seeded generator emitting a
  schema-validated synthetic document (all Phase A sections, four windows, all three
  cell states); `NEXT_PUBLIC_DATA_SOURCE=fixture pnpm dev` serves it with no API running
  (the branch is tree-shaken out of production builds). Suppression in the fixture is
  driven by distinct-student counts, mirroring the pipeline's floor semantics.

## 2026-07-07 — Phase B re-scope to real data (with Claude Code)

**D-33 · Phase B runs on real data end-to-end; emergent-theme generation enters scope
(amends D-30; plan re-scoped in place).** Owner decisions taken this session:
- **Inductive scope widened.** D-30 had deferred all inductive work beyond frozen-list
  assignment; the redesigned Topics tab (D-32) promises "emergent themes — the struggles
  and question patterns no codebook anticipated", and the owner directed that Phase B
  deliver that, not a frozen-list stand-in. Phase B therefore adds our own **two-stage
  inductive pass over our corpus** (mirroring Bergmann's generate→synthesize method):
  generate candidate codes per message batch → synthesize into a theme list → **operator
  review** → freeze as versioned theme set **`statsboteval-themes-v1`** → assign the
  corpus against it (multi-label). Corpus-wide, not conditioned on Bergmann's eight
  category sets — for the dashboard the direct question is "what do students ask about",
  and the deductive 13 are kept for structure/comparability anyway. Frozen method (21)
  and software (9) assignment is **retained** (cheap, Bergmann-comparable).
- **Data-derivation rule for generated themes:** the synthesized theme list is *derived
  from real chat text*. It stays git-ignored local like the Bergmann materials; theme
  labels enter a published aggregate **only after operator review** confirms they are
  short, generic, and non-identifying (generation prompts instruct this; the review is a
  named runbook step, not a code path).
- **Extract pulled forward from Phase A Part 4.** Recon queries (Task 1), the direct-MySQL
  extract with in-flight HMAC pseudonymization (Task 2), and the Bergmann-descriptives ETL
  correctness check (Task 3) open the re-scoped plan. Production DB confirmed reachable
  from the owner's machine over Uni Wien VPN; connection params received 2026-07-07
  (git-ignored `pipeline/.env`; password never enters chat or repo).
- **Erasure runbook joins Phase B** as a precondition of the first real publish (once real
  aggregates are public, an erasure request must be executable end-to-end). The
  `run-weekly` cadence wrapper stays with Phase A Parts 3–4 (operational convenience, not
  a publish precondition).
- **Dashboard task retargeted at the D-32 tab IA:** the Topics work replaces the
  `TopicsTab` teaser via a new categorical-distribution cell primitive obeying the
  established cell-state and footnote grammar; `dev-fixtures` gains a synthetic `topics`
  section so FE work needs no pipeline run.
- **Azure OpenAI provisioning is an in-plan task** (Sweden Central, Data Zone Standard,
  gpt-5-mini deployment in MOPS), closing D-30's "confirm deployability" item.
- **Phase B now ends with the first real-data publish** — Phase A sections included, the
  synthetic banner retired — under the gates closed by D-34.

**D-34 · Go-live gates closed (pepper custody · privacy floor N=3 · architecture
sign-off).** All three were owner decisions (ownership clarified 2026-07-05); recorded
here as taken 2026-07-07:
- **Pepper custody:** generate once, 256-bit (`python -c "import secrets;
  print(secrets.token_hex(32))"`). Primary copy: `PSEUDONYM_PEPPER` in the git-ignored
  `pipeline/.env` on the encrypted local volume. Backup: one copy in the owner's password
  manager — same custody class as the corpus medium's password. Interlock: the corpus
  stores a SHA-256 fingerprint of the pepper at first ingest and every extract run checks
  it, so a wrong/rotated pepper fails loudly instead of silently forking pseudonyms.
  Rotation = regenerate + full re-ingest (source DB remains available until mid-2027,
  D-20); the pepper is destroyed with the corpus per the data-lifecycle deadlines
  (`docs/ethics/data-handling.md`). Losing the pepper would break erasure (pseudonyms
  become unrecomputable) — hence the mandatory backup copy.
- **Privacy floor N = 3 confirmed** (promotes D-24's working value to the decision). The
  consent addendum and ethics protocol state no explicit minimum cell size; k = 3 is the
  smallest floor at which no published cell can single out an individual and the
  two-student mutual-inference case (each knows the other's contribution) is excluded.
  N = 5 would suppress substantially more at semester-week granularity (bachelor cohort:
  63 students, sparse early weeks) for no articulable requirement. Residual differencing
  risk across windows is structurally limited by the fixed windows registry (contract
  invariant 4 — no free date ranges); accepted and noted.
- **Architecture sign-off recorded:** the owner approves the consented architecture for
  real data — local pseudonymized DuckDB corpus on an encrypted volume; transient
  classification of chat text via Azure OpenAI EU Data Zone Standard (consented practice,
  never persisted cloud-side); only privacy-floored aggregates published to Azure Blob
  behind the publish guard. Gates close at the decision level; the first real publish
  additionally requires the plan's operational preconditions (recon done, descriptives
  check passed, erasure runbook in place).

## 2026-07-09 — program-level label recon (with Claude Code)

**Finding (no decision) · Bergmann `Status` (bachelor/master) is recoverable for the study
window via a verified `history.id` join; origin + full-cohort coverage remain open.**
Prompted by needing per-student program level for StatsBotEval. Confirmed the label is *not*
in the production DB, *not* in the MethodsHub Moodle participant view, and *not* inferable
from `Matrikelnummer` (leading digits = enrollment year). Then established that the public
OSF Stage-2 `full_dataset.csv` carries per-message `Status` (`Bachelorstudent`/
`Masterstudent`/`Other`) keyed on `ID`, and **verified the join end-to-end against the live
DB** (read-only, over VPN): 1,400/1,400 `ID`s resolve to `history` rows, `started` matches
1,400/1,400 exactly, and `history.id → student_id` reproduces 63 BA / 105 MA / 14 Other =
182 students / 584+776+40 = 1,400 messages with zero per-student Status conflicts. So for
the 2025-03-15→06-30 study window the label needs no coordinator handover. Durable details
recorded in `bergmann-framework.md` (join-keys section) and `source-data-dictionary.md`;
the residual open item (origin/derivation of `Status`, coverage for the full ~443-student
cohort, consent-compatibility beyond the published window) is tracked in `open-questions.md`
and was put to Leonardo/Daniel by email 2026-07-09. No decision changed; the OSF dataset
stays git-ignored local (D-16/D-30) — it contains chat text.

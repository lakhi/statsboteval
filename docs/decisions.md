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

## 2026-07-17 — extract validated; go-live re-sequenced (with Claude Code)

**D-35 · Extract validated against the public Bergmann dataset; formal Task 3 module
skipped as satisfied.** The Phase B plan gated the first real publish on a
Bergmann-descriptives ETL check (Task 3). Its substance was delivered 2026-07-17,
stronger than specified: joining the public OSF Stage-2 `full_dataset.csv` (`ID` →
`messages.history_id`), **all 1,400/1,400 rows match the corpus** on `prompt_tokens`,
`completion_tokens`, and `started`, and every published reference statistic reproduces
exactly — token medians (BA 113.5, MA 611.5), messages-per-chat (1.8/1.4, 2.5/2.1),
users by Status (63/105/14). The exact operationalizations (their token metric =
`prompt_tokens` median; the user-typology rules, incl. R-code quirks) were pinned from
the published R scripts and recorded in `bergmann-framework.md` ("Exact
operationalizations"), with the dataset cached git-ignored at
`pipeline/data/reference/full_dataset.csv`. Decision: the "descriptives check passed"
precondition is **satisfied**; the tested `check-descriptives` module is not built now
(it was a one-time ETL check, per Phase A Part 3's own wording) and can be formalized
later if a future re-extract raises doubt.

**D-36 · Re-sequenced to "go-live first, Topics later"** (amends D-33's sequencing; new
plan `docs/plans/2026-07-17-go-live-first.md`). Rationale: the owner's near-term
objective is the deployed dashboard on real data; the five Phase A tabs need **no
classification** (Language was always designed as local `lang-heuristic-v1`, lingua-py),
and the Topics tab renders its designed "not in this release yet" state (contract
invariant 5), so publishing without `topics` is a planned condition, not a compromise.
The blocker was never Task 3 or labels but the unbuilt Phase A Part 3 aggregation (thin
slice covers one of five sections, all-time window only). The new plan = windows
registry + full Phase A sections + labels table (Phase B Task 4, shared infra) +
language heuristic + `run-weekly` + erasure runbook (Phase B Task 17, publish
precondition) + gated first real publish. Phase B Tasks 5–16/18–19 (classification,
themes, topics, Azure OpenAI) resume unchanged after go-live.

**D-37 — First real-data publish (go-live).** The dashboard serves production data as
of 2026-07-17: blob `v1/aggregates_2026-W28_20260717T195040Z.json` (+ `latest.json`),
built from the corpus extracted through 2026-07-14, published axis 2025-W09 →
2026-W28 (72 complete weeks; `axis_start = 2025-03-01` clips the Jul 2024–Feb 2025
pilot traffic, which stays corpus-only), floor N=3, `data_provenance: "production"`
(the synthetic banner retires itself). Go-live preconditions all held: gates closed
(D-34), extract validated (D-35), erasure runbook + CLI in place (GL6), publish guard
green. Operator review of the document produced one change before upload: the
session-duration histogram publishes robust stats only (median/IQR, no mean/sd) —
resumed chats span days under the (student, `started`) session key and made the mean
meaningless (441 min, sd 6,404). The GL7 verification also caught that the deployed
bundle was still the pre-D-32 thin-slice dashboard; redeployed with the five-tab
bundle the same day. Headline first real numbers: 379 active students all-time,
3,521 messages, 1,521 sessions; languages 1,840 de / 1,446 en / 235 undetermined;
user classes 176 one-time / 17 monthly / 186 sporadic.

## 2026-07-18 — Phase B resumption session (with Claude Code)

**D-38 · Phase B resumes in two stages; classification joins the weekly cadence.**
(Amends the finish line of D-33 — the first real-data publish it named is already live
per D-37; the Phase B plan is updated in place, owner call, rather than re-issued.)
Owner decisions taken this session:
- **Staged topics publish.** Stage 1 = deductive (13 categories) + frozen method/software
  themes, validated on the public dataset (Task 19), aggregated and published with
  `emergent_themes` omitted — a state the 1.1.0 schema and Topics tab already design as
  valid and rendered (invariant 5). Stage 2 = the emergent-theme pass (generate →
  operator review → freeze `statsboteval-themes-v1` → assign) and a republish. Grounds:
  the generate→review→freeze loop is the slowest, operator-bound piece; the dashboard's
  first tab shouldn't wait on it.
- **`run-weekly` chains `classify`** (and `assign-themes` once a reviewed theme set
  exists) with a `--skip-classify` escape hatch mirroring `--skip-extract`. Grounds: the
  classification runner is idempotent by `(history_id, label_version)`, the weekly
  increment costs cents, and without this weekly publishes would serve stale topics next
  to fresh Phase A sections.
- Also recorded in the plan's "Resumption deltas": classification runs corpus-wide under
  `axis_start` (published windows clip at aggregation — no design change); theme-set
  regeneration (v2) is a per-semester operator-review question out of Phase B scope;
  Task 18 re-verifies the Data Zone Standard Sweden Central model catalog at
  provisioning time (D-30's check ages).

**D-39 · Program-level status enters the corpus (consent confirmed; usage-time
modality).** (Closes the open-questions "bachelor/master mapping — residual" item;
adds Phase B Task 21.)
- **Consent:** Leonardo confirmed in writing (2026-07-18) that the program-level
  linkage is in line with the ethics approval — Daniel performed the same linkage last
  year to produce the anonymous dataset behind the published paper. Program-level
  segmentation is unblocked for this project.
- **Source & coverage:** the owner's roster-list derivation (parallel session; 8
  program Excels outside the repo, u:account uid ↔ `students.uid` join) labels
  **550/550 corpus users with zero unknowns**: 298 MA / 170 BA / 36 BA→MA
  transitioners / 46 staff (36 no-list + 10 Doktorat). Validated against Bergmann's
  OSF `Status`: 180/182 agree; the 12 disagreements are transitioners, correct under
  usage-time semantics.
- **Modality: compact per-student row, resolved at usage time** — `student_status
  (pseudonym PK, status, ma_start_semester NULLABLE, provenance)`, with
  `status_at(session)` resolving transitioners by comparing the session's `started` to
  the Master Beginnsemester's calendar start (S → Mar 1, W → Oct 1; owner rule
  2026-07-17, session-level so a session never straddles statuses). Chosen over a
  per-(student, semester) row table because the source facts are exactly "one static
  label + at most one transition boundary" — semester expansion would store derived
  redundancy and invent rows for semesters without enrollment evidence. Staff
  sub-levels (PhD vs no-list-match) collapse to `staff` (owner: focus is students);
  `provenance` keeps the distinction locally.
- **Handoff & hygiene:** the roster session delivers a git-ignored **uid-keyed** CSV
  (`uid,status,ma_start_semester,source`); `import-status` pseudonymizes in flight
  (extract.py discipline — identifiers never persisted); `erase-student` covers the
  new table; the roster snapshot is refreshed + re-imported each semester.
- **Per-status split ships in Stage 1 (owner, same day):** `by_status`
  (bachelor/master/staff, `unknown` only when non-empty) enters the 1.1.0 schema in
  Task 13, aggregation in Task 14 (session-level `status_at` resolution; every cell
  floored independently), and the Topics tab as a segmented control in Task 15;
  Task 21 + a real `import-status` run precede Task 20a. Follow-ups (owner accepted
  the recommendations): the roster CSV is **produced in the roster-derivation
  session** (validated list semantics live there; this repo only imports — no
  re-derivation from summaries) and stays **uid-keyed** (single-hasher invariant —
  only extract/import ever map uid→pseudonym; survives pepper rotation, unlike a
  pre-hashed file; spot-checkable against the rosters).
- **Ethics check & custody (owner request, same session):** verified against the
  primary documents — EK 01548 approval (2026-05-05, "no ethical objection … as
  proposed") and the consent addendum's linkage clause. The uid-keyed CSV preserves
  the approval: the pseudonymization promise attaches to *chat histories* (the corpus
  keeps it); program level is enrollment-type data, the approved linkage category; an
  identified intermediate is inherent to any linkage and matches the study leader's
  own confirmed practice; the keying choice is internal data-handling, not a content
  amendment requiring re-submission. **Custody: the CSV lives outside the repo tree**,
  beside the roster Excels (one identifier custody point; the repo tree stays
  identifier-free tree-wide; importer reads `STUDENT_STATUS_CSV` from
  `pipeline/.env`). Lifecycle: deleted with the corpus end-2027; **erasure also
  removes the student's CSV row** (else re-import restores it). Full rules:
  `docs/ethics/data-handling.md` §program-level.

## D-40 — 2026-07-19: Classifier runs on the existing DZS gpt-5-mini deployment (gpt-5.4-mini rejected on data-zone grounds)

- **Context:** for the first real-data classification run (Task 20a), the owner
  deployed `gs-statsboteval-5.4-mini` (gpt-5.4-mini `2026-03-17`) on the shared
  `statistics-tutor` Azure OpenAI resource (MOPS / Lehrprojekt RG, Sweden Central)
  and pointed the pipeline at it.
- **Finding:** that deployment is **GlobalStandard** — inference may route to any
  Azure region worldwide. Consented practice (consent addendum; D-30/D-34) allows
  sending chat text only to **EU data centers**, i.e. Data Zone Standard (or an
  EU-regional Standard) deployment. Checked via `az cognitiveservices model list`:
  `gpt-5.4-mini` offers **no DataZoneStandard SKU in any EU region** (Sweden
  Central, West Europe, France Central, Germany West Central all list only
  GlobalStandard / provisioned tiers). There is no consent-compliant pay-as-you-go
  path for gpt-5.4-mini today.
- **Decision:** classification uses a **DataZoneStandard gpt-5-mini `2025-08-07`**
  deployment — exactly the model+version D-30 pinned (`classifier_model_tag =
  gpt-5-mini@2025-08-07`, label version `statsboteval-v1`). The gs- deployment
  stays untouched (owner may delete it or keep it for non-chat-text use); only
  synthetic connectivity probes were ever sent through it.
- **Amendment (same day, owner):** the run started on the resource's existing
  `statsbot_gpt-5-mini` deployment; the owner then created the dedicated
  **`statsboteval-5-mini`** deployment (same model+version+SKU) so the eval never
  competes with the production app's quota, and the pipeline switched mid-run.
  Identical model+version ⇒ the label version and provenance tag are unaffected.
- **Revisit:** if Azure later ships a DZS SKU for gpt-5.4-mini (or the Task 19
  validation argues for a stronger model), re-run under a **new** label version —
  never mix models within one (see `docs/runbooks/classification.md`).

## D-41 — 2026-07-19: Task-19 model decision — gpt-5-mini at reasoning effort "low", consolidated prompt

- **Validation (minimal effort, consolidated prompt):** average MCC **.57** on the
  300 human-consensus messages — well under the Bergmann GPT-5 reference (.79),
  with heavy under-detection on Specific Method (.26), Reference to Prior
  Content (.38), Instruction Given (.44), Question Posed (.47).
- **Attribution trial** (read-only, consensus subset only): effort "low" with the
  consolidated prompt lifted the average to **.72**; Bergmann-shaped
  per-category prompts at minimal effort did **not** help (average .57,
  Instruction Given collapsing to .18 on 183 false positives). The gap was
  effort, not prompt shape.
- **Decision:** production classification runs gpt-5-mini `2025-08-07` at
  **reasoning effort "low"** with the consolidated multi-label prompt
  (`CLASSIFIER_REASONING_EFFORT`, default "low"); format-deviation retries
  climb low→medium→high. The earlier minimal-effort `statsboteval-v1` labels
  were **deleted and the corpus fully re-classified** under the new setting —
  one label version never mixes inference settings.
- **Recorded caveats:** residual gap vs the reference (.72 vs .79) reflects the
  smaller model plus the consolidated prompt; weakest categories are Reference
  to Prior Content (.21 — isolated-message coding is inherently hard for it),
  Specific Method (.53), Declarative Statement (.60 — its codebook block is the
  interim Table-1 reconstruction, flagged for Leonardo). **Note (2026-07-27):
  these three per-category figures are from the attribution trial, not from the
  shipped classifier.** The full re-classification's final report
  (`pipeline/data/validation-report-2026-07-19.txt`, average .71 per D-42) scores
  them .344 / .567 / .574 — this list understates the shipped labels. Escalation options if
  these matter downstream: bigger model (gpt-5.1-mini+ if a DZS SKU exists) as
  `statsboteval-v2`, or per-category calls at low effort for fragile categories.

## D-42 — 2026-07-19: First topics publish (Phase B Stage 1 live)

- Published `v1/aggregates_2026-W28_20260719T110150Z.json` (+ `latest.json`), schema
  **1.1.0**, provenance `production`, data through 2026-W28 (extract skipped — VPN
  down; 14-Jul corpus, same call as D-37). Corpus snapshot: 550 students / 4,419
  messages; 3,521 messages inside the published axis.
- Topics content: 13 deductive categories + 21 frozen method themes + 9 software
  themes across all five windows; `emergent_themes` intentionally absent until
  Stage 2 (D-38); `by_status` = bachelor/master/staff (550/550 roster match, no
  `unknown`), 131 sub-floor cells suppressed at N=3.
- Classifier: `statsboteval-v1` = gpt-5-mini `2025-08-07`, DZS deployment
  `statsboteval-5-mini`, reasoning effort "low" (D-41); final validation average
  MCC **.71** on the 300 human-consensus messages (report: git-ignored
  `pipeline/data/validation-report-2026-07-19.txt`).
- Dashboard bundle redeployed (Topics tab live) at
  <https://statsboteval.azurewebsites.net>.

## D-43 — 2026-07-19: Emergent themes published (Phase B Stage 2 complete)

- Ran the two-stage inductive pass over the full corpus (4,419 messages): stage 1
  produced 7,459 candidate codes (5,347 distinct; 29 messages uncodable), stage 2
  synthesized a 15-theme draft — **operator-reviewed and approved unchanged**
  (D-33 privacy control; no identifying content found) and frozen as
  **`statsboteval-themes-v1`** (`reviewed_at` stamped, set immutable).
- Assignment wrote explicit 0/1 `emergent_theme` rows for all 4,419 messages
  under `statsboteval-v1`, provenance `gpt-5-mini@2025-08-07#statsboteval-themes-v1`
  (same model + settings as D-41 — one label version, one configuration).
  Most-assigned: regression modeling (695), test selection (689), model
  specification (630); least: multiple comparisons (99).
- Republished `v1/aggregates_2026-W28_20260719T131356Z.json` (+ `latest.json`):
  `emergent_themes` now renders on the Topics tab with `theme_set_version`
  stamped; 250 emergent cells published, 50 suppressed at N=3. No dashboard
  redeploy needed — the card shipped in Task 15 and lit up on data alone.
- Novel signals vs Bergmann's frozen lists: "Study design and analysis planning"
  and "Reporting, writing, and presentation" — help-seeking beyond method/tool
  mentions. A future regeneration (new data or prompt change) mints
  `statsboteval-themes-v2` with its own review; published sets are immutable.

## D-44 — 2026-07-19: Topics tab presentation revision; schema 1.2.0 adds emergent-theme descriptions

- **Owner-directed Topics tab redesign** (same day as D-42/D-43 go-live): emergent
  themes promoted to the top-left card and the deductive card renamed
  **"Bergmann-style Deductive Categories (for validation)"**, moved last — the tab
  now leads with the data-driven answer to its question. Rows show the full
  label on its own line over a full-width bar carrying the share of the view's
  messages (multi-label, so shares don't sum to 100%); each card caps at 7 rows
  ("+ N more" points at the data table, which gains a Share column); the emergent
  card's Note explains the generate→synthesize→operator-review→freeze method
  (D-33/D-43); the per-card †/‡ registry footnotes de-duplicate into one
  tab-level "Notes (all cards)" block; every row gets a hover/focus tooltip
  stating how the number was arrived at (count, window/status slice, classifier
  version, theme set, multi-label caveat, or the privacy-floor explanation for
  suppressed cells).
- **Schema 1.2.0 (additive minor bump, contract §8/§10):** optional
  `TopicItem.description`, published only for `emergent_themes` items and sourced
  from the frozen `theme_sets` table, so tooltips can show each theme's reviewed
  one-line definition. 1.1.0 documents stay valid; until the next publish the
  live document simply renders tooltips without definitions.
- **Deductive definitions are deliberately NOT published** although the owner
  asked for definitions in tooltips: the codebook definition texts are
  unpublished Bergmann research material (D-16 — names public, definitions
  local-only until their paper is formally recommended). The deductive tooltip
  cites the codebook as source instead; revisit when D-16's condition lifts.
  Method/software theme names are treated as self-describing.
- Rollout: FE redeploy (D-26 image rebuild) + re-aggregate/republish from the
  existing corpus; before that publish, the operator glances over the 15 emergent
  descriptions as now-public text (same D-33 review discipline as the labels).

## D-45 — 2026-07-28: Classifier configuration re-tuned; `statsboteval-v2` at batch_size 5

- **Problem.** `statsboteval-v1` scores average MCC **.71** on the 300 Bergmann
  human-consensus messages (D-42), below the Bergmann GPT-5 reference (.79). A 20-arm
  grid (2 models x batch_size {50,25,10,5} x reasoning_effort {low,medium}, plus
  replicates and a codebook A/B) located the cause: **`batch_size = 50` was inherited,
  never validated for our prompt.** Bergmann fixed 50 under a one-category-per-prompt
  design where a 50-message call asked for 50 decisions; D-30's consolidated prompt made
  each call ask for **650** while keeping the batch size. Evidence:
  `pipeline/data/classifier-grid-2026-07-28.txt` (git-ignored per D-16).
- **Method.** Every arm classified all 300 messages through the production
  `build_deductive_prompt` / `parse_deductive` / `_complete_parsed` path. The *scoring*
  was split (seed 2026) into tune-150 / holdout-150 — selection read the tune half only
  and the holdout was unsealed once, after the configuration was fixed. Splitting scoring
  rather than messages preserves n=300 per-category resolution. This also repairs the
  methodological gap in D-41, whose effort choice was selected on the same 300 messages it
  reported. Harness validated: the incumbent arm reproduces the shipped .71 (scores .717).
- **Finding 1 — batch size and reasoning effort are one resource.** Re-expressed as
  reasoning tokens per message, the grid collapses onto a single curve: b10/low
  (135 tok/msg → .795) and b50/medium (145 → .787) share no settings, only a budget.
  The interaction is sub-additive (independent effects would predict .873; observed .824).
- **Finding 2 — the curve saturates near 210 tok/msg and then decays.** Past saturation
  more reasoning makes both models *worse* (5-mini .824→.813, 5.4-mini .783→.772).
  On fixed-codebook annotation, over-reasoning is an active harm: the model deliberates
  into defensible-but-wrong labels where a literal codebook reading would have scored.
  This is why the answer is a *budget*, not "the most capable model".
- **Finding 3 — grouping noise is configuration-dependent.** b25/medium moved **.030**
  between two orderings of the same 300 messages; b5/medium moved .005. "Batch 25 is
  stable" (measured .005 at *low* effort on 2026-07-27) does **not** hold at medium. Every
  contender was therefore replicated; Stage 1's apparent winner did not survive its own
  replicate and was dropped.
- **Finding 4 — the codebook correction is a null.** The Declarative Statement block in
  v1 is our paraphrase (only its `Full` line is Bergmann's). Bergmann's actual text was
  located in the Stage-1 OSF folder, `/Human Rating/Coding Instruction/Coding
  Instruction.ods` — never missing, only unlooked-for; the README's "missing from the
  public prompt file" is true of the *prompt* file only. Predicted to fix
  declarative_statement's 63-FN-vs-8-FP under-detection; measured effect **disagreed in
  sign across two configurations** (-.039 and +.019 on that category). **Adopted on
  provenance grounds only** — Bergmann's text over text we invented — with no performance
  claim. Caveat: it is the *pilot* codebook while our other 12 categories match the
  *production* prompts; the `Full` line is identical across both, suggesting no revision,
  but that is inference (flagged for Leonardo).
- **Finding 5 — batch 5 and batch 10 are statistically indistinguishable at low effort.**
  b10/low replicated at .824 against its original .795 (spread .029); b5/low is .825/.813
  (mean .819, spread .013). The selection-criterion gap is **+.009**, inside both spreads.
  Since no accuracy difference is measurable, the choice falls to operational robustness:
  **`batch_size = 10` adopted** (owner, 2026-07-28) — 442 calls instead of 884 and ~1.6 h
  instead of ~3.1 h for a full corpus pass, halving the exposure of a multi-hour unattended
  run to the transient failures that interrupted this work twice (an overnight laptop-sleep
  stall and two network drops). Batch 5's only edge is a slightly tighter spread
  (.013 vs .029), which does not justify doubling the failure surface.
- **Decision.** `statsboteval-v2` = gpt-5-mini `2025-08-07`, DataZoneStandard deployment
  `statsboteval-5-mini`, reasoning effort **`low`**, seed 20260718 — all unchanged — with
  **`batch_size` reduced from 50 to 10**, and Bergmann's Declarative Statement block. Expected
  average MCC ~**.82–.84** (holdout-150: .841 vs the incumbent's .755). Adoption plan:
  `docs/plans/2026-07-28-statsboteval-v2-adoption.md`. `batch_size` is not currently
  configurable (`step.run_classification` takes the `BATCH_LIMIT` default) — that is task 1.
- **Recorded caveats.** The holdout half proved systematically easier (higher in 16/20
  arms, mean +.024), so its absolute value is optimistic for this split and tune/holdout
  numbers must never be compared across arms. n=2 per replicated configuration — enough to
  reject unstable configurations, not enough for a confidence interval. Wall-clock times
  from arms run overnight are invalid (the laptop cycled into Maintenance Sleep on
  battery). The batch-size finding is validated for the **deductive** pass only; theme
  assignment shares the batching but has no MCC ground truth (D-30), so the change applies
  there unmeasured.
- **Human ceiling, for interpreting all of the above.** Bergmann Stage-2 Table E1 reports
  each human coder's MCC against the 300-message consensus; where both read 1.00 the
  category was single-coded and the figure is tautological. Only five categories were
  genuinely double-coded, mean **.84** — but inflated, since each coder is scored against
  a consensus they helped produce. The un-inflated estimate is Table 1's pilot
  Krippendorff alpha from seven independent coders, mean **.48** on those five. The true
  human-human ceiling lies in **[.48, .84]**. Notably
  `reference_to_a_prior_content` reaches .543 under v2 against an independent-human alpha
  of **.56** — the pipeline's worst category is now at approximately the level at which
  independent human coders agree with each other, and the residual gap to Bergmann's .71
  is substantially the difference between one isolated judgement and two coders who
  discussed it.

## D-46 — 2026-07-28: gpt-5.4-mini rejected on evidence (supersedes D-40's residency grounds)

- **Context.** D-40 rejected gpt-5.4-mini because it offered **no DataZoneStandard SKU in
  any EU region**, making it consent-incompatible, and named the revisit condition: "if
  Azure later ships a DZS SKU for gpt-5.4-mini... re-run under a new label version."
- **The condition is now met.** Verified 2026-07-27 via `az cognitiveservices model list`:
  `gpt-5.4-mini 2026-03-17` lists `DataZoneStandard` in Sweden Central. The operator
  deployed `statsboteval-5.4-mini` (DZS, capacity 1005) on the shared `statistics-tutor`
  resource. **The residency objection is obsolete.**
- **Rejected anyway, on measured performance.** In the D-45 grid gpt-5.4-mini lost **all
  six** matched (batch, effort) comparisons to gpt-5-mini: +.165, +.054, +.058 at low and
  +.004, +.052, +.045 at medium. Its ceiling is ~**.78** against gpt-5-mini's ~**.82**, and
  below the Bergmann GPT-5 reference (.79). It is **not budget-starved** — adding reasoning
  past 230 tok/msg made it *worse* (.783 → .772), the same saturation-and-decay seen in
  gpt-5-mini. It also costs 2.5–3x more per corpus.
- **Methodological note that made the comparison valid.** Reasoning-effort labels are
  **not comparable across models**: at `low`, gpt-5.4-mini spends 4.5 reasoning tokens per
  message where gpt-5-mini spends 39. Comparing the two at equal effort *label* compares
  them at unequal thinking budgets and would have produced a meaningless 17-point gap.
  Capturing `response.usage` per call is what made the comparison interpretable — the
  production `ClassifierClient.complete()` discards it, which is fine for production but
  means any future model comparison must re-instrument.
- **Interpretation.** This is short-text multi-label annotation against a fixed codebook,
  where the winning behaviour is faithful instruction-following, not reasoning. Newer
  reasoning-optimised models are tuned for the opposite. **Do not assume a newer or larger
  model improves this task** — measure it, at matched token spend.
- **Decision.** Classification stays on gpt-5-mini `2025-08-07`. The
  `statsboteval-5.4-mini` deployment may be deleted; only the 300 public Bergmann
  consensus messages were ever sent through it (consented practice, DZS/EU). Revisit only
  if a future model is measured to beat gpt-5-mini at matched reasoning-token spend.

## D-47 — 2026-07-28: Emergent theme set reviewed in depth; `statsboteval-themes-v1` stays frozen unchanged

- **Why revisited.** D-43 records the 15-theme set as "operator-reviewed and approved
  unchanged", but that approval was made under time pressure. Ahead of the v2
  re-classification (D-45) the owner asked for a proper review, since regenerating themes
  is cheapest to do *before* a re-classification (one pass, one republish). Evidence:
  `pipeline/data/theme-regeneration-trial-2026-07-28.md` (git-ignored).
- **Two hypotheses tested and both refuted** (useful negative results):
  - *Stage-1 `batch_size = 10` would produce a less fragmented candidate vocabulary.*
    **No.** On 500 messages, batch 10 vs 50: uniqueness 79.4% vs 87.0%, hapax 86.8% vs
    89.9% — marginally *better*, not worse, and the apparent collapse in cross-call
    vocabulary overlap (0.28 vs 1.20 per call pair) is an artefact of vocabulary size per
    call (1.3% vs 1.5% as a share). The D-45 batch-size finding does **not** transfer to
    candidate generation, whose per-call load is ~85 short codes against the deductive
    pass's 650 binary decisions — it was never in the overloaded regime. The one real
    difference: batch 10 emits 29% more codes per message (2.08 vs 1.61).
  - *The 85%-hapax candidate vocabulary is lexically fragmented and can be consolidated by
    normalising word order and stopwords.* **No.** 5,347 → 5,176 distinct codes (**-3%**).
    The fragmentation is **semantic**, not lexical; consolidating it would need embeddings
    or an LLM canonicalisation pass. Side benefit: because normalisation was nearly a
    no-op, the chunked-synthesis arm's difference is attributable to chunking alone.
- **The current method is reproducible.** Re-synthesising from the raw 5,347 codes produced
  17 themes of which **13 map one-to-one onto the frozen 15** — `statsboteval-themes-v1`
  was not an unlucky draw, which matters for what is already published.
- **Coverage audit.** A targeted gap analysis over all 5,347 candidate codes (16 chunks,
  each proposal required to name the codes it covers, so support is counted rather than
  asserted) yielded 12 candidate additions. **The strongest carries 82 code instances =
  1.10%; all twelve together 6.6% — so the frozen 15 cover ~93% of coded content.**
  Rejections were principled, not arbitrary: *Conversational and logistical messages* (58)
  is interaction style, not topic, and is already measured by the deductive categories
  (`greeting_expression`, `politeness_expression`, `english_input`/`german_input`,
  `capability_request`); *T-distribution and t-test concepts* (36) and *Correlation
  specifics* (32) sit at specific-method granularity where the set is deliberately at
  method-family level; *Post-hoc analyses* (28) is explicitly inside theme 9.
- **The privacy floor is what settles it.** A theme's dashboard value is not its corpus
  share but whether its cells survive `floored_count()` at N=3, and cells are published per
  window x status. A 0.4%-support theme is ~24 messages corpus-wide, ~1.6 per cell across
  5 windows x 3 status groups — suppressed essentially everywhere (D-43 already reports 50
  of 300 emergent cells suppressed). **Under a privacy floor each additional low-support
  theme makes the Topics tab emptier, not richer.** Only the top candidate
  (*Psychometrics and measurement*, 82, ~112 merged with *Dimension reduction*) had any
  prospect of publishing outside `all_time`.
- **Decision: no change.** `statsboteval-themes-v1` remains frozen and published as-is; no
  `statsboteval-themes-v2` is minted. D-43's approval is now backed by a substantive review
  rather than a time-constrained one. Also avoided: a Topics-tab comparability break, and
  mixed theme-set provenance (15 from the D-33 generate→synthesize method plus N from a
  coverage audit) that the thesis would have had to explain.
- **Consequence for D-45.** Candidate regeneration is **not** a prerequisite for the v2
  adoption; the two are independent. v2 re-runs `assign-themes` against the unchanged
  frozen set, exactly as its plan already specifies.
- **Revisit when** new data plausibly shifts the distribution — a new semester's corpus, per
  D-38's per-semester question — or if *Psychometrics and measurement* grows enough to clear
  the floor. The gap analysis is cheap to re-run (~16 calls, minutes) and its script is the
  reusable artefact.

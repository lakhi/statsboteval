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

## D-45 — 2026-07-28: Classifier configuration re-tuned; `statsboteval-v2` at batch_size 10

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
- **SHIPPED 2026-07-28 — outcome on the full corpus.** All 4,419 messages re-classified
  under `statsboteval-v2`; `statsboteval-v1` retained as baseline and rollback path.
  Measured average MCC **.823** (v1: .714, **+.109**), inside the predicted .82–.84 and
  above the Bergmann GPT-5 reference of .79. **No category regressed.** Largest gains:
  `declarative_statement` .574→.801, `greeting_expression` .681→.892,
  `reference_to_a_prior_content` .344→**.551** (vs the .543 the grid predicted and the
  .56 independent-human alpha — at the human ceiling, as anticipated). Report:
  `pipeline/data/validation-report-v2-2026-07-28.txt` (git-ignored).
  **Attribution caveat:** batch size and codebook changed together in v2, so
  `declarative_statement`'s +.227 cannot be split between them from this run. The
  isolated A/B (finding 4) measured the codebook effect as a null disagreeing in sign,
  so the gain is attributed principally to batch size; the codebook remains adopted on
  provenance grounds, with no performance claim, exactly as recorded above.
- **Published 2026-07-28 19:53Z** as `v1/aggregates_2026-W30_20260728T195307Z.json` +
  `v1/latest.json`; the live API serves `label_versions.classification = statsboteval-v2`,
  schema 1.2.0 unchanged, no dashboard redeploy. `statsboteval-v1` retained in the corpus.
- **Topics effect of v2, and the one finding that needs stating.** Compared against a v1
  document regenerated *the same day* (comparing to the 2026-07-19 published doc would
  have confounded the label version with the calendar: `data_through_week` advanced W28 →
  W30, moving the emergent cell count 300 → 270 on its own). Holding the calendar
  constant: theme-set membership identical, **mean rank movement 0.9, 8/15 themes
  unchanged, max movement 5**, and suppressed emergent cells improve **43/270 → 39/270**
  — v2 makes the Topics tab slightly richer, consistent with D-47's floor reasoning.
  v2 assigns **21% more** emergent labels corpus-wide (6,664 → 8,064), with per-theme
  growth clustering +3.8%..+37.7% (median +16.5%) — **except `Hypothesis formulation and
  testing`, which grew +76.5% (328 → 579) and rose from rank 10 to 5**, double the
  next-highest rate.
  **This is unresolvable with the evidence available and is published as a caveat, not as
  a validated improvement.** The batch-size change is measured only against the deductive
  categories, where the 300 human-consensus messages give ground truth; the emergent pass
  has none (Bergmann validated themes by expert similarity, not MCC — D-30), so the change
  was applied there blind by design. A +76.5% shift is equally consistent with v2 correctly
  recognising hypothesis-framing that v1 missed and with batch-size noise in an unvalidated
  pass. Sampling the newly-labelled messages would be the natural check but requires reading
  chat text, which is consented for transient processing on Azure OpenAI EU only. **Revisit
  if** an expert-similarity validation of the theme pass is ever run (it would also close
  D-30's open comparison), or if the next semester's data reproduces the same outlier.
- **Correction to the cost/duration estimate in this decision and its plan.** Both said
  "442 calls, ~1.6 h" for a full corpus pass. That counted the **deductive call only**.
  `classify_corpus` piggybacks the method- and software-theme passes onto every batch
  (`THEME_PASSES`), so 442 batches issue **~1,326 calls**. Measured: ~34 s/batch,
  **~4.2 h** wall clock. The separate emergent `assign-themes` pass is one call per batch
  and runs at ~6 s/batch (~45 min). Budget future re-classifications by batches × 3, and
  read the grid's `$/corpus` column as a deductive-only figure likewise.

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

## D-48 — 2026-07-29: Dashboard header speaks educator vocabulary; the date range follows the window filter

- **Why.** The header line was written in pipeline vocabulary and was **document-scoped**
  (`Data through 2026-07-26 (2026-W30), from week 2025-W09`) while the window picker two
  inches to its right is **window-scoped**. Selecting "Summer semester 2026" therefore drew
  charts ending 28 Jun 26 underneath a line claiming data through 26 Jul 26. ISO week ids
  and RFC-3339 timestamps are pipeline identifiers; the audience for this page is educators.
- **New copy.** Eyebrow `StatsBotEval · University of Vienna` (was `University of Vienna ·
  StatsBot`); `<h1>` `Educator Dashboard`; subtitle `Based on student–GenAI interactions
  data from StatsBot (between 02 Mar 26 – 28 Jun 26)`; footer `generated 28 Jul 2026` (was
  the raw `2026-07-28T19:53:07.135948Z`). Year width differs on purpose: `YY` in the inline
  range, `YYYY` for the standalone footer date.
- **Range dates come from `coverage`, not from `start_date`/`end_date`.** Semester windows
  publish nominal boundaries (Mar 1 – Jun 30 / Oct 1 – Jan 31, `windows.py:40–44`), but
  `all_time` and `trailing_4` publish **no dates at all**, and nominal dates would *lie for
  an in-progress semester* — Winter 2026/27 opened in November would advertise "through
  31 Jan 27", months before that data exists. `coverage` is the one date source every window
  kind has, and `build_windows` has already clipped it to `[first_week, data_through_week]`,
  so a window's end date can never run past the data. It is also the range that matches what
  is actually plotted, since every series is week-bucketed.
- **Week→date math is dashboard-side, and this partly supersedes an aggregates-contract
  stance.** `docs/aggregates-contract.md` justified `data_through_date` as existing "for
  display without ISO-week math in TS". A window-scoped range cannot be served that way
  without new contract fields, a schema bump, a full manual operator run and a republish —
  disproportionate for a copy change, and it would couple two deploys. So `isoWeekMonday`
  now lives in `dashboard/src/lib/format.ts`, in UTC throughout, mirroring `week_monday` in
  `contract.py`. The duplication is pinned by a checkable identity on real data:
  `isoWeekSunday(data_through_week)` must equal `data_through_date`, which the Python side
  already validates. Rejected alternative kept on record: publish `from_date`/`through_date`
  on `Coverage` — the right move if a *second* consumer ever needs window dates.
- **`Intl` cannot express the requested format.** Verified across locales: every English
  locale rendering a 3-letter month reorders it month-first (`Sep 29, 25` — en-US, en-CA,
  en), and every day-first English locale spells September `"Sept"` (`29 Sept 25` — en-GB,
  en-IE, en-AU). Day-first + 3-letter month is not an English CLDR pattern, so the month
  table is hardcoded — which also makes output identical across browsers rather than
  dependent on the viewer's ICU data. `formatGeneratedDate` still uses `Intl`, but only via
  `formatToParts` to read calendar fields in `doc.timezone`.
- **`generated_at` is rendered Vienna-local, not UTC.** The document buckets everything
  Vienna-local and `data_through_date` is a Vienna-local Sunday. Since `run-weekly` is a
  manual operator run (often evening), a UTC render would print the wrong day for anything
  after ~22:00 UTC — checked: `2026-01-31T23:30:00Z` → `01 Feb 2026`.
- **The privacy floor moved rather than being deleted.** The request replaced the subtitle
  *and* the `privacy floor N ≥ 3` chip. N=3 is a consent-driven control (D-24), so it was
  relocated into the footer beside the other provenance metadata, tooltip text unchanged and
  still driven by `doc.privacy_floor_n` — never hardcoded, per the field's own contract note.
- **Scope.** Dashboard-only: `Dashboard.tsx` and `format.ts`. No API, pipeline, contract,
  schema or republish. `data_through_date`, `data_through_week` and `first_week` are no
  longer rendered anywhere; the picker still marks unfinished windows via `isInProgress`.

## D-49 — 2026-07-30: Trends tab — pipeline-selected period comparisons, ranked by usefulness rather than significance

- **What shipped.** A sixth dashboard tab answering *"how is usage changing over time?"*
  with at most five pipeline-selected findings per window, drawn from the measures behind
  all five existing tabs. Schema **1.2.0 → 1.3.0**, additive (the regenerated schema is
  +285 / −0 lines), same `v1/` blob prefix — a 1.2.0 reader ignores the section
  (invariant 5) and an old document under the new dashboard renders `SectionPending`, so
  deployment is safe in both directions.
- **The pipeline selects; the dashboard renders.** Invariant 4 decides most of this, but
  the binding reason is that real hypothesis tests need per-student observations, and
  those exist **only locally** (constraint 1). Floored aggregates cannot be tested. The
  relevance tier that drives the ordering is deliberately not published — publishing it
  would invite the client to re-sort.
- **Ranking is usefulness-first; significance is a gate, not an ordering** (owner,
  2026-07-29). The audience is a statistics educator or a StatsBot evaluator, so the tab
  surfaces what could change a teaching or tooling decision, not what has the smallest
  p-value. Findings sort by a pinned relevance tier with effect size only as the
  tie-break *within* a tier. This reversed the original plan's exclusion of method and
  software themes: *which statistical methods students ask about* is the most actionable
  signal this dashboard carries, and excluding it while ranking `Politeness Expression`
  inverted the stated priority. Topics accordingly gets 3 of the 5 slots.
- **Census framing, settled in-house.** These are all StatsBot users, not a sample, so
  the tests are framed as a guard against over-reading noise rather than inference to a
  population. No external sign-off is sought or required for any StatsBotEval decision.
- **Benjamini–Hochberg over one family per window**, chosen for simplicity: per-tab
  families would hold a topic finding and a language finding to different standards in
  the same list. The two-tier evidence marker (`robust` = BH-adjusted p < .05,
  `indicative` = unadjusted only) is the release valve, so a strict family cannot starve
  the tab — it changes how confidently findings are labelled.
- **Pinning discipline, split deliberately.** Relevance tiers were pinned *before* any
  dry run — they are a judgment about pedagogy, and nothing in the data informs them.
  Magnitude thresholds were pinned from **one** recorded dry run against the real corpus
  (2026-07-30, `preview-trends`), per measure family, not iteratively tuned. Families are
  separate because a shares threshold sized for language (40–60%, where 5 pp is ordinary)
  is unreachable for an individual topic theme (2–8%); a single threshold would have
  gated out exactly the tier-1 measures the ranking promotes.
- **`volume_rate` and `people_rate` are separate families**, found by the first dry run:
  a single `rate` family with `min_n = 30` conflated event counts (thousands per semester)
  with people counts (tens), which permanently gated `active-students-per-week` — a
  measure that never has 30 "observations" by construction.
- **Three empty states, not one.** "No earlier period", "nothing was testable"
  (`insufficient_data`) and "tested and flat" are different claims. Roughly a third of
  the year is break weeks and `trailing_4` sits in them for months, so without the
  distinction the tab would assert all summer that a comparison ran and came back flat.
  The calibration run confirmed this empirically: 62 of 69 `trailing_4` candidates fail
  the privacy floor in the July break. Stability is never published as a positive
  finding — absence of evidence through a noise gate is a weaker statement than it looks.
  A window where no candidate is even *defined* (every measure undefined on a side, e.g.
  a current period with no messages) reports `insufficient_data` too, not "flat" — caught
  in review, unreachable on today's corpus, and pinned by a test so the two paths for
  "nothing was testable" cannot diverge.
- **The floor is satisfied by absence here, not by a marker.** Findings publish derived
  floats and have no suppressed state; sub-floor candidates are dropped before
  publication. Legitimate because a rendered "we found a shift but cannot say what"
  carries no information, unlike a suppressed count whose position and neighbours do. A
  publish-time walk asserts no `n_students` anywhere in the outgoing bytes is below the
  floor, and a property test asserts no generated corpus yields a sub-floor finding side.
  Consequence, accepted: a measure falling to exactly zero publishes nothing.
- **No operator review gates a publish.** Titles are template-generated from pinned
  measure names, so no finding text derives from chat content and D-33's review
  discipline does not apply.
- **The delta is not colored by valence.** Almost nothing here has a good direction — a
  rising German share is neither better nor worse — so direction is carried by an arrow
  and a sign rather than by green/red, which would editorialize a measurement.
- **Known limitation, deferred.** Emergent and method themes are independent taxonomies
  over the same messages, so one real shift can occupy two of the three topics slots (the
  calibration run showed exactly this for assumption-checking in 2026S). Not a
  correctness fault — two taxonomies agreeing is corroboration — but it costs slot
  diversity. A per-label-family sub-cap is the fix if it proves annoying in practice.
- **Also deferred:** Cochran–Armitage trend test for trajectories (endpoint test in v1),
  same-elapsed-weeks clipping for in-progress semesters (per-week rates chosen instead),
  and `by_status` trend splits (suppression-heavy at this corpus size).
- **Incidental fix, recorded because it changed published output:** `seed_synthetic` never
  ran language detection, so every synthetic corpus was 100% `undetermined` and the
  dev-fixture Language tab was empty. It now runs the real local heuristic, as the real
  pipeline does before aggregation.

## D-50 — 2026-07-30: Adoption tab answers "who came back" and "which level"; schema 1.4.0

**Context.** A read-through of the Adoption tab (owner + assistant, 2026-07-30) found the
numbers correct but under-specified for the educator reading them: "Messages 986" does not
say a message is one exchange; "New registrations 119" counts accounts created, of which
32 never sent anything; "Active students" silently includes the 46 roster-labeled staff;
and the tab could not distinguish a returning student from a first-time one. Meanwhile
program level had existed in the corpus since D-39 but was wired into **Topics only** — an
inconsistency across tabs rather than a deliberate boundary.

**Decision.** Publish four additions under **schema 1.4.0** (additive minor; 1.3.0 is live)
and relabel the tab.

- **`usage_context.by_status`** — active students and messages per program level, reusing
  D-39's usage-time resolution. §13's "cohort-wide only" is thereby *partly* reversed for
  Adoption, as §13 itself anticipated ("would arrive as additive dimensions inside
  sections"). Per-course segmentation stays out — `students.lv` does not exist in prod.
- **`new_users` / `returning_users`** — the retention pair, partitioning `active_students`.
- **`new_registrations_active`** — of the window's signups, those who also wrote in it.
  `new_registrations` keeps its name (renaming a published field is a major break) and the
  tab renders the pair as "New signups: N signed up / M sent at least 1 msg".
- **`user_classes.frequent`** — Bergmann's fourth flag, published as a **sub-count of
  monthly**, not a fourth class.

**Why each of those is a pipeline change and not copy.** Invariant 4: `totals` feeds the
KPI tiles and is never client-summed. A dashboard deriving "returning" as
`active − new` would be subtracting two floored cells with no knowledge of how many
students back the difference — the floor tests *distinct contributing students*, so a
derived cell can bypass it. Three of the seven requested items (the message caption, the
class rules in the note, the "Bergmann et al. (2026)" wording) genuinely were copy and are
copy.

**`frequent` is a subset, and finding that out changed the design.** The plan initially had
it as an exclusive fourth class checked before monthly. Fetching the actual OSF script
(`30_Analysis Step 3 - Table K1 & subgroup analysis.R`, verified 2026-07-30) showed the
typology is **five independent indicator flags**, not an ordered if-else:

```r
one_time_user   <- ifelse(all(span_days < 3) & all(timedif <= 24), 1, 0)
frequent_user   <- ifelse(all(diffs < 14) & span_days > 30, 1, 0)
occasional_user <- ifelse(all(diffs < 30) & span_days >= 30, 1, 0)   # the paper's "monthly"
sporadic_user   <- ifelse(all(one_time_user==0) & all(occasional_user==0), 1, 0)
```

`all(diffs < 14) & span > 30` implies `all(diffs < 30) & span >= 30`, so every frequent user
is also an occasional one. Making it exclusive would have quietly redefined our `monthly`
away from their `occasional_user` the first time a frequent user existed. n = 0 in their
data and in all four of our windows, so no published number moves — the failure would have
been invisible until it mattered. `one_time` / `monthly` / `sporadic` do partition and still
sum to `active_students`; `frequent` is rendered dimmed and last, labeled "frequent (of
monthly)".

**The retention baseline reads behind `axis_start`.** `first_seen` is built from every
corpus message, including the 2024/25 pilot months that no chart shows, because a student
who wrote in November 2024 is not a new user in 2025S. Cost: with the alternative
(axis-scoped) baseline, 2025S would read 190 new / 0 returning; with this one it reads
150/38. For `all_time`, "returning" necessarily means "was active before 2025-03-01" — the
55-student pilot cohort — which `retention_definition` states.

**Signup activation is window-scoped on both sides.** "Sent at least 1 msg" counts messages
inside the same window, not ever. The "ever" variant differs by only ~3 students per
semester but would make a *published historical window change value on republish* — an
unwanted property for a thesis artifact.

**The retention pair needs complementary suppression — found in review, not in design.**
`new + returning = active_students` with all three published is the one shape where
per-cell flooring is not enough: rendering the `trailing_4` window showed "Active users 4 /
3 new / — returning", i.e. the withheld cell recoverable by subtraction. Fixed in
`aggregate.py`: if either side is sub-floor, **neither** is published. A measured zero is
`ok(0)` and never triggers it (invariant 2). The dev-fixture generator carries the same rule
so the fixture cannot show a shape the pipeline cannot emit.

**Open, larger than this decision: differencing exposure elsewhere.** The same subtraction
argument applies wherever a published total and its published parts leave exactly one part
suppressed — `topics.by_status` message counts against the all-students group (live since
1.1.0 / D-39), and `usage_context.by_status` messages, which sum to `totals.messages`.
Deliberately **not** changed here: it predates this decision, touches Topics' floor
reasoning (D-24, D-47), and warrants its own review rather than a side effect of an
Adoption relabel. Flagged to the owner 2026-07-30; `open-questions.md` if it is not taken up
promptly.

**Accepted overlap.** Program level resolves per session, so a BA→MA transitioner active on
both sides of their semester boundary is counted under both levels: 6 students all-time,
zero in any semester window. The owner accepted the duplication over a tie-break rule
(2026-07-30); `status_multi` states it, and messages still partition exactly.

**"Active students" → "Active users".** The tile includes the 46 roster-labeled staff
(faculty pre/postdocs — Bergmann's "Other"), which the new program-level table now makes
visible. Renaming was chosen over filtering: they are real users of the tool, and Bergmann
kept them as a third category.

**Consequences.**
- Status resolution moved out of the topics block into `read_corpus_view`, so Adoption's
  split no longer depends on whether Phase B labels exist. Synthetic roster seeding moved
  out of `seed_synthetic_labels` into `seed_synthetic` for the same reason.
- A re-aggregate + republish is required for any of this to appear; the numbers themselves
  did not change, only what is published about them.
- Bergmann replication strengthened incidentally: our 2025S window reproduces their
  63 bachelor students exactly, and 111/12/67 user classes against their published
  12 monthly / 67 sporadic / 56.6 % one-time.
- Still deferred: their `one_time_project_user` flag (subset of sporadic, 77 all-time),
  sessions-per-student and weeks-active distributions, and the registration→first-use lag
  (median 0 days — it would only confirm there is no onboarding friction).

## D-51 — 2026-07-30: `go-live` skill; production publish script; D-50 live on schema 1.4.0

**Publish record.** The D-50 Adoption work went live the same day: blob
`v1/aggregates_2026-W30_20260730T114248Z.json` (+ `latest.json`), schema 1.4.0,
`data_provenance: "production"`, axis 2025-W09 → 2026-W30, floor N=3, labels
`statsboteval-v2` / `lang-heuristic-v1`. Mode: **re-aggregate only**
(`--skip-extract --skip-classify`) — the presentation change moved no numbers, and mixing a
data refresh into it would have meant reviewing two things at once. The corpus extract
watermark therefore stays at 2026-07-14; the next refresh run picks that up. The bundle was
redeployed in the same session, which a schema bump requires: an older bundle ignores new
fields silently, which reads as "my change didn't deploy".

**Two gaps this exposed, both closed.**

1. **There was no production publish script.** `infra/scripts/` had
   `03_publish_synthetic.sh` and nothing for real data, so every real publish since D-37 has
   been an ad-hoc `AZURE_STORAGE_CONNECTION_STRING=$(az …) run-weekly --upload` typed from
   memory. Added `04_publish_production.sh`, same credential posture (D-28: connection
   string fetched ad hoc, never written to disk), plus two guards the ad-hoc form lacked: it
   **refuses a document whose `data_provenance` is not `production`**, and it curls the live
   URL back afterwards.
2. **`run-weekly --upload` cannot publish the document you reviewed.** It re-aggregates, so
   the uploaded bytes are a second, freshly computed document — normally identical, but not
   provably so (a run crossing an ISO-week boundary changes the axis). The script's
   `--from FILE` mode loads a reviewed document, re-runs the publish guard on those exact
   bytes, and uploads them. The D-37 review gate now means what it says.

**The `go-live` skill** (`.claude/skills/go-live/SKILL.md`) is the first skill in this repo.
It encodes the operator knowledge that was previously only in `infra/README.md` and one
person's head: the data/code split and why a schema bump needs both; the F1
`QuotaExceeded` state that no amount of redeploying fixes; the 5-minute API blob cache, so a
stale read is not diagnosed too early; that `NEXT_PUBLIC_DATA_SOURCE=fixture` inlines the
synthetic fixture at *build* time and must never be set for a deploy build; and that the
dashboard's lockfile is pnpm's.

**Extract and classify are opt-in, never implied** (owner, 2026-07-30). The skill must ask
which `run-weekly` mode to use and fall back to `--skip-extract --skip-classify` when the
operator does not choose, stating in the question that the default publishes the corpus as it
stands and pulls in no newer StatsBot activity. Grounds: the two opt-in modes each carry a
precondition the operator may not have met (VPN to the production DB) or a real cost
(per-message Azure OpenAI), so neither may happen by accident — and silence must not read as
"refresh everything", which is discovered only afterwards, from the numbers.

**Incidental fix:** `scripts/e2e_local.sh` advertised
`next dev` + `NEXT_PUBLIC_API_BASE` for eyeballing the page locally. That cannot work in a
browser — the API sets no CORS headers, because same-origin (API serves the built bundle,
D-26) is the only shape it ships in. `curl` against the API works, which is how the stale
recipe survived. Corrected to the build-and-serve recipe, which was verified end to end.

## D-52 — 2026-07-30: Trailing window anchors on the real extraction watermark, not wall-clock `now`

**The bug.** `read_corpus_view`'s axis boundary (`data_through_week`, and therefore
`trailing_4`/`all_time`/current-semester coverage) was derived from `datetime.now()` at
aggregate time, not from when data was actually last extracted. Reported by owner from the
live dashboard: the "Last 4 weeks" filter showed 29 Jun – 26 Jul, but the corpus's last real
message is 2026-07-14. Any aggregate run without a fresh extract immediately beforehand —
today's Adoption-tab iteration, `erase-student` — silently advanced the axis to whatever week
preceded wall-clock `now`, publishing the intervening weeks as `ok(0)` "measured zero" cells
that were never actually measured (invariant 2's reasoning assumes extraction just ran; that
assumption held for `run-weekly` alone).

**First attempt rejected by the test suite, which is exactly what it's for.** Capping
`through` at `min(now-derived week, last message's week)` looked like the fix, but it breaks
the legitimate case invariant 2 exists for: `test_hand_computed_document` extracts a corpus
that really is empty in its trailing week (extraction covered it, found nothing), and that
week must still publish as `ok(0)`. From message rows alone, "extraction covered this week and
found zero" and "extraction never reached this week" are indistinguishable — `now` was the
only signal telling them apart, and only `run-weekly` (extract immediately followed by
aggregate) earns the right to use wall-clock `now` for that.

**The real fix:** persist a `last_extracted_at` watermark in corpus `meta`, written by
`extract_new_rows` even on a quiet run (a quiet run is what proves the week was actually
checked). `read_corpus_view` now anchors the axis on that watermark, falling back to the
passed `now` only when a corpus has never been through a real extract (every synthetic
fixture and test corpus). `generated_at` (the publish instant) is untouched — only the
data-boundary calculation moved. `extract_new_rows` gained an optional `now` parameter so
`run-weekly` can pass one shared timestamp into both the extraction watermark and
`build_aggregates`.

**Renamed** the `trailing_4` window's label from "Last 4 weeks" to "Last Avl. 4 weeks" (owner)
— it tracks the last 4 weeks *for which data is available*, not the last 4 calendar weeks,
and the old label read as a promise the axis didn't keep whenever extraction lagged.

**Publish record.** Republished the corpus unchanged: blob
`v1/aggregates_2026-W30_20260730T135726Z.json` (+ `latest.json`), schema 1.4.0,
`data_provenance: "production"`, axis 2025-W09 → 2026-W30, floor N=3. Mode: **re-aggregate
only** (`--skip-extract --skip-classify`) — this fix moves no numbers today, since the real
corpus has no watermark yet (this run is what will eventually get one) and so still falls
back to `now`. Diffed the reviewed document against the prior publish before uploading:
the only field that changed anywhere in the document was `trailing_4.label`. No code deploy —
the label is entirely data-driven (`WindowPicker.tsx` renders whatever `label` the API
returns), so no dashboard/API bundle needed rebuilding.

Filed as an idea-level follow-up (issue #3): once a real extraction records the first
watermark, revisit whether extraction lag should be surfaced more visibly in the UI, rather
than only silently capping the axis.

## D-53 — 2026-07-30: Engagement tab measures students, not just sessions; schema 1.5.0

**Context.** A read-through of the Engagement tab (owner + assistant, 2026-07-30) found it
answering only half its own question. Every card binned *sessions* — messages per session,
session duration, reply length — so the tab could say how a conversation went but not how
much any student used StatsBot, or whether they ever came back. The three obvious
per-student distributions had already been flagged as deferred in D-50's consequences.
Two smaller problems came up in the same pass: "IQR 1–3" is methods vocabulary on a page
written for educators reading as administrators, and the tab said *session* while its own
footnote and the whole Trends tab said *conversation*.

**Decision.** Publish a new **`per_student`** section under **schema 1.5.0** (additive minor;
1.4.0 is live), withdraw the `tokens` section, and rebuild the tab around five cards.

- **`sessions_per_student` / `weeks_active_per_student` / `messages_per_student`** — the
  same `Histogram` primitive as `sessions`, but one observation per student. Bin edges reuse
  the session ruler (1 · 2–3 · 4–7 · 8+) for the first two; messages per student needs a
  wider one (1–2 · 3–5 · 6–10 · 11–25 · 26+) because a student's total spans an order of
  magnitude more than a session's.
- **`tokens` removed.** Completion tokens measure the model's verbosity, not the student's
  engagement — a tall bar there reads as "deep engagement" and means "GPT-4o was wordy".
- **Card order** (owner set the first two, the rest by weight): conversations per student ·
  conversation length · weeks active per student · messages per student · messages per
  conversation. The Bergmann-comparable turn count goes last: it is the measure most
  inflated by the `chat_fragmentation` caveat, and it is kept for comparability (their
  1.8/2.5) rather than for what it tells an educator.
- **Vocabulary unified on *conversation*** (D-08's unit) in every card title; field names
  keep `session`.
- **"IQR p25–p75" renders as "middle 50%"**, with the term on hover so a number here can
  still be matched to the thesis text. Display-only: `p25`/`p75` are unchanged in the
  document.

**Why these three had to be published rather than derived.** Invariant 4. An educator (or a
dashboard) dividing `totals.messages` by `totals.active_students` gets a mean and nothing
else — and on this data the mean and the median disagree sharply: 2026S is mean 7.5 against
median 5, because a long tail of heavy users pulls it. The skew *is* the finding, and no
arithmetic on published totals recovers it.

**What the real corpus says** (2026S, 132 active students, verified against the corpus
2026-07-30): conversations per student 52 · 42 · 27 · 11 with a maximum of 21 and median 2;
weeks active 66 · 55 · 11 · 0, i.e. **half the cohort wrote in exactly one week**; messages
per student 35 · 33 · 30 · 31 · 3, median 5, mean 7.5. The one-week half is what the tab
now says out loud.

**"Tried it" vs "adopted it" is stated, not left to the reader.** The weeks-active card
draws its single-week bin in a lighter tint of the accent (never gray — gray is
suppression), and leads with the sentence "66 of 132 students (50%) wrote in only one week".
That sentence is one published cell divided by another, which is the display math invariant 4
allows. It deliberately never states the complement: "students who came back" would be
`n_total` minus the bins, and a subtraction across bins is exactly how a suppressed bin's
value gets recovered. Both the sentence and the note are suppressed-safe — in a window where
the single-week bin falls under the floor, neither renders.

**Weeks, not days.** Days-active separates the middle of the distribution better (2026S:
55 · 53 · 22 · 2 against 66 · 55 · 11 · 0) but the ISO week is the unit the whole document
is built in (invariant 3), and "came back in three different weeks" is the adoption
sentence an educator wants. Days remain additive if the finer resolution is ever needed.

**Accepted: the differencing residual, declined secondary suppression.** These bins
partition the students that `n_total` counts, so `n_total` minus the published bins recovers
what the suppressed ones hold — exactly, when only one bin is suppressed, and there the
recovered number is a *student count*, the very quantity the floor protects. (Live example
at the time of writing: `trailing_4` weeks-active, 24 students, 23 in the single-week bin.)
The standard remedy is secondary suppression — never leave exactly one suppressed cell under
a published total. The owner declined it as over-engineering for a cohort-wide teaching
dashboard: the leak is bounded at 1–2 students, the floor stays per-cell here as everywhere
else, and the cost (a nearly empty chart in every short window) is real. Pinned by
`test_per_student_bins_floor_on_their_own_count` so the behaviour is deliberate rather than
accidental. This joins the differencing exposure D-50 left open for `by_status`.

**Removing a published section is treated as a minor bump.** §10 forbids removals within a
major version; `tokens` is withdrawn anyway, and §10 now carries the one narrow exception
that licenses it: an *optional section no reader renders* may go, because invariant 5 already
required every reader to tolerate its absence, and archived documents that still carry it
keep validating (readers ignore unknown fields — the exported schema sets no
`additionalProperties: false`, checked before deciding). Removing a *field from a section
that stays* is still a major break. `completion_tokens` remains in the corpus, so the view
can return additively.

**Consequences.**
- `_Message` no longer carries `completion_tokens`; `read_corpus_view` stopped selecting it.
  Extraction still stores it — reinstating reply length is aggregation-only work.
- Requires a re-aggregate + republish **and** a bundle redeploy: a schema bump needs both, or
  the deployed dashboard silently ignores the new section (D-51).
- Still deferred: Bergmann's `one_time_project_user` flag, days-active, and a Trends
  candidate for the per-student measures (the pool still compares only session medians).

**Publish record (D-53).** Went live the same day: blob
`v1/aggregates_2026-W30_20260730T151834Z.json` (+ `latest.json`), schema **1.5.0**,
`data_provenance: "production"`, axis 2025-W09 → 2026-W30, floor N=3, labels
`statsboteval-v2` / `lang-heuristic-v1`. Mode: **re-aggregate only**
(`--skip-extract --skip-classify`) — the corpus watermark stays at 2026-07-14, and mixing a
refresh into a schema change would have meant reviewing new numbers and a new tab at once.
Reviewed before uploading by diffing every `usage_context.totals` against the previous
publish: identical in all five windows, which is the claim this change makes about itself.
Bundle redeployed in the same session, as a schema bump requires (D-51): between the blob
upload and the deploy, the live site served 1.5.0 data to a 1.4.0 bundle, which renders the
withdrawn `tokens` card as "not in this data release yet" — harmless for the few minutes it
lasted, but it is why the two halves belong in one sitting.

`04_publish_production.sh` threw a `JSONDecodeError` in its own verify step: its second
`curl -sf` (the aggregates read, right behind the healthz request that wakes the F1 app from
idle) returned nothing, and the heredoc parsed an empty body. The upload itself had already
succeeded — re-curling immediately returned schema 1.5.0. Cosmetic, but the script would
read better if the verify curl retried once after a cold start instead of failing loudly
about a publish that worked.

## D-54 — 2026-07-30: Timing tab — dayparts replace the hour grid, semester rhythms overlay, week axis reads in months; schema 1.6.0

**Context.** An audit of the Timing tab found four problems: "Messages per week" never said
that one message is one *exchange* (a `history` row holds both `sent` and `received`),
"Active students per week" stated neither its ≥ 1-message rule nor the fact that it double-
counts across weeks, the 168-cell heatmap was being eaten by the privacy floor, and the
x-axis read `W10`, which no educator parses as "early March".

**The heatmap was the right chart at the wrong granularity.** 7 × 24 = 168 cells is too
fine for this corpus, and the stripes read as a privacy feature rather than a design
mistake. Non-empty cells suppressed, per published window: all_time 28/138, 2025S 40/122,
**2025W 52/84 (62%)**, 2026S 45/111.

The first fix considered was to publish the two *margins* (an hour profile and a weekday
profile), which barely suppress at all. **Testing killed it.** The weekday × daypart
interaction is real and is exactly the pedagogically interesting part — observed ÷
expected-under-independence over the published axis gives chi-square 159 on 18 df (critical
28.9), with **Saturday 00–06 at 3.75×**, Sunday evening 1.61×, against Friday evening 0.54
and Monday 0.69, and Wednesday small hours 0.28. Sunday's *daily total* is unremarkable
next to Friday's; the entire story is *when* on Sunday. Margins would have erased it.

So the grid stays and its hour axis coarsens to the dayparts: 7 × 4 = 28 cells, suppressing
2/28 all-time and 3/21 in 2025W. What is lost is the fine hour peak (11:00) becoming
"morning". Accepted.

**Four equal six-hour blocks, not six uneven ones — the owner's call, and it caught a real
defect.** The drafted registry used 2–8 hour blocks (06–09, 09–12, 12–14, 14–18, 18–22,
22–06). Bar length reads as intensity, so unequal bins invert the finding: that scheme puts
09–12 at 1,010 messages against 14–18 at 1,560, which says "afternoons are far busier",
while the per-hour rates are 337 and 390 — and the 2-hour midday block, *the shortest bar on
the chart*, is the densest period of the day at 408/h. Equal widths make the bars comparable
with no per-hour normalization. They also won on every other axis measured: least
suppression of any scheme tried (7 × 6 equal, 7 × 6 uneven, 7 × 8 all worse), a sharper
interaction, and no block wrapping midnight — which deleted a validator, a footnote clause
and a test case, because 00–06 starts the day instead of continuing the previous one.

**The dayparts registry ships in the document**, beside `windows` and `footnotes` (§6.3).
Same reason footnote texts do: a definition is versioned with the numbers it governs, and
the dashboard holds no daypart definitions of its own — labels and boundaries both come
from the blob. `_daypart_of` is a scan rather than `hour // 6`: the division is only correct
while every block is six hours wide, and that is a display property of today's registry,
not a law.

**Semester overlay renders under All-time only.** Re-indexing each semester to teaching week
answers "does the end-of-term surge repeat, and when?" — 2025S ramps to a week-17 peak of
218 messages, 2026S peaks at week 14 with 167. Nothing else on the dashboard asks that;
Trends compares *aggregates* between periods, not *shapes within* them. The chart cannot
honour the window picker, so rather than sit there ignoring a filter every neighbouring card
obeys, it renders only under `all_time` and is absent otherwise — the picker's meaning stays
exact. Deliberately not a `WindowGap`: that component says "not available for this window",
which would frame a design decision as missing data.

`semester_week` indexes the window's **full** Thursday-rule membership, not the covered
subset — this is the load-bearing line. Indexing on coverage would slide any semester whose
opening weeks are off-axis one week left and silently misalign every comparison the overlay
exists to make. Pinned by `test_semester_profile_indexes_full_membership_not_coverage`.
Both `messages` and `active_students` are published (cohorts differ in size — 2025S 165
active students vs 2026S 117 — so the latter is the size-robust read); the dashboard plots
messages, and a toggle is now a dashboard change rather than another schema bump.

**Week axis: month anchors, with Monday dates below 8 points.** `MMM-W#` was rejected on
measurement: **9 of the 24 months in 2025–26 hold five ISO weeks** (April 2026 and May 2025
among them, both on screen), the Monday and Thursday rules disagree on boundary weeks
(2026-W14 is `Mar-W5` or `Apr-W1`), `Mar-W1` repeats unqualified across years on the
74-week all_time axis, and going from 3 to 6 characters makes recharts drop *more* ticks
than today. The hierarchical axis — coarse unit named once at its boundary, fine unit
positional — is what every serious time-series axis does. Thursday rule for month ownership,
matching `windows.py:_semester_of`; the year rides on January and on the first tick, which
is what disambiguates the two `Mar`s. Short windows fall back to `02 Mar` on every tick
because a 4-week window need not contain a month boundary, and an axis with no labels is
worse than one with four. Tooltip and data table gained the exact range
(`W23 · 01–07 Jun 2026`), so precision moved rather than disappeared.

**Consequences.**
- `activity_heatmap` is still published and no longer rendered (~840 unread cells across
  five windows). It is a required field of a section that stays, and §10 forbids removing
  that within a major version — the 1.5.0 exception covers whole optional sections only.
  Also the rollback path.
- Requires a re-aggregate **and** a bundle redeploy in the same sitting (D-51).
- `TrendChart` now sets `interval={0}` / `minTickGap={0}`: the formatter already decides
  which weeks carry a label, and letting recharts thin them again would drop month anchors
  at random.
- Deferred, not rejected: **intra-session turnaround** (median 3.0 min, IQR 1.4–8.3, stable
  across both semesters — students read and re-ask in about three minutes, which is lookup
  rather than study). It is a session-depth measure and belongs beside Engagement's duration
  histogram. Also rejected: return latency (re-measures `user_classes`/`weeks_active`) and
  signup→first-message, which is degenerate — **364 of 443 students wrote within an hour of
  registering**, so Adoption's "signed up" and "sent at least 1 msg" tiles are near-identical
  by construction rather than by onboarding success.

**Publish record (D-54).** Went live the same day: blob
`v1/aggregates_2026-W30_20260730T213152Z.json` (+ `latest.json`), schema **1.6.0**,
`data_provenance: "production"`, axis 2025-W09 → 2026-W30, floor N=3, labels
`statsboteval-v2` / `lang-heuristic-v1`, all-time 379 active users / 3,528 messages. Mode:
**re-aggregate only** (`--skip-extract --skip-classify`) — the corpus watermark stays at
2026-07-14, because a schema-and-presentation change must not move a number and mixing a
refresh in would mean reviewing new numbers and a redesigned tab at once (the D-53 lesson).

The review gate was that claim, checked mechanically: every pre-existing section
(`usage_context`, `sessions`, `per_student`, `language`, `topics`, `trends`),
`temporal_usage.weekly`, and `activity_heatmap` in all five windows came back
**byte-identical** to the previous publish. Only the three new 1.6.0 blocks differ.
Bundle redeployed in the same sitting as a schema bump requires (D-51), and the deployed
chunk was verified to carry the new card titles rather than trusting the deploy's own
success message.

`04_publish_production.sh` threw the same cosmetic `JSONDecodeError` in its verify step
that D-53 recorded — the aggregates curl right behind the healthz wake-up returns an empty
body on a cold start, and the heredoc parses it. The upload had already succeeded; a
re-curl five seconds later returned 1.6.0. **Second occurrence, so it is systematic rather
than bad luck**: the verify curl should retry once after a cold start instead of failing
loudly about a publish that worked.

**One number in this ADR was corrected before the publish.** The exploratory figures were
measured with a hand-picked `axis_start` of 2025-02-24; `run-weekly` defaults to
**2025-03-01**, which excludes four days of week 09 — 3,528 published messages, not 3,552.
Every table in this entry and in the plan now quotes the built document.

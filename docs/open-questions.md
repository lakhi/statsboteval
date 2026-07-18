# Open questions

Restructured 2026-06-12 (decision review session): none of these block *building* milestone
1 — Phase A is developed end-to-end against synthetic fixtures. Items are grouped by what
they actually gate. Check items off (and move durable answers into the relevant doc) as
they resolve.

## Resolved

- [x] **Export capabilities** (was: Wolfgang/ZID) — a direct MySQL connection to the
      production DB exists; the weekly extract is scripted with in-flight pseudonymization.
      Recorded as decision **D-20**.

## Self-serve — recon queries against the production DB

*Run 2026-07-07 as Task 1 of the re-scoped Phase B plan (D-33), over Uni Wien VPN with a
read-only session (the DB is live — we never write). All four resolved; durable details
in `source-data-dictionary.md`.*

- [x] **Prod-vs-repo drift** — resolved 2026-07-07: `matnr` and `lv` **do not exist as
      columns in production** `students` (drift is the reverse of feared); prod adds a
      `registered` flag and an `import` roster table (Moodle "MethodsHub" export, 4,482
      rows) that *does* hold `Matrikelnummer`+`uid` — the stored matriculation number the
      consent names. Per-course `lv` segmentation is off the table.
- [x] **Data volume now** — resolved 2026-07-07: 550 students (443 with messages), 4,412
      messages, 1,871 sessions, 2024-07 → live. Classification cost at this scale:
      single-digit euros per full gpt-5-mini run (~3–4 M input tokens across all five
      passes), ≈ €10 even with a full gpt-5.1 escalation — Batch SKU stays unnecessary.
- [x] **Program-level source** — resolved 2026-07-07: **not in the production DB.** The
      only candidate (`import.Gruppen`) is "MethodsHub" for effectively every row. The
      Bergmann `Status` column came from outside the DB → remains with the Daniel item
      (Phase B inputs, below). Roster non-membership weakly proxies the "Other"
      (pre/postdoc) group only.
- [x] **`created_at` timezone** — resolved 2026-07-07: Laravel writes UTC strings into a
      Europe/Vienna-interpreting session (empirically confirmed via `started` diffs:
      monthly medians −3,530 s CET / −7,150 s CEST). **Extraction rule:** read with the
      server-default session timezone and treat values as UTC; never read with
      `time_zone='+00:00'`. The corpus "UTC assumed" convention holds; no Phase A
      aggregation change needed.

## Go-live gates — closed 2026-07-07 (D-34)

*Ownership clarified 2026-07-05: all three were project-owner decisions (Akshay), checked
against the governing documents and recorded with a date; Daniel is the erasure contact
per the consent addendum, not the gate decision-maker. All three closed 2026-07-07 — see
**D-34** for the full rationale. The first real publish still has operational
preconditions in the Phase B plan (recon, descriptives check, erasure runbook).*

- [x] **Pepper custody** (owner) — resolved 2026-07-07 (D-34): 256-bit pepper in the
      git-ignored `pipeline/.env` on the encrypted volume; backup copy in the owner's
      password manager; SHA-256 fingerprint interlock in the corpus so a wrong pepper
      fails loudly; rotation = re-ingest.
- [x] **Privacy floor N** (owner) — resolved 2026-07-07 (D-34): **N = 3** confirmed (no
      explicit minimum in the governing documents; k=3 excludes singling-out and
      two-student mutual inference; N=5 costs substantial surface at semester-week
      granularity for no articulable requirement).
- [x] **Architecture sign-off** (owner) — resolved 2026-07-07 (D-34): local corpus +
      transient Azure OpenAI EU classification + floored-aggregates-only publish approved
      as consent-consistent.

## Phase A build scoping — resolved by the D-32 redesign + go-live

- [x] **Hour×weekday heatmap value** (owner) — resolved by building it: the D-32 Timing
      tab ships the 7×24 grid, and the first real publish (D-37) shows it carries signal
      (clear weekday-afternoon peaks) despite per-cell suppression of quiet hours.
      Educator feedback on the live dashboard may still prune it later.
- [x] **Chart catalog** (owner) — resolved 2026-07-05/2026-07-17: the D-32 five-tab
      information architecture is the catalog, live on real data since D-37. Future
      changes are dashboard iterations, not open scoping.

## Thesis-interpretation items — needed for the write-up and Phase B context, not the build

- [ ] **Model timeline** (Wolfgang/ZID): which Azure deployment/model served StatsBot from
      March 2025 onward, with change dates? (No per-row model column — must be
      reconstructed externally.) *Per project owner (2026-06-19): StatsBot has run on GPT-4o
      since early 2025 to date; a GPT-5 upgrade is planned but not yet executed. The public
      Stage-2 manuscript (2026-06-30) confirms GPT-4o for Mar–Jun 2025 in print. Still need
      the exact Azure deployment ID(s) from ZID for the write-up.*
- [ ] **System prompt** (Wolfgang/ZID): does the Azure deployment bake in a persona/system
      prompt, or did students talk to a vanilla model? (App code sends none.)

## Phase B inputs — Bergmann replication details (no longer a gate)

*2026-07-02: the Stage-2 final manuscript, full coded dataset, production prompts, and R
scripts are now public on OSF (https://osf.io/v8ydk/), and the raw 1,400 messages on Zenodo
(https://doi.org/10.5281/zenodo.20827020) — most handover items resolved themselves.*

*2026-07-05: re-scoped from "gates" to "inputs" — there is no handover bottleneck;
building the classification pipeline is on us. Phase B planning starts after Part 2
implementation, using interim definitions from the public Stage-2 materials where the
items below are still open; each open item is chased in parallel, not waited on.*

- [x] **Exact GPT coding prompts** (deductive + inductive) — deductive obtained 2026-06-19
      from the OSF Stage-1 bundle; production *inductive* prompts (with final frozen theme
      lists inline) public since 2026-06-20 in the Stage-2 folder. Captured locally in
      `bergmann-prompts.md`.
- [x] **Access to the OSF folder** (https://osf.io/v8ydk/) materials — reviewed 2026-06-19,
      re-reviewed 2026-07-02 after the Stage-2 upload. The Stage-2 manuscript + data folder
      are now the source of truth (see `bergmann-framework.md` → "Source of truth &
      provenance"); the Stage-1 PDFs remain outdated.
- [x] **Inductive theme lists frozen or evolving?** — frozen and public (inline in the
      Stage-2 prompt `.odt`s and as `*_themes.csv`).
- [x] **The coded dataset and what identifies a message** — public
      (`full_dataset.csv`/`merged_data.csv`, Stage-2 folder); `id` = `history.id` (matches
      the manuscript's "consecutive message ID" and the `history` column set). **Join
      verified end-to-end against the live DB 2026-07-09** (over VPN, read-only): all 1,400
      `full_dataset.csv` `ID`s resolve to `history` rows, `started` matches 1,400/1,400
      exactly (a client epoch-ms value — effectively a fingerprint), and joining through
      `history.id → student_id` reproduces the study's 63 BA / 105 MA / 14 Other = 182
      students and 584/776/40 messages with zero per-student Status conflicts. (`sent` text
      matches 1,265/1,400; the rest are cp1252/whitespace serialization noise, not join
      errors — `started` proves row identity.)
- [x] **Bachelor/master mapping — residual** (Leonardo + Daniel/coordinators): the study
      got a per-student `Status` column with the coordinators' extract ("Other" =
      pre/postdocs). How is it derived, and how does our weekly extract reproduce it?
      *2026-07-07 recon: confirmed absent from the production DB (incl. the `import` roster —
      one Moodle course for everyone) and from the MethodsHub Moodle participant view
      (checked 2026-07-09: no study-level column; `Matrikelnummer` leading digits are the
      enrollment year, not the program), so it can only come from the coordinators.*
      **2026-07-09: the label is recoverable for the study window** — the OSF
      `full_dataset.csv` `Status` column joins to the live DB via the verified `history.id`
      key above (182 users: 63 BA / 105 MA / 14 Other). What remains open is (a) how
      `Status` was originally derived (u:space program enrollment? invitation lists?),
      (b) coverage beyond the 182 study-window users to the full cohort (~443 messaging /
      550 total, growing each semester), and (c) consent-compatibility of using the linkage
      beyond the already-published study window (overlaps the milestone-2 gate below). Email
      to Leonardo (and Daniel) drafted 2026-07-09 asking (a)–(c).
      **Resolved 2026-07-18 (D-39):** (a) Leonardo replied — Daniel performed the
      program-level linkage last year, producing the anonymous dataset behind the
      published paper; (b) full-cohort coverage solved by the owner's own roster-list
      derivation (8 program Excels outside the repo, uid→HMAC join; 550/550 corpus users
      labeled, zero unknown: 298 MA / 170 BA / 36 BA→MA transitioners / 46 staff);
      (c) **the linkage is in line with the ethics approval** (Leonardo, in writing).
      Program-level segmentation is unblocked; corpus storage + import = Phase B plan
      Task 21.
- [ ] **Declarative Statement production prompt** (Leonardo): the public deductive prompt
      file contains only 12 of 13 codebook blocks — Declarative Statement is missing
      (interim: manuscript Table 1 definition).
- [ ] **Production repetition protocol** (Leonardo): the Stage-2 manuscript documents
      repetition/majority voting only for the pilot (3×); nothing stated for the production
      GPT-5 runs — confirm single-run vs repeated before exact `bergmann-v1` replication.
- [x] **Classifier model on the consented platform** (self-serve/ZID) — resolved 2026-07-06
      (D-30). Chat text leaves the machine only via **Azure OpenAI EU, Data Zone Standard**
      (Sweden Central) for GDPR residency. Pinned **gpt-5-mini** (2025-08-07), escalating to
      **gpt-5.1** only if a category underperforms in validation. Several newer models
      (gpt-5.2/5.3, gpt-5.4-mini, the `-chat` variants) are **not** offered in Data Zone
      Standard there, which constrained the choice. Exact Bergmann replication is not a goal
      (owner), so the model/prompt differences are recorded as a validation caveat rather
      than avoided. Owner to confirm gpt-5-mini Data Zone Standard deployability in the
      portal before the first run.

## Milestone 2 gates

- [ ] **Course-records linkage** (Daniel/ethics): which records exist
      (enrollment/withdrawal, questionnaires), who provides them, on what key, in what
      format? *2026-07-07 recon: a linkage key exists in principle — the prod `import`
      roster maps `uid` ↔ `Matrikelnummer` (the stored matriculation number the consent
      names). Consent-compatibility check required before any use; StatsBotEval does not
      extract that table.*

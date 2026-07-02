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

Answerable directly over the MySQL connection; fold results into
`source-data-dictionary.md`.

- [ ] **Prod-vs-repo drift:** does production data actually populate `matnr` and/or `lv`?
      (Repo snapshot never writes them, but the consent names matriculation number as
      stored.) `SELECT COUNT(*) FROM students WHERE matnr IS NOT NULL AND matnr <> ''` etc.
- [ ] **Data volume now:** current counts of students / sessions (distinct
      (`student_id`,`started`)) / messages.
- [ ] **Program-level source:** the Bergmann extract carried a per-student `Status`
      column (`Bachelorstudent`/`Masterstudent`/`Other`) — check whether any prod table
      holds it (neither documented research table does), else it came from outside the DB
      (→ Daniel item below).

## Go-live gates — required before the first real-data publish (not before development)

- [ ] **Pepper custody** (Daniel/coordinating team): who holds the HMAC pepper, where is it
      kept, and where is its backup? (Low-stakes until first real ingest; corpus is
      reproducible from source until mid-2027, so rotation = re-ingest.)
- [ ] **Privacy floor N** (Daniel): does the ethics protocol imply a minimum cell size?
      (Working value: 5.)
- [ ] **Architecture confirmation** (Daniel): local-corpus + cloud-aggregates split,
      including transient Azure OpenAI processing for Phase B classification.

## Thesis-interpretation items — needed for the write-up and Phase B context, not the build

- [ ] **Model timeline** (Wolfgang/ZID): which Azure deployment/model served StatsBot from
      March 2025 onward, with change dates? (No per-row model column — must be
      reconstructed externally.) *Per project owner (2026-06-19): StatsBot has run on GPT-4o
      since early 2025 to date; a GPT-5 upgrade is planned but not yet executed. The public
      Stage-2 manuscript (2026-06-30) confirms GPT-4o for Mar–Jun 2025 in print. Still need
      the exact Azure deployment ID(s) from ZID for the write-up.*
- [ ] **System prompt** (Wolfgang/ZID): does the Azure deployment bake in a persona/system
      prompt, or did students talk to a vanilla model? (App code sends none.)

## Phase B gates — Leonardo / Bergmann study handover (deferred until after Phase A)

*2026-07-02: the Stage-2 final manuscript, full coded dataset, production prompts, and R
scripts are now public on OSF (https://osf.io/v8ydk/), and the raw 1,400 messages on Zenodo
(https://doi.org/10.5281/zenodo.20827020) — most handover items resolved themselves.*

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
      the manuscript's "consecutive message ID" and the `history` column set). Verify on
      import against `sent`/timestamps.
- [ ] **Bachelor/master mapping — residual** (Daniel/coordinators): the study got a
      per-student `Status` column with the coordinators' extract ("Other" = pre/postdocs).
      How is it derived, and how does our weekly extract reproduce it? (Also a recon query
      above.)
- [ ] **Declarative Statement production prompt** (Leonardo): the public deductive prompt
      file contains only 12 of 13 codebook blocks — Declarative Statement is missing
      (interim: manuscript Table 1 definition).
- [ ] **Production repetition protocol** (Leonardo): the Stage-2 manuscript documents
      repetition/majority voting only for the pilot (3×); nothing stated for the production
      GPT-5 runs — confirm single-run vs repeated before exact `bergmann-v1` replication.
- [ ] **Classifier model on the consented platform** (self-serve/ZID): chat text may only
      leave the machine via **Azure OpenAI (EU)** — not the OpenAI API the team used, and
      other vendors (e.g. Anthropic) would need a consent-compatibility check first. Policy
      (agreed 2026-07-02): quality-first — best model available on Azure OpenAI EU, tone
      down only if cost bites. To confirm: is GPT-5 deployable in our subscription? If a
      different model must be used, the `bergmann-v1` comparison loosens (model difference
      conflated with pipeline difference) — acceptable, but note it in the validation
      write-up.

## Milestone 2 gates

- [ ] **Course-records linkage** (Daniel/ethics): which records exist
      (enrollment/withdrawal, questionnaires), who provides them, on what key, in what
      format?

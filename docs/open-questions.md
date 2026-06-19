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
      since early 2025 to date; a GPT-5 upgrade is planned but not yet executed. Still need the
      exact Azure deployment ID(s) from ZID for the write-up.*
- [ ] **System prompt** (Wolfgang/ZID): does the Azure deployment bake in a persona/system
      prompt, or did students talk to a vanilla model? (App code sends none.)

## Phase B gates — Leonardo / Bergmann study handover (deferred until after Phase A)

- [x] **Exact GPT coding prompts** (deductive + inductive) — obtained 2026-06-19 from the OSF
      Stage-1 bundle; captured locally and summarized in `bergmann-framework.md`. (Harness =
      OpenAI API + the team's R evaluation scripts.)
- [x] **Access to the OSF folder** (https://osf.io/v8ydk/) materials — reviewed 2026-06-19.
      Note: the OSF *manuscript PDFs* are an outdated Stage-1 artifact; the team's working doc
      is the source of truth (see `bergmann-framework.md` → "Source of truth & provenance").
- [x] **Inductive theme lists frozen or evolving?** — finalized in the team's working results
      draft; treat as frozen pending publication.
- [ ] The coded dataset, and **what identifies a message** in it (ideally `history.id`).
- [ ] Source of the bachelor/master program-level mapping used in the study (the split is a
      core result, but how students are mapped to bachelor/master/other is not yet documented
      for us).

## Milestone 2 gates

- [ ] **Course-records linkage** (Daniel/ethics): which records exist
      (enrollment/withdrawal, questionnaires), who provides them, on what key, in what
      format?

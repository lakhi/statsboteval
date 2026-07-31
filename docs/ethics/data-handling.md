# Data handling — binding constraints

Source of authority: `informed-consent-addendum.pdf` (bilingual German/English; shown to and
accepted by every StatsBot user at registration; deadline-extended 2027 version). This page
extracts the constraints that bind StatsBotEval's design. If this summary and the PDF ever
disagree, the PDF wins.

## What students consented to

- StatsBot stores first name, surname, matriculation number, chat histories, and token counts
  in a ZID web database (needed for the chat-history feature).
- Chat messages are sent to a Microsoft Azure LLM (EU data centers) to generate responses;
  University of Vienna's Azure data-protection regulations apply.
- Chat histories may be **exported and analyzed for scientific research until end of June
  2027** (further information: https://osf.io/v8ydk/).
- Anonymous course data (e.g. enrollment in / withdrawal from statistics tutorials) and
  anonymized questionnaire data may be **linked** to chat histories.
- For analysis, chat histories are **pseudonymized** (personal information removed) and stored
  on a **password-protected local storage medium until end of 2027**.
- Students may request **deletion until end of July 2027** (contact:
  daniel.reiter@univie.ac.at).
- Afterwards chat histories are **anonymized and added to a public dataset** (e.g. on OSF);
  the pseudonymized corpus is **permanently deleted** in that process.

## What this means for StatsBotEval (hard rules)

1. **The pseudonymized corpus lives locally only** — on a password-protected/encrypted local
   medium. It must never be stored in a cloud database, object store, or this git repository.
2. **The cloud side (Azure dashboard) receives only aggregated, non-identifying outputs.**
   Aggregation happens locally, and the privacy floor is applied there: any aggregate cell
   covering fewer than **N students is suppressed before publication** (working value N = 3,
   lowered from 5 on 2026-07-05 — decision D-24; confirmation against the ethics protocol
   pending — see `../open-questions.md`).
3. **Transient LLM processing is permitted, cloud storage is not.** Sending message text to
   Azure OpenAI for classification matches already-consented practice (StatsBot itself, and
   the Bergmann study's GPT-based coding); persisting message text cloud-side does not.
4. **Pseudonymization mechanism:** pseudonym = HMAC(uid, secret pepper), with `uid`
   normalized (trim + lowercase) before hashing. Deterministic, so pseudonyms are stable
   across weekly pipeline runs without a stored mapping table. Re-identification requires
   the pepper. Pseudonymization is applied **in-flight** during extraction (decision D-20):
   direct identifiers flow from the source MySQL DB through pipeline memory into the HMAC
   and are never persisted on the local medium — only pseudonymized rows are stored.
   *Pepper custody: to be fixed with the coordinating team (placeholder — see
   `../open-questions.md`).*
5. **Erasure procedure** (requests via daniel.reiter@univie.ac.at, until end of July 2027):
   compute HMAC(uid) for the requesting student, delete all corpus rows with that pseudonym,
   re-run aggregation, republish. Document each request's completion date.
6. **End-of-life obligations** (calendar deadlines):
   - End of June 2027 — last date for exporting/analyzing chat histories.
   - End of July 2027 — deletion-request window closes.
   - End of 2027 — anonymize the corpus, publish the anonymized dataset (OSF), permanently
     delete the pseudonymized corpus. The pipeline should eventually implement this
     anonymize-and-export step.

## Program-level roster data (approved linkage, EK 01548)

The consent addendum states that "anonymous course data (e.g. data relating to enrollment
in and withdrawal from statistics tutorials) … are linked to chat histories in order to
better analyze usage patterns"; the addendum application naming this linkage was approved
by the Ethics Committee (EK 01548, decision 2026-05-05), and the study leader confirmed in
writing (2026-07-18) that program-level linkage is in line with the approval — the same
linkage produced the published Stage-2 paper's dataset. Program level (bachelor/master/
staff) is enrollment-type data in this sense. Handling rules (decision D-39):

1. The linkage input is a **uid-keyed CSV** (`uid,status,ma_start_semester,source`)
   derived from the coordinators' roster lists. It lives **outside the repo tree**, in
   the same password-protected/encrypted directory as its source Excel lists — one
   identifier custody location; the repo working tree stays free of direct identifiers,
   extending rule 4's in-flight principle tree-wide. The importer reads its path from
   `STUDENT_STATUS_CSV` in the git-ignored `pipeline/.env`.
2. The pseudonymization promise above attaches to *chat histories*; the corpus keeps it —
   it stores only the pseudonymized derivative (`student_status`, HMAC-keyed), and the
   status↔message linkage happens on pseudonyms, locally. "Anonymous course data"
   describes the data as analyzed, not the intermediate: an identified join key is
   inherent to any linkage, matching the study leader's own confirmed practice.
3. Published aggregates expose program level only as privacy-floored `by_status` cells
   (rule 2 unchanged; sub-floor groups suppress).
4. **Lifecycle:** the CSV follows the corpus deadlines (rule 6) — permanently deleted in
   the end-of-2027 anonymize-and-delete step. An **erasure request also removes the
   student's row from the CSV** (not only from `student_status`); otherwise the next
   roster re-import would restore it.
5. Assessed 2026-07-18: the keying choice is internal data-handling within the approved
   linkage — no new data category, purpose, or recipient — and therefore not a content
   amendment requiring re-submission to the committee.
6. **Enrolled-cohort totals are repo-eligible; the lists they come from are not**
   (2026-07-31, D-55). `pipeline/cohort_totals.json` holds six numbers — how many bachelor
   and master students were enrolled in each published semester — derived from the SSC-Psych
   roster Excels and committed to this public repo. This does not weaken rule 1: an
   institutional headcount is aggregate, non-identifying, describes no student in the
   corpus, and is published on the dashboard regardless. The Excels themselves, and every
   uid in them, stay on the password-protected medium as before. Derivation happens in the
   roster session beside the lists; this repo records only the resulting counts, never
   re-derives them, exactly as D-39 set up for the status CSV.

## Accepted residual risk — repeated releases

Published aggregate file versions are retained (decision D-10), so consecutive weekly
versions can be **differenced**: a cell that grows from one week to the next reveals an
increment that may cover fewer than N students, even though every published cell
individually passes the privacy floor. This is the standard "repeated releases" limitation
in statistical disclosure control. It is **accepted, not overlooked**: the published cells
are non-identifying usage aggregates (topic counts, temporal patterns, language shares) —
learning that a small number of unnamed students contributed to a cell's weekly increment
identifies no one and exposes no sensitive attribute. Remedies (rounding, perturbation,
cumulative-increment suppression) would cost accuracy disproportionate to this risk.
Reassess if cell semantics ever become more sensitive than usage statistics.

## Repo policy

No real data in git, ever: enforced by `.gitignore` (data file types and directories) and by
review discipline. Test fixtures must be synthetic and labeled as such.

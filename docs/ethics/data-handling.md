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
   covering fewer than **N students is suppressed before publication** (working value N = 5;
   confirmation against the ethics protocol pending — see `../open-questions.md`).
3. **Transient LLM processing is permitted, cloud storage is not.** Sending message text to
   Azure OpenAI for classification matches already-consented practice (StatsBot itself, and
   the Bergmann study's GPT-based coding); persisting message text cloud-side does not.
4. **Pseudonymization mechanism:** pseudonym = HMAC(uid, secret pepper). Deterministic, so
   pseudonyms are stable across weekly pipeline runs without a stored mapping table.
   Re-identification requires the pepper. *Pepper custody: to be fixed with the coordinating
   team (placeholder — see `../open-questions.md`).*
5. **Erasure procedure** (requests via daniel.reiter@univie.ac.at, until end of July 2027):
   compute HMAC(uid) for the requesting student, delete all corpus rows with that pseudonym,
   re-run aggregation, republish. Document each request's completion date.
6. **End-of-life obligations** (calendar deadlines):
   - End of June 2027 — last date for exporting/analyzing chat histories.
   - End of July 2027 — deletion-request window closes.
   - End of 2027 — anonymize the corpus, publish the anonymized dataset (OSF), permanently
     delete the pseudonymized corpus. The pipeline should eventually implement this
     anonymize-and-export step.

## Repo policy

No real data in git, ever: enforced by `.gitignore` (data file types and directories) and by
review discipline. Test fixtures must be synthetic and labeled as such.

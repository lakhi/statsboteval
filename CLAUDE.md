# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**StatsBotEval** — an automated evaluation framework for student–GenAI interactions; Akshay
Lakhi's master's thesis project (MEi:CogSci, University of Vienna). It analyzes chat data
produced by **StatsBot** (separate repo: `~/Developer/uni-studAsst-projects/statsbot`, a
Laravel + Angular GPT chat client in production since March 2025) and presents aggregated
insights to educators.

Three milestones: (1) educator-facing dashboard, (2) exploratory ML analysis (GBDT + SHAP vs
course performance), (3) master's thesis. See `docs/research-context.md`.

**Current status: milestone 1 live on real data** at <https://statsboteval.azurewebsites.net>
since 2026-07-17 (D-37); Phase B classification complete (D-42/D-43/D-44). The weekly
pipeline extracts from the production DB, classifies, aggregates under the N=3 floor, and
publishes; the dashboard serves five educator-question tabs plus Topics and **Trends**
(period comparisons, schema 1.3.0, D-49 — built 2026-07-30, not yet published). Timing was
rebuilt on schema 1.6.0 (D-54): dayparts replace the 168-cell hour grid, a semester-rhythm
overlay renders under All-time, and week axes read as month anchors. **Schema 1.8.0 (D-56)
went live 2026-07-31** — `trailing_4` is gone, replaced by slices of a semester's closing
stretch — and **D-57 went live 2026-08-01**, narrowing those slices to the anchor semester
alone: `2026S.last4` / `2026S.last1` sit in a flat `Recent` group beside `Semesters` and
`Everything`, and no other semester is sliced. D-57 was a data-and-display change only; the
schema stays 1.8.0. **D-58 (built 2026-08-01, not yet published)** dissolves Adoption's
`Note.` paragraph into per-cell notes, rewrites four footnote texts, mints
`retention_all_time`, links the Bergmann citation to OSF, and reorders the tabs to
Adoption → Engagement → Topics → Timing → Language (Adoption is now the landing tab); also
data-and-display only, still 1.8.0, but it **needs both go-live halves** because the texts
travel in the blob. **D-59 (built 2026-08-01, not yet published) moves the schema to
1.9.0**: New signups is now split by program level — resolved from the roster at the
*registration* date, which is how a registrant who never wrote gets a level at all —
plus a round of caveat removals across all five tabs, donuts on Adoption's and Language's
part-to-whole cards, and three cards moved to the top of their tab. Both halves again.
Corpus scale:
550 students / 4,419 messages / 15 frozen emergent themes. Remaining `docs/open-questions.md`
items gate thesis interpretation (Wolfgang) and milestone 2, not day-to-day development.

**Published labels are `statsboteval-v2`** since 2026-07-28 (D-45): same model, deployment,
effort and seed as v1, with `CLASSIFIER_BATCH_SIZE` 50 → 10 and Bergmann's actual
Declarative Statement block. Average MCC **.823** on the 300 human-consensus messages
(v1: .714), above the Bergmann GPT-5 reference of .79; no category regressed.
`statsboteval-v1` is kept in the corpus as the comparison baseline and rollback path —
reverting means pointing `CLASSIFIER_LABEL_VERSION` and `--classification-version` back
at it and re-aggregating, no re-classification.

`labels.CURRENT_LABEL_VERSION` is the **single source of truth** for that default (settings,
both CLI flags, synthetic fixtures). Minting the next version is one edit there; never
reintroduce a bare `"statsboteval-vN"` literal in production code. The API and dashboard hold
no label version at all — they render whatever the published document declares.

`run-weekly` is **not yet scheduled** — every publish is a manual operator run
(`docs/plans/2026-07-27-weekly-run-automation.md` drafts the launchd wrapper).

## Binding constraints — read before any data-touching work

From the informed-consent addendum (`docs/ethics/informed-consent-addendum.pdf`, summarized in
`docs/ethics/data-handling.md`):

1. **No student data ever enters this repo or any cloud database.** Pseudonymized chat
   histories live on a password-protected LOCAL storage medium only (until end of 2027).
2. The cloud (Azure) side receives **only aggregated, non-identifying outputs** that have
   passed the privacy floor (aggregate cells covering fewer than N≈3 students are suppressed
   at aggregation time, locally).
3. Sending chat text to Azure OpenAI for classification is consistent with consented practice
   (EU data centers); storing it in the cloud is not.
4. Data lifecycle deadlines (deletion window until end of July 2027, anonymize-and-publish to
   OSF afterwards) are documented in `docs/ethics/data-handling.md`.
5. **The production StatsBot MySQL DB is live and strictly read-only for this project** —
   we analyze the data, never modify it. Every connection sets
   `SET SESSION TRANSACTION READ ONLY` at connect time and issues only `SELECT`/`SHOW`;
   no INSERT/UPDATE/DELETE/DDL under any circumstances.

## Architecture (agreed 2026-06-10, amended 2026-06-12 and 2026-07-03, see docs/decisions.md)

```
LOCAL (password-protected machine)                 AZURE (dashboard public by URL)
weekly Python batch pipeline:                      Blob: versioned aggregates file (private)
  extract (direct MySQL, in-flight                 FastAPI aggregates API (reads blob;
  pseudonymize HMAC(uid, pepper))                    future auth boundary)
  → DuckDB corpus (one file, encrypted             Next.js dashboard, static (English)
  disk) → classify (Bergmann prompts,              — no chat text exists cloud-side
  versioned labels) → aggregate +
  privacy floor → publish to Blob
```

- Deployment pattern follows `~/Developer/uni-studAsst-projects/ai_agents_ws/api-apps/health-research-agent-api`
  (FastAPI, Docker, `.env.local`/`.env.azure` switching, ruff/mypy/pytest).
- Classification labels are versioned (`bergmann-v1` imported, `statsboteval-v1` from our
  pipeline); the dashboard reads one configured version.
- A "conversation" = one `started` session, keyed by (`student_id`, `started`) (StatsBot's
  app-native grouping; see `docs/source-data-dictionary.md` for `started` semantics and
  other source-schema gotchas).

## Non-obvious invariants — breaking these silently corrupts data

- **Timestamps: never set the MySQL session timezone.** `extract.py` reads `created_at`
  with the server-default session tz on purpose. Laravel wrote UTC wall-clock strings that
  MySQL reinterprets as Vienna local; forcing `time_zone='+00:00'` skews every timestamp
  1–2 h. The correct code is code that *isn't there*.
- **`normalize_uid` (trim + lowercase) must run before the HMAC**, or casing variants fork
  one student into two pseudonyms. Same function in `extract.py` and `status.py` — that
  shared call is what makes the roster join line up.
- **The pepper interlock is load-bearing** (D-34): the corpus stores `sha256(pepper)` in
  `meta`; a mismatch aborts before any source query. Never bypass `verify_pepper`.
- **`floored_count()` is the only path from a corpus number to a published cell.** The
  floor tests *distinct contributing students*, never the value. `n_students == 0` publishes
  `ok(0)` — a measured zero is not identifying, and suppressing it would destroy meaning.
- **`prompt_tokens` counts the entire re-sent conversation context**, growing within a
  session. It is not a message-size metric; use `completion_tokens`.
- **The retention baseline reads *behind* `axis_start`** (D-50). `first_seen` in
  `read_corpus_view` is built before the `axis_start` filter, on purpose: a student who
  wrote during the 2024/25 pilot is not a "new user" in 2025S just because the pilot weeks
  are unpublishable. Move that line under the filter and every returning user silently
  becomes new (2025S would read 190 new / 0 returning instead of 150/38).
- **`frequent` is a subset of `monthly`, not a fourth user class** (D-50). Bergmann's script
  sets five *independent* flags; `all(gaps < 14) & span > 30` implies their occasional
  condition. Making it exclusive would redefine our `monthly` away from their
  `occasional_user` — invisibly, since n = 0 today. `one_time`/`monthly`/`sporadic`
  partition and sum to `active_students`; `frequent` never adds to them.
- **`created_at` is THE temporal axis** (weeks, windows, heatmap). `session_started` is a
  client clock — a session *key*, plus status-at-usage-time resolution, never an axis.
- **The program-level rule lives once, in `status.status_at(row, date)`** (D-59).
  `resolve_status` applies it to a session's start, `aggregate` to a signup's registration
  date — the same Beginnsemester boundary read at two instants, which is why signups can
  carry a level at all (a registrant who never wrote has no session to key off). Copying
  the comparison into either caller is two answers waiting to diverge. Corollary: a signup
  is never reassigned by a later BA→MA move, and a level that signed up but never wrote
  has no `by_status` slice, so published levels can sum to less than the window total.
- **Dayparts are four *equal* six-hour blocks, and the equality is load-bearing** (D-54).
  Bar length reads as intensity, so unequal bins invert the finding — the rejected 2–8 h
  draft made the densest period of the day (12–14 at 408 msg/h) the shortest bar on the
  chart. Re-cutting them unevenly silently lies. `_daypart_of` is a scan, not `hour // 6`,
  so a re-cut degrades the chart instead of corrupting the buckets.
- **`semester_week` indexes a semester's full Thursday-rule membership, never its
  coverage** (D-54). A semester whose opening weeks fall outside the axis must still start
  at the week it really started, or every curve in the overlay slides left by the number of
  missing weeks — invisibly, since each curve still looks plausible on its own. The same
  rule governs a slice's `semester_weeks` (D-56), and `contract._check_windows` now pins it.
- **A semester slice is anchored in its semester, not in the axis** (D-56). That is the
  whole point of replacing `trailing_4`: an axis-anchored "recent" window advances with
  extraction whether or not anyone was in class, so across a break it drifted into weeks
  holding almost nothing. Anything that re-derives a slice from `axis[-4:]` reintroduces
  the bug.
- **Only the anchor semester is sliced, and the anchor follows the data** (D-57). It is the
  last semester the *axis* reaches, not the one the calendar says we are in: between a term
  opening and its first complete week being extracted, "recent" must still point at the
  previous term. Deriving the anchor from `date.today()` reintroduces `trailing_4`'s bug in
  a new place. Labels are state-free since D-57 (`Previous N weeks`, `Last available week`)
  — do not restore the `Latest`/`Final` branch 1.8.0 briefly shipped.
- **`short_label` is declared but unemitted outside `semester_slice`, and stays that way**
  (D-56, D-57). It is optional on `all_time` and `semester` for a deployment reason: the
  API validates every fetched blob against the schema it ships with, so making it required
  would turn "API deployed before the blob is published" from a degraded render into a 500.
  Old documents must stay valid under new schemas; `api/tests/fixtures/
  aggregates_synthetic.json` is a 1.0.0 document kept as that proof. It is still *required*
  on `semester_slice` and nothing renders it — deleting it is a **major** break under
  contract §10, which is why an unread field is the cheaper of the two options.
- **`retention_all_time` is attached by the pipeline, to `all_time` only** (D-58). It says
  "returning here names the 2024/25 pilot cohort" — true of the widest window, false and
  quietly misleading on a semester, where returning means semester-to-semester loyalty.
  The placement is a `window.kind` test in `aggregate.py`, not a registry fact, so the
  dashboard must read `totals.footnote_ids` rather than the registry when deciding to
  render it. Related: `footnoteText` returns **null** for an id the document lacks, because
  a caveat rendered as standalone prose has no symbol to fall back to and would print the
  raw id during the bundle-before-blob deploy gap.
- **One label version never mixes models or inference settings** (D-41). Changing either
  means a new version and a full re-classify. **`CLASSIFIER_BATCH_SIZE` is an inference
  setting, not a throughput knob** (D-45): it sets how many decisions one call is asked
  for, and re-tuning it alone moved average MCC .71 → .82. `BATCH_LIMIT` in
  `classify/prompts.py` is the *ceiling*; `DEFAULT_BATCH_SIZE` is what we run at — the two
  were one constant until D-45, which is exactly how 50 survived unexamined.
- **cli.py's function-local imports are deliberate** — they keep `run-synthetic` working
  without pymysql/openai/azure installed. Do not hoist them to module scope.
- **Emergent theme sets are immutable.** `freeze-themes` refuses to overwrite; regeneration
  mints `…-v2` with its own operator review (the D-33 privacy control).

## Conventions

- Source-of-truth docs live in `docs/`; update `docs/decisions.md` (ADR-style) when a
  significant choice is made or reversed.
- The StatsBot source schema is documented in `docs/source-data-dictionary.md`; if the
  StatsBot repo's schema changes, update that file in the same change.
- Never weaken `.gitignore` data exclusions. Test fixtures must be synthetic and clearly
  labeled as such.

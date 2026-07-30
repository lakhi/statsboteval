# Trends tab — pipeline-computed period comparisons (design + execution plan)

**Date:** 2026-07-19 · **Rewritten:** 2026-07-29 after owner review
**Status:** **built and verified 2026-07-30 (T-1…T-9 done); awaiting the operator publish**
**Decision recorded:** **D-49**
**Contract:** additive minor bump → schema **1.3.0**, same `v1/` blob prefix

## Goal

A sixth dashboard tab, **Trends**, to the right of Language. For the selected window it
answers *"what changed, compared with the previous period?"* with a small set of
pipeline-selected findings (at most 5, possibly 0) drawn from the measures behind all
five existing tabs. The comparison pairing follows the window picker:

| selected window | baseline |
|---|---|
| semester (e.g. 2026S) | previous semester by chronology (2025W) |
| earliest semester | none — explanatory empty state ("no earlier period to compare") |
| `trailing_4` | the 4 complete weeks preceding the trailing window (hidden baseline, not a picker entry) |
| `all_time` | per-semester trajectory: each finding shows its measure across every semester |

**What the tab is *for* (owner, 2026-07-29):** the audience is a statistics educator or
an evaluator of StatsBot. The tab surfaces the changes most likely to **change a teaching
or tooling decision** — not the changes with the smallest p-values. Statistics decide
what is *admissible*; usefulness decides what is *shown*.

## Why the pipeline computes trends (not the dashboard)

Contract invariant 4 — the client never re-aggregates — already decides most of this:
selecting "meaningful" differences is analysis, not display math. But the stronger
reason is statistical: the raw per-student data exists **only locally**, so real
hypothesis tests (which need per-student/per-session observations, not floored
aggregates) can only run in the pipeline. The dashboard receives finished findings and
renders them; the file remains the complete statement of everything the dashboard can
show.

## Owner-approved design choices

### 2026-07-19 session

1. **`trailing_4` compares against the preceding 4 complete weeks** (`axis[-8:-4]`,
   derived from `TRAILING_WEEKS` in `windows.py`, never a literal), embedded in the
   section as a baseline reference — no new window-registry entry. If the axis has fewer
   than 8 weeks, baseline is `null` (empty state).
2. **`all_time` shows per-semester trajectories** (e.g. German share 68% → 61% → 52%),
   not a two-point comparison. Break weeks (Feb, Jul–Sep) drop out naturally because
   semesters partition the published axis.
3. **Volume measures compare as per-covered-week rates** (messages/week, sessions/week,
   active students/week, registrations/week) so unequal window lengths and an
   in-progress semester stay comparable. Shares and medians compare as-is. A new
   `per_week_rate` footnote carries the in-progress caveat (within-semester seasonality
   is acknowledged, not corrected). Reaffirmed 2026-07-29: no window is currently in
   progress, semester lengths are close (~17–18 weeks), and volume rates now sit in the
   lowest relevance tier — the alternative (same-elapsed-weeks clipping) would discard
   data to fix a problem this corpus does not have.
4. **Formal tests in the pipeline, plain language in the UI.** Two-proportion z for
   shares, Mann–Whitney U (normal approximation, tie-corrected) for per-session
   measures, Benjamini–Hochberg correction. The card shows an effect size and a
   qualitative evidence marker; the method name is published per finding
   (tooltip/footnote), p-values are not shown on cards.

### 2026-07-29 session

5. **Census framing, settled in-house.** These are all StatsBot users, not a sample, so
   the tests are framed as a guard against over-reading noise, not inference to a
   population. The thesis states this framing. No external sign-off is sought or
   required for any StatsBotEval decision.
6. **Ranking is usefulness-first.** Findings sort by a pinned **relevance tier**, with
   effect size only as the tie-break *within* a tier. Significance is a gate, not an
   ordering. This is what makes the tab answer "what should I look at?" rather than
   "what moved most?".
7. **Benjamini–Hochberg runs over one family per window** — every candidate corrected
   together. Chosen for simplicity and defensibility: per-tab families would hold a
   topic finding and a language finding to different standards in the same list. The
   two-tier evidence marker is the release valve (see the gate below), so a strict
   family cannot starve the tab; it changes how confidently findings are labelled.
8. **Method and software themes enter the candidate pool** — a reversal of the
   2026-07-19 exclusion. *Which statistical methods students ask about* is the most
   actionable signal this dashboard can carry for a statistics educator; excluding it
   while ranking `Politeness Expression` inverts the stated priority.
9. **Topics gets 3 of the 5 slots** (other tabs stay at ≤2). Topics holds most of tier
   1; capping it at 2 would force lower-tier findings onto the page by construction.
10. **Stability is not published.** Zero findings renders the plain empty state; the tab
    never manufactures a "topic mix was stable" claim, because absence of evidence
    through a noise gate is a weaker statement than it appears. The panel deck says so
    up front, so a short list reads as intended rather than as missing data.
11. **Effect-size thresholds are pinned per measure family, not per kind** — see gate
    (c). Without this, choices 8–9 have no effect: a shares threshold sized for language
    is unreachable for an individual topic theme.
12. **"Nothing changed" and "not enough data to look" are different states.** Roughly a
    third of the year is break weeks (Feb, Jul–Sep), and `trailing_4` sits in them for
    months at a time. When no candidate is even testable, saying "no meaningful shifts"
    implies a comparison happened and came back flat. An `insufficient_data` flag
    carries the distinction, and the copy names the likely cause (semester break,
    Christmas closure, exam period).

## Candidate measure pool + relevance tiers (pinned in code, one place)

Each candidate is (tab, measure, kind, test, **tier**). Kinds: `rate` (per covered
week), `share` (proportion of a window's messages/sessions/users), `median` (per-session
distributions).

**Tier 1 — changes what you teach, or whether the tool is working**

| tab | candidates |
|---|---|
| topics | per-theme share for **method themes** and **emergent themes**; deductive `Statistics Interaction` |
| adoption | one-time-user share of active students |

**Tier 2 — tells you how students are working**

| tab | candidates |
|---|---|
| engagement | median messages per session, median session duration (Mann–Whitney) |
| topics | per-theme share for **software themes**; deductive `Question Posed`, `Instruction Given`, `Multiple Choice`, `Reference to a Prior Content`, `Capability Request`, `Declarative Statement`, `Specific Method`, `Data Analysis Software` |
| timing | weekend share; share of messages by pinned daypart (morning 6–12, afternoon 12–18, evening 18–24, night 0–6) — most-shifted daypart enters ranking |

**Tier 3 — context**

| tab | candidates |
|---|---|
| adoption | messages/week, sessions/week, active students/week, registrations/week (rates) |
| language | German share and English share of messages (most-shifted enters) |
| topics | deductive `Politeness Expression`, `Greeting Expression` |

**Excluded from the pool:** deductive `English Input` / `German Input` — the Language
tab already publishes German/English share of messages. Keeping both puts one phenomenon
into the BH family twice and lets it occupy two slots.

Tiers **order, they do not exclude**: if only tier-3 measures moved in a window, showing
them beats showing nothing.

### Selection rule (per window, deterministic)

**Gate — is it real?** A candidate is admissible only if all hold:

- (a) both sides' distinct contributing students ≥ `privacy_floor_n` — sub-floor
  candidates are silently dropped, never rendered as "suppressed";
- (b) minimum n per side (pinned, e.g. ≥30 messages for shares);
- (c) minimum effect size, pinned **per measure family** — not per kind. Language shares
  sit at 40–60% where 5 pp is an ordinary move; an individual topic theme holds maybe
  2–8% of messages, where 5 pp is unreachable. A single shares threshold would gate out
  exactly the tier-1 measures choices 8–9 promote. Families: language shares, topic
  shares, timing shares, rates, medians — each with its own absolute floor, plus a
  relative-change floor for the small-base families so "regression questions went
  3% → 6%" can qualify on doubling rather than on percentage points. This is what keeps
  trivially small but significant shifts off the page, and it matters *more* now that
  ranking is not significance-ordered;
- (d) BH-adjusted p < 0.05 → evidence `"robust"`; else unadjusted p < 0.05 → evidence
  `"indicative"`; else dropped.

**Rank — is it worth attention?** Survivors sort by **(relevance tier ascending,
normalized effect size descending)** — |log rate ratio| for rates, |Δpp| for shares,
rank-biserial correlation for medians. Greedy fill with a per-tab cap: **≤3 for topics,
≤2 for every other tab**, overall cap 5.

For `all_time`, significance comes from the endpoint test (first vs last semester) and
the full per-semester trajectory is published; a trend test (Cochran–Armitage) is a
noted upgrade path, not v1.

### Pinning discipline (D-49 records this split)

- **Relevance tiers are pinned *before* the dry run.** They are a judgment about
  pedagogy, not an empirical finding; nothing in the data informs them.
- **Magnitude thresholds are pinned *after* one recorded dry run** (T-4), **per measure
  family**, so the tab is neither permanently empty nor full of trivia. One documented
  calibration pass, not iterative tuning.

Rates, shares, and medians derived from ≥N-student groups pass the same privacy
reasoning as existing cells; each published side carries its `n_students` (≥ floor,
guard-enforced), keeping every number citable.

## Contract additions (schema 1.3.0, additive)

```json
"trends": { "per_window": { "<window_id>": {
    "baseline": { "kind": "window", "window_id": "2025W" }
              | { "kind": "weeks", "from": "2026-W21", "through": "2026-W24" }
              | { "kind": "trajectory" }
              | null,                          // no predecessor → FE empty state
    "insufficient_data": false,                // true → nothing was even testable
    "findings": [ {
        "id": "language-de-share",             // stable slug
        "tab": "language",                     // topics|adoption|engagement|timing|language
        "title": "German share of messages fell",   // template-generated, no chat text
        "measure": "German share of messages",
        "kind": "share",                       // rate | share | median
        "unit": "% of messages",               // display unit ("per week", "messages", …)
        "current":  { "value": 48.1, "n_students": 74 },
        "baseline": { "value": 61.8, "n_students": 91 },
        "delta": -13.7,                        // in unit terms (pp, per-week, minutes…)
        "evidence": "robust",                  // robust | indicative
        "method": "two-proportion z, BH-adjusted",
        "trajectory": [ { "window_id": "2025S", "value": 68.2, "n_students": 88 }, … ],
                                               // present only under all_time
        "footnote_ids": ["trend_method", "language_heuristic"]
    } ]
} } }
```

Model names: `TrendsSection`, `TrendsWindow`, `BaselineRef` (tagged union), `Finding`,
`MeasureValue`, `TrajectoryPoint`. (`Finding`, not `TrendFinding` — see the naming note
under T-7.)

- Every registry window gets an entry; `baseline: null` + empty `findings` encodes "no
  predecessor" explicitly (the FE must distinguish it from "no meaningful shifts").
- ⚠️ **`dump_doc()` uses `exclude_none` and will silently drop `baseline: null`.**
  `TrendsWindow` needs the `HistogramBin._serialize` treatment
  (`contract.py:98-104` — a `model_serializer(mode="wrap")` that reinstates the key
  unconditionally), for exactly the reason stated there: the null *is* the marker.
- `relevance_tier` is **not published**. It is a pipeline-side ordering input; the FE
  renders the array in the order it receives. Publishing it would invite the dashboard
  to re-sort, which invariant 4 forbids.
- **`insufficient_data`** (default `false`) is true when a baseline exists but **no
  candidate cleared gates (a)+(b)** — nothing was testable, as opposed to tested and
  flat. Being a `bool` with a default it always serializes, so it needs no
  `exclude_none` workaround. It is meaningless without a baseline: when `baseline` is
  `null` it is always `false`, and the guard enforces that.
- Finding values are floats (rates/shares/medians are derived numbers) — a new
  `MeasureValue {value, n_students}` model, deliberately **not** `CountCell`: findings
  have no suppressed state because sub-floor candidates never publish. This is a **third
  floor-application path**; `aggregate.py`'s module docstring currently claims
  `floored_count()` and `_summary()` are the only two, and must be amended.
- New footnotes: `trend_method` (candidate pool, tests, BH family, thresholds —
  versioned with the numbers, per the footnote philosophy), `per_week_rate` (rate
  normalization + in-progress caveat), `cohort_turnover` (*"Each semester draws a
  largely different cohort of students; a shift between semesters may reflect who
  enrolled rather than a change in behavior."*). Findings inherit relevant existing
  footnotes from their source measures (`language_heuristic`, `multi_label`,
  `label_provenance`, `bachelor_onboarding` — which covers the narrower fact that the
  bachelor cohort exists only from 2025-05-16 — and `chat_fragmentation`).
- Titles are template-generated from pinned measure names — no text derived from chat
  content, so **no D-33-style operator review is required** (state in D-49).

## Tasks

### T-1: Contract models + schema export — DONE
**Files:** `pipeline/statsboteval_pipeline/contract.py`, `schema/aggregates.schema.json`,
`dashboard/src/lib/aggregates.gen.ts`
The regenerated schema is **+285 / −0 lines** — the bump is provably additive, which is
what earns the same `v1/` blob prefix under invariant 5.
The models above; `SCHEMA_VERSION` → `1.3.0`. Add `"trends"` to the hardcoded tuple in
`Aggregates._per_window_maps()` (`contract.py:398-403`) or the "per_window references a
known window" check silently skips the new section. Update
`pipeline/tests/test_contract_topics.py:56` (asserts `1.2.0`) and
`pipeline/tests/factories.py`. Regenerate schema
(`python -m statsboteval_pipeline.export_schema`) and TS types (`npm run gen:types`).
Extend `docs/aggregates-contract.md` with a §7.6 normative block, following the §8
precedent (header naming the schema version, italic provenance note citing D-49).
**Note:** §10 has no version-history block — provenance is recorded inline in the
changed section. Follow that precedent rather than inventing a changelog.

### T-2: Stats helpers (no new dependencies) — DONE
**Files:** `pipeline/statsboteval_pipeline/stats.py` (new), `tests/test_stats.py`

**Module split, decided during implementation.** The helpers live in `stats.py`, not
`trends.py`, because `build_trends` needs the type-2 median estimator and the Bergmann
user typology that `aggregate.py` also uses — and `aggregate.py` imports `trends.py`, so
reaching back into it would be circular. `stats.py` sits below both:
`stats.py` ← `trends.py` ← `aggregate.py`. `quantile_type2` and `classify_user` moved out
of `aggregate.py` into it, which also guarantees the median compared on Trends is the same
estimator the Engagement tab publishes rather than a second implementation of it.

`trends.py` reads the message/session structures through `Protocol` classes
(`MessageLike`, `SessionLike`) instead of importing `_Message`/`_Session`, which keeps the
dependency one-directional and documents exactly which fields trends depends on.
Hand-rolled, matching the `_quantile_type2` precedent (`aggregate.py:128-134`) — the
pipeline has no numpy/scipy and is not gaining any. Two-proportion z (pooled),
Mann–Whitney U normal approximation with tie correction, Benjamini–Hochberg,
rank-biserial effect size. Unit-test each against published worked examples (pinned
expected values), so correctness doesn't rest on scipy parity. This is a stricter
convention than `_quantile_type2` currently enjoys (which is covered only indirectly
through document assertions) and is the stated justification for hand-rolling.

### T-3: Candidate extraction + selection — DONE
**Files:** `pipeline/statsboteval_pipeline/trends.py` (new), `aggregate.py`, `tests/test_trends.py`
`build_trends(msgs, sessions, registrations, positives, windows, axis, floor_n, …)`
reuses the in-memory `_Message`/`_Session` structures rather than re-querying DuckDB.
Topic `positives` (`aggregate.py:442`) is currently local to the
`if classification_version is not None:` block and must be hoisted to be reachable.
Implements the pairing table, the tiered candidate pool, the gate, the ranking, and
all_time trajectories. Called at the end of `build_aggregates`; topics candidates only
when `classification_version` is set. Tiers and thresholds live as module constants
beside the bin edges (`aggregate.py:72-75`).

### T-4: `preview-trends` CLI + threshold calibration — DONE
**Files:** `pipeline/statsboteval_pipeline/cli.py`, `trends.py`
A read-only subcommand (verb-first, matching `generate-themes`/`freeze-themes`) that
opens the corpus, builds the same in-memory structures, runs candidate extraction for
every window, and prints the **full pre-selection candidate table**: tab, measure, kind,
tier, both sides' value and `n_students`, effect size, raw p, BH-adjusted p, which gate
it failed (if any), and what would have been published. No aggregation output, no blob
write, no publish. Keep `cli.py`'s function-local import discipline.

Run it once against the real corpus, pin the magnitude thresholds from what it shows,
and record the numbers in D-49. It stays in the tool afterwards: every publish is a
manual operator run, so a standing way to see *what almost made it* before publishing is
worth its small surface.

**Calibration pass, 2026-07-30** (`preview-trends --corpus data/corpus.duckdb --floor-n 3`,
one run, thresholds unchanged afterwards — the pinning discipline above allows one pass,
not iterative tuning). Only threshold values and candidate tallies are recorded here;
per-cell student counts stay local, since the table necessarily shows sub-floor sides.

| window | published | candidates | why the rest dropped |
|---|---|---|---|
| `all_time` | 5 | 60 | effect 44, cap 10, group 1 |
| `2025S` | — | — | earliest semester, `baseline: null` |
| `2025W` | 5 | 70 | effect 31, cap 20, floor 10, p 3, group 1 |
| `2026S` | 5 | 70 | effect 28, cap 25, floor 10, p 1, group 1 |
| `trailing_4` | **0** | 69 | floor 62, min-n 7 → **`insufficient_data`** |

Read-outs:

- **Thresholds are keepers.** No window is empty and none is padded with trivia; every
  filled window used all five slots on tier-1/2 material with tier 3 taking at most the
  last slot or two. Nothing is re-tuned.
- **The gate is deliberately permissive and the ranking does the work** — 10–25
  candidates per window earn verdict `cap` (passed everything, displaced). That is the
  design working as choice 6 intends: statistics decide admissibility, relevance decides
  the page. It also means threshold drift would change the tab slowly rather than
  cliff-edge, which is the safer failure mode.
- **`trailing_4` confirms choice 12 empirically.** 62 of 69 candidates fail the privacy
  floor in the July break weeks. Without `insufficient_data` the tab would have said "no
  meaningful shifts" for the whole summer — a false claim that a comparison ran.
- **The `people_rate` split earns its place**: `adoption-registrations-per-week` publishes
  in `2026S`, which it could not have done under the old shared `rate` min-n of 30.
- ⚠️ **Open editorial issue — taxonomy correlation.** In `2026S` the three published
  topic findings are one phenomenon seen twice: emergent *"Assumptions checking and
  diagnostics"* and method *"Assumption Testing, Diagnostics"* both fell ~11 pp, and
  emergent *"Model specification and selection"* is adjacent. The emergent and method
  taxonomies are independent label families over the same messages, so a single real
  shift can occupy 2 of the 3 topics slots. Not a correctness bug — two taxonomies
  agreeing is corroboration — but it costs slot diversity. See "Deliberately deferred".

### T-5: Publish guard + validation — DONE

**How it landed.** Most of the structural checks arrived early, as `model_validator`s on
`Aggregates` during T-1 (`_check_trends`) — floor on every side and trajectory point, the
`findings` cap and per-tab caps, registry membership for baseline and trajectory window
ids, trajectory-only-under-all_time, and the `insufficient_data` coherence rules.
`_iter_footnote_ids` already walks dumped sections generically, so finding footnotes
resolve with no new code.

What T-5 added is the *byte-level* half: `publish._assert_floor_respected`, a dump walk
asserting that **no `n_students` anywhere in the outgoing document** is below
`privacy_floor_n`. It is deliberately generic rather than trends-shaped — every model that
publishes an `n_students` does so only after a floor test, so the universal statement is
the true one and keeps holding when a later section adds a fourth such model. It reports
the JSON path to the offending cell, since an operator hitting this at publish time needs
coordinates. The property test (`test_floor_property.py`) now generates corpora and drives
`build_trends` over them; a companion deterministic test asserts the property is not
vacuous, because hypothesis shrinks toward small inputs and small corpora fail `min_n`
long before the floor is ever consulted.

`tests/factories.py` now carries a trends section, so round-trip, schema and guard tests
all exercise it.

<details><summary>Original plan text</summary>
**Files:** `pipeline/statsboteval_pipeline/contract.py`,
`pipeline/statsboteval_pipeline/publish.py`, contract tests
**Note the retarget:** the 2026-07-19 draft named `validate.py`, which is
classifier-MCC validation (D-30) and has nothing to do with documents. Structural
invariants belong on `Aggregates` as `model_validator`s beside
`_cross_document_consistency` (`contract.py:405-424`) — the only place with access to
both `windows` and `privacy_floor_n`. Anything needing a recursive dump walk goes in
`publish.py` beside `_assert_suppressed_bare`, raising `PublishGuardError`.

New checks: every finding side (and trajectory point) has `n_students ≥
privacy_floor_n`; `findings` length ≤ 5; ≤3 for topics and ≤2 per other tab;
`baseline.window_id` and trajectory `window_id`s exist in the registry; `trajectory`
only under `all_time`; `insufficient_data` is `false` whenever `baseline` is `null` or
`findings` is non-empty; every `footnote_ids` entry resolves (the existing
`_iter_footnote_ids` walk covers this for free). Extend the hypothesis property test
(`pipeline/tests/test_floor_property.py`): no generated corpus ever yields a finding
with a sub-floor side.

</details>

### T-6: Synthetic fixtures with planted shifts — DONE

**How it landed.** Shifts are keyed on `_phase_by_week`, which marks the *last semester on
the axis* as phase 1. That does two things: it lands the shift exactly on the boundary
Trends compares across, and it makes the planting inert on a one-semester axis. Every
`before` value is the constant the generator used pre-T-6, so the 8-week corpora the Phase
A tests were written against are byte-identical. Planted: German share 0.7 → 0.35,
messages per session (1,10) → (5,18), session gaps (1,15) → (3,30) minutes, and the first
method theme 0.35 → 0.65 (the other themes stay flat, so the fixture also exercises
candidates that correctly publish nothing). `run-synthetic --weeks` now defaults to **40**,
which always spans two semesters whatever today's date is.

**`seed_synthetic` now runs the real language detector.** It never did, so every synthetic
corpus was 100% `undetermined` and the Language tab rendered empty in the dev fixture —
a pre-existing defect T-6 surfaced by needing a language shift to be visible. Detection is
local and runs on every real corpus before aggregation, so running it here is the faithful
order; it also gives the fixture a genuine `undetermined` share that a hand-written mapping
would have had to invent.

**The two halves.** The pipeline fixture can only show a real corpus in one state at a
time, so it covers the live states (no-predecessor, semester pair, trailing pair,
trajectory, findings of every kind). The hand-authored dev fixture
(`dashboard/dev-fixtures/generate.mjs`) covers all five states in one document —
including the two the pipeline fixture cannot produce simultaneously, **zero findings**
("no meaningful shifts") and **`insufficient_data`** — plus both evidence markers and a
multi-footnote card. That file is what T-8 develops against.

⚠️ **Suite runtime went 113 s → 232 s.** Labelling dominates: `write_labels` measured at
~1.5 ms/row because DuckDB's Python `executemany` binds one row at a time (the engine
itself inserts 120 k rows in 0.02 s). Staging through a PK-less temp table halved it to
~720 µs/row and is what shipped; columnar `unnest`, batched multi-row `VALUES` and
explicit transactions were all measured and none beat it. The remaining cost is a DuckDB
Python-binding limit — the real fix is an Arrow/pandas ingestion path, which would mean a
new dependency and is **not** taken here. Consequence for the real pipeline: one
classification pass over today's corpus writes ~57 k label rows in ~40 s (was ~85 s).

<details><summary>Original plan text</summary>
**Files:** `pipeline/statsboteval_pipeline/fixtures.py`, fixture tests
**Bigger than it reads, and it blocks T-8.** `seed_synthetic` currently defaults to 8
weeks — one semester — and draws language share, session length, token size and label
probabilities from *time-invariant* distributions, so the corpus contains no planted
shift and no previous semester to compare against. Two semesters need ~30+ weeks.

The synthetic corpus must deterministically produce findings (plant at least a language
shift, an engagement shift and a topic shift between the last two semesters), so the tab
is developable and the E2E publish exercises every finding kind, both evidence tiers,
the trailing baseline, a trajectory, and the zero-findings + no-predecessor states.
FE dev serves `dashboard/dev-fixtures/aggregates.fixture.json` via
`NEXT_PUBLIC_DATA_SOURCE=fixture`; until that file has a `trends` key the tab renders
`SectionPending` forever.

</details>

### T-7: Dashboard — tab registration — DONE

Registered after Language with the editorial comment amended (rationale + date, per house
discipline). `onJumpToTab={setTab}` is threaded through the `panels` object literal; a
comment records why a function prop is safe here — `Dashboard.tsx` is the `"use client"`
entry point, so nothing below it crosses the boundary where props must be serializable.

`TrendsTab.tsx` landed as a shell that already resolves all four states correctly
(section absent → `SectionPending`; window absent → `WindowGap`; then the three published
states: no-predecessor, `insufficient_data`, zero findings). Findings currently render as
a plain list — **T-8 replaces that body** with `FindingCard`, the dynamic "Top N trends"
heading and its tooltip, evidence markers, footnote symbols and the trajectory sparkline.

Verified in the browser against `dev-fixtures/aggregates.fixture.json`: all four states
render, and a card's source-tab link switches tabs while preserving the window filter
(`?tab=language&window=2026S`).

<details><summary>Original plan text</summary>
**Files:** `dashboard/src/components/Dashboard.tsx`
`{ id: "trends", label: "Trends" }` appended after `language`, **amending the editorial
tab-order comment** (`Dashboard.tsx:18-20`) with the rationale and date — the house
discipline is a stated rationale, not a silent append. Pass an `onJumpToTab` callback
(net-new; `setTab` threaded through the `panels` object literal) so a finding card can
switch to its source tab.

**Naming:** `TrendChart`, `TrendSeries` and `trendTableRows` already exist and mean
"weekly line chart". To avoid a permanent readability tax without renaming shipped code,
the new components are **`TrendsTab.tsx`** (matches the label and its `TopicsTab`
siblings) and **`FindingCard.tsx`** — no confusing `TrendFindingCard`/`TrendChart` pair.

</details>

### T-8: Dashboard — TrendsTab + FindingCard — DONE

Built as specified. Two judgment calls worth recording:

- **The delta is not colored by valence.** The stat-tile convention tints a delta by
  direction × whether up is good, but almost nothing here has a good direction — a rising
  German share is neither better nor worse — so green/red would editorialize a
  measurement. Direction is carried by an arrow and the sign instead.
- **The trajectory sparkline is hand-rolled SVG, not recharts.** Two to four points, no
  axes, and one renders per card; a chart library and a `ResponsiveContainer` per card
  buy nothing (D-28 primitives-on-demand). Built against the dataviz guidance: single
  series so no legend, 2px accent line, r=4 markers with a 2px surface ring, earlier
  points in the de-emphasis gray with the latest in the accent, only the first and last
  directly labelled, and every value available in the `DataTable` twin. Palette checked
  with the validator — accent `#0063a6` vs de-emphasis `#898781` on the card surface:
  CVD ΔE 16.0, normal-vision 19.5, contrast ≥ 3:1.

`formatPair` was added because `formatStat` drops the decimal on whole numbers, which
rendered one measure two ways in the same sentence ("16 → 23.1") — a change of precision
reading as a change of value.

Verified in the browser across all five windows: five cards under a dynamic "Top 5 trends"
heading, "Top 2 trends" with trajectories under all_time, both evidence markers, the
per-card footnote symbols and `Note.` lines, and all three empty states.

<details><summary>Original plan text</summary>
**Files:** `dashboard/src/components/tabs/TrendsTab.tsx`,
`dashboard/src/components/cells/FindingCard.tsx`
`PanelIntro` question: **"How is usage changing over time?"** Deck (per choice 10):
*"Only measures that changed enough to stand out from normal variation are listed —
anything that stayed stable is left out."*

Findings group under a **dynamic heading — "Top 5 trends", "Top 3 trends"** — matching
the number actually shown, with a tooltip explaining the selection (most decision-
relevant changes, among those large and consistent enough not to be noise). Use the
`TopicRowTip` hover/focus pattern (`useId` + `role="tooltip"` + `aria-describedby`), not
a tooltip library — per D-28's primitives-on-demand rule.

States: section absent → `SectionPending` (`what="Trends (the trends section)"`);
`baseline: null` → explanatory empty state naming the selected window;
`insufficient_data` → "Too little activity in this period to compare" plus the likely
cause (*"this window may fall in a semester break, the Christmas closure, or an exam
period"*); empty `findings` otherwise → "No meaningful shifts between {window} and
{baseline}".

Card: title, source-tab badge (clickable via `onJumpToTab`), before/after values with
delta chip + direction, evidence marker with `method` in the tooltip, footnote symbols
via `resolveFootnotes`/`symbolsFor` rendered in `ChartCard`'s `Note.` line; under
all_time, a small inline per-semester slope/sparkline (consult the dataviz skill when
building it) with its `DataTable` twin. No `suppressionKey` — findings have no
suppressed state. Baseline context line under the intro: "Compared with Winter semester
2025/26" / "Compared with the preceding 4 weeks (2026-W21–W24)" / "(in progress — volume
measures compared per covered week)" via `isInProgress` (`lib/windows.ts:23-26`).

Per `dashboard/AGENTS.md`: this is Next 16.2.10 / React 19.2.4 — read the relevant guide
in `node_modules/next/dist/docs/` before writing client-component code.

</details>

### T-9: Docs, decision record, rollout — DONE (docs); **publish is the operator's**

**D-49 recorded** in `docs/decisions.md`. `docs/aggregates-contract.md` carries the
normative §7.6 and §11 now states the byte-level floor walk. `CLAUDE.md` and `README.md`
name the sixth tab and mark it built-but-unpublished.

**Rollout — steps 1–2 done, 3–5 are a manual operator run:**

1. ✅ Synthetic E2E: `run-synthetic` at the 40-week default publishes a trends section
   through the guard, asserted in `test_cli.py`.
2. ✅ Real-corpus dry run: `preview-trends` against `data/corpus.duckdb` (the T-4
   calibration pass) — every window produces a sensible deck.
3. ⬜ Re-aggregate the existing corpus and write the document locally:
   ```
   pipeline/.venv/bin/python -m statsboteval_pipeline.cli run-weekly \
       --corpus data/corpus.duckdb --env-file .env --skip-classify --out /tmp/aggregates.json
   ```
   No re-classification is needed — trends reads the labels already in the corpus.
4. ⬜ Publish (schema 1.3.0, same `v1/` prefix). A 1.2.0 reader ignores the new section.
5. ⬜ FE redeploy (D-26 image rebuild).

Order is safe either way: an old document under the new dashboard renders
`SectionPending`, and a new document under the old dashboard is simply not read.

<details><summary>Original plan text</summary>
**Files:** `docs/aggregates-contract.md`, `docs/decisions.md`
Record **D-49** (design + both owner-choice rounds, incl. the census framing, the
usefulness-first ranking with its tier table, the BH family choice, the a-priori-tiers /
post-dry-run-thresholds split with the calibrated numbers, and the no-review-needed
rationale for titles). Rollout: synthetic E2E → re-aggregate the existing real corpus →
publish (1.3.0, same `v1/` prefix; a 1.2.0 reader ignores the section — invariant 5) →
FE redeploy (D-26 image rebuild). Deployment order is safe in both directions: an old
document under the new FE renders `SectionPending`.

## What today's real corpus will produce

Semester rule (`windows.py:35-45`): SS = Mar 1–Jun 30, WS = Oct 1–Jan 31; Feb and
Jul–Sep are break weeks belonging only to `all_time`/`trailing_4`. Data runs March 2025
→ 2026-07-17, so on a publish run today:

- `2025S` — earliest → `baseline: null`, empty state.
- `2025W` — baseline `2025S`. Crosses the 2025-05-16 bachelor onboarding →
  `bachelor_onboarding` applies on top of `cohort_turnover`.
- `2026S` — baseline `2025W`. **Complete** (ended Jun 30), not in progress.
- `trailing_4` — currently the **July break weeks**: near-zero volume, likely sub-floor
  on both sides, so expect `insufficient_data` (not "no meaningful shifts") until
  October. Roughly a third of the year sits in break weeks, so this is the normal
  off-season state of that window, not a defect.
- `all_time` — a trajectory of exactly **3 points**.

Worth setting expectations before the first publish: the in-progress caveat has no live
case until 2026W opens in October, and the trajectory sparkline is drawing three points.

</details>

## Deliberately deferred

- Cochran–Armitage trend test for all_time trajectories (endpoint test v1).
- Same-elapsed-weeks clipping for in-progress semesters (per-week rates chosen; the
  clipping alternative is recorded here in case mid-semester rates prove misleading).
- `by_status` (bachelor/master) trend splits — additive later, suppression-heavy now.
- Publishing stability ("topic mix unchanged") as a positive finding — see choice 10.
- **A label-family sub-cap inside the topics allowance** (e.g. ≤2 of the 3 topics slots
  from any one of emergent / method / deductive / software), which would break up the
  emergent-vs-method duplication the T-4 calibration surfaced. Deferred pending an owner
  call: the alternative reading is that two independent taxonomies agreeing is the
  strongest signal on the page and should be allowed to say so twice.

# Trends tab — pipeline-computed period comparisons (design + execution plan)

**Date:** 2026-07-19 · **Status:** planned (owner-approved design choices folded in)
**Decisions to record at implementation:** D-45 (this design) · **Contract:** additive
minor bump → schema **1.3.0**, same `v1/` blob prefix

## Goal

A sixth dashboard tab, **Trends**, to the right of Language. For the selected window it
answers *"what changed, compared with the previous period?"* with a small set of
pipeline-selected findings (at most 5, possibly 0) drawn from the measures behind all
five existing tabs. The comparison pairing follows the window picker:

| selected window | baseline |
|---|---|
| semester (e.g. 2026W) | previous semester by chronology (2026S) |
| earliest semester | none — explanatory empty state ("no earlier period to compare") |
| `trailing_4` | the 4 complete weeks preceding the trailing window (hidden baseline, not a picker entry) |
| `all_time` | per-semester trajectory: each finding shows its measure across every semester |

## Why the pipeline computes trends (not the dashboard)

Contract invariant 4 — the client never re-aggregates — already decides most of this:
selecting "meaningful" differences is analysis, not display math. But the stronger
reason is statistical: the raw per-student data exists **only locally**, so real
hypothesis tests (which need per-student/per-session observations, not floored
aggregates) can only run in the pipeline. The dashboard receives finished findings and
renders them; the file remains the complete statement of everything the dashboard can
show.

## Owner-approved design choices (2026-07-19 session)

1. **`trailing_4` compares against the preceding 4 complete weeks** (`axis[-8:-4]`),
   embedded in the section as a baseline reference — no new window-registry entry. If
   the axis has fewer than 8 weeks, baseline is `null` (empty state).
2. **`all_time` shows per-semester trajectories** (e.g. German share 68% → 61% → 52%),
   not a two-point comparison. Break weeks (Feb, Jul–Sep) drop out naturally because
   semesters partition the published axis.
3. **Volume measures compare as per-covered-week rates** (messages/week, sessions/week,
   active students/week, registrations/week) so unequal window lengths and the
   in-progress current semester stay comparable. Shares and medians compare as-is. A
   new `per_week_rate` footnote carries the in-progress caveat (within-semester
   seasonality is acknowledged, not corrected).
4. **Formal tests in the pipeline, plain language in the UI.** Two-proportion z for
   shares, Mann–Whitney U (normal approximation, tie-corrected) for per-session
   measures, Benjamini–Hochberg correction across the full candidate set per window.
   The card shows an effect size and a qualitative evidence marker; the method name is
   published per finding (tooltip/footnote), p-values are not shown on cards. Since
   this is a census of users rather than a sample, tests are framed as a guard against
   over-reading noise, not as inference to a population — the thesis writeup states
   this framing.

## Candidate measure pool (pinned in code, one place)

Each candidate is (tab, measure, kind, test). Kinds: `rate` (per covered week),
`share` (proportion of a window's messages/sessions/users), `median` (per-session
distributions).

| tab | candidates |
|---|---|
| adoption | messages/week, sessions/week, active students/week, registrations/week (rates); one-time-user share of active students (share) |
| engagement | median messages per session, median session duration (medians, Mann–Whitney) |
| timing | share of messages by pinned daypart (morning 6–12, afternoon 12–18, evening 18–24, night 0–6) and weekend share — most-shifted one enters ranking |
| language | German share and English share of messages (share; most-shifted enters) |
| topics | per-label share of the window's messages for deductive categories + emergent themes (share, one candidate per label; method/software themes excluded from ranking to keep the pool focused — revisit if wanted) |

**Selection rule** (per window, deterministic): a candidate publishes only if
(a) both sides' distinct contributing students ≥ `privacy_floor_n` — sub-floor
candidates are silently dropped, never rendered as "suppressed";
(b) minimum n per side (pinned, e.g. ≥30 messages for shares);
(c) BH-adjusted p < 0.05 → evidence `"robust"`, else unadjusted p < 0.05 → `"indicative"`;
(d) minimum effect size (pinned per kind at implementation, with the fixture — like
bin edges: e.g. ≥5 pp for shares, ≥25% relative change for rates).
Survivors rank by normalized effect size (|log rate ratio| for rates, |Δpp| for
shares, rank-biserial correlation for medians), **at most 2 findings per source tab**
(diversity rule), cap 5. For `all_time`, significance comes from the endpoint test
(first vs last semester) and the full per-semester trajectory is published;
a trend test (Cochran–Armitage) is a noted upgrade path, not v1.

Rates, shares, and medians derived from ≥N-student groups pass the same privacy
reasoning as existing cells; each published side carries its `n_students` (≥ floor,
publish-guard-enforced), keeping every number citable.

## Contract additions (schema 1.3.0, additive)

```json
"trends": { "per_window": { "<window_id>": {
    "baseline": { "kind": "window", "window_id": "2026S" }
              | { "kind": "weeks", "from": "2026-W21", "through": "2026-W24" }
              | { "kind": "trajectory" }
              | null,                          // no predecessor → FE empty state
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

- Every registry window gets an entry; `baseline: null` + empty `findings` encodes "no
  predecessor" explicitly (the FE must distinguish it from "no meaningful shifts").
- Finding values are floats (rates/shares/medians are derived numbers) — a new
  `MeasureValue {value, n_students}` model, deliberately **not** `CountCell`: findings
  have no suppressed state because sub-floor candidates never publish.
- New footnotes: `trend_method` (candidate pool, tests, BH, thresholds — versioned with
  the numbers, per the footnote philosophy), `per_week_rate` (rate normalization +
  in-progress caveat). Findings inherit relevant existing footnotes
  (`language_heuristic`, `multi_label`, `label_provenance`, `bachelor_onboarding`,
  `chat_fragmentation`) from their source measures.
- Titles are template-generated from pinned measure names — no text derived from chat
  content, so **no D-33-style operator review is required** (state in D-45).

## Tasks

### T-1: Contract models + schema export
**Files:** `pipeline/statsboteval_pipeline/contract.py`, `schema/aggregates.schema.json`,
`dashboard/src/lib/aggregates.gen.ts`
`TrendsSection`, `TrendsWindow`, `BaselineRef` (tagged union), `TrendFinding`,
`MeasureValue`, `TrajectoryPoint`; `SCHEMA_VERSION` → `1.3.0`. Regenerate schema
(`python -m statsboteval_pipeline.export_schema`) and TS types (`npm run gen:types`).
Extend `docs/aggregates-contract.md` with a §7.6 normative block; note the bump in §10's
history.

### T-2: Stats helpers (no new dependencies)
**Files:** `pipeline/statsboteval_pipeline/trends.py` (new), tests
Hand-rolled, matching the `_quantile_type2` precedent: two-proportion z (pooled),
Mann–Whitney U normal approximation with tie correction, Benjamini–Hochberg, rank-
biserial effect size. Unit-test each against published worked examples (pinned
expected values), so correctness doesn't rest on scipy parity.

### T-3: Candidate extraction + selection
**Files:** `trends.py`, `pipeline/statsboteval_pipeline/aggregate.py`
`build_trends(msgs, sessions, registrations, windows, axis, floor_n, …)` reuses the
in-memory `_Message`/`_Session` structures — refactor them (and topic `positives`) to be
shareable rather than re-querying DuckDB. Implements the pairing table, the candidate
pool, the selection rule, and all_time trajectories. Called at the end of
`build_aggregates`; topics candidates only when `classification_version` is set.
Pinned thresholds live as module constants beside the bin edges.

### T-4: Publish guard + validation
**Files:** `pipeline/statsboteval_pipeline/validate.py`, contract tests
New checks: every finding side (and trajectory point) has `n_students ≥
privacy_floor_n`; `findings` length ≤ 5; ≤2 per tab; `baseline.window_id` and
trajectory `window_id`s exist in the registry; `trajectory` only under `all_time`;
every `footnote_ids` entry resolves. Extend the hypothesis property test: no generated
corpus ever yields a finding with a sub-floor side.

### T-5: Synthetic fixtures with planted shifts
**Files:** `pipeline/statsboteval_pipeline/fixtures.py`, fixture tests
The synthetic corpus must deterministically produce findings (e.g. plant a language
shift and an engagement shift between the last two semesters), so the tab is
developable and the E2E publish exercises every finding kind, both evidence tiers, the
trailing baseline, a trajectory, and the zero-findings + no-predecessor states.

### T-6: Dashboard — tab registration
**Files:** `dashboard/src/components/Dashboard.tsx`
`{ id: "trends", label: "Trends" }` appended after `language` (per the tab-order
comment discipline: note the editorial rationale). Pass an `onJumpToTab` callback so a
finding card can switch to its source tab.

### T-7: Dashboard — TrendsTab + finding card
**Files:** `dashboard/src/components/tabs/TrendsTab.tsx`,
`dashboard/src/components/cells/TrendFindingCard.tsx`
`PanelIntro` question: "How is usage changing over time?" States: section absent →
`SectionPending`; `baseline: null` → explanatory empty state naming the selected
window; empty `findings` → "No meaningful shifts between {window} and {baseline}".
Card: title, source-tab badge (clickable via `onJumpToTab`), before/after values with
delta chip + direction, evidence marker with `method` in the tooltip, footnote symbols
via the existing registry mechanics; under all_time, a small inline per-semester
slope/sparkline (consult the dataviz skill when building it). Baseline context line
under the intro: "Compared with Summer semester 2026" / "Compared with the preceding 4
weeks (2026-W21–W24)" / "(in progress — volume measures compared per covered week)"
via `isInProgress`.

### T-8: Docs, decision record, rollout
**Files:** `docs/aggregates-contract.md`, `docs/decisions.md`
Record D-45 (design + owner choices above, incl. the census framing and the
no-review-needed rationale for titles). Rollout: synthetic E2E → re-aggregate the
existing real corpus → publish (1.3.0, same `v1/` prefix; a 1.2.0 reader ignores the
section — invariant 5) → FE redeploy (D-26 image rebuild). Deployment order is safe in
both directions: an old document under the new FE renders `SectionPending`.

## Deliberately deferred

- Method/software-theme candidates in the ranking pool (excluded v1; revisit).
- Cochran–Armitage trend test for all_time trajectories (endpoint test v1).
- Same-elapsed-weeks clipping for in-progress semesters (per-week rates chosen; the
  clipping alternative is recorded here in case mid-semester rates prove misleading).
- `by_status` (bachelor/master) trend splits — additive later, suppression-heavy now.

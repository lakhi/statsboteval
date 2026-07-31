# Aggregates-file contract — v1

**Status: v1 locked 2026-07-05** (aggregates-contract design session; closes the D-19 "no
code until the contract is locked" gate; decisions D-24/D-25). Normative description of the
versioned JSON document the weekly pipeline publishes to Azure Blob and the FastAPI API +
Next.js dashboard consume. Machine-readable artifacts derive from this design: **pydantic
models in `pipeline/` are the single source of truth for shapes**, exported as
`schema/aggregates.schema.json` (committed artifact, drift-checked in CI), from which the
dashboard's TypeScript types are generated. If prose and models ever disagree on a *shape*,
the models win and this doc gets fixed; for *semantics* (what a value means, when it may be
published) this doc is the law. Implemented: models in
`pipeline/statsboteval_pipeline/contract.py`; artifact regenerated via
`python -m statsboteval_pipeline.export_schema`; drift-checked by
`pipeline/tests/test_schema_export.py`.

## 1 · Scope and consumers

One JSON document per weekly publish, containing **every number the Phase A dashboard can
display** — pre-aggregated, privacy-floored, cohort-wide. Consumers:

- **API** (`api/`): serves the latest document verbatim (`GET /api/v1/aggregates`),
  validates it against the exported schema on read, caches it. The API never reshapes the
  document — blob content and API response body are the same contract.
- **Dashboard** (`dashboard/`): renders the document. It selects, formats, and divides
  published numbers; it never re-aggregates them (§2, invariant 4).
- **Pipeline tests / publish guard**: assert the invariants below on every candidate file.

## 2 · Binding invariants

1. **Only privacy-floored aggregates exist in the file.** A cell is published iff the
   number of **distinct students contributing to it** is `0` or `≥ privacy_floor_n`
   (working value 3, D-24). The test is always on students, never on the value's
   magnitude: 100 messages from 2 students is suppressed; 0 messages from 0 students is
   published as `0`.
2. **Suppressed ≠ zero ≠ absent.** `{"status":"suppressed"}` = 1..N−1 students, number
   withheld (a suppressed cell carries **no value field at all**). `{"status":"ok",
   "value":0}` = measured, nothing happened. Absent = outside the published range or an
   optional section not computed — never used to encode suppression or zero.
3. **Complete ISO weeks only.** The finest published granularity is the ISO week (Mon–Sun);
   only weeks fully elapsed at extract time appear. There is no partial-week state.
4. **The client never re-aggregates.** Distinct counts don't sum and suppression destroys
   additivity, so every (metric × window) the dashboard shows is its own pre-aggregated,
   independently-floored cell. Client-side arithmetic on published cells is limited to
   *display math* (e.g. shares as division of two published cells).
5. **Readers ignore unknown fields, tolerate absent optional sections.** This single rule
   is what makes all evolution within a major version safe (§10).
6. **Structurally no chat text.** No field in the schema carries message content; the
   publish guard rejects any field not in the schema.

## 3 · Document layout

```
{ metadata fields }            §4   — schema_version, generated_at, …
"windows":   [ … ]             §6.1 — window registry (all_time, semesters, slices)
"footnotes": { … }             §6.2 — caveat registry, referenced by id
"sections":  {                 §7   — one key per dashboard view
    "temporal_usage": … , "usage_context": … , "sessions": … ,
    "per_student": … , "language": … , "trends": …  // Phase B adds "topics" (§8)
}
```

All keys snake_case. Week ids are ISO 8601 `"YYYY-Www"` (e.g. `"2025-W11"`); dates are
`"YYYY-MM-DD"`; timestamps are RFC 3339 UTC (`"…Z"`).

## 4 · Metadata block

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-07-06T05:12:33Z",
  "data_through_week": "2026-W27",
  "data_through_date": "2026-07-05",
  "first_week": "2025-W11",
  "privacy_floor_n": 3,
  "label_versions": { "language": "lang-heuristic-v1" },
  "timezone": "Europe/Vienna",
  "data_provenance": "synthetic",
  "pipeline_version": "0.1.0"
}
```

| field | semantics |
|---|---|
| `schema_version` | Semver. Minor/patch = additive only; **major = breaking** and moves to a new blob prefix (§9), so old readers never fetch a shape they can't parse. |
| `generated_at` | Publish timestamp (UTC). |
| `data_through_week` / `data_through_date` | Last complete ISO week in the file / its Sunday as a plain date. Originally published so no reader would need ISO-week math in TS; **partly superseded by D-48** — the dashboard header shows a *window-scoped* range, and only `coverage` (week ids) exists for every window kind, so `isoWeekMonday` in `dashboard/src/lib/format.ts` now does the conversion client-side. It mirrors `week_monday` in `contract.py`; keep the two in step. `data_through_date` remains the pinning check: Sunday of `data_through_week` must equal it. |
| `first_week` | Start of the dense weekly axis. With `data_through_week` it makes "absent" exact: weekly series contain one entry per week in `[first_week, data_through_week]`, nothing else. |
| `privacy_floor_n` | The N in force for this file (D-24: 3). Declared so no reader hardcodes it; a change is config + republish, not a schema change. |
| `label_versions` | Map **label domain → active version**, one active version per domain (D-07). Phase A: `language` (`lang-heuristic-v1`). Phase B adds `classification` (`statsboteval-v1` \| `bergmann-v1`). Metrics that involve no labels appear in no domain. |
| `timezone` | IANA zone used for hour/weekday bucketing of `created_at` in heatmaps (DST-correct local time). |
| `data_provenance` | `"synthetic"` \| `"production"`. The file self-labels; the dashboard's synthetic-data banner is driven by this field, not by deploy config. Synthetic files exist permanently (fixtures, E2E publishes). |
| `pipeline_version` | Version of the pipeline code that computed the numbers. |

**The version triad** — three fields answer three different questions: `schema_version` =
*how do I read this file* (shape); `pipeline_version` = *which code computed the numbers*
(a binning bug-fix changes numbers, not shape); `label_versions` = *which labeler labeled
the labeled subsets*. In a thesis about automated classification, "did the data, the code,
or the classifier change?" must always be answerable from the file alone.

## 5 · Shared cell taxonomy

Five primitives; every section is composed exclusively of these. Dashboard mapping:
KPI tile ← `CountCell` · trend chart ← `WeeklySeries` · distribution chart ← `Histogram` ·
stat callout ← `SummaryStats` · activity grid ← `HeatmapGrid`.

```ts
// Notation: generated-TypeScript view of the pydantic models.
type WeekId = string;      // "YYYY-Www", §3
type FootnoteId = string;  // key into the footnotes registry, §6.2

type CountCell = { status: "ok"; value: number }   // value ≥ 0 integer
               | { status: "suppressed" };          // no value field exists

type WeeklyEntry  = { week: WeekId; cell: CountCell };
type WeeklySeries = { series: WeeklyEntry[]; footnote_ids?: FootnoteId[] };
// Dense: exactly one entry per week in [first_week, data_through_week].

type Histogram = {
  unit: string;                       // what a bin counts: "sessions" | "messages" | …
  bins: { lo: number; hi: number | null; cell: CountCell }[];  // hi:null = open top bin
  n_total: CountCell;                 // published explicitly — suppressed bins make the
  summary?: SummaryStats;             // total un-derivable from surviving bins
  footnote_ids?: FootnoteId[];
};
// Bin edges live in the DATA, not the schema: re-binning = pipeline config change +
// pipeline_version bump. Bin cell counts things (unit); the floor tests the distinct
// students behind them. All binned quantities are integers (durations rounded to whole
// minutes), so bins are inclusive [lo, hi], non-overlapping, in ascending order.

type SummaryStats = { status: "ok"; n_students: number;
                      median: number; p25: number; p75: number;
                      mean?: number; sd?: number }   // filled where the Bergmann
                  | { status: "suppressed" };        // reference reports them
// All-or-nothing: published only when ≥ N distinct students stand behind the
// distribution. No partially-suppressed summaries. n_students always accompanies —
// a median without its n is uninterpretable and not citable next to Bergmann's table.

type HeatmapGrid = {
  cells: { dow: number; hour: number; cell: CountCell }[];  // dow 1–7 (ISO, Mon=1),
  footnote_ids?: FootnoteId[];                              // hour 0–23 local time
};
// Dense: all 168 cells always present (quiet = ok:0, small = suppressed; "absent"
// never occurs inside a window). Bucketing in metadata.timezone.
```

## 6 · Registries

### 6.1 Windows

Named week-sets that every `per_window` rollup keys on. One registry covers all-time,
semesters, and slices of a semester's closing stretch; UI presets map onto it completely
(current semester = semester window with the latest coverage; previous semesters = older
ones; last month and last week = that semester's `.last4` and `.last1`).

```json
"windows": [
  { "id": "all_time",   "kind": "all_time", "label": "All time", "short_label": "All time",
    "coverage": { "from": "2025-W11", "through": "2026-W27" } },
  { "id": "2026S",      "kind": "semester", "label": "Summer semester 2026",
    "short_label": "Whole semester",
    "start_date": "2026-03-01", "end_date": "2026-06-30",
    "weeks": ["2026-W10", "…", "2026-W26"],
    "coverage": { "from": "2026-W10", "through": "2026-W26" } },
  { "id": "2026S.last4", "kind": "semester_slice", "label": "Final 4 weeks · SS 2026",
    "short_label": "Final 4 weeks", "parent_window_id": "2026S",
    "weeks": ["2026-W23", "2026-W24", "2026-W25", "2026-W26"],
    "semester_weeks": [14, 17],
    "coverage": { "from": "2026-W23", "through": "2026-W26" } }
]
```

- `weeks` = full membership; `coverage` = membership clipped to
  `[first_week, data_through_week]`. For the running semester `coverage.through` <
  last member week — that is how the dashboard renders "(in progress)" with no date math.
- **Semester membership rule: a week belongs to the semester containing its Thursday**
  (ISO 8601's year rule applied to semesters). Deterministic; no week in two semesters;
  break weeks (Feb, Jul–Sep) belong to none and surface only in `all_time`.
- Semester generation is a **pipeline rule, not config**: SS = 1 Mar–30 Jun, WS = 1 Oct–
  31 Jan (following year), ids `"YYYYS"`/`"YYYYW"` by starting calendar year, for every
  semester intersecting the data range. Calendar knowledge lives in Python only.
- **Semester slices** (1.8.0, D-56): each semester publishes `{id}.last4` and `{id}.last1`
  — the last up-to-four and the last one of its *covered* weeks. `.last4` is omitted when
  the semester has a single covered week, where it would duplicate `.last1`.
  - The `4` in the id names the rule's cap, not a fact about the window. Early in a term
    the window holds fewer weeks, and the **label states the count it actually holds**
    ("Latest 3 weeks").
  - Labels are state-dependent: **`Latest` while the parent semester is in progress,
    `Final` once it has ended.** The same week-set answers "how is it going" for a running
    term and "how did it close" for a finished one.
  - `semester_weeks` is the `[first, last]` 1-based teaching-week span **within the
    parent's full membership, never its coverage**. Published for alignment, rendered
    nowhere: SS terms run 17 weeks and WS terms 18, so "final 4 weeks" spans different
    teaching weeks on each side of a cross-semester comparison.
  - Ids are stable forever once a semester ends, which `trailing_4` never was — a link to
    `?window=2026S.last1` resolves to the same span in every later publish.
  - `enrollment` is **not** keyed by slices; a reader follows `parent_window_id` to the
    parent's headcount (§6.3). Reach then means the share of that term's cohort active in
    those weeks, which `reach_window_scope` states.
- `short_label` is what a reader sees where context already names the parent (inside the
  picker's group heading); `label` is self-contained, for sentences. **Optional on
  `all_time` and `semester`** so a document published before 1.8.0 stays valid under this
  schema — the API validates every blob it fetches against the schema it ships with (§11),
  so a required field would make deploying before publishing a 500 rather than a degraded
  render. Readers fall back to `label`.
- Every key of every `per_window` object must exist in this registry (validated).
- **Not every registry window carries every section.** `sections.trends` covers semesters
  and `all_time` only; slices are excluded from the trends pass (D-56) until slice pairing
  is decided. Readers already tolerate a missing `per_window` key (invariant 5).

### 6.2 Footnotes

Per-metric caveat metadata (pinned input), normalized: texts live once in a registry,
metrics reference by id via `footnote_ids`. Caveats are versioned *with the numbers they
govern* — an archived blob still carries the exact warnings shown beside its figures.
Initial catalog:

| id | gist |
|---|---|
| `chat_fragmentation` | credit-limit UI nudges new-chat clicks; conversation counts may overstate distinct dialogues (D-08) |
| `bachelor_onboarding` | bachelor cohort exists only from 2025-05-16; cross-boundary trends partly reflect composition |
| `language_heuristic` | language detected by local heuristic (`lang-heuristic-v1`); short/mixed messages may misclassify |
| `user_class_definitions` | the class rules in days, per Bergmann et al. (2026); states that `frequent` is a subset of monthly (schema 1.4.0 — D-50) |
| `user_class_window` | classes are computed from in-window activity only, so a sub-30-day window cannot contain a monthly user (schema 1.4.0) |
| `retention_definition` | new = first-ever message inside the window, returning = wrote before it, the two summing to active users; the baseline includes pre-`axis_start` pilot use, and in `all_time` "returning" is the pilot cohort (schema 1.4.0) |
| `signup_activation` | "sent at least 1 msg" is window-scoped on both sides; a late signup counts in the window they first wrote in (schema 1.4.0) |
| `status_multi` | a BA→MA transitioner active on both sides of the boundary is counted under both levels, so student counts can exceed the total (schema 1.4.0) |
| `reach_window_scope` | reach divides by the enrolled cohort of the semester the window belongs to, so in a slice it is the share of that cohort active in those weeks, not over the term (schema 1.8.0 — D-56) |
| `daypart_definition` | Vienna local; four **equal** six-hour blocks (00–06, 06–12, 12–18, 18–24) so bar length is directly comparable; a chat crossing a boundary counts in both (schema 1.6.0 — D-54) |
| `semester_week_alignment` | week 1 is the semester's first ISO week (Thursday rule); cohorts and course structure differ between semesters, so compare shape not height; an in-progress semester ends where the data does (schema 1.6.0 — D-54) |
| `duration_definition` | session duration = last − first server `created_at` in the session; single-message sessions = 0 |
| `weeks_active_window` | weeks active counts only the weeks inside the selected window, so the shares are not comparable between windows of different length (schema 1.5.0 — D-53) |
| `multi_label` | a message may carry several categories/themes; topic counts do not sum to the message total (schema 1.1.0) |
| `label_provenance` | topics come from automated classification; `label_versions.classification` names the exact version (schema 1.1.0) |
| `status_rule` | program level from coordinator roster lists; BA→MA transitioners counted by status at usage time, session-level (D-39) |
| `trend_method` | how a trend is selected: gate (floor, size, effect, BH-adjusted p) then relevance ranking; census framing (schema 1.3.0 — D-49) |
| `per_week_rate` | volume measures compared per covered week; within-period seasonality not corrected, in-progress periods averaged over weeks so far (schema 1.3.0) |
| `cohort_turnover` | each semester draws a largely different cohort; a between-semester change may reflect who enrolled (schema 1.3.0) |
| `enrollment_source` | enrolled totals come from SSC-Psych records (schema 1.7.0 — D-55) |
| `enrollment_scope` | the enrolled totals cover all bachelor/master students, whereas only the first-year students take the statistics course; per-instructor first-year numbers are unavailable (schema 1.7.0 — D-55) |
| `level_scope` | the figure covers every program level; the program-level filter does not narrow it (schema 1.7.0 — D-55) |

Adding a footnote or attaching an existing id to a metric is additive.

### 6.3 `enrollment` — enrolled-cohort denominators (schema 1.7.0 — D-55)

```json
"enrollment": { "per_window": { "2026S": {
    "bachelor": 2012, "master": 1455,
    "source": "SSC-Psych roster lists (bachelor_and_master_students_mar_2026, typed)",
    "as_of": "2026-03-01" } } }
```

Top-level, **outside `sections`**, and carrying plain integers rather than `CountCell`s.
It is not a measurement: nothing here passes `floored_count` because there is nothing to
floor — an institutional headcount is not a count over students who wrote messages, and
dressing it as a cell would invite exactly that misreading. `source` and `as_of` name the
roster snapshot so a published number can be traced back.

**Semester windows only** (validated): `all_time` spans three semesters of cohort
turnover, so no single headcount is its denominator. The dashboard states that in words
rather than drawing an empty card. A semester slice is *not* keyed here either, for the
opposite reason — it lies entirely inside one term, so it reads its parent's entry through
`parent_window_id` (§6.1) rather than this map carrying the same institutional number
under several keys.

Keys are clipped at build time to the semester windows the registry actually built, so a
stale entry in the hand-maintained table can never introduce an unknown window id. The
table lives at `pipeline/cohort_totals.json`; the identifier-bearing roster lists it was
derived from stay outside the repo (D-39 custody, `docs/ethics/data-handling.md`).

Reach — active students ÷ enrolled — is display math over one published cell and one
enrollment integer, and is defined for `bachelor` and `master` only: staff are not
enrolled and `unknown` has no cohort by definition.

### 6.4 Dayparts (schema 1.6.0 — D-54)

Named blocks of the day that `daypart_heatmap` and `daypart_totals` key on. `from_hour` is
inclusive, `to_hour` exclusive, and the registry must tile 0..24 contiguously — so nothing
wraps midnight and every hour lands in exactly one block.

```json
"dayparts": [
  { "id": "night",     "label": "Night",     "from_hour": 0,  "to_hour": 6  },
  { "id": "morning",   "label": "Morning",   "from_hour": 6,  "to_hour": 12 },
  { "id": "afternoon", "label": "Afternoon", "from_hour": 12, "to_hour": 18 },
  { "id": "evening",   "label": "Evening",   "from_hour": 18, "to_hour": 24 }
]
```

**Why the boundaries live in the document.** Same reason footnote texts do: a definition is
versioned with the numbers it governs, so an archived blob still says what its own cells
meant, and the dashboard holds no daypart definitions of its own — it renders whatever the
registry declares, including the labels.

**Why the blocks are equal.** Bar length reads as intensity, so unequal bins invert the
finding. A six-block draft with 2–8 hour widths put 09–12 at 1,010 messages against 14–18
at 1,560 — "afternoons are far busier" — while the per-hour rates were 337 and 390, and the
2-hour midday block, the *shortest bar on the chart*, was the densest period of the day at
408/h. Equal widths make the bars comparable without per-hour normalization, which is what
the `daypart_definition` footnote tells the reader.

Optional: absent in documents that publish no daypart cells. Present whenever any are
published (validated at document root, since only the root sees both).

## 7 · Sections

Common inner layout: `weekly` (trend material) and/or `per_window` (rollups keyed by
window id). Educator-question coverage: E (when/language) fully; D (helping?) via proxies
only; A/B/C (topics) arrive with Phase B (§8).

### 7.1 `temporal_usage` — when are students using it?

```json
{ "weekly": { "messages":        { "series": [ … ] },
              "sessions":        { "series": [ … ], "footnote_ids": ["chat_fragmentation"] },
              "active_students": { "series": [ … ] } },
  "per_window": { "<window_id>": { "activity_heatmap": HeatmapGrid,
                                   "daypart_heatmap": DaypartGrid,      // 1.6.0
                                   "daypart_totals":  DaypartTotals } },// 1.6.0
  "semester_profiles": [ SemesterProfile ] }                            // 1.6.0
```

**`activity_heatmap` is published but no longer rendered (1.6.0, D-54).** The dashboard
draws `daypart_heatmap` instead: 7 × 24 = 168 cells was too fine for this corpus and the
floor ate it (52 of 84 non-empty cells suppressed in 2025W, 29 of 139 all-time), while
7 × 4 suppresses 3 and 2 respectively and preserves the weekday × daypart interaction the
grid exists to show. The field stays because it is a **required field of a section that
stays**, and §10 forbids removing that within a major version — the 1.5.0 exception covers
withdrawing a whole optional section only. It is also the rollback path.

**`daypart_totals`** carries `by_daypart` (one cell per registry id), plus `weekend` and
`weekday`, each floored on its own contributing-student set. They are never derived from
one another: `weekday = total − weekend` would recover a suppressed side exactly.

**`semester_profiles`** is deliberately *not* per-window — it exists to compare windows, so
the window picker cannot apply to it, and the dashboard renders it under `all_time` only.
Each entry re-indexes one semester to teaching week: `semester_week` is the 1-based index
into the window's **full** Thursday-rule membership, not into the weeks that happen to
carry data. Indexing on coverage would slide a semester whose opening weeks are off-axis
one week left and silently misalign every comparison the overlay exists to make. Weeks past
the axis are absent rather than zero-filled, so an in-progress semester ends where the data
does. Both `messages` and `active_students` are published; the dashboard plots messages.

### 7.2 `usage_context` — adoption, KPI totals, Bergmann-comparable user classes

```json
{ "weekly": { "registrations": { "series": [ … ] } },
  "per_window": { "<window_id>": {
      "totals": { "active_students": CountCell, "messages": CountCell,
                  "sessions": CountCell, "new_registrations": CountCell,
                  "new_registrations_active": CountCell,          // 1.4.0
                  "new_users": CountCell, "returning_users": CountCell,
                  "footnote_ids": ["retention_definition", "signup_activation"] },
      "user_classes": { "one_time": CountCell, "monthly": CountCell,
                        "sporadic": CountCell,
                        "frequent": CountCell,                    // 1.4.0, subset of monthly
                        "footnote_ids": ["user_class_definitions", "user_class_window"] },
      "by_status": { "<bachelor|master|staff|unknown>": {         // 1.4.0, absent w/o roster
                        "active_students": CountCell, "messages": CountCell,
                        "footnote_ids": ["status_rule", "status_multi"] } } } } }
```

`totals` feeds the KPI tiles for the selected window (invariant 4: never client-summed) —
which is exactly why the 1.4.0 additions have to be published rather than derived: a client
subtracting two floored cells to get "returning" would have no idea how many students back
the difference.

**Field semantics (1.4.0, D-50).** `new_registrations` still counts accounts created in the
window, whether or not they were ever used; it keeps its name because renaming a published
field is a *major* break, and the dashboard relabels it "New signups". `new_registrations_active`
is the subset who also wrote at least one message **inside the same window** — both sides
window-scoped, so a published window never changes value on a later republish.
`new_users` / `returning_users` partition `active_students` by whether the student's
first-ever message falls inside the window; that baseline reads the **whole corpus,
including pre-`axis_start` pilot months**, so a returning pilot user is not miscounted as
new. This pair carries **complementary suppression**: a two-part partition of a published
total is recoverable by subtraction, so if either side is sub-floor neither is published
(a measured zero is `ok(0)` and does not trigger it). It is the only cell pair in the
document where the floor is applied jointly rather than per cell. `by_status` resolves program level per session (D-39): messages partition exactly,
students do not — a bachelor→master transitioner active on both sides of their semester
boundary appears under both levels, which `status_multi` states.

`user_classes` reproduces the operational definitions of Bergmann et al. (2026), verified
verbatim against OSF script `30_Analysis Step 3 - Table K1 & subgroup analysis.R`
(2026-07-30). Their script sets five *independent indicator flags*, not one exclusive class.
`one_time` / `monthly` (their `occasional_user`) / `sporadic` happen to partition the users
and sum to `active_students`; **`frequent` does not** — `all(diffs < 14) & span_days > 30`
implies their occasional condition, so every frequent user is also a monthly one. It is
published as a sub-count so that a future non-zero is visible instead of being silently
folded into monthly. Reference check on our 2025S window: 111 one-time / 12 monthly /
67 sporadic against their published 12 monthly / 67 sporadic / 56.6 % one-time.

### 7.3 `sessions` — engagement depth

```json
{ "per_window": { "<window_id>": {
      "messages_per_session":     Histogram,   // summary incl. mean/sd (Bergmann: 1.8/2.5)
      "session_duration_minutes": Histogram    // footnotes: chat_fragmentation,
} } }                                          //            duration_definition
```

Field names keep the source vocabulary (`session`); the Engagement tab renders both as
*conversation* (D-08's unit, and the word the `chat_fragmentation` footnote already used).

### 7.4 `per_student` — engagement breadth (schema 1.5.0 — normative)

*Added 2026-07-30 (D-53), in the slot the removed `tokens` section held. Section
additions are additive (§10): `SCHEMA_VERSION` 1.4.0 → 1.5.0, same `v1/` blob prefix.*

```json
{ "per_window": { "<window_id>": {
      "sessions_per_student":     Histogram,   // unit "students"; chat_fragmentation
      "weeks_active_per_student": Histogram,   // unit "students"; weeks_active_window
      "messages_per_student":     Histogram    // unit "students"
} } }
```

- Same `Histogram` primitive as §7.3, but **one observation per student**: the bins count
  students, `n_total` is the window's active-student count, and the summary describes the
  spread across students. Only students with ≥ 1 message in the window appear.
- None of the three is derivable client-side (invariant 4). Dividing `totals.messages` by
  `totals.active_students` yields a mean and nothing else, and on this data mean and median
  disagree sharply (2026S: mean 7.5, median 5) — the skew *is* the finding.
- `weeks_active_per_student` is bounded by the window's length, so its shares are not
  comparable between windows of different length (`weeks_active_window` footnote).
- **Accepted differencing residual** (owner, 2026-07-30): these bins partition the students
  that `n_total` counts, so `n_total` minus the published bins recovers the total held by
  the suppressed ones — exactly, when only one bin is suppressed. Secondary suppression was
  considered and declined as disproportionate for a cohort-wide teaching dashboard; the
  floor stays per-cell here as everywhere else. Recorded in D-53 with the D-50 open item.

**Removed in 1.5.0: `tokens`** (`completion_tokens_per_message`). It measured the model's
verbosity rather than student engagement, and no view rendered it after the Engagement
redesign. Removing an *optional section no reader renders* is treated as a minor change
(§10): archived documents that carry it still validate, since readers ignore unknown fields
(invariant 5). `completion_tokens` and `prompt_tokens` remain in the local corpus, so a
reply-length or session-context-growth view can return additively.

### 7.5 `language` — …and in which language?

```json
{ "weekly": { "messages_by_language": {
      "de": { "series": [ … ] }, "en": { "series": [ … ] },
      "other": { "series": [ … ] }, "undetermined": { "series": [ … ] },
      "footnote_ids": ["language_heuristic"] } },
  "per_window": { "<window_id>": {
      "totals": { "de": CountCell, "en": CountCell,
                  "other": CountCell, "undetermined": CountCell } } } }
```

Fixed key set in v1 (`de`, `en`, `other`, `undetermined` — detector returns None →
`undetermined`; a detected non-de/en language → `other`). Shares are client-side division
of published cells (legal display math); a suppressed language renders as "< N students"
with no share. Governed by `label_versions.language` — the file's first exercise of the
D-07 label-versioning design.

### 7.6 `trends` — how is usage changing over time? (schema 1.3.0 — normative)

*Added 2026-07-29 (D-49). Additive minor bump: `SCHEMA_VERSION` 1.2.0 → 1.3.0, same
`v1/` blob prefix (§10); a 1.2.0 document still validates and 1.2.0 readers ignore this
section (invariant 5).*

```json
{ "per_window": { "<window_id>": {
      "baseline": { "kind": "window", "window_id": "2025W" }        // semester → predecessor
                | { "kind": "weeks", "from": WeekId, "through": WeekId }  // unemitted since 1.8.0
                | { "kind": "trajectory" }                          // all_time
                | null,                                             // no predecessor
      "insufficient_data": false,
      "findings": [ {
          "id": "language-de-share", "tab": "language",
          "title": "German share of messages fell",
          "measure": "German share of messages",
          "kind": "share",                       // rate | share | median
          "unit": "% of messages",
          "current":  MeasureValue, "baseline": MeasureValue,
          "delta": -13.7,                        // in unit terms (pp, per-week, minutes…)
          "evidence": "robust",                  // robust | indicative
          "method": "two-proportion z, BH-adjusted",
          "trajectory": [ TrajectoryPoint ],     // OPTIONAL — only under a trajectory baseline
          "footnote_ids": ["trend_method", "language_heuristic"] } ] } } }
```

- `MeasureValue` = `{ value: float, n_students: int }`, `TrajectoryPoint` =
  `{ window_id, value, n_students }`. Deliberately **not** `CountCell`: findings publish
  derived floats (rates, shares, medians), and a sub-floor candidate is **dropped before
  publication** rather than marked suppressed. This is the one place where the floor is
  satisfied by absence rather than by a visible marker — legitimate because a rendered
  "we found a shift but cannot tell you what it was" carries no information, unlike a
  suppressed count in a series where position and neighbours do. Every published side
  still carries `n_students ≥ privacy_floor_n`, guard-enforced.
- **`baseline: null` is a value, not an absent key** — it is the "no earliest predecessor
  to compare against" marker the dashboard branches on, so it survives the document's
  `exclude_none` serialization (same treatment as `HistogramBin.hi`).
- **`insufficient_data`** distinguishes *nothing was testable* (every candidate fell
  below the floor or the minimum n) from *tested and flat* (an empty `findings` list). It is `false`
  whenever `baseline` is `null` or `findings` is non-empty.
- **Findings are pre-ranked; the client renders them in the order received.** Selection
  and ordering are analysis, not display math (invariant 4), and the per-student
  observations the tests need exist only locally. The relevance tier that drives the
  ordering is deliberately **not published** — publishing it would invite the dashboard
  to re-sort.
- At most **5** findings per window, at most **3** from `topics` and **2** from any other
  tab. `tab` is the closed set `topics | adoption | engagement | timing | language` and
  names the source tab a card links back to.
- `evidence` is `robust` (Benjamini–Hochberg-adjusted p < .05, one family per window) or
  `indicative` (unadjusted p < .05 only). p-values are not published; `method` names the
  test for the card's tooltip. These are a census, not a sample — the tests guard against
  over-reading noise, not inference to a population.
- `title` is template-generated from pinned measure names. **No finding text derives from
  chat content**, so no D-33-style operator review gates a publish (invariant 6 holds
  structurally).
- New footnotes: `trend_method` (candidate pool, tests, BH family, thresholds — versioned
  with the numbers), `per_week_rate` (volume measures compare as per-covered-week rates;
  in-progress windows caveated, within-semester seasonality not corrected),
  `cohort_turnover` (each semester draws a largely different cohort, so a between-semester
  shift may reflect who enrolled).

No existing key changed meaning.

## 8 · `topics` section (Phase B, schema 1.1.0 — normative)

*Made normative 2026-07-18 (D-38/D-39); supersedes the informative sketch. Additive
minor bump: `SCHEMA_VERSION` 1.0.0 → 1.1.0, same `v1/` blob prefix (§10); a 1.0.0
document still validates and 1.0.0 readers ignore this section (invariant 5).*

```json
{ "per_window": { "<window_id>": {
      "deductive":       TopicDistribution,   // 13 Bergmann categories
      "method_themes":   TopicDistribution,   // frozen list (21)
      "software_themes": TopicDistribution,   // frozen list (9)
      "emergent_themes": TopicDistribution,   // OPTIONAL — Stage 2 (D-38); absent until then
      "by_status": {                          // OPTIONAL — D-39 program-level split
          "bachelor": TopicGroup, "master": TopicGroup,
          "staff": TopicGroup, "unknown": TopicGroup } } },   // unknown only when non-empty
  "theme_set_version": "statsboteval-themes-v1" }             // OPTIONAL, with emergent_themes
```

- `TopicDistribution` = `{ items: [{label, cell: CountCell, description?}], n_total:
  CountCell, footnote_ids? }` — a categorical distribution, **not** the numeric
  `Histogram`.
  Cells are multi-label counts (a message may be several categories/themes) and do
  **not** sum to `n_total` (`multi_label` footnote); `n_total` is the floored message
  count of the (window × status) slice. The floor tests distinct contributing
  students per cell, as everywhere.
- `by_status` keys are the closed set `bachelor | master | staff | unknown`; a status
  group appears only when non-empty, and every cell inside it floors independently —
  the floor, not the schema, is the small-group defense. Resolution is the D-39
  usage-time rule at session level (`status_rule` footnote).
- Deductive item labels are the public manuscript category names; theme labels are the
  frozen/reviewed theme strings (the D-33 operator review is the privacy control for
  emergent labels entering this file).
- `label_versions.classification` names the one configured version (`statsboteval-v1`
  or `bergmann-v1`, D-07); `theme_set_version` documents the reviewed emergent set.
- `description` (schema 1.2.0, additive minor bump — D-44): optional one-line
  definition of the item's label, published **only** for `emergent_themes` items,
  sourced from the frozen theme set (the same D-33-reviewed table as the labels).
  Deductive/method/software items never carry it — Bergmann category definitions are
  unpublished research material (D-16). A 1.1.0 document (no descriptions) stays valid.

No existing key changed meaning.

## 9 · Blob layout & publish protocol

```
container: aggregates            (private; API reads via connection string — D-18)
  v1/aggregates_2026-W27_20260706T051233Z.json   immutable, one per publish
  v1/latest.json                                  full copy, overwritten atomically
```

1. Write the immutable blob (`v1/aggregates_{data_through_week}_{generated_at}.json`).
2. Overwrite `v1/latest.json` with identical content. Azure blob PUT is atomic → readers
   get old-or-new, never torn. Full copy, not a pointer: one GET, and both writes happen
   in the same publish step, so pointer drift isn't a real risk.
3. History = the immutable blobs (D-10). The erasure runbook republishes and **may delete
   superseded historical blobs**; the retained-history differencing risk is the accepted
   repeated-releases residual (`ethics/data-handling.md`).
4. The `v1/` prefix is the schema major version. A breaking change publishes under `v2/`;
   an un-upgraded API keeps reading `v1/latest.json`. Compatibility is enforced by
   *routing*, with read-time schema validation as the tripwire behind it.

## 10 · Evolution policy

Within a major version, allowed (minor bump): new optional fields, new sections, new
metrics inside sections, new windows, new footnotes, new `label_versions` keys, new
language keys. Never within a major version: removing/renaming fields, changing a field's
type or a cell's meaning, changing week/date formats. Breaking = major bump + new blob
prefix + coordinated reader upgrade. `data_through_week` regressing (erasure republish of
a shorter history) is *not* a schema event.

**One narrow exception, exercised once (1.5.0, D-53): withdrawing a whole optional section
that no reader renders is a minor change.** The reasoning is invariant 5, not convenience —
an optional section may legitimately be absent, so a document without it is one every
reader already had to tolerate, and archived documents that still carry it keep validating
because readers ignore unknown fields. This does **not** extend to removing a *field from a
section that stays*: there the reader has no absence contract to fall back on, and that
remains a major break.

## 11 · Validation & publish guard

- **Schema round-trip**: pipeline output validates against
  `schema/aggregates.schema.json`; the API re-validates on read; the exported schema is
  regenerated in CI and must produce no diff (drift guard); dashboard TS types are
  generated from the exported schema.
- **Publish guard** (pre-upload, blocking): every cell's contributing-students count is
  0 or ≥ `privacy_floor_n`; no `suppressed` cell carries a value; weekly series are dense
  over `[first_week, data_through_week]`; heatmaps have exactly 168 cells; every
  `per_window` key exists in the windows registry; every `footnote_ids` entry exists in
  the footnotes registry; no fields outside the schema (structurally excludes chat text).
- **Floor walk over the outgoing bytes** (1.3.0, D-49): no `n_students` anywhere in the
  serialized document is below `privacy_floor_n`. Deliberately stated over the whole
  document rather than per section — every model that publishes an `n_students` does so
  only after a floor test, so the universal claim is the true one and keeps holding as
  sections are added. It is the last check before upload and is redundant with the model
  validators by design: those check the object graph, this checks what leaves the machine.
- **Property test**: cells covering 1..N−1 students never survive, for generated corpora;
  and for `trends` (where the floor is satisfied by dropping a candidate rather than by
  marking a cell) no generated corpus yields a finding with a sub-floor side.

## 12 · Example document (illustrative, truncated)

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-07-06T05:12:33Z",
  "data_through_week": "2026-W27",
  "data_through_date": "2026-07-05",
  "first_week": "2025-W11",
  "privacy_floor_n": 3,
  "label_versions": { "language": "lang-heuristic-v1" },
  "timezone": "Europe/Vienna",
  "data_provenance": "synthetic",
  "pipeline_version": "0.1.0",
  "windows": [
    { "id": "all_time", "kind": "all_time", "label": "All time",
      "coverage": { "from": "2025-W11", "through": "2026-W27" } },
    { "id": "2026S", "kind": "semester", "label": "Summer semester 2026",
      "start_date": "2026-03-01", "end_date": "2026-06-30",
      "weeks": ["2026-W10", "2026-W11", "2026-W12", "…", "2026-W26"],
      "coverage": { "from": "2026-W10", "through": "2026-W26" } }
  ],
  "dayparts": [
    { "id": "night", "label": "Night", "from_hour": 0, "to_hour": 6 },
    { "id": "morning", "label": "Morning", "from_hour": 6, "to_hour": 12 },
    { "id": "afternoon", "label": "Afternoon", "from_hour": 12, "to_hour": 18 },
    { "id": "evening", "label": "Evening", "from_hour": 18, "to_hour": 24 }
  ],
  "footnotes": {
    "chat_fragmentation": { "text": "The credit-limit UI nudges students toward starting new chats; conversation counts may overstate distinct dialogues." }
  },
  "sections": {
    "temporal_usage": {
      "weekly": {
        "messages": { "series": [
          { "week": "2025-W11", "cell": { "status": "ok", "value": 41 } },
          { "week": "2025-W12", "cell": { "status": "suppressed" } },
          { "week": "2025-W13", "cell": { "status": "ok", "value": 0 } }
        ] },
        "sessions": { "series": ["…"], "footnote_ids": ["chat_fragmentation"] },
        "active_students": { "series": ["…"] }
      },
      "per_window": {
        "2026S": {
          "activity_heatmap": { "cells": [
            { "dow": 1, "hour": 8, "cell": { "status": "ok", "value": 41 } },
            { "dow": 7, "hour": 3, "cell": { "status": "suppressed" } }
          ] },
          "daypart_heatmap": { "cells": [
            { "dow": 1, "daypart": "morning", "cell": { "status": "ok", "value": 159 } },
            { "dow": 7, "daypart": "night",   "cell": { "status": "suppressed" } }
          ], "footnote_ids": ["daypart_definition"] },
          "daypart_totals": {
            "by_daypart": {
              "night":     { "status": "ok", "value": 18 },
              "morning":   { "status": "ok", "value": 278 },
              "afternoon": { "status": "ok", "value": 510 },
              "evening":   { "status": "ok", "value": 180 }
            },
            "weekend": { "status": "ok", "value": 219 },
            "weekday": { "status": "ok", "value": 767 },
            "footnote_ids": ["daypart_definition"]
          }
        }
      },
      "semester_profiles": [
        { "window_id": "2026S", "label": "Summer semester 2026", "kind": "summer",
          "points": [
            { "semester_week": 1, "week": "2026-W10",
              "messages": { "status": "ok", "value": 49 },
              "active_students": { "status": "ok", "value": 12 } }
          ],
          "footnote_ids": ["semester_week_alignment", "cohort_turnover"] }
      ]
    },
    "sessions": {
      "per_window": {
        "2026S": {
          "messages_per_session": {
            "unit": "sessions",
            "bins": [
              { "lo": 1, "hi": 1,    "cell": { "status": "ok", "value": 214 } },
              { "lo": 2, "hi": 3,    "cell": { "status": "ok", "value": 96 } },
              { "lo": 4, "hi": 7,    "cell": { "status": "suppressed" } },
              { "lo": 8, "hi": null, "cell": { "status": "ok", "value": 11 } }
            ],
            "n_total": { "status": "ok", "value": 327 },
            "summary": { "status": "ok", "n_students": 74, "median": 2.0,
                         "p25": 1.0, "p75": 4.0, "mean": 2.4, "sd": 2.1 },
            "footnote_ids": ["chat_fragmentation"]
          }
        }
      }
    }
  }
}
```

(`"…"` marks truncation for readability; real files are dense per §5. `usage_context`,
`per_student`, `language` follow §7 identically.)

## 13 · Deliberately deferred (not TBDs — decided *against* for v1)

- **Segmentation** (per-course via `lv`, program level via `Status`): cohort-wide only —
  **partly reversed.** Program level arrived exactly as predicted, "as additive dimensions
  inside sections": `topics.by_status` in schema 1.1.0 (D-39), `usage_context.by_status`
  in 1.4.0 (D-50), and every remaining section in 1.7.0 (D-55) — all fed by the roster
  import rather than by `Status`. Per-course
  segmentation stays deferred — `students.lv` does not exist in production
  (`source-data-dictionary.md`), so it is not deferred but impossible.
- **Trends over semester slices**: excluded from the trends pass since 1.8.0 (D-56) —
  their pairing rule is undecided and the tab is hidden. Blocks un-hiding Trends.
- **Token views** (`completion_tokens` reply length, `prompt_tokens` session-context
  growth): both additive when wanted. Reply length was published in 1.0.0–1.4.0 and
  withdrawn in 1.5.0 (§7.4) — it describes the model, not the student.
- **Arbitrary date ranges**: excluded by invariant 4 by design; presets = windows.
- **Bin edges**: pipeline config at implementation (declared per-file in the data).
- **User-class SQL**: pinned at implementation against the Stage-2 manuscript definitions,
  with a validation test against their published counts. **Done** — pinned in
  `stats.classify_user` / `stats.is_frequent` against the OSF R script itself, unit-tested
  per condition (`tests/test_stats.py`). Their `one_time_project_user` flag (not one-time
  and span ≤ 30 days) is still unpublished; it is a subset of sporadic and additive when
  wanted (77 students all-time).

## Related decisions

D-03 (weekly batch) · D-07 (label versioning) · D-08 (conversation = `started` session) ·
D-09/D-24 (privacy floor, N=3 working) · D-10 (blob publish, history) · D-17 (DuckDB) ·
D-18 (private blob, API = auth boundary) · D-19 (walking skeleton; this doc closes its
contract gate) · D-23 (Next.js dashboard) · D-25 (this contract).

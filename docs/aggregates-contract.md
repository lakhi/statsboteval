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
"windows":   [ … ]             §6.1 — window registry (semesters, all_time, trailing)
"footnotes": { … }             §6.2 — caveat registry, referenced by id
"sections":  {                 §7   — one key per dashboard view
    "temporal_usage": … , "usage_context": … , "sessions": … ,
    "tokens": … , "language": …                    // Phase B adds "topics" (§8)
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
| `data_through_week` / `data_through_date` | Last complete ISO week in the file / its Sunday as a plain date (for display without ISO-week math in TS). |
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

Named week-sets that every `per_window` rollup keys on. One registry covers semesters,
all-time, and trailing windows; UI presets map onto it completely (current semester =
semester window with the latest coverage; previous semesters = older ones; last month =
`trailing_4`; current/last week = last entries of the weekly series directly — a
single-week window would only duplicate them; `trailing_1` can be added later for
last-week heatmaps/distributions, additively).

```json
"windows": [
  { "id": "all_time",   "kind": "all_time", "label": "All time",
    "coverage": { "from": "2025-W11", "through": "2026-W27" } },
  { "id": "2025S",      "kind": "semester", "label": "Summer semester 2025",
    "start_date": "2025-03-01", "end_date": "2025-06-30",
    "weeks": ["2025-W10", "…", "2025-W26"],
    "coverage": { "from": "2025-W11", "through": "2025-W26" } },
  { "id": "trailing_4", "kind": "trailing", "label": "Last 4 weeks",
    "weeks": ["2026-W24", "2026-W25", "2026-W26", "2026-W27"],
    "coverage": { "from": "2026-W24", "through": "2026-W27" } }
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
- `trailing_4` = the last 4 complete weeks, recomputed each publish.
- Every key of every `per_window` object must exist in this registry (validated).

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
| `user_class_definitions` | one-time/monthly/sporadic per the Bergmann Stage-2 operational definitions |
| `duration_definition` | session duration = last − first server `created_at` in the session; single-message sessions = 0 |

Adding a footnote or attaching an existing id to a metric is additive.

## 7 · Sections (Phase A)

Common inner layout: `weekly` (trend material) and/or `per_window` (rollups keyed by
window id). Educator-question coverage: E (when/language) fully; D (helping?) via proxies
only; A/B/C (topics) arrive with Phase B (§8).

### 7.1 `temporal_usage` — when are students using it?

```json
{ "weekly": { "messages":        { "series": [ … ] },
              "sessions":        { "series": [ … ], "footnote_ids": ["chat_fragmentation"] },
              "active_students": { "series": [ … ] } },
  "per_window": { "<window_id>": { "activity_heatmap": HeatmapGrid } } }
```

### 7.2 `usage_context` — adoption, KPI totals, Bergmann-comparable user classes

```json
{ "weekly": { "registrations": { "series": [ … ] } },
  "per_window": { "<window_id>": {
      "totals": { "active_students": CountCell, "messages": CountCell,
                  "sessions": CountCell, "new_registrations": CountCell },
      "user_classes": { "one_time": CountCell, "monthly": CountCell,
                        "sporadic": CountCell,
                        "footnote_ids": ["user_class_definitions"] } } } }
```

`totals` feeds the KPI tiles for the selected window (invariant 4: never client-summed).
`user_classes` uses the Stage-2 manuscript's operational definitions verbatim; the exact
SQL is pinned at implementation with a validation test against the published reference
(56.6 % one-time / 12 monthly / 67 sporadic on their window).

### 7.3 `sessions` — engagement depth

```json
{ "per_window": { "<window_id>": {
      "messages_per_session":     Histogram,   // summary incl. mean/sd (Bergmann: 1.8/2.5)
      "session_duration_minutes": Histogram    // footnotes: chat_fragmentation,
} } }                                          //            duration_definition
```

### 7.4 `tokens` — reply length

```json
{ "per_window": { "<window_id>": { "completion_tokens_per_message": Histogram } } }
```

v1 publishes `completion_tokens` only. `prompt_tokens` counts the re-sent session context
(source data dictionary) and is **omitted**; a session-context-growth view can arrive
additively later.

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

## 8 · Phase B extension path (informative)

Phase B adds — additively, same file (locked in this session):

- `sections.topics`: per-window distributions over the Bergmann deductive categories and
  inductive themes (`Histogram`-shaped over categorical bins), footnoted with label
  provenance.
- `label_versions.classification`: the one configured version (`statsboteval-v1` or
  `bergmann-v1`), per D-07.

No existing key changes meaning; v1 readers ignore the new section (invariant 5).

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
- **Property test**: cells covering 1..N−1 students never survive, for generated corpora.

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
        "2026S": { "activity_heatmap": { "cells": [
          { "dow": 1, "hour": 8, "cell": { "status": "ok", "value": 41 } },
          { "dow": 7, "hour": 3, "cell": { "status": "suppressed" } }
        ] } }
      }
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
`tokens`, `language` follow §7 identically.)

## 13 · Deliberately deferred (not TBDs — decided *against* for v1)

- **Segmentation** (per-course via `lv`, program level via `Status`): cohort-wide only.
  Blocked on unresolved sources anyway (`open-questions.md`); would arrive as additive
  dimensions inside sections.
- **`trailing_1` window** (last-week heatmap/distributions): additive when wanted; heavy
  suppression expected at one week of data.
- **`prompt_tokens` / session-context growth view**: additive when wanted.
- **Arbitrary date ranges**: excluded by invariant 4 by design; presets = windows.
- **Bin edges**: pipeline config at implementation (declared per-file in the data).
- **User-class SQL**: pinned at implementation against the Stage-2 manuscript definitions,
  with a validation test against their published counts.

## Related decisions

D-03 (weekly batch) · D-07 (label versioning) · D-08 (conversation = `started` session) ·
D-09/D-24 (privacy floor, N=3 working) · D-10 (blob publish, history) · D-17 (DuckDB) ·
D-18 (private blob, API = auth boundary) · D-19 (walking skeleton; this doc closes its
contract gate) · D-23 (Next.js dashboard) · D-25 (this contract).

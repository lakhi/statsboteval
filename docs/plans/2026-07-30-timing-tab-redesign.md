# Timing tab redesign — dayparts, coarser heatmap, semester overlay, readable week axis

**Date:** 2026-07-30 · **Status:** IMPLEMENTED 2026-07-30 (see D-54)

> **Figures corrected at implementation.** The exploratory numbers below were first
> measured over the whole corpus (4,419 messages, including the 2024/25 pilot) and over
> ad-hoc date ranges. Everything is now restated over the **published axis** (2025-W09 →
> 2026-W30, 3,528 messages — `axis_start` is 2025-03-01, so four days of week 09 are
> corpus-only) and the **real window registry**. Two corrections matter: the
> drafting note that `trailing_4` held 167 messages was wrong — the real trailing window is
> W27–W30, the July break, holding about ten messages, every cell sub-floor either way. The
> window the coarsening actually rescues is **2025W** (52/84 suppressed → 3/21). The
> direction of every conclusion is unchanged.

**Decision to record at implementation:** D-54
**Schema:** 1.5.0 → **1.6.0** (additive; minor bump per contract §10)

## Why

Four separate problems on one tab, found while auditing it on 2026-07-30:

1. **"Messages per week" is ambiguous.** One `history` row is one *question/answer exchange*
   (`docs/source-data-dictionary.md`), so the W23 peak of ~170 is ~170 student questions
   *and* ~170 replies. Adoption already states this on its Messages tile; Timing does not.
2. **"Active students per week" is ambiguous twice over** — the ≥ 1 message rule is
   unstated, and nothing warns that the line does not sum to a student total (a student
   active in five weeks is counted five times).
3. **The heatmap is being destroyed by the privacy floor.** 7 × 24 = 168 cells is too fine
   a grid for this corpus. Non-empty cells suppressed, per published window:

   | window | non-empty cells suppressed |
   |---|---|
   | all_time | 28 / 138 |
   | 2025S | 40 / 122 |
   | **2025W** | **52 / 84 (62%)** |
   | 2026S | 45 / 111 |

   A whole winter semester renders as mostly stripes.
4. **The x-axis says `W10`,** which no educator reads as "early March".

## What the corpus supports (measured 2026-07-30, `pipeline/data/corpus.duckdb`)

### Dayparts: four equal six-hour blocks

**Equal widths are not cosmetic — unequal ones actively mislead.** An earlier draft of this
plan used six blocks of 2–8 hours. On all-time data that renders 09–12 at 1,010 and 14–18
at 1,560, so the reader concludes the afternoon is far busier than the morning. Per hour
the rates are 337 and 390 — and the 2-hour midday block, the shortest bar on the chart, is
the *densest* period of the day at 408/h. A bar chart's height reads as intensity, so
unequal bins invert the finding. Four equal blocks make bar height directly comparable and
need no per-hour normalization to be read correctly.

Messages published per block, real windows (verified against the built document):

| window | 00–06 Night | 06–12 Morning | 12–18 Afternoon | 18–24 Evening |
|---|---|---|---|---|
| all_time | 66 | 923 | 1,895 | 644 |
| 2025S | 38 | 327 | 790 | 297 |
| 2026S | 18 | 278 | 510 | 180 |
| trailing_4 | 0 | *suppressed* | *suppressed* | 0 |

Every block publishes in every window that has traffic. `trailing_4` is the July break —
about ten messages from one or two students — so it is sub-floor whatever the binning, and
the two measured zeros publish as `ok(0)` exactly as invariant 2 requires.

The educator-facing headline, over the published axis: **80% of use falls between 06:00
and 18:00, one message in five is sent between 18:00 and 06:00, and 23% of all messages
are sent at weekends** — roughly a third of StatsBot use happens when no human tutor is
reachable.

Four blocks also beat every alternative on suppression, because fewer cells means more
students per cell. Non-empty cells suppressed, measured on the real published windows:

| scheme | all_time | 2025S | 2025W | 2026S |
|---|---|---|---|---|
| 7 × 24 (today) | 28/138 | 40/122 | **52/84** | 45/111 |
| **7 × 4 (chosen)** | **2/28** | **4/26** | **3/21** | **3/25** |

**2025W is the window this rescues**: 62% of its non-empty cells were striped, now 14%.
Alternatives, scored on the exploratory ranges before the registry was consulted, all came
out worse than 7 × 4 (7 × 6 equal: 4/42 all-time; 7 × 6 uneven: 1/42 but with the bar-width
defect below; 7 × 8: 6/53).

### The weekday × daypart interaction survives coarsening, and sharpens

The reason to keep a grid at all is that it holds information the two margins cannot.
Observed ÷ expected-under-independence at 7 × 4, over the published axis:

```
        00-06   06-12   12-18   18-24
Mon      0.96    1.05    1.08    0.69
Tue      0.78    1.17    0.92    1.01
Wed      0.28    0.98    1.09    0.84
Thu      0.50    0.95    0.98    1.17
Fri      0.37    1.13    1.12    0.54
Sat      3.75    0.80    0.91    1.25
Sun      1.47    0.81    0.87    1.61
```

chi-square 159 on 18 df (critical 28.9 at p < .05). **Saturday 00–06 runs at 3.75×** —
Friday-night-into-Saturday work, the sharpest single cell in the corpus. Sunday evening
1.61×, against Friday 0.54 and Monday 0.69. Wednesday small hours 0.28.

None of this is visible in the margins: Sunday's daily total is unremarkable next to
Friday's, and the whole story is *when* on Sunday. Publishing only an hour profile and a
weekday profile would erase it. Publishing a 28-cell grid keeps it and suppresses two
cells out of 28 all-time.

What is lost by coarsening: the fine hour peak (11:00, 492 messages) becomes "06–12 is
busy". Accepted.

### The semester overlay aligns for free

`windows.py` already assigns weeks to semesters by the Thursday rule, so **semester week
*i* is exactly `window.weeks[i-1]`** — no new anchor concept. 2025S and 2026S both run 17
weeks from W10; 2025W runs 18 from W40.

Messages by semester week:

| sem week | 1 | 5 | 10 | 12 | 14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|
| 2025S | 46 | 44 | 80 | 149 | 79 | 171 | 144 | **218** |
| 2026S | 49 | 66 | 24 | 29 | **167** | 61 | 71 | 86 |

Both semesters ramp in the back half; the peaks land three weeks apart. Only **1 of 36**
semester-weeks falls under the floor (2026S week 18, a partial week — data ends 14 Jul).

## Not doing (checked, rejected)

- **Separate hour and weekday margin charts.** Superseded by the 28-cell grid: its row
  totals *are* the weekday margin and the daypart chart *is* the hour margin.
- **Intra-session turnaround** (median 3.0 min, IQR 1.4–8.3, stable across both
  semesters). Genuinely new and interesting — students read and re-ask in ~3 minutes,
  which is lookup rather than study — but it is a *session-depth* measure and belongs
  beside Engagement's duration histogram, not on a "when" tab. Deferred, not rejected.
- **Return latency between sessions** (median 1.0 day, p75 13 days). Re-measures what
  `user_classes` and `weeks_active` already publish.
- **Signup → first message.** Degenerate: **364 of 443 students wrote within one hour of
  registering.** Worth recording as a finding — Adoption's "signed up" and "sent at least
  1 msg" tiles are near-identical by construction, not by onboarding success — but there
  is no chart in it.

---

## Part 1 — the two labelling fixes (dashboard only)

No schema change, no republish. `ChartCard` already accepts a `note` prop
(`ChartCard.tsx:27`) that `TimingTab` never passes; it renders into the same APA-style
*Note.* footer the Sessions card uses.

- `TrendCard` in `TimingTab.tsx` gains an optional `note?: ReactNode`, forwarded to
  `ChartCard`.
- **Messages per week** → `note`: "1 msg = 1 student message + 1 LLM response."
- **Active students per week** → `note`: "A student counts in any week they sent at least
  one message. The same student is counted again in every week they were active, so the
  line does not add up to a student total — Adoption's *Active users* is the deduplicated
  count for the whole window."

## Part 2 — readable week axis (dashboard only)

**Month anchors, with a short-window fallback.** Rejected `MMM-W#` on measurement: 9 of
the 24 months in 2025–26 carry five ISO weeks under the Thursday rule (including April
2026 and May 2025, both currently on screen), the Monday and Thursday rules disagree on
boundary weeks (2026-W14 is `Mar-W5` or `Apr-W1`), `Mar-W1` appears twice unqualified on
the 74-week all_time axis, and doubling label width from 3 to 6 characters makes Recharts'
`minTickGap={28}` drop *more* ticks than today.

New in `src/lib/format.ts`:

- `weekMonthAnchor(week, prevWeek)` → `"Mar"` when the week's **Thursday** falls in a
  different month than the previous week's Thursday, else `""`. Thursday rule for
  consistency with `windows.py:_semester_of`. Appends the year at each January boundary
  and at the first tick (`"Jan 26"`), which is what fixes all_time.
- `weekStartLabel(week)` → `"02 Mar"`, the Monday via the existing `isoWeekMonday` +
  `formatDay`. This is the short-window fallback.
- `weekRangeLabel(week)` → `"W23 · 01–07 Jun 2026"` for tooltip and data table.

In `TrendChart.tsx`:

- `tickFormatter` switches on series length: **≤ 8 points → `weekStartLabel` on every
  tick** (trailing_4 can contain zero month boundaries; an axis with no labels is worse
  than one with four), **> 8 → `weekMonthAnchor`**.
- Tooltip title becomes `weekRangeLabel`.
- `trendTableRows` first column becomes `"2026-W23 (01–07 Jun)"` — the table is the
  precision twin, so it keeps the machine-readable id *and* gains the dates.

`weekShort` stays for `TrendsTab.tsx:154`, which renders a baseline range in prose, not on
an axis.

Touches every `TrendChart` consumer: Timing (3 charts), Adoption (registrations), Language.
Verify by eye in all five windows — trailing_4 (4 points) and all_time (74) are the two
that break naive implementations.

## Part 3 — dayparts and the coarsened heatmap (schema 1.6.0)

### Contract additions

A **`dayparts` registry** at document root, beside `windows` and `footnotes`
(contract §6.3). Boundaries live in the document, not in dashboard code, for the same
reason footnotes do — a caveat is versioned with the numbers it governs, and the dashboard
holds no definitions of its own (it "renders whatever the published document declares").

```json
"dayparts": [
  { "id": "night",     "label": "Night",     "from_hour": 0,  "to_hour": 6  },
  { "id": "morning",   "label": "Morning",   "from_hour": 6,  "to_hour": 12 },
  { "id": "afternoon", "label": "Afternoon", "from_hour": 12, "to_hour": 18 },
  { "id": "evening",   "label": "Evening",   "from_hour": 18, "to_hour": 24 }
]
```

`from_hour` inclusive, `to_hour` exclusive. **No block wraps midnight** — a happy
consequence of the equal-width scheme, since 00–06 starts the day rather than continuing
the previous one. A model validator enforces that the registry partitions all 24 hours
contiguously, the way `HeatmapGrid._dense_168` enforces density today.

Two new fields in `TemporalUsageWindow` (both optional, both additive):

```python
class DaypartCell(BaseModel):
    dow: int = Field(ge=1, le=7)
    daypart: str            # must resolve against the dayparts registry
    cell: CountCell

class DaypartGrid(BaseModel):
    cells: list[DaypartCell]        # dense 28, validated
    footnote_ids: list[FootnoteId] | None = None

class DaypartTotals(BaseModel):
    by_daypart: dict[str, CountCell]    # 4 keys, registry order
    weekend: CountCell                  # Sat+Sun messages
    weekday: CountCell                  # Mon–Fri messages
    footnote_ids: list[FootnoteId] | None = None

class TemporalUsageWindow(BaseModel):
    activity_heatmap: HeatmapGrid            # unchanged, still required
    daypart_heatmap: DaypartGrid | None = None      # 1.6.0
    daypart_totals: DaypartTotals | None = None     # 1.6.0
```

**`activity_heatmap` keeps being published even though nothing renders it.** It is a
required field of a section that stays, and §10 forbids removing that within a major
version — the 1.5.0 exception covers withdrawing a whole optional *section*, not a field.
Cost is ~840 unread cells across five windows; benefit is a rollback path and a clean
contract. Withdraw it at the next major bump if ever.

### Aggregation

In `aggregate.py`'s per-window loop, beside the existing `heat_counts` accumulation —
one extra pass over `w_msgs`, no new corpus read:

```python
daypart_counts / daypart_students        keyed by daypart id
dp_grid_counts / dp_grid_students        keyed by (dow, daypart)
weekend/weekday counts + student sets
```

Every cell through `floored_count(value, len(students), floor_n)` — the single path
(invariant). Weekend and weekday are floored on their own contributing-student sets, not
derived from each other.

`_daypart_of(hour)` is the only new logic: `hour // 6` indexed into the registry, which is
the whole function given equal six-hour blocks.

### Footnote

```
daypart_definition: "Times are Vienna local. The day is split into four equal six-hour
blocks — night 00–06, morning 06–12, afternoon 12–18, evening 18–24 — so the bars are
directly comparable. Each block counts messages sent inside it, so a chat that runs past a
boundary contributes to both."
```

Attached to `daypart_totals` and `daypart_heatmap`.

## Part 4 — semester-week overlay (schema 1.6.0)

### Rendered on the All-time view only

The overlay compares whole semesters, so it cannot honour the window picker. Rather than
sit there ignoring the filter while every neighbouring card obeys it, it renders **only
when `all_time` is selected** and is simply absent otherwise. That keeps the picker's
meaning exact: pick a semester, and everything on screen is that semester.

Not a `WindowGap` placeholder — that component says "not available for this window", which
frames a design decision as missing data. The card is omitted and the grid reflows.

### Contract addition

A third block in `temporal_usage`, alongside `weekly` and `per_window`. Deliberately
**not** per-window: the whole point is comparing across windows.

```python
class SemesterProfilePoint(BaseModel):
    semester_week: int = Field(ge=1)
    week: WeekId                       # the real ISO week, for the tooltip
    messages: CountCell
    active_students: CountCell

class SemesterProfile(BaseModel):
    window_id: str                     # resolves against the windows registry
    label: str
    kind: Literal["summer", "winter"]
    points: list[SemesterProfilePoint]

class TemporalUsage(BaseModel):
    weekly: TemporalUsageWeekly
    per_window: dict[str, TemporalUsageWindow]
    semester_profiles: list[SemesterProfile] | None = None    # 1.6.0
```

**Messages is the rendered measure.** `active_students` is published alongside it —
cohorts differ in size (2025S 165 active students vs 2026S 117), so it is the size-robust
read and a dashboard toggle is a five-line change later. Publishing both costs ~70 cells
and avoids a schema bump to add the toggle.

**All published semesters are plotted**, with `kind` driving a summer/winter distinction in
the legend. On the current axis that is 2025S, 2025W and 2026S. Summer and winter run
different courses, which the footnote states; since the chart now appears only under
All-time, showing the full set is consistent with what that window means.

### Aggregation

For each `SemesterWindow` in the registry, enumerate `window.weeks` in order and emit one
point per week that is **on the published axis** (a semester whose weeks run past
`data_through_week` simply ends early — no padding, no zero-filling a week that has not
happened). `semester_week` is the 1-based index into `window.weeks`, not into the covered
subset, so a semester with a quiet opening week still starts at 1 and the curves stay
aligned.

Cells reuse the same `msg_counts` / `msg_students` tallies the weekly series is built
from — one source of truth for "how many messages in week W".

### Footnote

```
semester_week_alignment: "Week 1 is the semester's first ISO week (the first week whose
Thursday falls inside the semester), so the curves line up on teaching week rather than
calendar date. Semesters draw largely different cohorts and differ in course structure —
summer and winter semesters especially — so compare the shape of a curve rather than its
height. A semester still in progress ends where the data does."
```

Plus the existing `cohort_turnover`.

## Tab layout after the change

```
Row 1   [ When during the day        ]  [ Weekday × daypart heatmap ]   ← daypart first
Row 2   [ Messages per week          ]  [ Sessions per week         ]
Row 3   [ Active students per week   ]  [ Semester rhythm overlay   ]   ← all_time only
```

The tab's question is "when do students use StatsBot?", so the time-of-day answer leads.
In the four non-all_time windows the last card is absent and Row 3 holds one card.

`ActivityHeatmap.tsx` is rewritten to take a `DaypartGrid` plus the registry — 4 wide
columns instead of 24 narrow ones, so the daypart labels fit inside the column headers and
the hour ruler underneath disappears.

## Tests

Pipeline (`pipeline/tests/`):

- `test_contract_dayparts.py` (new): registry partitions 24 h contiguously with no gaps,
  no overlaps and no wrap; grid dense at 28; every `daypart` id resolves; unknown id
  rejected.
- `test_aggregate.py`: bucket boundaries are `[from, to)` — 05:59 → night, 06:00 →
  morning, 11:59 → morning, 12:00 → afternoon, 17:59 → afternoon, 18:00 → evening,
  23:59 → evening.
- `test_aggregate.py`: weekend/weekday floored on their own student sets, and
  weekend + weekday == window message total when neither is suppressed.
- `test_contract_sections.py`: `semester_profiles` — week 1 anchors on `window.weeks[0]`;
  an in-progress semester emits fewer points than `len(window.weeks)`; `semester_week` is
  the full-membership index, not the covered index; `kind` matches the window id suffix.
- `test_floor_property.py`: extend the property sweep over the two new cell shapes.
- `test_schema_export.py`: regenerate `schema/aggregates.schema.json`.
- `test_validate.py`: a 1.5.0 document still validates (new fields optional).

Dashboard has no test harness; Parts 1, 2 and the layout are verified by eye across all
five windows, dark and light.

## Publish sequence

Schema bump → **re-aggregate and bundle redeploy in the same sitting** (D-51), or the
deployed dashboard renders the new cards as "not in this data release yet".

1. `run-weekly --skip-extract --skip-classify --out data/aggregates-review-<date>.json`.
   Corpus watermark stays 2026-07-14; do not mix a data refresh into a schema change.
2. Review: diff every `usage_context.totals` and `temporal_usage.weekly` against the
   previous publish — **identical in all five windows** is the claim this change makes
   about itself. Then sanity-check the new blocks against the tables above.
3. Upload blob + `latest.json`; redeploy the bundle; verify schema `1.6.0` live.
4. `docs/decisions.md` D-54 with the publish record; update contract §6.2, §6.3, §7.1 and
   the §12 example; update `CLAUDE.md` current-status line.

## Decisions settled with the owner (2026-07-30)

1. **Four equal six-hour dayparts**, not six uneven ones — owner's call, and the
   measurements above show it is better on bar honesty, on suppression, and on the
   sharpness of the weekday interaction.
2. **Semester overlay renders under All-time only.**
3. **Messages is the overlay's rendered measure**; active students published alongside.
4. **The heatmap coarsens to 7 × 4**; the 168-cell `activity_heatmap` field stays in the
   document because contract §10 forbids removing it within v1.

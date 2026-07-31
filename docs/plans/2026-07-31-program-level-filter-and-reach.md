# Program-level filter goes global; enrolled-cohort reach (D-55)

*Planned 2026-07-31. **Schema 1.7.0**, in two parts that ship together: the program-level
split moves from Topics-only to every tab, and the enrolled-cohort denominator adds the
reach percentages. Originally drafted as two bumps (1.7.0 then 1.8.0) and collapsed to one
during implementation — both parts land in the same publish, and a 1.7.0-without-enrollment
document would never exist in the wild. A schema version should name a document that does.*

## Why

The dashboard already knows every message's program level (D-39, usage-time rule at
session level) and already publishes a split for Topics (1.1.0) and a two-measure split
for Adoption (1.4.0). The split is reachable only from inside the Topics panel, one level
at a time, so four of the six tabs cannot answer "and what about the bachelors?" at all.

Separately, every count on the page is an absolute with no denominator. "66 active
bachelor students" is unreadable without knowing whether that is 66 out of 100 or out of
2,000. The coordinator roster lists give the second number.

## Decisions taken (owner, 2026-07-31 — recorded as D-55)

1. **Trends is hidden, not deleted** — dropped from the visible tab strip, still
   reachable at `?tab=trends`. Re-enabling is deleting one word.
2. **The filter is global**, in the header filter bar beside the window picker, with two
   binding conditions: the header sentence states the active level, and every tab either
   honours the filter or says in words why its scope differs.
3. **All four levels** are offered (bachelor, master, staff, and unknown when non-empty)
   plus *All users* last. **Bachelor is first and the default**, deliberately, on the live
   public dashboard.
4. **A "By program level" comparison card on every tab**, rendered under *All users*
   only — that is the view which otherwise carries no level information at all. Every
   card shows percentages.
5. **Secondary suppression is deferred.** See "Known gap" below.
6. **Adoption's "New registrations per week" chart is removed** — a registration does not
   imply a message, and the chart could not say so. The paired *New signups* KPI tile
   (signed up / sent at least 1 msg) stays: it is the honest form of the same fact.
7. **Enrolled totals come from programme enrollment only** (the SSC-Psych roster lists),
   committed to the repo as aggregate counts, and reach is shown for semester windows only.

## Part 1 — the split everywhere

### Contract additions (all optional; a 1.6.0 document stays valid)

| section | new field | contents |
|---|---|---|
| `temporal_usage.per_window[w]` | `by_status` | `daypart_heatmap`, `daypart_totals` per level |
| `temporal_usage` | `weekly_by_status` | `messages`, `sessions`, `active_students` per level |
| `usage_context.per_window[w].by_status[l]` | *extended* | adds `sessions`, `new_users`, `returning_users`, `user_classes` beside the existing `active_students`, `messages` |
| `sessions.per_window[w]` | `by_status` | both session histograms per level |
| `per_student.per_window[w]` | `by_status` | all three per-student histograms per level |
| `language.per_window[w]` | `by_status` | language totals per level |
| `language` | `weekly_by_status` | the four language series per level |
| `topics.per_window[w].by_status` | unchanged | already published since 1.1.0 |

**`activity_heatmap` is deliberately not split.** The 7×24 grid has been unrendered since
D-54 (`TimingTab` reads `daypart_heatmap`), and it is 44 KB of the current 246 KB. Adding
three more copies would buy nothing. It stays published, unsplit, until a separate
decision retires it.

**`new_registrations` is not split.** A registration has no session, so D-39's rule does
not reach it, and splitting only the `_active` half of a pair is worse than not splitting.
The *New signups* tile therefore renders under *All users* only — the same
scope-is-different treatment D-54 gave the semester overlay, and the reason decision 6
above did not need a rule extension.

### Aggregation

`aggregate.py`'s per-window loop currently computes each section inline against `w_msgs`
and `w_sessions`. The change extracts those bodies into functions of a subset, exactly the
shape `topic_group(subset)` already has — which is why Topics could gain a split cheaply
in the first place. Status is resolved per *session*, so every message in a conversation
shares one level and a conversation never has to be split across groups.

Sizing, measured rather than guessed: the current document is 246 KB minified / **28 KB
gzipped**. The full split lands near 440 KB / ~50 KB gzipped. Non-issue.

### Suppression, measured against the real corpus

Simulated at floor N = 3 before writing any of this (read-only, local):

| window | group | students | daypart grid | histogram cells | summaries |
|---|---|---:|---:|---:|---:|
| 2026S | all | 132 | 3/28 | 0/27 | 0/5 |
| 2026S | **bachelor** | 66 | 5/28 | 1/27 | 0/5 |
| 2026S | master | 58 | 4/28 | 1/27 | 0/5 |
| 2026S | staff | 8 | 6/28 | 8/27 | 0/5 |
| all_time | bachelor | 144 | 3/28 | 0/27 | 0/5 |
| 2025W | bachelor | 16 | 13/28 | 8/27 | 0/5 |
| trailing_4 | bachelor | — | *no bachelor activity at all* | | |

Bachelor and Master hold up in the windows that matter; Staff degrades but stays legible;
summary statistics survive everywhere. **`trailing_4` under the Bachelor default is
entirely empty**, which is why a `LevelGap` empty state is part of this change rather than
an afterthought.

### Known gap — secondary suppression (deferred by decision)

Messages partition exactly across levels, and the window total is published. So wherever
one level falls sub-floor while the others clear it:

```
bachelor_messages = totals.messages − master_messages − staff_messages
```

The suppressed cell is recoverable by subtraction. This is the same shape D-50 solved once
for `new_users`/`returning_users` with complementary suppression, generalised to a
three-way partition. It is **latent, not live** — no window in the current corpus has a
sub-floor status group — but expanding `by_status` across five sections multiplies the
surface. The fix is standard practice (primary + secondary suppression: suppress the
smallest published group in the partition too). Deferred by owner decision; revisit when a
publish first produces a sub-floor level group.

### Dashboard

- `ProgramLevelPicker` in the header bar beside `WindowPicker`; state and `?status=` URL
  param move up to `Dashboard.tsx` from `TopicsTab`.
- The header sentence gains the active level: *"…from StatsBot — bachelor students
  (between 02 Mar 2026 – 28 Jun 2026)"*.
- Each tab picks `by_status[level] ?? cohortWide` and renders `LevelGap` when the level has
  no data in the window.
- Topics' in-panel segmented control is deleted. Its distributions are untouched.
- `TabDef.hidden` hides Trends from the strip while `Dashboard` still accepts it from the
  URL. Trends renders under *All users* only — its findings are pipeline-computed
  cohort-wide.

### The three percentages

Conflating these is the main way this goes wrong, so each card states its denominator in
the column header:

| percentage | numerator ÷ denominator | where |
|---|---|---|
| **share of window** | level's actives ÷ window's actives | Adoption, Engagement level cards |
| **within-level profile** | level's daypart/language/theme messages ÷ that level's messages | Timing, Language, Topics level cards |
| **reach** (part 2) | level's actives ÷ level's *enrolled* | Adoption tile + level card, student rows only |

All are divisions of two published cells — the one client-side arithmetic invariant 4
allows, on the same licence `LanguageTab` already uses for language shares.

### The five level cards (under *All users* only)

- **Adoption** — Level | Active users + % of window | Messages + % of window | Reach (1.8.0)
- **Engagement** — Level | Students | median conversations | median messages | median
  conversation length | tried-once %. The tried-once share reuses `TriedVsAdopted`'s
  discipline exactly: first bin ÷ n_total, and never the complement, because a complement
  across bins can recover a suppressed bin.
- **Timing** — Level | Night % | Morning % | Afternoon % | Evening % | Weekend %, all
  within-level so groups of different size stay comparable.
- **Language** — Level | German % | English % | Other % | Undetermined %, within-level.
- **Topics** — emergent themes × levels matrix, within-level %. The one comparison a
  filter-flip genuinely cannot substitute for: 15 themes is past what a reader can hold
  across two clicks.

## Part 2 — enrolled cohorts and reach

### The denominators

Derived locally from the SSC-Psych roster Excels (2026-07-31; counts only — no identifier
left the password-protected medium, and the lists themselves never enter the repo):

| window | BA enrolled | MA enrolled | source |
|---|---:|---:|---|
| 2025S | 2,011 | 1,469 | `bachelor_students_apr_2025` + `master_students_mar_2025`, both typed and in-semester |
| 2025W | 2,196 | 1,444 | `..._nov_2025` combined snapshot, typed against the BA/MA unions + the D-39 usage-time rule |
| 2026S | 2,012 | 1,455 | `..._mar_2026` combined snapshot, same method |

The two combined snapshots carry no program column. They become typeable because a uid in
an older BA list and a newer MA list is a transitioner, and the *same* rule `resolve_status`
applies in the pipeline decides which side of the boundary they fall on — using a different
rule here would put numerator and denominator on different definitions of "master".
Untyped residual 1.6%. Three independently-produced snapshots typed through an
independently-built union land within a few percent across 18 months, which is the check
that says the method holds.

Resulting reach: BA 3.1% / 0.7% / 3.3% and MA 7.6% / 4.4% / 4.0% across 2025S / 2025W /
2026S. The 2025W bachelor figure is a real finding, not noise — bachelors only got access
2025-05-16, and statistics is a summer-semester subject.

### Plumbing

`pipeline/cohort_totals.json`, committed. The numbers are non-identifying aggregate
headcounts that land on a public dashboard anyway, they are few, and a committed table is
diffable and reviewable in the go-live gate. Chosen over a git-ignored CSV plus an import
command and a corpus table: no new migration, no corpus lock, no pepper, and nothing about
this needs to be re-derived per publish. Each entry carries `source` and `as_of`.

`docs/ethics/data-handling.md` gains a line: aggregate cohort sizes are repo-eligible; the
lists they come from are not.

### Contract

A top-level `enrollment` block keyed by window id — **not** inside `usage_context`. It is
not a measurement: it never passes `floored_count`, because there is nothing to floor. An
institutional headcount is not a count over students who wrote messages, and putting it
among cells that were floored would invite exactly that misreading.

```json
"enrollment": { "per_window": { "2026S": {
    "bachelor": 2012, "master": 1455,
    "source": "SSC-Psych roster lists (bachelor_and_master_students_mar_2026)",
    "as_of": "2026-03-01" } } }
```

Semester windows only. Reach for `all_time` would span three semesters of cohort turnover
and `trailing_4` is currently four July break weeks; neither has a defensible denominator,
so neither gets one — stated as a scope decision in words, never as a `WindowGap` that
would frame a design choice as missing data.

Reach shows on the *Active users* tile only when a single level is selected. Under *All
users* there is no line: BA + MA enrolled is not a denominator for a numerator that
includes staff.

### Notes on every card that shows an enrolled total

- Provenance: *"Enrolled totals come from SSC-Psych records."*
- Scope caveat (owner wording): *"totals include all enrolled bachelor/master students,
  whereas only the first-year students take the statistics course — data for how many
  first-year students take it across instructors is not available."*

## Part 3 — summary-statistics wording (the `n` fix)

`StatCallout` prints `n = 132 students · median 2 · middle 50% 1–4 · mean 3.1 (SD 3.2)`
and never names what is being measured. Worse, on session-level cards it prints
`n = 132 students · 414 sessions · median 2 · …` — where the median is over **414
conversations** and the 132 is the floor's contributing-student count, not the sample size
of the summary. A reader binds the first number to *n*; in a thesis table that is an error.

Fix, applied to every card the strip appears on:

- `n` follows the unit of observation. Session-level: `n = 414 conversations (132 students)`.
- The measured quantity is named: `median 2 conversations`.
- The quantile definition (`quantile_type2`, R type 2) is stated in the hover alongside the
  existing IQR gloss — it is why *Weeks active* reads "median 1.5" on integer data.

## Order of work

1. Plan + D-55 recorded.
2. **Pipeline**: contract shapes, aggregation refactor, footnotes, `cohort_totals.json`,
   the `enrollment` block, tests.
3. **Dashboard**: global picker, header echo, per-tab wiring, five level cards, reach,
   Trends hidden, Topics control removed, `StatCallout` fix.
4. `pytest` + `ruff` + `mypy` + `pnpm build`, then `/go-live` (both halves — a schema bump
   needs the bundle as well as the blob).

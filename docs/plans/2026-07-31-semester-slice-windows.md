# Semester slice windows replace `trailing_4` (D-56)

*Planned 2026-07-31. **Schema 1.8.0.** The `trailing_4` window is removed and every
semester gains two sub-windows — its last covered week and its last (up to) four covered
weeks — so "recent" is anchored to teaching time instead of to the axis tail, and the same
lens can be pointed at any past semester for cross-semester comparison.*

## Why

`trailing_4` is anchored on the **axis**, which advances with extraction regardless of
whether anyone was in class. Measured on the live 1.7.0 document (2026-07-31):

| window | weeks | messages | students | bachelor | master | staff |
|---|---|---|---|---|---|---|
| **`trailing_4` (live)** | W27–W30 | **10** | **3** | **0** | 3 | 0 |
| SS 2026, last covered week | W26 | 86 | 22 | 16 | 3 | 3 |
| SS 2026, last 4 covered weeks | W23–W26 | 385 | 54 | 34 | 17 | 3 |
| *(whole SS 2026, for scale)* | W10–W26 | 986 | 132 | 66 | 58 | 8 |

The live "Last Avl. 4 weeks" holds **zero bachelor students**, and bachelor is the default
program level (D-55) — the default landing state of that filter is a blank page. Language
totals are `suppressed` in every cell. D-49's calibration already found 62 of 69
`trailing_4` trend candidates failing the floor in the July break.

The replacement costs nothing in term time: **during teaching weeks the last four axis
weeks *are* the last four semester weeks**, so the new windows are identical to what
`trailing_4` shows today. They diverge only across breaks — roughly a third of the year —
where the old definition degrades to noise and the new one keeps pointing at the last
weeks that meant something.

Two rollover behaviours were verified by running `build_windows` against simulated axes at
each calendar boundary rather than reasoned about:

| "today" | axis ends | anchor semester | last week | last 4 weeks |
|---|---|---|---|---|
| 31 Jul 2026 (break) | W30 | 2026S | W26 | 4w W23–W26 |
| 1 Oct 2026 *(WS starts)* | W39 | 2026S | W26 | 4w W23–W26 |
| 12 Oct 2026 | W41 | **2026W** | W41 | **2w** W40–W41 |
| 19 Oct 2026 | W42 | 2026W | W42 | **3w** W40–W42 |
| 10 Mar 2026 | W10 | 2026S | W10 | **1w** W10 |
| 25 Nov 2026 | W47 | 2026W | W47 | 4w W44–W47 |

- The anchor lags the calendar by about a week at each term start, because the axis holds
  complete weeks only. Inherent, unchanged from `trailing_4`, not worth fixing.
- **A four-week window holds fewer than four weeks for the first three weeks of every
  semester.** `trailing_4` clamped silently (`axis[-4:]`, pinned by
  `test_trailing_clamps_to_short_axis`) — which is the same disease the "Last **Avl.** 4
  weeks" rename papered over. The label must state the count it actually has.

## Decisions taken (owner, 2026-07-31 — recorded as D-56)

1. **`trailing_4` is removed, not kept alongside.** Break-period activity keeps its
   representation in `all_time` and in the weekly series; it loses its own distribution
   view (topics, dayparts, session shapes). Accepted: those weeks are sub-floor by
   construction.
2. **Slices are published for *every* semester, not only the anchor** — the whole point
   is comparing one term's closing weeks with another's.
3. **The single-week slice is the semester's last *covered* week**, never "the last week
   clearing the privacy floor". A teaching week nobody used is a finding; a floor-seeking
   rule would silently redefine the window on every publish.
4. **Labels are state-dependent**: `Latest` while the semester is in progress, `Final`
   once it has ended. Same week-set, two different questions — "how is it going" vs "how
   did the term close".
5. **Reach is published for slices** (D-55's "semesters only" rule relaxed *in the reader*,
   not in the contract — see below).
6. **Trends does not cover slices, knowingly.** The tab is hidden for this release
   (D-55), so rather than decide a pairing rule under no user pressure, slices are
   excluded from the trends pass entirely. See "Trends is left behind on purpose".
7. **Slices publish their semester-week span but nothing renders it.** It does not change
   what an educator reads, but it keeps the document self-describing and lets a later
   client or pipeline pass align two semesters without recomputing the index.
8. **The gzip middleware ships in this change but is tracked and committed separately**
   so it can be reverted on its own if it misbehaves in App Service.

Work is split across two GitHub issues, and every commit references the one it belongs to:
**#8** (semester slice windows) and **#9** (gzip the aggregates API response). Issue **#3**
— the D-52 follow-up on surfacing extraction lag — stays open: this change removes lag's
*worst* symptom (a "recent" window drifting into unmeasured break weeks) but says nothing
about how stale `data_through_date` is, which is what #3 asks for.

## The registry change

`TrailingWindow` stops being emitted and is replaced by:

```python
class SemesterSliceWindow(BaseModel):
    kind: Literal["semester_slice"]
    id: str                  # "2026S.last4" | "2026S.last1"
    label: str               # self-contained: "Final 4 weeks · Summer semester 2026"
    short_label: str         # inside its group: "Final 4 weeks"
    parent_window_id: str    # "2026S" — validated to be a semester window
    weeks: list[WeekId]
    semester_weeks: list[int] # [first, last] teaching week, 1-based, e.g. [14, 17]
    coverage: Coverage
```

`semester_weeks` is published and deliberately **not rendered**: SS terms run 17 weeks and
WS terms 18, so a cross-semester comparison of "final 4 weeks" spans different teaching
weeks on each side. That does not change what an educator reads off the page, but it makes
the document say so itself instead of leaving a future reader to re-derive it.

It is indexed against the parent's **full Thursday-rule membership**, never its coverage —
the D-54 invariant. `parent.weeks.index(w) + 1`, exactly as `SemesterProfilePoint` does it.
Indexing against covered weeks would slide a semester whose opening weeks fall outside the
axis, and every alignment built on it would be silently wrong by that many weeks.

`AllTimeWindow` and `SemesterWindow` gain `short_label` too (`"All time"`,
`"Whole semester"`), so the picker stays a pure renderer of pipeline-authored copy — the
D-52 property that let a label change ship as a blob upload with no code deploy. **Optional
on those two**, required on slices: see Rollout for why that is load-bearing rather than
lax.

`TrailingWindow` is **deprecated and unemitted, not deleted** — also Rollout.

### Generation rule (`windows.py:build_windows`)

For each semester window, let `C` = its covered weeks (membership ∩ axis), `n = len(C)`:

- `{sem}.last1` — emitted whenever `n >= 1`; `weeks = C[-1:]`.
- `{sem}.last4` — emitted whenever `n >= 2`; `weeks = C[-min(4, n):]`.
  At `n == 1` it would duplicate `.last1` exactly, so it is omitted rather than published
  as a second name for the same week-set.

Labels, with `running = coverage.through < weeks[-1]` (the existing `isInProgress` rule,
computed pipeline-side):

| | in progress | completed |
|---|---|---|
| `.last1` | `Latest week` | `Final week` |
| `.last4`, 4 covered | `Latest 4 weeks` | `Final 4 weeks` |
| `.last4`, 2–3 covered | `Latest 3 weeks` | *(cannot occur)* |

`label` is the short label plus `" · "` plus the *abbreviated* semester name
("Final 4 weeks · SS 2026" — owner's wording), generated beside the long form so the two
cannot drift. The count in the label is
the true count; the `4` in the **id** names the rule's cap, not a fact about the window,
and is documented as such in `docs/aggregates-contract.md` §6.1.

**Window ids become permanently stable**, which `trailing_4` never was: a link to
`?window=2026S.last1` means the same four-week span forever once SS 2026 has ended.
`trailing_4` meant something different at every publish, so no shared link to it was
reproducible.

### Ordering

`build_windows` emits `all_time`, then for each semester in axis order the semester
followed by its slices (`.last4`, `.last1`). Registry order is the pipeline's statement of
display order and the dashboard already relies on it.

## Dashboard

### Picker regrouped by parent (`lib/windows.ts`, `WindowPicker.tsx`)

```
Summer semester 2026 (in progress)     Winter semester 2025/26        Everything
  Whole semester                         Whole semester                 All time
  Latest 4 weeks                         Final 4 weeks
  Latest week                            Final week
```

`groupedWindows` becomes: for each semester (newest coverage first) emit a group labelled
with the semester's `label`, containing the semester itself followed by every window whose
`parent_window_id` matches; then a final `Everything` group for `all_time`. The `"Recent"`
group disappears. The `(in progress)` marker moves from the option to the **group
heading**, where it describes the semester rather than one lens on it.

`defaultWindowId` is untouched — it filters `kind === "semester"`, so the default landing
state stays *whole latest semester*.

### Reach follows the parent (`lib/levels.ts`)

`enrolledFor` currently reads `doc.enrollment?.per_window?.[win.id]`. It gains one
fallback: if the window has a `parent_window_id`, read the parent's entry. This means
**`contract.py:_check_enrollment` does not change** — enrollment stays keyed by semester
ids only, one headcount per semester, no duplication of an institutional number across
seven keys.

A new footnote is required, because reach changes meaning inside a slice:

> `reach_window_scope` — Reach is measured against the enrolled cohort of the semester
> this window belongs to, so in a shorter window it reads as the share of that cohort
> active during those weeks, not over the whole term.

`AdoptionTab` adds it to the resolved footnote set when the selected window is a slice.

### Two rendering defects the one-week slice would expose

1. **`TrendChart` renders nothing for a single-row dataset with multiple series.**
   `dot={single ? {...} : false}` at `cells/TrendChart.tsx:152` keys on the *series* count,
   so the Language tab (de/en/other/undetermined as separate lines) draws a polyline with
   one vertex and no dots — a blank chart. Fix: enable dots when
   `series.length === 1 || rows.length === 1`. This is a latent bug today; the slice just
   makes it reachable.
2. **`weeks_active_per_student` is definitionally 100 % in bin 1** in a one-week window.
   The dashboard hides that one card when `win.weeks?.length === 1` and says why —
   *"Weeks active is not meaningful in a single-week window: every active student is
   active in exactly one week by definition."* Hiding client-side rather than omitting it
   from the document is deliberate: an absent block renders as "not in this data release
   yet", which would misattribute a definitional property to the publish. The histogram
   stays in the document, where it remains correct.

`user_classes` stays published in one-week slices: `monthly` is unreachable under 30 days,
which the existing `user_class_window` footnote already states, and the `one_time` /
`sporadic` split still answers "did they come back later in the week".

## Trends is left behind on purpose (owner, 2026-07-31)

Trends is hidden from the tab strip for this release (D-55), so no pairing rule is decided
here. But "don't implement it" is not the same as "don't touch it", and the difference
matters:

`trends.py:_pair_for` dispatches on `kind`, and its final branch — written for
`trailing_4` — computes a baseline from the **axis tail** (`axis[-8:-4]`). Slices would
fall into that branch and be silently compared against whatever weeks sit at the end of the
axis: break weeks, for months at a time. The findings are published and floor-checked even
though nothing renders them, so this would put **wrong comparisons into the document**, not
merely leave a feature unbuilt.

So the minimum correct action is to **exclude slices from the trends pass**:
`assess_windows` skips `kind == "semester_slice"`, and `sections.trends.per_window` keeps
covering exactly the semesters and `all_time` it covers today. Nothing is computed, nothing
wrong is published, and the existing empty state carries it: selecting a slice under
`?tab=trends` renders `WindowGap` — *"No trends rollup is published for Final week · Summer
semester 2026"* — which is literally true.

**Known divergence, to be recorded in `docs/decisions.md` as part of D-56:** from 1.8.0 on,
the windows registry and the trends section no longer cover the same set of windows. Any
work that un-hides Trends must decide slice pairing first. The leading candidate is *the
same slice of the chronologically previous semester*
(`WindowBaseline(window_id="2025W.last4")`) — consistent with how semester windows already
pair, and the comparison that motivated per-semester slices in the first place — with no
baseline when the counterpart is missing or of a different length.

## API: response compression

Adding six windows grows the document from **437 KB to roughly 670 KB** uncompressed. The
API currently ships **no compression at all** — verified against the live service, which
returns 393 KB whether or not the client sends `Accept-Encoding: gzip`, and there is no
`GZipMiddleware` in `api/app/main.py`. The live document gzips to **24.6 KB (6.3 %)**.

Three lines (`app.add_middleware(GZipMiddleware, minimum_size=1000)`) make the payload
question disappear for this change and every future one, and also compress the static
bundle the same app serves (D-26).

Worth noting that the ADRs have been *sizing* this document by its gzipped figure for a
while — D-55 records "28 → 43 KB gzipped" — while the service has been shipping it
uncompressed the whole time. The number in the decision log was the number we wished were
true.

It ships in this change but lands as **its own commit against issue #9**, touching only
`api/app/main.py` and its test, so a revert is one commit and does not disturb the window
work. It is the one part of this plan that can fail in a way local testing will not catch
(App Service front-end behaviour, `Content-Length` on a streamed static bundle), which is
exactly why it is isolated.

## Work items

**Pipeline**
- `contract.py`: drop `TrailingWindow`, add `SemesterSliceWindow`, add `short_label` to the
  other two kinds, validate `parent_window_id` resolves to a semester window.
- `windows.py`: `TRAILING_WEEKS` → `SLICE_WEEKS`; emit slices per semester with the label
  rules above; drop the trailing window.
- `trends.py`: `assess_windows` skips `kind == "semester_slice"` — slices get no trends
  entry at all (see above). `_pair_for` loses its trailing branch with `TrailingWindow`.
- `aggregate.py`: `_window_weeks` already handles any window carrying `weeks` — verify no
  other branch keys on `kind == "trailing"`. New `reach_window_scope` footnote in the
  registry.
- `export_schema.py`: regenerate `schema/aggregates.schema.json`; bump to 1.8.0.

**Dashboard**
- `pnpm gen:types` → `lib/aggregates.gen.ts`.
- `lib/windows.ts`: `groupedWindows` by parent; keep `sliceToWindow`/`isInProgress` as is.
- `lib/levels.ts`: `enrolledFor` falls back to the parent window.
- `WindowPicker.tsx`: render `short_label`, in-progress marker on the group heading.
- `cells/TrendChart.tsx`: single-row dot fix.
- `cells/EmptyState.tsx`: a fourth empty state, `MeasureUndefined` — the measure is
  correct but the window makes its question vacuous. Distinct from pending / window gap /
  level gap, and worth its own words.
- `tabs/EngagementTab.tsx`: weeks-active card and the "Tried once" column withheld in
  one-week windows.
- `tabs/AdoptionTab.tsx`: `reach_window_scope` footnote for slices.
- `dev-fixtures/generate.mjs`: emits slices and `short_label`. Also gained a real
  `fullMembership()` — it had been indexing `semester_week` against *coverage* while its
  own comment claimed full membership, so the design fixture disagreed with the pipeline
  by one week. Fixed here because slices publish the same index.

**API**
- `main.py`: `GZipMiddleware`.

**Tests / fixtures**
- `test_windows.py`: replace the three trailing tests — ids and ordering, clamping with a
  truthful label, no `.last4` at n = 1, `Latest`/`Final` by state, `semester_weeks` indexed
  against full membership (a semester whose opening weeks fall outside the axis is the case
  that catches a coverage-indexed regression), and **a break-only axis yields no semesters
  and therefore no slices at all** (picker shows only *All time*).
- `test_trends.py`: slices get no trends entry — the assertion that pins decision 6, so
  that "we deferred this" cannot silently become "we shipped an axis-tail baseline".
- `factories.py` `WINDOW_IDS`, `test_aggregate.py` (expected id lists), `test_cli.py`
  (`preview-trends --window`), `test_contract_windows.py`, `test_contract_levels.py` (its
  comment asserting only semesters have a denominator is now half-wrong — slices inherit
  one through their parent).
- Regenerate `dashboard/dev-fixtures/aggregates.fixture.json` via `run-synthetic`.

## Rollout

**Corrected during implementation.** The plan above originally called the interim states
"cosmetic only". They were not, and the reason generalises: **the API validates every blob
it fetches against the schema it ships with** (contract §11), so a schema change that makes
the *other* half's document invalid is a 500, not a degraded render — for however long the
two halves are out of step, in whichever order they are done.

Measured against the real published document: a 1.8.0 schema with `TrailingWindow` removed
and `short_label` required **rejects the live 1.7.0 blob** on `windows[4]` (`kind:
"trailing"` matches no union member). Deploying the API first would have taken the
dashboard down until the upload landed; uploading first takes it down under the old API,
which cannot parse `semester_slice`. There was no safe order.

Two changes fix it, both now in place and both pinned by
`test_a_pre_1_8_0_document_still_validates`:

1. **`short_label` is optional** on `all_time` and `semester` (required on slices).
2. **`TrailingWindow` stays in the union, deprecated and unemitted**, until no reachable
   blob contains one. This makes the *deploy* safe in one direction; it does not make a
   rollback free once the new blob is up, since a 1.7.0 API cannot parse `semester_slice`
   — reverting the code after publishing also means restoring the previous blob.

With those, the live document validates under 1.8.0 and the interim states really are
cosmetic:

- **Old document, new bundle** (the deploy-first order, now safe): no slices exist, the
  picker shows each semester with only "Whole semester" under it plus All time, and
  `trailing_4` is dropped from the picker because `groupedWindows` groups by parent. The
  page renders.
- **New document, old bundle**: would 500 on the old API's schema — so **deploy the bundle
  and API first, then upload the blob**, not the other way round. This is a change from the
  D-51 habit of uploading first, and it is the order this schema requires.

Both halves still go in the **same sitting** (D-51).

Publish mode: **re-aggregate only** (`--skip-extract --skip-classify`). This change must
not move a number that exists today, and the review gate is exactly that claim — every
pre-existing window's sections byte-identical to the previous publish, with only the six
new window keys added. Mixing a data refresh into it would forfeit that check (the D-53
lesson).

Commits reference their issue (#8 for the window work, #9 for the middleware), so the
compression change can be reverted without unpicking the registry change.

## Carried forward

- **Trends pairing for slices** — deferred with the tab (decision 6). Blocks un-hiding
  Trends, not this release.
- **Issue #3 — surfacing extraction lag.** Independent of this change and still open.
  Semester anchoring removes lag's worst symptom, since a "recent" window can no longer
  drift into weeks nobody was measured in, but the axis boundary itself is still derived
  from `now` until an extract writes the first `last_extracted_at` watermark, and nothing
  on the page says how stale `data_through_date` is.
- **Secondary suppression** — deferred at D-55, untouched here. Slices are smaller windows
  and therefore hit the floor more often, which makes complementary suppression more
  visible, not more dangerous: no new cell class is published.

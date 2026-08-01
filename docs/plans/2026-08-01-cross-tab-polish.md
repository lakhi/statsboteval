# Cross-tab polish: fewer repeated caveats, two pies, three reorderings (D-59)

> **Status 2026-08-01: built, not yet published.** Schema moved to **1.9.0** (the signup
> split). Pipeline suite green (424 passed), `pnpm lint` + `pnpm build` clean, dev fixture
> regenerated. Outstanding: the browser walk-through of the matrix in §Verification, and
> both go-live halves. Decisions recorded as D-59 in `docs/decisions.md`.

*Planned 2026-08-01, the day D-58 was built. **No schema change — stays 1.8.0**, unless
open decision **Q1** is answered "split signups by level", which makes it 1.9.0. Fifteen
requests across all five tabs, in three families: (a) caveats that repeat themselves come
off the page, (b) three cards move to the top of their tab, (c) two part-to-whole tables
gain a pie and one provenance note gains its source.*

## Why (owner request, 2026-08-01)

The tabs have accumulated one caveat per publish since D-50. Each was right on its own
day; read together, the same roster rule is now stated up to three times on one screen,
and the two Timing notes restate what the chart's own axis labels already print. The
reader is an educator scanning a tab, not a reviewer reading table notes end to end —
the same premise as D-58, applied to what D-58 did not reach.

Nothing here changes a number. Every item is copy, placement, or a second rendering of a
figure that is already on the page.

---

## Decisions taken 2026-08-01 (record as D-59)

1. **New signups get a real per-level split** (A2), schema **1.9.0**. The coverage probe
   ran 2026-08-01 against `pipeline/data/corpus.duckdb` and came back **550 / 550**:
   298 master, 206 bachelor (36 of them transitioners), 46 staff, **zero registrants
   without a roster row**. 131 of the 550 never wrote a message — which is exactly the
   population this split makes visible, and the reason the usage-time rule could not
   reach them.
2. **The roster-rule tip comes off Active users outright** (A1). The ⓘ after "enrolled
   bachelor students" stays. Accepted consequence: on a level-filtered Adoption tab the
   roster rule is stated nowhere; it survives on the By-program-level card (All users) and
   on four other tabs. This reverses D-58 decision 6, one day old.
3. **"…then reviewed and frozen as the versioned set …"** (C1) — passive, attribution
   dropped.
4. **Language's figures move into the collapsible `Data table` disclosure** (E2), the same
   affordance every other chart card uses. Because that removes the always-visible text
   channel the four language colors currently lean on, **the donut's legend carries the
   label, count and share per language** — the figures stay on screen, in the legend
   rather than in a table, and the disclosure holds the full tabular twin.
5. **The Topics tab gets a crisp "How these labels were produced" block** (C.iii), ~65
   words, collapsed by default, under the panel deck.

---

## A · Adoption

### A1 — the roster-rule tip comes off Active users · **decided**

Delete the `tip` on the Active-users `KpiTile` and the `statusRuleNote` binding behind it
(`AdoptionTab.tsx:150`, `:220-226`). This **reverses D-58 decision 6**, which put it
there one day earlier; record the reversal in D-59 rather than editing D-58.

The `InfoTip` component stays — the reach tile still uses it.

### A2 — New signups under bachelor / master / staff · **probe, then branch**

Today the tile renders numbers under All users and a dashed explanatory box under any
single level (`AdoptionTab.tsx:295-311`), because D-55 held that a registration has no
session and therefore no usage-time level.

That reasoning is about the *implementation*, not the data. `student_status` is keyed by
pseudonym and carries `ma_start_semester`; `students` carries `registered_at`. So
`resolve_status(status_rows.get(pseudonym), registered_at)` — the same function, the same
rule, keyed on the registration instant instead of the session start — resolves it.

**Probe first** (read-only, local corpus, ~1 minute):

```sql
SELECT COALESCE(s.status, 'no roster row') AS level, count(*)
FROM students st LEFT JOIN student_status s USING (pseudonym)
GROUP BY 1 ORDER BY 2 DESC;
```

`students` includes registrants who never wrote (that is why 119 signed up and 87 wrote),
so coverage is an open number, not an assumption. If "no roster row" dominates, the split
is an `unknown` bar with three slivers beside it and branch (b) wins by default.

| branch | condition | what ships | cost |
|---|---|---|---|
| **(a) split** — preferred | roster covers most registrants | `new_registrations` + `new_registrations_active` become optional fields on `UsageContextByStatus`; new footnote `signup_level_rule` ("a signup has no conversation, so its level is read from the roster at the registration date rather than at usage time"); schema **1.9.0**; `aggregates.gen.ts` regenerated; API redeployed with the new schema | pipeline + contract + tests + fixture + both go-live halves |
| **(b) cohort-wide** — fallback | probe shows thin coverage | the tile renders `roll.totals` under every level, with the existing `level_scope` footnote as its note | bundle only, ~20 lines |

Under (a) the tile's meaning changes subtly: every other number on a bachelor-filtered
Adoption tab is resolved at usage time, this one at signup time. One footnote covers it;
that is what `signup_level_rule` is for.

### A3 — By program level: to the top, with a pie, without the disclosure

**i. Position.** The card moves out of the two-column grid it shares with User classes and
becomes the tab's first block, full width, above the KPI row. Consequence worth stating:
the tab then opens on a breakdown before the totals it decomposes, and because the card
renders only under All users, switching to Bachelor makes the KPI row jump to the top.
Both are the direct consequence of the request; noted, not argued.

**ii. Pie.** A donut of active users by level, below the `Note.` paragraph, inside the
same card. Three rules, all forced by the data rather than by taste:

- **Denominator is the sum of the published level cells, not the window total.** A
  BA→MA transitioner is counted under both levels (`status_multi`), so the levels can sum
  past the window total by a few. A pie whose slices are drawn against the window total
  would then over-fill; drawn against their own sum it is exact, and the caption says
  "share of the levels shown".
- **Any suppressed level cell → no pie**, table only. A slice that silently omits a
  withheld level asserts it is zero, which is precisely what `floored_count` exists to
  prevent.
- **Colors are the four existing tokens** — bachelor `--color-accent`, master
  `--color-series-en`, staff `--color-series-other`, unknown `#6e6c66` (the same neutral
  "no identity worth a hue" gray Language gives *Undetermined*). No new palette.

Center of the donut carries the window's active-user total, so the pie answers "how
many, split how" in one glance.

**iii. Disclosure.** Drop the `table` prop for this card only (`ProgramLevelCard` gains
`table?: boolean` defaulting to true, or the caller passes `showTable={false}`). The
card's own figure *is* an accessible `<table>` with a `<caption>`, so the collapsible twin
duplicates it verbatim — the one card on the dashboard where that is true. Every other
`ProgramLevelCard` caller keeps its disclosure: **do not** remove the prop from the shared
component.

---

## B · Engagement

**Weeks active per student moves first** (`EngagementTab.tsx:250-274` moves above
`:224`). It carries the tab's headline finding (`TriedVsAdopted`: "*N* of *M* students
wrote in only one week"), which is the answer to "how deeply do students engage?" — and it
currently sits third, below two distributions.

The `isSingleWeek` branch moves with it unchanged: in a one-week window the block is the
`MeasureUndefined` card and now leads the tab, which is the honest thing for a window
where the measure is degenerate.

Rewrite the editorial comment at `:211-213` — it argues for the D-53 order and would
otherwise be left contradicting the code beneath it.

---

## C · Topics

### C1 — theme-set sentence

`emergentMethodNote()` (`TopicsTab.tsx:147-158`): "reviewed by the project team and frozen"
→ "**reviewed and frozen**".

### C2 — `status_rule` leaves the four topic cards

The § appears only under a single level: `topic_distribution(..., with_status_rule=True)`
adds it to every `by_status` distribution (`aggregate.py:1004`). Remove it there —
**pipeline-side, not a dashboard filter** — so the document stops claiming a caveat the
page does not render. `with_status_rule` becomes dead and goes with it, along with the
parameter threaded through `topic_group`.

Kept deliberately: `status_rule` on the **Emergent themes by program level** card at the
bottom of the tab. That card only exists under All users, where comparing levels is the
whole point of the card and the rule is load-bearing rather than repeated.

Test to update: `test_aggregate_topics.py:133` asserts
`["multi_label", "label_provenance", "status_rule"]` → drop the third id. Contract §6.2's
`status_rule` row keeps its text (four other cards still reference it); the topics section
description in the contract needs the id removed from its example.

### C3 — provenance for Statistical methods and Analysis software

Both lists are **Bergmann et al.'s published frozen lists**, not our own: `method_themes`
(21 themes, from `Table4_s1_spec_meth_frequ.csv`) and `software_themes` (9 tools, from
`Table4_s2_softw_frequ.csv`), both from the Stage-2 OSF folder
(`bergmann-materials/README.md`). What is *ours* is the assignment — our
`statsboteval-v2` classifier labels each message against the list.

Add the owner's sentence as a card note on both (dashboard prose, like
`emergentMethodNote` — **verbatim**, no count interpolated):

> Frozen list from Bergmann et al.'s published materials; labels assigned by our
> classifier where the message names the method explicitly.

This is a distinct claim from the `label_provenance` footnote, which names the classifier
but says nothing about where the *list* came from.

### C4 — the suppression key comes off those same two cards

`TopicCard` passes `suppressionKey="A gray tick instead of a bar is a suppressed
category"` whenever any row is withheld (`TopicsTab.tsx:116`, `:127`); `ChartCard` appends
the floor clause. Suppress that prop for `method_themes` and `software_themes` only —
the emergent and deductive cards keep it.

Defensible because the tick is not left unexplained: `rowTip` already says
"Fewer than 3 students in *window* wrote messages the automated classifier flagged with
this method, so the count is withheld — not zero" on the row's own hover, and the
collapsible data table prints `suppressed` as text for the keyboard/screen-reader path.
What is lost is the at-a-glance legend; what is gained is that the two cards whose notes
now carry provenance do not also carry a third sentence.

### C5 — "How these labels were produced"

One collapsed `<details>` under the panel deck, ~65 words, draft:

> Messages are classified one at a time by an automated classifier
> (`statsboteval-v2` — GPT-5-mini, fixed seed, ten messages per call). Each message is
> judged on its own text — the student's message, not StatsBot's reply — and may carry
> several labels or none. The deductive categories and the method/software lists come
> from Bergmann et al.'s published materials; the emergent themes were generated from
> these chats and frozen after review.

Model name and batch size are stated because they are the two facts D-41/D-45 made
load-bearing for how the numbers should be read. `statsboteval-v2` is read from
`doc.label_versions.classification`, never hardcoded — the dashboard holds no label
version (CLAUDE.md).

---

## D · Timing

### D1 — `daypart_definition` loses its first two sentences

```
- Times are Vienna local. The day is split into four equal six-hour blocks — night 00–06,
- morning 06–12, afternoon 12–18, evening 18–24 — so the bars are directly comparable.
  Each block counts the messages sent inside it, so a chat that runs past a boundary
  contributes to both.
```

Safe to cut because **both cards already print the hour ranges themselves**:
`DaypartBars` renders `Night 00–06` beside every bar (`DaypartBars.tsx:72-77`) and
`ActivityHeatmap` prints them under each column header (`ActivityHeatmap.tsx:46-47`).
"Vienna local" is in the panel deck one line above. What the sentence added that the
chart does not was the *interpretive* clause "so the bars are directly comparable" — and
the equal cutting stays visible in the printed ranges.

The **pipeline invariant is untouched**: the blocks stay four equal six-hour bins
(`DAYPARTS`, `_daypart_of`), and CLAUDE.md's "the equality is load-bearing" line is about
the cutting, not about the sentence. Update the comment above the footnote entry
(`aggregate.py:195-196`) — it currently explains why the deleted clause exists — and
`DaypartBars.tsx:6-7`, which says the footnote says so on the card.

This is a **data change**: the text travels in the blob, so it needs the data half of
go-live as well as the bundle.

### D2 — Active students per week loses its second sentence

Dashboard prose (`TimingTab.tsx:250-257`), keep the first sentence:

> A student counts in any week they sent at least one message.

---

## E · Language

### E1 — order

| position | All users | single level |
|---|---|---|
| 1 | By program level (full width) | — |
| 2 | Totals — *window* (pie, 2 of 5 cols) | Totals (first card) |
| 3 | Messages by language per week (3 of 5 cols) | same |

Implementation is a reordering inside the existing `lg:grid-cols-5` grid: the level card
moves from the bottom to the top keeping `lg:col-span-5`, and Totals and the weekly chart
swap column order.

### E2 — Totals becomes a donut with a legend, table collapsed

Same `PieShare` component as A3, same rules (published cells only; suppressed language →
table only, no pie), colors already defined per language in `LANGS`. Center of the donut:
the window's message total.

The messages/share table moves into the standard collapsible `Data table` disclosure
(decision 4). To keep the figures on screen, **the legend carries them**: one row per
language with its swatch, label, message count and share — which is the table's content
in legend form, and keeps color from being the only channel for the aqua and yellow
slices (`LanguageTab.tsx:20`). The disclosure below holds the full `DataTable`.

The "shares need this window's published messages total" fallback line
(`LanguageTab.tsx:188-193`) stays: without a denominator the legend shows counts only.

`Other` at 0% is a real published zero and keeps its legend row with a `0` — a measured
zero is not identifying and must not read as absence (the `floored_count` rule, applied to
display).

---

## New shared component

`src/components/cells/PieShare.tsx` — recharts `PieChart`/`Pie`/`Cell` (already a
dependency; `TrendChart`, `HistogramChart` and `SemesterOverlay` all use it). Props:
`slices: {key, label, value, color}[]`, `total`, `centerLabel`, `ariaLabel`. Renders
nothing and returns `null` when any contributing cell is suppressed — the caller decides
what to show instead. `role="img"` + `aria-label` naming the largest slices, matching the
`DaypartBars`/`ActivityHeatmap` pattern.

**Load the `dataviz` skill before writing it** (house rule for any new chart) — it governs
the label/legend treatment and validates the four-token palette in light and dark.

---

## Data diffs (blob) — review these first

| id | change |
|---|---|
| `daypart_definition` | **40 → 20 words.** Keeps only: "Each block counts the messages sent inside it, so a chat that runs past a boundary contributes to both." |
| topics `by_status` `footnote_ids` | `["multi_label", "label_provenance", "status_rule"]` → `["multi_label", "label_provenance"]` |
| `signup_level_rule` | **new, only under Q1 branch (a).** |

Everything else on this page is bundle-only.

## Work inventory

### Pipeline

| file | change |
|---|---|
| `aggregate.py` | `FOOTNOTES["daypart_definition"]` text + its comment; drop `with_status_rule` from `topic_distribution`/`topic_group`; *(Q1a)* level-resolved signup cells |
| `contract.py` | *(Q1a only)* optional `new_registrations` / `new_registrations_active` on `UsageContextByStatus`; `SCHEMA_VERSION` → 1.9.0 |
| `tests/test_aggregate_topics.py:133` | drop `status_rule` from the expected ids |
| *(Q1a)* `tests/test_aggregate.py` | signup cells present per level; absent when no roster is imported |

### Dashboard

| file | change |
|---|---|
| `cells/PieShare.tsx` | **new** (above) |
| `cells/ProgramLevelCard.tsx` | opt out of the collapsible `DataTable`; accept a slot below the note for the pie |
| `tabs/AdoptionTab.tsx` | A1 tip removal; A3 reposition + pie + disclosure; *(Q1)* signups tile |
| `tabs/EngagementTab.tsx` | B1 reorder + comment rewrite |
| `tabs/TopicsTab.tsx` | C1 wording; C3 two card notes; C4 suppression key off those two cards; C5 method block |
| `tabs/TimingTab.tsx` | D2 sentence |
| `tabs/LanguageTab.tsx` | E1 reorder; E2 pie over table |

### Fixture

`dashboard/dev-fixtures/generate.mjs:591` carries its own copy of `daypart_definition` —
mirror the cut, drop `status_rule` from the topics `by_status` ids, then regenerate:

```bash
cd dashboard && node dev-fixtures/generate.mjs > dev-fixtures/aggregates.fixture.json
```

`pipeline/tests/test_schema_export.py:57` validates it, so a malformed edit fails the
suite rather than the browser.

### Docs

- `docs/aggregates-contract.md` §6.2 — `daypart_definition` gist row; topics example ids;
  *(Q1a)* the `signup_level_rule` row and the 1.9.0 fields.
- `docs/decisions.md` — **D-59**, including the D-58 decision-6 reversal (A1) and the
  D-55 reversal if Q1a is chosen; publish record after shipping.
- `CLAUDE.md` — status paragraph; the D-55 "a signup cannot be attributed to a program
  level" line becomes wrong under Q1a and must be rewritten in the same change.

## Verification

1. `cd pipeline && caffeinate -dims .venv/bin/python -m pytest -q` (~4 min) before any
   upload.
2. Regenerate the fixture; `cd dashboard && pnpm lint && pnpm build`.
3. `pnpm dev` and walk what actually varies:
   - **Adoption** — All users (level card first, donut present, no collapsible table),
     Bachelor (no level card, no roster tip on Active users, signups per Q1), a window
     where one level is suppressed (**table, no pie**).
   - **Engagement** — Weeks active leads; a one-week `Recent` slice leads with the
     `MeasureUndefined` card.
   - **Topics** — no § on any of the four cards under Bachelor; the two new provenance
     notes read as the card's whole Note (no suppression clause) in a window that *does*
     have withheld rows, and the tick is still explained on row hover; the emergent and
     deductive cards still show the key; level card at the bottom still carries †‡; the
     method block reads the classifier version from the document.
   - **Timing** — both daypart cards' notes read correctly as one sentence.
   - **Language** — order under All users vs Bachelor; the donut with `Other` at 0 (legend
     row present, showing `0` and `0%`); a window with a suppressed language (no donut,
     table only); a window with no message denominator (legend shows counts, no shares).
4. Keyboard + contrast pass on the two donuts (dataviz skill's checklist).
5. Confirm the deploy gap is harmless: the new bundle against the **old** blob still
   renders the long daypart text (cosmetic), and the old bundle against the new blob
   renders the short one. Neither is wrong at any moment.

## Deploy

`daypart_definition` and the topics ids travel in the blob → **both halves**, data first
is safest here (an old bundle showing the new short note is harmless; the reverse is too).
Under Q1a the schema moves, which makes both halves mandatory rather than merely advisable.
`--skip-extract --skip-classify` — nothing here needs newer StatsBot activity.

# Adoption's note moves into the cells; tab order leads with Adoption (D-58)

*Planned 2026-08-01, same day D-57 shipped. **No schema change — stays 1.8.0.** A copy,
placement and ordering change: the nine-line APA paragraph under Adoption's KPI row is
dissolved into per-cell notes, four footnote texts are rewritten or re-homed, one new
footnote id is minted for the all-time-only caveat, the Bergmann citation gains a
clickable OSF link, the header dash becomes a preposition, and Topics stops being the
first tab.*

## Why

Four requests, one theme — the reader is an educator scanning a tab, not a reviewer
reading a table note top to bottom.

1. **Tab order.** `Topics · Adoption · Engagement · Timing · Language` → `Adoption ·
   Engagement · Topics · Timing · Language`. This reverses the 2026-07-07 editorial
   decision recorded in `Dashboard.tsx` ("Topics first — the question the project exists
   to answer"). The new order is a reading order rather than a research-priority order:
   who used it → how much → what about → when → in which language.
2. **Header preposition.** `…data from StatsBot — bachelor students (between …)` reads as
   an aside; `…data from StatsBot for bachelor students (between …)` reads as a scope.
3. **Adoption deck** drops "Bergmann-comparable", which names a paper the educator has
   not read, for "frequency-based", which names what the classes measure.
4. **The Note paragraph.** 92 words in one block under a four-tile row, covering four
   unrelated numbers. Nobody reads it, and the reader who wants one of those four numbers
   explained has to find their sentence inside the other three.

## Decisions taken 2026-08-01 (record as D-58)

1. **The rewritten texts stay in the pipeline's `FOOTNOTES` registry** and travel in the
   blob, per contract §6.2 ("caveats are versioned with the numbers they govern"). The
   dashboard changes only *where* each footnote lands. Cost: this needs a **data
   republish** (`--skip-extract --skip-classify`) as well as a bundle deploy.
2. **Hybrid rendering.** One crisp always-visible line per tile saying what the number
   means; provenance and scope caveats sit behind a small marker revealed on hover or
   keyboard focus. Nothing that changes how a number should be *read* is hidden.
3. **A footnote renders whole, in exactly one place.** Visible-or-tip is a per-id
   decision made in `AdoptionTab.tsx`. The dashboard never splits a published string into
   "first sentence visible, rest in the tip" — that would make the rendering depend on
   the punctuation of data it does not own.
4. **The pilot passage goes, its all-time consequence stays — as its own footnote id.**
   `retention_all_time` is emitted only on the `all_time` window, by the pipeline, which
   is the side that knows the window kind. The dashboard renders whatever retention ids
   arrive and does not branch on `win.kind` for text.
5. **Bergmann attribution stays in the User classes card note**, now with a clickable OSF
   link. The link is a **bare URL at the end of the published text**, made clickable by a
   linkifier in the renderer — no markup inside published data, no schema field.
6. **`status_multi` leaves the totals block**; it is about summing levels, which only the
   By-program-level card shows. `status_rule` moves onto the Active-users tile *only when
   a single level is selected* — that is when the headline count depends on the roster
   rule; when the filter is All users the level card carries it, as today.

## The schema does not move

`Footnote` stays `{text: str}`. A footnote id is a key in an open `dict[str, Footnote]`,
not a schema field, so minting `retention_all_time` changes data, not shape —
`SCHEMA_VERSION` stays `1.8.0`, `aggregates.gen.ts` is not regenerated, and
`schema/aggregates.schema.json` does not change. §10 lists "new footnotes" among the
minor-bump-allowed changes; it is listed there because adding one is *additive*, and the
D-57 precedent (data + display only, no bump) is the one that applies.

**Both deploy orders are safe, with one condition.** The house order is bundle first,
blob second, so the new bundle will briefly run against the D-57 blob, which has no
`retention_all_time` key. `resolveFootnotes` currently falls back to rendering *the id
itself* as the text — which would print the literal string `retention_all_time` on the
all-time window for the length of the gap. So:

> **`footnoteText(doc, id)` returns `null` on a miss, and a tile with no text renders no
> line.** The id-as-text fallback stays where it is (the paragraph renderers), because
> there a missing id is a diagnostic; in a tile it is a typo on the page.

Blob first, bundle second: the old bundle prints the new footnote as one more sentence in
the paragraph it already renders. Cosmetic, never wrong.

## What each Adoption cell says after this

```
┌──────────────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐
│ Active users        ⁽ⁱ⁾¹ │  │ Messages       │  │ Sessions       │  │ New signups     │
│ 66                       │  │ 513            │  │ 225            │  │ 59  signed up   │
│ 3.3% of 2,012 enrolled   │  │ 1 msg = 1 user │  │                │  │  7  sent ≥1 msg │
│ bachelor students   ⁽ⁱ⁾² │  │ + 1 LLM resp.  │  │                │  │ Both counts are │
└──────────────────────────┘  └────────────────┘  └────────────────┘  │ window-scoped.  │
┌──────────────────────────┐                                          │ Someone who     │
│ Of those                 │   ⁽ⁱ⁾¹ status_rule — only when a single   │ signed up late  │
│ 59  new                  │        level is selected                  │ and first wrote │
│  7  returning            │   ⁽ⁱ⁾² enrollment_source +                │ afterwards …    │
│ New = the student's      │        enrollment_scope (+                └─────────────────┘
│ first-ever message falls │        reach_window_scope in a slice)
│ inside the selected      │
│ window; returning = they │   (all-time window only, third line:)
│ had already used StatsBot│   "All time has no earlier period except the 2024/25
│ before it. The two add up│    pilot, so returning here names the pilot cohort
│ to the active users."    │    rather than semester-to-semester loyalty."
└──────────────────────────┘
```

No `Note.` paragraph under the row. The `User classes` and `By program level` cards keep
theirs — one paragraph serving one figure is what APA table notes are for, and both
already sit inside a `ChartCard`.

### Consequence: the totals block leaves the APA symbol grammar

`†/‡/§/¶` exist because one paragraph served four tiles. With each note inside its cell
there is nothing for a symbol to point at, so `symbolsFor(totalsFootnotes, …)` and the
`markers` props on both totals tiles go. The grammar survives untouched in `ChartCard`
and `ProgramLevelCard`, which is every other place it is used.

## Footnote text diffs (pipeline data — review these first)

| id | change |
|---|---|
| `retention_definition` | **72 → 27 words.** Keeps: "New = the student's first-ever message falls inside the selected window; returning = they had already used StatsBot before it. The two add up to the active users." Drops the pilot-history sentence and the all-time sentence. |
| `retention_all_time` | **new.** "All time has no earlier period except the 2024/25 pilot, so returning here names the pilot cohort rather than semester-to-semester loyalty." Attached to `totals.footnote_ids` on the `all_time` window only. |
| `signup_activation` | **38 → 20 words.** "Both counts are window-scoped. Someone who signed up late and first wrote afterwards counts in the window they wrote in." |
| `user_class_definitions` | unchanged text + trailing `" Materials: https://osf.io/v8ydk/overview"`. |
| `enrollment_source`, `enrollment_scope`, `reach_window_scope` | **text unchanged** — they move into the reach tip, where length costs nothing. D-55 called `enrollment_scope` the owner's wording and not optional decoration, so it is not trimmed. |
| `status_rule`, `status_multi` | **text unchanged** — shared with Topics, Timing, Engagement and Language. Only their placement on Adoption changes. |

`first-ever` carries what the deleted sentence spelled out (the D-50 baseline reads behind
`axis_start`). The pipeline invariant is untouched either way; what changes is whether the
page explains it.

## Work inventory

### Pipeline — `pipeline/statsboteval_pipeline/aggregate.py`

- `FOOTNOTES`: rewrite `retention_definition` and `signup_activation`, add
  `retention_all_time` beside them, append the OSF URL to `user_class_definitions`.
  Keep the D-50 comment that explains why `frequent` is stated as a subset.
- `usage_windows[window.id]` (~line 855): `footnote_ids=["retention_definition",
  "signup_activation"]` becomes window-aware —
  `["retention_definition", *(["retention_all_time"] if window.kind == "all_time" else []),
  "signup_activation"]`. `window` is already the loop variable at line 765.
- `contract._iter_footnote_ids` already fails a publish that references an id missing from
  the registry, so the new id is pinned by existing validation.

### Pipeline tests

- `tests/test_aggregate.py:293` asserts the `all_time` totals dict verbatim → add
  `"retention_all_time"` to the expected `footnote_ids`. This is the pin for decision 4:
  the assertion is on `all_time`, so a semester window silently gaining the id would still
  need its own guard.
- Add one test asserting a **semester** window's totals do *not* carry
  `retention_all_time` — the half the existing assertion cannot see.

### Dashboard

| file | change |
|---|---|
| `src/components/Dashboard.tsx` | `TABS` order → adoption, engagement, topics, timing, language, (trends hidden). Rewrite the editorial comment: it currently argues for Topics-first, and leaving it would leave the file arguing with itself. `VISIBLE_TABS[0]` is the default landing tab, so **the dashboard now opens on Adoption** — intended, worth stating in the comment. Header line: `—` → `for`. |
| `src/components/cells/NoteText.tsx` | **new.** Renders a published note string with bare `https?://…` URLs as anchors (`target="_blank" rel="noreferrer"`, trailing `.,;:` stripped from the match). React elements only — never `dangerouslySetInnerHTML`, even though the text is ours. |
| `src/components/cells/InfoTip.tsx` | **new.** Inline marker + CSS-only popover, modelled on `TopicRowTip` (D-28 primitives-on-demand: hand-rolled, no library). Differences: it is an inline marker rather than a row wrapper, and it opens on `hover` **and `focus-within`** so a tap on touch reveals it — `focus-visible` alone does not fire on tap. `aria-describedby` ties marker to tip. `TopicRowTip` is left alone; the two anchor differently. |
| `src/components/cells/KpiTile.tsx` | `note?: string` → `ReactNode` on `KpiTile`; add the same prop to `KpiPairTile`; drop nothing else. Both `markers` props stay in the signature (unused by Adoption after this, still the right shape for a card that needs them). |
| `src/lib/footnotes.ts` | add `footnoteText(doc, id): string | null` — null on a miss, per the deploy-gap rule above. `resolveFootnotes`/`symbolsFor` stay as they are for the card renderers. |
| `src/components/cells/ChartCard.tsx` | render footnote text through `NoteText` (one line) so the Bergmann link is clickable wherever a card note appears — this is the only place `f.text` is rendered outside `AdoptionTab`. |
| `src/components/tabs/AdoptionTab.tsx` | the substance: delete the totals `Note.` paragraph, attach notes/tips per tile, deck rename, enrollment texts into the reach tip, `status_rule` onto Active users when `level !== ALL`, `status_multi` off the totals block. |

### Dev fixture

`dashboard/dev-fixtures/generate.mjs` keeps its own copy of every footnote text (line
577 ff.) — mirror all four edits there, add `retention_all_time` to the registry **and to
the all-time window's `totals.footnote_ids`**, then regenerate:

```bash
cd dashboard && node dev-fixtures/generate.mjs > dev-fixtures/aggregates.fixture.json
```

`pipeline/tests/test_schema_export.py:57` validates the regenerated fixture against the
schema, so a malformed edit fails the suite rather than the browser.

### Docs

- `docs/aggregates-contract.md` §6.2: update the `retention_definition` gist row, add a
  `retention_all_time` row (schema 1.8.0 — D-58), note that `user_class_definitions`
  carries a materials URL.
- `docs/decisions.md`: **D-58**, covering all six decisions above, the tab-order reversal
  of the 2026-07-07 choice, and (after shipping) the publish record.
- `CLAUDE.md` status paragraph: one sentence for D-58.

## Verification

1. `cd pipeline && .venv/bin/python -m pytest -q` — ~4 min; run it before uploading, not
   after (go-live §1).
2. Regenerate the fixture; `cd dashboard && pnpm lint && pnpm build`.
3. `pnpm dev` against the fixture and walk the matrix that actually varies:
   - **windows**: `All time` (the extra retention line appears), a whole semester (it does
     not), a `Recent` slice (`reach_window_scope` joins the reach tip).
   - **levels**: `All users` (no `status_rule` on Active users; By-program-level card
     visible with `status_rule` + `status_multi`), `Bachelor` (`status_rule` on Active
     users; level card gone), `Staff` (no reach line at all → no reach tip; the tile must
     not render an empty marker).
   - **cell states**: a suppressed retention pair, a window with no enrollment entry.
4. Keyboard pass: Tab reaches every tip marker and the popover is announced; Escape is not
   needed (nothing is modal). Check the tip against the last tile in the row — a popover
   anchored right could overflow the viewport at ≤ 640 px.
5. Confirm the OSF link opens `https://osf.io/v8ydk/overview` and that the surrounding
   sentence still reads correctly with the URL rendered as an anchor.

## Deploy

Both halves of `/go-live`, and the mode is **re-aggregate only**
(`--skip-extract --skip-classify`) — this is a copy and placement change; the numbers must
come out identical to the D-57 publish. Diff the new document against
`pipeline/data/` D-57's before uploading: **only `footnotes` and `usage_context.*.totals.
footnote_ids` may differ.** Any other delta means something was rebuilt that should not
have been.

Bundle first, blob second (house order, and the gap is harmless per the rule above).

## Rejected alternatives

- **Dashboard-side copy.** Fastest (one deploy, no republish), but the blob would keep
  shipping the long texts unread and archived documents would stop carrying the warnings
  actually shown beside their figures — the property §6.2 exists to hold.
- **A typed `url` field on `Footnote`.** Cleaner semantics, and safe on the wire (the
  published JSON Schema sets no `additionalProperties: false`, so an old API would not
  reject it) — but it is a schema minor bump, a `aggregates.gen.ts` regeneration and a
  permanent contract field for one citation, and it would still render as a trailing link.
  D-48 set the precedent: do not add contract fields for a copy change.
- **Anchoring the link on the token "Bergmann et al. (2026)"** by matching that phrase in
  the dashboard. Puts the link exactly where it was asked for, but the URL then lives
  dashboard-side (undoing decision 1) and the link disappears silently the day the
  sentence is reworded. Available on request — it is a five-line change to `NoteText`.
- **Splitting each footnote into a visible half and a tip half.** Rejected as decision 3:
  the renderer would depend on sentence boundaries inside data it does not own.

## Open for your call (not in the plan as written)

- **A definition line on the Sessions tile.** Messages says what a message is; Sessions
  says nothing, and `chat_fragmentation` ("the credit-limit UI nudges students toward
  starting new chats, so counts may overstate distinct dialogues", D-08) is exactly the
  caveat a reader of `225` needs. It is already attached to the weekly sessions series
  elsewhere, so this is placement only — say the word and it joins the plan.

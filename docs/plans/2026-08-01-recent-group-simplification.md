# A single "Recent" group replaces per-semester slice groups (D-57)

*Planned 2026-08-01, one day after D-56 shipped. **No schema change — stays 1.8.0.**
Slices are published for the anchor semester only, their labels lose the `Latest`/`Final`
state-dependence, and the picker returns to its pre-D-56 shape: `Semesters` / `Recent` /
`Everything`. This reverses D-56 decisions 2 and 4 and keeps everything else.*

## Why

D-56 decision 2 was *"slices are published for **every** semester, not only the anchor —
the whole point is comparing one term's closing weeks with another's."* Seen in use, that
is not a want. The picker grew from 5 options to 10, three of them repeating the same
three words under each of three headings:

```
Summer semester 2026        Semesters
  Whole semester              Summer semester 2026 (in progress)
  Final 4 weeks               Winter semester 2025/26
  Final week                  Summer semester 2025
Winter semester 2025/26     Recent
  Whole semester      -->     Previous 4 weeks · SS 2026
  Final 4 weeks               Last available week · SS 2026
  Final week                Everything
Summer semester 2025          All time
  …                         
Everything
  All time
```

The right column is what the picker looked like before D-56, with `trailing_4` swapped for
two semester-anchored entries — which is what the original requirement asked for and what
D-56 over-built past. **The anchoring survives; only the fan-out goes.** "Previous 4 weeks
· SS 2026" still means four *teaching* weeks, which is the entire reason `trailing_4` had
to die.

Owner decisions taken 2026-08-01 (recorded as D-57):

1. **Slices are emitted for the anchor semester only** — the semester with the latest
   coverage, exactly the rule `defaultWindowId` already uses client-side. Reverses D-56
   decision 2. Cross-semester comparison of closing weeks is not a need; the whole
   semesters remain individually selectable, as they always were.
2. **Labels lose the `Latest`/`Final` state-dependence** — reverses D-56 decision 4.
   `Previous 4 weeks` and `Last available week` read correctly whether the anchor term is
   running or finished, so the branch is not paying for itself. The truthful-count rule is
   *kept*: three weeks in, the label says "Previous 3 weeks".
3. **Older slices are dropped from the document, not merely hidden.** Measured on
   `pipeline/data/aggregates-review-20260731-slices.json`: 10 windows → 6,
   **667.0 KB → 461.6 KB** uncompressed, **33.4 KB → 26.7 KB** gzipped. Windows nobody can
   select still cost review time at every publish.
4. **Sentence case** (`Previous 4 weeks`, not `Previous 4 Weeks`), matching `All time` and
   the tab and card headings.

## The schema does not move

Nothing about the document's *shape* changes: `SemesterSliceWindow`, `parent_window_id`,
`semester_weeks` and the `_check_windows` validator all stay exactly as D-56 built them.
What changes is **which windows are emitted** (data), **two label strings** (data), and
**how the client groups them** (display). So:

- `SCHEMA_VERSION` stays `1.8.0` and `dashboard/src/lib/aggregates.gen.ts` is not
  regenerated. `schema/aggregates.schema.json` takes a **one-line documentation diff**:
  pydantic publishes a model docstring as the JSON Schema `description`, and
  `SemesterSliceWindow`'s had to stop promising that a slice id is "stable forever". No
  property, `required` entry, type or discriminator moves, so §10 is not engaged.
- **Both deploy orders are safe**, which is a first for this sequence of changes. Bundle
  before blob: the new picker briefly shows six entries under `Recent` (the old document's
  slices, all correctly labelled) — cosmetically busy, never wrong. Blob before bundle: the
  old picker shows three groups, two holding only a whole semester. Neither is a 500.
- No re-classification: `--skip-extract --skip-classify`. The corpus stands as extracted
  2026-07-14, which is already after SS 2026 ended, so the anchor and its slice weeks are
  the same ones D-56 published yesterday.

## Dead code inventory

D-56 introduced machinery specifically for the "whole semester / final 4 weeks / final
week, grouped under each semester" framing. Under the flat framing it is dead and comes
out:

| what | where | why it dies |
|---|---|---|
| `optionLabel()` | `dashboard/src/lib/windows.ts` | existed only to pick `short_label` inside a group heading; flat groups need the self-contained `label` |
| `semesterOf()` | `dashboard/src/lib/windows.ts` | **already dead** — nothing outside the module imports it |
| per-semester `groupedWindows()` body | `dashboard/src/lib/windows.ts` | reverts to the three fixed groups |
| the optgroup rationale comment | `WindowPicker.tsx` | describes a grouping that no longer exists |
| `running` / `word` branch | `windows.py::_slices` | D-57 decision 2 |
| `isRunning`, the `Latest`/`Final` ternary | `dev-fixtures/generate.mjs` | same |
| `short_label` **emission** on `all_time` and `semester` | `windows.py`, `generate.mjs` | with no group heading to shorten against, `label` is already the short form — `"Whole semester"` and a duplicate `"All time"` are read by nothing |
| `Latest`/`Final` label tests | `test_windows.py` | assert a rule that no longer exists |

**One thing stays that looks like it should go: `short_label` on `SemesterSliceWindow`.**
Nothing renders it. But contract §10 is explicit — *"removing a field from a section that
stays… remains a major break"*, and the narrow 1.5.0 exception covers withdrawing a whole
optional section, not a field. Deleting it would cost a 2.0.0 major bump and a new blob
prefix to save 60 bytes. It stays required and emitted, in the same **published, rendered
nowhere** category the contract already accepts for `semester_weeks`: it is the stem of the
label (`label = f"{short_label} · {short}"`), i.e. the part of the slice's name that is not
the semester. The *field declarations* on `all_time` and `semester` stay too, for the same
reason — only the emission stops, which their `| None = None` already tolerates by design.

## Changes

### `pipeline/statsboteval_pipeline/windows.py`

Hoist slice emission out of the loop. The axis is chronological and `seen` gates first
appearance, so semesters append in order and the last one assigned *is* the semester with
the latest coverage — no sort, no date math:

```python
    seen: set[str] = set()
    anchor: tuple[SemesterWindow, list[str], str] | None = None
    for week in axis:
        ...
        windows.append(semester)
        anchor = (semester, covered, sem.short)
    if anchor is not None:
        windows.extend(_slices(*anchor))
    return windows
```

`_slices` drops `running`/`word` and hard-codes the two stems: `f"Previous {len(multi)}
weeks"` and `"Last available week"`. `_Semester.short` and `_winter()` stay — the label
suffix still needs them. Drop `short_label=` from the `AllTimeWindow` and `SemesterWindow`
constructors. Module docstring: "Each semester also publishes two slices" → "The anchor
semester also publishes two slices".

### `pipeline/statsboteval_pipeline/contract.py`

No model changes. Two comment corrections:

- `SemesterSliceWindow`'s docstring claims *"the id is stable forever once the semester
  ends — `2026S.last1` names the same span in every later publish"*. Anchor-only emission
  breaks that: once WS 2026 opens, `2026S.last1` leaves the registry. Restate as **stable
  in meaning, not in presence** — a slice id never *changes* span, but only the anchor's
  slices are published.
- The `short_label` comment block above `AllTimeWindow` describes a picker that groups by
  semester. Rewrite for the new role (label stem on slices; unemitted on the other two).

### `dashboard/src/lib/windows.ts`

`groupedWindows` returns its pre-D-56 body with `kind === "trailing"` swapped for
`kind === "semester_slice"`:

```ts
  const recent = doc.windows.filter((w) => w.kind === "semester_slice");
  return [
    { label: "Semesters", windows: semesters },
    { label: "Recent", windows: recent },
    { label: "Everything", windows: allTime },
  ].filter((g) => g.windows.length > 0);
```

Delete `optionLabel` and `semesterOf`. **Keep** `parentWindowId` and have
`levels.ts::enrollmentFor` call it instead of re-inlining the same narrow — one place that
knows how a slice reaches its parent. **Keep** `isInProgress` as it is now
(`kind !== "semester"`): slices are picker options again, and it correctly returns false
for them, so the marker lands on *Summer semester 2026* and not on the Recent entries. Drop
the `Latest`/`Final` sentence from its docstring.

### `dashboard/src/components/WindowPicker.tsx`

Back to `{w.label}{isInProgress(w) ? " (in progress)" : ""}`; drop the `optionLabel`
import and the optgroup comment.

### Unchanged

`aggregate.py`, `trends.py`, `schema/`, `aggregates.gen.ts`, `EmptyState.tsx`
(`MeasureUndefined` still serves `.last1`), `EngagementTab.tsx`, `AdoptionTab.tsx`,
`format.ts`, the `reach_window_scope` footnote, `_check_windows`, `TrailingWindow`, and the
trends slice exclusion.

### Tests

- `test_windows.py` — replace `test_completed_semester_slices_read_as_final` and
  `test_running_semester_slices_read_as_latest` with the state-free labels; add
  **`test_only_the_anchor_semester_has_slices`** (a three-semester axis yields exactly two
  slice windows, both parented to the newest) and **`test_the_anchor_follows_the_axis_across
  _a_term_boundary`** parametrised on D-56's rollover table (31 Jul 2026 → 2026S;
  12 Oct 2026 → 2026W with a 2-week `.last4`). `test_winter_slice_label_spans_the_new_year`
  keeps its axis but drops "Final". `test_break_only_axis_…` unchanged and still passes.
- `test_contract_windows.py`, `test_trends.py`, `factories.py` — no change needed. The
  validator is per-slice and never assumed every semester carries one; a factory document
  whose slice parents a non-latest semester stays valid, which is correct (the contract
  constrains structure, the pipeline chooses the registry).
- `test_schema_export.py` — must produce no diff. That is the guard proving this is not a
  schema change.

### `dashboard/dev-fixtures/generate.mjs`

Same narrowing: emit `sliceFor` only for the last semester, delete `isRunning` and the
ternary, drop `short_label` from the all_time and semester literals. Fixture goes 10
windows → 6. The `windowStudents` map and the topics/tokens `per_window` filters shrink
accordingly.

### Docs

- **`docs/aggregates-contract.md` §6.1** — slices are emitted for the anchor semester only;
  new label wording; delete the state-dependence bullet; replace the "ids are stable
  forever" bullet with the stable-in-meaning statement; update the `short_label` bullet to
  its new role; correct the UI-preset sentence.
- **`docs/decisions.md`** — D-57, recording the reversal of D-56 decisions 2 and 4, the
  measured payload saving, and the accepted loss (a bookmarked `?window=2026S.last1` stops
  resolving once WS 2026 opens; `findWindow` returns undefined and the page falls back to
  the default, so it degrades cleanly).
- **`CLAUDE.md`** — three edits, one of them a pre-existing bug: the file still says
  **"Schema 1.8.0 (D-56) is built and not yet published"** although `dab05aa` recorded the
  2026-07-31 publish. Fix that, restate the slice description for anchor-only, and drop the
  "the label's word changes with state" clause from the D-56 invariant.

## Verification

1. `ruff check`, `mypy statsboteval_pipeline`, `pytest` (pipeline + api).
2. `test_schema_export.py` green, and the `schema/` diff inspected line by line: it must
   touch `description` text only. Anything under `properties`, `required`, `type` or the
   discriminator means this stopped being a data-and-display change.
3. Regenerate the dev fixture and validate it through the pipeline's own `Aggregates`
   model, not just `tsc`. D-56 shipped a fixture that `_check_windows` rejected because
   nothing ran it through the model; do that once here.
4. `tsc --noEmit`, `eslint`, `next build`.
5. Dry-run aggregation on the real corpus and diff the sections against
   `aggregates-review-20260731-slices.json`: **every retained window must be byte-identical**
   and the only difference must be the four dropped windows. Same review gate that worked
   for D-56.
6. Publish `--skip-extract --skip-classify`, bundle first then blob. Confirm the picker
   reads `Semesters` / `Recent` / `Everything`, and remember the ~7-minute stale-cache
   behaviour recorded under D-56 — check the blob before concluding an upload failed.

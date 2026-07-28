# `statsboteval-v2` adoption — re-classify under the tuned configuration

**Date:** 2026-07-28 · **Status:** planned, not started
**Decisions recorded:** D-45 (grid + v2 configuration) · D-46 (gpt-5.4-mini rejected on evidence)
· D-47 (theme set reviewed, left unchanged)
**Evidence:** `pipeline/data/classifier-grid-2026-07-28.txt` (git-ignored, 20-arm grid)

## Why

`statsboteval-v1` scores average MCC **.71** against the 300 Bergmann human-consensus
messages (D-42). A 20-arm grid over model x batch_size x reasoning_effort found the shipped
`batch_size = 50` to be the single largest lever: it was inherited from Bergmann's GPT-4o
validation, where one call asked for 50 decisions, and never re-tuned after D-30's
consolidated prompt made each call ask for **650**. Re-tuning it lifts the classifier to
~**.82–.84** — from below Bergmann's GPT-5 reference (.79) to above it.

Per D-41, one label version never mixes inference settings, so this is a new label version
and a full re-classification, not a config edit.

## Target configuration

| setting | v1 (shipped) | v2 | changed? |
|---|---|---|---|
| model | gpt-5-mini @2025-08-07 | gpt-5-mini @2025-08-07 | no |
| deployment | `statsboteval-5-mini` (DataZoneStandard) | same | no |
| `classifier_reasoning_effort` | `low` | `low` | no |
| **`batch_size`** | **50** (the `BATCH_LIMIT` default) | **10** | **YES** |
| `classifier_seed` | 20260718 | 20260718 | no |
| Declarative Statement codebook block | our paraphrase | Bergmann's actual text | yes (provenance) |
| theme set | `statsboteval-themes-v1` | `statsboteval-themes-v1` | no — frozen, immutable |

**One inference parameter changes.** The codebook change is provenance-motivated and
measured to have **no reliable effect** (the A/B disagreed in sign across two configs);
it is adopted because using Bergmann's actual text beats using text we invented, not
because it scores better.

> **RESOLVED 2026-07-28 — `batch_size = 10` (owner).** The `b10/low` replicate came back
> at **.824** against its original .795, shrinking the b5-vs-b10 gap to **+.009** on the
> selection criterion — inside both spreads (b5/low .013, b10/low .029). The two are
> statistically indistinguishable, so the choice falls to operational robustness, where
> batch 10 wins outright: **442 calls instead of 884, ~1.6 h instead of ~3.1 h**, and
> correspondingly half the exposure to the transient failures that interrupted this work
> twice (a laptop sleep stall and two network drops). Trading at most ~.02 of unmeasurable
> MCC for halving the failure surface of a multi-hour unattended run is the right call on
> this hardware.

## Sequencing

Tasks run **1 → 6 in order**. The theme question that once sat in front of this plan is
closed (D-47), so there is no longer any pre-step: no candidate regeneration, no pending
operator review. Task 1 is the only prerequisite for Task 3, and Tasks 3–5 must stay in
order so that one classification pass feeds one aggregate and one publish.

## Tasks

### 1. Make `batch_size` configurable
Currently it is not: `step.run_classification` calls `classify_corpus` without it, so it
takes the `BATCH_LIMIT` default (50) from `classify/prompts.py`. `BATCH_LIMIT` is also the
hard *ceiling* enforced by `_check_batch`, so the two roles need separating:

- keep `BATCH_LIMIT = 50` as the ceiling (`_check_batch` unchanged),
- add `classifier_batch_size: int = 10` to `ClassifierSettings`,
- thread it through `step.run_classification` → `classify_corpus`,
- same for the theme-assignment pass, which shares the batching.

Tests: a settings default test, and one asserting `classify_corpus` honours a non-default
size (the existing synthetic fixtures cover the path).

### 2. Adopt the codebook block
Replace the Declarative Statement block in `bergmann-materials/categories.md` with
Bergmann's text from `/Human Rating/Coding Instruction/Coding Instruction.ods`
(osf.io/download/dg5ca/, Stage-1 OSF folder — the spreadsheet the seven human coders used):

```
- Brief: Providing any context or informative statement?
- Code 1: if any context or informative statement is given.
- Code 0: if only a question or instruction is given without declaring any context or information.
- Example: I want to conduct a meta Analysis.
```

(`Full` is unchanged — it already matches manuscript Table 1 verbatim.)

Correct `bergmann-materials/README.md`: the block is **not** missing from the public
materials, only from the *prompt* file. Note that this is the **pilot** codebook
(2025-01-25) while our other 12 categories match the **production** prompts (2025-04-22);
the Full definition is byte-identical across both, which suggests the category was not
revised, but that is inference. Still worth confirming with Leonardo.

### 3. Re-classify under `statsboteval-v2`
- `classifier_label_version = statsboteval-v2`, provenance tag unchanged in shape.
- Full corpus: 4,419 messages. At batch 10 that is 442 deductive calls, ~1.6 h, ~$2.20.
- **Do not delete `statsboteval-v1`.** Both versions coexist by design (D-07's tidy `labels`
  table, PK `(history_id, label_version, domain, code)`), so v1 stays as the comparison
  baseline and the rollback path. Delete only after v2 is published and reviewed.
- Run on AC power. The 2026-07-27 grid run stalled for ~9 hours because the laptop was on
  battery and cycled into Maintenance Sleep; `caffeinate -dimsu -w <pid>` only inhibits
  system sleep when plugged in.

### 4. Re-run theme assignment under v2
`assign-themes` writes `emergent_theme` / `method_theme` / `software_theme` rows keyed by
label version, so v2 needs its own pass against the **unchanged, still-frozen**
`statsboteval-themes-v1`.

**Theme sets are NOT regenerated — settled by D-47, not merely deferred.** The set was
reviewed in depth on 2026-07-28: a coverage audit over all 5,347 candidate codes found the
frozen 15 cover ~93% of coded content, and every candidate addition (strongest: 1.10%) sits
below the N=3 publication floor once cells are split by window x status. Re-synthesis also
reproduced 13 of the 15, so the set is not an artefact. `statsboteval-themes-v1` therefore
stays frozen and this task is a straight re-assignment against it — no operator review is
pending and nothing here blocks on one.
Caveat to record: the batch-size finding is validated only for the *deductive* pass. Theme
assignment shares the consolidated-prompt dynamics and plausibly shares the effect, but
Bergmann validated themes by expert similarity rather than MCC (D-30), so there is **no
ground truth to measure it against** — the change is applied there blind. Flag in the
publish note.

### 5. Re-validate, re-aggregate, republish
- Re-run the validation report against the 300 consensus messages under v2; expect ~.82–.84.
- Point `label_versions.classification` at `statsboteval-v2`, re-aggregate, republish.
- Schema unchanged (1.2.0) — this is a value change, not a shape change.
- Dashboard needs **no** redeploy; it reads the configured version from the document.

### 6. Record decisions
D-45 and D-46 are written into `docs/decisions.md` as part of this work (see below).

## Verification

- [ ] `pytest`, `ruff`, `mypy` clean before and after
- [ ] validation report under v2 shows average MCC ≥ .80 on the 300 consensus messages
- [ ] `labels` holds both `statsboteval-v1` and `statsboteval-v2` for all 4,419 messages
- [ ] published document's `label_versions.classification` reads `statsboteval-v2`
- [ ] spot-check the Topics tab: emergent theme ordering should be broadly stable; large
      reordering is a signal worth investigating, not accepting
- [ ] `erase-student` still covers every table touched (no new tables, so expected pass)

## Deliberately out of scope

- Regenerating emergent themes — **closed by D-47**, not deferred: reviewed, audited, and
  deliberately left unchanged. Revisit only when a new semester's data could shift the
  distribution (D-38), using the reusable gap-analysis script (~16 calls, minutes).
- Per-category call splitting for `reference_to_a_prior_content` — the grid brings it to
  .543 against an independent-human alpha of .56; it is at the human ceiling, and further
  work there needs conversation context, not tuning.
- gpt-5.4-mini — rejected on evidence (D-46).
- Moving `run-weekly` off the laptop — tracked in `2026-07-27-weekly-run-automation.md`.

---
name: go-live
description: Publish StatsBotEval to the live Azure URL — re-aggregate the corpus, upload the aggregates blob, and deploy the dashboard/API bundle. Use when the user says go live, publish, deploy, ship it, make it live, or push the dashboard to production. Asks which run-weekly mode to use before touching anything.
---

# Go live

Takes the current repo state to <https://statsboteval.azurewebsites.net>. Two halves that
fail independently, so always know which one you are doing:

| half | what changes | script |
|---|---|---|
| **data** | the aggregates blob the API reads | `infra/scripts/04_publish_production.sh` |
| **code** | the API + the built dashboard bundle | `infra/scripts/02_deploy_app.sh` |

A schema bump needs **both** — an old bundle ignores new fields silently, which looks like
"my change didn't deploy". A copy-only dashboard change needs code only. A weekly data
refresh needs data only.

## 1 · Preflight

```bash
az account show --query name -o tsv          # must print: MOPS (Methods of Psychology)
git status --short                           # know what you are shipping
az webapp show -n statsboteval -g Lehrprojekt --query state -o tsv   # must be Running
```

If `state` is `QuotaExceeded`, the F1 daily CPU quota is burned (usually a crash loop) and
**deploying will not help** — it resets on the hour boundary of the daily window (09:00 UTC).
Say so and stop.

Do not run the pipeline test suite as part of this skill by default — assume it has already
been run when relevant. If the user asks for it explicitly, run
`cd pipeline && .venv/bin/python -m pytest -q` in the background (~4 minutes) and read it
before uploading, not after.

## 2 · Ask which run-weekly mode to use

**Always ask — never assume.** The modes differ in what they touch, what they cost, and what
they need connected. Use AskUserQuestion with these options:

| mode | flags | needs | costs |
|---|---|---|---|
| Re-aggregate only — **the default** | `--skip-extract --skip-classify` | nothing | nothing |
| Refresh data | `--skip-classify` | university VPN (production MySQL) | nothing |
| Full weekly run | *(no flags)* | VPN + Azure OpenAI | per new message |
| Publish an existing reviewed document | `--from FILE` | nothing | nothing |

**Extract and classify are opt-in, never implied.** If the user does not choose, fall back to
`--skip-extract --skip-classify`, and say plainly in the question that this default
**publishes the corpus as it already stands and does not pull in newer StatsBot activity** —
otherwise silence reads as "refresh everything" and the operator finds out from the numbers.
Both opt-in modes have a real precondition (VPN) or a real cost (per-message Azure OpenAI),
which is exactly why neither may happen by default.

State the recommendation in the option description — the text of the turn that asks is not
shown to the user, so the reasoning has to live in the options themselves. A presentation or
schema change that leaves the numbers alone wants **re-aggregate only**; a genuine weekly
refresh is the case for opting in.

Remember constraint 5: extract is strictly read-only against the live StatsBot DB, and
`--skip-extract` is the flag that avoids needing it at all.

## 3 · Review, then publish that document

The human gate (D-37) is the point of this step. Aggregate to a file first and *read it*:

```bash
cd pipeline && .venv/bin/python -m statsboteval_pipeline.cli run-weekly \
  --corpus data/corpus.duckdb <mode flags> \
  --out data/aggregates-review-$(date -u +%Y%m%d).json
```

Print the numbers a person can sanity-check — headline totals per window, and anything the
change was supposed to move. Compare against the last published document
(`pipeline/data/aggregates-*.json`, gitignored) and explain any difference before uploading.
An unexplained change is a stop, not a footnote.

Then publish exactly what was reviewed:

```bash
infra/scripts/04_publish_production.sh --from pipeline/data/aggregates-review-YYYYMMDD.json
```

The script re-runs the publish guard on those bytes, refuses anything whose
`data_provenance` is not `production`, uploads the immutable blob plus `latest.json`
(contract §9), and curls the live URL back.

## 4 · Deploy the bundle, if code changed

```bash
infra/scripts/02_deploy_app.sh
```

Builds the dashboard with pnpm (`pnpm-lock.yaml` is the lockfile — not npm), stages
`app/ + schema/ + static/`, and zip-deploys for Oryx to build server-side. Takes a few
minutes; the first request afterwards is a cold start.

Do **not** set `NEXT_PUBLIC_DATA_SOURCE=fixture` in the environment when building for
deploy — it inlines the synthetic fixture into the bundle at build time and the live site
would serve fake numbers. If a dev shell has it exported, unset it first.

## 5 · Verify like a reader, not like a script

```bash
curl -sf https://statsboteval.azurewebsites.net/healthz
curl -sf https://statsboteval.azurewebsites.net/api/v1/aggregates | jq '{schema_version, data_provenance, data_through_week}'
```

Then open the page and look at the thing that changed. `healthz` says the process boots;
it says nothing about whether the new tab renders. If Chrome tools are available, screenshot
the affected tab and put the path in the reply.

Cache: the API holds the blob for `CACHE_TTL_SECONDS` (default 300), so a fresh publish can
take up to 5 minutes to appear. Do not diagnose a stale read before that has elapsed.

## 6 · Record it

A publish is a fact about the project, so leave a trace:

- Append to `docs/decisions.md` if this go-live decided something (a first, a rollback, a
  gate closing). Routine republishes do not need an ADR.
- Commit and push whatever the run produced (scripts, docs, regenerated artifacts).
- Report the blob names, the live schema/provenance, and what a reader should now see.

## Rollback

The blob is versioned and immutable, so rolling back data is a republish of an older
document: `04_publish_production.sh --from <that file>`. Rolling back code is
`02_deploy_app.sh` from an earlier commit. A label-version rollback is different again —
point `CLASSIFIER_LABEL_VERSION` / `--classification-version` at the older version and
re-aggregate; no re-classification (see CLAUDE.md).

# Weekly-run automation — scheduling `run-weekly` (draft)

**Date:** 2026-07-27 · **Status:** WORK IN PROGRESS — open questions unanswered, do not implement yet
**Decision to record at implementation:** next free number at implementation time
(D-45/D-46 were taken by the 2026-07-28 classifier grid)

## Current state

`run-weekly` is **entirely manual today.** Verified 2026-07-27: `crontab -l` holds only
unrelated frappe-bench backups, `~/Library/LaunchAgents/` has no StatsBotEval agent, and
neither `docs/` nor `infra/` mentions cron, launchd, or scheduling anywhere. Every publish
since go-live (D-37) has been an operator running the command by hand.

## Four constraints that shape what automation is possible

1. **VPN.** The extract needs the Uni Wien VPN. This has already bitten — D-42 records a
   publish where the extract was skipped because the VPN was down.
2. **`cron` is the wrong tool on a Mac.** If the laptop is asleep at the scheduled time,
   cron simply skips the run and never catches up. `launchd` with `StartCalendarInterval`
   fires on the next wake. So: **launchd, not cron.**
3. **There is currently a human gate.** The classification runbook says run with `--out`,
   "review, then add `--upload`". Full automation would delete that gate.
4. **Unattended Azure spend.** Classification is metered per new message.

## Recommendation: semi-automate

A weekly LaunchAgent runs `run-weekly --out` (**no** `--upload`), writes a timestamped
review JSON and a log, and notifies the operator. The operator reviews and uploads with one
command.

This kills the tedium — remembering, connecting the VPN, waiting tens of minutes — while
keeping the publish decision human. That matches the posture the rest of the pipeline
already takes (the theme review gate in D-33, the publish guard). Full auto-publish would
be the only point in this system where data reaches the public URL without a person
looking at it first.

## The bigger question this sits inside: where does the pipeline *run*? (owner, 2026-07-27)

Owner position: **keeping the corpus and the weekly run on a single laptop is not
sustainable.** The scheduling question above is a symptom; the real issues are a single
point of failure holding the only copy of an irreplaceable-until-2027 corpus, availability
(the machine must be awake, on VPN, and not in use), and a bus factor of one.

**This cannot be solved by "move `run-weekly` to the cloud" as normally understood.**
Binding constraint 1 (consent addendum → `ethics/data-handling.md`; D-04; the D-34
architecture sign-off) is that pseudonymized chat histories live on a **password-protected
local storage medium only**. The corpus contains chat text. Hosting it on an Azure VM or any
cloud volume contradicts the consented architecture — that is an ethics-approval question,
not an engineering choice, and it would need the study leader plus a consent/ethics
amendment before it could even be designed.

What is *not* blocked, and is worth separating carefully:

- **Classification already runs "in the cloud"** and always has. Chat text transits to Azure
  OpenAI EU Data Zone Standard transiently (constraint 3 — consented practice). It is the
  corpus **at rest** that must stay local. Compute location and storage location are
  different questions and the consent document only constrains the second.
- **Wall time is a weaker argument than it first appears.** The multi-hour figures in the
  batch-size and grid trials are for a **full re-classification**, which happens once per
  label version. The *weekly increment* is ~50–100 new messages — single-digit minutes at
  any batch size. Automation should not be justified on weekly wall time.

Options, ranked by how much they solve per unit of approval friction:

1. **Dedicated always-on local host** (Mac mini / NUC on an encrypted volume, in the
   office). Consent-safe with no amendment — it is still a password-protected local storage
   medium — and it fixes availability, scheduling, and the "laptop asleep" problem outright.
   Does **not** fix bus factor or backup on its own; pair it with an encrypted offline backup
   of the corpus.
2. **University-managed VM inside Uni Wien.** Plausibly *better* protected than any laptop,
   and removes the VPN hop for the extract. But it is a change of custody: whether it counts
   as the consented "local storage medium" is a reading of the addendum that only the study
   leader can give. **Ask Leonardo/Daniel before designing anything on this.**
3. **Azure (or any public cloud) VM holding the corpus.** Currently **ruled out** by the
   consent addendum and D-04/D-34. Revisit only with an explicit ethics amendment; note the
   corpus is deletion-bound end-2027 anyway, which shortens the payback on that effort.
4. **Reduce what must run at all.** The extract is incremental by watermark and the
   classifier idempotent by `(history_id, label_version)`, so a missed week costs nothing but
   freshness — the pipeline is already designed to tolerate irregular operation. This is an
   argument for *lowering the stakes* of scheduling rather than engineering around them.

Related operational note found the same day: with the Uni Wien VPN up, **outbound SSH
(port 22) is blocked** — `git push` over SSH times out and needs the HTTPS remote. Any
automation that both extracts (VPN required) and pushes to git in the same window must use
HTTPS.

**Recommended sequencing:** option 1 unblocks everything below it and needs no approval;
put option 2 to Leonardo/Daniel in the same conversation as the other open Bergmann items.
Do not design option 3 speculatively.

## Open questions — answer before implementing

- [ ] **Review gate or full auto-publish?** (Recommendation: keep the gate.)
- [ ] **Day and time?** ISO weeks run Mon–Sun, so a Monday-morning run captures a complete
      prior week. Proposed: Monday 09:00.
- [ ] **Failure notification channel** — macOS notification banner, email, or a log file
      the operator checks?
- [ ] **VPN-down behaviour** — should the script fall back to `--skip-extract` and publish
      anyway, or abort and retry later? Aborting is safer; skipping keeps the dashboard
      fresh but silently stale on the extract side.
- [ ] **Where does the run live?** (see the section above) — settle the host before
      building the LaunchAgent, since a dedicated always-on host changes the sketch below
      from a user LaunchAgent on a sleeping laptop to a daemon on a machine that is always
      awake, and removes the "cron vs launchd" wake-up problem entirely.
- [ ] **Corpus backup and custody** — independent of scheduling, and currently unaddressed:
      the corpus is reproducible from the source DB until mid-2027 (D-20), which is the
      real safety net, but that guarantee expires before the data-retention deadline does.

## Sketch (not yet built)

- `~/Library/LaunchAgents/at.ac.univie.statsboteval.weekly.plist` with
  `StartCalendarInterval`, `WorkingDirectory` = `pipeline/`, `StandardOutPath` /
  `StandardErrorPath` to a git-ignored log.
- A wrapper script (launchd cannot do shell substitution, so the timestamped `--out`
  filename needs one) — candidate home: `infra/scripts/`.
- Secrets keep coming from `pipeline/.env` via `--env-file`; use absolute paths throughout.

## Related

- `docs/runbooks/classification.md` — the manual weekly procedure this would wrap
- D-37 (go-live), D-38 (`run-weekly` chaining), D-42 (a publish where VPN was down)

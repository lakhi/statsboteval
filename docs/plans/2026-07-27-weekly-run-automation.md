# Weekly-run automation — scheduling `run-weekly` (draft)

**Date:** 2026-07-27 · **Status:** WORK IN PROGRESS — open questions unanswered, do not implement yet
**Decision to record at implementation:** D-46 (proposed)

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

## Open questions — answer before implementing

- [ ] **Review gate or full auto-publish?** (Recommendation: keep the gate.)
- [ ] **Day and time?** ISO weeks run Mon–Sun, so a Monday-morning run captures a complete
      prior week. Proposed: Monday 09:00.
- [ ] **Failure notification channel** — macOS notification banner, email, or a log file
      the operator checks?
- [ ] **VPN-down behaviour** — should the script fall back to `--skip-extract` and publish
      anyway, or abort and retry later? Aborting is safer; skipping keeps the dashboard
      fresh but silently stale on the extract side.

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

# Source data dictionary — StatsBot MySQL schema

Describes the production data StatsBotEval ingests. Source of truth: the StatsBot repo
(`~/Developer/uni-studAsst-projects/statsbot/psy-lehrprojekt-backend-main`), migrations
`2024_07_12_170459_create_students_table.php` and `2024_07_12_171027_create_history_table.php`,
verified against `routes/api.php` and `AuthenticateStudent` middleware on 2026-06-10;
**re-verified against the live production schema on 2026-07-07** (Phase B Task 1 recon) —
prod drifts from the repo migrations, see the ⚠️ notes below.
**If StatsBot's schema changes, update this file in the same change.**

**The production DB is LIVE and strictly read-only for StatsBotEval** (owner directive
2026-07-07): the project analyzes StatsBot's data and never modifies it. Every connection
we open runs `SET SESSION TRANSACTION READ ONLY` as its init command and issues only
`SELECT`/`SHOW` — no INSERT/UPDATE/DELETE/DDL, ever.

Research-relevant tables: `students`, `history`, plus the roster table `import`
(documented below; holds direct identifiers, never extracted). The rest (`users`, `cache`,
`cache_locks`, `jobs`, `job_batches`, `failed_jobs`, `sessions`, `migrations`,
`password_reset_tokens`, `personal_access_tokens`) are Laravel scaffolding.

## `students` — one row per student

Live prod schema (2026-07-07). ⚠️ **Prod-vs-repo drift, resolved:** the repo migrations'
`matnr` and `lv` columns **do not exist in production** — the consent names the
matriculation number as stored, and it is, but in the `import` roster table below, not
here. Per-course segmentation via `students.lv` is off the table. Prod instead added a
`registered` flag the migrations lack.

| column | type | notes |
|---|---|---|
| `id` | bigint PK | referenced by `history.student_id` |
| `uid` | string | u:account ID from Shibboleth — **direct identifier**; pseudonymization input (normalize — trim + lowercase — before HMAC, or pseudonyms silently fork) |
| `firstname` | string | from Shibboleth `givenName` — **direct identifier**; stripped in ETL |
| `lastname` | string | from Shibboleth `sn` — **direct identifier**; stripped in ETL |
| `token_limit` | int | set from `TOKEN_LIMIT` env at registration |
| `token_left` | int | decremented by `total_tokens` per exchange |
| `registered` | bool, default 0 | access-flow flag set on first real login after the column was introduced (`routes/api.php`, middleware); only 44/550 are 1 while 443 students have messages — **not usable for historical analysis** |
| `activated` | bool | access kill-switch; new students auto-activated |
| `created_at` | timestamp | registration time — ⚠️ same timezone skew as `history.created_at`, see "Timestamps & timezone" |
| `updated_at` | timestamp | Laravel-managed, not research-relevant |

## `history` — one row per question/answer exchange

| column | type | notes |
|---|---|---|
| `id` | bigint PK | candidate message identifier for joining external classifications |
| `student_id` | bigint FK | → `students.id` |
| `sent` | text | the student's message, verbatim (only the **last** user message of the turn is stored) |
| `received` | text | the GPT reply, verbatim |
| `prompt_tokens` | int | ⚠️ counts the **entire re-sent conversation context**, not just the new message — it grows over a session. Not a message-size metric. |
| `completion_tokens` | int | tokens in the reply |
| `total_tokens` | int | prompt + completion; what gets deducted from `token_left` |
| `started` | bigint | **client-side `Date.now()` (epoch ms) generated when the student clicks "new chat"; doubles as the session/conversation ID** — all rows of one student sharing a `started` value form one dialog. Not globally unique: the session key is **(`student_id`, `started`)**. Client clock, may be skewed. |
| `created_at` | timestamp | server-side receive time — **the reliable clock for temporal analysis**, but read it with the server-default session timezone (see "Timestamps & timezone") |
| `updated_at` | timestamp | Laravel-managed, not research-relevant |

## `import` — course roster (allow-list), not written by any code path

Live prod table (4,482 rows, one per distinct `uid`) absent from the repo snapshot; no
backend code reads it — it is a manually loaded export of the **"MethodsHub"** Moodle
course roster (`Gruppen` = "MethodsHub" for 4,424 rows, blank/header noise for the rest).
Columns: `Vorname`, `Nachname`, `Matrikelnummer`, `E-Mail-Adresse`, `uid`, `Gruppen` —
**all direct identifiers except `Gruppen`; StatsBotEval never extracts this table.**

Facts that matter for analysis:
- **No program level here either:** `Gruppen` is one Moodle course for everyone, so the
  Bergmann `Status` column (bachelor/master/other) is confirmed **not derivable from the
  production DB** — it came from outside (Daniel/coordinators; still open).
- **Roster coverage as a staff/student proxy:** 540 of 550 `students` rows and 435 of 443
  messaging students match the roster on normalized `uid`; the unmatched ~8–10 are
  plausibly the faculty pre/postdocs Bergmann called "Other". Weak signal, not a
  program-level substitute.
- **Milestone-2 linkage:** the matriculation number the consent names as stored lives
  here (`Matrikelnummer` ↔ `uid`), so a course-records linkage key exists in principle —
  consent-compatibility check required before any use (see `open-questions.md`,
  milestone 2 gates).

## Timestamps & timezone (verified empirically 2026-07-07)

**Finding:** Laravel writes `created_at` as a **UTC wall-clock string** (`config/app.php`
`'timezone' => 'UTC'`), but the MySQL session interprets it as **Europe/Vienna local**
(`@@system_time_zone = CEST`, session tz `SYSTEM`) before converting to the `timestamp`
column's internal UTC. The internal value is therefore skewed 1–2 h behind true UTC.

**Evidence:** per session, `UNIX_TIMESTAMP(first created_at) − started/1000` under
`time_zone='+00:00'` has monthly medians ≈ **−3,530 s in CET months and −7,150 s in CEST
months** (offset + ~1 min median typing time) across all 1,871 sessions, 2024-07 → 2026-07.

**Extraction rule:** read `created_at` with the **server-default session timezone**
(i.e., don't touch `time_zone`) — the round-trip then reproduces the string Laravel
wrote, which **is true UTC**. Store it as UTC in the corpus (the migration-001 "UTC
assumed" comment holds). Never read with `time_zone='+00:00'`, which yields the skewed
internal value. Caveat: rows written during ~1–2 h around each DST transition can be off
by 1 h after the round-trip — a handful of messages per year, accepted.

## Behavioral facts that shape analysis (verified in code)

- **No system prompt exists in the application.** The `/messages` endpoint validates roles as
  `user|assistant` only; any persona must live in the Azure deployment configuration.
  Whether one exists there is unresolved (`open-questions.md`).
- **No per-row model identity.** The Azure model/deployment is `.env` configuration; if it
  changed since March 2025, the data cannot say which model produced which answer. A model
  timeline must be reconstructed externally.
- The client shows a **static tutor welcome message that is stripped before sending**
  (frontend `data.service.ts`) — it never appears in `history`.
- The full prior conversation is re-sent to the model each turn, but only the newest exchange
  is persisted as a row.
- StatsBotEval treats **one `started` session as one conversation** (decision D-08), keyed by
  (`student_id`, `started`) — `started` alone is a client-generated timestamp and could in
  principle collide across students. The Bergmann Stage-2 manuscript confirms their extract
  carried this same key ("chat ID", context variable 3) and that they reconstructed chats
  with it — their conversation definition and ours coincide, so per-chat numbers (e.g.
  messages/chat: master 2.5, bachelor 1.8) are directly comparable.

## Scale reference

**Production volumes (recon 2026-07-07, live DB):**

| measure | value |
|---|---|
| students | 550 (541 activated; registrations 2024-07-24 → 2026-06-26) |
| students with ≥1 message | 443 |
| messages (`history` rows) | 4,412 (2024-07-24 → 2026-07-03; DB is live and growing) |
| sessions (distinct (`student_id`,`started`)) | 1,871 (≈2.4 messages/session) |
| student text volume | Σ `CHAR_LENGTH(sent)` ≈ 1.95 M chars (avg 443 chars ≈ ~120 tokens/message) |

Period structure: a handful of team-test rows (2024-07 → 2024-10, ~24 messages) predate
the pilot; the pilot period (2024-11 → 2025-01, ≈724 messages) precedes the Bergmann
study window; 2025-03 → 2025-06 holds ≈1,494 messages in prod vs. the study's cleaned
1,400 (delta = their exclusions; Task 3 of the Phase B plan reconciles exactly).
Semester rhythm is visible (June peaks: 653 in 2025, 385 in 2026).

**Bergmann study reference** (Stage-2 manuscript, OSF 2026-06-30): 1,400 messages from
**182 users** between 2025-03-15 and 2025-06-30 — bachelor: 584 messages / 63 students
(invited only from 2025-05-16); master: 776 / 105; "other" (faculty pre/postdocs): 40 /
14. Their extract carried a per-student `Status` (program level) column now **confirmed
absent from the production DB** (2026-07-07 recon, incl. the `import` roster) — it came
from outside the DB; source still an open question (Daniel).

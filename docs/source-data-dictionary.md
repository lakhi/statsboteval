# Source data dictionary — StatsBot MySQL schema

Describes the production data StatsBotEval ingests. Source of truth: the StatsBot repo
(`~/Developer/uni-studAsst-projects/statsbot/psy-lehrprojekt-backend-main`), migrations
`2024_07_12_170459_create_students_table.php` and `2024_07_12_171027_create_history_table.php`,
verified against `routes/api.php` and `AuthenticateStudent` middleware on 2026-06-10.
**If StatsBot's schema changes, update this file in the same change.**

Only these two tables are research-relevant; the database's other tables (`users`, `cache`,
`jobs`, `personal_access_tokens`) are unused Laravel scaffolding.

## `students` — one row per student

| column | type | notes |
|---|---|---|
| `id` | bigint PK | referenced by `history.student_id` |
| `uid` | string | u:account ID from Shibboleth — **direct identifier**; pseudonymization input (normalize — trim + lowercase — before HMAC, or pseudonyms silently fork) |
| `firstname` | string | from Shibboleth `givenName` — **direct identifier**; stripped in ETL |
| `lastname` | string | from Shibboleth `sn` — **direct identifier**; stripped in ETL |
| `matnr` | string | matriculation number — **direct identifier**. ⚠️ In the schema and named in the consent, but **never written by any code path in the repo snapshot** (neither register route nor middleware). Prod may differ — unresolved, see `open-questions.md`. Natural key for milestone-2 course-record linkage. |
| `lv` | string | course (Lehrveranstaltung) — ⚠️ also never written by repo code. Needed for per-course dashboard segmentation if populated. |
| `token_limit` | int | set from `TOKEN_LIMIT` env at registration |
| `token_left` | int | decremented by `total_tokens` per exchange |
| `activated` | bool | access kill-switch; new students auto-activated |
| `created_at` | timestamp | registration time |

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
| `created_at` | timestamp | server-side receive time — **the reliable clock for temporal analysis** |

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
  principle collide across students. Note the Bergmann study instead reconstructed sequences
  via student + time; definitions must be stated when comparing numbers.

## Scale reference

Per the Bergmann study (Stage-2 manuscript, published on OSF 2026-06-30): 1,400 messages
from **182 users** between 2025-03-15 and 2025-06-30 — bachelor: 584 messages / 63 students
(invited only from 2025-05-16); master: 776 / 105; "other" (faculty pre/postdocs): 40 / 14.
Their extract also carried a per-student `Status` (program level) column that neither table
above holds — its source is an open question. Current production volume is larger and
unconfirmed.

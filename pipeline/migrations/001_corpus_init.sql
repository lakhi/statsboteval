-- Corpus schema v1: pseudonym-keyed, never holds direct identifiers
-- (see docs/source-data-dictionary.md for the source columns these mirror).

CREATE TABLE students (
  pseudonym     TEXT PRIMARY KEY,       -- HMAC output in prod; syn-NNNN in fixtures
  registered_at TIMESTAMP NOT NULL
);

CREATE TABLE messages (
  history_id        BIGINT PRIMARY KEY, -- source history.id
  pseudonym         TEXT NOT NULL,
  session_started   BIGINT NOT NULL,    -- client epoch ms; (pseudonym, session_started) = session (D-08)
  created_at        TIMESTAMP NOT NULL, -- server clock (UTC assumed); THE temporal axis
  sent              TEXT NOT NULL,
  received          TEXT NOT NULL,
  prompt_tokens     INTEGER NOT NULL,
  completion_tokens INTEGER NOT NULL
);

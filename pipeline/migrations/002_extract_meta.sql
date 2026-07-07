-- Corpus metadata (key/value). First use: the pepper SHA-256 fingerprint (D-34
-- interlock) — stored at first real ingest, verified by every later extract run,
-- so a wrong or rotated pepper fails loudly instead of silently forking pseudonyms.
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

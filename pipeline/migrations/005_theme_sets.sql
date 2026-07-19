-- Emergent-theme machinery (D-33, Phase B Stage 2).
--
-- theme_candidates: raw stage-1 candidate codes per message — derived from real
-- chat text, so they stay LOCAL FOREVER and are never published; only the
-- operator-reviewed theme_sets list may reach aggregates. A row with code = ''
-- marks a message processed with zero candidates (keeps the anti-join resume
-- exact); synthesis excludes it.
--
-- theme_sets: versioned, operator-reviewed theme lists. A set is usable for
-- assignment only once reviewed_at is stamped by `freeze-themes` — the review
-- is the privacy control (D-33).

CREATE TABLE theme_candidates (
  history_id BIGINT NOT NULL,   -- FK-in-spirit to messages.history_id
  run_id     TEXT   NOT NULL,   -- generation run, e.g. 'statsboteval-themes-v1'
  code       TEXT   NOT NULL,   -- normalized short candidate code ('' = none)
  PRIMARY KEY (history_id, run_id, code)
);

CREATE TABLE theme_sets (
  set_version TEXT      NOT NULL,   -- 'statsboteval-themes-v1', ...
  code        TEXT      NOT NULL,   -- the theme label as published
  description TEXT      NOT NULL,   -- one-line meaning, shown at review
  created_at  TIMESTAMP NOT NULL,
  reviewed_at TIMESTAMP,            -- NULL until the operator freeze (D-33)
  PRIMARY KEY (set_version, code)
);

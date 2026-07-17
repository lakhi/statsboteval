-- Versioned message labels (D-07): one tidy table for every label version —
-- 'lang-heuristic-v1' now (GL3); 'bergmann-v1' / 'statsboteval-v1' in Phase B.
-- Deductive rows store explicit 0/1 (MCC needs true negatives); theme and
-- language rows store only assignments (value = 1).

CREATE TABLE labels (
  history_id    BIGINT  NOT NULL,   -- FK-in-spirit to messages.history_id
  label_version TEXT    NOT NULL,   -- 'lang-heuristic-v1' | 'bergmann-v1' | 'statsboteval-v1'
  domain        TEXT    NOT NULL,   -- 'language' | 'deductive' | 'method_theme'
                                    --   | 'software_theme' | 'emergent_theme'
  code          TEXT    NOT NULL,   -- category name, theme label, or language code
  value         INTEGER NOT NULL,
  provenance    TEXT    NOT NULL,   -- 'lingua-py' | 'human_consensus' | 'gpt5' | model@date
  PRIMARY KEY (history_id, label_version, domain, code)
);

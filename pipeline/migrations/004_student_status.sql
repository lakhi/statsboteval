-- Program-level status dimension (D-39): one row per student, resolved to
-- status-at-usage-time at query time via ma_start_semester (S -> Mar 1,
-- W -> Oct 1). Populated by `import-status` from the roster-derived CSV that
-- lives OUTSIDE the repo tree (docs/ethics/data-handling.md, program-level
-- section); only HMAC pseudonyms are stored here.

CREATE TABLE student_status (
  pseudonym         TEXT PRIMARY KEY,   -- FK-in-spirit to students.pseudonym
  status            TEXT NOT NULL,      -- 'bachelor' | 'master' | 'staff'
  ma_start_semester TEXT,               -- NULL unless BA->MA transitioner ('2025W', ...)
  provenance        TEXT NOT NULL       -- source roster list, e.g. 'master-mar25'
);

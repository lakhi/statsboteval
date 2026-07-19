// SYNTHETIC design fixture generator — no real student data, all numbers invented.
// Emits a contract-v1-shaped aggregates document covering every Phase A section,
// semester/trailing/all-time windows, and all three cell states (ok / ok:0 /
// suppressed), so the dashboard can be designed against realistic shapes before
// the pipeline publishes them (see docs/aggregates-contract.md).
//
//   node dev-fixtures/generate.mjs > dev-fixtures/aggregates.fixture.json
//
// Deterministic (seeded PRNG): regenerating produces the identical file.

const FIRST_WEEK_MONDAY = new Date(Date.UTC(2025, 2, 10)); // 2025-W11
const LAST_WEEK_MONDAY = new Date(Date.UTC(2026, 5, 29)); // 2026-W27
const FLOOR_N = 3;

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(20260707);

const DAY = 24 * 60 * 60 * 1000;
const addDays = (d, n) => new Date(d.getTime() + n * DAY);
const iso = (d) => d.toISOString().slice(0, 10);

// ISO-8601 week label for a Monday.
function weekLabel(monday) {
  const thu = addDays(monday, 3);
  const isoYear = thu.getUTCFullYear();
  const jan4 = new Date(Date.UTC(isoYear, 0, 4));
  const week1Monday = addDays(jan4, -((jan4.getUTCDay() + 6) % 7));
  const week = Math.round((monday.getTime() - week1Monday.getTime()) / (7 * DAY)) + 1;
  return `${isoYear}-W${String(week).padStart(2, "0")}`;
}

const mondays = [];
for (let d = FIRST_WEEK_MONDAY; d <= LAST_WEEK_MONDAY; d = addDays(d, 7)) mondays.push(d);
const weeks = mondays.map(weekLabel);

// Semester rule (contract §6.1): a week belongs to the semester containing its
// Thursday. SS = Mar 1–Jun 30, WS = Oct 1–Jan 31 (following year).
function semesterOf(monday) {
  const thu = addDays(monday, 3);
  const y = thu.getUTCFullYear();
  const m = thu.getUTCMonth(); // 0-based
  if (m >= 2 && m <= 5) return { id: `${y}S`, label: `Summer semester ${y}` };
  if (m >= 9) return { id: `${y}W`, label: `Winter semester ${y}/${(y + 1) % 100}` };
  if (m === 0) return { id: `${y - 1}W`, label: `Winter semester ${y - 1}/${y % 100}` };
  return null; // break weeks (Feb, Jul–Sep)
}

// ---- weekly cohort rhythm ------------------------------------------------
// students(week): semester ramp with an exam-season bump, ~0–2 in breaks.
function studentsForWeek(monday, i) {
  const sem = semesterOf(monday);
  if (!sem) return rnd() < 0.55 ? 0 : Math.floor(rnd() * 3); // break: 0..2
  const month = addDays(monday, 3).getUTCMonth();
  const exam = month === 5 || month === 0 ? 4 : 0; // June / January bump
  const base = 6 + Math.floor(6 * Math.sin((i % 17) / 17 * Math.PI));
  return Math.max(3, base + exam + Math.floor(rnd() * 4));
}

const weekly = mondays.map((monday, i) => {
  const students = studentsForWeek(monday, i);
  const messages = students === 0 ? 0 : students * (5 + Math.floor(rnd() * 8));
  const sessions = students === 0 ? 0 : Math.max(students, Math.floor(messages / (2 + rnd() * 2)));
  return { monday, week: weeks[i], students, messages, sessions };
});

const cell = (students, value) =>
  students > 0 && students < FLOOR_N
    ? { status: "suppressed" }
    : { status: "ok", value };

const series = (rows, f) => ({ series: rows.map((r) => ({ week: r.week, cell: f(r) })) });

// ---- windows registry ----------------------------------------------------
const semesters = new Map();
for (const [i, monday] of mondays.entries()) {
  const sem = semesterOf(monday);
  if (!sem) continue;
  if (!semesters.has(sem.id)) semesters.set(sem.id, { ...sem, weeks: [] });
  semesters.get(sem.id).weeks.push(weeks[i]);
}
const semesterDates = {
  "2025S": ["2025-03-01", "2025-06-30"],
  "2025W": ["2025-10-01", "2026-01-31"],
  "2026S": ["2026-03-01", "2026-06-30"],
};
const windows = [
  {
    id: "all_time",
    kind: "all_time",
    label: "All time",
    coverage: { from: weeks[0], through: weeks.at(-1) },
  },
  ...[...semesters.values()].map((s) => ({
    id: s.id,
    kind: "semester",
    label: s.label,
    start_date: semesterDates[s.id][0],
    end_date: semesterDates[s.id][1],
    weeks: s.weeks,
    coverage: { from: s.weeks[0], through: s.weeks.at(-1) },
  })),
  {
    id: "trailing_4",
    kind: "trailing",
    label: "Last 4 weeks",
    weeks: weeks.slice(-4),
    coverage: { from: weeks.at(-4), through: weeks.at(-1) },
  },
];

// Distinct students per window (invented; NOT sums of weekly counts).
const windowStudents = { all_time: 118, "2025S": 61, "2025W": 74, "2026S": 66, trailing_4: 4 };
const rowsFor = (id) => {
  const w = windows.find((x) => x.id === id);
  const member = w.weeks ? new Set(w.weeks) : null;
  return weekly.filter((r) => (member ? member.has(r.week) : true));
};

// ---- per-window builders ---------------------------------------------------
function heatmap(id) {
  const n = windowStudents[id];
  const cells = [];
  for (let dow = 1; dow <= 7; dow++) {
    for (let hour = 0; hour < 24; hour++) {
      const day = dow <= 5 ? 1 : 0.35;
      const tod =
        hour >= 9 && hour <= 17 ? 1 : hour >= 18 && hour <= 22 ? 0.55 : hour >= 7 ? 0.3 : 0.02;
      const st = Math.min(FLOOR_N + 12, Math.round(n * 0.14 * day * tod * (0.6 + rnd() * 0.8)));
      cells.push({ dow, hour, cell: cell(st, st === 0 ? 0 : st * (2 + Math.floor(rnd() * 5))) });
    }
  }
  return { cells };
}

function histogram(id, unit, edges, spread, summaryBase, footnote_ids) {
  const n = windowStudents[id];
  const scale = Math.max(1, Math.round(n * 2.8));
  const bins = edges.map(([lo, hi], i) => {
    const st = Math.round(n * spread[i] * (0.75 + rnd() * 0.5));
    return { lo, hi, cell: cell(st, Math.round(scale * spread[i])) };
  });
  const summary =
    n >= FLOOR_N
      ? { status: "ok", n_students: n, ...summaryBase }
      : { status: "suppressed" };
  return { unit, bins, n_total: cell(n, scale), summary, ...(footnote_ids && { footnote_ids }) };
}

const perWindow = (f, ids = Object.keys(windowStudents)) =>
  Object.fromEntries(ids.map((id) => [id, f(id)]));

const langSplit = { de: 0.55, en: 0.35, other: 0.04, undetermined: 0.06 };

// ---- topics (schema 1.2.0) -------------------------------------------------
// Deductive labels are the PUBLIC manuscript category names; every theme label
// below is invented ("Synthetic …") — the real frozen/generated lists are
// git-ignored local materials (D-16/D-33) and never enter the repo.
const DEDUCTIVE = [
  "Statistics Interaction", "Specific Method", "Data Analysis Software",
  "Reference to a Prior Content", "Multiple Choice", "Question Posed",
  "Instruction Given", "Capability Request", "Declarative Statement",
  "English Input", "German Input", "Politeness Expression", "Greeting Expression",
];
const METHOD_THEMES = [
  "Synthetic regression theme", "Synthetic ANOVA-like theme",
  "Synthetic correlation theme with a deliberately long label",
  "Synthetic t-test theme", "Synthetic power-analysis theme", "Synthetic factor theme",
];
const SOFTWARE_THEMES = [
  "Synthetic software A", "Synthetic software B", "Synthetic software C", "Synthetic software D",
];
const EMERGENT_THEMES = [
  "Synthetic exam-preparation theme", "Synthetic homework-help theme",
  "Synthetic conceptual-confusion theme", "Synthetic tool-how-to theme",
  "Synthetic study-design theme",
];
// 1.2.0: emergent items carry their reviewed one-line definitions (tooltips).
const EMERGENT_DESCRIPTIONS = Object.fromEntries(
  EMERGENT_THEMES.map((label) => [label, `Synthetic one-line description of the ${label.toLowerCase()}.`]),
);

function topicDistribution(id, labels, statusShare, footnote_ids, descriptions) {
  const n = Math.round(windowStudents[id] * statusShare);
  const msgs = Math.round(rowsFor(id).reduce((a, r) => a + r.messages, 0) * statusShare);
  const items = labels.map((label, i) => {
    const share = Math.min(0.85, 0.9 / (i + 1.4)); // long tail; guarantees zeros late
    const st = Math.round(n * share * (0.55 + rnd() * 0.7));
    return {
      label,
      cell: cell(st, st === 0 ? 0 : Math.max(1, Math.round(msgs * share * (0.2 + rnd() * 0.5)))),
      ...(descriptions?.[label] && { description: descriptions[label] }),
    };
  });
  return { items, n_total: cell(n, msgs), ...(footnote_ids && { footnote_ids }) };
}

function topicGroup(id, statusShare, { withStatusRule = false, withEmergent = true } = {}) {
  const notes = withStatusRule
    ? ["multi_label", "label_provenance", "status_rule"]
    : ["multi_label", "label_provenance"];
  return {
    deductive: topicDistribution(id, DEDUCTIVE, statusShare, notes),
    method_themes: topicDistribution(id, METHOD_THEMES, statusShare, notes),
    software_themes: topicDistribution(id, SOFTWARE_THEMES, statusShare, notes),
    ...(withEmergent && {
      emergent_themes: topicDistribution(id, EMERGENT_THEMES, statusShare, notes, EMERGENT_DESCRIPTIONS),
    }),
  };
}

// trailing_4 omitted -> exercises the topics WindowGap state; 2025S omits
// emergent_themes -> exercises the per-card absent state. Staff share is small
// enough to suppress in the smaller windows; "unknown" published only where
// non-empty (all_time).
const statusShares = { bachelor: 0.36, master: 0.5, staff: 0.06 };
const topics = {
  per_window: Object.fromEntries(
    Object.keys(windowStudents)
      .filter((id) => id !== "trailing_4")
      .map((id) => {
        const withEmergent = id !== "2025S";
        return [
          id,
          {
            ...topicGroup(id, 1, { withEmergent }),
            by_status: {
              ...Object.fromEntries(
                Object.entries(statusShares).map(([status, share]) => [
                  status,
                  topicGroup(id, share, { withStatusRule: true, withEmergent }),
                ]),
              ),
              ...(id === "all_time" && {
                unknown: topicGroup(id, 0.04, { withStatusRule: true, withEmergent }),
              }),
            },
          },
        ];
      }),
  ),
  theme_set_version: "statsboteval-themes-v1",
};

const doc = {
  schema_version: "1.2.0",
  generated_at: "2026-07-06T05:12:33Z",
  data_through_week: weeks.at(-1),
  data_through_date: iso(addDays(LAST_WEEK_MONDAY, 6)),
  first_week: weeks[0],
  privacy_floor_n: FLOOR_N,
  label_versions: { language: "lang-heuristic-v1", classification: "statsboteval-v1" },
  timezone: "Europe/Vienna",
  data_provenance: "synthetic",
  pipeline_version: "0.1.0+design-fixture",
  windows,
  footnotes: {
    chat_fragmentation: {
      text: "The credit-limit UI nudges students toward starting new chats; conversation counts may overstate distinct dialogues.",
    },
    bachelor_onboarding: {
      text: "The bachelor cohort exists only from 2025-05-16; trends crossing that boundary partly reflect cohort composition, not behavior.",
    },
    language_heuristic: {
      text: "Language is detected by a local heuristic (lang-heuristic-v1); very short or mixed-language messages may be misclassified.",
    },
    user_class_definitions: {
      text: "One-time / monthly / sporadic follow the Bergmann et al. Stage-2 operational definitions.",
    },
    duration_definition: {
      text: "Session duration = last minus first server timestamp in the session; single-message sessions count as 0 minutes.",
    },
    multi_label: {
      text: "A message may carry several categories or themes, so topic counts do not sum to the message total.",
    },
    label_provenance: {
      text: "Topics come from automated classification; label_versions.classification names the exact classifier version.",
    },
    status_rule: {
      text: "Program level comes from coordinator roster lists; students who moved from bachelor to master are counted by their status at usage time (per session).",
    },
  },
  sections: {
    temporal_usage: {
      weekly: {
        messages: series(weekly, (r) => cell(r.students, r.messages)),
        sessions: {
          ...series(weekly, (r) => cell(r.students, r.sessions)),
          footnote_ids: ["chat_fragmentation"],
        },
        active_students: series(weekly, (r) => cell(r.students, r.students)),
      },
      per_window: perWindow((id) => ({ activity_heatmap: heatmap(id) })),
    },
    usage_context: {
      weekly: {
        registrations: {
          ...series(weekly, (r) => {
            const sem = semesterOf(r.monday);
            const wk = Number(r.week.slice(6));
            const spike = sem && (wk === 10 || wk === 40 || r.week === "2025-W20");
            const regs = spike ? 8 + Math.floor(rnd() * 14) : rnd() < 0.5 ? 0 : Math.floor(rnd() * 4);
            return cell(regs, regs);
          }),
          footnote_ids: ["bachelor_onboarding"],
        },
      },
      per_window: perWindow((id) => {
        const n = windowStudents[id];
        const rows = rowsFor(id);
        const msgs = rows.reduce((a, r) => a + r.messages, 0);
        const sess = rows.reduce((a, r) => a + r.sessions, 0);
        const oneTime = Math.round(n * 0.55);
        const monthly = Math.round(n * 0.1);
        return {
          totals: {
            active_students: cell(n, n),
            messages: cell(n, msgs),
            sessions: cell(n, sess),
            new_registrations: cell(n, Math.round(n * 0.8)),
          },
          user_classes: {
            one_time: cell(oneTime, oneTime),
            monthly: cell(monthly, monthly),
            sporadic: cell(n - oneTime - monthly, n - oneTime - monthly),
            footnote_ids: ["user_class_definitions"],
          },
        };
      }),
    },
    sessions: {
      per_window: perWindow((id) => ({
        messages_per_session: histogram(
          id,
          "sessions",
          [[1, 1], [2, 3], [4, 7], [8, null]],
          [0.55, 0.28, 0.12, 0.05],
          { median: 2.0, p25: 1.0, p75: 4.0, mean: 2.4, sd: 2.1 },
          ["chat_fragmentation"],
        ),
        session_duration_minutes: histogram(
          id,
          "sessions",
          [[0, 1], [2, 5], [6, 15], [16, 30], [31, null]],
          [0.34, 0.27, 0.22, 0.12, 0.05],
          { median: 4.0, p25: 1.0, p75: 12.0, mean: 8.1, sd: 11.4 },
          ["chat_fragmentation", "duration_definition"],
        ),
      })),
    },
    tokens: {
      // trailing_4 deliberately omitted → exercises the "no rollup for this
      // window" state in the dashboard.
      per_window: perWindow(
        (id) => ({
          completion_tokens_per_message: histogram(
            id,
            "messages",
            [[0, 100], [101, 250], [251, 500], [501, 1000], [1001, null]],
            [0.18, 0.31, 0.29, 0.16, 0.06],
            { median: 312.0, p25: 148.0, p75: 495.0, mean: 356.2, sd: 248.9 },
          ),
        }),
        Object.keys(windowStudents).filter((id) => id !== "trailing_4"),
      ),
    },
    language: {
      weekly: {
        messages_by_language: {
          ...Object.fromEntries(
            Object.entries(langSplit).map(([lang, share]) => [
              lang,
              series(weekly, (r) => {
                const st = Math.round(r.students * Math.min(1, share * 2.2) * (0.7 + rnd() * 0.6));
                return cell(st, st === 0 ? 0 : Math.round(r.messages * share));
              }),
            ]),
          ),
          footnote_ids: ["language_heuristic"],
        },
      },
      per_window: perWindow((id) => {
        const msgs = rowsFor(id).reduce((a, r) => a + r.messages, 0);
        return {
          totals: Object.fromEntries(
            Object.entries(langSplit).map(([lang, share]) => {
              const st = Math.round(windowStudents[id] * Math.min(1, share * 2.2));
              return [lang, cell(st, Math.round(msgs * share))];
            }),
          ),
        };
      }),
    },
    topics,
  },
};

process.stdout.write(JSON.stringify(doc, null, 2) + "\n");

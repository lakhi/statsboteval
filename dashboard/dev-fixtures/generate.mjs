// SYNTHETIC design fixture generator — no real student data, all numbers invented.
// Emits a contract-v1-shaped aggregates document covering every Phase A section,
// semester/slice/all-time windows, and all three cell states (ok / ok:0 /
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
// Full Thursday-rule membership, independent of the axis — the same rule windows.py
// applies. Needed because teaching-week indices (semester_week, and a slice's
// semester_weeks) count from a semester's first *member* week, which may sit before the
// first week this fixture's axis covers. Indexing against coverage instead would slide
// every curve in the overlay left by the number of missing opening weeks (D-54).
function fullMembership(startISO, endISO) {
  const start = new Date(startISO);
  const end = new Date(endISO);
  const out = [];
  let monday = addDays(start, -((start.getUTCDay() + 6) % 7));
  while (monday <= end) {
    const thu = addDays(monday, 3);
    if (thu >= start && thu <= end) out.push(weekLabel(monday));
    monday = addDays(monday, 7);
  }
  return out;
}

const semesterDates = {
  "2025S": ["2025-03-01", "2025-06-30"],
  "2025W": ["2025-10-01", "2026-01-31"],
  "2026S": ["2026-03-01", "2026-06-30"],
};
// Only the ANCHOR semester carries slices of its closing stretch (D-56, narrowed at D-57),
// and the anchor is the last one on the axis — the same rule windows.py applies. `short` is
// the abbreviated semester name a slice label reads in ("SS 2026"). Labels are state-free,
// so nothing here has to know whether the term is still running.
const members = (s) => fullMembership(...semesterDates[s.id]);
const shortName = (s) => (s.id.endsWith("S") ? `SS ${s.id.slice(0, 4)}` : `WS ${s.id.slice(0, 4)}/${(Number(s.id.slice(0, 4)) + 1) % 100}`);
const sliceFor = (s, take, suffix, stem) => {
  const held = s.weeks.slice(-take);
  const short = stem(held.length);
  return {
    id: `${s.id}.${suffix}`,
    kind: "semester_slice",
    label: `${short} · ${shortName(s)}`,
    // Unrendered since D-57 flattened the picker; published as the stem of `label`, and
    // kept because removing a required field is a major break (contract §10).
    short_label: short,
    parent_window_id: s.id,
    weeks: held,
    semester_weeks: [members(s).indexOf(held[0]) + 1, members(s).indexOf(held.at(-1)) + 1],
    coverage: { from: held[0], through: held.at(-1) },
  };
};
const anchor = [...semesters.values()].at(-1);
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
    // Full membership, not the covered weeks: `coverage` below is what clips to the
    // axis. Publishing coverage here made the fixture disagree with itself — a slice's
    // semester_weeks counts from the semester's first *member* week, so the index and
    // the list it indexes into started one week apart (contract._check_windows catches
    // exactly this, and nothing ran the fixture through it).
    weeks: members(s),
    coverage: { from: s.weeks[0], through: s.weeks.at(-1) },
  })),
  sliceFor(anchor, 4, "last4", (n) => `Previous ${n} weeks`),
  sliceFor(anchor, 1, "last1", () => "Last available week"),
];

// Distinct students per window (invented; NOT sums of weekly counts). Six entries, matching
// the registry above: only the anchor semester is sliced (D-57).
const windowStudents = {
  all_time: 118,
  "2025S": 61,
  "2025W": 74,
  "2026S": 66,
  "2026S.last4": 27,
  "2026S.last1": 4,
};
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

// 1.6.0 (D-54). Four equal six-hour blocks; the registry ships in the document so the
// dashboard holds no daypart definitions of its own. Mirrors aggregate.DAYPARTS.
const DAYPARTS = [
  { id: "night", label: "Night", from_hour: 0, to_hour: 6 },
  { id: "morning", label: "Morning", from_hour: 6, to_hour: 12 },
  { id: "afternoon", label: "Afternoon", from_hour: 12, to_hour: 18 },
  { id: "evening", label: "Evening", from_hour: 18, to_hour: 24 },
];
// Shape follows the real corpus: afternoon dominates, night is thin, and weekends
// tilt later in the day — so the fixture exercises the interaction the grid exists for.
const DAYPART_WEIGHT = { night: 0.03, morning: 0.3, afternoon: 0.52, evening: 0.15 };

function daypartHeatmap(id) {
  const n = windowStudents[id];
  const cells = [];
  for (let dow = 1; dow <= 7; dow++) {
    const weekend = dow >= 6;
    for (const part of DAYPARTS) {
      const tilt = weekend && (part.id === "evening" || part.id === "night") ? 1.9 : weekend ? 0.6 : 1;
      const st = Math.min(FLOOR_N + 20, Math.round(n * 0.5 * DAYPART_WEIGHT[part.id] * tilt * (0.6 + rnd() * 0.8)));
      cells.push({
        dow,
        daypart: part.id,
        cell: cell(st, st === 0 ? 0 : st * (2 + Math.floor(rnd() * 6))),
      });
    }
  }
  return { cells, footnote_ids: ["daypart_definition"] };
}

function daypartTotals(id) {
  const n = windowStudents[id];
  const msgs = rowsFor(id).reduce((a, r) => a + r.messages, 0);
  const by_daypart = Object.fromEntries(
    DAYPARTS.map((part) => {
      const st = Math.round(n * DAYPART_WEIGHT[part.id] * (0.7 + rnd() * 0.5));
      return [part.id, cell(st, Math.round(msgs * DAYPART_WEIGHT[part.id]))];
    }),
  );
  const weekendStudents = Math.round(n * 0.42);
  return {
    by_daypart,
    weekend: cell(weekendStudents, Math.round(msgs * 0.23)),
    weekday: cell(Math.round(n * 0.92), Math.round(msgs * 0.77)),
    footnote_ids: ["daypart_definition"],
  };
}

// Each semester re-indexed to teaching week. semester_week is the 1-based index into the
// semester's FULL membership, so a semester whose opening weeks are off-axis still starts
// where it really started — the fixture's 2025S does exactly that.
function semesterProfiles() {
  const byWeek = new Map(weekly.map((r) => [r.week, r]));
  return windows
    .filter((w) => w.kind === "semester")
    .map((w) => ({
      window_id: w.id,
      label: w.label,
      kind: w.id.endsWith("S") ? "summer" : "winter",
      points: fullMembership(w.start_date, w.end_date)
        .map((week, i) => ({ week, i: i + 1, row: byWeek.get(week) }))
        .filter((p) => p.row)
        .map((p) => ({
          semester_week: p.i,
          week: p.week,
          messages: cell(p.row.students, p.row.messages),
          active_students: cell(p.row.students, p.row.students),
        })),
      footnote_ids: ["semester_week_alignment", "cohort_turnover"],
    }));
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

// 1.7.0 (D-55). Every section carries a program-level split, so the fixture has to as
// well — otherwise `pnpm dev` under the default (Bachelor) filter shows the LevelGap
// state on every tab and the new cards can never be looked at. Shares are invented but
// deliberately uneven: staff is small enough to exercise suppression inside a split, and
// "unknown" appears in all_time only, so the picker's optional fourth option is real.
const LEVEL_SHARES = { bachelor: 0.42, master: 0.46, staff: 0.08 };
const levelsFor = (id) =>
  id === "all_time" ? { ...LEVEL_SHARES, unknown: 0.04 } : LEVEL_SHARES;
const scaleWeekly = (rows, share) =>
  rows.map((r) => ({
    ...r,
    students: Math.round(r.students * share),
    messages: Math.round(r.messages * share),
    sessions: Math.round(r.sessions * share),
  }));

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

// The one-week slices are omitted -> exercises the topics WindowGap state; 2025S omits
// emergent_themes -> exercises the per-card absent state. Staff share is small
// enough to suppress in the smaller windows; "unknown" published only where
// non-empty (all_time).
const statusShares = { bachelor: 0.36, master: 0.5, staff: 0.06 };
const topics = {
  per_window: Object.fromEntries(
    Object.keys(windowStudents)
      .filter((id) => !id.endsWith(".last1"))
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

// ---- trends (schema 1.3.0) -------------------------------------------------
// Hand-authored rather than derived, so that one document can hold every window state the
// tab has to branch on. The pipeline can only ever show a real corpus in one state at a
// time; this is the fixture the empty states get built against.
const finding = (o) => ({ method: "two-proportion z, BH-adjusted", footnote_ids: ["trend_method"], ...o });

const trends = {
  per_window: {
    // Earliest semester: nothing before it. Distinct from "we compared and found nothing".
    "2025S": { baseline: null, insufficient_data: false, findings: [] },

    // Compared, and genuinely flat — the "no meaningful shifts" empty state.
    "2025W": { baseline: { kind: "window", window_id: "2025S" }, insufficient_data: false, findings: [] },

    // A full deck: the cap of 5, topics taking its allowance of 3, every finding kind,
    // both evidence markers, and a footnote set that exercises multi-symbol Note. lines.
    "2026S": {
      baseline: { kind: "window", window_id: "2025W" },
      insufficient_data: false,
      findings: [
        finding({
          id: "topics-method_theme-regression",
          tab: "topics",
          title: "Questions about regression modelling rose",
          measure: "Share of messages about regression modelling",
          kind: "share",
          unit: "% of messages",
          current: { value: 23.1, n_students: 47 },
          baseline: { value: 16.0, n_students: 85 },
          delta: 7.1,
          evidence: "robust",
          footnote_ids: ["trend_method", "multi_label", "cohort_turnover"],
        }),
        finding({
          id: "topics-method_theme-anova",
          tab: "topics",
          title: "Questions about the ANOVA family fell",
          measure: "Share of messages about the ANOVA family",
          kind: "share",
          unit: "% of messages",
          current: { value: 8.4, n_students: 24 },
          baseline: { value: 13.8, n_students: 58 },
          delta: -5.4,
          evidence: "robust",
          footnote_ids: ["trend_method", "multi_label"],
        }),
        finding({
          id: "topics-emergent_theme-assumptions",
          tab: "topics",
          title: "Questions about checking assumptions rose",
          measure: "Share of messages about checking assumptions",
          kind: "share",
          unit: "% of messages",
          current: { value: 23.8, n_students: 37 },
          baseline: { value: 17.8, n_students: 73 },
          delta: 6.0,
          evidence: "indicative",
          footnote_ids: ["trend_method", "multi_label", "label_provenance"],
        }),
        finding({
          id: "language-de-share",
          tab: "language",
          title: "German share of messages fell",
          measure: "German share of messages",
          kind: "share",
          unit: "% of messages",
          current: { value: 48.1, n_students: 74 },
          baseline: { value: 61.8, n_students: 91 },
          delta: -13.7,
          evidence: "robust",
          footnote_ids: ["trend_method", "language_heuristic"],
        }),
        finding({
          id: "engagement-messages-per-session",
          tab: "engagement",
          title: "Messages per conversation rose",
          measure: "Median messages per conversation",
          kind: "median",
          unit: "messages",
          current: { value: 4.0, n_students: 66 },
          baseline: { value: 3.0, n_students: 74 },
          delta: 1.0,
          evidence: "indicative",
          method: "Mann-Whitney U (normal approximation)",
          footnote_ids: ["trend_method", "chat_fragmentation"],
        }),
      ],
    },

    // NOTE: the "baseline exists but nothing was testable" state (insufficient_data) lost
    // its home when trailing_4 went away (D-56) — it was the window that sat in break weeks
    // for months. Semester slices carry no trends entry at all, so no window in this
    // fixture exercises that branch today. Restore one here if Trends is un-hidden.

    // Trajectories: one point per semester, so the card draws a slope rather than a delta.
    all_time: {
      baseline: { kind: "trajectory" },
      insufficient_data: false,
      findings: [
        finding({
          id: "language-de-share",
          tab: "language",
          title: "German share of messages fell",
          measure: "German share of messages",
          kind: "share",
          unit: "% of messages",
          current: { value: 48.1, n_students: 74 },
          baseline: { value: 68.2, n_students: 88 },
          delta: -20.1,
          evidence: "robust",
          trajectory: [
            { window_id: "2025S", value: 68.2, n_students: 88 },
            { window_id: "2025W", value: 61.8, n_students: 91 },
            { window_id: "2026S", value: 48.1, n_students: 74 },
          ],
          footnote_ids: ["trend_method", "language_heuristic", "cohort_turnover"],
        }),
        finding({
          id: "adoption-messages-per-week",
          tab: "adoption",
          title: "Messages per week rose",
          measure: "Messages per covered week",
          kind: "rate",
          unit: "per week",
          current: { value: 194.0, n_students: 66 },
          baseline: { value: 105.6, n_students: 61 },
          delta: 88.4,
          evidence: "robust",
          method: "Poisson rate ratio, BH-adjusted",
          trajectory: [
            { window_id: "2025S", value: 105.6, n_students: 61 },
            { window_id: "2025W", value: 142.3, n_students: 74 },
            { window_id: "2026S", value: 194.0, n_students: 66 },
          ],
          footnote_ids: ["trend_method", "per_week_rate", "cohort_turnover"],
        }),
      ],
    },
  },
};

const doc = {
  schema_version: "1.8.0",
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
  dayparts: DAYPARTS,
  // Invented cohort sizes: the real table lives in pipeline/cohort_totals.json and must
  // not be mirrored into a synthetic document (D-55). Semester windows only.
  enrollment: {
    per_window: Object.fromEntries(
      windows
        .filter((w) => w.kind === "semester")
        .map((w) => [
          w.id,
          {
            bachelor: 900,
            master: 600,
            source: "synthetic roster (invented; not SSC-Psych records)",
            as_of: w.start_date,
          },
        ]),
    ),
  },
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
      text: "Classes follow the operational definitions of Bergmann et al. (2026), applied to the selected window: one-time = all messages within 24 hours and spanning under 3 days; monthly = active over 30 days or more with no gap of 30 days or longer; sporadic = everything else. Frequent counts the monthly users who additionally never paused for 14 days, so it is a subset of monthly and is not added to the other three.",
    },
    user_class_window: {
      text: "Each student is classified from their activity inside the selected window only, so a window shorter than 30 days cannot contain a monthly user by definition.",
    },
    retention_definition: {
      text: "New = the student's first-ever message falls inside the selected window; returning = they had already used StatsBot before it. The two add up to the active users. First use is counted from the whole recorded history, including the 2024/25 pilot months that the charts above do not show, so a student who tried StatsBot during the pilot and came back counts as returning. In the all-time window there is no earlier period except that pilot, so returning there names the pilot cohort rather than semester-to-semester loyalty.",
    },
    signup_activation: {
      text: "Counts the students who signed up in this window and sent at least one message within the same window; someone who signed up late and first wrote afterwards is counted in the window they wrote in.",
    },
    status_multi: {
      text: "A student who moved from bachelor to master inside the selected window is counted under both levels, so the student counts can exceed the window total by a few.",
    },
    daypart_definition: {
      text: "Times are Vienna local. The day is split into four equal six-hour blocks — night 00–06, morning 06–12, afternoon 12–18, evening 18–24 — so the bars are directly comparable. Each block counts the messages sent inside it, so a chat that runs past a boundary contributes to both.",
    },
    semester_week_alignment: {
      text: "Week 1 is the semester's first ISO week (the first week whose Thursday falls inside the semester), so the curves line up on teaching week rather than calendar date. Semesters draw largely different cohorts and differ in course structure — summer and winter especially — so compare the shape of a curve rather than its height. A semester still in progress ends where the data does.",
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
    trend_method: {
      text: "Findings are the changes most likely to inform a teaching or tooling decision, among those large and consistent enough to stand out from normal variation.",
    },
    per_week_rate: {
      text: "Volume measures are compared per covered week, so periods of unequal length stay comparable.",
    },
    enrollment_source: { text: "Enrolled totals come from SSC-Psych records." },
    reach_window_scope: {
      text: "Reach is measured against the enrolled cohort of the semester this window belongs to, so in a shorter window it reads as the share of that cohort active during those weeks — not over the whole term.",
    },
    enrollment_scope: {
      text: "The totals include all enrolled bachelor/master students, whereas only the first-year students take the statistics course — data for how many first-year students take it across instructors is not available.",
    },
    level_scope: {
      text: "This figure covers every program level; the program-level filter above does not narrow it.",
    },
    weeks_active_window: {
      text: "Weeks active counts only the ISO weeks inside the selected window, so a shorter window necessarily yields fewer weeks per student; the shares are not comparable between windows of different length.",
    },
    cohort_turnover: {
      text: "Each semester draws a largely different cohort of students; a shift between semesters may reflect who enrolled rather than a change in behavior.",
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
      per_window: perWindow((id) => ({
        activity_heatmap: heatmap(id),
        daypart_heatmap: daypartHeatmap(id),
        daypart_totals: daypartTotals(id),
        // No per-level activity_heatmap: unrendered since D-54, and the contract leaves it
        // out of TemporalUsageByStatus for exactly that reason.
        by_status: Object.fromEntries(
          Object.keys(levelsFor(id)).map((lvl) => [
            lvl,
            { daypart_heatmap: daypartHeatmap(id), daypart_totals: daypartTotals(id) },
          ]),
        ),
      })),
      semester_profiles: semesterProfiles(),
      weekly_by_status: Object.fromEntries(
        Object.entries(levelsFor("all_time")).map(([lvl, share]) => {
          const rows = scaleWeekly(weekly, share);
          return [
            lvl,
            {
              messages: series(rows, (r) => cell(r.students, r.messages)),
              sessions: {
                ...series(rows, (r) => cell(r.students, r.sessions)),
                footnote_ids: ["chat_fragmentation"],
              },
              active_students: series(rows, (r) => cell(r.students, r.students)),
            },
          ];
        }),
      ),
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
        const signups = Math.round(n * 0.8);
        const activated = Math.round(signups * 0.72);
        const newUsers = Math.round(n * 0.68);
        // Mirrors the pipeline's complementary suppression: new + returning = active, so a
        // published part beside a suppressed one would leak by subtraction. Keeping the rule
        // here too means the fixture can never show a shape the pipeline cannot emit.
        const retention =
            Math.min(newUsers, n - newUsers) < FLOOR_N && Math.min(newUsers, n - newUsers) > 0
              ? { new_users: { status: "suppressed" }, returning_users: { status: "suppressed" } }
              : { new_users: cell(newUsers, newUsers), returning_users: cell(n - newUsers, n - newUsers) };
        // 1.4.0: `frequent` is a subset of monthly, so it is deliberately not subtracted
        // from anything; the fixture keeps it small but non-zero to exercise the tile that
        // production currently publishes as a measured 0.
        const frequent = Math.min(monthly, Math.round(n * 0.02));
        return {
          totals: {
            active_students: cell(n, n),
            messages: cell(n, msgs),
            sessions: cell(n, sess),
            new_registrations: cell(n, signups),
            new_registrations_active: cell(activated, activated),
            ...retention,
            footnote_ids: ["retention_definition", "signup_activation"],
          },
          user_classes: {
            one_time: cell(oneTime, oneTime),
            monthly: cell(monthly, monthly),
            sporadic: cell(n - oneTime - monthly, n - oneTime - monthly),
            frequent: cell(frequent, frequent),
            footnote_ids: ["user_class_definitions", "user_class_window"],
          },
          // 1.7.0 widens this from two measures to what the KPI tiles need, because the
          // level filter now scopes the whole tab. new_registrations stays out: a signup
          // has no session, so the usage-time rule cannot resolve its level.
          by_status: Object.fromEntries(
            Object.entries(levelsFor(id)).map(([status, share]) => {
              const students = Math.round(n * share);
              const lvlNew = Math.round(students * 0.68);
              const lvlOne = Math.round(students * 0.55);
              const lvlMonthly = Math.round(students * 0.1);
              return [
                status,
                {
                  active_students: cell(students, students),
                  messages: cell(students, Math.round(msgs * share)),
                  sessions: cell(students, Math.round(sess * share)),
                  new_users: cell(lvlNew, lvlNew),
                  returning_users: cell(students - lvlNew, students - lvlNew),
                  user_classes: {
                    one_time: cell(lvlOne, lvlOne),
                    monthly: cell(lvlMonthly, lvlMonthly),
                    sporadic: cell(students - lvlOne - lvlMonthly, students - lvlOne - lvlMonthly),
                    frequent: cell(0, 0),
                    footnote_ids: ["user_class_definitions", "user_class_window"],
                  },
                  footnote_ids: ["status_rule", "status_multi"],
                },
              ];
            }),
          ),
        };
      }),
    },
    sessions: {
      per_window: perWindow((id) => ({
        by_status: Object.fromEntries(
          Object.keys(levelsFor(id)).map((lvl) => [
            lvl,
            {
              messages_per_session: histogram(
                id, "sessions",
                [[1, 1], [2, 3], [4, 7], [8, null]],
                [0.55, 0.28, 0.12, 0.05],
                { median: 2.0, p25: 1.0, p75: 3.0, mean: 2.3, sd: 1.9 },
                ["chat_fragmentation"],
              ),
              session_duration_minutes: histogram(
                id, "sessions",
                [[0, 1], [2, 5], [6, 15], [16, 30], [31, null]],
                [0.34, 0.27, 0.22, 0.12, 0.05],
                { median: 4.0, p25: 1.0, p75: 12.0 },
                ["chat_fragmentation", "duration_definition"],
              ),
            },
          ]),
        ),
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
    per_student: {
      per_window: perWindow((id) => {
        const bars = (footnotes) => ({
          sessions_per_student: histogram(
            id, "students",
            [[1, 1], [2, 3], [4, 7], [8, null]],
            [0.39, 0.32, 0.2, 0.09],
            { median: 2.0, p25: 1.0, p75: 4.0, mean: 3.1, sd: 3.2 },
            footnotes,
          ),
          weeks_active_per_student: histogram(
            id, "students",
            [[1, 1], [2, 3], [4, 7], [8, null]],
            [0.5, 0.42, 0.08, 0.0],
            { median: 1.5, p25: 1.0, p75: 2.0, mean: 1.8, sd: 1.1 },
            ["weeks_active_window"],
          ),
          messages_per_student: histogram(
            id, "students",
            [[1, 2], [3, 5], [6, 10], [11, 25], [26, null]],
            [0.27, 0.25, 0.23, 0.23, 0.02],
            { median: 5.0, p25: 2.0, p75: 11.0, mean: 7.5, sd: 7.0 },
          ),
        });
        return {
          ...bars(["chat_fragmentation"]),
          by_status: Object.fromEntries(
            Object.keys(levelsFor(id)).map((lvl) => [lvl, bars(["chat_fragmentation"])]),
          ),
        };
      }),
    },
    tokens: {
      // One-week slices deliberately omitted → exercises the "no rollup for this
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
        Object.keys(windowStudents).filter((id) => !id.endsWith(".last1")),
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
        const totalsFor = (scale) =>
          Object.fromEntries(
            Object.entries(langSplit).map(([lang, share]) => {
              const st = Math.round(windowStudents[id] * scale * Math.min(1, share * 2.2));
              return [lang, cell(st, Math.round(msgs * scale * share))];
            }),
          );
        return {
          totals: totalsFor(1),
          by_status: Object.fromEntries(
            Object.entries(levelsFor(id)).map(([lvl, share]) => [lvl, totalsFor(share)]),
          ),
        };
      }),
      weekly_by_status: Object.fromEntries(
        Object.entries(levelsFor("all_time")).map(([lvl, share]) => [
          lvl,
          {
            messages_by_language: {
              ...Object.fromEntries(
                Object.entries(langSplit).map(([lang, langShare]) => [
                  lang,
                  series(scaleWeekly(weekly, share), (r) => {
                    const st = Math.round(r.students * Math.min(1, langShare * 2.2));
                    return cell(st, st === 0 ? 0 : Math.round(r.messages * langShare));
                  }),
                ]),
              ),
              footnote_ids: ["language_heuristic"],
            },
          },
        ]),
      ),
    },
    topics,
    trends,
  },
};

process.stdout.write(JSON.stringify(doc, null, 2) + "\n");
